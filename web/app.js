/* The whole application: a hash router over three screens.
 *
 * A hash route rather than the history API, because this page is served by whatever static file
 * server is to hand and a path router would need that server to rewrite unknown paths back to
 * `index.html`. Requiring a server configuration is the kind of dependency this build does not have
 * anywhere else, and it fails silently — as a 404 on someone else's machine.
 */

import { announce, h, replace } from "./lib/dom.js";
import { chartName } from "./lib/format.js";
import { DataError, loadIndex } from "./lib/store.js";
import { renderCriteria } from "./views/criteria.js";
import { renderPacket } from "./views/packet.js";
import { renderQueue } from "./views/queue.js";

const main = document.getElementById("main");
const chrome = document.getElementById("chrome");

function parseRoute() {
  const [screen, ...rest] = window.location.hash.replace(/^#\/?/, "").split("/");
  return { screen, params: rest.map(decodeURIComponent) };
}

function navLink(href, label, current) {
  return h("a", { href, ...(current ? { "aria-current": "page" } : {}) }, label);
}

/* The trials in the bundle, as links to the same screen on another protocol. A packet is about one
 * patient of one trial and has no counterpart under another, so switching from one falls back to
 * that trial's queue rather than to a patient who may not be in it. */
function trialLinks(index, route, current) {
  if (index.trials.length < 2) return null;
  const screen = route.screen === "trial" ? "trial" : "queue";
  return h(
    "nav",
    { class: "nav", "aria-label": "Trials" },
    index.trials.map((trial) =>
      navLink(`#/${screen}/${trial.nct_id}`, trial.nct_id, trial.nct_id === current.nct_id),
    ),
  );
}

function renderChrome(index, route) {
  if (!index.trials.length) return replace(chrome);

  const nct = route.params[0] || index.trials[0].nct_id;
  const trial = index.trials.find((t) => t.nct_id === nct) || index.trials[0];
  const links = [
    navLink(`#/trial/${trial.nct_id}`, "Criteria review", route.screen === "trial"),
    navLink(`#/queue/${trial.nct_id}`, "Screening queue", route.screen === "queue"),
  ];
  // The packet is a document about one patient, so it appears in the navigation only once a
  // patient is in hand. A third tab that guessed one would be a link to somebody arbitrary.
  if (route.screen === "packet" && route.params[1]) {
    // Named from the index rather than from the route, so that a constructed chart carries its
    // case here too. The identifier alone would read as the chart it was built from.
    const entry = index.screenings.find(
      (s) => s.nct_id === trial.nct_id && s.patient_id === route.params[1],
    );
    const name = chartName(route.params[1], entry && entry.constructed);
    links.push(navLink(window.location.hash, `Packet · ${name}`, true));
  }

  // The screening date is in the chrome rather than on one screen because it qualifies every
  // number in the bundle, and it is not the date the rest of this repository uses.
  const screenedOn = index.demo ? `screened ${index.demo.screened_on} · ` : "";

  replace(
    chrome,
    h(
      "div",
      { class: "chrome__inner" },
      h("a", { class: "wordmark", href: `#/queue/${trial.nct_id}` }, "Caliper"),
      h("nav", { class: "nav", "aria-label": "Screens" }, links),
      trialLinks(index, route, trial),
      h(
        "p",
        { class: "chrome__meta" },
        `${screenedOn}criteria fingerprint `,
        h("span", { class: "pointer", title: trial.criteria_fingerprint },
          trial.criteria_fingerprint.slice(0, 12)),
      ),
    ),
  );
}

function renderError(error) {
  replace(
    main,
    h(
      "div",
      { class: "notice" },
      h("h1", {}, "The run is not here"),
      h("p", { class: "lede" }, error.message),
      h(
        "p",
        { class: "note" },
        "The interface reads a bundle written by the exporter. Build one with ",
        h("code", {}, "python -m caliper.cli ui demo"),
        " from the repository root.",
      ),
    ),
  );
  document.title = "Caliper — no run loaded";
}

const SCREENS = {
  trial: (index, [nct]) => renderCriteria(nct || index.trials[0].nct_id),
  queue: (index, [nct]) => renderQueue(index, nct || index.trials[0].nct_id),
  packet: (index, [nct, patient]) => renderPacket(nct, patient),
};

let booted = false;

async function route() {
  let index;
  try {
    index = await loadIndex();
  } catch (error) {
    if (error instanceof DataError) return renderError(error);
    throw error;
  }

  const parsed = parseRoute();
  const known = SCREENS[parsed.screen] && index.trials.length > 0;
  if (!known) {
    window.location.replace(`#/queue/${index.trials[0] ? index.trials[0].nct_id : ""}`);
    return;
  }

  renderChrome(index, parsed);
  try {
    const view = await SCREENS[parsed.screen](index, parsed.params);
    replace(main, view.content);
    document.title = `${view.title} — Caliper`;
    if (booted) {
      // Navigation inside a single page moves nobody's focus on its own, so a keyboard or screen
      // reader user would still be sitting in the header of the screen they just left.
      main.focus({ preventScroll: true });
      window.scrollTo(0, 0);
      announce(view.title);
    }
    booted = true;
  } catch (error) {
    if (error instanceof DataError) return renderError(error);
    throw error;
  }
}

window.addEventListener("hashchange", route);
route();
