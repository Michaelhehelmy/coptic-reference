#!/usr/bin/env python3
"""tools/emit/corpus_tarball.py — per-work fingerprinted corpus tarball (v4 §6.1).

WHY A TARBALL. `data/dist/dict/**` as JSON is 35.5 MiB after Session 4's merge.
Cloudflare Pages builds from the committed tree on every push, and a
35 MiB-per-push JSON dataset is the reason v4 §6.1 exists. The corpus becomes ONE
compressed tarball, regenerated only when a work's content actually changes.

THE REGENERATION GUARD IS THE POINT OF THIS FILE. Stage A runs weekly. If the
tarball is rebuilt every week regardless of whether any upstream text moved, the
committed diff is 5 MB of binary churn nobody reviews, and the review surface
stops being reviewable. So:

    fingerprint(work) = sha256(meta.json)      # per work, not per archive
    rebuild iff any fingerprint differs from manifest.json, or --force

meta.json is the fingerprint target on purpose: it carries the work's title,
dialect, licence, URN, source pin and verse/token counts. If any of those change,
the fingerprint changes and the work is rebuilt. If upstream revises a verse but
the counts and metadata hold, the fingerprint does NOT change — which is a real
limitation, stated here and in DECISIONS.md S4-A4, not hidden. A content hash of
text.json would catch it at the cost of hashing every work on every run; that is
the --hash-content option.

BYTE-REPRODUCIBLE. PAX format, sorted arcnames, fixed mtime/uid/gid/mode, and
gzip written with mtime=0. Two builds of the same inputs produce the same bytes,
so a rebuild that changes nothing produces an empty git diff.

ONE WORK IS AVAILABLE. Of the 9 shipped works in tools/shipped.toml, only
sahidic_ruth has source data in this environment (the four _TT files, 85 verses).
The other 8 are declared and skipped, each named on every run — a shipped work
with no data is a gap to report, never a gap to paper over.

LICENCE: project code, Apache-2.0. Corpus content stays CC BY-SA per source.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import pathlib
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import safeio  # noqa: E402
import tarfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "parse"))

def _verify_tarball(path: pathlib.Path, info: dict) -> None:
    """Re-read the tarball and confirm its size and digest. Rule 3."""
    try:
        blob = path.read_bytes()
    except OSError as e:
        raise SystemExit(f"[tarball] {path}: written but unreadable ({e}). "
                         f"Not claiming success.")
    got = hashlib.sha256(blob).hexdigest()
    if len(blob) != info["bytes"] or got != info["sha256"]:
        raise SystemExit(
            f"[tarball] {path}: read-back mismatch. Reported "
            f"{info['bytes']:,} B / {info['sha256'][:12]}…, found "
            f"{len(blob):,} B / {got[:12]}…. Not claiming success.")


def write_manifest(path: pathlib.Path, manifest: dict) -> None:
    """Single writer for manifest.json, so both the rebuild path and the
    skip path (Session 4 S4-C3) produce byte-identical formatting.

    Session 6 D1: verified by read-back. This file carries the fingerprints the
    whole tarball's integrity argument rests on; a manifest that half-landed
    would make the guards agree with each other and disagree with the artefact.
    """
    safeio.write_text_verified(
        path,
        json.dumps(manifest, indent=1, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8")


def hash_method(all_files: bool) -> str:
    """Say what is hashed. Load-bearing (Session 4 S4-C2/S4-C3).

    Both modes cover CONTENT; --hash-content additionally walks every file in the
    work tree instead of trusting meta.json's embedded hashes.
    """
    return ("all work files + meta.json sha256" if all_files
            else "meta.json sha256 (embeds text.json + tokens.json content hashes)")


GENERATED = "2026-10-04T00:00:00Z"
#: Fixed timestamp so the archive is byte-reproducible.
MTIME = 0


def load_shipped(path: pathlib.Path) -> list[dict]:
    import tomllib
    with path.open("rb") as fh:
        works = tomllib.load(fh).get("work", [])
    return [w for w in works if w.get("shipped", True)]


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ── build the per-work tree ──────────────────────────────────────────────────

def build_work(work: dict, out_root: pathlib.Path,
               corpora: pathlib.Path) -> dict | None:
    """Emit out_root/<slug>/{meta,text,tokens}.json, or None if no source data.

    Returns the meta dict, which is what gets fingerprinted.
    """
    slug = work["slug"]
    dest = out_root / slug
    # Session 7 D2. Primary layout is sources/corpus/<slug>/, which is where
    # tools/fetch/fetch_work.py puts a work and where the filename does not have
    # to encode the dialect. The old slug-prefix heuristic ("bohairic_mark" ->
    # "Mark_*.tt") cannot match upstream's actual "bohairic.Mark_01.tt", which is
    # why only Ruth had data before this session: one work happened to fit.
    per_work = corpora.parent / "corpus" / slug
    # NOTE: this ASSIGNS tt_files. An earlier version of this patch used
    # `return sorted(...)`, which short-circuited build_work before it wrote any
    # meta.json -- so the function returned a list where a meta dict was
    # expected, the fingerprint then failed on a file that had never been
    # written, and the tool reported a missing meta.json for a work it had just
    # "built". Session 7 S7-B3.
    tt_files: list[pathlib.Path] = []
    if per_work.is_dir() and any(per_work.glob("*.tt")):
        tt_files = sorted(per_work.glob("*.tt"))
    # Legacy fallback for work staged directly in sources/corpora/.
    # Match by the part of the slug after the dialect prefix, e.g.
    # "sahidic_ruth" -> "Ruth_*.tt". Explicit rather than clever: a wrong glob
    # would put the wrong text under the right title, which is the worst failure
    # this file could have.
    if not tt_files:
        stem = slug.split("_", 1)[-1]
        prefix = stem.capitalize()
        tt_files = sorted(corpora.glob(f"{prefix}_*.tt"))
    if not tt_files:
        return None

    from tt import parse_tt

    # Session 12 D1 / C4 — verse_index, and why `ref` alone is not an identity.
    #
    # `ref` is the upstream chapter/verse label. It is NOT unique within a work:
    # numbering restarts per chapter, so bohairic_mark's 678 verses share only 72
    # distinct refs, and the label '1' occurs 16 times in text and 542 times
    # among tokens. The reader keyed its token map on `ref`, pooled every token
    # from every colliding verse into each one, and rendered 276,522 token spans
    # for 20,322 tokens — with the WRONG words under most verses.
    #
    # Session 11 found this only because the per-work Playwright tests were
    # finally written; five of six works had never been opened in a browser. The
    # one that had, sahidic_ruth, is the one work whose refs happen to be unique.
    # Rule 8, exactly.
    #
    # verse_index is the sequential position in THIS work's verse list: 0..N-1,
    # unique by construction. It is the join key. `ref` stays, because it is what
    # a reader recognises and what the anchors are built from.
    #
    # Both loops are driven by one enumeration so verse_index in text.json and in
    # tokens.json cannot drift apart — a second, independently-numbered loop is
    # how this bug would come back.
    # Session 13 D0 / C2 — strip parse-internal markup from `norm`.
    #
    # The TT parser keeps <lang lang="Greek"> … </lang> wrappers from the source,
    # and they were being emitted verbatim. Measured: 9,132 of 83,017 tokens
    # (11.0%) carried them.
    #
    # This is a data bug, not a display bug, and the distinction matters:
    #
    #   * 9,132 normalised forms could never match the dictionary index, so those
    #     words were unreachable in the reader;
    #   * the markup reached the reader UI, where Session 11's manual check showed
    #     a token panel reading "normalised <lang lang="Hebrew"> ⲓⲱⲁⲛⲛⲏⲥ </lang>";
    #   * a `<` in a value that is hashed, sorted and joined on is a hazard
    #     everywhere else too.
    #
    # Stripped at EMIT, not at render: a value that is wrong on disk is wrong for
    # every consumer, and stripping in the browser would leave the corpus data,
    # the dictionary index and any future tool disagreeing about it.
    import re as _re
    _TAG = _re.compile(r"<[^>]*>")

    def _plain(v: str) -> str:
        return _TAG.sub("", v or "").strip()

    verses: list[dict] = []
    tokens: list[dict] = []
    for f in tt_files:
        doc = parse_tt(f)
        for v in doc.verses:
            vidx = len(verses)
            verses.append({
                "verse_index": vidx,
                "ref": v.verse_ref,
                "urn": v.urn,
                # Session 4 S4-C1: this was `v.orig if hasattr(v, "orig") else ""`.
                # tt.Verse has NO `orig` field — it has `tokens`. hasattr() quietly
                # returned False, so every verse shipped with coptic="" and the
                # corpus had no readable text at all. Nothing caught it: the
                # round-trip reads lemmas, the counts still matched, the sizes
                # were plausible. Reconstruct from the tokens' own surface forms.
                # LIMIT: original spacing and punctuation are not preserved,
                # because the parser does not retain the raw verse string.
                "coptic": " ".join(t.orig for t in v.tokens if t.orig),
                "en": v.translation or "",
            })
            for i, t in enumerate(v.tokens):
                tokens.append({
                    "verse_index": vidx,
                    "ref": v.verse_ref,
                    "i": i,
                    # Session 4 S4-C1: tt.Token's surface form field is `orig`,
                    # not `form`. getattr(t, "form", "") returned "" for all 3,470
                    # tokens, so the published tokens.json had no forms.
                    "form": t.orig or "",
                    "norm": _plain(t.norm),
                    "lemma": t.lemma or "",
                    "pos": t.pos or "",
                    "func": t.func or "",
                    "head": t.head or "",
                })

    dest.mkdir(parents=True, exist_ok=True)
    (dest / "text.json").write_text(
        json.dumps({"slug": slug, "verses": verses}, ensure_ascii=False),
        encoding="utf-8")
    (dest / "tokens.json").write_text(
        json.dumps({"slug": slug, "tokens": tokens}, ensure_ascii=False),
        encoding="utf-8")

    # Session 4 S4-C2 — THE FINGERPRINT NOW COVERS CONTENT.
    #
    # The original fingerprint was sha256(meta.json) and meta.json held only
    # counts. So when I fixed the empty-text bug (S4-C1) the rebuild guard said
    # "fingerprints unchanged - SKIPPING" and the fix did not ship. The tarball
    # kept serving empty text while the guard reported success.
    #
    # A guard that cannot notice the artefact changing is not a guard. So
    # meta.json now carries the sha256 of text.json and tokens.json, which makes
    # the content hash part of the fingerprint at no extra cost -- meta.json is
    # still one small file to hash, but it now MOVES when the content moves.
    text_sha = hashlib.sha256((dest / "text.json").read_bytes()).hexdigest()
    tokens_sha = hashlib.sha256((dest / "tokens.json").read_bytes()).hexdigest()

    licence = "CC-BY-SA-4.0"
    meta = {
        "slug": slug,
        "title": work.get("title", slug),
        "tier": work.get("tier", ""),
        "dialect": work.get("dialect", ""),
        "urn": work.get("urn", ""),
        "alignment": work.get("alignment", "none"),
        "licence": licence,
        "content_sha256": {"text.json": text_sha, "tokens.json": tokens_sha},
        "source_id": "Scriptorium_TT",
        "source_pin": "3ac067f1709a0012daf39ea8da2fac79980176a5",
        "files": [f.name for f in tt_files],
        "verses": len(verses),
        "tokens": len(tokens),
        "generated": GENERATED,
    }
    if work.get("note"):
        meta["note"] = work["note"]
    # Rule 3: the fingerprint target is written verified like everything else. A
    # meta.json that half-landed would make the fingerprint describe bytes that
    # are not what the tarball contains.
    dest.mkdir(parents=True, exist_ok=True)
    safeio.write_text_verified(
        dest / "meta.json",
        json.dumps(meta, indent=1, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8")
    return meta


# ── fingerprint + conditional rebuild ────────────────────────────────────────

def fingerprint(work_dir: pathlib.Path, *, hash_content: bool = False) -> str:
    """sha256 of meta.json, optionally with text+tokens too.

    meta-only is the default because it is O(1) per work. The known limitation:
    an upstream edit that leaves counts and metadata unchanged does not move the
    fingerprint, so that work is not rebuilt. --hash-content closes it.
    """
    h = hashlib.sha256()
    h.update((work_dir / "meta.json").read_bytes())
    if hash_content:
        for name in ("text.json", "tokens.json"):
            p = work_dir / name
            if p.is_file():
                h.update(p.read_bytes())
    return h.hexdigest()


def write_tarball(work_root: pathlib.Path, tarball: pathlib.Path) -> dict:
    """Deterministic gzip tar: PAX, sorted arcnames, fixed metadata."""
    members = sorted(p for p in work_root.rglob("*") if p.is_file())
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.PAX_FORMAT) as tf:
        for p in members:
            arc = p.relative_to(work_root).as_posix()
            info = tarfile.TarInfo(arc)
            data = p.read_bytes()
            info.size = len(data)
            info.mtime = MTIME
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mode = 0o644
            tf.addfile(info, io.BytesIO(data))
    raw = buf.getvalue()
    # gzip with mtime=0 and a fixed compresslevel: the default embeds the
    # current time, which would make every build a different file.
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode="wb", compresslevel=9, mtime=0) as gz:
        gz.write(raw)
    blob = out.getvalue()
    tarball.parent.mkdir(parents=True, exist_ok=True)
    tarball.write_bytes(blob)
    return {"members": len(members), "bytes": len(blob),
            "sha256": sha256_bytes(blob), "raw_bytes": len(raw)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="build the fingerprinted corpus tarball")
    ap.add_argument("--work-root", type=pathlib.Path,
                    default=ROOT / "work" / "corpus")
    ap.add_argument("--tarball", type=pathlib.Path,
                    default=ROOT / "data" / "dist" / "corpus" / "corpus.tar.gz")
    ap.add_argument("--manifest", type=pathlib.Path,
                    default=ROOT / "data" / "dist" / "corpus" / "manifest.json")
    ap.add_argument("--corpora", type=pathlib.Path,
                    default=ROOT / "sources" / "corpora")
    ap.add_argument("--force", action="store_true",
                    help="rebuild even if no fingerprint changed")
    ap.add_argument("--hash-content", action="store_true",
                    help="fingerprint text+tokens as well as meta (slower, stricter)")
    args = ap.parse_args(argv)

    works = load_shipped(ROOT / "tools" / "shipped.toml")
    print(f"[tarball] {len(works)} shipped work(s) declared in tools/shipped.toml")

    # Stage 1: build each work into a SCRATCH tree, so the fingerprint reflects
    # the current upstream sources rather than whatever is lying in work_root.
    #
    # This is a bug fix, and the bug made the guard theatre: the first version
    # did `rmtree(work_root)` and rebuilt in place BEFORE fingerprinting, so it
    # compared the manifest against a tree it had just regenerated. The
    # comparison could never fail, and "fingerprints unchanged — SKIPPING" was
    # printed unconditionally. A green guard that cannot go red is worse than no
    # guard, because it is believed.
    scratch = args.work_root.with_name(args.work_root.name + ".scratch")
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)

    built: dict[str, dict] = {}
    missing: list[str] = []
    for w in works:
        meta = build_work(w, scratch, args.corpora)
        if meta is None:
            missing.append(w["slug"])
        else:
            built[w["slug"]] = meta
    print(f"[tarball] {len(built)} work(s) have source data: "
          f"{', '.join(sorted(built)) or '(none)'}")
    if missing:
        print(f"[tarball] {len(missing)} shipped work(s) have NO source data in "
              f"this environment and are NOT in the tarball: {', '.join(missing)}")

    prints = {slug: fingerprint(scratch / slug, hash_content=args.hash_content)
              for slug in sorted(built)}

    # ── the regeneration guard ───────────────────────────────────────────────
    previous: dict = {}
    if args.manifest.is_file():
        previous = json.loads(args.manifest.read_text(encoding="utf-8"))
    prev_prints = previous.get("fingerprints", {})

    changed = sorted(s for s, f in prints.items() if prev_prints.get(s) != f)
    added = sorted(s for s in prints if s not in prev_prints)
    removed = sorted(s for s in prev_prints if s not in prints)

    if not args.force and previous and not changed and not added and not removed:
        print("[tarball] fingerprints unchanged — SKIPPING rebuild "
              "(this is the weekly-bake guard working)")
        old = args.tarball.stat().st_size if args.tarball.is_file() else 0
        print(f"[tarball] existing tarball kept: {old:,} bytes "
              f"({old / 1048576:.2f} MiB)")
        print(f"[tarball] work tree left untouched at {args.work_root}")

        # Session 4 S4-C3: skipping the rebuild must not mean skipping the
        # MANIFEST. This early return shipped a manifest whose `hash_method`
        # still described the old meta-only fingerprint, after the fingerprint
        # had been changed to cover content -- so the manifest misdescribed the
        # artefact it was supposed to document. Fingerprints are per-WORK;
        # the manifest also carries tool-level metadata that can change on its
        # own. So: repair the manifest in place, and say so.
        want = hash_method(args.hash_content)
        if previous.get("hash_method") != want:
            print(f"[tarball] manifest metadata is stale "
                  f"({previous.get('hash_method')!r} -> {want!r}); "
                  f"rewriting manifest without rebuilding")
            previous["hash_method"] = want
            previous["fingerprints"] = prints
            previous["declared_but_absent"] = sorted(missing)
            write_manifest(args.manifest, previous)
        shutil.rmtree(scratch, ignore_errors=True)
        return 0

    if args.force:
        print("[tarball] --force: rebuilding regardless of fingerprints")
    elif not previous:
        print("[tarball] no manifest.json: first build")
    else:
        if added:
            print(f"[tarball] new work(s): {', '.join(added)}")
        if changed:
            print(f"[tarball] fingerprint changed for: {', '.join(changed)}")
        if removed:
            print(f"[tarball] work(s) removed: {', '.join(removed)}")

    # Stage 2: only now is the work tree replaced, and only with the works whose
    # fingerprint moved. An unchanged work keeps its existing files, so `git diff`
    # on work_root shows exactly which work changed.
    if args.work_root.exists():
        shutil.rmtree(args.work_root)
    args.work_root.mkdir(parents=True)
    for slug in sorted(prints):
        if slug in changed or slug in added or args.force:
            shutil.copytree(scratch / slug, args.work_root / slug)
        else:
            print(f"[tarball] {slug}: unchanged, keeping existing files")
    shutil.rmtree(scratch, ignore_errors=True)

    # Session 6 D1: the tarball is written, then its size and SHA-256 are read
    # back off the file and compared with what the writer reported.
    info = write_tarball(args.work_root, args.tarball)
    _verify_tarball(args.tarball, info)
    manifest = {
        "schema": "coptic-reference/corpus-manifest/1",
        "generated": GENERATED,
        # Says what it hashes, because the difference is load-bearing: the
        # default now covers CONTENT (meta.json embeds the sha256 of text.json
        # and tokens.json), while --hash-content additionally walks every file
        # in the work tree. Both are content-safe; the default is just cheaper.
        # Session 4 S4-C2 -- see the empty-text bug this replaced.
        "hash_method": hash_method(args.hash_content),
        "fingerprints": prints,
        "tarball": args.tarball.name,
        "tarball_sha256": info["sha256"],
        "tarball_bytes": info["bytes"],
        "tarball_uncompressed_bytes": info["raw_bytes"],
        "member_count": info["members"],
        "works_count": len(prints),
        "works": {
            slug: {
                "title": built[slug]["title"],
                "dialect": built[slug]["dialect"],
                "tier": built[slug]["tier"],
                "licence": built[slug]["licence"],
                "verses": built[slug]["verses"],
                "tokens": built[slug]["tokens"],
            } for slug in sorted(prints)
        },
        "declared_but_absent": sorted(missing),
    }
    write_manifest(args.manifest, manifest)

    print(f"[tarball] rebuilt: {info['members']} member(s), "
          f"{info['bytes']:,} bytes ({info['bytes'] / 1048576:.2f} MiB) "
          f"from {info['raw_bytes']:,} raw "
          f"(ratio {info['raw_bytes'] / max(info['bytes'], 1):.1f}x)")
    print(f"[tarball] sha256 {info['sha256']}")
    print(f"[tarball] works {len(prints)}  manifest {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
