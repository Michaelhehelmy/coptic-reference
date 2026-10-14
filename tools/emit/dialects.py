#!/usr/bin/env python3
"""tools/emit/dialects.py — data/dist/dialects.json for the /dialects/ page (D5).

This is the file that makes v4 §10.2's Bohairic honesty CLAIM rather than prose.
"Bohairic is presentation priority, not data reality" is only true if a reader
can see the reality, so the page needs counts, computed from the shipped data
rather than asserted in a design document.

no_dialect_recorded is the number that matters most and the one most likely to be
left out. Q4: those entries are SHOWN with a visible "dialect not recorded — this
may be Sahidic" note. They are never filtered. 1,631 entries currently have no
dialect evidence from any source, and hiding them would make the dictionary look
better-grounded than it is.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import tarfile
import tomllib

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))

# After the sys.path line, not before it: the import is what needs the path.
import safeio  # noqa: E402
import shardio  # noqa: E402

GENERATED = "2026-10-04T00:00:00Z"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="write dialects.json")
    ap.add_argument("--dist", type=pathlib.Path, default=ROOT / "data" / "dist")
    args = ap.parse_args(argv)

    by_dialect: dict[str, int] = {}
    total = with_tla = no_dialect = 0
    # Session 5 G2: was glob("shard-*.json"), which matches nothing once the
    # shards are gzipped -- it would have reported 0 entries and still said OK.
    for _shard, e in shardio.iter_entries(args.dist / "dict", require=True):
        if True:
            total += 1
            if e.get("id") and not str(e["id"]).startswith("H"):
                with_tla += 1
            ds = e.get("dialects") or []
            if ds == ["N"]:
                no_dialect += 1
            for d in ds:
                by_dialect[d] = by_dialect.get(d, 0) + 1

    with (ROOT / "tools" / "shipped.toml").open("rb") as fh:
        works = [w for w in tomllib.load(fh).get("work", []) if w.get("shipped", True)]

    shipped_works = 0
    corpus_words = 0
    manifest = args.dist / "corpus" / "manifest.json"
    if manifest.is_file():
        m = json.loads(manifest.read_text(encoding="utf-8"))
        shipped_works = m.get("works_count", 0)
        corpus_words = sum(w.get("tokens", 0) for w in m.get("works", {}).values())

    out = {
        "schema": "coptic-reference/dialects/1",
        "generated": GENERATED,
        "total_entries": total,
        "with_tla_id": with_tla,
        "by_dialect": dict(sorted(by_dialect.items(), key=lambda kv: -kv[1])),
        "no_dialect_recorded": no_dialect,
        "shipped_works": shipped_works,
        "declared_works": len(works),
        "corpus_words": corpus_words,
        "notes": {
            "N": "Undetermined. A source recorded the lemma with no dialect, or "
                 "no source recorded a dialect at all. Shown with a visible "
                 "note; never filtered (Session 4 Q4).",
            "expansions": "A=Assiutic Ak=Akhmimic F=Fayumic S=Sahidic B=Bohairic. "
                          "L, M, P, V, W are CCL codes whose expansions this "
                          "project has not established; they are shown "
                          "verbatim rather than guessed.",
            "bohairic": "Bohairic is presented first because it is the language "
                        "the living Church uses. That is a PRESENTATION decision, "
                        "not a claim of equal data. v4 §10.2.",
        },
    }
    dest = args.dist / "dialects.json"
    safeio.write_text_verified(
        dest, json.dumps(out, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(f"[dialects] total_entries        {total}")
    print(f"[dialects] with_tla_id          {with_tla}")
    print(f"[dialects] no_dialect_recorded  {no_dialect}  ({no_dialect * 100 // max(total,1)}%)")
    print(f"[dialects] by_dialect           {out['by_dialect']}")
    print(f"[dialects] shipped_works        {shipped_works} of {len(works)} declared")
    print(f"[dialects] corpus_words         {corpus_words}")
    print(f"[dialects] wrote                {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
