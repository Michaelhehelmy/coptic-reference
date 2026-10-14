#!/usr/bin/env python3
"""tools/validate/shard_guard.py — the shipped shards must be intact and honest.

Session 5. This guard exists because of a whole family of bugs that no other
guard could see, and because of the rule COVERAGE.md now states: *a guard that
measures a proxy for the thing will pass when the thing is absent*.

Four things are checked, each on the thing itself:

  1. every `shard-NNN.json.gz` really is gzip (Session 5 S5-B2 put plain JSON in
     23 files with that name, and every count-based guard was happy);
  2. every shard decompresses, and its entry count matches the index header;
  3. the union of shards is exactly the index's rows -- no entry in a shard that
     the index does not list, none listed that is missing;
  4. the shard set is non-empty and covers the declared `shard_count`.

Check 3 is the cross-check D9 asks for, and it is the one that catches an index
that has drifted from the shards, which is the failure a reader sees as "the word
is in the index but tapping it does nothing".

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import argparse
import gzip
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import shardio  # noqa: E402

GZIP_MAGIC = b"\x1f\x8b"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="shipped shards must be intact")
    ap.add_argument("--dict-dir", type=pathlib.Path,
                    default=ROOT / "data" / "dist" / "dict")
    args = ap.parse_args(argv)

    d = args.dict_dir
    if not d.is_dir():
        print(f"[shard_guard] FAIL — {d} does not exist.", file=sys.stderr)
        return 1

    errors: list[str] = []

    # 1. every .gz is really gzip
    gzs = sorted(d.glob("shard-*.json.gz"))
    plains = sorted(p for p in d.glob("shard-*.json"))
    if not gzs:
        errors.append(f"no shard-*.json.gz in {d}")
    if plains:
        errors.append(
            f"{len(plains)} uncompressed shard(s) still present "
            f"({', '.join(p.name for p in plains[:3])}"
            f"{'...' if len(plains) > 3 else ''}). C2: serve .json.gz and do not "
            f"keep both — the uncompressed copy doubles the shipped bytes and "
            f"gives a reader two ways to get a stale file.")
    for g in gzs:
        head = g.read_bytes()[:2]
        if head != GZIP_MAGIC:
            errors.append(
                f"{g.name}: starts with {head.hex()} ({head!r}), not the gzip magic "
                f"1f8b. A plain JSON file named .gz is what Session 5 S5-B2 "
                f"produced for all 23 shards; nothing noticed.")

    # 2. each shard decompresses and its count matches
    total_entries = 0
    per_shard: dict[int, list[dict]] = {}
    for g in gzs:
        try:
            blob = shardio.read_shard(g)
        except SystemExit as e:
            errors.append(str(e).splitlines()[0])
            continue
        n = len(blob.get("entries", []) or [])
        total_entries += n
        declared = blob.get("count")
        if declared is not None and declared != n:
            errors.append(f"{g.name}: header says count={declared}, holds {n}")
        per_shard[_shard_no(g.name)] = blob.get("entries", []) or []

    # 3. index <-> shards cross-check
    idx_path = d / "index.json.gz"
    if not idx_path.is_file():
        errors.append(f"{idx_path.name} is missing; the client has no lookup table")
    else:
        idx = shardio.read_shard(idx_path)
        rows = idx.get("rows") or []
        if not rows:
            errors.append("index.json.gz has no rows — an empty index would send "
                          "every lookup nowhere while looking structurally fine")
        seen: set[tuple[int, int]] = set()
        for r in rows:
            key = (r["shard"], r["offset"])
            if key in seen:
                errors.append(f"index lists shard {r['shard']} offset "
                              f"{r['offset']} twice")
            seen.add(key)
            entries = per_shard.get(r["shard"])
            if entries is None:
                errors.append(f"index points at shard {r['shard']}, which is not "
                              f"in the shipped set")
                continue
            if r["offset"] >= len(entries):
                errors.append(f"index {r['norm_key']!r}: offset {r['offset']} is "
                              f"past the end of shard {r['shard']} "
                              f"({len(entries)} entries)")
                continue
            e = entries[r["offset"]]
            if e.get("norm_key") != r["norm_key"]:
                errors.append(
                    f"index says shard {r['shard']} offset {r['offset']} is "
                    f"{r['norm_key']!r}, but that slot holds {e.get('norm_key')!r}")

        # every entry in every shard must be listed
        listed = {(r["shard"], r["offset"]) for r in rows}
        for shard_no, entries in sorted(per_shard.items()):
            for off, e in enumerate(entries):
                if (shard_no, off) not in listed:
                    errors.append(
                        f"{e.get('norm_key')!r} is in shard {shard_no} at offset "
                        f"{off} but is NOT in the index — a reader would never "
                        f"find it")

        # 4. declared counts
        if idx.get("entry_count") is not None and idx["entry_count"] != len(rows):
            errors.append(f"index entry_count={idx['entry_count']} but it lists "
                          f"{len(rows)} rows")
        hdr_count = idx.get("shard_count")
        if hdr_count is not None and hdr_count != len(gzs):
            errors.append(f"index shard_count={hdr_count} but {len(gzs)} shard "
                          f"files are shipped")

    if errors:
        print(f"[shard_guard] FAIL — {len(errors)} problem(s):", file=sys.stderr)
        for e in errors[:20]:
            print(f"  - {e}", file=sys.stderr)
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more", file=sys.stderr)
        return 1

    print(f"[shard_guard] OK — {len(gzs)} shard(s), all really gzipped; "
          f"{total_entries} entries; index cross-check clean "
          f"(every listed row resolves, every shipped entry is listed); "
          f"{sum(1 for _ in per_shard)} shard(s) counted")
    return 0


def _shard_no(name: str) -> int:
    stem = name[len("shard-"):]
    for suf in (".json.gz", ".json"):
        if stem.endswith(suf):
            stem = stem[: -len(suf)]
            break
    return int(stem)


if __name__ == "__main__":
    raise SystemExit(main())
