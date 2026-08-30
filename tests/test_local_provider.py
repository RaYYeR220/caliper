"""A local command-line program standing in for a hosted provider.

Every test here runs a real subprocess, because the interesting failures — a prompt too long for a
command line, a non-zero exit, a program that never returns — only exist below the level a mock
operates at. The program under test is a few lines of Python written into `tmp_path`, so the
machinery is real and the behaviour is fixed.

Nothing here needs the `claude` binary, a key, or a network. The one test that would is skipped
unless the binary is present *and* the run opts in, since it would otherwise spend someone else's
tokens to assert what the other tests already assert.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import sys
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

from caliper.llm import LadderExhausted, LLMClient, StructuredOutput, estimate_cost
from caliper.llm.local import (
    CHARS_PER_TOKEN,
    CLAUDE_CODE_ARGV,
    PROMPT_DELIMITER,
    EstimatedUsage,
    LocalCommand,
    LocalCommandError,
    LocalCommandFailed,
    LocalCommandTimeout,
    LocalTransport,
    claude_code_command,
    estimate_usage,
    local_profile,
    render_prompt,
)
from caliper.tape import Tape, TapeTransport

REPLY = '{"label": "eligible", "confidence": 0.5}'


class Verdict(BaseModel):
    """A deliberately tiny schema: these tests are about the transport, not about the IR."""

    model_config = ConfigDict(extra="forbid")

    label: str
    confidence: float


# ------------------------------------------------------------------------------------------------
# The program under test. `sys.executable` rather than "python": the suite runs from a venv whose
# Scripts directory is not necessarily on PATH, and the point is a deterministic child process.
# ------------------------------------------------------------------------------------------------


def write_script(tmp_path: Path, body: str, name: str = "cli.py") -> Path:
    script = tmp_path / name
    script.write_text(body, encoding="utf-8")
    return script


def command(script: Path, **overrides) -> LocalCommand:
    return LocalCommand(argv=(sys.executable, str(script)), **overrides)


def transport(script: Path, **overrides) -> LocalTransport:
    return LocalTransport(command(script, **overrides))


def echoing(tmp_path: Path, reply: str = REPLY) -> Path:
    """A program that ignores its input and prints a fixed answer."""
    body = (
        "import sys\n"
        "sys.stdout.reconfigure(encoding='utf-8')\n"
        "sys.stdin.reconfigure(encoding='utf-8')\n"
        "sys.stdin.read()\n"
        f"sys.stdout.write({reply!r})\n"
    )
    return write_script(tmp_path, body)


def recording(tmp_path: Path, reply: str = REPLY) -> tuple[Path, Path]:
    """A program that writes down what it was given, so a test can read it back."""
    log = tmp_path / "received.json"
    body = (
        "import json, pathlib, sys\n"
        "sys.stdout.reconfigure(encoding='utf-8')\n"
        "sys.stdin.reconfigure(encoding='utf-8')\n"
        "received = sys.stdin.read()\n"
        f"pathlib.Path({str(log)!r}).write_text(\n"
        "    json.dumps({'stdin': received, 'argv': sys.argv}), encoding='utf-8'\n"
        ")\n"
        f"sys.stdout.write({reply!r})\n"
    )
    return write_script(tmp_path, body), log


def received(log: Path) -> dict:
    return json.loads(log.read_text(encoding="utf-8"))


def a_client(script: Path, **overrides) -> LLMClient:
    return LLMClient(local_profile(), transport=transport(script, **overrides))


def ask(script: Path, system: str = "Decide.", user: str = "A patient.") -> Verdict:
    return a_client(script).complete(system=system, user=user, model_cls=Verdict).value


def create(script: Path, system: str = "sys", user: str = "usr", **payload):
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    return transport(script).chat.completions.create(
        model="local", messages=messages, temperature=0.0, stream=False, **payload
    )


# ------------------------------------------------------------------------------------------------


class TestItIsAProvider:
    def test_a_fixed_reply_round_trips_to_a_validated_model(self, tmp_path):
        """The whole point: a shell command satisfies the same contract as the OpenAI client."""
        assert ask(echoing(tmp_path)) == Verdict(label="eligible", confidence=0.5)

    def test_a_reply_wrapped_in_prose_is_still_recovered(self, tmp_path):
        """Extraction is the client's job; the transport hands over what it was given, unedited."""
        chatty = f"Sure! Here you go:\n\n```json\n{REPLY}\n```\nHope that helps."
        assert ask(echoing(tmp_path, chatty)).label == "eligible"

    def test_the_extra_arguments_the_client_sends_are_tolerated(self, tmp_path):
        """`seed`, `stream` and `extra_body` mean nothing to a subprocess and must not break it."""
        response = create(echoing(tmp_path), seed=7, extra_body={"anything": True})
        assert response.choices[0].message.content == REPLY

    def test_a_retry_carries_the_earlier_turns_without_upsetting_the_renderer(self, tmp_path):
        """The client re-asks with assistant turns appended; the prompt has to absorb them."""
        body = (
            "import pathlib, sys\n"
            "sys.stdout.reconfigure(encoding='utf-8')\n"
            "sys.stdin.reconfigure(encoding='utf-8')\n"
            "sys.stdin.read()\n"
            "counter = pathlib.Path(__file__).with_suffix('.count')\n"
            "seen = int(counter.read_text()) if counter.exists() else 0\n"
            "counter.write_text(str(seen + 1))\n"
            f"sys.stdout.write('not json at all' if seen == 0 else {REPLY!r})\n"
        )
        assert ask(write_script(tmp_path, body)).confidence == 0.5


class TestTheCombinedPrompt:
    def test_the_system_prompt_arrives_before_the_user_prompt(self, tmp_path):
        """Instructions have to land before the material they govern, or they read as commentary."""
        script, log = recording(tmp_path)
        create(script, system="RULES-MARKER", user="MATERIAL-MARKER")

        prompt = received(log)["stdin"]
        assert prompt.index("RULES-MARKER") < prompt.index("MATERIAL-MARKER")

    def test_the_two_are_separated_by_a_delimiter(self, tmp_path):
        script, log = recording(tmp_path)
        create(script, system="RULES-MARKER", user="MATERIAL-MARKER")
        assert PROMPT_DELIMITER in received(log)["stdin"]

    def test_a_system_message_out_of_order_is_still_put_first(self):
        """The rule is a property of the rendering, not an assumption about the caller."""
        prompt = render_prompt(
            [{"role": "user", "content": "MATERIAL"}, {"role": "system", "content": "RULES"}]
        )
        assert prompt.index("RULES") < prompt.index("MATERIAL")

    def test_the_roles_are_labelled_because_the_program_cannot_see_them(self):
        prompt = render_prompt(
            [
                {"role": "system", "content": "RULES"},
                {"role": "user", "content": "MATERIAL"},
                {"role": "assistant", "content": "EARLIER"},
            ]
        )
        assert prompt.count(PROMPT_DELIMITER) == 2
        assert "EARLIER" in prompt

    def test_non_ascii_criteria_text_survives_the_round_trip(self, tmp_path):
        script, log = recording(tmp_path)
        create(script, user="eGFR ≥ 30 mL/min/1.73m²")
        assert "≥ 30 mL/min" in received(log)["stdin"]


class TestTheInputGoesOnStdin:
    def test_the_prompt_is_not_passed_as_an_argument(self, tmp_path):
        script, log = recording(tmp_path)
        create(script, user="MATERIAL-MARKER")

        seen = received(log)
        assert "MATERIAL-MARKER" in seen["stdin"]
        assert not any("MATERIAL-MARKER" in argument for argument in seen["argv"])

    def test_a_prompt_far_past_the_command_line_limit_still_arrives(self, tmp_path):
        """Windows caps a command line near 8k characters. One protocol's criteria exceed that."""
        script, log = recording(tmp_path)
        criteria = "Serum creatinine below 1.5 mg/dL. " * 6000
        create(script, user=criteria)
        assert received(log)["stdin"].count("Serum creatinine") == 6000


class TestAFailedRun:
    def test_a_non_zero_exit_raises_rather_than_returning_an_empty_completion(self, tmp_path):
        body = "import sys\nsys.stdin.read()\nsys.stderr.write('BOOM')\nsys.exit(3)\n"
        with pytest.raises(LocalCommandFailed) as caught:
            create(write_script(tmp_path, body))

        assert caught.value.returncode == 3
        assert "3" in str(caught.value)
        assert "BOOM" in str(caught.value)

    def test_the_failure_reaches_the_caller_through_the_client(self, tmp_path):
        """The client abandons a rung on any transport error; the reason must survive the trip."""
        body = "import sys\nsys.stdin.read()\nsys.stderr.write('BOOM')\nsys.exit(3)\n"
        with pytest.raises(LadderExhausted) as caught:
            ask(write_script(tmp_path, body))
        assert "BOOM" in str(caught.value)

    def test_a_long_stderr_is_truncated_but_keeps_the_part_that_says_why(self, tmp_path):
        body = (
            "import sys\n"
            "sys.stdin.read()\n"
            "sys.stderr.write('noise\\n' * 4000)\n"
            "sys.stderr.write('BOOM: the actual reason')\n"
            "sys.exit(1)\n"
        )
        with pytest.raises(LocalCommandFailed) as caught:
            create(write_script(tmp_path, body))

        message = str(caught.value)
        assert "BOOM: the actual reason" in message
        assert len(message) < 4000

    def test_silence_on_stderr_is_reported_as_silence(self, tmp_path):
        body = "import sys\nsys.stdin.read()\nsys.exit(9)\n"
        with pytest.raises(LocalCommandFailed) as caught:
            create(write_script(tmp_path, body))
        assert caught.value.stderr == ""
        assert "9" in str(caught.value)

    def test_a_program_that_is_not_there_says_so(self, tmp_path):
        missing = LocalCommand(argv=(str(tmp_path / "no-such-program"),))
        with pytest.raises(LocalCommandError):
            LocalTransport(missing).chat.completions.create(
                model="local", messages=[{"role": "user", "content": "hello"}]
            )

    def test_every_failure_is_catchable_as_one_kind(self):
        """Callers draw a boundary around the model layer, not around subprocess internals."""
        assert issubclass(LocalCommandFailed, LocalCommandError)
        assert issubclass(LocalCommandTimeout, LocalCommandError)


class TestATimeout:
    def test_a_program_that_never_returns_raises_instead_of_hanging(self, tmp_path):
        body = "import sys, time\nsys.stdin.read()\ntime.sleep(30)\n"
        slow = transport(write_script(tmp_path, body), timeout_seconds=0.5)
        with pytest.raises(LocalCommandTimeout) as caught:
            slow.chat.completions.create(
                model="local", messages=[{"role": "user", "content": "hello"}]
            )
        assert "0.5" in str(caught.value)
        assert caught.value.timeout_seconds == 0.5


class TestTheUsageEstimate:
    def test_the_usage_is_labelled_an_estimate(self, tmp_path):
        usage = create(echoing(tmp_path)).usage
        assert isinstance(usage, EstimatedUsage)
        assert usage.is_estimate is True
        assert "estimate" in repr(usage).lower()

    def test_the_estimate_follows_the_stated_ratio(self, tmp_path):
        messages = [{"role": "system", "content": "sys"}, {"role": "user", "content": "usr"}]
        usage = create(echoing(tmp_path)).usage
        expected = math.ceil(len(render_prompt(messages)) / CHARS_PER_TOKEN)
        assert usage.prompt_tokens == expected
        assert usage.completion_tokens == math.ceil(len(REPLY) / CHARS_PER_TOKEN)

    def test_the_ratio_it_used_travels_with_the_number(self, tmp_path):
        assert create(echoing(tmp_path)).usage.chars_per_token == CHARS_PER_TOKEN

    def test_an_estimate_never_becomes_a_cost_figure(self):
        """The guard that matters: unpriced, so no guess can be multiplied into a bill."""
        usage = estimate_usage("a" * 4000, "b" * 400)
        assert estimate_cost(local_profile(), usage) is None

    def test_the_client_carries_it_through_as_unpriced(self, tmp_path):
        completion = a_client(echoing(tmp_path)).complete(
            system="Decide.", user="A patient.", model_cls=Verdict
        )
        assert completion.cost.usd is None
        assert completion.cost.usage.total_tokens > 0

    def test_empty_text_estimates_nothing(self):
        assert estimate_usage("", "").prompt_tokens == 0


class TestTheSchemaRequest:
    def test_the_schema_name_is_named_in_the_prompt(self, tmp_path):
        script, log = recording(tmp_path)
        create(
            script,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "Verdict", "strict": True, "schema": {}},
            },
        )
        prompt = received(log)["stdin"]
        assert "Verdict" in prompt
        assert "single JSON object" in prompt

    def test_a_bare_json_object_request_still_asks_for_one_object(self, tmp_path):
        script, log = recording(tmp_path)
        create(script, response_format={"type": "json_object"})
        assert "single JSON object" in received(log)["stdin"]

    def test_no_schema_request_leaves_the_prompt_alone(self, tmp_path):
        script, log = recording(tmp_path)
        create(script)
        assert "single JSON object" not in received(log)["stdin"]

    def test_the_transport_does_not_try_to_repair_the_output(self, tmp_path):
        """Parsing lives in `parsing.py`. Two implementations of it would be two behaviours."""
        junk = "I am afraid I cannot help with that."
        assert create(echoing(tmp_path, junk)).choices[0].message.content == junk


class TestItStaysQuiet:
    def test_the_child_output_is_captured_rather_than_echoed(self, tmp_path, capfd):
        body = (
            "import sys\n"
            "sys.stdin.read()\n"
            "sys.stderr.write('a warning nobody asked for')\n"
            f"sys.stdout.write({REPLY!r})\n"
        )
        create(write_script(tmp_path, body), user="PROTOCOL-TEXT")

        captured = capfd.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    def test_a_failure_message_does_not_repeat_the_prompt_back(self, tmp_path):
        """Errors are read in terminals and pasted into issues; prompts carry chart text."""
        body = "import sys\nsys.stdin.read()\nsys.exit(1)\n"
        with pytest.raises(LocalCommandFailed) as caught:
            create(write_script(tmp_path, body), user="PROTOCOL-TEXT")
        assert "PROTOCOL-TEXT" not in str(caught.value)


class TestTheProfile:
    def test_it_promises_no_structured_output(self):
        assert local_profile().structured_output is StructuredOutput.NONE

    def test_it_is_unpriced_rather_than_free(self):
        """A local run costs electricity and a subscription; zero would be a claim, not a blank."""
        profile = local_profile()
        assert profile.input_usd_per_mtok is None
        assert profile.output_usd_per_mtok is None

    def test_it_asks_for_no_credential(self):
        assert local_profile().api_key_env == ""

    def test_the_model_name_is_the_callers(self):
        assert local_profile("claude-code").name == "local:claude-code"

    def test_overrides_reach_the_profile(self):
        assert local_profile(notes="via claude -p").notes == "via claude -p"

    def test_the_client_needs_no_key_to_use_it(self, tmp_path):
        """Building the client must not go looking for a variable that does not exist."""
        assert ask(echoing(tmp_path)).label == "eligible"


class TestTheCommand:
    def test_an_empty_command_is_refused(self):
        with pytest.raises(ValueError):
            LocalCommand(argv=())

    def test_a_non_positive_timeout_is_refused(self):
        with pytest.raises(ValueError):
            LocalCommand(argv=("true",), timeout_seconds=0)

    def test_the_claude_code_helper_is_print_mode(self):
        assert claude_code_command().argv == CLAUDE_CODE_ARGV
        assert "-p" in CLAUDE_CODE_ARGV

    def test_the_helper_takes_the_same_overrides(self):
        assert claude_code_command(timeout_seconds=30.0).timeout_seconds == 30.0


class TestUnderATape:
    def test_it_records_and_then_replays_without_the_program(self, tmp_path):
        """This is how a run gets committed: the tape has to outlive the thing that produced it."""
        script = echoing(tmp_path)
        tape_path = tmp_path / "tape.jsonl"

        recorder = Tape(tape_path, mode="record")
        live = LLMClient(
            local_profile(),
            transport=TapeTransport(recorder, upstream=transport(script), agent="compiler"),
        )
        first = live.complete(system="Decide.", user="A patient.", model_cls=Verdict)
        recorder.save()

        script.unlink()

        replayed = Tape(tape_path, mode="replay")
        offline = LLMClient(local_profile(), transport=TapeTransport(replayed))
        second = offline.complete(system="Decide.", user="A patient.", model_cls=Verdict)

        assert second.value == first.value
        assert replayed.hits == 1
        assert replayed.misses == 0

    def test_the_recorded_exchange_is_readable(self, tmp_path):
        script = echoing(tmp_path)
        tape_path = tmp_path / "tape.jsonl"
        recorder = Tape(tape_path, mode="record")
        client = LLMClient(
            local_profile(),
            transport=TapeTransport(recorder, upstream=transport(script), agent="compiler"),
        )
        client.complete(system="Decide.", user="A patient.", model_cls=Verdict)
        recorder.save()

        exchange = Tape(tape_path).exchanges()[0]
        assert exchange.response == REPLY
        assert "A patient." in exchange.user
        assert exchange.usage["prompt_tokens"] > 0


CLAUDE_BINARY = shutil.which("claude")
LIVE_CLI = os.environ.get("CALIPER_LIVE_LOCAL_CLI") == "1"


@pytest.mark.skipif(
    CLAUDE_BINARY is None or not LIVE_CLI,
    reason="needs the claude binary and CALIPER_LIVE_LOCAL_CLI=1; it costs tokens and a network",
)
def test_the_motivating_case_actually_works():
    """The one test that talks to a real CLI. Everything above asserts the same thing offline."""
    client = LLMClient(
        local_profile("claude-code"),
        transport=LocalTransport(claude_code_command(timeout_seconds=120.0)),
    )
    verdict = client.complete(
        system="Decide whether the patient is eligible.",
        user='The patient is eligible. Use confidence 0.5 and label "eligible".',
        model_cls=Verdict,
    )
    assert verdict.value.label
