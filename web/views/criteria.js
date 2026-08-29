/* Screen one: what the compiler made of one protocol.
 *
 * This is the screen a coordinator signs off once. Approving a compilation is a statement about the
 * trial, not about a patient, so every patient screened against it afterwards inherits the
 * approval — which is why it is worth reading forty criteria carefully here rather than skimming
 * them once per chart.
 *
 * Two things are given more room than their share of the page: the criteria that were never
 * formalised, and the ones the critic withdrew. Everything else on this screen will resolve itself
 * from a chart. Those will not, for any patient, ever.
 */

import { h } from "../lib/dom.js";
import { capitalise, plural } from "../lib/format.js";
import { loadTrial } from "../lib/store.js";

const CLAIM_WORDS = {
  direct: "quoted by a criterion",
  inherited: "claimed only through its parent",
  unclaimed: "claimed by nothing",
};

function stat(value, label, quiet) {
  return h(
    "div",
    { class: quiet ? "stat stat--quiet" : "stat" },
    h("span", { class: "stat__value" }, String(value)),
    h("span", { class: "stat__label" }, label),
  );
}

/* The protocol as a ruler: one tick per segmented span, in document order, drawn to one width.
 * A reader who has never met this system can see in one glance whether the compiler covered the
 * document or left holes in it. */
function scale(coverage) {
  const readout = h("p", { class: "scale__readout", "aria-hidden": "true" });
  const show = (span) => {
    readout.replaceChildren(
      h("span", { class: "micro" }, `Span ${span.index + 1}`),
      h("span", {}, span.text),
    );
  };
  const clear = () => readout.replaceChildren(
    h("span", { class: "micro" }, "Span"),
    h("span", { class: "note" }, "Point at a tick to read the protocol span it stands for."),
  );
  clear();

  const ticks = coverage.spans.map((span) =>
    h(
      "li",
      {},
      h("button", {
        type: "button",
        class: `tick tick--${span.claim}`,
        "aria-label":
          `Span ${span.index + 1} of ${coverage.total}, ${span.section}, ` +
          `${CLAIM_WORDS[span.claim]}: ${span.text}`,
        onmouseenter: () => show(span),
        onfocus: () => show(span),
        onmouseleave: clear,
        onblur: clear,
        onclick: () => show(span),
      }),
    ),
  );

  return h(
    "section",
    { class: "scale", "aria-label": "Protocol coverage" },
    h("ol", { class: "scale__ticks" }, ticks),
    readout,
    h(
      "ul",
      { class: "scale__legend" },
      h("li", {}, h("i", { class: "tick tick--direct" }), `${coverage.direct} quoted`),
      h("li", {}, h("i", { class: "tick tick--inherited" }), `${coverage.inherited} through a parent`),
      h("li", {}, h("i", { class: "tick tick--unclaimed" }), `${coverage.unclaimed} unclaimed`),
    ),
  );
}

function spanList(spans) {
  return h(
    "ul",
    { class: "stack" },
    spans.map((span) =>
      h(
        "li",
        {},
        h("span", { class: "micro" }, `Span ${span.index + 1} · ${span.section}`),
        h("blockquote", {}, h("p", {}, span.text)),
      ),
    ),
  );
}

function coverageSection(coverage) {
  const unclaimed = coverage.spans.filter((s) => s.claim === "unclaimed");
  const inherited = coverage.spans.filter((s) => s.claim === "inherited");

  const blocks = [];
  if (unclaimed.length) {
    blocks.push(
      h(
        "div",
        { class: "panel panel--double" },
        h("h3", {}, `${plural(unclaimed.length, "span")} no criterion claims`),
        h(
          "p",
          { class: "note" },
          "A dropped bullet is the compiler failure that hides best: every criterion that did " +
            "survive still looks correct. Read these against the protocol before approving.",
        ),
        spanList(unclaimed),
      ),
    );
  }
  if (inherited.length) {
    blocks.push(
      h(
        "div",
        { class: "panel panel--dashed" },
        h("h3", {}, `${plural(inherited.length, "span")} claimed only through a parent`),
        h(
          "p",
          { class: "note" },
          "No criterion quotes these directly. A sub-bullet usually qualifies the bullet above " +
            "it, so this is the expected reading — but a compiler that quoted the parent and " +
            "dropped the threshold underneath it would look exactly like this.",
        ),
        spanList(inherited),
      ),
    );
  }
  if (!blocks.length) {
    blocks.push(
      h(
        "p",
        { class: "note" },
        "Every span of this protocol is quoted directly by a criterion. Nothing was dropped and " +
          "nothing rests on a parent.",
      ),
    );
  }
  return blocks;
}

function unsupportedPanel(title, lede, criteria, modifier) {
  if (!criteria.length) return null;
  return h(
    "div",
    { class: `panel ${modifier}` },
    h("h3", {}, `${plural(criteria.length, "criterion", "criteria")} ${title}`),
    h("p", { class: "note" }, lede),
    h(
      "ul",
      { class: "stack" },
      criteria.map((criterion) =>
        h(
          "li",
          {},
          h(
            "div",
            { class: "stack__head" },
            h("span", { class: "id" }, criterion.id),
            h("span", { class: "kind" }, capitalise(criterion.kind)),
          ),
          h("blockquote", {}, h("p", {}, criterion.source_quote)),
          h(
            "p",
            { class: "reason" },
            criterion.critic
              ? [
                  h("span", { class: "severity" }, criterion.critic.severity),
                  criterion.critic.reason,
                ]
              : criterion.unsupported_reason,
          ),
        ),
      ),
    ),
  );
}

function compiledCell(criterion) {
  const critic = criterion.critic;
  if (critic && critic.downgraded) {
    return h(
      "td",
      {},
      h("del", { class: "withdrawn" }, critic.reviewed_rendering),
      h(
        "p",
        { class: "reason" },
        "Withdrawn. Caliper reports this criterion unresolved for every patient rather than " +
          "running a predicate that does not match the protocol.",
      ),
    );
  }
  if (criterion.unsupported) {
    return h(
      "td",
      {},
      h("span", { class: "micro" }, "Not formalised"),
      h("p", { class: "reason" }, criterion.unsupported_reason),
    );
  }
  return h(
    "td",
    {},
    criterion.compiled_as,
    criterion.notes ? h("span", { class: "engine" }, criterion.notes) : null,
  );
}

function criticCell(criterion) {
  const critic = criterion.critic;
  if (!critic) {
    return h(
      "td",
      { class: "note" },
      "Not reviewed. Nothing was formalised to compare against the quote.",
    );
  }
  return h(
    "td",
    {},
    h("span", { class: `severity severity--${critic.severity}` }, critic.severity),
    h("span", {}, critic.reason),
  );
}

function codesCell(criterion) {
  if (!criterion.codes.length) return h("td", { class: "none" }, "none attached");
  return h(
    "td",
    {},
    h(
      "ul",
      { class: "codes" },
      criterion.codes.map((code) =>
        h("li", { title: code.display || "" }, `${code.system} ${code.code}`),
      ),
    ),
  );
}

function criteriaTable(trial) {
  return h(
    "div",
    { class: "scroller" },
    h(
      "table",
      {},
      h(
        "thead",
        {},
        h(
          "tr",
          {},
          h("th", { scope: "col" }, "Criterion"),
          h("th", { scope: "col" }, "The protocol says"),
          h("th", { scope: "col" }, "Compiled to"),
          h("th", { scope: "col" }, "The critic read it back as"),
          h("th", { scope: "col" }, "Terminology"),
        ),
      ),
      h(
        "tbody",
        {},
        trial.criteria.map((criterion) =>
          h(
            "tr",
            { id: `criterion-${criterion.id}` },
            h(
              "td",
              {},
              h("div", { class: "id" }, criterion.id),
              h("div", { class: "kind" }, capitalise(criterion.kind)),
            ),
            h("td", { class: "protocol" }, criterion.source_quote),
            compiledCell(criterion),
            criticCell(criterion),
            codesCell(criterion),
          ),
        ),
      ),
    ),
  );
}

export async function renderCriteria(nctId) {
  const trial = await loadTrial(nctId);
  const counts = trial.counts;
  const executable = counts.criteria - counts.unsupported;
  const neverFormalised = trial.criteria.filter((c) => c.unsupported && !c.critic);
  const withdrawn = trial.criteria.filter((c) => c.unsupported && c.critic);

  const content = h(
    "div",
    { class: "page" },
    h(
      "header",
      { class: "page__head" },
      h("p", { class: "eyebrow" }, `Criteria review · ${trial.nct_id}`),
      h("h1", {}, trial.title),
      h(
        "p",
        { class: "lede subtitle" },
        "This compilation is approved once and inherited by every patient screened against the " +
          "trial. The protocol's own words are on the left of each row; everything to the right " +
          "of them was produced by Caliper.",
      ),
      h(
        "div",
        { class: "stats" },
        stat(counts.criteria, "criteria compiled"),
        stat(executable, "run against the chart"),
        stat(counts.unsupported, "need a person"),
        stat(counts.downgraded, "withdrawn by the critic"),
        stat(`${coverageFraction(trial)}`, "protocol spans claimed", true),
      ),
    ),

    h("h2", {}, "Coverage of the protocol"),
    scale(trial.coverage),
    ...coverageSection(trial.coverage),

    h("h2", {}, "What a person will always have to read"),
    h(
      "p",
      { class: "lede" },
      `${plural(counts.unsupported, "criterion", "criteria")} of ${counts.criteria} will report ` +
        "unresolved for every patient, whatever their chart says. Naming them is the point: a " +
        "coordinator reads these, and Caliper reads the rest.",
    ),
    unsupportedPanel(
      "the compiler would not formalise",
      "Each of these was recorded as unsupported rather than guessed at. The reason is the " +
        "compiler's own.",
      neverFormalised,
      "panel--dashed",
    ),
    unsupportedPanel(
      "the critic withdrew",
      "These compiled to a predicate that did not survive being read back into English and " +
        "compared with the protocol. Anything other than an exact match fails closed, because a " +
        "criterion narrower than the protocol screens out patients the trial wanted.",
      withdrawn,
      "panel--double",
    ),

    h("h2", {}, "Every criterion"),
    h(
      "p",
      { class: "note" },
      "Protocol text sits on paper. Everything Caliper derived sits on the panel.",
    ),
    criteriaTable(trial),
  );

  return { title: `Criteria review · ${trial.nct_id}`, content };
}

function coverageFraction(trial) {
  const { claimed, total } = trial.coverage;
  return `${claimed}/${total}`;
}
