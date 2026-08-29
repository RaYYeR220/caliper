"""The compiler: protocol prose in, executable criteria out.

Two properties are worth more than the rest. Every span of the protocol is accounted for, so a
criterion cannot silently disappear; and a criterion whose quote does not appear verbatim in the
protocol is downgraded rather than trusted, because a compiler that paraphrases has already stopped
reading the document it claims to implement.
"""

import json

import pytest

from caliper.agents.base import AgentContext
from caliper.agents.compiler import COMPILER_SYSTEM_PROMPT, compile_criteria
from caliper.criteria_text import Section
from caliper.ir import CompositePredicate, UnsupportedPredicate

from fakes import Reply, a_client, a_routed_client

PROTOCOL = (
    "Inclusion Criteria:\n\n"
    "* Type 2 diabetes with HbA1c >= 7%.\n"
    "* Age 18 years or older.\n\n"
    "Exclusion Criteria:\n\n"
    "* Unsuitable in the opinion of the investigator.\n"
)


def observation(text: str, op: str, value: float, unit: str) -> dict:
    return {
        "type": "observation",
        "concept": {"text": text, "codes": []},
        "op": op,
        "value": value,
        "value_high": None,
        "unit": unit,
        "window": None,
    }


def span_reply(quote: str, predicate: dict, kind: str = "inclusion") -> Reply:
    return Reply(
        json.dumps(
            {
                "is_criterion": True,
                "kind": kind,
                "source_quote": quote,
                "predicate": predicate,
                "notes": None,
            }
        )
    )


def not_a_criterion(note: str) -> Reply:
    return Reply(
        json.dumps(
            {
                "is_criterion": False,
                "kind": None,
                "source_quote": None,
                "predicate": None,
                "notes": note,
            }
        )
    )


UNSUPPORTED = {"type": "unsupported", "reason": "requires investigator judgement"}
AGE = {
    "type": "demographic",
    "field": "age",
    "op": ">=",
    "value": 18.0,
    "unit": "years",
}


A1C = observation("HbA1c", ">=", 7.0, "%")
A1C_QUOTE = "Type 2 diabetes with HbA1c >= 7%."
AGE_QUOTE = "Age 18 years or older."
JUDGEMENT_QUOTE = "Unsuitable in the opinion of the investigator."


def three_good_replies() -> list[Reply]:
    return [
        span_reply(A1C_QUOTE, A1C),
        span_reply(AGE_QUOTE, AGE),
        span_reply(JUDGEMENT_QUOTE, UNSUPPORTED, "exclusion"),
    ]


def context(replies):
    client, transport = a_client(replies)
    return AgentContext(client=client), transport


def compile_protocol(replies, text: str = PROTOCOL, nct_id: str = "NCT00000001"):
    ctx, transport = context(replies)
    return compile_criteria(nct_id, text, ctx), transport


class TestOneCallPerSpan:
    def test_each_span_gets_its_own_call(self):
        _, transport = compile_protocol(
            three_good_replies()
        )
        assert len(transport.requests) == 3

    def test_the_span_text_is_what_the_model_is_asked_about(self):
        _, transport = compile_protocol(
            three_good_replies()
        )
        assert "Age 18 years or older." in transport.user_messages[1]

    def test_the_section_is_given_to_the_model_as_context(self):
        _, transport = compile_protocol(
            three_good_replies()
        )
        assert "exclusion" in transport.user_messages[2].lower()


class TestAssembly:
    def test_identifiers_are_assigned_in_code_and_are_stable(self):
        result, _ = compile_protocol(
            three_good_replies()
        )
        assert [c.id for c in result.criteria_set.criteria] == ["INC-01", "INC-02", "EXC-01"]

    def test_the_section_decides_the_kind_not_the_model(self):
        """A model that mislabels a section must not move a criterion between inclusion sets."""
        result, _ = compile_protocol(
            [
                span_reply(
                    "Type 2 diabetes with HbA1c >= 7%.",
                    observation("HbA1c", ">=", 7.0, "%"),
                    kind="exclusion",
                ),
                span_reply("Age 18 years or older.", AGE),
                span_reply(JUDGEMENT_QUOTE, UNSUPPORTED, "exclusion"),
            ]
        )
        assert result.criteria_set.criteria[0].kind == "inclusion"

    def test_the_protocol_text_on_the_result_is_the_unescaped_source(self):
        result, _ = compile_protocol(
            three_good_replies()
        )
        assert result.criteria_set.source_text.startswith("Inclusion Criteria:")

    def test_registry_escapes_are_removed_before_anything_else_happens(self):
        text = "Inclusion Criteria:\n\n* eGFR \\<90 mL/min/1.73 m\\^2.\n"
        reply = span_reply("eGFR <90 mL/min/1.73 m^2.", observation("eGFR", "<", 90.0, "mL/min"))
        result, transport = compile_protocol([reply], text=text)
        assert "\\<" not in transport.user_messages[0]
        assert result.criteria_set.criteria[0].predicate.type == "observation"


class TestSpansThatAreNotCriteria:
    def test_a_rejected_span_produces_no_criterion(self):
        result, _ = compile_protocol(
            [
                span_reply(A1C_QUOTE, A1C),
                not_a_criterion("cross-reference, not a criterion"),
                span_reply(JUDGEMENT_QUOTE, UNSUPPORTED, "exclusion"),
            ]
        )
        assert [c.id for c in result.criteria_set.criteria] == ["INC-01", "EXC-01"]

    def test_a_rejected_span_is_reported_with_the_reason_given(self):
        result, _ = compile_protocol(
            [
                span_reply(A1C_QUOTE, A1C),
                not_a_criterion("cross-reference, not a criterion"),
                span_reply(JUDGEMENT_QUOTE, UNSUPPORTED, "exclusion"),
            ]
        )
        assert len(result.rejected) == 1
        assert "cross-reference" in result.rejected[0].reason


class TestQuoteFidelityIsEnforced:
    def test_a_paraphrased_quote_downgrades_the_criterion(self):
        """The compiler does not get to rewrite the protocol on its way past the check."""
        result, _ = compile_protocol(
            [
                span_reply("Diabetes with an A1c of at least seven", A1C),
                span_reply(AGE_QUOTE, AGE),
                span_reply(JUDGEMENT_QUOTE, UNSUPPORTED, "exclusion"),
            ]
        )
        first = result.criteria_set.criteria[0]
        assert isinstance(first.predicate, UnsupportedPredicate)
        assert "quote" in first.predicate.reason.lower()

    def test_a_downgraded_criterion_keeps_its_place_and_its_identifier(self):
        result, _ = compile_protocol(
            [
                span_reply("Diabetes with an A1c of at least seven", A1C),
                span_reply(AGE_QUOTE, AGE),
                span_reply(JUDGEMENT_QUOTE, UNSUPPORTED, "exclusion"),
            ]
        )
        assert result.criteria_set.criteria[0].id == "INC-01"
        assert result.downgraded == ("INC-01",)

    def test_the_quote_the_model_returned_is_kept_for_the_reviewer_to_see(self):
        result, _ = compile_protocol(
            [
                span_reply("Diabetes with an A1c of at least seven", A1C),
                span_reply(AGE_QUOTE, AGE),
                span_reply(JUDGEMENT_QUOTE, UNSUPPORTED, "exclusion"),
            ]
        )
        assert result.criteria_set.criteria[0].notes is not None
        assert "at least seven" in result.criteria_set.criteria[0].notes


class TestCoverage:
    def test_every_span_is_accounted_for(self):
        result, _ = compile_protocol(
            three_good_replies()
        )
        assert result.spans_total == 3
        assert result.spans_unaccounted == ()

    def test_a_span_whose_call_failed_is_reported_rather_than_dropped(self):
        """A failed call is a hole in the protocol and has to be visible as one."""
        client, _ = a_routed_client(
            {
                "Type 2 diabetes": span_reply(A1C_QUOTE, A1C).content,
                "Age 18": "the model produced prose instead of json",
                "investigator": span_reply(JUDGEMENT_QUOTE, UNSUPPORTED, "exclusion").content,
            }
        )
        result = compile_criteria("NCT00000001", PROTOCOL, AgentContext(client=client))
        assert result.spans_unaccounted == (1,)
        assert len(result.failures) == 1


class TestChildSpans:
    def test_a_parent_and_its_children_are_compiled_as_one_criterion(self):
        text = (
            "Inclusion Criteria\n\n"
            "1. Moderate to severe COPD.\n"
            "   1. Post-bronchodilator FEV1/FVC ratio <0.70.\n"
            "   2. FEV1 between 30% and 70% predicted.\n"
        )
        composite = {
            "type": "all_of",
            "operands": [
                observation("FEV1/FVC ratio", "<", 0.7, "1"),
                observation("FEV1", "between", 30.0, "%") | {"value_high": 70.0},
            ],
        }
        result, transport = compile_protocol(
            [span_reply("Moderate to severe COPD.", composite)], text=text
        )
        assert len(transport.requests) == 1
        assert isinstance(result.criteria_set.criteria[0].predicate, CompositePredicate)

    def test_the_children_are_shown_to_the_model_with_the_parent(self):
        text = (
            "Inclusion Criteria\n\n"
            "1. Moderate to severe COPD.\n"
            "   1. Post-bronchodilator FEV1/FVC ratio <0.70.\n"
        )
        _, transport = compile_protocol(
            [span_reply("Moderate to severe COPD.", UNSUPPORTED)],
            text=text,
        )
        assert "FEV1/FVC" in transport.user_messages[0]


class TestTheSystemPrompt:
    def test_it_is_loaded_from_the_prompt_file(self):
        assert "unsupported" in COMPILER_SYSTEM_PROMPT
        assert len(COMPILER_SYSTEM_PROMPT) > 500

    def test_it_is_what_the_model_is_actually_sent(self):
        _, transport = compile_protocol(
            three_good_replies()
        )
        assert transport.requests[0]["messages"][0]["content"] == COMPILER_SYSTEM_PROMPT


class TestSegmentationIsExposed:
    def test_the_units_it_compiled_are_reported_for_review(self):
        result, _ = compile_protocol(
            three_good_replies()
        )
        assert [u.section for u in result.units] == [
            Section.INCLUSION,
            Section.INCLUSION,
            Section.EXCLUSION,
        ]


@pytest.mark.parametrize("bad", ["", "   ", "\n\n"])
def test_an_empty_protocol_compiles_to_nothing_rather_than_raising(bad):
    result, transport = compile_protocol([], text=bad)
    assert result.criteria_set.criteria == []
    assert transport.requests == []
