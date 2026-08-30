"""Replaying a constructed case's edits onto its base chart.

`rebuild_patient` is the only implementation of this in the codebase, and everything that scores,
renders or re-derives a constructed case goes through it. The property that matters is not that it
produces a chart but that it refuses to produce the wrong one: a `before` row the chart does not
carry, or carries twice, means the published record does not describe this bundle, and a chart
built anyway would be one no record accounts for.

The last test is the regression the docstring names. `PatientIndex.deceased` was added after the
first perturbation helpers were written, and rebuilding the index field by field silently dropped
it, which brought a dead patient back to life in the middle of a screening.
"""

from __future__ import annotations

from datetime import date

import pytest

from caliper.answerkey import AnswerKeyError, Case, rebuild_patient
from caliper.ir import Code
from caliper.logic import ScreeningOutcome
from caliper.record import Evidence, PatientIndex

PATIENT_ID = "1be83f06-48ef-7bac-7097-b9e0644aeaf8"
SCREENING_DATE = date(2026, 6, 1)


def an_hba1c(value: float = 6.2, when: str = "2025-12-06") -> Evidence:
    return Evidence(
        kind="observation",
        resource_type="Observation",
        resource_id="obs-hba1c",
        display="Hemoglobin A1c/Hemoglobin.total in Blood",
        fhir_path="Bundle.entry[3].resource",
        codes=(Code(system="LOINC", code="4548-4"),),
        value=value,
        unit="%",
        date=date.fromisoformat(when),
    )


def a_snapshot(value: float = 6.2, when: str | None = "2025-12-06") -> dict:
    return {
        "resource_id": "obs-hba1c",
        "resource_type": "Observation",
        "kind": "observation",
        "display": "Hemoglobin A1c/Hemoglobin.total in Blood",
        "fhir_path": "Bundle.entry[3].resource",
        "codes": [{"system": "LOINC", "code": "4548-4"}],
        "value": value,
        "unit": "%",
        "date": when,
    }


def a_chart(*evidence: Evidence, **overrides) -> PatientIndex:
    defaults = dict(
        patient_id=PATIENT_ID,
        birth_date=date(1979, 11, 6),
        sex="male",
        evidence=list(evidence),
    )
    return PatientIndex(**{**defaults, **overrides})


def a_case(*perturbations: dict, **overrides) -> Case:
    defaults = dict(
        id="CK-001",
        patient_id=PATIENT_ID,
        nct_id="NCT03315143",
        screening_date=SCREENING_DATE,
        expected=ScreeningOutcome.ELIGIBLE,
        provenance="constructed",
        trap="none",
        rationale="the HbA1c was restated above the trial's floor",
        perturbations=perturbations,
    )
    return Case(**{**defaults, **overrides})


def a_shift(before: dict, after: dict) -> dict:
    return {
        "kind": "shift_value",
        "description": f"moved the most recent LOINC 4548-4 result to {after['value']}",
        "affected_resource_ids": ["obs-hba1c"],
        "before": [before],
        "after": [after],
    }


class TestAnnotatedCases:
    def test_a_case_with_no_perturbations_returns_the_base_chart_itself(self) -> None:
        base = a_chart(an_hba1c())
        assert rebuild_patient(a_case(provenance="annotated"), base) is base


class TestReplay:
    def test_a_shifted_value_replaces_the_row_it_names(self) -> None:
        base = a_chart(an_hba1c(6.2))
        case = a_case(a_shift(a_snapshot(6.2), a_snapshot(7.5)))

        rebuilt = rebuild_patient(case, base)

        assert [row.value for row in rebuilt.evidence] == [7.5]
        assert rebuilt.evidence[0].codes == (Code(system="LOINC", code="4548-4"),)

    def test_the_base_chart_is_not_mutated(self) -> None:
        base = a_chart(an_hba1c(6.2))
        rebuild_patient(a_case(a_shift(a_snapshot(6.2), a_snapshot(7.5))), base)
        assert [row.value for row in base.evidence] == [6.2]

    def test_edits_are_applied_in_the_order_they_were_recorded(self) -> None:
        base = a_chart(an_hba1c(6.2))
        case = a_case(
            a_shift(a_snapshot(6.2), a_snapshot(7.5)),
            a_shift(a_snapshot(7.5), a_snapshot(9.9)),
        )
        assert [row.value for row in rebuild_patient(case, base).evidence] == [9.9]

    def test_an_added_row_carries_its_synthetic_pointer(self) -> None:
        added = {
            "resource_id": "perturbation-condition-snomed-44054006",
            "resource_type": "Condition",
            "kind": "condition",
            "display": "Diabetes mellitus type 2 (disorder)",
            "fhir_path": "perturb.add_condition",
            "codes": [{"system": "SNOMED", "code": "44054006"}],
            "value": None,
            "unit": None,
            "date": "2025-12-06",
        }
        case = a_case(
            {
                "kind": "add_condition",
                "description": "added condition SNOMED 44054006",
                "affected_resource_ids": [added["resource_id"]],
                "before": [],
                "after": [added],
            }
        )
        rebuilt = rebuild_patient(case, a_chart(an_hba1c()))
        assert rebuilt.evidence[-1].fhir_path == "perturb.add_condition"
        assert rebuilt.evidence[-1].date == date(2025, 12, 6)

    def test_a_removal_with_no_replacement_shortens_the_chart(self) -> None:
        case = a_case(
            {
                "kind": "redact_analyte",
                "description": "removed all 1 results coded LOINC 4548-4",
                "affected_resource_ids": ["obs-hba1c"],
                "before": [a_snapshot(6.2)],
                "after": [],
            }
        )
        assert rebuild_patient(case, a_chart(an_hba1c(6.2))).evidence == []


class TestRefusals:
    def test_a_row_the_chart_does_not_carry_is_refused(self) -> None:
        case = a_case(a_shift(a_snapshot(5.1), a_snapshot(7.5)))
        with pytest.raises(AnswerKeyError, match="carries 0 times"):
            rebuild_patient(case, a_chart(an_hba1c(6.2)))

    def test_a_row_the_chart_carries_twice_is_refused(self) -> None:
        case = a_case(a_shift(a_snapshot(6.2), a_snapshot(7.5)))
        with pytest.raises(AnswerKeyError, match="carries 2 times"):
            rebuild_patient(case, a_chart(an_hba1c(6.2), an_hba1c(6.2)))

    def test_a_row_matching_on_everything_but_the_date_is_refused(self) -> None:
        """Two results of the same value on different days are different results."""
        case = a_case(a_shift(a_snapshot(6.2, when="2024-01-01"), a_snapshot(7.5)))
        with pytest.raises(AnswerKeyError, match="carries 0 times"):
            rebuild_patient(case, a_chart(an_hba1c(6.2, when="2025-12-06")))

    def test_the_wrong_base_chart_is_refused(self) -> None:
        base = a_chart(an_hba1c(), patient_id="ee4b7339-ca58-b6af-c199-04b6d5761c73")
        with pytest.raises(AnswerKeyError, match="expects the chart of patient"):
            rebuild_patient(a_case(a_shift(a_snapshot(), a_snapshot(7.5))), base)

    def test_an_unusable_added_row_is_refused(self) -> None:
        case = a_case(
            {"kind": "add_condition", "description": "", "before": [], "after": [{"kind": "x"}]}
        )
        with pytest.raises(AnswerKeyError, match="not a usable evidence record"):
            rebuild_patient(case, a_chart(an_hba1c()))


class TestCarriedOverFields:
    def test_a_deceased_patient_stays_deceased(self) -> None:
        base = a_chart(an_hba1c(6.2), deceased=date(2026, 5, 3))
        rebuilt = rebuild_patient(a_case(a_shift(a_snapshot(6.2), a_snapshot(7.5))), base)
        assert rebuilt.deceased == date(2026, 5, 3)
        assert rebuilt.died_before(SCREENING_DATE)

    def test_an_undated_death_stays_recorded(self) -> None:
        base = a_chart(an_hba1c(6.2), deceased_undated=True)
        rebuilt = rebuild_patient(a_case(a_shift(a_snapshot(6.2), a_snapshot(7.5))), base)
        assert rebuilt.deceased_undated is True

    def test_demographics_survive_the_rebuild(self) -> None:
        base = a_chart(an_hba1c(6.2))
        rebuilt = rebuild_patient(a_case(a_shift(a_snapshot(6.2), a_snapshot(7.5))), base)
        assert (rebuilt.patient_id, rebuilt.birth_date, rebuilt.sex) == (
            PATIENT_ID,
            date(1979, 11, 6),
            "male",
        )


class TestAgainstTheFrozenKey:
    def test_every_constructed_case_in_the_key_rebuilds(self) -> None:
        """The published records still describe the committed bundles."""
        from caliper.answerkey import load_key
        from caliper.corpus import load_patient

        key = load_key("eval/answer_key.json")
        constructed = [case for case in key.cases if case.provenance == "constructed"]
        assert constructed, "the key should carry constructed cases"
        for case in constructed:
            base = load_patient(case.patient_id)
            rebuilt = rebuild_patient(case, base)
            assert rebuilt is not base
            assert rebuilt.patient_id == base.patient_id
