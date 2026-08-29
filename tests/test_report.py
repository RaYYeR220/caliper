"""The results document.

Its one job is to be impossible to quietly falsify. Every figure is computed here, so the tests are
about what the document refuses to omit: the trivial baseline that reaches perfect safety by
answering nothing, the confidence interval that says how little fifty cases prove, and the cases
that failed to run at all.
"""

from caliper.evalrun import ArmReport
from caliper.logic import ScreeningOutcome as Outcome
from caliper.metrics import CaseScore, summarise
from caliper.report import ReportInputs, arm_table, headline, render


def scores(*rows: tuple[Outcome, Outcome, str]) -> list[CaseScore]:
    return [
        CaseScore(
            case_id=f"C-{i:03d}",
            expected=expected,
            decision=decision,
            forced_decision=decision,
            criteria_coverage=1.0 if decision is not Outcome.NEEDS_REVIEW else 0.5,
            trap=trap,
            provenance="annotated",
        )
        for i, (expected, decision, trap) in enumerate(rows, start=1)
    ]


def arm(name: str, rows: list[CaseScore], cost: float | None = 1.0) -> ArmReport:
    return ArmReport(arm=name, scores=rows, summary=summarise(rows, arm=name), cost_usd=cost)


CALIPER = arm(
    "caliper",
    scores(
        (Outcome.ELIGIBLE, Outcome.ELIGIBLE, "none"),
        (Outcome.INELIGIBLE, Outcome.INELIGIBLE, "threshold_edge"),
        (Outcome.NEEDS_REVIEW, Outcome.NEEDS_REVIEW, "missing_data"),
    ),
)
BASELINE = arm(
    "single_prompt",
    scores(
        (Outcome.ELIGIBLE, Outcome.ELIGIBLE, "none"),
        (Outcome.INELIGIBLE, Outcome.ELIGIBLE, "threshold_edge"),
        (Outcome.NEEDS_REVIEW, Outcome.ELIGIBLE, "missing_data"),
    ),
)
TRIVIAL = arm(
    "always_needs_review",
    scores(
        (Outcome.ELIGIBLE, Outcome.NEEDS_REVIEW, "none"),
        (Outcome.INELIGIBLE, Outcome.NEEDS_REVIEW, "threshold_edge"),
        (Outcome.NEEDS_REVIEW, Outcome.NEEDS_REVIEW, "missing_data"),
    ),
    cost=0.0,
)

INPUTS = ReportInputs(
    arms=[CALIPER, BASELINE, TRIVIAL],
    key_digest="0123456789abcdef" * 4,
    key_cases=3,
)


class TestHeadline:
    def test_it_names_the_coverage_reached_with_no_unsafe_error(self):
        assert "%" in headline([CALIPER, BASELINE])

    def test_it_states_the_baselines_unsafe_errors_beside_it(self):
        text = headline([CALIPER, BASELINE])
        assert "unsafe" in text

    def test_it_says_so_plainly_when_there_is_nothing_to_report(self):
        assert "No Caliper arm" in headline([BASELINE])


class TestArmTable:
    def test_every_arm_appears(self):
        table = arm_table(INPUTS.arms)
        for name in ("caliper", "single_prompt", "always_needs_review"):
            assert f"`{name}`" in table

    def test_each_row_carries_a_confidence_interval(self):
        assert table_rows(arm_table(INPUTS.arms))[2].count("–") == 1

    def test_the_free_baselines_report_a_cost_of_zero_rather_than_nothing(self):
        assert "$0.00" in arm_table([TRIVIAL])


class TestTheDocument:
    def test_the_trivial_baseline_is_explained_rather_than_left_to_look_good(self):
        text = render(INPUTS)
        assert "always_needs_review" in text
        assert "useless" in text

    def test_the_sample_size_caveat_is_not_optional(self):
        assert "thirteen percentage points" in render(INPUTS)

    def test_the_key_digest_is_printed_so_the_key_can_be_checked(self):
        assert INPUTS.key_digest[:16] in render(INPUTS)

    def test_the_risk_coverage_curve_is_included_when_there_is_one(self):
        assert "Risk and coverage" in render(INPUTS)

    def test_traps_are_broken_out(self):
        text = render(INPUTS)
        assert "`missing_data`" in text
        assert "`threshold_edge`" in text

    def test_a_clean_run_says_no_case_failed_rather_than_omitting_the_section(self):
        text = render(INPUTS)
        assert "Cases that failed to run" in text
        assert "No case failed to run" in text

    def test_failures_are_listed_with_their_stage_and_error(self):
        from caliper.evalrun import CaseFailure

        broken = ArmReport(
            arm="caliper",
            scores=CALIPER.scores,
            summary=CALIPER.summary,
            failures=[CaseFailure("C-009", "load_patient", "no such chart")],
        )
        text = render(ReportInputs(arms=[broken], key_digest="x" * 64, key_cases=3))
        assert "C-009" in text and "load_patient" in text and "no such chart" in text

    def test_the_metamorphic_section_appears_only_when_there_is_one(self):
        assert "Metamorphic checks" not in render(INPUTS)
        with_it = ReportInputs(
            arms=INPUTS.arms,
            key_digest=INPUTS.key_digest,
            key_cases=3,
            metamorphic="| case | result |",
        )
        assert "Metamorphic checks" in render(with_it)


def table_rows(table: str) -> list[str]:
    return table.splitlines()
