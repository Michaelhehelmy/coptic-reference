#!/usr/bin/env python3
"""tools/validate/nc_guard.py — fail-closed NC allowlist (v4 §9, invariant 5).

v3's guard checked "if source.id in NC_SOURCES: fail". That is **fail-open**: a
brand-new source is not on the NC list, so it passes silently. The only thing
that protects the dataset from an unknown source is a list of sources somebody
remembered to worry about.

This version inverts it. Only ids on an explicit allowlist may appear inside
``data/dist/**``. Anything else is a violation, *including sources that do not
exist yet*. Adding a source is therefore a deliberate, reviewed PR — which is
the point. FAIL CLOSED.

Why this is the highest-consequence gate in the repository: CC BY-NC text
reaching the redistributable dataset is the single legal failure that cannot be
walked back. A blocklist catches it only for sources someone already thought of.
An allowlist catches it for every source, including ones added in the future.

The companion gate is ``tools/validate/licence_guard.py``: an id on the
allowlist must also have a non-``UNKNOWN`` row in ``LICENSES.csv``, so the
allowlist and the licence manifest cannot drift apart.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import shardio  # noqa: E402
from typing import Iterable

# ── the allowlist ────────────────────────────────────────────────────────────
# Every source permitted inside data/dist/**. Order is irrelevant; membership is
# what matters. ADDING AN ENTRY HERE IS THE REVIEW ACT.
#
# These ids are CITATION ids — the exact strings that appear in an entry's
# `sources[].id` and `attributions[].source`. They are deliberately NOT the
# lowercase TOML keys used in tools/sources.lock (which are fetch targets).
# The two namespaces are kept distinct on purpose; see DECISIONS.md S2-A1 for
# the collision hazard that creates and how it is checked.
ALLOWED_SOURCES: dict[str, str] = {
    # id              licence                    rationale
    "CCL":            "CC-BY-SA-4.0",           # BBAW + DDGLC; DOI 10.17169/refubium-27566
    "CDO":            "CC-BY-SA-4.0",           # KELLIA;      DOI 10.17169/refubium-2333
    "Kaikki":         "CC-BY-SA-4.0 OR GFDL",   # Wiktextract via kaikki.org
    "CDO-API":        "CC-BY-SA-4.0",           # frequencies from the CDO service
    "Scriptorium_TT": "CC-BY-SA-4.0",           # corpus text + aligned translations
    "Scriptorium_TEI": "CC-BY-SA-4.0",          # per-document licence; see LICENSES.csv
    "UD_Coptic":      "CC-BY-4.0",              # UD_Coptic-Scriptorium; its LICENSE.txt
                                            # says CC BY 4.0, NOT SA. Corrected Session 3.
    "Crum":           "PD",                     # Crum, A Coptic Dictionary (1925/1939)
    "TLA":            "CC-BY-4.0",              # Thesaurus Linguae Aegyptiae
    "ProjectRebuild": "PD",                     # text this project itself authors
    "TranslitTable":  "PD",                     # romanisation schemes are not copyrightable
    "G2PTable":       "CC-BY-SA-4.0",           # our own G2P, derived from CCL/CDO
    # MERGE is a PSEUDO-SOURCE, not an upstream. It denotes a field this project
    # produced by combining or reordering upstream data, and v4 §8.2's worked
    # example uses it ("source": "MERGE", "changes": "deduplicated across 3
    # sources..."). It was MISSING from v4 §9's allowlist, which made §8.2's own
    # documented pattern fail the §9 guard. Added in Session 2 so both sections
    # work together; see DECISIONS.md S2-A5. Licence is CC BY-SA 4.0 because a
    # merged field inherits the strictest licence of its inputs.
    #
    # Prefer naming the real upstream sources alongside it. v5 §16.2 requires
    # distinguishing the author (us) from the data originator (upstream), and
    # MERGE alone loses the originator. MERGE says WHO DID IT, not WHOSE DATA.
    "MERGE":          "CC-BY-SA-4.0",           # our own merge/derivation step
}

# ── the contra-list ──────────────────────────────────────────────────────────
# REMOVED Session 4, correction Q2: "UD_Bohairic". Its treebank is NOT
# PUBLISHED — github.com/UniversalDependencies/UD_Bohairic-Coptic returns HTTP
# 404 (probed 2026-10-04), and no other UD Coptic treebank exists. Allowlisting a
# source that cannot be fetched means the allowlist claims a permission nobody can
# exercise, which is the fail-open shape this whole module exists to prevent.
# Zeldes/Speransky/Wagner/Schroeder 2025 is a real citation for a real artefact we
# do not have; it is kept in tools/sources.lock under [ud_bohairic] as a RESERVED
# note, so re-adding it is a one-line diff when the release appears. See
# DECISIONS.md S4-D1.
#
# Permitted ONLY outside data/dist/** — i.e. under content/nc/ and static/pdf/.
# Presence of any of these inside the dataset is a hard failure.
#
# "verify licence" in a comment means: nobody has actually checked yet. That is
# exactly why the id is HERE rather than on the allowlist. An unverified licence
# is treated as NC until a human resolves it.
NC_ONLY_SOURCES: frozenset[str] = frozenset({
    "Manley2019",       # Sahidic Coptic: An Introductory Textbook — CC BY-NC 4.0
    "ShishaHalevy",     # Coptic Grammatical Chrestomathy — verify PD before use
    "LearnersGrammar",  # verify licence
    "Younan2005",       # verify / request permission
    "LoCPrimers",       # PD-US; non-US jurisdictions differ
    "AnkiDeck",         # per-deck; content licence is the author's
})

# Licences that may never appear on an allowlisted source, whatever the id says.
# Belt-and-braces: a typo that puts an NC licence on an allowed id still fails.
FORBIDDEN_LICENCE_MARKERS: tuple[str, ...] = ("-NC", "NC-", "NONCOMMERCIAL", "NON-COMMERCIAL")

# Where NC material is permitted to live. Anything under here is skipped by
# check 2.
NC_CONTENT_DIR: str = "nc"


class NCGuardError(SystemExit):
    """Raised on any violation.

    Subclasses SystemExit exactly as v4 §9 specifies, so `raise NCGuardError(msg)`
    from a library caller terminates with a non-zero status and prints the reason
    — which is what CI wants. Note this makes it invisible to `except Exception`,
    so catch SystemExit explicitly.
    """


def _is_nc_content(path: pathlib.Path, content_root: pathlib.Path) -> bool:
    """True if `path` lives under content/nc/.

    v4 §9's sample used the substring test ``if "nc/" in p.as_posix()``. That
    works for real paths but is fragile: it would skip any path that happens to
    contain the two characters "nc/" anywhere, including a future
    ``content/lincoln/``-style directory. This compares resolved path parts
    instead. No behaviour change for the paths that exist today; strictly fewer
    false skips later. Logged as DECISIONS.md S2-B1.
    """
    try:
        rel = path.resolve().relative_to(content_root.resolve())
    except ValueError:
        return False
    return NC_CONTENT_DIR in rel.parts[:-1]  # the file itself may not be named nc


def _iter_shard_entries(dist: pathlib.Path) -> Iterable[tuple[pathlib.Path, dict]]:
    """Yield (shard_path, entry) for every entry in the dataset.

    Session 5 G1/G2. This used to be its own ``dist.rglob("*.json")`` loop, which
    meant two things were true at once and neither was visible in the code:

      - it PASSED with the whole dataset deleted (zero entries is a valid dataset
        to a loop with no zero check);
      - it matched no ``.json.gz`` shard, so the day D2 gzipped the dictionary it
        would have checked nothing and said OK.

    It is now a thin wrapper over ``tools.shardio``, which resolves both suffixes
    and fails closed on an empty directory. Note the parameter is still named
    `dist` because licence_guard imports this function; it is walked for `dict/`.
    """
    dict_dir = dist / "dict" if (dist / "dict").is_dir() else dist
    yield from shardio.iter_entries(dict_dir, require=True)


def check(dist: pathlib.Path, content: pathlib.Path) -> None:
    """Raise NCGuardError on any violation. Returns None when clean."""
    errors: list[str] = []

    # ── 1. every dataset entry's sources must be allowlisted ─────────────────
    for shard, e in _iter_shard_entries(dist):
        ids = {s["id"] for s in e.get("sources", []) or [] if isinstance(s, dict) and "id" in s}
        ids |= {a["source"] for a in e.get("attributions", []) or []
                if isinstance(a, dict) and "source" in a}
        entry_id = e.get("id", "<no id>")
        for sid in sorted(ids):
            if sid in NC_ONLY_SOURCES:
                errors.append(
                    f"{shard.name} entry {entry_id}: NC source {sid!r} "
                    f"inside the dataset — permitted only under "
                    f"content/{NC_CONTENT_DIR}/"
                )
            elif sid not in ALLOWED_SOURCES:
                errors.append(
                    f"{shard.name} entry {entry_id}: source {sid!r} is "
                    f"NOT in ALLOWED_SOURCES — fail-closed. Add it to "
                    f"tools/validate/nc_guard.py in a reviewed PR, with a row "
                    f"in data/dist/provenance/LICENSES.csv."
                )
            else:
                licence = ALLOWED_SOURCES[sid]
                if any(m in licence.upper() for m in FORBIDDEN_LICENCE_MARKERS):
                    errors.append(
                        f"{shard.name} entry {entry_id}: source {sid!r} IS "
                        f"allowlisted but its licence {licence!r} is non-commercial. "
                        f"An NC licence must never be allowlisted."
                    )

    # ── 2. NC ids must not appear outside content/nc/ ────────────────────────
    if content.is_dir():
        for p in sorted(content.rglob("*.md")):
            if _is_nc_content(p, content):
                continue
            text = p.read_text(encoding="utf-8", errors="ignore")
            for sid in sorted(NC_ONLY_SOURCES):
                if sid in text:
                    errors.append(
                        f"{p}: references NC source {sid!r} outside "
                        f"content/{NC_CONTENT_DIR}/"
                    )

    # ── 3. the allowlist itself must be internally consistent ───────────────
    overlap = set(ALLOWED_SOURCES) & NC_ONLY_SOURCES
    if overlap:
        errors.append(
            f"allowlist/contra-list overlap: {sorted(overlap)} — an id cannot "
            f"be both permitted and forbidden inside data/dist"
        )
    for sid, licence in sorted(ALLOWED_SOURCES.items()):
        if any(m in licence.upper() for m in FORBIDDEN_LICENCE_MARKERS):
            errors.append(
                f"ALLOWED_SOURCES[{sid!r}] carries non-commercial licence "
                f"{licence!r} — remove it from the allowlist"
            )

    if errors:
        for e in errors:
            print(f"[nc_guard] FAIL {e}", file=sys.stderr)
        raise NCGuardError(
            f"[nc_guard] {len(errors)} violation(s). data/dist/** must contain "
            f"only CC BY-SA / CC BY / PD material."
        )

    shard_count = sum(1 for _ in _iter_shard_entries(dist))
    print(
        f"[nc_guard] OK — {len(ALLOWED_SOURCES)} allowlisted sources, "
        f"{len(NC_ONLY_SOURCES)} NC sources correctly excluded, "
        f"{shard_count} entries checked, "
        f"0 violations (fail-closed: anything unlisted is a violation)"
    )


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="fail-closed NC allowlist (v4 §9)")
    ap.add_argument("--dist", default="data/dist", type=pathlib.Path,
                    help="dataset root (default: data/dist)")
    ap.add_argument("--content", default="content", type=pathlib.Path,
                    help="content root (default: content)")
    args = ap.parse_args(argv)
    try:
        check(args.dist, args.content)
    except NCGuardError as e:
        print(e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
