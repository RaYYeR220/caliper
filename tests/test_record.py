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


class TestTheFuture:
    """A screening decided on 1 June cannot use a result from August."""

    def test_evidence_dated_after_the_screening_is_never_returned(self):
        record = index(row(codes=(MI_CODE,), date=date(2026, 8, 1)))
        assert record.find("condition", MI, None, SCREENING) == []

    def test_evidence_dated_on_the_screening_day_still_counts(self):
        record = index(row(codes=(MI_CODE,), date=SCREENING))
        assert len(record.find("condition", MI, None, SCREENING)) == 1

    def test_an_undated_row_is_still_reachable_without_a_window(self):
        record = index(row(codes=(MI_CODE,), date=None))
        assert len(record.find("condition", MI, None, SCREENING)) == 1

    def test_a_future_encounter_does_not_document_the_window(self):
        future = Evidence(
            kind="encounter",
            resource_type="Encounter",
            resource_id="enc-future",
            display="visit",
            fhir_path="Bundle.entry[0].resource",
            date=date(2026, 9, 1),
        )
        assert index(future).has_documented_activity(None, SCREENING) is False


class TestDeath:
    def test_a_patient_who_died_before_screening_is_recorded_as_such(self):
        record = PatientIndex(
            patient_id="p-1",
            birth_date=date(1970, 1, 1),
            sex="female",
            evidence=[],
            deceased=date(2026, 5, 3),
        )
        assert record.died_before(SCREENING) is True

    def test_a_living_patient_is_not(self):
        assert index().died_before(SCREENING) is False

    def test_a_death_after_the_screening_date_does_not_apply_to_it(self):
        record = PatientIndex(
            patient_id="p-1",
            birth_date=date(1970, 1, 1),
            sex="female",
            evidence=[],
            deceased=date(2026, 7, 1),
        )
        assert record.died_before(SCREENING) is False


class TestEmptyDisplays:
    def test_an_unlabelled_row_never_matches_an_uncoded_concept(self):
        """A blank display would otherwise match every concept, since "" is in every string."""
        record = index(row(codes=(), display=""))
        assert record.find("condition", UNCODED_MI, None, SCREENING) == []

    def test_an_unlabelled_row_is_still_reachable_by_its_code(self):
        record = index(row(codes=(MI_CODE,), display=""))
        assert len(record.find("condition", MI, None, SCREENING)) == 1


class TestDeathWithoutADate:
    """FHIR allows deceasedBoolean with no date, and a date must not be invented for it."""

    def undated(self) -> PatientIndex:
        return PatientIndex(
            patient_id="p-1",
            birth_date=date(1970, 1, 1),
            sex="female",
            evidence=[],
            deceased_undated=True,
        )

    def test_a_patient_dead_on_an_unknown_date_is_still_deceased(self):
        assert self.undated().is_deceased() is True

    def test_but_no_date_is_asserted_about_them(self):
        assert self.undated().deceased is None

    def test_they_do_not_pass_a_test_that_needs_a_date(self):
        """`died_before` answers a question about a date, and there is no date to answer it with."""
        assert self.undated().died_before(SCREENING) is False

    def test_a_living_patient_is_neither(self):
        assert index().is_deceased() is False
