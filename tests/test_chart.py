"""The chart summary is an annotation artifact, so its guarantees are about the reader.

Two properties matter more than the wording: it must be byte-stable, because the file is committed
alongside the labels a human derived from it, and it must never quietly drop a result, because an
omitted creatinine turns into an annotated "unknown" that the answer key then treats as truth.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from caliper.chart import summarise, summarise_dict
from caliper.fhir import load_patient_index
from caliper.ir import Code
from caliper.record import Evidence, PatientIndex

SCREENING = date(2026, 6, 1)
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PATIENTS_DIR = DATA_DIR / "patients"

CREATININE = Code(system="LOINC", code="38483-4", display="Creatinine")
HBA1C = Code(system="LOINC", code="4548-4", display="Hemoglobin A1c")


def observation(
    value: float, when: date, *, code: Code = CREATININE, unit: str = "mg/dL"
) -> Evidence:
    return Evidence(
        kind="observation",
        resource_type="Observation",
        resource_id=f"obs-{code.code}-{when.isoformat()}",
        display=code.display or code.code,
        fhir_path="Bundle.entry[1].resource",
        codes=(code,),
        value=value,
        unit=unit,
        date=when,
    )


def condition(display: str, when: date, *, resource_id: str = "cond-1") -> Evidence:
    return Evidence(
        kind="condition",
        resource_type="Condition",
        resource_id=resource_id,
        display=display,
        fhir_path="Bundle.entry[2].resource",
        codes=(Code(system="SNOMED", code="195967001"),),
        date=when,
    )


def encounter(when: date, *, resource_id: str = "enc-1") -> Evidence:
    return Evidence(
        kind="encounter",
        resource_type="Encounter",
        resource_id=resource_id,
        display="General examination",
        fhir_path="Bundle.entry[3].resource",
        date=when,
    )


def index(*evidence: Evidence, birth_date: date | None = date(1980, 6, 2)) -> PatientIndex:
    return PatientIndex(
        patient_id="p-1", birth_date=birth_date, sex="female", evidence=list(evidence)
    )


class TestDeterminism:
    def test_two_calls_on_the_same_index_are_byte_identical(self):
        patient = index(
            observation(1.1, date(2025, 3, 1)),
            observation(0.9, date(2024, 3, 1)),
            condition("Asthma (disorder) (active, confirmed)", date(2001, 1, 1)),
            encounter(date(2025, 3, 1)),
        )
        assert summarise(patient, as_of=SCREENING) == summarise(patient, as_of=SCREENING)

    def test_evidence_order_does_not_change_the_summary(self):
        rows = [
            observation(1.1, date(2025, 3, 1)),
            observation(0.9, date(2024, 3, 1)),
            condition("Asthma (disorder) (active, confirmed)", date(2001, 1, 1)),
        ]
        assert summarise(index(*rows), as_of=SCREENING) == summarise(
            index(*reversed(rows)), as_of=SCREENING
        )

    def test_the_summary_ends_with_exactly_one_newline(self):
        text = summarise(index(), as_of=SCREENING)
        assert text.endswith("\n") and not text.endswith("\n\n")


class TestDemographics:
    def test_age_is_reported_at_the_screening_date_not_today(self):
        """A summary that ages with the wall clock cannot be committed next to its labels."""
        patient = index(birth_date=date(1980, 6, 2))
        assert summarise_dict(patient, as_of=date(2026, 6, 1))["demographics"]["age_years"] == 45
        assert summarise_dict(patient, as_of=date(2030, 6, 2))["demographics"]["age_years"] == 50

    def test_the_screening_date_is_stated_in_the_text(self):
        assert "2026-06-01" in summarise(index(), as_of=SCREENING)

    def test_a_missing_birth_date_is_reported_rather_than_guessed(self):
        summary = summarise_dict(index(birth_date=None), as_of=SCREENING)
        assert summary["demographics"]["age_years"] is None
        assert summary["demographics"]["birth_date"] is None


class TestResults:
    def test_a_patient_with_no_labs_still_summarises(self):
        patient = index(condition("Asthma (disorder) (active, confirmed)", date(2001, 1, 1)))
        text = summarise(patient, as_of=SCREENING)
        assert summarise_dict(patient, as_of=SCREENING)["analytes"] == []
        assert "Asthma" in text

    def test_an_empty_index_summarises(self):
        assert summarise(index(), as_of=SCREENING)

    def test_the_most_recent_value_is_the_one_shown_with_its_date(self):
        patient = index(
            observation(0.9, date(2024, 3, 1)),
            observation(1.4, date(2025, 3, 1)),
            observation(1.1, date(2023, 3, 1)),
        )
        analyte = summarise_dict(patient, as_of=SCREENING)["analytes"][0]
        assert analyte["value"] == 1.4
        assert analyte["date"] == "2025-03-01"
        assert analyte["unit"] == "mg/dL"
        assert "1.4 mg/dL" in summarise(patient, as_of=SCREENING)
        assert "2025-03-01" in summarise(patient, as_of=SCREENING)

    def test_every_result_line_carries_a_date(self):
        patient = index(
            observation(1.1, date(2025, 3, 1)),
            observation(42.0, date(2024, 5, 6), code=HBA1C, unit="%"),
        )
        for analyte in summarise_dict(patient, as_of=SCREENING)["analytes"]:
            assert analyte["date"]

    def test_a_single_result_has_no_trend(self):
        analyte = summarise_dict(index(observation(1.1, date(2025, 3, 1))), as_of=SCREENING)[
            "analytes"
        ][0]
        assert analyte["count"] == 1
        assert analyte["trend"] is None

    def test_a_second_result_produces_a_trend_and_the_earlier_value(self):
        patient = index(observation(0.9, date(2024, 3, 1)), observation(1.1, date(2025, 3, 1)))
        analyte = summarise_dict(patient, as_of=SCREENING)["analytes"][0]
        assert analyte["count"] == 2
        assert analyte["trend"] == "rising"
        assert analyte["previous_value"] == 0.9
        assert analyte["previous_date"] == "2024-03-01"

    def test_a_falling_series_is_reported_as_falling(self):
        patient = index(observation(1.1, date(2024, 3, 1)), observation(0.9, date(2025, 3, 1)))
        assert summarise_dict(patient, as_of=SCREENING)["analytes"][0]["trend"] == "falling"

    def test_a_trend_across_two_units_is_not_claimed(self):
        """Comparing 88 umol/L against 1.0 mg/dL as numbers would invent a direction."""
        patient = index(
            observation(1.0, date(2024, 3, 1)),
            observation(88.0, date(2025, 3, 1), unit="umol/L"),
        )
        assert summarise_dict(patient, as_of=SCREENING)["analytes"][0]["trend"] == "unit changed"

    def test_distinct_analytes_are_reported_separately(self):
        patient = index(
            observation(1.1, date(2025, 3, 1)),
            observation(7.2, date(2025, 3, 1), code=HBA1C, unit="%"),
        )
        codes = {a["loinc"] for a in summarise_dict(patient, as_of=SCREENING)["analytes"]}
        assert codes == {"38483-4", "4548-4"}

    def test_observations_without_a_numeric_value_are_counted_not_listed(self):
        survey = Evidence(
            kind="observation",
            resource_type="Observation",
            resource_id="obs-survey",
            display="Are you a refugee",
            fhir_path="Bundle.entry[4].resource",
            date=date(2025, 3, 1),
        )
        summary = summarise_dict(index(survey), as_of=SCREENING)
        assert summary["analytes"] == []
        assert summary["observations_without_value"] == 1


class TestTemporalHonesty:
    def test_evidence_recorded_after_the_screening_date_is_excluded(self):
        """Synthea bundles run past any fixed screening date; a chart may not show the future."""
        patient = index(
            observation(1.1, date(2025, 3, 1)),
            observation(9.9, date(2026, 8, 1)),
        )
        summary = summarise_dict(patient, as_of=SCREENING)
        assert summary["analytes"][0]["value"] == 1.1
        assert summary["excluded_after_screening"] == 1
        assert "9.9" not in summarise(patient, as_of=SCREENING)

    def test_the_exclusion_is_stated_rather_than_silent(self):
        patient = index(observation(9.9, date(2026, 8, 1)))
        assert "1 record dated after the screening date" in summarise(patient, as_of=SCREENING)

    def test_nothing_is_said_when_nothing_was_excluded(self):
        assert "dated after the screening date" not in summarise(index(), as_of=SCREENING)


class TestConditions:
    def test_active_and_resolved_conditions_are_separated(self):
        patient = index(
            condition("Asthma (disorder) (active, confirmed)", date(2001, 1, 1), resource_id="c1"),
            condition(
                "Stress (finding) (resolved, confirmed)", date(2013, 3, 26), resource_id="c2"
            ),
        )
        summary = summarise_dict(patient, as_of=SCREENING)
        assert [c["display"] for c in summary["conditions"]["active"]] == ["Asthma (disorder)"]
        assert [c["display"] for c in summary["conditions"]["inactive"]] == ["Stress (finding)"]

    def test_the_onset_date_is_carried(self):
        patient = index(condition("Asthma (disorder) (active, confirmed)", date(2001, 1, 1)))
        assert summarise_dict(patient, as_of=SCREENING)["conditions"]["active"][0][
            "date"
        ] == "2001-01-01"

    def test_a_condition_with_no_status_suffix_is_treated_as_active(self):
        patient = index(condition("Asthma", date(2001, 1, 1)))
        summary = summarise_dict(patient, as_of=SCREENING)
        assert [c["display"] for c in summary["conditions"]["active"]] == ["Asthma"]

    def test_an_unconfirmed_condition_says_so(self):
        patient = index(condition("Asthma (disorder) (active, provisional)", date(2001, 1, 1)))
        assert summarise_dict(patient, as_of=SCREENING)["conditions"]["active"][0][
            "verification"
        ] == "provisional"


class TestMedicationsEncountersAndNotes:
    def test_the_most_recent_order_per_drug_is_shown_with_its_date(self):
        def med(when: date, resource_id: str) -> Evidence:
            return Evidence(
                kind="medication",
                resource_type="MedicationRequest",
                resource_id=resource_id,
                display="Ventolin inhaler",
                fhir_path="Bundle.entry[5].resource",
                codes=(Code(system="RxNorm", code="859088"),),
                date=when,
            )

        patient = index(med(date(2016, 4, 12), "m1"), med(date(2020, 1, 3), "m2"))
        medications = summarise_dict(patient, as_of=SCREENING)["medications"]
        assert len(medications) == 1
        assert medications[0]["date"] == "2020-01-03"

    def test_a_medication_with_no_drug_name_is_flagged_rather_than_left_blank(self):
        """Synthea names a third of its drugs by reference to a resource the corpus drops."""
        anonymous = Evidence(
            kind="medication",
            resource_type="MedicationRequest",
            resource_id="m-anon",
            display="",
            fhir_path="Bundle.entry[5].resource",
            date=date(2018, 8, 5),
        )
        summary = summarise_dict(index(anonymous), as_of=SCREENING)
        assert summary["medications"][0]["display"] == "(unlabelled MedicationRequest)"

    def test_nameless_medications_are_counted_separately(self):
        def anonymous(resource_id: str, when: date) -> Evidence:
            return Evidence(
                kind="medication",
                resource_type="MedicationRequest",
                resource_id=resource_id,
                display="",
                fhir_path="Bundle.entry[5].resource",
                date=when,
            )

        patient = index(anonymous("m-1", date(2018, 8, 5)), anonymous("m-2", date(2020, 1, 3)))
        assert len(summarise_dict(patient, as_of=SCREENING)["medications"]) == 2

    def test_encounter_count_and_span_are_reported(self):
        patient = index(encounter(date(2019, 1, 1), resource_id="e1"), encounter(date(2025, 4, 1)))
        encounters = summarise_dict(patient, as_of=SCREENING)["encounters"]
        assert encounters == {"count": 2, "first_date": "2019-01-01", "last_date": "2025-04-01"}

    def test_notes_are_listed_when_present(self):
        note = Evidence(
            kind="note",
            resource_type="DocumentReference",
            resource_id="doc-1",
            display="Discharge summary",
            fhir_path="Bundle.entry[6].resource",
            source="narrative",
            narrative_quote="Patient denies chest pain.",
            date=date(2025, 2, 1),
        )
        summary = summarise_dict(index(note), as_of=SCREENING)
        assert summary["notes"] == [
            {"date": "2025-02-01", "display": "Discharge summary", "resource_id": "doc-1"}
        ]

    def test_no_notes_is_stated_rather_than_omitted(self):
        assert "note" in summarise(index(), as_of=SCREENING).casefold()


class TestFocusCodes:
    def test_focus_analytes_are_listed_before_the_rest(self):
        patient = index(
            observation(1.1, date(2025, 3, 1)),
            observation(7.2, date(2025, 3, 1), code=HBA1C, unit="%"),
        )
        text = summarise(patient, as_of=SCREENING, focus_codes=["4548-4"])
        assert text.index("4548-4") < text.index("38483-4")

    def test_focus_codes_do_not_remove_anything(self):
        patient = index(
            observation(1.1, date(2025, 3, 1)),
            observation(7.2, date(2025, 3, 1), code=HBA1C, unit="%"),
        )
        focused = summarise(patient, as_of=SCREENING, focus_codes=["4548-4"])
        assert "38483-4" in focused

    def test_an_unmatched_focus_code_is_harmless(self):
        patient = index(observation(1.1, date(2025, 3, 1)))
        assert summarise(patient, as_of=SCREENING, focus_codes=["99999-9"])

    def test_focus_order_follows_the_caller(self):
        patient = index(
            observation(1.1, date(2025, 3, 1)),
            observation(7.2, date(2025, 3, 1), code=HBA1C, unit="%"),
        )
        text = summarise(patient, as_of=SCREENING, focus_codes=["38483-4", "4548-4"])
        assert text.index("38483-4") < text.index("4548-4")


def _bundle_paths() -> list[Path]:
    if not PATIENTS_DIR.is_dir():
        return []
    return sorted(
        path
        for path in PATIENTS_DIR.glob("*.json")
        if path.name not in {"index.json", "PROVENANCE.json"}
    )


@pytest.mark.skipif(not _bundle_paths(), reason="data/patients is not present")
class TestAgainstRealBundles:
    def test_a_real_bundle_summarises_deterministically(self):
        path = _bundle_paths()[0]
        patient = load_patient_index(json.loads(path.read_text(encoding="utf-8")))
        first = summarise(patient, as_of=SCREENING)
        assert first == summarise(patient, as_of=SCREENING)
        assert patient.patient_id in first

    def test_a_reloaded_bundle_produces_the_same_summary(self):
        """Byte stability has to survive re-parsing, not just a second call on one object."""
        path = _bundle_paths()[0]
        text = path.read_text(encoding="utf-8")
        one = summarise(load_patient_index(json.loads(text)), as_of=SCREENING)
        two = summarise(load_patient_index(json.loads(text)), as_of=SCREENING)
        assert one == two

    def test_every_committed_bundle_summarises_without_raising(self):
        for path in _bundle_paths():
            patient = load_patient_index(json.loads(path.read_text(encoding="utf-8")))
            assert summarise(patient, as_of=SCREENING).strip()


class TestVitalStatus:
    """The baseline sees the chart through this summary and nothing else.

    Caliper reads `PatientIndex.deceased` directly. If the summary omits it, the two systems are not
    being shown the same patient, and the comparison measures our plumbing rather than their
    reasoning.
    """

    def a_patient(self, **overrides):
        from datetime import date as _date

        from caliper.record import PatientIndex

        base = dict(
            patient_id="p-1",
            birth_date=_date(1970, 1, 1),
            sex="female",
            evidence=[],
        )
        return PatientIndex(**{**base, **overrides})

    def test_a_death_before_the_screening_date_is_stated(self):
        from datetime import date as _date

        text = summarise(self.a_patient(deceased=_date(2026, 5, 3)), as_of=_date(2026, 6, 1))
        assert "2026-05-03" in text
        assert "died" in text.lower() or "deceased" in text.lower()

    def test_a_death_recorded_after_the_screening_date_is_not(self):
        """It had not happened yet on the date the screening is about."""
        from datetime import date as _date

        text = summarise(self.a_patient(deceased=_date(2026, 7, 1)), as_of=_date(2026, 6, 1))
        assert "2026-07-01" not in text

    def test_a_death_with_no_date_is_still_stated(self):
        from datetime import date as _date

        text = summarise(self.a_patient(deceased_undated=True), as_of=_date(2026, 6, 1))
        assert "deceased" in text.lower() or "died" in text.lower()

    def test_a_living_patient_gets_no_such_line(self):
        from datetime import date as _date

        text = summarise(self.a_patient(), as_of=_date(2026, 6, 1))
        assert "died" not in text.lower()
