"""Answers a person gave to questions the record could not.

Most of what Caliper abstains on is not a gap in a chart. It is a category the protocol never
enumerated — "at least one major cardiovascular risk factor" — or a plan, or an intention. No FHIR
query closes those. Somebody has to be asked, and unless their answer can come back into the
screening the system has produced a very well-documented dead end.

This module is that path, and it is deliberately the narrowest one that works.

**A settlement may answer a question the record could not, and may never contradict a question the
record already answered.** A criterion the evaluator resolved to MET or NOT_MET keeps its verdict
whatever anyone submits, and the attempt is recorded rather than dropped. That single rule is what
makes a human answer safe to accept: it can only ever move a criterion off UNKNOWN, so the worst a
wrong settlement can do is what a wrong human screening already does — and the record underneath is
still there, still cited, still disagreeing in writing.

Three smaller rules follow from the same instinct:

- UNKNOWN is not an answer a person may give. Declining to answer is what the criterion already
  says; a settlement exists to close one, not to restate it.
- A settlement is signed and explained, or it is refused at construction. An unattributable
  override is indistinguishable from a bug in six months.
- A settlement carries no evidence, and nothing renders it as though it did. It is a person's word,
  and the packet says so on the row.

A settlement names one patient, always. The first version of this module scoped them to the trial,
on the reasoning that the criterion blocking one screening usually blocks the whole cohort — and
that is true, but it does not follow that the answer is the same for everyone. "At least one major
cardiovascular risk factor" blocks all twenty-four charts and is a different question about each of
them; a cohort-wide `met` would have quietly enrolled the twenty-three it was not asked about. What
generalises is the *definition* the coordinator applies, not the verdict it produces, and supplying
a definition means recompiling the criterion rather than answering it. That is a different feature
and it is not built.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date

from caliper.logic import Verdict

SCHEMA = "caliper.settlements/1"


@dataclass(frozen=True)
class Settlement:
    """One criterion, answered by a named person on a stated date, with their reason."""

    nct_id: str
    patient_id: str
    criterion_id: str
    verdict: Verdict
    answered_by: str
    answered_on: date
    note: str

    def __post_init__(self) -> None:
        if self.verdict not in (Verdict.MET, Verdict.NOT_MET):
            raise ValueError(
                f"a settlement must be MET or NOT_MET, not {self.verdict.name}: declining to "
                "answer is what the criterion already says"
            )
        if not self.answered_by.strip():
            raise ValueError("a settlement needs answered_by: an unsigned override is a bug")
        if not self.note.strip():
            raise ValueError("a settlement needs a note saying what was asked and what was said")
        if not self.patient_id.strip():
            raise ValueError(
                "a settlement names one patient: an answer that applies to a whole cohort is a "
                "different question from the one a coordinator was asked"
            )

    def as_dict(self) -> dict[str, str]:
        return {
            "nct_id": self.nct_id,
            "patient_id": self.patient_id,
            "criterion_id": self.criterion_id,
            "verdict": self.verdict.value,
            "answered_by": self.answered_by,
            "answered_on": self.answered_on.isoformat(),
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, str]) -> Settlement:
        return cls(
            nct_id=payload["nct_id"],
            patient_id=payload["patient_id"],
            criterion_id=payload["criterion_id"],
            verdict=Verdict(payload["verdict"]),
            answered_by=payload["answered_by"],
            answered_on=date.fromisoformat(payload["answered_on"]),
            note=payload["note"],
        )

    @property
    def sentence(self) -> str:
        """How the packet says it, so no reader mistakes this for something from the chart."""
        answer = "met" if self.verdict is Verdict.MET else "not met"
        return (
            f"Settled by {self.answered_by} on {self.answered_on.isoformat()}, not from the "
            f"record: {answer}. {self.note.rstrip('.')}."
        )


@dataclass(frozen=True)
class Refusal:
    """A settlement that was submitted and not applied, with the reason it was not."""

    criterion_id: str
    reason: str


class SettlementLog:
    """The settlements standing for one screening, and every one that was refused.

    Mutable in exactly one direction: it accumulates refusals as the evaluator meets them. Nothing
    can add a settlement after construction, so the set of answers a screening ran against is fixed
    before the first criterion is read.
    """

    def __init__(self, settlements: Iterable[Settlement] = ()) -> None:
        self._by_criterion: dict[tuple[str, str, str], Settlement] = {}
        for settlement in settlements:
            key = (settlement.nct_id, settlement.patient_id, settlement.criterion_id)
            if key in self._by_criterion:
                raise ValueError(
                    f"{settlement.criterion_id} is settled twice for {settlement.patient_id} "
                    f"against {settlement.nct_id}; one criterion takes one answer"
                )
            self._by_criterion[key] = settlement
        self._refused: list[Refusal] = []

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SettlementLog):
            return NotImplemented
        return self._by_criterion == other._by_criterion

    def __hash__(self) -> int:  # pragma: no cover - a log is not a key
        raise TypeError("SettlementLog is not hashable")

    def __len__(self) -> int:
        return len(self._by_criterion)

    def __iter__(self) -> Iterator[Settlement]:
        return iter(self._by_criterion.values())

    def __bool__(self) -> bool:
        return bool(self._by_criterion)

    def for_criterion(self, nct_id: str, patient_id: str, criterion_id: str) -> Settlement | None:
        return self._by_criterion.get((nct_id, patient_id, criterion_id))

    def refuse(self, criterion_id: str, reason: str) -> None:
        """Record that a settlement was submitted for a criterion and not applied."""
        refusal = Refusal(criterion_id=criterion_id, reason=reason)
        if refusal not in self._refused:
            self._refused.append(refusal)

    @property
    def refused(self) -> tuple[Refusal, ...]:
        return tuple(self._refused)

    def to_json(self) -> str:
        return json.dumps(
            {"schema": SCHEMA, "settlements": [s.as_dict() for s in self]},
            indent=2,
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, text: str) -> SettlementLog:
        payload = json.loads(text)
        if payload.get("schema") != SCHEMA:
            raise ValueError(f"not a settlement log: schema is {payload.get('schema')!r}")
        return cls(Settlement.from_dict(row) for row in payload["settlements"])
