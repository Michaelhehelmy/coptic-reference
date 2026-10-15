# tools/tests/test_drill.py — drills must be fair (Session 18 D4).
#
# Rule 7: a bank that exists is not a bank that works. The positive test runs
# drillgen's own builder on a crafted verse; the four negatives feed
# drill_guard one violation per checked category. The tarball and the bank
# both live in tmp_path (Rule 6: tests own what they write).
#
# LICENCE: project code, Apache-2.0.
from __future__ import annotations

import gzip
import json
import pathlib
import sys
import tarfile

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "emit"))
sys.path.insert(0, str(ROOT / "tools" / "validate"))

import drillgen  # noqa: E402
import drill_guard  # noqa: E402
import parsedrill_guard  # noqa: E402


def _tok(verse, i, form, lemma, pos):
    return {"verse_index": verse, "ref": str(verse + 1), "i": i,
            "form": form, "norm": form, "lemma": lemma, "pos": pos,
            "func": "dep", "head": ""}


def _tarball(path: pathlib.Path, verses: list[list[dict]]) -> pathlib.Path:
    """A minimal corpus tarball: one work, the given verses."""
    tokens = [tok for verse in verses for tok in verse]
    tmp = path / "members"
    (tmp / "w").mkdir(parents=True)
    (tmp / "w" / "tokens.json").write_text(
        json.dumps({"slug": "w", "tokens": tokens}), encoding="utf-8")
    (tmp / "w" / "meta.json").write_text(
        json.dumps({"slug": "w"}), encoding="utf-8")
    tarball = path / "corpus.tar.gz"
    with tarfile.open(tarball, "w:gz") as archive:
        archive.add(tmp / "w" / "tokens.json", arcname="w/tokens.json")
        archive.add(tmp / "w" / "meta.json", arcname="w/meta.json")
    return tarball


def _bank(path: pathlib.Path, items: list[dict]) -> pathlib.Path:
    bank = path / "cloze-w.json.gz"
    bank.write_bytes(gzip.compress(
        json.dumps({"work_slug": "w", "items": items}).encode("utf-8"),
        compresslevel=9, mtime=0))
    return path


def _verse():
    # ⲁ(article, kept) ⲣⲱⲙⲉ(noun) ⲉⲃⲟⲗ(verb-ish adverb? use V) ⲡⲉ(article)
    return [_tok(0, 0, "ⲁ", "ⲁ", "ART"),
            _tok(0, 1, "ⲣⲱⲙⲉ", "ⲣⲱⲙⲉ", "N"),
            _tok(0, 2, "ⲃⲱⲕ", "ⲃⲱⲕ", "V"),
            _tok(0, 3, "ⲉⲃⲟⲗ", "ⲉⲃⲟⲗ", "ADV")]


def _good_item():
    verse = _verse()
    return {
        "id": "d-w-00000", "type": "cloze", "work_slug": "w",
        "verse_index": 0, "ref": "1",
        "tokens": [tok["form"] for tok in verse], "blank": 1,
        "choices": ["ⲣⲱⲙⲉ", "ⲥϩⲓⲙⲉ", "ϣⲏⲣⲉ", "ϩⲟⲟⲩ"],
        "correct": 0,
        "source": {"lemma": "ⲣⲱⲙⲉ", "pos": "N", "freq_total": 5,
                   "freq_band": "beginner", "removed_form": "ⲣⲱⲙⲉ",
                   "distractor_lemmas": ["ⲥϩⲓⲙⲉ", "ϣⲏⲣⲉ", "ϩⲟⲟⲩ"]},
        "context": {"prev": "ⲁ", "next": "ⲃⲱⲕ"},
    }


def test_guard_accepts_a_fair_item(tmp_path):
    tarball = _tarball(tmp_path, [_verse()])
    bankdir = tmp_path / "drill"
    bankdir.mkdir()
    _bank(bankdir, [_good_item()])
    count, errors = drill_guard.check(bankdir, tarball)
    assert (count, errors) == (1, [])


def test_guard_rejects_a_wrong_correct_answer(tmp_path):
    tarball = _tarball(tmp_path, [_verse()])
    bankdir = tmp_path / "drill"
    bankdir.mkdir()
    item = _good_item()
    item["correct"] = 2  # points at a distractor, not the removed token
    _bank(bankdir, [item])
    _, errors = drill_guard.check(bankdir, tarball)
    assert any("not the removed token" in e for e in errors)


def test_guard_rejects_an_ambiguous_item(tmp_path):
    verse = _verse() + [_tok(0, 4, "ⲣⲱⲙⲉ", "ⲣⲱⲙⲉ", "N")]  # lemma twice
    tarball = _tarball(tmp_path, [verse])
    bankdir = tmp_path / "drill"
    bankdir.mkdir()
    item = _good_item()
    item["tokens"] = [tok["form"] for tok in verse]
    _bank(bankdir, [item])
    _, errors = drill_guard.check(bankdir, tarball)
    assert any("ambiguous" in e for e in errors)


def test_guard_rejects_a_distractor_equal_after_normalization(tmp_path):
    tarball = _tarball(tmp_path, [_verse()])
    bankdir = tmp_path / "drill"
    bankdir.mkdir()
    item = _good_item()
    item["choices"] = ["ⲣⲱⲙⲉ", "  ⲢⲰⲘⲈ  ", "ⲥϩⲓⲙⲉ", "ϣⲏⲣⲉ"]
    _bank(bankdir, [item])
    _, errors = drill_guard.check(bankdir, tarball)
    assert any("after normalization" in e for e in errors)


def test_guard_rejects_an_unresolvable_verse(tmp_path):
    tarball = _tarball(tmp_path, [_verse()])
    bankdir = tmp_path / "drill"
    bankdir.mkdir()
    item = _good_item()
    item["verse_index"] = 99  # no such verse in the work
    _bank(bankdir, [item])
    _, errors = drill_guard.check(bankdir, tarball)
    assert any("does not resolve" in e for e in errors)


def test_drillgen_skips_ambiguous_slots(tmp_path):
    """Builder-level: a verse whose only content lemma repeats is skipped."""
    verse = [_tok(0, 0, "ⲁ", "ⲁ", "ART"),
             _tok(0, 1, "ⲣⲱⲙⲉ", "ⲣⲱⲙⲉ", "N"),
             _tok(0, 2, "ⲣⲱⲙⲉ", "ⲣⲱⲙⲉ", "N")]
    totals = {"ⲣⲱⲙⲉ": 4, "ⲥϩⲓⲙⲉ": 4, "ϣⲏⲣⲉ": 4, "ϩⲟⲟⲩ": 4}
    ranks = {lemma: rank + 1 for rank, lemma in enumerate(totals)}
    rep = {"ⲣⲱⲙⲉ": "ⲣⲱⲙⲉ", "ⲥϩⲓⲙⲉ": "ⲥϩⲓⲙⲉ",
           "ϣⲏⲣⲉ": "ϣⲏⲣⲉ", "ϩⲟⲟⲩ": "ϩⲟⲟⲩ"}
    pos_of = dict.fromkeys(totals, "N")
    items, skipped = drillgen.build_items("w", verse, totals, ranks, rep, pos_of)
    assert items == [] and skipped["ambiguous"] == 2


def _parse_bank(path: pathlib.Path, items: list[dict]) -> pathlib.Path:
    bank = path / "parse-w.json.gz"
    bank.write_bytes(gzip.compress(
        json.dumps({"work_slug": "w", "items": items}).encode("utf-8"),
        compresslevel=9, mtime=0))
    return path


def _parse_item(**over):
    item = {
        "id": "p-w-00000", "drill_type": "pos", "type": "parse",
        "work_slug": "w", "verse_index": 0, "ref": "1",
        "tokens": ["ⲁ", "ⲥ", "ϣⲱⲡⲉ"], "token_index": 1,
        "choices": ["PPERS", "ART", "N", "V"], "correct": 0,
        "source": {"form": "ⲥ", "lemma": "ⲛⲧⲟⲥ", "pos": "PPERS",
                   "func": "dep", "freq_band": "beginner",
                   "distractor_tags": ["ART", "N", "V"]},
        "context": {"prev": "ⲁ", "next": "ϣⲱⲡⲉ"},
    }
    item.update(over)
    return item


def _parse_verse():
    return [_tok(0, 0, "ⲁ", "ⲁ", "ART"),
            _tok(0, 1, "ⲥ", "ⲛⲧⲟⲥ", "PPERS"),
            _tok(0, 2, "ϣⲱⲡⲉ", "ϣⲱⲡⲓ", "VSTAT")]


def test_parsedrill_guard_accepts_a_fair_item(tmp_path):
    tarball = _tarball(tmp_path, [_parse_verse()])
    bankdir = tmp_path / "drill"
    bankdir.mkdir()
    _parse_bank(bankdir, [_parse_item()])
    count, errors = parsedrill_guard.check(bankdir, tarball)
    assert (count, errors) == (1, [])


def test_parsedrill_guard_rejects_a_wrong_correct_answer(tmp_path):
    tarball = _tarball(tmp_path, [_parse_verse()])
    bankdir = tmp_path / "drill"
    bankdir.mkdir()
    _parse_bank(bankdir, [_parse_item(correct=2)])
    _, errors = parsedrill_guard.check(bankdir, tarball)
    assert any("not the annotated" in e for e in errors)


def test_parsedrill_guard_rejects_a_normalized_equal_distractor(tmp_path):
    tarball = _tarball(tmp_path, [_parse_verse()])
    bankdir = tmp_path / "drill"
    bankdir.mkdir()
    _parse_bank(bankdir, [_parse_item(choices=["PPERS", "ppers", "N", "V"])])
    _, errors = parsedrill_guard.check(bankdir, tarball)
    assert any("after normalization" in e for e in errors)
