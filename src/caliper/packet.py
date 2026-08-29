"""The screening packet: the document a coordinator reads, files, and signs.

Nothing here consults a model. Every line is a rearrangement of the structured screening result,
including the rationale sentences, which arrive already written and already checked. What this
module decides is what a person sees first.

That ordering is the whole design. When a screening needs review, the open items come before the
criteria table: a coordinator opens this page to find out what to do next, and burying three
actionable gaps under forty resolved criteria wastes the only thing the tool was built to save. An
ineligible screening is finished, so it leads with the criterion that ended it and does not raise
a worklist for evidence that could no longer change the outcome.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from importlib import resources
from typing import TYPE_CHECKING

from jinja2 import Environment, StrictUndefined

from caliper.evaluate import AbsencePolicy, CriterionResult
from caliper.ir import CriteriaSet, Criterion
from caliper.logic import ScreeningOutcome, Verdict
from caliper.record import Evidence, PatientIndex
from caliper.screen import ScreeningResult

if TYPE_CHECKING:  # Rendering a document must not require the model runtime to be importable.
    from caliper.agents.writer import RationaleSet

DISCLAIMER = (
    "This packet is decision support for pre-screening. Eligibility is determined by the "
    "investigator."
)

VERDICT_LABELS = {
    Verdict.MET: "Met",
    Verdict.NOT_MET: "Not met",
    Verdict.UNKNOWN: "Unresolved",
}

DECISION_WORDS = {
    ScreeningOutcome.ELIGIBLE: "Eligible",
    ScreeningOutcome.INELIGIBLE: "Not eligible",
    ScreeningOutcome.NEEDS_REVIEW: "Needs review before a decision",
}

ABSENCE_POLICY_NOTES = {
    AbsencePolicy.COVERAGE_GATED: (
        "coverage-gated, meaning a finding absent from the chart counts as absent only where "
        "an encounter documents the window"
    ),
    AbsencePolicy.OPEN_WORLD: (
        "open-world, meaning a finding absent from the chart never resolves a criterion"
    ),
    AbsencePolicy.CLOSED_WORLD: (
        "closed-world, meaning a finding absent from the chart is read as absent from the patient"
    ),
}

_VERDICT_SLUGS = {Verdict.MET: "met", Verdict.NOT_MET: "not-met", Verdict.UNKNOWN: "unresolved"}


@dataclass(frozen=True)
class EvidenceLine:
    """One citation as it is printed: what was found, when, and where to open it."""

    resource: str
    description: str
    recorded_on: str
    fhir_path: str

    @property
    def citation(self) -> str:
        return f"{self.resource}, {self.description}, {self.recorded_on}, {self.fhir_path}"


@dataclass(frozen=True)
class CriterionRow:
    criterion_id: str
    kind: str
    quote: str
    verdict: str
    verdict_slug: str
    rationale: str
    engine_written: bool
    evidence: tuple[EvidenceLine, ...] = ()


@dataclass(frozen=True)
class OpenItem:
    """One unresolved criterion, with the work that would close it."""

    criterion_id: str
    quote: str
    missing: str
    where_to_look: str
    fhir_query: str


@dataclass(frozen=True)
class Packet:
    patient_id: str
    patient_summary: str
    nct_id: str
    trial_title: str | None
    screened_on: date
    decision: ScreeningOutcome
    verdict: str
    deciding: tuple[CriterionRow, ...]
    open_items: tuple[OpenItem, ...]
    rows: tuple[CriterionRow, ...]
    absence_policy: AbsencePolicy
    absence_policy_note: str
    criteria_fingerprint: str
    criteria_resolved: int
    criteria_total: int
    engine_written: int
    """How many rationale sentences the screening engine had to write itself."""

    @property
    def trial(self) -> str:
        return f"{self.nct_id} - {self.trial_title}" if self.trial_title else self.nct_id


def build_packet(
    result: ScreeningResult,
    criteria_set: CriteriaSet,
    patient: PatientIndex,
    rationales: RationaleSet,
    *,
    trial_title: str | None = None,
) -> Packet:
    """Assemble the packet for one screening.

    The identifiers are checked against each other first. A packet built from a result and a
    patient that do not belong together is the worst failure this program has — a document about
    the wrong person, correct in every other respect — and it costs two comparisons to refuse.
    """
    if result.patient_id != patient.patient_id:
        raise ValueError(
            f"screening result is for {result.patient_id!r}, patient index for "
            f"{patient.patient_id!r}"
        )
    if result.nct_id != criteria_set.nct_id:
        raise ValueError(
            f"screening result is for {result.nct_id!r}, criteria for {criteria_set.nct_id!r}"
        )

    by_id = {criterion.id: criterion for criterion in criteria_set.criteria}
    rows = tuple(_row(outcome, by_id, rationales) for outcome in result.criteria)
    rows_by_id = {row.criterion_id: row for row in rows}

    deciding: tuple[CriterionRow, ...] = ()
    if result.decision is ScreeningOutcome.INELIGIBLE:
        deciding = tuple(
            rows_by_id[cid] for cid in result.deciding_criterion_ids if cid in rows_by_id
        )

    # Only a screening that is still open raises a worklist. An ineligible patient's remaining
    # gaps are recorded in the criteria table, but chasing them cannot change the outcome.
    open_items: tuple[OpenItem, ...] = ()
    if result.decision is ScreeningOutcome.NEEDS_REVIEW:
        open_items = tuple(
            OpenItem(
                criterion_id=hint.blocks_criterion_id,
                quote=_quote_of(by_id.get(hint.blocks_criterion_id)),
                missing=hint.missing,
                where_to_look=hint.where_to_look,
                fhir_query=hint.fhir_query,
            )
            for hint in result.resolution_worklist
        )

    return Packet(
        patient_id=patient.patient_id,
        patient_summary=_patient_summary(patient, result.screened_on),
        nct_id=result.nct_id,
        trial_title=trial_title,
        screened_on=result.screened_on,
        decision=result.decision,
        verdict=DECISION_WORDS[result.decision],
        deciding=deciding,
        open_items=open_items,
        rows=rows,
        absence_policy=result.absence_policy,
        absence_policy_note=ABSENCE_POLICY_NOTES[result.absence_policy],
        criteria_fingerprint=criteria_set.source_text_sha256,
        criteria_resolved=result.criteria_resolved,
        criteria_total=result.criteria_total,
        engine_written=sum(1 for row in rows if row.engine_written),
    )


def _row(
    outcome: CriterionResult,
    by_id: dict[str, Criterion],
    rationales: RationaleSet,
) -> CriterionRow:
    criterion = by_id.get(outcome.criterion_id)
    if criterion is None:
        raise ValueError(f"no compiled criterion for {outcome.criterion_id!r}")

    rationale = rationales.get(outcome.criterion_id)
    # A missing sentence is recoverable: the evaluator's rationale is always available and always
    # bound to the record. A missing criterion is not, because the quote cannot be reconstructed.
    sentence = rationale.sentence if rationale is not None else outcome.rationale
    engine_written = rationale is None or rationale.source == "fallback"

    return CriterionRow(
        criterion_id=outcome.criterion_id,
        kind=criterion.kind.capitalize(),
        quote=criterion.source_quote,
        verdict=VERDICT_LABELS[outcome.verdict],
        verdict_slug=_VERDICT_SLUGS[outcome.verdict],
        rationale=sentence,
        engine_written=engine_written,
        evidence=tuple(_evidence_line(e) for e in outcome.evidence),
    )


def _evidence_line(evidence: Evidence) -> EvidenceLine:
    description = evidence.display
    if evidence.value is not None:
        unit = f" {evidence.unit}" if evidence.unit else ""
        description = f"{description} {evidence.value:g}{unit}"
    return EvidenceLine(
        resource=f"{evidence.resource_type}/{evidence.resource_id}",
        description=description,
        recorded_on=evidence.date.isoformat() if evidence.date else "not dated",
        fhir_path=evidence.fhir_path,
    )


def _quote_of(criterion: Criterion | None) -> str:
    return criterion.source_quote if criterion is not None else ""


def _patient_summary(patient: PatientIndex, as_of: date) -> str:
    """Age and recorded sex, for the coordinator checking they have the right chart open."""
    parts = []
    age = patient.age_at(as_of)
    if age is not None:
        parts.append(f"{age:g} years old at screening")
    if patient.sex:
        parts.append(f"recorded sex {patient.sex}")
    return ", ".join(parts) if parts else "no demographics on file"


# ------------------------------------------------------------------------------------------------
# Markdown
# ------------------------------------------------------------------------------------------------


def render_markdown(packet: Packet) -> str:
    """The packet as Markdown, for a terminal, a pull request, or an email."""
    lines = [
        "# Screening packet",
        "",
        f"- **Patient:** {packet.patient_id}",
        f"- **Chart:** {packet.patient_summary}",
        f"- **Trial:** {packet.trial}",
        f"- **Screened on:** {packet.screened_on.isoformat()}",
        f"- **Decision:** {packet.verdict}",
        "",
    ]
    lines += _markdown_deciding(packet)
    lines += _markdown_open_items(packet)
    lines += _markdown_table(packet)
    lines += _markdown_footer(packet)
    return "\n".join(lines)


def _markdown_deciding(packet: Packet) -> list[str]:
    if not packet.deciding:
        return []
    lines = ["## Why this patient is not eligible", ""]
    for row in packet.deciding:
        lines += [f"**{row.criterion_id}, {row.kind.lower()} criterion**", ""]
        lines += [f"> {row.quote}", "", row.rationale, ""]
        if row.evidence:
            lines.append("Evidence:")
            lines += [f"- {line.citation}" for line in row.evidence]
            lines.append("")
    return lines


def _markdown_open_items(packet: Packet) -> list[str]:
    if not packet.open_items:
        return []
    count = len(packet.open_items)
    subject = "criterion" if count == 1 else "criteria"
    lines = [
        "## Open items",
        "",
        (
            f"{count} {subject} could not be decided from the record. Each one has to be closed "
            "before this screening can be signed."
        ),
        "",
    ]
    for item in packet.open_items:
        lines += [f"**{item.criterion_id}** {item.quote}", ""]
        lines += [
            f"- Missing: {item.missing}",
            f"- Where to look: {item.where_to_look}",
            f"- FHIR query: `{item.fhir_query}`" if item.fhir_query else "- FHIR query: none",
            "",
        ]
    return lines


def _markdown_table(packet: Packet) -> list[str]:
    lines = [
        "## Criteria",
        "",
        "| ID | Type | Verdict | Protocol text | Rationale | Evidence |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in packet.rows:
        evidence = "; ".join(line.citation for line in row.evidence) or "none on file"
        lines.append(
            "| "
            + " | ".join(
                _cell(value)
                for value in (
                    row.criterion_id,
                    row.kind,
                    row.verdict,
                    row.quote,
                    row.rationale,
                    evidence,
                )
            )
            + " |"
        )
    lines.append("")
    return lines


def _markdown_footer(packet: Packet) -> list[str]:
    return [
        "## About this packet",
        "",
        f"- Absence policy in effect: {packet.absence_policy_note}.",
        f"- Compiled criteria fingerprint: `{packet.criteria_fingerprint}`",
        (
            f"- Resolved {packet.criteria_resolved} of {packet.criteria_total} criteria from the "
            "patient record."
        ),
        f"- {_engine_written_note(packet)}",
        "",
        DISCLAIMER,
        "",
    ]


def _engine_written_note(packet: Packet) -> str:
    if not packet.engine_written:
        return "Every rationale sentence below was checked against the record it describes."
    return (
        f"{packet.engine_written} of {packet.criteria_total} rationale sentences were written by "
        "the screening engine, because the drafted sentence could not be verified against the "
        "record."
    )


def _cell(text: str) -> str:
    """A pipe or a newline inside a cell breaks the table around it."""
    return " ".join(text.split()).replace("|", "\\|")


# ------------------------------------------------------------------------------------------------
# HTML
# ------------------------------------------------------------------------------------------------

_ENVIRONMENT = Environment(
    autoescape=True,  # Patient and protocol text must never be able to inject markup.
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
)

_TEMPLATE = _ENVIRONMENT.from_string(
    resources.files("caliper")
    .joinpath("templates", "packet.html.j2")
    .read_text(encoding="utf-8")
)


def render_html(packet: Packet) -> str:
    """The packet as a single self-contained page: no scripts, no fonts, no requests."""
    return _TEMPLATE.render(packet=packet, disclaimer=DISCLAIMER)
