# Build trajectory — the answer key

Work delivered exactly to spec, and sent back anyway, because the spec had a hole in it that only
showed up in the result.

---

## 1. The brief

The methodology mattered more than the artifact, so it was specified rather than left to judgement:

> **Annotate criteria, not cases.** For each patient-and-trial pair, work through the trial's
> eligibility criteria *as the registry wrote them* — never from any compiled output, which would
> make the exercise circular — and label each criterion `met`, `not_met` or `unknown` against the
> patient's chart summary. Then **derive** the case-level expected outcome by applying the rollup
> rule from `caliper.logic.roll_up`.
>
> This matters because a case-level label produced by reading everything at once is exactly the
> baseline system's failure mode, and a key built that way would be biased toward the baseline.
>
> **Two passes, then adjudication.** Annotate every pair twice, independently. Record both passes.
> Where they disagree, record the disagreement, decide it, and record the reason. Report Cohen's
> kappa over the criterion-level labels.
>
> **Label honestly.** Use `"llm-pass-1"` and `"llm-pass-2"`, and `"maintainer"` as adjudicator. Do
> not write anything that implies clinician review, because there was none.

## 2. What came back

All of it, done properly. 33 cases across 8 trials and 14 patients, 476 criterion labels per pass,
kappa 0.886, and an analysis of the disagreements that was better than the number:

> The more useful finding is the asymmetry: **all 33 disagreements run one way.** Pass 2 never
> abstained on a criterion pass 1 resolved. Collapsed to resolved-versus-abstain, kappa 0.865. That
> is a difference of threshold, not noise.

And an adjudication that reads like a real one:

> **AK-032**, 10 of the 33 disagreements. Last encounter is five months before screening; pass 1
> demanded an encounter *inside* each window, pass 2 asked only that the chart be current. Pass 1
> lost because pass 1 contradicted itself — it had used the looser rule on nine other charts.

Then, flagged by the agent itself rather than buried:

> **There are no `eligible` cases, and that is the single most important thing to know about this
> key.** Every one of the eight protocols bounds at least one lab quantity no chart in the corpus
> carries, and under the protocol's rule that a test not done is not a normal result those go
> `unknown` and propagate.

## 3. Why that was not survivable

The agent was right that it was the most important thing about the key, and right to lead with it.
It was wrong that documenting it was enough, and the reason is arithmetic:

> With no eligible case in the key, an unsafe error — calling a patient eligible when they are not —
> is possible in exactly one direction, and that direction is never the right answer. A system that
> answered "ineligible" to everything would commit zero unsafe errors and score 22 of 33. Our
> headline metric is coverage at zero unsafe errors, and against this key it would be measuring
> something close to nothing.

## 4. What was asked for instead

Not a different key. Constructed cases, built from the annotations already in hand:

> For a pair whose labels are all `met` except one or two `unknown` caused by a *missing
> measurement*, the pre-registered rollup rule says: supply that measurement in a value the criterion
> accepts, and the case becomes `eligible`. The label follows from your existing human criterion
> labels plus the rollup rule stated up front. It is not circular — nothing about our system is
> consulted.
>
> Also build, from the same pairs: near-miss cases where one supplied value is *just outside* what
> the criterion accepts, so the answer is `ineligible`; and cases where every value but one is
> supplied, so the answer stays `needs_review`. Together these form a triple on the same patient and
> trial — eligible, ineligible by a hair, and undecidable — which is exactly the discrimination the
> key currently cannot make.

With one instruction about how to say it afterwards:

> Keep and sharpen the finding: **no patient in this corpus is eligible for any of these ten real
> protocols as their charts stand.** Name the quantities. That is a fact about the data, and it is
> more interesting than a table of scores. Report the two counts separately — annotated and
> constructed — everywhere the key is summarised, so nobody can read a constructed case as an
> observed one.

## 5. The transferable part

The agent did the job it was given and surfaced the thing that made the job insufficient. That is
the best available outcome from a brief with a hole in it, and it only happened because the report
led with the inconvenient finding instead of the headline number.

The hole was in the brief, not the work: nobody had asked what the key would be able to discriminate
once it existed. It is a question worth asking before an evaluation is built rather than after.
