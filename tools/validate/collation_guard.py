#!/usr/bin/env python3
"""tools/validate/collation_guard.py — fail if the collation alphabet drifted.

Recomputes tools/collate.collation_hash() and compares it to the pin in
tools/tests/test_collate.py::test_collation_hash_pinned.

# LICENCE: project code, Apache-2.0.
This is the review gate for alphabet changes (v4 §1.3). Editing _ALPHA or
_GREEK in collate.py changes the hash; CI then fails until the pin is updated in
the SAME pull request. That forces an alphabet change to be deliberate and
visible in review, instead of an invisible implementation detail.

Exit 0 = the alphabet is pinned correctly.  Exit 1 = drift, or the pin is missing.

Run standalone, or from CI:
    python3 tools/validate/collation_guard.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from collate import alphabet_chars, collation_hash  # noqa: E402

#: Session 6 D0. The hash says "this is the alphabet that exists". It does NOT
#: say the alphabet has the shape we believe it has -- a hash of an alphabet with
#: two letters removed is still a perfectly consistent hash, and would pin a
#: broken alphabet just as happily. So the SHAPE is asserted separately:
#: 18 Coptic letters + 4 Greek, 22 in all.
EXPECT_COPTIC = 18
EXPECT_GREEK = 4
EXPECT_TOTAL = EXPECT_COPTIC + EXPECT_GREEK

PIN_RE = re.compile(r'assert\s+collation_hash\(\)\s*==\s*"([0-9a-f]{16})"')
TEST = ROOT / "tools" / "tests" / "test_collate.py"


def pinned() -> str | None:
    m = PIN_RE.search(TEST.read_text(encoding="utf-8"))
    return m.group(1) if m else None


def check_alphabet_shape() -> list[str]:
    """Assert 18 Coptic + 4 Greek letters. Returns problems; empty means fine.

    Kept separate from the hash on purpose. A hash pins identity; it cannot tell
    you the identity is wrong-but-consistent. Session 6 D0.
    """
    problems: list[str] = []
    chars = alphabet_chars()
    coptic = [c for c in chars if 0x2C80 <= ord(c) <= 0x2CFF]
    greek = [c for c in chars if 0x0370 <= ord(c) <= 0x03FF]
    other = [c for c in chars
             if not (0x2C80 <= ord(c) <= 0x2CFF) and not (0x0370 <= ord(c) <= 0x03FF)]
    if len(coptic) != EXPECT_COPTIC:
        problems.append(
            f"expected {EXPECT_COPTIC} Coptic letters, alphabet has {len(coptic)}: "
            f"{''.join(coptic)}")
    if len(greek) != EXPECT_GREEK:
        problems.append(
            f"expected {EXPECT_GREEK} Greek letters, alphabet has {len(greek)}: "
            f"{''.join(greek)}")
    if len(chars) != EXPECT_TOTAL:
        problems.append(
            f"expected {EXPECT_TOTAL} letters total, alphabet has {len(chars)}")
    if other:
        problems.append(
            f"{len(other)} letter(s) outside the Coptic and Greek blocks: "
            f"{''.join(other)!r}")
    if len(set(chars)) != len(chars):
        dupes = sorted({c for c in chars if chars.count(c) > 1})
        problems.append(f"duplicate letters in the alphabet: {''.join(dupes)}")
    return problems


def main() -> int:
    computed = collation_hash()
    expected = pinned()

    shape = check_alphabet_shape()
    if shape:
        print("COLLATION GUARD: FAIL — alphabet SHAPE is wrong.", file=sys.stderr)
        for p in shape:
            print(f"  - {p}", file=sys.stderr)
        print("", file=sys.stderr)
        print("  The hash can be perfectly consistent with a broken alphabet, so "
              "the\n  shape is asserted separately. If this change is deliberate, "
              "update\n  EXPECT_COPTIC / EXPECT_GREEK in this file and the pin in "
              "test_collate.py\n  in the SAME pull request.", file=sys.stderr)
        return 1

    if expected is None:
        print("COLLATION GUARD: FAIL — no 16-hex pin found in "
              f"{TEST.relative_to(ROOT)}", file=sys.stderr)
        print("  A collation pin must exist. If the alphabet is being changed for "
              "the first time, add it deliberately.", file=sys.stderr)
        return 1

    if computed != expected:
        print("COLLATION GUARD: FAIL — alphabet drifted.", file=sys.stderr)
        print(f"  pinned   : {expected}", file=sys.stderr)
        print(f"  computed : {computed}", file=sys.stderr)
        print("", file=sys.stderr)
        print("  If you changed _ALPHA or _GREEK in tools/collate.py, that is "
              "expected: update the pin in\n"
              "  tools/tests/test_collate.py in THIS SAME pull request and get a "
              "Coptic linguist to\n  review the diff. If you did not change them, "
              "something is wrong with the module.", file=sys.stderr)
        return 1

    print(f"COLLATION GUARD: OK — alphabet pinned at {computed}, "
          f"{EXPECT_COPTIC} Coptic + {EXPECT_GREEK} Greek = {EXPECT_TOTAL} letters")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
