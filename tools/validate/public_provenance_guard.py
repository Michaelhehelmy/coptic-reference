#!/usr/bin/env python3
"""tools/validate/public_provenance_guard.py — every file in public/ has a source.

Session 9 C3, and Rule 5 (public/ is a build product; only the build writes to it).

Session 8 found out why this guard is needed the hard way. For the CSV reader page
I copied `LICENSES.csv.gz` into `public/` with `cp`. That file **names the six
CC BY-NC sources it excludes**, so invariant 5 was broken — and it was broken by
the one step in the whole project with no gate in front of it: a hand-placed file.

So the question this guard asks is not "is this file licensed?" It already is.
It is **"who put this here, and can they say so?"** A file nobody claims is an
orphan, and an orphan is a file that arrived without a review.

Provenance comes from exactly four places:

  data/dist/**   the built dataset, copied by tools/emit/corpus_public.py
  content/**     Hugo source, rendered by Hugo
  static/**      Hugo static assets
  BUILD-MANIFEST.json  written by tools/build.py, naming what IT emitted

The manifest is the important one. It is written by the build and read by the
guard, which is the one legitimate way a generated file can exist without a human
having named it in a `cp`.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]

#: Directories Hugo owns outright. Anything under these is accounted for by
#: content/** or static/** rather than by the manifest.
HUGO_OWNED = ("css/", "js/", "fonts/", "img/", "keys/", "pdf/", "nc/")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="every file in public/ has a source")
    ap.add_argument("--public", type=pathlib.Path, default=ROOT / "public")
    ap.add_argument("--dist", type=pathlib.Path, default=ROOT / "data" / "dist")
    ap.add_argument("--strict", action="store_true",
                    help="fail if BUILD-MANIFEST.json is absent. Off by default "
                         "so the guard can audit a hand-made tree, which is how "
                         "it was introduced.")
    args = ap.parse_args(argv)

    if not args.public.is_dir():
        print(f"[public_provenance] FAIL — {args.public} does not exist. There is "
              f"no published tree to account for.", file=sys.stderr)
        return 1

    public = args.public.resolve()
    files = sorted(p for p in public.rglob("*") if p.is_file())
    if not files:
        print(f"[public_provenance] FAIL — {args.public} is empty. An empty "
              f"published tree is not a pass; build it.", file=sys.stderr)
        return 1

    # ── what the build claims it emitted ─────────────────────────────────────
    manifest_path = public / "BUILD-MANIFEST.json"
    claimed: dict[str, str] = {}
    if manifest_path.is_file():
        try:
            m = json.loads(manifest_path.read_text(encoding="utf-8"))
            for e in m.get("emitted", []):
                claimed[e["path"]] = e.get("source", "?")
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"[public_provenance] FAIL — {manifest_path.name} is unreadable "
                  f"({e}). A manifest nobody can parse claims nothing.", file=sys.stderr)
            return 1

    # ── what legitimately has a source ──────────────────────────────────────
    dist_prefix = args.dist.resolve()
    manifest_rel = manifest_path.relative_to(public).as_posix()

    accounted: list[str] = []
    orphans: list[str] = []

    for p in files:
        rel = p.relative_to(public).as_posix()
        src = p.resolve()

        if rel == manifest_rel:
            accounted.append(f"{rel} <- the build's own manifest")
            continue
        if rel in claimed:
            accounted.append(f"{rel} <- manifest: {claimed[rel]}")
            continue
        # Hugo output: an .html/.xml beside a content page or a static asset.
        if any(rel.startswith(d) for d in HUGO_OWNED):
            accounted.append(f"{rel} <- static/ (Hugo)")
            continue
        if rel.endswith((".html", ".xml", ".webmanifest")):
            accounted.append(f"{rel} <- content/ rendered by Hugo")
            continue
        # NOTE: `.txt` is NOT here, and its absence was a hole in this guard
        # until the D7 negative control proved it. A hand-placed `rogue.txt`
        # passed as "Hugo output" because the extension was in this list. An
        # orphan rule that can be satisfied by choosing the right extension is
        # not an orphan rule -- so anything not positively accounted for by a
        # SOURCE is an orphan, whatever it is called.
        if rel == "robots.txt" or rel == "sitemap.xml":
            accounted.append(f"{rel} <- Hugo config")
            continue
        # The built dataset, byte-identical to its source.
        try:
            data = src.relative_to(dist_prefix)
        except ValueError:
            data = None
        if data is not None:
            origin = args.dist / data
            if origin.is_file():
                if origin.read_bytes() == p.read_bytes():
                    accounted.append(f"{rel} <- data/dist/{data} (byte-identical)")
                    continue
                orphans.append(f"{rel} — data/dist/{data} exists but the bytes "
                               f"DIFFER. Something rewrote a published artefact.")
                continue
            orphans.append(f"{rel} — claims data/dist/{data}, which does not exist")
            continue
        # Anything left has to have been placed by a human.
        orphans.append(f"{rel} — no source. Not in data/dist, not Hugo output, "
                       f"not in BUILD-MANIFEST.json. This is an orphan.")

    if orphans:
        print(f"[public_provenance] FAIL — {len(orphans)} orphan(s) in "
              f"{args.public}:", file=sys.stderr)
        for o in orphans:
            print(f"  - {o}", file=sys.stderr)
        print("\n  public/ is a BUILD PRODUCT (HANDOFF.md §8a Rule 5). A file gets "
              "there\n  by being emitted by tools/build.py and recorded in "
              "BUILD-MANIFEST.json, not\n  by hand. If this file is genuinely "
              "wanted, add it to static/ or\n  content/ so a generator owns it.",
              file=sys.stderr)
        return 1

    if args.strict and not claimed:
        print("[public_provenance] FAIL — --strict was given but "
              "BUILD-MANIFEST.json is absent, so nothing was emitted by a "
              "build.", file=sys.stderr)
        return 1

    print(f"[public_provenance] OK — {len(files)} file(s) in {args.public.name}/, "
          f"every one accounted for; {len(claimed)} claimed by "
          f"BUILD-MANIFEST.json, {len(files) - len(claimed)} by Hugo or data/dist")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
