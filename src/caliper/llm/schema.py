"""Turning a Pydantic model into a schema a provider's strict mode will actually accept.

Strict structured output is a much smaller language than JSON Schema. Every object must forbid
additional properties, every declared property must be required, and most validation keywords —
`minLength`, `default`, `const`, `oneOf`, `discriminator` — are not part of the dialect. Pydantic
emits all of them.

The transform below rewrites the generated schema into that subset. Nothing is lost by dropping
the constraints: the provider's schema is a steering aid, and the real gate is
`Model.model_validate_json`, which still applies every validator the model declares.

Venice reports a malformed schema as a request timeout rather than a 400, so
`strict_schema_problems` exists to catch the mistake locally, before a call is made.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from caliper.llm.errors import LLMError

# Keywords that a strict-mode endpoint will either reject or silently ignore. They are stripped
# on the way out and flagged on the way in.
UNSUPPORTED_KEYWORDS = frozenset(
    {
        "oneOf",
        "allOf",
        "not",
        "discriminator",
        "default",
        "const",
        "pattern",
        "minLength",
        "maxLength",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "minItems",
        "maxItems",
        "uniqueItems",
        "patternProperties",
        "propertyNames",
    }
)

_SIMPLE_TYPES = frozenset({"string", "number", "integer", "boolean", "null"})
_DEFS = "$defs"


class StrictSchemaError(LLMError):
    """A model's schema cannot be expressed in a provider's strict dialect."""


def to_strict_schema(model: type[BaseModel], *, inline_refs: bool = True) -> dict[str, Any]:
    """Build a strict-mode JSON schema for `model`.

    With `inline_refs` (the default) every `$ref` is expanded in place, which suits providers
    whose strict mode does not resolve references. Recursive models cannot be inlined and raise
    `StrictSchemaError`; pass `inline_refs=False` to keep `$defs` intact for them.
    """
    raw = model.model_json_schema()
    defs = raw.pop(_DEFS, {})

    # A self-referencing model is emitted as a bare `$ref` into `$defs`. The root has to be a
    # concrete object either way, so resolve that one hop by hand.
    stack: tuple[str, ...] = ()
    if "$ref" in raw:
        name = raw["$ref"].rsplit("/", 1)[-1]
        if name in defs:
            stack, raw = (name,), defs[name]

    root: dict[str, Any] = _convert(raw, defs, stack, inline_refs)
    if root.get("type") != "object":
        raise StrictSchemaError(f"{model.__name__} does not serialise to a JSON object")

    if not inline_refs and defs:
        root[_DEFS] = {name: _convert(body, defs, (), False) for name, body in defs.items()}
    return root


def strict_schema_problems(schema: dict[str, Any]) -> list[str]:
    """Describe every reason `schema` would be rejected by a strict-mode endpoint.

    An empty list means the schema is safe to send. This is deliberately independent of
    `to_strict_schema` so that it can catch a regression in the transform itself.
    """
    problems: list[str] = []
    _inspect(schema, schema, "$", problems)
    return problems


def _convert(
    node: Any,
    defs: dict[str, Any],
    stack: tuple[str, ...],
    inline: bool,
) -> Any:
    if isinstance(node, list):
        return [_convert(item, defs, stack, inline) for item in node]
    if not isinstance(node, dict):
        return node

    if "$ref" in node:
        return _convert_ref(node["$ref"], defs, stack, inline)
    if "allOf" in node:
        return _convert_all_of(node, defs, stack, inline)

    branches = node.get("anyOf") or node.get("oneOf")
    if branches:
        return _convert_union(node, branches, defs, stack, inline)
    if node.get("type") == "object" or "properties" in node:
        return _convert_object(node, defs, stack, inline)
    if node.get("type") == "array":
        return _convert_array(node, defs, stack, inline)
    return _convert_scalar(node)


def _convert_ref(ref: str, defs: dict[str, Any], stack: tuple[str, ...], inline: bool) -> Any:
    name = ref.rsplit("/", 1)[-1]
    if not inline:
        return {"$ref": ref}
    if name in stack:
        raise StrictSchemaError(
            f"{name} is recursive and cannot be inlined; build the schema with inline_refs=False"
        )
    if name not in defs:
        raise StrictSchemaError(f"unresolved reference {ref!r}")
    return _convert(defs[name], defs, (*stack, name), inline)


def _convert_all_of(
    node: dict[str, Any],
    defs: dict[str, Any],
    stack: tuple[str, ...],
    inline: bool,
) -> Any:
    members = node["allOf"]
    if len(members) != 1:
        raise StrictSchemaError("allOf with more than one member cannot be made strict")
    merged = _convert(members[0], defs, stack, inline)
    if isinstance(merged, dict) and "description" in node and "description" not in merged:
        merged["description"] = node["description"]
    return merged


def _convert_union(
    node: dict[str, Any],
    branches: list[Any],
    defs: dict[str, Any],
    stack: tuple[str, ...],
    inline: bool,
) -> dict[str, Any]:
    """Rewrite a union as `anyOf`, collapsing the scalar case into a type list.

    A discriminated union loses its `discriminator` keyword — no strict dialect accepts it — but
    not its meaning: each branch still pins the tag property to a literal, so the union stays
    unambiguous, and Pydantic re-applies the real discriminator at the validation gate.
    """
    converted = [_convert(branch, defs, stack, inline) for branch in branches]
    types = [b["type"] for b in converted if set(b) == {"type"} and b["type"] in _SIMPLE_TYPES]
    if len(types) == len(converted):
        collapsed: dict[str, Any] = {"type": list(dict.fromkeys(types))}
        if "description" in node:
            collapsed["description"] = node["description"]
        return collapsed

    union: dict[str, Any] = {}
    if "description" in node:
        union["description"] = node["description"]
    union["anyOf"] = converted
    return union


def _convert_object(
    node: dict[str, Any],
    defs: dict[str, Any],
    stack: tuple[str, ...],
    inline: bool,
) -> dict[str, Any]:
    properties = node.get("properties")
    if not properties:
        raise StrictSchemaError(
            "an object with no declared properties cannot be made strict; "
            "give the field an explicit model instead of a free-form mapping"
        )
    out: dict[str, Any] = {"type": "object"}
    if "description" in node:
        out["description"] = node["description"]
    out["properties"] = {
        name: _convert(value, defs, stack, inline) for name, value in properties.items()
    }
    # Strict mode has no notion of an optional property: everything is required, and absence is
    # expressed by widening the value's type to include null.
    out["required"] = list(out["properties"])
    out["additionalProperties"] = False
    return out


def _convert_array(
    node: dict[str, Any],
    defs: dict[str, Any],
    stack: tuple[str, ...],
    inline: bool,
) -> dict[str, Any]:
    items = node.get("items")
    if items is None:
        raise StrictSchemaError("an array without an item schema cannot be made strict")
    out: dict[str, Any] = {"type": "array"}
    if "description" in node:
        out["description"] = node["description"]
    out["items"] = _convert(items, defs, stack, inline)
    return out


def _convert_scalar(node: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if "const" in node:
        # A literal is a one-value enum, which every strict dialect understands.
        value = node["const"]
        out["type"] = node.get("type") or _json_type_of(value)
        out["enum"] = [value]
    elif "enum" in node:
        if "type" in node:
            out["type"] = node["type"]
        out["enum"] = list(node["enum"])
    elif "type" in node:
        out["type"] = node["type"]
    else:
        raise StrictSchemaError(f"cannot make an untyped schema strict: {node!r}")

    if "description" in node:
        out["description"] = node["description"]
    return out


def _json_type_of(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if value is None:
        return "null"
    return "string"


def _inspect(node: Any, root: dict[str, Any], path: str, problems: list[str]) -> None:
    if isinstance(node, list):
        for index, item in enumerate(node):
            _inspect(item, root, f"{path}[{index}]", problems)
        return
    if not isinstance(node, dict):
        return

    for keyword in sorted(UNSUPPORTED_KEYWORDS & set(node)):
        problems.append(f"{path}: unsupported keyword {keyword!r}")

    if "$ref" in node:
        name = node["$ref"].rsplit("/", 1)[-1]
        if name not in root.get(_DEFS, {}):
            problems.append(f"{path}: dangling reference {node['$ref']!r}")

    if "properties" in node:
        if node.get("additionalProperties") is not False:
            problems.append(f"{path}: additionalProperties must be false")
        declared = set(node["properties"])
        required = set(node.get("required", []))
        if required != declared:
            missing = ", ".join(sorted(declared - required)) or "none"
            problems.append(f"{path}: required must list every property; missing: {missing}")

    for key, value in node.items():
        if key in {"required", "enum"}:
            continue
        _inspect(value, root, f"{path}.{key}", problems)


def count_union_parameters(schema: Any) -> int:
    """How many parameters in a strict schema carry a union type.

    Strict modes compile a schema before generating against it, and a union multiplies the states
    that compilation has to consider. Providers therefore cap the count — Venice at sixteen — and
    strict mode makes the number worse than it looks, because every optional field becomes a null
    union. Counting it lets a profile decline a rung it knows will be refused.
    """
    if isinstance(schema, dict):
        here = 1 if isinstance(schema.get("type"), list) or "anyOf" in schema else 0
        return here + sum(count_union_parameters(v) for v in schema.values())
    if isinstance(schema, list):
        return sum(count_union_parameters(v) for v in schema)
    return 0
