"""Running one arm of the evaluation over the answer key.

An arm is a system under test: Caliper in some configuration, or a baseline. The runner's whole job
is to make every arm answer exactly the same questions from exactly the same data, then write down
what happened in enough detail that someone else can recompute the numbers.

Two details are load-bearing. A trial is compiled once and reused across every patient screened
against it, because compilation is where the money goes and paying for it per patient would make
the cost comparison meaningless. And a case that *failed* — a patient that would not load, a model
call that never produced valid output — is recorded as a failure rather than being quietly scored
as an abstention, which would flatter exactly the metric this system is judged on.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from caliper.answerkey import AnswerKey, Case
from caliper.baselines import Baseline
from caliper.blockers import Blocker, blocking_criteria
from caliper.ir import CriteriaSet
from caliper.logic import ScreeningOutcome, Verdict
from caliper.metrics import CaseScore, Summary, by_expected, summarise
from caliper.pipeline import PipelineConfig
from caliper.record import PatientIndex
from caliper.screen import ScreeningResult, screen


def forced_outcome(result: ScreeningResult) -> ScreeningOutcome:
    """What the screening would have said if abstention were not available to it.

    Unresolved criteria are read the way a system with no notion of abstention reads them: an
    unknown inclusion is assumed met, an unknown exclusion assumed untriggered. That is the
    optimistic reading, and it is the right one for this purpose — it is what a system that always
    answers would produce, so sweeping it against the abstention threshold traces the cost of
    answering rather than the cost of some other guess.
    """
    for criterion in result.criteria:
        if criterion.verdict is Verdict.UNKNOWN:
            continue
        if criterion.kind == "inclusion" and criterion.verdict is Verdict.NOT_MET:
            return ScreeningOutcome.INELIGIBLE
        if criterion.kind == "exclusion" and criterion.verdict is Verdict.MET:
            return ScreeningOutcome.INELIGIBLE
    return ScreeningOutcome.ELIGIBLE


def score_screening(case: Case, result: ScreeningResult) -> CaseScore:
    return CaseScore(
        case_id=case.id,
        expected=case.expected,
        decision=result.decision,
        forced_decision=forced_outcome(result),
        criteria_coverage=result.coverage,
        trap=case.trap,
        provenance=case.provenance,
    )


def score_baseline(case: Case, outcome: ScreeningOutcome) -> CaseScore:
    """A baseline answers every case, so its curve is a single point at full coverage."""
    return CaseScore(
        case_id=case.id,
        expected=case.expected,
        decision=outcome,
        forced_decision=outcome,
        criteria_coverage=1.0,
        trap=case.trap,
        provenance=case.provenance,
    )


@dataclass(frozen=True)
class CaseFailure:
    case_id: str
    stage: str
    error: str


@dataclass(frozen=True)
class Arm:
    """One system under test.

    `compile_trial` and `run_baseline` are injected rather than imported so the runner can be
    exercised without a provider, and so an arm can be swapped for a recorded one.
    """

    name: str
    config: PipelineConfig | None = None
    compile_trial: Callable[[str], CriteriaSet] | None = None
    run_baseline: Baseline | None = None

    @property
    def is_baseline(self) -> bool:
        return self.run_baseline is not None


@dataclass(frozen=True)
class ArmReport:
    arm: str
    scores: list[CaseScore]
    summary: Summary
    failures: list[CaseFailure] = field(default_factory=list)
    wall_seconds: float = 0.0
    cost_usd: float | None = None
    blockers: list[Blocker] = field(default_factory=list)
    """The criteria that left screenings undecided, most frequent first.

    Empty for a baseline arm, which produces an answer rather than a set of criterion verdicts and
    so has nothing to report about what held it up.
    """

    screenings: int = 0
    """How many screenings the blocker counts are out of, so a share can be worked out from them."""


    def to_dict(self) -> dict[str, object]:
        return {
            "arm": self.arm,
            "wall_seconds": round(self.wall_seconds, 3),
            "cost_usd": self.cost_usd,
            "cases": self.summary.cases,
            "correct": self.summary.correct,
            "unsafe": self.summary.unsafe,
            "coverage": self.summary.coverage,
            "selective_risk": self.summary.selective_risk,
            "false_abstention": self.summary.false_abstention,
            "coverage_at_zero_unsafe": self.summary.coverage_at_zero_unsafe,
            "balanced_accuracy": self.summary.balanced_accuracy,
            "accuracy_ci": list(self.summary.accuracy_ci),
            # Kept as the report reads it: how many of the cases the key expected this answer for
            # were got right. A single accuracy figure on this key is close to a measurement of its
            # base rate, so the breakdown is the part worth persisting.
            "by_expected": {
                expected: {
                    "cases": group.cases,
                    "correct": group.correct,
                    "unsafe": group.unsafe,
                    "abstained": group.abstained,
                }
                for expected, group in by_expected(self.scores).items()
            },
            "screenings": self.screenings,
            "blockers": [
                {
                    "nct_id": b.nct_id,
                    "criterion_id": b.criterion_id,
                    "screenings": b.screenings,
                    "reason": b.reason,
                    "missing": b.missing,
                    "quote": b.quote,
                }
                for b in self.blockers
            ],
            "scores": [
                {
                    "case_id": s.case_id,
                    "expected": s.expected.value,
                    "decision": s.decision.value,
                    "forced_decision": s.forced_decision.value,
                    "criteria_coverage": s.criteria_coverage,
                    "trap": s.trap,
                    "provenance": s.provenance,
                }
                for s in self.scores
            ],
            "failures": [
                {"case_id": f.case_id, "stage": f.stage, "error": f.error} for f in self.failures
            ],
            "curve": [
                {
                    "threshold": p.threshold,
                    "coverage": p.coverage,
                    "risk": p.risk,
                    "unsafe": p.unsafe,
                    "answered": p.answered,
                }
                for p in self.summary.curve
            ],
        }

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")


def run_arm(
    key: AnswerKey,
    arm: Arm,
    *,
    load_patient: Callable[[Case], PatientIndex],
    load_criteria_text: Callable[[str], str] | None = None,
    cost_usd: float | None = None,
) -> ArmReport:
    """Answer every case in `key` with one arm."""
    started = time.perf_counter()
    scores: list[CaseScore] = []
    failures: list[CaseFailure] = []
    compiled: dict[str, CriteriaSet] = {}
    screenings: list[ScreeningResult] = []

    for case in key.cases:
        try:
            # The whole case, not just the identifier: a constructed case is scored against the
            # chart its perturbations describe, and loading the base chart instead would answer a
            # question nobody asked, silently and plausibly.
            patient = load_patient(case)
        except Exception as error:  # a chart that will not load is a failure, not an abstention
            failures.append(CaseFailure(case.id, "load_patient", str(error)))
            continue

        try:
            if arm.is_baseline:
                assert arm.run_baseline is not None and load_criteria_text is not None
                decision = arm.run_baseline.decide(
                    load_criteria_text(case.nct_id), patient, case.screening_date
                )
                if decision.failed or decision.outcome is None:
                    failures.append(CaseFailure(case.id, "baseline", decision.rationale))
                    continue
                scores.append(score_baseline(case, decision.outcome))
                continue

            assert arm.compile_trial is not None and arm.config is not None
            if case.nct_id not in compiled:
                compiled[case.nct_id] = arm.compile_trial(case.nct_id)
            result = screen(
                compiled[case.nct_id],
                patient,
                case.screening_date,
                policy=arm.config.absence_policy,
            )
            screenings.append(result)
            scores.append(score_screening(case, result))
        except Exception as error:
            failures.append(CaseFailure(case.id, "screen", str(error)))

    return ArmReport(
        arm=arm.name,
        scores=scores,
        summary=summarise(scores, arm=arm.name),
        failures=failures,
        wall_seconds=time.perf_counter() - started,
        cost_usd=cost_usd,
        blockers=blocking_criteria(screenings, criteria_sets=list(compiled.values())),
        screenings=len(screenings),
    )
