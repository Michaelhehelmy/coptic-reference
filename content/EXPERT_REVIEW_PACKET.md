---
title: "Expert review packet"
url: /expert-review-packet/
---

# Expert review packet — Session 23 D3

This page gathers **every open expert-verdict item in the site** into one
place, so a Copticist can review the whole backlog offline, in one sitting,
and respond without an account on this site. It has two parts: the grammar
claims register (lessons 1–20) and the POS labels register (eight tags).
Both registers — `content/GRAMMAR_CLAIMS.md` and
`content/POS_LABELS_REVIEW.md` — are the source of truth; this packet
mirrors their tables line for line, and a test
(`tools/tests/test_review_packet.py`) fails the build if the mirror ever
drifts.

Nothing here is generated content. Every claim was written in this
project's own sessions from grammar knowledge and corpus observation, and
every number below was measured, not modelled. The site is static, has no
accounts, and no part of the build runs a model.

## How to respond

1. **Pick a verdict vocabulary** and use it in the blank *Verdict* cells:
   - `confirmed` — the claim/label is correct as written;
   - `corrected: <replacement text> (+ source)` — wrong or too narrow; give
     the correction and the grammar or tagset it rests on;
   - `cannot adjudicate: <what would settle it>` — the row as written
     cannot be judged without something the packet does not carry.
2. **Answer in either place**, whichever is easier:
   - edit the Verdict cell in the register file itself (a pull request on
     `Michaelhehelmy/coptic-reference`, or the file attached back to the
     steward), or
   - open a GitHub issue quoting the row; issue comments are fine — the
     steward transfers them into the cells.
3. **Cite a source you would accept as authoritative.** The rows name the
   candidates (Layton 2000, Lambdin 1983, Polis & Lungu, the Coptic
   Scriptorium / UD Coptic tagset). Your citation is the record; corpus
   counts alone cannot confirm a label.

Verdict cells stay blank until a reviewer fills them — the same contract
both registers have carried since Session 21. A lesson's
`grammar_claims_verified` flag flips to true only when every one of its
rows reads confirmed; until then the lesson page shows the review banner.
No part of the build, deploy, or guard suite waits on a verdict.

## Evidence the reviewer is being asked to judge against

- **Corpus:** seven parsed works — Bohairic Mark, Sahidic Ruth, 1
  Corinthians, Life of Isaac, Martyrdom of Victor, Lausiac History,
  and Shenoute's Eagerness —
  shipped as `data/dist/corpus/corpus.tar.gz`, collation hash
  `b7b49af6e144ef87`. Token counts and top-form tables in the POS register
  were re-measured against that tarball in Session 25, when the seventh
  work shipped; they are observations, not confirmations.
- **Glosses are already machine-checked** (`lesson_vocab_guard.py`, Rule
  14): a taught word pair that the dictionary does not support fails the
  build. Grammar and part-of-speech claims are precisely the residue that
  machine checking cannot settle, which is why they are in these registers.

## Part A — Grammar claims register (mirror of `content/GRAMMAR_CLAIMS.md`)

Every grammar assertion in every lesson, one line each: what the lesson
claims about how Coptic works (not what words mean — glosses are checked by
`lesson_vocab_guard.py`), what corpus evidence would verify it, and a
verdict slot that stays blank until a reviewer fills it.

| Lesson | Claim | Corpus evidence needed | Verdict (blank until reviewed) |
|---|---|---|---|
| 01 | Coptic uses Greek letters plus six Egyptian-derived signs | Alphabet tables in Layton; letter inventory of the corpus | |
| 01 | Little grammar words are written apart from content words | Bound-group segmentation of Ruth 1:1 (ⲁ ⲥ ϣⲱⲡⲉ as three tokens) | |
| 01 | ⲁ marks past, ⲥ is a 3fs pronoun, ϣⲱⲡⲉ carries the lexical meaning | POS/func tags of Ruth 1:1 tokens (APST, PPERS, VSTAT) | |
| 02 | Definite articles agree in gender and number (ⲡ masc.sg, ⲧ fem.sg, ⲛⲉ pl.) | Article forms by following-noun gender across Ruth | |
| 02 | Possessive ⲧⲉϥ does the work of English word order | PPOS tokens vs English alignments in Ruth | |
| 03 | ⲉⲓ covers both "come" and "go" | Gloss inventory of ⲉⲓ's entry (both senses listed) | |
| 04 | Past time is marked by a pre-verbal ⲁ; the verb keeps dictionary shape | ⲁ-initial clauses in Ruth 1:1–5 vs citation forms | |
| 04 | Mark's spelling habits are Bohairic, distinct from Ruth's Sahidic | Dialect-tagged works (bohairic_mark vs sahidic_ruth) | |
| 05 | Negation wraps the clause (ⲛ before, ⲁⲛ after) | NEG/PST-negated clauses in Mark | |
| 06 | Independent pronouns stand alone for emphasis or contrast | Emphatic vs clitic pronoun distribution in Mark 1:9–12 | |
| 06 | Most subjects hide inside the verb (pro-drop) | Subject pronoun rate per clause in Mark | |
| 06 | ⲡⲁⲓ leans Sahidic, ⲫⲁⲓ leans Bohairic | Demonstrative forms by dialect work | |
| 07 | Coptic commands are softer than English imperatives (wishes) | Mood tags on directive verbs in 1 Corinthians | |
| 08 | ⲉⲧⲉ converts a sentence into a noun-modifying description | CREL clauses and their head nouns in 1 Cor 1:4–8 | |
| 09 | Motion verbs pair with direction words; direction carries the load | ⲉⲃⲟⲗ/ⲉϩⲟⲩⲛ/ⲉϩⲣⲁⲓ collocations with motion verbs in Mark | |
| 09 | ⲧⲟⲧⲉ leans on its verse for sense | ⲧⲟⲧⲉ tokens across narrative vs discourse contexts | |
| 10 | (No new grammar claims; reading method only) | — | |
| 11 | Coptic chains clauses with linking words instead of new sentences | Clause-linker frequency in Life of Isaac 1–4 | |
| 12 | Purpose and result clauses are distinct, marked constructions | Final vs consecutive clause markers in Isaac 5–8 | |
| 12 | ⲉⲃⲟⲗ closes motion verbs (completion, not onset) | ⲉⲃⲟⲗ co-occurrence with motion vs stative verbs | |
| 13 | Direct discourse follows speaker–verb–speech order; the quoting verb never moves | Speech introductions in Victor 1–4 | |
| 14 | Nominal sentences state equivalence with no copula ("X is Y" with no "is") | Verbless clauses in Lausiac History 1–4 | |
| 15 | (Restates lesson 1 on ⲁ ⲥ ϣⲱⲡⲉ; no new claims) | See lesson 01 | |
| 16 | Circumstantial ⲉⲣⲉ opens a dependent frame; the main clause follows it | Shenoute 95 (aligned English) and 309 (Coptic-only): the ⲉⲣⲉ-clause stands before its main clause | |
| 16 | Temporal ⲙⲡⲁⲧⲉ places one event before another ("before") | Shenoute 75 and 357, both Coptic-only segments with no English in either | |
| 17 | Fronted possessive: ⲙ̄/ⲛⲧⲉ stand before the phrase where English tacks "of" onto the end | Shenoute 100 vs English "a snare of the devil" (one unit, ⲛⲧⲉ at its heart) | |
| 17 | The bare dative ⲛⲁ ⲛ rides after the verb with no separate preposition ("to us") | Shenoute 102: Coptic ⲛⲁ ⲛ vs English "give it to us" | |
| 17 | (Restates lesson 09: destination opens with ⲉϩⲣⲁⲓ ⲉ) | Shenoute 100 vs English "down to a snare"; see lesson 09 | |
| 18 | (No new grammar claims; codex segmentation and reading method only) | — | |
| 19 | (No new grammar claims; reading method only) | — | |
| 20 | (No new grammar claims; orientation only) | — | |

## Part B — POS labels register (mirror of `content/POS_LABELS_REVIEW.md`)

Seven labels in `tools/emit/pos_labels.py` rest on corpus examples and
annotation-function patterns rather than a grammar citation; an eighth
(AAOR) was added by the emitter's fail-closed catch in Session 21. Each row
gives the tag, the label currently shipped, what the corpus already shows,
and the source that would confirm or correct the label.

| Tag | Proposed label | Corpus evidence already in hand | Source that would confirm | Verdict (blank until reviewed) |
|---|---|---|---|---|
| VBD | past-tense verb | 494 tokens; ⲡⲉϫⲁ (291), ⲡⲉϫⲉ (72), ⲛⲁⲛⲉ (38), ⲡⲉϫⲱ (27); functions root/parataxis/conj — the narrative-past class, not a general past | Lambdin 1983, lessons on ⲡⲉϫⲉ / ⲡⲉϫⲁ; Layton 2000, past-tenses chapter — confirm whether every VBD form is an old-perfective stem, and whether "past-tense verb" should say "narrative past" | |
| PPERI | independent pronoun (for emphasis) | 539 tokens; ⲁⲛⲟⲕ (140), ⲛⲑⲟϥ (82), ⲁⲛⲟⲛ (47), ⲛⲑⲱⲧⲉⲛ (43); mostly UD function dislocated (282) — matches the label | Layton 2000, independent-pronoun section; confirm the label covers dislocated positions, not only contrastive emphasis | |
| IMOD | modifier | 563 tokens; ⲧⲏⲣ (313), ϩⲱ (72), ⲥⲁⲧⲟⲧ (62), ϩⲱⲱ (38); functions obl:unmarked / nmod:unmarked — post-nominal modifiers, not adjectives | Polis & Lungu / Coptic Scriptorium annotation guidelines for IMOD; Layton on nominal modification — decide whether the label should name the post-nominal position | |
| FM | focus particle (only, just) | 50 tokens; ⲟⲩ (13), ⲙⲟⲛⲟⲛ (6), ⲁⲗⲗⲟ (3), ⲧⲟⲩ (2) — the forms are heterogeneous and ⲙⲟⲛⲟⲛ is a MINORITY; "only, just" may be too narrow for the class | Coptic Scriptorium / UD Coptic tagset definition of FM; corpus check: what do the ⲟⲩ / ⲧⲟⲩ / ⲕⲉ FM tokens align to in English? — the label may need widening beyond "only, just" | |
| APREC | temporal marker (when) | 388 tokens; ⲉⲧ (351), ⲛ̅ⲧⲉⲣⲉ (12), ⲛⲧⲉⲣⲉ (8), ⲛ̅ⲧⲉⲣ (7); functions aux/mark — ⲉⲧ dominates, not ⲛⲧⲉⲣⲉ | Layton 2000, temporal ⲉⲧ vs relative ⲉⲧ (compare CREL); confirm APREC-ⲉⲧ is distinct from CREL-ⲉⲧ in annotation practice | |
| AOPT | wish marker (may it be) | 13 tokens; ⲉⲣⲉ only; functions aux/mark — tiny class, label is name-read from the tag string | Layton 2000, imperative and optative (the lesson 07 reading); 11 tokens cannot confirm a gloss — the grammar must | |
| AAOR | habitual marker (usually) | 163 tokens; ϣⲁ (132), ϣⲁⲣⲉ (31); functions aux/case — the aoristic-habitual class the label names | Layton 2000, aoristic / habitual ⲛⲧⲉⲣⲉ–ϣⲁⲣⲉ; confirm ϣⲁ (uninflected) belongs to the same class as ϣⲁⲣⲉ | |
| AFUTCONJ | future conjunctive marker | 6 tokens; ⲧⲁⲣ (3), ⲧⲁⲣⲉ (2), ⲧⲁⲣ︤ (1); functions case/aux — six tokens cannot confirm anything | Coptic Scriptorium / UD Coptic tagset documentation for AFUTCONJ; the tag name itself is the only current source — a 6-token class should stay name-read until documented | |

## Part C — what happens after a verdict

- **Confirmed:** the steward writes `confirmed` in the cell (plus the
  source); the lesson's `grammar_claims_verified` flag flips to true once
  all of that lesson's rows are confirmed, and the review banner leaves the
  lesson page.
- **Corrected:** the steward edits the claim or label to the reviewer's
  wording, records the correction and its source in the cell, and the next
  build carries it. Lesson edits re-run `lesson_vocab_guard.py` (Rule 14);
  label edits re-run the emit and its tests.
- **Cannot adjudicate:** the row stays open with the missing evidence
  named — it does not get silently closed.

Both registers, and this mirror, are published under the site's licence,
**CC BY-SA 4.0**; a verdict is a contribution to the same licence. See
`CONTRIBUTING.md` for how suggestions are handled, and `AUTHORS.md` for
attribution.
