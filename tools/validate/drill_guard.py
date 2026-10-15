#!/usr/bin/env python3
"""tools/validate/drill_guard.py — every cloze item is fair and traceable.

Session 18 D4. A drill bank that exists is not a drill that works (Rule 7):
for every item in every data/dist/drill/cloze-<work>.json.gz, resolved
against the corpus tarball (never the bank alone):

- the work/verse_index resolves to a real verse;
- choices[correct] is the surface token removed at blank (re-read from the
  verse, not trusted from the bank);
- the removed (lemma, pos) is unique in its verse (no ambiguity shipped);
- no distractor equals the correct answer after normalization;
- exactly four unique choices (after normalization).

Reads banks through safeio (Rule 12); the tarball is single-form, read with
tarfile like its three sibling readers.

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


class DrillGuardError(SystemExit):
    """A drill bank is unfair or untraceable. Raised, never warned."""


def normalized(text: str) -> str:
    return unicodedata.normalize("NFC", text.strip().casefold())


def read_bank(path: pathlib.Path) -> dict:
    try:
        raw = safeio.read_maybe_gzip(path)
    except OSError as e:
        raise DrillGuardError(f"[drill_guard] {path} unreadable ({e})") from e
    try:
        return json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise DrillGuardError(f"[drill_guard] {path} is not JSON ({e})") from e


def read_verses(tarball: pathlib.Path) -> dict[str, dict[int, list[dict]]]:
    """{work_slug: {verse_index: [tokens in order]}}."""
    if not tarball.is_file():
        raise DrillGuardError(f"[drill_guard] {tarball} is missing")
    verses: dict[str, dict[int, list[dict]]] = {}
    with tarfile.open(tarball, "r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile() or not member.name.endswith("/tokens.json"):
                continue
            slug = member.name.partition("/")[0]
            stream = archive.extractfile(member)
            if stream is None:
                raise DrillGuardError(f"[drill_guard] {member.name} unreadable")
            by_verse: dict[int, list[dict]] = {}
            for tok in json.loads(stream.read().decode("utf-8"))["tokens"]:
                by_verse.setdefault(tok["verse_index"], []).append(tok)
            verses[slug] = {index: sorted(toks, key=lambda tok: tok["i"])
                            for index, toks in by_verse.items()}
    if not verses:
        raise DrillGuardError("[drill_guard] no works in the corpus tarball")
    return verses


def check_item(item: dict, verses: dict[str, dict[int, list[dict]]],
               filename: str, errors: list[str]) -> None:
    prefix = f"{filename} {item.get('id', '?')}"
    if not isinstance(item, dict):
        errors.append(f"{prefix}: not an object")
        return
    slug, verse_index = item.get("work_slug"), item.get("verse_index")
    verse = (verses.get(slug) or {}).get(verse_index) \
        if isinstance(slug, str) and isinstance(verse_index, int) else None
    if not verse:
        errors.append(f"{prefix}: work/verse_index does not resolve in corpus")
        return
    blank = item.get("blank")
    if not isinstance(blank, int) or not 0 <= blank < len(verse):
        errors.append(f"{prefix}: blank is outside the verse")
        return
    removed = verse[blank]
    choices = item.get("choices")
    correct = item.get("correct")
    if (not isinstance(choices, list) or len(choices) != 4
            or not all(isinstance(choice, str) for choice in choices)):
        errors.append(f"{prefix}: need exactly four string choices")
        return
    if not isinstance(correct, int) or not 0 <= correct < 4:
        errors.append(f"{prefix}: correct is not a choice index")
        return
    if choices[correct] != (removed.get("form") or ""):
        errors.append(f"{prefix}: correct answer is not the removed token "
                      f"({choices[correct]!r} != {removed.get('form')!r})")
    if len({normalized(choice) for choice in choices}) != 4:
        errors.append(f"{prefix}: a distractor equals the answer "
                      f"after normalization")
    key = ((removed.get("lemma") or ""), (removed.get("pos") or ""))
    others = [((tok.get("lemma") or ""), (tok.get("pos") or ""))
              for pos, tok in enumerate(verse) if pos != blank]
    if key in others:
        errors.append(f"{prefix}: ambiguous — {key[0]!r}/{key[1]} occurs "
                      f"twice in the verse")
    if item.get("tokens") != [tok.get("form") or "" for tok in verse]:
        errors.append(f"{prefix}: bank tokens do not match the verse")


def check(drill_dir: pathlib.Path = DRILL_DIR,
          tarball: pathlib.Path = TARBALL) -> tuple[int, list[str]]:
    """Returns (item count, errors). Empty errors means clean."""
    banks = sorted(drill_dir.glob("cloze-*.json.gz"))
    if not banks:
        raise DrillGuardError(f"[drill_guard] no banks in {drill_dir}")
    verses = read_verses(tarball)
    errors: list[str] = []
    count = 0
    for bank in banks:
        for item in read_bank(bank).get("items", []):
            count += 1
            check_item(item, verses, bank.name, errors)
    return count, errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="cloze drills must be fair")
    ap.parse_args(argv)
    try:
        count, errors = check()
    except DrillGuardError as e:
        print(str(e), file=sys.stderr)
        return 1
    if errors:
        print(f"[drill_guard] FAIL — {len(errors)} unfair item(s) "
              f"of {count}:", file=sys.stderr)
        for error in errors[:20]:
            print(f"  - {error}", file=sys.stderr)
        if len(errors) > 20:
            print(f"  - ... and {len(errors) - 20} more", file=sys.stderr)
        return 1
    print(f"[drill_guard] OK — {count} cloze items checked; every correct "
          f"answer is its removed token")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
