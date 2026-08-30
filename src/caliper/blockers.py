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
    criterion_id: str
    screenings: int
    reason: str
    missing: str
    quote: str = ""

    @property
    def share(self) -> float:
        return 0.0


def blocking_criteria(
    results: list[ScreeningResult], criteria_sets: list[CriteriaSet] | None = None
) -> list[Blocker]:
    """The criteria that left screenings undecided, most frequent first.

    A criterion settled at the screening visit is not counted: it holds nothing up, and listing it
    here would bury the ones that do behind consent forms.
    """
    quotes: dict[str, str] = {}
    for criteria_set in criteria_sets or []:
        for criterion in criteria_set.criteria:
            quotes[criterion.id] = criterion.source_quote

    counts: Counter[str] = Counter()
    detail: dict[str, tuple[str, str]] = {}
    for result in results:
        for criterion in result.criteria:
            if criterion.verdict is not Verdict.UNKNOWN or not criterion.blocking:
                continue
            counts[criterion.criterion_id] += 1
            hint = criterion.resolution_hint
            detail.setdefault(
                criterion.criterion_id,
                (criterion.rationale, hint.missing if hint is not None else ""),
            )

    return [
        Blocker(
            criterion_id=criterion_id,
            screenings=count,
            reason=detail[criterion_id][0],
            missing=detail[criterion_id][1],
            quote=quotes.get(criterion_id, ""),
        )
        for criterion_id, count in counts.most_common()
    ]
