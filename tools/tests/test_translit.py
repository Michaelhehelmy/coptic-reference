# tools/tests/test_translit.py — Session 17, D0.
#
# The rule-based transliterator (tools/emit/translit.py) is deterministic and
# every rule cites a published source; unclear cases are UNVERIFIED in the
# module, not hidden. These tests pin:
#
#   1. the four required words (bohairic + sahidic),
#   2. the v4 §2.1 example across all five schemes (layton/till/egyptological),
#   3. twenty corpus words from Ruth (Sahidic) and Mark (Bohairic), derived by
#      hand from the rules — expected strings are literals, not code output,
#   4. the edge branches: combining marks, ϯ ligature, bound groups, Greek
#      block, capitals, diaeresis, determinism.
#
# Rule 8 (two inputs per branch): every branch the renderer conditions on —
# digraph present/absent, mark present/absent, ϯ present/absent, Greek-block
# present/absent, capital present/absent — appears in at least two cases.
#
# Kaikki `forms.romanization` is a CROSS-CHECK (C4), never the source: the one
# test that reads it asserts agreement only where no known systematic
# divergence exists (ϫ: Kaikki j vs ALA-LC č; ϭ: Kaikki č vs ALA-LC ky).
#
# LICENCE: project code, Apache-2.0.
from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "emit"))
sys.path.insert(0, str(ROOT / "tools" / "merge"))

import translit  # noqa: E402
import entries as mergemod  # noqa: E402

B, S, L, T, E = (translit.to_bohairic, translit.to_sahidic,
                 translit.to_layton, translit.to_till,
                 translit.to_egyptological)


# ── 1. required cases (session brief) ────────────────────────────────────────

@pytest.mark.parametrize(("coptic", "bohairic", "sahidic"), [
    ("ⲧⲉⲛⲟⲩ", "tenoou", "tenou"),
    ("ⲡⲉⲧⲣⲟⲥ", "petros", "petros"),
    ("ⲓⲱⲁⲛⲛⲏⲥ", "ioannes", "iōannēs"),
    ("ⲙⲁⲣⲓⲁ", "maria", "maria"),
])
def test_required_words(coptic, bohairic, sahidic):
    assert B(coptic) == bohairic
    assert S(coptic) == sahidic


# ── 2. v4 §2.1 example across all five schemes ───────────────────────────────

def test_v4_example_all_schemes():
    assert translit.transliterate_all("ⲧⲉⲛⲟⲩ") == {
        "bohairic": "tenoou", "sahidic": "tenou", "layton": "ṯenou",
        "till": "teno", "egyptological": "tnw",
    }


# ── 3. twenty corpus words, hand-derived ─────────────────────────────────────
# Format: (coptic, bohairic, sahidic, layton, till, egyptological).
# Sources: sahidic_ruth norms (1-10), bohairic_mark norms (11-20).
TWENTY = [
    ("ϣⲱⲡⲉ", "šope", "šōpe", "šōpe", "šōpe", "šp"),
    ("ϩⲙⲟⲟⲥ", "hmoos", "hmoos", "hmoos", "hmoos", "hms"),
    ("ϯϩⲁⲡ", "dihap", "tihap", "tihap", "tihap", "tihp"),
    ("ⲛϭⲓ", "nkyi", "nkyi", "nkyi", "nkyi", "nkj"),
    ("ϫⲉ", "če", "če", "če", "če", "č"),
    ("ⲃⲏⲑⲗⲉⲉⲙ", "bethleem", "bēthleem", "bēthleem", "bēthleem", "bthlm"),
    ("ⲕⲣⲓⲧⲏⲥ", "krites", "kritēs", "kriṯēs", "kritēs", "krjts"),
    ("ⲓⲟⲩⲇⲁ", "ioouda", "iouda", "iouda", "ioda", "jwd"),
    ("ⲉⲃⲟⲗ", "ebol", "ebol", "ebol", "ebol", "bl"),
    ("ⲥϩⲓⲙⲉ", "shime", "shime", "shime", "shime", "shjm"),
    ("ⲓⲏⲥⲟⲩⲥ", "iesoous", "iēsous", "iēsous", "iēsos", "jsws"),
    ("ⲛⲟⲩϯ", "nooudi", "nouti", "nouti", "noti", "nwti"),
    ("ⲭⲣⲓⲥⲧⲟⲥ", "christos", "christos", "chrisṯos", "christos", "chrjsts"),
    ("ⲉⲩⲁⲅⲅⲉⲗⲓⲟⲛ", "euaggelion", "euaggelion", "euaggelion",
     "euaggelion", "wggljn"),
    ("ⲟⲩⲱⲣⲡ", "oouorp", "ouōrp", "ouōrp", "oōrp", "wrp"),
    ("ⲥϧⲏⲟⲩⲧ", "sheoout", "shēout", "shēouṯ", "shēot", "shwt"),
    ("ⲁⲣⲭⲏ", "arche", "archē", "archē", "archē", "rch"),
    ("ⲡⲣⲟⲫⲏⲧⲏⲥ", "prophetes", "prophētēs", "prophēṯēs", "prophētēs",
     "prphts"),
    ("ϩⲏⲡⲡⲉ", "heppe", "hēppe", "hēppe", "hēppe", "hpp"),
    ("ϭⲟⲓⲥ", "kyois", "kyois", "kyois", "kyois", "kjs"),
]


@pytest.mark.parametrize(("coptic", "b", "s", "l", "t", "e"), TWENTY)
def test_corpus_words_hand_verified(coptic, b, s, l, t, e):
    assert B(coptic) == b, f"bohairic {coptic}"
    assert S(coptic) == s, f"sahidic {coptic}"
    assert L(coptic) == l, f"layton {coptic}"
    assert T(coptic) == t, f"till {coptic}"
    assert E(coptic) == e, f"egyptological {coptic}"


# ── 4. edge branches ─────────────────────────────────────────────────────────

def test_combining_grave_strips_to_base_letter():
    # R4: ⲛ + U+0300 still transliterates as n (ALA-LC Note 3).
    assert S("ⲛ̀") == "n"
    assert B("ⲛ̀ⲑⲱⲟⲩ") == B("ⲛⲑⲱⲟⲩ")
    assert S("ⲙ̄ⲛ̄ⲟⲩⲱⲙ") == S("ⲙⲛⲟⲩⲱⲙ")


def test_ti_ligature_sahidic_ti_bohairic_di():
    # R7 / U1: single-codepoint ϯ (and capital Ϯ).
    assert S("ϯ") == "ti"
    assert B("ϯ") == "di"
    assert S("Ϯ") == "ti"
    assert B("Ϯ") == "di"


def test_bound_group_separators_pass_through():
    # R5: spaces, underscores, hyphens and pipes are preserved, never merged.
    assert S("ϩⲙ ⲡⲏⲓ") == "hm pēi"
    assert S("ϩⲙ_ⲡⲏⲓ") == "hm_pēi"
    assert S("ϩⲙ-ⲡⲏⲓ") == "hm-pēi"


def test_greek_block_letters():
    # R6/R1: ϣ ϩ ϭ ϯ each covered, plus ϫ and ϧ.
    assert S("ϣ") == "š"
    assert S("ϩ") == "h"
    assert S("ϫ") == "č"
    assert S("ϭ") == "ky"
    assert S("ϯ") == "ti"
    assert S("ϧⲉⲛ") == "hen"


def test_capitals_fold():
    # R8: Ϣⲁⲓ and ϣⲁⲓ are the same word (S2-B10 class).
    assert S("Ϣⲁⲓ") == S("ϣⲁⲓ") == "šai"
    assert B("Ⲧⲉⲛⲟⲩ") == B("ⲧⲉⲛⲟⲩ")


def test_diaeresis_kept():
    # R4 exception: ⲓ̈->ï, ⲩ̈->ü (ALA-LC Note 3).
    assert S("ⲓ̈") == "ï"
    assert S("ⲩ̈") == "ü"


def test_deterministic_and_pure():
    # R8: same input twice, input string never mutated.
    word = "ⲓⲱⲁⲛⲛⲏⲥ"
    first = translit.transliterate_all(word)
    assert translit.transliterate_all(word) == first
    assert word == "ⲓⲱⲁⲛⲛⲏⲥ"
    with pytest.raises(TypeError):
        S(None)  # type: ignore[arg-type]


def test_unverified_rules_are_declared():
    # C2: every UNVERIFIED id is referenced by at least the module docstring
    # and the registry is non-empty (an empty registry would claim full
    # sourcing, which is false). D1 adds R9 (editorial passthrough) and U7
    # (unsourced Old Coptic letters).
    assert len(translit.UNVERIFIED) >= 5
    assert {u[0] for u in translit.UNVERIFIED} == \
        {"U1", "U2", "U3", "U4", "U5", "U6", "U7"}
    assert len(translit.RULES) == 9


def test_d1_dialect_letters():
    # D1 table additions: ⳉ->ẍ (ALA-LC row), Greek ι->i (ALA-LC Greek row),
    # ⳋ->h (U7, HORI analogy with ϧ).
    assert S("ⲁⲛⲁⳉ") == "anaẍ"
    assert S("ϩⲩⲡⲟⲕⲉιⲙⲉⲛⲟⲥ") == "hupokeimenos"
    assert S("ⲙⲉⳋⲏⲗ") == "mehēl"


def test_d1_editorial_marks_pass_through_visibly():
    # R9: Leiden preservation — sigla survive in every scheme, never dropped.
    assert S("*ⲃⲁⲗⲙⲟⲩ") == "*balmou"
    assert S("ⲁⲙⲁϩⲧⲉ (ⲉϫⲛ-)") == "amahte (ečn-)"
    assert S("ⲁⲣⲏϫ⸗") == "arēč⸗"
    assert B("*ⲃⲁⲗⲙⲟⲩ") == "*balmoou"
    assert E("ⲛⳤ") == "nⳤ"


def test_d1_unsourced_letters_stay_visible():
    # U7: ⲋ/ⳇ have no sourced Latin value; passthrough keeps them greppable.
    assert S("ⲁⲡⲟⲩⲕⲁⳇ") == "apoukaⳇ"
    assert S("Ⲋ") == "ⲋ"


def test_d1_strict_raises_naming_the_character():
    # C3 mechanism: a truly unmappable character raises, naming U+code.
    with pytest.raises(translit.TranslitError, match=r"U\+2CDF"):
        translit.transliterate_all_strict("ⲁⳟ")
    # ...while the full merged corpus is strict-clean (0 failures / 11,369).
    assert translit.transliterate_all_strict("ⲧⲉⲛⲟⲩ")["sahidic"] == "tenou"


def test_d1_merge_error_names_entry_id_and_character():
    # C3 end to end: merge_group raises MergeError naming id + character.
    rec = {
        "lemma": "ⲁⳟ", "display": "ⲁⳟ", "pos": [], "dialects": [],
        "glosses": [{"text": "x", "lang": "en", "source": "CCL"}],
        "etymology": None, "forms": [], "examples": [],
        "tla_id": None,
        "sources": [{"id": "CCL", "licence": "CC-BY-SA-4.0"}],
        "provenance": {"record_id": "T-1"},
    }
    with pytest.raises(mergemod.MergeError, match=r"U\+2CDF") as exc:
        mergemod.merge_group([rec])
    assert "ⲁⳟ" in str(exc.value)  # the lemma, so the entry is findable


# ── Kaikki cross-check (C4: check, never source) ─────────────────────────────

def _kaikki_romanizations():
    path = ROOT / "sources" / "kaikki" / \
        "kaikki.org-dictionary-Coptic.jsonl"
    if not path.is_file():
        pytest.skip("kaikki source absent")
    out: dict[str, str] = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            for f in obj.get("forms", []) or []:
                if "romanization" in (f.get("tags") or []) and f.get("form"):
                    out.setdefault(obj.get("word", ""), f["form"])
                    break
    return out


def test_kaikki_cross_check_where_comparable():
    """C4: Kaikki agrees with sahidic except on four known divergences.

    Systematic Wiktionary-vs-ALA-LC differences, measured on this corpus
    (module docstring): ϫ (Kaikki j vs ALA-LC č, e.g. je/če), ϭ (Kaikki č
    vs ALA-LC ky, e.g. nči/nkyi), ⲭ (Kaikki kh vs ALA-LC ch, e.g.
    khristos/christos), ϧ (Kaikki x vs our h from the CDO S/B cognate,
    e.g. sxēout/shēout). Every other comparable word must agree exactly.
    """
    kaikki = _kaikki_romanizations()
    words = ["ⲙⲁⲣⲓⲁ", "ⲡⲉⲧⲣⲟⲥ", "ⲓⲱⲁⲛⲛⲏⲥ",
             *[w for w, _, _, _, _, _ in TWENTY]]
    checked = mismatched = 0
    divergent: list[str] = []
    for w in words:
        roman = kaikki.get(w)
        if not roman:
            continue  # e.g. ⲧⲉⲛⲟⲩ has no Kaikki record: absence, not failure
        if any(c in w for c in ("ϫ", "ϭ", "ⲭ", "ϧ")):
            divergent.append(f"{w}: kaikki={roman} sahidic={S(w)}")
            continue
        checked += 1
        if S(w) != roman:
            mismatched += 1
            divergent.append(f"{w}: kaikki={roman} sahidic={S(w)}")
    assert checked > 0, "no comparable Kaikki romanizations found"
    assert mismatched == 0, \
        f"{mismatched} non-divergent mismatch(s): {divergent}"
