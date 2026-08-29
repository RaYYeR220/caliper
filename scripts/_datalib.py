"""Shared helpers for the data fixture build scripts.

Every file committed under ``data/`` is written through these helpers so that byte
layout -- indentation, key order, encoding and newlines -- is identical on every
platform. Without that guarantee the digests in ``data/SHA256SUMS`` would differ
between a Windows and a Linux run and the integrity test would be worthless.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
CACHE_DIR = REPO_ROOT / ".cache"
CHECKSUM_FILE = DATA_DIR / "SHA256SUMS"


def json_bytes(payload: Any) -> bytes:
    """Serialise ``payload`` to the canonical on-disk form used across ``data/``."""
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
    return (text + "\n").encode("utf-8")


def write_json(path: Path, payload: Any) -> int:
    """Write ``payload`` to ``path`` canonically and return the number of bytes written."""
    data = json_bytes(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Binary mode: text mode would rewrite "\n" as "\r\n" on Windows and break the digests.
    path.write_bytes(data)
    return len(data)


def sha256_file(path: Path) -> str:
    """Return the hex SHA-256 digest of the file at ``path``."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_data_files() -> Iterator[Path]:
    """Yield every file under ``data/`` except the checksum manifest itself."""
    for path in sorted(DATA_DIR.rglob("*")):
        if path.is_file() and path != CHECKSUM_FILE:
            yield path


def write_sha256sums() -> int:
    """Rewrite ``data/SHA256SUMS`` over the whole tree and return the number of entries."""
    lines = [
        f"{sha256_file(path)}  {path.relative_to(DATA_DIR).as_posix()}"
        for path in iter_data_files()
    ]
    CHECKSUM_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHECKSUM_FILE.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    return len(lines)
