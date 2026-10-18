# Guard coverage

What each guard actually inspects, what it catches, and — the column that matters —
**what it would pass silently**.

Written from observation, not from intent. Every guard in `tools/validate/` was
run once against the real tree, then re-run with its inputs removed, to see
whether it noticed. The "would pass silently" column is filled from those runs
and from reading the code path, not from what the guard was meant to do.

The empty-corpus bug of Session 4 happened because guards were described by their
intent. Four of the six bugs found in Sessions 4 and 5 were guards that passed
correctly about a proxy while the thing itself was absent. This file is the
answer to that, and it should be updated whenever a guard is added or changed.

---

## The table

| Guard | What it measures | What it catches | What it would pass silently | Companion guard |
|---|---|---|---|---|
| `collation_guard.py` | `collate.collation_hash()` recomputed from `_ALPHA`/`_GREEK`, compared to the pin in `tools/tests/test_collate.py` | an alphabet edited without updating the pin in the same PR | **A shipped `index.json` whose `collation_hash` is wrong.** Proved: set the shipped value to `0000000000000000`; guard still printed OK. It checks the CODE, never the artefact a client reads. | **NONE - gap (G3).** Closed in Session 5 by `index_pin_guard.py`, which reads `data/dist/dict/index.json` from disk. |
| `nc_guard.py` | every `sources[]` and `attributions[]` in every shard under `data/dist` | an NC source id or NC licence reaching the dataset; a shard whose source is not on the allowlist | **The whole dataset being absent.** Proved: moved `data/dist/dict/` away; printed `OK - 0 entries checked, 0 violations`, exit 0. Also **any `.json.gz` shard**, because it globbed `*.json` - see G2. | **SHARED GAP** with `licence_guard` - it imports the same iterator, so it is blind in the same way and is not a companion. Closed in Session 5 by the shared reader failing closed on zero shards. |
| `licence_guard.py` | every source id used in the dataset has a `LICENSES.csv` row with a determined licence and a `scope` that reaches `data/dist`; no row reaching dist is undetermined | a source used but unlicensed; a licence recorded from memory (`UNKNOWN`); allowlist and manifest disagreeing | **The dataset being absent.** Proved: same run as above; printed OK. Uses the same shard iterator, so a `.json.gz` dataset yields zero used-ids and passes. | **SHARED GAP** with `nc_guard` - same iterator, same blindness, so not a companion. Closed by the shared reader failing closed. |
| `nc_guard_public.py` | every file under `public/**`, recursing into any container by magic bytes; gzip, zip, tar, `.tar.gz`, and nested combinations | an NC source id in anything published, including inside `.gz` (Session 4 S4-B1, Session 5 S5-B1) | **A missing `public/`.** It printed `OK - public/ does not exist yet` and exited 0. Also genuinely-binary formats (fonts, images, PDF) - counted and reported, never scanned; that is a stated limit, not an oversight. | **NONE - gap (G4)** for the missing-`public/` case: closed in Session 5, where an absent tree is a failure unless `--allow-missing` is passed. |
| `corpus_text_guard.py` | the shipped tarball: every verse has Coptic and English, every token has a form, lemma and POS; `meta.json` content hashes match the member bytes | **an empty corpus** (Session 4 S4-C1 - every other guard passed on a corpus with no text at all) | **A missing tarball.** It prints `SKIP - no baked corpus` and exits 0. | `tarball_guard_check` (the fingerprint responds) and `nc_guard_public` (the published copy matches). |
| `tarball_repro_check.py` | two independent `--force` builds produce the same SHA-256 | non-determinism: a timestamp, an unsorted member, dict ordering leaking in | **A reproducibly EMPTY tarball.** It compares two hashes and neither hash is required to contain anything. The clearest proxy in the project. | `corpus_text_guard` measures the contents directly - this is what makes repro alone safe. `tarball_guard_check` proves the hash tracks its sources. |
| `tarball_guard_check.py` | perturbing a `.tt` source's text moves the fingerprint, and an unchanged build skips | a fingerprint blind to content (Session 4 S4-C2, where a bug fix failed to ship while this reported success) | **A tarball whose sources are absent** - it prints `SKIP - no .tt sources present` and exits 0. Also it checks one specific slug, so a second work with a broken fingerprint would not be seen. | `tarball_repro_check` for determinism, `corpus_text_guard` for content. |
| `dialects_check.py` | the committed `data/dist/dialects.json`, compared against counts recomputed from the shards | counts drifting from the data; `no_dialect_recorded` forced to 0, which is the dishonesty Q4 exists to prevent | **Missing shards** - prints `SKIP - no baked shards`, exit 0. | `collation_guard` for the sort key the file is built with. (It also *regenerated* the file in Session 4, which made it unable to fail - Rule 1, fixed in Session 4 S4-C6.) |
| `merge/dry_run.py --real` | the merged dataset validates against `entry.schema.json`, is allowlisted and licensed; `--inject` proves each stage can fail | a schema regression in real data; a source that slipped past a gate | **The dataset being absent.** Proved: moved `data/dist/dict/` away; printed `PASS`. `load_real()` globbed `shard-*.json` and an empty list is a valid dataset. | **SHARED GAP** with `nc_guard` and `licence_guard` - `load_real()` has the same blindness, so none of the three is a companion to the others. Closed by the shared reader. |
| `fetch/fetch_all.py --check` | every pinned source file present locally matches the SHA-256 and byte count in `tools/sources.lock` | a source changing under a pin; a truncated download | **A pinned source DELETED.** Proved: moved `sources/kaikki/` away; it reclassified it as 'declared without a local copy' and still printed `all sources verified`, exit 0. A removal is silently a demotion. | **NONE - gap (G5)** for the demotion case. Closed in Session 5 by requiring a byte-verified local copy for any source the lock says must be present. |
| `pytest tools/tests/` | contracts, parsers, schemas, and the guards themselves, including the 12-check corpus round trip | contract regressions in code the other guards only exercise | **The shipped dataset, where the tests only assert on fixtures.** `test_merge_emit.py` read `index.json`'s `collation_hash` from a *tmp* emit, never from the shipped file. | **SHARED GAP** with `collation_guard` - the suite and the guard together still missed a corrupted shipped `index.json` (G3). Closed by `index_pin_guard.py`. |
| `emit/obsidian.py` (+ `test_obsidian.py`) | the vault payload respects the size limits and keeps text as text | a vault that would not fit Obsidian; text reflowed into a paragraph | **A vault that was never built** - the test asserts limits on a generated fixture, not on `public/downloads`. | **SHARED GAP** - `nc_guard_public` scans the built archive, but with `public/downloads/` absent it cannot tell 'not built' from 'built and empty'. |
| `reader_usage_guard.py` | every direct file-access call in `tools/**/*.py` and `static/js/*.js` naming a bare-form pipeline artefact without safeio/shardio/FetchJson mediation | a second way to open the same bytes (Session 17 emit crash on `.csv.gz` opened as text; S5-B2 plain JSON in `.json.gz` names) | **A path assigned on one line and opened several lines later** (verb and path must share a line). Proved in-session: `dict_index.py:135` read `index.json` through a variable and was found by survey, not by the guard; fixed the same way. Also explicit-form literals (`.json.gz` written out) and single-form inputs, by design. | `test_guards.py` Rule-12 negatives (planted direct open + raw fetch fail naming the file). |
| `drill_guard.py` | all 2,599 cloze items against the corpus tarball: correct == removed token, unique (lemma, pos) in verse, no normalized-equal distractor, verse resolves | an unfair or untraceable drill item; a bank whose tokens drifted from its verse | **A missing drill dir** - raises instead of passing (fail-closed, unlike the SKIP guards above). A verse whose tokens changed without rebuilding the bank: caught, because tokens are compared, not trusted. | `tools/tests/test_drill.py` (one negative per category on crafted tmp banks) + Playwright `test_drill.py` (plays one item, asserts score; no-JS fallback renders). |

## Gaps found

**12 guards. 3 cells say NONE — gap outright** (`collation_guard`,
`nc_guard_public`, `fetch_all`). A further **5 cells name a companion that shares
the very blindness being described** — `nc_guard` / `licence_guard` / `dry_run`
all consume the dataset through one iterator and therefore all share one hole,
and a "companion" that cannot see either is not a companion. Those are marked
SHARED GAP below, because counting them as covered would be the exact mistake
this table exists to prevent.

Grouped by cause, because there are five causes and each is a rule rather than a
list of bugs:

### G1 — "the artefact is absent" (4 guards)

`nc_guard`, `licence_guard`, `dry_run --real` all passed with `data/dist/dict/`
deleted. `corpus_text_guard` and `tarball_repro_check` and `dialects_check`
`SKIP` with exit 0. `nc_guard_public` prints OK when `public/` is missing.

A zero-entry dataset is a *valid* dataset to every one of these guards. This is
Rule 2 in its purest form: entry count and file count are proxies, and a proxy
measures zero just as happily as it measures ten thousand.

### G2 — "the file is compressed" (4 guards, and it is one filename away)

`nc_guard` globs `data/dist/**/*.json`. `dialects_check`, `dry_run --real`,
`corpus_refs`, `obsidian` glob `shard-*.json`. **None of them matches `.json.gz`.**

Session 5 D2 gzips the dictionary shards. On the day it did, with no other change,
all four would have found zero files and reported success — G1 arriving through a
filename. This is the single highest-risk finding in this file, and it is why D2
was done before D7 rather than after.

### G3 — "the guard measures the code, not the artefact" (1 guard)

`collation_guard` proves `collate.py` and its pin agree. It does not read
`data/dist/dict/index.json`, which is where the hash a client depends on actually
lives. A stale shipped index passes forever.

### G4 — "the container is unopened" (1 guard, now closed)

Session 4: `.json.gz` was handed to `tarfile`, so the guard could not open it —
and the gzipped corpus text was never scanned. The false positive *was* the false
negative. Session 5 C1 requires nested containers, which suffix-dispatch cannot
deliver; the scanner now identifies containers by magic and recurses, and a
container that announces itself and will not open is a failure.

### G5 — "removal is silently a demotion" (1 guard)

`fetch_all --check` treats a missing local copy as "metadata-only", not as a
failure. So deleting a source weakens the check instead of breaking it.

---

## Rules these gaps produced

Now project rules, in `CONTRIBUTING.md` and `HANDOFF.md` §8 (Session 5 C3):

**Rule 1 — A checker that generates the artefact it verifies is not a checker.**
Guards must read from disk, never write. (`dialects_check.py` regenerated the
file it compared and passed a `no_dialect_recorded: 0`.)

**Rule 2 — A guard that measures a proxy for the thing will pass when the thing is
absent.** Sizes, counts and stable fingerprints are proxies: they pass whether or
not the artefact is correct. At least one guard per artefact must measure the
thing itself. Every guard needs a companion that measures the artefact directly,
or a written note here saying why it does not need one.

Two consequences used throughout Session 5, both of them the direct application of
these rules rather than new policy:

- **Zero is a failure, not a skip.** A guard that needs a dataset and finds none
  fails, unless it is explicitly told an empty tree is acceptable. Silence and
  success look identical in CI, so the guard has to say which one it means.
- **Traversal lives in one place.** Rather than teaching five guards about gzip,
  a single reader resolves `.json` and `.json.gz` and *fails* if it finds no
  shards. Then a compressed shard cannot be missed, because no call site chooses
  how to read.

---

## Status after Session 5

| gap | closed by | how |
|---|---|---|
| **G1** absent dataset passes | `tools/shardio.py` | resolves `.json`/`.json.gz`, **fails closed** on zero shards. Six call sites moved onto it. Verified: with `data/dist/dict/` removed, `nc_guard`, `licence_guard` and `dry_run --real` now all exit 1 with a reason. |
| **G2** compressed file unseen | `tools/shardio.py` | one traversal, two suffixes, no call site chooses. Verified on the shipped `.gz`-only dataset: all 23 shards, 11,369 entries, seen by every guard. |
| **G3** code checked, artefact not | `tools/validate/index_pin_guard.py` | reads the shipped `index.json.gz` **and** `index.json` from disk; refuses if either disagrees with the alphabet on disk. |
| **G4** missing `public/` passes | `nc_guard_public.py` | an absent tree is a failure unless `--allow-missing` is passed explicitly. |
| **G5** removal is a demotion | `fetch_all.py` | counts pinned-but-absent sources; the headline carries the arithmetic (`1 of 2 pinned source(s) were present… 1 were NOT PRESENT and were not checked`) instead of an unqualified "all sources verified". |

### Still open, and why

- **`corpus_text_guard.py` and `tarball_repro_check.py` still `SKIP` with exit 0**
  when their artefact is absent. Deliberate, and it is the one place this file's own
  Rule 2 is not yet satisfied. Neither can fail closed without breaking a fresh
  clone before the first bake, and neither has a CI job that guarantees the artefact
  exists — so a job could go green having checked nothing. The fix is for CI to
  assert the artefact exists *before* running the guard, which is a workflow change
  rather than a guard change. **Open.**
- **`tarball_guard_check.py` checks one slug** (`sahidic_ruth`). With a second work
  carrying a broken fingerprint, this would not see it. It should iterate every work
  in the manifest. **Open.**
- **`emit/obsidian.py` limits are asserted on a fixture**, not on the built
  `public/downloads` archive. `nc_guard_public` scans the archive, but cannot tell
  "not built" from "built and empty". **Open.**
- **`fetch_all.py --check` still exits 0** when pinned sources are absent (deliberate
  — `sources/` is gitignored, so CI has none). `--strict` makes absence a failure.
  The honesty fix means the output can no longer be *read* as a pass, but it can
  still be *exited* as one. **Open.**

---

## Session 6 — status of every gap (C1)

**No gap is "open" without a named owner and a date.**

| gap | status | closed by / accepted-risk reason |
|---|---|---|
| **G1** absent dataset passes | **closed** | `tools/shardio.py` fails closed on zero shards. Verified: `data/dist/dict` removed → `nc_guard`, `licence_guard`, `dry_run` all exit 1. |
| **G2** compressed file unseen | **closed** | one traversal, both suffixes. Verified on the `.gz`-only dataset. |
| **G3** code checked, artefact not | **closed** | `index_pin_guard.py` reads the shipped `index.json.gz` and `index.json`. |
| **G4** missing `public/` passes | **closed** | absent tree is a failure; `--allow-empty` is the explicit opt-out. |
| **G5** removal is a demotion | **closed** | `fetch_all` counts pinned-but-absent and carries the arithmetic in its headline. `--check` now **exits non-zero**; `--allow-absent-sources` is for CI, which is gitignored, and it prints that nothing was verified. |
| corpus-text / tarball-repro **SKIP with exit 0** | **closed** | both now exit **non-zero** when the artefact is absent. `--allow-missing` exists for a fresh clone and says loudly that it is not a pass. |
| `tarball_guard_check` checks one slug | **closed** | iterates every work in the manifest and reports how many it verified. |
| `collation_guard` checks identity, not shape | **closed** | asserts **18 Coptic + 4 Greek = 22** letters separately from the hash, because a hash of a broken-but-consistent alphabet pins just as happily. |
| `nc_guard_public` can inspect 0 files | **closed** | `MIN_INSPECTED = 5` floor; 34 blobs + 33 members inspected in practice. |
| `obsidian` limits asserted on a fixture, not the built archive | **accepted-risk** | Owner: **Michael**, review by **Session 7**. `nc_guard_public` does scan `public/downloads/*.zip`, so an over-limit vault is still licence-checked; what is *not* asserted is Obsidian's file-count ceiling against the real archive. Low risk: the vault is 31 files against a 200 limit, and the build prints both numbers on every run. |
| `fetch_all --check` cannot detect upstream drift in CI | **accepted-risk** | Owner: **Michael**, review by **Session 7**. Unavoidable: `sources/` is gitignored, so CI has no bytes to hash. Mitigated by the job asserting the lock is well-formed and by `--allow-absent-sources` printing "0 sources verified" in yellow rather than a green pass. |


---

## Session 10 — D0–D4 status

| ID | Item | Status | Evidence |
|----|------|--------|----------|
| D0 | `public/` completeness guard | **DONE** | 90 artefacts, 23 shards, 15 HTML pages. Negatives: deleted shard → names it; zero-byte shard → caught; zero-byte HTML under `--strict` → caught |
| D0 | Wired into CI | **DONE** | `public-completeness` job runs build + completeness `--strict` + provenance `--strict` |
| D1 | Service worker actually registers | **DONE** | `footer.html` calls `navigator.serviceWorker.register()`. It was never called before |
| D1 | Reader markup exists on `/dict/` | **DONE** | `layouts/dict/list.html`; Goldmark was stripping the raw HTML |
| D1 | Playwright green | **DONE** | 12 passed, 1 xfailed (the open English-search defect) |
| D1 | Precached URL negative control | **DONE** | `test_4_every_precached_url_really_exists` |
| D2a | `ud_bohairic` removal verified + dated | **DONE** | measured `False`; dated note in `tools/sources.lock`; lock still parses |
| D2b | Format-char strip list unified | **DONE** | `strip_chars` in `index.json`; 35/35 marked lemmas reachable, was 26/35 |
| D2c | `import.meta.url` lint | **DONE** | `tools/validate/esm_path_guard.py`; bare-use probe caught |
| D2 | Pagefind search tests | **PARTIAL** | Coptic + prefix pass; `copper` **xfail(strict)** — see DECISIONS.md |
| D3 | `/corpus/<work>/` routes | **DONE** | 7 routes (6 works + index), 85 Ruth verses, 3,470 tokens |
| D3 | Token → dictionary → corpus loop | **DONE** | `test_7` asserts both directions against real routes |
| D3 | No-JS fallback | **DONE** | `<noscript>` names the two `.json.gz` files |
| D4 | `fetch_work --check` | **DONE** | 9 works match pins; byte-flip and deletion caught |
| D4 | CI job | **DONE** | `fetch-work-pins`, no network |
| — | `esm-path-guard` CI job | **DONE** | 26 jobs total (was 22) |

### Not covered

- **Lighthouse**: not run. Chromium is installed via Playwright, which is enough
  for the functional tests above but is not a substitute for a Lighthouse receipt.
- **Pagefind on a real CDN**: verified against a local static server that does
  *not* set `Content-Encoding: gzip` (the harder case). Not verified against
  Cloudflare Pages.
- **Pagefind binary**: still only at `/tmp/pagefind`. The CI `playwright` job does
  not run Pagefind, so it does not need it; the `public-completeness` job does not
  either. **`tools/build.py` needs `PAGEFIND_BIN` to produce a search index and
  nothing enforces that** — a build without it silently ships no `pagefind/`.
- **The four `VERIFY: reconstructed 2026-10-06` markers** remain unresolved in
  `tools/sources.lock`, by instruction.


---

## Session 11 — coverage

| ID | Item | Status | Evidence |
|----|------|--------|----------|
| D0 | Rule 7 in HANDOFF §8a and CONTRIBUTING | **DONE** | verbatim from C1 |
| D0 | `tools/tests/test_behaviors.py`, 6 tests | **DONE** | 6 passed; all 6 fail when their bug is reintroduced |
| D0 | **Found and fixed:** `reader.js` assumed no `Content-Encoding` | **DONE** | see below |
| D1 | Pagefind English bug | **OPEN, investigated** | 6 queries ruled out; mechanism not identified; xfail kept |
| D2 | Playwright for all six works | **DONE** | 4 passed, 15 xfailed (see the known defect) |
| D2 | **Found:** verse refs not unique within a work | **OPEN** | 5 of 6 works show wrong tokens |
| D2 | Negative: tamper a work's JSON | **DONE** | Ruth render test fails |
| D2 | Negative: tamper a precache URL | **DONE** | SW test 4 fails; completeness guard catches it too |
| D3 | Pagefind pinned | **DONE** | `pagefind@1.5.2`, exact, installs clean; build no longer needs `/tmp` |
| D4 | Lighthouse | **DONE** | `/dict/` 91/93/96/100; corpus 75/92/96/100 |
| D5 | Deploy prep | **DONE** | `DEPLOY.md`, `POST_DEPLOY_CHECKLIST.md`, build command, time budget |
| D6 | Docs | **DONE** | this file, DECISIONS.md, PLAN-ERRATA.md, README.md |

### D0 negative demonstrations

| Test | Reverted | Result |
|---|---|---|
| `behavior_1_service_worker_is_registered` | removed the `register()` call | **failed** |
| `behavior_2_reader_renders_an_entry` | deleted `#q`/`#results`/`#entry` | **failed** |
| `behavior_3_no_page_relative_data_urls` | root-relative → page-relative | **failed** |
| `behavior_4_deep_link_opens_the_entry` | `?q=` no longer read | **failed** |
| `behavior_5_corpus_reads_gzipped_json` | always inflate | **failed** |
| `behavior_6_token_click_keeps_lemma` | `data-ref` → `h3` textContent | **failed** |

`behavior_4` was **weak on the first attempt** and is worth recording: it
accepted `"URLSearchParams" in reader`, so changing the code to
`new URLSearchParams("")` — the bug, exactly — left the test passing. It now
requires `location.search` *and* `URLSearchParams(location.search`, and both
revert variants were re-run to confirm.

### The bug D0 found

`reader.js` piped every response through `DecompressionStream("gzip")`
unconditionally. That is correct only when the host does **not** send
`Content-Encoding: gzip`. Cloudflare Pages and `nginx gzip_static` both do — the
browser inflates once and `reader.js` inflated again and threw. The reader
worked in every local test and would have failed on the real deploy target.
`corpus.js` already sniffed correctly; the reader did not, and no test caught
the difference because every test server so far has served `.gz` undecoded.

### Not covered

- **Verse-ref uniqueness fix.** The join must move to position (`verse_index`),
  not `ref`. Diagnosed, not fixed — see DECISIONS.md.
- **CSP vs the inline SW registration.** The inline block in `footer.html` will
  violate the CSP in DEPLOY.md §5. Flagged there, deliberately not "fixed" by
  weakening the policy.
- **`public/_headers` is not yet emitted by `tools/build.py`.** It must be,
  because `public/` is wiped on every build. Documented, not implemented.
- Lighthouse was run against a local static server, not against Cloudflare's CDN.


---

## Session 12 — coverage

| ID | Item | Status | Evidence |
|----|------|--------|----------|
| D0 | Rule 8 in HANDOFF §8a + CONTRIBUTING | **DONE** | verbatim from C1 |
| D0 | `static/js/fetch_json.js` | **DONE** | one implementation, three call sites |
| D0 | **Found:** `read-csv.html` still had the pre-Session-11 bug | **FIXED** | third copy of a drifted concept |
| D0 | Both `Content-Encoding` branches mocked | **DONE** | 13 tests, `test_fetch_json.py` |
| D1 | `verse_index` emitted per work | **DONE** | 0..N-1, unique, one enumeration |
| D1 | `corpus.js` keys on `verse_index` | **DONE** | anchors `v<idx>`, `byRef` gone |
| D1 | 15 xfails → XPASS | **DONE** | **all 15 now pass; `BROKEN` is `set()`** |
| D1 | Manual check: bohairic_mark verse 5 | **DONE** | 20,322 spans (was 276,522); `#v5` has its own 33; correct lemma opens |
| D2 | `_headers` emitted from `build.py` | **DONE** | `tools/emit/headers.py`, claimed in the manifest |
| D2 | SW registration externalised | **DONE** | `js/sw-register.js`; CSP keeps no `unsafe-inline` |
| D2 | **Found:** CSP blocked Pagefind's WASM | **FIXED** | `'wasm-unsafe-eval'` added |
| D2 | Playwright runs under the real CSP | **DONE** | conftest serves the emitted `_headers` |
| D2 | Build idempotence | **DONE** | 3 builds, identical content hash |
| D2 | **Found:** build not reproducible | **FIXED** | generator mtime fed its own stamp |
| D3 | Minimal harness with working controls | **DONE** | `<p>azurite copper</p>` → 1 and 1 |
| D3 | Minimal reproduction of the bug | **DONE** | 1 record: azurite 9, copper 0, carbonate 0 |
| D3 | Mechanism | **OPEN** | hypothesis + exact next test in DECISIONS.md |
| D3 | azurite 9 → 8 | **UNEXPLAINED** | points at the writer, not the query |
| D4 | npm cold-build mitigation | **DONE** | npm cache; vendoring tried and reverted |
| D4 | **Found:** `pagefind` pin was `^1.5.2` | **FIXED** | `pagefind_pin_guard.py` |
| D5 | All suites | **DONE** | 327 passed, 14 skipped, 1 xfailed |
| D6 | Docs | **DONE** | DECISIONS, PLAN-ERRATA, COVERAGE, README, DEPLOY |

### Not covered

- **The Pagefind mechanism.** Diagnosed to a one-record reproduction, no cause.
- **`public/_headers` on Cloudflare.** Correct per the Pages spec and locally
  exercised; never served by Cloudflare itself.
- **Lighthouse under the CSP.** Session 11's scores predate it; re-running needs a
  served CSP, which the local harness now does, but was out of scope here.
- **`corpus.js` does not validate that `verse_index` exists** before using it —
  it throws with a clear message, which is tested, but a work emitted by an older
  tarball would fail at runtime rather than at build time.


---

## Session 13 — coverage

| ID | Item | Status | Evidence |
|----|------|--------|----------|
| D0 | Rule 9 in HANDOFF §8a + CONTRIBUTING | **DONE** | verbatim from C1 |
| D0 | `tok.norm` markup stripped at emit | **DONE** | **9,132 → 0** of 83,017 (11.0% → 0%) |
| D0 | `corpus_shape_guard` fails the build | **DONE** | verse_index stripped → 6 errors, build refused |
| D0 | `test_truncated_inside_norm_raises` skipped, not failed | **FIXED** | used the corpus without `needs_corpus` |
| D1 | Pagefind confirming experiment | **DONE** | trigger **isolated** to the term |
| D1 | Mechanism | **OPEN** | 6 hypotheses refuted; next test specified |
| D2 | azurite 9 → 8 | **EXPLAINED** | reproduced in a one-record index |
| D3 | Deploy | **DONE** | `session-13.coptic-reference.pages.dev`, 116 files |
| D3 | Telemetry blocked the deploy | **WORKED AROUND** | `WRANGLER_SEND_METRICS=false` |
| D3 | `pages project create` via Node fetch | **WORKED AROUND** | curl succeeds where Node's fetch fails |
| D3 | Post-deploy checklist on the real origin | **10/10 PASS** | 2 documented expected failures |
| D4 | Lighthouse under the CSP | **DONE** | `/dict/` 90/93/96/100; corpus 78/92/96/100 |
| D5 | Corpus heading order + touch targets | **DONE** | a11y **92 → 100** |
| D6 | Docs | **DONE** | DECISIONS, COVERAGE, POST_DEPLOY_CHECKLIST |

### Not covered

- **The Pagefind mechanism.** Isolated, not explained. The next experiment is in
  DECISIONS.md and needs Pagefind's internal index representation.
- **A production deployment.** This is a *preview* on branch `session-13`.
  Production needs `master` and Michael's go-ahead.
- **`/dict/`'s `<ul>`-containment failure** (Lighthouse, a11y 93). Reported, not
  tuned; the corpus page's two failures *were* fixed.
- **Vendoring.** Withdrawn in Session 12 and left withdrawn, per C6.


---

## Session 14 — coverage

| ID | Item | Status | Evidence |
|----|------|--------|----------|
| D0 | Rule 10 in HANDOFF §8a + CONTRIBUTING | **DONE** | verbatim from C1 |
| D0 | `/dict/` a11y 93 → 100 | **DONE** | `<ul id=results>` → `<div>`; Lighthouse 100 |
| D0 | Corpus a11y (Session 13) | **DONE** | stayed at 100 |
| D0 | SW precache declared vs served | **DONE** | 8 = 8, no discrepancy |
| D1 | Upstream report filed | **DONE** | PageFind/PageFind#1370 |
| D2 | `english_index.py` | **DONE** | 10,017 terms, 148,546 B gz |
| D2 | `search.js` merge layer | **DONE** | 6 Playwright tests, all pass |
| D2 | `copper` → entries, links work | **DONE** | 19 hits locally and on the CDN |
| D2 | `ⲧⲉⲛⲟⲩ` → entry, links work | **DONE** | 1 hit, entry renders |
| D3 | Deploy the workaround | **DONE** | `session-14.coptic-reference.pages.dev` |
| D3 | Post-deploy checklist | **10/10 PASS** | plus English search 19 hits |
| D4 | Commit plan + production commands | **DONE** | 11 commits, `PRE_PRODUCTION_CHECKLIST.md` |
| D4 | Actual commit / promotion | **NOT DONE** | by instruction; `master` unborn |
| D5 | `_headers` exposure | **ACCEPTED** | logged in DECISIONS.md |
| D5 | Checklist precache item | **DONE** | declared-vs-served, calibrated |
| D6 | Docs | **DONE** | this file, DECISIONS, README, both checklists |

### Not covered

- **A commit.** Nothing is committed; `master` remains unborn.
- **A production deployment.** Preview only, by instruction.
- **The Pagefind fix.** Reported upstream (#1370); the workaround stands until it
  lands. Nothing in this repository can fix it.
- **`sources/**/*.tt`** is fetched, not vendored, so a clean clone needs
  `fetch_work.py` before `tools/build.py` will produce a corpus.


---

## Session 15 — coverage

| ID | Item | Status | Evidence |
|----|------|--------|----------|
| D0 | CONTRIBUTING missing-input rule | **DONE** | verbatim |
| D0 | HANDOFF fetch-first step | **DONE** | §5 step 1 |
| D0 | Size budgets enforced | **DONE** | 300 KB / 500 KB, fail-closed |
| D0 | Budget negative | **DONE** | 358 KB index → guard FAIL; restored PASS |
| D0 | #1370 review date | **DONE** | 2027-04-01 in DECISIONS.md |
| D1 | 11 (+1) commits | **DONE** | 12 hashes, clean tree |
| D1 | `.gitignore` scope | **DONE** | `data/`, `database.db*`, scratch added |
| D2 | Push | **BLOCKED** | no remote; commands prepared |
| D3 | Production deploy | **DONE** | `coptic-reference.pages.dev` |
| D3 | Production checklist | **10/10 PASS** | on the production origin |
| D4 | curl production | **DONE** | 4 routes, 200s |
| D4 | Lighthouse production | **DONE** | 85/100/100/100 and 97/100/100/100 |
| D4 | Manual browser walkthrough | **DONE** | scripted Chromium (see note) |
| D5 | SHIP.md | **DONE** | production URL, state, contacts |
| D6 | Final docs | **DONE** | this file, DECISIONS, README, HANDOFF |

### Not covered

- **A git remote and a production build from git.** There is no remote, so
  Cloudflare cannot pull and build. Production is a direct upload.
- **A human-driven GUI walkthrough.** The "manual" test was Chromium driven by
  Playwright, not a hand on a mouse. It loads the real site, searches real
  words and clicks real links, but it is scripted — reported as such rather
  than claimed otherwise.
- **The four VERIFY markers.** Unresolved, as instructed since Session 10.
- **Pagefind#1370.** Open; review 2027-04-01.


---

## Session 16 — coverage

| ID | Item | Status | Evidence |
|----|------|--------|----------|
| D0 | Rule 11 in HANDOFF §8a + CONTRIBUTING | **DONE** | verbatim from C7 |
| D0 | `static/js/translit.js` | **DONE** | sole `translitDisplay()` renderer |
| D0 | `no_object_object_guard.py` | **DONE** | 94 artefacts, 56 compressed payloads; negative injects and names one file |
| D0 | `translit_shape_guard.py` | **DONE** | 11,369 entries; string/unexpected-scheme negatives fail |
| D0 | `test_translit_renders_string` | **DONE** | `/dict/`, `/corpus/`, and `/quiz/` render strings, not objects |
| D1 | `tools/emit/quizgen.py` | **DONE** | 959 items in 19 banks, deterministic IDs and gzip |
| D1 | Correct-answer traceability | **DONE** | `quiz_guard.py` checks all 959 answers |
| D1 | Transliteration prompts | **DONE** | generated through shipped `translitDisplay()`; romanization provenance recorded |
| D2 | `static/js/quiz.js` | **DONE** | 10-item sessions, score, localStorage, spaced repetition |
| D2 | Quiz Playwright tests | **DONE** | completion, persistence, transliteration, export |
| D3 | `/quiz/` route | **DONE** | works, no-JS fallback renders, Lighthouse 100/100/96/100 |
| D4 | `quiz_guard.py` | **DONE** | clean; wrong-answer and duplicate-choice negatives fail |
| D5 | Docs | **DONE** | this file, DECISIONS.md, PLAN-ERRATA.md, README.md, HANDOFF.md, SHIP.md |

### Not covered

- **Shipped `translit` schemes.** All 11,369 entries currently have empty
  transliteration objects. The quiz therefore uses source-backed
  `forms.romanization` values, explicitly labeled, rather than asserting absent
  scheme data.
- **A production deployment of `/quiz/`.** Verified locally and in Chromium; the
  production promotion decision remains Michael's.


---

## Session 16 — coverage

| ID | Item | Status | Evidence |
|----|------|--------|----------|
| D0 | Rule 11 in HANDOFF §8a + CONTRIBUTING | **DONE** | verbatim from C7 |
| D0 | `static/js/translit.js` | **DONE** | sole `translitDisplay()` renderer |
| D0 | `no_object_object_guard.py` | **DONE** | 94 artefacts, 56 compressed payloads; negative injects and names one file |
| D0 | `translit_shape_guard.py` | **DONE** | 11,369 entries; string/unexpected-scheme negatives fail |
| D0 | `test_translit_renders_string` | **DONE** | `/dict/`, `/corpus/`, and `/quiz/` render strings, not objects |
| D1 | `tools/emit/quizgen.py` | **DONE** | 959 items in 19 banks, deterministic IDs and gzip |
| D1 | Correct-answer traceability | **DONE** | `quiz_guard.py` checks all 959 answers |
| D1 | Transliteration prompts | **DONE** | generated through shipped `translitDisplay()`; romanization provenance recorded |
| D2 | `static/js/quiz.js` | **DONE** | 10-item sessions, score, localStorage, spaced repetition |
| D2 | Quiz Playwright tests | **DONE** | completion, persistence, transliteration, export |
| D3 | `/quiz/` route | **DONE** | works, no-JS fallback renders, Lighthouse 100/100/96/100 |
| D4 | `quiz_guard.py` | **DONE** | clean; wrong-answer and duplicate-choice negatives fail |
| D5 | Docs | **DONE** | this file, DECISIONS.md, PLAN-ERRATA.md, README.md, HANDOFF.md, SHIP.md |

### Not covered

- **Shipped `translit` schemes.** All 11,369 entries currently have empty
  transliteration objects. The quiz therefore uses source-backed
  `forms.romanization` values, explicitly labeled, rather than asserting absent
  scheme data.
- **A production deployment of `/quiz/`.** Verified locally and in Chromium; the
  production promotion decision remains Michael's.

---

## Session 18 — coverage

| ID | Item | Status | Evidence |
|----|------|--------|----------|
| D0 | Rule 12 in HANDOFF §8a + CONTRIBUTING | **DONE** | verbatim from C1; evidence Session 17 emit crash + S5-B2 |
| D0 | `reader_usage_guard.py` | **DONE** | clean; 3 flags triaged+fixed (cli.py x2, dry_run), dict_index by survey; 4 control tests |
| D1 | translit.js orphan | **DONE** | reverted; 240-combination behavioral identity proven first |
| D2 | empty-by-rule fixture | **DONE** | 8 lemmas versioned; both-direction test passes |
| D3 | quiz regen confirmation | **DONE** | identical sha, 50/50/50, quiz_guard clean |
| D4 | `drillgen.py` | **DONE** | 2,599 items in 6 banks, skips counted per reason |
| D4 | `drill_guard.py` | **DONE** | clean; 4 negatives (one per category) fail |
| D4 | `/drill/` + drill.js + no-JS fallback | **DONE** | Playwright: one item completes and scores; fallback lists works |
| D5 | all guards + pytest + Playwright | **DONE** | every guard OK; 336 + 48 passed |
| D7 | Docs | **DONE** | this file, DECISIONS.md, PLAN-ERRATA.md, README.md, HANDOFF.md, SHIP.md |

---

## Session 19 — coverage

| ID | Item | Status | Evidence |
|----|------|--------|----------|
| D0 | Rule 13 in HANDOFF §8a + CONTRIBUTING | **DONE** | verbatim from C1 |
| D0 | AST `reader_usage_guard.py` | **DONE** | clean; E31 split-line test fails on old regex, passes on AST; 2 over-reach fixes |
| D1 | drill lexical-blank decision | **DONE** | Ruth sample inspected; (b) chosen on measured 24k/35k + fairness; 2,589 re-emitted |
| D2 | unsigned-commit standing state | **DONE** | SHIP.md Signing row + HANDOFF.md paragraph (Option B; no key in env) |
| D3 | course plan | **DONE** | 15 lessons, all vocab corpus-attested with entries (28 memory-words replaced) |
| D4 | `coursegen.py` + `course_guard.py` | **DONE** | 15 lessons chain; every filter resolves (bounds, inventory, banks) |
| D4 | `/course/` + course.js + no-JS list | **DONE** | Playwright: lesson 1 passes → 2 unlocks; 2 starts locked; fallback lists 15 |
| D4 | Lighthouse /course/ | **DONE** | 100 a11y / 100 SEO / 96 bp (favicon, pre-existing) / 86 perf |
| D5 | lessons 01–05 + 10 placeholders | **DONE** | prose glosses checked vs dictionary; placeholders carry full filters + TODO |
| D5 | `size_guard` back under budget | **DONE** | was 122% (stale plain CSVs); gzip_csvs per C4 design, now green |
| D7 | Docs | **DONE** | this file, DECISIONS.md, PLAN-ERRATA.md (E32), README.md, HANDOFF.md, SHIP.md |

---

## Session 20 — coverage

| ID | Item | Status | Evidence |
|----|------|--------|----------|
| D0 | `lesson_vocab_guard.py` | **DONE** | clean on 15 lessons; 3 negatives + positive + exemption + real-tree tests |
| D0 | D1 plain-language statement | **DONE** | drillgen.py header + DECISIONS.md paragraph |
| D1 | lessons 06–15 | **DONE** | 200–251 words each; guard run after every lesson; glosses checked vs entries |
| D2 | `public_size_guard.py` | **DONE** | clean (6.7/20 MB); inflate-a-dir negative fails naming it |
| D3 | signing paragraph + pointer | **DONE** | HANDOFF.md §8a paragraph, SHIP.md pointer (Option B) |
| D4 | `parsedrillgen.py` | **DONE** | 2,599 pos + 2,599 lemma, skips counted, rotation over first-token bias |
| D4 | `parsedrill_guard.py` | **DONE** | clean; 2 negatives (wrong answer, normalized-equal distractor) |
| D4 | drill.js three types + /drill/ | **DONE** | Playwright: POS + lemma complete; default cloze unchanged |
| D5 | all guards + pytest + Playwright | **DONE** | every guard OK; 353 + 54 passed |
| D7 | Docs | **DONE** | this file, DECISIONS.md, PLAN-ERRATA.md (E33), README.md, SHIP.md |

---

## Session 21 — coverage

| ID | Item | Status | Evidence |
|----|------|--------|----------|
| D0 | Rule 14 in HANDOFF §8a + CONTRIBUTING | **DONE** | verbatim from C1; evidence ⲭⲱ/ϭⲟⲓⲗⲉ |
| D0 | content audit | **DONE** | 156 pairs verified, 4 declared, 1 plan line fixed, rest zero-Coptic |
| D1 | GRAMMAR_CLAIMS.md + markers + banner | **DONE** | 21 claims + 2 method notes; banner renders (Playwright asserts) |
| D2 | pos_labels data + renderer + guard | **DONE** | 57/57 tags; behavior test renders labels; AAOR fail-closed catch |
| D3 | trivial-identity skip + guard rule | **DONE** | 5,198 → 5,174; negative control fails naming it |
| D4 | writing practice | **DONE** | 35 SVGs + index; canvas verdicts; Playwright draws; LH 99/100/96/100 |
| D5 | all guards + pytest + Playwright | **DONE** | every guard OK; 360 + 57 passed |
| D7 | Docs | **DONE** | this file, DECISIONS.md, PLAN-ERRATA.md (E34), README.md, SHIP.md |

---

## Session 22 — coverage

| ID | Item | Status | Evidence |
|----|------|--------|----------|
| D0 | AST `no_object_object_guard.py` + `js_object_scan.mjs` | **DONE** | 141 artefacts, 19 via AST, 71 payloads; comment/comparison/bare-literal/parse-error negatives (17 tests); E34 case now passes on its merits; THIRD_PARTY_EXCEPTIONS deleted |
| D0 | acorn 8.19.0 pinned | **DONE** | exact, no caret; `esm_path_guard` clean after dropping createRequire for a direct ESM import |
| D1 | `speakgen.py` + `/speak/` + `speak.js` | **DONE** | 100 lemmas ranked by corpus occurrences; record→play under mocked MediaRecorder; zero foreign requests; Lighthouse /speak/ 100/100/100/100 |
| D1 | no-JS page | **DONE** | `/speak/top100.html` static table (100 rows, no script), generated by speakgen, copied by build.py — never `site.Data` (E35) |
| D2 | `ankigen.py` + `/anki/` | **DONE** | vocab 300 cards (6 banks) + drill 2,589 cloze cards (6 banks); collections opened via zipfile+sqlite3: deck names, note counts, unique guids, attribution field |
| D2 | download routes | **DONE** | Playwright: both `/downloads/anki/*.apkg` return 200, PK magic, `collection.anki2` present |
| D3 | `favicon.py` + Lighthouse | **DONE** | 16+32 ICO drawn from geometry; /dict/ best-practices 96 → 100 (before/after JSON kept in /tmp) |
| D4 | `content/POS_LABELS_REVIEW.md` | **DONE** | 8 rows (VBD/PPERI/IMOD/FM/APREC/AOPT/AAOR/AFUTCONJ) with corpus counts and confirming sources; verdict columns blank for a human |
| D5 | all guards + pytest + Playwright | **DONE** | every validator OK; 450 + 22 skipped + 1 xfailed |
| D6 | two commits + push | **DONE** | `3e3748e..b70f338`, 0 ahead, clean tree |
| D7 | Docs | **DONE** | this file, DECISIONS.md, PLAN-ERRATA.md (E35), README.md, HANDOFF.md, SHIP.md |

### Not covered

- **A production deployment of `/speak/` and `/anki/`.** Verified locally and
  in Chromium; the promotion decision remains Michael's.
- **IPA pronunciation data.** No dictionary entry carries an IPA field, and
  `speakgen` emits no `ipa` key rather than a blank one (see DECISIONS.md D1).
- **Anki import on a real device.** The `.apkg` files are verified as Anki
  collections (zip + sqlite, deck ids, note counts), not opened in Anki itself.

## Session 23 — coverage

| ID | Item | Status | Evidence |
|----|------|--------|----------|
| D0 | production staleness audit + direct-upload promotion | **DONE** | all post-15 routes 404 behind the 200 homepage fallback; promoted `66a9a37a`, checklist pass (manifest local==remote, SW 8/8, offline dict, headers, gzip, no console errors) |
| D1 | `quiz.apkg` = all 959 quiz items | **DONE** | 19 banks, 676,058 B (was 300 cards / 200,922 B as `vocab.apkg`); deck/model/guid ids kept for in-place upgrade; invariant `test_quiz_deck_carries_every_bank_item`; deployed `797c0916`, prod bytes exact |
| D1 | canonical `SITE_BASE` in decks | **DONE** | drill.apkg 2,134 `coptic.re` dict links, 0 `pages.dev`; 3,514,586 B, 2,589 notes |
| D2 | Rules 15 + 16 verbatim | **DONE** | HANDOFF §8a (same shape as 1–14) + CONTRIBUTING `## Rule 15/16`; whitespace-normalized text-identical check |
| D3 | `content/EXPERT_REVIEW_PACKET.md` + drift guard | **DONE** | mirror of 23 grammar + 8 POS rows, verdict cells blank, verdict vocabulary + workflow; `test_review_packet.py` (3 tests) fails on any drift or filled mirror cell |
| D4 | site-wide consistency walk | **DONE** | 40 sitemap routes / 99 internal paths; 4 fixes (3 empty titles, `Ncs`→`NC material`, `list.html` `.Site.RegularPages`→`.Pages`); re-walk 0 problems, 0 broken links |
| D5 | full CI guard battery | **DONE** | all 29 workflow commands + build-internal guards + `lesson_vocab_guard`/`reader_usage_guard` standalone + 21-value POS heredoc; **454 passed, 22 skipped, 1 xfailed** |
| D6 | four commits + push | **DONE** | `1d2f47b` (deck), `5d76fdf` (rules+packet), `02f751b` (walk fixes), docs commit; pushed, 0 ahead, clean tree |
| D7 | production re-verify + docs | **DONE** | deployment `08459596`: 25 routes 200, 40 titles, packet page 31 blank verdicts, decks byte-exact, precache 8=8, offline dict, zero console errors; this file, DECISIONS.md (Session 23), PLAN-ERRATA.md (E36), README.md, HANDOFF.md §5 + clone URL, SHIP.md |

### Not covered

- **Why the git-connected Pages build emits empty deployments.** The
  failure is dashboard-side; the CLI cannot read the build config.
  Direct upload is the working path (SHIP.md, HANDOFF §5); repairing or
  disconnecting the git build is a Cloudflare dashboard task for Michael.
- **Lighthouse this session.** No JS/CSS/CSP change — content, templates
  and decks only; Session 22's numbers stand.
- **Anki import on a real device** (carried from Session 22). Decks are
  verified as Anki collections (zip + sqlite, note counts, guid
  uniqueness), not opened in the Anki app.
