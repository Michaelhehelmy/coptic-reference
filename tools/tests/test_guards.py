# tools/tests/test_guards.py — the guards must be able to FAIL.
#
# A licence gate nobody has watched reject anything is decoration. Every test
# here is a negative: it asserts a specific violation is caught, and by which
# gate. CI runs this as its own job (guards_can_fail) so that weakening
# nc_guard.py to the point of accepting NC content turns the build red even
# though the clean nc_guard job stays green.
#
# The last group is different in kind: those tests do not feed the guards bad
# data, they check that the two files which must agree — nc_guard.py's allowlist
# and entry.schema.json's source enums — have not drifted apart. That drift is
# not hypothetical; it happened during Session 2 and is recorded in DECISIONS.md.
#
# LICENCE: project code, Apache-2.0.
from __future__ import annotations

import csv
import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "validate"))

import licence_guard  # noqa: E402
import nc_guard  # noqa: E402

# Session 7 C4: the shipped manifest is LICENSES.csv.gz. Resolve the form once,
# here, so every fixture below reads real bytes instead of a FileNotFoundError.
def _repo_licences() -> pathlib.Path:
    p = ROOT / "data" / "dist" / "provenance" / "LICENSES.csv"
    return p if p.is_file() else p.with_name("LICENSES.csv.gz")


def _repo_licences_bytes() -> bytes:
    p = _repo_licences()
    raw = p.read_bytes()
    if p.name.endswith(".gz"):
        import gzip as _g
        raw = _g.decompress(raw)
    return raw


# ── helpers ──────────────────────────────────────────────────────────────────

def _shard(entries: list[dict]) -> dict:
    return {"shard": "t", "entries": entries}


def _entry(eid: str, source: str, *, licence: str | None = None,
           attribution: dict | None = None) -> dict:
    lic = licence if licence is not None else nc_guard.ALLOWED_SOURCES.get(source, "UNKNOWN")
    e = {
        "id": eid,
        "lemma": "ⲧⲉⲛⲟⲩ",
        "glosses": [{"text": "now", "lang": "en", "source": source, "rank": 1}],
        "sources": [{"id": source, "licence": lic}],
        "attributions": [attribution or {
            "field": "glosses", "source": source, "licence": lic, "changes": "none",
        }],
    }
    return e


@pytest.fixture()
def dist(tmp_path: pathlib.Path) -> pathlib.Path:
    """A dist with a real (tiny) dataset, NOT just a licences file.

    Session 5 made the shared shard reader fail closed, so a `dist/` with no
    shards is now a hard failure. These fixtures deliberately had none -- they
    only cared about the licence manifest -- so fail-closed fired first and every
    licence assertion below was masked by a shardio error about missing shards.
    The guards were right and the fixtures were wrong: a licence check needs a
    dataset to check the licences OF.
    """
    d = tmp_path / "dist"
    (d / "dict").mkdir(parents=True)
    (d / "provenance").mkdir(parents=True)
    (d / "provenance" / "LICENSES.csv").write_bytes(_repo_licences_bytes())
    # One allowlisted, licensed entry, so the licence/NC checks have something to
    # read. Written through shardio so it is a real shard in the shipped format.
    sys.path.insert(0, str(ROOT / "tools"))
    import shardio as _shardio
    _shardio.write_shard(d / "dict" / "shard-000.json.gz",
                         {"schema": "coptic-reference/dict-shard/1",
                          "shard": 0, "count": 1, "entries": [_entry("C1", "CCL")]})
    return d


def _write(dist: pathlib.Path, entries: list[dict], name: str = "shard-t.json") -> None:
    (dist / "dict" / name).write_text(
        json.dumps(_shard(entries), ensure_ascii=False), encoding="utf-8")


def _nc(dist: pathlib.Path, content: pathlib.Path | None = None) -> None:
    nc_guard.check(dist, content if content is not None else ROOT / "content")


def _lic(dist: pathlib.Path) -> None:
    licence_guard.check(dist, dist / "provenance" / "LICENSES.csv")


# NCGuardError and LicenceGuardError subclass SystemExit (v4 §9 convention), so
# these must catch SystemExit explicitly — `except Exception` will NOT work.
def _fails(fn, *a, **kw) -> str:
    with pytest.raises(SystemExit):
        fn(*a, **kw)
    return ""


# ── the allowlist admits only what it lists ──────────────────────────────────

def test_clean_dataset_passes(dist):
    _write(dist, [_entry("C5047", "CCL"), _entry("C5048", "Kaikki")])
    _nc(dist)


def test_every_allowlisted_source_is_accepted(dist):
    """Each id on the allowlist must actually survive the guard. A typo in
    ALLOWED_SOURCES would otherwise only show up at ingest time."""
    entries = [_entry(f"E{i}", sid) for i, sid in enumerate(sorted(nc_guard.ALLOWED_SOURCES))]
    _write(dist, entries)
    _nc(dist)


def test_non_allowlisted_source_fails(dist, capsys):
    _write(dist, [_entry("C5047", "CCL"), _entry("C9999", "SomeCorpusWeJustFound")])
    with pytest.raises(SystemExit):
        _nc(dist)
    err = capsys.readouterr().err
    assert "SomeCorpusWeJustFound" in err
    assert "C9999" in err, "the error must name the offending entry"
    assert "shard-t.json" in err, "the error must name the offending file"


def test_nc_source_fails(dist, capsys):
    _write(dist, [_entry("C5047", "Manley2019")])
    with pytest.raises(SystemExit):
        _nc(dist)
    err = capsys.readouterr().err
    assert "Manley2019" in err and "C5047" in err


def test_nc_source_with_a_PERMITTED_licence_string_still_fails(dist, capsys):
    """The dangerous case. A scrape that kept a CC BY-SA header while carrying
    NC text passes every schema check; only the allowlist knows better."""
    e = _entry("C5047", "Manley2019", licence="CC-BY-SA-4.0")
    e["attributions"][0]["licence"] = "CC-BY-SA-4.0"
    _write(dist, [e])
    with pytest.raises(SystemExit):
        _nc(dist)
    assert "Manley2019" in capsys.readouterr().err


def test_unknown_source_named_only_in_attributions_fails(dist, capsys):
    """attributions[].source is a free string per v4 §8.2, so nc_guard is the
    ONLY control on it."""
    e = _entry("C5047", "CCL")
    e["attributions"][0]["source"] = "MysterySource"
    _write(dist, [e])
    with pytest.raises(SystemExit):
        _nc(dist)
    assert "MysterySource" in capsys.readouterr().err


def test_allowlist_and_contra_list_must_not_overlap(monkeypatch):
    """Check 3. Self-inconsistency in the guard's own tables is a violation."""
    monkeypatch.setitem(nc_guard.ALLOWED_SOURCES, "Manley2019", "CC-BY-NC-4.0")
    with pytest.raises(SystemExit):
        nc_guard.check(ROOT / "data" / "dist", ROOT / "content")


def test_nc_licence_on_an_allowlisted_id_is_rejected(monkeypatch, capsys):
    """Belt-and-braces: a source allowlisted WITH an NC licence is still a bug."""
    monkeypatch.setitem(nc_guard.ALLOWED_SOURCES, "Sneaky", "CC-BY-NC-4.0")
    with pytest.raises(SystemExit):
        nc_guard.check(ROOT / "data" / "dist", ROOT / "content")
    assert "Sneaky" in capsys.readouterr().err


def test_unparseable_shard_fails_closed(dist):
    """A shard we cannot read cannot be cleared. Skipping it would be fail-open."""
    (dist / "dict" / "shard-broken.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(SystemExit):
        _nc(dist)


def test_non_dict_shard_is_ignored_not_crashed(dist):
    (dist / "dict" / "shard-list.json").write_text("[1,2,3]", encoding="utf-8")
    _nc(dist)  # must not raise


# ── check 2: NC ids outside content/nc/ ─────────────────────────────────────

def test_nc_reference_in_content_outside_nc_dir_fails(dist, tmp_path, capsys):
    content = tmp_path / "content"
    (content / "lessons").mkdir(parents=True)
    (content / "lessons" / "l1.md").write_text("See Manley2019 ch. 2.", encoding="utf-8")
    with pytest.raises(SystemExit):
        nc_guard.check(dist, content)   # Session 6 D0: a real dataset, not a
                                  # path that does not exist. nc_guard
                                  # now FAILS on an absent dataset, which
                                  # is correct -- these tests are about
                                  # the content half, so give it content
                                  # to check alongside.
    assert "Manley2019" in capsys.readouterr().err


def test_nc_reference_under_content_nc_is_permitted(dist, tmp_path):
    content = tmp_path / "content"
    (content / "nc").mkdir(parents=True)
    (content / "nc" / "notes.md").write_text("See Manley2019 ch. 2.", encoding="utf-8")
    nc_guard.check(dist, content)   # Session 6 D0: a real dataset, not a
                                  # path that does not exist. nc_guard
                                  # now FAILS on an absent dataset, which
                                  # is correct -- these tests are about
                                  # the content half, so give it content
                                  # to check alongside.  # must not raise


def test_a_directory_merely_containing_nc_is_not_treated_as_nc_content(dist, tmp_path, capsys):
    """v4 §9's sample skipped any path containing the substring 'nc/'. A
    directory like content/lincoln/ would be wrongly skipped, letting an NC
    reference through. Fixed in S2-B1; this pins the fix."""
    content = tmp_path / "content"
    (content / "lincoln").mkdir(parents=True)
    (content / "lincoln" / "notes.md").write_text("See Manley2019.", encoding="utf-8")
    with pytest.raises(SystemExit):
        nc_guard.check(dist, content)   # Session 6 D0: a real dataset, not a
                                  # path that does not exist. nc_guard
                                  # now FAILS on an absent dataset, which
                                  # is correct -- these tests are about
                                  # the content half, so give it content
                                  # to check alongside.
    assert "Manley2019" in capsys.readouterr().err


def test_a_file_named_nc_md_is_not_itself_the_nc_directory(dist, tmp_path, capsys):
    content = tmp_path / "content"
    content.mkdir(parents=True)
    (content / "nc.md").write_text("See Manley2019.", encoding="utf-8")
    with pytest.raises(SystemExit):
        nc_guard.check(dist, content)   # Session 6 D0: a real dataset, not a
                                  # path that does not exist. nc_guard
                                  # now FAILS on an absent dataset, which
                                  # is correct -- these tests are about
                                  # the content half, so give it content
                                  # to check alongside.


# ── licence_guard ────────────────────────────────────────────────────────────

def test_licence_guard_clean(dist):
    _write(dist, [_entry("C5047", "CCL")])
    _lic(dist)


def test_missing_licences_row_fails(dist, capsys):
    p = dist / "provenance" / "LICENSES.csv"
    kept = [l for l in p.read_text(encoding="utf-8").split("\n")
            if not l.startswith("CDO-API,")]
    p.write_text("\n".join(kept), encoding="utf-8")
    with pytest.raises(SystemExit):
        _lic(dist)
    err = capsys.readouterr().err
    assert "CDO-API" in err and "no row" in err


@pytest.mark.parametrize("bad", ["UNKNOWN", "UNVERIFIED", "TBD", "", "n/a"])
def test_undetermined_licence_on_a_redistributable_row_fails(dist, capsys, bad):
    p = dist / "provenance" / "LICENSES.csv"
    rows = list(csv.DictReader(p.read_text(encoding="utf-8").splitlines()))
    for r in rows:
        if r["id"] == "Crum":
            r["licence"] = bad
    with p.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with pytest.raises(SystemExit):
        _lic(dist)
    assert "Crum" in capsys.readouterr().err


def test_unverified_is_allowed_on_an_nc_only_row(dist):
    """The five unverified NC sources legitimately say UNVERIFIED. Rejecting
    that would pressure someone to invent a licence — see S2-A3."""
    p = dist / "provenance" / "LICENSES.csv"
    rows = list(csv.DictReader(p.read_text(encoding="utf-8").splitlines()))
    # Exactly the NC contra-list. A scope test is not equivalent: UD_Bohairic is
    # restricted away from data/dist too (Session 4 Q2 reserved it) but it is
    # CC BY 4.0 and belongs to neither list, so it must not be swept in here.
    nc_rows = [r for r in rows if r["id"] in nc_guard.NC_ONLY_SOURCES]
    assert nc_rows, "expected some nc-only rows to exist"
    # Not ALL of them are UNVERIFIED: Manley2019's licence is known to be
    # CC BY-NC 4.0, which is a real verdict. The point is that an *undetermined*
    # licence is tolerated here, and that a determined one is equally fine.
    undetermined = [r for r in nc_rows if r["licence"] == "UNVERIFIED"]
    assert len(undetermined) >= 4, (
        "expected the genuinely unverified NC sources to say UNVERIFIED; got "
        f"{[r['id'] for r in nc_rows]}"
    )
    assert all(r["licence"] in ("UNVERIFIED", "CC-BY-NC-4.0") for r in nc_rows)
    _lic(dist)  # must not raise


def test_allowlist_and_manifest_licence_drift_fails(dist, monkeypatch, capsys):
    """The two files must not disagree about a licence (v4 §9's PR-step rule)."""
    monkeypatch.setitem(nc_guard.ALLOWED_SOURCES, "TLA", "CC-BY-SA-4.0")
    with pytest.raises(SystemExit):
        _lic(dist)
    assert "TLA" in capsys.readouterr().err


def test_source_claiming_dist_scope_without_being_allowlisted_fails(dist, capsys):
    p = dist / "provenance" / "LICENSES.csv"
    p.write_text(p.read_text(encoding="utf-8").rstrip("\n") + "\n"
                 "Sneaky,CC-BY-SA-4.0,Unlisted,x,url,data/dist,2026-10-03,row only\n",
                 encoding="utf-8")
    with pytest.raises(SystemExit):
        _lic(dist)
    assert "Sneaky" in capsys.readouterr().err


def test_dataset_source_with_no_licences_row_fails(dist, capsys):
    """An id used in the dataset but absent from the manifest. It cannot be
    allowlisted either (nc_guard would have caught it), so this proves the
    manifest is not merely a copy of the allowlist."""
    _write(dist, [_entry("C5047", "CCL")])
    p = dist / "provenance" / "LICENSES.csv"
    p.write_text(p.read_text(encoding="utf-8").replace("CCL,", "ZZ_not_ccl,"),
                 encoding="utf-8")
    with pytest.raises(SystemExit):
        _lic(dist)
    assert "CCL" in capsys.readouterr().err


def test_duplicate_id_in_the_manifest_fails(dist, capsys):
    p = dist / "provenance" / "LICENSES.csv"
    p.write_text(p.read_text(encoding="utf-8")
                 + "CCL,CC-BY-SA-4.0,Duplicate,x,url,data/dist,2026-10-03,second row\n",
                 encoding="utf-8")
    with pytest.raises(SystemExit):
        _lic(dist)
    assert "duplicate" in capsys.readouterr().err.lower()


def test_missing_manifest_is_a_failure_not_a_skip(tmp_path):
    with pytest.raises(SystemExit):
        licence_guard.check(tmp_path / "dist", tmp_path / "nope" / "LICENSES.csv")


def test_manifest_missing_a_required_column_fails(tmp_path):
    p = tmp_path / "LICENSES.csv"
    p.write_text("id,licence\nCCL,CC-BY-SA-4.0\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        licence_guard.check(tmp_path, p)


# ── DRIFT: nc_guard.py and entry.schema.json must agree on source ids ────────

def _schema() -> dict:
    return json.loads((ROOT / "schema" / "entry.schema.json").read_text(encoding="utf-8"))


def _source_enums(schema: dict) -> dict[str, list[str]]:
    p = schema["properties"]
    return {
        "glosses[].source": p["glosses"]["items"]["properties"]["source"]["enum"],
        "examples[].source": p["examples"]["items"]["properties"]["source"]["enum"],
        "etymology.source": p["etymology"]["properties"]["source"]["enum"],
    }


def test_no_schema_source_enum_contains_an_id_the_allowlist_rejects():
    """If the schema offers an id the allowlist rejects, nc_guard fails every
    entry that uses it. If the schema omits an id the allowlist permits, that
    source cannot be cited at all. Both are drift; both must be caught here."""
    allowed = set(nc_guard.ALLOWED_SOURCES) | {"MERGE"}
    for field, values in _source_enums(_schema()).items():
        extra = set(values) - allowed
        assert not extra, (
            f"schema {field} offers ids absent from ALLOWED_SOURCES: {sorted(extra)}. "
            f"nc_guard would reject any entry using them."
        )


def test_every_allowlisted_source_is_citable_in_glosses_and_examples():
    """Session 2 found Scriptorium_TT — the corpus of record — uncitable in an
    entry, because the enum had drifted to 6 of 14 ids (DECISIONS.md S2-B4)."""
    allowed = set(nc_guard.ALLOWED_SOURCES) | {"MERGE"}
    schema = _schema()
    enums = _source_enums(schema)
    for field in ("glosses[].source", "examples[].source"):
        missing = allowed - set(enums[field])
        assert not missing, f"schema {field} cannot cite {sorted(missing)}"


def test_attributions_source_is_deliberately_unconstrained():
    """v4 §8.2 makes attributions[].source a free string. That is intentional —
    but it means nc_guard is the primary control there, so the property must
    stay unconstrained rather than gaining a helpful-looking enum."""
    node = _schema()["properties"]["attributions"]["items"]["properties"]["source"]
    assert "enum" not in node, (
        "attributions[].source gained an enum; v4 §8.2 specifies a free string "
        "and nc_guard is the control that catches NC ids there."
    )


def test_merge_pseudo_source_is_allowlisted_and_documented():
    """v4 §8.2's worked example cites source "MERGE", which was missing from
    v4 §9's allowlist — so §8.2's own pattern failed §9's guard (S2-A5)."""
    assert "MERGE" in nc_guard.ALLOWED_SOURCES
    rows = licence_guard.load_licences(_repo_licences())
    assert "MERGE" in rows
    assert rows["MERGE"]["licence"] == nc_guard.ALLOWED_SOURCES["MERGE"]


# ── the harness itself ───────────────────────────────────────────────────────

def _dry_run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "merge" / "dry_run.py"), *args],
        capture_output=True, text=True, cwd=ROOT)


def test_dry_run_clean_passes():
    r = _dry_run()
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PASS" in r.stdout


@pytest.mark.parametrize("kind,expect_stage", [
    ("nc", "stage 3"),
    ("unknown-source", "stage 3"),
    ("malformed", "stage 3"),
    ("nc-in-attribution", "stage 4"),
    ("undocumented", "stage 5"),
])
def test_dry_run_every_injection_fails_at_the_right_gate(kind, expect_stage):
    r = _dry_run("--inject", kind)
    assert r.returncode != 0, f"--inject {kind} did not fail:\n{r.stdout}"
    assert "FAIL at" in r.stdout
    assert expect_stage in r.stdout, (
        f"--inject {kind} should be caught at {expect_stage}, got:\n{r.stdout}"
    )


def test_dry_run_never_writes_to_the_real_data_dist():
    """A harness that wrote to the real dataset would be one invocation away
    from shipping the violation it exists to catch."""
    before = sorted(p.relative_to(ROOT).as_posix()
                    for p in (ROOT / "data" / "dist").rglob("*") if p.is_file())
    for kind in ("none", "nc", "nc-in-attribution", "undocumented"):
        _dry_run(*([] if kind == "none" else ["--inject", kind]))
    after = sorted(p.relative_to(ROOT).as_posix()
                   for p in (ROOT / "data" / "dist").rglob("*") if p.is_file())
    assert before == after


# ── Rule 12: one reader, one writer (Session 18 D0) ──────────────────────────

def _rug():
    sys.path.insert(0, str(ROOT / "tools" / "validate"))
    import reader_usage_guard as rug
    return rug


def test_reader_usage_guard_fails_on_a_direct_open_naming_the_file(tmp_path):
    """Negative control: a planted direct open() must fail naming the file."""
    rug = _rug()
    planted = tmp_path / "violator.py"
    planted.write_text(
        'import json\n'
        'blob = json.loads((d / "dict" / "index.json").read_text())\n',
        encoding="utf-8")
    hits = rug.check_python_file(planted)
    assert len(hits) == 1, f"expected exactly one hit, got {hits}"
    assert "violator.py" in hits[0] and "index.json" in hits[0]


def test_reader_usage_guard_passes_mediated_access(tmp_path):
    """Positive control: the guard must not fire on its own discipline."""
    rug = _rug()
    clean = tmp_path / "clean.py"
    clean.write_text(
        'blob = shardio.read_shard(d / "dict" / "shard-000.json.gz")\n'
        'safeio.write_verified(d / "dict" / "index.json", raw)\n',
        encoding="utf-8")
    assert rug.check_python_file(clean) == []


def test_reader_usage_guard_fails_on_raw_fetch(tmp_path):
    """Negative control (JS half): a raw fetch() of data must fail."""
    rug = _rug()
    planted = tmp_path / "reader.js"
    planted.write_text('const r = await fetch("data/quiz/bank.json");\n',
                       encoding="utf-8")
    hits = rug.check_js_file(planted)
    assert len(hits) == 1 and "reader.js" in hits[0]


def test_reader_usage_guard_is_clean_on_the_real_tree():
    """The shipped tree holds no direct opens of pipeline artefacts."""
    rug = _rug()
    assert rug.check() == []
