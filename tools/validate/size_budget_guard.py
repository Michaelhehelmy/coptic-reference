#!/usr/bin/env python3
"""tools/validate/size_budget_guard.py — hard size budgets on published indices.

LICENCE: project code, Apache-2.0.

Session 15 C2. Two budgets, both enforced as build FAILURES rather than warnings:

    public/data/search/english_index.json.gz   300 KB gz
    public/data/dist/dict/index.json.gz        500 KB gz

Why these two and not everything: they are the only published artefacts that grow
with the *dataset* rather than with the code. The dictionary index is already
inside `tools/validate/size_guard.py`'s 500 KB shard budget, but that guard reads
`data/dist` — the artefact the *reader fetches* is the copy in `public/`, and a
budget on the source and not the published copy is a budget on a proxy for the
thing that ships.

The English index is newer and unchecked entirely: 10,017 terms today. It is
derived from `glosses[]`, so it grows as the corpus grows, and without a budget it
would grow until the dictionary page stopped being usable on a phone.

Rule 1 note: this guard *measures*, it never generates. The budget failing must
never be a reason the artefact got bigger.
"""
from __future__ import annotations

import argparse
import gzip
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
KIB = 1024

BUDGETS = {
    "data/search/english_index.json.gz": 300 * KIB,
    "data/dist/dict/index.json.gz": 500 * KIB,
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="published index size budgets")
    ap.add_argument("--public", type=pathlib.Path, default=ROOT / "public")
    args = ap.parse_args(argv)

    errors: list[str] = []
    rows: list[str] = []
    for rel, budget in sorted(BUDGETS.items()):
        p = args.public / rel
        if not p.is_file():
            errors.append(
                f"{rel} is ABSENT. That is a build failure, not a warning: the "
                f"reader would fetch a 404 and the page would silently not work "
                f"(CONTRIBUTING.md, 'A missing required input is a build "
                f"failure, never a warning').")
            continue
        gz = p.stat().st_size
        # Report the uncompressed size too: it is what the browser must parse.
        try:
            raw = len(gzip.decompress(p.read_bytes()))
        except OSError as e:
            errors.append(f"{rel} is not readable gzip ({e})")
            continue
        pct = gz / budget * 100
        rows.append(f"  {rel:38} {gz:>9,} B gz  ({raw:>10,} B raw)  "
                    f"{pct:5.1f}% of {budget // KIB} KB")
        if gz > budget:
            errors.append(
                f"{rel} is {gz:,} B gz, over its {budget // KIB} KB budget by "
                f"{gz - budget:,} B. Refusing to publish: the reader fetches this "
                f"on every cold visit.")

    for r in rows:
        print(r)
    if errors:
        print(f"[size_budget_guard] FAIL — {len(errors)} problem(s):",
              file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"[size_budget_guard] OK — {len(BUDGETS)} published index budget(s) met")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
