# Trajectory

**Calls:** 31 | **Prompt tokens:** 137532 | **Completion tokens:** 3520 | **Estimated cost:** $0.3103

| # | Agent | Model | Tier | Retries | Tokens | Cost | Outcome |
|---|---|---|---|---:|---:|---:|---|
| 1 | compiler | venice/claude-sonnet-5 | `json_object` | 1 | 13805 | $0.0303 | validated |
| 2 | compiler | venice/claude-sonnet-5 | `json_object` | 1 | 13697 | $0.0291 | validated |
| 3 | compiler | venice/claude-sonnet-5 | `json_object` | 1 | 14024 | $0.0324 | validated |
| 4 | compiler | venice/claude-sonnet-5 | `json_object` | 1 | 13557 | $0.0281 | validated |
| 5 | compiler | venice/claude-sonnet-5 | `json_object` | 1 | 13931 | $0.0317 | validated |
| 6 | compiler | venice/claude-sonnet-5 | `json_object` | 1 | 13644 | $0.0289 | validated |
| 7 | compiler | venice/claude-sonnet-5 | `json_object` | 1 | 13899 | $0.0312 | validated |
| 8 | compiler | venice/claude-sonnet-5 | `json_object` | 1 | 13658 | $0.0289 | validated |
| 9 | resolver | venice/claude-sonnet-5 | `memory` | 0 | 0 | unpriced | validated |
| 10 | critic | venice/claude-sonnet-5 | `json_schema` | 0 | 2915 | $0.0066 | validated |
| 11 | critic | venice/claude-sonnet-5 | `json_schema` | 0 | 2889 | $0.0063 | validated |
| 12 | extractor | venice/claude-sonnet-5 | `json_schema` | 0 | 2886 | $0.0063 | validated |
| 13 | extractor | venice/claude-sonnet-5 | `json_schema` | 0 | 2973 | $0.0075 | validated |
| 14 | extractor | venice/claude-sonnet-5 | `json_schema` | 0 | 2778 | $0.0062 | validated |
| 15 | extractor | venice/claude-sonnet-5 | `gate` | 0 | 0 | unpriced | validated |
| 16 | writer | venice/claude-sonnet-5 | `json_schema` | 0 | 2007 | $0.0046 | validated |
| 17 | writer | venice/claude-sonnet-5 | `prose_check` | 0 | 0 | unpriced | validated |
| 18 | writer | venice/claude-sonnet-5 | `json_schema` | 0 | 2144 | $0.0049 | validated |
| 19 | writer | venice/claude-sonnet-5 | `prose_check` | 0 | 0 | unpriced | validated |
| 20 | writer | venice/claude-sonnet-5 | `json_schema` | 0 | 2075 | $0.0047 | validated |
| 21 | writer | venice/claude-sonnet-5 | `prose_check` | 0 | 0 | unpriced | validated |
| 22 | writer | venice/claude-sonnet-5 | `json_schema` | 0 | 1983 | $0.0044 | validated |
| 23 | writer | venice/claude-sonnet-5 | `prose_check` | 0 | 0 | unpriced | validated |
| 24 | writer | venice/claude-sonnet-5 | `json_schema` | 0 | 2045 | $0.0046 | validated |
| 25 | writer | venice/claude-sonnet-5 | `prose_check` | 0 | 0 | unpriced | validated |
| 26 | writer | venice/claude-sonnet-5 | `json_schema` | 0 | 2013 | $0.0045 | validated |
| 27 | writer | venice/claude-sonnet-5 | `prose_check` | 0 | 0 | unpriced | validated |
| 28 | writer | venice/claude-sonnet-5 | `json_schema` | 0 | 2095 | $0.0046 | validated |
| 29 | writer | venice/claude-sonnet-5 | `prose_check` | 0 | 0 | unpriced | validated |
| 30 | writer | venice/claude-sonnet-5 | `json_schema` | 0 | 2034 | $0.0046 | validated |
| 31 | writer | venice/claude-sonnet-5 | `prose_check` | 0 | 0 | unpriced | validated |

## 1. compiler on venice/claude-sonnet-5

- **Started:** 2026-08-30T10:35:10Z
- **Tier used:** `json_object`
- **Retries:** 1
- **Tokens:** 13466 in / 339 out
- **Estimated cost:** $0.0303
- **Outcome:** validated

### Instructions

```
# Criteria compiler

You formalise one span of a clinical trial's eligibility criteria into a machine-checkable
predicate. A downstream engine will evaluate that predicate against a patient's structured record
and produce a screening verdict. You never see a patient and you never decide eligibility.

You are given one span at a time, together with the section it appeared under and, where the
protocol nested sub-conditions beneath it, its children. Treat the whole unit as one criterion.

## The only judgement that matters

A criterion you formalise incorrectly is worse than a criterion you decline to formalise. The
engine has an explicit `unsupported` predicate; a criterion marked unsupported goes to a research
coordinator, who reads it and decides. That is a normal, safe, expected outcome. A predicate that
looks right and means something slightly different produces a confident wrong verdict that nobody
catches.

So: when the span does not map cleanly onto the vocabulary below, return `unsupported` with a
reason. Do not approximate. Do not drop a qualifier to make something fit. Do not invent a
threshold the protocol did not state.

Use `unsupported` when the span:

- depends on clinical judgement — "in the opinion of the investigator", "otherwise unsuitable",
  "clinically significant", "adequate organ function" without stated numbers;
- depends on something no chart records — willingness to comply, ability to attend visits,
  informed consent, contraception intentions, geographic availability;
- names a threshold relative to something the engine cannot resolve, such as "above the upper
  limit of normal" (the reference range is laboratory-specific and is not in the record);
- describes a process rather than a state — "must complete a washout", "will be randomised";
- is a class of drug or a category of disease broad enough that no single code captures it, and
  the protocol does not enumerate members;
- nests more deeply than the schema allows.

### Which kind of unsupported

Every `unsupported` criterion also carries a `settlement`, and the choice matters more than it
looks. It decides whether one criterion holds up the whole screening.

**`at_visit`** — the criterion is settled when the patient comes in, and would be settled the same
way for every patient in the world. No chart that has ever been written could answer it, so its
being unanswered here says nothing about *this* patient. A coordinator confirms it at the screening
visit, and the packet lists it for them.

> Signed written informed consent.
> Willing and able to comply with the study schedule.
> Planned coronary procedure or surgery after randomization.
> Planning to start an SGLT2 inhibitor during the study.
> In the investigator's opinion, unsuitable for the study.
> Women of childbearing potential must agree to use contraception during the trial.

**`from_data`** — the criterion asks about the patient's recorded history or state, and we simply
could not formalise the question. That is a gap in what we know about this patient, and it does hold
up the screening.

> Adequate organ function. *(about the record; no threshold stated)*
> Any clinically significant abnormality on screening laboratory tests. *(about the record)*
> Lower extremity complications such as skin ulcer, infection, osteomyelitis and gangrene.
> *(about the record; an open list this schema cannot enumerate)*
> Alanine aminotransferase above the upper limit of normal. *(about the record; the range is
> laboratory-specific and not in it)*

The test to apply, in one sentence: **would a complete and perfect medical record answer this?** If
yes, and we merely failed to express it, that is `from_data`. If even a perfect record could not,
because the answer does not exist until the patient is in the room, that is `at_visit`.

When you are unsure, choose `from_data`. It is the cautious answer: it sends the criterion to a
human either way, and it does not let a verdict through on a criterion that should have stopped it.

## Vocabulary

**`observation`** — a numeric comparison against a measurement: laboratory values, vital signs,
scores. Give the analyte as the protocol names it, the operator, the number, and the unit exactly
as written. `between` is for a two-sided range and takes both bounds. Never convert units; the
engine converts, and it knows which conversions are safe.

**`condition`, `medication`, `procedure`** — whether something is on the chart. `presence`
is `present` when the protocol requires it and `absent` when the protocol requires its absence.

Note carefully: an exclusion criterion that reads "history of myocardial infarction" is a
**`present`** predicate under an **exclusion** criterion. Do not negate it yourself — the engine
knows that a met exclusion rules the patient out. Only use `absent` when the protocol itself
states an absence as a requirement, such as an inclusion criterion reading "no history of
malignancy".

**`demographic`** — age and sex only.

**`all_of` / `any_of` / `not`** — for spans that carry several conditions. "eGFR ≥25 and ≤60" is a
single `observation` with `between`, not a composite. "On an ACE inhibitor or an ARB" is `any_of`.
Sub-bullets beneath a parent bullet are almost always conjunctive: `all_of`.

## Temporal windows

Attach a window whenever the protocol bounds the evidence in time: "within 6 months prior to
screening", "in the last 30 days", "no myocardial infarction within 12 weeks". Use the number and
unit the protocol gives.

Protocols anchor windows to different events — screening, enrolment, randomisation, consent — and
those are genuinely different dates. The engine anchors everything to the screening date. If the
span anchors to something else and the difference could plausibly matter, say so in `notes`; if
the anchor is doing real work in the criterion, return `unsupported`.

## Quoting

`source_quote` must be the span reproduced character for character, including its punctuation and
its unicode operators. It is checked against the protocol text automatically, and a criterion whose
quote does not match is discarded. Do not tidy, expand abbreviations, or normalise `≥` to `>=`.

## Spans that are not criteria

Registry text contains section headings, cross-references and standard boilerplate. If the span is
one of those, set `is_criterion` to false and say why in `notes`. This is a correct answer, not a
failure.

## Concepts

Give the concept's `text` as the protocol names it. Leave `codes` empty — terminology resolution is
a separate step with its own controls. A code you guess here will be trusted downstream.

```

### Request

```
Section: inclusion

Criterion:
Type 2 Diabetes Mellitus with glycosylated hemoglobin (HbA1c) ≥7%.
```

### Attempt 1, tier `json_schema`

The provider rejected the request:

```
TapeMiss: no recorded answer for this request.
  model:  claude-sonnet-5
  system: "# Criteria compiler\n\nYou formalise one span of a clinical trial's eligibility cr"
  user:   'Section: inclusion\n\nCriterion:\nType 2 Diabetes Mellitus with glycosylated hemoglobin (HbA1c) ≥7%.'
The code has changed since the tape was recorded. Re-record with a key, or check out the commit the tape belongs to.
```

### Attempt 2, tier `json_object`

Restarted with:

```
[system]
# Criteria compiler

You formalise one span of a clinical trial's eligibility criteria into a machine-checkable
predicate. A downstream engine will evaluate that predicate against a patient's structured record
and produce a screening verdict. You never see a patient and you never decide eligibility.

You are given one span at a time, together with the section it appeared under and, where the
protocol nested sub-conditions beneath it, its children. Treat the whole unit as one criterion.

## The only judgement that matters

A criterion you formalise incorrectly is worse than a criterion you decline to formalise. The
engine has an explicit `unsupported` predicate; a criterion marked unsupported goes to a research
coordinator, who reads it and decides. That is a normal, safe, expected outcome. A predicate that
looks right and means something slightly different produces a confident wrong verdict that nobody
catches.

So: when the span does not map cleanly onto the vocabulary below, return `unsupported` with a
reason. Do not approximate. Do not drop a qualifier to make something fit. Do not invent a
threshold the protocol did not state.

Use `unsupported` when the span:

- depends on clinical judgement — "in the opinion of the investigator", "otherwise unsuitable",
  "clinically significant", "adequate organ function" without stated numbers;
- depends on something no chart records — willingness to comply, ability to attend visits,
  informed consent, contraception intentions, geographic availability;
- names a threshold relative to something the engine cannot resolve, such as "above the upper
  limit of normal" (the reference range is laboratory-specific and is not in the record);
- describes a process rather than a state — "must complete a washout", "will be randomised";
- is a class of drug or a category of disease broad enough that no single code captures it, and
  the protocol does not enumerate members;
- nests more deeply than the schema allows.

### Which kind of unsupported

Every `unsupported` criterion also carries a `settlement`, and the choice matters more than it
looks. It decides whether one criterion holds up the whole screening.

**`at_visit`** — the criterion is settled when the patient comes in, and would be settled the same
way for every patient in the world. No chart that has ever been written could answer it, so its
being unanswered here says nothing about *this* patient. A coordinator confirms it at the screening
visit, and the packet lists it for them.

> Signed written informed consent.
> Willing and able to comply with the study schedule.
> Planned coronary procedure or surgery after randomization.
> Planning to start an SGLT2 inhibitor during the study.
> In the investigator's opinion, unsuitable for the study.
> Women of childbearing potential must agree to use contraception during the trial.

**`from_data`** — the criterion asks about the patient's recorded history or state, and we simply
could not formalise the question. That is a gap in what we know about this patient, and it does hold
up the screening.

> Adequate organ function. *(about the record; no threshold stated)*
> Any clinically significant abnormality on screening laboratory tests. *(about the record)*
> Lower extremity complications such as skin ulcer, infection, osteomyelitis and gangrene.
> *(about the record; an open list this schema cannot enumerate)*
> Alanine aminotransferase above the upper limit of normal. *(about the record; the range is
> laboratory-specific and not in it)*

The test to apply, in one sentence: **would a complete and perfect medical record answer this?** If
yes, and we merely failed to express it, that is `from_data`. If even a perfect record could not,
because the answer does not exist until the patient is in the room, that is `at_visit`.

When you are unsure, choose `from_data`. It is the cautious answer: it sends the criterion to a
human either way, and it does not let a verdict through on a criterion that should have stopped it.

## Vocabulary

**`observation`** — a numeric comparison against a measurement: laboratory values, vital signs,
scores. Give the analyte as the protocol names it, the operator, the number, and the unit exactly
as written. `between` is for a two-sided range and takes both bounds. Never convert units; the
engine converts, and it knows which conversions are safe.

**`condition`, `medication`, `procedure`** — whether something is on the chart. `presence`
is `present` when the protocol requires it and `absent` when the protocol requires its absence.

Note carefully: an exclusion criterion that reads "history of myocardial infarction" is a
**`present`** predicate under an **exclusion** criterion. Do not negate it yourself — the engine
knows that a met exclusion rules the patient out. Only use `absent` when the protocol itself
states an absence as a requirement, such as an inclusion criterion reading "no history of
malignancy".

**`demographic`** — age and sex only.

**`all_of` / `any_of` / `not`** — for spans that carry several conditions. "eGFR ≥25 and ≤60" is a
single `observation` with `between`, not a composite. "On an ACE inhibitor or an ARB" is `any_of`.
Sub-bullets beneath a parent bullet are almost always conjunctive: `all_of`.

## Temporal windows

Attach a window whenever the protocol bounds the evidence in time: "within 6 months prior to
screening", "in the last 30 days", "no myocardial infarction within 12 weeks". Use the number and
unit the protocol gives.

Protocols anchor windows to different events — screening, enrolment, randomisation, consent — and
those are genuinely different dates. The engine anchors everything to the screening date. If the
span anchors to something else and the difference could plausibly matter, say so in `notes`; if
the anchor is doing real work in the criterion, return `unsupported`.

## Quoting

`source_quote` must be the span reproduced character for character, including its punctuation and
its unicode operators. It is checked against the protocol text automatically, and a criterion whose
quote does not match is discarded. Do not tidy, expand abbreviations, or normalise `≥` to `>=`.

## Spans that are not criteria

Registry text contains section headings, cross-references and standard boilerplate. If the span is
one of those, set `is_criterion` to false and say why in `notes`. This is a correct answer, not a
failure.

## Concepts

Give the concept's `text` as the protocol names it. Leave `codes` empty — terminology resolution is
a separate step with its own controls. A code you guess here will be trusted downstream.


Reply with a single JSON object and nothing else. It must conform to this JSON schema:

{
  "type": "object",
  "description": "The result of formalising one span of eligibility text. Set is_criterion to false when the span is a heading, a note to readers, or registry boilerplate rather than a condition a patient can meet.",
  "properties": {
    "is_criterion": {
      "type": "boolean"
    },
    "kind": {
      "description": "Only needed when the span sits under no inclusion or exclusion header.",
      "anyOf": [
        {
          "type": "string",
          "enum": [
            "inclusion",
            "exclusion"
          ]
        },
        {
          "type": "null"
        }
      ]
    },
    "source_quote": {
      "type": [
        "string",
        "null"
      ],
      "description": "The span copied verbatim, character for character."
    },
    "predicate": {
      "anyOf": [
        {
          "anyOf": [
            {
              "type": "object",
              "description": "A numeric comparison against a measurement: labs, vitals, scores.",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "observation"
                  ]
                },
                "concept": {
                  "type": "object",
                  "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                  "properties": {
                    "text": {
                      "type": "string"
                    },
                    "codes": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                        "properties": {
                          "system": {
                            "type": "string",
                            "enum": [
                              "LOINC",
                              "SNOMED",
                              "RxNorm",
                              "ICD10",
                              "UCUM"
                            ]
                          },
                          "code": {
                            "type": "string"
                          },
                          "display": {
                            "type": [
                              "string",
                              "null"
                            ]
                          }
                        },
                        "required": [
                          "system",
                          "code",
                          "display"
                        ],
                        "additionalProperties": false
                      }
                    }
                  },
                  "required": [
                    "text",
                    "codes"
                  ],
                  "additionalProperties": false
                },
                "op": {
                  "type": "string",
                  "enum": [
                    "<",
                    "<=",
                    ">",
                    ">=",
                    "==",
                    "!=",
                    "between"
                  ]
                },
                "value": {
                  "type": "number"
                },
                "value_high": {
                  "type": [
                    "number",
                    "null"
                  ]
                },
                "unit": {
                  "type": "string"
                },
                "window": {
                  "anyOf": [
                    {
                      "type": "object",
                      "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                      "properties": {
                        "relation": {
                          "type": "string",
                          "enum": [
                            "within",
                            "before",
                            "after",
                            "ever",
                            "current"
                          ]
                        },
                        "amount": {
                          "type": [
                            "integer",
                            "null"
                          ]
                        },
                        "unit": {
                          "anyOf": [
                            {
                              "type": "string",
                              "enum": [
                                "days",
                                "weeks",
                                "months",
                                "years"
                              ]
                            },
                            {
                              "type": "null"
                            }
                          ]
                        },
                        "anchor": {
                          "type": "string",
                          "enum": [
                            "screening",
                            "enrolment",
                            "randomisation",
                            "consent",
                            "first_dose"
                          ]
                        }
                      },
                      "required": [
                        "relation",
                        "amount",
                        "unit",
                        "anchor"
                      ],
                      "additionalProperties": false
                    },
                    {
                      "type": "null"
                    }
                  ]
                }
              },
              "required": [
                "type",
                "concept",
                "op",
                "value",
                "value_high",
                "unit",
                "window"
              ],
              "additionalProperties": false
            },
            {
              "type": "object",
              "description": "Whether a coded thing is on the chart at all: a condition, a drug, a procedure.",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "condition",
                    "medication",
                    "procedure"
                  ]
                },
                "concept": {
                  "type": "object",
                  "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                  "properties": {
                    "text": {
                      "type": "string"
                    },
                    "codes": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                        "properties": {
                          "system": {
                            "type": "string",
                            "enum": [
                              "LOINC",
                              "SNOMED",
                              "RxNorm",
                              "ICD10",
                              "UCUM"
                            ]
                          },
                          "code": {
                            "type": "string"
                          },
                          "display": {
                            "type": [
                              "string",
                              "null"
                            ]
                          }
                        },
                        "required": [
                          "system",
                          "code",
                          "display"
                        ],
                        "additionalProperties": false
                      }
                    }
                  },
                  "required": [
                    "text",
                    "codes"
                  ],
                  "additionalProperties": false
                },
                "presence": {
                  "type": "string",
                  "enum": [
                    "present",
                    "absent"
                  ]
                },
                "window": {
                  "anyOf": [
                    {
                      "type": "object",
                      "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                      "properties": {
                        "relation": {
                          "type": "string",
                          "enum": [
                            "within",
                            "before",
                            "after",
                            "ever",
                            "current"
                          ]
                        },
                        "amount": {
                          "type": [
                            "integer",
                            "null"
                          ]
                        },
                        "unit": {
                          "anyOf": [
                            {
                              "type": "string",
                              "enum": [
                                "days",
                                "weeks",
                                "months",
                                "years"
                              ]
                            },
                            {
                              "type": "null"
                            }
                          ]
                        },
                        "anchor": {
                          "type": "string",
                          "enum": [
                            "screening",
                            "enrolment",
                            "randomisation",
                            "consent",
                            "first_dose"
                          ]
                        }
                      },
                      "required": [
                        "relation",
                        "amount",
                        "unit",
                        "anchor"
                      ],
                      "additionalProperties": false
                    },
                    {
                      "type": "null"
                    }
                  ]
                }
              },
              "required": [
                "type",
                "concept",
                "presence",
                "window"
              ],
              "additionalProperties": false
            },
            {
              "type": "object",
              "description": "Age and sex, which come from the patient resource rather than from clinical events.",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "demographic"
                  ]
                },
                "field": {
                  "type": "string",
                  "enum": [
                    "age",
                    "sex"
                  ]
                },
                "op": {
                  "type": "string",
                  "enum": [
                    "<",
                    "<=",
                    ">",
                    ">=",
                    "==",
                    "!="
                  ]
                },
                "value": {
                  "type": [
                    "number",
                    "string"
                  ]
                },
                "unit": {
                  "type": [
                    "string",
                    "null"
                  ]
                }
              },
              "required": [
                "type",
                "field",
                "op",
                "value",
                "unit"
              ],
              "additionalProperties": false
            },
            {
              "type": "object",
              "description": "A criterion that cannot be honestly formalised. It stays unresolved forever, by design.\n\n`settlement` says *why* no chart can answer it, and the difference is load-bearing.\n\nA criterion settled `from_data` was a question about the patient's record that we failed to\nformalise \u2014 a threshold with no number, an open category. It is a gap, and it blocks a verdict.\n\nA criterion settled `at_visit` is not a gap at all. Signed informed consent, a procedure planned\nafter randomisation, the investigator's own judgement of the patient in person: these have the\nsame answer for every chart ever written, because they are settled when the patient comes in.\nTreating them as unresolved data made ELIGIBLE unreachable for every real protocol we hold \u2014 one\nconsent criterion and the screening abstains, which is not caution but paralysis.\n\nThe default is `from_data`, so a compiler that says nothing cannot thereby unblock a verdict.",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "unsupported"
                  ]
                },
                "reason": {
                  "type": "string"
                },
                "settlement": {
                  "type": "string",
                  "enum": [
                    "from_data",
                    "at_visit"
                  ]
                }
              },
              "required": [
                "type",
                "reason",
                "settlement"
              ],
              "additionalProperties": false
            },
            {
              "type": "object",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "all_of",
                    "any_of",
                    "not"
                  ]
                },
                "operands": {
                  "type": "array",
                  "items": {
                    "anyOf": [
                      {
                        "type": "object",
                        "description": "A numeric comparison against a measurement: labs, vitals, scores.",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "observation"
                            ]
                          },
                          "concept": {
                            "type": "object",
                            "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                            "properties": {
                              "text": {
                                "type": "string"
                              },
                              "codes": {
                                "type": "array",
                                "items": {
                                  "type": "object",
                                  "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                                  "properties": {
                                    "system": {
                                      "type": "string",
                                      "enum": [
                                        "LOINC",
                                        "SNOMED",
                                        "RxNorm",
                                        "ICD10",
                                        "UCUM"
                                      ]
                                    },
                                    "code": {
                                      "type": "string"
                                    },
                                    "display": {
                                      "type": [
                                        "string",
                                        "null"
                                      ]
                                    }
                                  },
                                  "required": [
                                    "system",
                                    "code",
                                    "display"
                                  ],
                                  "additionalProperties": false
                                }
                              }
                            },
                            "required": [
                              "text",
                              "codes"
                            ],
                            "additionalProperties": false
                          },
                          "op": {
                            "type": "string",
                            "enum": [
                              "<",
                              "<=",
                              ">",
                              ">=",
                              "==",
                              "!=",
                              "between"
                            ]
                          },
                          "value": {
                            "type": "number"
                          },
                          "value_high": {
                            "type": [
                              "number",
                              "null"
                            ]
                          },
                          "unit": {
                            "type": "string"
                          },
                          "window": {
                            "anyOf": [
                              {
                                "type": "object",
                                "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                                "properties": {
                                  "relation": {
                                    "type": "string",
                                    "enum": [
                                      "within",
                                      "before",
                                      "after",
                                      "ever",
                                      "current"
                                    ]
                                  },
                                  "amount": {
                                    "type": [
                                      "integer",
                                      "null"
                                    ]
                                  },
                                  "unit": {
                                    "anyOf": [
                                      {
                                        "type": "string",
                                        "enum": [
                                          "days",
                                          "weeks",
                                          "months",
                                          "years"
                                        ]
                                      },
                                      {
                                        "type": "null"
                                      }
                                    ]
                                  },
                                  "anchor": {
                                    "type": "string",
                                    "enum": [
                                      "screening",
                                      "enrolment",
                                      "randomisation",
                                      "consent",
                                      "first_dose"
                                    ]
                                  }
                                },
                                "required": [
                                  "relation",
                                  "amount",
                                  "unit",
                                  "anchor"
                                ],
                                "additionalProperties": false
                              },
                              {
                                "type": "null"
                              }
                            ]
                          }
                        },
                        "required": [
                          "type",
                          "concept",
                          "op",
                          "value",
                          "value_high",
                          "unit",
                          "window"
                        ],
                        "additionalProperties": false
                      },
                      {
                        "type": "object",
                        "description": "Whether a coded thing is on the chart at all: a condition, a drug, a procedure.",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "condition",
                              "medication",
                              "procedure"
                            ]
                          },
                          "concept": {
                            "type": "object",
                            "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                            "properties": {
                              "text": {
                                "type": "string"
                              },
                              "codes": {
                                "type": "array",
                                "items": {
                                  "type": "object",
                                  "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                                  "properties": {
                                    "system": {
                                      "type": "string",
                                      "enum": [
                                        "LOINC",
                                        "SNOMED",
                                        "RxNorm",
                                        "ICD10",
                                        "UCUM"
                                      ]
                                    },
                                    "code": {
                                      "type": "string"
                                    },
                                    "display": {
                                      "type": [
                                        "string",
                                        "null"
                                      ]
                                    }
                                  },
                                  "required": [
                                    "system",
                                    "code",
                                    "display"
                                  ],
                                  "additionalProperties": false
                                }
                              }
                            },
                            "required": [
                              "text",
                              "codes"
                            ],
                            "additionalProperties": false
                          },
                          "presence": {
                            "type": "string",
                            "enum": [
                              "present",
                              "absent"
                            ]
                          },
                          "window": {
                            "anyOf": [
                              {
                                "type": "object",
                                "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                                "properties": {
                                  "relation": {
                                    "type": "string",
                                    "enum": [
                                      "within",
                                      "before",
                                      "after",
                                      "ever",
                                      "current"
                                    ]
                                  },
                                  "amount": {
                                    "type": [
                                      "integer",
                                      "null"
                                    ]
                                  },
                                  "unit": {
                                    "anyOf": [
                                      {
                                        "type": "string",
                                        "enum": [
                                          "days",
                                          "weeks",
                                          "months",
                                          "years"
                                        ]
                                      },
                                      {
                                        "type": "null"
                                      }
                                    ]
                                  },
                                  "anchor": {
                                    "type": "string",
                                    "enum": [
                                      "screening",
                                      "enrolment",
                                      "randomisation",
                                      "consent",
                                      "first_dose"
                                    ]
                                  }
                                },
                                "required": [
                                  "relation",
                                  "amount",
                                  "unit",
                                  "anchor"
                                ],
                                "additionalProperties": false
                              },
                              {
                                "type": "null"
                              }
                            ]
                          }
                        },
                        "required": [
                          "type",
                          "concept",
                          "presence",
                          "window"
                        ],
                        "additionalProperties": false
                      },
                      {
                        "type": "object",
                        "description": "Age and sex, which come from the patient resource rather than from clinical events.",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "demographic"
                            ]
                          },
                          "field": {
                            "type": "string",
                            "enum": [
                              "age",
                              "sex"
                            ]
                          },
                          "op": {
                            "type": "string",
                            "enum": [
                              "<",
                              "<=",
                              ">",
                              ">=",
                              "==",
                              "!="
                            ]
                          },
                          "value": {
                            "type": [
                              "number",
                              "string"
                            ]
                          },
                          "unit": {
                            "type": [
                              "string",
                              "null"
                            ]
                          }
                        },
                        "required": [
                          "type",
                          "field",
                          "op",
                          "value",
                          "unit"
                        ],
                        "additionalProperties": false
                      },
                      {
                        "type": "object",
                        "description": "A criterion that cannot be honestly formalised. It stays unresolved forever, by design.\n\n`settlement` says *why* no chart can answer it, and the difference is load-bearing.\n\nA criterion settled `from_data` was a question about the patient's record that we failed to\nformalise \u2014 a threshold with no number, an open category. It is a gap, and it blocks a verdict.\n\nA criterion settled `at_visit` is not a gap at all. Signed informed consent, a procedure planned\nafter randomisation, the investigator's own judgement of the patient in person: these have the\nsame answer for every chart ever written, because they are settled when the patient comes in.\nTreating them as unresolved data made ELIGIBLE unreachable for every real protocol we hold \u2014 one\nconsent criterion and the screening abstains, which is not caution but paralysis.\n\nThe default is `from_data`, so a compiler that says nothing cannot thereby unblock a verdict.",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "unsupported"
                            ]
                          },
                          "reason": {
                            "type": "string"
                          },
                          "settlement": {
                            "type": "string",
                            "enum": [
                              "from_data",
                              "at_visit"
                            ]
                          }
                        },
                        "required": [
                          "type",
                          "reason",
                          "settlement"
                        ],
                        "additionalProperties": false
                      },
                      {
                        "type": "object",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "all_of",
                              "any_of",
                              "not"
                            ]
                          },
                          "operands": {
                            "type": "array",
                            "items": {
                              "anyOf": [
                                {
                                  "type": "object",
                                  "description": "A numeric comparison against a measurement: labs, vitals, scores.",
                                  "properties": {
                                    "type": {
                                      "type": "string",
                                      "enum": [
                                        "observation"
                                      ]
                                    },
                                    "concept": {
                                      "type": "object",
                                      "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                                      "properties": {
                                        "text": {
                                          "type": "string"
                                        },
                                        "codes": {
                                          "type": "array",
                                          "items": {
                                            "type": "object",
                                            "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                                            "properties": {
                                              "system": {
                                                "type": "string",
                                                "enum": [
                                                  "LOINC",
                                                  "SNOMED",
                                                  "RxNorm",
                                                  "ICD10",
                                                  "UCUM"
                                                ]
                                              },
                                              "code": {
                                                "type": "string"
                                              },
                                              "display": {
                                                "type": [
                                                  "string",
                                                  "null"
                                                ]
                                              }
                                            },
                                            "required": [
                                              "system",
                                              "code",
                                              "display"
                                            ],
                                            "additionalProperties": false
                                          }
                                        }
                                      },
                                      "required": [
                                        "text",
                                        "codes"
                                      ],
                                      "additionalProperties": false
                                    },
                                    "op": {
                                      "type": "string",
                                      "enum": [
                                        "<",
                                        "<=",
                                        ">",
                                        ">=",
                                        "==",
                                        "!=",
                                        "between"
                                      ]
                                    },
                                    "value": {
                                      "type": "number"
                                    },
                                    "value_high": {
                                      "type": [
                                        "number",
                                        "null"
                                      ]
                                    },
                                    "unit": {
                                      "type": "string"
                                    },
                                    "window": {
                                      "anyOf": [
                                        {
                                          "type": "object",
                                          "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                                          "properties": {
                                            "relation": {
                                              "type": "string",
                                              "enum": [
                                                "within",
                                                "before",
                                                "after",
                                                "ever",
                                                "current"
                                              ]
                                            },
                                            "amount": {
                                              "type": [
                                                "integer",
                                                "null"
                                              ]
                                            },
                                            "unit": {
                                              "anyOf": [
                                                {
                                                  "type": "string",
                                                  "enum": [
                                                    "days",
                                                    "weeks",
                                                    "months",
                                                    "years"
                                                  ]
                                                },
                                                {
                                                  "type": "null"
                                                }
                                              ]
                                            },
                                            "anchor": {
                                              "type": "string",
                                              "enum": [
                                                "screening",
                                                "enrolment",
                                                "randomisation",
                                                "consent",
                                                "first_dose"
                                              ]
                                            }
                                          },
                                          "required": [
                                            "relation",
                                            "amount",
                                            "unit",
                                            "anchor"
                                          ],
                                          "additionalProperties": false
                                        },
                                        {
                                          "type": "null"
                                        }
                                      ]
                                    }
                                  },
                                  "required": [
                                    "type",
                                    "concept",
                                    "op",
                                    "value",
                                    "value_high",
                                    "unit",
                                    "window"
                                  ],
                                  "additionalProperties": false
                                },
                                {
                                  "type": "object",
                                  "description": "Whether a coded thing is on the chart at all: a condition, a drug, a procedure.",
                                  "properties": {
                                    "type": {
                                      "type": "string",
                                      "enum": [
                                        "condition",
                                        "medication",
                                        "procedure"
                                      ]
                                    },
                                    "concept": {
                                      "type": "object",
                                      "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                                      "properties": {
                                        "text": {
                                          "type": "string"
                                        },
                                        "codes": {
                                          "type": "array",
                                          "items": {
                                            "type": "object",
                                            "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                                            "properties": {
                                              "system": {
                                                "type": "string",
                                                "enum": [
                                                  "LOINC",
                                                  "SNOMED",
                                                  "RxNorm",
                                                  "ICD10",
                                                  "UCUM"
                                                ]
                                              },
                                              "code": {
                                                "type": "string"
                                              },
                                              "display": {
                                                "type": [
                                                  "string",
                                                  "null"
                                                ]
                                              }
                                            },
                                            "required": [
                                              "system",
                                              "code",
                                              "display"
                                            ],
                                            "additionalProperties": false
                                          }
                                        }
                                      },
                                      "required": [
                                        "text",
                                        "codes"
                                      ],
                                      "additionalProperties": false
                                    },
                                    "presence": {
                                      "type": "string",
                                      "enum": [
                                        "present",
                                        "absent"
                                      ]
                                    },
                                    "window": {
                                      "anyOf": [
                                        {
                                          "type": "object",
                                          "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                                          "properties": {
                                            "relation": {
                                              "type": "string",
                                              "enum": [
                                                "within",
                                                "before",
                                                "after",
                                                "ever",
                                                "current"
                                              ]
                                            },
                                            "amount": {
                                              "type": [
                                                "integer",
                                                "null"
                                              ]
                                            },
                                            "unit": {
                                              "anyOf": [
                                                {
                                                  "type": "string",
                                                  "enum": [
                                                    "days",
                                                    "weeks",
                                                    "months",
                                                    "years"
                                                  ]
                                                },
                                                {
                                                  "type": "null"
                                                }
                                              ]
                                            },
                                            "anchor": {
                                              "type": "string",
                                              "enum": [
                                                "screening",
                                                "enrolment",
                                                "randomisation",
                                                "consent",
                                                "first_dose"
                                              ]
                                            }
                                          },
                                          "required": [
                                            "relation",
                                            "amount",
                                            "unit",
                                            "anchor"
                                          ],
                                          "additionalProperties": false
                                        },
                                        {
                                          "type": "null"
                                        }
                                      ]
                                    }
                                  },
                                  "required": [
                                    "type",
                                    "concept",
                                    "presence",
                                    "window"
                                  ],
                                  "additionalProperties": false
                                },
                                {
                                  "type": "object",
                                  "description": "Age and sex, which come from the patient resource rather than from clinical events.",
                                  "properties": {
                                    "type": {
                                      "type": "string",
                                      "enum": [
                                        "demographic"
                                      ]
                                    },
                                    "field": {
                                      "type": "string",
                                      "enum": [
                                        "age",
                                        "sex"
                                      ]
                                    },
                                    "op": {
                                      "type": "string",
                                      "enum": [
                                        "<",
                                        "<=",
                                        ">",
                                        ">=",
                                        "==",
                                        "!="
                                      ]
                                    },
                                    "value": {
                                      "type": [
                                        "number",
                                        "string"
                                      ]
                                    },
                                    "unit": {
                                      "type": [
                                        "string",
                                        "null"
                                      ]
                                    }
                                  },
                                  "required": [
                                    "type",
                                    "field",
                                    "op",
                                    "value",
                                    "unit"
                                  ],
                                  "additionalProperties": false
                                },
                                {
                                  "type": "object",
                                  "description": "A criterion that cannot be honestly formalised. It stays unresolved forever, by design.\n\n`settlement` says *why* no chart can answer it, and the difference is load-bearing.\n\nA criterion settled `from_data` was a question about the patient's record that we failed to\nformalise \u2014 a threshold with no number, an open category. It is a gap, and it blocks a verdict.\n\nA criterion settled `at_visit` is not a gap at all. Signed informed consent, a procedure planned\nafter randomisation, the investigator's own judgement of the patient in person: these have the\nsame answer for every chart ever written, because they are settled when the patient comes in.\nTreating them as unresolved data made ELIGIBLE unreachable for every real protocol we hold \u2014 one\nconsent criterion and the screening abstains, which is not caution but paralysis.\n\nThe default is `from_data`, so a compiler that says nothing cannot thereby unblock a verdict.",
                                  "properties": {
                                    "type": {
                                      "type": "string",
                                      "enum": [
                                        "unsupported"
                                      ]
                                    },
                                    "reason": {
                                      "type": "string"
                                    },
                                    "settlement": {
                                      "type": "string",
                                      "enum": [
                                        "from_data",
                                        "at_visit"
                                      ]
                                    }
                                  },
                                  "required": [
                                    "type",
                                    "reason",
                                    "settlement"
                                  ],
                                  "additionalProperties": false
                                }
                              ]
                            }
                          }
                        },
                        "required": [
                          "type",
                          "operands"
                        ],
                        "additionalProperties": false
                      }
                    ]
                  }
                }
              },
              "required": [
                "type",
                "operands"
              ],
              "additionalProperties": false
            }
          ]
        },
        {
          "type": "null"
        }
      ]
    },
    "notes": {
      "type": [
        "string",
        "null"
      ],
      "description": "Why this span was hard, or why it is not a criterion."
    }
  },
  "required": [
    "is_criterion",
    "kind",
    "source_quote",
    "predicate",
    "notes"
  ],
  "additionalProperties": false
}

[user]
Section: inclusion

Criterion:
Type 2 Diabetes Mellitus with glycosylated hemoglobin (HbA1c) ≥7%.
```

Response:

```
{
  "is_criterion": true,
  "kind": "inclusion",
  "source_quote": "Type 2 Diabetes Mellitus with glycosylated hemoglobin (HbA1c) ≥7%.",
  "predicate": {
    "type": "all_of",
    "operands": [
      {
        "type": "condition",
        "concept": {
          "text": "Type 2 Diabetes Mellitus",
          "codes": []
        },
        "presence": "present",
        "window": null
      },
      {
        "type": "observation",
        "concept": {
          "text": "glycosylated hemoglobin (HbA1c)",
          "codes": []
        },
        "op": ">=",
        "value": 7,
        "value_high": null,
        "unit": "%",
        "window": null
      }
    ]
  },
  "notes": null
}
```

Validated against the schema.

### Result

```json
{
  "is_criterion": true,
  "kind": "inclusion",
  "source_quote": "Type 2 Diabetes Mellitus with glycosylated hemoglobin (HbA1c) ≥7%.",
  "predicate": {
    "type": "all_of",
    "operands": [
      {
        "type": "condition",
        "concept": {
          "text": "Type 2 Diabetes Mellitus",
          "codes": []
        },
        "presence": "present",
        "window": null
      },
      {
        "type": "observation",
        "concept": {
          "text": "glycosylated hemoglobin (HbA1c)",
          "codes": []
        },
        "op": ">=",
        "value": 7.0,
        "value_high": null,
        "unit": "%",
        "window": null
      }
    ]
  },
  "notes": null
}
```

## 2. compiler on venice/claude-sonnet-5

- **Started:** 2026-08-30T10:35:10Z
- **Tier used:** `json_object`
- **Retries:** 1
- **Tokens:** 13482 in / 215 out
- **Estimated cost:** $0.0291
- **Outcome:** validated

### Instructions

```
# Criteria compiler

You formalise one span of a clinical trial's eligibility criteria into a machine-checkable
predicate. A downstream engine will evaluate that predicate against a patient's structured record
and produce a screening verdict. You never see a patient and you never decide eligibility.

You are given one span at a time, together with the section it appeared under and, where the
protocol nested sub-conditions beneath it, its children. Treat the whole unit as one criterion.

## The only judgement that matters

A criterion you formalise incorrectly is worse than a criterion you decline to formalise. The
engine has an explicit `unsupported` predicate; a criterion marked unsupported goes to a research
coordinator, who reads it and decides. That is a normal, safe, expected outcome. A predicate that
looks right and means something slightly different produces a confident wrong verdict that nobody
catches.

So: when the span does not map cleanly onto the vocabulary below, return `unsupported` with a
reason. Do not approximate. Do not drop a qualifier to make something fit. Do not invent a
threshold the protocol did not state.

Use `unsupported` when the span:

- depends on clinical judgement — "in the opinion of the investigator", "otherwise unsuitable",
  "clinically significant", "adequate organ function" without stated numbers;
- depends on something no chart records — willingness to comply, ability to attend visits,
  informed consent, contraception intentions, geographic availability;
- names a threshold relative to something the engine cannot resolve, such as "above the upper
  limit of normal" (the reference range is laboratory-specific and is not in the record);
- describes a process rather than a state — "must complete a washout", "will be randomised";
- is a class of drug or a category of disease broad enough that no single code captures it, and
  the protocol does not enumerate members;
- nests more deeply than the schema allows.

### Which kind of unsupported

Every `unsupported` criterion also carries a `settlement`, and the choice matters more than it
looks. It decides whether one criterion holds up the whole screening.

**`at_visit`** — the criterion is settled when the patient comes in, and would be settled the same
way for every patient in the world. No chart that has ever been written could answer it, so its
being unanswered here says nothing about *this* patient. A coordinator confirms it at the screening
visit, and the packet lists it for them.

> Signed written informed consent.
> Willing and able to comply with the study schedule.
> Planned coronary procedure or surgery after randomization.
> Planning to start an SGLT2 inhibitor during the study.
> In the investigator's opinion, unsuitable for the study.
> Women of childbearing potential must agree to use contraception during the trial.

**`from_data`** — the criterion asks about the patient's recorded history or state, and we simply
could not formalise the question. That is a gap in what we know about this patient, and it does hold
up the screening.

> Adequate organ function. *(about the record; no threshold stated)*
> Any clinically significant abnormality on screening laboratory tests. *(about the record)*
> Lower extremity complications such as skin ulcer, infection, osteomyelitis and gangrene.
> *(about the record; an open list this schema cannot enumerate)*
> Alanine aminotransferase above the upper limit of normal. *(about the record; the range is
> laboratory-specific and not in it)*

The test to apply, in one sentence: **would a complete and perfect medical record answer this?** If
yes, and we merely failed to express it, that is `from_data`. If even a perfect record could not,
because the answer does not exist until the patient is in the room, that is `at_visit`.

When you are unsure, choose `from_data`. It is the cautious answer: it sends the criterion to a
human either way, and it does not let a verdict through on a criterion that should have stopped it.

## Vocabulary

**`observation`** — a numeric comparison against a measurement: laboratory values, vital signs,
scores. Give the analyte as the protocol names it, the operator, the number, and the unit exactly
as written. `between` is for a two-sided range and takes both bounds. Never convert units; the
engine converts, and it knows which conversions are safe.

**`condition`, `medication`, `procedure`** — whether something is on the chart. `presence`
is `present` when the protocol requires it and `absent` when the protocol requires its absence.

Note carefully: an exclusion criterion that reads "history of myocardial infarction" is a
**`present`** predicate under an **exclusion** criterion. Do not negate it yourself — the engine
knows that a met exclusion rules the patient out. Only use `absent` when the protocol itself
states an absence as a requirement, such as an inclusion criterion reading "no history of
malignancy".

**`demographic`** — age and sex only.

**`all_of` / `any_of` / `not`** — for spans that carry several conditions. "eGFR ≥25 and ≤60" is a
single `observation` with `between`, not a composite. "On an ACE inhibitor or an ARB" is `any_of`.
Sub-bullets beneath a parent bullet are almost always conjunctive: `all_of`.

## Temporal windows

Attach a window whenever the protocol bounds the evidence in time: "within 6 months prior to
screening", "in the last 30 days", "no myocardial infarction within 12 weeks". Use the number and
unit the protocol gives.

Protocols anchor windows to different events — screening, enrolment, randomisation, consent — and
those are genuinely different dates. The engine anchors everything to the screening date. If the
span anchors to something else and the difference could plausibly matter, say so in `notes`; if
the anchor is doing real work in the criterion, return `unsupported`.

## Quoting

`source_quote` must be the span reproduced character for character, including its punctuation and
its unicode operators. It is checked against the protocol text automatically, and a criterion whose
quote does not match is discarded. Do not tidy, expand abbreviations, or normalise `≥` to `>=`.

## Spans that are not criteria

Registry text contains section headings, cross-references and standard boilerplate. If the span is
one of those, set `is_criterion` to false and say why in `notes`. This is a correct answer, not a
failure.

## Concepts

Give the concept's `text` as the protocol names it. Leave `codes` empty — terminology resolution is
a separate step with its own controls. A code you guess here will be trusted downstream.

```

### Request

```
Section: inclusion

Criterion:
Estimated glomerular filtration rate (eGFR) ≥25 and ≤60 milliliter/minute (mL/min)/1.73 square meter (m^2).
```

### Attempt 1, tier `json_schema`

The provider rejected the request:

```
TapeMiss: no recorded answer for this request.
  model:  claude-sonnet-5
  system: "# Criteria compiler\n\nYou formalise one span of a clinical trial's eligibility cr"
  user:   'Section: inclusion\n\nCriterion:\nEstimated glomerular filtration rate (eGFR) ≥25 and ≤60 milliliter/minute (mL/min)/1.73 square meter (m^2).'
The code has changed since the tape was recorded. Re-record with a key, or check out the commit the tape belongs to.
```

### Attempt 2, tier `json_object`

Restarted with:

```
[system]
# Criteria compiler

You formalise one span of a clinical trial's eligibility criteria into a machine-checkable
predicate. A downstream engine will evaluate that predicate against a patient's structured record
and produce a screening verdict. You never see a patient and you never decide eligibility.

You are given one span at a time, together with the section it appeared under and, where the
protocol nested sub-conditions beneath it, its children. Treat the whole unit as one criterion.

## The only judgement that matters

A criterion you formalise incorrectly is worse than a criterion you decline to formalise. The
engine has an explicit `unsupported` predicate; a criterion marked unsupported goes to a research
coordinator, who reads it and decides. That is a normal, safe, expected outcome. A predicate that
looks right and means something slightly different produces a confident wrong verdict that nobody
catches.

So: when the span does not map cleanly onto the vocabulary below, return `unsupported` with a
reason. Do not approximate. Do not drop a qualifier to make something fit. Do not invent a
threshold the protocol did not state.

Use `unsupported` when the span:

- depends on clinical judgement — "in the opinion of the investigator", "otherwise unsuitable",
  "clinically significant", "adequate organ function" without stated numbers;
- depends on something no chart records — willingness to comply, ability to attend visits,
  informed consent, contraception intentions, geographic availability;
- names a threshold relative to something the engine cannot resolve, such as "above the upper
  limit of normal" (the reference range is laboratory-specific and is not in the record);
- describes a process rather than a state — "must complete a washout", "will be randomised";
- is a class of drug or a category of disease broad enough that no single code captures it, and
  the protocol does not enumerate members;
- nests more deeply than the schema allows.

### Which kind of unsupported

Every `unsupported` criterion also carries a `settlement`, and the choice matters more than it
looks. It decides whether one criterion holds up the whole screening.

**`at_visit`** — the criterion is settled when the patient comes in, and would be settled the same
way for every patient in the world. No chart that has ever been written could answer it, so its
being unanswered here says nothing about *this* patient. A coordinator confirms it at the screening
visit, and the packet lists it for them.

> Signed written informed consent.
> Willing and able to comply with the study schedule.
> Planned coronary procedure or surgery after randomization.
> Planning to start an SGLT2 inhibitor during the study.
> In the investigator's opinion, unsuitable for the study.
> Women of childbearing potential must agree to use contraception during the trial.

**`from_data`** — the criterion asks about the patient's recorded history or state, and we simply
could not formalise the question. That is a gap in what we know about this patient, and it does hold
up the screening.

> Adequate organ function. *(about the record; no threshold stated)*
> Any clinically significant abnormality on screening laboratory tests. *(about the record)*
> Lower extremity complications such as skin ulcer, infection, osteomyelitis and gangrene.
> *(about the record; an open list this schema cannot enumerate)*
> Alanine aminotransferase above the upper limit of normal. *(about the record; the range is
> laboratory-specific and not in it)*

The test to apply, in one sentence: **would a complete and perfect medical record answer this?** If
yes, and we merely failed to express it, that is `from_data`. If even a perfect record could not,
because the answer does not exist until the patient is in the room, that is `at_visit`.

When you are unsure, choose `from_data`. It is the cautious answer: it sends the criterion to a
human either way, and it does not let a verdict through on a criterion that should have stopped it.

## Vocabulary

**`observation`** — a numeric comparison against a measurement: laboratory values, vital signs,
scores. Give the analyte as the protocol names it, the operator, the number, and the unit exactly
as written. `between` is for a two-sided range and takes both bounds. Never convert units; the
engine converts, and it knows which conversions are safe.

**`condition`, `medication`, `procedure`** — whether something is on the chart. `presence`
is `present` when the protocol requires it and `absent` when the protocol requires its absence.

Note carefully: an exclusion criterion that reads "history of myocardial infarction" is a
**`present`** predicate under an **exclusion** criterion. Do not negate it yourself — the engine
knows that a met exclusion rules the patient out. Only use `absent` when the protocol itself
states an absence as a requirement, such as an inclusion criterion reading "no history of
malignancy".

**`demographic`** — age and sex only.

**`all_of` / `any_of` / `not`** — for spans that carry several conditions. "eGFR ≥25 and ≤60" is a
single `observation` with `between`, not a composite. "On an ACE inhibitor or an ARB" is `any_of`.
Sub-bullets beneath a parent bullet are almost always conjunctive: `all_of`.

## Temporal windows

Attach a window whenever the protocol bounds the evidence in time: "within 6 months prior to
screening", "in the last 30 days", "no myocardial infarction within 12 weeks". Use the number and
unit the protocol gives.

Protocols anchor windows to different events — screening, enrolment, randomisation, consent — and
those are genuinely different dates. The engine anchors everything to the screening date. If the
span anchors to something else and the difference could plausibly matter, say so in `notes`; if
the anchor is doing real work in the criterion, return `unsupported`.

## Quoting

`source_quote` must be the span reproduced character for character, including its punctuation and
its unicode operators. It is checked against the protocol text automatically, and a criterion whose
quote does not match is discarded. Do not tidy, expand abbreviations, or normalise `≥` to `>=`.

## Spans that are not criteria

Registry text contains section headings, cross-references and standard boilerplate. If the span is
one of those, set `is_criterion` to false and say why in `notes`. This is a correct answer, not a
failure.

## Concepts

Give the concept's `text` as the protocol names it. Leave `codes` empty — terminology resolution is
a separate step with its own controls. A code you guess here will be trusted downstream.


Reply with a single JSON object and nothing else. It must conform to this JSON schema:

{
  "type": "object",
  "description": "The result of formalising one span of eligibility text. Set is_criterion to false when the span is a heading, a note to readers, or registry boilerplate rather than a condition a patient can meet.",
  "properties": {
    "is_criterion": {
      "type": "boolean"
    },
    "kind": {
      "description": "Only needed when the span sits under no inclusion or exclusion header.",
      "anyOf": [
        {
          "type": "string",
          "enum": [
            "inclusion",
            "exclusion"
          ]
        },
        {
          "type": "null"
        }
      ]
    },
    "source_quote": {
      "type": [
        "string",
        "null"
      ],
      "description": "The span copied verbatim, character for character."
    },
    "predicate": {
      "anyOf": [
        {
          "anyOf": [
            {
              "type": "object",
              "description": "A numeric comparison against a measurement: labs, vitals, scores.",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "observation"
                  ]
                },
                "concept": {
                  "type": "object",
                  "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                  "properties": {
                    "text": {
                      "type": "string"
                    },
                    "codes": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                        "properties": {
                          "system": {
                            "type": "string",
                            "enum": [
                              "LOINC",
                              "SNOMED",
                              "RxNorm",
                              "ICD10",
                              "UCUM"
                            ]
                          },
                          "code": {
                            "type": "string"
                          },
                          "display": {
                            "type": [
                              "string",
                              "null"
                            ]
                          }
                        },
                        "required": [
                          "system",
                          "code",
                          "display"
                        ],
                        "additionalProperties": false
                      }
                    }
                  },
                  "required": [
                    "text",
                    "codes"
                  ],
                  "additionalProperties": false
                },
                "op": {
                  "type": "string",
                  "enum": [
                    "<",
                    "<=",
                    ">",
                    ">=",
                    "==",
                    "!=",
                    "between"
                  ]
                },
                "value": {
                  "type": "number"
                },
                "value_high": {
                  "type": [
                    "number",
                    "null"
                  ]
                },
                "unit": {
                  "type": "string"
                },
                "window": {
                  "anyOf": [
                    {
                      "type": "object",
                      "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                      "properties": {
                        "relation": {
                          "type": "string",
                          "enum": [
                            "within",
                            "before",
                            "after",
                            "ever",
                            "current"
                          ]
                        },
                        "amount": {
                          "type": [
                            "integer",
                            "null"
                          ]
                        },
                        "unit": {
                          "anyOf": [
                            {
                              "type": "string",
                              "enum": [
                                "days",
                                "weeks",
                                "months",
                                "years"
                              ]
                            },
                            {
                              "type": "null"
                            }
                          ]
                        },
                        "anchor": {
                          "type": "string",
                          "enum": [
                            "screening",
                            "enrolment",
                            "randomisation",
                            "consent",
                            "first_dose"
                          ]
                        }
                      },
                      "required": [
                        "relation",
                        "amount",
                        "unit",
                        "anchor"
                      ],
                      "additionalProperties": false
                    },
                    {
                      "type": "null"
                    }
                  ]
                }
              },
              "required": [
                "type",
                "concept",
                "op",
                "value",
                "value_high",
                "unit",
                "window"
              ],
              "additionalProperties": false
            },
            {
              "type": "object",
              "description": "Whether a coded thing is on the chart at all: a condition, a drug, a procedure.",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "condition",
                    "medication",
                    "procedure"
                  ]
                },
                "concept": {
                  "type": "object",
                  "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                  "properties": {
                    "text": {
                      "type": "string"
                    },
                    "codes": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                        "properties": {
                          "system": {
                            "type": "string",
                            "enum": [
                              "LOINC",
                              "SNOMED",
                              "RxNorm",
                              "ICD10",
                              "UCUM"
                            ]
                          },
                          "code": {
                            "type": "string"
                          },
                          "display": {
                            "type": [
                              "string",
                              "null"
                            ]
                          }
                        },
                        "required": [
                          "system",
                          "code",
                          "display"
                        ],
                        "additionalProperties": false
                      }
                    }
                  },
                  "required": [
                    "text",
                    "codes"
                  ],
                  "additionalProperties": false
                },
                "presence": {
                  "type": "string",
                  "enum": [
                    "present",
                    "absent"
                  ]
                },
                "window": {
                  "anyOf": [
                    {
                      "type": "object",
                      "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                      "properties": {
                        "relation": {
                          "type": "string",
                          "enum": [
                            "within",
                            "before",
                            "after",
                            "ever",
                            "current"
                          ]
                        },
                        "amount": {
                          "type": [
                            "integer",
                            "null"
                          ]
                        },
                        "unit": {
                          "anyOf": [
                            {
                              "type": "string",
                              "enum": [
                                "days",
                                "weeks",
                                "months",
                                "years"
                              ]
                            },
                            {
                              "type": "null"
                            }
                          ]
                        },
                        "anchor": {
                          "type": "string",
                          "enum": [
                            "screening",
                            "enrolment",
                            "randomisation",
                            "consent",
                            "first_dose"
                          ]
                        }
                      },
                      "required": [
                        "relation",
                        "amount",
                        "unit",
                        "anchor"
                      ],
                      "additionalProperties": false
                    },
                    {
                      "type": "null"
                    }
                  ]
                }
              },
              "required": [
                "type",
                "concept",
                "presence",
                "window"
              ],
              "additionalProperties": false
            },
            {
              "type": "object",
              "description": "Age and sex, which come from the patient resource rather than from clinical events.",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "demographic"
                  ]
                },
                "field": {
                  "type": "string",
                  "enum": [
                    "age",
                    "sex"
                  ]
                },
                "op": {
                  "type": "string",
                  "enum": [
                    "<",
                    "<=",
                    ">",
                    ">=",
                    "==",
                    "!="
                  ]
                },
                "value": {
                  "type": [
                    "number",
                    "string"
                  ]
                },
                "unit": {
                  "type": [
                    "string",
                    "null"
                  ]
                }
              },
              "required": [
                "type",
                "field",
                "op",
                "value",
                "unit"
              ],
              "additionalProperties": false
            },
            {
              "type": "object",
              "description": "A criterion that cannot be honestly formalised. It stays unresolved forever, by design.\n\n`settlement` says *why* no chart can answer it, and the difference is load-bearing.\n\nA criterion settled `from_data` was a question about the patient's record that we failed to\nformalise \u2014 a threshold with no number, an open category. It is a gap, and it blocks a verdict.\n\nA criterion settled `at_visit` is not a gap at all. Signed informed consent, a procedure planned\nafter randomisation, the investigator's own judgement of the patient in person: these have the\nsame answer for every chart ever written, because they are settled when the patient comes in.\nTreating them as unresolved data made ELIGIBLE unreachable for every real protocol we hold \u2014 one\nconsent criterion and the screening abstains, which is not caution but paralysis.\n\nThe default is `from_data`, so a compiler that says nothing cannot thereby unblock a verdict.",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "unsupported"
                  ]
                },
                "reason": {
                  "type": "string"
                },
                "settlement": {
                  "type": "string",
                  "enum": [
                    "from_data",
                    "at_visit"
                  ]
                }
              },
              "required": [
                "type",
                "reason",
                "settlement"
              ],
              "additionalProperties": false
            },
            {
              "type": "object",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "all_of",
                    "any_of",
                    "not"
                  ]
                },
                "operands": {
                  "type": "array",
                  "items": {
                    "anyOf": [
                      {
                        "type": "object",
                        "description": "A numeric comparison against a measurement: labs, vitals, scores.",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "observation"
                            ]
                          },
                          "concept": {
                            "type": "object",
                            "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                            "properties": {
                              "text": {
                                "type": "string"
                              },
                              "codes": {
                                "type": "array",
                                "items": {
                                  "type": "object",
                                  "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                                  "properties": {
                                    "system": {
                                      "type": "string",
                                      "enum": [
                                        "LOINC",
                                        "SNOMED",
                                        "RxNorm",
                                        "ICD10",
                                        "UCUM"
                                      ]
                                    },
                                    "code": {
                                      "type": "string"
                                    },
                                    "display": {
                                      "type": [
                                        "string",
                                        "null"
                                      ]
                                    }
                                  },
                                  "required": [
                                    "system",
                                    "code",
                                    "display"
                                  ],
                                  "additionalProperties": false
                                }
                              }
                            },
                            "required": [
                              "text",
                              "codes"
                            ],
                            "additionalProperties": false
                          },
                          "op": {
                            "type": "string",
                            "enum": [
                              "<",
                              "<=",
                              ">",
                              ">=",
                              "==",
                              "!=",
                              "between"
                            ]
                          },
                          "value": {
                            "type": "number"
                          },
                          "value_high": {
                            "type": [
                              "number",
                              "null"
                            ]
                          },
                          "unit": {
                            "type": "string"
                          },
                          "window": {
                            "anyOf": [
                              {
                                "type": "object",
                                "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                                "properties": {
                                  "relation": {
                                    "type": "string",
                                    "enum": [
                                      "within",
                                      "before",
                                      "after",
                                      "ever",
                                      "current"
                                    ]
                                  },
                                  "amount": {
                                    "type": [
                                      "integer",
                                      "null"
                                    ]
                                  },
                                  "unit": {
                                    "anyOf": [
                                      {
                                        "type": "string",
                                        "enum": [
                                          "days",
                                          "weeks",
                                          "months",
                                          "years"
                                        ]
                                      },
                                      {
                                        "type": "null"
                                      }
                                    ]
                                  },
                                  "anchor": {
                                    "type": "string",
                                    "enum": [
                                      "screening",
                                      "enrolment",
                                      "randomisation",
                                      "consent",
                                      "first_dose"
                                    ]
                                  }
                                },
                                "required": [
                                  "relation",
                                  "amount",
                                  "unit",
                                  "anchor"
                                ],
                                "additionalProperties": false
                              },
                              {
                                "type": "null"
                              }
                            ]
                          }
                        },
                        "required": [
                          "type",
                          "concept",
                          "op",
                          "value",
                          "value_high",
                          "unit",
                          "window"
                        ],
                        "additionalProperties": false
                      },
                      {
                        "type": "object",
                        "description": "Whether a coded thing is on the chart at all: a condition, a drug, a procedure.",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "condition",
                              "medication",
                              "procedure"
                            ]
                          },
                          "concept": {
                            "type": "object",
                            "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                            "properties": {
                              "text": {
                                "type": "string"
                              },
                              "codes": {
                                "type": "array",
                                "items": {
                                  "type": "object",
                                  "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                                  "properties": {
                                    "system": {
                                      "type": "string",
                                      "enum": [
                                        "LOINC",
                                        "SNOMED",
                                        "RxNorm",
                                        "ICD10",
                                        "UCUM"
                                      ]
                                    },
                                    "code": {
                                      "type": "string"
                                    },
                                    "display": {
                                      "type": [
                                        "string",
                                        "null"
                                      ]
                                    }
                                  },
                                  "required": [
                                    "system",
                                    "code",
                                    "display"
                                  ],
                                  "additionalProperties": false
                                }
                              }
                            },
                            "required": [
                              "text",
                              "codes"
                            ],
                            "additionalProperties": false
                          },
                          "presence": {
                            "type": "string",
                            "enum": [
                              "present",
                              "absent"
                            ]
                          },
                          "window": {
                            "anyOf": [
                              {
                                "type": "object",
                                "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                                "properties": {
                                  "relation": {
                                    "type": "string",
                                    "enum": [
                                      "within",
                                      "before",
                                      "after",
                                      "ever",
                                      "current"
                                    ]
                                  },
                                  "amount": {
                                    "type": [
                                      "integer",
                                      "null"
                                    ]
                                  },
                                  "unit": {
                                    "anyOf": [
                                      {
                                        "type": "string",
                                        "enum": [
                                          "days",
                                          "weeks",
                                          "months",
                                          "years"
                                        ]
                                      },
                                      {
                                        "type": "null"
                                      }
                                    ]
                                  },
                                  "anchor": {
                                    "type": "string",
                                    "enum": [
                                      "screening",
                                      "enrolment",
                                      "randomisation",
                                      "consent",
                                      "first_dose"
                                    ]
                                  }
                                },
                                "required": [
                                  "relation",
                                  "amount",
                                  "unit",
                                  "anchor"
                                ],
                                "additionalProperties": false
                              },
                              {
                                "type": "null"
                              }
                            ]
                          }
                        },
                        "required": [
                          "type",
                          "concept",
                          "presence",
                          "window"
                        ],
                        "additionalProperties": false
                      },
                      {
                        "type": "object",
                        "description": "Age and sex, which come from the patient resource rather than from clinical events.",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "demographic"
                            ]
                          },
                          "field": {
                            "type": "string",
                            "enum": [
                              "age",
                              "sex"
                            ]
                          },
                          "op": {
                            "type": "string",
                            "enum": [
                              "<",
                              "<=",
                              ">",
                              ">=",
                              "==",
                              "!="
                            ]
                          },
                          "value": {
                            "type": [
                              "number",
                              "string"
                            ]
                          },
                          "unit": {
                            "type": [
                              "string",
                              "null"
                            ]
                          }
                        },
                        "required": [
                          "type",
                          "field",
                          "op",
                          "value",
                          "unit"
                        ],
                        "additionalProperties": false
                      },
                      {
                        "type": "object",
                        "description": "A criterion that cannot be honestly formalised. It stays unresolved forever, by design.\n\n`settlement` says *why* no chart can answer it, and the difference is load-bearing.\n\nA criterion settled `from_data` was a question about the patient's record that we failed to\nformalise \u2014 a threshold with no number, an open category. It is a gap, and it blocks a verdict.\n\nA criterion settled `at_visit` is not a gap at all. Signed informed consent, a procedure planned\nafter randomisation, the investigator's own judgement of the patient in person: these have the\nsame answer for every chart ever written, because they are settled when the patient comes in.\nTreating them as unresolved data made ELIGIBLE unreachable for every real protocol we hold \u2014 one\nconsent criterion and the screening abstains, which is not caution but paralysis.\n\nThe default is `from_data`, so a compiler that says nothing cannot thereby unblock a verdict.",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "unsupported"
                            ]
                          },
                          "reason": {
                            "type": "string"
                          },
                          "settlement": {
                            "type": "string",
                            "enum": [
                              "from_data",
                              "at_visit"
                            ]
                          }
                        },
                        "required": [
                          "type",
                          "reason",
                          "settlement"
                        ],
                        "additionalProperties": false
                      },
                      {
                        "type": "object",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "all_of",
                              "any_of",
                              "not"
                            ]
                          },
                          "operands": {
                            "type": "array",
                            "items": {
                              "anyOf": [
                                {
                                  "type": "object",
                                  "description": "A numeric comparison against a measurement: labs, vitals, scores.",
                                  "properties": {
                                    "type": {
                                      "type": "string",
                                      "enum": [
                                        "observation"
                                      ]
                                    },
                                    "concept": {
                                      "type": "object",
                                      "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                                      "properties": {
                                        "text": {
                                          "type": "string"
                                        },
                                        "codes": {
                                          "type": "array",
                                          "items": {
                                            "type": "object",
                                            "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                                            "properties": {
                                              "system": {
                                                "type": "string",
                                                "enum": [
                                                  "LOINC",
                                                  "SNOMED",
                                                  "RxNorm",
                                                  "ICD10",
                                                  "UCUM"
                                                ]
                                              },
                                              "code": {
                                                "type": "string"
                                              },
                                              "display": {
                                                "type": [
                                                  "string",
                                                  "null"
                                                ]
                                              }
                                            },
                                            "required": [
                                              "system",
                                              "code",
                                              "display"
                                            ],
                                            "additionalProperties": false
                                          }
                                        }
                                      },
                                      "required": [
                                        "text",
                                        "codes"
                                      ],
                                      "additionalProperties": false
                                    },
                                    "op": {
                                      "type": "string",
                                      "enum": [
                                        "<",
                                        "<=",
                                        ">",
                                        ">=",
                                        "==",
                                        "!=",
                                        "between"
                                      ]
                                    },
                                    "value": {
                                      "type": "number"
                                    },
                                    "value_high": {
                                      "type": [
                                        "number",
                                        "null"
                                      ]
                                    },
                                    "unit": {
                                      "type": "string"
                                    },
                                    "window": {
                                      "anyOf": [
                                        {
                                          "type": "object",
                                          "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                                          "properties": {
                                            "relation": {
                                              "type": "string",
                                              "enum": [
                                                "within",
                                                "before",
                                                "after",
                                                "ever",
                                                "current"
                                              ]
                                            },
                                            "amount": {
                                              "type": [
                                                "integer",
                                                "null"
                                              ]
                                            },
                                            "unit": {
                                              "anyOf": [
                                                {
                                                  "type": "string",
                                                  "enum": [
                                                    "days",
                                                    "weeks",
                                                    "months",
                                                    "years"
                                                  ]
                                                },
                                                {
                                                  "type": "null"
                                                }
                                              ]
                                            },
                                            "anchor": {
                                              "type": "string",
                                              "enum": [
                                                "screening",
                                                "enrolment",
                                                "randomisation",
                                                "consent",
                                                "first_dose"
                                              ]
                                            }
                                          },
                                          "required": [
                                            "relation",
                                            "amount",
                                            "unit",
                                            "anchor"
                                          ],
                                          "additionalProperties": false
                                        },
                                        {
                                          "type": "null"
                                        }
                                      ]
                                    }
                                  },
                                  "required": [
                                    "type",
                                    "concept",
                                    "op",
                                    "value",
                                    "value_high",
                                    "unit",
                                    "window"
                                  ],
                                  "additionalProperties": false
                                },
                                {
                                  "type": "object",
                                  "description": "Whether a coded thing is on the chart at all: a condition, a drug, a procedure.",
                                  "properties": {
                                    "type": {
                                      "type": "string",
                                      "enum": [
                                        "condition",
                                        "medication",
                                        "procedure"
                                      ]
                                    },
                                    "concept": {
                                      "type": "object",
                                      "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                                      "properties": {
                                        "text": {
                                          "type": "string"
                                        },
                                        "codes": {
                                          "type": "array",
                                          "items": {
                                            "type": "object",
                                            "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                                            "properties": {
                                              "system": {
                                                "type": "string",
                                                "enum": [
                                                  "LOINC",
                                                  "SNOMED",
                                                  "RxNorm",
                                                  "ICD10",
                                                  "UCUM"
                                                ]
                                              },
                                              "code": {
                                                "type": "string"
                                              },
                                              "display": {
                                                "type": [
                                                  "string",
                                                  "null"
                                                ]
                                              }
                                            },
                                            "required": [
                                              "system",
                                              "code",
                                              "display"
                                            ],
                                            "additionalProperties": false
                                          }
                                        }
                                      },
                                      "required": [
                                        "text",
                                        "codes"
                                      ],
                                      "additionalProperties": false
                                    },
                                    "presence": {
                                      "type": "string",
                                      "enum": [
                                        "present",
                                        "absent"
                                      ]
                                    },
                                    "window": {
                                      "anyOf": [
                                        {
                                          "type": "object",
                                          "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                                          "properties": {
                                            "relation": {
                                              "type": "string",
                                              "enum": [
                                                "within",
                                                "before",
                                                "after",
                                                "ever",
                                                "current"
                                              ]
                                            },
                                            "amount": {
                                              "type": [
                                                "integer",
                                                "null"
                                              ]
                                            },
                                            "unit": {
                                              "anyOf": [
                                                {
                                                  "type": "string",
                                                  "enum": [
                                                    "days",
                                                    "weeks",
                                                    "months",
                                                    "years"
                                                  ]
                                                },
                                                {
                                                  "type": "null"
                                                }
                                              ]
                                            },
                                            "anchor": {
                                              "type": "string",
                                              "enum": [
                                                "screening",
                                                "enrolment",
                                                "randomisation",
                                                "consent",
                                                "first_dose"
                                              ]
                                            }
                                          },
                                          "required": [
                                            "relation",
                                            "amount",
                                            "unit",
                                            "anchor"
                                          ],
                                          "additionalProperties": false
                                        },
                                        {
                                          "type": "null"
                                        }
                                      ]
                                    }
                                  },
                                  "required": [
                                    "type",
                                    "concept",
                                    "presence",
                                    "window"
                                  ],
                                  "additionalProperties": false
                                },
                                {
                                  "type": "object",
                                  "description": "Age and sex, which come from the patient resource rather than from clinical events.",
                                  "properties": {
                                    "type": {
                                      "type": "string",
                                      "enum": [
                                        "demographic"
                                      ]
                                    },
                                    "field": {
                                      "type": "string",
                                      "enum": [
                                        "age",
                                        "sex"
                                      ]
                                    },
                                    "op": {
                                      "type": "string",
                                      "enum": [
                                        "<",
                                        "<=",
                                        ">",
                                        ">=",
                                        "==",
                                        "!="
                                      ]
                                    },
                                    "value": {
                                      "type": [
                                        "number",
                                        "string"
                                      ]
                                    },
                                    "unit": {
                                      "type": [
                                        "string",
                                        "null"
                                      ]
                                    }
                                  },
                                  "required": [
                                    "type",
                                    "field",
                                    "op",
                                    "value",
                                    "unit"
                                  ],
                                  "additionalProperties": false
                                },
                                {
                                  "type": "object",
                                  "description": "A criterion that cannot be honestly formalised. It stays unresolved forever, by design.\n\n`settlement` says *why* no chart can answer it, and the difference is load-bearing.\n\nA criterion settled `from_data` was a question about the patient's record that we failed to\nformalise \u2014 a threshold with no number, an open category. It is a gap, and it blocks a verdict.\n\nA criterion settled `at_visit` is not a gap at all. Signed informed consent, a procedure planned\nafter randomisation, the investigator's own judgement of the patient in person: these have the\nsame answer for every chart ever written, because they are settled when the patient comes in.\nTreating them as unresolved data made ELIGIBLE unreachable for every real protocol we hold \u2014 one\nconsent criterion and the screening abstains, which is not caution but paralysis.\n\nThe default is `from_data`, so a compiler that says nothing cannot thereby unblock a verdict.",
                                  "properties": {
                                    "type": {
                                      "type": "string",
                                      "enum": [
                                        "unsupported"
                                      ]
                                    },
                                    "reason": {
                                      "type": "string"
                                    },
                                    "settlement": {
                                      "type": "string",
                                      "enum": [
                                        "from_data",
                                        "at_visit"
                                      ]
                                    }
                                  },
                                  "required": [
                                    "type",
                                    "reason",
                                    "settlement"
                                  ],
                                  "additionalProperties": false
                                }
                              ]
                            }
                          }
                        },
                        "required": [
                          "type",
                          "operands"
                        ],
                        "additionalProperties": false
                      }
                    ]
                  }
                }
              },
              "required": [
                "type",
                "operands"
              ],
              "additionalProperties": false
            }
          ]
        },
        {
          "type": "null"
        }
      ]
    },
    "notes": {
      "type": [
        "string",
        "null"
      ],
      "description": "Why this span was hard, or why it is not a criterion."
    }
  },
  "required": [
    "is_criterion",
    "kind",
    "source_quote",
    "predicate",
    "notes"
  ],
  "additionalProperties": false
}

[user]
Section: inclusion

Criterion:
Estimated glomerular filtration rate (eGFR) ≥25 and ≤60 milliliter/minute (mL/min)/1.73 square meter (m^2).
```

Response:

```
{
  "is_criterion": true,
  "kind": "inclusion",
  "source_quote": "Estimated glomerular filtration rate (eGFR) ≥25 and ≤60 milliliter/minute (mL/min)/1.73 square meter (m^2).",
  "predicate": {
    "type": "observation",
    "concept": {
      "text": "Estimated glomerular filtration rate (eGFR)",
      "codes": []
    },
    "op": "between",
    "value": 25,
    "value_high": 60,
    "unit": "mL/min/1.73m^2",
    "window": null
  },
  "notes": null
}
```

Validated against the schema.

### Result

```json
{
  "is_criterion": true,
  "kind": "inclusion",
  "source_quote": "Estimated glomerular filtration rate (eGFR) ≥25 and ≤60 milliliter/minute (mL/min)/1.73 square meter (m^2).",
  "predicate": {
    "type": "observation",
    "concept": {
      "text": "Estimated glomerular filtration rate (eGFR)",
      "codes": []
    },
    "op": "between",
    "value": 25.0,
    "value_high": 60.0,
    "unit": "mL/min/1.73m^2",
    "window": null
  },
  "notes": null
}
```

## 3. compiler on venice/claude-sonnet-5

- **Started:** 2026-08-30T10:35:10Z
- **Tier used:** `json_object`
- **Retries:** 1
- **Tokens:** 13474 in / 550 out
- **Estimated cost:** $0.0324
- **Outcome:** validated

### Instructions

```
# Criteria compiler

You formalise one span of a clinical trial's eligibility criteria into a machine-checkable
predicate. A downstream engine will evaluate that predicate against a patient's structured record
and produce a screening verdict. You never see a patient and you never decide eligibility.

You are given one span at a time, together with the section it appeared under and, where the
protocol nested sub-conditions beneath it, its children. Treat the whole unit as one criterion.

## The only judgement that matters

A criterion you formalise incorrectly is worse than a criterion you decline to formalise. The
engine has an explicit `unsupported` predicate; a criterion marked unsupported goes to a research
coordinator, who reads it and decides. That is a normal, safe, expected outcome. A predicate that
looks right and means something slightly different produces a confident wrong verdict that nobody
catches.

So: when the span does not map cleanly onto the vocabulary below, return `unsupported` with a
reason. Do not approximate. Do not drop a qualifier to make something fit. Do not invent a
threshold the protocol did not state.

Use `unsupported` when the span:

- depends on clinical judgement — "in the opinion of the investigator", "otherwise unsuitable",
  "clinically significant", "adequate organ function" without stated numbers;
- depends on something no chart records — willingness to comply, ability to attend visits,
  informed consent, contraception intentions, geographic availability;
- names a threshold relative to something the engine cannot resolve, such as "above the upper
  limit of normal" (the reference range is laboratory-specific and is not in the record);
- describes a process rather than a state — "must complete a washout", "will be randomised";
- is a class of drug or a category of disease broad enough that no single code captures it, and
  the protocol does not enumerate members;
- nests more deeply than the schema allows.

### Which kind of unsupported

Every `unsupported` criterion also carries a `settlement`, and the choice matters more than it
looks. It decides whether one criterion holds up the whole screening.

**`at_visit`** — the criterion is settled when the patient comes in, and would be settled the same
way for every patient in the world. No chart that has ever been written could answer it, so its
being unanswered here says nothing about *this* patient. A coordinator confirms it at the screening
visit, and the packet lists it for them.

> Signed written informed consent.
> Willing and able to comply with the study schedule.
> Planned coronary procedure or surgery after randomization.
> Planning to start an SGLT2 inhibitor during the study.
> In the investigator's opinion, unsuitable for the study.
> Women of childbearing potential must agree to use contraception during the trial.

**`from_data`** — the criterion asks about the patient's recorded history or state, and we simply
could not formalise the question. That is a gap in what we know about this patient, and it does hold
up the screening.

> Adequate organ function. *(about the record; no threshold stated)*
> Any clinically significant abnormality on screening laboratory tests. *(about the record)*
> Lower extremity complications such as skin ulcer, infection, osteomyelitis and gangrene.
> *(about the record; an open list this schema cannot enumerate)*
> Alanine aminotransferase above the upper limit of normal. *(about the record; the range is
> laboratory-specific and not in it)*

The test to apply, in one sentence: **would a complete and perfect medical record answer this?** If
yes, and we merely failed to express it, that is `from_data`. If even a perfect record could not,
because the answer does not exist until the patient is in the room, that is `at_visit`.

When you are unsure, choose `from_data`. It is the cautious answer: it sends the criterion to a
human either way, and it does not let a verdict through on a criterion that should have stopped it.

## Vocabulary

**`observation`** — a numeric comparison against a measurement: laboratory values, vital signs,
scores. Give the analyte as the protocol names it, the operator, the number, and the unit exactly
as written. `between` is for a two-sided range and takes both bounds. Never convert units; the
engine converts, and it knows which conversions are safe.

**`condition`, `medication`, `procedure`** — whether something is on the chart. `presence`
is `present` when the protocol requires it and `absent` when the protocol requires its absence.

Note carefully: an exclusion criterion that reads "history of myocardial infarction" is a
**`present`** predicate under an **exclusion** criterion. Do not negate it yourself — the engine
knows that a met exclusion rules the patient out. Only use `absent` when the protocol itself
states an absence as a requirement, such as an inclusion criterion reading "no history of
malignancy".

**`demographic`** — age and sex only.

**`all_of` / `any_of` / `not`** — for spans that carry several conditions. "eGFR ≥25 and ≤60" is a
single `observation` with `between`, not a composite. "On an ACE inhibitor or an ARB" is `any_of`.
Sub-bullets beneath a parent bullet are almost always conjunctive: `all_of`.

## Temporal windows

Attach a window whenever the protocol bounds the evidence in time: "within 6 months prior to
screening", "in the last 30 days", "no myocardial infarction within 12 weeks". Use the number and
unit the protocol gives.

Protocols anchor windows to different events — screening, enrolment, randomisation, consent — and
those are genuinely different dates. The engine anchors everything to the screening date. If the
span anchors to something else and the difference could plausibly matter, say so in `notes`; if
the anchor is doing real work in the criterion, return `unsupported`.

## Quoting

`source_quote` must be the span reproduced character for character, including its punctuation and
its unicode operators. It is checked against the protocol text automatically, and a criterion whose
quote does not match is discarded. Do not tidy, expand abbreviations, or normalise `≥` to `>=`.

## Spans that are not criteria

Registry text contains section headings, cross-references and standard boilerplate. If the span is
one of those, set `is_criterion` to false and say why in `notes`. This is a correct answer, not a
failure.

## Concepts

Give the concept's `text` as the protocol names it. Leave `codes` empty — terminology resolution is
a separate step with its own controls. A code you guess here will be trusted downstream.

```

### Request

```
Section: inclusion

Criterion:
Age 18 years or older with at least one major cardiovascular risk factor or age 55 years or older with at least two minor cardiovascular risk factors.
```

### Attempt 1, tier `json_schema`

The provider rejected the request:

```
TapeMiss: no recorded answer for this request.
  model:  claude-sonnet-5
  system: "# Criteria compiler\n\nYou formalise one span of a clinical trial's eligibility cr"
  user:   'Section: inclusion\n\nCriterion:\nAge 18 years or older with at least one major cardiovascular risk factor or age 55 years or older with at least two minor cardiovascular risk factors.'
The code has changed since the tape was recorded. Re-record with a key, or check out the commit the tape belongs to.
```

### Attempt 2, tier `json_object`

Restarted with:

```
[system]
# Criteria compiler

You formalise one span of a clinical trial's eligibility criteria into a machine-checkable
predicate. A downstream engine will evaluate that predicate against a patient's structured record
and produce a screening verdict. You never see a patient and you never decide eligibility.

You are given one span at a time, together with the section it appeared under and, where the
protocol nested sub-conditions beneath it, its children. Treat the whole unit as one criterion.

## The only judgement that matters

A criterion you formalise incorrectly is worse than a criterion you decline to formalise. The
engine has an explicit `unsupported` predicate; a criterion marked unsupported goes to a research
coordinator, who reads it and decides. That is a normal, safe, expected outcome. A predicate that
looks right and means something slightly different produces a confident wrong verdict that nobody
catches.

So: when the span does not map cleanly onto the vocabulary below, return `unsupported` with a
reason. Do not approximate. Do not drop a qualifier to make something fit. Do not invent a
threshold the protocol did not state.

Use `unsupported` when the span:

- depends on clinical judgement — "in the opinion of the investigator", "otherwise unsuitable",
  "clinically significant", "adequate organ function" without stated numbers;
- depends on something no chart records — willingness to comply, ability to attend visits,
  informed consent, contraception intentions, geographic availability;
- names a threshold relative to something the engine cannot resolve, such as "above the upper
  limit of normal" (the reference range is laboratory-specific and is not in the record);
- describes a process rather than a state — "must complete a washout", "will be randomised";
- is a class of drug or a category of disease broad enough that no single code captures it, and
  the protocol does not enumerate members;
- nests more deeply than the schema allows.

### Which kind of unsupported

Every `unsupported` criterion also carries a `settlement`, and the choice matters more than it
looks. It decides whether one criterion holds up the whole screening.

**`at_visit`** — the criterion is settled when the patient comes in, and would be settled the same
way for every patient in the world. No chart that has ever been written could answer it, so its
being unanswered here says nothing about *this* patient. A coordinator confirms it at the screening
visit, and the packet lists it for them.

> Signed written informed consent.
> Willing and able to comply with the study schedule.
> Planned coronary procedure or surgery after randomization.
> Planning to start an SGLT2 inhibitor during the study.
> In the investigator's opinion, unsuitable for the study.
> Women of childbearing potential must agree to use contraception during the trial.

**`from_data`** — the criterion asks about the patient's recorded history or state, and we simply
could not formalise the question. That is a gap in what we know about this patient, and it does hold
up the screening.

> Adequate organ function. *(about the record; no threshold stated)*
> Any clinically significant abnormality on screening laboratory tests. *(about the record)*
> Lower extremity complications such as skin ulcer, infection, osteomyelitis and gangrene.
> *(about the record; an open list this schema cannot enumerate)*
> Alanine aminotransferase above the upper limit of normal. *(about the record; the range is
> laboratory-specific and not in it)*

The test to apply, in one sentence: **would a complete and perfect medical record answer this?** If
yes, and we merely failed to express it, that is `from_data`. If even a perfect record could not,
because the answer does not exist until the patient is in the room, that is `at_visit`.

When you are unsure, choose `from_data`. It is the cautious answer: it sends the criterion to a
human either way, and it does not let a verdict through on a criterion that should have stopped it.

## Vocabulary

**`observation`** — a numeric comparison against a measurement: laboratory values, vital signs,
scores. Give the analyte as the protocol names it, the operator, the number, and the unit exactly
as written. `between` is for a two-sided range and takes both bounds. Never convert units; the
engine converts, and it knows which conversions are safe.

**`condition`, `medication`, `procedure`** — whether something is on the chart. `presence`
is `present` when the protocol requires it and `absent` when the protocol requires its absence.

Note carefully: an exclusion criterion that reads "history of myocardial infarction" is a
**`present`** predicate under an **exclusion** criterion. Do not negate it yourself — the engine
knows that a met exclusion rules the patient out. Only use `absent` when the protocol itself
states an absence as a requirement, such as an inclusion criterion reading "no history of
malignancy".

**`demographic`** — age and sex only.

**`all_of` / `any_of` / `not`** — for spans that carry several conditions. "eGFR ≥25 and ≤60" is a
single `observation` with `between`, not a composite. "On an ACE inhibitor or an ARB" is `any_of`.
Sub-bullets beneath a parent bullet are almost always conjunctive: `all_of`.

## Temporal windows

Attach a window whenever the protocol bounds the evidence in time: "within 6 months prior to
screening", "in the last 30 days", "no myocardial infarction within 12 weeks". Use the number and
unit the protocol gives.

Protocols anchor windows to different events — screening, enrolment, randomisation, consent — and
those are genuinely different dates. The engine anchors everything to the screening date. If the
span anchors to something else and the difference could plausibly matter, say so in `notes`; if
the anchor is doing real work in the criterion, return `unsupported`.

## Quoting

`source_quote` must be the span reproduced character for character, including its punctuation and
its unicode operators. It is checked against the protocol text automatically, and a criterion whose
quote does not match is discarded. Do not tidy, expand abbreviations, or normalise `≥` to `>=`.

## Spans that are not criteria

Registry text contains section headings, cross-references and standard boilerplate. If the span is
one of those, set `is_criterion` to false and say why in `notes`. This is a correct answer, not a
failure.

## Concepts

Give the concept's `text` as the protocol names it. Leave `codes` empty — terminology resolution is
a separate step with its own controls. A code you guess here will be trusted downstream.


Reply with a single JSON object and nothing else. It must conform to this JSON schema:

{
  "type": "object",
  "description": "The result of formalising one span of eligibility text. Set is_criterion to false when the span is a heading, a note to readers, or registry boilerplate rather than a condition a patient can meet.",
  "properties": {
    "is_criterion": {
      "type": "boolean"
    },
    "kind": {
      "description": "Only needed when the span sits under no inclusion or exclusion header.",
      "anyOf": [
        {
          "type": "string",
          "enum": [
            "inclusion",
            "exclusion"
          ]
        },
        {
          "type": "null"
        }
      ]
    },
    "source_quote": {
      "type": [
        "string",
        "null"
      ],
      "description": "The span copied verbatim, character for character."
    },
    "predicate": {
      "anyOf": [
        {
          "anyOf": [
            {
              "type": "object",
              "description": "A numeric comparison against a measurement: labs, vitals, scores.",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "observation"
                  ]
                },
                "concept": {
                  "type": "object",
                  "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                  "properties": {
                    "text": {
                      "type": "string"
                    },
                    "codes": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                        "properties": {
                          "system": {
                            "type": "string",
                            "enum": [
                              "LOINC",
                              "SNOMED",
                              "RxNorm",
                              "ICD10",
                              "UCUM"
                            ]
                          },
                          "code": {
                            "type": "string"
                          },
                          "display": {
                            "type": [
                              "string",
                              "null"
                            ]
                          }
                        },
                        "required": [
                          "system",
                          "code",
                          "display"
                        ],
                        "additionalProperties": false
                      }
                    }
                  },
                  "required": [
                    "text",
                    "codes"
                  ],
                  "additionalProperties": false
                },
                "op": {
                  "type": "string",
                  "enum": [
                    "<",
                    "<=",
                    ">",
                    ">=",
                    "==",
                    "!=",
                    "between"
                  ]
                },
                "value": {
                  "type": "number"
                },
                "value_high": {
                  "type": [
                    "number",
                    "null"
                  ]
                },
                "unit": {
                  "type": "string"
                },
                "window": {
                  "anyOf": [
                    {
                      "type": "object",
                      "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                      "properties": {
                        "relation": {
                          "type": "string",
                          "enum": [
                            "within",
                            "before",
                            "after",
                            "ever",
                            "current"
                          ]
                        },
                        "amount": {
                          "type": [
                            "integer",
                            "null"
                          ]
                        },
                        "unit": {
                          "anyOf": [
                            {
                              "type": "string",
                              "enum": [
                                "days",
                                "weeks",
                                "months",
                                "years"
                              ]
                            },
                            {
                              "type": "null"
                            }
                          ]
                        },
                        "anchor": {
                          "type": "string",
                          "enum": [
                            "screening",
                            "enrolment",
                            "randomisation",
                            "consent",
                            "first_dose"
                          ]
                        }
                      },
                      "required": [
                        "relation",
                        "amount",
                        "unit",
                        "anchor"
                      ],
                      "additionalProperties": false
                    },
                    {
                      "type": "null"
                    }
                  ]
                }
              },
              "required": [
                "type",
                "concept",
                "op",
                "value",
                "value_high",
                "unit",
                "window"
              ],
              "additionalProperties": false
            },
            {
              "type": "object",
              "description": "Whether a coded thing is on the chart at all: a condition, a drug, a procedure.",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "condition",
                    "medication",
                    "procedure"
                  ]
                },
                "concept": {
                  "type": "object",
                  "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                  "properties": {
                    "text": {
                      "type": "string"
                    },
                    "codes": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                        "properties": {
                          "system": {
                            "type": "string",
                            "enum": [
                              "LOINC",
                              "SNOMED",
                              "RxNorm",
                              "ICD10",
                              "UCUM"
                            ]
                          },
                          "code": {
                            "type": "string"
                          },
                          "display": {
                            "type": [
                              "string",
                              "null"
                            ]
                          }
                        },
                        "required": [
                          "system",
                          "code",
                          "display"
                        ],
                        "additionalProperties": false
                      }
                    }
                  },
                  "required": [
                    "text",
                    "codes"
                  ],
                  "additionalProperties": false
                },
                "presence": {
                  "type": "string",
                  "enum": [
                    "present",
                    "absent"
                  ]
                },
                "window": {
                  "anyOf": [
                    {
                      "type": "object",
                      "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                      "properties": {
                        "relation": {
                          "type": "string",
                          "enum": [
                            "within",
                            "before",
                            "after",
                            "ever",
                            "current"
                          ]
                        },
                        "amount": {
                          "type": [
                            "integer",
                            "null"
                          ]
                        },
                        "unit": {
                          "anyOf": [
                            {
                              "type": "string",
                              "enum": [
                                "days",
                                "weeks",
                                "months",
                                "years"
                              ]
                            },
                            {
                              "type": "null"
                            }
                          ]
                        },
                        "anchor": {
                          "type": "string",
                          "enum": [
                            "screening",
                            "enrolment",
                            "randomisation",
                            "consent",
                            "first_dose"
                          ]
                        }
                      },
                      "required": [
                        "relation",
                        "amount",
                        "unit",
                        "anchor"
                      ],
                      "additionalProperties": false
                    },
                    {
                      "type": "null"
                    }
                  ]
                }
              },
              "required": [
                "type",
                "concept",
                "presence",
                "window"
              ],
              "additionalProperties": false
            },
            {
              "type": "object",
              "description": "Age and sex, which come from the patient resource rather than from clinical events.",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "demographic"
                  ]
                },
                "field": {
                  "type": "string",
                  "enum": [
                    "age",
                    "sex"
                  ]
                },
                "op": {
                  "type": "string",
                  "enum": [
                    "<",
                    "<=",
                    ">",
                    ">=",
                    "==",
                    "!="
                  ]
                },
                "value": {
                  "type": [
                    "number",
                    "string"
                  ]
                },
                "unit": {
                  "type": [
                    "string",
                    "null"
                  ]
                }
              },
              "required": [
                "type",
                "field",
                "op",
                "value",
                "unit"
              ],
              "additionalProperties": false
            },
            {
              "type": "object",
              "description": "A criterion that cannot be honestly formalised. It stays unresolved forever, by design.\n\n`settlement` says *why* no chart can answer it, and the difference is load-bearing.\n\nA criterion settled `from_data` was a question about the patient's record that we failed to\nformalise \u2014 a threshold with no number, an open category. It is a gap, and it blocks a verdict.\n\nA criterion settled `at_visit` is not a gap at all. Signed informed consent, a procedure planned\nafter randomisation, the investigator's own judgement of the patient in person: these have the\nsame answer for every chart ever written, because they are settled when the patient comes in.\nTreating them as unresolved data made ELIGIBLE unreachable for every real protocol we hold \u2014 one\nconsent criterion and the screening abstains, which is not caution but paralysis.\n\nThe default is `from_data`, so a compiler that says nothing cannot thereby unblock a verdict.",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "unsupported"
                  ]
                },
                "reason": {
                  "type": "string"
                },
                "settlement": {
                  "type": "string",
                  "enum": [
                    "from_data",
                    "at_visit"
                  ]
                }
              },
              "required": [
                "type",
                "reason",
                "settlement"
              ],
              "additionalProperties": false
            },
            {
              "type": "object",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "all_of",
                    "any_of",
                    "not"
                  ]
                },
                "operands": {
                  "type": "array",
                  "items": {
                    "anyOf": [
                      {
                        "type": "object",
                        "description": "A numeric comparison against a measurement: labs, vitals, scores.",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "observation"
                            ]
                          },
                          "concept": {
                            "type": "object",
                            "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                            "properties": {
                              "text": {
                                "type": "string"
                              },
                              "codes": {
                                "type": "array",
                                "items": {
                                  "type": "object",
                                  "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                                  "properties": {
                                    "system": {
                                      "type": "string",
                                      "enum": [
                                        "LOINC",
                                        "SNOMED",
                                        "RxNorm",
                                        "ICD10",
                                        "UCUM"
                                      ]
                                    },
                                    "code": {
                                      "type": "string"
                                    },
                                    "display": {
                                      "type": [
                                        "string",
                                        "null"
                                      ]
                                    }
                                  },
                                  "required": [
                                    "system",
                                    "code",
                                    "display"
                                  ],
                                  "additionalProperties": false
                                }
                              }
                            },
                            "required": [
                              "text",
                              "codes"
                            ],
                            "additionalProperties": false
                          },
                          "op": {
                            "type": "string",
                            "enum": [
                              "<",
                              "<=",
                              ">",
                              ">=",
                              "==",
                              "!=",
                              "between"
                            ]
                          },
                          "value": {
                            "type": "number"
                          },
                          "value_high": {
                            "type": [
                              "number",
                              "null"
                            ]
                          },
                          "unit": {
                            "type": "string"
                          },
                          "window": {
                            "anyOf": [
                              {
                                "type": "object",
                                "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                                "properties": {
                                  "relation": {
                                    "type": "string",
                                    "enum": [
                                      "within",
                                      "before",
                                      "after",
                                      "ever",
                                      "current"
                                    ]
                                  },
                                  "amount": {
                                    "type": [
                                      "integer",
                                      "null"
                                    ]
                                  },
                                  "unit": {
                                    "anyOf": [
                                      {
                                        "type": "string",
                                        "enum": [
                                          "days",
                                          "weeks",
                                          "months",
                                          "years"
                                        ]
                                      },
                                      {
                                        "type": "null"
                                      }
                                    ]
                                  },
                                  "anchor": {
                                    "type": "string",
                                    "enum": [
                                      "screening",
                                      "enrolment",
                                      "randomisation",
                                      "consent",
                                      "first_dose"
                                    ]
                                  }
                                },
                                "required": [
                                  "relation",
                                  "amount",
                                  "unit",
                                  "anchor"
                                ],
                                "additionalProperties": false
                              },
                              {
                                "type": "null"
                              }
                            ]
                          }
                        },
                        "required": [
                          "type",
                          "concept",
                          "op",
                          "value",
                          "value_high",
                          "unit",
                          "window"
                        ],
                        "additionalProperties": false
                      },
                      {
                        "type": "object",
                        "description": "Whether a coded thing is on the chart at all: a condition, a drug, a procedure.",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "condition",
                              "medication",
                              "procedure"
                            ]
                          },
                          "concept": {
                            "type": "object",
                            "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                            "properties": {
                              "text": {
                                "type": "string"
                              },
                              "codes": {
                                "type": "array",
                                "items": {
                                  "type": "object",
                                  "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                                  "properties": {
                                    "system": {
                                      "type": "string",
                                      "enum": [
                                        "LOINC",
                                        "SNOMED",
                                        "RxNorm",
                                        "ICD10",
                                        "UCUM"
                                      ]
                                    },
                                    "code": {
                                      "type": "string"
                                    },
                                    "display": {
                                      "type": [
                                        "string",
                                        "null"
                                      ]
                                    }
                                  },
                                  "required": [
                                    "system",
                                    "code",
                                    "display"
                                  ],
                                  "additionalProperties": false
                                }
                              }
                            },
                            "required": [
                              "text",
                              "codes"
                            ],
                            "additionalProperties": false
                          },
                          "presence": {
                            "type": "string",
                            "enum": [
                              "present",
                              "absent"
                            ]
                          },
                          "window": {
                            "anyOf": [
                              {
                                "type": "object",
                                "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                                "properties": {
                                  "relation": {
                                    "type": "string",
                                    "enum": [
                                      "within",
                                      "before",
                                      "after",
                                      "ever",
                                      "current"
                                    ]
                                  },
                                  "amount": {
                                    "type": [
                                      "integer",
                                      "null"
                                    ]
                                  },
                                  "unit": {
                                    "anyOf": [
                                      {
                                        "type": "string",
                                        "enum": [
                                          "days",
                                          "weeks",
                                          "months",
                                          "years"
                                        ]
                                      },
                                      {
                                        "type": "null"
                                      }
                                    ]
                                  },
                                  "anchor": {
                                    "type": "string",
                                    "enum": [
                                      "screening",
                                      "enrolment",
                                      "randomisation",
                                      "consent",
                                      "first_dose"
                                    ]
                                  }
                                },
                                "required": [
                                  "relation",
                                  "amount",
                                  "unit",
                                  "anchor"
                                ],
                                "additionalProperties": false
                              },
                              {
                                "type": "null"
                              }
                            ]
                          }
                        },
                        "required": [
                          "type",
                          "concept",
                          "presence",
                          "window"
                        ],
                        "additionalProperties": false
                      },
                      {
                        "type": "object",
                        "description": "Age and sex, which come from the patient resource rather than from clinical events.",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "demographic"
                            ]
                          },
                          "field": {
                            "type": "string",
                            "enum": [
                              "age",
                              "sex"
                            ]
                          },
                          "op": {
                            "type": "string",
                            "enum": [
                              "<",
                              "<=",
                              ">",
                              ">=",
                              "==",
                              "!="
                            ]
                          },
                          "value": {
                            "type": [
                              "number",
                              "string"
                            ]
                          },
                          "unit": {
                            "type": [
                              "string",
                              "null"
                            ]
                          }
                        },
                        "required": [
                          "type",
                          "field",
                          "op",
                          "value",
                          "unit"
                        ],
                        "additionalProperties": false
                      },
                      {
                        "type": "object",
                        "description": "A criterion that cannot be honestly formalised. It stays unresolved forever, by design.\n\n`settlement` says *why* no chart can answer it, and the difference is load-bearing.\n\nA criterion settled `from_data` was a question about the patient's record that we failed to\nformalise \u2014 a threshold with no number, an open category. It is a gap, and it blocks a verdict.\n\nA criterion settled `at_visit` is not a gap at all. Signed informed consent, a procedure planned\nafter randomisation, the investigator's own judgement of the patient in person: these have the\nsame answer for every chart ever written, because they are settled when the patient comes in.\nTreating them as unresolved data made ELIGIBLE unreachable for every real protocol we hold \u2014 one\nconsent criterion and the screening abstains, which is not caution but paralysis.\n\nThe default is `from_data`, so a compiler that says nothing cannot thereby unblock a verdict.",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "unsupported"
                            ]
                          },
                          "reason": {
                            "type": "string"
                          },
                          "settlement": {
                            "type": "string",
                            "enum": [
                              "from_data",
                              "at_visit"
                            ]
                          }
                        },
                        "required": [
                          "type",
                          "reason",
                          "settlement"
                        ],
                        "additionalProperties": false
                      },
                      {
                        "type": "object",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "all_of",
                              "any_of",
                              "not"
                            ]
                          },
                          "operands": {
                            "type": "array",
                            "items": {
                              "anyOf": [
                                {
                                  "type": "object",
                                  "description": "A numeric comparison against a measurement: labs, vitals, scores.",
                                  "properties": {
                                    "type": {
                                      "type": "string",
                                      "enum": [
                                        "observation"
                                      ]
                                    },
                                    "concept": {
                                      "type": "object",
                                      "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                                      "properties": {
                                        "text": {
                                          "type": "string"
                                        },
                                        "codes": {
                                          "type": "array",
                                          "items": {
                                            "type": "object",
                                            "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                                            "properties": {
                                              "system": {
                                                "type": "string",
                                                "enum": [
                                                  "LOINC",
                                                  "SNOMED",
                                                  "RxNorm",
                                                  "ICD10",
                                                  "UCUM"
                                                ]
                                              },
                                              "code": {
                                                "type": "string"
                                              },
                                              "display": {
                                                "type": [
                                                  "string",
                                                  "null"
                                                ]
                                              }
                                            },
                                            "required": [
                                              "system",
                                              "code",
                                              "display"
                                            ],
                                            "additionalProperties": false
                                          }
                                        }
                                      },
                                      "required": [
                                        "text",
                                        "codes"
                                      ],
                                      "additionalProperties": false
                                    },
                                    "op": {
                                      "type": "string",
                                      "enum": [
                                        "<",
                                        "<=",
                                        ">",
                                        ">=",
                                        "==",
                                        "!=",
                                        "between"
                                      ]
                                    },
                                    "value": {
                                      "type": "number"
                                    },
                                    "value_high": {
                                      "type": [
                                        "number",
                                        "null"
                                      ]
                                    },
                                    "unit": {
                                      "type": "string"
                                    },
                                    "window": {
                                      "anyOf": [
                                        {
                                          "type": "object",
                                          "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                                          "properties": {
                                            "relation": {
                                              "type": "string",
                                              "enum": [
                                                "within",
                                                "before",
                                                "after",
                                                "ever",
                                                "current"
                                              ]
                                            },
                                            "amount": {
                                              "type": [
                                                "integer",
                                                "null"
                                              ]
                                            },
                                            "unit": {
                                              "anyOf": [
                                                {
                                                  "type": "string",
                                                  "enum": [
                                                    "days",
                                                    "weeks",
                                                    "months",
                                                    "years"
                                                  ]
                                                },
                                                {
                                                  "type": "null"
                                                }
                                              ]
                                            },
                                            "anchor": {
                                              "type": "string",
                                              "enum": [
                                                "screening",
                                                "enrolment",
                                                "randomisation",
                                                "consent",
                                                "first_dose"
                                              ]
                                            }
                                          },
                                          "required": [
                                            "relation",
                                            "amount",
                                            "unit",
                                            "anchor"
                                          ],
                                          "additionalProperties": false
                                        },
                                        {
                                          "type": "null"
                                        }
                                      ]
                                    }
                                  },
                                  "required": [
                                    "type",
                                    "concept",
                                    "op",
                                    "value",
                                    "value_high",
                                    "unit",
                                    "window"
                                  ],
                                  "additionalProperties": false
                                },
                                {
                                  "type": "object",
                                  "description": "Whether a coded thing is on the chart at all: a condition, a drug, a procedure.",
                                  "properties": {
                                    "type": {
                                      "type": "string",
                                      "enum": [
                                        "condition",
                                        "medication",
                                        "procedure"
                                      ]
                                    },
                                    "concept": {
                                      "type": "object",
                                      "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                                      "properties": {
                                        "text": {
                                          "type": "string"
                                        },
                                        "codes": {
                                          "type": "array",
                                          "items": {
                                            "type": "object",
                                            "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                                            "properties": {
                                              "system": {
                                                "type": "string",
                                                "enum": [
                                                  "LOINC",
                                                  "SNOMED",
                                                  "RxNorm",
                                                  "ICD10",
                                                  "UCUM"
                                                ]
                                              },
                                              "code": {
                                                "type": "string"
                                              },
                                              "display": {
                                                "type": [
                                                  "string",
                                                  "null"
                                                ]
                                              }
                                            },
                                            "required": [
                                              "system",
                                              "code",
                                              "display"
                                            ],
                                            "additionalProperties": false
                                          }
                                        }
                                      },
                                      "required": [
                                        "text",
                                        "codes"
                                      ],
                                      "additionalProperties": false
                                    },
                                    "presence": {
                                      "type": "string",
                                      "enum": [
                                        "present",
                                        "absent"
                                      ]
                                    },
                                    "window": {
                                      "anyOf": [
                                        {
                                          "type": "object",
                                          "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                                          "properties": {
                                            "relation": {
                                              "type": "string",
                                              "enum": [
                                                "within",
                                                "before",
                                                "after",
                                                "ever",
                                                "current"
                                              ]
                                            },
                                            "amount": {
                                              "type": [
                                                "integer",
                                                "null"
                                              ]
                                            },
                                            "unit": {
                                              "anyOf": [
                                                {
                                                  "type": "string",
                                                  "enum": [
                                                    "days",
                                                    "weeks",
                                                    "months",
                                                    "years"
                                                  ]
                                                },
                                                {
                                                  "type": "null"
                                                }
                                              ]
                                            },
                                            "anchor": {
                                              "type": "string",
                                              "enum": [
                                                "screening",
                                                "enrolment",
                                                "randomisation",
                                                "consent",
                                                "first_dose"
                                              ]
                                            }
                                          },
                                          "required": [
                                            "relation",
                                            "amount",
                                            "unit",
                                            "anchor"
                                          ],
                                          "additionalProperties": false
                                        },
                                        {
                                          "type": "null"
                                        }
                                      ]
                                    }
                                  },
                                  "required": [
                                    "type",
                                    "concept",
                                    "presence",
                                    "window"
                                  ],
                                  "additionalProperties": false
                                },
                                {
                                  "type": "object",
                                  "description": "Age and sex, which come from the patient resource rather than from clinical events.",
                                  "properties": {
                                    "type": {
                                      "type": "string",
                                      "enum": [
                                        "demographic"
                                      ]
                                    },
                                    "field": {
                                      "type": "string",
                                      "enum": [
                                        "age",
                                        "sex"
                                      ]
                                    },
                                    "op": {
                                      "type": "string",
                                      "enum": [
                                        "<",
                                        "<=",
                                        ">",
                                        ">=",
                                        "==",
                                        "!="
                                      ]
                                    },
                                    "value": {
                                      "type": [
                                        "number",
                                        "string"
                                      ]
                                    },
                                    "unit": {
                                      "type": [
                                        "string",
                                        "null"
                                      ]
                                    }
                                  },
                                  "required": [
                                    "type",
                                    "field",
                                    "op",
                                    "value",
                                    "unit"
                                  ],
                                  "additionalProperties": false
                                },
                                {
                                  "type": "object",
                                  "description": "A criterion that cannot be honestly formalised. It stays unresolved forever, by design.\n\n`settlement` says *why* no chart can answer it, and the difference is load-bearing.\n\nA criterion settled `from_data` was a question about the patient's record that we failed to\nformalise \u2014 a threshold with no number, an open category. It is a gap, and it blocks a verdict.\n\nA criterion settled `at_visit` is not a gap at all. Signed informed consent, a procedure planned\nafter randomisation, the investigator's own judgement of the patient in person: these have the\nsame answer for every chart ever written, because they are settled when the patient comes in.\nTreating them as unresolved data made ELIGIBLE unreachable for every real protocol we hold \u2014 one\nconsent criterion and the screening abstains, which is not caution but paralysis.\n\nThe default is `from_data`, so a compiler that says nothing cannot thereby unblock a verdict.",
                                  "properties": {
                                    "type": {
                                      "type": "string",
                                      "enum": [
                                        "unsupported"
                                      ]
                                    },
                                    "reason": {
                                      "type": "string"
                                    },
                                    "settlement": {
                                      "type": "string",
                                      "enum": [
                                        "from_data",
                                        "at_visit"
                                      ]
                                    }
                                  },
                                  "required": [
                                    "type",
                                    "reason",
                                    "settlement"
                                  ],
                                  "additionalProperties": false
                                }
                              ]
                            }
                          }
                        },
                        "required": [
                          "type",
                          "operands"
                        ],
                        "additionalProperties": false
                      }
                    ]
                  }
                }
              },
              "required": [
                "type",
                "operands"
              ],
              "additionalProperties": false
            }
          ]
        },
        {
          "type": "null"
        }
      ]
    },
    "notes": {
      "type": [
        "string",
        "null"
      ],
      "description": "Why this span was hard, or why it is not a criterion."
    }
  },
  "required": [
    "is_criterion",
    "kind",
    "source_quote",
    "predicate",
    "notes"
  ],
  "additionalProperties": false
}

[user]
Section: inclusion

Criterion:
Age 18 years or older with at least one major cardiovascular risk factor or age 55 years or older with at least two minor cardiovascular risk factors.
```

Response:

```
{
  "is_criterion": true,
  "kind": "inclusion",
  "source_quote": "Age 18 years or older with at least one major cardiovascular risk factor or age 55 years or older with at least two minor cardiovascular risk factors.",
  "predicate": {
    "type": "unsupported",
    "reason": "The criterion turns on membership in 'major' and 'minor' cardiovascular risk factor categories, which this span does not enumerate. Without the protocol's defined list of qualifying risk factors, no single code or small set of codes can capture the category, so counting them cannot be formalised.",
    "settlement": "from_data"
  },
  "notes": "The age thresholds (18, 55) are demographic and formalisable on their own, but they are inseparable here from counting undefined 'major'/'minor' cardiovascular risk factors, which is an open category not enumerated in this span."
}
```

Validated against the schema.

### Result

```json
{
  "is_criterion": true,
  "kind": "inclusion",
  "source_quote": "Age 18 years or older with at least one major cardiovascular risk factor or age 55 years or older with at least two minor cardiovascular risk factors.",
  "predicate": {
    "type": "unsupported",
    "reason": "The criterion turns on membership in 'major' and 'minor' cardiovascular risk factor categories, which this span does not enumerate. Without the protocol's defined list of qualifying risk factors, no single code or small set of codes can capture the category, so counting them cannot be formalised.",
    "settlement": "from_data"
  },
  "notes": "The age thresholds (18, 55) are demographic and formalisable on their own, but they are inseparable here from counting undefined 'major'/'minor' cardiovascular risk factors, which is an open category not enumerated in this span."
}
```

## 4. compiler on venice/claude-sonnet-5

- **Started:** 2026-08-30T10:35:10Z
- **Tier used:** `json_object`
- **Retries:** 1
- **Tokens:** 13435 in / 122 out
- **Estimated cost:** $0.0281
- **Outcome:** validated

### Instructions

```
# Criteria compiler

You formalise one span of a clinical trial's eligibility criteria into a machine-checkable
predicate. A downstream engine will evaluate that predicate against a patient's structured record
and produce a screening verdict. You never see a patient and you never decide eligibility.

You are given one span at a time, together with the section it appeared under and, where the
protocol nested sub-conditions beneath it, its children. Treat the whole unit as one criterion.

## The only judgement that matters

A criterion you formalise incorrectly is worse than a criterion you decline to formalise. The
engine has an explicit `unsupported` predicate; a criterion marked unsupported goes to a research
coordinator, who reads it and decides. That is a normal, safe, expected outcome. A predicate that
looks right and means something slightly different produces a confident wrong verdict that nobody
catches.

So: when the span does not map cleanly onto the vocabulary below, return `unsupported` with a
reason. Do not approximate. Do not drop a qualifier to make something fit. Do not invent a
threshold the protocol did not state.

Use `unsupported` when the span:

- depends on clinical judgement — "in the opinion of the investigator", "otherwise unsuitable",
  "clinically significant", "adequate organ function" without stated numbers;
- depends on something no chart records — willingness to comply, ability to attend visits,
  informed consent, contraception intentions, geographic availability;
- names a threshold relative to something the engine cannot resolve, such as "above the upper
  limit of normal" (the reference range is laboratory-specific and is not in the record);
- describes a process rather than a state — "must complete a washout", "will be randomised";
- is a class of drug or a category of disease broad enough that no single code captures it, and
  the protocol does not enumerate members;
- nests more deeply than the schema allows.

### Which kind of unsupported

Every `unsupported` criterion also carries a `settlement`, and the choice matters more than it
looks. It decides whether one criterion holds up the whole screening.

**`at_visit`** — the criterion is settled when the patient comes in, and would be settled the same
way for every patient in the world. No chart that has ever been written could answer it, so its
being unanswered here says nothing about *this* patient. A coordinator confirms it at the screening
visit, and the packet lists it for them.

> Signed written informed consent.
> Willing and able to comply with the study schedule.
> Planned coronary procedure or surgery after randomization.
> Planning to start an SGLT2 inhibitor during the study.
> In the investigator's opinion, unsuitable for the study.
> Women of childbearing potential must agree to use contraception during the trial.

**`from_data`** — the criterion asks about the patient's recorded history or state, and we simply
could not formalise the question. That is a gap in what we know about this patient, and it does hold
up the screening.

> Adequate organ function. *(about the record; no threshold stated)*
> Any clinically significant abnormality on screening laboratory tests. *(about the record)*
> Lower extremity complications such as skin ulcer, infection, osteomyelitis and gangrene.
> *(about the record; an open list this schema cannot enumerate)*
> Alanine aminotransferase above the upper limit of normal. *(about the record; the range is
> laboratory-specific and not in it)*

The test to apply, in one sentence: **would a complete and perfect medical record answer this?** If
yes, and we merely failed to express it, that is `from_data`. If even a perfect record could not,
because the answer does not exist until the patient is in the room, that is `at_visit`.

When you are unsure, choose `from_data`. It is the cautious answer: it sends the criterion to a
human either way, and it does not let a verdict through on a criterion that should have stopped it.

## Vocabulary

**`observation`** — a numeric comparison against a measurement: laboratory values, vital signs,
scores. Give the analyte as the protocol names it, the operator, the number, and the unit exactly
as written. `between` is for a two-sided range and takes both bounds. Never convert units; the
engine converts, and it knows which conversions are safe.

**`condition`, `medication`, `procedure`** — whether something is on the chart. `presence`
is `present` when the protocol requires it and `absent` when the protocol requires its absence.

Note carefully: an exclusion criterion that reads "history of myocardial infarction" is a
**`present`** predicate under an **exclusion** criterion. Do not negate it yourself — the engine
knows that a met exclusion rules the patient out. Only use `absent` when the protocol itself
states an absence as a requirement, such as an inclusion criterion reading "no history of
malignancy".

**`demographic`** — age and sex only.

**`all_of` / `any_of` / `not`** — for spans that carry several conditions. "eGFR ≥25 and ≤60" is a
single `observation` with `between`, not a composite. "On an ACE inhibitor or an ARB" is `any_of`.
Sub-bullets beneath a parent bullet are almost always conjunctive: `all_of`.

## Temporal windows

Attach a window whenever the protocol bounds the evidence in time: "within 6 months prior to
screening", "in the last 30 days", "no myocardial infarction within 12 weeks". Use the number and
unit the protocol gives.

Protocols anchor windows to different events — screening, enrolment, randomisation, consent — and
those are genuinely different dates. The engine anchors everything to the screening date. If the
span anchors to something else and the difference could plausibly matter, say so in `notes`; if
the anchor is doing real work in the criterion, return `unsupported`.

## Quoting

`source_quote` must be the span reproduced character for character, including its punctuation and
its unicode operators. It is checked against the protocol text automatically, and a criterion whose
quote does not match is discarded. Do not tidy, expand abbreviations, or normalise `≥` to `>=`.

## Spans that are not criteria

Registry text contains section headings, cross-references and standard boilerplate. If the span is
one of those, set `is_criterion` to false and say why in `notes`. This is a correct answer, not a
failure.

## Concepts

Give the concept's `text` as the protocol names it. Leave `codes` empty — terminology resolution is
a separate step with its own controls. A code you guess here will be trusted downstream.

```

### Request

```
Section: inclusion

Criterion:
Signed written informed consent.
```

### Attempt 1, tier `json_schema`

The provider rejected the request:

```
TapeMiss: no recorded answer for this request.
  model:  claude-sonnet-5
  system: "# Criteria compiler\n\nYou formalise one span of a clinical trial's eligibility cr"
  user:   'Section: inclusion\n\nCriterion:\nSigned written informed consent.'
The code has changed since the tape was recorded. Re-record with a key, or check out the commit the tape belongs to.
```

### Attempt 2, tier `json_object`

Restarted with:

```
[system]
# Criteria compiler

You formalise one span of a clinical trial's eligibility criteria into a machine-checkable
predicate. A downstream engine will evaluate that predicate against a patient's structured record
and produce a screening verdict. You never see a patient and you never decide eligibility.

You are given one span at a time, together with the section it appeared under and, where the
protocol nested sub-conditions beneath it, its children. Treat the whole unit as one criterion.

## The only judgement that matters

A criterion you formalise incorrectly is worse than a criterion you decline to formalise. The
engine has an explicit `unsupported` predicate; a criterion marked unsupported goes to a research
coordinator, who reads it and decides. That is a normal, safe, expected outcome. A predicate that
looks right and means something slightly different produces a confident wrong verdict that nobody
catches.

So: when the span does not map cleanly onto the vocabulary below, return `unsupported` with a
reason. Do not approximate. Do not drop a qualifier to make something fit. Do not invent a
threshold the protocol did not state.

Use `unsupported` when the span:

- depends on clinical judgement — "in the opinion of the investigator", "otherwise unsuitable",
  "clinically significant", "adequate organ function" without stated numbers;
- depends on something no chart records — willingness to comply, ability to attend visits,
  informed consent, contraception intentions, geographic availability;
- names a threshold relative to something the engine cannot resolve, such as "above the upper
  limit of normal" (the reference range is laboratory-specific and is not in the record);
- describes a process rather than a state — "must complete a washout", "will be randomised";
- is a class of drug or a category of disease broad enough that no single code captures it, and
  the protocol does not enumerate members;
- nests more deeply than the schema allows.

### Which kind of unsupported

Every `unsupported` criterion also carries a `settlement`, and the choice matters more than it
looks. It decides whether one criterion holds up the whole screening.

**`at_visit`** — the criterion is settled when the patient comes in, and would be settled the same
way for every patient in the world. No chart that has ever been written could answer it, so its
being unanswered here says nothing about *this* patient. A coordinator confirms it at the screening
visit, and the packet lists it for them.

> Signed written informed consent.
> Willing and able to comply with the study schedule.
> Planned coronary procedure or surgery after randomization.
> Planning to start an SGLT2 inhibitor during the study.
> In the investigator's opinion, unsuitable for the study.
> Women of childbearing potential must agree to use contraception during the trial.

**`from_data`** — the criterion asks about the patient's recorded history or state, and we simply
could not formalise the question. That is a gap in what we know about this patient, and it does hold
up the screening.

> Adequate organ function. *(about the record; no threshold stated)*
> Any clinically significant abnormality on screening laboratory tests. *(about the record)*
> Lower extremity complications such as skin ulcer, infection, osteomyelitis and gangrene.
> *(about the record; an open list this schema cannot enumerate)*
> Alanine aminotransferase above the upper limit of normal. *(about the record; the range is
> laboratory-specific and not in it)*

The test to apply, in one sentence: **would a complete and perfect medical record answer this?** If
yes, and we merely failed to express it, that is `from_data`. If even a perfect record could not,
because the answer does not exist until the patient is in the room, that is `at_visit`.

When you are unsure, choose `from_data`. It is the cautious answer: it sends the criterion to a
human either way, and it does not let a verdict through on a criterion that should have stopped it.

## Vocabulary

**`observation`** — a numeric comparison against a measurement: laboratory values, vital signs,
scores. Give the analyte as the protocol names it, the operator, the number, and the unit exactly
as written. `between` is for a two-sided range and takes both bounds. Never convert units; the
engine converts, and it knows which conversions are safe.

**`condition`, `medication`, `procedure`** — whether something is on the chart. `presence`
is `present` when the protocol requires it and `absent` when the protocol requires its absence.

Note carefully: an exclusion criterion that reads "history of myocardial infarction" is a
**`present`** predicate under an **exclusion** criterion. Do not negate it yourself — the engine
knows that a met exclusion rules the patient out. Only use `absent` when the protocol itself
states an absence as a requirement, such as an inclusion criterion reading "no history of
malignancy".

**`demographic`** — age and sex only.

**`all_of` / `any_of` / `not`** — for spans that carry several conditions. "eGFR ≥25 and ≤60" is a
single `observation` with `between`, not a composite. "On an ACE inhibitor or an ARB" is `any_of`.
Sub-bullets beneath a parent bullet are almost always conjunctive: `all_of`.

## Temporal windows

Attach a window whenever the protocol bounds the evidence in time: "within 6 months prior to
screening", "in the last 30 days", "no myocardial infarction within 12 weeks". Use the number and
unit the protocol gives.

Protocols anchor windows to different events — screening, enrolment, randomisation, consent — and
those are genuinely different dates. The engine anchors everything to the screening date. If the
span anchors to something else and the difference could plausibly matter, say so in `notes`; if
the anchor is doing real work in the criterion, return `unsupported`.

## Quoting

`source_quote` must be the span reproduced character for character, including its punctuation and
its unicode operators. It is checked against the protocol text automatically, and a criterion whose
quote does not match is discarded. Do not tidy, expand abbreviations, or normalise `≥` to `>=`.

## Spans that are not criteria

Registry text contains section headings, cross-references and standard boilerplate. If the span is
one of those, set `is_criterion` to false and say why in `notes`. This is a correct answer, not a
failure.

## Concepts

Give the concept's `text` as the protocol names it. Leave `codes` empty — terminology resolution is
a separate step with its own controls. A code you guess here will be trusted downstream.


Reply with a single JSON object and nothing else. It must conform to this JSON schema:

{
  "type": "object",
  "description": "The result of formalising one span of eligibility text. Set is_criterion to false when the span is a heading, a note to readers, or registry boilerplate rather than a condition a patient can meet.",
  "properties": {
    "is_criterion": {
      "type": "boolean"
    },
    "kind": {
      "description": "Only needed when the span sits under no inclusion or exclusion header.",
      "anyOf": [
        {
          "type": "string",
          "enum": [
            "inclusion",
            "exclusion"
          ]
        },
        {
          "type": "null"
        }
      ]
    },
    "source_quote": {
      "type": [
        "string",
        "null"
      ],
      "description": "The span copied verbatim, character for character."
    },
    "predicate": {
      "anyOf": [
        {
          "anyOf": [
            {
              "type": "object",
              "description": "A numeric comparison against a measurement: labs, vitals, scores.",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "observation"
                  ]
                },
                "concept": {
                  "type": "object",
                  "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                  "properties": {
                    "text": {
                      "type": "string"
                    },
                    "codes": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                        "properties": {
                          "system": {
                            "type": "string",
                            "enum": [
                              "LOINC",
                              "SNOMED",
                              "RxNorm",
                              "ICD10",
                              "UCUM"
                            ]
                          },
                          "code": {
                            "type": "string"
                          },
                          "display": {
                            "type": [
                              "string",
                              "null"
                            ]
                          }
                        },
                        "required": [
                          "system",
                          "code",
                          "display"
                        ],
                        "additionalProperties": false
                      }
                    }
                  },
                  "required": [
                    "text",
                    "codes"
                  ],
                  "additionalProperties": false
                },
                "op": {
                  "type": "string",
                  "enum": [
                    "<",
                    "<=",
                    ">",
                    ">=",
                    "==",
                    "!=",
                    "between"
                  ]
                },
                "value": {
                  "type": "number"
                },
                "value_high": {
                  "type": [
                    "number",
                    "null"
                  ]
                },
                "unit": {
                  "type": "string"
                },
                "window": {
                  "anyOf": [
                    {
                      "type": "object",
                      "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                      "properties": {
                        "relation": {
                          "type": "string",
                          "enum": [
                            "within",
                            "before",
                            "after",
                            "ever",
                            "current"
                          ]
                        },
                        "amount": {
                          "type": [
                            "integer",
                            "null"
                          ]
                        },
                        "unit": {
                          "anyOf": [
                            {
                              "type": "string",
                              "enum": [
                                "days",
                                "weeks",
                                "months",
                                "years"
                              ]
                            },
                            {
                              "type": "null"
                            }
                          ]
                        },
                        "anchor": {
                          "type": "string",
                          "enum": [
                            "screening",
                            "enrolment",
                            "randomisation",
                            "consent",
                            "first_dose"
                          ]
                        }
                      },
                      "required": [
                        "relation",
                        "amount",
                        "unit",
                        "anchor"
                      ],
                      "additionalProperties": false
                    },
                    {
                      "type": "null"
                    }
                  ]
                }
              },
              "required": [
                "type",
                "concept",
                "op",
                "value",
                "value_high",
                "unit",
                "window"
              ],
              "additionalProperties": false
            },
            {
              "type": "object",
              "description": "Whether a coded thing is on the chart at all: a condition, a drug, a procedure.",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "condition",
                    "medication",
                    "procedure"
                  ]
                },
                "concept": {
                  "type": "object",
                  "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                  "properties": {
                    "text": {
                      "type": "string"
                    },
                    "codes": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                        "properties": {
                          "system": {
                            "type": "string",
                            "enum": [
                              "LOINC",
                              "SNOMED",
                              "RxNorm",
                              "ICD10",
                              "UCUM"
                            ]
                          },
                          "code": {
                            "type": "string"
                          },
                          "display": {
                            "type": [
                              "string",
                              "null"
                            ]
                          }
                        },
                        "required": [
                          "system",
                          "code",
                          "display"
                        ],
                        "additionalProperties": false
                      }
                    }
                  },
                  "required": [
                    "text",
                    "codes"
                  ],
                  "additionalProperties": false
                },
                "presence": {
                  "type": "string",
                  "enum": [
                    "present",
                    "absent"
                  ]
                },
                "window": {
                  "anyOf": [
                    {
                      "type": "object",
                      "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                      "properties": {
                        "relation": {
                          "type": "string",
                          "enum": [
                            "within",
                            "before",
                            "after",
                            "ever",
                            "current"
                          ]
                        },
                        "amount": {
                          "type": [
                            "integer",
                            "null"
                          ]
                        },
                        "unit": {
                          "anyOf": [
                            {
                              "type": "string",
                              "enum": [
                                "days",
                                "weeks",
                                "months",
                                "years"
                              ]
                            },
                            {
                              "type": "null"
                            }
                          ]
                        },
                        "anchor": {
                          "type": "string",
                          "enum": [
                            "screening",
                            "enrolment",
                            "randomisation",
                            "consent",
                            "first_dose"
                          ]
                        }
                      },
                      "required": [
                        "relation",
                        "amount",
                        "unit",
                        "anchor"
                      ],
                      "additionalProperties": false
                    },
                    {
                      "type": "null"
                    }
                  ]
                }
              },
              "required": [
                "type",
                "concept",
                "presence",
                "window"
              ],
              "additionalProperties": false
            },
            {
              "type": "object",
              "description": "Age and sex, which come from the patient resource rather than from clinical events.",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "demographic"
                  ]
                },
                "field": {
                  "type": "string",
                  "enum": [
                    "age",
                    "sex"
                  ]
                },
                "op": {
                  "type": "string",
                  "enum": [
                    "<",
                    "<=",
                    ">",
                    ">=",
                    "==",
                    "!="
                  ]
                },
                "value": {
                  "type": [
                    "number",
                    "string"
                  ]
                },
                "unit": {
                  "type": [
                    "string",
                    "null"
                  ]
                }
              },
              "required": [
                "type",
                "field",
                "op",
                "value",
                "unit"
              ],
              "additionalProperties": false
            },
            {
              "type": "object",
              "description": "A criterion that cannot be honestly formalised. It stays unresolved forever, by design.\n\n`settlement` says *why* no chart can answer it, and the difference is load-bearing.\n\nA criterion settled `from_data` was a question about the patient's record that we failed to\nformalise \u2014 a threshold with no number, an open category. It is a gap, and it blocks a verdict.\n\nA criterion settled `at_visit` is not a gap at all. Signed informed consent, a procedure planned\nafter randomisation, the investigator's own judgement of the patient in person: these have the\nsame answer for every chart ever written, because they are settled when the patient comes in.\nTreating them as unresolved data made ELIGIBLE unreachable for every real protocol we hold \u2014 one\nconsent criterion and the screening abstains, which is not caution but paralysis.\n\nThe default is `from_data`, so a compiler that says nothing cannot thereby unblock a verdict.",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "unsupported"
                  ]
                },
                "reason": {
                  "type": "string"
                },
                "settlement": {
                  "type": "string",
                  "enum": [
                    "from_data",
                    "at_visit"
                  ]
                }
              },
              "required": [
                "type",
                "reason",
                "settlement"
              ],
              "additionalProperties": false
            },
            {
              "type": "object",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "all_of",
                    "any_of",
                    "not"
                  ]
                },
                "operands": {
                  "type": "array",
                  "items": {
                    "anyOf": [
                      {
                        "type": "object",
                        "description": "A numeric comparison against a measurement: labs, vitals, scores.",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "observation"
                            ]
                          },
                          "concept": {
                            "type": "object",
                            "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                            "properties": {
                              "text": {
                                "type": "string"
                              },
                              "codes": {
                                "type": "array",
                                "items": {
                                  "type": "object",
                                  "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                                  "properties": {
                                    "system": {
                                      "type": "string",
                                      "enum": [
                                        "LOINC",
                                        "SNOMED",
                                        "RxNorm",
                                        "ICD10",
                                        "UCUM"
                                      ]
                                    },
                                    "code": {
                                      "type": "string"
                                    },
                                    "display": {
                                      "type": [
                                        "string",
                                        "null"
                                      ]
                                    }
                                  },
                                  "required": [
                                    "system",
                                    "code",
                                    "display"
                                  ],
                                  "additionalProperties": false
                                }
                              }
                            },
                            "required": [
                              "text",
                              "codes"
                            ],
                            "additionalProperties": false
                          },
                          "op": {
                            "type": "string",
                            "enum": [
                              "<",
                              "<=",
                              ">",
                              ">=",
                              "==",
                              "!=",
                              "between"
                            ]
                          },
                          "value": {
                            "type": "number"
                          },
                          "value_high": {
                            "type": [
                              "number",
                              "null"
                            ]
                          },
                          "unit": {
                            "type": "string"
                          },
                          "window": {
                            "anyOf": [
                              {
                                "type": "object",
                                "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                                "properties": {
                                  "relation": {
                                    "type": "string",
                                    "enum": [
                                      "within",
                                      "before",
                                      "after",
                                      "ever",
                                      "current"
                                    ]
                                  },
                                  "amount": {
                                    "type": [
                                      "integer",
                                      "null"
                                    ]
                                  },
                                  "unit": {
                                    "anyOf": [
                                      {
                                        "type": "string",
                                        "enum": [
                                          "days",
                                          "weeks",
                                          "months",
                                          "years"
                                        ]
                                      },
                                      {
                                        "type": "null"
                                      }
                                    ]
                                  },
                                  "anchor": {
                                    "type": "string",
                                    "enum": [
                                      "screening",
                                      "enrolment",
                                      "randomisation",
                                      "consent",
                                      "first_dose"
                                    ]
                                  }
                                },
                                "required": [
                                  "relation",
                                  "amount",
                                  "unit",
                                  "anchor"
                                ],
                                "additionalProperties": false
                              },
                              {
                                "type": "null"
                              }
                            ]
                          }
                        },
                        "required": [
                          "type",
                          "concept",
                          "op",
                          "value",
                          "value_high",
                          "unit",
                          "window"
                        ],
                        "additionalProperties": false
                      },
                      {
                        "type": "object",
                        "description": "Whether a coded thing is on the chart at all: a condition, a drug, a procedure.",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "condition",
                              "medication",
                              "procedure"
                            ]
                          },
                          "concept": {
                            "type": "object",
                            "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                            "properties": {
                              "text": {
                                "type": "string"
                              },
                              "codes": {
                                "type": "array",
                                "items": {
                                  "type": "object",
                                  "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                                  "properties": {
                                    "system": {
                                      "type": "string",
                                      "enum": [
                                        "LOINC",
                                        "SNOMED",
                                        "RxNorm",
                                        "ICD10",
                                        "UCUM"
                                      ]
                                    },
                                    "code": {
                                      "type": "string"
                                    },
                                    "display": {
                                      "type": [
                                        "string",
                                        "null"
                                      ]
                                    }
                                  },
                                  "required": [
                                    "system",
                                    "code",
                                    "display"
                                  ],
                                  "additionalProperties": false
                                }
                              }
                            },
                            "required": [
                              "text",
                              "codes"
                            ],
                            "additionalProperties": false
                          },
                          "presence": {
                            "type": "string",
                            "enum": [
                              "present",
                              "absent"
                            ]
                          },
                          "window": {
                            "anyOf": [
                              {
                                "type": "object",
                                "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                                "properties": {
                                  "relation": {
                                    "type": "string",
                                    "enum": [
                                      "within",
                                      "before",
                                      "after",
                                      "ever",
                                      "current"
                                    ]
                                  },
                                  "amount": {
                                    "type": [
                                      "integer",
                                      "null"
                                    ]
                                  },
                                  "unit": {
                                    "anyOf": [
                                      {
                                        "type": "string",
                                        "enum": [
                                          "days",
                                          "weeks",
                                          "months",
                                          "years"
                                        ]
                                      },
                                      {
                                        "type": "null"
                                      }
                                    ]
                                  },
                                  "anchor": {
                                    "type": "string",
                                    "enum": [
                                      "screening",
                                      "enrolment",
                                      "randomisation",
                                      "consent",
                                      "first_dose"
                                    ]
                                  }
                                },
                                "required": [
                                  "relation",
                                  "amount",
                                  "unit",
                                  "anchor"
                                ],
                                "additionalProperties": false
                              },
                              {
                                "type": "null"
                              }
                            ]
                          }
                        },
                        "required": [
                          "type",
                          "concept",
                          "presence",
                          "window"
                        ],
                        "additionalProperties": false
                      },
                      {
                        "type": "object",
                        "description": "Age and sex, which come from the patient resource rather than from clinical events.",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "demographic"
                            ]
                          },
                          "field": {
                            "type": "string",
                            "enum": [
                              "age",
                              "sex"
                            ]
                          },
                          "op": {
                            "type": "string",
                            "enum": [
                              "<",
                              "<=",
                              ">",
                              ">=",
                              "==",
                              "!="
                            ]
                          },
                          "value": {
                            "type": [
                              "number",
                              "string"
                            ]
                          },
                          "unit": {
                            "type": [
                              "string",
                              "null"
                            ]
                          }
                        },
                        "required": [
                          "type",
                          "field",
                          "op",
                          "value",
                          "unit"
                        ],
                        "additionalProperties": false
                      },
                      {
                        "type": "object",
                        "description": "A criterion that cannot be honestly formalised. It stays unresolved forever, by design.\n\n`settlement` says *why* no chart can answer it, and the difference is load-bearing.\n\nA criterion settled `from_data` was a question about the patient's record that we failed to\nformalise \u2014 a threshold with no number, an open category. It is a gap, and it blocks a verdict.\n\nA criterion settled `at_visit` is not a gap at all. Signed informed consent, a procedure planned\nafter randomisation, the investigator's own judgement of the patient in person: these have the\nsame answer for every chart ever written, because they are settled when the patient comes in.\nTreating them as unresolved data made ELIGIBLE unreachable for every real protocol we hold \u2014 one\nconsent criterion and the screening abstains, which is not caution but paralysis.\n\nThe default is `from_data`, so a compiler that says nothing cannot thereby unblock a verdict.",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "unsupported"
                            ]
                          },
                          "reason": {
                            "type": "string"
                          },
                          "settlement": {
                            "type": "string",
                            "enum": [
                              "from_data",
                              "at_visit"
                            ]
                          }
                        },
                        "required": [
                          "type",
                          "reason",
                          "settlement"
                        ],
                        "additionalProperties": false
                      },
                      {
                        "type": "object",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "all_of",
                              "any_of",
                              "not"
                            ]
                          },
                          "operands": {
                            "type": "array",
                            "items": {
                              "anyOf": [
                                {
                                  "type": "object",
                                  "description": "A numeric comparison against a measurement: labs, vitals, scores.",
                                  "properties": {
                                    "type": {
                                      "type": "string",
                                      "enum": [
                                        "observation"
                                      ]
                                    },
                                    "concept": {
                                      "type": "object",
                                      "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                                      "properties": {
                                        "text": {
                                          "type": "string"
                                        },
                                        "codes": {
                                          "type": "array",
                                          "items": {
                                            "type": "object",
                                            "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                                            "properties": {
                                              "system": {
                                                "type": "string",
                                                "enum": [
                                                  "LOINC",
                                                  "SNOMED",
                                                  "RxNorm",
                                                  "ICD10",
                                                  "UCUM"
                                                ]
                                              },
                                              "code": {
                                                "type": "string"
                                              },
                                              "display": {
                                                "type": [
                                                  "string",
                                                  "null"
                                                ]
                                              }
                                            },
                                            "required": [
                                              "system",
                                              "code",
                                              "display"
                                            ],
                                            "additionalProperties": false
                                          }
                                        }
                                      },
                                      "required": [
                                        "text",
                                        "codes"
                                      ],
                                      "additionalProperties": false
                                    },
                                    "op": {
                                      "type": "string",
                                      "enum": [
                                        "<",
                                        "<=",
                                        ">",
                                        ">=",
                                        "==",
                                        "!=",
                                        "between"
                                      ]
                                    },
                                    "value": {
                                      "type": "number"
                                    },
                                    "value_high": {
                                      "type": [
                                        "number",
                                        "null"
                                      ]
                                    },
                                    "unit": {
                                      "type": "string"
                                    },
                                    "window": {
                                      "anyOf": [
                                        {
                                          "type": "object",
                                          "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                                          "properties": {
                                            "relation": {
                                              "type": "string",
                                              "enum": [
                                                "within",
                                                "before",
                                                "after",
                                                "ever",
                                                "current"
                                              ]
                                            },
                                            "amount": {
                                              "type": [
                                                "integer",
                                                "null"
                                              ]
                                            },
                                            "unit": {
                                              "anyOf": [
                                                {
                                                  "type": "string",
                                                  "enum": [
                                                    "days",
                                                    "weeks",
                                                    "months",
                                                    "years"
                                                  ]
                                                },
                                                {
                                                  "type": "null"
                                                }
                                              ]
                                            },
                                            "anchor": {
                                              "type": "string",
                                              "enum": [
                                                "screening",
                                                "enrolment",
                                                "randomisation",
                                                "consent",
                                                "first_dose"
                                              ]
                                            }
                                          },
                                          "required": [
                                            "relation",
                                            "amount",
                                            "unit",
                                            "anchor"
                                          ],
                                          "additionalProperties": false
                                        },
                                        {
                                          "type": "null"
                                        }
                                      ]
                                    }
                                  },
                                  "required": [
                                    "type",
                                    "concept",
                                    "op",
                                    "value",
                                    "value_high",
                                    "unit",
                                    "window"
                                  ],
                                  "additionalProperties": false
                                },
                                {
                                  "type": "object",
                                  "description": "Whether a coded thing is on the chart at all: a condition, a drug, a procedure.",
                                  "properties": {
                                    "type": {
                                      "type": "string",
                                      "enum": [
                                        "condition",
                                        "medication",
                                        "procedure"
                                      ]
                                    },
                                    "concept": {
                                      "type": "object",
                                      "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                                      "properties": {
                                        "text": {
                                          "type": "string"
                                        },
                                        "codes": {
                                          "type": "array",
                                          "items": {
                                            "type": "object",
                                            "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                                            "properties": {
                                              "system": {
                                                "type": "string",
                                                "enum": [
                                                  "LOINC",
                                                  "SNOMED",
                                                  "RxNorm",
                                                  "ICD10",
                                                  "UCUM"
                                                ]
                                              },
                                              "code": {
                                                "type": "string"
                                              },
                                              "display": {
                                                "type": [
                                                  "string",
                                                  "null"
                                                ]
                                              }
                                            },
                                            "required": [
                                              "system",
                                              "code",
                                              "display"
                                            ],
                                            "additionalProperties": false
                                          }
                                        }
                                      },
                                      "required": [
                                        "text",
                                        "codes"
                                      ],
                                      "additionalProperties": false
                                    },
                                    "presence": {
                                      "type": "string",
                                      "enum": [
                                        "present",
                                        "absent"
                                      ]
                                    },
                                    "window": {
                                      "anyOf": [
                                        {
                                          "type": "object",
                                          "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                                          "properties": {
                                            "relation": {
                                              "type": "string",
                                              "enum": [
                                                "within",
                                                "before",
                                                "after",
                                                "ever",
                                                "current"
                                              ]
                                            },
                                            "amount": {
                                              "type": [
                                                "integer",
                                                "null"
                                              ]
                                            },
                                            "unit": {
                                              "anyOf": [
                                                {
                                                  "type": "string",
                                                  "enum": [
                                                    "days",
                                                    "weeks",
                                                    "months",
                                                    "years"
                                                  ]
                                                },
                                                {
                                                  "type": "null"
                                                }
                                              ]
                                            },
                                            "anchor": {
                                              "type": "string",
                                              "enum": [
                                                "screening",
                                                "enrolment",
                                                "randomisation",
                                                "consent",
                                                "first_dose"
                                              ]
                                            }
                                          },
                                          "required": [
                                            "relation",
                                            "amount",
                                            "unit",
                                            "anchor"
                                          ],
                                          "additionalProperties": false
                                        },
                                        {
                                          "type": "null"
                                        }
                                      ]
                                    }
                                  },
                                  "required": [
                                    "type",
                                    "concept",
                                    "presence",
                                    "window"
                                  ],
                                  "additionalProperties": false
                                },
                                {
                                  "type": "object",
                                  "description": "Age and sex, which come from the patient resource rather than from clinical events.",
                                  "properties": {
                                    "type": {
                                      "type": "string",
                                      "enum": [
                                        "demographic"
                                      ]
                                    },
                                    "field": {
                                      "type": "string",
                                      "enum": [
                                        "age",
                                        "sex"
                                      ]
                                    },
                                    "op": {
                                      "type": "string",
                                      "enum": [
                                        "<",
                                        "<=",
                                        ">",
                                        ">=",
                                        "==",
                                        "!="
                                      ]
                                    },
                                    "value": {
                                      "type": [
                                        "number",
                                        "string"
                                      ]
                                    },
                                    "unit": {
                                      "type": [
                                        "string",
                                        "null"
                                      ]
                                    }
                                  },
                                  "required": [
                                    "type",
                                    "field",
                                    "op",
                                    "value",
                                    "unit"
                                  ],
                                  "additionalProperties": false
                                },
                                {
                                  "type": "object",
                                  "description": "A criterion that cannot be honestly formalised. It stays unresolved forever, by design.\n\n`settlement` says *why* no chart can answer it, and the difference is load-bearing.\n\nA criterion settled `from_data` was a question about the patient's record that we failed to\nformalise \u2014 a threshold with no number, an open category. It is a gap, and it blocks a verdict.\n\nA criterion settled `at_visit` is not a gap at all. Signed informed consent, a procedure planned\nafter randomisation, the investigator's own judgement of the patient in person: these have the\nsame answer for every chart ever written, because they are settled when the patient comes in.\nTreating them as unresolved data made ELIGIBLE unreachable for every real protocol we hold \u2014 one\nconsent criterion and the screening abstains, which is not caution but paralysis.\n\nThe default is `from_data`, so a compiler that says nothing cannot thereby unblock a verdict.",
                                  "properties": {
                                    "type": {
                                      "type": "string",
                                      "enum": [
                                        "unsupported"
                                      ]
                                    },
                                    "reason": {
                                      "type": "string"
                                    },
                                    "settlement": {
                                      "type": "string",
                                      "enum": [
                                        "from_data",
                                        "at_visit"
                                      ]
                                    }
                                  },
                                  "required": [
                                    "type",
                                    "reason",
                                    "settlement"
                                  ],
                                  "additionalProperties": false
                                }
                              ]
                            }
                          }
                        },
                        "required": [
                          "type",
                          "operands"
                        ],
                        "additionalProperties": false
                      }
                    ]
                  }
                }
              },
              "required": [
                "type",
                "operands"
              ],
              "additionalProperties": false
            }
          ]
        },
        {
          "type": "null"
        }
      ]
    },
    "notes": {
      "type": [
        "string",
        "null"
      ],
      "description": "Why this span was hard, or why it is not a criterion."
    }
  },
  "required": [
    "is_criterion",
    "kind",
    "source_quote",
    "predicate",
    "notes"
  ],
  "additionalProperties": false
}

[user]
Section: inclusion

Criterion:
Signed written informed consent.
```

Response:

```
{"is_criterion": true, "kind": "inclusion", "source_quote": "Signed written informed consent.", "predicate": {"type": "unsupported", "reason": "Informed consent is a procedural/administrative act confirmed at the screening visit, not a fact recorded in the patient's clinical record.", "settlement": "at_visit"}, "notes": null}
```

Validated against the schema.

### Result

```json
{
  "is_criterion": true,
  "kind": "inclusion",
  "source_quote": "Signed written informed consent.",
  "predicate": {
    "type": "unsupported",
    "reason": "Informed consent is a procedural/administrative act confirmed at the screening visit, not a fact recorded in the patient's clinical record.",
    "settlement": "at_visit"
  },
  "notes": null
}
```

## 5. compiler on venice/claude-sonnet-5

- **Started:** 2026-08-30T10:35:10Z
- **Tier used:** `json_object`
- **Retries:** 1
- **Tokens:** 13456 in / 475 out
- **Estimated cost:** $0.0317
- **Outcome:** validated

### Instructions

```
# Criteria compiler

You formalise one span of a clinical trial's eligibility criteria into a machine-checkable
predicate. A downstream engine will evaluate that predicate against a patient's structured record
and produce a screening verdict. You never see a patient and you never decide eligibility.

You are given one span at a time, together with the section it appeared under and, where the
protocol nested sub-conditions beneath it, its children. Treat the whole unit as one criterion.

## The only judgement that matters

A criterion you formalise incorrectly is worse than a criterion you decline to formalise. The
engine has an explicit `unsupported` predicate; a criterion marked unsupported goes to a research
coordinator, who reads it and decides. That is a normal, safe, expected outcome. A predicate that
looks right and means something slightly different produces a confident wrong verdict that nobody
catches.

So: when the span does not map cleanly onto the vocabulary below, return `unsupported` with a
reason. Do not approximate. Do not drop a qualifier to make something fit. Do not invent a
threshold the protocol did not state.

Use `unsupported` when the span:

- depends on clinical judgement — "in the opinion of the investigator", "otherwise unsuitable",
  "clinically significant", "adequate organ function" without stated numbers;
- depends on something no chart records — willingness to comply, ability to attend visits,
  informed consent, contraception intentions, geographic availability;
- names a threshold relative to something the engine cannot resolve, such as "above the upper
  limit of normal" (the reference range is laboratory-specific and is not in the record);
- describes a process rather than a state — "must complete a washout", "will be randomised";
- is a class of drug or a category of disease broad enough that no single code captures it, and
  the protocol does not enumerate members;
- nests more deeply than the schema allows.

### Which kind of unsupported

Every `unsupported` criterion also carries a `settlement`, and the choice matters more than it
looks. It decides whether one criterion holds up the whole screening.

**`at_visit`** — the criterion is settled when the patient comes in, and would be settled the same
way for every patient in the world. No chart that has ever been written could answer it, so its
being unanswered here says nothing about *this* patient. A coordinator confirms it at the screening
visit, and the packet lists it for them.

> Signed written informed consent.
> Willing and able to comply with the study schedule.
> Planned coronary procedure or surgery after randomization.
> Planning to start an SGLT2 inhibitor during the study.
> In the investigator's opinion, unsuitable for the study.
> Women of childbearing potential must agree to use contraception during the trial.

**`from_data`** — the criterion asks about the patient's recorded history or state, and we simply
could not formalise the question. That is a gap in what we know about this patient, and it does hold
up the screening.

> Adequate organ function. *(about the record; no threshold stated)*
> Any clinically significant abnormality on screening laboratory tests. *(about the record)*
> Lower extremity complications such as skin ulcer, infection, osteomyelitis and gangrene.
> *(about the record; an open list this schema cannot enumerate)*
> Alanine aminotransferase above the upper limit of normal. *(about the record; the range is
> laboratory-specific and not in it)*

The test to apply, in one sentence: **would a complete and perfect medical record answer this?** If
yes, and we merely failed to express it, that is `from_data`. If even a perfect record could not,
because the answer does not exist until the patient is in the room, that is `at_visit`.

When you are unsure, choose `from_data`. It is the cautious answer: it sends the criterion to a
human either way, and it does not let a verdict through on a criterion that should have stopped it.

## Vocabulary

**`observation`** — a numeric comparison against a measurement: laboratory values, vital signs,
scores. Give the analyte as the protocol names it, the operator, the number, and the unit exactly
as written. `between` is for a two-sided range and takes both bounds. Never convert units; the
engine converts, and it knows which conversions are safe.

**`condition`, `medication`, `procedure`** — whether something is on the chart. `presence`
is `present` when the protocol requires it and `absent` when the protocol requires its absence.

Note carefully: an exclusion criterion that reads "history of myocardial infarction" is a
**`present`** predicate under an **exclusion** criterion. Do not negate it yourself — the engine
knows that a met exclusion rules the patient out. Only use `absent` when the protocol itself
states an absence as a requirement, such as an inclusion criterion reading "no history of
malignancy".

**`demographic`** — age and sex only.

**`all_of` / `any_of` / `not`** — for spans that carry several conditions. "eGFR ≥25 and ≤60" is a
single `observation` with `between`, not a composite. "On an ACE inhibitor or an ARB" is `any_of`.
Sub-bullets beneath a parent bullet are almost always conjunctive: `all_of`.

## Temporal windows

Attach a window whenever the protocol bounds the evidence in time: "within 6 months prior to
screening", "in the last 30 days", "no myocardial infarction within 12 weeks". Use the number and
unit the protocol gives.

Protocols anchor windows to different events — screening, enrolment, randomisation, consent — and
those are genuinely different dates. The engine anchors everything to the screening date. If the
span anchors to something else and the difference could plausibly matter, say so in `notes`; if
the anchor is doing real work in the criterion, return `unsupported`.

## Quoting

`source_quote` must be the span reproduced character for character, including its punctuation and
its unicode operators. It is checked against the protocol text automatically, and a criterion whose
quote does not match is discarded. Do not tidy, expand abbreviations, or normalise `≥` to `>=`.

## Spans that are not criteria

Registry text contains section headings, cross-references and standard boilerplate. If the span is
one of those, set `is_criterion` to false and say why in `notes`. This is a correct answer, not a
failure.

## Concepts

Give the concept's `text` as the protocol names it. Leave `codes` empty — terminology resolution is
a separate step with its own controls. A code you guess here will be trusted downstream.

```

### Request

```
Section: exclusion

Criterion:
Antihyperglycemic treatment has not been stable within 12 weeks prior to screening.
```

### Attempt 1, tier `json_schema`

The provider rejected the request:

```
TapeMiss: no recorded answer for this request.
  model:  claude-sonnet-5
  system: "# Criteria compiler\n\nYou formalise one span of a clinical trial's eligibility cr"
  user:   'Section: exclusion\n\nCriterion:\nAntihyperglycemic treatment has not been stable within 12 weeks prior to screening.'
The code has changed since the tape was recorded. Re-record with a key, or check out the commit the tape belongs to.
```

### Attempt 2, tier `json_object`

Restarted with:

```
[system]
# Criteria compiler

You formalise one span of a clinical trial's eligibility criteria into a machine-checkable
predicate. A downstream engine will evaluate that predicate against a patient's structured record
and produce a screening verdict. You never see a patient and you never decide eligibility.

You are given one span at a time, together with the section it appeared under and, where the
protocol nested sub-conditions beneath it, its children. Treat the whole unit as one criterion.

## The only judgement that matters

A criterion you formalise incorrectly is worse than a criterion you decline to formalise. The
engine has an explicit `unsupported` predicate; a criterion marked unsupported goes to a research
coordinator, who reads it and decides. That is a normal, safe, expected outcome. A predicate that
looks right and means something slightly different produces a confident wrong verdict that nobody
catches.

So: when the span does not map cleanly onto the vocabulary below, return `unsupported` with a
reason. Do not approximate. Do not drop a qualifier to make something fit. Do not invent a
threshold the protocol did not state.

Use `unsupported` when the span:

- depends on clinical judgement — "in the opinion of the investigator", "otherwise unsuitable",
  "clinically significant", "adequate organ function" without stated numbers;
- depends on something no chart records — willingness to comply, ability to attend visits,
  informed consent, contraception intentions, geographic availability;
- names a threshold relative to something the engine cannot resolve, such as "above the upper
  limit of normal" (the reference range is laboratory-specific and is not in the record);
- describes a process rather than a state — "must complete a washout", "will be randomised";
- is a class of drug or a category of disease broad enough that no single code captures it, and
  the protocol does not enumerate members;
- nests more deeply than the schema allows.

### Which kind of unsupported

Every `unsupported` criterion also carries a `settlement`, and the choice matters more than it
looks. It decides whether one criterion holds up the whole screening.

**`at_visit`** — the criterion is settled when the patient comes in, and would be settled the same
way for every patient in the world. No chart that has ever been written could answer it, so its
being unanswered here says nothing about *this* patient. A coordinator confirms it at the screening
visit, and the packet lists it for them.

> Signed written informed consent.
> Willing and able to comply with the study schedule.
> Planned coronary procedure or surgery after randomization.
> Planning to start an SGLT2 inhibitor during the study.
> In the investigator's opinion, unsuitable for the study.
> Women of childbearing potential must agree to use contraception during the trial.

**`from_data`** — the criterion asks about the patient's recorded history or state, and we simply
could not formalise the question. That is a gap in what we know about this patient, and it does hold
up the screening.

> Adequate organ function. *(about the record; no threshold stated)*
> Any clinically significant abnormality on screening laboratory tests. *(about the record)*
> Lower extremity complications such as skin ulcer, infection, osteomyelitis and gangrene.
> *(about the record; an open list this schema cannot enumerate)*
> Alanine aminotransferase above the upper limit of normal. *(about the record; the range is
> laboratory-specific and not in it)*

The test to apply, in one sentence: **would a complete and perfect medical record answer this?** If
yes, and we merely failed to express it, that is `from_data`. If even a perfect record could not,
because the answer does not exist until the patient is in the room, that is `at_visit`.

When you are unsure, choose `from_data`. It is the cautious answer: it sends the criterion to a
human either way, and it does not let a verdict through on a criterion that should have stopped it.

## Vocabulary

**`observation`** — a numeric comparison against a measurement: laboratory values, vital signs,
scores. Give the analyte as the protocol names it, the operator, the number, and the unit exactly
as written. `between` is for a two-sided range and takes both bounds. Never convert units; the
engine converts, and it knows which conversions are safe.

**`condition`, `medication`, `procedure`** — whether something is on the chart. `presence`
is `present` when the protocol requires it and `absent` when the protocol requires its absence.

Note carefully: an exclusion criterion that reads "history of myocardial infarction" is a
**`present`** predicate under an **exclusion** criterion. Do not negate it yourself — the engine
knows that a met exclusion rules the patient out. Only use `absent` when the protocol itself
states an absence as a requirement, such as an inclusion criterion reading "no history of
malignancy".

**`demographic`** — age and sex only.

**`all_of` / `any_of` / `not`** — for spans that carry several conditions. "eGFR ≥25 and ≤60" is a
single `observation` with `between`, not a composite. "On an ACE inhibitor or an ARB" is `any_of`.
Sub-bullets beneath a parent bullet are almost always conjunctive: `all_of`.

## Temporal windows

Attach a window whenever the protocol bounds the evidence in time: "within 6 months prior to
screening", "in the last 30 days", "no myocardial infarction within 12 weeks". Use the number and
unit the protocol gives.

Protocols anchor windows to different events — screening, enrolment, randomisation, consent — and
those are genuinely different dates. The engine anchors everything to the screening date. If the
span anchors to something else and the difference could plausibly matter, say so in `notes`; if
the anchor is doing real work in the criterion, return `unsupported`.

## Quoting

`source_quote` must be the span reproduced character for character, including its punctuation and
its unicode operators. It is checked against the protocol text automatically, and a criterion whose
quote does not match is discarded. Do not tidy, expand abbreviations, or normalise `≥` to `>=`.

## Spans that are not criteria

Registry text contains section headings, cross-references and standard boilerplate. If the span is
one of those, set `is_criterion` to false and say why in `notes`. This is a correct answer, not a
failure.

## Concepts

Give the concept's `text` as the protocol names it. Leave `codes` empty — terminology resolution is
a separate step with its own controls. A code you guess here will be trusted downstream.


Reply with a single JSON object and nothing else. It must conform to this JSON schema:

{
  "type": "object",
  "description": "The result of formalising one span of eligibility text. Set is_criterion to false when the span is a heading, a note to readers, or registry boilerplate rather than a condition a patient can meet.",
  "properties": {
    "is_criterion": {
      "type": "boolean"
    },
    "kind": {
      "description": "Only needed when the span sits under no inclusion or exclusion header.",
      "anyOf": [
        {
          "type": "string",
          "enum": [
            "inclusion",
            "exclusion"
          ]
        },
        {
          "type": "null"
        }
      ]
    },
    "source_quote": {
      "type": [
        "string",
        "null"
      ],
      "description": "The span copied verbatim, character for character."
    },
    "predicate": {
      "anyOf": [
        {
          "anyOf": [
            {
              "type": "object",
              "description": "A numeric comparison against a measurement: labs, vitals, scores.",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "observation"
                  ]
                },
                "concept": {
                  "type": "object",
                  "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                  "properties": {
                    "text": {
                      "type": "string"
                    },
                    "codes": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                        "properties": {
                          "system": {
                            "type": "string",
                            "enum": [
                              "LOINC",
                              "SNOMED",
                              "RxNorm",
                              "ICD10",
                              "UCUM"
                            ]
                          },
                          "code": {
                            "type": "string"
                          },
                          "display": {
                            "type": [
                              "string",
                              "null"
                            ]
                          }
                        },
                        "required": [
                          "system",
                          "code",
                          "display"
                        ],
                        "additionalProperties": false
                      }
                    }
                  },
                  "required": [
                    "text",
                    "codes"
                  ],
                  "additionalProperties": false
                },
                "op": {
                  "type": "string",
                  "enum": [
                    "<",
                    "<=",
                    ">",
                    ">=",
                    "==",
                    "!=",
                    "between"
                  ]
                },
                "value": {
                  "type": "number"
                },
                "value_high": {
                  "type": [
                    "number",
                    "null"
                  ]
                },
                "unit": {
                  "type": "string"
                },
                "window": {
                  "anyOf": [
                    {
                      "type": "object",
                      "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                      "properties": {
                        "relation": {
                          "type": "string",
                          "enum": [
                            "within",
                            "before",
                            "after",
                            "ever",
                            "current"
                          ]
                        },
                        "amount": {
                          "type": [
                            "integer",
                            "null"
                          ]
                        },
                        "unit": {
                          "anyOf": [
                            {
                              "type": "string",
                              "enum": [
                                "days",
                                "weeks",
                                "months",
                                "years"
                              ]
                            },
                            {
                              "type": "null"
                            }
                          ]
                        },
                        "anchor": {
                          "type": "string",
                          "enum": [
                            "screening",
                            "enrolment",
                            "randomisation",
                            "consent",
                            "first_dose"
                          ]
                        }
                      },
                      "required": [
                        "relation",
                        "amount",
                        "unit",
                        "anchor"
                      ],
                      "additionalProperties": false
                    },
                    {
                      "type": "null"
                    }
                  ]
                }
              },
              "required": [
                "type",
                "concept",
                "op",
                "value",
                "value_high",
                "unit",
                "window"
              ],
              "additionalProperties": false
            },
            {
              "type": "object",
              "description": "Whether a coded thing is on the chart at all: a condition, a drug, a procedure.",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "condition",
                    "medication",
                    "procedure"
                  ]
                },
                "concept": {
                  "type": "object",
                  "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                  "properties": {
                    "text": {
                      "type": "string"
                    },
                    "codes": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                        "properties": {
                          "system": {
                            "type": "string",
                            "enum": [
                              "LOINC",
                              "SNOMED",
                              "RxNorm",
                              "ICD10",
                              "UCUM"
                            ]
                          },
                          "code": {
                            "type": "string"
                          },
                          "display": {
                            "type": [
                              "string",
                              "null"
                            ]
                          }
                        },
                        "required": [
                          "system",
                          "code",
                          "display"
                        ],
                        "additionalProperties": false
                      }
                    }
                  },
                  "required": [
                    "text",
                    "codes"
                  ],
                  "additionalProperties": false
                },
                "presence": {
                  "type": "string",
                  "enum": [
                    "present",
                    "absent"
                  ]
                },
                "window": {
                  "anyOf": [
                    {
                      "type": "object",
                      "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                      "properties": {
                        "relation": {
                          "type": "string",
                          "enum": [
                            "within",
                            "before",
                            "after",
                            "ever",
                            "current"
                          ]
                        },
                        "amount": {
                          "type": [
                            "integer",
                            "null"
                          ]
                        },
                        "unit": {
                          "anyOf": [
                            {
                              "type": "string",
                              "enum": [
                                "days",
                                "weeks",
                                "months",
                                "years"
                              ]
                            },
                            {
                              "type": "null"
                            }
                          ]
                        },
                        "anchor": {
                          "type": "string",
                          "enum": [
                            "screening",
                            "enrolment",
                            "randomisation",
                            "consent",
                            "first_dose"
                          ]
                        }
                      },
                      "required": [
                        "relation",
                        "amount",
                        "unit",
                        "anchor"
                      ],
                      "additionalProperties": false
                    },
                    {
                      "type": "null"
                    }
                  ]
                }
              },
              "required": [
                "type",
                "concept",
                "presence",
                "window"
              ],
              "additionalProperties": false
            },
            {
              "type": "object",
              "description": "Age and sex, which come from the patient resource rather than from clinical events.",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "demographic"
                  ]
                },
                "field": {
                  "type": "string",
                  "enum": [
                    "age",
                    "sex"
                  ]
                },
                "op": {
                  "type": "string",
                  "enum": [
                    "<",
                    "<=",
                    ">",
                    ">=",
                    "==",
                    "!="
                  ]
                },
                "value": {
                  "type": [
                    "number",
                    "string"
                  ]
                },
                "unit": {
                  "type": [
                    "string",
                    "null"
                  ]
                }
              },
              "required": [
                "type",
                "field",
                "op",
                "value",
                "unit"
              ],
              "additionalProperties": false
            },
            {
              "type": "object",
              "description": "A criterion that cannot be honestly formalised. It stays unresolved forever, by design.\n\n`settlement` says *why* no chart can answer it, and the difference is load-bearing.\n\nA criterion settled `from_data` was a question about the patient's record that we failed to\nformalise \u2014 a threshold with no number, an open category. It is a gap, and it blocks a verdict.\n\nA criterion settled `at_visit` is not a gap at all. Signed informed consent, a procedure planned\nafter randomisation, the investigator's own judgement of the patient in person: these have the\nsame answer for every chart ever written, because they are settled when the patient comes in.\nTreating them as unresolved data made ELIGIBLE unreachable for every real protocol we hold \u2014 one\nconsent criterion and the screening abstains, which is not caution but paralysis.\n\nThe default is `from_data`, so a compiler that says nothing cannot thereby unblock a verdict.",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "unsupported"
                  ]
                },
                "reason": {
                  "type": "string"
                },
                "settlement": {
                  "type": "string",
                  "enum": [
                    "from_data",
                    "at_visit"
                  ]
                }
              },
              "required": [
                "type",
                "reason",
                "settlement"
              ],
              "additionalProperties": false
            },
            {
              "type": "object",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "all_of",
                    "any_of",
                    "not"
                  ]
                },
                "operands": {
                  "type": "array",
                  "items": {
                    "anyOf": [
                      {
                        "type": "object",
                        "description": "A numeric comparison against a measurement: labs, vitals, scores.",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "observation"
                            ]
                          },
                          "concept": {
                            "type": "object",
                            "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                            "properties": {
                              "text": {
                                "type": "string"
                              },
                              "codes": {
                                "type": "array",
                                "items": {
                                  "type": "object",
                                  "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                                  "properties": {
                                    "system": {
                                      "type": "string",
                                      "enum": [
                                        "LOINC",
                                        "SNOMED",
                                        "RxNorm",
                                        "ICD10",
                                        "UCUM"
                                      ]
                                    },
                                    "code": {
                                      "type": "string"
                                    },
                                    "display": {
                                      "type": [
                                        "string",
                                        "null"
                                      ]
                                    }
                                  },
                                  "required": [
                                    "system",
                                    "code",
                                    "display"
                                  ],
                                  "additionalProperties": false
                                }
                              }
                            },
                            "required": [
                              "text",
                              "codes"
                            ],
                            "additionalProperties": false
                          },
                          "op": {
                            "type": "string",
                            "enum": [
                              "<",
                              "<=",
                              ">",
                              ">=",
                              "==",
                              "!=",
                              "between"
                            ]
                          },
                          "value": {
                            "type": "number"
                          },
                          "value_high": {
                            "type": [
                              "number",
                              "null"
                            ]
                          },
                          "unit": {
                            "type": "string"
                          },
                          "window": {
                            "anyOf": [
                              {
                                "type": "object",
                                "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                                "properties": {
                                  "relation": {
                                    "type": "string",
                                    "enum": [
                                      "within",
                                      "before",
                                      "after",
                                      "ever",
                                      "current"
                                    ]
                                  },
                                  "amount": {
                                    "type": [
                                      "integer",
                                      "null"
                                    ]
                                  },
                                  "unit": {
                                    "anyOf": [
                                      {
                                        "type": "string",
                                        "enum": [
                                          "days",
                                          "weeks",
                                          "months",
                                          "years"
                                        ]
                                      },
                                      {
                                        "type": "null"
                                      }
                                    ]
                                  },
                                  "anchor": {
                                    "type": "string",
                                    "enum": [
                                      "screening",
                                      "enrolment",
                                      "randomisation",
                                      "consent",
                                      "first_dose"
                                    ]
                                  }
                                },
                                "required": [
                                  "relation",
                                  "amount",
                                  "unit",
                                  "anchor"
                                ],
                                "additionalProperties": false
                              },
                              {
                                "type": "null"
                              }
                            ]
                          }
                        },
                        "required": [
                          "type",
                          "concept",
                          "op",
                          "value",
                          "value_high",
                          "unit",
                          "window"
                        ],
                        "additionalProperties": false
                      },
                      {
                        "type": "object",
                        "description": "Whether a coded thing is on the chart at all: a condition, a drug, a procedure.",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "condition",
                              "medication",
                              "procedure"
                            ]
                          },
                          "concept": {
                            "type": "object",
                            "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                            "properties": {
                              "text": {
                                "type": "string"
                              },
                              "codes": {
                                "type": "array",
                                "items": {
                                  "type": "object",
                                  "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                                  "properties": {
                                    "system": {
                                      "type": "string",
                                      "enum": [
                                        "LOINC",
                                        "SNOMED",
                                        "RxNorm",
                                        "ICD10",
                                        "UCUM"
                                      ]
                                    },
                                    "code": {
                                      "type": "string"
                                    },
                                    "display": {
                                      "type": [
                                        "string",
                                        "null"
                                      ]
                                    }
                                  },
                                  "required": [
                                    "system",
                                    "code",
                                    "display"
                                  ],
                                  "additionalProperties": false
                                }
                              }
                            },
                            "required": [
                              "text",
                              "codes"
                            ],
                            "additionalProperties": false
                          },
                          "presence": {
                            "type": "string",
                            "enum": [
                              "present",
                              "absent"
                            ]
                          },
                          "window": {
                            "anyOf": [
                              {
                                "type": "object",
                                "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                                "properties": {
                                  "relation": {
                                    "type": "string",
                                    "enum": [
                                      "within",
                                      "before",
                                      "after",
                                      "ever",
                                      "current"
                                    ]
                                  },
                                  "amount": {
                                    "type": [
                                      "integer",
                                      "null"
                                    ]
                                  },
                                  "unit": {
                                    "anyOf": [
                                      {
                                        "type": "string",
                                        "enum": [
                                          "days",
                                          "weeks",
                                          "months",
                                          "years"
                                        ]
                                      },
                                      {
                                        "type": "null"
                                      }
                                    ]
                                  },
                                  "anchor": {
                                    "type": "string",
                                    "enum": [
                                      "screening",
                                      "enrolment",
                                      "randomisation",
                                      "consent",
                                      "first_dose"
                                    ]
                                  }
                                },
                                "required": [
                                  "relation",
                                  "amount",
                                  "unit",
                                  "anchor"
                                ],
                                "additionalProperties": false
                              },
                              {
                                "type": "null"
                              }
                            ]
                          }
                        },
                        "required": [
                          "type",
                          "concept",
                          "presence",
                          "window"
                        ],
                        "additionalProperties": false
                      },
                      {
                        "type": "object",
                        "description": "Age and sex, which come from the patient resource rather than from clinical events.",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "demographic"
                            ]
                          },
                          "field": {
                            "type": "string",
                            "enum": [
                              "age",
                              "sex"
                            ]
                          },
                          "op": {
                            "type": "string",
                            "enum": [
                              "<",
                              "<=",
                              ">",
                              ">=",
                              "==",
                              "!="
                            ]
                          },
                          "value": {
                            "type": [
                              "number",
                              "string"
                            ]
                          },
                          "unit": {
                            "type": [
                              "string",
                              "null"
                            ]
                          }
                        },
                        "required": [
                          "type",
                          "field",
                          "op",
                          "value",
                          "unit"
                        ],
                        "additionalProperties": false
                      },
                      {
                        "type": "object",
                        "description": "A criterion that cannot be honestly formalised. It stays unresolved forever, by design.\n\n`settlement` says *why* no chart can answer it, and the difference is load-bearing.\n\nA criterion settled `from_data` was a question about the patient's record that we failed to\nformalise \u2014 a threshold with no number, an open category. It is a gap, and it blocks a verdict.\n\nA criterion settled `at_visit` is not a gap at all. Signed informed consent, a procedure planned\nafter randomisation, the investigator's own judgement of the patient in person: these have the\nsame answer for every chart ever written, because they are settled when the patient comes in.\nTreating them as unresolved data made ELIGIBLE unreachable for every real protocol we hold \u2014 one\nconsent criterion and the screening abstains, which is not caution but paralysis.\n\nThe default is `from_data`, so a compiler that says nothing cannot thereby unblock a verdict.",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "unsupported"
                            ]
                          },
                          "reason": {
                            "type": "string"
                          },
                          "settlement": {
                            "type": "string",
                            "enum": [
                              "from_data",
                              "at_visit"
                            ]
                          }
                        },
                        "required": [
                          "type",
                          "reason",
                          "settlement"
                        ],
                        "additionalProperties": false
                      },
                      {
                        "type": "object",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "all_of",
                              "any_of",
                              "not"
                            ]
                          },
                          "operands": {
                            "type": "array",
                            "items": {
                              "anyOf": [
                                {
                                  "type": "object",
                                  "description": "A numeric comparison against a measurement: labs, vitals, scores.",
                                  "properties": {
                                    "type": {
                                      "type": "string",
                                      "enum": [
                                        "observation"
                                      ]
                                    },
                                    "concept": {
                                      "type": "object",
                                      "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                                      "properties": {
                                        "text": {
                                          "type": "string"
                                        },
                                        "codes": {
                                          "type": "array",
                                          "items": {
                                            "type": "object",
                                            "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                                            "properties": {
                                              "system": {
                                                "type": "string",
                                                "enum": [
                                                  "LOINC",
                                                  "SNOMED",
                                                  "RxNorm",
                                                  "ICD10",
                                                  "UCUM"
                                                ]
                                              },
                                              "code": {
                                                "type": "string"
                                              },
                                              "display": {
                                                "type": [
                                                  "string",
                                                  "null"
                                                ]
                                              }
                                            },
                                            "required": [
                                              "system",
                                              "code",
                                              "display"
                                            ],
                                            "additionalProperties": false
                                          }
                                        }
                                      },
                                      "required": [
                                        "text",
                                        "codes"
                                      ],
                                      "additionalProperties": false
                                    },
                                    "op": {
                                      "type": "string",
                                      "enum": [
                                        "<",
                                        "<=",
                                        ">",
                                        ">=",
                                        "==",
                                        "!=",
                                        "between"
                                      ]
                                    },
                                    "value": {
                                      "type": "number"
                                    },
                                    "value_high": {
                                      "type": [
                                        "number",
                                        "null"
                                      ]
                                    },
                                    "unit": {
                                      "type": "string"
                                    },
                                    "window": {
                                      "anyOf": [
                                        {
                                          "type": "object",
                                          "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                                          "properties": {
                                            "relation": {
                                              "type": "string",
                                              "enum": [
                                                "within",
                                                "before",
                                                "after",
                                                "ever",
                                                "current"
                                              ]
                                            },
                                            "amount": {
                                              "type": [
                                                "integer",
                                                "null"
                                              ]
                                            },
                                            "unit": {
                                              "anyOf": [
                                                {
                                                  "type": "string",
                                                  "enum": [
                                                    "days",
                                                    "weeks",
                                                    "months",
                                                    "years"
                                                  ]
                                                },
                                                {
                                                  "type": "null"
                                                }
                                              ]
                                            },
                                            "anchor": {
                                              "type": "string",
                                              "enum": [
                                                "screening",
                                                "enrolment",
                                                "randomisation",
                                                "consent",
                                                "first_dose"
                                              ]
                                            }
                                          },
                                          "required": [
                                            "relation",
                                            "amount",
                                            "unit",
                                            "anchor"
                                          ],
                                          "additionalProperties": false
                                        },
                                        {
                                          "type": "null"
                                        }
                                      ]
                                    }
                                  },
                                  "required": [
                                    "type",
                                    "concept",
                                    "op",
                                    "value",
                                    "value_high",
                                    "unit",
                                    "window"
                                  ],
                                  "additionalProperties": false
                                },
                                {
                                  "type": "object",
                                  "description": "Whether a coded thing is on the chart at all: a condition, a drug, a procedure.",
                                  "properties": {
                                    "type": {
                                      "type": "string",
                                      "enum": [
                                        "condition",
                                        "medication",
                                        "procedure"
                                      ]
                                    },
                                    "concept": {
                                      "type": "object",
                                      "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                                      "properties": {
                                        "text": {
                                          "type": "string"
                                        },
                                        "codes": {
                                          "type": "array",
                                          "items": {
                                            "type": "object",
                                            "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                                            "properties": {
                                              "system": {
                                                "type": "string",
                                                "enum": [
                                                  "LOINC",
                                                  "SNOMED",
                                                  "RxNorm",
                                                  "ICD10",
                                                  "UCUM"
                                                ]
                                              },
                                              "code": {
                                                "type": "string"
                                              },
                                              "display": {
                                                "type": [
                                                  "string",
                                                  "null"
                                                ]
                                              }
                                            },
                                            "required": [
                                              "system",
                                              "code",
                                              "display"
                                            ],
                                            "additionalProperties": false
                                          }
                                        }
                                      },
                                      "required": [
                                        "text",
                                        "codes"
                                      ],
                                      "additionalProperties": false
                                    },
                                    "presence": {
                                      "type": "string",
                                      "enum": [
                                        "present",
                                        "absent"
                                      ]
                                    },
                                    "window": {
                                      "anyOf": [
                                        {
                                          "type": "object",
                                          "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                                          "properties": {
                                            "relation": {
                                              "type": "string",
                                              "enum": [
                                                "within",
                                                "before",
                                                "after",
                                                "ever",
                                                "current"
                                              ]
                                            },
                                            "amount": {
                                              "type": [
                                                "integer",
                                                "null"
                                              ]
                                            },
                                            "unit": {
                                              "anyOf": [
                                                {
                                                  "type": "string",
                                                  "enum": [
                                                    "days",
                                                    "weeks",
                                                    "months",
                                                    "years"
                                                  ]
                                                },
                                                {
                                                  "type": "null"
                                                }
                                              ]
                                            },
                                            "anchor": {
                                              "type": "string",
                                              "enum": [
                                                "screening",
                                                "enrolment",
                                                "randomisation",
                                                "consent",
                                                "first_dose"
                                              ]
                                            }
                                          },
                                          "required": [
                                            "relation",
                                            "amount",
                                            "unit",
                                            "anchor"
                                          ],
                                          "additionalProperties": false
                                        },
                                        {
                                          "type": "null"
                                        }
                                      ]
                                    }
                                  },
                                  "required": [
                                    "type",
                                    "concept",
                                    "presence",
                                    "window"
                                  ],
                                  "additionalProperties": false
                                },
                                {
                                  "type": "object",
                                  "description": "Age and sex, which come from the patient resource rather than from clinical events.",
                                  "properties": {
                                    "type": {
                                      "type": "string",
                                      "enum": [
                                        "demographic"
                                      ]
                                    },
                                    "field": {
                                      "type": "string",
                                      "enum": [
                                        "age",
                                        "sex"
                                      ]
                                    },
                                    "op": {
                                      "type": "string",
                                      "enum": [
                                        "<",
                                        "<=",
                                        ">",
                                        ">=",
                                        "==",
                                        "!="
                                      ]
                                    },
                                    "value": {
                                      "type": [
                                        "number",
                                        "string"
                                      ]
                                    },
                                    "unit": {
                                      "type": [
                                        "string",
                                        "null"
                                      ]
                                    }
                                  },
                                  "required": [
                                    "type",
                                    "field",
                                    "op",
                                    "value",
                                    "unit"
                                  ],
                                  "additionalProperties": false
                                },
                                {
                                  "type": "object",
                                  "description": "A criterion that cannot be honestly formalised. It stays unresolved forever, by design.\n\n`settlement` says *why* no chart can answer it, and the difference is load-bearing.\n\nA criterion settled `from_data` was a question about the patient's record that we failed to\nformalise \u2014 a threshold with no number, an open category. It is a gap, and it blocks a verdict.\n\nA criterion settled `at_visit` is not a gap at all. Signed informed consent, a procedure planned\nafter randomisation, the investigator's own judgement of the patient in person: these have the\nsame answer for every chart ever written, because they are settled when the patient comes in.\nTreating them as unresolved data made ELIGIBLE unreachable for every real protocol we hold \u2014 one\nconsent criterion and the screening abstains, which is not caution but paralysis.\n\nThe default is `from_data`, so a compiler that says nothing cannot thereby unblock a verdict.",
                                  "properties": {
                                    "type": {
                                      "type": "string",
                                      "enum": [
                                        "unsupported"
                                      ]
                                    },
                                    "reason": {
                                      "type": "string"
                                    },
                                    "settlement": {
                                      "type": "string",
                                      "enum": [
                                        "from_data",
                                        "at_visit"
                                      ]
                                    }
                                  },
                                  "required": [
                                    "type",
                                    "reason",
                                    "settlement"
                                  ],
                                  "additionalProperties": false
                                }
                              ]
                            }
                          }
                        },
                        "required": [
                          "type",
                          "operands"
                        ],
                        "additionalProperties": false
                      }
                    ]
                  }
                }
              },
              "required": [
                "type",
                "operands"
              ],
              "additionalProperties": false
            }
          ]
        },
        {
          "type": "null"
        }
      ]
    },
    "notes": {
      "type": [
        "string",
        "null"
      ],
      "description": "Why this span was hard, or why it is not a criterion."
    }
  },
  "required": [
    "is_criterion",
    "kind",
    "source_quote",
    "predicate",
    "notes"
  ],
  "additionalProperties": false
}

[user]
Section: exclusion

Criterion:
Antihyperglycemic treatment has not been stable within 12 weeks prior to screening.
```

Response:

```
{
  "is_criterion": true,
  "kind": "exclusion",
  "source_quote": "Antihyperglycemic treatment has not been stable within 12 weeks prior to screening.",
  "predicate": {
    "type": "unsupported",
    "reason": "\"Stable\" antihyperglycemic treatment is not a single coded fact; it requires comparing dose/regimen changes across a window, which has no representation in this vocabulary (no concept for treatment stability, and no way to enumerate what counts as a change).",
    "settlement": "from_data"
  },
  "notes": "Depends on medication history detail (dose/regimen changes over time) that a perfect record could in principle answer, but the schema has no predicate for 'stability' of a treatment regimen."
}
```

Validated against the schema.

### Result

```json
{
  "is_criterion": true,
  "kind": "exclusion",
  "source_quote": "Antihyperglycemic treatment has not been stable within 12 weeks prior to screening.",
  "predicate": {
    "type": "unsupported",
    "reason": "\"Stable\" antihyperglycemic treatment is not a single coded fact; it requires comparing dose/regimen changes across a window, which has no representation in this vocabulary (no concept for treatment stability, and no way to enumerate what counts as a change).",
    "settlement": "from_data"
  },
  "notes": "Depends on medication history detail (dose/regimen changes over time) that a perfect record could in principle answer, but the schema has no predicate for 'stability' of a treatment regimen."
}
```

## 6. compiler on venice/claude-sonnet-5

- **Started:** 2026-08-30T10:35:10Z
- **Tier used:** `json_object`
- **Retries:** 1
- **Tokens:** 13444 in / 200 out
- **Estimated cost:** $0.0289
- **Outcome:** validated

### Instructions

```
# Criteria compiler

You formalise one span of a clinical trial's eligibility criteria into a machine-checkable
predicate. A downstream engine will evaluate that predicate against a patient's structured record
and produce a screening verdict. You never see a patient and you never decide eligibility.

You are given one span at a time, together with the section it appeared under and, where the
protocol nested sub-conditions beneath it, its children. Treat the whole unit as one criterion.

## The only judgement that matters

A criterion you formalise incorrectly is worse than a criterion you decline to formalise. The
engine has an explicit `unsupported` predicate; a criterion marked unsupported goes to a research
coordinator, who reads it and decides. That is a normal, safe, expected outcome. A predicate that
looks right and means something slightly different produces a confident wrong verdict that nobody
catches.

So: when the span does not map cleanly onto the vocabulary below, return `unsupported` with a
reason. Do not approximate. Do not drop a qualifier to make something fit. Do not invent a
threshold the protocol did not state.

Use `unsupported` when the span:

- depends on clinical judgement — "in the opinion of the investigator", "otherwise unsuitable",
  "clinically significant", "adequate organ function" without stated numbers;
- depends on something no chart records — willingness to comply, ability to attend visits,
  informed consent, contraception intentions, geographic availability;
- names a threshold relative to something the engine cannot resolve, such as "above the upper
  limit of normal" (the reference range is laboratory-specific and is not in the record);
- describes a process rather than a state — "must complete a washout", "will be randomised";
- is a class of drug or a category of disease broad enough that no single code captures it, and
  the protocol does not enumerate members;
- nests more deeply than the schema allows.

### Which kind of unsupported

Every `unsupported` criterion also carries a `settlement`, and the choice matters more than it
looks. It decides whether one criterion holds up the whole screening.

**`at_visit`** — the criterion is settled when the patient comes in, and would be settled the same
way for every patient in the world. No chart that has ever been written could answer it, so its
being unanswered here says nothing about *this* patient. A coordinator confirms it at the screening
visit, and the packet lists it for them.

> Signed written informed consent.
> Willing and able to comply with the study schedule.
> Planned coronary procedure or surgery after randomization.
> Planning to start an SGLT2 inhibitor during the study.
> In the investigator's opinion, unsuitable for the study.
> Women of childbearing potential must agree to use contraception during the trial.

**`from_data`** — the criterion asks about the patient's recorded history or state, and we simply
could not formalise the question. That is a gap in what we know about this patient, and it does hold
up the screening.

> Adequate organ function. *(about the record; no threshold stated)*
> Any clinically significant abnormality on screening laboratory tests. *(about the record)*
> Lower extremity complications such as skin ulcer, infection, osteomyelitis and gangrene.
> *(about the record; an open list this schema cannot enumerate)*
> Alanine aminotransferase above the upper limit of normal. *(about the record; the range is
> laboratory-specific and not in it)*

The test to apply, in one sentence: **would a complete and perfect medical record answer this?** If
yes, and we merely failed to express it, that is `from_data`. If even a perfect record could not,
because the answer does not exist until the patient is in the room, that is `at_visit`.

When you are unsure, choose `from_data`. It is the cautious answer: it sends the criterion to a
human either way, and it does not let a verdict through on a criterion that should have stopped it.

## Vocabulary

**`observation`** — a numeric comparison against a measurement: laboratory values, vital signs,
scores. Give the analyte as the protocol names it, the operator, the number, and the unit exactly
as written. `between` is for a two-sided range and takes both bounds. Never convert units; the
engine converts, and it knows which conversions are safe.

**`condition`, `medication`, `procedure`** — whether something is on the chart. `presence`
is `present` when the protocol requires it and `absent` when the protocol requires its absence.

Note carefully: an exclusion criterion that reads "history of myocardial infarction" is a
**`present`** predicate under an **exclusion** criterion. Do not negate it yourself — the engine
knows that a met exclusion rules the patient out. Only use `absent` when the protocol itself
states an absence as a requirement, such as an inclusion criterion reading "no history of
malignancy".

**`demographic`** — age and sex only.

**`all_of` / `any_of` / `not`** — for spans that carry several conditions. "eGFR ≥25 and ≤60" is a
single `observation` with `between`, not a composite. "On an ACE inhibitor or an ARB" is `any_of`.
Sub-bullets beneath a parent bullet are almost always conjunctive: `all_of`.

## Temporal windows

Attach a window whenever the protocol bounds the evidence in time: "within 6 months prior to
screening", "in the last 30 days", "no myocardial infarction within 12 weeks". Use the number and
unit the protocol gives.

Protocols anchor windows to different events — screening, enrolment, randomisation, consent — and
those are genuinely different dates. The engine anchors everything to the screening date. If the
span anchors to something else and the difference could plausibly matter, say so in `notes`; if
the anchor is doing real work in the criterion, return `unsupported`.

## Quoting

`source_quote` must be the span reproduced character for character, including its punctuation and
its unicode operators. It is checked against the protocol text automatically, and a criterion whose
quote does not match is discarded. Do not tidy, expand abbreviations, or normalise `≥` to `>=`.

## Spans that are not criteria

Registry text contains section headings, cross-references and standard boilerplate. If the span is
one of those, set `is_criterion` to false and say why in `notes`. This is a correct answer, not a
failure.

## Concepts

Give the concept's `text` as the protocol names it. Leave `codes` empty — terminology resolution is
a separate step with its own controls. A code you guess here will be trusted downstream.

```

### Request

```
Section: exclusion

Criterion:
Planned coronary procedure or surgery after randomization.
```

### Attempt 1, tier `json_schema`

The provider rejected the request:

```
TapeMiss: no recorded answer for this request.
  model:  claude-sonnet-5
  system: "# Criteria compiler\n\nYou formalise one span of a clinical trial's eligibility cr"
  user:   'Section: exclusion\n\nCriterion:\nPlanned coronary procedure or surgery after randomization.'
The code has changed since the tape was recorded. Re-record with a key, or check out the commit the tape belongs to.
```

### Attempt 2, tier `json_object`

Restarted with:

```
[system]
# Criteria compiler

You formalise one span of a clinical trial's eligibility criteria into a machine-checkable
predicate. A downstream engine will evaluate that predicate against a patient's structured record
and produce a screening verdict. You never see a patient and you never decide eligibility.

You are given one span at a time, together with the section it appeared under and, where the
protocol nested sub-conditions beneath it, its children. Treat the whole unit as one criterion.

## The only judgement that matters

A criterion you formalise incorrectly is worse than a criterion you decline to formalise. The
engine has an explicit `unsupported` predicate; a criterion marked unsupported goes to a research
coordinator, who reads it and decides. That is a normal, safe, expected outcome. A predicate that
looks right and means something slightly different produces a confident wrong verdict that nobody
catches.

So: when the span does not map cleanly onto the vocabulary below, return `unsupported` with a
reason. Do not approximate. Do not drop a qualifier to make something fit. Do not invent a
threshold the protocol did not state.

Use `unsupported` when the span:

- depends on clinical judgement — "in the opinion of the investigator", "otherwise unsuitable",
  "clinically significant", "adequate organ function" without stated numbers;
- depends on something no chart records — willingness to comply, ability to attend visits,
  informed consent, contraception intentions, geographic availability;
- names a threshold relative to something the engine cannot resolve, such as "above the upper
  limit of normal" (the reference range is laboratory-specific and is not in the record);
- describes a process rather than a state — "must complete a washout", "will be randomised";
- is a class of drug or a category of disease broad enough that no single code captures it, and
  the protocol does not enumerate members;
- nests more deeply than the schema allows.

### Which kind of unsupported

Every `unsupported` criterion also carries a `settlement`, and the choice matters more than it
looks. It decides whether one criterion holds up the whole screening.

**`at_visit`** — the criterion is settled when the patient comes in, and would be settled the same
way for every patient in the world. No chart that has ever been written could answer it, so its
being unanswered here says nothing about *this* patient. A coordinator confirms it at the screening
visit, and the packet lists it for them.

> Signed written informed consent.
> Willing and able to comply with the study schedule.
> Planned coronary procedure or surgery after randomization.
> Planning to start an SGLT2 inhibitor during the study.
> In the investigator's opinion, unsuitable for the study.
> Women of childbearing potential must agree to use contraception during the trial.

**`from_data`** — the criterion asks about the patient's recorded history or state, and we simply
could not formalise the question. That is a gap in what we know about this patient, and it does hold
up the screening.

> Adequate organ function. *(about the record; no threshold stated)*
> Any clinically significant abnormality on screening laboratory tests. *(about the record)*
> Lower extremity complications such as skin ulcer, infection, osteomyelitis and gangrene.
> *(about the record; an open list this schema cannot enumerate)*
> Alanine aminotransferase above the upper limit of normal. *(about the record; the range is
> laboratory-specific and not in it)*

The test to apply, in one sentence: **would a complete and perfect medical record answer this?** If
yes, and we merely failed to express it, that is `from_data`. If even a perfect record could not,
because the answer does not exist until the patient is in the room, that is `at_visit`.

When you are unsure, choose `from_data`. It is the cautious answer: it sends the criterion to a
human either way, and it does not let a verdict through on a criterion that should have stopped it.

## Vocabulary

**`observation`** — a numeric comparison against a measurement: laboratory values, vital signs,
scores. Give the analyte as the protocol names it, the operator, the number, and the unit exactly
as written. `between` is for a two-sided range and takes both bounds. Never convert units; the
engine converts, and it knows which conversions are safe.

**`condition`, `medication`, `procedure`** — whether something is on the chart. `presence`
is `present` when the protocol requires it and `absent` when the protocol requires its absence.

Note carefully: an exclusion criterion that reads "history of myocardial infarction" is a
**`present`** predicate under an **exclusion** criterion. Do not negate it yourself — the engine
knows that a met exclusion rules the patient out. Only use `absent` when the protocol itself
states an absence as a requirement, such as an inclusion criterion reading "no history of
malignancy".

**`demographic`** — age and sex only.

**`all_of` / `any_of` / `not`** — for spans that carry several conditions. "eGFR ≥25 and ≤60" is a
single `observation` with `between`, not a composite. "On an ACE inhibitor or an ARB" is `any_of`.
Sub-bullets beneath a parent bullet are almost always conjunctive: `all_of`.

## Temporal windows

Attach a window whenever the protocol bounds the evidence in time: "within 6 months prior to
screening", "in the last 30 days", "no myocardial infarction within 12 weeks". Use the number and
unit the protocol gives.

Protocols anchor windows to different events — screening, enrolment, randomisation, consent — and
those are genuinely different dates. The engine anchors everything to the screening date. If the
span anchors to something else and the difference could plausibly matter, say so in `notes`; if
the anchor is doing real work in the criterion, return `unsupported`.

## Quoting

`source_quote` must be the span reproduced character for character, including its punctuation and
its unicode operators. It is checked against the protocol text automatically, and a criterion whose
quote does not match is discarded. Do not tidy, expand abbreviations, or normalise `≥` to `>=`.

## Spans that are not criteria

Registry text contains section headings, cross-references and standard boilerplate. If the span is
one of those, set `is_criterion` to false and say why in `notes`. This is a correct answer, not a
failure.

## Concepts

Give the concept's `text` as the protocol names it. Leave `codes` empty — terminology resolution is
a separate step with its own controls. A code you guess here will be trusted downstream.


Reply with a single JSON object and nothing else. It must conform to this JSON schema:

{
  "type": "object",
  "description": "The result of formalising one span of eligibility text. Set is_criterion to false when the span is a heading, a note to readers, or registry boilerplate rather than a condition a patient can meet.",
  "properties": {
    "is_criterion": {
      "type": "boolean"
    },
    "kind": {
      "description": "Only needed when the span sits under no inclusion or exclusion header.",
      "anyOf": [
        {
          "type": "string",
          "enum": [
            "inclusion",
            "exclusion"
          ]
        },
        {
          "type": "null"
        }
      ]
    },
    "source_quote": {
      "type": [
        "string",
        "null"
      ],
      "description": "The span copied verbatim, character for character."
    },
    "predicate": {
      "anyOf": [
        {
          "anyOf": [
            {
              "type": "object",
              "description": "A numeric comparison against a measurement: labs, vitals, scores.",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "observation"
                  ]
                },
                "concept": {
                  "type": "object",
                  "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                  "properties": {
                    "text": {
                      "type": "string"
                    },
                    "codes": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                        "properties": {
                          "system": {
                            "type": "string",
                            "enum": [
                              "LOINC",
                              "SNOMED",
                              "RxNorm",
                              "ICD10",
                              "UCUM"
                            ]
                          },
                          "code": {
                            "type": "string"
                          },
                          "display": {
                            "type": [
                              "string",
                              "null"
                            ]
                          }
                        },
                        "required": [
                          "system",
                          "code",
                          "display"
                        ],
                        "additionalProperties": false
                      }
                    }
                  },
                  "required": [
                    "text",
                    "codes"
                  ],
                  "additionalProperties": false
                },
                "op": {
                  "type": "string",
                  "enum": [
                    "<",
                    "<=",
                    ">",
                    ">=",
                    "==",
                    "!=",
                    "between"
                  ]
                },
                "value": {
                  "type": "number"
                },
                "value_high": {
                  "type": [
                    "number",
                    "null"
                  ]
                },
                "unit": {
                  "type": "string"
                },
                "window": {
                  "anyOf": [
                    {
                      "type": "object",
                      "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                      "properties": {
                        "relation": {
                          "type": "string",
                          "enum": [
                            "within",
                            "before",
                            "after",
                            "ever",
                            "current"
                          ]
                        },
                        "amount": {
                          "type": [
                            "integer",
                            "null"
                          ]
                        },
                        "unit": {
                          "anyOf": [
                            {
                              "type": "string",
                              "enum": [
                                "days",
                                "weeks",
                                "months",
                                "years"
                              ]
                            },
                            {
                              "type": "null"
                            }
                          ]
                        },
                        "anchor": {
                          "type": "string",
                          "enum": [
                            "screening",
                            "enrolment",
                            "randomisation",
                            "consent",
                            "first_dose"
                          ]
                        }
                      },
                      "required": [
                        "relation",
                        "amount",
                        "unit",
                        "anchor"
                      ],
                      "additionalProperties": false
                    },
                    {
                      "type": "null"
                    }
                  ]
                }
              },
              "required": [
                "type",
                "concept",
                "op",
                "value",
                "value_high",
                "unit",
                "window"
              ],
              "additionalProperties": false
            },
            {
              "type": "object",
              "description": "Whether a coded thing is on the chart at all: a condition, a drug, a procedure.",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "condition",
                    "medication",
                    "procedure"
                  ]
                },
                "concept": {
                  "type": "object",
                  "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                  "properties": {
                    "text": {
                      "type": "string"
                    },
                    "codes": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                        "properties": {
                          "system": {
                            "type": "string",
                            "enum": [
                              "LOINC",
                              "SNOMED",
                              "RxNorm",
                              "ICD10",
                              "UCUM"
                            ]
                          },
                          "code": {
                            "type": "string"
                          },
                          "display": {
                            "type": [
                              "string",
                              "null"
                            ]
                          }
                        },
                        "required": [
                          "system",
                          "code",
                          "display"
                        ],
                        "additionalProperties": false
                      }
                    }
                  },
                  "required": [
                    "text",
                    "codes"
                  ],
                  "additionalProperties": false
                },
                "presence": {
                  "type": "string",
                  "enum": [
                    "present",
                    "absent"
                  ]
                },
                "window": {
                  "anyOf": [
                    {
                      "type": "object",
                      "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                      "properties": {
                        "relation": {
                          "type": "string",
                          "enum": [
                            "within",
                            "before",
                            "after",
                            "ever",
                            "current"
                          ]
                        },
                        "amount": {
                          "type": [
                            "integer",
                            "null"
                          ]
                        },
                        "unit": {
                          "anyOf": [
                            {
                              "type": "string",
                              "enum": [
                                "days",
                                "weeks",
                                "months",
                                "years"
                              ]
                            },
                            {
                              "type": "null"
                            }
                          ]
                        },
                        "anchor": {
                          "type": "string",
                          "enum": [
                            "screening",
                            "enrolment",
                            "randomisation",
                            "consent",
                            "first_dose"
                          ]
                        }
                      },
                      "required": [
                        "relation",
                        "amount",
                        "unit",
                        "anchor"
                      ],
                      "additionalProperties": false
                    },
                    {
                      "type": "null"
                    }
                  ]
                }
              },
              "required": [
                "type",
                "concept",
                "presence",
                "window"
              ],
              "additionalProperties": false
            },
            {
              "type": "object",
              "description": "Age and sex, which come from the patient resource rather than from clinical events.",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "demographic"
                  ]
                },
                "field": {
                  "type": "string",
                  "enum": [
                    "age",
                    "sex"
                  ]
                },
                "op": {
                  "type": "string",
                  "enum": [
                    "<",
                    "<=",
                    ">",
                    ">=",
                    "==",
                    "!="
                  ]
                },
                "value": {
                  "type": [
                    "number",
                    "string"
                  ]
                },
                "unit": {
                  "type": [
                    "string",
                    "null"
                  ]
                }
              },
              "required": [
                "type",
                "field",
                "op",
                "value",
                "unit"
              ],
              "additionalProperties": false
            },
            {
              "type": "object",
              "description": "A criterion that cannot be honestly formalised. It stays unresolved forever, by design.\n\n`settlement` says *why* no chart can answer it, and the difference is load-bearing.\n\nA criterion settled `from_data` was a question about the patient's record that we failed to\nformalise \u2014 a threshold with no number, an open category. It is a gap, and it blocks a verdict.\n\nA criterion settled `at_visit` is not a gap at all. Signed informed consent, a procedure planned\nafter randomisation, the investigator's own judgement of the patient in person: these have the\nsame answer for every chart ever written, because they are settled when the patient comes in.\nTreating them as unresolved data made ELIGIBLE unreachable for every real protocol we hold \u2014 one\nconsent criterion and the screening abstains, which is not caution but paralysis.\n\nThe default is `from_data`, so a compiler that says nothing cannot thereby unblock a verdict.",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "unsupported"
                  ]
                },
                "reason": {
                  "type": "string"
                },
                "settlement": {
                  "type": "string",
                  "enum": [
                    "from_data",
                    "at_visit"
                  ]
                }
              },
              "required": [
                "type",
                "reason",
                "settlement"
              ],
              "additionalProperties": false
            },
            {
              "type": "object",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "all_of",
                    "any_of",
                    "not"
                  ]
                },
                "operands": {
                  "type": "array",
                  "items": {
                    "anyOf": [
                      {
                        "type": "object",
                        "description": "A numeric comparison against a measurement: labs, vitals, scores.",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "observation"
                            ]
                          },
                          "concept": {
                            "type": "object",
                            "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                            "properties": {
                              "text": {
                                "type": "string"
                              },
                              "codes": {
                                "type": "array",
                                "items": {
                                  "type": "object",
                                  "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                                  "properties": {
                                    "system": {
                                      "type": "string",
                                      "enum": [
                                        "LOINC",
                                        "SNOMED",
                                        "RxNorm",
                                        "ICD10",
                                        "UCUM"
                                      ]
                                    },
                                    "code": {
                                      "type": "string"
                                    },
                                    "display": {
                                      "type": [
                                        "string",
                                        "null"
                                      ]
                                    }
                                  },
                                  "required": [
                                    "system",
                                    "code",
                                    "display"
                                  ],
                                  "additionalProperties": false
                                }
                              }
                            },
                            "required": [
                              "text",
                              "codes"
                            ],
                            "additionalProperties": false
                          },
                          "op": {
                            "type": "string",
                            "enum": [
                              "<",
                              "<=",
                              ">",
                              ">=",
                              "==",
                              "!=",
                              "between"
                            ]
                          },
                          "value": {
                            "type": "number"
                          },
                          "value_high": {
                            "type": [
                              "number",
                              "null"
                            ]
                          },
                          "unit": {
                            "type": "string"
                          },
                          "window": {
                            "anyOf": [
                              {
                                "type": "object",
                                "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                                "properties": {
                                  "relation": {
                                    "type": "string",
                                    "enum": [
                                      "within",
                                      "before",
                                      "after",
                                      "ever",
                                      "current"
                                    ]
                                  },
                                  "amount": {
                                    "type": [
                                      "integer",
                                      "null"
                                    ]
                                  },
                                  "unit": {
                                    "anyOf": [
                                      {
                                        "type": "string",
                                        "enum": [
                                          "days",
                                          "weeks",
                                          "months",
                                          "years"
                                        ]
                                      },
                                      {
                                        "type": "null"
                                      }
                                    ]
                                  },
                                  "anchor": {
                                    "type": "string",
                                    "enum": [
                                      "screening",
                                      "enrolment",
                                      "randomisation",
                                      "consent",
                                      "first_dose"
                                    ]
                                  }
                                },
                                "required": [
                                  "relation",
                                  "amount",
                                  "unit",
                                  "anchor"
                                ],
                                "additionalProperties": false
                              },
                              {
                                "type": "null"
                              }
                            ]
                          }
                        },
                        "required": [
                          "type",
                          "concept",
                          "op",
                          "value",
                          "value_high",
                          "unit",
                          "window"
                        ],
                        "additionalProperties": false
                      },
                      {
                        "type": "object",
                        "description": "Whether a coded thing is on the chart at all: a condition, a drug, a procedure.",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "condition",
                              "medication",
                              "procedure"
                            ]
                          },
                          "concept": {
                            "type": "object",
                            "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                            "properties": {
                              "text": {
                                "type": "string"
                              },
                              "codes": {
                                "type": "array",
                                "items": {
                                  "type": "object",
                                  "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                                  "properties": {
                                    "system": {
                                      "type": "string",
                                      "enum": [
                                        "LOINC",
                                        "SNOMED",
                                        "RxNorm",
                                        "ICD10",
                                        "UCUM"
                                      ]
                                    },
                                    "code": {
                                      "type": "string"
                                    },
                                    "display": {
                                      "type": [
                                        "string",
                                        "null"
                                      ]
                                    }
                                  },
                                  "required": [
                                    "system",
                                    "code",
                                    "display"
                                  ],
                                  "additionalProperties": false
                                }
                              }
                            },
                            "required": [
                              "text",
                              "codes"
                            ],
                            "additionalProperties": false
                          },
                          "presence": {
                            "type": "string",
                            "enum": [
                              "present",
                              "absent"
                            ]
                          },
                          "window": {
                            "anyOf": [
                              {
                                "type": "object",
                                "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                                "properties": {
                                  "relation": {
                                    "type": "string",
                                    "enum": [
                                      "within",
                                      "before",
                                      "after",
                                      "ever",
                                      "current"
                                    ]
                                  },
                                  "amount": {
                                    "type": [
                                      "integer",
                                      "null"
                                    ]
                                  },
                                  "unit": {
                                    "anyOf": [
                                      {
                                        "type": "string",
                                        "enum": [
                                          "days",
                                          "weeks",
                                          "months",
                                          "years"
                                        ]
                                      },
                                      {
                                        "type": "null"
                                      }
                                    ]
                                  },
                                  "anchor": {
                                    "type": "string",
                                    "enum": [
                                      "screening",
                                      "enrolment",
                                      "randomisation",
                                      "consent",
                                      "first_dose"
                                    ]
                                  }
                                },
                                "required": [
                                  "relation",
                                  "amount",
                                  "unit",
                                  "anchor"
                                ],
                                "additionalProperties": false
                              },
                              {
                                "type": "null"
                              }
                            ]
                          }
                        },
                        "required": [
                          "type",
                          "concept",
                          "presence",
                          "window"
                        ],
                        "additionalProperties": false
                      },
                      {
                        "type": "object",
                        "description": "Age and sex, which come from the patient resource rather than from clinical events.",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "demographic"
                            ]
                          },
                          "field": {
                            "type": "string",
                            "enum": [
                              "age",
                              "sex"
                            ]
                          },
                          "op": {
                            "type": "string",
                            "enum": [
                              "<",
                              "<=",
                              ">",
                              ">=",
                              "==",
                              "!="
                            ]
                          },
                          "value": {
                            "type": [
                              "number",
                              "string"
                            ]
                          },
                          "unit": {
                            "type": [
                              "string",
                              "null"
                            ]
                          }
                        },
                        "required": [
                          "type",
                          "field",
                          "op",
                          "value",
                          "unit"
                        ],
                        "additionalProperties": false
                      },
                      {
                        "type": "object",
                        "description": "A criterion that cannot be honestly formalised. It stays unresolved forever, by design.\n\n`settlement` says *why* no chart can answer it, and the difference is load-bearing.\n\nA criterion settled `from_data` was a question about the patient's record that we failed to\nformalise \u2014 a threshold with no number, an open category. It is a gap, and it blocks a verdict.\n\nA criterion settled `at_visit` is not a gap at all. Signed informed consent, a procedure planned\nafter randomisation, the investigator's own judgement of the patient in person: these have the\nsame answer for every chart ever written, because they are settled when the patient comes in.\nTreating them as unresolved data made ELIGIBLE unreachable for every real protocol we hold \u2014 one\nconsent criterion and the screening abstains, which is not caution but paralysis.\n\nThe default is `from_data`, so a compiler that says nothing cannot thereby unblock a verdict.",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "unsupported"
                            ]
                          },
                          "reason": {
                            "type": "string"
                          },
                          "settlement": {
                            "type": "string",
                            "enum": [
                              "from_data",
                              "at_visit"
                            ]
                          }
                        },
                        "required": [
                          "type",
                          "reason",
                          "settlement"
                        ],
                        "additionalProperties": false
                      },
                      {
                        "type": "object",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "all_of",
                              "any_of",
                              "not"
                            ]
                          },
                          "operands": {
                            "type": "array",
                            "items": {
                              "anyOf": [
                                {
                                  "type": "object",
                                  "description": "A numeric comparison against a measurement: labs, vitals, scores.",
                                  "properties": {
                                    "type": {
                                      "type": "string",
                                      "enum": [
                                        "observation"
                                      ]
                                    },
                                    "concept": {
                                      "type": "object",
                                      "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                                      "properties": {
                                        "text": {
                                          "type": "string"
                                        },
                                        "codes": {
                                          "type": "array",
                                          "items": {
                                            "type": "object",
                                            "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                                            "properties": {
                                              "system": {
                                                "type": "string",
                                                "enum": [
                                                  "LOINC",
                                                  "SNOMED",
                                                  "RxNorm",
                                                  "ICD10",
                                                  "UCUM"
                                                ]
                                              },
                                              "code": {
                                                "type": "string"
                                              },
                                              "display": {
                                                "type": [
                                                  "string",
                                                  "null"
                                                ]
                                              }
                                            },
                                            "required": [
                                              "system",
                                              "code",
                                              "display"
                                            ],
                                            "additionalProperties": false
                                          }
                                        }
                                      },
                                      "required": [
                                        "text",
                                        "codes"
                                      ],
                                      "additionalProperties": false
                                    },
                                    "op": {
                                      "type": "string",
                                      "enum": [
                                        "<",
                                        "<=",
                                        ">",
                                        ">=",
                                        "==",
                                        "!=",
                                        "between"
                                      ]
                                    },
                                    "value": {
                                      "type": "number"
                                    },
                                    "value_high": {
                                      "type": [
                                        "number",
                                        "null"
                                      ]
                                    },
                                    "unit": {
                                      "type": "string"
                                    },
                                    "window": {
                                      "anyOf": [
                                        {
                                          "type": "object",
                                          "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                                          "properties": {
                                            "relation": {
                                              "type": "string",
                                              "enum": [
                                                "within",
                                                "before",
                                                "after",
                                                "ever",
                                                "current"
                                              ]
                                            },
                                            "amount": {
                                              "type": [
                                                "integer",
                                                "null"
                                              ]
                                            },
                                            "unit": {
                                              "anyOf": [
                                                {
                                                  "type": "string",
                                                  "enum": [
                                                    "days",
                                                    "weeks",
                                                    "months",
                                                    "years"
                                                  ]
                                                },
                                                {
                                                  "type": "null"
                                                }
                                              ]
                                            },
                                            "anchor": {
                                              "type": "string",
                                              "enum": [
                                                "screening",
                                                "enrolment",
                                                "randomisation",
                                                "consent",
                                                "first_dose"
                                              ]
                                            }
                                          },
                                          "required": [
                                            "relation",
                                            "amount",
                                            "unit",
                                            "anchor"
                                          ],
                                          "additionalProperties": false
                                        },
                                        {
                                          "type": "null"
                                        }
                                      ]
                                    }
                                  },
                                  "required": [
                                    "type",
                                    "concept",
                                    "op",
                                    "value",
                                    "value_high",
                                    "unit",
                                    "window"
                                  ],
                                  "additionalProperties": false
                                },
                                {
                                  "type": "object",
                                  "description": "Whether a coded thing is on the chart at all: a condition, a drug, a procedure.",
                                  "properties": {
                                    "type": {
                                      "type": "string",
                                      "enum": [
                                        "condition",
                                        "medication",
                                        "procedure"
                                      ]
                                    },
                                    "concept": {
                                      "type": "object",
                                      "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                                      "properties": {
                                        "text": {
                                          "type": "string"
                                        },
                                        "codes": {
                                          "type": "array",
                                          "items": {
                                            "type": "object",
                                            "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                                            "properties": {
                                              "system": {
                                                "type": "string",
                                                "enum": [
                                                  "LOINC",
                                                  "SNOMED",
                                                  "RxNorm",
                                                  "ICD10",
                                                  "UCUM"
                                                ]
                                              },
                                              "code": {
                                                "type": "string"
                                              },
                                              "display": {
                                                "type": [
                                                  "string",
                                                  "null"
                                                ]
                                              }
                                            },
                                            "required": [
                                              "system",
                                              "code",
                                              "display"
                                            ],
                                            "additionalProperties": false
                                          }
                                        }
                                      },
                                      "required": [
                                        "text",
                                        "codes"
                                      ],
                                      "additionalProperties": false
                                    },
                                    "presence": {
                                      "type": "string",
                                      "enum": [
                                        "present",
                                        "absent"
                                      ]
                                    },
                                    "window": {
                                      "anyOf": [
                                        {
                                          "type": "object",
                                          "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                                          "properties": {
                                            "relation": {
                                              "type": "string",
                                              "enum": [
                                                "within",
                                                "before",
                                                "after",
                                                "ever",
                                                "current"
                                              ]
                                            },
                                            "amount": {
                                              "type": [
                                                "integer",
                                                "null"
                                              ]
                                            },
                                            "unit": {
                                              "anyOf": [
                                                {
                                                  "type": "string",
                                                  "enum": [
                                                    "days",
                                                    "weeks",
                                                    "months",
                                                    "years"
                                                  ]
                                                },
                                                {
                                                  "type": "null"
                                                }
                                              ]
                                            },
                                            "anchor": {
                                              "type": "string",
                                              "enum": [
                                                "screening",
                                                "enrolment",
                                                "randomisation",
                                                "consent",
                                                "first_dose"
                                              ]
                                            }
                                          },
                                          "required": [
                                            "relation",
                                            "amount",
                                            "unit",
                                            "anchor"
                                          ],
                                          "additionalProperties": false
                                        },
                                        {
                                          "type": "null"
                                        }
                                      ]
                                    }
                                  },
                                  "required": [
                                    "type",
                                    "concept",
                                    "presence",
                                    "window"
                                  ],
                                  "additionalProperties": false
                                },
                                {
                                  "type": "object",
                                  "description": "Age and sex, which come from the patient resource rather than from clinical events.",
                                  "properties": {
                                    "type": {
                                      "type": "string",
                                      "enum": [
                                        "demographic"
                                      ]
                                    },
                                    "field": {
                                      "type": "string",
                                      "enum": [
                                        "age",
                                        "sex"
                                      ]
                                    },
                                    "op": {
                                      "type": "string",
                                      "enum": [
                                        "<",
                                        "<=",
                                        ">",
                                        ">=",
                                        "==",
                                        "!="
                                      ]
                                    },
                                    "value": {
                                      "type": [
                                        "number",
                                        "string"
                                      ]
                                    },
                                    "unit": {
                                      "type": [
                                        "string",
                                        "null"
                                      ]
                                    }
                                  },
                                  "required": [
                                    "type",
                                    "field",
                                    "op",
                                    "value",
                                    "unit"
                                  ],
                                  "additionalProperties": false
                                },
                                {
                                  "type": "object",
                                  "description": "A criterion that cannot be honestly formalised. It stays unresolved forever, by design.\n\n`settlement` says *why* no chart can answer it, and the difference is load-bearing.\n\nA criterion settled `from_data` was a question about the patient's record that we failed to\nformalise \u2014 a threshold with no number, an open category. It is a gap, and it blocks a verdict.\n\nA criterion settled `at_visit` is not a gap at all. Signed informed consent, a procedure planned\nafter randomisation, the investigator's own judgement of the patient in person: these have the\nsame answer for every chart ever written, because they are settled when the patient comes in.\nTreating them as unresolved data made ELIGIBLE unreachable for every real protocol we hold \u2014 one\nconsent criterion and the screening abstains, which is not caution but paralysis.\n\nThe default is `from_data`, so a compiler that says nothing cannot thereby unblock a verdict.",
                                  "properties": {
                                    "type": {
                                      "type": "string",
                                      "enum": [
                                        "unsupported"
                                      ]
                                    },
                                    "reason": {
                                      "type": "string"
                                    },
                                    "settlement": {
                                      "type": "string",
                                      "enum": [
                                        "from_data",
                                        "at_visit"
                                      ]
                                    }
                                  },
                                  "required": [
                                    "type",
                                    "reason",
                                    "settlement"
                                  ],
                                  "additionalProperties": false
                                }
                              ]
                            }
                          }
                        },
                        "required": [
                          "type",
                          "operands"
                        ],
                        "additionalProperties": false
                      }
                    ]
                  }
                }
              },
              "required": [
                "type",
                "operands"
              ],
              "additionalProperties": false
            }
          ]
        },
        {
          "type": "null"
        }
      ]
    },
    "notes": {
      "type": [
        "string",
        "null"
      ],
      "description": "Why this span was hard, or why it is not a criterion."
    }
  },
  "required": [
    "is_criterion",
    "kind",
    "source_quote",
    "predicate",
    "notes"
  ],
  "additionalProperties": false
}

[user]
Section: exclusion

Criterion:
Planned coronary procedure or surgery after randomization.
```

Response:

```
{"is_criterion": true, "kind": "exclusion", "source_quote": "Planned coronary procedure or surgery after randomization.", "predicate": {"type": "unsupported", "reason": "Refers to a future planned event after randomization, not a recorded state; this is settled at the visit/planning stage rather than being derivable from the chart, and is the same determination for every patient regardless of history.", "settlement": "at_visit"}, "notes": "Describes a planned future procedure, which is a plan/intent rather than a chart-recorded state; no historical record could answer this, so it is settled at_visit."}
```

Validated against the schema.

### Result

```json
{
  "is_criterion": true,
  "kind": "exclusion",
  "source_quote": "Planned coronary procedure or surgery after randomization.",
  "predicate": {
    "type": "unsupported",
    "reason": "Refers to a future planned event after randomization, not a recorded state; this is settled at the visit/planning stage rather than being derivable from the chart, and is the same determination for every patient regardless of history.",
    "settlement": "at_visit"
  },
  "notes": "Describes a planned future procedure, which is a plan/intent rather than a chart-recorded state; no historical record could answer this, so it is settled at_visit."
}
```

## 7. compiler on venice/claude-sonnet-5

- **Started:** 2026-08-30T10:35:10Z
- **Tier used:** `json_object`
- **Retries:** 1
- **Tokens:** 13478 in / 421 out
- **Estimated cost:** $0.0312
- **Outcome:** validated

### Instructions

```
# Criteria compiler

You formalise one span of a clinical trial's eligibility criteria into a machine-checkable
predicate. A downstream engine will evaluate that predicate against a patient's structured record
and produce a screening verdict. You never see a patient and you never decide eligibility.

You are given one span at a time, together with the section it appeared under and, where the
protocol nested sub-conditions beneath it, its children. Treat the whole unit as one criterion.

## The only judgement that matters

A criterion you formalise incorrectly is worse than a criterion you decline to formalise. The
engine has an explicit `unsupported` predicate; a criterion marked unsupported goes to a research
coordinator, who reads it and decides. That is a normal, safe, expected outcome. A predicate that
looks right and means something slightly different produces a confident wrong verdict that nobody
catches.

So: when the span does not map cleanly onto the vocabulary below, return `unsupported` with a
reason. Do not approximate. Do not drop a qualifier to make something fit. Do not invent a
threshold the protocol did not state.

Use `unsupported` when the span:

- depends on clinical judgement — "in the opinion of the investigator", "otherwise unsuitable",
  "clinically significant", "adequate organ function" without stated numbers;
- depends on something no chart records — willingness to comply, ability to attend visits,
  informed consent, contraception intentions, geographic availability;
- names a threshold relative to something the engine cannot resolve, such as "above the upper
  limit of normal" (the reference range is laboratory-specific and is not in the record);
- describes a process rather than a state — "must complete a washout", "will be randomised";
- is a class of drug or a category of disease broad enough that no single code captures it, and
  the protocol does not enumerate members;
- nests more deeply than the schema allows.

### Which kind of unsupported

Every `unsupported` criterion also carries a `settlement`, and the choice matters more than it
looks. It decides whether one criterion holds up the whole screening.

**`at_visit`** — the criterion is settled when the patient comes in, and would be settled the same
way for every patient in the world. No chart that has ever been written could answer it, so its
being unanswered here says nothing about *this* patient. A coordinator confirms it at the screening
visit, and the packet lists it for them.

> Signed written informed consent.
> Willing and able to comply with the study schedule.
> Planned coronary procedure or surgery after randomization.
> Planning to start an SGLT2 inhibitor during the study.
> In the investigator's opinion, unsuitable for the study.
> Women of childbearing potential must agree to use contraception during the trial.

**`from_data`** — the criterion asks about the patient's recorded history or state, and we simply
could not formalise the question. That is a gap in what we know about this patient, and it does hold
up the screening.

> Adequate organ function. *(about the record; no threshold stated)*
> Any clinically significant abnormality on screening laboratory tests. *(about the record)*
> Lower extremity complications such as skin ulcer, infection, osteomyelitis and gangrene.
> *(about the record; an open list this schema cannot enumerate)*
> Alanine aminotransferase above the upper limit of normal. *(about the record; the range is
> laboratory-specific and not in it)*

The test to apply, in one sentence: **would a complete and perfect medical record answer this?** If
yes, and we merely failed to express it, that is `from_data`. If even a perfect record could not,
because the answer does not exist until the patient is in the room, that is `at_visit`.

When you are unsure, choose `from_data`. It is the cautious answer: it sends the criterion to a
human either way, and it does not let a verdict through on a criterion that should have stopped it.

## Vocabulary

**`observation`** — a numeric comparison against a measurement: laboratory values, vital signs,
scores. Give the analyte as the protocol names it, the operator, the number, and the unit exactly
as written. `between` is for a two-sided range and takes both bounds. Never convert units; the
engine converts, and it knows which conversions are safe.

**`condition`, `medication`, `procedure`** — whether something is on the chart. `presence`
is `present` when the protocol requires it and `absent` when the protocol requires its absence.

Note carefully: an exclusion criterion that reads "history of myocardial infarction" is a
**`present`** predicate under an **exclusion** criterion. Do not negate it yourself — the engine
knows that a met exclusion rules the patient out. Only use `absent` when the protocol itself
states an absence as a requirement, such as an inclusion criterion reading "no history of
malignancy".

**`demographic`** — age and sex only.

**`all_of` / `any_of` / `not`** — for spans that carry several conditions. "eGFR ≥25 and ≤60" is a
single `observation` with `between`, not a composite. "On an ACE inhibitor or an ARB" is `any_of`.
Sub-bullets beneath a parent bullet are almost always conjunctive: `all_of`.

## Temporal windows

Attach a window whenever the protocol bounds the evidence in time: "within 6 months prior to
screening", "in the last 30 days", "no myocardial infarction within 12 weeks". Use the number and
unit the protocol gives.

Protocols anchor windows to different events — screening, enrolment, randomisation, consent — and
those are genuinely different dates. The engine anchors everything to the screening date. If the
span anchors to something else and the difference could plausibly matter, say so in `notes`; if
the anchor is doing real work in the criterion, return `unsupported`.

## Quoting

`source_quote` must be the span reproduced character for character, including its punctuation and
its unicode operators. It is checked against the protocol text automatically, and a criterion whose
quote does not match is discarded. Do not tidy, expand abbreviations, or normalise `≥` to `>=`.

## Spans that are not criteria

Registry text contains section headings, cross-references and standard boilerplate. If the span is
one of those, set `is_criterion` to false and say why in `notes`. This is a correct answer, not a
failure.

## Concepts

Give the concept's `text` as the protocol names it. Leave `codes` empty — terminology resolution is
a separate step with its own controls. A code you guess here will be trusted downstream.

```

### Request

```
Section: exclusion

Criterion:
Lower extremity complications (such as skin ulcer, infection, osteomyelitis, and gangrene) identified during screening and requiring treatment at randomization.
```

### Attempt 1, tier `json_schema`

The provider rejected the request:

```
TapeMiss: no recorded answer for this request.
  model:  claude-sonnet-5
  system: "# Criteria compiler\n\nYou formalise one span of a clinical trial's eligibility cr"
  user:   'Section: exclusion\n\nCriterion:\nLower extremity complications (such as skin ulcer, infection, osteomyelitis, and gangrene) identified during screening and requiring treatment at randomization.'
The code has changed since the tape was recorded. Re-record with a key, or check out the commit the tape belongs to.
```

### Attempt 2, tier `json_object`

Restarted with:

```
[system]
# Criteria compiler

You formalise one span of a clinical trial's eligibility criteria into a machine-checkable
predicate. A downstream engine will evaluate that predicate against a patient's structured record
and produce a screening verdict. You never see a patient and you never decide eligibility.

You are given one span at a time, together with the section it appeared under and, where the
protocol nested sub-conditions beneath it, its children. Treat the whole unit as one criterion.

## The only judgement that matters

A criterion you formalise incorrectly is worse than a criterion you decline to formalise. The
engine has an explicit `unsupported` predicate; a criterion marked unsupported goes to a research
coordinator, who reads it and decides. That is a normal, safe, expected outcome. A predicate that
looks right and means something slightly different produces a confident wrong verdict that nobody
catches.

So: when the span does not map cleanly onto the vocabulary below, return `unsupported` with a
reason. Do not approximate. Do not drop a qualifier to make something fit. Do not invent a
threshold the protocol did not state.

Use `unsupported` when the span:

- depends on clinical judgement — "in the opinion of the investigator", "otherwise unsuitable",
  "clinically significant", "adequate organ function" without stated numbers;
- depends on something no chart records — willingness to comply, ability to attend visits,
  informed consent, contraception intentions, geographic availability;
- names a threshold relative to something the engine cannot resolve, such as "above the upper
  limit of normal" (the reference range is laboratory-specific and is not in the record);
- describes a process rather than a state — "must complete a washout", "will be randomised";
- is a class of drug or a category of disease broad enough that no single code captures it, and
  the protocol does not enumerate members;
- nests more deeply than the schema allows.

### Which kind of unsupported

Every `unsupported` criterion also carries a `settlement`, and the choice matters more than it
looks. It decides whether one criterion holds up the whole screening.

**`at_visit`** — the criterion is settled when the patient comes in, and would be settled the same
way for every patient in the world. No chart that has ever been written could answer it, so its
being unanswered here says nothing about *this* patient. A coordinator confirms it at the screening
visit, and the packet lists it for them.

> Signed written informed consent.
> Willing and able to comply with the study schedule.
> Planned coronary procedure or surgery after randomization.
> Planning to start an SGLT2 inhibitor during the study.
> In the investigator's opinion, unsuitable for the study.
> Women of childbearing potential must agree to use contraception during the trial.

**`from_data`** — the criterion asks about the patient's recorded history or state, and we simply
could not formalise the question. That is a gap in what we know about this patient, and it does hold
up the screening.

> Adequate organ function. *(about the record; no threshold stated)*
> Any clinically significant abnormality on screening laboratory tests. *(about the record)*
> Lower extremity complications such as skin ulcer, infection, osteomyelitis and gangrene.
> *(about the record; an open list this schema cannot enumerate)*
> Alanine aminotransferase above the upper limit of normal. *(about the record; the range is
> laboratory-specific and not in it)*

The test to apply, in one sentence: **would a complete and perfect medical record answer this?** If
yes, and we merely failed to express it, that is `from_data`. If even a perfect record could not,
because the answer does not exist until the patient is in the room, that is `at_visit`.

When you are unsure, choose `from_data`. It is the cautious answer: it sends the criterion to a
human either way, and it does not let a verdict through on a criterion that should have stopped it.

## Vocabulary

**`observation`** — a numeric comparison against a measurement: laboratory values, vital signs,
scores. Give the analyte as the protocol names it, the operator, the number, and the unit exactly
as written. `between` is for a two-sided range and takes both bounds. Never convert units; the
engine converts, and it knows which conversions are safe.

**`condition`, `medication`, `procedure`** — whether something is on the chart. `presence`
is `present` when the protocol requires it and `absent` when the protocol requires its absence.

Note carefully: an exclusion criterion that reads "history of myocardial infarction" is a
**`present`** predicate under an **exclusion** criterion. Do not negate it yourself — the engine
knows that a met exclusion rules the patient out. Only use `absent` when the protocol itself
states an absence as a requirement, such as an inclusion criterion reading "no history of
malignancy".

**`demographic`** — age and sex only.

**`all_of` / `any_of` / `not`** — for spans that carry several conditions. "eGFR ≥25 and ≤60" is a
single `observation` with `between`, not a composite. "On an ACE inhibitor or an ARB" is `any_of`.
Sub-bullets beneath a parent bullet are almost always conjunctive: `all_of`.

## Temporal windows

Attach a window whenever the protocol bounds the evidence in time: "within 6 months prior to
screening", "in the last 30 days", "no myocardial infarction within 12 weeks". Use the number and
unit the protocol gives.

Protocols anchor windows to different events — screening, enrolment, randomisation, consent — and
those are genuinely different dates. The engine anchors everything to the screening date. If the
span anchors to something else and the difference could plausibly matter, say so in `notes`; if
the anchor is doing real work in the criterion, return `unsupported`.

## Quoting

`source_quote` must be the span reproduced character for character, including its punctuation and
its unicode operators. It is checked against the protocol text automatically, and a criterion whose
quote does not match is discarded. Do not tidy, expand abbreviations, or normalise `≥` to `>=`.

## Spans that are not criteria

Registry text contains section headings, cross-references and standard boilerplate. If the span is
one of those, set `is_criterion` to false and say why in `notes`. This is a correct answer, not a
failure.

## Concepts

Give the concept's `text` as the protocol names it. Leave `codes` empty — terminology resolution is
a separate step with its own controls. A code you guess here will be trusted downstream.


Reply with a single JSON object and nothing else. It must conform to this JSON schema:

{
  "type": "object",
  "description": "The result of formalising one span of eligibility text. Set is_criterion to false when the span is a heading, a note to readers, or registry boilerplate rather than a condition a patient can meet.",
  "properties": {
    "is_criterion": {
      "type": "boolean"
    },
    "kind": {
      "description": "Only needed when the span sits under no inclusion or exclusion header.",
      "anyOf": [
        {
          "type": "string",
          "enum": [
            "inclusion",
            "exclusion"
          ]
        },
        {
          "type": "null"
        }
      ]
    },
    "source_quote": {
      "type": [
        "string",
        "null"
      ],
      "description": "The span copied verbatim, character for character."
    },
    "predicate": {
      "anyOf": [
        {
          "anyOf": [
            {
              "type": "object",
              "description": "A numeric comparison against a measurement: labs, vitals, scores.",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "observation"
                  ]
                },
                "concept": {
                  "type": "object",
                  "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                  "properties": {
                    "text": {
                      "type": "string"
                    },
                    "codes": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                        "properties": {
                          "system": {
                            "type": "string",
                            "enum": [
                              "LOINC",
                              "SNOMED",
                              "RxNorm",
                              "ICD10",
                              "UCUM"
                            ]
                          },
                          "code": {
                            "type": "string"
                          },
                          "display": {
                            "type": [
                              "string",
                              "null"
                            ]
                          }
                        },
                        "required": [
                          "system",
                          "code",
                          "display"
                        ],
                        "additionalProperties": false
                      }
                    }
                  },
                  "required": [
                    "text",
                    "codes"
                  ],
                  "additionalProperties": false
                },
                "op": {
                  "type": "string",
                  "enum": [
                    "<",
                    "<=",
                    ">",
                    ">=",
                    "==",
                    "!=",
                    "between"
                  ]
                },
                "value": {
                  "type": "number"
                },
                "value_high": {
                  "type": [
                    "number",
                    "null"
                  ]
                },
                "unit": {
                  "type": "string"
                },
                "window": {
                  "anyOf": [
                    {
                      "type": "object",
                      "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                      "properties": {
                        "relation": {
                          "type": "string",
                          "enum": [
                            "within",
                            "before",
                            "after",
                            "ever",
                            "current"
                          ]
                        },
                        "amount": {
                          "type": [
                            "integer",
                            "null"
                          ]
                        },
                        "unit": {
                          "anyOf": [
                            {
                              "type": "string",
                              "enum": [
                                "days",
                                "weeks",
                                "months",
                                "years"
                              ]
                            },
                            {
                              "type": "null"
                            }
                          ]
                        },
                        "anchor": {
                          "type": "string",
                          "enum": [
                            "screening",
                            "enrolment",
                            "randomisation",
                            "consent",
                            "first_dose"
                          ]
                        }
                      },
                      "required": [
                        "relation",
                        "amount",
                        "unit",
                        "anchor"
                      ],
                      "additionalProperties": false
                    },
                    {
                      "type": "null"
                    }
                  ]
                }
              },
              "required": [
                "type",
                "concept",
                "op",
                "value",
                "value_high",
                "unit",
                "window"
              ],
              "additionalProperties": false
            },
            {
              "type": "object",
              "description": "Whether a coded thing is on the chart at all: a condition, a drug, a procedure.",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "condition",
                    "medication",
                    "procedure"
                  ]
                },
                "concept": {
                  "type": "object",
                  "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                  "properties": {
                    "text": {
                      "type": "string"
                    },
                    "codes": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                        "properties": {
                          "system": {
                            "type": "string",
                            "enum": [
                              "LOINC",
                              "SNOMED",
                              "RxNorm",
                              "ICD10",
                              "UCUM"
                            ]
                          },
                          "code": {
                            "type": "string"
                          },
                          "display": {
                            "type": [
                              "string",
                              "null"
                            ]
                          }
                        },
                        "required": [
                          "system",
                          "code",
                          "display"
                        ],
                        "additionalProperties": false
                      }
                    }
                  },
                  "required": [
                    "text",
                    "codes"
                  ],
                  "additionalProperties": false
                },
                "presence": {
                  "type": "string",
                  "enum": [
                    "present",
                    "absent"
                  ]
                },
                "window": {
                  "anyOf": [
                    {
                      "type": "object",
                      "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                      "properties": {
                        "relation": {
                          "type": "string",
                          "enum": [
                            "within",
                            "before",
                            "after",
                            "ever",
                            "current"
                          ]
                        },
                        "amount": {
                          "type": [
                            "integer",
                            "null"
                          ]
                        },
                        "unit": {
                          "anyOf": [
                            {
                              "type": "string",
                              "enum": [
                                "days",
                                "weeks",
                                "months",
                                "years"
                              ]
                            },
                            {
                              "type": "null"
                            }
                          ]
                        },
                        "anchor": {
                          "type": "string",
                          "enum": [
                            "screening",
                            "enrolment",
                            "randomisation",
                            "consent",
                            "first_dose"
                          ]
                        }
                      },
                      "required": [
                        "relation",
                        "amount",
                        "unit",
                        "anchor"
                      ],
                      "additionalProperties": false
                    },
                    {
                      "type": "null"
                    }
                  ]
                }
              },
              "required": [
                "type",
                "concept",
                "presence",
                "window"
              ],
              "additionalProperties": false
            },
            {
              "type": "object",
              "description": "Age and sex, which come from the patient resource rather than from clinical events.",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "demographic"
                  ]
                },
                "field": {
                  "type": "string",
                  "enum": [
                    "age",
                    "sex"
                  ]
                },
                "op": {
                  "type": "string",
                  "enum": [
                    "<",
                    "<=",
                    ">",
                    ">=",
                    "==",
                    "!="
                  ]
                },
                "value": {
                  "type": [
                    "number",
                    "string"
                  ]
                },
                "unit": {
                  "type": [
                    "string",
                    "null"
                  ]
                }
              },
              "required": [
                "type",
                "field",
                "op",
                "value",
                "unit"
              ],
              "additionalProperties": false
            },
            {
              "type": "object",
              "description": "A criterion that cannot be honestly formalised. It stays unresolved forever, by design.\n\n`settlement` says *why* no chart can answer it, and the difference is load-bearing.\n\nA criterion settled `from_data` was a question about the patient's record that we failed to\nformalise \u2014 a threshold with no number, an open category. It is a gap, and it blocks a verdict.\n\nA criterion settled `at_visit` is not a gap at all. Signed informed consent, a procedure planned\nafter randomisation, the investigator's own judgement of the patient in person: these have the\nsame answer for every chart ever written, because they are settled when the patient comes in.\nTreating them as unresolved data made ELIGIBLE unreachable for every real protocol we hold \u2014 one\nconsent criterion and the screening abstains, which is not caution but paralysis.\n\nThe default is `from_data`, so a compiler that says nothing cannot thereby unblock a verdict.",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "unsupported"
                  ]
                },
                "reason": {
                  "type": "string"
                },
                "settlement": {
                  "type": "string",
                  "enum": [
                    "from_data",
                    "at_visit"
                  ]
                }
              },
              "required": [
                "type",
                "reason",
                "settlement"
              ],
              "additionalProperties": false
            },
            {
              "type": "object",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "all_of",
                    "any_of",
                    "not"
                  ]
                },
                "operands": {
                  "type": "array",
                  "items": {
                    "anyOf": [
                      {
                        "type": "object",
                        "description": "A numeric comparison against a measurement: labs, vitals, scores.",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "observation"
                            ]
                          },
                          "concept": {
                            "type": "object",
                            "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                            "properties": {
                              "text": {
                                "type": "string"
                              },
                              "codes": {
                                "type": "array",
                                "items": {
                                  "type": "object",
                                  "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                                  "properties": {
                                    "system": {
                                      "type": "string",
                                      "enum": [
                                        "LOINC",
                                        "SNOMED",
                                        "RxNorm",
                                        "ICD10",
                                        "UCUM"
                                      ]
                                    },
                                    "code": {
                                      "type": "string"
                                    },
                                    "display": {
                                      "type": [
                                        "string",
                                        "null"
                                      ]
                                    }
                                  },
                                  "required": [
                                    "system",
                                    "code",
                                    "display"
                                  ],
                                  "additionalProperties": false
                                }
                              }
                            },
                            "required": [
                              "text",
                              "codes"
                            ],
                            "additionalProperties": false
                          },
                          "op": {
                            "type": "string",
                            "enum": [
                              "<",
                              "<=",
                              ">",
                              ">=",
                              "==",
                              "!=",
                              "between"
                            ]
                          },
                          "value": {
                            "type": "number"
                          },
                          "value_high": {
                            "type": [
                              "number",
                              "null"
                            ]
                          },
                          "unit": {
                            "type": "string"
                          },
                          "window": {
                            "anyOf": [
                              {
                                "type": "object",
                                "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                                "properties": {
                                  "relation": {
                                    "type": "string",
                                    "enum": [
                                      "within",
                                      "before",
                                      "after",
                                      "ever",
                                      "current"
                                    ]
                                  },
                                  "amount": {
                                    "type": [
                                      "integer",
                                      "null"
                                    ]
                                  },
                                  "unit": {
                                    "anyOf": [
                                      {
                                        "type": "string",
                                        "enum": [
                                          "days",
                                          "weeks",
                                          "months",
                                          "years"
                                        ]
                                      },
                                      {
                                        "type": "null"
                                      }
                                    ]
                                  },
                                  "anchor": {
                                    "type": "string",
                                    "enum": [
                                      "screening",
                                      "enrolment",
                                      "randomisation",
                                      "consent",
                                      "first_dose"
                                    ]
                                  }
                                },
                                "required": [
                                  "relation",
                                  "amount",
                                  "unit",
                                  "anchor"
                                ],
                                "additionalProperties": false
                              },
                              {
                                "type": "null"
                              }
                            ]
                          }
                        },
                        "required": [
                          "type",
                          "concept",
                          "op",
                          "value",
                          "value_high",
                          "unit",
                          "window"
                        ],
                        "additionalProperties": false
                      },
                      {
                        "type": "object",
                        "description": "Whether a coded thing is on the chart at all: a condition, a drug, a procedure.",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "condition",
                              "medication",
                              "procedure"
                            ]
                          },
                          "concept": {
                            "type": "object",
                            "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                            "properties": {
                              "text": {
                                "type": "string"
                              },
                              "codes": {
                                "type": "array",
                                "items": {
                                  "type": "object",
                                  "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                                  "properties": {
                                    "system": {
                                      "type": "string",
                                      "enum": [
                                        "LOINC",
                                        "SNOMED",
                                        "RxNorm",
                                        "ICD10",
                                        "UCUM"
                                      ]
                                    },
                                    "code": {
                                      "type": "string"
                                    },
                                    "display": {
                                      "type": [
                                        "string",
                                        "null"
                                      ]
                                    }
                                  },
                                  "required": [
                                    "system",
                                    "code",
                                    "display"
                                  ],
                                  "additionalProperties": false
                                }
                              }
                            },
                            "required": [
                              "text",
                              "codes"
                            ],
                            "additionalProperties": false
                          },
                          "presence": {
                            "type": "string",
                            "enum": [
                              "present",
                              "absent"
                            ]
                          },
                          "window": {
                            "anyOf": [
                              {
                                "type": "object",
                                "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                                "properties": {
                                  "relation": {
                                    "type": "string",
                                    "enum": [
                                      "within",
                                      "before",
                                      "after",
                                      "ever",
                                      "current"
                                    ]
                                  },
                                  "amount": {
                                    "type": [
                                      "integer",
                                      "null"
                                    ]
                                  },
                                  "unit": {
                                    "anyOf": [
                                      {
                                        "type": "string",
                                        "enum": [
                                          "days",
                                          "weeks",
                                          "months",
                                          "years"
                                        ]
                                      },
                                      {
                                        "type": "null"
                                      }
                                    ]
                                  },
                                  "anchor": {
                                    "type": "string",
                                    "enum": [
                                      "screening",
                                      "enrolment",
                                      "randomisation",
                                      "consent",
                                      "first_dose"
                                    ]
                                  }
                                },
                                "required": [
                                  "relation",
                                  "amount",
                                  "unit",
                                  "anchor"
                                ],
                                "additionalProperties": false
                              },
                              {
                                "type": "null"
                              }
                            ]
                          }
                        },
                        "required": [
                          "type",
                          "concept",
                          "presence",
                          "window"
                        ],
                        "additionalProperties": false
                      },
                      {
                        "type": "object",
                        "description": "Age and sex, which come from the patient resource rather than from clinical events.",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "demographic"
                            ]
                          },
                          "field": {
                            "type": "string",
                            "enum": [
                              "age",
                              "sex"
                            ]
                          },
                          "op": {
                            "type": "string",
                            "enum": [
                              "<",
                              "<=",
                              ">",
                              ">=",
                              "==",
                              "!="
                            ]
                          },
                          "value": {
                            "type": [
                              "number",
                              "string"
                            ]
                          },
                          "unit": {
                            "type": [
                              "string",
                              "null"
                            ]
                          }
                        },
                        "required": [
                          "type",
                          "field",
                          "op",
                          "value",
                          "unit"
                        ],
                        "additionalProperties": false
                      },
                      {
                        "type": "object",
                        "description": "A criterion that cannot be honestly formalised. It stays unresolved forever, by design.\n\n`settlement` says *why* no chart can answer it, and the difference is load-bearing.\n\nA criterion settled `from_data` was a question about the patient's record that we failed to\nformalise \u2014 a threshold with no number, an open category. It is a gap, and it blocks a verdict.\n\nA criterion settled `at_visit` is not a gap at all. Signed informed consent, a procedure planned\nafter randomisation, the investigator's own judgement of the patient in person: these have the\nsame answer for every chart ever written, because they are settled when the patient comes in.\nTreating them as unresolved data made ELIGIBLE unreachable for every real protocol we hold \u2014 one\nconsent criterion and the screening abstains, which is not caution but paralysis.\n\nThe default is `from_data`, so a compiler that says nothing cannot thereby unblock a verdict.",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "unsupported"
                            ]
                          },
                          "reason": {
                            "type": "string"
                          },
                          "settlement": {
                            "type": "string",
                            "enum": [
                              "from_data",
                              "at_visit"
                            ]
                          }
                        },
                        "required": [
                          "type",
                          "reason",
                          "settlement"
                        ],
                        "additionalProperties": false
                      },
                      {
                        "type": "object",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "all_of",
                              "any_of",
                              "not"
                            ]
                          },
                          "operands": {
                            "type": "array",
                            "items": {
                              "anyOf": [
                                {
                                  "type": "object",
                                  "description": "A numeric comparison against a measurement: labs, vitals, scores.",
                                  "properties": {
                                    "type": {
                                      "type": "string",
                                      "enum": [
                                        "observation"
                                      ]
                                    },
                                    "concept": {
                                      "type": "object",
                                      "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                                      "properties": {
                                        "text": {
                                          "type": "string"
                                        },
                                        "codes": {
                                          "type": "array",
                                          "items": {
                                            "type": "object",
                                            "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                                            "properties": {
                                              "system": {
                                                "type": "string",
                                                "enum": [
                                                  "LOINC",
                                                  "SNOMED",
                                                  "RxNorm",
                                                  "ICD10",
                                                  "UCUM"
                                                ]
                                              },
                                              "code": {
                                                "type": "string"
                                              },
                                              "display": {
                                                "type": [
                                                  "string",
                                                  "null"
                                                ]
                                              }
                                            },
                                            "required": [
                                              "system",
                                              "code",
                                              "display"
                                            ],
                                            "additionalProperties": false
                                          }
                                        }
                                      },
                                      "required": [
                                        "text",
                                        "codes"
                                      ],
                                      "additionalProperties": false
                                    },
                                    "op": {
                                      "type": "string",
                                      "enum": [
                                        "<",
                                        "<=",
                                        ">",
                                        ">=",
                                        "==",
                                        "!=",
                                        "between"
                                      ]
                                    },
                                    "value": {
                                      "type": "number"
                                    },
                                    "value_high": {
                                      "type": [
                                        "number",
                                        "null"
                                      ]
                                    },
                                    "unit": {
                                      "type": "string"
                                    },
                                    "window": {
                                      "anyOf": [
                                        {
                                          "type": "object",
                                          "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                                          "properties": {
                                            "relation": {
                                              "type": "string",
                                              "enum": [
                                                "within",
                                                "before",
                                                "after",
                                                "ever",
                                                "current"
                                              ]
                                            },
                                            "amount": {
                                              "type": [
                                                "integer",
                                                "null"
                                              ]
                                            },
                                            "unit": {
                                              "anyOf": [
                                                {
                                                  "type": "string",
                                                  "enum": [
                                                    "days",
                                                    "weeks",
                                                    "months",
                                                    "years"
                                                  ]
                                                },
                                                {
                                                  "type": "null"
                                                }
                                              ]
                                            },
                                            "anchor": {
                                              "type": "string",
                                              "enum": [
                                                "screening",
                                                "enrolment",
                                                "randomisation",
                                                "consent",
                                                "first_dose"
                                              ]
                                            }
                                          },
                                          "required": [
                                            "relation",
                                            "amount",
                                            "unit",
                                            "anchor"
                                          ],
                                          "additionalProperties": false
                                        },
                                        {
                                          "type": "null"
                                        }
                                      ]
                                    }
                                  },
                                  "required": [
                                    "type",
                                    "concept",
                                    "op",
                                    "value",
                                    "value_high",
                                    "unit",
                                    "window"
                                  ],
                                  "additionalProperties": false
                                },
                                {
                                  "type": "object",
                                  "description": "Whether a coded thing is on the chart at all: a condition, a drug, a procedure.",
                                  "properties": {
                                    "type": {
                                      "type": "string",
                                      "enum": [
                                        "condition",
                                        "medication",
                                        "procedure"
                                      ]
                                    },
                                    "concept": {
                                      "type": "object",
                                      "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                                      "properties": {
                                        "text": {
                                          "type": "string"
                                        },
                                        "codes": {
                                          "type": "array",
                                          "items": {
                                            "type": "object",
                                            "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                                            "properties": {
                                              "system": {
                                                "type": "string",
                                                "enum": [
                                                  "LOINC",
                                                  "SNOMED",
                                                  "RxNorm",
                                                  "ICD10",
                                                  "UCUM"
                                                ]
                                              },
                                              "code": {
                                                "type": "string"
                                              },
                                              "display": {
                                                "type": [
                                                  "string",
                                                  "null"
                                                ]
                                              }
                                            },
                                            "required": [
                                              "system",
                                              "code",
                                              "display"
                                            ],
                                            "additionalProperties": false
                                          }
                                        }
                                      },
                                      "required": [
                                        "text",
                                        "codes"
                                      ],
                                      "additionalProperties": false
                                    },
                                    "presence": {
                                      "type": "string",
                                      "enum": [
                                        "present",
                                        "absent"
                                      ]
                                    },
                                    "window": {
                                      "anyOf": [
                                        {
                                          "type": "object",
                                          "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                                          "properties": {
                                            "relation": {
                                              "type": "string",
                                              "enum": [
                                                "within",
                                                "before",
                                                "after",
                                                "ever",
                                                "current"
                                              ]
                                            },
                                            "amount": {
                                              "type": [
                                                "integer",
                                                "null"
                                              ]
                                            },
                                            "unit": {
                                              "anyOf": [
                                                {
                                                  "type": "string",
                                                  "enum": [
                                                    "days",
                                                    "weeks",
                                                    "months",
                                                    "years"
                                                  ]
                                                },
                                                {
                                                  "type": "null"
                                                }
                                              ]
                                            },
                                            "anchor": {
                                              "type": "string",
                                              "enum": [
                                                "screening",
                                                "enrolment",
                                                "randomisation",
                                                "consent",
                                                "first_dose"
                                              ]
                                            }
                                          },
                                          "required": [
                                            "relation",
                                            "amount",
                                            "unit",
                                            "anchor"
                                          ],
                                          "additionalProperties": false
                                        },
                                        {
                                          "type": "null"
                                        }
                                      ]
                                    }
                                  },
                                  "required": [
                                    "type",
                                    "concept",
                                    "presence",
                                    "window"
                                  ],
                                  "additionalProperties": false
                                },
                                {
                                  "type": "object",
                                  "description": "Age and sex, which come from the patient resource rather than from clinical events.",
                                  "properties": {
                                    "type": {
                                      "type": "string",
                                      "enum": [
                                        "demographic"
                                      ]
                                    },
                                    "field": {
                                      "type": "string",
                                      "enum": [
                                        "age",
                                        "sex"
                                      ]
                                    },
                                    "op": {
                                      "type": "string",
                                      "enum": [
                                        "<",
                                        "<=",
                                        ">",
                                        ">=",
                                        "==",
                                        "!="
                                      ]
                                    },
                                    "value": {
                                      "type": [
                                        "number",
                                        "string"
                                      ]
                                    },
                                    "unit": {
                                      "type": [
                                        "string",
                                        "null"
                                      ]
                                    }
                                  },
                                  "required": [
                                    "type",
                                    "field",
                                    "op",
                                    "value",
                                    "unit"
                                  ],
                                  "additionalProperties": false
                                },
                                {
                                  "type": "object",
                                  "description": "A criterion that cannot be honestly formalised. It stays unresolved forever, by design.\n\n`settlement` says *why* no chart can answer it, and the difference is load-bearing.\n\nA criterion settled `from_data` was a question about the patient's record that we failed to\nformalise \u2014 a threshold with no number, an open category. It is a gap, and it blocks a verdict.\n\nA criterion settled `at_visit` is not a gap at all. Signed informed consent, a procedure planned\nafter randomisation, the investigator's own judgement of the patient in person: these have the\nsame answer for every chart ever written, because they are settled when the patient comes in.\nTreating them as unresolved data made ELIGIBLE unreachable for every real protocol we hold \u2014 one\nconsent criterion and the screening abstains, which is not caution but paralysis.\n\nThe default is `from_data`, so a compiler that says nothing cannot thereby unblock a verdict.",
                                  "properties": {
                                    "type": {
                                      "type": "string",
                                      "enum": [
                                        "unsupported"
                                      ]
                                    },
                                    "reason": {
                                      "type": "string"
                                    },
                                    "settlement": {
                                      "type": "string",
                                      "enum": [
                                        "from_data",
                                        "at_visit"
                                      ]
                                    }
                                  },
                                  "required": [
                                    "type",
                                    "reason",
                                    "settlement"
                                  ],
                                  "additionalProperties": false
                                }
                              ]
                            }
                          }
                        },
                        "required": [
                          "type",
                          "operands"
                        ],
                        "additionalProperties": false
                      }
                    ]
                  }
                }
              },
              "required": [
                "type",
                "operands"
              ],
              "additionalProperties": false
            }
          ]
        },
        {
          "type": "null"
        }
      ]
    },
    "notes": {
      "type": [
        "string",
        "null"
      ],
      "description": "Why this span was hard, or why it is not a criterion."
    }
  },
  "required": [
    "is_criterion",
    "kind",
    "source_quote",
    "predicate",
    "notes"
  ],
  "additionalProperties": false
}

[user]
Section: exclusion

Criterion:
Lower extremity complications (such as skin ulcer, infection, osteomyelitis, and gangrene) identified during screening and requiring treatment at randomization.
```

Response:

```
{
  "is_criterion": true,
  "kind": "exclusion",
  "source_quote": "Lower extremity complications (such as skin ulcer, infection, osteomyelitis, and gangrene) identified during screening and requiring treatment at randomization.",
  "predicate": {
    "type": "unsupported",
    "reason": "\"Lower extremity complications\" is an open-ended category illustrated by examples (skin ulcer, infection, osteomyelitis, gangrene) rather than an enumerated list; no single code or fixed set of codes captures it. It also requires judging that treatment is 'required' at a future randomization timepoint, which is not a stable recorded fact at screening.",
    "settlement": "from_data"
  },
  "notes": "Open disease category with illustrative, non-exhaustive examples; also references a status ('requiring treatment') at randomization rather than a discrete coded diagnosis at screening."
}
```

Validated against the schema.

### Result

```json
{
  "is_criterion": true,
  "kind": "exclusion",
  "source_quote": "Lower extremity complications (such as skin ulcer, infection, osteomyelitis, and gangrene) identified during screening and requiring treatment at randomization.",
  "predicate": {
    "type": "unsupported",
    "reason": "\"Lower extremity complications\" is an open-ended category illustrated by examples (skin ulcer, infection, osteomyelitis, gangrene) rather than an enumerated list; no single code or fixed set of codes captures it. It also requires judging that treatment is 'required' at a future randomization timepoint, which is not a stable recorded fact at screening.",
    "settlement": "from_data"
  },
  "notes": "Open disease category with illustrative, non-exhaustive examples; also references a status ('requiring treatment') at randomization rather than a discrete coded diagnosis at screening."
}
```

## 8. compiler on venice/claude-sonnet-5

- **Started:** 2026-08-30T10:35:10Z
- **Tier used:** `json_object`
- **Retries:** 1
- **Tokens:** 13463 in / 195 out
- **Estimated cost:** $0.0289
- **Outcome:** validated

### Instructions

```
# Criteria compiler

You formalise one span of a clinical trial's eligibility criteria into a machine-checkable
predicate. A downstream engine will evaluate that predicate against a patient's structured record
and produce a screening verdict. You never see a patient and you never decide eligibility.

You are given one span at a time, together with the section it appeared under and, where the
protocol nested sub-conditions beneath it, its children. Treat the whole unit as one criterion.

## The only judgement that matters

A criterion you formalise incorrectly is worse than a criterion you decline to formalise. The
engine has an explicit `unsupported` predicate; a criterion marked unsupported goes to a research
coordinator, who reads it and decides. That is a normal, safe, expected outcome. A predicate that
looks right and means something slightly different produces a confident wrong verdict that nobody
catches.

So: when the span does not map cleanly onto the vocabulary below, return `unsupported` with a
reason. Do not approximate. Do not drop a qualifier to make something fit. Do not invent a
threshold the protocol did not state.

Use `unsupported` when the span:

- depends on clinical judgement — "in the opinion of the investigator", "otherwise unsuitable",
  "clinically significant", "adequate organ function" without stated numbers;
- depends on something no chart records — willingness to comply, ability to attend visits,
  informed consent, contraception intentions, geographic availability;
- names a threshold relative to something the engine cannot resolve, such as "above the upper
  limit of normal" (the reference range is laboratory-specific and is not in the record);
- describes a process rather than a state — "must complete a washout", "will be randomised";
- is a class of drug or a category of disease broad enough that no single code captures it, and
  the protocol does not enumerate members;
- nests more deeply than the schema allows.

### Which kind of unsupported

Every `unsupported` criterion also carries a `settlement`, and the choice matters more than it
looks. It decides whether one criterion holds up the whole screening.

**`at_visit`** — the criterion is settled when the patient comes in, and would be settled the same
way for every patient in the world. No chart that has ever been written could answer it, so its
being unanswered here says nothing about *this* patient. A coordinator confirms it at the screening
visit, and the packet lists it for them.

> Signed written informed consent.
> Willing and able to comply with the study schedule.
> Planned coronary procedure or surgery after randomization.
> Planning to start an SGLT2 inhibitor during the study.
> In the investigator's opinion, unsuitable for the study.
> Women of childbearing potential must agree to use contraception during the trial.

**`from_data`** — the criterion asks about the patient's recorded history or state, and we simply
could not formalise the question. That is a gap in what we know about this patient, and it does hold
up the screening.

> Adequate organ function. *(about the record; no threshold stated)*
> Any clinically significant abnormality on screening laboratory tests. *(about the record)*
> Lower extremity complications such as skin ulcer, infection, osteomyelitis and gangrene.
> *(about the record; an open list this schema cannot enumerate)*
> Alanine aminotransferase above the upper limit of normal. *(about the record; the range is
> laboratory-specific and not in it)*

The test to apply, in one sentence: **would a complete and perfect medical record answer this?** If
yes, and we merely failed to express it, that is `from_data`. If even a perfect record could not,
because the answer does not exist until the patient is in the room, that is `at_visit`.

When you are unsure, choose `from_data`. It is the cautious answer: it sends the criterion to a
human either way, and it does not let a verdict through on a criterion that should have stopped it.

## Vocabulary

**`observation`** — a numeric comparison against a measurement: laboratory values, vital signs,
scores. Give the analyte as the protocol names it, the operator, the number, and the unit exactly
as written. `between` is for a two-sided range and takes both bounds. Never convert units; the
engine converts, and it knows which conversions are safe.

**`condition`, `medication`, `procedure`** — whether something is on the chart. `presence`
is `present` when the protocol requires it and `absent` when the protocol requires its absence.

Note carefully: an exclusion criterion that reads "history of myocardial infarction" is a
**`present`** predicate under an **exclusion** criterion. Do not negate it yourself — the engine
knows that a met exclusion rules the patient out. Only use `absent` when the protocol itself
states an absence as a requirement, such as an inclusion criterion reading "no history of
malignancy".

**`demographic`** — age and sex only.

**`all_of` / `any_of` / `not`** — for spans that carry several conditions. "eGFR ≥25 and ≤60" is a
single `observation` with `between`, not a composite. "On an ACE inhibitor or an ARB" is `any_of`.
Sub-bullets beneath a parent bullet are almost always conjunctive: `all_of`.

## Temporal windows

Attach a window whenever the protocol bounds the evidence in time: "within 6 months prior to
screening", "in the last 30 days", "no myocardial infarction within 12 weeks". Use the number and
unit the protocol gives.

Protocols anchor windows to different events — screening, enrolment, randomisation, consent — and
those are genuinely different dates. The engine anchors everything to the screening date. If the
span anchors to something else and the difference could plausibly matter, say so in `notes`; if
the anchor is doing real work in the criterion, return `unsupported`.

## Quoting

`source_quote` must be the span reproduced character for character, including its punctuation and
its unicode operators. It is checked against the protocol text automatically, and a criterion whose
quote does not match is discarded. Do not tidy, expand abbreviations, or normalise `≥` to `>=`.

## Spans that are not criteria

Registry text contains section headings, cross-references and standard boilerplate. If the span is
one of those, set `is_criterion` to false and say why in `notes`. This is a correct answer, not a
failure.

## Concepts

Give the concept's `text` as the protocol names it. Leave `codes` empty — terminology resolution is
a separate step with its own controls. A code you guess here will be trusted downstream.

```

### Request

```
Section: exclusion

Criterion:
Planning to start a sodium-glucose linked transporter-2 (SGLT2) inhibitor during the study.
```

### Attempt 1, tier `json_schema`

The provider rejected the request:

```
TapeMiss: no recorded answer for this request.
  model:  claude-sonnet-5
  system: "# Criteria compiler\n\nYou formalise one span of a clinical trial's eligibility cr"
  user:   'Section: exclusion\n\nCriterion:\nPlanning to start a sodium-glucose linked transporter-2 (SGLT2) inhibitor during the study.'
The code has changed since the tape was recorded. Re-record with a key, or check out the commit the tape belongs to.
```

### Attempt 2, tier `json_object`

Restarted with:

```
[system]
# Criteria compiler

You formalise one span of a clinical trial's eligibility criteria into a machine-checkable
predicate. A downstream engine will evaluate that predicate against a patient's structured record
and produce a screening verdict. You never see a patient and you never decide eligibility.

You are given one span at a time, together with the section it appeared under and, where the
protocol nested sub-conditions beneath it, its children. Treat the whole unit as one criterion.

## The only judgement that matters

A criterion you formalise incorrectly is worse than a criterion you decline to formalise. The
engine has an explicit `unsupported` predicate; a criterion marked unsupported goes to a research
coordinator, who reads it and decides. That is a normal, safe, expected outcome. A predicate that
looks right and means something slightly different produces a confident wrong verdict that nobody
catches.

So: when the span does not map cleanly onto the vocabulary below, return `unsupported` with a
reason. Do not approximate. Do not drop a qualifier to make something fit. Do not invent a
threshold the protocol did not state.

Use `unsupported` when the span:

- depends on clinical judgement — "in the opinion of the investigator", "otherwise unsuitable",
  "clinically significant", "adequate organ function" without stated numbers;
- depends on something no chart records — willingness to comply, ability to attend visits,
  informed consent, contraception intentions, geographic availability;
- names a threshold relative to something the engine cannot resolve, such as "above the upper
  limit of normal" (the reference range is laboratory-specific and is not in the record);
- describes a process rather than a state — "must complete a washout", "will be randomised";
- is a class of drug or a category of disease broad enough that no single code captures it, and
  the protocol does not enumerate members;
- nests more deeply than the schema allows.

### Which kind of unsupported

Every `unsupported` criterion also carries a `settlement`, and the choice matters more than it
looks. It decides whether one criterion holds up the whole screening.

**`at_visit`** — the criterion is settled when the patient comes in, and would be settled the same
way for every patient in the world. No chart that has ever been written could answer it, so its
being unanswered here says nothing about *this* patient. A coordinator confirms it at the screening
visit, and the packet lists it for them.

> Signed written informed consent.
> Willing and able to comply with the study schedule.
> Planned coronary procedure or surgery after randomization.
> Planning to start an SGLT2 inhibitor during the study.
> In the investigator's opinion, unsuitable for the study.
> Women of childbearing potential must agree to use contraception during the trial.

**`from_data`** — the criterion asks about the patient's recorded history or state, and we simply
could not formalise the question. That is a gap in what we know about this patient, and it does hold
up the screening.

> Adequate organ function. *(about the record; no threshold stated)*
> Any clinically significant abnormality on screening laboratory tests. *(about the record)*
> Lower extremity complications such as skin ulcer, infection, osteomyelitis and gangrene.
> *(about the record; an open list this schema cannot enumerate)*
> Alanine aminotransferase above the upper limit of normal. *(about the record; the range is
> laboratory-specific and not in it)*

The test to apply, in one sentence: **would a complete and perfect medical record answer this?** If
yes, and we merely failed to express it, that is `from_data`. If even a perfect record could not,
because the answer does not exist until the patient is in the room, that is `at_visit`.

When you are unsure, choose `from_data`. It is the cautious answer: it sends the criterion to a
human either way, and it does not let a verdict through on a criterion that should have stopped it.

## Vocabulary

**`observation`** — a numeric comparison against a measurement: laboratory values, vital signs,
scores. Give the analyte as the protocol names it, the operator, the number, and the unit exactly
as written. `between` is for a two-sided range and takes both bounds. Never convert units; the
engine converts, and it knows which conversions are safe.

**`condition`, `medication`, `procedure`** — whether something is on the chart. `presence`
is `present` when the protocol requires it and `absent` when the protocol requires its absence.

Note carefully: an exclusion criterion that reads "history of myocardial infarction" is a
**`present`** predicate under an **exclusion** criterion. Do not negate it yourself — the engine
knows that a met exclusion rules the patient out. Only use `absent` when the protocol itself
states an absence as a requirement, such as an inclusion criterion reading "no history of
malignancy".

**`demographic`** — age and sex only.

**`all_of` / `any_of` / `not`** — for spans that carry several conditions. "eGFR ≥25 and ≤60" is a
single `observation` with `between`, not a composite. "On an ACE inhibitor or an ARB" is `any_of`.
Sub-bullets beneath a parent bullet are almost always conjunctive: `all_of`.

## Temporal windows

Attach a window whenever the protocol bounds the evidence in time: "within 6 months prior to
screening", "in the last 30 days", "no myocardial infarction within 12 weeks". Use the number and
unit the protocol gives.

Protocols anchor windows to different events — screening, enrolment, randomisation, consent — and
those are genuinely different dates. The engine anchors everything to the screening date. If the
span anchors to something else and the difference could plausibly matter, say so in `notes`; if
the anchor is doing real work in the criterion, return `unsupported`.

## Quoting

`source_quote` must be the span reproduced character for character, including its punctuation and
its unicode operators. It is checked against the protocol text automatically, and a criterion whose
quote does not match is discarded. Do not tidy, expand abbreviations, or normalise `≥` to `>=`.

## Spans that are not criteria

Registry text contains section headings, cross-references and standard boilerplate. If the span is
one of those, set `is_criterion` to false and say why in `notes`. This is a correct answer, not a
failure.

## Concepts

Give the concept's `text` as the protocol names it. Leave `codes` empty — terminology resolution is
a separate step with its own controls. A code you guess here will be trusted downstream.


Reply with a single JSON object and nothing else. It must conform to this JSON schema:

{
  "type": "object",
  "description": "The result of formalising one span of eligibility text. Set is_criterion to false when the span is a heading, a note to readers, or registry boilerplate rather than a condition a patient can meet.",
  "properties": {
    "is_criterion": {
      "type": "boolean"
    },
    "kind": {
      "description": "Only needed when the span sits under no inclusion or exclusion header.",
      "anyOf": [
        {
          "type": "string",
          "enum": [
            "inclusion",
            "exclusion"
          ]
        },
        {
          "type": "null"
        }
      ]
    },
    "source_quote": {
      "type": [
        "string",
        "null"
      ],
      "description": "The span copied verbatim, character for character."
    },
    "predicate": {
      "anyOf": [
        {
          "anyOf": [
            {
              "type": "object",
              "description": "A numeric comparison against a measurement: labs, vitals, scores.",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "observation"
                  ]
                },
                "concept": {
                  "type": "object",
                  "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                  "properties": {
                    "text": {
                      "type": "string"
                    },
                    "codes": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                        "properties": {
                          "system": {
                            "type": "string",
                            "enum": [
                              "LOINC",
                              "SNOMED",
                              "RxNorm",
                              "ICD10",
                              "UCUM"
                            ]
                          },
                          "code": {
                            "type": "string"
                          },
                          "display": {
                            "type": [
                              "string",
                              "null"
                            ]
                          }
                        },
                        "required": [
                          "system",
                          "code",
                          "display"
                        ],
                        "additionalProperties": false
                      }
                    }
                  },
                  "required": [
                    "text",
                    "codes"
                  ],
                  "additionalProperties": false
                },
                "op": {
                  "type": "string",
                  "enum": [
                    "<",
                    "<=",
                    ">",
                    ">=",
                    "==",
                    "!=",
                    "between"
                  ]
                },
                "value": {
                  "type": "number"
                },
                "value_high": {
                  "type": [
                    "number",
                    "null"
                  ]
                },
                "unit": {
                  "type": "string"
                },
                "window": {
                  "anyOf": [
                    {
                      "type": "object",
                      "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                      "properties": {
                        "relation": {
                          "type": "string",
                          "enum": [
                            "within",
                            "before",
                            "after",
                            "ever",
                            "current"
                          ]
                        },
                        "amount": {
                          "type": [
                            "integer",
                            "null"
                          ]
                        },
                        "unit": {
                          "anyOf": [
                            {
                              "type": "string",
                              "enum": [
                                "days",
                                "weeks",
                                "months",
                                "years"
                              ]
                            },
                            {
                              "type": "null"
                            }
                          ]
                        },
                        "anchor": {
                          "type": "string",
                          "enum": [
                            "screening",
                            "enrolment",
                            "randomisation",
                            "consent",
                            "first_dose"
                          ]
                        }
                      },
                      "required": [
                        "relation",
                        "amount",
                        "unit",
                        "anchor"
                      ],
                      "additionalProperties": false
                    },
                    {
                      "type": "null"
                    }
                  ]
                }
              },
              "required": [
                "type",
                "concept",
                "op",
                "value",
                "value_high",
                "unit",
                "window"
              ],
              "additionalProperties": false
            },
            {
              "type": "object",
              "description": "Whether a coded thing is on the chart at all: a condition, a drug, a procedure.",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "condition",
                    "medication",
                    "procedure"
                  ]
                },
                "concept": {
                  "type": "object",
                  "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                  "properties": {
                    "text": {
                      "type": "string"
                    },
                    "codes": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                        "properties": {
                          "system": {
                            "type": "string",
                            "enum": [
                              "LOINC",
                              "SNOMED",
                              "RxNorm",
                              "ICD10",
                              "UCUM"
                            ]
                          },
                          "code": {
                            "type": "string"
                          },
                          "display": {
                            "type": [
                              "string",
                              "null"
                            ]
                          }
                        },
                        "required": [
                          "system",
                          "code",
                          "display"
                        ],
                        "additionalProperties": false
                      }
                    }
                  },
                  "required": [
                    "text",
                    "codes"
                  ],
                  "additionalProperties": false
                },
                "presence": {
                  "type": "string",
                  "enum": [
                    "present",
                    "absent"
                  ]
                },
                "window": {
                  "anyOf": [
                    {
                      "type": "object",
                      "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                      "properties": {
                        "relation": {
                          "type": "string",
                          "enum": [
                            "within",
                            "before",
                            "after",
                            "ever",
                            "current"
                          ]
                        },
                        "amount": {
                          "type": [
                            "integer",
                            "null"
                          ]
                        },
                        "unit": {
                          "anyOf": [
                            {
                              "type": "string",
                              "enum": [
                                "days",
                                "weeks",
                                "months",
                                "years"
                              ]
                            },
                            {
                              "type": "null"
                            }
                          ]
                        },
                        "anchor": {
                          "type": "string",
                          "enum": [
                            "screening",
                            "enrolment",
                            "randomisation",
                            "consent",
                            "first_dose"
                          ]
                        }
                      },
                      "required": [
                        "relation",
                        "amount",
                        "unit",
                        "anchor"
                      ],
                      "additionalProperties": false
                    },
                    {
                      "type": "null"
                    }
                  ]
                }
              },
              "required": [
                "type",
                "concept",
                "presence",
                "window"
              ],
              "additionalProperties": false
            },
            {
              "type": "object",
              "description": "Age and sex, which come from the patient resource rather than from clinical events.",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "demographic"
                  ]
                },
                "field": {
                  "type": "string",
                  "enum": [
                    "age",
                    "sex"
                  ]
                },
                "op": {
                  "type": "string",
                  "enum": [
                    "<",
                    "<=",
                    ">",
                    ">=",
                    "==",
                    "!="
                  ]
                },
                "value": {
                  "type": [
                    "number",
                    "string"
                  ]
                },
                "unit": {
                  "type": [
                    "string",
                    "null"
                  ]
                }
              },
              "required": [
                "type",
                "field",
                "op",
                "value",
                "unit"
              ],
              "additionalProperties": false
            },
            {
              "type": "object",
              "description": "A criterion that cannot be honestly formalised. It stays unresolved forever, by design.\n\n`settlement` says *why* no chart can answer it, and the difference is load-bearing.\n\nA criterion settled `from_data` was a question about the patient's record that we failed to\nformalise \u2014 a threshold with no number, an open category. It is a gap, and it blocks a verdict.\n\nA criterion settled `at_visit` is not a gap at all. Signed informed consent, a procedure planned\nafter randomisation, the investigator's own judgement of the patient in person: these have the\nsame answer for every chart ever written, because they are settled when the patient comes in.\nTreating them as unresolved data made ELIGIBLE unreachable for every real protocol we hold \u2014 one\nconsent criterion and the screening abstains, which is not caution but paralysis.\n\nThe default is `from_data`, so a compiler that says nothing cannot thereby unblock a verdict.",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "unsupported"
                  ]
                },
                "reason": {
                  "type": "string"
                },
                "settlement": {
                  "type": "string",
                  "enum": [
                    "from_data",
                    "at_visit"
                  ]
                }
              },
              "required": [
                "type",
                "reason",
                "settlement"
              ],
              "additionalProperties": false
            },
            {
              "type": "object",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "all_of",
                    "any_of",
                    "not"
                  ]
                },
                "operands": {
                  "type": "array",
                  "items": {
                    "anyOf": [
                      {
                        "type": "object",
                        "description": "A numeric comparison against a measurement: labs, vitals, scores.",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "observation"
                            ]
                          },
                          "concept": {
                            "type": "object",
                            "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                            "properties": {
                              "text": {
                                "type": "string"
                              },
                              "codes": {
                                "type": "array",
                                "items": {
                                  "type": "object",
                                  "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                                  "properties": {
                                    "system": {
                                      "type": "string",
                                      "enum": [
                                        "LOINC",
                                        "SNOMED",
                                        "RxNorm",
                                        "ICD10",
                                        "UCUM"
                                      ]
                                    },
                                    "code": {
                                      "type": "string"
                                    },
                                    "display": {
                                      "type": [
                                        "string",
                                        "null"
                                      ]
                                    }
                                  },
                                  "required": [
                                    "system",
                                    "code",
                                    "display"
                                  ],
                                  "additionalProperties": false
                                }
                              }
                            },
                            "required": [
                              "text",
                              "codes"
                            ],
                            "additionalProperties": false
                          },
                          "op": {
                            "type": "string",
                            "enum": [
                              "<",
                              "<=",
                              ">",
                              ">=",
                              "==",
                              "!=",
                              "between"
                            ]
                          },
                          "value": {
                            "type": "number"
                          },
                          "value_high": {
                            "type": [
                              "number",
                              "null"
                            ]
                          },
                          "unit": {
                            "type": "string"
                          },
                          "window": {
                            "anyOf": [
                              {
                                "type": "object",
                                "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                                "properties": {
                                  "relation": {
                                    "type": "string",
                                    "enum": [
                                      "within",
                                      "before",
                                      "after",
                                      "ever",
                                      "current"
                                    ]
                                  },
                                  "amount": {
                                    "type": [
                                      "integer",
                                      "null"
                                    ]
                                  },
                                  "unit": {
                                    "anyOf": [
                                      {
                                        "type": "string",
                                        "enum": [
                                          "days",
                                          "weeks",
                                          "months",
                                          "years"
                                        ]
                                      },
                                      {
                                        "type": "null"
                                      }
                                    ]
                                  },
                                  "anchor": {
                                    "type": "string",
                                    "enum": [
                                      "screening",
                                      "enrolment",
                                      "randomisation",
                                      "consent",
                                      "first_dose"
                                    ]
                                  }
                                },
                                "required": [
                                  "relation",
                                  "amount",
                                  "unit",
                                  "anchor"
                                ],
                                "additionalProperties": false
                              },
                              {
                                "type": "null"
                              }
                            ]
                          }
                        },
                        "required": [
                          "type",
                          "concept",
                          "op",
                          "value",
                          "value_high",
                          "unit",
                          "window"
                        ],
                        "additionalProperties": false
                      },
                      {
                        "type": "object",
                        "description": "Whether a coded thing is on the chart at all: a condition, a drug, a procedure.",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "condition",
                              "medication",
                              "procedure"
                            ]
                          },
                          "concept": {
                            "type": "object",
                            "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                            "properties": {
                              "text": {
                                "type": "string"
                              },
                              "codes": {
                                "type": "array",
                                "items": {
                                  "type": "object",
                                  "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                                  "properties": {
                                    "system": {
                                      "type": "string",
                                      "enum": [
                                        "LOINC",
                                        "SNOMED",
                                        "RxNorm",
                                        "ICD10",
                                        "UCUM"
                                      ]
                                    },
                                    "code": {
                                      "type": "string"
                                    },
                                    "display": {
                                      "type": [
                                        "string",
                                        "null"
                                      ]
                                    }
                                  },
                                  "required": [
                                    "system",
                                    "code",
                                    "display"
                                  ],
                                  "additionalProperties": false
                                }
                              }
                            },
                            "required": [
                              "text",
                              "codes"
                            ],
                            "additionalProperties": false
                          },
                          "presence": {
                            "type": "string",
                            "enum": [
                              "present",
                              "absent"
                            ]
                          },
                          "window": {
                            "anyOf": [
                              {
                                "type": "object",
                                "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                                "properties": {
                                  "relation": {
                                    "type": "string",
                                    "enum": [
                                      "within",
                                      "before",
                                      "after",
                                      "ever",
                                      "current"
                                    ]
                                  },
                                  "amount": {
                                    "type": [
                                      "integer",
                                      "null"
                                    ]
                                  },
                                  "unit": {
                                    "anyOf": [
                                      {
                                        "type": "string",
                                        "enum": [
                                          "days",
                                          "weeks",
                                          "months",
                                          "years"
                                        ]
                                      },
                                      {
                                        "type": "null"
                                      }
                                    ]
                                  },
                                  "anchor": {
                                    "type": "string",
                                    "enum": [
                                      "screening",
                                      "enrolment",
                                      "randomisation",
                                      "consent",
                                      "first_dose"
                                    ]
                                  }
                                },
                                "required": [
                                  "relation",
                                  "amount",
                                  "unit",
                                  "anchor"
                                ],
                                "additionalProperties": false
                              },
                              {
                                "type": "null"
                              }
                            ]
                          }
                        },
                        "required": [
                          "type",
                          "concept",
                          "presence",
                          "window"
                        ],
                        "additionalProperties": false
                      },
                      {
                        "type": "object",
                        "description": "Age and sex, which come from the patient resource rather than from clinical events.",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "demographic"
                            ]
                          },
                          "field": {
                            "type": "string",
                            "enum": [
                              "age",
                              "sex"
                            ]
                          },
                          "op": {
                            "type": "string",
                            "enum": [
                              "<",
                              "<=",
                              ">",
                              ">=",
                              "==",
                              "!="
                            ]
                          },
                          "value": {
                            "type": [
                              "number",
                              "string"
                            ]
                          },
                          "unit": {
                            "type": [
                              "string",
                              "null"
                            ]
                          }
                        },
                        "required": [
                          "type",
                          "field",
                          "op",
                          "value",
                          "unit"
                        ],
                        "additionalProperties": false
                      },
                      {
                        "type": "object",
                        "description": "A criterion that cannot be honestly formalised. It stays unresolved forever, by design.\n\n`settlement` says *why* no chart can answer it, and the difference is load-bearing.\n\nA criterion settled `from_data` was a question about the patient's record that we failed to\nformalise \u2014 a threshold with no number, an open category. It is a gap, and it blocks a verdict.\n\nA criterion settled `at_visit` is not a gap at all. Signed informed consent, a procedure planned\nafter randomisation, the investigator's own judgement of the patient in person: these have the\nsame answer for every chart ever written, because they are settled when the patient comes in.\nTreating them as unresolved data made ELIGIBLE unreachable for every real protocol we hold \u2014 one\nconsent criterion and the screening abstains, which is not caution but paralysis.\n\nThe default is `from_data`, so a compiler that says nothing cannot thereby unblock a verdict.",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "unsupported"
                            ]
                          },
                          "reason": {
                            "type": "string"
                          },
                          "settlement": {
                            "type": "string",
                            "enum": [
                              "from_data",
                              "at_visit"
                            ]
                          }
                        },
                        "required": [
                          "type",
                          "reason",
                          "settlement"
                        ],
                        "additionalProperties": false
                      },
                      {
                        "type": "object",
                        "properties": {
                          "type": {
                            "type": "string",
                            "enum": [
                              "all_of",
                              "any_of",
                              "not"
                            ]
                          },
                          "operands": {
                            "type": "array",
                            "items": {
                              "anyOf": [
                                {
                                  "type": "object",
                                  "description": "A numeric comparison against a measurement: labs, vitals, scores.",
                                  "properties": {
                                    "type": {
                                      "type": "string",
                                      "enum": [
                                        "observation"
                                      ]
                                    },
                                    "concept": {
                                      "type": "object",
                                      "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                                      "properties": {
                                        "text": {
                                          "type": "string"
                                        },
                                        "codes": {
                                          "type": "array",
                                          "items": {
                                            "type": "object",
                                            "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                                            "properties": {
                                              "system": {
                                                "type": "string",
                                                "enum": [
                                                  "LOINC",
                                                  "SNOMED",
                                                  "RxNorm",
                                                  "ICD10",
                                                  "UCUM"
                                                ]
                                              },
                                              "code": {
                                                "type": "string"
                                              },
                                              "display": {
                                                "type": [
                                                  "string",
                                                  "null"
                                                ]
                                              }
                                            },
                                            "required": [
                                              "system",
                                              "code",
                                              "display"
                                            ],
                                            "additionalProperties": false
                                          }
                                        }
                                      },
                                      "required": [
                                        "text",
                                        "codes"
                                      ],
                                      "additionalProperties": false
                                    },
                                    "op": {
                                      "type": "string",
                                      "enum": [
                                        "<",
                                        "<=",
                                        ">",
                                        ">=",
                                        "==",
                                        "!=",
                                        "between"
                                      ]
                                    },
                                    "value": {
                                      "type": "number"
                                    },
                                    "value_high": {
                                      "type": [
                                        "number",
                                        "null"
                                      ]
                                    },
                                    "unit": {
                                      "type": "string"
                                    },
                                    "window": {
                                      "anyOf": [
                                        {
                                          "type": "object",
                                          "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                                          "properties": {
                                            "relation": {
                                              "type": "string",
                                              "enum": [
                                                "within",
                                                "before",
                                                "after",
                                                "ever",
                                                "current"
                                              ]
                                            },
                                            "amount": {
                                              "type": [
                                                "integer",
                                                "null"
                                              ]
                                            },
                                            "unit": {
                                              "anyOf": [
                                                {
                                                  "type": "string",
                                                  "enum": [
                                                    "days",
                                                    "weeks",
                                                    "months",
                                                    "years"
                                                  ]
                                                },
                                                {
                                                  "type": "null"
                                                }
                                              ]
                                            },
                                            "anchor": {
                                              "type": "string",
                                              "enum": [
                                                "screening",
                                                "enrolment",
                                                "randomisation",
                                                "consent",
                                                "first_dose"
                                              ]
                                            }
                                          },
                                          "required": [
                                            "relation",
                                            "amount",
                                            "unit",
                                            "anchor"
                                          ],
                                          "additionalProperties": false
                                        },
                                        {
                                          "type": "null"
                                        }
                                      ]
                                    }
                                  },
                                  "required": [
                                    "type",
                                    "concept",
                                    "op",
                                    "value",
                                    "value_high",
                                    "unit",
                                    "window"
                                  ],
                                  "additionalProperties": false
                                },
                                {
                                  "type": "object",
                                  "description": "Whether a coded thing is on the chart at all: a condition, a drug, a procedure.",
                                  "properties": {
                                    "type": {
                                      "type": "string",
                                      "enum": [
                                        "condition",
                                        "medication",
                                        "procedure"
                                      ]
                                    },
                                    "concept": {
                                      "type": "object",
                                      "description": "A clinical concept as the protocol names it, plus whatever codes we resolved it to.",
                                      "properties": {
                                        "text": {
                                          "type": "string"
                                        },
                                        "codes": {
                                          "type": "array",
                                          "items": {
                                            "type": "object",
                                            "description": "A terminology code. `system` is kept as a short name rather than a URI for legibility.",
                                            "properties": {
                                              "system": {
                                                "type": "string",
                                                "enum": [
                                                  "LOINC",
                                                  "SNOMED",
                                                  "RxNorm",
                                                  "ICD10",
                                                  "UCUM"
                                                ]
                                              },
                                              "code": {
                                                "type": "string"
                                              },
                                              "display": {
                                                "type": [
                                                  "string",
                                                  "null"
                                                ]
                                              }
                                            },
                                            "required": [
                                              "system",
                                              "code",
                                              "display"
                                            ],
                                            "additionalProperties": false
                                          }
                                        }
                                      },
                                      "required": [
                                        "text",
                                        "codes"
                                      ],
                                      "additionalProperties": false
                                    },
                                    "presence": {
                                      "type": "string",
                                      "enum": [
                                        "present",
                                        "absent"
                                      ]
                                    },
                                    "window": {
                                      "anyOf": [
                                        {
                                          "type": "object",
                                          "description": "When the evidence has to have happened, and relative to what.\n\nProtocols anchor windows to screening, enrolment, randomisation, consent or first dose, and\nthose are genuinely different dates \u2014 sometimes weeks apart. Caliper evaluates every window\nagainst the screening date because that is the only date it has, so the anchor is recorded\nrather than discarded: a criterion evaluated against the wrong anchor is reported as an\napproximation instead of passing silently.",
                                          "properties": {
                                            "relation": {
                                              "type": "string",
                                              "enum": [
                                                "within",
                                                "before",
                                                "after",
                                                "ever",
                                                "current"
                                              ]
                                            },
                                            "amount": {
                                              "type": [
                                                "integer",
                                                "null"
                                              ]
                                            },
                                            "unit": {
                                              "anyOf": [
                                                {
                                                  "type": "string",
                                                  "enum": [
                                                    "days",
                                                    "weeks",
                                                    "months",
                                                    "years"
                                                  ]
                                                },
                                                {
                                                  "type": "null"
                                                }
                                              ]
                                            },
                                            "anchor": {
                                              "type": "string",
                                              "enum": [
                                                "screening",
                                                "enrolment",
                                                "randomisation",
                                                "consent",
                                                "first_dose"
                                              ]
                                            }
                                          },
                                          "required": [
                                            "relation",
                                            "amount",
                                            "unit",
                                            "anchor"
                                          ],
                                          "additionalProperties": false
                                        },
                                        {
                                          "type": "null"
                                        }
                                      ]
                                    }
                                  },
                                  "required": [
                                    "type",
                                    "concept",
                                    "presence",
                                    "window"
                                  ],
                                  "additionalProperties": false
                                },
                                {
                                  "type": "object",
                                  "description": "Age and sex, which come from the patient resource rather than from clinical events.",
                                  "properties": {
                                    "type": {
                                      "type": "string",
                                      "enum": [
                                        "demographic"
                                      ]
                                    },
                                    "field": {
                                      "type": "string",
                                      "enum": [
                                        "age",
                                        "sex"
                                      ]
                                    },
                                    "op": {
                                      "type": "string",
                                      "enum": [
                                        "<",
                                        "<=",
                                        ">",
                                        ">=",
                                        "==",
                                        "!="
                                      ]
                                    },
                                    "value": {
                                      "type": [
                                        "number",
                                        "string"
                                      ]
                                    },
                                    "unit": {
                                      "type": [
                                        "string",
                                        "null"
                                      ]
                                    }
                                  },
                                  "required": [
                                    "type",
                                    "field",
                                    "op",
                                    "value",
                                    "unit"
                                  ],
                                  "additionalProperties": false
                                },
                                {
                                  "type": "object",
                                  "description": "A criterion that cannot be honestly formalised. It stays unresolved forever, by design.\n\n`settlement` says *why* no chart can answer it, and the difference is load-bearing.\n\nA criterion settled `from_data` was a question about the patient's record that we failed to\nformalise \u2014 a threshold with no number, an open category. It is a gap, and it blocks a verdict.\n\nA criterion settled `at_visit` is not a gap at all. Signed informed consent, a procedure planned\nafter randomisation, the investigator's own judgement of the patient in person: these have the\nsame answer for every chart ever written, because they are settled when the patient comes in.\nTreating them as unresolved data made ELIGIBLE unreachable for every real protocol we hold \u2014 one\nconsent criterion and the screening abstains, which is not caution but paralysis.\n\nThe default is `from_data`, so a compiler that says nothing cannot thereby unblock a verdict.",
                                  "properties": {
                                    "type": {
                                      "type": "string",
                                      "enum": [
                                        "unsupported"
                                      ]
                                    },
                                    "reason": {
                                      "type": "string"
                                    },
                                    "settlement": {
                                      "type": "string",
                                      "enum": [
                                        "from_data",
                                        "at_visit"
                                      ]
                                    }
                                  },
                                  "required": [
                                    "type",
                                    "reason",
                                    "settlement"
                                  ],
                                  "additionalProperties": false
                                }
                              ]
                            }
                          }
                        },
                        "required": [
                          "type",
                          "operands"
                        ],
                        "additionalProperties": false
                      }
                    ]
                  }
                }
              },
              "required": [
                "type",
                "operands"
              ],
              "additionalProperties": false
            }
          ]
        },
        {
          "type": "null"
        }
      ]
    },
    "notes": {
      "type": [
        "string",
        "null"
      ],
      "description": "Why this span was hard, or why it is not a criterion."
    }
  },
  "required": [
    "is_criterion",
    "kind",
    "source_quote",
    "predicate",
    "notes"
  ],
  "additionalProperties": false
}

[user]
Section: exclusion

Criterion:
Planning to start a sodium-glucose linked transporter-2 (SGLT2) inhibitor during the study.
```

Response:

```
{"is_criterion": true, "kind": "exclusion", "source_quote": "Planning to start a sodium-glucose linked transporter-2 (SGLT2) inhibitor during the study.", "predicate": {"type": "unsupported", "reason": "Future intent to start a medication during the study is a planned future state, not a recorded fact; it is settled at the screening visit and would be answered the same way regardless of chart contents.", "settlement": "at_visit"}, "notes": "Analogous to the worked example 'Planning to start an SGLT2 inhibitor during the study.'"}
```

Validated against the schema.

### Result

```json
{
  "is_criterion": true,
  "kind": "exclusion",
  "source_quote": "Planning to start a sodium-glucose linked transporter-2 (SGLT2) inhibitor during the study.",
  "predicate": {
    "type": "unsupported",
    "reason": "Future intent to start a medication during the study is a planned future state, not a recorded fact; it is settled at the screening visit and would be answered the same way regardless of chart contents.",
    "settlement": "at_visit"
  },
  "notes": "Analogous to the worked example 'Planning to start an SGLT2 inhibitor during the study.'"
}
```

## 9. resolver on venice/claude-sonnet-5

- **Started:** 2026-08-30T10:35:10Z
- **Tier used:** `memory`
- **Retries:** 0
- **Tokens:** 0 in / 0 out
- **Estimated cost:** unpriced
- **Outcome:** validated

### Instructions

```
Concept resolution summary. No request was sent for this step.
```

### Request

```
Resolved 3 distinct concept(s) for NCT03315143.
  memory: type 2 diabetes mellitus
  memory: glycosylated hemoglobin (hba1c)
  memory: estimated glomerular filtration rate (egfr)
```

### Attempt 1, tier `memory`

Response:

```
{
  "nct_id": "NCT03315143",
  "concepts": 3,
  "memory_hits": [
    "type 2 diabetes mellitus",
    "glycosylated hemoglobin (hba1c)",
    "estimated glomerular filtration rate (egfr)"
  ],
  "model_calls": [],
  "resolved_without_codes": [],
  "model_failures": [],
  "low_confidence_dropped": 0,
  "malformed_codes_dropped": 0,
  "memory": {
    "entries": 128,
    "hits": 3,
    "misses": 0,
    "lookups": 3,
    "hit_rate": 1.0,
    "consistency_violations": 0
  }
}
```

Validated against the schema.

### Result

```json
{
  "nct_id": "NCT03315143",
  "concepts": 3,
  "memory_hits": [
    "type 2 diabetes mellitus",
    "glycosylated hemoglobin (hba1c)",
    "estimated glomerular filtration rate (egfr)"
  ],
  "model_calls": [],
  "resolved_without_codes": [],
  "model_failures": [],
  "low_confidence_dropped": 0,
  "malformed_codes_dropped": 0,
  "memory": {
    "entries": 128,
    "hits": 3,
    "misses": 0,
    "lookups": 3,
    "hit_rate": 1.0,
    "consistency_violations": 0
  }
}
```

## 10. critic on venice/claude-sonnet-5

- **Started:** 2026-08-30T10:35:10Z
- **Tier used:** `json_schema`
- **Retries:** 0
- **Tokens:** 2818 in / 97 out
- **Estimated cost:** $0.0066
- **Outcome:** validated

### Instructions

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

## 11. critic on venice/claude-sonnet-5

- **Started:** 2026-08-30T10:35:10Z
- **Tier used:** `json_schema`
- **Retries:** 0
- **Tokens:** 2829 in / 60 out
- **Estimated cost:** $0.0063
- **Outcome:** validated

### Instructions

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

## 12. extractor on venice/claude-sonnet-5

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

## 13. extractor on venice/claude-sonnet-5

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

## 14. extractor on venice/claude-sonnet-5

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

## 15. extractor on venice/claude-sonnet-5

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

## 16. writer on venice/claude-sonnet-5

- **Started:** 2026-08-30T10:35:10Z
- **Tier used:** `json_schema`
- **Retries:** 0
- **Tokens:** 1936 in / 71 out
- **Estimated cost:** $0.0046
- **Outcome:** validated

### Instructions

```
# Rationale writing

You write one sentence at a time. Each one goes into a screening packet that a research
coordinator reads and signs, printed beside a criterion from a trial protocol and the evidence a
screening engine found in one patient's chart.

The verdict is already decided, deterministically, before you are asked. You are not reviewing it
and you are not being asked whether you agree. Your job is to say, in plain clinical English, what
the record shows and how it stands against the criterion.

## What you are given

- the criterion as the protocol wrote it, word for word;
- the verdict: met, not met, or unresolved;
- the engine's own rationale — correct, and written like a machine wrote it;
- every piece of evidence the verdict rests on, with its value, its unit and the date it was
  recorded.

That material is all you have and all you may use. You have no access to the chart, to reference
ranges, to the protocol beyond the quoted criterion, or to anything you happen to know about this
disease.

## What a good sentence looks like

> Creatinine was 1.2 mg/dL on 2026-05-14, inside the 1.5 mg/dL ceiling this criterion sets.

> No haemoglobin A1c result is on file for the window this criterion requires.

> Metformin is on the current medication list, which this exclusion criterion rules out.

One sentence. Name the finding, give the value and the date the record gives, and say how that
stands against the criterion. Past tense for what the chart recorded, present tense for what the
criterion requires. A coordinator should be able to read it and know whether they need to open the
chart.

Around twenty-five words is right. Forty is too long.

## Every number comes from the evidence

Each number and each date you write is checked mechanically against the values this criterion
resolved from: its threshold, its window, and the evidence rows you were shown. A sentence
carrying anything else is rejected and never reaches the packet.

- Copy values, units and dates exactly as they are given to you. Do not round, do not convert
  units, and do not restate a value "for clarity" in a form nobody wrote down.
- Do not calculate. No differences from a threshold, no percentages, no headroom, no averages.
- Do not count in digits. "Neither result is on file" is fine; "0 of 2 results" is not.
- Do not import a number from anywhere else: a normal range, a guideline cut-off, a value from
  another criterion, a today's date.
- Write a date in the form you were given it — `2026-05-14` — or refer to it without digits at
  all, as "the most recent result". A date rewritten as "14 May 2026" reads as two loose numbers
  and is rejected.

A sentence with no numbers in it is always safe, and is often the best sentence available.

## Hedging is not a way of abstaining

"Appears to be", "likely", "approximately", "suggests", "may indicate" — these decide nothing, and
to a coordinator they read as doubt about a verdict that is not in doubt. If the record supports
the statement, make it plainly. If it does not, say what is missing instead. There is no third
option where you make a claim and quietly disown it.

## "No result is on file" is a complete and correct sentence

An unresolved criterion is a normal outcome, not a failure to be smoothed over. Say what is
absent and leave it there.

Two mistakes to avoid specifically:

- Never invent a plausible value for a result that is not on file. A number that looks right is
  worse than no number, because it will be read as a measurement.
- Never write that a patient does not have a condition when what the record shows is that nobody
  wrote it down. "No myocardial infarction is documented in the chart" is true. "The patient has
  no history of myocardial infarction" is a clinical claim the record has not made.

## Voice

Write the way a clinician writes in a chart: specific, unhurried, no adjective doing rhetorical
work. No "importantly", "notably", "it is worth noting". Do not address the reader, do not
recommend anything, and do not tell anyone what to do next — the packet has a section for that,
and eligibility is the investigator's decision, not yours.

Do not repeat the criterion back verbatim. The packet prints it directly above your sentence.

## Format

Return one sentence in the `sentence` field: one terminal full stop, no line breaks, no lists, no
markdown, no bracketed citations, no resource identifiers.

```

### Request

```
Criterion INC-01, an inclusion criterion.

The protocol says, word for word:
Type 2 Diabetes Mellitus with glycosylated hemoglobin (HbA1c) ≥7%.

The screening engine found this criterion not met, because:
Type 2 Diabetes Mellitus is not documented in a window the chart covers and 6.02 % on 2025-09-24 against >= 7.0 %

Evidence the verdict rests on:
  - Hemoglobin A1c/Hemoglobin.total in Blood, 6.02 %, recorded 2025-09-24

Write the sentence a coordinator will read beside this criterion.
```

### Attempt 1, tier `json_schema`

Response:

```
{"sentence":"HbA1c was 6.02 % on 2025-09-24, below the 7% threshold this criterion requires, and Type 2 Diabetes Mellitus is not documented in the chart."}
```

Validated against the schema.

### Result

```json
{
  "sentence": "HbA1c was 6.02 % on 2025-09-24, below the 7% threshold this criterion requires, and Type 2 Diabetes Mellitus is not documented in the chart."
}
```

## 17. writer on venice/claude-sonnet-5

- **Started:** 2026-08-30T10:35:10Z
- **Tier used:** `prose_check`
- **Retries:** 0
- **Tokens:** 0 in / 0 out
- **Estimated cost:** unpriced
- **Outcome:** validated

### Instructions

```
Prose check on one rationale sentence. No request was sent.
```

### Request

```
INC-01: the model's sentence was accepted as written.
```

### Attempt 1, tier `prose_check`

Response:

```
{
  "criterion_id": "INC-01",
  "verdict": "not_met",
  "source": "model",
  "sentence": "HbA1c was 6.02 % on 2025-09-24, below the 7% threshold this criterion requires, and Type 2 Diabetes Mellitus is not documented in the chart.",
  "rejected": [],
  "violations": [],
  "fallback_reason": null
}
```

Validated against the schema.

### Result

```json
{
  "criterion_id": "INC-01",
  "verdict": "not_met",
  "source": "model",
  "sentence": "HbA1c was 6.02 % on 2025-09-24, below the 7% threshold this criterion requires, and Type 2 Diabetes Mellitus is not documented in the chart.",
  "rejected": [],
  "violations": [],
  "fallback_reason": null
}
```

## 18. writer on venice/claude-sonnet-5

- **Started:** 2026-08-30T10:35:10Z
- **Tier used:** `json_schema`
- **Retries:** 0
- **Tokens:** 2063 in / 81 out
- **Estimated cost:** $0.0049
- **Outcome:** validated

### Instructions

```
# Rationale writing

You write one sentence at a time. Each one goes into a screening packet that a research
coordinator reads and signs, printed beside a criterion from a trial protocol and the evidence a
screening engine found in one patient's chart.

The verdict is already decided, deterministically, before you are asked. You are not reviewing it
and you are not being asked whether you agree. Your job is to say, in plain clinical English, what
the record shows and how it stands against the criterion.

## What you are given

- the criterion as the protocol wrote it, word for word;
- the verdict: met, not met, or unresolved;
- the engine's own rationale — correct, and written like a machine wrote it;
- every piece of evidence the verdict rests on, with its value, its unit and the date it was
  recorded.

That material is all you have and all you may use. You have no access to the chart, to reference
ranges, to the protocol beyond the quoted criterion, or to anything you happen to know about this
disease.

## What a good sentence looks like

> Creatinine was 1.2 mg/dL on 2026-05-14, inside the 1.5 mg/dL ceiling this criterion sets.

> No haemoglobin A1c result is on file for the window this criterion requires.

> Metformin is on the current medication list, which this exclusion criterion rules out.

One sentence. Name the finding, give the value and the date the record gives, and say how that
stands against the criterion. Past tense for what the chart recorded, present tense for what the
criterion requires. A coordinator should be able to read it and know whether they need to open the
chart.

Around twenty-five words is right. Forty is too long.

## Every number comes from the evidence

Each number and each date you write is checked mechanically against the values this criterion
resolved from: its threshold, its window, and the evidence rows you were shown. A sentence
carrying anything else is rejected and never reaches the packet.

- Copy values, units and dates exactly as they are given to you. Do not round, do not convert
  units, and do not restate a value "for clarity" in a form nobody wrote down.
- Do not calculate. No differences from a threshold, no percentages, no headroom, no averages.
- Do not count in digits. "Neither result is on file" is fine; "0 of 2 results" is not.
- Do not import a number from anywhere else: a normal range, a guideline cut-off, a value from
  another criterion, a today's date.
- Write a date in the form you were given it — `2026-05-14` — or refer to it without digits at
  all, as "the most recent result". A date rewritten as "14 May 2026" reads as two loose numbers
  and is rejected.

A sentence with no numbers in it is always safe, and is often the best sentence available.

## Hedging is not a way of abstaining

"Appears to be", "likely", "approximately", "suggests", "may indicate" — these decide nothing, and
to a coordinator they read as doubt about a verdict that is not in doubt. If the record supports
the statement, make it plainly. If it does not, say what is missing instead. There is no third
option where you make a claim and quietly disown it.

## "No result is on file" is a complete and correct sentence

An unresolved criterion is a normal outcome, not a failure to be smoothed over. Say what is
absent and leave it there.

Two mistakes to avoid specifically:

- Never invent a plausible value for a result that is not on file. A number that looks right is
  worse than no number, because it will be read as a measurement.
- Never write that a patient does not have a condition when what the record shows is that nobody
  wrote it down. "No myocardial infarction is documented in the chart" is true. "The patient has
  no history of myocardial infarction" is a clinical claim the record has not made.

## Voice

Write the way a clinician writes in a chart: specific, unhurried, no adjective doing rhetorical
work. No "importantly", "notably", "it is worth noting". Do not address the reader, do not
recommend anything, and do not tell anyone what to do next — the packet has a section for that,
and eligibility is the investigator's decision, not yours.

Do not repeat the criterion back verbatim. The packet prints it directly above your sentence.

## Format

Return one sentence in the `sentence` field: one terminal full stop, no line breaks, no lists, no
markdown, no bracketed citations, no resource identifiers.

```

### Request

```
Criterion INC-02, an inclusion criterion.

The protocol says, word for word:
Estimated glomerular filtration rate (eGFR) ≥25 and ≤60 milliliter/minute (mL/min)/1.73 square meter (m^2).

The screening engine found this criterion unresolved, because:
cannot convert mL/min to mL/min/1.73m^2 for this analyte

Evidence the verdict rests on:
  - Glomerular filtration rate [Volume Rate/Area] in Serum or Plasma by Creatinine-based formula (MDRD)/1.73 sq M, 84.289 mL/min, recorded 2025-09-25

Nothing in the record settles this criterion. What is missing: Estimated glomerular filtration rate (eGFR) in mL/min/1.73m^2 (the chart reports mL/min, which we cannot convert).
A coordinator would go looking in the laboratory result system or the most recent panel in the chart.

Write the sentence a coordinator will read beside this criterion.
```

### Attempt 1, tier `json_schema`

Response:

```
{"sentence":"An eGFR value of 84.289 mL/min was recorded on 2025-09-25, but this cannot be converted to the mL/min/1.73m^2 units this criterion requires, leaving the criterion unresolved."}
```

Validated against the schema.

### Result

```json
{
  "sentence": "An eGFR value of 84.289 mL/min was recorded on 2025-09-25, but this cannot be converted to the mL/min/1.73m^2 units this criterion requires, leaving the criterion unresolved."
}
```

## 19. writer on venice/claude-sonnet-5

- **Started:** 2026-08-30T10:35:10Z
- **Tier used:** `prose_check`
- **Retries:** 0
- **Tokens:** 0 in / 0 out
- **Estimated cost:** unpriced
- **Outcome:** validated

### Instructions

```
Prose check on one rationale sentence. No request was sent.
```

### Request

```
INC-02: the model's sentence was accepted as written.
```

### Attempt 1, tier `prose_check`

Response:

```
{
  "criterion_id": "INC-02",
  "verdict": "unknown",
  "source": "model",
  "sentence": "An eGFR value of 84.289 mL/min was recorded on 2025-09-25, but this cannot be converted to the mL/min/1.73m^2 units this criterion requires, leaving the criterion unresolved.",
  "rejected": [],
  "violations": [],
  "fallback_reason": null
}
```

Validated against the schema.

### Result

```json
{
  "criterion_id": "INC-02",
  "verdict": "unknown",
  "source": "model",
  "sentence": "An eGFR value of 84.289 mL/min was recorded on 2025-09-25, but this cannot be converted to the mL/min/1.73m^2 units this criterion requires, leaving the criterion unresolved.",
  "rejected": [],
  "violations": [],
  "fallback_reason": null
}
```

## 20. writer on venice/claude-sonnet-5

- **Started:** 2026-08-30T10:35:10Z
- **Tier used:** `json_schema`
- **Retries:** 0
- **Tokens:** 2011 in / 64 out
- **Estimated cost:** $0.0047
- **Outcome:** validated

### Instructions

```
# Rationale writing

You write one sentence at a time. Each one goes into a screening packet that a research
coordinator reads and signs, printed beside a criterion from a trial protocol and the evidence a
screening engine found in one patient's chart.

The verdict is already decided, deterministically, before you are asked. You are not reviewing it
and you are not being asked whether you agree. Your job is to say, in plain clinical English, what
the record shows and how it stands against the criterion.

## What you are given

- the criterion as the protocol wrote it, word for word;
- the verdict: met, not met, or unresolved;
- the engine's own rationale — correct, and written like a machine wrote it;
- every piece of evidence the verdict rests on, with its value, its unit and the date it was
  recorded.

That material is all you have and all you may use. You have no access to the chart, to reference
ranges, to the protocol beyond the quoted criterion, or to anything you happen to know about this
disease.

## What a good sentence looks like

> Creatinine was 1.2 mg/dL on 2026-05-14, inside the 1.5 mg/dL ceiling this criterion sets.

> No haemoglobin A1c result is on file for the window this criterion requires.

> Metformin is on the current medication list, which this exclusion criterion rules out.

One sentence. Name the finding, give the value and the date the record gives, and say how that
stands against the criterion. Past tense for what the chart recorded, present tense for what the
criterion requires. A coordinator should be able to read it and know whether they need to open the
chart.

Around twenty-five words is right. Forty is too long.

## Every number comes from the evidence

Each number and each date you write is checked mechanically against the values this criterion
resolved from: its threshold, its window, and the evidence rows you were shown. A sentence
carrying anything else is rejected and never reaches the packet.

- Copy values, units and dates exactly as they are given to you. Do not round, do not convert
  units, and do not restate a value "for clarity" in a form nobody wrote down.
- Do not calculate. No differences from a threshold, no percentages, no headroom, no averages.
- Do not count in digits. "Neither result is on file" is fine; "0 of 2 results" is not.
- Do not import a number from anywhere else: a normal range, a guideline cut-off, a value from
  another criterion, a today's date.
- Write a date in the form you were given it — `2026-05-14` — or refer to it without digits at
  all, as "the most recent result". A date rewritten as "14 May 2026" reads as two loose numbers
  and is rejected.

A sentence with no numbers in it is always safe, and is often the best sentence available.

## Hedging is not a way of abstaining

"Appears to be", "likely", "approximately", "suggests", "may indicate" — these decide nothing, and
to a coordinator they read as doubt about a verdict that is not in doubt. If the record supports
the statement, make it plainly. If it does not, say what is missing instead. There is no third
option where you make a claim and quietly disown it.

## "No result is on file" is a complete and correct sentence

An unresolved criterion is a normal outcome, not a failure to be smoothed over. Say what is
absent and leave it there.

Two mistakes to avoid specifically:

- Never invent a plausible value for a result that is not on file. A number that looks right is
  worse than no number, because it will be read as a measurement.
- Never write that a patient does not have a condition when what the record shows is that nobody
  wrote it down. "No myocardial infarction is documented in the chart" is true. "The patient has
  no history of myocardial infarction" is a clinical claim the record has not made.

## Voice

Write the way a clinician writes in a chart: specific, unhurried, no adjective doing rhetorical
work. No "importantly", "notably", "it is worth noting". Do not address the reader, do not
recommend anything, and do not tell anyone what to do next — the packet has a section for that,
and eligibility is the investigator's decision, not yours.

Do not repeat the criterion back verbatim. The packet prints it directly above your sentence.

## Format

Return one sentence in the `sentence` field: one terminal full stop, no line breaks, no lists, no
markdown, no bracketed citations, no resource identifiers.

```

### Request

```
Criterion INC-03, an inclusion criterion.

The protocol says, word for word:
Age 18 years or older with at least one major cardiovascular risk factor or age 55 years or older with at least two minor cardiovascular risk factors.

The screening engine found this criterion unresolved, because:
this criterion was not formalised because it cannot be decided from data

Evidence the verdict rests on:
  nothing on file

Nothing in the record settles this criterion. What is missing: human judgement: The criterion turns on membership in 'major' and 'minor' cardiovascular risk factor categories, which this span does not enumerate. Without the protocol's defined list of qualifying risk factors, no single code or small set of codes can capture the category, so counting them cannot be formalised..
A coordinator would go looking in the protocol and the investigator.

Write the sentence a coordinator will read beside this criterion.
```

### Attempt 1, tier `json_schema`

Response:

```
{"sentence":"No evidence is on file for age or cardiovascular risk factor status, and the protocol's lists of qualifying major and minor risk factors are not available to determine this criterion."}
```

Validated against the schema.

### Result

```json
{
  "sentence": "No evidence is on file for age or cardiovascular risk factor status, and the protocol's lists of qualifying major and minor risk factors are not available to determine this criterion."
}
```

## 21. writer on venice/claude-sonnet-5

- **Started:** 2026-08-30T10:35:10Z
- **Tier used:** `prose_check`
- **Retries:** 0
- **Tokens:** 0 in / 0 out
- **Estimated cost:** unpriced
- **Outcome:** validated

### Instructions

```
Prose check on one rationale sentence. No request was sent.
```

### Request

```
INC-03: the model's sentence was accepted as written.
```

### Attempt 1, tier `prose_check`

Response:

```
{
  "criterion_id": "INC-03",
  "verdict": "unknown",
  "source": "model",
  "sentence": "No evidence is on file for age or cardiovascular risk factor status, and the protocol's lists of qualifying major and minor risk factors are not available to determine this criterion.",
  "rejected": [],
  "violations": [],
  "fallback_reason": null
}
```

Validated against the schema.

### Result

```json
{
  "criterion_id": "INC-03",
  "verdict": "unknown",
  "source": "model",
  "sentence": "No evidence is on file for age or cardiovascular risk factor status, and the protocol's lists of qualifying major and minor risk factors are not available to determine this criterion.",
  "rejected": [],
  "violations": [],
  "fallback_reason": null
}
```

## 22. writer on venice/claude-sonnet-5

- **Started:** 2026-08-30T10:35:10Z
- **Tier used:** `json_schema`
- **Retries:** 0
- **Tokens:** 1928 in / 55 out
- **Estimated cost:** $0.0044
- **Outcome:** validated

### Instructions

```
# Rationale writing

You write one sentence at a time. Each one goes into a screening packet that a research
coordinator reads and signs, printed beside a criterion from a trial protocol and the evidence a
screening engine found in one patient's chart.

The verdict is already decided, deterministically, before you are asked. You are not reviewing it
and you are not being asked whether you agree. Your job is to say, in plain clinical English, what
the record shows and how it stands against the criterion.

## What you are given

- the criterion as the protocol wrote it, word for word;
- the verdict: met, not met, or unresolved;
- the engine's own rationale — correct, and written like a machine wrote it;
- every piece of evidence the verdict rests on, with its value, its unit and the date it was
  recorded.

That material is all you have and all you may use. You have no access to the chart, to reference
ranges, to the protocol beyond the quoted criterion, or to anything you happen to know about this
disease.

## What a good sentence looks like

> Creatinine was 1.2 mg/dL on 2026-05-14, inside the 1.5 mg/dL ceiling this criterion sets.

> No haemoglobin A1c result is on file for the window this criterion requires.

> Metformin is on the current medication list, which this exclusion criterion rules out.

One sentence. Name the finding, give the value and the date the record gives, and say how that
stands against the criterion. Past tense for what the chart recorded, present tense for what the
criterion requires. A coordinator should be able to read it and know whether they need to open the
chart.

Around twenty-five words is right. Forty is too long.

## Every number comes from the evidence

Each number and each date you write is checked mechanically against the values this criterion
resolved from: its threshold, its window, and the evidence rows you were shown. A sentence
carrying anything else is rejected and never reaches the packet.

- Copy values, units and dates exactly as they are given to you. Do not round, do not convert
  units, and do not restate a value "for clarity" in a form nobody wrote down.
- Do not calculate. No differences from a threshold, no percentages, no headroom, no averages.
- Do not count in digits. "Neither result is on file" is fine; "0 of 2 results" is not.
- Do not import a number from anywhere else: a normal range, a guideline cut-off, a value from
  another criterion, a today's date.
- Write a date in the form you were given it — `2026-05-14` — or refer to it without digits at
  all, as "the most recent result". A date rewritten as "14 May 2026" reads as two loose numbers
  and is rejected.

A sentence with no numbers in it is always safe, and is often the best sentence available.

## Hedging is not a way of abstaining

"Appears to be", "likely", "approximately", "suggests", "may indicate" — these decide nothing, and
to a coordinator they read as doubt about a verdict that is not in doubt. If the record supports
the statement, make it plainly. If it does not, say what is missing instead. There is no third
option where you make a claim and quietly disown it.

## "No result is on file" is a complete and correct sentence

An unresolved criterion is a normal outcome, not a failure to be smoothed over. Say what is
absent and leave it there.

Two mistakes to avoid specifically:

- Never invent a plausible value for a result that is not on file. A number that looks right is
  worse than no number, because it will be read as a measurement.
- Never write that a patient does not have a condition when what the record shows is that nobody
  wrote it down. "No myocardial infarction is documented in the chart" is true. "The patient has
  no history of myocardial infarction" is a clinical claim the record has not made.

## Voice

Write the way a clinician writes in a chart: specific, unhurried, no adjective doing rhetorical
work. No "importantly", "notably", "it is worth noting". Do not address the reader, do not
recommend anything, and do not tell anyone what to do next — the packet has a section for that,
and eligibility is the investigator's decision, not yours.

Do not repeat the criterion back verbatim. The packet prints it directly above your sentence.

## Format

Return one sentence in the `sentence` field: one terminal full stop, no line breaks, no lists, no
markdown, no bracketed citations, no resource identifiers.

```

### Request

```
Criterion INC-04, an inclusion criterion.

The protocol says, word for word:
Signed written informed consent.

The screening engine found this criterion unresolved, because:
this criterion is settled at the screening visit, not from the record

Evidence the verdict rests on:
  nothing on file

Nothing in the record settles this criterion. What is missing: confirmation at the screening visit: Informed consent is a procedural/administrative act confirmed at the screening visit, not a fact recorded in the patient's clinical record..
A coordinator would go looking in the screening visit itself.

Write the sentence a coordinator will read beside this criterion.
```

### Attempt 1, tier `json_schema`

Response:

```
{"sentence": "Signed informed consent is confirmed at the screening visit rather than documented in the clinical record, so no evidence on file resolves this criterion."}
```

Validated against the schema.

### Result

```json
{
  "sentence": "Signed informed consent is confirmed at the screening visit rather than documented in the clinical record, so no evidence on file resolves this criterion."
}
```

## 23. writer on venice/claude-sonnet-5

- **Started:** 2026-08-30T10:35:10Z
- **Tier used:** `prose_check`
- **Retries:** 0
- **Tokens:** 0 in / 0 out
- **Estimated cost:** unpriced
- **Outcome:** validated

### Instructions

```
Prose check on one rationale sentence. No request was sent.
```

### Request

```
INC-04: the model's sentence was accepted as written.
```

### Attempt 1, tier `prose_check`

Response:

```
{
  "criterion_id": "INC-04",
  "verdict": "unknown",
  "source": "model",
  "sentence": "Signed informed consent is confirmed at the screening visit rather than documented in the clinical record, so no evidence on file resolves this criterion.",
  "rejected": [],
  "violations": [],
  "fallback_reason": null
}
```

Validated against the schema.

### Result

```json
{
  "criterion_id": "INC-04",
  "verdict": "unknown",
  "source": "model",
  "sentence": "Signed informed consent is confirmed at the screening visit rather than documented in the clinical record, so no evidence on file resolves this criterion.",
  "rejected": [],
  "violations": [],
  "fallback_reason": null
}
```

## 24. writer on venice/claude-sonnet-5

- **Started:** 2026-08-30T10:35:10Z
- **Tier used:** `json_schema`
- **Retries:** 0
- **Tokens:** 1986 in / 59 out
- **Estimated cost:** $0.0046
- **Outcome:** validated

### Instructions

```
# Rationale writing

You write one sentence at a time. Each one goes into a screening packet that a research
coordinator reads and signs, printed beside a criterion from a trial protocol and the evidence a
screening engine found in one patient's chart.

The verdict is already decided, deterministically, before you are asked. You are not reviewing it
and you are not being asked whether you agree. Your job is to say, in plain clinical English, what
the record shows and how it stands against the criterion.

## What you are given

- the criterion as the protocol wrote it, word for word;
- the verdict: met, not met, or unresolved;
- the engine's own rationale — correct, and written like a machine wrote it;
- every piece of evidence the verdict rests on, with its value, its unit and the date it was
  recorded.

That material is all you have and all you may use. You have no access to the chart, to reference
ranges, to the protocol beyond the quoted criterion, or to anything you happen to know about this
disease.

## What a good sentence looks like

> Creatinine was 1.2 mg/dL on 2026-05-14, inside the 1.5 mg/dL ceiling this criterion sets.

> No haemoglobin A1c result is on file for the window this criterion requires.

> Metformin is on the current medication list, which this exclusion criterion rules out.

One sentence. Name the finding, give the value and the date the record gives, and say how that
stands against the criterion. Past tense for what the chart recorded, present tense for what the
criterion requires. A coordinator should be able to read it and know whether they need to open the
chart.

Around twenty-five words is right. Forty is too long.

## Every number comes from the evidence

Each number and each date you write is checked mechanically against the values this criterion
resolved from: its threshold, its window, and the evidence rows you were shown. A sentence
carrying anything else is rejected and never reaches the packet.

- Copy values, units and dates exactly as they are given to you. Do not round, do not convert
  units, and do not restate a value "for clarity" in a form nobody wrote down.
- Do not calculate. No differences from a threshold, no percentages, no headroom, no averages.
- Do not count in digits. "Neither result is on file" is fine; "0 of 2 results" is not.
- Do not import a number from anywhere else: a normal range, a guideline cut-off, a value from
  another criterion, a today's date.
- Write a date in the form you were given it — `2026-05-14` — or refer to it without digits at
  all, as "the most recent result". A date rewritten as "14 May 2026" reads as two loose numbers
  and is rejected.

A sentence with no numbers in it is always safe, and is often the best sentence available.

## Hedging is not a way of abstaining

"Appears to be", "likely", "approximately", "suggests", "may indicate" — these decide nothing, and
to a coordinator they read as doubt about a verdict that is not in doubt. If the record supports
the statement, make it plainly. If it does not, say what is missing instead. There is no third
option where you make a claim and quietly disown it.

## "No result is on file" is a complete and correct sentence

An unresolved criterion is a normal outcome, not a failure to be smoothed over. Say what is
absent and leave it there.

Two mistakes to avoid specifically:

- Never invent a plausible value for a result that is not on file. A number that looks right is
  worse than no number, because it will be read as a measurement.
- Never write that a patient does not have a condition when what the record shows is that nobody
  wrote it down. "No myocardial infarction is documented in the chart" is true. "The patient has
  no history of myocardial infarction" is a clinical claim the record has not made.

## Voice

Write the way a clinician writes in a chart: specific, unhurried, no adjective doing rhetorical
work. No "importantly", "notably", "it is worth noting". Do not address the reader, do not
recommend anything, and do not tell anyone what to do next — the packet has a section for that,
and eligibility is the investigator's decision, not yours.

Do not repeat the criterion back verbatim. The packet prints it directly above your sentence.

## Format

Return one sentence in the `sentence` field: one terminal full stop, no line breaks, no lists, no
markdown, no bracketed citations, no resource identifiers.

```

### Request

```
Criterion EXC-01, an exclusion criterion.

The protocol says, word for word:
Antihyperglycemic treatment has not been stable within 12 weeks prior to screening.

The screening engine found this criterion unresolved, because:
this criterion was not formalised because it cannot be decided from data

Evidence the verdict rests on:
  nothing on file

Nothing in the record settles this criterion. What is missing: human judgement: "Stable" antihyperglycemic treatment is not a single coded fact; it requires comparing dose/regimen changes across a window, which has no representation in this vocabulary (no concept for treatment stability, and no way to enumerate what counts as a change)..
A coordinator would go looking in the protocol and the investigator.

Write the sentence a coordinator will read beside this criterion.
```

### Attempt 1, tier `json_schema`

Response:

```
{"sentence": "No record establishes whether antihyperglycemic treatment was stable in the 12 weeks before screening, so this criterion could not be resolved from the chart."}
```

Validated against the schema.

### Result

```json
{
  "sentence": "No record establishes whether antihyperglycemic treatment was stable in the 12 weeks before screening, so this criterion could not be resolved from the chart."
}
```

## 25. writer on venice/claude-sonnet-5

- **Started:** 2026-08-30T10:35:10Z
- **Tier used:** `prose_check`
- **Retries:** 0
- **Tokens:** 0 in / 0 out
- **Estimated cost:** unpriced
- **Outcome:** validated

### Instructions

```
Prose check on one rationale sentence. No request was sent.
```

### Request

```
EXC-01: the model's sentence was accepted as written.
```

### Attempt 1, tier `prose_check`

Response:

```
{
  "criterion_id": "EXC-01",
  "verdict": "unknown",
  "source": "model",
  "sentence": "No record establishes whether antihyperglycemic treatment was stable in the 12 weeks before screening, so this criterion could not be resolved from the chart.",
  "rejected": [],
  "violations": [],
  "fallback_reason": null
}
```

Validated against the schema.

### Result

```json
{
  "criterion_id": "EXC-01",
  "verdict": "unknown",
  "source": "model",
  "sentence": "No record establishes whether antihyperglycemic treatment was stable in the 12 weeks before screening, so this criterion could not be resolved from the chart.",
  "rejected": [],
  "violations": [],
  "fallback_reason": null
}
```

## 26. writer on venice/claude-sonnet-5

- **Started:** 2026-08-30T10:35:10Z
- **Tier used:** `json_schema`
- **Retries:** 0
- **Tokens:** 1957 in / 56 out
- **Estimated cost:** $0.0045
- **Outcome:** validated

### Instructions

```
# Rationale writing

You write one sentence at a time. Each one goes into a screening packet that a research
coordinator reads and signs, printed beside a criterion from a trial protocol and the evidence a
screening engine found in one patient's chart.

The verdict is already decided, deterministically, before you are asked. You are not reviewing it
and you are not being asked whether you agree. Your job is to say, in plain clinical English, what
the record shows and how it stands against the criterion.

## What you are given

- the criterion as the protocol wrote it, word for word;
- the verdict: met, not met, or unresolved;
- the engine's own rationale — correct, and written like a machine wrote it;
- every piece of evidence the verdict rests on, with its value, its unit and the date it was
  recorded.

That material is all you have and all you may use. You have no access to the chart, to reference
ranges, to the protocol beyond the quoted criterion, or to anything you happen to know about this
disease.

## What a good sentence looks like

> Creatinine was 1.2 mg/dL on 2026-05-14, inside the 1.5 mg/dL ceiling this criterion sets.

> No haemoglobin A1c result is on file for the window this criterion requires.

> Metformin is on the current medication list, which this exclusion criterion rules out.

One sentence. Name the finding, give the value and the date the record gives, and say how that
stands against the criterion. Past tense for what the chart recorded, present tense for what the
criterion requires. A coordinator should be able to read it and know whether they need to open the
chart.

Around twenty-five words is right. Forty is too long.

## Every number comes from the evidence

Each number and each date you write is checked mechanically against the values this criterion
resolved from: its threshold, its window, and the evidence rows you were shown. A sentence
carrying anything else is rejected and never reaches the packet.

- Copy values, units and dates exactly as they are given to you. Do not round, do not convert
  units, and do not restate a value "for clarity" in a form nobody wrote down.
- Do not calculate. No differences from a threshold, no percentages, no headroom, no averages.
- Do not count in digits. "Neither result is on file" is fine; "0 of 2 results" is not.
- Do not import a number from anywhere else: a normal range, a guideline cut-off, a value from
  another criterion, a today's date.
- Write a date in the form you were given it — `2026-05-14` — or refer to it without digits at
  all, as "the most recent result". A date rewritten as "14 May 2026" reads as two loose numbers
  and is rejected.

A sentence with no numbers in it is always safe, and is often the best sentence available.

## Hedging is not a way of abstaining

"Appears to be", "likely", "approximately", "suggests", "may indicate" — these decide nothing, and
to a coordinator they read as doubt about a verdict that is not in doubt. If the record supports
the statement, make it plainly. If it does not, say what is missing instead. There is no third
option where you make a claim and quietly disown it.

## "No result is on file" is a complete and correct sentence

An unresolved criterion is a normal outcome, not a failure to be smoothed over. Say what is
absent and leave it there.

Two mistakes to avoid specifically:

- Never invent a plausible value for a result that is not on file. A number that looks right is
  worse than no number, because it will be read as a measurement.
- Never write that a patient does not have a condition when what the record shows is that nobody
  wrote it down. "No myocardial infarction is documented in the chart" is true. "The patient has
  no history of myocardial infarction" is a clinical claim the record has not made.

## Voice

Write the way a clinician writes in a chart: specific, unhurried, no adjective doing rhetorical
work. No "importantly", "notably", "it is worth noting". Do not address the reader, do not
recommend anything, and do not tell anyone what to do next — the packet has a section for that,
and eligibility is the investigator's decision, not yours.

Do not repeat the criterion back verbatim. The packet prints it directly above your sentence.

## Format

Return one sentence in the `sentence` field: one terminal full stop, no line breaks, no lists, no
markdown, no bracketed citations, no resource identifiers.

```

### Request

```
Criterion EXC-02, an exclusion criterion.

The protocol says, word for word:
Planned coronary procedure or surgery after randomization.

The screening engine found this criterion unresolved, because:
this criterion is settled at the screening visit, not from the record

Evidence the verdict rests on:
  nothing on file

Nothing in the record settles this criterion. What is missing: confirmation at the screening visit: Refers to a future planned event after randomization, not a recorded state; this is settled at the visit/planning stage rather than being derivable from the chart, and is the same determination for every patient regardless of history..
A coordinator would go looking in the screening visit itself.

Write the sentence a coordinator will read beside this criterion.
```

### Attempt 1, tier `json_schema`

Response:

```
{"sentence": "No chart evidence addresses a planned coronary procedure or surgery after randomization, since this determination is made at the screening visit rather than from the record."}
```

Validated against the schema.

### Result

```json
{
  "sentence": "No chart evidence addresses a planned coronary procedure or surgery after randomization, since this determination is made at the screening visit rather than from the record."
}
```

## 27. writer on venice/claude-sonnet-5

- **Started:** 2026-08-30T10:35:10Z
- **Tier used:** `prose_check`
- **Retries:** 0
- **Tokens:** 0 in / 0 out
- **Estimated cost:** unpriced
- **Outcome:** validated

### Instructions

```
Prose check on one rationale sentence. No request was sent.
```

### Request

```
EXC-02: the model's sentence was accepted as written.
```

### Attempt 1, tier `prose_check`

Response:

```
{
  "criterion_id": "EXC-02",
  "verdict": "unknown",
  "source": "model",
  "sentence": "No chart evidence addresses a planned coronary procedure or surgery after randomization, since this determination is made at the screening visit rather than from the record.",
  "rejected": [],
  "violations": [],
  "fallback_reason": null
}
```

Validated against the schema.

### Result

```json
{
  "criterion_id": "EXC-02",
  "verdict": "unknown",
  "source": "model",
  "sentence": "No chart evidence addresses a planned coronary procedure or surgery after randomization, since this determination is made at the screening visit rather than from the record.",
  "rejected": [],
  "violations": [],
  "fallback_reason": null
}
```

## 28. writer on venice/claude-sonnet-5

- **Started:** 2026-08-30T10:35:10Z
- **Tier used:** `json_schema`
- **Retries:** 0
- **Tokens:** 2040 in / 55 out
- **Estimated cost:** $0.0046
- **Outcome:** validated

### Instructions

```
# Rationale writing

You write one sentence at a time. Each one goes into a screening packet that a research
coordinator reads and signs, printed beside a criterion from a trial protocol and the evidence a
screening engine found in one patient's chart.

The verdict is already decided, deterministically, before you are asked. You are not reviewing it
and you are not being asked whether you agree. Your job is to say, in plain clinical English, what
the record shows and how it stands against the criterion.

## What you are given

- the criterion as the protocol wrote it, word for word;
- the verdict: met, not met, or unresolved;
- the engine's own rationale — correct, and written like a machine wrote it;
- every piece of evidence the verdict rests on, with its value, its unit and the date it was
  recorded.

That material is all you have and all you may use. You have no access to the chart, to reference
ranges, to the protocol beyond the quoted criterion, or to anything you happen to know about this
disease.

## What a good sentence looks like

> Creatinine was 1.2 mg/dL on 2026-05-14, inside the 1.5 mg/dL ceiling this criterion sets.

> No haemoglobin A1c result is on file for the window this criterion requires.

> Metformin is on the current medication list, which this exclusion criterion rules out.

One sentence. Name the finding, give the value and the date the record gives, and say how that
stands against the criterion. Past tense for what the chart recorded, present tense for what the
criterion requires. A coordinator should be able to read it and know whether they need to open the
chart.

Around twenty-five words is right. Forty is too long.

## Every number comes from the evidence

Each number and each date you write is checked mechanically against the values this criterion
resolved from: its threshold, its window, and the evidence rows you were shown. A sentence
carrying anything else is rejected and never reaches the packet.

- Copy values, units and dates exactly as they are given to you. Do not round, do not convert
  units, and do not restate a value "for clarity" in a form nobody wrote down.
- Do not calculate. No differences from a threshold, no percentages, no headroom, no averages.
- Do not count in digits. "Neither result is on file" is fine; "0 of 2 results" is not.
- Do not import a number from anywhere else: a normal range, a guideline cut-off, a value from
  another criterion, a today's date.
- Write a date in the form you were given it — `2026-05-14` — or refer to it without digits at
  all, as "the most recent result". A date rewritten as "14 May 2026" reads as two loose numbers
  and is rejected.

A sentence with no numbers in it is always safe, and is often the best sentence available.

## Hedging is not a way of abstaining

"Appears to be", "likely", "approximately", "suggests", "may indicate" — these decide nothing, and
to a coordinator they read as doubt about a verdict that is not in doubt. If the record supports
the statement, make it plainly. If it does not, say what is missing instead. There is no third
option where you make a claim and quietly disown it.

## "No result is on file" is a complete and correct sentence

An unresolved criterion is a normal outcome, not a failure to be smoothed over. Say what is
absent and leave it there.

Two mistakes to avoid specifically:

- Never invent a plausible value for a result that is not on file. A number that looks right is
  worse than no number, because it will be read as a measurement.
- Never write that a patient does not have a condition when what the record shows is that nobody
  wrote it down. "No myocardial infarction is documented in the chart" is true. "The patient has
  no history of myocardial infarction" is a clinical claim the record has not made.

## Voice

Write the way a clinician writes in a chart: specific, unhurried, no adjective doing rhetorical
work. No "importantly", "notably", "it is worth noting". Do not address the reader, do not
recommend anything, and do not tell anyone what to do next — the packet has a section for that,
and eligibility is the investigator's decision, not yours.

Do not repeat the criterion back verbatim. The packet prints it directly above your sentence.

## Format

Return one sentence in the `sentence` field: one terminal full stop, no line breaks, no lists, no
markdown, no bracketed citations, no resource identifiers.

```

### Request

```
Criterion EXC-03, an exclusion criterion.

The protocol says, word for word:
Lower extremity complications (such as skin ulcer, infection, osteomyelitis, and gangrene) identified during screening and requiring treatment at randomization.

The screening engine found this criterion unresolved, because:
this criterion was not formalised because it cannot be decided from data

Evidence the verdict rests on:
  nothing on file

Nothing in the record settles this criterion. What is missing: human judgement: "Lower extremity complications" is an open-ended category illustrated by examples (skin ulcer, infection, osteomyelitis, gangrene) rather than an enumerated list; no single code or fixed set of codes captures it. It also requires judging that treatment is 'required' at a future randomization timepoint, which is not a stable recorded fact at screening..
A coordinator would go looking in the protocol and the investigator.

Write the sentence a coordinator will read beside this criterion.
```

### Attempt 1, tier `json_schema`

Response:

```
{"sentence": "No evidence is on file to determine whether a lower extremity complication requiring treatment at randomization is present, leaving this criterion unresolved."}
```

Validated against the schema.

### Result

```json
{
  "sentence": "No evidence is on file to determine whether a lower extremity complication requiring treatment at randomization is present, leaving this criterion unresolved."
}
```

## 29. writer on venice/claude-sonnet-5

- **Started:** 2026-08-30T10:35:10Z
- **Tier used:** `prose_check`
- **Retries:** 0
- **Tokens:** 0 in / 0 out
- **Estimated cost:** unpriced
- **Outcome:** validated

### Instructions

```
Prose check on one rationale sentence. No request was sent.
```

### Request

```
EXC-03: the model's sentence was accepted as written.
```

### Attempt 1, tier `prose_check`

Response:

```
{
  "criterion_id": "EXC-03",
  "verdict": "unknown",
  "source": "model",
  "sentence": "No evidence is on file to determine whether a lower extremity complication requiring treatment at randomization is present, leaving this criterion unresolved.",
  "rejected": [],
  "violations": [],
  "fallback_reason": null
}
```

Validated against the schema.

### Result

```json
{
  "criterion_id": "EXC-03",
  "verdict": "unknown",
  "source": "model",
  "sentence": "No evidence is on file to determine whether a lower extremity complication requiring treatment at randomization is present, leaving this criterion unresolved.",
  "rejected": [],
  "violations": [],
  "fallback_reason": null
}
```

## 30. writer on venice/claude-sonnet-5

- **Started:** 2026-08-30T10:35:10Z
- **Tier used:** `json_schema`
- **Retries:** 0
- **Tokens:** 1968 in / 66 out
- **Estimated cost:** $0.0046
- **Outcome:** validated

### Instructions

```
# Rationale writing

You write one sentence at a time. Each one goes into a screening packet that a research
coordinator reads and signs, printed beside a criterion from a trial protocol and the evidence a
screening engine found in one patient's chart.

The verdict is already decided, deterministically, before you are asked. You are not reviewing it
and you are not being asked whether you agree. Your job is to say, in plain clinical English, what
the record shows and how it stands against the criterion.

## What you are given

- the criterion as the protocol wrote it, word for word;
- the verdict: met, not met, or unresolved;
- the engine's own rationale — correct, and written like a machine wrote it;
- every piece of evidence the verdict rests on, with its value, its unit and the date it was
  recorded.

That material is all you have and all you may use. You have no access to the chart, to reference
ranges, to the protocol beyond the quoted criterion, or to anything you happen to know about this
disease.

## What a good sentence looks like

> Creatinine was 1.2 mg/dL on 2026-05-14, inside the 1.5 mg/dL ceiling this criterion sets.

> No haemoglobin A1c result is on file for the window this criterion requires.

> Metformin is on the current medication list, which this exclusion criterion rules out.

One sentence. Name the finding, give the value and the date the record gives, and say how that
stands against the criterion. Past tense for what the chart recorded, present tense for what the
criterion requires. A coordinator should be able to read it and know whether they need to open the
chart.

Around twenty-five words is right. Forty is too long.

## Every number comes from the evidence

Each number and each date you write is checked mechanically against the values this criterion
resolved from: its threshold, its window, and the evidence rows you were shown. A sentence
carrying anything else is rejected and never reaches the packet.

- Copy values, units and dates exactly as they are given to you. Do not round, do not convert
  units, and do not restate a value "for clarity" in a form nobody wrote down.
- Do not calculate. No differences from a threshold, no percentages, no headroom, no averages.
- Do not count in digits. "Neither result is on file" is fine; "0 of 2 results" is not.
- Do not import a number from anywhere else: a normal range, a guideline cut-off, a value from
  another criterion, a today's date.
- Write a date in the form you were given it — `2026-05-14` — or refer to it without digits at
  all, as "the most recent result". A date rewritten as "14 May 2026" reads as two loose numbers
  and is rejected.

A sentence with no numbers in it is always safe, and is often the best sentence available.

## Hedging is not a way of abstaining

"Appears to be", "likely", "approximately", "suggests", "may indicate" — these decide nothing, and
to a coordinator they read as doubt about a verdict that is not in doubt. If the record supports
the statement, make it plainly. If it does not, say what is missing instead. There is no third
option where you make a claim and quietly disown it.

## "No result is on file" is a complete and correct sentence

An unresolved criterion is a normal outcome, not a failure to be smoothed over. Say what is
absent and leave it there.

Two mistakes to avoid specifically:

- Never invent a plausible value for a result that is not on file. A number that looks right is
  worse than no number, because it will be read as a measurement.
- Never write that a patient does not have a condition when what the record shows is that nobody
  wrote it down. "No myocardial infarction is documented in the chart" is true. "The patient has
  no history of myocardial infarction" is a clinical claim the record has not made.

## Voice

Write the way a clinician writes in a chart: specific, unhurried, no adjective doing rhetorical
work. No "importantly", "notably", "it is worth noting". Do not address the reader, do not
recommend anything, and do not tell anyone what to do next — the packet has a section for that,
and eligibility is the investigator's decision, not yours.

Do not repeat the criterion back verbatim. The packet prints it directly above your sentence.

## Format

Return one sentence in the `sentence` field: one terminal full stop, no line breaks, no lists, no
markdown, no bracketed citations, no resource identifiers.

```

### Request

```
Criterion EXC-04, an exclusion criterion.

The protocol says, word for word:
Planning to start a sodium-glucose linked transporter-2 (SGLT2) inhibitor during the study.

The screening engine found this criterion unresolved, because:
this criterion is settled at the screening visit, not from the record

Evidence the verdict rests on:
  nothing on file

Nothing in the record settles this criterion. What is missing: confirmation at the screening visit: Future intent to start a medication during the study is a planned future state, not a recorded fact; it is settled at the screening visit and would be answered the same way regardless of chart contents..
A coordinator would go looking in the screening visit itself.

Write the sentence a coordinator will read beside this criterion.
```

### Attempt 1, tier `json_schema`

Response:

```
{"sentence": "No chart evidence addresses planned SGLT2 inhibitor initiation during the study, since this exclusion is settled by confirmation at the screening visit rather than by the record."}
```

Validated against the schema.

### Result

```json
{
  "sentence": "No chart evidence addresses planned SGLT2 inhibitor initiation during the study, since this exclusion is settled by confirmation at the screening visit rather than by the record."
}
```

## 31. writer on venice/claude-sonnet-5

- **Started:** 2026-08-30T10:35:10Z
- **Tier used:** `prose_check`
- **Retries:** 0
- **Tokens:** 0 in / 0 out
- **Estimated cost:** unpriced
- **Outcome:** validated

### Instructions

```
Prose check on one rationale sentence. No request was sent.
```

### Request

```
EXC-04: the model's sentence was accepted as written.
```

### Attempt 1, tier `prose_check`

Response:

```
{
  "criterion_id": "EXC-04",
  "verdict": "unknown",
  "source": "model",
  "sentence": "No chart evidence addresses planned SGLT2 inhibitor initiation during the study, since this exclusion is settled by confirmation at the screening visit rather than by the record.",
  "rejected": [],
  "violations": [],
  "fallback_reason": null
}
```

Validated against the schema.

### Result

```json
{
  "criterion_id": "EXC-04",
  "verdict": "unknown",
  "source": "model",
  "sentence": "No chart evidence addresses planned SGLT2 inhibitor initiation during the study, since this exclusion is settled by confirmation at the screening visit rather than by the record.",
  "rejected": [],
  "violations": [],
  "fallback_reason": null
}
```

## Cost

| Agent | Calls | Prompt | Completion | Cost |
|---|---:|---:|---:|---:|
| compiler | 8 | 107698 | 2517 | $0.2406 |
| critic | 2 | 5647 | 157 | $0.0129 |
| extractor | 4 | 8298 | 339 | $0.0200 (+1 unpriced) |
| resolver | 1 | 0 | 0 | $0.0000 (+1 unpriced) |
| writer | 16 | 15889 | 507 | $0.0368 (+8 unpriced) |

| Model | Calls | Prompt | Completion | Cost |
|---|---:|---:|---:|---:|
| claude-sonnet-5 | 31 | 137532 | 3520 | $0.3103 (+10 unpriced) |

**Total:** 141052 tokens, $0.3103 (+10 unpriced)
