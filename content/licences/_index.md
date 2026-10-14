---
title: "Licences"
weight: 30
---

# Licences

Every source, what licence it carries, and what was deliberately left out. The
full manifest is `data/dist/provenance/LICENSES.csv.gz`, regenerable at
<https://coptic.re/read-csv.html>, and enforced by
`tools/validate/licence_guard.py`.

A source named on this page is not thereby redistributed here. The list exists so
the boundary is visible.

## Coptic Dictionary Online (CDO) — not included

**Coptic Dictionary Online (CDO) data is not included in this build.** The public
CDO API does not currently serve machine-readable entries;
`coptic-dictionary.org` returns its single-page application at every `/api/*`
path, and no bulk export repository is published. We have contacted the KELLIA
maintainers and asked whether a bulk export or a documented API endpoint exists,
and under what licence.

**Status: open, as of 2026-10-05.** No CDO-derived entry, example, frequency or
URN appears anywhere in this build, and the TEI parser has **no CDO dialect at
all**, deliberately, rather than a guess at a format none of us has seen.

## Three liturgical works — no upstream source exists

`shipped.toml` declares nine works. **Three do not exist in the corpus of record at
all** — there is no liturgical corpus in CopticScriptorium/corpora, so
*Lauds*, *Theotokia* and *Common Prayers* have no source to fetch. They are the
three works the plan puts first, because that is what the church uses weekly, so
this is the largest gap in coverage rather than the smallest. Outreach is by
Michael; nothing here is substituted for them, and every build names all three.

Six of the nine are present: Ruth, Mark, 1 Corinthians, the Lausiac History, the
Life of Isaac and the Martyrdom of Victor — 2,601 verses, 83,017 tokens.
