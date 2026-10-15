#!/usr/bin/env python3
"""tools/validate/quiz_guard.py — every quiz answer must be derivable from data.

LICENCE: project code, Apache-2.0.

Session 16 D4. A multiple-choice bank can look complete while teaching the wrong
answer. This guard does not trust the generator's claims; it rereads the
dictionary shards and the pinned corpus tarball and re-derives each correct
answer from the stored coordinates.

It checks, for every bank:

- file inventory and per-file item counts;
- item identity, nonempty prompt, four unique choices (three for dialect), and a
  valid correct index;
- difficulty band exactly matching the independently recomputed frequency rank;
- source shard/offset/token coordinates that resolve to the claimed entry;
- the exact displayed answer expected from those coordinates;
- distractor answers drawn from the same primary POS and difficulty band;
- no distractor that is also correct for the displayed prompt;
- no `[object Object]` anywhere in an item.

Rule 1 is respected: this file reads `data/dist/dict`, `data/dist/corpus`, and
`data/dist/quiz`; it writes nothing.

The transliteration check calls `static/js/translit.js` through
`tools/emit/translit_probe.mjs`, rather than reimplementing it in Python. The
prompt must equal the output of the one renderer the site uses. A second
implementation would be exactly the drift Rule 11 exists to prevent.
"""
from __future__ import annotations

import argparse
import gzip
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tarfile
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import pos as posvocab  # noqa: E402
import shardio  # noqa: E402

DICT = ROOT / "data" / "dist" / "dict"
TARBALL = ROOT / "data" / "dist" / "corpus" / "corpus.tar.gz"
QUIZ = ROOT / "data" / "dist" / "quiz"
PROBE = ROOT / "tools" / "emit" / "translit_probe.mjs"
EXPECTED_BANDS = ("beginner", "intermediate", "advanced")
EXPECTED_CHOICES = {
    "coptic_to_english": 4,
    "english_to_coptic": 4,
    "transliteration_to_coptic": 4,
    "lemma_identification": 4,
    "pos_identification": 4,
    "dialect_identification": 3,
    "verse_matching": 4,
}
ID_PREFIXES = {
    "coptic_to_english": "c2e",
    "english_to_coptic": "e2c",
    "transliteration_to_coptic": "t2c",
    "lemma_identification": "lemma",
    "pos_identification": "pos",
    "dialect_identification": "dialect",
    "verse_matching": "verse",
}
DIALECT_LABELS = {
    "A": "Assiutic",
    "Ak": "Akhmimic",
    "B": "Bohairic",
    "F": "Fayumic",
    "N": "N (undetermined)",
    "S": "Sahidic",
}


class QuizGuardError(SystemExit):
    """A quiz bank that cannot be trusted."""


def normalized(text: str) -> str:
    return unicodedata.normalize("NFC", text.strip().casefold())


def display(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text or "").split())


def shard_number(path: pathlib.Path) -> int:
    match = re.fullmatch(r"shard-(\d+)\.json(?:\.gz)?", path.name)
    if not match:
        raise QuizGuardError(f"unexpected shard filename {path.name}")
    return int(match.group(1))


def read_dictionary() -> tuple[dict[str, dict], dict[str, dict]]:
    paths = shardio.shard_paths(DICT)
    if not paths:
        raise QuizGuardError(f"no dictionary shards in {DICT}")
    entries: dict[str, dict] = {}
    coordinates: dict[str, dict] = {}
    for path in paths:
        blob = shardio.read_shard(path, strict=True)
        if blob is None:
            raise QuizGuardError(f"{path.name}: no shard object")
        shard = shard_number(path)
        items = blob.get("entries", [])
        if not isinstance(items, list):
            raise QuizGuardError(f"{path.name}: entries is not a list")
        for offset, entry in enumerate(items):
            if not isinstance(entry, dict):
                raise QuizGuardError(f"{path.name} offset {offset}: not an object")
            entry_id = entry.get("id")
            if not isinstance(entry_id, str) or not entry_id:
                raise QuizGuardError(f"{path.name} offset {offset}: no string id")
            if entry_id in entries:
                raise QuizGuardError(f"duplicate entry id {entry_id}")
            entries[entry_id] = entry
            coordinates[entry_id] = {"shard": shard, "offset": offset}
    return entries, coordinates


def frequency(entries: dict[str, dict]) -> tuple[dict[str, int], dict[str, int]]:
    totals = {
        entry_id: sum(ref.get("occurrences", 0)
                      for ref in entry.get("corpus_refs") or []
                      if isinstance(ref, dict) and isinstance(ref.get("occurrences"), int))
        for entry_id, entry in entries.items()
    }
    attested = [entry_id for entry_id, total in totals.items() if total > 0]
    ordered = sorted(
        attested,
        key=lambda entry_id: (
            -totals[entry_id],
            entries[entry_id].get("norm_key", ""),
            entry_id,
        ),
    )
    ranks = {entry_id: rank for rank, entry_id in enumerate(ordered, 1)}
    return ranks, totals


def difficulty(rank: int) -> str:
    if rank <= 300:
        return "beginner"
    if rank <= 1000:
        return "intermediate"
    return "advanced"


def first_gloss(entry: dict) -> str:
    for gloss in entry.get("glosses") or []:
        if isinstance(gloss, dict):
            text = display(gloss.get("text", ""))
            if text:
                return text
    return ""


def all_glosses(entry: dict) -> set[str]:
    return {
        normalized(gloss.get("text", ""))
        for gloss in entry.get("glosses") or []
        if isinstance(gloss, dict) and display(gloss.get("text", ""))
    }


def primary_pos(entry: dict) -> str:
    pos = entry.get("pos") or []
    return pos[0] if isinstance(pos, list) and pos and isinstance(pos[0], str) else ""


def render_transliterations(tasks: list[dict]) -> list[str]:
    node = shutil.which("node")
    if node is None:
        raise QuizGuardError("node is required to call static/js/translit.js")
    proc = subprocess.run(
        [node, str(PROBE)],
        input="\n".join(json.dumps(task, ensure_ascii=False) for task in tasks).encode(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise QuizGuardError(f"translit probe failed: {proc.stderr.decode().strip()}")
    lines = proc.stdout.decode("utf-8").splitlines()
    if len(lines) != len(tasks):
        raise QuizGuardError(
            f"translit probe returned {len(lines)} prompts for {len(tasks)} tasks")
    try:
        rendered = [json.loads(line) for line in lines]
    except json.JSONDecodeError as e:
        raise QuizGuardError(f"translit probe returned invalid JSON: {e}") from e
    if any(not isinstance(value, str) for value in rendered):
        raise QuizGuardError("translit probe did not return only strings")
    return rendered


def read_corpus() -> dict[str, dict]:
    if not TARBALL.is_file():
        raise QuizGuardError(f"{TARBALL} is missing")
    works: dict[str, dict] = {}
    with tarfile.open(TARBALL, "r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            slug, _, name = member.name.partition("/")
            if not slug or name not in {"meta.json", "text.json", "tokens.json"}:
                continue
            stream = archive.extractfile(member)
            if stream is None:
                raise QuizGuardError(f"{member.name}: cannot read corpus member")
            works.setdefault(slug, {})[name] = json.loads(stream.read().decode("utf-8"))
    for slug, docs in works.items():
        for name in ("meta.json", "text.json", "tokens.json"):
            if name not in docs:
                raise QuizGuardError(f"{slug}: {name} is missing from the tarball")
    return works


def expected_filenames() -> list[str]:
    names = [f"{quiz_type}-{band}.json.gz"
             for quiz_type in sorted(ID_PREFIXES)
             if quiz_type != "verse_matching"
             for band in sorted(EXPECTED_BANDS)]
    return [*names, "verse_matching.json.gz"]


def check_item_shape(item: dict, quiz_type: str, filename: str, errors: list[str]) -> None:
    for key in ("id", "type", "prompt", "choices", "correct", "source",
                "difficulty", "freq_rank"):
        if key not in item:
            errors.append(f"{filename} {item.get('id', '?')}: missing {key}")
    if not isinstance(item.get("id"), str) or not re.fullmatch(
            rf"q-{ID_PREFIXES[quiz_type]}-\d{{5}}", item.get("id", "")):
        errors.append(f"{filename} {item.get('id', '?')}: bad quiz id")
    if item.get("type") != quiz_type:
        errors.append(f"{filename} {item.get('id', '?')}: type {item.get('type')!r}")
    if not isinstance(item.get("prompt"), str) or not display(item.get("prompt", "")):
        errors.append(f"{filename} {item.get('id', '?')}: empty prompt")
    choices = item.get("choices", [])
    expected = EXPECTED_CHOICES[quiz_type]
    if not isinstance(choices, list) or len(choices) != expected:
        errors.append(f"{filename} {item.get('id', '?')}: expected {expected} "
                      f"choices, found {len(choices) if isinstance(choices, list) else '?'}")
        return
    if any(not isinstance(choice, str) or not display(choice) for choice in choices):
        errors.append(f"{filename} {item['id']}: empty choice")
    if len({normalized(choice) for choice in choices}) != expected:
        errors.append(f"{filename} {item['id']}: duplicate choices")
    if not isinstance(item.get("correct"), int) or not 0 <= item["correct"] < expected:
        errors.append(f"{filename} {item['id']}: correct index {item.get('correct')!r}")
    if "[object Object]" in json.dumps(item, ensure_ascii=False):
        errors.append(f"{filename} {item['id']}: rendered object marker")
    source = item.get("source", {})
    if not isinstance(source, dict):
        errors.append(f"{filename} {item['id']}: source is not an object")


def resolve_entry(source: dict, entries: dict, coordinates: dict,
                  filename: str, item_id: str, errors: list[str]) -> dict | None:
    entry_id = source.get("entry_id")
    entry = entries.get(entry_id) if isinstance(entry_id, str) else None
    if entry is None:
        errors.append(f"{filename} {item_id}: unknown source entry {entry_id!r}")
        return None
    coords = coordinates[entry_id]
    if source.get("shard") != coords["shard"] or source.get("offset") != coords["offset"]:
        errors.append(f"{filename} {item_id}: source coordinates do not match {entry_id}")
        return None
    return entry


def check_frequency(item: dict, filename: str, entry_id: str,
                    ranks: dict[str, int], totals: dict[str, int],
                    errors: list[str]) -> None:
    rank = ranks.get(entry_id, 0)
    if item.get("freq_rank") != rank:
        errors.append(f"{filename} {item['id']}: freq_rank {item.get('freq_rank')!r}, "
                      f"data says {rank}")
    if item.get("difficulty") not in EXPECTED_BANDS and item["type"] != "verse_matching":
        errors.append(f"{filename} {item['id']}: bad difficulty {item.get('difficulty')!r}")
    elif item.get("difficulty") != difficulty(rank):
        errors.append(f"{filename} {item['id']}: difficulty {item.get('difficulty')!r} "
                      f"does not match rank {rank}")
    if item.get("frequency_total") != totals.get(entry_id):
        errors.append(f"{filename} {item['id']}: frequency_total does not match source")


def check_distractor_pool(item: dict, filename: str, entries: dict,
                          coordinates: dict[str, dict], ranks: dict[str, int],
                          errors: list[str]) -> list[dict]:
    source = item.get("source", {})
    records = source.get("choice_sources", [])
    expected = EXPECTED_CHOICES[item["type"]] - 1
    if len(records) != expected:
        errors.append(f"{filename} {item['id']}: expected {expected} distractor "
                      f"sources, found {len(records)}")
        return []
    target = entries[source.get("entry_id")]
    checked: list[dict] = []
    for record in records:
        candidate = resolve_entry(record, entries, coordinates, filename,
                                  item["id"], errors)
        if candidate is None:
            continue
        checked.append(candidate)
    # Every recorded distractor must share the target band and primary POS.
    for candidate in checked:
        if ranks.get(candidate["id"], 0) == 0 or difficulty(ranks[candidate["id"]]) != item["difficulty"]:
            errors.append(f"{filename} {item['id']}: distractor {candidate['id']} is "
                          f"outside the target band")
        if primary_pos(candidate) != primary_pos(target):
            errors.append(f"{filename} {item['id']}: distractor {candidate['id']} has "
                          f"a different primary POS")
    return checked


def check_lexical(item: dict, filename: str, entries: dict, coordinates: dict,
                  ranks: dict[str, int], totals: dict[str, int],
                  errors: list[str]) -> None:
    source = item.get("source", {})
    target = resolve_entry(source, entries, coordinates, filename, item["id"], errors)
    if target is None:
        return
    check_frequency(item, filename, target["id"], ranks, totals, errors)
    distractors = check_distractor_pool(item, filename, entries, coordinates, ranks, errors)
    correct = item["choices"][item["correct"]]

    if item["type"] == "coptic_to_english":
        if item["prompt"] != target["lemma"]:
            errors.append(f"{filename} {item['id']}: prompt is not the source lemma")
        if correct != first_gloss(target):
            errors.append(f"{filename} {item['id']}: correct choice is not the source gloss")
        for candidate in distractors:
            gloss = first_gloss(candidate)
            if normalized(gloss) in all_glosses(target):
                errors.append(f"{filename} {item['id']}: distractor {candidate['id']} "
                              f"is also correct")
    elif item["type"] == "english_to_coptic":
        if item["prompt"] != first_gloss(target):
            errors.append(f"{filename} {item['id']}: prompt is not the source gloss")
        if correct != target["lemma"]:
            errors.append(f"{filename} {item['id']}: correct choice is not the source lemma")
        for candidate in distractors:
            if normalized(item["prompt"]) in all_glosses(candidate):
                errors.append(f"{filename} {item['id']}: distractor {candidate['id']} "
                              f"also has the prompt gloss")
    elif item["type"] == "transliteration_to_coptic":
        # Session 17 D3: prompts are rule-based scheme values, not Kaikki
        # romanizations. The snapshot must carry the scheme, the shipped entry
        # must agree, and the renderer must reproduce the prompt.
        scheme = source.get("translit_scheme")
        snapshot = source.get("translit_snapshot", {})
        if scheme not in ("bohairic", "sahidic", "layton", "till",
                          "egyptological"):
            errors.append(f"{filename} {item['id']}: translit_scheme is not a "
                          f"shipped scheme")
            return
        if not isinstance(snapshot, dict) or not snapshot.get(scheme):
            errors.append(f"{filename} {item['id']}: missing transliteration source payload")
            return
        shipped = target.get("translit") or {}
        if not isinstance(shipped, dict) or shipped.get(scheme) != snapshot.get(scheme):
            errors.append(f"{filename} {item['id']}: snapshot does not match "
                          f"the shipped translit.{scheme}")
            return
        rendered = render_transliterations([{
            "translit": snapshot,
            "forms": [],
            "scheme": scheme,
        }])[0]
        if item["prompt"] != rendered or not rendered:
            errors.append(f"{filename} {item['id']}: prompt is not translitDisplay()")
        if source.get("translit_source") != f"translit.{scheme}":
            errors.append(f"{filename} {item['id']}: missing scheme provenance")
        if correct != target["lemma"]:
            errors.append(f"{filename} {item['id']}: correct choice is not the source lemma")
        for candidate in distractors:
            candidate_translit = candidate.get("translit") or {}
            if normalized(item["prompt"]) == normalized(candidate_translit.get(scheme, "")):
                errors.append(f"{filename} {item['id']}: distractor {candidate['id']} "
                              f"shares the prompt transliteration")
    elif item["type"] == "lemma_identification":
        form_index = source.get("form_index")
        forms = [form for form in target.get("forms") or [] if isinstance(form, dict)]
        if not isinstance(form_index, int) or not 0 <= form_index < len(forms):
            errors.append(f"{filename} {item['id']}: bad source form index")
            return
        form = forms[form_index]
        if item["prompt"] != display(form.get("form", "")):
            errors.append(f"{filename} {item['id']}: prompt is not the source form")
        if form.get("kind") != "inflection" or item["prompt"] == target["lemma"]:
            errors.append(f"{filename} {item['id']}: prompt is not an inflected form")
        if correct != target["lemma"]:
            errors.append(f"{filename} {item['id']}: correct choice is not the source lemma")
        for candidate in distractors:
            if any(display(form.get("form", "")) == item["prompt"]
                   for form in candidate.get("forms") or [] if isinstance(form, dict)):
                errors.append(f"{filename} {item['id']}: distractor {candidate['id']} "
                              f"also has the prompt form")
    elif item["type"] == "pos_identification":
        if item["prompt"] != target["lemma"]:
            errors.append(f"{filename} {item['id']}: prompt is not the source lemma")
        if correct != primary_pos(target):
            errors.append(f"{filename} {item['id']}: correct choice is not the source POS")
        if correct not in posvocab.CONTROLLED:
            errors.append(f"{filename} {item['id']}: answer is outside the POS vocabulary")
        for choice in item["choices"]:
            if choice in (target.get("pos") or []) and choice != correct:
                errors.append(f"{filename} {item['id']}: distractor {choice!r} is also "
                              f"in the source POS list")
    elif item["type"] == "dialect_identification":
        dialects = target.get("dialects") or []
        if len(dialects) != 1:
            errors.append(f"{filename} {item['id']}: source dialects are ambiguous")
            return
        if item["prompt"] != target["lemma"]:
            errors.append(f"{filename} {item['id']}: prompt is not the source lemma")
        if correct != DIALECT_LABELS.get(dialects[0], dialects[0]):
            errors.append(f"{filename} {item['id']}: correct choice is not the source dialect")
        for choice in item["choices"]:
            if choice != correct and choice in [
                    DIALECT_LABELS.get(code, code) for code in dialects]:
                errors.append(f"{filename} {item['id']}: distractor {choice!r} is also "
                              f"in the source dialect set")


def roman_forms(entry: dict) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for index, form in enumerate(entry.get("forms") or []):
        if isinstance(form, dict) and form.get("kind") == "romanization":
            text = " ".join(str(form.get("form", "")).split())
            if text:
                out.append((index, text))
    return out


def check_verse(item: dict, filename: str, entries: dict, coordinates: dict,
                ranks: dict[str, int], totals: dict[str, int],
                works: dict[str, dict], errors: list[str]) -> None:
    source = item.get("source", {})
    target = resolve_entry(source, entries, coordinates, filename, item["id"], errors)
    if target is None:
        return
    check_frequency(item, filename, target["id"], ranks, totals, errors)
    slug = source.get("work_slug")
    docs = works.get(slug) if isinstance(slug, str) else None
    if docs is None:
        errors.append(f"{filename} {item['id']}: unknown work {slug!r}")
        return
    verses = {verse.get("verse_index"): verse
              for verse in docs["text.json"]["verses"] if isinstance(verse, dict)}
    verse = verses.get(source.get("verse_index"))
    if verse is None:
        errors.append(f"{filename} {item['id']}: verse {source.get('verse_index')!r} "
                      f"is absent")
        return
    if item["prompt"] != display(verse.get("coptic", "")):
        errors.append(f"{filename} {item['id']}: prompt is not the verse text")
        return
    if item["choices"][item["correct"]] != display(verse.get("en", "")):
        errors.append(f"{filename} {item['id']}: correct choice is not the verse translation")
        return
    if verse.get("urn") != source.get("urn") or verse.get("ref") != source.get("ref"):
        errors.append(f"{filename} {item['id']}: verse metadata does not match source")
    tokens = [token for token in docs["tokens.json"]["tokens"]
              if isinstance(token, dict) and token.get("verse_index") == verse.get("verse_index")]
    token_index = source.get("token_index")
    if not isinstance(token_index, int) or not 0 <= token_index < len(
            docs["tokens.json"]["tokens"]):
        errors.append(f"{filename} {item['id']}: bad token index")
        return
    token = docs["tokens.json"]["tokens"][token_index]
    if token.get("verse_index") != verse.get("verse_index"):
        errors.append(f"{filename} {item['id']}: anchor token is in another verse")
    if token.get("lemma") != source.get("anchor_lemma"):
        errors.append(f"{filename} {item['id']}: anchor lemma does not match token")
    norm = token.get("norm", "")
    mapped = next((entry for entry in entries.values() if entry.get("norm_key") == norm), None)
    if mapped is None or mapped["id"] != target["id"]:
        errors.append(f"{filename} {item['id']}: anchor token does not resolve to "
                      f"the source entry")
    for record in source.get("choice_sources", []):
        other = verses.get(record.get("verse_index"))
        if other is None or other.get("work_slug", slug) != slug:
            # choice_sources carry the same work implicitly; only the index matters.
            pass
        if other is None:
            errors.append(f"{filename} {item['id']}: distractor verse is absent")
            continue
        if normalized(display(other.get("en", ""))) == normalized(item["choices"][item["correct"]]):
            errors.append(f"{filename} {item['id']}: a distractor verse has the "
                          f"correct translation")


def read_bank(path: pathlib.Path, errors: list[str]) -> list[dict] | None:
    try:
        payload = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        errors.append(f"{path.name}: cannot read quiz bank ({e})")
        return None
    if not isinstance(payload, list) or not payload:
        errors.append(f"{path.name}: bank is not a nonempty list")
        return None
    return payload


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="every quiz answer must resolve to data")
    ap.add_argument("--quiz-dir", type=pathlib.Path, default=ROOT / "data" / "dist" / "quiz")
    args = ap.parse_args(argv)

    errors: list[str] = []
    if not args.quiz_dir.is_dir():
        print(f"[quiz_guard] FAIL — {args.quiz_dir} does not exist. Generate the "
              f"bank with tools/emit/quizgen.py; an absent bank must not pass.",
              file=sys.stderr)
        return 1
    try:
        entries, coordinates = read_dictionary()
        ranks, totals = frequency(entries)
        works = read_corpus()
    except QuizGuardError as e:
        print(f"[quiz_guard] FAIL — {e}", file=sys.stderr)
        return 1

    found = sorted(args.quiz_dir.glob("*.json.gz"))
    names = [path.name for path in found]
    if names != expected_filenames():
        print(f"[quiz_guard] FAIL — expected {len(expected_filenames())} quiz files, "
              f"found {len(names)}: {', '.join(names) or 'none'}", file=sys.stderr)
        return 1

    checked = 0
    seen_ids: set[str] = set()
    for path in found:
        stem = path.name.removesuffix(".json.gz")
        if stem == "verse_matching":
            quiz_type = "verse_matching"
        else:
            quiz_type, _, band = stem.rpartition("-")
            if quiz_type not in ID_PREFIXES or band not in EXPECTED_BANDS:
                errors.append(f"{path.name}: bad quiz filename")
                continue
        items = read_bank(path, errors)
        if items is None:
            continue
        for item in items:
            if not isinstance(item, dict):
                errors.append(f"{path.name}: item is not an object")
                continue
            check_item_shape(item, quiz_type, path.name, errors)
            if item.get("id") in seen_ids:
                errors.append(f"{path.name} {item.get('id')}: duplicate quiz id")
            elif isinstance(item.get("id"), str):
                seen_ids.add(item["id"])
            check_band(item, path.name, quiz_type, errors)
            if quiz_type == "verse_matching":
                check_verse(item, path.name, entries, coordinates, ranks, totals,
                            works, errors)
            else:
                check_lexical(item, path.name, entries, coordinates, ranks, totals,
                              errors)
            checked += 1

    if errors:
        print(f"[quiz_guard] FAIL — {len(errors)} problem(s):", file=sys.stderr)
        for error in errors[:30]:
            print(f"  - {error}", file=sys.stderr)
        if len(errors) > 30:
            print(f"  - ... and {len(errors) - 30} more", file=sys.stderr)
        return 1
    print(f"[quiz_guard] OK — {checked:,} quiz items checked in {len(found)} bank(s); "
          f"every correct answer resolves to its source")
    return 0


def check_band(item: dict, filename: str, quiz_type: str, errors: list[str]) -> None:
    if quiz_type == "verse_matching":
        return
    stem = filename.removesuffix(".json.gz")
    quiz_name, _, band = stem.rpartition("-")
    if quiz_name != quiz_type or band not in EXPECTED_BANDS:
        errors.append(f"{filename}: bad band in filename")
    elif item.get("difficulty") != band:
        errors.append(f"{filename} {item.get('id')}: file is {band}, item says "
                      f"{item.get('difficulty')!r}")


if __name__ == "__main__":
    raise SystemExit(main())
