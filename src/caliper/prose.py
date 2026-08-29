"""Checking model-written prose against the record it claims to describe.

Everything else in a screening packet is generated from structured data. The one-line rationale is
not: a model writes it, because a coordinator reading forty criteria wants a sentence, not a row of
fields. That makes it the only place where the packet can drift.

`check_rationale` extracts every number and date from the sentence and requires each to be bound to
*that criterion's* own values — its threshold, its window, its evidence, the code it resolved
through. Binding is deliberately per-criterion: if the whole packet were the allowed set, a
threshold belonging to one criterion could vouch for a sentence about another, which is exactly the
mistake worth catching.

What this does not do is check meaning. A sentence whose every number is bound can still describe
the wrong relationship between them, and no amount of token matching will notice. That limit is
stated plainly in the report rather than papered over.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from caliper.evaluate import CriterionResult
from caliper.ir import Criterion, DemographicPredicate, ObservationPredicate, PresencePredicate
from caliper.units import convert

_ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
# The lookbehind keeps "18-85" reading as two bounds rather than 18 and minus 85.
_NUMBER = re.compile(r"(?<![\d.])-?\d+(?:\.\d+)?")

# A resource pointer addresses a record; it does not assert anything about the patient.
_FHIR_POINTER = re.compile(r"\b[A-Z][A-Za-z]*\.entry\[\d+\][\w.\[\]]*")


@dataclass(frozen=True)
class ProseViolation:
    criterion_id: str
    kind: str
    token: str
    sentence: str
    message: str


def _allowed_dates(result: CriterionResult) -> set[str]:
    return {e.date.isoformat() for e in result.evidence if e.date is not None}


def _allowed_numbers(criterion: Criterion, result: CriterionResult) -> set[float]:
    """Every number this criterion is entitled to mention."""
    allowed: set[float] = set()
    predicate = criterion.predicate

    if isinstance(predicate, ObservationPredicate):
        allowed.add(predicate.value)
        if predicate.value_high is not None:
            allowed.add(predicate.value_high)
        if predicate.window is not None and predicate.window.amount is not None:
            allowed.add(float(predicate.window.amount))
    elif isinstance(predicate, DemographicPredicate) and isinstance(predicate.value, (int, float)):
        allowed.add(float(predicate.value))
    elif isinstance(predicate, PresencePredicate):
        if predicate.window is not None and predicate.window.amount is not None:
            allowed.add(float(predicate.window.amount))

    target_unit = predicate.unit if isinstance(predicate, ObservationPredicate) else None
    concept_codes = getattr(predicate, "concept", None)
    codes = concept_codes.codes if concept_codes is not None else ()
    literals = code_literals(criterion)

    for evidence in result.evidence:
        if evidence.value is None:
            continue
        allowed.add(evidence.value)
        if target_unit and evidence.unit:
            converted = convert(evidence.value, evidence.unit, target_unit, codes)
            if converted is not None:
                allowed.add(converted)

    # The rationale the evaluator itself produced is by definition derived from the record. Dates
    # are stripped from it first: a date is checked as a date, and letting 2026-05-14 seed the
    # numeric set would license a sentence asserting a creatinine of 2026.
    rationale = _ISO_DATE.sub(" ", _strip_addresses(result.rationale, literals))
    allowed.update(float(t) for t in _NUMBER.findall(rationale))
    quote = _ISO_DATE.sub(" ", _strip_addresses(criterion.source_quote, literals))
    allowed.update(float(t) for t in _NUMBER.findall(quote))
    return allowed


def code_literals(criterion: Criterion) -> tuple[str, ...]:
    """The terminology codes this criterion is allowed to name without asserting anything."""
    concept = getattr(criterion.predicate, "concept", None)
    if concept is None:
        return ()
    return tuple(code.code for code in concept.codes)


def _strip_addresses(text: str, codes: tuple[str, ...] = ()) -> str:
    """Blank out things that address a record rather than assert a value.

    Terminology codes are exempted only when the criterion actually resolved through them; a blanket
    "anything hyphenated is a code" rule would quietly wave through an invented range like 18-85.
    """
    cleaned = _FHIR_POINTER.sub(" ", text)
    for code in codes:
        cleaned = cleaned.replace(code, " ")
    return cleaned


def _is_bound(token: str, allowed: set[float]) -> bool:
    """Accept a rendered number that is exact, or a decimal rounding of an allowed value.

    Rounding is permitted only to a decimal place. Allowing it to the whole number would mean a
    1.5 mg/dL threshold vouched for a sentence saying "2", which is the kind of hole that makes a
    linter worse than useless: it would certify the sentence and nobody would look again.
    """
    rendered = float(token)
    decimals = len(token.split(".")[1]) if "." in token else 0
    for candidate in allowed:
        if abs(candidate - rendered) < 1e-9:
            return True
        if decimals >= 1 and round(candidate, decimals) == rendered:
            return True
    return False


def check_rationale(
    sentence: str, criterion: Criterion, result: CriterionResult
) -> list[ProseViolation]:
    """Report every number or date in `sentence` that the criterion's record does not support."""
    violations: list[ProseViolation] = []
    allowed_dates = _allowed_dates(result)

    remaining = sentence
    for token in _ISO_DATE.findall(sentence):
        if token not in allowed_dates:
            violations.append(
                ProseViolation(
                    criterion_id=criterion.id,
                    kind="unbound_date",
                    token=token,
                    sentence=sentence,
                    message=f"{token} does not appear in the evidence for {criterion.id}",
                )
            )
        remaining = remaining.replace(token, " ")

    allowed_numbers = _allowed_numbers(criterion, result)
    for token in _NUMBER.findall(_strip_addresses(remaining, code_literals(criterion))):
        if not _is_bound(token, allowed_numbers):
            violations.append(
                ProseViolation(
                    criterion_id=criterion.id,
                    kind="unbound_number",
                    token=token,
                    sentence=sentence,
                    message=f"{token} is not a value {criterion.id} resolved from",
                )
            )
    return violations
