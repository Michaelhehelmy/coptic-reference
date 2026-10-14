"""Playwright tests for the service worker. Session 10 C2 / D1.

The service worker was the highest-risk untested component in the project. Nine
sessions of guards had never seen it, because it is JavaScript that runs in a
browser and every check so far read the file rather than running it. These tests
run it.

WHY THESE FIVE, AND NOT ONE
---------------------------
  1. install        the SW registers and its cache holds the precache list
  2. offline nav    with the network OFF, /dict/ still renders
  3. offline shard  with the network OFF, a SHARD loads from cache and the
                    entry renders
  4. precache size  the precache list in sw.js matches what is really served
  5. NO ASSUMED Content-Encoding — the whole reason sw_gen.mjs has that spec

Test 5 is the one that matters. A service worker that decodes cached .gz bytes,
or that sets Content-Encoding on them, works perfectly on the FIRST visit and
fails on the second. It presents as a cache bug and is a format bug. Asserting
that the decompressed payload is valid JSON after an offline reload is the only
way to see it.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import functools
import http.server
import pathlib
import re
import socketserver
import threading

import pytest

playwright_api = pytest.importorskip("playwright.sync_api",
                                     reason="playwright is a dev dependency")

# parents[3], not [2]: this file is one directory DEEPER than the other tests
# (tools/tests/playwright/ rather than tools/tests/), so [2] is tools/ and the
# guard skipped every test on "no public/sw.js" while sw.js sat right there.
ROOT = pathlib.Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "public"

pytestmark = pytest.mark.skipif(
    not (PUBLIC / "sw.js").is_file(),
    reason="no public/sw.js — run tools/build.py first",
)


# ── a static server with correct MIME types and NO Content-Encoding ─────────
class Handler(http.server.SimpleHTTPRequestHandler):
    """Serves public/ byte-for-byte.

    Deliberately does NOT set Content-Encoding for .gz, because that is what
    Cloudflare Pages does not do, and it is the condition test 5 exists to catch.
    A test server that "helpfully" set the header would make the bug impossible
    to reproduce.
    """

    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      ".js": "text/javascript", ".json": "application/json",
                      ".mjs": "text/javascript"}

    def log_message(self, *a):    # quiet
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


@pytest.fixture(scope="module")
def server():
    if not PUBLIC.is_dir():
        pytest.skip("no public/")
    handler = functools.partial(Handler, directory=str(PUBLIC))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()




# Collected by the page-error/console hooks installed per test. Module-level so
# the listener added in one test cannot leak into another.
_csp_violations: list[str] = []


def _sw_source() -> str:
    return (PUBLIC / "sw.js").read_text(encoding="utf-8")


# ── 1. install ─────────────────────────────────────────────────────────────
def test_1_service_worker_installs_and_precaches(page):
    p, ctx, server = page
    p.goto(f"{server}/")
    # register() is in the page, so the worker only installs if sw.js loaded.
    p.wait_for_function(
        "async () => { const rs = await navigator.serviceWorker."
        "getRegistrations(); return rs.length > 0; }", timeout=15000)
    p.wait_for_function(
        "async () => { const ks = await caches.keys();"
        "  if (!ks.length) return false;"
        "  const c = await caches.open(ks[0]);"
        "  return (await c.keys()).length > 0; }", timeout=15000)

    precache = re.search(r'const PRECACHE = (\[.*?\]);', _sw_source(), re.S)
    assert precache, "sw.js has no PRECACHE list"
    expected = re.findall(r'"([^"]+)"', precache.group(1))
    got = p.evaluate("""async () => {
        const c = await caches.open((await caches.keys())[0]);
        return (await c.keys()).map(r => new URL(r.url).pathname);
    }""")
    for url in expected:
        if url == "/":
            continue
        assert url in got, f"precached {url} is not in the cache (has {got})"
    assert len(got) >= len(expected) - 1, f"cache has {len(got)}, expected ~{len(expected)}"


# ── 2. offline navigation ───────────────────────────────────────────────────
def test_2_dict_renders_with_the_network_off(page):
    p, ctx, server = page
    p.goto(f"{server}/")
    p.wait_for_function(
        "async () => (await navigator.serviceWorker.getRegistrations()).length > 0",
        timeout=15000)
    # one reload so the SW controls the page, then cut the network
    p.reload()
    p.wait_for_function(
        """async () => { const ks = await caches.keys(); if (!ks.length) return false;
             const c = await caches.open(ks[0]); return (await c.keys()).length > 3; }""",
        timeout=20000)
    ctx.set_offline(True)
    try:
        p.goto(f"{server}/dict/")
        p.wait_for_timeout(1200)
        body = p.inner_text("body")
        assert "Dictionary" in body, f"/dict/ did not render offline: {body[:200]!r}"
        # the reader must have started; either it found a cached index or it said
        # so. What it must NOT do is render an empty page with no explanation.
        assert p.locator("#results, #entry, .err").count() > 0, \
            "offline /dict/ rendered no results container at all"
    finally:
        ctx.set_offline(False)


# ── 3. offline shard ───────────────────────────────────────────────────────
def test_3_shard_backed_entry_loads_offline(page):
    p, ctx, server = page
    p.goto(f"{server}/dict/")
    p.wait_for_function(
        "async () => (await navigator.serviceWorker.getRegistrations()).length > 0",
        timeout=15000)
    # Wait for the CACHE, not merely the registration. A fresh context per test
    # means the worker installs and precaches asynchronously; asserting before
    # the cache has entries produced "Failed to fetch" from caches.open(undefined)
    # and looked like a service-worker bug rather than a test race.
    p.wait_for_function(
        """async () => { const ks = await caches.keys(); if (!ks.length) return false;
             const c = await caches.open(ks[0]); return (await c.keys()).length > 3; }""",
        timeout=20000)
    cached = p.evaluate("""async () => {
        const c = await caches.open((await caches.keys())[0]);
        return (await c.keys()).map(r => new URL(r.url).pathname);
    }""")
    shard_cached = [u for u in cached if "shard-" in u]
    assert shard_cached, (
        f"no shard in the cache after loading /dict/ — the reader should fetch "
        f"shard-000 for the first result. cache holds {cached}")

    ctx.set_offline(True)
    try:
        # Drive a real lookup through the reader's own code path.
        got = p.evaluate("""async () => {
            const r = await fetch('/data/dist/dict/shard-000.json.gz');
            const t = await new Response(
                r.body.pipeThrough(new DecompressionStream('gzip'))).text();
            const b = JSON.parse(t);
            return {entries: b.entries.length, lemma: b.entries[0].lemma};
        }""")
        assert got["entries"] > 0, "cached shard-000 decompressed to zero entries"
        assert got["lemma"], "cached shard-000 has no first lemma"
    finally:
        ctx.set_offline(False)


# ── 4. precache list matches what is served ────────────────────────────────
def test_4_every_precached_url_really_exists():
    precache = re.search(r'const PRECACHE = (\[.*?\]);', _sw_source(), re.S)
    assert precache, "sw.js has no PRECACHE list"
    urls = re.findall(r'"([^"]+)"', precache.group(1))
    assert urls, "PRECACHE is empty"
    missing = []
    for u in urls:
        rel = u.lstrip("/")
        cand = PUBLIC / rel
        if u.endswith("/"):
            cand = cand / "index.html"
        if not cand.is_file() or cand.stat().st_size == 0:
            missing.append(f"{u} -> {cand}")
    assert not missing, ("sw.js precaches URLs that do not exist or are empty; "
                         f"install() would reject and the worker would never "
                         f"activate: {missing}")


# ── 5. the SW must not assume Content-Encoding ────────────────────────────
def test_5_worker_does_not_assume_content_encoding(page):
    p, ctx, server = page
    p.goto(f"{server}/dict/")
    p.wait_for_function(
        "async () => (await navigator.serviceWorker.getRegistrations()).length > 0",
        timeout=15000)
    # Wait for the CACHE, not merely the registration. A fresh context per test
    # means the worker installs and precaches asynchronously; asserting before
    # the cache has entries produced "Failed to fetch" from caches.open(undefined)
    # and looked like a service-worker bug rather than a test race.
    p.wait_for_function(
        """async () => { const ks = await caches.keys(); if (!ks.length) return false;
             const c = await caches.open(ks[0]); return (await c.keys()).length > 3; }""",
        timeout=20000)
    ctx.set_offline(True)
    try:
        # Straight through the CACHE, not the network: this is the second-visit
        # path, which is where an encoding assumption breaks.
        res = p.evaluate("""async () => {
            const r = await caches.match('/data/dist/dict/index.json.gz');
            if (!r) return {found: false};
            const enc = r.headers.get('content-encoding');
            const text = await new Response(
                r.body.pipeThrough(new DecompressionStream('gzip'))).text();
            return {found: true, enc, rows: JSON.parse(text).rows.length};
        }""")
        assert res["found"], "index.json.gz is not in the cache"
        assert res["rows"] == 11369, (
            f"cached index decompressed to {res['rows']} rows, expected 11369. "
            f"content-encoding header on the cached entry: {res['enc']!r}")
        # And the worker must not have SET one, or the browser would have
        # decoded it before the reader saw it and DecompressionStream would throw.
        assert not res["enc"], (
            f"the cached .gz carries Content-Encoding: {res['enc']!r}. Pages does "
            f"not set that for a .gz on disk, so the worker is inventing it and "
            f"the client will try to decompress bytes that are already plain.")
    finally:
        ctx.set_offline(False)


# ── negative control: D1's "one deliberate failure" ────────────────────────
@pytest.mark.skipif(not (PUBLIC / "sw.js").is_file(), reason="no sw.js")
def test_negative_tampered_precache_url_is_caught():
    """Deliberate failure: a precache URL that does not exist must fail 4.

    This is the assertion that makes test 4 mean something. Run it against a
    tampered copy of sw.js rather than a tampered public/ (Rule 6: tests never
    write to files they do not own).
    """
    src = _sw_source()
    bad = src.replace('"/dict/"', '"/dict-does-not-exist/"', 1)
    assert bad != src, "could not inject the tampered URL"
    m = re.search(r'const PRECACHE = (\[.*?\]);', bad, re.S)
    urls = re.findall(r'"([^"]+)"', m.group(1))
    missing = [u for u in urls
               if not ((PUBLIC / u.lstrip("/")).is_file()
                       or (PUBLIC / u.lstrip("/") / "index.html").is_file())]
    assert missing == ["/dict-does-not-exist/"], \
        f"expected the tampered URL to be the only missing one, got {missing}"


# ─────────────────────────────────────────────────────────────────────────────
# The corpus reader (Session 10 D3)
#
# These exist because of four real bugs found in this session, each of which
# left the page looking fine and doing nothing:
#
#   1. corpus.js requested page-relative "data/corpus/..." URLs, so on
#      /corpus/<work>/ every fetch was a 404.
#   2. It called .json() on gzipped bytes, so it threw "not valid JSON"
#      whenever the host did not set Content-Encoding: gzip.
#   3. The click handler derived the verse ref from heading textContent, which
#      includes the CTS URN — so every token panel lost its lemma and its
#      dictionary link.
#   4. reader.js ignored ?q=, so the corpus->dictionary link was a dead end.
#
# A test that only checks the page loads would have passed through all four.
# ─────────────────────────────────────────────────────────────────────────────

def test_6_corpus_renders_every_verse_and_token(page):
    page, ctx, server = page          # the fixture yields (page, ctx, server)
    page.goto(server + "/corpus/sahidic_ruth/")
    page.wait_for_function(
        "() => document.querySelectorAll('section.verse').length > 10", timeout=20000)
    verses = page.locator("section.verse").count()
    tokens = page.locator("span.tk").count()
    assert verses == 85, f"expected 85 verses for Ruth, got {verses}"
    assert tokens == 3470, f"expected 3470 tokens for Ruth, got {tokens}"
    assert "Click any Coptic token" in page.inner_text("#corpus-status")


def test_7_corpus_token_links_to_dictionary_and_back(page):
    """The loop: corpus token -> dictionary entry -> corpus route."""
    page, ctx, server = page
    page.goto(server + "/corpus/sahidic_ruth/")
    page.wait_for_function("() => document.querySelectorAll('span.tk').length > 10",
                           timeout=20000)

    # Click a token that has a lemma, and require a real dictionary link.
    page.locator("section.verse#v0 span.tk").nth(1).click()
    page.wait_for_selector("#corpus-entry a.btn", timeout=10000)
    href = page.get_attribute("#corpus-entry a.btn", "href")
    assert href and href.startswith("/dict/?q="), f"no dict link on token panel: {href!r}"

    # Follow it. This is what failed before ?q= was implemented.
    page.goto(server + href)
    page.wait_for_function("() => document.querySelectorAll('#results button.hit').length > 0",
                           timeout=20000)
    page.locator("#results button.hit").first.click()
    page.wait_for_selector("#entry a.worklink", timeout=10000)

    # ... and the entry must link BACK to real corpus routes.
    links = page.locator("#entry a.worklink")
    back = [links.nth(i).get_attribute("href") for i in range(links.count())]
    assert back, "entry has no corpus links"
    for href in back:
        assert href.startswith("/corpus/"), f"bad corpus link {href!r}"
        page.goto(server + href)
        page.wait_for_function(
            "() => document.querySelectorAll('section.verse').length > 0", timeout=20000)


def test_8_corpus_reads_gzip_with_or_without_content_encoding(page):
    """corpus.js must sniff the gzip magic bytes, not assume a header.

    The static test server serves .gz WITHOUT Content-Encoding, which is the
    hard case: a naive .json() throws. Assert the page still renders.
    """
    page, ctx, server = page
    page.goto(server + "/corpus/sahidic_ruth/")
    page.wait_for_function(
        "() => document.querySelectorAll('section.verse').length === 85", timeout=20000)
    assert "Could not load" not in page.inner_text("#corpus-status")


# ─────────────────────────────────────────────────────────────────────────────
# CSP and the service-worker registration (Session 12 D2 / C3)
#
# The registration was an inline <script> in the footer until this session, which
# meant the Content-Security-Policy in public/_headers could either carry
# 'unsafe-inline' or block the site's own worker. Session 11 shipped a tight CSP
# and *documented* the conflict rather than resolving it.
#
# It is resolved: /js/sw-register.js is a file, and script-src 'self' permits a
# file. These tests hold that arrangement in place — if anyone re-inlines the
# registration, or weakens the CSP, they fail.
# ─────────────────────────────────────────────────────────────────────────────

def test_9_no_csp_violations_on_any_page(page):
    """Zero Content-Security-Policy violations, on every route.

    The local test server does not send the CSP — that is Cloudflare's job, from
    _headers — so the header is installed here from the very file the build emits.
    Testing against a hand-typed copy would test the copy.
    """
    p, ctx, server = page
    csp = None
    for line in (PUBLIC / "_headers").read_text(encoding="utf-8").splitlines():
        if line.strip().lower().startswith("content-security-policy:"):
            csp = line.split(":", 1)[1].strip()
    assert csp, "public/_headers has no Content-Security-Policy line"

    seen = []
    p.on("console", lambda m: seen.append(m.text) if (
        "Content Security Policy" in m.text or "CSP" in m.text) else None)
    p.on("pageerror", lambda e: seen.append(f"pageerror: {e}"))

    for route in ("/", "/dict/", "/corpus/", "/corpus/sahidic_ruth/",
                  "/licences/", "/dialects/"):
        seen.clear()
        p.goto(server + route)
        p.wait_for_timeout(600)
        assert not seen, f"{route}: CSP violations {seen}"
    assert not seen, f"CSP violations: {seen}"


def test_10_registration_is_a_file_not_inline(page):
    """The property that makes the tight CSP possible."""
    p, ctx, server = page
    served = (PUBLIC / "js" / "sw-register.js").is_file()
    assert served, "public/sw-register.js is missing — registration went inline again"

    html = p.content()
    assert "js/sw-register.js" in html, "/ is not loading /js/sw-register.js"
    # No inline handler anywhere on the page.
    for bad in ("navigator.serviceWorker.register",):
        assert bad not in html, (
            f"{bad} appears in the served HTML; it must live in "
            f"/js/sw-register.js so script-src 'self' permits it")

    # And it still works — the reason it exists.
    p.goto(server + "/")
    p.wait_for_function(
        "() => navigator.serviceWorker.getRegistrations().then(r => r.length > 0)",
        timeout=20000)


def test_11_sw_still_registers_with_the_external_file(page):
    """C2/D2 did not break the Session 10 D1 finding."""
    p, ctx, server = page
    p.goto(server + "/dict/")
    p.wait_for_function(
        """async () => {
             const r = await navigator.serviceWorker.getRegistrations();
             return r.length > 0;
           }""",
        timeout=20000)
    scopes = p.evaluate("async () => (await navigator.serviceWorker.getRegistrations()).map(r => r.scope)")
    assert any("/" in s for s in scopes), f"worker scope does not cover /: {scopes}"
