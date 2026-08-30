/* Formatting, and nothing else. No view builds a sentence of its own here.
 *
 * Labels that a coordinator will act on — the verdict words, the decision words, the absence-policy
 * note, the disclaimer — are written once in `caliper.packet` and travel in the export, so the page
 * and the printed document cannot drift into saying different things about the same screening.
 */

/** Synthea patient identifiers are UUIDs. The first group is enough to tell charts apart. */
export function shortId(id) {
  return String(id).split("-")[0];
}

/** What a chart is called wherever it is named.
 *
 * A constructed chart is three things at once — a real chart, a recorded case, and the edits
 * between them — and a reader who sees only the first would be reading an edited chart as an
 * observed one. So the case identifier is part of the name, everywhere, and not a badge that a
 * narrow column or a sorted table could drop.
 */
export function chartName(patientId, constructed) {
  if (!constructed) return shortId(patientId);
  return `${shortId(constructed.base_patient_id)} · ${constructed.case_id}`;
}

export function plural(count, singular, many) {
  return `${count} ${count === 1 ? singular : many || `${singular}s`}`;
}

export function percent(ratio) {
  return `${Math.round(ratio * 100)}%`;
}

/** A number the way a chart prints it: 30.3, but 45 rather than 45.0. */
export function decimal(value) {
  if (value === null || value === undefined) return "";
  return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(4)));
}

export function capitalise(word) {
  return word ? word[0].toUpperCase() + word.slice(1) : "";
}

/** The measured value on an evidence row, with its unit, or null where the row carries none. */
export function evidenceValue(evidence) {
  if (evidence.value === null || evidence.value === undefined) return null;
  return evidence.unit ? `${decimal(evidence.value)} ${evidence.unit}` : decimal(evidence.value);
}

export function trialLabel(trial) {
  return `${trial.nct_id} · ${trial.title}`;
}
