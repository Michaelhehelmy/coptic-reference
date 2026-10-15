"""tools/tests/playwright/test_write.py — tracing gives lenient feedback.

LICENCE: project code, Apache-2.0.

Session 21 D4. A canvas that exists is not practice that responds (Rule 7).
These tests draw a real stroke across the canvas and prove feedback appears
in the three-word vocabulary (good/close/try again — never a number), then
prove the no-JS gallery names the letters.
"""
from __future__ import annotations

import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "public"

pytestmark = pytest.mark.skipif(
    not (PUBLIC / "write" / "index.html").is_file(),
    reason="no published /write/ — run tools/build.py first")


@pytest.fixture
def page(browser, server):
    ctx = browser.new_context(service_workers="allow", has_touch=True)
    p = ctx.new_page()
    p.goto(server + "/write/")
    p.wait_for_selector("#write-check", timeout=25000)
    yield p, ctx, server
    ctx.close()


def test_draw_a_stroke_receives_lenient_feedback(page):
    p, ctx, server = page
    box = p.locator("#write-canvas").bounding_box()
    assert box and box["width"] > 100, "canvas has no drawable size"
    x0, y0 = box["x"] + 20, box["y"] + box["height"] / 2
    p.mouse.move(x0, y0)
    p.mouse.down()
    for step in range(1, 11):
        p.mouse.move(x0 + step * 20, y0 - step * 8)
    p.mouse.up()
    p.click("#write-check")
    p.wait_for_function(
        "() => document.getElementById('write-feedback').textContent.length > 0",
        timeout=25000)
    feedback = p.text_content("#write-feedback") or ""
    assert any(word in feedback for word in ("Good", "Close", "Try again")), feedback
    assert not any(ch.isdigit() for ch in feedback), f"numeric score leaked: {feedback!r}"
    assert "[object Object]" not in p.content()


def test_write_no_js_fallback_lists_letters(browser, server):
    ctx = browser.new_context(java_script_enabled=False)
    p = ctx.new_page()
    p.goto(server + "/write/")
    body = p.content()
    assert "Tracing needs JavaScript" in body
    assert "write/svg/ref-u2c81.svg" in body
    assert "write/svg/ref-word-maria.svg" in body
    ctx.close()
