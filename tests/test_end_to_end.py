"""The whole system, over real corpus data, with a stand-in for the provider.

Every other test exercises one layer against fixtures its author chose. This one runs a real
ClinicalTrials.gov protocol and a real Synthea chart through segmentation, compilation, terminology
resolution, criticism, evaluation and packet rendering, and asserts the properties that are supposed
to hold whatever the model says.

The provider is a stand-in, so nothing here is a result. What it establishes is that the pipeline
holds together on the data it will actually be asked about, which is exactly the class of problem
that only appears when the layers meet.
"""

import json
import re
from datetime import date

import pytest

from caliper import corpus
from caliper.agents.base import AgentContext
from caliper.logic import ScreeningOutcome, Verdict
from caliper.packet import build_packet, render_html, render_markdown
from caliper.pipeline import PipelineConfig, compile_trial, screen_patient

from fakes import a_programmable_client

pytestmark = pytest.mark.skipif(
    not (corpus.DATA_ROOT / "trials").is_dir(), reason="the corpus is not present"
)

TRIAL = "NCT03315143"
SCREENING = corpus.default_screening_date()

_CRITERION_BLOCK = re.compile(r"Criterion:\n(?P<text>.+?)(?:\n\n|$)", re.S)


def compiled_span_for(user: str) -> str:
    """Echo back the span we were actually given, so the quote check has something to pass on."""
    match = _CRITERION_BLOCK.search(user)
    quote = match.group("text").strip() if match else "unparsed"
    return json.dumps(
        {
            "is_criterion": True,
            "kind": "inclusion",
            "source_quote": quote,
            "predicate": {"type": "unsupported", "reason": "stand-in compiler"},
            "notes": None,
        }
    )


def paraphrasing_span_for(user: str) -> str:
    """A compiler that rewrites the protocol before formalising it."""
    return json.dumps(
        {
            "is_criterion": True,
            "kind": "inclusion",
            "source_quote": "a criterion nobody wrote",
            "predicate": {"type": "unsupported", "reason": "stand-in compiler"},
            "notes": None,
        }
    )


def responder(compile_with=compiled_span_for):
    def respond(system: str, user: str) -> str:
        if system.startswith("# Criteria compiler"):
            return compile_with(user)
        if system.startswith("# Concept resolution"):
            return json.dumps({"rationale": "stand-in", "candidates": []})
        if system.startswith("# Back-translation check"):
            return json.dumps({"agrees": True, "severity": "equivalent", "reason": "stand-in"})
        if system.startswith("# Rationale writing"):
            return json.dumps({"sentence": "No value is on file."})
        raise AssertionError(f"unexpected agent: {system.splitlines()[0]!r}")

    return respond


def a_context(compile_with=compiled_span_for):
    client, transport = a_programmable_client(responder(compile_with))
    return AgentContext(client=client), transport


MINIMAL = PipelineConfig(use_resolver=False, use_critic=False, write_rationales=False)


class TestARealProtocol:
    def test_it_compiles_into_criteria(self):
        trial = corpus.load_trial(TRIAL)
        ctx, _ = a_context()
        compiled = compile_trial(TRIAL, trial.criteria_text, ctx, MINIMAL)
        assert len(compiled.criteria_set.criteria) >= 6

    def test_the_sections_are_read_from_the_headings(self):
        """This protocol writes "Inclusion criteria :" with a space before the colon."""
        trial = corpus.load_trial(TRIAL)
        ctx, _ = a_context()
        compiled = compile_trial(TRIAL, trial.criteria_text, ctx, MINIMAL)
        kinds = {c.kind for c in compiled.criteria_set.criteria}
        assert kinds == {"inclusion", "exclusion"}

    def test_the_registry_boilerplate_is_not_compiled_as_a_criterion(self):
        trial = corpus.load_trial(TRIAL)
        ctx, _ = a_context()
        compiled = compile_trial(TRIAL, trial.criteria_text, ctx, MINIMAL)
        quotes = " ".join(c.source_quote for c in compiled.criteria_set.criteria)
        assert "not intended to contain all considerations" not in quotes

    def test_every_span_is_accounted_for(self):
        trial = corpus.load_trial(TRIAL)
        ctx, _ = a_context()
        compiled = compile_trial(TRIAL, trial.criteria_text, ctx, MINIMAL)
        assert compiled.compilation.spans_unaccounted == ()

    def test_every_quote_survives_the_fidelity_check(self):
        trial = corpus.load_trial(TRIAL)
        ctx, _ = a_context()
        compiled = compile_trial(TRIAL, trial.criteria_text, ctx, MINIMAL)
        assert compiled.compilation.downgraded == ()

    def test_a_paraphrasing_compiler_is_caught_on_real_text(self):
        trial = corpus.load_trial(TRIAL)
        ctx, _ = a_context(paraphrasing_span_for)
        compiled = compile_trial(TRIAL, trial.criteria_text, ctx, MINIMAL)
        assert len(compiled.compilation.downgraded) == len(compiled.criteria_set.criteria)

    def test_one_model_call_per_compilation_unit(self):
        trial = corpus.load_trial(TRIAL)
        ctx, transport = a_context()
        compiled = compile_trial(TRIAL, trial.criteria_text, ctx, MINIMAL)
        assert len(transport.requests) == len(compiled.compilation.units)


def living_patient_ids() -> list[str]:
    """Five of the twenty-four charts belong to patients who had died by the screening date."""
    return [
        pid
        for pid in corpus.patient_ids()
        if not corpus.load_patient(pid).died_before(SCREENING)
    ]


class TestARealPatient:
    def patient_id(self) -> str:
        return living_patient_ids()[0]

    def test_a_chart_screens_without_raising(self):
        trial = corpus.load_trial(TRIAL)
        patient = corpus.load_patient(self.patient_id())
        ctx, _ = a_context()
        compiled = compile_trial(TRIAL, trial.criteria_text, ctx, MINIMAL)
        screening = screen_patient(compiled, patient, SCREENING, ctx, MINIMAL)
        assert screening.result.decision in set(ScreeningOutcome)

    def test_a_protocol_nobody_could_formalise_never_screens_anyone_in(self):
        """Every criterion here is unsupported, so eligibility must be structurally unreachable."""
        trial = corpus.load_trial(TRIAL)
        ctx, _ = a_context()
        compiled = compile_trial(TRIAL, trial.criteria_text, ctx, MINIMAL)
        for patient_id in corpus.patient_ids()[:8]:
            patient = corpus.load_patient(patient_id)
            screening = screen_patient(compiled, patient, SCREENING, ctx, MINIMAL)
            assert screening.result.decision is not ScreeningOutcome.ELIGIBLE

    def test_every_unresolved_criterion_says_what_would_resolve_it(self):
        trial = corpus.load_trial(TRIAL)
        patient = corpus.load_patient(self.patient_id())
        ctx, _ = a_context()
        compiled = compile_trial(TRIAL, trial.criteria_text, ctx, MINIMAL)
        screening = screen_patient(compiled, patient, SCREENING, ctx, MINIMAL)
        unresolved = [c for c in screening.result.criteria if c.verdict is Verdict.UNKNOWN]
        assert unresolved
        assert all(c.resolution_hint is not None for c in unresolved)

    def test_a_patient_who_died_before_screening_stops_the_screening(self):
        """There is one such chart in the corpus, and it looks complete and current."""
        dead = [
            pid for pid in corpus.patient_ids() if corpus.load_patient(pid).died_before(SCREENING)
        ]
        assert dead, "the corpus is meant to contain deceased patients"
        trial = corpus.load_trial(TRIAL)
        ctx, _ = a_context()
        compiled = compile_trial(TRIAL, trial.criteria_text, ctx, MINIMAL)
        screening = screen_patient(compiled, corpus.load_patient(dead[0]), SCREENING, ctx, MINIMAL)
        assert screening.result.decision is ScreeningOutcome.INELIGIBLE
        assert screening.result.blocked_by is not None

    def test_no_criterion_is_decided_from_a_result_dated_after_screening(self):
        trial = corpus.load_trial(TRIAL)
        ctx, _ = a_context()
        compiled = compile_trial(TRIAL, trial.criteria_text, ctx, MINIMAL)
        for patient_id in corpus.patient_ids()[:6]:
            patient = corpus.load_patient(patient_id)
            screening = screen_patient(compiled, patient, SCREENING, ctx, MINIMAL)
            for criterion in screening.result.criteria:
                for evidence in criterion.evidence:
                    assert evidence.date is None or evidence.date <= SCREENING


class TestTheDocumentAtTheEnd:
    def test_a_packet_renders_from_a_real_screening(self):
        trial = corpus.load_trial(TRIAL)
        patient = corpus.load_patient(living_patient_ids()[0])
        ctx, _ = a_context()
        compiled = compile_trial(TRIAL, trial.criteria_text, ctx, MINIMAL)
        screening = screen_patient(compiled, patient, SCREENING, ctx, MINIMAL)
        packet = build_packet(
            screening.result,
            compiled.criteria_set,
            patient,
            screening.rationales,
            trial_title=trial.title,
        )
        html = render_html(packet)
        assert "http://" not in html and "https://" not in html
        assert trial.title[:30] in render_markdown(packet)

    def test_the_full_configuration_runs_over_real_data(self):
        trial = corpus.load_trial(TRIAL)
        patient = corpus.load_patient(living_patient_ids()[0])
        ctx, _ = a_context()
        config = PipelineConfig()
        compiled = compile_trial(TRIAL, trial.criteria_text, ctx, config)
        screening = screen_patient(compiled, patient, SCREENING, ctx, config)
        agents = {step.agent for step in ctx.trajectory.steps}
        assert "compiler" in agents
        assert screening.rationales is not None


class TestEveryTrialInTheCorpus:
    @pytest.mark.parametrize("nct_id", corpus.trial_ids() if corpus.DATA_ROOT.is_dir() else [])
    def test_it_segments_into_at_least_a_few_criteria(self, nct_id: str):
        """A protocol that segments to nothing would be silently screened against an empty set."""
        from caliper.criteria_text import segment, unescape_registry_markdown

        trial = corpus.load_trial(nct_id)
        spans = segment(unescape_registry_markdown(trial.criteria_text))
        assert len(spans) >= 4

    @pytest.mark.parametrize("nct_id", corpus.trial_ids() if corpus.DATA_ROOT.is_dir() else [])
    def test_both_sections_are_found(self, nct_id: str):
        from caliper.criteria_text import Section, segment, unescape_registry_markdown

        trial = corpus.load_trial(nct_id)
        spans = segment(unescape_registry_markdown(trial.criteria_text))
        assert {s.section for s in spans} >= {Section.INCLUSION, Section.EXCLUSION}


class TestScreeningDates:
    def test_the_screening_date_is_fixed_so_runs_are_comparable(self):
        assert corpus.default_screening_date() == date(2026, 6, 1)
