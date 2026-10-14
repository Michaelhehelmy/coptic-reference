# Pagefind drops specific English terms from the index (pagefind 1.5.2)

**Reproduction:** one HTML file. One custom record. Three words.

```sh
npm install pagefind@1.5.2          # 1.5.2 is current on npm
```

`index.html`:

```html
<!doctype html><html><head><meta charset="utf-8"><title>t</title></head>
<body><p>seed</p></body></html>
```

`pagefind-entry-records.json` — the array Pagefind indexes as custom records:

```json
[{"url":"/x","content":"copper carbonate, azurite","meta":{}}]
```

```sh
pagefind --site .
```

```js
const pagefind = await import('/pagefind/pagefind.js');
for (const q of ['copper', 'carbonate', 'azurite']) {
  console.log(q, (await pagefind.search(q, {limit: 5})).results.length);
}
```

## Result

```
copper      0
carbonate   0
azurite     9
```

Three words in one document. One is findable; two adjacent to it are not. All three
are ordinary English, none is a stopword, and the document contains nothing else.

## Scope

Not project-specific. The reproduction above uses no Coptic, no dictionary, no
custom weighting, and a single record. Everything below was tried against it.

## Hypotheses ruled out

Each was tested by changing exactly one thing and rebuilding.

| Hypothesis | Test | Result |
|---|---|---|
| Co-occurrence in the document | the document is exactly the three words | **not it** — reproduced with the minimal document |
| Document scale | 50 records vs 11,369 | **not it** — identical at both |
| Coptic/Unicode script mixing | no Coptic in the document at all | **not it** |
| `weighted_ngrams` | removed entirely | **not it** — identical |
| `excerpts` | field removed entirely | **not it** — identical |
| `--force-language` | `cop`, `en`, `fr`, and the default | **not it** — identical missing set |
| Word order | content reversed | **not it** — identical missing set |
| Stemming / prefix matching | `copp`, `coppe`, `opper` | **not it** — the term is absent, not stemmed |

## The missing set is stable

One record, content = 21 words. Missing every time, under every language and in
either order:

```
copper  carbonate  coin  rust  fire  green
```

Found:

```
azurite  money  seller  smith  ore  the  and  of  blue  stone  metal  bronze
```

I have not found the property that separates these two sets. It is not length
(found: 1–13 chars; missing: 4–11), not a lexicon, not position, and not
configuration.

## Clue: the count shifts with `--force-language`

Same single record, same query, only the flag changes:

```
--force-language cop   ->  azurite: 9
(no flag)               ->  azurite: 8
```

This is the most interesting part of the report. `azurite` is not merely present
or absent — its **count** depends on a writer-side setting. And a count of 9 from
a *one-document* index shows `results.length` is not "documents matching"; it is
something the writer accumulates per language configuration.

That points at the index writer rather than the query path: something about how
terms are stored changes with the language setting, and the same mechanism that
loses `copper` also changes how `azurite` is counted.

My reading of it — offered as a guess, not a diagnosis — is that terms are written
into per-language buckets, and some terms land in a bucket the query path does not
read back. `azurite` and `copper` would then differ by which bucket they were
written to, not by anything about the words. The 9-vs-8 shift is the same effect
visible from the other side.

## How to check

Build the index in-process and inspect the writer's own term table:

```js
import { createIndex } from 'pagefind';
// ... add the record, writeFiles(), then read public/pagefind/index/*.pf_index
```

If `copper` is absent from the term table, the drop is at write time and the cause
is in the `.pf_index` encoding. If `copper` is present in the table but absent
from `search()`, the drop is in the query path.

Either result would narrow this to a single file.

## Notes

- pagefind **1.5.2**, npm, x86_64-unknown-linux-musl, Chromium 153.
- No `unsafe-eval` / WASM involvement; unrelated to CSP.
- Search is run through Pagefind's own browser API against the generated index,
  not against any hand-written index.
