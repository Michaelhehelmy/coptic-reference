# PLAN-ERRATA.md

**Read this before copying any code sample out of `STATIC-COPTIC-REFERENCE-PLAN-v4.md`
or `-v5.md` verbatim.**

The plans are closed and authoritative as *design*. Their embedded code samples
are not: **nine** defects have been found by running them. Five fail loudly; four
produce plausible wrong output, which is worse. All nine are fixed in this
repository. Full detail, including the failing commands, is in `DECISIONS.md`
(B-1 … B-8, B-10) — this file is the index.

**Does an erratum affect the design?** Only B-5 touches a stated fact. Nothing
here changes an architecture, an invariant, or a decision. In every case the
working code is a *repair* of the sample, not a replacement of the design.

| # | One-line | Sample or design? | Working code |
|---|----------|-------------------|--------------|
| B-1 | `test_collate.py` imports `canon_for_sort`; the module defines `_folded` | sample | `tools/collate.py:canon_for_sort` |
| B-2 | Total-order fixture has 32 items but 30 distinct, so `len(set)==len` is unsatisfiable | sample | `tools/tests/test_collate.py` |
| B-3 | `_TT` parser cannot run: one `SyntaxError` + three silent-wrong-output faults | sample | `tools/parse/tt.py` |
| B-4 | `_TT` is called XML; it is malformed SGML. `@norm` is derived, `@orig` is authoritative | **design wording** | `tools/parse/tt.py` |
| B-5 | `Ruth_01` stated as 85 verses; the file has 22 (85 is the whole book) | **stated fact** | — (parser was right) |
| B-6 | `format: date` enforces nothing without a `FormatChecker`; `decide_by` accepted `"next year"` | sample | `schema/suggestion.schema.json` |
| B-7 | My own first drafts: unpinned-source failure, two stray `"""`, order-dependent harness | my code | fixed |
| B-8 | The reason codepoint order fails is Greek-script codepoints for Sahidic letters, not anything exotic | design wording | `tools/collate.py` |
| B-10 | The name scan covers only U+2C80–U+2CFF, so the seven Greek-script Sahidic capitals never case-fold | sample | `tools/collate.py` |

## The five that fail loudly

**B-1.** `from collate import (..., canon_for_sort, ...)` — `ImportError`; the
name is never used. Session 1 Q5 resolved it by adding the public alias, so the
plan's sample now runs verbatim.

**B-2.** The total-order fixture is `alphabet_chars() + [... "ⲁ", ..., "ⲛ" ...]`
— `ⲁ` and `ⲛ` appear in both halves, so 32 items yield 30 distinct strings and
`len(set(keys)) == len(keys)` can never hold. De-duplicated; **assertion
unchanged**.

**B-10.** The capital/small name scan is bounded to the Coptic block
(U+2C80–U+2CFF), but the seven Sahidic letters descend from Greek capitals and sit
in the **Greek and Coptic block** at U+03E2–U+03EE. So `canon_for_sort("Ϣⲁⲓ")`
returned `"Ϣⲁⲓ"` unchanged while `canon_for_sort("ϣⲁⲓ")` returned `"ϣⲁⲓ"` — two
cases of one letter were not the same string, and `rank_key`, the documented
*equivalence* key, answered "no" for **seven** of the alphabet's letters.
Extending the *name* scan to the Greek block is the right fix (parity is what
v4 §1.3 rejects); `_ALPHA`, `_GREEK` and the order are untouched, so
`collation_hash()` is still `b7b49af6e144ef87` — the pin is the proof. Found by
`tools/emit/obsidian.py`, which filed `Ϣⲁⲓ` under no letter at all.

**B-3.** Four faults in one sample. The `SyntaxError` (an unbalanced paren in
`_ORIG_OPEN_RE`) is trivial; the other three produce *plausible wrong output*,
which is why this file exists. `_TAG_RE` had no capture for the leading `/`, so
`</translation>` matched as an *opening* tag and every verse got an empty
translation. `raw.startswith("</verse_vid", pos)` never fired — the tag sits at
column 0 *after* a newline `pos` had passed, so verses never terminated. The
`PRE_VERSE` jump scanned to the next `<verse_vid>`, jumping *over* the
`<translation>` and `<vid_n>` before it, losing alignments and URNs. Empty
translations look like a *corpus* problem, so the parser now raises on
`@norm`/`@orig` drift instead of trusting the file.

Empty translations and absent URNs look like a *corpus* problem. A parser that
fails silently on malformed SGML is the worst kind, so the parser now raises
`TTParseError` on `@norm`/`@orig` drift instead of trusting the file.

**B-6.** `decide_by` used `{"type": ["string","null"], "format": "date"}`. In
JSON Schema 2020-12 `format` is **annotation-only** without a `FormatChecker`, so
`{"decide_by": "next year"}` validated clean — on a field v5 §14.2 makes
load-bearing. Two layers now, **keep both**: a `pattern` (catches shape on any
validator) and `jsonschema[format]` (catches meaning). Layer 1 alone cannot
reject `2027-13-45`, which has the correct shape.

## The two that touch design wording

**B-4.** v4 calls `_TT` XML; it is TreeTagger-style SGML (unclosed `<word>`, no
namespace). `xml.etree` raises `mismatched tag` on the first file. The
consequence is inverted attribution: **`@orig` is authoritative and `@norm` is
cross-checked**. Reaching for `lxml` first is the predictable mistake.

**B-5.** v4 §4.5 expects 85 verses from `Ruth_01`; the file has **22**. Parsing
all four Ruth files gives `22+23+18+22 = 85` — the whole book's figure, attached
to chapter 1. The parser was left alone (Session 1 Q1). **If 85 was load-bearing
for a layout decision, that decision needs revisiting.**

## The lesson behind B-10 — read this before writing a fixture

**Ten of v4 §1.5's fifteen collation fixtures contained no Greek-block letter
at all** — and those are exactly the seven B-10 broke. So the plan's own suite
could not have caught B-10, and would have kept passing with a collation that
treated Ϣ and ϣ as different letters. Coverage is not only *which assertions
run*; it is *which inputs they run on*. A fixture that omits a block of the
alphabet is an untested claim about that block, and it reads like a tested one.

Session 3 (C2) added Greek-block pairs to every fixture and pinned the
coverage: all 7 fold and `rank_key` treats each as one letter; all 7 `sort_key`s
are DISTINCT (a tie would make shard boundaries input-order dependent — v4 §1.3
defect B3, a *different* bug that would survive the B-10 fix); the 4 whose small
form is in the alphabet rank in the Greek tier (base 500), not by codepoint; and
the 3 Unicode defines but v4 §1.2 excludes (ϥ ϧ ϫ — FEI, KHEI, GANGIA) fold
correctly but stay in the non-letter tier.

**Two practical warnings from writing those tests.**

1. **Write Greek-script capitals by codepoint, not by hand.** Hand-typing the
   alphabet produced four real bugs in v4 §1.3 (see below). The same trap caught
   an earlier draft of the C2 block: a capital was lost in transit, producing a
   duplicate literal that failed as a "tie" and looked like a collation bug. The
   tests now build literals with `chr(0x03E2)` and friends.
2. **A test that fails for a reason you did not intend is still information.**
   Read it before adjusting it. Three of my own assertions here were wrong, not
   the module.

## Not defects, but do not repeat them

- **Do not hand-type the alphabet.** v4 §1.3's own header records four real bugs
  from doing so (including typing U+2C9A "Ⲛ" for *kho*, which is capital Ni).
  `collate.py` resolves every letter from its Unicode **name**. Keep it that way.
- **Do not assume `format` is enforced.** See B-6.
- **Do not assume v5's section numbers match v4's.** v5 §1 amends "§1" and "§6";
  in v4 those are §6.3 and §3.5 (`DECISIONS.md` A-1).

### E4-1 · §6.1's tarball covers the corpus, and the corpus is not the size problem

**Plan said:** `data/dist` drops from 36 MB to under 5 MB once the corpus is
tarred.

**Measured:** `data/dist` was 37,245,747 B before Session 4 and 37,140,393 B after
(35.42 MiB). It did not drop. §6.1 assumed the corpus was the large artefact —
2.38M words of aligned text — but in this build the corpus is 0.05 MiB and the
**dictionary is 33.68 MiB of JSON**, roughly 700x larger. The tarball compresses
11.1x and does its job perfectly; it is simply pointed at the smaller half.

**Not corrected, because the fix is a data-modelling decision, not a build
decision.** Which fields a reader-facing page actually needs is the question to
answer first, and answering it by guessing would mean shipping a dictionary with
fields removed that something needed. Recorded as open question 2 in
`DECISIONS.md`.

### E4-2 · §6.1's fingerprint is `meta.json`, and a counts-only meta.json cannot see content

**Plan said:** fingerprint each work by `sha256(meta.json)`.

**Measured:** the tarball shipped with no text in it for a full session (S4-C1).
When that was fixed, the builder reported `fingerprints unchanged — SKIPPING` and
**discarded the fix** (S4-C2), because `meta.json` held only counts. The plan's
fingerprint, as written, is not sensitive to the artefact it is fingerprinting.

**Corrected in the build:** `meta.json` now embeds
`content_sha256: {text.json, tokens.json}`, so the plan's cheap fingerprint is
content-safe. `--hash-content` still walks the whole tree. The manifest records
which mode produced it. This is an addition to §6.1, not a departure from it.

### E4-3 · A stage gate is not a substitute for an artefact gate

Not in the original plan at all, and it is the one that would have caught S4-C1:
nothing asserted that the corpus **contains text**. Every stage gate passed on an
empty corpus, because each measured a different thing than the thing that was
broken. Added `tools/validate/corpus_text_guard.py` and
`tools/validate/tarball_guard_check.py`, both wired into CI.

### E4-4 · Errata length

This file is now over the 100-line budget agreed in Q6. The overage is
Session 4's four findings above, three of which are "the plan's own gate could not
have caught the bug it was written to prevent".


---

## Session 10 errata

### E1 — `parent[2]` vs `parents[2]` in `tools/tests/playwright/test_sw.py`

`ROOT = pathlib.Path(__file__).resolve().parents[2]` resolves to `tools/`, not the
repository root, because that file sits one directory deeper
(`tools/tests/playwright/`) than the other tests. Every Playwright test skipped
with *"no public/sw.js"* while `public/sw.js` sat right there. The guard was
correct; it was looking in the wrong tree. Fixed to `parents[3]`.

**Lesson: a skip message is a claim about the world, and this one was false.**
Four of five suites in this repo were unaffected only because they sit at
`tools/tests/`. The fixture is now in `tools/tests/playwright/conftest.py`, where
the depth is stated once.

### E2 — the service worker shipped but was never registered

Session 9 generated `public/sw.js` with a valid 8-entry precache list, wrote it to
`public/`, and passed `public_provenance_guard.py --strict`. Nothing ever called
`navigator.serviceWorker.register()`. The site cached nothing.

Registration now lives in the shared footer partial, inline on every route. A
comment in `footer.html` records why it is inline rather than bundled.

### E3 — Goldmark stripped the reader markup

`hugo.yaml` sets `markup.goldmark.renderer.unsafe = false` (correct). The reader's
`<div>`s and `<script>` were written as raw HTML into generated markdown and were
silently dropped — the page rendered its heading and nothing else, with no
warning. Moved to `themes/copticref/layouts/shortcodes/corpus.html` rather than
weakening `unsafe`, so content stays closed to raw HTML while the template can
supply the reader.

### E4 — page-relative data URLs

`reader.js` and `corpus.js` requested `data/dist/dict/index.json.gz` without a
leading slash. On `/dict/` and `/corpus/<work>/` that resolves to
`/dict/data/dist/...` → 404. Worse, it could never match the service worker's
cache key, which stores `/data/dist/...`, so offline would have failed even after
the worker installed. Both are root-relative now.

### E5 — `.json()` on gzipped bytes

`corpus.js` called `r.json()` directly. When the host does not set
`Content-Encoding: gzip` the browser hands back raw gzip and the parse throws
*"not valid JSON"*. Both readers now sniff the `1f 8b` magic bytes, which is the
same rule the service worker follows.

### E6 — `data-ref` instead of heading `textContent`

The corpus click handler recovered the verse reference from
`heading.textContent.trim()`, which also contains the CTS URN in a `<span>`. Every
lookup missed, so every token panel silently lost its lemma and its dictionary
link. The `<section>` now carries `data-ref`.

### E7 — `corpora.works.<slug>`, not `<slug>`

`fetch_work --check` first read pins from `lock[slug]` and reported all six
shipped works as `UNPINNED` — alarming, and purely a wrong key. The pins live at
`corpora.works."<slug>"`. The digests it computed had matched the lock exactly.

### E8 — `strip_chars` scanned only the stripped field

`_strip_chars()` first read `norm_key`, which `collate.py` has already stripped,
so it found nothing and emitted `[]`. The marks live in the **display lemma**.
Scanning both fields yields
`['U+0300','U+0304','U+0305','U+0323','U+FE24','U+FE26']`.

### E9 — Pagefind's skip was on stderr

`pagefind_index.mjs` announced "no Pagefind binary" on **stderr** and exited 0.
`tools/build.py` only surfaces a script's stdout, so the skip was invisible and
the build printed a green `guard PASSED` while shipping no search index. The
message now goes to stdout, and `build.py` warns when `public/pagefind/` is
absent. Same shape as E2: a missing artefact that nothing objected to.


---

## Session 11 errata

### E10 — `assert cond,` with the message on the next line

```python
assert not line.lstrip().startswith(("//", "*", "<!--")),
    f"the only register() call is commented out: {line.strip()[:80]!r}"
```

`SyntaxError: invalid syntax`, pointing at the end of the *first* line with no
useful context. Python allows a line break after `assert x,` only inside
brackets; the message needs `assert x, (`.

The confusing part was the diagnostic: the caret landed far from the real cause,
and a bisect over line prefixes reported every multi-line construct as a
candidate. Compiling each top-level block separately located it in one pass.

### E11 — `pytest.mark.xfail(condition=lambda ...)` does not bind per-param

A module-level `xfail_refs = pytest.mark.xfail(condition=lambda slug: slug in
BROKEN)` xfailed **every** work, including `sahidic_ruth`, whose refs are unique
and which genuinely passes. Replaced with `pytest.param(slug, marks=...)` in a
single shared `_PARAMS()` list, so the marks cannot drift between the three tests
that need them.

Separately: `xfail_refs` used as a decorator was missing its `@`, which is a
`SyntaxError`, not a `NameError`.

### E12 — test anchor duplicated the production transform

The corpus test computed anchors as `ref.lower().replace(" ", "-")`, giving
`ruth-1:1` for "Ruth 1:1" — and a colon is not legal in a CSS id selector, so
Playwright errored on the selector rather than reporting a corpus problem. The
test now uses the same transform as `corpus.js`. Rule: a test must call the same
function as the code, not a paraphrase of it.

### E13 — hard-coded expectations written from memory

`test_corpus_works.py` shipped with a `WORKS` table I wrote from memory. Four of
six rows were wrong (Life of Isaac was recorded as 0 verses; it has 406). The
counts are now pinned from the published corpus. A test whose expectation is
typed from memory is worse than no test: it fails for the wrong reason and
teaches you to distrust it.

### E14 — `npm run build` violates Rule 5

`package.json`'s `build` script ran `hugo` directly, writing to `public/` outside
`tools/build.py`, which deletes and regenerates `public/` in a fixed order.
Running it would leave orphans from a previous build that
`public_provenance_guard.py` then rejects. DEPLOY.md names `tools/build.py` as
the build command and says why `npm run build` is not it.

### E15 — Pagefind resolved only from `/tmp`

`pagefind_index.mjs` defaulted `PAGEFIND_BIN` to `/tmp/pagefind`. On a fresh
checkout — and on every Cloudflare Pages build container, where `/tmp` is empty —
that meant **no search index**, silently. Now resolves `$PAGEFIND_BIN` →
`node_modules/pagefind/lib/runner/bin.cjs` (pinned 1.5.2) → `/tmp/pagefind`.


---

## Session 12 errata

### E16 — `package.json` said "PINNED EXACTLY, no caret" directly above `"^1.5.2"`

The comment was right about the intent and the value contradicted it. A caret lets
the installed pagefind drift, so the search index can differ between bakes —
breaking the byte-reproducibility every other pin here guarantees. Fixed to
`"1.5.2"`; `tools/validate/pagefind_pin_guard.py` fails the build if a caret or
range returns. The guard found this in the first minute it existed, which is the
best argument for having written it.

### E17 — the build was not byte-reproducible, and a path+size check could not see it

Session 10's idempotence check hashed paths and **sizes**. The manifest's
`generated` stamp advanced on every build (E: generator writes into `content/`,
stamp derives from `content/` mtimes), so the bytes differed while the sizes did
not. The check now hashes file **contents**, and `safeio.write_verified` skips
writing when the bytes already match.

### E18 — vendoring pagefind produced a binary that could not run

`node_modules/pagefind/lib/runner/bin.cjs` is a 1,137-byte **wrapper** that
resolves the real platform binary at runtime. Copying it produced
`vendor/pagefind/pagefind-1.5.2`, which printed a Node stack trace when run.
Reverted. Unverified mitigation withdrawn rather than shipped — and the DEPLOY.md
section rewritten to say so, since a doc claiming a mitigation that does not work
is worse than no doc.

### E19 — two of this session's own behaviour tests failed, for the right reason

`test_behaviors.py` asserted that `navigator.serviceWorker.register` appears in
served HTML, that `corpus.js` contains `0x1f`, and that the handler reads
`data-ref`. Session 12 moved all three — to a file, to `fetch_json.js`, and to
`data-vindex`. The tests were pinning an arrangement, not a property. Rewritten to
the properties, with all six negative demonstrations re-run to prove each still
fails.

`behavior_5` took three attempts: first checking the constants, then checking
`isGzip(buf) ?` anywhere — which the *error message* also contains — and finally
matching `out = isGzip(`. A negative demonstration that stops failing is theatre.

### E20 — Hugo `--minify` strips attribute quotes (third time)

`<script src="/js/sw-register.js">` is emitted as `src=/js/sw-register.js`.
A quoted-only regex failed. This is the third selector this has broken (after
`section.verse#ruth-1:1` and `id="q"`); every selector against minified Hugo
output must now be quote-agnostic.

### E21 — running `pagefind --site public` by hand destroys the dictionary index

The index is built from `pagefind-entry-records.json`, which the build writes,
uses, then deletes. Running pagefind against `public/` without that file produces
an HTML-only index — 663 words instead of the full dictionary — and silently
replaces the shipped one. Done accidentally while investigating D3; caught by the
search tests returning the wrong shape of result, and repaired by rebuilding.

### E22 — a Node harness whose `run()` helper clobbered its own mocks

The 404 and empty-body cases set `globalThis.fetch` and then called `run()`, which
installs its own mock — so both "passed" while actually re-reading the happy-path
buffer. The mock is now part of the call. Same class of error as the invalid
minimal harness in Session 11: **a test with no working control is worse than no
test**, because it looks like evidence.


---

## Session 14 errata

### E23 — three null results, all from the probe

`?q=ⲃ︦` → 0 hits (hand-written percent-encoding); precache "10 vs 8" (regex
matched the *template* `PRECACHE = [`, not the emitted array); deployed cache
"0 entries" (raced the worker's install). The third was in the checklist written
this session, which is what made it worth a rule: the check meant to catch a
failure reported one on a healthy system. Rule 10 now requires calibration, and the
checklist compares declared against served instead of reading a bare cache.

### E24 — the English index was written to `public/` by an emitter

`public_provenance_guard.py --strict` called it an orphan. The guard was right and
the file was on the wrong side of Rule 5. Emitters write to `data/dist/`; the
build publishes into `public/` and claims it in the manifest.

### E25 — the emit ran after the publish

`tools/build.py` printed *"english_index.json.gz is absent; English gloss search
will not work"* and shipped a site whose English search silently did nothing —
a warning about a file the build had not yet produced. Order was the whole bug.
The emit is now step 3c, immediately above the publish.

### E26 — `<ul id="results">` received a `<p>`

`reader.js` injects `<p class="count">…</p><ul class="hits">…</ul>` into `#results`,
which was a `<ul>`. Every `/dict/` load put a paragraph directly inside a list and
Lighthouse reported *"Lists do not contain only `<li>` elements"*. The container is
not a list — the list is inside it. Now a `<div>`; accessibility 93 → 100.

### E27 — the OAuth token cannot refresh itself

  `wrangler pages deploy` failed with *"Your auth token has expired and could not be
refreshed because the Cloudflare auth server could not be reached"* — while
`curl` to the same host answered fine and `wrangler whoami` still worked. Same
Node-`fetch`-versus-`curl` split as Session 13's `pages project create`. Re-running
the command succeeded; the deploy needed no change. `PRE_PRODUCTION_CHECKLIST.md`
records it so it is not rediscovered as a permissions problem.

---

## Session 16 errata

### E28 — an empty transliteration object is not a visible `[object Object]`

All 11,369 emitted entries currently have `translit: {}`. That means no shipped
dictionary page could presently display the literal bug, even though
`reader.js` would have printed it for the first nonempty value. The fix was
still required: latent shape bugs are not passing tests.

### E29 — Kaikki romanizations are source data, not invented transliteration

The shipped `translit` schemes remain empty, but 2,799 Kaikki-derived
`forms.romanization` values exist. Quiz transliteration prompts use those values
through the one renderer and label them as romanizations. Calling one of them
“Bohairic” would have invented a scheme the source does not assert.

---

## Session 18 errata

### E30 — a guard that scans nothing passes (parents[1] vs parents[2])

`reader_usage_guard.py` first shipped with `ROOT = parents[1]` (the `tools/`
directory) instead of `parents[2]` (the repo root). It scanned `tools/tools/`
and `tools/static/js`, found nothing, and printed OK. A guard that checks
nothing is worse than no guard — the exact failure mode COVERAGE.md exists to
prevent. Caught because the run was suspiciously clean: three flags were
expected from the pre-run survey and zero appeared. Fixed to `parents[2]`;
the guard immediately failed with the three real flags. Lesson restated: a
new guard's first run must produce its expected findings before it is
believed, same as Rule 10's probe calibration.

### E31 — the split-line read the grep guard cannot see

`dict_index.py:135` read `index.json` through `hdr_path`, assigned two lines
above. The line-based guard cannot match a verb and a path on different
lines, so this one was found by reading the survey output, not by the guard,
and fixed the same way (via `safeio.read_maybe_gzip`). Recorded as a stated
limitation in the guard's docstring and in COVERAGE.md rather than fixed by
making the guard track variables — a variable-tracking linter is a project
of its own, and an honest limitation beats a clever heuristic nobody can
audit.

### E32 — the line-grep guard needed an AST (reader_usage_guard rewrite)

Session 18's guard matched verbs and paths on the same line; E31 documented
the split-line shape it could not see. Session 19 rewrote it on `ast`:
calls have path expressions resolved (constants joined through `/`,
f-string parts, variables followed transitively with per-function scopes
and a cycle guard), keeping the regexes as a file-level pre-filter. The
rewrite over-reached twice before shipping — file-wide variable merging
flagged three innocent vault writes, harvesting content arguments flagged
vault prose mentioning `data/dist` — and both were fixed by narrowing
(path-position args only, per-function scopes) rather than by exemption.
The E31 shape has a reproducing test the old regex provably misses.

### E33 — size_guard red from stale plain CSVs nobody gzips

`size_guard` failed at 122% of the 5 MiB data/dist budget. The overage was
1.72 MB of plain `records.csv` + `LICENSES.csv` sitting next to their `.gz`
twins since the Session 17 re-emit: `emit/cli.py` always writes plain, and
no automated step runs `gzip_csvs.py` (its docstring says the plains are
removed, but nothing invokes it). Fixed by running `gzip_csvs` (−1.49 MB),
not by raising the budget — a budget breached by doing the planned thing
still gets fixed by doing the planned thing, and "tune the budget" stays
off the table. Open item: the emit→gzip step has no owner in build.py or
any Makefile (there is no Makefile); the next emit will re-break this.

### E34 — a comment tripped the content guard

`no_object_object_guard` scans file contents, comments included. The new
`pos_labels.js` header mentioned the raw-object marker by name to explain
what it prevents — and failed the guard for containing the string. Fixed by
describing the bug class without the literal, with a comment in the file
saying why the literal must never appear. Guards that scan text cannot tell
mention from use; the file now says so on its own behalf.

## Session 22 errata

### E35 — touching `site.Data` makes Hugo read every file under `data/`

The first Session 22 build died with `data/dist/anki/drill.apkg:1:1:
unmarshal of format "" is not supported`. The decks had been written under
`data/dist/` (where every other pipeline artefact lives), so the obvious
fix was to move them out; moving them made the same error reappear on
`data/dist/corpus/corpus.tar.gz`, then — with `data/dist` renamed away
entirely — on `data/README.md`. The tree had built cleanly 20 minutes
earlier. `git stash` of the session's changes and a re-run proved it:
clean tree builds, modified tree fails.

The actual trigger was one template line. `speak/list.html` ranged over
`site.Data.speak_top100` for the `<noscript>` table, and the moment any
template references `site.Data`, Hugo's data loader unmarshals EVERYTHING
below `data/` — every file, extension notwithstanding, binary or not.
Without a `site.Data` reference the loader never runs, which is why
`corpus.tar.gz` had sat unharmed in `data/` for six sessions.

Fixes, both required: (1) the no-JS word list became a standalone static
page (`/speak/top100.html`) written by `speakgen` and copied into `public/`
by `build.py`, so nothing reads `site.Data` at all; (2) the `.apkg` decks
moved to `work/anki/` regardless — a build product the site does not serve
at build time has no business inside the tree a template can reach, and
the next person who reaches for `site.Data` should not meet a zip file.
The lesson is not "Hugo is bad at data files": it is that a data directory
is not a scratch space the moment a template touches it.

## Session 23 errata

### E36 — a push is not a deploy, and on this project it has not been one since Session 15

Session 22's receipts said "pushed `3e3748e..b70f338`, 0 ahead" as though
that ended the work. It did not: at the start of Session 23 every route
added since Session 15 — `/quiz/`, `/drill/`, `/course/`, `/write/`,
`/speak/`, all fifteen lesson pages — was a 404 on production, which was
still serving the Session 15 build. Seven sessions of documentation,
tests and deploys-in-spirit never reached the live URL.

Two facts stacked so nobody noticed. First, the Cloudflare Pages project
is git-connected, but its build has produced **empty 404-only
deployments** since `886a48f` — a dashboard-side configuration the CLI
cannot read, let alone fix; every push created a deployment while
shipping nothing (re-confirmed after Session 23's own pushes:
`d094b123`, `171273e4`, `35eb3c85` all answer 404 for both
`/BUILD-MANIFEST.json` and `/`), and no session ran a route check
against the live URL, because pushing was assumed to deploy. Second,
what a missing path answers depends on the hostname, not on the route:
on the apex a bare 404, on a deployment URL the homepage with HTTP 200
(`x-robots-tag: noindex` — a soft-404), on an empty git deployment a
404 even for `/`. Whichever of the three a check happens to hit, the
status code alone identifies nothing — only the response content does
(Rule 17).

The fix was never in the plan because the plan (correctly) assumed
`push → deploy`: `npx wrangler pages deploy public` direct-uploads the
baked tree and works (`66a9a37a`, `797c0916`, `08459596`). The durable
correction is Rule 16 — shipped means deployed to the public URL and
verified there, in the same session, and the session receipt must name
the deployment — plus HANDOFF §5, which now teaches the upload instead
of "push to main, Cloudflare deploys automatically". Until the dashboard
build is repaired or the project is disconnected from git, every
maintainer must treat `git push` as history-keeping and the deploy
command as the release. And no production check should trust a status
code alone on this host: compare the body (title, or a known marker)
against what you expect to have shipped.

One more layer, found while closing the session: even a correct body
check can be reading yesterday's deploy. The apex edge caches assets
with `s-maxage=604800` and does **not** purge on deployment — the
Session 23 build's `BUILD-MANIFEST.json` was invisible on
`coptic-reference.pages.dev` for hours (age 21,597 and counting, born
at the D0 fetch, surviving two later deploys) while the deployment
hostname `08459596.coptic-reference.pages.dev` served the new file with
`max-age=0, must-revalidate`. Anything fetched in an earlier deployment
can therefore report stale bytes for up to seven days, and a
local-versus-remote manifest comparison fails for a reason that is
entirely cache. Verify with `cf-cache-status`/`age` in the response, or
fetch the same path from the deployment URL, before believing a
discrepancy — and before claiming an agreement.

**Correction, Session 24.** The closing claim above — "production still
serves the direct upload (`08459596`'s content) — the empties never
replaced it, which is why the Session 15 build survived seven sessions
of pushes" — was true when written and is now false. Measured Session
24: the apex origin was serving an **empty git build**
(`fb32acf5`, source `604ffd4`, Environment Production: 404 for `/`,
for `/js/course.js`, for `/BUILD-MANIFEST.json`), masked by the very
edge cache this entry describes — uncached paths (`/lessons/05/`,
`/favicon.ico`, `/keys/`, …) answered bare 404 while pages fetched
during Session 23 still answered 200 from HIT entries with `age` past
43,000 s. Sometime after Session 23's final upload and its own push,
the empties took the alias; what changed in the dashboard to allow
that after seven sessions of not allowing it cannot be read from the
CLI (`wrangler pages project` has no `get`). The session's own
direct upload (`fe421e32`) took the alias back — `/lessons/05/`
answered 200 from origin immediately after — so the durable rule
gains one clause: **the deploy is the last act**, because a push
after a deploy can move the alias onto a new empty build. Full
measurement and Michael's dashboard checklist: DECISIONS Session 24
D4.

### E37 — the plan's Shenoute reading windows were partly fabricated

**Claim (plan, Session 24 handoff):** lesson windows 306–309 and 42–45
carry clean Coptic / real English; v309's English opens "That the word
might…"; the v43/ⲛⲁⲓ pair is dative evidence.

**Measured, Session 25 D0:** v42–45 en = '...' (the source's
placeholder); v306–309 en = empty (the quoted sentence never existed in
the tarball); v43 ⲛⲁⲓ is demonstrative "these". Reading windows were
re-measured from the tarball and replaced: 95–98 / 100–103 / 82–85 /
89–93, Lausiac 4–7. Drill ranges unchanged.

### E38 — "587 real English" counted the placeholders

`en populated = 587` counted ASCII "..." as English. Truth: 21 of 1,078
segments carry real Brakke/Crislip prose; 566 carry "..."; 491 are U+2026
→ None. Corrected in tt.py's comment, shipped.toml's note (flows into
meta.json and the corpus pages), corpus_text_guard's comment, and
test_tt_parser's comment. The parser deliberately still parses "..." as
it finds it — normalizing would be a data change, not a comment fix.

### E39 — exact Coptic cannot be typed through this interface

Writing a crasis (five contiguous codepoints) or a macron (a letter +
U+0304) into a file via a typed string silently mangles diacritics and
spacing. The working tactic: inject exact strings programmatically with
`chr()` sequences after the file is written; `lesson_vocab_guard`
verifies them by normalized form either way. Anything future sessions
must reproduce exactly (crasis tokens, combining marks) should be built
from codepoints, not typed.

### E40 — the lesson-16/17 dative claim lost its evidence

The register row for the bare dative cited Shenoute v43 — but that
token is demonstrative "these" (dead as dative evidence). The live
evidence is v102: Coptic bare dative against English "give it to us",
aligned. Row rewritten; the circumstance claim now cites v95 (with
English) and v309 (Coptic-only) instead of the fabricated translation.

### E41 — D1's commit message mis-adds the verse receipt

`75a9057`'s body says verses 3,201→4,279. The work tables sum to
2,601→3,679 (measured by corpus_shape_guard on the shipped tarball:
3,679 verses, 99,642 tokens). The token figures in that message
(83,017→99,642) are correct; only the verse arithmetic is wrong. The
commit is immutable; this entry carries the correction.
