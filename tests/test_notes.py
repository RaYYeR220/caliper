"""Loading hand-authored notes, and keeping the ground truth honest.

Two jobs live here. The first is `caliper.notes`: notes are merged into a `PatientIndex` from
outside the checksummed bundles, deterministically, with a pointer that resolves back to the file
and note id a coordinator would open.

The second is the corpus itself. `data/notes/manifest.json` is what the extractor's evaluation is
scored against, so a quote in it that has drifted from the note it claims to come from would score
the extractor against fiction. Every quote is therefore re-checked against its note on every run.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from caliper.notes import (
    NotesError,
    attach_notes,
    load_notes,
    note_pointer,
    parse_note_pointer,
    resolve_note_pointer,
)
from caliper.record import Evidence, PatientIndex

REPO = Path(__file__).resolve().parent.parent
NOTES_DIR = REPO / "data" / "notes"
PATIENT_INDEX = REPO / "data" / "patients" / "index.json"

REQUIRED_PHENOMENA = (
    "asserted",
    "denial",
    "family_history",
    "hypothetical",
    "historical",
    "uncertain",
    "other_subject",
    "other_organ_system",
    "numeric_in_prose",
)


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


MANIFEST = _load(NOTES_DIR / "manifest.json")
NOTE_FILES = sorted(p for p in NOTES_DIR.glob("*.json") if p.name != "manifest.json")
CORPUS = {path.stem: _load(path) for path in NOTE_FILES}
MANIFEST_ROWS = MANIFEST["notes"]


def a_patient(patient_id: str = "p-1") -> PatientIndex:
    return PatientIndex(
        patient_id=patient_id,
        birth_date=date(1970, 1, 1),
        sex="female",
        evidence=[
            Evidence(
                kind="condition",
                resource_type="Condition",
                resource_id="c-1",
                display="Asthma",
                fhir_path="Bundle.entry[3].resource",
                date=date(2020, 5, 1),
            )
        ],
    )


def write_notes(root: Path, patient_id: str, notes: list[dict]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{patient_id}.json"
    path.write_text(json.dumps(notes), encoding="utf-8")
    return path


A_NOTE = {
    "note_id": "n-1",
    "date": "2024-03-09",
    "type": "Discharge summary",
    "author_role": "cardiology registrar",
    "text": "No history of myocardial infarction.",
}
ANOTHER_NOTE = {
    "note_id": "n-2",
    "date": "2023-01-05",
    "type": "GP consultation",
    "author_role": "general practitioner",
    "text": "Father had an MI in his fifties.",
}


class TestLoading:
    def test_a_note_becomes_a_narrative_evidence_row(self, tmp_path):
        write_notes(tmp_path, "p-1", [A_NOTE])
        (row,) = load_notes("p-1", root=tmp_path)
        assert row.kind == "note"
        assert row.source == "narrative"
        assert row.resource_id == "n-1"
        assert row.display == "Discharge summary"
        assert row.narrative_quote == "No history of myocardial infarction."
        assert row.date == date(2024, 3, 9)
        assert row.codes == ()

    def test_a_patient_with_no_notes_file_yields_no_notes(self, tmp_path):
        assert load_notes("nobody", root=tmp_path) == []

    def test_loading_is_deterministic_and_ordered_by_date(self, tmp_path):
        write_notes(tmp_path, "p-1", [A_NOTE, ANOTHER_NOTE])
        first = load_notes("p-1", root=tmp_path)
        assert [r.resource_id for r in first] == ["n-2", "n-1"]
        assert load_notes("p-1", root=tmp_path) == first

    def test_a_notes_file_that_is_not_a_list_of_notes_raises(self, tmp_path):
        (tmp_path / "p-1.json").write_text('{"note_id": "n-1"}', encoding="utf-8")
        with pytest.raises(NotesError):
            load_notes("p-1", root=tmp_path)

    def test_a_note_missing_a_required_field_raises(self, tmp_path):
        write_notes(tmp_path, "p-1", [{"note_id": "n-1", "text": "Hello."}])
        with pytest.raises(NotesError):
            load_notes("p-1", root=tmp_path)

    def test_two_notes_sharing_an_id_raise(self, tmp_path):
        write_notes(tmp_path, "p-1", [A_NOTE, {**A_NOTE, "text": "Something else."}])
        with pytest.raises(NotesError):
            load_notes("p-1", root=tmp_path)

    def test_a_note_date_is_read_by_the_same_parser_the_bundles_are(self):
        """There were two copies of it, identical line for line, and one place for them to drift."""
        from caliper import fhir, notes

        assert notes.parse_date is fhir.parse_date

    def test_a_partial_date_is_dropped_rather_than_completed(self, tmp_path):
        write_notes(tmp_path, "p-1", [{**A_NOTE, "date": "2024-03"}])
        (row,) = load_notes("p-1", root=tmp_path)
        assert row.date is None


class TestPointers:
    def test_a_pointer_names_the_file_and_the_note(self, tmp_path):
        path = write_notes(tmp_path, "p-1", [A_NOTE])
        (row,) = load_notes("p-1", root=tmp_path)
        assert row.fhir_path == note_pointer(path, "n-1")
        assert parse_note_pointer(row.fhir_path).note_id == "n-1"

    def test_a_pointer_resolves_back_to_the_note_it_came_from(self, tmp_path):
        write_notes(tmp_path, "p-1", [A_NOTE, ANOTHER_NOTE])
        for row in load_notes("p-1", root=tmp_path):
            resolved = resolve_note_pointer(row.fhir_path)
            assert resolved is not None
            assert resolved["note_id"] == row.resource_id
            assert resolved["text"] == row.narrative_quote

    def test_a_pointer_to_a_note_that_is_not_there_resolves_to_nothing(self, tmp_path):
        path = write_notes(tmp_path, "p-1", [A_NOTE])
        assert resolve_note_pointer(note_pointer(path, "n-99")) is None

    def test_a_pointer_that_is_not_a_pointer_is_refused(self):
        with pytest.raises(NotesError):
            parse_note_pointer("Bundle.entry[8].resource")

    @pytest.mark.parametrize("patient_id", sorted(CORPUS), ids=sorted(CORPUS))
    def test_every_committed_pointer_resolves(self, patient_id):
        """A citation a coordinator cannot open is not a citation."""
        rows = load_notes(patient_id, root=NOTES_DIR)
        assert rows
        for row in rows:
            resolved = resolve_note_pointer(row.fhir_path)
            assert resolved is not None, row.fhir_path
            assert resolved["text"] == row.narrative_quote


class TestAttaching:
    def test_notes_are_added_to_the_index(self, tmp_path):
        write_notes(tmp_path, "p-1", [A_NOTE])
        merged = attach_notes(a_patient(), root=tmp_path)
        assert [e.resource_id for e in merged.notes()] == ["n-1"]

    def test_the_original_index_is_left_alone(self, tmp_path):
        write_notes(tmp_path, "p-1", [A_NOTE])
        original = a_patient()
        before = list(original.evidence)
        merged = attach_notes(original, root=tmp_path)
        assert original.evidence == before
        assert original.notes() == []
        assert merged is not original
        assert merged.evidence is not original.evidence

    def test_structured_evidence_survives_the_merge(self, tmp_path):
        write_notes(tmp_path, "p-1", [A_NOTE])
        merged = attach_notes(a_patient(), root=tmp_path)
        assert [e.resource_id for e in merged.evidence if e.kind == "condition"] == ["c-1"]
        assert merged.birth_date == date(1970, 1, 1)
        assert merged.sex == "female"

    def test_attaching_twice_does_not_duplicate_the_notes(self, tmp_path):
        write_notes(tmp_path, "p-1", [A_NOTE])
        once = attach_notes(a_patient(), root=tmp_path)
        assert len(attach_notes(once, root=tmp_path).notes()) == 1

    def test_a_patient_with_no_notes_is_merged_unchanged(self, tmp_path):
        merged = attach_notes(a_patient(), root=tmp_path)
        assert merged.evidence == a_patient().evidence


class TestCorpusShape:
    def test_the_corpus_is_large_enough_to_be_worth_scoring(self):
        assert len(CORPUS) >= 8
        assert 16 <= sum(len(notes) for notes in CORPUS.values()) <= 24

    def test_every_note_file_names_a_committed_patient(self):
        known = {entry["id"] for entry in _load(PATIENT_INDEX)["patients"]}
        assert set(CORPUS) <= known

    def test_no_note_post_dates_the_chart_it_is_attached_to(self):
        """A 2026 letter on a chart that stops in 2016 would be a fixture nobody could believe."""
        entries = {e["id"]: e for e in _load(PATIENT_INDEX)["patients"]}
        for patient_id, notes in CORPUS.items():
            entry = entries[patient_id]
            for note in notes:
                assert entry["birth_date"] < note["date"] <= entry["latest_encounter_date"], (
                    f"{note['note_id']} sits outside {patient_id}'s encounter history"
                )

    def test_every_note_carries_the_fields_a_reader_is_promised(self):
        for patient_id, notes in CORPUS.items():
            assert isinstance(notes, list) and notes
            for note in notes:
                assert set(note) == {"note_id", "date", "type", "author_role", "text"}
                assert note["text"].strip()
                assert note["note_id"].startswith(patient_id[:8])

    def test_note_ids_are_unique_across_the_whole_corpus(self):
        ids = [note["note_id"] for notes in CORPUS.values() for note in notes]
        assert len(ids) == len(set(ids))


class TestManifestIsGroundTruth:
    def test_the_manifest_covers_exactly_the_committed_notes(self):
        listed = {(row["patient_id"], row["note_id"]) for row in MANIFEST_ROWS}
        present = {(pid, note["note_id"]) for pid, notes in CORPUS.items() for note in notes}
        assert listed == present

    @pytest.mark.parametrize(
        "row", MANIFEST_ROWS, ids=[row["note_id"] for row in MANIFEST_ROWS]
    )
    def test_every_quoted_sentence_appears_verbatim_in_its_note(self, row):
        """The check that stops the ground truth drifting away from the corpus."""
        note = next(n for n in CORPUS[row["patient_id"]] if n["note_id"] == row["note_id"])
        assert note["date"] == row["date"]
        for entry in row["items"]:
            assert entry["sentence"] in note["text"], (
                f"{row['note_id']}: {entry['sentence']!r} is not in the note"
            )

    def test_every_phenomenon_the_extractor_is_judged_on_appears_at_least_twice(self):
        counts = {name: 0 for name in REQUIRED_PHENOMENA}
        for row in MANIFEST_ROWS:
            for entry in row["items"]:
                counts[entry["phenomenon"]] += 1
        assert all(n >= 2 for n in counts.values()), counts

    def test_the_declared_counts_match_the_items(self):
        counted: dict[str, int] = {}
        for row in MANIFEST_ROWS:
            for entry in row["items"]:
                counted[entry["phenomenon"]] = counted.get(entry["phenomenon"], 0) + 1
        assert MANIFEST["counts"] == counted

    def test_an_assertion_that_is_not_present_or_absent_extracts_nothing(self):
        """The manifest must agree with the guard it is used to score."""
        for row in MANIFEST_ROWS:
            for entry in row["items"]:
                if entry["assertion"] not in ("present", "absent"):
                    assert entry["extract"] == [], entry["sentence"]

    def test_every_phenomenon_used_is_one_the_manifest_defines(self):
        defined = set(MANIFEST["phenomena"])
        assert defined == set(REQUIRED_PHENOMENA)
        used = {entry["phenomenon"] for row in MANIFEST_ROWS for entry in row["items"]}
        assert used <= defined
