# tools/tests/test_parse_guard.py — cheap structural guard over the whole tree.
#
# I have now orphaned a closing `"""` in a test module THREE times (Session 1
# twice, Session 3 once). Each time the module failed to parse, and each time I
# found out from a confusing error rather than from a check. The cause is always
# the same: I open a docstring with `#` comments and leave the closing `"""` as an
# orphan, or an em-dash inside a string that is not actually a string.
#
# `ast.parse` on every .py file costs milliseconds and would have caught all
# three at the point of writing. So: do that, in CI, forever.
#
# LICENCE: project code, Apache-2.0.
from __future__ import annotations

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]

SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache",
             "work", "public", "sources"}

PY_FILES = sorted(
    p for p in ROOT.rglob("*.py")
    if not any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts)
)


def _rel(p: pathlib.Path) -> str:
    return p.relative_to(ROOT).as_posix()


def test_there_are_python_files_to_check():
    """A guard that silently checks nothing is worse than no guard."""
    assert len(PY_FILES) >= 20, f"only found {len(PY_FILES)} .py files"


def test_every_python_file_parses():
    """The whole point. One failure names the file and the line."""
    broken: list[str] = []
    for p in PY_FILES:
        try:
            ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
        except SyntaxError as e:
            broken.append(f"{_rel(p)}:{e.lineno}: {e.msg}")
        except UnicodeDecodeError as e:
            broken.append(f"{_rel(p)}: not valid UTF-8 ({e})")
    assert not broken, "files that do not parse:\n  " + "\n  ".join(broken)
chr(34) * 3


def test_tool_modules_all_have_a_license_line():
    """Apache-2.0 project code. A new module without the line is a review miss."""
    missing: list[str] = []
    for p in PY_FILES:
        if "__init__.py" in p.name:
            continue
        head = "\n".join(p.read_text(encoding="utf-8").splitlines()[:60])
        if "LICENCE: project code, Apache-2.0" not in head:
            missing.append(_rel(p))
    assert not missing, ("module(s) missing the Apache-2.0 LICENCE header:\n  "
                         + "\n  ".join(missing))
