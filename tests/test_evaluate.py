"""Per-criterion evaluation.

Nothing in here calls a language model. Given a compiled criterion and a patient index, the
verdict is a pure function — which is the whole point: the part that decides is the part you can
read.
"""

from datetime import date

import pytest

from caliper.evaluate import AbsencePolicy, evaluate_criterion
from caliper.ir import (
    Code,
    Concept,
    Criterion,
    DemographicPredicate,
    ObservationPredicate,
    PresencePredicate,
    TemporalWindow,
    UnsupportedPredicate,
)
from caliper.logic import Verdict
from caliper.record import Evidence, PatientIndex

SCREENING = date(2026, 6, 1)

CREATININE_CODE = Code(system="LOINC", code="2160-0", display="Creatinine [Mass/volume] in Serum")
CREATININE = Concept(text="serum creatinine", codes=(CREATININE_CODE,))
MI_CODE = Code(system="SNOMED", code="22298006", display="Myocardial infarction")
MI = Concept(text="myocardial infarction", codes=(MI_CODE,))


def lab(value: float, unit: str, when: date, code: Code = CREATININE_CODE) -> Evidence:
    return Evidence(
        kind="observation",
        resource_type="Observation",
        resource_id=f"obs-{when.isoformat()}-{value}",
        codes=(code,),
        display=code.display or "",
        value=value,
        unit=unit,
        date=when,
        fhir_path="Bundle.entry[0].resource",
    )


def condition(when: date, code: Code = MI_CODE) -> Evidence:
    return Evidence(
        kind="condition",
        resource_type="Condition",
        resource_id=f"cond-{when.isoformat()}",
        codes=(code,),
        display=code.display or "",
        date=when,
        fhir_path="Bundle.entry[1].resource",
    )


def encounter(when: date) -> Evidence:
    return Evidence(
        kind="encounter",
        resource_type="Encounter",
        resource_id=f"enc-{when.isoformat()}",
        display="ambulatory visit",
        date=when,
        fhir_path="Bundle.entry[2].resource",
    )


def index(*evidence: Evidence, birth_date: date | None = date(1970, 3, 4), sex: str = "female"):
    return PatientIndex(
        patient_id="p1", birth_date=birth_date, sex=sex, evidence=list(evidence)
    )


def criterion(predicate, *, kind: str = "inclusion", cid: str = "INC-01") -> Criterion:
    return Criterion(id=cid, kind=kind, source_quote="quoted from protocol", predicate=predicate)


class TestObservationThresholds:
    def test_a_value_satisfying_the_threshold_is_met(self):
        c = criterion(ObservationPredicate(concept=CREATININE, op="<=", value=1.5, unit="mg/dL"))
        result = evaluate_criterion(c, index(lab(1.2, "mg/dL", date(2026, 5, 1))), SCREENING)
        assert result.verdict is Verdict.MET

    def test_a_met_verdict_cites_the_observation_it_used(self):
        c = criterion(ObservationPredicate(concept=CREATININE, op="<=", value=1.5, unit="mg/dL"))
        result = evaluate_criterion(c, index(lab(1.2, "mg/dL", date(2026, 5, 1))), SCREENING)
        assert [e.resource_id for e in result.evidence] == ["obs-2026-05-01-1.2"]

    def test_a_value_failing_the_threshold_is_not_met(self):
        c = criterion(ObservationPredicate(concept=CREATININE, op="<=", value=1.5, unit="mg/dL"))
        result = evaluate_criterion(c, index(lab(2.4, "mg/dL", date(2026, 5, 1))), SCREENING)
        assert result.verdict is Verdict.NOT_MET

    def test_a_missing_measurement_is_unknown_rather_than_assumed_normal(self):
        c = criterion(ObservationPredicate(concept=CREATININE, op="<=", value=1.5, unit="mg/dL"))
        result = evaluate_criterion(c, index(encounter(date(2026, 5, 1))), SCREENING)
        assert result.verdict is Verdict.UNKNOWN

    def test_an_unknown_measurement_says_what_would_resolve_it(self):
        c = criterion(ObservationPredicate(concept=CREATININE, op="<=", value=1.5, unit="mg/dL"))
        result = evaluate_criterion(c, index(encounter(date(2026, 5, 1))), SCREENING)
        assert result.resolution_hint is not None
        assert "serum creatinine" in result.resolution_hint.missing
        assert result.resolution_hint.blocks_criterion_id == "INC-01"

    def test_a_measurement_outside_the_window_does_not_count(self):
        c = criterion(
            ObservationPredicate(
                concept=CREATININE,
                op="<=",
                value=1.5,
                unit="mg/dL",
                window=TemporalWindow(relation="within", amount=3, unit="months"),
            )
        )
        result = evaluate_criterion(c, index(lab(1.2, "mg/dL", date(2025, 1, 1))), SCREENING)
        assert result.verdict is Verdict.UNKNOWN

    def test_the_most_recent_value_in_the_window_is_the_one_compared(self):
        c = criterion(ObservationPredicate(concept=CREATININE, op="<=", value=1.5, unit="mg/dL"))
        record = index(lab(0.9, "mg/dL", date(2025, 1, 1)), lab(2.4, "mg/dL", date(2026, 5, 1)))
        result = evaluate_criterion(c, record, SCREENING)
        assert result.verdict is Verdict.NOT_MET

    def test_a_range_is_inclusive_at_both_ends(self):
        c = criterion(
            ObservationPredicate(
                concept=CREATININE, op="between", value=1.0, value_high=2.0, unit="mg/dL"
            )
        )
        low = evaluate_criterion(c, index(lab(1.0, "mg/dL", SCREENING)), SCREENING)
        high = evaluate_criterion(c, index(lab(2.0, "mg/dL", SCREENING)), SCREENING)
        assert (low.verdict, high.verdict) == (Verdict.MET, Verdict.MET)


class TestUnits:
    def test_a_convertible_unit_is_converted_before_comparison(self):
        """106 umol/L of creatinine is 1.2 mg/dL, which clears a 1.5 mg/dL ceiling."""
        c = criterion(ObservationPredicate(concept=CREATININE, op="<=", value=1.5, unit="mg/dL"))
        result = evaluate_criterion(c, index(lab(106.0, "umol/L", date(2026, 5, 1))), SCREENING)
        assert result.verdict is Verdict.MET

    def test_a_unit_we_cannot_convert_abstains_instead_of_guessing(self):
        c = criterion(ObservationPredicate(concept=CREATININE, op="<=", value=1.5, unit="mg/dL"))
        result = evaluate_criterion(c, index(lab(1.2, "furlongs", date(2026, 5, 1))), SCREENING)
        assert result.verdict is Verdict.UNKNOWN


class TestPresenceAndTheAbsenceProblem:
    def test_a_documented_condition_satisfies_a_present_requirement(self):
        c = criterion(PresencePredicate(type="condition", concept=MI, presence="present"))
        result = evaluate_criterion(c, index(condition(date(2026, 1, 1))), SCREENING)
        assert result.verdict is Verdict.MET

    def test_a_documented_condition_fails_an_absence_requirement(self):
        c = criterion(
            PresencePredicate(type="condition", concept=MI, presence="absent"), kind="inclusion"
        )
        result = evaluate_criterion(c, index(condition(date(2026, 1, 1))), SCREENING)
        assert result.verdict is Verdict.NOT_MET

    def test_absence_is_accepted_when_the_chart_covers_the_window(self):
        """A visit inside the window means somebody looked; silence then means absent."""
        c = criterion(
            PresencePredicate(
                type="condition",
                concept=MI,
                presence="absent",
                window=TemporalWindow(relation="within", amount=6, unit="months"),
            )
        )
        record = index(encounter(date(2026, 4, 1)), condition(date(2020, 1, 1), MI_CODE))
        result = evaluate_criterion(c, record, SCREENING)
        assert result.verdict is Verdict.MET

    def test_absence_is_unknown_when_nothing_documents_the_window(self):
        """No visit, no problem list, no evidence anyone looked. That is not a clean chart."""
        c = criterion(
            PresencePredicate(
                type="condition",
                concept=MI,
                presence="absent",
                window=TemporalWindow(relation="within", amount=6, unit="months"),
            )
        )
        result = evaluate_criterion(c, index(condition(date(2015, 1, 1))), SCREENING)
        assert result.verdict is Verdict.UNKNOWN

    def test_the_open_world_policy_never_infers_absence(self):
        c = criterion(PresencePredicate(type="condition", concept=MI, presence="absent"))
        record = index(encounter(date(2026, 4, 1)))
        result = evaluate_criterion(c, record, SCREENING, policy=AbsencePolicy.OPEN_WORLD)
        assert result.verdict is Verdict.UNKNOWN

    def test_the_closed_world_policy_infers_absence_from_silence_alone(self):
        c = criterion(PresencePredicate(type="condition", concept=MI, presence="absent"))
        result = evaluate_criterion(c, index(), SCREENING, policy=AbsencePolicy.CLOSED_WORLD)
        assert result.verdict is Verdict.MET


class TestDemographics:
    def test_age_is_computed_at_the_screening_date(self):
        c = criterion(DemographicPredicate(field="age", op=">=", value=18, unit="years"))
        result = evaluate_criterion(c, index(birth_date=date(2008, 5, 31)), SCREENING)
        assert result.verdict is Verdict.MET

    def test_a_patient_one_day_short_of_the_age_bound_is_not_met(self):
        c = criterion(DemographicPredicate(field="age", op=">=", value=18, unit="years"))
        result = evaluate_criterion(c, index(birth_date=date(2008, 6, 2)), SCREENING)
        assert result.verdict is Verdict.NOT_MET

    def test_a_missing_birth_date_is_unknown(self):
        c = criterion(DemographicPredicate(field="age", op=">=", value=18, unit="years"))
        result = evaluate_criterion(c, index(birth_date=None), SCREENING)
        assert result.verdict is Verdict.UNKNOWN

    def test_sex_is_matched_case_insensitively(self):
        c = criterion(DemographicPredicate(field="sex", op="==", value="Female"))
        result = evaluate_criterion(c, index(sex="female"), SCREENING)
        assert result.verdict is Verdict.MET


class TestUnsupportedCriteria:
    def test_a_criterion_the_compiler_refused_stays_unresolved(self):
        c = criterion(UnsupportedPredicate(reason="requires investigator judgement"))
        result = evaluate_criterion(c, index(encounter(SCREENING)), SCREENING)
        assert result.verdict is Verdict.UNKNOWN

    def test_it_tells_the_coordinator_why_a_human_has_to_read_it(self):
        c = criterion(UnsupportedPredicate(reason="requires investigator judgement"))
        result = evaluate_criterion(c, index(), SCREENING)
        assert "investigator judgement" in result.resolution_hint.missing


class TestInvariantsThatMustNeverBreak:
    @pytest.mark.parametrize(
        "predicate",
        [
            ObservationPredicate(concept=CREATININE, op="<=", value=1.5, unit="mg/dL"),
            PresencePredicate(type="condition", concept=MI, presence="present"),
            DemographicPredicate(field="age", op=">=", value=18, unit="years"),
            UnsupportedPredicate(reason="judgement"),
        ],
    )
    def test_every_unresolved_criterion_carries_a_resolution_hint(self, predicate):
        c = criterion(predicate)
        result = evaluate_criterion(c, index(birth_date=None), SCREENING)
        if result.verdict is Verdict.UNKNOWN:
            assert result.resolution_hint is not None

    def test_a_resolved_verdict_never_invents_evidence_it_did_not_read(self):
        c = criterion(ObservationPredicate(concept=CREATININE, op="<=", value=1.5, unit="mg/dL"))
        result = evaluate_criterion(c, index(lab(1.2, "mg/dL", date(2026, 5, 1))), SCREENING)
        assert all(e.resource_id for e in result.evidence)
        assert result.verdict is not Verdict.UNKNOWN
