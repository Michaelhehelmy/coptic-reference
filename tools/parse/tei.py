#!/usr/bin/env python3
"""tools/parse/tei.py — parser for CCL and CDO TEI XML (Session 3, D2).

Emits the SAME record shape as tools/parse/kaikki.py, so tools/merge/entries.py
can consume all three sources without special-casing.

VERIFIED AGAINST REAL DATA
    CCL v1.2-2020 — 12,342,431 bytes, sha256 ace84fce11b76386a6adb9888b2cb947
    056954fc9fe9c04aa0676b1f595fd43d, fetched from the KELLIA/dictionary mirror
    of the BBAW/DDGLC release. Parsed with lxml.iterparse, never loaded whole.

NOT VERIFIED AGAINST REAL DATA — and this matters
    CDO (Coptic Dictionary Online). CDO is NOT distributed as a TEI file. Its
    GitHub repo holds the CCL mirror plus tooling; the dictionary itself is
    served by an SPA at coptic-dictionary.org, and every /api/* path returns the
    HTML shell rather than data. There is no public JSON endpoint and no data
    repo. So the CDO dialect below is implemented from the structure CDO
    documents and is exercised against fixtures only.

    Anyone with CDO access should run `--dialect cdo` against a real export
    before trusting the CDO path. Until then the CDO dialect is a hypothesis,
    and the merge treats a CDO parse as optional rather than required. Logged as
    S3-A-2 / S3-B1 in DECISIONS.md.

WHY ONE PARSER FOR TWO DIALECTS
    CCL and CDO are both TEI, so the outer skeleton (entry -> form/orth ->
    gramGrp/pos -> sense -> cit/quote) is shared. They differ in where the
    dialect lives (`usg type="geo"` in CCL, `gramGrp/dial` in CDO), in how the
    lemma is marked (`form type="lemma"` vs `@type`), and in the sense id
    attribute. One parser with a dialect table beats two parsers that drift.

NAMESPACES
    CCL declares xmlns="http://www.tei-c.org/ns/1.0". We match on the LOCAL name
    so a file with no namespace, or a different TEI version URI, still parses —
    the alternative is a KeyError on files that are otherwise fine.

FAIL LOUDLY ON A MISSING REQUIRED ELEMENT (per D2). Specifically: an <entry>
    with no lemma is an error, not a skip. A lexicon entry without its headword
    is a broken file, and skipping it would make the entry count look smaller
    than the file for no visible reason.

LICENCE: project code, Apache-2.0. CCL content is CC BY-SA 4.0 (BBAW + DDGLC).
"""
from __future__ import annotations

import json
import pathlib
import sys
from typing import Iterator

from lxml import etree

CCL_ID = "CCL"
CCL_LICENCE = "CC-BY-SA-4.0"
CCL_DOI = "10.17169/refubium-27566"

# CDO IS DELIBERATELY NOT SUPPORTED. Session 4 correction Q3: do not invent CDO
# structure. Sessions 2-3 carried a `cdo` dialect built from guesswork; it is
# removed, because a parser for a format nobody has seen is a guess wearing a
# parser's clothes, and it would have shipped as though it were verified.
#
# There is no CDO TEI file, no CDO JSON, and coptic-dictionary.org serves an SPA
# at every /api/* path. CDO ships in v1 WITHOUT being ingested; /licences/ says
# so publicly and DECISIONS.md carries the open question about emailing the
# KELLIA maintainers. When a real export exists, add a dialect here against the
# real file — not against a recollection.
CDO_LICENCE = "CC-BY-SA-4.0"
CDO_DOI = "10.17169/refubium-2333"

TEI_NS = "http://www.tei-c.org/ns/1.0"

#: ONE dialect: CCL. See the CDO note above for why there is not a second.
DIALECTS: dict[str, dict] = {
    "ccl": {
        "id": CCL_ID,
        "licence": CCL_LICENCE,
        "doi": CCL_DOI,
        "originators": "BBAW; DDGLC (Freie Universität Berlin) — Burns, Feder, "
                       "John, Kupreyev + contributors",
        "dialect_from": "usg_geo",
    },
}

#: CCL <usg type="geo"> values -> our dialect flags.
#:
#: MEASURED against the real CCL v1.2-2020 (11,283 entries), the values actually
#: present are ELEVEN, plus "?" meaning undetermined:
#:
#:     S 9418   Sahidic          B 2221   Bohairic
#:      A  822   Assiutic         Ak   93   Akhmimic
#:      F  617   Fayumic          ?  112   undetermined -> N
#:      M  747   L 725   V 146   W 57   P 7    (CCL codes, expansions not established)
#:
#: Anything unmapped is PRESERVED VERBATIM: a wrong expansion is worse than an
#: unexpanded code, because it looks authoritative. "?" maps to N, the flag the
#: entry schema already defines as undetermined.
GEO_MAP: dict[str, str] = {
    "S": "S", "B": "B", "N": "N",
    "SAH": "S", "SAHIDIC": "S", "BOH": "B", "BOHAIRIC": "B", "NOH": "N",
    "A": "A", "AK": "Ak", "AKHMIMIC": "Ak", "F": "F", "FAYUMIC": "F",
}

#: Values that mean "we do not know", not "a dialect called ?".
UNKNOWN_GEO_VALUES: frozenset[str] = frozenset({"?", "-", "unknown"})


class TEIParseError(ValueError):
    """Malformed or unusable TEI. Raised, never warned."""


def _local(el) -> str:
    """Tag name without the namespace."""
    t = el.tag
    if not isinstance(t, str):
        return ""
    return t.rsplit("}", 1)[-1]


def _find(el, name: str) -> list:
    """Direct children with local-name `name`, namespace-agnostic."""
    return [c for c in el if _local(c) == name]


def _find_deep(el, name: str) -> list:
    """Descendants with local-name `name`, namespace-agnostic."""
    return [c for c in el.iter() if _local(c) == name]


def _first_text(el, name: str) -> str:
    for c in _find(el, name):
        return " ".join((c.text or "").split()).strip()
    return ""


def _attr(el, *names: str) -> str:
    for n in names:
        v = el.get(n)
        if v:
            return v.strip()
    return ""


def extract_tla_id(el, entry_id: str) -> str:
    """Preserve a TLA id where present (D2).

    CCL keys are the TLA lemma ids where the entry supplies one (on
    `<idno type="tla">` or a `ref` pointing at a TLA lemma), falling back to the
    entry's own `xml:id` (`C5047`). The fallback is the entry id, NOT empty:
    provenance needs a stable handle and `C5047` is one.
    """
    for idno in _find_deep(el, "idno"):
        typ = (_attr(idno, "type") or "").lower()
        text = " ".join((idno.text or "").split()).strip()
        if text and typ in ("tla", "tla-id", "lemma-id", ""):
            return text
    for ref in _find_deep(el, "ref"):
        target = _attr(ref, "target")
        if target and ("tla" in target.lower() or target.startswith("http")):
            return target.rsplit("/", 1)[-1]
    return entry_id


def parse_dialects(entry, style: dict) -> tuple[list[str], bool]:
    """Dialect flags per the dialect's convention, plus an unknown-dialect flag.

    Returns (flags, dialect_unknown). See GEO_MAP for why "?" is separated out.
    """
    out: list[str] = []
    unknown = False
    if style["dialect_from"] == "usg_geo":
        for usg in _find_deep(entry, "usg"):
            if (_attr(usg, "type") or "").lower() == "geo":
                v = " ".join((usg.text or "").split()).strip()
                if not v:
                    continue
                if v.upper() in UNKNOWN_GEO_VALUES or v == "?":
                    # "?" means "undetermined". The entry schema already has N for
                    # exactly that, so map it there rather than inventing a second
                    # way of saying the same thing.
                    unknown = True
                    if "N" not in out:
                        out.append("N")
                    continue
                mapped = GEO_MAP.get(v.upper(), v)
                if mapped not in out:
                    out.append(mapped)
    else:
        for grp in _find_deep(entry, "gramGrp"):
            for d in _find(grp, "dial"):
                v = " ".join((d.text or "").split()).strip()
                for piece in v.replace("/", " ").split():
                    if piece.upper() in UNKNOWN_GEO_VALUES or piece == "?":
                        unknown = True
                        if "N" not in out:
                            out.append("N")
                        continue
                    mapped = GEO_MAP.get(piece.upper(), piece)
                    if mapped not in out:
                        out.append(mapped)
    return out, unknown


def parse_pos(entry) -> list[str]:
    pos: list[str] = []
    for grp in _find_deep(entry, "gramGrp"):
        for p in _find(grp, "pos"):
            v = " ".join((p.text or "").split()).strip()
            if v and v not in pos:
                pos.append(v)
    if not pos:
        for p in _find_deep(entry, "pos"):
            v = " ".join((p.text or "").split()).strip()
            if v and v not in pos:
                pos.append(v)
    return pos


def parse_senses(entry) -> list[dict]:
    """Glosses, from <cit type="translation"><quote xml:lang="…">.

    Only the ENGLISH quote is taken. CCL ships de/fr quotes alongside it, and
    emitting all three would put three languages into a field the schema calls
    `lang: en` — and would show a German gloss to an English reader with no way
    to tell. The other languages are DROPPED, not mislabelled; see S3-A-3.
    """
    glosses: list[dict] = []
    # rank runs across the WHOLE entry, not per <sense>. An earlier version reset
    # it per sense, so a three-sense entry emitted rank 1, 1, 1 — and rank is the
    # field the merge sorts senses by (v4 §2.4 rule 2). Duplicate ranks make that
    # sort unstable.
    rank = 0
    for sense in _find_deep(entry, "sense"):
        for cit in _find_deep(sense, "cit"):
            ctype = (_attr(cit, "type") or "").lower()
            if ctype and ctype != "translation":
                continue
            for quote in _find_deep(cit, "quote"):
                lang = (_attr(quote, "lang", "{http://www.w3.org/XML/1998/namespace}lang")
                        or "en").lower()
                if lang != "en":
                    continue
                text = " ".join("".join(quote.itertext()).split()).strip()
                if not text:
                    continue
                rank += 1
                g = {"text": text, "pos": None, "lang": "en",
                     "source": None, "rank": rank}
                bibl = cit.find("bibl")
                if bibl is not None:
                    refs = " ".join("".join(bibl.itertext()).split()).strip()
                    if refs:
                        g["references"] = refs
                glosses.append(g)
    return glosses


def parse_forms(entry, lemma: str) -> list[dict]:
    """Non-lemma <form><orth> values become inflections.

    The lemma form itself is EXCLUDED: listing a headword as its own inflection
    makes the dictionary page show the same string twice and inflates the form
    count, which is a number the plan uses.
    """
    out: list[dict] = []
    seen: set[str] = set()
    for form in _find_deep(entry, "form"):
        if (_attr(form, "type") or "").lower() == "lemma":
            continue
        orth = _first_text(form, "orth")
        if not orth or orth == lemma or orth in seen:
            continue
        seen.add(orth)
        item = {"form": orth, "pos": None, "kind": "form"}
        cert = _first_text(form, "cert")
        if cert:
            item["note"] = cert
        out.append(item)
    return out


def parse_entry(el, style: dict) -> dict:
    """One <entry> -> our record shape. Raises on a missing lemma."""
    entry_id = _attr(el, "{http://www.w3.org/XML/1998/namespace}id", "id") or ""

    lemma = ""
    display = ""
    variant = False
    # The type is on the FORM, not the entry: C11273 is
    # <entry xml:id="C11273"> with <form type="inflected">. Recorded because it is
    # what distinguishes a variant entry from a headword entry.
    lemma_form_type = ""
    for form in _find(el, "form"):
        if (_attr(form, "type") or "").lower() == "lemma":
            lemma = _first_text(form, "orth")
            display = lemma
            lemma_form_type = _attr(form, "type")
            break
    if not lemma:
        # Fall back to the first <orth> ANYWHERE in the entry.
        #
        # Measured against the real CCL v1.2-2020: 11,283 entries, of which
        # exactly ONE (C11273, `type="inflected"`, orth "ⲃⲁⲅ-", gloss "going,
        # throwing") carries no <form type="lemma">. It is a legitimate
        # prefix/variant entry with real sense data, not a broken record — so it
        # is kept and flagged `variant`, rather than raising or being dropped.
        #
        # The first version of this fallback looked only at DIRECT children of
        # <entry>, and that entry's <orth> is nested inside <form>, so the
        # "fail loudly on a missing lemma" rule fired on 1 of 11,283 real
        # entries. Searching descendants fixes it; raising is now reserved for an
        # entry with no <orth> at all, which would be genuinely empty.
        for form in _find(el, "form"):
            candidate = _first_text(form, "orth")
            if candidate:
                lemma = candidate
                display = candidate
                lemma_form_type = _attr(form, "type")   # e.g. "inflected"
                variant = True
                break
        if not lemma:
            # Last resort: an <orth> that is not inside any <form>.
            for orth in _find_deep(el, "orth"):
                candidate = " ".join((orth.text or "").split()).strip()
                if candidate:
                    lemma = candidate
                    display = candidate
                    variant = True
                    break
    if not lemma:
        raise TEIParseError(
            f"<entry> {_attr(el, '{http://www.w3.org/XML/1998/namespace}id') or '(no xml:id)'}"
            f" has no lemma: no <form type=\"lemma\"><orth>, no descendant <orth>, "
            f"and no bare <orth>. A lexicon entry with no headword anywhere is a "
            f"broken file, not a record to skip — skipping it would make the "
            f"entry count quietly smaller."
        )

    dialects, dialect_unknown = parse_dialects(el, style)
    glosses = parse_senses(el)
    for g in glosses:
        g["source"] = style["id"]

    tla = extract_tla_id(el, entry_id or lemma)

    examples: list[dict] = []
    for ex in _find_deep(el, "exemplar"):
        quote = " ".join("".join(ex.itertext()).split()).strip()
        ref = ""
        for cite in _find(ex, "cit"):
            ref = _attr(cite, "ref") or _first_text(cite, "bibl")
            if ref:
                break
        if quote:
            examples.append({"coptic": "", "translation": quote,
                             "work": ref, "quality": "automatic",
                             "source": style["id"]})

    return {
        "lemma": lemma,
        "display": display or lemma,
        "pos": parse_pos(el),
        "dialects": dialects,
        "dialect_unknown": dialect_unknown,
        "glosses": glosses,
        "etymology": None,
        "forms": parse_forms(el, lemma),
        "examples": examples,
        "tla_id": tla,
        "variant": variant,
        "sources": [{
            "id": style["id"],
            "licence": style["licence"],
            "doi": style["doi"],
            "originators": style["originators"],
        }],
        "provenance": {
            "record_id": tla,
            "xml_id": entry_id,
            "entry_type": _attr(el, "type"),
            "lemma_form_type": lemma_form_type,
        },
    }


def iter_entries(path: pathlib.Path, dialect: str = "ccl") -> Iterator[dict]:
    """Stream <entry> elements. iterparse, so 12 MB never becomes a tree.

    `tag=("{*}entry", "entry")` covers namespaced and non-namespaced files. The
    element is cleared and its preceding siblings removed after each hit, which
    is the standard lxml idiom and is what keeps memory flat.
    """
    if dialect not in DIALECTS:
        raise TEIParseError(f"unknown dialect {dialect!r}; "
                            f"expected one of {sorted(DIALECTS)}")
    style = DIALECTS[dialect]
    context = etree.iterparse(str(path), events=("end",), tag=("{*}entry", "entry"))
    for _event, el in context:
        try:
            yield parse_entry(el, style)
        finally:
            el.clear()
            while el.getprevious() is not None:
                del el.getparent()[0]


def census(path: pathlib.Path, dialect: str = "ccl") -> dict[str, int]:
    out = {"entries": 0, "with_gloss": 0, "no_gloss": 0, "with_pos": 0,
           "with_dialect": 0, "with_forms": 0, "with_tla": 0, "multi_gloss": 0}
    for rec in iter_entries(path, dialect):
        out["entries"] += 1
        if rec["glosses"]:
            out["with_gloss"] += 1
            if len(rec["glosses"]) > 1:
                out["multi_gloss"] += 1
        else:
            out["no_gloss"] += 1
        if rec["pos"]:
            out["with_pos"] += 1
        if rec["dialects"]:
            out["with_dialect"] += 1
        if rec["forms"]:
            out["with_forms"] += 1
        if rec["tla_id"]:
            out["with_tla"] += 1
    return out


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="parse CCL / CDO TEI XML")
    ap.add_argument("--input", type=pathlib.Path, default=pathlib.Path(
        "sources/ccl/Comprehensive_Coptic_Lexicon-v1.2-2020.xml"))
    ap.add_argument("--dialect", default="ccl", choices=sorted(DIALECTS))
    ap.add_argument("--census", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args(argv)

    if not args.input.is_file():
        print(f"[tei] {args.input} not found. Run tools/fetch/fetch_all.py.",
              file=sys.stderr)
        return 1

    if args.census:
        c = census(args.input, args.dialect)
        for k, v in c.items():
            print(f"[tei] {k:16} {v}")
        return 0

    shown = 0
    for rec in iter_entries(args.input, args.dialect):
        print(json.dumps(rec, ensure_ascii=False, indent=2))
        shown += 1
        if args.limit and shown >= args.limit:
            break
    if not shown:
        print("[tei] no entries", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
