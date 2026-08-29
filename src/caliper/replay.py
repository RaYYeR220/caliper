"""Recording and replaying model responses.

This is the reproducibility story, and it is worth saying why it is not the obvious one. Setting
temperature to zero and pinning a seed does not make a hosted model deterministic: the provider
batches requests, and the reduction order inside a batched kernel depends on what else was in the
batch, so identical inputs can produce different tokens. Fixed seeds only control the sampler,
which at temperature zero is doing nothing anyway.

So the headline result does not depend on the provider behaving. It is replayed from recorded HTTP
exchanges committed to the repository, which means a reviewer with no key, no network and no budget
gets exactly the numbers in the report. The live path still exists, and reports its drift against
the recording rather than hiding it.

Nothing that could identify a key reaches a cassette: authorisation headers are redacted before
anything is written, and a test greps the cassette directory to prove it.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal

CASSETTE_ROOT = Path(__file__).resolve().parents[2] / "eval" / "cassettes"

REDACTED_HEADERS = ("authorization", "x-api-key", "api-key", "openai-organization", "cookie")

RecordMode = Literal["none", "once", "new_episodes", "all"]


def cassette_config(path: Path) -> dict[str, Any]:
    """The one configuration every recording and every replay must share.

    Matching on the request body is not optional. Every call in a run goes to the same URL with the
    same method, so a cassette matched on the URL alone would replay whichever response happened to
    be recorded first and quietly answer the compiler with the critic's verdict.
    """
    return {
        "path": str(path),
        "filter_headers": [(name, "REDACTED") for name in REDACTED_HEADERS],
        "match_on": ["method", "scheme", "host", "port", "path", "body"],
        "decode_compressed_response": True,
        "allow_playback_repeats": True,
    }


@contextmanager
def cassette(name: str, *, mode: RecordMode = "none", root: Path = CASSETTE_ROOT) -> Iterator[Any]:
    """Play back, or record, the model traffic for one named run.

    In `none` the tape is authoritative and an unmatched request raises rather than silently
    reaching the network, which is what makes "this ran offline" a claim rather than a hope.
    """
    import vcr

    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{name}.yaml"
    recorder = vcr.VCR(record_mode=mode, **_vcr_kwargs())
    with recorder.use_cassette(str(path)) as tape:
        yield tape


def _vcr_kwargs() -> dict[str, Any]:
    return {
        "filter_headers": [(name, "REDACTED") for name in REDACTED_HEADERS],
        "match_on": ["method", "scheme", "host", "port", "path", "body"],
        "decode_compressed_response": True,
    }


def cassette_exists(name: str, root: Path = CASSETTE_ROOT) -> bool:
    return (root / f"{name}.yaml").is_file()


def recorded_runs(root: Path = CASSETTE_ROOT) -> list[str]:
    return sorted(p.stem for p in root.glob("*.yaml"))
