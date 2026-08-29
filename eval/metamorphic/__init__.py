"""The metamorphic suite: relations between two runs that hold without an answer key.

`cases` holds the catalogue and the relation vocabulary. The runner lives in
`eval.metamorphic.runner` and is deliberately not re-exported here, so that
`python -m eval.metamorphic.runner` — which prints the report table — does not import it twice.
"""

from .cases import (
    CASES,
    AllOf,
    AllVerdictsUnchanged,
    CoverageDoesNotDecrease,
    CriterionBecomesUnknown,
    CriterionVerdictFlips,
    MetamorphicCase,
    OnlyThisCriterionChanges,
    OutcomeUnchanged,
    Relation,
    ScreeningBlockedOn,
    all_of,
)

__all__ = [
    "CASES",
    "AllOf",
    "AllVerdictsUnchanged",
    "CoverageDoesNotDecrease",
    "CriterionBecomesUnknown",
    "CriterionVerdictFlips",
    "MetamorphicCase",
    "OnlyThisCriterionChanges",
    "OutcomeUnchanged",
    "Relation",
    "ScreeningBlockedOn",
    "all_of",
]
