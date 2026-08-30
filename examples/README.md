# Closing an abstention

`settlements.json` is a worked example of the one thing Caliper's design makes necessary: a way for
a person to answer a question the record could not.

Most of what Caliper abstains on is not a gap in a chart. It is a category the protocol never
enumerated — "at least one major cardiovascular risk factor" — or a plan, or an intention. No FHIR
query closes those. Somebody has to be asked, and unless their answer comes back into the screening
the system has produced a very well-documented dead end.

## The rule

**A settlement may answer a question the record could not, and may never contradict a question the
record already answered.**

A criterion the evaluator resolved to MET or NOT_MET keeps its verdict whatever this file says, and
the attempt is recorded and printed rather than dropped. That single rule is what makes accepting a
human answer safe: it can only ever move a criterion off UNKNOWN, so the worst a wrong settlement can
do is what a wrong human screening already does — and the record underneath is still there, still
cited, still disagreeing in writing.

Three smaller rules follow from the same instinct, all enforced at construction:

- **UNKNOWN is not an answer a person may give.** Declining to answer is what the criterion already
  says.
- **A settlement is signed and explained, or it is refused.** An unattributable override is
  indistinguishable from a bug in six months.
- **A settlement names one patient.** The criterion blocking one screening usually blocks the whole
  cohort, which makes a cohort-wide answer tempting and wrong: "does this patient have a major
  cardiovascular risk factor" is a different question about each of them, and one `met` would carry
  twenty-three charts nobody was asked about. What generalises is the *definition* a coordinator
  applies, not the verdict it produces, and supplying a definition means recompiling the criterion
  rather than answering it. That is a different feature and it is not built.

## Running it

```bash
caliper screen NCT03315143 1be83f06-48ef-7bac-7097-b9e0644aeaf8 \
  --settlements examples/settlements.json \
  --packet /tmp/packet.html
```

The two criteria in this file are the ones that actually blocked that screening, and the notes on
them are grounded in what the committed chart says — the SNOMED code and its onset date are in the
bundle, and the missing stop dates are the documented reason the treatment-stability criterion
cannot be settled from data. The coordinator supplies only the judgement, which is their job.

The packet marks every settled criterion in the table, gives them their own section above it, and
prints the name and the date on each, so nobody reads a person's word as a citation from the chart.
