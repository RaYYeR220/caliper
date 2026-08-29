"""Turning protocol prose into executable criteria, one span at a time.

The compiler could be one call per protocol. It is one call per span instead, for three reasons
that all showed up in practice. A span is a bounded job, so the model spends its attention on the
criterion rather than on bookkeeping. A failure is contained: a span whose call never produced
valid output is a hole in exactly one criterion, and the hole is reported. And every span is
accounted for by construction, which is the only way to notice that a criterion has gone missing —
the failure mode that matters most here, because a patient screened against a protocol with a hole
in it looks exactly like a patient screened properly.

Two things the model is not allowed to decide. Identifiers are assigned in code, so they are stable
across runs and across models. And the inclusion-or-exclusion kind comes from the section heading
the span appeared under, not from the model's opinion of it: getting that wrong silently inverts a
criterion's meaning, and the segmenter already knows the answer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from importlib import resources

from caliper.agents.base import AgentContext
from caliper.criteria_text import CriterionSpan, Section, segment, unescape_registry_markdown
from caliper.ir import CriteriaSet, Criterion, UnsupportedPredicate, quote_fidelity_problems
from caliper.llm import LLMError
from caliper.wire import DEFAULT_DEPTH, wire_criteria_set_model, wire_span_model

COMPILER_SYSTEM_PROMPT = (
    resources.files("caliper.agents.prompts").joinpath("compiler.md").read_text(encoding="utf-8")
)

_KIND_FOR_SECTION = {Section.INCLUSION: "inclusion", Section.EXCLUSION: "exclusion"}


@dataclass(frozen=True)
class CompileUnit:
    """One span plus any sub-conditions nested under it, compiled together."""

    span_indices: tuple[int, ...]
    section: Section
    text: str
    child_texts: tuple[str, ...] = ()

    @property
    def index(self) -> int:
        return self.span_indices[0]


@dataclass(frozen=True)
class RejectedUnit:
    unit: CompileUnit
    reason: str


@dataclass(frozen=True)
class CompileFailure:
    unit: CompileUnit
    error: str


@dataclass(frozen=True)
class CompileResult:
    criteria_set: CriteriaSet
    units: tuple[CompileUnit, ...]
    rejected: tuple[RejectedUnit, ...]
    failures: tuple[CompileFailure, ...]
    downgraded: tuple[str, ...]
    unclaimed_spans: tuple[int, ...] = ()
    """Only meaningful for whole-protocol compilation, where a criterion can simply go missing."""

    @property
    def spans_total(self) -> int:
        return sum(len(u.span_indices) for u in self.units) + sum(
            len(f.unit.span_indices) for f in self.failures
        )

    @property
    def spans_unaccounted(self) -> tuple[int, ...]:
        """Spans whose criterion never materialised. Each one is a hole in the protocol."""
        failed = tuple(i for f in self.failures for i in f.unit.span_indices)
        return tuple(sorted(set(failed) | set(self.unclaimed_spans)))


def plan_units(spans: list[CriterionSpan]) -> list[CompileUnit]:
    """Group each top-level span with the sub-conditions nested beneath it.

    Sub-bullets qualify their parent rather than standing alone, so compiling them separately would
    produce criteria that are individually true and jointly wrong.
    """
    by_parent: dict[int, list[CriterionSpan]] = {}
    for span in spans:
        if span.parent_index is not None:
            by_parent.setdefault(span.parent_index, []).append(span)

    units = []
    for span in spans:
        if span.parent_index is not None:
            continue
        children = by_parent.get(span.index, [])
        units.append(
            CompileUnit(
                span_indices=(span.index, *(c.index for c in children)),
                section=span.section,
                text=span.text,
                child_texts=tuple(c.text for c in children),
            )
        )
    return units


def render_unit(unit: CompileUnit) -> str:
    lines = [f"Section: {unit.section.value}", "", "Criterion:", unit.text]
    if unit.child_texts:
        lines += ["", "Sub-conditions stated beneath it:"]
        lines += [f"- {child}" for child in unit.child_texts]
    return "\n".join(lines)


def _identifier(kind: str, ordinal: int) -> str:
    return f"{'INC' if kind == 'inclusion' else 'EXC'}-{ordinal:02d}"


def compile_criteria(
    nct_id: str,
    criteria_text: str,
    ctx: AgentContext,
    *,
    depth: int = DEFAULT_DEPTH,
    per_span: bool = True,
) -> CompileResult:
    """Compile a registry eligibility blob into a `CriteriaSet`.

    `per_span=False` is the obvious alternative — hand the model the whole protocol and take what
    comes back. It is kept so the choice can be measured rather than argued: see the whole-protocol
    arm in the evaluation, and the count of spans it leaves unaccounted for.
    """
    if not per_span:
        return _compile_whole(nct_id, criteria_text, ctx, depth)

    source_text = unescape_registry_markdown(criteria_text)
    spans = segment(source_text)
    units = plan_units(spans)
    span_model = wire_span_model(depth)

    criteria: list[Criterion] = []
    rejected: list[RejectedUnit] = []
    failures: list[CompileFailure] = []
    ordinals = {"inclusion": 0, "exclusion": 0}

    for unit in units:
        try:
            completion = ctx.client.complete(
                system=COMPILER_SYSTEM_PROMPT,
                user=render_unit(unit),
                model_cls=span_model,
                agent="compiler",
            )
        except LLMError as error:
            failures.append(CompileFailure(unit=unit, error=str(error)))
            continue

        span = completion.value
        if not span.is_criterion or span.predicate is None or not span.source_quote:
            rejected.append(RejectedUnit(unit=unit, reason=span.notes or "not a criterion"))
            continue

        kind = _KIND_FOR_SECTION.get(unit.section) or span.kind or "inclusion"
        ordinals[kind] += 1
        criteria.append(
            Criterion.model_validate(
                {
                    "id": _identifier(kind, ordinals[kind]),
                    "kind": kind,
                    "source_quote": span.source_quote,
                    "predicate": span.predicate.model_dump(mode="json"),
                    "notes": span.notes,
                }
            )
        )

    criteria_set = CriteriaSet(nct_id=nct_id, source_text=source_text, criteria=criteria)
    criteria_set, downgraded = _downgrade_unfaithful_quotes(criteria_set)

    return CompileResult(
        criteria_set=criteria_set,
        units=tuple(units),
        rejected=tuple(rejected),
        failures=tuple(failures),
        downgraded=downgraded,
    )


def _downgrade_unfaithful_quotes(criteria_set: CriteriaSet) -> tuple[CriteriaSet, tuple[str, ...]]:
    """Replace the predicate of any criterion whose quote is not in the protocol text.

    A quote that does not appear verbatim means the compiler rewrote the criterion before
    formalising it, and there is then no way to tell which version the predicate encodes. The
    criterion keeps its identifier and its place — it simply stops being answerable without a
    human, which is the honest outcome.
    """
    problems = {p.criterion_id: p for p in quote_fidelity_problems(criteria_set)}
    if not problems:
        return criteria_set, ()

    rewritten = []
    for criterion in criteria_set.criteria:
        if criterion.id not in problems:
            rewritten.append(criterion)
            continue
        note = f"compiler returned a quote absent from the protocol: {criterion.source_quote!r}"
        rewritten.append(
            criterion.model_copy(
                update={
                    "predicate": UnsupportedPredicate(
                        reason="the compiled quote does not appear in the protocol text"
                    ),
                    "notes": note if not criterion.notes else f"{criterion.notes}; {note}",
                }
            )
        )

    return (
        CriteriaSet(
            nct_id=criteria_set.nct_id,
            source_text=criteria_set.source_text,
            criteria=rewritten,
        ),
        tuple(sorted(problems)),
    )


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def _compile_whole(
    nct_id: str, criteria_text: str, ctx: AgentContext, depth: int
) -> CompileResult:
    """Compile a whole protocol in one call, the way the obvious implementation would.

    Kept as a measurable alternative rather than as a fallback. Two things go wrong here that the
    per-span loop makes impossible: a criterion can be dropped without anyone noticing, and a single
    failed response costs the entire trial rather than one criterion. Both are counted.
    """
    source_text = unescape_registry_markdown(criteria_text)
    spans = segment(source_text)
    units = plan_units(spans)
    all_spans = CompileUnit(
        span_indices=tuple(s.index for s in spans),
        section=Section.UNSPECIFIED,
        text=source_text,
    )

    try:
        completion = ctx.client.complete(
            system=COMPILER_SYSTEM_PROMPT,
            user="Compile every criterion in this protocol.\n\n" + source_text,
            model_cls=wire_criteria_set_model(depth),
            agent="compiler",
        )
    except LLMError as error:
        empty = CriteriaSet(nct_id=nct_id, source_text=source_text, criteria=[])
        return CompileResult(
            criteria_set=empty,
            units=tuple(units),
            rejected=(),
            failures=(CompileFailure(unit=all_spans, error=str(error)),),
            downgraded=(),
        )

    ordinals = {"inclusion": 0, "exclusion": 0}
    criteria: list[Criterion] = []
    for returned in completion.value.criteria:
        kind = returned.kind
        ordinals[kind] += 1
        criteria.append(
            Criterion.model_validate(
                {
                    "id": _identifier(kind, ordinals[kind]),
                    "kind": kind,
                    "source_quote": returned.source_quote,
                    "predicate": returned.predicate.model_dump(mode="json"),
                    "notes": returned.notes,
                }
            )
        )

    criteria_set = CriteriaSet(nct_id=nct_id, source_text=source_text, criteria=criteria)
    criteria_set, downgraded = _downgrade_unfaithful_quotes(criteria_set)

    quoted = [_normalise(c.source_quote) for c in criteria_set.criteria]
    unclaimed = tuple(
        span.index for span in spans if not any(_normalise(span.text) in q for q in quoted)
    )

    return CompileResult(
        criteria_set=criteria_set,
        units=tuple(units),
        rejected=(),
        failures=(),
        downgraded=downgraded,
        unclaimed_spans=unclaimed,
    )
