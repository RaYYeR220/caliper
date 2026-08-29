"""Build the committed synthetic-patient corpus from the Synthea sample dataset.

The upstream ``downloads/latest/`` path is mutable, so the archive is pinned to a commit
SHA resolved through the GitHub API and verified by SHA-256 before it is read. Each
selected FHIR Bundle is trimmed to the resource types an eligibility screener can
actually reason over, which removes roughly two thirds of the bytes without altering any
clinical content that remains.

Selection is a budgeted covering problem rather than a simple top-N. Synthea records grow
with the length of the simulated life, so the patients carrying the most evidence are also
the largest: chronic kidney disease only appears at the end of a long simulated life, and
its cheapest carrier is roughly 4 MB. The policy therefore reserves capacity for the
evidence dimensions the screener must be able to exercise -- each disease area, older
patients with a multi-decade history, each scarce laboratory code, and a quota of
deliberately sparse patients where the honest answer is "unknown" -- and only then spends
what is left on the best evidence-per-byte candidates.

Usage:
    python scripts/build_patient_corpus.py [--dry-run]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
from _datalib import CACHE_DIR, DATA_DIR, json_bytes, write_json, write_sha256sums
from rich.console import Console
from rich.table import Table

REPO = "synthetichealth/synthea-sample-data"
ARCHIVE_PATH = "downloads/latest/synthea_sample_data_fhir_latest.zip"
COMMITS_URL = f"https://api.github.com/repos/{REPO}/commits"
ARCHIVE_LICENSE = "Apache-2.0"
ARCHIVE_ATTRIBUTION = "Synthea synthetic patient generator, The MITRE Corporation"

PATIENTS_DIR = DATA_DIR / "patients"
ARCHIVE_CACHE = CACHE_DIR / "synthea_sample_data_fhir_latest.zip"

# Bumped whenever the scan extracts different facts, so a stale cache is never reused.
SCAN_SCHEMA = 3

# Resource types the screening engine can consume. Everything else in the Synthea
# bundles is billing, scheduling or provenance scaffolding.
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

LOINC_SYSTEM = "http://loinc.org"

# Age is evaluated against a fixed date so the corpus does not silently change meaning
# as wall-clock time passes.
AGE_REFERENCE_DATE = date(2026, 6, 1)
MIN_AGE = 18
MAX_AGE = 85

# Laboratory and vital-sign codes the target trial criteria key on. Platelets carry two
# codes: 777-3 is what Synthea actually emits, while 777-7 is retained so the panel still
# matches sources that use it.
SCREENING_PANEL: dict[str, tuple[str, ...]] = {
    "creatinine": ("2160-0", "38483-4"),
    "hba1c": ("4548-4",),
    "egfr": ("33914-3", "98979-8"),
    "glucose": ("2345-7",),
    "bmi": ("39156-5",),
    "systolic_bp": ("8480-6",),
    "hemoglobin": ("718-7",),
    "platelets": ("777-3", "777-7"),
}

TARGET_CONDITION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "asthma": ("asthma",),
    "ckd": ("chronic kidney disease", "renal failure", "end-stage renal", "renal disease"),
    "copd": ("chronic obstructive", "copd", "emphysema"),
    "diabetes": ("diabetes", "diabetic"),
    "heart_failure": ("heart failure", "cardiac failure"),
}

# SNOMED CT backstop, for codings that carry no display text.
TARGET_CONDITION_CODES: dict[str, frozenset[str]] = {
    "asthma": frozenset({"195967001", "233678006"}),
    "ckd": frozenset(
        {"431855005", "431856006", "433144002", "431857002", "46177005", "129721000119106"}
    ),
    "copd": frozenset({"185086009", "87433001"}),
    "diabetes": frozenset(
        {
            "44054006",
            "15777000",
            "368581000119106",
            "127013003",
            "90781000119102",
            "157141000119108",
            "1501000119109",
            "422034002",
            "4855003",
        }
    ),
    "heart_failure": frozenset({"84114007", "88805009", "42343007"}),
}

TARGET_COUNT = 24
SPARSE_QUOTA = 5

# The trial snapshots take roughly 4.2 MB of the 30 MB budget for data/.
MAX_PATIENT_BYTES = 25_500_000

# No single patient may be admitted as an anchor if it would eat this much of the budget.
# The cap exists to keep the 10-25 MB outliers out; the ~4 MB CKD carriers clear it.
ANCHOR_MAX_BUDGET_FRACTION = 0.25

# Minimum carriers per disease area. Two apiece for heart failure and COPD so that a
# single reshuffled patient cannot silently remove a whole trial's worth of cases.
MIN_DISEASE_CARRIERS: dict[str, int] = {
    "asthma": 1,
    "ckd": 1,
    "copd": 2,
    "diabetes": 1,
    "heart_failure": 2,
}

# Minimum carriers for the laboratory codes that are scarce in the sample dataset;
# the common vitals need no floor because nearly every patient has them.
MIN_PANEL_CARRIERS: dict[str, int] = {"creatinine": 4, "hba1c": 4, "egfr": 2, "glucose": 2}

# Several trials set minimumAge at or above 40, so the corpus needs older patients whose
# records actually span enough time to carry a chronic history.
SENIOR_MIN_AGE = 55
SENIOR_MIN_RECORD_YEARS = 20
MIN_SENIOR_CARRIERS = 3


@dataclass
class PatientSummary:
    """Raw screening-relevant facts about one candidate bundle, plus its committed size.

    Only extracted facts are stored. Everything policy-dependent (age bracket, disease
    match, panel coverage, score) is derived, so tuning the policy does not invalidate
    the on-disk scan cache.
    """

    patient_id: str
    member: str
    birth_date: str | None
    sex: str | None
    condition_displays: list[str]
    condition_codes: list[str]
    loinc_codes: list[str]
    n_encounters: int
    earliest_encounter_date: str | None
    latest_encounter_date: str | None
    trimmed_bytes: int
    entries_kept: int
    dropped_types: dict[str, int] = field(default_factory=dict)

    @property
    def age(self) -> int | None:
        """Age in whole years at :data:`AGE_REFERENCE_DATE`."""
        return _age_years(self.birth_date)

    @property
    def record_span_years(self) -> int:
        """Years between the first and last encounter, 0 if the history is unusable."""
        if not self.earliest_encounter_date or not self.latest_encounter_date:
            return 0
        return int(self.latest_encounter_date[:4]) - int(self.earliest_encounter_date[:4])

    @property
    def is_senior_with_history(self) -> bool:
        """Whether the patient is older and carries a genuinely multi-decade record."""
        age = self.age
        return (
            age is not None
            and age >= SENIOR_MIN_AGE
            and self.record_span_years >= SENIOR_MIN_RECORD_YEARS
        )

    @property
    def is_adult(self) -> bool:
        """Whether the patient falls in the adult bracket most trials recruit from."""
        age = self.age
        return age is not None and MIN_AGE <= age <= MAX_AGE

    @property
    def target_conditions(self) -> list[str]:
        """Which of the five target disease areas this patient's conditions cover."""
        lowered = [display.lower() for display in self.condition_displays]
        codes = set(self.condition_codes)
        matched = {
            category
            for category, keywords in TARGET_CONDITION_KEYWORDS.items()
            if any(keyword in text for text in lowered for keyword in keywords)
        }
        matched |= {
            category
            for category, category_codes in TARGET_CONDITION_CODES.items()
            if codes & category_codes
        }
        return sorted(matched)

    @property
    def panel_present(self) -> list[str]:
        """Screening panel entries for which this patient has at least one Observation."""
        codes = set(self.loinc_codes)
        return sorted(name for name, panel in SCREENING_PANEL.items() if codes.intersection(panel))

    @property
    def score(self) -> int:
        """Number of screening features present, out of ten."""
        return int(self.is_adult) + int(bool(self.target_conditions)) + len(self.panel_present)


@dataclass(frozen=True)
class Selection:
    """A chosen patient together with the reason it earned a place in the corpus."""

    summary: PatientSummary
    reason: str


def _age_years(birth_date: str | None) -> int | None:
    if not birth_date:
        return None
    try:
        born = date.fromisoformat(birth_date[:10])
    except ValueError:
        return None
    reference = AGE_REFERENCE_DATE
    had_birthday = (reference.month, reference.day) >= (born.month, born.day)
    return reference.year - born.year - (0 if had_birthday else 1)


def resolve_pinned_commit(client: httpx.Client) -> dict[str, str]:
    """Return the newest commit that touched the archive, so the download can be pinned."""
    response = client.get(COMMITS_URL, params={"path": ARCHIVE_PATH, "per_page": 1})
    response.raise_for_status()
    commits = response.json()
    if not commits:
        raise RuntimeError(f"no commit history for {ARCHIVE_PATH} in {REPO}")
    commit = commits[0]
    return {"sha": commit["sha"], "date": commit["commit"]["committer"]["date"]}


def download_archive(client: httpx.Client, sha: str) -> tuple[Path, str, int]:
    """Download the pinned archive into the cache; return its path, digest and size."""
    url = f"https://raw.githubusercontent.com/{REPO}/{sha}/{ARCHIVE_PATH}"
    if not ARCHIVE_CACHE.exists():
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        partial = ARCHIVE_CACHE.with_suffix(".part")
        print(f"downloading {url}")
        with client.stream("GET", url, timeout=300.0) as response:
            response.raise_for_status()
            with partial.open("wb") as handle:
                for chunk in response.iter_bytes(1 << 20):
                    handle.write(chunk)
        # Rename only once the body is complete, so an interrupted run cannot leave a
        # truncated archive that a later run would happily treat as cached.
        partial.replace(ARCHIVE_CACHE)
    else:
        print(f"using cached archive {ARCHIVE_CACHE}")

    digest = hashlib.sha256()
    with ARCHIVE_CACHE.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return ARCHIVE_CACHE, digest.hexdigest(), ARCHIVE_CACHE.stat().st_size


def trim_bundle(bundle: dict[str, Any]) -> tuple[dict[str, Any], Counter[str]]:
    """Drop every entry outside the allow-list; return the trimmed bundle and what went.

    Bundle-level fields are preserved verbatim and kept entries are copied unchanged, so
    references from a kept resource to a dropped one (an Encounter naming its
    Organization, for instance) remain present but unresolvable within the corpus.
    """
    dropped: Counter[str] = Counter()
    kept_entries = []
    for entry in bundle.get("entry", []):
        resource_type = entry.get("resource", {}).get("resourceType")
        if resource_type in ALLOWED_RESOURCE_TYPES:
            kept_entries.append(entry)
        else:
            dropped[resource_type or "<unknown>"] += 1
    return {**bundle, "entry": kept_entries}, dropped


def _codings(concept: dict[str, Any]) -> list[dict[str, Any]]:
    return concept.get("coding") or []


def _observation_loinc_codes(resource: dict[str, Any]) -> set[str]:
    """Collect LOINC codes from an Observation, including any panel components.

    Component codes are collected for every Observation, not just for the case that
    exposed the problem: Synthea emits blood pressure as an 85354-9 panel whose systolic
    reading exists only as a component, so a top-level-code-only scan misses 8480-6 in
    every patient. Any panel dimension can be published this way, so both levels are
    always read.
    """
    codes: set[str] = set()
    concepts = [resource.get("code", {})]
    concepts += [component.get("code", {}) for component in resource.get("component") or []]
    for concept in concepts:
        for coding in _codings(concept):
            if coding.get("system") == LOINC_SYSTEM and coding.get("code"):
                codes.add(coding["code"])
    return codes


def _condition_labels(resource: dict[str, Any]) -> tuple[set[str], set[str]]:
    """Return the display strings and raw codes carried by a Condition."""
    concept = resource.get("code", {})
    displays = {coding["display"] for coding in _codings(concept) if coding.get("display")}
    if concept.get("text"):
        displays.add(concept["text"])
    codes = {coding["code"] for coding in _codings(concept) if coding.get("code")}
    return displays, codes


def summarise(bundle: dict[str, Any], member: str, trimmed_bytes: int) -> PatientSummary | None:
    """Summarise a trimmed bundle, or return ``None`` if it is not a single-patient record."""
    patients = [
        entry["resource"]
        for entry in bundle.get("entry", [])
        if entry.get("resource", {}).get("resourceType") == "Patient"
    ]
    if len(patients) != 1:
        return None
    patient = patients[0]

    displays: set[str] = set()
    condition_codes: set[str] = set()
    loinc_codes: set[str] = set()
    encounter_dates: list[str] = []
    n_encounters = 0

    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        match resource.get("resourceType"):
            case "Condition":
                entry_displays, entry_codes = _condition_labels(resource)
                displays |= entry_displays
                condition_codes |= entry_codes
            case "Observation":
                loinc_codes |= _observation_loinc_codes(resource)
            case "Encounter":
                n_encounters += 1
                period = resource.get("period", {})
                stamp = period.get("end") or period.get("start")
                if stamp:
                    encounter_dates.append(stamp[:10])

    return PatientSummary(
        patient_id=patient["id"],
        member=member,
        birth_date=patient.get("birthDate"),
        sex=patient.get("gender"),
        condition_displays=sorted(displays),
        condition_codes=sorted(condition_codes),
        loinc_codes=sorted(loinc_codes),
        n_encounters=n_encounters,
        earliest_encounter_date=min(encounter_dates) if encounter_dates else None,
        latest_encounter_date=max(encounter_dates) if encounter_dates else None,
        trimmed_bytes=trimmed_bytes,
        entries_kept=len(bundle.get("entry", [])),
    )


def scan_archive(archive: Path) -> list[PatientSummary]:
    """Parse, trim and summarise every patient bundle in the archive."""
    summaries: list[PatientSummary] = []
    with zipfile.ZipFile(archive) as zf:
        members = sorted(name for name in zf.namelist() if name.endswith(".json"))
        for index, member in enumerate(members, start=1):
            bundle = json.loads(zf.read(member))
            if bundle.get("resourceType") != "Bundle":
                continue
            trimmed, dropped = trim_bundle(bundle)
            summary = summarise(trimmed, member, len(json_bytes(trimmed)))
            if summary is None:
                # hospitalInformation / practitionerInformation carry no Patient resource.
                continue
            summary.dropped_types = dict(dropped)
            summaries.append(summary)
            # Member names carry accented characters a legacy console cannot encode, so
            # progress is reported as a plain counter.
            print(f"  scanned {index:3d}/{len(members)}", end="\r")
    print(f"  scanned {len(members)} members")
    return summaries


def load_or_build_scan(archive: Path, archive_sha256: str, refresh: bool) -> list[PatientSummary]:
    """Return archive summaries, memoised on disk against the archive digest."""
    cache_file = CACHE_DIR / f"scan-v{SCAN_SCHEMA}-{archive_sha256[:16]}.json"
    if cache_file.exists() and not refresh:
        print(f"reusing scan cache {cache_file.name}")
        return [PatientSummary(**row) for row in json.loads(cache_file.read_text("utf-8"))]
    print("scanning archive (this parses roughly 386 MB of JSON)")
    summaries = scan_archive(archive)
    cache_file.write_text(json.dumps([asdict(summary) for summary in summaries]), encoding="utf-8")
    return summaries


def _by_evidence_density(summary: PatientSummary) -> tuple[float, str]:
    """Rank by screening features per byte, so the budget buys the most evidence."""
    return (-summary.score / summary.trimmed_bytes, summary.patient_id)


def _by_sparseness(summary: PatientSummary) -> tuple[int, int, str]:
    return (summary.score, summary.trimmed_bytes, summary.patient_id)


def select_patients(summaries: list[PatientSummary]) -> tuple[list[Selection], list[str]]:
    """Choose the corpus under a byte budget; return the selection and any unmet quota.

    Reservations are made in order of how hard they are to satisfy later: the sparse
    quota first (it is cheap), then the disease carriers, then older patients with a
    multi-decade history, then the floors for scarce laboratory codes, and finally a
    density-ranked fill. Anchors larger than :data:`ANCHOR_MAX_BUDGET_FRACTION` of the
    budget are passed over, which keeps the 10-25 MB outliers out of the corpus.

    A quota the sample cannot satisfy is reported rather than silently dropped, because
    an eval that is missing a disease area should say so out loud.
    """
    budget = MAX_PATIENT_BYTES
    anchor_cap = int(MAX_PATIENT_BYTES * ANCHOR_MAX_BUDGET_FRACTION)
    chosen: dict[str, Selection] = {}
    unmet: list[str] = []

    def spend(summary: PatientSummary, reason: str) -> bool:
        nonlocal budget
        if summary.patient_id in chosen or summary.trimmed_bytes > budget:
            return False
        chosen[summary.patient_id] = Selection(summary, reason)
        budget -= summary.trimmed_bytes
        return True

    def satisfy(predicate: Callable[[PatientSummary], bool], label: str, needed: int) -> None:
        have = sum(1 for pick in chosen.values() if predicate(pick.summary))
        candidates: Iterable[PatientSummary] = sorted(summaries, key=_by_evidence_density)
        for summary in candidates:
            if have >= needed:
                break
            if not predicate(summary) or summary.trimmed_bytes > anchor_cap:
                continue
            if spend(summary, label):
                have += 1
        if have < needed:
            unmet.append(f"{label}: {have}/{needed}")

    for summary in sorted(summaries, key=_by_sparseness)[:SPARSE_QUOTA]:
        spend(summary, "sparse")

    for disease, needed in MIN_DISEASE_CARRIERS.items():
        satisfy(lambda s, d=disease: d in s.target_conditions, f"condition:{disease}", needed)

    satisfy(lambda s: s.is_senior_with_history, "senior_history", MIN_SENIOR_CARRIERS)

    for panel_name, needed in MIN_PANEL_CARRIERS.items():
        satisfy(lambda s, n=panel_name: n in s.panel_present, f"lab:{panel_name}", needed)

    for summary in sorted(summaries, key=_by_evidence_density):
        if len(chosen) >= TARGET_COUNT:
            break
        spend(summary, "fill")

    ordered = sorted(
        chosen.values(), key=lambda pick: (-pick.summary.score, pick.summary.patient_id)
    )
    return ordered, unmet


def render_selection(console: Console, picks: list[Selection]) -> None:
    """Print the selection table."""
    table = Table(title=f"Selected patient corpus ({len(picks)} bundles)")
    table.add_column("patient_id", overflow="fold", max_width=38)
    table.add_column("sex")
    table.add_column("age", justify="right")
    table.add_column("score", justify="right")
    table.add_column("target conditions")
    table.add_column("panel", justify="right")
    table.add_column("enc", justify="right")
    table.add_column("span", justify="right")
    table.add_column("latest")
    table.add_column("KiB", justify="right")
    table.add_column("selected as")

    for pick in picks:
        summary = pick.summary
        age = summary.age
        table.add_row(
            summary.patient_id,
            summary.sex or "-",
            "-" if age is None else str(age),
            f"{summary.score}/10",
            ", ".join(summary.target_conditions) or "-",
            f"{len(summary.panel_present)}/{len(SCREENING_PANEL)}",
            str(summary.n_encounters),
            f"{summary.record_span_years}y",
            summary.latest_encounter_date or "-",
            f"{summary.trimmed_bytes / 1024:.0f}",
            pick.reason,
        )
    console.print(table)


def write_corpus(archive: Path, picks: list[Selection]) -> tuple[int, Counter[str]]:
    """Write the trimmed bundles for the selected patients; return bytes and dropped types."""
    dropped_total: Counter[str] = Counter()
    total_bytes = 0
    with zipfile.ZipFile(archive) as zf:
        for pick in picks:
            trimmed, dropped = trim_bundle(json.loads(zf.read(pick.summary.member)))
            dropped_total += dropped
            total_bytes += write_json(PATIENTS_DIR / f"{pick.summary.patient_id}.json", trimmed)
    return total_bytes, dropped_total


def build_index(picks: list[Selection]) -> dict[str, Any]:
    """Build the human-readable manifest for ``data/patients/index.json``."""
    return {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "age_reference_date": AGE_REFERENCE_DATE.isoformat(),
        "screening_panel_loinc": {name: list(codes) for name, codes in SCREENING_PANEL.items()},
        "patients": [
            {
                "id": pick.summary.patient_id,
                "file": f"{pick.summary.patient_id}.json",
                "birth_date": pick.summary.birth_date,
                "sex": pick.summary.sex,
                "condition_display_list": pick.summary.condition_displays,
                "observation_loinc_codes_present": pick.summary.loinc_codes,
                "n_encounters": pick.summary.n_encounters,
                "latest_encounter_date": pick.summary.latest_encounter_date,
            }
            for pick in sorted(picks, key=lambda p: p.summary.patient_id)
        ],
    }


def build_provenance(
    commit: dict[str, str],
    archive_sha256: str,
    archive_bytes: int,
    candidates: int,
    picks: list[Selection],
    unmet: list[str],
    corpus_bytes: int,
    dropped_total: Counter[str],
) -> dict[str, Any]:
    """Build the provenance record for ``data/patients/PROVENANCE.json``."""
    return {
        "retrieved_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": {
            "repository": f"https://github.com/{REPO}",
            "path_in_repository": ARCHIVE_PATH,
            "pinned_commit_sha": commit["sha"],
            "pinned_commit_date": commit["date"],
            "download_url": (
                f"https://raw.githubusercontent.com/{REPO}/{commit['sha']}/{ARCHIVE_PATH}"
            ),
            "archive_sha256": archive_sha256,
            "archive_bytes": archive_bytes,
            "license": ARCHIVE_LICENSE,
            "attribution": ARCHIVE_ATTRIBUTION,
            "contains_phi": False,
        },
        "selection": {
            "age_reference_date": AGE_REFERENCE_DATE.isoformat(),
            "adult_age_range": [MIN_AGE, MAX_AGE],
            "candidate_bundles": candidates,
            "selected_bundles": len(picks),
            "target_count": TARGET_COUNT,
            "sparse_quota": SPARSE_QUOTA,
            "byte_budget": MAX_PATIENT_BYTES,
            "anchor_max_budget_fraction": ANCHOR_MAX_BUDGET_FRACTION,
            "min_disease_carriers": MIN_DISEASE_CARRIERS,
            "min_panel_carriers": MIN_PANEL_CARRIERS,
            "senior_quota": {
                "min_age": SENIOR_MIN_AGE,
                "min_record_span_years": SENIOR_MIN_RECORD_YEARS,
                "min_carriers": MIN_SENIOR_CARRIERS,
            },
            "corpus_bytes": corpus_bytes,
            "unmet_quotas": unmet,
            "screening_panel_loinc": {name: list(codes) for name, codes in SCREENING_PANEL.items()},
            "reasons": {pick.summary.patient_id: pick.reason for pick in picks},
        },
        "modifications": {
            "reserialised": "UTF-8, two-space indent, sorted object keys, LF newlines",
            "kept_resource_types": sorted(ALLOWED_RESOURCE_TYPES),
            "removed_resource_types": dict(sorted(dropped_total.items())),
            "removed_entry_count": sum(dropped_total.values()),
            "kept_entry_count": sum(pick.summary.entries_kept for pick in picks),
            "note": (
                "Entries outside the allow-list were removed wholesale. Retained resources "
                "are unchanged in content, but references from them to removed resources "
                "are no longer resolvable within this corpus."
            ),
        },
    }


def main() -> int:
    """Resolve the pinned archive, select the corpus, and write it under ``data/``."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="score and print the selection without writing"
    )
    parser.add_argument("--refresh-scan", action="store_true", help="ignore the on-disk scan cache")
    args = parser.parse_args()

    console = Console()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        commit = resolve_pinned_commit(client)
        print(f"pinned commit {commit['sha']} ({commit['date']})")
        archive, archive_sha256, archive_bytes = download_archive(client, commit["sha"])
    print(f"archive {archive_bytes:,} bytes  sha256 {archive_sha256}")

    summaries = load_or_build_scan(archive, archive_sha256, args.refresh_scan)
    print(f"{len(summaries)} candidate patient bundles")

    picks, unmet = select_patients(summaries)
    render_selection(console, picks)
    projected = sum(pick.summary.trimmed_bytes for pick in picks)
    print(f"projected corpus size {projected:,} bytes")
    if unmet:
        print(f"unmet quotas (no affordable candidate): {', '.join(unmet)}")

    if args.dry_run:
        return 0

    PATIENTS_DIR.mkdir(parents=True, exist_ok=True)
    for stale in PATIENTS_DIR.glob("*.json"):
        stale.unlink()

    corpus_bytes, dropped_total = write_corpus(archive, picks)
    write_json(PATIENTS_DIR / "index.json", build_index(picks))
    write_json(
        PATIENTS_DIR / "PROVENANCE.json",
        build_provenance(
            commit,
            archive_sha256,
            archive_bytes,
            len(summaries),
            picks,
            unmet,
            corpus_bytes,
            dropped_total,
        ),
    )

    count = write_sha256sums()
    data_bytes = sum(path.stat().st_size for path in DATA_DIR.rglob("*") if path.is_file())
    print(f"wrote {len(picks)} bundles, {corpus_bytes:,} bytes")
    print(f"removed {sum(dropped_total.values()):,} entries across {len(dropped_total)} types")
    print(f"data/SHA256SUMS refreshed over {count} files")
    print(f"total committed data/ size {data_bytes:,} bytes ({data_bytes / 1e6:.2f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
