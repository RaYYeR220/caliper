"""Write one Markdown chart summary per committed patient, for the annotators to work from.

These files are the annotation artifacts. A human labels a case by reading `eval/charts/{id}.md`,
so the file is committed next to the label it produced and a judge can see exactly what was in
front of the annotator. `caliper.chart.summarise` is byte-deterministic, which is what makes that
pairing hold: re-running this script on an unchanged bundle rewrites identical bytes.

DocumentReference notes are attached to the index here rather than in `caliper.fhir`, which returns
them separately. They are listed as dated pointers, never as clinical evidence — `PatientIndex`
keeps `kind="note"` rows out of every concept match — so a note can tell an annotator where to
look without deciding anything on its own.

Usage:
    python scripts/summarise_patients.py [--out eval/charts]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from _datalib import DATA_DIR, REPO_ROOT
from rich.console import Console
from rich.table import Table

from caliper.chart import summarise, summarise_dict
from caliper.fhir import load_patient_index, narrative_notes
from caliper.record import Evidence, PatientIndex

PATIENTS_DIR = DATA_DIR / "patients"
DEFAULT_OUT_DIR = REPO_ROOT / "eval" / "charts"

# The corpus was selected against this date and the trial criteria are read as of it, so every
# chart, every label and every screening run share one screening date.
SCREENING_DATE = date(2026, 6, 1)

NOT_A_BUNDLE = {"index.json", "PROVENANCE.json"}

# Synthea notes open with a bare date, then "# Chief Complaint" and a bulleted list. The bullets
# are the only part that differs between visits, so they are what the note is labelled with.
_NOTE_LABEL_LIMIT = 70
_COMPLAINT_HEADING = "chief complaint"


def bundle_paths() -> list[Path]:
    """Every committed patient bundle, in a stable order."""
    return sorted(path for path in PATIENTS_DIR.glob("*.json") if path.name not in NOT_A_BUNDLE)


def _note_label(text: str) -> str:
    """A one-line label for a note: its chief complaint, which is what varies between visits."""
    complaints: list[str] = []
    in_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            if in_section:
                break
            in_section = stripped.lstrip("#").strip().casefold() == _COMPLAINT_HEADING
        elif in_section and stripped:
            # Synthea writes the complaints as bullets, or as one bare "No complaints." line.
            complaints.append(stripped.lstrip("-").strip())
    if not complaints:
        return "clinical note"
    return f"chief complaint: {'; '.join(complaints)}"[:_NOTE_LABEL_LIMIT]


def load_with_notes(path: Path) -> PatientIndex:
    """Index one bundle and attach its decoded narrative notes as `kind="note"` rows."""
    bundle = json.loads(path.read_text(encoding="utf-8"))
    index = load_patient_index(bundle)
    for note in narrative_notes(bundle):
        index.evidence.append(
            Evidence(
                kind="note",
                resource_type="DocumentReference",
                resource_id=note.resource_id,
                display=_note_label(note.text),
                fhir_path=note.fhir_path,
                date=note.date,
                source="narrative",
                narrative_quote=note.text,
            )
        )
    return index


def write_chart(patient: PatientIndex, out_dir: Path) -> tuple[Path, int]:
    """Render one chart and write it; return the path and the number of bytes written."""
    text = summarise(patient, as_of=SCREENING_DATE)
    destination = out_dir / f"{patient.patient_id}.md"
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Binary mode: text mode would rewrite "\n" as "\r\n" on Windows and the artifact would
    # stop being byte-identical between platforms.
    destination.write_bytes(text.encode("utf-8"))
    return destination, len(text.encode("utf-8"))


def render_table(console: Console, rows: list[dict[str, object]]) -> None:
    table = Table(title=f"Chart summaries at {SCREENING_DATE.isoformat()} ({len(rows)} patients)")
    table.add_column("patient_id", overflow="fold", max_width=38)
    table.add_column("age", justify="right")
    table.add_column("sex")
    table.add_column("conditions", justify="right")
    table.add_column("analytes", justify="right")
    table.add_column("notes", justify="right")
    table.add_column("chars", justify="right")
    table.add_column("lines", justify="right")

    for row in rows:
        table.add_row(*(str(value) for value in row.values()))
    console.print(table)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help=f"directory to write the summaries into (default {DEFAULT_OUT_DIR})",
    )
    args = parser.parse_args()

    paths = bundle_paths()
    if not paths:
        print(f"no patient bundles found in {PATIENTS_DIR}", file=sys.stderr)
        return 1

    rows: list[dict[str, object]] = []
    total_bytes = 0
    for path in paths:
        patient = load_with_notes(path)
        summary = summarise_dict(patient, as_of=SCREENING_DATE)
        destination, written = write_chart(patient, args.out)
        total_bytes += written
        conditions = summary["conditions"]
        active = len(conditions["active"])
        demographics = summary["demographics"]
        rows.append(
            {
                "patient_id": patient.patient_id,
                "age": demographics["age_years"] if demographics["age_years"] is not None else "-",
                "sex": demographics["sex"] or "-",
                "conditions": f"{active}/{active + len(conditions['inactive'])}",
                "analytes": len(summary["analytes"]),
                "notes": len(summary["notes"]),
                "chars": written,
                "lines": destination.read_text(encoding="utf-8").count("\n"),
            }
        )

    render_table(Console(), rows)
    print(f"wrote {len(rows)} summaries to {args.out} ({total_bytes:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
