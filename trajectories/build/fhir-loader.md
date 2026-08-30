# Build trajectory — the FHIR ingestion layer

An agent given a brief, refusing part of it because the brief was wrong, and being right.

---

## 1. The brief

Scoped to two files: `src/caliper/fhir.py` and `tests/test_fhir.py`. Everything else was
read-only, with an explicit instruction: *"If you believe another file must change, report it
instead of changing it."*

The mapping rules were spelled out — Observation to evidence with LOINC codes and units, Condition
with onset dates, component-valued observations emitting one row per component, `fhir_path`
pointing at the real entry index. Then this, about clinical notes:

> `DocumentReference` → `kind` per its content, but its real purpose is narrative evidence: decode
> `content[].attachment.data` (base64) into text, and emit Evidence with `source="narrative"` and
> `narrative_quote` set to the decoded text. Give it `kind="encounter"` ONLY if that is genuinely
> right; otherwise, since `EvidenceKind` has no "note" member, report back that you need a new
> `EvidenceKind` rather than forcing it into a wrong bucket. Do not modify `record.py` yourself.

## 2. What came back

The agent implemented everything else and declined that part, with a two-part argument:

> **`EvidenceKind` needs a narrative member — I suggest `"note"`.** `DocumentReference` has no
> honest home in the current `Literal[...]`:
>
> - `"encounter"` is wrong because `PatientIndex.has_documented_activity` treats every encounter row
>   as proof a visit occurred inside the window, which is what lets `AbsencePolicy.COVERAGE_GATED`
>   resolve an absence to `MET`. A note is documentation *about* an encounter — Synthea emits one per
>   encounter, so the Encounter resource is already in the bundle — and indexing it as an encounter
>   both double-counts and quietly redefines what "the chart was covered" means.
> - `"condition"` is worse: narrative rows have no codes, so `_matches_concept` falls through to
>   substring matching. A discharge summary containing the phrase "myocardial infarction" in a
>   *negated* or family-history sentence would satisfy a `PresencePredicate`.

It had also noticed something outside its scope and reported rather than fixed it:

> `_matches_concept`'s text fallback will match narrative and uncoded rows on any substring, so it
> will want a guard once narrative evidence exists.

## 3. What changed

Both points were accepted and implemented in `record.py`, which the agent could not touch:

- `EvidenceKind` gained `"note"`.
- `_matches_concept` now refuses to match a narrative row by wording at all. Prose earns a verdict
  only once something has attached a code to it and taken responsibility for reading the sentence.

That second rule became the whole design of the extraction agent, which arrived later: a note
sentence produces coded evidence only if it is classified `present` or `absent` about *this*
patient, and the quoted sentence must appear in the note verbatim.

The first version — indexing notes as encounters — would have been silently, catastrophically wrong.
Every patient with a discharge summary would have looked like a patient with a documented visit, and
the absence policy would have started resolving absences on charts nobody had reviewed.

## 4. What it found later

The same agent, resumed twice on the same files, produced two of the four bugs in `CHANGELOG.md`:

> `1be83f06-…` has a recorded death on 2026-05-03; the fixed screening date is 2026-06-01. Because
> `load_patient_index` never reads `Patient.deceasedDateTime`, that chart currently reads as an
> ordinary screenable patient whose records simply stop.

and

> 114 of 342 MedicationRequest rows across 16 patients come back with an empty display and no codes,
> because Synthea writes them as `medicationReference` pointing at a `Medication` resource rather
> than inlining `medicationCodeableConcept`.

When told to implement the first, it refused a piece of that too. FHIR permits `deceasedBoolean`
with no date, and the brief had not said what to do with it:

> **`deceasedBoolean: true` with no date does not get a fabricated date.** `screen.py` interpolates
> `patient.deceased.isoformat()` straight into the coordinator-facing rationale. Any sentinel I
> picked would surface there as a stated date of death that no one recorded.

`PatientIndex` gained a second field, `deceased_undated`, and the screening now says *"the chart
records that the patient has died, without giving a date."* No such chart exists in the corpus. It
is a tripwire for the first one that does.

## 5. The transferable part

The rule that produced all of this was not about models. It was that an agent could read anything
and write almost nothing, so the only way to change a contract was to argue for it in writing. Three
times the argument was better than the brief.
