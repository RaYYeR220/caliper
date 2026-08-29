"""The patient side of a screening: a flat, queryable index of everything on the chart.

`Evidence` is the only currency the evaluator accepts. Every row points back at the FHIR resource
it came from, so a verdict can always be traced to something a coordinator can open. Nothing is
summarised, inferred or paraphrased on the way in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from dateutil.relativedelta import relativedelta

from caliper.ir import Code, Concept, TemporalWindow

EvidenceKind = Literal[
    "observation", "condition", "medication", "procedure", "encounter", "note"
]


@dataclass(frozen=True)
class Evidence:
    """One retrievable fact from the chart, with the pointer that lets a human check it."""

    kind: EvidenceKind
    resource_type: str
    resource_id: str
    display: str
    fhir_path: str
    codes: tuple[Code, ...] = ()
    value: float | None = None
    unit: str | None = None
    date: date | None = None
    source: Literal["structured", "narrative"] = "structured"
    narrative_quote: str | None = None

    @property
    def citation(self) -> str:
        stamp = self.date.isoformat() if self.date else "undated"
        if self.value is not None:
            return f"{self.resource_type}/{self.resource_id}: {self.value} {self.unit} ({stamp})"
        return f"{self.resource_type}/{self.resource_id}: {self.display} ({stamp})"


_DELTAS = {
    "days": lambda n: relativedelta(days=n),
    "weeks": lambda n: relativedelta(weeks=n),
    "months": lambda n: relativedelta(months=n),
    "years": lambda n: relativedelta(years=n),
}


def window_start(window: TemporalWindow | None, as_of: date) -> date | None:
    """The earliest date evidence may carry to count, or None when any date will do."""
    if window is None or window.relation in ("ever", "current"):
        return None
    assert window.amount is not None and window.unit is not None
    return as_of - _DELTAS[window.unit](window.amount)


def _in_window(when: date | None, window: TemporalWindow | None, as_of: date) -> bool:
    if window is None or window.relation in ("ever", "current"):
        return True
    if when is None:
        return False
    start = window_start(window, as_of)
    assert start is not None
    if window.relation == "within":
        return start <= when <= as_of
    if window.relation == "before":
        return when < start
    return when > start


def _matches_concept(evidence: Evidence, concept: Concept) -> bool:
    """Prefer a coded match; fall back to the recorded wording only for structured rows.

    The fallback is deliberately unavailable to narrative rows. A note mentioning a condition is
    not a diagnosis: the sentence around the phrase may be a denial, or about a relative. Prose
    earns a verdict only once an extraction step has attached a code to it and taken
    responsibility for reading the sentence, and from then on the code is what matches.
    """
    if concept.codes:
        wanted = {(c.system, c.code) for c in concept.codes}
        return any((c.system, c.code) in wanted for c in evidence.codes)
    if evidence.source == "narrative":
        return False
    return concept.text.casefold() in evidence.display.casefold()


@dataclass
class PatientIndex:
    patient_id: str
    birth_date: date | None
    sex: str | None
    evidence: list[Evidence] = field(default_factory=list)

    def find(
        self,
        kind: EvidenceKind,
        concept: Concept,
        window: TemporalWindow | None,
        as_of: date,
    ) -> list[Evidence]:
        """Every matching row inside the window, most recent first."""
        hits = [
            e
            for e in self.evidence
            if e.kind == kind and _matches_concept(e, concept) and _in_window(e.date, window, as_of)
        ]
        return sorted(hits, key=lambda e: (e.date is not None, e.date or date.min), reverse=True)

    def notes(self) -> list[Evidence]:
        """Raw clinical notes, for the extraction step and for showing a coordinator the source."""
        return [e for e in self.evidence if e.kind == "note"]

    def has_documented_activity(self, window: TemporalWindow | None, as_of: date) -> bool:
        """Whether the chart shows anyone was actually looking during the window.

        This is what separates 'the patient does not have it' from 'nobody wrote anything down'.
        An encounter inside the window is our proxy for the chart having been maintained.
        """
        return any(
            e.kind == "encounter" and _in_window(e.date, window, as_of) for e in self.evidence
        )

    def age_at(self, as_of: date) -> float | None:
        if self.birth_date is None:
            return None
        return relativedelta(as_of, self.birth_date).years
