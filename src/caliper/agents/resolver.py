"""Attaching terminology codes to the concepts a protocol names, and remembering the answers.

A compiled criterion arrives holding a `Concept` with the wording the protocol used and usually no
codes. Nothing downstream can match evidence without them: `PatientIndex.find` matches on
`(system, code)` pairs, and falls back to wording only for structured rows whose concept is
uncoded.

Two ideas carry this module.

The first is the confidence gate. Anything the model does not mark `high` is discarded, and a
concept whose candidates are all discarded comes back with no codes at all. That is deliberate and
asymmetric: an uncoded concept still matches structured rows by wording and degrades a verdict to
"we could not tell", whereas a *wrong* code matches the wrong evidence exactly and produces a
confident, wrong verdict about a patient — with nothing in the output to suggest anything went
astray. A missing code is a visible gap; a wrong code is an invisible one. So the gate is set
where a false negative is cheap and a false positive is not.

The second is `ConceptMemory`. Terminology work is the same for every trial that mentions
creatinine, so it is done once and written down, with the provenance needed to audit it later.
The store exists to be measured as much as to save money: `stats()` is a first-class output, and
a concept that resolved one way must not resolve another way in the next trial, so an attempt to
overwrite an entry with different codes keeps the first answer and is counted as a consistency
violation.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from caliper.agents.base import AgentContext
from caliper.ir import Code, Concept
from caliper.llm import LLMError
from caliper.llm.trace import Attempt, TraceStep, utc_now

AGENT_NAME = "resolver"
DEFAULT_MEMORY_PATH = Path(".caliper") / "concepts.json"
STORE_VERSION = 1

CodeSystem = Literal["LOINC", "SNOMED", "RxNorm", "ICD10", "UCUM"]
Confidence = Literal["high", "medium", "low"]

SYSTEM_PROMPT = (
    resources.files("caliper.agents").joinpath("prompts", "resolver.md").read_text(encoding="utf-8")
)

# What a well-formed identifier looks like in each system. This is a check on model output, so it
# lives here rather than in the prompt: a model asked to obey a regex will sometimes fabricate a
# string that satisfies it, and the only defence against that is to apply the rule ourselves.
# ICD-10 is matched against the ICD-10-CM shape, which is the one US charts carry.
_CODE_SHAPES: Mapping[str, re.Pattern[str]] = {
    "LOINC": re.compile(r"\d{1,5}-\d"),
    "RxNorm": re.compile(r"\d+"),
    "SNOMED": re.compile(r"\d{6,18}"),
    "ICD10": re.compile(r"[A-TV-Z]\d[0-9A-Z](?:\.[0-9A-Z]{1,4})?"),
    "UCUM": re.compile(r"\S+"),
}

_WHITESPACE = re.compile(r"\s+")
_TRAILING_PUNCTUATION = " \t.,;:"


def normalise_concept_text(text: str) -> str:
    """The store's key: case-folded, whitespace-collapsed, trailing punctuation removed.

    Only *trailing* punctuation goes, because "estimated glomerular filtration rate (eGFR)" ends
    in a bracket that is part of the concept.
    """
    return _WHITESPACE.sub(" ", text).strip().rstrip(_TRAILING_PUNCTUATION).casefold()


# --------------------------------------------------------------------------------------------
# What the model is asked for
# --------------------------------------------------------------------------------------------


class CandidateCode(BaseModel):
    """One proposed code, with the model's own assessment of whether it is sure."""

    model_config = ConfigDict(extra="forbid")

    system: CodeSystem = Field(description="The terminology this code belongs to.")
    code: str = Field(description="The identifier itself, exactly as the terminology writes it.")
    display: str = Field(description="The concept's name in that terminology.")
    confidence: Confidence = Field(
        description=(
            "'high' only when the identifier is recalled with certainty and means this concept "
            "exactly. Anything else is discarded."
        )
    )


class ConceptCodes(BaseModel):
    """The codes that identify one concept, or none.

    Kept flat and non-recursive so it survives `to_strict_schema` on every provider. The rationale
    comes first because it is written first: the model states what kind of concept it is looking
    at before it commits to identifiers.
    """

    model_config = ConfigDict(extra="forbid")

    rationale: str = Field(
        description="One or two sentences: what kind of concept this is, and why these codes."
    )
    candidates: list[CandidateCode] = Field(
        description="Proposed codes. An empty list is a valid and often correct answer."
    )


# --------------------------------------------------------------------------------------------
# The store
# --------------------------------------------------------------------------------------------


class ResolvedConcept(BaseModel):
    """One settled answer, with enough provenance to argue about it a month later."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str = Field(min_length=1)
    """The normalised concept text this entry is keyed by."""

    codes: tuple[Code, ...] = ()
    model: str
    """The `provider:model` that produced the codes."""

    resolved_at: str
    first_seen_nct: str
    reuse_count: int = 0
    """How many times `record_hit` has been called for this entry, across all runs."""


@dataclass(frozen=True)
class MemoryStats:
    """What the store did, which is the number the cold-versus-warm evaluation compares.

    `hits` and `misses` count lookups made through this object since it was constructed, so a run
    against a cold store reports a hit rate of zero and the same run against a warm one reports
    something near one. `consistency_violations` is cumulative over the store's whole life,
    because an answer that changed once is worth knowing about forever.
    """

    entries: int
    hits: int
    misses: int
    consistency_violations: int

    @property
    def lookups(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        """Hits over lookups. A store nobody asked has a rate of zero, not an error."""
        return self.hits / self.lookups if self.lookups else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "entries": self.entries,
            "hits": self.hits,
            "misses": self.misses,
            "lookups": self.lookups,
            "hit_rate": round(self.hit_rate, 4),
            "consistency_violations": self.consistency_violations,
        }


class ConceptMemory:
    """A JSON-backed map from normalised concept text to the codes it resolved to.

    Loading is total: a missing, unreadable or corrupt file yields an empty store rather than an
    exception, because a broken cache is not a reason to abandon a screening run. Saving is
    atomic — a temporary file in the same directory, then `os.replace` — so an interrupted run
    cannot leave a truncated store behind for the next one to read.
    """

    def __init__(self, path: str | Path = DEFAULT_MEMORY_PATH):
        self.path = Path(path)
        self._entries: dict[str, ResolvedConcept] = {}
        self._hits = 0
        self._misses = 0
        self._consistency_violations = 0
        self.load()

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, text: str) -> bool:
        return normalise_concept_text(text) in self._entries

    def get(self, text: str) -> ResolvedConcept | None:
        """Look up a concept, counting the lookup as a hit or a miss.

        An entry with no codes is still a hit: "we asked, and the honest answer was nothing" is a
        result worth keeping, and re-asking would cost a call to learn the same thing.
        """
        entry = self._entries.get(normalise_concept_text(text))
        if entry is None:
            self._misses += 1
        else:
            self._hits += 1
        return entry

    def put(
        self,
        text: str,
        codes: Iterable[Code],
        *,
        model: str,
        nct_id: str,
    ) -> None:
        """Record an answer. The first answer for a concept is the one that stands.

        Two trials naming the same thing must screen against the same codes, so a later `put` that
        disagrees with the stored entry is refused and counted rather than applied. The stored
        answer may be wrong, but it will at least be wrong identically everywhere, which is a
        property you can measure and fix.
        """
        key = normalise_concept_text(text)
        existing = self._entries.get(key)
        settled = tuple(codes)
        if existing is not None:
            if _identity(existing.codes) != _identity(settled):
                self._consistency_violations += 1
            return
        self._entries[key] = ResolvedConcept(
            text=key,
            codes=settled,
            model=model,
            resolved_at=utc_now(),
            first_seen_nct=nct_id,
        )

    def record_hit(self, text: str) -> None:
        """Note that a stored entry was reused. Unknown text is ignored."""
        key = normalise_concept_text(text)
        entry = self._entries.get(key)
        if entry is not None:
            self._entries[key] = entry.model_copy(update={"reuse_count": entry.reuse_count + 1})

    def stats(self) -> MemoryStats:
        return MemoryStats(
            entries=len(self._entries),
            hits=self._hits,
            misses=self._misses,
            consistency_violations=self._consistency_violations,
        )

    def load(self) -> None:
        """Replace the entries with what is on disk, tolerating anything that is not a store.

        Nothing is logged. A cache that cannot be read is indistinguishable from a cache that does
        not exist yet, and neither is worth a line of output on a run that is about to rebuild it.
        """
        self._entries = {}
        self._consistency_violations = 0
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(payload, dict):
            return

        entries = payload.get("entries")
        if isinstance(entries, dict):
            for key, raw in entries.items():
                try:
                    entry = ResolvedConcept.model_validate(raw)
                except ValidationError:
                    continue  # One unreadable entry costs one call, not the whole store.
                self._entries[normalise_concept_text(str(key))] = entry

        violations = payload.get("consistency_violations")
        if isinstance(violations, int) and not isinstance(violations, bool) and violations >= 0:
            self._consistency_violations = violations

    def save(self) -> Path:
        """Write the store atomically, and leave nothing behind if the write fails."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle_fd, temporary_name = tempfile.mkstemp(
            dir=self.path.parent, prefix=f"{self.path.name}.", suffix=".tmp"
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(handle_fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(self._payload(), handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        return self.path

    def _payload(self) -> dict[str, Any]:
        return {
            "version": STORE_VERSION,
            "consistency_violations": self._consistency_violations,
            "entries": {
                key: entry.model_dump(mode="json") for key, entry in sorted(self._entries.items())
            },
        }


def _identity(codes: Iterable[Code]) -> frozenset[tuple[str, str]]:
    """What makes two answers the same answer: the systems and codes, not the display text."""
    return frozenset((code.system, code.code) for code in codes)


# --------------------------------------------------------------------------------------------
# Resolution
# --------------------------------------------------------------------------------------------


@dataclass
class _Summary:
    """What one call to `resolve_concepts` did, for the trajectory."""

    nct_id: str
    memory_hits: list[str] = field(default_factory=list)
    model_calls: list[str] = field(default_factory=list)
    uncoded: list[str] = field(default_factory=list)
    model_failures: list[str] = field(default_factory=list)
    low_confidence_dropped: int = 0
    malformed_codes_dropped: int = 0

    def to_dict(self, stats: MemoryStats) -> dict[str, Any]:
        return {
            "nct_id": self.nct_id,
            "concepts": len(self.memory_hits) + len(self.model_calls),
            "memory_hits": self.memory_hits,
            "model_calls": self.model_calls,
            "resolved_without_codes": self.uncoded,
            "model_failures": self.model_failures,
            "low_confidence_dropped": self.low_confidence_dropped,
            "malformed_codes_dropped": self.malformed_codes_dropped,
            "memory": stats.to_dict(),
        }


def resolve_concepts(
    concepts: Sequence[Concept], ctx: AgentContext, *, nct_id: str
) -> dict[str, tuple[Code, ...]]:
    """Resolve every distinct concept to codes, consulting the store before the model.

    Returns a mapping keyed by each input concept's `text` exactly as it was given, so a caller
    can write `concept.model_copy(update={"codes": resolved[concept.text]})` without repeating the
    normalisation. Concepts that differ only in case, spacing or a trailing full stop share one
    lookup and one answer.

    **A concept may legitimately come back with no codes, and that is preferred to a doubtful
    one.** Only candidates the model marked `high` are kept, and only if the identifier has its
    system's shape. An uncoded concept still matches structured evidence by wording and, failing
    that, leaves the criterion unresolved for a human. A wrong code matches the wrong evidence
    exactly and returns a confident, wrong verdict. The two failures are not worth the same, so
    the gate is not set in the middle.

    Every hit, call, and dropped candidate is summarised into `ctx.trajectory`.
    """
    memory = _memory_of(ctx)
    summary = _Summary(nct_id=nct_id)

    first_spelling: dict[str, str] = {}
    for concept in concepts:
        key = normalise_concept_text(concept.text)
        if key:
            first_spelling.setdefault(key, concept.text)

    settled: dict[str, tuple[Code, ...]] = {}
    for key, spelling in first_spelling.items():
        entry = memory.get(key)
        if entry is not None:
            memory.record_hit(key)
            summary.memory_hits.append(key)
            settled[key] = entry.codes
            continue

        summary.model_calls.append(key)
        answer = _ask(ctx, spelling)
        summary.low_confidence_dropped += answer.low_confidence
        summary.malformed_codes_dropped += answer.malformed
        if answer.failed:
            # A provider that would not answer is not evidence that the concept has no codes, so
            # nothing is cached and the next run gets to try again.
            summary.model_failures.append(key)
            settled[key] = ()
            continue

        memory.put(key, answer.codes, model=ctx.client.profile.name, nct_id=nct_id)
        memory.save()
        settled[key] = answer.codes

    summary.uncoded = [key for key, codes in settled.items() if not codes]

    _record(ctx, summary, memory.stats())
    return {
        concept.text: settled.get(normalise_concept_text(concept.text), ()) for concept in concepts
    }


@dataclass(frozen=True)
class _Answer:
    codes: tuple[Code, ...] = ()
    low_confidence: int = 0
    malformed: int = 0
    failed: bool = False


def _ask(ctx: AgentContext, text: str) -> _Answer:
    """One model call for one concept, with everything the gate rejects counted on the way out."""
    try:
        completion = ctx.client.complete(
            system=SYSTEM_PROMPT,
            user=_user_prompt(text),
            model_cls=ConceptCodes,
            agent=AGENT_NAME,
        )
    except LLMError:
        # The runtime has already written the failure into the trajectory in full detail; one
        # unresolvable concept is not a reason to abandon the trial.
        return _Answer(failed=True)
    return _accept(completion.value)


def _user_prompt(text: str) -> str:
    return f"Concept: {text}"


def _accept(answer: ConceptCodes) -> _Answer:
    """Apply the confidence gate and the shape check, keeping the order deterministic."""
    kept: dict[tuple[str, str], Code] = {}
    low_confidence = 0
    malformed = 0
    for candidate in answer.candidates:
        if candidate.confidence != "high":
            low_confidence += 1
            continue
        code = _well_formed(candidate.system, candidate.code)
        if code is None:
            malformed += 1
            continue
        kept.setdefault(
            (candidate.system, code),
            Code(system=candidate.system, code=code, display=candidate.display.strip() or None),
        )
    ordered = tuple(sorted(kept.values(), key=lambda c: (c.system, c.code)))
    return _Answer(codes=ordered, low_confidence=low_confidence, malformed=malformed)


def _well_formed(system: str, raw: str) -> str | None:
    """The code as it should be stored, or `None` if it is not shaped like one of its system."""
    code = raw.strip()
    if system == "ICD10":
        code = code.upper()  # ICD-10 letters are case-insensitive; charts write them upper.
    return code if _CODE_SHAPES[system].fullmatch(code) else None


def _memory_of(ctx: AgentContext) -> ConceptMemory:
    """The store on the context, or a fresh one at the default path, cached back onto it."""
    if ctx.memory is None:
        ctx.memory = ConceptMemory()
        return ctx.memory
    if isinstance(ctx.memory, ConceptMemory):
        return ctx.memory
    raise TypeError(f"ctx.memory must be a ConceptMemory, got {type(ctx.memory).__name__}")


def _record(ctx: AgentContext, summary: _Summary, stats: MemoryStats) -> None:
    """Append the run's summary to the trajectory, so a judge can see what a call actually cost.

    It is a step with one attempt on a `memory` tier: no request was sent, but the trajectory's
    reader wants this in the same sequence as the calls it explains.
    """
    payload = summary.to_dict(stats)
    rendered = json.dumps(payload, indent=2, ensure_ascii=False)
    ctx.trajectory.append(
        TraceStep(
            agent=AGENT_NAME,
            provider=ctx.client.profile.provider,
            model=ctx.client.profile.model,
            system_prompt="Concept resolution summary. No request was sent for this step.",
            user_prompt="\n".join(_lines(summary)),
            attempts=[Attempt(tier="memory", messages=[], raw_response=rendered)],
            parsed=payload,
        )
    )


def _lines(summary: _Summary) -> list[str]:
    total = len(summary.memory_hits) + len(summary.model_calls)
    lines = [f"Resolved {total} distinct concept(s) for {summary.nct_id}."]
    lines += [f"  memory: {text}" for text in summary.memory_hits]
    lines += [f"  called: {text}" for text in summary.model_calls]
    if summary.uncoded:
        lines.append(f"Left uncoded: {', '.join(summary.uncoded)}")
    if summary.model_failures:
        lines.append(f"Model failed on: {', '.join(summary.model_failures)}")
    return lines
