"""Deterministic evaluation of one compiled criterion against one patient.

No language model is reachable from this module, by construction. Everything here is a pure
function of the compiled criterion, the patient index and the screening date — which is what makes
a verdict arguable in a monitoring visit rather than merely plausible.

Absence is the hard part. A chart that does not mention myocardial infarction may mean the patient
never had one, or may mean nobody wrote it down. `AbsencePolicy` names that choice instead of
burying it: the default accepts absence only where the chart shows someone was looking.
"""

from __future__ import annotations

import operator
from dataclasses import dataclass, replace
from datetime import date
from enum import Enum

from caliper.ir import (
    CompositePredicate,
    Criterion,
    DemographicPredicate,
    ObservationPredicate,
    Predicate,
    PresencePredicate,
    UnsupportedPredicate,
)
from caliper.logic import Verdict
from caliper.record import Evidence, PatientIndex, window_start
from caliper.units import convert


class AbsencePolicy(Enum):
    """How to read silence in the chart."""

    COVERAGE_GATED = "coverage_gated"
    """Absence counts only where an encounter documents the window. The default."""

    OPEN_WORLD = "open_world"
    """Silence never resolves anything. Safest, and unusably conservative on real charts."""

    CLOSED_WORLD = "closed_world"
    """Silence means absent. What a naive implementation does implicitly."""


@dataclass(frozen=True)
class ResolutionHint:
    """What a coordinator would have to find for an unresolved criterion to resolve.

    Abstention that does not say what is missing just moves the work without reducing it.
    """

    missing: str
    where_to_look: str
    fhir_query: str
    blocks_criterion_id: str


@dataclass(frozen=True)
class CriterionResult:
    criterion_id: str
    kind: str
    verdict: Verdict
    rationale: str
    evidence: tuple[Evidence, ...] = ()
    resolution_hint: ResolutionHint | None = None
    approximations: tuple[str, ...] = ()
    """Places where the verdict rests on something we could not evaluate exactly."""

    blocking: bool = True
    """Whether being unresolved here should stop a screening.

    False for a criterion the record was never going to answer — consent, a procedure planned after
    randomisation, the investigator's judgement at the visit. Those are confirmed when the patient
    comes in; holding the whole screening for them decides nothing about anybody.
    """


_COMPARISONS = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "==": operator.eq,
    "!=": operator.ne,
}

_RESOURCE_FOR = {
    "condition": "Condition",
    "medication": "MedicationRequest",
    "procedure": "Procedure",
}

_KIND_LOCATIONS = {
    "observation": "the laboratory result system or the most recent panel in the chart",
    "condition": "the problem list and recent discharge summaries",
    "medication": "the medication list and the last medication reconciliation",
    "procedure": "the procedure history and operative notes",
}


def _query(index: PatientIndex, resource: str, predicate: Predicate, since: date | None) -> str:
    """A FHIR search a coordinator could paste into their own system to close the gap."""
    concept = getattr(predicate, "concept", None)
    code_part = ""
    if concept is not None and concept.codes:
        code_part = "&code=" + ",".join(c.code for c in concept.codes)
    date_part = f"&date=ge{since.isoformat()}" if since else ""
    return f"{resource}?patient={index.patient_id}{code_part}{date_part}"


def _anchor_caveats(predicate: Predicate) -> tuple[str, ...]:
    """Note any window anchored to an event other than screening."""
    window = getattr(predicate, "window", None)
    if window is None or window.anchor == "screening":
        return ()
    return (
        f"the protocol anchors this window to {window.anchor}, "
        "which was evaluated against the screening date",
    )


def _unresolved(
    criterion: Criterion,
    *,
    missing: str,
    where: str,
    query: str,
    rationale: str,
    evidence: tuple[Evidence, ...] = (),
    approximations: tuple[str, ...] = (),
    blocking: bool = True,
) -> CriterionResult:
    return CriterionResult(
        criterion_id=criterion.id,
        kind=criterion.kind,
        verdict=Verdict.UNKNOWN,
        rationale=rationale,
        evidence=evidence,
        approximations=approximations,
        blocking=blocking,
        resolution_hint=ResolutionHint(
            missing=missing,
            where_to_look=where,
            fhir_query=query,
            blocks_criterion_id=criterion.id,
        ),
    )


def _resolved(
    criterion: Criterion,
    verdict: Verdict,
    rationale: str,
    evidence: tuple[Evidence, ...] = (),
    approximations: tuple[str, ...] = (),
) -> CriterionResult:
    return CriterionResult(
        criterion_id=criterion.id,
        kind=criterion.kind,
        verdict=verdict,
        rationale=rationale,
        evidence=evidence,
        approximations=approximations,
    )


def _evaluate_observation(
    criterion: Criterion, predicate: ObservationPredicate, index: PatientIndex, as_of: date
) -> CriterionResult:
    since = window_start(predicate.window, as_of)
    matches = index.find("observation", predicate.concept, predicate.window, as_of)
    if not matches:
        return _unresolved(
            criterion,
            missing=f"a {predicate.concept.text} result",
            where=_KIND_LOCATIONS["observation"],
            query=_query(index, "Observation", predicate, since),
            rationale=f"no {predicate.concept.text} result is on file for the required window",
        )

    latest = matches[0]
    if latest.value is None or latest.unit is None:
        return _unresolved(
            criterion,
            missing=f"a numeric value for {predicate.concept.text}",
            where=_KIND_LOCATIONS["observation"],
            query=_query(index, "Observation", predicate, since),
            rationale="the most recent matching result carries no numeric value",
            evidence=(latest,),
        )

    value = convert(latest.value, latest.unit, predicate.unit, predicate.concept.codes)
    if value is None:
        return _unresolved(
            criterion,
            missing=(
                f"{predicate.concept.text} in {predicate.unit} "
                f"(the chart reports {latest.unit}, which we cannot convert)"
            ),
            where=_KIND_LOCATIONS["observation"],
            query=_query(index, "Observation", predicate, since),
            rationale=f"cannot convert {latest.unit} to {predicate.unit} for this analyte",
            evidence=(latest,),
        )

    if predicate.op == "between":
        assert predicate.value_high is not None
        satisfied = predicate.value <= value <= predicate.value_high
        bound = f"between {predicate.value} and {predicate.value_high} {predicate.unit}"
    else:
        satisfied = _COMPARISONS[predicate.op](value, predicate.value)
        bound = f"{predicate.op} {predicate.value} {predicate.unit}"

    return _resolved(
        criterion,
        Verdict.MET if satisfied else Verdict.NOT_MET,
        f"{value:g} {predicate.unit} on {latest.date} against {bound}",
        (latest,),
    )


def _evaluate_presence(
    criterion: Criterion,
    predicate: PresencePredicate,
    index: PatientIndex,
    as_of: date,
    policy: AbsencePolicy,
) -> CriterionResult:
    since = window_start(predicate.window, as_of)
    resource = _RESOURCE_FOR[predicate.type]
    matches = index.find(predicate.type, predicate.concept, predicate.window, as_of)

    if matches:
        found_means_met = predicate.presence == "present"
        return _resolved(
            criterion,
            Verdict.MET if found_means_met else Verdict.NOT_MET,
            f"{predicate.concept.text} is documented ({matches[0].citation})",
            (matches[0],),
        )

    if policy is AbsencePolicy.OPEN_WORLD:
        documented = False
    elif policy is AbsencePolicy.CLOSED_WORLD:
        documented = True
    else:
        documented = index.has_documented_activity(predicate.window, as_of)

    if not documented:
        return _unresolved(
            criterion,
            missing=(
                f"confirmation that {predicate.concept.text} is genuinely absent "
                "rather than merely unrecorded"
            ),
            where=_KIND_LOCATIONS[predicate.type],
            query=_query(index, resource, predicate, since),
            rationale=(
                f"nothing documents {predicate.concept.text} in the required window, and the "
                "chart does not show the window was covered"
            ),
        )

    absent_means_met = predicate.presence == "absent"
    return _resolved(
        criterion,
        Verdict.MET if absent_means_met else Verdict.NOT_MET,
        f"{predicate.concept.text} is not documented in a window the chart covers",
    )


def _evaluate_demographic(
    criterion: Criterion, predicate: DemographicPredicate, index: PatientIndex, as_of: date
) -> CriterionResult:
    if predicate.field == "age":
        age = index.age_at(as_of)
        if age is None:
            return _unresolved(
                criterion,
                missing="the patient's date of birth",
                where="the patient demographics record",
                query=f"Patient/{index.patient_id}",
                rationale="no date of birth is recorded, so age cannot be computed",
            )
        satisfied = _COMPARISONS[predicate.op](age, float(predicate.value))
        return _resolved(
            criterion,
            Verdict.MET if satisfied else Verdict.NOT_MET,
            f"age {age:g} years at screening against {predicate.op} {predicate.value}",
        )

    if index.sex is None:
        return _unresolved(
            criterion,
            missing="the patient's recorded sex",
            where="the patient demographics record",
            query=f"Patient/{index.patient_id}",
            rationale="no sex is recorded",
        )
    equal = index.sex.casefold() == str(predicate.value).casefold()
    satisfied = equal if predicate.op == "==" else not equal
    return _resolved(
        criterion,
        Verdict.MET if satisfied else Verdict.NOT_MET,
        f"recorded sex {index.sex!r} against {predicate.op} {predicate.value!r}",
    )


_FLIPPED = {
    Verdict.MET: Verdict.NOT_MET,
    Verdict.NOT_MET: Verdict.MET,
    Verdict.UNKNOWN: Verdict.UNKNOWN,
}


def _evaluate_composite(
    criterion: Criterion,
    predicate: CompositePredicate,
    index: PatientIndex,
    as_of: date,
    policy: AbsencePolicy,
) -> CriterionResult:
    """Combine member verdicts under Kleene's strong three-valued logic.

    The rule worth stating out loud: a decisive member settles the composite even when a sibling is
    unresolved. One failed member of a conjunction cannot be rescued by whatever the unknown member
    turns out to be, so the conjunction is NOT_MET rather than UNKNOWN — and abstaining there would
    send a coordinator to the chart for an answer that could not change anything.
    """
    members = [
        _evaluate_predicate(criterion, operand, index, as_of, policy)
        for operand in predicate.operands
    ]
    verdicts = [m.verdict for m in members]

    if predicate.type == "not":
        member = members[0]
        return CriterionResult(
            criterion_id=criterion.id,
            kind=criterion.kind,
            verdict=_FLIPPED[member.verdict],
            rationale=f"not ({member.rationale})",
            evidence=member.evidence,
            resolution_hint=member.resolution_hint,
            approximations=member.approximations,
        )

    decisive = Verdict.NOT_MET if predicate.type == "all_of" else Verdict.MET
    joiner = " and " if predicate.type == "all_of" else " or "

    if decisive in verdicts:
        settling = [m for m in members if m.verdict is decisive]
        return CriterionResult(
            criterion_id=criterion.id,
            kind=criterion.kind,
            verdict=decisive,
            rationale=joiner.join(m.rationale for m in settling),
            evidence=tuple(e for m in settling for e in m.evidence),
            approximations=tuple(a for m in settling for a in m.approximations),
        )

    unresolved = [m for m in members if m.verdict is Verdict.UNKNOWN]
    if unresolved:
        return CriterionResult(
            criterion_id=criterion.id,
            kind=criterion.kind,
            verdict=Verdict.UNKNOWN,
            rationale=joiner.join(m.rationale for m in members),
            evidence=tuple(e for m in members for e in m.evidence),
            resolution_hint=unresolved[0].resolution_hint,
            approximations=tuple(a for m in members for a in m.approximations),
            # A composite is only deferrable if every unresolved member is: one real data gap
            # inside it is still a data gap.
            blocking=any(m.blocking for m in unresolved),
        )

    return CriterionResult(
        criterion_id=criterion.id,
        kind=criterion.kind,
        verdict=Verdict.MET if predicate.type == "all_of" else Verdict.NOT_MET,
        rationale=joiner.join(m.rationale for m in members),
        evidence=tuple(e for m in members for e in m.evidence),
        approximations=tuple(a for m in members for a in m.approximations),
    )


def evaluate_criterion(
    criterion: Criterion,
    index: PatientIndex,
    as_of: date,
    policy: AbsencePolicy = AbsencePolicy.COVERAGE_GATED,
) -> CriterionResult:
    """Decide one criterion for one patient on one date."""
    return _evaluate_predicate(criterion, criterion.predicate, index, as_of, policy)


def _evaluate_predicate(
    criterion: Criterion,
    predicate: Predicate,
    index: PatientIndex,
    as_of: date,
    policy: AbsencePolicy,
) -> CriterionResult:
    result = _dispatch(criterion, predicate, index, as_of, policy)
    caveats = _anchor_caveats(predicate)
    if not caveats:
        return result
    return replace(result, approximations=result.approximations + caveats)


def _dispatch(
    criterion: Criterion,
    predicate: Predicate,
    index: PatientIndex,
    as_of: date,
    policy: AbsencePolicy,
) -> CriterionResult:
    if isinstance(predicate, CompositePredicate):
        return _evaluate_composite(criterion, predicate, index, as_of, policy)

    if isinstance(predicate, UnsupportedPredicate):
        at_visit = predicate.settlement == "at_visit"
        return _unresolved(
            criterion,
            missing=(
                f"confirmation at the screening visit: {predicate.reason}"
                if at_visit
                else f"human judgement: {predicate.reason}"
            ),
            where=(
                "the screening visit itself" if at_visit else "the protocol and the investigator"
            ),
            query="",
            rationale=(
                "this criterion is settled at the screening visit, not from the record"
                if at_visit
                else "this criterion was not formalised because it cannot be decided from data"
            ),
            blocking=not at_visit,
        )
    if isinstance(predicate, ObservationPredicate):
        return _evaluate_observation(criterion, predicate, index, as_of)
    if isinstance(predicate, PresencePredicate):
        return _evaluate_presence(criterion, predicate, index, as_of, policy)
    return _evaluate_demographic(criterion, predicate, index, as_of)
