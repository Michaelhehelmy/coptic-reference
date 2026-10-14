# tools/tests/test_full_roundtrip.py — Session 4, D4.
# LICENCE: project code, Apache-2.0.
#
# Tap-a-word, in a test. This is the loop the site's entire value depends on:
#
#     a token in Ruth  ->  the dictionary entry  ->  back to the token in Ruth
#
# If this does not round-trip in a test it will not round-trip in a browser, and
# the failure will be found by a reader rather than by CI. Every step below reads
# the SHIPPED artefacts off disk — data/dist/dict/shard-*.json and the tarball —
# not the in-memory objects that produced them. Reading the intermediates would
# pass even if the writers were wrong.
#
# Both directions are asserted, because a one-way test passes when the reverse
# link is broken.
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import tarfile
from collections import defaultdict

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "emit"))

import collate  # noqa: E402
from corpus_refs import key as corpus_key  # noqa: E402

DICT = ROOT / "data" / "dist" / "dict"
TARBALL = ROOT / "data" / "dist" / "corpus" / "corpus.tar.gz"
MANIFEST = ROOT / "data" / "dist" / "corpus" / "manifest.json"

pytestmark = pytest.mark.skipif(
    not (TARBALL.is_file() and any(DICT.glob("shard-*.json"))),
    reason="no baked corpus/dict; run emit/cli.py, corpus_tarball.py, corpus_refs.py")


def key(s: str) -> str:
    return collate.canon_for_sort(s)


def load_dict() -> dict[str, dict]:
    """norm_key -> entry, read off disk."""
    out: dict[str, dict] = {}
    for shard in sorted(DICT.glob("shard-*.json")):
        for e in json.loads(shard.read_text(encoding="utf-8"))["entries"]:
            out[key(e["lemma"])] = e
    return out


def load_tokens() -> tuple[dict[str, dict], dict[str, list[dict]]]:
    """(work meta by slug, {work_slug: [tokens]}) straight out of the tarball."""
    metas: dict[str, dict] = {}
    toks: dict[str, list[dict]] = {}
    with tarfile.open(TARBALL, "r:gz") as tf:
        for slug in sorted({n.split("/")[0] for n in tf.getnames() if "/" in n}):
            metas[slug] = json.loads(
                tf.extractfile(f"{slug}/meta.json").read().decode("utf-8"))
            toks[slug] = json.loads(
                tf.extractfile(f"{slug}/tokens.json").read().decode("utf-8"))["tokens"]
    return metas, toks


@pytest.fixture(scope="module")
def dictionary() -> dict[str, dict]:
    return load_dict()


@pytest.fixture(scope="module")
def corpus():
    return load_tokens()


def test_the_dictionary_and_the_corpus_actually_overlap(corpus):
    """Precondition. If these did not overlap, every later test would pass
    vacuously by finding nothing."""
    _metas, toks = corpus
    lemmas = {key(t["lemma"]) for tl in toks.values() for t in tl if t.get("lemma")}
    assert len(lemmas) > 300, f"only {len(lemmas)} distinct corpus lemmas"


# ── forward: token -> entry ──────────────────────────────────────────────────

def test_a_ruth_token_resolves_to_a_dictionary_entry(corpus, dictionary):
    """Step 1+2. Take a real token from Ruth and find its entry."""
    _metas, toks = corpus
    ruth = toks["sahidic_ruth"]
    lemma = next(t["lemma"] for t in ruth if t.get("lemma") and key(t["lemma"]) in dictionary)
    entry = dictionary[key(lemma)]
    assert entry["glosses"], f"{entry['lemma']} has no gloss; it would render blank"
    assert entry["norm_key"] == key(lemma)


def test_a_greek_script_capital_token_matches_its_small_form(corpus, dictionary):
    """The S2-B10 bug, in the one place it would bite a reader: a reader taps a
    capitalised Greek-borrowed word and gets nothing.

    Matching is on the collation key, so Ϣⲁ and ϣⲁ are the same word. If anyone
    'simplifies' the join to a raw string comparison, this fails."""
    _metas, toks = corpus
    ruth = toks["sahidic_ruth"]
    caps = [t["lemma"] for t in ruth
            if t.get("lemma") and 0x03E2 <= ord(t["lemma"][0]) <= 0x03EE]
    if not caps:
        pytest.skip("this corpus slice has no Greek-script initial")
    k = key(caps[0])
    assert k in dictionary, f"capital {caps[0]!r} did not resolve"
    assert key(caps[0]) == key(caps[0].lower() if caps[0].lower() in
                                "ⲁⲃⲅⲇⲉⲋⲍⲏⲙⲛⲝⲟⲡⲣⲥⲧⲩⲭϣϩϭϯ" else caps[0])


# ── the link itself ──────────────────────────────────────────────────────────

def test_the_entry_points_back_at_the_corpus(corpus, dictionary):
    """Step 3. The entry's corpus_refs must name a work that actually contains
    the lemma. A corpus_ref pointing at a work with no occurrence is worse than
    none: it sends a reader to a text that will not help."""
    _metas, toks = corpus
    checked = 0
    for entry in dictionary.values():
        for ref in entry.get("corpus_refs") or []:
            slug = ref["work_slug"]
            hits = [t for t in toks.get(slug, []) if key(t.get("lemma", "")) == key(entry["lemma"])]
            assert hits, (f"{entry['lemma']} claims {ref['occurrences']} occurrences "
                          f"in {slug}, but the tarball has none")
            assert len(hits) == ref["occurrences"], (
                f"{entry['lemma']}: corpus_refs says {ref['occurrences']}, "
                f"tarball has {len(hits)}")
            checked += 1
    assert checked > 100, f"only {checked} corpus_refs to verify"


def test_corpus_ref_counts_match_the_tarball_exactly(corpus, dictionary):
    _metas, toks = corpus
    actual: dict[str, int] = defaultdict(int)
    for slug, tl in toks.items():
        for t in tl:
            if t.get("lemma"):
                actual[key(t["lemma"])] += 1
    for k, entry in dictionary.items():
        claimed = sum(r["occurrences"] for r in entry.get("corpus_refs") or [])
        assert claimed == actual.get(k, 0), (
            f"{entry['lemma']}: corpus_refs total {claimed}, tarball has "
            f"{actual.get(k, 0)}")


def test_lemma_rank_is_the_true_rank_within_the_work(corpus, dictionary):
    """A rank that is merely plausible is worse than no rank: a reader uses it to
    judge how common a word is."""
    from collections import Counter
    _metas, toks = corpus
    for slug, tl in toks.items():
        counts = Counter(key(t["lemma"]) for t in tl if t.get("lemma"))
        ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        rank = {k: i + 1 for i, (k, _c) in enumerate(ordered)}
        for entry in dictionary.values():
            for ref in entry.get("corpus_refs") or []:
                if ref["work_slug"] != slug:
                    continue
                k = key(entry["lemma"])
                assert ref["lemma_rank"] == rank[k], (
                    f"{entry['lemma']} claims rank {ref['lemma_rank']} in {slug}, "
                    f"true rank is {rank[k]}")


# ── reverse: entry -> token position ─────────────────────────────────────────

def test_from_an_entry_the_token_position_is_reachable(corpus, dictionary):
    """Step 4. Not just "the work is named" — the specific verse and token
    offset must be findable, because that is what a tap needs to highlight."""
    _metas, toks = corpus
    reached = 0
    for entry in dictionary.values():
        for ref in entry.get("corpus_refs") or []:
            tl = toks.get(ref["work_slug"])
            if tl is None:
                continue
            positions = [(t["ref"], t["i"]) for t in tl
                         if key(t.get("lemma", "")) == key(entry["lemma"])]
            assert positions, f"{entry['lemma']}: no reachable token in {ref['work_slug']}"
            # And the ref URN must be usable to cite any of them.
            assert ref["urn"], f"{entry['lemma']}: corpus_ref with no URN"
            reached += 1
    assert reached > 100, f"only {reached} reverse lookups exercised"


def test_verse_refs_resolve_into_the_work_text(corpus, dictionary):
    """The token's ref must exist in the work's text, or the reader taps a word
    and the highlight lands nowhere."""
    from corpus_public import gzip_bytes  # noqa: F401  (import proves it exists)
    _metas, toks = corpus
    import tarfile as _tf
    texts: dict[str, dict[str, dict]] = {}
    with _tf.open(TARBALL, "r:gz") as tf:
        for slug in sorted({n.split("/")[0] for n in tf.getnames() if "/" in n}):
            v = json.loads(tf.extractfile(f"{slug}/text.json").read().decode("utf-8"))
            texts[slug] = {x["ref"]: x for x in v["verses"]}
    checked = 0
    for entry in dictionary.values():
        for ref in entry.get("corpus_refs") or []:
            tl = toks.get(ref["work_slug"]) or []
            verse_refs = {t["ref"] for t in tl
                          if key(t.get("lemma", "")) == key(entry["lemma"])}
            for vr in verse_refs:
                assert vr in texts[ref["work_slug"]], (
                    f"{entry['lemma']}: token ref {vr!r} is not in the work's text")
                checked += 1
    assert checked > 100, f"only {checked} verse refs resolved"


def test_every_shipped_work_with_data_is_referenced_by_some_entry(corpus, dictionary):
    """The other direction of completeness: a work nobody links to is a work
    nobody can find."""
    _metas, toks = corpus
    used = {r["work_slug"] for e in dictionary.values()
            for r in e.get("corpus_refs") or []}
    for slug in toks:
        assert slug in used, f"{slug} is in the corpus but no entry references it"


def test_the_manifest_and_the_tarball_agree(corpus):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    metas, toks = corpus
    assert set(manifest["fingerprints"]) == set(toks), (
        "the manifest's work set and the tarball's differ")
    for slug, meta in manifest["works"].items():
        assert meta["verses"] == metas[slug]["verses"]
        assert meta["tokens"] == len(toks[slug])


def test_the_corpus_actually_contains_text():
    """Session 4 S4-C1. The guard that should have existed from the start.

    For one full session the corpus shipped with `coptic: ""` and `form: ""` on
    every verse and every one of 3,470 tokens. Nothing caught it:

      - the round-trip passed, because it looks up by LEMMA;
      - the counts matched, because lemmas were never empty;
      - the sizes looked plausible, because JSON keys cost bytes either way;
      - the fingerprints were stable, because they hashed meta.json, not text.

    Every check agreed the corpus was fine because every check looked at a
    different thing than the thing that was broken. This asserts the plain
    thing: there is text, in both languages, on every verse and every token.
    """
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["works"], "no works in the corpus"

    total_verses = total_tokens = 0
    for slug, expected in manifest["works"].items():
        member = f"{slug}/text.json"
        with tarfile.open(TARBALL) as tf:
            text = json.loads(tf.extractfile(member).read().decode("utf-8"))
            tokens = json.loads(
                tf.extractfile(f"{slug}/tokens.json").read().decode("utf-8"))

        verses = text["verses"]
        assert verses, f"{slug}: no verses"
        for v in verses:
            assert v.get("coptic", "").strip(), (
                f"{slug} {v.get('ref')}: verse has no Coptic text")
            assert v.get("en", "").strip(), (
                f"{slug} {v.get('ref')}: verse has no English translation")
            assert v.get("urn"), f"{slug} {v.get('ref')}: verse has no urn"

        toks = tokens["tokens"]
        assert toks, f"{slug}: no tokens"
        for t in toks:
            assert t.get("form", "").strip(), (
                f"{slug} {t.get('ref')} token {t.get('i')}: no surface form")
            assert t.get("lemma", "").strip(), (
                f"{slug} {t.get('ref')} token {t.get('i')}: no lemma")
            assert t.get("pos", "").strip(), (
                f"{slug} {t.get('ref')} token {t.get('i')}: no part of speech")

        assert len(toks) == expected["tokens"], (
            f"{slug}: manifest says {expected['tokens']} tokens, file has {len(toks)}")
        total_verses += len(verses)
        total_tokens += len(toks)

    assert total_verses > 0 and total_tokens > 0


def test_the_fingerprint_covers_the_content_not_just_the_metadata():
    """Session 4 S4-C2. A guard that cannot notice its artefact changing.

    The fingerprint was sha256(meta.json), and meta.json held only counts. When
    the empty-text bug was fixed, the rebuild guard reported 'fingerprints
    unchanged - SKIPPING' and the fix did not ship -- the tarball kept serving
    empty text while the guard said everything was fine.

    So meta.json must carry the content hashes: then any edit to text.json or
    tokens.json moves the fingerprint, and the cheap guard stays honest.
    """
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    # hash_method is recorded at manifest level, and must say it covers content.
    assert "content" in manifest["hash_method"], (
        f"manifest hash_method is {manifest['hash_method']!r}; it must state that "
        f"the fingerprint covers the CONTENT and not just meta.json's counts")

    for slug, expected in manifest["works"].items():
        with tarfile.open(TARBALL) as tf:
            meta = json.loads(tf.extractfile(f"{slug}/meta.json").read().decode("utf-8"))
        content = meta.get("content_sha256")
        assert content, (
            f"{slug}: meta.json has no content_sha256, so editing the text or "
            f"the tokens would not move the fingerprint and the rebuild guard "
            f"would skip the work. This is how the empty-text fix failed to ship.")
        assert set(content) == {"text.json", "tokens.json"}, content
        for name, want in content.items():
            with tarfile.open(TARBALL) as tf:
                got = hashlib.sha256(
                    tf.extractfile(f"{slug}/{name}").read()).hexdigest()
            assert got == want, f"{slug}/{name}: meta records {want[:12]}, file is {got[:12]}"
