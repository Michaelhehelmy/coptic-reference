#!/usr/bin/env python3
"""tools/validate/tarball_repro_check.py — the tarball must be byte-reproducible.

v4 §6.1 promises that the same inputs produce the same SHA-256, which is what
makes a tarball reviewable in a pull request: a reviewer sees a changed hash and
knows something changed. A promise like that has to be checked, not assumed, so
this builds twice and compares.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tool", type=pathlib.Path,
                    default=ROOT / "tools" / "emit" / "corpus_tarball.py")
    ap.add_argument("--manifest", type=pathlib.Path,
                    default=ROOT / "data" / "dist" / "corpus" / "manifest.json")
    ap.add_argument("--allow-missing", action="store_true",
                    help="skip instead of failing when no corpus is baked")
    args = ap.parse_args(argv)

    # Session 6 D0, closing a gap COVERAGE.md admitted: SKIP-with-exit-0 on an
    # absent corpus. Absence is failure -- a reproducibility check that never
    # compared anything has proved nothing.
    if not args.manifest.is_file():
        if args.allow_missing:
            print("[tarball_repro] SKIP — no baked corpus, --allow-missing given. "
                  "NOT a pass.", file=sys.stderr)
            return 0
        print(f"[tarball_repro] FAIL — {args.manifest} is absent, so there is "
              f"nothing to check for reproducibility. Run "
              f"tools/emit/corpus_tarball.py, or pass --allow-missing on a fresh "
              f"clone.", file=sys.stderr)
        return 1

    shas = []
    for _ in range(2):
        subprocess.run([sys.executable, str(args.tool), "--force"],
                       check=True, capture_output=True)
        shas.append(json.loads(args.manifest.read_text(encoding="utf-8"))["tarball_sha256"])

    a, b = shas
    if a != b:
        print(f"[tarball_repro] FAIL — run A {a}\n                   run B {b}\n"
              f"  The tarball is not reproducible, so its SHA cannot be trusted in "
              f"review. Check for a timestamp or an unsorted member leaking in.",
              file=sys.stderr)
        return 1
    print(f"[tarball_repro] OK — two independent --force builds agree: {a}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
