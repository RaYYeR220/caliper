"""The written record of what the model was asked, what it said, and what we did about it.

A trajectory is the artefact a reviewer reads instead of the code. Every call the runtime makes
appends one `TraceStep`, and every round trip inside that call — including the ones that failed
validation and were retried — appends an `Attempt`. Nothing is summarised away: the raw response
text is kept verbatim, and so is the validation error that rejected it.

Steps are plain data. `write_jsonl` gives a machine-readable log, `to_markdown` gives the same
information in the order a person would want to read it.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from caliper.llm.cost import CostLedger, CostRecord, CostTotals, Usage

_BACKTICKS = re.compile(r"`+")


def utc_now() -> str:
    """An ISO-8601 timestamp in UTC, to the second."""
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass
class Attempt:
    """One request/response round trip."""

    tier: str
    messages: list[dict[str, str]]
    raw_response: str | None = None
    usage: Usage = field(default_factory=Usage)
    usd: float | None = None
    validation_error: str | None = None
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.validation_error is None and self.error is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tier": self.tier,
            "messages": self.messages,
            "raw_response": self.raw_response,
            "usage": self.usage.to_dict(),
            "usd": self.usd,
            "validation_error": self.validation_error,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Attempt:
        return cls(
            tier=payload["tier"],
            messages=list(payload.get("messages", [])),
            raw_response=payload.get("raw_response"),
            usage=Usage.from_dict(payload.get("usage", {})),
            usd=payload.get("usd"),
            validation_error=payload.get("validation_error"),
            error=payload.get("error"),
        )


@dataclass
class TraceStep:
    """One `LLMClient.complete` call, from the instructions given to the value returned."""

    agent: str
    provider: str
    model: str
    system_prompt: str
    user_prompt: str
    attempts: list[Attempt] = field(default_factory=list)
    skipped_tiers: list[tuple[str, str]] = field(default_factory=list)
    """Rungs never attempted, with the reason. A reader should not have to infer an absence."""
    parsed: Any | None = None
    timestamp: str = field(default_factory=utc_now)

    @property
    def tier(self) -> str | None:
        """The rung that produced the answer, or the last one tried if none did."""
        if not self.attempts:
            return None
        for attempt in self.attempts:
            if attempt.succeeded:
                return attempt.tier
        return self.attempts[-1].tier

    @property
    def retries(self) -> int:
        """Round trips beyond the first, whether they were re-asks or drops to a lower rung."""
        return max(len(self.attempts) - 1, 0)

    @property
    def raw_response(self) -> str | None:
        return self.attempts[-1].raw_response if self.attempts else None

    @property
    def validation_errors(self) -> list[str]:
        return [a.validation_error for a in self.attempts if a.validation_error is not None]

    @property
    def succeeded(self) -> bool:
        return any(a.succeeded for a in self.attempts)

    @property
    def usage(self) -> Usage:
        total = Usage()
        for attempt in self.attempts:
            total = total + attempt.usage
        return total

    @property
    def usd(self) -> float | None:
        priced = [a.usd for a in self.attempts if a.usd is not None]
        return sum(priced) if priced else None

    def cost_record(self) -> CostRecord:
        return CostRecord(
            agent=self.agent,
            provider=self.provider,
            model=self.model,
            usage=self.usage,
            usd=self.usd,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "agent": self.agent,
            "provider": self.provider,
            "model": self.model,
            "tier": self.tier,
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "raw_response": self.raw_response,
            "parsed": self.parsed,
            "validation_errors": self.validation_errors,
            "retries": self.retries,
            "usage": self.usage.to_dict(),
            "usd": self.usd,
            "attempts": [a.to_dict() for a in self.attempts],
            "skipped_tiers": [list(pair) for pair in self.skipped_tiers],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> TraceStep:
        return cls(
            agent=payload["agent"],
            provider=payload["provider"],
            model=payload["model"],
            system_prompt=payload["system_prompt"],
            user_prompt=payload["user_prompt"],
            attempts=[Attempt.from_dict(a) for a in payload.get("attempts", [])],
            skipped_tiers=[tuple(pair) for pair in payload.get("skipped_tiers", [])],
            parsed=payload.get("parsed"),
            timestamp=payload["timestamp"],
        )


class Trajectory:
    """An ordered log of model calls, writable as JSONL and readable as Markdown."""

    def __init__(self, steps: Iterable[TraceStep] = ()):
        self.steps: list[TraceStep] = list(steps)

    def append(self, step: TraceStep) -> TraceStep:
        self.steps.append(step)
        return step

    def total_usage(self) -> Usage:
        total = Usage()
        for step in self.steps:
            total = total + step.usage
        return total

    def total_usd(self) -> float | None:
        priced = [step.usd for step in self.steps if step.usd is not None]
        return sum(priced) if priced else None

    def cost_ledger(self) -> CostLedger:
        return CostLedger(step.cost_record() for step in self.steps)

    def to_dicts(self) -> list[dict[str, Any]]:
        return [step.to_dict() for step in self.steps]

    def write_jsonl(self, path: str | Path) -> Path:
        """Write one JSON object per step. Existing content is replaced."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="\n") as handle:
            for step in self.steps:
                handle.write(json.dumps(step.to_dict(), ensure_ascii=False) + "\n")
        return target

    def write_markdown(self, path: str | Path) -> Path:
        """Write the rendered trajectory as UTF-8, whatever the platform's default encoding is."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.to_markdown(), encoding="utf-8", newline="\n")
        return target

    @classmethod
    def read_jsonl(cls, path: str | Path) -> Trajectory:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
        return cls(TraceStep.from_dict(json.loads(line)) for line in lines if line.strip())

    def to_markdown(self, *, repeat_instructions: bool = True) -> str:
        """Render the trajectory for a human reader, in the order events happened.

        With `repeat_instructions=False`, standing instructions shared by every step are
        printed once at the top rather than before each call. An agent's instructions do not
        change between calls, and a compiler making one call per criterion otherwise buries
        the run in copies of its own brief.
        """
        totals = self.cost_ledger().totals()
        out: list[str] = ["# Trajectory", "", _headline(totals), "", _overview(self.steps), ""]

        shared = None
        if not repeat_instructions:
            prompts = {step.system_prompt for step in self.steps}
            if len(prompts) == 1:
                shared = prompts.pop()
                out += [
                    "## Standing instructions",
                    "",
                    "Identical on every call below, so printed once rather than before each.",
                    "",
                    _fence(shared),
                    "",
                ]

        for number, step in enumerate(self.steps, 1):
            out.extend(_render_step(number, step, hide_instructions=shared is not None))
        out += ["## Cost", "", self.cost_ledger().summary_table(), ""]
        return "\n".join(out)


def _headline(totals: CostTotals) -> str:
    return (
        f"**Calls:** {totals.calls} | **Prompt tokens:** {totals.usage.prompt_tokens} | "
        f"**Completion tokens:** {totals.usage.completion_tokens} | "
        f"**Estimated cost:** {_usd(totals.usd)}"
    )


def _overview(steps: list[TraceStep]) -> str:
    rows = [
        "| # | Agent | Model | Tier | Retries | Tokens | Cost | Outcome |",
        "|---|---|---|---|---:|---:|---:|---|",
    ]
    for number, step in enumerate(steps, 1):
        rows.append(
            f"| {number} | {step.agent} | {step.provider}/{step.model} | `{step.tier}` | "
            f"{step.retries} | {step.usage.total_tokens} | {_usd(step.usd)} | "
            f"{'validated' if step.succeeded else 'failed'} |"
        )
    return "\n".join(rows)


def _render_step(number: int, step: TraceStep, *, hide_instructions: bool = False) -> list[str]:
    out = [
        f"## {number}. {step.agent} on {step.provider}/{step.model}",
        "",
        f"- **Started:** {step.timestamp}",
        f"- **Tier used:** `{step.tier}`",
        f"- **Retries:** {step.retries}",
        f"- **Tokens:** {step.usage.prompt_tokens} in / {step.usage.completion_tokens} out",
        f"- **Estimated cost:** {_usd(step.usd)}",
        f"- **Outcome:** {'validated' if step.succeeded else 'no valid response'}",
        "",
    ]
    if not hide_instructions:
        out += ["### Instructions", "", _fence(step.system_prompt), ""]
    out += [
        "### Request",
        "",
        _fence(step.user_prompt),
        "",
    ]

    for tier, reason in step.skipped_tiers:
        out += [f"### Tier `{tier}` not attempted", "", reason, ""]

    previous: Attempt | None = None
    for index, attempt in enumerate(step.attempts, 1):
        out += [f"### Attempt {index}, tier `{attempt.tier}`", ""]
        added = _messages_added(previous, attempt)
        if previous is not None and added:
            label = "Sent back to the model" if attempt.tier == previous.tier else "Restarted with"
            out += [f"{label}:", "", _fence(_render_messages(added)), ""]
        if attempt.error is not None:
            out += ["The provider rejected the request:", "", _fence(attempt.error), ""]
        if attempt.raw_response is not None:
            out += ["Response:", "", _fence(attempt.raw_response), ""]
        if attempt.validation_error is not None:
            out += ["The response did not validate:", "", _fence(attempt.validation_error), ""]
        elif attempt.error is None:
            out += ["Validated against the schema.", ""]
        previous = attempt

    if step.parsed is not None:
        rendered = json.dumps(step.parsed, indent=2, ensure_ascii=False)
        out += ["### Result", "", _fence(rendered, "json"), ""]
    return out


def _messages_added(previous: Attempt | None, attempt: Attempt) -> list[dict[str, str]]:
    if previous is None:
        return []
    shared = len(previous.messages)
    if attempt.messages[:shared] == previous.messages:
        return attempt.messages[shared:]
    return attempt.messages


def _render_messages(messages: list[dict[str, str]]) -> str:
    return "\n\n".join(f"[{m.get('role', '?')}]\n{m.get('content', '')}" for m in messages)


def _usd(amount: float | None) -> str:
    return "unpriced" if amount is None else f"${amount:.4f}"


def _fence(text: str, language: str = "") -> str:
    """Fence `text` with enough backticks that its own backticks cannot escape the block."""
    longest = max((len(run) for run in _BACKTICKS.findall(text)), default=0)
    ticks = "`" * max(3, longest + 1)
    return f"{ticks}{language}\n{text}\n{ticks}"
