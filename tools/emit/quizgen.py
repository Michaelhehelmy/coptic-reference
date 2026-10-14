#!/usr/bin/env python3
"""tools/emit/quizgen.py — emit traceable static quiz banks from shipped data.

LICENCE: project code, Apache-2.0.

Session 16 D1/C1-C6. Every quiz item is a fact already present in the shipped
dataset; nothing here composes language, invents a gloss, or asks a language
model. The generator selects prompts, choices, and the correct answer from:

- a dictionary shard entry (`shard`, `offset`, `entry_id`), or
- a pinned corpus token plus the dictionary entry it resolves to.

Traceability is structural: each item carries the coordinates needed to reread
its answer from the source. `tools/validate/quiz_guard.py` independently checks
those coordinates and refuses to publish anything whose correct answer is not
derivable.

Difficulty is corpus frequency, exactly as specified:

- ranks 1–300: beginner
- ranks 301–1,000: intermediate
- ranks 1,001 and above: advanced

The rank is global, by the summed `occurrences` in an entry's `corpus_refs`,
with ties broken deterministically by `norm_key` and then entry id. Only
entries with a positive corpus total can be banded; an untested word has no
frequency and therefore no band.

Transliteration prompts are the one intentionally subtle case. The live shards
currently contain no nonempty `translit` schemes, but they do contain
Kaikki-derived source forms with `kind == "romanization"`. Those are data, so a
`transliteration_to_coptic` item may use one — but only through the single
renderer, `static/js/translit.js`, invoked here through
`tools/emit/translit_probe.mjs`. The generator never constructs or normalizes a
romanization itself. It records the source form's index, so the string can be
reread from the shard.

Distractor discipline:

- same primary part of speech and same difficulty band;
- exact option text is unique;
- no distractor is another correct answer for the target prompt;
- choices are deterministically shuffled with a per-item seed.

Determinism is load-bearing. Shard order, candidate order, tie-breakers, choice
order, and gzip `mtime=0` are all fixed, so the same dataset always emits the
same bank.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import pathlib
import random
import re
import shutil
import subprocess
import sys
import tarfile
import unicodedata

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import safeio  # noqa: E402
import shardio  # noqa: E402

DICT = ROOT / "data" / "dist" / "dict"
TARBALL = ROOT / "data" / "dist" / "corpus" / "corpus.tar.gz"
QUIZ_DIR = ROOT / "data" / "dist" / "quiz"
TRANSLIT_PROBE = HERE / "translit_probe.mjs"
QUIZ_SEED = 20261016
CHOICE_COUNT = 4
DIALECT_CHOICE_COUNT = 3
TARGETS_PER_BAND = 50
DIALECT_TARGETS_PER_BAND = 30
VERSE_ITEMS = 120
VERSE_TARGETS_PER_WORK = 20

BANDS = ("beginner", "intermediate", "advanced")
BAND_LIMITS = ((300, "beginner"), (1000, "intermediate"), (float("inf"), "advanced"))
DIALECT_LABELS = {
    "A": "Assiutic",
    "Ak": "Akhmimic",
    "B": "Bohairic",
    "F": "Fayumic",
    "N": "N (undetermined)",
    "S": "Sahidic",
}
TYPE_SPECS = {
    "coptic_to_english": {"prefix": "c2e", "prompt_kind": "lemma", "answer_kind": "gloss"},
    "english_to_coptic": {"prefix": "e2c", "prompt_kind": "gloss", "answer_kind": "lemma"},
    "transliteration_to_coptic": {
        "prefix": "t2c",
        "prompt_kind": "romanization",
        "answer_kind": "lemma",
    },
    "lemma_identification": {
        "prefix": "lemma",
        "prompt_kind": "inflected_form",
        "answer_kind": "lemma",
    },
    "pos_identification": {"prefix": "pos", "prompt_kind": "lemma", "answer_kind": "pos"},
    "dialect_identification": {
        "prefix": "dialect",
        "prompt_kind": "lemma",
        "answer_kind": "dialect",
    },
    "verse_matching": {
        "prefix": "verse",
        "prompt_kind": "coptic_verse",
        "answer_kind": "translation",
    },
}

COOCCURRENCE_SPLIT = re.compile(r"\s+")


class QuizGenError(SystemExit):
    """Refuse to emit an incomplete or unverifiable bank."""


def fail(message: str) -> QuizGenError:
    return QuizGenError(f"[quizgen] {message}")


def clean_display(text: str) -> str:
    """User-visible strings, but nothing semantic is changed."""
    return " ".join(unicodedata.normalize("NFC", text or "").split())


def choice_key(text: str) -> str:
    """Exact duplicates are forbidden; near-synonyms are not resolved here."""
    return unicodedata.normalize("NFC", text.strip().casefold())


def shard_number(path: pathlib.Path) -> int:
    match = re.fullmatch(r"shard-(\d+)\.json(?:\.gz)?", path.name)
    if not match:
        raise fail(f"unexpected shard filename {path.name}")
    return int(match.group(1))


def read_entries() -> tuple[list[dict], dict[str, dict]]:
    paths = shardio.shard_paths(DICT)
    if not paths:
        raise fail(f"no dictionary shards in {DICT}")
    entries: list[dict] = []
    coordinates: dict[str, dict] = {}
    for path in paths:
        blob = shardio.read_shard(path, strict=True)
        if blob is None:
            raise fail(f"{path.name}: no shard object")
        shard = shard_number(path)
        items = blob.get("entries", [])
        if not isinstance(items, list):
            raise fail(f"{path.name}: entries is not a list")
        for offset, entry in enumerate(items):
            if not isinstance(entry, dict):
                raise fail(f"{path.name} offset {offset}: entry is not an object")
            entry_id = entry.get("id")
            if not entry_id or not isinstance(entry_id, str):
                raise fail(f"{path.name} offset {offset}: entry has no string id")
            if entry_id in coordinates:
                raise fail(f"duplicate entry id {entry_id}")
            coordinates[entry_id] = {"shard": shard, "offset": offset}
            entries.append(entry)
    if not entries:
        raise fail(f"no dictionary entries in {DICT}")
    return entries, coordinates


def frequency_ranks(entries: list[dict]) -> tuple[dict[str, int], dict[str, int]]:
    totals: dict[str, int] = {}
    for entry in entries:
        total = 0
        for ref in entry.get("corpus_refs") or []:
            if isinstance(ref, dict) and isinstance(ref.get("occurrences"), int):
                total += ref["occurrences"]
        totals[entry["id"]] = total
    attested = [entry_id for entry_id, total in totals.items() if total > 0]
    if not attested:
        raise fail("no corpus-attested dictionary entries; nothing can be banded")
    by_id = {entry["id"]: entry for entry in entries}
    ordered = sorted(
        attested,
        key=lambda entry_id: (
            -totals[entry_id],
            by_id[entry_id].get("norm_key", ""),
            entry_id,
        ),
    )
    ranks = {entry_id: rank for rank, entry_id in enumerate(ordered, 1)}
    return ranks, totals


def difficulty(rank: int) -> str:
    for limit, band in BAND_LIMITS:
        if rank <= limit:
            return band
    raise fail(f"invalid frequency rank {rank}")


def first_gloss(entry: dict) -> str:
    for gloss in entry.get("glosses") or []:
        if isinstance(gloss, dict):
            text = clean_display(gloss.get("text", ""))
            if text:
                return text
    return ""


def all_gloss_keys(entry: dict) -> set[str]:
    return {
        choice_key(gloss.get("text", ""))
        for gloss in entry.get("glosses") or []
        if isinstance(gloss, dict) and clean_display(gloss.get("text", ""))
    }


def primary_pos(entry: dict) -> str:
    pos = entry.get("pos") or []
    return pos[0] if isinstance(pos, list) and pos and isinstance(pos[0], str) else ""


def coptic_forms(entry: dict, kind: str) -> list[tuple[int, str]]:
    """Unique Coptic form strings of one kind, preserving source order."""
    forms: list[tuple[int, str]] = []
    seen: set[str] = set()
    for index, form in enumerate(entry.get("forms") or []):
        if not isinstance(form, dict) or form.get("kind") != kind:
            continue
        text = clean_display(form.get("form", ""))
        if not text or not any("\u2c80" <= char <= "\u2cff" for char in text):
            continue
        if text in seen:
            continue
        seen.add(text)
        forms.append((index, text))
    return forms


def romanization_forms(entry: dict) -> list[tuple[int, str]]:
    forms: list[tuple[int, str]] = []
    seen: set[str] = set()
    for index, form in enumerate(entry.get("forms") or []):
        if not isinstance(form, dict) or form.get("kind") != "romanization":
            continue
        text = clean_display(form.get("form", ""))
        if not text or text in seen:
            continue
        seen.add(text)
        forms.append((index, text))
    return forms


def render_transliterations(tasks: list[dict]) -> list[str]:
    """Ask the shipped renderer for prompts; Python never formats transliteration.

    The payload is the smallest object the renderer needs. Anything else would be
    a second implementation of the rule the renderer owns.
    """
    node = shutil.which("node")
    if node is None:
        raise fail("node is required to call static/js/translit.js")
    payload = "\n".join(json.dumps({
        "translit": task.get("translit") or {},
        "forms": task.get("forms") or [],
        "scheme": task.get("scheme", "romanization"),
    }, ensure_ascii=False) for task in tasks)
    proc = subprocess.run(
        [node, str(TRANSLIT_PROBE)],
        input=payload.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise fail(f"translit_probe.mjs failed: {proc.stderr.decode().strip()}")
    lines = proc.stdout.decode("utf-8").splitlines()
    if len(lines) != len(tasks):
        raise fail(f"translit probe returned {len(lines)} prompts for {len(tasks)} tasks")
    try:
        return [json.loads(line) for line in lines]
    except json.JSONDecodeError as e:
        raise fail(f"translit probe returned invalid JSON: {e}") from e


def place_choices(correct: str, distractors: list[str], item_id: str,
                    expected: int = CHOICE_COUNT) -> tuple[list[str], int]:
    choices = [correct, *distractors]
    if len(choices) != expected:
        raise fail(f"{item_id}: expected {expected} choices, selected {len(choices)}")
    if len({choice_key(choice) for choice in choices}) != expected:
        raise fail(f"{item_id}: choices are not unique after selection")
    seed = f"{QUIZ_SEED}:{item_id}".encode("utf-8")
    rng = random.Random(int(hashlib.sha256(seed).hexdigest(), 16))
    rng.shuffle(choices)
    return choices, choices.index(correct)


def read_corpus() -> tuple[dict[str, dict], dict[str, dict]]:
    if not TARBALL.is_file():
        raise fail(f"{TARBALL} is missing; fetch the corpus before generating quizzes")
    works: dict[str, dict] = {}
    texts: dict[str, dict] = {}
    with tarfile.open(TARBALL, "r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            slug, _, name = member.name.partition("/")
            if not slug or name not in {"meta.json", "text.json", "tokens.json"}:
                continue
            stream = archive.extractfile(member)
            if stream is None:
                raise fail(f"{member.name}: cannot read corpus member")
            payload = json.loads(stream.read().decode("utf-8"))
            works.setdefault(slug, {})[name] = payload
    for slug, docs in works.items():
        for name in ("meta.json", "text.json", "tokens.json"):
            if name not in docs:
                raise fail(f"{slug}: {name} is missing from the corpus tarball")
        texts[slug] = {member: docs[member] for member in ("meta.json", "text.json", "tokens.json")}
    if not texts:
        raise fail(f"no corpus works in {TARBALL}")
    return texts, works


def norm_to_entry(entries: list[dict]) -> dict[str, dict]:
    mapping: dict[str, dict] = {}
    for entry in entries:
        norm = entry.get("norm_key")
        if isinstance(norm, str) and norm and norm not in mapping:
            mapping[norm] = entry
    return mapping


def banded(entries: list[dict], ranks: dict[str, int], band: str) -> list[dict]:
    return sorted(
        (entry for entry in entries if ranks.get(entry["id"], 0) and difficulty(ranks[entry["id"]]) == band),
        key=lambda entry: (ranks[entry["id"]], entry.get("norm_key", ""), entry["id"]),
    )


def glosses_ready(entries: list[dict]) -> list[dict]:
    return [entry for entry in entries if first_gloss(entry)]


def choose_distractor_entries(
    target: dict,
    pool: list[dict],
    totals: dict[str, int],
    ranks: dict[str, int],
    choice_texts: dict[str, set[str]],
    forbidden: set[str],
    needed: int = CHOICE_COUNT - 1,
) -> list[dict]:
    """Three same-POS, same-band entries whose displayed answers are safe."""
    target_pos = primary_pos(target)
    chosen: list[dict] = []
    used_texts = set(forbidden)
    ordered = sorted(
        (candidate for candidate in pool
         if candidate["id"] != target["id"]
         and primary_pos(candidate) == target_pos
         and candidate["id"] in ranks),
        key=lambda candidate: (
            abs(totals[candidate["id"]] - totals[target["id"]]),
            ranks[candidate["id"]],
            candidate.get("norm_key", ""),
            candidate["id"],
        ),
    )
    for candidate in ordered:
        texts = choice_texts.get(candidate["id"], set())
        if len(texts) != 1:
            continue
        text = next(iter(texts))
        key = choice_key(text)
        if not text or key in used_texts:
            continue
        used_texts.add(key)
        chosen.append(candidate)
        if len(chosen) == needed:
            return chosen
    raise fail(
        f"cannot find three safe distractor entries for {target.get('id')} "
        f"({target.get('lemma')}); pool is too narrow"
    )


def entry_source(entry: dict, coordinates: dict[str, dict]) -> dict:
    return {
        "entry_id": entry["id"],
        "shard": coordinates[entry["id"]]["shard"],
        "offset": coordinates[entry["id"]]["offset"],
    }


def entry_item(
    item_type: str,
    prefix: str,
    sequence: int,
    prompt: str,
    choices: list[str],
    correct: int,
    target: dict,
    coordinates: dict,
    ranks: dict[str, int],
    totals: dict[str, int],
    prompt_kind: str,
    answer_kind: str,
    source: dict | None = None,
    expected_choices: int = CHOICE_COUNT,
) -> dict:
    rank = ranks[target["id"]]
    item_id = f"q-{prefix}-{sequence:05d}"
    ordered, index = place_choices(choices[0], choices[1:], item_id, expected_choices)
    if index != correct:
        # place_choices returns the index; keep the explicit parameter honest.
        correct = index
    return {
        "id": item_id,
        "type": item_type,
        "prompt": prompt,
        "choices": ordered,
        "correct": correct,
        "source": {
            "entry_id": target["id"],
            "shard": coordinates[target["id"]]["shard"],
            "offset": coordinates[target["id"]]["offset"],
            **(source or {}),
        },
        "difficulty": difficulty(rank),
        "freq_rank": rank,
        "frequency_total": totals[target["id"]],
        "prompt_kind": prompt_kind,
        "answer_kind": answer_kind,
    }


def coptic_to_english_items(
    entries: list[dict],
    coordinates: dict[str, dict],
    ranks: dict[str, int],
    totals: dict[str, int],
    band: str,
) -> list[dict]:
    pool = glosses_ready(banded(entries, ranks, band))
    choice_texts = {entry["id"]: {first_gloss(entry)} for entry in pool}
    forbidden_by_id = {entry["id"]: all_gloss_keys(entry) for entry in entries}
    items: list[dict] = []
    for target in pool:
        if len(items) >= TARGETS_PER_BAND:
            break
        try:
            distractors = choose_distractor_entries(
                target, pool, totals, ranks, choice_texts, forbidden_by_id[target["id"]])
        except QuizGenError:
            continue
        choices = [first_gloss(target), *(first_gloss(d) for d in distractors)]
        item = entry_item(
            "coptic_to_english", TYPE_SPECS["coptic_to_english"]["prefix"],
            len(items) + 1, target["lemma"], choices, 0, target, coordinates,
            ranks, totals, "lemma", "gloss")
        item["source"]["choice_sources"] = [entry_source(d, coordinates) for d in distractors]
        items.append(item)
    if len(items) < 10:
        raise fail(f"coptic_to_english {band}: only {len(items)} items; need at least 10")
    return items


def english_to_coptic_items(
    entries: list[dict],
    coordinates: dict[str, dict],
    ranks: dict[str, int],
    totals: dict[str, int],
    band: str,
) -> list[dict]:
    pool = glosses_ready(banded(entries, ranks, band))
    # One gloss, one lemma: if two entries share the displayed gloss, the prompt
    # would have two right answers, so keep the highest-frequency one only.
    seen: dict[str, dict] = {}
    for entry in pool:
        key = choice_key(first_gloss(entry))
        if key not in seen:
            seen[key] = entry
    pool = list(seen.values())
    choice_texts = {entry["id"]: {entry["lemma"]} for entry in pool}
    forbidden_by_id = {entry["id"]: {choice_key(entry["lemma"])} for entry in entries}
    items: list[dict] = []
    for target in pool:
        if len(items) >= TARGETS_PER_BAND:
            break
        prompt = first_gloss(target)
        try:
            distractors = [
                candidate for candidate in choose_distractor_entries(
                    target, pool, totals, ranks, choice_texts,
                    forbidden_by_id[target["id"]])
            ]
        except QuizGenError:
            continue
        # A distractor lemma is also correct when one of its own glosses is the
        # prompt. That is a different question hiding in the choices.
        if any(choice_key(prompt) in all_gloss_keys(candidate) for candidate in distractors):
            continue
        choices = [target["lemma"], *(d["lemma"] for d in distractors)]
        entry = dict(target)
        item = entry_item(
            "english_to_coptic", TYPE_SPECS["english_to_coptic"]["prefix"],
            len(items) + 1, prompt, choices, 0, entry, coordinates,
            ranks, totals, "gloss", "lemma",
            source={"gloss_index": 0})
        item["source"]["choice_sources"] = [entry_source(d, coordinates) for d in distractors]
        items.append(item)
    if len(items) < 10:
        raise fail(f"english_to_coptic {band}: only {len(items)} items; need at least 10")
    return items


def transliteration_items(
    entries: list[dict],
    coordinates: dict[str, dict],
    ranks: dict[str, int],
    totals: dict[str, int],
    band: str,
) -> list[dict]:
    pool = banded(entries, ranks, band)
    candidates = [entry for entry in pool if romanization_forms(entry)]
    prompts = render_transliterations([
        {"translit": entry.get("translit") or {},
         "forms": entry.get("forms") or [],
         "scheme": "romanization"}
        for entry in candidates
    ])
    usable: list[tuple[dict, str]] = []
    for entry, prompt in zip(candidates, prompts):
        if not prompt:
            continue
        forms = romanization_forms(entry)
        form_index = next((index for index, text in forms if text == prompt), None)
        if form_index is None:
            raise fail(f"{entry['id']}: renderer prompt {prompt!r} is not a source form")
        usable.append((entry, prompt))
    seen: dict[str, dict] = {}
    for entry, prompt in usable:
        key = choice_key(prompt)
        if key not in seen:
            seen[key] = entry
    pool = list(seen.values())
    source_forms = {
        entry["id"]: next(
            text for _, text in romanization_forms(entry)
            if choice_key(text) == choice_key(
                next(prompt for candidate, prompt in usable if candidate["id"] == entry["id"]))
        )
        for entry in pool
    }
    choice_texts = {entry["id"]: {entry["lemma"]} for entry in pool}
    forbidden_by_id = {entry["id"]: {choice_key(entry["lemma"])} for entry in entries}
    items: list[dict] = []
    for target in pool:
        if len(items) >= TARGETS_PER_BAND:
            break
        prompt = next(prompt for candidate, prompt in usable if candidate["id"] == target["id"])
        try:
            distractors = choose_distractor_entries(
                target, pool, totals, ranks, choice_texts, forbidden_by_id[target["id"]])
        except QuizGenError:
            continue
        if any(prompt in {text for _, text in romanization_forms(candidate)}
               for candidate in distractors):
            continue
        choices = [target["lemma"], *(d["lemma"] for d in distractors)]
        form_index = next(
            index for index, text in romanization_forms(target) if text == prompt)
        forms = target.get("forms") or []
        raw_form = forms[form_index] if 0 <= form_index < len(forms) else {}
        source_form = raw_form if isinstance(raw_form, dict) else {}
        snapshot = target.get("translit")
        item = entry_item(
            "transliteration_to_coptic",
            TYPE_SPECS["transliteration_to_coptic"]["prefix"],
            len(items) + 1, prompt, choices, 0, target, coordinates,
            ranks, totals, "romanization", "lemma",
            source={"translit_scheme": "romanization",
                    "translit_source": "forms.romanization",
                    "form_index": form_index,
                    "translit_snapshot": snapshot if isinstance(snapshot, dict) else {},
                    "romanization_forms": [{
                        "form": source_form.get("form", ""),
                        "kind": "romanization",
                        "pos": source_form.get("pos"),
                    }]})
        item["source"]["choice_sources"] = [entry_source(d, coordinates) for d in distractors]
        items.append(item)
    if len(items) < 10:
        raise fail(f"transliteration_to_coptic {band}: only {len(items)} items; need at least 10")
    return items


def lemma_identification_items(
    entries: list[dict],
    coordinates: dict[str, dict],
    ranks: dict[str, int],
    totals: dict[str, int],
    band: str,
) -> list[dict]:
    pool = banded(entries, ranks, band)
    surface: dict[str, list[dict]] = {}
    for entry in pool:
        for _, text in coptic_forms(entry, "inflection"):
            if text == entry.get("lemma"):
                continue
            surface.setdefault(choice_key(text), []).append(entry)
    pool = [entry for entry in pool
            if any(choice_key(text) in surface and len(surface[choice_key(text)]) == 1
                   for _, text in coptic_forms(entry, "inflection")
                   if text != entry.get("lemma"))]
    choice_texts = {entry["id"]: {entry["lemma"]} for entry in pool}
    forbidden_by_id = {entry["id"]: {choice_key(entry["lemma"])} for entry in entries}
    items: list[dict] = []
    for target in pool:
        if len(items) >= TARGETS_PER_BAND:
            break
        forms = [(index, text) for index, text in coptic_forms(target, "inflection")
                 if text != target.get("lemma")
                 and len(surface.get(choice_key(text), [])) == 1]
        if not forms:
            continue
        form_index, prompt = forms[0]
        try:
            distractors = choose_distractor_entries(
                target, pool, totals, ranks, choice_texts, forbidden_by_id[target["id"]])
        except QuizGenError:
            continue
        if any(any(text == prompt for _, text in coptic_forms(candidate, "inflection"))
               for candidate in distractors):
            continue
        choices = [target["lemma"], *(d["lemma"] for d in distractors)]
        item = entry_item(
            "lemma_identification", TYPE_SPECS["lemma_identification"]["prefix"],
            len(items) + 1, prompt, choices, 0, target, coordinates,
            ranks, totals, "inflected_form", "lemma",
            source={"form_index": form_index, "form_kind": "inflection"})
        item["source"]["choice_sources"] = [entry_source(d, coordinates) for d in distractors]
        items.append(item)
    if len(items) < 10:
        raise fail(f"lemma_identification {band}: only {len(items)} items; need at least 10")
    return items


def pos_identification_items(
    entries: list[dict],
    coordinates: dict[str, dict],
    ranks: dict[str, int],
    totals: dict[str, int],
    band: str,
) -> list[dict]:
    pool = [entry for entry in banded(entries, ranks, band) if primary_pos(entry)]
    items: list[dict] = []
    for target in pool:
        if len(items) >= TARGETS_PER_BAND:
            break
        forbidden = set(target.get("pos") or [])
        alternatives: list[str] = []
        alternative_sources: list[dict] = []
        ordered = sorted(
            (candidate for candidate in pool
             if candidate["id"] != target["id"]
             and primary_pos(candidate) == primary_pos(target)),
            key=lambda candidate: (
                abs(totals[candidate["id"]] - totals[target["id"]]),
                ranks[candidate["id"]],
                candidate.get("norm_key", ""),
                candidate["id"],
            ),
        )
        for candidate in ordered:
            for pos in candidate.get("pos") or []:
                if pos in forbidden or pos in alternatives:
                    continue
                alternatives.append(pos)
                alternative_sources.append(candidate)
                break
            if len(alternatives) == CHOICE_COUNT - 1:
                break
        if len(alternatives) != CHOICE_COUNT - 1:
            continue
        correct = primary_pos(target)
        choices = [correct, *alternatives]
        item = entry_item(
            "pos_identification", TYPE_SPECS["pos_identification"]["prefix"],
            len(items) + 1, target["lemma"], choices, 0, target, coordinates,
            ranks, totals, "lemma", "pos")
        item["source"]["choice_sources"] = [
            {"entry_id": candidate["id"],
             "shard": coordinates[candidate["id"]]["shard"],
             "offset": coordinates[candidate["id"]]["offset"]}
            for candidate in alternative_sources
        ]
        items.append(item)
    if len(items) < 10:
        raise fail(f"pos_identification {band}: only {len(items)} items; need at least 10")
    return items


def dialect_identification_items(
    entries: list[dict],
    coordinates: dict[str, dict],
    ranks: dict[str, int],
    totals: dict[str, int],
    band: str,
) -> list[dict]:
    pool = [entry for entry in banded(entries, ranks, band)
            if len(entry.get("dialects") or []) == 1
            and (entry.get("dialects") or [""])[0] in DIALECT_LABELS]
    items: list[dict] = []
    for target in pool:
        if len(items) >= DIALECT_TARGETS_PER_BAND:
            break
        correct_code = (target.get("dialects") or [""])[0]
        forbidden = set(target.get("dialects") or [])
        alternatives: list[str] = []
        alternative_sources: list[dict] = []
        ordered = sorted(
            (candidate for candidate in pool
             if candidate["id"] != target["id"]
             and primary_pos(candidate) == primary_pos(target)),
            key=lambda candidate: (
                abs(totals[candidate["id"]] - totals[target["id"]]),
                ranks[candidate["id"]],
                candidate.get("norm_key", ""),
                candidate["id"],
            ),
        )
        for candidate in ordered:
            code = (candidate.get("dialects") or [""])[0]
            if code in forbidden or code in alternatives or code not in DIALECT_LABELS:
                continue
            alternatives.append(code)
            alternative_sources.append(candidate)
            if len(alternatives) == DIALECT_CHOICE_COUNT - 1:
                break
        if len(alternatives) != DIALECT_CHOICE_COUNT - 1:
            continue
        choices = [DIALECT_LABELS[correct_code],
                   *(DIALECT_LABELS[code] for code in alternatives)]
        item = entry_item(
            "dialect_identification",
            TYPE_SPECS["dialect_identification"]["prefix"],
            len(items) + 1, target["lemma"], choices, 0, target, coordinates,
            ranks, totals, "lemma", "dialect",
            source={"dialect": correct_code},
            expected_choices=DIALECT_CHOICE_COUNT)
        item["source"]["choice_sources"] = [
            {"entry_id": candidate["id"],
             "shard": coordinates[candidate["id"]]["shard"],
             "offset": coordinates[candidate["id"]]["offset"],
             "dialect": (candidate.get("dialects") or [""])[0]}
            for candidate in alternative_sources
        ]
        items.append(item)
    if len(items) < 10:
        raise fail(f"dialect_identification {band}: only {len(items)} items; need at least 10")
    return items


def verse_items(
    entries: list[dict],
    coordinates: dict[str, dict],
    ranks: dict[str, int],
    totals: dict[str, int],
) -> list[dict]:
    texts, _ = read_corpus()
    rows_by_norm = norm_to_entry(entries)
    selected: list[dict] = []
    for slug in sorted(texts):
        verses = [verse for verse in texts[slug]["text.json"]["verses"]
                  if clean_display(verse.get("coptic", "")) and clean_display(verse.get("en", ""))]
        if not verses:
            raise fail(f"{slug}: no translated verses")
        step = max(1, len(verses) // VERSE_TARGETS_PER_WORK)
        candidates = verses[::step][:VERSE_TARGETS_PER_WORK]
        if len(candidates) < VERSE_TARGETS_PER_WORK:
            # Small works keep every verse rather than repeating one.
            candidates = (candidates + verses)[:VERSE_TARGETS_PER_WORK]
        for verse in candidates:
            selected.append({"slug": slug, "verse": verse})
    seen_translations: set[str] = set()
    anchored: list[dict] = []
    for candidate in selected:
        verse = candidate["verse"]
        key = choice_key(verse["en"])
        if key in seen_translations:
            continue
        anchor = None
        for index, token in enumerate(texts[candidate["slug"]]["tokens.json"]["tokens"]):
            if token.get("verse_index") != verse.get("verse_index"):
                continue
            norm = token.get("norm", "")
            entry = rows_by_norm.get(norm)
            if entry is not None and entry["id"] in ranks:
                anchor = {"token": token, "token_index": index, "entry": entry}
                break
        if anchor is None:
            continue
        seen_translations.add(key)
        anchored.append({**candidate, **anchor})
    if len(anchored) < 10:
        raise fail(f"verse_matching: only {len(anchored)} anchored verses; need at least 10")
    by_work: dict[str, list[dict]] = {}
    for candidate in anchored:
        by_work.setdefault(candidate["slug"], []).append(candidate)
    items: list[dict] = []
    sequence = 1
    for slug in sorted(by_work):
        verses = sorted(by_work[slug], key=lambda candidate: candidate["verse"]["verse_index"])
        for position, candidate in enumerate(verses):
            if len([item for item in items if item["source"]["work_slug"] == slug]) >= VERSE_TARGETS_PER_WORK:
                continue
            others = [other for other in verses if other is not candidate]
            others.sort(key=lambda other: -abs(other["verse"]["verse_index"]
                                                - candidate["verse"]["verse_index"]))
            chosen_others = others[:CHOICE_COUNT - 1]
            distractors = [other["verse"]["en"] for other in chosen_others]
            if len(distractors) != CHOICE_COUNT - 1:
                continue
            entry = candidate["entry"]
            token = candidate["token"]
            item = entry_item(
                "verse_matching", TYPE_SPECS["verse_matching"]["prefix"], sequence,
                clean_display(candidate["verse"]["coptic"]),
                [clean_display(candidate["verse"]["en"]), *[clean_display(d) for d in distractors]],
                0, entry, coordinates, ranks, totals, "coptic_verse", "translation",
                source={
                    "work_slug": slug,
                    "verse_index": candidate["verse"]["verse_index"],
                    "ref": candidate["verse"].get("ref", ""),
                    "urn": candidate["verse"].get("urn", ""),
                    "token_index": candidate["token_index"],
                    "anchor_lemma": token.get("lemma", ""),
                })
            item["source"]["choice_sources"] = [{
                "work_slug": slug,
                "verse_index": other["verse"]["verse_index"],
                "ref": other["verse"].get("ref", ""),
                "urn": other["verse"].get("urn", ""),
            } for other in chosen_others]
            items.append(item)
            sequence += 1
    if len(items) < 10:
        raise fail(f"verse_matching: only {len(items)} items; need at least 10")
    return items


def write_bank(filename: str, items: list[dict]) -> tuple[int, int]:
    QUIZ_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(items, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    dest = QUIZ_DIR / filename
    safeio.write_verified(dest, gzip.compress(payload, compresslevel=9, mtime=0))
    return len(payload), dest.stat().st_size


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="emit traceable static quiz banks")
    ap.parse_args(argv)
    entries, coordinates = read_entries()
    ranks, totals = frequency_ranks(entries)
    counts: dict[str, int] = {}
    sizes: dict[str, tuple[int, int]] = {}

    for quiz_type in [
        "coptic_to_english",
        "english_to_coptic",
        "transliteration_to_coptic",
        "lemma_identification",
        "pos_identification",
        "dialect_identification",
    ]:
        # One ID sequence per quiz type, continued across bands. Per-bank counters
        # would repeat q-c2e-00001 in all three bands; quiz progress is keyed by
        # item id, so those would be three different questions sharing one identity.
        sequence = 1
        prefix = TYPE_SPECS[quiz_type]["prefix"]
        for band in BANDS:
            if quiz_type == "coptic_to_english":
                items = coptic_to_english_items(entries, coordinates, ranks, totals, band)
            elif quiz_type == "english_to_coptic":
                items = english_to_coptic_items(entries, coordinates, ranks, totals, band)
            elif quiz_type == "transliteration_to_coptic":
                items = transliteration_items(entries, coordinates, ranks, totals, band)
            elif quiz_type == "lemma_identification":
                items = lemma_identification_items(entries, coordinates, ranks, totals, band)
            elif quiz_type == "pos_identification":
                items = pos_identification_items(entries, coordinates, ranks, totals, band)
            else:
                items = dialect_identification_items(entries, coordinates, ranks, totals, band)
            for item in items:
                item["id"] = f"q-{prefix}-{sequence:05d}"
                sequence += 1
            filename = f"{quiz_type}-{band}.json.gz"
            sizes[filename] = write_bank(filename, items)
            counts[filename] = len(items)
    items = verse_items(entries, coordinates, ranks, totals)
    sizes["verse_matching.json.gz"] = write_bank("verse_matching.json.gz", items)
    counts["verse_matching.json.gz"] = len(items)

    digest = hashlib.sha256()
    for filename in sorted(sizes):
        digest.update((QUIZ_DIR / filename).read_bytes())
    print(f"[quizgen] {sum(counts.values()):,} items in {len(counts)} bank(s); "
          f"quiz sha {digest.hexdigest()[:16]}…")
    for filename in sorted(counts):
        raw, gz = sizes[filename]
        print(f"  {filename:42} {counts[filename]:>4} items  {raw:>9,} B raw  {gz:>8,} B gz")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
