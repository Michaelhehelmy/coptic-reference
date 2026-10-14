# SHIP.md — the Coptic language reference

The document a new maintainer reads first. Written at the end of Session 15.

## Status

**Preview, live and verified. Production, prepared but not promoted.**

| | |
|---|---|
| Preview | `https://session-14.coptic-reference.pages.dev` (Session 14 build) |
| **Production** | **`https://coptic-reference.pages.dev`** — deployed Session 15, checklist 10/10 |
| Repository | 11 commits on `master`, clean tree, `sources.lock` untouched (4 VERIFY markers intact) |
| Tests | 330 passed, 22 skipped, 1 xfailed |
| Guards | 17, all pass, all run inside `tools/build.py` |
| Learning layer | Session 16: `/quiz/`, 959 data-derived items, browser-local progress |
| Lighthouse | `/dict/` 90/93→**100**/96/100, `/corpus/sahidic_ruth/` 78/**92→100**/96/100 |

## What is live (on the preview)

- **`/dict/`** — 11,369 entries. Coptic search via Pagefind, English gloss
  search via the static workaround, merged and deduped. Capital folding and
  combining-mark stripping from shipped tables, not guessed ranges.
- **`/corpus/<work>/`** — six parsed texts, token → lemma → dictionary → corpus
  round trip, on `verse_index` (0..N-1, unique per work).
- **`/quiz/`** — seven data-derived quiz types in 19 static banks. Ten-question
  sessions, localStorage scoring, spaced repetition, JSON export/import, and a
  static no-JS topic list. Progress never leaves the browser.
- **Offline** — the service worker registers, precaches exactly 8 declared
  entries, and serves the dictionary with the network off.
- **CSP** — `script-src 'self' 'wasm-unsafe-eval'`, no `unsafe-inline`, zero
  console violations on every route.

## What is not

- **Pagefind English search** is served by `static/js/search.js` and
  `data/search/english_index.json.gz`, not by Pagefind. Six terms
  (`copper carbonate coin rust fire green`) are dropped by Pagefind 1.5.2 itself.
  Reported: **PageFind/PageFind#1370**, review date **2027-04-01**. If it is fixed,
  delete the script, drop `tools/build.py` step 3c, delete
  `tools/emit/english_index.py` — in that order.
- **Four `VERIFY: reconstructed 2026-10-06` markers** in `tools/sources.lock` are
  unresolved. A deploy does not resolve them.
- **`sources/**/*.tt`** is fetched, not vendored. A clean clone needs
  `tools/fetch/fetch_work.py` first — it is HANDOFF.md §5 step 1.

## How to build locally

```sh
.venv/bin/python tools/fetch/fetch_work.py --tarball /tmp/corpora.tarball.tar.gz
.venv/bin/python tools/fetch/fetch_work.py --check
export PATH="$HOME/.local/bin:/usr/local/bin:$PATH"
.venv/bin/python tools/build.py            # must print "guard PASSED"
.venv/bin/python -m pytest tools/tests -q  # 330 passed, 22 skipped, 1 xfailed
```

Needs Hugo 0.128.0 and Node 22 on PATH. Pagefind resolves from
`node_modules` (`npm ci` once). No `PAGEFIND_BIN` needed.

## How to deploy updates

```sh
export WRANGLER_SEND_METRICS=false        # else the deploy fails on telemetry
npx wrangler pages deploy public --project-name coptic-reference --branch <name>
```

Two quirks that will otherwise cost you time: telemetry must be disabled, and the
OAuth token cannot refresh itself (Node's `fetch` cannot reach the auth server
that `curl` reaches fine) — re-running the command usually succeeds, `wrangler
login` is the fallback and is interactive.

Full runbook: `DEPLOY.md`. Post-deploy verification: `POST_DEPLOY_CHECKLIST.md`
(10 items; the precache check compares declared-vs-served with calibration).
Production promotion: `PRE_PRODUCTION_CHECKLIST.md`.

## Review date

**Pagefind#1370 — 2027-04-01.** Until then the workaround stands.

## Production verification (Session 15)

Against `https://coptic-reference.pages.dev`, in Chromium via Playwright:

| # | Check | Result |
|---|---|---|
| 1 | Manifest from the CDN | 143 files |
| 2 | Routes | 8 checked, all 200 |
| 3 | Service worker | 1 registration, scope `/` |
| 4 | Cache | 8 entries = 8 declared |
| 5 | Coptic search | `ⲧⲉⲛⲟⲩ` → 1 |
| 5 | English search | `copper` → 19 |
| 6 | Headers | `service-worker-allowed: /` |
| 7 | gzip | `application/gzip`, no `Content-Encoding` |
| 8 | U+FE26 lemma | `ⲃ︦` → 297 |
| 9 | Corpus | 3,470 spans, `ⲛⲧⲟⲥ`, back to `/corpus/sahidic_ruth/` |
| 10 | CSP violations | none |

Lighthouse on production: `/dict/` **85/100/100/100**, `/corpus/sahidic_ruth/`
**97/100/100/100** (perf/a11y/best-practices/SEO). Both accessibility scores are
100. Best-practices is 100 on both (was 96 locally — the CDN serves the headers
the local server never did, which is Rule 9 in one number).

## Who to contact

Maintainer: **Michael Helmy** (AUTHORS.md, GOVERNANCE.md).
Upstream search bug: <https://github.com/PageFind/PageFind/issues/1370>.
