# workers/suggest/test/

`smoke.mjs` runs the bundled Worker in plain Node against a stubbed GitHub API.

It exists because `wrangler deploy --dry-run` was not runnable in the authoring
environment (no network access; wrangler's dependencies could not be installed)
and because a dry-run would not have tested behaviour anyway — it only proves
the bundle uploads. This harness asserts on what the Worker actually does: which
GitHub endpoints it calls, with which labels and bodies, that the honeypot is
silent, that dedup comments instead of duplicating, that the rate limiter
engages, and that neither the token nor a raw IP ever reaches a response.

    npx esbuild workers/suggest/index.ts --bundle --format=esm \
        --outfile=workers/suggest/dist/index.mjs
    node workers/suggest/test/smoke.mjs
