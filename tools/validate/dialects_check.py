#!/usr/bin/env python3
"""tools/validate/dialects_check.py — dialects.json must match the shipped shards.

The page at /dialects/ is v4 §10.2's honesty mechanism: it shows that Bohairic is
presented first as a choice, not because the data supports it equally. A count
that has drifted from the data would make that mechanism lie quietly, so the
counts are recomputed from the shards and compared, not trusted.

Also asserts the Q4 invariant in the strong direction: `no_dialect_recorded` must
be non-zero and must equal the number of entries whose only dialect is N. If a
future change ever "fixed" that by filtering those entries out, this fails.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import shardio  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dist", type=pathlib.Path, default=ROOT / "data" / "dist")
    ap.add_argument("--tool", type=pathlib.Path,
                    default=ROOT / "tools" / "emit" / "dialects.py")
    ap.add_argument("--write", action="store_true",
                    help="regenerate dialects.json first; OFF by default, because "
                         "a checker that rewrites the file it is checking cannot "
                         "detect the file being wrong (Session 4 S4-C6)")
    args = ap.parse_args(argv)

    # Session 5 G1: this SKIPped on missing shards and exited 0. It now uses the
    # shared reader, which fails closed -- there is no "no shards, all good".
    shards = shardio.shard_paths(args.dist / "dict")

    target = args.dist / "dialects.json"
    if args.write:
        subprocess.run([sys.executable, str(args.tool)], check=True, capture_output=True)
    elif not target.is_file():
        print(f"[dialects_check] FAIL — {target} does not exist. Run "
              f"`python3 tools/emit/dialects.py` (or pass --write).", file=sys.stderr)
        return 1
    # Read the COMMITTED file. The first version of this check ran the emitter
    # first, which meant it compared a file it had just written against the data
    # that had just written it -- always true, and blind to a dialects.json that
    # had drifted or been hand-edited. So it could not fail. It "MISSED" a
    # dialects.json with no_dialect_recorded forced to 0, which is precisely the
    # dishonesty Q4 exists to prevent.
    got = json.loads(target.read_text(encoding="utf-8"))

    total = with_tla = no_dialect = 0
    by = collections.Counter()
    for _p, e in shardio.iter_entries(args.dist / "dict", require=True):
        if True:
            total += 1
            if e.get("id") and not str(e["id"]).startswith("H"):
                with_tla += 1
            ds = e.get("dialects") or []
            if ds == ["N"]:
                no_dialect += 1
            by.update(ds)

    want_by = dict(sorted(by.items(), key=lambda kv: -kv[1]))
    errors: list[str] = []
    for field, want in (("total_entries", total), ("with_tla_id", with_tla),
                        ("no_dialect_recorded", no_dialect), ("by_dialect", want_by)):
        if got.get(field) != want:
            errors.append(f"{field}: dialects.json says {got.get(field)!r}, "
                          f"shards give {want!r}")

    # Q4: the undetermined count must be VISIBLE, not filtered away.
    if got.get("no_dialect_recorded", 0) <= 0:
        errors.append("no_dialect_recorded is 0 — Q4 requires the undetermined "
                      "count to be shown, so a page that renders it cannot "
                      "silently hide that the entries exist")
    if got.get("notes", {}).get("N", "").strip() == "":
        errors.append("dialects.json has no note explaining N, but Q4 requires a "
                      "visible reader-facing note for those entries")

    if errors:
        print(f"[dialects_check] FAIL — {len(errors)} problem(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    pct = no_dialect * 100 // max(total, 1)
    print(f"[dialects_check] OK — {total} entries, {with_tla} with a TLA id, "
          f"{no_dialect} ({pct}%) undetermined and shown; by_dialect matches the shards")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
