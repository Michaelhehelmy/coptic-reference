/**
 * workers/suggest/test/smoke.mjs
 *
 * A real functional test of the Worker, run in plain Node against the esbuild
 * bundle. This exists because `wrangler deploy --dry-run` could not be run in
 * this environment (no network; wrangler's deps are not installed), and a
 * dry-run would not have tested behaviour anyway — it only proves the bundle
 * uploads.
 *
 * The Worker uses only crypto.subtle, TextEncoder, Request and Response, all
 * of which Node 22 provides natively, so it runs unmodified. We stub
 * globalThis.fetch to intercept every GitHub API call and assert on it.
 *
 * Run:  node workers/suggest/test/smoke.mjs
 * Exit: 0 = all pass, 1 = a failure (with the reason printed).
 */
import assert from "node:assert/strict";
import worker from "../dist/index.mjs";

const ENV = {
  GITHUB_TOKEN: "ghp_FAKE_TOKEN_FOR_TESTS_ONLY",
  REPO: "owner/repo",
  SITE_ORIGIN: "https://coptic.re",
  RATE_LIMIT: "20",
};

let passed = 0;
const failures = [];
const calls = [];

/** Stub GitHub. `route(url, init)` returns [status, body]. */
function stub(route) {
  calls.length = 0;
  globalThis.fetch = async (input, init = {}) => {
    const url = String(input);
    calls.push({ url, method: init.method ?? "GET", body: init.body });
    const [status, body] = route(url, init);
    return new Response(body === undefined ? null : JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    });
  };
}

// The rate limiter is module-level state keyed by IP, so each test gets its own
// IP. Without this, later tests inherit earlier tests' quota and fail with a
// (correct, but unhelpful) 429. Test 23 below exercises the limiter explicitly.
let ipSeq = 0;
const freshIp = () => `198.51.100.${++ipSeq}`;

async function call(path, { method = "POST", body, ip = freshIp(), origin } = {}) {
  const headers = { "content-type": "application/json" };
  if (ip) headers["cf-connecting-ip"] = ip;
  if (origin) headers.origin = origin;
  const req = new Request(`https://worker.test${path}`, {
    method,
    headers,
    body: method === "GET" || method === "OPTIONS" ? undefined : JSON.stringify(body ?? {}),
  });
  const res = await worker.fetch(req, ENV, {});
  let parsed = null;
  try { parsed = await res.clone().json(); } catch { /* non-JSON */ }
  return { res, parsed };
}

async function test(name, fn) {
  calls.length = 0;
  try {
    await fn();
    passed += 1;
    console.log(`  ok   ${name}`);
  } catch (e) {
    failures.push([name, e.message]);
    console.log(`  FAIL ${name}\n       ${e.message}`);
  }
}

const goodSuggest = {
  target: { kind: "entry", id: "C5047", url_path: "/dict/c5047/", dialect: "B" },
  kind: "gloss",
  body: "This should read 'at the present time', not merely 'now'.",
  evidence: "Layton, Coptic Grammar 12",
};

// ── the happy path, with the brief's nested target shape ────────────────────
await test("POST /api/suggest creates an issue labelled entry/c5047", async () => {
  stub(() => [201, { number: 421, html_url: "https://github.com/owner/repo/issues/421" }]);
  const { res, parsed } = await call("/api/suggest", { body: goodSuggest });
  assert.equal(res.status, 201);
  assert.equal(parsed.ok, true);
  assert.equal(parsed.github_issue_number, 421);

  const created = calls.find((c) => c.url.endsWith("/repos/owner/repo/issues") && c.method === "POST");
  assert.ok(created, "expected a POST to the issues endpoint");
  const payload = JSON.parse(created.body);
  assert.ok(payload.labels.includes("entry/c5047"), `labels were ${payload.labels}`);
  assert.ok(payload.labels.includes("kind/gloss"));
  assert.ok(payload.labels.includes("status/new"));
  assert.equal(payload.title, "[gloss] C5047");
  assert.match(created.body, /<!-- dedup:[0-9a-f]{16} target:entry:C5047 -->/,
    "issue body must carry the dedup marker for the stateless dedup to work");
  assert.match(created.body, /Bohairic/);
});

await test("no token ever reaches the response or the issue body", async () => {
  stub(() => [201, { number: 1, html_url: "u" }]);
  const { res, parsed } = await call("/api/suggest", { body: goodSuggest });
  const wire = JSON.stringify(parsed) + JSON.stringify(calls);
  assert.ok(!wire.includes(ENV.GITHUB_TOKEN), "token leaked into client or issue body");
  assert.ok(!wire.includes("203.0.113.9"), "raw IP leaked");
});

// ── the migration this session performed ────────────────────────────────────
await test("the OLD flat target_* shape is now rejected", async () => {
  stub(() => [201, { number: 1, html_url: "u" }]);
  const { res, parsed } = await call("/api/suggest", {
    body: { target_kind: "entry", target_id: "C5047", url_path: "/dict/c5047/",
            kind: "gloss", body: "x".repeat(20) },
  });
  assert.equal(res.status, 400);
  assert.equal(parsed.error, "bad_target_kind");
});

await test("the OLD endorse `issue` field is now rejected", async () => {
  stub(() => [201, {}]);
  const { res, parsed } = await call("/api/endorse", { body: { issue: 421, reaction: "+1" } });
  assert.equal(res.status, 400);
  assert.equal(parsed.error, "bad_issue");
});

// ── validation ──────────────────────────────────────────────────────────────
const rejects = [
  ["bad target kind",    { ...goodSuggest, target: { ...goodSuggest.target, kind: "user" } }, "bad_target_kind"],
  ["missing target",     { ...goodSuggest, target: undefined },                   "bad_target_kind"],
  ["relative-less url_path", { ...goodSuggest, target: { ...goodSuggest.target, url_path: "dict/c5047/" } }, "bad_url_path"],
  ["short body",         { ...goodSuggest, body: "too short" },                   "body_too_short"],
  ["empty body",         { ...goodSuggest, body: "   " },                         "body_too_short"],
  ["unknown kind",       { ...goodSuggest, kind: "praise" },                      "bad_kind"],
];
for (const [label, body, err] of rejects) {
  await test(`rejects ${label} -> ${err}`, async () => {
    stub(() => [201, {}]);
    const { res, parsed } = await call("/api/suggest", { body });
    assert.equal(res.status, 400);
    assert.equal(parsed.error, err);
    assert.equal(calls.length, 0, "must reject BEFORE touching GitHub");
  });
}

await test("rejects malformed JSON", async () => {
  stub(() => [201, {}]);
  const req = new Request("https://worker.test/api/suggest", {
    method: "POST", headers: { "content-type": "application/json" }, body: "{not json",
  });
  const res = await worker.fetch(req, ENV, {});
  assert.equal(res.status, 400);
  assert.equal((await res.json()).error, "invalid_json");
});

// ── the honeypot must be silent, not loud ───────────────────────────────────
await test("honeypot returns 200 and never calls GitHub", async () => {
  stub(() => [201, {}]);
  const { res, parsed } = await call("/api/suggest", { body: { ...goodSuggest, honeypot: "i am a bot" } });
  assert.equal(res.status, 200, "must look successful so the bot learns nothing");
  assert.equal(parsed.ok, true);
  assert.equal(parsed.id, null);
  assert.equal(calls.length, 0, "a trapped bot must not be able to file issues");
});

// ── stateless dedup ─────────────────────────────────────────────────────────
await test("an existing open issue for the same submitter is commented on, not duplicated", async () => {
  stub((url) => {
    if (url.includes("/search/issues")) {
      return [200, { total_count: 1, items: [{ number: 99, html_url: "https://github.com/owner/repo/issues/99" }] }];
    }
    return [201, {}];
  });
  const { res, parsed } = await call("/api/suggest", { body: goodSuggest });
  assert.equal(res.status, 200);
  assert.equal(parsed.deduplicated, true);
  assert.equal(parsed.github_issue_number, 99);
  const created = calls.find((c) => c.method === "POST" && c.url.endsWith("/issues"));
  assert.equal(created, undefined, "must NOT create a second issue");
  assert.ok(calls.some((c) => c.url.includes("/issues/99/comments")), "must comment instead");
});

await test("search finding nothing creates a new issue", async () => {
  stub((url) => url.includes("/search/issues")
    ? [200, { total_count: 0, items: [] }]
    : [201, { number: 7, html_url: "u7" }]);
  const { parsed } = await call("/api/suggest", { body: goodSuggest });
  assert.equal(parsed.deduplicated, false);
  assert.equal(parsed.github_issue_number, 7);
});

// ── labels for non-entry targets ────────────────────────────────────────────
await test("a work target labels work/<id> instead of entry/<id>", async () => {
  stub((url) => url.includes("/search/issues")
    ? [200, { total_count: 0, items: [] }] : [201, { number: 3, html_url: "u" }]);
  await call("/api/suggest", {
    body: { target: { kind: "work", id: "urn:cts:copticLit:ot.exodus", url_path: "/works/exodus/" },
            kind: "typo", body: "The title should be spelled differently here." },
  });
  const payload = JSON.parse(calls.find((c) => c.method === "POST" && c.url.endsWith("/issues")).body);
  // split(":").pop() on a CTS URN yields the CTS *work component*, which is
  // "ot.exodus" — not the bare book name. That is the correct URN discipline.
  assert.ok(payload.labels.includes("work/ot.exodus"), `labels were ${payload.labels}`);
  assert.ok(!payload.labels.some((l) => l.startsWith("entry/")), "must not label a work as an entry");
});

// ── endorse ─────────────────────────────────────────────────────────────────
await test("endorse adds a reaction using issue_number", async () => {
  stub(() => [201, {}]);
  const { res, parsed } = await call("/api/endorse", { body: { issue_number: 421, reaction: "heart" } });
  assert.equal(res.status, 201);
  assert.equal(parsed.ok, true);
  const r = calls.find((c) => c.url.endsWith("/reactions"));
  assert.equal(JSON.parse(r.body).content, "heart");
});

await test("endorse treats an existing reaction as success, not an error", async () => {
  stub(() => [422, {}]);
  const { res, parsed } = await call("/api/endorse", { body: { issue_number: 421, reaction: "+1" } });
  assert.equal(res.status, 200);
  assert.equal(parsed.error, "already_reacted");
});

for (const [label, body, err] of [
  ["a bad reaction", { issue_number: 1, reaction: "eyes" }, "bad_reaction"],
  ["issue 0",         { issue_number: 0 },                  "bad_issue"],
  ["a fractional issue", { issue_number: 1.5 },             "bad_issue"],
]) {
  await test(`endorse rejects ${label}`, async () => {
    stub(() => [201, {}]);
    const { res, parsed } = await call("/api/endorse", { body });
    assert.equal(res.status, 400);
    assert.equal(parsed.error, err);
  });
}

// ── rate limiting (behaviour the shared-IP accident exposed) ────────────────
await test("the rate limiter fires for a repeat submitter on one IP", async () => {
  stub((url) => url.includes("/search/issues")
    ? [200, { total_count: 0, items: [] }] : [201, { number: 5, html_url: "u" }]);
  const spammer = "203.0.113.77";
  const first = await call("/api/suggest", { body: goodSuggest, ip: spammer });
  assert.equal(first.res.status, 201, "the first submission must succeed");

  // RATE_LIMIT is 20/window; drive past it from the same IP.
  let limited = null;
  for (let i = 0; i < 25 && !limited; i += 1) {
    const r = await call("/api/suggest", { body: goodSuggest, ip: spammer });
    if (r.res.status === 429) limited = r;
  }
  assert.ok(limited, "the limiter never engaged");
  assert.equal(limited.parsed.error, "rate_limited");
  assert.ok(Number(limited.res.headers.get("retry-after")) > 0, "must send retry-after");

  // A different IP is unaffected — the limiter is per-IP, not global.
  const other = await call("/api/suggest", { body: goodSuggest, ip: "203.0.113.78" });
  assert.equal(other.res.status, 201, "limiting one IP must not throttle everyone");
});

// ── routing, CORS, health ───────────────────────────────────────────────────
await test("GET is 405, not 200", async () => {
  stub(() => [200, {}]);
  const { res, parsed } = await call("/api/health", { method: "GET" });
  assert.equal(res.status, 200, "health is explicitly GET-able");
  assert.equal(parsed.repo, "owner/repo");

  const other = await call("/api/suggest", { method: "GET" });
  assert.equal(other.res.status, 405);
  assert.equal(other.parsed.error, "method_not_allowed");
});

await test("health reports configuration without leaking the token", async () => {
  stub(() => [200, {}]);
  const { parsed } = await call("/api/health", { method: "GET" });
  assert.equal(JSON.stringify(parsed).includes(ENV.GITHUB_TOKEN), false);
  assert.equal(parsed.turnstile, false);

  const bare = await worker.fetch(
    new Request("https://worker.test/api/health"), { REPO: "owner/repo" }, {});
  assert.equal((await bare.json()).ok, false, "unconfigured Worker must report ok:false");
});

await test("OPTIONS preflight returns 204 with the CORS methods", async () => {
  stub(() => [200, {}]);
  const { res } = await call("/api/suggest", { method: "OPTIONS", origin: "https://coptic.re" });
  assert.equal(res.status, 204);
  assert.equal(res.headers.get("access-control-allow-origin"), "https://coptic.re");
  assert.equal(res.headers.get("access-control-allow-methods"), "POST, OPTIONS");
  assert.equal(res.headers.get("x-content-type-options"), "nosniff");
});

await test("CORS is not echoed to a foreign origin", async () => {
  stub(() => [200, {}]);
  const { res } = await call("/api/health", { method: "OPTIONS", origin: "https://evil.example" });
  assert.equal(res.headers.get("access-control-allow-origin"), null);
});

await test("an unknown path is 404", async () => {
  stub(() => [200, {}]);
  const { res, parsed } = await call("/api/nope", {});
  assert.equal(res.status, 404);
  assert.equal(parsed.error, "not_found");
});

// ── upstream failure is degraded, not leaked ────────────────────────────────
await test("a GitHub 403 becomes 503 with a mailto hint, not a raw upstream error", async () => {
  stub(() => [403, { message: "API rate limit exceeded for 1.2.3.4" }]);
  const { res, parsed } = await call("/api/suggest", { body: goodSuggest });
  assert.equal(res.status, 503);
  assert.equal(parsed.error, "github_rejected");
  assert.match(parsed.hint, /mailto/);
  assert.ok(!JSON.stringify(parsed).includes("1.2.3.4"), "upstream detail must not be echoed");
});

await test("an unexpected throw becomes 500 and never echoes internals", async () => {
  stub(() => { throw new Error("ECONNRESET while calling api.github.com/repos/owner/repo"); });
  const { res, parsed } = await call("/api/suggest", { body: goodSuggest });
  assert.equal(res.status, 500);
  assert.equal(parsed.error, "internal");
  assert.ok(!JSON.stringify(parsed).includes("ECONNRESET"));
});

console.log(`\n${passed} passed, ${failures.length} failed`);
process.exit(failures.length ? 1 : 0);
