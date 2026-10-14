#!/usr/bin/env python3
"""tools/pos.py — the controlled part-of-speech vocabulary.

Session 6 D2 / C3. The merge was carrying **55 distinct POS strings** across
11,369 entries, of which 136 entries (1%) held non-ASCII values. They came from
three sources that do not agree:

  - CCL, which uses **German** abbreviations: `Subst.`, `Vb.`, `Adj.`, `Adv.`,
    `Präp.`, `Konj.`, `Pron.`, `Zahlwort`, `Interjektion`, `Possessivartikel` …
  - Kaikki/Wiktextract, which uses **English** Wikidata-ish tags: `n`, `v`,
    `adj`, `adv`, `prep`, `pron`, `num`, `name`, `particle`, `art`, `det` …
  - UD CoNLL-U, which uses its own **universal** tags.

A reader filtering "show me verbs" should not have to know that CCL says `Vb.`
and Kaikki says `v`. And a site that renders `Präp.` next to `prep` next to
`prep_phrase` looks like three languages in one dropdown.

The controlled set is the **already-English tags that were genuinely in use**,
not an invented taxonomy. Nothing was normalised to a tag that did not already
appear in the data, except where a German form is unambiguously one of them.

Two decisions worth stating:

**`unknown` exists.** CCL marks four values with `?` — `Subst.?`, `Adj.?`,
`Vb.?` and a bare `?`. For the bare `?` there is no information at all, and
guessing `n` would be inventing data. So `unknown` is in the controlled set, and
the original is recorded in the entry's attributions.

**Normalisation happens at MERGE time, not emit time** (C3). The merge is where
three sources become one entry; normalising afterwards would mean the shipped
shards differ from what the merge produced, and a re-merge would lose the
normalisation. Normalising at merge also means `dry_run --real` validates the
same POS values a reader sees.

The original value is preserved in `attributions[]` whenever it differs from the
normalised form, so nothing is lost and CC BY-SA §3(b) stays satisfiable.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

#: The controlled vocabulary. Every normalised value must be in here; the assert
#: in `normalize` is what enforces that, so adding a POS upstream fails the build
#: rather than silently widening the vocabulary.
CONTROLLED: frozenset[str] = frozenset({
    # already present in the data, English
    "n", "v", "adj", "adv", "prep", "pron", "num", "name", "particle",
    "art", "det", "conj", "interj", "char", "symbol", "phrase",
    "pfx", "sfx", "infix", "prep_phrase",
    # added deliberately
    "unknown",
})

#: German -> English. Keys are EXACT source strings, matched case-sensitively,
#: because a fuzzy match on a POS tag is a guess about a word's grammar.
DE_TO_EN: dict[str, str] = {
    # CCL abbreviations
    "Subst.": "n",
    "Vb.": "v",
    # Auxiliary verb. Mapped to `v` rather than introducing an `aux` tag for a
    # single entry: a controlled vocabulary with one member is not a category,
    # and `v` is not wrong. If auxiliary verbs become common, add `aux` then.
    "Vb. Hilfsverb.": "v",
    "Adj.": "adj",
    "Adv.": "adv",
    "Präp.": "prep",
    "Konj.": "conj",
    "Pron.": "pron",
    "Dem. Pron.": "pron",
    "Poss. Pron.": "pron",
    "Interr. Pron.": "interj",
    "Selbst. Pers. Pron.": "pron",
    "Zahlwort": "num",
    "Zahlzeichen": "num",
    "Interjektion": "interj",
    "Partikel": "particle",
    "Partikel, enklitisch": "particle",
    "Possessivartikel": "det",
    "bestimmter Artikel": "art",
    "unbestimmter Artikel": "art",
    "Suffixpronomen": "pron",
    "Präfixpronomen (Präsens I)": "pron",
    "Kompositum": "n",
    "Satzkonverter": "conj",
    "unpersönlicher Ausdruck": "phrase",
    # prefixes
    "Präfix": "pfx",
    "Nominalpräfix": "pfx",
    "Verbalpräfix": "pfx",
    "Adjektivpräfix": "pfx",
    "Possessivpräfix": "pfx",
    "Präfix der Ordinalzahlen": "pfx",
    # English-ish aliases already in the data
    "phr": "phrase",
    "prep_phrase": "prep_phrase",
    "pfx": "pfx", "sfx": "sfx", "infix": "infix",
    # CCL uncertainty markers: the base tag is the honest reading, and the `?`
    # is preserved in the entry's attributions rather than silently dropped.
    "Subst.?": "n",
    "Adj.?": "adj",
    "Vb.?": "v",
    "?": "unknown",
}

#: Keys that carried a CCL uncertainty marker, so merge can say so out loud.
UNCERTAIN: frozenset[str] = frozenset({"Subst.?", "Adj.?", "Vb.?", "?"})


class PosVocabularyError(ValueError):
    """A POS value that is neither in the controlled set nor in the map.

    Deliberately fatal. The alternative — silently widening CONTROLLED to
    whatever arrived — is how a controlled vocabulary stops being controlled.
    """


def normalize(value: str) -> str:
    """Map one POS value to the controlled set, or raise."""
    v = (value or "").strip()
    if v in CONTROLLED:
        return v
    if v in DE_TO_EN:
        return DE_TO_EN[v]
    raise PosVocabularyError(
        f"POS {value!r} is not in the controlled vocabulary and has no mapping. "
        f"Add it to tools/pos.py CONTROLLED (if it is already English) or to "
        f"DE_TO_EN (if it is German or another source's tag) — deliberately, in "
        f"this pull request. Do not let the vocabulary widen itself: a controlled "
        f"set that accepts anything controls nothing.")


def normalize_list(values: list[str] | None) -> tuple[list[str], list[str]]:
    """Normalise a list. Returns (normalised, originals_that_differed)."""
    out: list[str] = []
    changed: list[str] = []
    for v in values or []:
        n = normalize(v)
        if n not in out:          # de-duplicate: n+adj -> adj
            out.append(n)
        if n != v:
            changed.append(v)
    for n in out:
        if n not in CONTROLLED:   # belt and braces; normalize() already checks
            raise PosVocabularyError(f"normalised POS {n!r} escaped the set")
    return out, changed


def describe() -> str:
    lines = [f"controlled vocabulary: {len(CONTROLLED)} values"]
    lines.append("  " + ", ".join(sorted(CONTROLLED)))
    lines.append(f"mappings: {len(DE_TO_EN)} source values -> controlled")
    return "\n".join(lines)
