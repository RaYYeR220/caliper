"""What the coordinator's interface is entitled to assume about the export.

The interface is a static page with no way back into Python, so anything the exporter drops is
simply gone: a criterion that never reaches the JSON cannot be shown, and an evidence pointer that
does not travel cannot be opened. These tests are therefore about completeness more than about
formatting.

Two of them are about what the exporter must *not* do. It must not escape — the page builds its DOM
through `textContent` and would render an escaped ampersand literally — and it must not omit a key
because its value happens to be empty, because a viewer that has to distinguish "no open items"
from "this run did not record open items" will get it wrong.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import date
from pathlib import Path

from typer.testing import CliRunner

from caliper import corpus, uicmd
from caliper.agents.compiler import CompileResult
from caliper.agents.critic import (
    CriticReport,
    Finding,
    apply_findings,
    coverage_report,
    render_predicate,
)
from caliper.agents.writer import deterministic_rationales
from caliper.evaluate import AbsencePolicy
from caliper.ir import (
    Code,
    Concept,
    CriteriaSet,
    Criterion,
    DemographicPredicate,
    ObservationPredicate,
    PresencePredicate,
    TemporalWindow,
    UnsupportedPredicate,
)
from caliper.logic import ScreeningOutcome
from caliper.pipeline import CompiledTrial, PipelineConfig, Screening
from caliper.record import Evidence, PatientIndex
from caliper.screen import screen
from caliper.uiexport import (
    ScreeningRecord,
    _screening_entry,
    _trial_entry,
    export_screening,
    export_trial,
    write_ui_bundle,
)

SCREENING = date(2026, 6, 1)
TRIAL_TITLE = "A trial of something, in patients with something else"

AWKWARD_QUOTE = 'Investigator judgement: "unsuitable" for <any> reason & no appeal'

SOURCE = (
    "Inclusion Criteria:\n"
    "- HbA1c between 7.0 and 10.0 % within 12 weeks\n"
    "- Age 18 years or older\n"
    "- Serum creatinine at most 2.0 mg/dL\n"
    "Exclusion Criteria:\n"
    "- Myocardial infarction within 6 months of randomisation\n"
    "- Serum potassium above 5.5 mmol/L or a documented arrhythmia\n"
    f"- {AWKWARD_QUOTE}\n"
    "- A criterion nobody compiled\n"
)

HBA1C = Concept(
    text="HbA1c", codes=(Code(system="LOINC", code="4548-4", display="Haemoglobin A1c"),)
)
CREATININE = Concept(text="serum creatinine", codes=(Code(system="LOINC", code="2160-0"),))
POTASSIUM = Concept(text="serum potassium", codes=(Code(system="LOINC", code="2823-3"),))
INFARCTION = Concept(
    text="myocardial infarction", codes=(Code(system="SNOMED", code="22298006"),)
)

CRITERIA = CriteriaSet(
    nct_id="NCT04000000",
    source_text=SOURCE,
    criteria=[
        Criterion(
            id="INC-01",
            kind="inclusion",
            source_quote="HbA1c between 7.0 and 10.0 % within 12 weeks",
            predicate=ObservationPredicate(
                concept=HBA1C,
                op="between",
                value=7.0,
                value_high=10.0,
                unit="%",
                window=TemporalWindow(relation="within", amount=12, unit="weeks"),
            ),
        ),
        Criterion(
            id="INC-02",
            kind="inclusion",
            source_quote="Age 18 years or older",
            predicate=DemographicPredicate(field="age", op=">=", value=18, unit="years"),
        ),
        Criterion(
            id="INC-03",
            kind="inclusion",
            source_quote="Serum creatinine at most 2.0 mg/dL",
            predicate=ObservationPredicate(
                concept=CREATININE, op="<=", value=2.0, unit="mg/dL"
            ),
        ),
        Criterion(
            id="EXC-01",
            kind="exclusion",
            source_quote="Myocardial infarction within 6 months of randomisation",
            predicate=PresencePredicate(
                type="condition",
                concept=INFARCTION,
                presence="present",
                # Anchored somewhere other than screening, which is what makes the evaluator
                # record an approximation on every result that depends on this criterion.
                window=TemporalWindow(
                    relation="within", amount=6, unit="months", anchor="randomisation"
                ),
            ),
        ),
        Criterion(
            id="EXC-02",
            kind="exclusion",
            source_quote="Serum potassium above 5.5 mmol/L or a documented arrhythmia",
            predicate=ObservationPredicate(
                concept=POTASSIUM, op=">", value=5.5, unit="mmol/L"
            ),
        ),
        Criterion(
            id="EXC-03",
            kind="exclusion",
            source_quote=AWKWARD_QUOTE,
            predicate=UnsupportedPredicate(reason="the protocol defers to the investigator"),
        ),
    ],
)


def _criterion(criterion_id: str) -> Criterion:
    return next(c for c in CRITERIA.criteria if c.id == criterion_id)


# EXC-02 is the criterion the critic sends back: the compiled predicate reads on potassium alone
# where the protocol is also triggered by an arrhythmia, which is a narrowing and so a downgrade.
REVIEW = (
    Finding(
        criterion_id="EXC-02",
        severity="narrower",
        reason="B tests serum potassium only; A is also triggered by a documented arrhythmia.",
        rendered=render_predicate(_criterion("EXC-02").predicate),
        quote=_criterion("EXC-02").source_quote,
    ),
)


def a_patient(patient_id: str, *, born: date, hba1c: float | None) -> PatientIndex:
    """A chart with one encounter, so absence is answerable, and at most one lab."""
    evidence = [
        Evidence(
            kind="encounter",
            resource_type="Encounter",
            resource_id="enc-1",
            display="outpatient visit",
            fhir_path="Bundle.entry[0].resource",
            date=date(2026, 5, 1),
        )
    ]
    if hba1c is not None:
        evidence.append(
            Evidence(
                kind="observation",
                resource_type="Observation",
                resource_id="obs-1",
                display="Haemoglobin A1c",
                fhir_path="Bundle.entry[1].resource",
                codes=HBA1C.codes,
                value=hba1c,
                unit="%",
                date=date(2026, 5, 1),
            )
        )
    return PatientIndex(patient_id=patient_id, birth_date=born, sex="female", evidence=evidence)


def a_trial() -> CompiledTrial:
    """The criteria set as it stands after the critic's findings have been applied."""
    report = CriticReport.from_coverage(REVIEW, coverage_report(CRITERIA))
    return CompiledTrial(
        nct_id=CRITERIA.nct_id,
        criteria_set=apply_findings(CRITERIA, report),
        compilation=CompileResult(
            criteria_set=CRITERIA, units=(), rejected=(), failures=(), downgraded=()
        ),
        config=PipelineConfig(use_resolver=False, write_rationales=False),
        resolved_codes={
            "HbA1c": HBA1C.codes,
            "serum creatinine": CREATININE.codes,
            "serum potassium": POTASSIUM.codes,
        },
        critic_report=report,
    )


def a_screening(trial: CompiledTrial, patient: PatientIndex) -> Screening:
    result = screen(
        trial.criteria_set, patient, SCREENING, policy=AbsencePolicy.COVERAGE_GATED
    )
    return Screening(trial=trial, result=result, rationales=deterministic_rationales(result))


def an_open_screening() -> tuple[Screening, PatientIndex]:
    """An adult with an in-range HbA1c: nothing disqualifies her, so unknowns keep it open."""
    patient = a_patient("open-1", born=date(1970, 3, 2), hba1c=8.1)
    return a_screening(a_trial(), patient), patient


def a_closed_screening() -> tuple[Screening, PatientIndex]:
    """A child: the age criterion is provably not met, which ends the screening."""
    patient = a_patient("closed-1", born=date(2015, 3, 2), hba1c=8.1)
    return a_screening(a_trial(), patient), patient


# ------------------------------------------------------------------------------------------------
# The screening document
# ------------------------------------------------------------------------------------------------


def test_every_criterion_reaches_the_export_in_the_order_it_was_evaluated() -> None:
    screening, patient = an_open_screening()
    payload = export_screening(screening, patient, TRIAL_TITLE)

    assert [row["id"] for row in payload["criteria"]] == [
        result.criterion_id for result in screening.result.criteria
    ]
    assert len(payload["criteria"]) == len(CRITERIA.criteria)
    for row, result in zip(payload["criteria"], screening.result.criteria, strict=True):
        assert row["verdict"] == result.verdict.value
        assert row["kind"] == result.kind


def test_every_evidence_pointer_travels_with_its_value_date_and_unit() -> None:
    screening, patient = an_open_screening()
    payload = export_screening(screening, patient, TRIAL_TITLE)

    cited = [row for row in payload["criteria"] if row["evidence"]]
    assert cited, "the fixture must cite at least one piece of evidence"

    for row, result in zip(payload["criteria"], screening.result.criteria, strict=True):
        assert len(row["evidence"]) == len(result.evidence)
        for exported, evidence in zip(row["evidence"], result.evidence, strict=True):
            assert exported["fhir_path"] == evidence.fhir_path
            assert exported["resource"] == f"{evidence.resource_type}/{evidence.resource_id}"
            assert exported["value"] == evidence.value
            assert exported["unit"] == evidence.unit
            assert exported["date"] == (evidence.date.isoformat() if evidence.date else None)


def test_the_fingerprint_and_the_absence_policy_are_on_the_screening() -> None:
    screening, patient = an_open_screening()
    payload = export_screening(screening, patient, TRIAL_TITLE)

    assert payload["criteria_fingerprint"] == CRITERIA.source_text_sha256
    assert payload["absence_policy"]["value"] == AbsencePolicy.COVERAGE_GATED.value
    assert "an encounter documents the window" in payload["absence_policy"]["note"]


def test_approximations_are_exported_on_the_screening_and_on_the_criterion() -> None:
    screening, patient = an_open_screening()
    payload = export_screening(screening, patient, TRIAL_TITLE)

    assert payload["approximations"] == list(screening.result.approximations)
    assert payload["approximations"], "the anchored window must raise an approximation"

    # Each caveat also names the criteria that leaned on it, as the printed packet groups them.
    assert [c["text"] for c in payload["caveats"]] == payload["approximations"]
    assert payload["caveats"][0]["criterion_ids"] == ["EXC-01"]

    anchored = next(row for row in payload["criteria"] if row["id"] == "EXC-01")
    assert anchored["approximations"] == list(
        next(r for r in screening.result.criteria if r.criterion_id == "EXC-01").approximations
    )


def test_the_exporter_does_not_escape_and_the_strings_survive_a_json_round_trip() -> None:
    screening, patient = an_open_screening()
    payload = export_screening(screening, patient, TRIAL_TITLE)

    quoted = next(row for row in payload["criteria"] if row["id"] == "EXC-03")
    assert quoted["quote"] == AWKWARD_QUOTE

    serialised = json.dumps(payload, ensure_ascii=False)
    assert "&amp;" not in serialised
    assert "&lt;" not in serialised
    assert json.loads(serialised) == payload


def test_an_open_screening_raises_its_worklist_with_the_query_where_there_is_one() -> None:
    screening, patient = an_open_screening()
    payload = export_screening(screening, patient, TRIAL_TITLE)

    assert screening.result.decision is ScreeningOutcome.NEEDS_REVIEW
    assert payload["open_items"], "an open screening must carry its open items"

    by_criterion = {item["criterion_id"]: item for item in payload["open_items"]}
    # No creatinine is on file, and a query would fetch one.
    assert by_criterion["INC-03"]["retrievable"] is True
    assert by_criterion["INC-03"]["fhir_query"].startswith("Observation?patient=open-1")
    # A criterion nobody formalised has no query behind it, and says so rather than offering one.
    assert by_criterion["EXC-03"]["retrievable"] is False
    assert by_criterion["EXC-03"]["fhir_query"] == ""


def test_a_screening_with_no_open_items_exports_an_empty_list_not_a_missing_key() -> None:
    screening, patient = a_closed_screening()
    payload = export_screening(screening, patient, TRIAL_TITLE)

    assert screening.result.decision is ScreeningOutcome.INELIGIBLE
    assert "open_items" in payload
    assert payload["open_items"] == []
    # The gaps themselves are not lost: they stay on the criteria that could not be decided.
    assert any(row["resolution"] is not None for row in payload["criteria"])


def test_a_downgraded_criterion_carries_the_verdict_that_condemned_it() -> None:
    screening, patient = an_open_screening()
    payload = export_screening(screening, patient, TRIAL_TITLE)

    downgraded = next(row for row in payload["criteria"] if row["id"] == "EXC-02")
    assert downgraded["verdict"] == "unknown"
    assert downgraded["unsupported"] is True
    assert "narrower than the protocol quote" in downgraded["resolution"]["missing"]


# ------------------------------------------------------------------------------------------------
# The trial document
# ------------------------------------------------------------------------------------------------


def test_the_trial_export_renders_every_criterion_and_keeps_its_codes() -> None:
    payload = export_trial(a_trial(), TRIAL_TITLE)

    assert [row["id"] for row in payload["criteria"]] == [c.id for c in CRITERIA.criteria]
    assert payload["criteria_fingerprint"] == CRITERIA.source_text_sha256
    assert payload["counts"]["criteria"] == len(CRITERIA.criteria)

    hba1c = next(row for row in payload["criteria"] if row["id"] == "INC-01")
    assert hba1c["compiled_as"] == render_predicate(_criterion("INC-01").predicate)
    assert {"system": "LOINC", "code": "4548-4", "display": "Haemoglobin A1c"} in hba1c["codes"]


def test_a_downgraded_criterion_shows_what_it_compiled_to_and_why_it_was_withdrawn() -> None:
    payload = export_trial(a_trial(), TRIAL_TITLE)
    downgraded = next(row for row in payload["criteria"] if row["id"] == "EXC-02")

    assert downgraded["unsupported"] is True
    assert downgraded["critic"]["downgraded"] is True
    assert downgraded["critic"]["severity"] == "narrower"
    assert downgraded["critic"]["reason"] == REVIEW[0].reason
    # `apply_findings` has replaced the predicate, so the English the critic read is the only
    # surviving record of what the compiler produced. It has to travel.
    assert downgraded["critic"]["reviewed_rendering"] == REVIEW[0].rendered
    assert payload["counts"]["downgraded"] == 1


def test_every_protocol_span_is_exported_with_the_strength_of_its_claim() -> None:
    payload = export_trial(a_trial(), TRIAL_TITLE)
    coverage = payload["coverage"]

    assert len(coverage["spans"]) == coverage["total"]
    assert {span["claim"] for span in coverage["spans"]} <= {"direct", "inherited", "unclaimed"}
    assert coverage["unclaimed"] == sum(
        1 for span in coverage["spans"] if span["claim"] == "unclaimed"
    )
    # Every fixture quote is verbatim in the protocol text, so no span is unclaimed by accident.
    assert coverage["quote_problems"] == []
    unclaimed = [span["text"] for span in coverage["spans"] if span["claim"] == "unclaimed"]
    assert "A criterion nobody compiled" in unclaimed


# ------------------------------------------------------------------------------------------------
# The bundle
# ------------------------------------------------------------------------------------------------


def test_the_bundle_writes_one_file_per_screening_plus_an_index_that_lists_them(
    tmp_path: Path,
) -> None:
    trial = a_trial()
    records = [
        ScreeningRecord(
            screening=a_screening(trial, patient), patient=patient, trial_title=TRIAL_TITLE
        )
        for patient in (
            a_patient("open-1", born=date(1970, 3, 2), hba1c=8.1),
            a_patient("closed-1", born=date(2015, 3, 2), hba1c=8.1),
            a_patient("thin-1", born=date(1980, 3, 2), hba1c=None),
        )
    ]

    written = write_ui_bundle(records, root=tmp_path)
    data = tmp_path / "data"

    assert all(path.is_file() for path in written)
    # One trial document, three screenings, one index.
    assert len(written) == 5
    assert data / "index.json" in written

    index = json.loads((data / "index.json").read_text(encoding="utf-8"))
    assert [entry["patient_id"] for entry in index["screenings"]] == [
        "open-1",
        "closed-1",
        "thin-1",
    ]
    for entry in index["screenings"]:
        assert (data / entry["file"]).is_file()

    assert len(index["trials"]) == 1
    assert (data / index["trials"][0]["file"]).is_file()


def test_the_index_row_counts_the_two_kinds_of_gap_separately(tmp_path: Path) -> None:
    trial = a_trial()
    patient = a_patient("open-1", born=date(1970, 3, 2), hba1c=8.1)
    record = ScreeningRecord(
        screening=a_screening(trial, patient), patient=patient, trial_title=TRIAL_TITLE
    )

    write_ui_bundle([record], root=tmp_path)
    index = json.loads((tmp_path / "data" / "index.json").read_text(encoding="utf-8"))
    row = index["screenings"][0]

    assert row["open_items"] == row["open_retrievable"] + row["open_needing_a_person"]
    assert row["open_retrievable"] >= 1
    assert row["open_needing_a_person"] >= 1
    # The queue names the gap it would chase first, and prefers one a query could close.
    assert row["blocking_criterion_id"] == "INC-03"


def test_the_bundle_is_written_as_utf8_with_newline_endings(tmp_path: Path) -> None:
    """Two machines regenerating the same run must produce the same bytes.

    Text mode would translate "\\n" to "\\r\\n" on Windows, so a bundle rebuilt there would show up
    as a diff on every line without a single value having changed.
    """
    trial = a_trial()
    patient = a_patient("open-1", born=date(1970, 3, 2), hba1c=8.1)
    write_ui_bundle(
        [ScreeningRecord(screening=a_screening(trial, patient), patient=patient, trial_title="t")],
        root=tmp_path,
    )

    raw = (tmp_path / "data" / "index.json").read_bytes()
    assert b"\r\n" not in raw
    assert raw.endswith(b"\n")


# ------------------------------------------------------------------------------------------------
# The demo bundle
#
# `caliper ui demo` is the only producer of a bundle in this repository, and it screens two cohorts:
# the corpus as it stands, and charts the answer key edited to put a value on the far side of a
# stated threshold. The export has no field for that distinction and `uicmd` writes one onto the
# bundle itself, so these tests are about the mark surviving — a viewer that let an edited chart
# pass for an observed one would be lying in the one place nobody would think to check.
# ------------------------------------------------------------------------------------------------


def test_the_demo_bundle_marks_every_constructed_screening_and_only_those(tmp_path: Path) -> None:
    result = CliRunner().invoke(uicmd.app, ["demo", "--root", str(tmp_path)])
    assert result.exit_code == 0, result.output

    index = json.loads((tmp_path / "data" / "index.json").read_text(encoding="utf-8"))
    corpus_ids = set(corpus.patient_ids())
    marked = [row for row in index["screenings"] if "constructed" in row]
    assert len(marked) == len(uicmd.constructed_charts(uicmd.CONSTRUCTED_NCT))

    for row in index["screenings"]:
        # An unmarked row must be a chart the corpus actually contains. Anything else would be a
        # constructed chart the interface would draw as an observed one.
        assert ("constructed" in row) is (row["patient_id"] not in corpus_ids)

    for row in marked:
        built = row["constructed"]
        assert built["kind"] == "constructed"
        assert built["base_patient_id"] in corpus_ids
        assert built["edits"], "a constructed chart has to say what was changed"
        # The queue reads the index and the packet reads the document; both have to carry it.
        document = json.loads(
            (tmp_path / "data" / f"{row['nct_id']}--{row['patient_id']}.json").read_text(
                encoding="utf-8"
            )
        )
        assert document["constructed"] == built


def test_the_demo_bundle_states_the_screening_date_it_departed_from(tmp_path: Path) -> None:
    result = CliRunner().invoke(uicmd.app, ["demo", "--root", str(tmp_path)])
    assert result.exit_code == 0, result.output

    demo = json.loads((tmp_path / "data" / "index.json").read_text(encoding="utf-8"))["demo"]
    assert demo["screened_on"] == uicmd.DEMO_SCREENING_DATE.isoformat()
    assert demo["screened_on"] != demo["corpus_screening_date"]
    # A date that differs from every other figure in the repository has to arrive with its reason,
    # or the two will disagree later with nobody able to say why.
    assert demo["corpus_screening_date"] in demo["screening_date_note"]
    assert "2026-05-03" in demo["screening_date_note"]


def test_a_constructed_chart_carries_the_value_the_answer_key_says_was_supplied() -> None:
    charts = {c.case.id: c for c in uicmd.constructed_charts(uicmd.CONSTRUCTED_NCT)}
    near_miss = charts["CK-008"]

    def egfr(patient: PatientIndex) -> list[float | None]:
        return [
            row.value
            for row in patient.evidence
            if row.kind == "observation"
            and any(code.system == "LOINC" and code.code == "33914-3" for code in row.codes)
        ]

    # The chart this case was built from has never carried a filtration rate, which is why the
    # case had to supply one rather than move one.
    assert egfr(corpus.load_patient(near_miss.case.patient_id)) == []
    assert egfr(near_miss.chart) == [24.0]
    assert near_miss.chart.patient_id != near_miss.case.patient_id
    assert any("33914-3" in edit for edit in near_miss.edits)


# ------------------------------------------------------------------------------------------------
# The questions the record was never going to answer
# ------------------------------------------------------------------------------------------------


def a_visit_screening() -> tuple[Screening, PatientIndex]:
    """The same open screening, with two criteria only the screening visit can settle."""
    trial = a_trial()
    criteria = CriteriaSet(
        nct_id=trial.criteria_set.nct_id,
        source_text=trial.criteria_set.source_text,
        criteria=[
            *trial.criteria_set.criteria,
            Criterion(
                id="INC-90",
                kind="inclusion",
                source_quote="Signed written informed consent",
                predicate=UnsupportedPredicate(reason="given at the visit", settlement="at_visit"),
            ),
            Criterion(
                id="EXC-90",
                kind="exclusion",
                source_quote="Planning to start an SGLT2 inhibitor",
                predicate=UnsupportedPredicate(reason="an intention", settlement="at_visit"),
            ),
        ],
    )
    patient = a_patient("visit-1", born=date(1970, 3, 2), hba1c=8.1)
    trial = dataclasses.replace(trial, criteria_set=criteria)
    return a_screening(trial, patient), patient


def test_the_visit_questions_are_exported_with_their_quotes_and_kind() -> None:
    screening, patient = a_visit_screening()
    payload = export_screening(screening, patient, TRIAL_TITLE)

    assert [item["criterion_id"] for item in payload["at_visit"]] == ["INC-90", "EXC-90"]
    assert payload["at_visit"][0]["quote"] == "Signed written informed consent"
    assert payload["at_visit"][1]["kind"] == "exclusion"


def test_an_exclusion_left_to_the_visit_is_flagged_as_one_that_can_still_exclude() -> None:
    screening, patient = a_visit_screening()
    payload = export_screening(screening, patient, TRIAL_TITLE)

    assert payload["at_visit"][0]["can_still_exclude"] is False
    assert payload["at_visit"][1]["can_still_exclude"] is True


def test_a_screening_with_no_visit_questions_exports_an_empty_list() -> None:
    screening, patient = an_open_screening()

    assert export_screening(screening, patient, TRIAL_TITLE)["at_visit"] == []


def test_the_queue_entry_counts_them_so_a_coordinator_can_sort_on_it() -> None:
    screening, patient = a_visit_screening()
    payload = export_screening(screening, patient, TRIAL_TITLE)

    assert _screening_entry(payload)["at_visit"] == 2


def test_the_trial_counts_separate_the_two_kinds_of_unformalisable() -> None:
    """Both are `unsupported`; only one of them holds a verdict open.

    The interface says in a cohort banner why nothing came back eligible, and a count that lumps a
    consent line in with a category the protocol never enumerated makes that sentence wrong: it
    would claim a criterion blocks every chart when the screening deliberately lets it pass.
    """
    trial = a_trial()
    criteria = CriteriaSet(
        nct_id=trial.criteria_set.nct_id,
        source_text=trial.criteria_set.source_text,
        criteria=[
            *trial.criteria_set.criteria,
            Criterion(
                id="INC-90",
                kind="inclusion",
                source_quote="Signed written informed consent",
                predicate=UnsupportedPredicate(reason="given at the visit", settlement="at_visit"),
            ),
        ],
    )
    payload = export_trial(dataclasses.replace(trial, criteria_set=criteria), TRIAL_TITLE)

    counts = payload["counts"]
    assert counts["unsupported"] == counts["unsupported_blocking"] + counts["unsupported_at_visit"]
    assert counts["unsupported_at_visit"] == 1


def test_a_criterion_says_which_kind_of_unanswerable_it_is() -> None:
    trial = a_trial()
    criteria = CriteriaSet(
        nct_id=trial.criteria_set.nct_id,
        source_text=trial.criteria_set.source_text,
        criteria=[
            Criterion(
                id="INC-90",
                kind="inclusion",
                source_quote="Signed written informed consent",
                predicate=UnsupportedPredicate(reason="given at the visit", settlement="at_visit"),
            ),
        ],
    )
    payload = export_trial(dataclasses.replace(trial, criteria_set=criteria), TRIAL_TITLE)

    assert payload["criteria"][0]["settlement"] == "at_visit"


def test_the_index_carries_the_split_the_cohort_banner_reads() -> None:
    """The banner explains why nothing is eligible, and it reads these two numbers, not the sum."""
    trial = a_trial()
    payload = export_trial(trial, TRIAL_TITLE)
    entry = _trial_entry(payload)

    assert entry["unsupported_blocking"] + entry["unsupported_at_visit"] == entry["unsupported"]
