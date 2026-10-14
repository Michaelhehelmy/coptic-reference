/* static/js/search.js — merges Pagefind (Coptic) with a static English index.
 *
 * LICENCE: project code, Apache-2.0.
 *
 * Session 14 D2 / C3.
 *
 * The problem this exists to solve. Pagefind 1.5.2 silently drops a fixed set of
 * English gloss terms from its index — copper, carbonate, coin, rust, fire,
 * green — while indexing their neighbours in the same document. English search on
 * this site has therefore been decorative since Session 9: `azurite` returned 9
 * hits, `copper` returned 0, in the very same document.
 *
 * Filed upstream as PageFind/PageFind#1370 with a three-word reproduction.
 * Until it is fixed, this path serves the terms Pagefind loses.
 *
 * Design, in one line: Coptic goes to Pagefind, Latin goes to a static inverted
 * index, and mixed queries merge and dedupe.
 *
 * Why not fix pagefind_index.mjs: the terms are dropped by Pagefind's WRITER, so
 * there is no configuration to change. The only lever is the data we publish.
 * This adds ~148 KB gzipped of static JSON to the same origin — no runtime
 * dependency, no server, no account (invariants 1–4).
 *
 * Entry ids are "<shard>-<offset>", which is what the dictionary index already
 * carries, so resolving an id to a lemma uses the index the page has already
 * fetched. No second lookup table ships.
 */
(function (root) {
  "use strict";

  const EN_INDEX_URL = "/data/search/english_index.json.gz";

  let enIndex = null;        // {terms: {...}, version}
  let enPromise = null;      // in-flight fetch, so concurrent callers share it

  /** Coptic and other non-Latin scripts go to Pagefind; Latin to the static index. */
  function splitQuery(q) {
    const s = String(q || "").trim();
    if (!s) return { latin: [], other: "" };
    const m = s.match(/[\p{Script=Latin}\p{M}\p{N}'\- ]+/gu) || [];
    const latin = s.match(/[A-Za-z][A-Za-z'\-]*/g) || [];
    return { latin, other: s.replace(/[A-Za-z][A-Za-z'\-]*/g, " ").trim() };
  }

  async function load() {
    if (enIndex) return enIndex;
    if (!enPromise) {
      enPromise = (async () => {
        const doc = await root.FetchJson.json(EN_INDEX_URL, { cache: "force-cache" });
        enIndex = doc;
        return doc;
      })().catch((e) => {
        // Surface it rather than pretending English search works. This is a
        // degraded path, not the main one, so a failure must not break the page.
        console.warn("[search] English index unavailable:", e && e.message);
        enIndex = { terms: {}, version: "", failed: true };
        return enIndex;
      });
    }
    return enPromise;
  }

  /** Terms in the English index, longest-first so "copper" beats "cop". */
  async function englishTerms(q) {
    const doc = await load();
    if (!doc.terms) return [];
    const words = String(q || "").toLowerCase().match(/[a-z][a-z'\-]*/g) || [];
    const hits = new Set();
    for (const w of words) {
      if (doc.terms[w]) for (const id of doc.terms[w]) hits.add(id);
    }
    return [...hits];
  }

  /**
   * Resolve English-index entry ids to dictionary rows.
   * `byId` is built from the index rows the reader already has.
   */
  function resolve(ids, byId) {
    const out = [];
    const seen = new Set();
    for (const id of ids) {
      if (seen.has(id)) continue;
      seen.add(id);
      const row = byId.get(id);
      if (row) out.push(row);
    }
    return out;
  }

  /** Prefix matches, so "copper-sel" still finds "coppersmith"-style entries. */
  async function englishPrefix(q) {
    const doc = await load();
    if (!doc.terms) return [];
    const words = String(q || "").toLowerCase().match(/[a-z][a-z'\-]*/g) || [];
    const hits = new Set();
    for (const w of words) {
      if (w.length < 2) continue;
      for (const t of Object.keys(doc.terms)) {
        if (t.startsWith(w)) for (const id of doc.terms[t]) hits.add(id);
      }
    }
    return [...hits];
  }

  const Search = { load, englishTerms, englishPrefix, resolve, splitQuery,
                   EN_INDEX_URL };

  root.Search = Search;
  if (typeof module !== "undefined" && module.exports) module.exports = Search;
})(typeof globalThis !== "undefined" ? globalThis : this);