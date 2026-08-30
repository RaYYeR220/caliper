"""The pre-registered answer key: schema, loader, and the freezing that makes it evidence.

The key says what the right answer is for each patient-and-trial pair before any system is run
against it. That claim is only worth something if a reader can tell it was not edited afterwards,
which is what `freeze` and `verify_frozen` are for: the README can carry a digest, and anyone can
recompute it.

The fingerprint is over content, not over bytes. It ignores how a dictionary happened to be
ordered, what order the cases were written in, and when the key was frozen — so re-freezing an
unchanged key produces the same digest, and any real edit produces a different one.

Storage is JSON. `pyproject.toml` declares no YAML dependency (PyYAML is importable in the
development environment only as a transitive dependency of `vcrpy`, a dev extra, so a normal
install of Caliper would not have it), and adding one to store a few hundred lines of structured
data would buy nothing.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal

from caliper.ir import Code
from caliper.logic import ScreeningOutcome, Verdict
from caliper.record import Evidence, PatientIndex

# The failure modes the evaluation is designed to separate. "none" is a case with no trap: an
# honest pair that should simply come out right, without which the key would only measure traps.
TRAPS = (
    "none",
    "missing_data",
    "unit",
    "temporal",
    "negation",
    "family_history",
    "unsupported",
    "threshold_edge",
    "shuffled_pair",
)

PROVENANCES = ("constructed", "annotated")

MIN_ANNOTATORS = 2

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = _REPO_ROOT / "data"

SIDECAR_SUFFIX = ".sha256"


class AnswerKeyError(ValueError):
    """The key on disk is not one this evaluation can be judged against."""


@dataclass(frozen=True)
class CriterionLabel:
    """The expected verdict for one criterion, quoted from the protocol as the annotator read it."""

    quote: str
    expected: Verdict


@dataclass(frozen=True)
class Case:
    """One pre-registered patient-and-trial pair, with the answer and why it is the answer."""

    id: str
    patient_id: str
    nct_id: str
    screening_date: date
    expected: ScreeningOutcome
    provenance: Literal["constructed", "annotated"]
    trap: str
    rationale: str
    criterion_labels: tuple[CriterionLabel, ...] = ()
    perturbations: tuple[dict[str, Any], ...] = ()
    annotators: tuple[str, ...] = ()
    adjudicated_by: str | None = None


@dataclass(frozen=True)
class AnswerKey:
    """A whole key, at one version, frozen at one moment."""

    version: str
    screening_date: date
    cases: tuple[Case, ...] = ()
    frozen_at: datetime | None = None
    notes: str = ""


# ------------------------------------------------------------------------------------------------
# Rebuilding a constructed chart
# ------------------------------------------------------------------------------------------------


def _rehydrate(snapshot: dict[str, Any], where: str) -> Evidence:
    """One evidence row rebuilt from the record a case publishes.

    The synthetic `fhir_path` travels with it. A row that came from a perturbation says so — it
    points at `perturb.add_condition` rather than at a bundle entry — and a viewer that showed a
    plausible-looking pointer resolving to nothing would be worse than one that shows this.
    """
    try:
        when = snapshot["date"]
        return Evidence(
            kind=snapshot["kind"],
            resource_type=snapshot["resource_type"],
            resource_id=snapshot["resource_id"],
            display=snapshot["display"],
            fhir_path=snapshot["fhir_path"],
            codes=tuple(Code(system=c["system"], code=c["code"]) for c in snapshot["codes"]),
            value=snapshot["value"],
            unit=snapshot["unit"],
            date=date.fromisoformat(when) if when else None,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise AnswerKeyError(
            f"{where}: an added row is not a usable evidence record: {exc}"
        ) from exc


def _is(row: Evidence, snapshot: dict[str, Any]) -> bool:
    """Whether this row is the one the record says was removed or replaced.

    A FHIR panel flattens into one row per component, all carrying the same `resource_id`, so the
    identifier alone does not pick a row out. The value, unit, date and codes together do.
    """
    return bool(
        row.resource_id == snapshot.get("resource_id")
        and row.value == snapshot.get("value")
        and row.unit == snapshot.get("unit")
        and (row.date.isoformat() if row.date else None) == snapshot.get("date")
        and [{"system": c.system, "code": c.code} for c in row.codes] == snapshot.get("codes")
    )


def _replay(rows: list[Evidence], record: dict[str, Any], where: str) -> list[Evidence]:
    """Apply one recorded perturbation to a chart, or refuse to.

    `caliper.perturb` raises rather than returning a chart unchanged, because a constructed case
    whose label asserts an edit that never happened is a wrong answer in the answer key. Replaying
    a published record is held to the same standard: every row the record says it removed has to be
    on the chart exactly once, or this is not the chart the key describes.
    """
    remaining = list(rows)
    for snapshot in record.get("before") or ():
        matched = [row for row in remaining if _is(row, snapshot)]
        if len(matched) != 1:
            raise AnswerKeyError(
                f"{where}: the recorded {record.get('kind')} names "
                f"{snapshot.get('resource_id')} ({snapshot.get('value')} {snapshot.get('unit')}), "
                f"which the chart carries {len(matched)} times"
            )
        remaining.remove(matched[0])
    return [*remaining, *(_rehydrate(snapshot, where) for snapshot in record.get("after") or ())]


def rebuild_patient(case: Case, base: PatientIndex) -> PatientIndex:
    """The chart a case is actually about: `base` with the case's recorded perturbations replayed.

    This is the one implementation. A constructed case's labels describe the edited chart, so
    anything that scores, renders or re-derives such a case has to reproduce the same edits from
    the same record, and three implementations of that is three chances to disagree about what a
    case says.

    An annotated case has no perturbations and is returned unchanged, which is the whole reason the
    caller does not need to know which provenance it is holding. A constructed case is rebuilt only
    if every recorded edit applies exactly as recorded: a `before` row that the chart does not
    carry, or carries twice, means this is not the chart the key describes, and continuing would
    produce a plausible chart that no published record accounts for.

    Only `evidence` changes. Demographics and vital status are carried over untouched, because no
    perturbation in this key edits them and silently resurrecting a deceased patient by rebuilding
    the index field by field is a bug this project has already had once.
    """
    where = f"case {case.id}"
    if case.patient_id and base.patient_id and case.patient_id != base.patient_id:
        raise AnswerKeyError(
            f"{where}: expects the chart of patient {case.patient_id}, got {base.patient_id}"
        )
    if not case.perturbations:
        return base

    rows = list(base.evidence)
    for record in case.perturbations:
        rows = _replay(rows, dict(record), where)
    return replace(base, evidence=rows)


def _case_payload(case: Case) -> dict[str, Any]:
    return {
        "id": case.id,
        "patient_id": case.patient_id,
        "nct_id": case.nct_id,
        "screening_date": case.screening_date.isoformat(),
        "expected": case.expected.value,
        "provenance": case.provenance,
        "trap": case.trap,
        "rationale": case.rationale,
        "criterion_labels": [
            {"quote": label.quote, "expected": label.expected.value}
            for label in case.criterion_labels
        ],
        "perturbations": [dict(record) for record in case.perturbations],
        "annotators": list(case.annotators),
        "adjudicated_by": case.adjudicated_by,
    }


def _payload(key: AnswerKey) -> dict[str, Any]:
    """The key as plain data, in the shape written to disk."""
    return {
        "version": key.version,
        "screening_date": key.screening_date.isoformat(),
        "frozen_at": key.frozen_at.isoformat() if key.frozen_at else None,
        "notes": key.notes,
        "cases": [_case_payload(case) for case in key.cases],
    }


def _case_sort_key(case: Any) -> str:
    return str(case.get("id", "")) if isinstance(case, dict) else repr(case)


def _canonical_bytes(payload: dict[str, Any]) -> bytes:
    """The digest input: content only, in one canonical order.

    `frozen_at` is dropped so that re-freezing an unchanged key is visibly unchanged, and the cases
    are sorted by id so that reordering the file is not mistaken for editing it. Object keys are
    sorted recursively by `json.dumps`, which is what makes the digest insensitive to how a
    perturbation record happened to be built.
    """
    content = {k: v for k, v in payload.items() if k != "frozen_at"}
    cases = content.get("cases")
    if isinstance(cases, list):
        content["cases"] = sorted(cases, key=_case_sort_key)
    text = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return text.encode("utf-8")


def key_fingerprint(key: AnswerKey) -> str:
    """A sha256 over the key's content, stable under reordering and independent of `frozen_at`."""
    return hashlib.sha256(_canonical_bytes(_payload(key))).hexdigest()


def _enum(cls: type[Verdict] | type[ScreeningOutcome], value: Any, where: str) -> Any:
    try:
        return cls(value)
    except ValueError:
        legal = ", ".join(member.value for member in cls)
        raise AnswerKeyError(f"{where}: {value!r} is not one of {legal}") from None


def _require(payload: Any, name: str) -> Any:
    if not isinstance(payload, dict):
        raise AnswerKeyError(f"{name} must be a JSON object, got {type(payload).__name__}")
    return payload


def _parse_case(payload: Any) -> Case:
    body = _require(payload, "each case")
    case_id = body.get("id")
    if not isinstance(case_id, str) or not case_id.strip():
        raise AnswerKeyError(f"a case is missing a usable id: {body!r}")
    where = f"case {case_id}"
    try:
        screening_date = date.fromisoformat(str(body["screening_date"]))
    except (KeyError, ValueError) as exc:
        raise AnswerKeyError(f"{where}: screening_date is missing or unreadable") from exc

    labels = tuple(
        CriterionLabel(
            quote=str(_require(label, f"{where}: each criterion label").get("quote", "")),
            expected=_enum(Verdict, label.get("expected"), f"{where}: criterion label"),
        )
        for label in body.get("criterion_labels") or ()
    )
    return Case(
        id=case_id,
        patient_id=str(body.get("patient_id", "")),
        nct_id=str(body.get("nct_id", "")),
        screening_date=screening_date,
        expected=_enum(ScreeningOutcome, body.get("expected"), f"{where}: expected"),
        provenance=body.get("provenance"),
        trap=str(body.get("trap", "")),
        rationale=str(body.get("rationale", "")),
        criterion_labels=labels,
        perturbations=tuple(dict(record) for record in body.get("perturbations") or ()),
        annotators=tuple(str(name) for name in body.get("annotators") or ()),
        adjudicated_by=body.get("adjudicated_by"),
    )


def _parse(payload: Any) -> AnswerKey:
    body = _require(payload, "the answer key")
    try:
        screening_date = date.fromisoformat(str(body["screening_date"]))
    except (KeyError, ValueError) as exc:
        raise AnswerKeyError("the answer key: screening_date is missing or unreadable") from exc
    stamp = body.get("frozen_at")
    return AnswerKey(
        version=str(body.get("version", "")),
        screening_date=screening_date,
        cases=tuple(_parse_case(case) for case in body.get("cases") or ()),
        frozen_at=datetime.fromisoformat(stamp) if isinstance(stamp, str) and stamp else None,
        notes=str(body.get("notes", "")),
    )


def _known_patient_ids(data_dir: Path) -> set[str]:
    index = data_dir / "patients" / "index.json"
    if not index.is_file():
        raise AnswerKeyError(f"cannot validate patient ids: {index} is missing")
    payload = json.loads(index.read_text(encoding="utf-8"))
    return {str(entry["id"]) for entry in payload.get("patients", [])}


def _known_nct_ids(data_dir: Path) -> set[str]:
    trials = data_dir / "trials"
    if not trials.is_dir():
        raise AnswerKeyError(f"cannot validate trial ids: {trials} is missing")
    return {path.stem for path in trials.glob("*.json") if not path.name.startswith("_")}


def validate_key(key: AnswerKey, *, data_dir: Path | None = None) -> AnswerKey:
    """Check every rule the evaluation depends on, raising on the first violation.

    The rules are not stylistic. A duplicate id makes a result unattributable; a patient or trial we
    do not ship makes a case unreproducible; a constructed case with no perturbation is asserting a
    label it cannot justify; and an annotated case with one annotator and no adjudicator is one
    person's opinion wearing the word "ground truth".
    """
    root = DEFAULT_DATA_DIR if data_dir is None else Path(data_dir)
    patients = _known_patient_ids(root)
    trials = _known_nct_ids(root)

    seen: set[str] = set()
    for case in key.cases:
        where = f"case {case.id}"
        if case.id in seen:
            raise AnswerKeyError(f"duplicate case id {case.id!r}")
        seen.add(case.id)

        if not isinstance(case.expected, ScreeningOutcome):
            raise AnswerKeyError(f"{where}: expected {case.expected!r} is not a ScreeningOutcome")
        for label in case.criterion_labels:
            if not isinstance(label.expected, Verdict):
                raise AnswerKeyError(f"{where}: {label.expected!r} is not a Verdict")
        if case.provenance not in PROVENANCES:
            raise AnswerKeyError(
                f"{where}: provenance {case.provenance!r} must be one of {PROVENANCES}"
            )
        if case.trap not in TRAPS:
            raise AnswerKeyError(f"{where}: trap {case.trap!r} must be one of {TRAPS}")
        if not case.rationale.strip():
            raise AnswerKeyError(f"{where}: rationale may not be blank")
        if case.patient_id not in patients:
            raise AnswerKeyError(f"{where}: patient {case.patient_id!r} is not in {root}")
        if case.nct_id not in trials:
            raise AnswerKeyError(f"{where}: trial {case.nct_id!r} is not in {root / 'trials'}")

        if case.provenance == "constructed" and not case.perturbations:
            raise AnswerKeyError(
                f"{where}: a constructed case must record at least one perturbation"
            )
        if case.provenance == "annotated":
            if len(set(case.annotators)) < MIN_ANNOTATORS:
                raise AnswerKeyError(
                    f"{where}: an annotated case needs at least "
                    f"{MIN_ANNOTATORS} distinct annotators, got {list(case.annotators)}"
                )
            if not (case.adjudicated_by or "").strip():
                raise AnswerKeyError(f"{where}: an annotated case must name an adjudicator")
    return key


def load_key(path: Path | str, *, data_dir: Path | None = None) -> AnswerKey:
    """Read and validate an answer key. `data_dir` defaults to the repository's `data/`."""
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AnswerKeyError(f"{source} is not valid JSON: {exc}") from exc
    return validate_key(_parse(payload), data_dir=data_dir)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Binary mode: text mode would rewrite "\n" as "\r\n" on Windows and change the file's digest.
    path.write_bytes((text + "\n").encode("utf-8"))


def save_key(
    key: AnswerKey, path: Path | str, *, data_dir: Path | None = None, validate: bool = True
) -> None:
    """Write an answer key, validating it first.

    Validation happens before the write because an invalid key on disk is one whose digest may
    already have been published. Pass `validate=False` only to stage a key that is knowingly
    incomplete — `load_key` will still refuse it.
    """
    if validate:
        validate_key(key, data_dir=data_dir)
    _write_json(Path(path), _payload(key))


def _sidecar(path: Path) -> Path:
    return path.with_name(path.name + SIDECAR_SUFFIX)


def freeze(key: AnswerKey, path: Path | str, *, data_dir: Path | None = None) -> str:
    """Write the key with a fresh `frozen_at`, write its digest sidecar, return the digest.

    The digest is over content, so freezing an unchanged key twice yields the same value even
    though the stamp moved. That is the point: the README can quote it, and a judge can tell
    whether the key that produced the published results is the key in the repository.
    """
    destination = Path(path)
    stamped = AnswerKey(
        version=key.version,
        screening_date=key.screening_date,
        cases=key.cases,
        frozen_at=datetime.now(UTC).replace(microsecond=0),
        notes=key.notes,
    )
    save_key(stamped, destination, data_dir=data_dir)
    digest = key_fingerprint(stamped)
    _sidecar(destination).write_bytes(f"{digest}  {destination.name}\n".encode())
    return digest


def verify_frozen(path: Path | str) -> bool:
    """Whether the key on disk still matches its sidecar digest.

    Deliberately independent of `validate_key`: this answers "was this file edited after it was
    frozen", which a judge must be able to check without the patient corpus to hand.
    """
    source = Path(path)
    sidecar = _sidecar(source)
    if not source.is_file() or not sidecar.is_file():
        return False
    recorded = sidecar.read_text(encoding="utf-8").split()
    if not recorded:
        return False
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    if not isinstance(payload, dict):
        return False
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest() == recorded[0]
