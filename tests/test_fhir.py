"""Ingestion of Synthea FHIR R4 bundles into a patient index.

Every assertion here is about fidelity. What the bundle says is what the index carries, what the
bundle does not say stays unsaid, and every row keeps a pointer precise enough for a human to open
the exact resource a claim rests on.
"""

import base64
import json
from datetime import date
from pathlib import Path

import pytest

from caliper.fhir import FhirBundleError, load_patient_index, narrative_notes
from caliper.ir import Code, Concept

LOINC = "http://loinc.org"
SNOMED = "http://snomed.info/sct"
RXNORM = "http://www.nlm.nih.gov/research/umls/rxnorm"
VER_STATUS = "http://terminology.hl7.org/CodeSystem/condition-ver-status"


def a_bundle(*resources: dict) -> dict:
    """A transaction bundle wrapping the given resources, in the order given."""
    return {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": [
            {"fullUrl": f"urn:uuid:{r.get('id', i)}", "resource": r, "request": {"method": "POST"}}
            for i, r in enumerate(resources)
        ],
    }


def a_patient(**overrides: object) -> dict:
    base = {
        "resourceType": "Patient",
        "id": "3f1a-patient",
        "birthDate": "1962-04-17",
        "gender": "female",
    }
    return {**base, **overrides}


def a_lab(**overrides: object) -> dict:
    base = {
        "resourceType": "Observation",
        "id": "obs-creat",
        "status": "final",
        "effectiveDateTime": "2018-07-12T01:11:59+00:00",
        "code": {
            "text": "Creatinine [Mass/volume] in Serum or Plasma",
            "coding": [{"system": LOINC, "code": "2160-0", "display": "Creatinine"}],
        },
        "valueQuantity": {
            "value": 1.2,
            "unit": "mg/dL",
            "system": "http://unitsofmeasure.org",
            "code": "mg/dL",
        },
    }
    return {**base, **overrides}


def a_condition(**overrides: object) -> dict:
    base = {
        "resourceType": "Condition",
        "id": "cond-mi",
        "onsetDateTime": "2019-02-03T09:00:00+00:00",
        "code": {
            "text": "Myocardial infarction",
            "coding": [{"system": SNOMED, "code": "22298006", "display": "Myocardial infarction"}],
        },
    }
    return {**base, **overrides}


def an_encounter(**overrides: object) -> dict:
    base = {
        "resourceType": "Encounter",
        "id": "enc-1",
        "class": {"code": "AMB"},
        "type": [
            {
                "text": "General examination of patient",
                "coding": [{"system": SNOMED, "code": "162673000"}],
            }
        ],
        "period": {"start": "2020-05-06T14:00:00+00:00", "end": "2020-05-06T14:30:00+00:00"},
    }
    return {**base, **overrides}


def only(evidence: list, kind: str) -> list:
    return [e for e in evidence if e.kind == kind]


class TestPatientDemographics:
    def test_a_minimal_bundle_yields_the_patients_identity(self):
        index = load_patient_index(a_bundle(a_patient()))
        assert index.patient_id == "3f1a-patient"
        assert index.birth_date == date(1962, 4, 17)
        assert index.sex == "female"

    def test_a_patient_without_demographics_leaves_them_unknown(self):
        resource = {"resourceType": "Patient", "id": "p-bare"}
        index = load_patient_index(a_bundle(resource))
        assert (index.birth_date, index.sex) == (None, None)

    def test_a_bundle_with_no_patient_is_rejected(self):
        with pytest.raises(FhirBundleError, match="exactly one Patient"):
            load_patient_index(a_bundle(a_lab()))

    def test_a_bundle_with_two_patients_is_rejected(self):
        with pytest.raises(FhirBundleError, match="exactly one Patient"):
            load_patient_index(a_bundle(a_patient(), a_patient(id="other")))

    def test_a_bundle_with_no_entries_at_all_is_rejected(self):
        with pytest.raises(FhirBundleError):
            load_patient_index({"resourceType": "Bundle", "type": "transaction"})


class TestObservations:
    def test_a_lab_result_carries_its_code_value_unit_and_date(self):
        index = load_patient_index(a_bundle(a_patient(), a_lab()))
        [obs] = only(index.evidence, "observation")
        assert obs.resource_type == "Observation"
        assert obs.resource_id == "obs-creat"
        assert [(c.system, c.code) for c in obs.codes] == [("LOINC", "2160-0")]
        assert (obs.value, obs.unit) == (1.2, "mg/dL")
        assert obs.date == date(2018, 7, 12)
        assert obs.source == "structured"

    def test_a_lab_result_is_findable_by_the_concept_the_protocol_names(self):
        """The point of the index: a compiled criterion has to be able to reach the row."""
        index = load_patient_index(a_bundle(a_patient(), a_lab()))
        concept = Concept(text="serum creatinine", codes=(Code(system="LOINC", code="2160-0"),))
        assert index.find("observation", concept, None, date(2026, 6, 1))

    def test_an_observation_falls_back_to_issued_when_no_effective_time_is_given(self):
        resource = a_lab(issued="2018-07-12T01:11:59+00:00")
        del resource["effectiveDateTime"]
        index = load_patient_index(a_bundle(a_patient(), resource))
        [obs] = only(index.evidence, "observation")
        assert obs.date == date(2018, 7, 12)

    def test_an_unrecognised_coding_system_is_dropped_rather_than_renamed(self):
        resource = a_lab(
            code={
                "text": "Creatinine",
                "coding": [
                    {"system": "http://example.org/local-lab-dictionary", "code": "CR"},
                    {"system": LOINC, "code": "2160-0"},
                ],
            }
        )
        index = load_patient_index(a_bundle(a_patient(), resource))
        [obs] = only(index.evidence, "observation")
        assert [(c.system, c.code) for c in obs.codes] == [("LOINC", "2160-0")]

    def test_an_observation_with_no_recognised_coding_is_still_indexed(self):
        """Losing the codes must not lose the row: the display still supports a text match."""
        resource = a_lab(
            code={"text": "Creatinine", "coding": [{"system": "http://example.org/x", "code": "C"}]}
        )
        index = load_patient_index(a_bundle(a_patient(), resource))
        [obs] = only(index.evidence, "observation")
        assert obs.codes == ()
        assert obs.display == "Creatinine"

    def test_a_coding_without_a_code_is_dropped(self):
        resource = a_lab(code={"text": "Creatinine", "coding": [{"system": LOINC, "display": "C"}]})
        index = load_patient_index(a_bundle(a_patient(), resource))
        [obs] = only(index.evidence, "observation")
        assert obs.codes == ()

    def test_a_non_numeric_value_is_left_unset_rather_than_coerced(self):
        resource = a_lab(valueQuantity={"value": "not a number", "unit": "mg/dL"})
        index = load_patient_index(a_bundle(a_patient(), resource))
        [obs] = only(index.evidence, "observation")
        assert obs.value is None


class TestComponentObservations:
    """Blood pressure in Synthea is only reachable through `component`."""

    BP = {
        "resourceType": "Observation",
        "id": "obs-bp",
        "effectiveDateTime": "2020-05-06T14:10:00+00:00",
        "code": {
            "text": "Blood pressure panel",
            "coding": [{"system": LOINC, "code": "85354-9"}],
        },
        "component": [
            {
                "code": {"coding": [{"system": LOINC, "code": "8462-4", "display": "Diastolic"}]},
                "valueQuantity": {"value": 82.0, "unit": "mm[Hg]"},
            },
            {
                "code": {"coding": [{"system": LOINC, "code": "8480-6", "display": "Systolic"}]},
                "valueQuantity": {"value": 128.0, "unit": "mm[Hg]"},
            },
        ],
    }

    def test_each_component_becomes_its_own_row_with_its_own_code_and_value(self):
        index = load_patient_index(a_bundle(a_patient(), self.BP))
        rows = only(index.evidence, "observation")
        assert len(rows) == 2
        assert {c.code for row in rows for c in row.codes} == {"8462-4", "8480-6"}
        assert {row.value for row in rows} == {82.0, 128.0}
        assert {row.unit for row in rows} == {"mm[Hg]"}

    def test_every_component_inherits_the_observations_date_and_identity(self):
        index = load_patient_index(a_bundle(a_patient(), self.BP))
        rows = only(index.evidence, "observation")
        assert {row.date for row in rows} == {date(2020, 5, 6)}
        assert {row.resource_id for row in rows} == {"obs-bp"}
        assert {row.fhir_path for row in rows} == {"Bundle.entry[1].resource"}

    def test_the_valueless_panel_itself_is_not_indexed(self):
        """A value-free panel row would outrank its own components as 'the latest result'."""
        index = load_patient_index(a_bundle(a_patient(), self.BP))
        assert all(row.value is not None for row in only(index.evidence, "observation"))

    def test_a_panel_that_also_carries_its_own_value_keeps_it(self):
        panel = {**self.BP, "valueQuantity": {"value": 96.0, "unit": "mm[Hg]"}}
        index = load_patient_index(a_bundle(a_patient(), panel))
        rows = only(index.evidence, "observation")
        assert len(rows) == 3
        assert 96.0 in {row.value for row in rows}


class TestConditions:
    def test_a_condition_uses_its_onset_date(self):
        index = load_patient_index(a_bundle(a_patient(), a_condition()))
        [cond] = only(index.evidence, "condition")
        assert cond.date == date(2019, 2, 3)
        assert [(c.system, c.code) for c in cond.codes] == [("SNOMED", "22298006")]

    def test_a_condition_falls_back_to_the_recorded_date(self):
        resource = a_condition(recordedDate="2019-02-05")
        del resource["onsetDateTime"]
        index = load_patient_index(a_bundle(a_patient(), resource))
        [cond] = only(index.evidence, "condition")
        assert cond.date == date(2019, 2, 5)

    def test_a_refuted_condition_is_excluded(self):
        resource = a_condition(
            verificationStatus={"coding": [{"system": VER_STATUS, "code": "refuted"}]}
        )
        index = load_patient_index(a_bundle(a_patient(), resource))
        assert only(index.evidence, "condition") == []

    def test_a_condition_entered_in_error_is_excluded(self):
        resource = a_condition(
            verificationStatus={"coding": [{"system": VER_STATUS, "code": "entered-in-error"}]}
        )
        index = load_patient_index(a_bundle(a_patient(), resource))
        assert only(index.evidence, "condition") == []

    def test_a_confirmed_condition_is_kept(self):
        resource = a_condition(
            verificationStatus={"coding": [{"system": VER_STATUS, "code": "confirmed"}]},
            clinicalStatus={"coding": [{"code": "active"}]},
        )
        index = load_patient_index(a_bundle(a_patient(), resource))
        assert len(only(index.evidence, "condition")) == 1

    def test_the_recorded_statuses_survive_into_the_display(self):
        resource = a_condition(
            verificationStatus={"coding": [{"system": VER_STATUS, "code": "confirmed"}]},
            clinicalStatus={"coding": [{"code": "resolved"}]},
        )
        index = load_patient_index(a_bundle(a_patient(), resource))
        [cond] = only(index.evidence, "condition")
        assert "Myocardial infarction" in cond.display
        assert "resolved" in cond.display and "confirmed" in cond.display

    def test_a_condition_without_a_verification_status_is_kept(self):
        """Synthea rarely writes one, and absence of refutation is not refutation."""
        index = load_patient_index(a_bundle(a_patient(), a_condition()))
        assert len(only(index.evidence, "condition")) == 1


class TestMedicationsAndProcedures:
    def test_a_medication_request_carries_its_rxnorm_code_and_authored_date(self):
        resource = {
            "resourceType": "MedicationRequest",
            "id": "med-1",
            "status": "active",
            "authoredOn": "2021-03-09T08:15:00+00:00",
            "medicationCodeableConcept": {
                "text": "Lisinopril 10 MG Oral Tablet",
                "coding": [{"system": RXNORM, "code": "314076"}],
            },
        }
        index = load_patient_index(a_bundle(a_patient(), resource))
        [med] = only(index.evidence, "medication")
        assert med.resource_type == "MedicationRequest"
        assert [(c.system, c.code) for c in med.codes] == [("RxNorm", "314076")]
        assert med.date == date(2021, 3, 9)
        assert med.display == "Lisinopril 10 MG Oral Tablet"

    def test_a_procedure_uses_its_performed_date(self):
        resource = {
            "resourceType": "Procedure",
            "id": "proc-1",
            "performedDateTime": "2017-11-02T10:00:00+00:00",
            "code": {"coding": [{"system": SNOMED, "code": "232717009", "display": "CABG"}]},
        }
        index = load_patient_index(a_bundle(a_patient(), resource))
        [proc] = only(index.evidence, "procedure")
        assert proc.date == date(2017, 11, 2)
        assert proc.display == "CABG"

    def test_a_procedure_falls_back_to_the_start_of_its_performed_period(self):
        resource = {
            "resourceType": "Procedure",
            "id": "proc-2",
            "performedPeriod": {"start": "2017-11-02T10:00:00+00:00", "end": "2017-11-02T12:00Z"},
            "code": {"coding": [{"system": SNOMED, "code": "232717009"}]},
        }
        index = load_patient_index(a_bundle(a_patient(), resource))
        [proc] = only(index.evidence, "procedure")
        assert proc.date == date(2017, 11, 2)


class TestEncounters:
    def test_an_encounter_carries_the_start_of_its_period(self):
        index = load_patient_index(a_bundle(a_patient(), an_encounter()))
        [enc] = only(index.evidence, "encounter")
        assert enc.date == date(2020, 5, 6)
        assert enc.resource_type == "Encounter"
        assert [(c.system, c.code) for c in enc.codes] == [("SNOMED", "162673000")]
        assert enc.display == "General examination of patient"

    def test_encounters_are_what_lets_the_evaluator_call_a_window_covered(self):
        index = load_patient_index(a_bundle(a_patient(), an_encounter()))
        assert index.has_documented_activity(None, date(2020, 6, 1))

    def test_an_untyped_encounter_falls_back_to_its_class(self):
        resource = an_encounter()
        del resource["type"]
        index = load_patient_index(a_bundle(a_patient(), resource))
        [enc] = only(index.evidence, "encounter")
        assert enc.display == "AMB"

    def test_an_encounter_without_a_period_is_kept_but_undated(self):
        resource = an_encounter()
        del resource["period"]
        index = load_patient_index(a_bundle(a_patient(), resource))
        [enc] = only(index.evidence, "encounter")
        assert enc.date is None


class TestDatesWeCannotTrust:
    def test_a_malformed_date_yields_no_date_rather_than_an_exception(self):
        index = load_patient_index(a_bundle(a_patient(), a_lab(effectiveDateTime="12/07/2018")))
        [obs] = only(index.evidence, "observation")
        assert obs.date is None

    def test_a_partial_date_is_not_rounded_up_to_a_day_we_invented(self):
        index = load_patient_index(a_bundle(a_patient(), a_lab(effectiveDateTime="2018-07")))
        [obs] = only(index.evidence, "observation")
        assert obs.date is None

    def test_a_malformed_birth_date_leaves_the_patient_ageless(self):
        index = load_patient_index(a_bundle(a_patient(birthDate="unknown")))
        assert index.birth_date is None

    def test_a_date_is_read_on_its_own_calendar_rather_than_shifted_to_utc(self):
        resource = a_lab(effectiveDateTime="2018-07-12T23:30:00-05:00")
        index = load_patient_index(a_bundle(a_patient(), resource))
        [obs] = only(index.evidence, "observation")
        assert obs.date == date(2018, 7, 12)


class TestProvenance:
    def test_fhir_paths_match_the_entry_positions_in_the_source_bundle(self):
        bundle = a_bundle(an_encounter(), a_patient(), a_lab(), a_condition())
        index = load_patient_index(bundle)
        by_id = {e.resource_id: e.fhir_path for e in index.evidence}
        assert by_id["enc-1"] == "Bundle.entry[0].resource"
        assert by_id["obs-creat"] == "Bundle.entry[2].resource"
        assert by_id["cond-mi"] == "Bundle.entry[3].resource"

    def test_an_entry_carrying_no_resource_does_not_shift_the_indices(self):
        bundle = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                {"request": {"method": "DELETE", "url": "Observation/gone"}},
                {"resource": a_patient()},
                {"resource": a_lab()},
            ],
        }
        index = load_patient_index(bundle)
        [obs] = only(index.evidence, "observation")
        assert obs.fhir_path == "Bundle.entry[2].resource"

    def test_a_resource_without_an_id_is_named_after_its_position(self):
        resource = a_lab()
        del resource["id"]
        index = load_patient_index(a_bundle(a_patient(), resource))
        [obs] = only(index.evidence, "observation")
        assert obs.resource_id == "entry-1"

    def test_a_patient_without_an_id_is_named_after_its_position(self):
        resource = a_patient()
        del resource["id"]
        index = load_patient_index(a_bundle(resource))
        assert index.patient_id == "entry-0"

    def test_resources_we_do_not_map_are_skipped_without_complaint(self):
        claim = {"resourceType": "Claim", "id": "claim-1", "status": "active"}
        index = load_patient_index(a_bundle(a_patient(), claim, a_lab()))
        assert [e.resource_type for e in index.evidence] == ["Observation"]


def _note(text: str, **overrides: object) -> dict:
    base = {
        "resourceType": "DocumentReference",
        "id": "doc-1",
        "date": "2020-05-06T15:00:00+00:00",
        "content": [
            {
                "attachment": {
                    "contentType": "text/plain; charset=utf-8",
                    "data": base64.b64encode(text.encode("utf-8")).decode("ascii"),
                }
            }
        ],
    }
    return {**base, **overrides}


class TestNarrativeDocuments:
    """DocumentReference has no honest home in `EvidenceKind` yet — see the module docstring."""

    def test_an_attachment_is_decoded_from_base64(self):
        bundle = a_bundle(a_patient(), _note("Chief complaint: exertional chest pain."))
        [decoded] = narrative_notes(bundle)
        assert decoded.text == "Chief complaint: exertional chest pain."
        assert decoded.resource_id == "doc-1"
        assert decoded.fhir_path == "Bundle.entry[1].resource"
        assert decoded.date == date(2020, 5, 6)

    def test_a_document_reference_is_not_indexed_as_clinical_evidence(self):
        bundle = a_bundle(a_patient(), _note("Chief complaint: exertional chest pain."))
        assert load_patient_index(bundle).evidence == []

    def test_an_unreadable_attachment_is_skipped_rather_than_mangled(self):
        note = _note("ignored")
        note["content"][0]["attachment"]["data"] = "%%% not base64 %%%"
        assert narrative_notes(a_bundle(a_patient(), note)) == []

    def test_a_binary_attachment_is_skipped(self):
        note = _note("ignored")
        note["content"][0]["attachment"]["contentType"] = "application/pdf"
        assert narrative_notes(a_bundle(a_patient(), note)) == []

    def test_several_attachments_on_one_document_are_joined_in_order(self):
        note = _note("First paragraph.")
        note["content"].append(
            {
                "attachment": {
                    "contentType": "text/plain",
                    "data": base64.b64encode(b"Second paragraph.").decode("ascii"),
                }
            }
        )
        [decoded] = narrative_notes(a_bundle(a_patient(), note))
        assert decoded.text == "First paragraph.\n\nSecond paragraph."


# Synthea also writes provider and organization bundles into its output directory; they carry no
# Patient and are not charts, so they are not candidates for this test.
_PATIENTS = Path(__file__).resolve().parents[1] / "data" / "patients"
_SYNTHEA_INFRASTRUCTURE = ("hospitalInformation", "practitionerInformation")
_BUNDLE_FILES = (
    [p for p in sorted(_PATIENTS.glob("*.json")) if not p.name.startswith(_SYNTHEA_INFRASTRUCTURE)]
    if _PATIENTS.is_dir()
    else []
)


@pytest.mark.skipif(not _BUNDLE_FILES, reason="no Synthea bundles under data/patients")
def test_a_real_synthea_bundle_produces_a_non_empty_index():
    bundle = json.loads(_BUNDLE_FILES[0].read_text(encoding="utf-8"))
    index = load_patient_index(bundle)

    assert index.patient_id
    assert index.evidence
    assert any(e.kind == "encounter" for e in index.evidence)
    assert any(e.kind == "observation" and e.value is not None for e in index.evidence)

    entries = bundle["entry"]
    for evidence in index.evidence:
        position = int(evidence.fhir_path.removeprefix("Bundle.entry[").removesuffix("].resource"))
        assert entries[position]["resource"]["resourceType"] == evidence.resource_type
