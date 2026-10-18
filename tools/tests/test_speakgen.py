# tools/tests/test_speakgen.py — the /speak/ word list must be defensible.
#
# Session 22 D1. Frequency-ranked means ranked by corpus occurrences summed
# from the dictionary's own corpus_refs — not hand-picked. These tests pin
# the order, the shape, the collation, and the no-IPA decision.
#
# LICENCE: project code, Apache-2.0.
from __future__ import annotations

import gzip
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEAK_GZ = ROOT / "data" / "dist" / "speak" / "speak.json.gz"
TOP100_HTML = ROOT / "work" / "speak" / "top100.html"

pytestmark = pytest.mark.skipif(
    not SPEAK_GZ.is_file(),
    reason="no data/dist/speak — run tools/emit/speakgen.py")


def _payload() -> dict:
    return json.loads(gzip.decompress(SPEAK_GZ.read_bytes()))


def test_shape_and_count():
    d = _payload()
    assert d["schema"] == "coptic-reference/speak/1"
    assert d["count"] == 100
    assert len(d["words"]) == 100


def test_words_are_sorted_by_occurrences_descending():
    words = _payload()["words"]
    occs = [w["occurrences"] for w in words]
    assert occs == sorted(occs, reverse=True), "word list is not frequency-ranked"
    assert occs[0] >= occs[-1] > 0


def test_every_word_carries_the_three_selector_schemes():
    for w in _payload()["words"]:
        assert set(w["translit"]) == {"bohairic", "sahidic", "layton"}, w["lemma"]
        assert w["lemma"], "empty lemma in the word list"
        assert w["norm_key"], f"{w['lemma']} has no norm_key (no dictionary link)"
        assert w["gloss"], f"{w['lemma']} has no gloss"


def test_no_ipa_field_is_emitted():
    """No dictionary entry carries IPA, so the payload must not pretend
    otherwise with an empty or invented field (Session 22 D1)."""
    for w in _payload()["words"]:
        assert "ipa" not in w, f"{w['lemma']} claims IPA without a source"


def test_collation_matches_the_dictionary():
    d = _payload()
    idx = json.loads(gzip.decompress(
        (ROOT / "data" / "dist" / "dict" / "index.json.gz").read_bytes()))
    assert d["collation_hash"] == idx["collation_hash"]


def test_standalone_no_js_page_carries_every_word():
    """work/speak/top100.html is the no-JS fallback. It must be a complete
    document (not a fragment — nothing frames it) and contain every lemma
    from the payload, in the same order, with zero <script> tags."""
    page = TOP100_HTML.read_text(encoding="utf-8")
    assert page.startswith("<!doctype html>"), "not a standalone document"
    assert "<script" not in page.lower(), "the no-JS page must not need JS"
    for w in _payload()["words"]:
        assert w["lemma"] in page, f"{w['lemma']} missing from top100.html"
    # Rows are emitted in rank order; lemma 1 appears before lemma 2.
    first, second = _payload()["words"][0]["lemma"], _payload()["words"][1]["lemma"]
    assert page.index(first) < page.index(second), "rows are not in rank order"
