# Trajectory

**Calls:** 8 | **Prompt tokens:** 107698 | **Completion tokens:** 2517 | **Estimated cost:** $0.2406

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

## Standing instructions

Identical on every call below, so printed once rather than before each.

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

## 1. compiler on venice/claude-sonnet-5

- **Started:** 2026-08-30T10:35:10Z
- **Tier used:** `json_object`
- **Retries:** 1
- **Tokens:** 13466 in / 339 out
- **Estimated cost:** $0.0303
- **Outcome:** validated

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

## Cost

| Agent | Calls | Prompt | Completion | Cost |
|---|---:|---:|---:|---:|
| compiler | 8 | 107698 | 2517 | $0.2406 |

| Model | Calls | Prompt | Completion | Cost |
|---|---:|---:|---:|---:|
| claude-sonnet-5 | 8 | 107698 | 2517 | $0.2406 |

**Total:** 110215 tokens, $0.2406
