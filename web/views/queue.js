/* Screen two: a cohort against one trial.
 *
 * The default ordering is the opinion this screen holds. A screening blocked by one missing lab is
 * a phone call; a screening blocked by nine is an afternoon, and one blocked only by criteria that
 * need a human reading the protocol is not a phone call at all. So the two kinds of gap are counted
 * in separate columns and ranked in that order, and the toolbar says so in as many words — a sort
 * whose rule a coordinator cannot state is a sort they will not trust.
 *
 * Filter and sort state outlives navigation. Opening a packet and coming back to a queue that had
 * forgotten its filter is the fastest way to make a working tool feel like a demo.
 *
 * Some cohorts mix charts as they were recorded with charts that were edited to supply a
 * measurement the patient never had. That mark sits inside the identity cell, beside the
 * identifier, so it survives every filter, every sort and every column this screen may ever grow.
 * A badge that lived in a column of its own could be sorted away from the chart it qualifies, and
 * an edited chart read as a recorded one is the one mistake this interface must not permit.
 */

import { h, replace } from "../lib/dom.js";
import { chartName, plural, shortId } from "../lib/format.js";
import { outcomeMark, tickBar } from "../lib/marks.js";

const state = { verdict: "all", chart: "all", sort: "nearest", ascending: true, find: "" };

/* The queue's own wording for the three outcomes. The packet says "Needs review before a decision"
 * at the head of a document, where the sentence earns its width; twenty-four rows deep in a column
 * it is noise, so the column shows the outcome and the mark's title carries the packet's phrase. */
const SHORT_LABEL = {
  eligible: "Eligible",
  ineligible: "Not eligible",
  needs_review: "Needs review",
};

const VERDICTS = [
  ["all", "All"],
  ["needs_review", "Needs review"],
  ["ineligible", "Not eligible"],
  ["eligible", "Eligible"],
];

/* Provenance is a filter of its own, because "show me only the charts nobody edited" is the
 * question a reader asks the moment they learn that some of them were. */
const CHARTS = [
  ["all", "All"],
  ["observed", "As recorded"],
  ["constructed", "Constructed"],
];

const SORTS = {
  nearest: { label: "Nearest to a decision", ascending: true },
  patient: { label: "Chart", ascending: true },
  verdict: { label: "Verdict", ascending: true },
  resolved: { label: "Criteria resolved", ascending: false },
  retrievable: { label: "Gaps a query would close", ascending: true },
  person: { label: "Gaps needing a person", ascending: true },
  source: { label: "Constructed beneath its source chart", ascending: true, constructed: true },
};

/* How much work stands between this screening and a decision. Screenings a query could advance
 * come first, fewest gaps at the top; then the ones waiting on a person; then the settled ones. */
function distance(row) {
  if (row.decision === "needs_review") {
    return row.open_retrievable > 0
      ? [0, row.open_retrievable, row.open_needing_a_person]
      : [1, row.open_needing_a_person, 0];
  }
  return [row.decision === "eligible" ? 2 : 3, 0, 0];
}

/** The chart a row is about: for a constructed screening, the chart it was built from. */
function sourceId(row) {
  return row.constructed ? row.constructed.base_patient_id : row.patient_id;
}

const KEYS = {
  nearest: distance,
  patient: (row) => [row.patient_id],
  verdict: (row) => [["needs_review", "eligible", "ineligible"].indexOf(row.decision)],
  resolved: (row) => [row.criteria_total ? row.criteria_resolved / row.criteria_total : -1],
  retrievable: (row) => [row.open_retrievable, ...distance(row)],
  person: (row) => [row.open_needing_a_person, ...distance(row)],
  // The source chart first, then its constructed derivatives in case order. This is the ordering
  // that brings a triple together inside the queue, with the unedited chart at the head of it.
  source: (row) => [sourceId(row), row.constructed ? 1 : 0, row.constructed?.case_id || ""],
};

function compare(a, b, key, ascending) {
  const left = KEYS[key](a);
  const right = KEYS[key](b);
  for (let i = 0; i < Math.max(left.length, right.length); i += 1) {
    const l = left[i];
    const r = right[i];
    if (l === r) continue;
    const order = l < r ? -1 : 1;
    return ascending ? order : -order;
  }
  return a.patient_id < b.patient_id ? -1 : 1;
}

function matches(row) {
  if (state.verdict !== "all" && row.decision !== state.verdict) return false;
  if (state.chart === "constructed" && !row.constructed) return false;
  if (state.chart === "observed" && row.constructed) return false;
  if (!state.find) return true;
  const needle = state.find.toLowerCase();
  const haystack = [
    row.patient_id,
    row.patient_summary,
    row.blocking,
    row.blocked_by,
    row.blocking_criterion_id,
    ...row.deciding_criterion_ids,
    ...(row.constructed ? [row.constructed.case_id, ...row.constructed.edits] : []),
  ];
  return haystack.some((field) => (field || "").toLowerCase().includes(needle));
}

function resolvedCell(row) {
  if (!row.criteria_total) {
    return h("td", { class: "count-cell is-zero" }, "not evaluated");
  }
  return h(
    "td",
    { class: "count-cell" },
    h("span", {}, `${row.criteria_resolved} of ${row.criteria_total}`),
    tickBar(
      row.criteria_resolved,
      row.criteria_total,
      `${row.criteria_resolved} of ${row.criteria_total} criteria resolved`,
    ),
  );
}

function gapCell(count, unit) {
  return h(
    "td",
    { class: count ? "count-cell" : "count-cell is-zero" },
    count ? h("strong", {}, String(count)) : h("span", {}, "none"),
    count ? h("span", { class: "visually-hidden" }, ` ${unit}`) : null,
  );
}

function blockingCell(row) {
  if (row.blocked_by) {
    return h(
      "td",
      { class: "blocking" },
      h("span", { class: "micro" }, "Stopped before any criterion"),
      row.blocked_by,
    );
  }
  if (row.decision === "needs_review") {
    return h(
      "td",
      { class: "blocking" },
      h("span", { class: "micro" }, `Next, on ${row.blocking_criterion_id}`),
      row.blocking,
    );
  }
  if (row.decision === "ineligible") {
    const unresolved = row.criteria_total - row.criteria_resolved;
    return h(
      "td",
      { class: "blocking" },
      h("span", { class: "micro micro--inline" }, "Decided by"),
      h("span", { class: "id" }, row.deciding_criterion_ids.join(", ")),
      unresolved
        ? h("span", { class: "quiet" }, ` · ${unresolved} left unresolved`)
        : null,
    );
  }
  return h("td", { class: "blocking" }, h("span", { class: "micro" }, "Nothing outstanding"));
}

/* The identity cell, and the only place a constructed chart could pass for a recorded one. The
 * name carries the case, the hatched edge carries it without being read, and the line beneath says
 * how far this chart is from the one it was built from. */
function chartCell(entry) {
  const href = `#/packet/${entry.nct_id}/${encodeURIComponent(entry.patient_id)}`;
  const built = entry.constructed;
  return h(
    "td",
    { class: built ? "chart chart--constructed" : "chart" },
    h("a", { class: "patient", href }, chartName(entry.patient_id, built)),
    h("div", { class: "summary" }, entry.patient_summary),
    built
      ? h(
          "div",
          { class: "built" },
          h("span", { class: "micro micro--inline" }, "Constructed"),
          `${plural(built.edits.length, "edit")} to ${shortId(built.base_patient_id)}`,
        )
      : null,
  );
}

function row(entry) {
  return h(
    "tr",
    { class: `row--${entry.decision}` },
    h(
      "td",
      {},
      outcomeMark(entry.decision, SHORT_LABEL[entry.decision], { title: entry.decision_label }),
    ),
    chartCell(entry),
    resolvedCell(entry),
    gapCell(entry.open_retrievable, "gaps a query would close"),
    gapCell(entry.open_needing_a_person, "gaps needing a person"),
    blockingCell(entry),
  );
}

function header(key, label, rerender) {
  const active = state.sort === key;
  const props = { scope: "col" };
  if (active) props["aria-sort"] = state.ascending ? "ascending" : "descending";
  return h(
    "th",
    props,
    h(
      "button",
      {
        type: "button",
        class: "sort",
        onclick: () => {
          state.ascending = active ? !state.ascending : SORTS[key].ascending;
          state.sort = key;
          rerender();
        },
      },
      label,
    ),
  );
}

function table(rows, rerender) {
  return h(
    "div",
    { class: "scroller" },
    h(
      "table",
      { class: "queue" },
      h(
        "thead",
        {},
        h(
          "tr",
          {},
          header("verdict", "Verdict", rerender),
          header("patient", "Chart", rerender),
          header("resolved", "Criteria resolved", rerender),
          header("retrievable", "Gaps a query would close", rerender),
          header("person", "Gaps needing a person", rerender),
          h("th", { scope: "col" }, "What happens next"),
        ),
      ),
      h("tbody", {}, rows.map(row)),
    ),
  );
}

function empty(rerender) {
  const eligible = state.verdict === "eligible";
  return h(
    "div",
    { class: "empty" },
    h("h3", {}, eligible ? "No screening reaches eligible" : "No screening matches"),
    h(
      "p",
      {},
      eligible
        ? "Eligible is unreachable while any criterion is unresolved, and this protocol has " +
          "criteria that no chart can settle. Every open screening stops at needs review, which " +
          "is the honest answer rather than a softer one."
        : "Nothing in this cohort matches the verdict and the text you asked for.",
    ),
    h(
      "button",
      {
        type: "button",
        class: "button",
        onclick: () => {
          state.verdict = "all";
          state.chart = "all";
          state.find = "";
          rerender();
        },
      },
      "Show all screenings",
    ),
  );
}

function segmented(label, options, counts, selected, choose) {
  return h(
    "div",
    { class: "field" },
    h("span", { class: "micro" }, label),
    h(
      "div",
      { class: "segmented", role: "group", "aria-label": `Filter by ${label.toLowerCase()}` },
      options.map(([value, text]) =>
        h(
          "button",
          {
            type: "button",
            "aria-pressed": String(selected === value),
            onclick: () => choose(value),
          },
          text,
          h("span", { class: "count" }, String(counts[value])),
        ),
      ),
    ),
  );
}

function toolbar(all, sorts, rerender) {
  const verdicts = { all: all.length };
  VERDICTS.slice(1).forEach(([value]) => {
    verdicts[value] = all.filter((r) => r.decision === value).length;
  });
  const charts = {
    all: all.length,
    observed: all.filter((r) => !r.constructed).length,
    constructed: all.filter((r) => r.constructed).length,
  };

  const sort = h(
    "select",
    {
      id: "queue-sort",
      onchange: (event) => {
        state.sort = event.target.value;
        state.ascending = SORTS[state.sort].ascending;
        rerender();
      },
    },
    sorts.map(([value, meta]) =>
      h("option", { value, ...(state.sort === value ? { selected: true } : {}) }, meta.label),
    ),
  );

  const find = h("input", {
    id: "queue-find",
    type: "search",
    value: state.find,
    placeholder: "chart, case, criterion or missing datum",
    oninput: (event) => {
      state.find = event.target.value;
      rerender({ keepFocus: "queue-find" });
    },
  });

  return h(
    "div",
    { class: "toolbar" },
    segmented("Verdict", VERDICTS, verdicts, state.verdict, (value) => {
      state.verdict = value;
      rerender();
    }),
    // Offered only where there is something to tell apart, so a cohort nobody edited does not
    // grow a control that can never change what it shows.
    charts.constructed
      ? segmented("Chart", CHARTS, charts, state.chart, (value) => {
          state.chart = value;
          rerender();
        })
      : null,
    h("div", { class: "field" }, h("label", { class: "micro", for: "queue-sort" }, "Order"), sort),
    h("div", { class: "field" }, h("label", { class: "micro", for: "queue-find" }, "Find"), find),
  );
}

/* Why no row says eligible, stated rather than left to be found by filtering to a verdict that
 * never appears. The counts come from the compilation: a protocol whose every criterion could be
 * formalised would drop this panel of its own accord. */
function finding(trial, all) {
  if (all.some((entry) => entry.decision === "eligible")) return null;
  const built = all.filter((e) => e.constructed && e.constructed.key_outcome === "eligible");
  return h(
    "div",
    { class: "panel panel--dashed" },
    h("h3", {}, "Nothing in this cohort is eligible, and that is a finding"),
    h(
      "p",
      { class: "note" },
      `Eligible needs every criterion resolved. ${trial.unsupported} of this protocol's ` +
        `${trial.criteria} could not be formalised from a record at all, so they read unresolved ` +
        "against every chart and no chart can clear them. That is a fact about the protocol " +
        "rather than about these patients.",
    ),
    built.length
      ? h(
          "p",
          { class: "note" },
          `${built.length} of the charts below were edited until the frozen answer key calls them ` +
            "eligible on the criteria it scopes in, and Caliper still stops at needs review. Each " +
            "of those packets names the criteria that stopped it.",
        )
      : null,
  );
}

/** Which of a group's edits belong to one member alone: the number the comparison turns on. */
function separator(entries) {
  const shared = new Map();
  entries.forEach((entry) =>
    entry.constructed.edits.forEach((edit) => shared.set(edit, (shared.get(edit) || 0) + 1)),
  );
  return (entry) => entry.constructed.edits.filter((edit) => shared.get(edit) < entries.length);
}

/* An edit the whole group makes tells a reader nothing about why the group's members differ, so
 * the column carries only the edits that are not common to all of them. Where that leaves nothing,
 * the row says so: an absent measurement is a difference too, and is the point of a third case. */
function differenceCell(entry, edits) {
  if (!entry.constructed) {
    return h(
      "td",
      { class: "separator" },
      h("span", { class: "quiet" }, "not edited: the chart as the corpus records it"),
    );
  }
  if (!edits.length) {
    return h(
      "td",
      { class: "separator" },
      h("span", { class: "quiet" }, "nothing: it makes only the edits the whole group makes"),
    );
  }
  return h("td", { class: "separator" }, edits.map((edit) => h("p", {}, edit)));
}

function comparisonRow(entry, edits) {
  return h(
    "tr",
    { class: `row--${entry.decision}` },
    h(
      "td",
      { class: entry.constructed ? "chart chart--constructed" : "chart" },
      h(
        "a",
        {
          class: "patient",
          href: `#/packet/${entry.nct_id}/${encodeURIComponent(entry.patient_id)}`,
        },
        chartName(entry.patient_id, entry.constructed),
      ),
    ),
    differenceCell(entry, edits),
    h(
      "td",
      {},
      outcomeMark(entry.decision, SHORT_LABEL[entry.decision], { title: entry.decision_label }),
    ),
    blockingCell(entry),
  );
}

/* The comparison the queue cannot make while it is also a worklist: one chart, screened two or
 * three times, one supplied number apart, with the unedited chart at the head of each group. Every
 * value here is already in the index, so the whole section costs no request. */
function comparisons(all) {
  const byChart = new Map();
  all.forEach((entry) => {
    if (!entry.constructed) return;
    const source = entry.constructed.base_patient_id;
    if (!byChart.has(source)) byChart.set(source, []);
    byChart.get(source).push(entry);
  });

  const groups = [...byChart.entries()]
    .filter(([, entries]) => entries.length > 1)
    .map(([source, entries]) => ({
      source,
      recorded: all.find((e) => !e.constructed && e.patient_id === source),
      entries: entries.slice().sort((a, b) =>
        a.constructed.case_id < b.constructed.case_id ? -1 : 1,
      ),
    }));
  if (!groups.length) return [];

  return [
    h("h2", {}, "The same chart, one number apart"),
    h(
      "p",
      { class: "lede" },
      "Each group is one chart screened against this trial more than once, the members differing " +
        "only in the value supplied for a single measurement. Reading down a group shows the " +
        "bound being evaluated rather than approximated: inside it, one unit outside it, and " +
        "absent.",
    ),
    h(
      "div",
      { class: "scroller" },
      h(
        "table",
        { class: "queue" },
        h(
          "thead",
          {},
          h(
            "tr",
            {},
            h("th", { scope: "col" }, "Chart"),
            h("th", { scope: "col" }, "Where this row differs from the rest of its group"),
            h("th", { scope: "col" }, "Verdict"),
            h("th", { scope: "col" }, "What happens next"),
          ),
        ),
        groups.map((group) => {
          const separating = separator(group.entries);
          return h(
            "tbody",
            {},
            h(
              "tr",
              { class: "group" },
              h(
                "th",
                { scope: "rowgroup", colspan: "4" },
                `Chart ${shortId(group.source)}`,
                h(
                  "span",
                  { class: "quiet" },
                  ` · ${plural(group.entries.length, "constructed screening")}` +
                    (group.recorded ? ", and the chart they were built from" : ""),
                ),
              ),
            ),
            group.recorded ? comparisonRow(group.recorded, []) : null,
            group.entries.map((entry) => comparisonRow(entry, separating(entry))),
          );
        }),
      ),
    ),
  ];
}

export async function renderQueue(index, nctId) {
  const trial = index.trials.find((t) => t.nct_id === nctId) || index.trials[0];
  const all = index.screenings.filter((s) => s.nct_id === trial.nct_id);
  const constructed = all.some((s) => s.constructed);
  const sorts = Object.entries(SORTS).filter(([, meta]) => constructed || !meta.constructed);
  // A sort carried over from a cohort that had constructed charts would leave the select showing
  // no selection at all on one that does not.
  if (!sorts.some(([value]) => value === state.sort)) state.sort = "nearest";
  const body = h("div", {});

  const rerender = (options = {}) => {
    const rows = all.filter(matches).sort((a, b) => compare(a, b, state.sort, state.ascending));
    replace(
      body,
      toolbar(all, sorts, rerender),
      h(
        "p",
        { class: "note" },
        "Nearest first ranks by the gaps a query would close, fewest at the top. Gaps that need " +
          "a person are counted apart, because no query closes them, and settled screenings sort " +
          "last.",
      ),
      rows.length ? table(rows, rerender) : empty(rerender),
      h(
        "p",
        { class: "note" },
        `Showing ${rows.length} of ${plural(all.length, "screening")}. ` +
          "A decided screening raises no worklist: its remaining criteria are recorded in the " +
          "packet, but closing them could not change the outcome.",
      ),
    );
    if (options.keepFocus) {
      const field = document.getElementById(options.keepFocus);
      if (field) {
        field.focus();
        field.setSelectionRange(field.value.length, field.value.length);
      }
    }
  };

  rerender();

  const open = all.filter((s) => s.decision === "needs_review").length;
  const content = h(
    "div",
    { class: "page" },
    h(
      "header",
      { class: "page__head" },
      h("p", { class: "eyebrow" }, "Screening queue"),
      h("h1", {}, trial.nct_id),
      h("p", { class: "trial-line" }, trial.title),
      h(
        "p",
        { class: "lede subtitle" },
        `${plural(all.length, "chart")} screened on ${all[0] ? all[0].screened_on : "—"} ` +
          `against ${plural(trial.criteria, "compiled criterion", "compiled criteria")}. ` +
          `${open === 1 ? "One screening is" : `${open} screenings are`} still open.`,
      ),
      index.demo ? h("p", { class: "lede note" }, index.demo.screening_date_note) : null,
      finding(trial, all),
    ),
    body,
    ...comparisons(all),
  );

  return { title: `Screening queue · ${trial.nct_id}`, content };
}
