# ONBOARDING.md

**Your first four weeks as a maintainer of the Coptic Reference.**

**What this is trying to achieve:** not that you know everything. That you know
**which five files matter** and **where the bodies are buried.** Those are
different skills. The second is what actually keeps a project alive when one
person has to stop.

**A note on Coptic.** You do not need to be a Coptologist to maintain this site.
You need to know when to ask one. The single most useful thing you will learn in
week 1 is **which questions are yours to answer and which belong to a Reviewer.**
Almost all of them belong to a Reviewer.

---

## Week 1 — Understand the shape

**Goal:** you can explain the project to someone else in three sentences, and
you have run a bake yourself.

**Read**
- `README.md` — 10 minutes
- `HANDOFF.md` §1–3 — the elevator pitch, the architecture diagram, **the five files**
- The live site, as a reader would: look up `ⲧⲉⲛⲟⲩ`, open a Bohairic Psalm, run a concordance query on `ⲛⲁⲓ`, try the keyboard on your phone
- `/licences/` and `/credits/` — you will be the second person to look at these

**Do**
```bash
git clone https://github.com/coptic-reference/coptic-reference && cd coptic-reference
make -C tools all          # ~12 min. This is the whole pipeline. It will work.
ls -la data/dist/          # shards, tarball, provenance CSV, manifest
cat data/dist/manifest.json | head -40
```

Then deploy to a **preview URL** and share it with one person who is not technical.

**Check you can answer:**
- What are the three stages, and which one runs on Cloudflare and which does not?
- Which five files matter? Name them.
- What is `submitter_hash`, and why is it never displayed?
- If the Worker disappeared tonight, what would break?

---

## Week 2 — Understand the data

**Goal:** you can trace one dictionary entry back to its sources, and you have shipped one real change end to end.

**Read**
- `tools/collate.py` — 30 min. Then read the **comments at the top**: they record four bugs that shipped in an earlier draft. Understand why the alphabet is name-resolved from Unicode rather than typed out
- `tools/parse/tt.py` — 45 min. Focus on the state machine and on *why it raises instead of skipping*
- `tools/merge/entries.py` — 30 min. The precedence rules and the "never merge distinct senses" rule
- One shard of `data/dist/dict/shard-000.json` — trace entry `C5047` back through `records.csv` to CCL, CDO and Kaikki

**Do — the end-to-end exercise, which is the point of this week**

Pick any open suggestion and carry it all the way through:

```bash
gh issue list --label suggestion --label status/new --limit 5
# pick one
gh issue view 421
# triage it
gh issue edit 421 --add-label status/triaged,entry/C5047,reviewer/linguistic
# (Reviewer responds — use a real one, or shadow a real review)
# make the change
$EDITOR tools/merge/entries.py     # or the right source
make -C tools merge && make -C tools emit && make -C tools validate
git diff data/dist/provenance/records.csv    # ← read it
# commit, push, watch the preview deploy
```

**One suggestion, start to finished.** By the end of this week you have felt the
entire loop, which is the only way to know which parts are slow.

**Check you can answer:**
- Why is the corpus parsed from `_TT` and not from TEI?
- What happens to a sentence if the parser cannot read it? *(It must raise. Why is that better than skipping?)*
- Which source wins for a gloss, and why is the loser kept anyway?

---

## Week 3 — Understand the process

**Goal:** you can triage, and you know exactly where your authority stops.

**Read**
- `GOVERNANCE.md` — all of it, especially the roles table
- `CONTRIBUTING.md` and `CONTRIBUTING_SOURCES.md`
- `RUNBOOK.md` §1–3 — *read these as if they are about you, not hypothetical*
- `/roadmap/` on the live site, and the last three entries of `CHANGELOG.md`
- The most recent five **declined** suggestions on GitHub, and the reasoning. This is the most instructive reading in the whole project

**Do**
```bash
# Triage five real suggestions, shadowed by a Steward.
gh issue list --label suggestion --label status/new --json number,title --limit 5
for n in 421 422 423; do gh issue view $n; done
# write your triage decision for each, then compare with the Steward's
```

Then read the closed issues. Ask: *why was this declined?* The answer is usually
more interesting than the suggestion.

**Check you can answer:**
- Can a Steward move a suggestion to `accepted`? *(No.)*
- A suggestion has 80 endorsements and one Reviewer says it is wrong. What happens?
- What does `decide_by` mean, and what breaks if it slips? *(CI fails the build.)*
- What do you do if `kind/licence` arrives? *(Same day, `reviewer/licence`.)*

---

## Week 4 — Own a piece

**Goal:** you ship something unaided that nobody checked for you first.

Whatever the Maintainer hands you. Good candidates, in rough order of how much
they teach:

1. **Fix a real suggestion** end to end (§ week 2)
2. **Write or improve a lesson.** You will learn what "5–10 corpus deep-links, ≥ 1 grammar reference" actually costs
3. **Add a data source** through all four gates. If you do this once you will never again wonder why `LICENSES.csv` is so fussy
4. **Run a review window.** If you are the Deputy, this is the month to shadow it
5. **Write something for `FAQ.md`**, answering a question a reader actually asked

Then, and only then, read `HANDOFF.md` §9 and `RUNBOOK.md` again. The rest of it
will make much more sense now that you have hit one or two of the procedures.

---

## After week 4

**You are a maintainer.** Two things to do in your first month:

1. **Add yourself to `AUTHORS.md`** with your role and what you look after
2. **Confirm you are reachable the way `HANDOFF.md` §10 says** — a real email a person monitors, not a Discord handle

**Things worth knowing that are not in the docs:**

- The hardest part of this project is not technical. It is that the two people
  whose unpaid expertise makes the site trustworthy — a Coptic linguist and a
  priest — have very little spare capacity. Everything in `GOVERNANCE.md` is
  shaped around not burning them out. **When you feel tempted to ask for one more
  review, do not.**
- **Write down what you decide and why**, in the issue or in `CHANGELOG.md`. The
  author's single hardest problem is that nobody knows why a gloss was accepted.
  Be the person who writes it down.
- **The site will not tell you it is broken.** Bakes fail silently, data drifts
  quietly, and a wrong sort order looks fine to anyone who cannot read Coptic.
  That is what the CI gates are for. Do not disable one.
- **Say no kindly and quickly** to suggestions that are out of scope. A fast,
  explained "no" keeps people. A slow silence loses them.
