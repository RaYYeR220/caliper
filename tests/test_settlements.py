"""A question the record could not answer, answered by a person instead.

Abstention is only useful if it can be closed, and most of what Caliper abstains on is not a gap
in a chart — it is a category the protocol never enumerated, a plan, an intention. Those have no
FHIR query behind them. Somebody has to be asked, and their answer has to come back into the
screening or the system has merely produced a very well-documented dead end.

The whole safety argument for letting a person answer rests on one rule, and it is the rule these
tests spend most of their length on: a settlement may answer a question the record could not, and
may never contradict a question the record already answered. Everything else is bookkeeping.
"""

from __future__ import annotations

from datetime import date

import pytest

from caliper.evaluate import evaluate_criterion
from caliper.ir import (
    Code,
    Concept,
    CriteriaSet,
    Criterion,
    ObservationPredicate,
    UnsupportedPredicate,
)
from caliper.logic import ScreeningOutcome, Verdict
from caliper.record import Evidence, PatientIndex
from caliper.screen import screen
from caliper.settlements import Settlement, SettlementLog

SCREENING = date(2026, 6, 1)
A1C = Code(system="LOINC", code="4548-4", display="HbA1c")
SOURCE = (
    "Inclusion Criteria:\n"
    "- HbA1c >= 7%\n"
    "- At least one major cardiovascular risk factor\n"
    "Exclusion Criteria:\n"
    "- Planning to start an SGLT2 inhibitor\n"
)

LAB = Criterion(
    id="INC-01",
    kind="inclusion",
    source_quote="HbA1c >= 7%",
    predicate=ObservationPredicate(
        concept=Concept(text="HbA1c", codes=(A1C,)), op=">=", value=7.0, unit="%"
    ),
)
OPEN_CATEGORY = Criterion(
    id="INC-02",
    kind="inclusion",
    source_quote="At least one major cardiovascular risk factor",
    predicate=UnsupportedPredicate(reason="the protocol does not enumerate the category"),
)
INTENTION = Criterion(
    id="EXC-01",
    kind="exclusion",
    source_quote="Planning to start an SGLT2 inhibitor",
    predicate=UnsupportedPredicate(reason="an intention", settlement="at_visit"),
)

CRITERIA = CriteriaSet(nct_id="NCT99", source_text=SOURCE, criteria=[LAB, OPEN_CATEGORY, INTENTION])

ANSWERED_ON = date(2026, 5, 20)
NOTE = "Confirmed with the investigator against the protocol's own list."


def a_settlement(criterion_id: str, verdict: Verdict, **kw: object) -> Settlement:
    return Settlement(
        nct_id=str(kw.get("nct_id", "NCT99")),
        patient_id=str(kw.get("patient_id", "p")),
        criterion_id=criterion_id,
        verdict=verdict,
        answered_by=str(kw.get("answered_by", "r.okonkwo")),
        answered_on=ANSWERED_ON,
        note=str(kw.get("note", NOTE)),
    )


def patient(pid: str, a1c: float | None) -> PatientIndex:
    rows = [
        Evidence(
            kind="encounter",
            resource_type="Encounter",
            resource_id="enc",
            display="visit",
            fhir_path="Bundle.entry[0].resource",
            date=date(2026, 4, 2),
        )
    ]
    if a1c is not None:
        rows.append(
            Evidence(
                kind="observation",
                resource_type="Observation",
                resource_id="obs",
                display="HbA1c",
                fhir_path="Bundle.entry[1].resource",
                codes=(A1C,),
                value=a1c,
                unit="%",
                date=date(2026, 5, 2),
            )
        )
    return PatientIndex(patient_id=pid, birth_date=date(1968, 1, 1), sex="female", evidence=rows)


# ------------------------------------------------------------------------------------------------
# The rule the whole feature rests on
# ------------------------------------------------------------------------------------------------


class TestASettlementCannotContradictTheRecord:
    def test_it_answers_a_criterion_the_record_left_unknown(self):
        log = SettlementLog([a_settlement("INC-02", Verdict.MET)])
        result = evaluate_criterion(
            OPEN_CATEGORY, patient("p", 8.1), SCREENING, settlements=log, nct_id="NCT99"
        )

        assert result.verdict is Verdict.MET

    def test_it_is_refused_where_the_record_already_answered(self):
        log = SettlementLog([a_settlement("INC-01", Verdict.MET)])
        result = evaluate_criterion(
            LAB, patient("p", 5.4), SCREENING, settlements=log, nct_id="NCT99"
        )

        assert result.verdict is Verdict.NOT_MET
        assert result.settled_by is None

    def test_the_refusal_is_recorded_rather_than_silent(self):
        log = SettlementLog([a_settlement("INC-01", Verdict.MET)])
        evaluate_criterion(LAB, patient("p", 5.4), SCREENING, settlements=log, nct_id="NCT99")

        assert [refusal.criterion_id for refusal in log.refused] == ["INC-01"]
        assert "record" in log.refused[0].reason

    def test_a_settlement_for_another_trial_is_not_applied(self):
        log = SettlementLog([a_settlement("INC-02", Verdict.MET, nct_id="NCT-OTHER")])
        result = evaluate_criterion(
            OPEN_CATEGORY, patient("p", 8.1), SCREENING, settlements=log, nct_id="NCT99"
        )

        assert result.verdict is Verdict.UNKNOWN

    def test_a_settlement_for_another_patient_is_not_applied(self):
        """The property this module was rewritten for.

        The blocking criterion is usually the same one across a whole cohort, which makes a
        cohort-wide answer tempting and wrong: "does this patient have a major cardiovascular risk
        factor" is a different question about each of them, and one `met` would have carried
        twenty-three charts nobody was asked about.
        """
        log = SettlementLog([a_settlement("INC-02", Verdict.MET, patient_id="someone-else")])
        result = evaluate_criterion(
            OPEN_CATEGORY, patient("p", 8.1), SCREENING, settlements=log, nct_id="NCT99"
        )

        assert result.verdict is Verdict.UNKNOWN

    def test_an_unnamed_patient_is_refused_at_construction(self):
        with pytest.raises(ValueError, match="one patient"):
            a_settlement("INC-02", Verdict.MET, patient_id=" ")

    def test_the_same_criterion_can_be_answered_for_two_patients(self):
        log = SettlementLog(
            [
                a_settlement("INC-02", Verdict.MET, patient_id="a"),
                a_settlement("INC-02", Verdict.NOT_MET, patient_id="b"),
            ]
        )

        assert len(log) == 2

    def test_unknown_is_not_an_answer_a_person_may_give(self):
        with pytest.raises(ValueError, match="MET or NOT_MET"):
            a_settlement("INC-02", Verdict.UNKNOWN)

    def test_an_unsigned_settlement_is_refused_at_construction(self):
        with pytest.raises(ValueError, match="answered_by"):
            a_settlement("INC-02", Verdict.MET, answered_by="  ")

    def test_an_unexplained_settlement_is_refused_at_construction(self):
        with pytest.raises(ValueError, match="note"):
            a_settlement("INC-02", Verdict.MET, note="")


# ------------------------------------------------------------------------------------------------
# What the screening does with it
# ------------------------------------------------------------------------------------------------


class TestScreening:
    def test_settling_the_blocking_criterion_lets_the_screening_close(self):
        log = SettlementLog([a_settlement("INC-02", Verdict.MET)])
        before = screen(CRITERIA, patient("p", 8.1), SCREENING)
        after = screen(CRITERIA, patient("p", 8.1), SCREENING, settlements=log)

        assert before.decision is ScreeningOutcome.NEEDS_REVIEW
        assert after.decision is ScreeningOutcome.ELIGIBLE

    def test_a_settled_exclusion_can_end_the_screening(self):
        log = SettlementLog([a_settlement("EXC-01", Verdict.MET)])
        result = screen(CRITERIA, patient("p", 8.1), SCREENING, settlements=log)

        assert result.decision is ScreeningOutcome.INELIGIBLE
        assert result.deciding_criterion_ids == ("EXC-01",)

    def test_the_screening_says_which_criteria_a_person_answered(self):
        log = SettlementLog([a_settlement("INC-02", Verdict.MET)])
        result = screen(CRITERIA, patient("p", 8.1), SCREENING, settlements=log)

        assert result.settled_criterion_ids == ("INC-02",)

    def test_an_unsettled_screening_reports_none(self):
        assert screen(CRITERIA, patient("p", 8.1), SCREENING).settled_criterion_ids == ()

    def test_the_answer_travels_with_who_gave_it(self):
        log = SettlementLog([a_settlement("INC-02", Verdict.MET)])
        result = screen(CRITERIA, patient("p", 8.1), SCREENING, settlements=log)
        settled = next(r for r in result.criteria if r.criterion_id == "INC-02")

        assert settled.settled_by is not None
        assert settled.settled_by.answered_by == "r.okonkwo"
        assert "r.okonkwo" in settled.rationale

    def test_a_settled_criterion_carries_no_evidence(self):
        log = SettlementLog([a_settlement("INC-02", Verdict.MET)])
        result = screen(CRITERIA, patient("p", 8.1), SCREENING, settlements=log)
        settled = next(r for r in result.criteria if r.criterion_id == "INC-02")

        assert settled.evidence == ()

    def test_a_dead_patient_is_not_brought_back_by_a_settlement(self):
        log = SettlementLog([a_settlement("INC-02", Verdict.MET)])
        dead = PatientIndex(
            patient_id="p",
            birth_date=date(1968, 1, 1),
            sex="female",
            evidence=[],
            deceased=date(2026, 5, 1),
        )
        result = screen(CRITERIA, dead, SCREENING, settlements=log)

        assert result.decision is ScreeningOutcome.INELIGIBLE


# ------------------------------------------------------------------------------------------------
# The log
# ------------------------------------------------------------------------------------------------


class TestTheLog:
    def test_it_survives_a_json_round_trip(self):
        log = SettlementLog([a_settlement("INC-02", Verdict.MET)])

        assert SettlementLog.from_json(log.to_json()) == log

    def test_two_answers_to_the_same_question_are_refused(self):
        with pytest.raises(ValueError, match="twice"):
            SettlementLog(
                [a_settlement("INC-02", Verdict.MET), a_settlement("INC-02", Verdict.NOT_MET)]
            )

    def test_an_empty_log_changes_nothing(self):
        plain = screen(CRITERIA, patient("p", 8.1), SCREENING)
        empty = screen(CRITERIA, patient("p", 8.1), SCREENING, settlements=SettlementLog([]))

        assert plain.decision is empty.decision
        assert [r.verdict for r in plain.criteria] == [r.verdict for r in empty.criteria]
