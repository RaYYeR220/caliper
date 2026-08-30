"""Scoring a run of screenings against the answer key.

The vocabulary is selective prediction's. A system that may abstain is described by two numbers
rather than one: how often it answers (*coverage*) and how often it is wrong when it does
(*selective risk*). Sweeping the threshold that governs abstention traces a **risk-coverage curve**
(El-Yaniv and Wiener, JMLR 2010; the trade goes back to Chow 1970), and the curve is reported in
full because it is the honest shape of that trade.

The headline is not a point on the curve, though, and `coverage_at_zero_unsafe` says why: the curve
is drawn over `forced_decision`, the answer the system would have given had abstention been
unavailable to it, and a headline is about what the system actually did. Reporting either number
alone would also be dishonest, because abstaining on everything reaches zero unsafe errors
trivially. So `summarise` carries the false-abstention rate, which is what abstaining on everything
is bad at, and the results table always shows the trivial baselines alongside.

An **unsafe** error has a specific meaning here: the system sent a patient forward as eligible when
the key says they were not, or says a human had to look first. The reverse mistake — screening out
a patient who could have enrolled — is a real cost too, but it is a cost to the trial rather than to
the patient, and nobody ever finds out about it, so the two are counted separately rather than
averaged together.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from caliper.logic import ScreeningOutcome

DECIDED = (ScreeningOutcome.ELIGIBLE, ScreeningOutcome.INELIGIBLE)


@dataclass(frozen=True)
class CaseScore:
    """One case, as the key sees it and as the system answered it."""

    case_id: str
    expected: ScreeningOutcome
    decision: ScreeningOutcome
    forced_decision: ScreeningOutcome
    """What the system would have said had it not been allowed to abstain. Drives the curve."""

    criteria_coverage: float
    """The share of this trial's criteria that resolved from data. The abstention score."""

    trap: str = "none"
    provenance: str = "constructed"

    @property
    def answered(self) -> bool:
        """Whether the system committed to something a coordinator can act on without a chart."""
        return self.decision is not ScreeningOutcome.NEEDS_REVIEW or (
            self.expected is ScreeningOutcome.NEEDS_REVIEW
        )

    @property
    def correct(self) -> bool:
        return self.decision is self.expected


def _is_unsafe(expected: ScreeningOutcome, decision: ScreeningOutcome) -> bool:
    return decision is ScreeningOutcome.ELIGIBLE and expected is not ScreeningOutcome.ELIGIBLE


def unsafe_errors(scores: list[CaseScore]) -> list[CaseScore]:
    """Cases sent forward as eligible that should not have been."""
    return [s for s in scores if _is_unsafe(s.expected, s.decision)]


def empirical_coverage(scores: list[CaseScore]) -> float:
    if not scores:
        return 0.0
    return sum(1 for s in scores if s.answered) / len(scores)


def selective_risk(scores: list[CaseScore]) -> float:
    """The error rate among the cases the system was willing to answer."""
    answered = [s for s in scores if s.answered]
    if not answered:
        return 0.0
    return sum(1 for s in answered if not s.correct) / len(answered)


def false_abstention_rate(scores: list[CaseScore]) -> float:
    """How often the system sent a decidable case to a human anyway.

    This is the number that stops "abstain on everything" from looking good.
    """
    decidable = [s for s in scores if s.expected in DECIDED]
    if not decidable:
        return 0.0
    abstained = sum(1 for s in decidable if s.decision is ScreeningOutcome.NEEDS_REVIEW)
    return abstained / len(decidable)


@dataclass(frozen=True)
class CurvePoint:
    threshold: float
    coverage: float
    risk: float
    unsafe: int
    answered: int


def risk_coverage_curve(scores: list[CaseScore]) -> list[CurvePoint]:
    """Sweep the abstention threshold and record what each setting buys.

    The threshold is the share of a trial's criteria that must resolve from data before the system
    is willing to commit. At a threshold of zero it answers everything using `forced_decision`,
    which is what a system with no notion of abstention would do; at one it answers only fully
    resolved cases.

    Every point is counterfactual, including the last one: `forced_decision` is what the system
    *would* have said, and on cases it really abstained on it never said that. The curve is the
    right instrument for the trade between answering and being wrong, and the wrong instrument for
    reporting what happened — see `coverage_at_zero_unsafe`.
    """
    if not scores:
        return []

    thresholds = sorted({round(s.criteria_coverage, 6) for s in scores} | {0.0})
    points = []
    for threshold in thresholds:
        answered = [s for s in scores if s.criteria_coverage >= threshold]
        if not answered:
            continue
        wrong = sum(1 for s in answered if s.forced_decision is not s.expected)
        unsafe = sum(1 for s in answered if _is_unsafe(s.expected, s.forced_decision))
        points.append(
            CurvePoint(
                threshold=threshold,
                coverage=len(answered) / len(scores),
                risk=wrong / len(answered),
                unsafe=unsafe,
                answered=len(answered),
            )
        )
    return points


def coverage_at_zero_unsafe(scores: list[CaseScore]) -> float:
    """The share of cases the system decided itself, or zero if it committed an unsafe error.

    Defined over `decision` — what the system actually did — rather than over `forced_decision`,
    which is the hypothetical the curve sweeps. The curve reading was tried first and cannot carry a
    headline. It measures a threshold the system does not run at, and it is won outright by a system
    that answers nothing: every case sits on the curve at full width, no answer is ever given, and
    so no answer is ever unsafe. That is how `always_needs_review` scored 100% here while Caliper,
    which really did decide 86% of its cases without committing a single unsafe error, scored zero.

    Retiring the number in favour of printing coverage and unsafe errors side by side was the other
    option, and the report does print both. But one arm has to be comparable against another in a
    single column, so the two are combined the way a reader would combine them: lexicographically.
    Safety is a precondition rather than a term to trade against, so an arm that waved one
    ineligible patient through scores nothing however much it covered; an arm that met the
    precondition scores exactly the work it took off a human's desk. That share is realised rather
    than hypothetical, so abstaining lowers it, and no amount of abstention can win this column.
    """
    if unsafe_errors(scores):
        return 0.0
    return empirical_coverage(scores)


def _binomial_cdf(k: int, n: int, p: float) -> float:
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k + 1))


def _bisect(predicate, low: float, high: float, iterations: int = 80) -> float:
    for _ in range(iterations):
        middle = (low + high) / 2
        if predicate(middle):
            low = middle
        else:
            high = middle
    return (low + high) / 2


def clopper_pearson(successes: int, trials: int, alpha: float = 0.05) -> tuple[float, float]:
    """An exact binomial confidence interval.

    Bisection on the binomial CDF rather than an incomplete beta from a numerical library: the
    samples here are small enough that the exact sum is instant, and it keeps the dependency list
    honest. The interval is what stops fifty cases from being reported as if they were five hundred.
    """
    if trials == 0:
        return (0.0, 1.0)
    if successes < 0 or successes > trials:
        raise ValueError("successes must lie between 0 and trials")

    lower = 0.0
    if successes > 0:
        lower = _bisect(lambda p: 1 - _binomial_cdf(successes - 1, trials, p) < alpha / 2, 0.0, 1.0)

    upper = 1.0
    if successes < trials:
        upper = _bisect(lambda p: _binomial_cdf(successes, trials, p) > alpha / 2, 0.0, 1.0)

    return (lower, upper)


@dataclass(frozen=True)
class Slice:
    cases: int
    correct: int
    unsafe: int
    abstained: int

    @property
    def accuracy(self) -> float:
        return self.correct / self.cases if self.cases else 0.0


@dataclass(frozen=True)
class Summary:
    arm: str
    cases: int
    correct: int
    unsafe: int
    coverage: float
    selective_risk: float
    false_abstention: float
    coverage_at_zero_unsafe: float
    accuracy_ci: tuple[float, float]
    by_trap: dict[str, Slice] = field(default_factory=dict)
    by_provenance: dict[str, Slice] = field(default_factory=dict)
    curve: list[CurvePoint] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return self.correct / self.cases if self.cases else 0.0


def _slice(scores: list[CaseScore]) -> Slice:
    return Slice(
        cases=len(scores),
        correct=sum(1 for s in scores if s.correct),
        unsafe=len(unsafe_errors(scores)),
        abstained=sum(1 for s in scores if s.decision is ScreeningOutcome.NEEDS_REVIEW),
    )


def _grouped(scores: list[CaseScore], key) -> dict[str, Slice]:
    groups: dict[str, list[CaseScore]] = {}
    for score in scores:
        groups.setdefault(key(score), []).append(score)
    return {name: _slice(members) for name, members in sorted(groups.items())}


def summarise(scores: list[CaseScore], *, arm: str) -> Summary:
    """Everything the results table needs for one arm of the evaluation."""
    correct = sum(1 for s in scores if s.correct)
    return Summary(
        arm=arm,
        cases=len(scores),
        correct=correct,
        unsafe=len(unsafe_errors(scores)),
        coverage=empirical_coverage(scores),
        selective_risk=selective_risk(scores),
        false_abstention=false_abstention_rate(scores),
        coverage_at_zero_unsafe=coverage_at_zero_unsafe(scores),
        accuracy_ci=clopper_pearson(correct, len(scores)),
        by_trap=_grouped(scores, lambda s: s.trap),
        by_provenance=_grouped(scores, lambda s: s.provenance),
        curve=risk_coverage_curve(scores),
    )
