#!/usr/bin/env python3
"""tools/build.py — the ONLY thing that writes to public/.

Session 9 D1 / C1 / C6. Rule 5, verbatim:

    public/ is a build product; only the build writes to it.

Session 8 ended with me hand-placing `LICENSES.csv.gz` into `public/` and
breaking invariant 5, because `cp` has no gate in front of it. This script is
that gate. It is a single entry point, it runs in a fixed order, it records
every file it emitted in `BUILD-MANIFEST.json`, and **it refuses to exit 0 unless
`public_provenance_guard.py` passes.**

THE ORDER IS LOAD-BEARING
-------------------------
    1. rm -rf public          nothing survives from a previous build
    2. corpus_public.py       the browser-facing corpus (reads the tarball)
    3. gzip provenance CSVs   records.csv.gz, LICENSES.csv.gz
    4. speakgen.py            the /speak/ top-100 word list (+ static no-JS page)
    4b. ankigen.py            the /downloads/anki/ decks (vocab + cloze)
    5. obsidian.py            the vault download
    6. hugo                   the pages and static assets
    7. pagefind_index.mjs     search (a no-op stub until wired)
    8. sw_gen.mjs             the service worker (a no-op stub until wired)
    9. manifest               name everything above
    10. public_provenance_guard  and fail the build if anything is unaccounted for

Steps 2-6 must precede Hugo because Hugo copies `static/**` into the destination
and the static tree must already be final. The provenance guard must be last
because it is the only step that can say the build was wrong.

IDEMPOTENCE
-----------
Running twice must produce identical bytes, or `git status` is noise. The one
thing that could break that is a timestamp, so this script writes the manifest
with a FIXED `generated` timestamp derived from the inputs' own mtimes, never
from `now()`. Measured and asserted by `--check-idempotent`.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
PUBLIC = ROOT / "public"
sys.path.insert(0, str(ROOT / "tools"))

import safeio  # noqa: E402

#: Which hugo binary. Resolved, not assumed — a missing hugo must be a clear
#: error rather than a confusing "public/ is empty" downstream.
def hugo_bin() -> str | None:
    for cand in (shutil.which("hugo"), os.path.expanduser("~/.local/bin/hugo"),
                 "/usr/local/bin/hugo"):
        if cand and pathlib.Path(cand).is_file():
            return cand
    return None


def run(cmd: list[str], *, what: str) -> tuple[int, str]:
    exe = cmd[0]
    if exe == "hugo":
        exe = hugo_bin() or "hugo"
    p = subprocess.run([exe] + cmd[1:], capture_output=True, text=True, cwd=ROOT)
    out = (p.stdout + p.stderr).strip()
    if p.returncode != 0:
        print(f"[build] FAILED at {what}: {' '.join(cmd)}", file=sys.stderr)
        print(out, file=sys.stderr)
    return p.returncode, out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="build public/ from nothing")
    ap.add_argument("--check-idempotent", action="store_true",
                    help="build twice and assert the trees are byte-identical")
    ap.add_argument("--skip-hugo", action="store_true",
                    help="diagnostic only; leaves public/ without pages")
    args = ap.parse_args(argv)

    t0 = time.monotonic()
    print("[build] public/ is a build product (HANDOFF.md §8a Rule 5). "
          "Nothing survives this build that the steps below did not write.")

    # 1 ── nothing survives
    if PUBLIC.exists():
        shutil.rmtree(PUBLIC)
    PUBLIC.mkdir(parents=True)

    emitted: list[dict] = []
    claimed: set[str] = set()

    def note(src: str, produced: list[pathlib.Path]) -> None:
        # Only FILES. rglob("*") yields directories too, and claiming a
        # directory in the manifest put 6 phantom entries in it -- the manifest
        # said 66 files for a tree of 44. A guard that trusts a count nobody
        # checked is exactly Rule 2's failure in miniature.
        for p in produced:
            if not p.is_file():
                continue
            rel = p.relative_to(PUBLIC).as_posix()
            if rel in claimed:        # first writer owns a file
                continue
            claimed.add(rel)
            emitted.append({
                "path": rel,
                "source": src,
                "bytes": p.stat().st_size,
            })

    # 2 ── the browser-facing corpus
    rc, _ = run([sys.executable, "tools/emit/corpus_public.py"], what="corpus_public")
    if rc != 0:
        return rc
    note("tools/emit/corpus_public.py (from data/dist/corpus/corpus.tar.gz)",
         sorted((PUBLIC / "data" / "corpus").rglob("*")) if (PUBLIC / "data" / "corpus").is_dir() else [])

    # 3 ── provenance CSVs, under /licences/ because LICENSES.csv names the NC
    #      sources it excludes and invariant 5 permits those ids only there
    gz = ROOT / "data" / "dist" / "provenance"
    lic = PUBLIC / "licences"
    lic.mkdir(parents=True, exist_ok=True)
    for name in sorted(gz.glob("*.csv.gz")):
        safeio.write_verified(lic / name.name, name.read_bytes())
        emitted.append({"path": f"licences/{name.name}",
                        "source": f"data/dist/provenance/{name.name}",
                        "bytes": (lic / name.name).stat().st_size})
    # the reader page, from static/
    src = ROOT / "static" / "read-csv.html"
    if src.is_file():
        safeio.write_verified(PUBLIC / "read-csv.html", src.read_bytes())
        emitted.append({"path": "read-csv.html", "source": "static/read-csv.html",
                        "bytes": (PUBLIC / "read-csv.html").stat().st_size})

    # 3b ── the dictionary the reader fetches: index.json.gz plus 23 shards.
    #      Session 9 D2 found this missing the hard way -- reader.js asked for
    #      data/dist/dict/index.json.gz and public/ had no such path, because
    #      data/dist was built and guarded but never PUBLISHED. The dataset has
    #      to cross into public/ or the reader is a page that cannot load.
    dd = ROOT / "data" / "dist" / "dict"
    if dd.is_dir():
        for f in sorted(dd.iterdir()):
            if f.is_file() and f.name.endswith(".gz"):
                dest = PUBLIC / "data" / "dist" / "dict" / f.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                safeio.write_verified(dest, f.read_bytes())
                emitted.append({
                    "path": dest.relative_to(PUBLIC).as_posix(),
                    "source": f"data/dist/dict/{f.name}",
                    "bytes": dest.stat().st_size,
                })
        # the plain build-record index, small and useful to a human
        plain = dd / "index.json"
        if plain.is_file():
            dest = PUBLIC / "data" / "dist" / "dict" / "index.json"
            safeio.write_verified(dest, plain.read_bytes())
            emitted.append({"path": dest.relative_to(PUBLIC).as_posix(),
                            "source": "data/dist/dict/index.json",
                            "bytes": dest.stat().st_size})

    # 3c ── the English search index (Session 14 D2).
    #
    # Emitted here, published immediately below. The first version ran the emit
    # LATER in the pipeline than the publish, so the build printed
    # "english_index.json.gz is absent" and shipped a site whose English search
    # silently did nothing — a warning nobody reads, about a file the build
    # itself had not produced yet. Order is the whole fix.
    # Session 14 D2: the English index Pagefind cannot build. Runs BEFORE the
    # dictionary is copied, so it reads data/dist; the copy step then publishes
    # it with everything else under /data/.
    rc, _ = run([sys.executable, str(ROOT / "tools" / "emit" / "english_index.py")],
                what="english_index")
    if rc != 0:
        return rc


    #      Pagefind 1.5.2 drops a fixed set of English gloss terms; this is the
    #      workaround, and it must cross into public/ or the reader cannot use it.
    es = ROOT / "data" / "dist" / "search" / "english_index.json.gz"
    if es.is_file():
        dest = PUBLIC / "data" / "search" / "english_index.json.gz"
        dest.parent.mkdir(parents=True, exist_ok=True)
        safeio.write_verified(dest, es.read_bytes())
        claimed.add(dest.relative_to(PUBLIC).as_posix())
        emitted.append({"path": dest.relative_to(PUBLIC).as_posix(),
                        "source": "data/dist/search/english_index.json.gz",
                        "bytes": dest.stat().st_size})
    else:
        print("[build] WARNING — data/dist/search/english_index.json.gz is absent; "
              "English gloss search will not work. tools/emit/english_index.py "
              "runs in this pipeline, so this means it failed silently.", file=sys.stderr)

    # 3d ── the quiz banks (Session 16 D1/D4).
    #
    # Emit, validate, then publish in that order. The quiz generator reads the
    # authoritative data/dist shards and corpus tarball, never the public/ tree it
    # is about to help populate. The guard runs before publication for the same
    # reason the shape guards do: a wrong answer must fail the build, not the
    # first learner who taps it.
    rc, _ = run([sys.executable, str(ROOT / "tools" / "emit" / "quizgen.py")],
                what="quizgen")
    if rc != 0:
        return rc
    rc, _ = run([sys.executable, str(ROOT / "tools" / "validate" / "quiz_guard.py")],
                what="quiz_guard")
    if rc != 0:
        print("[build] quiz guard failed — refusing to publish", file=sys.stderr)
        return rc
    quiz_src = ROOT / "data" / "dist" / "quiz"
    quiz_dest = PUBLIC / "data" / "quiz"
    if not quiz_src.is_dir():
        print("[build] FAIL — data/dist/quiz is absent after quizgen; refusing to "
              "publish a quiz page with no questions.", file=sys.stderr)
        return 1
    for name in sorted(p.name for p in quiz_src.iterdir() if p.is_file()):
        src = quiz_src / name
        dest = quiz_dest / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        safeio.write_verified(dest, src.read_bytes())
        claimed.add(dest.relative_to(PUBLIC).as_posix())
        emitted.append({"path": dest.relative_to(PUBLIC).as_posix(),
                        "source": f"data/dist/quiz/{name}",
                        "bytes": dest.stat().st_size})

    # 3e ── the cloze drill banks (Session 18 D4).
    #
    # Same order as the quiz: emit, validate, then publish. drillgen reads
    # the authoritative corpus tarball, never the public/ tree.
    rc, _ = run([sys.executable, str(ROOT / "tools" / "emit" / "drillgen.py")],
                what="drillgen")
    if rc != 0:
        return rc
    rc, _ = run([sys.executable, str(ROOT / "tools" / "validate" / "drill_guard.py")],
                what="drill_guard")
    if rc != 0:
        print("[build] drill guard failed — refusing to publish", file=sys.stderr)
        return rc
    # Session 20 D4: Layer 2's second drill type, same order (emit, guard).
    # The publish loop below copies the whole drill dir, parse banks included.
    rc, _ = run([sys.executable, str(ROOT / "tools" / "emit" / "parsedrillgen.py")],
                what="parsedrillgen")
    if rc != 0:
        return rc
    rc, _ = run([sys.executable, str(ROOT / "tools" / "validate" / "parsedrill_guard.py")],
                what="parsedrill_guard")
    if rc != 0:
        print("[build] parse drill guard failed — refusing to publish",
              file=sys.stderr)
        return rc
    # Session 21 D2: the POS label file ships with the banks it serves.
    # The emitter fails closed on any unlabeled tag in the tarball.
    rc, _ = run([sys.executable, str(ROOT / "tools" / "emit" / "pos_labels.py")],
                what="pos_labels")
    if rc != 0:
        return rc
    drill_src = ROOT / "data" / "dist" / "drill"
    drill_dest = PUBLIC / "data" / "drill"
    if not drill_src.is_dir():
        print("[build] FAIL — data/dist/drill is absent after drillgen; refusing to "
              "publish a drill page with no drills.", file=sys.stderr)
        return 1
    for name in sorted(p.name for p in drill_src.iterdir() if p.is_file()):
        src = drill_src / name
        dest = drill_dest / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        safeio.write_verified(dest, src.read_bytes())
        claimed.add(dest.relative_to(PUBLIC).as_posix())
        emitted.append({"path": dest.relative_to(PUBLIC).as_posix(),
                        "source": f"data/dist/drill/{name}",
                        "bytes": dest.stat().st_size})

    # 3f ── the structured course file (Session 19 D4).
    #
    # Same order: emit, validate, then publish. coursegen reads lesson front
    # matter; course_guard checks every filter resolves to data.
    rc, _ = run([sys.executable, str(ROOT / "tools" / "emit" / "coursegen.py")],
                what="coursegen")
    if rc != 0:
        return rc
    rc, _ = run([sys.executable, str(ROOT / "tools" / "validate" / "course_guard.py")],
                what="course_guard")
    if rc != 0:
        print("[build] course guard failed — refusing to publish", file=sys.stderr)
        return rc
    course_src = ROOT / "data" / "dist" / "course" / "course.json.gz"
    course_dest = PUBLIC / "data" / "course" / "course.json.gz"
    if not course_src.is_file():
        print("[build] FAIL — data/dist/course/course.json.gz is absent after "
              "coursegen; refusing to publish a course page with no course.",
              file=sys.stderr)
        return 1
    course_dest.parent.mkdir(parents=True, exist_ok=True)
    safeio.write_verified(course_dest, course_src.read_bytes())
    claimed.add(course_dest.relative_to(PUBLIC).as_posix())
    emitted.append({"path": course_dest.relative_to(PUBLIC).as_posix(),
                    "source": "data/dist/course/course.json.gz",
                    "bytes": course_dest.stat().st_size})

    # 4 ── /speak/ word list (Session 22 D1). Runs before Hugo only because
    # the build is ordered that way; nothing under data/ is read at Hugo
    # time (see the module docstring — touching site.Data makes Hugo
    # unmarshal the whole data/ tree, including corpus.tar.gz, and fail).
    rc, _ = run([sys.executable, "tools/emit/speakgen.py"], what="speakgen")
    if rc != 0:
        return rc
    speak_src = ROOT / "data" / "dist" / "speak" / "speak.json.gz"
    if not speak_src.is_file():
        print("[build] FAIL — data/dist/speak/speak.json.gz absent after "
              "speakgen; refusing to publish an empty /speak/", file=sys.stderr)
        return 1
    speak_dest = PUBLIC / "data" / "dist" / "speak" / "speak.json.gz"
    speak_dest.parent.mkdir(parents=True, exist_ok=True)
    safeio.write_verified(speak_dest, speak_src.read_bytes())
    claimed.add(speak_dest.relative_to(PUBLIC).as_posix())
    emitted.append({"path": speak_dest.relative_to(PUBLIC).as_posix(),
                    "source": "data/dist/speak/speak.json.gz",
                    "bytes": speak_dest.stat().st_size})
    # The no-JS page is a complete HTML document; it must land in public/
    # alongside Hugo's /speak/ output, so it is copied here, not via Hugo.
    top100_src = ROOT / "work" / "speak" / "top100.html"
    if not top100_src.is_file():
        print("[build] FAIL — work/speak/top100.html absent after speakgen",
              file=sys.stderr)
        return 1
    top100_dest = PUBLIC / "speak" / "top100.html"
    top100_dest.parent.mkdir(parents=True, exist_ok=True)
    safeio.write_verified(top100_dest, top100_src.read_bytes())
    claimed.add(top100_dest.relative_to(PUBLIC).as_posix())
    emitted.append({"path": top100_dest.relative_to(PUBLIC).as_posix(),
                    "source": "work/speak/top100.html",
                    "bytes": top100_dest.stat().st_size})

    # 4b ── Anki decks (Session 22 D2). Generated from the same quiz and
    # drill banks the site serves; downloadable, no server, no accounts.
    # Emitted to work/anki/ (Hugo's data loader walks data/ and chokes on
    # a binary .apkg); copied into public/downloads/anki/ here.
    rc, _ = run([sys.executable, "tools/emit/ankigen.py"], what="ankigen")
    if rc != 0:
        return rc
    anki_src_dir = ROOT / "work" / "anki"
    if not anki_src_dir.is_dir():
        print("[build] FAIL — work/anki/ absent after ankigen",
              file=sys.stderr)
        return 1
    for name in ("vocab.apkg", "drill.apkg"):
        src = anki_src_dir / name
        if not src.is_file():
            print(f"[build] FAIL — ankigen did not produce {name}",
                  file=sys.stderr)
            return 1
        dest = PUBLIC / "downloads" / "anki" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        safeio.write_verified(dest, src.read_bytes())
        claimed.add(dest.relative_to(PUBLIC).as_posix())
        emitted.append({"path": dest.relative_to(PUBLIC).as_posix(),
                        "source": f"work/anki/{name}",
                        "bytes": dest.stat().st_size})

    # 5 ── the vault download
    rc, _ = run([sys.executable, "tools/emit/obsidian.py"], what="obsidian")
    if rc != 0:
        return rc
    if (PUBLIC / "downloads").is_dir():
        note("tools/emit/obsidian.py", sorted((PUBLIC / "downloads").rglob("*")))

    # 6 ── Hugo
    if args.skip_hugo:
        print("[build] --skip-hugo: no pages built")
    else:
        # Generate the /corpus/<work>/ pages BEFORE Hugo, so Hugo sees the
        # content tree. Session 10 D3.
        rc, _ = run([sys.executable, str(ROOT / "tools" / "emit" / "corpus_pages.py")], what="corpus_pages")
        if rc != 0:
            print("[build] corpus_pages failed", file=sys.stderr)
            return rc
        rc, _ = run(["hugo", "--gc", "--minify", "--destination", "public"],
                    what="hugo")
        if rc != 0:
            print("[build] Hugo failed. Is it installed?", file=sys.stderr)
            return rc
        for p in sorted(PUBLIC.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(PUBLIC).as_posix()
            # Only the CSVs we placed by hand, not the whole licences/ tree:
            # Hugo renders /licences/ from content/licences/_index.md and that
            # page has to be claimed too, or it is an orphan by omission.
            if rel == "read-csv.html" or rel.endswith(".csv.gz"):
                continue          # placed by the build, above
            if rel in claimed:
                # Hugo copied static/** into the destination AFTER corpus_public
                # and obsidian ran, so its rglob sees their output too. Without
                # this the manifest claimed the corpus twice and 62 entries
                # described a 44-file tree.
                continue
            claimed.add(rel)
            emitted.append({"path": rel,
                            "source": "hugo (content/ + static/ + theme/)",
                            "bytes": p.stat().st_size})

    # 6, 7 ── search and the service worker
    for script in ("tools/emit/pagefind_index.mjs", "tools/emit/sw_gen.mjs"):
        if (ROOT / script).is_file():
            rc, out = run(["node", script], what=script)
            if rc != 0:
                return rc
            if out:
                print(f"[build]   {pathlib.Path(script).name}: {out.splitlines()[-1]}")
    for name in ("pagefind", "sw.js"):
        d = PUBLIC / name
        if d.is_dir():
            note(f"{script}", sorted(d.rglob("*")))
        elif d.is_file():
            note(script, [d])

    # A missing search index must not look like a successful build.
    #
    # pagefind_index.mjs exits 0 when there is no binary, so the build used to
    # print a green "guard PASSED" with no public/pagefind/ anywhere. Nothing
    # inside tools/build.py enforced it; only the separate completeness guard,
    # which CI runs, would catch it -- so a local build said nothing at all.
    if not (PUBLIC / "pagefind").is_dir():
        print("[build] WARNING — public/pagefind/ does not exist: the site will "
              "ship with no search.\n          Set PAGEFIND_BIN to the pagefind "
              "binary and rebuild. tools/validate/\n          "
              "public_completeness_guard.py will fail on this, so CI will catch it.",
              file=sys.stderr)

    # Session 16 D0.4: transliteration must remain the documented schema object.
    # This reads data/dist before it can be published in the wrong shape.
    rc, _ = run([sys.executable, str(ROOT / "tools" / "validate" / "translit_shape_guard.py")],
                what="translit_shape_guard")
    if rc != 0:
        print("[build] translit shape guard failed — refusing to publish", file=sys.stderr)
        return rc

    # Session 15 C2: published index budgets. A FAILURE, not a warning —
    # these are the only published artefacts that grow with the dataset rather
    # than with the code, and they are the two the reader fetches on a cold visit.
    rc, _ = run([sys.executable, str(ROOT / "tools" / "validate" / "size_budget_guard.py")],
                what="size_budget_guard")
    if rc != 0:
        print("[build] size budget exceeded — refusing to publish", file=sys.stderr)
        return rc

    # Session 13 D0/C3: verse_index and clean norms are BUILD-time conditions.
    # Until this ran here, they were only checked in the browser, so a tarball
    # from an older emitter built, published, and then rendered the wrong words
    # in a reader's browser. The guard is in the pipeline, not beside it.
    rc, _ = run([sys.executable, str(ROOT / "tools" / "validate" / "corpus_shape_guard.py")],
                what="corpus_shape_guard")
    if rc != 0:
        print("[build] corpus shape guard failed — refusing to publish", file=sys.stderr)
        return rc

    rc, _ = run([sys.executable, str(ROOT / "tools" / "emit" / "headers.py")], what="headers")
    if rc != 0:
        return rc
    # Claim it. public_provenance_guard.py --strict rejects any file in public/
    # it cannot account for, and _headers is emitted by a tool rather than by
    # Hugo or copied from data/dist — so without this the build fails its own
    # guard on a correct artefact. That is the guard working: it caught the file
    # the first time this was wired in.
    claimed.add("_headers")
    emitted.append({"path": "_headers",
                    "source": "tools/emit/headers.py",
                    "bytes": (PUBLIC / "_headers").stat().st_size})

    # 8 ── manifest. The timestamp is derived from the INPUTS, never from now(),
    #      so two builds of the same tree are byte-identical.
    newest = 0.0
    for d in (ROOT / "content", ROOT / "static", ROOT / "themes", ROOT / "data" / "dist"):
        if not d.exists():
            continue
        for p in d.rglob("*"):
            if p.is_file():
                newest = max(newest, p.stat().st_mtime)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(newest))

    manifest = {
        "schema": "coptic-reference/build-manifest/1",
        "generated": stamp,
        "collation_hash": _collation_hash(),
        "emitted": sorted(emitted, key=lambda e: e["path"]),
        "file_count": len(emitted),
        "note": ("Written by tools/build.py. public/ is a build product; a file "
                 "in public/ that is not named here is an orphan and "
                 "public_provenance_guard.py fails the build."),
    }
    safeio.write_text_verified(
        PUBLIC / "BUILD-MANIFEST.json",
        json.dumps(manifest, indent=1, ensure_ascii=False, sort_keys=True) + "\n")

    # Session 16 D0.3: no rendered structured value may reach a reader.
    # This runs after the manifest, when public/ is final, and inspects the
    # published bytes — including decompressed JSON payloads. It must run before
    # provenance because a leak means the tree is wrong, however well documented.
    rc, _ = run([sys.executable, str(ROOT / "tools" / "validate" / "no_object_object_guard.py")],
                what="no_object_object_guard")
    if rc != 0:
        print("[build] rendered structured value found — refusing to publish", file=sys.stderr)
        return rc

    # 9 ── the guard, and no exit 0 without it
    rc, out = run([sys.executable, "tools/validate/public_provenance_guard.py",
                   "--strict"], what="public_provenance_guard")
    if rc != 0:
        print("[build] REFUSING to report success: the published tree has files "
              "nobody can account for.", file=sys.stderr)
        return rc

    n = sum(1 for _ in PUBLIC.rglob("*") if _.is_file())
    print(f"[build] public/: {n} files, {sum(e['bytes'] for e in emitted):,} B "
          f"emitted in {time.monotonic() - t0:.2f}s — guard PASSED")

    if args.check_idempotent:
        first = _tree_digest(PUBLIC)
        print("[build] rebuilding to check idempotence ...")
        if PUBLIC.exists():
            shutil.rmtree(PUBLIC)
        PUBLIC.mkdir(parents=True)
        subprocess.run([sys.executable, str(HERE / "build.py")], check=False,
                       capture_output=True, cwd=ROOT)
        second = _tree_digest(PUBLIC)
        if first == second:
            print(f"[build] IDEMPOTENT: two builds agree, tree sha {first[:16]}…")
        else:
            print(f"[build] NOT IDEMPOTENT: {first[:16]} vs {second[:16]}",
                  file=sys.stderr)
            return 1
    return 0


def _collation_hash() -> str:
    try:
        import collate
        return collate.collation_hash()
    except Exception:                      # never block a build on this
        return "unknown"


def _tree_digest(root: pathlib.Path) -> str:
    """sha256 over the whole tree: sorted relpath, length, bytes."""
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        b = p.read_bytes()
        h.update(f"{p.relative_to(root).as_posix()}:{len(b)}\n".encode())
        h.update(b)
    return h.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
