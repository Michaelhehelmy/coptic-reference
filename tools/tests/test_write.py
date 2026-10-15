# tools/tests/test_write.py — writing practice references (Session 21 D4).
#
# Rule 7: an SVG that exists is not a reference that resolves. These tests
# pin the generator's output to its source list, the no-JS gallery to the
# index, and every glyph to the corpus — all read-only (Rule 6: tests never
# write; writegen.py owns static/write/).
#
# LICENCE: project code, Apache-2.0.
from __future__ import annotations

import json
import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "emit"))

import writegen  # noqa: E402


def _index() -> dict:
    path = ROOT / "static" / "write" / "index.json"
    if not path.is_file():
        pytest.skip("no generated write index — run tools/emit/writegen.py")
    return json.loads(path.read_text(encoding="utf-8"))


def test_index_matches_the_generator_source():
    """The committed index is what the generator emits (all 35)."""
    index = _index()
    assert [g["glyph"] for g in index["glyphs"]] == \
        [glyph for glyph, _, _ in writegen.GLYPHS]
    assert len(index["glyphs"]) == 35


def test_every_svg_exists_and_names_its_glyph():
    index = _index()
    for entry in index["glyphs"]:
        path = ROOT / "static" / "write" / entry["file"]
        assert path.is_file(), entry["file"]
        text = path.read_text(encoding="utf-8")
        assert entry["glyph"] in text
        assert "<text" in text and "</svg>" in text


def test_no_js_gallery_matches_the_index():
    """The fallback lists the same glyphs the canvas session offers."""
    index = _index()
    template = (ROOT / "themes" / "copticref" / "layouts" / "write" /
                "list.html").read_text(encoding="utf-8")
    noscript = template.split("<noscript", 1)[1].split("</noscript>", 1)[0]
    listed = re.findall(r"<li>.*?(?:</li>)", noscript, re.S)
    assert len(listed) == len(index["glyphs"]), (len(listed), len(index["glyphs"]))
    for entry, item in zip(index["glyphs"], listed):
        assert entry["glyph"] in item, entry["glyph"]
        assert entry["file"] in item, entry["file"]


def test_reference_letters_are_corpus_attested():
    """Every tracing letter occurs in the six shipped works (or says why)."""
    import tarfile
    tarball = ROOT / "data" / "dist" / "corpus" / "corpus.tar.gz"
    if not tarball.is_file():
        pytest.skip("no corpus tarball")
    import unicodedata
    have: set[str] = set()
    with tarfile.open(tarball, "r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile() or not member.name.endswith("/tokens.json"):
                continue
            stream = archive.extractfile(member)
            assert stream is not None
            for tok in json.loads(stream.read().decode("utf-8"))["tokens"]:
                for ch in unicodedata.normalize("NFD", tok.get("form", "")):
                    if unicodedata.category(ch) not in ("Mn", "Me", "Cf"):
                        have.add(ch.lower())
    index = _index()
    for entry in index["glyphs"]:
        glyph = entry["glyph"]
        if len(glyph) == 1 and not entry.get("note"):
            assert glyph in have, f"{glyph!r} not in corpus"
