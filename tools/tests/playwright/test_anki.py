"""tools/tests/playwright/test_anki.py — the decks are downloadable and real.

Session 22 D2 / C4. /anki/ is the exit path: a learner finishes the site's
course flow and carries the items into Anki. These tests load the page,
assert both download links resolve over HTTP with Anki-shaped bytes (a zip
starting with PK, containing collection.anki2), and that the licensing
note is on the page. The deck *contents* (note counts, guids, models) are
verified by tools/tests/test_ankigen.py without a browser; this file proves
the published routes serve what the emitters produced.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "public"

pytestmark = pytest.mark.skipif(
    not (PUBLIC / "anki" / "index.html").is_file(),
    reason="no published /anki/ — run tools/build.py first")


DECKS = ("quiz.apkg", "drill.apkg")


def test_anki_page_lists_both_decks_and_the_licence(browser, server):
    ctx = browser.new_context()
    p = ctx.new_page()
    p.goto(server + "/anki/")
    body = p.content()
    assert "CC BY-SA 4.0" in body
    assert "Anki is the canonical" in body or "canonical spaced-repetition" in body
    for name in DECKS:
        assert f"/downloads/anki/{name}" in body, name
    ctx.close()


@pytest.mark.parametrize("name", DECKS)
def test_deck_download_resolves_with_anki_bytes(browser, server, name):
    ctx = browser.new_context()
    resp = ctx.request.get(f"{server}/downloads/anki/{name}")
    assert resp.status == 200, f"{name}: HTTP {resp.status}"
    body = resp.body()
    assert len(body) > 1000, f"{name} is suspiciously small ({len(body)} B)"
    assert body[:2] == b"PK", f"{name} is not a zip (Anki packages are zips)"
    # collection.anki2 is the sqlite collection every .apkg carries.
    # Zip central directory holds file names as plain bytes.
    assert b"collection.anki2" in body, f"{name} lacks collection.anki2"
    ctx.close()
