#!/usr/bin/env python3
"""tools/tests/test_corpus_tarball_incremental.py — a partial rebuild must not
drop the unchanged works (Session 25 D1).

LICENCE: project code, Apache-2.0.

The Stage-2 copy loop used to rmtree(work_root) and then re-copy only the works
whose fingerprint moved, so the unchanged works were dropped from the tree and
from the tarball — in a directory it had just deleted. Every past run masked the
bug by changing every work at once (the first build, or a corpus-wide emitter
fix). The first run that changed exactly one work produced a tarball containing
only that work; corpus_text_guard caught it as "missing member" for the other six.

This test drives the REAL tools/emit/corpus_tarball.py as a subprocess (its
inputs are the repo's own sources; its outputs live entirely in tmp_path):

  1. build once — all works land;
  2. perturb exactly one work's fingerprint in the manifest, so the regeneration
     guard reports one changed work and six unchanged;
  3. build again — every member must still be there, and because the emitter is
     byte-reproducible, the tarball must be byte-identical to step 1's.

Nothing in the repo is written: --work-root/--tarball/--manifest all point at
tmp_path (Rule 6 — tests own their files).
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys
import tarfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMITTER = ROOT / "tools" / "emit" / "corpus_tarball.py"


def _run(work_root: pathlib.Path, tarball: pathlib.Path, manifest: pathlib.Path,
         *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(EMITTER),
         "--work-root", str(work_root),
         "--tarball", str(tarball),
         "--manifest", str(manifest),
         *extra],
        capture_output=True, text=True, cwd=ROOT)


def _members(tarball: pathlib.Path) -> set[str]:
    with tarfile.open(tarball) as tf:
        return {n for n in tf.getnames() if n.endswith(("text.json", "tokens.json",
                                                        "meta.json"))}


def test_partial_change_keeps_every_work(tmp_path):
    work_root = tmp_path / "work" / "corpus"
    tarball = tmp_path / "corpus.tar.gz"
    manifest = tmp_path / "manifest.json"

    first = _run(work_root, tarball, manifest)
    assert first.returncode == 0, first.stderr[-2000:]
    m1 = json.loads(manifest.read_text(encoding="utf-8"))
    assert m1["works_count"] >= 2, "fixture needs at least two works on disk"
    members1 = _members(tarball)
    sha1 = hashlib.sha256(tarball.read_bytes()).hexdigest()
    for slug in m1["works"]:
        assert f"{slug}/text.json" in members1, \
            f"{slug} missing after the initial build"

    # Exactly one work "changed": its recorded fingerprint no longer matches.
    victim = sorted(m1["works"])[0]
    m1["fingerprints"][victim] = "stale" * 8
    manifest.write_text(json.dumps(m1), encoding="utf-8")

    second = _run(work_root, tarball, manifest)
    assert second.returncode == 0, second.stderr[-2000:]
    assert "fingerprint changed for:" in second.stdout, \
        "expected exactly one changed work in the simulated run"
    members2 = _members(tarball)
    assert members2 == members1, (
        "an incremental rebuild dropped members: "
        f"only in first: {sorted(members1 - members2)}, "
        f"only in second: {sorted(members2 - members1)}")

    # Byte-reproducible: the simulated change was to the MANIFEST's recorded
    # fingerprint, not to any source, so the rebuilt tarball must be the same
    # bytes the first run produced.
    assert hashlib.sha256(tarball.read_bytes()).hexdigest() == sha1, (
        "identical inputs produced different tarball bytes")
