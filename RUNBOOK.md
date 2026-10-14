# RUNBOOK.md

**For: the maintainer on call.**

Every procedure here has commands and a rollback. Use them in order.

**House rule:** if a rollback exists, take it first, then investigate. A site
that is a day older is better than a site that is wrong for a week.

---

## 1. Weekly bake failed

**Symptom:** the `bake` workflow failed. `data/dist/` is unchanged, so the live
site is fine. **There is no user impact.** Do not panic; the design is that a bad
bake cannot reach readers.

### 1.1 Read the failure

```bash
gh run list --workflow bake --limit 5
gh run view <run-id> --log-failed
```

The failure will be in one of four stages:

| Stage | Failing command | Likely cause |
|---|---|---|
| `fetch` | `make -C tools fetch` | Network blip, or an upstream moved/renamed a file |
| `parse` | `make -C tools parse` | **Upstream schema change** (read on) |
| `emit` | `make -C tools emit` | Usually out of disk or an out-of-memory kill |
| `validate` | `make -C tools validate` | **A gate caught something. Read what it says.** |

### 1.2 Upstream change or parser bug?

```bash
# what changed upstream?
git diff main -- tools/sources.lock

# parse both pins and compare what comes out
git stash
make -C tools parse && cp -r work/ /tmp/work-old
git checkout main -- tools/sources.lock   # or the old SHA
git stash pop
make -C tools parse && cp -r work/ /tmp/work-new
diff -rq /tmp/work-old /tmp/work-new | head -30
```

- **Differences are confined to a few files** → upstream changed something small.
  Read the diff. If it is a genuine improvement, take it and add a note to `CHANGELOG.md`.
- **Differences touch everything, or output shrank sharply** → format drift.
  **Do not merge.** See §2.
- **No differences, parse still fails** → parser bug on your side, likely a stale
  local env. `rm -rf work/ merged/ && make -C tools all`.

### 1.3 Merge or reject

```bash
# reject — nothing to do, live site is unaffected
# just re-run next week:
gh workflow run bake
```

**Never merge a bake you have not read the `records.csv` diff for.** That file is
the review surface for data changes; `data/dist/corpus.tar.gz` is a binary blob
you cannot meaningfully diff.

```bash
git diff data/dist/provenance/records.csv | less
git diff data/dist/provenance/LICENSES.csv | less   # ← licence changes matter most
```

---

## 2. Corpus count dropped

`tools/validate/corpus_counts.py` failed. It fired because documents or verses
fell more than 2% against the previous manifest.

### 2.1 What it means

Almost always **`_TT` format drift**, not a real corpus change. Coptic Scriptorium
is unlikely to have deleted a fifth of itself in a week.

```bash
# how much dropped?
make -C tools validate 2>&1 | grep '\[counts\]'
```

### 2.2 Investigate

```bash
# which documents vanished or shrank?
git diff data/dist/manifest.json | less     # corpus_verses, corpus_documents, fingerprints

# find one that got small and parse it by hand
python3 - <<'PY'
import json, pathlib
m = json.load(open("data/dist/manifest.json"))
print("works:", m.get("corpus_works"), "verses:", m.get("corpus_verses"))
PY

python3 -c "
from pathlib import Path; import sys; sys.path.insert(0,'tools')
from parse.tt import parse_tt, TTParseError
try:
    d = parse_tt(Path('sources/corpora/sahidic.ruth/sahidic.ruth_TT/Ruth_01.tt'))
    print('ok', len(d.verses), 'verses')
except TTParseError as e:
    print('PARSE FAILURE:', e)
"
```

### 2.3 When to force-override

**Almost never.** A legitimate upstream release that removes a large corpus would
be announced and would appear in the release notes.

Force-override only when you have **confirmed on the upstream repository** that
the removal is intentional, and you record why:

```bash
# confirm upstream, in writing, then document the override
# 1. read the upstream CHANGELOG / release notes and paste the link into the PR
# 2. add to CHANGELOG.md:
#    "Corpus count drop accepted: <upstream link>. <what was removed and why>."
gh pr edit --add-label reviewed
```

**If you cannot confirm it upstream, it is drift. Do not merge.**

---

## 3. Suggestion Worker is down

### 3.1 Confirm reading is unaffected — do this first

```bash
curl -fsS -o /dev/null -w '%{http_code}\n' https://coptic.re/
curl -fsS -o /dev/null -w '%{http_code}\n' https://coptic.re/dict/lookup/?q=%E2%93%A7
curl -fsS https://coptic.re/data/suggestions/index.json | head -c 200
```

**All three fine means there is no outage.** A report of "the site is broken"
after a Worker deploy is usually a report about the Worker. Say so kindly and
check the form specifically.

### 3.2 Is it the Worker or GitHub?

```bash
npx wrangler tail --format pretty          # watch live
curl -fsS https://<worker>.workers.dev/api/health | jq
```

| `ok: false` | The Worker is misconfigured — a var or secret is missing. Go to §3.3 |
| `ok: true` but submissions 503 | GitHub is rejecting us. Check the token's scopes |
| timeout / DNS | Cloudflare-side. Nothing to do; the site works |

### 3.3 Rotate the token

```bash
cd workers/suggest
# create a PAT with issues:write + contents:read, then:
npx wrangler secret put GITHUB_TOKEN
npx wrangler deploy
curl -fsS https://<worker>.workers.dev/api/health | jq
```

**The token is a secret. Never `cat` it, never paste it into an issue, never log
`env`.** If you think it leaked: revoke it on GitHub first, then rotate.

### 3.4 The mailto fallback

It works throughout and needs nothing. If the Worker will not be fixed quickly,
say so on the submission panel — one line, and it defuses every report:

> Suggestions are being emailed for now. Nothing has been lost and nothing
> needs to be resubmitted.

**Never disable the `mailto:` fallback to work around a Worker outage.** It is
the guarantee that contributions cannot be lost. Removing it to simplify is how
you turn a small outage into a data-loss event.

---

## 4. Licence challenge received

### 4.1 Do not argue

Not in public, not in the issue, not on social media. **An unhelpfully
defensive first response is what turns a misunderstanding into an actual claim.**

### 4.2 Procedure

```bash
# 1. Preserve the evidence immediately
gh issue create --title "Licence challenge: <source>" \
  --body "Received <date> from <who>. Verbatim: <text>" \
  --label kind/licence,reviewer/licence,status/needs-expert,priority/high

# 2. Determine whether the item is affected
grep -n "<source-id>" data/dist/provenance/LICENSES.csv
grep -n "<source-id>" tools/validate/nc_guard.py       # is it in ALLOWED_SOURCES?

# 3. Check whether it was added with a real licence verdict
git log -p --follow -- tools/sources.lock | grep -B5 -A5 "<source-id>"
```

### 4.3 Outcomes

**If the claim is valid — remove first, argue later:**

```bash
# take it down FIRST, then respond
make -C tools emit
git commit -m "URGENT: remove <source> pending licence review"
git push                                    # deploys in ~2 min
```

Then:

```bash
mkdir -p public/licences
cat > public/licences/takedowns.md <<'EOF'
# Takedowns

## <date> — <source>

**Claim received:** <date>, from <who>, <where>.
**Affected:** <what used it — pages, entries, count>.
**Action:** removed from the site on <date>, pending licence resolution.
**Status:** open / resolved <date> — <outcome>.
**Contact:** <who responded>.
EOF
```

**Respond within 7 days**, even if only to say "we have removed it and are
investigating." Silence is the thing that escalates a claim.

**If the claim is invalid:** respond once, factually, with the licence text and
the DOI, and offer to remove it anyway if they prefer. Keep the record in
`/licences/takedowns.md` either way.

### 4.4 Then fix the process

If this got through, a gate was bypassed. Check which one, in this order:
`sources.lock` pin · licence verdict · `ALLOWED_SOURCES` · diff review. Fix the
gate, not the entry.

---

## 5. Upstream project publishes a new corpus version

```bash
# 1. Read the release notes BEFORE bumping anything
#    Coptic Scriptorium: https://github.com/CopticScriptorium/corpora/releases

# 2. Bump the pin
$EDITOR tools/sources.lock     # update [corpora] version and any sha256

# 3. Bake
make -C tools all

# 4. Read the review surface — this is the whole point of the two-stage design
git diff --stat data/dist
git diff data/dist/provenance/records.csv | less
git diff data/dist/provenance/LICENSES.csv | less

# 5. Check the counts did not collapse
make -C tools validate

# 6. Note it
echo "Bumped Coptic Scriptorium to <version>. <what changed>." >> CHANGELOG.md
```

**If verse counts *increase* and gloss counts look sane:** normal release, merge.

**If counts drop:** §2.

**If licence fields changed:** §4. A per-document licence change is the highest
consequence diff in the whole project. Read every line of the `LICENSES.csv`
diff, not a sample.

---

## 6. A page 404s in production but works locally

Almost always a **deploy-cache or base-URL mismatch**, not a missing file.

```bash
# is the file actually in the last deploy?
ls -la public/dict/c5047/index.html        # locally
curl -sI https://coptic.re/dict/c5047/ | head -3
gh run list --limit 1                     # did the last deploy succeed?
```

| Cause | Check | Fix |
|---|---|---|
| Trailing-slash mismatch | Cloudflare Pages serves `/path` and `/path/` differently for files | Use directory URLs with trailing slash consistently |
| `baseURL` wrong in the deploy | Hugo emitted absolute paths to a preview domain | Set `SITE_URL` env in Pages; never hardcode |
| Case sensitivity | `C5047.json` vs `c5047.json` | Cloudflare Pages keys are **case-sensitive**. Linux CI will not warn you |
| Stale deploy cache | — | Hard-refresh; add a cache-busting query in the test |

**Always test a case-sensitive path in CI.** It is the bug that only exists in
production.

```bash
find public -name '*.html' | head -50 | while read f; do
  [ -f "$f" ] || echo "CASE MISMATCH: $f"
done
```

---

## 7. File count approaching 15,000

```bash
find public -type f | wc -l
find public -type f | sed 's|/[^/]*$||' | sort | uniq -c | sort -rn | head -20
```

Currently ~950. CI fails at 15,000. Cloudflare Pages **Free fails at 20,000.**

**Do not raise the CI ceiling to make it pass.** The ceiling is a warning that
something is multiplying; raising it removes the only signal you get.

Usual culprits, in order:

| Multiplier | Usual cause | Fix |
|---|---|---|
| ~11,500 HTML files | someone regenerated the whole dictionary as pages | Revert. Shard reader only |
| Thousands of small JSON | one file per work instead of shards | Shard |
| Thousands of images | unoptimised, or originals committed | WebP, subset, 300 px max |
| Duplicate `_fonts` | a font imported per template | One subset woff2 |

If genuinely short of room: raise the **SEO page count** from 300 to a thousand
or two. We have ~19,000 files of headroom and that is the cheapest way to use it.

---

## 8. Michael Helmy is unreachable for 30 days

The delegation chain, from `GOVERNANCE.md` §Succession:

```
1. Deputy Maintainer #1        → acts as Maintainer. May accept, defer,
                                decline, implement. Runs review windows.
2. Deputy Maintainer #2        → if #1 is also unreachable.
3. Lead Steward                → may triage, label, dedupe.
                                MAY NOT accept, decline, or implement.
                                SHIPS NOTHING. Publishes a status note.
4. Institutional custodian     → asked IN ADVANCE, in this order:
     a. Coptic Orthodox Diocese (Southern USA)
     b. KELLIA alliance (Göttingen / FU Berlin / BBAW)
     c. Coptic Scriptorium (Georgetown / U Pacific)
```

**Step 3 is deliberately powerless.** If the Maintainer and both deputies are
gone, the correct action is to **stop shipping**, not to let a Steward guess at
curation decisions. A Steward who can approve is a Maintainer who was never
appointed.

```bash
# Step 3: the status note. Post it, change nothing else.
gh issue create --title "Project status: maintainer unavailable" \
  --body "Michael Helmy has been unreachable since <date>. Triaging continues.
         Nothing is being merged or implemented during this period.
         Reading and all suggestions are unaffected. Next update within 14 days."

# Step 4: the custodian request. Send this BEFORE you need it.
```

**How long is too long?** 14 days without a status note is how a community
assumes abandonment. Post one every two weeks, even if the news is "no change."

**If a Deputy has never been named** — the succession commitments were missed.
That is the failure this chain exists to prevent. Escalate to the institutional
custodian list rather than inventing a Maintainer.
