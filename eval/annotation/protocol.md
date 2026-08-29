# Annotation protocol for the Caliper answer key

This document describes how `eval/answer_key.json` was produced, in enough detail that someone
with this repository and no other information could repeat the exercise and get the same labels.

It was written before annotation began. Four things were added afterwards, and each is marked where
it appears: the counts in section 9, the note on `family_history` in section 7, and three
clarifications forced by the adjudication — two in section 4 and one in section 5 — each labelled
*sharpened at adjudication* and each traceable to the disagreement that produced it. Nothing that was
in the document before annotation was removed or reworded.

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

33 pairs over 8 trials and 14 patients, listed in `pairs.json`. Trials were chosen first, for
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
  Ten of the 33 pairs are against one of those four charts.
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

The 33 pairs therefore carry 476 criterion labels per pass.

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
the 33 pairs are against charts whose most recent measurement predates screening by more than two
years, and six of those are `needs_review` for that reason alone and would become decided outcomes
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

The two passes agreed on 443 of 476 criterion labels, giving **Cohen's kappa 0.886** (95% interval
0.849 to 0.924). All 33 disagreements are listed criterion by criterion in `disagreements.md` with
the adjudication and the reason for it, and the contingency table and arithmetic are in `kappa.md`.
Twelve adjudications upheld pass 1, twenty-one upheld pass 2, and exactly one changed a case-level
outcome. Adjudication was done by the maintainer, and `adjudicated_by` on every case says
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

33 cases, all `provenance: annotated`, all with two annotators and an adjudicator.

| Outcome | Cases |
|---|---|
| `ineligible` | 22 |
| `needs_review` | 11 |
| `eligible` | 0 |

**There are no `eligible` cases, and that is a finding rather than an oversight.** We looked for
one. Reaching `eligible` requires every in-scope criterion to resolve `met` or `not_met`, and every
one of these eight protocols bounds at least one laboratory quantity that no chart in the corpus
carries at all — a liver panel for `NCT01131676`, a UACR for `NCT02545049`, `NCT03819153` and
`NCT06717698`, an eGFR for most of them, spirometry percent-predicted and pack-years for
`NCT07252908`. Under section 4's rule that a test not done is not a normal result, those criteria
are `unknown`, and `unknown` propagates. This is the same structural property the README claims for
the system — that `ELIGIBLE` is unreachable while any criterion is unresolved — showing up in the
ground truth as well.

The consequence for scoring should be stated plainly: this key cannot measure whether a system
correctly identifies an eligible patient, because it contains no eligible patient. It measures
whether a system correctly rules patients out, and whether it abstains where the chart is silent.
A system that answered `needs_review` to all 33 pairs would commit no unsafe error and would be
wrong on 22 of them; a system that answered `ineligible` to all 33 would be wrong on 11, in the
direction that quietly loses enrolments. Both baselines are worth running against this key for
exactly that reason.

Cases by trap:

| Trap | Cases |
|---|---|
| `none` | 14 |
| `temporal` | 6 |
| `unit` | 4 |
| `missing_data` | 4 |
| `unsupported` | 3 |
| `negation` | 1 |
| `threshold_edge` | 1 |
| `family_history` | 0 |

---

## 10. Files

| File | What it is |
|---|---|
| `protocol.md` | this document |
| `criteria.json` | the criterion decomposition and the scope decisions, fixed before annotation |
| `pairs.json` | the 33 pairs |
| `cases.json` | per case, the trap it probes and the note that opens its rationale |
| `pass1.json` | pass 1 labels, one verdict and one reason per criterion per pair |
| `pass2.json` | pass 2 labels, produced independently |
| `adjudication.json` | every criterion where the passes differed, with the decision and why |
| `disagreements.md` | the same, in prose |
| `kappa.md` | Cohen's kappa, the contingency table, and the working |

`scripts/build_answer_key.py` reads all of these, applies `caliper.logic.roll_up`, validates
through `caliper.answerkey.load_key`, and freezes the result. It refuses to build if either pass is
missing a criterion, if a disagreement is not decided in `adjudication.json`, or if
`adjudication.json` decides a criterion the passes agreed on.
