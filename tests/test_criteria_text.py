"""Segmenting a registry eligibility blob into criterion-sized spans.

ClinicalTrials.gov stores inclusion and exclusion criteria as one free-text field, formatted by
whoever registered the trial. Doing this deterministically, before any model sees the text, buys
two things: the model gets a bounded job, and we get a completeness check — a span that no compiled
criterion claims is a span we silently dropped.
"""

from caliper.criteria_text import Section, segment, unescape_registry_markdown

BULLETS = (
    "Inclusion criteria :\n\n"
    "* Type 2 Diabetes Mellitus with glycosylated hemoglobin (HbA1c) ≥7%.\n"
    "* Estimated glomerular filtration rate (eGFR) ≥25 and ≤60 mL/min/1.73 m^2.\n\n"
    "Exclusion criteria:\n\n"
    "* Antihyperglycemic treatment has not been stable within 12 weeks prior to screening.\n"
    "* Planned coronary procedure or surgery after randomization.\n"
)

NUMBERED = (
    "Inclusion Criteria\n\n"
    "1. Age 40 to 85 years at screening.\n"
    "2. Moderate to severe COPD.\n"
    "   1. Post-bronchodilator FEV1/FVC ratio <0.70.\n"
    "   2. FEV1 between 30% and 70% predicted.\n\n"
    "Exclusion Criteria\n\n"
    "1. Current smoker.\n"
)

BOILERPLATE = (
    "Inclusion Criteria:\n\n"
    "* Age 18 years or older.\n\n"
    "The above information is not intended to contain all considerations relevant to a "
    "participant's potential participation in a clinical trial.\n"
)


class TestUnescaping:
    def test_registry_escapes_are_removed(self):
        assert unescape_registry_markdown(r"eGFR \<90 mL/min/1.73 m\^2") == (
            "eGFR <90 mL/min/1.73 m^2"
        )

    def test_escaped_brackets_survive_as_brackets(self):
        escaped = r"HbA1c \[48 - 91 mmol/mol\]"
        assert unescape_registry_markdown(escaped) == "HbA1c [48 - 91 mmol/mol]"

    def test_text_without_escapes_is_untouched(self):
        assert unescape_registry_markdown("HbA1c ≥ 7%") == "HbA1c ≥ 7%"


class TestSectioning:
    def test_a_header_with_a_space_before_the_colon_is_still_a_header(self):
        spans = segment(BULLETS)
        assert {s.section for s in spans} == {Section.INCLUSION, Section.EXCLUSION}

    def test_items_are_assigned_to_the_section_that_precedes_them(self):
        spans = segment(BULLETS)
        inclusion = [s.text for s in spans if s.section is Section.INCLUSION]
        assert len(inclusion) == 2
        assert inclusion[0].startswith("Type 2 Diabetes Mellitus")

    def test_a_header_without_a_colon_still_opens_a_section(self):
        spans = segment(NUMBERED)
        assert [s.section for s in spans].count(Section.EXCLUSION) == 1


class TestListFormats:
    def test_asterisk_bullets_are_split(self):
        assert len(segment(BULLETS)) == 4

    def test_numbered_items_are_split(self):
        top_level = [s for s in segment(NUMBERED) if s.parent_index is None]
        assert len(top_level) == 3

    def test_indented_items_are_recorded_as_children_of_the_item_above(self):
        spans = segment(NUMBERED)
        children = [s for s in spans if s.parent_index is not None]
        assert len(children) == 2
        parent = spans[children[0].parent_index]
        assert parent.text.startswith("Moderate to severe COPD")

    def test_a_child_keeps_its_parents_section(self):
        spans = segment(NUMBERED)
        children = [s for s in spans if s.parent_index is not None]
        assert all(c.section is Section.INCLUSION for c in children)


class TestNoise:
    def test_the_registry_boilerplate_sentence_is_not_a_criterion(self):
        spans = segment(BOILERPLATE)
        assert len(spans) == 1
        assert spans[0].text.startswith("Age 18")

    def test_prose_without_list_markers_is_split_into_lines(self):
        text = (
            "Inclusion Criteria:\n"
            "Male or female patients aged 18 years or older.\n"
            "Documented type 2 diabetes for at least 6 months.\n"
        )
        assert len(segment(text)) == 2

    def test_blank_lines_do_not_become_spans(self):
        assert all(s.text.strip() for s in segment(BULLETS))


class TestTraceability:
    def test_every_span_points_back_at_its_place_in_the_source(self):
        spans = segment(BULLETS)
        for span in spans:
            assert BULLETS[span.char_start : span.char_end] == span.text

    def test_spans_are_numbered_in_document_order(self):
        spans = segment(BULLETS)
        assert [s.index for s in spans] == [0, 1, 2, 3]
        assert [s.char_start for s in spans] == sorted(s.char_start for s in spans)

    def test_text_with_no_recognisable_header_still_yields_spans(self):
        """Some registrations omit headers entirely; losing the whole trial is not acceptable."""
        spans = segment("* Age 18 years or older.\n* Able to give consent.\n")
        assert len(spans) == 2
        assert all(s.section is Section.UNSPECIFIED for s in spans)
