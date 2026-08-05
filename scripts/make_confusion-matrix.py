#!/usr/bin/env python3
"""
make_confusion-matrix — a house-styled 3-class confusion matrix as a hand SVG.

A confusion matrix crosses the *actual* class (rows) against the *predicted*
class (columns): the diagonal is where the classifier is right, everything
off-diagonal is a specific mistake. This figure labels **both** axes — class
names down the left (Actual) and the same names across the top (Predicted) — so
a reader never has to guess which way a cell reads. Cells are shaded on a single
blue ramp (darkest = most examples, so the correct diagonal stands out) with the
count printed in each, a small gap between cells (a tile grid, gently rounded per
the Sprezzature Corner Policy), and generous breathing room around the grid.

The SVG is built by hand — no matplotlib / Vega — so it matches the other hero
figures and carries a native ``<title>`` per cell plus an accessible
``<title>``/``<desc>``.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _style import CORNERS  # noqa: E402
from _svg import rounded_rect_path, svg_open, xml_escape  # noqa: E402
from _render import render_cli  # noqa: E402
from _interactive import fullscreen_control  # noqa: E402

# --- data: a 3-class pet classifier (rows = actual, cols = predicted) ---------
CLASSES = ["Cat", "Dog", "Fox"]
MATRIX = [
    [52, 5, 3],   # actual Cat
    [6, 44, 4],   # actual Dog
    [2, 7, 39],   # actual Fox
]

# --- geometry + house-style constants -----------------------------------------
_WIDTH = 820
_HEIGHT = 640
_CELL = 150.0          # cell size
_GAP = 8.0             # gap between cells (a tile grid)
_GRID_X = 250.0        # left edge of the grid (room for row labels + axis)
_GRID_Y = 190.0        # top edge of the grid (room for title + column labels)

_INK = "#1D1D1F"
_SUBTLE = "#6E6E73"
_BG = "#FFFFFF"

# Blue sequential ramp endpoints (light -> dark), lerped by normalised count.
_LO = (234, 243, 255)  # #EAF3FF
_HI = (10, 77, 160)    # #0A4DA0


def _shade(t: float) -> str:
    """Hex colour t of the way (0..1) along the light-to-dark blue ramp."""
    r = round(_LO[0] + (_HI[0] - _LO[0]) * t)
    g = round(_LO[1] + (_HI[1] - _LO[1]) * t)
    b = round(_LO[2] + (_HI[2] - _LO[2]) * t)
    return f"#{r:02X}{g:02X}{b:02X}"


def build_svg(mode: str = "self-contained", accessibility: str = "universal") -> str:
    _ = accessibility  # single blue ramp reads in greyscale/CVD; no re-levelling
    n = len(CLASSES)
    vmax = max(max(row) for row in MATRIX)
    tile_r = CORNERS["xs"]

    parts: List[str] = []
    parts.append(svg_open(_WIDTH, _HEIGHT, "cm-title", "cm-desc"))
    parts.append(
        '<title id="cm-title">A 3-class confusion matrix: the classifier is '
        'right on the diagonal and confuses Dog with Fox most</title>'
    )
    parts.append(
        '<desc id="cm-desc">Confusion matrix of a 3-class classifier over 162 '
        'test images. Rows are the actual class (Cat, Dog, Fox), columns the '
        'predicted class; each cell is shaded on a blue ramp by its count, '
        'darkest on the correct diagonal, with the count printed. The heavy '
        'diagonal (52, 44, 39) shows most predictions are correct; the largest '
        'error is 7 foxes predicted as dogs.</desc>'
    )
    parts.append(f'<rect width="{_WIDTH}" height="{_HEIGHT}" fill="{_BG}"/>')

    # Title + subtitle (top-left, house style).
    parts.append(
        f'<text x="40" y="56" font-size="26" font-weight="600" fill="{_INK}" '
        f'letter-spacing="-0.3">Confusion matrix</text>'
    )
    parts.append(
        f'<text x="40" y="84" font-size="14" fill="{_SUBTLE}">'
        f'Actual vs predicted class over 162 test images · diagonal = correct</text>'
    )

    grid_w = n * _CELL + (n - 1) * _GAP

    # Column axis label ("Predicted"), centred above the grid.
    parts.append(
        f'<text x="{_GRID_X + grid_w / 2:.1f}" y="{_GRID_Y - 56:.1f}" '
        f'font-size="16" font-weight="700" fill="{_INK}" text-anchor="middle">'
        f'Predicted</text>'
    )
    # Column class names across the top.
    for j, name in enumerate(CLASSES):
        cx = _GRID_X + j * (_CELL + _GAP) + _CELL / 2
        parts.append(
            f'<text x="{cx:.1f}" y="{_GRID_Y - 26:.1f}" font-size="15" '
            f'fill="{_INK}" text-anchor="middle">{xml_escape(name)}</text>'
        )

    # Row axis label ("Actual"), rotated on the left.
    ax_y = _GRID_Y + grid_w / 2
    parts.append(
        f'<text x="90" y="{ax_y:.1f}" font-size="16" font-weight="700" '
        f'fill="{_INK}" text-anchor="middle" '
        f'transform="rotate(-90 90 {ax_y:.1f})">Actual</text>'
    )

    # Cells + row class names.
    for i, name in enumerate(CLASSES):
        cy = _GRID_Y + i * (_CELL + _GAP) + _CELL / 2
        parts.append(
            f'<text x="{_GRID_X - 24:.1f}" y="{cy + 5:.1f}" font-size="15" '
            f'fill="{_INK}" text-anchor="end">{xml_escape(name)}</text>'
        )
        for j, pred in enumerate(CLASSES):
            count = MATRIX[i][j]
            t = count / vmax if vmax else 0.0
            x = _GRID_X + j * (_CELL + _GAP)
            y = _GRID_Y + i * (_CELL + _GAP)
            fill = _shade(t)
            txt_fill = "#FFFFFF" if t > 0.55 else _INK
            kind = "correct" if i == j else "error"
            tip = f"Actual {name}, predicted {pred}: {count} ({kind})"
            parts.append(
                f'<path d="{rounded_rect_path(x, y, _CELL, _CELL, tile_r, tile_r, tile_r, tile_r)}" '
                f'fill="{fill}"><title>{xml_escape(tip)}</title></path>'
            )
            parts.append(
                f'<text x="{x + _CELL / 2:.1f}" y="{y + _CELL / 2 + 8:.1f}" '
                f'font-size="24" font-weight="700" font-family="Roboto Mono, monospace" '
                f'fill="{txt_fill}" text-anchor="middle" style="pointer-events:none">'
                f'{count}</text>'
            )

    parts.append(fullscreen_control(_WIDTH, _HEIGHT, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def main() -> None:
    """Write the confusion-matrix SVG to the canonical assets path."""
    render_cli(__file__, "confusion-matrix", build_svg,
               description="Render the confusion-matrix SVG.")


if __name__ == "__main__":
    main()
