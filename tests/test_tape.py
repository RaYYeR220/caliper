"""The response tape.

What a reviewer needs from a recording is not proof that packets moved. It is the ability to read
what the model was asked and what it said, and to rerun the whole thing from that. So the recording
is kept at the level of the exchange rather than the socket: readable JSON, one line per call.

The tests below are mostly about the ways a tape can lie. A key that ignores part of the request
would replay one agent's answer to another's question; a miss that falls through to the network
would make an offline claim false; a tape written with a key in it would be a leak.
"""

import json

import pytest

from caliper.tape import Tape, TapeMiss, TapeTransport, exchange_key

from fakes import Reply, a_client, a_profile


def request(system: str = "sys", user: str = "usr", model: str = "test-model") -> dict:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.0,
    }


class TestTheKey:
    def test_the_same_request_keys_the_same(self):
        assert exchange_key(request()) == exchange_key(request())

    def test_a_different_user_message_keys_differently(self):
        assert exchange_key(request(user="a")) != exchange_key(request(user="b"))

    def test_a_different_system_prompt_keys_differently(self):
        """Two agents can be asked about the same protocol text; only the system prompt differs."""
        assert exchange_key(request(system="compiler")) != exchange_key(request(system="critic"))

    def test_a_different_model_keys_differently(self):
        assert exchange_key(request(model="a")) != exchange_key(request(model="b"))

    def test_the_response_format_is_part_of_the_key(self):
        with_schema = {**request(), "response_format": {"json_schema": {"name": "Thing"}}}
        assert exchange_key(with_schema) != exchange_key(request())

    def test_temperature_is_not_part_of_the_key(self):
        """It is a knob on how the answer was produced, not on what was asked."""
        assert exchange_key({**request(), "temperature": 0.7}) == exchange_key(request())


class TestRecordingAndReplay:
    def test_a_recorded_exchange_replays(self, tmp_path):
        tape = Tape(tmp_path / "t.jsonl", mode="record")
        tape.record(request(), response="hello", agent="compiler", usage={"prompt_tokens": 1})
        tape.save()

        replayed = Tape(tmp_path / "t.jsonl", mode="replay")
        assert replayed.lookup(request()).response == "hello"

    def test_a_miss_in_replay_raises_rather_than_returning_nothing(self, tmp_path):
        tape = Tape(tmp_path / "t.jsonl", mode="replay")
        with pytest.raises(TapeMiss):
            tape.require(request())

    def test_the_miss_says_what_was_asked_so_it_can_be_diagnosed(self, tmp_path):
        tape = Tape(tmp_path / "t.jsonl", mode="replay")
        with pytest.raises(TapeMiss) as caught:
            tape.require(request(user="a criterion about creatinine"))
        assert "creatinine" in str(caught.value)

    def test_the_tape_counts_what_it_served_and_what_it_missed(self, tmp_path):
        tape = Tape(tmp_path / "t.jsonl", mode="record")
        tape.record(request(), response="hello", agent="compiler")
        tape.save()

        replayed = Tape(tmp_path / "t.jsonl", mode="replay")
        replayed.lookup(request())
        replayed.lookup(request(user="never recorded"))
        assert (replayed.hits, replayed.misses) == (1, 1)

    def test_a_repeated_question_replays_the_same_answer(self, tmp_path):
        tape = Tape(tmp_path / "t.jsonl", mode="record")
        tape.record(request(), response="hello", agent="compiler")
        tape.save()
        replayed = Tape(tmp_path / "t.jsonl", mode="replay")
        assert replayed.lookup(request()).response == replayed.lookup(request()).response

    def test_a_missing_file_replays_as_an_empty_tape_rather_than_raising(self, tmp_path):
        assert Tape(tmp_path / "absent.jsonl", mode="replay").lookup(request()) is None


class TestTheFileItself:
    def test_it_is_one_readable_json_object_per_line(self, tmp_path):
        tape = Tape(tmp_path / "t.jsonl", mode="record")
        tape.record(request(), response="hello", agent="compiler")
        tape.save()
        lines = (tmp_path / "t.jsonl").read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["response"] == "hello"

    def test_it_carries_the_prompts_so_a_reader_can_check_what_was_asked(self, tmp_path):
        tape = Tape(tmp_path / "t.jsonl", mode="record")
        tape.record(request(system="the compiler prompt"), response="x", agent="compiler")
        tape.save()
        entry = json.loads((tmp_path / "t.jsonl").read_text(encoding="utf-8"))
        assert entry["system"] == "the compiler prompt"
        assert entry["agent"] == "compiler"

    def test_entries_are_written_in_key_order_so_two_runs_diff_cleanly(self, tmp_path):
        tape = Tape(tmp_path / "t.jsonl", mode="record")
        for user in ("c", "a", "b"):
            tape.record(request(user=user), response=user, agent="compiler")
        tape.save()
        keys = [
            json.loads(line)["key"]
            for line in (tmp_path / "t.jsonl").read_text(encoding="utf-8").strip().splitlines()
        ]
        assert keys == sorted(keys)

    def test_nothing_resembling_a_credential_is_written(self, tmp_path):
        """The tape records the conversation, never the transport that carried it."""
        tape = Tape(tmp_path / "t.jsonl", mode="record")
        tape.record(
            {**request(), "extra_headers": {"Authorization": "Bearer sk-secret"}},
            response="x",
            agent="compiler",
        )
        tape.save()
        assert "sk-secret" not in (tmp_path / "t.jsonl").read_text(encoding="utf-8")


class TestTheTransport:
    def test_replaying_never_reaches_the_upstream(self, tmp_path):
        tape = Tape(tmp_path / "t.jsonl", mode="record")
        tape.record(request(), response='{"ok": true}', agent="compiler")
        tape.save()

        exploding = _Exploding()
        transport = TapeTransport(
            Tape(tmp_path / "t.jsonl", mode="replay"), upstream=exploding, agent="compiler"
        )
        reply = transport.chat.completions.create(**request())
        assert reply.choices[0].message.content == '{"ok": true}'
        assert exploding.calls == 0

    def test_recording_passes_through_and_stores_what_came_back(self, tmp_path):
        client, upstream = a_client([Reply('{"ok": true}')])
        tape = Tape(tmp_path / "t.jsonl", mode="record")
        transport = TapeTransport(tape, upstream=upstream, agent="compiler")
        transport.chat.completions.create(**request())
        tape.save()
        assert len(upstream.requests) == 1
        assert Tape(tmp_path / "t.jsonl", mode="replay").lookup(request()) is not None

    def test_a_replay_miss_is_an_error_rather_than_a_silent_call(self, tmp_path):
        transport = TapeTransport(
            Tape(tmp_path / "t.jsonl", mode="replay"), upstream=_Exploding(), agent="compiler"
        )
        with pytest.raises(TapeMiss):
            transport.chat.completions.create(**request())

    def test_a_run_recorded_through_a_client_replays_through_the_same_client(self, tmp_path):
        """The round trip that matters: record a real run, then reproduce it with no provider.

        The tape keys on the request the client actually sends, tier decorations and all, so a
        recording made at one rung of the ladder replays at that rung and not another.
        """
        from pydantic import BaseModel

        from caliper.llm import LLMClient

        class Thing(BaseModel):
            ok: bool

        _, upstream = a_client([Reply('{"ok": true}')])
        recording = Tape(tmp_path / "t.jsonl", mode="record")
        recorder = LLMClient(
            a_profile(),
            transport=TapeTransport(recording, upstream=upstream, agent="compiler"),
            env={"TEST_API_KEY": "not-a-real-key"},
        )
        assert recorder.complete(system="sys", user="usr", model_cls=Thing).value.ok is True
        recording.save()

        replaying = LLMClient(
            a_profile(),
            transport=TapeTransport(
                Tape(tmp_path / "t.jsonl", mode="replay"), upstream=_Exploding(), agent="compiler"
            ),
            env={"TEST_API_KEY": "not-a-real-key"},
        )
        assert replaying.complete(system="sys", user="usr", model_cls=Thing).value.ok is True


class _Exploding:
    def __init__(self):
        self.calls = 0
        self.chat = _Chat(self)


class _Chat:
    def __init__(self, owner):
        self.completions = _Completions(owner)


class _Completions:
    def __init__(self, owner):
        self.owner = owner

    def create(self, **kwargs):
        self.owner.calls += 1
        raise AssertionError("the upstream must not be reached while replaying")


class TestAgentAttribution:
    """A tape is read by a person, and "which agent asked this" is the first thing they want."""

    def test_the_agent_is_read_from_the_prompt_heading(self, tmp_path):
        from caliper.tape import agent_from_system

        assert agent_from_system("# Criteria compiler\n\nYou formalise...") == "compiler"
        assert agent_from_system("# Back-translation check\n\n...") == "critic"
        assert agent_from_system("# Concept resolution\n\n...") == "resolver"
        assert agent_from_system("# Assertion detection in a clinical note\n") == "extractor"
        assert agent_from_system("# Rationale writing\n") == "writer"
        assert agent_from_system("# Trial pre-screening\n") == "baseline"

    def test_an_unrecognised_prompt_falls_back_to_the_transport_default(self, tmp_path):
        client, upstream = a_client([Reply("x")])
        tape = Tape(tmp_path / "t.jsonl", mode="record")
        transport = TapeTransport(tape, upstream=upstream, agent="fallback")
        transport.chat.completions.create(**request(system="something else"))
        tape.save()
        assert tape.agents == {"fallback": 1}

    def test_a_recorded_run_can_be_summarised_by_agent(self, tmp_path):
        tape = Tape(tmp_path / "t.jsonl", mode="record")
        tape.record(request(user="a"), response="x", agent="compiler")
        tape.record(request(user="b"), response="x", agent="compiler")
        tape.record(request(user="c"), response="x", agent="critic")
        assert tape.agents == {"compiler": 2, "critic": 1}


class TestRecordingIsResumable:
    """A recording run is long. Losing it to a crash halfway would be its own kind of bug."""

    def test_recording_reuses_an_answer_it_already_has(self, tmp_path):
        first, upstream = a_client([Reply("first")])
        tape = Tape(tmp_path / "t.jsonl", mode="record")
        transport = TapeTransport(tape, upstream=upstream, agent="compiler")
        transport.chat.completions.create(**request())
        transport.chat.completions.create(**request())
        assert len(upstream.requests) == 1
        assert first is not None

    def test_a_new_question_is_still_asked(self, tmp_path):
        _, upstream = a_client([Reply("a"), Reply("b")])
        tape = Tape(tmp_path / "t.jsonl", mode="record")
        transport = TapeTransport(tape, upstream=upstream, agent="compiler")
        transport.chat.completions.create(**request(user="a"))
        transport.chat.completions.create(**request(user="b"))
        assert len(upstream.requests) == 2

    def test_a_resumed_run_asks_only_what_is_missing(self, tmp_path):
        seed = Tape(tmp_path / "t.jsonl", mode="record")
        seed.record(request(user="a"), response="a", agent="compiler")
        seed.save()

        _, upstream = a_client([Reply("b")])
        resumed = Tape(tmp_path / "t.jsonl", mode="record")
        transport = TapeTransport(resumed, upstream=upstream, agent="compiler")
        transport.chat.completions.create(**request(user="a"))
        transport.chat.completions.create(**request(user="b"))
        assert len(upstream.requests) == 1
        assert len(resumed) == 2

    def test_refresh_asks_again_even_when_the_answer_is_known(self, tmp_path):
        seed = Tape(tmp_path / "t.jsonl", mode="record")
        seed.record(request(), response="stale", agent="compiler")
        seed.save()

        _, upstream = a_client([Reply("fresh")])
        refreshing = Tape(tmp_path / "t.jsonl", mode="refresh")
        transport = TapeTransport(refreshing, upstream=upstream, agent="compiler")
        reply = transport.chat.completions.create(**request())
        assert len(upstream.requests) == 1
        assert reply.choices[0].message.content == "fresh"


class TestPruning:
    """A tape accumulates. Committing exchanges nothing replays makes the artefact confusing."""

    def test_it_keeps_only_the_keys_that_were_used(self, tmp_path):
        from caliper.tape import prune

        tape = Tape(tmp_path / "t.jsonl", mode="record")
        tape.record(request(user="wanted"), response="a", agent="compiler")
        tape.record(request(user="stale"), response="b", agent="compiler")
        tape.save()

        kept = prune(tmp_path / "t.jsonl", {exchange_key(request(user="wanted"))})
        assert kept == 1
        assert len(Tape(tmp_path / "t.jsonl", mode="replay")) == 1

    def test_it_refuses_to_prune_a_key_it_does_not_hold(self, tmp_path):
        """A miss means the caller replayed against a different tape; emptying this one would hide it."""
        import pytest

        from caliper.tape import prune

        tape = Tape(tmp_path / "t.jsonl", mode="record")
        tape.record(request(), response="a", agent="compiler")
        tape.save()

        with pytest.raises(KeyError):
            prune(tmp_path / "t.jsonl", {"a key that was never recorded"})

    def test_pruning_nothing_leaves_the_file_alone(self, tmp_path):
        from caliper.tape import prune

        tape = Tape(tmp_path / "t.jsonl", mode="record")
        tape.record(request(), response="a", agent="compiler")
        tape.save()
        before = (tmp_path / "t.jsonl").read_bytes()

        prune(tmp_path / "t.jsonl", {exchange_key(request())})
        assert (tmp_path / "t.jsonl").read_bytes() == before
