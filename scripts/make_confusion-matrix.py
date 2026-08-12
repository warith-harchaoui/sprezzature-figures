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
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _style import CORNERS, GRIDLINE  # noqa: E402
from _svg import rounded_rect_path, svg_open, tooltip_bubble, xml_escape  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _interactive import fullscreen_control  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme  # noqa: E402

# --- data: a 3-class pet classifier (rows = actual, cols = predicted) ---------
CLASSES = ["Cat", "Dog", "Fox"]
MATRIX = [
    [52, 5, 3],   # actual Cat
    [6, 44, 4],   # actual Dog
    [2, 7, 39],   # actual Fox
]

# The make_<kind> contract's row-record view of MATRIX: one row per cell.
# make_confusion_matrix() reshapes this back into (classes, matrix) via
# _rows_to_matrix() before calling build_svg().
DEMO_DATA: List[Dict[str, Any]] = [
    {"actual": CLASSES[i], "predicted": CLASSES[j], "count": MATRIX[i][j]}
    for i in range(len(CLASSES))
    for j in range(len(CLASSES))
]


def _rows_to_matrix(rows: List[Dict[str, Any]]) -> tuple[List[str], List[List[int]]]:
    """Reshape actual/predicted/count row records into a dense matrix.

    Parameters
    ----------
    rows : list of dict
        Records shaped ``{"actual": ..., "predicted": ..., "count": ...}``
        (see :data:`DEMO_DATA`). Class order follows first appearance
        across the rows.

    Returns
    -------
    tuple of (list of str, list of list of int)
        ``(classes, matrix)`` where ``matrix[i][j]`` is the count of actual
        ``classes[i]`` predicted as ``classes[j]`` (missing pairs default
        to 0).
    """
    classes: List[str] = []
    for r in rows:
        for key in ("actual", "predicted"):
            name = str(r[key])
            if name not in classes:
                classes.append(name)
    index = {c: i for i, c in enumerate(classes)}
    n = len(classes)
    matrix = [[0 for _ in range(n)] for _ in range(n)]
    for r in rows:
        i, j = index[str(r["actual"])], index[str(r["predicted"])]
        matrix[i][j] = int(r["count"])
    return classes, matrix

# --- geometry + house-style constants -----------------------------------------
# Floors, not fixed sizes: build_svg() grows width/height from these to fit
# however many classes `data` actually has (the grid itself always scales
# with `n`; a canvas that didn't would clip the last row/column for any `n`
# large enough to outgrow the floor -- including the 3-class demo, which
# used to clip by 16px against a literal `_HEIGHT = 640`).
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


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full confusion-matrix SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``actual``, ``predicted`` (str) and ``count`` (int),
        one per cell (see :data:`DEMO_DATA`). Class order follows first
        appearance. Defaults to a 3-class pet classifier.
    mode : str, optional
        Interactivity mode passed to :func:`_interactive.fullscreen_control`.
    accessibility : str, optional
        Accepted for CLI parity but a documented no-op: a single blue ramp
        reads in greyscale/CVD, so it is never re-levelled.
    theme : str, optional
        Visual theme: ``"corporate"`` (default, Roboto -- byte-identical to
        the pre-theme render) or ``"academic"`` (LaTeX-style Latin Modern).
        See :func:`sprezzature_figures.fonts.chrome_stack_for_theme`.

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    _ = accessibility  # single blue ramp reads in greyscale/CVD; no re-levelling
    rows = data if data else DEMO_DATA
    classes, matrix = _rows_to_matrix(rows)
    n = len(classes)
    total = sum(sum(row) for row in matrix)
    vmax = max((max(row) for row in matrix), default=1) or 1
    tile_r = CORNERS["xs"]

    # Narrate the diagonal + biggest miss dynamically so a caller-supplied
    # matrix still gets an accurate <title>/<desc>, not the fixed pet-class
    # story.
    diag = [matrix[i][i] for i in range(n)]
    diag_str = ", ".join(str(v) for v in diag)
    worst = max(
        ((matrix[i][j], classes[i], classes[j]) for i in range(n) for j in range(n) if i != j),
        default=(0, "", ""),
    )
    worst_count, worst_actual, worst_pred = worst
    n_cls_word = f"{n}-class" if n != 1 else "1-class"

    # Grid size follows `n` directly (it's always an n x n square, so one
    # formula gives both edges); grow the canvas from the module floors so
    # the last row/column never clips, whatever `n` a caller's data has.
    grid_w = grid_h = n * _CELL + (n - 1) * _GAP
    width = max(_WIDTH, _GRID_X + grid_w + 90.0)
    height = max(_HEIGHT, _GRID_Y + grid_h + 40.0)

    parts: List[str] = []
    parts.append(svg_open(width, height, "cm-title", "cm-desc", font_family=chrome_stack_for_theme(theme)))
    parts.append(
        f'<title id="cm-title">A {n_cls_word} confusion matrix: the classifier is '
        f'right on the diagonal and confuses {worst_actual} with {worst_pred} most</title>'
    )
    parts.append(
        f'<desc id="cm-desc">Confusion matrix of a {n_cls_word} classifier over '
        f'{total} test images. Rows are the actual class ({", ".join(classes)}), '
        f'columns the predicted class; each cell is shaded on a blue ramp by its '
        f'count, darkest on the correct diagonal, with the count printed. The '
        f'diagonal ({diag_str}) shows most predictions are correct; the largest '
        f'error is {worst_count} {worst_actual} predicted as {worst_pred}.</desc>'
    )
    parts.append(
        "<style>"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        ".hit:hover+.tip,.hit:focus+.tip{opacity:1}"
        "@media (prefers-reduced-motion: reduce){.tip{transition:none}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{_BG}"/>')

    # Title + subtitle (top-left, house style).
    parts.append(
        f'<text x="40" y="56" font-size="26" font-weight="600" fill="{_INK}" '
        f'letter-spacing="-0.3">Confusion matrix</text>'
    )
    parts.append(
        f'<text x="40" y="84" font-size="14" fill="{_SUBTLE}">'
        f'Actual vs predicted class over {total} test images · diagonal = correct</text>'
    )

    # Column axis label ("Predicted"), centred above the grid.
    parts.append(
        f'<text x="{_GRID_X + grid_w / 2:.1f}" y="{_GRID_Y - 56:.1f}" '
        f'font-size="16" font-weight="700" fill="{_INK}" text-anchor="middle">'
        f'Predicted</text>'
    )
    # Column class names across the top.
    for j, name in enumerate(classes):
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
    for i, name in enumerate(classes):
        cy = _GRID_Y + i * (_CELL + _GAP) + _CELL / 2
        parts.append(
            f'<text x="{_GRID_X - 24:.1f}" y="{cy + 5:.1f}" font-size="15" '
            f'fill="{_INK}" text-anchor="end">{xml_escape(name)}</text>'
        )
        row_total = sum(matrix[i])
        for j, pred in enumerate(classes):
            count = matrix[i][j]
            t = count / vmax if vmax else 0.0
            x = _GRID_X + j * (_CELL + _GAP)
            y = _GRID_Y + i * (_CELL + _GAP)
            fill = _shade(t)
            txt_fill = "#FFFFFF" if t > 0.55 else _INK
            kind = "correct" if i == j else "error"
            tip = f"Actual {name}, predicted {pred}: {count} ({kind})"
            parts.append(
                f'<path class="hit" tabindex="0" d="{rounded_rect_path(x, y, _CELL, _CELL, tile_r, tile_r, tile_r, tile_r)}" '
                f'fill="{fill}"><title>{xml_escape(tip)}</title></path>'
            )
            row_share = count / row_total * 100.0 if row_total else 0.0
            parts.append(
                tooltip_bubble(
                    x + _CELL / 2, y - 8,
                    [
                        f"actual {name} → predicted {pred}",
                        f"{count} images ({kind})",
                        f"{row_share:.1f}% of actual {name}",
                    ],
                    anchor="middle", canvas_w=width, canvas_h=height,
                    ink=_INK, secondary=_SUBTLE, border=GRIDLINE,
                )
            )
            parts.append(
                f'<text x="{x + _CELL / 2:.1f}" y="{y + _CELL / 2 + 8:.1f}" '
                f'font-size="24" font-weight="700" font-family="Roboto Mono, monospace" '
                f'fill="{txt_fill}" text-anchor="middle" style="pointer-events:none">'
                f'{count}</text>'
            )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def main() -> None:
    """Write the confusion-matrix SVG to the canonical assets path."""
    render_cli(__file__, "confusion-matrix", build_svg,
               description="Render the confusion-matrix SVG.")


def make_confusion_matrix(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "",
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render the house-styled confusion matrix and write the SVG to *out*.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``actual``, ``predicted`` (str) and ``count`` (int),
        one per cell (see :data:`DEMO_DATA`). Class order follows first
        appearance. Defaults to a 3-class pet classifier.
    out : Path, str, or None
        Output path (.svg). Defaults to
        ``assets/svg-examples/confusion-matrix.svg``.
    title : str, optional
        Accepted for CLI/dispatcher parity; the figure's title and
        narrative <desc> are derived from ``data`` directly.
    mode, accessibility : str
        Forwarded to :func:`build_svg`.
    theme : str, optional
        Visual theme. Forwarded to :func:`build_svg`.

    Returns
    -------
    Path
        Absolute path to the written SVG file.

    Examples
    --------
    >>> p = make_confusion_matrix()
    >>> p.exists()
    True
    """
    _ = title
    svg = build_svg(data, mode=mode, accessibility=accessibility, theme=theme)
    dest = Path(out) if out else svg_example_path(__file__, "confusion-matrix")
    return write_svg(dest, svg, theme=theme)


if __name__ == "__main__":
    main()
