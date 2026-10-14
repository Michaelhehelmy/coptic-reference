#!/usr/bin/env python3
"""tools/parse/conllu.py — CoNLL-U parser for the UD Coptic treebanks (D3).

Emits sentence-level records with tokens and dependency heads, from the real
`cop_scriptorium-ud-{dev,test,train}.conllu`.

MEASURED AGAINST REAL DATA
    UD_Coptic-Scriptorium  master, 2,252 sentences total
    dev 380 · test 405 · train 1467 · 5,818,154 bytes · sha256 (concatenated)
    059c9e2762d08f7058792ddad1798ae8dbc49a76b90c7d727f2570dbcecff4f6

TWO FACTS THAT CONTRADICT THE BRIEF, reported rather than papered over
----------------------------------------------------------------------
1. **There is no Bohairic treebank to parse.**
   `UniversalDependencies/UD_Bohairic-Coptic` returns HTTP 404. The UD
   organisation publishes UD_Coptic-Scriptorium (Sahidic) and nothing else for
   Coptic. tools/sources.lock lists UD_Bohairic with the Zeldes/Speransky/
   Wagner/Schroeder 2025 citation and `wordforms = 30000`, but that treebank is
   NOT published under that name. v4 §10.2's Bohairic-parsing-is-weaker claim
   cannot be quantified from UD data until someone locates that release. The
   parser handles both dialects identically because the format is identical; it
   simply has one treebank to read.

2. **The CoNLL-U header carries NO dialect field.**
   D3 asks to "preserve dialect (Sahidic / Bohairic) from the file header". The
   real header contains `newdoc id`, `global.Entity`, `meta::author`,
   `meta::document_cts_urn`, `meta::source`, `meta::title`, `sent_id`,
   `text_en`, `text` — and no language or dialect marker anywhere. The treebank's
   README states Sahidic; tools/sources.lock declares `dialect = "Sahidic"`.

   `parse_dialect` therefore reads a header field IF one exists, else uses the
   caller-supplied declared dialect, else returns "unknown". It NEVER infers a
   dialect from the text. Inferring one would be a guess presented as a
   metadata field, which is the exact failure v4 §10.2 warns about.

MWT (multi-word tokens)
-----------------------
The real data uses CoNLL-U ranges: a `3-5` line whose FORM is the whole surface
token and whose other columns are `_`, followed by the `3`, `4`, `5` sub-tokens.
An earlier draft ignored ranges and emitted the `_` placeholder as a real token,
which silently corrupts every sentence containing a prefix or suffix. Ranges are
expanded here: the surface token is attached to the sub-token list, and the
placeholder is NOT emitted as a token.

`Orig=` preservation
--------------------
The MISC column carries `Orig=ⲣ̄ⲙⲏ̂` — the original orthography with diacritics,
which the UD FORM column has stripped. That is the same relationship as `_TT`'s
`@orig`/`@norm` (PLAN-ERRATA B-4): the marked form is authoritative for display
and the stripped form is for search. Preserved as `orig`.

LICENCE: project code, Apache-2.0. Treebank data CC BY 4.0 — read from the
treebank's own LICENSE.txt, which says "Creative Commons Attribution 4.0
international". Session 1 recorded CC-BY-SA-4.0 without having fetched the
treebank; corrected Session 3. See DECISIONS.md S3-B3.
"""
from __future__ import annotations

import json
import pathlib
import sys
from typing import Iterator

UD_SAHIDIC_ID = "UD_Coptic"
UD_SAHIDIC_LICENCE = "CC-BY-4.0"
UD_SAHIDIC_DOI = ""

#: CoNLL-U columns, by index.
COL_ID, COL_FORM, COL_LEMMA, COL_UPOS, COL_XPOS = 0, 1, 2, 3, 4
COL_FEATS, COL_HEAD, COL_DEPRELS, COL_DEPS, COL_MISC = 5, 6, 7, 8, 9
N_COLS = 10

UNDERSCORE = "_"


class CoNLLUError(ValueError):
    """Malformed CoNLL-U. Raised, never warned."""


def _split_meta(line: str) -> tuple[str, str]:
    """`# key = value` -> (key, value). Keys are matched case-sensitively as
    written because the treebank uses `meta::` prefixes that are load-bearing."""
    body = line.lstrip("#").strip()
    if "=" not in body:
        return body.strip(), ""
    key, _, value = body.partition("=")
    return key.strip(), value.strip()


def parse_dialect(header: dict[str, str], declared: str | None = None) -> str:
    """Dialect for the whole file.

    Order: an explicit header field, then the caller's declared value, then
    "unknown". Never inferred from text. See the module docstring.
    """
    for key in ("dialect", "meta::dialect", "language", "meta::language",
                "lang", "meta::lang"):
        if key in header:
            v = header[key].strip()
            if v:
                return v
    if declared:
        return declared
    return "unknown"


def _parse_id(raw: str, line_no: int) -> tuple[int, int, int]:
    """`7` -> (7,7,7); `3-5` -> (3,3,5)."""
    raw = raw.strip()
    if "-" in raw:
        lo, _, hi = raw.partition("-")
        try:
            return int(lo), int(lo), int(hi)
        except ValueError as e:
            raise CoNLLUError(
                f"line {line_no}: malformed token id range {raw!r}") from e
    try:
        n = int(raw)
    except ValueError as e:
        raise CoNLLUError(
            f"line {line_no}: token id {raw!r} is not an integer or a range"
        ) from e
    return n, n, n


def _feats(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in (raw or "").split("|"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, _, v = part.partition("=")
        out[k.strip()] = v.strip()
    return out


def _misc(raw: str) -> dict[str, str]:
    """MISC pairs. Coptic's `Orig=` and `MSeg=` live here.

    Values may contain `=` (Entity=(object|subject)), so partition once.
    """
    out: dict[str, str] = {}
    for part in (raw or "").split("|"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, _, v = part.partition("=")
        out[k.strip()] = v.strip()
    return out


def parse_sentence(block: list[str], header: dict[str, str], *,
                   dialect: str, source: str, line_no: int) -> dict:
    """One blank-line-delimited block -> a sentence record."""
    tokens: list[dict] = []
    mwt_stack: dict[int, dict] = {}     # mwt start id -> {form, lo, hi}
    mwt_of: dict[int, int] = {}          # token id -> mwt start id

    for line in block:
        if not line or line.startswith("#"):
            continue
        cols = line.split("\t")
        if len(cols) < N_COLS:
            # CoNLL-U allows trailing empty columns to be omitted; pad rather
            # than fail, but only up to N_COLS.
            if len(cols) < 7:
                raise CoNLLUError(
                    f"line {line_no}: token line has {len(cols)} column(s), "
                    f"minimum 7 (ID FORM LEMMA UPOS XPOS FEATS HEAD). HEAD is "
                    f"mandatory in CoNLL-U: padding it with 0 would invent a "
                    f"root relation, and padding it with _ would fail on the "
                    f"next line for no clearer reason. A line this short is a "
                    f"truncated write, not a sparse token."
                )
            cols = cols + [UNDERSCORE] * (N_COLS - len(cols))

        tid, lo, hi = _parse_id(cols[COL_ID], line_no)
        form = cols[COL_FORM]

        if lo != hi:
            # MWT placeholder row. Remember the surface token, emit nothing.
            mwt_stack[lo] = {"form": form, "lo": lo, "hi": hi}
            continue

        misc = _misc(cols[COL_MISC])
        feats = _feats(cols[COL_FEATS])
        head_raw = cols[COL_HEAD].strip()
        try:
            head = int(head_raw)
        except ValueError as e:
            raise CoNLLUError(
                f"line {line_no}: HEAD {head_raw!r} is not an integer "
                f"(expected an integer or 0 for the root)"
            ) from e

        tok = {
            "id": tid,
            "form": "" if form == UNDERSCORE else form,
            "lemma": "" if cols[COL_LEMMA] == UNDERSCORE else cols[COL_LEMMA],
            "upos": "" if cols[COL_UPOS] == UNDERSCORE else cols[COL_UPOS],
            "xpos": "" if cols[COL_XPOS] == UNDERSCORE else cols[COL_XPOS],
            "feats": feats,
            "head": head,
            "deprel": "" if cols[COL_DEPRELS] == UNDERSCORE else cols[COL_DEPRELS],
            "deps": "" if cols[COL_DEPS] == UNDERSCORE else cols[COL_DEPS],
            "misc": misc,
            # Coptic-specific, and the reason this parser exists rather than a
            # generic CoNLL-U reader: the marked original orthography.
            "orig": misc.get("Orig", ""),
            "mseg": misc.get("MSeg", ""),
            "mwt": None,
        }
        # Attach to an enclosing MWT if one is open over this id.
        for start, info in mwt_stack.items():
            if info["lo"] <= tid <= info["hi"]:
                tok["mwt"] = {"lo": info["lo"], "hi": info["hi"],
                              "form": info["form"]}
                mwt_of[tid] = start
                break
        tokens.append(tok)

    tokens.sort(key=lambda t: t["id"])

    # Heads must reference a token in this sentence. A dangling head means the
    # parse is broken, and silently keeping it would produce a dependency graph
    # with edges to nowhere.
    ids = {t["id"] for t in tokens}
    dangling = sorted({t["head"] for t in tokens
                       if t["head"] != 0 and t["head"] not in ids})
    if dangling:
        raise CoNLLUError(
            f"line {line_no}: sentence {header.get('sent_id', '?')!r} has "
            f"HEAD(s) pointing at absent token id(s) {dangling}. Sentence has "
            f"ids {sorted(ids)[:8]}… A dangling head is a broken parse."
        )

    mwts = [{"lo": i["lo"], "hi": i["hi"], "form": i["form"]}
            for i in sorted(mwt_stack.values(), key=lambda x: x["lo"])]

    return {
        "sent_id": header.get("sent_id", ""),
        "text": header.get("text", ""),
        "text_en": header.get("text_en", ""),
        "dialect": dialect,
        "tokens": tokens,
        "mwt": mwts,
        "n_tokens": len(tokens),
        "header": {k: v for k, v in header.items() if k.startswith("meta::")
                   or k in ("newdoc id", "global.Entity")},
        "urn": header.get("meta::document_cts_urn", ""),
        "author": header.get("meta::author", ""),
        "title": header.get("meta::title", ""),
        "sources": [{"id": source, "licence": UD_SAHIDIC_LICENCE,
                     "doi": UD_SAHIDIC_DOI}],
        "provenance": {"record_id": header.get("sent_id", "")},
    }


def iter_sentences(path: pathlib.Path, *, declared_dialect: str | None = None,
                   source: str = UD_SAHIDIC_ID) -> Iterator[dict]:
    """Stream sentence records. One block in memory at a time."""
    header: dict[str, str] = {}
    block: list[str] = []
    dialect: str | None = None
    line_no = 0

    def flush(block: list[str], header: dict[str, str], start: int) -> dict | None:
        if not any(l and not l.startswith("#") for l in block):
            return None
        return parse_sentence(block, header, dialect=dialect or "unknown",
                              source=source, line_no=start)

    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line_no += 1
            line = line.rstrip("\n")
            if line.startswith("#"):
                k, v = _split_meta(line)
                # A `newdoc id` starts a new DOCUMENT. Everything meta:: belongs
                # to the previous document and must be cleared, or a second
                # document in the same file inherits the first one's URN,
                # author and title. The real dev file opens several newdoc
                # blocks, so this is not hypothetical.
                if k in ("newdoc id", "newdoc"):
                    for stale in [h for h in header if h.startswith("meta::")]:
                        del header[stale]
                # File-level keys apply until replaced; sent_id/text/text_en are
                # per-sentence and popped at the blank line.
                header[k] = v
                if dialect is None:
                    dialect = parse_dialect(header, declared_dialect)
                continue
            if not line.strip():
                rec = flush(block, header, line_no)
                if rec is not None:
                    yield rec
                block = []
                for k in ("sent_id", "text", "text_en"):
                    header.pop(k, None)
                continue
            block.append(line)

    rec = flush(block, header, line_no)
    if rec is not None:
        yield rec


def census(paths: list[pathlib.Path], *, declared_dialect: str | None = None) -> dict:
    out = {"files": len(paths), "sentences": 0, "tokens": 0, "mwt": 0,
           "with_en": 0, "with_orig": 0, "with_urn": 0, "dialects": {}}
    for p in paths:
        for s in iter_sentences(p, declared_dialect=declared_dialect):
            out["sentences"] += 1
            out["tokens"] += s["n_tokens"]
            out["mwt"] += len(s["mwt"])
            if s["text_en"]:
                out["with_en"] += 1
            if any(t["orig"] for t in s["tokens"]):
                out["with_orig"] += 1
            if s["urn"]:
                out["with_urn"] += 1
            out["dialects"][s["dialect"]] = out["dialects"].get(s["dialect"], 0) + 1
    return out


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="parse UD Coptic CoNLL-U")
    ap.add_argument("--input", type=pathlib.Path, nargs="+", default=None)
    ap.add_argument("--dialect", default="Sahidic",
                    help="declared dialect when the header has none (it has none)")
    ap.add_argument("--census", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args(argv)

    paths = args.input or sorted(pathlib.Path("sources/ud_coptic").glob("*.conllu"))
    if not paths:
        print("[conllu] no .conllu files found. Run tools/fetch/fetch_all.py.",
              file=sys.stderr)
        return 1

    if args.census:
        c = census(paths, declared_dialect=args.dialect)
        for k, v in c.items():
            print(f"[conllu] {k:14} {v}")
        return 0

    shown = 0
    for p in paths:
        for s in iter_sentences(p, declared_dialect=args.dialect):
            print(json.dumps(s, ensure_ascii=False, indent=2))
            shown += 1
            if args.limit and shown >= args.limit:
                return 0
    if not shown:
        print("[conllu] no sentences", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
