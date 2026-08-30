"""The results document.

Its one job is to be impossible to quietly falsify. Every figure is computed here, so the tests are
about what the document refuses to omit: the trivial baseline that reaches perfect safety by
answering nothing, the confidence interval that says how little fifty cases prove, and the cases
that failed to run at all.

The other half is what the document may not *say*. A generated report can print a sentence its own
table contradicts, and that is worse than an omission because it reads as a finding. So the
headline is checked against the arm it describes, and the sample-size caveat is checked against the
intervals it is talking about.
"""

from caliper.blockers import Blocker
from caliper.evalrun import ArmReport
from caliper.logic import ScreeningOutcome as Outcome
from caliper.metrics import CaseScore, summarise
from caliper.report import (
    MAX_BLOCKERS_LISTED,
    ReportInputs,
    arm_table,
    base_rate_note,
    blocker_note,
    blocker_table,
    expected_table,
    headline,
    interval_note,
    ordered_arms,
    render,
)


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

# The shape the real run has, and the one the old headline could not describe. Every case whose
# criteria did not fully resolve would have been waved through had the system been forced to answer,
# so every point on the risk-coverage curve carries an unsafe error and the curve reading of
# "coverage at zero unsafe" collapses to nothing — for an arm that decided half its cases cleanly.
ABSTAINS_WHERE_IT_WOULD_HAVE_BEEN_WRONG = arm(
    "caliper",
    [
        # Decided on 40% of the criteria, which a decisive exclusion legitimately allows: one
        # failed inclusion ends a screening whatever the rest of the protocol says.
        CaseScore(
            case_id="C-001",
            expected=Outcome.INELIGIBLE,
            decision=Outcome.INELIGIBLE,
            forced_decision=Outcome.INELIGIBLE,
            criteria_coverage=0.4,
            provenance="annotated",
        ),
        CaseScore(
            case_id="C-002",
            expected=Outcome.INELIGIBLE,
            decision=Outcome.NEEDS_REVIEW,
            forced_decision=Outcome.ELIGIBLE,
            criteria_coverage=0.4,
            provenance="annotated",
        ),
    ],
)

INPUTS = ReportInputs(
    arms=[CALIPER, BASELINE, TRIVIAL],
    key_digest="0123456789abcdef" * 4,
    key_cases=3,
)


def a_lopsided_run(ineligible: int = 41, eligible: int = 6, review: int = 4) -> list[Outcome]:
    """The shape of the corrected answer key, where `ineligible` is most of the answer."""
    return (
        [Outcome.INELIGIBLE] * ineligible
        + [Outcome.ELIGIBLE] * eligible
        + [Outcome.NEEDS_REVIEW] * review
    )


def an_arm_answering(name: str, answer: Outcome, expected: list[Outcome]) -> ArmReport:
    rows = [
        CaseScore(
            case_id=f"C-{i:03d}",
            expected=want,
            decision=answer,
            forced_decision=answer,
            criteria_coverage=1.0,
            provenance="annotated",
        )
        for i, want in enumerate(expected, start=1)
    ]
    return arm(name, rows, cost=0.0)


def a_perfect_arm(name: str, expected: list[Outcome]) -> ArmReport:
    rows = [
        CaseScore(
            case_id=f"C-{i:03d}",
            expected=want,
            decision=want,
            forced_decision=want,
            criteria_coverage=1.0,
            provenance="annotated",
        )
        for i, want in enumerate(expected, start=1)
    ]
    return arm(name, rows)


LOPSIDED = a_lopsided_run()
ALWAYS_INELIGIBLE = an_arm_answering("always_ineligible", Outcome.INELIGIBLE, LOPSIDED)
REAL = a_perfect_arm("caliper", LOPSIDED)
LOPSIDED_INPUTS = ReportInputs(
    arms=[REAL, ALWAYS_INELIGIBLE],
    key_digest="0123456789abcdef" * 4,
    key_cases=len(LOPSIDED),
)


class TestHeadline:
    def test_it_names_the_coverage_the_system_actually_reached(self):
        assert f"{CALIPER.summary.coverage * 100:.0f}%" in headline([CALIPER, BASELINE])

    def test_it_reports_the_real_operating_point_and_not_the_curve(self):
        """The bug this pins printed "decided 0% of cases while committing no unsafe error"."""
        report = ABSTAINS_WHERE_IT_WOULD_HAVE_BEEN_WRONG
        assert report.summary.unsafe == 0
        assert report.summary.coverage == 0.5
        assert all(point.unsafe > 0 for point in report.summary.curve)

        text = headline([report])
        assert "50%" in text
        assert "no unsafe error" in text

    def test_it_does_not_claim_a_baseline_answered_every_case_unless_it_did(self):
        text = headline([CALIPER, BASELINE])
        assert BASELINE.summary.coverage == 1.0
        assert f"{BASELINE.summary.coverage * 100:.0f}%" in text
        assert "answered every case" not in text

    def test_it_counts_the_baselines_unsafe_errors_rather_than_glossing_them(self):
        assert BASELINE.summary.unsafe == 2
        assert "**2** unsafe errors" in headline([CALIPER, BASELINE])

    def test_a_clean_arm_is_described_in_words_rather_than_as_a_zero(self):
        assert "no unsafe error" in headline([CALIPER])

    def test_it_says_so_plainly_when_there_is_nothing_to_report(self):
        assert "No Caliper arm" in headline([BASELINE])

    def test_a_baseline_that_ran_no_cases_is_left_out_rather_than_reported_as_zero(self):
        """Decided 0% of 0 cases is true of an arm that never ran, and reads as a result."""
        empty = arm("single_prompt", [], cost=0.0)
        text = headline([CALIPER, empty])
        assert "single-prompt" not in text


class TestTheBaseRate:
    """Accuracy on a key that is 80% one answer is close to a measurement of the key.

    The document has to say so where the table is, and the sentence has to rest on a row the reader
    can see rather than on an assertion. `always_ineligible` is that row.
    """

    def test_the_document_names_the_arm_that_proves_the_point(self):
        text = render(LOPSIDED_INPUTS)
        assert "always_ineligible" in text
        assert "What the accuracy column is worth" in text

    def test_it_quotes_the_degenerate_arms_own_two_numbers(self):
        note = base_rate_note(LOPSIDED_INPUTS.arms)
        assert note is not None
        summary = ALWAYS_INELIGIBLE.summary
        assert f"{summary.accuracy * 100:.0f}%" in note
        assert f"{summary.balanced_accuracy * 100:.0f}%" in note

    def test_the_section_is_dropped_when_no_such_arm_was_run(self):
        """A floor nobody measured is a claim, and this module does not print claims."""
        text = render(ReportInputs(arms=[REAL], key_digest="x" * 64, key_cases=len(LOPSIDED)))
        assert base_rate_note([REAL]) is None
        assert "What the accuracy column is worth" not in text

    def test_the_per_outcome_table_shows_where_the_correctness_came_from(self):
        table = expected_table(LOPSIDED_INPUTS.arms)
        assert "41/41" in table
        assert "0/6" in table
        assert "0/4" in table

    def test_the_balanced_column_is_in_the_table_beside_accuracy(self):
        table = arm_table(LOPSIDED_INPUTS.arms)
        assert "| Balanced |" in table
        # 80% accuracy, 33% balanced, on the same row.
        assert "| 80% | 33% |" in table


RISK_FACTOR = Blocker(
    nct_id="NCT03315143",
    criterion_id="INC-04",
    screenings=24,
    reason="no evidence resolves 'at least one major cardiovascular risk factor'",
    missing="whether any of the risk factors the protocol means is documented",
    quote="At least one major cardiovascular risk factor",
)
UNSTABLE_TREATMENT = Blocker(
    nct_id="NCT03315143",
    criterion_id="INC-06",
    screenings=8,
    reason="prescriptions carry no stop date",
    missing="whether antihyperglycemic treatment was stable in the last 12 weeks",
    quote="Antihyperglycemic treatment has not been stable within 12 weeks | of screening",
)


class TestWhatAbstentionCost:
    """A false-abstention rate says how often; these say which criteria, and at what cost.

    The distinction the section turns on: a criterion that blocks every screening is one
    conversation about the protocol, settled once for the cohort. A criterion that blocks a third of
    them is a per-patient tax. Both are the same integer until the document says which.
    """

    def test_the_section_appears_where_the_false_abstention_figure_is(self):
        text = render(
            ReportInputs(
                arms=INPUTS.arms,
                key_digest=INPUTS.key_digest,
                key_cases=3,
                blockers=[RISK_FACTOR, UNSTABLE_TREATMENT],
                blocked_screenings=24,
            )
        )
        assert "What abstention cost" in text
        assert text.index("Every arm") < text.index("What abstention cost")
        assert text.index("What abstention cost") < text.index("Risk and coverage")

    def test_it_names_the_criteria_and_quotes_the_protocol_at_the_reader(self):
        table = blocker_table([RISK_FACTOR, UNSTABLE_TREATMENT], 24)
        assert "`INC-04`" in table
        assert "At least one major cardiovascular risk factor" in table
        assert "24 of 24" in table

    def test_a_pipe_in_the_protocol_text_does_not_break_the_table(self):
        row = blocker_table([UNSTABLE_TREATMENT], 24).splitlines()[-1]
        assert "\\|" in row
        # Four columns, so five unescaped delimiters. The one in the quote is not one of them.
        assert row.replace("\\|", "").count("|") == 5

    def test_a_criterion_that_blocks_everything_is_described_as_such_in_words(self):
        note = blocker_note([RISK_FACTOR], 24)
        assert "every one" in note
        assert "`INC-04`" in note
        assert "That is not a per-patient cost" in note

    def test_a_criterion_that_blocks_some_of_them_is_not(self):
        note = blocker_note([UNSTABLE_TREATMENT], 24)
        assert "every one" not in note

    def test_two_of_them_are_described_in_the_plural(self):
        """A generated sentence that reads as broken English is one nobody trusts."""
        both = Blocker(
            nct_id="NCT03315143", criterion_id="INC-06", screenings=24, reason="r", missing="m"
        )
        note = blocker_note([RISK_FACTOR, both], 24)
        assert "`INC-04` and `INC-06`" in note
        assert "Those are not per-patient costs" in note

    def test_two_trials_are_told_apart_where_the_identifiers_collide(self):
        """`INC-06` is a different criterion in every protocol, so the sentence has to say which."""
        elsewhere = Blocker(
            nct_id="NCT01131676", criterion_id="INC-06", screenings=24, reason="r", missing="m"
        )
        note = blocker_note([RISK_FACTOR, elsewhere], 24)

        assert "(NCT01131676)" in note
        assert "(NCT03315143)" in note

    def test_the_counts_are_not_summed_into_a_number_of_screenings(self):
        """A screening held up by three criteria is held up once, not three times."""
        note = blocker_note([RISK_FACTOR, UNSTABLE_TREATMENT], 24)
        assert "32" not in note
        assert "appears in both rows" in note

    def test_the_section_is_omitted_when_the_run_recorded_no_blockers(self):
        """An empty list means the runner did not record them, not that nothing blocked anything."""
        assert "What abstention cost" not in render(INPUTS)

    def test_a_long_tail_is_truncated_and_said_to_be(self):
        many = [
            Blocker(
                nct_id="NCT03315143",
                criterion_id=f"INC-{i:02d}",
                screenings=1,
                reason="r",
                missing="m",
            )
            for i in range(MAX_BLOCKERS_LISTED + 3)
        ]
        text = render(
            ReportInputs(
                arms=INPUTS.arms,
                key_digest=INPUTS.key_digest,
                key_cases=3,
                blockers=many,
                blocked_screenings=24,
            )
        )
        assert "3 further criteria" in text
        assert f"`INC-{MAX_BLOCKERS_LISTED:02d}`" not in text

    def test_the_arm_the_blockers_belong_to_is_named_rather_than_assumed(self):
        text = render(
            ReportInputs(
                arms=INPUTS.arms,
                key_digest=INPUTS.key_digest,
                key_cases=3,
                blockers=[RISK_FACTOR],
                blocked_arm="caliper-no-resolver",
                blocked_screenings=24,
            )
        )
        assert "`caliper-no-resolver`" in text


class TestArmOrder:
    def test_the_arms_that_answer_without_looking_come_last(self):
        ordered = ordered_arms([ALWAYS_INELIGIBLE, REAL])
        assert [a.arm for a in ordered] == ["caliper", "always_ineligible"]

    def test_every_always_arm_is_grouped_there_whichever_answer_it_gives(self):
        arms = [
            an_arm_answering("always_eligible", Outcome.ELIGIBLE, LOPSIDED),
            REAL,
            ALWAYS_INELIGIBLE,
            TRIVIAL,
        ]
        assert [a.arm for a in ordered_arms(arms)][0] == "caliper"
        assert {a.arm for a in ordered_arms(arms)[1:]} == {
            "always_eligible",
            "always_ineligible",
            "always_needs_review",
        }

    def test_an_arm_that_happens_to_answer_uniformly_is_not_demoted_for_it(self):
        """Answering uniformly is not evidence of a policy; a name is a claim its author made."""
        uniform = an_arm_answering("single_prompt", Outcome.ELIGIBLE, LOPSIDED)
        assert [a.arm for a in ordered_arms([uniform, ALWAYS_INELIGIBLE])] == [
            "single_prompt",
            "always_ineligible",
        ]

    def test_random_is_named_because_its_answers_vary_without_meaning_anything(self):
        varied = arm(
            "random",
            scores(
                (Outcome.ELIGIBLE, Outcome.ELIGIBLE, "none"),
                (Outcome.INELIGIBLE, Outcome.NEEDS_REVIEW, "none"),
            ),
        )
        assert [a.arm for a in ordered_arms([varied, REAL])] == ["caliper", "random"]

    def test_real_arms_keep_the_order_they_were_given_in(self):
        ordered = ordered_arms([BASELINE, CALIPER, TRIVIAL])
        assert [a.arm for a in ordered][:2] == ["single_prompt", "caliper"]


class TestIntervalNote:
    def test_the_width_it_names_is_the_width_the_table_prints(self):
        widths = [(a.summary.accuracy_ci[1] - a.summary.accuracy_ci[0]) * 100 for a in INPUTS.arms]
        note = interval_note(INPUTS.arms)
        assert f"{sorted(widths)[len(widths) // 2]:.0f} percentage points" in note

    def test_it_reports_no_interval_rather_than_a_made_up_one(self):
        assert "no interval" in interval_note([])


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
        assert "percentage points" in render(INPUTS)

    def test_the_trivial_baseline_paragraph_is_dropped_when_that_arm_was_not_run(self):
        """A paragraph about an arm that is not in the table is a claim about nothing."""
        text = render(ReportInputs(arms=[CALIPER], key_digest="x" * 64, key_cases=3))
        assert "always_needs_review" not in text

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
