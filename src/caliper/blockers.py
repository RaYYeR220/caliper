"""Which criteria abstention actually costs.

A false-abstention rate says how often a decidable case went to a human. It does not say why, and
without that the number is a complaint rather than a finding.

In practice the same few criteria block most screenings in a cohort — an open category the protocol
never enumerates ("at least one major cardiovascular risk factor"), a threshold with no number
("adequate organ function"). Naming them turns the cost into something a site can act on: a
coordinator settles those once for the trial, and the rest of the cohort clears without them.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from caliper.ir import CriteriaSet
from caliper.logic import Verdict
from caliper.screen import ScreeningResult


@dataclass(frozen=True)
class Blocker:
    """One criterion, and how many screenings it left undecided.

    Identified by trial and criterion together. Criterion identifiers are ordinals assigned within
    one protocol, so `INC-01` names a different criterion in every trial in the corpus; keying on
    the identifier alone silently added eight unrelated criteria together and reported the sum as
    one very troublesome line.
    """

    nct_id: str
    criterion_id: str
    screenings: int
    reason: str
    missing: str
    quote: str = ""


def blocking_criteria(
    results: list[ScreeningResult], criteria_sets: list[CriteriaSet] | None = None
) -> list[Blocker]:
    """The criteria that left screenings undecided, most frequent first.

    A criterion settled at the screening visit is not counted: it holds nothing up, and listing it
    here would bury the ones that do behind consent forms.
    """
    quotes: dict[tuple[str, str], str] = {}
    for criteria_set in criteria_sets or []:
        for criterion in criteria_set.criteria:
            quotes[criteria_set.nct_id, criterion.id] = criterion.source_quote

    counts: Counter[tuple[str, str]] = Counter()
    detail: dict[tuple[str, str], tuple[str, str]] = {}
    for result in results:
        for outcome in result.criteria:
            if outcome.verdict is not Verdict.UNKNOWN or not outcome.blocking:
                continue
            key = (result.nct_id, outcome.criterion_id)
            counts[key] += 1
            hint = outcome.resolution_hint
            detail.setdefault(key, (outcome.rationale, hint.missing if hint is not None else ""))

    return [
        Blocker(
            nct_id=nct_id,
            criterion_id=criterion_id,
            screenings=count,
            reason=detail[nct_id, criterion_id][0],
            missing=detail[nct_id, criterion_id][1],
            quote=quotes.get((nct_id, criterion_id), ""),
        )
        for (nct_id, criterion_id), count in counts.most_common()
    ]
