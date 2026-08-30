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
| 4 | **Whole-protocol compilation → per-span compilation.** The obvious implementation hands the model the whole eligibility blob. Criteria went missing during development, and nothing noticed. | the `Protocol claimed` column in `RESULTS.md`, which is the span figure this entry always claimed as its evidence — **both arms reach 100%** | Kept per-span, and the evidence does not support it on this corpus. See below: neither the span figure nor accuracy separates the two, and the honest statement is that we chose the expensive one for a failure this corpus does not contain. |
| 5 | **Quote fidelity.** A compiler that paraphrases before formalising leaves no way to tell which version the predicate encodes. | `test_a_paraphrasing_compiler_is_caught_on_real_text` | Kept. A criterion whose quote is not verbatim in the protocol is downgraded to unresolved rather than trusted. |
| 6 | **Composite predicates.** Coverage was collapsing: "eGFR ≥25 and ≤60", "on an ACE inhibitor or an ARB" and every sub-bulleted criterion was being recorded as unformalisable. | the share of criteria compiled as `unsupported`, before and after | Kept, with a caveat. The IR is recursive; the schema sent to the model is the same structure unrolled to a fixed depth, because strict JSON-schema modes handle reference cycles badly and Venice reports one as a timeout rather than an error. |
| 7 | **Terminology resolution, with a store that remembers.** Nothing matches evidence without a code, and a trial mentioning creatinine six times should cost one lookup. | `caliper-no-resolver` arm; the store's own hit rate across trials | Kept. The confidence gate matters more than the cache: a candidate below high confidence is discarded, because an uncoded concept still falls back to wording while a *wrong* code silently matches the wrong evidence. |
| 8 | **The critic.** A compiled predicate that is subtly wrong looks exactly like one that is right. | `caliper-no-critic` arm; the downgrade rate per trial | Kept, in a specific form. The critic is shown two English sentences — the protocol's, and a deterministic rendering of the predicate — and never the JSON. Comparing sentences is a job that can be audited; auditing a data structure is not. |
| 9 | **How to read silence.** The first version treated an unmentioned condition as absent, which is what a naive implementation does implicitly. | `caliper-closed-world` and `caliper-open-world` arms | Kept the coverage-gated middle. Absence counts only where an encounter documents the window. It is a modelling assumption and the alternatives are reported beside it so its size is visible. |
| 10 | **Actionable abstention.** Abstention that does not say what is missing has moved the work rather than reduced it — and a 2025 study of 259 clinicians ([arXiv:2508.07617](https://arxiv.org/abs/2508.07617)) found abstention without explanation shifted errors rather than removing them: 18% more missed diagnoses, 35% more missed treatments. | every `UNKNOWN` in the packet carries a missing datum, a place to look, and a FHIR query | Kept. This is what makes the design a product rather than a safety argument. |
| 11 | **Narrative extraction.** Real eligibility lives in prose, and a system that resolves a criterion by finding a phrase in a note will confidently diagnose the patient's father. | `tests/test_extractor.py`; the manifest in `data/notes/manifest.json` | Kept, with the guard in code rather than in the prompt. Only `present` and `absent` assertions survive; the quoted sentence must appear in the note verbatim; a narrative row cannot match a concept by wording at all, only by a code something took responsibility for attaching. |
| 12 | **A gap in the record is not a question the record was never asked.** The first full run showed Caliper returning "needs review" for every patient against every one of the eight protocols the answer key covers. The cause was structural: each protocol contains a criterion no chart could ever answer — informed consent, a procedure planned after randomisation — and one of those was enough to make `ELIGIBLE` unreachable. | the `caliper` arm's outcome distribution: needs review on all 51 cases before, 18 of 51 after | Kept, with the safety property intact. The compiler now says which kind of unanswerable a criterion is; only a question the record was supposed to settle blocks a verdict. The default is the cautious one, so a compiler that says nothing cannot unblock anything. |
| 13 | **The writer and the prose linter.** A coordinator reading forty criteria wants sentences, and a sentence is the one place a model can drift. | `tests/test_writer.py`; the fallback rate reported per run | Kept. Every number and date in a written sentence is bound to *that criterion's* own values; two failures and the packet degrades to machine prose and says so. |
| 14 | **Letting a person close what the record cannot.** The blocker table below says what abstention actually cost, and it is not what we expected: on the headline trial the same three criteria hold up every screening, and none of them is a gap in a chart. They are an unenumerated category, an intention, and an open-ended list. No query closes those, so a system that only names them has moved the work rather than reduced it. | `tests/test_settlements.py`; the worked case in `examples/` | Kept, under one rule: a settlement may answer a question the record could not, and may never contradict one it did. The evaluator consults it only after reaching UNKNOWN on its own, so a wrong settlement can do no more damage than a wrong human screening — and the record underneath still disagrees in writing. A settlement names one patient, is signed and explained or refused at construction, and is marked on every row of the packet it touches. |

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

**Per-span compilation is refuted here, not merely unfalsified.** Two cases moved, one in each
direction, so accuracy says nothing. The argument for it was always that whole-protocol compilation
silently drops criteria, and that is not an accuracy question — it is measured by how much of the
protocol text some criterion claims. That figure is now published as the `Protocol claimed` column,
and **both arms claim 100% of the spans in all eight protocols.** Whole-protocol compilation dropped
nothing here.

So the entry stands corrected. Per-span compilation is kept for a reason this evaluation does not
support: the failure it prevents was real during development, on protocols with forty-odd criteria
and nested sub-bullets, and the corpus that ended up in the answer key does not contain a protocol
long enough to reproduce it. That is an argument from anecdote, and the arm is in the table so a
reader can see the argument fail rather than take our account of it.

**The absence policy made no difference whatever.** `COVERAGE_GATED` and `CLOSED_WORLD` produced
identical decisions on all 51 cases. `LIMITS.md` spends a section on how load-bearing the
coverage-gated assumption is, and on this corpus it is load-bearing in theory only: every patient
whose chart could have distinguished the two policies has an encounter documenting the window, so
the gate never fires against a chart that would otherwise have gone closed-world. That is a fact
about the corpus — Synthea patients attend regularly — and it means our safest-looking design choice
is the one this evaluation has the least to say about.

## Bugs the process found

None of these were visible from outside the layer they lived in. All of them came from reading one
component closely enough to notice something did not fit. The last one is the same mistake as an
earlier one — a `PatientIndex` rebuilt by naming its fields, dropping the two that were added after
that code was written — in a second place nobody thought to check when the first was fixed. Both are
now `dataclasses.replace`, which cannot forget a field, and a test asserts every field survives the
merge rather than the two we happen to have noticed.

| Bug | Consequence | Found by |
|---|---|---|
| A criterion with no temporal window accepted evidence of **any** date, including after the screening date | Screenings dated 1 June were being decided from results dated in August. Synthea charts run past the fixed screening date, so this was live rather than theoretical. | building the chart summariser, which correctly hid future rows while the evaluator used them |
| `Patient.deceasedDateTime` was dropped on ingestion | One patient who died four weeks before the screening date read as an ordinary, complete, screenable chart | building the evaluation cases |
| `medicationReference` was not resolved, and `Medication` had been trimmed from the corpus | 114 of 342 prescriptions carried no drug identity at all, so any criterion about a concomitant or prohibited medication was unresolvable for two thirds of patients | rendering medications in the chart summary |
| The prose linter's rounding rule | See above | writing the packet against it |
| Attaching a clinical note resurrected the patient | `attach_notes` returns a copy, and the copy was built by naming the fields to carry over — `deceased` and `deceased_undated` were not named. Three of the nine patients with notes in this corpus are recorded as dead, and sixteen answer-key cases are on them. Screening stops on a recorded death before it reads a criterion; after a note was attached it no longer did. **The published numbers are unaffected: `use_narrative` is off in every evaluation arm, so the path never ran during a scored run.** It ran in `caliper screen`. | reading `screen_patient` while looking for somewhere to thread settlements through, and finding the same rebuild a second time |

## The reproducibility claim was false, and the container is what found it

`README.md` said the headline result reproduces byte for byte with no API key and no network. It did
not, and the failure was silent, which is the worst way for it to fail.

`docker run --rm caliper` produced **eleven verdicts different from the same command run locally** —
73% coverage against 88%, and a `caliper` arm that had quietly become `caliper-no-resolver`. Nothing
on stdout said so. Both runs printed a full table and neither printed a warning.

Two causes, one on top of the other:

| | |
|---|---|
| **The terminology store was not part of the artefact** | The resolver reads `.caliper/concepts.json` before it calls a model. That file was gitignored as a run artefact, so it was warm when the tape was recorded and cold in any fresh clone or container — which made the resolver ask questions the recording had never been asked. It is now committed and copied into the image, with the reason written in both ignore files. |
| **A tape miss was degrading instead of stopping** | The retry ladder drops a rung on any transport exception, because a provider refusing a `response_format` has no portable exception type. `TapeMiss` was caught by that same clause, exhausted the ladder, and surfaced to the resolver as an ordinary failure — which it handles by returning no codes and carrying on, exactly as designed. A missing recording is not an unresolvable concept, and it now propagates. |

The second is the one worth keeping. The first was a packaging mistake and would have been found by
anyone who cloned the repository; the second is a system that was built to be honest about what it
does not know and had a path by which it could be wrong without saying so. `tests/test_tape.py`
now asserts that a miss reaches the caller and that an ordinary transport refusal still drops a rung,
because the fix is only correct if it keeps both behaviours apart.

Verified after the fix: every one of the eleven arms reports identical figures in the container and
on the host.

## What an adversarial read of our own documentation found

Late in the build, one agent was given a single instruction: read every public document as the judge
who checks, and find every sentence the repository itself refutes. Report, do not fix. It came back
with twenty-two, and the three worst were not in the code.

| | |
|---|---|
| **The coverage metric was not coverage** | `CaseScore.answered` counted an abstention as an answer whenever the key also said `needs_review` — on the reasoning that abstaining on an undecidable case is the correct output. It is, and the coordinator opens the chart anyway. It inflated our own headline from 65% to 73%, and the tell was in the table the whole time: `always_needs_review`, an arm that decides nothing, scored 8% coverage. It reads 0% now. |
| **Three required files were not in the repository** | `.gitignore` carried an unanchored `build/`, which swallowed `trajectories/build/` — the coding-agent trajectories the challenge requires and the README links to. Locally the directory was there; in every clone it was three broken links, in the section about honesty. |
| **`eval/annotation/corrections.md` described a run that no longer existed** | It names `eval/results/run.json` as its source, and every figure in it disagreed: a different timestamp, ten arms instead of eleven, 45.1% where the committed run says 49.0%. The document was written before two bugs it had itself exposed were fixed and the evaluation re-recorded, and nobody regenerated it. Four other documents point a sceptical reader at that file. |

The rest were smaller and the same shape: a cost figure from a superseded trajectory, "every accuracy
figure moved by twenty-four points" when one arm moved twenty-two the other way, "all ten protocols"
when the evaluation covers eight, "asserted for every predicate type" when the parametrization listed
four of eleven, "about seven seconds" for a suite that takes twenty-five.

Two things are worth drawing out of that.

**Generated documents did not appear in the list.** Every refuted claim was in prose a person typed.
`RESULTS.md` is generated from the run on every build and had nothing wrong in it, which is the
argument for generating it, made by a check we did not design to make it.

**The findings that cost us most were the ones we would never have found by testing.** No test can
notice that a metric's name and its definition have drifted apart, because both halves are internally
consistent. It took someone reading the sentence next to the number.

## What the changelog is missing

The order above is the order the components were reasoned about, not a clean chronology — several
were built in parallel, and the ablation numbers were all measured at the end against the same
frozen key rather than one at a time as each landed. That is a weaker form of evidence than a
sequential A/B would be, and it is worth saying: the arms tell you what each component contributes
to the *finished* system, not what it contributed on the day it was added.
