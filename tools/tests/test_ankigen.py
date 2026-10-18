# tools/tests/test_ankigen.py — the decks must be real Anki collections.
#
# Session 22 D2 / C4. The Playwright test proves the published routes serve
# zip bytes; this file opens the collections themselves and checks what a
# learner would actually receive: note counts, deck names, the attribution
# field, and stable guids. Uses stdlib zipfile + sqlite3 (Anki's collection
# is a sqlite database), so it does not depend on genanki at test time even
# though the emitter does.
#
# LICENCE: project code, Apache-2.0.
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys
import tempfile
import zipfile

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
ANKI = ROOT / "work" / "anki"

pytestmark = pytest.mark.skipif(
    not ANKI.is_dir(), reason="no work/anki — run tools/emit/ankigen.py")

VOCAB_DECK_ID = 2059400110
DRILL_DECK_ID = 2059400111


def _open_collection(name: str) -> tuple[sqlite3.Connection, pathlib.Path]:
    """Extract collection.anki2 from the .apkg and open it read-only."""
    apkg = ANKI / name
    tmpdir = pathlib.Path(tempfile.mkdtemp(prefix="apkg-"))
    with zipfile.ZipFile(apkg) as z:
        assert "collection.anki2" in z.namelist(), f"{name} lacks a collection"
        z.extract("collection.anki2", tmpdir)
    conn = sqlite3.connect(tmpdir / "collection.anki2")
    return conn, tmpdir


@pytest.mark.parametrize("name,deck_id,deck_name,min_notes", [
    ("vocab.apkg", VOCAB_DECK_ID, "Coptic Reference::Vocabulary", 250),
    ("drill.apkg", DRILL_DECK_ID, "Coptic Reference::Cloze Drills", 2000),
])
def test_deck_opens_with_the_expected_notes(name, deck_id, deck_name, min_notes):
    conn, tmpdir = _open_collection(name)
    try:
        n = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
        assert n >= min_notes, f"{name} has only {n} notes"
        decks = json.loads(conn.execute("SELECT decks FROM col").fetchone()[0])
        names = {d["name"] for d in decks.values() if isinstance(d, dict)}
        assert deck_name in names, f"{deck_name} not in {names}"
        ids = {int(k) for k in decks}
        assert deck_id in ids, f"deck id {deck_id} not in {ids}"
    finally:
        conn.close()
        for p in sorted(tmpdir.rglob("*"), reverse=True):
            p.unlink(missing_ok=True)
        tmpdir.rmdir()


def test_vocab_cards_carry_the_gloss_and_attribution():
    conn, tmpdir = _open_collection("vocab.apkg")
    try:
        row = conn.execute("SELECT flds FROM notes LIMIT 1").fetchone()
        assert row, "vocab deck has no notes"
        fields = row[0].split("\x1f")
        assert len(fields) == 3, f"expected 3 fields, got {len(fields)}"
        assert "CC BY-SA 4.0" in fields[2], "attribution missing from Notes"
        assert "Kaikki" in fields[2] or "CCL" in fields[2]
    finally:
        conn.close()
        for p in sorted(tmpdir.rglob("*"), reverse=True):
            p.unlink(missing_ok=True)
        tmpdir.rmdir()


def test_cloze_cards_carry_a_blank_and_a_dictionary_link():
    conn, tmpdir = _open_collection("drill.apkg")
    try:
        rows = conn.execute("SELECT flds FROM notes LIMIT 5").fetchall()
        assert rows, "drill deck has no notes"
        fronts = [r[0].split("\x1f")[0] for r in rows]
        assert any("[ …… ]" in f for f in fronts), "no cloze blank in sampled cards"
        backs = [r[0].split("\x1f")[1] for r in rows]
        assert any("/dict/?q=" in b for b in backs), "no dictionary link in sampled backs"
    finally:
        conn.close()
        for p in sorted(tmpdir.rglob("*"), reverse=True):
            p.unlink(missing_ok=True)
        tmpdir.rmdir()


def test_guids_are_unique_across_the_vocab_deck():
    conn, tmpdir = _open_collection("vocab.apkg")
    try:
        guids = [r[0] for r in conn.execute("SELECT guid FROM notes")]
        assert len(guids) == len(set(guids)), "duplicate guids — cards would merge in Anki"
    finally:
        conn.close()
        for p in sorted(tmpdir.rglob("*"), reverse=True):
            p.unlink(missing_ok=True)
        tmpdir.rmdir()
