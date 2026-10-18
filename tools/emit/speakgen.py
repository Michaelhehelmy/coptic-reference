#!/usr/bin/env python3
"""tools/emit/speakgen.py — the top-100 frequency-ranked lemmas for /speak/.

LICENCE: project code, Apache-2.0.

Session 22 D1. Pronunciation practice needs a word list with a defensible
order, not a hand-picked "nice words to say". Frequency is the only rank
the corpus itself can supply: every lemma's total occurrences across the
six parsed works, summed from the dictionary's corpus_refs (which are
generated from the same tarball the corpus pages read).

Two outputs, one computation:

  data/dist/speak/speak.json.gz   the browser payload (published under
                                  /data/dist/speak/ by tools/build.py)
  work/speak/top100.html          a standalone static page with the same
                                  words as a table — the no-JS fallback,
                                  copied to public/speak/top100.html by
                                  tools/build.py. NOT a Hugo data file:
                                  touching site.Data in a template makes
                                  Hugo unmarshal EVERYTHING under data/,
                                  including corpus.tar.gz, which it cannot
                                  parse (Session 22: "unmarshal of format
                                  \"\" is not supported"). A page that needs
                                  no JS needs no Hugo data loader either.

No IPA is emitted: no entry in the dictionary carries an IPA field, and
the Session 22 spec says show IPA only with a source. A blank field would
be a claim of "no pronunciation"; silence is the honest state.
"""
from __future__ import annotations

import argparse
import gzip
import html
import json
import pathlib
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import safeio  # noqa: E402

DICT_DIR = ROOT / "data" / "dist" / "dict"
OUT_GZ = ROOT / "data" / "dist" / "speak" / "speak.json.gz"
OUT_HTML = ROOT / "work" / "speak" / "top100.html"
TOP_N = 100
# Schemes offered in the /speak/ selector. The payload carries every scheme
# the dictionary has; the selector is a presentation choice (Session 22 D1:
# bohairic default, sahidic, layton).
SCHEMES = ("bohairic", "sahidic", "layton")


def _rank1_gloss(entry: dict) -> str:
    """The rank-1 English gloss, or the first English gloss, or ""."""
    glosses = entry.get("glosses") or []
    first_en = ""
    for g in glosses:
        if not isinstance(g, dict):
            continue
        if g.get("lang") != "en":
            continue
        text = (g.get("text") or "").strip()
        if not text:
            continue
        if g.get("rank") == 1:
            return text
        if not first_en:
            first_en = text
    return first_en


def _total_occurrences(entry: dict) -> int:
    return sum(int(r.get("occurrences") or 0)
               for r in (entry.get("corpus_refs") or [])
               if isinstance(r, dict))


def collect(limit: int = TOP_N) -> tuple[list[dict], str]:
    """Top-N lemmas by corpus occurrences. Returns (words, collation_hash)."""
    shards = sorted(DICT_DIR.glob("shard-*.json.gz"))
    if not shards:
        raise SystemExit(f"speakgen: no dict shards under {DICT_DIR}. "
                         f"Run the merge pipeline first.")
    totals: Counter[str] = Counter()
    best: dict[str, dict] = {}
    collation = ""
    for shard in shards:
        data = json.loads(gzip.decompress(shard.read_bytes()))
        if not isinstance(data, dict) or "entries" not in data:
            raise SystemExit(f"speakgen: {shard.name} is not a dict shard")
        collation = data.get("collation_hash") or collation
        for entry in data["entries"]:
            occ = _total_occurrences(entry)
            if occ <= 0:
                continue
            lemma = entry.get("lemma") or ""
            if not lemma:
                continue
            totals[lemma] += occ
            prev = best.get(lemma)
            # Keep the entry with the rank-1 gloss if two ids share a lemma;
            # otherwise the first one seen wins (shard order is stable).
            if prev is None or (_rank1_gloss(entry) and not _rank1_gloss(prev)):
                best[lemma] = entry

    words: list[dict] = []
    for lemma, occ in totals.most_common(limit):
        entry = best[lemma]
        translit = entry.get("translit")
        if not isinstance(translit, dict):
            translit = {}
        words.append({
            "lemma": lemma,
            "norm_key": entry.get("norm_key") or lemma,
            "gloss": _rank1_gloss(entry),
            "occurrences": occ,
            "translit": {s: (translit.get(s) or "") for s in SCHEMES},
        })
    if len(words) < limit:
        raise SystemExit(f"speakgen: only {len(words)} lemmas have corpus "
                         f"occurrences; expected at least {limit}")
    return words, collation


def _top100_page(words: list[dict]) -> str:
    """A standalone, script-free HTML page: the 100 words as a table.

    Served at /speak/top100.html. No-JS visitors land here from the
    <noscript> link on /speak/; anyone else can open it directly. Inline
    styles only — this file is a build product, not a theme layout.
    """
    esc = html.escape
    rows = "\n".join(
        f'<tr><td>{i}</td><td lang="cop" dir="ltr">{esc(w["lemma"])}</td>'
        f'<td>{esc(w["translit"].get("bohairic") or "")}</td>'
        f'<td>{esc(w["translit"].get("sahidic") or "")}</td>'
        f'<td>{esc(w["translit"].get("layton") or "")}</td>'
        f'<td>{esc(w["gloss"])}</td>'
        f'<td>{w["occurrences"]}</td></tr>'
        for i, w in enumerate(words, 1))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Top 100 Coptic words — Coptic Reference</title>
<style>
  body {{ font-family: Georgia, "Times New Roman", serif; margin: 2rem auto;
         max-width: 52rem; padding: 0 1rem; color: #1a1a1a; line-height: 1.5; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 0.95rem; }}
  th, td {{ border: 1px solid #ccc; padding: 0.35rem 0.5rem; text-align: left; }}
  th {{ background: #f0f0f0; }}
  td[lang="cop"] {{ font-size: 1.1rem; }}
</style>
</head>
<body>
<h1>Top 100 Coptic words</h1>
<p>Frequency-ranked by total occurrences across the six works in this
site's corpus — see the <a href="/speak/">speaking page</a> for the
pronunciation practice. No JavaScript required.</p>
<table>
<thead><tr><th>#</th><th>Coptic</th><th>Bohairic</th><th>Sahidic</th>
<th>Layton</th><th>Gloss</th><th>Occurrences</th></tr></thead>
<tbody>
{rows}
</tbody>
</table>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="emit the /speak/ top-100 list")
    ap.add_argument("--top", type=int, default=TOP_N)
    args = ap.parse_args(argv)

    words, collation = collect(limit=args.top)

    payload = {
        "schema": "coptic-reference/speak/1",
        # Derived from inputs, never from the clock (build-manifest rule).
        "generated": "from-corpus-collation-" + (collation or "unknown"),
        "collation_hash": collation,
        "count": len(words),
        "words": words,
    }
    blob = gzip.compress(
        (json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"
         ).encode("utf-8"))
    OUT_GZ.parent.mkdir(parents=True, exist_ok=True)
    safeio.write_verified(OUT_GZ, blob)

    # Standalone no-JS page: the same words as a table, zero scripts, zero
    # fetches. NOT a Hugo data file — see module docstring.
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    safeio.write_verified(OUT_HTML, _top100_page(words).encode("utf-8"))

    top3 = ", ".join(f"{w['lemma']}({w['occurrences']})" for w in words[:3])
    print(f"[speakgen] {len(words)} word(s) → "
          f"{OUT_GZ.relative_to(ROOT)} + {OUT_HTML.relative_to(ROOT)}; "
          f"top: {top3}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
