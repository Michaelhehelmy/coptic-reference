#!/usr/bin/env python3
"""tools/validate/lesson_vocab_guard.py — lesson Coptic is dictionary-backed.

Session 20 D0 (C1). Every Coptic token a lesson teaches must resolve to a
dictionary entry, and the gloss the lesson gives it must appear in that
entry's glosses. Taught means `TOKEN (gloss, ...)`: a Coptic token directly
followed by a Latin parenthetical. Phrase translations in quotes ("his
wife"), letter mentions (single characters: use/mention), and front-matter
prose are not taught pairs.

Three rules, one per Session 20 negative control:

- taught TOKEN resolves to an entry by norm_key (invented lemma fails);
- every gloss segment (split on , ;) equals an entry gloss segment
  (wrong gloss fails);
- a taught TOKEN with no entry fails even with a perfect gloss (missing
  entry fails: ⲡⲉϫⲉ taught as "to say" must fail, not silently pass).

Bare (untaught) multi-character tokens must also resolve — or be declared in
front matter `unlisted_forms: {FORM: reason}` (real headword gaps like ⲧⲉϥ,
ⲡⲉϫⲉ, ⲁⲛ); an exempted form must still be an attested corpus surface form,
so the exemption cannot hide a typo. Vocabulary front-matter lemmas must
resolve (already true; enforced here).

Reads shards through shardio and the tarball member list like its siblings
(Rule 12: shards via shardio; tarball single-form).

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import tarfile
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import collate  # noqa: E402
import shardio  # noqa: E402
import yaml  # noqa: E402

LESSONS_DIR = ROOT / "content" / "lessons"
TARBALL = ROOT / "data" / "dist" / "corpus" / "corpus.tar.gz"

COP = re.compile(r"[Ⲁ-⳿Ϣ-ϯ]+")
PAIR = re.compile(r"([Ⲁ-⳿Ϣ-ϯ]+)\s*\(([^()]*[a-zA-Z][^()]*)\)")


class LessonVocabError(SystemExit):
    """A lesson teaches what the dictionary does not say."""


def normalized(text: str) -> str:
    text = unicodedata.normalize("NFC", text.strip().casefold())
    text = re.sub(r"\s+", " ", text)
    # Parenthetical qualifiers ("go (on land or water)") and the English
    # infinitive marker ("to dwell" vs "dwell") carry no lexical meaning;
    # both sides are stripped identically so neither direction is favored.
    text = re.sub(r"\([^()]*\)", "", text)
    text = re.sub(r"(?:^|(?<=[\s;,.]))to ", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" .!?,;:")


def segments(gloss: str) -> list[str]:
    """Comma/semicolon segments of one gloss string.

    Normalize FIRST (qualifiers and "to " removed), split second: splitting
    the raw string fragments parentheticals across segments ("envoy (general"
    / "or specific sense unclear)"), and no fragment ever matches again.
    Each piece is stripped again after the split (" do" is not "do").
    """
    return [part.strip(" .!?,;:") for part in
            re.split(r"[,;]", normalized(gloss)) if part.strip(" .!?,;:")]


def norm(token: str) -> str:
    return collate.canon_for_sort(unicodedata.normalize("NFC", token))


def load_entries() -> dict[str, dict]:
    """norm_key -> {id, glosses}. First entry wins a norm collision."""
    index: dict[str, dict] = {}
    for shard in shardio.shard_paths(ROOT / "data" / "dist" / "dict"):
        for entry in shardio.read_shard(shard).get("entries", []) or []:
            index.setdefault(entry.get("norm_key", ""), entry)
    if not index:
        raise LessonVocabError("[lesson_vocab_guard] no baked shards")
    return index


def load_forms() -> set[str]:
    """Attested corpus surface forms (exemption backstop)."""
    if not TARBALL.is_file():
        raise LessonVocabError(f"[lesson_vocab_guard] {TARBALL} is missing")
    forms: set[str] = set()
    with tarfile.open(TARBALL, "r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile() or not member.name.endswith("/tokens.json"):
                continue
            stream = archive.extractfile(member)
            if stream is None:
                raise LessonVocabError(
                    f"[lesson_vocab_guard] {member.name} unreadable")
            for tok in json.loads(stream.read().decode("utf-8"))["tokens"]:
                if tok.get("form"):
                    forms.add(tok["form"])
    return forms


def read_lesson(path: pathlib.Path) -> tuple[dict, str]:
    """Front-matter lesson block + body (README.md has none: skipped)."""
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text.split("---", 2)[1])
    return data.get("lesson") or {}, text.split("---", 2)[2]


def check_pair(token: str, gloss: str, entries: dict[str, dict],
               filename: str, errors: list[str]) -> None:
    """One taught pair. Order matters: entry first, then gloss segments."""
    entry = entries.get(norm(token))
    if entry is None:
        errors.append(f"{filename}: {token!r} taught as {gloss!r} but has "
                      f"no dictionary entry")
        return
    available = {segment for gloss_obj in entry.get("glosses", [])
                 for segment in segments(gloss_obj.get("text", ""))}
    for piece in segments(gloss):
        if piece not in available:
            errors.append(
                f"{filename}: {token!r} glossed {piece!r}, not in "
                f"{entry.get('id')} ({sorted(available)[:6]})")
            return


def check_file(path: pathlib.Path, entries: dict[str, dict],
               forms: set[str]) -> list[str]:
    """All lesson_vocab_guard errors in one lesson file."""
    errors: list[str] = []
    name = path.name
    try:
        lesson, body = read_lesson(path)
    except (OSError, ValueError, AttributeError) as e:
        return [f"{name}: unreadable front matter ({e})"]
    if not lesson:
        return [f"{name}: no `lesson` front-matter block"]
    for lemma in (lesson.get("vocabulary") or {}).get("lemmas", []):
        if norm(lemma) not in entries:
            errors.append(f"{name}: vocabulary {lemma!r} has no entry")
    taught: set[str] = set()
    for match in PAIR.finditer(body):
        token, gloss = match.group(1), match.group(2)
        if COP.search(gloss):
            continue  # metalinguistic paren, not a taught gloss
        taught.add(token)
        check_pair(token, gloss, entries, name, errors)
    exempt = lesson.get("unlisted_forms") or {}
    if not isinstance(exempt, dict):
        errors.append(f"{name}: unlisted_forms is not a mapping")
        exempt = {}
    for token in COP.findall(body):
        if len(token) < 2:
            continue  # letter mention (use/mention), not a taught token
        if token in taught or norm(token) in entries:
            continue
        reason = exempt.get(token, "")
        if not reason:
            errors.append(f"{name}: {token!r} has no entry and is not "
                          f"declared in unlisted_forms")
        elif token not in forms:
            errors.append(f"{name}: exempted {token!r} is not even an "
                          f"attested corpus form")
    return errors


def check(lessons_dir: pathlib.Path = LESSONS_DIR) -> tuple[int, list[str]]:
    """Returns (lesson count, errors). Empty errors means clean."""
    entries = load_entries()
    forms = load_forms()
    errors: list[str] = []
    count = 0
    for path in sorted(lessons_dir.glob("[0-9]*.md")):
        count += 1
        errors.extend(check_file(path, entries, forms))
    if not count:
        raise LessonVocabError(f"[lesson_vocab_guard] no lessons in {lessons_dir}")
    return count, errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="lesson Coptic is dictionary-backed")
    ap.parse_args(argv)
    try:
        count, errors = check()
    except LessonVocabError as e:
        print(str(e), file=sys.stderr)
        return 1
    if errors:
        print(f"[lesson_vocab_guard] FAIL — {len(errors)} unbacked token(s) "
              f"in {count} lessons:", file=sys.stderr)
        for error in errors[:20]:
            print(f"  - {error}", file=sys.stderr)
        if len(errors) > 20:
            print(f"  - ... and {len(errors) - 20} more", file=sys.stderr)
        return 1
    print(f"[lesson_vocab_guard] OK — {count} lessons; every taught token "
          f"resolves with its gloss")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
