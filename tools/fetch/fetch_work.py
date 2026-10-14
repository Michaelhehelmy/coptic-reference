#!/usr/bin/env python3
"""tools/fetch/fetch_work.py — fetch one corpus work from the pinned release.

Session 7 D1. `shipped.toml` declares nine works; the corpus of record
(CopticScriptorium/corpora at the pinned commit) does not contain all nine. This
tool fetches what exists, verifies it, and **reports what does not** rather than
substituting something close.

Three of the nine declared works are absent upstream:

    bohairic_liturgy_lauds     no `liturgy`/`prayer` directory exists at all
    bohairic_theotokia         ditto
    bohairic_common_prayers    ditto

The corpus of record has scripture, hagiography, monastic literature, canon law
and magical papyri -- and no liturgical corpus. Those three are the *highest*
community-value works in the shipped set (v4 puts liturgical first precisely
because that is what the church uses weekly), so their absence is the most
consequential gap in the site, not the least. `shipped.toml` still declares them:
declaring a work we intend to ship is not the same as claiming we have it, and
`corpus_tarball.py` names every absent work on every run.

WHY A PER-WORK SHA-256, given the release is pinned by commit
------------------------------------------------------------
A commit pin says "this tree". It does not say "these bytes": a re-run of the
tarball export, a line-ending normalisation, or a truncated download all pass it.
Each work therefore carries its own sha256 in `sources.lock`, computed over the
concatenated members in a fixed order, so the pin covers the bytes we actually
parse. This is the same discipline as the shard fingerprints, and it is why
`fetch_all.py --check` could verify 2 of 13 sources in Session 5 -- the others had
no pin to check.

NO PARSING. This tool moves bytes and verifies them. `tt.py` and `corpus_tarball.py`
do the parsing, separately, so a fetch failure is never confused with a parse
failure.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import pathlib
import sys
import tarfile
import tomllib

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import safeio  # noqa: E402

LOCK = ROOT / "tools" / "sources.lock"
SHIPPED = ROOT / "tools" / "shipped.toml"
CORPUS_DIR = ROOT / "sources" / "corpus"

#: slug -> (corpus directory in the release, filename glob). Deliberately a table
#: and not a derivation: the mapping is a fact about the upstream layout, checked
#: by the pins, and computing it would be guessing at filenames.
WORK_SOURCES: dict[str, list[tuple[str, str]]] = {
    "bohairic_mark":         [("bohairic.mark", "*.tt")],
    "bohairic_1corinthians": [("bohairic.1corinthians", "*.tt")],
    "lausiac_history":       [("bohairic-lausiac", "*.tt")],
    "life_of_isaac":         [("bohairic-life-isaac", "*.tt")],
    "martyrdom_of_victor":   [("martyrdom-victor", "*.tt")],
    # Ruth is in coptic-treebank, not a directory named for it. Verified
    # byte-for-byte against the release (Session 7).
    "sahidic_ruth":          [("coptic-treebank/coptic.treebank_TT", "Ruth_*.tt"),
                             ("sahidica.ruth", "*.tt")],
}

#: Declared in shipped.toml, absent from the corpus of record. Reported, never
#: substituted.
KNOWN_ABSENT_UPSTREAM = {
    "bohairic_liturgy_lauds": "no liturgical corpus exists in CopticScriptorium/corpora",
    "bohairic_theotokia": "no liturgical corpus exists in CopticScriptorium/corpora",
    "bohairic_common_prayers": "no liturgical corpus exists in CopticScriptorium/corpora",
}


def load_lock() -> dict:
    with LOCK.open("rb") as fh:
        return tomllib.load(fh)


def shipped_slugs() -> list[str]:
    with SHIPPED.open("rb") as fh:
        return [w["slug"] for w in tomllib.load(fh).get("work", [])
                if w.get("shipped", True)]


def work_digest(files: list[pathlib.Path]) -> str:
    """sha256 over the members in NAME order, each preceded by its length.

    Length-prefixing so that concatenating a different set of files cannot
    collide with concatenating the same characters a different way.
    """
    h = hashlib.sha256()
    for f in sorted(files, key=lambda p: p.name):
        b = f.read_bytes()
        h.update(f"{f.name}:{len(b)}\n".encode("utf-8"))
        h.update(b)
    return h.hexdigest()


def fetch_one(slug: str, tarball: pathlib.Path, *, force: bool) -> tuple[str, str, int]:
    """Returns (status, sha256_or_message, total_bytes)."""
    if slug in KNOWN_ABSENT_UPSTREAM:
        return "absent-upstream", KNOWN_ABSENT_UPSTREAM[slug], 0
    if slug not in WORK_SOURCES:
        return "unknown-work", f"{slug} has no entry in WORK_SOURCES", 0

    candidates = WORK_SOURCES[slug]
    dest = CORPUS_DIR / slug
    dest.mkdir(parents=True, exist_ok=True)

    # Extract matching members out of the release tarball. Candidates are tried in
    # order and the first that matches wins, so a work that moved upstream between
    # releases can list both locations without anyone editing code.
    want: dict[str, bytes] = {}
    tried: list[str] = []
    with tarfile.open(tarball, "r:gz") as tf:
        members = tf.getmembers()
        for subdir, pattern in candidates:
            tried.append(f"{subdir}/{pattern}")
            for m in members:
                if not m.isfile():
                    continue
                if f"/{subdir}/" not in f"/{m.name}":
                    continue
                if not fnmatch.fnmatch(pathlib.PurePosixPath(m.name).name, pattern):
                    continue
                fh = tf.extractfile(m)
                if fh is None:
                    continue
                want[pathlib.PurePosixPath(m.name).name] = fh.read()
            if want:
                break

    if not want:
        return "absent-upstream", f"tried {', '.join(tried)} — no match", 0

    total = 0
    for name, blob in sorted(want.items()):
        out = dest / name
        if out.is_file() and not force:
            total += out.stat().st_size
            continue
        safeio.write_verified(out, blob)      # Rule 3
        total += len(blob)

    files = sorted(dest.glob(pattern), key=lambda p: p.name)
    digest = work_digest(files)
    return "fetched", digest, total


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="fetch corpus works from the pinned release")
    ap.add_argument("slugs", nargs="*", help="work slugs; default = all shipped")
    ap.add_argument("--tarball", type=pathlib.Path, default=None,
                    help="path to the pinned release tarball "
                         "(required unless --check) "
                         f"({load_lock().get('corpora',{}).get('url','')})")
    ap.add_argument("--force", action="store_true", help="re-extract even if present")
    ap.add_argument("--write-pins", action="store_true",
                    help="write the computed sha256 into tools/sources.lock")
    ap.add_argument("--check", action="store_true",
                    help="verify the on-disk works against tools/sources.lock "
                         "pins WITHOUT network and WITHOUT writing anything")
    args = ap.parse_args(argv)

    if args.check:
        return _check(args)

    if args.tarball is None:
        ap.error("--tarball is required unless --check")

    lock = load_lock()
    corpora = lock.get("corpora", {})
    if not corpora.get("commit"):
        print("[fetch_work] FAIL — tools/sources.lock has no [corpora] commit pin. "
              "Nothing may be fetched from an unpinned release.", file=sys.stderr)
        return 1
    if not args.tarball.is_file():
        print(f"[fetch_work] FAIL — {args.tarball} not found. The release tarball is "
              f"{int(corpora.get('bytes', 0)) or 831764587:,} B; fetch it once and "
              f"reuse it: curl -L -o {args.tarball} {corpora.get('url')}",
              file=sys.stderr)
        return 1

    targets = args.slugs or shipped_slugs()
    print(f"[fetch_work] release {corpora.get('repo')} @ {corpora.get('commit')[:12]} "
          f"(v{corpora.get('version')})")
    print()

    pins: dict[str, dict] = {}
    fetched = absent = 0
    print(f"  {'work':30s} {'status':16s} {'bytes':>12s}  sha256")
    print(f"  {'-'*30} {'-'*16} {'-'*12}  {'-'*16}")
    for slug in targets:
        status, digest, nbytes = fetch_one(slug, args.tarball, force=args.force)
        if status == "fetched":
            fetched += 1
            pins[slug] = {"sha256": digest, "bytes": nbytes}
            print(f"  {slug:30s} {status:16s} {nbytes:12,d}  {digest[:16]}")
        else:
            absent += 1
            print(f"  {slug:30s} {status:16s} {'—':>12s}  {digest[:64]}")
    print()
    print(f"  fetched {fetched}, absent upstream {absent}")
    if absent:
        print("  The absent works are declared in shipped.toml and reported by "
              "corpus_tarball.py\n  on every run. Nothing was substituted for them.")
    if args.write_pins and pins:
        _write_pins(pins)
    return 0 if fetched else 1


def _check(args) -> int:
    """Verify on-disk works against the pins. No network, no writes.

    Session 10 D4. fetch_all --check does NOT do this: it verifies the corpora
    release tarball, while the pins that actually protect each WORK live per-work
    in tools/sources.lock. Nothing checked those, so a silently edited or
    truncated data/corpus/<slug>/*.tt would pass every existing guard until it
    changed a digest.

    This reads only:
      tools/sources.lock                the expected sha256 + byte count
      sources/corpus/<slug>/*.tt        what is actually on disk

    and compares. Exit 1 on the first disagreement. Writes nothing at all --
    including to sources.lock -- so it is safe in CI and safe to run by hand.
    """
    lock = load_lock()
    # Pins live at corpora.works."<slug>", not at the top level. My first version
    # looked at lock[slug] and reported all six shipped works as UNPINNED --
    # which reads as a serious provenance failure and was purely a wrong key.
    # The digests it computed matched the lock exactly.
    works = (lock.get("corpora") or {}).get("works") or {}
    bad: list[str] = []
    n_ok = 0
    print(f"[fetch_work --check] verifying on-disk works against "
          f"tools/sources.lock pins (no network, no writes)")
    print()
    for slug in (args.slugs or shipped_slugs()):
        pin = works.get(slug) or {}
        want = pin.get("sha256")
        d = CORPUS_DIR / slug
        files = sorted(d.glob("*.tt")) if d.is_dir() else []
        if not files:
            if slug in KNOWN_ABSENT_UPSTREAM or pin.get("ingested") is False:
                print(f"  {slug:30s} {'declared absent':16s} — upstream check stands")
                n_ok += 1
                continue
            bad.append(f"{slug}: no {CORPUS_DIR.name}/corpus/{slug}/ and no "
                       f"absent declaration")
            print(f"  {slug:30s} {'MISSING':16s} — no files on disk")
            continue
        got = work_digest(files)
        wantb = pin.get("bytes")
        gotb = sum(f.stat().st_size for f in files)
        if not want:
            bad.append(f"{slug}: files on disk but no sha256 pin in tools/sources.lock")
            print(f"  {slug:30s} {'UNPINNED':16s} — {got[:16]} on disk, no pin")
        elif got != want:
            bad.append(f"{slug}: digest mismatch\n      pin   {want}\n      disk  {got}")
            print(f"  {slug:30s} {'MISMATCH':16s} {got[:16]} != {want[:16]}")
        elif wantb is not None and int(wantb) != gotb:
            bad.append(f"{slug}: byte count {gotb} != pin {wantb} (digest agrees, "
                       f"so the pin's byte count is stale)")
            print(f"  {slug:30s} {'BYTE COUNT':16s} {gotb:,} != {int(wantb):,}")
        else:
            n_ok += 1
            print(f"  {slug:30s} {'OK':16s} {gotb:12,d}  {got[:16]}")
    print()
    if bad:
        print(f"[fetch_work --check] FAIL — {len(bad)} problem(s):", file=sys.stderr)
        for b in bad:
            print(f"  - {b}", file=sys.stderr)
        print("\n  The pinned bytes are what every corpus digest was computed "
              "from. Do not\n  re-pin to make this pass unless you know why the "
              "source changed.", file=sys.stderr)
        return 1
    print(f"[fetch_work --check] OK — {n_ok} work(s) match their pins")
    return 0


def _write_pins(pins: dict[str, dict]) -> int:
    """APPEND-ONLY. Session 8 C1.

    The previous implementation did string surgery: on a second run it cut the
    file from a marker onward and re-appended, which **deleted six tables** --
    `nc_only`, the four authored sources, `[crum]`, `[tla]`, `[ud_coptic]` and
    `[ud_bohairic]` -- and the file only looked plausible because TOML still
    parsed. S7-B2.

    The rules now:

      1. Never delete. New pins are appended to the end of the file.
      2. **Never change an existing pin.** If `corpora.works.<slug>` is already
         present, this tool refuses. Changing a pin is a human decision: it means
         either the source changed (a new commit, a new digest) or the pin was
         wrong, and both need a human reading the diff.
      3. Refuse if the file contains anything TOML cannot round-trip -- i.e. if
         parsing it changes the set of top-level tables we found, or if any
         pre-existing table's parsed value differs after the append.
      4. Verify before and after: every pre-existing table must be present and
         equal afterwards, or the whole write is rolled back by leaving the file
         untouched.

    It still cannot round-trip TOML comments, which is exactly why it appends
    text rather than re-emitting a parse. The file stays hand-maintained prose
    with a machine-appended tail, and that is a deliberate trade: a tool that
    rewrites the whole file would lose every `#` in it.
    """
    text = LOCK.read_text(encoding="utf-8")
    try:
        before = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        print(f"[fetch_work] REFUSING to touch sources.lock: it does not parse "
              f"({e}). Fix the file by hand.", file=sys.stderr)
        return 0

    existing = (before.get("corpora") or {}).get("works") or {}

    new_blocks: list[str] = []
    for slug in sorted(pins):
        want = pins[slug]["sha256"]
        if slug in existing:
            have = str(existing[slug].get("sha256", ""))
            if have == want:
                print(f"[fetch_work] pin for {slug} already present and identical "
                      f"— left alone")
                continue
            print("[fetch_work] REFUSING to change the existing pin for %s:" % slug,
                  file=sys.stderr)
            print("       recorded %s" % have, file=sys.stderr)
            print("       computed %s" % want, file=sys.stderr)
            print("  A pin change means the source changed or the pin was wrong.\n"
                  "  Both need a human to read the diff, so this tool will not do "
                  "it (Session 8 C1).", file=sys.stderr)
            return 0
        new_blocks.append(slug)

    if not new_blocks:
        print(f"[fetch_work] no new pins; sources.lock untouched "
              f"({len(existing)} work pin(s) already present)")
        return 0

    lines = ["", "# ── corpus work byte pins (append-only, tools/fetch/fetch_work.py) ──",
             "# Added, never modified, by this tool. A human edits an existing pin.",
             "# digest = sha256 over the work's .tt members, length-prefixed, name order.", ""]
    for slug in new_blocks:
        lines += [f'[corpora.works."{slug}"]',
                  f'sha256 = "{pins[slug]["sha256"]}"',
                  f'bytes  = {pins[slug]["bytes"]}', '']

    candidate = text.rstrip("\n") + "\n" + "\n".join(lines)

    # Rule 3 for a hand-maintained file: verify the append changed ONLY the
    # additions. Every pre-existing table must survive, unaltered.
    try:
        after = tomllib.loads(candidate)
    except tomllib.TOMLDecodeError as e:
        print(f"[fetch_work] REFUSING: the append would make sources.lock "
              f"unparseable ({e}). Not writing.", file=sys.stderr)
        return 0

    for key, val in before.items():
        if key == "corpora":
            b2 = dict(val)
            a2 = dict(after.get("corpora") or {})
            b2.pop("works", None)
            a2.pop("works", None)
            if b2 != a2:
                print("[fetch_work] REFUSING: [corpora] would change outside "
                      "`works`.", file=sys.stderr)
                return 0
            for slug, spec in (val.get("works") or {}).items():
                if (a2.get("works") or {}).get(slug) != spec:
                    print(f"[fetch_work] REFUSING: existing pin {slug} would "
                          f"change.", file=sys.stderr)
                    return 0
            continue
        if after.get(key) != val:
            print(f"[fetch_work] REFUSING: [{key}] would change.", file=sys.stderr)
            return 0

    # And every comment line must survive, because we cannot re-emit them.
    before_comments = [l for l in text.splitlines() if l.strip().startswith("#")]
    after_comments = [l for l in candidate.splitlines() if l.strip().startswith("#")]
    if not set(before_comments).issubset(set(after_comments)):
        print("[fetch_work] REFUSING: the append would drop comment lines.",
              file=sys.stderr)
        return 0

    safeio.write_text_verified(LOCK, candidate)
    print(f"[fetch_work] appended {len(new_blocks)} pin(s) to sources.lock: "
          f"{', '.join(new_blocks)}")
    print(f"[fetch_work]   sha256 now {hashlib.sha256(candidate.encode()).hexdigest()[:16]}… "
          f"({len(before_comments)} existing comment line(s) preserved)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
