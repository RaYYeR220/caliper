"""The prose linter.

A model writes the one-line rationale a coordinator reads. That sentence is the only part of the
packet a model authors freely, so it is the only part that can drift from the record. The linter
checks every number and date in it against the values that criterion actually resolved from — not
against the packet as a whole, which would let a threshold from one criterion vouch for a sentence
about another.

It proves binding, not meaning. A sentence can pass with every number correct and still describe
the wrong relationship; that limitation is real and is stated in the report.
"""

from datetime import date

from caliper.evaluate import CriterionResult
from caliper.ir import Code, Concept, Criterion, ObservationPredicate, TemporalWindow
from caliper.logic import Verdict
from caliper.prose import ProseViolation, check_rationale
from caliper.record import Evidence

CREATININE = Code(system="LOINC", code="2160-0", display="Creatinine")
CONCEPT = Concept(text="serum creatinine", codes=(CREATININE,))

CRITERION = Criterion(
    id="INC-03",
    kind="inclusion",
    source_quote="Serum creatinine <= 1.5 mg/dL within 6 months",
    predicate=ObservationPredicate(
        concept=CONCEPT,
        op="<=",
        value=1.5,
        unit="mg/dL",
        window=TemporalWindow(relation="within", amount=6, unit="months"),
    ),
)

EVIDENCE = Evidence(
    kind="observation",
    resource_type="Observation",
    resource_id="obs-1",
    display="Creatinine",
    fhir_path="Bundle.entry[7].resource",
    codes=(CREATININE,),
    value=1.2,
    unit="mg/dL",
    date=date(2026, 5, 14),
)

RESULT = CriterionResult(
    criterion_id="INC-03",
    kind="inclusion",
    verdict=Verdict.MET,
    rationale="1.2 mg/dL on 2026-05-14 against <= 1.5 mg/dL",
    evidence=(EVIDENCE,),
)


class TestBoundValues:
    def test_a_sentence_using_only_recorded_values_passes(self):
        text = "Creatinine was 1.2 mg/dL on 2026-05-14, within the 1.5 mg/dL ceiling."
        assert check_rationale(text, CRITERION, RESULT) == []

    def test_a_threshold_quoted_from_the_protocol_passes(self):
        text = "The protocol allows up to 1.5 mg/dL within 6 months of screening."
        assert check_rationale(text, CRITERION, RESULT) == []

    def test_a_value_rounded_for_readability_still_counts_as_bound(self):
        result = CriterionResult(
            criterion_id="INC-03",
            kind="inclusion",
            verdict=Verdict.MET,
            rationale="1.199 mg/dL",
            evidence=(Evidence(**{**EVIDENCE.__dict__, "value": 1.199}),),
        )
        assert check_rationale("Creatinine was 1.2 mg/dL.", CRITERION, result) == []

    def test_a_sentence_with_no_numbers_at_all_passes(self):
        assert check_rationale("No creatinine result is on file.", CRITERION, RESULT) == []


class TestUnboundValues:
    def test_an_invented_number_is_reported(self):
        text = "Creatinine was 0.9 mg/dL, comfortably under the ceiling."
        violations = check_rationale(text, CRITERION, RESULT)
        assert [v.token for v in violations] == ["0.9"]
        assert violations[0].kind == "unbound_number"

    def test_an_invented_date_is_reported(self):
        text = "Creatinine was 1.2 mg/dL on 2026-01-02."
        violations = check_rationale(text, CRITERION, RESULT)
        assert [v.token for v in violations] == ["2026-01-02"]
        assert violations[0].kind == "unbound_date"

    def test_the_violation_names_the_criterion_it_came_from(self):
        violations = check_rationale("It was 42 mg/dL.", CRITERION, RESULT)
        assert violations[0].criterion_id == "INC-03"

    def test_a_number_belonging_to_a_different_criterion_does_not_vouch_for_this_one(self):
        """Slot binding is the point: membership in the packet is not membership in the sentence."""
        text = "Creatinine was 1.2 mg/dL, and the patient is 64 years old."
        violations = check_rationale(text, CRITERION, RESULT)
        assert [v.token for v in violations] == ["64"]

    def test_every_unbound_token_is_reported_not_just_the_first(self):
        text = "Creatinine was 0.9 mg/dL on 2020-01-01."
        assert len(check_rationale(text, CRITERION, RESULT)) == 2


class TestTokenExtraction:
    def test_digits_inside_an_allowed_date_are_not_treated_as_loose_numbers(self):
        text = "Measured 2026-05-14."
        assert check_rationale(text, CRITERION, RESULT) == []

    def test_a_loinc_code_in_the_sentence_is_bound_by_the_concept(self):
        text = "Resolved from LOINC 2160-0."
        assert check_rationale(text, CRITERION, RESULT) == []

    def test_a_fhir_pointer_is_not_mistaken_for_a_claim(self):
        text = "See Bundle.entry[7].resource for the source."
        assert check_rationale(text, CRITERION, RESULT) == []

    def test_a_hyphenated_range_is_not_waved_through_as_if_it_were_a_code(self):
        """Only the codes this criterion actually resolved through are exempt."""
        text = "Acceptable range is 18-85 mg/dL."
        assert {v.token for v in check_rationale(text, CRITERION, RESULT)} == {"18", "85"}


class TestViolationShape:
    def test_a_violation_carries_enough_to_show_the_reader_where_it_is(self):
        violations = check_rationale("It was 42 mg/dL.", CRITERION, RESULT)
        v = violations[0]
        assert isinstance(v, ProseViolation)
        assert v.sentence == "It was 42 mg/dL."
        assert "42" in v.message


class TestRoundingIsNotALoophole:
    """A threshold must not vouch for a number it merely rounds to."""

    def test_a_threshold_does_not_license_the_integer_it_rounds_to(self):
        text = "Neither of the 2 requested results is on file."
        violations = check_rationale(text, CRITERION, RESULT)
        assert [v.token for v in violations] == ["2"]

    def test_rounding_to_a_decimal_place_is_still_allowed(self):
        result = CriterionResult(
            criterion_id="INC-03",
            kind="inclusion",
            verdict=Verdict.MET,
            rationale="1.199 mg/dL",
            evidence=(Evidence(**{**EVIDENCE.__dict__, "value": 1.199}),),
        )
        assert check_rationale("Creatinine was 1.2 mg/dL.", CRITERION, result) == []

    def test_an_exact_integer_is_bound_as_it_always_was(self):
        result = CriterionResult(
            criterion_id="INC-03",
            kind="inclusion",
            verdict=Verdict.MET,
            rationale="6 months",
            evidence=(),
        )
        assert check_rationale("Measured within 6 months.", CRITERION, result) == []


class TestDatesDoNotLeakIntoTheNumbers:
    def test_the_year_of_an_evidence_date_is_not_a_permitted_value(self):
        """2026-05-14 in the rationale must not license the number 2026 in the sentence."""
        violations = check_rationale("The value was 2026 mg/dL.", CRITERION, RESULT)
        assert [v.token for v in violations] == ["2026"]

    def test_the_date_itself_still_passes(self):
        assert check_rationale("Measured on 2026-05-14.", CRITERION, RESULT) == []
