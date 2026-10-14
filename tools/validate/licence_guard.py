#!/usr/bin/env python3
"""tools/validate/licence_guard.py — every source has a licence verdict.

Companion to ``tools/validate/nc_guard.py``. The NC guard answers "is this
source permitted inside data/dist?"; this one answers "do we actually know what
licence it is?" A source can pass the allowlist and still be a problem if its
licence was never determined — and a licence recorded as ``UNKNOWN`` is the
mechanism by which CC BY-NC material gets waved through by accident.

Invariant 7: every artefact carries provenance. This gate is provenance's
enforcement point for source licensing.

Three checks (v4 §9, "One new required PR step"):

1. Every source id used in any shard's ``sources[]`` resolves to a row in
   ``data/dist/provenance/LICENSES.csv`` with a real licence.
2. Every id on ``ALLOWED_SOURCES`` has a row — so adding an id to the allowlist
   without documenting its licence fails here, not at audit time.
3. No row that can reach ``data/dist`` carries an undetermined licence.
4. (Added, DECISIONS.md S2-B2) No row claims ``data/dist`` scope unless its id
   is on ``ALLOWED_SOURCES``.

**Why check 3 is scoped rather than blanket.** The obvious reading of v4 §9's
"non-UNKNOWN" is "reject the token everywhere". That is wrong, and building it
that way immediately produced a false failure against our own manifest: five NC
sources (ShishaHalevy, LearnersGrammar, Younan2005, LoCPrimers, AnkiDeck) have
genuinely unverified licences, and the only way to satisfy a blanket rule would
be to *write down a licence nobody has determined*. A gate that pressures people
to invent provenance is worse than no gate — it converts an honest blank into a
confident lie.

So the rule is scoped by the ``scope`` column: a row that can reach ``data/dist``
must state a determined licence; a row restricted to ``content/nc`` may say
``UNVERIFIED``, which is accurate information and is visible in the file. What
is forbidden is an undetermined licence on anything redistributable. The
contra-list in ``nc_guard.py`` independently guarantees those five ids can never
reach the dataset, so this is defence in depth, not the primary control.

``UNKNOWN``, ``TBD``, ``TODO``, ``N/A`` and the empty string are all treated as
undetermined — a gate that accepts five spellings of "unknown" is not a gate.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import csv
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import safeio  # noqa: E402
from nc_guard import ALLOWED_SOURCES, _iter_shard_entries  # noqa: E402

DEFAULT_LICENCES = pathlib.Path("data/dist/provenance/LICENSES.csv")

# Values that mean "we have not determined this".
UNKNOWN_TOKENS: frozenset[str] = frozenset({
    "UNKNOWN", "UNVERIFIED", "TBD", "TODO", "", "-", "N/A", "NONE",
})

REQUIRED_COLUMNS: frozenset[str] = frozenset({"id", "licence", "name", "scope"})


def _reaches_dist(row: dict[str, str]) -> bool:
    """True if this row's declared scope puts it inside the redistributable set.

    Absence of a `scope` column value is treated as REACHING dist, not as
    safe. An unscoped row is an undetermined scope, and undetermined must fail
    closed like every other unknown here.
    """
    scope = (row.get("scope") or "").lower()
    if "data/dist" in scope:
        return True
    return not scope


class LicenceGuardError(SystemExit):
    """Raised on any violation. Subclasses SystemExit per v4 §9 convention.

    Note: a SystemExit's message is NOT printed when a caller catches the
    exception — Python only prints it at top level. This guard is imported by
    tools/merge/dry_run.py and by the tests, so every raise site must print
    first or the reason is invisible. Hence _fail() below.
    """


def _fail(message: str) -> None:
    """Print to stderr, then raise. Use for EVERY exit path in this module."""
    print(message, file=sys.stderr)
    raise LicenceGuardError(message)


def load_licences(path: pathlib.Path) -> dict[str, dict[str, str]]:
    """Parse the licence manifest. Accepts plain .csv or .csv.gz (Session 7 C4).

    Fails closed: an unreadable manifest is an error, never an empty dict. An
    empty dict here would mean "no source has a licence", which is the one answer
    this guard exists to prevent.
    """
    resolved = safeio.resolve_readable(path)
    if not resolved.is_file():
        _fail(
            f"[licence_guard] {path} not found. The licence manifest is not "
            f"optional: without it no source has a verdict (invariant 7)."
        )
    rows_list, used = safeio.read_csv_rows(resolved)
    if not rows_list:
        _fail(
            f"[licence_guard] {used}: no data rows. A licence manifest with no "
            f"rows is not a manifest."
        )
    missing = REQUIRED_COLUMNS - set(rows_list[0].keys())
    if missing:
        _fail(
            f"[licence_guard] {used}: missing required column(s) {sorted(missing)}; "
            f"found {sorted(rows_list[0].keys())}"
        )
    rows: dict[str, dict[str, str]] = {}
    for row in rows_list:
        rid = (row.get("id") or "").strip()
        if not rid:
            continue
        if rid in rows:
            _fail(
                f"[licence_guard] {used}: duplicate row for id {rid!r}. "
                f"Two verdicts for one source is one too many."
            )
        rows[rid] = {k: (v or "").strip() for k, v in row.items() if k}
    return rows


def check(dist: pathlib.Path, licences_path: pathlib.Path = DEFAULT_LICENCES) -> None:
    errors: list[str] = []
    rows = load_licences(licences_path)

    # ── 3. nothing that can reach data/dist may be undetermined ──────────────
    for rid, row in sorted(rows.items()):
        if not _reaches_dist(row):
            continue
        value = row.get("licence", "")
        if value.upper() in UNKNOWN_TOKENS:
            errors.append(
                f"{licences_path}: source {rid!r} has scope "
                f"{row.get('scope', '?')!r} but licence {value!r} — "
                f"undetermined. Determine the licence, or restrict the row to "
                f"content/nc and keep the id on NC_ONLY_SOURCES."
            )

    # ── 4. only an allowlisted id may claim data/dist scope ──────────────────
    for rid, row in sorted(rows.items()):
        if _reaches_dist(row) and rid not in ALLOWED_SOURCES:
            errors.append(
                f"{licences_path}: source {rid!r} claims scope "
                f"{row.get('scope', '?')!r} but is NOT in ALLOWED_SOURCES. A "
                f"licence row does not permit a source — only the reviewed "
                f"allowlist in tools/validate/nc_guard.py does."
            )

    # ── 2. every allowlisted id must be documented ───────────────────────────
    for sid, declared in sorted(ALLOWED_SOURCES.items()):
        if sid not in rows:
            errors.append(
                f"{licences_path}: ALLOWED_SOURCES id {sid!r} has no row. "
                f"Adding a source to the allowlist must also document its "
                f"licence (declared in nc_guard.py as {declared!r})."
            )
            continue
        recorded = rows[sid].get("licence", "")
        if recorded.upper() in UNKNOWN_TOKENS:
            errors.append(
                f"{licences_path}: ALLOWED_SOURCES id {sid!r} has an "
                f"undetermined licence ({recorded!r}) but is allowlisted."
            )
        elif recorded != declared:
            errors.append(
                f"{licences_path}: ALLOWED_SOURCES[{sid!r}] is "
                f"{declared!r} in nc_guard.py but {recorded!r} here. The "
                f"allowlist and the manifest must not drift apart."
            )

    # ── 1. every source used in the dataset must be documented ───────────────
    used_ids: dict[str, set[str]] = {}
    for shard, entry in _iter_shard_entries(dist):
        entry_id = entry.get("id", "<no id>")
        for s in entry.get("sources", []) or []:
            if isinstance(s, dict) and "id" in s:
                used_ids.setdefault(s["id"], set()).add(f"{shard.name}:{entry_id}")

    for sid, where in sorted(used_ids.items()):
        if sid not in rows:
            hint = ""
            if sid in ALLOWED_SOURCES:
                hint = " It IS on the allowlist but has no LICENSES.csv row."
            errors.append(
                f"{licences_path}: source {sid!r} used by "
                f"{', '.join(sorted(where))} has no row.{hint}"
            )

    if errors:
        for e in errors:
            print(f"[licence_guard] FAIL {e}", file=sys.stderr)
        raise LicenceGuardError(
            f"[licence_guard] {len(errors)} violation(s). Every source must "
            f"have a determined licence."
        )

    print(
        f"[licence_guard] OK — {len(rows)} rows in {licences_path}, "
        f"{len(ALLOWED_SOURCES)} allowlisted sources all documented and in "
        f"agreement with nc_guard.py, {len(used_ids)} distinct source ids used "
        f"in the dataset, 0 undetermined licences"
    )


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="every source has a licence verdict")
    ap.add_argument("--dist", default="data/dist", type=pathlib.Path)
    ap.add_argument("--licences", default=DEFAULT_LICENCES, type=pathlib.Path)
    args = ap.parse_args(argv)
    try:
        check(args.dist, args.licences)
    except LicenceGuardError as e:
        print(e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
