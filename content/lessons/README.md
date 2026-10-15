# Structured course plan — Session 19 D3

Fifteen lessons, beginner to intermediate, Sahidic narrative first (Ruth),
then Bohairic gospel (Mark), then letters, lives, and martyrdom. Every
machine-readable field below reappears as front matter in
`content/lessons/NN.md` and in `data/dist/course/course.json.gz`, emitted by
`tools/emit/coursegen.py`. No per-item data ships in the course file: the
client fetches quiz banks by band+POS and drill banks by work, exactly as
`/quiz/` and `/drill/` do today; the course only chains them.

Conventions used by every lesson:

- `vocabulary`: 10–20 lemmas from one frequency band, each linking to
  `/dict/?q=<lemma>`. Lemmas below are the corpus-measured most frequent in
  their class — no invented glosses anywhere in this plan.
- `quiz`: a filter `{band, pos}` over the quiz banks (beginner = ranks 1–300,
  intermediate = 301–1,000, advanced = 1,001+, same bands as quizgen).
- `drill`: a filter `{work, verse_min, verse_max}` (verse_index, 0-based,
  traceable to the tarball) over the drill banks.
- `corpus`: 3–5 verses `{work, verse_start, verse_end}` to read after the
  exercises, at the lesson's difficulty.
- `checkpoint`: pass the lesson's quiz filter at ≥ 70% to unlock the next
  lesson (client-side; an "unlock all" override exists for advanced learners).
- `reading`: a print-grammar citation by topic (Layton 2000 *A Coptic
  Grammar*, Layton 2007/2011 *Coptic in 20 Lessons*, Lambdin 1983
  *Introduction to Sahidic Coptic*, Till 1961 *Dialektgrammatik*/*Koptische
  Grammatik*, Reintges *Learner's Grammar*, Mallon *Grammaire copte* for
  Bohairic). Section numbers are deliberately NOT cited — only works and
  topics, so no unverifiable pointer ships.

## Beginner — Ruth and the opening of Mark (lessons 1–5, full content)

### Lesson 1 — The alphabet and its sounds
prerequisite: none.
reading: Layton, alphabet chapter; the six Demotic letters ϣϥϩϫϭϯ.
vocabulary (beginner, mixed): ⲉⲃⲟⲗ ϫⲱ ⲓⲣⲓ ⲃⲱⲕ ϣⲱⲡⲓ ⲛⲟⲩϯ ϯ ⲣⲏϯ ⲣⲱⲙⲉ ⲙⲟϣⲓ ⲟⲩⲁⲓ ⲥⲁϫⲓ.
quiz: {band: beginner, pos: N}. drill: {work: sahidic_ruth, verse_min: 0, verse_max: 19}.
corpus: {work: sahidic_ruth, verse_start: 0, verse_end: 4} (Ruth 1:1–5).
checkpoint: quiz ≥ 70%.

### Lesson 2 — Articles and nouns
prerequisite: 1.
reading: Lambdin, lessons on the definite article (ⲡ/ⲡⲓ/ⲟⲩ).
vocabulary (beginner, N): ⲛⲟⲩϯ ⲣⲱⲙⲉ ⲥⲁϫⲓ ⲙⲁ ϩⲏⲧ ⲙⲏϣ ⲁⲡⲁ ϩⲱⲃ ⲉⲙⲓ ⲥⲟⲛ ⲙⲟⲩ ⲭⲣⲓⲥⲧⲟⲥ.
quiz: {band: beginner, pos: N}. drill: {work: sahidic_ruth, verse_min: 0, verse_max: 29}.
corpus: {work: sahidic_ruth, verse_start: 5, verse_end: 9}.
checkpoint: quiz ≥ 70%.

### Lesson 3 — Saying and doing: core verbs
prerequisite: 2.
reading: Layton, the verbal system overview; Lambdin on ϫⲱ/ⲡⲉϫⲉ.
vocabulary (beginner, V): ϫⲱ ⲓⲣⲓ ⲉⲓⲣⲉ ϯ ⲃⲱⲕ ⲉⲓ ⲙⲟϣⲓ ⲟⲩⲱⲙ ⲛⲁⲩ ⲓⲛⲓ ⲥⲱⲧⲉⲙ.
quiz: {band: beginner, pos: V}. drill: {work: sahidic_ruth, verse_min: 20, verse_max: 49}.
corpus: {work: sahidic_ruth, verse_start: 10, verse_end: 14}.
checkpoint: quiz ≥ 70%.

### Lesson 4 — The past that happened: ⲁ… and motion
prerequisite: 3.
reading: Layton, past tenses; motion verbs ⲃⲱⲕ/ⲉⲓ in context.
vocabulary (beginner, V/VSTAT): ϣⲱⲡⲓ ⲃⲱⲕ ⲉⲓ ⲟⲩⲱⲙ ⲙⲟϣⲓ ϣⲉ ⲉⲓⲣⲉ ⲟⲩⲁⲃ ⲥⲱϣⲉ ⲙⲟⲟϣⲉ.
quiz: {band: beginner, pos: V}. drill: {work: bohairic_mark, verse_min: 0, verse_max: 29}.
corpus: {work: bohairic_mark, verse_start: 0, verse_end: 3} (the opening).
checkpoint: quiz ≥ 70%.

### Lesson 5 — Negation and number
prerequisite: 4.
reading: Till, negation (ⲁⲛ, ⲙⲛ-) and numerals (ⲟⲩⲁⲓ, ⲥⲛⲁⲩ).
vocabulary (beginner, ADV/NUM/N): ⲟⲛ ⲙⲙⲁⲩ ⲟⲩⲁⲓ ⲙⲏϣ ⲥⲛⲁⲩ ⲣⲁⲛ ϣⲉⲗⲉⲉⲧ ⲥϩⲓⲙⲉ ⲣⲱⲙⲉ ⲥⲟⲛ.
quiz: {band: beginner, pos: ADV}. drill: {work: bohairic_mark, verse_min: 30, verse_max: 69}.
corpus: {work: bohairic_mark, verse_start: 4, verse_end: 7}.
checkpoint: quiz ≥ 70%.

## Intermediate — Mark and 1 Corinthians (lessons 6–10, placeholders in 19)

### Lesson 6 — Pronouns that point
prerequisite: 5. reading: Reintges, personal pronouns. vocabulary
(intermediate, pronouns-as-lemmas for recognition only): ⲁⲛⲟⲕ ⲛⲧⲟⲕ ⲛⲧⲟϥ
ⲛⲧⲟⲥ ⲁⲛⲟⲛ ⲛⲧⲱⲧⲛ ⲛⲧⲟⲟⲩ ⲡⲁⲓ ⲫⲁⲓ ⲛⲁⲓ. quiz: {band: intermediate, pos: V}.
drill: {work: bohairic_mark, verse_min: 70, verse_max: 129}. corpus:
{work: bohairic_mark, verse_start: 8, verse_end: 11}. checkpoint: quiz ≥ 70%.

### Lesson 7 — Commands and wishes
prerequisite: 6. reading: Layton, imperative and optative. vocabulary
(intermediate, V): ⲥⲙⲟⲩ ⲧⲱⲃϩ ⲕⲱⲧ ⲟⲩⲱⲛϩ ⲛⲁϩϯ ⲧⲱⲟⲩⲛ ⲟⲩⲱϣ ⲉⲙⲓ ϭⲓ ⲟⲩⲱⲙ. quiz: {band: intermediate, pos: V}. drill:
{work: bohairic_1corinthians, verse_min: 0, verse_max: 39}. corpus:
{work: bohairic_1corinthians, verse_start: 0, verse_end: 3}. checkpoint: quiz ≥ 70%.

### Lesson 8 — The converter ⲉⲧⲉ and relative clauses
prerequisite: 7. reading: Layton, relative conversion. vocabulary
(intermediate, N): ⲁⲅⲅⲉⲗⲟⲥ ⲡⲣⲟⲫⲏⲧⲏⲥ ⲙⲁⲑⲏⲧⲏⲥ ⲡⲓⲥⲧⲓⲥ ⲁⲅⲁⲡⲏ ⲥⲱⲙⲁ
ⲥⲟⲫⲓⲁ ⲇⲩⲛⲁⲙⲓⲥ ⲉⲕⲕⲗⲏⲥⲓⲁ ⲡⲛⲉⲩⲙⲁ. quiz: {band: intermediate, pos: N}.
drill: {work: bohairic_1corinthians, verse_min: 40, verse_max: 99}. corpus:
{work: bohairic_1corinthians, verse_start: 4, verse_end: 7}. checkpoint: quiz ≥ 70%.

### Lesson 9 — Prepositions of place and agency
prerequisite: 8. reading: Till, prepositions (ϩⲛ/ϧⲉⲛ, ⲉⲃⲟⲗ ϩⲛ, ⲛⲧⲉ).
vocabulary (intermediate, ADV): ⲉⲃⲟⲗ ⲉⲙⲁⲩ ⲙⲙⲁⲩ ⲉϩⲣⲁⲓ ⲧⲉⲛⲟⲩ ⲉϩⲟⲩⲛ ⲛⲁⲙⲉ ⲧⲟⲧⲉ ⲟⲩⲏⲓ ⲡⲱⲥ. quiz: {band: intermediate, pos: ADV}. drill:
{work: bohairic_mark, verse_min: 130, verse_max: 199}. corpus:
{work: bohairic_mark, verse_start: 12, verse_end: 15}. checkpoint: quiz ≥ 70%.

### Lesson 10 — The parables read whole
prerequisite: 9. reading: none new — reread Mark with the grammar so far.
vocabulary (intermediate, mixed review): ⲥⲡⲉⲣⲙⲁ ⲧⲱⲃⲉ ⲛⲟⲩϫⲉ ⲓⲁⲣⲟ ⲥⲱⲧⲉⲙ ⲭⲱⲣⲁ ⲕⲁⲣⲡⲟⲥ ⲛⲁⲩ ⲓⲛⲓ ⲙⲟϣⲓ. quiz: {band: intermediate, pos: V}.
drill: {work: bohairic_mark, verse_min: 200, verse_max: 279}. corpus:
{work: bohairic_mark, verse_start: 16, verse_end: 19}. checkpoint: quiz ≥ 70%.

## Upper intermediate — lives and martyrdom (lessons 11–15, placeholders in 19)

### Lesson 11 — Shenoute's life: long sentences
prerequisite: 10. reading: Reintges, clause chaining. vocabulary
(advanced, N): ⲙⲟⲛⲁⲭⲟⲥ ⲁⲃⲃⲁ ⲡⲉⲧⲣⲟⲥ ϩⲙϩⲁⲗ ⲇⲓⲁⲕⲟⲛⲟⲥ ⲡⲁⲣⲑⲉⲛⲟⲥ
ⲙⲁⲣⲧⲩⲣⲟⲥ ⲥⲩⲛⲁⲅⲱⲅⲏ ⲕⲁⲛⲱⲛ ⲉⲡⲓⲥⲕⲟⲡⲟⲥ. quiz: {band: advanced, pos: N}.
drill: {work: life_of_isaac, verse_min: 0, verse_max: 49}. corpus:
{work: life_of_isaac, verse_start: 0, verse_end: 3}. checkpoint: quiz ≥ 70%.

### Lesson 12 — Purpose and result clauses
prerequisite: 11. reading: Layton, final and consecutive clauses. vocabulary
(advanced, V): ⲥⲱⲧⲡ ⲧⲁⲙⲓⲟ ⲟⲩⲱⲛϩ ⲉⲃⲟⲗ ⲁⲛⲁⲭⲱⲣⲉⲓ ⲡⲁⲣⲁⲕⲁⲗⲉⲓ ⲡⲉⲓⲑⲉ ⲛⲁⲩ ⲥⲱⲧⲉⲙ ⲓⲛⲓ. quiz: {band: advanced, pos: V}. drill:
{work: life_of_isaac, verse_min: 50, verse_max: 119}. corpus:
{work: life_of_isaac, verse_start: 4, verse_end: 7}. checkpoint: quiz ≥ 70%.

### Lesson 13 — The martyr speaks: direct discourse
prerequisite: 12. reading: Mallon, Bohairic direct speech. vocabulary
(advanced, mixed): ⲁⲡⲟⲫⲁⲥⲓⲥ ⲡⲁⲣⲣⲏⲥⲓⲁ ⲥⲧⲣⲁⲧⲏⲗⲁⲧⲏⲥ ⲡⲓⲗⲁⲧⲟⲥ ⲑⲗⲓⲯⲓⲥ ⲣⲣⲟ ϫⲟⲉⲓⲥ ⲇⲟⲩⲝ ⲉⲓⲱⲧ ⲁⲡⲁ. quiz:
{band: advanced, pos: N}. drill: {work: martyrdom_of_victor, verse_min: 0,
verse_max: 59}. corpus: {work: martyrdom_of_victor, verse_start: 0,
verse_end: 3}. checkpoint: quiz ≥ 70%.

### Lesson 14 — Lausiac brevity: sayings of the elders
prerequisite: 13. reading: Layton, nominal sentences. vocabulary (advanced,
mixed): ⲁⲡⲁ ⲛⲁⲩ ⲡⲣⲉⲥⲃⲩⲧⲉⲣⲟⲥ ⲛⲏⲥⲧⲉⲓⲁ ⲡⲣⲟⲥⲉⲩⲭⲏ ⲥⲃⲱ ϩⲩⲡⲟⲙⲟⲛⲏ ⲓⲣⲓ ⲉⲙⲓ ⲟⲩⲱⲙ. quiz: {band: advanced, pos: V}.
drill: {work: lausiac_history, verse_min: 0, verse_max: 49}. corpus:
{work: lausiac_history, verse_start: 0, verse_end: 3}. checkpoint: quiz ≥ 70%.

### Lesson 15 — Reading alone: Ruth whole
prerequisite: 14. reading: none new — the whole Ruth in Sahidic, start to
finish, with the dictionary. vocabulary (review, 20 most frequent lexical):
ⲉⲃⲟⲗ ϫⲱ ⲓⲣⲓ ⲛⲟⲩϯ ϯ ⲣⲱⲙⲉ ⲥⲁϫⲓ ϩⲏⲧ ⲁⲡⲁ ϩⲱⲃ ⲉⲙⲓ ⲥⲟⲛ ⲙⲟⲩ ⲟⲩⲁⲃ ϣⲉⲗⲉⲉⲧ
ⲥϩⲓⲙⲉ ⲕⲁϩ. quiz: {band: beginner, pos: N}. drill:
{work: sahidic_ruth, verse_min: 50, verse_max: 84}. corpus:
{work: sahidic_ruth, verse_start: 80, verse_end: 84}. checkpoint: quiz ≥ 70%.
