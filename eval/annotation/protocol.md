# Annotation protocol for the Caliper answer key

This document describes how `eval/answer_key.json` was produced, in enough detail that someone
with this repository and no other information could repeat the exercise and get the same labels.

It was written before annotation began. Seven things were added afterwards, and each is marked where
it appears: the counts in section 9, the note on `family_history` in section 7, three clarifications
forced by the adjudication — two in section 4 and one in section 5 — each labelled *sharpened at
adjudication*, section 11, which describes the constructed cases added after the first build,
section 12, a methods amendment written after the first *scored* run, and section 13, which
compares this document's scope decisions against the compiler's. Nothing that was in the document
before annotation was removed or reworded.

**Sections 9 and 11 describe version 1 of the key, which is kept unchanged at
`eval/answer_key.v1.json`. Section 12 says what changed in version 2 and carries the corrected
counts.**

Everything here is an annotation of synthetic patient records by language models against real
registry text. **No clinician reviewed these labels.** Section 8 says what that costs.

---

## 1. What is being labelled

The unit of annotation is a *criterion*, not a case.

For each patient-and-trial pair, the annotator reads the trial's eligibility criteria as
ClinicalTrials.gov published them — the `eligibilityCriteria` free-text field of
`data/trials/<NCT>.json` — and assigns each in-scope criterion one of three verdicts against the
patient's chart summary in `eval/charts/<patient_id>.md`:

| Verdict | Meaning |
|---|---|
| `met` | The chart supports the criterion being satisfied. For an exclusion, this means the exclusion **fires**. |
| `not_met` | The chart supports the criterion not being satisfied. For an exclusion, this means the exclusion does **not** fire. |
| `unknown` | The chart does not contain what is needed to decide, and the annotator says specifically what is missing. |

The case-level outcome is then **derived**, never guessed, by applying the rollup rule implemented
in `caliper.logic.roll_up`:

1. If any inclusion is `not_met`, **or** any exclusion is `met`, the case is `ineligible`.
2. Otherwise, if any criterion is `unknown`, the case is `needs_review`.
3. Otherwise the case is `eligible`.

The derivation is done by `scripts/build_answer_key.py`, which imports `roll_up` directly rather
than reimplementing it, so the key cannot drift from the logic it claims to follow. Each case's
`rationale` names the criterion or criteria that drove the outcome.

The reason for annotating this way is that a case-level label formed by reading everything at once
is exactly the failure mode the evaluation exists to detect: a fluent, confident judgement about a
patient whose chart does not support one. A key built that way would agree with the baseline
wherever the baseline is wrong for that reason, and the evaluation would be measuring nothing.

The annotators worked from the committed chart summaries in `eval/charts/`, which are the artifact
`caliper.chart.summarise` produces and are byte-deterministic. That is deliberate: the exact text
an annotator read is committed next to the labels it produced. They also read the raw trial JSON.
**No annotator saw any compiled criterion, any intermediate representation, or any system output
for any pair.** Doing so would have made the key circular.

---

## 2. Choosing the pairs

36 annotated pairs over 8 trials and 14 patients, listed in `pairs.json`. Thirty-three were fixed
before annotation began; AK-034, AK-035 and AK-036 were added after the first build to widen the
base for the constructed cases of section 11, and were put through both passes and the adjudication
under this same protocol before any perturbation was written. Trials were chosen first, for
range: six cardiometabolic (`NCT01131676`, `NCT02545049`, `NCT03036124`, `NCT03315143`,
`NCT03819153`, `NCT06717698`), one respiratory (`NCT07252908`) and one oncology
(`NCT05748834`). Two of the ten committed trials were not used at all: `NCT05763121` and
`NCT06547333`, both of which are long enough (30 and 33 criteria after scoping) that annotating
them twice would have cost more than the range they added.

Patients were then chosen against those trials to produce a spread that discriminates rather than
flatters:

- **Charts that answer the question.** `1be83f06` has type 2 diabetes, a recent HbA1c and a recent
  UACR, so the diabetes trials get real values to compare against.
- **Charts that are silent.** `35f80d0e`, `23da8e71`, `fd0d7b3a`, `6c4283c9`, `cc3eac4a` and
  `8c5b83b2` have creatinine but no eGFR result and no UACR, which is what most of the kidney
  criteria turn on.
- **Charts that are stale.** `2211f478` (last encounter 2016-06-13), `8d91c36a` (2015-09-26),
  `fb56f051` (1991-06-08) and `30889246` (1961-08-25) carry the right analytes at the wrong dates.
  Ten of the 36 annotated pairs are against one of those four charts.
- **Charts where a unit or a formula does not match the protocol.** `8d91c36a`, `fb56f051` and
  `f870c432` report eGFR by the MDRD formula in bare `mL/min`, where three of the trials ask for
  CKD-EPI in `mL/min/1.73 m^2`; `cbd1dd48` reports FEV1/FVC as `66.607 %` where `NCT07252908`
  writes the bound as a ratio `< 0.7`; `NCT07252908` writes its glucose bound in `mmol/L` where
  every chart records glucose in `mg/dL`.
- **A demographic floor.** `a6d0791e` is two years old and `cbd1dd48` is 37, against trials whose
  age windows are `>=18` and `40 to 80`.
- **The oncology trial**, against three patients, none of whom has any oncological history. It is
  in the key to show a limit honestly, not to be scored well; see section 7.

---

## 3. Which criteria are annotated, and which are not

The decomposition is fixed in `criteria.json`, one entry per bullet or numbered item **as the
registry wrote it** — where the registry nested sub-bullets under one item, that item is one
criterion. Sub-bullets are joined with `; ` in the recorded quote. Quotes reproduce the registry
field with its Markdown escaping removed (`\>=` becomes `>=`), and nothing else.

Every criterion in every used trial appears in `criteria.json`, including the ones that are not
annotated, each with the reason it is not. Nothing is quietly dropped: of 153 criteria across the
eight trials, 130 are in scope and 23 are not.

| Trial | Criteria | In scope |
|---|---:|---:|
| NCT01131676 | 22 | 18 |
| NCT02545049 | 11 | 11 |
| NCT03036124 | 18 | 17 |
| NCT03315143 | 8 | 5 |
| NCT03819153 | 12 | 11 |
| NCT05748834 | 25 | 19 |
| NCT06717698 | 15 | 15 |
| NCT07252908 | 42 | 34 |

The 36 annotated pairs therefore carry 491 criterion labels per pass.

A criterion is **in scope** when it asserts something about the patient that is true or false at
the screening date and that a clinical record could in principle carry: a diagnosis, a medication,
a procedure, a dated event, a demographic fact, a laboratory or vital-sign value, an imaging
measurement, or an instrument score.

A criterion is **out of scope** in exactly three cases:

1. **Study process.** Consent, willingness or ability to comply with visits, ability to perform a
   study procedure, being a site employee. *(e.g. `NCT01131676-I6`, "Signed and dated informed
   consent".)*
2. **Investigator discretion.** A catch-all whose content is the investigator's opinion rather than
   a fact. *(e.g. `NCT01131676-E14`, "Any other clinical condition that would jeopardize patients
   safety".)*
3. **Future intent.** A statement about what the patient or the site plans to do, which no record
   of the past can settle. *(e.g. `NCT03315143-E4`, "Planning to start a sodium-glucose linked
   transporter-2 (SGLT2) inhibitor during the study".)* Where a criterion mixes a historical clause
   with an intent clause — `NCT03036124-E6`, revascularisation "within 12 weeks prior to enrolment
   **or planned** to undergo any of these operations after randomization" — the criterion stays in
   scope and is judged on the historical clause alone.

Criteria that need a measurement the protocol schedules at the screening visit — a screening brain
MRI, an ECHO, spirometry at Visit 1, ECOG, NYHA class, mMRC, ACQ-6 — are **kept in scope**. They
are the honest `unknown`s, and putting them out of scope would have flattered every case that
depends on them.

This scoping is the largest judgement call in the key. It means that `eligible`, had any case
reached it, would mean *eligible on the chart-determinable criteria* and not *enrollable*. Any
system scored against this key is being asked the same restricted question, so the comparison is
fair; but the restriction is real and it is stated here rather than in a footnote.

---

## 4. How absence is read

This is the rule that decides most `unknown`s, and it distinguishes two kinds of criterion.

**Criteria over conditions, medications, procedures and events.** Absence from the chart is read as
absence in the patient — the criterion resolves to `not_met` — **only where the chart documents
encounters covering the window the criterion asks about.** This matches the default policy in
`caliper.evaluate`, which the README describes as accepting absence only where an encounter
documents the relevant window. So for `1be83f06`, whose encounters run to 2026-05-12, "Medical
history of cancer ... within the last 5 years" is `not_met`: there are annual encounters through
the whole window and no neoplasm in any of them. For `30889246`, whose last encounter is
1961-08-25, the same criterion is `unknown`: nothing has been written down about this patient for
sixty-five years, and silence over an undocumented window is not evidence.

*Sharpened at adjudication (see `disagreements.md`, theme 1).* "Covering the window" is a property
of the chart, not of each window separately: **a chart whose most recent encounter is within twelve
months of the screening date is current, and on a current chart the absence of a condition,
medication, procedure or event is read as absence for any window.** A chart whose most recent
encounter is older than twelve months is not current, and absence resolves nothing for any window
reaching past that encounter. The bound splits this corpus cleanly — ten current charts, four stale
(`2211f478` 2016, `8d91c36a` 2015, `fb56f051` 1991, `30889246` 1961) — and the passes differed on ten
labels before it was written down.

*Sharpened at adjudication (theme 3).* The condition-versus-measurement test applies to what the
criterion asserts, not to what a site would do to check it: "second or third degree heart block" is
a diagnosis even though a site would order an ECG. And **a criterion whose subject matter is entailed
by a condition the chart resolves as absent resolves too** — a patient with no cancer has no RECIST
measurable disease and no brain metastases. The entailment runs one way only: an inclusion that
demands a positive finding from a study procedure, such as the CNS classification made from a
screening contrast brain MRI, stays `unknown`.

**This is an assumption, not a fact.** A chart with encounters covering a window can still omit a
diagnosis made elsewhere, and the corpus is synthetic, so the assumption is not even testable here.
It is adopted because it is the policy the system defaults to and because the alternative — reading
every absent condition as `unknown` — would make every case `needs_review` and the key useless.
`caliper` implements open-world and closed-world alternatives and reports them side by side; a key
built under either of those would differ from this one, and the size of that difference is a
property of the corpus, not of the annotation.

**Criteria over measured quantities.** Absence of a measurement is **never** read as a normal
result. If a trial bounds ALT and the chart has never carried an ALT, the criterion is `unknown`,
not `not_met`. A test that was not done is not a test that came back normal. This single rule
accounts for most of the `unknown` labels in the key, and it is why `NCT01131676` produces
`needs_review` for every patient who is not disqualified outright: no chart in the corpus carries a
liver panel and a recent one at the same time.

Where a chart records a condition but not the attribute the criterion turns on — `Anemia
(disorder)` against an exclusion for "disorders causing haemolysis" — the criterion is `unknown`.
Presence is documented; the qualifying attribute is not.

---

## 5. How recency is read

Where a criterion states a window ("within 12 weeks prior to screening"), the window is applied
literally against the screening date, 2026-06-01.

Where a criterion states no window:

- A **diagnosis** does not expire. An active chronic condition recorded in 1989 is still `met` in
  2026 unless the chart marks it resolved or inactive. The chart summary separates active from
  resolved conditions, and the annotators used that separation.
- A **measured quantity** — a laboratory result, a vital sign, an imaging measurement, a score —
  is usable only if the most recent value on file was taken **within 24 months of the screening
  date**. Older than that, the criterion is `unknown` and the reason states the value, its date,
  and how far outside the window it falls.

The 24-month bound is ours; the protocols do not state one. It was chosen before annotation and
applied uniformly. It is the rule most likely to move labels if a reader disagrees with it: ten of
the 36 annotated pairs are against charts whose most recent measurement predates screening by more
than two years, and six of those are `needs_review` for that reason alone and would become decided outcomes
if the bound were removed. Cases where it is decisive are marked `trap: temporal`.

*Sharpened at adjudication (see `disagreements.md`, theme 6).* Recency is not the only way a
measurement can fail to be usable. **Where two results recorded on the same date are mutually
inconsistent under the equation the criterion names, the criterion is `unknown`.** `f870c432` is
recorded on 2025-09-25 with an MDRD eGFR of 84.289 mL/min and a serum creatinine of 2.578 mg/dL,
which cannot both be true; choosing between them would be picking rather than reading.

---

## 6. Writing a reason

Every label carries a reason. For `met` and `not_met`, the reason cites the datum: the value, its
unit and its date, or the condition and the date it was recorded.

For `unknown`, the reason must name the missing datum specifically enough that a coordinator could
go and get it. "Not enough information" is not a reason. "No serum creatinine result after
2016-02-15, and the criterion requires an eGFR at the screening visit" is. This is the same
standard the system's own resolution hints are held to, and holding the key to it is the only way
to tell whether a hint is right.

---

## 7. Traps

Each case carries one `trap` label from the vocabulary in `caliper.answerkey.TRAPS`. It names the
failure mode the pair was **selected to probe at the criterion level**. It is not necessarily the
criterion that decides the rollup, and where the two differ the case's `rationale` says so
explicitly — `AK-007` is the clearest example: it is `ineligible` because the patient has no type 2
diabetes diagnosis, but it is in the key because his serum potassium is exactly 4.80 mmol/L against
a `<=4.8 mmol/L` bound, and a system that reads an inclusive bound as exclusive flips that label
without changing the outcome.

`family_history` is not used. There is no family history in this corpus — Synthea's
`FamilyMemberHistory` resources are not carried by the trimmed bundles — and none of the eight
trials states a family-history criterion, so a `family_history` case would have to be invented. It
was not.

---

## 8. Two passes, and what they are worth

Every pair was annotated twice.

- **Pass 1** (`pass1.json`, annotator `llm-pass-1`) was produced by the model that assembled the
  key, reading each chart and each protocol pair by pair.
- **Pass 2** (`pass2.json`, annotator `llm-pass-2`) was produced by separate agent instances with
  **no access to pass 1, to the pair-level expectations, or to any of the reasoning behind them**.
  Each was given this protocol, `criteria.json`, and the pair list, and read the charts and trial
  JSON itself from the repository. Independence here is structural — a fresh context per pass —
  rather than merely procedural.

The two passes agreed on 455 of 491 criterion labels, giving **Cohen's kappa 0.879** (95% interval
0.841 to 0.917). All 36 disagreements are listed criterion by criterion in `disagreements.md` with
the adjudication and the reason for it, and the contingency table and arithmetic are in `kappa.md`.
Fifteen adjudications upheld pass 1, twenty-one upheld pass 2, and exactly one changed a case-level
outcome. The constructed cases of section 11 carry no annotator labels of their own and are not part
of this statistic. Adjudication was done by the maintainer, and `adjudicated_by` on every case says
`maintainer`.

Every disagreement ran the same way — pass 1 abstained or pass 1 was the stricter of the two, never
the reverse — which is a more useful finding than the coefficient and is set out at the end of
`kappa.md`.

**What this is not.** Both passes are language models. n2c2 2018 Track 1 and TREC Clinical Trials
established dual *expert* annotation as the standard for cohort selection, and this is not that.
Agreement between two language-model passes measures whether the protocol in this document is
specific enough to be applied consistently. It does not measure whether the labels are clinically
correct, and a high kappa here would not be evidence that they are. The honest claim the key
supports is: *these are the labels this written protocol produces on this corpus, reproducibly, and
here is exactly where the protocol was ambiguous enough that two readings differed.*

The annotator names in the key — `llm-pass-1` and `llm-pass-2` — are written that way so that no
reader can mistake them for people.

---

## 9. What the key contains

51 cases: **36 annotated** and **15 constructed**. Every count in this document, in the key's own
`notes`, and in the summary `scripts/build_answer_key.py` prints is reported for the two provenances
separately, so a constructed case cannot be read as an observed one.

| Outcome | Annotated | Constructed | Total |
|---|---:|---:|---:|
| `ineligible` | 25 | 4 | 29 |
| `needs_review` | 11 | 4 | 15 |
| `eligible` | **0** | 7 | 7 |

### No patient in this corpus is eligible for any of these protocols

This is the key's central finding and it survived the addition of the constructed cases, which exist
precisely because of it. Not one of the 36 annotated pairs reaches `eligible`, and the reason is not
that these patients are sick in the wrong ways. It is that **every one of the eight protocols bounds
at least one quantity that no chart in this corpus carries at all**, and under section 4 a test not
done is `unknown` rather than normal, and `unknown` propagates.

| Trial | The quantity no chart carries |
|---|---|
| NCT01131676 | a liver panel (ALT, AST, alkaline phosphatase) on any patient who also has a recent chart; and the sub-type of a recorded "Anemia (disorder)" |
| NCT02545049 | a UACR on any patient with type 2 diabetes and an ACE inhibitor or ARB at a labelled maximum dose |
| NCT03036124 | an NYHA functional class, which no Synthea chart records |
| NCT03315143 | an eGFR on most charts — and this is the one trial where nothing else is missing |
| NCT03819153 | a UACR, and a fundus examination inside the 90-day window the criterion names |
| NCT05748834 | ECOG performance status, RECIST measurable disease, and a screening contrast brain MRI |
| NCT06717698 | a cystatin C-based eGFR; no cystatin C is measured anywhere in the corpus |
| NCT07252908 | mMRC dyspnoea grade, pack-years, and FEV1 percent-predicted |

That table is a fact about the data and about routine care, not about the screening logic, and it is
more interesting than any score computed on top of it. It is also the reason the eligible cases had
to be constructed rather than found: `NCT03315143` is the only trial in the set whose every in-scope
criterion can be closed with terminology the committed corpus already uses, so all 15 constructed
cases are on it. Section 11 says what was done and section 11's last paragraph says what that costs.

### What the key can and cannot measure

With seven eligible cases the key can now separate a system that finds eligible patients from one
that does not, and the degenerate baselines are all beaten:

- answering `needs_review` everywhere is wrong on 36 of 51 and finds nothing;
- answering `ineligible` everywhere is wrong on 22 of 51, and 7 of those errors are missed
  enrolments — the direction nobody ever audits;
- answering `eligible` everywhere is wrong on 44 of 51 and commits 44 unsafe errors.

What the key still cannot do is measure eligible-detection on a chart nobody edited. All seven
eligible cases are constructed, all seven are on one trial, and four of the seven were built by
supplying an observation that the patient's real chart never contained. A system could in principle
learn the shape of our perturbations rather than the shape of eligibility. The mitigation is that
the perturbations are published in full, in the key itself, so that anyone can check what was
supplied and re-derive the label.

Cases by trap:

| Trap | Annotated | Constructed | Total |
|---|---:|---:|---:|
| `none` | 17 | 7 | 24 |
| `missing_data` | 4 | 4 | 8 |
| `temporal` | 6 | 0 | 6 |
| `threshold_edge` | 1 | 4 | 5 |
| `unit` | 4 | 0 | 4 |
| `unsupported` | 3 | 0 | 3 |
| `negation` | 1 | 0 | 1 |
| `family_history` | 0 | 0 | 0 |

---

## 10. Files

| File | What it is |
|---|---|
| `protocol.md` | this document |
| `criteria.json` | the criterion decomposition and the scope decisions, fixed before annotation |
| `pairs.json` | the 36 annotated pairs |
| `cases.json` | per case, the trap it probes and the note that opens its rationale |
| `pass1.json` | pass 1 labels, one verdict and one reason per criterion per pair |
| `pass2.json` | pass 2 labels, produced independently |
| `adjudication.json` | every criterion where the passes differed, with the decision and why |
| `disagreements.md` | the same, in prose |
| `kappa.md` | Cohen's kappa, the contingency table, and the working |
| `constructed.json` | the 15 constructed cases: base pair, chart edits, and the criteria they close |
| `refutation.json` | *added at the amendment.* What a `met` label asserts, per criterion, as a fact that can be looked for in a raw bundle; plus the flags that were reviewed and accepted |
| `corrections.md` | *added at the amendment.* Every label that changed between key versions 1 and 2, with the chart value behind it |

`scripts/build_answer_key.py` reads all of these, derives each outcome, validates through
`caliper.answerkey.load_key`, and freezes the result. It refuses to build if either pass is
missing a criterion, if a disagreement is not decided in `adjudication.json`, if `adjudication.json`
decides a criterion the passes agreed on, if a constructed case overrides a criterion its base pair
had already satisfied, if any chart edit is not visible in the finished chart when read back, if a
criterion carries a `met` label with no probe declared for it, if the refutation pass contradicts a
`met` label that `refutation.json` does not answer for, or if a constructed case carries a `met`
label the committed chart does not support and does not declare the edit that supplies it.

---

## 11. Constructed cases

*Added after the first build. The 36 annotated pairs and their labels were complete and frozen
before any of this was written.*

Section 9 explains why the annotated half of the key contains no `eligible` case. That is an honest
finding and a broken measurement: with no eligible case, calling a patient eligible is never right,
"coverage at zero unsafe errors" degenerates, and a system that answers `ineligible` to everything
looks respectable. The constructed cases close that hole without anybody eyeballing a case.

**The method.** Take an annotated pair. Read its adjudicated criterion labels and find the criteria
that block `eligible` — an inclusion that is not `met`, or an exclusion that is. Apply a recorded
list of edits to the chart that supply exactly what those criteria ask for. Override only those
criteria, carrying every other label forward untouched. Then derive the outcome with the same
`caliper.logic.roll_up` used everywhere else. The label is not a judgement about the constructed
patient; it is the pre-registered rollup rule applied to human criterion labels plus a value chosen
to be plainly inside or plainly outside a stated band.

Three properties make this non-circular:

1. **Nothing about the system is consulted.** The edits are chosen from the registry text and the
   chart, exactly as the annotation was.
2. **The base labels are the annotated ones.** For a 5-criterion trial, an eligible constructed case
   carries 2 or 3 labels straight from the two passes and overrides the rest.
3. **The edits are verified against the finished chart.** `build_answer_key.py` applies every step
   and then reads each one back off the resulting `PatientIndex`; a step that silently did nothing
   is a build error, not a case.

**What was edited, and with what.** `caliper.perturb` supplies `shift_value`, `redact_analyte` and
`add_condition`, and those do most of the work. It has **no function that adds an observation**, and
this build was not permitted to add one to that module, so `add_observation` is implemented in
`scripts/build_answer_key.py` instead: it builds an `Evidence` row with `dataclasses.replace` and
records an equivalent `Perturbation`, so the case documents the change in the same form as every
other. Four of the 15 constructed cases use it. If `perturb.py` ever gains an observation helper,
that local function should be deleted in its favour.

Every code used is lifted verbatim from the committed corpus — SNOMED 44054006 and 414545008, LOINC
33914-3, 4548-4 and 38483-4 — so no terminology is invented. Values are placed comfortably inside or
outside the band except in the four `threshold_edge` cases, where the whole point is to sit one unit
the wrong side of a bound.

**The shape of the set.** Four base patients carry a full triple — eligible, ineligible by a hair,
and undecidable — on the same patient and trial, differing only in the supplied value:

| Patient | eligible | near miss | undecidable | The bound that separates them |
|---|---|---|---|---|
| `1be83f06` | CK-001 | CK-002 | CK-003 | eGFR 42 / 61 / removed, against 25-60 |
| `f870c432` | CK-004 | CK-005 | CK-006 | HbA1c 7.4% / 6.9% / eGFR removed, against 7% |
| `6c4283c9` | CK-007 | CK-008 | CK-009 | eGFR 45 / 24 / absent, against 25-60 |
| `8c5b83b2` | CK-010 | CK-011 | CK-012 | eGFR 52 / 61 / absent, against 25-60 |

CK-013, CK-014 and CK-015 are three further eligible cases on three more patients, added so that the
eligible group does not rest on four charts.

**What is wrong with this set, stated plainly.** All 15 are on one trial, `NCT03315143`. The brief
asked for at least three, and three is not reachable: section 9's table shows that every other trial
in the key needs at least one datum that cannot be supplied without inventing a LOINC or RxNorm code
this build cannot verify offline, or without asserting an investigator's opinion. Two near misses
were possible in principle on other trials but would have been decided by an unrelated criterion,
which teaches nothing. Widening the constructed set past one trial needs one of two decisions that
are not the annotator's to make: a small, verified terminology addition to the corpus (a cystatin C
eGFR, an NYHA class, a fundus finding, a maximum-dose ACE inhibitor product), or acceptance that
constructed eligibility is demonstrated on one trial only.

---

## 12. Methods amendment: vital status, and what the first scored run found

*Written after the first scored run of the whole evaluation, and after seeing which cases the system
under test disagreed with. Nothing above this line was reworded. Sections 9 and 11 continue to
describe key version 1, which is kept unchanged at `eval/answer_key.v1.json`.*

The first full run finished `2026-08-30T08:30:46Z` and cost $21.67. Scored against key version 1,
digest `42b74a00...`, the `caliper` arm answered 23 of 51 cases correctly, 45.1%, with 0 unsafe
errors. Investigating the 28 disagreements found that a substantial fraction of them were errors in
this protocol rather than in the system. That is the most useful thing the run produced, and it is
reported here rather than buried: an evaluation whose first result is a list of faults in its own
ground truth is working, but only if the list is published.

**The omission.** This protocol decomposed 153 criteria and stated how to read absence, recency,
units, negation and thresholds. It never asked whether the patient was alive. Nothing in a criterion
decomposition could have carried it: no protocol writes "the patient must be alive", so no criterion
states the fact, so no criterion label can express it.

Five of the fourteen patients in the key are recorded dead before the 2026-06-01 screening date, and
20 of the 51 cases are on them. Version 1 labelled 11 of those `needs_review` and one `eligible`.

### The rule, which precedes every criterion

> **A patient whose chart records a death on or before the screening date is `ineligible`. No
> criterion is evaluated, the case carries no criterion labels, and the case's `trap` stays as it
> was: the rule introduces no trap of its own.**

FHIR permits `deceasedBoolean` with no date; a chart that records a death without one is treated the
same way, since inventing a date would put one in front of a coordinator that nobody wrote down.

This is applied in `build_answer_key.derive`, which reads `Patient.deceasedDateTime` out of the
committed bundle directly rather than asking `PatientIndex` for it. `caliper.screen` applies the
same precedence, short-circuiting on `PatientIndex.died_before(as_of)` and returning no criterion
table. The two now answer the same question in the same order; before the amendment they did not.
Everything else is unchanged: where the rule does not fire, the outcome is still
`caliper.logic.roll_up` over the adjudicated criterion labels, exactly as section 1 describes.

### What it changed

12 outcomes, 264 criterion labels withdrawn, 0 criterion verdicts reversed, 0 cases added or
dropped, and no change at all to any case on a living patient. Every change is listed with the chart
value behind it in `corrections.md`. Key version 2 has digest `2c411896...`.

| Outcome | Annotated | Constructed | Total | (v1) |
|---|---:|---:|---:|---:|
| `ineligible` | 35 | 6 | **41** | 29 |
| `needs_review` | 1 | 3 | **4** | 15 |
| `eligible` | 0 | 6 | **6** | 7 |

### What it cost

Three things, stated plainly.

**The key is more degenerate than it was.** 41 of 51 cases are `ineligible`, so a system that
answers `ineligible` to everything scores 80.4% against version 2, against 56.9% on version 1 —
higher than any real arm scored on either. Accuracy against version 2 is a weaker statistic than
accuracy against version 1, and the corrected key has to be read through selective risk and the
coverage curve rather than through its headline. Both keys are therefore scored and both tables
published.

**Four criterion-level probes are dead.** The traps were left as each pair was selected to probe
them, because rewriting them would erase the fact that this happened. Four cases now carry a trap
they can no longer exercise, because the vital-status rule decides them before the criterion is
read:

| case | trap | what it can no longer probe |
|---|---|---|
| `CK-002` | `threshold_edge` | an eGFR of 61 against an inclusive ceiling of 60 |
| `AK-010` | `unit` | an MDRD eGFR in bare `mL/min` where the protocol names CKD-EPI per 1.73 m2 |
| `AK-001` | `missing_data` | a liver panel the chart has never carried, as named missing data |
| `CK-003` | `missing_data` | a removed eGFR, as named missing data |

`AK-007`'s potassium of exactly 4.80 mmol/L against a `<=4.8 mmol/L` bound survives, because that
patient is alive. So do the unit cases `AK-021`, `AK-030` and `AK-032`.

**The one eligible case that did not rest on a supplied diagnosis is gone.** `CK-001` was built on
`1be83f06`, the only patient in this corpus with a real type 2 diabetes diagnosis (SNOMED 44054006,
active, onset 2025-06-03) and a real HbA1c above `NCT03315143`'s 7% floor (7.58% on 2025-06-03). He
died on 2026-05-03. All six remaining `eligible` cases are constructed on patients whose committed
charts record Prediabetes, SNOMED 714628002, with HbA1c between 6.02% and 6.27%, and every one of
them is `eligible` only because a recorded edit supplied a diabetes diagnosis and a renal value.
**The key can no longer demonstrate eligible-detection on a chart whose diabetes was not put there
by us.** That is a limitation of the corpus, not of the method, and no edit fixes it. Dropping those
six would return the key to having no `eligible` case at all, which is the degenerate measurement
section 11 exists to prevent; they are kept, flagged on every build, and the choice between six
disclosed-but-supplied eligible cases and none is left open.

### The refutation check

Added at this amendment, and run on every build. For every `met` label in the key it tries to
contradict the label against the raw committed FHIR, reading `data/patients/*.json` itself and using
neither `caliper.record`, `caliper.evaluate` nor `PatientIndex` — a key checked with the same
matching code the key is used to score could only ever agree with it. What each `met` label asserts
is pre-registered per criterion in `refutation.json`, in terms weak enough that a probe can never
dispute a judgement call: it ignores recency, ignores which result is most recent, and ignores the
mutual-consistency rule of section 5, so it can only catch a label that nothing on the chart
supports.

It flags and does not fix, and the build fails while a flag is unanswered. On version 2 it checks
64 `met` labels and refutes none. It reports 18 as *supplied*: not on the committed chart, and put
there by an edit the constructed case publishes. Those 18 are the diabetes and renal labels of the
constructed cases, and `corrections.md` lists every one with the value the committed bundle actually
carries.

### One implementation of the chart rebuild

A constructed case's labels describe the base chart *plus its edits*. `caliper.evalrun.run_arm`
screened `load_patient(case.patient_id)` — the base chart, unedited — so in the run above all 15
constructed cases were scored against labels written for a chart no arm was shown, and `run.json`
records `"replayed": false`. That is a scoring defect rather than a key error, and it accounts for
the disagreements on those cases. `caliper.answerkey.rebuild_patient` is now the single
implementation of replaying a case's recorded perturbations onto its base chart; it refuses to
proceed if a recorded edit does not apply exactly as recorded, and returns the base unchanged for an
annotated case.

---

## 13. Scope, and what the system does with it

*Added at the amendment, for the same reason as section 12.*

### The equivalence

Section 3 put 23 of 153 criteria out of scope, with a reason for each, and the key is derived by
`roll_up` over the remaining 130. That is not merely a restriction of what is annotated; it is a
substantive claim about the rollup, and it should be stated rather than left for a reader to notice:

> **Deriving the outcome from the in-scope criteria alone is identical to deriving it from all 153
> with the 23 out-of-scope ones labelled `unknown` and marked non-blocking.**

`roll_up` looks for a disqualifying verdict over every criterion it is given, and an out-of-scope
criterion labelled `unknown` is never disqualifying; it then forces `needs_review` on any criterion
that is `unknown` *and blocking*, and an out-of-scope one is not. The two derivations agree on all
51 cases of version 1 that carry a criterion table, checked directly rather than argued.

This matters because `caliper.screen` makes the same distinction, through
`UnsupportedPredicate.settlement`: a criterion classified `at_visit` is settled when the patient
comes in, is settled the same way for every patient, and does not block a verdict; one classified
`from_data` is a question about the record that the compiler failed to formalise, and does block.
The key and the system are therefore answering the same question — *nothing in the record rules this
patient out, everything the record was supposed to settle is settled, and here are the N to confirm
at the visit* — rather than two questions that happen to share a vocabulary.

### The overlap

The 23 were chosen by this protocol before any system output existed, by a reader applying section
3's rules to the registry text. The compiler's classifications are produced by a model reading one
criterion at a time with no knowledge of this protocol. Where they agree, neither party could have
checked it alone.

Read out of `eval/tape.jsonl`, which holds the recorded compiler responses from the run in section
12, matched back to `criteria.json` by source quote:

| Section 3's reason for scoping out | Criteria | Compiler called them `unsupported` | My reading of `settlement` |
|---|---:|---:|---|
| study process: consent | 5 | 5 | `at_visit` |
| future intent | 5 | 5 | `at_visit` |
| investigator discretion | 6 | 6 | `at_visit` |
| contraception attestation and future intent | 3 | 3 | `at_visit` |
| study process: compliance | 2 | 2 | `at_visit` |
| study process: ability to perform a study procedure | 1 | 1 | `at_visit` |
| study process: protocol medication restrictions | 1 | 1 | `at_visit`, arguable |
| **total** | **23** | **23** | |

**All 23 agree.** Not one criterion this protocol scoped out was formalised by the compiler, and
none is missing from the tape.

The one I would argue about is `NCT07252908-I13`, "Meet the concurrent medication restrictions
(within the time intervals specified in the protocol) and are expected to maintain the restriction
requirements during treatment." Its second clause is forward-looking and clearly `at_visit`. Its
first asks what the patient is taking, which is a question about the record — but the restrictions
live in a protocol appendix the registry entry does not reproduce, so no chart can answer it *as
written*. I read it `at_visit`; a reader who split the clause would read the first half `from_data`,
and would be making a defensible point about this document's decomposition rather than about the
compiler.

### The caveat, and what is not yet checked

The tape predates the `settlement` field. Every recorded `unsupported` response carries no
settlement and defaults to `from_data`, so **the right-hand column above is my own reading, not the
compiler's classification.** What the tape does establish is the harder half — that the compiler
independently refused to formalise exactly the 23 criteria this protocol scoped out — and that half
needs no re-recording. The comparison of the two `settlement` values is pre-registered here so that
it can be run against the real classifications as soon as the tape is re-recorded, without anyone
choosing the expected answer afterwards.

Two further observations from the same matching:

- The compiler also classified **60 of the 130 in-scope criteria** as `unsupported`. Those are not
  disagreements about visit-settlement; they are formalisation gaps — `from_data` in the new
  vocabulary — and they are the reason the key's coverage figures matter. This protocol says those
  60 criteria *are* questions about the record; the compiler says it could not express them. Both
  can be true, and the distance between them measures the compiler, not the scope.
- Three compiler responses could not be matched to any criterion id, all on `NCT05748834`: the
  compiler split sub-bullets that `criteria.json` had joined with `; ` into criteria of their own
  (the WBRT interval, "other sites of disease assessable by RECIST 1.1", and previously-treated
  brain metastases). That is a difference in decomposition granularity rather than in judgement, and
  it moves no label, since all three sit inside criteria that are `unknown` on every chart in the
  corpus.
