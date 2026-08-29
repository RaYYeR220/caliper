"""The exception hierarchy for the model runtime.

Everything raised deliberately by this package descends from `LLMError`, so a caller can draw a
single boundary around "the model layer failed" without catching provider SDK exceptions by
accident.
"""

from __future__ import annotations


class LLMError(Exception):
    """Base class for every failure this package raises on purpose."""
