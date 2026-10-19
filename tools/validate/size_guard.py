#!/usr/bin/env python3
"""tools/validate/size_guard.py — the offline budget, enforced rather than observed.

Session 6 D4. Session 5 brought `data/dist` from 35.52 MiB to 4.05 MiB and then
*reported* that number. Reporting is not enforcing: nothing would have failed had
it been 6 MiB, and the number is the kind of thing that creeps upward one
harmless-looking field at a time.

Four budgets, each with the reason it is the number it is:

  data/dist       < 6 MB    the whole offline dictionary, the thing this budget exists for
  public/         < 20 MB   everything the browser downloads
  each shard      < 200 kB  so a client fetching ONE entry pulls one small file
  index.json.gz   < 500 kB  the lookup table, cached whole, so it wants to be small

Measured now: data/dist 5.29 MB, public 12.35 MB, largest shard 172 KB,
index.json.gz 281 KB. The data/dist ceiling was 5 MB from Session 6, when the
tree measured 4.05 MB; Session 25 raised it to 6 MB after adding the seventh
corpus work (shenoute_eagerness: corpus.tar.gz 1.24 -> 1.47 MB, plus its
corpus_refs in the shards) took the tree to 5.29 MB. That is exactly the
distinction the docstring draws: this is the budget against CREEP, and a whole
reviewed work is not creep — but the raise is a human decision recorded here so
the next 0.24 MB of creep has to argue against a written number, not a silent
one. The shard and index budgets have ~1.2x and ~1.8x headroom.

`--report` prints the numbers without enforcing, for a status update.
`--blame` names the largest contributors, which is what you want when it fails
and you need to know why.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]

BUDGETS: dict[str, int] = {
    # Session 25 D1: 5 MB -> 6 MB, justified in the module docstring. Raise
    # only with a written reason, never to make a red run green.
    "data/dist":        6 * 1024 * 1024,
    "public":          20 * 1024 * 1024,
    "shard_each":      200 * 1024,
    "index_json_gz":   500 * 1024,
}


def tree_size(p: pathlib.Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.is_dir() else 0


def human(n: int) -> str:
    return f"{n:,} B ({n / 1048576:.2f} MiB)"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="offline size budgets")
    ap.add_argument("--dist", type=pathlib.Path, default=ROOT / "data" / "dist")
    ap.add_argument("--public", type=pathlib.Path, default=ROOT / "public")
    ap.add_argument("--report", action="store_true", help="print, do not fail")
    ap.add_argument("--blame", action="store_true", help="list the largest files")
    args = ap.parse_args(argv)

    dict_dir = args.dist / "dict"
    shards = sorted(dict_dir.glob("shard-*.json.gz"))
    index = dict_dir / "index.json.gz"

    dist_total = tree_size(args.dist)
    public_total = tree_size(args.public)
    biggest = max((p.stat().st_size for p in shards), default=0)
    biggest_name = max(shards, key=lambda p: p.stat().st_size).name if shards else "-"
    index_size = index.stat().st_size if index.is_file() else 0

    rows = [
        ("data/dist", dist_total, BUDGETS["data/dist"]),
        ("public/", public_total, BUDGETS["public"]),
        (f"largest shard ({biggest_name})", biggest, BUDGETS["shard_each"]),
        ("dict/index.json.gz", index_size, BUDGETS["index_json_gz"]),
    ]

    print("[size_guard] offline budget")
    print(f"  {'what':38s} {'actual':>20s} {'budget':>14s}  {'used':>6s}")
    print(f"  {'-'*38} {'-'*20} {'-'*14}  {'-'*6}")
    over: list[str] = []
    for name, actual, budget in rows:
        pct = actual * 100 // max(budget, 1)
        flag = ""
        if actual > budget:
            flag = "  OVER"
            over.append(f"{name}: {human(actual)} exceeds {human(budget)}")
        print(f"  {name:38s} {human(actual):>20s} {human(budget):>14s}  {pct:4d}%{flag}")
    print()

    if args.blame:
        print("  largest files under data/dist:")
        files = sorted((f for f in args.dist.rglob("*") if f.is_file()),
                       key=lambda f: f.stat().st_size, reverse=True)
        for f in files[:8]:
            print(f"    {f.stat().st_size:12,d} B  {f.relative_to(args.dist)}")
        print()

    if args.report:
        print("[size_guard] --report: not enforcing.")
        return 0
    if over:
        print("[size_guard] FAIL — over budget:", file=sys.stderr)
        for o in over:
            print(f"  - {o}", file=sys.stderr)
        print("\n  Re-run with --blame to see the largest contributors.", file=sys.stderr)
        return 1
    print("[size_guard] OK — all four budgets met.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
