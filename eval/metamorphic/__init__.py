"""The metamorphic suite: relations between two runs that hold without an answer key.

`cases` holds the catalogue and the relation vocabulary; `runner` runs it and renders the table.
`python -m eval.metamorphic.runner` prints that table.
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
    all_of,
)
from .runner import CaseResult, run_all, run_case, to_markdown

__all__ = [
    "CASES",
    "AllOf",
    "AllVerdictsUnchanged",
    "CaseResult",
    "CoverageDoesNotDecrease",
    "CriterionBecomesUnknown",
    "CriterionVerdictFlips",
    "MetamorphicCase",
    "OnlyThisCriterionChanges",
    "OutcomeUnchanged",
    "Relation",
    "all_of",
    "run_all",
    "run_case",
    "to_markdown",
]
