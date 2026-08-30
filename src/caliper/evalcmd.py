"""The `caliper eval` and `caliper report` commands.

Kept out of `cli.py` because this is where the run is defined rather than merely invoked: which
arms exist, what each one turns off, and which of them can share a compilation. Reading this file
should be enough to know exactly what produced `RESULTS.md`.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from caliper import corpus, report
from caliper.agents.base import AgentContext
from caliper.answerkey import (
    AnswerKey,
    Case,
    key_fingerprint,
    load_key,
    rebuild_patient,
    verify_frozen,
)
from caliper.baselines import (
    AlwaysEligible,
    AlwaysIneligible,
    AlwaysNeedsReview,
    RandomOutcome,
    SinglePrompt,
)
from caliper.blockers import Blocker
from caliper.evalrun import Arm, ArmReport, run_arm
from caliper.evaluate import AbsencePolicy
from caliper.ir import CriteriaSet
from caliper.llm import LLMClient, Trajectory, profile_from_env, resolve_api_key
from caliper.pipeline import PipelineConfig, compile_trial
from caliper.record import PatientIndex
from caliper.tape import DEFAULT_TAPE, Tape, TapeTransport

app = typer.Typer(help="Run the evaluation and rebuild the results.")
console = Console()

DEFAULT_KEY = Path("eval/answer_key.json")
DEFAULT_OUT = Path("eval/results")

ARMS: dict[str, PipelineConfig | None] = {
    "caliper": PipelineConfig(),
    "caliper-whole-protocol": PipelineConfig(per_span_compile=False),
    "caliper-no-critic": PipelineConfig(use_critic=False),
    "caliper-no-resolver": PipelineConfig(use_resolver=False),
    "caliper-closed-world": PipelineConfig(absence_policy=AbsencePolicy.CLOSED_WORLD),
    "caliper-open-world": PipelineConfig(absence_policy=AbsencePolicy.OPEN_WORLD),
    "single_prompt": None,
    "always_needs_review": None,
    "always_eligible": None,
    "always_ineligible": None,
    "random": None,
}




def _compile_key(config: PipelineConfig) -> tuple[int, bool, bool, bool]:
    """Arms differing only in how they read absence share their compiled criteria exactly."""
    return (
        config.compile_depth,
        config.per_span_compile,
        config.use_resolver,
        config.use_critic,
    )


def _context(tape: Tape) -> AgentContext:
    """One client for the whole run, answering from the tape or recording into it.

    Recording needs a live upstream; replaying refuses to build one, so a tape miss surfaces as a
    miss rather than as an unbudgeted call to a provider.
    """
    profile = profile_from_env()
    trajectory = Trajectory()
    upstream = None
    if tape.mode in ("record", "refresh"):
        from openai import OpenAI

        upstream = OpenAI(api_key=resolve_api_key(profile), base_url=profile.base_url)

    client = LLMClient(
        profile,
        transport=TapeTransport(tape, upstream=upstream),
        trajectory=trajectory,
        env={profile.api_key_env: "replayed"} if tape.mode == "replay" else None,
    )
    return AgentContext(client=client, trajectory=trajectory)


def _compiler(
    config: PipelineConfig, ctx: AgentContext, cache: dict
) -> Callable[[str], CriteriaSet]:
    def compile_for(nct_id: str) -> CriteriaSet:
        cache_key = (_compile_key(config), nct_id)
        if cache_key not in cache:
            trial = corpus.load_trial(nct_id)
            cache[cache_key] = compile_trial(nct_id, trial.criteria_text, ctx, config).criteria_set
        return cache[cache_key]

    return compile_for


def _chart_for(case: Case) -> PatientIndex:
    """The chart a case is about: the committed one, or the edited one it describes."""
    base = corpus.load_patient(case.patient_id)
    return rebuild_patient(case, base) if case.perturbations else base


def _baseline(name: str, ctx: AgentContext):
    if name == "single_prompt":
        return SinglePrompt(ctx.client)
    if name == "always_needs_review":
        return AlwaysNeedsReview()
    if name == "always_eligible":
        return AlwaysEligible()
    if name == "always_ineligible":
        return AlwaysIneligible()
    return RandomOutcome(seed=20260601)


def _run(
    key: AnswerKey,
    names: list[str],
    ctx: AgentContext,
    *,
    tape: Tape | None = None,
    save_every: int = 1,
) -> list[ArmReport]:
    reports: list[ArmReport] = []
    cache: dict = {}
    for index, name in enumerate(names, start=1):
        config = ARMS[name]
        before = ctx.trajectory.total_usd() or 0.0
        if config is None:
            arm = Arm(name=name, run_baseline=_baseline(name, ctx))
        else:
            arm = Arm(name=name, config=config, compile_trial=_compiler(config, ctx, cache))
        # Computed after the arm runs, not passed in: as an argument it was evaluated eagerly and
        # every arm reported nothing.
        report = run_arm(
            key,
            arm,
            load_patient=_chart_for,
            load_criteria_text=lambda nct: corpus.load_trial(nct).criteria_text,
        )
        spent = (ctx.trajectory.total_usd() or 0.0) - before
        reports.append(replace(report, cost_usd=spent))
        console.print(
            f"[green]{name}[/green]: {reports[-1].summary.cases} cases, "
            f"{reports[-1].summary.unsafe} unsafe, {reports[-1].wall_seconds:.0f}s"
        )
        if tape is not None and index % save_every == 0:
            tape.save()
    return reports


@app.command("eval")
def run_eval(
    key_path: Path = typer.Option(DEFAULT_KEY, "--key", help="The frozen answer key."),
    out: Path = typer.Option(DEFAULT_OUT, "--out", help="Where to write the per-arm results."),
    arms: str = typer.Option("all", help="Comma-separated arm names, or 'all'."),
    replay: bool = typer.Option(True, help="Replay recorded model responses. Needs no API key."),
    record: bool = typer.Option(False, help="Call the provider for anything not already recorded."),
    refresh: bool = typer.Option(False, help="Call the provider again even for recorded answers."),
    tape_path: Path = typer.Option(DEFAULT_TAPE, "--tape", help="The recording to use."),
    save_every: int = typer.Option(1, help="Write the tape after this many arms."),
) -> None:
    """Run every arm over the answer key and write the results."""
    if not verify_frozen(key_path):
        raise typer.BadParameter(
            f"{key_path} does not match its recorded digest. The key was edited after it was "
            "frozen, and scoring against it would prove nothing."
        )
    key = load_key(key_path)
    names = list(ARMS) if arms == "all" else [a.strip() for a in arms.split(",")]
    unknown = [n for n in names if n not in ARMS]
    if unknown:
        raise typer.BadParameter(f"unknown arm(s): {', '.join(unknown)}")

    mode = "refresh" if refresh else ("record" if record else "replay")
    tape = Tape(tape_path, mode=mode)
    if tape.mode == "replay" and len(tape) == 0:
        raise typer.BadParameter(
            f"{tape_path} is empty. Run with --record and a key to produce it, or check out the "
            "commit whose tape belongs to this code."
        )
    ctx = _context(tape)
    reports = _run(key, names, ctx, tape=tape if mode != "replay" else None, save_every=save_every)
    if mode != "replay":
        tape.save()
        console.print(f"recorded {len(tape)} exchanges to {tape_path}")
    else:
        console.print(f"replayed {tape.hits} exchanges from {tape_path}")

    out.mkdir(parents=True, exist_ok=True)
    for arm_report in reports:
        arm_report.write_json(out / f"{arm_report.arm}.json")

    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    (out / "run.json").write_text(
        json.dumps(
            {
                "finished_utc": stamp,
                "key_digest": key_fingerprint(key),
                "key_cases": len(key.cases),
                "arms": [r.arm for r in reports],
                "replayed": not record,
                "tape_exchanges": len(tape),
                "tape_agents": tape.agents,
                "total_usd": ctx.trajectory.total_usd(),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    ctx.trajectory.write_jsonl(out / "trajectory.jsonl")

    (out / "tape_keys_used.json").write_text(
        json.dumps(sorted(tape.used), indent=2), encoding="utf-8"
    )
    _print_summary(reports)
    console.print(f"\nresults written to {out}")


def _print_summary(reports: list[ArmReport]) -> None:
    table = Table("arm", "cases", "accuracy", "coverage", "unsafe", "cost", box=None)
    for r in reports:
        table.add_row(
            r.arm,
            str(r.summary.cases),
            f"{r.summary.accuracy:.0%}",
            f"{r.summary.coverage:.0%}",
            str(r.summary.unsafe),
            "—" if r.cost_usd is None else f"${r.cost_usd:.2f}",
        )
    console.print(table)


BLOCKED_ARM = "caliper"
"""Which arm "what abstention cost" is reported for: the system as it ships, not an ablation."""


@app.command("report")
def build_report(
    results: Path = typer.Option(DEFAULT_OUT, "--results", help="Where the per-arm results are."),
    out: Path = typer.Option(Path("RESULTS.md"), "--out"),
    metamorphic: Path = typer.Option(None, help="A Markdown table of metamorphic results."),
    compare: Path = typer.Option(
        None, help="A second results directory: the same decisions scored against another key."
    ),
    compare_label: str = typer.Option(
        "the earlier key", help="What to call that key in the report."
    ),
) -> None:
    """Rebuild RESULTS.md from the committed run. No figure in it is typed by hand."""
    run = json.loads((results / "run.json").read_text(encoding="utf-8"))
    reports = [_load_arm(results / f"{name}.json") for name in run["arms"]]
    # The blockers are reported for the system as it ships, not for an ablation: "what abstention
    # cost" is only a useful section if it is about the arm the headline numbers describe.
    blocked = next((r for r in reports if r.arm == BLOCKED_ARM), None)

    # The same recorded decisions, scored against a different key. Loaded from a directory rather
    # than rescored here, so the comparison is between two committed runs a reader can open.
    other: list[ArmReport] = []
    other_digest = ""
    if compare is not None:
        other_run = json.loads((compare / "run.json").read_text(encoding="utf-8"))
        other = [_load_arm(compare / f"{name}.json") for name in other_run["arms"]]
        other_digest = other_run["key_digest"]
    text = report.render(
        report.ReportInputs(
            arms=reports,
            key_digest=run["key_digest"],
            key_cases=run["key_cases"],
            metamorphic=metamorphic.read_text(encoding="utf-8") if metamorphic else None,
            blockers=blocked.blockers if blocked else (),
            blocked_arm=BLOCKED_ARM,
            blocked_screenings=blocked.screenings if blocked else 0,
            comparison=other,
            comparison_label=compare_label,
            comparison_digest=other_digest,
        )
    )
    out.write_text(text, encoding="utf-8")
    console.print(f"written to {out}")


def _load_arm(path: Path) -> ArmReport:
    from caliper.logic import ScreeningOutcome
    from caliper.metrics import CaseScore, summarise

    payload = json.loads(path.read_text(encoding="utf-8"))
    scores = [
        CaseScore(
            case_id=row["case_id"],
            expected=ScreeningOutcome(row["expected"]),
            decision=ScreeningOutcome(row["decision"]),
            forced_decision=ScreeningOutcome(row["forced_decision"]),
            criteria_coverage=row["criteria_coverage"],
            trap=row["trap"],
            provenance=row["provenance"],
        )
        for row in payload["scores"]
    ]
    return ArmReport(
        arm=payload["arm"],
        scores=scores,
        summary=summarise(scores, arm=payload["arm"]),
        cost_usd=payload.get("cost_usd"),
        blockers=[Blocker(**row) for row in payload.get("blockers", [])],
        screenings=payload.get("screenings", 0),
        span_coverage=tuple(payload.get("span_coverage", (0, 0))),
    )
