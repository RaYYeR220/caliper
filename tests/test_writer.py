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
from caliper.evaluate import AbsencePolicy, CriterionResult, ResolutionHint
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
from caliper.prose import check_rationale
from caliper.record import Evidence
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
