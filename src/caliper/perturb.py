"""Constructed cases: edits to a chart whose consequence for the verdict is known by construction.

Redact the only creatinine and the renal criterion must resolve to UNKNOWN. Move an HbA1c from 7.1
to 6.9 across a 7.0 threshold and the verdict must flip. No human has to adjudicate these, and no
one can argue with them, which is what makes them the negative controls that stop a green result
from being vacuous.

Three rules hold for every function here.

Nothing is mutated. Each returns a fresh `PatientIndex`; `Evidence` is frozen, so the untouched
rows are shared rather than copied. A perturbation that edited its input in place would poison
every later case built from the same bundle.

Nothing happens quietly. A function whose target is absent raises `PerturbationError` instead of
returning the chart unchanged. A silent no-op yields a "constructed" case whose label asserts a
change that was never made — a wrong answer in the answer key, which is the worst failure available
in this file.

Nothing is clever. `convert_units` multiplies by the factor it is handed and rewrites the unit
string, with no reference to `caliper.units`. The point of a unit case is to test whether the
system converts correctly, so the fixture must not be built from the system's own conversion table.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import date
from typing import Any

from caliper.ir import Code
from caliper.record import Evidence, PatientIndex

# A synthetic row points at no bundle entry, and must not pretend otherwise: an evidence pointer
# that looks real but resolves to nothing is worse than one that is obviously manufactured.
_SYNTHETIC_PATH = "perturb.add_condition"


class PerturbationError(ValueError):
    """The perturbation could not be applied, so no constructed case may claim it was."""


def _snapshot(row: Evidence) -> dict[str, Any]:
    """A JSON-safe record of one evidence row, enough to reconstruct the diff."""
    return {
        "resource_id": row.resource_id,
        "resource_type": row.resource_type,
        "kind": row.kind,
        "display": row.display,
        "fhir_path": row.fhir_path,
        "codes": [{"system": c.system, "code": c.code} for c in row.codes],
        "value": row.value,
        "unit": row.unit,
        "date": row.date.isoformat() if row.date else None,
    }


@dataclass(frozen=True)
class Perturbation:
    """What was done to the chart, in enough detail to reproduce and to publish."""

    kind: str
    description: str
    affected_resource_ids: tuple[str, ...]
    before: tuple[dict[str, Any], ...]
    after: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        """The record as plain data, for `answerkey.Case.perturbations`."""
        return {
            "kind": self.kind,
            "description": self.description,
            "affected_resource_ids": list(self.affected_resource_ids),
            "before": list(self.before),
            "after": list(self.after),
        }


@dataclass(frozen=True)
class PerturbedPatient:
    """A perturbed chart and the ordered record of how it got that way."""

    patient: PatientIndex
    perturbations: tuple[Perturbation, ...]

    def then(
        self, perturb: Callable[..., PerturbedPatient], *args: Any, **kwargs: Any
    ) -> PerturbedPatient:
        """Apply another perturbation, accumulating the record.

        Cases routinely need two edits — redact one analyte and move another across a threshold —
        and the answer key stores the perturbations as a list for exactly that reason.
        """
        following = perturb(self.patient, *args, **kwargs)
        return PerturbedPatient(
            patient=following.patient,
            perturbations=self.perturbations + following.perturbations,
        )


def _rebuild(patient: PatientIndex, evidence: Iterable[Evidence]) -> PatientIndex:
    """Copy the whole index and swap the evidence.

    Listing the fields by hand is how a chart edit came to resurrect a deceased patient: `deceased`
    was added to `PatientIndex` afterwards and this function silently dropped it. `replace` cannot
    lose a field that is added later.
    """
    return replace(patient, evidence=list(evidence))


def _result(
    patient: PatientIndex, rows: Iterable[Evidence], record: Perturbation
) -> PerturbedPatient:
    return PerturbedPatient(patient=_rebuild(patient, rows), perturbations=(record,))


def _without(patient: PatientIndex, removed: list[Evidence]) -> list[Evidence]:
    """Drop the given rows by identity, so two rows that merely look alike are not confused."""
    dropped = {id(row) for row in removed}
    return [row for row in patient.evidence if id(row) not in dropped]


def _has_loinc(row: Evidence, loinc: str) -> bool:
    return any(code.system == "LOINC" and code.code == loinc for code in row.codes)


def _analyte_rows(patient: PatientIndex, loinc: str) -> list[Evidence]:
    """Every observation row for one analyte, most recent first, or raise if there are none.

    The ordering mirrors `PatientIndex.find`, so "the latest result" means the same row here as it
    does to the evaluator — including the tie-break between two results drawn on the same day.
    """
    rows = [row for row in patient.evidence if row.kind == "observation" and _has_loinc(row, loinc)]
    if not rows:
        raise PerturbationError(
            f"patient {patient.patient_id} has no observation coded LOINC {loinc}"
        )
    return sorted(rows, key=lambda r: (r.date is not None, r.date or date.min), reverse=True)


def redact_analyte(patient: PatientIndex, loinc: str) -> PerturbedPatient:
    """Remove every result for one analyte, so the answer is forced to "unknown"."""
    removed = _analyte_rows(patient, loinc)
    kept = _without(patient, removed)
    record = Perturbation(
        kind="redact_analyte",
        description=f"removed all {len(removed)} results coded LOINC {loinc}",
        affected_resource_ids=tuple(row.resource_id for row in removed),
        before=tuple(_snapshot(row) for row in removed),
        after=(),
    )
    return _result(patient, kept, record)


def shift_value(patient: PatientIndex, loinc: str, *, to: float) -> PerturbedPatient:
    """Move the most recent result for one analyte to a new value, leaving its unit and date.

    Only the latest result moves, because that is the row the evaluator reads. Rewriting the whole
    series would change the case into something else — a chart that never held the original value —
    and would make the threshold the case is built around harder to point at.
    """
    latest = _analyte_rows(patient, loinc)[0]
    if latest.value is None:
        raise PerturbationError(
            f"the most recent LOINC {loinc} result ({latest.resource_id}) carries no numeric value"
        )
    shifted = replace(latest, value=to)
    rows = [shifted if row is latest else row for row in patient.evidence]
    record = Perturbation(
        kind="shift_value",
        description=(
            f"moved the most recent LOINC {loinc} result from {latest.value} to {to} "
            f"{latest.unit or 'with no unit'}"
        ),
        affected_resource_ids=(latest.resource_id,),
        before=(_snapshot(latest),),
        after=(_snapshot(shifted),),
    )
    return _result(patient, rows, record)


def convert_units(
    patient: PatientIndex, loinc: str, *, to_unit: str, factor: float
) -> PerturbedPatient:
    """Restate every result for one analyte in another unit, by the caller's factor.

    Deliberately dumb: the value is multiplied by `factor` and the unit string is replaced. Nothing
    checks that the factor is correct, because the case exists to test whether the system converts
    correctly, and a fixture built from the system's own table could not detect a wrong table.
    """
    numeric = [(row, row.value) for row in _analyte_rows(patient, loinc) if row.value is not None]
    if not numeric:
        raise PerturbationError(f"no LOINC {loinc} result carries a numeric value to convert")

    converted = {
        id(row): replace(row, value=value * factor, unit=to_unit) for row, value in numeric
    }
    rebuilt = [converted.get(id(row), row) for row in patient.evidence]
    record = Perturbation(
        kind="convert_units",
        description=(
            f"restated all {len(numeric)} LOINC {loinc} results in {to_unit} "
            f"by multiplying by {factor}"
        ),
        affected_resource_ids=tuple(row.resource_id for row, _ in numeric),
        before=tuple(_snapshot(row) for row, _ in numeric),
        after=tuple(_snapshot(converted[id(row)]) for row, _ in numeric),
    )
    return _result(patient, rebuilt, record)


def shift_date(patient: PatientIndex, resource_id: str, *, to: date) -> PerturbedPatient:
    """Move one source resource in time, taking every row derived from it along.

    A FHIR panel flattens into one row per component, all pointing at a single dated resource, so
    moving fewer than all of them would leave one Observation claiming two effective dates.
    """
    targets = [row for row in patient.evidence if row.resource_id == resource_id]
    if not targets:
        raise PerturbationError(
            f"patient {patient.patient_id} has no evidence from resource {resource_id}"
        )
    moved = {id(row): replace(row, date=to) for row in targets}
    rebuilt = [moved.get(id(row), row) for row in patient.evidence]
    was = ", ".join(sorted({row.date.isoformat() if row.date else "undated" for row in targets}))
    record = Perturbation(
        kind="shift_date",
        description=f"moved resource {resource_id} from {was} to {to.isoformat()}",
        affected_resource_ids=(resource_id,),
        before=tuple(_snapshot(row) for row in targets),
        after=tuple(_snapshot(moved[id(row)]) for row in targets),
    )
    return _result(patient, rebuilt, record)


def remove_encounters(patient: PatientIndex, *, after: date) -> PerturbedPatient:
    """Drop every encounter later than `after`, closing the window the chart documents.

    This is the case that separates "the patient does not have it" from "nobody was looking":
    with no encounter covering the window, `AbsencePolicy.COVERAGE_GATED` must abstain rather than
    read silence as absence. Undated encounters stay, since nothing shows them to be later.
    """
    removed = [
        row
        for row in patient.evidence
        if row.kind == "encounter" and row.date is not None and row.date > after
    ]
    if not removed:
        raise PerturbationError(
            f"patient {patient.patient_id} has no encounter after {after.isoformat()}"
        )
    kept = _without(patient, removed)
    record = Perturbation(
        kind="remove_encounters",
        description=f"removed {len(removed)} encounters dated after {after.isoformat()}",
        affected_resource_ids=tuple(row.resource_id for row in removed),
        before=tuple(_snapshot(row) for row in removed),
        after=(),
    )
    return _result(patient, kept, record)


def add_condition(
    patient: PatientIndex, code: Code, display: str, *, onset: date
) -> PerturbedPatient:
    """Put a coded condition on the chart, dated at `onset`.

    `display` is the wording the chart is to show and is not derived from `code.display`: a case
    about a condition recorded under an unhelpful label needs to say so. Callers building a case
    that must be indistinguishable from ingested rows should mirror how `fhir.py` renders a
    Condition, which appends the clinical and verification statuses in parentheses.
    """
    resource_id = f"perturbation-condition-{code.system.casefold()}-{code.code}"
    already = any(
        row.kind == "condition"
        and any(c.system == code.system and c.code == code.code for c in row.codes)
        for row in patient.evidence
    )
    if already:
        raise PerturbationError(
            f"patient {patient.patient_id} already has a condition coded "
            f"{code.system} {code.code}; adding it again would prove nothing"
        )

    added = Evidence(
        kind="condition",
        resource_type="Condition",
        resource_id=resource_id,
        display=display,
        fhir_path=_SYNTHETIC_PATH,
        codes=(code,),
        date=onset,
    )
    record = Perturbation(
        kind="add_condition",
        description=(
            f"added condition {code.system} {code.code} ({display}) with onset {onset.isoformat()}"
        ),
        affected_resource_ids=(resource_id,),
        before=(),
        after=(_snapshot(added),),
    )
    return _result(patient, [*patient.evidence, added], record)
