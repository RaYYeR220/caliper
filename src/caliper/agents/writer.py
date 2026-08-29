"""The one sentence in a screening packet that a model is allowed to author.

Everything else the coordinator reads is generated from the structured screening result: the
verdict, the evidence rows, the FHIR pointers, the worklist. The rationale is not, because a
person reading forty criteria wants a sentence rather than a row of fields. That makes it the only
place in the document where prose can drift away from the record it claims to describe.

So nothing the model writes is trusted on sight. Every sentence goes through `check_rationale`,
which binds each number and date in it to the values *that* criterion resolved from. A sentence
that fails is re-asked once with the offending tokens named. A sentence that fails twice is thrown
away and the evaluator's own rationale is printed instead — machine prose, visibly machine prose,
recorded as a fallback in the packet and in the trajectory.

That degradation is the point. A packet that reads slightly worse is a cost worth paying; a packet
carrying a fluent sentence nobody can check is not.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from importlib import resources
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from caliper.agents.base import AgentContext
from caliper.evaluate import CriterionResult
from caliper.ir import CriteriaSet, Criterion
from caliper.llm import LLMError
from caliper.llm.trace import Attempt, TraceStep
from caliper.logic import Verdict
from caliper.prose import ProseViolation, check_rationale
from caliper.screen import ScreeningResult

AGENT_NAME = "writer"

PROSE_CHECK_TIER = "prose_check"
"""The tier a prose-check step is recorded under. No request is sent for one."""

MAX_REDRAFTS = 1
"""Rejected sentences are re-asked once. A second failure is a fallback, not a third try."""

SYSTEM_PROMPT = (
    resources.files("caliper.agents").joinpath("prompts", "writer.md").read_text(encoding="utf-8")
)

RationaleSource = Literal["model", "fallback"]

_VERDICT_WORDS = {
    Verdict.MET: "met",
    Verdict.NOT_MET: "not met",
    Verdict.UNKNOWN: "unresolved",
}

_REJECTION_HEADER = "The sentence you wrote was rejected."

_REDRAFT_INSTRUCTION = (
    "Write the sentence again. Use only the values and dates in the material above, or write a "
    "sentence that carries no number at all."
)


class RationaleDraft(BaseModel):
    """What the writer returns for one criterion: a sentence, and nothing to hide behind."""

    model_config = ConfigDict(extra="forbid")

    sentence: str = Field(
        description=(
            "One sentence in plain clinical English, using only the values and dates given. "
            "One terminal full stop, no line breaks, no markdown, no citations."
        )
    )


@dataclass(frozen=True)
class Rationale:
    """The sentence that will be printed for one criterion, and where it came from."""

    criterion_id: str
    sentence: str
    source: RationaleSource
    violations: tuple[ProseViolation, ...] = ()
    """Everything the linter objected to, across every draft — kept even when a redraft passed."""

    rejected: tuple[str, ...] = ()
    """The drafts that were refused, verbatim, so a reviewer can see what was nearly printed."""

    fallback_reason: str | None = None


@dataclass(frozen=True)
class RationaleSet:
    """Every rationale for one screening, in the order the criteria were evaluated."""

    nct_id: str
    patient_id: str
    rationales: tuple[Rationale, ...] = ()

    def __iter__(self) -> Iterator[Rationale]:
        return iter(self.rationales)

    def __len__(self) -> int:
        return len(self.rationales)

    def __getitem__(self, criterion_id: str) -> Rationale:
        rationale = self.get(criterion_id)
        if rationale is None:
            raise KeyError(criterion_id)
        return rationale

    def get(self, criterion_id: str) -> Rationale | None:
        return next((r for r in self.rationales if r.criterion_id == criterion_id), None)

    @property
    def fallback_count(self) -> int:
        return sum(1 for r in self.rationales if r.source == "fallback")

    @property
    def fallback_rate(self) -> float:
        """The share of criteria whose sentence the model did not get to write.

        Worth reporting per run rather than averaged away: a rate that climbs on one trial usually
        means the criteria carry numbers the evidence does not, not that the model got worse.
        """
        return self.fallback_count / len(self.rationales) if self.rationales else 0.0


def write_rationales(
    result: ScreeningResult, criteria_set: CriteriaSet, ctx: AgentContext
) -> RationaleSet:
    """Write one checked sentence per criterion, falling back where the check fails.

    One model call per criterion, because a criterion is the unit the linter can check: the values
    a sentence is entitled to use are the ones *that* criterion resolved from, and asking for forty
    sentences at once would put them all in one allowed set.
    """
    by_id = {criterion.id: criterion for criterion in criteria_set.criteria}
    written: list[Rationale] = []

    for outcome in result.criteria:
        criterion = by_id.get(outcome.criterion_id)
        if criterion is None:
            # Without the compiled criterion there is nothing to check a sentence against, and an
            # unchecked sentence is exactly what this module exists to keep out of the packet.
            rationale = _fallback(outcome, reason="no compiled criterion carries this identifier")
        else:
            rationale = _write_one(criterion, outcome, ctx)
        _record(ctx, outcome, rationale)
        written.append(rationale)

    return RationaleSet(
        nct_id=result.nct_id, patient_id=result.patient_id, rationales=tuple(written)
    )


def deterministic_rationales(result: ScreeningResult) -> RationaleSet:
    """Every sentence taken from the evaluator, for a run with no model in it.

    The packet is a deterministic document; this is what it renders when nobody has been asked to
    improve the prose. It is also the floor the writer degrades to, criterion by criterion.
    """
    return RationaleSet(
        nct_id=result.nct_id,
        patient_id=result.patient_id,
        rationales=tuple(
            _fallback(outcome, reason="no model was consulted") for outcome in result.criteria
        ),
    )


def rationale_request(criterion: Criterion, result: CriterionResult) -> str:
    """Everything the writer is allowed to know about one criterion.

    The resolution hint's FHIR query is deliberately withheld: it carries a cutoff date that the
    sentence has no right to state, and the packet prints the query itself anyway.
    """
    lines = [
        f"Criterion {criterion.id}, an {criterion.kind} criterion.",
        "",
        "The protocol says, word for word:",
        criterion.source_quote,
        "",
        f"The screening engine found this criterion {_VERDICT_WORDS[result.verdict]}, because:",
        result.rationale,
        "",
        "Evidence the verdict rests on:",
    ]
    lines += _evidence_lines(result) or ["  nothing on file"]

    hint = result.resolution_hint
    if hint is not None:
        lines += [
            "",
            f"Nothing in the record settles this criterion. What is missing: {hint.missing}.",
            f"A coordinator would go looking in {hint.where_to_look}.",
        ]

    lines += ["", "Write the sentence a coordinator will read beside this criterion."]
    return "\n".join(lines)


def redraft_request(
    criterion: Criterion,
    result: CriterionResult,
    sentence: str,
    violations: Sequence[ProseViolation],
) -> str:
    """The follow-up, naming every token the record does not support."""
    tokens = ", ".join(dict.fromkeys(violation.token for violation in violations))
    return "\n".join(
        [
            rationale_request(criterion, result),
            "",
            _REJECTION_HEADER,
            "",
            "What you wrote:",
            sentence,
            "",
            f"These do not appear anywhere in the record for {criterion.id}: {tokens}",
            *[f"  - {violation.message}" for violation in violations],
            "",
            _REDRAFT_INSTRUCTION,
        ]
    )


def _write_one(criterion: Criterion, result: CriterionResult, ctx: AgentContext) -> Rationale:
    """Ask, check, re-ask once, then give up and print the evaluator's own words."""
    rejected: list[str] = []
    violations: list[ProseViolation] = []
    request = rationale_request(criterion, result)

    for _ in range(MAX_REDRAFTS + 1):
        try:
            completion = ctx.client.complete(
                system=SYSTEM_PROMPT,
                user=request,
                model_cls=RationaleDraft,
                agent=AGENT_NAME,
            )
        except LLMError as error:
            # The runtime has already written the failure into the trajectory in full. A provider
            # that would not answer will not answer a follow-up either, so stop asking.
            return _fallback(result, tuple(violations), str(error), tuple(rejected))

        sentence = " ".join(completion.value.sentence.split())
        found = check_rationale(sentence, criterion, result)
        if not found:
            return Rationale(
                criterion_id=result.criterion_id,
                sentence=sentence,
                source="model",
                violations=tuple(violations),
                rejected=tuple(rejected),
            )

        rejected.append(sentence)
        violations.extend(found)
        request = redraft_request(criterion, result, sentence, found)

    return _fallback(
        result,
        tuple(violations),
        "the redraft still carried values the record does not support",
        tuple(rejected),
    )


def _fallback(
    result: CriterionResult,
    violations: tuple[ProseViolation, ...] = (),
    reason: str = "",
    rejected: tuple[str, ...] = (),
) -> Rationale:
    """Print what the evaluator said.

    The evaluator's rationale passes the linter by construction — every number in it was read off
    the record — and it reads like a machine wrote it, which is the honest signal to send when the
    sentence a person would rather read could not be verified.
    """
    return Rationale(
        criterion_id=result.criterion_id,
        sentence=result.rationale,
        source="fallback",
        violations=violations,
        rejected=rejected,
        fallback_reason=reason or None,
    )


def _evidence_lines(result: CriterionResult) -> list[str]:
    """The evidence rows, without the resource pointers: the sentence must not cite them."""
    lines = []
    for evidence in result.evidence:
        parts = [evidence.display]
        if evidence.value is not None:
            unit = f" {evidence.unit}" if evidence.unit else ""
            parts.append(f"{evidence.value:g}{unit}")
        parts.append(
            f"recorded {evidence.date.isoformat()}" if evidence.date else "no date recorded"
        )
        lines.append("  - " + ", ".join(parts))
    return lines


def _record(ctx: AgentContext, result: CriterionResult, rationale: Rationale) -> None:
    """Append one step per criterion saying what was written and what was refused.

    The client already records the conversation; what it cannot record is the decision taken
    afterwards, which is the part a reviewer is actually auditing. It is recorded as a step with a
    single `prose_check` attempt — no request was sent — so that it reads in sequence with the
    calls it explains.
    """
    payload = {
        "criterion_id": rationale.criterion_id,
        "verdict": result.verdict.value,
        "source": rationale.source,
        "sentence": rationale.sentence,
        "rejected": list(rationale.rejected),
        "violations": [
            {"kind": v.kind, "token": v.token, "message": v.message} for v in rationale.violations
        ],
        "fallback_reason": rationale.fallback_reason,
    }

    ctx.trajectory.append(
        TraceStep(
            agent=AGENT_NAME,
            provider=ctx.client.profile.provider,
            model=ctx.client.profile.model,
            system_prompt="Prose check on one rationale sentence. No request was sent.",
            user_prompt=_summary_line(rationale),
            attempts=[
                Attempt(
                    tier=PROSE_CHECK_TIER,
                    messages=[],
                    raw_response=json.dumps(payload, indent=2, ensure_ascii=False),
                )
            ],
            parsed=payload,
        )
    )


def _summary_line(rationale: Rationale) -> str:
    if rationale.source == "model":
        if not rationale.violations:
            return f"{rationale.criterion_id}: the model's sentence was accepted as written."
        return (
            f"{rationale.criterion_id}: the model's sentence was accepted after "
            f"{len(rationale.rejected)} rejected draft(s)."
        )
    return (
        f"{rationale.criterion_id}: fell back to the evaluator's rationale "
        f"({rationale.fallback_reason})."
    )
