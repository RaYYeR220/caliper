"""Metamorphic evaluation: assertions about a pair of runs, never about a single answer.

A metamorphic test does not say what the right answer is. It changes one thing about the input in
a way whose consequence is fixed by the design, then asserts the *relationship* between the two
runs: redact the only creatinine on a chart and the renal criterion must move from a verdict to
UNKNOWN; restate that same creatinine in micromoles per litre with the arithmetic done correctly
and every verdict must be identical. Neither claim needs an annotator, and neither can be argued
with by someone who reads the chart differently than we do.

That is why this suite is stronger evidence than our own answer key. The key is a set of labels we
wrote, so a reader who distrusts our clinical judgement has to take them on faith. The relations
below are entailed by the specification itself — by `AbsencePolicy`, by the unit table's refusal
to guess, by the window semantics in `record.py` — so a green result here survives disagreeing
with us about any individual patient. No model is involved anywhere: every criteria set in this
file is hand-written, and every patient is read from the committed corpus.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, replace
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
from caliper.logic import ScreeningOutcome, Verdict
from caliper.perturb import (
    Perturbation,
    PerturbationError,
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
            return f"the decision moved {before.decision.name} -> {after.decision.name}"
        return None


def _block_problems(label: str, result: ScreeningResult, expected: bool) -> list[str]:
    """Whether one run was stopped by a screening-level fact, and whether it stopped properly."""
    blocked = result.blocked_by is not None
    if blocked is not expected:
        return [
            f"the {label} run was {'blocked' if blocked else 'evaluated'} "
            f"({result.decision.name}, {len(result.criteria)} criteria)"
        ]
    if not blocked:
        return [] if result.criteria else [f"the {label} run evaluated no criteria at all"]

    problems = []
    if result.criteria:
        problems.append(
            f"the {label} run was blocked but still evaluated {len(result.criteria)} criteria"
        )
    if result.decision is not ScreeningOutcome.INELIGIBLE:
        problems.append(f"the {label} run was blocked but decided {result.decision.name}")
    return problems


@dataclass(frozen=True)
class ScreeningBlockedOn(Relation):
    """Whether `screen` stops on a screening-level fact before the perturbation, after it, or both.

    A block is not a criterion and carries no criterion id: `screen` returns an empty criteria
    table and an INELIGIBLE decision without evaluating anything. So this relation is about the two
    screenings as wholes, which is the only honest way to assert something about a chart that is
    never read. It also insists that a block look like one — no criteria, and INELIGIBLE — because
    a block that left a half-filled table behind would be worse than no block at all.
    """

    before_blocked: bool
    after_blocked: bool

    @property
    def summary(self) -> str:
        def word(blocked: bool) -> str:
            return "blocked" if blocked else "evaluated"

        return (
            f"the screening is {word(self.before_blocked)} before the perturbation "
            f"and {word(self.after_blocked)} after it"
        )

    def check(self, before: ScreeningResult, after: ScreeningResult) -> str | None:
        problems = _block_problems("before", before, self.before_blocked) + _block_problems(
            "after", after, self.after_blocked
        )
        return "; ".join(problems) if problems else None


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
# The case type, and the two perturbations this package builds for itself
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
    """The second run's criteria, for a case that perturbs the trial instead of the chart.

    Almost every relation here is about editing a chart, but one invariant worth asserting is about
    editing the protocol: relaxing every threshold must not change how much of the chart is
    readable. That needs a second criteria set rather than a second patient, and it is hand-written
    like the first.
    """


def unchanged(patient: PatientIndex) -> PerturbedPatient:
    """Leave the chart exactly as it is, for the case whose perturbation is to the trial."""
    return PerturbedPatient(patient=patient, perturbations=())


def record_death(patient: PatientIndex, *, on: date | None) -> PerturbedPatient:
    """Rewrite the recorded date of death, touching nothing else on the chart.

    `caliper.perturb` has no function for this and it is not this package's to add, so the second
    `PatientIndex` is built here. The evidence list is copied rather than shared, so the two
    indexes cannot alias each other's rows, and a no-op raises for the same reason every function
    in `caliper.perturb` does: a case must not claim an edit that was never made.
    """
    if patient.deceased == on:
        raise PerturbationError(
            f"patient {patient.patient_id} already records "
            f"{'no death' if on is None else f'a death on {on.isoformat()}'}"
        )
    changed = replace(patient, deceased=on, evidence=list(patient.evidence))
    stamp = "no death" if on is None else on.isoformat()
    was = "no death" if patient.deceased is None else patient.deceased.isoformat()
    record = Perturbation(
        kind="record_death",
        description=f"changed the recorded date of death from {was} to {stamp}",
        affected_resource_ids=(patient.patient_id,),
        before=({"deceased": None if patient.deceased is None else was},),
        after=({"deceased": None if on is None else stamp},),
    )
    return PerturbedPatient(patient=changed, perturbations=(record,))


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
    codes=(
        Code(system="LOINC", code="4548-4", display="Hemoglobin A1c/Hemoglobin.total in Blood"),
    ),
)
MYOCARDIAL_INFARCTION = Concept(
    text="myocardial infarction",
    codes=(Code(system="SNOMED", code="22298006", display="Myocardial infarction"),),
)
HYPERTENSION = Concept(
    text="essential hypertension",
    codes=(Code(system="SNOMED", code="59621000", display="Essential hypertension"),),
)
METABOLIC_SYNDROME = Concept(
    text="metabolic syndrome",
    codes=(Code(system="SNOMED", code="237602007", display="Metabolic syndrome X"),),
)
OBESITY = Concept(
    text="obesity",
    codes=(Code(system="SNOMED", code="162864005", display="Body mass index 30+ - obesity"),),
)
LISINOPRIL = Concept(
    text="lisinopril",
    codes=(Code(system="RxNorm", code="314076", display="lisinopril 10 MG Oral Tablet"),),
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
    predicate=ObservationPredicate(concept=HBA1C, op="<", value=7.0, unit="%", window=LAST_YEAR),
)
HBA1C_ELEVATED = Criterion(
    id="hba1c-elevated",
    kind="inclusion",
    source_quote="HbA1c of 7.0% or above within the last 12 months.",
    predicate=ObservationPredicate(concept=HBA1C, op=">=", value=7.0, unit="%", window=LAST_YEAR),
)
HBA1C_BELOW_NINE = Criterion(
    id="hba1c-below-nine",
    kind="inclusion",
    source_quote="HbA1c below 9.0% within the last 12 months.",
    predicate=ObservationPredicate(concept=HBA1C, op="<", value=9.0, unit="%", window=LAST_YEAR),
)
ON_ACE_INHIBITOR = Criterion(
    id="on-ace-inhibitor",
    kind="inclusion",
    source_quote="Prescribed lisinopril within the last 12 months.",
    predicate=PresencePredicate(
        type="medication", concept=LISINOPRIL, presence="present", window=LAST_YEAR
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
RECENT_HYPERTENSION = Criterion(
    id="recent-hypertension",
    kind="inclusion",
    source_quote="Essential hypertension diagnosed within the last 12 months.",
    predicate=PresencePredicate(
        type="condition", concept=HYPERTENSION, presence="present", window=LAST_YEAR
    ),
)
HYPERTENSION_EVER = Criterion(
    id="hypertension-ever",
    kind="inclusion",
    source_quote="A documented diagnosis of essential hypertension at any time.",
    predicate=PresencePredicate(
        type="condition", concept=HYPERTENSION, presence="present", window=EVER
    ),
)
METABOLIC_SYNDROME_EXCLUDED = Criterion(
    id="metabolic-syndrome-excluded",
    kind="exclusion",
    source_quote="Any documented diagnosis of metabolic syndrome.",
    predicate=PresencePredicate(
        type="condition", concept=METABOLIC_SYNDROME, presence="present", window=EVER
    ),
)
OBESITY_EVER = Criterion(
    id="obesity-ever",
    kind="inclusion",
    source_quote="A documented body mass index of 30 or above at any time.",
    predicate=PresencePredicate(
        type="condition", concept=OBESITY, presence="present", window=EVER
    ),
)

RENAL_PANEL = _trial("MM-RENAL", CREATININE_BAND, HBA1C_CONTROLLED, ADULT)
RENAL_CEILING = _trial("MM-RENAL-CEILING", CREATININE_CEILING, ADULT)
GLYCAEMIC = _trial("MM-GLYCAEMIC", HBA1C_ELEVATED, CREATININE_BAND, ON_ACE_INHIBITOR, ADULT)
GLYCAEMIC_EXCLUDING_SYNDROME = _trial(
    "MM-GLYCAEMIC-EXCL", HBA1C_BELOW_NINE, METABOLIC_SYNDROME_EXCLUDED
)
HYPERTENSION_HISTORY = _trial("MM-HTN", RECENT_HYPERTENSION, HYPERTENSION_EVER, ADULT)
CARDIAC = _trial("MM-CARDIAC", NO_RECENT_MI, CREATININE_BAND)
STALE_SCREEN = _trial("MM-STALE", NO_RECENT_MI, OBESITY_EVER)

# The same trial with every numeric bound widened until any value satisfies it. The criterion ids
# are deliberately identical, so the two runs line up criterion for criterion in a report.
RENAL_PANEL_RELAXED = _trial(
    "MM-RENAL",
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
        id="hba1c-controlled",
        kind="inclusion",
        source_quote="HbA1c below 1000.0% within the last 12 months.",
        predicate=ObservationPredicate(
            concept=HBA1C, op="<", value=1000.0, unit="%", window=LAST_YEAR
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

# Essential hypertension, metabolic syndrome and a lisinopril prescription all dated 2026-02-01,
# four months inside the window, with labs from the same visit.
HYPERTENSIVE = "35f80d0e-eaad-ef68-b762-3a1c12a872c1"

# Creatinine 2.578 mg/dL, comfortably the wrong side of a 1.5 mg/dL ceiling.
IMPAIRED_RENAL = "f870c432-0887-125e-f778-cf5110d3de1d"

# A chart that stops in December 2024: no encounter documents the last twelve months, which is what
# makes coverage-gated absence abstain on it before anything has been perturbed at all.
STALE_CHART = "bd4e49cb-391b-d08a-c7ab-b585e7bd5758"

# Recorded as having died on 2026-05-03, four weeks before the screening date, on a chart that is
# otherwise complete and current-looking. `screen` must stop on that before reading any of it.
DECEASED = "1be83f06-48ef-7bac-7097-b9e0644aeaf8"

# The one creatinine result inside the twelve-month window on FRESH_CHART; the next is 2025-05-24,
# a week the wrong side of it, so moving this resource empties the window.
FRESH_CREATININE_RESOURCE = "23da8e71-dfb9-9773-9850-4c4fe75f1e42"

# The essential hypertension Condition on HYPERTENSIVE, onset 2026-02-01 and the only one.
HYPERTENSION_RESOURCE = "35f80d0e-eaad-ef68-5726-01e3106bb28f"

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
        criteria=GLYCAEMIC_EXCLUDING_SYNDROME,
        patient_id=HYPERTENSIVE,
        perturb=partial(redact_analyte, loinc=HBA1C_LOINC),
        relation=all_of(
            CriterionBecomesUnknown("hba1c-below-nine"),
            OutcomeUnchanged(),
        ),
    ),
    MetamorphicCase(
        id="hba1c-crossing-the-threshold-flips-one-verdict",
        description=(
            "Moving the HbA1c from 6.11% to 7.1% against a criterion reading 'at least 7.0%' must "
            "flip that criterion, and only that criterion."
        ),
        rationale=(
            "The comparison is `>=` against 7.0, so 6.11 and 7.1 fall on opposite sides of it by "
            "arithmetic. Nothing else in the trial reads HbA1c — the other three criteria read "
            "creatinine, a prescription and a date of birth — so a second verdict moving would "
            "mean criteria are not being evaluated independently."
        ),
        criteria=GLYCAEMIC,
        patient_id=HYPERTENSIVE,
        perturb=partial(shift_value, loinc=HBA1C_LOINC, to=7.1),
        relation=all_of(
            CriterionVerdictFlips("hba1c-elevated"),
            OnlyThisCriterionChanges("hba1c-elevated"),
        ),
    ),
    MetamorphicCase(
        id="hba1c-moving-within-one-side-changes-nothing",
        description=(
            "Moving the HbA1c from 6.11% to 6.9% — a real change, but still under the 7.0% "
            "threshold — must leave every verdict alone."
        ),
        rationale=(
            "The companion to the flip case. A verdict is a function of which side of the bound "
            "the value lands on, not of the value itself or of how close it came, so a system that "
            "moved here would be reading something other than the criterion it was given."
        ),
        criteria=GLYCAEMIC,
        patient_id=HYPERTENSIVE,
        perturb=partial(shift_value, loinc=HBA1C_LOINC, to=6.9),
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
            "mmol/mol is the IFCC unit for HbA1c and lands in the tens where a percentage lands in "
            "single figures. A system reading the bare number would compare it against a bound of "
            "7.0 and flip the criterion to met on a value that means nothing of the sort. "
            "Abstention is the only honest answer for a unit we cannot convert."
        ),
        criteria=GLYCAEMIC,
        patient_id=HYPERTENSIVE,
        perturb=partial(convert_units, loinc=HBA1C_LOINC, to_unit="mmol/mol", factor=10.93),
        relation=all_of(
            CriterionBecomesUnknown("hba1c-elevated"),
            OnlyThisCriterionChanges("hba1c-elevated"),
        ),
    ),
    MetamorphicCase(
        id="onset-leaving-the-window-is-invisible-only-to-the-window",
        description=(
            "Moving a hypertension diagnosis from inside the last 12 months back to 2015 must flip "
            "the criterion that carries that window, while the criterion reading 'ever' holds."
        ),
        rationale=(
            "`_in_window` admits a dated row only between the window start and the screening date, "
            "so the windowed criterion must stop seeing the diagnosis. `relation='ever'` "
            "short-circuits that test entirely, so the history criterion must go on seeing it. One "
            "perturbation, two opposite obligations, and no annotator needed for either."
        ),
        criteria=HYPERTENSION_HISTORY,
        patient_id=HYPERTENSIVE,
        perturb=partial(shift_date, resource_id=HYPERTENSION_RESOURCE, to=date(2015, 1, 5)),
        relation=all_of(
            CriterionVerdictFlips("recent-hypertension"),
            OnlyThisCriterionChanges("recent-hypertension"),
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
        perturb=partial(shift_date, resource_id=FRESH_CREATININE_RESOURCE, to=date(2019, 3, 4)),
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
        perturb=partial(add_condition, code=MI_CODE, display=MI_DISPLAY, onset=date(2026, 3, 2)),
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
        perturb=partial(add_condition, code=MI_CODE, display=MI_DISPLAY, onset=date(2026, 1, 15)),
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
        perturb=partial(add_condition, code=MI_CODE, display=MI_DISPLAY, onset=date(2026, 1, 15)),
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
            "patient's chart stops in December 2024, so both runs must abstain on both lab "
            "criteria for want of an in-window result: a trivial bound cannot conjure a "
            "measurement. A system that resolved more here would be resolving criteria it has no "
            "data for."
        ),
        criteria=RENAL_PANEL,
        patient_id=STALE_CHART,
        perturb=unchanged,
        relation=CoverageDoesNotDecrease(),
        criteria_after=RENAL_PANEL_RELAXED,
    ),
    MetamorphicCase(
        id="a-death-before-screening-stops-everything",
        description=(
            "A chart recording a death four weeks before the screening date must be stopped before "
            "any criterion is read; moving that death after the screening date must let the same "
            "chart screen normally."
        ),
        rationale=(
            "`screen` consults `died_before` before it evaluates anything, and the chart itself is "
            "byte-for-byte the same on both sides — same labs, same encounters, same diagnoses. "
            "Only the recorded date of death moves, so any difference between the two runs is "
            "attributable to it and to nothing else. This is the case that would have caught a "
            "vital-status check wired to the wrong comparison or to no comparison at all."
        ),
        criteria=RENAL_PANEL,
        patient_id=DECEASED,
        perturb=partial(record_death, on=date(2026, 9, 1)),
        relation=ScreeningBlockedOn(before_blocked=True, after_blocked=False),
    ),
    MetamorphicCase(
        id="a-recorded-death-blocks-an-otherwise-complete-chart",
        description=(
            "Recording a death two weeks before the screening date on an otherwise complete chart "
            "must stop the screening, leaving no criteria evaluated and an ineligible decision."
        ),
        rationale=(
            "The dangerous direction. Every criterion on this chart resolves and the patient looks "
            "enrollable, so a vital-status check that failed open would produce a green packet for "
            "someone who cannot consent. The relation demands the block, not merely a different "
            "verdict somewhere."
        ),
        criteria=RENAL_PANEL,
        patient_id=FRESH_CHART,
        perturb=partial(record_death, on=date(2026, 5, 15)),
        relation=ScreeningBlockedOn(before_blocked=False, after_blocked=True),
    ),
    MetamorphicCase(
        id="a-death-after-the-screening-date-is-not-retroactive",
        description=(
            "Recording a death a month after the screening date must not block the screening or "
            "change a single verdict."
        ),
        rationale=(
            "The boundary on the other side. A screening is a statement about what the chart said "
            "on the screening date, and `died_before` is written to compare against exactly that "
            "date. A check that blocked on any recorded death would rewrite history every time a "
            "chart was re-read later, which is precisely what a fixed screening date exists to "
            "prevent."
        ),
        criteria=RENAL_PANEL,
        patient_id=FRESH_CHART,
        perturb=partial(record_death, on=date(2026, 7, 1)),
        relation=all_of(
            ScreeningBlockedOn(before_blocked=False, after_blocked=False),
            AllVerdictsUnchanged(),
        ),
    ),
)
