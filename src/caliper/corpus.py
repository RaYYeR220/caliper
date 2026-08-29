"""Reading the committed fixtures.

Both corpora are frozen files in the repository rather than live calls, so that a run in six
months' time answers the same question as a run today. `verify_digests` is what a reviewer runs
first: if it passes, every number in the report was produced from exactly these bytes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from caliper.fhir import load_patient_index
from caliper.record import PatientIndex

DATA_ROOT = Path(__file__).resolve().parents[2] / "data"


@dataclass(frozen=True)
class Trial:
    nct_id: str
    title: str
    criteria_text: str
    minimum_age: str | None = None
    maximum_age: str | None = None
    sex: str | None = None

    @property
    def short_title(self) -> str:
        return self.title if len(self.title) <= 90 else self.title[:87] + "..."


def trial_ids(root: Path = DATA_ROOT) -> list[str]:
    return sorted(p.stem for p in (root / "trials").glob("NCT*.json"))


def load_trial(nct_id: str, root: Path = DATA_ROOT) -> Trial:
    payload = json.loads((root / "trials" / f"{nct_id}.json").read_text(encoding="utf-8"))
    protocol = payload["protocolSection"]
    eligibility = protocol.get("eligibilityModule", {})
    identification = protocol.get("identificationModule", {})
    return Trial(
        nct_id=nct_id,
        title=identification.get("briefTitle") or identification.get("officialTitle") or nct_id,
        criteria_text=eligibility.get("eligibilityCriteria", ""),
        minimum_age=eligibility.get("minimumAge"),
        maximum_age=eligibility.get("maximumAge"),
        sex=eligibility.get("sex"),
    )


def patient_ids(root: Path = DATA_ROOT) -> list[str]:
    index = json.loads((root / "patients" / "index.json").read_text(encoding="utf-8"))
    entries = index["patients"] if isinstance(index, dict) else index
    return sorted(entry["id"] for entry in entries)


def load_patient(patient_id: str, root: Path = DATA_ROOT) -> PatientIndex:
    bundle = json.loads((root / "patients" / f"{patient_id}.json").read_text(encoding="utf-8"))
    return load_patient_index(bundle)


@dataclass(frozen=True)
class DigestReport:
    checked: int
    mismatched: tuple[str, ...]
    missing: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.mismatched and not self.missing


def verify_digests(root: Path = DATA_ROOT) -> DigestReport:
    """Confirm every file listed in `data/SHA256SUMS` is present and unchanged."""
    listing = (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    mismatched: list[str] = []
    missing: list[str] = []
    checked = 0

    for line in listing:
        if not line.strip():
            continue
        expected, _, name = line.partition("  ")
        path = root / name.strip()
        if not path.is_file():
            missing.append(name.strip())
            continue
        checked += 1
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected.strip():
            mismatched.append(name.strip())

    return DigestReport(checked=checked, mismatched=tuple(mismatched), missing=tuple(missing))


def default_screening_date() -> date:
    """Fixed so that two runs a month apart compute the same ages and the same windows."""
    return date(2026, 6, 1)
