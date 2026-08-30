"""How the packet says that a person, not the record, answered a criterion.

The mechanism is only safe if the document is honest about it, and the failure mode is specific: a
settled criterion that reads like a resolved one turns somebody's recollection into a citation. So
the packet marks the row, gives the settlements their own section above the criteria table, and
prints the name and the date every time — including on the row itself, where a reader skimming for
evidence would otherwise find a confident sentence and no source.
"""

from __future__ import annotations

from datetime import date

from caliper.agents.writer import deterministic_rationales
from caliper.ir import (
    Code,
    Concept,
    CriteriaSet,
    Criterion,
    ObservationPredicate,
    UnsupportedPredicate,
)
from caliper.logic import ScreeningOutcome, Verdict
from caliper.packet import build_packet, render_html, render_markdown
from caliper.record import Evidence, PatientIndex
from caliper.screen import screen
from caliper.settlements import Settlement, SettlementLog

SCREENING = date(2026, 6, 1)
A1C = Code(system="LOINC", code="4548-4", display="HbA1c")
SOURCE = "Inclusion Criteria:\n- HbA1c >= 7%\n- At least one major cardiovascular risk factor\n"

CRITERIA = CriteriaSet(
    nct_id="NCT99",
    source_text=SOURCE,
    criteria=[
        Criterion(
            id="INC-01",
            kind="inclusion",
            source_quote="HbA1c >= 7%",
            predicate=ObservationPredicate(
                concept=Concept(text="HbA1c", codes=(A1C,)), op=">=", value=7.0, unit="%"
            ),
        ),
        Criterion(
            id="INC-02",
            kind="inclusion",
            source_quote="At least one major cardiovascular risk factor",
            predicate=UnsupportedPredicate(reason="the protocol does not enumerate the category"),
        ),
    ],
)

SETTLEMENT = Settlement(
    nct_id="NCT99",
    criterion_id="INC-02",
    verdict=Verdict.MET,
    answered_by="r.okonkwo",
    answered_on=date(2026, 5, 20),
    note="Documented ischaemic heart disease counts as a major risk factor under this protocol",
)


def a_patient() -> PatientIndex:
    return PatientIndex(
        patient_id="p-1",
        birth_date=date(1968, 1, 1),
        sex="female",
        evidence=[
            Evidence(
                kind="encounter",
                resource_type="Encounter",
                resource_id="enc",
                display="visit",
                fhir_path="Bundle.entry[0].resource",
                date=date(2026, 4, 2),
            ),
            Evidence(
                kind="observation",
                resource_type="Observation",
                resource_id="obs",
                display="HbA1c",
                fhir_path="Bundle.entry[1].resource",
                codes=(A1C,),
                value=8.1,
                unit="%",
                date=date(2026, 5, 2),
            ),
        ],
    )


def a_settled_packet():
    patient = a_patient()
    result = screen(CRITERIA, patient, SCREENING, settlements=SettlementLog([SETTLEMENT]))
    return build_packet(result, CRITERIA, patient, deterministic_rationales(result))


class TestTheRow:
    def test_a_settled_criterion_is_tagged_in_the_table(self):
        markdown = render_markdown(a_settled_packet())
        row = next(line for line in markdown.splitlines() if line.startswith("| INC-02"))

        assert "settled by a person" in row

    def test_the_row_names_who_answered_and_when(self):
        row = next(r for r in a_settled_packet().rows if r.criterion_id == "INC-02")

        assert "r.okonkwo" in row.rationale
        assert "2026-05-20" in row.rationale

    def test_a_criterion_the_record_decided_carries_no_such_tag(self):
        markdown = render_markdown(a_settled_packet())
        row = next(line for line in markdown.splitlines() if line.startswith("| INC-01"))

        assert "settled by a person" not in row

    def test_the_settled_row_offers_no_evidence(self):
        row = next(r for r in a_settled_packet().rows if r.criterion_id == "INC-02")

        assert row.evidence == ()


class TestTheSection:
    def test_the_settlements_are_listed_where_the_verdict_is_read(self):
        markdown = render_markdown(a_settled_packet())

        assert "Answered by a person, not by the record" in markdown
        assert markdown.index("Answered by a person") < markdown.index("## Criteria")

    def test_it_quotes_the_protocol_and_the_reason_given(self):
        markdown = render_markdown(a_settled_packet())

        assert "At least one major cardiovascular risk factor" in markdown
        assert "ischaemic heart disease" in markdown

    def test_the_verdict_line_says_the_decision_rests_on_one(self):
        packet = a_settled_packet()

        assert packet.decision is ScreeningOutcome.ELIGIBLE
        assert packet.settlement_note is not None
        assert "1 criterion" in packet.settlement_note

    def test_a_screening_with_no_settlements_says_nothing_about_them(self):
        patient = a_patient()
        result = screen(CRITERIA, patient, SCREENING)
        packet = build_packet(result, CRITERIA, patient, deterministic_rationales(result))

        assert packet.settlements == ()
        assert packet.settlement_note is None
        assert "Answered by a person" not in render_markdown(packet)

    def test_both_renderings_agree(self):
        html = render_html(a_settled_packet())

        assert 'id="settlements"' in html
        assert html.index('id="settlements"') < html.index('id="criteria"')
        assert "r.okonkwo" in html
        assert "ischaemic heart disease" in html
