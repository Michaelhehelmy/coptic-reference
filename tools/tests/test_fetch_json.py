#!/usr/bin/env python3
"""tools/tests/test_fetch_json.py — both Content-Encoding branches, mocked.

LICENCE: project code, Apache-2.0.

Session 12 D0 / C2, and the concrete case for Rule 8.

Rule 8 exists because this project's single sample was degenerate: every local
test server sends `.gz` **without** `Content-Encoding: gzip`. Under that one
sample, `reader.js` inflating unconditionally looked correct, so 295 tests passed
while the reader would have thrown on Cloudflare Pages, which does send the
header. A second sample on the other branch would have failed immediately.

So this file mocks the two branches explicitly instead of inheriting whatever
the local server happens to do:

    case A  Content-Encoding: gzip   -> already-inflated bytes reach fetch()
    case B  no header                 -> raw gzip bytes reach fetch()

Both must yield identical JSON. Neither is "the real one"; they are the two
inputs that differ in the property the code branches on.

Runs the SAME file the browser runs (static/js/fetch_json.js) under Node, so the
implementation under test is the shipped one, not a Python re-implementation.

Negative control, required by C2: corrupt/truncated gzip must fail GRACEFULLY
with a message naming the URL — never return empty text, which would render as
"this table has no rows" instead of "this file is broken".
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
HELPER = ROOT / "static" / "js" / "fetch_json.js"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(
    not HELPER.is_file() or NODE is None,
    reason="needs static/js/fetch_json.js and node on PATH")


HARNESS = r"""
const zlib = require("node:zlib");
const fs = require("node:fs");

// Load the SHIPPED file, not a copy, and not via require().
//
// require() does not work here: package.json declares "type": "module", so Node
// treats static/js/fetch_json.js as ESM and returns an empty namespace,
// silently discarding the module.exports guard. The browser is unaffected — a
// classic <script src> ignores package.json entirely — so the file is correct
// and only the loader is wrong.
//
// Evaluated with an explicit `module` object so the same CommonJS guard runs, and
// the helper's global assignment is asserted below so a broken UMD wrapper
// cannot pass silently.
const src = fs.readFileSync(process.argv[process.argv.length - 1], "utf8");
const mod = { exports: {} };
new Function("module", "globalThis", src)(mod, globalThis);
const FJ = mod.exports && Object.keys(mod.exports).length
  ? mod.exports
  : globalThis.FetchJson;

const PAYLOAD = { lemmas: ["ⲁ", "ⲧⲉⲛⲟⲩ"], gloss: "now", n: 2 };
const plain = Buffer.from(JSON.stringify(PAYLOAD), "utf8");
const gz = zlib.gzipSync(plain);

function makeResponse(buf, contentEncoding) {
  const headers = new Headers();
  headers.set("content-type", "application/json");
  if (contentEncoding) headers.set("content-encoding", contentEncoding);
  return new Response(buf, { status: 200, headers });
}

const results = {};
// run() INSTALLS its own fetch mock. That bit me once: the 404 and empty-body
// cases set globalThis.fetch themselves and then called run(), which overwrote
// it — so both "passed" while actually re-reading the happy-path buffer. The
// mock has to be part of the call, not set beforehand.
async function run(name, buf, encoding, fn) {
  globalThis.fetch = async () => makeResponse(buf, encoding);
  try { results[name] = { ok: true, value: await fn() }; }
  catch (e) { results[name] = { ok: false, error: String((e && e.message) || e) }; }
}

async function runWith(name, fetchImpl, fn) {
  globalThis.fetch = fetchImpl;
  try { results[name] = { ok: true, value: await fn() }; }
  catch (e) { results[name] = { ok: false, error: String((e && e.message) || e) }; }
}

(async () => {
  // ── the two branches Rule 8 demands ───────────────────────────────────
  // A: header set. A real browser hands us ALREADY-INFLATED bytes, because it
  //    applies Content-Encoding itself. So mock the post-browser body.
  await run("A_encoded_plain", plain, "gzip", () => FJ.json("/x.json.gz"));
  // B: no header. Raw gzip reaches fetch() untouched.
  await run("B_unencoded_gzip", gz, null, () => FJ.json("/x.json.gz"));
  // Also: no header and genuinely plain (a .json file that is not compressed).
  await run("C_plain_unencoded", plain, null, () => FJ.json("/x.json"));
  // And: header set but the body is STILL gzip (a host that double-encodes or
  // a proxy that stripped the header after the fact). Must also work.
  await run("D_encoded_but_gzip", gz, "gzip", () => FJ.json("/x.json.gz"));

  // ── negative controls ─────────────────────────────────────────────────
  const truncated = gz.subarray(0, Math.floor(gz.length / 2));
  await run("E_truncated_gzip", truncated, null, () => FJ.json("/x.json.gz"));

  const notGzip = Buffer.from("this is not json at all", "utf8");
  await run("F_plain_not_json", notGzip, null, () => FJ.json("/x.json"));

  await runWith("G_http_404",
    async () => new Response("nope", { status: 404 }),
    () => FJ.json("/missing.json.gz"));

  await runWith("H_empty_body",
    async () => new Response(new Uint8Array(0), { status: 200 }),
    () => FJ.json("/x.json.gz"));

  // isGzip must classify, not guess.
  results.exportsNonEmpty = !!(mod.exports && Object.keys(mod.exports).length);
  results.globalSet = typeof globalThis.FetchJson === "object";
  results.sniff = {
    gzip: FJ.isGzip(gz),
    plain: FJ.isGzip(plain),
    empty: FJ.isGzip(new Uint8Array(0)),
    oneByte: FJ.isGzip(new Uint8Array([0x1f])),
  };
  console.log(JSON.stringify(results));
})();
"""


@pytest.fixture(scope="module")
def outcome():
    assert NODE, "node is not on PATH"
    p = subprocess.run(
        [NODE, "-e", HARNESS, str(HELPER)],
        capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    if p.returncode != 0:
        pytest.fail(f"node harness failed:\n{p.stderr[-2000:]}")
    line = [l for l in p.stdout.splitlines() if l.startswith("{")]
    assert line, f"no JSON from harness:\n{p.stdout[-2000:]}\n{p.stderr[-2000:]}"
    return json.loads(line[-1])


def test_both_encoding_branches_yield_the_same_json(outcome):
    """The Rule 8 assertion: two inputs that differ in the branching property."""
    a = outcome["A_encoded_plain"]
    b = outcome["B_unencoded_gzip"]
    assert a["ok"], f"Content-Encoding: gzip branch failed: {a.get('error')}"
    assert b["ok"], f"no-header branch failed: {b.get('error')}"
    assert a["value"] == b["value"], "the two branches disagree"


def test_plain_uncompressed_body_still_parses(outcome):
    r = outcome["C_plain_unencoded"]
    assert r["ok"], f"a plain .json body failed: {r.get('error')}"
    assert r["value"]["gloss"] == "now"


def test_encoded_header_with_still_gzipped_body(outcome):
    """The awkward case: the header says gzip but the bytes are gzip.

    Sniffing must win over the header, or a proxy that strips Content-Encoding
    after the browser already saw it would break the page.
    """
    r = outcome["D_encoded_but_gzip"]
    assert r["ok"], f"gzipped body behind a gzip header failed: {r.get('error')}"


def test_helper_exports_under_both_module_systems(outcome):
    """The UMD wrapper must work in Node AND set the browser global.

    Found the hard way: package.json says "type": "module", so require() returns
    an empty object and a harness written with require() sees {} while the browser
    works fine. Asserting both halves means neither failure mode is invisible.
    """
    assert outcome["exportsNonEmpty"], (
        "module.exports is empty under Node; the CommonJS branch of the UMD "
        "wrapper did not run")
    assert outcome["globalSet"], (
        "globalThis.FetchJson was not set; a classic <script src> load would get "
        "nothing")


def test_gzip_magic_bytes_are_classified_not_guessed(outcome):
    s = outcome["sniff"]
    assert s["gzip"] is True
    assert s["plain"] is False
    assert s["empty"] is False, "an empty buffer must not be called gzip"
    assert s["oneByte"] is False, "a 1-byte buffer must not throw or match"


def test_truncated_gzip_fails_gracifully(outcome):
    """C2's required negative: needs decompression, gets broken bytes.

    Must throw with the URL named — never return "" or partial text, which would
    render as an empty table and read as "this work has no rows".
    """
    r = outcome["E_truncated_gzip"]
    assert not r["ok"], "truncated gzip was accepted; that is a silent empty table"
    assert "/x.json.gz" in r["error"], f"error does not name the URL: {r['error']!r}"
    assert "decompress" in r["error"].lower(), (
        f"error does not say the file is corrupt: {r['error']!r}")


def test_plain_text_is_reported_as_invalid_json(outcome):
    r = outcome["F_plain_not_json"]
    assert not r["ok"]
    assert "not valid JSON" in r["error"], r["error"]


def test_http_error_names_status_and_url(outcome):
    r = outcome["G_http_404"]
    assert not r["ok"]
    assert "404" in r["error"] and "/missing.json.gz" in r["error"]


def test_empty_body_is_rejected_rather_than_returning_empty_string(outcome):
    r = outcome["H_empty_body"]
    assert not r["ok"], "an empty body must not look like a successful empty read"
    assert "empty" in r["error"].lower(), r["error"]


# ─────────────────────────────────────────────────────────────────────────────
# The shipped call sites must all use the helper. A fourth copy of this logic
# would reintroduce exactly the drift Rule 8 describes, silently.
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("rel", [
    "static/js/reader.js",
    "static/js/corpus.js",
    "static/read-csv.html",
])
def test_call_sites_delegate_to_the_shared_helper(rel):
    p = ROOT / rel
    assert p.is_file(), f"{rel} is missing"
    txt = p.read_text(encoding="utf-8")
    assert "DecompressionStream" not in txt, (
        f"{rel} still decompresses on its own. It must call FetchJson — that is "
        f"the whole point of the extraction. A copy here is how read-csv.html "
        f"kept the pre-Session-11 bug while the other two were fixed.")
    assert "FetchJson" in txt, f"{rel} does not reference FetchJson"


def test_only_the_helper_decompresses():
    """Exactly one file in the reading path may know about gzip."""
    offenders = []
    for rel in ("static/js/reader.js", "static/js/corpus.js",
                "static/js/fetch_json.js", "static/read-csv.html"):
        p = ROOT / rel
        if p.is_file() and "DecompressionStream" in p.read_text(encoding="utf-8"):
            if rel != "static/js/fetch_json.js":
                offenders.append(rel)
    assert not offenders, (
        f"gzip decompression appears outside the helper: {offenders}")
