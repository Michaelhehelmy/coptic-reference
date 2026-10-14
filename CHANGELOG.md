# CHANGELOG

**Every implementation, in the order it shipped.**

Hand-written and reviewed. Not generated — this is the artefact a scholar reads to
judge whether to trust the project, so it gets a human.

Each entry records: **what changed** (entry id, field, old → new), **which
suggestion prompted it** (issue + link), **which upstream change it accompanies**
if any, and **who implemented and who reviewed it**.

See [GOVERNANCE.md](GOVERNANCE.md) §Review windows for when things get
implemented.

---

## Unreleased

Nothing yet. The first entry appears when the January or July window closes.

**Format for a new entry — copy this:**

```markdown
## YYYY.MM — window name

### What changed
- `C5047` ⲧⲉⲛⲩ — `glosses[0]`: "now" → "at the present time"
  ([#421](https://github.com/coptic-reference/coptic-reference/issues/421))
- `C1092` ⲟⲩ — `dialects`: added `B`; Bohairic liturgical attestation
  ([#388](https://github.com/coptic-reference/coptic-reference/issues/388))

### Upstream
- Coptic Scriptorium bumped 6.3.0 → 6.4.0. Bohairic Habakkuk added (+41K words).

### People
- Implemented: <name>
- Reviewed: <name> (`reviewer/linguistic`)
- Decisions recorded: <link to the issue where a Maintainer overruled a Reviewer, if any>
```

---

## Before launch

Project structure and the first bake. Not content changes.

- Dictionaries ingested: CCL v1.2, CDO, Kaikki (3,293)
- Corpus ingested: Coptic Scriptorium v6.3.0 — 2.38M words, Sahidic + Bohairic
- `tools/collate.py` written. Coptic alphabetical order, name-resolved from
  Unicode. Replaces codepoint sort, which was wrong and invisible.
- `_TT` parser: single-pass state machine, raises on drift, preserves `@orig`
- Sharded dictionary reader, corpus reader, concordance, Anki export
- Suggestion Worker deployed — contributions only; reading is unaffected if removed
- **Deputy Maintainer named** — launch gate
