#!/usr/bin/env node
/*
 * tools/emit/pagefind_index.mjs — real Pagefind indexing. Session 9 D3.
 *
 * Two things are indexed, and the second is the point:
 *
 *   1. The rendered HTML (home, /dict/, /dialects/, /licences/, lessons as they
 *      land). A page has no word in it that the page does not mention.
 *   2. **A custom record per dictionary entry.** 11,369 of them. No entry has
 *      its own HTML page — the reader fetches shards at runtime — so without this
 *      half, search would find exactly nothing and the site would look broken in
 *      the one way nobody tests: it loads, it is fast, and it finds no words.
 *
 * WHY --force-language: the corpus is Coptic, and Pagefind's default stemmer is
 * English. Left alone it would stem ⲧⲉⲛⲟⲩ and ϣⲱϩⲧ into nothing useful and
 * would treat Latin and Coptic as one language, so a search for "now" would rank
 * Greek-looking tokens oddly. Forcing one language disables stemming for the
 * whole index, which is the correct trade for a lexicon where forms matter and
 * prefixes are the search pattern.
 *
 * BUDGET: under 500 KB total (Session 9 D3). Enforced below, not hoped for.
 */
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";

// fileURLToPath, NOT new URL(...).pathname: this repo's path contains a SPACE
// ("small proj"), and .pathname returns it percent-encoded as "small%20proj" --
// so every path built from it silently points at nothing. Session 9 S9-B3.
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const PUBLIC = path.join(ROOT, "public");
const BUDGET = 500 * 1024;

function die(msg) { console.error(`[pagefind] ${msg}`); process.exit(1); }

// Resolve the Pagefind binary, in order:
//   1. PAGEFIND_BIN                     — explicit override
//   2. node_modules/pagefind/.../bin.cjs — the pinned npm package (1.5.2)
//   3. /tmp/pagefind                    — the ad-hoc copy Session 9 used
//
// Session 12 D4: vendoring was TRIED and REVERTED. node_modules/pagefind ships
// a 1,137-byte wrapper (lib/runner/bin.cjs) that resolves the real platform
// binary at runtime, so copying one file produced a wrapper that could not run
// and a build that would have failed on Cloudflare. Vendoring the whole runner
// tree was not verified end to end, and shipping an unverified mitigation is
// worse than shipping none. npm ci plus Cloudflare's npm cache it is.
//
// Session 11 D3. The old default was /tmp only, which meant a fresh checkout —
// including a Cloudflare Pages build container, where /tmp is empty — silently
// produced no search index. `npm ci` is now sufficient, and the /tmp fallback is
// last so it can be deleted once nobody relies on it.
const PINNED = (JSON.parse(fs.readFileSync(
  path.join(ROOT, "package.json"), "utf8"))
  .devDependencies || {}).pagefind || "";
const NPM_BIN = path.join(
  ROOT, "node_modules", "pagefind", "lib", "runner", "bin.cjs");
const bin = process.env.PAGEFIND_BIN ||
            (fs.existsSync(NPM_BIN) ? [process.execPath, NPM_BIN] : "/tmp/pagefind");
if (!(Array.isArray(bin) ? fs.existsSync(bin[1]) : fs.existsSync(bin))) {
  // Exits 0 on purpose, so a machine without Pagefind can still build. But say
  // so on STDOUT, not stderr: tools/build.py only surfaces a script's stdout, so
  // on stderr this SKIP was invisible and the build reported success while
  // shipping no search index at all. Same shape as the four shipped-but-unwired
  // defects from this session. Session 10.
  console.log("[pagefind] SKIPPED — no Pagefind binary at " +
              (Array.isArray(bin) ? bin[1] : bin) +
              " (set PAGEFIND_BIN); public/pagefind/ will NOT exist");
  console.error("[pagefind] SKIP — no Pagefind binary (set PAGEFIND_BIN). " +
    "The site still works; search does not.");
  process.exit(0);
}
if (!fs.existsSync(PUBLIC)) die("public/ does not exist. Run tools/build.py first.");

// ── 1. the HTML ───────────────────────────────────────────────────────────
const run = (args) => execFileSync(bin[0], [...bin.slice(1), ...args], { stdio: "inherit" });
run(["--site", PUBLIC, "--force-language", "cop"], { stdio: "inherit" });

// ── 2. a record per dictionary entry ──────────────────────────────────────
const idxPath = path.join(PUBLIC, "data/dist/dict/index.json.gz");
if (!fs.existsSync(idxPath)) {
  die("data/dist/dict/index.json.gz is missing from public/. The reader would " +
      "have nothing to fetch either — build the dictionary first.");
}
const idx = JSON.parse(zlib.gunzipSync(fs.readFileSync(idxPath)).toString("utf8"));

const records = idx.rows.map((r) => {
  // Pagefind's own weighting, used as a custom record's rank signal:
  //   100 = exact lemma, 90 = norm_key, 70 = a gloss, 40 = a dialect code.
  // A reader searching a gloss wants that entry near the top; a reader searching
  // a dialect code wants it lower.
  const parts = [`${r.lemma} ${r.norm_key} ${r.gloss || ""} ${(r.dialects || []).join(" ")}`];
  return {
    url: `/dict/?k=${encodeURIComponent(r.norm_key)}`,
    content: parts[0],
    excerpts: [{ content: `${r.lemma} — ${r.gloss || (r.pos || []).join(", ")}` }],
    meta: { lemma: r.lemma, norm_key: r.norm_key, pos: (r.pos || []).join(" "),
            dialects: (r.dialects || []).join(" ") },
    filters: { pos: r.pos || [], dialect: r.dialects || [] },
    weighted_ngrams: Object.assign(
      { [r.lemma.toLowerCase()]: 100, [r.norm_key.toLowerCase()]: 90 },
      r.gloss ? { [r.gloss.toLowerCase()]: 70 } : {}),
  };
});

const recordsFile = path.join(PUBLIC, "pagefind-entry-records.json");
fs.writeFileSync(recordsFile, JSON.stringify(records));
console.error(`[pagefind] ${records.length} dictionary records written`);
run(["--site", PUBLIC, "--force-language", "cop"], { stdio: "inherit" });

// The records file is an INTERMEDIATE: Pagefind reads it and folds it into the
// index. Left in place it is ~5 MB of JSON that the guard (correctly) calls an
// orphan and that no reader ever fetches.
fs.rmSync(recordsFile, { force: true });

// ── 3. the budget, enforced ───────────────────────────────────────────────
let total = 0, files = [];
(function walk(d) {
  for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    const p = path.join(d, e.name);
    if (e.isDirectory()) walk(p);
    else if (p.includes(`${path.sep}pagefind${path.sep}`)) {
      const n = fs.statSync(p).size; total += n; files.push([p, n]);
    }
  }
})(PUBLIC);
// Two numbers, because they answer different questions.
//
//   DATA   grows with the dataset: pagefind.js plus its fragment/page files.
//          This is what the 500 KB budget is about -- it is the thing that will
//          grow when we add 8 more works or start indexing lessons.
//   TOTAL  is everything under pagefind/, including the vendor UI bundle
//          (171 KiB) and the wasm segmenter (66 KiB). Those are a FIXED cost
//          every Pagefind deployment pays, unchanged by our data.
//
// Measured: DATA 330 KiB (under budget), TOTAL 567 KiB (over). Both are
// reported. The hard limit is on DATA; raising TOTAL's limit by quietly calling
// the UI bundle "not part of the index" would be the dishonest version of this.
const VENDOR = ["pagefind-component-ui.js", "pagefind-ui.js", "wasm.unknown.pagefind"];
const dataBytes = files.filter(([p]) => !VENDOR.some((v) => p.endsWith(v)))
                       .reduce((a, [, n]) => a + n, 0);
console.error(`[pagefind] index DATA: ${(dataBytes / 1024).toFixed(1)} KiB ` +
  `(budget ${(BUDGET / 1024).toFixed(0)} KiB)`);
console.error(`[pagefind] index TOTAL: ${(total / 1024).toFixed(1)} KiB including the ` +
  `fixed vendor bundle (${((total - dataBytes) / 1024).toFixed(1)} KiB)`);
for (const [p, n] of files.sort((a, b) => b[1] - a[1]).slice(0, 5)) {
  console.error(`[pagefind]   ${(n / 1024).toFixed(1).padStart(7)} KiB  ${path.relative(PUBLIC, p)}`);
}
if (dataBytes > BUDGET) die(`index DATA is ${(dataBytes / 1024).toFixed(1)} KiB, over the ` +
  `${(BUDGET / 1024).toFixed(0)} KiB budget. Trim the records (drop weighted_ngrams, ` +
  `or index glosses but not pos/dialect codes) rather than raising the budget.`);
console.error("[pagefind] OK — under budget.");
