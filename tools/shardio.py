#!/usr/bin/env python3
"""tools/shardio.py — the ONE way to read a dictionary shard.

Session 5 G2: `nc_guard` globbed `data/dist/**/*.json` and `dialects_check`,
`dry_run`, `corpus_refs` and `obsidian` globbed `shard-*.json`. **None of them
matched `.json.gz`.** On the day D2 gzipped the shards, with no other change,
four guards would have found zero files and reported success — the Session 4
empty-corpus bug arriving through a filename.

Session 5 G1: with `data/dist/dict/` deleted, `nc_guard`, `licence_guard` and
`dry_run --real` all printed OK / PASS, because zero entries is a perfectly valid
dataset to a loop with no zero check.

So both failures have the same fix and the same home. This module:

  1. resolves both `.json` and `.json.gz`, so compression is invisible to callers
     and impossible to forget;
  2. **fails closed** when it finds no shards, so "nothing to check" can never be
     mistaken for "nothing wrong".

Fail-closed is the whole point. Every one of those guards would rather stop the
build on a fresh clone than pass on an empty dataset, and the escape hatch
(`require=False`) is opt-in and explicit at the call site.

No runtime dependency: stdlib `gzip` and `json` only.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import gzip
import json
import pathlib
from typing import Iterable, Iterator

import safeio  # noqa: E402  (same directory)

#: Suffixes that count as a dictionary shard. `.json.gz` first because
#: `Path.suffix` of "shard-000.json.gz" is ".gz", not ".json.gz".
SHARD_SUFFIXES: tuple[str, ...] = (".json.gz", ".json")


class ShardIOError(SystemExit):
    """No shards where shards are required.

    Subclasses SystemExit (like the other guards' error types) so an uncaught
    failure exits non-zero with the reason printed, which is what CI needs.
    """


def is_shard(path: pathlib.Path) -> bool:
    name = path.name
    return name.startswith("shard-") and name.endswith(SHARD_SUFFIXES)


def read_bytes(path: pathlib.Path) -> bytes:
    """Raw bytes of a shard, transparently decompressing `.gz`.

    `mtime=0` is not available here and does not matter: this is read-only.
    """
    if path.name.endswith(".gz"):
        with gzip.open(path, "rb") as fh:
            return fh.read()
    return path.read_bytes()


def read_shard(path: pathlib.Path, *, strict: bool = True) -> dict | None:
    """One shard as a dict.

    Two different failures, treated differently on purpose:

    * **malformed JSON -> always a failure.** A file named `shard-*.json` that
      will not parse cannot be cleared for licensing, so it must stop the build.
      Session 2 established this and `test_guards.py` pins it.
    * **valid JSON that is not an object -> ignored** (`strict=False` returns
      `None`). Session 2 also pinned this: a stray `records.json`-shaped array in
      `dict/` is not a shard and should not crash the guard.

    `strict=True` (the default) turns the second case into a failure too, which is
    what the explicit readers want -- `shard_guard` should not quietly pass over a
    shard-shaped file that turned out to be a list.
    """
    try:
        blob = json.loads(read_bytes(path).decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError, EOFError) as e:
        raise ShardIOError(
            f"[shardio] {path}: cannot read ({e}). A shard that cannot be read "
            f"cannot be checked, so it is a failure rather than a skip."
        ) from e
    if not isinstance(blob, dict):
        if strict:
            raise ShardIOError(
                f"[shardio] {path}: expected a JSON object, got "
                f"{type(blob).__name__}. It is named like a shard, so this is a "
                f"failure rather than a silent skip.")
        return None
    return blob


def write_shard(path: pathlib.Path, payload: dict) -> int:
    """Write a shard, compressing iff the FILENAME says .gz. Returns bytes written.

    Session 5 S5-B2. This function exists because `shardio` had a reader and no
    writer, and `corpus_refs.py` responded with `shard.write_text(json.dumps(...))`
    -- which, once the shards were gzipped, wrote PLAIN JSON into 23 files named
    `shard-NNN.json.gz`. Every one was mislabelled: `magic=7b0a`, i.e. `{\n`.

    Nothing caught it at the time. The files existed, they were the right size,
    and `nc_guard` had already read them successfully moments earlier. It was
    only the *next* reader that failed, with "Not a gzipped file (b'{\n')".

    So: a module that reads a format must also write it. Otherwise every caller
    invents its own write, and one of them invents a wrong one. The rule here is
    that the FILENAME is the contract -- `.gz` in, gzip out, always -- because
    that is the only thing both sides can agree on without passing a flag around.
    """
    raw = json.dumps(payload, ensure_ascii=False, indent=1).encode("utf-8")
    if path.name.endswith(".gz"):
        raw = gzip.compress(raw, compresslevel=9, mtime=0)
    # Session 6 D1: Rule 3. This function is where Session 5 S5-B2 originated --
    # it existed precisely because corpus_refs.py needed a writer and had none.
    # A writer is exactly where an unverified write is most dangerous.
    return safeio.write_verified(path, raw)


def shard_paths(dict_dir: pathlib.Path) -> list[pathlib.Path]:
    """Every shard in `dict_dir`, sorted, de-duplicated across the two suffixes.

    Sorted by the numeric shard id rather than by name, so shard-9 sorts before
    shard-10 in the returned order even though "shard-0009" would not. The
    filenames are zero-padded so this is belt-and-braces, but the readers
    downstream concatenate in this order, so it should not depend on luck.
    """
    if not dict_dir.is_dir():
        return []
    found = [p for p in dict_dir.iterdir() if p.is_file() and is_shard(p)]
    return sorted(found, key=lambda p: (p.name[: -len(p.suffix)] if p.name.endswith(".gz")
                                        else p.stem, p.name))


def _require(paths: list[pathlib.Path], dict_dir: pathlib.Path, require: bool,
             what: str) -> list[pathlib.Path]:
    if not paths and require:
        raise ShardIOError(
            f"[shardio] no dictionary shards in {dict_dir} "
            f"(looked for shard-*.json and shard-*.json.gz).\n"
            f"  This guard needed {what} and found nothing. Treating an absent\n"
            f"  dataset as 'no problems found' is how Session 4 shipped a corpus\n"
            f"  with no text in it, and how Session 5 found three guards that\n"
            f"  passed with data/dist/dict/ deleted. Run tools/emit/cli.py, or pass\n"
            f"  require=False if an empty dataset is genuinely what you mean."
        )
    return paths


def iter_entries(dict_dir: pathlib.Path, *, require: bool = True
                 ) -> Iterator[tuple[pathlib.Path, dict]]:
    """Yield (shard_path, entry) for every entry in the dataset.

    `require=True` (the default) fails when no shards exist. Set it False only
    where an empty dataset is a legitimate input, and say so in a comment.
    """
    paths = _require(shard_paths(dict_dir), dict_dir, require, "the dictionary entries")
    for p in paths:
        blob = read_shard(p, strict=False)   # non-dict JSON is ignored, not fatal
        if blob is None:
            continue
        for entry in blob.get("entries", []) or []:
            if isinstance(entry, dict):
                yield p, entry


def load_entries(dict_dir: pathlib.Path, *, require: bool = True) -> list[dict]:
    """All entries as a flat list, in shard order. Fails closed on no shards."""
    return [e for _, e in iter_entries(dict_dir, require=require)]


def load_index(dict_dir: pathlib.Path, *, require: bool = True) -> dict:
    """The existing `index.json` (the header). Session 5 D3 writes a real
    lookup index to `index.json` too, so this reads whatever is there."""
    p = dict_dir / "index.json"
    if not p.is_file():
        if require:
            raise ShardIOError(
                f"[shardio] {p} is missing. The shard index is part of the "
                f"artefact, not an optional convenience.")
        return {}
    return json.loads(read_bytes(p).decode("utf-8"))


def describe(dict_dir: pathlib.Path) -> str:
    """One line naming what is actually on disk — for guard output.

    Guards print this so that "0 entries checked" is visibly 0 because the tree
    is empty, rather than 0 because a glob stopped matching.
    """
    paths = shard_paths(dict_dir)
    if not paths:
        return f"{dict_dir}: NO SHARDS"
    n = sum(len(read_shard(p).get("entries", []) or []) for p in paths)
    gz = sum(1 for p in paths if p.name.endswith(".gz"))
    return (f"{dict_dir}: {len(paths)} shard(s) ({gz} gzipped), {n} entries")
