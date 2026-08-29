"""The writer: the one sentence in a screening packet that a model is allowed to author.

Everything else in the packet is generated from the structured screening result. The rationale is
not, so every sentence that comes back is checked against the record it claims to describe. A
sentence that cannot be checked never reaches the page: the packet degrades to the evaluator's own
prose and says on its face that it did. These tests are mostly about that degradation, because it
is the behaviour that keeps an unverifiable claim about a patient out of a document someone signs.
"""

from __future__ import annotations

import json
from datetime import date

from caliper.agents.base import AgentContext
from caliper.agents.writer import (
    PROSE_CHECK_TIER,
    Rationale,
    RationaleSet,
    deterministic_rationales,
    rationale_request,
    write_rationales,
)
from caliper.evaluate import (
    AbsencePolicy,
    CriterionResult,
    ResolutionHint,
    evaluate_criterion,
)
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
)
from caliper.logic import ScreeningOutcome, Verdict
from caliper.prose import check_rationale
from caliper.record import Evidence, PatientIndex
from caliper.screen import ScreeningResult

from fakes import a_routed_client

SCREENING = date(2026, 6, 1)

CREATININE = Code(system="LOINC", code="2160-0", display="Creatinine")
CREATININE_CONCEPT = Concept(text="serum creatinine", codes=(CREATININE,))
INFARCTION = Concept(
    text="myocardial infarction", codes=(Code(system="SNOMED", code="22298006"),)
)

SOURCE = (
    "Inclusion Criteria:\n"
    "- Serum creatinine <= 1.5 mg/dL within 6 months\n"
    "- Age 18 years or older\n"
    "Exclusion Criteria:\n"
    "- Myocardial infarction within 6 months\n"
)

CREAT = Criterion(
    id="INC-01",
    kind="inclusion",
    source_quote="Serum creatinine <= 1.5 mg/dL within 6 months",
    predicate=ObservationPredicate(
        concept=CREATININE_CONCEPT,
        op="<=",
        value=1.5,
        unit="mg/dL",
        window=TemporalWindow(relation="within", amount=6, unit="months"),
    ),
)
AGE = Criterion(
    id="INC-02",
    kind="inclusion",
    source_quote="Age 18 years or older",
    predicate=DemographicPredicate(field="age", op=">=", value=18, unit="years"),
)
INFARCT = Criterion(
    id="EXC-01",
    kind="exclusion",
    source_quote="Myocardial infarction within 6 months",
    predicate=PresencePredicate(
        type="condition",
        concept=INFARCTION,
        presence="present",
        window=TemporalWindow(relation="within", amount=6, unit="months"),
    ),
)

CRITERIA = CriteriaSet(nct_id="NCT04000000", source_text=SOURCE, criteria=[CREAT, AGE, INFARCT])

CREATININE_ROW = Evidence(
    kind="observation",
    resource_type="Observation",
    resource_id="obs-creat",
    display="Creatinine",
    fhir_path="Bundle.entry[3].resource",
    codes=(CREATININE,),
    value=1.2,
    unit="mg/dL",
    date=date(2026, 5, 14),
)

CREAT_MET = CriterionResult(
    criterion_id="INC-01",
    kind="inclusion",
    verdict=Verdict.MET,
    rationale="1.2 mg/dL on 2026-05-14 against <= 1.5 mg/dL",
    evidence=(CREATININE_ROW,),
)
CREAT_UNRESOLVED = CriterionResult(
    criterion_id="INC-01",
    kind="inclusion",
    verdict=Verdict.UNKNOWN,
    rationale="no serum creatinine result is on file for the required window",
    resolution_hint=ResolutionHint(
        missing="a serum creatinine result",
        where_to_look="the laboratory result system or the most recent panel in the chart",
        fhir_query="Observation?patient=P-001&code=2160-0&date=ge2025-12-01",
        blocks_criterion_id="INC-01",
    ),
)
AGE_MET = CriterionResult(
    criterion_id="INC-02",
    kind="inclusion",
    verdict=Verdict.MET,
    rationale="age 67 years at screening against >= 18",
)
INFARCT_ABSENT = CriterionResult(
    criterion_id="EXC-01",
    kind="exclusion",
    verdict=Verdict.NOT_MET,
    rationale="myocardial infarction is not documented in a window the chart covers",
)


def a_screening(
    *results: CriterionResult,
    decision: ScreeningOutcome = ScreeningOutcome.NEEDS_REVIEW,
) -> ScreeningResult:
    return ScreeningResult(
        nct_id="NCT04000000",
        patient_id="P-001",
        screened_on=SCREENING,
        decision=decision,
        criteria=results,
        deciding_criterion_ids=(),
        resolution_worklist=tuple(
            r.resolution_hint for r in results if r.resolution_hint is not None
        ),
        absence_policy=AbsencePolicy.COVERAGE_GATED,
    )


def draft(sentence: str) -> str:
    return json.dumps({"sentence": sentence})


def run(
    result: ScreeningResult,
    routes: dict[str, str],
    *,
    default: str | None = None,
) -> tuple[RationaleSet, list[str], AgentContext]:
    client, transport = a_routed_client(routes, default=default)
    ctx = AgentContext(client=client)
    written = write_rationales(result, CRITERIA, ctx)
    return written, transport.user_messages, ctx


CLEAN = "Creatinine was 1.2 mg/dL on 2026-05-14, inside the 1.5 mg/dL ceiling."
INVENTED = "Creatinine was 1.9 mg/dL on 2026-03-02, inside the ceiling."


class TestAcceptance:
    def test_a_clean_sentence_is_kept_as_the_model_wrote_it(self):
        written, messages, _ = run(a_screening(CREAT_MET), {"INC-01": draft(CLEAN)})

        assert len(messages) == 1
        rationale = written["INC-01"]
        assert rationale.sentence == CLEAN
        assert rationale.source == "model"
        assert rationale.violations == ()
        assert written.fallback_count == 0

    def test_the_request_carries_the_quote_the_evidence_and_the_verdict(self):
        request = rationale_request(CREAT, CREAT_MET)

        assert "Serum creatinine <= 1.5 mg/dL within 6 months" in request
        assert "1.2 mg/dL" in request
        assert "2026-05-14" in request
        assert "met" in request
        assert "1.2 mg/dL on 2026-05-14 against <= 1.5 mg/dL" in request

    def test_the_request_for_an_unresolved_criterion_says_what_is_missing(self):
        request = rationale_request(CREAT, CREAT_UNRESOLVED)

        assert "a serum creatinine result" in request
        assert "unresolved" in request
        # The FHIR query carries a date the sentence has no right to; the packet prints it, the
        # writer never sees it.
        assert "ge2025-12-01" not in request


class TestRetry:
    def test_an_invented_number_is_retried_and_the_retry_names_the_token(self):
        written, messages, _ = run(
            a_screening(CREAT_MET),
            {"was rejected": draft(CLEAN), "INC-01": draft(INVENTED)},
        )

        assert len(messages) == 2
        retry = messages[1]
        assert "1.9" in retry
        assert "2026-03-02" in retry
        assert INVENTED in retry

        rationale = written["INC-01"]
        assert rationale.sentence == CLEAN
        assert rationale.source == "model"
        # The rejection stays on the record even though the second attempt was accepted.
        assert {v.token for v in rationale.violations} == {"1.9", "2026-03-02"}


class TestFallback:
    def test_a_second_failure_falls_back_to_the_evaluator(self):
        written, messages, _ = run(a_screening(CREAT_MET), {"INC-01": draft(INVENTED)})

        assert len(messages) == 2
        rationale = written["INC-01"]
        assert rationale.sentence == CREAT_MET.rationale
        assert rationale.source == "fallback"
        assert rationale.fallback_reason is not None
        assert len(rationale.violations) == 4  # two tokens, twice
        assert written.fallback_count == 1
        assert written.fallback_rate == 1.0

    def test_the_fallback_sentence_passes_the_linter_it_was_chosen_by(self):
        # By construction: every number in the evaluator's rationale is one the criterion resolved
        # from. The fallback is only safe because of that, so it is asserted rather than assumed.
        for criterion, result in (
            (CREAT, CREAT_MET),
            (CREAT, CREAT_UNRESOLVED),
            (AGE, AGE_MET),
            (INFARCT, INFARCT_ABSENT),
        ):
            invented = draft("Creatinine was 9.9 mg/dL on 1999-01-01.")
            written, _, _ = run(a_screening(result), {criterion.id: invented})
            rationale = written[result.criterion_id]
            assert rationale.source == "fallback"
            assert check_rationale(rationale.sentence, criterion, result) == []

    def test_a_provider_that_never_answers_falls_back_without_pretending_otherwise(self):
        written, _, _ = run(a_screening(CREAT_MET), {"INC-01": "not json at all"})

        rationale = written["INC-01"]
        assert rationale.sentence == CREAT_MET.rationale
        assert rationale.source == "fallback"
        assert rationale.violations == ()
        assert "no valid" in rationale.fallback_reason


class TestUnresolvedCriteria:
    def test_an_unresolved_criterion_still_gets_a_sentence(self):
        abstention = "No serum creatinine result is on file for the required window."
        written, _, _ = run(a_screening(CREAT_UNRESOLVED), {"INC-01": draft(abstention)})

        rationale = written["INC-01"]
        assert rationale.sentence == abstention
        assert rationale.source == "model"

    def test_a_sentence_that_asserts_a_value_the_chart_lacks_is_refused(self):
        written, _, _ = run(
            a_screening(CREAT_UNRESOLVED),
            {"INC-01": draft("Creatinine was 1.2 mg/dL and is within the limit.")},
        )

        rationale = written["INC-01"]
        assert rationale.source == "fallback"
        assert not any(character.isdigit() for character in rationale.sentence)


class TestTrajectory:
    def test_one_trajectory_step_per_criterion(self):
        result = a_screening(CREAT_MET, AGE_MET, INFARCT_ABSENT)
        written, _, ctx = run(
            result,
            {
                "INC-01": draft(CLEAN),
                "INC-02": draft("The patient was 67 years old at screening."),
                "EXC-01": draft("No myocardial infarction is documented in the covered window."),
            },
        )

        checks = [step for step in ctx.trajectory.steps if step.tier == PROSE_CHECK_TIER]
        assert [step.parsed["criterion_id"] for step in checks] == ["INC-01", "INC-02", "EXC-01"]
        assert len(written) == 3

    def test_the_step_records_the_rejection_that_forced_a_fallback(self):
        _, _, ctx = run(a_screening(CREAT_MET), {"INC-01": draft(INVENTED)})

        step = next(s for s in ctx.trajectory.steps if s.tier == PROSE_CHECK_TIER)
        assert step.parsed["source"] == "fallback"
        assert step.parsed["rejected"] == [INVENTED, INVENTED]
        assert {v["token"] for v in step.parsed["violations"]} == {"1.9", "2026-03-02"}


class TestDeterministicRationales:
    def test_the_packet_can_be_built_without_a_model_at_all(self):
        written = deterministic_rationales(a_screening(CREAT_MET, AGE_MET))

        assert [r.criterion_id for r in written] == ["INC-01", "INC-02"]
        assert all(isinstance(r, Rationale) and r.source == "fallback" for r in written)
        assert written["INC-02"].sentence == AGE_MET.rationale


# ------------------------------------------------------------------------------------------------
# The floor the packet degrades to.
#
# `_fallback` prints the evaluator's own rationale, and the packet has no other safety net: if that
# sentence can fail the linter, a fallback ships an unverifiable claim about a patient wearing the
# appearance of having been checked. The invariant is supposed to hold by construction, so it is
# asserted against what the evaluator actually produces rather than against prose written here.
# ------------------------------------------------------------------------------------------------

HAEMOGLOBIN = Code(system="LOINC", code="718-7", display="Haemoglobin")
SPECIFIC_GRAVITY = Code(system="LOINC", code="5811-5", display="Specific gravity")
HAEMOGLOBIN_CONCEPT = Concept(text="haemoglobin", codes=(HAEMOGLOBIN,))
GRAVITY_CONCEPT = Concept(text="specific gravity", codes=(SPECIFIC_GRAVITY,))
DIABETES = Concept(text="type 2 diabetes", codes=(Code(system="SNOMED", code="44054006"),))

FULL_CHART = PatientIndex(
    patient_id="P-FULL",
    birth_date=date(1959, 3, 2),
    sex="female",
    evidence=[
        Evidence(
            kind="encounter",
            resource_type="Encounter",
            resource_id="enc-1",
            display="Office visit",
            fhir_path="Bundle.entry[1].resource",
            date=date(2026, 5, 14),
        ),
        CREATININE_ROW,
        Evidence(  # a result with no number attached to it
            kind="observation",
            resource_type="Observation",
            resource_id="obs-sg",
            display="Specific gravity",
            fhir_path="Bundle.entry[5].resource",
            codes=(SPECIFIC_GRAVITY,),
            date=date(2026, 5, 14),
        ),
        Evidence(  # a result in a unit nothing can honestly convert to mg/dL
            kind="observation",
            resource_type="Observation",
            resource_id="obs-hb",
            display="Haemoglobin",
            fhir_path="Bundle.entry[6].resource",
            codes=(HAEMOGLOBIN,),
            value=11.4,
            unit="%",
            date=date(2026, 5, 14),
        ),
        Evidence(
            kind="condition",
            resource_type="Condition",
            resource_id="cond-mi",
            display="Acute myocardial infarction",
            fhir_path="Bundle.entry[9].resource",
            codes=(Code(system="SNOMED", code="22298006"),),
            date=date(2026, 2, 1),
        ),
    ],
)

EMPTY_CHART = PatientIndex(patient_id="P-EMPTY", birth_date=None, sex=None, evidence=[])


def an_observation(
    identifier: str, concept: Concept, op: str, value: float, unit: str, **extra: object
) -> Criterion:
    return Criterion(
        id=identifier,
        kind="inclusion",
        source_quote=f"{concept.text} {op} {value} {unit}",
        predicate=ObservationPredicate(concept=concept, op=op, value=value, unit=unit, **extra),
    )


CREAT_LOW = an_observation("O-01", CREATININE_CONCEPT, "<=", 1.5, "mg/dL")
CREAT_STRICT = an_observation("O-02", CREATININE_CONCEPT, "<=", 1.0, "mg/dL")
CREAT_RANGE = an_observation(
    "O-03", CREATININE_CONCEPT, "between", 1.0, "mg/dL", value_high=2.0
)
GRAVITY = an_observation("O-04", GRAVITY_CONCEPT, ">", 1.0, "1")
UNCONVERTIBLE = an_observation("O-05", HAEMOGLOBIN_CONCEPT, ">=", 9.0, "mg/dL")
WINDOWED = an_observation(
    "O-06",
    CREATININE_CONCEPT,
    "<=",
    1.5,
    "mg/dL",
    window=TemporalWindow(relation="within", amount=6, unit="months"),
)

MATRIX = [
    CREAT_LOW,
    CREAT_STRICT,
    CREAT_RANGE,
    GRAVITY,
    UNCONVERTIBLE,
    WINDOWED,
    INFARCT,
    Criterion(
        id="P-02",
        kind="inclusion",
        source_quote="No history of myocardial infarction",
        predicate=PresencePredicate(type="condition", concept=INFARCTION, presence="absent"),
    ),
    Criterion(
        id="P-03",
        kind="exclusion",
        source_quote="Type 2 diabetes",
        predicate=PresencePredicate(type="condition", concept=DIABETES, presence="present"),
    ),
    AGE,
    Criterion(
        id="D-02",
        kind="inclusion",
        source_quote="Age 90 years or older",
        predicate=DemographicPredicate(field="age", op=">=", value=90, unit="years"),
    ),
    Criterion(
        id="D-03",
        kind="inclusion",
        source_quote="Female",
        predicate=DemographicPredicate(field="sex", op="==", value="female"),
    ),
    Criterion(
        id="D-04",
        kind="exclusion",
        source_quote="Male",
        predicate=DemographicPredicate(field="sex", op="==", value="male"),
    ),
    Criterion(
        id="U-01",
        kind="exclusion",
        source_quote="Unsuitable in the opinion of the investigator",
        predicate=UnsupportedPredicate(reason="requires investigator judgement"),
    ),
    Criterion(
        id="C-01",
        kind="inclusion",
        source_quote="Serum creatinine <= 1.5 mg/dL and age 18 years or older",
        predicate=CompositePredicate(type="all_of", operands=(CREAT_LOW.predicate, AGE.predicate)),
    ),
    Criterion(
        id="C-02",
        kind="inclusion",
        source_quote="Serum creatinine <= 1.0 mg/dL and age 18 years or older",
        predicate=CompositePredicate(
            type="all_of", operands=(CREAT_STRICT.predicate, AGE.predicate)
        ),
    ),
    Criterion(
        id="C-03",
        kind="inclusion",
        source_quote="Haemoglobin >= 9 mg/dL or serum creatinine <= 1.5 mg/dL",
        predicate=CompositePredicate(
            type="any_of", operands=(UNCONVERTIBLE.predicate, CREAT_LOW.predicate)
        ),
    ),
    Criterion(
        id="C-04",
        kind="inclusion",
        source_quote="Specific gravity > 1 and age 18 years or older",
        predicate=CompositePredicate(type="all_of", operands=(GRAVITY.predicate, AGE.predicate)),
    ),
    Criterion(
        id="C-05",
        kind="exclusion",
        source_quote="Not serum creatinine <= 1.5 mg/dL",
        predicate=CompositePredicate(type="not", operands=(CREAT_LOW.predicate,)),
    ),
]


class TestTheFallbackFloor:
    def test_every_rationale_the_evaluator_writes_passes_the_linter(self):
        seen = set()
        for criterion in MATRIX:
            for chart in (FULL_CHART, EMPTY_CHART):
                result = evaluate_criterion(criterion, chart, SCREENING)
                seen.add(result.verdict)
                violations = check_rationale(result.rationale, criterion, result)
                assert violations == [], (
                    f"{criterion.id} on {chart.patient_id} would ship an unverifiable fallback: "
                    f"{result.rationale!r} names {[v.token for v in violations]}"
                )

        # Guard against the matrix quietly collapsing onto one branch.
        assert seen == {Verdict.MET, Verdict.NOT_MET, Verdict.UNKNOWN}


class TestBlockedScreening:
    def test_a_screening_stopped_before_the_protocol_asks_the_model_nothing(self):
        blocked = ScreeningResult(
            nct_id="NCT04000000",
            patient_id="P-004",
            screened_on=SCREENING,
            decision=ScreeningOutcome.INELIGIBLE,
            criteria=(),
            deciding_criterion_ids=(),
            resolution_worklist=(),
            absence_policy=AbsencePolicy.COVERAGE_GATED,
            blocked_by="the chart records that the patient died on 2026-05-03",
        )
        client, transport = a_routed_client({}, default=draft("unreachable"))
        ctx = AgentContext(client=client)

        written = write_rationales(blocked, CRITERIA, ctx)

        assert len(written) == 0
        assert transport.requests == []
        assert ctx.trajectory.steps == []
