"""Running the evaluation.

The runner's job is to make two systems answer exactly the same questions and to write down what
happened in enough detail that someone else can check it. The scoring logic it feeds lives in
`caliper.metrics`; what is tested here is that the questions really are the same, that a failure is
recorded as a failure rather than as an abstention, and that compilation is not paid for twice.
"""

import json
from datetime import date

from caliper.answerkey import AnswerKey, Case
from caliper.blockers import Blocker
from caliper.evalrun import (
    Arm,
    ArmReport,
    forced_outcome,
    run_arm,
    score_screening,
    span_coverage,
)
from caliper.evaluate import AbsencePolicy
from caliper.ir import (
    Code,
    Concept,
    CriteriaSet,
    Criterion,
    DemographicPredicate,
    ObservationPredicate,
    PresencePredicate,
    UnsupportedPredicate,
)
from caliper.logic import ScreeningOutcome, Verdict
from caliper.metrics import summarise
from caliper.pipeline import PipelineConfig
from caliper.record import Evidence, PatientIndex
from caliper.screen import screen

SCREENING = date(2026, 6, 1)
A1C = Code(system="LOINC", code="4548-4", display="Hemoglobin A1c")
A1C_CONCEPT = Concept(text="HbA1c", codes=(A1C,))
MI = Concept(text="myocardial infarction", codes=(Code(system="SNOMED", code="22298006"),))

SOURCE = "Inclusion Criteria:\n- HbA1c >= 7%\n- Age 18 years or older\nExclusion Criteria:\n- MI\n"


def criteria() -> CriteriaSet:
    return CriteriaSet(
        nct_id="NCT1",
        source_text=SOURCE,
        criteria=[
            Criterion(
                id="INC-01",
                kind="inclusion",
                source_quote="HbA1c >= 7%",
                predicate=ObservationPredicate(concept=A1C_CONCEPT, op=">=", value=7.0, unit="%"),
            ),
            Criterion(
                id="INC-02",
                kind="inclusion",
                source_quote="Age 18 years or older",
                predicate=DemographicPredicate(field="age", op=">=", value=18, unit="years"),
            ),
            Criterion(
                id="EXC-01",
                kind="exclusion",
                source_quote="MI",
                predicate=PresencePredicate(type="condition", concept=MI, presence="present"),
            ),
        ],
    )


def patient(a1c: float | None) -> PatientIndex:
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
                resource_id="obs-1",
                display="Hemoglobin A1c",
                fhir_path="Bundle.entry[2].resource",
                codes=(A1C,),
                value=a1c,
                unit="%",
                date=date(2026, 5, 1),
            )
        )
    return PatientIndex(
        patient_id="p-1", birth_date=date(1970, 1, 1), sex="female", evidence=evidence
    )


class TestForcedOutcome:
    """What the system would have said had it not been allowed to abstain."""

    def test_an_unresolved_inclusion_is_read_generously(self):
        result = screen(criteria(), patient(a1c=None), SCREENING)
        assert result.decision is ScreeningOutcome.NEEDS_REVIEW
        assert forced_outcome(result) is ScreeningOutcome.ELIGIBLE

    def test_a_resolved_case_is_forced_to_the_answer_it_already_gave(self):
        result = screen(criteria(), patient(a1c=8.1), SCREENING)
        assert forced_outcome(result) is result.decision

    def test_a_decisive_failure_survives_being_forced(self):
        result = screen(criteria(), patient(a1c=5.2), SCREENING)
        assert forced_outcome(result) is ScreeningOutcome.INELIGIBLE

    def test_an_unresolved_exclusion_is_also_read_generously(self):
        """Reading an unknown exclusion as untriggered is the optimistic reading, on purpose."""
        record = PatientIndex(
            patient_id="p-1",
            birth_date=date(1970, 1, 1),
            sex="female",
            evidence=[
                Evidence(
                    kind="observation",
                    resource_type="Observation",
                    resource_id="obs-1",
                    display="Hemoglobin A1c",
                    fhir_path="Bundle.entry[2].resource",
                    codes=(A1C,),
                    value=8.1,
                    unit="%",
                    date=date(2026, 5, 1),
                )
            ],
        )
        result = screen(criteria(), record, SCREENING)
        assert result.decision is ScreeningOutcome.NEEDS_REVIEW
        assert forced_outcome(result) is ScreeningOutcome.ELIGIBLE


class TestScoring:
    def a_case(self, expected: ScreeningOutcome, trap: str = "none") -> Case:
        return Case(
            id="C-001",
            patient_id="p-1",
            nct_id="NCT1",
            screening_date=SCREENING,
            expected=expected,
            provenance="constructed",
            trap=trap,
            rationale="because",
        )

    def test_a_score_carries_what_the_curve_needs(self):
        result = screen(criteria(), patient(a1c=None), SCREENING)
        score = score_screening(self.a_case(ScreeningOutcome.ELIGIBLE), result)
        assert score.decision is ScreeningOutcome.NEEDS_REVIEW
        assert score.forced_decision is ScreeningOutcome.ELIGIBLE
        assert 0 < score.criteria_coverage < 1

    def test_the_trap_and_provenance_travel_with_the_score(self):
        result = screen(criteria(), patient(a1c=8.1), SCREENING)
        score = score_screening(self.a_case(ScreeningOutcome.ELIGIBLE, trap="unit"), result)
        assert (score.trap, score.provenance) == ("unit", "constructed")

    def test_a_fully_resolved_case_has_complete_coverage(self):
        result = screen(criteria(), patient(a1c=8.1), SCREENING)
        score = score_screening(self.a_case(ScreeningOutcome.ELIGIBLE), result)
        assert score.criteria_coverage == 1.0


class TestRunningAnArm:
    def key(self, *cases: Case) -> AnswerKey:
        return AnswerKey(
            version="1", screening_date=SCREENING, cases=tuple(cases), frozen_at=None, notes=""
        )

    def a_case(self, case_id: str, patient_id: str = "p-1") -> Case:
        return Case(
            id=case_id,
            patient_id=patient_id,
            nct_id="NCT1",
            screening_date=SCREENING,
            expected=ScreeningOutcome.ELIGIBLE,
            provenance="constructed",
            trap="none",
            rationale="because",
        )

    def test_a_trial_is_compiled_once_however_many_patients_use_it(self):
        compiled: list[str] = []

        def compile_once(nct_id: str) -> CriteriaSet:
            compiled.append(nct_id)
            return criteria()

        arm = Arm(name="caliper", config=PipelineConfig(), compile_trial=compile_once)
        report = run_arm(
            self.key(self.a_case("C-001"), self.a_case("C-002", "p-2")),
            arm,
            load_patient=lambda pid: patient(a1c=8.1),
        )
        assert compiled == ["NCT1"]
        assert len(report.scores) == 2

    def test_the_summary_is_computed_over_the_arm(self):
        arm = Arm(name="caliper", config=PipelineConfig(), compile_trial=lambda n: criteria())
        report = run_arm(
            self.key(self.a_case("C-001")), arm, load_patient=lambda pid: patient(a1c=8.1)
        )
        assert report.summary.arm == "caliper"
        assert report.summary.cases == 1

    def test_a_case_whose_patient_cannot_be_loaded_is_recorded_as_a_failure(self):
        def explode(patient_id: str) -> PatientIndex:
            raise FileNotFoundError(patient_id)

        arm = Arm(name="caliper", config=PipelineConfig(), compile_trial=lambda n: criteria())
        report = run_arm(self.key(self.a_case("C-001")), arm, load_patient=explode)
        assert report.failures and report.failures[0].case_id == "C-001"
        assert report.scores == []

    def test_the_arm_records_the_absence_policy_it_ran_under(self):
        config = PipelineConfig(absence_policy=AbsencePolicy.CLOSED_WORLD)
        arm = Arm(name="closed", config=config, compile_trial=lambda n: criteria())
        report = run_arm(
            self.key(self.a_case("C-001")), arm, load_patient=lambda pid: patient(a1c=None)
        )
        assert report.arm == "closed"
        assert report.scores[0].decision is ScreeningOutcome.NEEDS_REVIEW


class TestPersistence:
    def test_a_report_round_trips_through_json(self, tmp_path):
        arm = Arm(name="caliper", config=PipelineConfig(), compile_trial=lambda n: criteria())
        key = AnswerKey(
            version="1",
            screening_date=SCREENING,
            cases=(
                Case(
                    id="C-001",
                    patient_id="p-1",
                    nct_id="NCT1",
                    screening_date=SCREENING,
                    expected=ScreeningOutcome.ELIGIBLE,
                    provenance="constructed",
                    trap="none",
                    rationale="because",
                ),
            ),
            frozen_at=None,
            notes="",
        )
        report = run_arm(key, arm, load_patient=lambda pid: patient(a1c=8.1))
        path = tmp_path / "scores.json"
        report.write_json(path)
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["arm"] == "caliper"
        assert loaded["scores"][0]["case_id"] == "C-001"


class TestVerdictsAreNotSilentlyCoerced:
    def test_an_unknown_criterion_never_reads_as_met_in_the_recorded_verdicts(self):
        result = screen(criteria(), patient(a1c=None), SCREENING)
        recorded = {c.criterion_id: c.verdict for c in result.criteria}
        assert recorded["INC-01"] is Verdict.UNKNOWN


class TestConstructedCases:
    """A case whose chart was edited must be scored against the edited chart.

    Loading the base chart instead is silent: every constructed case still runs, still produces a
    verdict, and the verdict answers a question nobody asked.
    """

    def a_case(self, case_id: str, patient_id: str = "p-1", **overrides) -> Case:
        base = dict(
            id=case_id,
            patient_id=patient_id,
            nct_id="NCT1",
            screening_date=SCREENING,
            expected=ScreeningOutcome.ELIGIBLE,
            provenance="constructed",
            trap="none",
            rationale="because",
            perturbations=({"kind": "add_observation", "description": "supplied HbA1c 8.1"},),
        )
        return Case(**{**base, **overrides})

    def key(self, *cases: Case) -> AnswerKey:
        return AnswerKey(
            version="1", screening_date=SCREENING, cases=tuple(cases), frozen_at=None, notes=""
        )

    def test_the_loader_is_given_the_case_not_only_the_patient_id(self):
        seen: list[str] = []

        def load(case: Case) -> PatientIndex:
            seen.append(case.id)
            return patient(a1c=8.1)

        arm = Arm(name="caliper", config=PipelineConfig(), compile_trial=lambda n: criteria())
        run_arm(self.key(self.a_case("CK-001")), arm, load_patient=load)
        assert seen == ["CK-001"]

    def test_an_edited_chart_reaches_the_screening(self):
        def load(case: Case) -> PatientIndex:
            return patient(a1c=8.1 if case.perturbations else None)

        arm = Arm(name="caliper", config=PipelineConfig(), compile_trial=lambda n: criteria())
        report = run_arm(self.key(self.a_case("CK-001")), arm, load_patient=load)
        assert report.scores[0].decision is ScreeningOutcome.ELIGIBLE

    def test_a_chart_that_cannot_be_rebuilt_is_a_failure_not_a_verdict(self):
        def load(case: Case) -> PatientIndex:
            raise ValueError("a recorded edit did not apply")

        arm = Arm(name="caliper", config=PipelineConfig(), compile_trial=lambda n: criteria())
        report = run_arm(self.key(self.a_case("CK-001")), arm, load_patient=load)
        assert report.scores == []
        assert report.failures[0].stage == "load_patient"


def test_a_blocker_keeps_its_own_trial_denominator_through_the_json() -> None:
    """Dropped in serialisation, the report's counts silently revert to "of the whole run"."""
    report = ArmReport(
        arm="caliper",
        scores=[],
        summary=summarise([], arm="caliper"),
        blockers=[
            Blocker(
                nct_id="NCT03315143",
                criterion_id="INC-03",
                screenings=18,
                reason="r",
                missing="m",
                trial_screenings=24,
            )
        ],
        screenings=51,
    )

    row = report.to_dict()["blockers"][0]
    assert row["trial_screenings"] == 24
    assert Blocker(**row).trial_screenings == 24


class TestSpanCoverage:
    """How much of the protocol text some criterion actually claims, per arm.

    `CHANGELOG.md` entry 4 argues that compiling one span at a time beats handing a model the whole
    eligibility blob, and says the evidence is spans no criterion claims rather than accuracy —
    which was true, and the figure was in no committed artifact. A claim whose evidence exists only
    in a command's stdout is a claim a reader has to take on trust.
    """

    def a_criteria_set(self, quotes: list[str]) -> CriteriaSet:
        return CriteriaSet(
            nct_id="NCT1",
            source_text="Inclusion Criteria:\n- Age 18 years or older\n- HbA1c >= 7%\n",
            criteria=[
                Criterion(
                    id=f"INC-{i:02d}",
                    kind="inclusion",
                    source_quote=quote,
                    predicate=UnsupportedPredicate(reason="not the point of this test"),
                )
                for i, quote in enumerate(quotes, start=1)
            ],
        )

    def test_an_arm_that_claims_every_span_reports_none_unclaimed(self):
        report = ArmReport(
            arm="caliper",
            scores=[],
            summary=summarise([], arm="caliper"),
            span_coverage=span_coverage(
                [self.a_criteria_set(["Age 18 years or older", "HbA1c >= 7%"])]
            ),
        )

        assert report.span_coverage == (2, 2)

    def test_a_span_no_criterion_quotes_is_counted_as_unclaimed(self):
        covered, total = span_coverage([self.a_criteria_set(["Age 18 years or older"])])

        assert (covered, total) == (1, 2)

    def test_it_survives_the_json_round_trip(self):
        report = ArmReport(
            arm="caliper", scores=[], summary=summarise([], arm="caliper"), span_coverage=(7, 9)
        )
        payload = report.to_dict()

        assert payload["span_coverage"] == [7, 9]

    def test_an_arm_that_compiled_nothing_reports_nothing_rather_than_a_ratio(self):
        assert span_coverage([]) == (0, 0)
