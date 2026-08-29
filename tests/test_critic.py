"""The critic: round-trip verification of a compiled criterion, and a coverage audit.

Two halves, tested differently. `render_predicate` and `coverage_report` are deterministic, so
they are asserted on directly. `review` talks to a model, so it runs against a fake transport that
answers from a queue — the same pattern `tests/test_llm.py` uses, kept local so that a change to
the client's own fixtures cannot quietly change what the critic is tested against.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from caliper.agents import AgentContext
from caliper.agents.critic import (
    AGENT_NAME,
    BackTranslation,
    CriticReport,
    apply_findings,
    back_translate,
    coverage_report,
    critic_prompt,
    render_predicate,
    review,
)
from caliper.criteria_text import segment
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
from caliper.llm import LLMClient, ProviderProfile, StructuredOutput

# ------------------------------------------------------------------------------------------------
# A fake transport, and the smallest context that will drive the client through it.
# ------------------------------------------------------------------------------------------------


class FakeTransport:
    """The slice of `openai.OpenAI` the client uses, answering from a queue of canned replies."""

    def __init__(self, replies: list[str]):
        self.replies = list(replies)
        self.requests: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs: object) -> SimpleNamespace:
        self.requests.append(kwargs)
        if not self.replies:
            raise AssertionError("the critic asked for more turns than the test provided")
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.replies.pop(0)))],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
        )


def a_verdict(severity: str, reason: str = "the two sentences differ", **overrides: object) -> str:
    payload = {
        "agrees": severity == "equivalent",
        "severity": severity,
        "reason": reason,
        **overrides,
    }
    return json.dumps(payload)


def a_context(replies: list[str]) -> tuple[AgentContext, FakeTransport]:
    profile = ProviderProfile(
        provider="venice",
        model="test-model",
        base_url="https://example.invalid/v1",
        api_key_env="TEST_API_KEY",
        structured_output=StructuredOutput.JSON_SCHEMA,
        input_usd_per_mtok=1.0,
        output_usd_per_mtok=2.0,
    )
    transport = FakeTransport(replies)
    return AgentContext(client=LLMClient(profile, transport=transport)), transport


# ------------------------------------------------------------------------------------------------
# Predicates, one of every shape.
# ------------------------------------------------------------------------------------------------

CREATININE = ObservationPredicate(
    concept=Concept(
        text="serum creatinine",
        codes=(Code(system="LOINC", code="2160-0", display="Creatinine [Mass/volume] in Serum"),),
    ),
    op="<=",
    value=1.5,
    unit="mg/dL",
    window=TemporalWindow(relation="within", amount=6, unit="months"),
)

FEV1_RANGE = ObservationPredicate(
    concept=Concept(text="FEV1 percent predicted"),
    op="between",
    value=30,
    value_high=70,
    unit="%",
)

DIABETES = PresencePredicate(
    type="condition",
    concept=Concept(text="type 2 diabetes mellitus"),
    presence="present",
    window=TemporalWindow(relation="ever"),
)

NO_INSULIN = PresencePredicate(
    type="medication",
    concept=Concept(text="insulin"),
    presence="absent",
    window=TemporalWindow(relation="within", amount=1, unit="months"),
)

BYPASS = PresencePredicate(
    type="procedure",
    concept=Concept(text="coronary artery bypass graft"),
    presence="present",
    window=TemporalWindow(relation="before", amount=3, unit="years"),
)

ADULT = DemographicPredicate(field="age", op=">=", value=18, unit="years")
FEMALE = DemographicPredicate(field="sex", op="==", value="female")
NOT_MALE = DemographicPredicate(field="sex", op="!=", value="male")
UNSUPPORTED = UnsupportedPredicate(reason="requires the investigator's clinical judgement")

NESTED = CompositePredicate(
    type="all_of",
    operands=(
        ADULT,
        CompositePredicate(
            type="any_of",
            operands=(
                DIABETES,
                PresencePredicate(
                    type="condition", concept=Concept(text="prediabetes"), presence="present"
                ),
            ),
        ),
    ),
)

NOT_PREGNANT = CompositePredicate(
    type="not",
    operands=(
        PresencePredicate(type="condition", concept=Concept(text="pregnancy"), presence="present"),
    ),
)

EVERY_PREDICATE = (
    CREATININE,
    FEV1_RANGE,
    DIABETES,
    NO_INSULIN,
    BYPASS,
    ADULT,
    FEMALE,
    NOT_MALE,
    UNSUPPORTED,
    NESTED,
    NOT_PREGNANT,
)


# ------------------------------------------------------------------------------------------------
# A protocol, and criteria compiled from it.
# ------------------------------------------------------------------------------------------------

PROTOCOL = (
    "Inclusion Criteria\n\n"
    "1. Age 40 to 85 years at screening.\n"
    "2. Moderate to severe COPD.\n"
    "   1. Post-bronchodilator FEV1/FVC ratio <0.70.\n"
    "   2. FEV1 between 30% and 70% predicted.\n\n"
    "Exclusion Criteria\n\n"
    "1. Current smoker.\n"
)

AGE_BAND = Criterion(
    id="INC-01",
    kind="inclusion",
    source_quote="Age 40 to 85 years at screening.",
    predicate=CompositePredicate(
        type="all_of",
        operands=(
            DemographicPredicate(field="age", op=">=", value=40, unit="years"),
            DemographicPredicate(field="age", op="<=", value=85, unit="years"),
        ),
    ),
)

COPD = Criterion(
    id="INC-02",
    kind="inclusion",
    source_quote="Moderate to severe COPD.",
    predicate=PresencePredicate(
        type="condition",
        concept=Concept(text="moderate to severe COPD"),
        presence="present",
        window=TemporalWindow(relation="ever"),
    ),
)

SMOKER = Criterion(
    id="EXC-01",
    kind="exclusion",
    source_quote="Current smoker.",
    predicate=PresencePredicate(
        type="condition",
        concept=Concept(text="current tobacco smoking"),
        presence="present",
        window=TemporalWindow(relation="current"),
    ),
)

JUDGEMENT = Criterion(
    id="EXC-02",
    kind="exclusion",
    source_quote="Current smoker.",
    predicate=UNSUPPORTED,
)


def a_criteria_set(*criteria: Criterion, source_text: str = PROTOCOL) -> CriteriaSet:
    return CriteriaSet(nct_id="NCT00000001", source_text=source_text, criteria=list(criteria))


# ------------------------------------------------------------------------------------------------


class TestRenderPredicate:
    def test_every_predicate_type_renders_into_a_plain_english_phrase(self):
        for predicate in EVERY_PREDICATE:
            rendered = render_predicate(predicate)
            assert rendered.strip() == rendered
            assert len(rendered.split()) >= 3, f"{predicate.type} rendered too thinly: {rendered}"

    def test_the_rendering_never_leaks_the_json_the_model_must_not_see(self):
        """The whole point of rendering in code: the model compares prose, not a data structure."""
        for predicate in EVERY_PREDICATE:
            rendered = render_predicate(predicate)
            for token in ('"', "{", "}", "[", "]", "_of", "None", "null"):
                assert token not in rendered, f"{token!r} leaked into {rendered!r}"

    def test_an_observation_names_its_concept_its_bound_and_its_unit(self):
        rendered = render_predicate(CREATININE)
        assert "serum creatinine" in rendered
        assert "at most 1.5 mg/dL" in rendered

    def test_a_temporal_window_renders_with_its_span_and_its_anchor(self):
        rendered = render_predicate(CREATININE)
        assert "6 months" in rendered
        assert "screening" in rendered

    def test_a_single_unit_window_is_not_pluralised(self):
        assert "1 month before screening" in render_predicate(NO_INSULIN)

    def test_a_before_window_reads_as_older_than_its_span(self):
        assert "more than 3 years before screening" in render_predicate(BYPASS)

    def test_an_open_window_says_it_is_open(self):
        assert "at any time" in render_predicate(DIABETES)

    def test_a_range_names_both_bounds_and_says_whether_they_are_included(self):
        rendered = render_predicate(FEV1_RANGE)
        assert "between 30 and 70%" in rendered
        assert "inclusive" in rendered

    def test_a_whole_number_loses_its_decimal_point(self):
        assert "at least 18 years" in render_predicate(ADULT)

    def test_presence_and_absence_do_not_render_the_same_way(self):
        assert render_predicate(DIABETES).startswith("a documented diagnosis of")
        assert render_predicate(NO_INSULIN).startswith("no documented prescription for")

    def test_sex_renders_as_an_identity_and_its_negation(self):
        assert render_predicate(FEMALE) == "sex is female"
        assert render_predicate(NOT_MALE) == "sex is not male"

    def test_an_all_of_renders_with_and(self):
        rendered = render_predicate(
            CompositePredicate(type="all_of", operands=(ADULT, FEMALE)),
        )
        assert rendered == "age at least 18 years and sex is female"

    def test_an_any_of_renders_with_or(self):
        rendered = render_predicate(
            CompositePredicate(type="any_of", operands=(ADULT, FEMALE)),
        )
        assert rendered == "age at least 18 years or sex is female"

    def test_a_not_renders_as_a_negation(self):
        rendered = render_predicate(NOT_PREGNANT)
        assert rendered.startswith("not (")
        assert "pregnancy" in rendered

    def test_a_nested_composite_is_grouped_so_the_scope_is_unambiguous(self):
        rendered = render_predicate(NESTED)
        assert " and (" in rendered
        assert " or " in rendered
        assert rendered.endswith(")")

    def test_an_operand_carrying_a_comma_is_grouped_too(self):
        rendered = render_predicate(
            CompositePredicate(type="all_of", operands=(CREATININE, ADULT)),
        )
        assert rendered.startswith("(serum creatinine")
        assert rendered.endswith(") and age at least 18 years")

    def test_an_unsupported_predicate_says_it_was_never_formalised(self):
        rendered = render_predicate(UNSUPPORTED)
        assert "not formalised" in rendered
        assert "clinical judgement" in rendered

    def test_rendering_is_deterministic(self):
        assert [render_predicate(p) for p in EVERY_PREDICATE] == [
            render_predicate(p) for p in EVERY_PREDICATE
        ]


# ------------------------------------------------------------------------------------------------


class TestPrompt:
    def test_the_prompt_ships_with_the_package(self):
        assert len(critic_prompt()) > 500

    def test_the_prompt_names_every_verdict_the_schema_allows(self):
        prompt = critic_prompt()
        for severity in ("equivalent", "narrower", "broader", "contradicts"):
            assert severity in prompt

    def test_the_prompt_warns_against_agreeing_for_the_sake_of_it(self):
        assert "agree" in critic_prompt().lower()

    def test_the_prompt_is_plain_ascii_engineering_prose(self):
        prompt = critic_prompt()
        assert prompt.isascii()
        assert "helpful assistant" not in prompt.lower()


# ------------------------------------------------------------------------------------------------


class TestBackTranslation:
    def test_the_model_is_shown_the_quote_and_the_rendering_and_nothing_else(self):
        ctx, transport = a_context([a_verdict("equivalent", "same bound, same window")])
        finding = back_translate(COPD, ctx)

        user = transport.requests[0]["messages"][1]["content"]
        assert COPD.source_quote in user
        assert render_predicate(COPD.predicate) in user
        # The claim the whole design rests on: no JSON reaches the comparison.
        assert "{" not in user and "}" not in user
        assert finding.quote == COPD.source_quote
        assert finding.rendered == render_predicate(COPD.predicate)

    def test_the_call_is_attributed_to_the_critic(self):
        ctx, _ = a_context([a_verdict("equivalent")])
        back_translate(COPD, ctx)
        assert ctx.trajectory.steps[0].agent == AGENT_NAME

    def test_the_verdict_and_its_reason_survive_onto_the_finding(self):
        ctx, _ = a_context([a_verdict("broader", "the rendering drops the severity qualifier")])
        finding = back_translate(COPD, ctx)
        assert finding.severity == "broader"
        assert finding.reason == "the rendering drops the severity qualifier"
        assert finding.is_downgrade

    def test_an_equivalent_verdict_is_not_a_downgrade(self):
        ctx, _ = a_context([a_verdict("equivalent", "identical meaning")])
        assert not back_translate(COPD, ctx).is_downgrade

    def test_a_verdict_that_agrees_with_a_non_equivalent_label_is_still_a_downgrade(self):
        ctx, _ = a_context([a_verdict("narrower", "tighter than the protocol", agrees=True)])
        finding = back_translate(COPD, ctx)
        assert finding.severity == "narrower"
        assert finding.is_downgrade

    def test_a_disagreement_labelled_equivalent_fails_closed(self):
        """A response at war with itself is not an agreement, whatever its label says."""
        ctx, _ = a_context([a_verdict("equivalent", "actually the window is wrong", agrees=False)])
        finding = back_translate(COPD, ctx)
        assert finding.severity == "contradicts"
        assert finding.is_downgrade


# ------------------------------------------------------------------------------------------------


class TestReview:
    def test_one_finding_and_one_trajectory_step_per_criterion_reviewed(self):
        ctx, transport = a_context([a_verdict("equivalent"), a_verdict("equivalent")])
        report = review(a_criteria_set(AGE_BAND, COPD), ctx)

        assert len(report.findings) == 2
        assert len(ctx.trajectory.steps) == 2
        assert len(transport.requests) == 2
        assert [f.criterion_id for f in report.findings] == ["INC-01", "INC-02"]

    def test_an_unsupported_criterion_is_never_sent_to_the_model(self):
        """There is no compiled meaning to verify, and a model asked anyway will invent one."""
        ctx, transport = a_context([a_verdict("equivalent")])
        report = review(a_criteria_set(COPD, JUDGEMENT), ctx)

        assert len(transport.requests) == 1
        assert [f.criterion_id for f in report.findings] == ["INC-02"]

    def test_the_trajectory_records_what_was_compared_and_what_came_back(self):
        ctx, _ = a_context([a_verdict("narrower", "the window shrank to 30 days")])
        review(a_criteria_set(COPD), ctx)

        step = ctx.trajectory.steps[0]
        assert COPD.source_quote in step.user_prompt
        assert render_predicate(COPD.predicate) in step.user_prompt
        assert step.parsed["severity"] == "narrower"
        assert step.parsed["reason"] == "the window shrank to 30 days"

    def test_the_report_carries_the_coverage_audit_as_well(self):
        ctx, _ = a_context([a_verdict("equivalent"), a_verdict("equivalent")])
        report = review(a_criteria_set(AGE_BAND, COPD), ctx)

        assert report.coverage == pytest.approx(0.8)
        assert [s.text for s in report.unclaimed_spans] == ["Current smoker."]
        assert report.quote_problems == ()


# ------------------------------------------------------------------------------------------------


class TestApplyFindings:
    def _downgraded(self, severity: str, reason: str = "the bound moved") -> CriteriaSet:
        ctx, _ = a_context([a_verdict("equivalent"), a_verdict(severity, reason)])
        criteria_set = a_criteria_set(AGE_BAND, COPD)
        return apply_findings(criteria_set, review(criteria_set, ctx))

    def test_a_criterion_the_model_calls_equivalent_is_left_alone(self):
        applied = self._downgraded("narrower")
        assert applied.criteria[0] == AGE_BAND

    def test_a_narrower_criterion_is_downgraded_and_keeps_the_reason(self):
        applied = self._downgraded("narrower", "only counts diagnoses in the last year")
        predicate = applied.criteria[1].predicate
        assert isinstance(predicate, UnsupportedPredicate)
        assert "narrower" in predicate.reason
        assert "only counts diagnoses in the last year" in predicate.reason

    def test_a_broader_criterion_is_downgraded(self):
        assert self._downgraded("broader").criteria[1].predicate.type == "unsupported"

    def test_a_contradicting_criterion_is_downgraded(self):
        assert self._downgraded("contradicts").criteria[1].predicate.type == "unsupported"

    def test_downgrading_preserves_the_id_the_kind_and_the_source_quote(self):
        downgraded = self._downgraded("contradicts").criteria[1]
        assert downgraded.id == COPD.id
        assert downgraded.kind == COPD.kind
        assert downgraded.source_quote == COPD.source_quote

    def test_the_original_criteria_set_is_not_mutated(self):
        ctx, _ = a_context([a_verdict("equivalent"), a_verdict("contradicts")])
        criteria_set = a_criteria_set(AGE_BAND, COPD)
        applied = apply_findings(criteria_set, review(criteria_set, ctx))

        assert criteria_set.criteria[1].predicate.type == "condition"
        assert applied.criteria[1].predicate.type == "unsupported"
        assert applied.nct_id == criteria_set.nct_id
        assert applied.source_text_sha256 == criteria_set.source_text_sha256

    def test_a_clean_review_changes_nothing(self):
        ctx, _ = a_context([a_verdict("equivalent"), a_verdict("equivalent")])
        criteria_set = a_criteria_set(AGE_BAND, COPD)
        applied = apply_findings(criteria_set, review(criteria_set, ctx))
        assert applied.criteria == criteria_set.criteria

    def test_a_criterion_that_was_already_unsupported_stays_untouched(self):
        ctx, _ = a_context([a_verdict("equivalent")])
        criteria_set = a_criteria_set(COPD, JUDGEMENT)
        applied = apply_findings(criteria_set, review(criteria_set, ctx))
        assert applied.criteria[1] == JUDGEMENT


# ------------------------------------------------------------------------------------------------


class TestCoverageReport:
    def test_a_criteria_set_claiming_every_span_reports_full_coverage(self):
        coverage = coverage_report(a_criteria_set(AGE_BAND, COPD, SMOKER))
        assert coverage.coverage == 1.0
        assert coverage.unclaimed_spans == ()
        assert coverage.unclaimed_span_indices == ()
        assert coverage.total_spans == len(segment(PROTOCOL))

    def test_a_dropped_bullet_shows_up_as_an_unclaimed_span_with_its_text(self):
        coverage = coverage_report(a_criteria_set(AGE_BAND, COPD))
        assert coverage.unclaimed_span_indices == (4,)
        assert coverage.unclaimed_span_texts == ("Current smoker.",)
        assert coverage.coverage == pytest.approx(0.8)

    def test_a_criterion_claiming_a_parent_span_also_claims_that_spans_children(self):
        coverage = coverage_report(a_criteria_set(COPD))
        assert coverage.claimed_span_indices == (1, 2, 3)
        assert coverage.unclaimed_span_indices == (0, 4)

    def test_a_quote_spanning_a_parent_and_its_children_claims_all_three(self):
        quoted = Criterion(
            id="INC-02",
            kind="inclusion",
            source_quote=(
                "Moderate to severe COPD.\n"
                "   1. Post-bronchodilator FEV1/FVC ratio <0.70.\n"
                "   2. FEV1 between 30% and 70% predicted."
            ),
            predicate=FEV1_RANGE,
        )
        assert coverage_report(a_criteria_set(quoted)).claimed_span_indices == (1, 2, 3)

    def test_claiming_forgives_whitespace_and_case_but_not_wording(self):
        loose = Criterion(
            id="EXC-01",
            kind="exclusion",
            source_quote="  CURRENT   smoker.  ",
            predicate=SMOKER.predicate,
        )
        assert coverage_report(a_criteria_set(loose)).claimed_span_indices == (4,)

    def test_a_paraphrased_quote_is_reported_as_a_quote_problem(self):
        paraphrased = Criterion(
            id="INC-01",
            kind="inclusion",
            source_quote="Patients aged forty to eighty-five years.",
            predicate=AGE_BAND.predicate,
        )
        coverage = coverage_report(a_criteria_set(paraphrased))
        assert [p.criterion_id for p in coverage.quote_problems] == ["INC-01"]
        assert coverage.unclaimed_span_indices == (0, 1, 2, 3, 4)

    def test_an_empty_criteria_set_claims_nothing(self):
        coverage = coverage_report(a_criteria_set())
        assert coverage.coverage == 0.0
        assert len(coverage.unclaimed_spans) == 5

    def test_a_protocol_with_no_spans_is_vacuously_covered(self):
        assert coverage_report(a_criteria_set(source_text="   \n\n")).coverage == 1.0

    def test_the_report_is_written_for_a_person_to_read(self):
        markdown = coverage_report(a_criteria_set(AGE_BAND, COPD)).to_markdown()
        assert "4 of 5" in markdown
        assert "Current smoker." in markdown
        assert "[4]" in markdown


# ------------------------------------------------------------------------------------------------


class TestCriticReportRendering:
    def test_the_report_lists_the_downgrades_it_would_apply(self):
        ctx, _ = a_context([a_verdict("equivalent"), a_verdict("narrower", "window too tight")])
        report = review(a_criteria_set(AGE_BAND, COPD), ctx)

        assert [f.criterion_id for f in report.downgrades] == ["INC-02"]

        markdown = report.to_markdown()
        assert "INC-02" in markdown
        assert "narrower" in markdown
        assert "window too tight" in markdown
        assert "Current smoker." in markdown

    def test_a_report_without_findings_still_renders(self):
        report = CriticReport.from_coverage((), coverage_report(a_criteria_set(AGE_BAND)))
        assert isinstance(report.to_markdown(), str)


# ------------------------------------------------------------------------------------------------


class TestResponseModel:
    def test_the_response_model_is_flat_enough_for_a_strict_schema(self):
        from caliper.llm import strict_schema_problems, to_strict_schema

        assert strict_schema_problems(to_strict_schema(BackTranslation)) == []

    def test_a_severity_outside_the_four_verdicts_is_rejected(self):
        with pytest.raises(ValueError):
            BackTranslation(agrees=False, severity="probably fine", reason="hmm")

    def test_a_blank_reason_is_rejected_because_a_human_has_to_read_it(self):
        with pytest.raises(ValueError):
            BackTranslation(agrees=True, severity="equivalent", reason="")
</content>
