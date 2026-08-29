# Disagreements and adjudication

Of 476 criterion labels, the two passes differed on 33, across 19 of the 33 cases. All 33 are listed
here with the decision and the reason for it; the same decisions in machine-readable form, which
`scripts/build_answer_key.py` requires to be exactly the set of differing criteria, are in
`adjudication.json`.

Adjudication was done by the maintainer, after both passes were complete, with both reasons visible
and the chart summary and registry text open. Twelve decisions upheld pass 1 and twenty-one upheld
pass 2. **One changed a case-level outcome**: AK-026 moved from `needs_review` to `ineligible`. The
other thirty-two changed a criterion label without changing the case, which is the pattern to expect
if the disagreements are about how to read the protocol rather than about what the chart says.

The disagreements fall into six themes. Nothing here is a clerical error; every one of them is a
place where `protocol.md` was less specific than it needed to be, and each theme ends with the
sharpening that was written back into it.

---

## Theme 1 — Chart currency: how a window is documented (10 labels)

| Case | Criterion | pass 1 | pass 2 | Decided |
|---|---|---|---|---|
| AK-032 | NCT07252908-I11 clinically stable COPD within 4 weeks | unknown | met | **met** |
| AK-032 | NCT07252908-E2 exacerbation needing steroids within 3 months | unknown | not_met | **not_met** |
| AK-032 | NCT07252908-E4 antibiotics for respiratory infection within 6 weeks | unknown | not_met | **not_met** |
| AK-032 | NCT07252908-E8 pulmonary rehabilitation | unknown | not_met | **not_met** |
| AK-032 | NCT07252908-E9 oral steroids/roflumilast within 3 months | unknown | not_met | **not_met** |
| AK-032 | NCT07252908-E12 immunotherapy within 4 weeks | unknown | not_met | **not_met** |
| AK-032 | NCT07252908-E15 cardiovascular events within 3 and 6 months | unknown | not_met | **not_met** |
| AK-032 | NCT07252908-E18 major surgery within 8 weeks | unknown | not_met | **not_met** |
| AK-032 | NCT07252908-E25 vaccination within 28 days | unknown | not_met | **not_met** |
| AK-032 | NCT07252908-E27 trial participation within 4 weeks | unknown | not_met | **not_met** |

Patient `cbd1dd48`'s last encounter is 2026-01-06, five months before the screening date. Pass 1
required an encounter dated *inside* each criterion's window before it would read absence as
absence, so every window shorter than five months came out `unknown`. Pass 2 required only that the
chart be current in general.

Pass 1 lost, and the reason is that pass 1 does not agree with itself. On nine other charts whose
last encounter is between one and eight months before screening — `f870c432` at 2025-10-08,
`fd0d7b3a` at 2025-09-09, `a6d0791e` at 2025-12-09, `8c5b83b2` at 2025-11-24 among them — pass 1
read absence over 30-day, 60-day, 90-day and 12-week windows as `not_met` without an encounter
inside them, and pass 2 agreed. The disagreement on AK-032 exposed an inconsistency inside pass 1
rather than a difference of principle between the passes, and it is resolved in the direction of
pass 1's own dominant practice.

**Written back into the protocol (section 4):** a chart whose most recent encounter is within twelve
months of the screening date is *current*, and for a current chart the absence of a condition,
medication, procedure or event is read as absence for any window. A chart whose most recent
encounter is older than twelve months is not current, and absence resolves nothing for any window
that reaches past that encounter. The bound splits this corpus exactly along the line one would draw
by eye: ten charts current, four stale (`2211f478` 2016, `8d91c36a` 2015, `fb56f051` 1991,
`30889246` 1961).

None of the ten changed the outcome of AK-032, which is `ineligible` because the patient is 37
against an age floor of 40.

---

## Theme 2 — Undefined risk criteria (6 labels)

| Case | Criterion | pass 1 | pass 2 | Decided |
|---|---|---|---|---|
| AK-001 | NCT01131676-I7 "High cardiovascular risk" | unknown | not_met | **unknown** |
| AK-014 | NCT03315143-I3 major/minor cardiovascular risk factors | unknown | met | **unknown** |
| AK-015 | NCT03315143-I3 | unknown | met | **unknown** |
| AK-016 | NCT03315143-I3 | unknown | met | **met** |
| AK-017 | NCT03315143-I3 | unknown | met | **unknown** |
| AK-018 | NCT03315143-I3 | unknown | met | **unknown** |

Two trials require a cardiovascular risk judgement and neither defines it. EMPA-REG's inclusion 7 is
the three words "High cardiovascular risk". SCORED's inclusion 3 asks for "at least one major
cardiovascular risk factor" or, from 55, "at least two minor cardiovascular risk factors", and
enumerates neither class. Pass 2 supplied a definition — obesity, metabolic syndrome and
hyperlipidaemia counted as major factors — and resolved all six. Pass 1 abstained on all six.

The decision splits them, on a single principle: the criterion resolves where every plausible
definition gives the same answer, and abstains where the definition does the work.

- **AK-016** is `met`. This patient has had ischemic heart disease since 2013-09-04. Established
  cardiovascular disease is a major risk factor under every published scheme, so no choice of
  definition changes the label.
- The other five are `unknown`. Obesity is classified as a major risk factor by some schemes, a
  minor one by others, and a risk marker rather than a factor by others again; metabolic syndrome is
  a cluster of factors rather than a factor; and none of AK-001, AK-014, AK-015, AK-017 or AK-018
  has established cardiovascular disease. Pass 2's answer is defensible and it is a choice the
  registry text does not license.

This is the disagreement that most directly tests what the key is for. A system that resolves
"high cardiovascular risk" from a BMI is guessing, and if the key resolved it too the evaluation
would score that guess as correct.

---

## Theme 3 — Absence of a measurement versus absence of a disease (6 labels)

| Case | Criterion | pass 1 | pass 2 | Decided |
|---|---|---|---|---|
| AK-012 | NCT03036124-E10 bradycardia or 2nd/3rd degree block | unknown | not_met | **not_met** |
| AK-013 | NCT03036124-E10 | unknown | not_met | **not_met** |
| AK-024 | NCT05748834-I6 measurable disease per RECIST 1.1 | unknown | not_met | **not_met** |
| AK-024 | NCT05748834-E2 findings on screening brain MRI | unknown | not_met | **not_met** |
| AK-025 | NCT05748834-I6 | unknown | not_met | **not_met** |
| AK-025 | NCT05748834-E2 | unknown | not_met | **not_met** |

Protocol section 4 draws a line between criteria over conditions, where absence from a current chart
resolves, and criteria over measured quantities, where absence of the measurement is `unknown`. Pass
1 put all six on the measurement side of it: no electrocardiogram, so no verdict on heart block; no
tumour imaging, so no verdict on measurable disease; no brain MRI, so no verdict on brain lesions.

Pass 1 was wrong about what these criteria are about.

`NCT03036124-E10` names diagnoses — symptomatic bradycardia, second- or third-degree heart block —
not an interval on a tracing. It is a condition criterion, and on charts current to 2026-05-30 and
2025-12-09 with no such diagnosis it resolves `not_met`.

The two oncology criteria are subtler. Both presuppose the disease under study: RECIST measurable
disease presupposes a tumour, and every limb of the brain-MRI exclusion is about metastases from
that tumour. Inclusion 4, "confirmed diagnosis of locally advanced/metastatic HER2+ breast cancer",
is `not_met` on both charts under the condition rule. **A criterion whose subject matter is entailed
by a condition the chart resolves as absent resolves too.**

That principle is deliberately not extended to everything in the same trial. `NCT05748834-I13`, the
CNS *inclusion*, stays `unknown` on both cases — both passes agreed on that, so it is not in this
table — because it demands a positive classification made from a screening contrast brain MRI, and
no such study exists. An exclusion is not triggered by a lesion the patient cannot have; an
inclusion is not satisfied by an imaging study nobody performed. Likewise ECOG, LVEF, the
haematology panel and the liver panel stay `unknown` throughout: they are quantities every patient
has and this corpus never measures, and the absence of cancer entails nothing about them.

**Written back into the protocol (section 4):** the condition-versus-measurement test is applied to
what the criterion asserts, not to what a site would do to check it; and a criterion entailed by a
resolved condition is resolved.

---

## Theme 4 — Screening-visit procedures the protocol names explicitly (2 labels)

| Case | Criterion | pass 1 | pass 2 | Decided |
|---|---|---|---|---|
| AK-020 | NCT03819153-E7 retinopathy, fundus exam within 90 days | unknown | not_met | **unknown** |
| AK-027 | NCT06717698-E7 retinopathy, eye exam within 90 days | unknown | not_met | **unknown** |

Both trials exclude uncontrolled diabetic retinopathy and both say how it must be established: by a
fundus examination performed within the 90 days before screening. Patient `1be83f06` has an
ophthalmic encounter on 2025-06-24 recording intraocular pressures of 14 mmHg and LogMAR acuity of
0 in each eye. Pass 2 treated that as sufficient to rule retinopathy out.

Pass 1 stands. The encounter is 342 days before screening, outside the stated window, and
intraocular pressure and visual acuity do not grade a retina. A retina nobody has looked at is not a
retina that is normal, and this is exactly the criterion where a coordinator would order the
examination rather than assume it.

This does not conflict with Theme 3. There, the excluded finding could not exist because the disease
that produces it does not; here the patient does have type 2 diabetes, so the finding could exist
and nothing in the record speaks to it.

Neither changes an outcome: AK-020 and AK-027 are both `ineligible` on inclusion criteria.

---

## Theme 5 — Reading a criterion's scope (5 labels)

| Case | Criterion | pass 1 | pass 2 | Decided |
|---|---|---|---|---|
| AK-002 | NCT01131676-I2 drug naive or pre-treated, therapy unchanged 12 weeks | not_met | met | **met** |
| AK-003 | NCT01131676-I2 | not_met | met | **met** |
| AK-026 | NCT05748834-E7 GI disease interfering with absorption | unknown | met | **met** |
| AK-029 | NCT06717698-I7 ACEi/ARB at maximum labelled or tolerated dose | unknown | met | **unknown** |
| AK-033 | NCT07252908-E17 poorly controlled T2D or fasting glucose > 10 mmol/L | unknown | not_met | **not_met** |

**AK-002 and AK-003, EMPA-REG inclusion 2.** Pass 1 read the bullet as presupposing diabetes and
marked it `not_met` for two patients who have prediabetes only. That double-counts inclusion 1,
which is where the diabetes requirement lives. The operative content of the bullet is that the
patient is drug naive or on background therapy and that antidiabetic therapy has been unchanged for
12 weeks; a patient with no antidiabetic order on a current chart satisfies both. Pass 2 wins.
Neither case changes: both are `ineligible` on inclusions 1 and 3.

**AK-026, the tucatinib absorption exclusion.** Pass 1 abstained because patient `2211f478`'s chart
stops in 2016. But the currency rule governs how *absence* is read, and this is presence: cystic
fibrosis is an active condition from 1984-10-15 and pancreatin 600 mg was ordered on 2016-02-15,
which together document exocrine pancreatic insufficiency — a malabsorption syndrome, the example
the criterion itself names. An active chronic diagnosis does not expire and does not need the last
decade documented. Pass 2 wins, and this is the one adjudication that moves a case: AK-026 goes from
`needs_review` to `ineligible`, and becomes the only case in the key decided by an exclusion alone.

**AK-029, the maximum-dose RAAS criterion.** Pass 2 established that an ACE inhibitor is in place
and stable, which is true and is not what the criterion asks. Lisinopril 10 mg is a quarter of the
40 mg labelled maximum, and the record carries no titration note, no intolerance and no investigator
opinion, so neither the maximum-labelled branch nor the maximum-tolerated branch can be
established. Pass 1 stands. Both passes had already agreed `unknown` on the same drug at the same
dose for AK-007, so this makes the key internally consistent.

**AK-033, the TQC3721 glycaemia exclusion.** Pass 1 abstained on two grounds: the chart's glucose is
not marked as fasting, and "poorly controlled" is undefined. Both are answerable here. A *random*
glucose of 93.45 mg/dL on 2025-06-03 is 5.19 mmol/L, and a random value below the threshold bounds
the fasting value below it rather than leaving it open; and an HbA1c of 7.58% on the same date is
above target but is not poorly controlled diabetes under any usual reading. Pass 2 wins. This is
also the one place in the key where a unit conversion decides a label rather than merely
complicating one.

---

## Theme 6 — Two results that cannot both be true (4 labels)

| Case | Criterion | pass 1 | pass 2 | Decided |
|---|---|---|---|---|
| AK-003 | NCT01131676-E4 GFR < 30 mL/min (MDRD) | unknown | not_met | **unknown** |
| AK-016 | NCT03315143-I2 eGFR 25-60 mL/min/1.73 m2 | unknown | not_met | **unknown** |
| AK-031 | NCT06717698-I1 female of non-childbearing potential | unknown | met | **unknown** |
| AK-031 | NCT06717698-E1 pregnant, breast-feeding, or of childbearing potential | unknown | not_met | **unknown** |

Patient `f870c432`'s chart records, on 2025-09-25, an MDRD eGFR of 84.289 mL/min and a serum
creatinine of 2.578 mg/dL. Those two numbers are incompatible: a creatinine of 2.578 mg/dL in a
56-year-old man gives an MDRD eGFR near 30, not 84. Pass 2 took the reported eGFR at face value on
both pairs. Pass 1 abstained, and stands: choosing one of two mutually inconsistent same-day results
is picking, not reading. Neither case changes — AK-003 is `ineligible` on inclusions 1 and 3, AK-016
on inclusion 1 — so the decision costs nothing and keeps the key from asserting a number it cannot
defend.

**Written back into the protocol (section 5):** where two results recorded on the same date are
mutually inconsistent under the equation the criterion names, the criterion is `unknown`.

The two AK-031 labels are the same failure in a different costume. Pass 2 inferred that a
58-year-old woman is of non-childbearing potential. She almost certainly is. It is not in the
record: no menopausal status, no hysterectomy, no sterilisation, and no encounter since 1991-06-08.
Inferring an eligibility fact from a demographic plausibility is the behaviour this key exists to
detect, so it cannot be built into the key. Pass 1 stands on both, and the exclusion follows the
inclusion because it is conditioned on the same undetermined fact.

---

## What the adjudication changed about the protocol

Three sharpenings, all recorded above and all written into `protocol.md`:

1. **Chart currency** (section 4): twelve months from the last encounter, and absence over any
   window is readable on a current chart.
2. **Entailment** (section 4): a criterion whose subject matter is entailed by a condition the chart
   resolves as absent resolves too; a criterion demanding a positive finding from a study procedure
   does not.
3. **Contradictory results** (section 5): same-date results that cannot both be true make the
   criterion `unknown`.

None of the three was invented to reach a particular outcome. The first and second were adopted
against pass 1, the third for it; between them they touched 19 cases and moved one.
