# Trajectories

Two kinds of agent worked on this project, and they leave two different kinds of record.

## `product/` — the agents inside Caliper

Generated from the committed run. Each file is one agent's calls in order: its standing
instructions, what it was sent, what came back, anything that failed validation, what it did next,
and what it cost.

Regenerate any of them from the recorded run:

```bash
caliper trajectory eval/results/trajectory.jsonl --out trajectories/product/run.md
caliper tape --agent compiler --limit 20        # what one agent was asked, and said
```

The retries are the part worth reading. A run in which nothing ever failed validation would mean
the checks were not doing anything — so the interesting lines are the ones where a compiler quoted
the protocol inexactly and the criterion was downgraded, or where a written sentence used a number
the evidence did not support and was sent back.

## `build/` — the coding agents that wrote Caliper

These are not generated. They are curated records of three exchanges that changed the design, each
following one agent from the brief it was given to what happened as a result.

They are here because the interesting artefact of the build was not the code the agents produced.
It was the disagreements: three of the four bugs listed in `CHANGELOG.md` arrived as an agent
saying "I could not do this cleanly, and here is why" rather than working around it.

| File | What it shows |
|---|---|
| [`fhir-loader.md`](build/fhir-loader.md) | An agent refusing to implement its brief as written, because the brief was wrong |
| [`critic-anchor.md`](build/critic-anchor.md) | A finding that was fixed in the wrong place first, and moved |
| [`answer-key.md`](build/answer-key.md) | Work delivered to spec and sent back anyway, because the spec had a hole |

**How these were edited.** The briefs are reproduced as they were sent, with two changes: passages
about contest scoring are removed, because they say nothing about the engineering, and long file
listings are trimmed with an ellipsis. The agents' reports are quoted from their own summaries and
are otherwise unedited. Nothing was added after the fact to make a decision look better than it was.
