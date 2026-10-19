# Contributing to the Coptic Reference

**Everything here can be done without a GitHub account.** You do not need one to
tell us something is wrong, and you never will.

---

## 1. Found a mistake?

**This is the most useful thing you can do**, and it is how this project is
going to be right rather than merely published.

Coptic is read every week in churches across Egypt, the Sudan, and the diaspora,
and almost all of it has been digitised by a very small number of people. If you
read a text here and thought *"that is not what this word means,"* **you are the
expert and we are not.** Tell us.

### How

Every dictionary entry, corpus work and lesson has a **"Something wrong? Please
tell us"** panel at the bottom. Open it and either:

- **type into the form** if JavaScript is on — no account, no email, no captcha;
  or
- **click the email link** — it opens your mail app with everything already
  filled in. Edit and send.

The email route is not a fallback for people who got unlucky. It is a normal
supported path, and for many people it is the better one.

Either way you will get back a link, and you can watch your suggestion move
through triage.

### What helps most

**A citation turns a suggestion into a change.** CCL, CDO, Crum, or a published
grammar — any of them. You do not need one to submit. Most accepted changes
arrive with one.

### What happens next, and how long

| Stage | Who | Target |
|---|---|---|
| Read and labelled | A volunteer steward | **7 days** |
| Technical or theological verdict | A Coptic linguist or priest | **30 days** |
| Decision | The maintainer | January and July windows |
| Implementation | The maintainer | Within 12 months of acceptance, or a public reason why not |

All of this is spelled out in [GOVERNANCE.md](GOVERNANCE.md) and on
[/roadmap/](roadmap.md).

### One thing endorsements are not

**An endorsement is not a vote.** A suggestion with a hundred thumbs-up and no
scholarly support does not override a Coptic linguist. A suggestion with three
endorsements and a citation to CCL is taken seriously regardless.

We say this plainly because we would rather you knew how decisions get made here
than wonder about it.

### What actually happens to a suggestion

Not everything gets implemented, and some things should not. We publish what we
decline and why, on [/roadmap/](roadmap.md), because a silent "no" is more
discouraging than an explained one.

---

## 2. Adding a data source

**Read [CONTRIBUTING_SOURCES.md](CONTRIBUTING_SOURCES.md) first.** It is the
same procedure with more detail, and it is short.

The short version: a new source must pass **four gates**, and all four are
checked by CI.

```bash
# 1. pin it
$EDITOR tools/sources.lock
# 2. licence verdict — no "UNKNOWN", no "open access"
# 3. allowlist
$EDITOR tools/validate/nc_guard.py
# 4. a second person reads the diff
make -C tools all && git diff data/dist/provenance/
```

**If you cannot determine a source's licence, link to it — do not mirror it.**

---

## 3. Fixing a bug

```bash
# 1. is it already known?
gh issue list --label suggestion --label kind/bug --search "in:title"

# 2. if not, file it through the form on any page (no account needed)
#    or:
gh issue create --title "[bug] <what>" --body "..." --label suggestion,kind/bug,status/new

# 3. fix it, and add a test that would have caught it
# 4. make -C tools all && git diff data/dist/provenance/records.csv
```

**Add a test.** Every bug we have fixed in the collation and the parser came
from a missing test, and every one of them would have been caught by one. See
the comments at the top of `tools/collate.py` — they record four such bugs.

---

## 4. Writing a lesson

Lessons are CC BY-SA and live in `content/lessons/`. Each one needs:

- **5–10 deep links into corpus works.** A grammar page that does not point at
  real text is an essay, not a lesson.
- **≥ 1 grammar reference**, cited.
- **Dialect noted.** Sahidic and Bohairic differ in ways that will confuse a
  beginner who is not told.
- **Expert review before publication.** Unreviewed grammar is worse than none.

Twenty lessons exist now. **We add five a month**, chosen from what
suggestions and readers ask for. See [ONBOARDING.md](ONBOARDING.md) week 4 for
what writing one actually costs.

**Do not copy from CC BY-NC material.** The Manley textbook is CC BY-NC 4.0: we
link to it and cite it, we do not reproduce it. `nc_guard.py` enforces this.

### Writing lessons in Obsidian

`content/` **is** an Obsidian vault. There is no conversion step, no plugin, and
no pipeline difference — the same `.md` file you write in Obsidian is the file
you commit and the file the site builds.

- **File → Open folder as vault** → choose `<repo>/content/`. That is all.
- Write in Markdown, save, `git add content/lessons/`, open a PR. Done.
- Links between lessons are ordinary relative Markdown links; Obsidian resolves
  them locally and Hugo resolves them on the site.
- **Fonts:** the site's Coptic subset is planned for `static/fonts/*.woff2`
  (OFL, subset to the 22 letters in `tools/collate.py`). **It is not built yet.**
  Until it is, Obsidian will fall back to any system font with Coptic coverage —
  on Linux that usually means installing `fonts-noto-core` or GNU FreeFont. The
  vault download bundles the subset once it exists.

### The downloadable vault

Readers can take the whole reference away as an [Obsidian] vault:
**[/downloads/coptic-reference-vault.zip](/downloads/coptic-reference-vault.zip)**
(built by `python3 tools/emit/obsidian.py`, landing in
`public/downloads/coptic-reference-vault.zip`).

It is the same content as the site, re-shaped for a filesystem: one file per
Coptic letter, one per corpus work, the lessons, and `99 Meta/` with licences
and credits. **Coptic stays text** — no images, no SVG — so it is greppable and
screen-reader friendly. The bundled `.obsidian/` config sets fonts only and
enables **no plugins**; the build asserts the archive stays under 200 files and
under 25 MiB, and fails if any NC source reaches it.

Note the archive is a build artefact: `public/` is gitignored, so it is
regenerated rather than committed.

---

## 5. Transliteration and the keyboard

**Keyman layouts**, MIT-licensed, by Michael Everson:

- `coptic_greek` — for people who read some Greek
- `coptic_qwerty` — for everyone else

Both install on Windows, macOS, Linux, web, iOS and Android. See
[keyman.com/keyboards/coptic_greek](https://keyman.com/keyboards/coptic_greek).

The site also embeds a web keyboard. If it is wrong, awkward, or missing the
diacritics you need, **tell us** — that is a bug and a legitimate one.

---

## 6. Transcribing

For **printed editions** and **manuscripts**: eScriptorium, which the Coptic
Scriptorium team maintains specifically for this.

Manuscript transcription is genuinely hard and **we are not claiming to automate
it.** Coptic manuscripts are layered, overwritten, abbreviated, and code-switched;
a machine transcribing one reliably is a research problem, not a feature. If you
want to help, hand-transcribe in eScriptorium and a model will get better at the
*printed* pages as a side effect.

---

## 7. Reporting a licence problem

**See [RUNBOOK.md](RUNBOOK.md) §4.**

Short version for contributors: if you believe something here is mislicensed,
tell us. **We will take it down first and argue afterwards.** We would rather
remove something we love than defend something we should not have. We respond
within 7 days, and we record every takedown in `/licences/takedowns.md` whether
or not it turns out to be justified.

---

## 8. For developers

```bash
make -C tools all          # fetch → parse → merge → emit → validate
hugo --gc --minify
node tools/emit/pagefind_index.mjs     # ONE pass. not two.
npx serve public -l 3000
```

**Read [HANDOFF.md](HANDOFF.md) §3 before changing anything.** It names the five
files that matter and the five things that break first.

### The rules that are not negotiable

- **Do not add AI or ML**, at runtime or at build time. The corpus already
  carries parse data; a model in the build is a reproducibility and licence
  liability.
- **Do not link GPL-licensed code into this tree.** `cs_ocr` and the remnqymi
  pipeline stay behind a subprocess.
- **Do not add an NC source to `data/dist/`.**
- **Do not regenerate all 11.5K dictionary entries as HTML pages.** It eats 58%
  of the Cloudflare Pages file budget.
- **Do not make the Worker load-bearing for reading.** If it is removed, reading
  must be unaffected.
- **Do not disable a CI gate** to make a build pass. You are removing a safety
  net, not fixing a bug.
- **Do not require an account** to submit anything.

---

## What gets gzipped, and what does not

Decided in Session 5 D2/D5. Recorded here because it is a property of the *build*,
and a contributor adding an artefact needs to know which bucket it lands in.

**Gzipped on disk** — text that a browser fetches and must decompress with
`DecompressionStream('gzip')`:

| Artefact | Form | Why |
|---|---|---|
| `data/dist/dict/shard-NNN.json.gz` | gz | 33.68 MiB → 1.88 MiB, **18.6x**. The client fetches one shard, not all 23. |
| `data/dist/dict/index.json.gz` | gz | 2.42 MiB → 184 KB. A lookup table meant to be cached whole. |
| `public/data/corpus/<slug>/*.json.gz` | gz | already gzipped in Session 4 D3 |
| `content/lessons/**` | gz **when it exists** | `content/lessons/` is currently **empty**. The pipeline handles it anyway: lessons are static markdown, and the same reader applies. Nothing special is needed when they land — but note they are *prose*, so expect ~4x, not 18x. |
| vault payload (`public/downloads/*.zip`) | **already a zip** | no change. A zip is already compressed; wrapping it in gzip saves ~1% and costs the reader a second decompressor. |

**Not gzipped**, on purpose:

- **Fonts** (`.woff2`, `.ttf`, `.otf`) — already compressed formats. Gzipping
  compressed data makes it larger, and it costs CPU on every page load.
- **Images** (`.png`, `.jpg`, `.webp`, `.svg`) — same reason. `.svg` is the
  exception worth noting: it *is* text, so a plain `.svg` compresses well. It is
  left alone because Cloudflare already compresses text responses at the edge, and
  a `.svg.gz` on disk would need the same client-side decompression as the shards
  for no gain on a file that is usually a few kB.
- **PDF, `.mp3`, `.mp4`, `.epub`** — already compressed.
- **`index.json`** (the plain one) — this is the *build record*, read by tooling and
  tests, never fetched by a browser. Its gzipped twin `index.json.gz` is the client
  artefact. Different payloads for different readers, not two copies of one thing.
- **`records.csv`, `LICENSES.csv`** — small, downloaded rarely, and uncompressed
  form is far more useful in a terminal, a spreadsheet, and a text editor than a
  `.gz` a human has to remember how to open.

**The rule, if you add an artefact:** gzip it if a browser fetches it repeatedly
and it is text over about 20 kB. Do not gzip it if it is already a compressed
format, if a human is likely to open it directly, or if it is fetched once.

**How a client fetches a gzipped file:**

```js
const resp = await fetch("data/dist/dict/shard-012.json.gz");
const json = await new Response(
  resp.body.pipeThrough(new DecompressionStream("gzip"))).json();
```

Note we do **not** rely on `Content-Encoding: gzip`. Cloudflare Pages sets
`Content-Type` from the extension and will not attach that header to a `.gz` on
disk, so the browser would hand raw gzip bytes to `JSON.parse`. Getting the header
right would need a `_headers` rule on `/*.json`, which would then also mislabel any
uncompressed `.json` we ever serve. The decision and its rejected alternative are
recorded in `tools/emit/gzip_shards.py`.

## How to write a guard

(Session 5; mirrors `HANDOFF.md` §8a.)

Two rules, added after Session 4 shipped a corpus with no text in it and Session 5
found three guards that passed with the entire dictionary deleted. Both cost a full
session to learn, so they are rules now.

**Rule 1: A checker that generates the artefact it verifies is not a checker. If a
guard regenerates the file it checks, it will always pass. Guards must read from
disk, never write.**

`dialects_check.py` ran `tools/emit/dialects.py` and then compared the result to
the shards. It therefore compared a file it had just written against the data that
had just written it — always true. It passed a `dialects.json` with
`no_dialect_recorded: 0`, which is precisely the dishonesty Q4 exists to prevent.
Generating the artefact is a *build* step. Verifying it is a *check* step. If one
function does both, the check is theatre.

**Rule 2: A guard that measures a proxy for the thing will pass when the thing is
absent. At least one guard per artefact must measure the thing itself. Sizes,
counts, and stable fingerprints are proxies; they pass whether or not the artefact
is correct. Every guard should have a companion that measures the artefact
directly, or a written note in COVERAGE.md saying why it doesn't need one.**

The empty corpus passed everything for a whole session: the round trip (it looks up
by lemma), the occurrence counts (it counted lemmas), the file sizes (JSON keys
cost bytes whether or not the value is empty), and the fingerprints (they hashed
`meta.json`, which held counts). Every check was correct about what it measured.
Together they said the corpus was healthy while it was empty.

With the dictionary deleted, `nc_guard`, `licence_guard` and `dry_run --real` all
printed OK / PASS, because **zero entries is a perfectly valid dataset** to a loop
with no zero check. A proxy measures zero just as happily as it measures ten
thousand.

Three consequences that follow directly:

- **Zero is a failure, not a skip.** A guard that needs a dataset and finds none
  fails, unless it is explicitly told an empty tree is acceptable. Silence and
  success look identical in CI, so the guard has to say which it means. (Two
  guards still `SKIP` with exit 0 on an absent artefact — `corpus_text_guard` and
  `tarball_repro_check` — which COVERAGE.md records as an open item.)
- **Traversal lives in one place.** Rather than teaching five guards about gzip,
  `tools/shardio.py` resolves `.json` and `.json.gz` and *fails* if it finds no
  shards. Then a compressed shard cannot be missed, because no call site chooses
  how to read.
- **Read and write are symmetric.** A module that reads a format must also write
  it. `shardio` had a reader and no writer, so `corpus_refs.py` invented its own
  and wrote plain JSON into 23 files named `shard-NNN.json.gz` (S5-B2).

**Before you trust a new guard, break it.** Write the negative control first: make
the artefact wrong on purpose and confirm the guard exits non-zero. Four of the six
bugs found in Sessions 4 and 5 were found by that discipline, not by reading code
carefully. A guard with no demonstrated failure is an assumption.

`tools/validate/COVERAGE.md` is the map: for every guard, what it measures, what it
catches, **what it would pass silently**, and its companion. Consult it before
adding a guard, and update it when you add one.

**Rule 3. Every artefact write is verified by read-back. A write that reports
success is a claim; a read-back is evidence. Filesystems fail, NFS reorders,
containers unmount — none of them announce themselves. If the code can't
re-read what it wrote, the write did not happen.**

This is `tools/safeio.py::write_verified()`, and it is the ONLY way artefact
writes happen in this project: write to `path + ".tmp"`, `fsync`, `os.replace`,
then read the file back and compare. Any mismatch raises and the build stops.

Rule 3 exists because the alternative was already tried and it failed twice in
one session:

- `emit/cli.py` printed `LICENSES.csv 19 row(s)` on a write that had not landed.
- Then `is_file()` came back False for the file it was about to regenerate, so
  the "previous" licence map was empty and every `originators` / `reference` /
  `notes` value was replaced with a blank. The emitter still reported success.
  **A licence manifest that silently forgets where its sources came from is
  invariant 7 breaking in the most literal way available**, and no amount of
  correct code downstream can recover it.

I then misdiagnosed that as a broken filesystem, and "fixed" a machine that was
fine. The actual bug was a one-letter filename difference (`LICENCES.csv` vs
`LICENSES.csv`) that meant the generated manifest was never the file any guard
validated. Rule 3 would not have caught *that* either — which is why Rule 2's
companion guards read the artefact, and why `licence_guard` now reads the same
name the emitter writes.

Use it:

```python
import safeio
safeio.write_verified(dest, payload)              # bytes; compresses iff .gz
safeio.write_text_verified(dest, "text\n")        # text, utf-8
```

Never call `write_text` / `write_bytes` on a path under `data/dist/` or
`public/`. If you find yourself needing `os.replace` by hand, you want
`write_verified` instead.

**Rule 5. public/ is a build product; only the build writes to it.**

`public/` is deleted and recreated by `tools/build.py` on every build. A file
gets there by being emitted by a step that records it in
`BUILD-MANIFEST.json`, or by being copied from `static/`/`content/` by Hugo.

Never `cp` into `public/`. Session 8 is why: I hand-placed
`data/provenance/LICENSES.csv.gz` with `cp` — and that file **names the six
CC BY-NC sources it excludes**, so invariant 5 was broken by the one step in this
project with no gate in front of it. `nc_guard_public` caught it on the next run,
but only by luck of ordering. `cp` has no guard; the build does.

If you want a file published, add it to `static/` or `content/` so a generator
owns it. `tools/validate/public_provenance_guard.py` fails the build on any file
nobody can account for, which is the mechanism that makes this rule checkable
rather than aspirational.

**Rule 6. Tests never write to files they do not own.**

A test may write into its own `tmp_path`. It may not write into the repository.
The failure mode is specific and nasty: a test that writes `sources.lock` — or
`data/dist/**`, or any pinned artefact — leaves it subtly different, every later
test and every guard sees the mutated tree, and the damage is attributed to
whatever ran next.

`tools/tests/conftest.py` asserts that `tools/sources.lock` is **byte-identical at
session teardown**, so a test that touches it fails loudly at the end of the run
rather than silently corrupting the next one. This is the same discipline as
Rule 3 on the build side: a write that reports success is a claim, and a
read-back is evidence — here the read-back is at the end of the session.

Session 8 added the negative control that proves it works: a test that writes to
the lock, run deliberately, must fail at teardown.

## 9. Code of conduct

Be accurate, be patient, and be kind to people who are learning. **Coptic is a
living liturgical language of a real community**, and this project is about
helping people learn their own heritage. Nobody here owes us patience on that
account, and a contributor whose Coptic is better than our English is still
right about Coptic.

Report concerns to the maintainer privately. Attribution and licence complaints
follow [RUNBOOK.md](RUNBOOK.md) §4.

---

*Anything here unclear? Ask. The submission form works without an account, and so
does the email link in this footer.*


## Rule 7 — behaviour over existence

A component that exists and passes every guard but does nothing is a shipped bug,
not a success. Every artefact needs a **behavioral** test: not "does it exist" but
"does it do the thing it's for". A file that loads is not a file that works.

When you add a reader surface, a generator, or a cache, the test must drive it and
assert on the effect:

```sh
# Weak — passes for a file that does nothing at all
test -f public/sw.js
grep -q corpus.js public/corpus/sahidic_ruth/index.html

# Strong — fails when the thing is broken
page.goto(base + "/dict/?q=ⲧⲉⲛⲟⲩ")
assert page.locator("#entry h2").inner_text() == "ⲧⲉⲛⲟⲩ"
```

Session 10 shipped six artefacts that passed every existence check and functioned
in none. See `tools/tests/test_behaviors.py` for the six that now guard this.


## Rule 8 — one sample is not a test

A test that passes on one sample has not tested the feature. Test with at least
two inputs that differ in a known way. If the sample you tested happened to work
for unrelated reasons, you have tested the sample, not the feature.

Before writing a test, name the property the code branches on, then vary *that*:

```sh
# Weak — the project's only server omits Content-Encoding, so this proves
# nothing about the host that sends it.
test -f public/data/dist/dict/index.json.gz

# Strong — mock both branches explicitly
mock_response(gzip_bytes)   # Content-Encoding: gzip
mock_response(plain_bytes)  # no header
assert both decode to the same JSON
```

Session 11 shipped two defects that lived entirely in a dimension where the single
sample was degenerate: a reader tested on the one work with unique refs (five
other works were broken), and a reader tested only on a host that omits
`Content-Encoding` (which the deploy target sends).


## Rule 9 — test under deployed conditions

Test under deployed conditions, not development conditions. A test that runs
against a local dev server does not prove anything about the CDN. Where the
condition cannot be reproduced locally — CSP, headers, CDN behavior, TLS —
simulate it.

```js
// Useless: http.server sends no security headers, so this passes under a
// policy that would break the page in production.
fetch("/data/dist/dict/index.json.gz")
```

```python
# Useless: asserts the file exists.
# Useful: serve the policy the CDN will actually send.
for k, v in parse_headers(PUBLIC / "_headers"):
    self.send_header(k, v)
```

Session 12 found a total, silent production failure this way. Pagefind compiles
WebAssembly in a worker, which `script-src 'self'` forbids. Search worked in every
local test and returned nothing on the deployed site for every reader — because the
dev server sent no CSP at all.


## Rule 10 — calibrate a probe before believing its null

A null result from a probe is not evidence until the probe has produced a positive
result on a case that should succeed.

```python
# Wrong: reports a defect that does not exist.
pg.goto(f"{U}/dict/?q=%E2%B3%83")     # U+2CC3, not ⲃ

# Right: let the code compute the encoding, and calibrate first.
pg.goto(f"{U}/dict/?q={urllib.parse.quote('ⲃ')}")   # -> 297 hits
```

```sh
# Wrong: the regex matches the TEMPLATE line, not the emitted array, and
# invents a discrepancy of 10 vs 8.
grep -oE '"(/[^"]+)"' public/sw.js

# Right: parse the emitted structure, and check the tool agrees.
json.loads(re.findall(r"const PRECACHE = (\[.*?\]);", src, re.S)[-1])
```

Session 13 nearly filed a false production bug report on a hand-written
percent-encoding, and nearly filed a second on a regex that matched the wrong
line. Both were 0-versus-nonzero claims from probes that had never produced a
positive result. If a probe cannot succeed on a case that should work, it has not
been tested — it has been aimed.


## Rule 11 — structured fields have exactly one renderer

Every field whose schema type is object or array has exactly one renderer, and
every template calls it. A raw structured value in a template is a bug that
produces `[object Object]`, `undefined`, or a concatenated mess. If two
templates read the same structured field independently, one of them will be
wrong.

```js
// Wrong: reads the translit *object* as if it were a string.
`<dd>${esc(e.translit)}</dd>`                    // renders "[object Object]"

// Right: the single renderer owns the schema field.
`<dd>${esc(translitDisplay(e))}</dd>`
```

Session 16 found this exact split: the dictionary reader interpolated `translit`
directly, while the Obsidian emitter read its keys one by one. Only the second
could be right, and only by accident.


## Rule 12 — every file format has exactly one reader and one writer

Every file format in the pipeline has exactly one reader and one writer. No
call site opens a file directly. A file that exists in multiple on-disk forms
has exactly one reader that resolves all forms.

In practice: shard reads/writes go through `tools/shardio.py`, every other
dual-form artefact (`index.json`, `LICENSES.csv`, `records.csv`, quiz banks)
through `tools/safeio.py` (`resolve_readable` / `read_maybe_gzip` /
`write_verified`), and every browser fetch of `data/` through
`static/js/fetch_json.js` (`FetchJson.json`). `tools/validate/reader_usage_guard.py`
fails the build on any other way to open the same bytes.

```python
# Wrong: resolves the form, then ignores the resolution (Session 17 crash).
prior = safeio.resolve_readable(old_csv)   # may be LICENSES.csv.gz ...
with prior.open(encoding="utf-8") as fh:   # ... opened as text. Boom.
    ...

# Right: the resolving reader owns both forms.
text = safeio.read_maybe_gzip(prior_csv).decode("utf-8")
```

Session 17 is the evidence: the emit crashed on gzip magic (`0x8b`) because
one call site hardcoded the plain form of a file that ships gzipped — the
mirror image of Session 5 writing plain JSON into files named `.json.gz`.
Single-form inputs (`sources/*`, `schema/*`, `tools/shipped.toml`) and test
fixtures under `tools/tests/` (which own `tmp_path` per Rule 6) are outside
the guard's scope; `tools/parse/*` and `tools/fetch/*` are the designated
ingest readers. See `COVERAGE.md` for what the guard would pass silently.


## Rule 13 — a guard ships with the test that would catch its class

A guard that closes a class needs a test that reproduces the class. Not a
clean-run test — a test that plants an instance of the class and fails if the
guard passes. This test must exist before the guard is trusted, and it must
be added to COVERAGE.md alongside the guard.

```python
# Wrong: the guard passes on the real tree. So what? A guard that cannot
# fail is decoration (this bit us in Session 18: the first version scanned
# tools/tools/, found nothing, and printed OK).
assert check() == []

# Right: plant the violation, watch the guard name the file.
planted.write_text('json.loads((d / "dict" / "index.json").read_text())')
hits = check_python_file(planted)
assert len(hits) == 1 and "index.json" in hits[0]
```

The clean run tells you the tree is clean today. Only the planted failure
tells you the guard works. Both ship together, and COVERAGE.md names the
reproducing test next to the guard it vouches for.


## A missing required input is a build failure, never a warning

Session 14 shipped a build that printed

```
[build] WARNING — data/dist/search/english_index.json.gz is absent; English gloss
       search will not work.
```

and produced a site whose English search silently did nothing. Two mistakes in
one line: the emit ran *after* the publish step, and the consequence was demoted to
a warning.

The rule this follows from is Rule 7. A missing artefact is not a diagnostic, it
is a broken site, and a warning trains everyone to ignore the output that matters.

```python
# Wrong: ships a site that quietly does not work.
if es.is_file():
    publish(es)
else:
    print("[build] WARNING — the English index is absent", file=sys.stderr)

# Right: no public/, no build.
if not es.is_file():
    print("[build] FAIL — data/dist/search/english_index.json.gz is absent; "
          "tools/emit/english_index.py must run before this step.", file=sys.stderr)
    return 1
publish(es)
```

Before writing a warning into a build, answer one question: **if this input were
missing in production, would a reader notice?** If yes, it is a failure. If the
answer is genuinely no, a warning is fine — and say in the warning why not.


## Rule 14 — content claims are verified like code claims

A claim in content is verified the same way a claim in code is. If a lesson
says ⲭⲱ means 'say', that claim is checked against the dictionary the same
way a function's return value is checked against a test. Authoring without
verification is the same as coding without tests.

Concretely: every `TOKEN (gloss)` pair you write in a lesson is checked by
`tools/validate/lesson_vocab_guard.py` — the token must resolve to a
dictionary entry, and every gloss segment must appear in that entry's
glosses. Gloss parens carry machine-readable segments only; discussion goes
outside them. Tokens without headwords (ⲡⲉϫⲉ, ⲁⲛ) are declared in front
matter `unlisted_forms` with a reason, never silently unresolvable. And
grammar assertions — anything about how the language works, as opposed to
what a word means — go in `content/GRAMMAR_CLAIMS.md` for a reviewer, with
the lesson marked `grammar_claims_verified: false` until then.


## Rule 15 — a template references data by explicit path, not by enumerating a directory

A template references data by explicit path, not by enumerating a
directory. If a template needs data/dist/dict/index.json, it reads that
file, not data/. If a build system enumerates a data root, isolate unrelated
file types from that root. A template that assumes data/ contains only small
files is a bug waiting for the first large file.

Why: Session 22's E35 — referencing site.Data in a Hugo template made Hugo
unmarshal everything under data/, including corpus.tar.gz. The tarball is
not UTF-8, unmarshalling crashed the build, and the fix was to generate the
page as a standalone static file. The failure mode was a template whose data
source had a larger scope than the template assumed. The class applies to
Hugo site.Data, Jekyll site.data, Next.js getStaticProps returning a
directory, and any templating engine with an implicit data source.

The correct shape: data/dist/dict/index.json is a file; data/dist is a
directory containing files, some of which are not data for templates. A
template that wants one file names it. A template that names a directory is
asking the build system to enumerate, and the build system will enumerate
everything.


## Rule 16 — shipped means live on the public URL and verified there

A feature is shipped when it is live on the public URL and verified there.
Preview URLs, local builds, and pushes to the repository are staging, not
shipping. A push to the repository is not a deploy; a deploy is a deploy.

Why: Session 15 shipped production via direct `wrangler pages deploy`
because there was no git remote. Sessions 16–22 built seven major features
— quizzes, drills, course, transliterator, writing, pronunciation, Anki —
pushed to origin/master, and did not deploy. If a learner loaded the public
URL between Sessions 15 and 23, they saw the Session 15 state. Every session
reported "pushed" as if that were the finish line. It was not.

The correct shape: after every session that changes user-facing behavior,
either promote to production and run the post-deploy checklist, or state
explicitly in the receipt "not deployed; the public URL is stale." Silence
on the deployment state is not the same as "shipped."

The failure mode is subtle: the code is correct, the tests pass, the push
succeeds, and the site is old. Nothing fails. The gap is invisible until
someone checks the URL.


## Rule 17 — a status code is not the existence of a route

A status code is not the existence of a route. An SPA fallback, a CDN,
or a reverse proxy can serve HTTP 200 for any path. A route exists if
and only if its response content is what only that route could produce —
the title, a marker element, a specific script include, a distinctive
string in the body, or a content-hash. A checklist that reads status
codes has verified the CDN is responding, not that the routes exist.

Why: Session 23 — coptic-reference.pages.dev's SPA fallback returned
HTTP 200 with the homepage for every path, including paths that don't
exist. Every route check that read status codes alone across Sessions
15-22 could not have distinguished a working route from a broken one.
The fix was to check titles (parse the <title> and compare) and content
markers (unique strings, script includes) rather than status codes. The
failure mode is silent: a site with zero broken links and one broken
route looks identical to a site with all routes working, if you only
check status.

The correct shape: a deploy checklist entry for a route is (status ==
200) AND (title matches expected) AND (marker element present). The
second and third conditions are the ones that prove the route.
