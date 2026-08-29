"""Turning clinical prose into coded evidence, one note at a time.

`record.py` refuses to match a narrative row by wording, so a note reaches a verdict only through
this module. That refusal is the reason the module exists: a discharge summary containing the
phrase "myocardial infarction" is not a diagnosis, because the sentence around it may be a denial,
a plan, a query, or a fact about the patient's father. Something has to read the sentence and take
responsibility for the reading before a code is attached, and this is that something.

The division of labour is the point. The model is asked for one thing it is good at — which of a
given list of concepts a note asserts, in what sense, quoted — and is trusted with none of the
consequences. Everything that decides what reaches a patient's record is deterministic code below:

* only `present` and `absent` survive; the other four assertion classes produce no evidence;
* a quoted sentence that is not in the note is discarded, and the finding with it, because a
  paraphrase has stopped being a citation and there is no way to tell which reading it encodes;
* a quote that *is* in the note is re-anchored to the note's own characters, so the row carries
  wording a coordinator can find by searching the document rather than the model's rendering of it;
* a denial becomes a documented negation rather than evidence, and is reported rather than dropped.

Negations are reported and not converted into `Evidence` on purpose. `Evidence` means "this is on
the chart", and `PatientIndex.find` has no way to express a row that means the opposite; a negation
filed as evidence would satisfy the very criterion it refutes. The caller gets them as their own
list, because "the note says he has never had one" is genuinely more informative than silence and
some callers will want it.

One call per note, following the compiler's one-call-per-span shape: a bounded job for the model,
a failure contained to one note, and a count that makes a missing note visible.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from importlib import resources
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from caliper.agents.base import AgentContext
from caliper.agents.resolver import normalise_concept_text
from caliper.ir import Concept
from caliper.llm import LLMError
from caliper.llm.trace import Attempt, TraceStep
from caliper.record import Evidence, EvidenceKind, PatientIndex

AGENT_NAME = "extractor"

SYSTEM_PROMPT = (
    resources.files("caliper.agents")
    .joinpath("prompts", "extractor.md")
    .read_text(encoding="utf-8")
)

Assertion = Literal[
    "present", "absent", "family_history", "hypothetical", "uncertain", "other_subject"
]

KEPT_ASSERTIONS: tuple[Assertion, ...] = ("present", "absent")
"""The two classes that say something about this patient's chart. The other four are counted and
discarded: a plan, a query, a relative's diagnosis and a bystander's diagnosis all resolve nothing,
and ranking them against each other would only invite a caller to use one of them anyway."""

REASON_NOT_QUOTED = "the quoted sentence does not appear in the note"
REASON_UNKNOWN_CONCEPT = "the concept is not among those the caller asked about"

_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


# --------------------------------------------------------------------------------------------
# What the model is asked for
# --------------------------------------------------------------------------------------------


class ExtractedFinding(BaseModel):
    """One concept the model believes the note says something about, and what it says."""

    model_config = ConfigDict(extra="forbid")

    concept: str = Field(
        description="One of the concepts offered in the request, written exactly as listed."
    )
    sentence: str = Field(
        description="The sentence from the note carrying the assertion, copied character for "
        "character."
    )
    assertion: Assertion = Field(
        description="Whose finding this is and in what sense: asserted, denied, a relative's, "
        "planned, suspected, or another person's."
    )
    date: str | None = Field(
        description="The date the sentence itself gives for the event, as YYYY-MM-DD, or null "
        "when it gives none that can be written in full."
    )


class NoteReading(BaseModel):
    """Everything the model found in one note. An empty list is a common and correct answer."""

    model_config = ConfigDict(extra="forbid")

    findings: list[ExtractedFinding] = Field(
        description="One entry per concept-and-sentence pair. Empty when the note asserts none "
        "of the offered concepts."
    )


# --------------------------------------------------------------------------------------------
# What the caller gets back
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class DocumentedNegation:
    """The note says this patient does not have the concept, and names the sentence saying so.

    Deliberately not an `Evidence` row. Evidence means the thing is on the chart, and there is no
    way to write a negative one that `PatientIndex.find` would not treat as a positive.
    """

    concept: Concept
    note_id: str
    fhir_path: str
    quote: str
    date: date | None = None


@dataclass(frozen=True)
class DiscardedFinding:
    """A finding the gate refused, with the reason, so the evaluation can show what was rejected."""

    note_id: str
    fhir_path: str
    concept: str
    quote: str
    assertion: str
    reason: str


@dataclass(frozen=True)
class NoteExtraction:
    """What one note produced, whether or not that was anything."""

    note_id: str
    fhir_path: str
    counts: Mapping[str, int] = field(default_factory=dict)
    kept: int = 0
    rejected: int = 0
    error: str | None = None
    """Set when the provider never returned a valid reading for this note. Distinct from a note
    the model read and found nothing in, which is the ordinary case."""

    @property
    def returned(self) -> int:
        return sum(self.counts.values())


@dataclass(frozen=True)
class ExtractionResult:
    """Everything one extraction run produced, including what it threw away and why."""

    evidence: tuple[Evidence, ...] = ()
    negations: tuple[DocumentedNegation, ...] = ()
    discarded: tuple[DiscardedFinding, ...] = ()
    notes: tuple[NoteExtraction, ...] = ()

    @property
    def failed_notes(self) -> tuple[str, ...]:
        """Notes whose reading never arrived. Each one is a note nobody has read."""
        return tuple(n.note_id for n in self.notes if n.error is not None)

    def counts_by_assertion(self) -> dict[str, int]:
        """How many findings came back in each class, across every note."""
        totals: dict[str, int] = {}
        for note in self.notes:
            for assertion, count in note.counts.items():
                totals[assertion] = totals.get(assertion, 0) + count
        return totals

    def to_dict(self) -> dict[str, Any]:
        return {
            "notes": len(self.notes),
            "evidence": len(self.evidence),
            "negations": len(self.negations),
            "discarded": len(self.discarded),
            "counts_by_assertion": self.counts_by_assertion(),
            "failed_notes": list(self.failed_notes),
            "rejections": [
                {"note_id": d.note_id, "assertion": d.assertion, "reason": d.reason}
                for d in self.discarded
            ],
        }


# --------------------------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Sink:
    """The three lists a note's findings are sorted into, passed around as one thing."""

    evidence: list[Evidence] = field(default_factory=list)
    negations: list[DocumentedNegation] = field(default_factory=list)
    discarded: list[DiscardedFinding] = field(default_factory=list)


def extract_findings(
    patient: PatientIndex,
    concepts: Sequence[Concept],
    ctx: AgentContext,
    *,
    kind: EvidenceKind = "condition",
) -> ExtractionResult:
    """Read every note on `patient` for the given concepts and return what survives the gate.

    `kind` is the evidence kind the surviving rows carry. Notes assert conditions overwhelmingly,
    so that is the default; a caller chasing procedures or drugs groups those concepts and calls
    again with the matching kind, rather than letting a model decide which sort of thing a
    sentence describes.

    Nothing here is emitted that a human cannot check: every row carries a sentence that appears
    in the note, and a pointer to the note it appears in.
    """
    notes = patient.notes()
    if not notes or not concepts:
        return ExtractionResult()

    by_key = {normalise_concept_text(c.text): c for c in concepts if c.text.strip()}
    offered = [c.text for c in concepts]

    sink = _Sink()
    summaries = [_read_note(note, by_key, offered, ctx, kind, sink) for note in notes]

    result = ExtractionResult(
        evidence=tuple(sink.evidence),
        negations=tuple(sink.negations),
        discarded=tuple(sink.discarded),
        notes=tuple(summaries),
    )
    _record(ctx, result)
    return result


def _read_note(
    note: Evidence,
    by_key: Mapping[str, Concept],
    offered: Sequence[str],
    ctx: AgentContext,
    kind: EvidenceKind,
    sink: _Sink,
) -> NoteExtraction:
    """One call, then the gate. Files what survives into `sink` and reports what this note did."""
    text = note.narrative_quote or ""
    try:
        completion = ctx.client.complete(
            system=SYSTEM_PROMPT,
            user=render_note(note, offered),
            model_cls=NoteReading,
            agent=AGENT_NAME,
        )
    except LLMError as error:
        # The runtime has already written the failure into the trajectory in full. One unreadable
        # note is not a reason to abandon the patient, but it must not look like an empty one.
        return NoteExtraction(note_id=note.resource_id, fhir_path=note.fhir_path, error=str(error))

    counts: dict[str, int] = {}
    kept = 0
    rejected = 0
    seen: set[tuple[str, str]] = set()

    for finding in completion.value.findings:
        counts[finding.assertion] = counts.get(finding.assertion, 0) + 1

        if finding.assertion not in KEPT_ASSERTIONS:
            rejected += 1
            sink.discarded.append(
                _discard(
                    note,
                    finding,
                    f"assertion {finding.assertion!r} is not a fact about this patient's chart",
                )
            )
            continue

        concept = by_key.get(normalise_concept_text(finding.concept))
        if concept is None:
            rejected += 1
            sink.discarded.append(_discard(note, finding, REASON_UNKNOWN_CONCEPT))
            continue

        quote = locate_quote(text, finding.sentence)
        if quote is None:
            rejected += 1
            sink.discarded.append(_discard(note, finding, REASON_NOT_QUOTED))
            continue

        signature = (concept.text, quote)
        if signature in seen:
            continue  # The same sentence said twice about one concept is still one finding.
        seen.add(signature)
        kept += 1

        if finding.assertion == "absent":
            sink.negations.append(
                DocumentedNegation(
                    concept=concept,
                    note_id=note.resource_id,
                    fhir_path=note.fhir_path,
                    quote=quote,
                    date=_sentence_date(finding.date) or note.date,
                )
            )
        else:
            sink.evidence.append(
                Evidence(
                    kind=kind,
                    resource_type=note.resource_type,
                    resource_id=note.resource_id,
                    display=concept.text,
                    fhir_path=note.fhir_path,
                    codes=concept.codes,
                    # The sentence's own date when it gives one, else the day it was written
                    # down. `fhir.py` dates a Condition from `recordedDate` for the same reason:
                    # an undated row silently fails every relative window, which turns a real
                    # finding into "we could not tell".
                    date=_sentence_date(finding.date) or note.date,
                    source="narrative",
                    narrative_quote=quote,
                )
            )

    return NoteExtraction(
        note_id=note.resource_id,
        fhir_path=note.fhir_path,
        counts=counts,
        kept=kept,
        rejected=rejected,
    )


def render_note(note: Evidence, offered: Sequence[str]) -> str:
    """The user turn: what the note is, what it says, and which concepts are on the table."""
    stamp = note.date.isoformat() if note.date else "undated"
    return "\n".join(
        [
            f"Note type: {note.display}",
            f"Note date: {stamp}",
            "",
            "Concepts:",
            *(f"- {text}" for text in offered),
            "",
            "Note text:",
            note.narrative_quote or "",
        ]
    )


def locate_quote(text: str, quote: str) -> str | None:
    """The note's own characters for `quote`, or None if the note does not contain it.

    An exact substring is returned as given. Failing that the two are compared with runs of
    whitespace collapsed, because a note wraps its lines and a model quoting one sentence will
    reasonably return it unwrapped — that is a rendering difference, not a rewrite. Case and
    wording are not forgiven: a citation whose letters differ from the source is no longer a
    citation, and the caller cannot tell which version was being asserted.

    The span returned is always the note's, never the model's, so a coordinator searching the
    document for the quoted sentence finds it.
    """
    needle = quote.strip()
    if not needle:
        return None
    if needle in text:
        return needle

    flat, offsets = _collapse(text)
    target, _ = _collapse(needle)
    if not target:
        return None
    start = flat.find(target)
    if start < 0:
        return None
    return text[offsets[start] : offsets[start + len(target) - 1] + 1]


def _collapse(text: str) -> tuple[str, list[int]]:
    """`text` with whitespace runs squeezed to one space, plus each kept character's origin."""
    out: list[str] = []
    offsets: list[int] = []
    pending = False
    for position, character in enumerate(text):
        if character.isspace():
            pending = bool(out)
            continue
        if pending:
            out.append(" ")
            offsets.append(position)
            pending = False
        out.append(character)
        offsets.append(position)
    return "".join(out), offsets


def _discard(note: Evidence, finding: ExtractedFinding, reason: str) -> DiscardedFinding:
    return DiscardedFinding(
        note_id=note.resource_id,
        fhir_path=note.fhir_path,
        concept=finding.concept,
        quote=finding.sentence,
        assertion=finding.assertion,
        reason=reason,
    )


def _sentence_date(value: str | None) -> date | None:
    """A full ISO date, or None. A partial date is not narrowed to a day it never named."""
    if value is None:
        return None
    candidate = value.strip()
    if not _ISO_DATE.fullmatch(candidate):
        return None
    try:
        return date.fromisoformat(candidate)
    except ValueError:
        return None


def _record(ctx: AgentContext, result: ExtractionResult) -> None:
    """Append the run's summary to the trajectory, beside the calls it explains.

    It is a step with one attempt on a `gate` tier: no request was sent, but a reader following
    the trajectory wants to see what the deterministic half did with the answers it just read.
    """
    payload = result.to_dict()
    ctx.trajectory.append(
        TraceStep(
            agent=AGENT_NAME,
            provider=ctx.client.profile.provider,
            model=ctx.client.profile.model,
            system_prompt="Extraction gate summary. No request was sent for this step.",
            user_prompt="\n".join(_lines(result)),
            attempts=[
                Attempt(
                    tier="gate",
                    messages=[],
                    raw_response=json.dumps(payload, indent=2, ensure_ascii=False),
                )
            ],
            parsed=payload,
        )
    )


def _lines(result: ExtractionResult) -> list[str]:
    lines = [
        f"Read {len(result.notes)} note(s): {len(result.evidence)} coded row(s), "
        f"{len(result.negations)} documented negation(s), {len(result.discarded)} rejected."
    ]
    for assertion, count in sorted(result.counts_by_assertion().items()):
        lines.append(f"  {assertion}: {count}")
    if result.failed_notes:
        lines.append(f"No reading returned for: {', '.join(result.failed_notes)}")
    return lines
