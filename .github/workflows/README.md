# .github/workflows/

GitHub Actions workflows land here.

This directory is intentionally empty of workflows for now. The first one that
belongs here is `ci.yml`, which runs exactly the three gates that already exist
and are already verified locally:

| Gate | Command | Enforces |
|------|---------|----------|
| Collation | `python tools/validate/collation_guard.py` | The 23-letter Coptic alphabet is pinned at `b7b49af6e144ef87` (v4 §1.3). Changing it fails CI until a Coptic linguist signs off on the diff. |
| Sources | `python tools/fetch/fetch_all.py --check` | Every downloaded source matches its SHA-256 and byte count in `tools/sources.lock` (v4 §7.1). |
| Tests | `pytest tools/tests` | The schema, collation, and `_TT` parser contracts. |

Wiring these up is deliberately a later step, not a guess made now: a CI file
that runs `wrangler deploy` or reaches for the network would fail in ways that
have nothing to do with the code it is meant to protect.
