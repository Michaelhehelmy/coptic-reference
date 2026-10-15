#!/usr/bin/env python3
"""tools/validate/parsedrill_guard.py — parse drill answers match annotation.

Session 20 D4. For every item in every data/dist/drill/parse-<work>.json.gz,
resolved against the corpus tarball (never the bank alone):

- the work/verse_index/token_index resolves to a real annotated token;
- a POS item's correct choice is the token's annotated POS;
- a lemma item's correct choice is the token's annotated lemma;
- no distractor equals the correct answer after normalization;
- exactly four unique choices (after normalization);
- Session 21 D3: the token's form differs from its lemma after
  normalization (trivial identity items must never ship).

Reads banks through safeio (Rule 12); the tarball is single-form.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import tarfile
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import safeio  # noqa: E402

DRILL_DIR = ROOT / "data" / "dist" / "drill"
TARBALL = ROOT / "data" / "dist" / "corpus" / "corpus.tar.gz"
LABELS = DRILL_DIR / "pos_labels.json.gz"


class ParseDrillGuardError(SystemExit):
    """A parse drill item contradicts its annotation."""


def normalized(text: str) -> str:
    return unicodedata.normalize("NFC", text.strip().casefold())


def read_bank(path: pathlib.Path) -> dict:
    try:
        raw = safeio.read_maybe_gzip(path)
    except OSError as e:
        raise ParseDrillGuardError(f"[parsedrill_guard] {path} unreadable ({e})") from e
    try:
        return json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ParseDrillGuardError(
            f"[parsedrill_guard] {path} is not JSON ({e})") from e


def read_verses(tarball: pathlib.Path = TARBALL) -> dict[str, dict[int, list[dict]]]:
    """{work_slug: {verse_index: [tokens in order]}}."""
    if not tarball.is_file():
        raise ParseDrillGuardError(f"[parsedrill_guard] {tarball} is missing")
    verses: dict[str, dict[int, list[dict]]] = {}
    with tarfile.open(tarball, "r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile() or not member.name.endswith("/tokens.json"):
                continue
            slug = member.name.partition("/")[0]
            stream = archive.extractfile(member)
            if stream is None:
                raise ParseDrillGuardError(
                    f"[parsedrill_guard] {member.name} unreadable")
            by_verse: dict[int, list[dict]] = {}
            for tok in json.loads(stream.read().decode("utf-8"))["tokens"]:
                by_verse.setdefault(tok["verse_index"], []).append(tok)
            verses[slug] = {index: sorted(toks, key=lambda tok: tok["i"])
                            for index, toks in by_verse.items()}
    if not verses:
        raise ParseDrillGuardError("[parsedrill_guard] no works in the tarball")
    return verses


def check_item(item: dict, verses: dict[str, dict[int, list[dict]]],
               filename: str, errors: list[str]) -> None:
    prefix = f"{filename} {item.get('id', '?')}"
    if not isinstance(item, dict):
        errors.append(f"{prefix}: not an object")
        return
    drill_type = item.get("drill_type")
    if drill_type not in ("pos", "lemma"):
        errors.append(f"{prefix}: drill_type is not pos/lemma")
        return
    slug, verse_index = item.get("work_slug"), item.get("verse_index")
    verse = (verses.get(slug) or {}).get(verse_index) \
        if isinstance(slug, str) and isinstance(verse_index, int) else None
    if not verse:
        errors.append(f"{prefix}: work/verse_index does not resolve in corpus")
        return
    position = item.get("token_index")
    if not isinstance(position, int) or not 0 <= position < len(verse):
        errors.append(f"{prefix}: token_index is outside the verse")
        return
    token = verse[position]
    form, lemma = (token.get("form") or ""), (token.get("lemma") or "")
    if normalized(form) == normalized(lemma):
        errors.append(f"{prefix}: trivial — form equals lemma "
                      f"({form!r}); answerable by shape matching")
        return
    expected = (token.get("pos") or "") if drill_type == "pos" else lemma
    if not expected:
        errors.append(f"{prefix}: annotated token has no {drill_type}")
        return
    choices = item.get("choices")
    correct = item.get("correct")
    if (not isinstance(choices, list) or len(choices) != 4
            or not all(isinstance(choice, str) for choice in choices)):
        errors.append(f"{prefix}: need exactly four string choices")
        return
    if not isinstance(correct, int) or not 0 <= correct < 4:
        errors.append(f"{prefix}: correct is not a choice index")
        return
    if choices[correct] != expected:
        errors.append(f"{prefix}: correct answer {choices[correct]!r} is not "
                      f"the annotated {drill_type} {expected!r}")
    if len({normalized(choice) for choice in choices}) != 4:
        errors.append(f"{prefix}: a distractor equals the answer "
                      f"after normalization")
    if item.get("tokens") != [tok.get("form") or "" for tok in verse]:
        errors.append(f"{prefix}: bank tokens do not match the verse")


def read_labels(path: pathlib.Path = LABELS) -> dict[str, str]:
    """The tag->label map. Missing file is a failure, not a fallback."""
    try:
        raw = safeio.read_maybe_gzip(path)
    except OSError as e:
        raise ParseDrillGuardError(
            f"[parsedrill_guard] {path} unreadable ({e})") from e
    try:
        return json.loads(raw.decode("utf-8")).get("labels", {})
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ParseDrillGuardError(
            f"[parsedrill_guard] {path} is not JSON ({e})") from e


def check(drill_dir: pathlib.Path = DRILL_DIR,
          tarball: pathlib.Path = TARBALL) -> tuple[int, list[str]]:
    """Returns (item count, errors). Empty errors means clean."""
    banks = sorted(drill_dir.glob("parse-*.json.gz"))
    if not banks:
        raise ParseDrillGuardError(f"[parsedrill_guard] no banks in {drill_dir}")
    verses = read_verses(tarball)
    labels = read_labels(drill_dir / "pos_labels.json.gz")
    if not isinstance(labels, dict):
        raise ParseDrillGuardError("[parsedrill_guard] labels file has no map")
    errors: list[str] = []
    for tag, label in labels.items():
        if not isinstance(label, str) or not label:
            errors.append(f"labels: {tag!r} has no string label")
        elif label == tag:
            errors.append(f"labels: {tag!r} equals its tag")
    errors.extend(check_labels_cover_banks(banks, labels))
    count = 0
    for bank in banks:
        for item in read_bank(bank).get("items", []):
            count += 1
            check_item(item, verses, bank.name, errors)
    return count, errors


def check_labels_cover_banks(banks: list[pathlib.Path],
                             labels: dict[str, str]) -> list[str]:
    """Session 21 D2: every POS tag in a parse bank has a label to render."""
    tags: set[str] = set()
    for bank in banks:
        for item in read_bank(bank).get("items", []):
            if not isinstance(item, dict) or item.get("drill_type") != "pos":
                continue
            for choice in item.get("choices", []) or []:
                if isinstance(choice, str) and choice:
                    tags.add(choice)
    return [f"labels: bank tag {tag!r} has no label" for tag in sorted(tags)
            if tag not in labels]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="parse drills match annotation")
    ap.parse_args(argv)
    try:
        count, errors = check()
    except ParseDrillGuardError as e:
        print(str(e), file=sys.stderr)
        return 1
    if errors:
        print(f"[parsedrill_guard] FAIL — {len(errors)} unfair item(s) "
              f"of {count}:", file=sys.stderr)
        for error in errors[:20]:
            print(f"  - {error}", file=sys.stderr)
        if len(errors) > 20:
            print(f"  - ... and {len(errors) - 20} more", file=sys.stderr)
        return 1
    print(f"[parsedrill_guard] OK — {count} parse items checked; every "
          f"correct answer matches its annotation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
