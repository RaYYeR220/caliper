"""A stand-in provider, so every agent can be exercised without a network or a key.

Replies are consumed in order and the requests are kept, which lets a test assert on what was
actually sent rather than on how many times a mock was called.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from caliper.llm import LLMClient, ProviderProfile, StructuredOutput


class Reply:
    """One canned assistant turn, with the usage a provider would have reported."""

    def __init__(self, content: str, prompt_tokens: int = 100, completion_tokens: int = 20):
        self.content = content
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class FakeTransport:
    """Exposes only `chat.completions.create`, the surface `LLMClient` actually uses."""

    def __init__(self, replies: list[Reply | Exception] | None = None):
        self.replies: list[Reply | Exception] = list(replies or [])
        self.requests: list[dict[str, Any]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs: Any) -> SimpleNamespace:
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

    @property
    def user_messages(self) -> list[str]:
        return [r["messages"][-1]["content"] for r in self.requests]


def a_profile(**overrides: Any) -> ProviderProfile:
    defaults: dict[str, Any] = dict(
        provider="venice",
        model="test-model",
        base_url="https://example.invalid/v1",
        api_key_env="TEST_API_KEY",
        structured_output=StructuredOutput.JSON_SCHEMA,
        input_usd_per_mtok=1.0,
        output_usd_per_mtok=2.0,
    )
    return ProviderProfile(**{**defaults, **overrides})


def a_client(
    replies: list[Reply | Exception] | None = None,
    *,
    profile: ProviderProfile | None = None,
    **kw: Any,
) -> tuple[LLMClient, FakeTransport]:
    transport = FakeTransport(replies)
    client = LLMClient(
        profile or a_profile(), transport=transport, env={"TEST_API_KEY": "not-a-real-key"}, **kw
    )
    return client, transport


class RoutedTransport(FakeTransport):
    """Replies chosen by what the request is about, rather than by call order.

    Order-based fakes are brittle here: the client's retry ladder decides how many turns a single
    logical call takes, so a test that counts replies is really asserting on the ladder.

    `agent_routes` is keyed on a substring of the *system* prompt and takes precedence, because in a
    full pipeline several agents see the same protocol text and routing on the user message alone
    would hand the critic the compiler's answer.
    """

    def __init__(
        self,
        routes: dict[str, str] | None = None,
        *,
        agent_routes: dict[str, dict[str, str] | str] | None = None,
        default: str | None = None,
    ):
        super().__init__([])
        self.routes = routes or {}
        self.agent_routes = agent_routes or {}
        self.default = default

    def _create(self, **kwargs: Any) -> SimpleNamespace:
        self.requests.append(kwargs)
        system = kwargs["messages"][0]["content"]
        user = kwargs["messages"][-1]["content"]

        for needle, route in self.agent_routes.items():
            if needle not in system:
                continue
            if isinstance(route, str):
                return _response(route)
            for user_needle, content in route.items():
                if user_needle in user:
                    return _response(content)
            break

        for needle, content in self.routes.items():
            if needle in user:
                return _response(content)
        if self.default is None:
            raise AssertionError(f"no route matched a request about: {user[:120]!r}")
        return _response(self.default)


def _response(content: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=100, completion_tokens=20),
    )


def a_routed_client(
    routes: dict[str, str] | None = None,
    *,
    agent_routes: dict[str, dict[str, str] | str] | None = None,
    default: str | None = None,
    profile: ProviderProfile | None = None,
    **kw: Any,
) -> tuple[LLMClient, RoutedTransport]:
    transport = RoutedTransport(routes, agent_routes=agent_routes, default=default)
    client = LLMClient(
        profile or a_profile(), transport=transport, env={"TEST_API_KEY": "not-a-real-key"}, **kw
    )
    return client, transport


class ProgrammableTransport(FakeTransport):
    """Replies computed from the request, for tests that run over real corpus data.

    A canned reply cannot satisfy the compiler on a real protocol, because the quote it returns is
    checked against the protocol text and a fixed string will not match forty different spans. This
    transport is handed a function of the system and user prompts and can therefore echo the span it
    was actually given.
    """

    def __init__(self, respond: Any):
        super().__init__([])
        self.respond = respond

    def _create(self, **kwargs: Any) -> SimpleNamespace:
        self.requests.append(kwargs)
        system = kwargs["messages"][0]["content"]
        user = kwargs["messages"][-1]["content"]
        return _response(self.respond(system, user))


def a_programmable_client(
    respond: Any, *, profile: ProviderProfile | None = None, **kw: Any
) -> tuple[LLMClient, ProgrammableTransport]:
    transport = ProgrammableTransport(respond)
    client = LLMClient(
        profile or a_profile(), transport=transport, env={"TEST_API_KEY": "not-a-real-key"}, **kw
    )
    return client, transport
