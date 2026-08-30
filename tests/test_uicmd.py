"""The trial fixtures the interface is built from.

`caliper ui build` runs the real pipeline stages over hand-written criteria sets rather than
calling a model, so the screens are reproducible without a key. That is only honest while the
fixtures say what the compiler said, and the settlement split is the part most tempting to
improve on: marking one more criterion as a question for the visit would turn a needs-review
screen into an eligible one. These tests hold the split to the run.
"""

from __future__ import annotations

from caliper import corpus
from caliper.criteria_text import unescape_registry_markdown
from caliper.ir import UnsupportedPredicate
from caliper.uicmd import _COMPILATIONS


class TestSettlement:
    """Which of the demo trial's unanswerable criteria are questions for the visit.

    The fixture claims to be what the pipeline produces, so the split has to be the one the
    compiler actually made on this protocol — not a more flattering one. These two lists are the
    live run's, and locking them here is what stops the interface from quietly becoming a nicer
    demo than the system.
    """

    AT_VISIT = {
        "NCT01131676": {"INC-06", "EXC-03", "EXC-08", "EXC-13", "EXC-14"},
        "NCT03315143": {"INC-04", "EXC-02", "EXC-04"},
    }

    def unsupported(self, nct_id: str) -> dict[str, str]:
        build, _table = _COMPILATIONS[nct_id]
        criteria_set = build(unescape_registry_markdown(corpus.load_trial(nct_id).criteria_text))
        return {
            criterion.id: criterion.predicate.settlement
            for criterion in criteria_set.criteria
            if isinstance(criterion.predicate, UnsupportedPredicate)
        }

    def test_the_visit_questions_are_the_ones_the_compiler_found(self):
        for nct_id, expected in self.AT_VISIT.items():
            settlement = self.unsupported(nct_id)
            at_visit = {cid for cid, kind in settlement.items() if kind == "at_visit"}
            assert at_visit == expected, nct_id

    def test_everything_else_unanswerable_still_blocks_the_verdict(self):
        for nct_id, expected in self.AT_VISIT.items():
            settlement = self.unsupported(nct_id)
            assert {cid for cid in settlement if cid not in expected}
            assert all(settlement[cid] == "from_data" for cid in settlement if cid not in expected)

    def test_a_consent_criterion_is_never_treated_as_a_gap_in_the_record(self):
        for nct_id in self.AT_VISIT:
            build, _table = _COMPILATIONS[nct_id]
            criteria_set = build(
                unescape_registry_markdown(corpus.load_trial(nct_id).criteria_text)
            )
            for criterion in criteria_set.criteria:
                if "informed consent" in criterion.source_quote.lower().split(" prior")[0][:40]:
                    assert isinstance(criterion.predicate, UnsupportedPredicate)
                    assert criterion.predicate.settlement == "at_visit"
