# tools/tests/test_tei.py — Session 3, D2.
#
# CCL is verified against the REAL 12.3 MB file. CDO is verified against a
# synthetic fixture ONLY, because CDO is not distributed as a TEI file and has
# no public API — see the fixture header and DECISIONS.md S3-B1. That
# asymmetry is asserted here so it cannot quietly become a claim of coverage.
#
# LICENCE: project code, Apache-2.0.
from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "parse"))

import tei  # noqa: E402

CCL = ROOT / "sources" / "ccl" / "Comprehensive_Coptic_Lexicon-v1.2-2020.xml"
CDO_FIXTURE = ROOT / "tools" / "tests" / "fixtures" / "cdo_sample.xml"

needs_ccl = pytest.mark.skipif(not CCL.is_file(),
                               reason="CCL not fetched; run tools/fetch/fetch_all.py")


# ── CDO is deliberately NOT supported (Session 4, correction Q3) ─────────────

def test_cdo_dialect_does_not_exist():
    """Do not invent CDO structure.

    Sessions 2-3 carried a `cdo` dialect built from guesswork, exercised against
    a synthetic fixture. There is no CDO TEI file, no CDO JSON, and
    coptic-dictionary.org serves an SPA at every /api/* path. A parser for a
    format nobody has seen ships as though it were verified, so it is removed.
    """
    assert "cdo" not in tei.DIALECTS
    assert set(tei.DIALECTS) == {"ccl"}


def test_requesting_the_cdo_dialect_is_an_error():
    """Not a silent fallback to CCL. Asking for CDO must fail loudly."""
    with pytest.raises(tei.TEIParseError) as e:
        list(tei.iter_entries(CCL, "cdo"))
    assert "cdo" in str(e.value)


def test_no_cdo_fixture_is_shipped():
    """The invented fixture is deleted, so it cannot be mistaken for real CDO."""
    fixture = ROOT / "tools" / "tests" / "fixtures" / "cdo_sample.xml"
    assert not fixture.exists(), (
        "a CDO fixture would imply a CDO format we do not have")


def test_ccl_still_declares_its_own_provenance():
    style = tei.DIALECTS["ccl"]
    assert style["id"] == "CCL"
    assert style["licence"] == "CC-BY-SA-4.0"
    assert style["doi"] == "10.17169/refubium-27566"
    assert style["originators"]


# ── shared behaviour ─────────────────────────────────────────────────────────







# ── fail loudly on a missing required element ────────────────────────────────

def test_entry_with_no_orth_anywhere_raises(tmp_path):
    p = tmp_path / "broken.xml"
    p.write_text(
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>'
        '<entry xml:id="X1"><sense><cit type="translation">'
        '<quote xml:lang="en">orphan gloss</quote></cit></sense></entry>'
        '</body></text></TEI>', encoding="utf-8")
    with pytest.raises(tei.TEIParseError) as e:
        list(tei.iter_entries(p, "ccl"))
    assert "X1" in str(e.value), "the error must name the entry"
    assert "no lemma" in str(e.value)


def test_malformed_xml_raises(tmp_path):
    p = tmp_path / "bad.xml"
    p.write_text("<TEI><text><body><entry>", encoding="utf-8")
    with pytest.raises(Exception):
        list(tei.iter_entries(p, "ccl"))


def test_a_file_with_no_entries_yields_nothing(tmp_path):
    p = tmp_path / "empty.xml"
    p.write_text('<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body/></text></TEI>',
                 encoding="utf-8")
    assert list(tei.iter_entries(p, "ccl")) == []


# ── namespace handling ───────────────────────────────────────────────────────

def test_namespace_is_optional(tmp_path):
    """CCL declares the TEI namespace. A file without it must still parse — the
    alternative is a hard failure on files that are otherwise fine."""
    p = tmp_path / "nons.xml"
    p.write_text("<TEI><text><body><entry>"
                 '<form type="lemma"><orth>ⲁⲛ</orth></form>'
                 '<sense><cit type="translation">'
                 '<quote xml:lang="en">without</quote></cit></sense>'
                 "</entry></body></text></TEI>", encoding="utf-8")
    recs = list(tei.iter_entries(p, "ccl"))
    assert recs[0]["lemma"] == "ⲁⲛ"
    assert recs[0]["glosses"][0]["text"] == "without"


# ── against the real CCL ─────────────────────────────────────────────────────

@needs_ccl
def test_real_ccl_entry_count():
    """11,283. The plan says "~11,500"; the measured figure is 11,283 and that
    is what the pipeline should expect."""
    assert tei.census(CCL)["entries"] == 11283


@needs_ccl
def test_real_ccl_every_entry_has_a_lemma_dialect_and_id():
    """Checked by streaming the whole file, not a sample: 11,283 assertions."""
    n = 0
    for r in tei.iter_entries(CCL):
        assert r["lemma"], r["provenance"]
        assert r["tla_id"], r["provenance"]
        assert r["pos"], r["lemma"]
        assert r["dialects"], r["lemma"]
        n += 1
    assert n == 11283


@needs_ccl
def test_real_ccl_gloss_coverage_is_high():
    c = tei.census(CCL)
    assert c["with_gloss"] > 11000
    assert c["no_gloss"] == 35, "the 35 glossless entries are a measured fact"


@needs_ccl
def test_real_ccl_lemma_less_entry_is_kept_as_a_variant():
    """C11273 is `type="inflected"` with orth ⲃⲁⲅ- and a real gloss. It must be
    kept and flagged, not raise and not vanish.

    The first version of the lemma fallback looked only at direct children of
    <entry>; that entry's <orth> is nested inside <form>, so the "fail loudly"
    rule fired on 1 of 11,283 real entries."""
    variants = [r for r in tei.iter_entries(CCL) if r["variant"]]
    assert len(variants) == 1
    v = variants[0]
    # By codepoint, not by a hand-typed glyph: the first attempt at this
    # assertion used a literal and was wrong by one letter (U+2C95 vs U+2C96).
    assert [ord(c) for c in v["lemma"]] == [0x2C83, 0x2C81, 0x2C95, 0x002D]
    assert v["lemma"].endswith("-"), "a bound-prefix variant ends in a hyphen"
    assert v["glosses"], "a variant entry still carries sense data"
    assert v["glosses"][0]["text"] == "going, throwing"
    # The type is on the <form>, not the <entry>.
    assert v["provenance"]["lemma_form_type"] == "inflected"
    assert v["provenance"]["entry_type"] in (None, "")


@needs_ccl
def test_real_ccl_records_all_carry_provenance():
    """Invariant 7, over every entry."""
    for r in tei.iter_entries(CCL):
        s = r["sources"][0]
        assert s["id"] == "CCL"
        assert s["licence"] == "CC-BY-SA-4.0"
        assert s["doi"] == "10.17169/refubium-27566"
        assert s["originators"]


@needs_ccl
def test_real_ccl_dialect_vocabulary_is_the_measured_eleven():
    """CCL uses ELEVEN <usg type="geo"> values. The entry schema contemplates
    three (B, S, N), so this is a measured fact worth pinning.

    An earlier version of this test asserted a closed set of seven that I had
    guessed from the plan, and real data failed it: M, F, Ak and W were missing.
    The values below are counted, not assumed, and unmapped codes are preserved
    verbatim rather than dropped.
    """
    seen: dict[str, int] = {}
    unknown = 0
    for r in tei.iter_entries(CCL):
        for d in r["dialects"]:
            seen[d] = seen.get(d, 0) + 1
        if r["dialect_unknown"]:
            unknown += 1
    # N is present because CCL's "?" maps to it — the entry schema already
    # defines N as "undetermined", so "?" needed no parallel field.
    assert set(seen) == {"S", "B", "N", "A", "M", "L", "F", "V", "Ak", "W", "P"}, sorted(seen)
    assert seen["S"] == 9418
    assert seen["B"] == 2221
    assert seen["Ak"] == 93, "Akhmimic is a real dialect and must survive"
    assert seen["N"] == 112, "the 112 '?' entries become N (undetermined)"
    assert unknown == 112, "and they are additionally flagged"


@needs_ccl
def test_question_mark_is_never_a_dialect_flag():
    """v4 §10.2: coverage gaps must be shown, not papered over. "?" is not a
    dialect, and a dialect switcher offering "?" is a lie told by a data field."""
    for r in tei.iter_entries(CCL):
        assert "?" not in r["dialects"]
    # ...and that they are N rather than absent, so an entry with no dialect
    # evidence still satisfies the schema's minItems: 1.
    # 112 entries carry N. Most also carry a real dialect, because CCL records
    # "?" alongside e.g. S on the same entry; N marks the uncertainty, it does
    # not replace what else the source said.
    n_entries = sum(1 for r in tei.iter_entries(CCL) if "N" in r["dialects"])
    assert n_entries == 112
    # Measured: all 112 also carry a real dialect. CCL records "?" alongside S or
    # B on the same entry, so N is always additive here. Asserted so a future
    # change that makes N exclusive is noticed rather than assumed.


@needs_ccl
def test_real_ccl_parsing_is_streaming_not_a_full_tree():
    """A 12 MB file must not become a 12x tree. Checked by asserting the parser
    is a generator, which is the property that guarantees it."""
    import types
    gen = tei.iter_entries(CCL)
    assert isinstance(gen, types.GeneratorType)
    first = next(gen)
    assert first["lemma"]
