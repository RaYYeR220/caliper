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
from caliper.logic import CriterionKind, ScreeningOutcome, Verdict
from caliper.record import Evidence, PatientIndex
from caliper.screen import ScreeningResult
from caliper.settlements import Settlement

if TYPE_CHECKING:  # Rendering a document must not require the model runtime to be importable.
    from caliper.agents.writer import RationaleSet

DISCLAIMER = (
    "This packet is decision support for pre-screening. Eligibility is determined by the "
    "investigator."
)

NOTHING_EVALUATED_HEADING = "No criteria were evaluated"

NOTHING_EVALUATED = (
    "No criterion in this protocol was evaluated against this chart, so nothing here says whether "
    "this patient would otherwise have met them."
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

# The class fragment each verdict gets in the HTML rendering, so a stylesheet can colour a row
# without matching on the printed label. Kept apart from `VERDICT_LABELS` because that one is prose
# a reader sees and this one is an identifier a stylesheet depends on; the two must be free to move
# independently. Read by `templates/packet.html.j2`, not from Python.
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
    decisive: bool = False
    """Whether this criterion alone ended the screening."""

    approximations: tuple[str, ...] = ()
    """Where this criterion's verdict rests on something evaluated inexactly."""

    settled_by: Settlement | None = None
    """Set where a person answered this criterion because the record could not."""

    evidence: tuple[EvidenceLine, ...] = ()


@dataclass(frozen=True)
class Caveat:
    """One approximation the screening rests on, and the criteria that leaned on it."""

    text: str
    criterion_ids: tuple[str, ...]

    @property
    def affected(self) -> str:
        """The criteria this approximation touched, as both renderings name them."""
        return ", ".join(self.criterion_ids)


@dataclass(frozen=True)
class OpenItem:
    """One unresolved criterion, with the work that would close it."""

    criterion_id: str
    quote: str
    missing: str
    where_to_look: str
    fhir_query: str


@dataclass(frozen=True)
class VisitCheck:
    """One criterion no record was ever going to settle, put to the patient at the visit instead.

    This is not an open item. An open item is a gap in the chart with somewhere to look; this is a
    question that has no answer until a person is asked it, and chasing the record for it would be
    a coordinator wasting an afternoon on a consent form.
    """

    criterion_id: str
    kind: CriterionKind
    quote: str
    reason: str

    @property
    def can_still_exclude(self) -> bool:
        """An exclusion settled at the visit can still rule the patient out after printing."""
        return self.kind == "exclusion"


@dataclass(frozen=True)
class Packet:
    patient_id: str
    patient_summary: str
    nct_id: str
    trial_title: str | None
    screened_on: date
    decision: ScreeningOutcome
    verdict: str
    blocked_by: str | None
    """Why the screening stopped before any criterion was evaluated, if it did."""

    caveats: tuple[Caveat, ...]
    deciding: tuple[CriterionRow, ...]
    open_items: tuple[OpenItem, ...]
    at_visit: tuple[VisitCheck, ...]
    """Criteria the screening deliberately left to the visit. On an eligible packet, the caveat."""

    settlements: tuple[Settlement, ...]
    """Criteria a person answered because the record could not. Never presented as evidence."""

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

    @property
    def stopped_note(self) -> str | None:
        """The blocking fact as a sentence, for printing beside the verdict.

        `blocked_by` is phrased as a clause about the record; a coordinator opening this page needs
        it as a statement about what happened to their screening.
        """
        if self.blocked_by is None:
            return None
        return f"Screening stopped before any criterion was evaluated, because {self.blocked_by}."

    @property
    def settlement_note(self) -> str | None:
        """The line that qualifies the verdict where a person answered part of it."""
        if not self.settlements:
            return None
        count = len(self.settlements)
        noun = "criterion" if count == 1 else "criteria"
        return f"{count} {noun} on this screening was answered by a person rather than from data."

    def quote_of(self, criterion_id: str) -> str:
        """The protocol's own words for one criterion, as the table prints them."""
        return next(
            (row.quote for row in self.rows if row.criterion_id == criterion_id), criterion_id
        )

    @property
    def caveat_note(self) -> str | None:
        """The line that qualifies the verdict, or None when nothing was approximated.

        A verdict that leaned on an approximation and did not say so is a verdict that comes apart
        in a monitoring visit with nothing on the page to explain why.
        """
        if not self.caveats:
            return None
        count = len(self.caveats)
        noun = "approximation" if count == 1 else "approximations"
        return (
            f"This screening rests on {count} {noun}. The criteria affected are marked in the "
            "table below."
        )

    @property
    def coverage_note(self) -> str:
        """How much of the protocol was actually decided, as both renderings print it."""
        if self.blocked_by is not None:
            return "no criterion was evaluated; the screening stopped before the protocol was run"
        return f"{self.criteria_resolved} of {self.criteria_total} decided from the patient record"

    @property
    def rationale_note(self) -> str | None:
        """How the rationale sentences were arrived at, or None when there are none."""
        if not self.rows:
            return None
        if not self.engine_written:
            return "every sentence was checked against the record it describes"
        return (
            f"{self.engine_written} of {len(self.rows)} were written by the screening engine, "
            "because the drafted sentence could not be verified against the record"
        )


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
    decisive = set(result.deciding_criterion_ids)
    rows = tuple(_row(outcome, by_id, rationales, decisive) for outcome in result.criteria)
    rows_by_id = {row.criterion_id: row for row in rows}

    caveats = tuple(
        Caveat(
            text=text,
            criterion_ids=tuple(r.criterion_id for r in rows if text in r.approximations),
        )
        for text in result.approximations
    )

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

    # A patient the record already excludes is not going to be asked anything, so listing the
    # visit questions on their packet would be busywork dressed as diligence.
    at_visit: tuple[VisitCheck, ...] = ()
    if result.decision is not ScreeningOutcome.INELIGIBLE:
        at_visit = tuple(
            VisitCheck(
                criterion_id=outcome.criterion_id,
                kind=outcome.kind,
                quote=_quote_of(by_id.get(outcome.criterion_id)),
                reason=outcome.rationale,
            )
            for outcome in result.to_confirm_at_visit
        )

    settlements = tuple(row.settled_by for row in rows if row.settled_by is not None)

    return Packet(
        patient_id=patient.patient_id,
        patient_summary=_patient_summary(patient, result.screened_on),
        nct_id=result.nct_id,
        trial_title=trial_title,
        screened_on=result.screened_on,
        decision=result.decision,
        verdict=DECISION_WORDS[result.decision],
        blocked_by=result.blocked_by,
        caveats=caveats,
        deciding=deciding,
        open_items=open_items,
        at_visit=at_visit,
        settlements=settlements,
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
    decisive: set[str],
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
        decisive=outcome.criterion_id in decisive,
        approximations=outcome.approximations,
        settled_by=outcome.settled_by,
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
    """Age and recorded sex, for the coordinator checking they have the right chart open.

    A death the chart records belongs on this line, and it decides how the age is worded. "67 years
    old at screening" is not something to print about someone the chart already had as dead — which
    includes a `deceasedBoolean` carrying no date, where there is nothing to compare against the
    screening date. A death recorded *after* the screening is a different case: the age was true
    when it was taken, so that line keeps "at screening" and reports the death beside it.
    """
    dead_at_screening = patient.died_before(as_of) or patient.deceased_undated
    parts = []
    age = patient.age_at(as_of)
    if age is not None:
        suffix = "" if dead_at_screening else " at screening"
        parts.append(f"{age:g} years old{suffix}")
    if patient.sex:
        parts.append(f"recorded sex {patient.sex}")
    if patient.is_deceased():
        parts.append(
            f"died {patient.deceased.isoformat()}"
            if patient.deceased is not None
            else "recorded as deceased, no date given"
        )
    return ", ".join(parts) if parts else "no demographics on file"


# ------------------------------------------------------------------------------------------------
# Markdown
# ------------------------------------------------------------------------------------------------


def render_markdown(packet: Packet) -> str:
    """The packet as Markdown, for a terminal, a pull request, or an email.

    The same document as `render_html`, and both are kept. A packet that renders only as a page is
    a packet that cannot be pasted into a ticket, diffed between two runs, or read over SSH, and
    the coordinator's copy of a screening decision should not depend on having a browser.
    """
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
    if packet.stopped_note is not None:
        lines += [f"**{packet.stopped_note}**", ""]
    lines += _markdown_caveats(packet)
    lines += _markdown_deciding(packet)
    lines += _markdown_open_items(packet)
    lines += _markdown_settlements(packet)
    lines += _markdown_at_visit(packet)
    lines += _markdown_criteria(packet)
    lines += _markdown_footer(packet)
    return "\n".join(lines)


def _markdown_caveats(packet: Packet) -> list[str]:
    """Directly under the verdict, because it is the verdict that is qualified."""
    if packet.caveat_note is None:
        return []
    lines = ["## Caveats", "", packet.caveat_note, ""]
    for caveat in packet.caveats:
        affected = f" ({caveat.affected})" if caveat.criterion_ids else ""
        lines.append(f"- {caveat.text}{affected}")
    lines.append("")
    return lines


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


def _markdown_settlements(packet: Packet) -> list[str]:
    """Above the criteria table, because these qualify the verdict rather than sit inside it.

    A settled criterion is the one row in the table with a confident sentence and no citation
    under it. Printing the answers together, with the name and the date on each, is what stops a
    reader from taking one for something the chart said.
    """
    if not packet.settlements:
        return []
    lines = [
        "## Answered by a person, not by the record",
        "",
        (
            f"{packet.settlement_note} Each was asked because no chart could settle it. The record "
            "underneath is unchanged, and disagrees with none of them."
        ),
        "",
    ]
    for settlement in packet.settlements:
        answer = "met" if settlement.verdict is Verdict.MET else "not met"
        lines += [
            f"**{settlement.criterion_id}** {packet.quote_of(settlement.criterion_id)}",
            "",
            f"- Answer: {answer}",
            f"- Answered by: {settlement.answered_by} on {settlement.answered_on.isoformat()}",
            f"- Reason given: {settlement.note}",
            "",
        ]
    return lines


def _markdown_at_visit(packet: Packet) -> list[str]:
    """The questions the verdict does not cover.

    Printed after the open items and before the table, because a coordinator holding an eligible
    packet needs to know what they still have to ask before they read forty settled criteria.
    """
    if not packet.at_visit:
        return []
    count = len(packet.at_visit)
    subject = "criterion" if count == 1 else "criteria"
    lines = [
        "## Confirm at the screening visit",
        "",
        (
            f"The decision above does not cover {count} {subject}, because no record could answer "
            "them. Put each one to the patient in person."
        ),
        "",
    ]
    for check in packet.at_visit:
        lines.append(f"- **{check.criterion_id}** {check.quote}")
        if check.can_still_exclude:
            lines.append("  - An exclusion: a yes here can still rule this patient out.")
    lines.append("")
    return lines


def _markdown_criteria(packet: Packet) -> list[str]:
    if packet.stopped_note is not None:
        # A table headed "Criteria" with nothing under it reads as a broken program rather than
        # as an answer, and the answer here is that the protocol was never applied.
        return [
            f"## {NOTHING_EVALUATED_HEADING}",
            "",
            packet.stopped_note,
            "",
            NOTHING_EVALUATED,
            "",
        ]

    lines = [
        "## Criteria",
        "",
        "| ID | Type | Verdict | Protocol text | Rationale | Evidence |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in packet.rows:
        evidence = "; ".join(line.citation for line in row.evidence) or "none on file"
        tags = _tags(row)
        identifier = f"{row.criterion_id} ({', '.join(tags)})" if tags else row.criterion_id
        lines.append(
            "| "
            + " | ".join(
                _cell(value)
                for value in (
                    identifier,
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
    lines = [
        "## About this packet",
        "",
        f"- Absence policy in effect: {packet.absence_policy_note}.",
        f"- Compiled criteria fingerprint: `{packet.criteria_fingerprint}`",
        f"- Criteria: {packet.coverage_note}.",
    ]
    if packet.rationale_note is not None:
        lines.append(f"- Rationale sentences: {packet.rationale_note}.")
    lines += ["", DISCLAIMER, ""]
    return lines


def _tags(row: CriterionRow) -> list[str]:
    """What a reader needs to see about a row beyond its verdict."""
    tags = []
    if row.decisive:
        tags.append("decisive")
    if row.approximations:
        tags.append("approximated")
    if row.settled_by is not None:
        tags.append("settled by a person")
    return tags


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
    resources.files("caliper").joinpath("templates", "packet.html.j2").read_text(encoding="utf-8")
)


def render_html(packet: Packet) -> str:
    """The packet as a single self-contained page: no scripts, no fonts, no requests."""
    return _TEMPLATE.render(
        packet=packet,
        disclaimer=DISCLAIMER,
        nothing_evaluated_heading=NOTHING_EVALUATED_HEADING,
        nothing_evaluated=NOTHING_EVALUATED,
    )
