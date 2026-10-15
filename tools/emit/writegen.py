#!/usr/bin/env python3
"""tools/emit/writegen.py — writing-practice reference SVGs (Session 21 D4).

Emits static/write/svg/ref-*.svg plus static/write/index.json: one SVG per
reference glyph. Each SVG shows the glyph as font text in the site's Coptic
font stack inside a frame, with a description — and deliberately NOTHING
else. There are no stroke paths and no stroke-order metadata in these files:
no verified source for Coptic stroke order exists in this repository, and an
invented stroke order would teach wrong handwriting with authority.

What the feature measures instead is computed at runtime by static/js/write.js
from the same font rendering the learner sees: the reference glyph's ink
pixels and connected components (flood fill on an offscreen canvas), versus
the learner's ink and gesture count. Overlap bands, never scores. See
DECISIONS.md Session 21 D4 for the full deviation note.

THE 32: 25 Greek-derived letters in Greek order (ⲉ and ⲋ are different
letters — epsilon and numeral-6 sou — which is why the count is 25, not 24)
plus 7 Demotic-derived letters in Unicode-block order (ϣ ϥ ϩ ϧ ϫ ϭ ϯ).
All 32 occur in the six shipped works. ⳉ (Akhmimic khei) occurs in
dictionary headwords (e.g. ⲁⲛⲁⳉ) but in none of the six works and in no
counted alphabet, so it is not taught as tracing — documented here rather
than hidden. The 3 words (ⲁⲙⲏⲛ ⲡⲉⲧⲣⲟⲥ ⲙⲁⲣⲓⲁ) are corpus surface forms.
Filenames use codepoints (no invented English letter names); words use
their plain Latin spellings.

Deterministic; safe to re-run (byte-identical output). Committed under
static/ because Hugo publishes static/ verbatim and the no-JS page embeds
these files as images.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import unicodedata

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import safeio  # noqa: E402

OUT_DIR = ROOT / "static" / "write" / "svg"
INDEX = ROOT / "static" / "write" / "index.json"

FONT_STACK = "Coptic, 'Segoe UI Historic', 'Noto Sans Coptic', serif"

#: (glyph, slug, note). Order is the teaching order.
_BASE_LETTERS = "ⲁⲃⲅⲇⲉⲋⲍⲏⲑⲓⲕⲗⲙⲛⲝⲟⲡⲣⲥⲧⲩⲫⲭⲯⲱ"
GLYPHS: tuple[tuple[str, str, str], ...] = tuple(
    [(ch, "ref-u%04x" % ord(ch), "") for ch in _BASE_LETTERS] + [
        ("ϣ", "ref-u03e3", ""), ("ϥ", "ref-u03e5", ""),
        ("ϩ", "ref-u03e9", ""), ("ϧ", "ref-u03e7", ""),
    ("ϫ", "ref-u03eb", ""), ("ϭ", "ref-u03ed", ""),
    ("ϯ", "ref-u03ef", ""),
    ("ⲁⲙⲏⲛ", "ref-word-amen", "corpus word"),
        ("ⲡⲉⲧⲣⲟⲥ", "ref-word-petros", "corpus word"),
        ("ⲙⲁⲣⲓⲁ", "ref-word-maria", "corpus word"),
    ])


def fail(message: str) -> SystemExit:
    return SystemExit(f"[writegen] FAIL — {message}")


def svg_for(glyph: str, slug: str, note: str) -> str:
    """Reference SVG: font-rendered glyph in a frame. No stroke paths."""
    codepoints = " ".join("U+%04X" % ord(ch) for ch in glyph)
    desc = f"Coptic reference glyph {glyph} ({codepoints}). " \
        f"Rendered in the site Coptic font; stroke guides are measured " \
        f"at runtime, not shipped."
    if note:
        desc += " Note: " + note + "."
    size = 150 if len(glyph) == 1 else max(40, 150 - 22 * (len(glyph) - 1))
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" '
        f'role="img" aria-label="{desc}">\n'
        f"<desc>{desc}</desc>\n"
        f'<rect x="8" y="8" width="184" height="184" fill="none" '
        f'stroke="currentColor" stroke-width="2"/>\n'
        f"<text x=\"100\" y=\"148\" text-anchor=\"middle\" "
        f"font-size=\"{size}\" font-family=\"{FONT_STACK}\">{glyph}</text>\n"
        f"</svg>\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="writing-practice reference SVGs")
    ap.parse_args(argv)
    seen_slugs: set[str] = set()
    seen_glyphs: set[str] = set()
    for glyph, slug, _ in GLYPHS:
        if not glyph or slug in seen_slugs or glyph in seen_glyphs:
            raise fail(f"duplicate or empty glyph entry: {glyph!r}/{slug!r}")
        seen_slugs.add(slug)
        seen_glyphs.add(glyph)
        for ch in glyph:
            unicodedata.name(ch)  # KeyError on a non-character: fail, don't ship
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    index = []
    for glyph, slug, note in GLYPHS:
        data = svg_for(glyph, slug, note).encode("utf-8")
        safeio.write_verified(OUT_DIR / f"{slug}.svg", data)
        codepoints = ["U+%04X" % ord(ch) for ch in glyph]
        index.append({"glyph": glyph, "file": f"svg/{slug}.svg",
                      "codepoints": codepoints, "note": note})
    safeio.write_text_verified(
        INDEX, json.dumps({"generated": "writegen-v1", "glyphs": index},
                          ensure_ascii=False, indent=1) + "\n")
    print(f"[writegen] {len(index)} SVGs + index.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
