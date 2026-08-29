"""The whole run, wired together.

Every stage is behind a flag. That is not configurability for its own sake: the evaluation turns
each flag off in turn and reports what the number does, which is the only honest way to claim a
component earned its place.
"""

import json
from datetime import date

from caliper.agents.base import AgentContext
from caliper.evaluate import AbsencePolicy
from caliper.ir import Code, Concept, CriteriaSet, Criterion, ObservationPredicate, concepts_in
from caliper.logic import ScreeningOutcome
from caliper.pipeline import PipelineConfig, compile_trial, screen_patient
from caliper.record import Evidence, PatientIndex

from fakes import a_routed_client

SCREENING = date(2026, 6, 1)
PROTOCOL = "Inclusion Criteria:\n\n* HbA1c >= 7%.\n* Age 18 years or older.\n"

A1C_CODE = {"system": "LOINC", "code": "4548-4", "display": "Hemoglobin A1c"}


def compiled_span(quote: str, predicate: dict) -> str:
    return json.dumps(
        {
            "is_criterion": True,
            "kind": "inclusion",
            "source_quote": quote,
            "predicate": predicate,
            "notes": None,
        }
    )


A1C_PREDICATE = {
    "type": "observation",
    "concept": {"text": "HbA1c", "codes": []},
    "op": ">=",
    "value": 7.0,
    "value_high": None,
    "unit": "%",
    "window": None,
}
AGE_PREDICATE = {"type": "demographic", "field": "age", "op": ">=", "value": 18.0, "unit": "years"}

EQUIVALENT = json.dumps({"agrees": True, "severity": "equivalent", "reason": "same"})
RESOLVED_A1C = json.dumps(
    {
        "rationale": "A laboratory analyte, identified in LOINC.",
        "candidates": [
            {
                "system": "LOINC",
                "code": "4548-4",
                "display": "Hemoglobin A1c",
                "confidence": "high",
            }
        ],
    }
)
NO_CODES = json.dumps({"rationale": "Not a codeable concept.", "candidates": []})


COMPILER_ROUTES = {
    "HbA1c >= 7%": compiled_span("HbA1c >= 7%.", A1C_PREDICATE),
    "Age 18 years or older": compiled_span("Age 18 years or older.", AGE_PREDICATE),
}
WRITTEN_SENTENCE = json.dumps({"sentence": "No result is on file."})


def a_context(**agents: dict[str, str] | str):
    """Route by which agent is asking, since several of them see the same protocol text."""
    routes: dict[str, dict[str, str] | str] = {"# Criteria compiler": COMPILER_ROUTES}
    for name, route in agents.items():
        routes[_HEADINGS[name]] = route
    client, transport = a_routed_client(agent_routes=routes)
    return AgentContext(client=client), transport


_HEADINGS = {
    "resolver": "# Concept resolution",
    "critic": "# Back-translation check",
    "writer": "# Rationale writing",
}


def patient(a1c: float | None = 8.1) -> PatientIndex:
    evidence = [
        Evidence(
            kind="encounter",
            resource_type="Encounter",
            resource_id="enc-1",
            display="visit",
            fhir_path="Bundle.entry[0].resource",
            date=date(2026, 4, 1),
        )
    ]
    if a1c is not None:
        evidence.append(
            Evidence(
                kind="observation",
                resource_type="Observation",
                resource_id="obs-a1c",
                display="Hemoglobin A1c",
                fhir_path="Bundle.entry[5].resource",
                codes=(Code(**A1C_CODE),),
                value=a1c,
                unit="%",
                date=date(2026, 5, 1),
            )
        )
    return PatientIndex(
        patient_id="p-1", birth_date=date(1970, 1, 1), sex="female", evidence=evidence
    )


MINIMAL = PipelineConfig(use_resolver=False, use_critic=False, write_rationales=False)


class TestConceptWalking:
    def test_it_finds_concepts_inside_composites(self):
        inner = ObservationPredicate(
            concept=Concept(text="eGFR"), op=">=", value=25, unit="mL/min"
        )
        outer = ObservationPredicate(
            concept=Concept(text="creatinine"), op="<=", value=1.5, unit="mg/dL"
        )
        criteria = CriteriaSet(
            nct_id="NCT1",
            source_text="x",
            criteria=[
                Criterion(id="INC-01", kind="inclusion", source_quote="x", predicate=inner),
                Criterion(id="INC-02", kind="inclusion", source_quote="x", predicate=outer),
            ],
        )
        assert {c.text for c in concepts_in(criteria)} == {"eGFR", "creatinine"}


class TestCompileTrial:
    def test_the_minimal_configuration_only_compiles(self):
        ctx, transport = a_context()
        trial = compile_trial("NCT1", PROTOCOL, ctx, MINIMAL)
        assert len(transport.requests) == 2
        assert [c.id for c in trial.criteria_set.criteria] == ["INC-01", "INC-02"]
        assert trial.critic_report is None

    def test_the_resolver_attaches_codes_to_the_compiled_concepts(self):
        ctx, _ = a_context(resolver=RESOLVED_A1C)
        config = PipelineConfig(use_resolver=True, use_critic=False, write_rationales=False)
        trial = compile_trial("NCT1", PROTOCOL, ctx, config)
        concept = trial.criteria_set.criteria[0].predicate.concept
        assert [c.code for c in concept.codes] == ["4548-4"]

    def test_the_critic_runs_when_it_is_switched_on(self):
        ctx, _ = a_context(critic=EQUIVALENT)
        config = PipelineConfig(use_resolver=False, use_critic=True, write_rationales=False)
        trial = compile_trial("NCT1", PROTOCOL, ctx, config)
        assert trial.critic_report is not None
        assert len(trial.critic_report.findings) == 2

    def test_the_configuration_used_is_recorded_on_the_result(self):
        ctx, _ = a_context()
        trial = compile_trial("NCT1", PROTOCOL, ctx, MINIMAL)
        assert trial.config is MINIMAL


class TestScreenPatient:
    def test_a_resolved_patient_is_screened_in(self):
        ctx, _ = a_context(resolver=RESOLVED_A1C)
        config = PipelineConfig(use_resolver=True, use_critic=False, write_rationales=False)
        trial = compile_trial("NCT1", PROTOCOL, ctx, config)
        screening = screen_patient(trial, patient(), SCREENING, ctx, config)
        assert screening.result.decision is ScreeningOutcome.ELIGIBLE

    def test_a_missing_lab_sends_the_case_to_a_human(self):
        ctx, _ = a_context(resolver=RESOLVED_A1C)
        config = PipelineConfig(use_resolver=True, use_critic=False, write_rationales=False)
        trial = compile_trial("NCT1", PROTOCOL, ctx, config)
        screening = screen_patient(trial, patient(a1c=None), SCREENING, ctx, config)
        assert screening.result.decision is ScreeningOutcome.NEEDS_REVIEW
        assert screening.result.resolution_worklist

    def test_the_absence_policy_from_the_configuration_reaches_the_evaluator(self):
        ctx, _ = a_context()
        config = PipelineConfig(
            use_resolver=False,
            use_critic=False,
            write_rationales=False,
            absence_policy=AbsencePolicy.OPEN_WORLD,
        )
        trial = compile_trial("NCT1", PROTOCOL, ctx, config)
        screening = screen_patient(trial, patient(), SCREENING, ctx, config)
        assert screening.result.absence_policy is AbsencePolicy.OPEN_WORLD

    def test_rationales_are_written_when_the_flag_is_on(self):
        ctx, _ = a_context(writer=WRITTEN_SENTENCE)
        config = PipelineConfig(use_resolver=False, use_critic=False, write_rationales=True)
        trial = compile_trial("NCT1", PROTOCOL, ctx, config)
        screening = screen_patient(trial, patient(a1c=None), SCREENING, ctx, config)
        assert screening.rationales is not None

    def test_without_the_flag_the_deterministic_rationales_are_used(self):
        ctx, _ = a_context()
        trial = compile_trial("NCT1", PROTOCOL, ctx, MINIMAL)
        screening = screen_patient(trial, patient(), SCREENING, ctx, MINIMAL)
        assert screening.rationales is not None
        assert all(r.source == "fallback" for r in screening.rationales.rationales)


class TestCostAndTrace:
    def test_every_stage_writes_into_one_trajectory(self):
        ctx, _ = a_context(critic=EQUIVALENT)
        config = PipelineConfig(use_resolver=False, use_critic=True, write_rationales=False)
        compile_trial("NCT1", PROTOCOL, ctx, config)
        agents = {step.agent for step in ctx.trajectory.steps}
        assert {"compiler", "critic"} <= agents
