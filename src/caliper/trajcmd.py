"""Producing one readable trajectory per agent.

Two of Caliper's five agents never run during the evaluation, by design rather than oversight. The
extractor reads clinical notes, which only some charts carry; the writer produces the sentence a
coordinator reads, which no verdict depends on. Neither belongs on the path a score is computed
from.

They are still part of the system, so this command runs one screening with every agent switched on:
a patient who has notes, against a trial whose criteria need terminology. It writes what each agent
was asked and what it said. The run goes through the same tape as the evaluation, so a reviewer
with no key reproduces these too.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import typer
from rich.console import Console

from caliper import corpus
from caliper.agents.base import AgentContext
from caliper.evaluate import AbsencePolicy
from caliper.llm import LLMClient, Trajectory, profile_from_env, resolve_api_key
from caliper.notes import DEFAULT_NOTES_ROOT
from caliper.pipeline import PipelineConfig, compile_trial, screen_patient
from caliper.tape import DEFAULT_TAPE, Tape, TapeTransport

app = typer.Typer(help="Record and render one trajectory per agent.")
console = Console()

# Chosen so every agent has real work rather than a stub. This chart's notes assert an inferior
# STEMI, deny diabetes in as many words, and mention a brother's stent and a partner's treatment —
# so the extractor has one finding to keep and three to reject, and the trial's first inclusion is
# exactly the diabetes the note denies.
DEMO_PATIENT = "f870c432-0887-125e-f778-cf5110d3de1d"
DEMO_TRIAL = "NCT03315143"


@app.command("run")
def run(
    out: Path = typer.Option(Path("trajectories/product"), help="Where to write the trajectories."),
    tape_path: Path = typer.Option(DEFAULT_TAPE, "--tape"),
    record: bool = typer.Option(False, help="Call the provider for anything not already recorded."),
    patient_id: str = typer.Option(DEMO_PATIENT, "--patient"),
    nct_id: str = typer.Option(DEMO_TRIAL, "--trial"),
) -> None:
    """Screen one patient with every agent switched on, and write down what each one did."""
    tape = Tape(tape_path, mode="record" if record else "replay")
    profile = profile_from_env()
    upstream = None
    if tape.mode == "record":
        from openai import OpenAI

        upstream = OpenAI(api_key=resolve_api_key(profile), base_url=profile.base_url)

    trajectory = Trajectory()
    client = LLMClient(
        profile,
        transport=TapeTransport(tape, upstream=upstream),
        trajectory=trajectory,
        env={profile.api_key_env: "replayed"} if tape.mode == "replay" else None,
    )
    ctx = AgentContext(client=client, trajectory=trajectory)

    config = PipelineConfig(
        use_resolver=True,
        use_critic=True,
        use_narrative=True,
        write_rationales=True,
        absence_policy=AbsencePolicy.COVERAGE_GATED,
        notes_root=DEFAULT_NOTES_ROOT,
    )

    trial = corpus.load_trial(nct_id)
    compiled = compile_trial(nct_id, trial.criteria_text, ctx, config)
    patient = corpus.load_patient(patient_id)
    screening = screen_patient(compiled, patient, _as_of(), ctx, config)

    if record:
        tape.save()

    out.mkdir(parents=True, exist_ok=True)
    (out / "tape_keys_used.json").write_text(
        json.dumps(sorted(tape.used), indent=2), encoding="utf-8"
    )
    trajectory.write_jsonl(out / "run.jsonl")
    (out / "run.md").write_text(trajectory.to_markdown(), encoding="utf-8")

    by_agent: dict[str, list] = {}
    for step in trajectory.steps:
        by_agent.setdefault(step.agent, []).append(step)
    for agent, steps in sorted(by_agent.items()):
        text = Trajectory(steps).to_markdown(repeat_instructions=False)
        (out / f"{agent}.md").write_text(text, encoding="utf-8")
        console.print(f"{agent}: {len(steps)} call(s) -> {out / f'{agent}.md'}")

    console.print(
        f"\n{screening.result.decision.value} for {patient_id[:8]} against {nct_id}; "
        f"{screening.result.criteria_resolved} of {screening.result.criteria_total} resolved, "
        f"{len(screening.result.to_confirm_at_visit)} to confirm at the visit"
    )
    if screening.narrative is not None:
        console.print(
            f"notes: {len(screening.narrative.evidence)} coded, "
            f"{len(screening.narrative.negations)} documented negations, "
            f"{len(screening.narrative.discarded)} discarded"
        )
    if screening.rationales is not None:
        fell_back = screening.rationales.fallback_count
        console.print(f"rationales: {fell_back} fell back to machine prose")


def _as_of() -> date:
    return corpus.default_screening_date()
