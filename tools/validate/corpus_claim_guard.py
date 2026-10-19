#!/usr/bin/env python3
"""tools/validate/corpus_claim_guard.py — written English counts must match the corpus.

Session 26 D1 (E38's guard). The claim "587 real English segments" for
shenoute_eagerness counted the source's ASCII "..." placeholders as English;
the true count was 21 of 1,078. The claim lived in code comments and in the
shipped.toml note that FLOWS INTO meta.json whenever corpus_tarball runs, so
the only reason the deployment never carried it is that the correction landed
in the same push as the introduction. This guard makes that timing accident
unnecessary: any numeric "real English" claim written down anywhere that
reaches a reader is checked against the corpus artefact itself.

Truth source (Rule 12, one reader): data/dist/corpus/corpus.tar.gz, the same
tarball every other guard reads. A claim surface with no numeric claim passes
trivially — the guard polices claims that exist, it does not demand them.

Claim surfaces, in the order the 587 bug could have travelled:

  1. tools/shipped.toml — per-work ``note`` fields (the source of meta.json).
  2. public/data/corpus/<slug>/meta.json — the emitted form.
  3. content/**/*.md — a claim line must also name the work it describes;
     an unattributed numeric claim is itself a failure (ambiguous claims are
     how 587 survived three comment reviews).

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import tarfile

ROOT = pathlib.Path(__file__).resolve().parents[2]

# "21 of 1,078 segments carry real English" — the full claim shape.
CLAIM_OF = re.compile(
    r"(\d[\d,]*)\s+of\s+(\d[\d,]*)\s+segments?\s+carry\s+real\s+English")
# "21 real English" — the short shape (comments, prose).
CLAIM_SHORT = re.compile(r"(\d[\d,]*)\s+real\s+English")
# Placeholder English: dots and bracket-filler only, nothing else.
PLACEHOLDER = re.compile(r"[\.\u2026\[\]\(\)\s]+")


def is_real(en: str | None) -> bool:
    """Real English prose: non-empty and not the source's placeholder."""
    s = (en or "").strip()
    if not s:
        return False
    return PLACEHOLDER.fullmatch(s) is None


def truth_from_tarball(tarball: pathlib.Path) -> dict[str, dict[str, int]]:
    """{slug: {verses, real}} — read from the shipped artefact, not a parser."""
    out: dict[str, dict[str, int]] = {}
    with tarfile.open(tarball) as tf:
        slugs = sorted({n.split("/")[0] for n in tf.getnames() if "/" in n})
        for slug in slugs:
            try:
                fh = tf.extractfile(f"{slug}/text.json")
            except KeyError:
                continue
            if fh is None:
                continue
            doc = json.load(fh)
            verses = doc.get("verses", [])
            out[slug] = {
                "verses": len(verses),
                "real": sum(1 for v in verses if is_real(v.get("en"))),
            }
    return out


def _num(s: str) -> int:
    return int(s.replace(",", ""))


def _check_claim(claimed_n: int, claimed_m: int | None, slug: str,
                 truth: dict[str, dict[str, int]], where: str,
                 errors: list[str]) -> None:
    if slug not in truth:
        errors.append(f"{where}: claim attributes to {slug!r}, which is not in "
                      f"the corpus tarball")
        return
    real = truth[slug]["real"]
    verses = truth[slug]["verses"]
    if claimed_n != real:
        errors.append(
            f"{where}: claims {claimed_n:,} real English segments for {slug}, "
            f"the tarball has {real:,}")
    if claimed_m is not None and claimed_m != verses:
        errors.append(
            f"{where}: claims {claimed_m:,} segments for {slug}, "
            f"the tarball has {verses:,}")


def _attributed_work(line: str, works: list[dict]) -> str | None:
    """Which work does this line name? Slug first, then title."""
    for w in works:
        if w["slug"] in line:
            return w["slug"]
    for w in works:
        t = w.get("title") or ""
        if t and t.lower() in line.lower():
            return w["slug"]
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="written 'real English' counts must match the corpus")
    ap.add_argument("--dist", type=pathlib.Path,
                    default=ROOT / "data" / "dist")
    ap.add_argument("--root", type=pathlib.Path, default=ROOT,
                    help="repo root (claim surfaces are resolved under it)")
    args = ap.parse_args(argv)

    tarball = args.dist / "corpus" / "corpus.tar.gz"
    if not tarball.is_file():
        print("[corpus_claim_guard] FAIL — no corpus tarball at "
              f"{tarball}; run tools/emit/corpus_tarball.py", file=sys.stderr)
        return 1
    truth = truth_from_tarball(tarball)
    if not truth:
        print("[corpus_claim_guard] FAIL — tarball has no works", file=sys.stderr)
        return 1

    works: list[dict] = []
    shipped = args.root / "tools" / "shipped.toml"
    if shipped.is_file():
        import tomllib
        works = tomllib.loads(shipped.read_text(encoding="utf-8")).get("work", [])

    errors: list[str] = []
    checked = 0

    # 1. shipped.toml notes — per-work attribution is structural.
    if shipped.is_file():
        import tomllib
        doc = tomllib.loads(shipped.read_text(encoding="utf-8"))
        for w in doc.get("work", []):
            note = w.get("note") or ""
            for m in CLAIM_OF.finditer(note):
                checked += 1
                _check_claim(_num(m.group(1)), _num(m.group(2)), w["slug"],
                             truth, f"{shipped.name}:{w['slug']} note", errors)
            for m in CLAIM_SHORT.finditer(note):
                # Skip matches already covered by CLAIM_OF on the same span.
                if any(m.start() >= o.start() and m.end() <= o.end()
                       for o in CLAIM_OF.finditer(note)):
                    continue
                checked += 1
                _check_claim(_num(m.group(1)), None, w["slug"], truth,
                             f"{shipped.name}:{w['slug']} note", errors)

    # 2. emitted meta.json — slug from the path.
    pub = args.root / "public" / "data" / "corpus"
    if pub.is_dir():
        for meta in sorted(pub.glob("*/meta.json")):
            slug = meta.parent.name
            try:
                note = json.loads(meta.read_text(encoding="utf-8")).get("note") or ""
            except (OSError, json.JSONDecodeError) as e:
                errors.append(f"{meta}: unreadable ({e})")
                continue
            for m in CLAIM_OF.finditer(note):
                checked += 1
                _check_claim(_num(m.group(1)), _num(m.group(2)), slug, truth,
                             f"public/{slug}/meta.json", errors)
            for m in CLAIM_SHORT.finditer(note):
                if any(m.start() >= o.start() and m.end() <= o.end()
                       for o in CLAIM_OF.finditer(note)):
                    continue
                checked += 1
                _check_claim(_num(m.group(1)), None, slug, truth,
                             f"public/{slug}/meta.json", errors)

    # 3. content pages — attribution by work name on the same line; a claim
    #    line that names no work is itself an error.
    content = args.root / "content"
    if content.is_dir():
        for md in sorted(content.rglob("*.md")):
            for i, line in enumerate(
                    md.read_text(encoding="utf-8").splitlines(), 1):
                hits = list(CLAIM_OF.finditer(line)) or list(
                    CLAIM_SHORT.finditer(line))
                if not hits:
                    continue
                where = f"{md.relative_to(args.root)}:{i}"
                slug = _attributed_work(line, works)
                if slug is None:
                    errors.append(
                        f"{where}: numeric real-English claim names no work — "
                        "ambiguous claims are how 587 survived review")
                    continue
                for m in hits:
                    checked += 1
                    mo = CLAIM_OF.fullmatch(m.group(0)) or (
                        CLAIM_OF.search(m.group(0)))
                    if mo:
                        _check_claim(_num(mo.group(1)), _num(mo.group(2)),
                                     slug, truth, where, errors)
                    else:
                        _check_claim(_num(m.group(1)), None, slug, truth,
                                     where, errors)

    if errors:
        print(f"[corpus_claim_guard] FAIL — {len(errors)} bad claim(s), "
              f"{checked} checked:", file=sys.stderr)
        for e in errors[:20]:
            print(f"  - {e}", file=sys.stderr)
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more", file=sys.stderr)
        return 1

    print(f"[corpus_claim_guard] OK — {checked} numeric real-English claim(s) "
          f"checked against {len(truth)} work(s) in the tarball; all match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
