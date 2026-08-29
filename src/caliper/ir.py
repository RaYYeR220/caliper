"""The compiled representation of a trial's eligibility criteria.

This module is the contract between the language model and the evaluator. The model's only job is
to produce a `CriteriaSet`; everything downstream operates on these objects and never on prose.
A criterion the model cannot faithfully formalise is not guessed at — it is recorded as
`UnsupportedPredicate`, which the evaluator treats as permanently unresolved.
"""

from __future__ import annotations

import hashlib
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

NUMERIC_OPS = ("<", "<=", ">", ">=", "==", "!=", "between")
EQUALITY_OPS = ("==", "!=")


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Code(_Frozen):
    """A terminology code. `system` is kept as a short name rather than a URI for legibility."""

    system: Literal["LOINC", "SNOMED", "RxNorm", "ICD10", "UCUM"]
    code: str = Field(min_length=1)
    display: str | None = None


class Concept(_Frozen):
    """A clinical concept as the protocol names it, plus whatever codes we resolved it to."""

    text: str = Field(min_length=1)
    codes: tuple[Code, ...] = ()


class TemporalWindow(_Frozen):
    """When the evidence has to have happened, relative to the screening date."""

    relation: Literal["within", "before", "after", "ever", "current"]
    amount: int | None = Field(default=None, gt=0)
    unit: Literal["days", "weeks", "months", "years"] | None = None

    @model_validator(mode="after")
    def _relative_windows_need_a_span(self) -> TemporalWindow:
        relative = self.relation in ("within", "before", "after")
        if relative and (self.amount is None or self.unit is None):
            raise ValueError(f"relation {self.relation!r} requires both amount and unit")
        if not relative and (self.amount is not None or self.unit is not None):
            raise ValueError(f"relation {self.relation!r} takes no amount or unit")
        return self


class ObservationPredicate(_Frozen):
    """A numeric comparison against a measurement: labs, vitals, scores."""

    type: Literal["observation"] = "observation"
    concept: Concept
    op: Literal["<", "<=", ">", ">=", "==", "!=", "between"]
    value: float
    value_high: float | None = None
    unit: str = Field(min_length=1)
    window: TemporalWindow | None = None

    @model_validator(mode="after")
    def _ranges_need_two_ordered_bounds(self) -> ObservationPredicate:
        if self.op == "between":
            if self.value_high is None:
                raise ValueError("op 'between' requires value_high")
            if self.value > self.value_high:
                raise ValueError("value must not exceed value_high")
        elif self.value_high is not None:
            raise ValueError("value_high is only meaningful for op 'between'")
        return self


class PresencePredicate(_Frozen):
    """Whether a coded thing is on the chart at all: a condition, a drug, a procedure."""

    type: Literal["condition", "medication", "procedure"]
    concept: Concept
    presence: Literal["present", "absent"]
    window: TemporalWindow | None = None


class DemographicPredicate(_Frozen):
    """Age and sex, which come from the patient resource rather than from clinical events."""

    type: Literal["demographic"] = "demographic"
    field: Literal["age", "sex"]
    op: Literal["<", "<=", ">", ">=", "==", "!="]
    value: float | str
    unit: str | None = None

    @model_validator(mode="after")
    def _age_is_ordered_and_sex_is_not(self) -> DemographicPredicate:
        if self.field == "age":
            if not isinstance(self.value, (int, float)):
                raise ValueError("age must be compared against a number")
            if self.unit is None:
                raise ValueError("age requires a unit")
        else:
            if self.op not in EQUALITY_OPS:
                raise ValueError(f"sex supports only {EQUALITY_OPS}, got {self.op!r}")
            if not isinstance(self.value, str):
                raise ValueError("sex must be compared against a string")
        return self


class UnsupportedPredicate(_Frozen):
    """A criterion that cannot be honestly formalised. It stays unresolved forever, by design."""

    type: Literal["unsupported"] = "unsupported"
    reason: str = Field(min_length=1)


class CompositePredicate(_Frozen):
    """Several predicates combined. Protocols rarely put one assertion in one bullet.

    The IR is recursive because criteria are; the schema we send a model is not, because strict
    JSON-schema modes handle `$ref` cycles badly. `unrolled_predicate_schema` in `wire.py` flattens
    this to a fixed depth, and anything deeper is compiled as unsupported rather than truncated.
    """

    type: Literal["all_of", "any_of", "not"]
    operands: tuple[Predicate, ...]

    @model_validator(mode="after")
    def _arity_matches_the_operator(self) -> CompositePredicate:
        if self.type == "not":
            if len(self.operands) != 1:
                raise ValueError("'not' takes exactly one operand")
        elif len(self.operands) < 2:
            raise ValueError(f"{self.type!r} needs at least two operands")
        return self


Predicate = Annotated[
    ObservationPredicate
    | PresencePredicate
    | DemographicPredicate
    | UnsupportedPredicate
    | CompositePredicate,
    Field(discriminator="type"),
]

CompositePredicate.model_rebuild()


def max_predicate_depth(predicate: Predicate) -> int:
    """How deeply composites nest. Atoms are depth 0."""
    if not isinstance(predicate, CompositePredicate):
        return 0
    return 1 + max(max_predicate_depth(operand) for operand in predicate.operands)


class Criterion(_Frozen):
    id: str = Field(min_length=1)
    kind: Literal["inclusion", "exclusion"]
    source_quote: str
    predicate: Predicate
    notes: str | None = None

    @model_validator(mode="after")
    def _the_quote_must_carry_content(self) -> Criterion:
        if not self.source_quote.strip():
            raise ValueError("source_quote may not be blank")
        return self


class CriteriaSet(BaseModel):
    """One trial's criteria, compiled, fingerprinted against the protocol text they came from."""

    model_config = ConfigDict(extra="forbid")

    nct_id: str = Field(min_length=1)
    source_text: str
    criteria: list[Criterion] = Field(default_factory=list)

    @model_validator(mode="after")
    def _ids_must_be_unique(self) -> CriteriaSet:
        ids = [c.id for c in self.criteria]
        duplicates = {i for i in ids if ids.count(i) > 1}
        if duplicates:
            raise ValueError(f"duplicate criterion ids: {sorted(duplicates)}")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def source_text_sha256(self) -> str:
        return hashlib.sha256(self.source_text.encode("utf-8")).hexdigest()

    @property
    def unsupported_count(self) -> int:
        return sum(1 for c in self.criteria if c.predicate.type == "unsupported")


class QuoteProblem(_Frozen):
    criterion_id: str
    quote: str
    reason: str


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def quote_fidelity_problems(criteria_set: CriteriaSet) -> list[QuoteProblem]:
    """Find criteria whose `source_quote` is not actually in the protocol text.

    Case and whitespace are forgiven; wording is not. A model that paraphrases the protocol has
    already lost the thread, and we would rather catch it here than at the bedside.
    """
    haystack = _normalise(criteria_set.source_text)
    problems = []
    for criterion in criteria_set.criteria:
        if _normalise(criterion.source_quote) not in haystack:
            problems.append(
                QuoteProblem(
                    criterion_id=criterion.id,
                    quote=criterion.source_quote,
                    reason="quote is not present verbatim in the protocol text",
                )
            )
    return problems
