# Hand-authored synthetic clinical notes

**These notes were written by hand for this project. They describe no real person, they are not
derived from any real record, and they contain no protected health information.** Names,
relatives, dates and results in them were invented. They are attached to Synthea patients by id
so that a narrative sits beside a plausible structured chart, but nothing here came out of
Synthea and nothing here was copied from a real chart.

## Why they exist

Caliper's rule is that prose earns a verdict only once something has read the sentence and
attached a code to it. `caliper.record._matches_concept` enforces it: a narrative row with no
codes matches nothing, however well its wording matches. The component that earns those codes is
`caliper.agents.extractor`, and it needs prose that can actually catch it out.

Synthea's own `DocumentReference` notes cannot do that. They are fill-in-the-blank templates —
demographics, a problem list, a medication list — with no clinical language in them. Nothing in
them is denied, attributed to a relative, planned rather than done, or left uncertain, so nothing
in them distinguishes an extractor that reads a sentence from one that greps for a phrase. That
distinction is the whole point: an eligibility criterion answered by finding "myocardial
infarction" in a discharge summary will confidently diagnose the patient's father.

So the notes here are written to contain exactly the readings that a keyword match gets wrong:

| Phenomenon | What a naive matcher does | Example from the corpus |
|---|---|---|
| plainly asserted | right, by luck | "Presented with an inferior STEMI on 14 March 2025 …" |
| explicit denial | diagnoses the patient | "No history of myocardial infarction." |
| family history | diagnoses the father | "Father had an MI in his fifties …" |
| hypothetical or planned | records an operation that has not happened | "Listed for functional endoscopic sinus surgery." |
| resolved or historical | ignores the date that decides the window | "Admitted with decompensated heart failure in 2013; no recurrence since." |
| uncertain | promotes a query to a diagnosis | "Query paroxysmal AF as the cause of the collapse." |
| other subject | diagnoses the partner | "His partner is currently on treatment for smear positive pulmonary TB …" |
| other organ system | matches the word, not the organ | "… an old right occipital infarct unchanged since 2019." |
| numeric only in prose | misses the result entirely | "Creatinine today 1.7 mg/dL, up from 1.2 in January." |

## Layout

One file per patient, `{patient_id}.json`, holding a list of notes ordered by date:

```json
{
  "note_id": "8d91c36a-hf-2015-04-22",
  "date": "2015-04-22",
  "type": "Heart failure clinic note",
  "author_role": "heart failure nurse specialist",
  "text": "HF clinic, nurse led.\n\n34M with chronic heart failure …"
}
```

21 notes across 9 patients: discharge summaries, clinic letters, GP consultations, ED notes and
nurse triage calls. Note dates sit inside each patient's own encounter history, so a note never
post-dates a chart that stops in 2016.

## Why they are not in the bundles

`data/patients/*.json` is checksummed Synthea output, declared byte-for-byte in
`data/DATA_SOURCE.md` and verified by `tests/test_data_integrity.py`. Writing hand-authored text
into a `DocumentReference` inside a bundle would break that declaration and blur the line between
what was generated upstream and what was written here. The notes are therefore kept in a separate
tree and merged explicitly at load time by `caliper.notes.attach_notes`, which is also the only
place a reader has to look to see what was added.

For the same reason a note's `fhir_path` points at this directory rather than at a bundle entry:

```
data/notes/8d91c36a-1f7e-3842-9f14-8d567ed9cdcd.json#8d91c36a-hf-2015-04-22
```

`Bundle.entry[n].resource` would be a citation to a resource that does not exist.

## manifest.json

`manifest.json` is the ground truth. For every note it lists the phenomena in it, the sentence
carrying each one **quoted character for character from the note**, the assertion class the
sentence belongs to, and what a correct extraction produces — `"extract": []` meaning nothing at
all. `must_not_extract` names the concept a keyword search would wrongly pull out of that
sentence.

`tests/test_notes.py` re-checks every quote against its note on every run, so the ground truth
cannot drift away from the corpus it describes.

Codes are given in the manifest only where the identifier is beyond doubt. Attaching codes is the
resolver's job, not the extractor's; the extractor is graded on the assertion and the concept it
picked, and it copies whatever codes the concept arrived with.
