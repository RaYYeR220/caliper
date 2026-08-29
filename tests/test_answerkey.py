"""The answer key is pre-registered, so the tests are mostly about tamper-evidence.

The fingerprint has to ignore everything that is not content — how a dictionary happened to be
ordered, when the key was frozen, what order the cases were written in — and catch everything that
is. Without that, a digest in the README proves nothing.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from caliper.answerkey import (
    AnswerKey,
    AnswerKeyError,
    Case,
    CriterionLabel,
    freeze,
    key_fingerprint,
    load_key,
    save_key,
    verify_frozen,
)
from caliper.logic import ScreeningOutcome, Verdict

PATIENT_ID = "1be83f06-48ef-7bac-7097-b9e0644aeaf8"
OTHER_PATIENT_ID = "ee4b7339-ca58-b6af-c199-04b6d5761c73"
NCT_ID = "NCT03036124"


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """A minimal stand-in for ``data/``, so validation is not coupled to the real corpus."""
    root = tmp_path / "data"
    (root / "patients").mkdir(parents=True)
    (root / "trials").mkdir(parents=True)
    (root / "patients" / "index.json").write_text(
        json.dumps({"patients": [{"id": PATIENT_ID}, {"id": OTHER_PATIENT_ID}]}), encoding="utf-8"
    )
    (root / "trials" / f"{NCT_ID}.json").write_text("{}", encoding="utf-8")
    return root


def a_constructed_case(**overrides) -> Case:
    defaults = dict(
        id="constructed-missing-creatinine",
        patient_id=PATIENT_ID,
        nct_id=NCT_ID,
        screening_date=date(2026, 6, 1),
        expected=ScreeningOutcome.NEEDS_REVIEW,
        provenance="constructed",
        trap="missing_data",
        rationale="the only creatinine result was redacted, so the renal criterion cannot resolve",
        criterion_labels=(CriterionLabel(quote="eGFR > 45 mL/min", expected=Verdict.UNKNOWN),),
        perturbations=({"kind": "redact_analyte", "loinc": "38483-4"},),
    )
    return Case(**{**defaults, **overrides})


def an_annotated_case(**overrides) -> Case:
    defaults = dict(
        id="annotated-asthma-eligible",
        patient_id=OTHER_PATIENT_ID,
        nct_id=NCT_ID,
        screening_date=date(2026, 6, 1),
        expected=ScreeningOutcome.ELIGIBLE,
        provenance="annotated",
        trap="none",
        rationale="every inclusion is documented and no exclusion is triggered",
        annotators=("ada", "grace"),
        adjudicated_by="ada",
    )
    return Case(**{**defaults, **overrides})


def a_key(*cases: Case, **overrides) -> AnswerKey:
    defaults = dict(
        version="1.0.0",
        screening_date=date(2026, 6, 1),
        cases=cases or (a_constructed_case(), an_annotated_case()),
        frozen_at=None,
        notes="pre-registered before any results were produced",
    )
    return AnswerKey(**{**defaults, **overrides})


class TestFingerprint:
    def test_it_is_stable_across_calls(self):
        key = a_key()
        assert key_fingerprint(key) == key_fingerprint(a_key())

    def test_it_is_a_sha256_hex_digest(self):
        digest = key_fingerprint(a_key())
        assert len(digest) == 64
        assert set(digest) <= set("0123456789abcdef")

    def test_reordering_the_keys_of_a_dictionary_does_not_change_it(self):
        one = a_key(a_constructed_case(perturbations=({"kind": "shift_value", "to": 6.9},)))
        two = a_key(a_constructed_case(perturbations=({"to": 6.9, "kind": "shift_value"},)))
        assert key_fingerprint(one) == key_fingerprint(two)

    def test_reordering_the_cases_does_not_change_it(self):
        forwards = a_key(a_constructed_case(), an_annotated_case())
        backwards = a_key(an_annotated_case(), a_constructed_case())
        assert key_fingerprint(forwards) == key_fingerprint(backwards)

    def test_frozen_at_does_not_change_it(self):
        """Otherwise re-freezing an unchanged key would look like an edit."""
        stamped = a_key(frozen_at=datetime(2026, 6, 2, 9, 0, tzinfo=UTC))
        later = a_key(frozen_at=datetime(2026, 7, 3, 17, 30, tzinfo=UTC))
        assert key_fingerprint(stamped) == key_fingerprint(later) == key_fingerprint(a_key())

    def test_changing_an_expected_outcome_changes_it(self):
        edited = a_key(
            a_constructed_case(expected=ScreeningOutcome.INELIGIBLE), an_annotated_case()
        )
        assert key_fingerprint(edited) != key_fingerprint(a_key())

    def test_changing_a_criterion_label_changes_it(self):
        edited = a_key(
            a_constructed_case(
                criterion_labels=(
                    CriterionLabel(quote="eGFR > 45 mL/min", expected=Verdict.NOT_MET),
                )
            ),
            an_annotated_case(),
        )
        assert key_fingerprint(edited) != key_fingerprint(a_key())

    def test_changing_the_rationale_changes_it(self):
        edited = a_key(a_constructed_case(rationale="something else"), an_annotated_case())
        assert key_fingerprint(edited) != key_fingerprint(a_key())

    def test_changing_the_notes_changes_it(self):
        assert key_fingerprint(a_key(notes="edited")) != key_fingerprint(a_key())

    def test_dropping_a_case_changes_it(self):
        assert key_fingerprint(a_key(a_constructed_case())) != key_fingerprint(a_key())


class TestRoundTrip:
    def test_every_field_survives_save_and_load(self, tmp_path: Path, data_dir: Path):
        key = a_key(frozen_at=datetime(2026, 6, 2, 9, 0, tzinfo=UTC))
        path = tmp_path / "answer_key.json"
        save_key(key, path, data_dir=data_dir)
        assert load_key(path, data_dir=data_dir) == key

    def test_the_file_is_utf8_with_lf_newlines(self, tmp_path: Path, data_dir: Path):
        path = tmp_path / "answer_key.json"
        save_key(a_key(notes="unité"), path, data_dir=data_dir)
        raw = path.read_bytes()
        assert b"\r\n" not in raw
        assert raw.endswith(b"\n")
        assert "unité" in raw.decode("utf-8")

    def test_saving_twice_produces_identical_bytes(self, tmp_path: Path, data_dir: Path):
        one, two = tmp_path / "a.json", tmp_path / "b.json"
        save_key(a_key(), one, data_dir=data_dir)
        save_key(a_key(), two, data_dir=data_dir)
        assert one.read_bytes() == two.read_bytes()

    def test_a_loaded_key_fingerprints_the_same(self, tmp_path: Path, data_dir: Path):
        path = tmp_path / "answer_key.json"
        save_key(a_key(), path, data_dir=data_dir)
        assert key_fingerprint(load_key(path, data_dir=data_dir)) == key_fingerprint(a_key())


class TestFreezing:
    def test_freeze_writes_the_key_and_a_sidecar(self, tmp_path: Path, data_dir: Path):
        path = tmp_path / "answer_key.json"
        digest = freeze(a_key(), path, data_dir=data_dir)
        assert path.is_file()
        sidecar = tmp_path / "answer_key.json.sha256"
        assert sidecar.is_file()
        assert digest in sidecar.read_text(encoding="utf-8")
        assert path.name in sidecar.read_text(encoding="utf-8")

    def test_a_frozen_key_verifies(self, tmp_path: Path, data_dir: Path):
        path = tmp_path / "answer_key.json"
        freeze(a_key(), path, data_dir=data_dir)
        assert verify_frozen(path) is True

    def test_verify_detects_an_edited_key(self, tmp_path: Path, data_dir: Path):
        path = tmp_path / "answer_key.json"
        freeze(a_key(), path, data_dir=data_dir)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["cases"][0]["expected"] = "eligible"
        path.write_text(json.dumps(payload), encoding="utf-8")
        assert verify_frozen(path) is False

    def test_reformatting_the_file_is_not_an_edit(self, tmp_path: Path, data_dir: Path):
        """The digest is over content, so whitespace and key order must not trip it."""
        path = tmp_path / "answer_key.json"
        freeze(a_key(), path, data_dir=data_dir)
        payload = json.loads(path.read_text(encoding="utf-8"))
        path.write_text(json.dumps(payload, indent=8, sort_keys=False), encoding="utf-8")
        assert verify_frozen(path) is True

    def test_refreezing_an_unchanged_key_keeps_the_digest(self, tmp_path: Path, data_dir: Path):
        path = tmp_path / "answer_key.json"
        first = freeze(a_key(), path, data_dir=data_dir)
        second = freeze(a_key(), path, data_dir=data_dir)
        assert first == second

    def test_freeze_stamps_frozen_at(self, tmp_path: Path, data_dir: Path):
        path = tmp_path / "answer_key.json"
        freeze(a_key(), path, data_dir=data_dir)
        assert load_key(path, data_dir=data_dir).frozen_at is not None

    def test_verify_reports_false_when_the_sidecar_is_missing(self, tmp_path: Path, data_dir):
        path = tmp_path / "answer_key.json"
        save_key(a_key(), path, data_dir=data_dir)
        assert verify_frozen(path) is False


class TestValidation:
    def _write(self, path: Path, key: AnswerKey) -> Path:
        save_key(key, path, data_dir=None, validate=False)
        return path

    def test_duplicate_case_ids_are_rejected(self, tmp_path: Path, data_dir: Path):
        key = a_key(a_constructed_case(), a_constructed_case(patient_id=OTHER_PATIENT_ID))
        path = self._write(tmp_path / "k.json", key)
        with pytest.raises(AnswerKeyError, match="duplicate"):
            load_key(path, data_dir=data_dir)

    def test_an_illegal_screening_outcome_is_rejected(self, tmp_path: Path, data_dir: Path):
        path = self._write(tmp_path / "k.json", a_key())
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["cases"][0]["expected"] = "probably_fine"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(AnswerKeyError, match="probably_fine"):
            load_key(path, data_dir=data_dir)

    def test_an_illegal_criterion_verdict_is_rejected(self, tmp_path: Path, data_dir: Path):
        path = self._write(tmp_path / "k.json", a_key())
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["cases"][0]["criterion_labels"][0]["expected"] = "maybe"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(AnswerKeyError, match="maybe"):
            load_key(path, data_dir=data_dir)

    def test_an_illegal_trap_is_rejected(self, tmp_path: Path, data_dir: Path):
        path = self._write(tmp_path / "k.json", a_key(a_constructed_case(trap="vibes")))
        with pytest.raises(AnswerKeyError, match="vibes"):
            load_key(path, data_dir=data_dir)

    def test_an_illegal_provenance_is_rejected(self, tmp_path: Path, data_dir: Path):
        path = self._write(tmp_path / "k.json", a_key())
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["cases"][0]["provenance"] = "vibes"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(AnswerKeyError, match="provenance"):
            load_key(path, data_dir=data_dir)

    def test_an_unknown_patient_id_is_rejected(self, tmp_path: Path, data_dir: Path):
        key = a_key(a_constructed_case(patient_id="not-a-patient"))
        path = self._write(tmp_path / "k.json", key)
        with pytest.raises(AnswerKeyError, match="not-a-patient"):
            load_key(path, data_dir=data_dir)

    def test_an_unknown_nct_id_is_rejected(self, tmp_path: Path, data_dir: Path):
        path = self._write(tmp_path / "k.json", a_key(a_constructed_case(nct_id="NCT00000000")))
        with pytest.raises(AnswerKeyError, match="NCT00000000"):
            load_key(path, data_dir=data_dir)

    def test_a_constructed_case_needs_a_perturbation(self, tmp_path: Path, data_dir: Path):
        path = self._write(tmp_path / "k.json", a_key(a_constructed_case(perturbations=())))
        with pytest.raises(AnswerKeyError, match="perturbation"):
            load_key(path, data_dir=data_dir)

    def test_an_annotated_case_needs_two_annotators(self, tmp_path: Path, data_dir: Path):
        path = self._write(tmp_path / "k.json", a_key(an_annotated_case(annotators=("ada",))))
        with pytest.raises(AnswerKeyError, match="annotator"):
            load_key(path, data_dir=data_dir)

    def test_an_annotated_case_needs_an_adjudicator(self, tmp_path: Path, data_dir: Path):
        path = self._write(tmp_path / "k.json", a_key(an_annotated_case(adjudicated_by=None)))
        with pytest.raises(AnswerKeyError, match="adjudicat"):
            load_key(path, data_dir=data_dir)

    def test_a_blank_rationale_is_rejected(self, tmp_path: Path, data_dir: Path):
        path = self._write(tmp_path / "k.json", a_key(a_constructed_case(rationale="  ")))
        with pytest.raises(AnswerKeyError, match="rationale"):
            load_key(path, data_dir=data_dir)

    def test_a_valid_key_loads(self, tmp_path: Path, data_dir: Path):
        path = self._write(tmp_path / "k.json", a_key())
        assert len(load_key(path, data_dir=data_dir).cases) == 2

    def test_save_refuses_to_write_an_invalid_key(self, tmp_path: Path, data_dir: Path):
        key = a_key(a_constructed_case(perturbations=()))
        with pytest.raises(AnswerKeyError, match="perturbation"):
            save_key(key, tmp_path / "k.json", data_dir=data_dir)
        assert not (tmp_path / "k.json").exists()

    def test_a_malformed_file_names_the_problem(self, tmp_path: Path, data_dir: Path):
        path = tmp_path / "k.json"
        path.write_text("[]", encoding="utf-8")
        with pytest.raises(AnswerKeyError, match="object"):
            load_key(path, data_dir=data_dir)


class TestAgainstTheRealCorpus:
    def test_the_default_data_directory_is_the_committed_one(self, tmp_path: Path):
        """A key that names a patient we do not ship is unusable, and must fail on load."""
        repo_data = Path(__file__).resolve().parent.parent / "data"
        if not (repo_data / "patients" / "index.json").is_file():
            pytest.skip("data/patients is not present")
        path = tmp_path / "k.json"
        save_key(a_key(), path, data_dir=None, validate=False)
        assert load_key(path).cases
