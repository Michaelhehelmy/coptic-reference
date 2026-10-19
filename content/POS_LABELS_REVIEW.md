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

Token counts and top forms are from the seven-work corpus tarball
(`data/dist/corpus/corpus.tar.gz`, collation `b7b49af6e144ef87`),
re-measured in Session 25 when Shenoute's Eagerness joined; they are
observations, not confirmations.

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

## Why this register exists

Session 21's emitter labels all 57 tags and fails closed on an unlabeled
one; that catches absence, not wrongness. A label can be present, readable,
and still misdescribe the class (FM's "only, just" against a form
inventory led by ⲟⲩ is the live example above). These eight rows are the
debt the fail-closed rule cannot see. Confirming or correcting them is a
human task with the print grammars open; nothing in the build waits on it.
