# Agents

Two different things in this repository are called agents, and conflating them makes both harder to
judge. This file separates them.

- **The agents inside Caliper** are part of the product. They run when a coordinator screens a
  patient, and their behaviour is what the evaluation measures.
- **The coding agents that built Caliper** are part of the process. They wrote the code and are not
  present at run time.

Both are disclosed below, with representative trajectories for each in [`trajectories/`](trajectories/).

---

## Part one — the agents inside Caliper

Five, each with one job, each with its instructions committed as a file rather than embedded in
code. The instructions are in [`src/caliper/agents/prompts/`](src/caliper/agents/prompts/) and are
loaded at import; changing one is a reviewable diff.

| Agent | Instructions | What it is given | What it returns | Where the guard is |
|---|---|---|---|---|
| **compiler** | [`compiler.md`](src/caliper/agents/prompts/compiler.md) | one span of protocol text, plus its section and any sub-conditions | one compiled predicate, or `is_criterion: false` | the returned quote must appear verbatim in the protocol, or the criterion is downgraded to unresolved |
| **resolver** | [`resolver.md`](src/caliper/agents/prompts/resolver.md) | one clinical concept as the protocol wrote it | candidate terminology codes with a confidence | anything below high confidence is discarded; every code must match its system's shape |
| **critic** | [`critic.md`](src/caliper/agents/prompts/critic.md) | two English sentences — the protocol's, and a deterministic rendering of the predicate | whether they mean the same thing, and how they differ | anything other than *equivalent* downgrades the criterion |
| **extractor** | [`extractor.md`](src/caliper/agents/prompts/extractor.md) | one clinical note and the concepts this trial needs | which concepts the note asserts, in which sense | only `present` and `absent` survive; the quoted sentence must appear verbatim in the note |
| **writer** | [`writer.md`](src/caliper/agents/prompts/writer.md) | one criterion, its verdict and its evidence | one sentence for the packet | every number and date is checked against that criterion's own values; two failures fall back to machine prose |

**None of them decides eligibility.** The verdict comes from `caliper/evaluate.py` and
`caliper/screen.py`, which have no import path to this package — the dependency runs one way, and a
test asserts it.

Three design choices are worth stating because they are what the trajectories show:

**Each agent is asked one small question at a time.** The compiler sees one criterion, not a
protocol. The critic compares two sentences, not a data structure. The writer produces one sentence
for one criterion, because the values a sentence may use are the ones that criterion resolved from,
and asking for forty sentences at once would put them all in one permitted set.

**Every agent's output passes a check written in code.** Not another model. A verbatim quote match,
a shape check on a code, a token-binding check on a sentence. The checks are small, boring, and the
reason the system can be argued with.

**Refusing is a first-class answer.** A criterion the compiler cannot formalise, a concept the
resolver will not code, a note sentence the extractor reads as a relative's history — each is a
normal outcome that the pipeline carries forward, not an error to be retried away.

### Reading a trajectory

`caliper trajectory eval/results/trajectory.jsonl` renders a run as Markdown: for every call, the
agent's standing instructions, what it was sent, what came back, anything that failed validation,
what was retried, and the cost. `trajectories/` holds one representative run for each agent, and
`trajectories/README.md` explains what to look for in each.

The retries are the interesting part. A trajectory where nothing ever failed validation would mean
the checks were not doing anything.

---

## Part two — the coding agents that built it

Caliper was built with **Claude Code** (Anthropic), driving Claude models. The challenge requires
disclosing this, and the working method is itself worth describing, because it is the same shape as
the product.

### How the work was divided

One orchestrating session held the architecture, the contracts between modules, and the deterministic
core — the three-valued logic, the evaluator, the IR, the screening rollup, the prose linter, the
metrics. Everything that decides something was written and reviewed in one place.

Around it, subagents were dispatched in parallel with **scoped file ownership**: each was given an
explicit list of files it could touch, told which files to read first for the contracts it had to
satisfy, and told to report rather than edit anything outside its scope. That constraint did most of
the work. Two agents never raced on the same file, and every cross-module change came back as a
written recommendation the orchestrator could accept, refuse, or implement differently.

Work that went out this way: the FHIR ingestion layer, the provider runtime and cassette recording,
the data acquisition scripts, the four peripheral agents above, the chart summariser and perturbation
tooling, the evaluation annotation, the metamorphic suite, and the web interface.

### What that produced, and what it cost

The recommendations that came back were the most valuable output, more than the code. Several of the
findings in [`LIMITS.md`](LIMITS.md) and several bugs fixed in this repository originated as an agent
saying "I could not do this cleanly, and here is why" rather than working around it:

- the evaluator was deciding criteria from evidence dated *after* the screening date, because a
  criterion with no temporal window accepted any date at all;
- one patient in the corpus died four weeks before the fixed screening date, and the ingestion layer
  was dropping `deceasedDateTime` entirely, so that chart read as an ordinary screenable patient;
- a third of the medication records carried no drug identity, because Synthea writes them as a
  reference to a resource the corpus trimming had removed;
- the prose linter's rounding rule let a threshold of 1.5 vouch for a sentence saying "2".

None of those were visible from the outside. All of them came from an agent reading one layer
closely enough to notice that something did not fit.

### One agent was pointed at the documentation instead of the code

The last substantial piece of work in this repository was not a feature. An agent was given the
public documents, the committed results, and one instruction: be the judge who checks, find every
sentence the repository itself refutes, and **report rather than fix**.

That constraint is the interesting part. An agent that fixes what it finds produces a clean tree and
no list; an agent that only reports produces a list somebody has to act on, one item at a time, which
is where the judgement belongs. It found twenty-two, including the two most damaging problems in the
submission — a metric whose name and definition had drifted apart, and three required files an
unanchored `.gitignore` rule had kept out of every clone. `CHANGELOG.md` has the full account.

It went at this file too, which is the right way round: a process description is a claim like any
other. One claim here was refuted — the sentence above pointing at `trajectories/` for the coding
agents, which was true of the working tree and false of every clone. One was confirmed the hard way:
"one commit whose test suite did not parse", below, was checked by parsing every test file at every
commit in the history, and there is exactly one.

### Discipline that was enforced, not hoped for

- **Tests first.** Every module in this repository was specified as failing tests before it existed.
  The suite is over 1,100 tests and most of it was written before the code it covers.
- **A shared fake provider.** `tests/fakes.py` lets every agent be exercised offline, with replies
  routed by which agent is asking rather than by call order — because the retry ladder decides how
  many turns one logical call takes, and a test counting replies would really be testing the ladder.
- **No agent could commit.** Every commit in the history was made by the orchestrator after running
  the full suite and the linter.

### What went wrong

Worth recording, because a process description with no failures in it is not a description.

An agent working mid-flight had its unfinished test file swept into a commit by another agent's
staging, producing one commit whose test suite did not parse. It was caught by the next full run and
superseded. The lesson was that scoped *file ownership* is not the same as scoped *staging*, and
commits were made file-by-file afterwards rather than with `git add -A`.

Two agents also independently proposed changes to files they did not own — one wanting a new
`EvidenceKind` for clinical notes, one wanting an explicit anchor field on temporal windows. Both
were right, both were implemented in the core, and both would have been silent divergences if the
agents had been allowed to edit freely.
