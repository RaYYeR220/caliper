/* Reading the exported run.
 *
 * One request per document, cached for the life of the page. The index carries everything the queue
 * needs, so a cohort of any size costs one fetch to list and one more to open a patient.
 *
 * A failed fetch is reported with the file name and the likely cause. The most common one by far is
 * opening `index.html` from the file system, where module scripts and `fetch` are both blocked, so
 * that case is named explicitly rather than left as a bare network error.
 */

const cache = new Map();

export class DataError extends Error {
  constructor(message, file) {
    super(message);
    this.name = "DataError";
    this.file = file;
  }
}

async function loadJson(file) {
  if (cache.has(file)) return cache.get(file);

  const pending = fetch(`data/${file}`, { cache: "no-cache" })
    .then((response) => {
      if (!response.ok) {
        throw new DataError(
          `data/${file} could not be read (${response.status}). ` +
            "Run `caliper ui demo` to write the bundle.",
          file,
        );
      }
      return response.json();
    })
    .catch((error) => {
      cache.delete(file);
      if (error instanceof DataError) throw error;
      if (window.location.protocol === "file:") {
        throw new DataError(
          "This page has to be served over HTTP. Run `python -m http.server` in this " +
            "directory and open the address it prints.",
          file,
        );
      }
      throw new DataError(`data/${file} could not be read: ${error.message}`, file);
    });

  cache.set(file, pending);
  return pending;
}

export function loadIndex() {
  return loadJson("index.json");
}

export function loadTrial(nctId) {
  return loadJson(`${nctId}.trial.json`);
}

export function loadScreening(nctId, patientId) {
  return loadJson(`${nctId}--${patientId}.json`);
}
