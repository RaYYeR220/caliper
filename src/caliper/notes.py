"""Hand-authored clinical notes, loaded from beside the bundles rather than from inside them.

The notes live outside `data/patients/` on purpose. Those bundles are checksummed Synthea output,
declared byte-for-byte in `data/DATA_SOURCE.md` and verified on every test run, so hand-written
prose cannot be added to them without making that declaration false and blurring the line between
what a generator produced and what a human wrote. The notes are kept in their own tree, and
merged into a `PatientIndex` explicitly by `attach_notes` — one call, in one place, that a reader
can find.

The same reasoning decides what a note's `fhir_path` says. `Bundle.entry[n].resource` would be a
citation to an entry that does not exist; a coordinator following it would find nothing. A note
therefore cites the file and the note id it actually came from:

    data/notes/8d91c36a-1f7e-3842-9f14-8d567ed9cdcd.json#8d91c36a-hf-2015-04-22

`resolve_note_pointer` reads that pointer back and returns the note, which is the property tests
assert and the reason the format is worth having.

A note row is `kind="note"` and `source="narrative"`, carries the full text in `narrative_quote`,
and carries no codes. It can therefore never resolve a criterion on its own: `record.py` refuses
to match a narrative row by wording. Getting a coded row out of a note is the extractor's job.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from caliper.record import Evidence, PatientIndex

DEFAULT_NOTES_ROOT = Path("data/notes")

RESOURCE_TYPE = "ClinicalNote"
"""What a note calls itself in a citation. Deliberately not `DocumentReference`: these notes are
not FHIR resources and are not in any bundle, and saying otherwise would send a reader looking."""

POINTER_SEPARATOR = "#"

_REQUIRED_FIELDS = ("note_id", "date", "type", "author_role", "text")


class NotesError(ValueError):
    """A notes file exists but cannot be read as notes.

    Distinct from a missing file, which is a legitimate answer — most patients have no notes.
    A file that is present and malformed is a mistake in hand-authored data, and hiding it would
    hide a typo in the corpus the extractor is scored against.
    """


@dataclass(frozen=True)
class NotePointer:
    """The two halves of a note citation: which file, and which note inside it."""

    path: Path
    note_id: str


def note_pointer(path: Path, note_id: str) -> str:
    """The citation string for one note."""
    return f"{path.as_posix()}{POINTER_SEPARATOR}{note_id}"


def parse_note_pointer(pointer: str) -> NotePointer:
    """Split a citation back into a file and a note id."""
    file_part, separator, note_id = pointer.rpartition(POINTER_SEPARATOR)
    if not separator or not file_part or not note_id:
        raise NotesError(f"not a note pointer: {pointer!r}")
    return NotePointer(path=Path(file_part), note_id=note_id)


def resolve_note_pointer(pointer: str) -> dict[str, Any] | None:
    """The note a citation names, or None when nothing is there to open."""
    target = parse_note_pointer(pointer)
    try:
        notes = _read(target.path)
    except FileNotFoundError:
        return None
    found = next((note for note in notes if note["note_id"] == target.note_id), None)
    return dict(found) if found is not None else None


def load_notes(patient_id: str, root: Path = DEFAULT_NOTES_ROOT) -> list[Evidence]:
    """Every hand-authored note for one patient, oldest first.

    A patient with no notes file has no notes, which is the common case and not an error. The
    ordering is by date and then id so that two runs over the same tree produce byte-identical
    evidence, whatever order the file happens to list its notes in.
    """
    path = Path(root) / f"{patient_id}.json"
    try:
        notes = _read(path)
    except FileNotFoundError:
        return []

    rows = [_row(path, note) for note in notes]
    return sorted(rows, key=lambda e: (e.date or date.min, e.resource_id))


def attach_notes(patient: PatientIndex, root: Path = DEFAULT_NOTES_ROOT) -> PatientIndex:
    """A copy of `patient` with its notes merged in. The original is not touched.

    Merging is idempotent: a note already cited in the index is not added again, so a caller who
    attaches twice gets one copy rather than two rows a coordinator would have to reconcile.
    """
    cited = {e.fhir_path for e in patient.evidence}
    fresh = [row for row in load_notes(patient.patient_id, root) if row.fhir_path not in cited]
    return PatientIndex(
        patient_id=patient.patient_id,
        birth_date=patient.birth_date,
        sex=patient.sex,
        evidence=[*patient.evidence, *fresh],
    )


def _read(path: Path) -> Sequence[Mapping[str, Any]]:
    """The notes in one file, validated far enough that `_row` cannot produce a half-note."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise NotesError(f"{path} is not valid JSON: {exc}") from exc

    if not isinstance(payload, list):
        raise NotesError(f"{path} must hold a list of notes, found {type(payload).__name__}")

    seen: set[str] = set()
    for position, note in enumerate(payload):
        if not isinstance(note, Mapping):
            raise NotesError(f"{path}[{position}] is not a note object")
        missing = [field for field in _REQUIRED_FIELDS if not str(note.get(field, "")).strip()]
        if missing:
            raise NotesError(f"{path}[{position}] is missing {', '.join(missing)}")
        note_id = str(note["note_id"])
        if note_id in seen:
            raise NotesError(f"{path} uses the note id {note_id!r} twice")
        seen.add(note_id)
    return payload


def _row(path: Path, note: Mapping[str, Any]) -> Evidence:
    return Evidence(
        kind="note",
        resource_type=RESOURCE_TYPE,
        resource_id=str(note["note_id"]),
        display=str(note["type"]),
        fhir_path=note_pointer(path, str(note["note_id"])),
        date=_parse_date(note["date"]),
        source="narrative",
        narrative_quote=str(note["text"]),
    )


def _parse_date(value: Any) -> date | None:
    """A note's date, or None if it was not written as one. Partial dates invent precision."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.strip()).date()
    except ValueError:
        return None
