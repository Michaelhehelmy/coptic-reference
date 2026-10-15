# tools/tests/test_lessons.py — lesson_vocab_guard must be able to FAIL.
#
# Session 20 D0 (C1, Rule 13). Three negatives, one per checked category,
# on crafted lesson files in tmp_path (Rule 6): an invented lemma, a wrong
# gloss, and a taught pair for a form with no dictionary entry. Plus a
# positive control and a run over the real lessons (skipped without baked
# data, like the course tests).
#
# LICENCE: project code, Apache-2.0.
from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "validate"))

import lesson_vocab_guard as guard  # noqa: E402


def _entries() -> dict[str, dict]:
    import unicodedata
    sys.path.insert(0, str(ROOT / "tools"))
    import collate

    def norm(token: str) -> str:
        return collate.canon_for_sort(unicodedata.normalize("NFC", token))

    return {
        norm("ϫⲱ"): {"id": "C-jo", "glosses": [
            {"text": "say, speak, tell"}, {"text": "sing"}]},
        norm("ⲣⲱⲙⲉ"): {"id": "C-rome", "glosses": [
            {"text": "man, human being"}]},
    }


def _lesson(tmp_path: pathlib.Path, body: str,
            extra: str = "") -> pathlib.Path:
    path = tmp_path / "99.md"
    path.write_text(
        "---\ntitle: \"Lesson 99\"\nweight: 99\nlesson:\n"
        "  number: 99\n  prerequisite: 98\n"
        "  reading: \"Test.\"\n"
        "  vocabulary: {band: beginner, pos: V, lemmas: [ϫⲱ]}\n"
        "  quiz: {band: beginner, pos: V}\n"
        "  drill: {work: w, verse_min: 0, verse_max: 4}\n"
        "  corpus: {work: w, verse_start: 0, verse_end: 4}\n"
        "  checkpoint: {threshold: 70}\n" + extra + "---\n\n" + body,
        encoding="utf-8")
    return path


def test_invented_lemma_fails(tmp_path):
    path = _lesson(tmp_path, "The verb ⲭⲭⲭⲱⲱⲱ (to frobnicate) is made up.\n")
    errors = guard.check_file(path, _entries(), {"ⲭⲭⲭⲱⲱⲱ"})
    assert any("no dictionary entry" in e for e in errors), errors


def test_wrong_gloss_fails(tmp_path):
    path = _lesson(tmp_path, "The verb ϫⲱ (to dance) moves.\n")
    errors = guard.check_file(path, _entries(), {"ϫⲱ"})
    assert any("not in" in e and "C-jo" in e for e in errors), errors


def test_taught_pair_without_entry_fails(tmp_path):
    path = _lesson(tmp_path, "The form ⲡⲉϫⲉ (to say) has no headword.\n")
    errors = guard.check_file(path, _entries(), {"ⲡⲉϫⲉ"})
    assert any("no dictionary entry" in e for e in errors), errors


def test_clean_lesson_passes(tmp_path):
    path = _lesson(tmp_path, "The verb ϫⲱ (say, speak, tell) says.\n")
    assert guard.check_file(path, _entries(), {"ϫⲱ"}) == []


def test_declared_unlisted_form_passes(tmp_path):
    path = _lesson(tmp_path, "The form ⲡⲉϫⲉ has no headword.\n",
                   "  unlisted_forms: {ⲡⲉϫⲉ: \"conjugated form\"}\n")
    assert guard.check_file(path, _entries(), {"ⲡⲉϫⲉ"}) == []


def test_real_lessons_are_clean():
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        import shardio  # noqa: E402
    except ImportError:
        pytest.skip("tools/ not importable")
    if not shardio.shard_paths(ROOT / "data" / "dist" / "dict"):
        pytest.skip("no baked shards")
    _, errors = guard.check()
    assert errors == []
