#!/usr/bin/env python3
"""tools/emit/english_index.py — a static English -> entry-id index.

LICENCE: project code, Apache-2.0.

Session 14 D2 / C3. **English search has been decorative since Session 9.**
Pagefind 1.5.2 silently drops a fixed set of English terms from its index —
`copper`, `carbonate`, `coin`, `rust`, `fire`, `green` — while indexing their
neighbours in the same document (`azurite`, `money`, `ore`, `bronze`). The defect
is in Pagefind; the minimal reproduction is in `docs/PAGEFIND-BUG.md` and filed
upstream as PageFind/PageFind#1370.

This is the workaround, and it does not wait for upstream.

Why a static index rather than a fix in `pagefind_index.mjs`: the terms are
dropped by Pagefind's writer, so there is nothing to configure around it. What we
control is the data we publish. A 30 KB inverted index of English gloss terms
costs nothing at build time, ships gzipped, and is served from the same origin as
everything else — no runtime dependency, no server, no account (invariants 1–4).

Shape:
    {"terms": {"copper": ["12-451", "16-88"], ...},
     "version": "<corpus/index pin>",
     "generated_from": "..."}

Entry ids are `"<shard>-<offset>"`, which is exactly what the dictionary index
already carries, so the browser resolves an id to a lemma with the index it has
already fetched. No second lookup table ships.

Terms come from the SAME gloss text `pagefind_index.mjs` feeds Pagefind, so the two
search paths cannot disagree about what an entry says.
"""
from __future__ import annotations

import gzip
import json
import pathlib
import re
import sys
import unicodedata

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import safeio  # noqa: E402
import shardio  # noqa: E402

DICT = ROOT / "data" / "dist" / "dict"
# Emitters write to data/dist; the BUILD publishes into public/ (Rule 5). The
# first version wrote straight into public/ and public_provenance_guard.py
# correctly called it an orphan — which was the guard doing its job and this
# file being on the wrong side of the rule.
DEST = ROOT / "data" / "dist" / "search" / "english_index.json.gz"

# Small, closed-class English stopword list. Kept explicit rather than derived:
# this project's words ARE the content, and a large stoplist would quietly drop
# a legitimate gloss word like "no" or "all". Rule: a concept has one file.
STOPWORDS = frozenset("""
a an and are as at be but by can for from has have he her his i if in into is it
its me my no not of on or our out she so than that the their them then there
these they this to too up us was we were what when where which who will with
would you your
""".split())

# A term is a run of letters, optionally with internal apostrophes/hyphens, so
# "copper-seller" and "assaarion's" both survive, and "1/16th" does not become
# two garbage terms.
WORD = re.compile(r"[A-Za-z][A-Za-z'\-]*")


def norm_term(w: str) -> str:
    """Lowercase, NFKD, strip accents, drop apostrophes at the edges.

    `linguae` and `linguae` must be one term. So must `coppersmith` written with a
    combining acute: the corpus is inconsistent about diacritics and a reader
    typing without them must still hit.
    """
    w = unicodedata.normalize("NFKD", w.strip().lower())
    w = "".join(c for c in w if not unicodedata.combining(c))
    return w.strip("-'")


def terms_from_glosses(glosses: list[str]) -> set[str]:
    out: set[str] = set()
    for g in glosses or []:
        for raw in WORD.findall(g or ""):
            t = norm_term(raw)
            if len(t) < 2 or t in STOPWORDS:
                continue
            out.add(t)
    return out


def main(public: pathlib.Path | None = None) -> int:
    pub = public or (ROOT / "public")
    if not DICT.is_dir():
        print(f"[english_index] FAIL — {DICT} missing; run dict_index.py first",
              file=sys.stderr)
        return 1

    index: dict[str, list[str]] = {}
    n_entries = n_terms = 0
    # shardio.iter_entries() does not yield offsets, and the entry id IS the
    # offset, so enumerate here over shardio's own read_shard rather than
    # re-implementing shard discovery. One concept, one file.
    for shard_path in shardio.shard_paths(DICT):
        blob = shardio.read_shard(shard_path, strict=False)
        if blob is None:
            continue
        shard_no = int(re.sub(r"[^0-9]", "", shard_path.stem))
        for offset, entry in enumerate(blob.get("entries", []) or []):
            if not isinstance(entry, dict):
                continue
            glosses = [g.get("text", "") for g in (entry.get("glosses") or [])]
            # The shard entry carries the full gloss list; index.json only carries
            # the first, which would index a fraction of the English.
            if not glosses and entry.get("gloss"):
                glosses = [entry["gloss"]]
            terms = terms_from_glosses(glosses)
            if not terms:
                continue
            n_entries += 1
            for t in terms:
                index.setdefault(t, []).append(f"{shard_no}-{offset}")

    for t in index:
        index[t].sort()
    n_terms = len(index)
    if not index:
        print("[english_index] FAIL — no English terms extracted; refusing to "
              "write an empty index, which would look like a working search that "
              "finds nothing", file=sys.stderr)
        return 1

    # Version = a pin on the inputs, so the browser can tell whether a cached
    # index matches the dictionary it is querying against.
    idx_path = DICT / "index.json.gz"
    version = ""
    if idx_path.is_file():
        import hashlib
        version = hashlib.sha256(idx_path.read_bytes()).hexdigest()[:16]

    doc = {
        "terms": index,
        "version": version,
        "generated_from": "data/dist/dict/shard-*.json.gz (glosses[])",
        "entry_id": "<shard>-<offset>",
    }
    raw = json.dumps(doc, ensure_ascii=False, sort_keys=True).encode("utf-8")
    DEST.parent.mkdir(parents=True, exist_ok=True)
    safeio.write_verified(DEST, gzip.compress(raw, 9, mtime=0))

    gz = DEST.stat().st_size
    print(f"[english_index] {n_entries:,} entries -> {n_terms:,} distinct English "
          f"terms; {len(raw):,} B raw, {gz:,} B gz "
          f"({gz/len(raw)*100:.0f}%) -> {DEST.relative_to(ROOT)}")
    for probe in ("copper", "azurite", "carbonate", "hammerscale", "coptic"):
        n = len(index.get(probe, []))
        print(f"           {probe:14} -> {n} entr{'y' if n == 1 else 'ies'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())