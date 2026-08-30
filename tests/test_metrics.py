"""Scoring a run.

The headline number is the operating point: the share of cases the system decided by itself, and
nothing at all if it committed an unsafe error along the way. Any system can reach zero unsafe
errors by abstaining on everything, so the tests below pin the property that makes the number worth
printing — abstention lowers it, and cannot win it. The risk-coverage curve, the false-abstention
rate and the trivial baselines all stay in the same table for the same reason.
"""

import math

import pytest

from caliper.logic import ScreeningOutcome as Outcome
from caliper.metrics import (
    CaseScore,
    balanced_accuracy,
    by_expected,
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


class TestTheOperatingPoint:
    """`coverage_at_zero_unsafe` has to describe what the system did, not what it might have done.

    The bug these pin: the number used to be read off the risk-coverage curve, which is drawn over
    `forced_decision`. A system that abstains on everything then scored a perfect 100% — it never
    answers, so it is never unsafe — while a system that really decided most of its cases with a
    clean safety record scored zero, because every curve point carried the errors it would have
    made had it answered.
    """

    def test_it_is_the_share_of_cases_the_system_really_decided(self):
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

    def test_a_case_it_abstained_on_is_not_scored_against_it_as_an_unsafe_error(self):
        """The whole point of abstaining: the answer it did not give cannot be held against it."""
        scores = [
            score(Outcome.ELIGIBLE, Outcome.ELIGIBLE, criteria_coverage=1.0),
            score(
                Outcome.INELIGIBLE,
                Outcome.NEEDS_REVIEW,
                forced=Outcome.ELIGIBLE,
                criteria_coverage=0.0,
                case_id="C-002",
            ),
        ]
        assert unsafe_errors(scores) == []
        assert coverage_at_zero_unsafe(scores) == 0.5

    def test_one_unsafe_error_costs_the_whole_number(self):
        """Safety is a precondition, not a term traded against coverage."""
        scores = [
            score(Outcome.ELIGIBLE, Outcome.ELIGIBLE, case_id=f"C-{i:03d}") for i in range(9)
        ]
        scores.append(score(Outcome.INELIGIBLE, Outcome.ELIGIBLE, case_id="C-009"))
        assert empirical_coverage(scores) == 1.0
        assert coverage_at_zero_unsafe(scores) == 0.0

    def test_abstaining_on_everything_cannot_outrank_a_system_that_answers_safely(self):
        """`always_needs_review` answers nothing. It must not come first on the headline number.

        Both arms score zero unsafe errors, so the safety precondition alone cannot separate them.
        What separates them is coverage of the decisions actually made — which is the work a
        coordinator no longer has to do, and which abstaining on everything does not do at all.
        """
        cases = [
            (Outcome.ELIGIBLE, "C-001"),
            (Outcome.INELIGIBLE, "C-002"),
            (Outcome.ELIGIBLE, "C-003"),
            (Outcome.INELIGIBLE, "C-004"),
            (Outcome.NEEDS_REVIEW, "C-005"),
        ]
        answers_safely = [
            score(expected, expected, case_id=case_id) for expected, case_id in cases
        ]
        abstains_on_everything = [
            score(
                expected,
                Outcome.NEEDS_REVIEW,
                # The curve reading gave this arm full width at every threshold, which is what let
                # it win. Full criteria coverage here keeps that escape route open under the test.
                forced=Outcome.ELIGIBLE,
                criteria_coverage=1.0,
                case_id=case_id,
            )
            for expected, case_id in cases
        ]

        good = summarise(answers_safely, arm="caliper")
        trivial = summarise(abstains_on_everything, arm="always_needs_review")

        assert good.unsafe == 0 and trivial.unsafe == 0
        assert trivial.coverage_at_zero_unsafe < good.coverage_at_zero_unsafe
        assert trivial.false_abstention == 1.0

    def test_a_system_that_answers_everything_unsafely_scores_nothing(self):
        scores = [
            score(Outcome.INELIGIBLE, Outcome.ELIGIBLE, case_id="C-001"),
            score(Outcome.NEEDS_REVIEW, Outcome.ELIGIBLE, case_id="C-002"),
        ]
        assert coverage_at_zero_unsafe(scores) == 0.0


def a_lopsided_key(ineligible: int = 41, eligible: int = 6, review: int = 4) -> list[Outcome]:
    """The shape of the real answer key: most patients do not qualify for most trials."""
    return (
        [Outcome.INELIGIBLE] * ineligible
        + [Outcome.ELIGIBLE] * eligible
        + [Outcome.NEEDS_REVIEW] * review
    )


def always(answer: Outcome, expected: list[Outcome]) -> list[CaseScore]:
    return [
        score(want, answer, case_id=f"C-{i:03d}") for i, want in enumerate(expected, start=1)
    ]


class TestByExpected:
    def test_every_case_lands_in_exactly_one_group(self):
        scores = always(Outcome.INELIGIBLE, a_lopsided_key())
        slices = by_expected(scores)
        assert sum(s.cases for s in slices.values()) == len(scores)

    def test_the_groups_are_the_outcomes_the_key_uses(self):
        slices = by_expected(always(Outcome.INELIGIBLE, a_lopsided_key()))
        assert set(slices) == {"eligible", "ineligible", "needs_review"}
        assert slices["ineligible"].correct == 41
        assert slices["eligible"].correct == 0

    def test_an_outcome_the_key_never_asks_about_is_absent_rather_than_empty(self):
        slices = by_expected(always(Outcome.ELIGIBLE, [Outcome.ELIGIBLE, Outcome.INELIGIBLE]))
        assert "needs_review" not in slices

    def test_the_summary_carries_it(self):
        summary = summarise(always(Outcome.INELIGIBLE, a_lopsided_key()), arm="always_ineligible")
        assert sum(s.cases for s in summary.by_expected.values()) == summary.cases


class TestBalancedAccuracy:
    """Plain accuracy on a lopsided key is close to a measurement of the key's base rate.

    The corrected answer key expects `ineligible` for 41 of 51 cases, so an arm that answers
    `ineligible` and reads nothing scores 80% — better than any real arm. These pin the number that
    survives that: per-expected-outcome accuracy, averaged without weighting.
    """

    def test_answering_only_the_commonest_outcome_scores_the_base_rate_on_accuracy(self):
        summary = summarise(always(Outcome.INELIGIBLE, a_lopsided_key()), arm="always_ineligible")
        assert round(summary.accuracy, 3) == round(41 / 51, 3)

    def test_and_scores_one_over_k_on_the_balanced_figure(self):
        scores = always(Outcome.INELIGIBLE, a_lopsided_key())
        assert math.isclose(balanced_accuracy(scores), 1 / 3)

    @pytest.mark.parametrize(
        "answer", [Outcome.ELIGIBLE, Outcome.INELIGIBLE, Outcome.NEEDS_REVIEW]
    )
    def test_no_single_answer_can_beat_one_over_k_whatever_it_is(self, answer):
        """The bound is the whole reason this number is worth printing beside accuracy."""
        expected = a_lopsided_key()
        outcomes = len(set(expected))
        assert balanced_accuracy(always(answer, expected)) <= 1 / outcomes + 1e-9

    def test_a_system_that_is_right_about_everything_still_scores_one(self):
        expected = a_lopsided_key()
        scores = [score(want, want, case_id=f"C-{i:03d}") for i, want in enumerate(expected, 1)]
        assert balanced_accuracy(scores) == 1.0

    def test_it_averages_over_the_outcomes_the_key_uses_rather_than_every_outcome_there_is(self):
        """A key that never asks a question must not put a ceiling below 1.0 on a perfect system."""
        expected = [Outcome.ELIGIBLE, Outcome.INELIGIBLE]
        scores = [score(want, want, case_id=f"C-{i:03d}") for i, want in enumerate(expected, 1)]
        assert balanced_accuracy(scores) == 1.0

    def test_an_empty_run_is_zero_rather_than_an_error(self):
        assert balanced_accuracy([]) == 0.0


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


class TestCoverageCountsCommitments:
    """Coverage is the share of cases the system did not abstain on. Nothing else belongs in it.

    The first definition also counted an abstention the key agreed with — "correct to send this to a
    human" read as "answered". That inflated the headline by eight points and, worse, gave
    `always_needs_review` a coverage of 8% while it decided literally nothing, which is the exact
    reading the arm exists to make impossible. Coverage in the selective-prediction sense (El-Yaniv
    and Wiener) is one minus the abstention rate, and a coordinator still has to open the chart on
    every case the system declined, whether or not declining was right.
    """

    def a_score(self, expected: Outcome, decision: Outcome) -> CaseScore:
        return CaseScore(
            case_id="c",
            expected=expected,
            decision=decision,
            forced_decision=Outcome.ELIGIBLE,
            criteria_coverage=1.0,
        )

    def test_an_abstention_the_key_agrees_with_is_still_an_abstention(self):
        score = self.a_score(Outcome.NEEDS_REVIEW, Outcome.NEEDS_REVIEW)

        assert score.answered is False
        assert empirical_coverage([score]) == 0.0

    def test_a_verdict_is_answered_whether_or_not_it_is_right(self):
        wrong = self.a_score(Outcome.ELIGIBLE, Outcome.INELIGIBLE)

        assert wrong.answered is True
        assert empirical_coverage([wrong]) == 1.0

    def test_an_arm_that_abstains_on_everything_covers_nothing(self):
        scores = [
            self.a_score(Outcome.INELIGIBLE, Outcome.NEEDS_REVIEW),
            self.a_score(Outcome.NEEDS_REVIEW, Outcome.NEEDS_REVIEW),
        ]

        assert empirical_coverage(scores) == 0.0

    def test_the_abstention_it_got_right_is_still_credited_as_accurate(self):
        """Coverage and accuracy answer different questions, and the fix must not blur them."""
        score = self.a_score(Outcome.NEEDS_REVIEW, Outcome.NEEDS_REVIEW)

        assert score.correct is True
        assert score.answered is False
