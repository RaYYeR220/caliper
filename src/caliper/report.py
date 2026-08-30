"""Turning a run into the document a reader argues with.

Everything here is generated. No number in `RESULTS.md` is typed by hand, which is the only way to
keep a report honest across a dozen edits — a hand-copied figure is a figure that will eventually be
stale, and nobody will notice because it looks fine.

The layout is deliberate. The operating point goes first because it is the headline — the share of
cases the system decided by itself, and the unsafe errors it committed doing so — then immediately
the two things that stop it being a magic trick: the trivial baselines that reach perfect safety by
refusing to answer, and the false-abstention rate that shows what refusing costs.

No sentence here may be able to contradict a figure printed beside it. That rules out two habits in
particular: describing an arm's behaviour in words the arm's own numbers can falsify ("answered
every case", when its coverage column says 94%), and stating a quantity as prose when it can be
computed ("roughly thirteen percentage points", when the intervals in the table span twenty-eight).
Every claim below is either derived from the run or is true by construction of the arm it names.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from caliper.evalrun import ArmReport
from caliper.metrics import CurvePoint


def _pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def _ci(bounds: tuple[float, float]) -> str:
    return f"{_pct(bounds[0])}–{_pct(bounds[1])}"


def _cost(value: float | None) -> str:
    return "—" if value is None else f"${value:.2f}"


@dataclass(frozen=True)
class ReportInputs:
    arms: list[ArmReport]
    key_digest: str
    key_cases: int
    metamorphic: str | None = None


def _errors(count: int) -> str:
    """The unsafe-error count as words that stay true at zero and at one."""
    if count == 0:
        return "no unsafe error"
    return f"**{count}** unsafe error" + ("" if count == 1 else "s")


def headline(arms: list[ArmReport]) -> str:
    """The operating point: what the system decided, and what that cost in unsafe errors.

    Both halves are read off the same arm's realised behaviour, so the sentence cannot congratulate
    the system on a safety record it did not have, nor report a coverage it reached only in a
    counterfactual sweep.
    """
    caliper = next((a for a in arms if a.arm == "caliper"), None)
    baseline = next((a for a in arms if a.arm == "single_prompt"), None)
    if caliper is None:
        return "No Caliper arm was run."

    summary = caliper.summary
    lines = [
        f"Caliper decided **{_pct(summary.coverage)}** of its {summary.cases} cases without a "
        f"human, committing {_errors(summary.unsafe)} in doing so.",
    ]
    if baseline is not None:
        other = baseline.summary
        lines.append(
            f"The single-prompt baseline decided **{_pct(other.coverage)}** of the same "
            f"{other.cases} cases and committed {_errors(other.unsafe)}."
        )
    return " ".join(lines)


def arm_table(arms: list[ArmReport]) -> str:
    header = (
        "| Arm | Cases | Accuracy | 95% CI | Coverage | Unsafe errors | "
        "False abstention | Coverage at 0 unsafe | Cost |\n"
        "|---|---:|---:|---|---:|---:|---:|---:|---:|"
    )
    rows = []
    for report in arms:
        s = report.summary
        rows.append(
            f"| `{report.arm}` | {s.cases} | {_pct(s.accuracy)} | {_ci(s.accuracy_ci)} | "
            f"{_pct(s.coverage)} | {s.unsafe} | {_pct(s.false_abstention)} | "
            f"{_pct(s.coverage_at_zero_unsafe)} | {_cost(report.cost_usd)} |"
        )
    return "\n".join([header, *rows])


def interval_note(arms: list[ArmReport]) -> str:
    """How wide the accuracy intervals in this run actually are, in the run's own numbers.

    Computed rather than described. A sentence naming a width the table beside it contradicts is
    worse than no sentence at all, and a hand-written one goes stale the first time the key grows.
    """
    widths = [high - low for a in arms for low, high in (a.summary.accuracy_ci,)]
    if not widths:
        return (
            "No arm was run, so there is no interval to report and nothing below is a measurement."
        )
    typical = median(widths)
    return (
        f"At this sample size an exact binomial interval spans about "
        f"{typical * 100:.0f} percentage points. Differences narrower than that are not "
        "differences, and the intervals are printed so that is checkable rather than asserted."
    )


def curve_table(points: list[CurvePoint]) -> str:
    header = (
        "| Abstention threshold | Coverage | Selective risk | Unsafe errors | Cases answered |\n"
        "|---:|---:|---:|---:|---:|"
    )
    rows = [
        f"| {p.threshold:.2f} | {_pct(p.coverage)} | {_pct(p.risk)} | {p.unsafe} | {p.answered} |"
        for p in points
    ]
    return "\n".join([header, *rows])


def trap_table(arms: list[ArmReport]) -> str:
    traps = sorted({trap for a in arms for trap in a.summary.by_trap})
    header = "| Trap | " + " | ".join(f"`{a.arm}`" for a in arms) + " |\n|---|" + "---|" * len(arms)
    rows = []
    for trap in traps:
        cells = []
        for report in arms:
            slice_ = report.summary.by_trap.get(trap)
            cells.append(
                "—"
                if slice_ is None
                else f"{slice_.correct}/{slice_.cases} correct, {slice_.unsafe} unsafe"
            )
        rows.append(f"| `{trap}` | " + " | ".join(cells) + " |")
    return "\n".join([header, *rows])


def failures_section(arms: list[ArmReport]) -> str:
    lines = []
    for report in arms:
        if not report.failures:
            continue
        lines.append(f"**`{report.arm}`** — {len(report.failures)} case(s) failed to run:")
        lines += [f"- `{f.case_id}` at {f.stage}: {f.error}" for f in report.failures]
    if not lines:
        return "No case failed to run in any arm."
    return "\n".join(lines)


def render(inputs: ReportInputs) -> str:
    """Build `RESULTS.md` from the run."""
    caliper = next((a for a in inputs.arms if a.arm == "caliper"), None)
    sections = [
        "# Results",
        "",
        "Generated by `caliper report`. Every figure below comes from the committed run; none is "
        "typed by hand.",
        "",
        f"Answer key: **{inputs.key_cases} cases**, frozen before the first scored run, "
        f"digest `{inputs.key_digest[:16]}…`.",
        "",
        "## Headline",
        "",
        headline(inputs.arms),
        "",
        interval_note(inputs.arms),
        "",
        "## Every arm",
        "",
        arm_table(inputs.arms),
        "",
        "The `Coverage at 0 unsafe` column is the operating point: the share of cases an arm "
        "decided by itself, or nothing at all if it committed an unsafe error. Safety is a "
        "precondition there rather than something to trade coverage against.",
        "",
    ]

    if any(a.arm == "always_needs_review" for a in inputs.arms):
        sections += [
            "`always_needs_review` is in this table on purpose. It can never commit an unsafe "
            "error, because it never sends anyone forward, and it is useless — which is the whole "
            "reason coverage and false abstention are reported beside the safety number rather "
            "than behind it.",
            "",
        ]

    if caliper is not None and caliper.summary.curve:
        sections += [
            "## Risk and coverage",
            "",
            "Each row answers the cases whose criteria resolved at least this far, reading an "
            "unresolved criterion the way a system with no notion of abstention would: an unknown "
            "inclusion assumed met, an unknown exclusion assumed untriggered. Every row is "
            "therefore a counterfactual — what answering would have cost — and not a record of "
            "what this run did. The headline above is the record.",
            "",
            curve_table(caliper.summary.curve),
            "",
        ]

    sections += [
        "## By trap",
        "",
        "Cases are labelled by the specific failure they were built to provoke.",
        "",
        trap_table(inputs.arms),
        "",
        "## Cases that failed to run",
        "",
        failures_section(inputs.arms),
        "",
    ]

    if inputs.metamorphic:
        sections += [
            "## Metamorphic checks",
            "",
            "These assert a required relationship between two runs rather than an answer, so they "
            "are true by construction and owe nothing to our answer key.",
            "",
            inputs.metamorphic,
            "",
        ]

    return "\n".join(sections)
