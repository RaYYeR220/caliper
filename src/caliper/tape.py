"""A readable recording of everything a model was asked, and everything it said.

The reproducibility problem is real: temperature zero does not make a hosted model deterministic,
because providers batch requests and the reduction order inside a batched kernel depends on what
else was in the batch. So the committed result cannot depend on the provider behaving, and the run
has to be replayable from a recording.

The recording is kept at the level of the exchange rather than the socket. An HTTP capture proves
packets moved; it does not let a reviewer read what the compiler was asked about criterion four and
decide whether the answer was reasonable. A tape does, because it is one JSON object per call with
the prompts in it. It is also provider-agnostic, which matters more than it sounds: a capture is
coupled to whichever HTTP client happened to be in use.

A tape carries the conversation and nothing else. Headers never reach it, so a key cannot leak into
one; a test asserts that.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

TapeMode = Literal["replay", "record"]

DEFAULT_TAPE = Path("eval/tape.jsonl")


class TapeMiss(LookupError):
    """A request the tape has no answer for.

    Raised rather than falling through to the provider: a replay that quietly reached the network
    would make "this runs offline" false, and nobody would find out until the bill arrived.
    """


def exchange_key(payload: dict[str, Any]) -> str:
    """Identify a request by what was asked, not by how it was sent.

    The model, the whole message list and the name of the schema demanded back all count. The
    system prompt has to be in there: in a full run several agents are asked about the same
    protocol text, and a key built from the user message alone would hand the critic the compiler's
    answer.
    """
    schema = payload.get("response_format") or {}
    schema_name = ""
    if isinstance(schema, dict):
        schema_name = str(schema.get("json_schema", {}).get("name", schema.get("type", "")))

    material = json.dumps(
        {
            "model": payload.get("model"),
            "messages": payload.get("messages"),
            "schema": schema_name,
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Exchange:
    key: str
    agent: str
    model: str
    system: str
    user: str
    response: str
    usage: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "agent": self.agent,
            "model": self.model,
            "system": self.system,
            "user": self.user,
            "response": self.response,
            "usage": self.usage,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Exchange:
        return cls(
            key=payload["key"],
            agent=payload.get("agent", ""),
            model=payload.get("model", ""),
            system=payload.get("system", ""),
            user=payload.get("user", ""),
            response=payload["response"],
            usage=payload.get("usage", {}),
        )


_AGENT_HEADINGS = {
    "# Criteria compiler": "compiler",
    "# Concept resolution": "resolver",
    "# Back-translation check": "critic",
    "# Assertion detection": "extractor",
    "# Rationale writing": "writer",
    "# Trial pre-screening": "baseline",
}


def agent_from_system(system: str) -> str | None:
    """Which agent asked, read from the heading of its own instructions.

    Derived rather than plumbed through, so that recording needs no change anywhere else. The
    headings are the first line of the files in `agents/prompts/`, and a test pins them.
    """
    heading = system.strip().splitlines()[0].strip() if system.strip() else ""
    for prefix, name in _AGENT_HEADINGS.items():
        if heading.startswith(prefix):
            return name
    return None


def _role(payload: dict[str, Any], role: str) -> str:
    for message in payload.get("messages", []):
        if message.get("role") == role:
            return str(message.get("content", ""))
    return ""


class Tape:
    """A set of recorded exchanges, loaded from and written to one JSONL file."""

    def __init__(self, path: Path, *, mode: TapeMode = "replay"):
        self.path = Path(path)
        self.mode = mode
        self.hits = 0
        self.misses = 0
        self._entries: dict[str, Exchange] = {}
        if self.path.is_file():
            self._load()

    def _load(self) -> None:
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                exchange = Exchange.from_dict(json.loads(line))
                self._entries[exchange.key] = exchange

    def __len__(self) -> int:
        return len(self._entries)

    @property
    def agents(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for exchange in self._entries.values():
            counts[exchange.agent] = counts.get(exchange.agent, 0) + 1
        return dict(sorted(counts.items()))

    def exchanges(self) -> list[Exchange]:
        """Every recorded exchange, in the order the file holds them."""
        return [self._entries[key] for key in sorted(self._entries)]

    def lookup(self, payload: dict[str, Any]) -> Exchange | None:
        found = self._entries.get(exchange_key(payload))
        if found is None:
            self.misses += 1
        else:
            self.hits += 1
        return found

    def require(self, payload: dict[str, Any]) -> Exchange:
        found = self.lookup(payload)
        if found is not None:
            return found
        raise TapeMiss(
            f"no recorded answer for this request.\n"
            f"  model:  {payload.get('model')}\n"
            f"  system: {_role(payload, 'system')[:80]!r}\n"
            f"  user:   {_role(payload, 'user')[:200]!r}\n"
            f"The code has changed since the tape was recorded. Re-record with a key, or check out "
            f"the commit the tape belongs to."
        )

    def record(
        self,
        payload: dict[str, Any],
        *,
        response: str,
        agent: str,
        usage: dict[str, int] | None = None,
    ) -> Exchange:
        exchange = Exchange(
            key=exchange_key(payload),
            agent=agent,
            model=str(payload.get("model", "")),
            system=_role(payload, "system"),
            user=_role(payload, "user"),
            response=response,
            usage=usage or {},
        )
        self._entries[exchange.key] = exchange
        return exchange

    def save(self) -> None:
        """Write in key order, so two recordings of the same run diff to nothing."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            json.dumps(self._entries[key].to_dict(), sort_keys=True, ensure_ascii=False)
            for key in sorted(self._entries)
        ]
        self.path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


class TapeTransport:
    """An OpenAI-shaped transport that answers from a tape, or records into one."""

    def __init__(self, tape: Tape, *, upstream: Any = None, agent: str = "unknown"):
        self.tape = tape
        self.upstream = upstream
        self.agent = agent
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **payload: Any) -> SimpleNamespace:
        if self.tape.mode == "replay":
            return _as_response(self.tape.require(payload))

        if self.upstream is None:
            raise RuntimeError("recording needs an upstream transport to record from")
        live = self.upstream.chat.completions.create(**payload)
        content = live.choices[0].message.content or ""
        usage = {
            "prompt_tokens": getattr(live.usage, "prompt_tokens", 0),
            "completion_tokens": getattr(live.usage, "completion_tokens", 0),
        }
        agent = agent_from_system(_role(payload, "system")) or self.agent
        self.tape.record(payload, response=content, agent=agent, usage=usage)
        return live


def _as_response(exchange: Exchange) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=exchange.response))],
        usage=SimpleNamespace(
            prompt_tokens=exchange.usage.get("prompt_tokens", 0),
            completion_tokens=exchange.usage.get("completion_tokens", 0),
        ),
    )
