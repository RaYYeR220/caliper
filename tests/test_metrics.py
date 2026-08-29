"""Scoring a run.

The headline number is coverage at zero unsafe errors, which is one point on a risk-coverage curve.
Reporting only that point would be a way of hiding: any system can reach zero unsafe errors by
abstaining on everything. So the curve, the false-abstention rate and the trivial baselines all have
to be in the same table.
"""

import math

from caliper.logic import ScreeningOutcome as Outcome
from caliper.metrics import (
    CaseScore,
    clopper_pearson,
    coverage_at_zero_unsafe,
    empirical_coverage,
    false_abstention_rate,
    risk_coverage_curve,
    selective_risk,
    summarise,
    unsafe_errors,
)


def score(
    expected: Outcome,
    decision: Outcome,
    *,
    forced: Outcome | None = None,
    criteria_coverage: float = 1.0,
    trap: str = "none",
    provenance: str = "constructed",
    case_id: str = "C-001",
) -> CaseScore:
    return CaseScore(
        case_id=case_id,
        expected=expected,
        decision=decision,
        forced_decision=forced if forced is not None else decision,
        criteria_coverage=criteria_coverage,
        trap=trap,
        provenance=provenance,
    )


class TestCoverageAndRisk:
    def test_coverage_counts_the_cases_the_system_actually_decided(self):
        scores = [
            score(Outcome.ELIGIBLE, Outcome.ELIGIBLE),
            score(Outcome.INELIGIBLE, Outcome.NEEDS_REVIEW, case_id="C-002"),
        ]
        assert empirical_coverage(scores) == 0.5

    def test_a_case_the_key_calls_needs_review_counts_as_decided_when_we_agree(self):
        """Abstaining is the right answer sometimes, and it should not be scored as silence."""
        scores = [score(Outcome.NEEDS_REVIEW, Outcome.NEEDS_REVIEW)]
        assert selective_risk(scores) == 0.0

    def test_selective_risk_is_the_error_rate_among_decided_cases(self):
        scores = [
            score(Outcome.ELIGIBLE, Outcome.ELIGIBLE),
            score(Outcome.INELIGIBLE, Outcome.ELIGIBLE, case_id="C-002"),
            score(Outcome.ELIGIBLE, Outcome.NEEDS_REVIEW, case_id="C-003"),
        ]
        assert selective_risk(scores) == 0.5

    def test_risk_is_zero_when_nothing_was_decided(self):
        scores = [score(Outcome.ELIGIBLE, Outcome.NEEDS_REVIEW)]
        assert selective_risk(scores) == 0.0
        assert empirical_coverage(scores) == 0.0


class TestUnsafeErrors:
    def test_calling_an_ineligible_patient_eligible_is_unsafe(self):
        scores = [score(Outcome.INELIGIBLE, Outcome.ELIGIBLE)]
        assert [s.case_id for s in unsafe_errors(scores)] == ["C-001"]

    def test_calling_a_needs_review_patient_eligible_is_also_unsafe(self):
        """The key saying 'a human must look' is not a licence to wave the patient through."""
        scores = [score(Outcome.NEEDS_REVIEW, Outcome.ELIGIBLE)]
        assert len(unsafe_errors(scores)) == 1

    def test_calling_an_eligible_patient_ineligible_is_wrong_but_not_unsafe(self):
        scores = [score(Outcome.ELIGIBLE, Outcome.INELIGIBLE)]
        assert unsafe_errors(scores) == []

    def test_abstaining_is_never_unsafe(self):
        scores = [score(Outcome.ELIGIBLE, Outcome.NEEDS_REVIEW)]
        assert unsafe_errors(scores) == []


class TestFalseAbstention:
    def test_abstaining_on_a_decidable_case_is_counted(self):
        scores = [
            score(Outcome.ELIGIBLE, Outcome.NEEDS_REVIEW),
            score(Outcome.INELIGIBLE, Outcome.INELIGIBLE, case_id="C-002"),
        ]
        assert false_abstention_rate(scores) == 0.5

    def test_abstaining_on_a_case_the_key_calls_undecidable_is_not_a_false_abstention(self):
        scores = [score(Outcome.NEEDS_REVIEW, Outcome.NEEDS_REVIEW)]
        assert false_abstention_rate(scores) == 0.0

    def test_a_system_that_abstains_on_everything_has_a_false_abstention_rate_of_one(self):
        scores = [
            score(Outcome.ELIGIBLE, Outcome.NEEDS_REVIEW),
            score(Outcome.INELIGIBLE, Outcome.NEEDS_REVIEW, case_id="C-002"),
        ]
        assert false_abstention_rate(scores) == 1.0


class TestRiskCoverageCurve:
    def test_the_curve_starts_at_full_coverage_and_ends_at_the_operating_point(self):
        scores = [
            score(Outcome.ELIGIBLE, Outcome.ELIGIBLE, criteria_coverage=1.0),
            score(
                Outcome.INELIGIBLE,
                Outcome.NEEDS_REVIEW,
                forced=Outcome.ELIGIBLE,
                criteria_coverage=0.5,
                case_id="C-002",
            ),
        ]
        curve = risk_coverage_curve(scores)
        assert curve[0].coverage == 1.0
        assert curve[-1].coverage == 0.5

    def test_answering_more_cases_cannot_lower_the_error_count(self):
        scores = [
            score(Outcome.ELIGIBLE, Outcome.ELIGIBLE, criteria_coverage=1.0),
            score(
                Outcome.INELIGIBLE,
                Outcome.NEEDS_REVIEW,
                forced=Outcome.ELIGIBLE,
                criteria_coverage=0.4,
                case_id="C-002",
            ),
        ]
        curve = risk_coverage_curve(scores)
        errors = [point.unsafe for point in curve]
        assert errors == sorted(errors, reverse=True)

    def test_each_point_carries_the_threshold_that_produced_it(self):
        scores = [score(Outcome.ELIGIBLE, Outcome.ELIGIBLE, criteria_coverage=0.75)]
        assert risk_coverage_curve(scores)[0].threshold <= 0.75

    def test_coverage_at_zero_unsafe_is_the_widest_threshold_with_no_unsafe_error(self):
        scores = [
            score(Outcome.ELIGIBLE, Outcome.ELIGIBLE, criteria_coverage=1.0),
            score(
                Outcome.INELIGIBLE,
                Outcome.NEEDS_REVIEW,
                forced=Outcome.ELIGIBLE,
                criteria_coverage=0.5,
                case_id="C-002",
            ),
        ]
        assert coverage_at_zero_unsafe(scores) == 0.5


class TestConfidenceIntervals:
    def test_a_perfect_run_still_has_an_interval(self):
        low, high = clopper_pearson(10, 10)
        assert high == 1.0
        assert low < 1.0

    def test_a_run_of_nothing_spans_the_unit_interval(self):
        assert clopper_pearson(0, 10)[0] == 0.0

    def test_the_interval_narrows_as_the_sample_grows(self):
        narrow = clopper_pearson(50, 100)
        wide = clopper_pearson(5, 10)
        assert (narrow[1] - narrow[0]) < (wide[1] - wide[0])

    def test_it_matches_the_textbook_value(self):
        """Clopper-Pearson for 8 of 10 at 95% is approximately (0.444, 0.975)."""
        low, high = clopper_pearson(8, 10)
        assert math.isclose(low, 0.4439, abs_tol=1e-3)
        assert math.isclose(high, 0.9748, abs_tol=1e-3)

    def test_an_empty_sample_is_the_whole_interval(self):
        assert clopper_pearson(0, 0) == (0.0, 1.0)


class TestSummary:
    def test_it_reports_the_numbers_the_results_table_needs(self):
        scores = [
            score(Outcome.ELIGIBLE, Outcome.ELIGIBLE),
            score(Outcome.INELIGIBLE, Outcome.ELIGIBLE, case_id="C-002"),
            score(Outcome.ELIGIBLE, Outcome.NEEDS_REVIEW, case_id="C-003"),
        ]
        summary = summarise(scores, arm="caliper")
        assert summary.arm == "caliper"
        assert summary.cases == 3
        assert summary.unsafe == 1
        assert summary.coverage == 2 / 3

    def test_it_breaks_results_down_by_trap(self):
        scores = [
            score(Outcome.ELIGIBLE, Outcome.ELIGIBLE, trap="none"),
            score(Outcome.NEEDS_REVIEW, Outcome.ELIGIBLE, trap="missing_data", case_id="C-002"),
        ]
        summary = summarise(scores, arm="caliper")
        assert summary.by_trap["missing_data"].unsafe == 1
        assert summary.by_trap["none"].unsafe == 0

    def test_it_separates_constructed_cases_from_annotated_ones(self):
        scores = [
            score(Outcome.ELIGIBLE, Outcome.ELIGIBLE, provenance="constructed"),
            score(Outcome.ELIGIBLE, Outcome.ELIGIBLE, provenance="annotated", case_id="C-002"),
        ]
        summary = summarise(scores, arm="caliper")
        assert set(summary.by_provenance) == {"constructed", "annotated"}
