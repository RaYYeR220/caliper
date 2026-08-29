"""Snapshot clinical trial records from the ClinicalTrials.gov API v2.

Each study is stored as the full response body under ``data/trials/{NCT}.json``. The
content is not altered; it is only re-serialised into the canonical layout shared by
every fixture in this repository. The API version and its ``dataTimestamp`` are captured
in ``data/trials/_api_version.json`` so the snapshot can be cited exactly.

Usage:
    python scripts/fetch_trials.py
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import UTC, datetime
from typing import Any

import httpx
from _datalib import DATA_DIR, write_json, write_sha256sums

API_ROOT = "https://clinicaltrials.gov/api/v2"
VERSION_URL = f"{API_ROOT}/version"
TRIALS_DIR = DATA_DIR / "trials"

# Hand-picked studies with substantial free-text eligibility criteria, spanning the
# therapeutic areas the patient corpus is built around.
NCT_IDS = (
    "NCT03315143",
    "NCT03036124",
    "NCT02545049",
    "NCT03819153",
    "NCT06717698",
    "NCT07252908",
    "NCT06547333",
    "NCT05763121",
    "NCT01131676",
    "NCT05748834",
)

REQUEST_DELAY_S = 1.0
MAX_ATTEMPTS = 5
BACKOFF_BASE_S = 2.0
BACKOFF_CAP_S = 60.0


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    """Return how long to wait before retrying, preferring the server's ``Retry-After``."""
    header = response.headers.get("Retry-After")
    if header:
        try:
            return min(float(header), BACKOFF_CAP_S)
        except ValueError:
            pass  # Retry-After may be an HTTP date; fall back to our own backoff.
    return min(BACKOFF_BASE_S**attempt, BACKOFF_CAP_S)


def fetch_json(client: httpx.Client, url: str) -> Any:
    """GET ``url`` and return its decoded JSON body, retrying transient failures.

    Rate limiting (429) and server errors (5xx) are retried with exponential backoff.
    Client errors other than 429 are raised immediately -- retrying a 404 is pointless.
    """
    for attempt in range(1, MAX_ATTEMPTS + 1):
        response = client.get(url)
        if not response.is_error:
            return response.json()
        transient = response.status_code == 429 or response.status_code >= 500
        if not transient or attempt == MAX_ATTEMPTS:
            response.raise_for_status()
        delay = _retry_delay(response, attempt)
        print(f"  HTTP {response.status_code} from {url}; retrying in {delay:.0f}s")
        time.sleep(delay)
    raise AssertionError("retry loop must either return or raise")


def eligibility_criteria(study: dict[str, Any]) -> str:
    """Return the free-text eligibility criteria of a study record, or an empty string."""
    protocol = study.get("protocolSection", {})
    return protocol.get("eligibilityModule", {}).get("eligibilityCriteria", "") or ""


def fetch_study(client: httpx.Client, nct_id: str) -> dict[str, Any]:
    """Fetch one study and verify it is the record we asked for and is usable."""
    study = fetch_json(client, f"{API_ROOT}/studies/{nct_id}?format=json")
    returned_id = study.get("protocolSection", {}).get("identificationModule", {}).get("nctId")
    if returned_id != nct_id:
        raise RuntimeError(f"requested {nct_id} but the API returned {returned_id!r}")
    if not eligibility_criteria(study).strip():
        raise RuntimeError(f"{nct_id} has no eligibilityCriteria text; it is unusable here")
    return study


def main() -> int:
    """Fetch every configured study, write the snapshots, and refresh the checksums."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--timeout", type=float, default=60.0, help="per-request timeout in seconds"
    )
    args = parser.parse_args()

    TRIALS_DIR.mkdir(parents=True, exist_ok=True)
    # The ClinicalTrials.gov edge rejects unrecognised User-Agent strings with HTTP 403,
    # so the client's default identifier is left in place rather than branded.
    headers = {"Accept": "application/json"}
    total_bytes = 0

    with httpx.Client(headers=headers, timeout=args.timeout, follow_redirects=True) as client:
        version = fetch_json(client, VERSION_URL)
        write_json(
            TRIALS_DIR / "_api_version.json",
            {
                "retrieved_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                "source_url": VERSION_URL,
                "version": version,
            },
        )
        print(
            f"API {version.get('apiVersion')}, dataTimestamp {version.get('dataTimestamp')}\n"
        )

        for index, nct_id in enumerate(NCT_IDS, start=1):
            # One request at a time with a fixed pause; this dataset is tiny and there is
            # no reason to lean on a public endpoint any harder than that.
            if index > 1:
                time.sleep(REQUEST_DELAY_S)
            study = fetch_study(client, nct_id)
            written = write_json(TRIALS_DIR / f"{nct_id}.json", study)
            total_bytes += written
            criteria_chars = len(eligibility_criteria(study))
            print(
                f"[{index:2d}/{len(NCT_IDS)}] {nct_id}  "
                f"{written / 1024:7.1f} KiB  criteria {criteria_chars:5d} chars"
            )

    count = write_sha256sums()
    print(f"\n{len(NCT_IDS)} studies, {total_bytes / 1024:.1f} KiB")
    print(f"data/SHA256SUMS refreshed over {count} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
