#!/usr/bin/env python3
"""tools/validate/index_pin_guard.py — the SHIPPED index must carry the pin.

Session 5 G3. `collation_guard.py` compares `collate.collation_hash()` to the pin
in `tools/tests/test_collate.py`. That is a statement about the CODE.

It said nothing about the artefact. Proved in Session 5 D1: setting the shipped
`index.json`'s `collation_hash` to `0000000000000000` left `collation_guard`
printing OK, and so did the test suite, because the suite checked a *tmp* emit.

So a stale index could ship — carrying a hash that says "sorted with an alphabet
that no longer exists" — and nothing would notice. A client reading that hash to
decide whether its own collator matches would be misled, and one sorting by hand
against it would produce a different order from the shards.

This closes it the boring way: read the shipped file, compare the pin, and also
refuse if the file was built by a different collator than the one on disk now.
That second half is what a hash is for, and nothing was using it.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import collate  # noqa: E402
import shardio  # noqa: E402

PIN_RE = re.compile(r'assert\s+collation_hash\(\)\s*==\s*"([0-9a-f]{16})"')
PIN_SOURCE = ROOT / "tools" / "tests" / "test_collate.py"
#: Both index artefacts are checked: `index.json.gz` is what a client fetches,
#: `index.json` is the build record. Either drifting is a bug.
INDEX_FILES = ("index.json.gz", "index.json")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="the shipped index carries the pin")
    ap.add_argument("--dict-dir", type=pathlib.Path,
                    default=ROOT / "data" / "dist" / "dict")
    args = ap.parse_args(argv)

    m = PIN_RE.search(PIN_SOURCE.read_text(encoding="utf-8"))
    if not m:
        print(f"[index_pin_guard] FAIL — no 16-hex pin in {PIN_SOURCE}. Run "
              f"collation_guard.py first; the pin must exist.", file=sys.stderr)
        return 1
    pinned = m.group(1)
    current = collate.collation_hash()

    errors: list[str] = []
    if pinned != current:
        errors.append(f"code drift: tools/collate.py now hashes to {current}, the "
                      f"pin says {pinned}. collation_guard.py should have caught "
                      f"this — run it.")

    checked = 0
    for name in INDEX_FILES:
        p = args.dict_dir / name
        if not p.is_file():
            continue
        try:
            blob = shardio.read_shard(p)
        except SystemExit as e:
            errors.append(str(e).splitlines()[0])
            continue
        checked += 1
        got = blob.get("collation_hash")
        if got is None:
            errors.append(f"{name}: no collation_hash field. A client cannot tell "
                          f"whether its collator matches the shards' order.")
        elif got != current:
            errors.append(
                f"{name}: carries collation_hash {got!r} but the alphabet on disk "
                f"hashes to {current!r}. Either the file is stale or it was built "
                f"by a different collator. Rows would be sorted by an alphabet that "
                f"no longer exists.")

    if errors:
        print(f"[index_pin_guard] FAIL — {len(errors)} problem(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    if not checked:
        print(f"[index_pin_guard] SKIP — no index file in {args.dict_dir}; run "
              f"tools/emit/cli.py and tools/emit/dict_index.py. Treating 'nothing "
              f"to check' as a pass is the habit Session 5 exists to break, so "
              f"this is a skip with a loud reason, not a clean bill.", file=sys.stderr)
        return 0

    print(f"[index_pin_guard] OK — pin {pinned} matches the alphabet on disk; "
          f"{checked} shipped index file(s) carry it "
          f"({', '.join(INDEX_FILES[:checked])})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
