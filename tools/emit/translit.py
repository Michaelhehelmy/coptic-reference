#!/usr/bin/env python3
"""tools/emit/translit.py — rule-based Coptic transliterator (Session 17, D0).

LICENCE: project code, Apache-2.0.

Populates the empty ``translit`` objects in the shards: five schemes per entry
(bohairic, sahidic, layton, till, egyptological). Deterministic, pure functions
of the input string; no I/O, no network, no guessing.

C1 — the empty ``translit`` objects are a missing feature, not an upstream
absence. Upstream (CCL/CDO/Kaikki) supplies no per-scheme transliteration, so
this module derives it from published letter tables. It does NOT read
``forms.romanization`` (C4): Kaikki romanizations are a cross-check used by the
tests, never an input to the mapping.

C2 — every rule cites a source. Rules without a published source are marked
UNVERIFIED in ``UNVERIFIED`` below and must be reported, not hidden.

PUBLIC API
    to_bohairic(coptic) -> str
    to_sahidic(coptic) -> str
    to_layton(coptic) -> str
    to_till(coptic) -> str
    to_egyptological(coptic) -> str
    transliterate_all(coptic) -> dict[str, str]

RULES WITH CITATIONS
    R1  Single-letter base map (all schemes): ALA-LC Coptic Romanization Table,
        2014 version, approved 2014-01-25 (Library of Congress / American
        Library Association): a b g d e z th i k l m n x o p r s t u ph ch ps,
        plus Demotic-derived ϣ=s with caron, ϥ=f, ϩ=h, ϫ=c with caron,
        ϭ=ky, ϯ=ti, ⲏ=e with macron, ⲱ=o with macron, ⲳ=ʼ (glottal stop).
        Corroborated by Layton (2000) Table 1 "The Sahidic alphabet with
        Egyptian-Coptic values" and Till (1961) Koptische Dialektgrammatik,
        "Die im Koptischen verwendeten Buchstaben mit ihrer Umschrift".
    R2  Long vowels ⲏ/ⲱ keep the macron (ē/ō) in sahidic, layton and till
        (ALA-LC table: H=Emacron, W=Omacron) but are plain e/o in bohairic.
        Bohairic: contemporary Greco-Bohairic teaching profile (ⲏ=/e/,
        ⲱ=/o/) and the required contrast ioannes (B) vs iōannēs (S).
    R3  ⲟⲩ is a digraph rendered "ou" in sahidic and layton: Bukovec (2016),
        "Transliteration Koptisch" (Vienna): "Die Ligatur ou wird analog zum
        Griechischen mit ou wiedergegeben." Likewise ⲉⲓ -> "ei" (same source).
    R4  Combining marks (supralinear strokes, syllabic markers: U+0300,
        U+0304/U+0305, U+0323 and the Mn/Me/Cf classes in collate._IGN) are
        stripped to the base letter: ALA-LC Note 3, "Ignore diacritics when
        romanizing Coptic, following the practice of the Journal of Coptic
        Studies". Transliteration does NOT insert a vowel; vowel quality is a
        matter of transcription (Layton 2000 Table 1; Reintges Learner's
        Grammar 1.1.2/1.2). Exception, same ALA-LC note: diaeresis is kept on
        ⲓ/ⲩ -> ï/ü.
    R5  Bound-group separators (space, underscore, hyphen, pipe, equals) pass
        through unchanged; the transliterator never merges or splits bound
        groups. Bound groups defined in Layton (2011:12-20), cited via Zeldes &
        Schroeder (2016) "An NLP Pipeline for Coptic" 2.1; Till-vs-Layton
        segmentation contrast (hm p vs hmp) documented by Coptic Scriptorium
        ("Laytonization", 2018: conservative merging, e.g. hm p -> hmp).
    R6  Greek-block Demotic letters (Layton 2000: "six additional letters"
        ϣϥϩϫϭϯ): mapped per ALA-LC (R1). ϧ (Bohairic hori) -> h, evidenced by
        the dialect cognate pair ϩⲉⲛ (S) / ϧⲉⲛ (B) for the same preposition
        (CDO C6668: CF15380 S vs Scriptorium B).
    R7  ϯ is biphonemic t+i: Reintges Learner's Grammar 1.1.1 ("biphonemic
        letters ... ti (t+i)"). Sahidic/layton/till/egyptological render "ti"
        (ALA-LC: Ti/ti). Bohairic pronunciation /di/ (Worrell 1934, Coptic
        Sounds; Mallon, Grammaire copte) — its use as the *transliteration*
        string is UNVERIFIED (U1).
    R8  Determinism: input is NFC-normalized, case-folded for lookup, output is
        lowercase Latin; unknown codepoints pass through unchanged so nothing
        is silently dropped. Pure functions; calling twice gives the same
        string.

UNVERIFIED (project conventions, no published source found; reported, C2)
    U1  bohairic ϯ -> "di". The /di/ pronunciation is sourced (R7); using it as
        the transliteration string is a project choice.
    U2  bohairic ⲟⲩ -> "oou". No grammar found; required to reproduce the v4
        §2.1 example (ⲧⲉⲛⲟⲩ -> tenoou). Treats ⲟⲩ as o + ou in Bohairic only.
    U3  till ⲟⲩ -> "o". No source found; required to reproduce the v4 §2.1
        example (ⲧⲉⲛⲟⲩ -> teno).
    U4  layton ⲧ -> "ṯ" (t with breve below? no — t with dot? here U+1E6F
        LATIN SMALL LETTER T WITH LINE BELOW ... actually ṯ U+1E6F). No passage
        in Layton (2000) found that writes ⲧ as ṯ (his examples use plain t,
        e.g. hm-p-ran, hetb-psyche); required to reproduce the v4 §2.1 example
        (ⲧⲉⲛⲟⲩ -> ṯenou). The shape is Egyptological (Manuel de Codage ṯ).
    U5  egyptological vowel stripping (ⲁⲉⲏⲟⲱ -> empty; ⲓ->j, ⲩ->w). Inspired
        by Manuel de Codage conventions (Buurman et al. 1988) and TLA/Demotic
        etymologies (e.g. Demotic tnw behind ⲧⲉⲛⲟⲩ), but no published rule
        maps Coptic ⲧⲉⲛⲟⲩ -> tnw. Required to reproduce v4 §2.1 (tnw).
    U6  egyptological ϭ -> "k" (instead of ALA-LC "ky"). Consonantal-skeleton
        choice; the letter's value is contested (/g/ or /c/, cf. collate.py).
    U7  (D1) dialect/Old-Coptic letters without a sourced Latin value: ⳋ->h
        (HORI-name analogy with ϧ, R6), ⲋ (sou) and ⳇ (esh) rendered visibly
        unmapped. 14 merged entries affected. Source-to-find: Till 1961
        Old-Coptic sections, Steindorff Lehrbuch, or Quaegebeur.
R9  (D1) editorial and symbolic marks render as themselves in every scheme
    (Leiden preservation practice): parens, asterisk, stops, brackets, U+2019,
    U+2E17, U+25CC, U+2CE4/2CE5/2CE7/2CE8. Listed explicitly; never dropped.

Kaikki cross-check (C4, not a source): where a Kaikki ``forms.romanization``
exists for a test word it is compared against the sahidic output. Known
systematic divergences, measured on the Ruth/Mark word list: Kaikki/
Wiktionary writes ϫ as "j" (jinmisi, je) where ALA-LC requires "č", ϭ as "č"
(činmise, nči) where ALA-LC requires "ky", ⲭ as "kh" (khristos) where ALA-LC
(and the DBMNT table) require "ch", and ϧ as "x" (sxēout) where the CDO S/B
cognate pair ϩⲉⲛ/ϧⲉⲛ supports "h". Mismatches on those four letters are
expected and reported, not fixed by changing the table.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import unicodedata

SCHEMES: tuple[str, ...] = ("bohairic", "sahidic", "layton", "till",
                            "egyptological")

#: Machine-readable rule registry: (rule_id, statement, citation).
RULES: tuple[tuple[str, str, str], ...] = (
    ("R1", "single-letter base map (a b g d e z th i k l m n x o p r s t "
           "u ph ch ps; sh=f caron,h,f,č,ky,ti; e/omacron; ʼ)",
     "ALA-LC Coptic Romanization Table 2014 (LoC/ALA, approved 2014-01-25); "
     "Layton 2000 Table 1; Till 1961 Umschrift table"),
    ("R2", "ⲏ/ⲱ macron (ē/ō) in sahidic/layton/till, plain e/o in bohairic",
     "ALA-LC table (Emacron/Omacron); Greco-Bohairic teaching profile"),
    ("R3", "ⲟⲩ->ou, ⲉⲓ->ei (sahidic/layton; base for others)",
     "Bukovec 2016, Transliteration Koptisch (Vienna)"),
    ("R4", "combining marks stripped to base letter (Mn/Me/Cf); "
           "diaeresis kept on ⲓ/ⲩ (ï/ü)",
     "ALA-LC Note 3 (ignore diacritics; Journal of Coptic Studies practice)"),
    ("R5", "bound-group separators pass through; never merge/split",
     "Layton 2011:12-20 via Zeldes & Schroeder 2016 §2.1; Scriptorium "
     "'Laytonization' 2018"),
    ("R6", "Demotic letters per ALA-LC; Bohairic ϧ->h",
     "Layton 2000 (six additional letters); CDO C6668 (ϩⲉⲛ S / ϧⲉⲛ B)"),
    ("R7", "ϯ biphonemic t+i -> ti (sahidic/layton/till/egyptological)",
     "Reintges Learner Grammar 1.1.1; ALA-LC Ti/ti"),
    ("R8", "deterministic: NFC in, lowercase Latin out, unknowns pass through",
     "this module (tested)"),
    ("R9", "editorial and symbolic marks pass through visibly (never dropped): "
           "parens, asterisk, stops, brackets (Leiden editorial convention), "
           "U+2019 glottal variant, U+2E17 pronominal marker, U+25CC "
           "placeholder, Coptic symbols U+2CE4/2CE5/2CE7/2CE8",
     "Leiden Convention for editions (editorial brackets/asterisk "
     "preserved in transliteration); codepoints listed explicitly"),
)

#: Rules with no published source. Each entry: (id, statement, reason).
UNVERIFIED: tuple[tuple[str, str, str], ...] = (
    ("U1", "bohairic ϯ -> 'di'",
     "/di/ pronunciation sourced (Worrell 1934; Mallon); use as "
     "transliteration string is a project choice"),
    ("U2", "bohairic ⲟⲩ -> 'oou'",
     "no grammar found; reproduces v4 §2.1 example tenoou"),
    ("U3", "till ⲟⲩ -> 'o'",
     "no source found; reproduces v4 §2.1 example teno"),
    ("U4", "layton ⲧ -> 'ṯ' (U+1E6F)",
     "not found in Layton 2000 (his examples use plain t); Egyptological "
     "shape; reproduces v4 §2.1 example ṯenou"),
    ("U5", "egyptological ⲁⲉⲏⲟⲱ->∅, ⲓ->j, ⲩ->w",
     "MdC-inspired consonantal skeleton; no published Coptic rule; "
     "reproduces v4 §2.1 example tnw"),
    ("U6", "egyptological ϭ -> 'k' (not ALA-LC 'ky')",
     "consonantal-skeleton choice; value contested (/g/ or /č/)"),
    ("U7", "dialect/Old-Coptic letters without a sourced Latin value: "
           "ⳋ -> 'h' (HORI-name analogy with ϧ, R6), ⲋ (sou) and ⳇ (esh) "
           "rendered visibly unmapped (passthrough, never dropped)",
     "no row in ALA-LC 2014 or our Layton/Till excerpts; 14 merged entries "
     "affected; source-to-find: Till 1961 Dialektgrammatik Old-Coptic "
     "sections, Steindorff Lehrbuch, or Quaegebeur on Old Coptic letters"),
)

# ── base letter table (lowercase keys; lookup folds case) ────────────────────
# R1 (ALA-LC 2014). ϯ/ⲏ/ⲱ/ⲧ handled per-scheme below.
_BASE: dict[str, str] = {
    "ⲁ": "a", "ⲃ": "b", "ⲅ": "g", "ⲇ": "d", "ⲉ": "e",
    "ⲍ": "z", "ⲑ": "th", "ⲓ": "i", "ⲕ": "k", "ⲗ": "l",
    "ⲙ": "m", "ⲛ": "n", "ⲝ": "x", "ⲟ": "o", "ⲡ": "p",
    "ⲣ": "r", "ⲥ": "s", "ⲫ": "ph", "ⲭ": "ch", "ⲯ": "ps",
    "ϣ": "š", "ϥ": "f", "ϩ": "h", "ϧ": "h", "ϫ": "č",
    "ϭ": "ky", "ⲳ": "ʼ",
    # Session 17 D1 additions. Each cites a source or is UNVERIFIED (U7).
    "ⳉ": "ẍ",  # R1: ALA-LC 2014 has the row "Ⳉ Ẍ / ⳉ ẍ" (Akhmimic khei).
    "ι": "i",  # R1: ALA-LC Greek row ι->i; homoglyph of Coptic ⲓ (same
               # shape; one Mark lemma mixes the blocks: ϩⲩⲡⲟⲕⲉιⲙⲉⲛⲟⲥ).
    "ⳋ": "h",  # U7: DIALECT-P HORI by name/slot analogy with ϩ/ϧ (R6);
               # one merged lemma (ⲙⲉⳋⲏⲗ). No direct table row found.
}

# Session 17 D1, R9/U7: codepoints that render as themselves, visibly, in
# every scheme. Editorial sigla are preserved per Leiden Convention practice;
# nomina-sacra-like symbols have no letter value to expand. ⲋ/ⳇ (U7) are
# real Old Coptic letters with no sourced Latin value: passthrough keeps them
# visible (and greppable) instead of silently dropping them. Capitals fold
# via lower() in _base_letters, so only lowercase forms are listed.
_PASS_THROUGH = frozenset({
    "(", ")",                    # U+0028/0029 editorial parens
    "*",                         # U+002A reconstruction asterisk
    ".",                         # U+002E editorial stop
    "[", "]",                    # U+005B/005D editorial brackets
    "’",                         # U+2019 glottal-marker variant (cf. ʼ R1)
    "⸗",                         # U+2E17 pronominal-state marker (cf. - R5)
    "◌",                         # U+25CC placeholder: no phonetic value
    "ⳤ", "⳥", "⳧", "⳨",           # U+2CE4/2CE5/2CE7/2CE8 symbols
    "ⲋ",                         # U+2C8B SOU (Ⲋ folds here): U7
    "ⳇ",                         # U+2CC7 OLD COPTIC ESH: U7
})

_LONG_VOWEL_MACRON = {"ⲏ": "ē", "ⲱ": "ō"}
_LONG_VOWEL_PLAIN = {"ⲏ": "e", "ⲱ": "o"}

_DIAERESIS = {"ⲓ": "ï", "ⲩ": "ü"}

# Separators that pass through (R5). Includes the pipe used for gold
# tokenization and the underscore used for bound groups in plain-text input.
_SEPARATORS = frozenset({" ", "\t", "\n", "_", "-", "|", "=", "/"})

_IGNORED_CATEGORIES = frozenset({"Mn", "Me", "Cf"})
_DIAERESIS_MARK = "̈"  # U+0308, the only mark ALA-LC keeps (R4)

_TI_SMALL = "ϯ"  # U+03EF; capital Ϯ (U+03EE) folds to it via lower()


def _base_letters(text: str) -> list[str]:
    """Input -> list of lowercase base letters, marks resolved (R4, R8).

    Decomposed (NFD) walk so a diaeresis that follows its base as a separate
    codepoint is seen: U+0308 after ⲓ/ⲩ yields ï/ü (ALA-LC exception); every
    other Mn/Me/Cf mark is dropped (ALA-LC Note 3).
    """
    out: list[str] = []
    for ch in unicodedata.normalize("NFD", text):
        if ch == _DIAERESIS_MARK:
            if out and out[-1] in _DIAERESIS:
                out[-1] = _DIAERESIS[out[-1]]
            # A stray diaeresis with no Coptic base is dropped (R4).
            continue
        if unicodedata.category(ch) in _IGNORED_CATEGORIES:
            continue
        out.append(ch.lower())
    return out


def _render(units: list[str], scheme: str) -> str:
    """Render base-letter units for one scheme (digraphs R3/U2/U3, R7, U4-6)."""
    # Per-scheme single-letter deltas from _BASE.
    if scheme == "bohairic":
        long_v = _LONG_VOWEL_PLAIN
        tau, upsilon, iota = "t", "u", "i"
        ti = "di"  # U1
        khai = "ky"
    elif scheme == "layton":
        long_v = _LONG_VOWEL_MACRON
        tau, upsilon, iota = "ṯ", "u", "i"  # U4 (tau only)
        ti = "ti"
        khai = "ky"
    elif scheme == "till":
        long_v = _LONG_VOWEL_MACRON
        tau, upsilon, iota = "t", "u", "i"
        ti = "ti"
        khai = "ky"
    elif scheme == "egyptological":
        long_v = {"ⲏ": "", "ⲱ": "", "ⲁ": "", "ⲉ": "", "ⲟ": ""}
        tau, upsilon, iota = "t", "w", "j"  # U5 (upsilon/iota only)
        ti = "ti"
        khai = "k"  # U6
    else:  # sahidic (default scholarly)
        long_v = _LONG_VOWEL_MACRON
        tau, upsilon, iota = "t", "u", "i"
        ti = "ti"
        khai = "ky"

    ou_value = {"bohairic": "oou",  # U2
                "till": "o",        # U3
                "egyptological": None,  # compositional: ∅+w (U5)
                }.get(scheme, "ou")  # sahidic + layton: R3
    ei_value = {"egyptological": None}.get(scheme, "ei")  # R3 (j via U5)

    out: list[str] = []
    i = 0
    n = len(units)
    while i < n:
        ch = units[i]
        nxt = units[i + 1] if i + 1 < n else ""
        # Digraphs first (ordered before single letters).
        if ch == "ⲟ" and nxt == "ⲩ":
            if ou_value is None:  # egyptological: render compositionally
                out.append(long_v.get("ⲟ", _BASE["ⲟ"]))
                out.append(upsilon)
            else:
                out.append(ou_value)
            i += 2
            continue
        if ch == "ⲉ" and nxt == "ⲓ":
            if ei_value is None:
                out.append(long_v.get("ⲉ", _BASE["ⲉ"]))
                out.append(iota)
            else:
                out.append(ei_value)
            i += 2
            continue
        if ch in _SEPARATORS:
            out.append(ch)
            i += 1
            continue
        if ch in _PASS_THROUGH:  # R9/U7: visible identity, never dropped
            out.append(ch)
            i += 1
            continue
        if ch == _TI_SMALL:
            out.append(ti)  # R7 / U1
        elif ch == "ⲧ":
            out.append(tau)  # R1 / U4
        elif ch == "ⲩ":
            out.append(upsilon)  # R1 / U5
        elif ch == "ⲓ":
            out.append(iota)  # R1 / U5
        elif ch in long_v:
            out.append(long_v[ch])  # R2 / U5
        elif ch in _BASE:
            if ch == "ϭ":
                out.append(khai)  # R1 / U6
            else:
                out.append(_BASE[ch])  # R1
        elif ch in ("ï", "ü"):
            out.append(ch)  # R4
        else:
            # Unknown codepoint (Old Nubian, punctuation, numerals): pass
            # through unchanged (R8) so nothing is silently dropped.
            out.append(ch)
        i += 1
    return "".join(out)


class TranslitError(ValueError):
    """A string contains a character no scheme can map (Session 17 D1, C3)."""


#: Every unit _render() can consume without reaching its unknown branch.
_RENDERABLE = (set(_BASE) | {_TI_SMALL, "ⲧ", "ⲩ", "ⲓ", "ⲏ", "ⲱ"}
               | _SEPARATORS | _PASS_THROUGH | {"ï", "ü"})


def unmapped_chars(text: str) -> list[str]:
    """Characters in text that no scheme can map, in order of appearance."""
    seen: list[str] = []
    for unit in _base_letters(text):
        if unit not in _RENDERABLE and unit not in seen:
            seen.append(unit)
    return seen


def _transliterate(coptic: str, scheme: str) -> str:
    if not isinstance(coptic, str):
        raise TypeError(f"expected str, got {type(coptic).__name__}")
    return _render(_base_letters(coptic), scheme)


def to_bohairic(coptic: str) -> str:
    """Transliterate to the Bohairic scheme (R1-R8, U1-U2)."""
    return _transliterate(coptic, "bohairic")


def to_sahidic(coptic: str) -> str:
    """Transliterate to the Sahidic scheme (R1-R8, fully sourced)."""
    return _transliterate(coptic, "sahidic")


def to_layton(coptic: str) -> str:
    """Transliterate to the Layton scheme (sahidic + U4 ṯ)."""
    return _transliterate(coptic, "layton")


def to_till(coptic: str) -> str:
    """Transliterate to the Till scheme (sahidic + U3 ⲟⲩ->o)."""
    return _transliterate(coptic, "till")


def to_egyptological(coptic: str) -> str:
    """Transliterate to the Egyptological consonantal skeleton (U5-U6)."""
    return _transliterate(coptic, "egyptological")


_TO: dict[str, object] = {
    "bohairic": to_bohairic,
    "sahidic": to_sahidic,
    "layton": to_layton,
    "till": to_till,
    "egyptological": to_egyptological,
}


def transliterate_all(coptic: str) -> dict[str, str]:
    """All five schemes for one string (new dict on every call)."""
    return {
        "bohairic": to_bohairic(coptic),
        "sahidic": to_sahidic(coptic),
        "layton": to_layton(coptic),
        "till": to_till(coptic),
        "egyptological": to_egyptological(coptic),
    }


def transliterate_all_strict(coptic: str) -> dict[str, str]:
    """Like transliterate_all, but raise TranslitError naming the character.

    Session 17 D1, C3: the merge path uses this so an unusual character in a
    lemma fails the build naming the character, instead of silently shipping
    a partial transliteration. The lenient transliterate_all() is kept for
    interactive use; the pipeline must never use it.
    """
    bad = unmapped_chars(coptic)
    if bad:
        shown = ", ".join(f"{c!r} (U+{ord(c):04X})" for c in bad)
        raise TranslitError(f"character(s) with no mapping: {shown}")
    return transliterate_all(coptic)


if __name__ == "__main__":  # pragma: no cover
    import json
    import sys

    words = sys.argv[1:] or ["ⲧⲉⲛⲟⲩ"]
    for w in words:
        print(json.dumps({"coptic": w, **transliterate_all(w)},
                         ensure_ascii=False))
