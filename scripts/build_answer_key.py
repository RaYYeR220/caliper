"""Assemble, derive, validate and freeze `eval/answer_key.json` from the annotation artifacts.

The key is not written by hand. Every case in it is built here from three things that are written
by hand — the criterion decomposition in `eval/annotation/criteria.json`, the two independent
annotation passes, and the adjudication of the criteria where they differed — and one thing that is
not: the case-level outcome, which this script derives by calling `caliper.logic.roll_up` on the
adjudicated criterion labels.

Deriving rather than asserting is the point of the exercise. A case-level label written down by a
reader who had just read the whole chart is exactly the failure mode the evaluation exists to
detect, so the key must not contain one. Because the rollup is imported rather than reimplemented,
the key also cannot drift away from the logic it claims to follow: if `roll_up` changes, this script
produces a different key and the frozen digest stops matching.

The script refuses to guess. A criterion the two passes disagreed on and the adjudication file does
not decide is an error, not a coin toss.

Two passes exist because the first scored run found errors in the key rather than in the system,
and both are described in `eval/annotation/corrections.md`.

`vital_status` applies the rule that precedes every criterion: a patient the chart records as dead
before the screening date is `ineligible`, and no criterion is evaluated. It reads the bundle's
`Patient.deceasedDateTime` directly rather than asking `PatientIndex`, for the same reason the
refutation pass does.

`refute` tries to contradict every `met` label against the raw committed FHIR: `data/patients`
read here, with no help from `caliper.record`, `caliper.evaluate` or `PatientIndex`, because
validating the key with the same matching code the key is used to score would establish nothing.
It flags; it does not fix. A flag it raises against an annotated case is an error in the key. A flag
it raises against a constructed case whose own recorded edits supply the fact is not: that is what a
constructed case is, and the pass reports the two separately.

Usage:
    python scripts/build_answer_key.py            # rebuild, validate, freeze, print the summary
    python scripts/build_answer_key.py --dry-run  # everything except writing the key
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass, replace
from datetime import date
from typing import Any

from _datalib import REPO_ROOT
from rich.console import Console
from rich.table import Table

from caliper.answerkey import (
    AnswerKey,
    Case,
    CriterionLabel,
    freeze,
    key_fingerprint,
    load_key,
    verify_frozen,
)
from caliper.corpus import load_patient
from caliper.ir import Code
from caliper.logic import CriterionVerdict, ScreeningOutcome, Verdict, roll_up
from caliper.perturb import (
    Perturbation,
    PerturbedPatient,
    add_condition,
    redact_analyte,
    shift_value,
)
from caliper.record import Evidence, PatientIndex

ANNOTATION_DIR = REPO_ROOT / "eval" / "annotation"
PATIENT_DIR = REPO_ROOT / "data" / "patients"
KEY_PATH = REPO_ROOT / "eval" / "answer_key.json"

SCREENING_DATE = date(2026, 6, 1)

# Both passes are language models, and `adjudicated_by` is a person. The key says so in the
# annotator names themselves so that no reader can mistake either pass for a clinician.
ANNOTATORS = ("llm-pass-1", "llm-pass-2")
ADJUDICATOR = "maintainer"

VERDICTS = ("met", "not_met", "unknown")

# `caliper.perturb` has no function that puts an observation on a chart, and this script may not
# add one to that module. Rows are therefore built here, recorded as an equivalent `Perturbation`
# so the case still documents exactly what changed, and marked with a synthetic `fhir_path` so
# nothing pretends to point at a bundle entry.
_SYNTHETIC_PATH = "build_answer_key.add_observation"

# How many unresolved criteria to name in a derived rationale before summarising the rest.
_MAX_NAMED_UNRESOLVED = 4


class BuildError(RuntimeError):
    """The annotation artifacts do not describe a key that can be built."""


def _read(name: str) -> Any:
    path = ANNOTATION_DIR / name
    if not path.is_file():
        raise BuildError(f"missing annotation artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _criterion_index(criteria: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Every in-scope criterion by id, carrying its kind and the quote the annotators read."""
    index: dict[str, dict[str, Any]] = {}
    for nct_id, trial in criteria["trials"].items():
        for entry in trial["criteria"]:
            if entry["in_scope"]:
                index[entry["id"]] = {**entry, "nct_id": nct_id}
    return index


def _labels_by_case(payload: dict[str, Any], where: str) -> dict[str, dict[str, str]]:
    """One pass, flattened to {case_id: {criterion_id: verdict}}, with the shape checked."""
    out: dict[str, dict[str, str]] = {}
    for pair in payload["pairs"]:
        case_id = pair["case_id"]
        if case_id in out:
            raise BuildError(f"{where}: case {case_id} appears twice")
        labels: dict[str, str] = {}
        for label in pair["labels"]:
            criterion_id, verdict = label["criterion_id"], label["verdict"]
            if verdict not in VERDICTS:
                raise BuildError(f"{where}: {case_id} {criterion_id}: bad verdict {verdict!r}")
            labels[criterion_id] = verdict
        out[case_id] = labels
    return out


def _expected_criteria(nct_id: str, index: dict[str, dict[str, Any]]) -> list[str]:
    return [cid for cid, entry in index.items() if entry["nct_id"] == nct_id]


def adjudicate(
    pairs: list[dict[str, str]],
    index: dict[str, dict[str, Any]],
    pass1: dict[str, dict[str, str]],
    pass2: dict[str, dict[str, str]],
    decisions: dict[tuple[str, str], dict[str, Any]],
) -> tuple[dict[str, dict[str, str]], list[tuple[str, str]]]:
    """Resolve the two passes into one label per criterion, and report what had to be decided."""
    resolved: dict[str, dict[str, str]] = {}
    disagreed: list[tuple[str, str]] = []

    for pair in pairs:
        case_id, nct_id = pair["case_id"], pair["nct_id"]
        wanted = _expected_criteria(nct_id, index)
        for name, labels in (("pass1", pass1), ("pass2", pass2)):
            if case_id not in labels:
                raise BuildError(f"{name} has no labels for {case_id}")
            missing = set(wanted) - set(labels[case_id])
            extra = set(labels[case_id]) - set(wanted)
            if missing or extra:
                raise BuildError(
                    f"{name} {case_id}: missing {sorted(missing)}, extra {sorted(extra)}"
                )

        agreed: dict[str, str] = {}
        for criterion_id in wanted:
            first, second = pass1[case_id][criterion_id], pass2[case_id][criterion_id]
            if first == second:
                agreed[criterion_id] = first
                continue
            disagreed.append((case_id, criterion_id))
            decision = decisions.get((case_id, criterion_id))
            if decision is None:
                raise BuildError(
                    f"{case_id} {criterion_id}: passes differ ({first} vs {second}) and "
                    "adjudication.json does not decide it"
                )
            if decision["verdict"] not in VERDICTS:
                raise BuildError(f"{case_id} {criterion_id}: bad adjudicated verdict")
            if not str(decision.get("reason", "")).strip():
                raise BuildError(f"{case_id} {criterion_id}: adjudication carries no reason")
            agreed[criterion_id] = decision["verdict"]
        resolved[case_id] = agreed

    undecided = set(decisions) - set(disagreed)
    if undecided:
        raise BuildError(
            f"adjudication.json decides criteria the passes agreed on: {sorted(undecided)}"
        )
    return resolved, disagreed


def add_observation(
    patient: PatientIndex,
    *,
    loinc: str,
    display: str,
    value: float,
    unit: str,
    when: date,
) -> PerturbedPatient:
    """Put one numeric observation on the chart, as `perturb.add_condition` puts a diagnosis.

    This is the gap in `caliper.perturb`: it can move a value, remove one, or add a condition, but
    it cannot supply a measurement that was never taken, which is exactly what a constructed
    eligible case needs. The row is assembled here rather than there because this script may not
    edit that module.
    """
    resource_id = f"constructed-observation-loinc-{loinc}-{when.isoformat()}"
    added = Evidence(
        kind="observation",
        resource_type="Observation",
        resource_id=resource_id,
        display=display,
        fhir_path=_SYNTHETIC_PATH,
        codes=(Code(system="LOINC", code=loinc, display=display),),
        value=value,
        unit=unit,
        date=when,
    )
    record = Perturbation(
        kind="add_observation",
        description=(
            f"added observation LOINC {loinc} ({display}) with value {value} {unit} "
            f"dated {when.isoformat()}"
        ),
        affected_resource_ids=(resource_id,),
        before=(),
        after=(
            {
                "resource_id": resource_id,
                "resource_type": "Observation",
                "kind": "observation",
                "display": display,
                "fhir_path": _SYNTHETIC_PATH,
                "codes": [{"system": "LOINC", "code": loinc}],
                "value": value,
                "unit": unit,
                "date": when.isoformat(),
            },
        ),
    )
    return PerturbedPatient(
        patient=replace(patient, evidence=[*patient.evidence, added]),
        perturbations=(record,),
    )


def _latest_analyte(patient: PatientIndex, loinc: str) -> Evidence | None:
    rows = [
        row
        for row in patient.evidence
        if row.kind == "observation"
        and any(c.system == "LOINC" and c.code == loinc for c in row.codes)
    ]
    if not rows:
        return None
    return max(rows, key=lambda r: (r.date is not None, r.date or date.min))


def _apply_step(current: PerturbedPatient, step: dict[str, Any]) -> PerturbedPatient:
    op = step["op"]
    if op == "shift_value":
        return current.then(shift_value, step["loinc"], to=step["to"])
    if op == "redact_analyte":
        return current.then(redact_analyte, step["loinc"])
    if op == "add_condition":
        return current.then(
            add_condition,
            Code(system=step["system"], code=step["code"], display=step["display"]),
            step["display"],
            onset=date.fromisoformat(step["onset"]),
        )
    if op == "add_observation":
        return current.then(
            add_observation,
            loinc=step["loinc"],
            display=step["display"],
            value=step["value"],
            unit=step["unit"],
            when=date.fromisoformat(step["date"]),
        )
    raise BuildError(f"unknown perturbation op {op!r}")


def _check_step(patient: PatientIndex, step: dict[str, Any], where: str) -> None:
    """Confirm the edit is visible in the finished chart, not merely requested.

    `perturb` raises when a target is absent, but it cannot know that a later step undid an earlier
    one. A constructed case whose label asserts a value the chart does not carry is the worst
    failure available here, so every step is read back off the result.
    """
    op = step["op"]
    if op in ("shift_value", "add_observation"):
        latest = _latest_analyte(patient, step["loinc"])
        wanted = step["to"] if op == "shift_value" else step["value"]
        if latest is None or latest.value != wanted:
            got = "no result" if latest is None else str(latest.value)
            raise BuildError(f"{where}: LOINC {step['loinc']} reads {got}, expected {wanted}")
    elif op == "redact_analyte":
        if _latest_analyte(patient, step["loinc"]) is not None:
            raise BuildError(f"{where}: LOINC {step['loinc']} survived redaction")
    elif op == "add_condition":
        present = any(
            row.kind == "condition"
            and any(c.system == step["system"] and c.code == step["code"] for c in row.codes)
            for row in patient.evidence
        )
        if not present:
            raise BuildError(f"{where}: condition {step['code']} is not on the finished chart")


def _is_blocker(kind: str, verdict: str) -> bool:
    """Whether this label is what stops the case reaching `eligible`."""
    return verdict != ("met" if kind == "inclusion" else "not_met")


# ------------------------------------------------------------------------------------------------
# Reading the raw bundles, without the system's help
# ------------------------------------------------------------------------------------------------

# Terminology systems as the bundles spell them, mapped to the short names the annotation uses.
_SYSTEMS = {
    "http://loinc.org": "LOINC",
    "http://snomed.info/sct": "SNOMED",
    "http://www.nlm.nih.gov/research/umls/rxnorm": "RxNorm",
}

_MEDICATION_TYPES = ("MedicationRequest", "MedicationStatement", "MedicationAdministration")


@dataclass(frozen=True)
class Fact:
    """One thing the bundle says, flattened far enough to be looked for and quoted back."""

    kind: str
    codes: tuple[tuple[str, str], ...]
    display: str
    value: float | None = None
    unit: str | None = None
    when: date | None = None
    status: str | None = None

    def has(self, system: str, codes: tuple[str, ...]) -> bool:
        return any(s == system and c in codes for s, c in self.codes)

    @property
    def cited(self) -> str:
        stamp = self.when.isoformat() if self.when else "undated"
        if self.value is not None:
            return f"{self.value} {self.unit or ''}".strip() + f" on {stamp}"
        return f"{self.display} ({stamp})"


@dataclass(frozen=True)
class Chart:
    """A whole bundle as plain facts: what the committed JSON says, and nothing derived from it."""

    patient_id: str
    birth_date: date | None
    sex: str | None
    deceased: date | None
    deceased_undated: bool
    facts: tuple[Fact, ...]

    def age_at(self, as_of: date) -> int | None:
        if self.birth_date is None:
            return None
        born = self.birth_date
        return as_of.year - born.year - ((as_of.month, as_of.day) < (born.month, born.day))

    def died_before(self, as_of: date) -> bool:
        return self.deceased is not None and self.deceased <= as_of


def _stamp(value: Any) -> date | None:
    if not isinstance(value, str) or not value[:10]:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _codings(concept: Any) -> tuple[tuple[str, str], ...]:
    if not isinstance(concept, dict):
        return ()
    out = []
    for coding in concept.get("coding") or ():
        system = _SYSTEMS.get(str(coding.get("system", "")))
        code = coding.get("code")
        if system and code:
            out.append((system, str(code)))
    return tuple(out)


def _wording(concept: Any, codes: tuple[tuple[str, str], ...]) -> str:
    if isinstance(concept, dict):
        if concept.get("text"):
            return str(concept["text"])
        for coding in concept.get("coding") or ():
            if coding.get("display"):
                return str(coding["display"])
    return ", ".join(f"{system} {code}" for system, code in codes)


def _observation_facts(resource: dict[str, Any], when: date | None) -> list[Fact]:
    """One fact per coded numeric result, with panel components counted as results themselves."""
    parts: list[tuple[Any, Any]] = [(resource.get("code"), resource.get("valueQuantity"))]
    parts += [
        (component.get("code"), component.get("valueQuantity"))
        for component in resource.get("component") or ()
        if isinstance(component, dict)
    ]
    facts = []
    for concept, quantity in parts:
        codes = _codings(concept)
        if not codes:
            continue
        value = quantity.get("value") if isinstance(quantity, dict) else None
        unit = quantity.get("unit") if isinstance(quantity, dict) else None
        facts.append(
            Fact(
                kind="observation",
                codes=codes,
                display=_wording(concept, codes),
                value=float(value) if isinstance(value, int | float) else None,
                unit=str(unit) if unit else None,
                when=when,
            )
        )
    return facts


def read_chart(patient_id: str) -> Chart:
    """Everything the refutation pass is allowed to know about a patient.

    Deliberately its own reader. `caliper.fhir` is the code under evaluation; a key checked with it
    could only ever agree with it, and a judge is entitled to see that this pass never touches it.
    """
    path = PATIENT_DIR / f"{patient_id}.json"
    if not path.is_file():
        raise BuildError(f"no committed bundle for patient {patient_id}: {path} is missing")
    bundle = json.loads(path.read_text(encoding="utf-8"))

    birth_date: date | None = None
    sex: str | None = None
    deceased: date | None = None
    deceased_undated = False
    facts: list[Fact] = []

    for entry in bundle.get("entry") or ():
        resource = entry.get("resource") if isinstance(entry, dict) else None
        if not isinstance(resource, dict):
            continue
        kind = resource.get("resourceType")

        if kind == "Patient":
            birth_date = _stamp(resource.get("birthDate"))
            sex = resource.get("gender")
            deceased = _stamp(resource.get("deceasedDateTime"))
            deceased_undated = deceased is None and bool(resource.get("deceasedBoolean"))
        elif kind == "Condition":
            codes = _codings(resource.get("code"))
            if codes:
                coded_status = (resource.get("clinicalStatus") or {}).get("coding") or [{}]
                facts.append(
                    Fact(
                        kind="condition",
                        codes=codes,
                        display=_wording(resource.get("code"), codes),
                        when=_stamp(resource.get("onsetDateTime")),
                        status=str(coded_status[0].get("code") or "") or None,
                    )
                )
        elif kind == "Observation":
            facts += _observation_facts(resource, _stamp(resource.get("effectiveDateTime")))
        elif kind in _MEDICATION_TYPES:
            codes = _codings(resource.get("medicationCodeableConcept"))
            if codes:
                facts.append(
                    Fact(
                        kind="medication",
                        codes=codes,
                        display=_wording(resource.get("medicationCodeableConcept"), codes),
                        when=_stamp(
                            resource.get("authoredOn") or resource.get("effectiveDateTime")
                        ),
                    )
                )

    return Chart(
        patient_id=patient_id,
        birth_date=birth_date,
        sex=sex,
        deceased=deceased,
        deceased_undated=deceased_undated,
        facts=tuple(facts),
    )


def _snapshot_fact(snapshot: dict[str, Any]) -> Fact:
    """One published perturbation row, read as a fact so it can be looked for like any other."""
    return Fact(
        kind=str(snapshot.get("kind", "")),
        codes=tuple(
            (str(c["system"]), str(c["code"])) for c in snapshot.get("codes") or () if c.get("code")
        ),
        display=str(snapshot.get("display", "")),
        value=snapshot.get("value"),
        unit=snapshot.get("unit"),
        when=_stamp(snapshot.get("date")),
        status="active",
    )


def as_built(chart: Chart, case: Case) -> Chart:
    """The chart a case is actually about, at the level of plain facts.

    This is not a second `rebuild_patient`: it produces no `PatientIndex`, and it exists so the
    refutation pass can say *which* of two different things is true of a flagged label — that the
    record does not support it at all, or that the case's own published edits supply it. Both
    answers are needed, and both have to be reached without the system's matching code.
    """
    if not case.perturbations:
        return chart
    facts = list(chart.facts)
    for record in case.perturbations:
        for snapshot in record.get("before") or ():
            wanted = _snapshot_fact(snapshot)
            matched = [
                fact
                for fact in facts
                if fact.kind == wanted.kind
                and fact.value == wanted.value
                and fact.unit == wanted.unit
                and fact.when == wanted.when
                and set(wanted.codes) <= set(fact.codes)
            ]
            if len(matched) != 1:
                raise BuildError(
                    f"case {case.id}: the recorded {record.get('kind')} removes "
                    f"{wanted.cited}, which the committed bundle carries {len(matched)} times"
                )
            facts.remove(matched[0])
        facts += [_snapshot_fact(snapshot) for snapshot in record.get("after") or ()]
    return replace(chart, facts=tuple(facts))


# ------------------------------------------------------------------------------------------------
# The refutation pass
# ------------------------------------------------------------------------------------------------

# What a probe can fail on. `supplied` is not an error: it says the committed bundle does not carry
# the fact and the case's own perturbation record does, which is the definition of a constructed
# case. `refuted` says nothing anywhere supports the label.
REFUTED, SUPPLIED = "refuted", "supplied"


@dataclass(frozen=True)
class Flag:
    """One `met` label the raw chart will not support, and the value or absence that says so."""

    case_id: str
    criterion_id: str
    provenance: str
    status: str
    finding: str


def _numbers(chart: Chart, loinc: tuple[str, ...], as_of: date) -> list[Fact]:
    rows = [
        fact
        for fact in chart.facts
        if fact.kind == "observation"
        and fact.value is not None
        and fact.has("LOINC", loinc)
        and (fact.when is None or fact.when <= as_of)
    ]
    return sorted(rows, key=lambda f: (f.when is not None, f.when or date.min))


def _within(value: float, term: dict[str, Any]) -> bool:
    if "at_least" in term and value < term["at_least"]:
        return False
    if "at_most" in term and value > term["at_most"]:
        return False
    if "above" in term and value <= term["above"]:
        return False
    return not ("below" in term and value >= term["below"])


def _bound_text(term: dict[str, Any]) -> str:
    words = {"at_least": ">=", "at_most": "<=", "above": ">", "below": "<"}
    return " and ".join(f"{words[k]} {term[k]}" for k in words if k in term) or "any value"


def _conditions(chart: Chart, term: dict[str, Any]) -> list[Fact]:
    system, codes = str(term["system"]), tuple(str(c) for c in term["codes"])
    rows = [fact for fact in chart.facts if fact.kind == "condition" and fact.has(system, codes)]
    if term.get("status"):
        rows = [fact for fact in rows if fact.status == term["status"]]
    onset = _stamp(term.get("onset_on_or_before"))
    if onset is not None:
        rows = [fact for fact in rows if fact.when is not None and fact.when <= onset]
    return rows


def _check(term: Any, chart: Chart, as_of: date, where: str) -> str | None:
    """None if the chart could support this term, otherwise what refutes it, in words."""
    if not isinstance(term, dict) or len(term) != 1:
        raise BuildError(f"{where}: a probe term must be a single-key object, got {term!r}")
    (name, body), = term.items()

    if name == "all_of":
        failures = [_check(sub, chart, as_of, where) for sub in body]
        found = [f for f in failures if f]
        return "; ".join(found) if found else None

    if name == "any_of":
        failures = [_check(sub, chart, as_of, where) for sub in body]
        if any(f is None for f in failures):
            return None
        return "no branch holds: " + " / ".join(f for f in failures if f)

    if name == "age":
        age = chart.age_at(as_of)
        if age is None:
            return "the bundle records no date of birth"
        if _within(float(age), body):
            return None
        return f"the patient is {age} at screening, and the criterion asks for {_bound_text(body)}"

    if name == "sex":
        if chart.sex in tuple(body):
            return None
        return (
            f"the bundle records sex {chart.sex!r}, and the criterion asks "
            f"for one of {list(body)}"
        )

    if name == "condition":
        if _conditions(chart, body):
            return None
        system = str(body["system"])
        wanted = f"{system} {'/'.join(str(c) for c in body['codes'])}"
        near = tuple(str(c) for c in body.get("near") or ())
        found = sorted(
            {
                f"{fact.display} ({system} {fact.codes[0][1]})"
                for fact in chart.facts
                if fact.kind == "condition" and near and fact.has(system, near)
            }
        )
        instead = f"; what the chart records instead is {', '.join(found)}" if found else ""
        qualifier = " and active" if body.get("status") == "active" else ""
        return f"no condition coded {wanted}{qualifier} is on the chart{instead}"

    if name == "absent_condition":
        rows = _conditions(chart, body)
        if not rows:
            return None
        return "the chart does carry " + ", ".join(sorted({f.display for f in rows}))

    if name == "medication":
        system, codes = str(body["system"]), tuple(str(c) for c in body["codes"])
        if any(fact.kind == "medication" and fact.has(system, codes) for fact in chart.facts):
            return None
        return f"no medication coded {system} {'/'.join(codes)} is on the chart"

    if name == "observation":
        loinc = tuple(str(c) for c in body["loinc"])
        rows = _numbers(chart, loinc, as_of)
        if any(_within(float(fact.value or 0.0), body) for fact in rows):
            return None
        listed = "/".join(loinc)
        if not rows:
            return f"no result coded LOINC {listed} has ever been recorded"
        return (
            f"the criterion asks for {_bound_text(body)} and the chart's "
            f"{len(rows)} results for LOINC {listed} do not reach it; "
            f"the most recent is {rows[-1].cited}"
        )

    raise BuildError(f"{where}: unknown probe term {name!r}")


def refute(
    cases: list[Case],
    index: dict[str, dict[str, Any]],
    probes: dict[str, dict[str, Any]],
    as_of: date,
) -> list[Flag]:
    """Try to contradict every `met` label in the key against the committed bundles.

    Reads the raw JSON and nothing else. A criterion carrying a `met` label anywhere in the key must
    have an entry in `refutation.json`, even if that entry declares the criterion unrefutable and
    says why, so that a new `met` label cannot arrive without somebody deciding whether it is
    checkable.
    """
    by_quote = {(entry["nct_id"], entry["quote"]): cid for cid, entry in index.items()}
    charts: dict[str, Chart] = {}
    flags: list[Flag] = []

    for case in cases:
        for label in case.criterion_labels:
            if label.expected is not Verdict.MET:
                continue
            criterion_id = by_quote[(case.nct_id, label.quote)]
            if criterion_id not in probes:
                raise BuildError(
                    f"case {case.id}: {criterion_id} carries a met label and "
                    f"refutation.json declares no probe for it"
                )
            probe = probes[criterion_id].get("probe")
            if probe is None:
                continue
            if case.patient_id not in charts:
                charts[case.patient_id] = read_chart(case.patient_id)
            observed = charts[case.patient_id]
            where = f"{case.id} {criterion_id}"
            finding = _check(probe, observed, as_of, where)
            if finding is None:
                continue
            rebuilt = case.perturbations and _check(
                probe, as_built(observed, case), as_of, where
            )
            flags.append(
                Flag(
                    case_id=case.id,
                    criterion_id=criterion_id,
                    provenance=case.provenance,
                    status=SUPPLIED if case.perturbations and rebuilt is None else REFUTED,
                    finding=finding,
                )
            )
    return flags


def audit_flags(
    flags: list[Flag], accepted: list[dict[str, Any]], closes: dict[str, set[str]]
) -> None:
    """Refuse to build while anything the check raised is unaccounted for.

    A `refuted` flag has to be answered in `refutation.json`, by correcting the label or by writing
    down why the check is wrong. A `supplied` flag has to be one the constructed case declared it
    was closing: a `met` label the committed chart does not support and the case does not admit to
    supplying is a label nobody has taken responsibility for.
    """
    waived = {(row["case_id"], row["criterion_id"]): row for row in accepted}
    for row in accepted:
        if not str(row.get("reason", "")).strip():
            raise BuildError(
                f"refutation.json accepts {row['case_id']} {row['criterion_id']} with no reason"
            )

    outstanding = [
        flag
        for flag in flags
        if flag.status == REFUTED and (flag.case_id, flag.criterion_id) not in waived
    ]
    if outstanding:
        lines = "\n".join(
            f"  {flag.case_id} {flag.criterion_id}: {flag.finding}" for flag in outstanding
        )
        raise BuildError(
            "the refutation pass contradicts these met labels and refutation.json does not "
            f"answer for them:\n{lines}"
        )

    raised = {(flag.case_id, flag.criterion_id) for flag in flags if flag.status == REFUTED}
    stale = sorted(set(waived) - raised)
    if stale:
        raise BuildError(
            "refutation.json accepts flags the check no longer raises, so nobody has re-read "
            f"them: {stale}"
        )

    undeclared = [
        flag
        for flag in flags
        if flag.status == SUPPLIED and flag.criterion_id not in closes.get(flag.case_id, set())
    ]
    if undeclared:
        lines = "\n".join(
            f"  {flag.case_id} {flag.criterion_id}: {flag.finding}" for flag in undeclared
        )
        raise BuildError(
            "these met labels rest on a chart edit the constructed case does not declare it "
            f"made:\n{lines}"
        )


def build_constructed_cases(
    spec: list[dict[str, Any]],
    pairs: dict[str, dict[str, str]],
    index: dict[str, dict[str, Any]],
    resolved: dict[str, dict[str, str]],
    charts: dict[str, Chart],
) -> list[Case]:
    """One case per constructed entry, with the chart actually built and read back."""
    cases: list[Case] = []
    for entry in spec:
        case_id, base_id = entry["case_id"], entry["base_case_id"]
        if base_id not in pairs:
            raise BuildError(f"{case_id}: base case {base_id} is not an annotated pair")
        base = pairs[base_id]
        nct_id = base["nct_id"]
        ordered = _expected_criteria(nct_id, index)

        current = PerturbedPatient(patient=load_patient(base["patient_id"]), perturbations=())
        for step in entry["steps"]:
            current = _apply_step(current, step)
        for step in entry["steps"]:
            _check_step(current.patient, step, case_id)

        labels = dict(resolved[base_id])
        for close in entry["closes"]:
            criterion_id = close["criterion_id"]
            if criterion_id not in labels:
                raise BuildError(f"{case_id}: {criterion_id} is not a criterion of {nct_id}")
            if not _is_blocker(index[criterion_id]["kind"], labels[criterion_id]):
                raise BuildError(
                    f"{case_id}: {criterion_id} was already satisfied in {base_id}, so overriding "
                    "it closes nothing"
                )
            if not str(close.get("reason", "")).strip():
                raise BuildError(f"{case_id}: {criterion_id} override carries no reason")
            labels[criterion_id] = close["verdict"]

        derived = derive(ordered, labels, index, charts[base["patient_id"]])
        carried = len(ordered) - len(entry["closes"])
        provenance = (
            f"Constructed from {base_id} by {len(current.perturbations)} recorded edits, "
            "which the case publishes in full."
            if derived.by_vital_status
            else (
                f"Constructed from {base_id} by {len(current.perturbations)} recorded edits; "
                f"{carried} criterion labels are carried forward unchanged from the two annotation "
                f"passes and {len(entry['closes'])} are overridden by those edits."
            )
        )
        cases.append(
            Case(
                id=case_id,
                patient_id=base["patient_id"],
                nct_id=nct_id,
                screening_date=SCREENING_DATE,
                expected=derived.outcome,
                provenance="constructed",
                trap=entry["trap"],
                rationale=f"{entry['note'].strip()} {provenance} {derived.sentence}",
                criterion_labels=derived.labels,
                perturbations=tuple(record.to_dict() for record in current.perturbations),
                annotators=ANNOTATORS,
                adjudicated_by=ADJUDICATOR,
            )
        )
    return cases


@dataclass(frozen=True)
class Derivation:
    """A case's outcome and criterion labels, and the sentence saying how they were reached."""

    outcome: ScreeningOutcome
    labels: tuple[CriterionLabel, ...]
    sentence: str

    @property
    def by_vital_status(self) -> bool:
        return not self.labels


def derive(
    ordered: list[str],
    labels: dict[str, str],
    index: dict[str, dict[str, Any]],
    chart: Chart,
) -> Derivation:
    """The outcome, by the same precedence the system screens with.

    Vital status comes first and is not a criterion. No protocol writes "the patient must be alive",
    so nothing in the criterion decomposition can carry it, and a key that leaves it out labels a
    patient who died four weeks before the screening date as one a coordinator should look at again.
    `caliper.screen` short-circuits on exactly this fact and reports no criterion table; a case
    derived here does the same, and carries no criterion labels, because none was evaluated.

    Everything else is `roll_up` over the adjudicated labels, unchanged.
    """
    if chart.died_before(SCREENING_DATE) or chart.deceased_undated:
        died = (
            f"death on {chart.deceased.isoformat()}"
            if chart.deceased is not None
            else "that the patient has died, without giving a date"
        )
        return Derivation(
            outcome=ScreeningOutcome.INELIGIBLE,
            labels=(),
            sentence=(
                "Derived ineligible by the vital-status rule of protocol.md section 12, which "
                f"precedes every criterion: the committed bundle records {died}, before the "
                f"{SCREENING_DATE.isoformat()} screening date. No criterion was evaluated, so the "
                "case carries no criterion labels, and the criterion-level reading in the note "
                "above describes the chart rather than the outcome."
            ),
        )

    verdicts = [
        CriterionVerdict(
            criterion_id=criterion_id,
            kind=index[criterion_id]["kind"],
            verdict=Verdict(labels[criterion_id]),
        )
        for criterion_id in ordered
    ]
    rollup = roll_up(verdicts)
    return Derivation(
        outcome=rollup.decision,
        labels=tuple(
            CriterionLabel(
                quote=index[criterion_id]["quote"], expected=Verdict(labels[criterion_id])
            )
            for criterion_id in ordered
        ),
        sentence=_derived_sentence(
            rollup.decision,
            rollup.deciding_criterion_ids,
            rollup.unresolved_criterion_ids,
            index,
            len(ordered),
        ),
    )


def _derived_sentence(
    outcome: ScreeningOutcome,
    deciding: list[str],
    unresolved: list[str],
    index: dict[str, dict[str, Any]],
    total: int,
) -> str:
    """The half of the rationale that is computed, naming the criteria that produced the outcome."""
    if outcome is ScreeningOutcome.INELIGIBLE:
        parts = [
            f"{criterion_id} ({index[criterion_id]['kind']} "
            f"{'not met' if index[criterion_id]['kind'] == 'inclusion' else 'met'})"
            for criterion_id in deciding
        ]
        return (
            "Derived ineligible by roll_up on the adjudicated labels; "
            f"decided by {', '.join(parts)}."
        )
    if outcome is ScreeningOutcome.NEEDS_REVIEW:
        named = ", ".join(unresolved[:_MAX_NAMED_UNRESOLVED])
        rest = len(unresolved) - _MAX_NAMED_UNRESOLVED
        tail = f" and {rest} more" if rest > 0 else ""
        return (
            f"Derived needs_review by roll_up on the adjudicated labels; no criterion is "
            f"disqualifying and {len(unresolved)} of {total} are unresolved: {named}{tail}."
        )
    return (
        f"Derived eligible by roll_up on the adjudicated labels; all {total} criteria resolved "
        "and none is disqualifying."
    )


def build_cases(
    pairs: list[dict[str, str]],
    index: dict[str, dict[str, Any]],
    resolved: dict[str, dict[str, str]],
    meta: dict[str, dict[str, str]],
    charts: dict[str, Chart],
) -> list[Case]:
    cases: list[Case] = []
    for pair in pairs:
        case_id, nct_id = pair["case_id"], pair["nct_id"]
        if case_id not in meta:
            raise BuildError(f"cases.json has no trap and note for {case_id}")
        ordered = _expected_criteria(nct_id, index)
        derived = derive(ordered, resolved[case_id], index, charts[pair["patient_id"]])
        cases.append(
            Case(
                id=case_id,
                patient_id=pair["patient_id"],
                nct_id=nct_id,
                screening_date=SCREENING_DATE,
                expected=derived.outcome,
                provenance="annotated",
                trap=meta[case_id]["trap"],
                rationale=f"{meta[case_id]['note'].strip()} {derived.sentence}",
                criterion_labels=derived.labels,
                annotators=ANNOTATORS,
                adjudicated_by=ADJUDICATOR,
            )
        )
    return cases


def cohen_kappa(
    pairs: list[dict[str, str]],
    index: dict[str, dict[str, Any]],
    pass1: dict[str, dict[str, str]],
    pass2: dict[str, dict[str, str]],
) -> tuple[float, float, float, int, dict[tuple[str, str], int]]:
    """Cohen's kappa over the criterion-level labels, with the contingency table it came from."""
    table: dict[tuple[str, str], int] = {(a, b): 0 for a in VERDICTS for b in VERDICTS}
    for pair in pairs:
        case_id = pair["case_id"]
        for criterion_id in _expected_criteria(pair["nct_id"], index):
            table[(pass1[case_id][criterion_id], pass2[case_id][criterion_id])] += 1

    total = sum(table.values())
    if total == 0:
        raise BuildError("no labels to compare")
    observed = sum(table[(v, v)] for v in VERDICTS) / total
    expected = sum(
        (sum(table[(v, b)] for b in VERDICTS) / total)
        * (sum(table[(a, v)] for a in VERDICTS) / total)
        for v in VERDICTS
    )
    kappa = (observed - expected) / (1 - expected) if expected < 1 else 1.0
    return kappa, observed, expected, total, table


def _render(console: Console, cases: list[Case], kappa: float, observed: float, total: int) -> None:
    annotated = [case for case in cases if case.provenance == "annotated"]
    constructed = [case for case in cases if case.provenance == "constructed"]

    outcome_table = Table(title=f"Answer key: {len(cases)} cases by expected outcome")
    outcome_table.add_column("outcome")
    outcome_table.add_column("annotated", justify="right")
    outcome_table.add_column("constructed", justify="right")
    outcome_table.add_column("total", justify="right")
    by_annotated = Counter(case.expected.value for case in annotated)
    by_constructed = Counter(case.expected.value for case in constructed)
    for outcome in ScreeningOutcome:
        a = by_annotated.get(outcome.value, 0)
        c = by_constructed.get(outcome.value, 0)
        outcome_table.add_row(outcome.value, str(a), str(c), str(a + c))
    outcome_table.add_row("[bold]all[/bold]", str(len(annotated)), str(len(constructed)),
                          str(len(cases)))
    console.print(outcome_table)

    trap_table = Table(title="Cases by trap")
    trap_table.add_column("trap")
    trap_table.add_column("annotated", justify="right")
    trap_table.add_column("constructed", justify="right")
    trap_table.add_column("total", justify="right")
    traps_annotated = Counter(case.trap for case in annotated)
    traps_constructed = Counter(case.trap for case in constructed)
    for trap in sorted(set(traps_annotated) | set(traps_constructed)):
        a, c = traps_annotated.get(trap, 0), traps_constructed.get(trap, 0)
        trap_table.add_row(trap, str(a), str(c), str(a + c))
    console.print(trap_table)

    trial_table = Table(title="Cases by trial")
    trial_table.add_column("nct_id")
    trial_table.add_column("cases", justify="right")
    trial_table.add_column("ineligible", justify="right")
    trial_table.add_column("needs_review", justify="right")
    trial_table.add_column("eligible", justify="right")
    trial_table.add_column("of which constructed", justify="right")
    for nct_id in sorted({case.nct_id for case in cases}):
        rows = [case for case in cases if case.nct_id == nct_id]
        counts = Counter(case.expected.value for case in rows)
        trial_table.add_row(
            nct_id,
            str(len(rows)),
            str(counts.get("ineligible", 0)),
            str(counts.get("needs_review", 0)),
            str(counts.get("eligible", 0)),
            str(sum(1 for case in rows if case.provenance == "constructed")),
        )
    console.print(trial_table)

    agreement = Table(title="Inter-annotator agreement, criterion level")
    agreement.add_column("measure")
    agreement.add_column("value", justify="right")
    agreement.add_row("labels compared", str(total))
    agreement.add_row("observed agreement", f"{observed:.4f}")
    agreement.add_row("Cohen's kappa", f"{kappa:.4f}")
    console.print(agreement)


def _render_refutation(console: Console, cases: list[Case], flags: list[Flag]) -> None:
    checked = sum(
        1
        for case in cases
        for label in case.criterion_labels
        if label.expected is Verdict.MET
    )
    dead = [case for case in cases if not case.criterion_labels]

    summary = Table(title="Refutation pass, against the raw committed FHIR")
    summary.add_column("measure")
    summary.add_column("count", justify="right")
    summary.add_row("met labels in the key", str(checked))
    summary.add_row("refuted by the chart", str(sum(1 for f in flags if f.status == REFUTED)))
    supplied = sum(1 for f in flags if f.status == SUPPLIED)
    summary.add_row("supplied by a recorded edit", str(supplied))
    summary.add_row("cases decided by vital status", str(len(dead)))
    console.print(summary)

    if not flags:
        return
    detail = Table(title="Every met label the committed bundle does not carry")
    detail.add_column("case")
    detail.add_column("criterion")
    detail.add_column("provenance")
    detail.add_column("status")
    detail.add_column("what the chart says")
    for flag in flags:
        detail.add_row(
            flag.case_id, flag.criterion_id, flag.provenance, flag.status, flag.finding
        )
    console.print(detail)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="build and validate, but do not write or freeze"
    )
    args = parser.parse_args()
    console = Console()

    criteria = _read("criteria.json")
    index = _criterion_index(criteria)
    pairs = _read("pairs.json")["pairs"]
    raw1, raw2 = _read("pass1.json"), _read("pass2.json")
    pass1, pass2 = _labels_by_case(raw1, "pass1"), _labels_by_case(raw2, "pass2")
    decisions = {
        (row["case_id"], row["criterion_id"]): row
        for row in _read("adjudication.json")["decisions"]
    }
    meta = {row["case_id"]: row for row in _read("cases.json")["cases"]}

    constructed = _read("constructed.json")["cases"]
    refutation = _read("refutation.json")
    charts = {pair["patient_id"]: read_chart(pair["patient_id"]) for pair in pairs}

    resolved, disagreed = adjudicate(pairs, index, pass1, pass2, decisions)
    annotated_cases = build_cases(pairs, index, resolved, meta, charts)
    constructed_cases = build_constructed_cases(
        constructed,
        {pair["case_id"]: pair for pair in pairs},
        index,
        resolved,
        charts,
    )
    cases = [*annotated_cases, *constructed_cases]
    kappa, observed, _expected, total, _table = cohen_kappa(pairs, index, pass1, pass2)

    flags = refute(cases, index, refutation["probes"], SCREENING_DATE)
    audit_flags(
        flags,
        refutation["accepted"]["entries"],
        {
            entry["case_id"]: {close["criterion_id"] for close in entry["closes"]}
            for entry in constructed
        },
    )

    key = AnswerKey(
        version=_read("cases.json")["version"],
        screening_date=SCREENING_DATE,
        cases=tuple(cases),
        notes=_read("cases.json")["key_note"],
    )

    _render(console, cases, kappa, observed, total)
    _render_refutation(console, cases, flags)
    console.print(
        f"{len(disagreed)} of {total} criterion labels differed between the passes "
        f"and were adjudicated by {ADJUDICATOR}."
    )
    edits = sum(len(case.perturbations) for case in constructed_cases)
    bases = {entry["base_case_id"] for entry in constructed}
    console.print(
        f"{len(constructed_cases)} constructed cases were built from {len(bases)} annotated bases "
        f"by {edits} recorded chart edits, each read back off the finished chart."
    )
    deceased = sorted({case.patient_id for case in cases if not case.criterion_labels})
    console.print(
        f"{sum(1 for case in cases if not case.criterion_labels)} cases on {len(deceased)} "
        "patients were decided by vital status before any criterion was evaluated."
    )

    if args.dry_run:
        console.print(f"dry run: fingerprint would be {key_fingerprint(key)}")
        return 0

    digest = freeze(key, KEY_PATH)
    reloaded = load_key(KEY_PATH)
    if not verify_frozen(KEY_PATH):
        raise BuildError(f"{KEY_PATH} does not match its sidecar digest immediately after freezing")
    console.print(f"wrote {KEY_PATH.relative_to(REPO_ROOT)} with {len(reloaded.cases)} cases")
    console.print(f"sha256 {digest}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BuildError as exc:
        print(f"build_answer_key: {exc}", file=sys.stderr)
        sys.exit(1)
