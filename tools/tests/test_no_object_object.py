# tools/tests/test_no_object_object.py — the AST guard must still FAIL.
#
# Session 22 D0 / C1. Two regressions in one guard:
#
#   E34 (Session 21): the byte-level text scan failed the build because
#   pos_labels.js COMMENTED on the bug class it exists to prevent. A mention
#   in a comment cannot render. The AST upgrade must let that comment stand.
#
#   The complement: a real leak — a concatenation, a template literal, an
#   innerHTML/textContent assignment, a document.write call — must still be
#   caught, and the HTML/JSON text scan must stay exactly as strict as it
#   was. A guard that only learned to be lenient would be worse than the one
#   it replaced.
#
# Every negative here is a planted artefact in a tmp public/ tree, run
# through the real CLI (main), never through an internal helper. That is
# Rule 1's shape: the guard reads from disk; the test writes the disk.
#
# LICENCE: project code, Apache-2.0.
from __future__ import annotations

import gzip
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "validate"))

import no_object_object_guard as guard  # noqa: E402


def _public(tmp_path: pathlib.Path) -> pathlib.Path:
    p = tmp_path / "public"
    (p / "js").mkdir(parents=True)
    (p / "data").mkdir(parents=True)
    return p


def _run(public: pathlib.Path, capsys) -> tuple[int, pytest.CaptureResult[str]]:
    rc = guard.main(["--public", str(public)])
    return rc, capsys.readouterr()


# ── the E34 regression: a COMMENT about the needle must pass ─────────────────

def test_e34_a_comment_mentioning_the_needle_passes(tmp_path, capsys):
    """The literal Session 21 incident: pos_labels.js documented the bug
    class in a header comment and the text scan failed the build. Comments
    are not in the AST, so this must be rc=0."""
    pub = _public(tmp_path)
    (pub / "js" / "pos_labels.js").write_text(
        "/*\n"
        " * Rule 11 shape: this file exists to prevent a raw structured value\n"
        " * interpolating into a template. The string it must never produce\n"
        " * is mentioned here for the reader: [object Object].\n"
        " * (Note: this comment must never be read as a leak — comments are\n"
        " * not in the AST and cannot render.)\n"
        " */\n"
        "function posDisplay(tag, labels) {\n"
        "  return (labels && labels[tag]) || '';\n"
        "}\n",
        encoding="utf-8")
    rc, out = _run(pub, capsys)
    assert rc == 0, out.err
    assert "object Object" not in out.err


def test_e34_a_block_comment_mention_also_passes(tmp_path, capsys):
    pub = _public(tmp_path)
    (pub / "js" / "x.js").write_text(
        "/* avoided: el.innerHTML = obj; would render [object Object] */\n"
        "const ok = 1;\n", encoding="utf-8")
    rc, out = _run(pub, capsys)
    assert rc == 0, out.err


# ── the complement: real leaks must still fail ───────────────────────────────

def test_a_concatenation_producing_the_needle_fails(tmp_path, capsys):
    """The exact Session 22 spec plant. The scanner attributes this to the
    .textContent sink (the more specific reason) rather than to the bare
    `+`; either attribution is a catch, and rc must be 1 either way."""
    pub = _public(tmp_path)
    (pub / "js" / "bug.js").write_text(
        'el.textContent = prefix + "[object Object]";\n', encoding="utf-8")
    rc, out = _run(pub, capsys)
    assert rc == 1
    assert "bug.js" in out.err
    assert "textContent" in out.err


def test_a_pure_concatenation_without_a_sink_fails(tmp_path, capsys):
    pub = _public(tmp_path)
    (pub / "js" / "bug.js").write_text(
        'const s = "a" + "[object Object]" + "b";\n', encoding="utf-8")
    rc, out = _run(pub, capsys)
    assert rc == 1
    assert "bug.js" in out.err


def test_a_template_literal_fails(tmp_path, capsys):
    pub = _public(tmp_path)
    (pub / "js" / "bug.js").write_text(
        "el.innerHTML = `got ${v} [object Object] done`;\n", encoding="utf-8")
    rc, out = _run(pub, capsys)
    assert rc == 1
    assert "bug.js" in out.err


def test_an_innerhtml_assignment_fails(tmp_path, capsys):
    pub = _public(tmp_path)
    (pub / "js" / "bug.js").write_text(
        'el.innerHTML = "[object Object]";\n', encoding="utf-8")
    rc, out = _run(pub, capsys)
    assert rc == 1
    assert "innerHTML" in out.err


def test_a_textcontent_assignment_fails(tmp_path, capsys):
    pub = _public(tmp_path)
    (pub / "js" / "bug.js").write_text(
        'el.textContent = "[object Object]";\n', encoding="utf-8")
    rc, out = _run(pub, capsys)
    assert rc == 1
    assert "textContent" in out.err


def test_document_write_fails(tmp_path, capsys):
    pub = _public(tmp_path)
    (pub / "js" / "bug.js").write_text(
        'document.write("<p>[object Object]</p>");\n', encoding="utf-8")
    rc, out = _run(pub, capsys)
    assert rc == 1
    assert "document.write" in out.err


def test_an_equality_comparison_is_not_a_rendering_path(tmp_path, capsys):
    """pagefind-highlight.js's exact pattern: a type check, not a leak. The
    AST rule ignores comparisons, so the old vendor carve-out is unnecessary
    and the comparison must pass on its own merits."""
    pub = _public(tmp_path)
    (pub / "js" / "vendor.js").write_text(
        'if (Object.prototype.toString.call(a[0]) !== "[object Object]") {\n'
        "  handle(a[0]);\n}\n", encoding="utf-8")
    rc, out = _run(pub, capsys)
    assert rc == 0, out.err


def test_a_bare_literal_with_no_sink_is_not_flagged(tmp_path, capsys):
    """Session 22 spec: only concatenations, template literals, and
    innerHTML/textContent/document.write sinks count. Dead data does not."""
    pub = _public(tmp_path)
    (pub / "js" / "dead.js").write_text(
        'const historical = "[object Object]";\n', encoding="utf-8")
    rc, out = _run(pub, capsys)
    assert rc == 0, out.err


def test_an_unparseable_script_fails_closed(tmp_path, capsys):
    pub = _public(tmp_path)
    (pub / "js" / "broken.js").write_text("function ( { ;\n", encoding="utf-8")
    rc, out = _run(pub, capsys)
    assert rc == 1
    assert "broken.js" in out.err


# ── the text scan for HTML/JSON must be unchanged ─────────────────────────────

def test_an_html_file_containing_the_needle_still_fails(tmp_path, capsys):
    pub = _public(tmp_path)
    (pub / "index.html").write_text(
        "<p>value: [object Object]</p>\n", encoding="utf-8")
    rc, out = _run(pub, capsys)
    assert rc == 1
    assert "index.html" in out.err


def test_a_json_file_containing_the_needle_still_fails(tmp_path, capsys):
    pub = _public(tmp_path)
    (pub / "data" / "x.json").write_text(
        '{"gloss": "[object Object]"}\n', encoding="utf-8")
    rc, out = _run(pub, capsys)
    assert rc == 1
    assert "x.json" in out.err


def test_a_compressed_json_payload_containing_the_needle_still_fails(
        tmp_path, capsys):
    pub = _public(tmp_path)
    payload = gzip.compress(b'{"gloss": "[object Object]"}\n')
    (pub / "data" / "shard-000.json.gz").write_bytes(payload)
    rc, out = _run(pub, capsys)
    assert rc == 1
    assert "shard-000.json.gz" in out.err


def test_a_clean_tree_passes(tmp_path, capsys):
    pub = _public(tmp_path)
    (pub / "index.html").write_text("<p>clean</p>\n", encoding="utf-8")
    (pub / "js" / "app.js").write_text("const x = 1;\n", encoding="utf-8")
    payload = gzip.compress(b'{"gloss": "one"}\n')
    (pub / "data" / "shard-000.json.gz").write_bytes(payload)
    rc, out = _run(pub, capsys)
    assert rc == 0, out.err


def test_an_empty_tree_still_fails(tmp_path, capsys):
    """Zero is a failure, not a skip (HANDOFF §8a Rule 1/2 family)."""
    pub = tmp_path / "public"
    pub.mkdir()
    rc, out = _run(pub, capsys)
    assert rc == 1


# ── the real published tree, when one exists ─────────────────────────────────

@pytest.mark.skipif(not (ROOT / "public" / "js").is_dir(),
                    reason="no published tree — run tools/build.py first")
def test_the_real_published_tree_passes(capsys):
    rc, out = _run(ROOT / "public", capsys)
    assert rc == 0, out.err
