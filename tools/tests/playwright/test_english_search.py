"""tools/tests/playwright/test_english_search.py — English gloss search works.

LICENCE: project code, Apache-2.0.

Session 14 D2 / C3. English search has been decorative since Session 9: Pagefind
1.5.2 drops a fixed set of English gloss terms from its index, so `copper`
returned 0 hits while `azurite` returned 9 in the same document. Filed upstream as
PageFind/PageFind#1370; `tools/emit/english_index.py` +
`static/js/search.js` are the workaround.

Rule 8 and Rule 10 both apply here. Rule 8: two inputs that differ in the
property the code branches on — a Coptic term and a Latin term. Rule 10: every
assertion below is written so a broken probe would show up as a failure on the
KNOWN-GOOD case first, not as a pass.
"""
from __future__ import annotations

import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "public"

pytestmark = pytest.mark.skipif(
    not (PUBLIC / "data" / "search" / "english_index.json.gz").is_file(),
    reason="no English index — run tools/emit/english_index.py")


@pytest.fixture
def page(browser, server):
    ctx = browser.new_context(service_workers="allow")
    p = ctx.new_page()
    p.goto(server + "/dict/")
    p.wait_for_function(
        "() => document.getElementById('count-all') && "
        "!document.getElementById('count-all').textContent.includes('Loading')",
        timeout=25000)
    yield p, ctx, server
    ctx.close()


def _search(p, server, query: str):
    """Type into the box and wait for the merged list to settle.

    Uses URL encoding from the library, never a hand-written literal — the
    Session 13 near-miss was exactly that (Rule 10).
    """
    import urllib.parse
    p.goto(f"{server}/dict/?q={urllib.parse.quote(query)}")
    # The English merge is asynchronous; wait for the count line to stop being
    # the Coptic-only render.
    p.wait_for_function(
        """(q) => {
             const el = document.querySelector('#results .count');
             return !!el && !el.textContent.includes('Loading');
           }""",
        arg=query, timeout=25000)
    p.wait_for_timeout(700)
    return p.locator("#results button.hit").count()


def test_english_term_pagefind_cannot_find(page):
    """`copper` is THE term Pagefind drops. 19 entries gloss it."""
    p, ctx, server = page
    n = _search(p, server, "copper")
    assert n > 0, (
        "'copper' returns no results. Pagefind drops this term "
        "(PageFind/PageFind#1370), so it must come from the static English index."
    )


def test_english_result_is_clickable_and_shows_the_right_entry(page):
    p, ctx, server = page
    assert _search(p, server, "copper") > 0
    p.locator("#results button.hit").first.click()
    p.wait_for_selector("#entry h2", timeout=10000)
    assert p.inner_text("#entry h2").strip(), "clicking an English hit showed no entry"
    # ... and the entry's gloss mentions copper, or we resolved to the wrong row.
    body = p.inner_text("#entry")
    assert "copper" in body.lower(), (
        "the entry opened by an English hit does not mention the search term; the "
        "id -> row resolution is pointing at the wrong entry")


def test_english_term_pagefind_already_found_still_works(page):
    """Rule 8: a second input. `azurite` works in BOTH paths and must not regress."""
    p, ctx, server = page
    n = _search(p, server, "azurite")
    assert n > 0, "'azurite' regressed — it used to work via Pagefind alone"


def test_coptic_search_is_unchanged(page):
    """The workaround must not disturb the path that already worked."""
    p, ctx, server = page
    n = _search(p, server, "ⲧⲉⲛⲟⲩ")
    assert n == 1, f"expected 1 hit for ⲧⲉⲛⲟⲩ, got {n}"
    p.locator("#results button.hit").first.click()
    p.wait_for_selector("#entry h2", timeout=10000)
    assert p.inner_text("#entry h2").strip() == "ⲧⲉⲛⲟⲩ"


def test_english_hits_are_deduped(page):
    """`copper` appears in many glosses; the merged list must not repeat a lemma."""
    p, ctx, server = page
    _search(p, server, "copper")
    lemmas = p.eval_on_selector_all(
        "#results button.hit .lemma", "els => els.map(e => e.textContent.trim())")
    assert len(lemmas) == len(set(lemmas)), (
        f"duplicate lemmas in the merged list: "
        f"{[l for l in lemmas if lemmas.count(l) > 1][:4]}")


def test_stopwords_do_not_match_everything(page):
    """A closed-class stopword must not return the whole dictionary."""
    p, ctx, server = page
    n = _search(p, server, "the")
    assert n < 200, f"'the' matched {n} entries — stopwords are not being filtered"
