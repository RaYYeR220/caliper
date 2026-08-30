# Corrections to the answer key, version 1 to version 2

**These corrections were made after seeing a scored run, and after seeing which cases the system
under test disagreed with.** That is the circumstance in which a correction is least trustworthy,
so this document states what was changed, what evidence forced it, and what rule bounded it, in
enough detail that a reader can disagree with any of it line by line.

## The run

The corrections follow the first full evaluation, recorded in `eval/results/`:

| | |
|---|---|
| finished | `2026-08-30T08:30:46Z` (`eval/results/run.json`) |
| key scored | version 1, digest `42b74a00ab98ffa9d7a4c2bb366707a83fc10e65a7e30b73315a81f5c145d975` |
| arms | 10, over 51 cases each |
| cost | $21.67 |
| headline | the `caliper` arm answered 23 of 51 correctly, 45.1%, with 0 unsafe errors |

Version 1 is kept unchanged as `eval/answer_key.v1.json`, with its own sidecar carrying that same
digest. Version 2 is `eval/answer_key.json`, digest
`2c411896ee836f16b790b63b38f017f24e48dd33ab4d5e03ec25b108efc5f11c`. Both ship, and both are scored.

## The rule that was applied

> **A label was changed only where the committed chart refutes it. A label the system merely
> disagreed with was left alone.**

Twenty-eight of the 51 cases were disagreements in that run. Twelve outcomes changed. The other
sixteen disagreements are untouched, and remain disagreements.

Every change below is a consequence of one omission in the annotation protocol: it never asked
whether the patient was alive. No criterion change was made. No criterion verdict was reversed.

## The independent check

`scripts/build_answer_key.py` now carries a refutation pass. For every criterion label of `met` in
the key, it tries to contradict the label against the raw committed FHIR — it opens
`data/patients/<id>.json` and reads the resources itself, using neither `caliper.record`,
`caliper.evaluate` nor `PatientIndex`, because a key validated with the same matching code the key
is used to score would only ever agree with it.

What a `met` label asserts, expressed as a fact that can be looked for in a bundle, is
pre-registered in `eval/annotation/refutation.json`: 29 probes, one for every criterion that carries
a `met` label anywhere in the key. Three of them are declared unrefutable, with the reason —
"high cardiovascular risk" is a phrase the registry never defines, and a probe for it would be an
opinion about cardiology rather than a reading of a chart.

The probes are deliberately weaker than the annotation protocol. They ignore recency, ignore which
result is the most recent, and ignore the mutual-consistency rule of `protocol.md` section 5. A
probe therefore cannot dispute a judgement call; it can only catch a label that nothing on the
chart supports. The pass flags and does not fix: the build fails while any flag is unanswered.

It classifies each flag as one of two things:

- **refuted** — neither the committed bundle nor the case's own published edits carry anything that
  could support the label. This is an error in the key.
- **supplied** — the committed bundle does not carry it and one of the case's recorded
  perturbations does. This is the definition of a constructed case, not an error, and the build
  additionally fails if such a label is not one the case declared it was closing.

**Result on the corrected key: 64 `met` labels checked, 0 refuted, 18 supplied.** The 18 are
listed and discussed under error class 2 below.

---

## Error class 1: vital status was never part of the annotation protocol

`protocol.md` decomposed 153 criteria and said how to read absence, recency, units and negation. It
never asked whether the patient was alive on the screening date, because no protocol writes "the
patient must be alive" and nothing in a criterion decomposition can carry a fact no criterion
states.

Five of the fourteen patients in the key are recorded dead before 2026-06-01, in
`Patient.deceasedDateTime` in the committed bundles:

| patient | `deceasedDateTime` | before screening by | cases in the key |
|---|---|---:|---:|
| `1be83f06` | `2026-05-03T13:57:29+00:00` | 29 days | 10 |
| `2211f478` | `2016-06-03T17:41:28+00:00` | 9 years | 4 |
| `8d91c36a` | `2015-09-24T19:56:57+00:00` | 10 years | 2 |
| `fb56f051` | `1991-06-06T17:50:38+00:00` | 35 years | 2 |
| `30889246` | `1961-08-23T10:39:49+00:00` | 64 years | 2 |
| | | **total** | **20** |

Version 1 labelled 11 of those 20 `needs_review` and one `eligible`. A patient who died four weeks
before the screening date is not someone a coordinator should look at again, and is not enrollable;
they are ineligible, and no criterion needs evaluating to know it. `caliper.screen` short-circuits
on `PatientIndex.died_before(as_of)` and reports no criterion table at all. The key now derives the
same way, through the same precedence, in `build_answer_key.derive`.

### The twelve outcome changes

| case | patient | trial | v1 outcome | v2 outcome | what refutes v1 |
|---|---|---|---|---|---|
| `AK-001` | `1be83f06` | NCT01131676 | `needs_review` | `ineligible` | death recorded 2026-05-03 |
| `AK-004` | `2211f478` | NCT01131676 | `needs_review` | `ineligible` | death recorded 2016-06-03 |
| `AK-005` | `30889246` | NCT01131676 | `needs_review` | `ineligible` | death recorded 1961-08-23 |
| `AK-008` | `2211f478` | NCT02545049 | `needs_review` | `ineligible` | death recorded 2016-06-03 |
| `AK-010` | `8d91c36a` | NCT03036124 | `needs_review` | `ineligible` | death recorded 2015-09-24 |
| `AK-011` | `fb56f051` | NCT03036124 | `needs_review` | `ineligible` | death recorded 1991-06-06 |
| `AK-015` | `2211f478` | NCT03315143 | `needs_review` | `ineligible` | death recorded 2016-06-03 |
| `AK-019` | `30889246` | NCT03315143 | `needs_review` | `ineligible` | death recorded 1961-08-23 |
| `AK-023` | `8d91c36a` | NCT03819153 | `needs_review` | `ineligible` | death recorded 2015-09-24 |
| `AK-031` | `fb56f051` | NCT06717698 | `needs_review` | `ineligible` | death recorded 1991-06-06 |
| `CK-001` | `1be83f06` | NCT03315143 | **`eligible`** | `ineligible` | death recorded 2026-05-03 |
| `CK-003` | `1be83f06` | NCT03315143 | `needs_review` | `ineligible` | death recorded 2026-05-03 |

`CK-001` was one of version 1's seven eligible cases. It was constructed on `1be83f06`, the only
patient in the corpus with a genuine type 2 diabetes diagnosis and an HbA1c above the trial's floor,
and it was the only eligible case in the key that did not rest on a supplied diagnosis. Losing it is
the most expensive single consequence of this correction, and it is unavoidable: the patient died
four weeks before the screening date.

### The eight cases whose outcome did not change, but whose derivation did

`AK-006`, `AK-014`, `AK-020`, `AK-024`, `AK-026`, `AK-027`, `AK-033` and `CK-002` were already
`ineligible`. They are now ineligible for a different and prior reason, and they no longer carry a
criterion table, because none was evaluated.

### The criterion labels that were withdrawn

Across all 20 cases, **264 criterion labels were withdrawn** — 144 `unknown`, 82 `not_met`, 38
`met`. They were not reversed; they were removed, because the key should not assert per-criterion
verdicts for a screening that evaluated no criteria. The withdrawn labels remain readable in
`eval/answer_key.v1.json`, and the annotation passes that produced them are untouched in
`pass1.json` and `pass2.json`.

This is a real cost, and it falls unevenly. `AK-007`'s potassium of exactly 4.80 mmol/L against a
`<=4.8 mmol/L` bound survives, because that patient is alive. `CK-002`'s eGFR of 61 against a
ceiling of 60 does not: the case is decided before the eGFR is read, so the key retains a
`threshold_edge` trap on a case that can no longer probe a threshold. The traps were left as
written rather than being downgraded, because they record what each pair was *selected* to probe,
and rewriting them would erase the fact that this correction cost the key four threshold and unit
probes. `protocol.md` section 12 lists them.

### Why this was not a change made to flatter the system

It moves the score in the system's favour, which is exactly the shape of a correction a reader
should distrust. Three things bound it:

1. **The fact is in the committed data and is checkable without the system.**
   `Patient.deceasedDateTime` is in `data/patients/*.json`, whose digests are in `data/SHA256SUMS`.
   The build reads it directly, not through `PatientIndex`.
2. **The rule was not tuned.** It has one form — dead before the screening date means ineligible —
   and it applies to every case, changing 12 and leaving 39 alone. There is no version of it that
   could have been made to change fewer or different cases.
3. **It does not flatter selectively.** Rescoring the *same recorded decisions* from the run above
   against both keys:

   | arm | v1 | v2 | |
   |---|---:|---:|---:|
   | `caliper-no-critic` | 54.9% | 78.4% | +12 |
   | `caliper` | 45.1% | 68.6% | +12 |
   | `caliper-whole-protocol` | 45.1% | 68.6% | +12 |
   | `caliper-no-resolver` | 45.1% | 68.6% | +12 |
   | `caliper-closed-world` | 45.1% | 68.6% | +12 |
   | `caliper-open-world` | 37.3% | 60.8% | +12 |
   | `single_prompt` | 58.8% | 70.6% | +6 |
   | `random` | 31.4% | 29.4% | −1 |
   | `always_needs_review` | 29.4% | 7.8% | −11 |
   | `always_eligible` | 13.7% | 11.8% | −1 |
   | *always ineligible (not run)* | *56.9%* | *80.4%* | *+12* |

   The last row is the one that matters. **Version 2 is a more degenerate key than version 1**: 41
   of its 51 cases are `ineligible`, so a system that says `ineligible` to everything now beats every
   real arm on accuracy. Accuracy against version 2 is worth less than accuracy against version 1,
   and the corrected key has to be read through the selective-risk and coverage curves rather than
   through its headline. That is a cost of the correction and it is not offset by the fact that the
   correction is right.

   The 15 constructed cases in that run were screened against **unedited** charts, because the
   runner did not replay perturbations; see error class 2. Their contribution to every number in
   that table is not meaningful until the runner is wired to `caliper.answerkey.rebuild_patient`.
   The clean comparison is the annotated half alone: the `caliper` arm scored 19 of 36 against
   version 1 and 29 of 36 against version 2.

---

## Error class 2: criterion labels contradicted by the chart

**The refutation pass found none, and I am reporting that rather than making changes to match the
brief.** The brief for this work stated that the seven constructed `eligible` cases rest on
`NCT03315143-I1`, "Type 2 Diabetes Mellitus with glycosylated hemoglobin (HbA1c) >=7%", being `met`
on patients whose charts record prediabetes and an HbA1c near 6.1%. The chart facts in that
statement are correct and the check reproduces them independently. The inference does not hold, for
one reason: the annotated cases on those patients label that criterion `not_met`, and the
constructed cases label it `met` only after a recorded edit puts a diabetes diagnosis and an HbA1c
on the chart.

| patient | condition on the committed chart | latest HbA1c | annotated case | its `NCT03315143-I1` label |
|---|---|---|---|---|
| `6c4283c9` | Prediabetes (finding), SNOMED 714628002 | 6.21% on 2025-12-06 | `AK-017` | `not_met` |
| `cc3eac4a` | Prediabetes (finding), SNOMED 714628002 | 6.08% on 2026-02-09 | `AK-035` | `not_met` |
| `35f80d0e` | Prediabetes (finding), SNOMED 714628002 | 6.11% on 2026-02-01 | `AK-034` | `not_met` |
| `8c5b83b2` | Prediabetes (finding), SNOMED 714628002 | 6.27% on 2025-11-24 | `AK-018` | `not_met` |
| `f870c432` | Prediabetes (finding), SNOMED 714628002 | 6.02% on 2025-09-24 | `AK-016` | `not_met` |
| `fd0d7b3a` | Prediabetes (finding), SNOMED 714628002 | 6.21% on 2025-08-26 | `AK-036` | `not_met` |
| `1be83f06` | **Diabetes mellitus type 2 (disorder), SNOMED 44054006**, active, onset 2025-06-03 | **7.58%** on 2025-06-03 | `AK-014` | `met` |

The one annotated `met` label on that criterion is `AK-014`, and the last row is why: that patient
does have type 2 diabetes and an HbA1c of 7.58%. No annotated label anywhere in the key asserts
diabetes on a prediabetic chart.

### What the check did find: 18 `met` labels supplied by a recorded edit

All 18 are on constructed cases, all on `NCT03315143`, and every one is declared in that case's
`closes` list in `constructed.json`:

| criterion | cases | what the committed bundle says |
|---|---|---|
| `NCT03315143-I1` | `CK-004`, `CK-006`, `CK-007`, `CK-008`, `CK-009`, `CK-010`, `CK-011`, `CK-012`, `CK-013`, `CK-014`, `CK-015` | no condition coded SNOMED 44054006; the chart records Prediabetes (SNOMED 714628002), and no HbA1c reaches 7.0% |
| `NCT03315143-I2` | `CK-004`, `CK-005` | six eGFR results, the most recent 84.289 mL/min on 2025-09-25, none inside 25–60 |
| `NCT03315143-I2` | `CK-007`, `CK-010`, `CK-013`, `CK-014`, `CK-015` | no result coded LOINC 33914-3 has ever been recorded |

**These were not treated as errors, and none was changed.** The reasoning:

- The label describes the chart the case is about, which is the base chart plus the edits the case
  publishes in full, not the base chart. That is what `constructed` provenance means, and
  `protocol.md` section 11 pre-registered the method before any of these cases was built.
- The edit is disclosed in the key itself, in the `perturbations` field, in the form of a before-and-
  after snapshot of every row that moved. A reader can replay it and check.
- Nothing is hidden by it: the build now names all 18 on every run, and refuses to build if a
  constructed case carries such a label without declaring the edit that supplies it.

**But the concern behind the question is real, and it is now the largest known weakness of the key.**
After the vital-status correction, all six remaining `eligible` cases are constructed, all six are
on one trial, and every one of them rests on a type 2 diabetes diagnosis supplied to a patient whose
real chart says prediabetes. Version 1 had one eligible case that did not — `CK-001`, on the only
genuinely diabetic patient — and vital status has taken it. **The key can no longer demonstrate
eligible-detection on any chart whose diabetes was not put there by us.** Section 12 of
`protocol.md` states this as a limitation rather than burying it, and nothing in the corpus fixes
it: `1be83f06` is the only patient with a real type 2 diabetes diagnosis, and he is dead.

Dropping the six would leave the key with no `eligible` case at all, restoring the exact degenerate
measurement the constructed cases were built to remove. They are therefore kept, flagged, and the
decision is deferred: the choice between six disclosed-but-supplied eligible cases and none is a
judgement about what the evaluation is for, not a correction the chart forces.

### The defect the 45% run actually exposed

`caliper.evalrun.run_arm` screens `load_patient(case.patient_id)`: the **base** chart, with no
perturbations replayed. Every one of the 15 constructed cases in that run was therefore screened
against a chart that is not the chart its labels describe, and `run.json` records `"replayed":
false`. The six eligible cases were presented to every arm as prediabetic patients with no eGFR and
scored against labels written for diabetic patients with an eGFR of 34–52.

That is a scoring defect, not a key error, and it is the direct cause of the disagreement on those
cases. The fix is `caliper.answerkey.rebuild_patient`, added by this work as the single
implementation of perturbation replay; the runner is not wired to it here.

---

## What changed, in full

Everything below is the complete difference between `answer_key.v1.json` and `answer_key.json`.

| | v1 | v2 |
|---|---:|---:|
| cases | 51 | 51 |
| annotated / constructed | 36 / 15 | 36 / 15 |
| `ineligible` | 29 | 41 |
| `needs_review` | 15 | 4 |
| `eligible` | 7 | 6 |
| cases with a criterion table | 51 | 31 |
| criterion labels | 566 | 302 |

- **12 outcomes changed**, all listed above, all on patients recorded dead before screening.
- **264 criterion labels withdrawn**, on the 20 cases those five patients account for.
- **0 criterion verdicts reversed.** Not one `met` became `not_met`, or the reverse, anywhere.
- **0 cases added or dropped.**
- **0 traps changed.** The vital-status rule introduces no trap of its own; each case keeps the trap
  it was selected for.
- **0 changes on any case whose patient is alive.** Verifiable by diffing the two files.
- `cases.json` version `1.0.0` → `2.0.0`, and its `key_note` rewritten to describe version 2.
- `eval/annotation/refutation.json` added: the pre-registered probes and the empty accepted-flag
  list.

## Reproducing this

```
python scripts/build_answer_key.py --dry-run   # rebuilds, runs the refutation pass, prints the tables
python -c "from caliper.answerkey import verify_frozen as v; print(v('eval/answer_key.json'), v('eval/answer_key.v1.json'))"
```

The correction table above is the diff between the two frozen keys, not a record kept by hand: it
can be recomputed from `eval/answer_key.v1.json` and `eval/answer_key.json` alone.
