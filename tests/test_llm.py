"""The model-runtime layer: strict schemas, the fallback ladder, trajectories and cost.

Everything here runs offline. The only tests that touch a network stack are marked `vcr` and
replay a cassette from `tests/cassettes/`; they are skipped until someone with an API key records
them with `pytest --record-mode=once`. Authorization headers are stripped on the way in, and
`TestCassetteHygiene` fails the build if a secret ever reaches the cassette directory.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from caliper.ir import CriteriaSet
from caliper.llm import (
    CostLedger,
    CostRecord,
    JSONExtractionError,
    LadderExhausted,
    LLMClient,
    MissingAPIKeyError,
    ProviderProfile,
    StrictSchemaError,
    StructuredOutput,
    Tier,
    Trajectory,
    UnknownProfileError,
    Usage,
    builtin_profiles,
    estimate_cost,
    extract_json_object,
    profile_from_env,
    strict_schema_problems,
    to_strict_schema,
)
from caliper.wire import to_criteria_set, wire_criteria_set_model

CASSETTE_DIR = Path(__file__).parent / "cassettes"


# The compiler talks to a model through the depth-bounded mirror, not the recursive IR itself.
WIRE = wire_criteria_set_model(2)

# --------------------------------------------------------------------------------------------
# VCR configuration. Body matching matters because every call in this project hits the same URL.
# --------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def vcr_cassette_dir() -> str:
    return str(CASSETTE_DIR)


@pytest.fixture(scope="module")
def vcr_config() -> dict:
    return {
        "filter_headers": [
            ("authorization", "REDACTED"),
            ("x-api-key", "REDACTED"),
            ("api-key", "REDACTED"),
            ("openai-organization", "REDACTED"),
            ("cookie", "REDACTED"),
            ("set-cookie", "REDACTED"),
        ],
        "filter_query_parameters": [("api_key", "REDACTED")],
        "match_on": ["method", "scheme", "host", "port", "path", "body"],
        "decode_compressed_response": True,
        "allow_playback_repeats": False,
    }


# --------------------------------------------------------------------------------------------
# Fixtures: models and a fake transport that speaks the slice of the OpenAI surface we use.
# --------------------------------------------------------------------------------------------


class Sample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    count: int
    note: str | None = None


class Node(BaseModel):
    """A self-referential model, used to prove the inliner refuses to loop forever."""

    label: str
    child: Node | None = None


VALID_SAMPLE = '{"name": "aspirin", "count": 2, "note": null}'


class Reply:
    """One canned assistant turn, with the usage the provider would have reported."""

    def __init__(self, content: str, prompt_tokens: int = 100, completion_tokens: int = 20):
        self.content = content
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class FakeTransport:
    """Stand-in for `openai.OpenAI`, exposing only `chat.completions.create`.

    Replies are consumed in order. An `Exception` in the queue is raised instead of returned,
    which is how a provider rejecting a `response_format` is simulated.
    """

    def __init__(self, replies: list[Reply | Exception]):
        self.replies = list(replies)
        self.requests: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        if not self.replies:
            raise AssertionError("the client asked for more turns than the test provided")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=reply.content))],
            usage=SimpleNamespace(
                prompt_tokens=reply.prompt_tokens,
                completion_tokens=reply.completion_tokens,
            ),
        )


def a_profile(**overrides) -> ProviderProfile:
    defaults = dict(
        provider="venice",
        model="test-model",
        base_url="https://example.invalid/v1",
        api_key_env="TEST_API_KEY",
        structured_output=StructuredOutput.JSON_SCHEMA,
        input_usd_per_mtok=1.0,
        output_usd_per_mtok=2.0,
    )
    return ProviderProfile(**{**defaults, **overrides})


def a_client(replies, *, profile=None, **kwargs):
    transport = FakeTransport(replies)
    client = LLMClient(profile or a_profile(), transport=transport, **kwargs)
    return client, transport


# --------------------------------------------------------------------------------------------


class TestStrictSchema:
    def test_every_object_forbids_additional_properties(self):
        schema = to_strict_schema(WIRE)
        objects = list(_objects(schema))
        assert objects, "expected the walker to find object schemas"
        assert all(o["additionalProperties"] is False for o in objects)

    def test_every_property_is_required(self):
        schema = to_strict_schema(WIRE)
        for obj in _objects(schema):
            assert set(obj["required"]) == set(obj["properties"])

    def test_optional_scalars_are_widened_to_a_null_union(self):
        schema = to_strict_schema(Sample)
        assert schema["properties"]["note"]["type"] == ["string", "null"]
        assert "anyOf" not in schema["properties"]["note"]

    def test_optional_objects_stay_an_anyof_with_a_null_branch(self):
        window = _find_property(to_strict_schema(WIRE), "window")
        branches = window["anyOf"]
        assert {"type": "null"} in branches
        assert any(b.get("type") == "object" or "$ref" in b for b in branches)

    def test_the_discriminated_union_becomes_an_anyof_of_tagged_objects(self):
        predicate = _find_property(to_strict_schema(WIRE), "predicate")
        assert "oneOf" not in predicate
        assert "discriminator" not in predicate
        assert len(predicate["anyOf"]) == 5
        tags = {tuple(b["properties"]["type"]["enum"]) for b in predicate["anyOf"]}
        assert ("observation",) in tags
        assert ("condition", "medication", "procedure") in tags

    def test_a_literal_default_becomes_a_single_value_enum(self):
        branches = _find_property(to_strict_schema(WIRE), "predicate")["anyOf"]
        observation = next(
            b for b in branches if b["properties"]["type"]["enum"] == ["observation"]
        )
        assert observation["properties"]["type"] == {"type": "string", "enum": ["observation"]}

    def test_defaults_and_unsupported_validation_keywords_are_dropped(self):
        text = json.dumps(to_strict_schema(WIRE))
        for keyword in ("default", "minLength", "exclusiveMinimum", "oneOf", "discriminator"):
            assert f'"{keyword}"' not in text

    def test_descriptions_survive_because_the_model_reads_them(self):
        schema = to_strict_schema(WIRE)
        assert "description" in schema

    def test_refs_are_inlined_by_default(self):
        text = json.dumps(to_strict_schema(WIRE))
        assert "$ref" not in text
        assert "$defs" not in text

    def test_refs_can_be_preserved_for_providers_that_accept_them(self):
        schema = to_strict_schema(WIRE, inline_refs=False)
        assert "$defs" in schema
        assert schema["properties"]["criteria"]["items"] == {"$ref": "#/$defs/CriterionWireD2"}
        assert not strict_schema_problems(schema)

    def test_a_recursive_model_cannot_be_inlined(self):
        with pytest.raises(StrictSchemaError, match="recursive"):
            to_strict_schema(Node)

    def test_a_recursive_model_survives_with_refs_preserved(self):
        assert not strict_schema_problems(to_strict_schema(Node, inline_refs=False))

    def test_the_transform_is_deterministic(self):
        once, again = to_strict_schema(WIRE), to_strict_schema(WIRE)
        assert json.dumps(once) == json.dumps(again)

    def test_the_validator_catches_a_hand_broken_schema(self):
        broken = {
            "type": "object",
            "properties": {"a": {"type": "string"}, "b": {"type": "string"}},
            "required": ["a"],
        }
        problems = strict_schema_problems(broken)
        assert any("additionalProperties" in p for p in problems)
        assert any("required" in p for p in problems)

    def test_the_validator_catches_a_dangling_ref(self):
        assert strict_schema_problems({"$ref": "#/$defs/Missing"})

    def test_a_clean_schema_has_no_problems(self):
        assert strict_schema_problems(to_strict_schema(WIRE)) == []


def _objects(node) -> list[dict]:
    """Every object schema reachable from `node`, including definitions."""
    found = []
    if isinstance(node, dict):
        if node.get("type") == "object" and "properties" in node:
            found.append(node)
        for value in node.values():
            found.extend(_objects(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(_objects(value))
    return found


def _find_property(schema: dict, name: str) -> dict:
    for obj in _objects(schema):
        if name in obj["properties"]:
            return obj["properties"][name]
    raise AssertionError(f"no property named {name!r} in the schema")


# --------------------------------------------------------------------------------------------


class TestFencedJSONExtraction:
    def test_a_labelled_fence(self):
        text = 'Here you go:\n```json\n{"name": "a", "count": 1}\n```\n'
        assert json.loads(extract_json_object(text))["name"] == "a"

    def test_an_unlabelled_fence(self):
        text = '```\n{"name": "a", "count": 1}\n```'
        assert json.loads(extract_json_object(text))["count"] == 1

    def test_a_bare_object(self):
        assert json.loads(extract_json_object('{"name": "a", "count": 1}'))["name"] == "a"

    def test_prose_before_and_after(self):
        text = 'I compiled two criteria.\n{"name": "a", "count": 1}\nLet me know if that helps.'
        assert json.loads(extract_json_object(text))["count"] == 1

    def test_braces_inside_strings_do_not_confuse_the_scanner(self):
        text = 'note:\n{"name": "a }{ b", "count": 1}\ndone'
        assert json.loads(extract_json_object(text))["name"] == "a }{ b"

    def test_nested_objects_are_returned_whole(self):
        text = 'prose {"outer": {"inner": [1, 2]}} more prose'
        assert json.loads(extract_json_object(text)) == {"outer": {"inner": [1, 2]}}

    def test_prose_containing_a_stray_brace_is_skipped(self):
        text = 'a { not json at all\n{"name": "a", "count": 1}'
        assert json.loads(extract_json_object(text))["name"] == "a"

    def test_text_without_json_is_an_error(self):
        with pytest.raises(JSONExtractionError):
            extract_json_object("I am afraid I cannot help with that.")


# --------------------------------------------------------------------------------------------


class TestTheLadder:
    def test_a_clean_first_attempt_validates_and_costs(self):
        client, transport = a_client([Reply(VALID_SAMPLE, 1000, 500)])
        result = client.complete(system="be exact", user="compile this", model_cls=Sample)

        assert isinstance(result.value, Sample)
        assert result.value.name == "aspirin"
        assert result.step.tier == Tier.JSON_SCHEMA
        assert result.step.retries == 0
        assert result.cost.usd == pytest.approx(1000 / 1e6 * 1.0 + 500 / 1e6 * 2.0)
        assert len(transport.requests) == 1

    def test_tier_one_sends_a_strict_json_schema(self):
        client, transport = a_client([Reply(VALID_SAMPLE)])
        client.complete(system="s", user="u", model_cls=Sample)

        response_format = transport.requests[0]["response_format"]
        assert response_format["type"] == "json_schema"
        assert response_format["json_schema"]["strict"] is True
        assert response_format["json_schema"]["name"] == "Sample"
        assert strict_schema_problems(response_format["json_schema"]["schema"]) == []

    def test_streaming_is_never_requested(self):
        client, transport = a_client([Reply(VALID_SAMPLE)])
        client.complete(system="s", user="u", model_cls=Sample)
        assert transport.requests[0]["stream"] is False

    def test_invalid_json_twice_then_valid_is_recovered_within_tier_one(self):
        replies = [
            Reply("not json at all"),
            Reply('{"name": "", "count": "many"}'),
            Reply(VALID_SAMPLE),
        ]
        client, transport = a_client(replies)
        result = client.complete(system="s", user="u", model_cls=Sample, agent="compiler")

        assert result.value.count == 2
        assert result.step.retries == 2
        assert len(result.step.attempts) == 3
        assert len(result.step.validation_errors) == 2
        assert all(a.tier == Tier.JSON_SCHEMA for a in result.step.attempts)
        assert len(transport.requests) == 3

    def test_the_validation_error_text_is_fed_back_to_the_model(self):
        replies = [Reply('{"name": "", "count": "many"}'), Reply(VALID_SAMPLE)]
        client, transport = a_client(replies)
        client.complete(system="s", user="u", model_cls=Sample)

        retry_messages = transport.requests[1]["messages"]
        assert [m["role"] for m in retry_messages] == ["system", "user", "assistant", "user"]
        assert retry_messages[2]["content"] == '{"name": "", "count": "many"}'
        assert "count" in retry_messages[3]["content"]

    def test_a_model_without_schema_support_falls_straight_to_plain_text(self):
        profile = a_profile(structured_output=StructuredOutput.NONE)
        fenced = Reply(f"Sure:\n```json\n{VALID_SAMPLE}\n```")
        client, transport = a_client([fenced], profile=profile)
        result = client.complete(system="s", user="u", model_cls=Sample)

        assert result.step.tier == Tier.TEXT
        assert len(transport.requests) == 1
        assert "response_format" not in transport.requests[0]

    def test_the_schema_is_pasted_into_the_prompt_below_tier_one(self):
        profile = a_profile(structured_output=StructuredOutput.JSON_OBJECT)
        client, transport = a_client([Reply(VALID_SAMPLE)], profile=profile)
        client.complete(system="be exact", user="u", model_cls=Sample)

        request = transport.requests[0]
        assert request["response_format"] == {"type": "json_object"}
        system = request["messages"][0]["content"]
        assert system.startswith("be exact")
        assert '"additionalProperties"' in system

    def test_a_provider_rejecting_tier_one_drops_to_the_next_rung(self):
        replies = [RuntimeError("response_format is not supported"), Reply(VALID_SAMPLE)]
        client, transport = a_client(replies, max_retries=0)
        result = client.complete(system="s", user="u", model_cls=Sample)

        assert result.step.tier == Tier.JSON_OBJECT
        assert result.step.attempts[0].error is not None
        assert transport.requests[1]["response_format"] == {"type": "json_object"}

    def test_persistent_garbage_walks_the_whole_ladder_then_raises(self):
        client, transport = a_client([Reply("nope") for _ in range(9)])
        with pytest.raises(LadderExhausted) as caught:
            client.complete(system="s", user="u", model_cls=Sample)

        assert len(transport.requests) == 9
        assert {a.tier for a in caught.value.attempts} == set(Tier)
        assert "Sample" in str(caught.value)

    def test_the_failed_ladder_is_still_recorded_in_the_trajectory(self):
        trajectory = Trajectory()
        client, _ = a_client([Reply("nope") for _ in range(9)], trajectory=trajectory)
        with pytest.raises(LadderExhausted):
            client.complete(system="s", user="u", model_cls=Sample, agent="compiler")

        assert len(trajectory.steps) == 1
        assert trajectory.steps[0].parsed is None
        assert len(trajectory.steps[0].attempts) == 9

    def test_unvalidated_data_is_never_returned(self):
        # `count` is not an integer, so no amount of retrying may produce a `Sample`.
        client, _ = a_client([Reply('{"name": "a", "count": []}') for _ in range(9)])
        with pytest.raises(LadderExhausted):
            client.complete(system="s", user="u", model_cls=Sample)

    def test_venice_never_gets_its_persona_prompt(self):
        profile = builtin_profiles()["venice:claude-sonnet-5"]
        client, transport = a_client([Reply(VALID_SAMPLE)], profile=profile)
        client.complete(system="s", user="u", model_cls=Sample)

        assert transport.requests[0]["extra_body"] == {
            "venice_parameters": {"include_venice_system_prompt": False}
        }

    def test_openrouter_only_routes_to_endpoints_that_honour_the_schema(self):
        profile = builtin_profiles()["openrouter:anthropic/claude-sonnet-5"]
        client, transport = a_client([Reply(VALID_SAMPLE)], profile=profile)
        client.complete(system="s", user="u", model_cls=Sample)

        assert transport.requests[0]["extra_body"] == {"provider": {"require_parameters": True}}

    def test_temperature_and_seed_are_sent_when_set(self):
        client, transport = a_client([Reply(VALID_SAMPLE)], temperature=0.2, seed=11)
        client.complete(system="s", user="u", model_cls=Sample)

        assert transport.requests[0]["temperature"] == 0.2
        assert transport.requests[0]["seed"] == 11

    def test_a_missing_key_is_reported_by_name_and_never_by_value(self, monkeypatch):
        monkeypatch.delenv("TEST_API_KEY", raising=False)
        with pytest.raises(MissingAPIKeyError, match="TEST_API_KEY"):
            LLMClient(a_profile()).complete(system="s", user="u", model_cls=Sample)


# --------------------------------------------------------------------------------------------


class TestCost:
    def test_tokens_are_priced_per_million(self):
        profile = a_profile(input_usd_per_mtok=2.0, output_usd_per_mtok=10.0)
        usd = estimate_cost(profile, Usage(prompt_tokens=1_500_000, completion_tokens=200_000))
        assert usd == pytest.approx(1.5 * 2.0 + 0.2 * 10.0)

    def test_an_unpriced_model_reports_no_cost_rather_than_a_guess(self):
        profile = a_profile(input_usd_per_mtok=None, output_usd_per_mtok=None)
        assert estimate_cost(profile, Usage(1000, 1000)) is None

    def test_the_ledger_aggregates_by_agent_and_by_model(self):
        ledger = CostLedger()
        ledger.add(CostRecord("compiler", "venice", "m1", Usage(100, 10), 0.5))
        ledger.add(CostRecord("compiler", "venice", "m2", Usage(200, 20), 1.0))
        ledger.add(CostRecord("critic", "venice", "m1", Usage(300, 30), 2.0))

        by_agent = ledger.by_agent()
        assert by_agent["compiler"].calls == 2
        assert by_agent["compiler"].usd == pytest.approx(1.5)
        assert by_agent["critic"].usage.prompt_tokens == 300

        by_model = ledger.by_model()
        assert by_model["m1"].usd == pytest.approx(2.5)
        assert by_model["m1"].usage.completion_tokens == 40

    def test_the_ledger_counts_unpriced_calls_separately(self):
        ledger = CostLedger()
        ledger.add(CostRecord("compiler", "openrouter", "m1", Usage(100, 10), None))
        assert ledger.totals().usd == 0.0
        assert ledger.totals().unpriced_calls == 1
        assert "unpriced" in ledger.summary_table()

    def test_the_summary_table_names_every_agent_and_model(self):
        ledger = CostLedger()
        ledger.add(CostRecord("compiler", "venice", "claude-sonnet-5", Usage(100, 10), 0.25))
        table = ledger.summary_table()
        assert "compiler" in table
        assert "claude-sonnet-5" in table
        assert "0.25" in table

    def test_usage_adds(self):
        assert Usage(1, 2) + Usage(10, 20) == Usage(11, 22)
        assert Usage(1, 2).total_tokens == 3


# --------------------------------------------------------------------------------------------


class TestTrajectory:
    def _trajectory(self) -> Trajectory:
        trajectory = Trajectory()
        replies = [Reply("not json"), Reply(VALID_SAMPLE, 1000, 500)]
        client, _ = a_client(replies, trajectory=trajectory)
        client.complete(
            system="You compile eligibility criteria.",
            user="Adults over 18.",
            model_cls=Sample,
            agent="compiler",
        )
        return trajectory

    def test_markdown_shows_the_instructions_the_retries_and_the_cost(self):
        markdown = self._trajectory().to_markdown()
        assert "You compile eligibility criteria." in markdown
        assert "Adults over 18." in markdown
        assert "Retries" in markdown and "1" in markdown
        assert "$" in markdown
        assert "not json" in markdown

    def test_markdown_shows_what_failed_validation_in_order(self):
        markdown = self._trajectory().to_markdown()
        first = markdown.index("Attempt 1")
        failure = markdown.index("did not validate")
        second = markdown.index("Attempt 2")
        assert first < failure < second

    def test_a_response_full_of_backticks_cannot_break_the_fences(self):
        trajectory = Trajectory()
        poisoned = f"```json\n{VALID_SAMPLE}\n```"
        client, _ = a_client([Reply(poisoned)], trajectory=trajectory)
        client.complete(system="s", user="u", model_cls=Sample)
        markdown = trajectory.to_markdown()
        assert poisoned in markdown
        assert "````" in markdown

    def test_totals_are_reported(self):
        trajectory = self._trajectory()
        assert trajectory.total_usage().completion_tokens == 520
        assert trajectory.total_usd() == pytest.approx(1100 / 1e6 * 1.0 + 520 / 1e6 * 2.0)

    def test_markdown_is_written_as_utf8_regardless_of_platform(self, tmp_path):
        path = self._trajectory().write_markdown(tmp_path / "trajectory.md")
        assert "Attempt 1" in path.read_text(encoding="utf-8")

    def test_jsonl_round_trips(self, tmp_path):
        path = tmp_path / "trajectory.jsonl"
        original = self._trajectory()
        original.write_jsonl(path)

        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["agent"] == "compiler"

        reloaded = Trajectory.read_jsonl(path)
        assert reloaded.steps[0].system_prompt == "You compile eligibility criteria."
        assert reloaded.steps[0].retries == 1
        assert reloaded.to_markdown() == original.to_markdown()

    def test_every_step_is_json_serialisable(self):
        json.dumps(self._trajectory().to_dicts())


# --------------------------------------------------------------------------------------------


class TestProviderProfiles:
    def test_the_documented_models_all_ship(self):
        names = set(builtin_profiles())
        assert {
            "venice:claude-sonnet-5",
            "venice:zai-org-glm-5",
            "venice:deepseek-v4-flash",
            "venice:qwen3-235b-a22b-instruct-2507",
            "venice:mistral-small-3-2-24b-instruct",
            "openrouter:anthropic/claude-sonnet-5",
            "openrouter:google/gemini-3.1-pro-preview",
            "openrouter:deepseek/deepseek-v4-pro",
        } <= names

    def test_qwen_is_marked_as_having_no_structured_output(self):
        profile = builtin_profiles()["venice:qwen3-235b-a22b-instruct-2507"]
        assert profile.structured_output is StructuredOutput.NONE
        assert profile.supports_json_schema is False

    def test_venice_prices_match_the_published_rates(self):
        profile = builtin_profiles()["venice:claude-sonnet-5"]
        assert (profile.input_usd_per_mtok, profile.output_usd_per_mtok) == (2.0, 10.0)

    def test_the_environment_selects_a_profile(self, monkeypatch):
        monkeypatch.setenv("CALIPER_PROVIDER", "venice")
        monkeypatch.setenv("CALIPER_MODEL", "claude-sonnet-5")
        profile = profile_from_env()
        assert profile.model == "claude-sonnet-5"
        assert profile.base_url == "https://api.venice.ai/api/v1"
        assert profile.api_key_env == "VENICE_API_KEY"

    def test_the_default_is_the_primary_venice_model(self, monkeypatch):
        monkeypatch.delenv("CALIPER_PROVIDER", raising=False)
        monkeypatch.delenv("CALIPER_MODEL", raising=False)
        assert profile_from_env().model == "claude-sonnet-5"

    def test_an_unknown_model_names_the_ones_that_exist(self, monkeypatch):
        monkeypatch.setenv("CALIPER_MODEL", "gpt-9-ultra")
        with pytest.raises(UnknownProfileError, match="claude-sonnet-5"):
            profile_from_env()

    def test_a_profile_holds_the_name_of_the_key_and_not_the_key(self, monkeypatch):
        monkeypatch.setenv("VENICE_API_KEY", "sk-planted-secret")
        profile = builtin_profiles()["venice:claude-sonnet-5"]
        assert "VENICE_API_KEY" in repr(profile)
        assert "sk-planted-secret" not in repr(profile)

    def test_venice_capabilities_can_be_refreshed_from_the_models_endpoint(self):
        payload = {
            "data": [
                {
                    "id": "qwen3-235b-a22b-instruct-2507",
                    "model_spec": {"capabilities": {"supportsResponseSchema": True}},
                }
            ]
        }
        refreshed = builtin_profiles()["venice:qwen3-235b-a22b-instruct-2507"].with_capabilities(
            payload
        )
        assert refreshed.structured_output is StructuredOutput.JSON_SCHEMA


# --------------------------------------------------------------------------------------------


_LEAKED_BEARER = re.compile(r"Bearer\s+(?!REDACTED\b)\S+")


def bearer_leaks(directory: Path) -> list[str]:
    """Locations in `directory` where an Authorization value survived redaction.

    The secret itself is deliberately never included in the return value: a failure message ends
    up in CI logs.
    """
    leaks = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".yaml", ".yml", ".json"}:
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for number, line in enumerate(lines, 1):
            if _LEAKED_BEARER.search(line):
                leaks.append(f"{path}:{number}")
    return leaks


class TestCassetteHygiene:
    def test_the_committed_cassettes_carry_no_credentials(self):
        assert bearer_leaks(CASSETTE_DIR) == []

    def test_the_scanner_finds_a_planted_secret(self, tmp_path):
        (tmp_path / "leaky.yaml").write_text(
            "headers:\n  Authorization:\n  - Bearer sk-not-a-real-key\n", encoding="utf-8"
        )
        assert len(bearer_leaks(tmp_path)) == 1

    def test_the_scanner_accepts_a_redacted_cassette(self, tmp_path):
        (tmp_path / "clean.yaml").write_text(
            "headers:\n  Authorization:\n  - REDACTED\n  X-Other:\n  - Bearer REDACTED\n",
            encoding="utf-8",
        )
        assert bearer_leaks(tmp_path) == []

    def test_no_live_key_value_appears_in_the_cassettes(self):
        import os

        for name in ("VENICE_API_KEY", "OPENROUTER_API_KEY"):
            value = os.environ.get(name)
            if not value or len(value) < 8:
                continue
            for path in CASSETTE_DIR.rglob("*"):
                if path.is_file():
                    body = path.read_text(encoding="utf-8", errors="replace")
                    assert value not in body, f"{name} leaked into {path}"

    @pytest.mark.vcr
    def test_the_recorder_is_wired_up(self, vcr):
        """The cassette a marked test would use lands where we said, and replays by default.

        Reaching into the cassette's private attributes is deliberate: the alternative is
        trusting that the fixtures below are read, and discovering otherwise during grading.
        """
        assert vcr is not None, "pytest-recording did not install a cassette"
        assert Path(vcr._path).parent == CASSETTE_DIR
        assert vcr.record_mode == "none"
        assert [matcher.__name__ for matcher in vcr._match_on] == [
            "method",
            "scheme",
            "host",
            "port",
            "path",
            "body",
        ]

    def test_the_vcr_config_redacts_and_matches_on_the_body(self, vcr_config):
        filtered = {name for name, _ in vcr_config["filter_headers"]}
        assert "authorization" in filtered
        assert "x-api-key" in filtered
        assert vcr_config["match_on"] == ["method", "scheme", "host", "port", "path", "body"]
        assert vcr_config["decode_compressed_response"] is True


# --------------------------------------------------------------------------------------------
# The one test that would touch the network. It replays `tests/cassettes/venice_compile.yaml`,
# which is produced by running `pytest --record-mode=once` once, with VENICE_API_KEY set.
# --------------------------------------------------------------------------------------------


LIVE_CASSETTE = CASSETTE_DIR / "test_compiles_a_criteria_set_from_venice.yaml"


@pytest.mark.vcr
@pytest.mark.skipif(not LIVE_CASSETTE.exists(), reason="cassette has not been recorded yet")
def test_compiles_a_criteria_set_from_venice(monkeypatch):
    monkeypatch.setenv("VENICE_API_KEY", "recorded-run-placeholder")
    monkeypatch.setenv("CALIPER_PROVIDER", "venice")
    monkeypatch.setenv("CALIPER_MODEL", "claude-sonnet-5")

    trajectory = Trajectory()
    client = LLMClient(profile_from_env(), trajectory=trajectory, temperature=0.0)
    result = client.complete(
        system="Compile clinical trial eligibility criteria into the given JSON schema.",
        user='NCT00000000\n\nInclusion: Age 18 years or older.',
        model_cls=WIRE,
        agent="compiler",
    )

    assert isinstance(to_criteria_set(result.value, source_text="x"), CriteriaSet)
    assert result.value.criteria
    assert trajectory.steps[0].usage.total_tokens > 0


def test_the_gate_is_pydantic_not_the_provider():
    """Whatever tier answered, the value handed back has been through the model's validators."""
    client, _ = a_client([Reply('{"name": "aspirin", "count": 2, "note": null}')])
    result = client.complete(system="s", user="u", model_cls=Sample)
    with pytest.raises(ValidationError):
        Sample.model_validate({"name": "", "count": 2})
    assert result.value == Sample(name="aspirin", count=2)


class TestSharedInstructions:
    """An agent's instructions are the same on every call, and repeating them buries the run.

    The compiler makes one call per criterion; printed in full each time, its standing instructions
    accounted for nine tenths of a 12,000-line trajectory, and the thing a reader came for — what
    was asked, what came back, what was retried — was scattered through it.
    """

    def a_step(self, system: str, user: str) -> TraceStep:
        client, _ = a_client([Reply(VALID_SAMPLE)])
        done = client.complete(system=system, user=user, model_cls=Sample, agent="compiler")
        return done.step

    def two_steps(self, system: str = "standing orders") -> Trajectory:
        return Trajectory([self.a_step(system, "one"), self.a_step(system, "two")])

    def test_shared_instructions_are_printed_once(self):
        text = self.two_steps().to_markdown(repeat_instructions=False)
        assert text.count("standing orders") == 1

    def test_the_reader_is_told_where_they_went(self):
        text = self.two_steps().to_markdown(repeat_instructions=False)
        assert "Standing instructions" in text

    def test_every_request_is_still_there(self):
        text = self.two_steps().to_markdown(repeat_instructions=False)
        assert "one" in text and "two" in text

    def test_differing_instructions_are_still_printed_per_step(self):
        """Two agents in one trajectory have nothing to share, so nothing is hoisted."""
        traj = Trajectory([self.a_step("orders A", "one"), self.a_step("orders B", "two")])
        text = traj.to_markdown(repeat_instructions=False)
        assert "orders A" in text and "orders B" in text

    def test_the_default_still_repeats_them(self):
        assert self.two_steps().to_markdown().count("standing orders") == 2


class TestUnionBudget:
    """Strict schema modes cap how many union-typed parameters they will compile.

    Venice rejects a schema with more than sixteen, and Caliper's depth-2 criteria schema has
    thirty-seven, because strict mode expresses every optional field as a null union. The ladder
    already handles the rejection; a profile that declares the limit means the request is never
    sent, and the trajectory says why rather than showing a 400 the reader has to interpret.
    """

    def test_a_schema_within_budget_still_starts_at_the_top(self):
        profile = a_profile(max_union_parameters=100)
        client, transport = a_client([Reply(VALID_SAMPLE)], profile=profile)
        step = client.complete(system="s", user="u", model_cls=Sample, agent="a").step
        assert step.attempts[0].tier == "json_schema"
        assert "response_format" in transport.requests[0]

    def test_a_schema_over_budget_skips_the_strict_rung(self):
        profile = a_profile(max_union_parameters=0)
        client, transport = a_client([Reply(VALID_SAMPLE)], profile=profile)
        step = client.complete(system="s", user="u", model_cls=Sample, agent="a").step
        assert step.attempts[0].tier == "json_object"
        assert len(transport.requests) == 1

    def test_the_trajectory_says_why_the_rung_was_skipped(self):
        profile = a_profile(max_union_parameters=0)
        client, _ = a_client([Reply(VALID_SAMPLE)], profile=profile)
        step = client.complete(system="s", user="u", model_cls=Sample, agent="a").step
        assert step.skipped_tiers
        reason = step.skipped_tiers[0][1]
        assert "union" in reason and "0" in reason

    def test_no_declared_budget_means_no_limit(self):
        client, transport = a_client([Reply(VALID_SAMPLE)], profile=a_profile())
        client.complete(system="s", user="u", model_cls=Sample, agent="a")
        assert "response_format" in transport.requests[0]

    def test_counting_matches_the_schema_the_provider_would_have_seen(self):
        from caliper.llm.schema import count_union_parameters, to_strict_schema

        assert count_union_parameters(to_strict_schema(Sample)) >= 1
