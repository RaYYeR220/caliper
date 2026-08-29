"""The schema we actually send a model.

The IR is recursive because criteria are. Strict JSON-schema modes are not: a `$ref` cycle either
gets rejected or, on Venice, surfaces as a timeout rather than an error. So the wire schema is the
IR unrolled to a fixed depth — no cycles, no `$ref` into itself, and a hard ceiling on how deeply a
model may nest a criterion before it has to admit it cannot formalise it.

The unrolled models are shape-compatible with the IR, so the JSON that satisfies one validates as
the other. That is the property worth testing: the bound is on the schema, not on the meaning.
"""

import json

from caliper.ir import CriteriaSet, max_predicate_depth
from caliper.llm import to_strict_schema
from caliper.wire import to_criteria_set, wire_criteria_set_model

ATOM = {
    "type": "observation",
    "concept": {"text": "eGFR", "codes": [{"system": "LOINC", "code": "33914-3", "display": None}]},
    "op": ">=",
    "value": 25.0,
    "value_high": None,
    "unit": "mL/min/1.73m2",
    "window": None,
}


def criterion(predicate: dict) -> dict:
    return {
        "id": "INC-01",
        "kind": "inclusion",
        "source_quote": "eGFR >= 25",
        "predicate": predicate,
        "notes": None,
    }


def composite(kind: str, *operands: dict) -> dict:
    return {"type": kind, "operands": list(operands)}


class TestDepthBound:
    def test_a_flat_criterion_validates_at_every_depth(self):
        for depth in (0, 1, 2):
            model = wire_criteria_set_model(depth)
            model.model_validate({"nct_id": "NCT1", "criteria": [criterion(ATOM)]})

    def test_depth_zero_refuses_a_composite(self):
        model = wire_criteria_set_model(0)
        payload = {"nct_id": "NCT1", "criteria": [criterion(composite("all_of", ATOM, ATOM))]}
        assert not _validates(model, payload)

    def test_depth_one_accepts_a_composite_of_atoms(self):
        model = wire_criteria_set_model(1)
        payload = {"nct_id": "NCT1", "criteria": [criterion(composite("all_of", ATOM, ATOM))]}
        model.model_validate(payload)

    def test_depth_one_refuses_a_composite_inside_a_composite(self):
        model = wire_criteria_set_model(1)
        nested = composite("all_of", ATOM, composite("any_of", ATOM, ATOM))
        assert not _validates(model, {"nct_id": "NCT1", "criteria": [criterion(nested)]})

    def test_depth_two_accepts_one_level_of_nesting(self):
        model = wire_criteria_set_model(2)
        nested = composite("all_of", ATOM, composite("any_of", ATOM, ATOM))
        model.model_validate({"nct_id": "NCT1", "criteria": [criterion(nested)]})


class TestStrictSchemaCompatibility:
    def test_the_wire_schema_survives_the_strict_transform(self):
        """The recursive IR does not, which is the entire reason this module exists."""
        schema = to_strict_schema(wire_criteria_set_model(2))
        assert schema["additionalProperties"] is False

    def test_the_wire_schema_contains_no_self_reference(self):
        text = json.dumps(to_strict_schema(wire_criteria_set_model(2)))
        assert "$ref" not in text

    def test_the_schema_is_stable_across_calls(self):
        once = to_strict_schema(wire_criteria_set_model(2))
        again = to_strict_schema(wire_criteria_set_model(2))
        assert json.dumps(once) == json.dumps(again)

    def test_the_wire_schema_does_not_ask_the_model_for_the_protocol_text(self):
        """We already hold the source text; asking a model to echo it invites paraphrase."""
        schema = to_strict_schema(wire_criteria_set_model(1))
        assert "source_text" not in schema["properties"]


class TestConversionToTheRealIR:
    def test_a_validated_wire_object_becomes_a_criteria_set(self):
        model = wire_criteria_set_model(2)
        nested = composite("all_of", ATOM, composite("any_of", ATOM, ATOM))
        wire = model.model_validate({"nct_id": "NCT1", "criteria": [criterion(nested)]})
        result = to_criteria_set(wire, source_text="eGFR >= 25")
        assert isinstance(result, CriteriaSet)
        assert result.nct_id == "NCT1"
        assert max_predicate_depth(result.criteria[0].predicate) == 2

    def test_the_source_text_comes_from_us_not_from_the_model(self):
        model = wire_criteria_set_model(1)
        wire = model.model_validate({"nct_id": "NCT1", "criteria": [criterion(ATOM)]})
        result = to_criteria_set(wire, source_text="the real protocol text")
        assert result.source_text == "the real protocol text"

    def test_conversion_enforces_the_full_ir_rules(self):
        """A wire payload that the IR would reject must not slip through the conversion."""
        model = wire_criteria_set_model(1)
        payload = {"nct_id": "NCT1", "criteria": [criterion(ATOM), criterion(ATOM)]}
        wire = model.model_validate(payload)
        assert _raises(lambda: to_criteria_set(wire, source_text="x"))


def _validates(model, payload) -> bool:
    try:
        model.model_validate(payload)
    except Exception:
        return False
    return True


def _raises(fn) -> bool:
    try:
        fn()
    except Exception:
        return True
    return False
