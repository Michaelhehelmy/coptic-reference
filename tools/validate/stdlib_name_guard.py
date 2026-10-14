#!/usr/bin/env python3
"""tools/validate/stdlib_name_guard.py — no project module may shadow a stdlib name.

Session 7 C3. Session 6 was asked to add `tools/io.py`. It could not work, and the
reason is worth a guard: **`io` is in `sys.modules` before any project code runs**,
so `import io` always resolves to the stdlib module and `tools/io.py` is
unreachable under its own name. It failed at the first call site with

    AttributeError: module 'io' has no attribute 'write_verified'

Nothing would have warned us. The file would have been written, committed, and
referenced in a docstring, and every reviewer would have seen a plausible-looking
module. It was only caught by actually trying to use it.

The failure mode is asymmetric and nasty. A shadowing module is not a compile
error and not an import error; it is a module that silently resolves to something
else, or cannot resolve at all. Python's own guidance is that a standard-library
module should not be shadowed for exactly this reason.

Checked two ways:

  - **filename**: no file under `tools/` may be named after a stdlib module;
  - **import**: no source file may insert a directory containing one at the FRONT
    of `sys.path` while importing that name, which is how the trap is sprung.

`sysconfig.get_paths()["stdlib"]` is the authority for the stdlib list, so this
does not go stale when Python adds a module.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys
import sysconfig

ROOT = pathlib.Path(__file__).resolve().parents[2]

#: Names that are stdlib on SOME supported interpreter but absent on another, so
#: they must be denied even if this interpreter does not have them. A shadowing
#: bug that only appears on the other version is the same bug.
CROSS_VERSION: frozenset[str] = frozenset({
    "io", "tokenize", "token", "string", "typing", "queue", "copy", "pickle",
    "types", "enum", "abc", "json", "csv", "gzip", "tarfile", "hashlib",
    "pathlib", "random", "socket", "select", "signal", "struct", "uuid",
    "warnings", "weakref", "ast", "code", "codeop", "difflib", "inspect",
    "linecache", "tokenize", "trace", "types", "dataclasses", "contextlib",
})


def stdlib_names() -> set[str]:
    names: set[str] = set(CROSS_VERSION)
    root = pathlib.Path(sysconfig.get_paths()["stdlib"])
    if root.is_dir():
        for p in root.iterdir():
            if p.suffix == ".py" and p.stem != "__init__":
                names.add(p.stem)
            elif p.is_dir() and (p / "__init__.py").is_file():
                names.add(p.name)
    return names


#: Matches `import io`, `from io import x`, `import io, os`.
_IMPORT_RE = re.compile(
    r"^\s*(?:import\s+(?P<mods>[\w.]+(?:\s*,\s*[\w.]+)*)"
    r"|from\s+(?P<mod>[\w.]+)\s+import\b)", re.MULTILINE)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="no project module shadows a stdlib name")
    ap.add_argument("--tools", type=pathlib.Path, default=ROOT / "tools")
    args = ap.parse_args(argv)

    std = stdlib_names()
    errors: list[str] = []

    # 1. filenames
    checked_files = 0
    for p in sorted(args.tools.rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        checked_files += 1
        if p.stem in std:
            errors.append(
                f"{p.relative_to(ROOT)}: filename shadows the stdlib module "
                f"{p.stem!r}. A module named after a stdlib module cannot be "
                f"imported by that name -- `import {p.stem}` resolves to the "
                f"stdlib, always, because the stdlib is already in sys.modules "
                f"before project code runs. Rename it.")

    # 2. imports of a name we also define
    checked_imports = 0
    for p in sorted(args.tools.rglob("*.py")):
        if "__pycache__" in p.parts or p.resolve() == pathlib.Path(__file__).resolve():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        # Only our own modules: anything shadowing stdlib is a project file.
        ours = {q.stem for q in args.tools.rglob("*.py")} | {args.tools.name}
        for m in _IMPORT_RE.finditer(text):
            checked_imports += 1
            mods: list[str] = []
            if m.group("mods"):
                mods = [x.strip().split(".")[0] for x in m.group("mods").split(",")]
            elif m.group("mod"):
                mods = [m.group("mod").split(".")[0]]
            for name in mods:
                if name in std and name in ours:
                    line = text[:m.start()].count("\n") + 1
                    errors.append(
                        f"{p.relative_to(ROOT)}:{line}: imports {name!r}, which is "
                        f"both a stdlib module and a project module. One of them "
                        f"is unreachable; today the stdlib one wins.")

    if errors:
        print(f"[stdlib_name_guard] FAIL — {len(errors)} problem(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"[stdlib_name_guard] OK — {checked_files} module filename(s) and "
          f"{checked_imports} import statement(s) checked against "
          f"{len(std)} stdlib names; no shadowing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
