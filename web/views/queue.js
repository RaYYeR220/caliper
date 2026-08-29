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
 */

import { h, replace } from "../lib/dom.js";
import { plural, shortId } from "../lib/format.js";
import { outcomeMark, tickBar } from "../lib/marks.js";

const state = { verdict: "all", sort: "nearest", ascending: true, find: "" };

const VERDICTS = [
  ["all", "All"],
  ["needs_review", "Needs review"],
  ["ineligible", "Not eligible"],
  ["eligible", "Eligible"],
];

const SORTS = {
  nearest: { label: "Nearest to a decision", ascending: true },
  patient: { label: "Patient", ascending: true },
  verdict: { label: "Verdict", ascending: true },
  resolved: { label: "Criteria resolved", ascending: false },
  retrievable: { label: "Gaps a query would close", ascending: true },
  person: { label: "Gaps needing a person", ascending: true },
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

const KEYS = {
  nearest: distance,
  patient: (row) => [row.patient_id],
  verdict: (row) => [["needs_review", "eligible", "ineligible"].indexOf(row.decision)],
  resolved: (row) => [row.criteria_total ? row.criteria_resolved / row.criteria_total : -1],
  retrievable: (row) => [row.open_retrievable, ...distance(row)],
  person: (row) => [row.open_needing_a_person, ...distance(row)],
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
  if (!state.find) return true;
  const needle = state.find.toLowerCase();
  return (
    row.patient_id.toLowerCase().includes(needle) ||
    (row.blocking || "").toLowerCase().includes(needle) ||
    (row.blocked_by || "").toLowerCase().includes(needle) ||
    row.deciding_criterion_ids.join(" ").toLowerCase().includes(needle)
  );
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
      h("span", { class: "micro" }, "Screening stopped"),
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
      h("span", { class: "micro" }, `Decided by ${row.deciding_criterion_ids.join(", ")}`),
      unresolved
        ? `${plural(unresolved, "criterion", "criteria")} still unresolved, and closing them ` +
          "cannot change the outcome."
        : "Every criterion resolved.",
    );
  }
  return h("td", { class: "blocking" }, h("span", { class: "micro" }, "Nothing outstanding"));
}

function row(entry) {
  const href = `#/packet/${entry.nct_id}/${encodeURIComponent(entry.patient_id)}`;
  return h(
    "tr",
    { class: `row--${entry.decision}` },
    h("td", {}, outcomeMark(entry.decision, entry.decision_label)),
    h(
      "td",
      {},
      h("a", { class: "patient", href }, shortId(entry.patient_id)),
      h("div", { class: "summary" }, entry.patient_summary),
    ),
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
          header("patient", "Patient", rerender),
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
          state.find = "";
          rerender();
        },
      },
      "Show all screenings",
    ),
  );
}

function toolbar(all, rerender) {
  const counts = { all: all.length };
  VERDICTS.slice(1).forEach(([value]) => {
    counts[value] = all.filter((r) => r.decision === value).length;
  });

  const filter = h(
    "div",
    { class: "segmented", role: "group", "aria-label": "Filter by verdict" },
    VERDICTS.map(([value, label]) =>
      h(
        "button",
        {
          type: "button",
          "aria-pressed": String(state.verdict === value),
          onclick: () => {
            state.verdict = value;
            rerender();
          },
        },
        label,
        h("span", { class: "count" }, String(counts[value])),
      ),
    ),
  );

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
    Object.entries(SORTS).map(([value, meta]) =>
      h("option", { value, ...(state.sort === value ? { selected: true } : {}) }, meta.label),
    ),
  );

  const find = h("input", {
    id: "queue-find",
    type: "search",
    value: state.find,
    placeholder: "patient, criterion or missing datum",
    oninput: (event) => {
      state.find = event.target.value;
      rerender({ keepFocus: "queue-find" });
    },
  });

  return h(
    "div",
    { class: "toolbar" },
    h("div", { class: "field" }, h("span", { class: "micro" }, "Verdict"), filter),
    h(
      "div",
      { class: "field" },
      h("label", { class: "micro", for: "queue-sort" }, "Order"),
      sort,
    ),
    h("div", { class: "field" }, h("label", { class: "micro", for: "queue-find" }, "Find"), find),
  );
}

export async function renderQueue(index, nctId) {
  const trial = index.trials.find((t) => t.nct_id === nctId) || index.trials[0];
  const all = index.screenings.filter((s) => s.nct_id === trial.nct_id);
  const body = h("div", {});

  const rerender = (options = {}) => {
    const rows = all.filter(matches).sort((a, b) => compare(a, b, state.sort, state.ascending));
    replace(
      body,
      toolbar(all, rerender),
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
        `Showing ${rows.length} of ${plural(all.length, "screening")}.`,
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
      h("p", { class: "eyebrow" }, `Screening queue · ${trial.nct_id}`),
      h("h1", {}, trial.title),
      h(
        "p",
        { class: "lede subtitle" },
        `${plural(all.length, "chart")} screened on ${all[0] ? all[0].screened_on : "—"} ` +
          `against ${plural(trial.criteria, "compiled criterion", "compiled criteria")}. ` +
          `${open === 1 ? "One screening is" : `${open} screenings are`} still open.`,
      ),
    ),
    body,
  );

  return { title: `Screening queue · ${trial.nct_id}`, content };
}
