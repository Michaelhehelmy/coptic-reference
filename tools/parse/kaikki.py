#!/usr/bin/env python3
"""tools/parse/kaikki.py — streaming parser for the Kaikki Coptic JSONL.

Session 3, D1. The input is 62,813,016 bytes / 3,293 lines, pinned in
tools/sources.lock (v4 §7.1). It is read ONE LINE AT A TIME and never held in
memory: `json.loads` per line, yield, discard. Peak RSS is one record, not one
file. `iter_records` is a generator, so a caller that stops early has read only
what it consumed.

Why streaming is not optional here: the plan's own build has a 20-minute
Cloudflare Pages timeout, and a reader that slurps 63 MB to emit 3,293 dicts is
a reader whose memory profile nobody measured. See also v4 §6.1 — the corpus
itself became a compressed tarball for the same class of reason.

ROLE, stated plainly: Kaikki is **SUPPLEMENT ONLY**. Per tools/sources.lock it is
"3,293 of ~11,500 entries. Not the dictionary backbone." CCL and CDO are the
backbone. This parser must therefore be *lossy about wording and careful about
structure*: it keeps every gloss, because a gloss is data, but it discards
Wiktionary category metadata that is about the Wiktionary page rather than the
Coptic word.

SCHEMA-DRIFT GATE (v4 §7.1: "records < 2500 fails the build"). A drop from 3,293
to, say, 900 means the extract changed shape, not that Coptic shrank. That is a
human decision, so it is an exception, not a warning. See `count_records`.

LICENCE: project code, Apache-2.0. Kaikki content is CC BY-SA 4.0 OR GFDL.
"""
from __future__ import annotations

import json
import pathlib
import sys
from typing import Iterator

# ── pinned provenance. Every record carries this, without exception. ─────────
SOURCE_ID = "Kaikki"
SOURCE_LICENCE = "CC-BY-SA-4.0 OR GFDL"
SOURCE_DOI = ""            # kaikki.org publishes no DOI; cite the extractor paper
SOURCE_CITE = ("Ylönen, T. (2022). Wiktextract: Wiktionary as Machine-Readable "
               "Structured Data. LREC 2022, pp. 1317-1325.")

#: v4 §7.1 drift gate. Below this, the extract changed and a human must decide.
MIN_RECORDS = 2500

#: Kaikki POS strings mapped onto our controlled vocabulary. Anything unmapped is
#: PRESERVED VERBATIM rather than dropped — see S3-A-1 in DECISIONS.md.
POS_MAP: dict[str, str] = {
    "noun": "n", "verb": "v", "adj": "adj", "adjective": "adj",
    "adv": "adv", "adverb": "adv", "pron": "pron", "pronoun": "pron",
    "prep": "prep", "preposition": "prep", "conj": "conj",
    "conjunction": "conj", "interj": "interj", "interjection": "interj",
    "num": "num", "numeral": "num", "article": "art", "intj": "interj",
    "name": "name", "suffix": "sfx", "prefix": "pfx", "character": "char",
    "det": "det", "determiner": "det", "postp": "postp",
    "romanization": "roman", "phrase": "phr", "proverb": "prov",
    "contraction": "contr", "participle": "ptcp",
}


class KaikkiParseError(ValueError):
    """Malformed input. Raised, never warned — see module docstring."""


class SchemaDrift(KaikkiParseError):
    """Fewer records than the drift gate allows. A human must decide."""


def map_pos(raw: str | None) -> str:
    """Map a Kaikki POS onto our vocabulary, preserving anything unknown.

    Deliberately NOT filtered to the known set. A Coptic POS we have not seen
    (and there will be some: the extract is 3,293 entries of a language with a
    small scholarly literature) is still a fact about the word. Dropping it would
    make the entry look better-founded than it is. The schema's `pos` is an array
    of strings, so an unexpected value is representable.
    """
    if not raw:
        return ""
    key = raw.strip().lower()
    return POS_MAP.get(key, key)


def _as_list(value) -> list:
    """Coerce to a list, treating a STRING as absent rather than as a sequence.

    A string is iterable, so `for x in (value or [])` over a string yields its
    CHARACTERS. `glosses: "a bare string"` therefore produced nine one-character
    glosses instead of none — a silent wrong answer, from a field that was
    supposed to be empty. Every list-valued field in this parser goes through
    here so that shape drift degrades to "absent" instead of "nonsense".
    """
    if isinstance(value, (list, tuple)):
        return list(value)
    return []


def _clean_gloss(text: str) -> str:
    """Normalise a gloss without changing its wording.

    Whitespace collapse only. No lowercasing, no de-punctuation, no synonym
    merging: v4 §2.4 rule 7 forbids merging senses across sources by gloss text,
    and quietly rewriting a gloss here would make that rule unauditable.
    """
    return " ".join(text.split()).strip()


def _extract_glosses(sense: dict) -> list[str]:
    """All gloss strings for one sense, in order, deduped within the sense.

    Wiktextract emits `glosses` (the ordered chain, e.g. ["copper coin"]) and
    sometimes `raw_glosses` (the original untemplated string). We use `glosses`
    and take EVERY element, not just the first: in a chain like
    ["of copper", "of a metal"], element 2 is a real sense detail that the first
    element alone would lose.
    """
    out: list[str] = []
    seen: set[str] = set()
    for g in _as_list(sense.get("glosses")):
        if not isinstance(g, str):
            continue
        cleaned = _clean_gloss(g)
        if cleaned and cleaned.lower() not in seen:
            seen.add(cleaned.lower())
            out.append(cleaned)
    return out


def _extract_examples(sense: dict, word: str) -> list[dict]:
    """Examples, if the extract carries any. Rarely (a few dozen senses).

    Wiktextract example elements are DICTS, not strings. Keys seen in the real
    extract, none of them guaranteed: `text` (the Coptic), `english` or
    `translation` (either may carry the English), `ref`, `type`, `roman`, and
    bold-text offset arrays used for word alignment.

    An earlier draft filtered on `isinstance(ex, str)` and therefore extracted
    ZERO examples from 62 MB of real data — silently, because an empty list is a
    perfectly valid shape. See `test_examples_are_dicts_not_strings`, which pins
    the real element type so this cannot recur.
    """
    out = []
    for ex in _as_list(sense.get("examples")):
        if not isinstance(ex, dict):
            continue
        coptic = _clean_gloss(ex.get("text") or "")
        english = _clean_gloss(ex.get("english") or ex.get("translation") or "")
        # If `text` is not Coptic it is probably the English and `english` holds
        # nothing; file it on the side it actually belongs to.
        if coptic and not _looks_coptic(coptic) and not english:
            coptic, english = "", coptic
        if not (coptic or english):
            continue
        item = {
            "coptic": coptic,
            "translation": english,
            "quality": "automatic",
            "source": SOURCE_ID,
        }
        if ex.get("ref"):
            item["work"] = str(ex["ref"])
        if ex.get("type"):
            item["example_type"] = str(ex["type"])
        out.append(item)
    return out


def _extract_forms(rec: dict) -> list[dict]:
    """Inflected and romanised forms. Elements are DICTS with a `form` key.

    `tags` distinguishes the two kinds, and conflating them would be wrong in a
    way a reader would notice: `tags: ["romanization"]` means the string is a
    romanisation of the headword (not an inflection), and `tags: ["plural"]`
    means it is an inflection. Both are kept, and the tag is preserved so the
    merge and the UI can tell them apart.

    An earlier draft filtered on `isinstance(f, str)` and extracted ZERO forms
    from 39,000+ real form objects. Pinned by `test_forms_are_dicts_not_strings`.
    """
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    head_pos = map_pos(rec.get("pos")) or None
    for f in _as_list(rec.get("forms")):
        if isinstance(f, str):
            text, tags = f.strip(), []
        elif isinstance(f, dict):
            text = _clean_gloss(f.get("form") or "")
            tags = [t for t in _as_list(f.get("tags")) if isinstance(t, str)]
        else:
            continue
        if not text:
            continue
        key = (text, ",".join(sorted(tags)))
        if key in seen:
            continue
        seen.add(key)
        item = {"form": text, "pos": head_pos, "tags": sorted(tags)}
        if "romanization" in tags:
            item["kind"] = "romanization"
        elif tags:
            item["kind"] = "inflection"
        else:
            item["kind"] = "form"
        if isinstance(f, dict) and f.get("roman"):
            item["roman"] = _clean_gloss(f["roman"])
        out.append(item)
    return out


def _looks_coptic(s: str) -> bool:
    """True if the string contains a Coptic or Sahidic Coptic codepoint.

    Used only to decide which side of an example to file it on. Not a language
    detector and not load-bearing: if it guesses wrong the example is filed on
    the wrong side, which is visible, rather than dropped.
    """
    return any(0x2C80 <= ord(c) <= 0x2DFF or 0x03E2 <= ord(c) <= 0x03EF
               for c in s)


def parse_record(raw: str | dict, *, line_no: int | None = None) -> dict | None:
    """One JSONL line -> our record shape, or None if the record is unusable.

    Returns None (rather than raising) for a record with no word or no sense at
    all: an entry with neither a headword nor a meaning is not a dictionary
    entry, and dropping it silently would make the record count look smaller than
    the file. `iter_records` counts those separately so the arithmetic is
    auditable.

    Raises KaikkiParseError only for input that is not JSON at all — a genuinely
    malformed line, which is a different thing from a thin record.
    """
    where = f" (line {line_no})" if line_no else ""
    if isinstance(raw, str):
        try:
            rec = json.loads(raw)
        except json.JSONDecodeError as e:
            raise KaikkiParseError(f"malformed JSON{where}: {e}") from e
    else:
        rec = raw

    if not isinstance(rec, dict):
        raise KaikkiParseError(f"record is {type(rec).__name__}, not an object{where}")

    word = (rec.get("word") or "").strip()
    if not word:
        return None

    senses_in = _as_list(rec.get("senses"))
    senses = [s for s in senses_in if isinstance(s, dict)]

    # A record with senses but zero gloss text anywhere is a real schema-drift
    # signal (the field was renamed or emptied), not a thin entry. Keep it, with
    # an explicit marker, so the count of glossless records is visible downstream.
    glosses: list[dict] = []
    examples: list[dict] = []
    for sense in senses:
        texts = _extract_glosses(sense)
        # POS for a gloss: NOT sense["tags"][0]. Wiktextract's `tags` are
        # grammatical tags ("neuter", "plural", "masculine") — using the first as
        # a POS produced POS="neuter", which is nonsense. This extract carries no
        # per-sense POS, so the field is left null rather than invented; the
        # headword POS (rec["pos"]) is carried on the entry instead.
        sense_pos = map_pos(sense.get("pos")) or None
        for rank, text in enumerate(texts, start=1):
            glosses.append({
                "text": text,
                "pos": sense_pos,
                "lang": "en",
                "source": SOURCE_ID,
                "rank": rank,
            })
        examples.extend(_extract_examples(sense, word))

    if not word:
        return None

    etym_text = _clean_gloss(rec.get("etymology_text") or "")
    etym_templates = [t for t in _as_list(rec.get("etymology_templates"))
                      if isinstance(t, str)]
    etymology = None
    if etym_text:
        etymology = {
            "text": etym_text,
            "source": SOURCE_ID,
            "chain": [],
            "templates": sorted(set(etym_templates)),
        }

    forms = _extract_forms(rec)

    senses_present = bool(senses)
    record_id = None
    if senses:
        first_id = senses[0].get("id")
        if isinstance(first_id, str) and first_id:
            record_id = first_id

    return {
        "lemma": word,
        "display": word,
        "pos": [p for p in [map_pos(rec.get("pos"))] if p],
        "dialects": [],            # Kaikki carries no dialect flag. See below.
        "glosses": glosses,
        "etymology": etymology,
        "forms": forms,
        "examples": examples,
        "senses": senses_present,
        "sources": [{
            "id": SOURCE_ID,
            "licence": SOURCE_LICENCE,
            "doi": SOURCE_DOI,
            "cite": SOURCE_CITE,
        }],
        "provenance": {
            "record_id": record_id,
            "lang_code": rec.get("lang_code"),
            "lang": rec.get("lang"),
            "etymology_number": rec.get("etymology_number"),
            "head_templates": [t for t in _as_list(rec.get("head_templates"))
                               if isinstance(t, str)],
        },
    }


def iter_records(path: pathlib.Path) -> Iterator[dict]:
    """Stream every usable record. One line in memory at a time.

    Deliberately a generator. A caller that wants the first 10 records reads 10
    lines, not 63 MB.
    """
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            rec = parse_record(line, line_no=line_no)
            if rec is not None:
                yield rec


def count_records(path: pathlib.Path) -> dict[str, int]:
    """Full-file census. Enforces the drift gate.

    Counts four things separately so the arithmetic is auditable rather than a
    single number nobody can interrogate:

      lines        non-empty lines in the file
      records      lines that parsed to a usable record
      no_word      lines dropped for having no headword
      schema_drift raised below MIN_RECORDS
    """
    lines = records = no_word = 0
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            lines += 1
            rec = parse_record(line, line_no=line_no)
            if rec is None:
                no_word += 1
            else:
                records += 1

    if records < MIN_RECORDS:
        raise SchemaDrift(
            f"{path.name}: {records} usable records, below the v4 §7.1 drift gate "
            f"of {MIN_RECORDS}. Upstream changed shape, or the extract is broken. "
            f"DO NOT silently update the pin in tools/sources.lock — read the "
            f"diff, confirm on kaikki.org, then update in a pull request with a "
            f"note in CHANGELOG.md."
        )
    return {"lines": lines, "records": records, "no_word": no_word}


def census(path: pathlib.Path) -> dict[str, int]:
    """Streaming census for the receipt. One pass, constant memory."""
    out = {
        "records": 0, "with_gloss": 0, "with_etymology": 0, "with_forms": 0,
        "with_examples": 0, "with_senses": 0, "no_gloss": 0, "no_etymology": 0,
        "no_forms": 0, "multi_gloss": 0,
    }
    for rec in iter_records(path):
        out["records"] += 1
        if rec["glosses"]:
            out["with_gloss"] += 1
            if len(rec["glosses"]) > 1:
                out["multi_gloss"] += 1
        else:
            out["no_gloss"] += 1
        if rec["etymology"]:
            out["with_etymology"] += 1
        else:
            out["no_etymology"] += 1
        if rec["forms"]:
            out["with_forms"] += 1
        else:
            out["no_forms"] += 1
        if rec["examples"]:
            out["with_examples"] += 1
        if rec["senses"]:
            out["with_senses"] += 1

    if out["records"] < MIN_RECORDS:
        raise SchemaDrift(
            f"{path.name}: {out['records']} records, below the v4 §7.1 drift gate "
            f"of {MIN_RECORDS}. Do not silently update the pin."
        )
    return out


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="stream-parse the Kaikki Coptic extract")
    ap.add_argument("--input", type=pathlib.Path, default=pathlib.Path(
        "sources/kaikki/kaikki.org-dictionary-Coptic.jsonl"))
    ap.add_argument("--census", action="store_true",
                    help="print the full census and exit")
    ap.add_argument("--limit", type=int, default=0,
                    help="print N parsed records as JSON and exit")
    args = ap.parse_args(argv)

    if not args.input.is_file():
        print(f"[kaikki] {args.input} not found. Run tools/fetch/fetch_all.py "
              f"first; the pin is in tools/sources.lock.", file=sys.stderr)
        return 1

    if args.census:
        counts = count_records(args.input)
        print(f"[kaikki] lines={counts['lines']} records={counts['records']} "
              f"dropped_no_word={counts['no_word']} "
              f"(drift gate: >={MIN_RECORDS})")
        c = census(args.input)
        print(f"[kaikki] with >=1 gloss   : {c['with_gloss']}")
        print(f"[kaikki] with >1  gloss   : {c['multi_gloss']}")
        print(f"[kaikki] with etymology  : {c['with_etymology']}")
        print(f"[kaikki] with forms      : {c['with_forms']}")
        print(f"[kaikki] with examples   : {c['with_examples']}")
        print(f"[kaikki] with senses[]   : {c['with_senses']}")
        print(f"[kaikki] NO gloss at all : {c['no_gloss']}")
        return 0

    shown = 0
    for rec in iter_records(args.input):
        print(json.dumps(rec, ensure_ascii=False, indent=2))
        shown += 1
        if args.limit and shown >= args.limit:
            break
    if not shown:
        print("[kaikki] no records", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
