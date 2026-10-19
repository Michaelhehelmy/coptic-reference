# tools/tests/test_tt_parser.py — the contract for the _TT parser.
#
# The _TT format is TreeTagger-style SGML and is NOT well-formed XML. Verified:
#   ElementTree.parse(Ruth_01.tt) -> ParseError: mismatched tag
# So no XML parser may ever be used here, and every test below is about a real
# property of the format rather than about a shape we invented.
#
# NOTE ON THE PLAN'S FIGURES
# v4 §4.5 expected "85 verses" from Ruth_01.tt. That was wrong: 85 is the TOTAL
# across Ruth_01..04. Ruth_01.tt alone has 22. Verified and logged in
# DECISIONS.md (B-7). Both facts are asserted below so neither can drift.
# LICENCE: project code, Apache-2.0.
from __future__ import annotations

import pathlib
import sys
import unicodedata

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from tools.parse.tt import TTParseError, canon_form, parse_tt  # noqa: E402

CORPUS = pathlib.Path("/tmp/corpora/sahidic.ruth/sahidic.ruth_TT")
RUTH_01 = CORPUS / "Ruth_01.tt"

# NOTE: the corpus skip is applied PER TEST, not module-wide. A module-level
# skipif would also skip the hermetic tests below, which are precisely the ones
# that must run in CI where no corpus is checked out. Logged in DECISIONS.md.
needs_corpus = pytest.mark.skipif(
    not RUTH_01.exists(),
    reason="corpus not present; see RUNBOOK.md for how to fetch it",
)


# ── hermetic fixture ────────────────────────────────────────────────────────
# Built by hand so the diacritic and nested-<note> tests do not depend on
# upstream corpus content. sahidic.ruth contains ZERO combining marks, so a
# corpus-derived version of the diacritic test would pass vacuously.

# The real _TT <meta> line carries an HTML-escaped anchor inside @license, e.g.
#   license="&lt;a href='...by-sa/4.0/'&gt;CC-BY-SA 4.0&lt;/a&gt;"
# _clean_licence() unescapes it and reduces it to a bare licence token.
# Triple-quoted so the embedded single quotes need no escaping.
META = """<meta annotation="Test Annotator" chapter="1" corpus="test.corp" \
document_cts_urn="urn:cts:copticLit:test.corp:1" entities="gold" \
identities="gold" languages="Sahidic Coptic" \
license="&lt;a href='https://creativecommons.org/licenses/by-sa/4.0/'&gt;CC-BY-SA 4.0&lt;/a&gt;" \
parsing="gold" segmentation="gold" tagging="gold" version_n="6.3.0">"""


def fixture_verse(idx: int, tokens: str) -> str:
    return (
        f'<verse_n verse_n="{idx}">'
        f'<translation translation="English verse {idx}">'
        f'<vid_n vid_n="urn:cts:copticLit:test.corp:1.{idx}">'
        f'<verse_vid verse_vid="Test {idx}">'
        f"{tokens}"
        "</verse_vid></vid_n></translation></verse_n>"
    )


def token(orig: str, norm: str, tid: str, lemma: str = "") -> str:
    return (
        f'<orig orig="{orig}">'
        f'<norm xml:id="{tid}" func="root" pos="N" lemma="{lemma or norm}" '
        f'norm="{norm}">{norm}</norm>'
        "</orig>"
    )


# ── 1. parses a real corpus document ─────────────────────────────────────────

@needs_corpus
def test_parses_ruth_01_without_error():
    doc = parse_tt(RUTH_01)
    assert doc.corpus == "sahidic.ruth"
    assert doc.dialect == "S"
    assert doc.licence == "CC-BY-SA-4.0"
    assert doc.quality["segmentation"] == "gold"


# ── 2. verse count is derived from the file, not from a magic number ─────────

@needs_corpus
def test_verse_count_matches_source_markup():
    """The strongest honest assertion: count <verse_vid> in the source and
    require the parser to agree. Immune to upstream content changes."""
    raw = RUTH_01.read_text(encoding="utf-8")
    expected = raw.count("<verse_vid")
    doc = parse_tt(RUTH_01)
    assert expected == 22, f"fixture changed: {expected} <verse_vid> in source"
    assert len(doc.verses) == expected


@needs_corpus
def test_ruth_chapter_totals_85_verses():
    """The plan's 85 is the FOUR-FILE total, not per file. Both are asserted."""
    files = ["Ruth_01.tt", "Ruth_02.tt", "Ruth_03.tt", "Ruth_04.tt"]
    counts = [len(parse_tt(CORPUS / f).verses) for f in files if (CORPUS / f).exists()]
    if len(counts) != 4:
        pytest.skip("not all four Ruth chapters present")
    assert counts == [22, 23, 18, 22]
    assert sum(counts) == 85


@needs_corpus
def test_ruth_01_has_at_least_20_verses():
    """Plan expected >=80 per file; that was wrong (see module docstring).
    The real per-file figure is 22. This floor allows upstream churn."""
    assert len(parse_tt(RUTH_01).verses) >= 20


# ── 3. every verse carries tokens and its aligned translation ───────────────

@needs_corpus
def test_every_verse_has_at_least_one_token():
    doc = parse_tt(RUTH_01)
    for v in doc.verses:
        assert v.tokens, f"{v.verse_ref} has no tokens"


@needs_corpus
def test_every_verse_has_translation_and_urn():
    doc = parse_tt(RUTH_01)
    for v in doc.verses:
        assert v.translation, f"{v.verse_ref} lost its aligned translation"
        assert v.urn.startswith("urn:cts:"), f"{v.verse_ref} urn={v.urn!r}"


@needs_corpus
def test_tokens_carry_the_annotation_the_plan_relies_on():
    """v4 §4.5's whole premise: no ML needed, because _TT already carries
    pos / lemma / func / head. If this fails, the 'no AI' invariant is at risk."""
    t = parse_tt(RUTH_01).verses[0].tokens[0]
    assert t.xml_id == "u1"
    assert t.pos == "APST"
    assert t.lemma == "ⲁ"
    assert t.func == "aux"
    assert t.head == "#u3"


# ── 4. @orig preserves the diacritic; @norm is stripped ─────────────────────

def test_orig_preserves_combining_mark_norm_strips_it(tmp_path):
    """The Δ Fix 1 requirement. Hermetic because sahidic.ruth has no marks."""
    combining = "̀"                      # COMBINING GRAVE ACCENT
    marked = "ⲛ" + combining            # ⲛ̀  (n + ni)
    bare = "ⲛ"                            # ⲛ  (n)
    assert unicodedata.combining(combining)
    # NFC does NOT compose a Coptic letter with U+0300 — Unicode has no
    # precomposed form for it. That is exactly why canon_form() strips combining
    # marks by hand rather than trusting normalisation (v4 §1.3). Asserting the
    # true fact here, because it is the reason the manual strip exists at all.
    assert unicodedata.normalize("NFC", marked) == marked

    p = tmp_path / "Diacritic.tt"
    p.write_text(META + fixture_verse(1, token(marked, bare, "u1")),
                 encoding="utf-8")
    t = parse_tt(p).verses[0].tokens[0]

    assert unicodedata.combining(t.orig[1]), "orig must PRESERVE the combining mark"
    assert t.orig == marked
    assert t.norm == bare, "norm must be canonical (mark stripped)"
    assert not any(unicodedata.combining(c) for c in t.norm)
    assert t.lemma == bare


def test_canon_form_strips_marks_and_is_idempotent():
    marked = "ⲛ" + "̀"
    once = canon_form(marked)
    assert once == "ⲛ"
    assert canon_form(once) == once


# ── 5. a <verse_vid> inside a <note> must not become a verse ────────────────

def test_verse_vid_inside_note_does_not_create_a_verse(tmp_path):
    """The plan's justification for a single-pass scanner: a regex that finds
    '<verse_vid' cannot tell a verse from a mention of one inside a note."""
    note_with_fake_verse = (
        """<note note="cross-reference to """
        """<verse_vid verse_vid='Ruth 9:9'> is discussed elsewhere.">"""
        "</note>"
    )
    body = note_with_fake_verse + (
        '<orig orig="ⲁ">'
        '<norm xml:id="u1" func="root" pos="N" lemma="ⲁ" norm="ⲁ">ⲁ</norm>'
        "</orig>"
    )
    p = tmp_path / "Note.tt"
    p.write_text(META + fixture_verse(1, body), encoding="utf-8")

    doc = parse_tt(p)
    assert len(doc.verses) == 1, "a <verse_vid> inside a <note> became a verse"
    assert doc.verses[0].verse_ref == "Test 1"


# ── 6. malformed input RAISES rather than silently returning empty ───────────

@needs_corpus
def test_truncated_inside_norm_raises(tmp_path):
    """Truncated mid-<norm>: must raise, not return a short document."""
    raw = RUTH_01.read_text(encoding="utf-8")
    cut = raw.index("<norm ") + 40          # mid-element
    p = tmp_path / "Truncated.tt"
    p.write_text(raw[:cut], encoding="utf-8")
    with pytest.raises(TTParseError):
        parse_tt(p)


def test_empty_file_raises(tmp_path):
    p = tmp_path / "Empty.tt"
    p.write_text("", encoding="utf-8")
    with pytest.raises(TTParseError):
        parse_tt(p)


def test_file_without_meta_raises(tmp_path):
    p = tmp_path / "NoMeta.tt"
    p.write_text("<verse_n verse_n=\"1\"></verse_n>", encoding="utf-8")
    with pytest.raises(TTParseError):
        parse_tt(p)


def test_meta_without_trailing_newline_still_parses(tmp_path):
    """v4 §4.5 Δ Fix 3: the original meta regex required a trailing newline."""
    p = tmp_path / "NoNewline.tt"
    p.write_text(
        META.rstrip() + fixture_verse(1, token("ⲁ", "ⲁ", "u1")),
        encoding="utf-8",
    )
    doc = parse_tt(p)
    assert len(doc.verses) == 1
    assert doc.licence == "CC-BY-SA-4.0"
    assert doc.urn == "urn:cts:copticLit:test.corp:1"


def test_licence_defaults_to_unknown_not_silent_pass(tmp_path):
    """A document with no licence must be UNKNOWN and flagged, never blank."""
    # META stores the HTML-ESCAPED anchor exactly as _TT files do, so the
    # replacement target has to be the escaped form, not the literal one.
    assert "&lt;a href=" in META, "fixture precondition: META must be HTML-escaped"
    head, sep, tail = META.partition("license=")
    assert sep, "fixture precondition: META must carry a @license"
    escaped = sep + tail.split("parsing=", 1)[0]
    meta = META.replace(escaped, "")
    assert "license=" not in meta, "removal failed"
    p = tmp_path / "NoLicence.tt"
    p.write_text(meta + fixture_verse(1, token("ⲁ", "ⲁ", "u1")), encoding="utf-8")
    doc = parse_tt(p)
    assert doc.licence == "UNKNOWN"
    assert "_warn_licence" in doc.quality


# ── 7. the Shenoute shape: no <verse_n>, <translation> is the boundary ──────
# Session 25 D1. shenoute_eagerness's 17 _TT files carry ZERO <verse_n> and
# ZERO <verse_vid>: the unit is the <translation> segment under a codex page
# (<pb_xml_id>). Before this shape existed, Fix 4a refused every file at
# 0 verses — the correct refusal for a shape the parser did not know.

SHENOUTE_TT = (pathlib.Path(__file__).resolve().parents[2]
               / "sources" / "corpus" / "shenoute_eagerness" / "GF17-18.tt")
needs_shenoute = pytest.mark.skipif(
    not SHENOUTE_TT.exists(),
    reason="shenoute_eagerness not fetched; see tools/fetch/fetch_work.py")


def fixture_segment(page: str, tokens: str, translation: str = "…") -> str:
    return (
        f'<pb_xml_id pb_xml_id="{page}">'
        f'<translation translation="{translation}">'
        f"{tokens}"
        "</translation>"
    )


def test_segment_shape_opens_a_verse_per_translation(tmp_path):
    body = (
        fixture_segment("TESTPG", token("ⲁ", "ⲁ", "u1"))
        + '<translation translation="English segment two">'
        + token("ⲃ", "ⲃ", "u2") + "</translation>"
    )
    p = tmp_path / "Seg.tt"
    p.write_text(META + body, encoding="utf-8")
    doc = parse_tt(p)

    assert len(doc.verses) == 2
    assert [v.verse_ref for v in doc.verses] == ["TESTPG:1", "TESTPG:2"]
    assert doc.verses[0].translation is None, \
        "the '…' placeholder must not ship as a translation"
    assert doc.verses[1].translation == "English segment two"
    assert doc.verses[0].urn == doc.urn
    assert [t.norm for t in doc.verses[0].tokens] == ["ⲁ"]


def test_segment_counter_resets_per_codex_page(tmp_path):
    body = (
        fixture_segment("PG1", token("ⲁ", "ⲁ", "u1"))
        + '<translation translation="…">' + token("ⲃ", "ⲃ", "u2") + "</translation>"
        + fixture_segment("PG2", token("ⲅ", "ⲅ", "u3"))
    )
    p = tmp_path / "Pages.tt"
    p.write_text(META + body, encoding="utf-8")
    doc = parse_tt(p)
    assert [v.verse_ref for v in doc.verses] == ["PG1:1", "PG1:2", "PG2:1"]


def test_segment_shape_without_pages_gets_sequence_refs(tmp_path):
    body = ('<translation translation="…">' + token("ⲁ", "ⲁ", "u1")
            + "</translation>")
    p = tmp_path / "NoPage.tt"
    p.write_text(META + body, encoding="utf-8")
    doc = parse_tt(p)
    assert [v.verse_ref for v in doc.verses] == ["seg 1"]


@needs_shenoute
def test_real_shenoute_file_parses_with_segments():
    """The measured property of the real work: every translation pair becomes
    a verse, and every verse carries tokens."""
    raw = SHENOUTE_TT.read_text(encoding="utf-8")
    expected = raw.count("<translation ")
    assert expected == 22, "fixture changed: GF17-18.tt should have 22 segments"
    doc = parse_tt(SHENOUTE_TT)
    assert len(doc.verses) == expected
    assert all(v.tokens for v in doc.verses)
    # GF17-18 specifically has 0/22 aligned segments (the source's "…"
    # placeholder); other files in the work carry real English (21/1,078
    # across the work — alignment = "partial").
    assert all(v.translation is None for v in doc.verses), \
        "GF17-18 carries only the source's '…' placeholder, not a translation"
    assert doc.verses[0].verse_ref.startswith("GF17:")
    assert doc.licence.startswith("CC-BY")
