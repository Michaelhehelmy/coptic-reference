#!/usr/bin/env python3
"""tools/emit/cli.py — shard emission (Session 3, D5).

Writes the committed dataset:

    data/dist/dict/shard-NNN.json          500 entries per shard, Coptic order
    data/dist/dict/index.json              header incl. collation_hash
    data/dist/provenance/records.csv       v4 §6.2 — one row per (record, source)
    data/dist/provenance/LICENSES.csv      v4 §7.1 — regenerated from the allowlist

WHY THE ORDER MATTERS ENOUGH TO ASSERT IT
    Shards are cut from a Coptic-collation-ordered list. Cutting from a
    codepoint-ordered list would group Ϣⲁⲓ with ⲁⲛ and ⲃⲁ, so a letter page
    would have to scan every shard to render one letter. It also means shard
    boundaries land between letters, so adding one entry does not reshuffle the
    whole dataset. `sorted()` is banned here and the check below says so.

THE COLLATION PIN IS WRITTEN INTO THE OUTPUT
    index.json carries `collation_hash`. If someone changes the alphabet without
    re-baking, the hash in the committed data stops matching tools/collate.py and
    collation_guard.py fails. That is the review gate for alphabet changes,
    stated in v4 §1.3, and it only works if the hash travels with the data.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "validate"))

import safeio  # noqa: E402
from shardio import write_shard  # noqa: E402

import collate  # noqa: E402

SHARD_SIZE = 500
GENERATED = "2026-10-04T00:00:00Z"


#: Session 5 D2 / C2: the shipped shard form is gzipped. `.json.gz` is what goes
#: to disk and to the reader; the uncompressed `.json` is NOT kept alongside it.
SHARD_SUFFIX = ".json.gz"


def shard_name(i: int) -> str:
    return f"shard-{i:03d}{SHARD_SUFFIX}"


def _render_licences(rows: list[dict], cols: list[str]) -> bytes:
    """lic_rows -> CSV bytes. Kept separate so the write can be verified."""
    buf = io.StringIO(newline="")
    w = csv.DictWriter(buf, fieldnames=cols, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode("utf-8")


def emit(entries: list[dict], dist: pathlib.Path, *,
         pipeline_version: str) -> dict:
    """Write shards, index and provenance. Returns a summary dict."""
    dict_dir = dist / "dict"
    prov_dir = dist / "provenance"
    dict_dir.mkdir(parents=True, exist_ok=True)
    prov_dir.mkdir(parents=True, exist_ok=True)

    # Remove stale shards from a previous bake. A shard left behind from a larger
    # previous bake would be committed alongside the new ones and served to
    # readers, so its entries would appear twice.
    # Both suffixes: a bake that shrinks the dataset must not leave a .gz behind
    # from the previous run, and must not leave a .json from before D2 either.
    for old in list(dict_dir.glob("shard-*.json.gz")) + list(dict_dir.glob("shard-*.json")):
        old.unlink()

    # ── Coptic collation order. NEVER python sorted(). ────────────────────────
    ordered = collate.coptic_sorted(entries, key=lambda e: e["norm_key"])

    n_shards = 0
    for i in range(0, len(ordered), SHARD_SIZE):
        chunk = ordered[i:i + SHARD_SIZE]
        n = i // SHARD_SIZE
        payload = {
            "shard": n,
            "count": len(chunk),
            "collation_hash": collate.collation_hash(),
            "first_norm_key": chunk[0]["norm_key"] if chunk else None,
            "last_norm_key": chunk[-1]["norm_key"] if chunk else None,
            "entries": chunk,
        }
        # Session 5 S5-B2: write through shardio, which honours the .gz suffix.
        # A bare write_text() here is exactly what put plain JSON into 23 files
        # named shard-NNN.json.gz during the first D2 run.
        write_shard(dict_dir / shard_name(n), payload)
        n_shards += 1

    by_id = {e["id"]: e for e in ordered}
    index = {
        "schema": "coptic-reference/dict-index/1",
        "generated": GENERATED,
        "pipeline_version": pipeline_version,
        "collation_hash": collate.collation_hash(),
        "shard_size": SHARD_SIZE,
        "shard_count": n_shards,
        "entry_count": len(ordered),
        "letters": collate.alphabet_chars(),
        "shards": [
            {
                "shard": i // SHARD_SIZE,
                "file": f"dict/{shard_name(i // SHARD_SIZE)}",
                "count": len(ordered[i:i + SHARD_SIZE]),
                "first": ordered[i]["id"] if i < len(ordered) else None,
                "last": (ordered[i:i + SHARD_SIZE] or [{}])[-1].get("id"),
            }
            for i in range(0, len(ordered), SHARD_SIZE)
        ],
        "ids": [e["id"] for e in ordered],
    }
    (dict_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    # ── records.csv (v4 §6.2): one row per (entry, source) ────────────────────
    cols = ["record_id", "lemma", "norm_key", "pos", "dialects", "source_id",
            "source_record_id", "licence", "doi", "quality", "gloss_count",
            "example_count", "corpus_ref_count", "form_count",
            "pipeline_version", "generated"]
    rows = 0
    with (prov_dir / "records.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(cols)
        for e in ordered:
            rid_map = (e.get("provenance") or {}).get("record_ids") or {}
            for s in e["sources"]:
                w.writerow([
                    e["id"], e["lemma"], e["norm_key"],
                    ";".join(e["pos"]), ";".join(e["dialects"]),
                    s["id"], rid_map.get(s["id"], ""), s.get("licence", ""),
                    s.get("doi", ""), "",          # quality: source does not assert
                    len(e["glosses"]), len(e["examples"]),
                    len(e.get("corpus_refs") or []), len(e["forms"]),
                    pipeline_version, GENERATED,
                ])
                rows += 1
    record_rows = rows          # Session 5 S5-B4: `rows` was reused below and
                                # shadowed this counter, so the emit receipt
                                # printed an int that no longer existed.

    # ── LICENSES.csv (v4 §7.1): regenerated, so it cannot drift from the code ──
    from nc_guard import ALLOWED_SOURCES, NC_ONLY_SOURCES

    existing: dict[str, dict[str, str]] = {}
    old_csv = prov_dir / "LICENSES.csv"
    # Session 6 S6-B1. The NAME is `LICENSES.csv`, matching v4 §7.1 and every
    # reader: licence_guard.DEFAULT_LICENCES, obsidian.py, dry_run.py.
    #
    # Session 5 wrote the British spelling (no S) of the filename here, which
    # meant the generated
    # manifest was NOT the file any guard validated -- two licence files, and the
    # one under test was a stale copy. Worse, regenerating from an empty `prior`
    # map downgraded Manley2019's licence from CC-BY-NC-4.0 to UNVERIFIED, i.e.
    # losing a KNOWN licence, which is invariant 7 breaking in the most literal
    # way available. Caught in Session 6 D0, and it is the reason the Session 5
    # "filesystem fault" conclusion was wrong.
    #
    # The write is now atomic and verified: temp file, fsync, os.replace, then a
    # read-back that refuses to report success if a row or a provenance field did
    # not survive. That part stands on its own merits.
    existing: dict[str, dict] = {}
    try:
        # Session 7 C4: the shipped form is .csv.gz. Resolving both is what stops
        # this re-arming S6-B1 -- looking only for the plain name would silently
        # regenerate every originators/reference/notes field blank, losing licences
        # we already know.
        prior_csv = safeio.resolve_readable(old_csv)
        if prior_csv.is_file():
            with prior_csv.open(newline="", encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    existing[r["id"]] = r
    except OSError as e:
        print(f"[emit] LICENSES.csv: cannot read the previous version ({e}). "
              f"name/originators/reference/notes will be blank for rows that are "
              f"not in the allowlist. Restore the file if that matters.",
              file=sys.stderr)

    lcols = ["id", "licence", "name", "originators", "reference", "scope",
             "verified_on", "notes"]
    lic_rows: list[dict] = []
    for sid in sorted(ALLOWED_SOURCES):
        prior = existing.get(sid, {})
        lic_rows.append({
            "id": sid,
            # The allowlist is the authority for the licence, not the CSV.
            "licence": ALLOWED_SOURCES[sid],
            "name": prior.get("name", sid),
            "originators": prior.get("originators", ""),
            "reference": prior.get("reference", ""),
            "scope": prior.get("scope", "data/dist"),
            "verified_on": prior.get("verified_on", ""),
            "notes": prior.get("notes", ""),
        })
    for sid in sorted(NC_ONLY_SOURCES):
        prior = existing.get(sid, {})
        lic_rows.append({
            "id": sid,
            "licence": prior.get("licence", "UNVERIFIED"),
            "name": prior.get("name", sid),
            "originators": prior.get("originators", ""),
            "reference": prior.get("reference", ""),
            "scope": prior.get("scope", "content/nc only"),
            "verified_on": prior.get("verified_on", ""),
            "notes": prior.get("notes", ""),
        })

    # Session 6 D1: this ad-hoc version is now safeio.write_verified, which also
    # removes the .tmp on failure. Rule 3: a write that reports success is a claim.
    written = safeio.write_verified(
        old_csv,
        _render_licences(lic_rows, lcols),
        compress=False)
    print(f"[safeio] LICENSES.csv   {written:,} B written and read back", file=sys.stderr)
    summary_rows = len(lic_rows)
    summary = {
        "entries": len(ordered),
        "shards": n_shards,
        "shard_size": SHARD_SIZE,
        "record_rows": record_rows,
        "licence_rows": summary_rows,
    }
    return summary


def assert_coptic_order(entries: list[dict]) -> None:
    """Fail the build if the emitted order is not Coptic order.

    The cheapest possible guard against someone 'simplifying' the sort to
    sorted(). A codepoint sort is wrong in a way that is invisible in a diff and
    obvious to a reader looking for ϣ.
    """
    keys = [e["norm_key"] for e in entries]
    expected = collate.coptic_sorted(keys)
    if keys != expected:
        for i, (got, want) in enumerate(zip(keys, expected)):
            if got != want:
                raise SystemExit(
                    f"[emit] entries are NOT in Coptic collation order at index "
                    f"{i}: got {got!r}, Coptic order wants {want!r}. "
                    f"Use collate.coptic_sorted, never sorted()."
                )
    # And prove the difference is real, so this guard is not vacuous.
    demo = ["Ⲱ", "Ⲁ", "Ϣ"]
    if sorted(demo) == collate.coptic_sorted(demo):
        raise SystemExit("[emit] codepoint and Coptic order agree on the demo "
                         "string; the collation guard would be vacuous.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="shard the merged entries")
    ap.add_argument("--merged", type=pathlib.Path,
                    default=ROOT / "work" / "merged" / "entries.json")
    ap.add_argument("--dist", type=pathlib.Path, default=ROOT / "data" / "dist")
    ap.add_argument("--pipeline-version", default="3.0.0")
    args = ap.parse_args(argv)

    if not args.merged.is_file():
        print(f"[emit] {args.merged} not found. Run tools/merge/entries.py first.",
              file=sys.stderr)
        return 1

    blob = json.loads(args.merged.read_text(encoding="utf-8"))
    entries = blob["entries"] if isinstance(blob, dict) else blob

    ordered = collate.coptic_sorted(entries, key=lambda e: e["norm_key"])
    assert_coptic_order(ordered)

    summary = emit(ordered, args.dist, pipeline_version=args.pipeline_version)
    print(f"[emit] {summary['entries']} entries -> {summary['shards']} shard(s) "
          f"of <= {summary['shard_size']}")
    print(f"[emit] index.json      collation_hash "
          f"{collate.collation_hash()}")
    print(f"[emit] records.csv     {summary['record_rows']} row(s)")
    print(f"[emit] LICENSES.csv    {summary['licence_rows']} row(s)")
    print(f"[emit] dist            {args.dist}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
