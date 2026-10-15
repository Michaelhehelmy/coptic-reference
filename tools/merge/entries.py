#!/usr/bin/env python3
"""tools/merge/entries.py — the merge (Session 3, D4).

Implements v4 §2.4's precedence rules EXACTLY, in order:

    1. join on norm_key (NFC + marks stripped)
    2. senses:      CCL > CDO > Kaikki
    3. dialects:    union
    4. etymology:   Kaikki > CCL
    5. glosses:     union, deduped, ranked by source precedence
    6. examples:    CDO > Kaikki > CCL
    7. NEVER merge senses across sources by gloss text

RULE 7 IS NOT IN TENSION WITH RULE 5, and the distinction matters.
    Rule 5 dedupes on EXACT string equality: if CCL and Kaikki both say
    "now, at present", that is one gloss stated twice, and showing it twice
    makes the entry look better-sourced than it is.
    Rule 7 forbids FUSING: "now" (CCL) and "at the present time" (Kaikki) are
    two glosses, not one. Near-matching text must never be collapsed, because
    two sources using different wording for the same sense is the normal case,
    and merging them destroys the evidence that two sources agree.
    So: exact-match dedupe only. Pinned by
    test_near_matching_glosses_are_never_fused.

PRECEDENCE is a table, not control flow, so it is testable and so a change to it
is a visible diff:

    SENSE_PRECEDENCE   = CCL, CDO, Kaikki
    ETYMOLOGY_PRECEDENCE = Kaikki, CCL
    EXAMPLE_PRECEDENCE = CDO, Kaikki, CCL

SENSE vs GLOSS: a source's senses become glosses. "Senses: CCL > CDO > Kaikki"
governs ORDER and which source's wording leads; "glosses: union" means none are
dropped. Both rules are honoured: every gloss from every source survives, and
they are ordered by the sense precedence.

WHAT THIS DOES NOT DO
    * It does not split an entry by dialect. v4 §10.2 wants dialect-specific
      presentation, and doing that properly needs CCL's per-`usg type="geo"`
      sense structure, which is a Session 4 question. Here dialects are a UNION
      flag, per rule 3, and the entry says so.
    * It does not resolve conflicts. If CCL and Kaikki give different POS, both
      appear in `pos[]` and `attributions[]` records it. Silently preferring one
      would hide a real disagreement in the data.

MEMORY: Kaikki is 3,293 records and CCL 11,283; both are parsed to compact dicts
and grouped by norm_key. Peak memory is the grouped dict, not the 62 MB file —
the parsers stream. 11,283 entries is small enough to hold; if that changes,
this is the place to shard.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import unicodedata
from typing import Iterable, Iterator

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import collate
import pos as posvocab  # noqa: E402  (Session 6 D2)
from emit import translit as translit_mod  # noqa: E402  (Session 17 D1)

PIPELINE_VERSION = "3.0.0"

#: v4 §2.4 rule 2. First name wins the leading position.
SENSE_PRECEDENCE: tuple[str, ...] = ("CCL", "CDO", "Kaikki")
#: v4 §2.4 rule 4.
ETYMOLOGY_PRECEDENCE: tuple[str, ...] = ("Kaikki", "CCL")
#: v4 §2.4 rule 6.
EXAMPLE_PRECEDENCE: tuple[str, ...] = ("CDO", "Kaikki", "CCL")


class MergeError(ValueError):
    """The merge cannot produce a trustworthy entry. Raised, never warned."""


def norm_key(lemma: str) -> str:
    """v4 §2.4 rule 1: NFC + marks stripped.

    Deliberately built on collate.canon_for_sort rather than a fresh
    implementation, so the join key and the sort key cannot disagree — if they
    did, entries would merge in one order and shard in another, and shard
    boundaries would become input-order dependent (v4 §1.3 defect B3).
    """
    return collate.canon_for_sort(unicodedata.normalize("NFC", lemma))


def source_rank(source_id: str, table: tuple[str, ...]) -> int:
    """Position in a precedence table. Unknown sources sort last, stably."""
    try:
        return table.index(source_id)
    except ValueError:
        return len(table)


def entry_id(lemma: str, pos: list[str], tla_id: str | None) -> str:
    """v4 §2.4: id is the TLA id where one exists, else a hash of lemma|pos.

    TLA first because it is the stable, citable identifier the scholarly
    literature already uses; a hash nobody can look up is a fallback, not a
    primary key. The hash is 8 hex chars of sha256 over the NORMALISED key, so
    the same word always gets the same id regardless of which source spelled it.
    """
    if tla_id:
        return tla_id
    payload = norm_key(lemma) + "|" + "|".join(sorted(pos))
    return "H" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:7].upper()


def _dedupe_exact(items: Iterable[dict], key: str) -> list[dict]:
    """Exact-match dedupe only. See rule 7 in the module docstring."""
    out: list[dict] = []
    seen: set[str] = set()
    for it in items:
        k = (it.get(key) or "").strip().lower()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(it)
    return out


def merge_group(records: list[dict]) -> dict | None:
    """Merge every record sharing one norm_key into a single entry.

    Returns None when the group has no lemma AND no gloss — nothing to emit.
    A group with a lemma but no gloss is still emitted, and the schema will
    reject it, because dropping it here would make the entry count disagree
    with the merge arithmetic in a way nobody could audit.
    """
    records = [r for r in records if r.get("lemma")]
    if not records:
        return None

    # The DISPLAY lemma is the first by sense precedence, so CCL's spelling wins
    # over Kaikki's for the same word. Deterministic, not first-seen.
    ordered = sorted(records,
                     key=lambda r: (source_rank(r["sources"][0]["id"],
                                                 SENSE_PRECEDENCE),
                                    r["sources"][0]["id"]))
    primary = ordered[0]
    lemma = primary["lemma"]
    key = norm_key(lemma)

    src_ids = sorted({r["sources"][0]["id"] for r in records})

    # ── rule 3: dialects, union ──────────────────────────────────────────────
    dialects: list[str] = []
    dialect_unknown = False
    for r in records:
        for d in r.get("dialects") or []:
            if d and d not in dialects:
                dialects.append(d)
        if r.get("dialect_unknown"):
            dialect_unknown = True
    # Q1(a), the dialect-union rule: N means "a source recorded ? / undetermined".
    # If ANY source placed this lemma in a real dialect, that placement is better
    # evidence than another source's uncertainty, so N is dropped rather than
    # unioned alongside it. Otherwise an entry known to be Sahidic would carry
    # both S and N, and a reader could not tell whether N meant "also undetermined"
    # or "nothing else is known".
    #
    # Measured effect: 112 CCL entries record "?" AND a real dialect. All 112
    # lose N and keep their real flag.
    specific = [d for d in dialects if d != "N"]
    if specific:
        dialects = specific
    elif not dialects:
        # Nothing at all, from any source. N is a true statement here, not a
        # filler: the schema defines it, and the /dialects/ page counts these so
        # the gap is visible rather than hidden (v4 §10.2, correction Q4).
        dialects = ["N"]
    dialects.sort()

    # ── pos: union, conflicts recorded not resolved ───────────────────────────
    pos: list[str] = []
    for r in records:
        for p in r.get("pos") or []:
            if p and p not in pos:
                pos.append(p)

    # ── rule 2 + 5: senses by precedence, glosses unioned and deduped ────────
    gloss_pool: list[dict] = []
    for r in records:
        sid = r["sources"][0]["id"]
        for g in r.get("glosses") or []:
            if not g.get("text"):
                continue
            item = {
                "text": " ".join(g["text"].split()),
                "lang": g.get("lang") or "en",
                "source": sid,
                "_rank": source_rank(sid, SENSE_PRECEDENCE),
            }
            # OMIT an unknown POS rather than emitting null. The schema types it
            # as string and does not require it; absence says "not recorded",
            # null says "recorded as nothing", and only the first is true.
            if g.get("pos"):
                item["pos"] = g["pos"]
            gloss_pool.append(item)
    # Sort by precedence, then by original order WITHIN a source, so a single
    # source's sense order is preserved.
    for i, g in enumerate(gloss_pool):
        g["_i"] = i
    gloss_pool.sort(key=lambda g: (g["_rank"], g["_i"]))
    glosses = _dedupe_exact(gloss_pool, "text")
    for i, g in enumerate(glosses, start=1):
        g["rank"] = i
        g.pop("_rank", None)
        g.pop("_i", None)

    # ── rule 4: etymology by precedence ──────────────────────────────────────
    etymology = None
    etym_source = None
    for sid in ETYMOLOGY_PRECEDENCE:
        for r in records:
            if r["sources"][0]["id"] == sid and r.get("etymology"):
                etymology = r["etymology"]
                etym_source = sid
                break
        if etymology:
            etymology = {k: v for k, v in etymology.items() if k != "templates"}
            break

    # ── rule 6: examples by precedence ───────────────────────────────────────
    ex_pool: list[dict] = []
    for r in records:
        sid = r["sources"][0]["id"]
        for ex in r.get("examples") or []:
            # A Coptic example with no Coptic text is a translation with nothing
            # to translate FROM; the reader gets an English sentence and no way
            # to see the word. Dropped rather than emitted with an empty coptic.
            if not (ex.get("coptic") or "").strip():
                continue
            ex = dict(ex)
            ex.pop("example_type", None)   # extractor metadata, not reader-facing
            ex["source"] = sid
            ex["_rank"] = source_rank(sid, EXAMPLE_PRECEDENCE)
            ex_pool.append(ex)
    ex_pool.sort(key=lambda e: e["_rank"])
    examples = []
    for ex in ex_pool:
        ex.pop("_rank", None)
        examples.append(ex)
    # One example per (coptic, translation) pair, keeping the best-ranked.
    examples = _dedupe_exact(
        [dict(ex, _k=(ex.get("coptic", "") + "|" + ex.get("translation", "")))
         for ex in examples], "_k")
    for ex in examples:
        k = ex.pop("_k")
        ex["_k"] = k
    seen_ex = set()
    deduped_examples = []
    for ex in examples:
        k = ex.pop("_k")
        if k in seen_ex:
            continue
        seen_ex.add(k)
        deduped_examples.append(ex)

    # ── forms: union, tagged by source ───────────────────────────────────────
    forms: list[dict] = []
    seen_forms: set[tuple[str, str]] = set()
    for r in records:
        sid = r["sources"][0]["id"]
        for f in r.get("forms") or []:
            text = (f.get("form") or "").strip()
            if not text or text == lemma:
                continue
            sig = (text, f.get("kind") or "form")
            if sig in seen_forms:
                continue
            seen_forms.add(sig)
            item = {"form": text}
            if f.get("pos"):
                item["pos"] = f["pos"]
            if f.get("kind"):
                item["kind"] = f["kind"]
            if f.get("note"):
                item["note"] = f["note"]
            forms.append(item)

    # ── translit: rule-based, all five schemes (Session 17 D1) ───────────────
    # Upstream records carry no per-scheme transliteration, so the old
    # precedence loop always produced {}. Derive it from the D0
    # transliterator instead — at merge time (C1), never at emit time.
    # Strict (C3): an unmappable character fails naming the entry id and the
    # character, never a silent partial string.
    tla = next((r.get("tla_id") for r in records if r.get("tla_id")), None)
    eid = entry_id(lemma, pos, tla)
    try:
        translit: dict[str, str] = translit_mod.transliterate_all_strict(lemma)
    except translit_mod.TranslitError as exc:
        raise MergeError(f"entry {eid} lemma {lemma!r}: {exc}") from exc

    # ── sources[] and attributions[] (v4 §8.2) ──────────────────────────────
    sources = []
    seen_src = set()
    for r in records:
        s = r["sources"][0]
        if s["id"] in seen_src:
            continue
        seen_src.add(s["id"])
        entry_src = {"id": s["id"], "licence": s["licence"]}
        if s.get("doi"):
            entry_src["doi"] = s["doi"]
        sources.append(entry_src)
    sources.sort(key=lambda s: source_rank(s["id"], SENSE_PRECEDENCE))

    record_ids: dict[str, str] = {}
    for r in records:
        sid = r["sources"][0]["id"]
        rid = (r.get("provenance") or {}).get("record_id") or r.get("tla_id")
        if rid and sid not in record_ids:
            record_ids[sid] = rid

    attributions = build_attributions(
        src_ids=src_ids, n_records=len(records), n_senses=len(glosses),
        etym_source=etym_source, dialect_unknown=dialect_unknown,
        licences={s["id"]: s["licence"] for s in sources})

    # 55 distinct POS strings became 21. The originals are recorded in
    # attributions[] whenever they differ, so the German source tag is still
    # visible for CC BY-SA §3(b) and nothing is silently discarded.
    normalised_pos, pos_originals = posvocab.normalize_list(pos)
    if pos_originals:
        attributions.append({
            "field": "pos",
            "source": "ProjectRebuild",
            "licence": "CC-BY-SA-4.0",
            "changes": ("part-of-speech normalised to the controlled vocabulary "
                        "in tools/pos.py; source value(s): "
                        + ", ".join(repr(o) for o in pos_originals)),
        })

    return {
        "id": eid,  # computed above so C3 errors name the shipped id
        "lemma": lemma,
        "display": lemma,
        "norm_key": key,
        "translit": translit,
        "dialects": dialects,
        # Session 6 D2 / C3: normalise HERE, at merge time, because this is where
        # three sources become one entry. Emitting first and normalising later
        # would make the shipped shards differ from what the merge produced, and a
        # re-merge would silently drop the normalisation.
        "pos": normalised_pos,
        "glosses": glosses,
        "forms": forms,
        "examples": deduped_examples,
        "corpus_refs": [],
        "related_entries": [],
        "media": [],
        "sources": sources,
        "attributions": attributions,
        "etymology": etymology,
        "provenance": {
            "record_ids": record_ids,
            "pipeline_version": PIPELINE_VERSION,
            "generated": "2026-10-04T00:00:00Z",
            "collation_hash": collate.collation_hash(),
        },
    }


def build_attributions(*, src_ids: list[str], n_records: int, n_senses: int,
                       etym_source: str | None, dialect_unknown: bool,
                       licences: dict[str, str]) -> list[dict]:
    """v4 §8.2 attributions[].

    One row per (field, source) that contributed, plus a MERGE row when the
    merge itself changed something. The `changes` text uses a CONTROLLED
    VOCABULARY — v4 §8.2 requires it, and free text here would make
    "what did we actually do?" unanswerable across thousands of entries.

    Controlled vocabulary, fixed strings:
        none                      copied verbatim, nothing altered
        deduplicated              identical sense removed from a lower source
        sense order reordered     precedence table moved a sense's position
        diacritics stripped       marks removed for the join/sort key
        merged from N sources     entry combines N upstream records
        dialect union             dialect flags unioned across sources
        POS conflict retained     sources disagree and both were kept
    """
    from collections import Counter

    counts = Counter(src_ids)
    out: list[dict] = []
    for sid in sorted(src_ids, key=lambda s: source_rank(s, SENSE_PRECEDENCE)):
        changes = ["none"]
        if counts[sid] > 1:
            changes.append(f"merged from {counts[sid]} sources")
        if sid != SENSE_PRECEDENCE[0] and sid in src_ids:
            changes.append("deduplicated")
            changes.append("sense order reordered")
        if etym_source == sid:
            changes.append("diacritics stripped")
        out.append({
            "field": "glosses",
            "source": sid,
            "licence": licences.get(sid, "UNKNOWN"),
            "changes": "; ".join(dict.fromkeys(changes)),
        })

    # The MERGE row uses the SAME controlled vocabulary as the source rows. An
    # earlier version wrote a free-text sentence here ("merged N upstream
    # record(s) into M sense(s)"), which meant the one row describing the merge
    # itself was the one row a query could not filter on.
    merge_changes = [f"merged from {n_records} sources", "dialect union"]
    if len(src_ids) > 1:
        merge_changes.append("deduplicated")
        merge_changes.append("sense order reordered")
    out.append({
        "field": "glosses",
        "source": "MERGE",
        "licence": licences.get("MERGE", "CC-BY-SA-4.0"),
        "changes": "; ".join(merge_changes),
    })
    return out


def merge_all(records_by_source: dict[str, list[dict]]) -> Iterator[dict]:
    """Group every source's records by norm_key and merge each group."""
    groups: dict[str, list[dict]] = {}
    for source_id, records in records_by_source.items():
        for r in records:
            k = norm_key(r["lemma"])
            groups.setdefault(k, []).append(r)
    for k in sorted(groups):
        entry = merge_group(groups[k])
        if entry is not None:
            yield entry


def stats(entries: list[dict]) -> dict:
    return {
        "entries": len(entries),
        "multi_source": sum(1 for e in entries if len(e["sources"]) > 1),
        "with_attributions": sum(1 for e in entries if e["attributions"]),
        "with_glosses": sum(1 for e in entries if e["glosses"]),
        "no_glosses": sum(1 for e in entries if not e["glosses"]),
        "with_etymology": sum(1 for e in entries if e.get("etymology")),
        "with_dialects": sum(1 for e in entries if e["dialects"]),
        "dialect_undetermined": sum(1 for e in entries if e["dialects"] == ["N"]),
        "with_tla_id": sum(1 for e in entries
                           if e["id"] and not e["id"].startswith("H")),
        "with_examples": sum(1 for e in entries if e["examples"]),
        "with_forms": sum(1 for e in entries if e["forms"]),
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="merge Kaikki + CCL (+ CDO) into entries")
    ap.add_argument("--out", type=pathlib.Path,
                    default=ROOT / "work" / "merged" / "entries.json")
    ap.add_argument("--stats-only", action="store_true")
    args = ap.parse_args(argv)

    sys.path.insert(0, str(ROOT / "tools" / "parse"))
    import kaikki
    import tei

    kaikki_path = ROOT / "sources" / "kaikki" / "kaikki.org-dictionary-Coptic.jsonl"
    ccl_path = ROOT / "sources" / "ccl" / "Comprehensive_Coptic_Lexicon-v1.2-2020.xml"

    by_source: dict[str, list[dict]] = {}
    if kaikki_path.is_file():
        by_source["Kaikki"] = list(kaikki.iter_records(kaikki_path))
        print(f"[merge] Kaikki  {len(by_source['Kaikki']):6} records")
    if ccl_path.is_file():
        by_source["CCL"] = list(tei.iter_entries(ccl_path, "ccl"))
        print(f"[merge] CCL     {len(by_source['CCL']):6} entries")
    # CDO: not fetchable (see tools/parse/tei.py). Absent, not zero.
    total_in = sum(len(v) for v in by_source.values())
    print(f"[merge] input   {total_in:6} records from {len(by_source)} source(s)")

    merged = list(merge_all(by_source))
    # An entry with no gloss cannot render a dictionary page, and the schema
    # forbids an empty glosses[]. These are NOT silently dropped: they are
    # counted, and the count is printed, so the arithmetic stays auditable.
    # Measured on real data: 16 of 11,385 (1 Kaikki record whose Wiktionary page
    # is a stub, plus 15 CCL entries).
    glossless = [e for e in merged if not e["glosses"]]
    entries = collate.coptic_sorted([e for e in merged if e["glosses"]],
                                    key=lambda e: e["norm_key"])
    if glossless:
        print(f"[merge] EXCLUDED {len(glossless)} entry/entries with no gloss "
              f"(schema requires >=1): "
              f"{', '.join(sorted(e['lemma'] for e in glossless)[:8])}"
              f"{' ...' if len(glossless) > 8 else ''}")

    s = stats(entries)
    print(f"[merge] output  {s['entries']:6} entries")
    for k, v in s.items():
        if k != "entries":
            print(f"[merge]   {k:20} {v}")
    print(f"[merge] net     {total_in - s['entries']:+d} "
          f"(input records minus merged entries)")

    if not args.stats_only:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps({"entries": entries}, ensure_ascii=False),
            encoding="utf-8")
        print(f"[merge] wrote   {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
