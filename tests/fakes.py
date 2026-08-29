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
    logical call takes, so a test that counts replies is really asserting on the ladder. Routing on
    a substring of the user message lets a test say "this criterion fails" and mean it.
    """

    def __init__(self, routes: dict[str, str], *, default: str | None = None):
        super().__init__([])
        self.routes = routes
        self.default = default

    def _create(self, **kwargs: Any) -> SimpleNamespace:
        self.requests.append(kwargs)
        user = kwargs["messages"][-1]["content"]
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
    routes: dict[str, str],
    *,
    default: str | None = None,
    profile: ProviderProfile | None = None,
    **kw: Any,
) -> tuple[LLMClient, RoutedTransport]:
    transport = RoutedTransport(routes, default=default)
    client = LLMClient(
        profile or a_profile(), transport=transport, env={"TEST_API_KEY": "not-a-real-key"}, **kw
    )
    return client, transport
