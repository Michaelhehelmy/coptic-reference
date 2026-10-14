#!/usr/bin/env python3
"""tools/emit/corpus_refs.py — populate corpus_refs from the shipped corpus (D2).

For every entry in data/dist/dict/shard-*.json, find occurrences of its lemma in
the shipped corpus and record them: which works, at what frequency, at what rank.

    freq_per_10k = occurrences / total_corpus_tokens * 10000
    lemma_rank   = the lemma's rank by frequency within that work (1 = most frequent)

Up to MAX_REFS_PER_ENTRY refs, one per work, ordered by frequency then title. An
entry with no occurrence ships `corpus_refs: []` — which is a real answer, not a
gap: most Coptic dictionary headwords are rare or absent from a single biblical
book, and an empty list is the truth. It is emphatically NOT filled with a
placeholder, and the entry is not dropped.

COLLATION. Matching is on the collation key (`collate.canon_for_sort`), so a
Greek-script capital matches its small form. Matching on raw strings would miss
real occurrences — the S2-B10 bug, in a new place.

WHAT IS AVAILABLE. One of nine shipped works has source data in this environment
(sahidic_ruth, 85 verses). So every corpus_ref points at Ruth, and the per-entry
ref count tops out at 1 rather than 10. That is the number, reported rather than
padded.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import shardio  # noqa: E402
import tarfile
from collections import Counter, defaultdict

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import collate  # noqa: E402

MAX_REFS_PER_ENTRY = 10
GENERATED = "2026-10-04T00:00:00Z"


def key(s: str) -> str:
    return collate.canon_for_sort(s)


def load_corpus(tarball: pathlib.Path, manifest_path: pathlib.Path) -> dict:
    """{work_slug: {"meta":…, "counts": Counter, "total": int}}"""
    if not tarball.is_file():
        raise SystemExit(f"[corpus_refs] {tarball} not found. "
                         f"Run tools/emit/corpus_tarball.py first.")
    manifest = shardio.read_shard(manifest_path)
    works: dict[str, dict] = {}
    with tarfile.open(tarball, "r:gz") as tf:
        slugs = sorted({n.split("/")[0] for n in tf.getnames() if "/" in n})
        for slug in slugs:
            fh = tf.extractfile(f"{slug}/meta.json")
            meta = json.loads(fh.read().decode("utf-8")) if fh else {}
            fh = tf.extractfile(f"{slug}/tokens.json")
            tokens = json.loads(fh.read().decode("utf-8"))["tokens"] if fh else []
            counts = Counter()
            for t in tokens:
                lemma = (t.get("lemma") or "").strip()
                if lemma:
                    counts[key(lemma)] += 1
            works[slug] = {"meta": meta, "counts": counts, "total": len(tokens)}
    return {"works": works, "manifest": manifest}


def build_index(corpus: dict) -> dict[str, list[dict]]:
    """norm_key -> [{urn, work_title, work_slug, freq_per_10k, lemma_rank}]"""
    index: dict[str, list[dict]] = defaultdict(list)
    for slug, w in sorted(corpus["works"].items()):
        meta = w["meta"]
        total = max(w["total"], 1)
        # rank within this work, most frequent first; ties broken by the lemma
        # itself so the rank is deterministic across runs.
        ordered = sorted(w["counts"].items(), key=lambda kv: (-kv[1], kv[0]))
        rank = {k: i + 1 for i, (k, _c) in enumerate(ordered)}
        urn = meta.get("urn") or ""
        for lemma_key, n in ordered:
            index[lemma_key].append({
                "urn": urn,
                "work_title": meta.get("title", slug),
                "work_slug": slug,
                "freq_per_10k": round(n / total * 10000, 2),
                "lemma_rank": rank[lemma_key],
                "occurrences": n,
            })
    return index


def refs_for(entry: dict, index: dict[str, list[dict]]) -> list[dict]:
    hits = index.get(key(entry.get("lemma", "")), [])
    if not hits:
        return []
    # One ref per work: if the index somehow holds several for a work, keep the
    # highest-frequency one. freq desc, then rank asc, then title for determinism.
    best: dict[str, dict] = {}
    for h in hits:
        cur = best.get(h["work_slug"])
        if cur is None or (-h["freq_per_10k"], h["lemma_rank"], h["work_title"]) < \
                          (-cur["freq_per_10k"], cur["lemma_rank"], cur["work_title"]):
            best[h["work_slug"]] = h
    ordered = sorted(best.values(),
                     key=lambda h: (-h["freq_per_10k"], h["lemma_rank"],
                                    h["work_title"]))
    return ordered[:MAX_REFS_PER_ENTRY]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="populate corpus_refs")
    ap.add_argument("--dist", type=pathlib.Path, default=ROOT / "data" / "dist")
    ap.add_argument("--tarball", type=pathlib.Path,
                    default=ROOT / "data" / "dist" / "corpus" / "corpus.tar.gz")
    ap.add_argument("--manifest", type=pathlib.Path,
                    default=ROOT / "data" / "dist" / "corpus" / "manifest.json")
    ap.add_argument("--stats-only", action="store_true")
    args = ap.parse_args(argv)

    corpus = load_corpus(args.tarball, args.manifest)
    index = build_index(corpus)
    total_tokens = sum(w["total"] for w in corpus["works"].values())
    print(f"[corpus_refs] {len(corpus['works'])} work(s), {total_tokens} tokens, "
          f"{len(index)} distinct lemmas")

    # Session 5 G2: glob("shard-*.json") matches nothing once shards are .gz.
    shards = shardio.shard_paths(args.dist / "dict")
    if not shards:
        raise SystemExit("[corpus_refs] no shards; run tools/emit/cli.py first")

    before = after = with_refs = 0
    ref_counts: Counter = Counter()
    top: list[tuple[int, str, list[dict]]] = []

    for shard in shards:
        payload = shardio.read_shard(shard)
        changed = False
        for e in payload["entries"]:
            before += 1
            refs = refs_for(e, index)
            e["corpus_refs"] = refs
            after += 1
            if refs:
                with_refs += 1
                ref_counts[len(refs)] += 1
                top.append((len(refs), e.get("lemma", ""), refs))
            changed = True
        if changed and not args.stats_only:
            # Session 5 S5-B2: this used to be write_text(json.dumps(...)),
            # which put PLAIN JSON into 23 files named shard-NNN.json.gz.
            shardio.write_shard(shard, payload)
    print(f"[corpus_refs] entries before: {before}")
    print(f"[corpus_refs] entries after : {after}")
    print(f"[corpus_refs] with >=1 corpus_ref: {with_refs} "
          f"({with_refs * 100 // max(after, 1)}%)")
    print(f"[corpus_refs] with 0 corpus_refs : {after - with_refs} "
          f"(real: a headword absent from the shipped corpus)")
    print(f"[corpus_refs] refs-per-entry histogram: "
          f"{dict(sorted(ref_counts.items()))}")

    top.sort(key=lambda t: (-t[0], t[1]))
    print("[corpus_refs] top 5 by corpus_ref count:")
    for n, lemma, refs in top[:5]:
        print(f"    {n}  {lemma}  ({refs[0]['work_title']}, "
              f"rank {refs[0]['lemma_rank']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
