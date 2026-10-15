#!/usr/bin/env python3
"""tools/emit/parsedrillgen.py — parse drills from annotated tokens.

Session 20 D4, Layer 2's second drill type. Where cloze drills blank a
word, parse drills interrogate the annotation: given a token in its verse,
name its part of speech (POS drill) or its dictionary headword (lemma
drill). Everything comes from `tokens.json` in the corpus tarball — POS,
lemma, and function tags as the annotators left them. No new data.

- POS drill: the verse with one token highlighted; four POS tags; the three
  distractors are real tags, each the majority tag of some lemma in a
  DIFFERENT frequency band than the token's lemma (same tagset, unfamiliar
  territory — guessing by familiarity fails), ordered deterministically.
- Lemma drill: a surface form in its verse; four headwords; distractors
  share the token's frequency band but are different lemmas (same rule as
  cloze distractors), ordered by frequency closeness.

SKIPS (counted per reason, never hidden): tokens without lemma/POS;
punctuation (a part of speech for "." teaches nothing); trivial identity
(Session 21 D3: token.form == token.lemma after normalization — answerable
by shape matching, e.g. ⲁ→ⲁ); a surface form whose reading is ambiguous in
its own verse (same form, different POS or lemma beside it); fewer than
three valid distractors. At most one POS item and one lemma item per verse
(rotated among viable slots), keeping banks comparable (~2.6k × 2).

Frequency bands reuse quizgen's 300/1,000 rank thresholds on lemma totals
across all six works. Determinism throughout; gzip mtime=0.

Output: data/dist/drill/parse-<work>.json.gz, written through safeio
(Rule 12). Items carry drill_type "pos"/"lemma"; cloze banks carry "cloze".

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import pathlib
import sys
import tarfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE))

import safeio  # noqa: E402
from drillgen import difficulty  # noqa: E402  (one band vocabulary)
from quizgen import choice_key, place_choices  # noqa: E402  (one shuffle)
import unicodedata  # noqa: E402


def _same(form: str, lemma: str) -> bool:
    """Session 21 D3: a token identical to its lemma asks nothing.

    ⲁ→ⲁ is answerable by shape matching — no Coptic required. Normalized
    (NFC, strip, casefold) so coincidental case/markup differences do not
    smuggle trivial items through.
    """
    clean = lambda text: unicodedata.normalize("NFC", text.strip().casefold())
    return bool(form) and clean(form) == clean(lemma)

TARBALL = ROOT / "data" / "dist" / "corpus" / "corpus.tar.gz"
DRILL_DIR = ROOT / "data" / "dist" / "drill"
DRILL_SEED = "parsedrillgen-v1"


def fail(message: str) -> SystemExit:
    return SystemExit(f"[parsedrillgen] FAIL — {message}")


def read_tokens(tarball: pathlib.Path) -> dict[str, list[dict]]:
    """work_slug -> tokens in tarball order."""
    if not tarball.is_file():
        raise fail(f"{tarball} is missing; fetch the corpus first")
    works: dict[str, list[dict]] = {}
    with tarfile.open(tarball, "r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile() or not member.name.endswith("/tokens.json"):
                continue
            slug = member.name.partition("/")[0]
            stream = archive.extractfile(member)
            if stream is None:
                raise fail(f"{member.name}: cannot read corpus member")
            works[slug] = json.loads(stream.read().decode("utf-8"))["tokens"]
    if not works:
        raise fail(f"no works in {tarball}")
    return works


def lemma_stats(all_tokens: list[dict]) -> tuple[dict[str, int], dict[str, int]]:
    totals: dict[str, int] = {}
    for tok in all_tokens:
        if tok.get("lemma"):
            totals[tok["lemma"]] = totals.get(tok["lemma"], 0) + 1
    ranked = sorted(totals, key=lambda lemma: (-totals[lemma], lemma))
    return totals, {lemma: rank + 1 for rank, lemma in enumerate(ranked)}


def majority_pos(all_tokens: list[dict]) -> dict[str, str]:
    """Lemma -> its most frequent POS (ties: first seen)."""
    counts: dict[str, dict[str, int]] = {}
    for tok in all_tokens:
        lemma, pos = tok.get("lemma") or "", tok.get("pos") or ""
        if lemma and pos:
            counts.setdefault(lemma, {}).setdefault(pos, 0)
            counts[lemma][pos] += 1
    return {lemma: max(positions, key=lambda pos: (positions[pos], pos))
            for lemma, positions in counts.items()}


def build_pos_items(slug: str, tokens: list[dict], totals: dict[str, int],
                    ranks: dict[str, int], pos_of: dict[str, str]
                    ) -> tuple[list[dict], dict[str, int]]:
    """One POS item per verse (first unambiguous token)."""
    by_verse: dict[int, list[dict]] = {}
    for tok in tokens:
        by_verse.setdefault(tok["verse_index"], []).append(tok)
    tag_bands: dict[str, str] = {}
    for lemma, pos in pos_of.items():
        band = difficulty(ranks.get(lemma, 10 ** 9))
        tag_bands.setdefault(pos, band)
    items: list[dict] = []
    skipped = {"no_token": 0, "ambiguous": 0, "few_distractors": 0,
                   "trivial": 0}
    for verse_index in sorted(by_verse):
        verse = sorted(by_verse[verse_index], key=lambda tok: tok["i"])
        if not verse:
            skipped["no_token"] += 1
            continue
        # Every slot is evaluated (reasons counted); the item rotates among
        # the viable ones by verse_index, so drills do not all ask about
        # token 0. Deterministic: same verse, same slot, every bake.
        viable: list[tuple[int, dict, list[str], str]] = []
        for position, tok in enumerate(verse):
            pos, lemma, form = (tok.get("pos") or "", tok.get("lemma") or "",
                                tok.get("form") or "")
            if not pos or not lemma or not form or pos == "PUNCT":
                continue
            if _same(form, lemma):
                skipped["trivial"] += 1
                continue
            readings = {(t.get("pos") or "") for t in verse
                        if (t.get("form") or "") == form}
            if len(readings) > 1:
                skipped["ambiguous"] += 1
                continue
            band = difficulty(ranks.get(lemma, 10 ** 9))
            options = sorted({tag for tag, tag_band in tag_bands.items()
                              if tag != pos and tag_band != band
                              and tag != "PUNCT"})
            if len(options) < 3:
                skipped["few_distractors"] += 1
                continue
            viable.append((position, tok, options[:3], band))
        if not viable:
            skipped["no_token"] += 1
            continue
        position, tok, distractors, band = viable[verse_index % len(viable)]
        pos, lemma, form = (tok.get("pos") or "", tok.get("lemma") or "",
                            tok.get("form") or "")
        item_id = f"p-{slug}-{verse_index:05d}"
        choices, correct = place_choices(
            pos, distractors, DRILL_SEED + ":" + item_id)
        items.append({
            "id": item_id, "drill_type": "pos", "type": "parse",
            "work_slug": slug, "verse_index": verse_index,
            "ref": tok.get("ref", ""),
            "tokens": [t.get("form") or "" for t in verse],
            "token_index": position,
            "choices": choices, "correct": correct,
            "source": {"form": form, "lemma": lemma, "pos": pos,
                       "func": tok.get("func", ""),
                       "freq_band": band,
                       "distractor_tags": distractors},
            "context": {
                "prev": verse[position - 1].get("form") if position > 0 else None,
                "next": verse[position + 1].get("form")
                if position + 1 < len(verse) else None},
        })
    return items, skipped


def build_lemma_items(slug: str, tokens: list[dict], totals: dict[str, int],
                      ranks: dict[str, int]
                      ) -> tuple[list[dict], dict[str, int]]:
    """One lemma item per verse (first unambiguous token)."""
    by_verse: dict[int, list[dict]] = {}
    for tok in tokens:
        by_verse.setdefault(tok["verse_index"], []).append(tok)
    items: list[dict] = []
    skipped = {"no_token": 0, "ambiguous": 0, "few_distractors": 0,
                   "trivial": 0}
    for verse_index in sorted(by_verse):
        verse = sorted(by_verse[verse_index], key=lambda tok: tok["i"])
        if not verse:
            skipped["no_token"] += 1
            continue
        # Same rotation as POS items: evaluate every slot, rotate the item
        # among the viable ones by verse_index (see build_pos_items).
        viable: list[tuple[int, dict, list[str], str]] = []
        for position, tok in enumerate(verse):
            pos, lemma, form = (tok.get("pos") or "", tok.get("lemma") or "",
                                tok.get("form") or "")
            if not pos or not lemma or not form or pos == "PUNCT":
                continue
            if _same(form, lemma):
                skipped["trivial"] += 1
                continue
            readings = {(t.get("lemma") or "") for t in verse
                        if (t.get("form") or "") == form}
            if len(readings) > 1:
                skipped["ambiguous"] += 1
                continue
            band = difficulty(ranks.get(lemma, 10 ** 9))
            target_total = totals.get(lemma, 1)
            options: list[tuple[float, str]] = []
            seen = {choice_key(lemma)}
            for cand in sorted(totals):
                if cand == lemma or choice_key(cand) in seen:
                    continue
                if difficulty(ranks.get(cand, 10 ** 9)) != band:
                    continue
                if any((t.get("lemma") or "") == cand for t in verse):
                    continue  # fits this verse; cannot be a wrong answer
                seen.add(choice_key(cand))
                options.append((abs(math.log((totals[cand] + 1)
                                             / (target_total + 1))), cand))
            options.sort()
            if len(options) < 3:
                skipped["few_distractors"] += 1
                continue
            viable.append((position, tok,
                           [cand for _, cand in options[:3]], band))
        if not viable:
            skipped["no_token"] += 1
            continue
        position, tok, distractors, band = viable[verse_index % len(viable)]
        pos, lemma, form = (tok.get("pos") or "", tok.get("lemma") or "",
                            tok.get("form") or "")
        item_id = f"l-{slug}-{verse_index:05d}"
        choices, correct = place_choices(
            lemma, distractors, DRILL_SEED + ":" + item_id)
        items.append({
            "id": item_id, "drill_type": "lemma", "type": "parse",
            "work_slug": slug, "verse_index": verse_index,
            "ref": tok.get("ref", ""),
            "tokens": [t.get("form") or "" for t in verse],
            "token_index": position,
            "choices": choices, "correct": correct,
            "source": {"form": form, "lemma": lemma, "pos": pos,
                       "func": tok.get("func", ""),
                       "freq_band": band,
                       "distractor_lemmas": distractors},
            "context": {
                "prev": verse[position - 1].get("form") if position > 0 else None,
                "next": verse[position + 1].get("form")
                if position + 1 < len(verse) else None},
        })
    return items, skipped


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="parse drills from annotations")
    ap.parse_args(argv)
    tokens_by_work = read_tokens(TARBALL)
    all_tokens = [tok for tokens in tokens_by_work.values() for tok in tokens]
    totals, ranks = lemma_stats(all_tokens)
    pos_of = majority_pos(all_tokens)

    DRILL_DIR.mkdir(parents=True, exist_ok=True)
    grand = {"pos": 0, "lemma": 0}
    for slug in tokens_by_work:
        tokens = tokens_by_work[slug]
        pos_items, pos_skipped = build_pos_items(
            slug, tokens, totals, ranks, pos_of)
        lemma_items, lemma_skipped = build_lemma_items(
            slug, tokens, totals, ranks)
        items = sorted(pos_items + lemma_items,
                       key=lambda item: (item["verse_index"], item["id"]))
        payload = json.dumps({"work_slug": slug, "items": items},
                             ensure_ascii=False).encode("utf-8")
        dest = DRILL_DIR / f"parse-{slug}.json.gz"
        size = safeio.write_verified(
            dest, gzip.compress(payload, compresslevel=9, mtime=0))
        grand["pos"] += len(pos_items)
        grand["lemma"] += len(lemma_items)
        print(f"[parsedrillgen] {slug}: {len(pos_items)} pos + "
              f"{len(lemma_items)} lemma ({size:,} B gz; "
              f"skipped pos={pos_skipped} lemma={lemma_skipped})")
    print(f"[parsedrillgen] {grand['pos']} pos + {grand['lemma']} lemma "
          f"in {len(tokens_by_work)} bank(s)")
    if grand["pos"] + grand["lemma"] < 10:
        raise fail("fewer than 10 parse items; refusing a drill type with nothing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
