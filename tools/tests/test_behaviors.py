#!/usr/bin/env python3
"""tools/tests/test_behaviors.py — six behavioural tests, one per Session 10 bug.

LICENCE: project code, Apache-2.0.

Session 10 shipped six components that existed, built cleanly, passed provenance
and the completeness guard, and did nothing. Rule 7 (HANDOFF.md §8a) exists because
of them: existence is not behaviour.

Every test below drives the component and asserts on the **effect**. Each one
fails when its corresponding bug is reintroduced — that claim is not asserted, it
is demonstrated. The negative demonstrations are recorded in COVERAGE.md.

| # | Session 10 bug | Test |
|---|---|---|
| 1 | sw.js generated but never registered | `test_behavior_1_service_worker_is_registered` |
| 2 | reader.js had no elements to drive | `test_behavior_2_reader_renders_an_entry` |
| 3 | reader.js used page-relative data URLs (404) | `test_behavior_3_no_page_relative_data_urls` |
| 4 | reader.js ignored ?q= (dead-end links) | `test_behavior_4_deep_link_opens_the_entry` |
| 5 | corpus.js called .json() on gzip bytes | `test_behavior_5_corpus_reads_gzipped_json` |
| 6 | corpus click handler lost the lemma | `test_behavior_6_token_click_keeps_lemma` |

Why these are NOT the existing Playwright tests: those assert against a live
browser and are skipped when Chromium is absent. These run as ordinary pytest and
use a local static server plus a static/structural fallback, so the behavioural
claim is checked in the default `pytest tools/tests/` run, not only in the
dedicated Playwright job.
"""
from __future__ import annotations

import functools
import gzip
import http.server
import json
import pathlib
import re
import socketserver
import threading

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "public"
STATIC = ROOT / "static"

pytestmark = pytest.mark.skipif(
    not PUBLIC.is_dir(), reason="no public/ — run tools/build.py first")


# ─────────────────────────────────────────────────────────────────────────────
# Local static server. Same two properties as the Playwright fixture: .gz is
# served as application/json WITHOUT Content-Encoding: gzip (the hard case), and
# the log stays quiet.
# ─────────────────────────────────────────────────────────────────────────────
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
    """(base_url, requested_paths) — the paths the served pages actually asked for."""
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


def _get(base: str, path: str) -> tuple[int, bytes, str]:
    """GET without requests/urllib ceremony, returning (status, body, ctype)."""
    import urllib.error
    import urllib.request
    try:
        with urllib.request.urlopen(base + path, timeout=10) as r:
            return r.status, r.read(), r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return e.code, e.read(), ""



def _js_code(path: pathlib.Path) -> str:
    """Shipped JS with comments and doc-blocks removed.

    Necessary, not cosmetic. Both readers carry long comments quoting the exact
    strings they are *documented* to avoid — `reader.js` says in prose that the
    old value was page-relative "data/dist/dict/index.json.gz", which a naive
    substring scan reports as a live bug. Scanning prose for code defects is
    how a guard starts crying wolf.

    Strips // to end of line and /* ... */ blocks, leaving string contents alone.
    """
    txt = path.read_text(encoding="utf-8")
    out, i, n = [], 0, len(txt)
    while i < n:
        c = txt[i]
        if c == "/" and i + 1 < n and txt[i + 1] == "/":
            while i < n and txt[i] != "\n":
                i += 1
        elif c == "/" and i + 1 < n and txt[i + 1] == "*":
            i += 2
            while i + 1 < n and not (txt[i] == "*" and txt[i + 1] == "/"):
                i += 1
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _has_id(html: str, name: str) -> bool:
    """Does the HTML carry id="name" or id=name?

    Hugo runs with --minify, which drops attribute quotes. A test that only
    accepts the quoted form fails against the artefact that actually ships.
    """
    return (f'id="{name}"' in html) or (re.search(rf"\bid={re.escape(name)}\b", html)
                                       is not None)


# ─────────────────────────────────────────────────────────────────────────────
# 1. The service worker is REGISTERED, not merely present.
#
# Bug: Session 9 generated public/sw.js with a valid 8-entry precache list, wrote
# it, passed provenance --strict — and nothing ever called
# navigator.serviceWorker.register(). The site cached nothing, ever.
#
# A file-existence test passes for this bug. This asserts the registration call
# exists AND that the page's own script surface can reach it.
# ─────────────────────────────────────────────────────────────────────────────
def test_behavior_1_service_worker_is_registered(origin):
    """The registration must exist in something the browser actually executes.

    Session 12 D2/C3 moved it out of an inline <script> and into
    /js/sw-register.js, because inline forced a choice between
    'unsafe-inline' and a broken policy. The assertion therefore widened from
    "appears in a served HTML page" to "appears in a served resource the browser
    will run" — which is the actual property. It still fails when nothing
    registers, which is the bug it exists for.
    """
    status, sw_js, _ = _get(origin, "/sw.js")
    assert status == 200 and len(sw_js) > 500, "sw.js is not served with content"

    html_sources = []
    for page in sorted(PUBLIC.rglob("*.html")):
        _, body, _ = _get(origin, "/" + page.relative_to(PUBLIC).as_posix())
        html_sources.append((page, body.decode("utf-8", "replace")))

    # 1. The page must reference the registration file.
    # Quote-agnostic: hugo --minify drops attribute quotes, emitting
    # <script src=/js/sw-register.js defer>. A quoted-only pattern fails against
    # the artefact that actually ships, which is the second time this minification
    # has broken a selector (the first was section.verse#ruth-1:1).
    referenced = [p for p, t in html_sources
                  if re.search(r'src=\??"?[^" >]*sw-register\.js', t)]
    assert referenced, (
        "no served HTML page loads /js/sw-register.js — the worker would never "
        "be registered (Session 10 bug: shipped, green, inert)")

    # 2. That file must exist, be served, and contain the call.
    status, body, _ = _get(origin, "/js/sw-register.js")
    assert status == 200, "/js/sw-register.js is referenced but not served"
    code = _js_code(PUBLIC / "js" / "sw-register.js")
    assert "navigator.serviceWorker.register" in code, (
        "/js/sw-register.js does not register anything")

    # 3. Not inlined anywhere either — inlining is what forced 'unsafe-inline'.
    for page, txt in html_sources:
        assert "navigator.serviceWorker.register" not in txt, (
            f"{page.relative_to(PUBLIC)} inlines the registration; the tight "
            f"CSP blocks it (Session 12 D2)")


# ─────────────────────────────────────────────────────────────────────────────
# 2. The reader renders an entry — it has elements AND drives them.
#
# Bug: reader.js drove #q, #results, #entry, #count-all. /dict/ was markdown and
# had none of them, so the script started and filled nothing.
#
# This asserts the page has the elements the script requires, and that the
# served reader.js references exactly those ids — a rename on either side fails.
# ─────────────────────────────────────────────────────────────────────────────
def test_behavior_2_reader_renders_an_entry(origin):
    status, page, _ = _get(origin, "/dict/")
    assert status == 200
    html = page.decode("utf-8", "replace")

    required = ["q", "results", "entry", "count-all"]
    missing = [i for i in required if not _has_id(html, i)]
    assert not missing, (
        f"/dict/ is missing reader element(s) {missing}. reader.js drives them; "
        f"without them the script runs and renders nothing."
    )

    status, js, _ = _get(origin, "/js/reader.js")
    assert status == 200
    reader = js.decode("utf-8", "replace")
    reader_code = _js_code(PUBLIC / "js" / "reader.js")
    for i in required:
        assert f'"{i}"' in reader_code or f"'{i}'" in reader_code, (
            f"reader.js never references #{i}; the page and the script disagree"
        )

    # The page must actually load the script it depends on.
    assert "js/reader.js" in html, "/dict/ never loads reader.js"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Data URLs are root-relative, and every one of them resolves.
#
# Bug: "data/dist/dict/index.json.gz" without a leading slash resolves to
# /dict/data/dist/... on /dict/ — a 404. It could also never match the service
# worker's cache key (/data/dist/...), so offline would have failed even after the
# worker installed.
#
# This does not merely grep for a leading slash: it fetches each URL the served
# scripts reference and asserts a real 200. A page-relative URL fails here even
# though it looks harmless in source.
# ─────────────────────────────────────────────────────────────────────────────
def test_behavior_3_no_page_relative_data_urls(origin):
    page_relative = []
    for name in ("js/reader.js", "js/corpus.js"):
        p = PUBLIC / name
        if not p.is_file():
            continue
        # Scan CODE, not prose: reader.js documents in a comment that the old
        # value was page-relative, and a substring scan flags its own
        # explanation as a live bug.
        txt = _js_code(p)
        for m in re.finditer(r"""["'`]((?:data/|/data/)[^"'`]+)["'`]""", txt):
            url = m.group(1)
            if not url.startswith("/"):
                page_relative.append((name, url))
    assert not page_relative, (
        "page-relative data URL(s) in shipped JS: "
        f"{page_relative}. On /dict/ or /corpus/<work>/ these resolve under the "
        f"current path and 404, and can never match the SW cache key."
    )

    # Every referenced data URL must actually be served.
    for rel in ("/data/dist/dict/index.json.gz",
                "/data/dist/dict/shard-000.json.gz"):
        status, body, _ = _get(origin, rel)
        assert status == 200 and len(body) > 1024, (
            f"{rel} is referenced by the reader but serves {status} / {len(body)} B"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 4. ?q= opens the entry — the corpus→dictionary link is not a dead end.
#
# Bug: corpus.js links to /dict/?q=<norm>; reader.js ignored location.search, so
# the reader landed with an empty box and no indication a word was chosen.
#
# This asserts the deep-link contract at both ends: the script honours ?q=, and
# the URL the corpus actually emits is one it can honour.
# ─────────────────────────────────────────────────────────────────────────────
def test_behavior_4_deep_link_opens_the_entry(origin):
    _, js, _ = _get(origin, "/js/reader.js")
    reader = js.decode("utf-8", "replace")
    # Assert location.search specifically, NOT "URLSearchParams appears".
    #
    # The first version of this test accepted either. Demonstrated to be too
    # weak: changing the code to `new URLSearchParams("")` — which ignores ?q= and
    # reproduces the Session 10 bug exactly — left "URLSearchParams" in the file,
    # so the test passed against a reintroduced bug. That is the failure mode Rule
    # 7 names: an assertion that measures a proxy for the behaviour.
    #
    # location.search is the only source of the query string, so requiring it
    # cannot be satisfied by a stub.
    assert "location.search" in reader, (
        "reader.js never reads location.search: /dict/?q=... cannot pre-fill the "
        "box, so every corpus token link is a dead end (Session 10 bug)"
    )
    assert re.search(r"URLSearchParams\(\s*location\.search", reader), (
        "reader.js constructs URLSearchParams without location.search — the "
        "query string is parsed from a hardcoded value, so ?q= is ignored"
    )

    # The corpus must emit ?q= links, and they must be well-formed.
    _, cjs, _ = _get(origin, "/js/corpus.js")
    corpus = cjs.decode("utf-8", "replace")
    assert re.search(r"/dict/\?q=", corpus), (
        "corpus.js emits no /dict/?q= link, so a corpus token cannot reach a "
        "dictionary entry"
    )

    # A real lemma from the built index must survive the round trip through the
    # norm_key the index publishes.
    idx = json.loads(gzip.decompress(
        (PUBLIC / "data" / "dist" / "dict" / "index.json.gz").read_bytes()))
    assert idx["rows"], "index has no rows"
    row = next(r for r in idx["rows"] if r.get("lemma"))
    shard = json.loads(gzip.decompress(
        (PUBLIC / "data" / "dist" / "dict" / f"shard-{row['shard']:03d}.json.gz"
         ).read_bytes()))
    entries = shard["entries"] if isinstance(shard, dict) and "entries" in shard else shard
    entry = entries[row["offset"]]
    assert entry["lemma"] == row["lemma"], (
        f"index row points at shard {row['shard']} offset {row['offset']} but that "
        f"entry is {entry['lemma']!r}, not {row['lemma']!r} — the deep link would "
        f"open the wrong word"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 5. Gzipped JSON is decoded by sniffing magic bytes.
#
# Bug: corpus.js called r.json() directly. The static host serves .gz WITHOUT
# Content-Encoding: gzip, so the browser hands back raw gzip and the parse throws
# "Unexpected token ... is not valid JSON".
#
# Asserted against the real served bytes: the file IS gzipped, and the script
# contains the branch that handles it.
# ─────────────────────────────────────────────────────────────────────────────
def test_behavior_5_corpus_reads_gzipped_json(origin):
    _, body, ctype = _get(origin, "/data/corpus/sahidic_ruth/text.json.gz")
    assert len(body) > 100
    # The server did NOT claim to have decoded it, so the file is still gzipped
    # on the wire. That is the hard case, and it is the one under test.
    assert body[:2] == b"\x1f\x8b", (
        "test server unexpectedly sent decoded JSON; this test only exercises "
        "the undecoded path"
    )
    assert "content-encoding" not in ctype.lower()

    # The sniff now lives in the ONE shared helper (Session 12 D0/C2), not in
    # corpus.js. Asserting on the helper keeps the behaviour assertion while
    # following the code; asserting corpus.js would have failed on a correct
    # refactor and taught me nothing.
    corpus = _js_code(PUBLIC / "js" / "corpus.js")
    assert "FetchJson" in corpus, (
        "corpus.js does not use the shared FetchJson helper; it has its own "
        "fetch path, which is how the three copies drifted apart")
    helper = _js_code(PUBLIC / "js" / "fetch_json.js")
    assert "0x1f" in helper and "0x8b" in helper, (
        "fetch_json.js does not sniff the gzip magic bytes (1f 8b); with no "
        "Content-Encoding header it would hand raw gzip to JSON.parse and throw")
    assert "DecompressionStream" in helper, (
        "fetch_json.js sniffs gzip but has no DecompressionStream to inflate it")
    # The constants alone are not enough. The first version of this assertion
    # only checked for 0x1f/0x8b, and reverting the sniff to an unconditional
    # `await inflate(buf)` left both constants in the file — so the negative
    # demonstration quietly stopped failing while the bug was reintroduced.
    #
    # Require the BRANCH: the sniff must decide which path is taken.
    # Match the ASSIGNMENT, not any occurrence. Two earlier attempts were fooled
    # by this: checking only for the constants, then checking for `isGzip(buf) ?`
    # anywhere — but the error-message string `${url}: could not decompress
    # (${isGzip(buf) ? "gzip" : "plain"})` contains that exact pattern too, so the
    # assertion passed against an unconditional inflate twice in a row while the
    # negative demonstration silently rotted.
    #
    # `out = isGzip(` can only appear where the decoded text is chosen.
    assert re.search(r"out\s*=\s*isGzip\(", helper), (
        "fetch_json.js does not assign the decoded text from the sniff; it "
        "inflates unconditionally, which throws on a host that sends "
        "Content-Encoding: gzip")

    # The same rule must hold for the dictionary reader.
    # Session 11: reader.js piped every response through DecompressionStream
    # unconditionally — correct ONLY when the host leaves the file compressed.
    # Cloudflare Pages sends Content-Encoding: gzip, the browser inflates once,
    # and reader.js inflated again and threw. So the reader would have worked in
    # every test and failed on the deploy target.
    #
    # Asserted on the helper (both readers delegate to it) AND on the fact that
    # neither reader decompresses on its own, which is what makes drift
    # impossible. test_fetch_json.py mocks both branches for the runtime proof.
    reader = _js_code(PUBLIC / "js" / "reader.js")
    assert "FetchJson" in reader, "reader.js does not use the shared FetchJson helper"
    for name, txt in (("reader.js", reader), ("corpus.js", corpus)):
        assert "DecompressionStream" not in txt, (
            f"{name} decompresses on its own instead of delegating to "
            f"fetch_json.js — the drift Rule 8 exists to prevent")

    # And the payloads must be valid JSON once inflated — the sniffing is only
    # worth anything if what comes out parses.
    doc = json.loads(gzip.decompress(body))
    assert doc["verses"], "text.json.gz decoded to a document with no verses"


# ─────────────────────────────────────────────────────────────────────────────
# 6. Clicking a token keeps the lemma, so the dictionary link survives.
#
# Bug: the corpus click handler recovered the verse ref from
# heading.textContent, which also contains the CTS URN in a <span>. Every lookup
# missed, every token panel lost its lemma, and the dictionary link vanished.
#
# There is no browser in plain pytest, so this asserts the two halves separately:
# the ref must come from an explicit attribute (not from rendered text), and the
# token list must be keyed by a value that actually occurs in the data.
# ─────────────────────────────────────────────────────────────────────────────
def test_behavior_6_token_click_keeps_lemma(origin):
    _, cjs, _ = _get(origin, "/js/corpus.js")
    corpus = cjs.decode("utf-8", "replace")

    handler = corpus.split('addEventListener("click"')[1][:900]
    assert "querySelector(\"h3\").textContent" not in handler, (
        "the corpus click handler recovers the verse key from the heading's "
        "textContent; headings also contain the CTS URN, so the lookup misses "
        "and every lemma and dictionary link is lost (Session 10 bug)"
    )
    # Session 12 D1/C4 changed the key from the colliding `ref` to the unique
    # verse_index. The property is "the handler reads an explicit attribute", and
    # the specific attribute is data-vindex.
    assert "dataset.vindex" in handler, (
        "the corpus click handler does not read the verse from data-vindex; it "
        "must key on verse_index, not on ref (Session 11 defect: ref is not "
        "unique within a work, so tokens were pooled across verses)")
    assert "byRef" not in corpus, (
        "corpus.js still builds a byRef map; that pooled every token from every "
        "colliding verse and rendered the wrong words")
    assert "data-vindex" in corpus and "data-ref" in corpus, (
        "the <section> must carry BOTH data-vindex (the unique join key) and "
        "data-ref (the human-readable label the panel shows)"
    )
    assert "verse_index" in corpus, "corpus.js does not use verse_index at all"

    # The key the handler looks up must be a value that is really in the data,
    # and it must be UNIQUE — that is the whole fix.
    _, body, _ = _get(origin, "/data/corpus/sahidic_ruth/tokens.json.gz")
    doc = json.loads(gzip.decompress(body))
    vidx = [t.get("verse_index") for t in doc["tokens"]]
    assert all(v is not None for v in vidx), (
        "tokens.json has tokens with no verse_index — re-emit with "
        "tools/emit/corpus_tarball.py")
    _, tbody, _ = _get(origin, "/data/corpus/sahidic_ruth/text.json.gz")
    verses = json.loads(gzip.decompress(tbody))["verses"]
    verse_ids = [v["verse_index"] for v in verses]
    assert len(set(verse_ids)) == len(verse_ids), "verse_index is not unique in text.json.gz"
    assert set(vidx) <= set(verse_ids), "tokens reference verses that do not exist"

    # A token with a lemma must have both fields the panel needs, or the panel
    # renders with no lemma and no dictionary link.
    with_lemma = [t for t in doc["tokens"] if t.get("lemma")]
    assert with_lemma, "no token in sahidic_ruth carries a lemma"
    missing = [t for t in with_lemma if not t.get("form")]
    assert not missing, f"{len(missing)} token(s) have a lemma but no form"


# ─────────────────────────────────────────────────────────────────────────────
# 7. A transliteration object renders as a string, not [object Object].
#
# Bug shape: reader.js interpolated `e.translit` directly. Because that value is
# an object with scheme keys, the browser rendered the container instead of the
# selected transliteration.
#
# Session 11 cannot supply this test from production data alone: all 11,369
# shipped entries currently have an empty translit object, so the real dictionary
# has no nonempty transliteration to display. This test therefore injects one
# into C5047 in the test browser's memory only, using the same schema shape the
# merge emits. It does not modify data/dist, public/, or the shard on disk.
# It proves the production renderer handles a populated translit object without
# changing the dataset to make the assertion pass.
# ─────────────────────────────────────────────────────────────────────────────
def test_translit_renders_string(origin):
    pw = pytest.importorskip("playwright.sync_api")
    import urllib.parse

    shard = PUBLIC / "data" / "dist" / "dict" / "shard-013.json.gz"
    if not shard.is_file():
        pytest.skip("no published shard-013; run tools/build.py first")
    with pw.sync_playwright() as playwright:
        browser = None
        context = None
        try:
            browser = playwright.chromium.launch()
        except Exception as e:  # noqa: BLE001
            pytest.skip(f"chromium unavailable: {e}")
        try:
            assert browser is not None
            # Block the worker here: once it controls the page, its fetch handler
            # serves the shard before Playwright's page route sees the request,
            # and the controlled injection below would silently not happen.
            context = browser.new_context(service_workers="block")
            page = context.new_page()

            def fulfill_with_translit(route):
                payload = json.loads(gzip.decompress(shard.read_bytes()))
                entries = payload.get("entries", [])
                assert entries, "shard-013 has no entries to exercise"
                target = next((e for e in entries if e.get("id") == "C5047"), None)
                assert target is not None, "C5047 is not in shard-013"
                target["translit"] = {"bohairic": "tenoou", "sahidic": "tenou"}
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=gzip.compress(json.dumps(payload).encode("utf-8")),
                )

            page.route("**/data/dist/dict/shard-013.json.gz", fulfill_with_translit)
            page.goto(f"{origin}/dict/?q={urllib.parse.quote('ⲧⲉⲛⲟⲩ')}")
            page.wait_for_function(
                "() => document.querySelectorAll('#results button.hit').length > 0",
                timeout=25000)
            page.locator("#results button.hit").first.click()
            page.wait_for_selector("#entry h2", timeout=25000)
            entry_text = page.inner_text("#entry")
            rendered = page.content()
            assert "[object Object]" not in entry_text, entry_text[:500]
            assert "[object Object]" not in rendered
            assert "tenoou" in entry_text, (
                "the injected Bohairic transliteration did not render; "
                f"entry says: {entry_text[:300]!r}")

            # Rule 8: a second route that differs in a known way. Corpus tokens do
            # not carry a translit field, but their panel must not leak the raw
            # container if one ever arrives.
            tokens = json.loads(gzip.decompress(
                (PUBLIC / "data" / "corpus" / "sahidic_ruth" / "tokens.json.gz"
                 ).read_bytes()))["tokens"]
            target = next((t for t in tokens if (t.get("lemma") or "").strip()), None)
            assert target is not None, "sahidic_ruth has no lemma-bearing token"
            page.goto(f"{origin}/corpus/sahidic_ruth/")
            page.wait_for_function(
                "() => document.querySelectorAll('span.tk').length > 0",
                timeout=25000)
            page.locator(
                f"section.verse#v{target['verse_index']} span.tk").nth(target["i"]).click()
            page.wait_for_selector("#corpus-entry .btn", timeout=25000)
            panel = page.inner_text("#corpus-entry")
            assert target["lemma"] in panel
            assert "[object Object]" not in page.content()

            # Rule 8, third route: the quiz must expose the same renderer through
            # its whole interaction. Read the expected prompt from the shipped
            # bank, not from a literal, so the test compares two artefacts.
            bank = json.loads(gzip.decompress(
                (PUBLIC / "data" / "quiz" / "transliteration_to_coptic-beginner.json.gz"
                 ).read_bytes()))
            page.goto(f"{origin}/quiz/")
            page.wait_for_selector("#quiz-start", timeout=25000)
            page.select_option("#quiz-type", "transliteration_to_coptic")
            page.select_option("#quiz-band", "beginner")
            page.click("#quiz-start")
            page.wait_for_function(
                "() => document.querySelectorAll('#quiz-choices button.hit').length > 0",
                timeout=25000)
            assert page.inner_text("#quiz-prompt").strip() == bank[0]["prompt"]
            assert "[object Object]" not in page.content()
        finally:
            if context is not None:
                context.close()
            if browser is not None:
                browser.close()


# ─────────────────────────────────────────────────────────────────────────────
# 8. A POS tag renders as a label, never raw.
#
# Bug shape: drill.js printed annotation tags (APST, CREL, PPERS) straight
# into choice buttons — the learner did not study the tagset. Session 21 D2
# routes every tag through posDisplay() against the shipped labels file.
# This test starts a real POS session and asserts every rendered choice is a
# known label and no rendered choice is a raw tag.
# ─────────────────────────────────────────────────────────────────────────────
def test_pos_drill_renders_labels_not_tags(origin):
    pw = pytest.importorskip("playwright.sync_api")
    labels_file = PUBLIC / "data" / "drill" / "pos_labels.json.gz"
    if not labels_file.is_file():
        pytest.skip("no published pos_labels — run tools/build.py first")
    labels = json.loads(gzip.decompress(labels_file.read_bytes()))["labels"]
    with pw.sync_playwright() as playwright:
        browser = None
        context = None
        try:
            browser = playwright.chromium.launch()
        except Exception as e:  # noqa: BLE001
            pytest.skip(f"chromium unavailable: {e}")
        try:
            assert browser is not None
            context = browser.new_context(service_workers="block")
            page = context.new_page()
            page.goto(f"{origin}/drill/")
            page.wait_for_selector("#drill-start", timeout=25000)
            page.select_option("#drill-work", "sahidic_ruth")
            page.select_option("#drill-type", "pos")
            page.click("#drill-start")
            page.wait_for_function(
                "() => document.querySelectorAll('#drill-choices button.hit').length > 0",
                timeout=25000)
            shown = page.locator("#drill-choices button.hit").all_inner_texts()
            assert len(shown) == 4, shown
            for text in shown:
                assert text in labels.values(), f"{text!r} is not a known label"
                assert text not in labels, f"raw tag rendered: {text!r}"
            assert "[object Object]" not in page.content()
        finally:
            if context is not None:
                context.close()
            if browser is not None:
                browser.close()
