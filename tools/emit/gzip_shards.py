#!/usr/bin/env python3
"""tools/emit/gzip_shards.py — ship the dictionary as shard-NNN.json.gz.

Session 5 D2 / C2. The dictionary is 33.68 MiB of JSON in a project whose whole
budget is "fits on a USB stick and in a browser cache". Prose compresses ~4x;
11,369 Coptic entries with glosses, etymologies and attestations compress far
better, because the repeated keys and the boilerplate dominate.

C2 is explicit that this session does NOT prune fields. Nothing is dropped. The
bytes are just carried more cheaply, and the payload is byte-identical after
decompression -- which is checkable, and `shard_guard.py` checks it.

HOW THE CLIENT GETS THE BYTES BACK
----------------------------------
Decision: **fetch the `.gz` and decompress with `DecompressionStream('gzip')`.**

Rejected alternative: serve `shard-NNN.json` with `Content-Encoding: gzip`.
Cloudflare Pages sets `Content-Type` from the file extension and does not attach
`Content-Encoding` to a `.gz` on disk, so the browser would hand the raw gzip
bytes to `JSON.parse` and fail. Getting the header right would need a `_headers`
rule applied to `/*.json`, which would then also mislabel any uncompressed `.json`
we ever serve -- a lie baked into the config. And Cloudflare already compresses
text at the edge on the fly, so that route would shrink the *transfer* while
leaving the 33.68 MiB in the repository and in every `git clone`.

So the file on disk is `.json.gz`, and the client is one line of JavaScript:

    const r = await fetch(url);
    const text = await new Response(
        r.body.pipeThrough(new DecompressionStream('gzip'))).text();

`DecompressionStream` is baseline in every browser this project targets, it is
not a polyfillable dependency in a meaningful sense, and it costs the reading path
nothing -- no runtime, no server, no KV (invariants 1-3).

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import argparse
import gzip
import json
import pathlib
import shutil
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import shardio  # noqa: E402

SHARD_DIR = ROOT / "data" / "dist" / "dict"


def gzip_one(src: pathlib.Path, dest: pathlib.Path) -> tuple[int, int]:
    """Compress deterministically. Returns (raw_bytes, gz_bytes).

    mtime=0 and a fixed compresslevel, because a shard that gzips differently on
    two machines is a shard that shows up as a diff every time someone re-emits.
    The corpus tarball learned this in Session 4 (S4-B2); same rule, same reason.
    """
    raw = src.read_bytes()
    # level 9: the shards are re-emitted rarely and shipped often, and at 11k
    # entries the extra CPU is a few seconds against a permanently smaller repo.
    out = gzip.compress(raw, compresslevel=9, mtime=0)
    dest.write_bytes(out)
    return len(raw), len(out)


def gunzip_one(src: pathlib.Path, dest: pathlib.Path) -> None:
    dest.write_bytes(gzip.decompress(src.read_bytes()))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="gzip the dictionary shards in place")
    ap.add_argument("--dict-dir", type=pathlib.Path, default=SHARD_DIR)
    ap.add_argument("--restore", action="store_true",
                    help="gunzip back to .json (for debugging; the shipped form "
                         "is .json.gz)")
    ap.add_argument("--keep-both", action="store_true",
                    help="NOT the shipped form. C2 says serve .json.gz and do not "
                         "keep both; this exists only to show why, and shard_guard "
                         "fails if both exist.")
    args = ap.parse_args(argv)

    d = args.dict_dir
    if not d.is_dir():
        print(f"[gzip_shards] FAIL — {d} does not exist. Nothing to compress; "
              f"run tools/emit/cli.py first. Exiting non-zero rather than "
              f"reporting success on nothing.", file=sys.stderr)
        return 1

    plains = sorted(p for p in d.glob("shard-*.json"))
    gzs = sorted(p for p in d.glob("shard-*.json.gz"))

    if args.restore:
        if not gzs:
            print(f"[gzip_shards] nothing to restore in {d}", file=sys.stderr)
            return 1
        for g in gzs:
            gunzip_one(g, g.with_suffix(""))
            print(f"[gzip_shards] restored {g.name}")
        for p in plains:
            p.unlink()
        print(f"[gzip_shards] {len(gzs)} shard(s) restored to .json")
        return 0

    # Already gzipped and nothing new to do: report, do not rewrite. Rewriting
    # unchanged bytes churns mtimes and makes `git status` lie.
    if gzs and not plains:
        total_raw = total_gz = 0
        rows = []
        for g in gzs:
            raw = len(gzip.decompress(g.read_bytes()))
            rows.append((g.name, raw, g.stat().st_size))
            total_raw += raw
            total_gz += g.stat().st_size
        print(f"[gzip_shards] already gzipped: {len(gzs)} shard(s)")
        _report(rows, total_raw, total_gz, d)
        if not args.keep_both:
            return 0

    if not plains and not gzs:
        print(f"[gzip_shards] FAIL — no shards in {d}. Exiting non-zero rather "
              f"than reporting success on nothing.", file=sys.stderr)
        return 1

    rows = []
    total_raw = total_gz = 0
    for p in plains:
        dest = p.with_name(p.name + ".gz")
        raw, gz = gzip_one(p, dest)
        rows.append((p.name, raw, gz))
        total_raw += raw
        total_gz += gz
        if not args.keep_both:
            p.unlink()

    print(f"[gzip_shards] gzipped {len(rows)} shard(s) in {d}")
    _report(rows, total_raw, total_gz, d)

    if args.keep_both:
        print("[gzip_shards] --keep-both: .json files retained. This is NOT the "
              "shipped form (C2) and shard_guard.py will fail on it.")
    else:
        print(f"[gzip_shards] removed {len(rows)} uncompressed .json shard(s) — "
              f"serving .json.gz only (C2)")
    return 0


def _report(rows: list[tuple[str, int, int]], total_raw: int, total_gz: int,
            d: pathlib.Path) -> None:
    print()
    print(f"  {'shard':22s} {'raw':>12s} {'gz':>10s} {'ratio':>7s}")
    print(f"  {'-'*22} {'-'*12} {'-'*10} {'-'*7}")
    for name, raw, gz in rows:
        print(f"  {name:22s} {raw:12,d} {gz:10,d} {raw / max(gz, 1):6.2f}x")
    print(f"  {'-'*22} {'-'*12} {'-'*10} {'-'*7}")
    print(f"  {'TOTAL':22s} {total_raw:12,d} {total_gz:10,d} "
          f"{total_raw / max(total_gz, 1):6.2f}x")
    print()
    print(f"  {total_raw:,} B raw -> {total_gz:,} B gz  "
          f"(saved {total_raw - total_gz:,} B, {total_gz * 100 // max(total_raw, 1)}% of original)")
    print(f"  data/dist/dict on disk now: "
          f"{sum(f.stat().st_size for f in d.iterdir() if f.is_file()):,} B")


if __name__ == "__main__":
    raise SystemExit(main())
