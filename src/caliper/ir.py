"""The compiled representation of a trial's eligibility criteria.

This module is the contract between the language model and the evaluator. The model's only job is
to produce a `CriteriaSet`; everything downstream operates on these objects and never on prose.
A criterion the model cannot faithfully formalise is not guessed at — it is recorded as
`UnsupportedPredicate`, which the evaluator treats as permanently unresolved.
"""

from __future__ import annotations

import hashlib
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

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
    """When the evidence has to have happened, and relative to what.

    Protocols anchor windows to screening, enrolment, randomisation, consent or first dose, and
    those are genuinely different dates — sometimes weeks apart. Caliper evaluates every window
    against the screening date because that is the only date it has, so the anchor is recorded
    rather than discarded: a criterion evaluated against the wrong anchor is reported as an
    approximation instead of passing silently.
    """

    relation: Literal["within", "before", "after", "ever", "current"]
    amount: int | None = Field(default=None, gt=0)
    unit: Literal["days", "weeks", "months", "years"] | None = None
    anchor: Literal["screening", "enrolment", "randomisation", "consent", "first_dose"] = (
        "screening"
    )

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
    """A criterion that cannot be honestly formalised. It stays unresolved forever, by design.

    `settlement` says *why* no chart can answer it, and the difference is load-bearing.

    A criterion settled `from_data` was a question about the patient's record that we failed to
    formalise — a threshold with no number, an open category. It is a gap, and it blocks a verdict.

    A criterion settled `at_visit` is not a gap at all. Signed informed consent, a procedure planned
    after randomisation, the investigator's own judgement of the patient in person: these have the
    same answer for every chart ever written, because they are settled when the patient comes in.
    Treating them as unresolved data made ELIGIBLE unreachable for every real protocol we hold — one
    consent criterion and the screening abstains, which is not caution but paralysis.

    The default is `from_data`, so a compiler that says nothing cannot thereby unblock a verdict.
    """

    type: Literal["unsupported"] = "unsupported"
    reason: str = Field(min_length=1)
    settlement: Literal["from_data", "at_visit"] = "from_data"


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


def concepts_in(criteria_set: CriteriaSet) -> list[Concept]:
    """Every distinct concept a trial's criteria mention, composites included.

    Terminology resolution is charged per concept, not per criterion, so this walk is what makes
    a trial mentioning creatinine six times cost one lookup.
    """
    seen: dict[str, Concept] = {}
    for criterion in criteria_set.criteria:
        for concept in concepts_of(criterion.predicate):
            seen.setdefault(concept.text, concept)
    return list(seen.values())


def concepts_of(predicate: Predicate) -> list[Concept]:
    """Every concept one predicate mentions, composites included, in the order they are written.

    Public because the review interface asks this per criterion while `concepts_in` asks it per
    trial. One walk, so a composite shape that this one handles and a copy of it did not cannot
    exist.
    """
    if isinstance(predicate, CompositePredicate):
        return [c for operand in predicate.operands for c in concepts_of(operand)]
    concept = getattr(predicate, "concept", None)
    return [concept] if concept is not None else []


def with_codes(criteria_set: CriteriaSet, codes: dict[str, tuple[Code, ...]]) -> CriteriaSet:
    """Return a copy in which every concept carries the codes resolved for its text."""
    return CriteriaSet(
        nct_id=criteria_set.nct_id,
        source_text=criteria_set.source_text,
        criteria=[
            criterion.model_copy(update={"predicate": _coded(criterion.predicate, codes)})
            for criterion in criteria_set.criteria
        ],
    )


def _coded(predicate: Predicate, codes: dict[str, tuple[Code, ...]]) -> Predicate:
    if isinstance(predicate, CompositePredicate):
        return predicate.model_copy(
            update={"operands": tuple(_coded(o, codes) for o in predicate.operands)}
        )
    concept = getattr(predicate, "concept", None)
    if concept is None or concept.text not in codes:
        return predicate
    resolved = concept.model_copy(update={"codes": tuple(codes[concept.text])})
    return predicate.model_copy(update={"concept": resolved})


class QuoteProblem(_Frozen):
    criterion_id: str
    quote: str
    reason: str


def normalise_quote_text(text: str) -> str:
    """Fold a quote and the text it is checked against into one comparable form.

    Public, and the only normalisation in the codebase, because the answer to "is this the same
    text" decides whether a criterion survives as a predicate or is downgraded to
    `UnsupportedPredicate`. Two implementations of that question are two different corpora.

    `casefold` rather than `lower`: `lower` is a per-character mapping and leaves the cases where a
    fold changes length alone, so German `ß` never equals `SS`. A protocol that writes *Straße* and
    a heading that writes *STRASSE* are the same word, and a check that downgrades a criterion over
    that has failed at the one job it has. Whitespace is collapsed and stripped for the same reason:
    a line break inside a registry bullet is not a paraphrase.
    """
    return " ".join(text.split()).casefold()


def quote_fidelity_problems(criteria_set: CriteriaSet) -> list[QuoteProblem]:
    """Find criteria whose `source_quote` is not actually in the protocol text.

    Case and whitespace are forgiven; wording is not. A model that paraphrases the protocol has
    already lost the thread, and we would rather catch it here than at the bedside.
    """
    haystack = normalise_quote_text(criteria_set.source_text)
    problems = []
    for criterion in criteria_set.criteria:
        if normalise_quote_text(criterion.source_quote) not in haystack:
            problems.append(
                QuoteProblem(
                    criterion_id=criterion.id,
                    quote=criterion.source_quote,
                    reason="quote is not present verbatim in the protocol text",
                )
            )
    return problems
