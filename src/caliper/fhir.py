"""Ingestion of Synthea FHIR R4 transaction bundles into a `PatientIndex`.

This is the only place in Caliper that touches raw FHIR, and it is deliberately dumb: it flattens,
it never interprets. A field we cannot read without guessing — an unfamiliar code system, a date
that is not a date, a quantity that is not a number — is dropped rather than approximated, because
a fabricated value here becomes an unarguable verdict three modules later.

Every row keeps `Bundle.entry[i].resource`, the pointer back to the exact entry it came from, so
any claim in the final report can be opened and checked against the source bundle.

DocumentReference is decoded by `narrative_notes` rather than indexed by `load_patient_index`.
Synthea's notes are fill-in-the-blank templates, so indexing them as `kind="note"` would put
boilerplate in front of the extractor and would make `PatientIndex.notes()` non-empty for every
patient, which is not what that question means. Narrative evidence comes from `caliper.notes` and
the hand-authored tree beside the bundles; these are decoded and handed back, and nothing else.
"""

from __future__ import annotations

import base64
import warnings
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

UNRESOLVED_MEDICATION = "unresolved medication reference"
"""Display for a MedicationRequest pointing at a Medication the bundle does not carry.

A blank display would read as a coding failure and would quietly match no concept at all. Naming
the pointer says which resource is missing, so the gap can be closed rather than puzzled over.
"""

NO_MEDICATION_CODE = "medication with no recorded code"
"""Display for a MedicationRequest that names no drug, by reference or otherwise."""

DEAD_WITHOUT_A_DATE = (
    "Patient {patient} is recorded as deceased with no usable deceasedDateTime. The death is "
    "carried as PatientIndex.deceased_undated and will stop the screening, but nothing can be "
    "asked about when it happened."
)


@dataclass(frozen=True)
class _Entry:
    """One bundle entry that carries a resource, paired with its position in the bundle."""

    position: int
    resource: Mapping[str, Any]
    full_url: str | None = None

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


@dataclass(frozen=True)
class _References:
    """Resources that other resources point at, keyed by every form the pointer might take.

    FHIR lets a resource carry its codes inline or hold a reference to a resource elsewhere in the
    same bundle. Resolving those references needs a view of the whole bundle, which a converter
    looking at one entry does not have.
    """

    medications: Mapping[str, Mapping[str, Any]]


def _dig(node: Any, *path: str) -> Any:
    """Walk a chain of keys, returning None the moment the shape stops cooperating."""
    for key in path:
        if not isinstance(node, Mapping):
            return None
        node = node.get(key)
    return node


def parse_date(value: Any) -> date | None:
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
        parsed = parse_date(value)
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


def _observations(entry: _Entry, _references: _References) -> list[Evidence]:
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


def _conditions(entry: _Entry, _references: _References) -> list[Evidence]:
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


def _medications(entry: _Entry, references: _References) -> list[Evidence]:
    resource = entry.resource
    concept = resource.get("medicationCodeableConcept")
    fallback = NO_MEDICATION_CODE

    if concept is None:
        # Synthea writes a third of its MedicationRequests as a reference to a Medication resource
        # carried elsewhere in the same bundle rather than inlining the drug's codes.
        reference = _dig(resource, "medicationReference", "reference")
        if isinstance(reference, str) and reference:
            medication = references.medications.get(reference)
            if medication is None:
                shown = _dig(resource, "medicationReference", "display")
                fallback = (
                    shown.strip()
                    if isinstance(shown, str) and shown.strip()
                    else f"{UNRESOLVED_MEDICATION} {reference}"
                )
            else:
                concept = medication.get("code")

    return [
        _row(
            entry,
            "medication",
            display=_display(concept, fallback=fallback),
            codes=_codes(concept),
            when=parse_date(resource.get("authoredOn")),
        )
    ]


def _procedures(entry: _Entry, _references: _References) -> list[Evidence]:
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


def _encounters(entry: _Entry, _references: _References) -> list[Evidence]:
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
            when=parse_date(_dig(resource, "period", "start")),
        )
    ]


# Medication is deliberately absent: it is a lookup table for MedicationRequest, not a clinical
# event, and indexing it would put a drug on the chart that was never prescribed to anyone.
_CONVERTERS: dict[str, Callable[[_Entry, _References], list[Evidence]]] = {
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
            full_url = _dig(entry, "fullUrl")
            entries.append(
                _Entry(
                    position=position,
                    resource=resource,
                    full_url=full_url if isinstance(full_url, str) and full_url else None,
                )
            )
    return entries


def _medication_lookup(entries: list[_Entry]) -> dict[str, Mapping[str, Any]]:
    """Medication resources keyed by every pointer a MedicationRequest might use to reach them.

    Synthea references them by the entry's `fullUrl` (`urn:uuid:...`), but a bundle assembled by
    anything else may use `Medication/{id}` or the bare id, so all three forms are keyed.
    """
    lookup: dict[str, Mapping[str, Any]] = {}
    for entry in entries:
        if entry.resource_type != "Medication":
            continue
        for key in (entry.full_url, f"Medication/{entry.resource_id}", entry.resource_id):
            if key:
                lookup.setdefault(key, entry.resource)
    return lookup


def load_patient_index(bundle: dict[str, Any]) -> PatientIndex:
    """Flatten one Synthea FHIR R4 transaction bundle into a queryable patient index.

    A bundle is one person's chart, so exactly one Patient resource is required; anything else is
    a `FhirBundleError` rather than a silent choice between candidates. Resource types we have no
    mapping for are skipped, and evidence keeps the bundle's own ordering.

    A death recorded without a date is carried as `deceased_undated` and warned about, rather than
    given a date it does not have; see the comment below.
    """
    entries = _entries(bundle)
    patients = [entry for entry in entries if entry.resource_type == "Patient"]
    if len(patients) != 1:
        raise FhirBundleError(
            f"expected exactly one Patient resource in the bundle, found {len(patients)}"
        )

    patient_id = patients[0].resource_id
    demographics = patients[0].resource
    gender = demographics.get("gender")
    deceased = parse_date(demographics.get("deceasedDateTime"))

    # `deceasedBoolean` is legal FHIR and says the patient is dead without saying when. No date is
    # invented for it: `screen.py` prints a date of death straight into the coordinator's
    # rationale, so a sentinel would surface there as a fact nobody recorded. The death travels as
    # a flag instead, and the missing date is warned about rather than passed over in silence.
    undated_death = deceased is None and demographics.get("deceasedBoolean") is True
    if undated_death:
        warnings.warn(DEAD_WITHOUT_A_DATE.format(patient=patient_id), stacklevel=2)

    index = PatientIndex(
        patient_id=patient_id,
        birth_date=parse_date(demographics.get("birthDate")),
        sex=gender.strip() if isinstance(gender, str) and gender.strip() else None,
        deceased=deceased,
        deceased_undated=undated_death,
    )

    references = _References(medications=_medication_lookup(entries))
    for entry in entries:
        convert = _CONVERTERS.get(entry.resource_type)
        if convert is not None:
            index.evidence.extend(convert(entry, references))
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

    These are returned as plain records rather than folded into the index. `EvidenceKind` does now
    have a "note" member, but `caliper.notes` owns narrative evidence and sources it from the
    hand-authored tree beside the bundles; emitting Synthea's generated prose as note rows as well
    would put boilerplate in front of the extractor and change what `PatientIndex.notes()` means
    for every patient. Whether the bundle's own notes should join them is a decision for the
    corpus, not for the parser, so this hands them back and indexes nothing.
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
                date=parse_date(entry.resource.get("date")),
                text="\n\n".join(paragraphs),
            )
        )
    return notes
