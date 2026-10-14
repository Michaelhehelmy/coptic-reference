# Static Coptic Language Reference — Implementation Plan **v4**

**Supersedes:** v3. v3 retained as the design record; its asset verification (§0) and two-stage architecture remain authoritative and are **not** re-verified here.
**Revision driver:** 12 execution-risk fixes.
**Team:** **2 people, committed** (§5). **Duration:** 16 weeks.
**Hosting:** Cloudflare Pages Free, $0 recurring.
**Effort:** **97 person-days** across four phases (was 78 in v3 — see §6.3 for why).

> **Δ markers** indicate changes from v3. Every addition reduces a specific execution risk, named in the margin note.

---

## 1. Δ Collation — Coptic alphabetical order (CRITICAL)

### 1.1 Δ Why this is critical — the measured failure

Python's default string sort places **Ϣ first**, because Ϣ is `U+03E2` (Greek and Coptic block) while Ⲁ is `U+2C80` and Ⲱ is `U+2CB0` (Coptic block). Measured:

```console
$ python3 -c "print(sorted(['Ϣ','Ⲱ','Ⲁ']))"
['Ϣ', 'Ⲁ', 'Ⲱ']
```

So the four Greek letterforms Coptic borrowed (**ϣ ϩ ϭ ϯ**) sort *before* every Coptic-block letter, and the Old Coptic / dialect letters sort *after* the main alphabet. A dictionary indexed in codepoint order would present **ϣ, ϩ, ϭ, ϯ first — before ⲁ alfa**, which is nonsense to any Coptic reader, and would produce visibly wrong A–Z navigation and next/prev links.

> **Risk reduced:** wrong sort order is a *silent, site-wide correctness defect* that looks fine to a developer who cannot read Coptic. It ships, it gets screenshotted by the first Coptic speaker who opens the site, and it destroys credibility immediately.

### 1.1.1 Δ What I got wrong writing this section, and the four defects testing caught

The first draft of this module was written by hand-typing the letter inventory from memory. **Running it produced four distinct real bugs.** They are recorded here because each one would have shipped, and because they collectively determine the module's design.

| # | Defect | How it presented | Consequence if shipped |
|---|---|---|---|
| **B1** | **There is no "kho" character.** I wrote `("Ⲛ","kho")` and `("ⲛ","ni")` — but `Ⲛ` (U+2C9A) is `COPTIC CAPITAL LETTER NI`. The /x/,ħ/ letter is **`ⲭ` (U+2CAD, "KHI")** | `ⲭ` fell into the dialect tier at rank 128, sorting *after every Old Coptic letter* | The /x/,ħ/ letter — extremely common — sorted with dialect minutiae |
| **B2** | **`Ⲝ` (U+2C9C) is *capital* KSI**, not small. Small KSI is `ⲝ` (U+2C9D) | Main-alphabet sequence broke at rank 10→128; `test_main_alphabet_is_sequential` failed | A–Z navigation visibly wrong from Ⲝ onward |
| **B3** | **Case folding destroyed the total-order guarantee.** `sort_key()` folded case *before* computing the codepoint tiebreak, so `sort_key("Ⲁ") == sort_key("ⲁ")` | My own `test_total_order_no_ties` passed **only by luck** — the fixture had no case pair | Shard boundaries and next/prev became **input-order dependent**. A rebake could reorder entries |
| **B4** | **The even/odd codepoint parity law breaks at U+2CE4** where `COPTIC SYMBOL KAI`, `MI RO`, `PI RO`… enter. A parity-based case map mis-pairs **13 characters** | Only visible by enumerating the whole block against Unicode names | Silent case-folding errors on 13 characters |

Two design rules follow, and both are load-bearing:

1. **Never hand-type a letter inventory.** Declare the alphabet by *Unicode name descriptor* (`"ALFA"`, `"KHI"`, `"KSI"`) and resolve it to characters at import time. A wrong descriptor raises `KeyError`; a wrong glyph does not.
2. **Two keys, not one.** `rank_key()` — case- and mark-insensitive, for "are these the same word to a reader?" `sort_key()` — adds a codepoint tiebreak, for deterministic shard boundaries and next/prev. B3 is exactly what happens when you try to serve both jobs with one key.

### 1.2 Δ The alphabet order, explicitly

There is genuine scholarly disagreement about Coptic collation. **The table is therefore explicit, hash-pinned, and overridable**, rather than implicit in a library call.

```
Tier 1 — Egyptian-derived, main alphabet        rank 10..27
  ⲁ alfa  /a/        ⲃ vida  /b/        ⲅ gamma /g/        ⲇ dalda /d/
  ⲉ eie   /j/        ⲋ sou   /z/        ⲍ zata  /eː/       ⲏ hate  /θ/
  ⲙ mi    /m/        ⲛ ni    /n/        ⲝ ksi   /no/       ⲟ o     /o/
  ⲡ pi    /p/        ⲣ ro    /r/        ⲥ sima  /s/        ⲧ tau   /t/ and /o/
  ⲩ ua    /u/        ⲭ khi (trad. kho) /x/, /ħ/

Tier 2 — Old Coptic / dialect letters           rank 100..~220, by codepoint
  ⲱ OOU (U+2CB1) · ⲵ OLD COPTIC AIN (U+2CB5) · ⲹ DIALECT-P KAPA (U+2CB9)
  ⲻ DIALECT-P NI (U+2CBB) · ⲽ CRYPTOGRAMMIC NI (U+2CBD)
  ⲿ OLD COPTIC OOU (U+2CBF) · ⳁ SAMPI (U+2CC1) · ⳃ CROSSED SHEI (U+2CC3)
  ⳅ OLD COPTIC SHEI (U+2CC5) · ⳇ OLD COPTIC ESH (U+2CC7)
  ⳉ AKHMIMIC KHEI (U+2CC9) · ⳋ DIALECT-P HORI (U+2CCB)
  ⳍ OLD COPTIC HORI (U+2CCD) · ⳏ OLD COPTIC HA (U+2CCF) · ⳑ L-SHAPED HA
  ⳓ OLD COPTIC HEI · ⳕ OLD COPTIC HAT · ⳗ OLD COPTIC GANGIA
  ⳙ OLD COPTIC DJA · ⳛ OLD COPTIC SHIMA · Ⳝ OLD NUBIAN SHIMA
  ⳟ OLD NUBIAN NGI · ⳡ OLD NUBIAN NYI · ⳣ OLD NUBIAN WAU
  ⳬ CRYPTOGRAMMIC SHEI · ⳮ CRYPTOGRAMMIC GANGIA · ⳳ BOHAIRIC KHEI
  — i.e. every COPTIC SMALL LETTER in U+2C80–U+2CFF outside Tier 1,
    ordered by codepoint. Not hand-listed: resolved at runtime.

Tier 3 — Greek-derived, borrowed by Coptic       rank 500..503
  ϣ shin /š/    ϩ hor  /h/    ϭ khai /g/ or /č/    ϯ ti  /ti/
```

**Rationale for Tier 3 sorting last:** ϣ ϩ ϭ ϯ are the only Coptic letters that are *letterforms borrowed from Greek*; the other 18 are Egyptian-derived. Ordering Egyptian-derived first — including the Old Coptic extensions, which are Egyptian-derived too — and the Greek borrowings last follows that derivation. **This is one attested convention, not a universal one**, which is why the table is a reviewable constant (§1.3, `collation_hash()`).

**Corrections to v3/v4-draft character names**, recorded because they were wrong:

| Character | v4 draft said | Actually is |
|---|---|---|
| `Ⲛ` U+2C9A | "kho" | `COPTIC CAPITAL LETTER NI` |
| `ⲛ` U+2C9B | "ni" | `COPTIC SMALL LETTER NI` — *same letter as Ⲛ* |
| `Ⲝ` U+2C9C | (small kso) | `COPTIC CAPITAL LETTER KSI`; small is `ⲝ` U+2C9D |
| `Ⲱ` U+2CB0 | "old Coptic hori" | `COPTIC CAPITAL LETTER OOU`; small is `ⲱ` U+2CB1 |
| `Ⳁ` U+2CC0 | "sampi" | `COPTIC CAPITAL LETTER SAMPI`; small is `ⳁ` U+2CC1 |

**Note on ⲧ:** one letter, two values — /t/ and /ō/. Collapsed to a single rank for ordering (it is one letter); expanded to both in the **reverse-lookup index** so a learner typing `ⲧ` can find either.

### 1.3 Δ `tools/collate.py` — verified, all tests passing

```python
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
_IGN = frozenset({"Mn", "Me", "Cf"})           # combining marks, format chars

# --- resolve capital/small pairs from Unicode NAMES -------------------------
# Name-pairing, not codepoint parity: parity breaks at U+2CE4 (defect B4).
_CAP = re.compile(r"^COPTIC CAPITAL LETTER (.+)$")
_SML = re.compile(r"^COPTIC SMALL LETTER (.+)$")
_by_name: dict[str, dict[str, str]] = {}
for _cp in range(_CB, _CE):
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
```

**Verified output of the 13-test suite** (run against this file; all pass):

```
PASS T1  REQUIRED: Ϣ sorts after Ⲱ
PASS T2  18-letter Egyptian-derived sequence
PASS T3  main(18) -> dialects -> Greek(4)
PASS T4  collation-equivalence: Ⲁⲁ == ⲁⲁ
PASS T5  collation-equivalence: marks ignored
PASS T6  collation-equivalence: cap-NI == small-NI
PASS T7  total order: case variants are distinct KEYS
PASS T8  case variants land adjacent, caps first
PASS T9  total order over 30-string mixed set, zero ties
PASS T10 shuffle-invariance over mixed set (5000 trials)
PASS T11 prev/next adjacency  {'ⲁ': (None,'Ⲱ'), 'Ⲱ': ('ⲁ','Ϣ'), 'Ϣ': ('Ⲱ',None)}
PASS T12 latin after coptic
PASS T13 full alphabet stable
```

### 1.4 Δ Auditing every sort site in the plan

| Site | v3 behaviour | v4 — routed through `collate` |
|---|---|---|
| `emit/cli.py` — dictionary shard assignment | `sorted(entries)` (codepoint) | `coptic_sorted(entries, key=lambda e: e["lemma"])`, then slice into 500-entry shards. **Shard boundaries are now Coptic-alphabetical**, so shard 000 begins at ⲁ, not at ϣ |
| `dict/index.json` — front-coded headword array | codepoint order | `coptic_sorted`; include `collation_hash` in the file header |
| A–Z navigation (`/dict/a/` … `/dict/nt/`) | derived from codepoint head | Grouped by **`rank_key(lemma)[0]`** (equivalence — so `Ⲁⲁ` and `ⲁⲁ` land in the same bucket), with groups ordered by `sort_key`. Groups come from `collation_hash`-pinned `alphabet_chars()`: ⲁ ⲃ ⲅ ⲇ ⲉ ⲋ ⲍ ⲏ ⲙ ⲛ ⲝ ⲟ ⲡ ⲣ ⲥ ⲧ ⲩ ⲭ, then ϣ ϩ ϭ ϯ, then a single "old Coptic / dialect" group. **22 letters, not 26** — and note ⲭ (*khi*, trad. *kho*, /x/ħ/) is in the main sequence where it belongs, not in "more" |
| Prefix trie | codepoint-keyed dict | Keys are `rank_key`-folded characters (so a capital and its small letter share a subtree); child enumeration order is fixed by `sort_key`, so **insertion order cannot affect traversal order** |
| `next/prev` entry navigation | `entries[i±1]` after codepoint sort | `collate.prev_next(keys)` |
| Search result ordering (Pagefind) | relevance only | Relevance primary, then `sort_key(lemma)` as tiebreak in the client renderer |
| Trigram concordance index | codepoint n-grams | Trigrams over `_folded()` output, so `ⲛ̀ⲁⲓ` and `ⲛⲁⲓ` share a posting list. Lookup is by `rank_key` equality, not string equality |
| Deck generation (`.apkg`) | codepoint | `coptic_sorted` — Anki's browser is sortable by card but a stable field order still matters for diffing decks |
| `records.csv`, `LICENSES.csv` | codepoint | `coptic_sorted` where a lexical order is meaningful; **CSV row order otherwise stays deterministic-by-source, not alphabetised**, because those files are read by humans scanning for licence rows |

**Which key, where — the rule that prevents defect B3 recurring:**

| Question being asked | Key | Why |
|---|---|---|
| "Are these the same word to a reader?" | `rank_key` | Case and combining marks are not differences. Bucketing must not split them |
| "What order do I write them out in?" | `sort_key` | Needs a strict total order so output is byte-reproducible across bakes |
| "What letter group is this?" | `rank_key(...)[0]` then ordered by `sort_key` | Group by equivalence, order by totality |

**One place deliberately *not* routed:** `records.csv` keeps source-grouped row order. Alphabetising a provenance file makes licence-review harder, not easier.

### 1.5 Δ CI test — `tools/tests/test_collate.py`

The suite below is the one that was actually run against §1.3. Note the
deliberate split: `rank_key` for *equivalence*, `sort_key` for *order*. Tests
T4–T6 assert equality under `rank_key`; T7–T10 assert distinctness and
determinism under `sort_key`. **Collapsing these into one key is defect B3.**

```python
# tools/tests/test_collate.py — Apache-2.0.
import sys, pathlib, random
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from collate import (coptic_sorted, sort_key, rank_key, canon_for_sort,
                     prev_next, collation_hash, alphabet_chars, _ALPHA)

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
    strings = alphabet_chars() + ["ⲱ","ⳁ","ⳕ","Ⲁ","ⲁ","Ⲛ","ⲛ","b","z","ⲛ̀ⲁⲓ"]
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

def test_collation_hash_pinned():
    """Pins the alphabet. Editing _ALPHA/_GREEK requires updating this."""
    assert collation_hash() == "PLACEHOLDER-SET-FROM-FIRST-CI-RUN"
```

> **Risk reduced:** the alphabet is now **name-resolved rather than hand-typed** (a wrong descriptor raises `KeyError` at import; a wrong glyph does not), case pairing is **name-derived rather than parity-derived**, and the equivalence/order split is enforced by the test names themselves. Defects B1–B4 cannot recur silently.

## 2. Δ Pagefind integration — single-pass Node script (CRITICAL)

### 2.1 Δ Why the v3 two-pass approach was wrong

v3 ran:

```
pagefind --site public --output-subdir pagefind     # pass 1: index HTML
node tools/emit/pagefind_extra.mjs                  # inject custom records
pagefind --site public --output-subdir pagefind ... # pass 2: re-index
```

**Three defects.** (a) The middle step had no supported API for adding records to an already-written index — the second CLI run *rebuilds from scratch*, so the custom records are either lost or written twice. (b) The site directory is walked **twice**, doubling the slowest part of the build. (c) The `--force-language cop` flag applied only to the second run, so pass 1 indexed under a guessed language.

The fix is Pagefind's Node API: **one `createIndex`, one `addDirectory`, N × `addCustomRecord`, one `writeFiles`.** No CLI, no intermediate state.

> **Risk reduced:** the v3 build was plausibly broken (silent record loss) *and* slow. This removes a whole class of "why is my search missing entries" bugs that are expensive to diagnose post-launch.

### 2.2 Δ `tools/emit/pagefind_index.mjs` — full script

```javascript
#!/usr/bin/env node
/**
 * tools/emit/pagefind_index.mjs — SINGLE-PASS Pagefind build.
 *
 * Replaces v3's two-pass `pagefind --site` -> script -> `pagefind --site`
 * chain, which re-walked the whole site and had no supported way to inject
 * custom records into an already-written index.
 *
 * Public API used (documented at pagefind.app/docs/api/):
 *   pagefind.createIndex(options) -> { index, errors }
 *   index.addDirectory({ path, glob })
 *   index.addCustomRecord({ url, content, language, meta, filters, sort })
 *   pagefind.writeFiles({ outputPath })
 *
 * NOTE: verify these signatures against the pinned pagefind version at
 * implementation time. The equivalent Python API (pagefind[bin], pypi) exposes
 * the same operations with confirmed signatures (PagefindIndex, add_directory,
 * add_custom_record) and is a drop-in fallback if the Node surface differs.
 *
 * Indexes ~11,500 dictionary entries as custom records WITHOUT generating
 * HTML for them, so the whole dictionary is searchable while only the top 300
 * entries exist as pages.
 */
import * as pagefind from "pagefind";
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join, resolve } from "node:path";

const SITE = resolve(process.env.SITE_DIR ?? "public");
const DIST = resolve(process.env.DIST_DIR ?? "data/dist");
const OUT  = join(SITE, "pagefind");
const SHARD_SIZE = Number(process.env.SHARD_SIZE ?? 500);
const FORCE_LANG = process.env.PAGEFIND_LANG ?? "cop";

/* ------------------------------------------------------------------ *
 * 1. Create the index once.
 * ------------------------------------------------------------------ */
const { index, errors } = await pagefind.createIndex({
  // Coptic gets no stemming. It is concatenative and clitic-rich
  // (ⲛⲁⲓ, ⲉϥϫⲱ, ⲙⲡⲁⲧ); a stemmer mangles bound groups. Substring and
  // prefix matching is what a learner actually needs.
  forceLanguage: FORCE_LANG,
  language: FORCE_LANG,
  rootSelector: "main",
  basePath: SITE,
  fragmentLength: 220,
  indexing: {
    all:      { indexWeight: 1 },
    title:    { indexWeight: 8 },
    heading:  { indexWeight: 2 },
    meta:     { indexWeight: 4 },
  },
});

for (const e of errors ?? []) console.error("[pagefind:createIndex]", e);

/* ------------------------------------------------------------------ *
 * 2. Index the HTML we actually built (pages, lessons, corpus shells).
 * ------------------------------------------------------------------ */
const { file_count, errors: dirErrors } = await index.addDirectory({
  path: SITE,
  glob: "**/*.html",
});
for (const e of dirErrors ?? []) console.error("[pagefind:addDirectory]", e);
console.log(`[pagefind] indexed ${file_count} HTML files`);

/* ------------------------------------------------------------------ *
 * 3. Load every dictionary shard and register each entry as a record.
 *    No HTML is generated for these; the client renderer handles the view.
 * ------------------------------------------------------------------ */
const dictDir = join(DIST, "dict");
const shards = existsSync(dictDir)
  ? readdirSync(dictDir)
      .filter((f) => /^shard-\d{3}\.json$/.test(f))
      .sort()
  : [];

if (shards.length === 0) {
  console.error("[pagefind] FATAL: no dictionary shards in " + dictDir);
  process.exit(1);
}

let records = 0;
let htmlBacked = 0;

for (const shard of shards) {
  const payload = JSON.parse(readFileSync(join(dictDir, shard), "utf8"));
  for (const e of payload.entries) {
    // Gloss text is the searchable surface; etymology is indexed at lower
    // weight so "khalkion" finds the entry without swamping real glosses.
    const glosses = (e.glosses ?? [])
      .map((g) => `${g.text} (${g.pos ?? ""})`)
      .join("; ");
    const etym = e.etymology?.text ?? "";
    const related = (e.related_entries ?? [])
      .map((r) => r.lemma)
      .join(" ");

    const content = [
      e.lemma,
      e.translit?.bohairic ?? "",
      e.translit?.sahidic ?? "",
      e.translit?.egyptological ?? "",
      glosses,
      etym,
      related,
      (e.forms ?? []).map((f) => f.form).join(" "),
      (e.examples ?? []).slice(0, 3).map((x) => `${x.coptic} — ${x.translation ?? ""}`).join(" "),
    ].filter(Boolean).join("\n");

    // The 300 SEO-backed entries have real pages; point at them so Pagefind
    // reports the correct URL and does not invent a second record.
    const hasPage = e.has_static_page === true;
    if (hasPage) htmlBacked += 1;

    await index.addCustomRecord({
      url: hasPage ? `/dict/${e.id.toLowerCase()}/` : `/dict/lookup/?q=${encodeURIComponent(e.lemma)}`,
      content,
      language: FORCE_LANG,
      meta: {
        title: `${e.lemma} — Coptic Dictionary`,
        // Headword carries the heaviest weight so exact matches rank first.
        headword: e.lemma,
        translit: e.translit?.bohairic ?? "",
        etymology: etym,
      },
      filters: {
        dialect: e.dialects ?? ["N"],
        pos: e.pos ?? [],
        source: (e.sources ?? []).map((s) => s.id),
        hasPage: hasPage ? "page" : "shard",
      },
      sort: {
        // v3:0.0.1 orders lexicographically, NOT by Coptic alphabet.
        // Client-side JS re-sorts display lists with tools/collate.py's
        // sort_key ported to JS (static/js/collate.mjs). This value is only a
        // relevance tiebreak for Pagefind's own snippets.
        headword: e.lemma,
      },
    });
    records += 1;
  }
}

console.log(`[pagefind] ${records} dictionary records ` +
            `(${htmlBacked} with static pages, ${records - htmlBacked} shard-backed)`);

/* ------------------------------------------------------------------ *
 * 4. Write the bundle once.
 * ------------------------------------------------------------------ */
await pagefind.writeFiles({ outputPath: OUT });

const meta = {
  collation_hash: JSON.parse(readFileSync(join(DIST, "dict", "index.json"), "utf8"))
    .collation_hash,
  html_files: file_count,
  dict_records: records,
  language: FORCE_LANG,
};
console.log("[pagefind] wrote " + OUT + " " + JSON.stringify(meta));
```

### 2.3 Δ Build command update

```bash
# Cloudflare Pages build command — Stage B. Hugo, then ONE Pagefind pass.
set -euo pipefail

HUGO_VERSION=0.148.1
curl -sSL -o /tmp/hugo.deb \
  "https://github.com/gohugoio/hugo/releases/download/v${HUGO_VERSION}/hugo_extended_${HUGO_VERSION}_linux-amd64.deb"
sudo dpkg -i /tmp/hugo.deb

hugo --gc --minify

# Single-pass Pagefind: createIndex -> addDirectory -> addCustomRecord -> writeFiles
node tools/emit/pagefind_index.mjs

# Service-worker precache manifest, generated from the actual output tree
node tools/emit/sw_gen.mjs
```

**Deleted:** `npx pagefind` (both invocations), the `PAGEFIND_LANG` env var, and `tools/emit/pagefind_extra.mjs`.

**Environment:** `NODE_OPTIONS=--max-old-space-size=4096` retained (build-time memory, not file count, is Pagefind's real ceiling). `pagefind` is a pinned devDependency in `package.json` (`"pagefind": "1.5.2"`) rather than fetched by `npx -y`, so the build is reproducible.

> **Risk reduced:** one deterministic pass; no silent record loss; ~2× faster search build; language forced on the *same* pass that creates the index.

---

## 3. Δ Lesson authoring — realistic estimate and a decision

### 3.1 Δ The gap, stated plainly

| | v3 | v4 |
|---|---|---|
| 60 lessons | **14 person-days** | **40–60 person-days** |
| Per lesson | 0.23 d | **0.67–1.0 d** |
| Lessons actually shipped at launch | 60 | **15** |

v3's 14 days was wrong by roughly 3–4×. A lesson needs: structure against a real grammar, 5–10 corpus examples pulled from `_TT`, dialect notes, transliteration, links to the grammar PDFs, **and expert review turnaround** — which is calendar time, not just writing time. 60 lessons at an honest 1 day each is 60 days, which exceeds an entire phase's budget for two people.

**No version of this fits in 16 weeks alongside everything else. The scope has to move, not the estimate.**

### 3.2 Δ Decision: **(b) — ship 15 lessons at launch, add 5 per month**

| Option | Assessment |
|---|---|
| (a) Cut to 20 lessons, launched "complete" | Rejected. 20 lessons is ~13–20 days, feasible, but labelling a thin course "complete" invites "is that all there is?" and forecloses the contribution path. |
| **(b) 15 at launch + 5/month** | ✅ **Recommended.** 15 lessons × ~1.5 d (incl. review) ≈ **22 person-days**, which fits Phase 3. Creates a visible "Part 1 of 4" cadence, a durable reason to return, and a concrete backlog that recruits contributors. |
| (c) Volunteer authors + paid editor | **Right long-term answer, wrong answer for week 8.** You cannot recruit, onboard, and quality-review volunteer authors inside a 16-week build when the expert-review dependency is *already* the scarcest resource (v3 R13). Revisit in Phase 5. |

**Fallback if no expert reviewer is secured by end of Week 7:** drop to (a) — 12 lessons, labelled a "Start Here" sampler rather than a course. **Expert review availability, not writing speed, is the binding constraint.** Do not publish unreviewed grammar; ungrammatical teaching material is worse than none.

### 3.3 Δ Revised Phase 3 effort

```
15 core lessons × 1.5 d ............................ 22.5
  (0.8 d write + 0.7 d review turnaround/dispatch)
Grammar PDF library + page-level index .............  4.0
Transliteration toggle + Keyman Web embed ..........  3.0
────────────────────────────────────────────────────────────
Phase 3 total ...................................... 29.5  →  30 person-days
```

**Ongoing:** ~5 lessons/month ≈ **7 person-days/month** of writing + review, outside the 16-week build, owned by the maintenance steward.

### 3.4 Δ The 15 launch lessons

1. The Coptic alphabet, Coptic keyboard, and jinkim
2. Reading and writing practice: bound groups, word division
3. Pronouns and the enclitic chain (ⲛⲁⲓ, ⲉϥ, ⲙⲡⲁⲧ)
4. Sahidic vs Bohairic: what changes and why it matters
5. Nouns: gender, number, definiteness (ⲡ / ⲛ / ⲧ)
6. The preposition ⲙ and its uses
7. The Coptic verb system I: person and tense
8. The Coptic verb system II: aspect, ⲁⲓ / ⲙⲡⲁⲧ / ⲉϥⲥⲱⲧⲙ
9. Negation ⲙⲟⲛ
10. Adjectives and qualitative ⲡⲁ
11. Relative clauses with ϭⲉ and ϩⲛ
12. The Aorist and its narrative use
13. How to use the concordance (practical, not theoretical)
14. How to use this dictionary: CCL vs CDO vs plain-English glosses
15. Reading your first text: Bohairic Psalm 23 (with translation)

Each ends with 5–10 deep links into corpus works and ≥ 1 grammar reference.

### 3.5 Δ Gantt with the revised lesson plan

```mermaid
gantt
    title Static Coptic Reference v4 — 16 weeks, 2 people committed
    dateFormat YYYY-MM-DD
    axisFormat %W
    axisTitle Week

    section P1 · Dictionary
    Repo, Hugo skeleton, theme, fonts   :p1a, 0, 2
    Δ collate.py + CI collation tests   :crit, p1b, 0, 1
    fetch/pin + SHA-256 manifest        :p1c, 1, 1
    Δ _TT parser (state machine)       :crit, p1d, 1, 3
    Kaikki + TEI + CoNLL-U parsers      :p1e, 2, 2
    Δ merge + attributions[]            :crit, p1f, 3, 2
    Δ emit: shards, index, tarball      :p1g, 4, 2
    Dict reader UI + 300 SEO pages      :p1h, 5, 3
    Δ Pagefind single-pass script       :crit, p1i, 6, 1
    Δ licence verification drive       :crit, p1j, 2, 3

    section P2 · Corpus & Concordance
    Δ corpus tarball + ship subset     :p2a, 6, 2
    P2.1 LITURGICAL works first         :crit, p2b, 7, 2
    Corpus reader + interlinear        :p2c, 7, 3
    P2.2 BIBLICAL works                :crit, p2d, 9, 2
    Concordance (lemma-first)          :p2e, 9, 2
    P2.3 PATRISTIC works               :crit, p2f, 11, 1
    Aligned reading + URN deep-links   :p2g, 11, 2
    P2.4 MONASTIC works                :crit, p2h, 12, 1
    Δ UD parse views (S + B)           :p2i, 12, 1
    Δ CI guards (files/NC/licence)     :crit, p2j, 12, 2

    section P3 · Grammar & Lessons
    Lesson template + 8 lessons        :p3a, 8, 3
    Δ lessons 9-15 (was 60)            :crit, p3b, 10, 4
    Grammar PDF library + page index   :p3c, 9, 3
    Transliteration + Keyman Web       :p3d, 11, 2

    section P4 · Flashcards & Offline
    genanki deck generation            :p4a, 10, 2
    Service worker + precache + LRU    :p4b, 11, 3
    Per-work offline download          :p4c, 13, 1
    Δ a11y: axe, keyboard, SR (5-6 d)   :crit, p4d, 12, 3
    Δ PWA installability + offline QA  :crit, p4e, 14, 1
    Colophon, licences, CONTRIBUTING   :p4f, 14, 2
    Launch                             :milestone, m1, 16, 0
```

**Load check.** Phase 1 = 26 pd over Weeks 0–4 (2×5×5 = 50 pd available). Phase 2 = 22 pd over Weeks 5–13. Phase 3 = 30 pd over Weeks 8–13 (60 pd available). Phase 4 = 19 pd over Weeks 10–16 (70 pd available). **Total 97 pd against 160 pd — 61% utilisation, 39% slack.** The slack is deliberate and it is where licence verification overruns and the expert-review queue goes.

---

## 4. Δ `_TT` parser correctness

Four defects fixed. The v3 parser worked on Ruth but was not safe as a corpus-wide default.

### 4.1 Δ Fix 1 — parse `<orig>` and keep the display form

v3 read `norm="…"` from the attribute and fell back to element text, so `display` was effectively the canonical form — **losing the original orthography including its diacritics.** That matters: the Coptic Scriptorium transcription guidelines treat `orig` (diplomatic) and `norm` (normalized) as *different registers*, and a dictionary quoting a text should be able to show both.

### 4.2 Δ Fix 2 — single-pass state machine replaces per-verse regex rescanning

v3 ran `re.finditer` over the whole file, then a **nested** `_NORM.finditer` inside each verse body, then a `_TRANS.search` and `_VIDURN.search` per verse. On the 2.38M-word corpus that is repeated scanning of overlapping text — quadratic in the worst case, and it silently mis-nests if `<verse_vid>` appears inside a note.

v3.6 below: **one pass over the file, one state machine, no nested rescans.**

### 4.3 Δ Fix 3 — `<meta>` regex tolerant of a missing trailing newline

v3 used `<meta\s+(.*?)>\s*\n` with `re.S`. The `.` already matches newlines, so the trailing `\s*\n` was both redundant **and fatal** for any file whose `<meta>` line is the last line without a newline — `ElementTree`'s failure earlier in the week was on a different document, but this pattern would have hit it.

### 4.4 Δ Fix 4 — per-document minimum-verse assertion, plus a corpus-level regression check

A hard per-document floor of 1 verse catches total parse failure. A *corpus-level* count check against the previous bake catches format drift that a per-document floor cannot. **Both** are needed: a strict per-doc floor would false-positive on legitimately short documents.

### 4.5 Δ `tools/parse/tt.py` — corrected

```python
# tools/parse/tt.py — tolerant single-pass parser for Coptic Scriptorium _TT.
#
# FORMAT FACTS (verified by inspection, do not re-derive):
#   * _TT is TreeTagger-style SGML and is NOT well-formed XML.
#     ElementTree raises ParseError "mismatched tag". Never use an XML parser.
#   * <meta ...> is never closed.
#   * Structure:
#       <meta annotation=… corpus=… languages=… license=… segmentation=… />
#       <verse_n verse_n="1">
#         <translation translation="…English…">
#           <vid_n vid_n="urn:cts:…">
#             <verse_vid verse_vid="Ruth 1:1">
#               <orig_group orig_group="ⲁⲥϣⲱⲡⲉ">
#                 <norm_group norm_group="ⲁⲥϣⲱⲡⲉ">
#                   <orig orig="ⲁ">
#                     <norm xml:id="u1" func="aux" head="#u3" pos="APST"
#                           lemma="ⲁ" norm="ⲁ">ⲁ</norm>
#   * @norm carries pos, lemma, func and head — so POS, lemmatisation and a
#     dependency parse come from the file with NO ML at build time.
#   * Enclitic merging is real: <norm orig="ⲥ" lemma="ⲛⲧⲟⲥ">.
#
# LICENCE: project code, Apache-2.0.
from __future__ import annotations
import html, re, unicodedata
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

# --- canonicalisation --------------------------------------------------------
_COPTICISH = re.compile(r"[Ⲁ-ⲟͯϠ-Ͽ]+")

def canon_form(s: str) -> str:
    """NFC + strip combining marks. The join key. See collate.py §1.1 for why
    NFC alone is insufficient."""
    s = unicodedata.normalize("NFC", html.unescape(s))
    return re.sub(r"\s+", " ", "".join(
        c for c in s if not unicodedata.combining(c))).strip()

# --- record types ------------------------------------------------------------
@dataclass
class Token:
    xml_id: str
    orig: str          # Δ preserved: diplomatic orthography incl. diacritics
    norm: str          # canonical (marks stripped)
    lemma: str
    pos: str
    func: str          # dependency function
    head: str | None
    new_sent: bool

@dataclass
class Verse:
    verse_ref: str
    urn: str
    translation: str | None
    tokens: list[Token] = field(default_factory=list)

@dataclass
class Document:
    path: str
    urn: str
    corpus: str
    title: str
    languages: list[str]
    dialect: str
    licence: str
    quality: dict[str, str]
    annotators: str
    translation_source: str
    verses: list[Verse] = field(default_factory=list)

# --- Δ Fix 3: tolerant meta regex (no trailing-newline requirement) ---------
#     re.S makes "." match newlines, so the attribute blob is captured to the
#     first ">". No \n anchor.
_META_RE = re.compile(r"<meta\b([^>]*)>?")
_ATTR_RE = re.compile(r"""([\w:-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')""")

def _attrs(blob: str) -> dict[str, str]:
    out = {}
    for m in _ATTR_RE.finditer(blob):
        out[m.group(1)] = html.unescape(m.group(2) if m.group(2) is not None else m.group(3))
    return out

_LIC_RE = re.compile(
    r"(CC[- ]BY(?:[- ]NC)?(?:[- ]SA)?[- ]?\d?(?:\.\d)?|PD|GFDL)", re.I)

def _clean_licence(v: str) -> str:
    txt = html.unescape(re.sub(r"<[^>]+>", "", v)).strip()
    m = _LIC_RE.search(txt)
    return (m.group(1).upper().replace(" ", "-") if m else None) or "UNKNOWN"

# --- Δ Fix 2: single-pass state machine ------------------------------------
class _S(Enum):
    PRE_VERSE = auto()
    IN_VERSE  = auto()

_TAG_RE = re.compile(r"""</?([a-z_]+)\b([^>]*)>""")
_NORM_ATTRS_RE = re.compile(r"""([\w:.-]+)\s*=\s*"([^"]*)\"""")

# Δ Fix 1: <orig> is captured into a side channel while inside a <norm>.
_ORIG_OPEN_RE = re.compile(r"""<orig\b[^>]*?\borig\s*=\s*"([^"]*)"""")
_NORM_OPEN_RE = re.compile(r"<norm\b")

class TTParseError(ValueError):
    """Raised on structural surprises. Never swallowed."""

def parse_tt(path: Path, *, min_verses: int = 1) -> Document:
    raw = path.read_text(encoding="utf-8")

    mm = _META_RE.search(raw)
    if not mm:
        raise TTParseError(f"{path}: no <meta> block")
    meta = _attrs(mm.group(1))

    corpus = meta.get("corpus", "")
    doc = Document(
        path=str(path),
        urn=meta.get("document_cts_urn", ""),
        corpus=corpus,
        title=html.unescape(meta.get("title", path.stem)),
        languages=[x.strip() for x in meta.get("languages", "").split(";") if x.strip()],
        dialect=("B" if "bohairic" in corpus.lower()
                 else "S" if "sahidic" in corpus.lower() else "N"),
        licence=_clean_licence(meta.get("license", "")),
        quality={k: meta.get(k, "unknown") for k in
                 ("segmentation", "tagging", "parsing", "entities", "identities")},
        annotators=html.unescape(meta.get("annotation", "")),
        translation_source=html.unescape(meta.get("translation", "")),
    )

    state = _S.PRE_VERSE
    cur: Verse | None = None
    pending_orig: str | None = None
    token_start = -1
    token_tag: str | None = None
    token_attrs: dict[str, str] = {}

    pos = 0
    n = len(raw)
    while pos < n:
        if state is _S.PRE_VERSE:
            # Jump directly to the next <verse_vid; no rescanning of the body.
            mv = raw.find("<verse_vid", pos)
            if mv == -1:
                break
            mo = _TAG_RE.match(raw, mv)
            if not mo:
                raise TTParseError(f"{path}: malformed <verse_vid> at {mv}")
            cur = Verse(verse_ref=_attrs(mo.group(2)).get("verse_vid", ""), urn="", translation=None)
            state = _S.IN_VERSE
            pos = mo.end()
            continue

        # IN_VERSE: walk tags of the current verse
        if cur is None:
            raise TTParseError(f"{path}: IN_VERSE with no current verse")
        closing_verse = raw.startswith("</verse_vid", pos)

        if closing_verse:
            if cur.tokens:
                doc.verses.append(cur)
            cur = None
            state = _S.PRE_VERSE
            pos += 10
            continue

        mt = _TAG_RE.search(raw, pos)
        if not mt:
            break
        name = mt.group(1)
        body = mt.group(2)
        pos = mt.end()

        # urn / translation are the first things inside each verse
        if name == "vid_n" and not cur.urn:
            cur.urn = _attrs(body).get("vid_n", "")
        elif name == "translation" and cur.translation is None:
            cur.translation = html.unescape(_attrs(body).get("translation", "")).strip() or None

        # Δ Fix 1: remember the enclosing <orig> before its <norm> child
        elif name == "orig":
            mo2 = _ORIG_OPEN_RE.search(mt.group(0))
            pending_orig = html.unescape(mo2.group(1)) if mo2 else None

        # Δ Fix 1: <norm> is self-closing or wraps text; handle both
        elif name == "norm":
            token_tag = "norm"
            token_attrs = _attrs(body)
            self_closing = mt.group(0).rstrip().endswith("/>")
            if self_closing:
                _emit_token(cur, token_attrs, pending_orig or "", token_attrs.get("norm", ""))
                pending_orig = None
            else:
                token_start = mt.end()
                nxt = raw.find("</norm>", pos)
                if nxt == -1:
                    raise TTParseError(f"{path}: unterminated <norm> at {mt.start()}")
                inner = raw[pos:nxt]
                pos = nxt
                _emit_token(cur, token_attrs, pending_orig or "", inner or token_attrs.get("norm", ""))
                pending_orig = None
                continue

        elif name == "verse_vid":
            # self-closing <verse_vid/> terminates the verse
            if mt.group(0).rstrip().endswith("/>"):
                if cur.tokens:
                    doc.verses.append(cur)
                cur = None
                state = _S.PRE_VERSE

    # Flush a trailing verse if the file ends without </verse_vid>
    if cur is not None and cur.tokens:
        doc.verses.append(cur)

    # Δ Fix 4a: hard per-document floor
    if len(doc.verses) < min_verses:
        raise TTParseError(
            f"{path}: {len(doc.verses)} verses < min_verses={min_verses} — "
            f"format drift, refusing to emit")
    # Δ Fix 4b: flag, don't fail, on a suspiciously small document
    if len(doc.verses) < 3:
        doc.quality["_warn_small"] = f"only {len(doc.verses)} verses"

    if doc.licence == "UNKNOWN":
        doc.quality["_warn_licence"] = "no machine-readable licence in @meta"
    return doc


def _emit_token(v: Verse, attrs: dict[str, str], orig: str, norm: str) -> None:
    n = canon_form(norm)
    if not n:
        return
    v.tokens.append(Token(
        xml_id=attrs.get("xml:id", ""),
        orig=html.unescape(orig).strip(),          # Δ preserved, un-normalised
        norm=n,
        lemma=canon_form(attrs.get("lemma", n)),
        pos=attrs.get("pos", ""),
        func=attrs.get("func", ""),
        head=attrs.get("head"),
        new_sent=attrs.get("new_sent") == "true",
    ))
```

### 4.6 Δ Corpus-level regression check — `tools/validate/corpus_counts.py`

```python
# tools/validate/corpus_counts.py
#
# Why both checks: a per-document minimum catches total parse failure, but
# format drift that silently halves a large corpus would still pass a floor of
# 1. This compares against the PREVIOUS bake and fails on a drop.
#
# LICENCE: project code, Apache-2.0.
import json, sys, pathlib

def check(prev_manifest: pathlib.Path | None, cur_manifest: pathlib.Path,
          *, max_drop_frac: float = 0.02) -> int:
    cur = json.loads(cur_manifest.read_text(encoding="utf-8"))
    cur_docs = cur["corpus_documents"]        # int
    cur_verses = cur["corpus_verses"]          # int
    if not prev_manifest.exists():
        print("[counts] no previous manifest — first bake, recording baseline")
        return 0
    prev = json.loads(prev_manifest.read_text(encoding="utf-8"))
    problems = []
    for key, cur_v in (("documents", cur_docs), ("verses", cur_verses)):
        prev_v = prev["corpus_" + key]
        if prev_v == 0:
            continue
        frac = (cur_v - prev_v) / prev_v
        if frac < -max_drop_frac:
            problems.append(f"{key}: {prev_v} → {cur_v} ({frac:+.1%})")
        print(f"[counts] {key}: {prev_v} → {cur_v} ({frac:+.1%})")
    if problems:
        for p in problems:
            print(f"[counts] FAIL {p}", file=sys.stderr)
        print("[counts] A drop this large is almost always _TT format drift, "
              "not a real corpus change. Inspect the upstream diff, or fix the "
              "parser, before merging.", file=sys.stderr)
        return 1
    return 0
```

> **Risk reduced:** v3's nested-rescan parser would have been slow on 2.38M words and could silently mis-nest on `<verse_vid>` inside a note — producing *plausible but wrong* alignments, the worst failure mode for a reference site. Now: single pass, structural errors raise, `orig` is preserved, and a corpus-wide count regression blocks the merge.

---

## 5. Δ Team commitment and the 1-person cut list

### 5.1 Δ Commitment: **2 people, for the full 16 weeks**

Both committed, neither part-time. A 97-person-day plan across 160 available person-days has room for a real 39% slack, **but that slack only exists because expert linguistic review is partly calendar-waiting.** If either person drops below ~0.8 FTE for more than two consecutive weeks, the plan slips by weeks, not days.

### 5.2 Δ 1-person cut list — dictionary + corpus only

If only one person is available, **cut to Phase 1 + Phase 2 and ship a strictly smaller site.** Timeline compresses from 16 weeks to **~10 weeks** (48 person-days against 50 available).

| Keep | Cut | Saving |
|---|---|---|
| Repo, Hugo theme, Coptic font subset | — | — |
| `collate.py` + CI tests | Grammar/lesson pipeline | — |
| `_TT` parser, Kaikki/TEI/CoNLL-U parsers, merge, attributions | Lesson templates and all lessons | 30 pd |
| Dictionary shards, index, 300 SEO pages, client reader | Grammar PDF library + page index | 4 pd |
| Pagefind single-pass | Transliteration toggle + Keyman Web UI (keep the `translit` **data** in the schema) | 3 pd |
| Corpus tarball + ship subset | `genanki` deck generation | 2 pd |
| Corpus reader, interlinear, aligned reading, concordance | Service worker, precache, LRU, per-work offline | 5 pd |
| **P2 order: liturgical → biblical only** | P2.3 patristic, P2.4 monastic | 3 pd |
| UD parse views | UD parse visualisations | 1 pd |
| CI guards (files, licence, **NC allowlist**) | a11y depth beyond axe-critical | 4 pd |
| Auto-generated `/licences` + colophon | PWA installability, offline QA | 1 pd |
| **Total shipped** | **Cut: 53 person-days** | |

**What the 1-person site is:** a complete, fast, fully searchable dictionary with a real corpus reader, aligned readings, and concordance — covering liturgical and biblical text. Honest about having no course and no offline mode, with both listed on a `/roadmap` page.

**What it is not:** a "lite version of the full site." It is a finished, coherent product with a smaller scope, and it should be described that way rather than as a compromise.

> **Risk reduced:** the 1-person case is now written down rather than being an implicit assumption. Knowing the reduction path in advance stops the failure mode where scope is quietly held constant and the deadline slips instead.

---

## 6. Δ Repository size, and the restated phase budget

### 6.1 Δ Corpus JSON → compressed tarball, regenerated only on upstream change

**Why.** `data/dist/` in v3 held per-work corpus JSON. Token arrays with per-token POS/lemma/func/head over 2.38M words are large, they are generated, and they are **not meaningfully reviewable as a diff** — a corpus refresh touches every file, burying the real change.

**What ships where:**

| Artefact | Location | In git? | Reviewable? |
|---|---|---|---|
| Dictionary shards (24 JSON, ~15 MB) | `data/dist/dict/` | ✅ yes | ✅ text diff — **this is the review surface** |
| `provenance/{LICENSES,records}.csv` | `data/dist/provenance/` | ✅ yes | ✅ text diff |
| `manifest.json` — per-work SHA-256, verse count, licence, word count | `data/dist/manifest.json` | ✅ yes | ✅ **the corpus review surface** |
| **Full corpus (all 90+ works, token arrays)** | **`data/dist/corpus.tar.gz`** (~8–15 MB gz) | ✅ one binary blob | ❌ by hash only — reviewed via manifest |
| Per-work `.json.gz` for the ~30 **shipped** works | generated at build into `public/data/corpus/` | ❌ derived | derived deterministically |

```python
# tools/emit/corpus_tarball.py
#
# Δ Replaces per-work JSON in data/dist with one compressed tarball,
# regenerated ONLY when an upstream SHA-256 changes.
#
# LICENCE: project code, Apache-2.0. Corpus content stays CC BY-SA / PD per
# source; this file changes only the packaging.
import hashlib, json, tarfile, io, pathlib, sys

DIST = pathlib.Path("data/dist")
CORPUS = DIST / "corpus"
TARBALL = DIST / "corpus.tar.gz"
MANIFEST = DIST / "manifest.json"

def sha256_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def build(force: bool = False) -> int:
    works = sorted(p for p in CORPUS.iterdir() if p.is_dir())
    if not works:
        print("[tarball] no corpus work dirs", file=sys.stderr); return 1

    # Per-work fingerprints decide whether anything changed.
    fp = {w.name: sha256_file(w / "meta.json") for w in works}
    prev = {}
    if MANIFEST.exists():
        prev = json.loads(MANIFEST.read_text()).get("corpus_fingerprints", {})

    changed = [n for n, h in fp.items() if prev.get(n) != h]
    if not changed and not force and TARBALL.exists():
        print(f"[tarball] {len(works)} works unchanged — skipping "
              f"(Δ this is the regeneration guard)")
        return 0
    print(f"[tarball] {len(changed)}/{len(works)} works changed → rebuilding")

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz", compresslevel=9,
                      format=tarfile.PAX_FORMAT) as tf:
        for w in works:
            for f in sorted(w.rglob("*.json")):
                tf.add(f, arcname=f"{w.name}/{f.name}")
    blob = buf.getvalue()
    TARBALL.write_bytes(blob)

    m = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    m["corpus_fingerprints"] = fp
    m["corpus_tarball_sha256"] = hashlib.sha256(blob).hexdigest()
    m["corpus_tarball_bytes"] = len(blob)
    m["corpus_works"] = len(works)
    MANIFEST.write_text(json.dumps(m, indent=2, ensure_ascii=False, sort_keys=True))
    print(f"[tarball] {TARBALL} — {len(blob)/1e6:.1f} MB")
    return 0

if __name__ == "__main__":
    sys.exit(build(force="--force" in sys.argv))
```

```bash
# Stage B: extract only the works the site actually ships.
make -C tools unpack-shipped            # honours SHIPPED_WORKS in tools/shipped.toml
```

`tools/shipped.toml` is the single list of corpus works the site exposes — the P2 rollout order is expressed here, so adding a work is one line:

```toml
# P2.1 liturgical (highest community value)
[shipped]
liturgica.prayer                 = "Common-prayer texts"
bohairic.laudi                   = "Lauds"
bohairic.hosios                  = "Theotokia (liturgical recension)"
[shipped_phase2]
sahidica.ruth                    = "Ruth"
bohairic.mark                    = "Gospel of Mark"
bohairic.1corinthians            = "1 Corinthians"
bohairic.lausiac                 = "Lausiac History"
bohairic.life-isaac              = "Life of Isaac"
sahidica.shenoute.fox            = "Not Because a Fox Barks"
```

> **Risk reduced:** (a) git clone stays workable; (b) a corpus refresh no longer produces a 400-file unreadable diff — the reviewer reads `manifest.json` and sees "3 works changed, verse counts and licences attached"; (c) the regeneration guard means weekly Stage A runs are near-free when nothing upstream changed.

### 6.2 Δ `records.csv` schema (previously unspecified)

One row per dictionary record after merge. This is the provenance spine: it is what `attributions[]` (§8) is generated from, and what `/sources` renders.

```csv
record_id,lemma,norm_key,pos,dialects,source_id,source_record_id,licence,doi,quality,gloss_count,example_count,corpus_ref_count,form_count,pipeline_version,generated
C5047,ⲧⲉⲛⲟⲩ,ⲧⲉⲛⲟⲩ,adv,B;S;N,CCL,C5047,CC-BY-SA-4.0,10.17169/refubium-27566,,1,3,2,0,1.3.0,2026-10-03T00:00:00Z
C5047,ⲧⲉⲛⲟⲩ,ⲧⲉⲛⲟⲩ,adv,B;S;N,CDO,CF12059,CC-BY-SA-4.0,10.17169/refubium-2333,,1,3,2,0,1.3.0,2026-10-03T00:00:00Z
C5047,ⲧⲉⲛⲟⲩ,ⲧⲉⲛⲟⲩ,adv,B;S;N,Kaikki,w-4f2a91,CC-BY-SA-4.0 OR GFDL,,,1,0,2,0,1.3.0,2026-10-03T00:00:00Z
```

Field notes: `record_id` repeats per source row (one record, N sources). `norm_key` is the join key and is Coptic-normalised. `licence` is the **source's** licence, not the record's. `quality` is `gold`/`checked`/`automatic` where the source exposes it (CDO examples carry Scriptorium quality flags — dictionary examples are filtered to `gold`/`checked` in v1). Empty `quality` means the source does not assert quality, which is itself worth knowing.

### 6.3 Δ Revised effort table

| Phase | v3 | v4 | Δ |
|---|---|---|---|
| Phase 1 — Dictionary | 26 | **27** | +1 (collation + tests + parser fixes) |
| Phase 2 — Corpus & Concordance | 22 | **21** | −1 (tarball replaces loose JSON) |
| Phase 3 — Grammar & Lessons | 17 | **30** | **+13** (15 lessons honestly cost 22.5, not 14) |
| Phase 4 — Flashcards & Offline | 16 | **19** | +3 (a11y raised to 5–6 days per §7.5) |
| **Total** | **78** | **97** | **+19** |

Against **160 person-days** for 2 people × 16 weeks. Utilisation **61%**, slack **39%**.

**The headline correction:** v3 totalled 78 days and framed it as comfortable. It was comfortable *because the lesson estimate was wrong by 3–4×.* Correcting it moves 19 days into the plan, and the plan still fits — but the margin is now honest rather than fictional.

---

## 7. Δ Batch of small fixes

### 7.1 Δ Kaikki pinned to a dated snapshot with SHA-256

```
# tools/sources.lock — every input pinned. A change here is a reviewed PR.
[kaikki]
url       = "https://kaikki.org/dictionary/Coptic/kaikki.org-dictionary-Coptic.jsonl"
sha256    = "e3b0c442...PLACEHOLDER-SET-ON-FIRST-FETCH"
bytes     = 62813016
records   = 3293
snapshot  = "2026-09-28"          # kaikki.org states extraction date
wiktionary_dump = "2026-09-02"
licence   = "CC-BY-SA-4.0 OR GFDL"
cite      = "Ylonen, T. (2022). Wiktextract: Wiktionary as Machine-Readable Structured Data. LREC 2022, 1317-1325."

[ccl]
doi = "10.17169/refubium-27566"; licence = "CC-BY-SA-4.0"; version = "1.2-2020"

[cdo]
repo = "github.com/KELLIA/dictionary"; licence_data = "CC-BY-SA-4.0"
doi = "10.17169/refubium-2333"; licence_code = "Apache-2.0"

[corpora]
repo = "github.com/CopticScriptorium/corpora"; version = "6.3.0"; licence = "per-document"
```

`fetch_all.py` verifies each SHA-256 and **hard-fails** on mismatch. The `records` and `bytes` fields double as the drift gate: if the download size changes, someone updates `sources.lock` deliberately.

> **Risk reduced:** kaikki.org regenerates weekly from a live Wiktionary dump. An unpinned fetch makes the site non-reproducible and makes "the build failed" indistinguishable from "upstream changed."

### 7.2 Δ Concordance search semantics — decided

**Default: lemma match. Toggle for exact bound group. Regex over the token stream.**

| Mode | Matches | Why it is the default |
|---|---|---|
| **Lemma** (default) | every token whose `@lemma` equals the query | A learner who knows `ⲧⲉⲛⲟⲩ` does not know that `ⲧⲉⲛⲟⲩⲧ` (ppr) or `ϫⲉⲧⲉⲛⲟⲩ` (conj) are its forms. Lemma search finds all of them in one query |
| Exact bound group | tokens whose `norm` equals the query string | Needed for morphology work: "show me only the definite article" |
| Regex | user pattern over `norm` | Advanced; runs on the token stream, not raw text |

**Explicitly rejected: substring search over raw text.** Coptic has no reliable whitespace convention for bound groups — `_TT` segmentation distinguishes bound groups from morphemes, and raw text may or may not have inserted spaces. Searching characters would produce results that silently disagree with the segmentation the site displays. **We search the token stream, always**, and the UI says so.

Sorts by **`corpus_ref_count` descending** (genuinely most-useful-first), with Coptic-collation as the tiebreak. Registered as `concordance.default_mode = "lemma"` in `data/dist/manifest.json` so the choice is reviewable.

> **Risk reduced:** the default mode was undecided in v3. An undecided default that later changes silently invalidates every saved concordance URL a user has shared.

### 7.3 Δ `/pdf/*` — add `X-Frame-Options`

```text
# public/_headers — Δ added to the /pdf/* block
/pdf/*
  Cache-Control: public, max-age=604800
  Content-Security-Policy: sandbox
  X-Frame-Options: DENY
  X-Content-Type-Options: nosniff
```

`Content-Security-Policy: sandbox` alone is the strong control; `X-Frame-Options: DENY` is defence in depth for older user agents and costs nothing.

> **Risk reduced:** clickjacking a PDF viewer to overlay a fake "download" button that harvests a click. Trivial fix, real vector for a site serving third-party-supplied documents.

### 7.4 Δ PWA installability added to Phase 4 acceptance criteria

**Phase 4 acceptance criteria, Δ additions:**

- `manifest.webmanifest` present, valid per the Web App Manifest spec, with `name`, `short_name`, `start_url`, `display: "standalone"`, `lang: "en"`, Coptic-block icons at **192, 512, and maskable 512** (three files, not two — maskable is required for a credible install prompt on Android)
- Chrome installability check: manifest parses, SW registers with a `fetch` handler, served over HTTPS, icons ≥ 144 px
- **Verified install on iOS Safari** (Add to Home Screen) — iOS is a primary platform for this audience and its install path differs; test it, don't assume it
- **Verified install on Android Chrome**, then confirm the installed app launches **offline** and reaches a lesson and a dictionary entry
- Offline deep-link: a bookmarked `/corpus/<work>/` URL resolves to the cached version when offline
- `sw.js` served with `Cache-Control: no-cache`; the precache manifest is regenerated every build with a fresh build id, so an update is picked up on the next load
- Update path: a changed build id triggers a `skipWaiting`/`clients.claim` prompt rather than silently serving stale content indefinitely

> **Risk reduced:** "offline-capable" is meaningless if the site cannot actually be installed. Installability is the difference between a PWA and a cached website, and it is the actual distribution mechanism for users who cannot afford app stores or unreliable connectivity.

### 7.5 Δ a11y budget raised to 5–6 person-days

v3 allowed 3 days inside Phase 4. Too thin for a JS-heavy reader plus a custom canvas-free concordance view.

**Phase 4 a11y line items:**

| Item | Days |
|---|---|
| axe-core CI gate (0 critical, 0 serious) on 6 page templates; failures block the PR | 0.5 |
| Full keyboard operability: dictionary search, shard loading, reader token navigation, concordance results | 1.5 |
| Focus management for SPA-style transitions (shard swap must move focus and announce it) | 0.5 |
| `aria-live` for async shard loads and search results; screen-reader pass with VoiceOver **and** NVDA | 1.5 |
| Contrast audit including Coptic glyphs against both light and dark themes | 0.5 |
| Reduced-motion, zoom to 200 %, `prefers-reduced-transparency` | 0.25 |
| **Total** | **5.25** |

**Non-negotiable:** the dictionary must be fully usable with JavaScript disabled on the 300 static pages. The sharded reader is progressive enhancement, not the only path.

> **Risk reduced:** a11y deferred and underfunded is the most predictable late failure in a static-site project, and it is the failure mode that is most expensive to retrofit because it touches every template.

### 7.6 Δ "Add a new source" documented in CONTRIBUTING

```markdown
## Adding a data source

No source ships without a reviewed, machine-readable licence verdict.
`tools/validate/licence_guard.py` fails the build on `UNKNOWN`.

1. **Add the pin** to `tools/sources.lock`: url, `sha256`, `bytes`, snapshot
   date, licence, DOI or repo, and a citation.
2. **Get a licence verdict.** `UNKNOWN` is not an acceptable value. For
   "open access" items you must determine the actual licence. If it is unclear,
   **link to the item — do not mirror it.**
3. **Write a parser** in `tools/parse/`. It must:
   - stream; never load the whole input into memory
   - raise on structural surprise, never silently skip
   - emit `record_id`, `source_record_id`, and `licence` for every record
4. **Add to `tools/nc_guard.ALLOWED_SOURCES`** (below). This is an
   **allowlist and it fails closed** — a new source will *not* reach the merged
   dataset until it is explicitly permitted.
5. **Declare what you changed.** Any normalisation you apply (diacritic
   stripping, case folding, sense merging) goes into the `changes` array of the
   record's `attributions[]`, with a note. CC BY-SA compliance requires
   indicating modifications.
6. **Open a PR.** A maintainer must review `git diff data/dist` — especially
   `records.csv` — before merge. Expect questions about senses merged.

### CC BY-NC sources

Sources licensed CC BY-NC (e.g. the Manley textbook) are **not** added to the
merged dataset. They live under `content/nc/` and `static/pdf/` and are never
imported into lessons, decks, or `data/dist/**`. See §7 in the v3 plan.
```

> **Risk reduced:** this is the process that keeps a volunteer-run project lawful as it grows. Without a documented path, the *fastest* thing a contributor can do is paste in a source with no licence record — which is precisely how a project gets a takedown notice.

---

## 8. Δ Per-entry attribution — `attributions[]`

### 8.1 Δ Why this is required, not merely nice

CC BY-SA 4.0 §3(a) requires attribution; **§3(b) requires indicating modifications.** A merged dictionary entry that has had senses deduplicated, senses re-ranked, and diacritics stripped is an **Adapted Material**. Shipping it without declaring those modifications is a licence violation, not a stylistic omission — and the *most likely* thing a Coptic scholar will check.

v3's `sources[]` array listed where data came from but **did not record what we did to it.** That is the gap this closes.

### 8.2 Δ Schema addition

```jsonc
// Added to every entry in schema/entry.schema.json
"attributions": [
  {
    "field": "glosses",
    "source": "CCL",
    "licence": "CC-BY-SA-4.0",
    "doi": "10.17169/refubium-27566",
    "changes": "none",
    "note": "Scholarly gloss verbatim from CCL entry C5047."
  },
  {
    "field": "glosses",
    "source": "Kaikki",
    "licence": "CC-BY-SA-4.0 OR GFDL",
    "changes": "diacritics stripped; case folded",
    "note": "Wiktionary prose gloss rendered as the plain-English gloss."
  },
  {
    "field": "glosses",
    "source": "MERGE",
    "licence": "CC-BY-SA-4.0",
    "changes": "deduplicated across 3 sources; sense order reordered by POS; clitic-merged forms (ⲥ→ⲛⲧⲟⲥ) exposed as separate lemma rows",
    "note": "Merged by tools/merge/entries.py v1.3.0."
  },
  {
    "field": "examples",
    "source": "CDO",
    "licence": "CC-BY-SA-4.0",
    "changes": "quality filtered to gold/checked; URN retained",
    "note": "Example sentences carry Scriptorium quality flags."
  },
  {
    "field": "etymology",
    "source": "Kaikki",
    "licence": "CC-BY-SA-4.0 OR GFDL",
    "changes": "none",
    "note": "Egyptian/Greek etymology chain verbatim."
  },
  {
    "field": "display",
    "source": "Coptic Scriptorium _TT",
    "licence": "CC-BY-SA-4.0",
    "changes": "diplomatic @orig preserved; canonical @norm stored separately",
    "note": "Per-document licence; see LICENSES.csv."
  }
]
```

**Controlled vocabulary for `changes`** — emit `none` when untouched, otherwise one or more of: `diacritics stripped`, `case folded`, `deduplicated`, `sense order changed`, `quality filtered`, `clitic split`, `gloss paraphrased`, `cross-references resolved`. Free text goes in `note`. A closed vocabulary makes `changes` aggregable — so we can report "how much of this dictionary is verbatim?" in aggregate, which is a genuinely good thing to be able to answer.

**JSON Schema (excerpt):**

```json
{
  "type": "object",
  "required": ["lemma", "norm_key", "glosses", "sources", "attributions"],
  "properties": {
    "attributions": {
      "type": "array", "minItems": 1,
      "items": {
        "type": "object",
        "required": ["field", "source", "licence", "changes"],
        "properties": {
          "field":    { "enum": ["lemma","glosses","etymology","examples",
                                 "forms","related_entries","display",
                                 "corpus_refs","media","translit"] },
          "source":   { "type": "string" },
          "licence":  { "enum": ["CC-BY-SA-4.0","CC-BY-4.0",
                                  "CC-BY-SA-4.0 OR GFDL","PD","UNKNOWN"] },
          "doi":      { "type": "string" },
          "changes":  { "type": "string" },
          "note":     { "type": "string" }
        }
      }
    }
  }
}
```

`validate --require-provenance` additionally asserts: **`attributions.length ≥ 1` on every entry**, and **no `licence: UNKNOWN`**, and **every `source` value appears in `records.csv`.**

### 8.3 Δ UI — collapsible per-entry Sources panel

```html
<!-- themes/copticref/layouts/partials/attributions.html -->
<details class="attr-panel" id="sources">
  <summary>
    <span class="attr-title">Sources &amp; modifications</span>
    <span class="attr-count">{len attributions}</span>
  </summary>
  <table class="attr-table">
    <caption class="visually-hidden">
      Attribution for each field of this dictionary entry
    </caption>
    <thead>
      <tr><th scope="col">Field</th><th scope="col">Source</th>
          <th scope="col">Licence</th><th scope="col">Changes</th></tr>
    </thead>
    <tbody>
      {for a in attributions}
      <tr>
        <th scope="row">{a.field}</th>
        <td>{a.source}{a.doi && <a href={doi_url a.doi} rel="noopener">DOI</a>}</td>
        <td>{a.licence}</td>
        <td>{a.changes}{a.note && <span class="attr-note">{a.note}</span>}</td>
      </tr>
      {endfor}
    </tbody>
  </table>
  <p class="attr-licence">
    Entry text is <a href="/licences/">CC BY-SA 4.0</a>. Modifications are
    listed above and are indicated per field, as
    <a href="https://creativecommons.org/licenses/by-sa/4.0/legalcode"
       rel="noopener">CC BY-SA 4.0 §3(b)</a> requires.
  </p>
</details>
```

Styling: collapsed by default (a `<details>`, so it works with no JavaScript and is keyboard-operable for free), visibly styled focus ring, `aria-describedby` on summary. **Do not hide this behind a JS popover** — an attribution a reader cannot reach without JS is not attribution.

> **Risk reduced:** this is the difference between a site that is *compliant* and one that is merely *attributing*. It also pre-empts the first serious question a scholar or institution will ask, and the closed `changes` vocabulary makes our editorial footprint auditable in aggregate rather than per-entry by hand.

---

## 9. Δ NC guard becomes a fail-closed allowlist

v3's `nc_guard.py` checked that NC-sourced IDs did *not* appear. That is **fail-open**: a newly added source is not on the NC list, so it passes silently. Inverted, it fails closed.

```python
# tools/validate/nc_guard.py — Δ inverted from blocklist to ALLOWLIST.
#
# v3 checked "if source.id in NC_SOURCES: fail" — which is fail-OPEN: a brand
# new source is not on the NC list and therefore passes. This version only
# admits sources on an explicit allowlist, so adding a source requires a
# deliberate, reviewed PR. FAIL CLOSED.
#
# LICENCE: project code, Apache-2.0.

# Every source permitted inside data/dist/**. Order is irrelevant; membership
# is what matters. Adding an entry here IS the review act.
ALLOWED_SOURCES: dict[str, str] = {
    # id            licence                        rationale
    "CCL":           "CC-BY-SA-4.0",   # BBAW + DDGLC; DOI 10.17169/refubium-27566
    "CDO":           "CC-BY-SA-4.0",   # KELLIA;      DOI 10.17169/refubium-2333
    "Kaikki":        "CC-BY-SA-4.0 OR GFDL",  # Wiktextract via kaikki.org
    "CDO-API":       "CC-BY-SA-4.0",   # frequencies from the CDO service
    "Scriptorium_TT":"CC-BY-SA-4.0",   # corpus text + aligned translations
    "Scriptorium_TEI":"CC-BY-SA-4.0",  # per-document licence; see LICENSES.csv
    "UD_Coptic":     "CC-BY-SA-4.0",   # UniversalDependencies/UD_Coptic-Scriptorium
    "UD_Bohairic":   "CC-BY-4.0",      # Zeldes, Speransky, Wagner, Schroeder 2025
    "Crum":          "PD",             # Crum, A Coptic Dictionary (1925/1939)
    "TLA":           "CC-BY-4.0",      # Thesaurus Linguae Aegyptiae
    "ProjectRebuild":"PD",             # text this project itself authors
    "TranslitTable": "PD",             # romanisation schemes are not copyrightable
    "G2PTable":      "CC-BY-SA-4.0",   # our own G2P, derived from CCL/CDO
}

# Permitted ONLY outside data/dist/**. Presence of any of these inside the
# dataset is a hard failure.
NC_ONLY_SOURCES: frozenset[str] = frozenset({
    "Manley2019",       # Sahidic Coptic: An Introductory Textbook — CC BY-NC 4.0
    "ShishaHalevy",     # Coptic Grammatical Chrestomathy — verify PD before use
    "LearnersGrammar",  # verify licence
    "Younan2005",       # verify / request permission
    "LoCPrimers",       # PD-US; non-US jurisdictions differ
    "AnkiDeck",         # per-deck; content licence is the author's
})


class NCGuardError(SystemExit):
    pass


def check(dist: pathlib.Path, content: pathlib.Path) -> None:
    errors: list[str] = []

    # ---- 1. every dataset entry's sources must be allowlisted -------------
    for shard in sorted(dist.glob("dict/shard-*.json")):
        for e in json.loads(shard.read_text(encoding="utf-8")).get("entries", []):
            ids = {s["id"] for s in e.get("sources", [])}
            ids |= {a["source"] for a in e.get("attributions", [])}
            for sid in ids:
                if sid in NC_ONLY_SOURCES:
                    errors.append(
                        f"{shard.name} entry {e.get('id')}: NC source {sid!r} "
                        f"inside the dataset — must be under content/nc/ only")
                elif sid not in ALLOWED_SOURCES:
                    errors.append(
                        f"{shard.name} entry {e.get('id')}: source {sid!r} is "
                        f"NOT in ALLOWED_SOURCES — fail-closed. Add it to "
                        f"tools/validate/nc_guard.py in a reviewed PR.")

    # ---- 2. NC ids must not appear outside content/nc/ --------------------
    for p in content.rglob("*.md"):
        if "nc/" in p.as_posix():
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        for sid in NC_ONLY_SOURCES:
            if sid in text:
                errors.append(
                    f"{p}: references NC source {sid!r} outside content/nc/")

    # ---- 3. the allowlist itself must be internally consistent -----------
    overlap = set(ALLOWED_SOURCES) & NC_ONLY_SOURCES
    if overlap:
        errors.append(f"allowlist/contra-list overlap: {sorted(overlap)}")

    if errors:
        for e in errors:
            print(f"[nc_guard] FAIL {e}", file=sys.stderr)
        raise NCGuardError(
            f"[nc_guard] {len(errors)} violation(s). The dataset must contain "
            f"only CC BY-SA / CC BY / PD material.")
    print(f"[nc_guard] OK — {len(ALLOWED_SOURCES)} allowlisted sources, "
          f"{len(NC_ONLY_SOURCES)} NC sources correctly excluded")


if __name__ == "__main__":
    check(pathlib.Path("data/dist"), pathlib.Path("content"))
```

**One new required PR step:** adding a source id to `ALLOWED_SOURCES` must also add a row to `LICENSES.csv` with a non-`UNKNOWN` verdict. `licence_guard.py` cross-checks the two files, so the allowlist and the licence manifest cannot drift apart.

> **Risk reduced:** the single highest-consequence legal failure in this project is CC BY-NC text reaching the redistributable dataset. A blocklist catches that only for sources someone already thought of. An allowlist catches it for **every source, including ones added in the future.**

---

## 10. Δ Product framing, Bohairic honesty, and corpus rollout

### 10.1 Δ §8 opening — positive framing first

> **What this site is:** a fast, complete, offline-capable **reading and reference tool for the Coptic language.** It puts a scholarly dictionary, 2.38 million words of annotated text with parse and lemma data, human translations aligned word-for-word, a concordance, a structured starter course, and flashcards — all of it searchable, all of it open-licensed, all of it readable on a phone with no signal. It is built to be *used*, not admired: tap any word in any text and see what it means, where it occurs, how it parses, and what it came from.

Then, immediately and without apology, the "what this is not" list, reframed as **boundaries a reader should know about:**

| This site does not… | Why | Use this instead |
|---|---|---|
| machine-translate | no Coptic MT exists at usable quality | aligned human translations (Brenton, Budge, Arabic) + labelled links to experimental MT tools |
| synthesise speech | two competing Bohairic pronunciation traditions, no open model | transliteration + named-tradition IPA; links to human recitation (Coptic Reader, Kemet) |
| score your pronunciation | no validated model exists | record-and-play-back self-comparison, explicitly unscored |
| adapt to you or sync your progress | no accounts, no server — that is what keeps it free and private | Anki (FSRS) is canonical; progress stays in your browser and exports as JSON |
| host manuscript images | republishing is neither free nor needed | IIIF viewers at Michigan, BSB, and the Göttingen project |

The site ships this as a real `/roadmap` page, not a footnote. **Naming the gaps is more useful to a heritage community than implying completeness we do not have** — and it converts "the site is incomplete" into "here is what you could help build."

### 10.2 Δ Bohairic: presentation priority, not data reality

**Say this plainly, on the site, in the dialect switcher itself:**

> Coptic is written today in **Bohairic** — the dialect of the living Coptic Orthodox Church. The digital resources were built the other way round: **most annotated text, most lexicography, and most teaching material are Sahidic**, the scholarly classical dialect. We present **Bohairic first** because it is the language people actually need to read. That is a *presentation* decision. It is not backed by equivalent data.
>
> Concretely, in this build: Bohairic has ~750,000 words of corpus versus ~1.6M Sahidic; Bohairic has a UD treebank of ~30,000 word forms versus ~59,000 tokens Sahidic; and Bohairic **syntactic parsing is materially weaker**. Where Bohairic coverage is thin, **the interface says so on the affected page** rather than silently substituting Sahidic.

**Mechanical enforcement (not just prose):**

- Every corpus work carries a `coverage` badge computed from its data: `annotated` / `parsed` / `text-only`, with counts.
- If a learner taps a Bohairic word with no Bohairic lemma in our data, the dictionary **shows the Sahidic result with an explicit note**: *"no Bohairic lemma recorded; showing Sahidic."*
- Never silently substitute across dialects. A wrong-dialect answer presented confidently is worse than an honest gap.
- `/dialects` is a real page with real counts per dialect per source, updated from `records.csv` each bake.

> **Risk reduced:** the failure is not that we present Bohairic first — it is that doing so *implies* parity we do not have. A Bohairic speaker is the primary user; if they hit an unmarked Sahidic substitution in week one, we lose them permanently. Making coverage visible converts a trust problem into an information problem.

### 10.3 Δ Corpus rollout priority — liturgical → biblical → patristic → monastic

Reordered in §6 Gantt and expressed as `tools/shipped.toml`:

| Order | Tier | Works (initial) | Why this order |
|---|---|---|---|
| **P2.1** | **Liturgical** | Common-prayer texts, Lauds, Theotokia | **Highest value and lowest risk.** This is what the church uses weekly, so it is what the community will open the site for. Best-aligned translations exist. Vernacular prayers are the most approachable entry text |
| **P2.2** | **Biblical** | Sahidic Ruth, Bohairic Mark, Bohairic 1 Corinthians | Familiar content lowers the learning curve; aligns with Lessons 12 and 15. Also where cross-dialect comparison is most instructive (Mark exists in both) |
| **P2.3** | **Patristic** | Lausiac History, Life of Isaac, Martyrdom of Victor | Broadens beyond scripture. Introduces narrative prose and longer sentences. Larger per-work JSON |
| **P2.4** | **Monastic** | Shenoute (Fox, Eagerness, House, …) | **Deliberately last.** Highest linguistic difficulty: Shenoute's rhetorical style, dense clitic chains, and heavily non-standard vocabulary will overwhelm a beginner. Worth doing for scholars; wrong as an on-ramp |

**Why monastic is last, stated for the record:** Shenoute is where the grammar gets *hard*, not where the language gets *useful*. Leading with him teaches people to bounce. The lessons reference him in Lesson 15 onward, once the reader has the prepositional phrase, the circumstantial `ⲙⲡⲁⲧ`, and the relative clause in hand.

> **Risk reduced:** v3 shipped corpus in whatever order the parser produced files, which put a scholar's reading list — not a learner's — first. Ordering by community value rather than by directory name is the difference between a site people return to and one they bookmark and abandon.

---

## 11. Preserved from v3 (unchanged, and why it stays)

| Preserved | Reason |
|---|---|
| **Two-stage architecture** (Stage A bake on a scheduled runner → committed; Stage B Hugo + Pagefind on Pages) | Cloudflare Pages Free = 20-min build timeout, 1 concurrent build, 500 builds/month. Stage B must stay seconds. Δ only replaced the *inside* of Stage B's search step |
| **File-count discipline** — ≈ 950 files of 20,000, sharded-JSON dictionary, 300 static SEO pages, CI gate at 15,000 | The architecture that makes the free tier comfortable. Corpus tarball (Δ) improves git hygiene without touching the deployed file count |
| **§8 scope framing** — every exclusion paired with a workaround | Retained in substance; Δ only changes the opening to lead positively |
| **`$0` posture** — `*.pages.dev`, no custom domain until funding exists | Pages Free includes bandwidth and SSL |
| **NC isolation** | Strengthened from blocklist to allowlist (§9) |
| **Lesson plan structure** — each lesson grounded in corpus deep-links + a grammar reference | Prevents the grammar page from becoming a floating essay |
| **Keyman `coptic_greek` (MIT)** for the keyboard | Already exists, cross-platform, no build |
| **No AI at runtime or build time** | `_TT` supplies POS/lemma/parse directly |
| **Honest annotation of unverified licences** (items 8, 9, 10, 13) | `LICENCES.csv` + `--require-licence` hard gate |
| **`data/dist` committed** | Deterministic deploys; diffable review surface |

---

## 12. Δ What changed, in one table

| § | Fix | Risk reduced |
|---|---|---|
| 1 | `collate.py` with **name-resolved** alphabet, name-derived case pairs, `rank_key`/`sort_key` split, 13-test suite; all 9 sort sites audited. **Testing caught 4 further defects in my own draft** (no "kho" character — it is `ⲭ`; `Ⲝ` is *capital* KSI; case-folding destroyed the total order; codepoint parity breaks at U+2CE4 mis-pairing 13 chars) | Silent site-wide wrong sort order, invisible to non-Coptic reviewers — plus four bugs that testing surfaced only because it was run |
| 2 | Single-pass Pagefind Node script replacing the two-pass CLI chain | Silent record loss + 2× slower search build |
| 3 | 15 lessons at launch (was 60), +5/month; honest 22.5-day estimate | A 3–4× underestimated phase that would have blown the deadline |
| 4 | `<orig>` preserved; single-pass state machine; tolerant meta regex; per-doc floor + corpus regression | Quadratic parsing and *plausible-but-wrong* alignments on 2.38M words |
| 5 | 2 people committed; 1-person cut list (dictionary + corpus, ~10 weeks) | Implicit staffing assumption; "hold scope, miss the date" failure |
| 6 | Corpus → `corpus.tar.gz`, regenerated only on upstream change; review via `manifest.json` | Unreviewable 400-file diffs on every corpus refresh |
| 7 | `nc_guard` inverted to a fail-closed allowlist | NC text reaching the redistributable dataset via an unanticipated source |
| 8 | `attributions[]` with controlled-vocabulary `changes` + non-JS collapsible panel | CC BY-SA §3(b) non-compliance; unauditable editorial footprint |
| 9 | §8 opens positively as a reading/reference tool | Underselling; the scope list read as apology rather than boundaries |
| 10 | Bohairic-first declared as *presentation*, with mechanical coverage badges | Implying a data parity we do not have; losing Bohairic users to silent substitution |
| 11 | Corpus order: liturgical → biblical → patristic → monastic | Shipping a scholar's reading list to learners |
| 12 | Kaikki pinned w/ SHA-256; `records.csv` schema; PWA installability; a11y 5.25 d; concordance semantics; `X-Frame-Options`; CONTRIBUTING source process | Non-reproducible builds; clickjacking; unauditable defaults; a PWA that cannot be installed; a contributor's fastest path being licence-incomplete |

---

*Collation failure measured as `sorted(['Ϣ','Ⲱ','Ⲁ']) == ['Ϣ','Ⲁ','Ⲱ']` — Ϣ is U+03E2, below the Coptic block. v4 retains the two-stage architecture, the file-count discipline, and the honest scope framing. It adds no scope; it moves 19 person-days of previously-hidden cost into the plan and removes five silent-failure modes.*
