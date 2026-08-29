"""The narrative extractor, and the guard that decides what a note is allowed to assert.

`caliper.record` refuses to match a narrative row by wording, so a note can only ever reach a
verdict through this module. Everything here therefore asks the same question twice: did the
model say the right thing, and does the deterministic gate downstream of it hold when the model
says the wrong thing.

Every test runs offline against a fake transport. A test that reached the network would fail
rather than quietly cost money.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import pytest

from caliper.agents import AgentContext
from caliper.agents.extractor import (
    AGENT_NAME,
    SYSTEM_PROMPT,
    ExtractionResult,
    NoteReading,
    extract_findings,
    locate_quote,
)
from caliper.ir import Code, Concept
from caliper.llm import LLMClient, strict_schema_problems, to_strict_schema
from caliper.notes import attach_notes
from caliper.record import Evidence, PatientIndex

from fakes import RoutedTransport, a_profile, a_routed_client

SCREENING = date(2026, 6, 1)

MI_CODE = Code(system="SNOMED", code="22298006", display="Myocardial infarction")
MI = Concept(text="myocardial infarction", codes=(MI_CODE,))
UNCODED_MI = Concept(text="myocardial infarction")
HF = Concept(text="heart failure", codes=(Code(system="SNOMED", code="84114007"),))

# Wrapped mid-sentence on purpose: real notes wrap, and a quote must survive it.
DISCHARGE = {
    "note_id": "n-mi",
    "date": "2026-03-18",
    "type": "Discharge summary",
    "author_role": "cardiology registrar",
    "text": (
        "Discharge summary\n\n"
        "Presented with an inferior STEMI on 14 March 2026 and was treated with primary\n"
        "PCI to the right coronary artery.\n\n"
        "Father had an MI in his fifties.\n\n"
        "We would consider an ICD if the ejection fraction stays below 35%."
    ),
}
CLINIC = {
    "note_id": "n-clinic",
    "date": "2026-04-02",
    "type": "Cardiology clinic letter",
    "author_role": "cardiologist",
    "text": (
        "Cardiology clinic\n\n"
        "No history of myocardial infarction.\n\n"
        "Query paroxysmal AF; holter pending."
    ),
}

STEMI_SENTENCE = (
    "Presented with an inferior STEMI on 14 March 2026 and was treated with primary\n"
    "PCI to the right coronary artery."
)


def a_reading(*findings: dict[str, Any]) -> str:
    return json.dumps({"findings": list(findings)})


def found(
    sentence: str,
    assertion: str,
    concept: str = "myocardial infarction",
    when: str | None = None,
) -> dict[str, Any]:
    return {"concept": concept, "sentence": sentence, "assertion": assertion, "date": when}


NOTHING = a_reading()


def an_index(tmp_path, *notes: dict[str, Any]) -> PatientIndex:
    (tmp_path / "p-1.json").write_text(json.dumps(list(notes)), encoding="utf-8")
    patient = PatientIndex(patient_id="p-1", birth_date=date(1962, 4, 4), sex="male")
    return attach_notes(patient, root=tmp_path)


def run_recorded(
    index: PatientIndex, routes: dict[str, str], concepts=(MI,), **kw
) -> tuple[ExtractionResult, RoutedTransport]:
    client, transport = a_routed_client(routes, default=NOTHING)
    ctx = AgentContext(client=client, as_of=SCREENING)
    return extract_findings(index, list(concepts), ctx, **kw), transport


def run(index: PatientIndex, routes: dict[str, str], concepts=(MI,), **kw) -> ExtractionResult:
    return run_recorded(index, routes, concepts, **kw)[0]


class TestAssertedFindings:
    def test_an_asserted_finding_becomes_coded_narrative_evidence(self, tmp_path):
        index = an_index(tmp_path, DISCHARGE)
        result = run(index, {"inferior STEMI": a_reading(found(STEMI_SENTENCE, "present"))})

        (row,) = result.evidence
        assert row.kind == "condition"
        assert row.source == "narrative"
        assert row.codes == (MI_CODE,)
        assert row.narrative_quote == STEMI_SENTENCE
        assert row.resource_id == "n-mi"
        assert row.fhir_path.endswith("#n-mi")
        assert result.discarded == ()

    def test_the_quote_is_the_notes_own_wording_not_the_models(self, tmp_path):
        """A model that unwraps the line still cites the note; the row quotes the note."""
        index = an_index(tmp_path, DISCHARGE)
        unwrapped = " ".join(STEMI_SENTENCE.split())
        result = run(index, {"inferior STEMI": a_reading(found(unwrapped, "present"))})

        (row,) = result.evidence
        assert row.narrative_quote == STEMI_SENTENCE
        assert row.narrative_quote in DISCHARGE["text"]

    def test_a_date_in_the_sentence_is_kept(self, tmp_path):
        index = an_index(tmp_path, DISCHARGE)
        reading = a_reading(found(STEMI_SENTENCE, "present", when="2026-03-14"))
        result = run(index, {"inferior STEMI": reading})
        assert result.evidence[0].date == date(2026, 3, 14)

    def test_an_undated_sentence_falls_back_to_the_note_date(self, tmp_path):
        index = an_index(tmp_path, DISCHARGE)
        result = run(index, {"inferior STEMI": a_reading(found(STEMI_SENTENCE, "present"))})
        assert result.evidence[0].date == date(2026, 3, 18)

    def test_a_partial_date_is_not_rounded_into_a_real_one(self, tmp_path):
        index = an_index(tmp_path, DISCHARGE)
        result = run(
            index, {"inferior STEMI": a_reading(found(STEMI_SENTENCE, "present", when="2026-03"))}
        )
        assert result.evidence[0].date == date(2026, 3, 18)

    def test_the_caller_chooses_the_evidence_kind(self, tmp_path):
        index = an_index(tmp_path, DISCHARGE)
        result = run(
            index,
            {"inferior STEMI": a_reading(found(STEMI_SENTENCE, "present"))},
            kind="procedure",
        )
        assert result.evidence[0].kind == "procedure"


class TestTheGuard:
    def test_a_denial_produces_a_documented_negation_and_no_evidence(self, tmp_path):
        index = an_index(tmp_path, CLINIC)
        result = run(
            index,
            {"No history": a_reading(found("No history of myocardial infarction.", "absent"))},
        )

        assert result.evidence == ()
        (negation,) = result.negations
        assert negation.concept == MI
        assert negation.quote == "No history of myocardial infarction."
        assert negation.note_id == "n-clinic"
        assert negation.fhir_path.endswith("#n-clinic")

    def test_a_family_history_mention_produces_nothing_and_is_counted_as_rejected(self, tmp_path):
        index = an_index(tmp_path, DISCHARGE)
        result = run(
            index,
            {"STEMI": a_reading(found("Father had an MI in his fifties.", "family_history"))},
        )

        assert result.evidence == ()
        assert result.negations == ()
        (rejected,) = result.discarded
        assert rejected.assertion == "family_history"
        assert rejected.quote == "Father had an MI in his fifties."
        assert "family_history" in rejected.reason
        assert result.counts_by_assertion()["family_history"] == 1

    def test_a_hypothetical_produces_nothing(self, tmp_path):
        index = an_index(tmp_path, DISCHARGE)
        sentence = "We would consider an ICD if the ejection fraction stays below 35%."
        result = run(index, {"STEMI": a_reading(found(sentence, "hypothetical"))})

        assert result.evidence == ()
        assert result.negations == ()
        assert [d.assertion for d in result.discarded] == ["hypothetical"]

    def test_an_uncertain_finding_produces_nothing(self, tmp_path):
        index = an_index(tmp_path, CLINIC)
        reading = a_reading(found("Query paroxysmal AF; holter pending.", "uncertain"))
        result = run(index, {"No history": reading})

        assert result.evidence == ()
        assert [d.assertion for d in result.discarded] == ["uncertain"]

    def test_a_finding_about_someone_else_produces_nothing(self, tmp_path):
        index = an_index(tmp_path, DISCHARGE)
        result = run(
            index,
            {"STEMI": a_reading(found("Father had an MI in his fifties.", "other_subject"))},
        )
        assert result.evidence == ()
        assert [d.assertion for d in result.discarded] == ["other_subject"]

    def test_a_quote_that_is_not_in_the_note_is_discarded_with_a_reason(self, tmp_path):
        """A paraphrase has stopped being a citation, whatever it says."""
        index = an_index(tmp_path, DISCHARGE)
        invented = "The patient suffered a large anterior myocardial infarction."
        result = run(index, {"STEMI": a_reading(found(invented, "present"))})

        assert result.evidence == ()
        (rejected,) = result.discarded
        assert rejected.quote == invented
        assert "not appear" in rejected.reason
        assert rejected.assertion == "present"

    def test_a_denial_that_is_not_in_the_note_is_discarded_too(self, tmp_path):
        index = an_index(tmp_path, CLINIC)
        reading = a_reading(found("He denies any cardiac history.", "absent"))
        result = run(index, {"No history": reading})

        assert result.negations == ()
        assert len(result.discarded) == 1

    def test_a_concept_the_caller_never_asked_about_is_discarded(self, tmp_path):
        index = an_index(tmp_path, DISCHARGE)
        result = run(
            index,
            {"STEMI": a_reading(found(STEMI_SENTENCE, "present", concept="pulmonary embolism"))},
        )
        assert result.evidence == ()
        (rejected,) = result.discarded
        assert "not among" in rejected.reason

    def test_the_concept_is_matched_despite_spacing_and_case(self, tmp_path):
        index = an_index(tmp_path, DISCHARGE)
        loose = a_reading(found(STEMI_SENTENCE, "present", concept="Myocardial  Infarction"))
        result = run(index, {"STEMI": loose})
        assert result.evidence[0].codes == (MI_CODE,)

    def test_the_same_sentence_is_not_emitted_twice_for_one_concept(self, tmp_path):
        index = an_index(tmp_path, DISCHARGE)
        twice = a_reading(found(STEMI_SENTENCE, "present"), found(STEMI_SENTENCE, "present"))
        result = run(index, {"STEMI": twice})
        assert len(result.evidence) == 1


class TestEndToEndAgainstTheRecord:
    def test_extracted_evidence_is_matchable_through_its_codes(self, tmp_path):
        index = an_index(tmp_path, DISCHARGE)
        result = run(index, {"inferior STEMI": a_reading(found(STEMI_SENTENCE, "present"))})
        index.evidence.extend(result.evidence)

        hits = index.find("condition", MI, None, SCREENING)
        assert [e.narrative_quote for e in hits] == [STEMI_SENTENCE]

    def test_the_same_evidence_is_not_matchable_by_wording_alone(self, tmp_path):
        """The guard in `record.py`, proved end to end rather than in isolation."""
        index = an_index(tmp_path, DISCHARGE)
        result = run(index, {"inferior STEMI": a_reading(found(STEMI_SENTENCE, "present"))})
        index.evidence.extend(result.evidence)

        assert "myocardial infarction" in result.evidence[0].codes[0].display.casefold()
        assert index.find("condition", UNCODED_MI, None, SCREENING) == []

    def test_an_uncoded_concept_produces_evidence_that_can_never_resolve_anything(self, tmp_path):
        """Worth stating: extraction without resolution is work that buys nothing."""
        index = an_index(tmp_path, DISCHARGE)
        result = run(
            index,
            {"inferior STEMI": a_reading(found(STEMI_SENTENCE, "present"))},
            concepts=(UNCODED_MI,),
        )
        index.evidence.extend(result.evidence)
        assert result.evidence[0].codes == ()
        assert index.find("condition", UNCODED_MI, None, SCREENING) == []

    def test_a_raw_note_never_matches_a_concept_by_itself(self, tmp_path):
        index = an_index(tmp_path, DISCHARGE, CLINIC)
        assert index.find("condition", UNCODED_MI, None, SCREENING) == []
        assert len(index.notes()) == 2


class TestReporting:
    def test_counts_by_assertion_report_what_the_guard_saw(self, tmp_path):
        index = an_index(tmp_path, DISCHARGE, CLINIC)
        result = run(
            index,
            {
                "STEMI": a_reading(
                    found(STEMI_SENTENCE, "present"),
                    found("Father had an MI in his fifties.", "family_history"),
                ),
                "No history": a_reading(
                    found("No history of myocardial infarction.", "absent"),
                    found("Query paroxysmal AF; holter pending.", "uncertain"),
                ),
            },
        )
        assert result.counts_by_assertion() == {
            "present": 1,
            "absent": 1,
            "family_history": 1,
            "uncertain": 1,
        }

    def test_every_note_is_accounted_for_even_when_nothing_came_back(self, tmp_path):
        index = an_index(tmp_path, DISCHARGE, CLINIC)
        result = run(index, {"nothing routes here": NOTHING})

        assert [n.note_id for n in result.notes] == ["n-mi", "n-clinic"]
        assert all(n.counts == {} for n in result.notes)
        assert all(n.error is None for n in result.notes)

    def test_per_note_counts_separate_what_was_kept_from_what_was_rejected(self, tmp_path):
        index = an_index(tmp_path, DISCHARGE)
        result = run(
            index,
            {
                "STEMI": a_reading(
                    found(STEMI_SENTENCE, "present"),
                    found("Father had an MI in his fifties.", "family_history"),
                )
            },
        )
        (note,) = result.notes
        assert note.note_id == "n-mi"
        assert note.counts == {"present": 1, "family_history": 1}
        assert note.kept == 1
        assert note.rejected == 1

    def test_the_model_is_asked_once_per_note(self, tmp_path):
        index = an_index(tmp_path, DISCHARGE, CLINIC)
        _, transport = run_recorded(index, {"nothing routes here": NOTHING})
        assert len(transport.requests) == 2

    def test_the_note_text_and_the_concepts_are_both_in_the_prompt(self, tmp_path):
        index = an_index(tmp_path, DISCHARGE)
        _, transport = run_recorded(index, {"nothing routes here": NOTHING}, concepts=(MI, HF))
        (sent,) = transport.user_messages
        assert "inferior STEMI" in sent
        assert "myocardial infarction" in sent
        assert "heart failure" in sent
        assert "Discharge summary" in sent

    def test_the_run_is_summarised_into_the_trajectory(self, tmp_path):
        index = an_index(tmp_path, DISCHARGE)
        client, _ = a_routed_client({"STEMI": a_reading(found(STEMI_SENTENCE, "present"))})
        ctx = AgentContext(client=client, as_of=SCREENING)
        extract_findings(index, [MI], ctx)

        assert [step.agent for step in ctx.trajectory.steps] == [AGENT_NAME, AGENT_NAME]
        summary = ctx.trajectory.steps[-1].parsed
        assert summary["evidence"] == 1
        assert summary["notes"] == 1


class TestFailure:
    def test_a_provider_failure_on_one_note_does_not_lose_the_others(self, tmp_path):
        index = an_index(tmp_path, DISCHARGE, CLINIC)
        transport = _FlakyTransport(
            {"No history": a_reading(found("No history of myocardial infarction.", "absent"))},
            fail_on="inferior STEMI",
        )
        client = LLMClient(
            a_profile(), transport=transport, env={"TEST_API_KEY": "not-a-real-key"}
        )
        result = extract_findings(index, [MI], AgentContext(client=client, as_of=SCREENING))

        assert len(result.negations) == 1
        failed = [n for n in result.notes if n.error is not None]
        assert [n.note_id for n in failed] == ["n-mi"]
        assert result.failed_notes == ("n-mi",)

    def test_a_patient_with_no_notes_costs_nothing(self, tmp_path):
        patient = PatientIndex(patient_id="p-1", birth_date=date(1962, 4, 4), sex="male")
        client, transport = a_routed_client({})
        result = extract_findings(patient, [MI], AgentContext(client=client, as_of=SCREENING))

        assert result.evidence == ()
        assert result.notes == ()
        assert transport.requests == []

    def test_no_concepts_means_no_calls(self, tmp_path):
        index = an_index(tmp_path, DISCHARGE)
        client, transport = a_routed_client({})
        result = extract_findings(index, [], AgentContext(client=client, as_of=SCREENING))

        assert result.evidence == ()
        assert transport.requests == []


class _FlakyTransport(RoutedTransport):
    """Routes as usual, except for one note the provider refuses outright."""

    def __init__(self, routes: dict[str, str], *, fail_on: str):
        super().__init__(routes, default=NOTHING)
        self.fail_on = fail_on

    def _create(self, **kwargs: Any):
        if self.fail_on in kwargs["messages"][-1]["content"]:
            self.requests.append(kwargs)
            raise RuntimeError("the provider refused this request")
        return super()._create(**kwargs)


class TestQuoteAnchoring:
    def test_an_exact_quote_is_returned_unchanged(self):
        assert locate_quote("A. B. C.", "B.") == "B."

    def test_a_quote_that_differs_only_in_wrapping_is_re_anchored(self):
        assert locate_quote("one two\nthree four", "two three") == "two\nthree"

    def test_a_quote_with_a_word_changed_is_refused(self):
        assert locate_quote("Denies prior stroke.", "Denies previous stroke.") is None

    def test_case_is_not_forgiven(self):
        """Changing the letters of a citation is not a formatting difference."""
        assert locate_quote("Denies prior stroke.", "denies prior stroke.") is None

    def test_an_empty_quote_matches_nothing(self):
        assert locate_quote("Denies prior stroke.", "   ") is None


class TestPrompting:
    def test_the_system_prompt_names_every_assertion_class(self):
        for assertion in (
            "present",
            "absent",
            "family_history",
            "hypothetical",
            "uncertain",
            "other_subject",
        ):
            assert assertion in SYSTEM_PROMPT

    def test_the_prompt_says_plainly_that_this_is_not_summarisation(self):
        assert "not summarisation" in SYSTEM_PROMPT

    def test_the_reply_schema_survives_a_providers_strict_mode(self):
        assert strict_schema_problems(to_strict_schema(NoteReading)) == []

    @pytest.mark.parametrize("assertion", ["present", "absent", "hypothetical"])
    def test_the_reply_model_accepts_the_six_classes(self, assertion):
        reading = NoteReading.model_validate_json(a_reading(found("x", assertion)))
        assert reading.findings[0].assertion == assertion

    def test_a_class_outside_the_six_is_rejected_by_the_schema(self):
        with pytest.raises(ValueError):
            NoteReading.model_validate_json(a_reading(found("x", "probably")))


def test_note_rows_are_the_only_thing_the_extractor_reads(tmp_path):
    """Structured rows are already coded; sending them to a model would be a round trip for none."""
    index = an_index(tmp_path, DISCHARGE)
    index.evidence.append(
        Evidence(
            kind="condition",
            resource_type="Condition",
            resource_id="c-1",
            display="Myocardial infarction",
            fhir_path="Bundle.entry[2].resource",
            codes=(MI_CODE,),
            date=date(2020, 1, 1),
        )
    )
    _, transport = run_recorded(index, {"nothing routes here": NOTHING})
    assert len(transport.requests) == 1
