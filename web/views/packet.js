/* Screen three: one patient against one trial.
 *
 * The order is the printed packet's order, and it is the whole design. A coordinator opens this to
 * find out what to do next, so when a screening is still open the work comes before the evidence:
 * three actionable gaps buried under forty resolved criteria waste the only thing this tool saves.
 * A screening that is closed leads with the criterion that closed it and raises no worklist:
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

/* One line per criterion nobody can settle from data: the identifier, the protocol's words, and
 * what would have to happen instead. The full treatment above is reserved for the gaps a query
 * would close, which is where the coordinator's afternoon actually goes. */
function humanItem(item) {
  return h(
    "li",
    {},
    h("span", { class: "id" }, item.criterion_id),
    h("span", { class: "quote" }, item.quote),
    h("p", { class: "reason" }, item.missing),
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
          "No query closes these. They were never formalised, or the critic withdrew them, so " +
            "they read unresolved for every patient screened against this trial and are worth " +
            "reading once on the criteria review rather than once per chart.",
        ),
        // Folded away by default. They are a property of the protocol rather than of this chart,
        // and expanded they would push the two gaps that are actually actionable off the screen.
        h(
          "details",
          {},
          h("summary", {}, `Read all ${human.length}`),
          h("ul", { class: "roster" }, human.map(humanItem)),
        ),
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
  if (!screening.caveats.length) return [];
  return [
    h(
      "div",
      { class: "panel panel--dashed" },
      h("h3", {}, `${plural(screening.caveats.length, "approximation")} this verdict rests on`),
      h(
        "p",
        { class: "note" },
        "At the top of the packet rather than in one row of the table, because a verdict that " +
          "leaned on an approximation is a different thing from one that did not.",
      ),
      h(
        "ul",
        { class: "roster roster--spans" },
        screening.caveats.map((caveat) =>
          h(
            "li",
            {},
            h("span", { class: "id" }, caveat.criterion_ids.join(", ")),
            h("span", {}, caveat.text),
          ),
        ),
      ),
    ),
  ];
}

/* The row's account of itself, kept to a few lines. The worklist above already carries the full
 * treatment of an open item; repeating it in every row of a forty-row table would push the table
 * past the point where it can be read as one. */
function foundCell(criterion, showProvenance) {
  const children = [h("span", {}, criterion.rationale)];

  if (criterion.resolution) {
    children.push(
      h(
        "p",
        { class: "needs" },
        h("span", { class: "micro micro--inline" }, "Needs"),
        criterion.resolution.missing,
      ),
    );
    if (criterion.resolution.retrievable) {
      children.push(
        h(
          "span",
          { class: "query-row" },
          h("code", { class: "query" }, criterion.resolution.fhir_query),
          copyButton(criterion.resolution.fhir_query, "Copy"),
        ),
      );
    }
  }

  if (criterion.approximations.length) {
    children.push(
      h(
        "p",
        { class: "caveat" },
        h("span", { class: "micro micro--inline" }, "Approximation"),
        criterion.approximations.join("; "),
      ),
    );
  }

  if (showProvenance && criterion.engine_written) {
    children.push(h("span", { class: "engine" }, "Written by the screening engine"));
  }
  return h("td", { class: "rationale" }, children);
}

function criteriaTable(screening) {
  // The provenance badge marks an exception. When the engine wrote every sentence — which is what
  // a run with no model consulted looks like — the footer says so once and the column stays clean.
  const showProvenance = screening.rationales.engine_written < screening.rationales.total;
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
            foundCell(criterion, showProvenance),
            h("td", { class: "citations" }, evidenceList(criterion.evidence)),
          ),
        ),
      ),
    ),
  );
}

/* Where the sentences beside each criterion came from. A packet that does not say is a packet that
 * invites the reader to assume the most flattering answer. */
function rationaleNote(rationales) {
  if (!rationales.total) return "no criterion was evaluated, so none was written";
  if (!rationales.engine_written) {
    return "every sentence was checked against the record it describes";
  }
  if (rationales.engine_written === rationales.total) {
    return (
      `all ${rationales.total} were written by the screening engine, so every sentence is read ` +
      "straight off the record rather than drafted and checked"
    );
  }
  return (
    `${rationales.engine_written} of ${rationales.total} were written by the screening engine, ` +
    "because the drafted sentence could not be verified against the record"
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
        rationales.total
          ? `${screening.criteria_resolved} of ${screening.criteria_total} criteria decided from ` +
            "the patient record"
          : "no criterion was evaluated",
      ),
      h("dt", {}, "Rationale sentences"),
      h("dd", {}, rationaleNote(rationales)),
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
      h("p", { class: "eyebrow" }, "Screening packet"),
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
          outcomeMark(screening.decision, screening.decision_label, { large: true }),
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
