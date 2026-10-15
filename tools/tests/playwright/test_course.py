"""tools/tests/playwright/test_course.py — the course gates on checkpoints.

LICENCE: project code, Apache-2.0.

Session 19 D4. A course page that lists lessons is not a course that gates
(Rule 7). These tests complete lesson 1's real checkpoint by answering its
ten questions correctly — recomputing the client's deterministic selection
from the published banks, never from the client's memory — and prove lesson
2 unlocks; then prove lesson 2 starts locked; then prove the no-JS list names
the lessons.
"""
from __future__ import annotations

import gzip
import json
import pathlib
import urllib.request

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "public"
STORAGE_KEY = "coptic-course-progress-v1"

pytestmark = pytest.mark.skipif(
    not (PUBLIC / "data" / "course" / "course.json.gz").is_file(),
    reason="no published course — run tools/build.py first")


def _read_gz(path: pathlib.Path) -> dict:
    return json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))


def _checkpoint_session(server: str, lesson: dict) -> list[dict]:
    """The ten checkpoint items the client will ask, in order.

    Mirrors static/js/course.js: vocab-overlap first (c2e prompt or t2c
    answer in the lesson vocabulary), then band fill, rotated by attempts
    (zero on a fresh browser). If this drifts from the client, the test
    answers wrong — which is the point: the test, not the client, breaks.
    """
    band = lesson["quiz"]["band"]
    vocab = set(lesson["vocabulary"]["lemmas"])
    pool: list[dict] = []
    for quiz_type in ("coptic_to_english", "transliteration_to_coptic"):
        url = f"{server}/data/quiz/{quiz_type}-{band}.json.gz"
        with urllib.request.urlopen(url) as response:
            bank = json.loads(gzip.decompress(response.read()).decode("utf-8"))
        preferred, rest = [], []
        items = bank["items"] if isinstance(bank, dict) else bank
        for item in items:
            if quiz_type == "coptic_to_english":
                (preferred if item["prompt"] in vocab else rest).append(item)
            else:
                answer = item["choices"][item["correct"]]
                (preferred if answer in vocab else rest).append(item)
        pool.extend(preferred + rest)
    return pool[:10]


@pytest.fixture
def page(browser, server):
    ctx = browser.new_context(service_workers="allow")
    p = ctx.new_page()
    p.goto(server + "/course/")
    p.wait_for_selector("#course-lessons .course-lesson", timeout=25000)
    yield p, ctx, server
    ctx.close()


def test_lesson_1_checkpoint_unlocks_lesson_2(page):
    p, ctx, server = page
    course = _read_gz(PUBLIC / "data" / "course" / "course.json.gz")
    lesson = course["lessons"][0]
    session = _checkpoint_session(server, lesson)
    assert len(session) == 10, "checkpoint pool too small to test"
    lessons = p.locator("#course-lessons .course-lesson")
    assert lessons.count() == 15
    lessons.nth(0).locator("button").first.click()
    for item in session:
        p.wait_for_selector("#course-checkpoint .hits button.hit", timeout=25000)
        p.locator("#course-checkpoint .hits button.hit").nth(item["correct"]).click()
        nxt = p.locator("#course-checkpoint .course-next")
        nxt.wait_for(state="visible", timeout=25000)
        nxt.click()
    p.wait_for_function(
        "() => document.getElementById('course-status').textContent.includes('unlocked')",
        timeout=25000)
    progress = p.evaluate(f"JSON.parse(localStorage.getItem('{STORAGE_KEY}'))")
    assert progress["passed"].get("1") is True, progress
    assert "[object Object]" not in p.content()


def test_lesson_2_starts_locked(page):
    p, ctx, server = page
    lessons = p.locator("#course-lessons .course-lesson")
    second = lessons.nth(1)
    assert "locked" in (second.get_attribute("class") or "")
    assert second.locator("button").count() == 0


def test_course_no_js_fallback_lists_lessons(browser, server):
    ctx = browser.new_context(java_script_enabled=False)
    p = ctx.new_page()
    p.goto(server + "/course/")
    body = p.content()
    assert "interactive course needs JavaScript" in body
    assert "The alphabet and its sounds" in body
    assert "Reading alone: Ruth whole" in body
    ctx.close()


def test_lessons_1_to_5_render_prose_not_todo(browser, server):
    ctx = browser.new_context()
    p = ctx.new_page()
    for number in ("01", "02", "03", "04", "05"):
        p.goto(f"{server}/lessons/{number}/")
        body = p.content()
        assert "TODO (Session 20)" not in body, number
        assert len(body) > 2000, number
    ctx.close()


def test_lesson_pages_carry_the_unverified_banner(browser, server):
    ctx = browser.new_context()
    p = ctx.new_page()
    p.goto(server + "/lessons/01/")
    p.wait_for_selector("#grammar-claims-banner", timeout=25000)
    assert "not been independently verified" in p.content()
    assert "/grammar-claims/" in p.content()
    ctx.close()
