"""Depth-bounded mirrors of the criteria IR, for talking to a model.

`caliper.ir` is recursive because eligibility criteria are: a conjunction can hold a disjunction can
hold a comparison. Strict JSON-schema modes handle that badly — OpenAI-style strict subsets forbid
the `$ref` cycle outright, and Venice reports a schema it cannot compile as a request timeout rather
than an error, which is a miserable thing to debug at three in the morning.

So the model is handed the same structure unrolled to a fixed depth. Each level is a distinct
generated class whose operands are drawn from the level below, which terminates. The unrolled shape
is JSON-identical to the IR, so `to_criteria_set` re-validates the payload through the real models
and inherits every rule they enforce; nothing is trusted twice.

The depth ceiling is a real limitation, not a formality. A criterion nested deeper than the ceiling
does not get truncated — the compiler is instructed to record it as unsupported, and it goes to a
human.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, create_model, model_validator

from caliper.ir import (
    CriteriaSet,
    DemographicPredicate,
    ObservationPredicate,
    PresencePredicate,
    UnsupportedPredicate,
)

DEFAULT_DEPTH = 2

AtomPredicate = Annotated[
    ObservationPredicate | PresencePredicate | DemographicPredicate | UnsupportedPredicate,
    Field(discriminator="type"),
]


def _composite_model(level: int, operand_type: Any) -> type[BaseModel]:
    """One rung of the ladder: a composite whose operands come from the rung below."""

    def _arity(self: BaseModel) -> BaseModel:
        operands = self.operands  # type: ignore[attr-defined]
        if self.type == "not":  # type: ignore[attr-defined]
            if len(operands) != 1:
                raise ValueError("'not' takes exactly one operand")
        elif len(operands) < 2:
            raise ValueError("'all_of' and 'any_of' need at least two operands")
        return self

    return create_model(
        f"CompositePredicateL{level}",
        __config__=ConfigDict(extra="forbid"),
        __validators__={"_arity": model_validator(mode="after")(_arity)},
        type=(Literal["all_of", "any_of", "not"], ...),
        operands=(list[operand_type], ...),  # type: ignore[valid-type]
    )


@lru_cache(maxsize=8)
def wire_predicate_type(depth: int) -> Any:
    """The predicate union a model may use, allowing composites nested `depth` levels deep."""
    if depth < 0:
        raise ValueError("depth must not be negative")
    if depth == 0:
        return AtomPredicate

    below = wire_predicate_type(depth - 1)
    composite = _composite_model(depth, below)
    return Annotated[
        ObservationPredicate
        | PresencePredicate
        | DemographicPredicate
        | UnsupportedPredicate
        | composite,
        Field(discriminator="type"),
    ]


@lru_cache(maxsize=8)
def wire_criteria_set_model(depth: int = DEFAULT_DEPTH) -> type[BaseModel]:
    """The model class whose JSON schema is sent to the compiler.

    Note the absence of `source_text`: we already hold the protocol text, and asking a model to
    echo it back invites paraphrase into the one field the fidelity check depends on.
    """
    criterion = create_model(
        f"CriterionWireD{depth}",
        __doc__=(
            "One eligibility criterion, formalised. Use the 'unsupported' predicate whenever the "
            "criterion depends on clinical judgement, on information no chart would hold, or on "
            "nesting deeper than this schema allows."
        ),
        __config__=ConfigDict(extra="forbid"),
        id=(str, Field(description="Stable identifier, for example INC-01 or EXC-03.")),
        kind=(Literal["inclusion", "exclusion"], ...),
        source_quote=(
            str,
            Field(description="The criterion copied verbatim from the protocol text."),
        ),
        predicate=(wire_predicate_type(depth), ...),
        notes=(str | None, Field(default=None, description="Anything a reviewer should know.")),
    )
    return create_model(
        f"CriteriaSetWireD{depth}",
        __doc__=(
            "Every eligibility criterion of one trial, in the order it appears in the protocol. "
            "Quote each criterion verbatim; do not paraphrase, merge or reorder them."
        ),
        __config__=ConfigDict(extra="forbid"),
        nct_id=(str, ...),
        criteria=(list[criterion], ...),  # type: ignore[valid-type]
    )


@lru_cache(maxsize=8)
def wire_span_model(depth: int = DEFAULT_DEPTH) -> type[BaseModel]:
    """What the compiler returns for a single span of protocol text.

    The compiler works one span at a time rather than one protocol at a time. A span is a bounded
    job, a failure is contained to the criterion it belongs to, and — the reason that matters —
    every span is accounted for, so a criterion cannot go missing without the coverage check
    noticing. `is_criterion` is the escape hatch for the headers and registry boilerplate that a
    segmenter cannot reliably tell apart from criteria.
    """
    return create_model(
        f"SpanCompileD{depth}",
        __doc__=(
            "The result of formalising one span of eligibility text. Set is_criterion to false "
            "when the span is a heading, a note to readers, or registry boilerplate rather than a "
            "condition a patient can meet."
        ),
        __config__=ConfigDict(extra="forbid"),
        is_criterion=(bool, ...),
        kind=(
            Literal["inclusion", "exclusion"] | None,
            Field(
                default=None,
                description=(
                    "Only needed when the span sits under no inclusion or exclusion header."
                ),
            ),
        ),
        source_quote=(
            str | None,
            Field(default=None, description="The span copied verbatim, character for character."),
        ),
        predicate=(wire_predicate_type(depth) | None, Field(default=None)),
        notes=(
            str | None,
            Field(
                default=None,
                description="Why this span was hard, or why it is not a criterion.",
            ),
        ),
    )


def to_criteria_set(wire: BaseModel, *, source_text: str) -> CriteriaSet:
    """Re-validate a wire payload through the real IR and attach the protocol text we hold."""
    payload = wire.model_dump(mode="json")
    payload["source_text"] = source_text
    return CriteriaSet.model_validate(payload)
