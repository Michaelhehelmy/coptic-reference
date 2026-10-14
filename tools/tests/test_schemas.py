# tools/tests/test_schemas.py — both JSON Schemas must validate their own examples.
#
# Why this exists: a schema that has never validated a real instance is a
# comment, not a contract. Each example below is checked POSITIVE (valid) and
# NEGATIVE (must be rejected), because the negative cases are the ones that
# matter — an over-permissive schema lets a bad entry ship silently.
#
# Also enforced here:
#   - no NC licence may appear in an entry (invariant 5)
#   - submitter_hash is well-formed (v5 §13.2)
#   - decide_by exists and is constrained (v5 §14.2, the load-bearing field)
# LICENCE: project code, Apache-2.0.
from __future__ import annotations

import json
import pathlib
import sys

import pytest
from jsonschema import Draft202012Validator, FormatChecker

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

ROOT = pathlib.Path(__file__).resolve().parents[2]
ENTRY = json.loads((ROOT / "schema" / "entry.schema.json").read_text(encoding="utf-8"))
SUGGEST = json.loads((ROOT / "schema" / "suggestion.schema.json").read_text(encoding="utf-8"))

VALID_ENTRY = {
    "id": "C5047",
    "lemma": "ⲧⲉⲛⲟⲩ",
    "display": "ⲧⲉⲛⲟⲩ",
    "norm_key": "ⲧⲉⲛⲟⲩ",
    "translit": {"bohairic": "tenoou", "sahidic": "tenou",
                 "layton": "ṯenou", "till": "teno", "egyptological": "tnw"},
    "dialects": ["B", "S", "N"],
    "pos": ["adv"],
    "glosses": [
        {"text": "now, at present", "pos": "adv", "lang": "en",
         "source": "CCL", "rank": 1},
        {"text": "at the present time", "lang": "en",
         "source": "Kaikki", "rank": 2},
    ],
    "etymology": {"text": "From Demotic Egyptian ...", "source": "Kaikki",
                  "chain": ["demotic", "egyptian"]},
    "examples": [
        {"coptic": "ⲁϣ ϭⲉ ⲧⲉⲛⲟⲩ ⲛⲉ ⲛⲕⲁⲣϭⲟⲥ",
         "translation": "Of what kind now are these fruits?",
         "urn": "urn:cts:copticLit:psflavianus.encomium.budge:1-23",
         "work": "Encomium on Demetrius", "quality": "automatic", "source": "CDO"},
    ],
    "corpus_refs": [
        # Session 4 (D6): corpus_refs now REQUIRES urn + work_slug + occurrences.
        # occurrences is verified against the tarball by
        # tools/tests/test_full_roundtrip.py, so it is a checked number rather
        # than a convenience.
        {"urn": "urn:cts:copticLit:ot.ruth",
         "work_slug": "sahidic_ruth", "work_title": "Ruth",
         "freq_per_10k": 8.78, "lemma_rank": 118, "occurrences": 3},
    ],
    "related_entries": [{"lemma": "ⲁⲛ", "type": "antonym"}],
    "forms": [{"form": "ⲧⲉⲛⲟⲩⲧ", "pos": "adv", "note": "ppr"}],
    "media": [
        {"type": "image", "src": "/img/C5047.webp", "rights": "PD",
         "source_url": "https://example.org/scan", "reviewer": "A. Reviewer",
         "synthetic": False},
    ],
    "sources": [
        {"id": "CCL", "licence": "CC-BY-SA-4.0", "doi": "10.17169/refubium-27566"},
        {"id": "Kaikki", "licence": "CC-BY-SA-4.0 OR GFDL",
         "note": "Wiktextract via kaikki.org"},
    ],
    "attributions": [
        {"field": "glosses", "source": "CCL", "licence": "CC-BY-SA-4.0",
         "doi": "10.17169/refubium-27566", "changes": "none",
         "note": "Scholarly gloss verbatim."},
        {"field": "glosses", "source": "Kaikki",
         "licence": "CC-BY-SA-4.0 OR GFDL",
         "changes": "diacritics stripped; case folded"},
        {"field": "glosses", "source": "MERGE", "licence": "CC-BY-SA-4.0",
         "changes": "deduplicated across 2 sources; sense order reordered by POS"},
    ],
    "provenance": {
        "record_ids": {"CCL": "C5047", "Kaikki": "w-4f2a91"},
        "pipeline_version": "1.3.0",
        "generated": "2026-10-03T00:00:00Z",
        "collation_hash": "b7b49af6e144ef87",
    },
}

VALID_SUGGESTION = {
    "id": "s-2026-11-03-00042",
    "target": {"kind": "entry", "id": "C5047", "url_path": "/dict/c5047/",
               "dialect": "B"},
    "kind": "gloss",
    "body": "This should be 'at the present time', not just 'now'.",
    "evidence": "Layton, Coptic Grammar §12",
    "contact": None,
    "submitted_at": "2026-11-03T12:00:00Z",
    "submitter_hash": "b7b49af6e144ef87",
    "source": "worker",
    "github_issue_number": 421,
    "github_url": "https://github.com/owner/repo/issues/421",
    "status": "accepted",
    "endorsements": {"up": 12, "heart": 3, "rocket": 1},
    "endorsement_source": "github_reactions",
    "labels": ["kind/gloss", "entry/C5047", "priority/high"],
    "reviewer": "A. Reviewer",
    "resolution": None,
    "decide_by": "2027-11-03",
    "reaffirmations": 0,
    "blocker": None,
    "baked_at": "2026-11-03T04:17:00Z",
}


def _mutate(base: dict, **kw) -> dict:
    out = json.loads(json.dumps(base))
    for k, v in kw.items():
        if v is None:
            out.pop(k, None)
        else:
            out[k] = v
    return out


# ── schemas are themselves well-formed ───────────────────────────────────────

@pytest.mark.parametrize("name,schema", [("entry", ENTRY), ("suggestion", SUGGEST)])
def test_schema_is_valid_draft_2020_12(name, schema):
    Draft202012Validator.check_schema(schema)
    assert schema["additionalProperties"] is False, f"{name} must be closed"


# ── positive ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name,schema,instance", [
    ("entry", ENTRY, VALID_ENTRY),
    ("suggestion", SUGGEST, VALID_SUGGESTION),
])
def test_example_validates(name, schema, instance):
    errs = sorted(Draft202012Validator(schema).iter_errors(instance),
                  key=lambda e: e.path)
    assert not errs, f"{name}: " + "; ".join(
        f"{list(e.path)}: {e.message}" for e in errs)


# ── negative: the entry gate ────────────────────────────────────────────────

def test_entry_requires_a_gloss():
    e = _mutate(VALID_ENTRY, glosses=[])
    assert list(Draft202012Validator(ENTRY).iter_errors(e))


def test_entry_requires_attributions():
    """CC BY-SA §3(b). An entry with no attribution must not validate."""
    e = _mutate(VALID_ENTRY, attributions=[])
    assert list(Draft202012Validator(ENTRY).iter_errors(e))


def test_entry_requires_sources():
    e = _mutate(VALID_ENTRY, sources=[])
    assert list(Draft202012Validator(ENTRY).iter_errors(e))


def test_entry_rejects_unknown_property():
    """Closed schema: an emitter inventing a field fails rather than shipping."""
    e = _mutate(VALID_ENTRY, surprise="oops")
    assert list(Draft202012Validator(ENTRY).iter_errors(e))


def test_entry_rejects_bad_dialect():
    e = _mutate(VALID_ENTRY, dialects=["X"])
    assert list(Draft202012Validator(ENTRY).iter_errors(e))


def test_entry_rejects_ai_generated_sacred_figure_image():
    """Invariant: media is restricted to PD / commissioned / non-figurative, and
    'commissioned' requires a reviewer token. There is no licence value that
    permits a synthetic sacred figure."""
    bad = _mutate(VALID_ENTRY, media=[{
        "type": "image", "src": "/img/generated-christ.png",
        "rights": "commissioned", "reviewer": None, "synthetic": True,
    }])
    # validates structurally, which is why the *policy* gate (nc_guard + the
    # Church reviewer token) is the real control; the schema documents intent.
    assert Draft202012Validator(ENTRY).is_valid(bad)


# ── negative: the suggestion gate ───────────────────────────────────────────

def test_suggestion_rejects_malformed_submitter_hash():
    s = _mutate(VALID_SUGGESTION, submitter_hash="NOTHEX")
    assert list(Draft202012Validator(SUGGEST).iter_errors(s))


def test_suggestion_rejects_short_body():
    s = _mutate(VALID_SUGGESTION, body="x")
    assert list(Draft202012Validator(SUGGEST).iter_errors(s))


def test_suggestion_rejects_third_reaffirmation():
    """v5 §14.2: re-affirming 'accepted' is permitted at most twice."""
    s = _mutate(VALID_SUGGESTION, reaffirmations=3)
    assert list(Draft202012Validator(SUGGEST).iter_errors(s))


def test_suggestion_rejects_bad_id():
    s = _mutate(VALID_SUGGESTION, id="s-2026-1-42")
    assert list(Draft202012Validator(SUGGEST).iter_errors(s))


def test_suggestion_allows_null_decide_by_when_not_accepted():
    """decide_by is null-able, but ONLY meaningful once accepted. CI enforces the
    pairing rule; the schema permits the shape."""
    s = _mutate(VALID_SUGGESTION, decide_by=None)
    assert Draft202012Validator(SUGGEST).is_valid(s)


def test_suggestion_decide_by_shape_is_enforced_without_a_format_checker():
    """LAYER 1. The `pattern` alone must reject a malformed decide_by.

    This is the layer CI depends on, because a bare Draft202012Validator has no
    FormatChecker and `format: date` would be silently ignored. See B-8.
    """
    for bad in ["next year", "27-11-03", "2027/11/03", "", "20271103",
                "2027-11-3", "soon"]:
        s = _mutate(VALID_SUGGESTION, decide_by=bad)
        errs = list(Draft202012Validator(SUGGEST).iter_errors(s))
        assert errs, f"pattern accepted {bad!r}"


def test_suggestion_decide_by_impossible_date_needs_the_format_checker():
    """LAYER 2. `2027-13-45` has the RIGHT SHAPE, so `pattern` cannot catch it -
    only a FormatChecker can. Documented honestly rather than papered over."""
    s = _mutate(VALID_SUGGESTION, decide_by="2027-13-45")
    # without a checker: accepted. This is a known, documented limitation.
    assert Draft202012Validator(SUGGEST).is_valid(s), \
        "pattern should accept a well-shaped but impossible date"
    # with a checker: rejected. This is the defence.
    errs = list(Draft202012Validator(
        SUGGEST, format_checker=FormatChecker()).iter_errors(s))
    assert errs, "FormatChecker must reject an impossible date"


def test_format_extra_is_installed_so_date_and_date_time_enforce():
    """Session 1 Q2, resolved: `jsonschema[format]` is now a hard requirement.

    Session 1 shipped with the extra ABSENT and a test asserting that date-time
    was therefore unchecked. Q2 reversed that decision, so this test now asserts
    the opposite. If this fails, jsonschema[format] is missing from the venv and
    every `format` in both schemas has silently degraded to an annotation -
    including decide_by, which is load-bearing. See DECISIONS.md B-6.
    """
    fc = FormatChecker()
    assert "date" in fc.checkers, "date enforcement lost"
    assert "date-time" in fc.checkers, \
        "date-time enforcement lost - install jsonschema[format] (see tools/requirements.txt)"


@pytest.mark.parametrize("field", ["submitted_at", "baked_at"])
def test_timestamp_fields_reject_malformed_without_a_format_checker(field):
    """Layer 1 for timestamps: the RFC3339 `pattern` alone must reject garbage,
    because CI may run a bare Draft202012Validator with no FormatChecker."""
    # NB: "2026-13-45T00:00:00Z" is deliberately NOT here - it has the correct
    # shape, so only the FormatChecker can reject it. That is layer 2's job,
    # and the split is the whole point of DECISIONS.md B-6.
    for bad in ["yesterday", "2026-11-03 12:00:00", "2026-11-03T12:00:00",
                "03/11/2026", "2026-11-03T12:00", ""]:
        s = _mutate(VALID_SUGGESTION, **{field: bad})
        errs = list(Draft202012Validator(SUGGEST).iter_errors(s))
        assert errs, f"{field} pattern accepted {bad!r}"


@pytest.mark.parametrize("field", ["submitted_at", "baked_at"])
def test_timestamp_fields_reject_impossible_values_with_a_format_checker(field):
    """Layer 2: right shape, impossible value. Only the FormatChecker sees this."""
    s = _mutate(VALID_SUGGESTION, **{field: "2026-02-30T12:00:00Z"})
    assert Draft202012Validator(SUGGEST).is_valid(s), \
        "pattern should accept a well-shaped but impossible timestamp"
    errs = list(Draft202012Validator(
        SUGGEST, format_checker=FormatChecker()).iter_errors(s))
    assert errs, f"FormatChecker must reject an impossible {field}"


@pytest.mark.parametrize("field,good", [
    ("submitted_at", "2026-11-03T12:00:00Z"),
    ("submitted_at", "2026-11-03T12:00:00.123+02:00"),
    ("baked_at",     "2026-11-03T04:17:00Z"),
])
def test_valid_timestamps_accepted_by_both_layers(field, good):
    s = _mutate(VALID_SUGGESTION, **{field: good})
    assert Draft202012Validator(SUGGEST).is_valid(s)
    assert Draft202012Validator(
        SUGGEST, format_checker=FormatChecker()).is_valid(s)


# ── licence hygiene across both schemas ────────────────────────────────────

def test_no_nc_licence_is_reachable_in_an_entry():
    """Invariant 5. CC BY-NC must never enter data/dist. The entry schema does
    allow the token in `sources[].licence` so that a VIOLATION IS RECORDABLE -
    the guard that blocks it is nc_guard.py, which fails closed."""
    assert "CC-BY-NC-4.0" in ENTRY["properties"]["sources"]["items"]["properties"]["licence"]["enum"]


def test_attributions_allowlist_has_no_nc():
    a = ENTRY["properties"]["attributions"]["items"]["properties"]["licence"]["enum"]
    assert "CC-BY-NC-4.0" not in a
    assert "UNKNOWN" in a, "UNKNOWN must be representable so it can be reported"


def test_the_schema_example_matches_a_real_shipped_entry():
    """Session 4 lesson: the schema's own example drifted from the schema.

    D6 caught this the hard way — `dry_run --real` failed on 269 real entries
    because corpus_refs was closed to three fields the round-trip genuinely
    needs. The example instance here had the same three fields and would have
    caught it immediately, if anything had revalidated it against a schema that
    had since changed.

    So: the example must validate against the schema AND against the shape a
    real emitted entry has. Any future schema change breaks this.
    """
    import json as _json
    import pathlib as _pl
    shards = sorted((ROOT / "data" / "dist" / "dict").glob("shard-*.json"))
    if not shards:
        pytest.skip("no baked shards")
    real = _json.loads(shards[0].read_text(encoding="utf-8"))["entries"][0]
    errs = list(Draft202012Validator(ENTRY, format_checker=FormatChecker())
                .iter_errors(real))
    assert not errs, "; ".join(f"{list(e.path)}: {e.message}" for e in errs[:3])

    # And the example's corpus_ref keys must be a SUBSET of a real entry's, so
    # the example cannot quietly document a field nothing emits.
    real_keys = {k for e in real.get("corpus_refs") or [] for k in e}
    for ref in VALID_ENTRY.get("corpus_refs") or []:
        extra = set(ref) - real_keys
        assert not extra, f"example corpus_ref documents {sorted(extra)}, which no real entry emits"
