#!/usr/bin/env python3
"""tools/validate/public_size_guard.py — published bytes stay budgeted.

Session 20 D2. public_completeness_guard checks counts; nothing checked
size, so the published tree could grow without bound and no gate would
notice. Budgets (generous on purpose; breach means revisit the design, not
the numbers):

- public/ total: 20 MB (today 6.7 MB; Cloudflare Pages is effectively
  unbounded, but the PWA runtime cache is not — see sw_gen's 24 MiB cap);
- public/data/corpus/: 15 MB (today 1.2 MB; room for the remaining works);
- public/data/quiz/: 5 MB (today 73 KB);
- public/data/drill/: 5 MB (today 265 KB);
- public/data/course/: 500 KB (today 2 KB; the course file must stay tiny
  because it gates the whole learning path — per-item data would belong in
  the banks, and this budget is what says so).

A missing public/ is a SKIP (exit 0), not a pass: like nc_guard_public,
this guard measures the built site, and CI may run it before any build.
An over-budget directory is a FAIL naming the directory and both numbers.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "public"

BUDGETS: tuple[tuple[str, int], ...] = (
    ("", 20 * 1024 * 1024),
    ("data/corpus", 15 * 1024 * 1024),
    ("data/quiz", 5 * 1024 * 1024),
    ("data/drill", 5 * 1024 * 1024),
    ("data/course", 500 * 1024),
)


def dir_bytes(path: pathlib.Path) -> int:
    """All file bytes under path (symlinks not followed)."""
    total = 0
    for member in path.rglob("*"):
        if member.is_file() and not member.is_symlink():
            total += member.stat().st_size
    return total


def check(public_dir: pathlib.Path = PUBLIC) -> list[str]:
    """Over-budget entries as strings. Empty means within budget."""
    if not public_dir.is_dir():
        return []
    over: list[str] = []
    for rel, budget in BUDGETS:
        target = public_dir if not rel else public_dir / rel
        if not target.is_dir():
            continue
        actual = dir_bytes(target)
        if actual > budget:
            over.append(f"{rel or '.'}: {actual:,} B exceeds "
                        f"{budget:,} B ({actual / budget:.0%})")
    return over


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="published bytes stay budgeted")
    ap.parse_args(argv)
    if not PUBLIC.is_dir():
        print("[public_size_guard] SKIP — no public/; build first")
        return 0
    over = check()
    if over:
        print("[public_size_guard] FAIL — over budget:", file=sys.stderr)
        for line in over:
            print(f"  - {line}", file=sys.stderr)
        return 1
    total = dir_bytes(PUBLIC)
    print(f"[public_size_guard] OK — public/ {total:,} B; "
          f"{len(BUDGETS)} budget(s) met")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
