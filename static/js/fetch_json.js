/* static/js/fetch_json.js — the ONE place this project fetches and inflates.
 *
 * LICENCE: project code, Apache-2.0.
 *
 * Session 12 D0 / C2.
 *
 * Why this file exists. Three call sites each had their own copy of "fetch a
 * .json.gz and turn it into text":
 *
 *   static/js/reader.js       sniffed the magic bytes   (fixed Session 11)
 *   static/js/corpus.js       sniffed the magic bytes
 *   static/read-csv.html      inflated UNCONDITIONALLY  (still broken)
 *
 * That is Rule 8's failure mode in production form. A concept had three files,
 * they drifted, and the third was still the pre-Session-11 bug — it would have
 * thrown on every .gz it read as soon as the host set Content-Encoding: gzip.
 * Nothing caught it because no test opened read-csv.html in a browser against a
 * host that sends the header.
 *
 * So: one implementation, used by all three, and tested against BOTH branches.
 *
 * The branch that matters
 * -----------------------
 *   Content-Encoding: gzip  ->  the browser has ALREADY inflated the body
 *   no header               ->  the bytes are raw gzip and must be inflated here
 *
 * Sniffing 1f 8b handles both, and is the same rule the service worker follows.
 * Assuming either one is what breaks the site on the other host.
 */
(function (root) {
  "use strict";

  const GZ0 = 0x1f;
  const GZ1 = 0x8b;

  /** Is this buffer gzip-compressed? Sniffs, never trusts a header. */
  function isGzip(buf) {
    if (!buf || buf.byteLength < 2) return false;
    const b = new Uint8Array(buf, 0, 2);
    return b[0] === GZ0 && b[1] === GZ1;
  }

  async function inflate(buf) {
    const ds = new DecompressionStream("gzip");
    return new Response(new Blob([buf]).stream().pipeThrough(ds)).text();
  }

  /**
   * Fetch `url` and return its body as text, inflating only if it is gzip.
   *
   * Fails with a message that names the URL and the reason. A reader that
   * silently renders an empty table is indistinguishable from a work with no
   * data, which is a different and wrong claim.
   */
  async function text(url, opts) {
    let res;
    try {
      res = await fetch(url, opts);
    } catch (e) {
      // Network failure, DNS, offline with nothing cached.
      throw new Error(`${url}: ${(e && e.message) || e}`);
    }
    if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);

    const buf = await res.arrayBuffer();
    if (!buf.byteLength) throw new Error(`${url}: empty response`);

    let out;
    try {
      out = isGzip(buf) ? await inflate(buf) : new TextDecoder().decode(buf);
    } catch (e) {
      // Truncated or corrupt gzip. Say so: "not valid JSON" hides the cause.
      throw new Error(
        `${url}: could not decompress (${isGzip(buf) ? "gzip" : "plain"} body): ` +
        `${(e && e.message) || e}`);
    }
    if (!out.length) throw new Error(`${url}: decoded to an empty string`);
    return out;
  }

  /** Fetch and parse JSON. Same failure contract as text(). */
  async function json(url, opts) {
    const body = await text(url, opts);
    try {
      return JSON.parse(body);
    } catch (e) {
      throw new Error(`${url}: body is not valid JSON — ${(e && e.message) || e}`);
    }
  }

  const FetchJson = { text, json, isGzip };

  // Classic script (the site loads these with <script src>, not type=module),
  // and CommonJS so the Node harnesses can require the same file the browser
  // runs. One implementation, two consumers, no second copy.
  root.FetchJson = FetchJson;
  if (typeof module !== "undefined" && module.exports) module.exports = FetchJson;
})(typeof globalThis !== "undefined" ? globalThis : this);
