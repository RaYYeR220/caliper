"""Turning a run into the JSON the coordinator interface reads.

The interface in `web/` is the printed packet's interactive sibling. It is a static page — no
server, no build step — so everything it knows has to arrive as a file written here, which makes
this module the whole contract between the run and the screen.

It is written to lose nothing. Every criterion, every evidence pointer, every approximation and
every resolution hint is exported, including for screenings where the packet would not print them,
because a viewer that has to go back to Python to answer a coordinator's question is not a viewer
of this system. The packet's own ordering rules are preserved rather than reimplemented: the
screening export calls `build_packet`, so the page and the printout are the same document.

Nothing here escapes, truncates or prettifies. A string that arrived as protocol text leaves as
protocol text, byte for byte; escaping belongs to whatever renders it, and a value the exporter had
already mangled could not be un-mangled downstream.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from caliper.agents.critic import Coverage, Finding, coverage_report, render_predicate
from caliper.agents.writer import RationaleSet, deterministic_rationales
from caliper.criteria_text import CriterionSpan, segment
from caliper.evaluate import CriterionResult
from caliper.ir import (
    Code,
    CriteriaSet,
    Criterion,
    Predicate,
    UnsupportedPredicate,
    concepts_of,
)
from caliper.packet import (
    ABSENCE_POLICY_NOTES,
    DISCLAIMER,
    VERDICT_LABELS,
    OpenItem,
    VisitCheck,
    build_packet,
)
from caliper.pipeline import CompiledTrial, Screening
from caliper.record import Evidence, PatientIndex

SCHEMA_TRIAL = "caliper.ui.trial/1"
SCHEMA_SCREENING = "caliper.ui.screening/1"
SCHEMA_INDEX = "caliper.ui.index/1"

DATA_DIRNAME = "data"
"""Where a bundle lands under the web root, so the page's source and a run's output stay apart."""

INDEX_NAME = "index.json"


@dataclass(frozen=True)
class ScreeningRecord:
    """One screening plus the two things a `Screening` does not carry.

    The chart is needed because the packet refuses to be built from a result and a patient that do
    not belong together, and the title because `CompiledTrial` knows an NCT number and nothing else.
    """

    screening: Screening
    patient: PatientIndex
    trial_title: str


# ------------------------------------------------------------------------------------------------
# Pieces
# ------------------------------------------------------------------------------------------------


def _code(code: Code) -> dict[str, Any]:
    return {"system": code.system, "code": code.code, "display": code.display}


def _codes_of(predicate: Predicate) -> list[dict[str, Any]]:
    """The terminology attached to a predicate, de-duplicated, in the order it was resolved.

    `ir.concepts_of` does the walk. It used to be copied into this module, which meant the review
    screen and the terminology count could disagree about what a nested composite mentions.
    """
    seen: dict[tuple[str, str], Code] = {}
    for concept in concepts_of(predicate):
        for code in concept.codes:
            seen.setdefault((code.system, code.code), code)
    return [_code(code) for code in seen.values()]


def _critic(finding: Finding | None) -> dict[str, Any] | None:
    if finding is None:
        return None
    return {
        "severity": finding.severity,
        "reason": finding.reason,
        "downgraded": finding.is_downgrade,
        # The English the critic actually compared, which for a downgraded criterion is the only
        # surviving record of what the compiler had produced: `apply_findings` has since replaced
        # the predicate, so re-rendering it would return the downgrade notice instead.
        "reviewed_rendering": finding.rendered,
        "reviewed_quote": finding.quote,
    }


def _criterion(criterion: Criterion, finding: Finding | None) -> dict[str, Any]:
    predicate = criterion.predicate
    unsupported = predicate if isinstance(predicate, UnsupportedPredicate) else None
    return {
        "id": criterion.id,
        "kind": criterion.kind,
        "source_quote": criterion.source_quote,
        "notes": criterion.notes,
        "predicate_type": predicate.type,
        "compiled_as": render_predicate(predicate),
        "unsupported": unsupported is not None,
        "unsupported_reason": unsupported.reason if unsupported is not None else None,
        "codes": _codes_of(predicate),
        "critic": _critic(finding),
    }


def _span(span: CriterionSpan, claim: str) -> dict[str, Any]:
    return {
        "index": span.index,
        "section": span.section.value,
        "text": span.text,
        "parent_index": span.parent_index,
        "claim": claim,
    }


def _coverage(criteria_set: CriteriaSet, coverage: Coverage) -> dict[str, Any]:
    """Which spans of the protocol a criterion claims, span by span and in document order.

    The report on its own carries only the spans that failed. The interface draws the whole
    protocol as a scale, so every span is exported with the strength of its claim: `direct` where a
    criterion quotes it, `inherited` where only its parent was quoted, `unclaimed` where nobody
    went near it.
    """
    direct = set(coverage.direct_span_indices)
    inherited = set(coverage.inherited_span_indices)
    spans = []
    for span in segment(criteria_set.source_text):
        if span.index in direct:
            claim = "direct"
        elif span.index in inherited:
            claim = "inherited"
        else:
            claim = "unclaimed"
        spans.append(_span(span, claim))

    return {
        "total": coverage.total_spans,
        "claimed": len(coverage.claimed_span_indices),
        "direct": len(direct),
        "inherited": len(inherited),
        "unclaimed": len(coverage.unclaimed_spans),
        "ratio": coverage.coverage,
        "spans": spans,
        "quote_problems": [
            {"criterion_id": p.criterion_id, "quote": p.quote, "reason": p.reason}
            for p in coverage.quote_problems
        ],
    }


def _evidence(evidence: Evidence) -> dict[str, Any]:
    """One citation with everything needed to open it: the value, the date, and the pointer."""
    return {
        "resource": f"{evidence.resource_type}/{evidence.resource_id}",
        "resource_type": evidence.resource_type,
        "resource_id": evidence.resource_id,
        "kind": evidence.kind,
        "display": evidence.display,
        "value": evidence.value,
        "unit": evidence.unit,
        "date": evidence.date.isoformat() if evidence.date else None,
        "fhir_path": evidence.fhir_path,
        "source": evidence.source,
        "narrative_quote": evidence.narrative_quote,
        "codes": [_code(code) for code in evidence.codes],
    }


def _resolution(result: CriterionResult) -> dict[str, Any] | None:
    hint = result.resolution_hint
    if hint is None:
        return None
    return {
        "missing": hint.missing,
        "where_to_look": hint.where_to_look,
        "fhir_query": hint.fhir_query,
        # The evaluator leaves the query empty for a criterion no query can settle. That
        # distinction is what the queue ranks on, so it is exported as a fact rather than left for
        # the page to infer from an empty string.
        "retrievable": bool(hint.fhir_query),
    }


def _result(
    result: CriterionResult,
    by_id: dict[str, Criterion],
    rationales: RationaleSet,
    decisive: set[str],
) -> dict[str, Any]:
    criterion = by_id.get(result.criterion_id)
    rationale = rationales.get(result.criterion_id)
    engine_written = rationale is None or rationale.source == "fallback"
    return {
        "id": result.criterion_id,
        "kind": result.kind,
        "quote": criterion.source_quote if criterion is not None else "",
        "unsupported": (
            criterion is not None and isinstance(criterion.predicate, UnsupportedPredicate)
        ),
        "verdict": result.verdict.value,
        "verdict_label": VERDICT_LABELS[result.verdict],
        "decisive": result.criterion_id in decisive,
        "rationale": rationale.sentence if rationale is not None else result.rationale,
        "rationale_source": rationale.source if rationale is not None else "fallback",
        "fallback_reason": rationale.fallback_reason if rationale is not None else None,
        "engine_written": engine_written,
        "approximations": list(result.approximations),
        "evidence": [_evidence(e) for e in result.evidence],
        "resolution": _resolution(result),
    }


def _open_item(item: OpenItem) -> dict[str, Any]:
    return {
        "criterion_id": item.criterion_id,
        "quote": item.quote,
        "missing": item.missing,
        "where_to_look": item.where_to_look,
        "fhir_query": item.fhir_query,
        "retrievable": bool(item.fhir_query),
    }


# ------------------------------------------------------------------------------------------------
# Documents
# ------------------------------------------------------------------------------------------------


def _visit_check(check: VisitCheck) -> dict[str, Any]:
    return {
        "criterion_id": check.criterion_id,
        "kind": check.kind,
        "quote": check.quote,
        "reason": check.reason,
        "can_still_exclude": check.can_still_exclude,
    }


def export_trial(trial: CompiledTrial, trial_title: str) -> dict[str, Any]:
    """One trial's compilation, as the criteria review screen reads it.

    Approving a compilation is a per-trial act: a coordinator who has read these criteria once has
    read them for every patient screened against them, which is why this document exists separately
    from the screenings that cite it.
    """
    criteria_set = trial.criteria_set
    report = trial.critic_report
    findings = {f.criterion_id: f for f in report.findings} if report is not None else {}
    config = trial.config

    criteria = [_criterion(c, findings.get(c.id)) for c in criteria_set.criteria]
    return {
        "schema": SCHEMA_TRIAL,
        "nct_id": trial.nct_id,
        "title": trial_title,
        "criteria_fingerprint": criteria_set.source_text_sha256,
        "source_text": criteria_set.source_text,
        "counts": {
            "criteria": len(criteria),
            "inclusion": sum(1 for c in criteria if c["kind"] == "inclusion"),
            "exclusion": sum(1 for c in criteria if c["kind"] == "exclusion"),
            "unsupported": criteria_set.unsupported_count,
            "reviewed": len(findings),
            "downgraded": len(report.downgrades) if report is not None else 0,
        },
        "critic_ran": report is not None,
        "criteria": criteria,
        "coverage": _coverage(criteria_set, coverage_report(criteria_set)),
        "terminology": [
            {"text": text, "codes": [_code(code) for code in codes]}
            for text, codes in sorted((trial.resolved_codes or {}).items())
        ],
        "spans_unaccounted": list(trial.compilation.spans_unaccounted),
        "config": {
            "label": config.label,
            "resolver": config.use_resolver,
            "critic": config.use_critic,
            "rationales": config.write_rationales,
            "narrative": config.use_narrative,
            "absence_policy": config.absence_policy.value,
        },
    }


def export_screening(
    screening: Screening, patient: PatientIndex, trial_title: str
) -> dict[str, Any]:
    """One patient against one trial, as the packet screen reads it.

    `build_packet` decides what leads and what the open items are, so that the page cannot drift
    from the document a coordinator signs. Everything the packet flattens for print — the verdict
    enum, the evidence value and unit as separate fields, the resolution hint behind every
    unresolved criterion — is exported alongside it from the screening result itself.
    """
    result = screening.result
    criteria_set = screening.trial.criteria_set
    rationales = screening.rationales or deterministic_rationales(result)
    packet = build_packet(result, criteria_set, patient, rationales, trial_title=trial_title)

    by_id = {criterion.id: criterion for criterion in criteria_set.criteria}
    decisive = set(result.deciding_criterion_ids)

    return {
        "schema": SCHEMA_SCREENING,
        "nct_id": result.nct_id,
        "trial_title": trial_title,
        "criteria_fingerprint": packet.criteria_fingerprint,
        "patient": {
            "id": patient.patient_id,
            "summary": packet.patient_summary,
            "age": patient.age_at(result.screened_on),
            "sex": patient.sex,
        },
        "screened_on": result.screened_on.isoformat(),
        "decision": result.decision.value,
        "decision_label": packet.verdict,
        # A screening the evaluator stopped before any criterion was read. The criteria list is
        # then legitimately empty, and the interface has to say why rather than draw a blank table.
        "blocked_by": result.blocked_by,
        "criteria_total": result.criteria_total,
        "criteria_resolved": result.criteria_resolved,
        "coverage": result.coverage,
        "deciding_criterion_ids": list(result.deciding_criterion_ids),
        "approximations": list(result.approximations),
        # The same approximations, each with the criteria that leaned on it. The packet groups them
        # this way because "which verdict does this touch" is the reader's next question, and the
        # page has no business answering it differently from the document.
        "caveats": [
            {"text": caveat.text, "criterion_ids": list(caveat.criterion_ids)}
            for caveat in packet.caveats
        ],
        "absence_policy": {
            "value": result.absence_policy.value,
            "note": ABSENCE_POLICY_NOTES[result.absence_policy],
        },
        "open_items": [_open_item(item) for item in packet.open_items],
        # Not open items. A question no chart was ever going to answer has nowhere to look and no
        # query behind it, and putting it in the worklist would send a coordinator hunting a
        # consent form through the record.
        "at_visit": [_visit_check(check) for check in packet.at_visit],
        "criteria": [_result(r, by_id, rationales, decisive) for r in result.criteria],
        "rationales": {"total": result.criteria_total, "engine_written": packet.engine_written},
        "disclaimer": DISCLAIMER,
    }


# ------------------------------------------------------------------------------------------------
# Bundle
# ------------------------------------------------------------------------------------------------


def trial_filename(nct_id: str) -> str:
    return f"{nct_id}.trial.json"


def screening_filename(nct_id: str, patient_id: str) -> str:
    return f"{nct_id}--{patient_id}.json"


def _trial_entry(payload: dict[str, Any]) -> dict[str, Any]:
    counts = payload["counts"]
    return {
        "nct_id": payload["nct_id"],
        "title": payload["title"],
        "file": trial_filename(payload["nct_id"]),
        "criteria_fingerprint": payload["criteria_fingerprint"],
        "criteria": counts["criteria"],
        "unsupported": counts["unsupported"],
        "downgraded": counts["downgraded"],
        "coverage": payload["coverage"]["ratio"],
    }


def _screening_entry(payload: dict[str, Any]) -> dict[str, Any]:
    """The row the queue draws, so that a cohort of any size costs one request.

    The two open-item counts are kept apart rather than summed. A gap a FHIR query would close is a
    phone call; a gap that needs a person reading the protocol is not, and a queue that ranked them
    together would send a coordinator to the patient it can help least.
    """
    open_items = payload["open_items"]
    retrievable = [item for item in open_items if item["retrievable"]]
    blocking = retrievable[0] if retrievable else (open_items[0] if open_items else None)
    return {
        "nct_id": payload["nct_id"],
        "patient_id": payload["patient"]["id"],
        "file": screening_filename(payload["nct_id"], payload["patient"]["id"]),
        "patient_summary": payload["patient"]["summary"],
        "screened_on": payload["screened_on"],
        "decision": payload["decision"],
        "decision_label": payload["decision_label"],
        "blocked_by": payload["blocked_by"],
        "criteria_total": payload["criteria_total"],
        "criteria_resolved": payload["criteria_resolved"],
        "open_items": len(open_items),
        "open_retrievable": len(retrievable),
        "open_needing_a_person": len(open_items) - len(retrievable),
        "blocking": blocking["missing"] if blocking else None,
        "blocking_criterion_id": blocking["criterion_id"] if blocking else None,
        "deciding_criterion_ids": payload["deciding_criterion_ids"],
        "approximations": len(payload["approximations"]),
        "at_visit": len(payload["at_visit"]),
    }


def _write(path: Path, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    # Binary mode: text mode would rewrite "\n" as "\r\n" on Windows, so the same run would produce
    # different bytes on different machines and the bundle would show up as a diff for no reason.
    path.write_bytes((text + "\n").encode("utf-8"))


def write_ui_bundle(screenings: Iterable[ScreeningRecord], *, root: Path) -> list[Path]:
    """Write one file per screening, one per trial, and the index that lists them all.

    `root` is the directory a reviewer serves — `web/` — and the bundle lands in `root/data`.
    Records are written in the order given, which is what makes a regenerated bundle byte-identical
    to the one it replaces.
    """
    data = Path(root) / DATA_DIRNAME
    data.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    trial_entries: list[dict[str, Any]] = []
    screening_entries: list[dict[str, Any]] = []
    seen_trials: set[str] = set()

    for record in screenings:
        trial = record.screening.trial
        if trial.nct_id not in seen_trials:
            seen_trials.add(trial.nct_id)
            payload = export_trial(trial, record.trial_title)
            path = data / trial_filename(trial.nct_id)
            _write(path, payload)
            written.append(path)
            trial_entries.append(_trial_entry(payload))

        payload = export_screening(record.screening, record.patient, record.trial_title)
        path = data / screening_filename(payload["nct_id"], payload["patient"]["id"])
        _write(path, payload)
        written.append(path)
        screening_entries.append(_screening_entry(payload))

    index = data / INDEX_NAME
    _write(
        index,
        {
            "schema": SCHEMA_INDEX,
            "trials": trial_entries,
            "screenings": screening_entries,
            "disclaimer": DISCLAIMER,
        },
    )
    written.append(index)
    return written
