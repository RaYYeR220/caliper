"""The compiled criteria IR is the contract between the language model and the evaluator.

Everything the model produces must survive these checks before any patient is touched.
"""

import pytest
from pydantic import ValidationError

from caliper.ir import (
    Code,
    Concept,
    CriteriaSet,
    Criterion,
    DemographicPredicate,
    ObservationPredicate,
    PresencePredicate,
    TemporalWindow,
    UnsupportedPredicate,
    normalise_quote_text,
    quote_fidelity_problems,
)

CREATININE = Concept(text="serum creatinine", codes=[Code(system="LOINC", code="2160-0")])


def a_criterion(**overrides) -> Criterion:
    defaults = dict(
        id="INC-01",
        kind="inclusion",
        source_quote="Serum creatinine <= 1.5 mg/dL",
        predicate=ObservationPredicate(
            concept=CREATININE, op="<=", value=1.5, unit="mg/dL"
        ),
    )
    return Criterion(**{**defaults, **overrides})


class TestObservationPredicate:
    def test_a_numeric_comparison_requires_a_unit(self):
        with pytest.raises(ValidationError):
            ObservationPredicate(concept=CREATININE, op="<=", value=1.5, unit="")

    def test_a_unitless_score_is_expressed_with_the_ucum_unity_unit(self):
        p = ObservationPredicate(concept=CREATININE, op="<=", value=2, unit="1")
        assert p.unit == "1"

    def test_between_requires_an_upper_bound(self):
        with pytest.raises(ValidationError):
            ObservationPredicate(concept=CREATININE, op="between", value=1.0, unit="mg/dL")

    def test_between_accepts_two_bounds(self):
        p = ObservationPredicate(
            concept=CREATININE, op="between", value=1.0, value_high=2.0, unit="mg/dL"
        )
        assert (p.value, p.value_high) == (1.0, 2.0)

    def test_the_lower_bound_of_a_range_must_not_exceed_the_upper_bound(self):
        with pytest.raises(ValidationError):
            ObservationPredicate(
                concept=CREATININE, op="between", value=3.0, value_high=2.0, unit="mg/dL"
            )


class TestTemporalWindow:
    def test_a_relative_window_needs_an_amount_and_a_unit(self):
        with pytest.raises(ValidationError):
            TemporalWindow(relation="within")

    def test_ever_needs_no_amount(self):
        assert TemporalWindow(relation="ever").amount is None

    def test_a_relative_window_carries_its_span(self):
        w = TemporalWindow(relation="within", amount=6, unit="months")
        assert (w.amount, w.unit) == (6, "months")


class TestCriterion:
    def test_kind_is_restricted_to_inclusion_and_exclusion(self):
        with pytest.raises(ValidationError):
            a_criterion(kind="preferred")

    def test_the_source_quote_may_not_be_empty(self):
        with pytest.raises(ValidationError):
            a_criterion(source_quote="   ")

    def test_a_criterion_the_compiler_could_not_formalise_is_marked_unsupported(self):
        c = a_criterion(
            predicate=UnsupportedPredicate(reason="requires investigator judgement")
        )
        assert c.predicate.type == "unsupported"

    def test_an_unsupported_predicate_must_say_why(self):
        with pytest.raises(ValidationError):
            UnsupportedPredicate(reason="")


class TestCriteriaSet:
    def test_criterion_ids_must_be_unique(self):
        with pytest.raises(ValidationError):
            CriteriaSet(
                nct_id="NCT00000000",
                source_text="x",
                criteria=[a_criterion(), a_criterion()],
            )

    def test_it_reports_how_many_criteria_could_not_be_formalised(self):
        cs = CriteriaSet(
            nct_id="NCT00000000",
            source_text="x",
            criteria=[
                a_criterion(id="INC-01"),
                a_criterion(
                    id="INC-02", predicate=UnsupportedPredicate(reason="investigator judgement")
                ),
            ],
        )
        assert cs.unsupported_count == 1

    def test_it_fingerprints_the_source_text_so_a_protocol_edit_invalidates_the_compile(self):
        cs = CriteriaSet(nct_id="NCT00000000", source_text="Inclusion Criteria:\n- Age >= 18")
        assert len(cs.source_text_sha256) == 64
        other = CriteriaSet(nct_id="NCT00000000", source_text="Inclusion Criteria:\n- Age >= 19")
        assert cs.source_text_sha256 != other.source_text_sha256


class TestQuoteFidelity:
    SOURCE = (
        "Inclusion Criteria:\n"
        "- Age 18 years or older\n"
        "- Serum creatinine <= 1.5 mg/dL\n"
        "Exclusion Criteria:\n"
        "- Myocardial infarction within 6 months\n"
    )

    def test_a_quote_lifted_verbatim_from_the_protocol_passes(self):
        cs = CriteriaSet(
            nct_id="NCT1",
            source_text=self.SOURCE,
            criteria=[a_criterion(source_quote="Serum creatinine <= 1.5 mg/dL")],
        )
        assert quote_fidelity_problems(cs) == []

    def test_a_quote_the_model_reworded_is_caught(self):
        cs = CriteriaSet(
            nct_id="NCT1",
            source_text=self.SOURCE,
            criteria=[a_criterion(source_quote="Creatinine must be at most 1.5")],
        )
        problems = quote_fidelity_problems(cs)
        assert len(problems) == 1
        assert problems[0].criterion_id == "INC-01"

    def test_whitespace_and_case_differences_are_forgiven(self):
        cs = CriteriaSet(
            nct_id="NCT1",
            source_text=self.SOURCE,
            criteria=[a_criterion(source_quote="serum   creatinine <=  1.5 MG/DL")],
        )
        assert quote_fidelity_problems(cs) == []


class TestConceptsOf:
    """One walk over a predicate's concepts, shared rather than copied.

    `uiexport` had a second copy of this, and said so in its own docstring. Two walks over a
    recursive structure is two chances to handle a nesting depth differently, and the two answers
    would have been the terminology count on the review screen and the resolver's lookup budget.
    """

    def test_it_descends_into_nested_composites(self):
        from caliper.ir import CompositePredicate, concepts_in, concepts_of

        inner = CompositePredicate(
            type="any_of",
            operands=[
                PresencePredicate(
                    type="condition", concept=Concept(text="COPD"), presence="present"
                ),
                PresencePredicate(
                    type="condition", concept=Concept(text="asthma"), presence="present"
                ),
            ],
        )
        outer = CompositePredicate(
            type="all_of",
            operands=[
                inner,
                ObservationPredicate(concept=CREATININE, op="<=", value=1.5, unit="mg/dL"),
            ],
        )

        assert [c.text for c in concepts_of(outer)] == ["COPD", "asthma", "serum creatinine"]

        cs = CriteriaSet(
            nct_id="NCT1",
            source_text="Inclusion Criteria:\n- anything\n",
            criteria=[a_criterion(source_quote="anything", predicate=outer)],
        )
        assert [c.text for c in concepts_in(cs)] == ["COPD", "asthma", "serum creatinine"]

    def test_the_export_uses_this_walk_rather_than_its_own(self):
        from caliper import uiexport
        from caliper.ir import concepts_of

        assert uiexport.concepts_of is concepts_of


class TestNormaliseQuoteText:
    """The single fold every quote comparison in the codebase goes through.

    There were three of these, and they disagreed. `ir` folded with `lower`, the critic and the
    compiler with `casefold`, which means the gate that downgrades a criterion to
    `UnsupportedPredicate` and the coverage report that says which spans were claimed were answering
    "is this the same text" differently about the same protocol. The German ß is the shortest case
    where the two differ, and it is here so that a future edit cannot quietly separate them again.
    """

    def test_a_fold_that_changes_length_is_still_a_fold(self):
        assert "STRASSE".lower() != "Straße".lower()
        assert normalise_quote_text("STRASSE") == normalise_quote_text("Straße")

    def test_a_quote_the_protocol_capitalised_differently_is_not_a_paraphrase(self):
        cs = CriteriaSet(
            nct_id="NCT1",
            source_text="Inclusion Criteria:\n- Resident of MASSENSTRASSE district\n",
            criteria=[a_criterion(source_quote="Resident of Massenstraße district")],
        )
        assert quote_fidelity_problems(cs) == []

    def test_every_run_of_whitespace_collapses_to_one_space(self):
        assert normalise_quote_text("  a\n\t b \r\n") == "a b"

    def test_the_critic_folds_quotes_exactly_the_way_this_module_does(self):
        """Not "mirrors", which was the old docstring's word for two functions that disagreed."""
        from caliper.agents import critic

        assert critic.normalise_quote_text is normalise_quote_text


class TestPresenceAndDemographics:
    def test_a_condition_can_be_required_absent_within_a_window(self):
        p = PresencePredicate(
            type="condition",
            concept=Concept(text="myocardial infarction"),
            presence="absent",
            window=TemporalWindow(relation="within", amount=6, unit="months"),
        )
        assert p.presence == "absent"

    def test_an_age_bound_is_a_demographic_predicate(self):
        p = DemographicPredicate(field="age", op=">=", value=18, unit="years")
        assert p.field == "age"

    def test_sex_is_compared_by_equality_not_by_magnitude(self):
        with pytest.raises(ValidationError):
            DemographicPredicate(field="sex", op=">=", value="female")
