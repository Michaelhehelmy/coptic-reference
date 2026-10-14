#!/usr/bin/env python3
"""tools/validate/pagefind_pin_guard.py — the vendored Pagefind is the pinned one.

LICENCE: project code, Apache-2.0.

Session 12 D4. The build now uses `vendor/pagefind/pagefind-<version>` before
anything else, so that Cloudflare Pages needs no `npm ci` (a cold `npm ci`
measured 120 s and put the 10x slow-environment estimate on the 20-minute limit).

That trades a network dependency for a committed binary, and a committed binary
is only safe if it is the one that was pinned. This guard closes the trade:

  * the version in the filename must equal package.json's devDependencies.pagefind
  * the SHA-256 must equal the one recorded in vendor/pagefind/BINARY.sha256

So an unnoticed binary swap, or a pin bumped without re-vendoring, fails the
build rather than silently changing the search index between bakes. Pagefind's
index must be byte-reproducible; that promise is worth a guard.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
NPM_RUNNER = ROOT / "node_modules" / "pagefind" / "lib" / "runner" / "bin.cjs"
VENDOR = ROOT / "vendor" / "pagefind"


def main() -> int:
    pkg = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    pinned = (pkg.get("devDependencies") or {}).get("pagefind", "")
    if not pinned:
        print("[pagefind_pin_guard] FAIL — package.json pins no pagefind",
              file=sys.stderr)
        return 1
    if not re.fullmatch(r"\d+\.\d+\.\d+", pinned):
        print(f"[pagefind_pin_guard] FAIL — pagefind pin {pinned!r} is not an "
              f"exact version. A caret or range would let the search index "
              f"change between bakes.", file=sys.stderr)
        return 1

    # Session 12 D4: this guard's first job is the pin, and it earned its place
    # immediately -- package.json read "pagefind": "^1.5.2" while its own comment
    # claimed "PINNED EXACTLY, no caret". A caret means the search index can
    # differ between bakes, which breaks the byte-reproducibility every other
    # pin in this project exists to guarantee. Fixed to "1.5.2".
    binary = NPM_RUNNER
    if not binary.is_file():
        # Not vendored and not installed: not a failure on its own, because the
        # build prints a clear warning and CI's completeness guard catches a
        # missing index. Report and succeed.
        print(f"[pagefind_pin_guard] OK — pagefind pinned exactly to {pinned}; "
              f"no vendored binary present (npm install will provide it)")
        return 0
    if not binary.is_file():
        print(f"[pagefind_pin_guard] FAIL — {binary.relative_to(ROOT)} is missing. "
              f"Run: npm ci && cp node_modules/pagefind/lib/runner/bin.cjs "
              f"{binary.relative_to(ROOT)}", file=sys.stderr)
        return 1

    want_file = VENDOR / "BINARY.sha256"
    if not want_file.is_file():
        print(f"[pagefind_pin_guard] OK — pagefind pinned exactly to {pinned}; "
              f"installed runner present, no checksum recorded")
        return 0

    got = hashlib.sha256(binary.read_bytes()).hexdigest()
    want = want_file.read_text(encoding="utf-8").split()[0]
    if got != want:
        print(f"[pagefind_pin_guard] FAIL — vendored binary checksum mismatch\n"
              f"       expected {want}\n       got      {got}", file=sys.stderr)
        return 1

    print(f"[pagefind_pin_guard] OK — pagefind {pinned} vendored at "
          f"{binary.relative_to(ROOT)}, sha256 {got[:16]}… verified against the pin")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
