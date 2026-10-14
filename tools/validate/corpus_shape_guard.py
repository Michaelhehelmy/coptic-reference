#!/usr/bin/env python3
"""tools/validate/corpus_shape_guard.py — every shipped token carries the fields
the reader depends on, and nothing carries markup.

LICENCE: project code, Apache-2.0.

Session 13 D0, two guards that were missing.

**verse_index (C3).** Session 11 shipped a corpus reader that keyed its token map
on `ref`, which is not unique within a work — bohairic_mark's 678 verses share 72
refs — so it pooled tokens across verses and rendered 276,522 token spans for
20,322 tokens. Session 12 fixed that by emitting `verse_index`, but the *check*
was only in the browser tests. So a tarball produced by an older emitter would
still build, publish, and fail at read time in a reader's browser, on whichever
work happened to be loaded first.

That is the Rule 7 shape with the guard in the wrong place: a build-time
condition checked only at read time. This guard makes the build fail instead.

**No markup in norm (C2).** The TT parser keeps `<lang lang="Greek"> … </lang>`
wrappers from the source and they were emitted verbatim into `norm` — 9,132 of
83,017 tokens, 11.0%. Those normalised forms could never match the dictionary
index, so those words were unreachable, and the markup rendered in the reader's
token panel. The emitter now strips it; this guard proves it stayed stripped.

Deliberately a CHECKER, not a generator: it reads data/dist and public and never
writes them (HANDOFF.md §8a). A checker that generates the artefact it verifies
proves nothing.
"""
from __future__ import annotations

import argparse
import gzip
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _read(p: pathlib.Path):
    raw = p.read_bytes()
    return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)


def check_work(d: pathlib.Path, errors: list[str]) -> tuple[int, int]:
    slug = d.name
    text = _read(d / "text.json.gz")
    tokens = _read(d / "tokens.json.gz")
    verses = text.get("verses", [])
    toks = tokens.get("tokens", [])

    # ── verse_index present, sequential, unique ──────────────────────────────
    vidx = [v.get("verse_index") for v in verses]
    if any(x is None for x in vidx):
        n = sum(1 for x in vidx if x is None)
        errors.append(f"{slug}: {n} verse(s) have no verse_index — re-emit with "
                      f"tools/emit/corpus_tarball.py (Session 12 D1)")
    else:
        if sorted(vidx) != list(range(len(verses))):
            errors.append(f"{slug}: verse_index is not 0..{len(verses) - 1} in "
                          f"order; it must be the sequential position in the work")
        if len(set(vidx)) != len(vidx):
            errors.append(f"{slug}: verse_index is not unique "
                          f"({len(vidx)} verses, {len(set(vidx))} distinct)")

    # ── tokens carry verse_index, and it points at a real verse ─────────────
    if toks and any(t.get("verse_index") is None for t in toks):
        n = sum(1 for t in toks if t.get("verse_index") is None)
        errors.append(f"{slug}: {n}/{len(toks)} token(s) have no verse_index. The "
                      f"reader joins on it and would render the wrong words. "
                      f"Re-emit the corpus.")
    tidx = {t.get("verse_index") for t in toks}
    orphan = sorted(x for x in tidx - set(vidx) if x is not None)
    if orphan:
        errors.append(f"{slug}: {len(orphan)} token verse_index value(s) match no "
                      f"verse, e.g. {orphan[:5]}")

    # ── no parse-internal markup in norm (C2) ────────────────────────────────
    marked = [t for t in toks
              if "<" in (t.get("norm") or "") or ">" in (t.get("norm") or "")]
    if marked:
        errors.append(
            f"{slug}: {len(marked)} token(s) have '<' or '>' in norm, e.g. "
            f"{marked[0].get('norm', '')[:60]!r}. Parse-internal markup must be "
            f"stripped at emit time (tools/emit/corpus_tarball.py); such a norm "
            f"can never match the dictionary index.")

    return len(verses), len(toks)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="corpus shape: verse_index + clean norms")
    ap.add_argument("--dist", type=pathlib.Path,
                    default=ROOT / "data" / "dist" / "corpus")
    ap.add_argument("--public", type=pathlib.Path,
                    default=ROOT / "public" / "data" / "corpus")
    args = ap.parse_args(argv)

    src = args.dist
    assert src is not None
    if (src / "corpus.tar.gz").is_file():
        import tarfile
        works = {}
        with tarfile.open(src / "corpus.tar.gz", "r:gz") as tf:
            for m in tf.getmembers():
                if m.name.endswith(("tokens.json", "text.json")):
                    kind = "tokens.json" if m.name.endswith("tokens.json") else "text.json"
                    works.setdefault(m.name.split("/")[0], {})[kind] = tf.extractfile(m).read()
    else:
        works = None

    errors: list[str] = []
    checked = tv = tt = 0

    if works:
        for slug, blobs in sorted(works.items()):
            text = json.loads(gzip.decompress(blobs["text.json"])
                              if blobs["text.json"][:2] == b"\x1f\x8b" else blobs["text.json"])
            tokens = json.loads(gzip.decompress(blobs["tokens.json"])
                                if blobs["tokens.json"][:2] == b"\x1f\x8b"
                                else blobs["tokens.json"])
            verses, toks = text.get("verses", []), tokens.get("tokens", [])
            vidx = [v.get("verse_index") for v in verses]
            if any(x is None for x in vidx):
                errors.append(f"{slug}: {sum(1 for x in vidx if x is None)} verse(s) "
                              f"have no verse_index — re-emit with "
                              f"tools/emit/corpus_tarball.py (Session 12 D1)")
            elif sorted(vidx) != list(range(len(verses))):
                errors.append(f"{slug}: verse_index is not 0..{len(verses)-1} in order")
            elif len(set(vidx)) != len(vidx):
                errors.append(f"{slug}: verse_index is not unique")
            if toks and any(t.get("verse_index") is None for t in toks):
                n = sum(1 for t in toks if t.get("verse_index") is None)
                errors.append(f"{slug}: {n}/{len(toks)} token(s) have no verse_index")
            orphan = sorted({t.get("verse_index") for t in toks} - set(vidx)
                            - {None})
            if orphan:
                errors.append(f"{slug}: {len(orphan)} token verse_index value(s) "
                              f"match no verse, e.g. {orphan[:5]}")
            marked = [t for t in toks
                      if "<" in (t.get("norm") or "") or ">" in (t.get("norm") or "")]
            if marked:
                errors.append(f"{slug}: {len(marked)} token(s) have '<' or '>' in "
                              f"norm, e.g. {marked[0].get('norm','')[:60]!r}")
            checked += 1
            tv += len(verses)
            tt += len(toks)
    else:
        if not args.public.is_dir():
            print(f"[corpus_shape_guard] FAIL — neither {src/'corpus.tar.gz'} nor "
                  f"{args.public} exists", file=sys.stderr)
            return 1
        for d in sorted(p for p in args.public.iterdir() if p.is_dir()):
            v, t = check_work(d, errors)
            checked += 1
            tv += v
            tt += t

    if errors:
        print(f"[corpus_shape_guard] FAIL — {len(errors)} problem(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"[corpus_shape_guard] OK — {checked} work(s), {tv:,} verses, {tt:,} "
          f"tokens; every verse_index present, sequential and unique, every token "
          f"joins to a real verse, no norm contains markup")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())