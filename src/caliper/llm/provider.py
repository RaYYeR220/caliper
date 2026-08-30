"""Which model we are talking to, where it lives, what it can do and what it costs.

A `ProviderProfile` is the only place in the codebase that knows a provider's quirks: the base
URL, the name of the environment variable holding its key, whether the model can be held to a
strict JSON schema, its published per-million-token prices, and the vendor-specific `extra_body`
that has to ride along on every request. Profiles never hold a key — only the name of the
variable it lives in — so a profile is safe to print, log and serialise into a trajectory.
"""

from __future__ import annotations

import copy
import os
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any

from caliper.llm.errors import LLMError

VENICE_BASE_URL = "https://api.venice.ai/api/v1"
VENICE_UNION_LIMIT = 16
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Venice prepends a persona system prompt unless it is switched off. A clinical compiler that has
# been told it is a chatty assistant is a different program from the one we tested.
VENICE_EXTRA_BODY: dict[str, Any] = {"venice_parameters": {"include_venice_system_prompt": False}}

# OpenRouter will happily route to an endpoint that ignores `response_format`. This pins it to
# endpoints that honour every parameter we send.
OPENROUTER_EXTRA_BODY: dict[str, Any] = {"provider": {"require_parameters": True}}


class UnknownProfileError(LLMError):
    """A provider or model was requested that has no built-in profile."""


class MissingAPIKeyError(LLMError):
    """The environment variable a profile depends on is unset or empty."""


class StructuredOutput(StrEnum):
    """The strongest response format a model will honour.

    This is the top rung of the ladder for a given model, not a list of everything it accepts:
    the client starts here and works downwards.
    """

    JSON_SCHEMA = "json_schema"
    JSON_OBJECT = "json_object"
    NONE = "none"


@dataclass(frozen=True)
class ProviderProfile:
    """Everything the client needs to reach one model, minus the credential itself."""

    provider: str
    model: str
    base_url: str
    api_key_env: str
    structured_output: StructuredOutput
    input_usd_per_mtok: float | None
    output_usd_per_mtok: float | None
    extra_body: Mapping[str, Any] = field(default_factory=dict, hash=False)
    # Inlining `$defs` costs a few hundred tokens and buys compatibility with providers whose
    # strict mode does not resolve references. Turn it off only for recursive models.
    inline_schema_refs: bool = True
    max_union_parameters: int | None = None
    """How many union-typed parameters this provider's strict mode will compile, if it says.

    Venice answers a schema over its limit with a 400 naming the number, so the ladder recovers on
    its own; declaring the limit means the request is never sent and the trajectory records the
    reason instead of a rejection the reader has to interpret.
    """

    notes: str = ""

    @property
    def name(self) -> str:
        """The key this profile is registered under, e.g. `venice:claude-sonnet-5`."""
        return f"{self.provider}:{self.model}"

    @property
    def supports_json_schema(self) -> bool:
        return self.structured_output is StructuredOutput.JSON_SCHEMA

    def request_extra_body(self) -> dict[str, Any]:
        """A private copy of the vendor payload, safe for the caller to mutate."""
        return copy.deepcopy(dict(self.extra_body))

    def with_capabilities(self, models_payload: Mapping[str, Any]) -> ProviderProfile:
        """Return this profile updated from a Venice `GET /models?type=text` response.

        Structured-output support is per-model and changes without notice, so the built-in flags
        below are a starting point rather than a fact. That endpoint needs no authentication,
        which makes this cheap to run before a batch.
        """
        for entry in models_payload.get("data", []):
            if entry.get("id") != self.model:
                continue
            capabilities = entry.get("model_spec", {}).get("capabilities", {})
            supported = bool(capabilities.get("supportsResponseSchema"))
            # Venice implements `json_object` through the same machinery as `json_schema`, so a
            # model that cannot do one is assumed not to do the other.
            level = StructuredOutput.JSON_SCHEMA if supported else StructuredOutput.NONE
            return replace(self, structured_output=level)
        raise UnknownProfileError(f"{self.model!r} is not in the models listing")


def _venice(
    model: str,
    *,
    structured_output: StructuredOutput,
    input_usd: float,
    output_usd: float,
    notes: str = "",
) -> ProviderProfile:
    return ProviderProfile(
        provider="venice",
        model=model,
        base_url=VENICE_BASE_URL,
        api_key_env="VENICE_API_KEY",
        structured_output=structured_output,
        # Measured against the live endpoint: a schema with more union-typed parameters is
        # answered with a 400 naming this figure.
        max_union_parameters=VENICE_UNION_LIMIT,
        input_usd_per_mtok=input_usd,
        output_usd_per_mtok=output_usd,
        extra_body=VENICE_EXTRA_BODY,
        notes=notes,
    )


def _openrouter(
    model: str,
    *,
    structured_output: StructuredOutput = StructuredOutput.JSON_SCHEMA,
    input_usd: float | None,
    output_usd: float | None,
    notes: str = "",
) -> ProviderProfile:
    return ProviderProfile(
        provider="openrouter",
        model=model,
        base_url=OPENROUTER_BASE_URL,
        api_key_env="OPENROUTER_API_KEY",
        structured_output=structured_output,
        input_usd_per_mtok=input_usd,
        output_usd_per_mtok=output_usd,
        extra_body=OPENROUTER_EXTRA_BODY,
        notes=notes,
    )


_BUILTIN: tuple[ProviderProfile, ...] = (
    _venice(
        "claude-sonnet-5",
        structured_output=StructuredOutput.JSON_SCHEMA,
        input_usd=2.0,
        output_usd=10.0,
        notes="Primary compiler model. 1M token context.",
    ),
    _venice(
        "zai-org-glm-5",
        structured_output=StructuredOutput.JSON_SCHEMA,
        input_usd=1.0,
        output_usd=3.20,
    ),
    _venice(
        "deepseek-v4-flash",
        structured_output=StructuredOutput.JSON_SCHEMA,
        input_usd=0.14,
        output_usd=0.28,
    ),
    _venice(
        "qwen3-235b-a22b-instruct-2507",
        structured_output=StructuredOutput.NONE,
        input_usd=0.15,
        output_usd=0.75,
        notes="No response-schema support; the client drops straight to the text rung.",
    ),
    _venice(
        "mistral-small-3-2-24b-instruct",
        structured_output=StructuredOutput.JSON_SCHEMA,
        input_usd=0.09,
        output_usd=0.25,
    ),
    _openrouter("anthropic/claude-sonnet-5", input_usd=2.0, output_usd=10.0),
    _openrouter(
        "google/gemini-3.1-pro-preview",
        input_usd=None,
        output_usd=None,
        notes="Prices not confirmed; calls against this model are reported as unpriced.",
    ),
    _openrouter(
        "deepseek/deepseek-v4-pro",
        input_usd=None,
        output_usd=None,
        notes="Prices not confirmed; calls against this model are reported as unpriced.",
    ),
)

DEFAULT_PROVIDER = "venice"
DEFAULT_MODELS = {"venice": "claude-sonnet-5", "openrouter": "anthropic/claude-sonnet-5"}


def builtin_profiles() -> dict[str, ProviderProfile]:
    """The shipped profiles, keyed by `provider:model`."""
    return {profile.name: profile for profile in _BUILTIN}


def profile_for(provider: str, model: str) -> ProviderProfile:
    """Look up one built-in profile, or explain what is on offer."""
    profiles = builtin_profiles()
    try:
        return profiles[f"{provider}:{model}"]
    except KeyError:
        known = ", ".join(sorted(profiles))
        raise UnknownProfileError(
            f"no profile for provider {provider!r} and model {model!r}; known profiles: {known}"
        ) from None


def profile_from_env(env: Mapping[str, str] | None = None) -> ProviderProfile:
    """Resolve a profile from `CALIPER_PROVIDER` and `CALIPER_MODEL`.

    Defaults to Venice's `claude-sonnet-5`, which is the model the headline results were compiled
    with.
    """
    env = os.environ if env is None else env
    provider = env.get("CALIPER_PROVIDER", DEFAULT_PROVIDER).strip().lower()
    if provider not in DEFAULT_MODELS:
        known = ", ".join(sorted(DEFAULT_MODELS))
        raise UnknownProfileError(f"unknown provider {provider!r}; known providers: {known}")
    model = env.get("CALIPER_MODEL", DEFAULT_MODELS[provider]).strip()
    return profile_for(provider, model)


def resolve_api_key(profile: ProviderProfile, env: Mapping[str, str] | None = None) -> str:
    """Read the profile's key out of the environment.

    The value is returned to the caller and never stored, logged or put in a trajectory. Only the
    variable's name appears in error messages.

    A profile that names no variable needs no credential: a local command is reached by running it,
    not by authenticating to it.
    """
    if not profile.api_key_env:
        return ""
    env = os.environ if env is None else env
    key = (env.get(profile.api_key_env) or "").strip()
    if not key:
        raise MissingAPIKeyError(
            f"{profile.api_key_env} is not set; it is needed to reach {profile.name}"
        )
    return key


def has_api_key(profile: ProviderProfile, env: Mapping[str, str] | None = None) -> bool:
    """Whether the profile's credential is present, without reading its value out."""
    if not profile.api_key_env:
        return True
    env = os.environ if env is None else env
    return bool((env.get(profile.api_key_env) or "").strip())
