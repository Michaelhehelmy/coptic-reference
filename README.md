<div align="center">

# ⲙⲉⲧⲣⲉⲙⲛⲕⲏⲙⲉ

### A free, offline-capable reference for the Coptic language

Coptic is the last stage of Ancient Egyptian, and it is still chanted every week
in Coptic Orthodox churches across Egypt, the Sudan, and the diaspora.
Almost none of it is on the internet.

**This site puts a dictionary, 2.38 million words of annotated text with parse
data, aligned human translations, a concordance, a starter course and flashcards
into something that loads fast, works without a signal, and costs nothing to run.**

</div>

---

## What is in it

| | |
|---|---|
| **Dictionary** | ~11,500 entries from the Comprehensive Coptic Lexicon, Coptic Dictionary Online and Wiktionary. Every entry shows its **sources and what we changed** — required by CC BY-SA, and the only honest way to publish a merged lexicon. |
| **Corpus** | 2.38M words of Sahidic and Bohairic Coptic with part-of-speech, lemma, and dependency parse. Tap any word to look it up. |
| **Translations** | Human translations aligned line by line — Brenton's Septuagint, Budge's editions, Arabic. Not machine translation. |
| **Concordance** | Every occurrence of any lemma, with context and deep links. |
| **Lessons** | Fifteen lessons to start. Five more a month, in the open. |
| **Flashcards** | ~11,500 cards, exportable to Anki. |
| **Offline** | Works with no signal. Installable. No account, ever. |

---

## Status

**This repository is at Session 2 of a 16-week build. The site does not exist
yet.** Nothing in "What is in it" above is generated yet; that table describes
the finished goal. Read this section before trusting any other part of this file.

| | Built and verified | Not built |
|---|---|---|
| **Data pipeline** | Collation (32 tests, alphabet pinned); four parsers verified against real data — `_TT` (Sahidic Ruth), Kaikki (3,293), CCL (11,283), CoNLL-U (58,974 tokens); merge (11,369 entries, v4 §2.4 precedence); sharding + `records.csv` + `LICENSES.csv`. **257 tests.** | Pagefind, corpus tarball, `shipped.toml`-driven corpus ingest |
| **Gates** | Nine guards, all run against the real dataset, each with a demonstrated failure: `collation_guard`, `nc_guard`, `nc_guard_public`, `licence_guard`, `corpus_text_guard`, `tarball_repro_check`, `tarball_guard_check`, `dialects_check`, `fetch_all --check/--self-test`, plus `dry_run --real`. **14 CI jobs.** | — |
| **Schemas** | `entry.schema.json` (all 11,369 real entries valid), `suggestion.schema.json` | — |
| **Contributions** | `workers/suggest/index.ts`, 28 smoke assertions incl. search-based dedup | **Never deployed.** No preview, no live GitHub test |
| **The site** | — | Hugo config, layouts, theme, content, Pagefind index, **all 15 lessons**, `/roadmap/`, `/licences/`, `/credits/` |

**Gated, deliberately, until a human decides** (see `PRE_LAUNCH.md`):

- ☐ **Deputy Maintainer named** — v5 §15 makes this a launch gate.
- ☐ **Worker deployed to a preview** and its dedup verified against real GitHub.
  The 28 smoke assertions run against a *stubbed* API and do not substitute for this.

**Do not add content yet.** The gates are in place and passing, which is what
makes content safe to add — but no real source has been through them.

---

## Quick start

There is nothing to run yet — no site, no Makefile. What you can do today is run
the gates, which is the useful thing for a new contributor to do first.

```bash
git clone https://github.com/coptic-reference/coptic-reference.git
cd coptic-reference

python3 -m venv .venv && . .venv/bin/activate
pip install -r tools/requirements.txt
```

### The gates

Run all four. Each must exit `0`. These are the same commands CI runs on every
push (`.github/workflows/ci.yml`).

```bash
python3 -m pytest tools/tests/ -v            # 280 tests: collation, _TT parser,
                                             # kaikki/tei/conllu parsers, schemas, NC
                                             # guard, the 12-check corpus round trip,
                                             # and the guards themselves
python3 tools/validate/collation_guard.py    # the 23-letter Coptic alphabet is
                                             # pinned at b7b49af6e144ef87
python3 tools/validate/nc_guard.py           # invariant 5: no non-allowlisted
                                             # and no CC BY-NC source in data/dist
python3 tools/validate/corpus_text_guard.py  # the corpus must contain TEXT --
                                             # added after it shipped empty for a
                                             # whole session (see DECISIONS S4-C1)
python3 tools/validate/tarball_repro_check.py   # two --force builds, same SHA-256
python3 tools/validate/tarball_guard_check.py   # unchanged -> SKIP, text edit -> rebuild
python3 tools/validate/dialects_check.py        # dialects.json matches the shards
python3 tools/validate/licence_guard.py      # invariant 7: every source id has a
                                             # determined licence in LICENSES.csv
python3 tools/fetch/fetch_all.py --check     # source pins (see the caveat below)
```

### Proving the gates work

A gate nobody has watched reject anything is decoration. These deliberately fail:

```bash
python3 tools/merge/dry_run.py                            # PASS
python3 tools/merge/dry_run.py --inject nc-in-attribution # FAIL at stage 4
python3 tools/fetch/fetch_all.py --self-test              # proves the verifier bites
```

**Caveat on `fetch_all.py --check`:** `sources/` is gitignored, so on a fresh
clone there is nothing to byte-verify and it reports `0 pinned source(s)
byte-verified`. It audits `tools/sources.lock` for internal contradictions and
says so plainly. Detecting an *upstream* change requires the downloaded files —
run `python3 tools/fetch/fetch_all.py` locally.

**You need:** Python 3.12. Later sessions add Hugo extended and Node 22.
**No GPU. No API keys. No database.**

---

## Data pipeline

Five stages, in order. Stage A is slow and runs on a schedule; Stage B is fast
and runs on every push. **Every stage that produces output is gated.**

```
sources/  ──parse──▶  work/parsed  ──merge──▶  work/merged  ──emit──▶  data/dist/**  ──▶  Hugo
   ▲                                                              │
   └──────────────────── fetch ────────────────────────────────────┴── validate/*
```

### Run it locally

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r tools/requirements.txt

python3 tools/fetch/fetch_all.py        # download + verify every pin
python3 tools/parse/kaikki.py --census  # stream the 62 MB extract
python3 tools/parse/tei.py --census     # CCL v1.2-2020 (11,283 entries)
python3 tools/parse/conllu.py --census  # UD Coptic-Scriptorium (58,974 tokens)
python3 tools/merge/entries.py          # Kaikki + CCL -> unified entries
python3 tools/emit/cli.py               # -> data/dist/dict/shard-NNN.json.gz + index.json
python3 tools/emit/corpus_tarball.py    # -> data/dist/corpus/corpus.tar.gz (fingerprinted)
python3 tools/emit/corpus_refs.py       # populate corpus_refs[]   (MUST follow cli.py)
python3 tools/emit/dict_index.py        # -> data/dist/dict/index.json.gz  (the lookup table)
python3 tools/emit/dialects.py          # -> data/dist/dialects.json
python3 tools/emit/corpus_public.py     # -> public/data/corpus/
python3 tools/validate/size_guard.py --blame   # enforce the offline budget
```

Every artefact write goes through `tools/safeio.py::write_verified()` — write to
`.tmp`, `fsync`, `os.replace`, **read back and compare**. A write that reports
success is a claim; a read-back is evidence. See Rule 3 in `CONTRIBUTING.md`.

### The site

Hugo builds the reading path. It is a shell today — no JavaScript, no Pagefind,
no search — and that is deliberate: the data is built and licence-checked, and the
browser fetches it rather than a page baking it in.

    hugo --gc --minify --destination public_hugo      # 24 ms, 14 pages, 0 warnings

**No layout reads `data/dist`.** That is a tripwire, not an accident: CI asserts
the build stays under 30 s precisely so that a layout which starts crawling the
dataset fails loudly instead of turning a 24 ms build into a 60 s one.

Stage B, end to end:

    hugo --gc --minify
    node tools/emit/pagefind_index.mjs     # stub — says so
    node tools/emit/sw_gen.mjs              # stub — says so

Measured: **0.13 s** against a 60 s budget. The stubs exit 0 *and print that they
are stubs*, because a silent no-op that looks like success is how a build quietly
stops producing search.

Provenance tables ship as `.csv.gz` and are read at `/licences/read-csv.html` —
under `/licences/` because `LICENSES.csv` **names** the six CC BY-NC sources it
excludes, and invariant 5 permits those ids only on a disclosure page. Shipping
that file from `/read-csv.html` fails `nc_guard_public`, which is exactly what
happened the first time.


### Part of speech is a controlled vocabulary

The merge was carrying **55 distinct POS strings** from three sources that do not
agree: CCL uses German (`Subst.`, `Vb.`, `Präp.`), Kaikki uses English
(`n`, `v`, `adj`), UD uses universal tags. `tools/pos.py` normalises them to **21
values** at merge time, keeps the original in `attributions[]`, and **refuses**
anything unmapped — so the vocabulary cannot widen itself.

| | before | after |
|---|---|---|
| distinct POS | 55 | **21** |
| entries with non-ASCII POS | 136 | **0** |

### The offline budget is enforced

`tools/validate/size_guard.py` — fails the build on exceed, and `--blame` names
the largest contributors.

| | actual | budget |
|---|---|---|
| `data/dist` | 4,058,130 B (3.87 MiB) | 5 MiB |
| `public/` | 989,651 B | 20 MiB |
| largest shard | 150,770 B | 200 kB |
| `dict/index.json.gz` | 180,272 B | 500 kB |

`provenance/records.csv` is **1,717,003 B — 42% of `data/dist`**, and is the first
thing that will breach the 5 MiB line.

**Order matters, and it has bitten twice.** `emit/cli.py` re-emits the shards from
`work/merged`, which **drops every `corpus_ref`**. Run `corpus_refs.py` after it or
you ship entries with empty citation lists — no error, just quietly missing data.
`dict_index.py` must run last, because it reads the shard offsets that
`corpus_refs.py` rewrites. `tools/tests/test_client_lookup.py` fails if the order
was wrong.

### What is gzipped, and what the index is for

| Artefact | Form | Size | Why |
|---|---|---|---|
| `dict/shard-NNN.json.gz` | gz, 23 shards | 1.88 MiB | **18.6x.** One shard per lookup, not all 23. |
| `dict/index.json.gz` | gz | 184 KB | **The lookup table.** `lemma -> (shard, offset)`. |
| `dict/index.json` | plain | 133 KB | Build record: alphabet, ids, shard ranges. |
| `corpus/corpus.tar.gz` | gz | 49 KB | Reviewed in a pull request, licence-checked. |
| `public/data/corpus/<slug>/*.json.gz` | gz | 49 KB | What the browser downloads. |

`data/dist` went from **35.52 MiB to 4.05 MiB** — under the 5 MB budget, with **no
field pruned**. The 18.6x is gzip, not deletion.

Fonts and images are **not** gzipped: they are already compressed formats, and
gzipping compressed data makes it larger. `records.csv` and `LICENCES.csv` are left
plain because a human is more likely to open them directly. The full table, with the
reasoning, is in `CONTRIBUTING.md`.

### How a client fetches an entry

This is the "tap a word, see the entry" loop. No UI is built yet — this is the
contract, pinned by `tools/tests/test_client_lookup.py`.

```js
// 1. one small file, cached whole
const idx = await fetch("data/dist/dict/index.json.gz")
  .then(r => new Response(r.body.pipeThrough(new DecompressionStream("gzip"))))
  .then(r => r.json());

// 2. norm_key is the lookup key: it is what the shards were sorted by, and it
//    folds a capitalised input to the small form, so a reader who types "Ⲁⲁⲙ"
//    finds the entry stored under "ⲁⲙ".
const norm = canonForSort(tappedWord);          // tools/collate.py, the pinned collator
const row  = idx.rows.find(r => r.norm_key === norm);

// 3. fetch exactly one shard — not all 23
const shard = await fetch(`data/dist/dict/shard-${String(row.shard).padStart(3,"0")}.json.gz`)
  .then(r => new Response(r.body.pipeThrough(new DecompressionStream("gzip"))))
  .then(r => r.json());

const entry = shard.entries[row.offset];        // the entry, with corpus_refs[]
```

**Why the client decompresses explicitly** rather than relying on
`Content-Encoding: gzip`: Cloudflare Pages sets `Content-Type` from the file
extension and will not attach that header to a `.gz` on disk, so the browser would
hand raw gzip bytes to `JSON.parse`. Getting the header right would need a
`_headers` rule on `/*.json`, which would also mislabel any uncompressed `.json` we
serve. Reasoning recorded in `tools/emit/gzip_shards.py`.

`offset` is an index into the shard's `entries` array, **not** a byte offset: a
byte offset is destroyed by any re-compression and a stale index would then decode
the *wrong entry* silently, whereas an out-of-range array index fails loudly.

Both index files carry `collation_hash`, and `tools/validate/index_pin_guard.py`
refuses the build if a shipped index disagrees with the alphabet on disk — so a
client can check its collator matches instead of mis-sorting quietly.

`--census` on any parser prints counts without writing anything — the fastest way
to see whether a source changed shape.

## Corpus

The corpus is the aligned, parsed text: 2.38 million words across the works listed
in [`tools/shipped.toml`](tools/shipped.toml), with part-of-speech, lemma,
dependency parse and word-for-word English.

### What ships, and what actually ships

`shipped.toml` lists **9 works** in the roll-out order v4 §10.3 fixes —
liturgical → biblical → patristic → monastic, with monastic last because Shenoute
is where the grammar gets hard, not where the language gets useful.

**Right now 1 of the 9 has data in this checkout** (`sahidic_ruth`, 85 verses,
3,470 tokens). Every tool reports the other 8 by name on every run rather than
quietly publishing a smaller corpus than the manifest promises.

### Adding a work

1. Put the source in `sources/corpora/` and pin it in `tools/sources.lock`.
2. Add a `[[work]]` block to `tools/shipped.toml`: `slug`, `title`, `tier`,
   `dialect`, `urn`, `alignment`, and `shipped = false` until a reviewer has read it.
3. `python3 tools/emit/corpus_tarball.py` — it reports the work as new, fingerprints
   it, and rebuilds.
4. `python3 tools/emit/corpus_refs.py` then `python3 tools/emit/cli.py` to repopulate
   `corpus_refs[]`.
5. `python3 tools/emit/corpus_public.py` to publish it to `public/data/corpus/`.

Shipped order is a tier order, not alphabetical. Do not sort the file.

### The tarball, and why there are two copies

| | |
|---|---|
| `data/dist/corpus/corpus.tar.gz` | One compressed archive, 31 KB, **reviewed in a pull request** and licence-checked by `nc_guard`. Rebuilt **only** when a work's `meta.json` fingerprint changes — that is what makes the weekly Stage A cheap. Byte-reproducible: same inputs, same SHA-256. |
| `public/data/corpus/<slug>/` | What the **browser** downloads: `text.json.gz`, `tokens.json.gz`, `meta.json`. A browser cannot read a tarball without a server, and there is no server (invariant 1). |

**`nc_guard_public.py` opens both** — it decompresses gzip and zip members rather
than grepping bytes, because compressed text is exactly where a `grep` cannot see.

**The size finding:** the tarball compresses 11.5×, but `data/dist` did **not**
shrink this session (35.52 → 35.40 MiB). The corpus is 0.03 MiB; the
**dictionary** is 33.68 MiB of JSON and is what Cloudflare Pages actually uploads.
See `DECISIONS.md`, Session 4 headline.

### Which gate protects which stage

| Gate | Protects | Fails when |
|---|---|---|
| `fetch_all.py --check` | fetch | a downloaded file's SHA-256, byte count or record count differs from `tools/sources.lock` |
| `fetch_all.py --self-test` | fetch | the verifier itself stops rejecting a wrong pin |
| `collation_guard.py` | everything | the 23-letter alphabet changes without the pin being updated |
| `nc_guard.py` | **merge, emit** | any non-allowlisted or CC BY-NC source appears in `data/dist/**` (fail-closed: unknown = violation) |
| `nc_guard_public.py` | emit, build | an NC id reaches `public/**` outside the disclosure pages; opens zip/tar members |
| `licence_guard.py` | **merge, emit** | a source has no licence row, the row says `UNKNOWN`, or the allowlist and the manifest disagree |
| `corpus_text_guard.py` | corpus tarball | **the corpus contains no text** — every verse and every token is empty (S4-C1) |
| `tarball_repro_check.py` | corpus tarball | the same inputs give two different SHA-256s, so the hash means nothing in review |
| `tarball_guard_check.py` | corpus tarball | the rebuild guard never skips (weekly bake does all the work), or always skips (edits fail to ship) |
| `dialects_check.py` | dialects.json | the counts drift from the shards, or `no_dialect_recorded` is 0 — i.e. Q4's honesty mechanism has gone missing |
| `test_guards.py` | the guards | a guard stops being able to fail |
| `dry_run.py --real` | all five | the shipped dataset stops validating, or a violation is injected |

### Current output

```
11,369 entries   23 shards of <=500   12,535 records.csv rows
1,166 entries from >= 2 sources       9,738 with a TLA id
```

**Never commit `data/dist/**` with a gate failing.** All ten gates are in
`.github/workflows/ci.yml` and run on every push.

### Two things that will bite you

- **Sort with `collate.coptic_sorted`, never `sorted()`.** Ϣ is U+03E2, below
  every Coptic letter, so codepoint order files Greek-borrowed Coptic words in
  the wrong place. `emit/cli.py` asserts the order and fails the build.
- **Read the plan's code samples only through `PLAN-ERRATA.md`.** Nine defects
  have been found in them by running them.

---

## What a visitor can do

- **`/dict/`** — 11,369 entries. Search a headword in Coptic or English. Capital
  folding and combining-mark stripping both come from tables the index ships
  (`casefold`, `strip_chars`), not from guessed Unicode ranges — 35 headwords
  differ from their normalised form and all 35 are reachable. Every entry links
  back to the works the word appears in.
- **`/corpus/<work>/`** — six parsed texts. Coptic token stream with the English
  verse beneath it; click any token for its lemma, tag and dictionary link.
  Deep links work both ways: `/corpus/sahidic_ruth/#ruth-1-1` and
  `/dict/?q=ⲧⲉⲛⲟⲩ`.
- **Offline** — a service worker precaches the shell, the dictionary index and the
  first shard; `/dict/` renders with the network off. Verified in Chromium by
  `tools/tests/playwright/`.

Without JavaScript both readers degrade to a `<noscript>` note naming the
underlying `.json.gz` files. The data is never hidden behind the script.

### Building

```sh
PAGEFIND_BIN=/path/to/pagefind .venv/bin/python tools/build.py
```

`tools/build.py` is the only writer of `public/` (HANDOFF.md §8a Rule 5). Without
`PAGEFIND_BIN` it still builds, warns, and ships **no search**;
`public_completeness_guard.py --strict` then fails, so CI catches it.

Pagefind's data portion is held under 500 KiB (currently 154.7 KiB). Its total,
including the ~410 KiB vendor UI and wasm, is reported separately rather than
hidden — the budget is on data, and the total is printed so nobody has to guess.

## The three stages

This is the **target** architecture, not the current state. Only `parse` and
`validate` exist so far; `merge` and `emit` are Session 3 and later, and
`data/dist/**` is empty. Most of the time you will want to know this, because it
explains why the build is split:

```
 sources ──▶ parse ──▶ merge ──▶ data/dist/**  ──▶ Hugo + Pagefind ──▶ public/** ──▶ CDN
                          │      (committed)      (seconds, on Cloudflare Pages)
                          └──▶ validate/* ──▶ ✅ or ❌ fail the PR
   STAGE A: weekly, GitHub Actions          STAGE B: on every push
```

Cloudflare Pages Free has a **20-minute build timeout**. The corpus does not fit
through it. So the expensive step runs on a schedule and **commits its output**,
which makes every deploy fast, deterministic, and reviewable.

**You review `data/dist/provenance/records.csv` in a pull request.** That is the
review surface. It is why data changes are safe.

---

## Design decisions worth knowing

**Nothing a reader does to read this site touches a runtime service.** The whole
reading experience is static files. It works with JavaScript disabled, works
offline, and cannot be taken down by an outage.

There is **one** small Cloudflare Worker. It exists only so that someone with no
GitHub account can tell us something is wrong. **Delete it and reading is
completely unaffected** — every suggestion form falls back to a `mailto:` link.

**The dictionary is not 11,500 HTML pages.** That would eat 58% of Cloudflare's
free file budget. It is 300 static pages for SEO and no-JS, plus JSON shards read
in the browser. The whole site is ~950 files of a 20,000 limit.

**Coptic does not sort by Unicode codepoint.** `sorted(['Ϣ','Ⲱ','Ⲁ'])` gives
`['Ϣ', 'Ⲁ', 'Ⲱ']` — the Greek-borrowed letters would sort before ⲁ alfa, which
is nonsense to a Coptic reader and looks perfectly fine to a developer who cannot
read Coptic. `tools/collate.py` fixes it, with the alphabet resolved from Unicode
names, and a test that fails if it regresses.

**No AI, at build time or runtime.** The corpus already carries part-of-speech,
lemma and parse data, so the site needs no model to analyse anything.

---

## Contributing

**Found a mistake? We want to hear it, and you do not need a GitHub account.**

Coptic is read every week in churches and almost all of it has been digitised by
a very small number of people. **If you have read a text here and thought "that
is not what this word means," you are the expert and we are not.**

Every entry, text and lesson has a **"Something wrong? Please tell us"** panel at
the bottom. Type into it, or use the email link. No account, no email, no
captcha.

See **[CONTRIBUTING.md](CONTRIBUTING.md)** and
**[GOVERNANCE.md](GOVERNANCE.md)**.

---

## About the data, and who made it

**Michael Helmy** built this site, the code, and the compilation.

**He did not make the data.** The lexicons, corpora and treebanks are other
people's work, and they are credited more prominently than he is — which is what
the CC BY-SA licence requires, and also what is true.

- **Comprehensive Coptic Lexicon** — BBAW and DDGLC. CC BY-SA 4.0.
- **Coptic Dictionary Online** — the KELLIA alliance. CC BY-SA 4.0.
- **Coptic Scriptorium** corpora — Caroline Schroeder, Amir Zeldes and
  contributors. Per-document licence.
- **Universal Dependencies** treebanks — Zeldes & Abrams (2018); Zeldes,
  Speransky, Wagner & Schroeder (2025).
- **Wiktextract** — Tatu Ylönen. CC BY-SA 4.0 or GFDL.

> The Coptic Scriptorium maintainers **lost their NEH funding in 2025** and are
> still maintaining the corpus, the NLP pipeline and the OCR that this entire site
> depends on. We are in their debt.

Full list: **[/licences/](licences.md)** (machine-generated, complete).
People: **[/credits/](credits.md)** (hand-written).

If your work is here and the attribution is wrong, tell us and we will fix it.

---

## Session 22 status

**You can hear yourself, carry the drills into Anki, and the guard can
tell a comment from a rendering bug.**

- The AST rewrite of `no_object_object_guard`: acorn parses every published
  JS file (pinned 8.19.0) and flags only what can reach a page —
  concatenations, template literals, `innerHTML`/`textContent`/
  `document.write` sinks. Comments and `!== "[object Object]"` comparisons
  pass on their merits; the third-party exception list is gone.
- `/speak/`: the top 100 lemmas ranked by corpus occurrences, three
  transliteration schemes, record-and-compare in the browser with an
  explicit no-ASR, no-score banner — nothing leaves the machine, and
  `/speak/top100.html` serves the list without JavaScript.
- `/anki/`: 300 vocabulary cards and all 2,589 cloze drills as downloadable
  `.apkg` decks generated from the same banks the site serves. Favicon
  shipped (best-practices 96 → 100); `POS_LABELS_REVIEW.md` puts eight
  corpus-evidence labels in front of a human for verdicts.

## Session 21 status

**Content claims are verified like code claims, and learners can write.**

- Rule 14 with the content audit: 156 taught pairs verified, 4 headword
  gaps declared, 1 plan divergence fixed; `GRAMMAR_CLAIMS.md` holds 21
  grammar assertions with blank verdicts, and every lesson page carries the
  unverified banner until a reviewer fills them.
- POS drills render labels, never raw tags (`pos_labels.js`, 57 tags, 7
  flagged for review); trivial form==lemma items removed (5,198 → 5,174).
- `/write/`: trace 32 letters + 3 words on canvas with lenient Good/Close/
  Try-again feedback measured from the font at runtime — no invented stroke
  order, no numeric scores. Lighthouse 99/100/96/100.

## Session 20 status

**All fifteen lessons teach, and drills ask about the annotation too.**

- Lessons 6–15 are written with the same rigor as 1–5: 200+ words each,
  every taught gloss checked against the dictionary by
  `lesson_vocab_guard.py` (which caught two of its own normalization bugs
  on first contact with real prose). Unlisted-but-real forms (ⲧⲉϥ, ⲡⲉϫⲉ,
  ⲁⲛ, ⲉⲧⲉ) are declared in front matter with reasons, never silently
  unresolvable.
- Parse drills: name a marked word's part of speech or its headword —
  2,599 of each across the six works, answers re-read from the tarball by
  `parsedrill_guard.py`, rendered on `/drill/` beside cloze.
- `public_size_guard.py` budgets the published tree (20 MB total; corpus 15,
  quiz/drill 5 each, course 500 KB) after `size_guard` caught 1.7 MB of
  stale plain CSVs (E33: gzipped per design, budget untouched).

## Session 19 status

**The course chains the banks, and every guard ships with its reproducing test.**

- `/course/` offers fifteen lessons from the alphabet to reading Ruth alone.
  Each lesson chains a reading page, a quiz filter, a drill filter, a corpus
  passage, and a checkpoint — a real ten-question session from the lesson
  band's vocabulary banks (70% unlocks the next lesson, with an override for
  advanced learners). `coursegen.py` emits the chain from lesson front
  matter; `course_guard.py` checks every filter resolves to data. Lessons
  1–5 teach with corpus-verified prose; 6–15 ship complete filters with a
  Session 20 TODO. Playwright completes lesson 1 and proves lesson 2 unlocks
  (and starts locked); Lighthouse on `/course/`: 100/100/96/86.
- **Rule 13**: a guard ships with the test that reproduces its class — the
  reader-usage guard is now AST-based (E32), with the regex as pre-filter.
- Drill blanks are lexical words only (Session 19 D1 decision): the Ruth
  sample blanked a bound clitic, so `is_blankable` is now N/NPROP/V/VSTAT/
  ADV/NUM; 2,589 items re-emitted, guard clean.

## Session 18 status

**The site teaches grammar-in-context, and every pipeline file has one reader.**

- `/drill/` offers cloze drills from real corpus verses: one content token
  removed per verse (articles, prepositions, punctuation, and bound forms stay
  visible), four attested surface forms to choose from, 2,599 items in 6
  per-work banks, browser-local scoring, and a static no-JS work list.
  `drill_guard.py` re-reads every answer from the tarball; unfair items fail
  the build.
- **Rule 12**: every file format has exactly one reader and one writer —
  shards through `shardio`, dual-form artefacts through `safeio`, browser
  fetches through `fetch_json.js` — enforced by `reader_usage_guard.py`.
- The 8 vowel-only lemmas whose Egyptological skeleton is empty by rule live
  in `tools/tests/fixtures/translit_empty_by_rule.txt`, checked both
  directions; the `static/js/translit.js` orphan diff was proven
  behavior-identical across 240 inputs and reverted.

## Session 16 status

**The learning layer now has one transliteration renderer and data-derived quizzes.**

- `static/js/translit.js` owns every structured `translit` value through
  `translitDisplay()`. The dictionary reader calls it; quiz generation calls it
  through `tools/emit/translit_probe.mjs`.
- `tools/emit/quizgen.py` emitted **959 items in 19 static banks**: 50 per band
  for five dictionary quiz types, 30 per band for dialect identification, and
  119 verse-matching items.
- `/quiz/` offers ten-question sessions, local scorekeeping, spaced repetition,
  JSON export/import, and a static no-JS topic list.
- Because the shipped shards currently have no nonempty `translit` schemes,
  transliteration prompts explicitly use source-backed Kaikki `romanization`
  forms. They are not presented as Bohairic or Sahidic scheme values.

## Session 14 status

**English search works.** It has been decorative since Session 9: Pagefind 1.5.2
drops a fixed set of English gloss terms, so `azurite` returned 9 hits and
`copper` returned 0 *in the same document*. Reported upstream with a three-word
reproduction — [PageFind/PageFind#1370](https://github.com/PageFind/PageFind/issues/1370)
— and worked around here.

```
tools/emit/english_index.py  ->  10,017 English terms, 148,546 B gz
static/js/search.js          ->  Coptic to Pagefind, Latin to the index, mixed merged
```

Live on the Session 14 preview: `copper` → **19 entries**, `ⲧⲉⲛⲟⲩ` → 1,
`ⲃ︦` → 297. Entry ids are `"<shard>-<offset>"`, the same coordinates the
dictionary index already carries, so resolving a Latin hit costs no extra request.

**Both pages are now accessibility 100.** `/dict/`'s last failure was a `<ul>`
receiving a `<p>`; the container is not a list, so it is a `<div>` now.

**Rule 10** joins Rules 1–9: a null result from a probe is not evidence until that
probe has produced a positive result on a case that should succeed. Three nulls
this session were all probe bugs — including the checklist's own cache check, which
reported 0 entries on a site serving 8.

**Production is prepared, not promoted.** `PRE_PRODUCTION_CHECKLIST.md` has an
11-commit plan and the deploy command. Nothing is committed; `master` is still
unborn.

## Session 13 status

**Deployed**: <https://session-13.coptic-reference.pages.dev> — a Cloudflare Pages
preview. The service worker registers, all 8 precached entries cache, the CSP
loads with no violations, the corpus round-trips, and `/dict/?q=ⲃ︦` finds 297
entries — including the lemma that only works because `strip_chars` ships in the
index. `POST_DEPLOY_CHECKLIST.md` has the full run.

Two data leaks closed: **9,132 of 83,017 tokens (11.0%)** carried `<lang>` markup
in `norm`, which made those words unmatchable in the dictionary; stripped at emit
and now guarded at build time, along with `verse_index`.

Lighthouse under the real CSP: `/dict/` **90 / 93 / 96 / 100**; corpus
**78 / 100 / 96 / 100** — the two accessibility failures Session 11 reported
(heading order, touch targets) are fixed.

**Pagefind's English search defect is isolated, not explained.** One record whose
content is exactly `"copper carbonate, azurite"` returns 9 hits for `azurite` and
**0** for `copper`. Six explanations are refuted by their own experiments —
co-occurrence, scale, script mixing, `weighted_ngrams`, `excerpts`, and the
language flag (identical missing set under `cop`, `en`, `fr` and default). The drop
is a property of the term inside Pagefind. Nothing in this repository can fix it.

## Session 12 status

The verse-ref defect is fixed upstream, the CSP conflict is resolved, and the
Pagefind bug is minimally reproduced but still not explained.

- **`verse_index` is the join key.** `ref` is a human-readable label and is not
  unique within a work; `verse_index` is 0..N-1 and is. Assigned by one
  enumeration so `text.json` and `tokens.json` cannot drift. `bohairic_mark`
  renders 20,322 token spans where it rendered 276,522.
- **One fetch implementation.** `static/js/fetch_json.js`, used by `reader.js`,
  `corpus.js` and `read-csv.html`. The third copy was still the pre-Session-11
  bug and would have thrown on Cloudflare.
- **`_headers` is emitted by the build**, and the Playwright suite runs under the
  real CSP. Doing so found a deploy-fatal bug: the policy blocked Pagefind's
  WebAssembly, so search would have returned nothing in production, silently.
- **The build is byte-reproducible.** Three consecutive builds, identical content
  hashes. The generator was feeding its own timestamp.
- **`pagefind` is pinned to `1.5.2`.** It was `^1.5.2`, beneath a comment claiming
  otherwise; `tools/validate/pagefind_pin_guard.py` now enforces it.

Rule 8 applies to this project's own tests, which is where two of the above were
found: a test on one sample is not a test.

## Session 11 status

Behavioural tests, Playwright for all six works, Pagefind investigation and
deploy preparation. Two defects were found by the new tests and are recorded in
`DECISIONS.md`:

- **`reader.js` assumed no `Content-Encoding: gzip`.** It inflated every
  response unconditionally, which is correct only on a host that leaves `.gz`
  files compressed. Cloudflare Pages does not, so the reader would have worked
  in every test and failed on the deploy target. Both readers now sniff the
  `1f 8b` magic bytes. `corpus.js` had it right; the reader did not.
- **Verse refs are not unique within a work.** `bohairic_mark` has 678 verses
  and 72 distinct refs, with `'1'` appearing 16 times in the text and 542 times
  among the tokens, so the reader pools tokens across every verse that shares a
  ref and shows **the wrong words**. `sahidic_ruth` (85/85 unique) is the only
  correct work. Session 10's tests passed because they only exercised Ruth.

The first is fixed. The second is diagnosed, not fixed: the join has to move
from `ref` to token position, which is an upstream data change.

**Two expected failures are documented rather than hidden:**

- Pagefind English search is partial — `azurite` 9 hits, `copper` 0 — with the
  mechanism unidentified. Strict `xfail`, so a fix shows as XPASS.
- Five of six corpus works show wrong tokens, as above. `xfail`, so a fix shows
  as XPASS.

### Deploying

`DEPLOY.md` has the Cloudflare Pages settings, the verbatim build command and the
time budget. `POST_DEPLOY_CHECKLIST.md` has the ten post-deploy checks. Neither
step has been run — nothing in this project has touched a CDN.

### Testing

| Suite | What it is |
|---|---|
| `tools/tests/test_behaviors.py` | six behavioural tests, one per Session 10 bug; each fails when its bug is reintroduced (Rule 7) |
| `tools/tests/playwright/test_sw.py` | five service-worker tests: install, precache, offline, shard, no-assumed-encoding |
| `tools/tests/playwright/test_corpus_works.py` | all six works: verse renders, token → dictionary → correct lemma |
| `tools/tests/playwright/test_pagefind.py` | real Pagefind search in a browser |

Lighthouse (Session 11): `/dict/` **91 / 93 / 96 / 100**; `/corpus/sahidic_ruth/`
**75 / 92 / 96 / 100** (performance / accessibility / best-practices / SEO).
Both accessibility scores clear 90. The corpus page's two failures are heading
order and touch-target size; reported, not tuned.

## Licence

| | |
|---|---|
| **Site code** | Apache-2.0 |
| **Content and derived data** | CC BY-SA 4.0 |
| **Some individual books** | CC BY-NC 4.0 — listed separately, kept in their own section |

You can use both, including commercially, with attribution. See
[LICENSE](LICENSE) and [NOTICE](NOTICE).

---

## Maintainer documentation

| Document | For |
|---|---|
| **[HANDOFF.md](HANDOFF.md)** | The next maintainer. The five files that matter; the five things that break first |
| **[RUNBOOK.md](RUNBOOK.md)** | On call at 11pm with a broken bake. Step-by-step, with rollbacks |
| **[ONBOARDING.md](ONBOARDING.md)** | First four weeks as a maintainer |
| **[CONTRIBUTING.md](CONTRIBUTING.md)** | Adding a source, fixing a bug, writing a lesson |
| **[CONTRIBUTING_SOURCES.md](CONTRIBUTING_SOURCES.md)** | The four gates for a new data source |
| **[GOVERNANCE.md](GOVERNANCE.md)** | Roles, decision rights, why endorsement is not a vote |
| **[AUTHORS.md](AUTHORS.md)** | Everyone, and every source |
| **[FAQ.md](FAQ.md)** | Why no MT, no TTS, no accounts, why CC BY-SA |
| **[workers/suggest/README.md](workers/suggest/README.md)** | The one runtime component |

---

<div align="center">

**A project by Michael Helmy.**
Site code Apache-2.0 · Site content CC BY-SA 4.0 · Dictionary and corpus data
compiled from CCL, CDO, Coptic Scriptorium, Universal Dependencies and
Wiktionary — [full credits](licences.md).

</div>
