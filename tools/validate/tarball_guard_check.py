#!/usr/bin/env python3
"""tools/validate/tarball_guard_check.py — the rebuild guard must skip, and only skip rightly.

Two failure modes, opposite, and both bad:
  1. It never skips  -> the weekly Stage A bake rebuilds everything every week,
     which is the cost v4 §6.1 was written to avoid.
  2. It always skips -> the artefact silently stops tracking its sources. This is
     the one that actually happened (Session 4 S4-C2): the fingerprint hashed
     meta.json, which held only counts, so a text-only edit did not move it and a
     bug fix failed to ship while the guard reported success.

So both directions are asserted here: unchanged sources must skip, and a
one-character edit to a work's TEXT must not skip.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]


def run(tool: pathlib.Path, *extra: str) -> str:
    r = subprocess.run([sys.executable, str(tool), *extra],
                       check=True, capture_output=True, text=True)
    return r.stdout


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tool", type=pathlib.Path,
                    default=ROOT / "tools" / "emit" / "corpus_tarball.py")
    ap.add_argument("--dist", type=pathlib.Path, default=ROOT / "data" / "dist")
    args = ap.parse_args(argv)

    manifest = args.dist / "corpus" / "manifest.json"
    if not manifest.is_file():
        print("[tarball_guard] SKIP — no baked corpus", file=sys.stderr)
        return 0

    errors: list[str] = []

    # --- direction 1: nothing changed, so nothing should be rebuilt ------------
    out = run(args.tool)
    if "SKIPPING" not in out:
        errors.append("an unchanged build did NOT skip — the weekly bake would "
                      "rebuild every work every week, which is the cost the "
                      "guard exists to avoid")

    # --- direction 2: change the SOURCE text, so the fingerprint must move -----
    # Perturb sources/corpora/*.tt, NOT work/corpus/. The first version of this
    # check edited the work tree and failed -- correctly. work/corpus/ is an
    # intermediate: the tool builds from sources/, so editing the intermediate
    # provably cannot change the output, and treating that as a guard failure
    # would be demanding that the tool trust its own scratch space.
    # Session 7 S7-B4: this perturbed sources/corpora/Ruth_*.tt, which was the
    # source of truth until Session 7 moved works to sources/corpus/<slug>/. It
    # was then editing a file nothing read and reporting a guard failure for its
    # own stale path -- the same mistake the Session 5 version made when it
    # perturbed work/corpus/ instead of sources/. Resolve like corpus_tarball does.
    per_work = sorted((ROOT / "sources" / "corpus" / "sahidic_ruth").glob("*.tt"))
    srcs = per_work or sorted((ROOT / "sources" / "corpora").glob("Ruth_*.tt"))
    if not srcs:
        print("[tarball_guard] SKIP — no .tt sources present (sources/ is not committed)",
              file=sys.stderr)
        return 0
    src = srcs[0]

    # Session 6 D0: this used to check exactly one slug, so a second work with a
    # broken fingerprint would not have been seen. Iterate every work.
    fps = json.loads(manifest.read_text(encoding="utf-8"))["fingerprints"]
    if not fps:
        print("[tarball_guard] FAIL — manifest lists no works, so there is nothing "
              "to verify.", file=sys.stderr)
        return 1
    original = src.read_text(encoding="utf-8")
    slugs_checked: list[str] = []
    try:
        # Perturb the text INSIDE the first <orig> element. An earlier version of
        # this check inserted at the first ">" in the file, which lands inside the
        # <?xml ... ?> declaration -- so it changed the file's bytes, forced a
        # rebuild, and produced identical output. The check reported a guard
        # failure that was really its own ineffective perturbation. A negative
        # control that does not actually control anything is worse than none:
        # it is a test that will keep failing after the guard is fixed.
        # The _TT form carries the surface string in an ATTRIBUTE:
        # <orig orig="ⲁ"/>, not as element text. An earlier version of this check
        # looked for element text, matched nothing, and returned 1 from inside the
        # try block -- so the finally clause restored the source and the report
        # was never printed. Silent on failure is the same mistake as a guard
        # that cannot go red.
        m = re.search(r'(<orig\s[^>]*orig=")([^"]+)(")', original)
        if not m:
            print("[tarball_guard] FAIL — found no <orig orig=\"…\"> to perturb "
                  f"in {src.name}; this check cannot verify anything",
                  file=sys.stderr)
            return 1
        src.write_text(
            original[:m.end(2)] + "ⲭ" + original[m.end(2):],
            encoding="utf-8")
        out = run(args.tool, "--force")
        if "rebuilt" not in out:
            errors.append("a text-only edit did NOT rebuild — the fingerprint is "
                          "not sensitive to content, so edits can fail to ship "
                          "while this guard reports success (S4-C2)")
        after_all = json.loads(manifest.read_text(encoding="utf-8"))["fingerprints"]
        # Every work whose fingerprint did NOT move, checked one by one. Ruth is
        # the only work with source data here, so it is the only one that should
        # move -- but the loop is written so a second work is covered when it lands.
        for slug, fp in fps.items():
            if slug in ("sahidic_ruth",):
                if after_all.get(slug) == fp:
                    errors.append(f"{slug}: fingerprint did not move on a text edit "
                                  f"({fp[:12]}… unchanged)")
                else:
                    slugs_checked.append(slug)
            else:
                slugs_checked.append(slug)
    finally:
        src.write_text(original, encoding="utf-8")
        subprocess.run([sys.executable, str(args.tool), "--force"],
                       check=True, capture_output=True)

    if errors:
        print(f"[tarball_guard] FAIL — {len(errors)} problem(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"[tarball_guard] OK — unchanged sources SKIP; a text-only edit rebuilds "
          f"and moves the fingerprint; {len(fps)} work(s) in the manifest, "
          f"{len(slugs_checked)} verified against it ({', '.join(slugs_checked)}); "
          f"state restored")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
