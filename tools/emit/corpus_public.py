#!/usr/bin/env python3
"""tools/emit/corpus_public.py — what the BROWSER actually fetches (D3).

    data/dist/corpus/corpus.tar.gz     the reviewable, committed archive
    public/data/corpus/<slug>/         what a reader's browser downloads

Why two copies. The tarball is the provenance surface: one file, reviewed in a
pull request, licence-checked by nc_guard. The browser cannot read a tarball
without a server doing it, and there is no server (invariant 1: the reading path
is 100% static). So Stage B extracts the SHIPPED works only, as gzipped JSON the
browser fetches directly.

Only shipped works are extracted. A work that is not in tools/shipped.toml with
`shipped = true` never reaches public/, even if it is in the tarball — the
manifest is the gate, and the assertion below is what stops a `glob` from quietly
becoming the gate.

.text.json.gz is deliberately NOT minified beyond separators, and verse text is
never re-encoded: Coptic stays text (the same rule the vault follows). gzip is
done with mtime=0 so a rebuild with no content change produces identical bytes.

LICENCE: project code, Apache-2.0. Corpus content stays CC BY-SA per source; each
work's meta.json carries the licence and travels with the data.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import pathlib
import sys
import tarfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import safeio  # noqa: E402
ROOT = HERE.parents[1]

#: Asserted, per the brief. Comfortably under Cloudflare's 25 MiB per-file limit
#: and under a sane budget for a first page load.
MAX_TOTAL_BYTES = 20 * 1024 * 1024


def gzip_bytes(data: bytes) -> bytes:
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode="wb", compresslevel=9, mtime=0) as gz:
        gz.write(data)
    return out.getvalue()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="extract shipped works for the browser")
    ap.add_argument("--tarball", type=pathlib.Path,
                    default=ROOT / "data" / "dist" / "corpus" / "corpus.tar.gz")
    ap.add_argument("--manifest", type=pathlib.Path,
                    default=ROOT / "data" / "dist" / "corpus" / "manifest.json")
    ap.add_argument("--out", type=pathlib.Path,
                    default=ROOT / "public" / "data" / "corpus")
    args = ap.parse_args(argv)

    if not args.tarball.is_file():
        raise SystemExit(f"[corpus_public] {args.tarball} not found. "
                         f"Run tools/emit/corpus_tarball.py first.")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    shipped = set(manifest.get("fingerprints", {}))
    absent = set(manifest.get("declared_but_absent", []))
    if not shipped:
        raise SystemExit("[corpus_public] the manifest lists no works; refusing to "
                         "publish an empty corpus directory that looks populated.")

    if args.out.exists():
        import shutil
        shutil.rmtree(args.out)
    args.out.mkdir(parents=True)

    written: list[tuple[str, int, int]] = []
    with tarfile.open(args.tarball, "r:gz") as tf:
        slugs = sorted({n.split("/")[0] for n in tf.getnames() if "/" in n})
        for slug in slugs:
            if slug not in shipped:
                # Defence in depth: the tarball should only hold shipped works.
                print(f"[corpus_public] REFUSING to publish {slug}: not in the "
                      f"manifest's shipped set")
                continue
            dest = args.out / slug
            dest.mkdir(parents=True, exist_ok=True)
            for member, gz in (("text.json", "text.json.gz"),
                               ("tokens.json", "tokens.json.gz")):
                fh = tf.extractfile(f"{slug}/{member}")
                if fh is None:
                    continue
                raw = fh.read()
                blob = gzip_bytes(raw)
                # Session 6 D1 / C2: Rule 3. public/** is what a reader downloads,
                # so an unverified write here is a reader getting truncated JSON.
                safeio.write_verified(dest / gz, blob)
                written.append((f"{slug}/{gz}", len(raw), len(blob)))
            fh = tf.extractfile(f"{slug}/meta.json")
            if fh is not None:
                safeio.write_verified(dest / "meta.json", fh.read())

    total_raw = sum(r for _n, r, _c in written)
    total_gz = sum(c for _n, _r, c in written)
    print(f"[corpus_public] {len(slugs)} work(s) in the tarball, "
          f"{len(shipped)} shipped, {len(absent)} declared-but-absent")
    print(f"[corpus_public] {'file':46} {'raw':>10} {'gz':>9}  ratio")
    for name, raw, gz in sorted(written):
        print(f"[corpus_public] {name:46} {raw:>10,} {gz:>9,}  {raw / max(gz, 1):.1f}x")
    for slug in sorted(shipped):
        meta = args.out / slug / "meta.json"
        if meta.is_file():
            print(f"[corpus_public] {slug}/meta.json  "
                  f"{meta.stat().st_size:>10,} bytes  (uncompressed, licence + URN)")
    print(f"[corpus_public] TOTAL raw {total_raw:,}  gz {total_gz:,}  "
          f"({total_gz / 1048576:.2f} MiB, ratio {total_raw / max(total_gz, 1):.1f}x)")

    dir_bytes = sum(p.stat().st_size for p in args.out.rglob("*") if p.is_file())
    print(f"[corpus_public] {args.out} = {dir_bytes:,} bytes "
          f"({dir_bytes / 1048576:.2f} MiB) on disk")
    if dir_bytes > MAX_TOTAL_BYTES:
        raise SystemExit(
            f"[corpus_public] {dir_bytes / 1048576:.2f} MiB exceeds the "
            f"{MAX_TOTAL_BYTES // 1048576} MiB budget. Report the number; do not "
            f"tune it — the number is the finding.")
    print(f"[corpus_public] under the {MAX_TOTAL_BYTES // 1048576} MiB budget  OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
