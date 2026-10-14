/* static/js/corpus.js — the /corpus/<work>/ reader.
 *
 * Session 10 D3.
 *
 * Fetches the SAME two .json.gz files the dictionary's corpus counts were
 * computed from. Nothing here re-parses TT and nothing here invents alignment:
 * if the data has no per-token English, the reader shows the English verse.
 *
 * Two links close the loop:
 *   token -> /dict/?q=<norm>          look the word up
 *   dictionary entry -> /corpus/<slug>/#<ref-anchor>   come back here
 */
(() => {
  "use strict";

  const ROOT = "/data/corpus/";
  const status = document.getElementById("corpus-status");
  const body = document.getElementById("corpus-body");
  const panel = document.getElementById("corpus-entry");

  // The work slug is in the path; Hugo mounts this script only under /corpus/.
  const m = location.pathname.match(/^\/corpus\/([a-z0-9_]+)\/?$/i);
  const slug = m && m[1];
  if (!slug || !body) return;

  const setStatus = (t, cls) => {
    if (status) {
      status.textContent = t;
      status.className = cls || "note";
    }
  };

  const esc = (s) =>
    String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const legacyAnchor = (ref) =>
    String(ref).toLowerCase().replace(/[^0-9a-z]+/g, "-").replace(/^-|-$/g, "") || "v";

  /* Anchor for a verse.
   *
   * Built from verse_index, not ref. `ref` is not unique within a work —
   * bohairic_mark's 678 verses share 72 refs — so ref-based anchors produced
   * DUPLICATE id attributes, and every "#1" link landed on whichever verse came
   * first. Session 12 D1.
   */
  const anchorFor = (v) => "v" + v.verse_index;

  // Shared helper, Session 12 D0. Sniffs 1f 8b so it works whether or not the
  // host sets Content-Encoding: gzip.
  async function fetchGz(url) {
    if (typeof FetchJson === "undefined") {
      throw new Error("fetch_json.js did not load before corpus.js");
    }
    return FetchJson.json(url, { cache: "force-cache" });
  }

  function renderVerses(verses, byVindex) {
    return verses
      .map((v) => {
        const toks = byVindex.get(v.verse_index) || [];
        // The Coptic token stream: one clickable span per token, carrying the
        // normalised form so the dictionary lookup uses the same folding the
        // index was built with.
        const cop = toks.length
          ? toks
              .map(
                (t, i) =>
                  `<span class="tk" tabindex="0" role="link" data-i="${i}" ` +
                  `data-norm="${esc(t.norm || t.lemma || "")}" ` +
                  `data-lemma="${esc(t.lemma || "")}" data-pos="${esc(t.pos || "")}" ` +
                  `title="${esc((t.lemma || "") + (t.pos ? " · " + t.pos : ""))}">${esc(t.form)}</span>`
              )
              .join(" ")
          : `<span class="cop-raw">${esc(v.coptic || "")}</span>`;
        return (
          `<section class="verse" id="${esc(anchorFor(v))}" ` +
          `data-vindex="${esc(v.verse_index)}" data-ref="${esc(v.ref)}">` +
          `<h2><a class="urn" href="#${esc(anchorFor(v))}">${esc(v.ref)}</a>` +
          (v.urn ? ` <span class="urn note" title="CTS URN">${esc(v.urn)}</span>` : "") +
          `</h2>` +
          `<p class="cop" lang="cop" dir="ltr">${cop}</p>` +
          `<p class="en">${esc(v.en || "")}</p>` +
          `</section>`
        );
      })
      .join("");
  }

  function showToken(tok) {
    if (!panel) return;
    const lemma = tok.lemma || "";
    panel.innerHTML =
      `<h3>${esc(tok.form || "")}</h3>` +
      `<p><strong>Lemma</strong> ${esc(lemma || "—")}` +
      (tok.norm && tok.norm !== lemma ? ` · <span class="note">normalised ${esc(tok.norm)}</span>` : "") +
      `</p>` +
      (tok.pos ? `<p><strong>Tag</strong> <code>${esc(tok.pos)}</code>` +
        (tok.func ? ` · function <code>${esc(tok.func)}</code>` : "") +
        `</p>` : "") +
      (tok.head && tok.head !== "#" ? `<p class="note">head <code>${esc(tok.head)}</code></p>` : "") +
      // Link by LEMMA, not by norm.
      //
      // Ruth 1:1 token 5 is form ⲛⲉ with lemma ⲡ. Linking by norm sent the reader
      // to the entry for ⲛⲉ while the panel said "Lemma ⲡ" — the link text and the
      // link target disagreed, and the lemma the parser assigned was discarded.
      // A lemma is the headword a reader wants; linking anywhere else throws away
      // the one piece of analysis the corpus actually adds.
      //
      // Trade-off, stated: a lemma absent from the dictionary index yields
      // "no headword" rather than a link to the inflected form. That is the
      // honest outcome — the reader is not a lemmatiser, and silently opening a
      // different word is worse than saying it has none.
      (lemma
        ? `<p><a class="btn" href="/dict/?q=${encodeURIComponent(lemma)}">Look up ${esc(lemma)} in the dictionary →</a></p>`
        : `<p class="note">No lemma recorded, so no dictionary lookup.</p>`);
    panel.scrollIntoView({ block: "nearest" });
  }

  (async () => {
    try {
      setStatus("Loading text and tokens …");
      const [textDoc, tokDoc] = await Promise.all([
        fetchGz(ROOT + slug + "/text.json.gz"),
        fetchGz(ROOT + slug + "/tokens.json.gz"),
      ]);

      // Keyed on verse_index, NOT ref. Session 12 D1 / C4.
      //
      // Keying on ref pooled every token from every colliding verse: with
      // bohairic_mark, verse "1" carried 542 tokens and appeared in 16 verses,
      // so each of those 16 rendered the union — 276,522 token spans for 20,322
      // tokens, and a reader clicking a word got one from a different verse.
      //
      // verse_index is 0..N-1 within the work and unique by construction. `ref`
      // is still displayed, and still available on the element as data-ref.
      const byVindex = new Map();
      for (const t of tokDoc.tokens || []) {
        const k = t.verse_index;
        if (k === undefined) {
          throw new Error(
            "tokens.json has a token with no verse_index (ref " + t.ref +
            "). Re-emit the corpus: tools/emit/corpus_tarball.py");
        }
        if (!byVindex.has(k)) byVindex.set(k, []);
        byVindex.get(k).push(t);
      }
      for (const list of byVindex.values()) list.sort((a, b) => (a.i || 0) - (b.i || 0));

      const verses = textDoc.verses || [];
      const nTok = (tokDoc.tokens || []).length;
      body.innerHTML =
        `<p class="count">${verses.length} verses · ${nTok} tokens · ` +
        `<a href="${ROOT}${slug}/text.json.gz">text.json.gz</a> · ` +
        `<a href="${ROOT}${slug}/tokens.json.gz">tokens.json.gz</a></p>` +
        renderVerses(verses, byVindex);

      // Delegated, so it works for tokens rendered long after this runs.
      body.addEventListener("click", (e) => {
        const el = e.target.closest("span.tk");
        if (!el) return;
        // Read the verse index from data-vindex, never from the heading's
        // textContent: the heading also contains the CTS URN, so textContent is
        // "Ruth 1:1 urn:cts:copticLit:..." and a text-derived key misses. That
        // was Session 10's bug and it cost every token panel its lemma.
        const vindex = Number(el.closest(".verse").dataset.vindex);
        const list = byVindex.get(vindex) || [];
        showToken(list[Number(el.dataset.i)] || { form: el.textContent, norm: el.dataset.norm });
      });

      setStatus(
        `Showing ${verses.length} verses and ${nTok} tokens. Click any Coptic token.`,
        "note"
      );
    } catch (e) {
      // Fail visibly. A corpus page that silently shows nothing reads as "there
      // is no text here", which is a different and wrong claim.
      setStatus("Could not load this text: " + (e && e.message), "note err");
      if (body) {
        body.innerHTML =
          `<p class="err">The parsed text is published as compressed JSON at ` +
          `<code>${esc(ROOT + slug)}/text.json.gz</code> and ` +
          `<code>tokens.json.gz</code>. If those load in your browser, the script ` +
          `failed rather than the data being missing.</p>`;
      }
    }
  })();
})();
