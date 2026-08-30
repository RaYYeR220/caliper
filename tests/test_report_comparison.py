"""Scoring one run against two answer keys, and saying whether the correction mattered.

The answer key was corrected after a scored run, which is the circumstance in which a correction is
least trustworthy. Publishing the corrected numbers alone asks the reader to take our word for it;
publishing both asks a better question — did fixing the key change the conclusion, or only the
figures? — and that question has an answer this section can state.

The decisions being scored are identical in both columns. Only the key differs, so any change in the
table is the key's doing and none of it is the system's.
"""

from __future__ import annotations

import pytest

from caliper.evalrun import ArmReport
from caliper.logic import ScreeningOutcome
from caliper.metrics import CaseScore, summarise
from caliper.report import ReportInputs, comparison_note, comparison_table, render

ELIGIBLE = ScreeningOutcome.ELIGIBLE
INELIGIBLE = ScreeningOutcome.INELIGIBLE
REVIEW = ScreeningOutcome.NEEDS_REVIEW


def score(case_id: str, expected: ScreeningOutcome, decision: ScreeningOutcome) -> CaseScore:
    return CaseScore(
        case_id=case_id,
        expected=expected,
        decision=decision,
        forced_decision=decision if decision is not REVIEW else ELIGIBLE,
        criteria_coverage=1.0,
        trap="none",
        provenance="annotated",
    )


def arm(name: str, scores: list[CaseScore]) -> ArmReport:
    return ArmReport(arm=name, scores=scores, summary=summarise(scores, arm=name))


def a_run(expected: ScreeningOutcome) -> list[ArmReport]:
    """One safe arm and one that sends an ineligible patient forward, scored against `expected`."""
    return [
        arm("caliper", [score("c1", expected, REVIEW), score("c2", INELIGIBLE, INELIGIBLE)]),
        arm("single_prompt", [score("c1", expected, ELIGIBLE), score("c2", INELIGIBLE, ELIGIBLE)]),
    ]


class TestTheTable:
    def test_it_puts_the_same_arm_side_by_side_under_both_keys(self):
        table = comparison_table(a_run(INELIGIBLE), a_run(ELIGIBLE), label="version one")

        assert "version one" in table
        rows = [line for line in table.splitlines() if line.startswith("| `caliper`")]
        assert len(rows) == 1

    def test_an_arm_missing_from_the_earlier_run_is_marked_rather_than_dropped(self):
        table = comparison_table(a_run(INELIGIBLE), [], label="version one")

        assert "| `caliper` |" in table
        assert "—" in table


class TestTheSentence:
    def test_it_says_so_when_the_safety_ordering_survives_the_correction(self):
        note = comparison_note(a_run(INELIGIBLE), a_run(ELIGIBLE), label="version one")

        assert "unsafe" in note
        assert "unchanged" in note

    def test_it_refuses_to_claim_that_when_the_ordering_moved(self):
        current = a_run(INELIGIBLE)
        # Under the earlier key nothing is unsafe, so the ordering the current run shows is not one
        # the earlier run agreed with, and the sentence must not say it was.
        earlier = [
            arm("caliper", [score("c1", REVIEW, REVIEW)]),
            arm("single_prompt", [score("c1", ELIGIBLE, ELIGIBLE)]),
        ]
        note = comparison_note(current, earlier, label="version one")

        assert "unchanged" not in note

    def test_with_nothing_to_compare_it_says_nothing(self):
        assert comparison_note(a_run(INELIGIBLE), [], label="version one") is None


class TestInTheDocument:
    def test_the_section_appears_only_when_a_second_run_was_given(self):
        without = render(ReportInputs(arms=a_run(INELIGIBLE), key_digest="d" * 64, key_cases=2))
        assert "scored against" not in without

        with_ = render(
            ReportInputs(
                arms=a_run(INELIGIBLE),
                key_digest="d" * 64,
                key_cases=2,
                comparison=a_run(ELIGIBLE),
                comparison_label="version one",
                comparison_digest="a" * 64,
            )
        )
        assert "version one" in with_

    def test_it_names_the_digest_of_the_key_it_is_comparing_against(self):
        text = render(
            ReportInputs(
                arms=a_run(INELIGIBLE),
                key_digest="d" * 64,
                key_cases=2,
                comparison=a_run(ELIGIBLE),
                comparison_label="version one",
                comparison_digest="a" * 64,
            )
        )

        assert "a" * 16 in text

    def test_a_comparison_without_a_label_is_refused_rather_than_rendered_anonymously(self):
        with pytest.raises(ValueError, match="label"):
            ReportInputs(
                arms=a_run(INELIGIBLE),
                key_digest="d" * 64,
                key_cases=2,
                comparison=a_run(ELIGIBLE),
            )
