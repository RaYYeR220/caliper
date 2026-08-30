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

from collections.abc import Sequence
from dataclasses import dataclass
from statistics import median

from caliper.blockers import Blocker
from caliper.evalrun import ArmReport
from caliper.metrics import CurvePoint

MAX_BLOCKERS_LISTED = 10


def _pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def _ci(bounds: tuple[float, float]) -> str:
    return f"{_pct(bounds[0])}–{_pct(bounds[1])}"


def _cost(value: float | None) -> str:
    return "—" if value is None else f"${value:.2f}"


def _cell(text: str) -> str:
    """Protocol text goes in table cells, and a pipe or a newline in it breaks the table."""
    return " ".join(text.split()).replace("|", "\\|")


@dataclass(frozen=True)
class ReportInputs:
    arms: list[ArmReport]
    key_digest: str
    key_cases: int
    metamorphic: str | None = None

    blockers: Sequence[Blocker] = ()
    """The criteria that left screenings undecided, most frequent first.

    Computed by the runner rather than here: a blocker is a fact about a `ScreeningResult`, and the
    per-arm results this module is handed carry only the case-level scores. Empty when the run did
    not record them, in which case the section is omitted rather than guessed at.
    """

    blocked_arm: str = "caliper"
    """Which arm the blockers were counted over. Named so the section cannot mislabel them."""

    blocked_screenings: int = 0
    """How many screenings that arm ran. The denominator every count below is reported against."""

    comparison: Sequence[ArmReport] = ()
    """The same recorded decisions scored against a different answer key.

    The key was corrected after a scored run, which is exactly when a correction deserves least
    trust. Publishing only the corrected figures asks the reader to take our word for it; publishing
    both lets them ask the better question — did fixing the key change the conclusion, or only the
    numbers? Empty when there is nothing to compare, in which case the section is omitted.
    """

    comparison_label: str = ""
    """What that other key is called, in the reader's words rather than a path."""

    comparison_digest: str = ""
    """Its digest, so the comparison names the file it was made against rather than a version."""

    def __post_init__(self) -> None:
        if self.comparison and not self.comparison_label:
            raise ValueError(
                "a comparison needs a label: an unnamed second column of numbers invites the "
                "reader to guess which key produced it"
            )


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
    # Only when it answered something. "Decided 0% of the same 0 cases" is a true sentence about an
    # arm that did not run, and it reads as a result.
    if baseline is not None and baseline.summary.cases:
        other = baseline.summary
        lines.append(
            f"The single-prompt baseline decided **{_pct(other.coverage)}** of the same "
            f"{other.cases} cases and committed {_errors(other.unsafe)}."
        )
    return " ".join(lines)


DEGENERATE_PREFIX = "always_"
DEGENERATE_ARMS = frozenset({"random"})


def is_degenerate(report: ArmReport) -> bool:
    """Whether this arm answers without reading the chart in front of it.

    Read off the arm's name, which follows the convention `evalcmd.ARMS` uses: an `always_*` arm
    returns one fixed outcome, and `random` returns outcomes that vary without meaning anything.

    Inferring it from the answers instead was the obvious alternative and is wrong twice over. An
    arm that answered every case identically has done so degenerately in that run, but on a short
    run that is a coincidence rather than a policy — three cases and a real baseline can look
    identical to `always_eligible` — and on a lopsided key a genuinely good system could answer
    uniformly and be relegated for it. A name is a claim its author made; the answers are not.
    """
    return report.arm.startswith(DEGENERATE_PREFIX) or report.arm in DEGENERATE_ARMS


def ordered_arms(arms: list[ArmReport]) -> list[ArmReport]:
    """Real systems first, then the arms that answer without looking, each in the order given.

    Interleaved, a degenerate arm reads as a competitor. Grouped at the bottom it reads as what it
    is: the floor the table is measured against.
    """
    return [a for a in arms if not is_degenerate(a)] + [a for a in arms if is_degenerate(a)]


def arm_table(arms: list[ArmReport]) -> str:
    # "Protocol claimed" only appears when some arm compiled something. On a run of baselines alone
    # it would be a column of dashes implying a measurement nobody made.
    spans = any(report.span_coverage[1] for report in arms)
    header = (
        "| Arm | Cases | Accuracy | Balanced | 95% CI | Coverage | Unsafe errors | "
        "False abstention | Coverage at 0 unsafe |"
        + (" Protocol claimed |" if spans else "")
        + " Cost |\n|---|---:|---:|---:|---|---:|---:|---:|---:|"
        + ("---:|" if spans else "")
        + "---:|"
    )
    rows = []
    for report in ordered_arms(arms):
        s = report.summary
        claimed, total = report.span_coverage
        span_cell = f" {_pct(claimed / total)} |" if total else " — |"
        rows.append(
            f"| `{report.arm}` | {s.cases} | {_pct(s.accuracy)} | {_pct(s.balanced_accuracy)} | "
            f"{_ci(s.accuracy_ci)} | {_pct(s.coverage)} | {s.unsafe} | "
            f"{_pct(s.false_abstention)} | {_pct(s.coverage_at_zero_unsafe)} |"
            + (span_cell if spans else "")
            + f" {_cost(report.cost_usd)} |"
        )
    return "\n".join([header, *rows])


def expected_table(arms: list[ArmReport]) -> str:
    """How each arm did on each answer the key expects, which is where a base-rate exploit shows."""
    outcomes = sorted({name for a in arms for name in a.summary.by_expected})
    ordered = ordered_arms(arms)
    header = (
        "| Key expects | Cases | "
        + " | ".join(f"`{a.arm}`" for a in ordered)
        + " |\n|---|---:|"
        + "---:|" * len(ordered)
    )
    rows = []
    for outcome in outcomes:
        counts = [
            a.summary.by_expected[outcome].cases
            for a in ordered
            if outcome in a.summary.by_expected
        ]
        total = max(counts, default=0)
        cells = []
        for report in ordered:
            slice_ = report.summary.by_expected.get(outcome)
            cells.append("—" if slice_ is None else f"{slice_.correct}/{slice_.cases}")
        rows.append(f"| `{outcome}` | {total} | " + " | ".join(cells) + " |")
    return "\n".join([header, *rows])


def blocker_table(blockers: Sequence[Blocker], screenings: int) -> str:
    """One row per criterion that held screenings up, with the work that would settle it."""
    # The trial is part of the identity, not decoration: criterion identifiers are ordinals
    # within one protocol, so `INC-03` names something different in each of the eight here.
    header = (
        "| Trial | Criterion | Screenings blocked | Protocol text | What was missing |\n"
        "|---|---|---:|---|---|"
    )
    rows = []
    for blocker in blockers[:MAX_BLOCKERS_LISTED]:
        # Against its own trial's screenings, not the run's. A criterion on a protocol with 24
        # cases in a run of 51 can never block more than 24, and the larger denominator makes a
        # criterion that stops nearly everything look like one that stops a third of it.
        denominator = blocker.trial_screenings or screenings
        count = f"{blocker.screenings} of {denominator}" if denominator else str(blocker.screenings)
        rows.append(
            f"| {blocker.nct_id} | `{blocker.criterion_id}` | {count} | "
            f"{_cell(blocker.quote or '—')} | {_cell(blocker.missing or blocker.reason or '—')} |"
        )
    return "\n".join([header, *rows])


def _and_list(names: list[str]) -> str:
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + f" and {names[-1]}"


def blocker_note(blockers: Sequence[Blocker], screenings: int) -> str:
    """What the abstentions actually cost, in criteria rather than as a percentage.

    A criterion that stops *every* screening is one conversation about the protocol, settled once
    for the whole cohort. A criterion that stops a third of them is a per-patient tax on the chart.
    Both are the same integer in a table, so the sentence says which kind this run has rather than
    leaving the reader to divide.

    The counts are deliberately not summed. A screening held up by three criteria is held up once,
    and a total would read as a number of screenings while being a number of criterion-screenings.
    """
    if not blockers:
        return "No criterion left a screening undecided."

    subject = "criterion" if len(blockers) == 1 else "criteria"
    lines = [
        f"{len(blockers)} {subject} left screenings undecided, most-frequent first. Each row "
        "counts the screenings that one criterion held up, so a screening blocked by two of them "
        "appears in both rows."
    ]

    universal = [b for b in blockers if b.blocks_every_screening]
    if universal:
        # The trial is only worth naming where the sentence spans more than one, and repeating
        # the same NCT after every identifier reads like a machine wrote it, which it did.
        one_trial = len({b.nct_id for b in universal}) == 1
        named = _and_list(
            [
                f"`{b.criterion_id}`" if one_trial else f"`{b.criterion_id}` ({b.nct_id})"
                for b in universal
            ]
        )
        if len(universal) == 1:
            lines.append(
                f"{named} left **every one** of the {screenings} screenings undecided. That is not "
                "a per-patient cost. It is the same question about the protocol every time, and "
                "answering it once clears it for the whole cohort."
            )
        else:
            lines.append(
                f"{named} left **every one** of the {screenings} screenings undecided. Those are "
                "not per-patient costs. Each is the same question about the protocol every time, "
                "and answering them once clears them for the whole cohort."
            )
    return "\n\n".join(lines)


def blockers_section(inputs: ReportInputs) -> list[str]:
    """The section, or nothing when the run recorded no blockers to explain the number with."""
    if not inputs.blockers:
        return []
    listed = len(inputs.blockers[:MAX_BLOCKERS_LISTED])
    lines = [
        "### What abstention cost",
        "",
        f"The false-abstention column above says how often `{inputs.blocked_arm}` sent a decidable "
        "case to a human. It does not say why, and on its own that reads as a complaint. These are "
        "the criteria it could not settle from the record.",
        "",
        blocker_note(inputs.blockers, inputs.blocked_screenings),
        "",
        blocker_table(inputs.blockers, inputs.blocked_screenings),
        "",
    ]
    if listed < len(inputs.blockers):
        lines += [
            f"{len(inputs.blockers) - listed} further criteria blocked fewer screenings each and "
            "are omitted from this table.",
            "",
        ]
    return lines


def base_rate_note(arms: list[ArmReport]) -> str | None:
    """What the accuracy column is worth on this key, with the arm that proves it named.

    The arm named is whichever degenerate one scored highest on plain accuracy, because the point
    being made is how far up the accuracy column a system that reads nothing can get.

    Returns None when no degenerate arm was run: the claim rests on that arm's row, and a paragraph
    asserting a floor the table does not show would be exactly the kind of sentence this module is
    written to avoid.
    """
    candidates = [a for a in arms if is_degenerate(a) and a.summary.cases]
    if not candidates:
        return None
    exploit = max(candidates, key=lambda a: a.summary.accuracy)

    summary = exploit.summary
    largest = max(summary.by_expected.items(), key=lambda item: item[1].cases, default=None)
    if largest is None:
        return None
    name, biggest = largest
    outcomes = len(summary.by_expected)

    return "\n\n".join(
        [
            f"The key expects `{name}` for {biggest.cases} of its {summary.cases} cases. That is a "
            "real property of trial screening — most patients do not qualify for most trials — but "
            "it means the accuracy column above can be reached without reading a chart. "
            f"`{exploit.arm}` is in the table to make that concrete rather than latent: it scores "
            f"**{_pct(summary.accuracy)}** accuracy and knows nothing.",
            "The balanced column is the same run with that thumb taken off the scale: accuracy "
            f"computed per expected outcome and averaged unweighted over the {outcomes} outcomes "
            f"the key uses. `{exploit.arm}` scores **{_pct(summary.balanced_accuracy)}** on it, "
            f"which is the ceiling for any arm that gives the same answer every time. Read the "
            "balanced column, not the accuracy one, and read both against the unsafe-error count.",
        ]
    )


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


def _unsafe_ranking(arms: Sequence[ArmReport]) -> list[tuple[str, bool]]:
    """Which arms committed an unsafe error, by name. The only ordering this report argues from."""
    return sorted((a.arm, a.summary.unsafe > 0) for a in arms)


def comparison_table(
    arms: Sequence[ArmReport], other: Sequence[ArmReport], *, label: str
) -> str:
    """The same decisions under two keys, so any difference is the key's and not the run's."""
    by_name = {a.arm: a for a in other}
    header = (
        f"| Arm | Accuracy | Accuracy, {label} | Unsafe | Unsafe, {label} |\n"
        "|---|---:|---:|---:|---:|"
    )
    rows = []
    for report in ordered_arms(list(arms)):
        earlier = by_name.get(report.arm)
        rows.append(
            f"| `{report.arm}` | {_pct(report.summary.accuracy)} | "
            + (f"{_pct(earlier.summary.accuracy)}" if earlier else "—")
            + f" | {report.summary.unsafe} | "
            + (f"{earlier.summary.unsafe}" if earlier else "—")
            + " |"
        )
    return "\n".join([header, *rows])


def comparison_note(
    arms: Sequence[ArmReport], other: Sequence[ArmReport], *, label: str
) -> str | None:
    """Whether the correction moved the conclusion, stated only when it demonstrably did not.

    The conclusion this project rests on is an ordering, not a percentage: which arms sent a patient
    forward who should not have gone. If that ordering is identical under both keys then correcting
    the key changed the figures and nothing else, which is worth saying plainly. If it moved, the
    sentence says only that, and leaves the reader to compare — a report that talks its way out of
    an inconvenient comparison is worth less than no comparison at all.
    """
    if not other:
        return None

    shared = {a.arm for a in arms} & {a.arm for a in other}
    here = [(n, u) for n, u in _unsafe_ranking(arms) if n in shared]
    there = [(n, u) for n, u in _unsafe_ranking(other) if n in shared]
    lines = [
        "The decisions in both columns are the same recorded decisions. Only the key differs, so "
        "every change here is the key's doing and none of it is the system's."
    ]
    if here == there:
        lines.append(
            "Which arms committed an unsafe error is **unchanged** between the two: the "
            "correction moved the figures and left the conclusion where it was."
        )
    else:
        moved = sorted(n for (n, u), (_, v) in zip(here, there, strict=True) if u != v)
        lines.append(
            "Which arms committed an unsafe error is **not** the same between the two — "
            + _and_list([f"`{name}`" for name in moved])
            + " differs — so the correction did more than move figures, and the two columns have "
            "to be read against each other rather than one taken as the answer."
        )
    return " ".join(lines)


def render(inputs: ReportInputs) -> str:
    """Build `RESULTS.md` from the run."""
    caliper = next((a for a in inputs.arms if a.arm == "caliper"), None)
    sections = [
        "# Results",
        "",
        "Generated by `caliper report`. Every figure below comes from the committed run; none is "
        "typed by hand.",
        "",
        # Not "frozen before the first scored run": the key was corrected after one, which
        # `LIMITS.md` records. What the digest proves is narrower, and is what is claimed here.
        f"Answer key: **{inputs.key_cases} cases**, digest `{inputs.key_digest[:16]}…`. "
        "`caliper eval` refuses to score against a key whose digest does not match its sidecar; "
        "`LIMITS.md` records how the key was built and where it was corrected.",
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

    # Directly under the table, and before the accuracy discussion: the false-abstention figure and
    # the criteria that produced it have to be read together or the number reads as a complaint.
    sections += blockers_section(inputs)

    # The accuracy column is the weakest one printed, and a reader who has not been told so by the
    # time they have read it has already been misled.
    base_rate = base_rate_note(inputs.arms)
    if base_rate is not None:
        sections += [
            "### What the accuracy column is worth",
            "",
            base_rate,
            "",
            "Per expected outcome, which is where an arm that trades on the base rate shows itself "
            "— a column of the form `41/41`, `0/6`, `0/4`:",
            "",
            expected_table(inputs.arms),
            "",
        ]

    if inputs.comparison:
        sections += [
            f"## The same run, scored against {inputs.comparison_label}",
            "",
            f"Digest `{inputs.comparison_digest[:16]}…`. `LIMITS.md` records why there are two "
            "keys and `eval/annotation/corrections.md` lists every label that moved, with the "
            "chart value that refuted the old one.",
            "",
            comparison_table(inputs.arms, inputs.comparison, label=inputs.comparison_label),
            "",
            comparison_note(inputs.arms, inputs.comparison, label=inputs.comparison_label) or "",
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
