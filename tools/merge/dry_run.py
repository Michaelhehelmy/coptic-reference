#!/usr/bin/env python3
"""tools/merge/dry_run.py — prove the gates judge correctly BEFORE real data.

Session 2's whole purpose. Invariant 5 currently had a schema and no
enforcement; this harness is the evidence that the enforcement added in
Session 2 actually rejects bad input, rather than merely existing.

WHAT THIS IS NOT. This is **not** the merge pipeline. It is a stub-shaped
merge over three hand-written records whose only job is to produce output of
the right SHAPE so the gates have something to judge. The real merge arrives in
Session 3 with real sources. Nothing here reads a corpus, and nothing here
should be extended into something that does — see DECISIONS.md S2-A4.

The five stages, and which gate catches what:

    1. load stub records            (source: CCL)
    2. merge -> unified entries     validated against schema/entry.schema.json
    3. entry schema validation      catches a malformed record
    4. nc_guard                     catches NC / non-allowlisted provenance
    5. licence_guard                catches undocumented licences

Stages 3-5 are the point. Stage 2 only has to be shape-correct.

Usage:
    python3 tools/merge/dry_run.py              # clean run, expect PASS
    python3 tools/merge/dry_run.py --inject nc  # expect FAIL at stage 4
    python3 tools/merge/dry_run.py --inject unknown-source
    python3 tools/merge/dry_run.py --inject malformed
    python3 tools/merge/dry_run.py --inject undocumented

Output is written to a temporary directory, never to data/dist. A harness that
wrote to the real dataset would be one bad invocation away from shipping the
violation it exists to catch.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tools" / "validate"))
sys.path.insert(0, str(ROOT / "tools"))

from jsonschema import Draft202012Validator, FormatChecker  # noqa: E402

import licence_guard  # noqa: E402
import safeio  # noqa: E402
import shardio  # noqa: E402
import nc_guard  # noqa: E402

ENTRY_SCHEMA = ROOT / "schema" / "entry.schema.json"

# ── 1. the stub records ──────────────────────────────────────────────────────
# Shaped like Kaikki JSONL records, because that is what Session 3 will feed
# the real merge. Deliberately tiny: one clean source (CCL), plus whatever the
# --inject flag adds.
STUB_RECORDS: list[dict] = [
    {
        "word": "ⲧⲉⲛⲟⲩ",
        "pos": "adv",
        "lang_code": "cop",
        "source": "CCL",
        "record_id": "STUB-C5047",
        "senses": [{"gloss": "now, at present", "pos": "adv", "source": "CCL"}],
        "translit": {"bohairic": "tenoou", "sahidic": "tenou"},
        "dialects": ["B", "S"],
    },
    {
        "word": "ⲧⲉⲛⲟⲩ",
        "pos": "adv",
        "lang_code": "cop",
        "source": "CCL",
        "record_id": "STUB-C5048",
        "senses": [{"gloss": "at the present time", "pos": "adv", "source": "CCL"}],
        "translit": {"bohairic": "tenoou", "sahidic": "tenou"},
        "dialects": ["B", "S"],
    },
    {
        "word": "ⲁⲛ",
        "pos": "pron",
        "lang_code": "cop",
        "source": "CCL",
        "record_id": "STUB-C0001",
        "senses": [{"gloss": "without, not", "pos": "pron", "source": "CCL"}],
        "translit": {"bohairic": "an", "sahidic": "an"},
        "dialects": ["B", "S"],
    },
]


NC_ATTRIBUTION_ONLY: dict = {
    # Applied by merge() when --inject nc-in-attribution is used.
    #
    # The licence is deliberately a LIE. Labelling the row "CC-BY-NC-4.0" gets
    # it rejected by the attributions[].licence enum at stage 3, which proves
    # nothing: the schema caught a source that had already declared itself.
    #
    # The realistic and dangerous case is NC provenance with a PERMITTED licence
    # string — a scrape that kept the CC BY-SA header while carrying Manley text,
    # or an upstream that relicensed without updating us. Against that, every
    # schema check passes:
    #     - attributions[].licence  "CC-BY-SA-4.0" is in the enum
    #     - attributions[].source   is a free string per v4 §8.2
    # and the ONLY thing that can catch it is nc_guard, because only nc_guard
    # knows Manley2019 is on the contra-list. That is the whole reason this gate
    # is independent of the schema rather than folded into it.
    "source": "Manley2019",
    "licence": "CC-BY-SA-4.0",
    "changes": "gloss reworded from a CC BY-NC textbook",
}


def inject(records: list[dict], kind: str) -> list[dict]:
    """Return a copy of the stub records with one deliberate violation added."""
    out = [dict(r) for r in records]
    if kind == "nc":
        # Provenance from a CC BY-NC textbook. The single most consequential
        # mistake this project can make.
        out[0]["source"] = "Manley2019"
        out[0]["senses"] = [{"gloss": "STOLEN GLOSS", "pos": "adv",
                             "source": "Manley2019"}]
    elif kind == "unknown-source":
        # A source nobody has reviewed. Fail-closed must reject it even though
        # it is not on the NC list — this is the whole point of the allowlist.
        out[1]["source"] = "SomeCorpusWeJustFound"
        out[1]["senses"] = [{"gloss": "unsourced gloss", "pos": "adv",
                             "source": "SomeCorpusWeJustFound"}]
    elif kind == "malformed":
        # Structurally invalid: strip the required gloss list.
        out[2]["senses"] = []
    elif kind in ("none", "undocumented", "nc-in-attribution"):
        # `undocumented` edits the manifest in run(), not the records.
        # `nc-in-attribution` is applied below.
        pass
    else:
        raise SystemExit(f"unknown --inject kind: {kind!r}")
    return out


# ── 2. the stub merge ────────────────────────────────────────────────────────
def merge(records: list[dict], *, nc_in_attribution: bool = False) -> list[dict]:
    """Group stub records by lemma into unified entries.

    Shape-correct only. Real sense-ordering, dialect-splitting, and
    cross-source deduplication are Session 3 work.
    """
    by_lemma: dict[str, list[dict]] = {}
    for r in records:
        by_lemma.setdefault(r["word"], []).append(r)

    entries: list[dict] = []
    for lemma, group in by_lemma.items():
        sources = sorted({r["source"] for r in group})
        ids = sorted({r["record_id"] for r in group})
        glosses: list[dict] = []
        seen: set[str] = set()
        for r in group:
            for s in r["senses"]:
                key = s["gloss"].strip().lower()
                if key in seen:
                    continue
                seen.add(key)
                glosses.append({
                    "text": s["gloss"],
                    "pos": s.get("pos"),
                    "lang": "en",
                    "source": s["source"],
                    "rank": len(glosses) + 1,
                })

        entries.append({
            "id": f"DRY-{abs(hash(lemma)) % 100000:05d}",
            "lemma": lemma,
            "display": lemma,
            "norm_key": lemma,
            "translit": group[0].get("translit", {}),
            "dialects": sorted({d for r in group for d in r.get("dialects", [])}),
            "pos": sorted({r["pos"] for r in group if r.get("pos")}),
            "glosses": glosses,
            "examples": [],
            "corpus_refs": [],
            "related_entries": [],
            "forms": [],
            "media": [],
            "sources": [{"id": sid,
                         "licence": nc_guard.ALLOWED_SOURCES.get(sid, "UNKNOWN")}
                        for sid in sources],
            "attributions": [{
                "field": "glosses",
                "source": sid,
                "licence": nc_guard.ALLOWED_SOURCES.get(sid, "UNKNOWN"),
                "changes": f"merged {len(group)} stub record(s)",
            } for sid in sources] + ([{
                "field": "glosses",
                **NC_ATTRIBUTION_ONLY,
            }] if nc_in_attribution else []),
            "provenance": {
                "record_ids": {"CCL": ", ".join(ids)},
                "pipeline_version": "dry-run-0",
                "generated": "2026-10-04T00:00:00Z",
                "collation_hash": "b7b49af6e144ef87",
            },
        })
    return entries


# ── stages 3-5 ───────────────────────────────────────────────────────────────
def validate_schema(dist: pathlib.Path) -> list[str]:
    schema = json.loads(ENTRY_SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors: list[str] = []
    for shard in sorted(dist.rglob("*.json")):
        blob = json.loads(shard.read_text(encoding="utf-8"))
        for entry in blob.get("entries", []):
            for err in validator.iter_errors(entry):
                loc = "/".join(str(x) for x in err.path) or "(root)"
                errors.append(f"{shard.name} entry {entry.get('id')}: "
                              f"{loc}: {err.message}")
    return errors


def load_real(dist: pathlib.Path) -> list[dict]:
    """Read the real shipped shards. This is what the gates must judge."""
    # Session 5 G1: this returned [] for an empty dict dir and the run printed
    # PASS. require=True now fails instead -- an absent dataset is not a clean one.
    return shardio.load_entries(dist / "dict", require=True)


def run(inject_kind: str, real: bool = False, dist: pathlib.Path | None = None) -> int:
    label = "clean run" if inject_kind == "none" else f"injected violation: {inject_kind}"
    if real:
        label += " (REAL shipped data)"
    print(f"=== dry_run.py — {label} ===")

    if real:
        entries = load_real(dist or pathlib.Path("data/dist"))
        records = []
        print(f"[1] loaded      {len(entries)} entries from the real shards")
        if inject_kind != "none":
            # The injections target a record; on real data the equivalent is to
            # corrupt a COPY of the first entry. The point is to prove the gate
            # fires on shipped-shaped data, so the shape must stay real.
            victim = json.loads(json.dumps(entries[0]))
            victim["id"] = "INJECTED-1"
            if inject_kind == "nc":
                victim["sources"] = [{"id": "Manley2019", "licence": "CC-BY-NC-4.0"}]
                victim["attributions"] = [{"field": "glosses", "source": "Manley2019",
                                           "licence": "CC-BY-NC-4.0", "changes": "none"}]
            elif inject_kind == "unknown-source":
                victim["sources"] = [{"id": "MysterySource", "licence": "CC-BY-SA-4.0"}]
                victim["attributions"] = [{"field": "glosses", "source": "MysterySource",
                                           "licence": "CC-BY-SA-4.0", "changes": "none"}]
            elif inject_kind == "malformed":
                victim["glosses"] = []
            elif inject_kind == "empty-attributions":
                victim["attributions"] = []
            elif inject_kind == "nc-in-attribution":
                victim["attributions"] = list(victim["attributions"]) + [{
                    "field": "glosses", "source": "Manley2019",
                    "licence": "CC-BY-SA-4.0", "changes": "injected",
                }]
            entries = [victim] + entries[1:]
            print(f"[1] injected    violation {inject_kind!r} into entry 0")
    else:
        records = inject(STUB_RECORDS, inject_kind)
        entries = merge(records, nc_in_attribution=(inject_kind == "nc-in-attribution"))
        print(f"[1] loaded      {len(records)} stub records (sources: "
              f"{sorted({r['source'] for r in records})})")
    print(f"[1] loaded      {len(records)} stub records "
          f"(sources: {sorted({r['source'] for r in records})})")
    print(f"[2] merged      {len(entries)} entries")

    work = pathlib.Path(tempfile.mkdtemp(prefix="coptic-dryrun-"))
    try:
        dist = work / "dist"
        (dist / "dict").mkdir(parents=True)
        (dist / "provenance").mkdir(parents=True)
        # The guards need the real manifest; copy it so the harness is hermetic
        # and cannot be affected by an unrelated working-tree change.
        # Session 7 C4: keep the SUFFIX. Copying gzip bytes to a name without
        # `.gz` is the S5-B2 mislabelling class -- the file exists, the size is
        # plausible, and every reader that assumes the extension is right then
        # fails on a magic byte. Same bug shape, different extension.
        src_manifest = safeio.resolve_readable(
            ROOT / "data" / "dist" / "provenance" / "LICENSES.csv")
        manifest = dist / "provenance" / src_manifest.name
        shutil.copy(src_manifest, manifest)
        if inject_kind == "undocumented":
            # An allowlisted source whose licence was never documented. The
            # entry itself is perfectly clean and allowlisted — only the
            # provenance record is missing, which is exactly the drift this
            # gate exists to catch.
            # Session 7 C4: the copy may be .csv.gz, so read and write through
            # the resolver rather than assuming plain text.
            text = safeio.read_maybe_gzip(manifest).decode("utf-8")
            kept = [ln for ln in text.split("\n") if not ln.startswith("CDO-API,")]
            safeio.write_text_verified(manifest, "\n".join(kept))
            print("[2] injected   dropped the CDO-API row from the temp manifest")
        (dist / "dict" / "shard-a1.json").write_text(
            json.dumps({"shard": "a1", "entries": entries},
                       indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[2] wrote      {dist.relative_to(work)}/dict/shard-a1.json "
              f"(temporary — data/dist untouched)")

        print("[3] schema      validating against schema/entry.schema.json ...")
        errs = validate_schema(dist)
        if errs:
            for e in errs[:10]:
                print(f"    FAIL {e}")
            return _fail(3, f"entry schema rejected the output "
                            f"({len(errs)} error(s))")
        print(f"    OK   {len(entries)} entries valid")

        print("[4] nc_guard    fail-closed allowlist ...")
        try:
            nc_guard.check(dist, ROOT / "content")
        except SystemExit:
            print("    -> caught by nc_guard (stage 4)")
            return _fail(4, "nc_guard rejected the output — provenance is not "
                            "permitted inside data/dist")
        print("    OK   provenance allowlisted")

        print("[5] licence_guard  every source has a verdict ...")
        try:
            licence_guard.check(dist, manifest)
        except SystemExit:
            print("    -> caught by licence_guard (stage 5)")
            return _fail(5, "licence_guard rejected the output — a source has "
                            "no determined licence")
        print("    OK   every source documented")

        print()
        print("PASS — merge output is schema-valid, allowlisted, and licensed.")
        print("      The gates accept good input and (per --inject) reject bad.")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _fail(stage: int, reason: str) -> int:
    print()
    print(f"FAIL at stage {stage} — {reason}")
    print("      This is the harness working. A clean run should PASS.")
    return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="prove the licence gates judge correctly before real data")
    ap.add_argument("--real", action="store_true",
                    help="use the REAL merged dataset (data/dist/dict/shard-*.json) "
                         "instead of the stub records. Session 3 D6: the harness "
                         "must judge the shipped data, not only synthetic fixtures.")
    ap.add_argument("--inject", default="none",
                    choices=["none", "nc", "unknown-source", "malformed",
                             "undocumented", "nc-in-attribution",
                             "empty-attributions"],
                    help="add one deliberate violation (default: none). "
                         "malformed fails stage 3; nc and unknown-source fail "
                         "stage 3 via the schema enum (defence in depth); "
                         "nc-in-attribution reaches stage 4 because "
                         "attributions[].source is a free string; "
                         "undocumented fails stage 5.")
    ap.add_argument("--dist", default="data/dist", type=pathlib.Path)
    args = ap.parse_args(argv)
    return run(args.inject, real=args.real, dist=args.dist)


if __name__ == "__main__":
    raise SystemExit(main())
