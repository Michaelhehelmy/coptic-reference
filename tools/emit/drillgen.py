#!/usr/bin/env python3
"""tools/emit/drillgen.py — cloze (fill-in-the-blank) drills from real verses.

Session 18 D4, the last learning-layer deliverable. Quizzes teach vocabulary;
drills teach grammar-in-context: one content token removed per corpus verse,
four attested surface forms to choose from, every item traceable to data.
No authoring cost, no generated content, no accounts, no server.

WHAT COUNTS AS REMOVABLE. A token is blankable iff its POS is content:
anything except ART (article), PREP (preposition), PUNCT (a blanked full
stop has no lexical answer), and fused bound forms (tags containing
"_PPERO"/"_PPERS", e.g. PREP_PPERO, APST_PPERS: a fused preposition+pronoun
or auxiliary+pronoun is bound morphology, the "bound marker" of the brief).
Function words stay visible in the verse; only content tokens are blanked.
The fused-tag reading of "bound marker" is an interpretation, stated here so
a linguist can correct it (Sahidic/Bohairic Scriptorium tagset).

DISTRACTORS. Three surface forms from lemmas sharing the removed token's POS
and frequency band (beginner/intermediate/advanced by lemma-frequency rank,
same 300/1,000 thresholds as quizgen BAND_LIMITS), ordered deterministically
by closeness in frequency then lemma, first three win. Each distractor is the
lemma's most frequent attested surface form — real tokens, never synthesized.

SKIPS (a skipped verse ships nothing; skips are counted, not hidden):

- no blankable token in the verse;
- ambiguity: another token in the same verse shares the removed (lemma, pos);
- grammatical acceptability proxy: a distractor candidate whose (lemma, pos)
  occurs elsewhere in the same verse demonstrably fits this verse, so it is
  rejected as a candidate (conservative: may skip fair items, never ships a
  probably-acceptable one);
- fewer than three surviving distractors.

Determinism: verses in tarball order, slots in token order, distractors in
(frequency-closeness, lemma) order, choices shuffled by a seeded shuffle
borrowed from quizgen (one shuffle implementation, not two). gzip mtime=0.

Output: data/dist/drill/cloze-<work>.json.gz, one bank per work, written
through safeio (Rule 12).

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
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
from quizgen import choice_key, place_choices  # noqa: E402  (one shuffle)

TARBALL = ROOT / "data" / "dist" / "corpus" / "corpus.tar.gz"
DRILL_DIR = ROOT / "data" / "dist" / "drill"
DRILL_SEED = "drillgen-v1"

#: POS never blanked. ART/PREP per brief; PUNCT (no lexical answer); fused
#: bound forms (the brief's "bound marker", interpretation documented above).
NON_REMOVABLE_PREFIXES = ("ART", "PREP", "PUNCT")
NON_REMOVABLE_INFIX = ("_PPERO", "_PPERS")


def is_blankable(pos: str) -> bool:
    """Content-token test. Anything else stays visible in the verse."""
    if not isinstance(pos, str) or not pos:
        return False
    if pos in NON_REMOVABLE_PREFIXES or pos.startswith(("ART", "PREP", "PUNCT")):
        return False
    if any(infix in pos for infix in NON_REMOVABLE_INFIX):
        return False
    return True


def fail(message: str) -> SystemExit:
    return SystemExit(f"[drillgen] FAIL — {message}")


def read_corpus(tarball: pathlib.Path) -> dict[str, dict]:
    """{work_slug: {"tokens": [...], "meta": {...}}} in tarball order."""
    if not tarball.is_file():
        raise fail(f"{tarball} is missing; fetch the corpus first")
    works: dict[str, dict] = {}
    with tarfile.open(tarball, "r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            slug, _, name = member.name.partition("/")
            if not slug or name not in {"meta.json", "tokens.json"}:
                continue
            stream = archive.extractfile(member)
            if stream is None:
                raise fail(f"{member.name}: cannot read corpus member")
            works.setdefault(slug, {})[name] = json.loads(
                stream.read().decode("utf-8"))
    for slug, docs in works.items():
        if "tokens.json" not in docs:
            raise fail(f"{slug}: tokens.json is missing from the corpus tarball")
    return works


def lemma_stats(tokens_by_work: dict[str, list[dict]]) -> tuple[dict[str, int], dict[str, int]]:
    """Lemma -> total count; lemma -> frequency rank (1 = most frequent)."""
    totals: dict[str, int] = {}
    for tokens in tokens_by_work.values():
        for tok in tokens:
            lemma = tok.get("lemma") or ""
            if lemma:
                totals[lemma] = totals.get(lemma, 0) + 1
    ranked = sorted(totals, key=lambda lemma: (-totals[lemma], lemma))
    return totals, {lemma: rank + 1 for rank, lemma in enumerate(ranked)}


def difficulty(rank: int) -> str:
    """Same band vocabulary as quizgen BAND_LIMITS."""
    if rank <= 300:
        return "beginner"
    if rank <= 1000:
        return "intermediate"
    return "advanced"


def representative_forms(tokens: list[dict]) -> dict[str, str]:
    """Lemma -> its most frequent attested surface form (ties: first seen)."""
    counts: dict[str, dict[str, int]] = {}
    first: dict[str, str] = {}
    for tok in tokens:
        lemma, form = tok.get("lemma") or "", tok.get("form") or ""
        if not lemma or not form:
            continue
        counts.setdefault(lemma, {}).setdefault(form, 0)
        counts[lemma][form] += 1
        first.setdefault(lemma, form)
    out: dict[str, str] = {}
    for lemma, forms in counts.items():
        best = max(forms.values())
        out[lemma] = next(
            form for tok in tokens
            if tok.get("lemma") == lemma and (form := tok.get("form") or "") in forms
            and forms[form] == best)
    return out


def pos_of_lemmas(all_tokens: list[dict]) -> dict[str, str]:
    """Lemma -> its most frequent POS across the corpus (ties: first seen)."""
    counts: dict[str, dict[str, int]] = {}
    for tok in all_tokens:
        lemma, pos = tok.get("lemma") or "", tok.get("pos") or ""
        if lemma and pos:
            counts.setdefault(lemma, {}).setdefault(pos, 0)
            counts[lemma][pos] += 1
    return {lemma: max(positions, key=lambda pos: (positions[pos], pos))
            for lemma, positions in counts.items()}


def build_items(slug: str, tokens: list[dict], totals: dict[str, int],
                ranks: dict[str, int], rep: dict[str, str],
                pos_of: dict[str, str]) -> tuple[list[dict], dict[str, int]]:
    """One cloze item per verse that admits a fair blank. Skips counted."""
    by_verse: dict[int, list[dict]] = {}
    for tok in tokens:
        by_verse.setdefault(tok["verse_index"], []).append(tok)

    items: list[dict] = []
    skipped = {"no_content": 0, "ambiguous": 0, "few_distractors": 0}
    for verse_index in sorted(by_verse):
        verse = sorted(by_verse[verse_index], key=lambda tok: tok["i"])
        if not any(is_blankable(tok.get("pos") or "") and (tok.get("form") or "")
                   for tok in verse):
            skipped["no_content"] += 1
            continue
        verse_keys = [(tok.get("lemma") or "", tok.get("pos") or "") for tok in verse]
        made = False
        for position, tok in enumerate(verse):
            pos = tok.get("pos") or ""
            lemma = tok.get("lemma") or ""
            form = tok.get("form") or ""
            if not is_blankable(pos) or not lemma or not form:
                continue
            if verse_keys.count((lemma, pos)) > 1:
                skipped["ambiguous"] += 1
                continue
            band = difficulty(ranks.get(lemma, 10 ** 9))
            target_total = totals.get(lemma, 1)
            options: list[tuple[float, str, str]] = []
            seen_forms = {choice_key(form)}
            for cand_lemma in sorted(totals):
                if cand_lemma == lemma:
                    continue
                if pos_of.get(cand_lemma) != pos:
                    continue
                if difficulty(ranks.get(cand_lemma, 10 ** 9)) != band:
                    continue
                if (cand_lemma, pos) in verse_keys:
                    # Grammatical-acceptability proxy (documented): a word
                    # that already occurs in this verse demonstrably fits its
                    # grammar, so it cannot be a wrong answer here.
                    continue
                cand_form = rep.get(cand_lemma, "")
                if not cand_form or choice_key(cand_form) in seen_forms:
                    continue
                seen_forms.add(choice_key(cand_form))
                total = totals[cand_lemma]
                options.append((abs(math.log((total + 1) / (target_total + 1))),
                                cand_lemma, cand_form))
            options.sort()
            if len(options) < 3:
                skipped["few_distractors"] += 1
                continue
            distractors = [cand_form for _, _, cand_form in options[:3]]
            distractor_lemmas = [cand_lemma for _, cand_lemma, _ in options[:3]]
            item_id = f"d-{slug}-{verse_index:05d}"
            choices, correct = place_choices(
                form, distractors, DRILL_SEED + ":" + item_id)
            prev_tok = verse[position - 1].get("form") if position > 0 else None
            next_tok = verse[position + 1].get("form") \
                if position + 1 < len(verse) else None
            items.append({
                "id": item_id,
                "type": "cloze",
                "work_slug": slug,
                "verse_index": verse_index,
                "ref": verse[position].get("ref", ""),
                "tokens": [tok.get("form") or "" for tok in verse],
                "blank": position,
                "choices": choices,
                "correct": correct,
                "source": {
                    "lemma": lemma,
                    "pos": pos,
                    "freq_total": target_total,
                    "freq_band": band,
                    "removed_form": form,
                    "distractor_lemmas": distractor_lemmas,
                },
                "context": {"prev": prev_tok, "next": next_tok},
            })
            break
    return items, skipped


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="cloze drills from real verses")
    ap.parse_args(argv)
    works = read_corpus(TARBALL)
    tokens_by_work = {slug: docs["tokens.json"]["tokens"]
                      for slug, docs in works.items()}
    all_tokens = [tok for tokens in tokens_by_work.values() for tok in tokens]
    totals, ranks = lemma_stats(tokens_by_work)
    rep = representative_forms(all_tokens)
    pos_of = pos_of_lemmas(all_tokens)

    DRILL_DIR.mkdir(parents=True, exist_ok=True)
    grand = {"items": 0, "works": 0}
    for slug in works:
        tokens = tokens_by_work[slug]
        items, skipped = build_items(slug, tokens, totals, ranks, rep, pos_of)
        payload = json.dumps({"work_slug": slug, "items": items},
                             ensure_ascii=False).encode("utf-8")
        dest = DRILL_DIR / f"cloze-{slug}.json.gz"
        size = safeio.write_verified(
            dest, gzip.compress(payload, compresslevel=9, mtime=0))
        grand["items"] += len(items)
        grand["works"] += 1
        print(f"[drillgen] {slug}: {len(items)} items "
              f"({size:,} B gz; skipped {skipped})")
    print(f"[drillgen] {grand['items']} items in {grand['works']} bank(s)")
    if grand["items"] < 10:
        raise fail("fewer than 10 drill items; refusing a drill page with nothing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
