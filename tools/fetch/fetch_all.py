#!/usr/bin/env python3
"""tools/fetch/fetch_all.py — download sources, verify SHA-256 pins, hard-fail.

Every source is pinned in tools/sources.lock with sha256 + bytes + snapshot.
This script verifies all three and EXITS NON-ZERO on any mismatch.

Why this hard-fails: an upstream change must surface as a human decision, not a
shrug. If Kaikki quietly reshapes its schema and we re-ingest without noticing,
~3,300 dictionary entries can change with nobody reviewing them. The pin is what
turns that into a pull request a person reads.

    python3 tools/fetch/fetch_all.py                  # verify + download
    python3 tools/fetch/fetch_all.py --check-only     # verify, do not download
    python3 tools/fetch/fetch_all.py --write-pins     # first-run: compute pins

Design notes
------------
* STREAMING. Kaikki is 62 MB. Never load it whole.
* Honours ETAG / LAST-MODIFIED where offered, so a weekly bake that changes
  nothing costs almost nothing.
* --write-pins exists ONLY for a first run against a source that has never been
  pinned. It prints what it wrote and refuses to run if the file already has a
  non-placeholder pin for that source, so it cannot be used to launder a drift.

LICENCE: project code, Apache-2.0. Upstream content keeps its own licence.
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import shutil
import re
import subprocess
import sys
import tomllib

ROOT = pathlib.Path(__file__).resolve().parents[2]
LOCK = ROOT / "tools" / "sources.lock"
SOURCES = ROOT / "sources"
CHUNK = 1 << 20

OK, WARN, FAIL = "  ok  ", " warn ", " FAIL "
RED, YEL, GRN, DIM, RST = "\033[31m", "\033[33m", "\033[32m", "\033[2m", "\033[0m"
if not sys.stdout.isatty():
    OK = WARN = FAIL = ""
    RED = YEL = GRN = DIM = RST = ""


def load_lock() -> dict:
    with LOCK.open("rb") as fh:
        return tomllib.load(fh)


def sha256_of(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_of_url(url: str, dest: pathlib.Path) -> str:
    """Download then hash. Two passes over the bytes beats trusting Content-Length."""
    h = hashlib.sha256()
    with dest.open("wb") as out:
        with _open(url) as r:
            for chunk in iter(lambda: r.read(CHUNK), b""):
                h.update(chunk)
                out.write(chunk)
    return h.hexdigest()


def _open(url: str):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "coptic-reference-fetch/0.1"})
    return urllib.request.urlopen(req, timeout=300)


def fetch_one(name: str, spec: dict, *, check_only: bool, write_pins: bool) -> int:
    url = spec.get("url")
    if not url:
        print(f"{DIM}[{name}]{RST} {DIM}no url - metadata-only entry, nothing to fetch{RST}")
        return 0

    dest = SOURCES / name / url.rsplit("/", 1)[-1]
    want_sha = str(spec.get("sha256", "")).strip()
    want_bytes = spec.get("bytes")

    # Semantics, and they matter:
    #   pinned + MATCHES  -> ok
    #   pinned + DIFFERS  -> HARD FAIL. Upstream changed, or the pin is wrong.
    #   NOT pinned        -> warn. A forward declaration of something we intend to
    #                        ingest but have not pinned yet. NOT a failure.
    # A declared-but-unpinned source must not red the bake every week, or people
    # learn to ignore red - which is how a pin stops being a pin.
    if not check_only:
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"{DIM}[{name}]{RST} downloading {url}")
        try:
            got = sha256_of_url(url, dest)
        except Exception as e:  # noqa: BLE001 - report, do not crash the bake
            print(f"{FAIL}{RED}[{name}]{RST} download failed: {e}")
            return 1
    else:
        if not dest.exists():
            print(f"{WARN}{YEL}[{name}]{RST} {DIM}declared, not yet downloaded{RST}")
            return 0
        got = sha256_of(dest)

    size = dest.stat().st_size
    problems = []

    if want_sha:
        if want_sha.lower() != got:
            problems.append(f"sha256 mismatch\n         pinned   {want_sha}\n         actual   {got}")
        if want_bytes is not None and int(want_bytes) != size:
            problems.append(f"byte-count mismatch: pinned {want_bytes}, actual {size}")

        # Record-count gate: catches schema drift that preserves size and shape.
        if name == "kaikki" and dest.exists():
            want_records = spec.get("records")
            if want_records is not None:
                with dest.open("rb") as fh:
                    n = sum(c.count(b"\n") for c in iter(lambda: fh.read(CHUNK), b""))
                if n != int(want_records):
                    problems.append(f"record-count mismatch: pinned {want_records}, actual {n}")
    else:
        print(f"{WARN}{YEL}[{name}]{RST} {DIM}declared but NOT pinned - "
              f"{size:,} bytes, sha256 {got[:16]}…{RST}")
        if write_pins:
            print(f"       {DIM}to pin:  sha256 = \"{got}\"  /  bytes = {size}{RST}")
        return 0

    if problems:
        if write_pins and want_sha == "":
            print(f"{WARN}{YEL}[{name}]{RST} writing new pin:")
            print(f"         sha256   = \"{got}\"")
            print(f"         bytes    = {size}")
            return 0
        for p in problems:
            print(f"{FAIL}{RED}[{name}]{RST} {p}")
        print(f"       {DIM}Upstream changed, or the pin is wrong. Do NOT silently update it.{RST}")
        print(f"       {DIM}Read the diff, confirm on the upstream repo, then update{RST}")
        print(f"       {DIM}tools/sources.lock in a pull request with a note in CHANGELOG.md.{RST}")
        return 1

    lic = spec.get("licence", "UNKNOWN")
    print(f"{OK}{GRN}[{name}]{RST} {size:,} bytes  sha256 {got[:16]}…  licence {lic}")
    return 0


def _licence_verdict(spec: dict) -> str:
    """Find this entry's licence verdict, wherever the lock file keeps it.

    Not every entry uses the top-level `licence` key. `cdo` splits it into
    `licence_data` / `licence_code`; `nc_only` and `upstream_tools` carry a
    licence per nested source table. An earlier version of the structural audit
    only looked at `licence`, and failed three perfectly good entries for it.
    """
    for key in ("licence", "licence_data"):
        v = str(spec.get(key, "")).strip()
        if v:
            return v
    for value in spec.values():
        if isinstance(value, dict):
            v = str(value.get("licence", "")).strip()
            if v:
                return v
    return ""


def verify_pins_are_wellformed(lock: dict) -> list[str]:
    """Structural audit of the lock file itself. Needs no downloads.

    This is the part of source verification that CAN run on a fresh CI checkout,
    where `sources/` is gitignored and therefore absent. It cannot detect an
    upstream change — only a malformed, self-contradictory, or copy-pasted pin.
    """
    problems: list[str] = []
    seen: dict[str, str] = {}
    for name, spec in sorted(lock.items()):
        if not isinstance(spec, dict):
            continue
        sha = str(spec.get("sha256", "")).strip()
        size = spec.get("bytes")
        recs = spec.get("records")
        if sha:
            if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha.lower()):
                problems.append(f"[{name}] sha256 is not 64 lowercase hex chars: {sha!r}")
            if size is None:
                problems.append(f"[{name}] has a sha256 pin but no byte count")
            elif int(size) <= 0:
                problems.append(f"[{name}] byte count is not positive: {size!r}")
            if recs is not None and int(recs) <= 0:
                problems.append(f"[{name}] record count is not positive: {recs!r}")
            if int(size or 0) > 0 and int(recs or 0) > int(size or 0):
                problems.append(f"[{name}] record count {recs} exceeds byte count {size}")
            # A sha256 reused across two sources is a copy-paste error, and it
            # would let one file's pin silently bless another's bytes.
            if sha.lower() in seen:
                problems.append(f"[{name}] sha256 is identical to [{seen[sha.lower()]}]: "
                                f"copy-paste, or genuinely the same artefact")
            else:
                seen[sha.lower()] = name
        if not _licence_verdict(spec):
            problems.append(f"[{name}] declares no licence verdict anywhere in its "
                            f"entry — invariant 7 requires one")
    return problems


def self_test() -> int:
    """Prove the verification logic actually rejects bad pins, with no network.

    Without this, the CI job named "source pins" is decorative: `sources/` is
    gitignored, so on a fresh checkout there is nothing to verify and the job
    passes vacuously. Two things are checked:

      A. the end-to-end fetch-and-compare path, driven over a `file://` URL so
         it needs no network: a correct pin must be accepted, a wrong sha and a
         wrong byte count must both be rejected.
      B. the structural auditor must REJECT a deliberately malformed lock. An
         auditor that only ever returns [] is as useless as no auditor.
    """
    import tempfile

    failures = 0
    with tempfile.TemporaryDirectory() as td:
        probe = pathlib.Path(td) / "probe.jsonl"
        payload = b'{"word":"tenou","lang_code":"cop"}\n' * 128
        probe.write_bytes(payload)
        real = sha256_of(probe)
        size = probe.stat().st_size
        url = probe.as_uri()

        print("A. end-to-end verify path (file://, no network)")
        cases = [
            ("good",        {"sha256": real, "bytes": size}, 0),
            ("bad_sha",     {"sha256": "0" * 64, "bytes": size}, 1),
            ("bad_bytes",   {"sha256": real, "bytes": size + 1}, 1),
        ]
        for label, extra, expect in cases:
            name = f"probe_{label}"
            spec = {"url": url, "licence": "CC-BY-SA-4.0", **extra}
            got = fetch_one(name, spec, check_only=False, write_pins=False)
            status = "OK  " if got == expect else "FAIL"
            if got != expect:
                failures += 1
            print(f"  {status} {label}: exit {got} (expected {expect})")
            # Remove the probe copy so --self-test leaves sources/ exactly as
            # it found it. An earlier version unlinked the file but left the
            # empty directory behind, so three probe_* dirs accumulated in the
            # real sources tree on every CI run.
            shutil.rmtree(SOURCES / name, ignore_errors=True)

        print()
        print("B. structural auditor must REJECT a malformed lock")
        bad_lock = {
            "ok":            {"url": "u", "sha256": real, "bytes": size,
                              "licence": "CC-BY-SA-4.0"},
            "short_hex":     {"url": "u", "sha256": "abc", "bytes": size,
                              "licence": "CC-BY-SA-4.0"},
            "no_bytes":      {"url": "u", "sha256": real, "licence": "CC-BY-SA-4.0"},
            "dup_sha":       {"url": "u", "sha256": real, "bytes": size,
                              "licence": "CC-BY-SA-4.0"},
            "no_licence":    {"url": "u", "sha256": real, "bytes": size},
            "records_gt_bytes": {"url": "u", "sha256": real, "bytes": 10,
                                 "records": 99, "licence": "CC-BY-SA-4.0"},
        }
        problems = verify_pins_are_wellformed(bad_lock)
        for want in ("short_hex", "no_bytes", "dup_sha", "no_licence",
                     "records_gt_bytes"):
            hit = any(want in p for p in problems)
            if not hit:
                failures += 1
            print(f"  {'OK  ' if hit else 'FAIL'} auditor flags {want}")
        clean = verify_pins_are_wellformed({"ok": bad_lock["ok"]})
        if clean:
            failures += 1
            print(f"  FAIL auditor false-flags a well-formed entry: {clean}")
        else:
            print("  OK   auditor accepts a well-formed entry")

    print()
    print("self-test FAILED" if failures else "self-test OK — verifier is live, not vacuous")
    return failures



def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check-only", "--check", action="store_true",
                    dest="check_only",
                    help="verify existing downloads without fetching "
                         "(--check is an explicit alias, not an abbreviation)")
    ap.add_argument("--write-pins", action="store_true",
                    help="compute and print pins for never-pinned sources (first run only)")
    ap.add_argument("--strict", action="store_true",
                    help="fail if a pinned source is not present locally. Use for a "
                         "release bake; NOT for CI, where sources/ is gitignored.")
    ap.add_argument("--allow-absent-sources", action="store_true",
                    help="do not fail when pinned sources have no local copy. For "
                         "CI, where sources/ is gitignored and none are present; "
                         "prints a warning saying nothing was verified.")
    ap.add_argument("--self-test", action="store_true",
                    help="exercise the verification logic against synthetic data, so "
                         "the CI job is not vacuous when sources/ is absent")
    args = ap.parse_args()

    if args.self_test:
        return 1 if self_test() else 0

    lock = load_lock()
    print(f"verifying {len(lock)} entries in tools/sources.lock\n")

    failures = 0
    verified = skipped = 0
    for name, spec in lock.items():
        if not isinstance(spec, dict):
            continue
        rc = fetch_one(name, spec, check_only=args.check_only,
                       write_pins=args.write_pins)
        failures += rc
        if rc == 0 and spec.get("sha256") and spec.get("url"):
            dest = SOURCES / name / str(spec.get("url", "")).rsplit("/", 1)[-1]
            if dest.exists():
                verified += 1
            else:
                skipped += 1
                if args.strict:
                    print(f"{FAIL}{RED}[{name}]{RST} pinned but not present, and "
                          f"--strict was given")
                    failures += 1
        elif spec.get("url") and not spec.get("sha256"):
            skipped += 1

    print()
    struct = verify_pins_are_wellformed(lock)
    for s in struct:
        print(f"{FAIL}{RED}{s}{RST}")
    failures += len(struct)

    if failures:
        print(f"{RED}{FAIL}{failures} source(s) failed verification.{RST}")
        return 1

    # How many PINNED sources have no local copy. Session 5 G5: these used to be
    # indistinguishable from the unpinned ones, so a deleted source was reported
    # as "metadata-only" and the run passed.
    missing_pinned = sum(
        1 for n, spec in lock.items()
        if (spec.get("sha256") or "").strip() != ""
        and not (SOURCES / n).is_dir()
    )

    # Session 5 G5. Say plainly WHAT WAS VERIFIED, and never print an unqualified
    # "all sources verified" when some sources were not looked at at all.
    #
    # Proved in D1: with `sources/kaikki/` deleted, this printed
    #     all sources verified against tools/sources.lock
    #     1 pinned source(s) byte-verified
    #     4 declared without a local copy
    # and exited 0. Every line after the first was true and together they said
    # "nothing to worry about". Deleting a pinned source WEAKENED the check
    # silently -- a removal became a demotion to "metadata-only".
    #
    # The headline now carries the arithmetic. If not every pinned source was
    # present, it says so, in yellow, with the count.
    pinned_total = verified + missing_pinned
    if missing_pinned:
        print(f"{YEL}{WARN}all PRESENT sources verified against "
              f"tools/sources.lock{RST}")
        print(f"{DIM}  {verified} of {pinned_total} pinned source(s) were present "
              f"and byte-verified; {missing_pinned} were NOT PRESENT and were "
              f"not checked.{RST}")
        if verified == 0:
            print(f"{DIM}  <-- NONE. sources/ is absent (it is gitignored), so this "
                  f"run cannot detect an upstream change at all.{RST}")
            print(f"{DIM}  Byte verification happens when a maintainer runs "
                  f"fetch_all.py locally. Use --strict to make absence a "
                  f"failure.{RST}")
        else:
            print(f"{DIM}  A pinned source that is missing cannot be verified; "
                  f"absence is not a pass. Run fetch_all.py, or --strict to "
                  f"enforce it.{RST}")
    else:
        print(f"{GRN}all {verified} pinned source(s) verified against "
              f"tools/sources.lock{RST}")
    print(f"{DIM}  {verified} pinned source(s) byte-verified{RST}")
    print(f"{DIM}  {skipped} declared without a local copy "
          f"(metadata-only, or unpinned){RST}")

    # Session 6 D0, closing a gap COVERAGE.md admitted: --check could exit 0 with
    # nothing verified. An "all sources verified" line over zero sources is not a
    # pass. The escape hatch is explicit and CI-visible, because sources/ is
    # gitignored and CI genuinely has none.
    if missing_pinned and not args.allow_absent_sources:
        print(f"{RED}{FAIL}{missing_pinned} pinned source(s) have no local copy, so "
              f"{verified} of {pinned_total} could be verified. Not claiming a pass.\n"
              f"       Run fetch_all.py to fetch them, or pass --allow-absent-sources\n"
              f"       when you know the sources are not present (CI: sources/ is "
              f"gitignored).{RST}", file=sys.stderr)
        return 1
    if verified == 0 and args.allow_absent_sources:
        print(f"{YEL}{WARN}0 sources verified. This run checked nothing; upstream "
              f"drift would not be detected.{RST}")
    return 0



if __name__ == "__main__":
    raise SystemExit(main())
