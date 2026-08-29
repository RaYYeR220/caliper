"""The metamorphic suite, run as a test, plus the negative control on the suite itself.

Two of these matter more than the rest. The negative control builds cases whose assertions are
false on purpose and demands that the runner say so in detail, because a suite that cannot fail is
not evidence of anything. And the last two tests make the no-model claim checkable — once by
reading the imports out of the modules, once by making the construction of a client an error and
running the whole catalogue anyway — rather than leaving it asserted in a docstring.
"""

from __future__ import annotations

import ast
import sys
from functools import partial
from pathlib import Path

import pytest

from caliper.corpus import default_screening_date, load_patient, patient_ids
from caliper.ir import CriteriaSet
from caliper.perturb import redact_analyte

# `eval/` is a directory in the repository, not part of the installed `caliper` distribution, so
# the repository root has to be importable before the suite can be imported at all.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# ruff: noqa: E402

from eval.metamorphic import cases as cases_module
from eval.metamorphic import runner as runner_module
from eval.metamorphic.cases import (
    CASES,
    RENAL_PANEL,
    AllOf,
    AllVerdictsUnchanged,
    CriterionVerdictFlips,
    MetamorphicCase,
    Relation,
    ScreeningBlockedOn,
    all_of,
)
from eval.metamorphic.runner import run_all, run_case, to_markdown

FRESH_CHART = cases_module.FRESH_CHART
CREATININE_LOINC = cases_module.CREATININE_LOINC

# Anything reachable from here would put a model, or a socket, between a relation and its verdict.
FORBIDDEN_IMPORT_ROOTS = (
    "caliper.llm",
    "caliper.agents",
    "caliper.pipeline",
    "openai",
    "httpx",
    "requests",
    "socket",
    "urllib",
)


def _broken_case(case_id: str, relation: object) -> MetamorphicCase:
    """A case that asserts something false: deleting the creatinine plainly changes a verdict."""
    return MetamorphicCase(
        id=case_id,
        description="A case whose assertion is false, used to prove the runner can fail.",
        rationale="Deleting the only creatinine moves `creatinine-band` from MET to UNKNOWN.",
        criteria=RENAL_PANEL,
        patient_id=FRESH_CHART,
        perturb=partial(redact_analyte, loinc=CREATININE_LOINC),
        relation=relation,  # type: ignore[arg-type]
    )


def _criterion_ids(criteria: CriteriaSet) -> set[str]:
    return {criterion.id for criterion in criteria.criteria}


def _parts(relation: Relation) -> list[Relation]:
    """The relations a case asserts, flattening the one combinator there is."""
    return list(relation.relations) if isinstance(relation, AllOf) else [relation]


def _imported_modules(path: Path) -> set[str]:
    """Every module name a source file imports, however it spells the import."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


# --------------------------------------------------------------------------------------------
# The suite itself
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.id)
def test_every_relation_in_the_catalogue_holds(case: MetamorphicCase) -> None:
    result = run_case(case)
    assert result.passed, result.detail


def test_the_catalogue_is_large_enough_to_be_worth_reading() -> None:
    assert len(CASES) >= 14


def test_every_case_is_identifiable_and_described() -> None:
    ids = [case.id for case in CASES]
    assert len(set(ids)) == len(ids), "case ids must be unique to be attributable"
    for case in CASES:
        assert case.description.strip(), f"{case.id} has no description"
        assert case.rationale.strip(), f"{case.id} has no rationale"


def test_every_case_names_a_patient_in_the_committed_corpus() -> None:
    corpus = set(patient_ids())
    for case in CASES:
        assert case.patient_id in corpus, f"{case.id} names a patient that is not shipped"


def test_every_relation_names_a_criterion_the_case_actually_screens() -> None:
    """A mistyped criterion id would make a relation assert something about nothing."""
    for case in CASES:
        available = _criterion_ids(case.criteria)
        if case.criteria_after is not None:
            available &= _criterion_ids(case.criteria_after)
        for criterion_id in case.relation.criterion_ids:
            assert criterion_id in available, f"{case.id} names unknown criterion {criterion_id!r}"


def test_every_perturbation_kind_is_exercised() -> None:
    """Coverage of `caliper.perturb`, measured on the edits the cases actually make."""
    kinds = {
        record.kind
        for case in CASES
        for record in case.perturb(load_patient(case.patient_id)).perturbations
    }
    assert kinds == {
        # Every perturbation `caliper.perturb` offers.
        "redact_analyte",
        "shift_value",
        "convert_units",
        "shift_date",
        "remove_encounters",
        "add_condition",
        # Plus the one the suite builds for itself, because `perturb` has no function for it.
        "record_death",
    }


def test_both_interesting_absence_policies_are_exercised() -> None:
    policies = {case.policy for case in CASES}
    assert {"coverage_gated", "closed_world"} <= {policy.value for policy in policies}


def test_the_vital_status_cases_rest_on_the_corpus_as_shipped() -> None:
    """Two cases assume a fact about the corpus; say so plainly if the corpus ever moves."""
    as_of = default_screening_date()
    assert load_patient(cases_module.DECEASED).died_before(as_of)
    assert not load_patient(cases_module.FRESH_CHART).died_before(as_of)


def test_only_the_vital_status_cases_screen_around_a_block() -> None:
    """A criterion-level relation needs criteria, and a blocked screening evaluates none.

    `screen` stops before reading anything for a patient recorded dead on or before the screening
    date. A case that landed on such a patient by accident would compare two empty criteria tables
    and pass without asserting anything, so every case that does not mean to exercise the block
    has to start from a chart that is actually read.
    """
    for case in CASES:
        if any(isinstance(part, ScreeningBlockedOn) for part in _parts(case.relation)):
            continue
        result = run_case(case)
        assert result.before is not None and result.before.blocked_by is None, (
            f"{case.id} screens a patient whose chart is blocked, so no criterion is evaluated "
            f"and its relation has nothing to be about"
        )


def test_the_suite_is_deterministic() -> None:
    """Two runs of the same catalogue must produce the same verdicts, not merely the same passes."""
    first, second = run_all(), run_all()
    assert [(r.case_id, r.passed, r.detail) for r in first] == [
        (r.case_id, r.passed, r.detail) for r in second
    ]


# --------------------------------------------------------------------------------------------
# The negative control: the runner has to be able to fail
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("case_id", "relation", "expected_fragments"),
    [
        (
            "broken-claims-nothing-changed",
            AllVerdictsUnchanged(),
            ("every criterion keeps the verdict it had", "creatinine-band", "MET", "UNKNOWN"),
        ),
        (
            "broken-claims-an-untouched-criterion-flips",
            CriterionVerdictFlips("adult"),
            ("adult", "flips between MET and NOT_MET", "stayed MET"),
        ),
        (
            "broken-claims-a-flip-where-the-verdict-is-lost",
            all_of(CriterionVerdictFlips("creatinine-band")),
            ("creatinine-band", "MET -> UNKNOWN", "resolved verdict on both sides"),
        ),
    ],
)
def test_the_runner_reports_a_relation_that_does_not_hold(
    case_id: str, relation: object, expected_fragments: tuple[str, ...]
) -> None:
    result = run_case(_broken_case(case_id, relation))

    assert not result.passed
    for fragment in expected_fragments:
        assert fragment in result.detail, f"{fragment!r} missing from {result.detail!r}"
    # A failure has to be inspectable, not just labelled.
    assert result.before is not None and result.after is not None


def test_a_perturbation_that_cannot_be_applied_fails_the_case() -> None:
    """A chart edit that silently did not happen would be a false label, so it must fail loudly."""
    case = MetamorphicCase(
        id="broken-perturbation-does-not-apply",
        description="Redacts an analyte this patient has never had measured.",
        rationale="`caliper.perturb` refuses to no-op, and the runner must not swallow that.",
        criteria=RENAL_PANEL,
        patient_id=FRESH_CHART,
        perturb=partial(redact_analyte, loinc="00000-0"),
        relation=AllVerdictsUnchanged(),
    )

    result = run_case(case)

    assert not result.passed
    assert "did not apply" in result.detail
    assert "00000-0" in result.detail


def test_a_broken_case_is_marked_failed_in_the_report() -> None:
    broken = _broken_case("broken-in-the-report", AllVerdictsUnchanged())
    results = run_all([*CASES, broken])

    report = to_markdown(results, [*CASES, broken])

    assert "**FAIL**" in report
    assert "## Failures" in report
    assert f"{len(CASES)}/{len(CASES) + 1} relations held" in report


# --------------------------------------------------------------------------------------------
# The report
# --------------------------------------------------------------------------------------------


def test_to_markdown_includes_every_case() -> None:
    report = to_markdown(run_all())

    for case in CASES:
        assert case.id in report, f"{case.id} is missing from the report"
        assert case.description in report, f"{case.id}'s description is missing from the report"
        assert case.patient_id in report


def test_to_markdown_names_a_result_it_has_no_case_for() -> None:
    """The table still has to account for a row whose case is not in the catalogue."""
    orphan = run_case(_broken_case("orphan", AllVerdictsUnchanged()))

    report = to_markdown([orphan])

    assert "orphan" in report
    assert "not in the catalogue" in report


# --------------------------------------------------------------------------------------------
# No model, no network
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("module", [cases_module, runner_module], ids=["cases", "runner"])
def test_the_suite_imports_nothing_that_could_reach_a_model(module: object) -> None:
    imported = _imported_modules(Path(module.__file__))  # type: ignore[attr-defined]

    offending = sorted(
        name
        for name in imported
        for root in FORBIDDEN_IMPORT_ROOTS
        if name == root or name.startswith(f"{root}.")
    )
    assert not offending, f"{module.__name__} imports {offending}"  # type: ignore[attr-defined]


def test_the_suite_never_reaches_a_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Belt and braces on the import check: make construction itself an error and run anyway."""
    import httpx

    import caliper.llm
    import caliper.llm.client

    def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("the metamorphic suite must never construct a model client")

    monkeypatch.setattr(caliper.llm, "LLMClient", forbidden)
    monkeypatch.setattr(caliper.llm.client, "LLMClient", forbidden)
    monkeypatch.setattr(httpx, "Client", forbidden)
    monkeypatch.setattr(httpx, "AsyncClient", forbidden)

    results = run_all()

    assert results and all(result.passed for result in results)
