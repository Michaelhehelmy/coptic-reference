#!/usr/bin/env python3
"""tools/validate/no_object_object_guard.py — published output must not render objects.

LICENCE: project code, Apache-2.0.

Session 16 D0.3, upgraded Session 22 D0 / C1.

`[object Object]` is what JavaScript produces when a template interpolates a
structured value directly. Here it was the dictionary reader printing
`e.translit`, an object with five transliteration schemes, into a definition
list. The page built, the guards passed, and every entry with a
transliteration said `[object Object]`.

This guard looks for the rendered symptom, not one implementation. It walks
every published artefact and decompresses every `public/data/**/*.json.gz`
file before checking it. A future template that reads any object or array raw
fails here, whether or not anyone remembers `translit`.

Session 22 split the two media, because they fail differently:

  .html / .json / .json.gz   byte-level text scan. A rendered leak IS bytes
                             in the published output; there is nothing AST
                             about a built page.
  .js                        AST scan via tools/validate/js_object_scan.mjs
                             (acorn, pinned in package.json). A source file
                             may contain the needle in a comment, a type
                             check, or dead data without any of those
                             reaching a page. Session 21 E34 proved the text
                             scan cannot tell mention from use: it failed the
                             build on pos_labels.js for COMMENTING on the
                             bug class it exists to prevent. The AST scan
                             flags only literals in a concatenation, a
                             template literal, or an assignment to
                             innerHTML / textContent / document.write.

The former THIRD_PARTY_EXCEPTIONS carve-out for pagefind-highlight.js is
gone: that file compares `!== "[object Object]"`, and a comparison is not a
rendering path, so the AST scanner ignores it on its own merits. An
exception list is a standing debt; a correct rule is not.

Naming reports the relative path (and, for JS, the line), so a failure tells
exactly which built file contains the leak and where.
"""
from __future__ import annotations

import argparse
import gzip
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
NEEDLE = "[object Object]"
TEXT_SUFFIXES = {".html", ".json"}
MAX_TEXT_BYTES = 64 * 1024 * 1024
SCAN_MJS = ROOT / "tools" / "validate" / "js_object_scan.mjs"


def _check_blob(data: bytes, where: str, errors: list[str]) -> None:
    if NEEDLE.encode("utf-8") in data:
        errors.append(f"{where} contains {NEEDLE!r}")


def _run_js_scan(files: list[pathlib.Path], public: pathlib.Path,
                 errors: list[str]) -> int:
    """Parse every .js file with acorn in ONE node invocation. Returns the
    number of files scanned. Missing node or a scanner crash fails closed."""
    if not files:
        return 0
    node = shutil.which("node")
    if not node:
        errors.append("node is not on PATH; cannot AST-scan published JS. "
                      "Install Node (package.json pins acorn for this scan) "
                      "or fix PATH — a guard that cannot run must fail.")
        return 0
    if not SCAN_MJS.is_file():
        errors.append(f"scanner missing: {SCAN_MJS.relative_to(ROOT)}")
        return 0
    try:
        proc = subprocess.run(
            [node, str(SCAN_MJS), *[str(f) for f in files]],
            capture_output=True, text=True, cwd=ROOT, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        errors.append(f"js scan could not run ({e})")
        return 0
    if proc.returncode == 0:
        return len(files)
    if proc.returncode == 2:
        # Parse failure: the scanner prints which file. Fail closed — an
        # unparseable published script cannot be certified clean.
        for line in (proc.stderr or "").splitlines():
            errors.append(f"js scan: {line.strip()}")
        return len(files)
    # returncode 1: findings, one per stdout line, "path:line: reason".
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rel = pathlib.Path(line.split(":", 1)[0]).resolve().relative_to(
                public.resolve()).as_posix()
        except ValueError:
            rel = line.split(":", 1)[0]
        errors.append(f"{rel} {line.split(':', 1)[1].strip()}"
                      if ":" in line else f"{rel} contains {NEEDLE!r}")
    if proc.stderr:
        for line in proc.stderr.splitlines():
            if line.strip():
                errors.append(f"js scan: {line.strip()}")
    return len(files)


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
    js_files: list[pathlib.Path] = []
    for path in sorted(public.rglob("*")):
        if not path.is_file():
            continue
        try:
            if (path.suffix == ".gz" and path.name.endswith(".json.gz")
                    and path.is_relative_to(public / "data")):
                try:
                    raw = gzip.decompress(path.read_bytes())
                except OSError as e:
                    errors.append(f"{path.relative_to(public).as_posix()}: "
                                  f"cannot decompress published JSON ({e})")
                    continue
                decompressed += 1
                _check_blob(raw, path.relative_to(public).as_posix(), errors)
                inspected += 1
            elif path.suffix.lower() == ".js":
                js_files.append(path)
                inspected += 1
            elif path.suffix.lower() in TEXT_SUFFIXES:
                if path.stat().st_size > MAX_TEXT_BYTES:
                    errors.append(f"{path.relative_to(public).as_posix()}: text "
                                  f"file is unexpectedly large; refusing to "
                                  f"read it into memory")
                    continue
                _check_blob(path.read_bytes(),
                            path.relative_to(public).as_posix(), errors)
                inspected += 1
        except OSError as e:
            errors.append(f"{path.relative_to(public).as_posix()}: cannot read ({e})")

    _run_js_scan(js_files, public, errors)

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
    print(f"[no_object_object_guard] OK — {inspected} published artefact(s) "
          f"checked ({len(js_files)} via AST), {decompressed} compressed JSON "
          f"payload(s) decompressed; no {NEEDLE!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
