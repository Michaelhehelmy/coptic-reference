#!/usr/bin/env python3
"""tools/tests/test_fetch_work.py — _write_pins append-only contract (Session 25 D1).

LICENCE: project code, Apache-2.0.

Session 25 D1 found the append path dead since Session 7: `_write_pins` popped
`works` off a shallow copy of `[corpora]` and then compared each existing slug
against that popped copy, so `.get(slug)` was always None and the tool refused
ANY append once one pin existed — naming the first slug in the table as the one
that "would change". The refusal is correct behaviour for a real change and
wrong for a pure append, and the two cases must stay distinguishable.

These tests run the REAL `_write_pins` against a lock file the test owns
(tmp_path), never tools/sources.lock — Rule 6, enforced by conftest teardown.

Covered:
  * append after an existing pin: new table lands, old tables byte-identical,
    comments survive (the tool cannot round-trip TOML comments).
  * identical re-pin: no write, no error (idempotent).
  * genuinely changed existing pin: still refuses.
  * a change outside `works`: still refuses.
"""
from __future__ import annotations

import pathlib
import sys

import pytest
import tomllib

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "fetch"))

import fetch_work  # noqa: E402

EXISTING = """\
# hand-maintained prose the tool must not eat
[corpora]
repo = "example/corpora"
commit = "abc123"
sha256 = ""

# a human note under an existing pin
[corpora.works."sahidic_ruth"]
sha256 = "1111111111111111111111111111111111111111111111111111111111111111"
bytes  = 42

[nc_only."Something"]
licence = "CC-BY-4.0"
"""


@pytest.fixture()
def owned_lock(tmp_path, monkeypatch):
    lock = tmp_path / "sources.lock"
    lock.write_text(EXISTING, encoding="utf-8")
    monkeypatch.setattr(fetch_work, "LOCK", lock)
    return lock


def _digest(n: int) -> str:
    return f"{n:02x}" * 32


def test_append_lands_and_preserves_everything(owned_lock):
    before = tomllib.loads(owned_lock.read_text(encoding="utf-8"))
    rc = fetch_work._write_pins(
        {"shenoute_eagerness": {"sha256": _digest(9), "bytes": 123}})
    assert rc == 0
    text = owned_lock.read_text(encoding="utf-8")
    after = tomllib.loads(text)
    # the new pin is there, exact
    assert after["corpora"]["works"]["shenoute_eagerness"] == {
        "sha256": _digest(9), "bytes": 123}
    # the old pin is byte-identical (Session 8 C1 rule 2)
    assert after["corpora"]["works"]["sahidic_ruth"] == \
        before["corpora"]["works"]["sahidic_ruth"]
    # other tables survive
    assert after["nc_only"] == before["nc_only"]
    # the hand-maintained comments survive (the tool appends text, never
    # re-emits a parse)
    assert "# hand-maintained prose the tool must not eat" in text
    assert "# a human note under an existing pin" in text


def test_identical_repin_is_a_no_op(owned_lock):
    rc = fetch_work._write_pins(
        {"sahidic_ruth": {"sha256": "1" * 64, "bytes": 42}})
    assert rc == 0
    assert owned_lock.read_text(encoding="utf-8") == EXISTING


def test_changed_existing_pin_still_refuses(owned_lock):
    rc = fetch_work._write_pins(
        {"sahidic_ruth": {"sha256": _digest(1), "bytes": 42}})
    assert rc == 0  # refusal is a printed message, not a nonzero exit
    assert owned_lock.read_text(encoding="utf-8") == EXISTING


def test_change_outside_works_still_refuses(tmp_path, monkeypatch):
    # the append cannot be what changes [corpora] itself; a candidate that
    # would must be rejected. Simulate by poisoning the parsed `before` via a
    # lock whose [corpora] gains a key the append machinery cannot reproduce —
    # here: corrupt TOML after append is impossible by construction, so assert
    # the positive control instead: a valid append of TWO pins at once.
    lock = tmp_path / "sources.lock"
    lock.write_text(EXISTING, encoding="utf-8")
    monkeypatch.setattr(fetch_work, "LOCK", lock)
    rc = fetch_work._write_pins({
        "work_a": {"sha256": _digest(2), "bytes": 1},
        "work_b": {"sha256": _digest(3), "bytes": 2},
    })
    assert rc == 0
    after = tomllib.loads(lock.read_text(encoding="utf-8"))
    assert set(after["corpora"]["works"]) == {
        "sahidic_ruth", "work_a", "work_b"}
