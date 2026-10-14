# tools/tests/test_conllu.py — Session 3, D3.
# LICENCE: project code, Apache-2.0.
#
# Three cases the brief requires (valid file, empty file, malformed token count)
# plus the MWT trap: the real treebank uses CoNLL-U ranges, and an earlier draft
# emitted the "_" placeholder row as a real token, silently corrupting every
# sentence containing a Coptic prefix or suffix. 17,419 of the real treebank's
# structures are MWTs, so this is not a corner case.
#
# Fixtures are built with TAB.join() rather than embedded tab characters. Tabs in
# a triple-quoted test fixture are a transport hazard: the write path escapes
# them, and the module then fails to parse at a line that looks fine.
from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "parse"))

import conllu  # noqa: E402

UD_DIR = ROOT / "sources" / "ud_coptic"
UD_FILES = sorted(UD_DIR.glob("*.conllu")) if UD_DIR.is_dir() else []

needs_ud = pytest.mark.skipif(not UD_FILES, reason="UD treebank not fetched")

TAB = chr(9)
U = chr(0)  # placeholder, replaced below; keeps the literals readable

# Coptic strings by codepoint. Hand-typing Greek-script and Coptic literals is
# the documented hazard (PLAN-ERRATA: "Do not hand-type the alphabet"), and it
# has already cost this project one wrong assertion.
AN = chr(0x2C81) + chr(0x2C9B)          # an
PE = chr(0x2CA1) + chr(0x2C49)          # pe
NAI = chr(0x2C9B) + chr(0x2C81) + chr(0x2C93)   # nai
ASHO = chr(0x2C81) + chr(0x03D3) + chr(0x2C89) + chr(0x2CB5) + chr(0x2C81) + chr(0x2C45) + chr(0x2C49)
MWT_FORM = chr(0x2C89) + chr(0x2CB1) + chr(0x2CA5) + chr(0x2C81) + chr(0x2CA1) + chr(0x2C93)


def row(*cols: str) -> str:
    return TAB.join(cols)


def tree(*lines: str) -> str:
    return "\n".join(lines) + "\n"


def write(tmp_path: pathlib.Path, text: str, name: str = "t.conllu") -> pathlib.Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


ONE_TOKEN = row("1", AN, AN, "PRON", "PRON", "_", "0", "root", "_", "_")
TWO_TOKEN = tree(
    "# sent_id = t1",
    "# text = " + AN + " " + PE,
    "# text_en = there is not",
    "# meta::author = Test",
    "# meta::document_cts_urn = urn:cts:copticLit:test:1",
    row("1", AN, AN, "PRON", "PRON", "_", "2", "prep", "_", "_"),
    row("2", PE, PE, "DET", "ART", "Definite=Ind", "0", "root", "_", "_"),
    "",
    "# sent_id = t2",
    row("1", NAI, NAI, "PRON", "PRON", "_", "0", "root", "_", "_"),
    "",
)

MWT_TREE = tree(
    "# sent_id = m1",
    row("1-2", MWT_FORM, "_", "_", "_", "_", "_", "_", "_", "_"),
    row("1", chr(0x2C89), chr(0x2C89), "ADP", "PREP", "_", "0", "root", "_",
        "Orig=" + chr(0x2C89) + chr(0x0308)),
    row("2", MWT_FORM[1:], MWT_FORM[1:], "NOUN", "N", "_", "0", "root", "_",
        "Orig=" + MWT_FORM[1:]),
    "",
)


# ── a valid file ─────────────────────────────────────────────────────────────

def test_valid_file(tmp_path):
    recs = list(conllu.iter_sentences(write(tmp_path, TWO_TOKEN),
                                      declared_dialect="Sahidic"))
    assert len(recs) == 2
    r = recs[0]
    assert r["sent_id"] == "t1"
    assert r["text"] == AN + " " + PE
    assert r["text_en"] == "there is not"
    assert r["urn"] == "urn:cts:copticLit:test:1"
    assert r["author"] == "Test"
    assert r["dialect"] == "Sahidic"
    assert r["n_tokens"] == 2


def test_tokens_carry_heads_and_relations(tmp_path):
    r = list(conllu.iter_sentences(write(tmp_path, TWO_TOKEN)))[0]
    by_id = {t["id"]: t for t in r["tokens"]}
    assert by_id[1]["head"] == 2 and by_id[1]["deprel"] == "prep"
    assert by_id[2]["head"] == 0 and by_id[2]["deprel"] == "root"
    assert by_id[1]["feats"] == {}


def test_underscore_becomes_empty_string(tmp_path):
    r = list(conllu.iter_sentences(write(tmp_path, TWO_TOKEN)))[0]
    for t in r["tokens"]:
        for field in ("form", "lemma", "upos", "xpos", "deprel"):
            assert t[field] != "_", field + " left as the literal underscore"


def test_sent_headers_do_not_leak_but_file_headers_do(tmp_path):
    """sent_id/text/text_en are per-sentence and cleared at the blank line.
    meta:: keys are per-DOCUMENT and persist — that is correct UD semantics, and
    the real treebank relies on it (one newdoc block, many sentences)."""
    recs = list(conllu.iter_sentences(write(tmp_path, TWO_TOKEN)))
    assert recs[0]["sent_id"] == "t1"
    assert recs[1]["sent_id"] == "t2"
    assert recs[1]["text"] == ""
    assert recs[1]["urn"] == "urn:cts:copticLit:test:1", \
        "a document-level URN applies to every sentence in that document"


def test_new_document_clears_the_previous_documents_meta(tmp_path):
    """A second newdoc block must NOT inherit the first document's URN."""
    text = tree(
        "# newdoc id = doc1",
        "# meta::document_cts_urn = urn:cts:copticLit:doc1",
        "# meta::author = First",
        "# sent_id = s1",
        ONE_TOKEN,
        "",
        "# newdoc id = doc2",
        "# meta::document_cts_urn = urn:cts:copticLit:doc2",
        "# meta::author = Second",
        "# sent_id = s2",
        ONE_TOKEN,
        "",
    )
    recs = list(conllu.iter_sentences(write(tmp_path, text)))
    assert recs[0]["urn"] == "urn:cts:copticLit:doc1"
    assert recs[0]["author"] == "First"
    assert recs[1]["urn"] == "urn:cts:copticLit:doc2"
    assert recs[1]["author"] == "Second"


def test_a_document_with_no_urn_does_not_inherit_the_previous_one(tmp_path):
    """The contamination case that matters: doc2 declares no URN at all."""
    text = tree(
        "# newdoc id = doc1",
        "# meta::document_cts_urn = urn:cts:copticLit:doc1",
        "# sent_id = s1", ONE_TOKEN, "",
        "# newdoc id = doc2",
        "# sent_id = s2", ONE_TOKEN, "",
    )
    recs = list(conllu.iter_sentences(write(tmp_path, text)))
    assert recs[1]["urn"] == "", "must not inherit doc1's URN"


# ── MWT ──────────────────────────────────────────────────────────────────────

def test_mwt_placeholder_is_not_emitted_as_a_token(tmp_path):
    r = list(conllu.iter_sentences(write(tmp_path, MWT_TREE)))[0]
    assert r["n_tokens"] == 2
    assert all(t["form"] != "_" for t in r["tokens"])


def test_mwt_range_is_recorded_and_attached(tmp_path):
    r = list(conllu.iter_sentences(write(tmp_path, MWT_TREE)))[0]
    assert len(r["mwt"]) == 1
    m = r["mwt"][0]
    assert (m["lo"], m["hi"]) == (1, 2)
    assert m["form"] == MWT_FORM
    assert all(t["mwt"] is not None for t in r["tokens"])


def test_orig_diacritics_are_preserved(tmp_path):
    """Same relationship as _TT's @orig/@norm (PLAN-ERRATA B-4): the marked form
    is authoritative for display."""
    r = list(conllu.iter_sentences(write(tmp_path, MWT_TREE)))[0]
    assert chr(0x0308) in r["tokens"][0]["orig"], "the combining mark must survive"


def test_misc_splits_on_pipe_but_keeps_equals_inside_a_value(tmp_path):
    """The real treebank encodes an entity set ACROSS tokens —
    `Entity=(object` on one, `Entity=object)` on the next — because "|" is the
    CoNLL-U MISC separator. So a single MISC field holds ONE key=value, and the
    set is reassembled by a later stage, not here."""
    text = tree("# sent_id = e1",
                row("1", AN, AN, "NOUN", "N", "_", "0", "root", "_",
                    "Entity=(object"),
                row("2", PE, PE, "NOUN", "N", "_", "0", "root", "_",
                    "Entity=object)|Orig=" + PE))
    r = list(conllu.iter_sentences(write(tmp_path, text)))[0]
    assert r["tokens"][0]["misc"]["Entity"] == "(object"
    assert r["tokens"][1]["misc"]["Entity"] == "object)"
    assert r["tokens"][1]["orig"] == PE


# ── an empty file ────────────────────────────────────────────────────────────

def test_empty_file_yields_nothing(tmp_path):
    assert list(conllu.iter_sentences(write(tmp_path, ""))) == []


def test_comments_only_file_yields_no_sentences(tmp_path):
    assert list(conllu.iter_sentences(write(tmp_path, "# just a comment\n"))) == []


def test_header_without_tokens_yields_no_sentences(tmp_path):
    assert list(conllu.iter_sentences(
        write(tmp_path, "# sent_id = t1\n# text = x\n\n"))) == []


# ── malformed token count / columns ──────────────────────────────────────────

def test_short_line_raises(tmp_path):
    text = "# sent_id = t1\n" + row("1", AN, AN) + "\n"
    with pytest.raises(conllu.CoNLLUError) as e:
        list(conllu.iter_sentences(write(tmp_path, text)))
    assert "truncated" in str(e.value)


def test_trailing_empty_columns_are_padded_not_rejected(tmp_path):
    """DEPREL/DEPS/MISC may be omitted: they are the trailing columns and
    absence means "no value". Padded, not rejected."""
    text = "# sent_id = t1\n" + row("1", AN, AN, "PRON", "PRON", "_", "0") + "\n"
    r = list(conllu.iter_sentences(write(tmp_path, text)))[0]
    assert r["n_tokens"] == 1
    assert r["tokens"][0]["head"] == 0
    assert r["tokens"][0]["deprel"] == ""


def test_missing_head_column_raises(tmp_path):
    """6 columns is below the CoNLL-U minimum. Padding HEAD with 0 would invent a
    root relation for a token that may not be a root."""
    text = "# sent_id = t1\n" + row("1", AN, AN, "PRON", "PRON", "_") + "\n"
    with pytest.raises(conllu.CoNLLUError) as e:
        list(conllu.iter_sentences(write(tmp_path, text)))
    assert "HEAD is mandatory" in str(e.value)


def test_non_integer_token_id_raises(tmp_path):
    text = "# sent_id = t1\n" + row("x", AN, AN, "PRON", "PRON", "_", "0", "root", "_", "_") + "\n"
    with pytest.raises(conllu.CoNLLUError) as e:
        list(conllu.iter_sentences(write(tmp_path, text)))
    assert "not an integer" in str(e.value)


def test_malformed_range_raises(tmp_path):
    text = "# sent_id = t1\n" + row("a-b", MWT_FORM, "_", "_", "_", "_", "_", "_", "_", "_") + "\n"
    with pytest.raises(conllu.CoNLLUError) as e:
        list(conllu.iter_sentences(write(tmp_path, text)))
    assert "range" in str(e.value)


def test_non_integer_head_raises(tmp_path):
    text = "# sent_id = t1\n" + row("1", AN, AN, "PRON", "PRON", "_", "root", "_", "_", "_") + "\n"
    with pytest.raises(conllu.CoNLLUError) as e:
        list(conllu.iter_sentences(write(tmp_path, text)))
    assert "HEAD" in str(e.value)


def test_dangling_head_raises(tmp_path):
    """A head pointing outside the sentence is a broken parse; keeping it emits a
    dependency graph with edges to nowhere."""
    text = "# sent_id = t1\n" + row("1", AN, AN, "PRON", "PRON", "_", "7", "prep", "_", "_") + "\n"
    with pytest.raises(conllu.CoNLLUError) as e:
        list(conllu.iter_sentences(write(tmp_path, text)))
    assert "absent token" in str(e.value)


# ── dialect ──────────────────────────────────────────────────────────────────

def test_dialect_comes_from_a_header_field_when_present(tmp_path):
    text = tree("# dialect = Bohairic", "# sent_id = t1", ONE_TOKEN)
    assert list(conllu.iter_sentences(write(tmp_path, text)))[0]["dialect"] == "Bohairic"


def test_dialect_falls_back_to_declared_then_unknown(tmp_path):
    text = tree("# sent_id = t1", ONE_TOKEN)
    got = list(conllu.iter_sentences(write(tmp_path, text), declared_dialect="Sahidic"))
    assert got[0]["dialect"] == "Sahidic"
    assert list(conllu.iter_sentences(write(tmp_path, text)))[0]["dialect"] == "unknown"


def test_dialect_is_never_inferred_from_text(tmp_path):
    """The real header has no dialect field. Guessing one from the Coptic would be
    a guess wearing a metadata label — the failure v4 §10.2 warns about."""
    text = tree("# sent_id = t1",
                row("1", ASHO, ASHO, "N", "N", "_", "0", "root", "_", "_"))
    assert list(conllu.iter_sentences(write(tmp_path, text)))[0]["dialect"] == "unknown"


# ── against the real treebank ────────────────────────────────────────────────

@needs_ud
def test_real_token_count_matches_the_pin():
    """58,974 — exactly the `tokens` value in tools/sources.lock, arrived at
    independently. Two sources agreeing is worth pinning."""
    assert conllu.census(UD_FILES, declared_dialect="Sahidic")["tokens"] == 58974


@needs_ud
def test_real_sentence_and_file_counts():
    c = conllu.census(UD_FILES, declared_dialect="Sahidic")
    assert c["sentences"] == 2252
    assert c["files"] == 3


@needs_ud
def test_real_treebank_has_mwts_and_none_leak():
    c = conllu.census(UD_FILES, declared_dialect="Sahidic")
    assert c["mwt"] > 17000, "the real treebank is full of prefixed words"
    s = next(conllu.iter_sentences(UD_FILES[0], declared_dialect="Sahidic"))
    assert all(t["form"] != "_" for t in s["tokens"])


@needs_ud
def test_real_every_head_resolves():
    """Streaming all 58,974 tokens. The parser raises on a dangling head, so
    reaching the end IS the assertion."""
    n = 0
    for p in UD_FILES:
        for s in conllu.iter_sentences(p, declared_dialect="Sahidic"):
            n += s["n_tokens"]
    assert n == 58974


@needs_ud
def test_real_all_sentences_carry_english_and_a_urn():
    c = conllu.census(UD_FILES, declared_dialect="Sahidic")
    assert c["with_en"] == 2252
    assert c["with_urn"] == 2252


@needs_ud
def test_real_dialect_is_unknown_when_nothing_declares_it():
    c = conllu.census(UD_FILES)
    assert c["dialects"] == {"unknown": 2252}


@needs_ud
def test_real_records_carry_provenance_and_the_correct_licence():
    s = next(conllu.iter_sentences(UD_FILES[0], declared_dialect="Sahidic"))
    assert s["sources"][0]["id"] == "UD_Coptic"
    assert s["sources"][0]["licence"] == "CC-BY-4.0", (
        "CC BY 4.0, no ShareAlike — read from the treebank's own LICENSE.txt")
    assert s["provenance"]["record_id"]
