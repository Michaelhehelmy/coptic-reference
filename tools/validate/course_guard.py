#!/usr/bin/env python3
"""tools/validate/course_guard.py — every course filter resolves to data.

Session 19 D4. The course file chains quizzes and drills by filter; a filter
pointing at nothing is a locked door (Rule 7: a course that lists lessons it
cannot teach is decoration). Against the corpus tarball, the drill banks, and
the quiz banks, for every lesson:

- drill {work, verse_min, verse_max} lies inside the work's verse bounds and
  the drill bank for the work exists and covers the range;
- corpus {work, verse_start, verse_end} lies inside the work's verse bounds;
- every vocabulary lemma occurs in the corpus inventory;
- quiz {band} names a real band and the band's quiz banks exist.

Reads through safeio/tarfile like its siblings (Rule 12: tarball single-form).

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import argparse
import gzip
import json
import pathlib
import sys
import tarfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import safeio  # noqa: E402

COURSE = ROOT / "data" / "dist" / "course" / "course.json.gz"
TARBALL = ROOT / "data" / "dist" / "corpus" / "corpus.tar.gz"
DRILL_DIR = ROOT / "data" / "dist" / "drill"
QUIZ_DIR = ROOT / "data" / "dist" / "quiz"
BANDS = ("beginner", "intermediate", "advanced")


class CourseGuardError(SystemExit):
    """A course filter does not resolve. Raised, never warned."""


def read_course(path: pathlib.Path = COURSE) -> dict:
    try:
        raw = safeio.read_maybe_gzip(path)
    except OSError as e:
        raise CourseGuardError(f"[course_guard] {path} unreadable ({e})") from e
    try:
        return json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise CourseGuardError(f"[course_guard] {path} is not JSON ({e})") from e


def read_corpus(tarball: pathlib.Path = TARBALL) -> tuple[dict[str, int], set[str]]:
    """(work -> max verse_index, lemma inventory)."""
    if not tarball.is_file():
        raise CourseGuardError(f"[course_guard] {tarball} is missing")
    bounds: dict[str, int] = {}
    lemmas: set[str] = set()
    with tarfile.open(tarball, "r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile() or not member.name.endswith("/tokens.json"):
                continue
            slug = member.name.partition("/")[0]
            stream = archive.extractfile(member)
            if stream is None:
                raise CourseGuardError(f"[course_guard] {member.name} unreadable")
            indices = set()
            for tok in json.loads(stream.read().decode("utf-8"))["tokens"]:
                indices.add(tok["verse_index"])
                if tok.get("lemma"):
                    lemmas.add(tok["lemma"])
            bounds[slug] = max(indices)
    if not bounds:
        raise CourseGuardError("[course_guard] no works in the corpus tarball")
    return bounds, lemmas


def drill_verses(work: str, drill_dir: pathlib.Path = DRILL_DIR) -> set[int]:
    """Verse indices the drill bank for a work actually covers."""
    path = drill_dir / f"cloze-{work}.json.gz"
    if not path.is_file():
        raise CourseGuardError(f"[course_guard] drill bank missing: {path.name}")
    try:
        raw = safeio.read_maybe_gzip(path)
        return {item["verse_index"]
                for item in json.loads(raw.decode("utf-8")).get("items", [])}
    except (OSError, json.JSONDecodeError, UnicodeDecodeError, KeyError) as e:
        raise CourseGuardError(f"[course_guard] {path.name} unreadable ({e})") from e


def check(course_path: pathlib.Path = COURSE) -> tuple[int, list[str]]:
    """Returns (lesson count, errors). Empty errors means clean."""
    course = read_course(course_path)
    lessons = course.get("lessons", [])
    bounds, inventory = read_corpus()
    errors: list[str] = []
    for lesson in lessons:
        tag = f"lesson {lesson.get('number', '?')}"
        drill, passage = lesson.get("drill", {}), lesson.get("corpus", {})
        dwork = drill.get("work")
        if dwork not in bounds:
            errors.append(f"{tag}: drill work {dwork!r} is not a shipped work")
            continue
        for field in ("verse_min", "verse_max"):
            value = drill.get(field)
            if not isinstance(value, int) or not 0 <= value <= bounds[dwork]:
                errors.append(f"{tag}: drill {field}={value!r} outside "
                              f"{dwork} bounds 0..{bounds[dwork]}")
        covered = drill_verses(dwork)
        wanted = set(range(drill.get("verse_min", 1), drill.get("verse_max", 0) + 1))
        if not wanted & covered:
            errors.append(f"{tag}: drill range has no bank item in {dwork}")
        cwork = passage.get("work")
        if cwork not in bounds:
            errors.append(f"{tag}: corpus work {cwork!r} is not shipped")
            continue
        for field in ("verse_start", "verse_end"):
            value = passage.get(field)
            if not isinstance(value, int) or not 0 <= value <= bounds[cwork]:
                errors.append(f"{tag}: corpus {field}={value!r} outside "
                              f"{cwork} bounds 0..{bounds[cwork]}")
        for lemma in lesson.get("vocabulary", {}).get("lemmas", []):
            if lemma not in inventory:
                errors.append(f"{tag}: vocab {lemma!r} never occurs in corpus")
        band = lesson.get("quiz", {}).get("band")
        if band not in BANDS:
            errors.append(f"{tag}: quiz band {band!r} unknown")
            continue
        for bank in (f"coptic_to_english-{band}.json.gz",
                     f"transliteration_to_coptic-{band}.json.gz"):
            if not (QUIZ_DIR / bank).is_file():
                errors.append(f"{tag}: quiz bank missing: {bank}")
    return len(lessons), errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="course filters must resolve")
    ap.parse_args(argv)
    try:
        count, errors = check()
    except CourseGuardError as e:
        print(str(e), file=sys.stderr)
        return 1
    if errors:
        print(f"[course_guard] FAIL — {len(errors)} unresolvable filter(s) "
              f"in {count} lessons:", file=sys.stderr)
        for error in errors[:20]:
            print(f"  - {error}", file=sys.stderr)
        if len(errors) > 20:
            print(f"  - ... and {len(errors) - 20} more", file=sys.stderr)
        return 1
    print(f"[course_guard] OK — {count} lessons; every filter resolves to data")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
