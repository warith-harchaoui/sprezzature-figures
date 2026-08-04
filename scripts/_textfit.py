#!/usr/bin/env python3
"""
_textfit — dependency-free text measurement and orphan-aware wrapping.

Hand-authored SVG figures size their titles, subtitles, node boxes and axis
labels by hand, which means a longer string (French is routinely 15-30% longer
than the English it replaces) overflows a canvas laid out for English. This
helper makes that layout *adaptive to the actual string*, in any language:

- :func:`text_width` estimates the rendered width of a string at a given font
  size using a calibrated per-character advance table for the house Roboto
  stack (no PIL / fontTools dependency, so it is safe to import from any
  generator). Estimates run a touch wide, which is the safe direction for
  fitting.
- :func:`wrap_to_width` greedily wraps a string to a pixel budget and then
  enforces the house rule that a line may never end on a dangling function word
  ("of the" / "the" / "l'" ...), pulling such a word down to the next line.
- :func:`fit_font_size` shrinks a font size until a string fits one line.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""
from __future__ import annotations

# Per-character advance widths in em units, calibrated to Roboto. Only the
# classes that differ much from the mean are listed; everything else falls back
# to _DEFAULT_EM. Values are deliberately a hair generous so a fitted layout
# errs toward whitespace, never toward a clip.
_DEFAULT_EM = 0.52
_EM: dict[str, float] = {
    " ": 0.26, "i": 0.24, "j": 0.24, "l": 0.24, "I": 0.30, "t": 0.31, "f": 0.32,
    "r": 0.34, "'": 0.20, "’": 0.20, "!": 0.26, ".": 0.26, ",": 0.26, ":": 0.26,
    ";": 0.26, "|": 0.22, "(": 0.31, ")": 0.31, "[": 0.31, "]": 0.31, "-": 0.33,
    "m": 0.82, "M": 0.84, "w": 0.72, "W": 0.92, "%": 0.82, "@": 0.92,
    "0": 0.55, "1": 0.55, "2": 0.55, "3": 0.55, "4": 0.55, "5": 0.55,
    "6": 0.55, "7": 0.55, "8": 0.55, "9": 0.55,
}
# Function words that must not be stranded at the end of a wrapped line.
_ORPHANS_EN = {
    "of", "the", "a", "an", "to", "and", "or", "for", "in", "on", "is", "from",
    "with", "by", "at", "as", "into", "over", "than", "per", "vs",
}
_ORPHANS_FR = {"le", "la", "les", "de", "des", "du", "un", "une", "et", "ou", "à"}
_ORPHANS = _ORPHANS_EN | _ORPHANS_FR


def text_width(text: str, font_size: float, *, bold: bool = False) -> float:
    """Estimate the rendered width, in pixels, of ``text`` at ``font_size``.

    Bold Roboto is a little wider; ``bold`` scales the estimate by 3%.
    """
    ems = sum(_EM.get(ch, _DEFAULT_EM) for ch in text)
    return ems * font_size * (1.03 if bold else 1.0)


def fit_font_size(text: str, max_px: float, start: float, *, min_px: float = 9.0) -> float:
    """The largest size <= ``start`` at which ``text`` fits ``max_px`` on one
    line, floored at ``min_px``."""
    size = start
    while size > min_px and text_width(text, size) > max_px:
        size -= 0.5
    return max(size, min_px)


def _ends_on_orphan(line: str) -> bool:
    words = line.split()
    if not words:
        return False
    last = words[-1].strip(".,;:!?").lower()
    # A trailing elision ("l'", "d'") or a bare function word both count.
    return last in _ORPHANS or last.endswith("’") or last.endswith("'")


def wrap_to_width(text: str, max_px: float, font_size: float, *, bold: bool = False) -> list[str]:
    """Wrap ``text`` to lines no wider than ``max_px``, then push any dangling
    function word off the end of a line onto the next.

    Returns the list of lines. A single word wider than ``max_px`` is kept on
    its own line rather than split mid-word.
    """
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    cur = ""
    for w in words:
        trial = w if not cur else f"{cur} {w}"
        if text_width(trial, font_size, bold=bold) <= max_px or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)

    # Orphan pass: while a line ends on a function word, move that word down.
    changed = True
    while changed:
        changed = False
        for i in range(len(lines) - 1):
            if _ends_on_orphan(lines[i]):
                words_i = lines[i].split()
                moved = words_i.pop()
                lines[i] = " ".join(words_i)
                lines[i + 1] = f"{moved} {lines[i + 1]}"
                changed = True
        # The last line may also strand an orphan ("... share of the"); if so and
        # there is room to fold the previous word up would not help, so open a new
        # trailing line to carry the dangling word rather than leave it hanging.
        if lines and _ends_on_orphan(lines[-1]) and len(lines[-1].split()) > 1:
            words_last = lines[-1].split()
            moved = words_last.pop()
            lines[-1] = " ".join(words_last)
            lines.append(moved)
            changed = True
    return [ln for ln in lines if ln]


if __name__ == "__main__":  # tiny self-test
    assert text_width("", 20) == 0
    assert text_width("mmm", 20) > text_width("iii", 20)
    w = wrap_to_width("The ring is one full year; follow it clockwise from the top.", 180, 15)
    assert all(not _ends_on_orphan(ln) for ln in w), w
    fr = wrap_to_width("La longueur de chaque arc est sa part de l’année entière.", 180, 15)
    assert all(not ln.rstrip().endswith(("’", "'")) for ln in fr), fr
    assert fit_font_size("Very wide title here", 60, 30) < 30
    print("wrap EN:", w)
    print("wrap FR:", fr)
    print("_textfit self-test OK")
