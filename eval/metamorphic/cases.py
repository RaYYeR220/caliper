"""Metamorphic evaluation: assertions about a pair of runs, never about a single answer.

A metamorphic test does not say what the right answer is. It changes one thing about the input in
a way whose consequence is fixed by the design, then asserts the *relationship* between the two
runs: redact the only creatinine on a chart and the renal criterion must move from a verdict to
UNKNOWN; restate that same creatinine in micromoles per litre with the arithmetic done correctly
and every verdict must be identical. Neither claim needs an annotator, and neither can be argued
with by someone who reads the chart differently than we do.

That is why this suite is stronger evidence than our own answer key. The key is a set of labels we
wrote, so a reader who distrusts our clinical judgement has to take them on faith. The relations
below are entailed by the specification itself -- by `AbsencePolicy`, by the unit table's refusal
to guess, by the window semantics in `record.py` -- so a green result here survives disagreeing
with us about any individual patient. No model is involved anywhere: every criteria set in this
file is hand-written, and every patient is read from the committed corpus.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from functools import partial

from caliper.evaluate import AbsencePolicy
from caliper.ir import (
    Code,
    Concept,
    CriteriaSet,
    Criterion,
    DemographicPredicate,
    ObservationPredicate,
    PresencePredicate,
    TemporalWindow,
)
from caliper.logic import Verdict
from caliper.perturb import (
    PerturbedPatient,
    add_condition,
    convert_units,
    redact_analyte,
    remove_encounters,
    shift_date,
    shift_value,
)
from caliper.record import PatientIndex
from caliper.screen import ScreeningResult

# --------------------------------------------------------------------------------------------
# Relations
# --------------------------------------------------------------------------------------------


def _verdicts(result: ScreeningResult) -> dict[str, Verdict]:
    return {criterion.criterion_id: criterion.verdict for criterion in result.criteria}


def _name(verdict: Verdict | None) -> str:
    """A verdict as a judge would read it, including the case where the criterion is missing."""
    return verdict.name if verdict is not None else "ABSENT"


def _changes(
    before: ScreeningResult, after: ScreeningResult
) -> list[tuple[str, Verdict | None, Verdict | None]]:
    """Every criterion whose verdict moved, in the order the criteria were screened."""
    was, now = _verdicts(before), _verdicts(after)
    ids = list(dict.fromkeys([*was, *now]))
    return [(cid, was.get(cid), now.get(cid)) for cid in ids if was.get(cid) is not now.get(cid)]


def _describe(changes: list[tuple[str, Verdict | None, Verdict | None]]) -> str:
    return "; ".join(f"{cid} {_name(was)} -> {_name(now)}" for cid, was, now in changes)


class Relation(ABC):
    """A required relationship between the run before a perturbation and the run after it.

    A relation never states the correct verdict. It states what must be true of the pair, which is
    what lets it be checked without an annotator: the claim follows from the design of the system
    rather than from anyone's reading of the chart.
    """

    @property
    @abstractmethod
    def summary(self) -> str:
        """What is required, in one phrase, for printing beside a pass or a fail."""

    @abstractmethod
    def check(self, before: ScreeningResult, after: ScreeningResult) -> str | None:
        """None when the relation holds; otherwise what actually happened instead."""

    @property
    def criterion_ids(self) -> tuple[str, ...]:
        """The criteria this relation names, so a case can be checked for a mistyped id."""
        return ()


@dataclass(frozen=True)
class CriterionBecomesUnknown(Relation):
    """Taking away the evidence a criterion rested on must turn a verdict into abstention."""

    criterion_id: str

    @property
    def summary(self) -> str:
        return f"{self.criterion_id} moves from a resolved verdict to UNKNOWN"

    @property
    def criterion_ids(self) -> tuple[str, ...]:
        return (self.criterion_id,)

    def check(self, before: ScreeningResult, after: ScreeningResult) -> str | None:
        was, now = _verdicts(before).get(self.criterion_id), _verdicts(after).get(self.criterion_id)
        if was is None or now is None:
            return f"{self.criterion_id} is not among the criteria screened"
        if was is Verdict.UNKNOWN:
            return f"{self.criterion_id} was already UNKNOWN before the perturbation"
        if now is not Verdict.UNKNOWN:
            return (
                f"{self.criterion_id} went {was.name} -> {now.name}, "
                f"but was required to go {was.name} -> UNKNOWN"
            )
        return None


@dataclass(frozen=True)
class CriterionVerdictFlips(Relation):
    """Crossing a threshold must move the verdict to the other side, not merely disturb it."""

    criterion_id: str

    @property
    def summary(self) -> str:
        return f"{self.criterion_id} flips between MET and NOT_MET"

    @property
    def criterion_ids(self) -> tuple[str, ...]:
        return (self.criterion_id,)

    def check(self, before: ScreeningResult, after: ScreeningResult) -> str | None:
        was, now = _verdicts(before).get(self.criterion_id), _verdicts(after).get(self.criterion_id)
        if was is None or now is None:
            return f"{self.criterion_id} is not among the criteria screened"
        if Verdict.UNKNOWN in (was, now):
            return (
                f"{self.criterion_id} went {_name(was)} -> {_name(now)}, "
                "but a flip requires a resolved verdict on both sides"
            )
        if was is now:
            return f"{self.criterion_id} stayed {was.name} instead of flipping"
        return None


@dataclass(frozen=True)
class AllVerdictsUnchanged(Relation):
    """A perturbation the system is supposed to see through must move nothing at all."""

    @property
    def summary(self) -> str:
        return "every criterion keeps the verdict it had"

    def check(self, before: ScreeningResult, after: ScreeningResult) -> str | None:
        changes = _changes(before, after)
        return f"verdicts moved: {_describe(changes)}" if changes else None


@dataclass(frozen=True)
class OnlyThisCriterionChanges(Relation):
    """One criterion moves and the rest of the screening is untouched.

    This is the half of a metamorphic claim that is easy to forget and expensive to lose: a change
    that lands on the right criterion is worth little if it also perturbs three others.
    """

    criterion_id: str

    @property
    def summary(self) -> str:
        return f"{self.criterion_id} is the only criterion whose verdict moves"

    @property
    def criterion_ids(self) -> tuple[str, ...]:
        return (self.criterion_id,)

    def check(self, before: ScreeningResult, after: ScreeningResult) -> str | None:
        changes = _changes(before, after)
        collateral = [change for change in changes if change[0] != self.criterion_id]
        if collateral:
            return f"other verdicts moved as well: {_describe(collateral)}"
        if not changes:
            held = _verdicts(before).get(self.criterion_id)
            return f"{self.criterion_id} stayed {_name(held)}, so nothing moved at all"
        return None


@dataclass(frozen=True)
class CoverageDoesNotDecrease(Relation):
    """Nothing that adds evidence or loosens a bound may leave fewer criteria decided.

    Coverage is a fact about the chart, not about how hard a criterion is to satisfy. A system that
    abstained near a boundary, or that resolved fewer criteria once more data arrived, would be
    reporting something other than what it claims to report.
    """

    @property
    def summary(self) -> str:
        return "the share of criteria decided from data does not fall"

    def check(self, before: ScreeningResult, after: ScreeningResult) -> str | None:
        if after.coverage < before.coverage:
            return (
                f"coverage fell from {before.criteria_resolved}/{before.criteria_total} "
                f"to {after.criteria_resolved}/{after.criteria_total}"
            )
        return None


@dataclass(frozen=True)
class OutcomeUnchanged(Relation):
    """The screening decision is the same on both sides, whatever happened underneath it."""

    @property
    def summary(self) -> str:
        return "the screening decision is the same on both runs"

    def check(self, before: ScreeningResult, after: ScreeningResult) -> str | None:
        if after.decision is not before.decision:
            return (
                f"the decision moved {before.decision.name} -> {after.decision.name}"
            )
        return None


@dataclass(frozen=True)
class AllOf(Relation):
    """Several relations that must all hold. Every failure is reported, not just the first."""

    relations: tuple[Relation, ...]

    @property
    def summary(self) -> str:
        return ", and ".join(relation.summary for relation in self.relations)

    @property
    def criterion_ids(self) -> tuple[str, ...]:
        return tuple(cid for relation in self.relations for cid in relation.criterion_ids)

    def check(self, before: ScreeningResult, after: ScreeningResult) -> str | None:
        failures = [relation.check(before, after) for relation in self.relations]
        observed = [failure for failure in failures if failure is not None]
        return "; ".join(observed) if observed else None


def all_of(*relations: Relation) -> AllOf:
    """Conjunction of relations, written as a call so case definitions stay readable."""
    return AllOf(relations)


# --------------------------------------------------------------------------------------------
# The case type
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class MetamorphicCase:
    """One perturbation and the relationship it forces between the two screenings."""

    id: str
    description: str
    """One plain sentence, readable by someone who has never opened this file."""

    rationale: str
    """Why the relation must hold, in terms of the design rather than of clinical opinion."""

    criteria: CriteriaSet
    patient_id: str
    perturb: Callable[[PatientIndex], PerturbedPatient]
    relation: Relation
    policy: AbsencePolicy = AbsencePolicy.COVERAGE_GATED

    criteria_after: CriteriaSet | None = None
    """The second run's criteria, for the cases that perturb the trial instead of the chart.

    Almost every relation here is about editing a chart, but two of the invariants worth asserting
    are about editing the protocol -- relaxing every threshold must not reduce coverage. Those need
    a second criteria set rather than a second patient, and it is hand-written like the first.
    """


def unchanged(patient: PatientIndex) -> PerturbedPatient:
    """Leave the chart exactly as it is, for cases whose perturbation is to the trial."""
    return PerturbedPatient(patient=patient, perturbations=())


def _trial(nct_id: str, *criteria: Criterion) -> CriteriaSet:
    """Bundle hand-written criteria into a set, reconstructing the protocol text from the quotes.

    These criteria were written for this file rather than compiled from a real protocol, so the
    source text is assembled from the quotes themselves. That keeps `quote_fidelity_problems`
    honest instead of merely quiet, and it makes the trial identifiers visibly synthetic: no case
    here should be mistaken for a claim about a real registered study.
    """
    return CriteriaSet(
        nct_id=nct_id,
        source_text="\n".join(criterion.source_quote for criterion in criteria),
        criteria=list(criteria),
    )


# --------------------------------------------------------------------------------------------
# Vocabulary, windows and criteria, all hand-written
# --------------------------------------------------------------------------------------------

CREATININE = Concept(
    text="serum creatinine",
    codes=(
        Code(system="LOINC", code="38483-4", display="Creatinine [Mass/volume] in Blood"),
        Code(system="LOINC", code="2160-0", display="Creatinine [Mass/volume] in Serum or Plasma"),
    ),
)
HBA1C = Concept(
    text="haemoglobin A1c",
    codes=(Code(system="LOINC", code="4548-4", display="Hemoglobin A1c/Hemoglobin.total in Blood"),),
)
MYOCARDIAL_INFARCTION = Concept(
    text="myocardial infarction",
    codes=(Code(system="SNOMED", code="22298006", display="Myocardial infarction"),),
)
TYPE_2_DIABETES = Concept(
    text="type 2 diabetes mellitus",
    codes=(Code(system="SNOMED", code="44054006", display="Diabetes mellitus type 2"),),
)
HEART_FAILURE = Concept(
    text="chronic heart failure",
    codes=(Code(system="SNOMED", code="88805009", display="Chronic congestive heart failure"),),
)

CREATININE_LOINC = "38483-4"
HBA1C_LOINC = "4548-4"
CHOLESTEROL_LOINC = "2093-3"

LAST_YEAR = TemporalWindow(relation="within", amount=12, unit="months")
EVER = TemporalWindow(relation="ever")

ADULT = Criterion(
    id="adult",
    kind="inclusion",
    source_quote="Aged 18 years or older at screening.",
    predicate=DemographicPredicate(field="age", op=">=", value=18, unit="years"),
)
CREATININE_BAND = Criterion(
    id="creatinine-band",
    kind="inclusion",
    source_quote="Serum creatinine between 0.6 and 1.5 mg/dL within the last 12 months.",
    predicate=ObservationPredicate(
        concept=CREATININE,
        op="between",
        value=0.6,
        value_high=1.5,
        unit="mg/dL",
        window=LAST_YEAR,
    ),
)
CREATININE_CEILING = Criterion(
    id="creatinine-ceiling",
    kind="inclusion",
    source_quote="Serum creatinine no greater than 1.5 mg/dL within the last 12 months.",
    predicate=ObservationPredicate(
        concept=CREATININE, op="<=", value=1.5, unit="mg/dL", window=LAST_YEAR
    ),
)
HBA1C_CONTROLLED = Criterion(
    id="hba1c-controlled",
    kind="inclusion",
    source_quote="HbA1c below 7.0% within the last 12 months.",
    predicate=ObservationPredicate(
        concept=HBA1C, op="<", value=7.0, unit="%", window=LAST_YEAR
    ),
)
HBA1C_ELEVATED = Criterion(
    id="hba1c-elevated",
    kind="inclusion",
    source_quote="HbA1c of 7.0% or above within the last 12 months.",
    predicate=ObservationPredicate(
        concept=HBA1C, op=">=", value=7.0, unit="%", window=LAST_YEAR
    ),
)
HBA1C_BELOW_NINE = Criterion(
    id="hba1c-below-nine",
    kind="inclusion",
    source_quote="HbA1c below 9.0% within the last 12 months.",
    predicate=ObservationPredicate(
        concept=HBA1C, op="<", value=9.0, unit="%", window=LAST_YEAR
    ),
)
NO_RECENT_MI = Criterion(
    id="no-recent-mi",
    kind="inclusion",
    source_quote="No myocardial infarction in the 12 months before screening.",
    predicate=PresencePredicate(
        type="condition", concept=MYOCARDIAL_INFARCTION, presence="absent", window=LAST_YEAR
    ),
)
RECENT_DIABETES = Criterion(
    id="recent-diabetes",
    kind="inclusion",
    source_quote="Type 2 diabetes mellitus diagnosed within the last 12 months.",
    predicate=PresencePredicate(
        type="condition", concept=TYPE_2_DIABETES, presence="present", window=LAST_YEAR
    ),
)
DIABETES_EVER = Criterion(
    id="diabetes-ever",
    kind="inclusion",
    source_quote="A documented history of type 2 diabetes mellitus at any time.",
    predicate=PresencePredicate(
        type="condition", concept=TYPE_2_DIABETES, presence="present", window=EVER
    ),
)
DIABETES_EXCLUDED = Criterion(
    id="diabetes-excluded",
    kind="exclusion",
    source_quote="Any documented history of type 2 diabetes mellitus.",
    predicate=PresencePredicate(
        type="condition", concept=TYPE_2_DIABETES, presence="present", window=EVER
    ),
)
HEART_FAILURE_EVER = Criterion(
    id="heart-failure-ever",
    kind="inclusion",
    source_quote="A documented history of chronic heart failure at any time.",
    predicate=PresencePredicate(
        type="condition", concept=HEART_FAILURE, presence="present", window=EVER
    ),
)

RENAL_PANEL = _trial("MM-RENAL", CREATININE_BAND, HBA1C_CONTROLLED, ADULT)
RENAL_CEILING = _trial("MM-RENAL-CEILING", CREATININE_CEILING, ADULT)
GLYCAEMIC = _trial("MM-GLYCAEMIC", HBA1C_ELEVATED, CREATININE_BAND, ADULT)
GLYCAEMIC_EXCLUDING_DIABETES = _trial("MM-GLYCAEMIC-EXCL", HBA1C_BELOW_NINE, DIABETES_EXCLUDED)
DIABETES_HISTORY = _trial("MM-DIABETES", RECENT_DIABETES, DIABETES_EVER, ADULT)
CARDIAC = _trial("MM-CARDIAC", NO_RECENT_MI, CREATININE_BAND)
STALE_SCREEN = _trial("MM-STALE", NO_RECENT_MI, HEART_FAILURE_EVER)

# The same trial with every numeric bound widened until any value satisfies it. The criterion ids
# are deliberately identical, so the two runs line up criterion for criterion in a report.
GLYCAEMIC_RELAXED = _trial(
    "MM-GLYCAEMIC",
    Criterion(
        id="hba1c-elevated",
        kind="inclusion",
        source_quote="HbA1c of 0.0% or above within the last 12 months.",
        predicate=ObservationPredicate(
            concept=HBA1C, op=">=", value=0.0, unit="%", window=LAST_YEAR
        ),
    ),
    Criterion(
        id="creatinine-band",
        kind="inclusion",
        source_quote="Serum creatinine between 0.0 and 1000.0 mg/dL within the last 12 months.",
        predicate=ObservationPredicate(
            concept=CREATININE,
            op="between",
            value=0.0,
            value_high=1000.0,
            unit="mg/dL",
            window=LAST_YEAR,
        ),
    ),
    Criterion(
        id="adult",
        kind="inclusion",
        source_quote="Aged 0 years or older at screening.",
        predicate=DemographicPredicate(field="age", op=">=", value=0, unit="years"),
    ),
)

# --------------------------------------------------------------------------------------------
# Patients, from data/patients. Each is chosen for one property the cases below depend on.
# --------------------------------------------------------------------------------------------

# Labs and an encounter inside the twelve months before the screening date, and nothing cardiac.
FRESH_CHART = "23da8e71-dfb9-9773-1bc1-7b5e31d085b5"

# HbA1c 7.58% and a type 2 diabetes diagnosis, both dated two days inside the twelve-month window.
DIABETIC = "1be83f06-48ef-7bac-7097-b9e0644aeaf8"

# Creatinine 2.578 mg/dL, comfortably the wrong side of a 1.5 mg/dL ceiling.
IMPAIRED_RENAL = "f870c432-0887-125e-f778-cf5110d3de1d"

# A chart that stops in 2015: no encounter documents the last twelve months, which is what makes
# coverage-gated absence abstain on it before anything has been perturbed at all.
STALE_CHART = "8d91c36a-1f7e-3842-9f14-8d567ed9cdcd"

# The one creatinine result inside the twelve-month window on FRESH_CHART; the next is 2025-05-24,
# a week the wrong side of it, so moving this resource empties the window.
FRESH_CREATININE_RESOURCE = "23da8e71-dfb9-9773-9850-4c4fe75f1e42"

# The type 2 diabetes Condition on DIABETIC, onset 2025-06-03.
DIABETIC_DIAGNOSIS_RESOURCE = "1be83f06-48ef-7bac-29c9-3bb8d314aa2b"

# Published factor for creatinine, mg/dL to umol/L: 1000 / 113.12 g/mol / 10 dL/L. Written as a
# literal rather than derived from `caliper.units`, because a fixture built from the table under
# test could not detect an error in that table.
CREATININE_MG_DL_TO_UMOL_L = 88.4

MI_CODE = Code(system="SNOMED", code="22298006", display="Myocardial infarction")
# Mirrors how `fhir.py` renders a Condition, so the added row is indistinguishable from an
# ingested one.
MI_DISPLAY = "Myocardial infarction (active, confirmed)"

# --------------------------------------------------------------------------------------------
# The catalogue
# --------------------------------------------------------------------------------------------

CASES: tuple[MetamorphicCase, ...] = (
    MetamorphicCase(
        id="redact-creatinine-forces-abstention",
        description=(
            "Deleting every creatinine result from the chart must leave the creatinine criterion "
            "unresolved, and must not disturb any other criterion."
        ),
        rationale=(
            "`_evaluate_observation` abstains when `PatientIndex.find` returns nothing, so a "
            "criterion whose analyte has been removed has no path to a verdict. The other two "
            "criteria read age and HbA1c, neither of which this perturbation touches."
        ),
        criteria=RENAL_PANEL,
        patient_id=FRESH_CHART,
        perturb=partial(redact_analyte, loinc=CREATININE_LOINC),
        relation=all_of(
            CriterionBecomesUnknown("creatinine-band"),
            OnlyThisCriterionChanges("creatinine-band"),
        ),
    ),
    MetamorphicCase(
        id="redact-unread-analyte-is-inert",
        description=(
            "Deleting an analyte that no criterion mentions must change nothing whatsoever."
        ),
        rationale=(
            "Cholesterol appears nowhere in this trial's criteria. Evaluation is a function of the "
            "rows a criterion's concept actually matches, so removing unrelated rows cannot reach "
            "any verdict. A failure here would mean a verdict depends on chart bulk."
        ),
        criteria=RENAL_PANEL,
        patient_id=FRESH_CHART,
        perturb=partial(redact_analyte, loinc=CHOLESTEROL_LOINC),
        relation=AllVerdictsUnchanged(),
    ),
    MetamorphicCase(
        id="redact-cannot-rescue-a-triggered-exclusion",
        description=(
            "Losing the evidence behind an inclusion criterion must not change the decision for a "
            "patient a documented exclusion has already ruled out."
        ),
        rationale=(
            "`roll_up` treats a proven exclusion as decisive: an unresolved sibling cannot rescue "
            "a patient who is already ineligible, and sending a coordinator to the chart for an "
            "answer that could not change anything would be work with no purpose."
        ),
        criteria=GLYCAEMIC_EXCLUDING_DIABETES,
        patient_id=DIABETIC,
        perturb=partial(redact_analyte, loinc=HBA1C_LOINC),
        relation=all_of(
            CriterionBecomesUnknown("hba1c-below-nine"),
            OutcomeUnchanged(),
        ),
    ),
    MetamorphicCase(
        id="hba1c-crossing-the-threshold-flips-one-verdict",
        description=(
            "Moving the HbA1c from 7.58% to 6.9% against a criterion reading 'at least 7.0%' must "
            "flip that criterion, and only that criterion."
        ),
        rationale=(
            "The comparison is `>=` against 7.0, so 6.9 and 7.58 fall on opposite sides of it by "
            "arithmetic. Nothing else in the trial reads HbA1c, so a second verdict moving would "
            "mean criteria are not being evaluated independently."
        ),
        criteria=GLYCAEMIC,
        patient_id=DIABETIC,
        perturb=partial(shift_value, loinc=HBA1C_LOINC, to=6.9),
        relation=all_of(
            CriterionVerdictFlips("hba1c-elevated"),
            OnlyThisCriterionChanges("hba1c-elevated"),
        ),
    ),
    MetamorphicCase(
        id="hba1c-moving-within-one-side-changes-nothing",
        description=(
            "Moving the HbA1c from 7.58% to 7.4% -- a real change, but on the same side of the "
            "7.0% threshold -- must leave every verdict alone."
        ),
        rationale=(
            "The companion to the flip case. A verdict is a function of which side of the bound "
            "the value lands on, not of the value itself, so a system that moved here would be "
            "reading something other than the criterion it was given."
        ),
        criteria=GLYCAEMIC,
        patient_id=DIABETIC,
        perturb=partial(shift_value, loinc=HBA1C_LOINC, to=7.4),
        relation=AllVerdictsUnchanged(),
    ),
    MetamorphicCase(
        id="creatinine-leaving-the-band-flips-one-verdict",
        description=(
            "Moving the creatinine from 0.95 to 2.4 mg/dL, out of a 0.6-to-1.5 band, must flip "
            "that criterion and nothing else."
        ),
        rationale=(
            "`between` is evaluated as a closed interval, and 2.4 is outside it. The case exists "
            "because a range bound is the easiest of the comparison operators to implement with "
            "the wrong endpoint semantics and the hardest to notice."
        ),
        criteria=RENAL_PANEL,
        patient_id=FRESH_CHART,
        perturb=partial(shift_value, loinc=CREATININE_LOINC, to=2.4),
        relation=all_of(
            CriterionVerdictFlips("creatinine-band"),
            OnlyThisCriterionChanges("creatinine-band"),
        ),
    ),
    MetamorphicCase(
        id="correct-molar-restatement-changes-nothing",
        description=(
            "Restating every creatinine result in umol/L, with the arithmetic done correctly, "
            "must leave every verdict and the screening decision exactly as they were."
        ),
        rationale=(
            "`caliper.units` carries creatinine's molar mass, so the mass-to-substance bridge is "
            "available and the comparison must survive the change of unit. The fixture multiplies "
            "by a published factor rather than by anything read out of the table under test."
        ),
        criteria=RENAL_PANEL,
        patient_id=FRESH_CHART,
        perturb=partial(
            convert_units,
            loinc=CREATININE_LOINC,
            to_unit="umol/L",
            factor=CREATININE_MG_DL_TO_UMOL_L,
        ),
        relation=all_of(AllVerdictsUnchanged(), OutcomeUnchanged()),
    ),
    MetamorphicCase(
        id="mislabelled-unit-must-be-read-not-ignored",
        description=(
            "Relabelling a creatinine of 2.578 as umol/L without rescaling it must flip the "
            "criterion, because 2.578 umol/L and 2.578 mg/dL are not the same measurement."
        ),
        rationale=(
            "The number on the chart is unchanged and only the unit moves, so a system that "
            "compared the bare value against the bound would report no change at all. The verdict "
            "is required to move, which is the same thing as requiring that the unit be read."
        ),
        criteria=RENAL_CEILING,
        patient_id=IMPAIRED_RENAL,
        perturb=partial(convert_units, loinc=CREATININE_LOINC, to_unit="umol/L", factor=1.0),
        relation=all_of(
            CriterionVerdictFlips("creatinine-ceiling"),
            OnlyThisCriterionChanges("creatinine-ceiling"),
        ),
    ),
    MetamorphicCase(
        id="unconvertible-unit-forces-abstention",
        description=(
            "Restating the creatinine in mg%, a unit the conversion table does not carry, must "
            "leave the criterion unresolved rather than compared."
        ),
        rationale=(
            "mg% is a legacy spelling of mg/dL and the number is identical, so this is the exact "
            "shape of the mistake the table exists to refuse: `convert` returns None for a unit it "
            "has not vetted, and the criterion must abstain instead of guessing right by luck."
        ),
        criteria=RENAL_CEILING,
        patient_id=IMPAIRED_RENAL,
        perturb=partial(convert_units, loinc=CREATININE_LOINC, to_unit="mg%", factor=1.0),
        relation=all_of(
            CriterionBecomesUnknown("creatinine-ceiling"),
            OnlyThisCriterionChanges("creatinine-ceiling"),
        ),
    ),
    MetamorphicCase(
        id="unknown-unit-abstains-even-when-the-number-would-agree",
        description=(
            "Restating the HbA1c in mmol/mol, which the conversion table does not carry, must "
            "leave the criterion unresolved."
        ),
        rationale=(
            "mmol/mol is the IFCC unit for HbA1c and lands in the fifties and eighties where a "
            "percentage lands in the single figures. A system reading the bare number would "
            "compare it against a bound of 7.0 and call the criterion met -- the right verdict for "
            "the wrong reason. Abstention is the only honest answer for a unit we cannot convert."
        ),
        criteria=GLYCAEMIC,
        patient_id=DIABETIC,
        perturb=partial(convert_units, loinc=HBA1C_LOINC, to_unit="mmol/mol", factor=10.93),
        relation=all_of(
            CriterionBecomesUnknown("hba1c-elevated"),
            OnlyThisCriterionChanges("hba1c-elevated"),
        ),
    ),
    MetamorphicCase(
        id="onset-leaving-the-window-is-invisible-only-to-the-window",
        description=(
            "Moving a diabetes diagnosis from inside the last 12 months back to 2015 must flip the "
            "criterion that carries that window, while the criterion reading 'ever' holds."
        ),
        rationale=(
            "`_in_window` admits a dated row only between the window start and the screening date, "
            "so the windowed criterion must stop seeing the diagnosis. `relation='ever'` short-"
            "circuits that test entirely, so the history criterion must go on seeing it. One "
            "perturbation, two opposite obligations, and no annotator needed for either."
        ),
        criteria=DIABETES_HISTORY,
        patient_id=DIABETIC,
        perturb=partial(
            shift_date, resource_id=DIABETIC_DIAGNOSIS_RESOURCE, to=date(2015, 1, 5)
        ),
        relation=all_of(
            CriterionVerdictFlips("recent-diabetes"),
            OnlyThisCriterionChanges("recent-diabetes"),
        ),
    ),
    MetamorphicCase(
        id="result-leaving-the-window-forces-abstention",
        description=(
            "Moving the only in-window creatinine result back to 2019 must leave the creatinine "
            "criterion unresolved, not fall back to an older result."
        ),
        rationale=(
            "There are nine older creatinine results on this chart and every one of them is "
            "outside the twelve-month window. A criterion that resolved anyway would be answering "
            "a question the protocol did not ask."
        ),
        criteria=RENAL_PANEL,
        patient_id=FRESH_CHART,
        perturb=partial(
            shift_date, resource_id=FRESH_CREATININE_RESOURCE, to=date(2019, 3, 4)
        ),
        relation=all_of(
            CriterionBecomesUnknown("creatinine-band"),
            OnlyThisCriterionChanges("creatinine-band"),
        ),
    ),
    MetamorphicCase(
        id="closing-the-coverage-window-forces-abstention",
        description=(
            "Removing every encounter from 2026 must turn a satisfied absence criterion into an "
            "abstention under COVERAGE_GATED, and must not disturb the lab criterion beside it."
        ),
        rationale=(
            "This is the load-bearing demonstration that `AbsencePolicy` is a real choice. Nothing "
            "about the patient changed: no myocardial infarction was on the chart before and none "
            "is on it now. What changed is that no encounter documents the window any more, so "
            "'the patient did not have one' is no longer distinguishable from 'nobody was looking'."
        ),
        criteria=CARDIAC,
        patient_id=FRESH_CHART,
        perturb=partial(remove_encounters, after=date(2025, 12, 31)),
        relation=all_of(
            CriterionBecomesUnknown("no-recent-mi"),
            OnlyThisCriterionChanges("no-recent-mi"),
        ),
        policy=AbsencePolicy.COVERAGE_GATED,
    ),
    MetamorphicCase(
        id="closed-world-reads-the-same-silence-as-absence",
        description=(
            "The identical removal of every 2026 encounter must change nothing at all under "
            "CLOSED_WORLD."
        ),
        rationale=(
            "Same patient, same criteria, same perturbation as the case above; only the policy "
            "differs. CLOSED_WORLD reads silence as absence and never consults the encounter "
            "record, so it must be indifferent to the change. Together the pair shows that the "
            "policy label maps onto a difference in behaviour rather than onto documentation."
        ),
        criteria=CARDIAC,
        patient_id=FRESH_CHART,
        perturb=partial(remove_encounters, after=date(2025, 12, 31)),
        relation=AllVerdictsUnchanged(),
        policy=AbsencePolicy.CLOSED_WORLD,
    ),
    MetamorphicCase(
        id="a-new-diagnosis-is-seen-by-the-criterion-that-names-it",
        description=(
            "Adding a myocardial infarction dated inside the window must flip the criterion that "
            "requires its absence, and leave the unrelated lab criterion alone."
        ),
        rationale=(
            "The mirror image of redaction: evidence that arrives must be read. The added row "
            "carries the SNOMED code the criterion's concept resolves to, so the match is by code "
            "rather than by wording, and no other criterion mentions the concept."
        ),
        criteria=CARDIAC,
        patient_id=FRESH_CHART,
        perturb=partial(
            add_condition, code=MI_CODE, display=MI_DISPLAY, onset=date(2026, 3, 2)
        ),
        relation=all_of(
            CriterionVerdictFlips("no-recent-mi"),
            OnlyThisCriterionChanges("no-recent-mi"),
        ),
    ),
    MetamorphicCase(
        id="adding-evidence-never-lowers-coverage",
        description=(
            "Adding a diagnosis to a chart that documents nothing recent must not leave fewer "
            "criteria decided than before."
        ),
        rationale=(
            "Coverage gating withholds a verdict on absence, never on presence: a criterion that "
            "abstained because no encounter documented the window becomes decidable the moment "
            "matching evidence appears. More generally, adding rows to a chart can only ever move "
            "coverage up, and a system where it moved down would be unusable."
        ),
        criteria=STALE_SCREEN,
        patient_id=STALE_CHART,
        perturb=partial(
            add_condition, code=MI_CODE, display=MI_DISPLAY, onset=date(2026, 1, 15)
        ),
        relation=CoverageDoesNotDecrease(),
    ),
    MetamorphicCase(
        id="closed-world-had-already-decided-and-merely-flips",
        description=(
            "The same addition to the same stale chart, read under CLOSED_WORLD, must flip a "
            "criterion that was already resolved rather than resolve one that was not."
        ),
        rationale=(
            "Paired with the case above to show what coverage gating actually buys. CLOSED_WORLD "
            "had already answered the absence question from silence, so the new diagnosis can only "
            "flip it; COVERAGE_GATED had abstained, so the same diagnosis converts an abstention "
            "into a verdict. The chart edit is identical in both."
        ),
        criteria=STALE_SCREEN,
        patient_id=STALE_CHART,
        perturb=partial(
            add_condition, code=MI_CODE, display=MI_DISPLAY, onset=date(2026, 1, 15)
        ),
        relation=all_of(
            CriterionVerdictFlips("no-recent-mi"),
            OnlyThisCriterionChanges("no-recent-mi"),
        ),
        policy=AbsencePolicy.CLOSED_WORLD,
    ),
    MetamorphicCase(
        id="relaxing-every-threshold-never-lowers-coverage",
        description=(
            "Screening the same patient against the same trial with every numeric bound widened "
            "until anything satisfies it must not leave fewer criteria decided."
        ),
        rationale=(
            "Coverage measures what the chart supports, not how demanding the protocol is. This "
            "patient's chart stops in 2015, so both runs must abstain on both lab criteria for "
            "want of an in-window result -- a trivial bound cannot conjure a measurement. A "
            "system that resolved more here would be resolving criteria it has no data for."
        ),
        criteria=GLYCAEMIC,
        patient_id=STALE_CHART,
        perturb=unchanged,
        relation=CoverageDoesNotDecrease(),
        criteria_after=GLYCAEMIC_RELAXED,
    ),
)
