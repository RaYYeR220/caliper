"""Matching evidence to a concept.

The rules here decide what a criterion is allowed to see. The one that matters most is the
narrative guard: a discharge summary containing the phrase "myocardial infarction" is not evidence
that the patient had one — the sentence around it may be a denial, or about their father. Narrative
rows therefore resolve a criterion only once something has coded them, and the code is what
matches, not the prose.
"""

from datetime import date

from caliper.ir import Code, Concept
from caliper.record import Evidence, PatientIndex

SCREENING = date(2026, 6, 1)
MI_CODE = Code(system="SNOMED", code="22298006", display="Myocardial infarction")
MI = Concept(text="myocardial infarction", codes=(MI_CODE,))
UNCODED_MI = Concept(text="myocardial infarction")


def row(**overrides) -> Evidence:
    base = dict(
        kind="condition",
        resource_type="Condition",
        resource_id="c-1",
        display="Myocardial infarction",
        fhir_path="Bundle.entry[2].resource",
        date=date(2026, 1, 1),
    )
    return Evidence(**{**base, **overrides})


def index(*evidence: Evidence) -> PatientIndex:
    return PatientIndex(
        patient_id="p-1", birth_date=date(1970, 1, 1), sex="female", evidence=list(evidence)
    )


class TestCodedMatching:
    def test_a_shared_code_matches(self):
        record = index(row(codes=(MI_CODE,)))
        assert len(record.find("condition", MI, None, SCREENING)) == 1

    def test_a_different_code_does_not_match_even_with_the_same_wording(self):
        other = Code(system="SNOMED", code="230690007", display="Myocardial infarction")
        record = index(row(codes=(other,)))
        assert record.find("condition", MI, None, SCREENING) == []

    def test_a_concept_without_codes_falls_back_to_the_recorded_wording(self):
        record = index(row(codes=()))
        assert len(record.find("condition", UNCODED_MI, None, SCREENING)) == 1


class TestNarrativeGuard:
    def test_a_note_derived_row_needs_a_code_to_resolve_anything(self):
        """Substring matching on prose is how family history becomes a diagnosis."""
        record = index(row(codes=(), source="narrative", narrative_quote="father had an MI"))
        assert record.find("condition", UNCODED_MI, None, SCREENING) == []

    def test_a_coded_note_derived_row_does_match(self):
        record = index(
            row(codes=(MI_CODE,), source="narrative", narrative_quote="STEMI in March 2026")
        )
        assert len(record.find("condition", MI, None, SCREENING)) == 1

    def test_raw_notes_are_never_returned_as_clinical_evidence(self):
        record = index(
            Evidence(
                kind="note",
                resource_type="DocumentReference",
                resource_id="doc-1",
                display="Discharge summary",
                fhir_path="Bundle.entry[8].resource",
                source="narrative",
                narrative_quote="No history of myocardial infarction.",
                date=date(2026, 2, 1),
            )
        )
        assert record.find("condition", UNCODED_MI, None, SCREENING) == []

    def test_notes_are_still_retrievable_as_notes(self):
        note = Evidence(
            kind="note",
            resource_type="DocumentReference",
            resource_id="doc-1",
            display="Discharge summary",
            fhir_path="Bundle.entry[8].resource",
            source="narrative",
            narrative_quote="No history of myocardial infarction.",
            date=date(2026, 2, 1),
        )
        assert index(note).notes() == [note]


class TestCoverage:
    def test_a_note_does_not_count_as_a_documented_visit(self):
        note = Evidence(
            kind="note",
            resource_type="DocumentReference",
            resource_id="doc-1",
            display="Discharge summary",
            fhir_path="Bundle.entry[8].resource",
            date=date(2026, 5, 1),
        )
        assert index(note).has_documented_activity(None, SCREENING) is False
