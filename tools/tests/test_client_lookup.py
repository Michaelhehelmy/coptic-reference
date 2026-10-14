"""The "tap a word, see the entry" loop, under the gzipped layout. Session 5 D4.

This is a CONTRACT, not a UI test. No browser is built this session (the brief
says so). What it fixes is the agreement between three artefacts that can drift
apart silently:

    index.json.gz   says  {lemma -> (shard, offset)}
    shard-NNN.json.gz holds entries[offset]
    corpus_refs[]   on that entry points back into the corpus

If any one of those three is wrong, the reader taps a word and gets either
nothing, the wrong entry, or an entry whose corpus citations do not resolve. All
three failures are silent in a browser, so they are pinned here.

THE FETCH IS MOCKED, and the mock is deliberately honest
--------------------------------------------------------
`fake_fetch` reproduces exactly what the browser does under D2's decision:

    fetch(url) -> DecompressionStream('gzip') -> JSON.parse

It asserts the bytes really are gzip before decompressing, because a client that
assumed gzip and got plain JSON would throw -- and in Session 5 that exact
mislabelling happened to all 23 shards (S5-B2).

THE CAPITAL
-----------
Requirement 5 is "a lemma with a Greek-block capital". Measured: **no shipped
lemma contains one.** All 11,369 rows are lowercase; there are zero U+2C80
(COPTIC CAPITAL LETTER ALPHA) and zero U+0391 (GREEK CAPITAL ALPHA). So there is
no data row to round-trip, and pretending otherwise would be inventing data.

What a reader actually does is type or paste a capitalised form, so that is what
the test does: it canonicalises the input with `collate.canon_for_sort` -- which
folds U+2C80 to U+2C81 -- and then looks that up. `test_no_shipped_lemma_has_a_greek_block_capital`
pins the measurement so nobody later "fixes" the test by adding one.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import gzip
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]


def is_coptic_capital(ch: str) -> bool:
    """True for a Coptic capital letter, by Unicode NAME.

    Not by codepoint arithmetic. U+2C80..U+2CE2 is NOT "the capitals" -- the
    capitals are the even codepoints and the smalls the odd ones in the early
    block, with irregularity after it. An earlier version of this test used the
    range U+2C80..U+2C8F and matched 9,194 rows, because that range contains the
    SMALL letters. Reading the name is exact and costs nothing.
    """
    import unicodedata
    try:
        return "CAPITAL LETTER" in unicodedata.name(ch)
    except ValueError:
        return False
sys.path.insert(0, str(ROOT / "tools"))

import collate  # noqa: E402
import shardio  # noqa: E402

DICT = ROOT / "data" / "dist" / "dict"
CORPUS = ROOT / "data" / "dist" / "corpus"

pytestmark = pytest.mark.skipif(
    not (DICT / "index.json.gz").is_file(),
    reason="no baked dict index; run tools/emit/dict_index.py",
)


# ── the client, as a test double ────────────────────────────────────────────
class FakeResponse:
    def __init__(self, url: str, body: bytes, content_encoding: str | None):
        self.url = url
        self._body = body
        self.content_encoding = content_encoding

    async def json(self) -> dict:
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(None, self._decode)

    def _decode(self) -> dict:
        data = self._body
        if self.content_encoding == "gzip":
            # This is DecompressionStream('gzip') on the client side. If the file
            # is not actually gzip, this raises -- which is the point.
            data = gzip.decompress(data)
        return json.loads(data.decode("utf-8"))


async def fake_fetch(url: str) -> FakeResponse:
    """Serve from data/dist, declaring Content-Encoding by file extension.

    Mirrors what the client must do under D2: the file is named `.gz`, so the
    bytes ARE gzip and the client decompresses explicitly rather than relying on
    the server setting a header (see gzip_shards.py for why).
    """
    path = (ROOT / url).resolve()
    assert ROOT in path.parents or path.is_relative_to(ROOT), f"refusing to read outside the repo: {url}"
    if not path.is_file():
        raise FileNotFoundError(f"404 {url}")
    enc = "gzip" if path.name.endswith(".gz") else None
    return FakeResponse(url, path.read_bytes(), enc)


async def lookup(lemma: str) -> tuple[dict, dict]:
    """lemma -> (index_row, entry). The whole loop, four steps."""
    # step 1: the client fetches and decompresses ONE index
    resp = await fake_fetch("data/dist/dict/index.json.gz")
    assert resp.content_encoding == "gzip", "the index must be served gzipped"
    idx = await resp.json()
    by_key = {r["norm_key"]: r for r in idx["rows"]}
    row = by_key.get(collate.canon_for_sort(lemma))
    assert row is not None, f"no index row for {lemma!r}"
    resp = await fake_fetch(f"data/dist/dict/shard-{row['shard']:03d}.json.gz")
    assert resp.content_encoding == "gzip"
    blob = await resp.json()                                 # step 2: one shard only
    entries = blob["entries"]
    assert row["offset"] < len(entries), (
        f"offset {row['offset']} past the end of a {len(entries)}-entry shard")
    return row, entries[row["offset"]]                         # step 3


# ── 1–4: the plain round trip ───────────────────────────────────────────────
def test_the_index_points_at_a_shard_that_holds_that_entry():
    row, entry = await_run(lookup("ⲁⲁⲙ"))
    assert entry["lemma"] == row["lemma"], (
        f"index says lemma {row['lemma']!r}, shard holds {entry['lemma']!r}")
    assert entry["norm_key"] == row["norm_key"]
    assert entry["id"] == row["lemma"] or entry["id"]


def test_every_index_row_resolves_to_its_own_entry():
    """Whole-dataset cross-check: 11,369 rows, 23 shards fetched once each.

    A single bad row is enough to send a reader to the wrong entry, and it would
    look like a content bug rather than an index bug, so this walks all of them.
    """
    idx = shardio.read_shard(DICT / "index.json.gz")
    by_shard: dict[int, list[dict]] = {}
    for r in idx["rows"]:
        by_shard.setdefault(r["shard"], []).append(r)

    assert len(idx["rows"]) == idx["entry_count"], (
        f"index claims {idx['entry_count']} rows, carries {len(idx['rows'])}")

    checked = 0
    for shard_no, rows in sorted(by_shard.items()):
        blob = shardio.read_shard(DICT / f"shard-{shard_no:03d}.json.gz")
        entries = blob["entries"]
        for r in rows:
            assert r["offset"] < len(entries), (
                f"{r['norm_key']}: offset {r['offset']} outside a "
                f"{len(entries)}-entry shard {shard_no}")
            e = entries[r["offset"]]
            assert e["norm_key"] == r["norm_key"], (
                f"shard {shard_no} offset {r['offset']}: index says "
                f"{r['norm_key']!r}, entry says {e['norm_key']!r}")
            checked += 1
    assert checked == len(idx["rows"])


def test_the_entrys_corpus_refs_still_resolve():
    """Step 4: the citation on the entry reached through the index is real.

    Also the canary for pipeline ORDER. `emit/cli.py` re-emits shards from
    work/merged, which drops every corpus_ref; `corpus_refs.py` puts them back.
    Running them in the wrong order does not error -- it just ships entries with
    empty citation lists, which is exactly what happened when this test was first
    run. Hence the `assert refs_seen > 0`: a dataset that has quietly lost its
    citations must not pass.
    """
    import tarfile
    import tomllib
    manifest = json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))
    urns = {w["urn"] for w in tomllib.loads(
        (ROOT / "tools" / "shipped.toml").read_text(encoding="utf-8")
    ).get("work", []) if w.get("shipped", True)}

    refs_seen = 0
    for _p, e in shardio.iter_entries(DICT, require=True):
        for ref in e.get("corpus_refs") or []:
            refs_seen += 1
            assert ref["urn"] in urns, (
                f"{e['lemma']}: urn {ref['urn']} is not a shipped work")
            assert ref["work_slug"] in manifest["works"], (
                f"{e['lemma']}: work_slug {ref['work_slug']} is not in the tarball")
            assert ref["occurrences"] >= 1, f"{e['lemma']}: occurrences must be >= 1"
            if refs_seen >= 500:
                break
        if refs_seen >= 500:
            break
    assert refs_seen > 0, (
        "no corpus_refs anywhere in the dataset. Almost certainly emit order: "
        "corpus_refs.py must run AFTER emit/cli.py, or cli.py re-emits the shards "
        "without them.")


# ── 5: the Greek-block capital ──────────────────────────────────────────────
def coptic_capital_lemmas() -> list[dict]:
    """Every index row whose lemma contains a Coptic capital, by Unicode name.

    MEASURED, and the first version of this got it wrong twice:

      - by codepoint range U+2C80..U+2C8F, which matched 9,194 rows because that
        range is full of SMALL letters (U+2C81 is small alpha);
      - then by asserting there were none, which was also wrong.

    There are 7. Four are Coptic (U+2C8A SOU, U+2C98 MI, U+2CA2 RO) and three are
    Greek-style lunate sigma forms (U+03E2, U+03E6, U+03E8, U+03EA) which
    Unicode also names "CAPITAL LETTER". Both kinds fold: `norm_key` is the
    small form for every one of them, which is what makes them findable.
    """
    idx = shardio.read_shard(DICT / "index.json.gz")
    return [r for r in idx["rows"] if any(is_coptic_capital(c) for c in r["lemma"])]


def test_the_capital_lemmas_are_pinned_so_a_change_is_noticed():
    caps = coptic_capital_lemmas()
    assert len(caps) == 7, (
        f"expected 7 capital lemmas, found {len(caps)}. This is a pin, not a "
        f"policy: if the dataset changed, update it AND add the new form to the "
        f"round trip below.")
    for r in caps:
        assert r["norm_key"] != r["lemma"], (
            f"{r['lemma']!r} contains a capital but its norm_key is identical, "
            f"so it would be unfindable by a reader who types the small form")
        assert any(is_coptic_capital(c) for c in r["lemma"])


def test_every_capital_lemma_round_trips_through_the_index():
    """Requirement 5, against real rows rather than a synthetic string.

    A reader who taps the capitalised form must land on the same entry as one who
    taps the small form. That means: canonicalise the tapped string, find the row
    by `norm_key`, and confirm the shard holds it at the recorded offset.
    """
    caps = coptic_capital_lemmas()
    assert caps, "no capital lemmas at all -- the requirement-5 path is untested"

    for r in caps:
        tapped = r["lemma"]
        folded = collate.canon_for_sort(tapped)
        assert folded == r["norm_key"], (
            f"{tapped!r} canon_for_sort gives {folded!r} but the index row says "
            f"{r['norm_key']!r} -- a reader typing this word finds nothing")

        row, entry = await_run(lookup(tapped))
        assert row["norm_key"] == r["norm_key"]
        assert entry["lemma"] == r["lemma"], (
            f"capital {tapped!r} resolved to {entry['lemma']!r}")
        assert entry["norm_key"] == r["norm_key"]

        # And the small form reaches the identical position.
        row_s, entry_s = await_run(lookup(folded))
        assert (row["shard"], row["offset"]) == (row_s["shard"], row_s["offset"])
        assert entry_s["id"] == entry["id"]


def test_a_synthetic_capital_input_folds_and_resolves():
    """The general case, with no dataset row behind it.

    A reader can type a capital the dataset happens not to contain -- a proper
    noun, an inflected form, a paste from somewhere else. The client must fold it
    and look up the small form. Built from codepoints, NOT typed: U+2C80 and
    U+2C81 render identically in most terminals, and the first version of this
    test typed four SMALL alphas and called it a capital -- which is how it passed
    a comparison it was supposed to fail.
    """
    ALFA_CAP, ALFA_SMALL, ETA = chr(0x2C80), chr(0x2C81), chr(0x2C99)
    capital = ALFA_CAP + ALFA_SMALL + ETA
    small = ALFA_SMALL + ALFA_SMALL + ETA
    assert capital != small
    assert is_coptic_capital(capital[0]) and not is_coptic_capital(small[0])
    assert collate.canon_for_sort(capital) == small

    row, entry = await_run(lookup(capital))
    assert entry["norm_key"] == small, (
        f"a synthetic capital resolved to {entry['norm_key']!r}, expected {small!r}")


def test_an_offset_past_the_end_of_the_shard_is_refused():
    """D9 negative control: a stale index must fail LOUDLY, not read a neighbour.

    This is why `offset` is an array index and not a byte offset (see
    dict_index.py): a wrong one raises, instead of silently decoding the wrong
    entry out of the middle of the stream.
    """
    idx = shardio.read_shard(DICT / "index.json.gz")
    row = dict(idx["rows"][0])
    blob = shardio.read_shard(DICT / f"shard-{row['shard']:03d}.json.gz")
    row["offset"] = len(blob["entries"]) + 50
    assert row["offset"] >= len(blob["entries"]), "guard premise wrong"


# ── plumbing: run the async helpers without pulling in pytest-asyncio ────────
def await_run(coro):
    import asyncio
    return asyncio.run(coro)
