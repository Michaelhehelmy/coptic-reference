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
# NOTE: the two-state (PRE_VERSE/IN_VERSE) machine from v4 §4.5 is gone. A single
# linear scan is both simpler and correct; see the comment at the scan site and
# DECISIONS.md B-6.

_TAG_RE = re.compile(r"""<(/?)([a-z_]+)\b([^>]*)>""")
# group(1)="" opening, "/" closing. Capturing the slash is REQUIRED:
# with the plan's original </?(name) the closing tag yielded the same
# name as the opening one, so </norm> was scanned as an opening <norm>
# and the scanner hunted for the NEXT </norm>, swallowing real tokens and
# eventually running off the end of the file. See DECISIONS.md B-4.
_NORM_ATTRS_RE = re.compile(r"""([\w:.-]+)\s*=\s*"([^"]*)\"""")

# Δ Fix 1: <orig> is captured into a side channel while inside a <norm>.
_ORIG_OPEN_RE = re.compile(r"""<orig\b[^>]*?\borig\s*=\s*"([^"]*)""")
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

    # Single linear scan of every tag in the file. The plan's original two-state
    # machine (PRE_VERSE -> IN_VERSE) jumped straight to the next "<verse_vid",
    # but in the real _TT format <translation> and <vid_n> are SIBLINGS that
    # PRECEDE <verse_vid> inside the same <verse_n>:
    #     <verse_n><translation/><vid_n/><verse_vid>…</verse_vid></verse_n>
    # so the jump silently skipped both, and every verse came back with an empty
    # translation and an empty urn. DECISIONS.md B-6.
    #
    # Whitespace between tags is irrelevant here, which also fixes the plan's
    # positional startswith check (B-5).
    cur: Verse | None = None
    pending_orig: str | None = None
    pending_translation: str | None = None
    pending_urn: str | None = None
    chapter: str | None = None

    pos = 0
    n = len(raw)
    while pos < n:
        mt = _TAG_RE.search(raw, pos)
        if not mt:
            break
        is_closing = mt.group(1) == "/"
        name = mt.group(2)
        body = mt.group(3)
        pos = mt.end()

        if is_closing:
            # Session 8 C3: a verse closes on </verse_n>, which every work has.
            # </verse_vid> still closes one for Ruth, where it is the inner
            # wrapper; by then `cur` is None in the other shape and this is a
            # no-op, so nothing is appended twice.
            if name in ("verse_vid", "verse_n") and cur is not None:
                if cur.tokens:
                    doc.verses.append(cur)
                cur = None
                pending_translation = None
                pending_urn = None
                pending_orig = None
            continue

        if name == "verse_n":
            chapter = _attrs(body).get("verse_n") or chapter
            # Session 8 D3 / C3: open the verse HERE.
            #
            # Measured (Session 8 D2): the corpus ships TWO shapes of the same
            # _TT format and they differ in exactly one way.
            #
            #   Ruth:   <verse_n> <translation> <vid_n> <verse_vid> TOKENS </verse_vid> </verse_n>
            #   others: <verse_n> <translation>              TOKENS                    </verse_n>
            #
            # <vid_n> and <verse_vid> occur 85 times in Ruth and ZERO times in
            # all five other works. The old code created the Verse only on
            # <verse_vid>, so one work of nine happened to parse and the other
            # five returned 0 verses -- which the min_verses guard correctly
            # refused to ship rather than emitting five works of empty text.
            if cur is None:
                cur = Verse(
                    verse_ref=chapter,
                    urn=pending_urn or doc.urn,
                    translation=pending_translation,
                )

        elif name == "translation":
            # The aligned human translation for the verse that FOLLOWS.
            t = html.unescape(_attrs(body).get("translation", "")).strip()
            pending_translation = t or None
            # Session 8 D3: since <verse_n> now opens the Verse, the verse
            # usually EXISTS by the time its translation arrives -- the old code
            # created it later, at <verse_vid>, so pending_translation was
            # enough. Without this, every verse parsed with translation=None and
            # the whole corpus would have shipped with no English, which
            # test_every_verse_has_translation_and_urn caught immediately.
            if cur is not None and pending_translation:
                cur.translation = pending_translation

        elif name == "vid_n":
            pending_urn = _attrs(body).get("vid_n") or pending_urn

        elif name == "verse_vid":
            # Optional refinement. Present in Ruth, absent elsewhere; a Verse
            # already exists in both cases because <verse_n> opened it.
            a = _attrs(body)
            if cur is None:                      # defensive: verse_vid before verse_n
                cur = Verse(
                    verse_ref=a.get("verse_vid", ""),
                    urn=pending_urn or doc.urn,
                    translation=pending_translation,
                )
            else:
                cur.verse_ref = a.get("verse_vid", "") or cur.verse_ref
                cur.urn = pending_urn or cur.urn
            pending_translation = None
            pending_urn = None
            if chapter:
                doc.quality.setdefault("_chapter", chapter)

        # Δ Fix 1: remember the enclosing <orig> before its <norm> child
        elif name == "orig":
            mo2 = _ORIG_OPEN_RE.search(mt.group(0))
            pending_orig = html.unescape(mo2.group(1)) if mo2 else None

        # Δ Fix 1: <norm> is self-closing or wraps text; handle both
        elif name == "norm":
            token_attrs = _attrs(body)
            if mt.group(0).rstrip().endswith("/>"):
                if cur is not None:
                    _emit_token(cur, token_attrs, pending_orig or "",
                                token_attrs.get("norm", ""))
                pending_orig = None
            else:
                nxt = raw.find("</norm>", pos)
                if nxt == -1:
                    raise TTParseError(f"{path}: unterminated <norm> at {mt.start()}")
                inner = raw[pos:nxt]
                pos = nxt
                if cur is not None:
                    _emit_token(cur, token_attrs, pending_orig or "",
                                inner or token_attrs.get("norm", ""))
                pending_orig = None

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
