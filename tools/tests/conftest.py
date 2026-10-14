"""Session 9 C2. Rule 6: tests never write to files they do not own.

`tools/sources.lock` is the pinned provenance of every source the pipeline
depends on. If a test mutates it, every later test and every guard in the same
session sees the mutated tree, and the damage gets attributed to whatever ran
next — which is how a corruption becomes a mystery.

So the lock's SHA-256 is captured at session start and re-checked at teardown, and
a difference fails the session. The same discipline as Rule 3 on the build side,
at a different boundary: a write that reports success is a claim, and a read-back
is evidence.
"""
from __future__ import annotations

import hashlib
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
LOCK = ROOT / "tools" / "sources.lock"


def _sha(p: pathlib.Path) -> str | None:
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except OSError:
        return None


@pytest.fixture(scope="session", autouse=True)
def sources_lock_unchanged():
    """Assert tools/sources.lock is byte-identical at session teardown."""
    before = _sha(LOCK)
    yield
    after = _sha(LOCK)
    if before is None:
        return
    if after != before:
        # Deliberately NOT restoring it. Silently reverting would hide the fact
        # that something wrote to a file it does not own, which is the entire
        # point of the rule.
        raise AssertionError(
            f"tools/sources.lock CHANGED during the test session "
            f"(Rule 6):\n"
            f"  at session start: {before}\n"
            f"  at teardown:      {after}\n"
            f"  A test wrote to a pinned artefact it does not own. The change "
            f"has NOT been reverted, so it is visible in `git diff` -- fix the "
            f"test, then decide deliberately whether the lock edit was intended.")

# LICENCE: project code, Apache-2.0.
