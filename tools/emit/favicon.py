#!/usr/bin/env python3
"""tools/emit/favicon.py — draw the site favicon as a Coptic cross.

LICENCE: project code, Apache-2.0.

Session 22 D3 / C5. Every page on the site was losing 4 Lighthouse
best-practices points for shipping no favicon. This generator writes
static/favicon.ico (16x16 and 32x32, PNG-compressed ICO entries) from
stdlib only — no Pillow, no font dependency, no network.

WHY A GEOMETRIC CROSS, NOT THE LETTER ⲁ. The project font is deliberately
not vendored (themes/copticref/static/fonts/README.md), and no system face
is guaranteed on a build machine. Rendering ⲁ would mean either shipping a
font we do not have or trusting one we do not control. A Coptic cross is
pure geometry: equal arms, flared tips, a center diamond — it reads at
16 px, needs no font, and is the mark the tradition itself uses.

Deterministic: same code, same bytes. Re-run only when the design changes;
the .ico is committed, this script exists so the committed file can be
regenerated and diffed, not so the build depends on it.
"""
from __future__ import annotations

import pathlib
import struct
import sys
import zlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEST = ROOT / "static" / "favicon.ico"
INK: tuple[int, int, int, int] = (26, 77, 143, 255)  # --link #1a4d8f
CLEAR: tuple[int, int, int, int] = (0, 0, 0, 0)


def _draw_cross(size: int) -> bytes:
    """RGBA rows for one square icon: equal-armed cross, flared tips,
    center diamond. Geometry only — no font, no rasteriser."""
    px: list[list[tuple[int, int, int, int]]] = (
        [[CLEAR] * size for _ in range(size)])
    c = size // 2
    arm_w = max(2, size // 5)          # stroke thickness
    half = arm_w // 2
    reach = size // 2 - max(1, size // 12)   # arm tip, inside the border
    flare = max(1, size // 16)         # tip thickening

    def fill(x0: int, y0: int, x1: int, y1: int) -> None:
        for y in range(max(0, y0), min(size, y1)):
            row = px[y]
            for x in range(max(0, x0), min(size, x1)):
                row[x] = INK

    # Vertical arm + horizontal arm.
    fill(c - half, c - reach, c - half + arm_w, c + reach)
    fill(c - reach, c - half, c + reach, c - half + arm_w)
    # Flared tips: a short perpendicular bar at each arm end.
    tip = arm_w + 2 * flare
    t0 = c - tip // 2
    fill(t0, c - reach, t0 + tip, c - reach + flare)
    fill(t0, c + reach - flare, t0 + tip, c + reach)
    fill(c - reach, t0, c - reach + flare, t0 + tip)
    fill(c + reach - flare, t0, c + reach, t0 + tip)
    # Center diamond (rotated square), radius ~arm_w/2: the Coptic cross
    # tradition marks the crossing; at 16 px this is one brighter pixel
    # cluster, at 32 px it reads as a lozenge.
    r = max(1, arm_w // 2 + 1)
    for y in range(c - r, c + r + 1):
        for x in range(c - r, c + r + 1):
            if abs(x - c) + abs(y - c) <= r:
                px[y][x] = INK

    rows = bytearray()
    for row in px:
        rows.append(0)  # filter type None
        for r_, g_, b_, a_ in row:
            rows.extend((r_, g_, b_, a_))
    return bytes(rows)


def _png(size: int) -> bytes:
    raw = _draw_cross(size)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)  # 8-bit RGBA
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def _ico(images: list[tuple[int, bytes]]) -> bytes:
    """ICONDIR + ICONDIRENTRY per image + PNG payloads (PNG-in-ICO)."""
    out = bytearray(struct.pack("<HHH", 0, 1, len(images)))
    offset = 6 + 16 * len(images)
    payloads: list[bytes] = []
    for size, png in images:
        dim = 0 if size >= 256 else size
        out += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32,
                           len(png), offset)
        payloads.append(png)
        offset += len(png)
    for p in payloads:
        out += p
    return bytes(out)


def main() -> int:
    ico = _ico([(16, _png(16)), (32, _png(32))])
    DEST.parent.mkdir(parents=True, exist_ok=True)
    tmp = DEST.with_suffix(".ico.tmp")
    tmp.write_bytes(ico)
    tmp.replace(DEST)
    # Rule 3: read back what we wrote.
    if DEST.read_bytes() != ico:
        print(f"[favicon] FAIL — read-back mismatch for {DEST}", file=sys.stderr)
        return 1
    print(f"[favicon] wrote {DEST.relative_to(ROOT)} "
          f"({len(ico)} B, 16x16 + 32x32, Coptic cross in #1a4d8f)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
