"""Ingestion of Synthea FHIR R4 transaction bundles into a `PatientIndex`.

This is the only place in Caliper that touches raw FHIR, and it is deliberately dumb: it flattens,
it never interprets. A field we cannot read without guessing — an unfamiliar code system, a date
that is not a date, a quantity that is not a number — is dropped rather than approximated, because
a fabricated value here becomes an unarguable verdict three modules later.

Every row keeps `Bundle.entry[i].resource`, the pointer back to the exact entry it came from, so
any claim in the final report can be opened and checked against the source bundle.

DocumentReference is handled by `narrative_notes` rather than `load_patient_index`: see that
function for why narrative text is not currently indexable as `Evidence`.
"""

from __future__ import annotations

import base64
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal

from caliper.ir import Code
from caliper.record import Evidence, EvidenceKind, PatientIndex


class FhirBundleError(ValueError):
    """The bundle is not one patient's chart, so no index can honestly be built from it."""


CodeSystem = Literal["LOINC", "SNOMED", "RxNorm", "ICD10", "UCUM"]

_SYSTEM_NAMES: dict[str, CodeSystem] = {
    "http://loinc.org": "LOINC",
    "http://snomed.info/sct": "SNOMED",
    "http://www.nlm.nih.gov/research/umls/rxnorm": "RxNorm",
    "http://unitsofmeasure.org": "UCUM",
}

# ICD-10, ICD-10-CM and the national variants share a URI stem and are one vocabulary to us.
_ICD10_STEM = "http://hl7.org/fhir/sid/icd-10"

# A diagnosis the source system has taken back. Indexing these would let a retracted condition
# decide a screening, which is worse than not knowing about it at all.
_RETRACTED = frozenset({"refuted", "entered-in-error"})


@dataclass(frozen=True)
class _Entry:
    """One bundle entry that carries a resource, paired with its position in the bundle."""

    position: int
    resource: Mapping[str, Any]

    @property
    def resource_type(self) -> str:
        value = self.resource.get("resourceType")
        return value if isinstance(value, str) else ""

    @property
    def resource_id(self) -> str:
        value = self.resource.get("id")
        # An id-less resource still needs a stable handle, and its position is already stable.
        return value if isinstance(value, str) and value else f"entry-{self.position}"

    @property
    def fhir_path(self) -> str:
        return f"Bundle.entry[{self.position}].resource"


def _dig(node: Any, *path: str) -> Any:
    """Walk a chain of keys, returning None the moment the shape stops cooperating."""
    for key in path:
        if not isinstance(node, Mapping):
            return None
        node = node.get(key)
    return node


def _parse_date(value: Any) -> date | None:
    """A FHIR date or dateTime as the calendar day it was written on, or None if unreadable.

    The UTC offset is discarded rather than applied: the day as recorded is the day a coordinator
    reads back off the chart, and normalising would walk late-evening events into the next date.
    Partial dates such as '2018-07' also yield None, since choosing a day would invent precision.
    """
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.strip()).date()
    except ValueError:
        return None


def _first_date(*values: Any) -> date | None:
    for value in values:
        parsed = _parse_date(value)
        if parsed is not None:
            return parsed
    return None


def _system_name(uri: Any) -> CodeSystem | None:
    if not isinstance(uri, str):
        return None
    system = uri.strip().rstrip("/")
    if system.startswith(_ICD10_STEM):
        return "ICD10"
    return _SYSTEM_NAMES.get(system)


def _codings(concept: Any) -> list[Mapping[str, Any]]:
    codings = _dig(concept, "coding")
    if not isinstance(codings, list):
        return []
    return [c for c in codings if isinstance(c, Mapping)]


def _codes(concept: Any) -> tuple[Code, ...]:
    """The codings from a CodeableConcept whose system we recognise, in the order given.

    A system outside the table is dropped whole. Renaming it to the nearest familiar vocabulary
    would make a code look comparable to a protocol's codes when it is not.
    """
    resolved = []
    for coding in _codings(concept):
        system = _system_name(coding.get("system"))
        code = coding.get("code")
        if system is None or not isinstance(code, str) or not code.strip():
            continue
        display = coding.get("display")
        resolved.append(
            Code(
                system=system,
                code=code.strip(),
                display=display.strip() if isinstance(display, str) and display.strip() else None,
            )
        )
    return tuple(resolved)


def _display(concept: Any, fallback: str = "") -> str:
    """The most human-readable label a CodeableConcept offers."""
    text = _dig(concept, "text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    for coding in _codings(concept):
        for key in ("display", "code"):
            value = coding.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return fallback


def _status(concept: Any) -> str | None:
    """The first code of a status CodeableConcept, lowercased."""
    for coding in _codings(concept):
        code = coding.get("code")
        if isinstance(code, str) and code.strip():
            return code.strip().casefold()
    return None


def _quantity(node: Any) -> tuple[float | None, str | None]:
    """A FHIR Quantity as a number and a unit, dropping either half we cannot read."""
    if not isinstance(node, Mapping):
        return None, None
    try:
        value = float(node["value"])
    except (KeyError, TypeError, ValueError):
        value = None
    # `unit` is the printable form; `code` carries the UCUM symbol when no printable form is given.
    candidates = (node.get("unit"), node.get("code"))
    unit = next((u.strip() for u in candidates if isinstance(u, str) and u.strip()), None)
    return value, unit


def _row(
    entry: _Entry,
    kind: EvidenceKind,
    *,
    display: str,
    codes: tuple[Code, ...] = (),
    value: float | None = None,
    unit: str | None = None,
    when: date | None = None,
) -> Evidence:
    return Evidence(
        kind=kind,
        resource_type=entry.resource_type,
        resource_id=entry.resource_id,
        display=display,
        fhir_path=entry.fhir_path,
        codes=codes,
        value=value,
        unit=unit,
        date=when,
    )


def _observations(entry: _Entry) -> list[Evidence]:
    resource = entry.resource
    when = _first_date(resource.get("effectiveDateTime"), resource.get("issued"))
    components = [c for c in (resource.get("component") or ()) if isinstance(c, Mapping)]

    rows = []
    # A panel that carries only components has no value of its own — blood pressure is the common
    # case. Indexing the panel anyway would put a value-free row in front of its own components
    # when the evaluator asks for the most recent matching result.
    if "valueQuantity" in resource or not components:
        value, unit = _quantity(resource.get("valueQuantity"))
        rows.append(
            _row(
                entry,
                "observation",
                display=_display(resource.get("code")),
                codes=_codes(resource.get("code")),
                value=value,
                unit=unit,
                when=when,
            )
        )
    for component in components:
        value, unit = _quantity(component.get("valueQuantity"))
        rows.append(
            _row(
                entry,
                "observation",
                display=_display(component.get("code")),
                codes=_codes(component.get("code")),
                value=value,
                unit=unit,
                when=when,
            )
        )
    return rows


def _conditions(entry: _Entry) -> list[Evidence]:
    resource = entry.resource
    if _status(resource.get("verificationStatus")) in _RETRACTED:
        return []

    statuses = [
        status
        for status in (
            _status(resource.get("clinicalStatus")),
            _status(resource.get("verificationStatus")),
        )
        if status
    ]
    display = _display(resource.get("code"))
    if statuses:
        display = f"{display} ({', '.join(statuses)})"

    return [
        _row(
            entry,
            "condition",
            display=display,
            codes=_codes(resource.get("code")),
            when=_first_date(resource.get("onsetDateTime"), resource.get("recordedDate")),
        )
    ]


def _medications(entry: _Entry) -> list[Evidence]:
    medication = entry.resource.get("medicationCodeableConcept")
    return [
        _row(
            entry,
            "medication",
            display=_display(medication),
            codes=_codes(medication),
            when=_parse_date(entry.resource.get("authoredOn")),
        )
    ]


def _procedures(entry: _Entry) -> list[Evidence]:
    resource = entry.resource
    return [
        _row(
            entry,
            "procedure",
            display=_display(resource.get("code")),
            codes=_codes(resource.get("code")),
            when=_first_date(
                resource.get("performedDateTime"), _dig(resource, "performedPeriod", "start")
            ),
        )
    ]


def _encounters(entry: _Entry) -> list[Evidence]:
    resource = entry.resource
    types = [t for t in (resource.get("type") or ()) if isinstance(t, Mapping)]
    labels = [label for label in (_display(t) for t in types) if label]
    # Synthea leaves `type` off some encounters; the R4 `class` Coding is then all we have.
    class_code = _dig(resource, "class", "code")
    if not labels and isinstance(class_code, str) and class_code.strip():
        labels = [class_code.strip()]
    return [
        _row(
            entry,
            "encounter",
            display=labels[0] if labels else "encounter",
            codes=tuple(code for concept in types for code in _codes(concept)),
            when=_parse_date(_dig(resource, "period", "start")),
        )
    ]


_CONVERTERS: dict[str, Callable[[_Entry], list[Evidence]]] = {
    "Observation": _observations,
    "Condition": _conditions,
    "MedicationRequest": _medications,
    "Procedure": _procedures,
    "Encounter": _encounters,
}


def _entries(bundle: Mapping[str, Any]) -> list[_Entry]:
    """Every entry that actually carries a resource, keeping each one's original position."""
    entries = []
    for position, entry in enumerate(bundle.get("entry") or ()):
        resource = _dig(entry, "resource")
        if isinstance(resource, Mapping) and resource.get("resourceType"):
            entries.append(_Entry(position=position, resource=resource))
    return entries


def load_patient_index(bundle: dict[str, Any]) -> PatientIndex:
    """Flatten one Synthea FHIR R4 transaction bundle into a queryable patient index.

    A bundle is one person's chart, so exactly one Patient resource is required; anything else is
    a `FhirBundleError` rather than a silent choice between candidates. Resource types we have no
    mapping for are skipped, and evidence keeps the bundle's own ordering.
    """
    entries = _entries(bundle)
    patients = [entry for entry in entries if entry.resource_type == "Patient"]
    if len(patients) != 1:
        raise FhirBundleError(
            f"expected exactly one Patient resource in the bundle, found {len(patients)}"
        )

    demographics = patients[0].resource
    gender = demographics.get("gender")
    index = PatientIndex(
        patient_id=patients[0].resource_id,
        birth_date=_parse_date(demographics.get("birthDate")),
        sex=gender.strip() if isinstance(gender, str) and gender.strip() else None,
    )
    for entry in entries:
        convert = _CONVERTERS.get(entry.resource_type)
        if convert is not None:
            index.evidence.extend(convert(entry))
    return index


@dataclass(frozen=True)
class NarrativeNote:
    """Free text decoded out of a DocumentReference, with the pointer back to the resource."""

    resource_id: str
    fhir_path: str
    date: date | None
    text: str


def _attachment_text(attachment: Mapping[str, Any]) -> str | None:
    content_type = attachment.get("contentType")
    if isinstance(content_type, str) and not content_type.strip().startswith("text/"):
        return None
    data = attachment.get("data")
    if not isinstance(data, str) or not data:
        return None
    try:
        # binascii.Error, which strict decoding raises, is a ValueError.
        return base64.b64decode(data, validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None


def narrative_notes(bundle: dict[str, Any]) -> list[NarrativeNote]:
    """Decode the notes carried as base64 attachments on the bundle's DocumentReference resources.

    These are returned separately rather than as `Evidence` because narrative text belongs to no
    member of `EvidenceKind`. Filing a discharge summary under "encounter" would tell
    `PatientIndex.has_documented_activity` that a visit happened, and filing it under "condition"
    would let a note match a coded presence check on its wording alone. Once `EvidenceKind` gains
    a note member these become Evidence rows with `source="narrative"` and `narrative_quote` set,
    with no other change here.
    """
    notes = []
    for entry in _entries(bundle):
        if entry.resource_type != "DocumentReference":
            continue
        paragraphs = []
        for content in entry.resource.get("content") or ():
            attachment = _dig(content, "attachment")
            text = _attachment_text(attachment) if isinstance(attachment, Mapping) else None
            if text:
                paragraphs.append(text)
        if not paragraphs:
            continue
        notes.append(
            NarrativeNote(
                resource_id=entry.resource_id,
                fhir_path=entry.fhir_path,
                date=_parse_date(entry.resource.get("date")),
                text="\n\n".join(paragraphs),
            )
        )
    return notes
