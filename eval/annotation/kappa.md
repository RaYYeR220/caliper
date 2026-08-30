# Inter-annotator agreement

Cohen's kappa over the criterion-level labels of the two independent annotation passes, before
adjudication. The unit is one criterion on one patient-and-trial pair: 36 annotated pairs, and
therefore 491 paired labels. Every number below is reproduced by
`python scripts/build_answer_key.py`, which recomputes the statistic from `pass1.json` and
`pass2.json` on every run.

This measures the annotation only. The 15 constructed cases carry no annotator labels of their own
— their criterion labels are the adjudicated labels of their base pair with the perturbed criteria
overridden — so they are not part of this statistic and could not be.

## Contingency table

Rows are `llm-pass-1`, columns are `llm-pass-2`.

|  | met | not_met | unknown | **total** |
|---|---:|---:|---:|---:|
| **met** | 60 | 0 | 0 | **60** |
| **not_met** | 2 | 216 | 0 | **218** |
| **unknown** | 11 | 23 | 179 | **213** |
| **total** | **73** | **239** | **179** | **491** |

## The arithmetic

Observed agreement is the diagonal over the total:

```
p_o = (60 + 216 + 179) / 491 = 455 / 491 = 0.926680
```

Chance agreement is the sum over categories of the product of the two marginals:

```
p_e = (60/491)(73/491) + (218/491)(239/491) + (213/491)(179/491)
    = 0.122200 x 0.148676 + 0.443992 x 0.486762 + 0.433809 x 0.364562
    = 0.018168 + 0.216118 + 0.158150
    = 0.392437
```

Kappa:

```
kappa = (p_o - p_e) / (1 - p_e)
      = (0.926680 - 0.392437) / (1 - 0.392437)
      = 0.534243 / 0.607563
      = 0.8793
```

Large-sample standard error `sqrt(p_o(1 - p_o) / (n (1 - p_e)^2))` = 0.0194, giving an approximate
95% interval of **0.841 to 0.917**. On the Landis and Koch bands that is "almost perfect", a
description we quote and do not endorse: the bands were proposed as arbitrary and are routinely
misread as a quality certificate.

## Per trial

| Trial | Labels | Agreed | Differed | p_o | kappa |
|---|---:|---:|---:|---:|---:|
| NCT01131676 | 90 | 86 | 4 | 0.956 | 0.929 |
| NCT02545049 | 44 | 44 | 0 | 1.000 | 1.000 |
| NCT03036124 | 68 | 66 | 2 | 0.971 | 0.942 |
| NCT03315143 | 45 | 36 | 9 | 0.800 | 0.666 |
| NCT03819153 | 44 | 43 | 1 | 0.977 | 0.962 |
| NCT05748834 | 57 | 52 | 5 | 0.912 | 0.840 |
| NCT06717698 | 75 | 71 | 4 | 0.947 | 0.915 |
| NCT07252908 | 68 | 57 | 11 | 0.838 | 0.697 |

The two weakest trials are the two that concentrate the protocol's soft spots. `NCT03315143` has
five in-scope criteria and one of them, "at least one major cardiovascular risk factor", is
undefined in the registry text and was reached on all nine of its pairs; that single criterion
accounts for eight of its nine disagreements; the ninth, on `AK-016`, is `NCT03315143-I2` and is
listed under Theme 6 in `disagreements.md`. `NCT07252908` has the most criteria with explicit short
windows, and ten of its eleven disagreements are the chart-currency question described in
`disagreements.md`.

## The asymmetry, which matters more than the coefficient

Every one of the 36 disagreements runs the same way.

| Direction | Count |
|---|---:|
| pass 1 `unknown` -> pass 2 `not_met` | 23 |
| pass 1 `unknown` -> pass 2 `met` | 11 |
| pass 1 `not_met` -> pass 2 `met` | 2 |
| any direction where pass 2 was the more cautious | **0** |

Collapsing the three labels to the binary question the evaluation actually turns on — did the
annotator resolve the criterion, or abstain on it — gives:

|  | pass 2 resolved | pass 2 unknown |
|---|---:|---:|
| **pass 1 resolved** | 278 | 0 |
| **pass 1 unknown** | 34 | 179 |

with `p_o` = 0.9308, `p_e` = 0.5179 and **kappa = 0.856** (SE 0.024). The empty cell is the finding:
pass 2 never abstained on a criterion pass 1 resolved. Pass 1 abstained on 213 criteria and pass 2
on 179, and the 34 extra abstentions are entirely pass 1's.

This is not noise around a shared standard, it is a difference in threshold, and a kappa of 0.879
hides it. Two annotators who disagree symmetrically are applying one rule imprecisely; two who
disagree in one direction are applying two rules. The rules in question were the chart-currency
test in protocol section 4 and how much may be inferred from an undefined term — both of which the
protocol left more open than we thought when we wrote it. `disagreements.md` records what each was
sharpened to.

## What the number is and is not evidence of

Kappa here measures whether `protocol.md` is specific enough that two readings of the same chart
and the same registry text produce the same label. It measures nothing about clinical correctness.
Both passes are language models; n2c2 2018 Track 1 and TREC Clinical Trials established dual
*expert* annotation as the standard for cohort selection, and this is not that. A kappa of 1.0 here
would have meant the protocol is unambiguous, or that the two passes were not independent, and
would still not have meant the labels are right.

Two further caveats on the coefficient itself. The categories are unbalanced — 44% `not_met` and 43%
`unknown` on pass 1, with `met` at 12% — and kappa is sensitive to marginal distribution, so the
value is not comparable to a kappa computed on a differently balanced corpus. And the 491 labels are
not independent draws: they cluster by patient and by trial, so the standard error above is
optimistic. The per-trial table is the honest way to read the spread.

After adjudication, agreement is 100% by construction, which is why the pre-adjudication number is
the one reported. Of the 36 adjudications, 15 upheld pass 1 and 21 upheld pass 2, across 22 of the
36 annotated cases; exactly one changed a case-level outcome.
