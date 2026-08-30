"""Reading `.env`, without a dependency for it.

Twenty lines of parsing against a package is a poor trade when the file is ours and the format is
four rules. It also keeps the loader's behaviour visible: the environment always wins, so a variable
set on the command line is not quietly overridden by a stale file.
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_ENV_FILE = Path(".env")


def parse_env(text: str) -> dict[str, str]:
    """Parse a `.env` file: `KEY=value` per line, `#` comments, optional surrounding quotes."""
    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def load_env(path: Path = DEFAULT_ENV_FILE, env: dict[str, str] | None = None) -> list[str]:
    """Load `path` into the environment and return the names it set.

    A variable already present is left alone. Someone who exported a key for one command meant it
    for that command, and a file on disk should not be able to countermand them.
    """
    target = os.environ if env is None else env
    if not path.is_file():
        return []

    loaded = []
    for key, value in parse_env(path.read_text(encoding="utf-8")).items():
        if not value or key in target:
            continue
        target[key] = value
        loaded.append(key)
    return loaded
