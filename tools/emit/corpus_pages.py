#!/usr/bin/env python3
"""tools/emit/corpus_pages.py — write Hugo content pages for /corpus/<work>/.

Session 10 D3.

Reads ONLY the pinned, already-gzipped corpus under data/corpus/<slug>/meta.json
and writes a Hugo page per work into content/corpus/. Nothing here re-parses the
source TT: the pages cannot disagree with the reader, because the reader fetches
the same bytes this script reads the metadata from.

Front matter carries the provenance (dialect, licence, source pin, content
sha256) so the WORK page -- not just the API -- is auditable. The body carries a
no-JavaScript fallback that still tells a reader where the data is and what it
is.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import tarfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parents[0]))
import safeio  # noqa: E402

# The per-work directories exist only INSIDE the pinned tarball and inside
# public/ (which build.py wipes). Reading the tarball keeps this step independent
# of public/ and reads exactly the bytes the fingerprint covers.
TARBALL = ROOT / "data" / "dist" / "corpus" / "corpus.tar.gz"
DEST = ROOT / "content" / "corpus"


DIALECT = {"B": "Bohairic", "S": "Sahidic", "BO": "Bohairic", "SA": "Sahidic"}


def dialect_name(code: str) -> str:
    return DIALECT.get((code or "").strip(), code or "unknown")


def slugify(text: str) -> str:
    """Anchor-safe id from a verse ref like 'Ruth 1:1' -> 'ruth-1-1'."""
    s = re.sub(r"[^0-9A-Za-z]+", "-", text).strip("-").lower()
    return s or "v"


def works() -> list[tarfile.TarInfo, dict]:
    """Every work's meta.json, straight out of the fingerprint-covered tarball."""
    out = []
    with tarfile.open(TARBALL, "r:gz") as tf:
        for m in tf.getmembers():
            if m.name.endswith("/meta.json"):
                meta = json.loads(tf.extractfile(m).read().decode("utf-8"))
                out.append((m.name.split("/")[0], meta))
    return sorted(out, key=lambda kv: kv[0])


def index_page(ws: list[tuple[str, dict]]) -> str:
    rows = "\n".join(
        f"- [{w.get('title') or slug}](/corpus/{slug}/) — {dialect_name(w.get('dialect', ''))}, "
        f"{len(w.get('files', []))} source file"
        f"{'s' if len(w.get('files', [])) != 1 else ''}"
        for slug, w in ws
    )
    return f"""---
title: "Corpus"
slug: "corpus"
weight: 3
---

# Corpus

{len(ws)} Coptic texts, parsed from pinned source files and fingerprinted. Every
page below links to the same `.json.gz` bytes the dictionary's corpus counts were
computed from, so what you read here and what the reader counts cannot drift.

Click any Coptic token to look it up in the [dictionary](/dict/); dictionary
entries link back to the works a word appears in.

## The texts

{rows}

## What is not here

Three liturgical texts are declared in `tools/shipped.toml` and have **no
upstream source**: the Bohairic Laud offices, the Theotokia, and the common
prayers. They are absent rather than substituted, and the
[licences page](/licences/) says so. Nothing on this page is a reconstruction.

## Provenance

Each work page names its source, its pinned commit, its dialect, its licence,
and the SHA-256 of its content. Those are not decoration — they are what makes
the numbers on this site checkable.
"""


def work_page(w: dict) -> str:
    files = w.get("files", [])
    file_rows = "\n".join(f"  - `{f}`" for f in files) or "  - (single file)"
    shas = w.get("content_sha256") or {}
    sha_rows = "\n".join(f"  - `{k}`: `{v}`" for k, v in sorted(shas.items()))
    if isinstance(shas, str):
        sha_rows = f"  - `{shas}`"

    # The upstream metadata for some works claims full word-for-word alignment,
    # but the published tokens carry no per-token English (form, norm, lemma,
    # pos, func, head, ref and nothing else). So the reader shows the Coptic
    # token stream with the English VERSE beneath it and says so, rather than
    # implying a gloss-per-word it cannot deliver. Rule 1: a checker does not
    # generate the artefact it describes.
    note = w.get("note", "")
    align_claim = w.get("alignment", "")
    alignment_note = ""
    if align_claim in ("full", "word-for-word", "full-alignment"):
        alignment_note = (
            f"\n> **Note on alignment.** Upstream metadata records "
            f"`alignment = \"{align_claim}\"`, but the published `tokens.json` "
            f"carries no per-token English — a token is `form`, `norm`, `lemma`, "
            f"`pos`, `func`, `head`, `ref`. The reader therefore shows the Coptic "
            f"token stream with the whole English verse beneath it. Word-level "
            f"alignment is claimed by the source, not demonstrated by this "
            f"project's artefacts, and the page does not pretend otherwise.\n"
        )
    return f"""---
title: "{w.get('title') or w['slug']}"
slug: "{w['slug']}"
work_slug: "{w['slug']}"
dialect: "{w.get('dialect', '')}"
licence: "{w.get('licence', '')}"
weight: 10
---


{{{{< corpus >}}}}

## Provenance

- **Dialect**: {dialect_name(w.get('dialect', ''))} (`{w.get('dialect', '')}`)
- **Licence**: {w.get('licence', 'see /licences/')}
- **Source**: {w.get('source_id', '')}
- **Pinned at**: `{w.get('source_pin', '')}`
- **Alignment (upstream claim)**: `{align_claim}`
- **Generated**: {w.get('generated', '')}
{alignment_note}
Content SHA-256, per file:
{sha_rows}

Source files:
{file_rows}

[Back to the corpus index](/corpus/) · [Dictionary](/dict/)
"""


def esc(s: str) -> str:
    return str(s).replace('"', "'")


def main() -> int:
    pairs = works()
    if not pairs:
        print("[corpus_pages] FAIL — no works under data/corpus/", file=sys.stderr)
        return 1

    DEST.mkdir(parents=True, exist_ok=True)
    safeio.write_verified(DEST / "_index.md", index_page(pairs).encode("utf-8"))

    live = set()
    for slug, w in pairs:
        d = DEST / slug
        d.mkdir(parents=True, exist_ok=True)
        safeio.write_verified(d / "_index.md", work_page(w).encode("utf-8"))
        live.add(slug)

    # Remove pages for works that no longer exist, so a dropped source cannot
    # leave a route that 404s on its own data.
    for d in sorted(DEST.iterdir()):
        if d.is_dir() and d.name not in live:
            for f in d.glob("_index.md"):
                f.unlink()
            d.rmdir()
            print(f"[corpus_pages] removed stale page {d.name}")

    print(f"[corpus_pages] {len(pairs)} work page(s) + index written to content/corpus/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
