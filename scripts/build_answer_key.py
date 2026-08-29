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
from caliper.logic import CriterionVerdict, ScreeningOutcome, Verdict, roll_up

ANNOTATION_DIR = REPO_ROOT / "eval" / "annotation"
KEY_PATH = REPO_ROOT / "eval" / "answer_key.json"

SCREENING_DATE = date(2026, 6, 1)

# Both passes are language models, and `adjudicated_by` is a person. The key says so in the
# annotator names themselves so that no reader can mistake either pass for a clinician.
ANNOTATORS = ("llm-pass-1", "llm-pass-2")
ADJUDICATOR = "maintainer"

VERDICTS = ("met", "not_met", "unknown")

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
    by_outcome = Counter(case.expected.value for case in cases)
    outcome_table = Table(title=f"Answer key: {len(cases)} cases by expected outcome")
    outcome_table.add_column("outcome")
    outcome_table.add_column("cases", justify="right")
    for outcome in ScreeningOutcome:
        outcome_table.add_row(outcome.value, str(by_outcome.get(outcome.value, 0)))
    console.print(outcome_table)

    trap_table = Table(title="Cases by trap")
    trap_table.add_column("trap")
    trap_table.add_column("cases", justify="right")
    for trap, count in sorted(Counter(case.trap for case in cases).items()):
        trap_table.add_row(trap, str(count))
    console.print(trap_table)

    trial_table = Table(title="Cases by trial")
    trial_table.add_column("nct_id")
    trial_table.add_column("cases", justify="right")
    trial_table.add_column("ineligible", justify="right")
    trial_table.add_column("needs_review", justify="right")
    trial_table.add_column("eligible", justify="right")
    for nct_id in sorted({case.nct_id for case in cases}):
        rows = [case for case in cases if case.nct_id == nct_id]
        counts = Counter(case.expected.value for case in rows)
        trial_table.add_row(
            nct_id,
            str(len(rows)),
            str(counts.get("ineligible", 0)),
            str(counts.get("needs_review", 0)),
            str(counts.get("eligible", 0)),
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
    cases = build_cases(pairs, index, resolved, meta)
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
