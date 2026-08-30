# The coordinator's interface

Three screens over one run: what the compiler made of a protocol, a cohort screened against it, and
the packet for one patient. It is the interactive sibling of the printed packet that
`caliper screen --packet` produces, and it shows the same document — the screening export calls
`build_packet`, so the page and the printout cannot drift apart.

## Running it

```sh
python -m caliper.cli ui demo          # write web/data from the committed fixtures
python -m http.server --directory web  # then open the address it prints
```

`ui demo` needs no API key, no network and no model call. It compiles NCT01131676 and NCT03315143
from hand-written `CriteriaSet`s standing in for the compiler's output, runs the real critic
machinery, the real evaluator and the real packet builder over the committed FHIR bundles, and
writes one JSON file per screening plus an index. Everything on screen is a value the system
produced.

The bundle is screened on **2026-04-01**, not the 2026-06-01 that the answer key and the rest of
this repository use. The corpus's only patient with a type 2 diabetes diagnosis is recorded as
having died on 2026-05-03, so screening on the later date closes that screening on the death before
a criterion is read and leaves the cohort with no open work in it at all. Every screen states the
date and the reason; `caliper ui demo --as-of 2026-06-01` reproduces the other reading.

Opening `index.html` from the file system will not work: ES modules and `fetch` are both blocked on
`file://`, and the page says so rather than rendering blank.

## Two cohorts, and why some of the charts were edited

**No chart in this corpus is eligible for any of these real protocols as it stands, and none can
be.** That is two findings stacked on each other. The annotation found that every one of the eight
protocols in the answer key bounds at least one quantity no Synthea chart carries — a liver panel
for NCT01131676, a UACR, an NYHA class, an ECOG score — and a test that was not done is unresolved
rather than normal. The compiler adds the sharper half: sixteen of NCT01131676's twenty-two criteria
and six of NCT03315143's eight cannot be formalised from a record at all, and `ELIGIBLE` is
unreachable while any criterion is unresolved. The queue says so on both trials rather than leaving
it to be discovered by filtering to a verdict that never appears.

So the demo carries a second cohort, and marks it everywhere. The fifteen screenings on NCT03315143
whose identifier carries a `CK-` case number are **constructed**: charts from
[`eval/answer_key.json`](../eval/answer_key.json) that were edited to supply a measurement the
patient never had, so that a bound the protocol states could be crossed on purpose. Seven of them
the key derives as eligible on the criteria it scopes in; four are ineligible by one unit; four are
undecidable because the measurement was removed instead. Caliper still stops at needs review on all
seven of the eligible ones, and each of those packets names the criteria that stopped it.

Every constructed screening carries its case number in its name, a hatched edge in the queue and on
the packet, and — above the verdict, before anything derived from the chart — the frozen key's own
list of what was changed. The queue filters and sorts on the distinction, and its last section puts
each edited chart beside the two or three siblings that differ from it by one supplied number, with
the unedited chart at the head of the group. The construction method, the perturbation vocabulary
and what the whole device costs are in
[`eval/annotation/protocol.md`](../eval/annotation/protocol.md), section 11.

## Why there is no build step

Every dependency is a thing that can fail in front of the person you are showing the work to — a
lockfile that will not resolve, a CDN blocked on the hospital network, a build that wants a Node
version nobody has. This is plain HTML, one stylesheet and ES modules: nothing to install, nothing
to compile, and the only way it can fail is if the data is wrong, which is the failure worth seeing.

## The three screens

**Criteria review** (`#/trial/<nct>`) — one trial, approved once. The protocol's own words sit on
the left of every row and everything Caliper derived sits on the right: the deterministic English
rendering of the compiled predicate, the critic's verdict on whether that rendering still says what
the protocol said, and the terminology attached. Two things get more room than their share of the
page — the criteria the compiler would not formalise, and the ones the critic withdrew — because
those are the criteria a person will have to read for every patient, forever. Above them, the
protocol is drawn as a scale: one tick per segmented span, filled where a criterion quotes it,
outlined where the claim rests only on a parent, a stub where nobody went near it.

**Screening queue** (`#/queue/<nct>`) — a cohort against that trial. One row per patient with the
verdict, how many criteria resolved out of how many, and what stands between the screening and a
decision. It sorts and filters by verdict, and its default order is an opinion: nearest to a
decision first, ranked by the gaps a FHIR query would close. A patient blocked by one missing lab is
a phone call; a patient blocked by nine is not; and a patient blocked only by criteria that need a
person reading the protocol is neither, which is why those are counted in their own column. Where a
cohort mixes recorded charts with constructed ones it also filters on that, and sorts constructed
screenings directly beneath the chart they were built from.

**Screening packet** (`#/packet/<nct>/<patient>`) — one patient. The verdict, any approximation the
verdict rests on, and then the open items before anything else, each with the missing datum, where
to look, and a FHIR query to copy where a query exists. Then the full criterion table with the
evidence behind every row: the value, its unit, its date and the `Bundle.entry[n].resource` pointer,
together. A screening that is already decided leads with the criterion that decided it and raises no
worklist, because evidence found now could not change the answer.

## Reading the marks

The three criterion verdicts differ in shape, fill and border, never in colour:

| Verdict | Glyph | Chip |
| --- | --- | --- |
| Met | filled square — the measurement was taken and it landed | solid border |
| Not met | struck square — taken, and it failed | solid ink fill, reversed out |
| Unresolved | open bracket and a caret — unfinished work with a next action | dashed border |

Screening outcomes use the printed packet's border vocabulary: a solid rule for eligible, a double
rule for not eligible, a dashed rule for a screening still open.

A chart that was edited before it was screened is hatched — the notation a drawing uses for
material that has been cut into. It is a texture rather than a colour or an icon, so it survives a
greyscale printout, and it never sits on the edge that carries the verdict.

## Layout of the source

```
index.html      the shell: a header, a main region, and a live region for announcements
styles.css      one stylesheet; the substrate rule and the accent rule are stated at the top
app.js          the hash router and the header
lib/dom.js      element building through textContent, so data can never become markup
lib/store.js    one fetch per document, cached for the life of the page
lib/marks.js    the verdict glyphs and the two counting devices that reuse them
lib/format.js   formatting only; every label a coordinator acts on travels in the export
views/          one module per screen
data/           written by `caliper ui demo`
```
