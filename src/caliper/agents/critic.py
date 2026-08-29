"""Checking that a compiled criterion still means what the protocol said.

The compiler turns prose into a predicate. Nothing before this module checks that the predicate
says the same thing as the prose, and "ask the model whether it is happy with its own output" is
not a check — it is the same judgement, taken twice, by the same party.

So the round trip is split in half. `render_predicate` renders the compiled predicate back into
English **deterministically, in code, with no model involved**. Only then is a model asked one
narrow question: does this English sentence say the same thing as this protocol quote? The model
never sees the JSON. It compares two sentences, which is a far easier job than auditing a data
structure, and a far more checkable one — a rendering that reads wrong is wrong in front of a human
reader too. It also removes the failure mode this check exists to catch: familiar-looking JSON is
exactly what a compiler mistake hides behind, because a model reading a well-formed object tends to
read the object's intent rather than its content.

The verdict is applied by `apply_findings`, and it fails closed. Anything other than `equivalent`
replaces the criterion's predicate with `UnsupportedPredicate`, which the evaluator treats as
permanently unresolved, and the case goes to a human. `narrower` is a downgrade for the same reason
`broader` is: a criterion tighter than the protocol screens out patients the trial wanted.

`coverage_report` answers the other half of the question, and needs no model at all. Round-tripping
every compiled criterion says nothing about a criterion that was never compiled. It segments the
protocol text, works out which spans some criterion claims, and reports the ones nobody claimed.
A dropped bullet is the most dangerous compiler failure there is, because the screening then runs
against a protocol with a hole in it and every remaining criterion looks fine.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from caliper.agents.base import AgentContext
from caliper.criteria_text import CriterionSpan, segment
from caliper.ir import (
    CompositePredicate,
    CriteriaSet,
    Criterion,
    DemographicPredicate,
    ObservationPredicate,
    Predicate,
    PresencePredicate,
    QuoteProblem,
    TemporalWindow,
    UnsupportedPredicate,
    quote_fidelity_problems,
)

AGENT_NAME = "critic"
PROMPT_FILE = "critic.md"

Severity = Literal["equivalent", "narrower", "broader", "contradicts"]

DEFAULT_ANCHOR = "screening"

# How each anchor the IR allows is said in English. Naming the real one is the point: the evaluator
# resolves every window against the screening date whatever it is anchored to, so the anchor is the
# one part of a window that survives compilation without being checked by anything downstream. A
# criterion reading "within 12 weeks prior to randomisation" that was compiled with the screening
# anchor renders as a sentence about screening, and the model can see that against the quote.
ANCHOR_PHRASES: dict[str, str] = {
    "screening": "screening",
    "enrolment": "enrolment",
    "randomisation": "randomisation",
    "consent": "consent",
    "first_dose": "the first dose",
}

_COMPARISONS: dict[str, str] = {
    "<": "below",
    "<=": "at most",
    ">": "above",
    ">=": "at least",
    "==": "exactly",
    "!=": "other than",
}

_PRESENCE_NOUNS: dict[str, str] = {
    "condition": "documented diagnosis of {}",
    "medication": "documented prescription for {}",
    "procedure": "documented {} procedure",
}

_DOWNGRADE_PHRASES: dict[str, str] = {
    "narrower": "is narrower than the protocol quote",
    "broader": "is broader than the protocol quote",
    "contradicts": "contradicts the protocol quote",
}


class BackTranslation(BaseModel):
    """The model's answer to the one question it is asked.

    Deliberately flat and three fields wide: it has to survive `to_strict_schema`, and a critic
    with room to elaborate is a critic that elaborates instead of deciding.
    """

    model_config = ConfigDict(extra="forbid")

    agrees: bool = Field(
        description="True only if the rendered sentence says the same thing as the protocol quote."
    )
    severity: Severity = Field(
        description=(
            "How the rendered sentence relates to the protocol quote: 'equivalent' if it admits "
            "exactly the same patients, 'narrower' if it admits strictly fewer, 'broader' if it "
            "admits strictly more, 'contradicts' otherwise."
        )
    )
    reason: str = Field(
        min_length=1,
        description="One sentence naming the specific difference, or stating that there is none.",
    )


@dataclass(frozen=True)
class Finding:
    """What one criterion's round trip produced, and what was compared to produce it."""

    criterion_id: str
    severity: Severity
    reason: str
    rendered: str
    quote: str

    @property
    def is_downgrade(self) -> bool:
        return self.severity != "equivalent"


@dataclass(frozen=True)
class Coverage:
    """Which spans of the protocol some criterion claims, and which nobody does."""

    total_spans: int
    claimed_span_indices: tuple[int, ...]
    unclaimed_spans: tuple[CriterionSpan, ...]
    quote_problems: tuple[QuoteProblem, ...]

    @property
    def coverage(self) -> float:
        """Claimed spans over total. A protocol with nothing to claim is vacuously covered."""
        if self.total_spans == 0:
            return 1.0
        return len(self.claimed_span_indices) / self.total_spans

    @property
    def unclaimed_span_indices(self) -> tuple[int, ...]:
        return tuple(span.index for span in self.unclaimed_spans)

    @property
    def unclaimed_span_texts(self) -> tuple[str, ...]:
        return tuple(span.text for span in self.unclaimed_spans)

    def to_markdown(self) -> str:
        headline = (
            f"{len(self.claimed_span_indices)} of {self.total_spans} protocol spans claimed "
            f"({self.coverage * 100:.0f}%)."
        )
        return "\n".join(_coverage_section(headline, self.unclaimed_spans, self.quote_problems))


@dataclass(frozen=True)
class CriticReport:
    """Everything the critic found: per-criterion verdicts, plus what the compiler never saw."""

    findings: tuple[Finding, ...]
    coverage: float
    unclaimed_spans: tuple[CriterionSpan, ...]
    quote_problems: tuple[QuoteProblem, ...]

    @classmethod
    def from_coverage(cls, findings: tuple[Finding, ...], coverage: Coverage) -> CriticReport:
        return cls(
            findings=tuple(findings),
            coverage=coverage.coverage,
            unclaimed_spans=coverage.unclaimed_spans,
            quote_problems=coverage.quote_problems,
        )

    @property
    def downgrades(self) -> tuple[Finding, ...]:
        return tuple(finding for finding in self.findings if finding.is_downgrade)

    def to_markdown(self) -> str:
        out = ["# Critic report", "", "## Back-translation", ""]
        if not self.findings:
            out += ["No criterion carried a predicate to verify.", ""]
        else:
            out += ["| Criterion | Verdict | Compared against | Reason |", "|---|---|---|---|"]
            out += [
                f"| {f.criterion_id} | `{f.severity}` | {_cell(f.rendered)} | {_cell(f.reason)} |"
                for f in self.findings
            ]
            out += ["", f"{len(self.downgrades)} of {len(self.findings)} would be downgraded.", ""]
        headline = f"{self.coverage * 100:.0f}% of protocol spans are claimed by some criterion."
        out += _coverage_section(headline, self.unclaimed_spans, self.quote_problems)
        return "\n".join(out)


# ------------------------------------------------------------------------------------------------
# Rendering. No model, no I/O, no randomness: the same predicate always produces the same sentence.
# ------------------------------------------------------------------------------------------------


def render_predicate(predicate: Predicate) -> str:
    """Render a compiled predicate as an English phrase, deterministically.

    The output is what a model is asked to compare against the protocol quote, so it has to state
    everything the predicate decides — the bound and whether it is inclusive, the unit, the span of
    any window and what that window is anchored to — and nothing the predicate does not decide.
    """
    if isinstance(predicate, ObservationPredicate):
        return _with_window(
            f"{predicate.concept.text} {_comparison(predicate)}", predicate.window, "measured"
        )
    if isinstance(predicate, PresencePredicate):
        noun = _PRESENCE_NOUNS[predicate.type].format(predicate.concept.text)
        article = "a" if predicate.presence == "present" else "no"
        return _with_window(f"{article} {noun}", predicate.window, "recorded")
    if isinstance(predicate, DemographicPredicate):
        return _demographic(predicate)
    if isinstance(predicate, UnsupportedPredicate):
        return f"not formalised: {predicate.reason}"
    if isinstance(predicate, CompositePredicate):
        return _composite(predicate)
    raise TypeError(f"no rendering for predicate type {type(predicate).__name__}")


def _composite(predicate: CompositePredicate) -> str:
    if predicate.type == "not":
        # Always bracketed: the scope of a negation is the one thing a reader must not have to
        # guess at, and an unbracketed "not" over a conjunction reads as covering only its head.
        return f"not ({render_predicate(predicate.operands[0])})"
    joiner = " and " if predicate.type == "all_of" else " or "
    return joiner.join(_operand(operand) for operand in predicate.operands)


def _operand(operand: Predicate) -> str:
    """Bracket anything whose own punctuation could be read as belonging to the joiner."""
    rendered = render_predicate(operand)
    if isinstance(operand, CompositePredicate) or "," in rendered:
        return f"({rendered})"
    return rendered


def _comparison(predicate: ObservationPredicate) -> str:
    if predicate.op == "between":
        assert predicate.value_high is not None  # enforced by the model's own validator
        low, high = _number(predicate.value), _number(predicate.value_high)
        return f"between {low} and {_unit(high, predicate.unit)} inclusive"
    value = _unit(_number(predicate.value), predicate.unit)
    return f"{_COMPARISONS[predicate.op]} {value}"


def _demographic(predicate: DemographicPredicate) -> str:
    if predicate.field == "sex":
        negation = "" if predicate.op == "==" else "not "
        return f"sex is {negation}{predicate.value}"
    value = _unit(_number(predicate.value), predicate.unit or "")
    return f"age {_COMPARISONS[predicate.op]} {value}"


def _with_window(base: str, window: TemporalWindow | None, verb: str) -> str:
    if window is None:
        return base
    return f"{base}, {_window(window, verb)}"


def _window(window: TemporalWindow, verb: str) -> str:
    if window.relation == "ever":
        return f"{verb} at any time in the patient's record"
    if window.relation == "current":
        return f"current as of {ANCHOR}"

    assert window.amount is not None and window.unit is not None  # enforced by the IR
    unit = window.unit[:-1] if window.amount == 1 else window.unit
    span = f"{window.amount} {unit}"
    if window.relation == "within":
        return f"{verb} within the {span} before {ANCHOR}"
    if window.relation == "before":
        return f"{verb} more than {span} before {ANCHOR}"
    return f"{verb} less than {span} before {ANCHOR}"


def _number(value: float | str) -> str:
    """Render a number the way a protocol writes it: 18 rather than 18.0, 1.5 unchanged."""
    if isinstance(value, str):
        return value
    return str(int(value)) if float(value).is_integer() else str(value)


def _unit(value: str, unit: str) -> str:
    """Join a value to its unit, closing up the ones written as symbols: 70%, but 1.5 mg/dL."""
    if not unit:
        return value
    return f"{value}{unit}" if not unit[0].isalnum() else f"{value} {unit}"


# ------------------------------------------------------------------------------------------------
# Back-translation.
# ------------------------------------------------------------------------------------------------


@lru_cache(maxsize=1)
def critic_prompt() -> str:
    """The comparison instructions, shipped alongside the code that uses them."""
    return (
        resources.files("caliper.agents")
        .joinpath("prompts", PROMPT_FILE)
        .read_text(encoding="utf-8")
    )


def comparison_request(quote: str, rendered: str) -> str:
    """The two sentences, labelled, and nothing else. No JSON reaches the model from here.

    Nothing is said here about what B was compiled from or what vocabulary it was rendered with.
    A hint that the anchor is fixed by the IR would excuse the one mistake this check is best
    placed to catch — a window that no longer measures from the date the protocol measured from.
    """
    return (
        "Sentence A, quoted from the protocol:\n"
        f"{quote.strip()}\n\n"
        "Sentence B, the compiled predicate rendered back into English:\n"
        f"{rendered}\n\n"
        "Does B say the same thing as A?"
    )


def back_translate(criterion: Criterion, ctx: AgentContext) -> Finding:
    """Render one criterion back into English and ask whether it still says what the protocol did.

    A model call that never validates raises out of here rather than being caught. An unreachable
    provider is an infrastructure failure, and turning it into a clinical verdict — in either
    direction — would be worse than stopping.
    """
    rendered = render_predicate(criterion.predicate)
    completion = ctx.client.complete(
        system=critic_prompt(),
        user=comparison_request(criterion.source_quote, rendered),
        model_cls=BackTranslation,
        agent=AGENT_NAME,
    )
    verdict = completion.value

    severity: Severity = verdict.severity
    if not verdict.agrees and severity == "equivalent":
        # A response at war with itself is not an agreement. Read it the safe way round.
        severity = "contradicts"

    return Finding(
        criterion_id=criterion.id,
        severity=severity,
        reason=verdict.reason.strip(),
        rendered=rendered,
        quote=criterion.source_quote,
    )


def review(criteria_set: CriteriaSet, ctx: AgentContext) -> CriticReport:
    """Back-translate every compiled criterion, and audit what the compiler left behind.

    A criterion already recorded as unsupported is skipped: there is no compiled meaning to verify,
    and a model asked to compare a protocol quote against "not formalised" will invent an opinion
    about a criterion nobody claimed to have formalised.

    Each criterion that is reviewed costs exactly one `LLMClient.complete` call, so the trajectory
    gains one step per criterion, carrying both sentences that were compared and the verdict that
    came back.
    """
    findings = tuple(
        back_translate(criterion, ctx)
        for criterion in criteria_set.criteria
        if not isinstance(criterion.predicate, UnsupportedPredicate)
    )
    return CriticReport.from_coverage(findings, coverage_report(criteria_set))


def apply_findings(criteria_set: CriteriaSet, report: CriticReport) -> CriteriaSet:
    """Return a copy in which every criterion that failed its round trip is unresolved.

    Fail closed. `narrower`, `broader` and `contradicts` are all downgrades, because all three mean
    the executable criterion admits a different set of patients than the protocol wrote down. The
    criterion keeps its identity, its kind and its quote so a human reviewer can pick it up.
    """
    downgrades = {finding.criterion_id: finding for finding in report.downgrades}
    criteria = []
    for criterion in criteria_set.criteria:
        finding = downgrades.get(criterion.id)
        if finding is None:
            criteria.append(criterion)
            continue
        replacement = UnsupportedPredicate(reason=_downgrade_reason(finding))
        criteria.append(criterion.model_copy(update={"predicate": replacement}))
    # Always a fresh list, even when nothing was downgraded: a caller that holds both the reviewed
    # and the applied set must never find that writing to one of them changed the other.
    return criteria_set.model_copy(update={"criteria": criteria})


def _downgrade_reason(finding: Finding) -> str:
    """The sentence the human reviewer will read, carrying the critic's own words verbatim."""
    phrase = _DOWNGRADE_PHRASES.get(
        finding.severity, f"did not survive back-translation ({finding.severity})"
    )
    return f"back-translation: the compiled predicate {phrase}. {finding.reason}"


# ------------------------------------------------------------------------------------------------
# Coverage. Deterministic: what the compiler produced, against what it was given.
# ------------------------------------------------------------------------------------------------


def coverage_report(criteria_set: CriteriaSet) -> Coverage:
    """Which segmented spans of the protocol some criterion claims, and which nobody does."""
    spans = segment(criteria_set.source_text)
    claimed = _claimed_span_indices(spans, criteria_set)
    return Coverage(
        total_spans=len(spans),
        claimed_span_indices=tuple(sorted(claimed)),
        unclaimed_spans=tuple(span for span in spans if span.index not in claimed),
        quote_problems=tuple(quote_fidelity_problems(criteria_set)),
    )


def _claimed_span_indices(spans: list[CriterionSpan], criteria_set: CriteriaSet) -> set[int]:
    """A span is claimed when some criterion's quote contains it, or its parent's quote does.

    Containment rather than equality, because one criterion legitimately quotes a parent bullet
    together with the sub-bullets underneath it. The inherited claim covers the other half of that
    case: a criterion quoting only the parent has compiled the sub-conditions hanging off it, since
    those qualify the parent rather than standing on their own. Both readings are deliberately
    generous — this check exists to find spans nobody went near, and a false alarm on a
    legitimately merged criterion trains people to ignore the report.
    """
    quotes = [_normalise(criterion.source_quote) for criterion in criteria_set.criteria]
    claimed = {
        span.index
        for span in spans
        if span.text.strip() and any(_normalise(span.text) in quote for quote in quotes)
    }
    # Spans are in document order and a parent always precedes its children, so one forward pass
    # propagates a claim down an arbitrarily deep nesting.
    for span in spans:
        if span.parent_index is not None and span.parent_index in claimed:
            claimed.add(span.index)
    return claimed


def _normalise(text: str) -> str:
    """Forgive whitespace and case, forgive nothing else. Mirrors `ir.quote_fidelity_problems`."""
    return " ".join(text.split()).casefold()


def _cell(text: str) -> str:
    """Keep a Markdown table cell from being broken by the text it holds."""
    return text.replace("|", "\\|").replace("\n", " ")


def _coverage_section(
    headline: str,
    unclaimed: tuple[CriterionSpan, ...],
    problems: tuple[QuoteProblem, ...],
) -> list[str]:
    """The half of either report a reviewer actually acts on: what nobody compiled."""
    out = ["## Coverage", "", headline, ""]
    if unclaimed:
        out += ["Spans no criterion claims:", ""]
        out += [f"- [{span.index}] {span.text}" for span in unclaimed]
        out += [""]
    if problems:
        out += ["Quotes that are not verbatim in the protocol text:", ""]
        out += [f"- {p.criterion_id}: {p.quote!r} - {p.reason}" for p in problems]
        out += [""]
    return out
