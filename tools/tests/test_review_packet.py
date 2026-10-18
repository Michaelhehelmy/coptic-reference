# tools/tests/test_review_packet.py — the expert review packet is a mirror.
#
# Session 23 D3. content/EXPERT_REVIEW_PACKET.md exists so a reviewer can
# read every open verdict item in one place. Its authority lives in
# content/GRAMMAR_CLAIMS.md and content/POS_LABELS_REVIEW.md; the packet
# must mirror those tables exactly — same pipe-lines, same order, verdict
# cells still blank — or the "source of truth" sentence on the packet page
# is a lie. This test fails the build when the mirror drifts.
#
# LICENCE: project code, Apache-2.0.
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
PACKET = ROOT / "content" / "EXPERT_REVIEW_PACKET.md"
REGISTERS = (
    ROOT / "content" / "GRAMMAR_CLAIMS.md",
    ROOT / "content" / "POS_LABELS_REVIEW.md",
)


def _pipe_lines(text: str) -> list[str]:
    return [ln for ln in text.splitlines() if ln.startswith("|")]


def test_packet_exists_with_both_registers():
    assert PACKET.is_file(), "content/EXPERT_REVIEW_PACKET.md missing"
    for r in REGISTERS:
        assert r.is_file(), f"{r.name} missing — packet has nothing to mirror"


def test_packet_mirrors_every_register_line_in_order():
    packet_lines = _pipe_lines(PACKET.read_text(encoding="utf-8"))
    expected: list[str] = []
    for r in REGISTERS:
        expected.extend(_pipe_lines(r.read_text(encoding="utf-8")))
    assert len(expected) >= 30, (
        f"registers carry only {len(expected)} table lines — registers shrank?")
    assert packet_lines == expected, (
        "packet tables drifted from the registers — edit the registers "
        "first, then re-mirror, or regenerate the packet section")


def test_no_verdict_cell_has_been_filled_in_the_packet():
    # A filled row is the sign a reviewer answered here instead of in the
    # registers — the registers are where verdicts belong.
    for ln in _pipe_lines(PACKET.read_text(encoding="utf-8")):
        if ln.startswith("|---") or "Verdict (blank until reviewed)" in ln:
            continue
        # every mirrored data row ends with an empty final cell
        assert re.search(r"\|\s*\|?\s*$", ln) and ln.rstrip().endswith("| |"), (
            f"verdict cell looks filled in the packet: {ln[:80]}…")
