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

Usage:
    python scripts/build_answer_key.py            # rebuild, validate, freeze, print the summary
    python scripts/build_answer_key.py --dry-run  # everything except writing the key
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import replace
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


def build_constructed_cases(
    spec: list[dict[str, Any]],
    pairs: dict[str, dict[str, str]],
    index: dict[str, dict[str, Any]],
    resolved: dict[str, dict[str, str]],
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

        verdicts = [
            CriterionVerdict(
                criterion_id=criterion_id,
                kind=index[criterion_id]["kind"],
                verdict=Verdict(labels[criterion_id]),
            )
            for criterion_id in ordered
        ]
        rollup = roll_up(verdicts)
        carried = len(ordered) - len(entry["closes"])
        sentence = _derived_sentence(
            rollup.decision,
            rollup.deciding_criterion_ids,
            rollup.unresolved_criterion_ids,
            index,
            len(ordered),
        )
        provenance = (
            f"Constructed from {base_id} by {len(current.perturbations)} recorded edits; "
            f"{carried} criterion labels are carried forward unchanged from the two annotation "
            f"passes and {len(entry['closes'])} are overridden by those edits."
        )
        cases.append(
            Case(
                id=case_id,
                patient_id=base["patient_id"],
                nct_id=nct_id,
                screening_date=SCREENING_DATE,
                expected=rollup.decision,
                provenance="constructed",
                trap=entry["trap"],
                rationale=f"{entry['note'].strip()} {provenance} {sentence}",
                criterion_labels=tuple(
                    CriterionLabel(
                        quote=index[criterion_id]["quote"],
                        expected=Verdict(labels[criterion_id]),
                    )
                    for criterion_id in ordered
                ),
                perturbations=tuple(record.to_dict() for record in current.perturbations),
                annotators=ANNOTATORS,
                adjudicated_by=ADJUDICATOR,
            )
        )
    return cases


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
) -> list[Case]:
    cases: list[Case] = []
    for pair in pairs:
        case_id, nct_id = pair["case_id"], pair["nct_id"]
        if case_id not in meta:
            raise BuildError(f"cases.json has no trap and note for {case_id}")
        ordered = _expected_criteria(nct_id, index)
        verdicts = [
            CriterionVerdict(
                criterion_id=criterion_id,
                kind=index[criterion_id]["kind"],
                verdict=Verdict(resolved[case_id][criterion_id]),
            )
            for criterion_id in ordered
        ]
        rollup = roll_up(verdicts)
        sentence = _derived_sentence(
            rollup.decision,
            rollup.deciding_criterion_ids,
            rollup.unresolved_criterion_ids,
            index,
            len(ordered),
        )
        cases.append(
            Case(
                id=case_id,
                patient_id=pair["patient_id"],
                nct_id=nct_id,
                screening_date=SCREENING_DATE,
                expected=rollup.decision,
                provenance="annotated",
                trap=meta[case_id]["trap"],
                rationale=f"{meta[case_id]['note'].strip()} {sentence}",
                criterion_labels=tuple(
                    CriterionLabel(
                        quote=index[criterion_id]["quote"],
                        expected=Verdict(resolved[case_id][criterion_id]),
                    )
                    for criterion_id in ordered
                ),
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

    resolved, disagreed = adjudicate(pairs, index, pass1, pass2, decisions)
    annotated_cases = build_cases(pairs, index, resolved, meta)
    constructed_cases = build_constructed_cases(
        _read("constructed.json")["cases"],
        {pair["case_id"]: pair for pair in pairs},
        index,
        resolved,
    )
    cases = [*annotated_cases, *constructed_cases]
    kappa, observed, _expected, total, _table = cohen_kappa(pairs, index, pass1, pass2)

    key = AnswerKey(
        version=_read("cases.json")["version"],
        screening_date=SCREENING_DATE,
        cases=tuple(cases),
        notes=_read("cases.json")["key_note"],
    )

    _render(console, cases, kappa, observed, total)
    console.print(
        f"{len(disagreed)} of {total} criterion labels differed between the passes "
        f"and were adjudicated by {ADJUDICATOR}."
    )
    edits = sum(len(case.perturbations) for case in constructed_cases)
    bases = {entry["base_case_id"] for entry in _read("constructed.json")["cases"]}
    console.print(
        f"{len(constructed_cases)} constructed cases were built from {len(bases)} annotated bases "
        f"by {edits} recorded chart edits, each read back off the finished chart."
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
