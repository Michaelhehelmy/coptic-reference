# tools/tests/test_course.py — the course chain resolves (Session 19 D4/D5).
#
# Rule 7: a course file that exists is not a course that teaches. These
# tests pin the chain end to end at the data level (front matter ==
# course.json, every filter covered by a bank, the no-JS list in sync);
# the browser tests prove lessons unlock and lock.
#
# LICENCE: project code, Apache-2.0.
from __future__ import annotations

import gzip
import json
import pathlib
import re

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
COURSE = ROOT / "data" / "dist" / "course" / "course.json.gz"


def _course() -> dict:
    if not COURSE.is_file():
        pytest.skip("no baked course — run tools/emit/coursegen.py first")
    return json.loads(gzip.decompress(COURSE.read_bytes()).decode("utf-8"))


def _front_matters() -> dict[int, dict]:
    out: dict[int, dict] = {}
    for path in sorted((ROOT / "content" / "lessons").glob("[0-9]*.md")):
        data = yaml.safe_load(path.read_text(encoding="utf-8").split("---", 2)[1])
        block = data["lesson"]
        # Same title resolution as coursegen: block title, else page title.
        if not block.get("title"):
            block["title"] = data.get("title", "")
        out[block["number"]] = block
    return out


def test_course_has_fifteen_ordered_lessons():
    course = _course()
    assert [lesson["number"] for lesson in course["lessons"]] == list(range(1, 16))


def test_front_matter_matches_the_emitted_course():
    """coursegen fidelity: what Hugo renders is what the client chains."""
    course = _course()
    front = _front_matters()
    assert sorted(front) == list(range(1, 16))
    for lesson in course["lessons"]:
        source = front[lesson["number"]]
        for field in ("title", "prerequisite", "reading", "vocabulary",
                      "quiz", "drill", "corpus", "checkpoint"):
            assert lesson[field] == source[field], (lesson["number"], field)


def test_lesson_pages_carry_real_prose_or_an_honest_todo():
    """Lessons 1–5 teach; 6–15 say TODO and ship their filters anyway."""
    for number in range(1, 16):
        path = ROOT / "content" / "lessons" / f"{number:02d}.md"
        body = path.read_text(encoding="utf-8").split("---", 2)[2]
        words = len(body.split())
        if number <= 5:
            assert words >= 150, f"{path.name}: {words} words is not a lesson"
            assert "TODO" not in body, f"{path.name} teaches but claims TODO"
        else:
            assert "TODO (Session 20)" in body, f"{path.name} hides its stub"


def test_no_js_lesson_list_matches_the_course():
    """The fallback names the same fifteen lessons the client would chain."""
    course = _course()
    template = (ROOT / "themes" / "copticref" / "layouts" / "course" / "list.html"
                ).read_text(encoding="utf-8")
    noscript = template.split("<noscript", 1)[1].split("</noscript>", 1)[0]
    listed = re.findall(r"<li>(.*?)</li>", noscript)
    assert len(listed) == 15, listed
    for lesson, title in zip(course["lessons"], listed):
        assert lesson["title"].split("—", 1)[-1].strip() == title.strip(), \
            (lesson["number"], title)


def test_checkpoint_banks_exist_for_every_lesson():
    """Every lesson's checkpoint can actually fetch its two banks."""
    course = _course()
    for lesson in course["lessons"]:
        band = lesson["quiz"]["band"]
        for quiz_type in ("coptic_to_english", "transliteration_to_coptic"):
            bank = ROOT / "data" / "dist" / "quiz" / f"{quiz_type}-{band}.json.gz"
            assert bank.is_file(), (lesson["number"], bank.name)
