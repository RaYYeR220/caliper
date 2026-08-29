"""The screening packet: the document a coordinator reads, and the only artefact they sign.

Two things are asserted harder than the rest. The open items come first when the screening needs
review, because the whole point of the tool is to tell a coordinator what to do next rather than
make them find it under forty resolved criteria. And nothing in the rendered page reaches the
network or escapes into markup: a packet is printed, filed, and read on machines nobody controls.
"""

from __future__ import annotations

from datetime import date

from caliper.agents.writer import Rationale, RationaleSet, deterministic_rationales
from caliper.evaluate import AbsencePolicy
from caliper.ir import (
    Code,
    Concept,
    CriteriaSet,
    Criterion,
    DemographicPredicate,
    ObservationPredicate,
    PresencePredicate,
    TemporalWindow,
)
from caliper.logic import ScreeningOutcome
from caliper.packet import build_packet, render_html, render_markdown
from caliper.record import Evidence, PatientIndex
from caliper.screen import ScreeningResult, screen

SCREENING = date(2026, 6, 1)
WITHIN_SIX_MONTHS = TemporalWindow(relation="within", amount=6, unit="months")

CREATININE = Code(system="LOINC", code="2160-0", display="Creatinine")
HAEMOGLOBIN = Code(system="LOINC", code="718-7", display="Haemoglobin")
INFARCTION = Code(system="SNOMED", code="22298006", display="Myocardial infarction")

SOURCE = (
    "Inclusion Criteria:\n"
    "- Serum creatinine <= 1.5 mg/dL within 6 months\n"
    "- Age 18 years or older\n"
    "- Haemoglobin >= 9 g/dL within 6 months\n"
    "Exclusion Criteria:\n"
    "- Myocardial infarction within 6 months\n"
)

CRITERIA = CriteriaSet(
    nct_id="NCT04000000",
    source_text=SOURCE,
    criteria=[
        Criterion(
            id="INC-01",
            kind="inclusion",
            source_quote="Serum creatinine <= 1.5 mg/dL within 6 months",
            predicate=ObservationPredicate(
                concept=Concept(text="serum creatinine", codes=(CREATININE,)),
                op="<=",
                value=1.5,
                unit="mg/dL",
                window=WITHIN_SIX_MONTHS,
            ),
        ),
        Criterion(
            id="INC-02",
            kind="inclusion",
            source_quote="Age 18 years or older",
            predicate=DemographicPredicate(field="age", op=">=", value=18, unit="years"),
        ),
        Criterion(
            id="INC-03",
            kind="inclusion",
            source_quote="Haemoglobin >= 9 g/dL within 6 months",
            predicate=ObservationPredicate(
                concept=Concept(text="haemoglobin", codes=(HAEMOGLOBIN,)),
                op=">=",
                value=9.0,
                unit="g/dL",
                window=WITHIN_SIX_MONTHS,
            ),
        ),
        Criterion(
            id="EXC-01",
            kind="exclusion",
            source_quote="Myocardial infarction within 6 months",
            predicate=PresencePredicate(
                type="condition",
                concept=Concept(text="myocardial infarction", codes=(INFARCTION,)),
                presence="present",
                window=WITHIN_SIX_MONTHS,
            ),
        ),
    ],
)

TRIAL_TITLE = "A Study of Something in Adults with Type 2 Diabetes"

ENCOUNTER = Evidence(
    kind="encounter",
    resource_type="Encounter",
    resource_id="enc-1",
    display="Office visit",
    fhir_path="Bundle.entry[1].resource",
    date=date(2026, 5, 14),
)
CREATININE_ROW = Evidence(
    kind="observation",
    resource_type="Observation",
    resource_id="obs-creat",
    display="Creatinine",
    fhir_path="Bundle.entry[3].resource",
    codes=(CREATININE,),
    value=1.2,
    unit="mg/dL",
    date=date(2026, 5, 14),
)
HAEMOGLOBIN_ROW = Evidence(
    kind="observation",
    resource_type="Observation",
    resource_id="obs-hb",
    display="Haemoglobin",
    fhir_path="Bundle.entry[4].resource",
    codes=(HAEMOGLOBIN,),
    value=11.4,
    unit="g/dL",
    date=date(2026, 5, 14),
)
INFARCTION_ROW = Evidence(
    kind="condition",
    resource_type="Condition",
    resource_id="cond-mi",
    display="Acute myocardial infarction",
    fhir_path="Bundle.entry[9].resource",
    codes=(INFARCTION,),
    date=date(2026, 2, 1),
)


def a_patient(patient_id: str, evidence: list[Evidence]) -> PatientIndex:
    return PatientIndex(
        patient_id=patient_id,
        birth_date=date(1959, 3, 2),
        sex="female",
        evidence=evidence,
    )


ELIGIBLE_PATIENT = a_patient("P-001", [ENCOUNTER, CREATININE_ROW, HAEMOGLOBIN_ROW])
INELIGIBLE_PATIENT = a_patient(
    "P-002", [ENCOUNTER, CREATININE_ROW, HAEMOGLOBIN_ROW, INFARCTION_ROW]
)
REVIEW_PATIENT = a_patient("P-003", [ENCOUNTER])


def a_screening(patient: PatientIndex) -> ScreeningResult:
    return screen(CRITERIA, patient, SCREENING)


def a_packet(patient: PatientIndex, **overrides: object):
    result = a_screening(patient)
    return build_packet(
        result,
        CRITERIA,
        patient,
        deterministic_rationales(result),
        trial_title=TRIAL_TITLE,
        **overrides,
    )


class TestOrdering:
    def test_open_items_come_before_the_full_table_when_review_is_needed(self):
        packet = a_packet(REVIEW_PATIENT)
        assert packet.decision is ScreeningOutcome.NEEDS_REVIEW
        assert len(packet.open_items) == 2

        markdown = render_markdown(packet)
        assert markdown.index("## Open items") < markdown.index("## Criteria")

        html = render_html(packet)
        assert html.index('id="open-items"') < html.index('id="criteria"')

    def test_a_resolved_eligible_packet_has_no_open_items_section(self):
        packet = a_packet(ELIGIBLE_PATIENT)

        assert packet.decision is ScreeningOutcome.ELIGIBLE
        assert packet.verdict == "Eligible"
        assert packet.open_items == ()
        assert "Open items" not in render_markdown(packet)
        assert 'id="open-items"' not in render_html(packet)

    def test_an_open_item_carries_the_query_that_would_close_it(self):
        packet = a_packet(REVIEW_PATIENT)
        item = next(i for i in packet.open_items if i.criterion_id == "INC-01")

        assert "a serum creatinine result" in item.missing
        assert item.fhir_query.startswith("Observation?patient=P-003")
        assert item.fhir_query in render_markdown(packet)


class TestIneligible:
    def test_the_deciding_criterion_is_quoted_verbatim(self):
        packet = a_packet(INELIGIBLE_PATIENT)

        assert packet.verdict == "Not eligible"
        assert [row.criterion_id for row in packet.deciding] == ["EXC-01"]

        quote = "Myocardial infarction within 6 months"
        markdown = render_markdown(packet)
        assert markdown.index(quote) < markdown.index("## Criteria")
        assert quote in render_html(packet)

    def test_the_deciding_criterion_brings_its_evidence_with_it(self):
        packet = a_packet(INELIGIBLE_PATIENT)
        deciding = packet.deciding[0]

        assert [line.fhir_path for line in deciding.evidence] == ["Bundle.entry[9].resource"]


class TestEvidence:
    def test_every_evidence_citation_carries_its_fhir_pointer(self):
        packet = a_packet(INELIGIBLE_PATIENT)
        markdown = render_markdown(packet)
        html = render_html(packet)

        pointers = {line.fhir_path for row in packet.rows for line in row.evidence}
        assert pointers == {"Bundle.entry[3].resource", "Bundle.entry[4].resource",
                            "Bundle.entry[9].resource"}
        for pointer in pointers:
            assert pointer in markdown
            assert pointer in html


class TestFooter:
    def test_the_footer_names_the_absence_policy_and_the_fingerprint(self):
        packet = a_packet(REVIEW_PATIENT)
        markdown = render_markdown(packet)
        html = render_html(packet)

        assert packet.absence_policy == AbsencePolicy.COVERAGE_GATED
        for rendered in (markdown, html):
            assert "coverage-gated" in rendered
            assert CRITERIA.source_text_sha256 in rendered
            assert "2 of 4" in rendered

    def test_the_footer_says_who_decides_eligibility(self):
        packet = a_packet(ELIGIBLE_PATIENT)

        for rendered in (render_markdown(packet), render_html(packet)):
            assert "pre-screening" in rendered
            assert "investigator" in rendered

    def test_the_footer_counts_the_sentences_the_engine_had_to_write_itself(self):
        result = a_screening(ELIGIBLE_PATIENT)
        written = deterministic_rationales(result)
        mixed = RationaleSet(
            nct_id=written.nct_id,
            patient_id=written.patient_id,
            rationales=tuple(
                Rationale(criterion_id=r.criterion_id, sentence=r.sentence, source="model")
                if r.criterion_id != "INC-01"
                else r
                for r in written
            ),
        )
        packet = build_packet(result, CRITERIA, ELIGIBLE_PATIENT, mixed, trial_title=TRIAL_TITLE)

        assert packet.engine_written == 1
        assert "1 of 4" in render_markdown(packet)


class TestHtmlSafety:
    def test_the_page_makes_no_external_request(self):
        html = render_html(a_packet(REVIEW_PATIENT))

        assert "http://" not in html
        assert "https://" not in html
        assert "<script" not in html
        assert "@import" not in html

    def test_markup_in_a_patient_identifier_is_escaped_rather_than_rendered(self):
        hostile = a_patient('Ada <script>alert("x")</script>', [ENCOUNTER])
        packet = a_packet(hostile)
        html = render_html(packet)

        assert "<script>alert" not in html
        assert "&lt;script&gt;" in html
        # Protocol text goes through the same escape, and this quote carries an operator.
        assert "&lt;= 1.5 mg/dL" in html

    def test_the_page_is_self_contained(self):
        html = render_html(a_packet(ELIGIBLE_PATIENT))

        assert html.lstrip().startswith("<!DOCTYPE html>")
        assert "<style>" in html
        assert "<link" not in html


class TestAgreement:
    def test_markdown_and_html_agree_on_the_verdict_and_the_open_items(self):
        for patient in (ELIGIBLE_PATIENT, INELIGIBLE_PATIENT, REVIEW_PATIENT):
            packet = a_packet(patient)
            markdown = render_markdown(packet)
            html = render_html(packet)

            assert packet.verdict in markdown
            assert packet.verdict in html
            assert markdown.count("FHIR query") == len(packet.open_items)
            assert html.count("FHIR query") == len(packet.open_items)

    def test_every_criterion_appears_in_both_renderings_with_its_verdict(self):
        packet = a_packet(REVIEW_PATIENT)
        markdown = render_markdown(packet)
        html = render_html(packet)

        assert [row.criterion_id for row in packet.rows] == ["INC-01", "INC-02", "INC-03", "EXC-01"]
        assert {row.verdict for row in packet.rows} == {"Met", "Not met", "Unresolved"}
        for row in packet.rows:
            assert row.criterion_id in markdown
            assert row.criterion_id in html
            assert row.rationale in markdown
