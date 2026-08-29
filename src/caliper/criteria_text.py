"""Deterministic segmentation of a ClinicalTrials.gov eligibility blob.

The registry stores inclusion and exclusion criteria as a single free-text field whose formatting
depends on whoever registered the trial: asterisk bullets or numbered lists, headers with or
without colons, Markdown escapes injected by the registry, and a standard boilerplate sentence that
looks like a criterion but is not one.

Splitting this before the model sees it is worth the effort twice over. The compiler gets one
bounded span at a time instead of a wall of text, and because every span carries its offsets into
the source, we can afterwards check that no span was silently dropped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

_ESCAPED = re.compile(r"\\([<>\[\]^*_~`#+\-.!()])")

_HEADER = re.compile(
    r"^\s*(?:key\s+)?(?P<kind>inclusion|exclusion)\s+criteri(?:on|a)\b\s*:?\s*$",
    re.IGNORECASE,
)

_BULLET = re.compile(r"^(?P<indent>\s*)[*\-\u2022]\s+(?P<body>\S.*)$")
_NUMBERED = re.compile(r"^(?P<indent>\s*)(?:\(?\d+[.)]|[a-z][.)])\s+(?P<body>\S.*)$")

_BOILERPLATE = (
    "the above information is not intended to contain all considerations relevant to a "
    "participant's potential participation in a clinical trial"
)


class Section(Enum):
    INCLUSION = "inclusion"
    EXCLUSION = "exclusion"
    UNSPECIFIED = "unspecified"


@dataclass(frozen=True)
class CriterionSpan:
    """One candidate criterion, with the offsets that tie it back to the protocol text."""

    index: int
    section: Section
    text: str
    char_start: int
    char_end: int
    parent_index: int | None = None

    @property
    def is_child(self) -> bool:
        return self.parent_index is not None


def unescape_registry_markdown(text: str) -> str:
    """Remove the backslash escapes ClinicalTrials.gov injects around Markdown metacharacters.

    Left in place, `\\<0.70` never matches a `<` and `m\\^2` never matches a unit.
    """
    return _ESCAPED.sub(r"\1", text)


def _is_boilerplate(line: str) -> bool:
    return _BOILERPLATE in line.casefold()


@dataclass
class _Item:
    indent: int
    section: Section
    text: str
    start: int
    end: int


def _collect_items(text: str) -> list[_Item]:
    """Walk the text line by line, tracking the current section and the list nesting depth."""
    items: list[_Item] = []
    section = Section.UNSPECIFIED
    offset = 0
    saw_marker = False

    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        line_start = offset
        offset += len(line)

        if not stripped or _is_boilerplate(stripped):
            continue

        header = _HEADER.match(stripped)
        if header:
            section = Section[header.group("kind").upper()]
            continue

        match = _BULLET.match(line.rstrip("\n")) or _NUMBERED.match(line.rstrip("\n"))
        if match:
            saw_marker = True
            body = match.group("body").strip()
            body_start = line_start + line.index(body)
            items.append(
                _Item(
                    indent=len(match.group("indent")),
                    section=section,
                    text=body,
                    start=body_start,
                    end=body_start + len(body),
                )
            )
            continue

        # Prose registrations carry one criterion per line and no markers at all.
        body_start = line_start + line.index(stripped)
        items.append(
            _Item(
                indent=0,
                section=section,
                text=stripped,
                start=body_start,
                end=body_start + len(stripped),
            )
        )

    if not saw_marker:
        return items
    return items


def _link_children(items: list[_Item]) -> list[int | None]:
    """A more deeply indented item is a sub-condition of the last shallower item above it."""
    parents: list[int | None] = []
    stack: list[tuple[int, int]] = []  # (indent, index)
    for i, item in enumerate(items):
        while stack and stack[-1][0] >= item.indent:
            stack.pop()
        parents.append(stack[-1][1] if stack else None)
        stack.append((item.indent, i))
    return parents


def segment(text: str) -> list[CriterionSpan]:
    """Split an eligibility blob into criterion spans, in document order."""
    items = _collect_items(text)
    parents = _link_children(items)
    spans = []
    for i, (item, parent) in enumerate(zip(items, parents, strict=True)):
        section = item.section
        if parent is not None:
            section = spans[parent].section
        spans.append(
            CriterionSpan(
                index=i,
                section=section,
                text=item.text,
                char_start=item.start,
                char_end=item.end,
                parent_index=parent,
            )
        )
    return spans
