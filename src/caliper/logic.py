"""Three-valued screening logic.

Every criterion resolves to MET, NOT_MET or UNKNOWN. The rollup below is the only place in
Caliper where a screening decision is produced, and it is ordinary Python: no model is
consulted here. That is deliberate. UNKNOWN propagates, so ELIGIBLE is unreachable while any
criterion is unresolved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

CriterionKind = str

_KINDS = ("inclusion", "exclusion")


class Verdict(Enum):
    """Where a single criterion landed once its evidence was gathered."""

    MET = "met"
    NOT_MET = "not_met"
    UNKNOWN = "unknown"


class ScreeningOutcome(Enum):
    """What the coordinator is being told about this patient and this trial."""

    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    NEEDS_REVIEW = "needs_review"


@dataclass(frozen=True)
class CriterionVerdict:
    criterion_id: str
    kind: CriterionKind
    verdict: Verdict

    def __post_init__(self) -> None:
        if self.kind not in _KINDS:
            raise ValueError(f"kind must be one of {_KINDS}, got {self.kind!r}")

    @property
    def is_disqualifying(self) -> bool:
        """True when this criterion alone rules the patient out."""
        if self.kind == "inclusion":
            return self.verdict is Verdict.NOT_MET
        return self.verdict is Verdict.MET


@dataclass(frozen=True)
class Rollup:
    decision: ScreeningOutcome
    deciding_criterion_ids: list[str] = field(default_factory=list)
    unresolved_criterion_ids: list[str] = field(default_factory=list)


def roll_up(verdicts: list[CriterionVerdict]) -> Rollup:
    """Combine per-criterion verdicts into one screening decision.

    A definitive failure outranks an unresolved criterion: once an inclusion is provably not met
    or an exclusion is provably triggered, the screening is over. Otherwise anything unresolved
    forces the case to a human.
    """
    failed_inclusions = [
        v.criterion_id for v in verdicts if v.kind == "inclusion" and v.is_disqualifying
    ]
    triggered_exclusions = [
        v.criterion_id for v in verdicts if v.kind == "exclusion" and v.is_disqualifying
    ]
    deciding = failed_inclusions + triggered_exclusions
    if deciding:
        return Rollup(decision=ScreeningOutcome.INELIGIBLE, deciding_criterion_ids=deciding)

    unresolved = [v.criterion_id for v in verdicts if v.verdict is Verdict.UNKNOWN]
    if unresolved or not verdicts:
        return Rollup(
            decision=ScreeningOutcome.NEEDS_REVIEW, unresolved_criterion_ids=unresolved
        )

    return Rollup(decision=ScreeningOutcome.ELIGIBLE)
