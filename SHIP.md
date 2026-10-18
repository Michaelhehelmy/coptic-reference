# SHIP.md — the Coptic language reference

The document a new maintainer reads first. Written at the end of Session 15.

## Status

**Production live and verified (Session 23). A `git push` does not deploy
this project — see “How to deploy updates”.**

| | |
|---|---|
| Preview | `https://session-14.coptic-reference.pages.dev` (Session 14 build) |
| **Production** | **`https://coptic-reference.pages.dev`** — Session 23 direct upload (`08459596`), post-deploy checks pass; production was stale (Session 15 content, 404s for Sessions 16–22 routes) until Session 23 D0 |
| Repository | `master` through Session 23 (this session's code: deck fix `1d2f47b`, rules + packet `5d76fdf`, walk fixes `02f751b`, plus this session's docs commits), clean tree, `sources.lock` untouched (4 VERIFY markers intact) |
| Tests | 454 passed, 22 skipped, 1 xfailed |
| Guards | all pass; the guards that guard the build run inside `tools/build.py`, the rest in `pytest tools/tests/` |
| Learning layer | Session 16: `/quiz/`, 959 items · Session 18–20: `/drill/`, 2,589 cloze + 5,174 parse items · Session 19–20: `/course/`, 15 lessons teaching · Session 21: `/write/`, 35 tracing references, browser-local progress · Session 22: `/speak/`, top-100 self-comparison recorder · `/anki/`, 959 quiz + 2,589 cloze cards downloadable (Session 23 replaced the 300-card `vocab.apkg` subset) · Session 23: `/expert-review-packet/`, every open expert verdict in one place |
| Signing | Commits are unsigned — deliberate project state, not an omission. No signing key exists by policy; nothing in the pipeline verifies signatures. Recorded once here instead of per session. Rationale and contributor setup: HANDOFF.md §8a. |
| Lighthouse | `/dict/` 90/93→**100**/96→**100**/100 (favicon, Session 22), `/corpus/sahidic_ruth/` 78/**92→100**/96/100, `/speak/` **100/100/100/100** |

## What is live (on the preview)

- **`/dict/`** — 11,369 entries. Coptic search via Pagefind, English gloss
  search via the static workaround, merged and deduped. Capital folding and
  combining-mark stripping from shipped tables, not guessed ranges.
- **`/corpus/<work>/`** — six parsed texts, token → lemma → dictionary → corpus
  round trip, on `verse_index` (0..N-1, unique per work).
- **`/quiz/`** — seven data-derived quiz types in 19 static banks. Ten-question
  sessions, localStorage scoring, spaced repetition, JSON export/import, and a
  static no-JS topic list. Progress never leaves the browser.
- **`/drill/`** — cloze drills from real corpus verses, 2,589 items in 6
  per-work banks (lexical blanks only since Session 19 D1). Ten-drill
  sessions, localStorage scoring, answer linked to
  its dictionary entry, and a static no-JS work list. Every answer re-read
  from the tarball by `drill_guard.py`.
- **`/course/`** — fifteen lessons chaining reading, quiz, drill, passage,
  and checkpoint. Checkpoints are real ten-question sessions (70% unlocks
  next, override available); lessons 1–5 teach, 6–15 carry filters with a
  Session 20 TODO. `course_guard.py` checks every filter resolves to data.
- **`/speak/`** — the top 100 lemmas by corpus occurrence, three
  transliteration schemes, record and compare in the browser. No ASR, no
  score, no upload: the banner says so and a test asserts the feedback
  area never renders a score. No-JS visitors get `/speak/top100.html`, a
  static table.
- **`/anki/`** — `quiz.apkg` (all 959 quiz-bank items across 19 banks) and
  `drill.apkg` (all 2,589 cloze items), generated at build time from the
  same banks the site serves, downloadable with no account. (Session 23 D1
  replaced the Session 22 `vocab.apkg` 300-card subset.)
- **Offline** — the service worker registers, precaches exactly 8 declared
  entries, and serves the dictionary with the network off.
- **CSP** — `script-src 'self' 'wasm-unsafe-eval'`, `media-src 'self'
  blob:` (Session 22, for the recorder), no `unsafe-inline`, zero console
  violations on every route.

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
.venv/bin/python -m pytest tools/tests -q  # 454 passed, 22 skipped, 1 xfailed
```

Needs Hugo 0.128.0 and Node 22 on PATH. Pagefind resolves from
`node_modules` (`npm ci` once). No `PAGEFIND_BIN` needed.

## How to deploy updates

```sh
export WRANGLER_SEND_METRICS=false        # else the deploy fails on telemetry
npx wrangler pages deploy public --project-name coptic-reference --branch master
```

**A push does not deploy.** The Pages project is git-connected to this
repository, but its builds have produced empty 404 deployments since
Session 15 (dashboard config, not fixable from the CLI) — every push
from Session 15 through Session 22 changed production nothing while the
live site silently decayed. The working path is the direct upload above,
which reads the already-baked `public/` tree. After any code or content
change: rebuild → run the checklist → deploy → verify on the public URL
(Rule 16, CONTRIBUTING.md). `git push` is for history; it is not a
release step.

Two other quirks that will otherwise cost you time: telemetry must be
disabled, and the OAuth token sometimes cannot refresh itself (a network
or IPv6 issue) — re-running the command usually succeeds, `wrangler
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

## Production verification (Session 23)

Deployment `08459596`, direct upload of the post-D4 `public/` tree, verified
against `https://coptic-reference.pages.dev` (HTTP checks with a browser
User-Agent — Cloudflare 403s Python-urllib's default UA; browser checks in
Chromium via Playwright):

| Check | Result |
|---|---|
| Routes | all 25 sitemap routes 200 (incl. `/expert-review-packet/`, every lesson route) |
| Titles | all 40 sitemap titles non-empty and correct, incl. the 4 fixed in D4 |
| `/lessons/` anchors | 0 empty `<a></a>`; plan anchor reads “Structured course plan”; no stray `/nc/readme/` link |
| Packet page | both register mirrors present, 31 blank verdict cells (23 grammar + 8 POS) |
| `quiz.apkg` | 200, 676,058 B — exact local size, PK zip, 959 notes |
| `drill.apkg` | 200, 3,514,586 B, 2,589 notes, 2,134 `coptic.re` dictionary links, 0 `pages.dev` |
| `vocab.apkg` | no longer served — apex answers 404; deployment URLs answer with the homepage body (soft-404, `x-robots-tag: noindex`) |
| Service worker | 1 registration; precache 8 = 8 declared (after settle — first read races to 0 during install) |
| Offline | `/dict/` renders with the network off, 11,369 entries |
| Headers | CSP (`default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; …`), `access-control-allow-origin: *`, `service-worker-allowed` |
| Console | zero errors/warnings across `/`, `/expert-review-packet/`, `/lessons/`, `/nc/`, `/anki/` |

Known quirks on this host (both pre-existing, both found Session 23):

- **A status code does not say whether a route exists (Rule 17).**
  Measured Session 23, reproducibly: a missing path on the apex
  (`coptic-reference.pages.dev`) returns a bare **404** (0 bytes,
  `cache-control: no-store`); the same missing path on a deployment
  hostname (`<id>.coptic-reference.pages.dev`) returns **200 + the
  homepage** (`x-robots-tag: noindex` — Pages' soft-404 marker); and a
  git-connected deployment answers **404 for everything, including `/`**
  (empty build). Check the `<title>` and a body marker, or use the
  local `http.server`, which 404s missing paths honestly.
- **The apex edge cache survives deploys.** Assets fetched before a
  deployment can keep serving the old bytes for up to 7 days
  (`s-maxage=604800`, no purge on deploy — observed spanning two
  deployments; e.g. `BUILD-MANIFEST.json` on the apex still reported the
  D0 bake hours after `08459596` shipped the new one). Fresh origin is
  visible at the deployment hostname
  (`https://08459596.coptic-reference.pages.dev/…`), which serves
  `max-age=0, must-revalidate`. When verifying after a deploy, check
  `cf-cache-status`/`age` on anything fetched in an earlier session, or
  fetch it from the deployment URL — otherwise you are reading the
  previous deployment and calling it yours.

## Who to contact

Maintainer: **Michael Helmy** (AUTHORS.md, GOVERNANCE.md).
Upstream search bug: <https://github.com/PageFind/PageFind/issues/1370>.
