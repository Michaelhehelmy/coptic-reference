"""tools/tests/playwright/test_typed_coptic.py — typed Coptic round-trips end to end.

LICENCE: project code, Apache-2.0.

Session 26 D0.3. E39 claimed "exact Coptic cannot be typed through this
interface". Session 26 D0.1/D0.2 disproved the mechanism: the write tool,
the filesystem, Playwright typing, and the live deployment all round-trip
the codepoints they are given. The mangling was the agent constructing
hex escapes from memory (`\\u2c89` for ⲩ — U+2CA9 — and friends). The
guard is therefore two-sided:

  * the browser surface is proven with a real typing test (this file);
  * the construction rule is proven by never hand-typing the word here —
    it is read from the shipped dictionary index.

`/dict/` `#q` is the only typed-Coptic input on the site: /write/ uses
<select>, /speak/ has no input, /corpus/ has no search box. Typing does
not produce a network query by design (the index is fetched once and
filtered client-side); the encoding-critical hop is the ?q= deep link,
which this file exercises with urllib.parse.quote, never a literal.
"""
from __future__ import annotations

import functools
import gzip
import http.server
import json
import pathlib
import socketserver
import threading
import urllib.parse

import pytest

playwright_api = pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "public"
INDEX = PUBLIC / "data" / "dist" / "dict" / "index.json.gz"

pytestmark = pytest.mark.skipif(
    not INDEX.is_file(), reason="no dictionary index — run tools/build.py first")


class _Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript",
        ".json": "application/json",
    }

    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def origin():
    if not PUBLIC.is_dir():
        pytest.skip("no public/")
    httpd = socketserver.TCPServer(
        ("127.0.0.1", 0), functools.partial(_Handler, directory=str(PUBLIC)))
    httpd.daemon_threads = True
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()
        httpd.server_close()


def _lemma() -> str:
    """ⲧⲉⲛⲟⲩ, read from the shipped index — never constructed by hand."""
    with gzip.open(INDEX, "rt", encoding="utf-8") as f:
        idx = json.load(f)
    for row in idx["rows"]:
        if row["lemma"] == "ⲧⲉⲛⲟⲩ":
            return row["lemma"]
    pytest.fail("ⲧⲉⲛⲟⲩ not in the dictionary index")


@pytest.fixture
def page(browser, origin):
    ctx = browser.new_context(service_workers="allow")
    p = ctx.new_page()
    p.goto(origin + "/dict/", wait_until="networkidle")
    p.wait_for_function(
        "() => document.getElementById('count-all') && "
        "!document.getElementById('count-all').textContent.includes('Loading')",
        timeout=25000)
    yield p, ctx, origin
    ctx.close()


def test_typed_coptic_round_trips_and_finds_the_entry(page):
    """Type ⲧⲉⲛⲟⲩ: exact codepoints in, the right entry out, no mangling."""
    p, ctx, origin = page
    word = _lemma()
    p.locator("#q").click()
    p.locator("#q").press_sequentially(word, delay=30)
    p.wait_for_timeout(800)

    typed = p.evaluate("() => document.getElementById('q').value")
    assert [hex(ord(c)) for c in typed] == [hex(ord(c)) for c in word], (
        "the input box mangled the typed codepoints")

    hits = p.locator("#results button.hit")
    assert hits.count() == 1, (
        f"expected exactly 1 hit for {word!r}, got {hits.count()} — "
        "a wrong codepoint would silently produce zero (E39's real failure mode)")
    assert word in hits.first.inner_text()

    hits.first.click()
    p.wait_for_selector("#entry h2", timeout=10000)
    assert p.inner_text("#entry h2").strip() == word
    body = p.inner_text("#entry")
    assert "[object Object]" not in body
    assert "object Object" not in body
    # The gloss for ⲧⲉⲛⲟⲩ is "now" — proves the RIGHT row rendered.
    assert "now" in body.lower()


def test_deep_link_q_encodes_and_opens_the_entry(page):
    """The ?q= hop: urllib-encoded word, entry opens, no mangled characters."""
    p, ctx, origin = page
    word = _lemma()
    encoded = urllib.parse.quote(word)
    assert encoded == "%E2%B2%A7%E2%B2%89%E2%B2%9B%E2%B2%9F%E2%B2%A9", (
        "the quote() of the index lemma no longer matches the documented "
        "percent-encoding — the lemma changed, update the E39 receipt")
    p.goto(f"{origin}/dict/?q={encoded}", wait_until="networkidle")
    p.wait_for_function(
        "() => document.querySelector('#results button.hit')", timeout=25000)
    p.locator("#results button.hit").first.click()
    p.wait_for_selector("#entry h2", timeout=10000)
    assert p.inner_text("#entry h2").strip() == word
    assert "[object Object]" not in p.inner_text("#entry")


def test_fill_paste_equivalent_round_trips(page):
    """fill() is the paste path — same fidelity as typing."""
    p, ctx, origin = page
    word = _lemma()
    p.locator("#q").fill(word)
    p.wait_for_timeout(700)
    typed = p.evaluate("() => document.getElementById('q').value")
    assert [hex(ord(c)) for c in typed] == [hex(ord(c)) for c in word]
    assert p.locator("#results button.hit").count() == 1


def test_dict_is_the_only_typed_coptic_surface(origin):
    """Surface inventory: no other page offers a free-text Coptic input.

    /write/ uses <select>, /speak/ has no input, /corpus/ has no search
    box. If a future session adds one, this inventory line must move —
    deliberately, with its own typed test.
    """
    import re
    typed_surfaces = []
    for html in PUBLIC.rglob("*.html"):
        txt = html.read_text(encoding="utf-8", errors="replace")
        if re.search(r"<input[^>]*type=[\"']?search", txt, re.I):
            typed_surfaces.append(html.relative_to(PUBLIC).as_posix())
    assert typed_surfaces == ["dict/index.html"], (
        f"typed-Coptic surface inventory changed: {typed_surfaces}")
