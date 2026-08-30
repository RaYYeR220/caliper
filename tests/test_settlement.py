"""Criteria that no chart can ever answer.

Every real protocol contains a criterion like "signed written informed consent" or "planned coronary
procedure after randomisation". These are not gaps in the record. They are things a coordinator
settles at the screening visit, for every patient, and no chart that has ever existed could answer
them.

Treating them as unresolved data made ELIGIBLE unreachable for all ten protocols in the corpus: one
consent criterion and the whole screening abstains. That is not caution, it is a system that does
nothing. So the compiler now says which of the two it is, and only a criterion the *record* was
supposed to answer blocks a verdict.

The safety property is unchanged and worth restating: ELIGIBLE still requires every criterion the
record can decide to be resolved with cited evidence. What it now means is "nothing in this
patient's record rules them out, and here are the N things to confirm when they come in".
"""

from datetime import date

from caliper.evaluate import evaluate_criterion
from caliper.ir import (
    Code,
    Concept,
    CriteriaSet,
    Criterion,
    ObservationPredicate,
    UnsupportedPredicate,
)
from caliper.logic import CriterionVerdict, ScreeningOutcome, Verdict, roll_up
from caliper.record import Evidence, PatientIndex
from caliper.screen import screen

SCREENING = date(2026, 6, 1)
A1C = Code(system="LOINC", code="4548-4", display="Hemoglobin A1c")
A1C_CONCEPT = Concept(text="HbA1c", codes=(A1C,))

SOURCE = (
    "Inclusion Criteria:\n"
    "- HbA1c >= 7%\n"
    "- Signed written informed consent\n"
    "Exclusion Criteria:\n"
    "- Adequate organ function\n"
)


def criterion(predicate, cid="INC-01", kind="inclusion", quote="HbA1c >= 7%"):
    return Criterion(id=cid, kind=kind, source_quote=quote, predicate=predicate)


LAB = criterion(ObservationPredicate(concept=A1C_CONCEPT, op=">=", value=7.0, unit="%"))
CONSENT = criterion(
    UnsupportedPredicate(
        reason="settled with the patient in person", settlement="at_visit"
    ),
    cid="INC-02",
    quote="Signed written informed consent",
)
VAGUE = criterion(
    UnsupportedPredicate(reason="no threshold is stated"),
    cid="EXC-01",
    kind="exclusion",
    quote="Adequate organ function",
)


def patient(a1c: float | None = 8.1) -> PatientIndex:
    evidence = [
        Evidence(
            kind="encounter",
            resource_type="Encounter",
            resource_id="enc-1",
            display="visit",
            fhir_path="Bundle.entry[0].resource",
            date=date(2026, 4, 1),
        )
    ]
    if a1c is not None:
        evidence.append(
            Evidence(
                kind="observation",
                resource_type="Observation",
                resource_id="obs-1",
                display="Hemoglobin A1c",
                fhir_path="Bundle.entry[2].resource",
                codes=(A1C,),
                value=a1c,
                unit="%",
                date=date(2026, 5, 1),
            )
        )
    return PatientIndex(
        patient_id="p-1", birth_date=date(1970, 1, 1), sex="female", evidence=evidence
    )


def criteria(*items):
    return CriteriaSet(nct_id="NCT1", source_text=SOURCE, criteria=list(items))


class TestTheDistinction:
    def test_the_default_is_the_conservative_one(self):
        """A compiler that says nothing about settlement must not thereby unblock a verdict."""
        assert UnsupportedPredicate(reason="x").settlement == "from_data"

    def test_a_criterion_settled_at_the_visit_says_so(self):
        assert CONSENT.predicate.settlement == "at_visit"

    def test_both_kinds_still_evaluate_to_unknown(self):
        for c in (CONSENT, VAGUE):
            assert evaluate_criterion(c, patient(), SCREENING).verdict is Verdict.UNKNOWN

    def test_only_the_data_kind_blocks(self):
        assert evaluate_criterion(CONSENT, patient(), SCREENING).blocking is False
        assert evaluate_criterion(VAGUE, patient(), SCREENING).blocking is True

    def test_an_ordinary_unresolved_criterion_blocks(self):
        result = evaluate_criterion(LAB, patient(a1c=None), SCREENING)
        assert result.verdict is Verdict.UNKNOWN
        assert result.blocking is True


class TestTheRollup:
    def test_a_visit_criterion_does_not_stop_a_verdict(self):
        rollup = roll_up(
            [
                CriterionVerdict("INC-01", "inclusion", Verdict.MET),
                CriterionVerdict("INC-02", "inclusion", Verdict.UNKNOWN, blocking=False),
            ]
        )
        assert rollup.decision is ScreeningOutcome.ELIGIBLE

    def test_it_is_still_reported_rather_than_dropped(self):
        rollup = roll_up(
            [
                CriterionVerdict("INC-01", "inclusion", Verdict.MET),
                CriterionVerdict("INC-02", "inclusion", Verdict.UNKNOWN, blocking=False),
            ]
        )
        assert rollup.deferred_criterion_ids == ["INC-02"]

    def test_a_data_gap_still_stops_a_verdict(self):
        rollup = roll_up(
            [
                CriterionVerdict("INC-01", "inclusion", Verdict.UNKNOWN),
                CriterionVerdict("INC-02", "inclusion", Verdict.UNKNOWN, blocking=False),
            ]
        )
        assert rollup.decision is ScreeningOutcome.NEEDS_REVIEW
        assert rollup.unresolved_criterion_ids == ["INC-01"]

    def test_a_failed_criterion_still_outranks_everything(self):
        rollup = roll_up(
            [
                CriterionVerdict("INC-01", "inclusion", Verdict.NOT_MET),
                CriterionVerdict("INC-02", "inclusion", Verdict.UNKNOWN, blocking=False),
            ]
        )
        assert rollup.decision is ScreeningOutcome.INELIGIBLE

    def test_a_protocol_of_nothing_but_visit_criteria_is_still_not_eligible(self):
        """Nothing was checked, so nothing was established. Silence is not a clean bill."""
        rollup = roll_up([CriterionVerdict("INC-02", "inclusion", Verdict.UNKNOWN, blocking=False)])
        assert rollup.decision is ScreeningOutcome.NEEDS_REVIEW


class TestScreening:
    def test_a_consent_criterion_no_longer_makes_every_patient_a_review(self):
        result = screen(criteria(LAB, CONSENT), patient(a1c=8.1), SCREENING)
        assert result.decision is ScreeningOutcome.ELIGIBLE

    def test_the_things_to_confirm_at_the_visit_are_listed(self):
        result = screen(criteria(LAB, CONSENT), patient(a1c=8.1), SCREENING)
        assert [c.criterion_id for c in result.to_confirm_at_visit] == ["INC-02"]

    def test_a_missing_lab_still_sends_the_case_to_a_human(self):
        result = screen(criteria(LAB, CONSENT), patient(a1c=None), SCREENING)
        assert result.decision is ScreeningOutcome.NEEDS_REVIEW

    def test_a_vaguely_worded_data_criterion_still_blocks(self):
        result = screen(criteria(LAB, VAGUE), patient(a1c=8.1), SCREENING)
        assert result.decision is ScreeningOutcome.NEEDS_REVIEW

    def test_coverage_counts_only_what_the_record_was_asked_to_settle(self):
        """A visit criterion is not a gap in the record, so it is not counted against coverage."""
        result = screen(criteria(LAB, CONSENT), patient(a1c=8.1), SCREENING)
        assert result.coverage == 1.0

    def test_the_worklist_holds_only_gaps_a_query_could_close(self):
        result = screen(criteria(LAB, CONSENT), patient(a1c=None), SCREENING)
        assert [h.blocks_criterion_id for h in result.resolution_worklist] == ["INC-01"]
