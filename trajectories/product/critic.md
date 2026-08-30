# Trajectory

**Calls:** 2 | **Prompt tokens:** 5647 | **Completion tokens:** 157 | **Estimated cost:** $0.0129

| # | Agent | Model | Tier | Retries | Tokens | Cost | Outcome |
|---|---|---|---|---:|---:|---:|---|
| 1 | critic | venice/claude-sonnet-5 | `json_schema` | 0 | 2915 | $0.0066 | validated |
| 2 | critic | venice/claude-sonnet-5 | `json_schema` | 0 | 2889 | $0.0063 | validated |

## Standing instructions

Identical on every call below, so printed once rather than before each.

```
# Back-translation check

You are the last gate between a compiler and a patient. A previous step turned one sentence of a
clinical trial protocol into an executable predicate. That predicate has been rendered back into
English by code, deterministically, with no model involved. Your job is to compare the two English
sentences and say whether they mean the same thing.

You are not being asked to review the protocol, to improve the wording, to judge whether the
criterion is sensible, or to suggest a better formalisation. You are being asked one question about
two sentences.

## Input

Sentence A is the protocol text, quoted verbatim.
Sentence B is the compiled predicate, rendered back into English.

## Output

- `agrees`: true only when B says the same thing as A.
- `severity`: one of `equivalent`, `narrower`, `broader`, `contradicts`.
- `reason`: one sentence naming the specific difference, or stating that there is none. Name the
  thing that differs - the bound, the unit, the window, the anchor, the connective - not a general
  impression.

## The four verdicts

`equivalent`
: B admits exactly the patients A admits. Wording, ordering and terminology may differ freely.
  "serum creatinine at most 1.5 mg/dL" and "creatinine <= 1.5 mg/dL" are equivalent.

`narrower`
: Every patient B admits, A admits, but A admits patients B does not. B screens people out that
  the protocol would have let in.

`broader`
: Every patient A admits, B admits, but B admits patients A does not. B lets people in that the
  protocol would have excluded.

`contradicts`
: B is not a restriction or a relaxation of A but a different assertion: a reversed comparison, a
  different quantity, a different concept, a missing negation.

If B is narrower in one respect and broader in another, answer `contradicts`. If you cannot tell
which of A or B is the wider set, answer `contradicts` and say so in the reason. There is no
verdict for "close enough", and inventing one by choosing `equivalent` is the single most damaging
thing you can do here.

## On agreeing

The compiler that produced B is usually right, and B will usually look plausible. That is exactly
why this check exists: a plausible near-miss is the failure mode nobody catches downstream.

A critic that agrees by default is worse than no critic at all. It does not merely fail to find the
mistake, it certifies it - the compiled predicate then carries an explicit review saying it matched
the protocol, and the criterion is trusted precisely because you looked at it. Every `equivalent`
you return is a claim you are making on the record.

So do not soften a real difference into a note in the reason field while still answering
`equivalent`. If the reason field would contain the word "although", "slightly", "essentially" or
"minor", the verdict is not `equivalent`.

The reverse failure is real too. Do not manufacture a disagreement to look rigorous. Different
words for the same set are `equivalent`; so are a different unit spelling, a different concept
name, a reordered conjunction, and a rendering that spells out something A left implicit but
unambiguous. Only a difference in which patients qualify counts.

## Anything not stated is not a difference

Judge only what the two sentences say. B is rendered from a fixed vocabulary and will often be more
literal than A. Literalness is not a difference. Absence is: if A carries a condition, a bound, a
window or an exception that B does not mention at all, that is a difference, and B is broader for
it.

## Worked examples

### 1. A threshold that flipped strict to inclusive

A: Platelet count greater than 100 x 10^9/L.
B: platelet count at least 100 x10^9/L

One character of difference, one patient of difference: A excludes a count of exactly 100 and B
admits it. B admits everyone A admits, plus that patient, and nobody else.

Verdict: `broader`. Reason: A requires the count to exceed 100 while B admits a count of exactly
100.

A borderline threshold is not a rounding detail. It is the entire content of the criterion, and the
patients it decides are by definition the marginal ones.

### 2. A window anchored to the wrong event

A: No systemic corticosteroids within 3 months prior to screening.
B: no documented prescription for systemic corticosteroids, recorded within the 3 months before
enrolment

The span matches. The anchor does not. Screening and enrolment are different dates and the gap
between them is often weeks, so the two sentences cover different stretches of the chart, and a
patient dosed between the two dates is judged differently by each.

Verdict: `contradicts`. Reason: A measures the three months back from screening and B measures them
back from enrolment, which are different dates.

This one is worth dwelling on because B reads correctly. Every number matches, the drug matches,
the direction of the exclusion matches. One noun is wrong. Read the anchor of every window.

### 3. An "or" compiled as an "and"

A: Prior treatment with an anthracycline or a taxane.
B: a documented anthracycline regimen and a documented taxane regimen

A is satisfied by either drug class. B requires both, so a patient who had only an anthracycline
satisfies A and fails B, and every patient satisfying B satisfies A.

Verdict: `narrower`. Reason: A is satisfied by either drug class and B requires both.

Note that `narrower` is not a lesser finding than `broader`. On an inclusion criterion this
silently screens out patients the trial wanted; on an exclusion criterion it silently admits
patients the trial wanted kept out. Either way the protocol is not being applied.

### 4. A genuine equivalent

A: Age 18 years or older at the time of consent.
B: age at least 18 years

Verdict: `equivalent`. Reason: both admit exactly the patients aged 18 years or more.

B does not restate "at the time of consent", but for an age floor the anchor does not change who
qualifies: a patient 18 or older at consent is 18 or older at every later date. This is the case
where an unmentioned detail genuinely is not a difference, and it is narrower than it looks - a
window on a lab value or a diagnosis is never in this category.

## Reminder

One question, two sentences, four possible answers, one sentence of reason. Nothing you write here
is a suggestion to anyone; a verdict other than `equivalent` causes the criterion to be marked
unresolved and routed to a human reviewer, which is the correct outcome whenever you are not
certain the two sentences pick out the same patients.

```

## 1. critic on venice/claude-sonnet-5

- **Started:** 2026-08-30T10:35:10Z
- **Tier used:** `json_schema`
- **Retries:** 0
- **Tokens:** 2818 in / 97 out
- **Estimated cost:** $0.0066
- **Outcome:** validated

### Request

```
Sentence A, quoted from the protocol:
Type 2 Diabetes Mellitus with glycosylated hemoglobin (HbA1c) ≥7%.

Sentence B, the compiled predicate rendered back into English:
a documented diagnosis of Type 2 Diabetes Mellitus and glycosylated hemoglobin (HbA1c) at least 7%

Does B say the same thing as A?
```

### Attempt 1, tier `json_schema`

Response:

```
{"agrees": true, "severity": "equivalent", "reason": "Both require a Type 2 Diabetes Mellitus diagnosis combined with HbA1c of 7% or greater; 'documented diagnosis' is an implicit but unambiguous rendering of the condition in A."}
```

Validated against the schema.

### Result

```json
{
  "agrees": true,
  "severity": "equivalent",
  "reason": "Both require a Type 2 Diabetes Mellitus diagnosis combined with HbA1c of 7% or greater; 'documented diagnosis' is an implicit but unambiguous rendering of the condition in A."
}
```

## 2. critic on venice/claude-sonnet-5

- **Started:** 2026-08-30T10:35:10Z
- **Tier used:** `json_schema`
- **Retries:** 0
- **Tokens:** 2829 in / 60 out
- **Estimated cost:** $0.0063
- **Outcome:** validated

### Request

```
Sentence A, quoted from the protocol:
Estimated glomerular filtration rate (eGFR) ≥25 and ≤60 milliliter/minute (mL/min)/1.73 square meter (m^2).

Sentence B, the compiled predicate rendered back into English:
Estimated glomerular filtration rate (eGFR) between 25 and 60 mL/min/1.73m^2 inclusive

Does B say the same thing as A?
```

### Attempt 1, tier `json_schema`

Response:

```
{"agrees": true, "severity": "equivalent", "reason": "Both admit eGFR values from 25 to 60 mL/min/1.73m^2 inclusive."}
```

Validated against the schema.

### Result

```json
{
  "agrees": true,
  "severity": "equivalent",
  "reason": "Both admit eGFR values from 25 to 60 mL/min/1.73m^2 inclusive."
}
```

## Cost

| Agent | Calls | Prompt | Completion | Cost |
|---|---:|---:|---:|---:|
| critic | 2 | 5647 | 157 | $0.0129 |

| Model | Calls | Prompt | Completion | Cost |
|---|---:|---:|---:|---:|
| claude-sonnet-5 | 2 | 5647 | 157 | $0.0129 |

**Total:** 5804 tokens, $0.0129
