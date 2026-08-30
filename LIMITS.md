# Honest limits

What Caliper does not do, where the data is unrealistic, and which of our own results we would
attack first. Every claim in `README.md` is meant to be read against this file.

## What is real and what is simulated

| Component | Status |
|---|---|
| Trial eligibility criteria | **Real.** Ten studies pulled from the ClinicalTrials.gov v2 API and committed verbatim, with the registry's own `dataTimestamp`. Nothing was hand-edited. |
| Patient records | **Synthetic.** Synthea FHIR R4 bundles from MITRE's public sample, trimmed to ten resource types. No real person, no PHI, and none of this is derived from a real chart. |
| Clinical notes | **Hand-authored for this project.** Synthea's own notes are fill-in-the-blank templates with no clinical language in them, so the narrative cases use notes we wrote. They are listed in `data/notes/manifest.json` and are clearly labelled as authored fixtures. |
| Terminology codes | **Real code systems, resolved by a model.** LOINC, SNOMED CT and RxNorm identifiers are checked for shape but are not validated against a terminology server. |
| Screening verdicts | **Deterministic**, from `caliper/evaluate.py`. No model is reachable from that module. |
| The evaluation answer key | **Ours.** See "Grading our own homework" below. |

## The system does not decide eligibility

Caliper produces a pre-screening packet for a research coordinator. It never enrols anyone, never
writes to a record, and has no path to any system that could. Eligibility is determined by the
investigator. Every packet says so, and the design assumes a qualified human reads it.

## What `ELIGIBLE` means, precisely

Not "this patient is eligible for this trial". It means:

> Nothing in this patient's record rules them out, every criterion the record was supposed to settle
> has been settled with cited evidence, and these N criteria remain — each of which is settled at the
> screening visit for every patient, and each of which is listed.

That distinction is deliberate and it was forced on us by the data. Every one of the ten protocols in
the corpus contains at least one criterion no chart could ever answer: signed written informed
consent, a procedure planned after randomisation, the investigator's own judgement of the patient in
person. Treating those as unresolved data made `ELIGIBLE` unreachable for all ten — one consent
criterion and the screening abstains, whoever the patient is. That is not caution; it is a system
that never says anything.

So the compiler now records **which kind of unanswerable** a criterion is. A question the record was
supposed to answer and we failed to formalise is a gap, and it still blocks. A question that only the
screening visit can answer does not block, and appears on the packet under its own heading.

The cost of this is real and worth stating: an exclusion settled at the visit — "planning to start an
SGLT2 inhibitor during the study" — can still rule a patient out after Caliper has said `ELIGIBLE`.
That is what pre-screening is. The packet exists so the coordinator knows exactly which questions are
still open when the patient walks in.

The default is the conservative one. A compiler that says nothing about which kind a criterion is
cannot thereby unblock a verdict.

## Things Caliper genuinely cannot do

- **Read a criterion that depends on judgement.** "Adequate organ function", "clinically
  significant", "in the opinion of the investigator" are compiled as `unsupported` and go to a
  human. This is intentional, but it means our coverage on some protocols is bounded by how the
  protocol was written rather than by how good the system is.
- **Resolve "above the upper limit of normal".** Reference ranges are laboratory-specific and are
  not in the record we are given. Any criterion phrased that way abstains.
- **Reconcile `mL/min` with `mL/min/1.73m^2`.** This is worth naming separately because it is the
  single most expensive refusal we measured: on the headline trial it is the top blocker, holding up
  **18 of 24 screenings** — more than the three genuinely-unformalisable criteria beneath it. The
  protocol asks for an eGFR normalised to body surface area; the chart reports one that is not, or
  is labelled as though it is not. Converting needs the patient's BSA, and whether Synthea's
  `mL/min` is a genuinely un-normalised measurement or a labelling slip is not knowable from the
  bundle. So the criterion abstains and the packet says why. It is the clearest case in the corpus
  of an abstention that is correct, cheap to close, and *not* a limit of the model: one line from a
  site telling us how their laboratory reports eGFR would clear eighteen screenings.

- **Convert an analyte we have not vetted.** `caliper/units.py` carries an explicit table. A mass
  unit cannot be converted to a molar one without knowing the substance, so an analyte missing from
  the table abstains rather than guessing. The table is short by design and is a known bottleneck.
- **Distinguish "ruled out" from "not documented" in structured data.** Synthea never emits
  `verificationStatus: refuted`, so structured negation is unavailable. Negation is only reachable
  through the narrative path.
- **Handle criteria nested more than two levels deep.** The schema sent to a model is unrolled to a
  fixed depth because strict JSON-schema modes cannot take a reference cycle. Deeper criteria are
  compiled as `unsupported`, not truncated.
- **Anchor a window to anything but the screening date.** Protocols anchor to screening, enrolment,
  randomisation and consent, which are genuinely different dates. We treat them all as the screening
  date and flag the criterion when the difference could matter.

## Where the absence rule can be wrong

**On this corpus the choice makes no difference at all, which is its own limitation.** Scored against
the answer key, coverage-gated and closed-world produce identical decisions on all fifty-one cases:
every chart that could have separated them carries an encounter documenting the window, because
Synthea patients attend regularly. So the assumption below is load-bearing in argument and inert in
measurement, and this evaluation cannot tell you whether it is right.

The default `AbsencePolicy.COVERAGE_GATED` accepts "the patient does not have this condition" when
an encounter documents the relevant window, on the theory that a chart being maintained is evidence
someone was looking. That is a modelling assumption, not a fact. A patient can attend a visit for an
unrelated complaint while an undiagnosed condition goes unrecorded. The alternative policies are
implemented and measured — open-world abstains on every absence and is unusably conservative;
closed-world treats silence as absence and is what a naive implementation does implicitly. The
results table reports all three so the reader can see the size of the assumption rather than take
our word for it.

## What the prose linter proves, and what it does not

`caliper/prose.py` checks that every number and date in a model-written sentence is bound to a value
*that criterion* resolved from. It does not check that the sentence describes the right relationship
between those numbers. A sentence reading "creatinine of 1.2 mg/dL exceeds the 1.5 mg/dL ceiling"
has both numbers correctly bound and is still wrong. Slot-level binding narrows the gap — each
number is checked against the criterion it is rendered under, not against the packet as a whole —
but semantic verification of the sentence is not implemented.

## Grading our own homework

The answer key was built by us. That is the single weakest part of this submission and we would
attack it first.

What we did about it:

- **Constructed cases carry labels that are true by construction.** Redacting the only creatinine
  result means the correct answer is "unknown" whatever anyone believes; moving a value across a
  threshold means the verdict must flip. These cases cannot be argued with, and they are the
  negative controls that stop a green result from being vacuous.
- **Annotated cases are labelled by model-assisted dual annotation with adjudication.** We are not
  clinicians and we do not claim clinician review. The annotation protocol, the disagreements and
  the adjudication decisions are published with the key.
- **The key is frozen and hashed.** `caliper eval` refuses to score against a key whose digest does
  not match its sidecar. What that proves is narrower than it sounds, in two ways. The digest covers
  canonicalised content — `frozen_at` dropped, cases and object keys sorted — so it catches any
  change to a label, a case or a perturbation, and deliberately ignores reformatting. And the
  sidecar lives in the same tree and is written by the same script, so it shows nothing has been
  edited since the freeze, not that the freeze predates the results. The git history is what orders
  them.
- **The key was corrected after the first scored run, and both versions ship.** That is the
  circumstance in which a correction is least trustworthy, so version one is kept unchanged and
  scored alongside version two, and every changed label is published in
  `eval/annotation/corrections.md` with the chart value that refutes the old one. The rule was: a
  label moves only where the chart refutes it, never where the system merely disagreed. Two things
  forced it — the annotation protocol never mentioned vital status, and every constructed eligible
  case rested on a diabetes criterion the charts underneath contradict.
- **Fifty-odd cases is a small sample.** Every proportion is reported with an exact Clopper-Pearson
  interval, and at this n the interval is roughly ±13 percentage points. Differences smaller than
  that are not differences.

## Where the data is unrealistic

- Synthea laboratory values are drawn from distributions rather than being coupled to disease
  severity, so a patient's creatinine does not track their kidney disease the way a real chart's
  would. This makes some cases easier than reality and some incoherent.
- `referenceRange` and `interpretation` are essentially absent, so there are no abnormal flags to
  lean on.
- Medication records carry no stop date, only a status, so washout periods and prior lines of
  therapy are not reliably derivable. Criteria requiring them abstain.
- The sample contains exactly one COPD patient and two with heart failure. Results on those trials
  rest on very few charts and should not be read as a rate.
- No ECOG or Karnofsky performance status, no cancer staging, no biomarkers. Oncology protocols are
  therefore heavily abstained on, and the one oncology trial in the corpus is included to show that
  honestly rather than to be scored well.

## Reproducibility, precisely

The headline result replays recorded model responses, so it reproduces byte for byte with no API
key and no network. A **live** run will not reproduce exactly: temperature zero is not determinism
on a hosted API, where batching makes reduction order vary between requests. We do not claim
otherwise, and `caliper eval --live` reports the drift against the recorded run rather than hiding
it.

## Not claimed

- Not a medical device, and not validated for clinical use.
- No claim that Caliper improves enrolment rates. We measured screening decisions on synthetic
  charts, not enrolment on real ones.
- No claim of clinician-validated ground truth.
- No claim that the terminology mappings are complete or clinically audited.
- No claim of statistical significance at this sample size.
