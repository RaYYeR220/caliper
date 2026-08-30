# Improvement changelog

How Caliper got from a single prompt to what is in this repository, what each change was supposed to
buy, and what the evidence said.

Two honesty notes before the table. First, not every entry came from an experiment. Some choices
were made up front from the prior art — three-valued logic because CQL already specifies it, a
deterministic evaluator because that was the whole premise — and pretending otherwise would make
this document a story rather than a record. Where a decision was taken on principle it says so, and
where it was forced by evidence the evidence is named.

Second, the numbers live in [`RESULTS.md`](RESULTS.md), which is generated. Nothing here is typed
by hand, so nothing here can go stale against the run.

---

## The journey

| # | What was tried, and why | Evidence | Decision |
|---|---|---|---|
| 0 | **Baseline.** One prompt: the protocol text, the patient's chart, and "is this patient eligible?" | `single_prompt` row in `RESULTS.md` | Established the starting point, and the failure mode everything after this is about — it answers every case with the same confidence, including the ones the chart cannot support. |
| 1 | **Compile to an executable IR, evaluate in code.** The premise: if the model produces a predicate rather than a verdict, the verdict becomes reviewable. | it worked, and immediately exposed entry 2 | Kept. This is the spine. |
| 2 | **Boolean logic was wrong, not merely incomplete.** With two values, "no creatinine on file" and "creatinine above the ceiling" both came out as *not met*, and the patient was screened out for a lab nobody had ordered. | every case with a missing value produced a confident exclusion | Replaced with three-valued logic. `Verdict.UNKNOWN` is a first-class outcome, following CQL's null-propagation semantics rather than inventing our own. |
| 3 | **Propagation.** Three values are only worth having if `UNKNOWN` cannot be rounded away. | `roll_up` in `logic.py`; asserted in `tests/test_logic.py` | Kept. `ELIGIBLE` is unreachable while any criterion is unresolved. This is the design, and everything else is in service of making it survivable. |
| 4 | **Whole-protocol compilation → per-span compilation.** The obvious implementation hands the model the whole eligibility blob. Criteria went missing, and nothing noticed. | `caliper-whole-protocol` arm: the count of protocol spans no criterion claims | Kept per-span. The alternative is still in the repository and still measured, because "we chose the expensive one" is only worth saying with a number attached. |
| 5 | **Quote fidelity.** A compiler that paraphrases before formalising leaves no way to tell which version the predicate encodes. | `test_a_paraphrasing_compiler_is_caught_on_real_text` | Kept. A criterion whose quote is not verbatim in the protocol is downgraded to unresolved rather than trusted. |
| 6 | **Composite predicates.** Coverage was collapsing: "eGFR ≥25 and ≤60", "on an ACE inhibitor or an ARB" and every sub-bulleted criterion was being recorded as unformalisable. | the share of criteria compiled as `unsupported`, before and after | Kept, with a caveat. The IR is recursive; the schema sent to the model is the same structure unrolled to a fixed depth, because strict JSON-schema modes handle reference cycles badly and Venice reports one as a timeout rather than an error. |
| 7 | **Terminology resolution, with a store that remembers.** Nothing matches evidence without a code, and a trial mentioning creatinine six times should cost one lookup. | `caliper-no-resolver` arm; the store's own hit rate across trials | Kept. The confidence gate matters more than the cache: a candidate below high confidence is discarded, because an uncoded concept still falls back to wording while a *wrong* code silently matches the wrong evidence. |
| 8 | **The critic.** A compiled predicate that is subtly wrong looks exactly like one that is right. | `caliper-no-critic` arm; the downgrade rate per trial | Kept, in a specific form. The critic is shown two English sentences — the protocol's, and a deterministic rendering of the predicate — and never the JSON. Comparing sentences is a job that can be audited; auditing a data structure is not. |
| 9 | **How to read silence.** The first version treated an unmentioned condition as absent, which is what a naive implementation does implicitly. | `caliper-closed-world` and `caliper-open-world` arms | Kept the coverage-gated middle. Absence counts only where an encounter documents the window. It is a modelling assumption and the alternatives are reported beside it so its size is visible. |
| 10 | **Actionable abstention.** Abstention that does not say what is missing has moved the work rather than reduced it — and a 2025 study of 259 clinicians found abstention without explanation shifted errors rather than removing them. | every `UNKNOWN` in the packet carries a missing datum, a place to look, and a FHIR query | Kept. This is what makes the design a product rather than a safety argument. |
| 11 | **Narrative extraction.** Real eligibility lives in prose, and a system that resolves a criterion by finding a phrase in a note will confidently diagnose the patient's father. | `tests/test_extractor.py`; the manifest in `data/notes/manifest.json` | Kept, with the guard in code rather than in the prompt. Only `present` and `absent` assertions survive; the quoted sentence must appear in the note verbatim; a narrative row cannot match a concept by wording at all, only by a code something took responsibility for attaching. |
| 12 | **A gap in the record is not a question the record was never asked.** The first full run showed Caliper returning "needs review" for every patient against every one of the ten protocols. The cause was structural: each protocol contains a criterion no chart could ever answer — informed consent, a procedure planned after randomisation — and one of those was enough to make `ELIGIBLE` unreachable. | the `caliper` arm's outcome distribution before and after | Kept, with the safety property intact. The compiler now says which kind of unanswerable a criterion is; only a question the record was supposed to settle blocks a verdict. The default is the cautious one, so a compiler that says nothing cannot unblock anything. |
| 13 | **The writer and the prose linter.** A coordinator reading forty criteria wants sentences, and a sentence is the one place a model can drift. | `tests/test_writer.py`; the fallback rate reported per run | Kept. Every number and date in a written sentence is bound to *that criterion's* own values; two failures and the packet degrades to machine prose and says so. |

## Experiments that were removed

| What | Why it was tried | What happened |
|---|---|---|
| **A pseudo-criterion for vital status** | Five patients in the corpus are deceased, one of them four weeks before the screening date, and screening them normally produced a table of resolved criteria about a person who cannot be enrolled. The first fix injected a synthetic criterion called `VITAL-STATUS` into the result. | **Removed.** It leaked a criterion the protocol never contained into every consumer — the packet renderer crashed on it, and the metamorphic suite reported it as a criterion that had appeared from nowhere. Replaced with `blocked_by` on the screening itself: a fact about the screening is not a criterion, and modelling it as one made three other components wrong. |
| **Rounding in the prose linter** | A sentence saying "1.2 mg/dL" should be allowed to describe a value of 1.199, so the linter accepted any number an allowed value rounded to. | **Revised.** Rounding to the whole number meant a threshold of 1.5 vouched for a sentence saying "2" — a linter that certifies an invented number is worse than none, because nobody looks again. Rounding is now permitted only to a decimal place. |
| **Dates seeding the numeric allowed set** | The evaluator's own rationale is by definition derived from the record, so its numbers were added to what a sentence may say. | **Revised.** `2026-05-14` decomposed into 2026, 5 and 14, so a sentence could assert a creatinine of 2026 and pass. Dates are now stripped before numbers are extracted. |
| **Letting the model choose the inclusion-or-exclusion kind** | It has the criterion in front of it and could reasonably say. | **Removed.** The segmenter already knows, from the section heading, and a model that mislabels it silently inverts the criterion's meaning. The kind now comes from the heading, and the model's opinion is discarded. |
| **Letting the model choose criterion identifiers** | Simplest thing that could work. | **Removed.** Identifiers assigned in code are stable across runs and across models, which is what makes two arms comparable at all. |

## What the first scored run found

The evaluation's first useful output was not a score. It was a list of things wrong with the
evaluation, and with the system, that nothing else had surfaced.

| Found | What it was | What happened |
|---|---|---|
| **The key was wrong about the dead** | Twenty of fifty-one cases are on patients who died before the screening date. The annotation protocol never mentioned vital status — an omission in the brief, not in the annotation — so eleven were labelled "needs review" and one "eligible". Caliper screens them out and was penalised for it on twelve cases. | Vital status is now a rule that precedes every criterion. The corrections are published in `eval/annotation/corrections.md` with the run that prompted them. |
| **A wrong diagnosis, caught by the check built to catch it** | The constructed `eligible` cases rest on a criterion reading "Type 2 Diabetes Mellitus with HbA1c ≥7%", and the charts underneath carry **prediabetes** with an HbA1c of 6.08–6.21%. That looked conclusive, and it was written up as a second error in the key. It was not one: the annotated cases on those charts already label that criterion `not_met`, and the `met` labels belong to constructed cases *after* an edit that supplies the diagnosis and moves the HbA1c — both declared in the case's own `perturbations`. | The refutation pass, which reads the raw committed FHIR and never Caliper's own matching, checked 64 `met` labels and refuted none. It is the reason this entry says what it says instead of what we first believed. The real cause of those disagreements was the runner bug in the row below. |
| **Constructed cases were scored against the wrong chart** | The runner loaded each case's *base* chart and ignored the edits the case describes, so fifteen cases produced confident verdicts answering a question nobody had asked. Silent: every case ran, every case scored. | The runner is handed the case, not the identifier, and there is now one shared implementation of replaying a case's edits instead of three. |
| **The baseline could not see a death** | The chart summary is the whole record to whoever reads it, and it omitted a recorded death — so the baseline was shown a patient who had died four weeks earlier as an ordinary candidate, while Caliper read the date directly. The comparison was measuring our plumbing. | The summary states it. The baseline's brief was also rewritten to set it the same task Caliper works to, rather than a slightly different one. |
| **The provider will not compile our schema** | Venice answers a strict schema with more than sixteen union-typed parameters with a 400 naming the figure. The depth-2 criteria schema has thirty-seven, because strict mode turns every optional field into a null union. The three-tier ladder recovered on its own, every time, which is exactly what it is for — but it spent a round trip per call doing it. | A profile now declares the limit and the rung is skipped, with the arithmetic written into the trajectory. |

### What the corrected key cost

Correcting for vital status moved twelve cases to `ineligible` and left the key with 41 of 51
expecting that answer. **That makes accuracy against version two a weak statistic**: rescoring the
same recorded decisions, a system that answers "ineligible" to everything scores 80%, beating every
real arm. It is in the results table for exactly that reason, next to `always_needs_review`, which
collapses from 29% to 8% under the same correction. Read coverage, unsafe errors and the per-outcome
breakdown; the single accuracy figure is the least informative column in the table.

The six remaining `eligible` cases all rest on a diabetes diagnosis supplied to a chart that records
prediabetes. That is declared per case and it is not a label we asserted — the edit is published and
the label follows from it — but it is worth saying plainly why it had to be done that way: **the
corpus contains exactly one genuinely diabetic patient with an HbA1c over seven, and he died four
weeks before the screening date.** No edit fixes that, and no unedited chart in this corpus is
eligible for this trial.

## What the ablations actually said

The table above reads as a series of components that earned their place. The run does not support
that reading for all of them, and the arms are in `RESULTS.md` precisely so nobody has to take the
narrative's word for it. Comparing each ablation against `caliper` case by case, out of 51:

| Arm | Cases it decided differently | Which way | What it did to the numbers |
|---|---:|---|---|
| `caliper-whole-protocol` | 2 | one each way | Nothing. Same accuracy, same coverage, same zero unsafe errors. |
| `caliper-no-critic` | 4 | all `needs_review` → `ineligible` | **Removing the critic improved accuracy**, 73% to 80%, and coverage, 73% to 80%. No unsafe errors either way. |
| `caliper-no-resolver` | 11 | all `needs_review` → `ineligible` | Coverage 73% to 88%, accuracy 73% to 71%. No unsafe errors either way. |
| `caliper-closed-world` | **0** | — | Nothing at all. Not one of the 51 decisions moved. |
| `caliper-open-world` | 4 | all `ineligible` → `needs_review` | Coverage 73% to 65%, accuracy 73% to 65%. |

Three of those deserve to be said in words rather than left in a table.

**The critic costs accuracy on this key and buys nothing measurable.** It downgrades four criteria
that would otherwise have decided their case, and every one of those four cases was decided
correctly without it. The honest reading is that the critic is insurance against a failure mode this
answer key does not contain — a compiled predicate with a plausible wrong threshold, which our
constructed cases perturb the *chart* to create rather than the predicate. It is kept because the
failure it guards against is the expensive one and because a 7-point gap at n=51 sits well inside a
26-point interval, but "kept on principle" is what that is, and entry 8 above should be read with
this paragraph beside it.

**Per-span compilation is unfalsified here, not vindicated.** Two cases moved, one in each
direction. The argument for it — that whole-protocol compilation silently drops criteria — is
measured by the span-coverage number rather than by accuracy, and this key is not the instrument for
it.

**The absence policy made no difference whatever.** `COVERAGE_GATED` and `CLOSED_WORLD` produced
identical decisions on all 51 cases. `LIMITS.md` spends a section on how load-bearing the
coverage-gated assumption is, and on this corpus it is load-bearing in theory only: every patient
whose chart could have distinguished the two policies has an encounter documenting the window, so
the gate never fires against a chart that would otherwise have gone closed-world. That is a fact
about the corpus — Synthea patients attend regularly — and it means our safest-looking design choice
is the one this evaluation has the least to say about.

## Bugs the process found

None of these were visible from outside the layer they lived in. All four came from reading one
component closely enough to notice something did not fit.

| Bug | Consequence | Found by |
|---|---|---|
| A criterion with no temporal window accepted evidence of **any** date, including after the screening date | Screenings dated 1 June were being decided from results dated in August. Synthea charts run past the fixed screening date, so this was live rather than theoretical. | building the chart summariser, which correctly hid future rows while the evaluator used them |
| `Patient.deceasedDateTime` was dropped on ingestion | One patient who died four weeks before the screening date read as an ordinary, complete, screenable chart | building the evaluation cases |
| `medicationReference` was not resolved, and `Medication` had been trimmed from the corpus | 114 of 342 prescriptions carried no drug identity at all, so any criterion about a concomitant or prohibited medication was unresolvable for two thirds of patients | rendering medications in the chart summary |
| The prose linter's rounding rule | See above | writing the packet against it |

## What the changelog is missing

The order above is the order the components were reasoned about, not a clean chronology — several
were built in parallel, and the ablation numbers were all measured at the end against the same
frozen key rather than one at a time as each landed. That is a weaker form of evidence than a
sequential A/B would be, and it is worth saying: the arms tell you what each component contributes
to the *finished* system, not what it contributed on the day it was added.
