# Adding a data source

**The complete procedure.** It is four gates and they are all checked by CI. If
you can pass those, you can add a source.

Read [CONTRIBUTING.md](CONTRIBUTING.md) first for the short version.

---

## The four gates

```
  1. PIN           2. LICENCE VERDICT       3. ALLOWLIST       4. DIFF REVIEW
     ↓                    ↓                      ↓                   ↓
  sources.lock      not "UNKNOWN"        ALLOWED_SOURCES     a second person
  url+sha256        not "open access"     in nc_guard.py     reads the CSVs
  bytes, date       a real licence        (fails closed)     in the PR
  DOI, citation
```

**All four or nothing.** Gate 2 is the one people try to skip, and it is the one
that ends projects.

---

## 1. Pin it

Add a block to `tools/sources.lock`:

```toml
[my-source]
url       = "https://example.org/thing.xml"
sha256    = "e3b0c44298fc1c149afbf4c8996fb924..."   # ← no placeholders
bytes     = 4812993
snapshot  = "2026-11-01"                             # the DATE you fetched it
licence   = "CC-BY-SA-4.0"
doi       = "10.1234/abc.def"
cite      = "Author, A. (2026). Title. Publisher."
```

`sha256`, `bytes` and `snapshot` are not decoration. Without them your build is
not reproducible, and "the build failed" becomes indistinguishable from "upstream
changed."

```bash
curl -sSL -o /tmp/thing.xml "https://example.org/thing.xml"
sha256sum /tmp/thing.xml
wc -c < /tmp/thing.xml
```

`fetch_all.py` verifies each pin and **hard-fails on mismatch.** That is
deliberate: a changed upstream should make a human look, not a bot shrug.

---

## 2. Get a licence verdict

> **A source ships with a machine-readable licence or it does not ship.**
> `UNKNOWN` fails the build. "Open access" is not a licence.

Work through this in order:

1. **Is there an explicit licence?** Publisher page, repository `LICENSE`,
   DOI metadata, or the works themselves.
2. **Is it public domain?** Note the **jurisdiction** and the **date**.
   "Pre-1928" is a US fact. The UK, Egypt and Germany do not all agree, and for
   2D works the Bridgeman v. Corel position does not hold everywhere. Write down
   which reasoning you used.
3. **Is it CC BY-SA?** Fine — that is our own licence.
4. **Is it CC BY-NC?** **It cannot go in `data/dist/`.** It may live in
   `content/nc/` or `static/pdf/`, linked and cited but never reproduced into
   the dataset. See gate 3.
5. **Is it dual-licensed?** Preserve both options in the notice. Kaikki is
   CC BY-SA 4.0 **or** GFDL; do not silently reduce it to CC BY-SA.
6. **Do you not know?** Then you do not have a verdict. **Link to the item, do
   not mirror it**, and ask. An unresolved licence question is worth a week of
   delay; a takedown costs the whole corpus's credibility.

### If you are unsure

Ask the reviewer register in [GOVERNANCE.md](GOVERNANCE.md) and label
`kind/licence` — that path is escalated **the same day**. It exists for exactly
this.

---

## 3. Add it to the allowlist

```python
# tools/validate/nc_guard.py
ALLOWED_SOURCES: dict[str, str] = {
    ...
    "MySource": "CC-BY-SA-4.0",   # id: licence. Add a rationale comment.
}
```

**The allowlist fails closed.** A source that is not on this list cannot reach
the merged dataset at all — so adding an entry here *is* the review act. That is
intentional: it means nobody can bring in an unchecked source by forgetting to
block it.

If your source is CC BY-NC, it goes in `NC_ONLY_SOURCES` instead. It will then be
**rejected if it appears in `data/dist`**, which is the point.

Record the verdict in `data/dist/provenance/LICENSES.csv` at the same time.
`licence_guard.py` cross-checks the two files so they cannot drift apart.

---

## 4. Write a parser, then get the diff reviewed

```python
# tools/parse/mysource.py
```

A parser must:

- **stream.** Never load the whole input into memory. Kaikki's Coptic JSONL is
  62 MB for 3,293 records; multiply that habit by a bigger file and CI will OOM.
- **raise on structural surprise, never silently skip.** A parser that skips what
  it does not understand produces a site that looks fine and is quietly wrong.
  This is the single most important rule on this page.
- **emit `record_id`, `source_record_id` and `licence`** for every record, so
  attribution can be generated downstream.
- **declare its modifications.** Anything you normalise — diacritic stripping,
  case folding, sense merging — goes into the record's `attributions[].changes`.
  CC BY-SA 4.0 §3(b) requires indicating modifications.
- **have a sanity gate.** Kaikki's parser fails if it sees fewer than 2,500
  records. Upstream schema drift should stop the build.

```bash
make -C tools all
```

Then open a PR and paste:

```bash
git diff --stat data/dist
git diff data/dist/provenance/records.csv
git diff data/dist/provenance/LICENSES.csv
```

**`corpus.tar.gz` is a binary blob and is not meaningfully diffable.** That is
why the manifest carries per-work fingerprints, counts, and licences: those
*are* the review surface for corpus changes. If a diff to `records.csv` is not
something you can read, the parser is emitting too much or the wrong thing.

---

## 5. Declare what you changed

Every record gets an `attributions[]` entry saying what happened to it:

```jsonc
{
  "field": "glosses",
  "source": "MySource",
  "licence": "CC-BY-SA-4.0",
  "changes": "diacritics stripped; case folded",
  "note": "Glosses rendered as the plain-English gloss."
}
```

`changes` uses a closed vocabulary so it can be aggregated:
`none` · `diacritics stripped` · `case folded` · `deduplicated` ·
`sense order changed` · `quality filtered` · `clitic split` · `gloss paraphrased` ·
`cross-references resolved`. Anything else goes in `note`.

**A closed vocabulary lets us report, in aggregate, how much of this dictionary
is verbatim.** That is a genuinely good thing to be able to answer.

---

## 6. Merging, when it is a dictionary

Precedence, in order — do not reorder without a linguistic reason:

```
1. lemma identity    join on norm_key (NFC + marks stripped), NOT raw orthography
2. sense data        CCL ▸ CDO ▸ Kaikki
3. dialect flags     union, never overwrite
4. etymology         Kaikki ▸ CCL
5. glosses           union, deduped, ranked by source precedence
6. examples          CDO (URN-linked) ▸ Kaikki ▸ CCL
7. frequency         CDO API ▸ our own count from _TT
```

**Never merge distinct senses.** Two sources glossing the same word the same way
are probably one sense; "ⲟⲩ he" and "ⲟⲩ how" are not, and must not collapse.
Keep senses separate unless the normalised gloss strings match.

**Never discard a lower-precedence gloss.** A scholarly terse gloss and a
learner-friendly plain-English gloss are both useful. Show both, labelled.

**Multi-word expressions must survive.** Index them as their own entries *and* as
components.

---

## Checklist before you open the PR

- [ ] Pin in `sources.lock` with a real SHA-256, byte count and snapshot date
- [ ] Licence verdict in `LICENSES.csv`, and **not** `UNKNOWN`
- [ ] Source id added to `ALLOWED_SOURCES` (or `NC_ONLY_SOURCES`)
- [ ] Parser streams, and **raises** on structural surprise
- [ ] Parser has a count sanity gate
- [ ] Every record emits `record_id`, `source_record_id`, `licence`
- [ ] Modifications declared in `attributions[].changes`
- [ ] `make -C tools validate` passes
- [ ] `records.csv` and `LICENSES.csv` diffs read by a **second person**
- [ ] `CHANGELOG.md` entry written
- [ ] `AUTHORS.md` updated with the source and its originator

**The second-person review on `LICENSES.csv` is not optional.** It is the only
place a human checks that we are not quietly shipping something we should not.
