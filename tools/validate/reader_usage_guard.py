#!/usr/bin/env python3
"""tools/validate/reader_usage_guard.py — Rule 12: one reader, one writer.

Session 18 D0, rewritten Session 19 D0 (E32). Every file format in the
pipeline has exactly one reader and one writer; no call site opens a file
directly; a file in multiple on-disk forms has exactly one reader resolving
all forms. In practice: shards go through shardio, every other dual-form
artefact through safeio, browser fetches through fetch_json.js.

HOW IT WORKS. Two stages. The Session 18 regexes survive as a fast
file-level pre-filter: a file whose text contains no access verb or no
bare-form marker cannot violate, so it is never parsed. Everything else goes
through Python's `ast`: every call that opens, reads, writes, replaces, or
copies a file has its path expressions resolved — string constants joined
through `/`-divisions, f-string parts, and variable assignments followed one
hop (transitively, cycle-guarded) — and any resolved path naming a bare-form
dual artefact fails unless the call is `safeio.*`/`shardio.*`.

The rewrite exists because of E31: `dict_index.py` read `index.json` through
`hdr_path`, assigned two lines above, which no same-line regex can match.
The AST pass resolves exactly that shape.

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
- KNOWN LIMITATIONS (see COVERAGE.md): paths built across files, returned
  from functions, or fully dynamic (variables with no literal assignment in
  the same file) resolve to nothing and are invisible. Cross-file tracking
  would be a linter project of its own; the limitation is stated, not hidden.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import argparse
import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]

#: Fast file-level pre-filter (Session 18). A file containing no access verb
#: or no bare-form marker cannot violate; only the rest pays for parsing.
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

#: Verbs that open, read, write, replace, or copy a file when called
#: directly (rather than on safeio/shardio). tarfile.open is deliberately
#: absent: the corpus tarball is single-form, out of scope by construction.
_DIRECT_ATTRS = frozenset({
    "open", "read_text", "write_text", "read_bytes", "write_bytes",
    "replace", "copy", "copy2", "move",
})
_DIRECT_MODULES = {"os": {"replace"}, "shutil": {"copy", "copy2", "move"},
                   "gzip": {"open"}}
_MEDIATING_MODULES = frozenset({"safeio", "shardio"})

_MAX_RESOLVE_DEPTH = 4


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


def _assigned_exprs(tree: ast.AST) -> tuple[
        dict[tuple[int | None, str], list[ast.AST]], dict[int, int | None]]:
    """(scope, name) -> assigned value expressions, plus a scope map.

    Assignments resolve inside their own function first, then at module
    level. A file-wide map merged unrelated same-named variables (three
    false positives in obsidian.py on the first AST run: vault-dir `d`
    merged with a dict-dir `d` elsewhere), so scopes stay separate. Within
    one scope a reused name still merges — fail loud, don't guess.
    Returns the map and {node id: enclosing function id or None}.
    """
    parent: dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent.setdefault(id(child), node)
    mapping: dict[tuple[int | None, str], list[ast.AST]] = {}

    def scope_of(node: ast.AST) -> int | None:
        current = parent.get(id(node))
        while current is not None:
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef,
                                    ast.Lambda)):
                return id(current)
            current = parent.get(id(current))
        return None

    def record(target: ast.expr, value: ast.AST, scope: int | None) -> None:
        if isinstance(target, ast.Name):
            mapping.setdefault((scope, target.id), []).append(value)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                record(elt, value, scope)

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            scope = scope_of(node)
            for target in node.targets:
                record(target, node.value, scope)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            record(node.target, node.value, scope_of(node))
    scopes = {id(node): scope_of(node) for node in ast.walk(tree)}
    return mapping, scopes


def _expr_strings(node: ast.AST, assigned: dict[tuple[int | None, str],
                  list[ast.AST]], scope: int | None,
                  active: frozenset[str], depth: int) -> list[str]:
    """Candidate path strings for an expression. Best effort, bounded.

    Names resolve in their own scope first, then at module level. `active`
    is the chain of variable names currently being resolved; re-entering
    one stops that branch (cycle guard for `p = p / "x"`).
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.Name):
        if depth >= _MAX_RESOLVE_DEPTH or node.id in active:
            return []
        out: list[str] = []
        for key in ((scope, node.id), (None, node.id)):
            for value in assigned.get(key, ()):
                out.extend(_expr_strings(value, assigned, scope,
                                         active | {node.id}, depth + 1))
        return out
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left = _expr_strings(node.left, assigned, scope, active, depth + 1)
        right = _expr_strings(node.right, assigned, scope, active, depth + 1)
        if not left:
            return right  # `X / "index.json"` names the artefact whatever X is
        if not right:
            return left
        return [left_part + "/" + right_part
                for left_part in left for right_part in right]
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
        return parts
    # Calls, subscripts, attributes, anything else: harvest nested constants
    # (covers .with_name("LICENSES.csv.gz"), ROOT / "data" / ..., f-string
    # receivers) without pretending to evaluate.
    out: list[str] = []
    for child in ast.iter_child_nodes(node):
        out.extend(_expr_strings(child, assigned, scope, active, depth + 1))
    return out


def _is_direct_open(call: ast.Call) -> bool:
    """True when the call opens/reads/writes/copies a file itself.

    `tarfile.open` is excluded by name: the corpus tarball is single-form,
    so no form confusion is possible there (scope section above).
    """
    func = call.func
    if isinstance(func, ast.Name):
        return func.id == "open"
    if not isinstance(func, ast.Attribute):
        return False
    receiver = func.value
    if isinstance(receiver, ast.Name) and receiver.id in _MEDIATING_MODULES:
        return False
    if isinstance(receiver, ast.Name) and receiver.id == "tarfile":
        return False
    if isinstance(receiver, ast.Name) and receiver.id in _DIRECT_MODULES:
        return func.attr in _DIRECT_MODULES[receiver.id]
    return func.attr in _DIRECT_ATTRS


#: A direct read whose bytes feed only a hash cannot confuse forms: hashing
#: is form-agnostic (it works identically on plain and gzipped bytes, and a
#: changed form changes nothing but the digest). Matched on the source line.
_HASH_LINE = re.compile(r"(?:hashlib|sha256|md5|\bdigest\b)")


def _parent_map(tree: ast.AST) -> dict[int, ast.AST]:
    """Child node id -> parent node (ast.walk loses parents)."""
    parent: dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent.setdefault(id(child), node)
    return parent


def _nested_in_mediated(call: ast.Call, parent: dict[int, ast.AST]) -> bool:
    """True when the call is an argument of a safeio./shardio.* call.

    `safeio.write_verified(dest, src.read_bytes())` is one mediated write;
    flagging its inner read would punish the exact pattern the rule wants.
    """
    current = parent.get(id(call))
    while current is not None:
        if isinstance(current, ast.Call):
            func = current.func
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) \
                    and func.value.id in _MEDIATING_MODULES:
                return True
        current = parent.get(id(current))
    return False


def _call_strings(call: ast.Call,
                  assigned: dict[tuple[int | None, str], list[ast.AST]],
                  scopes: dict[int, int | None]) -> list[str]:
    """Candidate path strings for a call: receiver, plus path-position args.

    Only path positions are harvested. `write_text(content)` / `write_bytes`
    take CONTENT in args[0] — vault prose mentioning `data/dist` is not a
    path, and harvesting it flagged two innocent vault writes on the first
    AST run. Path-position args exist only on open/copy/replace verbs.
    """
    scope = scopes.get(id(call))
    out = _expr_strings(call.func, assigned, scope, frozenset(), 0)
    func = call.func
    harvest_args = False
    if isinstance(func, ast.Name) and func.id == "open":
        harvest_args = True
    elif isinstance(func, ast.Attribute):
        receiver = func.value
        if isinstance(receiver, ast.Name) and receiver.id in _DIRECT_MODULES:
            harvest_args = True
    if harvest_args:
        for arg in call.args:
            out.extend(_expr_strings(arg, assigned, scope, frozenset(), 0))
        for keyword in call.keywords:
            out.extend(_expr_strings(keyword.value, assigned, scope,
                                     frozenset(), 0))
    return out


def check_python_file(path: pathlib.Path) -> list[str]:
    """Direct opens of bare-form artefacts in one pipeline module (AST)."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        return [f"{path}: unreadable ({e})"]
    if not (PY_VERB.search(text) and PY_BARE.search(text)):
        return []  # fast pre-filter: no verb or no marker, cannot violate
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as e:
        return [f"{_display(path)}: unparsable ({e})"]
    assigned, scopes = _assigned_exprs(tree)
    parent = _parent_map(tree)
    lines = text.splitlines()
    hits: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _is_direct_open(node):
            continue
        if _nested_in_mediated(node, parent):
            continue
        lineno = getattr(node, "lineno", 1)
        snippet = lines[lineno - 1].strip() if lineno - 1 < len(lines) else ""
        if _HASH_LINE.search(snippet):
            continue
        candidates = _call_strings(node, assigned, scopes)
        if any(PY_BARE.search(candidate) for candidate in candidates):
            hits.append(f"{_display(path)}:{lineno}: {snippet}")
    return hits


def check_js_file(path: pathlib.Path) -> list[str]:
    """Raw fetch() of data URLs outside fetch_json.js (regex; no JS AST)."""
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
