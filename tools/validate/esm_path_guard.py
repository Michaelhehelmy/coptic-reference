#!/usr/bin/env python3
"""tools/validate/esm_path_guard.py — no bare `import.meta.url` in path building.

Session 10 C5. One line of lint, and it exists because Session 9 lost a build to
this exact mistake.

`new URL(import.meta.url).pathname` returns a **percent-encoded** path. This
repository lives at `.../small proj/coptic`, so every path built from it became
`.../small%20proj/coptic/...` and pointed at nothing. `pagefind_index.mjs` failed
with "public/ does not exist" while `public/` plainly existed, and the error
pointed at the wrong file entirely.

It is silent on any checkout without a space in its path — which is why it
survived review and only surfaced when I happened to be working in a directory
with one. Two Node scripts had it; both would have broken on a Windows
checkout.

The correct call is `fileURLToPath(import.meta.url)`, which decodes.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
BARE = re.compile(r"\.pathname\b")
FURL = "fileURLToPath"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="no bare import.meta.url pathname")
    ap.add_argument("--root", type=pathlib.Path, default=ROOT / "tools")
    args = ap.parse_args(argv)

    bad: list[str] = []
    scanned = 0
    for p in sorted(args.root.rglob("*")):
        if not p.is_file() or p.suffix not in (".mjs", ".js"):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        scanned += 1
        for i, line in enumerate(text.splitlines(), 1):
            if "import.meta.url" not in line:
                continue
            if FURL not in line and BARE.search(line):
                bad.append(f"{p.relative_to(ROOT)}:{i}: {line.strip()[:96]}")
            elif FURL not in line:
                bad.append(f"{p.relative_to(ROOT)}:{i}: import.meta.url used without "
                           f"fileURLToPath: {line.strip()[:80]}")

    if bad:
        print(f"[esm_path_guard] FAIL — {len(bad)} bare import.meta.url use(s):",
              file=sys.stderr)
        for b in bad:
            print(f"  - {b}", file=sys.stderr)
        print("\n  Use fileURLToPath(import.meta.url). `.pathname` is "
              "percent-encoded, so any\n  checkout whose path contains a space (or "
              "any other reserved character) silently\n  resolves to nothing. Session "
              "9 lost a build to this.", file=sys.stderr)
        return 1

    print(f"[esm_path_guard] OK — {scanned} JS module(s) scanned; every "
          f"import.meta.url goes through fileURLToPath")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
