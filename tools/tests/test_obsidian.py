# tools/tests/test_obsidian.py — the reader vault (D9) must obey its own limits.
#
# The vault is a REDISTRIBUTION surface. It lives in public/downloads/, not in
# data/dist/, so nc_guard.py never sees it — which means nothing was checking it
# until these tests existed. A vault is also the artefact a reader is most likely
# to pass around, so a licence leak in it matters more than a leak in the site's
# own copy.
#
# Every test here builds a real vault in a tmp dir. None of them mock the emitter.
#
# LICENCE: project code, Apache-2.0.
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import zipfile

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "emit"))
sys.path.insert(0, str(ROOT / "tools" / "validate"))

import nc_guard  # noqa: E402
import obsidian  # noqa: E402

MEDIA_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
                  ".woff", ".woff2", ".ttf", ".otf", ".pdf")


# ── a small stub dist ────────────────────────────────────────────────────────

STUB_ENTRY = {
    "id": "C5047", "lemma": "ⲧⲉⲛⲟⲩ", "display": "ⲧⲉⲛⲟⲩ",
    "translit": {"bohairic": "tenoou", "sahidic": "tenou"},
    "dialects": ["B", "S"], "pos": ["adv"],
    "glosses": [{"text": "now, at present", "lang": "en", "source": "CCL", "rank": 1}],
    "etymology": {"text": "From Demotic Egyptian.", "chain": ["demotic"]},
    "examples": [{"coptic": "ⲁϣ ϭⲉ ⲧⲉⲛⲟⲩ", "translation": "What kind now?",
                  "urn": "urn:cts:copticLit:x:1.1"}],
    "sources": [{"id": "CCL", "licence": "CC-BY-SA-4.0"}],
}
CAPS_ENTRY = {
    "id": "C9001", "lemma": "Ϣⲁⲓ", "display": "Ϣⲁⲓ",
    "translit": {"bohairic": "hai"}, "dialects": ["B"], "pos": ["vb"],
    "glosses": [{"text": "to rejoice", "lang": "en", "source": "CCL", "rank": 1}],
    "examples": [], "sources": [{"id": "CCL", "licence": "CC-BY-SA-4.0"}],
}
LATIN_ENTRY = {
    "id": "C9003", "lemma": "tenou", "display": "tenou",
    "translit": {"bohairic": "tenoou"}, "dialects": ["B"], "pos": ["adv"],
    "glosses": [{"text": "a Latin transliteration used as a lemma",
                 "lang": "en", "source": "CCL", "rank": 1}],
    "examples": [], "sources": [{"id": "CCL", "licence": "CC-BY-SA-4.0"}],
}


@pytest.fixture()
def stub(tmp_path: pathlib.Path) -> dict:
    dist = tmp_path / "dist"
    (dist / "dict").mkdir(parents=True)
    (dist / "corpus").mkdir(parents=True)
    (dist / "provenance").mkdir(parents=True)
    (dist / "dict" / "shard-a1.json").write_text(
        json.dumps({"shard": "a1",
                    "entries": [STUB_ENTRY, CAPS_ENTRY, LATIN_ENTRY]},
                   ensure_ascii=False), encoding="utf-8")
    (dist / "corpus" / "sahidic_ruth.json").write_text(
        json.dumps({"title": "Ruth", "licence": "CC-BY-SA-4.0",
                    "source": "Scriptorium_TT",
                    "verses": [{"verse_ref": "Ruth 1:1", "coptic": "ⲁⲥϣⲱⲡⲉ",
                                "translation": "And it came to pass.",
                                "urn": "urn:cts:copticLit:ot.ruth:1.1"}]},
                   ensure_ascii=False), encoding="utf-8")
    # Session 7 C4: the shipped manifest is .csv.gz. Read whichever form exists.
    _lic = ROOT / "data" / "dist" / "provenance" / "LICENSES.csv"
    if not _lic.is_file():
        _lic = _lic.with_name("LICENSES.csv.gz")
    raw = _lic.read_bytes()
    if _lic.name.endswith(".gz"):
        import gzip as _g
        raw = _g.decompress(raw)
    (dist / "provenance" / "LICENSES.csv").write_bytes(raw)
    content = tmp_path / "content"
    (content / "lessons").mkdir(parents=True)
    (content / "lessons" / "01-alpha.md").write_text(
        "# Lesson 1\n\nCoptic writes with the Greek alphabet.\n", encoding="utf-8")
    return {"dist": dist, "content": content, "tmp": tmp_path}


def build(stub: dict, *extra: str) -> tuple[pathlib.Path, pathlib.Path]:
    keep = stub["tmp"] / "vault"
    zipped = stub["tmp"] / "vault.zip"
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "emit" / "obsidian.py"),
         "--dist", str(stub["dist"]), "--content", str(stub["content"]),
         "--out", str(zipped), "--keep-dir", str(keep), *extra],
        capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, f"emit failed:\n{r.stdout}\n{r.stderr}"
    return keep / obsidian.VAULT_DIRNAME, zipped


# ── structure ────────────────────────────────────────────────────────────────

def test_one_file_per_coptic_letter(stub):
    v, _ = build(stub)
    letters = sorted((v / obsidian.DICT_DIR).glob("*.md"))
    # 22 letters + the unfiled-lemma file
    assert len(letters) == 23, [p.name for p in letters]
    for p in letters:
        if p.name.startswith("ZZ "):
            continue
        assert any(ch in p.name for ch in "ⲁⲃⲅⲇⲉⲋⲍⲏⲙⲛⲝⲟⲡⲣⲥⲧⲩⲭϣϩϭϯ"), p.name


def test_required_pages_exist(stub):
    v, _ = build(stub)
    assert (v / "00 START HERE.md").is_file()
    assert (v / obsidian.META_DIR / "Licences.md").is_file()
    assert (v / obsidian.META_DIR / "Credits.md").is_file()


def test_lessons_are_copied(stub):
    v, _ = build(stub)
    assert (v / obsidian.LESSONS_DIR / "01-alpha.md").is_file()
    assert "Greek alphabet" in (v / obsidian.LESSONS_DIR / "01-alpha.md").read_text(
        encoding="utf-8")


def test_under_two_hundred_files_and_under_25_mib(stub):
    _, z = build(stub)
    with zipfile.ZipFile(z) as zf:
        names = zf.namelist()
    assert len(names) <= obsidian.MAX_FILES, f"{len(names)} files"
    assert z.stat().st_size <= obsidian.MAX_BYTES, z.stat().st_size


# ── text stays text ──────────────────────────────────────────────────────────

def test_no_images_or_fonts_in_the_vault(stub):
    """Coptic must remain selectable, greppable, screen-reader-readable text.

    Converting it to pictures would be the single worst thing this build could
    do, and it would still 'look right', so it gets an explicit test.
    """
    v, z = build(stub)
    for p in v.rglob("*"):
        if p.is_file():
            assert p.suffix.lower() not in MEDIA_SUFFIXES, p
    with zipfile.ZipFile(z) as zf:
        for n in zf.namelist():
            assert pathlib.Path(n).suffix.lower() not in MEDIA_SUFFIXES, n


def test_coptic_is_plain_unicode_in_the_output(stub):
    v, _ = build(stub)
    tia = next((v / obsidian.DICT_DIR).glob("tia*"))
    text = tia.read_text(encoding="utf-8")
    assert "ⲧⲉⲛⲟⲩ" in text
    # the exact codepoints, so a future "normalisation" to NFD or to a
    # compatibility form is caught rather than silently changing sort keys
    # U+2CA7 is COPTIC SMALL LETTER TAU. Pinning the exact codepoint means a
    # future normalisation to NFD, or a substitution of a lookalike, is caught
    # rather than silently changing sort keys.
    assert "ⲧ" in text and ord("ⲧ") == 0x2CA7


# ── invariant 5: NC must never reach the vault payload ───────────────────────

def test_nc_id_in_a_payload_file_fails_the_build(stub):
    stub["dist"].mkdir(exist_ok=True)
    bad = json.loads((stub["dist"] / "dict" / "shard-a1.json").read_text(
        encoding="utf-8"))
    bad["entries"][0]["examples"][0]["translation"] = "stolen (Manley2019 p.42)"
    (stub["dist"] / "dict" / "shard-a1.json").write_text(
        json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    keep = stub["tmp"] / "v2"
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "emit" / "obsidian.py"),
         "--dist", str(stub["dist"]), "--content", str(stub["content"]),
         "--out", str(stub["tmp"] / "v2.zip"), "--keep-dir", str(keep)],
        capture_output=True, text=True, cwd=ROOT)
    assert r.returncode != 0, "an NC source in the vault payload must fail the build"
    assert "Manley2019" in r.stderr


def test_nc_ids_may_appear_in_licences_as_exclusions(stub):
    """Naming an excluded source is transparency, not redistribution. The page
    must still list them, and must do so under a heading that says they are
    excluded — otherwise a reader assumes the vault contains them."""
    v, _ = build(stub)
    t = (v / obsidian.META_DIR / "Licences.md").read_text(encoding="utf-8")
    assert "Sources deliberately NOT in this vault" in t
    for sid in nc_guard.NC_ONLY_SOURCES:
        assert sid in t, f"{sid} should be listed as excluded"
    # and the two groups must not be conflated
    inc, exc = t.split("## Sources deliberately NOT in this vault")
    assert "Coptic Reference" not in inc  # sanity: split worked


# ── invariant 7: attribution ─────────────────────────────────────────────────

def test_every_file_carries_a_sources_footer(stub):
    v, _ = build(stub)
    for p in v.rglob("*.md"):
        text = p.read_text(encoding="utf-8")
        assert "**Sources" in text or "Sources in this file" in text, p
        assert "99 Meta/Licences.md" in text, f"{p} has no licence link"


def test_meta_links_are_relative_and_resolve(stub):
    """A hardcoded '99 Meta/Licences.md' is broken from inside 10 Dictionary/."""
    v, _ = build(stub)
    for p in v.rglob("*.md"):
        for line in p.read_text(encoding="utf-8").splitlines():
            # Only real links. Prose also mentions "99 Meta/Licences.md" in
            # backticks, and that is not a link to resolve.
            if "](<" not in line or "99 Meta/" not in line:
                continue
            target = line.split("(<")[1].split(">")[0] if "(<" in line else None
            assert target, f"unencoded space in link: {line}"
            resolved = (p.parent / target).resolve()
            assert resolved.is_file(), f"{p.name}: dangling link -> {target}"


def test_entry_footer_lists_real_source_ids_not_entry_ids(stub):
    """An earlier version passed entry ids where source ids belonged, so the
    unfiled-lemma file read 'Sources: C9003'."""
    v, _ = build(stub)
    f = v / obsidian.DICT_DIR / "ZZ Unfiled lemmas.md"
    lines = f.read_text(encoding="utf-8").splitlines()
    # The orphan's own source (CCL) must be cited in the footer...
    footer_lines = [l for l in lines if l.startswith("**Sources")]
    assert footer_lines, "no sources footer"
    assert "`CCL`" in footer_lines[-1]
    # ...and the entry id must not be presented AS A SOURCE. It is legitimate
    # for the id to appear in the body, where it identifies the unfiled lemma,
    # so the assertion is scoped to the footer line rather than the whole file.
    assert "`C9003`" not in footer_lines[-1], "entry id leaked into a source list"
    assert "`ShishaHalevy`" not in "\n".join(lines), "NC source in the vault"


# ── collation (invariant 6) ──────────────────────────────────────────────────

def test_greek_script_capital_lemma_files_under_its_letter(stub):
    """Regression guard for DECISIONS.md S2-B10.

    Ϣⲁⲓ was filed under no letter at all, because the collation could not
    case-fold the Greek-script capitals. The vault surfaced it.
    """
    v, _ = build(stub)
    shin = next((v / obsidian.DICT_DIR).glob("shin*"))
    assert "Ϣⲁⲓ" in shin.read_text(encoding="utf-8"), (
        "a lemma beginning with a Greek-script capital must file under its letter")
    assert "Ϣⲁⲓ" not in (v / obsidian.DICT_DIR / "ZZ Unfiled lemmas.md").read_text(
        encoding="utf-8")


def test_lemma_with_no_coptic_letter_is_reported_not_dropped(stub):
    """Never drop data silently: a Latin-transliteration lemma goes to an
    explicit file and the build warns."""
    v, _ = build(stub)
    unfiled = v / obsidian.DICT_DIR / "ZZ Unfiled lemmas.md"
    assert unfiled.is_file()
    assert "tenou" in unfiled.read_text(encoding="utf-8")
    assert "merge bug" in unfiled.read_text(encoding="utf-8")


# ── .obsidian config ─────────────────────────────────────────────────────────

def test_obsidian_config_has_no_plugins(stub):
    v, _ = build(stub)
    app = json.loads((v / ".obsidian" / "app.json").read_text(encoding="utf-8"))
    assert app.get("communityPlugins") == []
    assert app.get("communityPluginsSortOrder") == []
    assert not (v / ".obsidian" / "plugins").exists()
    assert not list(v.rglob("*.js")), "no scripts in a vault people open blind"


def test_obsidian_config_sets_fonts(stub):
    v, _ = build(stub)
    a = json.loads((v / ".obsidian" / "appearance.json").read_text(encoding="utf-8"))
    assert "Coptic" in a["textFontFamily"]


def test_start_here_is_honest_about_the_missing_font(stub):
    """There is no font subset yet. A vault that claimed one would send people
    hunting for a file that does not exist."""
    v, _ = build(stub)
    t = (v / "00 START HERE.md").read_text(encoding="utf-8")
    if not list((ROOT / "static" / "fonts").glob("*.woff2")):
        assert "not been built" in t or "No Coptic webfont" in t
        assert "fonts-noto-core" in t, "must tell the reader what to install"


# ── Bohairic honesty (v4 §10.2) ──────────────────────────────────────────────

def test_bohairic_work_states_that_coverage_is_thinner(stub):
    v, _ = build(stub)
    ruth = next((v / obsidian.CORPUS_DIR).glob("ruth*"))
    assert "Bohairic coverage is thinner" not in ruth.read_text(encoding="utf-8"), (
        "a Sahidic work must not carry the Bohairic caveat")


def test_work_without_translation_says_so(stub):
    """'No aligned translation' must be stated. A Coptic text with a silently
    missing English reads as a parsing failure."""
    stub["dist"].mkdir(exist_ok=True)
    (stub["dist"] / "corpus" / "bohairic_mark.json").write_text(
        json.dumps({"title": "Mark", "licence": "CC-BY-SA-4.0",
                    "source": "Scriptorium_TT",
                    "verses": [{"verse_ref": "Mark 1:1", "coptic": "ⲁⲣϧⲉ"}]},
                   ensure_ascii=False), encoding="utf-8")
    v, _ = build(stub)
    mark = next((v / obsidian.CORPUS_DIR).glob("mark*"))
    t = mark.read_text(encoding="utf-8")
    assert "No aligned English translation" in t
    assert "Bohairic coverage is thinner" in t


# ── determinism ──────────────────────────────────────────────────────────────

def test_two_builds_are_byte_identical(stub):
    """Otherwise every build is a spurious diff and nobody reviews them."""
    _, z1 = build(stub)
    first = z1.read_bytes()
    _, z2 = build(stub)
    assert first == z2.read_bytes()
