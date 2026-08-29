/* Building DOM without strings.
 *
 * Every value on these screens is protocol text, chart text or a model's sentence, and none of it
 * is under our control. `h` puts text in through `textContent` and attributes through
 * `setAttribute`, so there is no path from data to markup at all. The printed packet reaches the
 * same guarantee with Jinja's autoescape; this is the browser's version of the same decision.
 */

const SVG_NS = "http://www.w3.org/2000/svg";

function append(node, child) {
  if (child === null || child === undefined || child === false) return;
  if (Array.isArray(child)) {
    child.forEach((one) => append(node, one));
    return;
  }
  node.append(child instanceof Node ? child : document.createTextNode(String(child)));
}

function applyProps(node, props) {
  for (const [key, value] of Object.entries(props)) {
    if (value === null || value === undefined || value === false) continue;
    if (key.startsWith("on") && typeof value === "function") {
      node.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (key === "class") {
      node.setAttribute("class", value);
    } else if (key === "dataset") {
      Object.assign(node.dataset, value);
    } else if (value === true) {
      node.setAttribute(key, "");
    } else {
      node.setAttribute(key, String(value));
    }
  }
}

/** An HTML element: `h("p", {class: "lede"}, "text", child, [children])`. */
export function h(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  applyProps(node, props);
  children.forEach((child) => append(node, child));
  return node;
}

/** The same, in the SVG namespace, for the verdict glyphs. */
export function s(tag, props = {}, ...children) {
  const node = document.createElementNS(SVG_NS, tag);
  applyProps(node, props);
  children.forEach((child) => append(node, child));
  return node;
}

export function fragment(...children) {
  const node = document.createDocumentFragment();
  children.forEach((child) => append(node, child));
  return node;
}

export function replace(node, ...children) {
  node.replaceChildren();
  children.forEach((child) => append(node, child));
  return node;
}

/** Announce a change that happened without moving focus, for anyone using a screen reader. */
export function announce(message) {
  const live = document.getElementById("live");
  if (live) live.textContent = message;
}

/** Copy text, falling back to a selection when the async clipboard is unavailable. */
export async function copyText(value) {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(value);
    return true;
  }
  const carrier = h("textarea", { readonly: true, style: "position:fixed;opacity:0" });
  carrier.value = value;
  document.body.append(carrier);
  carrier.select();
  const copied = document.execCommand("copy");
  carrier.remove();
  return copied;
}
