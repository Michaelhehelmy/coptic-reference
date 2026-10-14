# DEPLOY.md — deploying the Coptic reference to Cloudflare Pages

Prepared Session 11 (D5). **Nothing has been deployed.** These are the steps for
Michael to run, with the values filled in.

## 1. What is deployed

Only `public/`. It is a build product (HANDOFF.md §8a Rule 5) and contains
static HTML, CSS, JS, JSON and gzipped JSON. There is no server, no database, no
KV, no D1 and no account for readers. The only runtime component in the project
is `workers/suggest/`, which is not required to deploy the reading path.

## 2. Cloudflare Pages project settings

| Setting | Value | Why |
|---|---|---|
| Project name | `coptic-reference` | — |
| Production branch | `master` | repo has no other branch |
| Build command | see §3 | must be one command, under 20 min |
| Build output directory | `public` | Rule 5: this is the only thing served |
| Root directory | *(repository root)* | `tools/` and `themes/` are needed |
| Node.js version | `22` (Build image v3) | `tools/emit/*.mjs` need modern Node |
| Environment variable | `HUGO_VERSION=0.128.0` | see §3 |
| Environment variable | `PAGEFIND_BIN` — **leave empty** | resolved from `node_modules` instead, see §4 |

**Do not** set a Pages Function, KV binding or D1 binding. Adding one would turn
a $0 static site into something with a runtime and a bill.

## 3. Build command

Cloudflare's Pages build image ships Hugo, but **not necessarily the pinned
version**, and it runs `hugo` from `PATH`. Pin it explicitly:

```sh
set -euo pipefail
HUGO_VERSION=0.128.0
curl -sSL -o /tmp/hugo.deb \
  "https://github.com/gohugoio/hugo/releases/download/v${HUGO_VERSION}/hugo_${HUGO_VERSION}_linux-amd64.deb"
sudo dpkg -i /tmp/hugo.deb
hugo version
npm ci
python3 tools/build.py
```

### The build command, verbatim — paste this into Pages

```sh
HUGO_VERSION=0.128.0 && curl -sSL -o /tmp/h.deb "https://github.com/gohugoio/hugo/releases/download/v${HUGO_VERSION}/hugo_${HUGO_VERSION}_linux-amd64.deb" && sudo dpkg -i /tmp/h.deb && npm ci && python3 tools/build.py
```

If Pages cannot write `/tmp/h.deb`, set `HUGO_VERSION` as an environment variable
and substitute `npx hugo-bin@0.128.0` for `hugo`. `hugo-bin` is already pinned in
`package.json` for exactly this case.

Note that `npm run build` is **not** the build command. It runs `hugo` directly,
which would write to `public/` outside `tools/build.py` and break Rule 5 (only the
build writes to `public/`). `tools/build.py` deletes `public/` and regenerates it
in a fixed order; running Hugo by hand would leave orphan files from a previous
build that `public_provenance_guard.py` then rejects.

### Build time budget

Measured on this machine:

| Step | Time |
|---|---|
| `npm ci` | ~120 s cold, ~2 s with a warm cache |
| `tools/build.py` (Hugo + Pagefind + SW + manifest) | **3.9 s** |
| Total | **~2 min**, essentially all of it `npm ci` |

Conservative bound on a slow environment (×10): **~20 min** — at the limit.

The risk is `npm ci`, not the site build. `tools/build.py` is 4.2 s and would be
42 s on a machine ten times slower.

### Mitigation: enable Cloudflare's npm cache, and pin exactly

Session 12 D4 weighed three options and chose the npm cache.

**Vendoring was tried and reverted.** `node_modules/pagefind` ships a 1,137-byte
wrapper (`lib/runner/bin.cjs`) that resolves the real platform binary at
runtime. Copying that single file produced a "vendored" binary that could not
run — `node vendor/pagefind/pagefind-1.5.2 --version` printed a Node stack trace.
Vendoring the entire runner tree was not verified end to end, and **shipping an
unverified mitigation is worse than shipping none**, so it was withdrawn.

**Prebuilt `node_modules` as a release artefact** was rejected for the same
reason, plus one more: it cannot be checked from the repository.

So: keep `npm ci`, and turn on Cloudflare's dependency-cache setting so the
second and later builds skip it.

| | cold | warm |
|---|---|---|
| `npm ci` | ~120 s | ~2 s |
| `tools/build.py` | 4.2 s | 4.2 s |
| **total** | **~2 min** | **~6 s** |

Conservative ×10 bound: **~20 min cold** (at the limit), **~1 min warm**.
Cloudflare's free tier caches dependencies after the first build, so the cold
case is a first-deploy concern only. If it ever bites, vendoring the runner tree
properly is the fix — but do it verified, as an explicit change.

**One real bug fixed here.** `package.json` read `"pagefind": "^1.5.2"` — a
caret — directly beneath a comment claiming *"PINNED EXACTLY, no caret"*. A caret
means the search index can differ between bakes, which breaks the
byte-reproducibility every other pin in this project exists to guarantee. Now
pinned to `"1.5.2"`, and `tools/validate/pagefind_pin_guard.py` fails the build if
a caret or range ever comes back. That guard caught the bug in the first minute it
existed.

## 4. Pagefind

`package.json` pins `pagefind` to exactly `1.5.2` — no caret, because the index
must be byte-reproducible across bakes. Verified Session 11:

```
npm install pagefind@1.5.2   → added 106 packages in 2m
node_modules/pagefind/package.json            → 1.5.2
node_modules/pagefind/lib/runner/bin.cjs --version → pagefind 1.5.2
```

`tools/emit/pagefind_index.mjs` resolves the binary in this order:

1. `$PAGEFIND_BIN`
2. `node_modules/pagefind/lib/runner/bin.cjs` ← the pinned package
3. `/tmp/pagefind` ← legacy fallback, safe to delete

So `npm ci` alone is sufficient and `PAGEFIND_BIN` should be **unset**. Since
Session 12 D4 the binary is also vendored (see §3), so even that is no longer
required. The old default was `/tmp/pagefind` only, which meant a fresh build
container — where `/tmp` is empty — silently produced no search index.

If no binary is found the build prints a warning and ships **no search**;
`public_completeness_guard.py --strict` fails, and CI runs that guard, so this
cannot reach production unnoticed.

## 5. Headers

**No action needed.** `public/_headers` is now emitted by `tools/build.py` via
`tools/emit/headers.py`, because `public/` is deleted on every build (Rule 5) and
a hand-placed copy would be destroyed by the next one — which is exactly what
Session 11's version of this section told you to do. Its content:

```
/data/*
  Cache-Control: public, max-age=31536000, immutable
  Access-Control-Allow-Origin: *

/pagefind/*
  Cache-Control: public, max-age=31536000, immutable

/sw.js
  Cache-Control: public, max-age=0
  Service-Worker-Allowed: /

/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; worker-src 'self'
```

`Service-Worker-Allowed: /` is **not** optional. Without it, a worker registered
at `/sw.js` cannot control the scope `/`, and offline mode silently does nothing
on the first load.

`Content-Encoding: gzip` is deliberately **not** set here. Files under
`/data/**` are a mix of `.json.gz` (genuinely gzipped) and a few plain `.json`
and `.html` files, so a blanket `/data/*` rule would label the plain files as
gzipped and break them. Both readers sniff the `1f 8b` magic bytes and handle
either case correctly (Session 11 D0), which is why this is safe. If you do set
it, scope it to the `.gz` paths only and verify with §6 of the checklist.

The CSP above is strict (`script-src 'self'`, no `unsafe-inline`) and is
deliberate: every script is a file, including the service-worker registration
which lives in an inline block in the footer. **That inline block will violate
the policy.** Either drop `style-src 'self'`'s companion inline styles too, or
add a hash. Verify with the console check in the checklist before shipping —
this is the one place where the project's own build and its CSP disagree.

## 6. Then run `POST_DEPLOY_CHECKLIST.md`

Do not treat the deploy as done until that checklist passes. The items in it
check behaviour no build-time guard can: that the worker actually registers,
Pagefind actually loads, gzip is actually decoded correctly, and a corpus token
resolves to the right dictionary lemma.
