"""tools/tests/playwright/test_quiz.py — the quiz is playable and persistent.

LICENCE: project code, Apache-2.0.

Session 16 D2. A quiz file that exists is not a quiz that works (Rule 7). These
tests start a real session, answer ten questions, reload, and prove the browser
remembered the result. They also scan every rendered surface for the raw-object
marker, because quiz prompts include transliterations and glosses drawn from
structured shard fields.
"""
from __future__ import annotations

import gzip
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "public"
STORAGE_KEY = "coptic-quiz-progress-v1"

pytestmark = pytest.mark.skipif(
    not (PUBLIC / "data" / "quiz" / "coptic_to_english-beginner.json.gz").is_file(),
    reason="no published quiz bank — run tools/build.py first")


@pytest.fixture
def page(browser, server):
    ctx = browser.new_context(service_workers="allow")
    p = ctx.new_page()
    p.goto(server + "/quiz/")
    p.wait_for_selector("#quiz-start", timeout=25000)
    yield p, ctx, server
    ctx.close()


def _start(p, server, quiz_type, band):
    p.goto(server + "/quiz/")
    p.wait_for_selector("#quiz-start", timeout=25000)
    p.select_option("#quiz-type", quiz_type)
    if quiz_type != "verse_matching":
        p.select_option("#quiz-band", band)
    p.click("#quiz-start")
    p.wait_for_function(
        "() => document.querySelectorAll('#quiz-choices button.hit').length > 0",
        timeout=25000)


def _progress(p):
    return p.evaluate(f"JSON.parse(localStorage.getItem('{STORAGE_KEY}'))")


def _answer_current(p):
    p.locator("#quiz-choices button.hit:not([disabled])").first.click()
    p.wait_for_selector("#quiz-feedback .quiz-next", timeout=25000)
    p.locator("#quiz-feedback .quiz-next").click()


def test_quiz_session_completes_and_scores(page):
    p, ctx, server = page
    _start(p, server, "coptic_to_english", "beginner")
    for _ in range(10):
        _answer_current(p)
    p.wait_for_function(
        "() => document.getElementById('quiz-prompt').textContent.includes("
        "'Session complete')",
        timeout=25000)
    progress = _progress(p)
    assert progress["sessionsCompleted"] == 1, progress
    assert progress["answered"] == 10, progress
    assert 0 <= progress["correct"] <= 10, progress
    assert "[object Object]" not in p.content()


def test_quiz_score_survives_reload(page):
    p, ctx, server = page
    _start(p, server, "english_to_coptic", "beginner")
    for _ in range(10):
        _answer_current(p)
    before = _progress(p)
    assert before["answered"] == 10
    p.reload()
    p.wait_for_selector("#quiz-start", timeout=25000)
    after = _progress(p)
    assert after == before, "localStorage did not survive a reload"
    assert f"{after['correct']}/{after['answered']}" in p.inner_text("#quiz-score")


def test_transliteration_prompt_is_a_string_not_an_object(page):
    """The Session 16 D0 regression target, exercised through the whole UI."""
    bank = json.loads(gzip.decompress(
        (PUBLIC / "data" / "quiz" / "transliteration_to_coptic-beginner.json.gz"
         ).read_bytes()))
    p, ctx, server = page
    _start(p, server, "transliteration_to_coptic", "beginner")
    assert p.inner_text("#quiz-prompt").strip() == bank[0]["prompt"]
    assert "[object Object]" not in p.content()


def test_progress_exports_valid_json(page, tmp_path):
    """Exportability is the account-free portability story (C3)."""
    p, ctx, server = page
    _start(p, server, "lemma_identification", "beginner")
    _answer_current(p)
    with p.expect_download() as download:
        p.click("#quiz-export")
    path = tmp_path / "progress.json"
    download.value.save_as(str(path))
    exported = json.loads(path.read_text(encoding="utf-8"))
    assert exported["answered"] == 1
    assert exported["items"], "no per-item scheduling state was exported"


def test_quiz_has_a_static_no_javascript_fallback(page):
    """C4: without JS, the route is a topic list, not a blank shell."""
    p, ctx, server = page
    response = p.request.get(server + "/quiz/")
    assert response.status == 200
    html = response.text()
    assert 'id="quiz-noscript"' in html or "id=quiz-noscript" in html
    assert "Quiz topics" in html
    assert "needs JavaScript" in html
    for topic in (
        "Coptic to English",
        "Romanization to Coptic",
        "Verse matching",
    ):
        assert topic in html, f"no-JS fallback omits {topic}"
