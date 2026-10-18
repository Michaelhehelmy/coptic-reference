---
title: "POS labels needing review"
url: /pos-labels-review/
---

# POS labels needing review — Session 22 D4

Seven labels in `tools/emit/pos_labels.py` rest on corpus examples and
annotation-function patterns rather than a grammar citation; an eighth
(AAOR) was added by the emitter's fail-closed catch in Session 21 and is
flagged in the source for the same reason. Each row gives the tag, the
label currently shipped, what the corpus already shows, and the source
that would confirm or correct the label. Verdicts stay blank until a
reviewer fills them — the same contract as the grammar claims register.

Token counts and top forms are from the six-work corpus tarball
(`data/dist/corpus/corpus.tar.gz`, collation `b7b49af6e144ef87`),
measured in this session; they are observations, not confirmations.

| Tag | Proposed label | Corpus evidence already in hand | Source that would confirm | Verdict (blank until reviewed) |
|---|---|---|---|---|
| VBD | past-tense verb | 457 tokens; ⲡⲉϫⲁ (287), ⲡⲉϫⲉ (68), ⲛⲁⲛⲉ (38), ⲡⲉϫⲱ (27); functions root/parataxis/conj — the narrative-past class, not a general past | Lambdin 1983, lessons on ⲡⲉϫⲉ / ⲡⲉϫⲁ; Layton 2000, past-tenses chapter — confirm whether every VBD form is an old-perfective stem, and whether "past-tense verb" should say "narrative past" | |
| PPERI | independent pronoun (for emphasis) | 454 tokens; ⲁⲛⲟⲕ (133), ⲛⲑⲟϥ (82), ⲛⲑⲱⲧⲉⲛ (43), ⲁⲛⲟⲛ (36); mostly UD function dislocated (256) — matches the label | Layton 2000, independent-pronoun section; confirm the label covers dislocated positions, not only contrastive emphasis | |
| IMOD | modifier | 461 tokens; ⲧⲏⲣ (274), ϩⲱ (68), ⲥⲁⲧⲟⲧ (62), ⲙⲙⲁⲩⲁⲧ (29); functions obl:unmarked / nmod:unmarked — post-nominal modifiers, not adjectives | Polis & Lungu / Coptic Scriptorium annotation guidelines for IMOD; Layton on nominal modification — decide whether the label should name the post-nominal position | |
| FM | focus particle (only, just) | 38 tokens; ⲟⲩ (8), ⲙⲟⲛⲟⲛ (3), ⲧⲟⲩ (2), ⲕⲉ (1) — the forms are heterogeneous and ⲙⲟⲛⲟⲛ is a MINORITY; "only, just" may be too narrow for the class | Coptic Scriptorium / UD Coptic tagset definition of FM; corpus check: what do the ⲟⲩ / ⲧⲟⲩ / ⲕⲉ FM tokens align to in English? — the label may need widening beyond "only, just" | |
| APREC | temporal marker (when) | 384 tokens; ⲉⲧ (351), ⲛ̅ⲧⲉⲣⲉ (12), ⲛ̅ⲧⲉⲣ (7), ⲛⲧⲉⲣⲉ (5); functions aux/mark — ⲉⲧ dominates, not ⲛⲧⲉⲣⲉ | Layton 2000, temporal ⲉⲧ vs relative ⲉⲧ (compare CREL); confirm APREC-ⲉⲧ is distinct from CREL-ⲉⲧ in annotation practice | |
| AOPT | wish marker (may it be) | 11 tokens; ⲉⲣⲉ only; functions aux/mark — tiny class, label is name-read from the tag string | Layton 2000, imperative and optative (the lesson 07 reading); 11 tokens cannot confirm a gloss — the grammar must | |
| AAOR | habitual marker (usually) | 140 tokens; ϣⲁ (115), ϣⲁⲣⲉ (25); functions aux/case — the aoristic-habitual class the label names | Layton 2000, aoristic / habitual ⲛⲧⲉⲣⲉ–ϣⲁⲣⲉ; confirm ϣⲁ (uninflected) belongs to the same class as ϣⲁⲣⲉ | |
| AFUTCONJ | future conjunctive marker | 2 tokens; ⲧⲁⲣⲉ only; functions case/aux — two tokens cannot confirm anything | Coptic Scriptorium / UD Coptic tagset documentation for AFUTCONJ; the tag name itself is the only current source — a 2-token class should stay name-read until documented | |

## Why this register exists

Session 21's emitter labels all 57 tags and fails closed on an unlabeled
one; that catches absence, not wrongness. A label can be present, readable,
and still misdescribe the class (FM's "only, just" against a form
inventory led by ⲟⲩ is the live example above). These eight rows are the
debt the fail-closed rule cannot see. Confirming or correcting them is a
human task with the print grammars open; nothing in the build waits on it.
