"""The concept resolver and the store that remembers what it resolved.

Everything here runs offline against a fake transport, so the assertions about *not* calling the
model are as strong as the assertions about calling it: a test that reaches the network would
fail rather than quietly cost money.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from caliper.agents import AgentContext
from caliper.agents.resolver import (
    DEFAULT_MEMORY_PATH,
    SYSTEM_PROMPT,
    ConceptCodes,
    ConceptMemory,
    MemoryStats,
    ResolvedConcept,
    normalise_concept_text,
    resolve_concepts,
)
from caliper.ir import Code, Concept
from caliper.llm import (
    LLMClient,
    ProviderProfile,
    StructuredOutput,
    strict_schema_problems,
    to_strict_schema,
)

CREATININE = Code(system="LOINC", code="2160-0", display="Creatinine [Mass/volume] in Serum")
METFORMIN = Code(system="RxNorm", code="6809", display="metformin")


# --------------------------------------------------------------------------------------------
# A transport that speaks the slice of the OpenAI surface the client uses, and records requests.
# --------------------------------------------------------------------------------------------


class Reply:
    """One canned assistant turn."""

    def __init__(self, content: str, prompt_tokens: int = 80, completion_tokens: int = 40):
        self.content = content
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class FakeTransport:
    """Stand-in for `openai.OpenAI`. Replies are consumed in order; exceptions are raised."""

    def __init__(self, replies: list[Reply | Exception]):
        self.replies = list(replies)
        self.requests: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        if not self.replies:
            raise AssertionError("the resolver asked for more turns than the test provided")
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


def a_profile() -> ProviderProfile:
    return ProviderProfile(
        provider="venice",
        model="test-model",
        base_url="https://example.invalid/v1",
        api_key_env="TEST_API_KEY",
        structured_output=StructuredOutput.JSON_SCHEMA,
        input_usd_per_mtok=1.0,
        output_usd_per_mtok=2.0,
    )


def candidate(
    system: str = "LOINC",
    code: str = "2160-0",
    display: str = "Creatinine [Mass/volume] in Serum",
    confidence: str = "high",
) -> dict:
    return {"system": system, "code": code, "display": display, "confidence": confidence}


def a_reply(*candidates: dict, rationale: str = "Laboratory analyte.") -> Reply:
    return Reply(json.dumps({"rationale": rationale, "candidates": list(candidates)}))


def a_context(
    replies: list[Reply | Exception], memory: ConceptMemory
) -> tuple[AgentContext, FakeTransport]:
    transport = FakeTransport(replies)
    client = LLMClient(a_profile(), transport=transport)
    return AgentContext(client=client, memory=memory), transport


def a_memory(tmp_path: Path) -> ConceptMemory:
    return ConceptMemory(tmp_path / "concepts.json")


def summary_of(ctx: AgentContext) -> dict:
    step = ctx.trajectory.steps[-1]
    assert step.agent == "resolver"
    assert isinstance(step.parsed, dict)
    return step.parsed


# --------------------------------------------------------------------------------------------


class TestNormalisation:
    @pytest.mark.parametrize(
        "text",
        [
            "Serum Creatinine",
            "serum creatinine",
            "  Serum   creatinine  ",
            "Serum creatinine.",
            "SERUM CREATININE;",
        ],
    )
    def test_case_whitespace_and_trailing_punctuation_collapse(self, text: str):
        assert normalise_concept_text(text) == "serum creatinine"

    def test_meaningful_punctuation_inside_the_text_survives(self):
        text = "Estimated glomerular filtration rate (eGFR)"
        assert normalise_concept_text(text) == "estimated glomerular filtration rate (egfr)"


class TestConceptMemoryDurability:
    def test_a_missing_file_loads_as_an_empty_store(self, tmp_path: Path):
        memory = ConceptMemory(tmp_path / "nowhere" / "concepts.json")
        assert memory.stats().entries == 0
        assert memory.get("serum creatinine") is None

    def test_a_corrupt_file_loads_as_an_empty_store_rather_than_raising(self, tmp_path: Path):
        path = tmp_path / "concepts.json"
        path.write_text("{ this is not json", encoding="utf-8")

        memory = ConceptMemory(path)

        assert memory.stats().entries == 0

    def test_an_entry_that_does_not_validate_is_skipped_and_the_rest_survive(self, tmp_path: Path):
        path = tmp_path / "concepts.json"
        path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "entries": {
                        "serum creatinine": {
                            "text": "serum creatinine",
                            "codes": [CREATININE.model_dump()],
                            "model": "venice:test-model",
                            "resolved_at": "2026-01-01T00:00:00Z",
                            "first_seen_nct": "NCT00000001",
                            "reuse_count": 0,
                        },
                        "broken": {"text": "broken", "codes": [{"system": "MADE-UP"}]},
                    },
                }
            ),
            encoding="utf-8",
        )

        memory = ConceptMemory(path)

        assert memory.stats().entries == 1
        assert memory.get("Serum creatinine") is not None

    def test_the_store_round_trips_through_save_and_load(self, tmp_path: Path):
        path = tmp_path / "concepts.json"
        memory = ConceptMemory(path)
        memory.put(
            "Serum Creatinine", (CREATININE,), model="venice:test-model", nct_id="NCT00000001"
        )
        memory.put("metformin", (METFORMIN,), model="venice:test-model", nct_id="NCT00000002")
        memory.record_hit("serum creatinine")
        memory.save()

        reloaded = ConceptMemory(path)

        assert reloaded.stats().entries == 2
        entry = reloaded.get("SERUM  CREATININE")
        assert entry is not None
        assert entry.codes == (CREATININE,)
        assert entry.model == "venice:test-model"
        assert entry.first_seen_nct == "NCT00000001"
        assert entry.reuse_count == 1

    def test_saving_creates_the_parent_directory(self, tmp_path: Path):
        path = tmp_path / "deep" / "nested" / "concepts.json"
        memory = ConceptMemory(path)
        memory.put("metformin", (METFORMIN,), model="venice:test-model", nct_id="NCT1")

        memory.save()

        assert path.is_file()

    def test_a_failed_serialisation_leaves_no_partial_file(self, tmp_path: Path, monkeypatch):
        path = tmp_path / "concepts.json"
        memory = ConceptMemory(path)
        memory.put("metformin", (METFORMIN,), model="venice:test-model", nct_id="NCT1")
        memory.save()
        good = path.read_text(encoding="utf-8")

        # A payload that serialises for a while and then cannot: json.dump streams, so real bytes
        # reach the temporary file before it raises.
        monkeypatch.setattr(
            ConceptMemory,
            "_payload",
            lambda self: {"entries": {"a": "written", "b": object()}},
        )
        with pytest.raises(TypeError):
            memory.save()

        assert path.read_text(encoding="utf-8") == good
        assert [p.name for p in tmp_path.iterdir()] == ["concepts.json"]


class TestConceptMemoryConsistency:
    def test_a_second_put_with_different_codes_keeps_the_first_and_counts_a_violation(
        self, tmp_path: Path
    ):
        memory = a_memory(tmp_path)
        memory.put("serum creatinine", (CREATININE,), model="m", nct_id="NCT1")

        memory.put(
            "Serum creatinine",
            (Code(system="LOINC", code="38483-4"),),
            model="m",
            nct_id="NCT2",
        )

        entry = memory.get("serum creatinine")
        assert entry is not None
        assert entry.codes == (CREATININE,)
        assert entry.first_seen_nct == "NCT1"
        assert memory.stats().consistency_violations == 1

    def test_a_second_put_with_the_same_codes_is_not_a_violation(self, tmp_path: Path):
        memory = a_memory(tmp_path)
        memory.put("serum creatinine", (CREATININE,), model="m", nct_id="NCT1")

        memory.put("serum creatinine", (CREATININE,), model="m", nct_id="NCT2")

        assert memory.stats().consistency_violations == 0

    def test_violations_survive_a_save_and_load(self, tmp_path: Path):
        path = tmp_path / "concepts.json"
        memory = ConceptMemory(path)
        memory.put("x", (CREATININE,), model="m", nct_id="NCT1")
        memory.put("x", (METFORMIN,), model="m", nct_id="NCT2")
        memory.save()

        assert ConceptMemory(path).stats().consistency_violations == 1


class TestMemoryStats:
    def test_hit_rate_is_reported_across_a_mixed_run(self, tmp_path: Path):
        memory = a_memory(tmp_path)
        memory.put("serum creatinine", (CREATININE,), model="m", nct_id="NCT1")

        assert memory.get("serum creatinine") is not None  # hit
        assert memory.get("Serum  Creatinine") is not None  # hit
        assert memory.get("haemoglobin a1c") is None  # miss
        assert memory.get("sglt2 inhibitor") is None  # miss

        stats = memory.stats()
        assert (stats.entries, stats.hits, stats.misses) == (1, 2, 2)
        assert stats.hit_rate == 0.5

    def test_hit_rate_of_a_store_nobody_asked_is_zero_rather_than_undefined(self, tmp_path: Path):
        assert a_memory(tmp_path).stats().hit_rate == 0.0

    def test_stats_are_serialisable_for_a_run_report(self, tmp_path: Path):
        stats = a_memory(tmp_path).stats()
        assert isinstance(stats, MemoryStats)
        assert json.loads(json.dumps(stats.to_dict()))["hit_rate"] == 0.0


class TestResolveFromMemory:
    def test_a_memory_hit_does_not_call_the_model(self, tmp_path: Path):
        memory = a_memory(tmp_path)
        memory.put("serum creatinine", (CREATININE,), model="m", nct_id="NCT1")
        ctx, transport = a_context([], memory)

        resolved = resolve_concepts([Concept(text="Serum Creatinine")], ctx, nct_id="NCT2")

        assert transport.requests == []
        assert resolved == {"Serum Creatinine": (CREATININE,)}

    def test_every_hit_is_recorded_against_the_entry(self, tmp_path: Path):
        memory = a_memory(tmp_path)
        memory.put("serum creatinine", (CREATININE,), model="m", nct_id="NCT1")
        ctx, _ = a_context([], memory)

        resolve_concepts([Concept(text="serum creatinine")], ctx, nct_id="NCT2")
        resolve_concepts([Concept(text="Serum creatinine")], ctx, nct_id="NCT3")

        entry = memory.get("serum creatinine")
        assert entry is not None
        assert entry.reuse_count == 2


class TestResolveFromTheModel:
    def test_a_miss_calls_the_model_once_and_stores_the_result(self, tmp_path: Path):
        memory = a_memory(tmp_path)
        ctx, transport = a_context([a_reply(candidate())], memory)

        resolved = resolve_concepts([Concept(text="Serum creatinine")], ctx, nct_id="NCT1")

        assert len(transport.requests) == 1
        assert resolved["Serum creatinine"] == (CREATININE,)
        entry = memory.get("serum creatinine")
        assert entry is not None
        assert entry.codes == (CREATININE,)
        assert entry.first_seen_nct == "NCT1"
        assert entry.model == "venice:test-model"

    def test_the_store_is_written_to_disk_so_an_interrupted_run_keeps_what_it_paid_for(
        self, tmp_path: Path
    ):
        path = tmp_path / "concepts.json"
        memory = ConceptMemory(path)
        ctx, _ = a_context([a_reply(candidate())], memory)

        resolve_concepts([Concept(text="serum creatinine")], ctx, nct_id="NCT1")

        assert ConceptMemory(path).get("serum creatinine") is not None

    def test_two_concepts_differing_only_in_case_and_spacing_are_one_lookup(self, tmp_path: Path):
        memory = a_memory(tmp_path)
        ctx, transport = a_context([a_reply(candidate())], memory)

        concepts = [
            Concept(text="Serum creatinine"),
            Concept(text="serum  CREATININE"),
            Concept(text="Serum creatinine."),
        ]
        resolved = resolve_concepts(concepts, ctx, nct_id="NCT1")

        assert len(transport.requests) == 1
        assert all(resolved[c.text] == (CREATININE,) for c in concepts)

    def test_the_concept_text_reaches_the_model_and_the_prompt_file_is_the_instruction(
        self, tmp_path: Path
    ):
        ctx, transport = a_context([a_reply(candidate())], a_memory(tmp_path))

        resolve_concepts([Concept(text="Serum creatinine")], ctx, nct_id="NCT1")

        messages = transport.requests[0]["messages"]
        assert messages[0]["content"] == SYSTEM_PROMPT
        assert "Serum creatinine" in messages[1]["content"]

    def test_a_model_failure_yields_no_codes_and_is_not_cached_as_a_negative_result(
        self, tmp_path: Path
    ):
        memory = a_memory(tmp_path)
        ctx, _ = a_context([RuntimeError("the provider is down")], memory)

        resolved = resolve_concepts([Concept(text="serum creatinine")], ctx, nct_id="NCT1")

        assert resolved == {"serum creatinine": ()}
        assert memory.get("serum creatinine") is None
        assert summary_of(ctx)["model_failures"] == ["serum creatinine"]

    def test_a_concept_the_model_cannot_code_is_cached_so_it_is_not_asked_twice(
        self, tmp_path: Path
    ):
        memory = a_memory(tmp_path)
        ctx, transport = a_context([a_reply(rationale="A drug class, not a drug.")], memory)

        first = resolve_concepts([Concept(text="SGLT2 inhibitor")], ctx, nct_id="NCT1")
        second = resolve_concepts([Concept(text="SGLT2 inhibitor")], ctx, nct_id="NCT2")

        assert first == {"SGLT2 inhibitor": ()}
        assert second == {"SGLT2 inhibitor": ()}
        assert len(transport.requests) == 1


class TestConfidenceGate:
    def test_a_low_confidence_candidate_is_discarded_and_the_concept_comes_back_bare(
        self, tmp_path: Path
    ):
        ctx, _ = a_context(
            [a_reply(candidate(confidence="low"))],
            a_memory(tmp_path),
        )

        resolved = resolve_concepts([Concept(text="serum creatinine")], ctx, nct_id="NCT1")

        assert resolved == {"serum creatinine": ()}
        assert summary_of(ctx)["low_confidence_dropped"] == 1

    def test_a_medium_confidence_candidate_is_discarded_too(self, tmp_path: Path):
        ctx, _ = a_context([a_reply(candidate(confidence="medium"))], a_memory(tmp_path))

        resolved = resolve_concepts([Concept(text="serum creatinine")], ctx, nct_id="NCT1")

        assert resolved == {"serum creatinine": ()}

    def test_high_confidence_candidates_survive_alongside_discarded_ones(self, tmp_path: Path):
        ctx, _ = a_context(
            [
                a_reply(
                    candidate(),
                    candidate(system="LOINC", code="38483-4", confidence="medium"),
                )
            ],
            a_memory(tmp_path),
        )

        resolved = resolve_concepts([Concept(text="serum creatinine")], ctx, nct_id="NCT1")

        assert resolved["serum creatinine"] == (CREATININE,)


class TestCodeShapeValidation:
    def test_a_loinc_code_of_the_wrong_shape_is_dropped_and_counted(self, tmp_path: Path):
        ctx, _ = a_context([a_reply(candidate(code="2160"))], a_memory(tmp_path))

        resolved = resolve_concepts([Concept(text="serum creatinine")], ctx, nct_id="NCT1")

        assert resolved == {"serum creatinine": ()}
        assert summary_of(ctx)["malformed_codes_dropped"] == 1

    @pytest.mark.parametrize(
        ("system", "code"),
        [
            ("LOINC", "2160-0"),
            ("LOINC", "4548-4"),
            ("RxNorm", "6809"),
            ("SNOMED", "44054006"),
            ("ICD10", "E11.9"),
            ("ICD10", "N18"),
            ("UCUM", "mg/dL"),
        ],
    )
    def test_well_formed_codes_survive(self, tmp_path: Path, system: str, code: str):
        offered = candidate(system=system, code=code, display="a display name")
        ctx, _ = a_context([a_reply(offered)], a_memory(tmp_path))

        resolved = resolve_concepts([Concept(text="a concept")], ctx, nct_id="NCT1")

        assert resolved["a concept"] == (Code(system=system, code=code, display="a display name"),)

    @pytest.mark.parametrize(
        ("system", "code"),
        [
            ("LOINC", "2160"),
            ("LOINC", "abc-1"),
            ("LOINC", "1234567-8"),
            ("RxNorm", "RX6809"),
            ("SNOMED", "12345"),
            ("SNOMED", "44054006x"),
            ("ICD10", "1234"),
            ("UCUM", "mg per dL"),
        ],
    )
    def test_malformed_codes_are_dropped(self, tmp_path: Path, system: str, code: str):
        ctx, _ = a_context([a_reply(candidate(system=system, code=code))], a_memory(tmp_path))

        resolved = resolve_concepts([Concept(text="a concept")], ctx, nct_id="NCT1")

        assert resolved["a concept"] == ()
        assert summary_of(ctx)["malformed_codes_dropped"] == 1

    def test_the_same_code_offered_twice_is_kept_once(self, tmp_path: Path):
        ctx, _ = a_context([a_reply(candidate(), candidate())], a_memory(tmp_path))

        resolved = resolve_concepts([Concept(text="serum creatinine")], ctx, nct_id="NCT1")

        assert resolved["serum creatinine"] == (CREATININE,)


class TestTrajectorySummary:
    def test_the_summary_separates_memory_hits_from_calls(self, tmp_path: Path):
        memory = a_memory(tmp_path)
        memory.put("serum creatinine", (CREATININE,), model="m", nct_id="NCT0")
        ctx, _ = a_context([a_reply(candidate(system="RxNorm", code="6809"))], memory)

        resolve_concepts(
            [Concept(text="Serum creatinine"), Concept(text="Metformin")], ctx, nct_id="NCT1"
        )

        summary = summary_of(ctx)
        assert summary["nct_id"] == "NCT1"
        assert summary["memory_hits"] == ["serum creatinine"]
        assert summary["model_calls"] == ["metformin"]
        assert summary["memory"]["hit_rate"] == 0.5

    def test_the_summary_step_reads_as_a_completed_step_not_a_failed_call(self, tmp_path: Path):
        ctx, _ = a_context([], a_memory(tmp_path))

        resolve_concepts([], ctx, nct_id="NCT1")

        step = ctx.trajectory.steps[-1]
        assert step.succeeded
        assert step.usage.total_tokens == 0
        assert "NCT1" in ctx.trajectory.to_markdown()


class TestResolverContract:
    def test_the_response_model_survives_the_strict_schema_transform(self):
        schema = to_strict_schema(ConceptCodes)
        assert strict_schema_problems(schema) == []
        assert "$ref" not in json.dumps(schema)

    def test_the_default_store_lives_under_a_dot_caliper_directory(self):
        assert Path(".caliper") / "concepts.json" == DEFAULT_MEMORY_PATH

    def test_a_resolved_concept_carries_its_provenance(self, tmp_path: Path):
        memory = a_memory(tmp_path)
        memory.put("metformin", (METFORMIN,), model="venice:test-model", nct_id="NCT1")

        entry = memory.get("metformin")
        assert isinstance(entry, ResolvedConcept)
        assert entry.model == "venice:test-model"
        assert entry.first_seen_nct == "NCT1"
        assert entry.resolved_at.endswith("Z")

    def test_a_foreign_memory_object_is_refused_rather_than_ignored(self, tmp_path: Path):
        ctx, _ = a_context([], a_memory(tmp_path))
        ctx.memory = {"serum creatinine": []}

        with pytest.raises(TypeError, match="ConceptMemory"):
            resolve_concepts([Concept(text="serum creatinine")], ctx, nct_id="NCT1")


class TestPrompt:
    def test_the_prompt_is_loaded_from_package_data(self):
        assert SYSTEM_PROMPT.strip()
        assert len(SYSTEM_PROMPT) > 500

    def test_the_prompt_states_the_asymmetry_the_gate_depends_on(self):
        lowered = SYSTEM_PROMPT.lower()
        assert "high" in lowered
        assert "no codes" in lowered or "no code" in lowered

    def test_the_prompt_carries_no_emoji_and_no_assistant_persona(self):
        assert "helpful assistant" not in SYSTEM_PROMPT.lower()
        assert all(ord(character) < 0x2190 for character in SYSTEM_PROMPT)
