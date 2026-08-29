"""The rollup rule is the safety spine.

ELIGIBLE must be unreachable while anything is unresolved.
"""

import pytest

from caliper.logic import CriterionVerdict, ScreeningOutcome, Verdict, roll_up


def inc(verdict: Verdict, cid: str = "INC-1") -> CriterionVerdict:
    return CriterionVerdict(criterion_id=cid, kind="inclusion", verdict=verdict)


def exc(verdict: Verdict, cid: str = "EXC-1") -> CriterionVerdict:
    return CriterionVerdict(criterion_id=cid, kind="exclusion", verdict=verdict)


def test_all_inclusions_met_and_no_exclusion_triggered_is_eligible():
    outcome = roll_up([inc(Verdict.MET), exc(Verdict.NOT_MET)])
    assert outcome.decision is ScreeningOutcome.ELIGIBLE


def test_an_unmet_inclusion_makes_the_patient_ineligible():
    outcome = roll_up([inc(Verdict.NOT_MET), exc(Verdict.NOT_MET)])
    assert outcome.decision is ScreeningOutcome.INELIGIBLE


def test_a_triggered_exclusion_makes_the_patient_ineligible():
    outcome = roll_up([inc(Verdict.MET), exc(Verdict.MET)])
    assert outcome.decision is ScreeningOutcome.INELIGIBLE


def test_a_single_unknown_criterion_blocks_eligible_and_asks_for_review():
    outcome = roll_up([inc(Verdict.MET), inc(Verdict.UNKNOWN, "INC-2"), exc(Verdict.NOT_MET)])
    assert outcome.decision is ScreeningOutcome.NEEDS_REVIEW


def test_an_unknown_exclusion_also_blocks_eligible():
    outcome = roll_up([inc(Verdict.MET), exc(Verdict.UNKNOWN)])
    assert outcome.decision is ScreeningOutcome.NEEDS_REVIEW


def test_a_hard_failure_outranks_an_unresolved_criterion():
    """A definitively failed inclusion ends the screening even if other criteria are unresolved."""
    outcome = roll_up([inc(Verdict.NOT_MET), inc(Verdict.UNKNOWN, "INC-2")])
    assert outcome.decision is ScreeningOutcome.INELIGIBLE


def test_an_empty_criteria_set_is_never_eligible():
    """A trial we failed to compile any criteria from must not screen everyone in."""
    outcome = roll_up([])
    assert outcome.decision is ScreeningOutcome.NEEDS_REVIEW


def test_the_outcome_names_the_criteria_that_decided_it():
    outcome = roll_up([inc(Verdict.MET), exc(Verdict.MET, "EXC-7"), inc(Verdict.NOT_MET, "INC-4")])
    assert outcome.deciding_criterion_ids == ["INC-4", "EXC-7"]


def test_the_outcome_lists_every_unresolved_criterion():
    outcome = roll_up(
        [inc(Verdict.MET), inc(Verdict.UNKNOWN, "INC-2"), exc(Verdict.UNKNOWN, "EXC-3")]
    )
    assert outcome.unresolved_criterion_ids == ["INC-2", "EXC-3"]


def test_an_eligible_outcome_has_nothing_unresolved():
    outcome = roll_up([inc(Verdict.MET)])
    assert outcome.unresolved_criterion_ids == []
    assert outcome.deciding_criterion_ids == []


def test_kind_must_be_inclusion_or_exclusion():
    with pytest.raises(ValueError):
        CriterionVerdict(criterion_id="X-1", kind="maybe", verdict=Verdict.MET)
