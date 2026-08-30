"""Which criteria abstention actually costs.

A false-abstention rate says how often the system sent a decidable case to a human. It does not say
*why*, and without that the number is a complaint rather than a finding. The same three or four
criteria block most screenings — an open category the protocol never enumerates, a threshold with no
number — and naming them turns the cost into something a site can act on: approve those once for the
trial, and the rest of the cohort clears.
"""

from datetime import date

from caliper.blockers import blocking_criteria
from caliper.ir import (
    Code,
    Concept,
    CriteriaSet,
    Criterion,
    ObservationPredicate,
    UnsupportedPredicate,
)
from caliper.record import Evidence, PatientIndex
from caliper.screen import screen

SCREENING = date(2026, 6, 1)
A1C = Code(system="LOINC", code="4548-4")
CONCEPT = Concept(text="HbA1c", codes=(A1C,))
SOURCE = "Inclusion Criteria:\n- HbA1c >= 7%\n- One major cardiovascular risk factor\n"

LAB = Criterion(
    id="INC-01",
    kind="inclusion",
    source_quote="HbA1c >= 7%",
    predicate=ObservationPredicate(concept=CONCEPT, op=">=", value=7.0, unit="%"),
)
OPEN_CATEGORY = Criterion(
    id="INC-02",
    kind="inclusion",
    source_quote="One major cardiovascular risk factor",
    predicate=UnsupportedPredicate(reason="the protocol does not enumerate the category"),
)


def criteria() -> CriteriaSet:
    return CriteriaSet(nct_id="NCT1", source_text=SOURCE, criteria=[LAB, OPEN_CATEGORY])


def patient(pid: str, a1c: float | None) -> PatientIndex:
    rows = [
        Evidence(
            kind="encounter",
            resource_type="Encounter",
            resource_id="e",
            display="visit",
            fhir_path="Bundle.entry[0].resource",
            date=date(2026, 4, 1),
        )
    ]
    if a1c is not None:
        rows.append(
            Evidence(
                kind="observation",
                resource_type="Observation",
                resource_id="o",
                display="HbA1c",
                fhir_path="Bundle.entry[1].resource",
                codes=(A1C,),
                value=a1c,
                unit="%",
                date=date(2026, 5, 1),
            )
        )
    return PatientIndex(patient_id=pid, birth_date=date(1970, 1, 1), sex="male", evidence=rows)


def screenings():
    return [
        screen(criteria(), patient("p1", 8.1), SCREENING),
        screen(criteria(), patient("p2", 7.5), SCREENING),
        screen(criteria(), patient("p3", None), SCREENING),
    ]


class TestBlockingCriteria:
    def test_it_counts_how_often_each_criterion_blocked(self):
        counts = {b.criterion_id: b.screenings for b in blocking_criteria(screenings())}
        assert counts["INC-02"] == 3
        assert counts["INC-01"] == 1

    def test_the_worst_offender_comes_first(self):
        assert blocking_criteria(screenings())[0].criterion_id == "INC-02"

    def test_it_carries_the_protocol_text_so_the_finding_is_readable(self):
        top = blocking_criteria(screenings(), criteria_sets=[criteria()])[0]
        assert top.quote == "One major cardiovascular risk factor"

    def test_it_says_what_was_missing(self):
        top = blocking_criteria(screenings())[0]
        assert "enumerate" in top.missing or "enumerate" in top.reason

    def test_a_criterion_settled_at_the_visit_is_not_a_blocker(self):
        visit_only = Criterion(
            id="INC-03",
            kind="inclusion",
            source_quote="HbA1c >= 7%",
            predicate=UnsupportedPredicate(reason="consent", settlement="at_visit"),
        )
        result = screen(
            CriteriaSet(nct_id="NCT1", source_text=SOURCE, criteria=[LAB, visit_only]),
            patient("p1", 8.1),
            SCREENING,
        )
        assert blocking_criteria([result]) == []

    def test_nothing_blocking_reports_nothing(self):
        result = screen(
            CriteriaSet(nct_id="NCT1", source_text=SOURCE, criteria=[LAB]),
            patient("p1", 8.1),
            SCREENING,
        )
        assert blocking_criteria([result]) == []
