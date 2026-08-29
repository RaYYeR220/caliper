"""A readable chart summary, for the human who has to label a case.

Annotated cases in the answer key are only as good as what the annotator was shown, which puts two
constraints on this module.

It is byte-deterministic. The summary is committed next to the labels derived from it, so a judge
can see exactly what the annotator read; a summary that drifted with dictionary order or with the
wall clock would make that pairing meaningless.

It never silently drops a fact. There is no cap on the number of results, conditions or drugs: a
summary that quietly omitted the only creatinine would produce an annotated "unknown" that the key
then treats as ground truth. Length is the cheaper failure. Compactness comes from one line per
fact and from folding the resolved history into a single paragraph, not from truncation. What is
excluded — evidence recorded after the screening date, observations carrying no number — is stated
with its count rather than left to be inferred.

Every line carries a date, because almost every eligibility question is a question about time.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from datetime import date
from typing import Any

from caliper.record import Evidence, PatientIndex
from caliper.units import normalise_unit

# `fhir.py` renders a Condition as "<display> (<clinical>, <verification>)", and that suffix is the
# only status signal `Evidence` carries, so it is read back here rather than guessed at. A
# parenthetical that is not a status vocabulary term — "(disorder)", "(finding)" — is left alone.
_TRAILING_PARENTHETICAL = re.compile(r"\s*\(([^()]*)\)\s*$")

_CLINICAL_STATUSES = frozenset(
    {"active", "recurrence", "relapse", "inactive", "remission", "resolved"}
)
_VERIFICATION_STATUSES = frozenset(
    {"unconfirmed", "provisional", "differential", "confirmed", "refuted", "entered-in-error"}
)
_CLOSED_STATUSES = frozenset({"inactive", "remission", "resolved"})

_UNDATED = "undated"


def _iso(when: date | None) -> str | None:
    return when.isoformat() if when else None


def _stamp(value: str | None) -> str:
    return value or _UNDATED


def _number(value: float) -> str:
    return f"{value:g}"


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    return f"{count} {singular if count == 1 else (plural or singular + 's')}"


def _recency_key(row: Evidence) -> tuple[bool, date]:
    """The ordering `PatientIndex.find` uses, so the summary and the evaluator agree on 'latest'."""
    return (row.date is not None, row.date or date.min)


def _most_recent_first(rows: Iterable[Evidence]) -> list[Evidence]:
    return sorted(rows, key=_recency_key, reverse=True)


def _code(row: Evidence, system: str) -> str | None:
    return next((code.code for code in row.codes if code.system == system), None)


def _label(row: Evidence) -> str:
    """What to call a row on the page.

    Some rows genuinely have no name. Synthea writes a third of its MedicationRequests as a
    reference to a `Medication` resource that the trimmed corpus does not carry, so `fhir.py` has
    nothing to display. Saying so is the point: a blank line would read as a formatting glitch,
    where "(unlabelled MedicationRequest)" tells an annotator the drug is genuinely not on file.
    """
    return row.display.strip() or f"(unlabelled {row.resource_type})"


def _grouping_key(row: Evidence, system: str) -> str:
    """How rows are collapsed into one analyte or one drug.

    A row with neither a code nor a name falls back to its own resource id rather than joining
    every other nameless row under the empty string, which would hide how many there were.
    """
    code = _code(row, system)
    if code:
        return f"{system}:{code}"
    label = row.display.strip().casefold()
    return f"display:{label}" if label else f"resource:{row.resource_id}"


def _split_status(display: str) -> tuple[str, str | None, str | None]:
    """Separate a condition's label from its status suffix, or leave the display untouched."""
    match = _TRAILING_PARENTHETICAL.search(display)
    if match is None:
        return display, None, None
    tokens = [token.strip().casefold() for token in match.group(1).split(",")]
    known = _CLINICAL_STATUSES | _VERIFICATION_STATUSES
    if not tokens or any(token not in known for token in tokens):
        return display, None, None
    label = display[: match.start()].strip() or display
    clinical = next((token for token in tokens if token in _CLINICAL_STATUSES), None)
    verification = next((token for token in tokens if token in _VERIFICATION_STATUSES), None)
    return label, clinical, verification


def _entry_order(entry: dict[str, Any]) -> tuple[str, str, str]:
    return (entry["date"] or "", entry["display"].casefold(), entry["resource_id"])


def _condition_entries(rows: list[Evidence]) -> dict[str, list[dict[str, Any]]]:
    """Split conditions into the ones still in play and the ones the chart has closed."""
    active: list[dict[str, Any]] = []
    closed: list[dict[str, Any]] = []
    for row in rows:
        label, clinical, verification = _split_status(_label(row))
        entry = {
            "date": _iso(row.date),
            "display": label,
            "status": clinical,
            "verification": verification,
            "resource_id": row.resource_id,
        }
        # An unstated clinical status stays visible: silence is not resolution.
        (closed if clinical in _CLOSED_STATUSES else active).append(entry)
    return {
        "active": sorted(active, key=_entry_order),
        "inactive": sorted(closed, key=_entry_order),
    }


def _medication_entries(rows: list[Evidence]) -> list[dict[str, Any]]:
    """The most recent order for each distinct drug.

    `Evidence` does not carry MedicationRequest.status, so no claim about a drug being current can
    be made here. The latest order per drug, with its date, is the strongest honest substitute.
    """
    latest: dict[str, Evidence] = {}
    for row in _most_recent_first(rows):
        latest.setdefault(_grouping_key(row, "RxNorm"), row)
    entries = [
        {"date": _iso(row.date), "display": _label(row), "resource_id": row.resource_id}
        for row in latest.values()
    ]
    return sorted(entries, key=lambda entry: (entry["display"].casefold(), entry["date"] or ""))


def _trend(latest: Evidence, previous: Evidence | None) -> str | None:
    """Which way the analyte is moving, or None when a single result makes the question moot."""
    if previous is None or previous.value is None or latest.value is None:
        return None
    if normalise_unit(latest.unit or "") != normalise_unit(previous.unit or ""):
        # Reading 88 umol/L against 1.0 mg/dL as bare numbers would invent a direction.
        return "unit changed"
    if latest.value > previous.value:
        return "rising"
    if latest.value < previous.value:
        return "falling"
    return "unchanged"


def _analyte_entries(rows: list[Evidence]) -> list[dict[str, Any]]:
    """One entry per distinct analyte, holding its latest value and the shape of its history."""
    groups: dict[str, list[Evidence]] = {}
    for row in rows:
        groups.setdefault(_grouping_key(row, "LOINC"), []).append(row)

    entries = []
    for series in groups.values():
        ordered = _most_recent_first(series)
        latest = ordered[0]
        previous = ordered[1] if len(ordered) > 1 else None
        dated = [row.date for row in ordered if row.date is not None]
        entries.append(
            {
                "loinc": _code(latest, "LOINC"),
                "display": _label(latest),
                "value": latest.value,
                "unit": latest.unit,
                "date": _iso(latest.date),
                "resource_id": latest.resource_id,
                "count": len(ordered),
                "first_date": _iso(min(dated)) if dated else None,
                "previous_value": previous.value if previous else None,
                "previous_unit": previous.unit if previous else None,
                "previous_date": _iso(previous.date) if previous else None,
                "trend": _trend(latest, previous),
            }
        )
    return sorted(entries, key=lambda entry: (entry["display"].casefold(), entry["loinc"] or ""))


def _note_entries(rows: list[Evidence]) -> list[dict[str, Any]]:
    entries = [
        {"date": _iso(row.date), "display": _label(row), "resource_id": row.resource_id}
        for row in rows
    ]
    return sorted(entries, key=lambda entry: (entry["date"] or "", entry["resource_id"]))


def summarise_dict(patient: PatientIndex, *, as_of: date) -> dict[str, Any]:
    """The chart summary as structured data, in the order `summarise` renders it.

    Every value is JSON-safe — dates are ISO strings — so this can be committed beside the Markdown,
    served to a review UI, or diffed between two versions of one bundle.
    """
    current = [row for row in patient.evidence if row.date is None or row.date <= as_of]
    excluded = len(patient.evidence) - len(current)

    by_kind: dict[str, list[Evidence]] = {}
    for row in current:
        by_kind.setdefault(row.kind, []).append(row)

    observations = by_kind.get("observation", [])
    numeric = [row for row in observations if row.value is not None]
    encounters = by_kind.get("encounter", [])
    encounter_dates = [row.date for row in encounters if row.date is not None]
    age = patient.age_at(as_of)

    return {
        "patient_id": patient.patient_id,
        "as_of": as_of.isoformat(),
        "demographics": {
            "birth_date": _iso(patient.birth_date),
            "age_years": None if age is None else int(age),
            "sex": patient.sex,
        },
        "conditions": _condition_entries(by_kind.get("condition", [])),
        "medications": _medication_entries(by_kind.get("medication", [])),
        "analytes": _analyte_entries(numeric),
        "observations_without_value": len(observations) - len(numeric),
        "encounters": {
            "count": len(encounters),
            "first_date": _iso(min(encounter_dates)) if encounter_dates else None,
            "last_date": _iso(max(encounter_dates)) if encounter_dates else None,
        },
        "notes": _note_entries(by_kind.get("note", [])),
        "excluded_after_screening": excluded,
    }


def _condition_line(entry: dict[str, Any]) -> str:
    label = entry["display"]
    if entry["verification"] and entry["verification"] != "confirmed":
        label = f"{label} [{entry['verification']}]"
    return f"- {_stamp(entry['date'])}  {label}"


def _dated_line(entry: dict[str, Any]) -> str:
    return f"- {_stamp(entry['date'])}  {entry['display']}"


def _analyte_line(entry: dict[str, Any]) -> str:
    unit = f" {entry['unit']}" if entry["unit"] else ""
    code = f" [LOINC {entry['loinc']}]" if entry["loinc"] else ""
    head = f"- {_stamp(entry['date'])}  {entry['display']}{code}: {_number(entry['value'])}{unit}"
    if entry["count"] == 1:
        return f"{head} (only result on file)"
    previous_unit = f" {entry['previous_unit']}" if entry["previous_unit"] else ""
    return (
        f"{head} ({_plural(entry['count'], 'result')} since {entry['first_date']}; "
        f"previous {_number(entry['previous_value'])}{previous_unit} on "
        f"{entry['previous_date']}, {entry['trend']})"
    )


def _section(title: str, lines: Sequence[str], *, empty: str) -> list[str]:
    return [f"## {title}", "", *(lines or [empty]), ""]


def _preamble(summary: dict[str, Any]) -> str:
    excluded = summary["excluded_after_screening"]
    text = f"Screening date: {summary['as_of']}. Only facts recorded on or before it are shown"
    if excluded:
        verb = "is" if excluded == 1 else "are"
        text += f"; {_plural(excluded, 'record')} dated after the screening date {verb} excluded"
    return f"{text}."


def _results_section(summary: dict[str, Any], focus_codes: Sequence[str]) -> list[str]:
    """Render the analyte table, lifting the focus codes into a block of their own."""
    analytes = summary["analytes"]
    wanted = list(dict.fromkeys(focus_codes))
    focused = [entry for code in wanted for entry in analytes if entry["loinc"] == code]
    in_focus = {entry["loinc"] for entry in focused}
    rest = [entry for entry in analytes if entry["loinc"] not in in_focus]

    heading = f"Results ({_plural(len(analytes), 'analyte')}"
    heading += f"; {len(focused)} in focus)" if focused else ")"
    lines = [f"## {heading}", ""]

    if not analytes:
        lines.append("No numeric results on file.")
    elif focused:
        lines += ["### In focus", "", *(_analyte_line(entry) for entry in focused), ""]
        lines += ["### Other results", ""]
        lines += [_analyte_line(entry) for entry in rest] or ["None."]
    else:
        lines += [_analyte_line(entry) for entry in rest]

    missing = summary["observations_without_value"]
    if missing:
        carry, listed = ("carries", "is") if missing == 1 else ("carry", "are")
        lines += [
            "",
            f"{_plural(missing, 'further observation')} {carry} no numeric value "
            f"and {listed} not listed.",
        ]
    return [*lines, ""]


def summarise(patient: PatientIndex, *, as_of: date, focus_codes: Sequence[str] = ()) -> str:
    """Render a compact clinical summary a coordinator can annotate from.

    `focus_codes` are LOINC codes to lift to the top of the results section — the analytes a
    particular trial turns on. Focusing only reorders; nothing is ever removed by it, because an
    annotator who cannot see a result cannot label the case honestly.
    """
    summary = summarise_dict(patient, as_of=as_of)
    demographics = summary["demographics"]
    born = demographics["birth_date"]

    lines = [
        f"# Chart summary: {summary['patient_id']}",
        "",
        _preamble(summary),
        "",
        "## Demographics",
        "",
        f"- Date of birth: {born} (age {demographics['age_years']} at {summary['as_of']})"
        if born
        else "- Date of birth: not recorded, so age is unknown",
        f"- Sex: {demographics['sex'] or 'not recorded'}",
        "",
    ]

    active = summary["conditions"]["active"]
    lines += _section(
        f"Active conditions ({len(active)})",
        [_condition_line(entry) for entry in active],
        empty="None recorded.",
    )

    closed = summary["conditions"]["inactive"]
    folded = "; ".join(f"{entry['display']} ({_stamp(entry['date'])})" for entry in closed)
    lines += _section(
        f"Resolved or inactive conditions ({len(closed)})",
        [folded] if folded else [],
        empty="None recorded.",
    )

    medications = summary["medications"]
    lines += _section(
        f"Medications ({len(medications)}, most recent order per drug)",
        [_dated_line(entry) for entry in medications],
        empty="None recorded.",
    )

    lines += _results_section(summary, focus_codes)

    encounters = summary["encounters"]
    lines += _section(
        "Encounters",
        [
            f"{_plural(encounters['count'], 'encounter')}, "
            f"{encounters['first_date']} to {encounters['last_date']}."
        ]
        if encounters["count"] and encounters["first_date"]
        else [],
        empty="None recorded.",
    )

    lines += _section(
        f"Notes ({len(summary['notes'])})",
        [_dated_line(entry) for entry in summary["notes"]],
        empty="No notes on file.",
    )

    return "\n".join(lines).rstrip("\n") + "\n"
