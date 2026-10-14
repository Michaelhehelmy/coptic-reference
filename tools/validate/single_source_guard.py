#!/usr/bin/env python3
"""tools/validate/single_source_guard.py — one licence manifest, one spelling.

Session 7 C2. This guard exists because of Session 6's S6-B1, where the emitter
wrote `LICENCES.csv` (no S) while every reader used `LICENSES.csv`. Two licence
manifests existed and **the generated one was never the file any guard
validated** — so `licence_guard` had been reporting "OK, 19 rows" about a stale
copy while the pipeline regenerated something else. It then downgraded
`Manley2019` from `CC-BY-NC-4.0` to `UNVERIFIED`, losing a licence we knew.

Two failure modes are caught:

  1. a **banned** variant exists on disk at all (`LICENCES.csv`);
  2. a **banned** spelling appears in any tracked source file.

The second is the one that matters. A banned filename sitting in a pull request is
a warning; a banned string literal in the emitter is the bug itself, and it
compiles, runs, and passes every other guard.

The deny list is a list, not a clever check, because the failure was a one-letter
difference and cleverness is how you end up allowing `LICENSCES.csv`.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]

#: The one correct name, per v4 §7.1 and every existing reader.
CANONICAL = "LICENSES.csv"

#: Banned anywhere: on disk, or inside a tracked source file. Session 7 C2 says
#: the list starts with `LICENCES.csv`; the others are the same class of typo and
#: are cheap to prevent now rather than expensively later.
DENY_NAMES: frozenset[str] = frozenset({
    "LICENCES.csv",      # Session 6 S6-B1: the bug this guard was written for
    "LICENCE.csv",
    "LICENCSE.csv",
    "LICENSE.csv",       # American spelling: ambiguous with the repo's own licence
})

#: Directories scanned for banned spellings in source. `sources/` is excluded: it
#: holds third-party data that may legitimately contain the word "licence".
SOURCE_DIRS = ("tools", "schema", "themes", "static", ".github")
SOURCE_SUFFIXES = frozenset({".py", ".md", ".yaml", ".yml", ".json", ".toml",
                             ".html", ".css", ".mjs", ".sh"})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="one licence manifest, one spelling")
    ap.add_argument("--root", type=pathlib.Path, default=ROOT)
    ap.add_argument("--dist", type=pathlib.Path, default=ROOT / "data" / "dist")
    args = ap.parse_args(argv)

    errors: list[str] = []

    # 1. banned FILES on disk. The roots overlap (provenance/ is under dist/),
    # so each file is reported once.
    seen_files: set[pathlib.Path] = set()
    for base in (args.dist, args.root / "public"):
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if not p.is_file() or p.name not in DENY_NAMES:
                continue
            if p.resolve() in seen_files:
                continue
            seen_files.add(p.resolve())
            if True:
                errors.append(
                    f"{p.relative_to(args.root)}: banned filename {p.name!r}. The "
                    f"canonical name is {CANONICAL}. Two manifests drift; delete "
                    f"this one and regenerate with tools/emit/cli.py.")

    # 2. banned SPELLINGS in source. This is the one that catches the bug.
    scanned = 0
    for d in SOURCE_DIRS:
        base = args.root / d
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if not p.is_file() or p.suffix not in SOURCE_SUFFIXES:
                continue
            if "__pycache__" in p.parts:
                continue
            # This file necessarily contains the banned spellings -- it is the
            # deny list. Skipping it is the only way to keep the list literal and
            # reviewable in a diff, which matters more than a self-match.
            if p.resolve() == pathlib.Path(__file__).resolve():
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            scanned += 1
            for banned in sorted(DENY_NAMES):
                if banned in text:
                    for i, line in enumerate(text.splitlines(), 1):
                        if banned in line:
                            errors.append(
                                f"{p.relative_to(args.root)}:{i}: contains the "
                                f"banned spelling {banned!r}. The canonical name is "
                                f"{CANONICAL}. This is the Session 6 S6-B1 bug: the "
                                f"emitter wrote a file no guard read.")
                            break

    if errors:
        print(f"[single_source_guard] FAIL — {len(errors)} problem(s):",
              file=sys.stderr)
        for e in errors[:20]:
            print(f"  - {e}", file=sys.stderr)
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more", file=sys.stderr)
        return 1

    # Session 7 C4: shipped as .csv.gz. Resolve both forms, or this guard fails on
    # a perfectly correct tree.
    lic = args.dist / "provenance" / CANONICAL
    if not lic.is_file() and not (args.dist / "provenance" / (CANONICAL + ".gz")).is_file():
        print(f"[single_source_guard] FAIL — {CANONICAL} does not exist under "
              f"{args.dist / 'provenance'} (nor its .gz). There must be exactly "
              f"one licence manifest and it must exist.", file=sys.stderr)
        return 1
    lic = lic if lic.is_file() else args.dist / "provenance" / (CANONICAL + ".gz")
    print(f"[single_source_guard] OK — one licence manifest "
          f"({lic.relative_to(args.root)}, {lic.stat().st_size:,} B); "
          f"{len(DENY_NAMES)} banned spelling(s) absent from disk and from "
          f"{scanned} source file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
