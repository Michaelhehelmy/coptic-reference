#!/usr/bin/env python3
"""tools/validate/no_object_object_guard.py — published output must not contain rendered objects.

LICENCE: project code, Apache-2.0.

Session 16 D0.3. `[object Object]` is what JavaScript produces when a template
interpolates a structured value directly. Here it was the dictionary reader
printing `e.translit`, an object with five transliteration schemes, into a
definition list. The page built, the guards passed, and every entry with a
transliteration said `[object Object]`.

This guard looks for the rendered symptom, not one implementation. It walks every
published `.html`, `.json`, and `.js` file, and decompresses every
`public/data/**/*.json.gz` file before checking it. A future template that reads
any object or array raw fails here, whether or not anyone remembers
`translit`.

Naming reports the relative path, so a failure tells exactly which built file
contains the leak.
"""
from __future__ import annotations

import argparse
import gzip
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
NEEDLE = "[object Object]"
TEXT_SUFFIXES = {".html", ".json", ".js"}
MAX_TEXT_BYTES = 64 * 1024 * 1024
# Upstream Pagefind's bundled pagefind-highlight.js contains the same literal in
# a JavaScript type check. It is not a rendered template interpolation, and it
# ships verbatim from the pinned upstream package. Excluding that one generated
# vendor file keeps this guard focused on output this project controls.
THIRD_PARTY_EXCEPTIONS = frozenset({"pagefind/pagefind-highlight.js"})


def _check_blob(data: bytes, where: str, errors: list[str]) -> None:
    if NEEDLE.encode("utf-8") in data:
        errors.append(f"{where} contains {NEEDLE!r}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="no rendered [object Object] in public/")
    ap.add_argument("--public", type=pathlib.Path, default=ROOT / "public")
    args = ap.parse_args(argv)

    public = args.public
    if not public.is_dir():
        print(f"[no_object_object_guard] FAIL — {public} does not exist. Build "
              f"first with tools/build.py.", file=sys.stderr)
        return 1

    errors: list[str] = []
    inspected = 0
    decompressed = 0
    for path in sorted(public.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(public).as_posix()
        if rel in THIRD_PARTY_EXCEPTIONS:
            continue
        try:
            if (path.suffix == ".gz" and path.name.endswith(".json.gz")
                    and path.is_relative_to(public / "data")):
                try:
                    raw = gzip.decompress(path.read_bytes())
                except OSError as e:
                    errors.append(f"{rel}: cannot decompress published JSON ({e})")
                    continue
                decompressed += 1
                _check_blob(raw, rel, errors)
                inspected += 1
            elif path.suffix.lower() in TEXT_SUFFIXES:
                if path.stat().st_size > MAX_TEXT_BYTES:
                    errors.append(f"{rel}: text file is unexpectedly large; refusing "
                                  f"to read it into memory")
                    continue
                _check_blob(path.read_bytes(), rel, errors)
                inspected += 1
        except OSError as e:
            errors.append(f"{rel}: cannot read ({e})")

    if not inspected:
        print(f"[no_object_object_guard] FAIL — inspected 0 files in {public}. "
              f"An empty published tree passes nothing.", file=sys.stderr)
        return 1
    if errors:
        print(f"[no_object_object_guard] FAIL — {len(errors)} rendered object(s):",
              file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"[no_object_object_guard] OK — {inspected} published artefact(s) checked, "
          f"{decompressed} compressed JSON payload(s) decompressed; no {NEEDLE!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
