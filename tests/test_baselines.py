"""Baselines.

The comparison only means something if the baseline is the thing a competent person would actually
reach for first, given the same information. So the single-prompt baseline sees the same chart
summary and the same protocol text, runs on the same model, and is asked the question directly.

The trivial baselines exist for a different reason. "Abstain on everything" scores perfectly on any
metric that only counts unsafe errors, so it has to appear in the results table with its coverage of
zero, where a reader can see the trade being made.
"""

import json
from datetime import date

from caliper.baselines import (
    AlwaysEligible,
    AlwaysNeedsReview,
    RandomOutcome,
    SinglePrompt,
)
from caliper.logic import ScreeningOutcome
from caliper.record import Evidence, PatientIndex

from fakes import Reply, a_client

SCREENING = date(2026, 6, 1)
CRITERIA = "Inclusion Criteria:\n\n* HbA1c >= 7%.\n"


def patient() -> PatientIndex:
    return PatientIndex(
        patient_id="p-1",
        birth_date=date(1970, 1, 1),
        sex="female",
        evidence=[
            Evidence(
                kind="observation",
                resource_type="Observation",
                resource_id="obs-1",
                display="Hemoglobin A1c",
                fhir_path="Bundle.entry[3].resource",
                value=8.1,
                unit="%",
                date=date(2026, 5, 1),
            )
        ],
    )


def decision(outcome: str, reasoning: str = "because") -> Reply:
    return Reply(json.dumps({"outcome": outcome, "reasoning": reasoning}))


class TestSinglePrompt:
    def test_it_answers_in_one_call(self):
        client, transport = a_client([decision("eligible")])
        result = SinglePrompt(client).decide(CRITERIA, patient(), SCREENING)
        assert len(transport.requests) == 1
        assert result.outcome is ScreeningOutcome.ELIGIBLE

    def test_it_is_shown_the_protocol_text_and_the_chart(self):
        client, transport = a_client([decision("eligible")])
        SinglePrompt(client).decide(CRITERIA, patient(), SCREENING)
        sent = transport.user_messages[0]
        assert "HbA1c >= 7%" in sent
        assert "8.1" in sent

    def test_it_may_answer_that_it_cannot_tell(self):
        client, _ = a_client([decision("needs_review", "no HbA1c on file")])
        result = SinglePrompt(client).decide(CRITERIA, patient(), SCREENING)
        assert result.outcome is ScreeningOutcome.NEEDS_REVIEW

    def test_the_reasoning_it_gave_is_kept_for_the_report(self):
        client, _ = a_client([decision("ineligible", "HbA1c below threshold")])
        result = SinglePrompt(client).decide(CRITERIA, patient(), SCREENING)
        assert "below threshold" in result.rationale

    def test_a_call_that_never_validates_is_recorded_as_a_failure_not_a_verdict(self):
        """A baseline that crashes must not be scored as if it had abstained."""
        client, _ = a_client([Reply("not json")] * 8)
        result = SinglePrompt(client).decide(CRITERIA, patient(), SCREENING)
        assert result.failed is True
        assert result.outcome is None

    def test_it_reports_what_it_cost(self):
        client, _ = a_client([decision("eligible")])
        result = SinglePrompt(client).decide(CRITERIA, patient(), SCREENING)
        assert result.cost_usd is not None and result.cost_usd > 0


class TestTrivialBaselines:
    def test_always_needs_review_never_decides_anything(self):
        result = AlwaysNeedsReview().decide(CRITERIA, patient(), SCREENING)
        assert result.outcome is ScreeningOutcome.NEEDS_REVIEW
        assert result.cost_usd == 0.0

    def test_always_eligible_is_the_opposite_failure(self):
        assert AlwaysEligible().decide(CRITERIA, patient(), SCREENING).outcome is (
            ScreeningOutcome.ELIGIBLE
        )

    def test_random_is_reproducible_from_its_seed(self):
        def five(seed: int) -> list:
            chooser = RandomOutcome(seed=seed)
            return [chooser.decide(CRITERIA, patient(), SCREENING).outcome for _ in range(5)]

        assert five(7) == five(7)

    def test_random_varies_across_cases(self):
        chooser = RandomOutcome(seed=7)
        outcomes = {chooser.decide(CRITERIA, patient(), SCREENING).outcome for _ in range(30)}
        assert len(outcomes) > 1

    def test_every_baseline_reports_a_name(self):
        names = {
            SinglePrompt(a_client([])[0]).name,
            AlwaysNeedsReview().name,
            AlwaysEligible().name,
            RandomOutcome(seed=1).name,
        }
        assert len(names) == 4
        assert all(names)


class TestTheMajorityBaseline:
    """The key expects `ineligible` for forty-one of fifty-one cases after the vital-status
    correction, so a system that answers only that scores well without doing anything. It is in the
    table for the same reason `always_needs_review` is: a degenerate arm that beats a real one is a
    fact about the metric, and hiding it would make the metric look better than it is."""

    def test_it_answers_ineligible_to_everything(self):
        from caliper.baselines import AlwaysIneligible

        assert AlwaysIneligible().decide(CRITERIA, patient(), SCREENING).outcome is (
            ScreeningOutcome.INELIGIBLE
        )

    def test_it_costs_nothing(self):
        from caliper.baselines import AlwaysIneligible

        assert AlwaysIneligible().decide(CRITERIA, patient(), SCREENING).cost_usd == 0.0

    def test_it_has_its_own_name(self):
        from caliper.baselines import AlwaysEligible, AlwaysIneligible

        assert AlwaysIneligible().name != AlwaysEligible().name
