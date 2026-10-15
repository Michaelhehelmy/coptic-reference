#!/usr/bin/env python3
"""tools/validate/reader_usage_guard.py — Rule 12: one reader, one writer.

Session 18 D0. Every file format in the pipeline has exactly one reader and
one writer; no call site opens a file directly; a file in multiple on-disk
forms has exactly one reader resolving all forms. In practice: shards go
through shardio, every other dual-form artefact through safeio, browser
fetches through fetch_json.js.

This guard greps for the violation shape: a direct file-access call on a line
that names a dual-form (bare-form) pipeline artefact, without safeio/shardio
mediation on the same line.

SCOPE, stated so the clean run is meaningful rather than lucky:

- Scanned: tools/**/*.py (pipeline code) and static/js/*.js (fetch sites).
- Exempt: tools/tests/** (Rule 6: tests own tmp_path, and negative controls
  REQUIRE byte-direct writes), tools/safeio.py + tools/shardio.py (the
  designated modules), tools/parse/** + tools/fetch/** (designated ingest
  readers of single-form upstream inputs).
- Bare-form markers only (shard-, index.json, LICENSES, records.csv, ...).
  An explicit `.json.gz` literal states its form, so it cannot pick the wrong
  one; single-form inputs (sources/*, schema/*, shipped.toml, corpus.tar.gz,
  corpus manifest.json) are out of scope by construction.
- KNOWN LIMITATION (see COVERAGE.md): the verb and the path must share a
  line. A path assigned on one line and opened five lines later is invisible
  to this guard. Session 17's dict_index.py:135 was exactly that shape and
  was fixed by survey, not by this guard.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]

#: Direct file-access verbs. os.replace/shutil.copy are included: outside
#: safeio they are unverified file surgery on pipeline paths.
PY_VERB = re.compile(
    r"(?:\bos\.replace\b|\bshutil\.(?:copy|copy2|move)\b|\bgzip\.open\b"
    r"|\(\s*open\(|\.open\(|\.read_text\b|\.write_text\b"
    r"|\.read_bytes\b|\.write_bytes\b)"
)

#: Bare-form dual artefact names. Explicit `.json.gz` is excluded by
#: lookahead: stating the form cannot pick the wrong one.
PY_BARE = re.compile(
    r"(?:shard-|index\.json(?!\.gz)|LICENSES(?!\.csv\.gz)"
    r"|records\.csv(?!\.gz)|/dict/|/provenance/|/quiz/|/drill/|data/dist)"
)

#: Mediation: the resolving reader/writer owns the call.
PY_MEDIATED = re.compile(r"(?:safeio\.|shardio\.)")

#: Raw browser fetch outside the designated reader. FetchJson.json does not
#: match \bfetch (capital F), so only true raw calls flag.
JS_RAW_FETCH = re.compile(r"(?:[^_.A-Za-z]|^)fetch\s*\(")
JS_DATA_URL = re.compile(r"(?:data/|\.json|\.gz)")
JS_DESIGNATED = "fetch_json.js"

EXEMPT_DIRS = (
    ("tools", "tests"),
    ("tools", "parse"),
    ("tools", "fetch"),
)
EXEMPT_FILES = (
    ("tools", "safeio.py"),
    ("tools", "shardio.py"),
)


def _exempt(path: pathlib.Path) -> bool:
    rel = path.relative_to(ROOT).parts
    if rel[:2] in EXEMPT_DIRS:
        return True
    if rel in EXEMPT_FILES:
        return True
    return False


def _display(path: pathlib.Path) -> str:
    """Repo-relative where possible; absolute for out-of-tree probes."""
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def check_python_file(path: pathlib.Path) -> list[str]:
    """Direct opens of bare-form artefacts in one pipeline module."""
    hits: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        return [f"{path}: unreadable ({e})"]
    for number, line in enumerate(lines, 1):
        stripped = line.split("#", 1)[0]
        if PY_VERB.search(stripped) and PY_BARE.search(stripped) \
                and not PY_MEDIATED.search(stripped):
            hits.append(f"{_display(path)}:{number}: {line.strip()}")
    return hits


def check_js_file(path: pathlib.Path) -> list[str]:
    """Raw fetch() of data URLs outside fetch_json.js."""
    if path.name == JS_DESIGNATED:
        return []
    hits: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        return [f"{path}: unreadable ({e})"]
    for number, line in enumerate(lines, 1):
        stripped = line.split("//", 1)[0]
        if JS_RAW_FETCH.search(stripped) and JS_DATA_URL.search(stripped):
            hits.append(f"{_display(path)}:{number}: {line.strip()}")
    return hits


def check(root: pathlib.Path = ROOT) -> list[str]:
    """All Rule 12 violations under root. Empty means clean."""
    hits: list[str] = []
    for path in sorted((root / "tools").rglob("*.py")):
        if "__pycache__" in path.parts or _exempt(path):
            continue
        hits.extend(check_python_file(path))
    for path in sorted((root / "static" / "js").glob("*.js")):
        hits.extend(check_js_file(path))
    return hits


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Rule 12: one reader, one writer")
    ap.parse_args(argv)
    hits = check()
    if hits:
        print(f"[reader_usage_guard] FAIL — {len(hits)} direct open(s) "
              f"of pipeline artefacts:", file=sys.stderr)
        for hit in hits:
            print(f"  - {hit}", file=sys.stderr)
        print("Route shard access through shardio, other dual-form access "
              "through safeio, browser fetches through fetch_json.js.",
              file=sys.stderr)
        return 1
    print("[reader_usage_guard] OK — no direct opens of pipeline artefacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
