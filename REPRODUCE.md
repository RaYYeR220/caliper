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

**`caliper report`** — rewrites `RESULTS.md`. It should come back byte-identical to the committed
copy; `git diff --stat RESULTS.md` is the check.

**`pytest`** — the whole suite, about seven seconds. It includes the metamorphic suite, which needs
no model at all: those cases assert a required relationship between two runs (redact the only
creatinine and the criterion that used it *must* become unresolved) rather than asserting an answer,
so they hold whatever anyone believes about the answer key.

---

## The data

Nothing is downloaded at run time. Both corpora are committed with digests.

| What | Where | Source |
|---|---|---|
| 10 trials | `data/trials/` | ClinicalTrials.gov API v2, raw JSON, unmodified |
| 24 patients | `data/patients/` | Synthea (MITRE), trimmed to nine resource types |
| 21 clinical notes | `data/notes/` | Hand-authored for this project |

`data/DATA_SOURCE.md` records the registry's own processing date, the pinned commit and archive
digest for the Synthea sample, and every modification made. `scripts/fetch_trials.py` and
`scripts/build_patient_corpus.py` rebuild the fixtures from source; you do not need to run them, and
running them will produce a different snapshot because the registry moves.

---

## Running it live

A live run calls a provider. It costs money and it will not reproduce byte for byte — see
"Determinism" below.

```bash
cp .env.example .env       # then put a key in it
caliper eval --record      # calls the provider and re-records the cassettes
```

`CALIPER_PROVIDER` and `CALIPER_MODEL` select the provider and model; the defaults are Venice with
`claude-sonnet-5`. Any OpenAI-compatible endpoint works — `caliper` uses the stock `openai` client
against a configured base URL, and the provider profile carries whatever non-standard body each
provider needs.

**Approximate cost and runtime for one full evaluation** (all nine arms over the answer key):

| | |
|---|---|
| Model calls | roughly 400 for compilation and criticism, plus one per case per model-backed arm |
| Cost | under two dollars at `claude-sonnet-5` list prices |
| Wall clock | ten to fifteen minutes, dominated by rate limits rather than compute |

`caliper costs eval/results/trajectory.jsonl` breaks the actual figure down by agent and by model.

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

What carries the reproducibility claim instead is the recording. `eval/cassettes/` holds the HTTP
exchanges of the committed run, matched on method, host, path **and request body** — body matching
matters, because every call in a run goes to the same URL, and a cassette matched on the URL alone
would answer the compiler with the critic's response. Authorisation headers are redacted before
anything is written, and a test greps the cassette directory to prove no key is in it.

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
| `eval --replay` raises `CannotOverwriteExistingCassette` | A request was made that the recording does not contain, which means the code changed since the recording. Re-record with a key, or check out the commit the cassettes belong to. |
| `no API key found in VENICE_API_KEY` | You ran a live command. The replay path needs no key. |
| Tests fail on Windows with line-ending noise | `git config core.autocrlf false`, then re-clone. The repository is LF throughout. |

## Versions

Recorded per run in `eval/results/run.json`, and pinned in `uv.lock`. The figures in `RESULTS.md`
were produced on Python 3.12 with the dependency set in that lock file.
