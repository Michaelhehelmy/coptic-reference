# tools/tests/test_kaikki.py — Session 3, D1.
#
# Four cases the brief requires (valid, missing senses, empty gloss chain,
# malformed line) plus two that exist because the parser got them wrong first:
# `forms` and `examples` elements are DICTS in the real extract, and an earlier
# draft filtered on `isinstance(..., str)` and returned zero of each from 62 MB
# of real data — silently, because an empty list is a valid shape.
#
# LICENCE: project code, Apache-2.0. Fixtures are synthetic.
from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "parse"))

import kaikki  # noqa: E402

REAL = ROOT / "sources" / "kaikki" / "kaikki.org-dictionary-Coptic.jsonl"


# ── a valid record ───────────────────────────────────────────────────────────

VALID = {
    "word": "ⲧⲉⲛⲟⲩ",
    "lang": "Coptic",
    "lang_code": "cop",
    "pos": "adv",
    "senses": [{
        "id": "en-tenou-cop-adv-1",
        "glosses": ["now, at present"],
        "tags": ["neuter"],
        "categories": [{"name": "Coins", "kind": "other", "parents": [],
                        "source": "w", "langcode": "cop"}],
        "links": [["tenoou", "tenoou"]],
    }],
    "etymology_text": "From Demotic Egyptian.",
    "etymology_templates": ["From Demotic Egyptian."],
    "etymology_number": 1,
    "head_templates": ["adv"],
    "forms": [{"form": "ⲧⲉⲛⲟⲩⲧ", "tags": ["ppr"]},
              {"form": "tenou", "roman": "tenou", "tags": ["romanization"]}],
}


def test_valid_record():
    r = kaikki.parse_record(json.dumps(VALID, ensure_ascii=False))
    assert r is not None
    assert r["lemma"] == "ⲧⲉⲛⲟⲩ"
    assert r["display"] == "ⲧⲉⲛⲟⲩ"
    assert r["pos"] == ["adv"]
    assert len(r["glosses"]) == 1
    assert r["glosses"][0]["text"] == "now, at present"
    assert r["glosses"][0]["source"] == "Kaikki"
    assert r["etymology"]["text"] == "From Demotic Egyptian."
    assert r["provenance"]["record_id"] == "en-tenou-cop-adv-1"
    assert r["provenance"]["lang_code"] == "cop"


def test_every_record_carries_the_pinned_source_and_licence():
    """Invariant 7. A record without provenance cannot be attributed, so this is
    asserted rather than assumed — it is the field the merge relies on."""
    r = kaikki.parse_record(json.dumps(VALID, ensure_ascii=False))
    assert len(r["sources"]) == 1
    assert r["sources"][0]["id"] == "Kaikki"
    assert r["sources"][0]["licence"] == "CC-BY-SA-4.0 OR GFDL"
    assert r["sources"][0]["cite"]


def test_dialect_is_empty_not_invented():
    """Kaikki carries no dialect flag. Emitting one would be a fabrication, and
    v4 §10.2 forbids presenting a dialect we have no evidence for."""
    r = kaikki.parse_record(json.dumps(VALID, ensure_ascii=False))
    assert r["dialects"] == []


def test_gloss_pos_is_not_taken_from_tags():
    """Wiktextract `tags` are grammatical tags ("neuter"), not POS. An earlier
    draft used tags[0] and produced POS="neuter"."""
    r = kaikki.parse_record(json.dumps(VALID, ensure_ascii=False))
    assert r["glosses"][0]["pos"] is None
    assert r["pos"] == ["adv"], "headword POS comes from rec['pos']"


def test_every_element_of_a_gloss_chain_is_kept():
    """A chain like ["of copper", "of a metal"] — element 2 is a real sense
    detail that taking only element 1 would lose."""
    rec = dict(VALID)
    rec["senses"] = [{"glosses": ["of copper", "of a metal"], "id": "x"}]
    r = kaikki.parse_record(json.dumps(rec, ensure_ascii=False))
    assert [g["text"] for g in r["glosses"]] == ["of copper", "of a metal"]
    assert [g["rank"] for g in r["glosses"]] == [1, 2]


def test_gloss_wording_is_preserved_verbatim():
    """v4 §2.4 rule 7 forbids merging senses across sources by gloss text. If
    this parser lowercased or stripped punctuation, that rule would be
    unauditable."""
    rec = dict(VALID)
    rec["senses"] = [{"glosses": ["Now,  At Present!"]}]
    r = kaikki.parse_record(json.dumps(rec, ensure_ascii=False))
    assert r["glosses"][0]["text"] == "Now, At Present!"


# ── the two dict-vs-string regressions ───────────────────────────────────────

def test_forms_are_dicts_not_strings():
    """REAL DATA: `forms` elements are dicts with a `form` key. A str filter
    silently returned zero of 39,000+."""
    r = kaikki.parse_record(json.dumps(VALID, ensure_ascii=False))
    assert len(r["forms"]) == 2, "both forms must be extracted"
    texts = {f["form"] for f in r["forms"]}
    assert texts == {"ⲧⲉⲛⲟⲩⲧ", "tenou"}


def test_form_kind_distinguishes_romanization_from_inflection():
    """Conflating them would show a reader "tenou" as if it were an inflection
    of ⲧⲉⲛⲟⲩ."""
    r = kaikki.parse_record(json.dumps(VALID, ensure_ascii=False))
    kinds = {f["form"]: f["kind"] for f in r["forms"]}
    assert kinds["tenou"] == "romanization"
    assert kinds["ⲧⲉⲛⲟⲩⲧ"] == "inflection"


def test_examples_are_dicts_not_strings():
    """REAL DATA: `examples` elements are dicts with `text` and `english`."""
    rec = dict(VALID)
    rec["senses"] = [{"glosses": ["x"], "examples": [
        {"text": "ⲁϣ ϭⲉ ⲧⲉⲛⲟⲩ ⲛⲉ", "english": "What kind now?",
         "ref": "Encomium 1.23", "type": "example"},
    ]}]
    r = kaikki.parse_record(json.dumps(rec, ensure_ascii=False))
    assert len(r["examples"]) == 1
    assert r["examples"][0]["coptic"] == "ⲁϣ ϭⲉ ⲧⲉⲛⲟⲩ ⲛⲉ"
    assert r["examples"][0]["translation"] == "What kind now?"
    assert r["examples"][0]["work"] == "Encomium 1.23"


def test_example_with_english_instead_of_translation():
    rec = dict(VALID)
    rec["senses"] = [{"glosses": ["x"], "examples": [
        {"text": "ⲁⲛ ⲡⲉ", "english": "there is not", "translation": "there is not"},
    ]}]
    r = kaikki.parse_record(json.dumps(rec, ensure_ascii=False))
    assert r["examples"][0]["translation"] == "there is not"


# ── missing senses ───────────────────────────────────────────────────────────

def test_missing_senses_key():
    rec = {k: v for k, v in VALID.items() if k != "senses"}
    r = kaikki.parse_record(json.dumps(rec, ensure_ascii=False))
    assert r is not None, "a record without senses is still a record"
    assert r["glosses"] == []
    assert r["senses"] is False


def test_senses_is_null():
    rec = dict(VALID)
    rec["senses"] = None
    r = kaikki.parse_record(json.dumps(rec, ensure_ascii=False))
    assert r["glosses"] == []
    assert r["senses"] is False


def test_senses_wrong_type():
    """Not an exception. A future Wiktextract version must not red the build."""
    rec = dict(VALID)
    rec["senses"] = {"glosses": ["nope"]}
    r = kaikki.parse_record(json.dumps(rec, ensure_ascii=False))
    assert r["glosses"] == []


def test_senses_containing_non_dicts():
    rec = dict(VALID)
    rec["senses"] = ["a string", 42, None, {"glosses": ["kept"]}]
    r = kaikki.parse_record(json.dumps(rec, ensure_ascii=False))
    assert [g["text"] for g in r["glosses"]] == ["kept"]


def test_missing_word_returns_none():
    rec = {k: v for k, v in VALID.items() if k != "word"}
    assert kaikki.parse_record(json.dumps(rec, ensure_ascii=False)) is None


def test_blank_word_returns_none():
    rec = dict(VALID)
    rec["word"] = "   "
    assert kaikki.parse_record(json.dumps(rec, ensure_ascii=False)) is None


# ── empty gloss chain ────────────────────────────────────────────────────────

def test_empty_gloss_chain_is_kept_as_an_empty_list():
    """The real data has exactly one such record (ⲥⲛⲁⲩϩ). It must SURVIVE the
    parser with an empty list, so the count stays auditable, and be rejected
    later by the schema — not vanish here."""
    rec = dict(VALID)
    rec["senses"] = [{"glosses": [], "id": "empty"}]
    r = kaikki.parse_record(json.dumps(rec, ensure_ascii=False))
    assert r is not None
    assert r["glosses"] == []
    assert r["senses"] is True


def test_glosses_key_absent():
    rec = dict(VALID)
    rec["senses"] = [{"id": "no-glosses-key"}]
    r = kaikki.parse_record(json.dumps(rec, ensure_ascii=False))
    assert r["glosses"] == []


def test_glosses_containing_empty_and_whitespace_strings():
    rec = dict(VALID)
    rec["senses"] = [{"glosses": ["", "   ", "\t\n", "real"]}]
    r = kaikki.parse_record(json.dumps(rec, ensure_ascii=False))
    assert [g["text"] for g in r["glosses"]] == ["real"]


def test_glosses_not_a_list():
    rec = dict(VALID)
    rec["senses"] = [{"glosses": "a bare string"}]
    r = kaikki.parse_record(json.dumps(rec, ensure_ascii=False))
    assert r["glosses"] == []


def test_duplicate_glosses_within_one_sense_are_collapsed():
    rec = dict(VALID)
    rec["senses"] = [{"glosses": ["Now", "now", "NOW"]}]
    r = kaikki.parse_record(json.dumps(rec, ensure_ascii=False))
    assert len(r["glosses"]) == 1, "case-variant duplicates within a sense"


def test_glosses_containing_non_strings():
    rec = dict(VALID)
    rec["senses"] = [{"glosses": ["ok", 42, None, {"a": "dict"}]}]
    r = kaikki.parse_record(json.dumps(rec, ensure_ascii=False))
    assert [g["text"] for g in r["glosses"]] == ["ok"]


# ── malformed line ───────────────────────────────────────────────────────────

def test_malformed_json_raises_with_the_line_number():
    with pytest.raises(kaikki.KaikkiParseError) as e:
        kaikki.parse_record('{"word": "ⲁⲛ", ', line_no=42)
    assert "line 42" in str(e.value)


def test_malformed_json_names_the_problem():
    with pytest.raises(kaikki.KaikkiParseError):
        kaikki.parse_record("not json at all")


def test_a_json_array_raises():
    """A record must be an object. An array here means the extract's shape
    changed, which is drift, not a thin record."""
    with pytest.raises(kaikki.KaikkiParseError):
        kaikki.parse_record('[1, 2, 3]')


def test_a_json_scalar_raises():
    with pytest.raises(kaikki.KaikkiParseError):
        kaikki.parse_record('"just a string"')


# ── POS mapping ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("noun", "n"), ("verb", "v"), ("adj", "adj"), ("adverb", "adv"),
    ("proper noun", "proper noun"),   # unknown -> preserved verbatim
])
def test_pos_mapping(raw, expected):
    assert kaikki.map_pos(raw) == expected


def test_unknown_pos_is_preserved_not_dropped():
    """A POS we have not seen is still a fact about the word. Dropping it would
    make the entry look better-founded than it is."""
    assert kaikki.map_pos("Coptic-specific-thing") == "coptic-specific-thing"
    assert kaikki.map_pos("") == ""
    assert kaikki.map_pos(None) == ""


# ── the drift gate ───────────────────────────────────────────────────────────

def test_drift_gate_raises_below_2500(tmp_path):
    p = tmp_path / "small.jsonl"
    p.write_text("\n".join(json.dumps(VALID, ensure_ascii=False)
                           for _ in range(10)), encoding="utf-8")
    with pytest.raises(kaikki.SchemaDrift) as e:
        kaikki.count_records(p)
    msg = str(e.value)
    assert "2500" in msg
    assert "Do not silently update the pin" in msg or "DO NOT silently update" in msg


def test_drift_gate_passes_at_the_threshold(tmp_path):
    p = tmp_path / "exact.jsonl"
    p.write_text("\n".join(json.dumps(VALID, ensure_ascii=False)
                           for _ in range(kaikki.MIN_RECORDS)), encoding="utf-8")
    assert kaikki.count_records(p)["records"] == kaikki.MIN_RECORDS


def test_iter_records_is_a_generator_and_skips_thin_records(tmp_path):
    """Streaming is the point: a caller that wants 1 record must not read the
    file. `iter_records` is a generator, and blank lines are skipped."""
    p = tmp_path / "mixed.jsonl"
    p.write_text("\n".join([
        json.dumps(VALID, ensure_ascii=False),
        "",
        json.dumps({"lang_code": "cop"}, ensure_ascii=False),   # no word -> dropped
        "   ",
        json.dumps(VALID, ensure_ascii=False).replace("ⲧⲉⲛⲟⲩ", "ⲁⲛ"),
    ]), encoding="utf-8")
    import types
    gen = kaikki.iter_records(p)
    assert isinstance(gen, types.GeneratorType)
    first = next(gen)
    assert first["lemma"] == "ⲧⲉⲛⲟⲩ"
    rest = list(gen)
    assert len(rest) == 1 and rest[0]["lemma"] == "ⲁⲛ"


# ── against the real pinned file ─────────────────────────────────────────────

needs_real = pytest.mark.skipif(not REAL.is_file(),
                                reason="Kaikki extract not fetched; "
                                       "run tools/fetch/fetch_all.py")


@needs_real
def test_real_file_record_count_matches_the_pin():
    """3,293 exactly. If this moves, upstream moved — which is a human decision,
    not something to absorb silently."""
    counts = kaikki.count_records(REAL)
    assert counts["records"] == 3293
    assert counts["no_word"] == 0


@needs_real
def test_real_file_actually_yields_forms_and_examples():
    """The regression that motivated this file, run against the real 62 MB.

    An empty list is a valid shape, so nothing else would have caught it. These
    floors are deliberately far below the measured values (3,288 / 120) — they
    assert "not zero", not "exactly N", because the upstream file can change.
    """
    c = kaikki.census(REAL)
    assert c["with_forms"] > 3000, f"forms collapsed to {c['with_forms']}"
    assert c["with_examples"] > 50, f"examples collapsed to {c['with_examples']}"
    assert c["with_gloss"] > 3200
    assert c["with_etymology"] > 2500


@needs_real
def test_real_records_all_carry_provenance():
    n = 0
    for rec in kaikki.iter_records(REAL):
        assert rec["sources"][0]["id"] == "Kaikki"
        assert rec["sources"][0]["licence"] == "CC-BY-SA-4.0 OR GFDL"
        n += 1
        if n >= 500:
            break
    assert n == 500


@needs_real
def test_real_forms_are_dicts_in_the_source_data():
    """Check the assumption directly in the file, not just in the parser."""
    with REAL.open(encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            for f in rec.get("forms") or []:
                assert isinstance(f, dict), "forms elements changed shape"
                assert "form" in f
                return
    pytest.skip("no forms in the first record scanned")
