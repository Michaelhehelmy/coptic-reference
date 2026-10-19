#!/usr/bin/env python3
"""tools/emit/coursegen.py — the structured course file (Session 19 D4).

Reads `content/lessons/*.md` front matter, emits
`data/dist/course/course.json.gz`: the 20 lessons in order, each with its
filters. No per-item data ships here — quizzes and drills are fetched by the
client from their own banks based on these filters, exactly as `/quiz/` and
`/drill/` do today; the course only chains them.

Shape validated here (20 lessons, 1–20 ordered, prerequisite chain,
threshold range, non-empty filters); traceability to data (verse bounds,
vocab lemmas in the corpus, banks present) is `course_guard.py`'s job.

Written through safeio (Rule 12), gzip mtime=0 for determinism.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import argparse
import gzip
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import safeio  # noqa: E402
import yaml  # noqa: E402  (PyYAML; already a test dependency)

LESSONS_DIR = ROOT / "content" / "lessons"
COURSE_DIR = ROOT / "data" / "dist" / "course"
BANDS = ("beginner", "intermediate", "advanced")


def fail(message: str) -> SystemExit:
    return SystemExit(f"[coursegen] FAIL — {message}")


def read_front_matter(path: pathlib.Path) -> dict:
    """Hugo-style `---` YAML front matter. README.md has none: skipped."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise fail(f"{path.name}: no front matter")
    try:
        _, raw, _ = text.split("---", 2)
    except ValueError as e:
        raise fail(f"{path.name}: unclosed front matter ({e})") from e
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise fail(f"{path.name}: front matter is not a mapping")
    return data


def read_lessons(lessons_dir: pathlib.Path = LESSONS_DIR) -> list[dict]:
    """All lessons with a `lesson` front-matter block, in number order."""
    lessons: list[dict] = []
    for path in sorted(lessons_dir.glob("*.md")):
        if path.name == "README.md":
            continue
        data = read_front_matter(path)
        block = data.get("lesson")
        if not isinstance(block, dict):
            raise fail(f"{path.name}: no `lesson` front-matter block")
        block["_source"] = path.name
        # The display title is Hugo-canonical at top level; the lesson
        # block carries the machine fields. Prefer an explicit block title
        # (placeholders), else the page title (lessons 01–05).
        if not block.get("title") and isinstance(data.get("title"), str):
            block["title"] = data["title"]
        lessons.append(block)
    lessons.sort(key=lambda lesson: lesson.get("number", 0))
    return lessons


def check_shape(lessons: list[dict]) -> None:
    """Course shape. Traceability to data is course_guard.py."""
    if len(lessons) != 20:
        raise fail(f"expected 20 lessons, found {len(lessons)}")
    for position, lesson in enumerate(lessons, 1):
        where = lesson.get("_source", "?")
        if lesson.get("number") != position:
            raise fail(f"{where}: number is {lesson.get('number')}, "
                       f"expected {position} (order matters)")
        expected_prereq = None if position == 1 else position - 1
        if lesson.get("prerequisite") != expected_prereq:
            raise fail(f"{where}: prerequisite is {lesson.get('prerequisite')}, "
                       f"expected {expected_prereq}")
        if not isinstance(lesson.get("title"), str) or not lesson["title"]:
            raise fail(f"{where}: title missing")
        for section in ("vocabulary", "quiz", "drill", "corpus", "checkpoint"):
            if not isinstance(lesson.get(section), dict):
                raise fail(f"{where}: `{section}` filter missing")
        vocab = lesson["vocabulary"]
        lemmas = vocab.get("lemmas")
        if not isinstance(lemmas, list) or not 10 <= len(lemmas) <= 20:
            raise fail(f"{where}: vocabulary needs 10–20 lemmas")
        if lesson["quiz"].get("band") not in BANDS:
            raise fail(f"{where}: quiz band is not a known band")
        drill = lesson["drill"]
        if not (isinstance(drill.get("verse_min"), int)
                and isinstance(drill.get("verse_max"), int)
                and 0 <= drill["verse_min"] <= drill["verse_max"]):
            raise fail(f"{where}: drill verse range is not sane")
        passage = lesson["corpus"]
        if not (isinstance(passage.get("verse_start"), int)
                and isinstance(passage.get("verse_end"), int)
                and 0 <= passage["verse_start"] <= passage["verse_end"]
                and 2 <= passage["verse_end"] - passage["verse_start"] <= 4):
            raise fail(f"{where}: corpus passage is not 3–5 verses")
        threshold = lesson["checkpoint"].get("threshold")
        if not isinstance(threshold, (int, float)) \
                or not 0 < threshold <= 100:
            raise fail(f"{where}: checkpoint threshold is not a percent")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="emit the structured course file")
    ap.parse_args(argv)
    lessons = read_lessons()
    check_shape(lessons)
    payload = {
        "generated": "coursegen-v1",
        "lessons": [{key: lesson[key] for key in
                      ("number", "title", "prerequisite", "reading",
                       "vocabulary", "quiz", "drill", "corpus", "checkpoint")}
                     for lesson in lessons],
    }
    COURSE_DIR.mkdir(parents=True, exist_ok=True)
    size = safeio.write_verified(
        COURSE_DIR / "course.json.gz",
        gzip.compress(json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                      compresslevel=9, mtime=0))
    print(f"[coursegen] 20 lessons -> course.json.gz ({size:,} B gz)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
