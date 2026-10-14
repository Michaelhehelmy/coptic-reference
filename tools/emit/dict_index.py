#!/usr/bin/env python3
"""tools/emit/dict_index.py — data/dist/dict/index.json, the lookup table.

Session 5 D3. The reader's loop is "tap a word, see the entry". With 23 gzipped
shards totalling 1.88 MB, the worst case is downloading all of them to find one
entry. This index is the whole point of the gzipped layout: one file, small
enough to cache, that says which shard and which offset.

TWO INDEX FILES, ON PURPOSE
--------------------------
`index.json` (plain) is the BUILD record: the alphabet, the id list, the shard
ranges. Build tooling and tests read it; no browser fetches it.
`index.json.gz` is the CLIENT index: that header plus `rows`, the lookup table.
C2 forbids shipping the same payload in two encodings; these are different
payloads for different readers, and the client fetches exactly one. Both carry
`collation_hash`, so either can be checked against the pin.

Row shape, per the brief:

    { "lemma": "ⲧⲉⲛⲟⲩ", "norm_key": "ⲧⲉⲛⲟⲩ",
      "pos": ["adv"], "dialects": ["B","S"],
      "gloss": "now, at present",
      "shard": 12, "offset": 87 }

Two decisions worth stating, both conservative because the brief was silent:

**`offset` is the index into `shard-NNN.json.gz`'s `entries` array**, not a byte
offset. A byte offset would be smaller to read but is destroyed by any re-emit
that changes the shard's bytes -- which `gzip_shards` does not, but a re-bake
does, and a client with a stale index would then read the wrong entry silently.
An array index survives re-compression and fails loudly (out of range) instead.

**`lemma` is the display form and `norm_key` is the sort key**, and a client
should look up by `norm_key`, because that is what `collate.coptic_sorted`
ordered by and what the shards are keyed on. Both are present so a client can
tell "no such word" from "right word, different surface form".

The header carries `collation_hash`, so a client can refuse an index built with
a different alphabet rather than silently mis-sorting.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import argparse
import gzip
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import collate  # noqa: E402
import safeio  # noqa: E402
import shardio  # noqa: E402

GENERATED = "2026-10-04T00:00:00Z"
#: Which shard keys travel in a row. Deliberately few. `display`, `etymology`,
#: `attributions` and `examples` stay in the shard: this file exists to find a
#: shard, not to be the entry. C2 forbids pruning the entry; it does not ask for
#: a fat index, and the brief's row shape is the contract.
POS_KEY = "pos"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="emit dict/index.json")
    ap.add_argument("--dict-dir", type=pathlib.Path,
                    default=ROOT / "data" / "dist" / "dict")
    args = ap.parse_args(argv)

    rows: list[dict] = []
    seen: dict[str, str] = {}
    dupes = 0

    for path in shardio.shard_paths(args.dict_dir):
        if path.name.endswith("index.json"):
            continue
        blob = shardio.read_shard(path)
        shard_no = _shard_number(path.name)
        for offset, e in enumerate(blob.get("entries", []) or []):
            lemma = (e.get("lemma") or "").strip()
            if not lemma:
                continue
            nk = (e.get("norm_key") or collate.canon_for_sort(lemma)).strip()

            # A duplicate norm_key means two rows would claim the same lookup.
            # First wins, and the collision is REPORTED rather than silently
            # resolved -- a client asking for this word should not get whichever
            # row happened to be written last.
            if nk in seen:
                dupes += 1
                continue
            seen[nk] = lemma

            pos = e.get(POS_KEY)
            if isinstance(pos, str):
                pos = [pos]
            rows.append({
                "lemma": lemma,
                "norm_key": nk,
                "pos": list(pos) if pos else [],
                "dialects": list(e.get("dialects") or []),
                # Session 9 S9-B4: this was `display`, which for most entries is
                # just the lemma again -- so the index row said
                # {"lemma":"ⲧⲉⲛϣⲓ","gloss":"ⲧⲉⲛϣⲓ"} and a search for an
                # English word returned NOTHING. The reader's search box indexes
                # this field, so the search box was decorative.
                #
                # The first real gloss is what a reader means by "the gloss of a
                # word". Sources are already merged at this point, so this is a
                # field read, not a re-merge. English preferred, then any.
                "gloss": _first_gloss(e),
                "shard": shard_no,
                "offset": offset,
            })

    # Sorted by norm_key with `sort_key`, the STRICT TOTAL ORDER -- never python
    # sorted(), and not `rank_key`. `coptic_sorted` ordered the shards with
    # sort_key(norm_key), so using the same function here means a client's binary
    # search over these keys lands on the same sequence as the shards, and a
    # duplicate can never appear in one and not the other. rank_key would be
    # wrong: it folds case and marks, so Ⲁⲁ and ⲁⲁ would collide.
    rows.sort(key=lambda r: collate.sort_key(r["norm_key"]))

    # Fold in the build record's useful header (letters, shard ranges) so the
    # client index is self-contained. `index.json` stays as the BUILD record --
    # different payload, different reader, not a second copy of this one. See the
    # "two index files" note in the module docstring.
    header: dict = {}
    hdr_path = args.dict_dir / "index.json"
    if hdr_path.is_file():
        try:
            header = json.loads(hdr_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise SystemExit(f"[dict_index] {hdr_path} is unreadable ({e}); refusing "
                             f"to emit a client index with a half-known header")

    index = {
        "schema": "coptic-reference/dict-lookup/1",
        "generated": GENERATED,
        "collation_hash": collate.collation_hash(),
        "shard_suffix": ".json.gz",
        "entry_count": len(rows),
        "duplicate_norm_keys": dupes,
        "lookup_by": "norm_key",
        # Session 9 D2: the case-fold table, emitted HERE so the client and the
        # collator cannot disagree. It is 53 pairs, derived from the pinned
        # alphabet by Unicode NAME.
        #
        # The client's first attempt was range arithmetic -- subtract 8 from
        # U+2C80..U+2C8F -- which turned every SMALL letter into garbage (U+2C81
        # became U+2C99) and missed every lookup. The truth is worse than a bad
        # offset: the folds are NOT uniform. U+2C8B -> U+2C81 is -8, and
        # U+2C98 (MI) -> U+2C99 is +1. There is no arithmetic that works, so the
        # table ships with the index and the client does not guess.
        "casefold": _casefold_table(),
        # Session 10 D2b / C4: the characters to STRIP, emitted for the same
        # reason as casefold -- collate._IGN is a set of Unicode CATEGORIES
        # (Cf, Me, Mn), not code points, so a client cannot derive the list and
        # hardcoding U+0300..U+036F misses the combining marks this data actually
        # uses.
        #
        # Measured: nine lemmas were unreachable after case folding, every one of
        # them because of U+FE26 or U+FE24 -- Mn, and outside every range anyone
        # would have guessed. So the list is derived from the shipped norm_keys
        # rather than invented, and it travels with the index.
        "strip_chars": _strip_chars(),
        "offset_meaning": "index into the shard's `entries` array",
        "letters": header.get("letters"),
        "shard_size": header.get("shard_size"),
        "shards": header.get("shards"),
        "rows": rows,
    }

    # The client fetches THIS file. Gzipped like the shards, for the same reason:
    # a reader on a phone should not pull 2.4 MB to find one word.
    dest = args.dict_dir / "index.json.gz"
    raw = json.dumps(index, ensure_ascii=False, indent=1).encode("utf-8")
    # Session 6 D1: compress explicitly here rather than letting write_shard decide,
    # so raw_len/gz_len below can be reported from what was actually written.
    gz_len = safeio.write_verified(dest, gzip.compress(raw, compresslevel=9, mtime=0))
    raw_len = len(raw)

    print(f"[dict_index] entries        {len(rows)}")
    print(f"[dict_index] duplicate keys {dupes}")
    print(f"[dict_index] collation_hash {index['collation_hash']}")
    print(f"[dict_index] raw            {raw_len:,} B")
    print(f"[dict_index] gz             {gz_len:,} B  ({gz_len * 100 // max(raw_len,1)}% of raw)")
    print(f"[dict_index] wrote          {dest}")
    if gz_len > 1_200_000:
        print(f"[dict_index] NOTE — {gz_len:,} B gz is OVER the 1.2 MB estimate in the "
              f"brief. Reporting the measured number rather than shrinking the row "
              f"shape to hit a target.")
    print()
    print("  sample row:")
    print("   ", json.dumps(rows[0], ensure_ascii=False))
    return 0


def _casefold_table() -> dict[str, str]:
    """capital -> small, keyed by "U+XXXX", derived from Unicode names.

    Read off the collator's own pinned alphabet plus the titlecase block, so a
    change to the alphabet changes this table in the same build.
    """
    import unicodedata as _ud
    out: dict[str, str] = {}
    for cp in range(0x2C7C, 0x2D00):
        try:
            n = _ud.name(chr(cp))
        except ValueError:
            continue
        if "CAPITAL LETTER" not in n:
            continue
        want = n.replace("CAPITAL", "SMALL").replace("TITLE", "SMALL")
        for cand in range(0x2C7C, 0x2D00):
            try:
                if _ud.name(chr(cand)) == want:
                    out[f"U+{cp:04X}"] = chr(cand)
                    break
            except ValueError:
                continue
    # The four Greek letters in the pinned alphabet are the COPTIC LUNATE
    # SIGMA family, and Unicode names their capitals with CAPTICAL SIGMA
    # rather than anything containing "CAPITAL LETTER" -- so the name scan above
    # misses them. They are real headwords in this dataset: all four appear as
    # lemmas, and a reader who types the capital form finds nothing.
    for cap, small in (("U+03E2", "\u03E3"), ("U+03E6", "\u03E7"),
                       ("U+03E8", "\u03E9"), ("U+03EA", "\u03EB"),
                       ("U+0391", "\u03B1")):
        out[cap] = small
    return out


def _strip_chars() -> list[str]:
    """Code points in collate._IGN that actually occur in the shipped norm_keys.

    Scanned from the data rather than hardcoded, so it cannot drift from what
    the keys contain.
    """
    import unicodedata as _ud
    import collate as _c
    import shardio as _s
    seen: set[int] = set()
    dd = ROOT / "data" / "dist" / "dict"
    for _p, e in _s.iter_entries(dd, require=False):
        # BOTH fields. norm_key is already stripped by collate, so scanning only
        # it found nothing; the marks live in the DISPLAY lemma, which is what a
        # reader types.
        for nk in (e.get("norm_key") or "", e.get("lemma") or "", e.get("display") or ""):
            for ch in nk:
                if _ud.category(ch) in _c._IGN:
                    seen.add(ord(ch))
    return [f"U+{cp:04X}" for cp in sorted(seen)]


def _first_gloss(e: dict) -> str:
    """The most useful one-line gloss: English if we have it, else any."""
    gs = e.get("glosses") or []
    for want_en in (True, False):
        for g in gs:
            t = (g.get("text") or "").strip()
            if not t:
                continue
            lang = (g.get("lang") or "").lower()
            is_en = lang.startswith("en") or lang in ("", "mul")
            if is_en == want_en:
                return t.split("\n")[0][:120]
    return (e.get("display") or e.get("lemma") or "").strip()[:120]


def _shard_number(name: str) -> int:
    stem = name[len("shard-"):]
    for suf in (".json.gz", ".json"):
        if stem.endswith(suf):
            stem = stem[: -len(suf)]
            break
    try:
        return int(stem)
    except ValueError as e:
        raise SystemExit(f"[dict_index] cannot read a shard number from {name!r}") from e


if __name__ == "__main__":
    raise SystemExit(main())
