# POST_DEPLOY_CHECKLIST.md — verify the deployed site

Prepared Session 11 (D5). Run this **after** the first deploy, against the live
URL. Every item exists because a build-time guard cannot check it: guards verify
files, and these verify behaviour (HANDOFF.md §8a Rule 7).

Set `URL` to the deployed origin first:

```sh
URL=https://<your-project>.pages.dev
```

Record the result of each line. Anything marked ✗ is a blocker.

## 1. File count and size

```sh
curl -sS "$URL/BUILD-MANIFEST.json" | python3 -c "
import json,sys
m=json.load(sys.stdin)
print('files :', len(m['files']))
print('bytes :', f\"{m['total_bytes']:,}\")"
```

- ✗ fails · ✓ **114 files, 8,075,302 B** at Session 11

Compare against `tools/validate/size_guard.py` budgets: `data/dist` < 5 MiB,
`public` < 20 MiB. If either is exceeded, stop.

## 2. The routes exist

```sh
for p in / /dict/ /corpus/ /corpus/sahidic_ruth/ /corpus/bohairic_mark/ \
         /licences/ /dialects/ /sw.js /sitemap.xml; do
  printf "%-28s %s\n" "$p" "$(curl -sS -o /dev/null -w '%{http_code}' "$URL$p")"
done
```

- ✗ fails · ✓ **200**

All six works must be listed. `/corpus/` should link
`bohairic_1corinthians`, `bohairic_mark`, `lausiac_history`, `life_of_isaac`,
`martyrdom_of_victor`, `sahidic_ruth`.

## 3. The service worker registers

Browser console, on any page:

```js
navigator.serviceWorker.getRegistrations().then(r =>
  console.log('registrations:', r.length, r.map(x => x.scope)))
// expect: registrations: 1 …/…/
```

- ✗ `0` — **the Session 10 bug is live on the deploy**. `sw.js` will be served
  and pass every guard while caching nothing.
- Also check `chrome://serviceworker-internals` or DevTools → Application →
  Service Workers for **activated and running**.
- ✗ DevTools console shows a CSP violation for the inline registration block.
  See DEPLOY.md §5 — fix the CSP, do not remove the registration.

## 4. Offline actually works

DevTools → Network → **Offline**, then hard-reload `/dict/`:

- ✗ page is blank or the browser reports a network error
- ✓ the dictionary renders and `#count-all` shows `11,369 entries`

Then, still offline, search for `ⲧⲉⲛⲟⲩ` and confirm an entry renders.

```js
// Count DECLARED vs SERVED, and calibrate first (Rule 10).
// Do not trust a bare `caches.open(ks[0])` read: it races the worker's
// install, and it reports 0 on a perfectly healthy site — which it did on the
// Session 14 deploy. Read every cache, and compare to the PRECACHE array in sw.js.
(async () => {
  const per = {};
  for (const k of await caches.keys()) {
    const c = await caches.open(k);
    per[k] = (await c.keys()).map(r => new URL(r.url).pathname);
  }
  const declared = (await (await fetch('/sw.js')).text())
    .match(/const PRECACHE = (\[.*?\]);/s)[1];
  console.log('declared', JSON.parse(declared).length,
              'served', Object.values(per).reduce((a, v) => a + v.length, 0));
  console.log(per);
})()
// expect: declared 8  served 8
```

- ✗ `served 0` — the worker is not caching; see §3.
- ✗ `declared != served` — compare the two lists; a declared URL the worker could
  not fetch is an install failure, not a slow cache.

## 5. Pagefind loads

```js
// in the console, on any page
import('/pagefind/pagefind.js')
  .then(pf => pf.search('ⲧⲉⲛⲟⲩ'))
  .then(r => console.log('hits:', r.results.length))
```

- ✗ the import rejects, or `hits: 0` for a known Coptic headword — the index
  did not deploy. Check that `public/pagefind/` is non-empty in the build log.

**Known defect, expected on this deploy:** searching `copper` returns **0** hits
while `azurite` returns 9. This is the open Pagefind English bug (DECISIONS.md,
Session 11 D1) and is **not** a deployment error. Log it, do not treat the
deploy as failed for it, and do not "fix" it by changing the index configuration
— the mechanism is not yet understood.

## 6. Headers are correct

```sh
curl -sSI "$URL/sw.js"        | grep -i "service-worker-allowed\|cache-control"
curl -sSI "$URL/data/dist/dict/index.json.gz" | grep -i "cache-control\|content-encoding\|access-control"
curl -sSI "$URL/"             | grep -i "x-content-type-options\|content-security-policy"
```

- ✗ `Service-Worker-Allowed` missing from `/sw.js` → the worker cannot control
  `/` and offline silently fails on first load.
- ✗ `Cache-Control` missing from `/data/*` → the reading path refetches the
  dictionary index on every page load.

## 7. gzip behaviour observed

```sh
curl -sS -H "Accept-Encoding: gzip" -o /tmp/g.bin \
  -w "size=%{size_download} encoding=%{content_type}\n" \
  "$URL/data/dist/dict/index.json.gz"
file /tmp/g.bin
```

- If the response was decoded, `file` reports JSON or ASCII text.
- If raw gzip came through, `file` reports "gzip compressed data".
- **Both are acceptable.** The readers sniff `1f 8b` and handle either. What is
  *not* acceptable is a truncated or corrupt payload — then the dictionary fails
  to load and `#results` shows an error.

## 8. The dictionary works

- `/dict/` → type `ⲧⲉⲛⲟⲩ` → an entry renders with gloss `now`.
- Type `ⲧⲉⲛⲟⲩ` with a **capital** `ⲧ` → still matches (case folding is shipped in
  `index.json` as `casefold`).
- Type `ⲃ︦` (U+2C83 + U+FE26) → matches. That code point only works because
  `strip_chars` is shipped in the index; if search fails here, the index was
  built from a stale `data/dist`.

## 9. The corpus round trip works

- `/corpus/sahidic_ruth/` → verses render, status reads
  "Showing 85 verses and 3470 tokens".
- Click any token → the panel shows its form and lemma.
- Click "Look up …" → `/dict/?q=…` opens with the right entry.
- From that entry, a `worklink` returns to `/corpus/<work>/`.

**Known defect, expected on this deploy:** for five of the six works the tokens
under each verse are wrong, because verse refs are not unique within a work
(`bohairic_mark` has 678 verses and 72 distinct refs). Ruth is the only correct
one. Do not report this as a deploy failure — it is the
`KNOWN DEFECT` documented in `tools/tests/playwright/test_corpus_works.py` and
DECISIONS.md. **Do not ship a claim of corpus correctness for those five works.**

## 10. Reproducibility

```sh
git rev-parse HEAD
curl -sS "$URL/BUILD-MANIFEST.json" | python3 -c "import json,sys;print(json.load(sys.stdin).get('generated'))"
```

The manifest timestamp is derived from the **inputs**, never from `now()`, so a
rebuild of the same commit must produce the same manifest. If the two builds
differ, something is reading the clock and the "byte-reproducible index" claim
is false.

## Sign-off

| # | Item | Result |
|---|---|---|
| 1 | File count and size | |
| 2 | Routes return 200 | |
| 3 | Service worker registers | |
| 4 | Offline renders and caches 8 entries | |
| 5 | Pagefind loads (Coptic hits > 0) | |
| 6 | Headers correct | |
| 7 | gzip observed and not corrupt | |
| 8 | Dictionary search works incl. U+FE26 lemma | |
| 9 | Corpus round trip works (Ruth only) | |
| 10 | Manifest reproducible | |

Two items are expected to fail on first deploy and are **not** deploy blockers:
§5 for the word `copper` and §9 for the five non-Ruth works. Everything else must
pass.


---

## Session 13 — first real run, against `session-13.coptic-reference.pages.dev`

Run in a real browser against the deployed origin, not a local server.

| # | Item | Result |
|---|---|---|
| 1 | File count and size | **PASS** — 116 uploaded by wrangler; manifest reports 141 entries |
| 2 | Routes return 200 | **PASS** — `/`, `/dict/`, `/corpus/`, `/corpus/sahidic_ruth/`, `/licences/`, `/dialects/`, `/sw.js`, `/sitemap.xml` all 200 |
| 3 | Service worker registers | **PASS** — 1 registration, scope `/` |
| 4 | Offline renders and caches 8 entries | **PASS** — 8 cached, exactly the precache list |
| 5 | Pagefind loads | **PASS** — `ⲧⲉⲛⲟⲩ` → 1 hit |
| 6 | Headers correct | **PASS** — CSP served; `service-worker-allowed: /`; `/data/*` immutable |
| 7 | gzip observed and not corrupt | **PASS** — `application/gzip`, **no** `Content-Encoding`; the sniffing readers handle it |
| 8 | Dictionary search incl. U+FE26 | **PASS** — `/dict/?q=ⲃ︦` → 297 hits, entry `ⲃ︦` |
| 9 | Corpus round trip | **PASS** — 85 verses, 3,470 spans, token → dictionary → corpus |
| 10 | Manifest reproducible | **PASS** |

**Expected failures, both still open and neither a deploy problem:**

- §5, `copper` → 0 hits. Session 13 isolated the cause to a property of the term
  inside Pagefind itself: one record whose content is exactly
  `"copper carbonate, azurite"` returns 9 for `azurite` and 0 for `copper`. Refuted
  in this project: co-occurrence, scale, script mixing, `weighted_ngrams`,
  `excerpts`, language flag and word order. See DECISIONS.md.
- The CDN serves `_headers` as a public `text/html` file. Benign — it is
  configuration, not secret — but it does publish the policy.

**CSP violations in the deployed console: NONE.** This is the check that matters
most and it is only possible on the real origin; `'wasm-unsafe-eval'` is what
makes Pagefind's WebAssembly load at all.
