"""Screening one patient against one trial: the whole deterministic path, end to end."""

from datetime import date

from caliper.evaluate import AbsencePolicy
from caliper.ir import (
    Code,
    Concept,
    CriteriaSet,
    Criterion,
    DemographicPredicate,
    ObservationPredicate,
    PresencePredicate,
    UnsupportedPredicate,
)
from caliper.logic import ScreeningOutcome, Verdict
from caliper.record import Evidence, PatientIndex
from caliper.screen import screen

SCREENING = date(2026, 6, 1)
HBA1C = Code(system="LOINC", code="4548-4", display="Hemoglobin A1c")
HBA1C_CONCEPT = Concept(text="HbA1c", codes=(HBA1C,))
MI = Concept(text="myocardial infarction", codes=(Code(system="SNOMED", code="22298006"),))

SOURCE = (
    "Inclusion Criteria:\n"
    "- Age 18 years or older\n"
    "- HbA1c >= 7%\n"
    "Exclusion Criteria:\n"
    "- Myocardial infarction\n"
    "- Unsuitable in the opinion of the investigator\n"
)


def criteria(*criterion_list: Criterion) -> CriteriaSet:
    return CriteriaSet(nct_id="NCT99999999", source_text=SOURCE, criteria=list(criterion_list))


AGE = Criterion(
    id="INC-01",
    kind="inclusion",
    source_quote="Age 18 years or older",
    predicate=DemographicPredicate(field="age", op=">=", value=18, unit="years"),
)
A1C = Criterion(
    id="INC-02",
    kind="inclusion",
    source_quote="HbA1c >= 7%",
    predicate=ObservationPredicate(concept=HBA1C_CONCEPT, op=">=", value=7.0, unit="%"),
)
NO_MI = Criterion(
    id="EXC-01",
    kind="exclusion",
    source_quote="Myocardial infarction",
    predicate=PresencePredicate(type="condition", concept=MI, presence="present"),
)
JUDGEMENT = Criterion(
    id="EXC-02",
    kind="exclusion",
    source_quote="Unsuitable in the opinion of the investigator",
    predicate=UnsupportedPredicate(reason="requires investigator judgement"),
)


def a1c_result(value: float, when: date = date(2026, 5, 1)) -> Evidence:
    return Evidence(
        kind="observation",
        resource_type="Observation",
        resource_id=f"obs-a1c-{value}",
        display="Hemoglobin A1c",
        fhir_path="Bundle.entry[3].resource",
        codes=(HBA1C,),
        value=value,
        unit="%",
        date=when,
    )


def visit(when: date) -> Evidence:
    return Evidence(
        kind="encounter",
        resource_type="Encounter",
        resource_id="enc-1",
        display="ambulatory visit",
        fhir_path="Bundle.entry[1].resource",
        date=when,
    )


def patient(*evidence: Evidence, birth_date: date = date(1970, 1, 1)) -> PatientIndex:
    return PatientIndex(
        patient_id="p-1", birth_date=birth_date, sex="female", evidence=list(evidence)
    )


class TestScreeningDecisions:
    def test_a_fully_resolved_patient_is_screened_in(self):
        result = screen(
            criteria(AGE, A1C, NO_MI), patient(a1c_result(8.1), visit(date(2026, 4, 1))), SCREENING
        )
        assert result.decision is ScreeningOutcome.ELIGIBLE

    def test_a_single_unformalisable_criterion_forces_human_review(self):
        """This is the whole design: one criterion nobody can automate stops autonomy."""
        result = screen(
            criteria(AGE, A1C, NO_MI, JUDGEMENT),
            patient(a1c_result(8.1), visit(date(2026, 4, 1))),
            SCREENING,
        )
        assert result.decision is ScreeningOutcome.NEEDS_REVIEW

    def test_a_failed_inclusion_screens_the_patient_out(self):
        result = screen(
            criteria(AGE, A1C, NO_MI), patient(a1c_result(5.4), visit(date(2026, 4, 1))), SCREENING
        )
        assert result.decision is ScreeningOutcome.INELIGIBLE

    def test_a_missing_lab_never_produces_an_eligible_verdict(self):
        result = screen(criteria(AGE, A1C, NO_MI), patient(visit(date(2026, 4, 1))), SCREENING)
        assert result.decision is ScreeningOutcome.NEEDS_REVIEW


class TestWhatTheCoordinatorGetsBack:
    def test_every_criterion_appears_in_the_result(self):
        result = screen(criteria(AGE, A1C, NO_MI), patient(a1c_result(8.1)), SCREENING)
        assert [r.criterion_id for r in result.criteria] == ["INC-01", "INC-02", "EXC-01"]

    def test_unresolved_criteria_come_back_as_a_worklist(self):
        """Abstention that does not say what is missing just moves the work elsewhere."""
        result = screen(criteria(AGE, A1C, NO_MI), patient(visit(date(2026, 4, 1))), SCREENING)
        assert [h.blocks_criterion_id for h in result.resolution_worklist] == ["INC-02"]
        assert "HbA1c" in result.resolution_worklist[0].missing

    def test_the_deciding_criterion_is_named_when_a_patient_is_screened_out(self):
        result = screen(
            criteria(AGE, A1C, NO_MI), patient(a1c_result(5.4), visit(date(2026, 4, 1))), SCREENING
        )
        assert result.deciding_criterion_ids == ("INC-02",)

    def test_coverage_counts_how_much_was_decided_without_a_human(self):
        record = patient(a1c_result(8.1), visit(date(2026, 4, 1)))
        result = screen(criteria(AGE, A1C, NO_MI, JUDGEMENT), record, SCREENING)
        assert result.criteria_resolved == 3
        assert result.criteria_total == 4
        assert result.coverage == 0.75

    def test_the_result_records_the_protocol_it_was_screened_against(self):
        result = screen(criteria(AGE), patient(), SCREENING)
        assert result.nct_id == "NCT99999999"
        assert result.patient_id == "p-1"
        assert result.screened_on == SCREENING


class TestEvidenceDiscipline:
    def test_every_resolved_criterion_that_used_data_cites_it(self):
        result = screen(criteria(A1C), patient(a1c_result(8.1)), SCREENING)
        cited = [e.resource_id for r in result.criteria for e in r.evidence]
        assert cited == ["obs-a1c-8.1"]

    def test_the_absence_policy_is_recorded_on_the_result(self):
        """A verdict that depends on how we read silence must say which reading it used."""
        result = screen(
            criteria(NO_MI), patient(visit(SCREENING)), SCREENING, policy=AbsencePolicy.OPEN_WORLD
        )
        assert result.absence_policy is AbsencePolicy.OPEN_WORLD
        assert result.criteria[0].verdict is Verdict.UNKNOWN
