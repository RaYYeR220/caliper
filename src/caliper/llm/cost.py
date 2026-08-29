"""Token accounting, priced from the profile rather than from a hard-coded table.

Two models can produce the same answer for a twenty-fold difference in cost, so every call is
priced as it happens and attributed to the agent that made it. Where a model's published price is
not known, the cost is `None` rather than a plausible-looking guess: an unpriced call is counted
and reported separately, and the totals stay honest.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from caliper.llm.provider import ProviderProfile

TOKENS_PER_PRICE_UNIT = 1_000_000


@dataclass(frozen=True, slots=True)
class Usage:
    """Tokens billed for one or more calls."""

    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            self.prompt_tokens + other.prompt_tokens,
            self.completion_tokens + other.completion_tokens,
        )

    def to_dict(self) -> dict[str, int]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Usage:
        return cls(
            prompt_tokens=int(payload.get("prompt_tokens", 0)),
            completion_tokens=int(payload.get("completion_tokens", 0)),
        )


@dataclass(frozen=True, slots=True)
class CostRecord:
    """What one completed call cost, and who is answerable for it."""

    agent: str
    provider: str
    model: str
    usage: Usage
    usd: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "provider": self.provider,
            "model": self.model,
            "usage": self.usage.to_dict(),
            "usd": self.usd,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> CostRecord:
        return cls(
            agent=payload["agent"],
            provider=payload["provider"],
            model=payload["model"],
            usage=Usage.from_dict(payload.get("usage", {})),
            usd=payload.get("usd"),
        )


def estimate_cost(profile: ProviderProfile, usage: Usage) -> float | None:
    """Price `usage` at the profile's per-million-token rates, or `None` if they are unknown."""
    if profile.input_usd_per_mtok is None or profile.output_usd_per_mtok is None:
        return None
    return (
        usage.prompt_tokens * profile.input_usd_per_mtok
        + usage.completion_tokens * profile.output_usd_per_mtok
    ) / TOKENS_PER_PRICE_UNIT


@dataclass
class CostTotals:
    """An aggregate over some slice of the ledger."""

    calls: int = 0
    usage: Usage = field(default_factory=Usage)
    usd: float = 0.0
    unpriced_calls: int = 0

    def add(self, record: CostRecord) -> None:
        self.calls += 1
        self.usage = self.usage + record.usage
        if record.usd is None:
            self.unpriced_calls += 1
        else:
            self.usd += record.usd

    def to_dict(self) -> dict[str, Any]:
        return {
            "calls": self.calls,
            "usage": self.usage.to_dict(),
            "usd": self.usd,
            "unpriced_calls": self.unpriced_calls,
        }


class CostLedger:
    """Every priced call in a run, aggregable by agent and by model."""

    def __init__(self, records: Iterable[CostRecord] = ()):
        self._records: list[CostRecord] = list(records)

    @property
    def records(self) -> tuple[CostRecord, ...]:
        return tuple(self._records)

    def add(self, record: CostRecord) -> None:
        self._records.append(record)

    def totals(self) -> CostTotals:
        overall = CostTotals()
        for record in self._records:
            overall.add(record)
        return overall

    def by_agent(self) -> dict[str, CostTotals]:
        return self._aggregate(lambda record: record.agent)

    def by_model(self) -> dict[str, CostTotals]:
        return self._aggregate(lambda record: record.model)

    def _aggregate(self, key: Callable[[CostRecord], str]) -> dict[str, CostTotals]:
        buckets: dict[str, CostTotals] = defaultdict(CostTotals)
        for record in self._records:
            buckets[key(record)].add(record)
        return dict(buckets)

    def summary_table(self) -> str:
        """A small Markdown summary, for the end of a trajectory or a run report."""
        lines = ["| Agent | Calls | Prompt | Completion | Cost |", "|---|---:|---:|---:|---:|"]
        lines += [_row(name, totals) for name, totals in sorted(self.by_agent().items())]
        lines += ["", "| Model | Calls | Prompt | Completion | Cost |", "|---|---:|---:|---:|---:|"]
        lines += [_row(name, totals) for name, totals in sorted(self.by_model().items())]

        overall = self.totals()
        lines += ["", f"**Total:** {overall.usage.total_tokens} tokens, {_money(overall)}"]
        return "\n".join(lines)


def _row(name: str, totals: CostTotals) -> str:
    return (
        f"| {name} | {totals.calls} | {totals.usage.prompt_tokens} | "
        f"{totals.usage.completion_tokens} | {_money(totals)} |"
    )


def _money(totals: CostTotals) -> str:
    rendered = f"${totals.usd:.4f}"
    if totals.unpriced_calls:
        rendered += f" (+{totals.unpriced_calls} unpriced)"
    return rendered
