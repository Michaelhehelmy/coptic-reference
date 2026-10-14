#!/usr/bin/env python3
"""tools/validate/translit_shape_guard.py — translit is an object, never a string.

LICENCE: project code, Apache-2.0.

Session 16 D0.4. The dictionary schema defines `translit` as an object with keys
drawn from five transliteration schemes. A raw string in that field would mean
the emitted shape has drifted away from the shape every renderer and test
expects.

This checks exactly that contract:

- `translit` may be absent;
- otherwise it must be an object;
- its keys must be a subset of the five schema schemes;
- it must never be a string.

The last test is deliberately specific. The reader's bug was caused by treating
an object as if it were a string; silently changing the emitted shape to a string
would "fix" that renderer while breaking every other consumer of the documented
object. Shape drift is a finding, not an accommodation.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import shardio  # noqa: E402

SCHEMES = frozenset({"bohairic", "sahidic", "layton", "till", "egyptological"})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="translit must be an object")
    ap.add_argument("--dict-dir", type=pathlib.Path,
                    default=ROOT / "data" / "dist" / "dict")
    args = ap.parse_args(argv)

    try:
        paths = shardio.shard_paths(args.dict_dir)
    except OSError as e:
        print(f"[translit_shape_guard] FAIL — cannot list {args.dict_dir} ({e})",
              file=sys.stderr)
        return 1
    if not paths:
        print(f"[translit_shape_guard] FAIL — no dictionary shards in "
              f"{args.dict_dir}. An empty dataset cannot prove a shape.",
              file=sys.stderr)
        return 1

    errors: list[str] = []
    checked = 0
    for shard in paths:
        try:
            blob = shardio.read_shard(shard)
        except SystemExit as e:
            errors.append(str(e).splitlines()[0])
            continue
        for offset, entry in enumerate(blob.get("entries", []) or []):
            if not isinstance(entry, dict):
                errors.append(f"{shard.name} offset {offset}: entry is "
                              f"{type(entry).__name__}, not an object")
                continue
            checked += 1
            where = (f"{shard.name} offset {offset} "
                     f"id {entry.get('id', '?')!r} lemma {entry.get('lemma', '')!r}")
            translit = entry.get("translit")
            if translit is None:
                continue
            if isinstance(translit, str):
                errors.append(
                    f"{where}: translit is a string {translit!r}, not the schema "
                    f"object. A template expecting the object and an object "
                    f"expecting a string cannot both be right.")
                continue
            if not isinstance(translit, dict):
                errors.append(f"{where}: translit is {type(translit).__name__}, "
                              f"not an object")
                continue
            unexpected = sorted(set(translit) - SCHEMES)
            if unexpected:
                errors.append(f"{where}: unexpected translit scheme(s) "
                              f"{', '.join(unexpected)}; expected a subset of "
                              f"{', '.join(sorted(SCHEMES))}")

    if errors:
        print(f"[translit_shape_guard] FAIL — {len(errors)} shape problem(s):",
              file=sys.stderr)
        for e in errors[:20]:
            print(f"  - {e}", file=sys.stderr)
        if len(errors) > 20:
            print(f"  - ... and {len(errors) - 20} more", file=sys.stderr)
        return 1
    print(f"[translit_shape_guard] OK — {checked:,} entr{'y' if checked == 1 else 'ies'} "
          f"checked in {len(paths)} shard(s); translit is absent or a schema object")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())