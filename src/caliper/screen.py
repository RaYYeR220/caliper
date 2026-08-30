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
    blocked_by: str | None = None
    """A screening-level fact that ended the screening before any criterion was evaluated."""

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
        return len(self.criteria_the_record_should_settle)

    @property
    def to_confirm_at_visit(self) -> tuple[CriterionResult, ...]:
        """Criteria no chart could answer. The coordinator settles them at the visit."""
        return tuple(c for c in self.criteria if c.verdict is Verdict.UNKNOWN and not c.blocking)

    @property
    def criteria_the_record_should_settle(self) -> tuple[CriterionResult, ...]:
        """Everything coverage is measured over: what the record was actually asked to decide."""
        return tuple(c for c in self.criteria if c.blocking)

    @property
    def criteria_resolved(self) -> int:
        settled = self.criteria_the_record_should_settle
        return sum(1 for c in settled if c.verdict is not Verdict.UNKNOWN)

    @property
    def coverage(self) -> float:
        """The share of criteria decided from data.

        Reported per screening rather than averaged away, because a trial where one hard criterion
        always abstains behaves very differently from one where abstention is spread thin. A
        screening stopped by a screening-level fact is complete rather than uncovered: nothing is
        unresolved, because nothing needed resolving.
        """
        if self.blocked_by is not None:
            return 1.0
        if not self.criteria_total:
            return 0.0
        return self.criteria_resolved / self.criteria_total


def _deceased(
    criteria_set: CriteriaSet, patient: PatientIndex, as_of: date, policy: AbsencePolicy
) -> ScreeningResult:
    """Stop before evaluating anything else.

    Continuing would produce a criterion table describing a person who cannot be enrolled, and a
    coordinator skimming forty resolved rows would have to notice the one line that mattered. This
    is a fact about the screening rather than about any criterion, so it is reported as one and not
    smuggled in as a pseudo-criterion the protocol never contained.
    """
    reason = (
        f"the chart records that the patient died on {patient.deceased.isoformat()}, "
        "before the screening date"
        if patient.deceased is not None
        else "the chart records that the patient has died, without giving a date"
    )
    return ScreeningResult(
        nct_id=criteria_set.nct_id,
        patient_id=patient.patient_id,
        screened_on=as_of,
        decision=ScreeningOutcome.INELIGIBLE,
        criteria=(),
        deciding_criterion_ids=(),
        resolution_worklist=(),
        absence_policy=policy,
        blocked_by=reason,
    )


def screen(
    criteria_set: CriteriaSet,
    patient: PatientIndex,
    as_of: date,
    policy: AbsencePolicy = AbsencePolicy.COVERAGE_GATED,
) -> ScreeningResult:
    """Evaluate every criterion in `criteria_set` against `patient` and roll the results up."""
    if patient.died_before(as_of) or patient.deceased_undated:
        return _deceased(criteria_set, patient, as_of, policy)

    results = tuple(
        evaluate_criterion(criterion, patient, as_of, policy) for criterion in criteria_set.criteria
    )
    rollup = roll_up(
        [CriterionVerdict(r.criterion_id, r.kind, r.verdict, r.blocking) for r in results]
    )
    # The worklist is for gaps a query could close. A criterion settled at the visit is on the
    # packet too, but under its own heading, because no query closes it.
    worklist = tuple(
        r.resolution_hint for r in results if r.resolution_hint is not None and r.blocking
    )

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
