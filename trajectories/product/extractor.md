# Trajectory

**Calls:** 4 | **Prompt tokens:** 8298 | **Completion tokens:** 339 | **Estimated cost:** $0.0200

| # | Agent | Model | Tier | Retries | Tokens | Cost | Outcome |
|---|---|---|---|---:|---:|---:|---|
| 1 | extractor | venice/claude-sonnet-5 | `json_schema` | 0 | 2886 | $0.0063 | validated |
| 2 | extractor | venice/claude-sonnet-5 | `json_schema` | 0 | 2973 | $0.0075 | validated |
| 3 | extractor | venice/claude-sonnet-5 | `json_schema` | 0 | 2778 | $0.0062 | validated |
| 4 | extractor | venice/claude-sonnet-5 | `gate` | 0 | 0 | unpriced | validated |

## 1. extractor on venice/claude-sonnet-5

- **Started:** 2026-08-30T10:35:10Z
- **Tier used:** `json_schema`
- **Retries:** 0
- **Tokens:** 2819 in / 67 out
- **Estimated cost:** $0.0063
- **Outcome:** validated

### Instructions

```
# Assertion detection in a clinical note

You are reading one clinical note and answering one question about it: for each of the concepts
listed below, does this note assert that concept **about this patient, as a current or historical
fact**?

This is assertion detection, not summarisation. Do not describe the note, do not condense it, do
not report what is clinically important in it, and do not comment on the care. A note full of
significant findings that mentions none of the listed concepts produces no output at all, and
that is a correct answer.

Nothing downstream reads prose you write. Only the concept, the quoted sentence, the assertion
class and the date are consumed, and each of them is checked mechanically before it is used.

## What to return for each finding

- **concept** — one of the concepts listed in the request, written exactly as it is listed there.
  A concept that is not on the list has nowhere to go; do not invent one.
- **sentence** — the sentence from the note that carries the assertion, **quoted exactly**. Copy
  the characters. Do not correct spelling, expand an abbreviation, tidy the punctuation, join two
  sentences, or trim a clause you think is irrelevant. A sentence that cannot be found in the note
  is discarded along with the finding it came with, because a paraphrase has stopped being a
  citation and there is no way to tell afterwards which version was being asserted.
- **assertion** — one of the six classes below.
- **date** — the date the sentence itself gives for the event, as `YYYY-MM-DD`. Give a date only
  when the sentence names one that can be written in full: "on 14 March 2026" can, "in 2019",
  "last month" and "three years ago" cannot. Return null for those. Do not use the date the note
  was written, and do not compute a date from an interval.

One sentence may carry several findings, and each one is returned separately. A sentence such as
"Comorbidity: prediabetes, sleep apnoea on CPAP since 2022, no hypertension, no diabetes" asserts
two things and denies two others, on four different concepts, all from the same quote.

## The six assertion classes

`present`
: The note states the concept as a fact about this patient, now or in the past. A resolved
  episode is still `present` — it happened.
  *"Presented with an inferior STEMI on 14 March 2026, treated with primary PCI."*
  *"Admitted with decompensated heart failure in 2013; no recurrence since."*

`absent`
: The note states that this patient does not have the concept, or has never had it. An explicit
  denial is information, not silence, and is worth returning.
  *"No history of myocardial infarction."*
  *"Denies prior stroke or TIA."*

`family_history`
: The concept belongs to a blood relative. It is never about the patient, however the sentence is
  worded and whatever section of the note it sits in. A mention under a family-history heading is
  about the family.
  *"Father had an MI in his fifties."*

`hypothetical`
: The concept is planned, considered, offered, conditional, or being ruled in — and has not
  happened. Being on a waiting list is the strongest form of planned there is, and it still means
  the operation has not been done.
  *"Will consider ICD implantation if the EF remains below 35%."*
  *"Listed for functional endoscopic sinus surgery."*

`uncertain`
: The concept is suspected, queried, or offered as a working diagnosis that has not been settled.
  A test that would settle it is often still pending.
  *"Query paroxysmal AF; holter pending."*
  *"Diabetic nephropathy is the working diagnosis but no biopsy has been done."*

`other_subject`
: The concept belongs to someone who is neither the patient nor a blood relative — a partner, a
  carer, a housemate, a donor. Use this rather than `family_history` when the person named is not
  a relative, because the two mean different things to a clinician.
  *"His partner is currently on treatment for smear positive pulmonary TB."*

## How the classes are used

Only `present` and `absent` produce anything. The other four are recorded and discarded. Do not
promote a finding into `present` because it feels significant, and do not demote one into
`uncertain` because you are unsure whether the concept was listed — an unsure classification is
still a classification, and hedging it puts a query in the chart where a diagnosis belongs, or
the reverse.

## Returning nothing

An empty list is a common and correct answer, and it is the required answer when:

- none of the listed concepts appears in the note;
- the concept appears only as a word inside a phrase that means something else. "Old right
  occipital infarct" is not a myocardial infarction. "Mesenteric ischaemia" is not ischaemic heart
  disease. "Renal colic" is not chronic kidney disease. Match the concept, not the token;
- the note mentions a drug, a device or a service associated with the concept but does not assert
  the concept. Being on furosemide is not a diagnosis of heart failure;
- the concept appears only in a heading, a template field, or a list of things to ask about at the
  next appointment.

There is no penalty for a short answer, and no credit for a long one. A finding you are not
prepared to attach a verbatim sentence to should not be returned at all.

```

### Request

```
Note type: Discharge summary
Note date: 2025-03-18

Concepts:
- Type 2 Diabetes Mellitus
- glycosylated hemoglobin (HbA1c)
- Estimated glomerular filtration rate (eGFR)

Note text:
Discharge summary - Coronary Care Unit

DOA 14/03/2025   DOD 18/03/2025

Presented with an inferior STEMI on 14 March 2025 and was treated with primary PCI to the right
coronary artery, one drug eluting stent, door to balloon 52 minutes.

Peak troponin 8400 ng/L. Echo the following morning showed inferior hypokinesia with an EF of
48%.

Uncomplicated recovery. Brief run of accelerated idioventricular rhythm on day 1, self
terminating, no treatment given.

Discharged on ticagrelor 90 mg bd for 12 months, aspirin 75 mg od indefinitely, bisoprolol
2.5 mg od, ramipril 2.5 mg od, atorvastatin 80 mg nocte.

He tells me his brother had a stent at 47 and his mother has angina.

Cardiac rehab referral made. Not to drive for one week. GP to check lipids and renal function at
four weeks.
```

### Attempt 1, tier `json_schema`

Response:

```
{"findings":[]}
```

Validated against the schema.

### Result

```json
{
  "findings": []
}
```

## 2. extractor on venice/claude-sonnet-5

- **Started:** 2026-08-30T10:35:10Z
- **Tier used:** `json_schema`
- **Retries:** 0
- **Tokens:** 2778 in / 195 out
- **Estimated cost:** $0.0075
- **Outcome:** validated

### Instructions

```
# Assertion detection in a clinical note

You are reading one clinical note and answering one question about it: for each of the concepts
listed below, does this note assert that concept **about this patient, as a current or historical
fact**?

This is assertion detection, not summarisation. Do not describe the note, do not condense it, do
not report what is clinically important in it, and do not comment on the care. A note full of
significant findings that mentions none of the listed concepts produces no output at all, and
that is a correct answer.

Nothing downstream reads prose you write. Only the concept, the quoted sentence, the assertion
class and the date are consumed, and each of them is checked mechanically before it is used.

## What to return for each finding

- **concept** — one of the concepts listed in the request, written exactly as it is listed there.
  A concept that is not on the list has nowhere to go; do not invent one.
- **sentence** — the sentence from the note that carries the assertion, **quoted exactly**. Copy
  the characters. Do not correct spelling, expand an abbreviation, tidy the punctuation, join two
  sentences, or trim a clause you think is irrelevant. A sentence that cannot be found in the note
  is discarded along with the finding it came with, because a paraphrase has stopped being a
  citation and there is no way to tell afterwards which version was being asserted.
- **assertion** — one of the six classes below.
- **date** — the date the sentence itself gives for the event, as `YYYY-MM-DD`. Give a date only
  when the sentence names one that can be written in full: "on 14 March 2026" can, "in 2019",
  "last month" and "three years ago" cannot. Return null for those. Do not use the date the note
  was written, and do not compute a date from an interval.

One sentence may carry several findings, and each one is returned separately. A sentence such as
"Comorbidity: prediabetes, sleep apnoea on CPAP since 2022, no hypertension, no diabetes" asserts
two things and denies two others, on four different concepts, all from the same quote.

## The six assertion classes

`present`
: The note states the concept as a fact about this patient, now or in the past. A resolved
  episode is still `present` — it happened.
  *"Presented with an inferior STEMI on 14 March 2026, treated with primary PCI."*
  *"Admitted with decompensated heart failure in 2013; no recurrence since."*

`absent`
: The note states that this patient does not have the concept, or has never had it. An explicit
  denial is information, not silence, and is worth returning.
  *"No history of myocardial infarction."*
  *"Denies prior stroke or TIA."*

`family_history`
: The concept belongs to a blood relative. It is never about the patient, however the sentence is
  worded and whatever section of the note it sits in. A mention under a family-history heading is
  about the family.
  *"Father had an MI in his fifties."*

`hypothetical`
: The concept is planned, considered, offered, conditional, or being ruled in — and has not
  happened. Being on a waiting list is the strongest form of planned there is, and it still means
  the operation has not been done.
  *"Will consider ICD implantation if the EF remains below 35%."*
  *"Listed for functional endoscopic sinus surgery."*

`uncertain`
: The concept is suspected, queried, or offered as a working diagnosis that has not been settled.
  A test that would settle it is often still pending.
  *"Query paroxysmal AF; holter pending."*
  *"Diabetic nephropathy is the working diagnosis but no biopsy has been done."*

`other_subject`
: The concept belongs to someone who is neither the patient nor a blood relative — a partner, a
  carer, a housemate, a donor. Use this rather than `family_history` when the person named is not
  a relative, because the two mean different things to a clinician.
  *"His partner is currently on treatment for smear positive pulmonary TB."*

## How the classes are used

Only `present` and `absent` produce anything. The other four are recorded and discarded. Do not
promote a finding into `present` because it feels significant, and do not demote one into
`uncertain` because you are unsure whether the concept was listed — an unsure classification is
still a classification, and hedging it puts a query in the chart where a diagnosis belongs, or
the reverse.

## Returning nothing

An empty list is a common and correct answer, and it is the required answer when:

- none of the listed concepts appears in the note;
- the concept appears only as a word inside a phrase that means something else. "Old right
  occipital infarct" is not a myocardial infarction. "Mesenteric ischaemia" is not ischaemic heart
  disease. "Renal colic" is not chronic kidney disease. Match the concept, not the token;
- the note mentions a drug, a device or a service associated with the concept but does not assert
  the concept. Being on furosemide is not a diagnosis of heart failure;
- the concept appears only in a heading, a template field, or a list of things to ask about at the
  next appointment.

There is no penalty for a short answer, and no credit for a long one. A finding you are not
prepared to attach a verbatim sentence to should not be returned at all.

```

### Request

```
Note type: Cardiology clinic letter
Note date: 2025-06-10

Concepts:
- Type 2 Diabetes Mellitus
- glycosylated hemoglobin (HbA1c)
- Estimated glomerular filtration rate (eGFR)

Note text:
Dear Dr Salmond

Thank you for asking me to see this 55 year old man again, three months after his inferior
infarct.

He is limited more by his back than by his heart. Walks 20 minutes on the flat. No chest pain
since discharge and no breathlessness lying flat.

Repeat echo today: EF 44%, mild mitral regurgitation, normal right ventricle. LDL 2.9 mmol/L on
atorvastatin 80 mg. HbA1c 5.4%.

He does not have diabetes and never has. A single raised fasting glucose in 2011 was not
reproduced.

We would consider an ICD if the ejection fraction is still below 35% at the nine month scan, but
on today's numbers that looks unlikely.

Continue current treatment. I will see him once more in December and then discharge him back to
you.

Yours sincerely
Dr M. Farrow
```

### Attempt 1, tier `json_schema`

Response:

```
{"findings":[{"concept":"glycosylated hemoglobin (HbA1c)","sentence":"HbA1c 5.4%.","assertion":"present","date":null},{"concept":"Type 2 Diabetes Mellitus","sentence":"He does not have diabetes and never has.","assertion":"absent","date":null}]}
```

Validated against the schema.

### Result

```json
{
  "findings": [
    {
      "concept": "glycosylated hemoglobin (HbA1c)",
      "sentence": "HbA1c 5.4%.",
      "assertion": "present",
      "date": null
    },
    {
      "concept": "Type 2 Diabetes Mellitus",
      "sentence": "He does not have diabetes and never has.",
      "assertion": "absent",
      "date": null
    }
  ]
}
```

## 3. extractor on venice/claude-sonnet-5

- **Started:** 2026-08-30T10:35:10Z
- **Tier used:** `json_schema`
- **Retries:** 0
- **Tokens:** 2701 in / 77 out
- **Estimated cost:** $0.0062
- **Outcome:** validated

### Instructions

```
# Assertion detection in a clinical note

You are reading one clinical note and answering one question about it: for each of the concepts
listed below, does this note assert that concept **about this patient, as a current or historical
fact**?

This is assertion detection, not summarisation. Do not describe the note, do not condense it, do
not report what is clinically important in it, and do not comment on the care. A note full of
significant findings that mentions none of the listed concepts produces no output at all, and
that is a correct answer.

Nothing downstream reads prose you write. Only the concept, the quoted sentence, the assertion
class and the date are consumed, and each of them is checked mechanically before it is used.

## What to return for each finding

- **concept** — one of the concepts listed in the request, written exactly as it is listed there.
  A concept that is not on the list has nowhere to go; do not invent one.
- **sentence** — the sentence from the note that carries the assertion, **quoted exactly**. Copy
  the characters. Do not correct spelling, expand an abbreviation, tidy the punctuation, join two
  sentences, or trim a clause you think is irrelevant. A sentence that cannot be found in the note
  is discarded along with the finding it came with, because a paraphrase has stopped being a
  citation and there is no way to tell afterwards which version was being asserted.
- **assertion** — one of the six classes below.
- **date** — the date the sentence itself gives for the event, as `YYYY-MM-DD`. Give a date only
  when the sentence names one that can be written in full: "on 14 March 2026" can, "in 2019",
  "last month" and "three years ago" cannot. Return null for those. Do not use the date the note
  was written, and do not compute a date from an interval.

One sentence may carry several findings, and each one is returned separately. A sentence such as
"Comorbidity: prediabetes, sleep apnoea on CPAP since 2022, no hypertension, no diabetes" asserts
two things and denies two others, on four different concepts, all from the same quote.

## The six assertion classes

`present`
: The note states the concept as a fact about this patient, now or in the past. A resolved
  episode is still `present` — it happened.
  *"Presented with an inferior STEMI on 14 March 2026, treated with primary PCI."*
  *"Admitted with decompensated heart failure in 2013; no recurrence since."*

`absent`
: The note states that this patient does not have the concept, or has never had it. An explicit
  denial is information, not silence, and is worth returning.
  *"No history of myocardial infarction."*
  *"Denies prior stroke or TIA."*

`family_history`
: The concept belongs to a blood relative. It is never about the patient, however the sentence is
  worded and whatever section of the note it sits in. A mention under a family-history heading is
  about the family.
  *"Father had an MI in his fifties."*

`hypothetical`
: The concept is planned, considered, offered, conditional, or being ruled in — and has not
  happened. Being on a waiting list is the strongest form of planned there is, and it still means
  the operation has not been done.
  *"Will consider ICD implantation if the EF remains below 35%."*
  *"Listed for functional endoscopic sinus surgery."*

`uncertain`
: The concept is suspected, queried, or offered as a working diagnosis that has not been settled.
  A test that would settle it is often still pending.
  *"Query paroxysmal AF; holter pending."*
  *"Diabetic nephropathy is the working diagnosis but no biopsy has been done."*

`other_subject`
: The concept belongs to someone who is neither the patient nor a blood relative — a partner, a
  carer, a housemate, a donor. Use this rather than `family_history` when the person named is not
  a relative, because the two mean different things to a clinician.
  *"His partner is currently on treatment for smear positive pulmonary TB."*

## How the classes are used

Only `present` and `absent` produce anything. The other four are recorded and discarded. Do not
promote a finding into `present` because it feels significant, and do not demote one into
`uncertain` because you are unsure whether the concept was listed — an unsure classification is
still a classification, and hedging it puts a query in the chart where a diagnosis belongs, or
the reverse.

## Returning nothing

An empty list is a common and correct answer, and it is the required answer when:

- none of the listed concepts appears in the note;
- the concept appears only as a word inside a phrase that means something else. "Old right
  occipital infarct" is not a myocardial infarction. "Mesenteric ischaemia" is not ischaemic heart
  disease. "Renal colic" is not chronic kidney disease. Match the concept, not the token;
- the note mentions a drug, a device or a service associated with the concept but does not assert
  the concept. Being on furosemide is not a diagnosis of heart failure;
- the concept appears only in a heading, a template field, or a list of things to ask about at the
  next appointment.

There is no penalty for a short answer, and no credit for a long one. A finding you are not
prepared to attach a verbatim sentence to should not be returned at all.

```

### Request

```
Note type: GP consultation
Note date: 2025-10-08

Concepts:
- Type 2 Diabetes Mellitus
- glycosylated hemoglobin (HbA1c)
- Estimated glomerular filtration rate (eGFR)

Note text:
Med review. 15 minute appointment, ran over.

Main issue today is the back. Wants something stronger than co-codamol. I have said no and
explained why; he took it reasonably.

Cardiac side is quiet. No angina since March, taking everything, ticagrelor due to stop in March
2026.

Sleep is poor. His partner is currently on treatment for smear positive pulmonary TB and he is
worried about it. Contact screening arranged through the chest clinic; he has no cough and no
weight loss.

BP 128/78. Weight 104 kg, up 3 kg since June.

Actions: physio referral for the back, chest clinic contact screening, review 3/12.
```

### Attempt 1, tier `json_schema`

Response:

```
{"findings":[]}
```

Validated against the schema.

### Result

```json
{
  "findings": []
}
```

## 4. extractor on venice/claude-sonnet-5

- **Started:** 2026-08-30T10:35:10Z
- **Tier used:** `gate`
- **Retries:** 0
- **Tokens:** 0 in / 0 out
- **Estimated cost:** unpriced
- **Outcome:** validated

### Instructions

```
Extraction gate summary. No request was sent for this step.
```

### Request

```
Read 3 note(s): 1 coded row(s), 1 documented negation(s), 0 rejected.
  absent: 1
  present: 1
```

### Attempt 1, tier `gate`

Response:

```
{
  "notes": 3,
  "evidence": 1,
  "negations": 1,
  "discarded": 0,
  "counts_by_assertion": {
    "present": 1,
    "absent": 1
  },
  "failed_notes": [],
  "rejections": []
}
```

Validated against the schema.

### Result

```json
{
  "notes": 3,
  "evidence": 1,
  "negations": 1,
  "discarded": 0,
  "counts_by_assertion": {
    "present": 1,
    "absent": 1
  },
  "failed_notes": [],
  "rejections": []
}
```

## Cost

| Agent | Calls | Prompt | Completion | Cost |
|---|---:|---:|---:|---:|
| extractor | 4 | 8298 | 339 | $0.0200 (+1 unpriced) |

| Model | Calls | Prompt | Completion | Cost |
|---|---:|---:|---:|---:|
| claude-sonnet-5 | 4 | 8298 | 339 | $0.0200 (+1 unpriced) |

**Total:** 8637 tokens, $0.0200 (+1 unpriced)
