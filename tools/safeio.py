#!/usr/bin/env python3
"""tools/safeio.py — the ONE way this project writes an artefact.

Session 6 D1 / C2. Rule 3:

    Every artefact write is verified by read-back. A write that reports success
    is a claim; a read-back is evidence. Filesystems fail, NFS reorders,
    containers unmount — none of them announce themselves. If the code can't
    re-read what it wrote, the write did not happen.

This exists because it already happened twice, and the second time it was worse
than the first.

1. `emit/cli.py` reported `LICENSES.csv 19 row(s)` on a write that had not
   landed, because it trusted `write_text()` returning without raising.
2. Worse, a stale-dentry episode made `is_file()` return False for a file the
   emitter was about to regenerate, so `existing` came back empty and every
   `originators` / `reference` / `notes` value was replaced with a blank. That is
   a licence manifest forgetting where its sources came from — invariant 7
   breaking in the most literal way available.

Neither was catchable by the write call itself. Both are catchable by re-reading.

`write_verified()` does four things, in order, and refuses to continue on any
mismatch:

    write to path + ".tmp"   -> a partial write never lands under the real name
    fsync the file           -> the bytes are on the device, not in a buffer
    os.replace onto path     -> atomic; a reader sees the old file or the new one
    read back and compare    -> evidence, not a claim

Compression is handled by the caller, because whether a path should be gzipped is
a property of the FILENAME (`shard-NNN.json.gz`), and `write_verified` accepts
pre-compressed bytes without needing to know that.

NOT NAMED tools/io.py. Session 6 D1 asked for that path; it cannot work.  is
in  before any project code runs, so  always resolves to
the STDLIB module, and  is unreachable under its own name -- which is
exactly how this was found:  silently handed back the stdlib and
then failed on .
A module that shadows a stdlib name and can never be imported is worse than a
differently-named one, so this is . See DECISIONS.md S6-B2.

No runtime dependency: stdlib only, and this is a build-time module, not part of
the reading path (invariants 1-3).

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import gzip
import os
import pathlib
import sys

#: Matches a truncated gzip stream, which is how a partial write announces itself.
_GZIP_MAGIC = b"\x1f\x8b"


class WriteVerificationError(SystemExit):
    """A write could not be verified.

    Subclasses SystemExit so an uncaught failure exits non-zero with the reason
    printed, which is what CI needs. Catch SystemExit explicitly.
    """


def write_verified(path: pathlib.Path, data: bytes, *, encoding: str | None = None,
                   compress: bool | None = None) -> int:
    """Write `data` to `path`, verified. Returns the number of bytes on disk.

    `data` is raw bytes. If `encoding` is given, `data` must be `str` and is
    encoded with it.

    `compress` defaults to None, meaning "compress iff the filename ends .gz".
    Pass True/False to override deliberately; the default exists so that a module
    reading and writing a format cannot disagree about it (Session 5 S5-B2, where
    `corpus_refs.py` wrote plain JSON into 23 files named `shard-NNN.json.gz`).
    """
    if isinstance(data, str):
        if encoding is None:
            raise WriteVerificationError(
                f"[safeio] {path}: str data needs an encoding")
        data = data.encode(encoding)
    elif encoding is not None:
        raise WriteVerificationError(
            f"[safeio] {path}: encoding={encoding!r} given but data is bytes")

    if compress is None:
        compress = path.name.endswith(".gz")

    if compress:
        if not data.startswith(_GZIP_MAGIC):
            raise WriteVerificationError(
                f"[safeio] {path}: filename says .gz so the content must be gzip, but "
                f"the first bytes are {data[:2].hex()!r}. Refusing to write a "
                f"mislabelled file.")
        payload = data
    else:
        payload = data

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")

    # Session 12 D2 — DO NOT REWRITE IDENTICAL CONTENT.
    #
    # This looks like a micro-optimisation and is not. tools/build.py derives the
    # BUILD-MANIFEST `generated` stamp from the newest mtime under content/,
    # static/, themes/ and data/dist/, precisely so the stamp reflects the inputs
    # rather than the clock. corpus_pages.py writes generated pages into
    # content/corpus/, so an unconditional rewrite bumped that mtime on every
    # build, and the manifest timestamp — and therefore the manifest bytes —
    # advanced every run. Two builds of an unchanged tree were not byte-identical,
    # which is the exact claim the comment above the stamp makes.
    #
    # The bug is only visible because the check compares CONTENT. A path-and-size
    # hash, which is what Session 10 used, would have passed it: the file count
    # and sizes were unchanged, only the bytes differed.
    #
    # So: if the bytes on disk already match, leave the file alone and keep its
    # mtime. That is the right behaviour for every generator in this pipeline,
    # not just this one.
    try:
        if path.is_file() and path.read_bytes() == payload:
            return path.stat().st_size
    except OSError:
        pass  # unreadable: fall through and write it properly

    try:
        with tmp.open("wb") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
    except OSError as e:
        raise WriteVerificationError(
            f"[safeio] {path}: write failed ({e}). Not claiming success.") from e

    try:
        os.replace(tmp, path)
    except OSError as e:
        tmp.unlink(missing_ok=True)
        raise WriteVerificationError(
            f"[safeio] {path}: os.replace failed ({e}). The file at that path is "
            f"NOT the data we just wrote. Not claiming success.") from e

    # ── the read-back. This is the whole point. ─────────────────────────────
    try:
        got = path.read_bytes()
    except OSError as e:
        # Session 6 D1: also clear the .tmp. A no-op os.replace does NOT raise, so
        # the failure only surfaces here -- and without this the scratch file would
        # be left sitting in data/dist to be committed by the next run.
        tmp.unlink(missing_ok=True)
        raise WriteVerificationError(
            f"[safeio] {path}: written but cannot be read back ({e}). The write did "
            f"not durably happen. Not claiming success.") from e

    if got != payload:
        tmp.unlink(missing_ok=True)
        raise WriteVerificationError(
            f"[safeio] {path}: read-back mismatch. Wrote {len(payload):,} B, read "
            f"{len(got):,} B"
            + (f", first difference at byte {_first_diff(payload, got)}"
               if _first_diff(payload, got) is not None else "")
            + ". Not claiming success.")
    return len(got)


def write_text_verified(path: pathlib.Path, text: str, *, encoding: str = "utf-8") -> int:
    """`write_verified` for text. Refuses .gz unless the caller compresses."""
    if path.name.endswith(".gz"):
        return write_verified(path, gzip.compress(text.encode(encoding),
                                                   compresslevel=9, mtime=0))
    return write_verified(path, text.encode(encoding))


def resolve_readable(path: pathlib.Path) -> pathlib.Path:
    """Return `path` if it exists, else `path` with `.gz` appended (stripped).

    Session 7 C4 gzipped the provenance CSVs and deleted the plain copies. That
    immediately re-armed the Session 6 S6-B1 trap: `emit/cli.py` reads the
    PREVIOUS licence manifest to carry `originators` / `reference` / `notes`
    forward, so if it looked only for the plain name it would silently find
    nothing and regenerate every provenance field blank. Losing a known licence
    is invariant 7 breaking in the most literal way available.

    So readers resolve, rather than assuming a form. Exactly as `shardio` does
    for `.json` / `.json.gz`.
    """
    if path.exists():
        return path
    if path.suffix == ".gz":
        return path
    gz = path.with_name(path.name + ".gz")
    if gz.exists():
        return gz
    return path          # neither exists; caller reports the canonical name


def read_maybe_gzip(path: pathlib.Path) -> bytes:
    """Bytes of `path`, decompressing if it is `.gz` or resolves to a `.gz`."""
    p = resolve_readable(path)
    blob = p.read_bytes()
    if p.name.endswith(".gz"):
        blob = gzip.decompress(blob)
    return blob


def read_csv_rows(path: pathlib.Path) -> tuple[list[dict], str]:
    """Rows from a CSV that may be plain or .gz. Returns (rows, path_used).

    Session 7 C4. `resolve_readable()` tells you WHICH file exists; it does not
    make the file readable as text. The first version of `licence_guard` after
    the gzip move did exactly that and died with

        UnicodeDecodeError: 'utf-8' codec can't decode byte 0x8b in position 1

    -- gzip's magic byte, read as UTF-8. So the resolve and the decode belong in
    the same helper, or every caller has to remember both halves.
    """
    import csv
    import io as _io
    p = resolve_readable(path)
    raw = read_maybe_gzip(p)
    return list(csv.DictReader(_io.StringIO(raw.decode("utf-8"), newline=""))), str(p)


def _first_diff(a: bytes, b: bytes) -> int | None:
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    return None if len(a) == len(b) else min(len(a), len(b))
