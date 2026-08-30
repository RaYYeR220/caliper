"""A provider that is a program on this machine rather than an endpoint on the internet.

The provider layer is thin. `LLMClient` needs `chat.completions.create(**kwargs)` to come back with
a message and a token count, and nothing above it cares how that happened. So any local command
that maps text to text can be a provider, which is useful twice over. It is useful when no hosted
key is available: the Claude Code CLI in print mode (`claude -p`) is the motivating case, and a
reviewer who already has it installed can run the pipeline without signing up for anything. And it
is useful as a check that the abstraction is real rather than an `openai`-shaped hole — a transport
that shells out shares no code path with the SDK, so a pipeline that runs on both is one whose seam
is where it is claimed to be.

What a command-line program cannot do is honour a schema, count tokens, or tell a system message
from a user one. Each of those is met here by doing the honest thing rather than the convenient
one. The messages are flattened into one prompt in a documented order. A schema request becomes an
instruction in that prompt and is otherwise left to the client's own validation gate, which is the
only thing in this codebase that decides whether a response is data. Usage comes back as an
explicitly marked estimate, and `local_profile` prices at `None`, so the estimate cannot be
multiplied into a figure that reads like a measurement.

Nothing here logs, prints, or echoes. The prompts carry protocol text and chart text, and a
transport is not the place to decide that is safe to write down.

`local:claude-code` is a built-in profile, so `CALIPER_PROVIDER=local` resolves to it the way
`venice` and `openrouter` do. The profile is only half of it: a profile says where a model lives,
and this one lives in a subprocess, so the caller has to hand `LLMClient` the transport as well.
`LLMClient` builds an HTTP client when it is given none, and against `local://command` that fails —
loudly, which is the intended failure and not a fallback.

    from caliper.llm import LLMClient, profile_from_env
    from caliper.llm.local import LocalTransport, claude_code_command

    client = LLMClient(profile_from_env(), transport=LocalTransport(claude_code_command()))
"""

from __future__ import annotations

import math
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from caliper.llm.errors import LLMError
from caliper.llm.provider import (
    CLAUDE_CODE_MODEL,
    LOCAL_BASE_URL,
    LOCAL_PROVIDER,
    ProviderProfile,
    local,
)

__all__ = [
    "CLAUDE_CODE_ARGV",
    "CHARS_PER_TOKEN",
    "LOCAL_BASE_URL",
    "LOCAL_PROVIDER",
    "EstimatedUsage",
    "LocalCommand",
    "LocalCommandError",
    "LocalCommandFailed",
    "LocalCommandTimeout",
    "LocalTransport",
    "claude_code_command",
    "estimate_usage",
    "local_profile",
    "render_prompt",
]

# `claude -p` reads a prompt on stdin and writes the completion to stdout. Named here for the
# convenience constructor below; the transport itself knows nothing about it.
CLAUDE_CODE_ARGV: tuple[str, ...] = ("claude", "-p")

PROMPT_DELIMITER = "\n\n" + "-" * 56 + "\n\n"

# The usual English rule of thumb. Stated as a constant, carried on every estimate, and never
# quietly refined: a number that drifts is worse than one that is openly approximate.
CHARS_PER_TOKEN = 4.0

STDERR_EXCERPT_CHARS = 2000

_ROLE_LABELS = {
    "system": "INSTRUCTIONS",
    "user": "INPUT",
    "assistant": "YOUR PREVIOUS REPLY",
}
_FORMAT_LABEL = "OUTPUT FORMAT"

_SCHEMA_INSTRUCTION = "Reply with a single JSON object and nothing else."
_NAMED_SCHEMA_INSTRUCTION = (
    "Reply with a single JSON object conforming to the {name} schema, and nothing else."
)


class LocalCommandError(LLMError):
    """A local program could not be run, or did not finish the way a completion needs it to."""


class LocalCommandFailed(LocalCommandError):
    """The program ran and exited non-zero.

    Distinct from an empty completion on purpose. A model that answers with nothing is a failed
    response and gets re-asked; a program that exits 1 is a failed request and must not be quietly
    fed into the parser as an empty string.
    """

    def __init__(self, command: LocalCommand, returncode: int, stderr: str):
        self.command = command
        self.returncode = returncode
        self.stderr = stderr
        excerpt = _excerpt(stderr)
        detail = f": {excerpt}" if excerpt else " and wrote nothing to stderr"
        # The prompt is deliberately absent: these messages end up in terminals and issue reports.
        super().__init__(f"{command.display} exited {returncode}{detail}")


class LocalCommandTimeout(LocalCommandError):
    """The program was still running when its budget ran out, and was killed."""

    def __init__(self, command: LocalCommand, timeout_seconds: float):
        self.command = command
        self.timeout_seconds = timeout_seconds
        super().__init__(f"{command.display} did not finish within {timeout_seconds:g} seconds")


@dataclass(frozen=True)
class LocalCommand:
    """What to run, and how long to wait for it."""

    argv: tuple[str, ...]
    timeout_seconds: float = 300.0
    encoding: str = "utf-8"

    def __post_init__(self) -> None:
        if not self.argv:
            raise ValueError("a local command needs at least a program to run")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

    @property
    def display(self) -> str:
        """The command as a reader would recognise it. Diagnostic only, never re-executed."""
        return " ".join(self.argv)


@dataclass(frozen=True)
class EstimatedUsage:
    """Token counts a local program did not report, inferred from character counts.

    Named, flagged and carrying its own ratio because the alternative is a number that looks
    exactly like a measurement in every place a measurement is expected. `local_profile` leaves
    prices unset, so nothing downstream turns this into a cost.
    """

    prompt_tokens: int
    completion_tokens: int
    is_estimate: bool = True
    chars_per_token: float = CHARS_PER_TOKEN

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True)
class LocalMessage:
    content: str
    role: str = "assistant"


@dataclass(frozen=True)
class LocalChoice:
    message: LocalMessage
    index: int = 0


@dataclass(frozen=True)
class LocalResponse:
    """The OpenAI-shaped envelope, with only the fields anything in this codebase reads.

    Only those fields. A `finish_reason` and a second copy of `usage.is_estimate` were here, and
    both were write-only: nothing read either, and a field nobody reads is a claim nobody checks.
    `EstimatedUsage.is_estimate` is the one place that says these counts were inferred.
    """

    choices: tuple[LocalChoice, ...]
    usage: EstimatedUsage
    model: str = LOCAL_PROVIDER


def render_prompt(
    messages: Sequence[Mapping[str, Any]],
    *,
    response_format: Mapping[str, Any] | None = None,
) -> str:
    """Flatten a chat message list into the single string a command-line program can read.

    The format is stable and part of this module's contract:

        INSTRUCTIONS
        <system content>
        <delimiter>
        INPUT
        <user content>
        <delimiter>
        OUTPUT FORMAT
        <schema instruction, only when one was requested>

    System messages come first regardless of where they sat in the list. The order is the whole
    point of the rendering: instructions have to arrive before the material they govern, because a
    program reading top to bottom takes what precedes as its brief and what follows as the thing to
    work on. Put the protocol text first and the standing instructions read as a comment on it.

    Roles are labelled because the flattening destroys them, and an unlabelled concatenation makes
    a criterion that says "ignore the above" indistinguishable from an instruction that does. The
    format instruction goes last, where it is nearest the reply it constrains.
    """
    ordered = sorted(messages, key=lambda message: str(message.get("role", "")) != "system")
    blocks = [
        f"{_label(str(message.get('role', '')))}\n{message.get('content', '')}"
        for message in ordered
    ]
    instruction = _format_instruction(response_format)
    if instruction is not None:
        blocks.append(f"{_FORMAT_LABEL}\n{instruction}")
    return PROMPT_DELIMITER.join(blocks)


def estimate_usage(prompt: str, completion: str) -> EstimatedUsage:
    """Approximate token counts for one exchange at `CHARS_PER_TOKEN` characters per token."""
    return EstimatedUsage(
        prompt_tokens=_estimate_tokens(prompt),
        completion_tokens=_estimate_tokens(completion),
    )


class LocalTransport:
    """An OpenAI-shaped transport that fulfils a request by running a program on this machine.

    Exposes exactly `chat.completions.create(**kwargs)`, which is the entire surface `LLMClient`
    uses, so it drops in wherever the SDK client does — including underneath `TapeTransport`, which
    is how a run is recorded.
    """

    def __init__(self, command: LocalCommand, *, model: str = "local"):
        self.command = command
        self.model = model
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **payload: Any) -> LocalResponse:
        """Answer one request. Unknown keys — `temperature`, `seed`, `stream`, `extra_body` — are
        accepted and ignored: they describe how a hosted model should sample, and a subprocess has
        no such knobs. Silently ignoring them is right here, because the alternative is refusing
        requests the client sends to every provider.
        """
        prompt = render_prompt(
            payload.get("messages") or (),
            response_format=payload.get("response_format"),
        )
        completion = self._run(prompt)
        return LocalResponse(
            choices=(LocalChoice(message=LocalMessage(content=completion)),),
            usage=estimate_usage(prompt, completion),
            model=str(payload.get("model") or self.model),
        )

    def _run(self, prompt: str) -> str:
        """Run the program with the prompt on stdin, and return its stdout unedited.

        Stdin rather than an argument for two reasons: one protocol's criteria text is longer than
        a Windows command line is allowed to be, and quoting arbitrary clinical text correctly
        across shells is a bug waiting for a particular trial to trigger it.

        The output is returned exactly as it arrived. Digging JSON out of prose is `parsing.py`'s
        job, and a second implementation of it here would be a second behaviour to keep in step.
        """
        try:
            # No shell. The argv is passed through as a list, so nothing in a prompt can become a
            # command, and quoting is the operating system's problem rather than ours.
            completed = subprocess.run(
                list(self.command.argv),
                input=prompt,
                capture_output=True,
                text=True,
                encoding=self.command.encoding,
                # A stray undecodable byte in a diagnostic line should not take down a run that
                # otherwise produced a valid answer.
                errors="replace",
                timeout=self.command.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise LocalCommandTimeout(self.command, self.command.timeout_seconds) from exc
        except OSError as exc:
            raise LocalCommandError(f"could not run {self.command.display}: {exc}") from exc

        if completed.returncode != 0:
            raise LocalCommandFailed(self.command, completed.returncode, completed.stderr or "")
        return completed.stdout or ""


def local_profile(model: str = CLAUDE_CODE_MODEL, **overrides: Any) -> ProviderProfile:
    """A profile for a model reached by running a program. Defined in `provider.py`.

    Kept as a name in this module because a reader who has found the transport should not have to
    go looking for the profile that goes with it, and because the docstring explaining why the
    prices are `None` belongs beside the code that estimates the tokens.
    """
    return local(model, **overrides)


def claude_code_command(**overrides: Any) -> LocalCommand:
    """The motivating case, as a constructor rather than as a hard-coded assumption."""
    return LocalCommand(**{"argv": CLAUDE_CODE_ARGV, **overrides})


def _label(role: str) -> str:
    # An unrecognised role is labelled with its own name rather than dropped: a reader of the
    # prompt should be able to see that something arrived which this module did not expect.
    return _ROLE_LABELS.get(role) or (role.upper() if role else "INPUT")


def _format_instruction(response_format: Mapping[str, Any] | None) -> str | None:
    """Turn a `response_format` into words, since a pipe cannot carry one.

    This is as far as the honouring goes. The client's ladder already pastes the schema itself into
    the prompt on the rungs below `json_schema`, and its validation gate decides whether what came
    back is acceptable; naming the schema here is the part that would otherwise be lost.
    """
    if not response_format:
        return None
    schema = response_format.get("json_schema")
    name = schema.get("name") if isinstance(schema, Mapping) else None
    if name:
        return _NAMED_SCHEMA_INSTRUCTION.format(name=name)
    return _SCHEMA_INSTRUCTION


def _estimate_tokens(text: str) -> int:
    # Ceiling rather than rounding: any non-empty text costs at least one token, and an estimate
    # that can report zero for real work is worse than one that is coarse.
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def _excerpt(text: str, limit: int = STDERR_EXCERPT_CHARS) -> str:
    """The part of stderr worth putting in an exception message.

    The tail is kept rather than the head. A program that fails says why in its last lines — the
    exception, the parse error, the refusal — and a long stderr is usually a banner or a progress
    log standing in front of one useful sentence.
    """
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return "..." + stripped[-limit:]
