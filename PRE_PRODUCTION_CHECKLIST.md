# PRE_PRODUCTION_CHECKLIST.md — promoting to production

Prepared Session 14 (D4). **Nothing has been promoted.** `master` has no commits,
so there is nothing for Cloudflare to build from, and promotion is Michael's
decision. This is everything needed to do it, in order.

## 1. State right now

| | |
|---|---|
| Branch | `master`, **unborn** — `fatal: your current branch 'master' does not have any commits yet` |
| Working tree | 44 untracked entries; **no commit has ever been made** |
| Live preview | `https://session-14.coptic-reference.pages.dev` — checklist 10/10 |
| Cloudflare project | `coptic-reference`, account `160e5baf51934e3af06e3028a83de5b8` |
| Tests | 325 passed, 22 skipped, 1 xfailed |
| Guards | 16, all pass |

## 2. Before committing: what must not be committed

```sh
git check-ignore -v .venv node_modules public data/dist sources 2>&1
```

`.gitignore` must cover `.venv/`, `node_modules/`, `public/`, `__pycache__/`,
`.pytest-tmp/`. **`public/` is a build product (Rule 5)** — committing it would put
a second copy of the site in git that can disagree with the build.

Also confirm `tools/sources.lock` is present and unchanged (4 `VERIFY` markers
intact) and that no `sources/**/*.tt` corpus file is staged — those are fetched,
not vendored.

## 3. Commit plan

Eleven commits, ordered so each is independently reviewable and no commit is
broken. Review with `git log --stat` before pushing.

| # | Message | Paths | Why this order |
|---|---|---|---|
| 1 | `chore: repository scaffolding, licence and .gitignore` | `.gitignore`, `.gitattributes`, `LICENSE`, `NOTICE`, `AUTHORS.md`, `GOVERNANCE.md`, `CHANGELION.md` | everything else assumes these exist |
| 2 | `docs: project plans and the working method` | `COPTIC-AI-REVITALIZATION-PLAN*.md`, `FAQ.md`, `ONBOARDING.md`, `CONTRIBUTING*.md` | the method is written down before the code that follows it |
| 3 | `feat(sources): pinned source manifest and allowlists` | `tools/sources.lock`, `tools/shipped.toml`, `tools/fetch/`, `tools/validate/{nc_guard,licence_guard,single_source_guard,stdlib_name_guard}.py` | provenance first: nothing may be ingested before it can be attributed |
| 4 | `feat(parse): Coptic corpus parsers` | `tools/parse/` | parsers before anything that consumes them |
| 5 | `feat(merge): schema, POS normalisation and verified writes` | `tools/merge/`, `tools/pos.py`, `tools/collate.py`, `tools/safeio.py`, `tools/shardio.py` | collation and safe writes are used by every emitter |
| 6 | `feat(emit): dictionary shards, index and provenance tables` | `tools/emit/` | produces `data/dist` |
| 7 | `test: the corpus and guard suite` | `tools/tests/`, `tools/validate/` | lands with or immediately after the code it checks; tests and guards in one commit because they were written together |
| 8 | `feat(site): Hugo theme, content and the build pipeline` | `hugo.yaml`, `themes/`, `content/`, `static/`, `tools/build.py`, `.github/` | `public/` is generated and stays untracked |
| 9 | `fix: the six shipped-but-inert defects` | `static/js/*`, `themes/copticref/layouts/*`, `static/read-csv.html` | the Reader/glossary/corpus/offline fixes, isolated so the diff shows intent |
| 10 | `docs: decisions, errata, coverage and deployment runbooks` | `DECISIONS.md`, `PLAN-ERRATA.md`, `COVERAGE.md`, `HANDOFF.md`, `RUNBOOK.md`, `DEPLOY.md`, `POST_DEPLOY_CHECKLIST.md`, `PRE_PRODUCTION_CHECKLIST.md`, `README.md` | the record, once the code it describes is settled |
| 11 | `fix: Pagefind English-search workaround` | `tools/emit/english_index.py`, `static/js/search.js`, `docs/PAGEFIND-BUG.md` | separate because it is the one change with a known upstream issue attached (PageFind/PageFind#1370) |

Staging, deliberately explicit rather than `git add -A`:

```sh
git add .gitignore .gitattributes LICENSE NOTICE AUTHORS.md GOVERNANCE.md CHANGELOG.md
git commit -m "chore: repository scaffolding, licence and .gitignore"
# ... repeat per the table, then:
git status --short          # must be empty except ignored paths
```

## 4. Push and let Pages build

```sh
git push -u origin master
```

The Pages project's **production branch is already `master`**, so the push itself
triggers the production build. Build command and settings are in `DEPLOY.md` §2–§3
and are already configured on the project.

If you would rather build the exact artifact locally first:

```sh
export PATH="$HOME/.local/bin:/usr/local/bin:$PATH"
.venv/bin/python tools/build.py                       # must print "guard PASSED"
.venv/bin/python tools/validate/public_provenance_guard.py --strict
.venv/bin/python tools/validate/public_completeness_guard.py --strict
.venv/bin/python tools/validate/corpus_shape_guard.py
.venv/bin/python tools/validate/pagefind_pin_guard.py
```

## 5. Deploy production explicitly, if you do not want the push to do it

```sh
export WRANGLER_SEND_METRICS=false        # else the deploy fails on telemetry
npx wrangler pages deploy public --project-name coptic-reference --branch master
```

Two environment quirks that will otherwise cost you time:

- **`WRANGLER_SEND_METRICS=false` is required.** Without it the deploy fails with
  *"A fetch request failed"* — the failing request is the metrics dispatcher, not
  the Pages API.
- **The OAuth token expires.** When it does, `wrangler` cannot refresh it because
  Node's `fetch` cannot reach the auth server, though `curl` can. Re-running the
  command usually succeeds; `wrangler login` is the fallback and is interactive.

## 6. After production is up

Run `POST_DEPLOY_CHECKLIST.md` **against the production URL**, not the preview.
All ten items, including the precache declared-vs-served comparison and the CSP
check — the CSP is the one that has actually broken production behaviour before,
by blocking Pagefind's WebAssembly with no visible error.

## 7. Do not forget

- The four `VERIFY: reconstructed` markers in `tools/sources.lock` are still
  unresolved. A production deploy does not resolve them, and it should not.
- `copper`, `carbonate`, `coin`, `rust`, `fire` and `green` are found by the
  workaround, not by Pagefind. Upstream issue **PageFind/PageFind#1370** is open;
  if it is fixed, remove `static/js/search.js` and the 3c step in `tools/build.py`.