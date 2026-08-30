# Build trajectory — the critic, and where a finding gets fixed

A correct diagnosis, a wrong first instinct about where the fix belongs, and the correction.

---

## 1. The brief

Scoped to `src/caliper/agents/critic.py`, its prompt file, and its tests. The design was specified
tightly, because the component only works if it is narrow:

> For each compiled `Criterion`, render the predicate into plain English **deterministically, in
> code, without a model**. Then ask the model a *single, narrow* question: does this English sentence
> say the same thing as this protocol quote?
>
> The point of rendering deterministically is that the model is never shown the JSON. It compares two
> English sentences, which is a much easier and much more checkable job than auditing a data
> structure, and it means a compiler mistake cannot hide behind familiar-looking JSON.
>
> **Anything other than `equivalent` is a downgrade.** `narrower` and `broader` are both downgrades —
> a criterion that is merely *narrower* than the protocol still screens the wrong patients out.

It was also asked, explicitly, to report where the downgrade rule felt too aggressive.

## 2. What came back

The component, plus this, which was the point of asking:

> **The single temporal anchor.** `TemporalWindow` is defined relative to screening only, but
> protocols routinely anchor to randomisation, enrolment or first dose. The compiler has to flatten
> those onto screening; the rendering then honestly says "before screening", and the critic will call
> it `contradicts` and send it to a human. On real protocols this will produce a meaningful downgrade
> rate that is really an IR limitation surfacing as a critic finding.
>
> I deliberately did **not** add a hint to the comparison request telling the model the anchor is
> fixed by the vocabulary, because that hint would equally excuse a genuine anchor bug. If the
> downgrade rate proves unusable, the fix belongs in `ir.TemporalWindow` — an explicit anchor field —
> **not** in softening the critic.

The refusal to paper over it in the prompt is the part that mattered. Adding "assume the anchor is
screening" to the instructions would have made the symptom disappear and left a real class of
compiler bug permanently invisible.

## 3. What changed, and where

`TemporalWindow` gained an anchor:

```python
anchor: Literal["screening", "enrolment", "randomisation", "consent", "first_dose"] = "screening"
```

The evaluator still resolves every window against the screening date, because that is the only date
it has. What changed is that the approximation is now *reported* rather than discarded:
`CriterionResult.approximations` carries a sentence saying the protocol anchored to randomisation
and we evaluated against screening, `ScreeningResult.approximations` aggregates them, and the packet
prints them next to the verdict.

The agent was then sent back with the reasoning spelled out, because the point was not just to
render the new field:

> That removes the spurious `contradicts` flood you predicted, because the rendered sentence will
> now match the protocol quote for anchor-shifted criteria, and it keeps the critic catching genuine
> anchor bugs — a compiler that reads "within 12 weeks prior to randomisation" and emits
> `anchor="screening"` will now be caught, which is exactly the case you did not want to excuse with
> a prompt hint.

## 4. What it built on the second pass

Both halves, tested against each other on the same protocol quote:

| anchor | rendered as |
|---|---|
| `screening` | "recorded within the 12 weeks before screening" |
| `randomisation` | "recorded within the 12 weeks before randomisation" |
| `first_dose` | "recorded within the 12 weeks before the first dose" |

and a test deriving the set of legal anchors from the IR itself, so that adding one to
`TemporalWindow` fails in the critic before a rendering can silently omit it.

It also volunteered a second finding, unprompted, about its own coverage check:

> Rule 2 is the generous half: a criterion quoting only "Moderate to severe COPD." is treated as
> having compiled the sub-conditions hanging off it. That is deliberate — this check exists to find
> spans nobody went near, and false alarms on legitimately merged criteria train people to ignore the
> report. It is also the rule most worth revisiting: a compiler that quotes the parent and ignores a
> sub-bullet threshold will not be caught here.

The fix was to keep the rule and report the weaker evidence separately, so the report now reads:

```
Spans no criterion claims:
- [4] Current smoker.

Spans claimed only through their parent, not quoted by any criterion:
- [2] Post-bronchodilator FEV1/FVC ratio <0.70.
- [3] FEV1 between 30% and 70% predicted.
```

## 5. The transferable part

The first instinct on a noisy check is to make the check quieter. The agent named that instinct and
refused it, and the fix went one layer down into the data model, where it also made the packet
honest about something it had been silently approximating.
