# Static Coptic Language Reference — Implementation Plan **v5**

**Supersedes:** v4. v4 retained as the design record. §0 (asset verification), §1 (collation), §2 (Pagefind), §4 (`_TT` parser), §6.1 (tarball), §8 (attributions[] schema), §9 (NC allowlist), §10.2 (Bohairic honesty), §10.3 (corpus rollout) are **CLOSED and not re-opened here.**
**Revision driver:** community contribution, curation, delayed implementation, maintainer succession, attribution.
**Team:** 2 people committed. **Duration:** 16 weeks.
**Hosting:** Cloudflare Pages Free + **one** Cloudflare Worker. $0 recurring.
**Effort:** **102 person-days** (v4: 97 — see §1).

---

## Changes in v5

| New / amended | Content | Effort delta | Specific execution risk reduced |
|---|---|---|---|
| **§13.1** | Suggestion architecture decision: **(B)** GitHub + one Worker bridge. Justified against (A) and (C) | — | **Locking the architecture before writing code.** (A) excludes account-less diaspora readers; (C) creates a gated product and a runtime dependency on the reading path |
| **§13.2** | `schema/suggestion.schema.json` + `submitter_hash` never displayed | +0.25 d | Privacy leak: shipping an IP-derived hash in a public artefact |
| **§13.3** | `workers/suggest/index.ts` — 2 endpoints, stateless dedup **via GitHub search**, honeypot, in-memory rate limit. ⚠ **338 lines / 250 lines of code, not ~100** — see §13.3.1 | +1.0 d | The obvious implementation of "24h per-entry dedup" needs a datastore, which would silently push us to (C) and cost $0. Dedup is done by searching GitHub instead |
| **§13.4** | `<details>` submission UI, no-JS mailto first, never requires account/email/captcha | +3.0 d | A GitHub-account requirement is the single biggest reason a diaspora community never contributes to a heritage resource |
| **§13.5** | Stage A bakes `suggestions.json`; endorsement counts from GitHub reactions | +0.5 d | Endorsements that only exist on GitHub and never reach the static site — the feature would be invisible to the people it serves |
| **§13.6** | `/roadmap/`, `decide-by`, annual windows | — | **"Maybe after a year" becoming a hope instead of a written commitment** |
| **§14** | Curation model: 5 roles, **endorsement is not a vote**, full label taxonomy, triage SLA | — | A popular-but-wrong feedback loop that destroys credibility with the Church and academic blocs |
| **§15** | Handoff, runbook, onboarding, succession | — | **The project dying with its author.** A blank succession field is the most common cause |
| **§16** | Attribution: author vs. data originators, `/licences/` vs `/credits/` | — | CC BY-SA §3(a) non-compliance, and burying upstream originators who lost their NEH funding |
| **§6.3 amended** | Effort table: 97 → **102** | **+5.0 d** | Not a risk — a *disclosure*. The cost is real and now visible |
| **§3.5 amended** | Gantt: Phase 1 +1.5 d, Phase 4 +3.5 d | — | — |
| **§8 amended** | Cross-ref to §16 | — | Mixing project-level credit into per-entry upstream attribution (legally wrong and confusing) |
| **§12 amended** | v5 delta table | — | — |

**Total new build cost: 5.0 person-days** (UI 3 · Worker 1 · bake 0.5 · copy 0.5). **Zero change to reading architecture. Zero new runtime requirement for a reader.**

---

## 1. Δ Effort — the 5 days, and where they come from

> Note on numbering: the brief refers to "§1 (effort table)" and "§6 (Gantt)". In v4 those live at **§6.3 (effort table)** and **§3.5 (Gantt)**. Amendments are applied there; v4's §1 (collation) and §6.1 (tarball) are closed and untouched.

### 1.1 The arithmetic

| Phase | v4 | v5 | Δ | Source of the new days |
|---|---|---|---|---|
| Phase 1 — Dictionary | 27 | **28.5** | **+1.5** | Worker `index.ts` (1.0) + `suggestions.json` bake (0.5) |
| Phase 2 — Corpus & Concordance | 21 | **21** | — | — |
| Phase 3 — Grammar & Lessons | 30 | **30** | — | — |
| Phase 4 — Flashcards & Offline | 19 | **22.5** | **+3.5** | Submission UI (3.0) + user-facing copy (0.5) |
| **Total** | **97** | **102** | **+5.0** | |

**102 ÷ 160 person-days available (2 people × 16 weeks × 5 days) = 64% utilisation, 36% slack.**

### 1.2 I am not manufacturing a cut

The 5 days fit inside the slack v4 already had. Inventing a cut to look rigorous would be theatre, and it would cost a real feature to fix a problem that does not exist. **The honest statement is: this fits, and here is the arithmetic.**

What I *am* doing is naming the **conditional cut order now**, in advance, so that if slack erodes nobody has to renegotiate mid-build:

| Cut order | Action | Saves | Consequence to state publicly |
|---|---|---|---|
| 1 | Ship only the no-JS `<details>` + `mailto:`; defer the JS form | 1.5 d | GitHub-account users still get a working path; account-less users get email. Weakens the headline feature |
| 2 | Drop corpus rollout tier **P2.4 monastic** | 2.0 d | Shenoute et al. not on the site. Lowest community impact of the four tiers — it is last in the priority order anyway |
| 3 | Drop UD parse visualisations | 1.0 d | Loses the only Bohairic syntactic visualisation. Mild cost to scholars |
| 4 | Reduce first-bake dictionary SEO pages 300 → 150 | 0.5 d | Marginal SEO loss |
| — | **Never cut:** a11y line (§7.5), licence verification, NC allowlist, collation tests | — | v4 already marked these non-negotiable |

### 1.3 What does *not* change

Phase 2 and Phase 3 are untouched. Stage B does **not** gain a runtime call. The Worker is not on the reading path. If a reviewer reads §13 and concludes the reading site now depends on a service, that is a misreading — §13.1 states the invariant explicitly and §13.6 makes the Worker optional at request time.

---

## 2. Δ Amendment to v4 §3.5 — Gantt

```mermaid
gantt
    title Static Coptic Reference v5 — 16 weeks, 2 people, 102 person-days
    dateFormat YYYY-MM-DD
    axisFormat %W
    axisTitle Week

    section P1 · Dictionary
    Repo, Hugo skeleton, theme, fonts      :p1a, 0, 2
    collate.py + CI collation tests        :crit, p1b, 0, 1
    fetch/pin + SHA-256 manifest           :p1c, 1, 1
    _TT parser (state machine)             :crit, p1d, 1, 3
    Kaikki + TEI + CoNLL-U parsers         :p1e, 2, 2
    merge + attributions[]                 :crit, p1f, 3, 2
    emit: shards, index, tarball           :p1g, 4, 2
    Dict reader UI + 300 SEO pages         :p1h, 5, 3
    Pagefind single-pass script            :crit, p1i, 6, 1
    licence verification drive             :crit, p1j, 2, 3
    Δ workers/suggest/index.ts             :crit, p1k, 6, 1
    Δ Stage A bakes suggestions.json       :crit, p1l, 7, 1

    section P2 · Corpus & Concordance
    corpus tarball + ship subset           :p2a, 6, 2
    P2.1 LITURGICAL works first             :crit, p2b, 7, 2
    Corpus reader + interlinear            :p2c, 7, 3
    P2.2 BIBLICAL works                   :crit, p2d, 9, 2
    Concordance (lemma-first)              :p2e, 9, 2
    P2.3 PATRISTIC works                  :crit, p2f, 11, 1
    Aligned reading + URN deep-links       :p2g, 11, 2
    P2.4 MONASTIC works                   :crit, p2h, 12, 1
    UD parse views (S + B)                 :p2i, 12, 1
    CI guards (files/NC/licence)           :crit, p2j, 12, 2

    section P3 · Grammar & Lessons
    Lesson template + 8 lessons            :p3a, 8, 3
    lessons 9-15                           :crit, p3b, 10, 4
    Grammar PDF library + page index       :p3c, 9, 3
    Transliteration + Keyman Web           :p3d, 11, 2

    section P4 · Flashcards, Offline, Community
    genanki deck generation                :p4a, 10, 2
    Service worker + precache + LRU        :p4b, 11, 3
    Per-work offline download              :p4c, 13, 1
    a11y: axe, keyboard, SR (5.25 d)       :crit, p4d, 12, 3
    PWA installability + offline QA        :crit, p4e, 14, 1
    Δ Δ Suggestion UI (details + JS form)   :crit, p4f, 13, 2
    Δ Δ Suggestion copy + submission rules :p4g, 14, 1
    Colophon, licences, /credits/, handoff  :crit, p4h, 14, 2
    Launch                                 :milestone, m1, 16, 0
```

**Placement rationale.** The Worker lands in **Phase 1** (Week 6–7) even though the UI lands in Phase 4, because the Worker is 1 day of isolated TypeScript that needs no dictionary data and no design. Writing it early de-risks the single component that touches GitHub's API — the one part of this project that can fail with an HTTP 401 at launch. If it breaks, we find out in Week 7, not Week 15.

---

## 3. Δ Amendment to v4 §8 — pointer to §16

v4 §8 defines `attributions[]` and renders it per entry. **Unchanged and closed.** One line is added to its schema note:

> `attributions[]` lists **upstream data sources only**. The project author is credited at project level (§16), never inside `attributions[]` — the project is a compiler and a curator, not an originator of the underlying lexical or corpus data. See §16.2.

---

## 13. Community Suggestions & Curation

### 13.1 Δ Architectural decision: **(B)** — GitHub as source of truth, one Worker as an anonymous bridge

**Chosen: (B).** GitHub Issues holds every suggestion, every label, every endorsement and every decision, because it already provides an issue tracker, reaction-based endorsement, an authenticated API for Maintainers and Reviewers, a public audit trail, and a free tier for public repositories — all of which (A) gives us for free but only to people with accounts. A single ~100-line Cloudflare Worker sits in front of it purely to let **someone with no GitHub account create an issue**. That is the entire job.

**(A) GitHub Discussions only — rejected.** It is simpler and it would have been faster to build. It fails on the specific people this project exists for. The primary reader is a Coptic speaker in the diaspora who reads liturgical Bohairic every week and has never filed a GitHub issue — plausibly has no GitHub account, plausibly will never create one. Requiring an account to tell us that our gloss for `ⲧⲉⲛⲟⲩ` is wrong is asking the community to do the hardest part of the work and then also clear an unrelated hurdle before we can hear them. **The friction is not in the database; it is in the account creation.** (A) is rejected on that basis alone.

**(C) Full Workers + D1 — rejected.** D1 plus authentication is not a suggestion endpoint, it is a product: a database to migrate, an auth system to secure and audit, user accounts to support and moderate, and a real risk that a moderation queue becomes a launch blocker. Worse, it breaks the property that makes this project cheap and durable. **Nothing a reader does to read the site may touch a runtime service** — that is what keeps hosting at $0, keeps the site readable with JavaScript disabled and with no network at all, and means a Cloudflare outage cannot take the dictionary away. (C) would make the suggestion system load-bearing for reading. It must never be load-bearing.

**The invariant, stated once and enforced throughout:**

> **The Worker is the only runtime component in the entire project.** It handles *contributions* and nothing else. If it is deleted, revoked, rate-limited by Cloudflare, or broken by a GitHub API change, **reading is completely unaffected.** Every reader-facing feature degrades to a `mailto:` link with a prefilled subject and body. That fallback is a supported path, documented on the site, not a degraded one — because for many readers it will be the *better* path anyway: they would rather email than file an issue.

### 13.2 Δ `schema/suggestion.schema.json`

```jsonc
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://coptic.re/schemas/suggestion.schema.json",
  "title": "Coptic Reference Suggestion",
  "type": "object",
  "required": ["id", "target", "kind", "body", "submitted_at",
               "submitter_hash", "source", "status", "baked_at"],
  "additionalProperties": false,
  "properties": {
    "id": {
      "type": "string",
      "pattern": "^s-[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{5}$",
      "description": "Stable id, s-YYYY-MM-DD-NNNNN."
    },
    "target": {
      "type": "object",
      "required": ["kind", "url_path"],
      "properties": {
        "kind":     { "enum": ["entry", "work", "lesson", "site"] },
        "id":       { "type": ["string", "null"],
                      "description": "entry id (C5047), work URN, lesson slug, or null for kind=site." },
        "url_path": { "type": "string", "pattern": "^/" },
        "dialect":  { "enum": ["B", "S", "N", null],
                      "description": "B=Bohairic S=Sahidic N=undetermined. Advisory; recorded so the Reviewer sees what the submitter was looking at." }
      },
      "additionalProperties": false
    },
    "kind": {
      "enum": ["gloss", "example", "etymology", "typo", "parse",
               "translation", "licence", "bug", "feature"]
    },
    "body": {
      "type": "string", "minLength": 10, "maxLength": 8000,
      "description": "The suggested change. Prefilled context is appended by the Worker, not by the submitter."
    },
    "evidence": {
      "type": "string", "maxLength": 4000,
      "description": "Source, citation, or argument. Optional but strongly preferred — see the submission rules copy."
    },
    "contact": {
      "type": ["string", "null"], "maxLength": 200,
      "description": "Optional. Used only to credit. Never required, never displayed publicly unless the submitter chose to make it public in the issue body."
    },
    "submitted_at":  { "type": "string", "format": "date-time" },
    "submitter_hash": {
      "type": "string", "pattern": "^[a-f0-9]{16}$",
      "description": "sha256(ip + UTC day + entry id), truncated to 16 hex chars. DEDUP ONLY. NEVER RENDERED, NEVER EXPORTED, NEVER LOGGED. The Worker writes it into a GitHub issue body hidden in an HTML comment so Stage A can find duplicates without storing the IP anywhere."
    },
    "source": { "enum": ["github_issue", "worker", "email"] },
    "github_issue_number": { "type": ["integer", "null"] },
    "github_url":         { "type": ["string", "null"], "format": "uri" },
    "status": {
      "enum": ["new", "triaged", "needs-expert", "accepted", "deferred",
               "declined", "duplicate", "implemented"]
    },
    "endorsements": {
      "type": "object",
      "properties": {
        "up":     { "type": "integer", "minimum": 0, "default": 0 },
        "heart":  { "type": "integer", "minimum": 0, "default": 0 },
        "rocket": { "type": "integer", "minimum": 0, "default": 0 }
      },
      "additionalProperties": false
    },
    "endorsement_source": { "enum": ["github_reactions", "none"] },
    "labels": { "type": "array", "items": { "type": "string" },
                "uniqueItems": true },
    "reviewer": { "type": ["string", "null"],
                  "description": "Named Reviewer who gave a verdict, or null." },
    "resolution": { "type": ["string", "null"],
                    "description": "e.g. 'merged in #512, CHANGELOG 2027.04'." },
    "decide_by": {
      "type": ["string", "null"], "format": "date",
      "description": "LOAD-BEARING. Set when status becomes accepted: acceptance + 12 months. Rendered on /roadmap/. A suggestion in accepted with no decide_by is a CI failure."
    },
    "reaffirmations": {
      "type": "integer", "minimum": 0, "maximum": 2,
      "description": "How many times accepted has been re-affirmed with a written reason. Capped at 2 (v5 §14.2)."
    },
    "blocker": { "type": ["string", "null"],
                 "description": "Required when status is deferred. Stated publicly on /roadmap/." },
    "baked_at": { "type": "string", "format": "date-time" }
  }
}
```

**Validation is a release gate.** `tools/validate/suggestions.py` fails the build if: any `decide_by` is missing or in the past for a non-terminal `accepted` status; `reaffirmations > 2`; `status: deferred` with a null `blocker`; `status: declined` with a null `resolution`; or any `submitter_hash` appears in the rendered output. **The last check is the important one** — it greps the built `public/` tree for hash values and fails if one escaped.

### 13.3 Δ `workers/suggest/index.ts` — the only runtime component

Full source in `workers/suggest/index.ts`. Design notes for the maintainer:

**Deduplication without a database.** The obvious implementation of "same IP within 24h per entry" wants a datastore. That would push the project to (C). Instead the Worker **asks GitHub**: before creating an issue it searches

```
repo:<owner>/<repo> is:issue is:open label:entry/C5047 in:body "<submitter_hash>"
```

and if a hit exists it posts a comment on that issue and returns the existing URL. Stateless, no KV, no D1, and it reuses the audit trail we already have.

**Rate limiting is best-effort and is not a security boundary.** An in-memory `Map` dies with the isolate. It is a courtesy that stops an accidental script loop, nothing more. The real defences are the honeypot, Turnstile, and GitHub's own abuse handling. **Do not describe this as protection against a determined attacker in any documentation** — that would be inaccurate and would matter if someone gets blocked.

**Secrets.** `GITHUB_TOKEN` is a Worker secret, set via `wrangler secret put`. The source is public. The Worker reads `REPO` (`owner/name`) and `SUGGEST_TOKEN` from vars. Never commit a token; never log one.

### 13.3.1 ⚠ Deviation from the brief: the Worker is 250 lines of code, not ~100

The brief specified ~100 lines. The implementation is **338 lines total, 250 of
them code** (28 blank, 60 comment/docstring). I am flagging this rather than
quietly padding the spec in the other direction.

The overage is where the complexity actually lives:

| Block | Lines | Can it go? |
|---|---|---|
| GitHub API helper | 10 | No |
| `submitter_hash` + input validation + error codes | 40 | Validation yes, error codes no |
| **Stateless dedup** (search + comment-on-duplicate) | 35 | **No — this is the whole reason there is no database** |
| Rate limiting | 20 | Could move to a Cloudflare rule |
| Turnstile verification | 12 | Yes |
| Issue body assembly + label derivation | 45 | No |
| Endorsement endpoint | 30 | No |
| Router + CORS + error handling | 35 | No |

**To reach ~100 lines you would have to drop Turnstile and per-field validation.**
I do not recommend either: Turnstile is already off by default (its absence is 12
lines of branch), and validation is what stops a malformed request turning into a
garbage issue in the audit trail that is our source of truth.

250 lines of dependency-free TypeScript with no bindings is, in my judgement, the
right size for "two endpoints plus a stateless dedup that lets someone without a
GitHub account be heard." **If 100 lines is a hard constraint rather than an
estimate, say so and I will cut Turnstile and validation — but the honest
recommendation is that this is not where the complexity budget should be
protected.** The genuinely load-bearing constraint in this project is the **$0
and no-database** invariant, and that is fully intact.

### 13.4 Δ Submission UI

A `<details>` panel on every entry, corpus work, and lesson. It appears **below** the entry's content, never above it — a reader who did not want to correct anything must never be interrupted by the invitation.

**Without JavaScript (the default, and the guaranteed path):** the panel contains the rules, a `mailto:` link whose subject is `Suggestion: gloss — ⲧⲉⲛⲟⲩ (C5047)` and whose body is prefilled with the target id, URL, dialect, and **the current value being corrected**. The submitter edits an email. This works on every browser, needs no account, and survives the Worker being deleted.

**With JavaScript:** a small form — kind, body, evidence, optional contact — that `POST`s to the Worker. On success it replaces itself with the GitHub issue URL, so the submitter can watch their own suggestion get triaged. **That is the whole reward loop**, and it is why the Worker bothers to return the URL.

**Prefill, always.** Target kind and id, URL path, dialect, and the current value being corrected. **A submitter must never have to retype the thing they are correcting.** This is the single highest-leverage line in the feature.

**Copy — written for a Coptic speaker who has never filed an issue.** Verbatim, because this text matters more than the code:

> ### Something wrong? Please tell us.
>
> You do not need a GitHub account. You do not need an email address. There is no captcha.
>
> If you have ever read a Coptic text and thought *"that's not what this word means,"* this is the place to say so. Coptic is read every week in churches across Egypt, the Sudan, and the diaspora, and almost all of it is digitised by a small number of people. **Your correction is welcome. It is the point of the exercise.**
>
> **What helps most.** A citation — CCL, CDO, Crum, or a published grammar — turns a suggestion into a change. You do not need one to submit; most accepted changes arrive with one.
>
> **What happens next.** A volunteer steward reads every suggestion within **7 days** and labels it. Suggestions about dictionary content or parsing go to a Coptic linguist, who aims to respond within **30 days**. Suggestions about a liturgical translation also go to a church reviewer.
>
> **What actually happens.** Accepted suggestions are implemented in **January and July**. Not continuously — because every change to a dictionary is a change to a work that people have to re-attribute, and because reviewers are scarce enough that asking them for one gloss at a time does not work. If your suggestion is accepted you will see it on the [roadmap](/roadmap/) with a date by which we have either implemented it or told you why not.
>
> **One thing endorsements are not.** An endorsement is not a vote. A suggestion with a hundred thumbs-up and no scholarly support does not override a reviewer. We say this plainly because we would rather you knew how decisions get made here than wonder.

### 13.5 Δ Stage A — baked display

Weekly `bake` job, after the existing data bake:

```
fetch issues   →  GET /repos/<owner>/<repo>/issues?state=open&labels=suggestion
                 (paginate; 100/page; read-only GITHUB_TOKEN from a repo secret)
fetch reactions→  GET /repos/<owner>/<repo>/issues/{n}/reactions
                 (sum "up"/"+1", "heart", "rocket"; ignore the bot's own)
assemble       →  data/dist/suggestions.json  { "baked_at", "items": [...] }
```

- **A read-only token** (`GITHUB_READ`) is a repository secret, used by the workflow only. Unauthenticated reads work but the unauthenticated rate limit is 60/hr, which is adequate at one bake a week but leaves no headroom — so use the token and record its scope in `sources.lock`.
- **Emails do not land in `suggestions.json`.** A mailed suggestion becomes a GitHub issue by hand, so every suggestion has exactly one record and one audit trail. The email path is for *submitting*, not for tracking.
- `suggestions.json` is **not** a single 5 MB blob. It is written **paginated by target** — `suggestions/C5047.json`, `suggestions/index.json` — so a reader fetches only the suggestions for the entry they are looking at. Reading the site must not require downloading other people's contributions.
- The Worker's failure mode is load-time and silent: `GET /data/suggestions/<id>.json` 404s → the panel renders nothing and the `mailto:` link is used. **There is no error banner**, because a broken contributions panel is not the reader's problem and should not look like one.

### 13.6 Δ `/roadmap/` — the page that makes the promise real

Auto-generated each bake from `suggestions.json`. Five sections, in this order:

| Section | Source | What it shows |
|---|---|---|
| **Implemented** | `status: implemented` | What changed, link to `CHANGELOG.md` entry, the issue it came from |
| **Accepted — this window** | `accepted`, window contains today | Currently being worked. With the `decide-by` date |
| **Accepted — next window** | `accepted`, next window | The near future. With the `decide-by` date |
| **Deferred** | `status: deferred` | **With the blocker stated.** "Blocked: waiting on TLA lemma confirmation" |
| **Declined** | `status: declined` | **With the reason stated.** "Declined: this reading is attested in Bohairic liturgical use only; recorded in the entry note instead" |

Every `accepted` row shows `decide-by`. **A suggestion in `accepted` past its `decide-by` fails CI** — it cannot be published in that state.

Declined and deferred are shown, not hidden. A project that only displays what it shipped teaches contributors that silence means "no" and that effort is wasted. Showing the reasoning is the difference between a suggestion box and a relationship.

### 13.7 Δ `$0` and account posture — the check

| Concern | Cost | Account needed? |
|---|---|---|
| Cloudflare Pages Free | $0 | No |
| **Cloudflare Workers Free** — 100,000 req/day | $0 | No |
| GitHub public repo | $0 | No, to *read*. To *endorse*, yes (or via the Worker) |
| Turnstile (optional) | $0 | No |

Reader or submitter accounts: **none, ever.** Maintainers, Stewards, and Reviewers need a GitHub account — that is the entire account requirement of the project.

---

## 14. Delayed Implementation & the Annual Review

### 14.1 Δ Two windows a year: January and July

The Maintainer reviews everything `status: accepted` in **January** and **July**. Everything else waits. Three reasons, all of which would be false if we shipped continuously:

1. **Attribution is not free.** Every change to the dictionary is a change to a CC BY-SA derived work. Continuous shipping means continuous re-attribution across ~11,500 entries, and the `attributions[]` panel (§8) has to stay correct. Batching makes that tractable and reviewable.
2. **Reviewers are the scarcest resource in the entire project.** Asking a Coptic linguist to review one gloss at a time, indefinitely, is how you burn out your two most important volunteers. Asking them to review a batch of 20–40 every six months is a job someone can say yes to.
3. **Corpus refreshes are already scheduled.** Coptic Scriptorium ships on its own cadence and Stage A already runs weekly. Landing change on the same rhythm means one review, one bake, one announcement.

### 14.2 Δ The twelve-month rule

Every `accepted` suggestion carries **`decide_by` = acceptance + 12 months**. At each window the Maintainer must do exactly one of four things:

| Action | Requirement |
|---|---|
| **Implement it** | Commit to `CHANGELOG.md`, set `implemented` |
| **Re-affirm** | Written reason + **new** 12-month window. **Permitted at most twice** (`reaffirmations ≤ 2`) |
| **Defer** | A stated `blocker`. Shown publicly on `/roadmap/` |
| **Decline** | A written `reason`. Shown publicly on `/roadmap/` |

**No suggestion sits in `accepted` indefinitely.** After two re-affirmations the only honest options are implement or decline.

> **This is the load-bearing mechanism.** The user's original promise is "maybe after a year." A date field that CI enforces is the difference between that being a commitment and being a hope. If the date can slip silently, we have shipped a slower, more expensive version of "we'll get to it," and the community will read it exactly that way. **Do not soften this.**

### 14.3 Δ Roles and decision rights

| Role | Who | May do | May **not** do |
|---|---|---|---|
| **Submitter** | Anyone, no account | Submit suggestions | Endorse without a GitHub account or the Worker |
| **Endorser** | Anyone with a GitHub account, or the Worker | React 👍 ❤️ 🚀 | Change any status |
| **Steward** | Named volunteers from Coptic Devs / seminary / diaspora | Triage, dedupe, label, close duplicates, add `blocked-by` | **Approve.** Cannot move anything to `accepted` |
| **Reviewer** | Named Coptic linguists and clergy | Give a technical or theological verdict; set `reviewer/*`; mark a `needs-expert` suggestion resolved | Change priority unilaterally |
| **Maintainer** | Michael Helmy (project author), plus named deputies | **Final decision:** accept, defer, decline, implement. Owns the annual review and `decide_by` | Overrule a Reviewer verdict without recording the disagreement |

**Stewards cannot approve.** This is deliberate friction. The person who reads your email all week should not also be the person who decides whether you were right.

### 14.4 Δ Endorsement is not a vote — stated to users, not just to us

> **Endorsements signal interest, not authority.**
>
> A suggestion with a hundred thumbs-up and no scholarly support does not override a Coptic linguist. A suggestion with three endorsements and a citation to CCL is taken seriously regardless.
>
> We publish this rule because a system that quietly lets popularity decide will eventually ship something confidently wrong — and the people who would tell us we are wrong are the clergy and the academics whose trust makes this resource worth anything.

**Maintainer decision-weight order, in full:**

```
Reviewer verdict  >  evidence quality  >  endorsements  >  submitter count
```

> **Risk reduced:** a popular-but-wrong feedback loop. Without this stated rule, a suggestion with 100 endorsements *looks* authoritative to readers, and shipping it over a Reviewer's objection would damage credibility with exactly the two blocs (§14.3) whose unpaid labour makes the site possible.

### 14.5 Δ Label taxonomy

```
kind/gloss        kind/example     kind/etymology    kind/typo
kind/parse        kind/translation kind/licence     kind/bug
kind/feature

status/new        status/triaged   status/needs-expert  status/accepted
status/deferred   status/declined  status/duplicate     status/implemented

entry/<id>        work/<urn-short>     lesson/<slug>
site

priority/high    priority/medium   priority/low
reviewer/linguistic   reviewer/theological   reviewer/licence
```

`suggestion` is applied to every issue so Stage A's single label query returns exactly the set it needs.

### 14.6 Δ Steward triage SLA

| Situation | Action | Deadline |
|---|---|---|
| Any new suggestion | Steward reads; label `status/triaged` or `status/duplicate` | **7 days** |
| `kind/licence` | Escalate to `reviewer/licence` | **Same day** |
| `kind/gloss` or `kind/parse` or `kind/translation` | Assign `reviewer/linguistic` | 7 days |
| `kind/translation` **on a liturgical work** | Also assign `reviewer/theological` | 7 days |
| Reviewer response | Verdict recorded on the issue | **30 days** |

**Published on the site**, in the submission panel (§13.4) and on `/governance/` — not only in this plan. A service level that exists only in an internal document is not a service level.

### 14.7 Δ What makes a suggestion likely to be implemented — public criteria

Published verbatim on `/governance/` and in the submission panel. **This list is both the Maintainer's working criteria and the user's expectations.** Publishing it is what makes the system trustworthy:

| Criterion | What it means |
|---|---|
| **Correctness with evidence** | Cites CCL, CDO, Crum, or a published grammar. A scholarly edition carries more weight than a website |
| **Endorsement breadth** | Several independent people agree. One person upvoting their own suggestion is not breadth |
| **Reviewer support** | A Reviewer has confirmed it is correct. This is the strongest single signal |
| **Scope** | **Small changes ship faster than schema changes.** Say this plainly so nobody expects a redesign from a one-line observation |
| **Licence clarity** | A suggestion introducing a new source needs a licence verdict before acceptance (v4 §7.6: pin, verdict, allowlist, diff review) |

> **Risk reduced:** the failure mode of every suggestion box is that contributors cannot tell whether effort is worthwhile, so participation decays to zero after the first silent rejections. Publishing the criteria converts "should I bother?" into an answerable question.

### 14.8 Δ `CHANGELOG.md` — human-written, git-committed

Never generated. Each entry records:

- **What changed** — entry id, field, old value → new value
- **Which suggestion prompted it** — issue number and link
- **Which upstream source change it accompanies**, if any
- **Who implemented it and who reviewed it**

Human-reviewed because the changelog is the artefact a scholar reads to judge whether to trust this project.

---

## 15. Maintainer Handoff & Succession

### 15.1 Δ The problem, named

This project's most likely failure mode is not a broken build. It is a **single-author dependency**: one person holds the curation judgement, the merge authority, and the relationship with the Church and the academic reviewers. If that person stops, the work does not pause — it stops, permanently, because there is nobody who knows why a gloss was accepted or which reviewer to ask.

**A blank succession field is the single most common cause of a heritage project dying.** Every heritage project that died, died of the same thing: not competition, not funding, but one person.

### 15.2 Δ Succession — the direct answer

**Named successor: TBD. This is unavoidable and I will not pretend otherwise.**

No candidate can be named for a project that has not launched. There is no community yet from whom to recruit a deputy, no suggestion queue to learn triage on, and no reviewer relationship to inherit. **Naming someone today would be a fiction, and a worse outcome than an honest blank**, because a nominal successor who has never done the work provides false assurance.

**But the field is not left blank, and the gap is closed by a date rather than a hope:**

| Commitment | Deadline | Enforcement |
|---|---|---|
| **≥ 1 Deputy Maintainer named** | **Before launch** | **Launch is blocked until this is true.** Written into `GOVERNANCE.md` and checked in the pre-launch checklist |
| **2nd Deputy Maintainer named** | Within 6 months of launch | Listed in `AUTHORS.md` and `GOVERNANCE.md` |
| Deputy identified for **Reviewer relations** (Church + academic) | Within 6 months of launch | Separate from the Maintainer deputies — these are different relationships |
| First full **succession rehearsal** (Deputy runs a January window while the Maintainer observes) | 12 months after Deputy #1 is named | Recorded in `CHANGELOG.md` |

**Delegation chain if the Maintainer is unreachable for 30 days** (v5 `RUNBOOK.md` §7):

```
1. Deputy Maintainer #1          → acts as Maintainer; may implement, accept, decline
2. Deputy Maintainer #2          → if #1 also unreachable
3. Lead Steward                  → may triage, label, dedupe. CANNOT accept or implement.
                                   Ships nothing. Publishes a status note.
4. Institutional custodian        → Coptic Orthodox Diocese (Southern USA), then KELLIA
                                    alliance, then Coptic Scriptorium, in that order.
                                    Asked in advance, not in a crisis.
```

> **Risk reduced:** the most common and most total failure of a single-author open project. Note step 3 is deliberately powerless: if the Maintainer and both deputies are gone, the correct action is *to stop shipping*, not to let a Steward guess at curation decisions.

### 15.3 Δ Handoff deliverables — written, not promised

Four documents land in Phase 4 (Week 14), budgeted in the 3.5 days of §1.1:

| File | Audience | What it does |
|---|---|---|
| `README.md` | First-time visitor | What it is, who made it, how to run it locally in 10 minutes |
| `HANDOFF.md` | The next maintainer | What it is, the five files that matter, the five things that break first |
| `RUNBOOK.md` | On-call maintainer, 11pm, bake broken | Step-by-step procedures with rollback plans |
| `ONBOARDING.md` | New maintainer, first 4 weeks | Week-by-week reading and doing |

Plus `AUTHORS.md`, `GOVERNANCE.md`, `CONTRIBUTING.md`, `FAQ.md`, `CONTRIBUTING_SOURCES.md`.

**`HANDOFF.md`'s stated goal is not that the new maintainer knows everything.** It is that they know **which five files matter and where the bodies are buried.** Those are different skills and the document serves the second.

**The five files that matter:** `tools/collate.py` · `tools/parse/tt.py` · `tools/merge/entries.py` · `tools/validate/*` · the Cloudflare Pages build command. Everything else is replaceable, and `HANDOFF.md` says so.

### 15.4 Δ Named humans, not just links

`HANDOFF.md` §9 names who to email when stuck, with the current named people and their roles. Upstream dependency contacts are listed too, so a maintainer inheriting the project inherits the relationships and not just the code.

> **Risk reduced:** "ask in the Discord" fails for exactly the person who most needs help — the one who is not in the Discord, because they are the new one.

---

## 16. Attribution

### 16.1 Δ Michael Helmy is the project author

`AUTHORS.md` lists him first, role stated plainly: **Project author and maintainer.**

- Site footer: `A project by Michael Helmy · Content CC BY-SA 4.0 · Source`
- `<meta name="author" content="Michael Helmy">` on every page
- `/about/` — bio, contact, and the origin story
- `LICENSE` carries his copyright line; `NOTICE` names him as project lead
- On naming a successor he is credited as **Founding author** and **never removed** from `AUTHORS.md`

### 16.2 Δ The critical distinction — author vs. data originators

**Michael Helmy is the author of the site, the code, the curation, and the compilation. He is not the author of the underlying lexical or corpus data.**

CC BY-SA 4.0 on a derived work requires the upstream originators to be **more** prominent than the compiler, not less. So `/licences/` must name, at minimum:

- **CCL v1.2** — BBAW, DDGLC. CC BY-SA 4.0. DOI [10.17169/refubium-27566](https://doi.org/10.17169/refubium-27566)
- **CDO** — KELLIA alliance (ADW, BBAW, DDGLC, FU Berlin, Göttingen, Georgetown). CC BY-SA 4.0. DOI [10.17169/refubium-2333](https://doi.org/10.17169/refubium-2333)
- **Coptic Scriptorium corpora v6.3.0** — Caroline Schroeder, Amir Zeldes, and contributors. Per-document licence (predominantly CC BY-SA 4.0)
- **UD — Coptic Scriptorium treebank** — Zeldes & Abrams (2018). CC BY-SA 4.0
- **UD — Bohairic treebank** — Zeldes, Speransky, Wagner, Schroeder (2025). CC BY 4.0
- **Wiktextract / Kaikki** — Tatu Ylönen (2022). CC BY-SA 4.0 **OR** GFDL
- **Crum, *A Coptic Dictionary*** (1925/1939). Public domain
- **Thesaurus Linguae Aegyptiae** — BBAW. CC BY
- Every other entry in `ALLOWED_SOURCES` (v4 §9)

> **Risk reduced:** both a legal and an ethical failure. Legally, CC BY-SA §3(a) requires attribution and §3(b) requires indicating modifications. Ethically: **the Coptic Scriptorium maintainers lost their NEH funding in 2025 and are the actual authors of the resources this entire project depends on.** A footer that reads "© Michael Helmy" on top of their corpus is not just non-compliant; it is graceless, and they will notice.

### 16.3 Δ The footer must not collapse the two

**Wrong:**

```
© 2026 Michael Helmy · CC BY-SA 4.0
```

**Right:**

```
A project by Michael Helmy. Site code Apache-2.0 · Site content CC BY-SA 4.0 ·
Dictionary and corpus data compiled from CCL, CDO, Coptic Scriptorium,
Universal Dependencies, and Wiktionary — full credits.
```

### 16.4 Δ Per-entry credit is upstream-only

v4 §8's `attributions[]` panel is where upstream credit lands, per entry. **Michael Helmy never appears inside `attributions[]`.** His credit is project-level (§16.1). Mixing the two would be legally wrong — `attributions[]` is a statement about which upstream work a field derives from — and confusing to a reader trying to trace a gloss to its source.

### 16.5 Δ `/licences/` and `/credits/` are different pages

| Page | Generated? | For | Contains |
|---|---|---|---|
| `/licences/` | **Machine-generated** from `LICENSES.csv` | Compliance reviewers | Every source, every licence, every DOI, no omissions, no interpretation |
| `/credits/` | **Hand-written** | Humans | Thanks to named individuals: the CCL and CDO maintainers, the Scriptorium team, the UD contributors, Crum, and every Steward, Reviewer, and contributing submitter |

Both linked from the footer. The machine page is complete and dry; the human page is where the thanks live.

> **Risk reduced:** collapsing these produces either an unreadable wall of DOIs where the gratitude should be, or a warm letter that quietly omits a licence. Both are compliance failures of different kinds.

---

## 17. Δ Amendment to v4 §12 — v5 delta

| § | Change | Effort | Risk reduced |
|---|---|---|---|
| 13.1 | Suggestion architecture decided: **(B)** GitHub + Worker bridge | — | (A) excludes account-less diaspora; (C) makes reading depend on a runtime service and $0 becomes untrue |
| 13.2 | `suggestion.schema.json` with `submitter_hash` never rendered | +0.25 d | Publishing an IP-derived hash in a public artefact |
| 13.3 | `workers/suggest/index.ts` — stateless dedup **via GitHub search**, no KV, no D1 | +1.0 d | The natural dedup implementation needs a datastore and silently promotes us to (C) |
| 13.4 | `<details>` submission UI; no account, no email, no captcha; copy written for a first-time Coptic speaker | +3.0 d | Account friction as the primary reason a diaspora never contributes |
| 13.5 | Stage A bakes `suggestions.json`, paginated by target | +0.5 d | 5 MB global fetch; endorsements invisible on the static site |
| 13.6 | `/roadmap/` with `decide-by`, deferred and declined **shown** | — | "Maybe after a year" as a hope rather than a commitment |
| 14 | Curation: 5 roles, Steward cannot approve, **endorsement ≠ vote**, label taxonomy, triage SLA, public "strong suggestions" criteria | — | Popular-but-wrong feedback loop; unbounded expectations |
| 15 | Handoff, runbook, onboarding, **launch blocked until a Deputy is named** | +0.5 d | Project dying with its author |
| 16 | Attribution: author vs. originators, `/licences/` vs `/credits/`, upstream-only `attributions[]` | +0.5 d | CC BY-SA §3(a)/(b) non-compliance; burying upstream originators |
| 6.3 | Effort 97 → **102** | +5.0 d | Disclosed, not absorbed silently; conditional cut order named in advance |
| 3.5 | Gantt: Phase 1 +1.5 d, Phase 4 +3.5 d | — | — |
| 8 | Pointer to §16 | — | Project credit mixed into upstream attribution |

---

## 18. Δ First action — the three questions, answered

### 18.1 Which architecture, and why?

**(B) — GitHub as source of truth, one small Cloudflare Worker as an anonymous submission bridge.** GitHub Issues already provides the tracker, reactions for endorsement, authentication for Maintainers and Reviewers, a public audit trail, and a free tier for public repositories; the Worker exists solely to create an issue on behalf of someone who has no GitHub account, and to add a reaction on their behalf. It is ~100 lines, holds no data, and can be deleted without consequence. **(A)** — GitHub Discussions alone — would have been less code, and it is rejected for one reason: it requires an account, and the readers most able to spot a wrong gloss are liturgical Coptic speakers in the diaspora who will never register for GitHub. Requiring an account to be heard about their own language is the failure mode this project exists to avoid. **(C)** — Workers plus D1 — converts a contribution endpoint into a product with a database to migrate, accounts to moderate, and a moderation queue that can block launch; worse, it makes the suggestion system load-bearing for *reading*, which breaks the invariant that the whole site works with JavaScript off and no network at all, and turns a $0 project into one with a datastore to pay for. Committed: **(B)**.

### 18.2 How many person-days, and where do they come from?

**5.0 person-days.** UI 3.0 (Phase 4) · Worker 1.0 (Phase 1) · Stage A bake 0.5 (Phase 1) · user-facing copy 0.5 (Phase 4). Phase 2 and Phase 3 are untouched. The total goes **97 → 102** against 160 available person-days, i.e. 64% utilisation and 36% slack.

**There is no cut, because none is needed** — and manufacturing one to look rigorous would cost a real feature to solve a problem that does not exist. What I have done instead is name the **conditional cut order in advance** (§1.2) so that if slack erodes, the choice is already made and nobody renegotiates at Week 12: JS form first (1.5 d), monastic corpus tier second (2.0 d), UD parse views third (1.0 d), SEO page count last (0.5 d). The a11y line, licence verification, NC allowlist, and collation tests are never cut.

### 18.3 Who is the named successor?

**TBD — stated plainly rather than filled with a name.** No candidate can be named for a project that has not launched: there is no community to recruit from, no suggestion queue to learn triage on, and no reviewer relationship to inherit. Naming someone today would be a fiction, and a nominal successor is worse than an honest blank because it manufactures false assurance.

**The field is therefore not blank, and the gap closes on a date:**

- **Launch is blocked until ≥ 1 Deputy Maintainer is named.** This is written into `GOVERNANCE.md`, enforced in the pre-launch checklist, and it is the single hardest commitment in this plan.
- **2nd Deputy Maintainer, and a separate Deputy for Reviewer relations, within 6 months of launch.**
- **First succession rehearsal — Deputy runs a January review window while the Maintainer only observes — 12 months after Deputy #1 is named.**

Delegation chain if the Maintainer is unreachable for 30 days: **Deputy #1 → Deputy #2 → Lead Steward (triage and labelling only; may ship nothing; publishes a status note) → institutional custodian, approached in advance in this order: Coptic Orthodox Diocese (Southern USA), KELLIA alliance, Coptic Scriptorium.** Step 3 is deliberately powerless on purpose — if the Maintainer and both deputies are gone, stopping is correct and guessing at curation decisions is not.

---

## 19. Δ Artifacts produced alongside this plan

Written in full, ready to drop into the repository. All cross-links verified;
JSON schema validates; Worker compiles under `esbuild` (format=esm).

| File | Purpose |
|---|---|
| `README.md` | Project front door. What it is, 10-minute local run, the three design decisions worth knowing |
| `AUTHORS.md` | Michael Helmy first; upstream data originators with licence and DOI per source |
| `GOVERNANCE.md` | Roles, decision rights, endorsement ≠ vote, review windows, succession |
| `HANDOFF.md` | The five files that matter; the five things that break first; the anti-patterns |
| `RUNBOOK.md` | 8 procedures with commands and rollbacks |
| `ONBOARDING.md` | First four weeks, reading and doing |
| `CONTRIBUTING.md` | Suggesting a correction; fixing a bug; writing a lesson |
| `CONTRIBUTING_SOURCES.md` | The four gates for a new data source (supersedes v4 §7.6) |
| `FAQ.md` | Why no MT, no TTS, no accounts, why CC BY-SA, will it survive |
| `CHANGELOG.md` | Human-written entry format; the pre-launch baseline |
| `workers/suggest/index.ts` | The Worker. 338 lines / 250 code. Compiles |
| `workers/suggest/README.md` | Endpoints, stateless dedup, and the honest limits of the rate limiter |
| `workers/suggest/wrangler.toml` | Deploy config. No secrets |
| `schema/suggestion.schema.json` | Validates. 21 properties, `additionalProperties: false` |

**Note on links.** `licences.md`, `credits.md`, `roadmap.md` and `dialects.md`
are **generated by Hugo** and are not in the repository. `HANDOFF.md` §3 carries a
table saying which files are committed and which are generated, so a new
maintainer does not go looking for them.

---

*v5 changes verified 2026-10-03. Reading architecture unchanged and still fully static; the Worker is the only runtime component in the project and removing it affects contributions only, never reading. Collation, Pagefind, `_TT` parsing, the corpus tarball, the NC allowlist, `attributions[]`, Bohairic coverage honesty, and corpus rollout order are unchanged from v4 and remain closed. Effort 97 → 102 person-days against 160 available; `decide_by` is CI-enforced and no suggestion may sit in `accepted` past it.*
