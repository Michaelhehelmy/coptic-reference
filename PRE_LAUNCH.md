# PRE_LAUNCH.md

> ## 🚧 THIS PROJECT IS NOT YET LAUNCHED
>
> **Everything in this repository is under construction.** Pages may be missing,
> incomplete, or wrong. Nothing here should be presented to the Coptic community
> as a finished reference until this checklist is complete.
>
> **Not launched · pre-launch checklist in progress**

---

## Launch gate

**Launch is blocked until every box below is ticked and initialled.** This is not
a formality. v5 §15 makes the Deputy Maintainer line a hard gate, and §13.1
makes the reading path a hard gate.

| | Item | Owner | Date |
|---|---|---|---|
| ☐ | **Deputy Maintainer named, in writing** | | |
| ☐ | Deputy listed in `GOVERNANCE.md` §Succession and `AUTHORS.md` | | |
| ☐ | Institutional custodian asked in advance (Diocese → KELLIA → Scriptorium) | | |
| ☐ | Succession rehearsal scheduled | | |

---

## Invariants — verify, do not assume

| | Check | How | Result |
|---|---|---|---|
| ☐ | **Reading works with JavaScript disabled** | Load every template with JS off | |
| ☐ | **Reading works with no network after first load** | Load once, go offline, navigate everything | |
| ☐ | **Worker deleted → reading unaffected** | `wrangler delete` on preview, then read the whole site | |
| ☐ | **No runtime service on the reading path** | `rg` for fetch/XHR to any absolute URL in `themes/` and `static/js/` | |
| ☐ | **No account required to read or to suggest** | Submit via the form and via `mailto:` with no GitHub account | |
| ☐ | **No KV, no D1, no database, no bindings** | `wrangler.toml` has zero bindings | |
| ☐ | **$0 recurring** | Pages Free, Workers Free, GitHub free tier | |
| ☐ | **File count under 20,000** (CI gate at 15,000) | `find public -type f \| wc -l` | |
| ☐ | **No file over 25 MiB** | `find public -type f -size +25M` | |

---

## Licence and provenance

| | Check | Result |
|---|---|---|
| ☐ | Every asset has a licence verdict in `LICENSES.csv` — no `UNKNOWN` | |
| ☐ | `nc_guard.py` passes: only `ALLOWED_SOURCES` in `data/dist/**` | |
| ☐ | NC content is under `content/nc/` only, never in `data/dist` | |
| ☐ | Every entry has ≥ 1 `attributions[]` entry | |
| ☐ | Every `attributions[].changes` uses the controlled vocabulary | |
| ☐ | `/licences/` generated from `LICENSES.csv` and complete | |
| ☐ | `/credits/` hand-written, names individuals, not just institutions | |
| ☐ | Footer credits upstream originators **more** prominently than the project author | |
| ☐ | Footer does **not** read `© Michael Helmy · CC BY-SA 4.0` | |
| ☐ | `submitter_hash` appears nowhere in `public/` (CI greps for it) | |
| ☐ | Second person has reviewed `records.csv` and `LICENSES.csv` diffs | |
| ☐ | Unverified licences (Shisha-Halevy, learner's grammar, Younan, Anki decks) resolved or linked-not-mirrored | |

---

## Data quality

| | Check | Result |
|---|---|---|
| ☐ | `collation_hash` pinned and `collation_guard.py` passes | |
| ☐ | ≥ 10,500 unique entries after merge | |
| ☐ | ≥ 85% of entries have ≥ 1 English gloss | |
| ☐ | `canon_form` idempotent over all 2.38M corpus words | |
| ☐ | Corpus counts within 2% of previous bake | |
| ☐ | Bohairic coverage badges render, and are **honest where thin** | |
| ☐ | Corpus tier order is liturgical → biblical → patristic → monastic | |

---

## Content and access

| | Check | Result |
|---|---|---|
| ☐ | 15 lessons, each reviewed by a Coptic linguist | |
| ☐ | Every lesson: ≥ 300 words, ≥ 3 examples, ≥ 5 corpus deep-links, ≥ 1 grammar ref | |
| ☐ | axe-core: 0 critical, 0 serious on all 6 templates | |
| ☐ | Full keyboard operability of search, reader, concordance | |
| ☐ | 300 dictionary pages render **without JavaScript** | |
| ☐ | PWA installable: Chrome + **iOS Safari**; launches offline | |
| ☐ | Offline cache ≤ 24 MB; LRU eviction verified | |
| ☐ | Screen-reader pass: VoiceOver **and** NVDA | |
| ☐ | Fonts subset (Coptic block only), load < 100 KB total | |
| ☐ | Dialect toggle defaults to Bohairic and says coverage is uneven | |
| ☐ | Suggestion panel below content, not above; never demands an account | |

---

## Community and process

| | Check | Result |
|---|---|---|
| ☐ | `GOVERNANCE.md`, `RUNBOOK.md`, `HANDOFF.md`, `ONBOARDING.md` written | |
| ☐ | Steward named (≥ 1) | |
| ☐ | Reviewer named for linguistic, theological, **and** licence** | |
| ☐ | `/roadmap/` generated from `suggestions.json`, showing deferred and declined | |
| ☐ | `decide_by` enforced in CI: no `accepted` item may pass its date | |
| ☐ | January and July windows in the calendar, with the Maintainer's name on them | |
| ☐ | Submission SLAs published **on the site**, not only in `GOVERNANCE.md` | |
| ☐ | Suggestion form tested end to end against a throwaway repo, including dedup | |

### Session 2 additions — recorded, still open

These are **not** new requirements. They are Session 1 and Session 2 findings that
belong on this list and must not be quietly dropped. Both remain unticked.

| | Check | Why it is here | Result |
|---|---|---|---|
| ☐ | **Deputy Maintainer named** | v5 §15 makes succession a launch gate. Session 1 Q3: Michael's call, so the box stays unticked rather than being softened away. The pre-launch banner is the interim mitigation, not the gate. | |
| ☐ | **Suggestion Worker deployed to a preview, against a throwaway repo, with search-based dedup verified live** | Session 1 Q7: an environment constraint, not a code failure. `workers/suggest/test/smoke.mjs` verifies the dedup *logic* against a stubbed GitHub API (28 assertions), but nothing has exercised it against real GitHub. v5 §13.1 option (B) is unproven until this is done. | |

### Required pre-launch check — deploy the Worker and prove dedup end to end

**This is a gate, not a session note.** Sessions 1 and 2 both recorded it as an
environment limitation and it stayed undone, which is exactly how a gate rots.
It moves here so it is checked like every other item on this list.

Five steps. **All five must pass.** Steps 4 and 5 are the point; steps 1–3 only
prove the thing uploads.

| | Step | Command / action | Passes when |
|---|---|---|---|
| ☐ | 1. Dry run | `cd workers/suggest && npx wrangler deploy --dry-run` | Prints the bundle and binding list. **Bindings must be empty** — no KV, no D1, no R2, no queues (invariant 3). `vars` are plain config and are expected. |
| ☐ | 2. Throwaway repo | Create a private GitHub repo with Issues enabled; install the GitHub App (or PAT) with `issues:write` on it. Grant **only** that repo. | `GITHUB_TOKEN` is a secret on the Worker, never in the repo. |
| ☐ | 3. Deploy to preview | `npx wrangler secret put GITHUB_TOKEN` then `npx wrangler deploy --name coptic-suggest-preview` | Responds on `*.workers.dev`. |
| ☐ | 4. **Dedup, live** | Send the *same* `POST /api/suggest` body **twice**, from the same IP, within 24h. | The **second** returns the **same `github_issue_url`** as the first and adds a *comment*. Confirm by reading the throwaway repo's Issues tab: exactly **one** issue, **two** comments, and the second body contains `<!-- dedup:… -->`. |
| ☐ | 5. Endorse, live | `POST /api/endorse` with `{"issue_number": <the issue>, "reaction": "+1"}`, then again. | First → `201`. Second → `200 already_reacted` (not an error). The issue shows 👍 on GitHub. |

**Then delete the throwaway repo and revoke the token.** The preview Worker may
keep running; it must not keep a token for a repository that no longer exists.

**Record the outcome in `CHANGELOG.md`** with the date, whether step 4 deduplicated
on the first try, and anything that surprised you. A dedup test that only passed
after a code change is a finding worth writing down.

**On the Worker:** `npx wrangler deploy --dry-run` has **never** run successfully. Session 1: no
network at all. Session 2: registry reachable, but tarballs arrived at ~4 kB/s
and wrangler's dependency tree never finished installing. Neither failure is a
code failure. Substitutes verified instead: `wrangler.toml` parses and declares no
resource bindings, the bundle is a self-contained 9.5 KB ES module with zero
external imports, and `test/smoke.mjs` passes 28 assertions. **None of that is a
substitute for step 4.**

---

## Sign-off

| Role | Name | Date |
|---|---|---|
| Maintainer | | |
| Reviewer — linguistic | | |
| Reviewer — licence | | |
</content>

---

## Session 6 — environment note (C4): NOT a filesystem fault; a filename bug

**Correction.** Session 5 closed with "this machine's filesystem is broken, please
fsck". That was **wrong**, and it was my bug. No fsck is needed.

### What was actually happening

`emit/cli.py` wrote the licence manifest as **`LICENCES.csv`** (no S) while every
reader — `licence_guard.DEFAULT_LICENCES`, `obsidian.py`, `dry_run.py`,
`test_obsidian.py`, and the docs — reads **`LICENSES.csv`**. So the fixture wrote
one filename, the tests read another, and `os.listdir` showing the written file
next to `is_file()` returning False looked exactly like a stale dentry. I read it
that way and "fixed" a machine that was fine.

### How to reproduce the symptom (no fsck required)

```bash
# 15 tests fail; the guard says a file it can list is "not found"
python3 -m pytest tools/tests/test_guards.py -q

# the two names, side by side — this is the whole bug
grep -rn "LICENCES\.csv" tools/ | grep -v LICENSES
python3 -c "
import pathlib
d = pathlib.Path('data/dist/provenance')
print([p.name for p in d.iterdir()])"
```

### Real damage, now fixed

- Two licence manifests existed. The generated one was **not** the file any guard
  validated.
- Regenerating from an empty prior map downgraded `Manley2019` from
  `CC-BY-NC-4.0` to `UNVERIFIED` — **losing a known licence**, which is
  invariant 7 breaking in the most literal way available.

### Standing item

`LICENSES.csv` (with the S, matching v4 §7.1) is canonical. `safeio.write_verified`
now writes it atomically and reads it back, so a half-landed write cannot present
itself as a success again. See `DECISIONS.md` S6-B1 and S6-B2.


---

## Session 10 additions — still open for Michael

### 1. Four reconstructed provenance markers — UNRESOLVED, by instruction

Session 10 verified and dated the `ud_bohairic` removal but deliberately did
**not** resolve these. They need a human who knows the sources:

```
grep -n 'VERIFY: reconstructed' tools/sources.lock
```

Each marks a source whose origin was reconstructed from memory during an earlier
session rather than read from a real download. `tools/validate/single_source_guard.py`
and the NC gates all pass regardless, because a guard can only check what the file
says — not whether the file is true.

**Do not let a tool resolve these.** A guard that can clear a provenance marker
can also fabricate one.

### 2. English Pagefind search is partially indexed — OPEN DEFECT

`copper` returns 0 hits; `azurite` returns 9 from the same gloss field. Measured
in `DECISIONS.md`. `test_pagefind_english_search_finds_copper` is a strict
xfail so a fix surfaces as XPASS. Coptic search, prefix search and the English
path via `azurite` all pass.

### 3. Pagefind binary is not a project dependency

It lives at `/tmp/pagefind` here and is resolved from `PAGEFIND_BIN`. The build
degrades to a site with no search rather than failing, by design, and now warns.

### 4. No Lighthouse receipt

Chromium is available for the functional tests; Lighthouse has not been run.
