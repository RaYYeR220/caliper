"""Screening one patient against one trial.

This is the seam where per-criterion verdicts become a decision a coordinator acts on. It stays
deterministic: `screen` calls the evaluator once per criterion and rolls the results up. What comes
back is not a recommendation but a worked record — every criterion, the evidence behind it, and,
for anything unresolved, the specific thing a human would have to find.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from caliper.evaluate import AbsencePolicy, CriterionResult, ResolutionHint, evaluate_criterion
from caliper.ir import CriteriaSet
from caliper.logic import CriterionVerdict, ScreeningOutcome, Verdict, roll_up
from caliper.record import PatientIndex


@dataclass(frozen=True)
class ScreeningResult:
    nct_id: str
    patient_id: str
    screened_on: date
    decision: ScreeningOutcome
    criteria: tuple[CriterionResult, ...]
    deciding_criterion_ids: tuple[str, ...]
    resolution_worklist: tuple[ResolutionHint, ...]
    absence_policy: AbsencePolicy

    @property
    def approximations(self) -> tuple[str, ...]:
        """Every place this screening rests on something evaluated inexactly.

        Surfaced at the screening level because a coordinator reading a packet needs to know that a
        verdict leaned on an approximation, not have it buried in one row of a forty-row table.
        """
        seen: list[str] = []
        for criterion in self.criteria:
            for caveat in criterion.approximations:
                if caveat not in seen:
                    seen.append(caveat)
        return tuple(seen)

    @property
    def criteria_total(self) -> int:
        return len(self.criteria)

    @property
    def criteria_resolved(self) -> int:
        return sum(1 for c in self.criteria if c.verdict is not Verdict.UNKNOWN)

    @property
    def coverage(self) -> float:
        """The share of criteria decided from data.

        Reported per screening rather than averaged away, because a trial where one hard criterion
        always abstains behaves very differently from one where abstention is spread thin.
        """
        if not self.criteria:
            return 0.0
        return self.criteria_resolved / self.criteria_total


VITAL_STATUS = "VITAL-STATUS"


def _deceased(
    criteria_set: CriteriaSet, patient: PatientIndex, as_of: date, policy: AbsencePolicy
) -> ScreeningResult:
    """Stop before evaluating anything else.

    Continuing would produce a criterion table describing a person who cannot be enrolled, and a
    coordinator skimming forty green rows would have to notice the one line that mattered. It is a
    screening decision, not a criterion, so it is reported as one.
    """
    assert patient.deceased is not None
    row = CriterionResult(
        criterion_id=VITAL_STATUS,
        kind="inclusion",
        verdict=Verdict.NOT_MET,
        rationale=f"the chart records that the patient died on {patient.deceased.isoformat()}",
    )
    return ScreeningResult(
        nct_id=criteria_set.nct_id,
        patient_id=patient.patient_id,
        screened_on=as_of,
        decision=ScreeningOutcome.INELIGIBLE,
        criteria=(row,),
        deciding_criterion_ids=(VITAL_STATUS,),
        resolution_worklist=(),
        absence_policy=policy,
    )


def screen(
    criteria_set: CriteriaSet,
    patient: PatientIndex,
    as_of: date,
    policy: AbsencePolicy = AbsencePolicy.COVERAGE_GATED,
) -> ScreeningResult:
    """Evaluate every criterion in `criteria_set` against `patient` and roll the results up."""
    if patient.died_before(as_of):
        return _deceased(criteria_set, patient, as_of, policy)

    results = tuple(
        evaluate_criterion(criterion, patient, as_of, policy) for criterion in criteria_set.criteria
    )
    rollup = roll_up(
        [CriterionVerdict(r.criterion_id, r.kind, r.verdict) for r in results]
    )
    worklist = tuple(r.resolution_hint for r in results if r.resolution_hint is not None)

    return ScreeningResult(
        nct_id=criteria_set.nct_id,
        patient_id=patient.patient_id,
        screened_on=as_of,
        decision=rollup.decision,
        criteria=results,
        deciding_criterion_ids=tuple(rollup.deciding_criterion_ids),
        resolution_worklist=worklist,
        absence_policy=policy,
    )
