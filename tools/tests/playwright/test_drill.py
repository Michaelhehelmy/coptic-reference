"""tools/tests/playwright/test_drill.py — the drills are playable.

LICENCE: project code, Apache-2.0.

Session 18 D4. A drill bank that exists is not a drill that works (Rule 7).
These tests load /drill/, complete one cloze item, and prove the score moved
in localStorage — then prove the no-JS fallback names the works, because the
fallback is a supported path, not a degraded one.
"""
from __future__ import annotations

import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "public"
STORAGE_KEY = "coptic-drill-progress-v1"

pytestmark = pytest.mark.skipif(
    not (PUBLIC / "data" / "drill" / "cloze-sahidic_ruth.json.gz").is_file(),
    reason="no published drill bank — run tools/build.py first")


@pytest.fixture
def page(browser, server):
    ctx = browser.new_context(service_workers="allow")
    p = ctx.new_page()
    p.goto(server + "/drill/")
    p.wait_for_selector("#drill-start", timeout=25000)
    yield p, ctx, server
    ctx.close()


def _start(p, server):
    p.goto(server + "/drill/")
    p.wait_for_selector("#drill-start", timeout=25000)
    p.select_option("#drill-work", "sahidic_ruth")
    p.click("#drill-start")
    p.wait_for_function(
        "() => document.querySelectorAll('#drill-choices button.hit').length > 0",
        timeout=25000)


def test_drill_item_completes_and_scores(page):
    p, ctx, server = page
    _start(p, server)
    prompt = p.text_content("#drill-prompt")
    assert "____" in prompt, f"no blank rendered: {prompt!r}"
    p.locator("#drill-choices button.hit:not([disabled])").first.click()
    p.wait_for_selector("#drill-feedback .drill-next", timeout=25000)
    feedback = p.text_content("#drill-feedback")
    assert "Correct" in feedback or "Not quite" in feedback, feedback
    assert "/dict/?q=" in p.content(), "answer is not linked to its entry"
    p.locator("#drill-feedback .drill-next").click()
    progress = p.evaluate(f"JSON.parse(localStorage.getItem('{STORAGE_KEY}'))")
    assert progress["answered"] == 1, progress
    assert "[object Object]" not in p.content()


def test_drill_no_js_fallback_lists_works(browser, server):
    ctx = browser.new_context(java_script_enabled=False)
    p = ctx.new_page()
    p.goto(server + "/drill/")
    body = p.content()
    assert "interactive drills need JavaScript" in body, body[:500]
    assert "Sahidic Ruth" in body
    assert "Bohairic Mark" in body
    ctx.close()


def _start_typed(p, server, drill_type):
    p.goto(server + "/drill/")
    p.wait_for_selector("#drill-start", timeout=25000)
    p.select_option("#drill-work", "sahidic_ruth")
    p.select_option("#drill-type", drill_type)
    p.click("#drill-start")
    p.wait_for_function(
        "() => document.querySelectorAll('#drill-choices button.hit').length > 0",
        timeout=25000)


def test_pos_drill_item_completes(page):
    p, ctx, server = page
    _start_typed(p, server, "pos")
    assert "part of speech" in (p.text_content("#drill-progress") or "")
    p.locator("#drill-choices button.hit:not([disabled])").first.click()
    p.wait_for_selector("#drill-feedback .drill-next", timeout=25000)
    p.locator("#drill-feedback .drill-next").click()
    progress = p.evaluate("JSON.parse(localStorage.getItem('coptic-drill-progress-v1'))")
    assert progress["answered"] == 1, progress
    assert "[object Object]" not in p.content()


def test_lemma_drill_item_completes_and_links_entry(page):
    p, ctx, server = page
    _start_typed(p, server, "lemma")
    assert "headword" in (p.text_content("#drill-progress") or "")
    p.locator("#drill-choices button.hit:not([disabled])").first.click()
    p.wait_for_selector("#drill-feedback .drill-next", timeout=25000)
    assert "/dict/?q=" in p.content(), "lemma answer is not linked to its entry"
