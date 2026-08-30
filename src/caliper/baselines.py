"""What Caliper is measured against.

`SinglePrompt` is the honest comparison: the same model, the same protocol text, the same chart,
asked the question directly and given one turn to answer it. That is what a competent engineer
builds first, and if the rest of this repository does not beat it on the cases that matter, the rest
of this repository is not worth its complexity.

The three trivial baselines are there to stop the headline number from being vacuous. A system that
abstains on everything commits no unsafe errors at all, and the only thing that exposes it is
putting it in the same table with its coverage of zero. `AlwaysEligible` is the mirror image, and
`RandomOutcome` gives the floor a shape.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date
from importlib import resources
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict

from caliper.chart import summarise
from caliper.llm import LLMClient, LLMError
from caliper.logic import ScreeningOutcome
from caliper.record import PatientIndex

BASELINE_SYSTEM_PROMPT = (
    resources.files("caliper.agents.prompts").joinpath("baseline.md").read_text(encoding="utf-8")
)


class _Decision(BaseModel):
    """What the single-prompt baseline is asked for."""

    model_config = ConfigDict(extra="forbid")

    outcome: Literal["eligible", "ineligible", "needs_review"]
    reasoning: str


@dataclass(frozen=True)
class BaselineDecision:
    outcome: ScreeningOutcome | None
    rationale: str
    cost_usd: float | None = None
    failed: bool = False


class Baseline(Protocol):
    name: str

    def decide(
        self, criteria_text: str, patient: PatientIndex, as_of: date
    ) -> BaselineDecision: ...


class SinglePrompt:
    """One call: protocol text plus chart, answer the question.

    The chart is rendered with the same `chart.summarise` the rest of the system uses, so the
    baseline is not handicapped by being shown less than Caliper reads.
    """

    name = "single_prompt"

    def __init__(self, client: LLMClient):
        self.client = client

    def decide(self, criteria_text: str, patient: PatientIndex, as_of: date) -> BaselineDecision:
        user = (
            f"Screening date: {as_of.isoformat()}\n\n"
            f"## Trial eligibility criteria\n\n{criteria_text}\n\n"
            f"## Patient chart\n\n{summarise(patient, as_of=as_of)}\n"
        )
        try:
            completion = self.client.complete(
                system=BASELINE_SYSTEM_PROMPT,
                user=user,
                model_cls=_Decision,
                agent="baseline",
            )
        except LLMError as error:
            return BaselineDecision(outcome=None, rationale=str(error), failed=True)

        return BaselineDecision(
            outcome=ScreeningOutcome(completion.value.outcome),
            rationale=completion.value.reasoning,
            cost_usd=completion.cost.usd,
        )


@dataclass
class _Fixed:
    outcome: ScreeningOutcome
    name: str

    def decide(self, criteria_text: str, patient: PatientIndex, as_of: date) -> BaselineDecision:
        return BaselineDecision(
            outcome=self.outcome, rationale=f"fixed answer: {self.outcome.value}", cost_usd=0.0
        )


def AlwaysNeedsReview() -> _Fixed:  # noqa: N802 - reads as a constructor at the call site
    """The vacuity control: perfect safety, zero usefulness."""
    return _Fixed(ScreeningOutcome.NEEDS_REVIEW, "always_needs_review")


def AlwaysEligible() -> _Fixed:  # noqa: N802
    """The opposite failure: maximal coverage, maximal harm."""
    return _Fixed(ScreeningOutcome.ELIGIBLE, "always_eligible")


def AlwaysIneligible() -> _Fixed:  # noqa: N802
    """The majority answer, and the reason accuracy is the weakest column in the table.

    Most patients are not eligible for most trials, and the corrected key expects `ineligible` for
    forty-one of fifty-one cases. A system that answers only that scores well while deciding
    nothing, so it belongs beside the real arms where a reader can see it — the same argument that
    puts `always_needs_review` there.
    """
    return _Fixed(ScreeningOutcome.INELIGIBLE, "always_ineligible")


class RandomOutcome:
    """A seeded coin, so the floor of the results table is reproducible."""

    name = "random"

    def __init__(self, seed: int):
        self._random = random.Random(seed)

    def decide(self, criteria_text: str, patient: PatientIndex, as_of: date) -> BaselineDecision:
        outcome = self._random.choice(list(ScreeningOutcome))
        return BaselineDecision(outcome=outcome, rationale="random choice", cost_usd=0.0)
