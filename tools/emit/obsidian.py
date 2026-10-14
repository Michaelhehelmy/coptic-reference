#!/usr/bin/env python3
"""tools/emit/obsidian.py — build the reader vault (D9).

An Obsidian vault of the whole reference, as a single zip download. It exists
for readers who want the material offline, in an editor they already use, and in
plain text they can grep. It is the same content as the site, re-shaped for a
filesystem — not a second source of truth.

Hard constraints, and why each is here:

  * **TEXT STAYS TEXT.** No images, no SVG, no webfonts-as-glyphs, no canvas
    render of Coptic. Coptic is a normal Unicode script; the only reason it looks
    exotic is font coverage. Turning it into pictures would make it
    unsearchable, unselectable, uncopyable, and screen-reader-hostile. The
    project's own invariant 1 (static, works with JS off) has the same shape:
    the content is the content.
  * **≤ 200 files**, asserted. A vault with 4,000 notes is not something anyone
    opens. One file per letter, not per entry; one file per work, not per verse.
  * **< 25 MiB**, asserted. Cloudflare's per-file limit for a static asset.
  * **Every file carries its source attributions in a footer.** Invariant 7.
    A file lifted out of the vault and pasted into a blog post must still say
    where it came from and under what licence.
  * **Coptic collation order** throughout, via tools/collate.py (invariant 6).
    Never `sorted()` on a codepoint.

Usage:
    python3 tools/emit/obsidian.py                 # build from data/dist
    python3 tools/emit/obsidian.py --dist DIR      # build from a stub tree
    python3 tools/emit/obsidian.py --out FILE.zip
    python3 tools/emit/obsidian.py --keep-dir DIR  # also leave the tree on disk

LICENCE: project code, Apache-2.0. Vault content keeps its upstream licences;
see 99 Meta/Licences.md inside the archive.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import safeio  # noqa: E402
import shardio  # noqa: E402
import tomllib
import zipfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "validate"))

import collate  # noqa: E402
import nc_guard  # noqa: E402

VAULT_DIRNAME = "coptic-reference-vault"
MAX_FILES = 200
MAX_BYTES = 25 * 1024 * 1024  # 25 MiB, Cloudflare per-file limit

DICT_DIR = "10 Dictionary"
CORPUS_DIR = "20 Corpus"
LESSONS_DIR = "30 Lessons"
META_DIR = "99 Meta"

# Rule 11: the shipped translit.js renderer owns the translit schema field, even
# when another emitter needs its values. Python passes the structured object to
# that renderer; it never formats translit values itself.
TRANSLIT_SCHEMES = ("bohairic", "sahidic", "layton", "till", "egyptological")
TRANSLIT_PROBE = HERE / "translit_probe.mjs"


class TranslitError(SystemExit):
    """The shared renderer could not be called or did not answer."""


def render_scheme_transliterations(entries: list[dict]) -> dict[str, dict[str, str]]:
    """Ask translitDisplay() for every populated scheme, preserving the scheme.

    The probe is called only for entries whose schema object has at least one
    nonempty canonical value. Because the requested scheme is itself nonempty in
    every task, the renderer's fallback policy returns that scheme's text rather
    than substituting another scheme.
    """
    tasks: list[dict] = []
    positions: list[tuple[str, str]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        translit = entry.get("translit")
        if not isinstance(translit, dict):
            continue
        entry_id = entry.get("id")
        if not isinstance(entry_id, str) or not entry_id:
            continue
        for scheme in TRANSLIT_SCHEMES:
            value = translit.get(scheme)
            if isinstance(value, str) and value.strip():
                tasks.append({"translit": translit, "forms": [], "scheme": scheme})
                positions.append((entry_id, scheme))
    if not tasks:
        return {}
    node = shutil.which("node")
    if node is None:
        raise TranslitError("[obsidian] node is required to call static/js/translit.js")
    proc = subprocess.run(
        [node, str(TRANSLIT_PROBE)],
        input="\n".join(json.dumps(task, ensure_ascii=False) for task in tasks).encode(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise TranslitError(f"[obsidian] translit probe failed: {proc.stderr.decode().strip()}")
    lines = proc.stdout.decode("utf-8").splitlines()
    if len(lines) != len(tasks):
        raise TranslitError(
            f"[obsidian] translit probe returned {len(lines)} strings for {len(tasks)} tasks")
    try:
        rendered = [json.loads(line) for line in lines]
    except json.JSONDecodeError as e:
        raise TranslitError(f"[obsidian] translit probe returned invalid JSON: {e}") from e
    if any(not isinstance(value, str) for value in rendered):
        raise TranslitError("[obsidian] translit probe did not return only strings")
    values: dict[str, dict[str, str]] = {}
    for (entry_id, scheme), value in zip(positions, rendered):
        values.setdefault(entry_id, {})[scheme] = value
    return values

GENERATED_NOTE = (
    "<!-- Generated by tools/emit/obsidian.py from data/dist. "
    "Do not edit in the vault: edit the source and rebuild. -->"
)


class VaultError(SystemExit):
    """Raised on a condition that must fail the build, not warn."""


# ── loading ──────────────────────────────────────────────────────────────────

def load_shipped(path: pathlib.Path) -> list[dict]:
    """Works to publish, in the tier order v4 §10.3 fixes. Not alphabetised."""
    if not path.is_file():
        raise VaultError(
            f"[obsidian] {path} not found. It is the switch that decides what the "
            f"vault publishes; without it the vault would either be empty or "
            f"publish unreviewed text."
        )
    with path.open("rb") as fh:
        works = tomllib.load(fh).get("work", [])
    return [w for w in works if w.get("shipped", True)]


def load_entries(dist: pathlib.Path) -> list[dict]:
    """Every dictionary entry, from the committed shards."""
    entries: list[dict] = []
    for shard in shardio.shard_paths(dist / "dict"):  # Session 5 G2: *.json misses .gz
        blob = shardio.read_shard(shard)   # Session 5 G2: read_text on a .gz
                                         # raises UnicodeDecodeError on the
                                         # gzip magic byte 0x8b
        for e in blob.get("entries", []) or []:
            if isinstance(e, dict) and e.get("lemma"):
                entries.append(e)
    return entries


def load_licences(dist: pathlib.Path) -> list[dict[str, str]]:
    """Read the licence manifest, plain or .csv.gz.

    Session 8 S8-B2: this resolved the .gz path and then opened it as TEXT,
    which dies on gzip's magic byte 0x8b -- the same mistake licence_guard made
    in Session 7. `safeio.read_csv_rows` resolves AND decodes in one step, so
    there is no half-fixed version of this left to write again.
    """
    p = dist / "provenance" / "LICENSES.csv"
    if not safeio.resolve_readable(p).is_file():
        return []
    rows, _used = safeio.read_csv_rows(p)
    return rows


# ── attribution footer (invariant 7, on every single file) ───────────────────

def meta_link(from_dir: str, page: str) -> str:
    """Relative link to 99 Meta/<page> from a file in <from_dir>.

    Angle brackets, not %20: a space in a Markdown link target is legal inside
    <> and is what Obsidian actually resolves. URL-encoding it produces a link
    that works in a browser and not in the editor this vault is for.
    """
    depth = from_dir.count("/") + 1 if from_dir else 0
    prefix = "../" * depth
    return f"[{page}](<{prefix}99 Meta/{page}.md>)"


def footer(entry_sources: list[str], from_dir: str = "",
           extra: str | None = None, label: str = "Sources") -> str:
    srcs = sorted({x for x in entry_sources if x})
    line = ", ".join(f"`{x}`" for x in srcs) if srcs else "no source recorded"
    parts = ["", "---", "",
             f"**{label}:** {line}  ",
             f"Licences and originators: {meta_link(from_dir, 'Licences')} · "
             f"{meta_link(from_dir, 'Credits')}"]
    if extra:
        parts.insert(3, extra)
    return "\n".join(parts) + "\n"


# ── the dictionary, one file per Coptic letter ───────────────────────────────

def letter_index(letter: str) -> tuple[str, str]:
    """(filename stem, display name) for a letter.

    Filenames use the traditional Egyptian name in ASCII-safe form so the file
    is usable on a filesystem that mangles non-ASCII, while the DISPLAY name and
    the H1 keep the real glyph. Nothing is transliterated away.
    """
    for ch, name, value in collate.ALPHABET:
        if ch == letter:
            return f"{_slug(name)} ({letter})", f"{letter} — {name} / {value}"
    return _slug(letter), letter


def _slug(name: str) -> str:
    keep = [c if (c.isalnum()) else "-" for c in name.lower()]
    return "".join(keep).strip("-") or "letter"


def first_letter(lemma: str) -> str | None:
    """The letter this lemma files under, per the canonical alphabet.

    Uses rank_key, so a capital or a combining mark at the start still files
    under the right letter. Returns None for a lemma with no Coptic letter at
    the head (e.g. one starting with a Latin transliteration), which the caller
    must handle rather than silently dropping.
    """
    folded = collate.canon_for_sort(lemma)
    if not folded:
        return None
    head = folded[0]
    return head if head in collate.alphabet_chars() else None


def render_entry(e: dict, transliterations: dict[str, str] | None = None) -> str:
    """One entry as a ### block. Fields present-or-omitted, never 'None'."""
    """One entry as a ### block. Fields present-or-omitted, never 'None'."""
    out = [f"### {e.get('lemma', '')}"]

    meta: list[str] = []
    if e.get("display") and e["display"] != e.get("lemma"):
        meta.append(f"display {e['display']}")
    pos = e.get("pos") or []
    if pos:
        meta.append("POS " + "/".join(pos))
    dialects = e.get("dialects") or []
    if dialects:
        meta.append("dialect " + ", ".join(dialects))
    forms = e.get("forms") or []
    if forms:
        fs = ", ".join(f.get("form", "") for f in forms if isinstance(f, dict))
        if fs:
            meta.append(f"forms {fs}")
    if meta:
        out.append("*" + " · ".join(meta) + "*")

    shown = transliterations or {}
    # The strings come from translitDisplay(); this template only attaches the
    # scheme labels and joins them. It never reads the translit object itself.
    tr_bits = [f"{scheme} {shown[scheme]}" for scheme in TRANSLIT_SCHEMES
               if shown.get(scheme)]
    if tr_bits:
        out.append("**Transliteration:** " + "; ".join(tr_bits))

    for i, g in enumerate(e.get("glosses") or []):
        if not isinstance(g, dict):
            continue
        bits = [f"{i + 1}. **{g.get('text', '').strip()}**"]
        if g.get("pos"):
            bits.append(f"({g['pos']})")
        if g.get("source"):
            bits.append(f"— {g['source']}")
        out.append(" ".join(bits))

    etym = e.get("etymology")
    if isinstance(etym, dict) and (etym.get("text") or "").strip():
        chain = ""
        if etym.get("chain"):
            chain = f" ({' → '.join(etym['chain'])})"
        out.append(f"**Etymology:** {etym['text'].strip()}{chain}")

    # Exactly ONE example, per the spec — the longest available, which is the
    # most likely to contain the point being illustrated.
    examples = [x for x in (e.get("examples") or []) if isinstance(x, dict)]
    if examples:
        ex = max(examples, key=lambda x: len(x.get("coptic", "")))
        out.append("")
        out.append("> " + ex.get("coptic", "").strip())
        if ex.get("translation"):
            out.append(">")
            out.append("> — " + ex["translation"].strip())
        cite = " · ".join(str(ex[k]) for k in ("work", "urn") if ex.get(k))
        if cite:
            out.append(">")
            out.append(f"> <sub>{cite}</sub>")

    rel = e.get("related_entries") or []
    if rel:
        pairs = ", ".join(f"{r.get('lemma', '')} ({r.get('type', '')})"
                          for r in rel if isinstance(r, dict))
        if pairs:
            out.append(f"**Related:** {pairs}")

    srcs = [s.get("id") for s in (e.get("sources") or []) if isinstance(s, dict)]
    out.append("")
    out.append(footer([s for s in srcs if s], DICT_DIR,
                      label="Entry sources").rstrip())
    return "\n".join(out) + "\n"


def build_dictionary(out_dir: pathlib.Path, entries: list[dict]) -> tuple[int, list[str]]:
    """One file per letter, entries inside sorted by Coptic order."""
    d = out_dir / DICT_DIR
    d.mkdir(parents=True, exist_ok=True)

    buckets: dict[str, list[dict]] = {ch: [] for ch in collate.alphabet_chars()}
    orphans: list[dict] = []
    for e in entries:
        ch = first_letter(e["lemma"])
        (buckets[ch] if ch else orphans).append(e)

    written = 0
    rendered_transliterations = render_scheme_transliterations(entries)
    for ch in collate.alphabet_chars():
        stem, display = letter_index(ch)
        group = sorted(buckets[ch], key=lambda e: collate.sort_key(e["lemma"]))
        lines = [GENERATED_NOTE, "",
                 f"# {display}", "",
                 f"**{len(group)} entr{'y' if len(group) == 1 else 'ies'}**",
                 ""]
        if group:
            lines.append("---")
            lines.append("")
            lines.extend(render_entry(e, rendered_transliterations.get(e.get("id") or ""))
                         for e in group)
        else:
            lines.append("_No entries yet._")
            lines.append("")
        all_sources = [s.get("id") for e in group
                       for s in (e.get("sources") or []) if isinstance(s, dict)]
        lines.append(footer(all_sources, DICT_DIR,
                            label="Sources in this file").rstrip())
        (d / f"{stem}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        written += 1

    if orphans:
        # Never drop data silently. A lemma that files under no Coptic letter is
        # a merge bug, and it belongs in the report, not in a landfill file.
        stem, _ = letter_index(collate.alphabet_chars()[0])
        listed = "\n".join(f"- `{e.get('lemma')}` (id `{e.get('id')}`)"
                           for e in sorted(orphans,
                                           key=lambda e: collate.sort_key(e["lemma"])))
        (d / "ZZ Unfiled lemmas.md").write_text(
            GENERATED_NOTE + "\n\n# Unfiled lemmas\n\n"
            f"**{len(orphans)} lemma(s) begin with no letter in the canonical "
            "alphabet.** This is a merge bug, not a content decision.\n\n"
            + listed + "\n"
            + footer([s.get("id") for e in orphans
                      for s in (e.get("sources") or []) if isinstance(s, dict)],
                     DICT_DIR, label="Sources in this file"), encoding="utf-8")
        written += 1

    return written, [f"{e.get('lemma')}" for e in orphans]


# ── the corpus, one file per work ────────────────────────────────────────────

def render_work(work: dict, doc: dict) -> str:
    verses = doc.get("verses") or []
    lines = [GENERATED_NOTE, "",
             f"# {doc.get('title') or work.get('title')}", ""]

    meta = []
    if work.get("dialect"):
        meta.append(f"**Dialect:** {work['dialect']}"
                    + (" (Sahidic)" if work["dialect"] == "S" else
                       " (Bohairic)" if work["dialect"] == "B" else ""))
    if work.get("tier"):
        meta.append(f"**Tier:** {work['tier']}")
    if work.get("urn"):
        meta.append(f"**URN:** `{work['urn']}`")
    if doc.get("licence"):
        meta.append(f"**Licence:** {doc['licence']}")
    meta.append(f"**Verses:** {len(verses)}")
    lines.append("  \n".join(meta))
    lines.append("")

    if work.get("dialect") == "B":
        # v4 §10.2. The vault must not imply a parity the data does not have.
        lines.append(
            "> **Bohairic coverage is thinner than Sahidic.** Most annotated "
            "text, lexicography and teaching material for Coptic is Sahidic. "
            "Bohairic is presented first because it is the language the living "
            "Church uses — that is a *presentation* decision, not a claim of "
            "equal data. Where coverage is thin this project says so rather than "
            "substituting Sahidic silently.")
        lines.append("")

    # Derived from the DATA, not from shipped.toml's claim. A manifest that
    # says alignment="full" while the document carries no translation would
    # otherwise render Coptic with no English and no explanation, which reads as
    # a parsing failure rather than a missing resource.
    have_tr = any((v.get("translation") or "").strip()
                  for v in verses if isinstance(v, dict))
    claimed = work.get("alignment", "none")
    if not have_tr:
        lines.append("> **No aligned English translation** is available for this "
                     "work yet. The Coptic text is complete; the English is "
                     "missing, not the Coptic.")
        if claimed not in ("none", None):
            print(f"[obsidian] WARNING {work.get('slug')}: shipped.toml claims "
                  f"alignment={claimed!r} but no verse carries a translation. "
                  f"Rendering the truth from the data; fix the manifest.",
                  file=sys.stderr)
        lines.append("")

    lines.append("---")
    lines.append("")
    for v in verses:
        if not isinstance(v, dict):
            continue
        lines.append(f"## {v.get('verse_ref') or v.get('ref') or ''}".rstrip())
        lines.append("")
        lines.append(v.get("coptic", "").strip())
        lines.append("")
        if v.get("translation"):
            lines.append("> " + v["translation"].strip())
            lines.append("")
        if v.get("urn"):
            lines.append(f"<sub>`{v['urn']}`</sub>")
            lines.append("")

    if work.get("note"):
        lines.append("---")
        lines.append("")
        lines.append(f"*{work['note']}*")
        lines.append("")

    lines.append(footer([doc.get("source") or "Scriptorium_TT"], CORPUS_DIR).rstrip())
    return "\n".join(lines) + "\n"


def build_corpus(out_dir: pathlib.Path, dist: pathlib.Path,
                 works: list[dict]) -> tuple[int, list[str]]:
    d = out_dir / CORPUS_DIR
    d.mkdir(parents=True, exist_ok=True)
    written, missing = 0, []
    for w in works:
        doc_path = dist / "corpus" / f"{w['slug']}.json"
        if not doc_path.is_file():
            missing.append(w["slug"])
            continue
        doc = json.loads(doc_path.read_text(encoding="utf-8"))
        (d / f"{_slug(w.get('title') or w['slug'])}.md").write_text(
            render_work(w, doc), encoding="utf-8")
        written += 1
    return written, missing


# ── lessons ──────────────────────────────────────────────────────────────────

def build_lessons(out_dir: pathlib.Path, content: pathlib.Path) -> int:
    d = out_dir / LESSONS_DIR
    d.mkdir(parents=True, exist_ok=True)
    src = content / "lessons"
    files = sorted(p for p in src.glob("*.md") if not p.name.startswith("_"))
    if not files:
        (d / "README.md").write_text(
            GENERATED_NOTE + "\n\n# Lessons\n\n"
            "_No lessons have been written yet. They live in `content/lessons/` "
            "in the repository as plain Markdown — see CONTRIBUTING.md._\n"
            + footer([]), encoding="utf-8")
        return 1
    for p in files:
        body = p.read_text(encoding="utf-8").rstrip()
        if "generated by tools/emit/obsidian.py" not in body.lower():
            body = GENERATED_NOTE + "\n\n" + body
        (d / p.name).write_text(body + "\n" + footer([], LESSONS_DIR), encoding="utf-8")
    return len(files)


# ── meta pages ───────────────────────────────────────────────────────────────

def build_meta(out_dir: pathlib.Path, dist: pathlib.Path,
               letters: int, entries: int, works: int, lessons: int) -> int:
    d = out_dir / META_DIR
    d.mkdir(parents=True, exist_ok=True)

    rows = load_licences(dist)
    included = [r for r in rows if "data/dist" in (r.get("scope") or "").lower()]
    excluded = [r for r in rows if r not in included]

    def _row_md(row: dict) -> list[str]:
        out = [f"## {row.get('name') or row.get('id')} (`{row.get('id')}`)", ""]
        out.append(f"- **Licence:** {row.get('licence') or 'UNKNOWN'}")
        out.append(f"- **Originators:** {row.get('originators') or '—'}")
        out.append(f"- **Reference:** {row.get('reference') or '—'}")
        if row.get("notes"):
            out.append(f"- **Notes:** {row['notes']}")
        out.append("")
        return out

    lines = ["# Licences", "",
             "**This page is generated from `data/dist/provenance/LICENSES.csv`, "
             "which is enforced by `tools/validate/licence_guard.py`.** If a "
             "source is missing here, it is missing from the build — that is a "
             "bug, not an omission.", "",
             "## Sources whose content IS in this vault", "",
             f"{len(included)} source(s). Everything in this vault derives from "
             "these.", ""]
    for row in included:
        lines.extend(_row_md(row))

    # Session 5 D8 / C4: an explicit, dated, public note about CDO.
    #
    # CDO gets its own paragraph rather than a row in the excluded list because
    # the row is easy to miss and the omission is significant: CDO is the
    # backbone source for URN-linked examples and frequencies, so its absence is
    # a real gap in coverage, not just one more excluded licence.
    #
    # No parser was written for it (C4), and that is stated here so nobody reads
    # the absence as an oversight. The issue link is a PLACEHOLDER on purpose --
    # inventing a URL would be exactly the provenance-from-memory this project
    # forbids (invariant 7). It must be filled in when the issue is opened.
    lines += ["## Coptic Dictionary Online (CDO) — not included, and why", "",
              "**Coptic Dictionary Online (CDO) data is not included in this "
              "build.** The public CDO API does not currently serve "
              "machine-readable entries; `coptic-dictionary.org` returns its "
              "single-page application at every `/api/*` path, and no bulk "
              "export repository is published. We have contacted the KELLIA "
              "maintainers and asked whether a bulk export or a documented API "
              "endpoint exists, and under what licence.", "",
              "**Status: open, as of 2026-10-05.** The tracking issue has not "
              "been filed yet — see the open questions in `DECISIONS.md` for who "
              "is raising it. Until then:", "",
              "- no CDO-derived entry, example, frequency or URN appears "
              "anywhere in this build;",
              "- the `_TT`/TEI parser has **no CDO dialect at all**, deliberately, "
              "rather than a guess at a format none of us has seen (a parser "
              "built from an imagined schema would produce plausible-looking "
              "wrong data, which is worse than no data);",
              "- `tools/sources.lock` records CDO as `ingested = false` with this "
              "reason, so the omission is machine-visible and not only prose.",
              "",
              "This is a known gap in coverage, stated publicly rather than left "
              "for someone to discover. If you need CDO-sourced examples today, "
              "they are not here; if you can tell us how to obtain a machine-"
              "readable export, that unblocks the largest remaining gap in the "
              "dictionary's examples and frequencies.", ""]

    lines += ["## Sources deliberately NOT in this vault", "",
              f"{len(excluded)} source(s). **None of their content appears "
              "anywhere in this vault.** They are listed so the boundary is "
              "visible rather than invisible — a reader deserves to know what "
              "was left out and why. Naming a source and its licence is not the "
              "same as redistributing its text.", ""]
    for row in excluded:
        out = _row_md(row)
        out.insert(1, f"- **Scope:** {row.get('scope') or '—'} — "
                      f"**excluded from this vault**")
        lines.extend(out)
    lines.append(footer(["ProjectRebuild"], META_DIR).rstrip())
    (d / "Licences.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    credits = ["# Credits", "",
               "**Two different questions, and conflating them is how projects "
               "mis-credit people.**", "",
               "## Who wrote this project", "",
               "Michael Helmy, with contributors. The software is Apache-2.0. "
               "Prose and reconstructions authored here are PD. See "
               "[AUTHORS.md](https://github.com/coptic-reference/coptic-reference"
               "/blob/main/AUTHORS.md).", "",
               "## Who made the data", "",
               "The data is not ours. Every entry and every text carries the "
               "attribution of the people who made it — the Comprehensive Coptic "
               "Lexicon (BBAW + DDGLC), Coptic Dictionary Online (the KELLIA "
               "alliance), the Coptic Scriptorium corpora (Schroeder, Zeldes, "
               "Platte, Claassen and contributors), Wiktextract via kaikki.org, "
               "W. O. J. Crum, and the UD treebanks. Per-source detail is on the "
               "[Licences](Licences.md) page.", "",
               "## What we changed", "",
               "Merging sources means changing things: de-duplicating senses, "
               "reordering them, stripping diacritics, splitting by dialect. "
               "Every entry in this vault records what was done, per entry, in "
               "its own `attributions[]`. Nothing is presented as upstream's "
               "wording when it is ours.", "",
               "## What we did not do", "",
               "No CC BY-NC material appears in this vault. It is checked "
               "mechanically by `tools/validate/nc_guard.py`, which is a "
               "fail-closed allowlist: an unknown source is a violation, not a "
               "maybe.", ""]
    credits.append(footer(["ProjectRebuild"], META_DIR).rstrip())
    (d / "Credits.md").write_text("\n".join(credits) + "\n", encoding="utf-8")

    start = [
        "# 00 START HERE", "",
        "This is the **Coptic Reference** as an [Obsidian](https://obsidian.md) "
        "vault: the whole reference as plain Markdown you can grep, edit, and "
        "keep offline.", "",
        "> **The text is text.** Coptic here is ordinary Unicode — no images, no "
        "SVG, no pictures of letters. It is selectable, searchable, and readable "
        "by a screen reader, exactly as it should be.", "",
        "## What is in this vault", "",
        "| Folder | What |",
        "|---|---|",
        f"| `{DICT_DIR}/` | The dictionary, **one file per Coptic letter** "
        f"({letters} files, {entries} entries). Sorted in Coptic alphabetical "
        "order, not by Unicode codepoint. |",
        f"| `{CORPUS_DIR}/` | The shipped corpus, one file per work "
        f"({works} works), with aligned English where it exists. |",
        f"| `{LESSONS_DIR}/` | Lessons ({lessons}), copied unchanged from the "
        "repository. |",
        f"| `{META_DIR}/` | Licences and credits. Read these before "
        "republishing anything here. |",
        "",
        "## Where to start", "",
        f"1. New to the language? Read the lessons in `{LESSONS_DIR}/`, then look "
        f"a word up in `{DICT_DIR}/`.",
        "2. Looking something up? Open the file for its **first letter**. "
        "Coptic sorts by its own alphabet: ϣ sorts *after* Ⲱ, which is why "
        "Unicode sort order is wrong for this language.",
        "3. Reading a text? The corpus files carry the URN of every verse, so "
        "you can cite precisely.", "",
        "## Fonts", "",
    ]
    fonts = sorted((ROOT / "static" / "fonts").glob("*.woff2")) + \
        sorted((ROOT / "static" / "fonts").glob("*.ttf"))
    if fonts:
        fdir = out_dir / ".obsidian" / "fonts"
        fdir.mkdir(parents=True, exist_ok=True)
        for f in fonts:
            shutil.copy2(f, fdir / f.name)
        start += [f"The vault bundles {len(fonts)} font file(s) in "
                  "`.obsidian/fonts/`. `.obsidian/appearance.json` is configured "
                  "to use them. No plugin is required or enabled.", ""]
    else:
        start += [
            "**No Coptic webfont is bundled yet.** The project's subset "
            "(OFL-licensed, covering the 22 letters of `tools/collate.py`) is "
            "planned for `static/fonts/` but has not been built — see "
            "`CONTRIBUTING.md` §4.", "",
            "Obsidian will fall back to a system font with Coptic coverage. On "
            "Linux that usually means `fonts-noto-core` or GNU FreeFont; on "
            "macOS/Windows, most system fonts already cover the Coptic block. "
            "If Coptic shows as boxes, install one of the above rather than "
            "converting the text to images.", ""]
    start += ["## Licence", "",
              "The vault is a download of a CC BY-SA / CC BY / PD corpus plus "
              "Apache-2.0 project code. **Re-check `99 Meta/Licences.md` before "
              "you republish any of it** — in particular the Kaikki extract is "
              "dual-licensed `CC BY-SA 4.0 OR GFDL`, and five sources listed "
              "there have licences we have not yet verified.", "",
              footer(["ProjectRebuild"], "").rstrip()]
    (out_dir / "00 START HERE.md").write_text("\n".join(start) + "\n", encoding="utf-8")
    return 3  # START HERE + Licences + Credits


# ── .obsidian config: fonts only, no plugins ─────────────────────────────────

def build_obsidian_config(out_dir: pathlib.Path) -> int:
    """Minimal config. Explicitly NO community plugins.

    A vault that asks to run third-party code is a worse thing to hand someone
    than no vault at all, and the config below is deliberately the smallest
    thing that makes Coptic render. `communityPlugins` is written as an empty
    list on purpose so it is visible in the diff that we meant it.
    """
    d = out_dir / ".obsidian"
    d.mkdir(parents=True, exist_ok=True)

    appearance = {
        "textFontFamily": "Coptic Reference, Noto Sans Coptic, GNU FreeFont, serif",
        "interfaceFontFamily": "Coptic Reference, system-ui, sans-serif",
        "monospaceFontFamily": "Coptic Reference, monospace",
        "cssTheme": "",
        "baseFontSize": 18,
    }
    (d / "appearance.json").write_text(
        json.dumps(appearance, indent=2) + "\n", encoding="utf-8")

    app = {
        "alwaysUpdateLinks": True,
        "newFileLocation": "folder",
        "newFileFolderPath": "30 Lessons",
        "attachmentFolderPath": "99 Meta",
        "showUnsupportedFiles": True,
        "readableLineLength": False,
        "strictLineBreaks": False,
        "communityPlugins": [],
        "communityPluginsSortOrder": [],
    }
    (d / "app.json").write_text(json.dumps(app, indent=2) + "\n", encoding="utf-8")

    core = {"fileRecovery": {"enabled": False},
            "plugins": {"legacy": False}}
    (d / "core-plugins.json").write_text(json.dumps(core, indent=2) + "\n",
                                         encoding="utf-8")

    # A README inside .obsidian so nobody wonders whether it is safe to open.
    (d / "README.md").write_text(
        "# .obsidian/\n\n"
        "Generated by `tools/emit/obsidian.py`. **Fonts and layout only.**\n\n"
        "`communityPlugins` is an empty list and there is no `plugins/` "
        "directory: this vault asks to run **no third-party code**. If a future "
        "version adds one, that is a change worth reviewing on its own, because "
        "a vault is a thing people open without reading it first.\n"
        + footer(["ProjectRebuild"], ".obsidian", label="Sources"),
        encoding="utf-8")
    return 4


# ── zip ──────────────────────────────────────────────────────────────────────

def zip_vault(src: pathlib.Path, dest: pathlib.Path) -> tuple[int, int]:
    files = sorted(p for p in src.rglob("*") if p.is_file())
    # Deterministic order and fixed timestamps so two builds of the same inputs
    # produce a byte-identical zip. Otherwise every build is a spurious diff.
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in files:
            arc = p.relative_to(src.parent).as_posix()
            info = zipfile.ZipInfo(arc, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, p.read_bytes())
    return len(files), dest.stat().st_size


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="build the Obsidian reader vault")
    ap.add_argument("--dist", default=str(ROOT / "data" / "dist"), type=pathlib.Path)
    ap.add_argument("--content", default=str(ROOT / "content"), type=pathlib.Path)
    ap.add_argument("--out", default=str(ROOT / "public" / "downloads" /
                                         "coptic-reference-vault.zip"), type=pathlib.Path)
    ap.add_argument("--keep-dir", type=pathlib.Path,
                    help="also leave the unzipped tree here (for inspection)")
    args = ap.parse_args(argv)

    dist, content = args.dist, args.content
    works = load_shipped(ROOT / "tools" / "shipped.toml")
    entries = load_entries(dist)
    print(f"[obsidian] {len(entries)} entries, {len(works)} shipped works")

    work = args.keep_dir or ROOT / "work" / VAULT_DIRNAME
    if work.exists():
        shutil.rmtree(work)
    out_dir = work / VAULT_DIRNAME
    out_dir.mkdir(parents=True)

    n_dict, orphans = build_dictionary(out_dir, entries)
    n_works, missing = build_corpus(out_dir, dist, works)
    n_lessons = build_lessons(out_dir, content)
    n_meta = build_meta(out_dir, dist, len(collate.alphabet_chars()),
                        len(entries), n_works, n_lessons)
    n_conf = build_obsidian_config(out_dir)

    total = sum(1 for _ in out_dir.rglob("*") if _.is_file())
    print(f"[obsidian] {n_dict} letter files, {n_works} work files, "
          f"{n_lessons} lesson files, {n_meta} meta pages, {n_conf} config files")
    if orphans:
        print(f"[obsidian] WARNING {len(orphans)} lemma(s) filed under no letter: "
              f"{', '.join(orphans[:5])}", file=sys.stderr)
    if missing:
        print(f"[obsidian] WARNING {len(missing)} shipped work(s) have no "
              f"data/dist/corpus file: {', '.join(missing)}", file=sys.stderr)

    # The vault is a REDISTRIBUTION surface, and it is not inside data/dist, so
    # nc_guard.py never sees it. Check its payload here: an NC id may appear in
    # 99 Meta/Licences.md as a notice of exclusion, and nowhere else. This is a
    # hard failure, not a warning — invariant 5 does not care where a file lives.
    payload = [p for p in out_dir.rglob("*")
               if p.is_file() and META_DIR not in p.parts]
    for p in payload:
        text = p.read_text(encoding="utf-8", errors="ignore")
        for sid in sorted(nc_guard.NC_ONLY_SOURCES):
            if sid in text:
                raise VaultError(
                    f"[obsidian] {p.relative_to(out_dir)}: contains NC source "
                    f"{sid!r}. NC content must never reach a redistribution "
                    f"surface, including this one. Fail closed."
                )
    print(f"[obsidian] NC scan of {len(payload)} payload files: clean "
          f"(NC ids permitted only in {META_DIR}/Licences.md, as exclusions)")

    # The two hard limits, asserted rather than assumed.
    if total > MAX_FILES:
        raise VaultError(f"[obsidian] {total} files exceeds the {MAX_FILES}-file "
                         f"limit. A vault this size is not something anyone opens.")
    print(f"[obsidian] file count {total} <= {MAX_FILES}  OK")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    n, size = zip_vault(out_dir, args.out)
    mib = size / (1024 * 1024)
    print(f"[obsidian] {n} files, {size:,} bytes ({mib:.2f} MiB) -> {args.out}")
    if size > MAX_BYTES:
        raise VaultError(f"[obsidian] {mib:.2f} MiB exceeds the "
                         f"{MAX_BYTES // (1024 * 1024)} MiB per-file limit.")

    if not args.keep_dir:
        shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
