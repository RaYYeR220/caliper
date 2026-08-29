"""Recovering a JSON object from whatever a model actually sent back.

The bottom rung of the ladder has no structured-output support to lean on, so the response can
arrive fenced, prefaced with an apology, or trailed by a summary. This module finds the object and
returns it *as text* — the validation gate downstream parses the bytes itself, so nothing is
re-serialised on the way through.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator

from caliper.llm.errors import LLMError

_FENCE = re.compile(r"```(?:[A-Za-z0-9_+-]*)\r?\n(.*?)```", re.DOTALL)


class JSONExtractionError(LLMError):
    """No JSON object could be found in a model response."""


def extract_json_object(text: str) -> str:
    """Return the first substring of `text` that parses as a JSON object.

    Fenced blocks are preferred, because a model that fenced its answer meant the fence to be the
    answer. Failing that, the text is scanned for a balanced `{...}` span, which handles prose on
    either side and braces inside string literals.
    """
    for candidate in _candidates(text):
        try:
            parsed = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            return candidate
    raise JSONExtractionError("no JSON object found in the response")


def _candidates(text: str) -> Iterator[str]:
    for match in _FENCE.finditer(text):
        yield match.group(1).strip()
    yield from _balanced_spans(text)


def _balanced_spans(text: str) -> Iterator[str]:
    """Yield every `{...}` span whose braces balance, in order of where they start."""
    for start, character in enumerate(text):
        if character != "{":
            continue
        depth = 0
        in_string = False
        escaped = False
        for end in range(start, len(text)):
            current = text[end]
            if in_string:
                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == '"':
                    in_string = False
                continue
            if current == '"':
                in_string = True
            elif current == "{":
                depth += 1
            elif current == "}":
                depth -= 1
                if depth == 0:
                    yield text[start : end + 1]
                    break
