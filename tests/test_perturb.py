"""Constructed cases are only trustworthy if the perturbation really happened.

Two failure modes are fatal and both are tested here. A perturbation that mutates the original
index poisons every later case built from the same bundle, and a perturbation that finds no target
and returns quietly produces a case whose label asserts a change that was never made.
"""

from __future__ import annotations

import copy
import json
from datetime import date

import pytest

from caliper.ir import Code
from caliper.perturb import (
    PerturbationError,
    add_condition,
    convert_units,
    redact_analyte,
    remove_encounters,
    shift_date,
    shift_value,
)
from caliper.record import Evidence, PatientIndex

CREATININE = Code(system="LOINC", code="38483-4", display="Creatinine")
HBA1C = Code(system="LOINC", code="4548-4", display="Hemoglobin A1c")
DIABETES = Code(system="SNOMED", code="44054006", display="Diabetes mellitus type 2")


def observation(
    value: float,
    when: date,
    *,
    code: Code = CREATININE,
    unit: str = "mg/dL",
    resource_id: str | None = None,
) -> Evidence:
    return Evidence(
        kind="observation",
        resource_type="Observation",
        resource_id=resource_id or f"obs-{code.code}-{when.isoformat()}",
        display=code.display or code.code,
        fhir_path="Bundle.entry[1].resource",
        codes=(code,),
        value=value,
        unit=unit,
        date=when,
    )


def encounter(when: date, *, resource_id: str | None = None) -> Evidence:
    return Evidence(
        kind="encounter",
        resource_type="Encounter",
        resource_id=resource_id or f"enc-{when.isoformat()}",
        display="General examination",
        fhir_path="Bundle.entry[3].resource",
        date=when,
    )


def index(*evidence: Evidence) -> PatientIndex:
    return PatientIndex(
        patient_id="p-1", birth_date=date(1980, 6, 2), sex="female", evidence=list(evidence)
    )


def a_chart() -> PatientIndex:
    return index(
        observation(0.9, date(2024, 3, 1)),
        observation(1.4, date(2025, 3, 1)),
        observation(7.1, date(2025, 3, 1), code=HBA1C, unit="%"),
        encounter(date(2024, 3, 1)),
        encounter(date(2025, 3, 1)),
        encounter(date(2026, 4, 1)),
    )


PERTURBATIONS = [
    pytest.param(lambda p: redact_analyte(p, "38483-4"), id="redact_analyte"),
    pytest.param(lambda p: shift_value(p, "4548-4", to=6.9), id="shift_value"),
    pytest.param(
        lambda p: convert_units(p, "38483-4", to_unit="umol/L", factor=88.4), id="convert_units"
    ),
    pytest.param(
        lambda p: shift_date(p, "obs-38483-4-2025-03-01", to=date(2020, 1, 1)), id="shift_date"
    ),
    pytest.param(lambda p: remove_encounters(p, after=date(2025, 6, 1)), id="remove_encounters"),
    pytest.param(
        lambda p: add_condition(p, DIABETES, "Diabetes mellitus type 2", onset=date(2019, 5, 4)),
        id="add_condition",
    ),
]


class TestNonDestructive:
    @pytest.mark.parametrize("perturb", PERTURBATIONS)
    def test_the_original_index_is_untouched(self, perturb):
        patient = a_chart()
        before = copy.deepcopy(patient)
        result = perturb(patient)
        assert patient == before
        assert result.patient is not patient
        assert result.patient.evidence is not patient.evidence

    @pytest.mark.parametrize("perturb", PERTURBATIONS)
    def test_the_perturbation_is_recorded(self, perturb):
        result = perturb(a_chart())
        assert len(result.perturbations) == 1
        record = result.perturbations[0]
        assert record.kind
        assert record.description
        assert record.affected_resource_ids

    @pytest.mark.parametrize("perturb", PERTURBATIONS)
    def test_the_record_survives_a_round_trip_through_plain_data(self, perturb):
        record = perturb(a_chart()).perturbations[0]
        assert json.loads(json.dumps(record.to_dict())) == record.to_dict()

    @pytest.mark.parametrize("perturb", PERTURBATIONS)
    def test_demographics_are_carried_across(self, perturb):
        patient = perturb(a_chart()).patient
        assert patient.patient_id == "p-1"
        assert patient.birth_date == date(1980, 6, 2)
        assert patient.sex == "female"


class TestRedactAnalyte:
    def test_every_row_for_the_analyte_is_removed(self):
        result = redact_analyte(a_chart(), "38483-4")
        codes = {c.code for row in result.patient.evidence for c in row.codes}
        assert "38483-4" not in codes

    def test_other_analytes_survive(self):
        result = redact_analyte(a_chart(), "38483-4")
        values = [row.value for row in result.patient.evidence if row.kind == "observation"]
        assert values == [7.1]

    def test_an_absent_analyte_raises_rather_than_no_ops(self):
        """A silent no-op would produce a 'constructed' case whose label is a lie."""
        with pytest.raises(PerturbationError, match="2160-0"):
            redact_analyte(a_chart(), "2160-0")

    def test_the_record_names_the_removed_rows(self):
        record = redact_analyte(a_chart(), "38483-4").perturbations[0]
        assert len(record.before) == 2
        assert record.after == ()
        assert set(record.affected_resource_ids) == {
            "obs-38483-4-2024-03-01",
            "obs-38483-4-2025-03-01",
        }


class TestShiftValue:
    def test_the_most_recent_result_is_the_one_moved(self):
        """The evaluator reads the latest matching result, so that is the row a case must move."""
        result = shift_value(a_chart(), "38483-4", to=2.5)
        rows = [row for row in result.patient.evidence if row.codes[:1] == (CREATININE,)]
        assert {row.date: row.value for row in rows} == {
            date(2024, 3, 1): 0.9,
            date(2025, 3, 1): 2.5,
        }

    def test_only_the_targeted_row_changes(self):
        original = a_chart()
        result = shift_value(original, "4548-4", to=6.9)
        changed = [
            (a, b)
            for a, b in zip(original.evidence, result.patient.evidence, strict=True)
            if a != b
        ]
        assert len(changed) == 1
        assert changed[0][0].value == 7.1
        assert changed[0][1].value == 6.9

    def test_the_unit_and_date_are_left_alone(self):
        result = shift_value(a_chart(), "4548-4", to=6.9)
        row = next(r for r in result.patient.evidence if r.value == 6.9)
        assert row.unit == "%"
        assert row.date == date(2025, 3, 1)

    def test_before_and_after_are_recorded(self):
        record = shift_value(a_chart(), "4548-4", to=6.9).perturbations[0]
        assert record.before[0]["value"] == 7.1
        assert record.after[0]["value"] == 6.9
        assert record.affected_resource_ids == ("obs-4548-4-2025-03-01",)

    def test_an_absent_analyte_raises(self):
        with pytest.raises(PerturbationError, match="2160-0"):
            shift_value(a_chart(), "2160-0", to=1.0)

    def test_an_analyte_with_no_numeric_value_raises(self):
        survey = Evidence(
            kind="observation",
            resource_type="Observation",
            resource_id="obs-survey",
            display="Tobacco smoking status",
            fhir_path="Bundle.entry[4].resource",
            codes=(Code(system="LOINC", code="72166-2"),),
            date=date(2025, 3, 1),
        )
        with pytest.raises(PerturbationError, match="numeric"):
            shift_value(index(survey), "72166-2", to=1.0)


class TestConvertUnits:
    def test_the_factor_is_applied_exactly_as_given(self):
        """The fixture must not consult the system's own conversion table to build the trap."""
        result = convert_units(a_chart(), "4548-4", to_unit="mmol/mol", factor=10.0)
        row = next(r for r in result.patient.evidence if r.codes[:1] == (HBA1C,))
        assert row.value == 71.0
        assert row.unit == "mmol/mol"

    def test_a_wrong_factor_is_applied_without_complaint(self):
        result = convert_units(a_chart(), "4548-4", to_unit="mmol/mol", factor=3.0)
        row = next(r for r in result.patient.evidence if r.codes[:1] == (HBA1C,))
        assert row.value == pytest.approx(21.3)

    def test_the_whole_series_is_converted(self):
        result = convert_units(a_chart(), "38483-4", to_unit="umol/L", factor=88.4)
        rows = sorted(
            (r for r in result.patient.evidence if r.codes[:1] == (CREATININE,)),
            key=lambda r: r.date,
        )
        assert [r.unit for r in rows] == ["umol/L", "umol/L"]
        assert [r.value for r in rows] == pytest.approx([79.56, 123.76])

    def test_other_analytes_keep_their_units(self):
        result = convert_units(a_chart(), "38483-4", to_unit="umol/L", factor=88.4)
        row = next(r for r in result.patient.evidence if r.codes[:1] == (HBA1C,))
        assert row.unit == "%"

    def test_an_absent_analyte_raises(self):
        with pytest.raises(PerturbationError, match="2160-0"):
            convert_units(a_chart(), "2160-0", to_unit="umol/L", factor=88.4)


class TestShiftDate:
    def test_the_targeted_resource_moves(self):
        result = shift_date(a_chart(), "obs-38483-4-2025-03-01", to=date(2020, 1, 1))
        row = next(r for r in result.patient.evidence if r.value == 1.4)
        assert row.date == date(2020, 1, 1)

    def test_every_row_sharing_the_resource_id_moves_together(self):
        """A FHIR panel yields one row per component, all pointing at one dated resource."""
        patient = index(
            observation(120.0, date(2025, 3, 1), resource_id="bp-1"),
            observation(80.0, date(2025, 3, 1), code=HBA1C, resource_id="bp-1"),
            encounter(date(2025, 3, 1)),
        )
        result = shift_date(patient, "bp-1", to=date(2021, 2, 2))
        moved = [r.date for r in result.patient.evidence if r.resource_id == "bp-1"]
        assert moved == [date(2021, 2, 2), date(2021, 2, 2)]
        assert len(result.perturbations[0].before) == 2

    def test_other_rows_keep_their_dates(self):
        result = shift_date(a_chart(), "obs-38483-4-2025-03-01", to=date(2020, 1, 1))
        row = next(r for r in result.patient.evidence if r.value == 0.9)
        assert row.date == date(2024, 3, 1)

    def test_an_unknown_resource_id_raises(self):
        with pytest.raises(PerturbationError, match="no-such-id"):
            shift_date(a_chart(), "no-such-id", to=date(2020, 1, 1))


class TestRemoveEncounters:
    def test_only_encounters_after_the_cutoff_go(self):
        result = remove_encounters(a_chart(), after=date(2025, 6, 1))
        kept = [r.date for r in result.patient.evidence if r.kind == "encounter"]
        assert kept == [date(2024, 3, 1), date(2025, 3, 1)]

    def test_the_cutoff_date_itself_is_kept(self):
        patient = index(encounter(date(2025, 6, 1)), encounter(date(2025, 6, 2)))
        result = remove_encounters(patient, after=date(2025, 6, 1))
        kept = [r.date for r in result.patient.evidence if r.kind == "encounter"]
        assert kept == [date(2025, 6, 1)]

    def test_non_encounter_rows_after_the_cutoff_survive(self):
        rows = remove_encounters(a_chart(), after=date(2024, 6, 1)).patient.evidence
        assert any(r.kind == "observation" and r.date == date(2025, 3, 1) for r in rows)

    def test_a_cutoff_that_removes_nothing_raises(self):
        with pytest.raises(PerturbationError, match="2030-01-01"):
            remove_encounters(a_chart(), after=date(2030, 1, 1))

    def test_undated_encounters_are_never_removed(self):
        undated = Evidence(
            kind="encounter",
            resource_type="Encounter",
            resource_id="enc-undated",
            display="encounter",
            fhir_path="Bundle.entry[9].resource",
            date=None,
        )
        patient = index(undated, encounter(date(2026, 4, 1)))
        result = remove_encounters(patient, after=date(2025, 1, 1))
        assert [r.resource_id for r in result.patient.evidence] == ["enc-undated"]


class TestAddCondition:
    def test_the_condition_is_appended_with_its_code_and_onset(self):
        result = add_condition(
            a_chart(), DIABETES, "Diabetes mellitus type 2", onset=date(2019, 5, 4)
        )
        added = [r for r in result.patient.evidence if r.kind == "condition"]
        assert len(added) == 1
        assert added[0].codes == (DIABETES,)
        assert added[0].display == "Diabetes mellitus type 2"
        assert added[0].date == date(2019, 5, 4)

    def test_the_row_declares_that_it_is_synthetic(self):
        """A constructed row must not claim a bundle entry it does not have."""
        result = add_condition(
            a_chart(), DIABETES, "Diabetes mellitus type 2", onset=date(2019, 5, 4)
        )
        added = next(r for r in result.patient.evidence if r.kind == "condition")
        assert "Bundle.entry" not in added.fhir_path
        assert "perturb" in added.fhir_path

    def test_adding_the_same_condition_twice_raises(self):
        once = add_condition(a_chart(), DIABETES, "Type 2 diabetes", onset=date(2019, 5, 4))
        with pytest.raises(PerturbationError, match="already"):
            add_condition(once.patient, DIABETES, "Type 2 diabetes", onset=date(2020, 1, 1))

    def test_the_record_has_no_before_state(self):
        record = add_condition(
            a_chart(), DIABETES, "Type 2 diabetes", onset=date(2019, 5, 4)
        ).perturbations[0]
        assert record.before == ()
        assert record.after[0]["display"] == "Type 2 diabetes"


class TestComposition:
    def test_perturbations_accumulate_in_order(self):
        result = redact_analyte(a_chart(), "38483-4").then(shift_value, "4548-4", to=6.9)
        assert [p.kind for p in result.perturbations] == ["redact_analyte", "shift_value"]

    def test_composition_leaves_the_intermediate_index_untouched(self):
        first = redact_analyte(a_chart(), "38483-4")
        before = copy.deepcopy(first.patient)
        first.then(shift_value, "4548-4", to=6.9)
        assert first.patient == before


def test_a_chart_edit_does_not_bring_a_patient_back_to_life(tmp_path):
    """Rebuilding a PatientIndex field by field drops whatever field was added last."""
    from datetime import date

    from caliper.perturb import redact_analyte
    from caliper.record import Code, Evidence, PatientIndex

    creatinine = Code(system="LOINC", code="2160-0")
    patient = PatientIndex(
        patient_id="p-1",
        birth_date=date(1970, 1, 1),
        sex="female",
        evidence=[
            Evidence(
                kind="observation",
                resource_type="Observation",
                resource_id="obs-1",
                display="Creatinine",
                fhir_path="Bundle.entry[1].resource",
                codes=(creatinine,),
                value=1.1,
                unit="mg/dL",
                date=date(2026, 1, 1),
            )
        ],
        deceased=date(2026, 5, 3),
    )
    perturbed = redact_analyte(patient, "2160-0").patient
    assert perturbed.deceased == date(2026, 5, 3)
    assert perturbed.died_before(date(2026, 6, 1)) is True
