"""Running the metamorphic catalogue and reporting it.

Each case is two screenings of the same hand-written criteria: one against the committed chart and
one against the perturbed chart. Everything is deterministic -- the screening date is fixed by
`corpus.default_screening_date`, the patients are files in the repository, and no language model is
reachable from this module or from `cases`.

A failing case has to say what went wrong. `CaseResult.detail` names the criterion, the verdict on
each side and what was required instead, because "case 7 failed" tells a reader nothing they can
act on.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache

from caliper.corpus import default_screening_date, load_patient
from caliper.perturb import PerturbationError
from caliper.record import PatientIndex
from caliper.screen import ScreeningResult, screen

from .cases import CASES, MetamorphicCase


@dataclass(frozen=True)
class CaseResult:
    """One case, run. `before` and `after` are None only when the chart edit could not be made."""

    case_id: str
    passed: bool
    before: ScreeningResult | None
    after: ScreeningResult | None
    detail: str


@lru_cache(maxsize=None)
def _patient(patient_id: str) -> PatientIndex:
    """Load a chart once per process.

    Sharing the index between cases is safe because every function in `caliper.perturb` returns a
    fresh `PatientIndex` and `screen` only reads, so no case can leak an edit into the next one.
    """
    return load_patient(patient_id)


def run_case(case: MetamorphicCase) -> CaseResult:
    """Screen the case's patient twice and check the relation the case asserts."""
    as_of = default_screening_date()
    patient = _patient(case.patient_id)

    try:
        perturbed = case.perturb(patient)
    except PerturbationError as exc:
        # The chart no longer supports the edit this case is built on, so the case is asserting a
        # change that was never made. That is a failure of the case, not a passing run.
        return CaseResult(
            case_id=case.id,
            passed=False,
            before=None,
            after=None,
            detail=f"required: {case.relation.summary}; the perturbation did not apply: {exc}",
        )

    after_criteria = case.criteria if case.criteria_after is None else case.criteria_after
    before = screen(case.criteria, patient, as_of, case.policy)
    after = screen(after_criteria, perturbed.patient, as_of, case.policy)

    observed = case.relation.check(before, after)
    detail = (
        case.relation.summary
        if observed is None
        else f"required: {case.relation.summary}; observed: {observed}"
    )
    return CaseResult(
        case_id=case.id, passed=observed is None, before=before, after=after, detail=detail
    )


def run_all(cases: Sequence[MetamorphicCase] = CASES) -> list[CaseResult]:
    """Run every case in catalogue order."""
    return [run_case(case) for case in cases]


def _row(cells: Sequence[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def to_markdown(
    results: Sequence[CaseResult], cases: Sequence[MetamorphicCase] = CASES
) -> str:
    """A table a judge reads: what each case asserts, against which patient, and whether it held.

    `cases` supplies the plain-English descriptions, which a `CaseResult` deliberately does not
    carry. Any result whose case is not in the catalogue -- a one-off, or a deliberately broken
    case built in a test -- still gets a row, identified by its id.
    """
    catalogue = {case.id: case for case in cases}
    passed = sum(1 for result in results if result.passed)

    lines = [
        f"# Metamorphic suite: {passed}/{len(results)} relations held",
        "",
        _row(("Case", "Asserts", "Patient", "Policy", "Result")),
        _row(("---", "---", "---", "---", "---")),
    ]
    for result in results:
        case = catalogue.get(result.case_id)
        lines.append(
            _row(
                (
                    f"`{result.case_id}`",
                    case.description if case else "(not in the catalogue)",
                    f"`{case.patient_id}`" if case else "-",
                    case.policy.value if case else "-",
                    "pass" if result.passed else "**FAIL**",
                )
            )
        )

    failures = [result for result in results if not result.passed]
    if failures:
        lines += ["", "## Failures", ""]
        for result in failures:
            lines += [f"### `{result.case_id}`", "", result.detail, ""]

    return "\n".join(lines) + "\n"


if __name__ == "__main__":  # pragma: no cover
    print(to_markdown(run_all()), end="")
