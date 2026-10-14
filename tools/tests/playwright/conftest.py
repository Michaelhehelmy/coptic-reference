"""tools/tests/playwright/conftest.py — shared fixtures for the browser tests.

Session 10 D1. The `server` and `browser` fixtures used to live in test_sw.py,
where test_pagefind.py could not see them: pytest collects fixtures per module,
not per directory, so a second file in the same folder gets "fixture 'server' not
found" rather than reusing it.

They are shared infrastructure, so they belong here. Both test modules now use
the same server and the same browser instance.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import functools
import http.server
import pathlib
import socketserver
import threading

import pytest

playwright_api = pytest.importorskip("playwright.sync_api")

ROOT = pathlib.Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "public"


class Handler(http.server.SimpleHTTPRequestHandler):
    """Static server for the BUILT public/ tree.

    Two deliberate properties:

      * .gz is served as application/json WITHOUT Content-Encoding: gzip. Real
        hosts differ here, and a client that assumes the header breaks on this
        one. The readers sniff the gzip magic bytes instead, and
        test_8_corpus_reads_gzip_with_or_without_content_encoding covers it.

      * quiet. Pagefind and the service worker make a lot of requests; the test
        output stays readable.
    """

    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript",
        ".json": "application/json",
    }

    # Session 12 D2: serve the security headers from public/_headers, the file the
    # BUILD emits, so every browser test runs under the policy that will actually
    # be deployed. Reading the emitted file rather than a hand-typed copy is the
    # point: a copy would test the copy.
    #
    # This is why the CSP test can find violations at all — before this, the local
    # server sent no CSP, so "no violations" was true because nothing was checking.
    @classmethod
    def _headers(cls):
        f = PUBLIC / "_headers"
        if not f.is_file():
            return []
        out, active = [], False
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if not line[0].isspace():          # a path pattern begins a block
                active = True
                continue
            if ":" in line:
                k, v = line.strip().split(":", 1)
                out.append((k.strip(), v.strip()))
        return out

    def end_headers(self):
        for k, v in Handler._headers():
            self.send_header(k, v)
        super().end_headers()

    def log_message(self, *a):  # noqa: D102
        pass


@pytest.fixture(scope="module")
def browser():
    with playwright_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:                       # noqa: BLE001
            pytest.skip(f"chromium unavailable: {e}")
        try:
            yield b
        finally:
            b.close()


@pytest.fixture(scope="module")
def server(browser):                     # browser first: no point serving if absent
    if not PUBLIC.is_dir():
        pytest.skip("no public/ — run tools/build.py first")
    handler = functools.partial(Handler, directory=str(PUBLIC))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    httpd.daemon_threads = True
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()
        httpd.server_close()


@pytest.fixture
def page(browser, server):
    """Yields (page, context, base_url).

    A tuple, not a bare page: the service-worker tests need ctx to toggle
    set_offline(), and every module needs the base URL. Unpacking it explicitly
    is clearer than three near-identical fixtures.
    """
    ctx = browser.new_context(service_workers="allow")
    p = ctx.new_page()
    p.goto(server)
    yield p, ctx, server
    ctx.close()
