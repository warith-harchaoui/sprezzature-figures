#!/usr/bin/env python3
"""
make_corr-matrix — a house-styled correlation matrix heatmap as hand-authored SVG.

A symmetric grid of pairwise correlation coefficients, one row and column
per numeric feature, cell colour on a diverging red-white-blue scale
centred on zero so positive and negative correlation read as opposite
hues at a glance, and each cell's exact coefficient printed on top.
Typical uses: exploring a new dataset's feature relationships before
modelling, spotting multicollinearity, confirming an expected correlation
structure.

Previously rendered via Vega-Lite (a layered ``rect`` + ``text`` mark,
``vl_convert``); this module now paints both layers by hand -- no Vega,
no matplotlib. Every cell carries a native ``<title>`` tooltip.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _svg import svg_open, xml_escape  # noqa: E402

INK = "#1D1D1F"
SECONDARY = "#6E6E73"
BG = "#FFFFFF"
FONT_MONO = "Roboto Mono, ui-monospace, monospace"

FEATURES = ["mpg", "hp", "wt", "accel", "disp"]

# Diverging red-white-blue, centred on r=0.
_RAMP: Tuple[Tuple[float, str], ...] = (
    (-1.0, "#FF3B30"),
    (0.0, "#FFFFFF"),
    (1.0, "#007AFF"),
)


def _ramp_hex(r: float) -> str:
    """Sample the diverging red-white-blue ramp at correlation ``r`` in ``[-1, 1]``."""
    r = min(1.0, max(-1.0, r))
    for (lo_t, lo_c), (hi_t, hi_c) in zip(_RAMP, _RAMP[1:]):
        if lo_t <= r <= hi_t:
            local = (r - lo_t) / (hi_t - lo_t) if hi_t > lo_t else 0.0
            ar, ag, ab = int(lo_c[1:3], 16), int(lo_c[3:5], 16), int(lo_c[5:7], 16)
            br, bg, bb = int(hi_c[1:3], 16), int(hi_c[3:5], 16), int(hi_c[5:7], 16)
            red = round(ar + (br - ar) * local)
            green = round(ag + (bg - ag) * local)
            blue = round(ab + (bb - ab) * local)
            return f"#{red:02X}{green:02X}{blue:02X}"
    return _RAMP[-1][1]


# Symmetric feature-correlation demo values (5x5, diagonal = 1.0).
DEMO_DATA: List[Dict[str, Any]] = [
    {"a": "mpg", "b": "mpg", "r": 1.0}, {"a": "mpg", "b": "hp", "r": -0.78},
    {"a": "mpg", "b": "wt", "r": -0.87}, {"a": "mpg", "b": "accel", "r": 0.42},
    {"a": "mpg", "b": "disp", "r": -0.85}, {"a": "hp", "b": "mpg", "r": -0.78},
    {"a": "hp", "b": "hp", "r": 1.0}, {"a": "hp", "b": "wt", "r": 0.66},
    {"a": "hp", "b": "accel", "r": -0.69}, {"a": "hp", "b": "disp", "r": 0.79},
    {"a": "wt", "b": "mpg", "r": -0.87}, {"a": "wt", "b": "hp", "r": 0.66},
    {"a": "wt", "b": "wt", "r": 1.0}, {"a": "wt", "b": "accel", "r": -0.42},
    {"a": "wt", "b": "disp", "r": 0.89}, {"a": "accel", "b": "mpg", "r": 0.42},
    {"a": "accel", "b": "hp", "r": -0.69}, {"a": "accel", "b": "wt", "r": -0.42},
    {"a": "accel", "b": "accel", "r": 1.0}, {"a": "accel", "b": "disp", "r": -0.55},
    {"a": "disp", "b": "mpg", "r": -0.85}, {"a": "disp", "b": "hp", "r": 0.79},
    {"a": "disp", "b": "wt", "r": 0.89}, {"a": "disp", "b": "accel", "r": -0.55},
    {"a": "disp", "b": "disp", "r": 1.0},
]


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Feature Correlation",
    subtitle: str = "Pairwise Pearson correlation coefficient",
    width: int = 460,
    height: int = 460,
    mode: str = "self-contained",
    accessibility: str = "universal",
) -> str:
    """Assemble the full correlation matrix SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``a`` (str), ``b`` (str), ``r`` (numeric, -1..1).
        Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    mode : str, optional
        Forwarded to :func:`_interactive.fullscreen_control`.
    accessibility : str, optional
        Accepted for CLI parity but a documented no-op: the ramp is a
        fixed red-white-blue diverging semantic (negative/positive
        correlation), not a re-levelled categorical palette.

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    _ = accessibility
    rows = data if data else DEMO_DATA
    seen_features: List[str] = []
    for r in rows:
        if r["a"] not in seen_features:
            seen_features.append(r["a"])
    features = [f for f in FEATURES if f in seen_features] + [f for f in seen_features if f not in FEATURES]
    lookup: Dict[Tuple[str, str], float] = {(r["a"], r["b"]): float(r["r"]) for r in rows}

    plot_x, plot_y = 100.0, 118.0
    right_margin, bottom_margin = 24.0, 24.0
    n = len(features)
    grid_w = width - plot_x - right_margin
    grid_h = height - plot_y - bottom_margin
    cell = min(grid_w / n, grid_h / n)

    parts: List[str] = []
    parts.append(svg_open(width, height, "cm2-title", "cm2-desc"))
    parts.append(f'<title id="cm2-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="cm2-desc">Correlation matrix of {n} features. Hover or focus a cell '
        f'for its exact coefficient.</desc>'
    )
    parts.append(
        "<style>"
        ".cell{transition:stroke-width .1s ease;}"
        ".cell:hover,.cell:focus{stroke:#1D1D1F;stroke-width:1.5;outline:none;}"
        "@media (prefers-reduced-motion: reduce){.cell{transition:none;}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="20" y="42" font-size="21" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(f'<text x="20" y="64" font-size="13" fill="{SECONDARY}">{xml_escape(subtitle)}</text>')

    # ---- column labels (top) ----
    for ci, f in enumerate(features):
        tx = plot_x + ci * cell + cell / 2
        parts.append(
            f'<text x="{tx:.1f}" y="{plot_y - 10:.1f}" font-size="11" font-family="{FONT_MONO}" '
            f'fill="{SECONDARY}" text-anchor="middle">{xml_escape(f)}</text>'
        )
    # ---- row labels (left) ----
    for ri, f in enumerate(features):
        ty = plot_y + ri * cell + cell / 2 + 4
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{ty:.1f}" font-size="11" font-family="{FONT_MONO}" '
            f'fill="{SECONDARY}" text-anchor="end">{xml_escape(f)}</text>'
        )

    # ---- cells + labels ----
    for ri, a in enumerate(features):
        for ci, b in enumerate(features):
            r = lookup.get((a, b), 0.0)
            x = plot_x + ci * cell
            y = plot_y + ri * cell
            text_color = "#FFFFFF" if abs(r) > 0.6 else INK
            tip = f"{a} x {b}: r = {r:.2f}"
            parts.append(
                f'<rect class="cell" tabindex="0" x="{x:.1f}" y="{y:.1f}" width="{cell:.1f}" '
                f'height="{cell:.1f}" fill="{_ramp_hex(r)}" stroke="{BG}" stroke-width="1">'
                f'<title>{xml_escape(tip)}</title></rect>'
            )
            parts.append(
                f'<text x="{x + cell / 2:.1f}" y="{y + cell / 2 + 4:.1f}" font-size="12" '
                f'font-family="{FONT_MONO}" fill="{text_color}" text-anchor="middle">{r:.2f}</text>'
            )

    # ---- legend ----
    ly = height - 8.0
    lx0 = plot_x
    parts.append(f'<text x="{lx0:.1f}" y="{ly:.1f}" font-size="10" fill="{SECONDARY}">-1</text>')
    swatch_x = lx0 + 22.0
    n_swatches = 9
    for i in range(n_swatches):
        r = -1.0 + 2.0 * i / (n_swatches - 1)
        parts.append(f'<rect x="{swatch_x + i * 14:.1f}" y="{ly - 10:.1f}" width="12" height="11" fill="{_ramp_hex(r)}" stroke="#E5E5EA" stroke-width="0.5"/>')
    parts.append(f'<text x="{swatch_x + n_swatches * 14 + 6:.1f}" y="{ly:.1f}" font-size="10" fill="{SECONDARY}">+1</text>')

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_corr_matrix(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Feature Correlation",
    subtitle: str = "Pairwise Pearson correlation coefficient",
    width: int = 460,
    height: int = 460,
    mode: str = "self-contained",
    accessibility: str = "universal",
) -> Path:
    """Render a hand-authored correlation matrix and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``a`` (str), ``b`` (str), ``r`` (float, -1..1).
        Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/corr-matrix.svg``.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    mode, accessibility : str
        Forwarded to :func:`build_svg`.

    Returns
    -------
    Path
        Absolute path to the written SVG file.

    Examples
    --------
    >>> p = make_corr_matrix()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility)
    dest = Path(out) if out else svg_example_path(__file__, "corr-matrix")
    return write_svg(dest, svg)


def main() -> None:
    render_cli(__file__, "corr-matrix", build_svg, description="Generate a correlation matrix heatmap.")


if __name__ == "__main__":
    main()
