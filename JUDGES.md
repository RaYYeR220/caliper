# Reviewing this in five minutes

A guided path through the parts worth checking, in the order that makes them checkable. Every claim
below links to the thing that backs it, so nothing has to be taken on trust.

---

## One minute — does it run, and is it the same code that produced the numbers?

```bash
docker build -t caliper . && docker run --rm caliper
```

That verifies every fixture against its committed digest, runs the whole evaluation from recorded
model responses, and prints the results table. No API key, no network, no cost.

Without Docker: `make install && make data-verify && make eval`. Details in
[`REPRODUCE.md`](REPRODUCE.md).

---

## One minute — the claim, and the thing that would undermine it

Open [`RESULTS.md`](RESULTS.md).

The headline is **coverage at zero unsafe errors**: how much of the work the system takes off a
coordinator's desk without ever sending forward a patient who should not have been. It is a single
operating point on a risk-coverage curve, and the curve is printed underneath it.

Then look at two rows in the same table before believing any of it:

- **`always_needs_review`** — a system that abstains on everything. It commits no unsafe error at
  all, which is exactly why that number alone proves nothing.
- **the false-abstention column** — how often Caliper sent a *decidable* case to a human anyway.
  That is what abstaining on everything is bad at, and it is what stops the safety number from being
  free.

---

## One minute — is the safety structural, or is it a prompt?

Two things to check, both fast.

**The verdict cannot come from a model.** `caliper/evaluate.py` and `caliper/screen.py` import
nothing from `caliper/agents/` or `caliper/llm/`. The dependency runs one way and a test asserts it.
`grep -n "^from\|^import" src/caliper/evaluate.py` takes ten seconds.

**`ELIGIBLE` is unreachable while anything is unresolved.** The rule is nineteen lines in
[`src/caliper/logic.py`](src/caliper/logic.py), in the `roll_up` function, and it is ordinary
Python.

---

## One minute — how much of the evaluation depends on us?

This is the part we would attack first, so it is the part with the most machinery behind it.

**The metamorphic suite** (`pytest tests/test_metamorphic.py`) asserts *relationships between two
runs* rather than answers. Redact the only creatinine result and the criterion that used it must
become unresolved. Move a value across a threshold and that criterion's verdict must flip, and no
other criterion's may change. Remove the encounters covering a window and an absence criterion must
stop resolving under the default policy but keep resolving under the closed-world one. These are
true by construction and owe nothing to our judgement. The suite includes a deliberately broken case
to prove the runner catches failures.

**The answer key is frozen and hashed.** `caliper eval` refuses to score against a key whose digest
does not match its sidecar (`eval/answer_key.json.sha256`), so the key demonstrably predates the results.
[`eval/annotation/`](eval/annotation/) holds the annotation protocol, both independent passes, every
disagreement with how it was decided, and the inter-annotator agreement. It is model-assisted dual
annotation with human adjudication, and it says so — there was no clinician review and we do not
claim one.

**Case labels are derived, not asserted.** Annotators labelled individual criteria; the case-level
outcome is computed from those labels by the same rollup rule stated up front. Labelling a case by
reading everything at once is precisely the baseline's failure mode, and a key built that way would
have been biased toward it.

---

## One minute — is the output something a person would sign?

```bash
caliper ui demo && cd web && python -m http.server 8000
```

Three screens: criteria review, the screening queue, one patient's packet. No build step, nothing
fetched from a CDN.

On the packet, the things worth looking at:

- **The open items come first.** Every unresolved criterion names the missing datum, where to find
  it, and the FHIR query that would close it. Abstention that does not say what is missing has not
  reduced the work, it has moved it — and a 2025 study of 259 clinicians found that abstention
  without explanation shifted errors rather than removing them.
- **Every value carries its pointer.** Value, unit, date, and the FHIR path it came from.
- **The verdicts are distinguishable without colour.**
- **The sentences were checked.** Each rationale is written by a model and then verified against
  that criterion's own values; one that fails twice is replaced by machine prose, and the packet
  says which rows that happened to.

---

## If you have longer

| Question | Where |
|---|---|
| What is real and what is simulated? | [`LIMITS.md`](LIMITS.md) |
| What backs each claim in the README? | [`EVIDENCE.md`](EVIDENCE.md) |
| Which design choice bought which number? | [`CHANGELOG.md`](CHANGELOG.md) |
| What did the agents actually do? | [`AGENTS.md`](AGENTS.md), [`trajectories/`](trajectories/) |
| Where did the data come from? | [`data/DATA_SOURCE.md`](data/DATA_SOURCE.md) |
| What did we get wrong? | The "What went wrong" section of [`AGENTS.md`](AGENTS.md), and the failure mode at the end of [`README.md`](README.md) |

## The three things we would attack if this were someone else's

1. **The answer key is ours.** Mitigated by the metamorphic suite, by freezing, and by deriving case
   labels from criterion labels — but at fifty-odd cases the confidence intervals span roughly
   thirteen percentage points, and differences smaller than that are not differences.
2. **The trust moved rather than disappearing.** The evaluator cannot hallucinate, but it evaluates
   what the compiler gave it. Every guard narrows that surface without closing it. The honest
   mitigation is that compiled criteria are a small reviewable artifact approved once per protocol,
   not per patient.
3. **Synthetic charts are tidier than real ones.** Synthea's laboratory values are drawn from
   distributions rather than tracking disease severity, and its own notes are templates — which is
   why the narrative cases use notes we wrote and label as such.
