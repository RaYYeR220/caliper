/* The verdict marks, and the two counting devices that reuse them.
 *
 * The three criterion verdicts have to be told apart by someone reading a greyscale printout, so
 * each one differs from the others in three ways at once: the glyph's shape, whether the chip is
 * filled, and whether its border is solid or dashed. No verdict uses colour, here or in the
 * stylesheet.
 *
 * The glyph is the argument. A met criterion is a closed, filled square: the measurement was taken
 * and it landed. A criterion not met is that same square struck through: taken, and it failed. An
 * unresolved criterion is a bracket with its right side missing — an open shape, not a warning
 * sign, because the work is unfinished rather than wrong, and it is followed by a caret pointing at
 * the next action.
 */

import { h, s } from "./dom.js";

const GLYPHS = {
  met: () => [s("rect", { x: 1.5, y: 1.5, width: 8, height: 8, fill: "currentColor" })],
  not_met: () => [
    s("rect", {
      x: 1.5, y: 1.5, width: 8, height: 8,
      fill: "none", stroke: "currentColor", "stroke-width": 1.6,
    }),
    s("line", {
      x1: 1.5, y1: 9.5, x2: 9.5, y2: 1.5, stroke: "currentColor", "stroke-width": 1.6,
    }),
  ],
  unknown: () => [
    s("path", {
      d: "M7 1.5 H1.5 V9.5 H7",
      fill: "none", stroke: "currentColor", "stroke-width": 1.6,
    }),
    s("path", {
      d: "M9 3.6 L11 5.5 L9 7.4",
      fill: "none", stroke: "currentColor", "stroke-width": 1.6,
    }),
  ],
};

const CLASSES = {
  met: "mark mark--met",
  not_met: "mark mark--not-met",
  unknown: "mark mark--unresolved",
};

function glyph(verdict, large) {
  const scale = large ? 1.5 : 1;
  return s(
    "svg",
    {
      width: 12 * scale,
      height: 11 * scale,
      viewBox: "0 0 12 11",
      "aria-hidden": "true",
      focusable: "false",
    },
    GLYPHS[verdict](),
  );
}

/** The chip printed beside a criterion. `label` comes from the export, not from this file.
 *
 * `options.title` carries the fuller wording where the visible label had to be shortened for a
 * column: the queue cannot spend a third of its width on "Needs review before a decision", but the
 * sentence the packet prints is still the one a reader should be able to reach.
 */
export function verdictMark(verdict, label, options = {}) {
  const base = CLASSES[verdict] || CLASSES.unknown;
  return h(
    "span",
    {
      class: options.large ? `${base} mark--lg` : base,
      ...(options.title ? { title: options.title } : {}),
    },
    glyph(verdict, options.large),
    label,
  );
}

/* Screening outcomes borrow the printed packet's border vocabulary rather than inventing a second
 * one: a solid rule for a settled eligible screening, a double rule for one that is closed, a
 * dashed rule for one still open. */
const OUTCOME_VERDICT = {
  eligible: "met",
  ineligible: "not_met",
  needs_review: "unknown",
};

export function outcomeMark(decision, label, options) {
  return verdictMark(OUTCOME_VERDICT[decision] || "unknown", label, options);
}

/** `resolved` of `total`, drawn as `total` ticks. The same scale as the protocol ruler. */
export function tickBar(resolved, total, description) {
  const ticks = [];
  for (let i = 0; i < total; i += 1) {
    ticks.push(h("i", { class: i < resolved ? "on" : "" }));
  }
  return h("span", { class: "ticks", role: "img", "aria-label": description }, ticks);
}
