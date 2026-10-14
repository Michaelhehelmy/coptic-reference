# GOVERNANCE.md

**How decisions get made on the Coptic Reference, and by whom.**

Short version: **endorsement is interest, not authority, and a Reviewer's verdict
outranks both.** The rest of this document explains how that works in practice.

---

## 1. Roles

| Role | Who | May do | May **not** do |
|---|---|---|---|
| **Submitter** | Anyone. No account, no email, no captcha | Submit a suggestion | Endorse without a GitHub account or the Worker |
| **Endorser** | Anyone with a GitHub account, or via the Worker | React 👍 ❤️ 🚀 to a suggestion | Change any status |
| **Steward** | Named volunteers from Coptic Devs / seminary / diaspora | Triage within 7 days, dedupe, label, close duplicates, record blockers | **Approve.** Cannot move anything to `accepted` |
| **Reviewer** | Named Coptic linguists and clergy | Give a technical or theological verdict; set `reviewer/*`; resolve `status/needs-expert` | Change priority unilaterally |
| **Maintainer** | Michael Helmy, plus named deputies | **Final decision:** accept, defer, decline, implement. Owns the review windows and `decide_by` | Overrule a Reviewer verdict without recording the disagreement |

### Why a Steward cannot approve

The person who reads your email all week should not also be the person deciding
whether you were right. That friction is the point. Stewards **route**; Reviewers
**advise**; the Maintainer **decides** and answers for it.

### Reviewer register

Named individuals, published on [/credits/](credits.md).

| Area | Responsibility |
|---|---|
| `reviewer/linguistic` | Glosses, parses, morphology, segmentation, morphology of specific forms, "is this word used this way" |
| `reviewer/theological` | Liturgical translations, anything touching worship or doctrine |
| `reviewer/licence` | Licence verdicts, source permissions, takedown responses |

---

## 2. Endorsement is not a vote

> **Endorsements signal interest, not authority.**
>
> A suggestion with a hundred thumbs-up and no scholarly support **does not**
> override a Coptic linguist. A suggestion with three endorsements and a citation
> to CCL is taken seriously regardless of the count.

This is stated on the site, not only here, and it is load-bearing. A system that
quietly lets popularity decide will eventually ship something confidently wrong —
and the people who would tell us we are wrong are the clergy and the academics
whose unpaid labour makes this resource worth anything.

### Decision weight, in full order

```
Reviewer verdict  >  evidence quality  >  endorsements  >  submitter count
```

### What an endorsement actually means

It means "I have read this and I think it is worth someone's time." That is a
real contribution — it tells the Maintainer what the community cares about — but
it is not evidence that the suggestion is *correct*.

---

## 3. Decision rights, precisely

| Decision | Steward | Reviewer | Maintainer |
|---|---|---|---|
| `status/new` → `status/triaged` | ✅ | — | ✅ |
| `status/duplicate` | ✅ | — | ✅ |
| Assign `reviewer/*` | ✅ | — | ✅ |
| Set `priority/*` | ✅ (proposes) | — | ✅ |
| Technical verdict | — | ✅ **authoritative** | records it |
| Theological verdict | — | ✅ **authoritative** | records it |
| Licence verdict | — | ✅ **authoritative** | records it |
| → `status/accepted` | ❌ | — | ✅ |
| → `status/deferred` / `declined` | ❌ | — | ✅ |
| → `status/implemented` | ❌ | — | ✅ |
| Setting `decide_by` | ❌ | — | ✅ |

**If the Maintainer overrules a Reviewer,** the disagreement is recorded publicly
in the issue and on [/roadmap/](roadmap.md), with the Reviewer's name and their
reason. Disagreement is fine; silently overriding is not.

---

## 4. The suggestion lifecycle

```
  Submitter                Steward                Reviewer              Maintainer
      │                      │                      │                      │
      ▼                      ▼                      ▼                      ▼
   status/new ──────▶ status/triaged ──────▶ status/needs-expert ──▶ status/accepted
   (≤7 days)         (≤7 days)                (≤30 days)             (+ decide_by: +12mo)
      │                      │                      │                      │
      │                      ▼                      │          ┌───────────┼───────────┐
      │                status/duplicate               │          ▼           ▼           ▼
      │                      │                       │   implemented    deferred     declined
      │                      │                       │   + CHANGELOG    + blocker     + reason
      │                      │                       │                  (public)
      ▼                      ▼                       ▼                      ▼
   duplicates are commented on the original issue, never silently dropped
```

### Full status list

`status/new` · `status/triaged` · `status/needs-expert` · `status/accepted` ·
`status/deferred` · `status/declined` · `status/duplicate` · `status/implemented`

### Full label taxonomy

```
kind/gloss        kind/example     kind/etymology    kind/typo
kind/parse        kind/translation kind/licence      kind/bug
kind/feature

status/new        status/triaged   status/needs-expert  status/accepted
status/deferred   status/declined  status/duplicate     status/implemented

entry/<id>        work/<urn-short>     lesson/<slug>      site

priority/high    priority/medium   priority/low
reviewer/linguistic   reviewer/theological   reviewer/licence
```

Every suggestion also carries the bare `suggestion` label. That is what the
weekly bake queries — one label, one fetch, the whole set.

---

## 5. Service levels

Published here **and in the submission panel on every page**, because a service
level that exists only in an internal document is not a service level.

| Situation | Action | Deadline |
|---|---|---|
| Any new suggestion | Steward reads; label `status/triaged` or `status/duplicate` | **7 days** |
| `kind/licence` | Escalate to `reviewer/licence` | **Same day** |
| `kind/gloss`, `kind/parse`, `kind/translation` | Assign `reviewer/linguistic` | 7 days |
| `kind/translation` **on a liturgical work** | Also assign `reviewer/theological` | 7 days |
| Reviewer verdict | Recorded on the issue | **30 days** |

**These are targets, not guarantees.** A volunteer panel does not owe anyone a
response time. We publish them because "we aim to" is more useful to a
contributor than silence, and because they make it legitimate for you to ask us
where something stands.

---

## 6. Review windows and the twelve-month rule

**Two windows a year: January and July.** The Maintainer reviews everything in
`status/accepted` at each one.

### Why not ship continuously

1. **Attribution is not free.** Every change to the dictionary is a change to a
   CC BY-SA derived work. Continuous shipping means continuous re-attribution
   across ~11,500 entries, and the per-entry `Sources` panel has to stay correct.
2. **Reviewers are the scarcest resource in this project.** Asking a linguist to
   review one gloss at a time, indefinitely, burns out the two people whose
   unpaid expertise makes the site possible. A batch of 20–40 twice a year is a
   job someone can say yes to.
3. **Corpus refreshes are already scheduled.** Landing change on the same rhythm
   means one review, one bake, one announcement.

### The rule

Every `accepted` suggestion carries **`decide_by` = acceptance + 12 months**. At
each window the Maintainer must do exactly one of:

| Action | Requirement |
|---|---|
| **Implement** | Commit to `CHANGELOG.md`; set `implemented` |
| **Re-affirm** | Written reason **and** a new 12-month window. **Maximum twice** |
| **Defer** | A stated blocker, published on [/roadmap/](roadmap.md) |
| **Decline** | A written reason, published on [/roadmap/](roadmap.md) |

**No suggestion sits in `accepted` indefinitely.** After two re-affirmations the
only honest options are implement or decline.

> **This is the load-bearing mechanism.** The promise made to contributors is
> "maybe after a year." A `decide_by` date that CI enforces is the difference
> between that being a commitment and being a hope. If the date can slip
> silently, we have shipped a slower, more expensive version of "we'll get to
> it," and the community will read it exactly that way.

### [/roadmap/](roadmap.md) shows everything

Implemented · Accepted this window · Accepted next window · **Deferred (with
blocker)** · **Declined (with reason)** — with `decide_by` on every accepted item.

**Declined and deferred are shown, not hidden.** A project that displays only
what it shipped teaches contributors that silence means "no" and that effort is
wasted. Showing the reasoning is the difference between a suggestion box and a
relationship.

---

## 7. What makes a suggestion likely to be implemented

**Public criteria.** This is both the Maintainer's working list and your
expectation. It is published because a suggestion system nobody trusts is worse
than none.

| Criterion | What it means |
|---|---|
| **Correctness with evidence** | Cites CCL, CDO, Crum, or a published grammar. A scholarly edition carries more weight than a website |
| **Endorsement breadth** | Several *independent* people agree. One person upvoting their own suggestion is not breadth |
| **Reviewer support** | A Reviewer has confirmed it is correct. **The strongest single signal** |
| **Scope** | **Small changes ship faster than schema changes.** Do not expect a redesign from a one-line observation |
| **Licence clarity** | A suggestion introducing a new source needs a licence verdict first — see [CONTRIBUTING_SOURCES.md](CONTRIBUTING_SOURCES.md) |

---

## 8. Succession

**The single-author dependency is this project's most likely failure mode.** Not
competition, not funding — one person.

### Named successor

**TBD. Stated plainly rather than filled with a name.**

No candidate can be named for a project that has not launched: there is no
community to recruit from, no suggestion queue to learn triage on, and no
reviewer relationship to inherit. A nominal successor is **worse** than an honest
blank, because it manufactures false assurance.

**The field is closed by a date, not a hope:**

| Commitment | Deadline |
|---|---|
| **≥ 1 Deputy Maintainer named** | **Before launch — launch is blocked until true** |
| 2nd Deputy Maintainer named | Within 6 months of launch |
| Deputy for Reviewer relations (separate relationship) | Within 6 months of launch |
| First succession rehearsal — Deputy runs a January window, Maintainer observes | 12 months after Deputy #1 is named |

### Delegation chain — Maintainer unreachable for 30 days

```
1. Deputy Maintainer #1     → acts as Maintainer. May accept, defer, decline,
                              implement. Runs review windows.
2. Deputy Maintainer #2     → if #1 is also unreachable.
3. Lead Steward             → may triage, label, dedupe. MAY NOT accept,
                              decline, or implement. SHIPS NOTHING.
                              Publishes a status note every 14 days.
4. Institutional custodian  → asked IN ADVANCE, in this order:
                              a. Coptic Orthodox Diocese (Southern USA)
                              b. KELLIA alliance (Göttingen / FU Berlin / BBAW)
                              c. Coptic Scriptorium (Georgetown / U Pacific)
```

**Step 3 is deliberately powerless on purpose.** If the Maintainer and both
deputies are gone, the correct action is to **stop shipping**, not to let a
Steward guess at curation decisions.

### How a Maintainer is actually replaced

The current Maintainer asks; you say yes in writing. That is the whole mechanism.
It is deliberately informal because a formal process would not get used. On
naming a successor he is credited as **Founding author** and stays first in
[AUTHORS.md](AUTHORS.md) permanently.

---

## 9. Attribution

**The project author is not the author of the data.**

Michael Helmy authors the site, the code, the curation and the compilation. The
lexicons, corpora and treebanks are other people's work, and under CC BY-SA 4.0
those originators must be **more** prominent than the compiler, not less.

| Artefact | Credit |
|---|---|
| **Per entry** | `attributions[]` — upstream sources only, in the **Sources** panel. **The project author never appears here.** |
| **[/licences/](licences.md)** | Machine-generated from `LICENSES.csv`. Every source, licence and DOI. For compliance reviewers |
| **[/credits/](credits.md)** | Hand-written. Named individuals, thanked. For humans |
| **Footer** | `A project by Michael Helmy. Site code Apache-2.0 · Site content CC BY-SA 4.0 · Dictionary and corpus data compiled from CCL, CDO, Coptic Scriptorium, Universal Dependencies, and Wiktionary — full credits.` |

**Not this:** `© 2026 Michael Helmy · CC BY-SA 4.0`

**Ethical note.** Coptic Scriptorium lost its NEH funding in 2025. Those
maintainers are the actual authors of the corpus this entire project depends on,
and they are unpaid for it. A footer that puts the compiler above them is both
non-compliant and graceless.

---

## 10. Changing this document

Governance changes require the Maintainer **and** one Reviewer's agreement, and
must state the reason. Amendments go in `CHANGELOG.md` with the issue that
prompted them.
