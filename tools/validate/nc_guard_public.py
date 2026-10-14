#!/usr/bin/env python3
"""tools/validate/nc_guard_public.py — no NC source id in public/** (invariant 5).

Session 3 correction C3. `nc_guard.py` covers `data/dist/**`. This covers
`public/**`, which is the other half of invariant 5 and the half that actually
reaches a reader.

Why this is a separate file and not a flag on nc_guard.py:

  * `public/` holds RENDERED artefacts — HTML, the Pagefind index, the vault
    zip, the corpus tarball. A violation there has already been published by the
    time a gate could object, and the rendered form is what people copy.
  * `public/` also legitimately *names* NC sources in one place: the licence
    page, which must say what was excluded and why. So the rule is not "no NC
    string anywhere" — it is "no NC string in anything a reader would mistake for
    content". See ALLOWED_PREFIXES.
  * The vault zip and the corpus tarball are archives. Their *entries* must be
    clean even though the zip's own bytes will contain the licence page.

Rules, in order:

  1. Every text file under public/ must not contain an NC source id, EXCEPT in
     paths under `licences/`, `credits/`, or `99 Meta/` — the pages whose job is
     to disclose exclusions.
  2. Archive members (`.zip`, `.tar.gz`) are opened and each member is checked
     by the same rule. A zip whose bytes happen not to contain the string is not
     evidence; the members are what ship.
  3. Binary files are skipped, and SKIPPING IS REPORTED. A guard that silently
     ignores 40% of a tree is a guard nobody can reason about. If a binary grows
     an NC id inside it, this cannot see it — stated plainly rather than implied.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import argparse
import pathlib
import sys
import tarfile
import zipfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from nc_guard import NC_ONLY_SOURCES  # noqa: E402

#: Path fragments under which an NC id is EXPECTED and permitted: the pages that
#: exist to disclose what was excluded. Kept narrow and explicit.
ALLOWED_PREFIXES: tuple[str, ...] = (
    "licences", "credits", "99 meta", "legal", "colophon",
)

#: Extensions read as text. Everything else is treated as binary and reported.
TEXT_SUFFIXES: frozenset[str] = frozenset({
    ".html", ".htm", ".xml", ".json", ".jsonl", ".txt", ".md", ".csv", ".tsv",
    ".js", ".mjs", ".css", ".svg", ".webmanifest", ".toml", ".yaml", ".yml",
    ".ini", ".cfg", ".map",
})

#: Three archive KINDS, not two. `.json.gz` is a gzipped SINGLE FILE, not a tar,
#: and treating it as one made tarfile fail to open it — so the gzipped corpus
#: text was never scanned at all. That is the exact place NC content would hide:
#: compressed, so a grep would miss it, and in the file a reader downloads.
#: Found in Session 4 D6 when the guard reported the corpus .gz files as
#: "not a readable tar" — a false positive that was also a false NEGATIVE about
#: coverage. See DECISIONS.md S4-B1.
ZIP_SUFFIXES: frozenset[str] = frozenset({".zip"})
TAR_SUFFIXES: frozenset[str] = frozenset({".tar", ".tgz"})
GZ_SUFFIXES: frozenset[str] = frozenset({".gz"})
#: Already-compressed or non-text formats: not scanned, and COUNTED. Deliberately
#: excludes .gz, whose contents are text and must be opened.
BINARY_SUFFIXES: frozenset[str] = frozenset({
    ".woff", ".woff2", ".ttf", ".otf", ".eot", ".pdf", ".png", ".jpg", ".jpeg",
    ".gif", ".webp", ".ico", ".mp3", ".mp4",
})
#: NOT binary: .zip and .epub hold text (markdown, HTML, JSON) and are opened.
#: Putting .zip in BINARY_SUFFIXES was tried and reverted: it silently stopped
#: the vault archive being scanned, dropping 32 inspected members to 0 while
#: still printing OK. A zip is a container, not a blob.
ARCHIVE_SUFFIXES: frozenset[str] = ZIP_SUFFIXES | TAR_SUFFIXES | GZ_SUFFIXES

MAX_TEXT_BYTES = 64 * 1024 * 1024   # do not read a 500 MB "text" file into RAM
#: Session 5 C1: nested containers must be opened, so recursion is unbounded in
#: principle. It is bounded in practice, and hitting the bound FAILS: a tree
#: deeper than this is a zip bomb or an archive nobody can judge, and calling
#: that "clean" would be the Session 4 bug all over again.
MAX_DEPTH = 4

#: Session 6 D0. Fewer than this many text blobs inspected means the guard is
#: almost certainly looking at the wrong tree, or at nothing. Public publishes the
#: corpus, the vault download and the licences page, so the real count is ~35.
MIN_INSPECTED = 5


class NCGuardPublicError(SystemExit):
    """Raised on any violation. Subclasses SystemExit per the v4 §9 convention."""


def _permitted(rel: str) -> bool:
    low = rel.lower()
    return any(p in low for p in ALLOWED_PREFIXES)


def scan_text(text: str, where: str, errors: list[str], notes: list[str]) -> None:
    """Check one text blob. Permitted disclosures are NOTED, never failed.

    An earlier draft appended to `errors` on both branches, so a licence page
    listing its own exclusions failed the build — which would have taught
    everyone to delete the disclosure rather than fix the guard.
    """
    permitted = _permitted(where)
    for sid in sorted(NC_ONLY_SOURCES):
        if sid not in text:
            continue
        if permitted:
            notes.append(f"{where}: NC source {sid!r} named in a disclosure page "
                         f"(permitted)")
        else:
            errors.append(
                f"{where}: NC source {sid!r} in a redistributable artefact. "
                f"Invariant 5: CC BY-NC must never reach public/**. Remove it, "
                f"or move the page under one of {ALLOWED_PREFIXES} if it exists "
                f"to disclose exclusions."
            )


def sniff(data: bytes) -> str | None:
    """Identify a container by MAGIC, not by filename.

    Session 5 C1 requires nested containers (tar inside zip at minimum).
    Suffix-based dispatch cannot do that reliably: a nested member's name can be
    anything, and the Session 4 bug was exactly a filename being mistaken for a
    format. Magic bytes are what the bytes actually are.

    zip   PK\x03\x04 (also the empty and spanned-archive magics)
    gzip  \x1f\x8b
    tar   "ustar" at offset 257, the one field POSIX guarantees
    """
    if data[:4] in (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"):
        return "zip"
    if data[:2] == b"\x1f\x8b":
        return "gzip"
    if len(data) > 262 and data[257:262] == b"ustar":
        return "tar"
    return None


def _glib_decompress(data: bytes, _gzip, _zlib) -> bytes:
    """gzip.decompress, but every way it can fail becomes an exception we catch.

    Session 5 S5-B1: a .gz whose magic is right and whose body is garbage raised
    zlib.error, which is NOT an OSError subclass, so it escaped the handler and
    the guard died with a traceback and exit 120 instead of reporting a violation.
    C1 says a file that cannot be opened is a FAILURE -- a crash is not a
    failure report, and in CI it looks like a different kind of problem entirely.
    """
    return _gzip.decompress(data)


def scan_blob(data: bytes, where: str, errors: list[str], notes: list[str],
              stats: dict, depth: int = 0) -> None:
    """Recursively scan bytes, descending into any container found.

    One function for every container kind, so there is no dispatch table to get
    wrong and no combination of containers that goes unhandled: zip, tar, gzip,
    tar.gz, .tar.gz.gz and tar-inside-zip all take the same path.

    FAILS CLOSED. C1: "A file that cannot be opened is a failure." If the bytes
    announce themselves as a container and will not open, that is a violation,
    not a skip -- because the alternative is a container nobody looked inside.

    Depth is capped so a deliberately pathological archive cannot make this
    recurse without bound, and hitting the cap is a FAILURE, not a pass.
    """
    if depth > MAX_DEPTH:
        errors.append(f"{where}: nested deeper than {MAX_DEPTH} containers "
                      f"(a zip bomb, or an archive that cannot be judged) — "
                      f"cannot be cleared")
        return

    kind = sniff(data)
    if kind is None:
        scan_text(data.decode("utf-8", "replace"), where, errors, notes)
        stats["text"] += 1
        return

    stats["archives"] += 1
    if depth > 0:
        stats["nested_archives"] += 1

    # Every container we open costs memory proportional to the DECOMPRESSED size,
    # so the bound is applied after each expansion, not just at the leaves.
    if len(data) > MAX_TEXT_BYTES:
        errors.append(f"{where}: {kind} container is {len(data):,} bytes, over "
                      f"the {MAX_TEXT_BYTES:,}-byte inspection limit — cannot be "
                      f"cleared")
        return

    if kind == "gzip":
        import gzip as _gzip
        import zlib as _zlib
        try:
            inner = _glib_decompress(data, _gzip, _zlib)
        except (OSError, EOFError, _zlib.error) as e:
            errors.append(f"{where}: announces gzip but will not decompress "
                          f"({e}) — cannot be cleared")
            return
        stats["archive_members"] += 1
        scan_blob(inner, f"{where}~gz", errors, notes, stats, depth + 1)
        return

    if kind == "zip":
        import io as _io
        try:
            zf = zipfile.ZipFile(_io.BytesIO(data))
        except (zipfile.BadZipFile, OSError) as e:
            errors.append(f"{where}: announces zip but will not open ({e}) — "
                          f"cannot be cleared")
            return
        with zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                member = f"{where}!{info.filename}"
                if info.file_size > MAX_TEXT_BYTES:
                    errors.append(f"{member}: {info.file_size:,} bytes, over the "
                                  f"inspection limit — cannot be cleared")
                    continue
                try:
                    blob = zf.read(info)
                except (zipfile.BadZipFile, RuntimeError) as e:
                    errors.append(f"{member}: unreadable zip member ({e}) — "
                                  f"cannot be cleared")
                    continue
                stats["archive_members"] += 1
                scan_blob(blob, member, errors, notes, stats, depth + 1)
        return

    # tar
    import io as _io
    try:
        tf = tarfile.open(fileobj=_io.BytesIO(data), mode="r:")
    except tarfile.TarError as e:
        errors.append(f"{where}: announces tar but will not open ({e}) — "
                      f"cannot be cleared")
        return
    with tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            mname = f"{where}!{member.name}"
            if member.size > MAX_TEXT_BYTES:
                errors.append(f"{mname}: {member.size:,} bytes, over the "
                              f"inspection limit — cannot be cleared")
                continue
            fh = tf.extractfile(member)
            if fh is None:
                errors.append(f"{mname}: tar member has no readable content — "
                              f"cannot be cleared")
                continue
            stats["archive_members"] += 1
            scan_blob(fh.read(), mname, errors, notes, stats, depth + 1)


def check(public: pathlib.Path) -> None:
    errors: list[str] = []
    notes: list[str] = []
    stats = {"text": 0, "binary": 0, "archives": 0, "archive_members": 0,
             "skipped_large": 0, "permitted": 0, "nested_archives": 0}

    if not public.is_dir():
        print(f"[nc_guard_public] OK — {public} does not exist yet, so there is "
              f"nothing published to check. NOT a pass on content: run after "
              f"`tools/emit/cli.py`.")
        return

    files = sorted(p for p in public.rglob("*") if p.is_file())
    binary_suffixes = BINARY_SUFFIXES
    for p in files:
        rel = p.relative_to(public).as_posix()
        suffix = p.suffix.lower()

        # Genuinely binary formats (images, fonts, PDFs) are NOT scanned -- they
        # are already compressed or not text -- and the count is reported, because
        # a guard that silently ignores part of a tree is a guard nobody can
        # reason about. Note that .gz is NOT in this set: compressed text is
        # exactly what must be opened.
        if suffix in binary_suffixes:
            stats["binary"] += 1
            continue

        # Every file is read as bytes and handed to the recursive scanner, which
        # decides from magic whether it is a container. A .gz is NOT assumed to
        # be a tar (the Session 4 bug), and a nested container is not missed
        # because of what it is called.
        if p.stat().st_size > MAX_TEXT_BYTES:
            errors.append(f"{rel}: {p.stat().st_size:,} bytes, over the "
                          f"inspection limit — cannot be cleared")
            stats["skipped_large"] += 1
            continue
        try:
            blob = p.read_bytes()
        except OSError as e:
            errors.append(f"{rel}: unreadable ({e}) — cannot be cleared")
            continue
        scan_blob(blob, rel, errors, notes, stats)

    # Session 6 D0. "OK" over zero files is not a pass; it is a guard that looked
    # at nothing and called it clean. Require proof that something was inspected.
    total_inspected = stats["text"] + stats["archive_members"]
    if total_inspected < MIN_INSPECTED:
        errors.append(
            f"only {total_inspected} text blob(s)/archive member(s) were inspected, "
            f"which is below the floor of {MIN_INSPECTED}. A guard that reads "
            f"nothing and reports OK is the Session 4 empty-corpus bug; if public/ "
            f"is genuinely empty, build it first (tools/emit/corpus_public.py) or "
            f"pass --allow-empty.")

    if errors:
        for e in errors:
            print(f"[nc_guard_public] FAIL {e}", file=sys.stderr)
        raise NCGuardPublicError(
            f"[nc_guard_public] {len(errors)} violation(s). public/** must contain "
            f"no CC BY-NC source id outside the disclosure pages."
        )

    for n in notes:
        print(f"[nc_guard_public] note {n}", file=sys.stderr)
    print(
        f"[nc_guard_public] OK — {len(NC_ONLY_SOURCES)} NC ids absent from "
        f"{stats['text']} text blob(s) and {stats['archive_members']} archive "
        f"member(s) across {stats['archives']} container(s) "
        f"({stats['nested_archives']} nested). "
        f"Skipped as binary: {stats['binary']} (NOT scanned — a binary could "
        f"hide a string; see module docstring). Large text skipped: "
        f"{stats['skipped_large']}. Permitted disclosures: {len(notes)}."
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="no NC source id in public/** (invariant 5, second half)")
    ap.add_argument("--public", default="public", type=pathlib.Path)
    args = ap.parse_args(argv)
    try:
        check(args.public)
    except NCGuardPublicError as e:
        print(e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
