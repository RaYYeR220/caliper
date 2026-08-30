# Reproducing the results

Written for someone starting from an empty directory, with no Python installed and no API key.

Everything in `RESULTS.md` comes from one run. That run is committed — the model's responses are
recorded, so reproducing it needs no provider, no network and no money. The live path exists too,
and is described at the end along with what it costs and how far it drifts.

---

## The short version

```bash
git clone <this repository>
cd caliper
docker build -t caliper .
docker run --rm caliper
```

That prints the results table. It takes about a minute, most of it building the image.

The container is the check, not a convenience. Every arm in it reports figures identical to a host
run — which was **not** true the first time it was tried: a cold terminology store made the same
tape produce eleven different verdicts with nothing on stdout to say so. `CHANGELOG.md` records
what that was and what now makes it loud instead of silent. If your container disagrees with this
table, that is a bug and we would like to hear about it.

---

## Without Docker

**Requirements:** Python 3.12 or newer, and [`uv`](https://docs.astral.sh/uv/) (or plain `pip`).

```bash
uv venv --python 3.12
uv pip install -e ".[dev]"
```

With plain `pip`:

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"        # .venv\Scripts\pip on Windows
```

Then, in order:

```bash
caliper data verify        # 1. the fixtures are the ones the report was built from
caliper eval --replay      # 2. the headline result, replayed. No key needed.
caliper report             # 3. rebuild RESULTS.md from step 2
pytest                     # 4. the test suite, including the metamorphic checks
```

`make eval` and `make test` do the same things if you prefer. `make` is not required — every target
is one `caliper` command, which is deliberate: the commands work identically on Windows.

### What each step should print

**`caliper data verify`** — one line per problem, then a count. Expect

```
49 files verified
```

If it reports a changed file, stop: the numbers in `RESULTS.md` were produced from different bytes
and nothing below is meaningful.

**`caliper eval --replay`** — one line per arm as it finishes, then a table of every arm with its
accuracy, coverage, unsafe errors and cost. The replayed cost is zero. Roughly one minute.

**`caliper report`** — writes `RESULTS.md`. Use `make eval && make report` rather than the bare
commands: the committed `RESULTS.md` carries a second table scoring the same recorded decisions
against the *earlier* answer key, and that needs both `eval/results/` and `eval/results-v1/`, which
is what the `make` targets produce. `caliper eval --replay` followed by a bare `caliper report`
writes a valid file twenty lines shorter, missing that section, and you would be right to wonder
why it differed from the committed one.

The comparison is there because the key was corrected after a scored run, which is the least
trustworthy moment to correct one. It did not move the conclusion: which arms committed an unsafe
error is identical under both keys.

`RESULTS.md` **is** committed, so `git diff --stat RESULTS.md` after `make eval && make report` is a
real check and should come back empty. The file is generated rather
than committed, so there is nothing to diff it against: run step 2 twice and `caliper report` twice
and the two `RESULTS.md` must be byte-identical, which is what `caliper eval --replay` being a
replay means. Every figure in it is computed from `eval/results/`; none is typed by hand.

**`pytest`** — the whole suite, about twenty-five seconds on an ordinary laptop. It includes the metamorphic suite, which needs
no model at all: those cases assert a required relationship between two runs (redact the only
creatinine and the criterion that used it *must* become unresolved) rather than asserting an answer,
so they hold whatever anyone believes about the answer key.

---

## The data

Nothing is downloaded at run time. Both corpora are committed with digests.

| What | Where | Source |
|---|---|---|
| 10 trials | `data/trials/` | ClinicalTrials.gov API v2, raw JSON, unmodified |
| 24 patients | `data/patients/` | Synthea (MITRE), trimmed to ten resource types |
| 21 clinical notes | `data/notes/` | Hand-authored for this project |

`data/DATA_SOURCE.md` records the registry's own processing date, the pinned commit and archive
digest for the Synthea sample, and every modification made. `scripts/fetch_trials.py` and
`scripts/build_patient_corpus.py` rebuild the fixtures from source; you do not need to run them, and
running them will produce a different snapshot because the registry moves.
`scripts/summarise_patients.py` (`make charts`) regenerates `eval/charts/`, the chart summaries the
annotators worked from — worth knowing about, because what the annotators saw is what the answer key
rests on.

---

## Running it live

A live run calls a provider. It costs money and it will not reproduce byte for byte — see
"Determinism" below.

```bash
cp .env.example .env       # then put a key in it
caliper eval --record      # calls the provider and rewrites eval/tape.jsonl
```

`CALIPER_PROVIDER` and `CALIPER_MODEL` select the provider and model; the defaults are Venice with
`claude-sonnet-5`. Any OpenAI-compatible endpoint works — `caliper` uses the stock `openai` client
against a configured base URL, and the provider profile carries whatever non-standard body each
provider needs.

**Cost and runtime for one full evaluation** (all eleven arms over the answer key):

| | |
|---|---|
| Model calls | 767: 479 compiler, 213 critic, 51 baseline, and 24 resolver steps that cost nothing |
| Tokens | 8.3 million, overwhelmingly prompt rather than completion |
| Cost | $22.61 at `claude-sonnet-5` list prices |
| Wall clock | an hour and a half, dominated by rate limits rather than compute |

Read those out of the recording rather than from here: `caliper costs eval/results/trajectory.jsonl`
prints the first three broken down by agent and by model, and its total is the same figure the cost
column in `RESULTS.md` sums to. The compiler dominates because it is asked one criterion at a time —
that is the choice entry 4 in `CHANGELOG.md` describes, and this is its price. The resolver's
twenty-four steps carry no tokens and no cost because every one of them was served by the
terminology store rather than by a model; the store is what makes the second trial nearly free, and
`caliper costs` prints those steps as unpriced rather than hiding them.

`caliper costs eval/results/trajectory.jsonl` breaks the actual figure down by agent and by model,
and `caliper tape` shows what was asked to produce it.

Single pieces, if you want to watch one:

```bash
caliper compile NCT03315143 --out /tmp/criteria.json
caliper screen NCT03315143 <patient-id> --packet /tmp/packet.html
caliper data patients            # patient ids
```

---

## Determinism

The replayed result is byte-identical, because it does not involve a model.

A live run is not, and we do not claim it is. Temperature zero does not make a hosted model
deterministic: providers batch requests, and the reduction order inside a batched kernel depends on
what else was in the batch. A fixed seed only controls the sampler, which at temperature zero is
already doing nothing. We set `temperature=0`, `top_p=1` and a fixed seed anyway, as variance
reduction rather than as a guarantee, and pin the exact model identifier.

What carries the reproducibility claim instead is the recording, in `eval/tape.jsonl`. It is kept at
the level of the exchange rather than the socket: one JSON object per model call, carrying the
system prompt, the question, the answer and the token usage. A packet capture would prove traffic
moved; it would not let you read what the compiler was asked about criterion four and decide whether
the answer was reasonable. `caliper tape --agent compiler` prints exactly that.

The key includes the model, the whole message list and the name of the schema demanded back. The
system prompt has to be part of it: several agents are asked about the same protocol text in one
run, and a key built from the question alone would hand the critic the compiler's answer. A request
the tape has no answer for raises rather than falling through to the provider, so "this ran offline"
is a fact rather than a hope. Nothing but the conversation is recorded, so no header and no key can
end up in the file, and a test asserts it.

---

## The interface

```bash
caliper ui demo            # builds web/data/ from the committed fixtures
cd web && python -m http.server 8000
```

Then open `http://localhost:8000`. There is no build step and nothing is fetched from a CDN, so it
works offline and on a machine with no Node installed.

---

## If something fails

| Symptom | Cause |
|---|---|
| `data verify` reports a changed file | The fixtures were edited. Re-clone; do not proceed. |
| `eval` reports the key does not match its digest | `eval/answer_key.json` was edited after freezing. Scoring against it would prove nothing, so the command refuses. |
| `eval --replay` raises `TapeMiss` | A request was made that the recording does not contain, which means a prompt or the model changed since it was recorded. The error prints what was asked. Re-record with a key, or check out the commit the tape belongs to. |
| `no API key found in VENICE_API_KEY` | You ran a live command. The replay path needs no key. |
| Tests fail on Windows with line-ending noise | `git config core.autocrlf false`, then re-clone. The repository is LF throughout. |

## Versions

Pinned in `uv.lock`, which is committed. `eval/results/run.json` records what the run did — arms,
key digest, exchange counts, cost — and not which versions produced it; if you need to reproduce the
environment exactly, `uv sync` against the lockfile is the mechanism. The figures in `RESULTS.md`
were produced on Python 3.12 with the dependency set in that lock file.
