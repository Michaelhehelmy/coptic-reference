# tools/tests/test_nc_guard.py — Session 4, correction Q2.
# LICENCE: project code, Apache-2.0.
#
# The rule: every id on ALLOWED_SOURCES must be a source we can actually fetch
# and verify. An allowlist entry for something unobtainable asserts a permission
# nobody can exercise, which is the fail-open shape the allowlist exists to
# prevent.
#
# WHY THIS TEST EXISTS, in the project's own history: UD_Bohairic sat on the
# allowlist for three sessions while its treebank returned HTTP 404. Nobody
# noticed, because nothing asked whether the allowlist matched reality. The same
# failure produced the UD_Coptic licence bug in Session 1 — a licence recorded
# from memory for a treebank that had never been fetched.
#
# IMPLEMENTATION NOTE, and a deviation from the literal instruction. Q2 asks that
# every allowlisted id have a non-empty url and sha256. Implemented literally that
# fails for the four PROJECT-AUTHORED sources (ProjectRebuild, TranslitTable,
# G2PTable, MERGE), which we write ourselves and therefore have no upstream URL
# to give. Inventing one would be provenance from memory — the exact thing
# invariant 7 exists to prevent. So the rule is: non-empty url AND sha256, unless
# the lock entry declares `authored = true` or `ingested = false`, each of which
# must be explicit. See DECISIONS.md S4-A1.
from __future__ import annotations

import pathlib
import sys
import tomllib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "validate"))

import nc_guard  # noqa: E402

LOCK = ROOT / "tools" / "sources.lock"

#: Allowlist id -> sources.lock key. Not 1:1: the lock is keyed by FETCH TARGET,
#: the allowlist by CITATION ID as it appears in an entry. Scriptorium_TT and
#: Scriptorium_TEI are two citation ids for one fetched corpus.
LOCK_KEY: dict[str, str] = {
    "CCL": "ccl",
    "CDO": "cdo",
    "Kaikki": "kaikki",
    "CDO-API": "cdo",
    "Scriptorium_TT": "corpora",
    "Scriptorium_TEI": "corpora",
    "UD_Coptic": "ud_coptic",
    "Crum": "crum",
    "TLA": "tla",
    "ProjectRebuild": "project_rebuild",
    "TranslitTable": "translit_table",
    "G2PTable": "g2p_table",
    "MERGE": "merge_pseudo",
}


@pytest.fixture(scope="module")
def lock() -> dict:
    with LOCK.open("rb") as fh:
        return tomllib.load(fh)


def test_every_allowlisted_id_has_a_lock_entry(lock):
    """First half of Q2's rule, and the part that would have caught
    UD_Bohairic: an allowlist id with no lock entry at all."""
    missing = [sid for sid in nc_guard.ALLOWED_SOURCES if sid not in LOCK_KEY]
    assert not missing, (
        f"allowlisted id(s) with no sources.lock entry: {missing}. "
        f"Either pin the source or remove it from ALLOWED_SOURCES — an "
        f"allowlist entry for something unobtainable is a permission nobody can "
        f"exercise."
    )


def test_lock_entries_referenced_by_the_allowlist_all_exist(lock):
    for sid, key in sorted(LOCK_KEY.items()):
        if sid in nc_guard.ALLOWED_SOURCES:
            assert key in lock, f"{sid} maps to [{key}], which is not in the lock"


def test_every_allowlisted_id_is_fetchable_or_explicitly_exempt(lock):
    """Q2's rule, with the two explicit exemptions.

    Non-empty url AND sha256, unless the lock entry declares `authored = true`
    (we wrote it) or `ingested = false` (declared, deliberately not ingested).
    """
    violations: list[str] = []
    exempt: list[str] = []
    for sid in sorted(nc_guard.ALLOWED_SOURCES):
        key = LOCK_KEY[sid]
        spec = lock.get(key, {})
        if spec.get("authored") is True:
            exempt.append(f"{sid} (authored)")
            continue
        if spec.get("ingested") is False:
            exempt.append(f"{sid} (declared not-ingested)")
            continue
        if spec.get("pin_impossible"):
            # An external source that genuinely cannot be pinned, with the reason
            # recorded in the lock. Crum is a 1925 print book; TLA is a live web
            # service. Blank-and-failing would train people to ignore the test;
            # a bare exemption would hide the gap. The reason is the point.
            exempt.append(f"{sid} (pin impossible: {spec['pin_impossible']})")
            continue
        if spec.get("pin_method") == "git-commit-sha":
            if not str(spec.get("commit", "")).strip():
                violations.append(f"{sid} -> [{key}]: pin_method says git-commit-sha but commit is empty")
            exempt.append(f"{sid} (pinned by commit {spec.get('commit','')[:12]})")
            continue
        url = str(spec.get("url", "")).strip()
        sha = str(spec.get("sha256", "")).strip()
        # Either a real url+sha256 pair, OR a documented alternative pin.
        if not url or not sha:
            violations.append(
                f"{sid} -> [{key}]: url={url!r} sha256={sha!r}. "
                f"Pin it, mark it authored, or mark ingested=false."
            )
    print(f"\n  exempt (explicit): {', '.join(exempt)}")
    print(f"  UNPINNED EXTERNAL: {len(violations)}")
    for v in violations:
        print(f"    {v}")
    assert not violations, (
        f"{len(violations)} allowlisted external source(s) have no pinned "
        f"url+sha256:\n  " + "\n  ".join(violations)
    )


def test_ud_bohairic_is_not_allowlisted():
    """Correction Q2, pinned so it cannot drift back.

    Its treebank is HTTP 404. It is RESERVED in the lock, not allowlisted.
    """
    assert "UD_Bohairic" not in nc_guard.ALLOWED_SOURCES


def test_ud_bohairic_reservation_is_explicit_in_the_lock(lock):
    spec = lock.get("ud_bohairic", {})
    assert spec, "the reserved entry must stay in the lock so re-adding is easy"
    assert spec.get("allowlisted") is False
    assert spec.get("sha256", "") == "", "nothing was fetched, so nothing is pinned"
    assert "404" in str(spec.get("http_status", ""))


def test_cdo_is_declared_not_ingested(lock):
    """Correction Q3: CDO ships in v1 without being ingested, and says so."""
    spec = lock.get("cdo", {})
    assert spec.get("ingested") is False
    assert spec.get("ingest_blocker"), "a not-ingested source must record why"


def test_no_allowlisted_id_is_in_the_nc_contra_list():
    overlap = set(nc_guard.ALLOWED_SOURCES) & nc_guard.NC_ONLY_SOURCES
    assert not overlap, sorted(overlap)


def test_every_allowlisted_licence_is_a_real_spdx_id():
    """Invariant 7, and the Session 1 UD_Coptic bug in general form: a licence
    invented from memory is a guess wearing a provenance label."""
    allowed = {"CC-BY-SA-4.0", "CC-BY-4.0", "CC-BY-SA-4.0 OR GFDL", "PD"}
    bad = {sid: lic for sid, lic in nc_guard.ALLOWED_SOURCES.items()
           if lic not in allowed}
    assert not bad, f"unrecognised licence value(s): {bad}"


def test_no_allowlisted_licence_is_non_commercial():
    for sid, lic in nc_guard.ALLOWED_SOURCES.items():
        assert "NC" not in lic.upper(), f"{sid} is allowlisted with {lic}"


def test_the_allowlist_still_covers_every_source_the_dataset_uses():
    """If the dataset cites a source the allowlist dropped, that is a merge bug
    and it must fail here rather than at read time."""
    dict_dir = ROOT / "data" / "dist" / "dict"
    if not dict_dir.is_dir():
        pytest.skip("no baked shards")
    import json
    used: set[str] = set()
    for shard in dict_dir.glob("shard-*.json"):
        for e in json.loads(shard.read_text(encoding="utf-8")).get("entries", []):
            for s in e.get("sources", []):
                used.add(s.get("id", ""))
            for a in e.get("attributions", []):
                used.add(a.get("source", ""))
    unknown = {u for u in used if u and u not in nc_guard.ALLOWED_SOURCES}
    assert not unknown, f"the shipped dataset cites non-allowlisted source(s): {unknown}"
