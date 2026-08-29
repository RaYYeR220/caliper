/* Screen three: one patient against one trial.
 *
 * The order is the printed packet's order, and it is the whole design. A coordinator opens this to
 * find out what to do next, so when a screening is still open the work comes before the evidence:
 * three actionable gaps buried under forty resolved criteria waste the only thing this tool saves.
 * A screening that is closed leads with the criterion that closed it and raises no worklist, because
 * finding that lab now could not change the answer.
 *
 * The open items are split in two. A gap with a FHIR query behind it is a request someone can send;
 * a gap without one is a criterion that needs a person to read the protocol. Presenting them as one
 * list of eighteen would hide the two that are actually actionable.
 */

import { copyText, h } from "../lib/dom.js";
import { capitalise, evidenceValue, plural, shortId } from "../lib/format.js";
import { loadScreening } from "../lib/store.js";
import { outcomeMark, verdictMark } from "../lib/marks.js";

function copyButton(value, label) {
  const button = h(
    "button",
    {
      type: "button",
      class: "button",
      onclick: async () => {
        const done = await copyText(value);
        button.dataset.copied = String(done);
        button.replaceChildren(document.createTextNode(done ? "Copied" : "Press Ctrl+C"));
        window.setTimeout(() => {
          delete button.dataset.copied;
          button.replaceChildren(document.createTextNode(label));
        }, 2000);
      },
    },
    label,
  );
  return button;
}

function evidenceList(evidence) {
  if (!evidence.length) return h("span", { class: "none" }, "none on file");
  return h(
    "ul",
    { class: "evidence" },
    evidence.map((row) => {
      const value = evidenceValue(row);
      return h(
        "li",
        {},
        h("span", {}, row.display),
        value ? h("span", { class: "value" }, ` ${value}`) : null,
        h("span", { class: "when" }, row.date ? ` · ${row.date}` : " · not dated"),
        h("span", { class: "pointer" }, `${row.resource} — ${row.fhir_path}`),
      );
    }),
  );
}

function openItem(item, index) {
  return h(
    "li",
    {},
    h(
      "div",
      { class: "stack__head" },
      h("span", { class: "id" }, item.criterion_id),
      h("span", { class: "kind" }, `Open item ${index + 1}`),
    ),
    h("blockquote", {}, h("p", {}, item.quote)),
    h(
      "dl",
      { class: "open-item" },
      h("dt", {}, "Missing"),
      h("dd", {}, item.missing),
      h("dt", {}, "Where to look"),
      h("dd", {}, item.where_to_look),
      h("dt", {}, item.retrievable ? "Query" : "Who decides"),
      h(
        "dd",
        {},
        item.retrievable
          ? h(
              "span",
              { class: "query-row" },
              h("code", { class: "query" }, item.fhir_query),
              copyButton(item.fhir_query, "Copy query"),
            )
          : "No query returns this. A person has to read the criterion against the chart.",
      ),
    ),
  );
}

function openItems(screening) {
  if (screening.decision !== "needs_review") return [];

  const retrievable = screening.open_items.filter((item) => item.retrievable);
  const human = screening.open_items.filter((item) => !item.retrievable);

  const blocks = [
    h("h2", {}, "Open items"),
    h(
      "p",
      { class: "lede" },
      `${plural(screening.open_items.length, "criterion", "criteria")} could not be decided from ` +
        "the record. Every one has to be closed before this screening can be signed.",
    ),
  ];

  if (retrievable.length) {
    blocks.push(
      h(
        "div",
        { class: "panel panel--action" },
        h("h3", {}, `${plural(retrievable.length, "gap")} a query would close`),
        h(
          "p",
          { class: "note" },
          "Each query is written against this patient and can be sent as it stands.",
        ),
        h("ol", { class: "stack" }, retrievable.map(openItem)),
      ),
    );
  }

  if (human.length) {
    blocks.push(
      h(
        "div",
        { class: "panel panel--dashed" },
        h("h3", {}, `${plural(human.length, "criterion", "criteria")} that need a person`),
        h(
          "p",
          { class: "note" },
          "No query closes these. They were never formalised, or the critic withdrew them, and " +
            "they will read unresolved for every patient screened against this trial.",
        ),
        h("ol", { class: "stack" }, human.map(openItem)),
      ),
    );
  }

  return blocks;
}

function decidingSection(screening) {
  if (!screening.deciding_criterion_ids.length) return [];
  const rows = screening.criteria.filter((c) =>
    screening.deciding_criterion_ids.includes(c.id),
  );
  return [
    h("h2", {}, "Why this patient is not eligible"),
    h(
      "ul",
      { class: "stack" },
      rows.map((criterion) =>
        h(
          "li",
          {},
          h(
            "div",
            { class: "stack__head" },
            h("span", { class: "id" }, criterion.id),
            h("span", { class: "kind" }, `${capitalise(criterion.kind)} criterion`),
            verdictMark(criterion.verdict, criterion.verdict_label),
          ),
          h("blockquote", {}, h("p", {}, criterion.quote)),
          h("p", { class: "reason" }, criterion.rationale),
          evidenceList(criterion.evidence),
        ),
      ),
    ),
  ];
}

function approximations(screening) {
  if (!screening.approximations.length) return [];
  return [
    h(
      "div",
      { class: "panel panel--dashed" },
      h(
        "h3",
        {},
        `${plural(screening.approximations.length, "approximation")} this verdict rests on`,
      ),
      h(
        "p",
        { class: "note" },
        "Recorded at the top of the packet rather than in one row of the table, because a verdict " +
          "that leaned on an approximation is a different thing from one that did not.",
      ),
      h(
        "ul",
        { class: "stack" },
        screening.approximations.map((caveat) => h("li", {}, caveat)),
      ),
    ),
  ];
}

function foundCell(criterion) {
  const children = [h("span", {}, criterion.rationale)];
  if (criterion.engine_written) {
    children.push(h("span", { class: "engine" }, "Written by the screening engine"));
  }
  if (criterion.resolution) {
    children.push(
      h(
        "dl",
        { class: "open-item" },
        h("dt", {}, "Missing"),
        h("dd", {}, criterion.resolution.missing),
        h("dt", {}, "Where to look"),
        h("dd", {}, criterion.resolution.where_to_look),
        ...(criterion.resolution.retrievable
          ? [
              h("dt", {}, "Query"),
              h(
                "dd",
                {},
                h(
                  "span",
                  { class: "query-row" },
                  h("code", { class: "query" }, criterion.resolution.fhir_query),
                  copyButton(criterion.resolution.fhir_query, "Copy"),
                ),
              ),
            ]
          : []),
      ),
    );
  }
  if (criterion.approximations.length) {
    children.push(
      h("span", { class: "engine" }, `Approximated: ${criterion.approximations.join("; ")}`),
    );
  }
  return h("td", { class: "rationale" }, children);
}

function criteriaTable(screening) {
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
          h("th", { scope: "col" }, "Verdict"),
          h("th", { scope: "col" }, "The protocol says"),
          h("th", { scope: "col" }, "What Caliper found"),
          h("th", { scope: "col" }, "Evidence"),
        ),
      ),
      h(
        "tbody",
        {},
        screening.criteria.map((criterion) =>
          h(
            "tr",
            { class: `row--${criterion.verdict}` },
            h(
              "td",
              {},
              h("div", { class: "id" }, criterion.id),
              h("div", { class: "kind" }, capitalise(criterion.kind)),
              criterion.decisive ? h("span", { class: "decisive" }, "Decisive") : null,
            ),
            h("td", {}, verdictMark(criterion.verdict, criterion.verdict_label)),
            h("td", { class: "protocol" }, criterion.quote),
            foundCell(criterion),
            h("td", {}, evidenceList(criterion.evidence)),
          ),
        ),
      ),
    ),
  );
}

function footer(screening) {
  const rationales = screening.rationales;
  return h(
    "footer",
    { class: "about" },
    h("h2", {}, "About this packet"),
    h(
      "dl",
      { class: "facts" },
      h("dt", {}, "Absence policy"),
      h("dd", {}, screening.absence_policy.note),
      h("dt", {}, "Criteria fingerprint"),
      h("dd", {}, h("code", {}, screening.criteria_fingerprint)),
      h("dt", {}, "Resolved"),
      h(
        "dd",
        {},
        `${screening.criteria_resolved} of ${screening.criteria_total} criteria decided from the ` +
          "patient record",
      ),
      h("dt", {}, "Rationale sentences"),
      h(
        "dd",
        {},
        rationales.engine_written
          ? `${rationales.engine_written} of ${rationales.total} were written by the screening ` +
            "engine, because no drafted sentence could be verified against the record"
          : "every sentence was checked against the record it describes",
      ),
    ),
    h("p", { class: "disclaimer" }, screening.disclaimer),
  );
}

function decisionNote(screening) {
  if (screening.blocked_by) return screening.blocked_by;
  if (screening.decision === "needs_review") {
    return (
      `${plural(screening.open_items.length, "criterion", "criteria")} are unresolved. ` +
      "Eligible is unreachable while any of them stands."
    );
  }
  if (screening.decision === "ineligible") {
    return (
      `Closed by ${screening.deciding_criterion_ids.join(", ")}. ` +
      "No worklist is raised: evidence found now could not change this."
    );
  }
  return "Every criterion resolved from the record.";
}

export async function renderPacket(nctId, patientId) {
  const screening = await loadScreening(nctId, patientId);
  const stopped = Boolean(screening.blocked_by);

  const content = h(
    "div",
    { class: "page page--document" },
    h(
      "header",
      { class: "page__head" },
      h("p", { class: "eyebrow" }, `Screening packet · ${screening.nct_id}`),
      h("h1", {}, shortId(screening.patient.id)),
      h("p", { class: "subtitle" }, screening.patient.summary),
      h("p", { class: "pointer note" }, screening.patient.id),
      h(
        "dl",
        { class: "facts" },
        h("dt", {}, "Trial"),
        h("dd", {}, `${screening.nct_id} — ${screening.trial_title}`),
        h("dt", {}, "Screened on"),
        h("dd", {}, screening.screened_on),
        h("dt", {}, "Criteria"),
        h(
          "dd",
          {},
          stopped
            ? "no criterion was evaluated"
            : `${screening.criteria_resolved} of ${screening.criteria_total} resolved from the ` +
              "record",
        ),
      ),
      h(
        "div",
        { class: `decision decision--${screening.decision}` },
        h("span", { class: "decision__label eyebrow" }, "Decision"),
        h(
          "span",
          { class: "decision__value" },
          outcomeMark(screening.decision, screening.decision_label),
        ),
        h("p", { class: "decision__note" }, decisionNote(screening)),
      ),
      ...approximations(screening),
    ),

    ...(stopped
      ? [
          h("h2", {}, "Nothing was evaluated"),
          h(
            "p",
            { class: "lede" },
            "The screening stopped before the criteria were read, so this packet carries no " +
              "criterion table. Reporting a screening-level fact as a fact, rather than as a " +
              "criterion the protocol never contained, is what keeps the table honest.",
          ),
        ]
      : [
          ...openItems(screening),
          ...decidingSection(screening),
          h("h2", {}, "Criteria"),
          h(
            "p",
            { class: "note" },
            "Protocol text sits on paper. Everything Caliper derived sits on the panel.",
          ),
          criteriaTable(screening),
        ]),

    footer(screening),
  );

  return {
    title: `Packet · ${shortId(screening.patient.id)} · ${screening.nct_id}`,
    content,
  };
}
