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
