"""What every agent is handed.

One object rather than four arguments, so that adding a shared facility later does not ripple
through every call site. It carries the client, the trajectory everything is recorded into, and the
concept store that lets one trial's terminology work pay for the next trial's.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from caliper.llm import CostLedger, LLMClient, Trajectory


@dataclass
class AgentContext:
    client: LLMClient
    trajectory: Trajectory = field(default_factory=Trajectory)
    ledger: CostLedger = field(default_factory=CostLedger)
    memory: object | None = None
    """The concept store. Typed loosely here so `agents.base` stays free of import cycles."""

    as_of: date | None = None
    """The screening date, when an agent needs to reason about recency."""

    def __post_init__(self) -> None:
        # The client owns the recording; sharing its objects keeps one run in one trajectory.
        if self.client.trajectory is not self.trajectory:
            self.client.trajectory = self.trajectory
