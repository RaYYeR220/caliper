"""Integrity checks for the committed data fixtures.

These tests are the contract between the build scripts in ``scripts/`` and everything that
consumes ``data/``. They assert that the tree on disk is exactly the tree that was built:
digests match, every trial snapshot carries usable eligibility text, every patient bundle
is a single-patient bundle limited to the agreed resource types, and the manifest and the
directory agree with each other.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TRIALS_DIR = DATA_DIR / "trials"
PATIENTS_DIR = DATA_DIR / "patients"
CHECKSUM_FILE = DATA_DIR / "SHA256SUMS"

# Mirrors ALLOWED_RESOURCE_TYPES in scripts/build_patient_corpus.py. It is duplicated on
# purpose: the test must fail if the script's allow-list is widened without review.
ALLOWED_RESOURCE_TYPES = frozenset(
    {
        "AllergyIntolerance",
        "Condition",
        "DocumentReference",
        "Encounter",
        "Immunization",
        "MedicationRequest",
        "Observation",
        "Patient",
        "Procedure",
    }
)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _checksum_entries() -> list[tuple[str, str]]:
    """Parse ``data/SHA256SUMS`` into (digest, relative path) pairs."""
    lines = CHECKSUM_FILE.read_text(encoding="utf-8").splitlines()
    entries = []
    for line in lines:
        if not line.strip():
            continue
        digest, _, relative_path = line.partition("  ")
        entries.append((digest, relative_path))
    return entries


def _patient_bundle_paths() -> list[Path]:
    """Every committed patient bundle, excluding the manifest and provenance files."""
    return sorted(
        path
        for path in PATIENTS_DIR.glob("*.json")
        if path.name not in {"index.json", "PROVENANCE.json"}
    )


def _trial_paths() -> list[Path]:
    """Every committed trial snapshot, excluding the API version record."""
    return sorted(path for path in TRIALS_DIR.glob("*.json") if not path.name.startswith("_"))


CHECKSUM_ENTRIES = _checksum_entries()
PATIENT_PATHS = _patient_bundle_paths()
TRIAL_PATHS = _trial_paths()


def test_checksum_file_is_not_empty() -> None:
    assert CHECKSUM_ENTRIES, "data/SHA256SUMS is empty"


@pytest.mark.parametrize(
    ("digest", "relative_path"),
    CHECKSUM_ENTRIES,
    ids=[relative_path for _, relative_path in CHECKSUM_ENTRIES],
)
def test_checksum_matches(digest: str, relative_path: str) -> None:
    """Every file listed in SHA256SUMS exists and hashes to the recorded digest."""
    path = DATA_DIR / relative_path
    assert path.is_file(), f"{relative_path} is listed in SHA256SUMS but missing"
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    assert actual == digest, f"{relative_path} content does not match its recorded digest"


def test_checksums_cover_every_data_file() -> None:
    """SHA256SUMS covers the whole tree, so a stray or forgotten file cannot slip in."""
    listed = {relative_path for _, relative_path in CHECKSUM_ENTRIES}
    present = {
        path.relative_to(DATA_DIR).as_posix()
        for path in DATA_DIR.rglob("*")
        if path.is_file() and path != CHECKSUM_FILE
    }
    assert listed == present


def test_trial_snapshots_exist() -> None:
    assert TRIAL_PATHS, "no trial snapshots committed"


@pytest.mark.parametrize("path", TRIAL_PATHS, ids=[path.stem for path in TRIAL_PATHS])
def test_trial_has_eligibility_criteria(path: Path) -> None:
    """Every trial parses and carries non-empty free-text eligibility criteria."""
    study = _load_json(path)
    protocol = study["protocolSection"]
    assert protocol["identificationModule"]["nctId"] == path.stem
    criteria = protocol["eligibilityModule"]["eligibilityCriteria"]
    assert criteria.strip(), f"{path.name} has empty eligibilityCriteria"


def test_api_version_record_is_present() -> None:
    """The snapshot is citable only if the API data timestamp was captured with it."""
    record = _load_json(TRIALS_DIR / "_api_version.json")
    assert record["version"]["dataTimestamp"]
    assert record["version"]["apiVersion"]
    assert record["retrieved_utc"]


def test_patient_bundles_exist() -> None:
    assert PATIENT_PATHS, "no patient bundles committed"


@pytest.mark.parametrize("path", PATIENT_PATHS, ids=[path.stem for path in PATIENT_PATHS])
def test_patient_bundle_shape(path: Path) -> None:
    """Each bundle parses, is a Bundle, holds exactly one Patient, and is trimmed."""
    bundle = _load_json(path)
    assert bundle["resourceType"] == "Bundle"

    resource_types = [entry["resource"]["resourceType"] for entry in bundle["entry"]]
    assert resource_types.count("Patient") == 1, "a bundle must describe exactly one patient"

    disallowed = sorted(set(resource_types) - ALLOWED_RESOURCE_TYPES)
    assert not disallowed, f"{path.name} contains disallowed resource types: {disallowed}"

    patient = next(
        entry["resource"]
        for entry in bundle["entry"]
        if entry["resource"]["resourceType"] == "Patient"
    )
    assert patient["id"] == path.stem, "file name must be the Patient resource id"


def test_index_covers_exactly_the_committed_bundles() -> None:
    """The manifest and the directory listing must agree in both directions."""
    index = _load_json(PATIENTS_DIR / "index.json")
    listed_files = {entry["file"] for entry in index["patients"]}
    present_files = {path.name for path in PATIENT_PATHS}
    assert listed_files == present_files

    listed_ids = {entry["id"] for entry in index["patients"]}
    assert listed_ids == {path.stem for path in PATIENT_PATHS}
    assert len(index["patients"]) == len(PATIENT_PATHS), "duplicate entries in index.json"


@pytest.mark.parametrize("path", PATIENT_PATHS, ids=[path.stem for path in PATIENT_PATHS])
def test_index_entry_is_complete(path: Path) -> None:
    """Every manifest entry carries the fields a consumer is promised."""
    index = _load_json(PATIENTS_DIR / "index.json")
    entry = next(item for item in index["patients"] if item["id"] == path.stem)
    for key in (
        "id",
        "file",
        "birth_date",
        "sex",
        "condition_display_list",
        "observation_loinc_codes_present",
        "n_encounters",
        "latest_encounter_date",
    ):
        assert key in entry, f"index entry for {path.stem} is missing {key}"
    assert isinstance(entry["condition_display_list"], list)
    assert isinstance(entry["observation_loinc_codes_present"], list)
    assert isinstance(entry["n_encounters"], int)


def test_provenance_records_the_pinned_source() -> None:
    """Provenance must pin an immutable source and declare what trimming removed."""
    provenance = _load_json(PATIENTS_DIR / "PROVENANCE.json")
    source = provenance["source"]
    assert len(source["pinned_commit_sha"]) == 40
    assert len(source["archive_sha256"]) == 64
    assert source["pinned_commit_sha"] in source["download_url"]
    assert source["license"] == "Apache-2.0"
    assert source["contains_phi"] is False

    modifications = provenance["modifications"]
    assert sorted(modifications["kept_resource_types"]) == sorted(ALLOWED_RESOURCE_TYPES)
    assert modifications["removed_resource_types"], "trimming removed nothing; declare it"
    assert not set(modifications["removed_resource_types"]) & ALLOWED_RESOURCE_TYPES
