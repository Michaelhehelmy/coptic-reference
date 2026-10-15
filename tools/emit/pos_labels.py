#!/usr/bin/env python3
"""tools/emit/pos_labels.py — learner-facing POS labels (Session 21 D2).

The corpus annotates with the Scriptorium tagset (APST, CREL, PPERS, ...);
learners need words, not codes. This emitter maps every tag attested in the
corpus tarball to one plain label and writes
data/dist/drill/pos_labels.json.gz. `static/js/pos_labels.js` is the one
renderer (same shape as translit.js); drill.js shows labels, never raw tags.

LABEL SOURCES. Core grammatical terms (noun, verb, article, preposition,
conjunction, pronoun, adverb, numeral, copula, negation, ...) follow the
Coptic Scriptorium part-of-speech tagging guidelines and standard Coptic
grammar terminology (Layton, Lambdin, Till). Converter terms (relative,
circumstantial, focalizing, conjunctive, conditional, preterite, jussive,
optative, causative, limitative) are the standard English names of the
corresponding Coptic constructions. Fused tags (X_PPERS/X_PPERO) compose:
base label + "with attached pronoun" — the suffix is certain from the
lemma shape (e.g. ⲁ_ⲛⲧⲟ, ϫⲡⲟ_ⲛⲧⲟ).

SEVEN LABELS REST ON CORPUS EXAMPLES rather than documentation, and are
flagged for linguist review (examples inline): VBD (past narrative verbs
like ⲡⲉϫⲁ, func root), IMOD (nominal modifiers like ⲧⲏⲣ, func
obl:unmarked/nmod:unmarked), FM (focus particles like ⲙⲟⲛⲟⲛ "only", func
appos/advmod), PPERI (dislocated independent pronouns like ⲁⲛⲟⲕ, func
dislocated), APREC (temporal auxiliaries like ⲛⲧⲉⲣⲉ, func aux),
AFUTCONJ (two tokens only: ⲧⲁⲣⲉ, read as future+conjunctive by name),
AOPT (optative auxiliary ⲉⲣⲉ, 11 tokens, func aux/mark).

FAIL-CLOSED: a tag in the tarball without a row here fails the build, so a
new annotation tag can never ship unlabeled. Written through safeio
(Rule 12), gzip mtime=0.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import argparse
import gzip
import json
import pathlib
import sys
import tarfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import safeio  # noqa: E402

TARBALL = ROOT / "data" / "dist" / "corpus" / "corpus.tar.gz"
DEST = ROOT / "data" / "dist" / "drill" / "pos_labels.json.gz"

#: Tag -> learner-facing label. Every label is a plain string and no label
#: equals its tag (parsedrill_guard enforces both).
LABELS: dict[str, str] = {
    # Open classes and everyday function words.
    "N": "noun",
    "NPROP": "proper noun (name)",
    "V": "verb",
    "VSTAT": "stative verb (state, not act)",
    "VIMP": "imperative verb (command)",
    "VBD": "past-tense verb",  # REVIEW: ⲡⲉϫⲁ-type narrative verbs, func root.
    "ART": "article (the/a)",
    "PREP": "preposition",
    "CONJ": "conjunction (and, but, or)",
    "ADV": "adverb",
    "NUM": "numeral",
    "PUNCT": "punctuation",
    "PTC": "discourse particle",
    "PDEM": "demonstrative (this, that)",
    "PINT": "question word (who, what)",
    "PPOS": "possessive (my, your, his)",
    "PPERS": "personal pronoun",
    "PPERO": "object pronoun",
    "PPERI": "independent pronoun (for emphasis)",  # REVIEW: ⲁⲛⲟⲕ-type, func dislocated.
    "IMOD": "modifier",  # REVIEW: ⲧⲏⲣ-type nominal modifiers, func obl/nmod:unmarked.
    "COP": "copula (is)",
    "EXIST": "existence verb (there is)",
    "NEG": "negation (not)",
    "FM": "focus particle (only, just)",  # REVIEW: ⲙⲟⲛⲟⲛ-type, func appos/advmod.
    "ANY": "not-yet verb form",
    "UNKNOWN": "unclassified by the annotators",
    # Tense/aspect/mood markers and converters.
    "APST": "past tense marker",
    "APREC": "temporal marker (when)",  # REVIEW: ⲛⲧⲉⲣⲉ-type, func aux.
    "FUT": "future marker (will)",
    "AOPT": "wish marker (may it be)",  # REVIEW: 11 tokens (ⲉⲣⲉ), func aux/mark.
    "AJUS": "command marker (let)",
    "AAOR": "habitual marker (usually)",  # REVIEW: ϣⲁⲣⲉ-type (140 tokens), func aux.
    "ACOND": "conditional marker (if, when)",
    "ACAUS": "causative marker (make, let)",
    "ACONJ": "conjunctive (and then)",
    "ALIM": "limitative marker (until)",
    "ANEGAOR": "negative past marker",
    "ANEGJUS": "negative command marker",
    "ANEGOPT": "negative wish marker",
    "ANEGPST": "negative past marker",
    "AFUTCONJ": "future conjunctive marker",  # REVIEW: 2 tokens (ⲧⲁⲣⲉ), name-read.
    "CPRET": "conditional past (would have)",
    "CREL": "relative converter (who, which)",
    "CCIRC": "circumstantial converter (while, as)",
    "CFOC": "focalizing converter (it is … who)",
    # Fused bound forms: base label composed with the certain suffix.
    "APST_PPERS": "past tense marker with attached pronoun",
    "AOPT_PPERS": "wish marker with attached pronoun",
    "ACOND_PPERS": "conditional marker with attached pronoun",
    "ACONJ_PPERS": "conjunctive with attached pronoun",
    "ANEGPST_PPERS": "negative past marker with attached pronoun",
    "CFOC_PPERS": "focalizing converter with attached pronoun",
    "CPRET_PPERS": "conditional past with attached pronoun",
    "CCIRC_PPERS": "circumstantial converter with attached pronoun",
    "PREP_PPERO": "preposition with attached pronoun",
    "N_PPERO": "noun with attached pronoun",
    "V_PPERO": "verb with attached pronoun",
    "IMOD_PPERO": "modifier with attached pronoun",
}


def fail(message: str) -> SystemExit:
    return SystemExit(f"[pos_labels] FAIL — {message}")


def tarball_tags(tarball: pathlib.Path = TARBALL) -> set[str]:
    """Every POS tag attested in the corpus."""
    if not tarball.is_file():
        raise fail(f"{tarball} is missing")
    tags: set[str] = set()
    with tarfile.open(tarball, "r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile() or not member.name.endswith("/tokens.json"):
                continue
            stream = archive.extractfile(member)
            if stream is None:
                raise fail(f"{member.name} unreadable")
            for tok in json.loads(stream.read().decode("utf-8"))["tokens"]:
                if tok.get("pos"):
                    tags.add(tok["pos"])
    return tags


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="learner-facing POS labels")
    ap.parse_args(argv)
    tags = tarball_tags()
    missing = sorted(tags - set(LABELS))
    if missing:
        raise fail(f"tags without labels: {', '.join(missing)} — label them, "
                   f"do not ship them raw")
    for tag, label in LABELS.items():
        if not isinstance(label, str) or not label:
            raise fail(f"{tag}: label is not a non-empty string")
        if label == tag:
            raise fail(f"{tag}: label equals its tag")
    payload = {"generated": "pos_labels-v1",
               "labels": {tag: LABELS[tag] for tag in sorted(tags)}}
    DEST.parent.mkdir(parents=True, exist_ok=True)
    size = safeio.write_verified(
        DEST, gzip.compress(json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                            compresslevel=9, mtime=0))
    print(f"[pos_labels] {len(payload['labels'])} tags -> {DEST.name} ({size:,} B gz)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
