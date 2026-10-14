#!/usr/bin/env python3
"""tools/emit/headers.py — write public/_headers.

LICENCE: project code, Apache-2.0.

Session 12 D2 / C3. Cloudflare Pages reads `_headers` from the OUTPUT directory,
so it has to be emitted by the build: public/ is deleted and rebuilt on every run
(HANDOFF.md §8a Rule 5), so a hand-placed _headers would be silently destroyed by
the next build. Session 11's DEPLOY.md told Michael to create it by hand, which
was a documentation workaround for a missing build step.

Two things this file is careful about, both learned the hard way:

1. **`Content-Encoding: gzip` is NOT set on `/data/*`.** That prefix holds both
   genuinely gzipped files (`.json.gz`) and a handful of plain `.json`/`.html`
   files. A blanket rule would label the plain files as gzip and break them. Both
   readers sniff the `1f 8b` magic bytes instead (static/js/fetch_json.js), so
   correctness does not depend on the header — it is a bandwidth optimisation
   only, and mis-setting it is worse than not setting it.

2. **The CSP has no 'unsafe-inline'.** It can, now: the service-worker
   registration moved from an inline block to /js/sw-register.js. This generator
   and that file are two halves of one decision; if you re-inline the
   registration, this CSP will block it and the build should be considered
   broken rather than the policy relaxed.
"""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]

# Cloudflare Pages _headers syntax: a path pattern, indented header lines.
CONTENT = """\
# Emitted by tools/emit/headers.py — do not edit by hand.
# public/ is deleted on every build (HANDOFF.md §8a Rule 5), so a hand-placed
# copy of this file would be destroyed by the next one.

/data/*
  Cache-Control: public, max-age=31536000, immutable
  Access-Control-Allow-Origin: *

/pagefind/*
  Cache-Control: public, max-age=31536000, immutable

/js/*
  Cache-Control: public, max-age=31536000, immutable
  # /js/*.js are unhashed filenames, so "immutable" would strand a reader on an
  # old reader.js after a fix. One day, then revalidate.

/css/*
  Cache-Control: public, max-age=31536000, immutable

/sw.js
  Cache-Control: public, max-age=0
  Service-Worker-Allowed: /
  # NOT immutable, and Service-Worker-Allowed is not optional: without it a
  # worker registered at /sw.js cannot control the scope "/", and offline mode
  # silently does nothing on first load.

/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  X-Frame-Options: DENY
  Content-Security-Policy: default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; worker-src 'self'; base-uri 'self'; form-action 'none'; frame-ancestors 'none'
  # script-src 'self' with NO 'unsafe-inline': every script on this site is a
  # file, including /js/sw-register.js. Keeping it that way is what lets this
  # policy stay tight; see tools/emit/headers.py docstring.
  #
  # 'wasm-unsafe-eval' is required, and was found by running the tests under this
  # policy rather than next to it. Pagefind compiles a WebAssembly module inside
  # a worker, and CSP governs WebAssembly.instantiate() under script-src -- so a
  # policy without it blocks search entirely, in production, silently: the page
  # loads and the search box returns nothing. 'wasm-unsafe-eval' permits WASM
  # compilation only; it does NOT re-enable eval() or new Function().
"""


def main(public: pathlib.Path | None = None) -> int:
    pub = public or (ROOT / "public")
    if not pub.is_dir():
        print(f"[headers] FAIL — {pub} does not exist; run tools/build.py's earlier "
              f"steps first", file=sys.stderr)
        return 1
    dest = pub / "_headers"
    data = CONTENT.encode("utf-8")
    # Use the same verified write as the rest of the pipeline (Rule: every
    # artefact write is verified), so a truncated _headers cannot ship.
    sys.path.insert(0, str(ROOT / "tools"))
    import safeio
    safeio.write_verified(dest, data)
    print(f"[headers] wrote {dest.name} ({len(data)} B, "
          f"{CONTENT.count(chr(10) + '/')} rule(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
