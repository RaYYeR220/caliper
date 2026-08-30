"""`caliper ui demo` — build the coordinator interface's data without reaching a model.

The interface in `web/` has to show real screenings or it shows nothing worth looking at. A live run
needs an API key and a budget, and a reviewer opening this repository has neither, so the demo
bundle is built the only other honest way: the compiler's output is written by hand, and everything
downstream of it is the system itself.

What is hand-written is exactly two things per trial, and both are things a language model would
otherwise have produced: the `CriteriaSet` — one criterion per compile unit, with the protocol
quoted verbatim — and the critic's severity and reason for each criterion it reviewed. Everything
else on screen is computed here and now: the units are planned by `plan_units`, the back-translated
English by `render_predicate`, the coverage by `coverage_report`, the downgrades by
`apply_findings`, the verdicts by `screen` against the committed FHIR bundles, and the rationale
sentences by the evaluator itself. No number in the interface was typed by a person.

Neither compilation is flattering. Thirteen of NCT01131676's twenty-two criteria could not be
formalised at all and three more did not survive back-translation; six of NCT03315143's eight could
not be formalised. That is what these protocols look like when you refuse to guess, and it is the
case the interface exists to make.

Two cohorts are screened, and the bundle keeps them apart in the data as well as on screen.

The **observed** cohort is the committed corpus, unedited, against both trials. Not one chart in it
reaches `eligible`, and the reason is worth showing rather than leaving as an absence: `ELIGIBLE`
is unreachable while any criterion is unresolved, and both protocols contain criteria no chart can
settle.

The **constructed** cohort is the fifteen `provenance: "constructed"` cases of the answer key —
charts edited to supply a measurement the patient never had, so that a stated threshold can be
crossed on purpose. Their edits are replayed here from the frozen key's own `perturbations` records,
which are the published diff, and every replayed edit is read back off the finished chart. Four base
charts carry a full triple: the same patient and trial, one supplied number apart, so that a reader
can watch a bound being evaluated rather than approximated.

An edited chart must never be mistakable for an observed one. Where a chart came from is a fact
about this demo's inputs rather than about the screening `uiexport` computes from them, so it is
`_annotate_bundle` here that writes it onto the finished bundle, and the interface reads a
screening carrying no such mark as observed.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from caliper import corpus
from caliper.agents.compiler import CompileResult, plan_units
from caliper.agents.critic import (
    CriticReport,
    Finding,
    Severity,
    apply_findings,
    coverage_report,
    render_predicate,
)
from caliper.agents.writer import deterministic_rationales
from caliper.answerkey import Case, load_key, verify_frozen
from caliper.criteria_text import segment, unescape_registry_markdown
from caliper.evaluate import AbsencePolicy
from caliper.ir import (
    Code,
    CompositePredicate,
    Concept,
    CriteriaSet,
    Criterion,
    DemographicPredicate,
    ObservationPredicate,
    PresencePredicate,
    TemporalWindow,
    UnsupportedPredicate,
    concepts_in,
    quote_fidelity_problems,
)
from caliper.packet import DECISION_WORDS
from caliper.pipeline import CompiledTrial, PipelineConfig, Screening
from caliper.record import Evidence, PatientIndex
from caliper.screen import screen
from caliper.uiexport import (
    DATA_DIRNAME,
    INDEX_NAME,
    ScreeningRecord,
    screening_filename,
    write_ui_bundle,
)

app = typer.Typer(add_completion=False)
console = Console()


@app.callback()
def ui() -> None:
    """Build the data the coordinator interface reads.

    Declared as a callback so the sub-app stays a command group with one command in it, rather than
    collapsing into a bare `caliper ui` once it is mounted on the main CLI.
    """

FIXTURE_NCT = "NCT01131676"

CONSTRUCTED_NCT = "NCT03315143"
"""The trial the answer key's constructed cases were built against, so the demo screens it too.

Every constructed case in the key is on this trial, because it is the only one in the key whose
in-scope criteria can all be closed with terminology the committed corpus already uses
(`eval/annotation/protocol.md`, section 9). Screening those edited charts against NCT01131676 would
show nothing: the edits close none of its criteria, and all fifteen would land on the same verdict.
"""

REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_ROOT = REPO_ROOT / "web"

ANSWER_KEY = REPO_ROOT / "eval" / "answer_key.json"

DEMO_SCREENING_DATE = date(2026, 4, 1)
"""The date the demo cohort is screened against, and it is not the corpus's own reference date.

`corpus.default_screening_date()` is 2026-06-01, and the one patient in the committed corpus who
carries a type 2 diabetes diagnosis is recorded as having died on 2026-05-03. Screening on the
corpus date therefore closes every screening in the cohort before a criterion is evaluated, which
would demonstrate the interface against no open work at all. Two months earlier the same charts
still support a live decision. `--as-of` reproduces either.
"""

SCREENING_DATE_NOTE = (
    "Screened on {as_of}, not the {corpus_date} that the answer key and every other artefact in "
    "this repository use. The corpus's only patient with a type 2 diabetes diagnosis is recorded "
    "as having died on 2026-05-03, so on {corpus_date} that screening closes on the death before "
    "a criterion is read and the cohort has no open work left in it at all. Two months earlier the "
    "same charts still support a live decision, and caliper ui demo --as-of {corpus_date} "
    "reproduces the other reading."
)
"""Said in the interface, because a date that differs from every other figure is how two numbers
come to disagree with nobody able to say why."""

# "prior to informed consent" and "within 2 months prior to informed consent" are anchored to
# consent, not to screening. Caliper only ever has the screening date, so recording the anchor is
# what turns a silent substitution into a reported approximation on every result that depends on it.
AT_CONSENT = TemporalWindow(relation="current", anchor="consent")
WITHIN_TWO_MONTHS = TemporalWindow(relation="within", amount=2, unit="months", anchor="consent")
WITHIN_FIVE_YEARS = TemporalWindow(relation="within", amount=5, unit="years")

T2DM = Concept(
    text="type 2 diabetes mellitus",
    codes=(Code(system="SNOMED", code="44054006", display="Diabetes mellitus type 2 (disorder)"),),
)
HBA1C = Concept(
    text="HbA1c",
    codes=(
        Code(system="LOINC", code="4548-4", display="Hemoglobin A1c/Hemoglobin.total in Blood"),
    ),
)
BMI = Concept(
    text="body mass index",
    codes=(Code(system="LOINC", code="39156-5", display="Body mass index (BMI) [Ratio]"),),
)
GLUCOSE = Concept(
    text="blood glucose",
    codes=(
        Code(system="LOINC", code="2339-0", display="Glucose [Mass/volume] in Blood"),
        Code(system="LOINC", code="2345-7", display="Glucose [Mass/volume] in Serum or Plasma"),
    ),
)
ALT = Concept(
    text="alanine aminotransferase",
    codes=(
        Code(system="LOINC", code="1742-6", display="Alanine aminotransferase in Serum or Plasma"),
    ),
)
GFR = Concept(
    text="glomerular filtration rate",
    codes=(
        Code(
            system="LOINC",
            code="33914-3",
            display="Glomerular filtration rate by Creatinine-based formula (MDRD)/1.73 sq M",
        ),
    ),
)
MALIGNANCY = Concept(
    text="malignant neoplastic disease",
    codes=(
        Code(system="SNOMED", code="363346000", display="Malignant neoplastic disease (disorder)"),
    ),
)
BASAL_CELL = Concept(
    text="basal cell carcinoma",
    codes=(Code(system="SNOMED", code="254701007", display="Basal cell carcinoma (disorder)"),),
)
ACUTE_CORONARY = Concept(
    text="acute coronary syndrome",
    codes=(
        Code(system="SNOMED", code="394659003", display="Acute coronary syndrome (disorder)"),
        Code(system="SNOMED", code="22298006", display="Myocardial infarction (disorder)"),
    ),
)
STROKE = Concept(
    text="stroke",
    codes=(Code(system="SNOMED", code="230690007", display="Cerebrovascular accident (disorder)"),),
)
TIA = Concept(
    text="transient ischaemic attack",
    codes=(
        Code(system="SNOMED", code="266257000", display="Transient ischemic attack (disorder)"),
    ),
)


def _criteria_nct01131676(source_text: str) -> CriteriaSet:
    """The compilation, as a model would have returned it, one criterion per compile unit.

    Identifiers follow `compiler._identifier`: numbered within their section, in document order, so
    that a reviewer comparing this against a live run is comparing like with like.
    """
    criteria = [
        Criterion(
            id="INC-01",
            kind="inclusion",
            source_quote="Diagnosis of type 2 diabetes mellitus prior to informed consent",
            predicate=PresencePredicate(
                type="condition", concept=T2DM, presence="present", window=AT_CONSENT
            ),
        ),
        Criterion(
            id="INC-02",
            kind="inclusion",
            source_quote=(
                "Male or female patients on diet and exercise regimen who are drug naive or pre "
                "treated with any background therapy. Antidiabetic therapy has to be unchanged "
                "for 12 weeks prior to randomization."
            ),
            predicate=UnsupportedPredicate(
                reason=(
                    "the chart records prescriptions, not whether antidiabetic therapy was "
                    "unchanged over the 12 weeks before randomisation"
                )
            ),
        ),
        Criterion(
            id="INC-03",
            kind="inclusion",
            source_quote=(
                "Glycosylated haemoglobin (HbA1c) of >= 7.0% and <=10% for patients on background "
                "therapy or HbA1c >= 7.0% and <= 9.0% for drug naive patients"
            ),
            predicate=ObservationPredicate(
                concept=HBA1C, op="between", value=7.0, value_high=10.0, unit="%"
            ),
            notes="the ceiling depends on whether the patient is drug naive, which is not compiled",
        ),
        Criterion(
            id="INC-04",
            kind="inclusion",
            source_quote="Age >= 18 years",
            predicate=DemographicPredicate(field="age", op=">=", value=18, unit="years"),
        ),
        Criterion(
            id="INC-05",
            kind="inclusion",
            source_quote="Body Mass index <= 45 at Visit 1",
            predicate=ObservationPredicate(concept=BMI, op="<=", value=45, unit="kg/m2"),
        ),
        Criterion(
            id="INC-06",
            kind="inclusion",
            source_quote="Signed and dated informed consent",
            predicate=UnsupportedPredicate(
                reason="consent is a site procedure and leaves no finding in the patient record"
            ),
        ),
        Criterion(
            id="INC-07",
            kind="inclusion",
            source_quote="High cardiovascular risk",
            predicate=UnsupportedPredicate(
                reason=(
                    "the protocol defines high cardiovascular risk in a table the registry record "
                    "does not carry"
                )
            ),
        ),
        Criterion(
            id="EXC-01",
            kind="exclusion",
            source_quote=(
                "Uncontrolled hyperglycaemia with a glucose level >240 mg/dl (>13.3 mmol/L) after "
                "an overnight fast during placebo run-in and confirmed by a second measurement "
                "(not on the same day)"
            ),
            predicate=ObservationPredicate(concept=GLUCOSE, op=">", value=240, unit="mg/dL"),
        ),
        Criterion(
            id="EXC-02",
            kind="exclusion",
            source_quote=(
                "Indication of liver disease, defined by serum levels of either alanine "
                "aminotransferase (ALT), aspartate aminotransferase ALT or alkaline phosphatase "
                "above 3 x upper limit of normal (ULN) as determined at screening and/or run in."
            ),
            predicate=ObservationPredicate(concept=ALT, op=">", value=120, unit="U/L"),
        ),
        Criterion(
            id="EXC-03",
            kind="exclusion",
            source_quote="Planned cardiac surgery or angioplasty within 3 months",
            predicate=UnsupportedPredicate(
                reason="a planned procedure is an intention, and the chart records events"
            ),
        ),
        Criterion(
            id="EXC-04",
            kind="exclusion",
            source_quote=(
                "Impaired renal function, defined as Glomerular Filtration Rate <30 ml/min "
                "(severe renal impairment, Modification of Diet in Renal Disease formula) during "
                "screening or run in."
            ),
            predicate=ObservationPredicate(concept=GFR, op="<", value=30, unit="mL/min"),
        ),
        Criterion(
            id="EXC-05",
            kind="exclusion",
            source_quote=(
                "Bariatric surgery within the past two years and other gastrointestinal surgeries "
                "that induce chronic malabsorption"
            ),
            predicate=UnsupportedPredicate(
                reason=(
                    "'other gastrointestinal surgeries that induce chronic malabsorption' names no "
                    "enumerable set of procedure codes"
                )
            ),
        ),
        Criterion(
            id="EXC-06",
            kind="exclusion",
            source_quote=(
                "Blood dyscrasias or any disorders causing haemolysis or unstable Red Blood Cell "
                "(e.g. malaria, babesiosis, haemolytic anemia)"
            ),
            predicate=UnsupportedPredicate(
                reason=(
                    "the criterion names three examples of an open class of disorders, and "
                    "compiling the examples would exclude fewer patients than the protocol does"
                )
            ),
        ),
        Criterion(
            id="EXC-07",
            kind="exclusion",
            source_quote=(
                "Medical history of cancer (except for basal cell carcinoma) and/or treatment for "
                "cancer within the last 5 years"
            ),
            predicate=CompositePredicate(
                type="all_of",
                operands=(
                    PresencePredicate(
                        type="condition",
                        concept=MALIGNANCY,
                        presence="present",
                        window=WITHIN_FIVE_YEARS,
                    ),
                    CompositePredicate(
                        type="not",
                        operands=(
                            PresencePredicate(
                                type="condition",
                                concept=BASAL_CELL,
                                presence="present",
                                window=WITHIN_FIVE_YEARS,
                            ),
                        ),
                    ),
                ),
            ),
        ),
        Criterion(
            id="EXC-08",
            kind="exclusion",
            source_quote="Contraindications to background therapy according to the local label",
            predicate=UnsupportedPredicate(
                reason="the local label is not part of the patient record"
            ),
        ),
        Criterion(
            id="EXC-09",
            kind="exclusion",
            source_quote=(
                "Treatment with anti-obesity drugs (e.g. sibutramine, orlistat) 3 months prior to "
                "informed consent or any other treatment at the time of screening (i.e. surgery, "
                "aggressive diet regimen, etc.) leading to unstable body weight"
            ),
            predicate=UnsupportedPredicate(
                reason=(
                    "the second half of the criterion covers any treatment leading to unstable "
                    "body weight, which names no coded intervention"
                )
            ),
        ),
        Criterion(
            id="EXC-10",
            kind="exclusion",
            source_quote=(
                "Current treatment with systemic steroids at time of informed consent or change "
                "in dosage of thyroid hormones within 6 weeks prior to informed consent or any "
                "other uncontrolled endocrine disorder except type 2 diabetes mellitus"
            ),
            predicate=UnsupportedPredicate(
                reason=(
                    "a change in thyroid dose and an uncontrolled endocrine disorder are neither "
                    "of them recorded as a codeable finding"
                )
            ),
        ),
        Criterion(
            id="EXC-11",
            kind="exclusion",
            source_quote=(
                "Pre-menopausal women (last menstruation <+ 1 year prior to informed consent) who:"
            ),
            predicate=UnsupportedPredicate(
                reason=(
                    "birth control and agreement to periodic pregnancy testing are undertakings by "
                    "the patient, not findings in the chart"
                )
            ),
        ),
        Criterion(
            id="EXC-12",
            kind="exclusion",
            source_quote=(
                "Alcohol or drug abuse within the 3 months prior to informed consent that would "
                "interfere with trial participation or any ongoing condition leading to a "
                "decreased compliance to study procedures or study drug intake"
            ),
            predicate=UnsupportedPredicate(
                reason=(
                    "the criterion turns on whether the behaviour would interfere with "
                    "participation, which is a judgement rather than a finding"
                )
            ),
        ),
        Criterion(
            id="EXC-13",
            kind="exclusion",
            source_quote=(
                "Participation in another trial with an investigational drug within 30 days prior "
                "to informed consent"
            ),
            predicate=UnsupportedPredicate(
                reason="participation in another trial is not recorded in the chart"
            ),
        ),
        Criterion(
            id="EXC-14",
            kind="exclusion",
            source_quote=(
                "Any other clinical condition that would jeopardize patients safety while "
                "participating in this clinical trial"
            ),
            predicate=UnsupportedPredicate(
                reason="the criterion is a catch-all reserved for the investigator"
            ),
        ),
        Criterion(
            id="EXC-15",
            kind="exclusion",
            source_quote=(
                "Acute coronary syndrome, stroke or TIA within 2 months prior to informed consent"
            ),
            predicate=CompositePredicate(
                type="any_of",
                operands=(
                    PresencePredicate(
                        type="condition",
                        concept=ACUTE_CORONARY,
                        presence="present",
                        window=WITHIN_TWO_MONTHS,
                    ),
                    PresencePredicate(
                        type="condition",
                        concept=STROKE,
                        presence="present",
                        window=WITHIN_TWO_MONTHS,
                    ),
                    PresencePredicate(
                        type="condition", concept=TIA, presence="present", window=WITHIN_TWO_MONTHS
                    ),
                ),
            ),
        ),
    ]
    return CriteriaSet(nct_id=FIXTURE_NCT, source_text=source_text, criteria=criteria)


# The critic's answer for each criterion it reviewed: how the rendered English relates to the
# protocol quote, and the one sentence naming the difference. Criteria already compiled as
# unsupported are absent, because `review` does not ask about a criterion nobody formalised.
_REVIEW_NCT01131676: dict[str, tuple[Severity, str]] = {
    "INC-01": (
        "equivalent",
        "Both require a recorded diagnosis of type 2 diabetes mellitus and add no further "
        "condition.",
    ),
    "INC-03": (
        "broader",
        "B admits a drug-naive patient whose HbA1c is between 9.0% and 10%, whom A excludes.",
    ),
    "INC-04": ("equivalent", "Both admit patients aged 18 years or older at screening."),
    "INC-05": (
        "equivalent",
        "Visit 1 is the screening visit, and B is evaluated as of the screening date.",
    ),
    "EXC-01": (
        "broader",
        "A requires a fasting measurement confirmed on a second day; B is satisfied by one "
        "random glucose.",
    ),
    "EXC-02": (
        "narrower",
        "A is also triggered by aspartate aminotransferase or alkaline phosphatase above three "
        "times the upper limit of normal; B tests only alanine aminotransferase.",
    ),
    "EXC-04": (
        "equivalent",
        "Both exclude a glomerular filtration rate below 30 ml/min measured around screening.",
    ),
    "EXC-07": (
        "equivalent",
        "Both exclude a documented malignancy other than basal cell carcinoma within the last "
        "five years.",
    ),
    "EXC-15": (
        "equivalent",
        "Both exclude an acute coronary syndrome, a stroke or a transient ischaemic attack in the "
        "two months before screening.",
    ),
}


def _criteria_nct03315143(source_text: str) -> CriteriaSet:
    """The second compilation, in the same form and to the same standard as the first.

    Six of these eight criteria are refused, and the refusals are the same refusals the fixture
    makes for the same shapes of sentence: consent leaves no finding, a plan is not an event, an
    open list of examples enumerates nothing. Reaching a different answer here because this is the
    trial the constructed cohort needs to work on would be the one dishonesty this file cannot
    afford.
    """
    criteria = [
        Criterion(
            id="INC-01",
            kind="inclusion",
            source_quote="Type 2 Diabetes Mellitus with glycosylated hemoglobin (HbA1c) ≥7%.",
            predicate=CompositePredicate(
                type="all_of",
                operands=(
                    PresencePredicate(type="condition", concept=T2DM, presence="present"),
                    ObservationPredicate(concept=HBA1C, op=">=", value=7.0, unit="%"),
                ),
            ),
        ),
        Criterion(
            id="INC-02",
            kind="inclusion",
            source_quote=(
                "Estimated glomerular filtration rate (eGFR) ≥25 and ≤60 "
                "milliliter/minute (mL/min)/1.73 square meter (m^2)."
            ),
            # The unit is the corpus's UCUM spelling of the protocol's own unit, and it has to be:
            # `units.convert` bridges mass and substance, not a rate and a rate per body surface
            # area, so a chart reporting this analyte in plain mL/min goes unresolved rather than
            # being read as though the two were the same quantity.
            predicate=ObservationPredicate(
                concept=GFR, op="between", value=25, value_high=60, unit="mL/min/{1.73_m2}"
            ),
        ),
        Criterion(
            id="INC-03",
            kind="inclusion",
            source_quote=(
                "Age 18 years or older with at least one major cardiovascular risk factor or age "
                "55 years or older with at least two minor cardiovascular risk factors."
            ),
            predicate=UnsupportedPredicate(
                reason=(
                    "the criterion counts major and minor cardiovascular risk factors without "
                    "listing either, so neither branch names anything countable"
                )
            ),
        ),
        Criterion(
            id="INC-04",
            kind="inclusion",
            source_quote="Signed written informed consent.",
            predicate=UnsupportedPredicate(
                reason="consent is a site procedure and leaves no finding in the patient record"
            ),
        ),
        Criterion(
            id="EXC-01",
            kind="exclusion",
            source_quote=(
                "Antihyperglycemic treatment has not been stable within 12 weeks prior to "
                "screening."
            ),
            predicate=UnsupportedPredicate(
                reason=(
                    "the chart records prescriptions, not whether antihyperglycaemic therapy was "
                    "unchanged over the 12 weeks before screening"
                )
            ),
        ),
        Criterion(
            id="EXC-02",
            kind="exclusion",
            source_quote="Planned coronary procedure or surgery after randomization.",
            predicate=UnsupportedPredicate(
                reason="a planned procedure is an intention, and the chart records events"
            ),
        ),
        Criterion(
            id="EXC-03",
            kind="exclusion",
            source_quote=(
                "Lower extremity complications (such as skin ulcer, infection, osteomyelitis, and "
                "gangrene) identified during screening and requiring treatment at randomization."
            ),
            predicate=UnsupportedPredicate(
                reason=(
                    "'such as' leaves the list of lower extremity complications open, and the "
                    "criterion turns on treatment being required at randomisation, which has not "
                    "happened when a chart is screened"
                )
            ),
        ),
        Criterion(
            id="EXC-04",
            kind="exclusion",
            source_quote=(
                "Planning to start a sodium-glucose linked transporter-2 (SGLT2) inhibitor during "
                "the study."
            ),
            predicate=UnsupportedPredicate(
                reason="starting a drug during the study is an intention, and the chart records "
                "events"
            ),
        ),
    ]
    return CriteriaSet(nct_id=CONSTRUCTED_NCT, source_text=source_text, criteria=criteria)


_REVIEW_NCT03315143: dict[str, tuple[Severity, str]] = {
    "INC-01": (
        "equivalent",
        "Both require a recorded diagnosis of type 2 diabetes mellitus together with a "
        "glycosylated haemoglobin of 7% or more.",
    ),
    "INC-02": (
        "equivalent",
        "Both admit an estimated glomerular filtration rate from 25 to 60 mL/min/1.73 m2 with "
        "both bounds included.",
    ),
}

_COMPILATIONS = {
    FIXTURE_NCT: (_criteria_nct01131676, _REVIEW_NCT01131676),
    CONSTRUCTED_NCT: (_criteria_nct03315143, _REVIEW_NCT03315143),
}


def _review(criteria_set: CriteriaSet, table: dict[str, tuple[Severity, str]]) -> CriticReport:
    """The critic's report, with the rendered sentence and the coverage produced by real code.

    Only the severity and the reason come from the table. `render_predicate` renders what was
    compared and `coverage_report` audits what the compiler left behind, both deterministically.
    """
    findings = tuple(
        Finding(
            criterion_id=criterion.id,
            severity=table[criterion.id][0],
            reason=table[criterion.id][1],
            rendered=render_predicate(criterion.predicate),
            quote=criterion.source_quote,
        )
        for criterion in criteria_set.criteria
        if criterion.id in table
    )
    return CriticReport.from_coverage(findings, coverage_report(criteria_set))


def compile_trial(nct_id: str, criteria_text: str) -> CompiledTrial:
    """Assemble one compiled trial, running every real stage over its hand-written `CriteriaSet`.

    The one thing that would be dishonest here is claiming a model wrote the criteria, so the
    config records the run as it was: the resolver did not run, and the codes on screen are the
    ones the fixture attached.
    """
    build, table = _COMPILATIONS[nct_id]
    source_text = unescape_registry_markdown(criteria_text)
    criteria_set = build(source_text)

    problems = quote_fidelity_problems(criteria_set)
    if problems:
        # A fixture quote that drifted from the protocol would be silently downgraded by the real
        # compiler and would then teach a reviewer the wrong thing about this screen.
        raise typer.BadParameter(
            f"the {nct_id} fixture quotes do not match the protocol text: "
            + "; ".join(f"{p.criterion_id} ({p.reason})" for p in problems)
        )

    report = _review(criteria_set, table)
    applied = apply_findings(criteria_set, report)
    compilation = CompileResult(
        criteria_set=criteria_set,
        units=tuple(plan_units(segment(source_text))),
        rejected=(),
        failures=(),
        downgraded=(),
    )
    return CompiledTrial(
        nct_id=nct_id,
        criteria_set=applied,
        compilation=compilation,
        config=PipelineConfig(use_resolver=False, write_rationales=False),
        resolved_codes={concept.text: concept.codes for concept in concepts_in(criteria_set)},
        critic_report=report,
    )


# ------------------------------------------------------------------------------------------------
# The constructed cohort
# ------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ConstructedChart:
    """One edited chart, and the frozen key's own account of what was edited to produce it."""

    chart: PatientIndex
    case: Case
    edits: tuple[str, ...]


def _rehydrate(snapshot: dict[str, Any]) -> Evidence:
    """One evidence row rebuilt from the record the answer key publishes.

    The synthetic `fhir_path` travels with it. A row that came from a perturbation says so — it
    points at `perturb.add_condition` rather than at a bundle entry — and a viewer that showed a
    plausible-looking pointer resolving to nothing would be worse than one that shows this.
    """
    when = snapshot["date"]
    return Evidence(
        kind=snapshot["kind"],
        resource_type=snapshot["resource_type"],
        resource_id=snapshot["resource_id"],
        display=snapshot["display"],
        fhir_path=snapshot["fhir_path"],
        codes=tuple(Code(system=c["system"], code=c["code"]) for c in snapshot["codes"]),
        value=snapshot["value"],
        unit=snapshot["unit"],
        date=date.fromisoformat(when) if when else None,
    )


def _is(row: Evidence, snapshot: dict[str, Any]) -> bool:
    """Whether this row is the one the record says was removed or replaced.

    A FHIR panel flattens into one row per component, all carrying the same `resource_id`, so the
    identifier alone does not pick a row out. The value, unit, date and codes together do.
    """
    return bool(
        row.resource_id == snapshot["resource_id"]
        and row.value == snapshot["value"]
        and row.unit == snapshot["unit"]
        and (row.date.isoformat() if row.date else None) == snapshot["date"]
        and [{"system": c.system, "code": c.code} for c in row.codes] == snapshot["codes"]
    )


def _replay(rows: list[Evidence], record: dict[str, Any], where: str) -> list[Evidence]:
    """Apply one recorded perturbation to a chart, or refuse to.

    `caliper.perturb` raises rather than returning a chart unchanged, because a constructed case
    whose label asserts an edit that never happened is a wrong answer in the answer key. Replaying
    a published record is held to the same standard: every row the record says it removed has to be
    on the chart exactly once, or this is not the chart the key describes.
    """
    remaining = list(rows)
    for snapshot in record["before"]:
        matched = [row for row in remaining if _is(row, snapshot)]
        if len(matched) != 1:
            raise typer.BadParameter(
                f"{where}: the recorded {record['kind']} names {snapshot['resource_id']} "
                f"({snapshot['value']} {snapshot['unit']}), which the chart carries "
                f"{len(matched)} times"
            )
        remaining.remove(matched[0])
    return [*remaining, *(_rehydrate(snapshot) for snapshot in record["after"])]


def _constructed_patient_id(case: Case) -> str:
    """The identity a constructed chart is filed under.

    It has to differ from the base chart's, and from its two siblings': a triple is three cases on
    one patient and one trial, which would otherwise be three screenings competing for one filename.
    Deriving it from both makes the relationship visible in the identifier itself, and means no
    constructed screening can be filed where a reader would look for an observed one.
    """
    return f"{case.patient_id}~{case.id}"


def constructed_charts(nct_id: str) -> list[ConstructedChart]:
    """Rebuild every constructed chart the frozen answer key records for one trial.

    The key is the source rather than the annotation artifacts it was built from, because the key
    is the artefact with a published digest: if it has been edited since it was frozen, this
    refuses to build a cohort out of it.
    """
    if not verify_frozen(ANSWER_KEY):
        raise typer.BadParameter(
            f"{ANSWER_KEY} does not match its sidecar digest, so the constructed cohort it "
            "describes cannot be trusted; rebuild it with scripts/build_answer_key.py"
        )

    charts = []
    for case in load_key(ANSWER_KEY).cases:
        if case.provenance != "constructed" or case.nct_id != nct_id:
            continue
        base = corpus.load_patient(case.patient_id)
        rows = list(base.evidence)
        for record in case.perturbations:
            rows = _replay(rows, record, case.id)
        charts.append(
            ConstructedChart(
                chart=replace(base, patient_id=_constructed_patient_id(case), evidence=rows),
                case=case,
                edits=tuple(record["description"] for record in case.perturbations),
            )
        )
    return charts


def _provenance(chart: ConstructedChart) -> dict[str, Any]:
    """What the interface needs in order to say, of this screening, that the chart was edited.

    The key's own expected outcome travels with it. It is what the edits were chosen to produce,
    so it is part of saying what was done — and where Caliper's verdict stops short of it, the
    packet has the criteria that explain why.
    """
    case = chart.case
    return {
        "kind": "constructed",
        "case_id": case.id,
        "base_patient_id": case.patient_id,
        "trap": case.trap,
        "edits": list(chart.edits),
        "key_outcome": case.expected.value,
        "key_outcome_label": DECISION_WORDS[case.expected],
        "key": ANSWER_KEY.relative_to(REPO_ROOT).as_posix(),
        "documented_in": "eval/annotation/protocol.md, section 11",
    }


# ------------------------------------------------------------------------------------------------
# Building the bundle
# ------------------------------------------------------------------------------------------------


def screen_charts(
    trial: CompiledTrial, charts: Iterable[PatientIndex], as_of: date
) -> list[ScreeningRecord]:
    """Screen each chart against the compiled trial, in the order given."""
    title = corpus.load_trial(trial.nct_id).title
    records = []
    for chart in charts:
        result = screen(trial.criteria_set, chart, as_of, policy=AbsencePolicy.COVERAGE_GATED)
        screening = Screening(
            trial=trial, result=result, rationales=deterministic_rationales(result)
        )
        records.append(ScreeningRecord(screening=screening, patient=chart, trial_title=title))
    return records


def observed_cohort() -> list[PatientIndex]:
    """Every chart in the committed corpus, as it stands."""
    return [corpus.load_patient(patient_id) for patient_id in corpus.patient_ids()]


def _write(path: Path, payload: dict[str, Any]) -> None:
    """Rewrite one bundle document, byte for byte the way the exporter wrote it.

    Same indentation, same unescaped non-ASCII, same newline written as bytes: a bundle that
    changed shape depending on which of the two functions last touched it would show up as a diff
    for no reason.
    """
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    path.write_bytes((text + "\n").encode("utf-8"))


def _annotate_bundle(
    root: Path, provenance: dict[tuple[str, str], dict[str, Any]], as_of: date
) -> None:
    """Record on the bundle which cohort each screening belongs to, and how the run was made.

    `uiexport` writes what a screening is: a result, a chart, a packet. Where the chart came from
    and why this run chose the date it did are facts about the run rather than about the screening,
    and they belong to whoever assembled the cohort — which is this command. So they are added to
    the documents the exporter has just written, rather than by widening what a screening means for
    every caller. Everything the export does own, it still writes alone.
    """
    data = Path(root) / DATA_DIRNAME
    index_path = data / INDEX_NAME
    index = json.loads(index_path.read_text(encoding="utf-8"))

    index["demo"] = {
        "screened_on": as_of.isoformat(),
        "corpus_screening_date": corpus.default_screening_date().isoformat(),
        "screening_date_note": SCREENING_DATE_NOTE.format(
            as_of=as_of.isoformat(), corpus_date=corpus.default_screening_date().isoformat()
        ),
        "constructed": len(provenance),
    }

    for entry in index["screenings"]:
        record = provenance.get((entry["nct_id"], entry["patient_id"]))
        if record is None:
            continue
        entry["constructed"] = record
        path = data / screening_filename(entry["nct_id"], entry["patient_id"])
        screening = json.loads(path.read_text(encoding="utf-8"))
        screening["constructed"] = record
        _write(path, screening)

    _write(index_path, index)


def _cohort_table(trial: CompiledTrial, records: Sequence[ScreeningRecord], label: str) -> Table:
    """Outcomes for one cohort against one trial.

    The denominator comes from the compilation rather than from the first row: a screening stopped
    by a death carries no criteria at all, and reading the total off one of those would report
    every other row as "3.3 of 0".
    """
    total = len(trial.criteria_set.criteria)
    table = Table("Decision", label, "Criteria resolved", "Gaps a query would close", box=None)
    for decision in ("eligible", "needs_review", "ineligible"):
        results = [
            r.screening.result for r in records if r.screening.result.decision.value == decision
        ]
        if not results:
            continue
        resolved = sum(r.criteria_resolved for r in results) / len(results)
        gaps = [sum(1 for h in r.resolution_worklist if h.fhir_query) for r in results]
        table.add_row(
            decision.replace("_", " "),
            str(len(results)),
            f"{resolved:.1f} of {total}",
            f"{min(gaps)} to {max(gaps)}",
        )
    return table


def _report(compiled: CompiledTrial, records: Sequence[ScreeningRecord], cohort: str) -> None:
    report = compiled.critic_report
    assert report is not None  # `compile_trial` always reviews
    console.print(
        f"{compiled.nct_id}  {len(compiled.criteria_set.criteria)} criteria, "
        f"{compiled.unsupported_count} unresolvable from data, "
        f"{len(report.downgrades)} downgraded by the critic, "
        f"{report.coverage * 100:.0f}% of protocol spans claimed"
    )
    console.print(_cohort_table(compiled, records, cohort))


@app.command("demo")
def demo(
    root: Path = typer.Option(DEFAULT_ROOT, help="The web root to write the bundle into."),
    as_of: str = typer.Option(None, help="Screening date, ISO 8601. See DEMO_SCREENING_DATE."),
) -> None:
    """Build the interface bundle from the committed fixtures. No API key, no network."""
    screening_date = date.fromisoformat(as_of) if as_of else DEMO_SCREENING_DATE
    observed = observed_cohort()

    fixture = compile_trial(FIXTURE_NCT, corpus.load_trial(FIXTURE_NCT).criteria_text)
    fixture_records = screen_charts(fixture, observed, screening_date)

    second = compile_trial(CONSTRUCTED_NCT, corpus.load_trial(CONSTRUCTED_NCT).criteria_text)
    second_records = screen_charts(second, observed, screening_date)

    charts = constructed_charts(CONSTRUCTED_NCT)
    constructed_records = screen_charts(second, [c.chart for c in charts], screening_date)

    written = write_ui_bundle(
        [*fixture_records, *second_records, *constructed_records], root=root
    )
    _annotate_bundle(
        root,
        {(CONSTRUCTED_NCT, chart.chart.patient_id): _provenance(chart) for chart in charts},
        screening_date,
    )

    _report(fixture, fixture_records, "Charts as they stand")
    _report(second, second_records, "Charts as they stand")
    console.print(
        f"{CONSTRUCTED_NCT}  {len(charts)} constructed charts replayed from "
        f"{ANSWER_KEY.relative_to(REPO_ROOT).as_posix()}, "
        f"{sum(len(c.edits) for c in charts)} recorded edits"
    )
    console.print(_cohort_table(second, constructed_records, "Constructed charts"))
    console.print(f"{len(written)} files written to {(Path(root) / 'data').as_posix()}")
    console.print(f"serve it with: python -m http.server --directory {Path(root).as_posix()}")


if __name__ == "__main__":
    app()
