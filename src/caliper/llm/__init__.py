"""The model runtime: provider profiles, a validating client, trajectories and cost accounting.

The layer exists to make two guarantees. Nothing leaves it that Pydantic has not validated, and
every call it makes is written down in enough detail that a reader can reconstruct the run
without opening this package.

    from caliper.ir import CriteriaSet
    from caliper.llm import LLMClient, Trajectory, profile_from_env

    trajectory = Trajectory()
    client = LLMClient(profile_from_env(), trajectory=trajectory)
    result = client.complete(
        system="Compile eligibility criteria into the schema.",
        user=protocol_text,
        model_cls=CriteriaSet,
        agent="compiler",
    )
    trajectory.write_jsonl("runs/latest/trajectory.jsonl")
"""

from caliper.llm.client import (
    Completion,
    LadderExhausted,
    LLMClient,
    Tier,
)
from caliper.llm.cost import CostLedger, CostRecord, CostTotals, Usage, estimate_cost
from caliper.llm.errors import LLMError
from caliper.llm.parsing import JSONExtractionError, extract_json_object
from caliper.llm.provider import (
    MissingAPIKeyError,
    ProviderProfile,
    StructuredOutput,
    UnknownProfileError,
    builtin_profiles,
    has_api_key,
    profile_for,
    profile_from_env,
    resolve_api_key,
)
from caliper.llm.schema import StrictSchemaError, strict_schema_problems, to_strict_schema
from caliper.llm.trace import Attempt, TraceStep, Trajectory

__all__ = [
    "Attempt",
    "Completion",
    "CostLedger",
    "CostRecord",
    "CostTotals",
    "JSONExtractionError",
    "LLMClient",
    "LLMError",
    "LadderExhausted",
    "MissingAPIKeyError",
    "ProviderProfile",
    "StrictSchemaError",
    "StructuredOutput",
    "Tier",
    "TraceStep",
    "Trajectory",
    "UnknownProfileError",
    "Usage",
    "builtin_profiles",
    "estimate_cost",
    "extract_json_object",
    "has_api_key",
    "profile_for",
    "profile_from_env",
    "resolve_api_key",
    "strict_schema_problems",
    "to_strict_schema",
]
