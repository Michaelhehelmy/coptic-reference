/* static/js/translit.js — the one place transliteration is rendered.
 *
 * LICENCE: project code, Apache-2.0.
 *
 * Rule 11: exactly one renderer owns every object/array schema field. The
  * `translit` schema value is an object with up to five scheme keys. Any
  * template that interpolates that object renders the raw-object marker; any template
 * that reads one key independently bypasses the fallback policy and will
 * eventually show the wrong or missing value.
 *
 * Therefore every template calls translitDisplay(), and nothing else constructs
 * a transliteration string.
 */
(function (root) {
  "use strict";

  var SCHEMES = ["bohairic", "sahidic", "layton", "till", "egyptological"];

  function cleanString(value) {
    if (typeof value !== "string") return "";
    var text = value.trim();
    return text === "" ? "" : text;
  }

  function firstRomanization(entry) {
    var forms = entry.forms;
    var i, form;
    if (!Array.isArray(forms)) return "";
    for (i = 0; i < forms.length; i += 1) {
      form = forms[i];
      if (form && typeof form === "object" && !Array.isArray(form)
          && form.kind === "romanization") {
        if (cleanString(form.form) !== "") return cleanString(form.form);
      }
    }
    return "";
  }

  /**
   * Render one entry's transliteration.
   *
   * Priority: the requested scheme, then bohairic, then sahidic, then the first
   * nonempty canonical scheme. Empty translit returns "". No object, array,
   * undefined, or raw-object rendering ever leaves this function.
   *
   * The only deliberate exception is the requested pseudo-scheme
   * "romanization": the schema has no romanization key, so this branch returns
   * a Kaikki-derived source romanization from forms[] and never claims that it
   * is Bohairic, Sahidic, or another scheme. Quiz prompts use this branch when
   * source transliteration objects are absent.
   */
  function translitDisplay(entry, scheme) {
    var order, seen, i, key, found;
    if (!entry || typeof entry !== "object" || Array.isArray(entry)) return "";

    if (typeof scheme !== "string" || scheme.trim() === "") scheme = "bohairic";
    scheme = scheme.trim();

    order = [scheme, "bohairic", "sahidic"].concat(SCHEMES);
    seen = {};
    var translit = entry.translit;
    if (scheme === "romanization") return firstRomanization(entry);
    if (translit == null) return "";
    if (typeof translit === "string") return cleanString(translit);
    if (typeof translit !== "object" || Array.isArray(translit)) return "";

    for (i = 0; i < order.length; i += 1) {
      key = order[i];
      if (seen[key]) continue;
      seen[key] = true;
      found = cleanString(translit[key]);
      if (found !== "") return found;
    }
    return "";
  }

  // Classic script on the site; CommonJS for Node harnesses. Same file, same
  // implementation, no second reader of the schema field.
  root.translitDisplay = translitDisplay;
  if (typeof module !== "undefined" && module.exports) module.exports = translitDisplay;
})(typeof globalThis !== "undefined" ? globalThis : this);
