"""One client, one method, three ways of asking — and a single gate they all pass through.

Providers disagree about structured output, and the same provider disagrees with itself from one
model to the next. The client answers that with a ladder:

1. native strict `json_schema`, generated from the Pydantic model;
2. `json_object`, with the schema pasted into the instructions;
3. plain text, with the JSON dug back out of whatever prose came with it.

The rung a call starts on is decided by the profile, and a rung that fails drops to the next one.
Every rung ends in `Model.model_validate_json`. That is the point of the whole arrangement: a
response is data only once Pydantic says so, and a response that never says so raises rather than
returning something unchecked. A failed validation is re-asked, with the error text handed back to
the model, up to `max_retries` times per rung.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from caliper.llm.cost import CostLedger, CostRecord, Usage, estimate_cost
from caliper.llm.errors import LLMError
from caliper.llm.parsing import JSONExtractionError, extract_json_object
from caliper.llm.provider import ProviderProfile, StructuredOutput, resolve_api_key
from caliper.llm.schema import (
    StrictSchemaError,
    count_union_parameters,
    strict_schema_problems,
    to_strict_schema,
)
from caliper.llm.trace import Attempt, TraceStep, Trajectory

DEFAULT_AGENT = "compiler"
DEFAULT_MAX_RETRIES = 2
DEFAULT_TIMEOUT_SECONDS = 180.0


class Tier(StrEnum):
    """The rungs of the ladder, strongest first."""

    JSON_SCHEMA = "json_schema"
    JSON_OBJECT = "json_object"
    TEXT = "text"


_LADDER: tuple[Tier, ...] = (Tier.JSON_SCHEMA, Tier.JSON_OBJECT, Tier.TEXT)

_STARTING_RUNG = {
    StructuredOutput.JSON_SCHEMA: 0,
    StructuredOutput.JSON_OBJECT: 1,
    StructuredOutput.NONE: 2,
}

_JSON_OBJECT_INSTRUCTION = (
    "Reply with a single JSON object and nothing else. It must conform to this JSON schema:"
)
_TEXT_INSTRUCTION = (
    "Reply with a single JSON object inside a ```json fenced code block, and nothing else. "
    "It must conform to this JSON schema:"
)
_RETRY_INSTRUCTION = (
    "That response did not validate against the required schema.\n\n{error}\n\n"
    "Return the corrected JSON object. Output the object only."
)


class LadderExhausted(LLMError):
    """Every rung was tried and none produced a value the model would accept."""

    def __init__(self, model_name: str, attempts: list[Attempt]):
        self.model_name = model_name
        self.attempts = attempts
        tiers = ", ".join(dict.fromkeys(str(a.tier) for a in attempts))
        last = (attempts[-1].validation_error or attempts[-1].error) if attempts else "none"
        super().__init__(
            f"no valid {model_name} after {len(attempts)} attempts across tiers [{tiers}]; "
            f"last failure: {last}"
        )


@dataclass(frozen=True)
class Completion[T: BaseModel]:
    """A validated value, what it cost, and the trace step that produced it."""

    value: T
    cost: CostRecord
    step: TraceStep


class LLMClient:
    """Compiles prompts into validated Pydantic values against one provider profile."""

    def __init__(
        self,
        profile: ProviderProfile,
        *,
        transport: Any | None = None,
        trajectory: Trajectory | None = None,
        ledger: CostLedger | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        temperature: float = 0.0,
        seed: int | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        self.profile = profile
        self.trajectory = trajectory if trajectory is not None else Trajectory()
        self.ledger = ledger if ledger is not None else CostLedger()
        self.max_retries = max_retries
        self.temperature = temperature
        self.seed = seed
        self.timeout = timeout
        self._env = env
        self._transport = transport

    def complete[T: BaseModel](
        self,
        *,
        system: str,
        user: str,
        model_cls: type[T],
        agent: str = DEFAULT_AGENT,
    ) -> Completion[T]:
        """Ask the model for a `model_cls`, and return one or raise.

        `system` is the agent's standing instructions and `user` the material to work on. The
        returned value has been through every validator `model_cls` declares.
        """
        # Resolved before anything is recorded: a missing credential is a configuration mistake,
        # not a failed rung, and should not be buried in a trajectory as one.
        self._ensure_transport()

        step = TraceStep(
            agent=agent,
            provider=self.profile.provider,
            model=self.profile.model,
            system_prompt=system,
            user_prompt=user,
        )
        try:
            for tier in self._tiers(step, model_cls):
                value = self._run_tier(tier, step, system, user, model_cls)
                if value is not None:
                    return Completion(value=value, cost=step.cost_record(), step=step)
            raise LadderExhausted(model_cls.__name__, step.attempts)
        finally:
            self.trajectory.append(step)
            self.ledger.add(step.cost_record())

    def _tiers[T: BaseModel](self, step: TraceStep, model_cls: type[T]) -> tuple[Tier, ...]:
        """The rungs worth attempting for this model on this provider.

        A provider that declares a union-parameter budget is taken at its word: a schema over the
        limit is refused deterministically, so sending it wastes a round trip on every call and
        leaves a 400 in the trajectory for a reader to interpret. The rung is skipped instead, with
        the arithmetic recorded.
        """
        tiers = _LADDER[_STARTING_RUNG[self.profile.structured_output] :]
        budget = self.profile.max_union_parameters
        if budget is None or "json_schema" not in tiers:
            return tiers

        try:
            schema = to_strict_schema(model_cls, inline_refs=self.profile.inline_schema_refs)
        except StrictSchemaError:
            return tiers
        unions = count_union_parameters(schema)
        if unions <= budget:
            return tiers

        step.skipped_tiers.append(
            (
                "json_schema",
                f"{self.profile.name} compiles at most {budget} union-typed parameters and this "
                f"schema has {unions}; strict mode would refuse it",
            )
        )
        return tuple(t for t in tiers if t != "json_schema")

    def _run_tier[T: BaseModel](
        self,
        tier: Tier,
        step: TraceStep,
        system: str,
        user: str,
        model_cls: type[T],
    ) -> T | None:
        """Work one rung until it validates, runs out of retries, or the provider refuses."""
        try:
            system_prompt, response_format = self._tier_request(tier, model_cls, system)
        except StrictSchemaError as exc:
            # The model cannot be expressed in the strict dialect. Say so in the trace and drop a
            # rung rather than sending a schema the provider will silently choke on.
            step.attempts.append(Attempt(tier=tier, messages=[], error=str(exc)))
            return None

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user},
        ]
        for _ in range(self.max_retries + 1):
            attempt = Attempt(tier=tier, messages=copy.deepcopy(messages))
            step.attempts.append(attempt)

            try:
                content, usage = self._call(messages, response_format)
            except Exception as exc:
                # Every provider SDK raises its own hierarchy, and the interesting case — a model
                # that will not accept this `response_format` — has no portable type. A request
                # the provider refused will be refused identically on a re-ask, so drop a rung
                # instead of retrying. Transport hiccups are already retried inside the SDK.
                attempt.error = f"{type(exc).__name__}: {exc}"
                return None

            attempt.raw_response = content
            attempt.usage = usage
            attempt.usd = estimate_cost(self.profile, usage)

            try:
                value = model_cls.model_validate_json(extract_json_object(content))
            except (JSONExtractionError, ValidationError) as exc:
                attempt.validation_error = str(exc)
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": _RETRY_INSTRUCTION.format(error=exc)})
                continue

            step.parsed = value.model_dump(mode="json")
            return value
        return None

    def _tier_request(
        self, tier: Tier, model_cls: type[BaseModel], system: str
    ) -> tuple[str, dict[str, Any] | None]:
        """The system prompt and `response_format` for one rung."""
        prompt = self._system_prompt_for(tier, model_cls, system)
        if tier is Tier.JSON_SCHEMA:
            schema = to_strict_schema(model_cls, inline_refs=self.profile.inline_schema_refs)
            problems = strict_schema_problems(schema)
            if problems:
                # Venice answers a malformed schema with a timeout rather than a 400, which is an
                # expensive way to learn about a typo. Refuse locally instead.
                raise StrictSchemaError(
                    f"{model_cls.__name__} did not transform into a strict schema: "
                    + "; ".join(problems)
                )
            return prompt, {
                "type": "json_schema",
                "json_schema": {
                    "name": model_cls.__name__,
                    "strict": True,
                    "schema": schema,
                },
            }
        if tier is Tier.JSON_OBJECT:
            return prompt, {"type": "json_object"}
        return prompt, None

    def _system_prompt_for(self, tier: Tier, model_cls: type[BaseModel], system: str) -> str:
        """Below the top rung the schema has to travel in the prompt, since nothing enforces it."""
        if tier is Tier.JSON_SCHEMA:
            return system
        instruction = _JSON_OBJECT_INSTRUCTION if tier is Tier.JSON_OBJECT else _TEXT_INSTRUCTION
        schema = json.dumps(self._prompt_schema(model_cls), indent=2)
        return f"{system}\n\n{instruction}\n\n{schema}"

    def _prompt_schema(self, model_cls: type[BaseModel]) -> dict[str, Any]:
        """The schema to paste into a prompt: the strict form if it exists, else Pydantic's own."""
        try:
            return to_strict_schema(model_cls, inline_refs=self.profile.inline_schema_refs)
        except StrictSchemaError:
            return model_cls.model_json_schema()

    def _call(
        self, messages: list[dict[str, str]], response_format: dict[str, Any] | None
    ) -> tuple[str, Usage]:
        payload: dict[str, Any] = {
            "model": self.profile.model,
            "messages": messages,
            "temperature": self.temperature,
            # Recorded runs must be replayable, and a stream is not a body VCR can match on.
            "stream": False,
        }
        if response_format is not None:
            payload["response_format"] = response_format
        if self.seed is not None:
            payload["seed"] = self.seed
        extra_body = self.profile.request_extra_body()
        if extra_body:
            payload["extra_body"] = extra_body

        response = self.transport.chat.completions.create(**payload)
        # An empty message is billed like any other and is treated as a failed response rather
        # than a failed request, so that it is re-asked instead of costing us a rung.
        content = response.choices[0].message.content or ""
        return content, _usage_of(response)

    @property
    def transport(self) -> Any:
        """The OpenAI-compatible client, built on first use so a key is only needed when calling."""
        if self._transport is None:
            self._transport = OpenAI(
                base_url=self.profile.base_url,
                api_key=resolve_api_key(self.profile, self._env),
                timeout=self.timeout,
            )
        return self._transport

    def _ensure_transport(self) -> None:
        _ = self.transport


def _usage_of(response: Any) -> Usage:
    usage = getattr(response, "usage", None)
    if usage is None:
        return Usage()
    return Usage(
        prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
        completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
    )
