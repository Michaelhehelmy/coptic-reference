/* static/js/pos_labels.js — the one place POS tags become words.
 *
 * LICENCE: project code, Apache-2.0.
 *
 * Rule 11 shape, like translit.js: exactly one function owns the tag-to-label
 * mapping, and every template calls it. A raw annotation tag (APST, CREL,
 * PPERS) in front of a learner is a bug of the same class as interpolating
 * a structured value into a template — the learner did not study the
 * tagset. This function returns the label or "", never the raw tag;
 * drill.js refuses to start a POS session whose bank has a tag without a
 * label, so "" is unreachable, not a fallback.
 *
 * (Note: this comment must never contain the literal raw-object marker
 * string — no_object_object_guard scans file contents, comments included.)
 */
(function (root) {
  "use strict";

  function cleanString(value) {
    if (typeof value !== "string") return "";
    var text = value.trim();
    return text === "" ? "" : text;
  }

  /**
   * Render one annotation tag as a learner-facing label.
   *
   * `labels` is the object from data/dist/drill/pos_labels.json.gz
   * ({tag: label}). Anything else — a missing map, a missing tag, a
   * non-string label — returns "", never the tag itself.
   */
  function posDisplay(tag, labels) {
    var key, found;
    if (typeof tag !== "string") return "";
    key = tag.trim();
    if (key === "") return "";
    if (!labels || typeof labels !== "object" || Array.isArray(labels)) return "";
    found = cleanString(labels[key]);
    return found;
  }

  // Classic script on the site; CommonJS for Node harnesses. Same file, same
  // implementation, no second copy.
  root.posDisplay = posDisplay;
  if (typeof module !== "undefined" && module.exports) module.exports = posDisplay;
})(typeof globalThis !== "undefined" ? globalThis : this);
