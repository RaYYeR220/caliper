"""The command line.

Written so that a reviewer with no Python and no API key can still get to the headline result:
`caliper data verify` proves the fixtures are the ones the report was built from, and
`caliper eval --replay` reproduces the numbers from recorded model responses.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from caliper import corpus, evalcmd, uicmd
from caliper.agents.base import AgentContext
from caliper.config import load_env
from caliper.llm import LLMClient, Trajectory, has_api_key, profile_from_env
from caliper.pipeline import DEFAULT_CONFIG, PipelineConfig, compile_trial, screen_patient


def _use_utf8() -> None:
    """Print protocol text without losing characters to a legacy console codepage.

    Eligibility criteria are full of the unicode operators the registry stores them with, and a
    Windows console defaults to a national codepage that cannot encode them. Without this, showing
    a compiled criterion raises rather than printing.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


_use_utf8()

# Read `.env` before anything resolves a provider profile from the environment.
load_env()

app = typer.Typer(add_completion=False, help="Evidence-bound pre-screening for clinical trials.")
data_app = typer.Typer(help="Inspect and verify the committed fixtures.")
app.add_typer(data_app, name="data")
app.add_typer(evalcmd.app, name="")
app.add_typer(uicmd.app, name="ui")

console = Console()


def _screening_date() -> date:
    override = os.environ.get("CALIPER_SCREENING_DATE")
    return date.fromisoformat(override) if override else corpus.default_screening_date()


def _context() -> AgentContext:
    profile = profile_from_env()
    if not has_api_key(profile):
        raise typer.BadParameter(
            f"no API key found in {profile.api_key_env}. "
            "Copy .env.example to .env, or use the replay path, which needs no key."
        )
    trajectory = Trajectory()
    return AgentContext(client=LLMClient(profile, trajectory=trajectory), trajectory=trajectory)


@data_app.command("verify")
def data_verify() -> None:
    """Check every committed fixture against its recorded digest."""
    report = corpus.verify_digests()
    for name in report.missing:
        console.print(f"[red]missing[/red]  {name}")
    for name in report.mismatched:
        console.print(f"[red]changed[/red]  {name}")
    if report.ok:
        console.print(f"[green]{report.checked} files verified[/green]")
        return
    raise typer.Exit(code=1)


@data_app.command("trials")
def data_trials() -> None:
    """List the trials in the corpus with the size of their criteria."""
    table = Table("NCT", "Title", "Criteria", "Age", box=None)
    for nct_id in corpus.trial_ids():
        trial = corpus.load_trial(nct_id)
        bounds = " to ".join(x for x in (trial.minimum_age, trial.maximum_age) if x) or "unbounded"
        table.add_row(nct_id, trial.short_title, f"{len(trial.criteria_text)} chars", bounds)
    console.print(table)


@data_app.command("patients")
def data_patients() -> None:
    """List the patients in the corpus with what their charts contain."""
    as_of = _screening_date()
    table = Table("Patient", "Age", "Evidence rows", "Encounters", box=None)
    for patient_id in corpus.patient_ids():
        patient = corpus.load_patient(patient_id)
        age = patient.age_at(as_of)
        encounters = sum(1 for e in patient.evidence if e.kind == "encounter")
        table.add_row(
            patient_id[:8],
            f"{age:g}" if age is not None else "unknown",
            str(len(patient.evidence)),
            str(encounters),
        )
    console.print(table)


@app.command()
def compile(  # noqa: A001 - the verb is the right name for the command
    nct_id: str,
    out: Path = typer.Option(None, help="Write the compiled criteria here as JSON."),
    depth: int = typer.Option(DEFAULT_CONFIG.compile_depth, help="Composite nesting allowed."),
    resolver: bool = typer.Option(True, help="Resolve concepts to terminology codes."),
    critic: bool = typer.Option(True, help="Back-translate and check every criterion."),
) -> None:
    """Compile one trial's eligibility criteria into executable form."""
    trial = corpus.load_trial(nct_id)
    ctx = _context()
    config = PipelineConfig(compile_depth=depth, use_resolver=resolver, use_critic=critic)
    compiled = compile_trial(nct_id, trial.criteria_text, ctx, config)

    table = Table("id", "kind", "predicate", "quote", box=None)
    for criterion in compiled.criteria_set.criteria:
        table.add_row(
            criterion.id,
            criterion.kind,
            criterion.predicate.type,
            criterion.source_quote[:60],
        )
    console.print(table)
    console.print(
        f"{len(compiled.criteria_set.criteria)} criteria, "
        f"{compiled.unsupported_count} not formalised, "
        f"{len(compiled.compilation.spans_unaccounted)} spans unaccounted for"
    )
    if compiled.critic_report is not None:
        console.print(f"critic downgraded {len(compiled.critic_report.downgrades)} criteria")

    if out is not None:
        out.write_text(compiled.criteria_set.model_dump_json(indent=2), encoding="utf-8")
        console.print(f"written to {out}")


@app.command()
def screen(
    nct_id: str,
    patient_id: str,
    packet: Path = typer.Option(None, help="Write the screening packet here."),
) -> None:
    """Screen one patient against one trial and print the verdict."""
    trial = corpus.load_trial(nct_id)
    patient = corpus.load_patient(patient_id)
    as_of = _screening_date()

    ctx = _context()
    compiled = compile_trial(nct_id, trial.criteria_text, ctx)
    screening = screen_patient(compiled, patient, as_of, ctx)
    result = screening.result

    console.print(f"[bold]{result.decision.value}[/bold]  {patient_id[:8]} against {nct_id}")
    console.print(f"{result.criteria_resolved} of {result.criteria_total} criteria resolved")
    for hint in result.resolution_worklist:
        console.print(f"  open: {hint.blocks_criterion_id} needs {hint.missing}")
    for caveat in result.approximations:
        console.print(f"  caveat: {caveat}")

    if packet is not None:
        from caliper.packet import build_packet, render_html

        document = build_packet(
            result, compiled.criteria_set, patient, screening.rationales, trial_title=trial.title
        )
        packet.write_text(render_html(document), encoding="utf-8")
        console.print(f"packet written to {packet}")


@app.command()
def trajectory(run: Path, out: Path = typer.Option(None, help="Write Markdown here.")) -> None:
    """Render a recorded trajectory as something a person can read."""
    loaded = Trajectory.read_jsonl(run)
    text = loaded.to_markdown()
    if out is None:
        console.print(text)
        return
    out.write_text(text, encoding="utf-8")
    console.print(f"written to {out}")


@app.command()
def tape(
    path: Path = typer.Option(Path("eval/tape.jsonl"), help="The recording to inspect."),
    agent: str = typer.Option(None, help="Show only what this agent was asked."),
    limit: int = typer.Option(5, help="How many exchanges to print in full."),
) -> None:
    """Read a recorded run: what each agent was asked, and what it said."""
    from caliper.tape import Tape

    loaded = Tape(path, mode="replay")
    console.print(f"{len(loaded)} exchanges in {path}")
    for name, count in loaded.agents.items():
        console.print(f"  {name}: {count}")

    shown = 0
    for exchange in loaded.exchanges():
        if agent and exchange.agent != agent:
            continue
        if shown >= limit:
            break
        shown += 1
        console.print("")
        console.print(
            f"[bold]{exchange.agent}[/bold]  {exchange.model}  {exchange.key[:12]}"
        )
        console.print(f"  asked:  {exchange.user[:400]}")
        console.print(f"  said:   {exchange.response[:400]}")


@app.command()
def costs(run: Path) -> None:
    """Summarise what a recorded run cost, by agent and by model."""
    loaded = Trajectory.read_jsonl(run)
    ledger = loaded.cost_ledger()
    console.print(json.dumps(ledger.to_dict(), indent=2))


if __name__ == "__main__":
    app()
