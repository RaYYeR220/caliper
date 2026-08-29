"""The parts of Caliper that use a language model.

Five agents, each with one job it can be judged on:

* `compiler` turns one span of protocol text into one compiled criterion, or says it cannot.
* `resolver` attaches terminology codes to a concept, backed by a store that remembers.
* `critic` reads a compiled criterion back into English and checks it still says what the
  protocol said.
* `extractor` reads a clinical note and says which concepts it asserts about *this* patient, so
  that prose can become coded evidence instead of being matched by wording.
* `writer` produces the sentence a coordinator reads, which the prose linter then checks.

Nothing here decides eligibility. The verdict comes from `caliper.evaluate`, which cannot reach
this package: the import goes one way, deliberately.
"""

from caliper.agents.base import AgentContext

__all__ = ["AgentContext"]
