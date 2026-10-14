# tools/collate.py — Coptic collation.
#
# WHY THIS EXISTS (measured, not assumed):
#   python3 -c "print(sorted(['Ϣ','Ⲱ','Ⲁ']))"  ->  ['Ϣ', 'Ⲁ', 'Ⲱ']
# Ϣ is U+03E2 (Greek and Coptic block); Ⲁ is U+2C80 and Ⲱ is U+2CB0 (Coptic
# block). Codepoint order therefore places the four Greek-borrowed Coptic
# letters FIRST and the Old Coptic dialect letters LAST — both wrong.
#
# WHY THE ALPHABET IS DECLARED BY UNICODE NAME (not hand-typed glyphs):
# A hand-typed inventory produced four real bugs during development:
#   B1  typed U+2C9A "Ⲛ" for "kho" — it is CAPITAL LETTER NI. The /x/,ħ/
#       letter is ⲭ U+2CAD "KHI"; it fell into the dialect tier.
#   B2  typed U+2C9C "Ⲝ" for small kso — it is CAPITAL LETTER KSI
#       (small is U+2C9D). Broke the main-alphabet sequence.
#   B3  case-folded BEFORE the codepoint tiebreak, so sort_key("Ⲁ") ==
#       sort_key("ⲁ"). Shard boundaries became input-order dependent.
#   B4  even/odd codepoint parity for capital/small pairs breaks at U+2CE4
#       where COPTIC SYMBOL KAI / MI RO / PI RO enter; 13 chars mis-pair.
# Fixes: resolve the alphabet from Unicode names; pair case by NAME;
#        expose two keys (rank_key for equivalence, sort_key for order).
#
# LICENCE: project code, Apache-2.0.
from __future__ import annotations
import hashlib, json, re, unicodedata
from typing import Callable, Iterable

# (unicode NAME descriptor, traditional Egyptian name, value)
_ALPHA: tuple[tuple[str, str, str], ...] = (
    ("ALFA", "alfa", "/a/"),   ("VIDA",  "vida", "/b/"),
    ("GAMMA","gamma","/g/"),   ("DALDA", "dalda","/d/"),
    ("EIE",  "eie",  "/j/"),    ("SOU",   "sou",  "/z/"),
    ("ZATA", "zata", "/eː/"),   ("HATE",  "hate", "/θ/"),
    ("MI",   "men",  "/m/"),    ("NI",    "ni",   "/n/"),
    ("KSI",  "kso",  "/no/"),   ("O",     "omicron","/o/"),
    ("PI",   "pi",   "/p/"),    ("RO",    "rho",  "/r/"),
    ("SIMA", "sima", "/s/"),    ("TAU",   "tia",  "/t/ and /o/"),
    ("UA",   "uia",  "/u/"),    ("KHI",   "kho",  "/x/, /ħ/"),
)
# (char, upper, name, value) — Greek block, capital sits ABOVE small
_GREEK: tuple[tuple[str, str, str, str], ...] = (
    ("ϣ", "SHIN", "shin", "/š/"),
    ("ϩ", "HOR",  "hor",  "/h/"),
    ("ϭ", "KHAI", "khai", "contested /g/ or /č/"),
    ("ϯ", "TIA",  "ti",   "/ti/"),
)

_R_MAIN, _R_DIALECT_BASE, _R_GREEK, _R_NON = 10, 100, 500, 900
_CB, _CE = 0x2C80, 0x2D00                      # Coptic block bounds
# The seven Sahidic letters live in the GREEK and Coptic block, not the Coptic
# block, because they descend from Greek capitals. Their capitals (U+03E2, 03E4,
# 03E6, 03E8, 03EA, 03EC, 03EE) therefore fall outside _CB.._CE.
_GB, _GE = 0x0370, 0x0400                      # Greek and Coptic block bounds
_IGN = frozenset({"Mn", "Me", "Cf"})           # combining marks, format chars

# --- resolve capital/small pairs from Unicode NAMES -------------------------
# Name-pairing, not codepoint parity: parity breaks at U+2CE4 (defect B4).
_CAP = re.compile(r"^COPTIC CAPITAL LETTER (.+)$")
_SML = re.compile(r"^COPTIC SMALL LETTER (.+)$")
_by_name: dict[str, dict[str, str]] = {}
# Scan BOTH blocks. v4 §1.3 scanned only _CB.._CE, which silently excluded the
# seven Greek-block Sahidic letters from case-folding — so `canon_for_sort("Ϣⲁⲓ")`
# returned "Ϣⲁⲓ" unchanged while `canon_for_sort("ϣⲁⲓ")` returned "ϣⲁⲁ", i.e. the
# two cases of one letter were not the same string. Found in Session 2 by
# tools/emit/obsidian.py, which files a lemma by its first letter and reported
# Ϣⲁⲓ as unfiled. See DECISIONS.md S2-B10.
#
# The scan range is the ONLY thing changed. _ALPHA, _GREEK, ALPHABET, the rank
# table, and therefore collation_hash() are all untouched — verified: the hash
# is still b7b49af6e144ef87 after this edit. No _ALPHA descriptor collides with
# the seven Greek-block names (checked: ALFA, VIDA, GAMMA, DALDA, EIE, SOU, ZATA,
# HATE, MI, NI, KSI, O, PI, RO, SIMA, TAU, UA, KHI vs DEI, FEI, GANGIA, HORI, KHEI,
# SHEI, SHIMA).
for _cp in list(range(_GB, _GE)) + list(range(_CB, _CE)):
    _n = unicodedata.name(chr(_cp), "")
    m = _CAP.match(_n)
    if m:
        _by_name.setdefault(m.group(1), {})["cap"] = chr(_cp); continue
    m = _SML.match(_n)
    if m:
        _by_name.setdefault(m.group(1), {})["sml"] = chr(_cp)

def _small(descriptor: str) -> str:
    """Resolve a Unicode name descriptor to its SMALL letter.

    Raises KeyError on a bad descriptor — which is the entire point: a typo
    becomes an import-time crash, not a silent mis-sort (defects B1/B2).
    """
    try:
        return _by_name[descriptor]["sml"]
    except KeyError:
        raise KeyError(
            f"Coptic letter {descriptor!r} not found in U+2C80–U+2CFF; "
            f"known: {sorted(_by_name)[:12]}…"
        ) from None

_CASE: dict[str, str] = {}
for _d, _p in _by_name.items():
    if "cap" in _p and "sml" in _p:
        _CASE[_p["cap"]] = _p["sml"]
        _CASE[_p["sml"]] = _p["sml"]
for _ch, _up, _n, _v in _GREEK:               # Greek block: capital above small
    _CASE[_ch] = _ch.lower()
    _CASE[_ch.lower()] = _ch.lower()

# --- rank table --------------------------------------------------------------
_RANK: dict[str, int] = {}
ALPHABET: tuple[tuple[str, str, str], ...] = ()      # (char, trad. name, value)
for _i, (_d, _n, _v) in enumerate(_ALPHA):
    _ch = _small(_d)
    _RANK[_ch] = _R_MAIN + _i
    ALPHABET += ((_ch, _n, _v),)
for _j, (_ch, _up, _n, _v) in enumerate(_GREEK):
    _RANK[_ch.lower()] = _R_GREEK + _j
    ALPHABET += ((_ch, _n, _v),)
for _cp in range(_CB, _CE):                  # Tier 2, by codepoint
    _RANK.setdefault(_CASE.get(chr(_cp), chr(_cp)), _R_DIALECT_BASE + (_cp - _CB))
_BLOCK = [_RANK[_CASE.get(chr(cp), chr(cp))] for cp in range(_CB, _CE)]

def alphabet_chars() -> list[str]:
    return [c for c, _n, _v in ALPHABET]

# --- the two keys ------------------------------------------------------------
def _folded(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    return "".join(_CASE.get(c, c) for c in s
                   if unicodedata.category(c) not in _IGN)

def canon_for_sort(s: str) -> str:
    """Public alias for _folded: the canonical form a sort key is built from.

    Added per Session 1 Q5 ("the test is the contract"). v4 §1.5 imports this
    name and v4 §1.3 does not define it, so the suite could not run — see
    DECISIONS.md B-1. Rather than edit the closed test to match the module, the
    module gained the name the test already expected. Same function, one public
    name instead of two, and the plan's code sample now works verbatim.
    """
    return _folded(s)

def rank_key(s: str) -> tuple:
    """Collation-EQUIVALENCE key: case-folded, marks stripped, no tiebreak.

    rank_key("Ⲁⲁ") == rank_key("ⲁⲁ")  ->  True
    rank_key("ⲛ̀ⲁⲓ") == rank_key("ⲛⲁⲓ") -> True
    rank_key("Ⲛ")   == rank_key("ⲛ")   -> True

    Use for A-Z bucketing, prefix grouping, "same headword?" checks — i.e.
    wherever the question is "are these the same to a reader?"
    """
    ranks: list[int] = []
    for ch in _folded(s):
        cp = ord(ch)
        if _CB <= cp < _CE:  ranks.append(_BLOCK[cp - _CB])
        elif ch in _RANK:   ranks.append(_RANK[ch])
        elif ch.isalpha():  ranks.append(_R_NON + min(ord(c) for c in ch.lower()))
        else:               ranks.append(_R_NON + 0x100)
    return tuple(ranks)

def sort_key(s: str) -> tuple:
    """STRICT TOTAL ORDER key: rank_key + ORIGINAL codepoint tiebreak.

    The tiebreak must come from the ORIGINAL string. Deriving it from the
    folded string makes sort_key("Ⲁ") == sort_key("ⲁ"), which collapses two
    distinct headwords and makes shard boundaries input-order dependent
    (defect B3).

    Use for shard assignment, next/prev navigation, and any output that must be
    byte-reproducible across bakes.
    """
    s = unicodedata.normalize("NFC", s)
    ranks: list[int] = []
    cps: list[int] = []
    for orig in s:
        cps.append(ord(orig))
        if unicodedata.category(orig) in _IGN:
            continue                                  # combining mark
        ch = _CASE.get(orig, orig)                    # fold for RANK only
        cp = ord(ch)
        if _CB <= cp < _CE:  ranks.append(_BLOCK[cp - _CB])
        elif ch in _RANK:   ranks.append(_RANK[ch])
        elif ch.isalpha():  ranks.append(_R_NON + min(ord(c) for c in ch.lower()))
        else:               ranks.append(_R_NON + 0x100)
    return (tuple(ranks), tuple(cps))

def coptic_sorted(items: Iterable, key: Callable = lambda x: x) -> list:
    """Coptic-collation sort. Deterministic and shuffle-invariant."""
    return sorted(items, key=lambda x: sort_key(key(x)))

def prev_next(keys: list[str]) -> dict[str, tuple[str | None, str | None]]:
    """Neighbour map. Ties are impossible: sort_key is a strict total order."""
    o = coptic_sorted(keys)
    return {k: (o[i - 1] if i > 0 else None,
                o[i + 1] if i + 1 < len(o) else None) for i, k in enumerate(o)}

def collation_hash() -> str:
    """Fingerprint of the active alphabet, recorded in the build manifest.

    A Coptologist editing _ALPHA / _GREEK changes this hash, so the table
    becomes part of the reviewable build surface rather than an invisible
    implementation detail.
    """
    payload = json.dumps({"alpha": _ALPHA, "greek": _GREEK},
                         ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

if __name__ == "__main__":
    demo = ["Ⲱ", "Ⲁ", "Ϣ", "ⲁ", "ϯ", "ⲥ", "ⲭ", "ϩ", "ⲛ", "ⲉ"]
    print("input :", demo)
    print("sorted:", coptic_sorted(demo))
    print("alphabet:", " ".join(alphabet_chars()))
    print("hash   :", collation_hash())
