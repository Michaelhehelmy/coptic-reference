#!/usr/bin/env python3
"""tools/emit/gzip_csvs.py — ship records.csv and LICENSES.csv as .csv.gz.

Session 7 C4, and it is the reason this ran BEFORE fetching the eight works.

`--blame` on the size guard showed the largest file under `data/dist` was
`provenance/records.csv` at 1,717,003 B — **42% of the whole 5 MiB budget**. One
row per (entry, source), so it grows with both. Eight more corpus works will add
corpus_refs to every entry and push the dataset straight through the line, and a
budget that is breached by doing the thing the plan asks for is a budget that will
get "tuned" rather than enforced.

CSV compresses extremely well: it is a header row plus millions of rows that
repeat the same column names' values. Measured below.

Both files are served as `.csv.gz` and rendered by a static viewer that
decompresses in the browser with `DecompressionStream('gzip')`. **The
uncompressed .csv is removed**, per C4, because keeping both would defeat the
point and create two ways to read a stale copy — the same mistake as the two
licence manifests in Session 6.

One honest trade: a reader can no longer open these in a spreadsheet by
double-clicking. That is a real loss for the people who most want to sort a
lexicon by hand, and it is why `static/read-csv.html` exists and why the raw
`.csv.gz` stays downloadable.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import argparse
import gzip
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import safeio  # noqa: E402

#: The CSVs we ship gzipped. Everything else in provenance/ stays plain, because a
#: 4 KB README is not worth a decompress step.
TARGETS = ("records.csv", "LICENSES.csv")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="gzip the provenance CSVs")
    ap.add_argument("--dist", type=pathlib.Path, default=ROOT / "data" / "dist")
    ap.add_argument("--restore", action="store_true")
    args = ap.parse_args(argv)

    prov = args.dist / "provenance"
    if not prov.is_dir():
        print(f"[gzip_csvs] FAIL — {prov} does not exist. Run tools/emit/cli.py "
              f"first; refusing to report success on nothing.", file=sys.stderr)
        return 1

    rows = []
    total_raw = total_gz = 0
    missing = []
    for name in TARGETS:
        plain = prov / name
        gzpath = prov / (name + ".gz")

        if args.restore:
            if not gzpath.is_file():
                missing.append(f"{name}.gz absent")
                continue
            raw = gzip.decompress(gzpath.read_bytes())
            safeio.write_verified(plain, raw)
            gzpath.unlink()
            rows.append((name, len(raw), 0))
            total_raw += len(raw)
            continue

        if gzpath.is_file() and not plain.is_file():
            # already shipped form
            gz = gzpath.stat().st_size
            raw = len(gzip.decompress(gzpath.read_bytes()))
            rows.append((name, raw, gz))
            total_raw += raw
            total_gz += gz
            continue
        if not plain.is_file():
            missing.append(name)
            continue

        raw = plain.read_bytes()
        blob = gzip.compress(raw, compresslevel=9, mtime=0)
        # Rule 3, and this is the file where it matters most: a truncated
        # records.csv would look like a smaller dataset rather than an error.
        gz = safeio.write_verified(gzpath, blob)
        plain.unlink()          # C4: do not keep both
        rows.append((name, len(raw), gz))
        total_raw += len(raw)
        total_gz += gz

    if missing:
        print(f"[gzip_csvs] FAIL — missing: {', '.join(missing)}", file=sys.stderr)
        return 1
    if not rows:
        print("[gzip_csvs] FAIL — nothing was written.", file=sys.stderr)
        return 1

    print(f"[gzip_csvs] provenance CSVs ({'restored' if args.restore else 'gzipped'})")
    print(f"  {'file':16s} {'raw':>12s} {'gz':>10s} {'ratio':>8s}")
    print(f"  {'-'*16} {'-'*12} {'-'*10} {'-'*8}")
    for name, raw, gz in rows:
        r = f"{raw / gz:6.2f}x" if gz else "   n/a"
        print(f"  {name:16s} {raw:12,d} {gz:10,d} {r:>8s}")
    print(f"  {'-'*16} {'-'*12} {'-'*10} {'-'*8}")
    print(f"  {'TOTAL':16s} {total_raw:12,d} {total_gz:10,d} "
          f"{(total_raw / total_gz if total_gz else 0):6.2f}x")
    if not args.restore:
        print(f"  saved {total_raw - total_gz:,} B; uncompressed .csv removed (C4)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
