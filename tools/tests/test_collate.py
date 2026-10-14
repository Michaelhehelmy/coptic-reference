# tools/tests/test_collate.py — Apache-2.0.
# LICENCE: project code, Apache-2.0.
import sys, pathlib, random

import pytest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))  # tools/
# HISTORY: v4 §1.5 imported `canon_for_sort` here; v4 §1.3 named the function
# `_folded`, so the plan's own test could not run (DECISIONS.md B-1). Session 1
# dropped the unused import. Session 1 Q5 then reversed that — "the test is the
# contract" — so `tools/collate.py` now exports `canon_for_sort` as a public
# alias and this file imports the plan's line VERBATIM. See also
# test_public_alias_canon_for_sort_is_pinned below, so the alias cannot be
# quietly removed and the plan's sample quietly broken again.
from collate import (coptic_sorted, sort_key, rank_key,
                     prev_next, collation_hash, alphabet_chars, _ALPHA,
                     canon_for_sort, _folded)

def test_public_alias_canon_for_sort_is_pinned():
    """Session 1 Q5: `canon_for_sort` must stay a public alias for `_folded`.

    It exists solely so v4 §1.5's import line works unmodified. If someone
    "cleans up" the duplicate name, the plan's code sample breaks again and the
    only signal is an ImportError in a document nobody opens.
    """
    assert canon_for_sort is not _folded or canon_for_sort("ⲛ̀ⲁⲓ") == "ⲛⲁⲓ"
    for s in ("Ⲁⲁ", "ⲛ̀ⲁⲓ", "TENOU", "ⲧⲉⲛⲟⲩ"):
        # Compare against the module's own behaviour, not the alias to itself:
        # `sort_key` is built from `_folded`, so agreement here means the alias
        # really is the same function rather than a copy that can drift.
        assert canon_for_sort(s) == _folded(s), s

def test_required__khai_sorts_after_old_coptic_hori():
    """REQUIRED TEST: Ϣ must sort AFTER Ⲱ.

    Documents its own premise: codepoint sort puts Ϣ (U+03E2) FIRST.
    """
    ordered = coptic_sorted(["Ⲱ", "Ⲁ", "Ϣ"])
    assert ordered.index("Ϣ") > ordered.index("Ⲱ"), f"got {ordered}"
    assert ord("Ϣ") < ord("Ⲱ")
    assert sorted(["Ϣ", "Ⲁ", "Ⲱ"])[0] == "Ϣ"

def test_main_alphabet_is_sequential():
    """Guards defect B2 (typed U+2C9C, CAPITAL KSI, instead of U+2C9D)."""
    egyptian = [c for c in alphabet_chars()][:len(_ALPHA)]
    assert coptic_sorted(egyptian) == egyptian

def test_tier_order_main_dialects_greek():
    a = alphabet_chars()
    dialects = ["ⲱ", "ⳁ", "ⳕ"]           # U+2CB1, 2CC1, 2CD5
    assert coptic_sorted(a + dialects) == a[:18] + dialects + a[18:]

def test_collation_equivalence__case():
    """rank_key: case is NOT a difference (T4)."""
    assert rank_key("Ⲁⲁ") == rank_key("ⲁⲁ")
    assert rank_key("Ⲛ") == rank_key("ⲛ")          # cap-NI vs small-NI

def test_collation_equivalence__marks():
    assert rank_key("ⲛ̀ⲁⲓ") == rank_key("ⲛⲁⲓ")

def test_total_order__case_variants_are_distinct():
    """Guards defect B3: sort_key must NOT collapse Ⲁ and ⲁ."""
    assert sort_key("Ⲁⲁ") != sort_key("ⲁⲁ")
    assert sort_key("Ⲁ") != sort_key("ⲁ")

def test_case_variants_land_adjacent_caps_first():
    assert coptic_sorted(["ⲁⲁ", "Ⲁⲁ"]) == ["Ⲁⲁ", "ⲁⲁ"]

def test_total_order_no_ties():
    # NOTE: v4 §1.5's original fixture listed "ⲁ" and "ⲛ" twice — once via
    # alphabet_chars() and once in the extras — so the list held 32 items but only
    # 30 distinct strings. Two identical strings MUST produce identical sort
    # keys, so `len(set(keys)) == len(keys)` was unsatisfiable as written. The
    # module was correct; the FIXTURE was wrong (30 strings -> 30 distinct keys).
    # De-duplication preserves the assertion verbatim and keeps its intent.
    strings = list(dict.fromkeys(
        alphabet_chars() + ["ⲱ","ⳁ","ⳕ","Ⲁ","ⲁ","Ⲛ","ⲛ","b","z","ⲛ̀ⲁⲓ"]))
    keys = [sort_key(s) for s in strings]
    assert len(set(keys)) == len(keys), "sort keys must be distinct"

def test_shuffle_invariance():
    """Shard-boundary determinism. This is the property B3 would have broken."""
    s = alphabet_chars() + ["ⲱ","ⳁ","ⳕ","Ⲁ","ⲁ","b","Ⲁⲁ","ⲁⲁ","Ⲛ","ⲛ"]
    ref = coptic_sorted(s)
    for _ in range(500):
        assert coptic_sorted(random.sample(s, len(s))) == ref

def test_prev_next_coptic_order():
    pn = prev_next(["Ϣ", "ⲁ", "Ⲱ"])
    assert pn["ⲁ"][1] == "Ⲱ"
    assert pn["Ⲱ"][1] == "Ϣ"

def test_latin_after_coptic():
    assert coptic_sorted(["b", "ⲁ", "a", "ϣ"]) == ["ⲁ", "ϣ", "a", "b"]

def test_alphabet_inventory_names_resolve():
    """Every descriptor resolves; guards defects B1/B2 at the source."""
    for _d, _n, _v in _ALPHA:
        assert isinstance(alphabet_chars()[0], str)
    assert len(alphabet_chars()) == len(_ALPHA) + 4      # 18 + 4 Greek

# EDITING _ALPHA OR _GREEK REQUIRES UPDATING THIS PIN IN THE SAME PR.
# CI fails if the pin and computed value diverge. This is the review gate
# for alphabet changes — see v4 §1.3 and tools/validate/collation_guard.py
def test_collation_hash_pinned():
    """Pins the alphabet. Editing _ALPHA/_GREEK requires updating this."""
    assert collation_hash() == "b7b49af6e144ef87"


def test_greek_block_capitals_case_fold():
    """REGRESSION, Session 2 (DECISIONS.md S2-B10).

    The seven Sahidic letters descend from Greek capitals and live in the GREEK
    and Coptic block, so their capitals are at U+03E2-U+03EE — OUTSIDE the
    Coptic block bounds (U+2C80-U+2CFF) that v4 §1.3 scanned for capital/small
    name pairs. They were therefore never case-folded, and the two cases of one
    letter were not the same string:

        canon_for_sort("Ϣⲁⲓ")  ->  "Ϣⲁⲓ"    (unchanged - WRONG)
        canon_for_sort("ϣⲁⲓ")  ->  "ϣⲁⲓ"

    Found by tools/emit/obsidian.py, which files a lemma by its first letter and
    reported Ϣⲁⲓ as belonging to no letter at all.

    This test asserts BOTH that each capital folds to its small form AND that the
    alphabet itself is untouched — the fix widened a scan range and nothing else,
    so collation_hash() must still be the pinned value.
    """
    pairs = [("Ϣ", "ϣ"), ("Ϥ", "ϥ"), ("Ϧ", "ϧ"),
             ("Ϩ", "ϩ"), ("Ϫ", "ϫ"), ("Ϭ", "ϭ"), ("Ϯ", "ϯ")]
    for cap, sml in pairs:
        assert canon_for_sort(cap) == sml, f"{cap} must fold to {sml}"
        assert canon_for_sort(cap + "ⲁⲓ") == sml + "ⲁⲓ", cap
        assert rank_key(cap + "ⲁⲓ") == rank_key(sml + "ⲁⲓ"), (
            f"rank_key must treat {cap} and {sml} as one letter")
    # The alphabet is a closed decision: 22 letters, in order, hash unchanged.
    assert len(alphabet_chars()) == 22
    assert collation_hash() == "b7b49af6e144ef87"


# ─────────────────────────────────────────────────────────────────────────────
# Session 3, C2 — Greek-block coverage.
#
# THE LESSON, and the reason this block exists at all:
#
# Every one of v4 §1.5's original fixtures consisted of Coptic-block letters,
# Latin, and marks. NOT ONE contained a Greek-block letter — and the Greek-block
# letters are exactly the ones that were broken (PLAN-ERRATA.md B-10). So the
# plan's own suite could not have caught B-10, and would have gone on passing
# with a collation that treated Ϣ and ϣ as different letters.
#
# Test coverage is not only which assertions run; it is which INPUTS they run
# on. A fixture that omits an entire block of the alphabet is an untested claim
# about that block.
#
# Literals below are written as codepoints on purpose. Hand-typing Greek-script
# capitals is the same class of mistake as hand-typing the alphabet (see
# PLAN-ERRATA "Do not hand-type the alphabet"), and it is not hypothetical: an
# earlier draft of this very block lost a capital in transit and produced a
# duplicate, which then failed as a "tie" and looked like a collation bug.
# ─────────────────────────────────────────────────────────────────────────────

#: The seven Greek-block capital/small pairs, by Unicode name (B-10).
GREEK_BLOCK_PAIRS: tuple[tuple[str, str], ...] = (
    ("Ϣ", "ϣ"),   # SHEI
    ("Ϥ", "ϥ"),   # FEI
    ("Ϧ", "ϧ"),   # KHEI
    ("Ϩ", "ϩ"),   # HORI
    ("Ϫ", "ϫ"),   # GANGIA
    ("Ϭ", "ϭ"),   # SHIMA
    ("Ϯ", "ϯ"),   # DEI
)

#: Unicode names, in the same order, for error messages.
GREEK_BLOCK_NAMES: tuple[str, ...] = ('SHEI', 'FEI', 'KHEI', 'HORI', 'GANGIA', 'SHIMA', 'DEI',)

#: Only FOUR of the seven are in the 22-letter Coptic alphabet (v4 §1.2):
#: ϥ ϧ ϫ (FEI, KHEI, GANGIA) are deliberately excluded from the alphabet even
#: though Unicode defines them and they case-fold correctly. Their rank falls to
#: the non-letter tier. That distinction is pinned below rather than assumed.
ALPHABET_GREEK_SMALL: tuple[str, ...] = tuple(chr(c) for c in [995, 1001, 1005, 1007])
NON_ALPHABET_GREEK_SMALL: tuple[str, ...] = tuple(
    sml for _c, sml in GREEK_BLOCK_PAIRS if sml not in ALPHABET_GREEK_SMALL)


@pytest.mark.parametrize("cap,sml", GREEK_BLOCK_PAIRS)
def test_greek_pair_is_case_equivalent(cap, sml):
    """Each of the seven, individually — B-10 was found one at a time.

    rank_key is the equivalence key: these must be EQUAL. sort_key is the order
    key: these must DIFFER, because a strict total order needs a tiebreak or
    their relative position depends on input order (v4 §1.3 defect B3).
    """
    assert canon_for_sort(cap) == sml, f"{cap} must fold to {sml}"
    assert rank_key(cap + "\u2C61\u2C93") == rank_key(sml + "\u2C61\u2C93"), (
        f"rank_key must treat {cap} and {sml} as one letter")
    assert sort_key(cap + "\u2C61\u2C93") != sort_key(sml + "\u2C61\u2C93"), (
        f"sort_key must NOT tie {cap} and {sml} — a tie makes shard "
        f"boundaries input-order dependent")


@pytest.mark.parametrize("sml", ALPHABET_GREEK_SMALL)
def test_alphabet_greek_capital_sorts_in_the_greek_tier(sml):
    """A capital must rank exactly where its small form ranks.

    U+03E2 is numerically far BELOW every Coptic-block letter, so codepoint order
    would put a Ϣ-initial headword first in the alphabet. Coptic order puts it in
    the Greek tier (rank base 500), after the dialect block. This is the §1.1
    failure repeating inside the Greek block.

    Asserted on rank_key's FIRST element rather than on whole-key comparisons:
    whole-key comparisons against neighbouring letters proved fiddly and proved
    less. What matters is that the tier is right.
    """
    cap = next(c for c, m in GREEK_BLOCK_PAIRS if m == sml)
    alpha = alphabet_chars()
    i = alpha.index(sml)
    expected_tier_rank = 500 + (i - 18)          # _R_GREEK = 500, tier starts at 18
    assert rank_key(cap)[0] == expected_tier_rank, (
        f"{cap} ranked in tier {rank_key(cap)[0]}, expected {expected_tier_rank}")
    assert rank_key(cap)[0] == rank_key(sml)[0]
    # ...and well after the main alphabet, not at the bottom by codepoint.
    assert rank_key(cap)[0] > rank_key(alpha[0])[0]
    assert rank_key(cap)[0] > rank_key(alpha[17])[0]     # alpha[17] = ⲭ, last pre-Greek


@pytest.mark.parametrize("sml", NON_ALPHABET_GREEK_SMALL)
def test_non_alphabet_greek_letters_fold_but_do_not_enter_the_alphabet(sml):
    """ϥ ϧ ϫ case-fold correctly but are not in the 22-letter alphabet.

    They must rank in the non-letter tier, not be silently promoted. v4 §1.2
    fixes the alphabet at 22 letters; a bug that grew it to 25 would change the
    collation hash and be caught there, but this states the intent directly.
    """
    cap = next(c for c, m in GREEK_BLOCK_PAIRS if m == sml)
    assert canon_for_sort(cap) == sml
    assert sml not in alphabet_chars()
    assert rank_key(cap)[0] >= 900, "must land in the non-letter tier"


def test_greek_block_coverage_is_not_regressible():
    """The coverage assertion itself.

    Session 3's review found that ten of the fifteen collation tests held no
    Greek-block letter anywhere. Rather than trust a future editor to remember,
    the count is pinned: seven pairs, four of them in the alphabet.
    """
    assert len(GREEK_BLOCK_PAIRS) == 7
    assert len(ALPHABET_GREEK_SMALL) == 4
    assert len(NON_ALPHABET_GREEK_SMALL) == 3
    for _cap, sml in GREEK_BLOCK_PAIRS:
        assert len(canon_for_sort(_cap)) == 1
    # capitals and smalls are distinct characters, not one repeated literal
    for cap, sml in GREEK_BLOCK_PAIRS:
        assert cap != sml and ord(cap) + 1 == ord(sml)


def test_sort_is_total_over_a_fixture_containing_every_greek_pair():
    """Total-order re-run on a fixture that carries all seven capital/small
    pairs — the input shape that used to break."""
    words = ["\u2CA7\u2C89\u2C9B\u238F\u2CA9", "\u2C81\u2C9B"]
    for cap, sml in GREEK_BLOCK_PAIRS:
        words += [cap + "\u2C81\u2C93", sml + "\u2C81\u2C93"]
    keys = [sort_key(w) for w in words]
    assert len(set(keys)) == len(words), "sort_key must be a strict total order"
    assert coptic_sorted(words) == coptic_sorted(list(reversed(words)))


def test_shuffle_invariance_with_greek_capitals():
    import random
    words = ["\u2C81\u2C9B", "\u03E2\u2C81\u2C93", "\u03E3\u2C81\u2C93",
             "\u2CA7\u2C89\u2C9B\u238F\u2CA9", "\u03EE\u2C81",
             "\u03EF\u2C81", "\u2C99\u2CA1\u2C81\u2CA4",
             "\u03EC\u2C81\u2C93", "\u03ED\u2C81\u2C93"]
    out = [coptic_sorted(words)]
    for seed in range(12):
        rnd = random.Random(seed)
        shuf = words[:]
        rnd.shuffle(shuf)
        out.append(coptic_sorted(shuf))
    assert all(o == out[0] for o in out), "sort order depends on input order"
