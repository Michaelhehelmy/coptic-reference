# Fonts — none bundled yet

**Intended path:** `themes/copticref/static/fonts/Coptic.woff2`

**It does not exist, and this file does not pretend otherwise.** v4 §1.2 plans a
subset webfont covering the 22 letters of `tools/collate.py`, OFL-licensed,
built from Noto Sans Coptic. Until it is built, `css/styles.css` uses a system
font stack:

    "Coptic", "Segoe UI Historic", "Noto Sans Coptic",
    "New Athena Unicode", "Arial Unicode MS", serif

That covers the Coptic block (U+2C80–U+2CFF) on Windows, macOS, most Linux desktops
and Android. On a bare Linux box it may fall back to a font without Coptic and the
reader sees boxes; `CONTRIBUTING.md` says to install `fonts-noto-core` or GNU
FreeFont rather than converting text to images.

Two constraints for whoever builds it:

- **Subset to the 22 letters** in `tools/collate.py`, not the whole block. A Coptic
  block subset is small; the full Unicode Coptic block is not.
- **Keep it OFL.** The site's data is CC BY-SA and its code Apache-2.0; a
  bundled font with a copyleft or restricted licence would change what we can
  redistribute, so `licence_guard.py` and `COVERAGE.md` both treat "font file
  present" as a licence question, not a styling one.
