"""Composite criteria.

Real protocols do not hand you one assertion per bullet. "eGFR ≥25 and ≤60", "on an ACE inhibitor
or an ARB", "no myocardial infarction and no stroke within 6 months" are all single bullets holding
several conditions, and refusing to formalise them would push most of a protocol into human review
for no good reason.

Combining them is where three-valued logic earns its keep. An `all_of` whose members are TRUE,
TRUE and UNKNOWN is UNKNOWN — but one whose members are TRUE, FALSE and UNKNOWN is FALSE, because
the false member settles it whatever the unknown turns out to be. This is Kleene's strong logic,
and it is the same rule CQL applies to nulls.
"""

from datetime import date

from caliper.evaluate import evaluate_criterion
from caliper.ir import (
    Code,
    CompositePredicate,
    Concept,
    Criterion,
    DemographicPredicate,
    ObservationPredicate,
    PresencePredicate,
    UnsupportedPredicate,
    max_predicate_depth,
)
from caliper.logic import Verdict
from caliper.record import Evidence, PatientIndex

SCREENING = date(2026, 6, 1)
EGFR = Code(system="LOINC", code="33914-3", display="eGFR")
EGFR_CONCEPT = Concept(text="eGFR", codes=(EGFR,))
ACE = Concept(text="lisinopril", codes=(Code(system="RxNorm", code="29046"),))
ARB = Concept(text="losartan", codes=(Code(system="RxNorm", code="52175"),))


def egfr(value: float) -> Evidence:
    return Evidence(
        kind="observation",
        resource_type="Observation",
        resource_id=f"obs-egfr-{value}",
        display="eGFR",
        fhir_path="Bundle.entry[4].resource",
        codes=(EGFR,),
        value=value,
        unit="mL/min/1.73m2",
        date=date(2026, 5, 2),
    )


def drug(concept: Concept) -> Evidence:
    code = concept.codes[0]
    return Evidence(
        kind="medication",
        resource_type="MedicationRequest",
        resource_id=f"med-{code.code}",
        display=concept.text,
        fhir_path="Bundle.entry[9].resource",
        codes=(code,),
        date=date(2026, 3, 1),
    )


def visit() -> Evidence:
    return Evidence(
        kind="encounter",
        resource_type="Encounter",
        resource_id="enc-1",
        display="visit",
        fhir_path="Bundle.entry[0].resource",
        date=date(2026, 4, 1),
    )


def index(*evidence: Evidence) -> PatientIndex:
    return PatientIndex(
        patient_id="p-1", birth_date=date(1965, 1, 1), sex="male", evidence=list(evidence)
    )


def bound(op: str, value: float) -> ObservationPredicate:
    return ObservationPredicate(concept=EGFR_CONCEPT, op=op, value=value, unit="mL/min/1.73m2")


def on(concept: Concept) -> PresencePredicate:
    return PresencePredicate(type="medication", concept=concept, presence="present")


def criterion(predicate, *, kind: str = "inclusion") -> Criterion:
    return Criterion(id="INC-01", kind=kind, source_quote="quoted", predicate=predicate)


class TestConjunction:
    def test_all_members_met_makes_the_composite_met(self):
        c = criterion(
            CompositePredicate(type="all_of", operands=[bound(">=", 25), bound("<=", 60)])
        )
        assert evaluate_criterion(c, index(egfr(42)), SCREENING).verdict is Verdict.MET

    def test_one_member_not_met_makes_the_composite_not_met(self):
        c = criterion(
            CompositePredicate(type="all_of", operands=[bound(">=", 25), bound("<=", 60)])
        )
        assert evaluate_criterion(c, index(egfr(88)), SCREENING).verdict is Verdict.NOT_MET

    def test_an_unresolved_member_leaves_the_conjunction_unresolved(self):
        c = criterion(CompositePredicate(type="all_of", operands=[bound(">=", 25), on(ACE)]))
        assert evaluate_criterion(c, index(egfr(42)), SCREENING).verdict is Verdict.UNKNOWN

    def test_a_false_member_settles_a_conjunction_even_alongside_an_unknown_one(self):
        """FALSE dominates UNKNOWN: no value of the unknown member could rescue this."""
        c = criterion(CompositePredicate(type="all_of", operands=[bound(">=", 90), on(ACE)]))
        assert evaluate_criterion(c, index(egfr(42)), SCREENING).verdict is Verdict.NOT_MET


class TestDisjunction:
    def test_one_member_met_is_enough(self):
        c = criterion(CompositePredicate(type="any_of", operands=[on(ACE), on(ARB)]))
        assert evaluate_criterion(c, index(drug(ARB), visit()), SCREENING).verdict is Verdict.MET

    def test_a_true_member_settles_a_disjunction_even_alongside_an_unknown_one(self):
        c = criterion(CompositePredicate(type="any_of", operands=[on(ACE), on(ARB)]))
        result = evaluate_criterion(c, index(drug(ACE)), SCREENING)
        assert result.verdict is Verdict.MET

    def test_all_members_not_met_makes_the_disjunction_not_met(self):
        c = criterion(CompositePredicate(type="any_of", operands=[on(ACE), on(ARB)]))
        assert evaluate_criterion(c, index(visit()), SCREENING).verdict is Verdict.NOT_MET

    def test_no_true_member_but_an_unresolved_one_stays_unresolved(self):
        c = criterion(CompositePredicate(type="any_of", operands=[on(ACE), bound(">=", 25)]))
        assert evaluate_criterion(c, index(visit()), SCREENING).verdict is Verdict.UNKNOWN


class TestNegation:
    def test_negation_flips_a_resolved_member(self):
        c = criterion(CompositePredicate(type="not", operands=[bound(">=", 90)]))
        assert evaluate_criterion(c, index(egfr(42)), SCREENING).verdict is Verdict.MET

    def test_negation_of_an_unresolved_member_stays_unresolved(self):
        c = criterion(CompositePredicate(type="not", operands=[bound(">=", 90)]))
        assert evaluate_criterion(c, index(visit()), SCREENING).verdict is Verdict.UNKNOWN


class TestEvidenceAndAbstention:
    def test_the_composite_reports_the_evidence_its_members_used(self):
        c = criterion(
            CompositePredicate(type="all_of", operands=[bound(">=", 25), bound("<=", 60)])
        )
        result = evaluate_criterion(c, index(egfr(42)), SCREENING)
        assert {e.resource_id for e in result.evidence} == {"obs-egfr-42"}

    def test_an_unresolved_composite_hands_back_the_member_that_blocked_it(self):
        c = criterion(CompositePredicate(type="all_of", operands=[bound(">=", 25), on(ACE)]))
        result = evaluate_criterion(c, index(egfr(42)), SCREENING)
        assert result.resolution_hint is not None
        assert "lisinopril" in result.resolution_hint.missing

    def test_an_unsupported_member_makes_the_whole_composite_need_a_human(self):
        c = criterion(
            CompositePredicate(
                type="all_of",
                operands=[bound(">=", 25), UnsupportedPredicate(reason="investigator judgement")],
            )
        )
        result = evaluate_criterion(c, index(egfr(42)), SCREENING)
        assert result.verdict is Verdict.UNKNOWN
        assert "investigator judgement" in result.resolution_hint.missing


class TestNesting:
    def test_composites_may_contain_composites(self):
        inner = CompositePredicate(type="any_of", operands=[on(ACE), on(ARB)])
        outer = CompositePredicate(type="all_of", operands=[bound(">=", 25), inner])
        result = evaluate_criterion(criterion(outer), index(egfr(42), drug(ARB)), SCREENING)
        assert result.verdict is Verdict.MET

    def test_depth_is_measurable_so_a_wire_schema_can_bound_it(self):
        atom = bound(">=", 25)
        assert max_predicate_depth(atom) == 0
        assert max_predicate_depth(CompositePredicate(type="not", operands=[atom])) == 1
        nested = CompositePredicate(
            type="all_of", operands=[atom, CompositePredicate(type="not", operands=[atom])]
        )
        assert max_predicate_depth(nested) == 2


class TestConstruction:
    def test_a_conjunction_needs_at_least_two_members(self):
        import pytest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CompositePredicate(type="all_of", operands=[bound(">=", 25)])

    def test_a_negation_takes_exactly_one_member(self):
        import pytest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CompositePredicate(type="not", operands=[bound(">=", 25), bound("<=", 60)])

    def test_a_demographic_bound_composes_like_anything_else(self):
        c = criterion(
            CompositePredicate(
                type="all_of",
                operands=[
                    DemographicPredicate(field="age", op=">=", value=18, unit="years"),
                    bound(">=", 25),
                ],
            )
        )
        assert evaluate_criterion(c, index(egfr(42)), SCREENING).verdict is Verdict.MET
