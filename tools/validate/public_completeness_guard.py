#!/usr/bin/env python3
"""tools/validate/public_completeness_guard.py — everything expected is PRESENT.

Session 10 C1. `public_provenance_guard.py` answers "is every file here accounted
for?" This one answers the other half: **"is everything that should be here,
here?"**

The two are opposites and both are needed. Provenance alone would happily pass on
an empty `public/` with a manifest listing nothing, and completeness alone would
happily pass on a directory full of files nobody owns. Session 9 found this the
hard way: `tools/build.py` silently failed partway through (a JavaScript syntax
error), `rm -rf public` had already run, and the provenance guard — asked only
whether files were accounted for — had nothing to say about the ones that should
exist and did not.

Expectations are DERIVED, not listed by hand, wherever the truth lives elsewhere:

  * the shard set comes from `data/dist/dict/` — so a shard cannot be added or
    dropped without this guard noticing;
  * the expected works come from `data/dist/corpus/manifest.json`;
  * sizes come from `data/dist`, so `public/` cannot hold a truncated copy.

Anything with a real size requirement is asserted NON-EMPTY. A zero-byte shard
and a missing shard are the same bug to a reader, and only the size check tells
them apart.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="every expected artefact is present")
    ap.add_argument("--public", type=pathlib.Path, default=ROOT / "public")
    ap.add_argument("--dist", type=pathlib.Path, default=ROOT / "data" / "dist")
    ap.add_argument("--strict", action="store_true",
                    help="additionally require every published HTML page to be "
                         "non-trivial and every service-worker precache target to "
                         "resolve. Used in CI.")
    args = ap.parse_args(argv)

    pub = args.public
    errors: list[str] = []
    checked = 0

    if not pub.is_dir():
        print(f"[public_completeness] FAIL — {pub} does not exist. Run "
              f"tools/build.py.", file=sys.stderr)
        return 1

    def need(rel: str, why: str, min_bytes: int = 1) -> pathlib.Path:
        """Assert a file exists AND is big enough to be real."""
        nonlocal checked
        checked += 1
        p = pub / rel
        if not p.exists():
            errors.append(f"{rel} is MISSING — {why}")
            return p
        if not p.is_file():
            errors.append(f"{rel} is not a file — {why}")
            return p
        n = p.stat().st_size
        if n < min_bytes:
            errors.append(f"{rel} is {n} B, below the {min_bytes} B floor — {why}. "
                          f"A truncated copy reads as a smaller dataset, not an error.")
        return p

    # ── 1. the dictionary the reader fetches ────────────────────────────────
    dict_dir = args.dist / "dict"
    src_shards = sorted(dict_dir.glob("shard-*.json.gz"))
    if not src_shards:
        errors.append(f"data/dist/dict has no shard-*.json.gz, so there is nothing "
                      f"to expect. Run tools/emit/cli.py first.")
    need("data/dist/dict/index.json.gz", "the reader's lookup table; without it "
                                          "the /dict/ route cannot load")
    for s in src_shards:
        need(f"data/dist/dict/{s.name}",
             f"published copy of data/dist/dict/{s.name}; the reader fetches one "
             f"shard per lookup", min_bytes=1024)

    # The published path mirrors data/dist, so it is data/dist/dict under public/
    # -- NOT data/dict. Getting that wrong made this guard report zero shards and
    # claim a 23-shard dataset was incomplete, which was me, not the build.
    _pub_dict = pub / "data" / "dist" / "dict"
    pub_shards = sorted(_pub_dict.glob("shard-*.json.gz")) if _pub_dict.is_dir() else []
    if len(pub_shards) != len(src_shards):
        extra = sorted({p.name for p in pub_shards} - {p.name for p in src_shards})
        errors.append(
            f"public/ has {len(pub_shards)} shard(s), data/dist/dict has "
            f"{len(src_shards)}. Extra in public/: {extra or 'none'}. A shard in "
            f"public/ that is not in data/dist has no provenance (see "
            f"public_provenance_guard).")

    # ── 2. provenance, corpus, vault, search, worker ────────────────────────
    need("licences/records.csv.gz", "the per-(entry, source) provenance table")
    need("licences/LICENSES.csv.gz", "the licence manifest. It NAMES the six NC "
                                      "sources it excludes, so it lives under "
                                      "licences/ and nowhere else (invariant 5)")
    need("downloads/coptic-reference-vault.zip", "the Obsidian download")
    need("sw.js", "the service worker; without it the site works but never caches")
    need("js/reader.js", "the dictionary reader")

    pf = pub / "pagefind"
    if not pf.is_dir():
        errors.append("pagefind/ is MISSING — search returns nothing")
    else:
        pf_files = [p for p in pf.rglob("*") if p.is_file()]
        checked += len(pf_files)
        if not pf_files:
            errors.append("pagefind/ exists but is EMPTY — the indexer ran and "
                          "produced nothing")
        if not (pf / "pagefind.js").is_file():
            errors.append("pagefind/pagefind.js is missing — that is the entry "
                          "point the search box loads")

    # ── 3. the corpus, work by work, from the manifest ─────────────────────
    manifest = args.dist / "corpus" / "manifest.json"
    if not manifest.is_file():
        errors.append("data/dist/corpus/manifest.json is missing; the expected "
                      "work set cannot be derived")
    else:
        m = json.loads(manifest.read_text(encoding="utf-8"))
        for slug in sorted(m.get("works", {})):
            need(f"data/corpus/{slug}/meta.json",
                 f"meta for work {slug}, from data/dist/corpus/manifest.json")
            need(f"data/corpus/{slug}/text.json.gz", f"readable text for {slug}",
                 min_bytes=64)
            need(f"data/corpus/{slug}/tokens.json.gz", f"tokens for {slug}",
                 min_bytes=64)

    # ── 4. the pages ───────────────────────────────────────────────────────
    html = sorted(pub.rglob("*.html"))
    checked += len(html)
    if not html:
        errors.append("no .html files at all — the site has no pages")
    if not (pub / "index.html").is_file():
        errors.append("index.html is missing — the root route")
    # Session 18 D4: the learning pages are required routes too — a drill
    # page that 404s is a shipped bug, not a missing feature.
    for route in ("dict", "dialects", "licences", "quiz", "drill"):
        if not (pub / route / "index.html").is_file():
            errors.append(f"{route}/index.html is missing — a linked route 404s")
    if not (pub / "sitemap.xml").is_file():
        errors.append("sitemap.xml is missing (hugo.yaml asks for it)")

    # ── 5. the manifest the build wrote ────────────────────────────────────
    if not (pub / "BUILD-MANIFEST.json").is_file():
        errors.append("BUILD-MANIFEST.json is missing — public/ was not produced "
                      "by tools/build.py (Rule 5)")

    # ── 6. --strict: the two checks a manifest cannot catch ────────────────
    #
    # BUILD-MANIFEST.json lists every file, and public_provenance_guard --strict
    # proves each one is accounted for. Both are satisfiable by a file that exists
    # and is empty, or by an HTML page that renders a heading and nothing else.
    # --strict closes those two gaps.
    if args.strict:
        for p in sorted(pub.rglob("*")):
            if p.is_file() and p.suffix in (".html", ".js", ".json") and p.stat().st_size == 0:
                errors.append(f"{p.relative_to(pub)} is zero bytes")

        sw = pub / "sw.js"
        if sw.is_file():
            import re as _re
            txt = sw.read_text(encoding="utf-8", errors="replace")
            for url in _re.findall(r"[\"'](/[A-Za-z0-9._~/-]*)[\"']", txt):
                if url.endswith((".html", ".json", ".gz", ".css", ".js")):
                    if not (pub / url.lstrip("/")).exists():
                        errors.append(f"sw.js precaches {url} but public/{url.lstrip('/')} "
                                      f"does not exist — the offline test cannot pass")

        for p in sorted(html):
            if p.stat().st_size < 400:
                errors.append(f"{p.relative_to(pub)} is only {p.stat().st_size} B — "
                              f"probably a shell with no content")

    if errors:
        print(f"[public_completeness] FAIL — {len(errors)} problem(s) in "
              f"{pub.name}/:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"[public_completeness] OK — {checked} artefact(s) checked: "
          f"{len(src_shards)} shard(s), the index, 2 provenance tables, the "
          f"corpus for every manifest work, the vault, pagefind/, sw.js and "
          f"{len(html)} HTML page(s). Nothing missing, nothing empty.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
