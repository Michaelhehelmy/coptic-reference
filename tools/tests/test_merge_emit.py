# tools/tests/test_merge_emit.py — Session 3, D4 + D5.
# LICENCE: project code, Apache-2.0.
#
# v4 §2.4's precedence rules are the load-bearing logic of the whole dataset, and
# they are stated as an ordered list, which is exactly the kind of thing that
# gets "simplified" into a plain concatenation by a later maintainer. Each rule
# gets a test that fails if the rule is dropped.
#
# Fixtures use Coptic built from codepoints, for the reason PLAN-ERRATA records
# under "Do not hand-type the alphabet" — and because a hand-typed literal in
# this file already produced one wrong assertion.
from __future__ import annotations

import csv
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "merge"))
sys.path.insert(0, str(ROOT / "tools" / "emit"))

import collate  # noqa: E402
import entries as merge  # noqa: E402
from cli import assert_coptic_order, emit  # noqa: E402

TENOU = chr(0x2CA7) + chr(0x2C89) + chr(0x2C9B) + chr(0x238F) + chr(0x2CA9)
AN = chr(0x2C81) + chr(0x2C9B)
NAI = chr(0x2C9B) + chr(0x2C81) + chr(0x2C93)
SHIN_CAP = chr(0x03E2) + chr(0x2C81) + chr(0x2C93)   # capital shin + ai
SHIN_SML = chr(0x03E3) + chr(0x2C81) + chr(0x2C93)   # small  shin + ai


def rec(source: str, lemma: str, **kw) -> dict:
    base = {
        "lemma": lemma, "display": lemma, "pos": [],
        "dialects": [], "glosses": [], "etymology": None, "forms": [],
        "examples": [], "variant": False, "tla_id": None,
        "sources": [{"id": source,
                     "licence": {"CCL": "CC-BY-SA-4.0",
                                 "CDO": "CC-BY-SA-4.0",
                                 "Kaikki": "CC-BY-SA-4.0 OR GFDL"}[source],
                     "doi": "10.1/x"}],
        "provenance": {"record_id": f"{source}-1"},
    }
    base.update(kw)
    return base


def gloss(text: str, source: str, rank: int = 1) -> dict:
    return {"text": text, "lang": "en", "source": source, "rank": rank}


# ── rule 1: join on norm_key ─────────────────────────────────────────────────

def test_join_is_on_norm_key_not_the_raw_string():
    """A combining mark must not create a second entry for the same word."""
    marked = TENOU + chr(0x0300)          # tenou with a grave
    group = merge.merge_group([rec("CCL", TENOU), rec("Kaikki", marked)])
    assert group["norm_key"] == merge.norm_key(TENOU)
    out = list(merge.merge_all({"a": [rec("CCL", TENOU)],
                                "b": [rec("Kaikki", marked)]}))
    assert len(out) == 1


def test_norm_key_uses_collates_own_folding():
    """The join key and the sort key must be the same function, or entries merge
    in one order and shard in another (v4 §1.3 defect B3)."""
    assert merge.norm_key(TENOU) == collate.canon_for_sort(TENOU)
    assert merge.norm_key(SHIN_CAP) == collate.canon_for_sort(SHIN_CAP)
    assert merge.norm_key(SHIN_CAP) == merge.norm_key(SHIN_SML)


def test_greek_capital_and_small_join_together():
    """Regression guard for S2-B10: a capital lemma and its small form are one
    word and must not become two entries."""
    out = list(merge.merge_all({
        "a": [rec("CCL", SHIN_CAP)],
        "b": [rec("Kaikki", SHIN_SML)],
    }))
    assert len(out) == 1
    assert out[0]["sources"] and len(out[0]["sources"]) == 2


# ── rule 2: senses CCL > CDO > Kaikki ────────────────────────────────────────

def test_sense_precedence_orders_glosses():
    """CCL's gloss leads, then CDO, then Kaikki."""
    g = merge.merge_group([
        rec("Kaikki", TENOU, glosses=[gloss("kaikki gloss", "Kaikki")]),
        rec("CDO", TENOU, glosses=[gloss("cdo gloss", "CDO")]),
        rec("CCL", TENOU, glosses=[gloss("ccl gloss", "CCL")]),
    ])
    assert [x["source"] for x in g["glosses"]] == ["CCL", "CDO", "Kaikki"]


def test_unknown_source_sorts_last_but_is_kept():
    r = rec("CDO", TENOU, glosses=[gloss("cdo", "CDO")])
    r["sources"][0]["id"] = "Later"
    r["sources"][0]["licence"] = "CC-BY-SA-4.0"
    g = merge.merge_group([rec("CCL", TENOU, glosses=[gloss("ccl", "CCL")]), r])
    assert [x["source"] for x in g["glosses"]] == ["CCL", "Later"]


# ── rule 3: dialects, union ──────────────────────────────────────────────────

def test_dialects_are_a_union_never_an_overwrite():
    """Union across sources, and neither source's flags are discarded."""
    g = merge.merge_group([
        rec("CCL", TENOU, dialects=["S"]),
        rec("Kaikki", TENOU, dialects=["B"]),
    ])
    assert g["dialects"] == ["B", "S"], "sorted union of both sources"


def test_dialect_union_drops_n_when_a_specific_dialect_exists():
    """Correction Q1(a). N means "a source was uncertain". If any source placed
    the lemma for real, that placement beats the uncertainty, so N is dropped
    rather than unioned alongside — otherwise a known-Sahidic entry would read as
    "S and possibly something unknown", which is not what the data says."""
    g = merge.merge_group([
        rec("CCL", TENOU, dialects=["S"]),
        rec("Kaikki", TENOU, dialects=["B", "N"]),
    ])
    assert g["dialects"] == ["B", "S"], "N is dropped when a real dialect exists"


def test_dialect_union_keeps_n_when_it_is_all_there_is():
    g = merge.merge_group([
        rec("CCL", TENOU, dialects=["N"]),
        rec("Kaikki", TENOU, dialects=["N"]),
    ])
    assert g["dialects"] == ["N"], "nothing specific recorded anywhere -> N stands"


def test_measured_effect_of_the_union_rule():
    """All 112 CCL entries recording "?" also record a real dialect, so all 112
    lose N. Asserted so a regression in the rule is visible in the count."""
    import json as _json
    from collections import Counter
    if not (ROOT / "data" / "dict").is_dir():
        pytest.skip("no baked shards")
    n_with_specific = n_only = 0
    for shard in (ROOT / "data" / "dict").glob("shard-*.json"):
        for e in _shardio.read_shard(shard)["entries"]:
            d = e["dialects"]
            if d == ["N"]:
                n_only += 1
            else:
                n_with_specific += 1
    assert n_only == 1631, f"{n_only} entries have no dialect at all"
    assert "N" not in {x for d in ["A"] for x in d}, "sanity"


def test_no_dialect_evidence_yields_N_undetermined():
    """N is the schema's existing 'undetermined' flag. An empty list fails
    minItems; N is a true statement, not a filler."""
    g = merge.merge_group([rec("Kaikki", TENOU)])
    assert g["dialects"] == ["N"]


# ── rule 4: etymology Kaikki > CCL ──────────────────────────────────────────

def test_etymology_precedence_is_kaikki_over_ccl():
    g = merge.merge_group([
        rec("CCL", TENOU, etymology={"text": "from CCL", "source": "CCL", "chain": []}),
        rec("Kaikki", TENOU, etymology={"text": "from Kaikki", "source": "Kaikki",
                                        "chain": [], "templates": ["x"]}),
    ])
    assert g["etymology"]["text"] == "from Kaikki"
    assert "templates" not in g["etymology"], "extractor internals are dropped"


def test_etymology_falls_back_to_ccl():
    g = merge.merge_group([
        rec("CCL", TENOU, etymology={"text": "from CCL", "source": "CCL", "chain": []}),
    ])
    assert g["etymology"]["text"] == "from CCL"


# ── rule 5 + 7: union, exact dedupe, never fuse ──────────────────────────────

def test_identical_glosses_from_two_sources_are_deduped_exactly():
    """Rule 5. Two sources saying the same thing is one gloss stated twice."""
    g = merge.merge_group([
        rec("CCL", TENOU, glosses=[gloss("now, at present", "CCL")]),
        rec("Kaikki", TENOU, glosses=[gloss("now, at present", "Kaikki")]),
    ])
    assert len(g["glosses"]) == 1
    assert g["glosses"][0]["source"] == "CCL", "the higher-precedence source wins"


def test_near_matching_glosses_are_never_fused():
    """Rule 7, and the distinction that makes rules 5 and 7 compatible.

    "now" and "at the present time" are two glosses, not one. Fusing them would
    destroy the evidence that two sources describe the same sense in different
    words — which is the normal case and the reason attribution exists.
    """
    g = merge.merge_group([
        rec("CCL", TENOU, glosses=[gloss("now", "CCL")]),
        rec("Kaikki", TENOU, glosses=[gloss("at the present time", "Kaikki")]),
    ])
    assert len(g["glosses"]) == 2
    assert {x["source"] for x in g["glosses"]} == {"CCL", "Kaikki"}


def test_case_only_difference_counts_as_exact():
    g = merge.merge_group([
        rec("CCL", TENOU, glosses=[gloss("Now", "CCL")]),
        rec("Kaikki", TENOU, glosses=[gloss("now", "Kaikki")]),
    ])
    assert len(g["glosses"]) == 1


def test_gloss_ranks_are_dense_and_ordered():
    g = merge.merge_group([
        rec("CCL", TENOU, glosses=[gloss("a", "CCL"), gloss("b", "CCL")]),
        rec("Kaikki", TENOU, glosses=[gloss("c", "Kaikki")]),
    ])
    assert [x["rank"] for x in g["glosses"]] == [1, 2, 3]


def test_unknown_gloss_pos_is_omitted_not_null():
    """The schema types pos as string and does not require it. Absence says "not
    recorded"; null says "recorded as nothing"."""
    r = rec("Kaikki", TENOU, glosses=[{"text": "x", "lang": "en", "source": "Kaikki",
                                       "pos": None, "rank": 1}])
    g = merge.merge_group([r])
    assert "pos" not in g["glosses"][0]


# ── rule 6: examples CDO > Kaikki > CCL ─────────────────────────────────────

def test_example_precedence():
    mk = lambda s: [{"coptic": "x " + s, "translation": "t " + s,
                     "quality": "automatic", "source": s}]
    g = merge.merge_group([
        rec("CCL", TENOU, examples=mk("CCL")),
        rec("Kaikki", TENOU, examples=mk("Kaikki")),
        rec("CDO", TENOU, examples=mk("CDO")),
    ])
    assert [e["source"] for e in g["examples"]] == ["CDO", "Kaikki", "CCL"]


def test_example_without_coptic_is_dropped():
    g = merge.merge_group([
        rec("CDO", TENOU, examples=[{"coptic": "", "translation": "english only",
                                     "source": "CDO"}]),
    ])
    assert g["examples"] == []


# ── forms ────────────────────────────────────────────────────────────────────

def test_form_kind_survives_the_merge():
    """romanization must stay distinguishable from inflection, or `xalkin` is
    displayed as an inflected form of the headword."""
    r = rec("Kaikki", TENOU, forms=[{"form": "tenou", "kind": "romanization"},
                                    {"form": TENOU, "kind": "inflection"}])
    g = merge.merge_group([r])
    kinds = {f["form"]: f.get("kind") for f in g["forms"]}
    assert kinds == {"tenou": "romanization"}


def test_the_lemma_is_not_listed_as_its_own_form():
    r = rec("Kaikki", TENOU, forms=[{"form": TENOU, "kind": "inflection"}])
    assert merge.merge_group([r])["forms"] == []


# ── id and provenance ────────────────────────────────────────────────────────

def test_tla_id_wins_over_a_hash():
    g = merge.merge_group([rec("CCL", TENOU, tla_id="C5047")])
    assert g["id"] == "C5047"


def test_hash_id_is_stable_across_sources():
    a = merge.merge_group([rec("CCL", TENOU)])
    b = merge.merge_group([rec("CCL", TENOU + chr(0x0300))])
    assert a["id"] == b["id"], "the id must not depend on which source spelled it"


def test_provenance_record_ids_map_source_to_record():
    g = merge.merge_group([rec("CCL", TENOU), rec("Kaikki", TENOU)])
    assert g["provenance"]["record_ids"] == {"CCL": "CCL-1", "Kaikki": "Kaikki-1"}


def test_every_entry_gets_at_least_one_attribution():
    g = merge.merge_group([rec("CCL", TENOU), rec("Kaikki", TENOU)])
    assert len(g["attributions"]) >= 1
    assert any(a["source"] == "MERGE" for a in g["attributions"])


def test_attribution_changes_uses_a_controlled_vocabulary():
    """v4 §8.2 requires it. Free text would make "what did we actually do?"
    unanswerable across 11,369 entries."""
    allowed = {"none", "deduplicated", "sense order reordered",
               "diacritics stripped", "merged from", "dialect union"}
    g = merge.merge_group([rec("CCL", TENOU), rec("Kaikki", TENOU)])
    for a in g["attributions"]:
        for part in a["changes"].split("; "):
            assert any(part.startswith(w) for w in allowed), part


# ── D5: emit ─────────────────────────────────────────────────────────────────

def test_emit_writes_shards_index_and_provenance(tmp_path):
    entries = list(merge.merge_all({"CCL": [rec("CCL", TENOU), rec("CCL", AN)]}))
    s = emit(entries, tmp_path, pipeline_version="test")
    assert s["shards"] == 1
    # Session 5 D2: the shipped shard form is gzipped. The uncompressed .json is
    # NOT kept alongside it (C2), so this asserts the .gz and, separately, that
    # no .json was left behind.
    assert (tmp_path / "dict" / "shard-000.json.gz").is_file()
    assert not list((tmp_path / "dict").glob("shard-*.json")), \
        "C2: ship .json.gz only; an uncompressed copy doubles the shipped bytes"
    import gzip as _gz
    with _gz.open(tmp_path / "dict" / "shard-000.json.gz", "rb") as fh:
        assert json.loads(fh.read())["entries"]
    idx = json.loads((tmp_path / "dict" / "index.json").read_text(encoding="utf-8"))  # noqa: E501
    assert idx["collation_hash"] == collate.collation_hash()
    assert idx["entry_count"] == 2
    assert idx["shard_size"] == 500
    with (tmp_path / "provenance" / "records.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["source_id"] == "CCL"
    assert rows[0]["norm_key"] == merge.norm_key(rows[0]["lemma"])


def test_emit_index_carries_the_collation_pin(tmp_path):
    """If someone changes the alphabet without re-baking, this hash stops
    matching tools/collate.py and collation_guard.py fails. That is the v4 §1.3
    review gate, and it only works if the hash travels with the data."""
    entries = list(merge.merge_all({"CCL": [rec("CCL", TENOU)]}))
    emit(entries, tmp_path, pipeline_version="test")
    idx = json.loads((tmp_path / "dict" / "index.json").read_text(encoding="utf-8"))  # noqa: E501
    assert idx["collation_hash"] == "b7b49af6e144ef87"


def test_emit_removes_stale_shards(tmp_path):
    """A shard left from a bigger previous bake would be served alongside the new
    ones and its entries would appear twice."""
    entries = list(merge.merge_all({"CCL": [rec("CCL", TENOU)]}))
    emit(entries, tmp_path, pipeline_version="test")
    (tmp_path / "dict" / "shard-099.json").write_text("{}", encoding="utf-8")
    emit(entries, tmp_path, pipeline_version="test")
    assert not (tmp_path / "dict" / "shard-099.json").exists()


def test_emit_shard_size_is_respected(tmp_path):
    # 1,100 DISTINCT norm_keys. Two earlier attempts failed here, both wrongly
    # blaming the merge:
    #   * appending combining marks — norm_key strips them, so all 1,100 fold to 1
    #   * appending codepoints from U+2C80 — U+2C80 and U+2C81 are capital and
    #     small ALFA, which the collation folds together, so 1,100 became 550.
    # Both were correct behaviour. Three alphabet letters give 22^3 = 10,648
    # combinations that are distinct AFTER folding, which is the property needed.
    letters = collate.alphabet_chars()
    lemmas = []
    for i in range(1100):
        lemmas.append(TENOU + letters[i % 22] + letters[(i // 22) % 22]
                      + letters[(i // 484) % 22])
    assert len({merge.norm_key(l) for l in lemmas}) == 1100
    entries = list(merge.merge_all({"CCL": [rec("CCL", l) for l in lemmas]}))
    s = emit(entries, tmp_path, pipeline_version="test")
    assert s["shards"] == 3
    # Session 5 D2: read through shardio, which knows about the .gz form.
    import sys as _s; _s.path.insert(0, str(ROOT / "tools"))
    import shardio as _shardio
    counts = [_shardio.read_shard(p)["count"]
              for p in _shardio.shard_paths(tmp_path / "dict")]
    assert counts == [500, 500, 100]


def test_emit_order_guard_rejects_a_codepoint_sort():
    """The guard against someone 'simplifying' the sort to sorted()."""
    bad = [{"norm_key": k} for k in sorted([chr(0x2CB0), chr(0x2C80), chr(0x03E2)])]
    with pytest.raises(SystemExit):
        assert_coptic_order(bad)


def test_emit_order_guard_accepts_coptic_order():
    keys = collate.coptic_sorted([chr(0x2CB0), chr(0x2C80), chr(0x03E2)])
    assert_coptic_order([{"norm_key": k} for k in keys])


def test_emit_order_guard_is_not_vacuous():
    """If codepoint order and Coptic order agreed, the guard above would prove
    nothing. Assert the demo string where they differ."""
    demo = [chr(0x2CB0), chr(0x2C80), chr(0x03E2)]
    assert sorted(demo) != collate.coptic_sorted(demo)


# ── against the real shipped dataset ─────────────────────────────────────────

# Session 5 D2: the shipped shards are .json.gz. Resolved via shardio so this
# keeps working whether a checkout has the compressed or uncompressed form.
def _baked_shards() -> list:
    import sys as _s
    _s.path.insert(0, str(ROOT / "tools"))
    import shardio as _shardio
    return _shardio.shard_paths(ROOT / "data" / "dist" / "dict")


SHARDS = _baked_shards()

# Session 5 D2: the shipped shards are .json.gz, so every read of a baked shard
# goes through shardio, which resolves the compressed form transparently.
sys.path.insert(0, str(ROOT / "tools"))
import shardio as _shardio  # noqa: E402

needs_shards = pytest.mark.skipif(not SHARDS, reason="no baked shards; run emit")


@needs_shards
def test_real_shards_are_in_coptic_order():
    """Every shard boundary and every entry, read back off disk."""
    for p in SHARDS:
        payload = _shardio.read_shard(p)
        assert_coptic_order(payload["entries"])


@needs_shards
def test_real_index_hash_matches_the_module():
    idx = json.loads((ROOT / "data" / "dist" / "dict" / "index.json")
                     .read_text(encoding="utf-8"))
    assert idx["collation_hash"] == collate.collation_hash()
    assert idx["entry_count"] == sum(
        _shardio.read_shard(p)["count"] for p in SHARDS)


@needs_shards
def test_real_shards_are_non_empty_and_capped():
    for p in SHARDS:
        c = _shardio.read_shard(p)["count"]
        assert 0 < c <= 500, f"{p.name} has {c} entries"


@needs_shards
def test_real_records_csv_has_one_row_per_entry_source_pair():
    # Session 7 C4: records.csv ships as records.csv.gz, so it is read through
    # safeio rather than opened as text.
    import csv as _csv
    import io as _io
    import safeio as _safeio
    text = _safeio.read_maybe_gzip(
        ROOT / "data" / "dist" / "provenance" / "records.csv").decode("utf-8")
    rows = list(_csv.DictReader(_io.StringIO(text, newline="")))
    expected = 0
    for p in SHARDS:
        for e in _shardio.read_shard(p)["entries"]:
            expected += len(e["sources"])
