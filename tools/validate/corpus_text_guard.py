#!/usr/bin/env python3
"""tools/validate/corpus_text_guard.py — the corpus must actually contain text.

Session 4 S4-C1. For one full session the corpus shipped with `coptic: ""` and
`form: ""` on every verse and every one of 3,470 tokens, and nothing caught it:

  - the round trip passed, because it looks up by LEMMA;
  - the counts matched, because lemmas were never empty;
  - the sizes looked plausible, because JSON keys cost bytes either way;
  - the fingerprints were stable, because they hashed meta.json, not the text.

Every check agreed the corpus was fine because every check was looking at
something other than the thing that was broken. A data pipeline that emits empty
strings is not a data pipeline, so this asserts the plain thing, on the shipped
artefact, with no reference to the parser that produced it.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import tarfile

ROOT = pathlib.Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="the corpus must contain text")
    ap.add_argument("--dist", type=pathlib.Path, default=ROOT / "data" / "dist")
    ap.add_argument("--allow-missing", action="store_true",
                    help="skip instead of failing when no corpus is baked. For a "
                         "fresh clone only; it is not a pass.")
    args = ap.parse_args(argv)

    manifest = args.dist / "corpus" / "manifest.json"
    tarball = args.dist / "corpus" / "corpus.tar.gz"
    # Session 6 D0, closing a gap COVERAGE.md admitted: this used to SKIP with
    # exit 0 when the corpus was absent. A guard that reads nothing and exits 0 is
    # the Session 4 empty-corpus bug wearing a different hat. Absence is failure.
    # --allow-missing exists only for a fresh clone before the first bake, and it
    # prints why loudly.
    if not manifest.is_file() or not tarball.is_file():
        if args.allow_missing:
            print("[corpus_text_guard] SKIP — no baked corpus, and --allow-missing "
                  "was passed. NOT a pass on content.", file=sys.stderr)
            return 0
        print("[corpus_text_guard] FAIL — the corpus artefact is absent "
              f"(manifest={manifest.is_file()}, tarball={tarball.is_file()}). "
              f"An absent corpus cannot be cleared. Run "
              f"tools/emit/corpus_tarball.py, or pass --allow-missing if a fresh "
              f"clone genuinely has no corpus yet.", file=sys.stderr)
        return 1

    m = json.loads(manifest.read_text(encoding="utf-8"))
    errors: list[str] = []
    verses = tokens = 0

    with tarfile.open(tarball) as tf:
        for slug, expected in sorted(m.get("works", {}).items()):
            try:
                text = json.loads(tf.extractfile(f"{slug}/text.json").read().decode("utf-8"))
                toks = json.loads(tf.extractfile(f"{slug}/tokens.json").read().decode("utf-8"))
            except KeyError as e:
                errors.append(f"{slug}: missing member {e}")
                continue

            vs = text.get("verses") or []
            ts = toks.get("tokens") or []
            if not vs:
                errors.append(f"{slug}: no verses at all")
            if not ts:
                errors.append(f"{slug}: no tokens at all")

            blank_coptic = [v.get("ref") for v in vs if not (v.get("coptic") or "").strip()]
            blank_en = [v.get("ref") for v in vs if not (v.get("en") or "").strip()]
            blank_form = [t.get("i") for t in ts if not (t.get("form") or "").strip()]
            blank_lemma = [t.get("i") for t in ts if not (t.get("lemma") or "").strip()]
            blank_pos = [t.get("i") for t in ts if not (t.get("pos") or "").strip()]

            for label, bad in (("coptic text", blank_coptic), ("english", blank_en)):
                if bad:
                    errors.append(f"{slug}: {len(bad)} verse(s) with no {label}, "
                                  f"first: {bad[0]!r}")
            for label, bad in (("surface form", blank_form), ("lemma", blank_lemma),
                               ("part of speech", blank_pos)):
                if bad:
                    errors.append(f"{slug}: {len(bad)} token(s) with no {label}, "
                                  f"first index {bad[0]}")

            if len(ts) != expected.get("tokens"):
                errors.append(f"{slug}: manifest says {expected.get('tokens')} tokens, "
                              f"file has {len(ts)}")

            # meta.json must carry the content hashes, or a text-only edit would
            # not move the fingerprint and the rebuild guard would skip the work.
            meta = json.loads(tf.extractfile(f"{slug}/meta.json").read().decode("utf-8"))
            content = meta.get("content_sha256") or {}
            for name in ("text.json", "tokens.json"):
                want = content.get(name)
                if not want:
                    errors.append(f"{slug}: meta.json has no content_sha256 for "
                                  f"{name}, so editing it would not move the "
                                  f"fingerprint (S4-C2)")
                    continue
                got = __import__("hashlib").sha256(
                    tf.extractfile(f"{slug}/{name}").read()).hexdigest()
                if got != want:
                    errors.append(f"{slug}/{name}: meta records {want[:12]}…, "
                                  f"file is {got[:12]}…")

            verses += len(vs)
            tokens += len(ts)

    if errors:
        print(f"[corpus_text_guard] FAIL — {len(errors)} problem(s). "
              f"A corpus with empty text is not a corpus:", file=sys.stderr)
        for e in errors[:12]:
            print(f"  - {e}", file=sys.stderr)
        if len(errors) > 12:
            print(f"  ... and {len(errors) - 12} more", file=sys.stderr)
        return 1

    print(f"[corpus_text_guard] OK — {m.get('works_count', 0)} work(s), "
          f"{verses} verses, {tokens} tokens; every verse has Coptic and English, "
          f"every token has a form, lemma and POS; fingerprints cover content")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
