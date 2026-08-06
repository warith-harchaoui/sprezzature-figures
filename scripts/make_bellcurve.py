#!/usr/bin/env python3
"""
make_bellcurve — a house-styled bell curve (normal distribution) as hand-authored SVG.

A bell curve visualises a normal distribution by plotting the probability
density function (PDF) against its horizontal axis. It communicates three
things at once: where the distribution is centred (the mean), how spread
out it is (the standard deviation), and how likely each range of values is
(area under the curve). Annotating the mean and one-sigma bands makes the
68-95-99.7 rule tangible.

Previously rendered via Vega-Lite (``vl_convert``); this module now samples
the PDF itself and paints the filled curve plus annotation lines by hand
-- no Vega, no matplotlib.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _svg import svg_open, xml_escape  # noqa: E402

INK = "#1D1D1F"
SECONDARY = "#6E6E73"
BG = "#FFFFFF"
GRIDLINE = "#E5E5EA"
FONT_MONO = "Roboto Mono, ui-monospace, monospace"

COLOR_FILL = "#007AFF"
COLOR_STROKE = "#0051A8"
COLOR_SIGMA1 = "#28CD41"
COLOR_MEAN = "#FF3B30"


def _normal_pdf(x: float, mean: float, std: float) -> float:
    """Return the normal probability density at ``x``."""
    z = (x - mean) / std
    return math.exp(-0.5 * z * z) / (std * math.sqrt(2.0 * math.pi))


def build_svg(
    mean: float = 72.4,
    std: float = 9.1,
    title: str = "Distribution of Student Exam Scores",
    subtitle: str = "Normal distribution fitted to 1,840 exam results; shaded area = one standard deviation around the mean",
    width: int = 845,
    height: int = 519,
    mode: str = "self-contained",
    accessibility: str = "universal",
) -> str:
    """Assemble the full bell curve SVG document as a string.

    Parameters
    ----------
    mean, std : float
        Distribution parameters.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    mode : str, optional
        Forwarded to :func:`_interactive.fullscreen_control`.
    accessibility : str, optional
        Accepted for CLI parity but a documented no-op: the curve is a
        single house-blue fill, no categorical hues to re-level.

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    _ = accessibility
    n_points = 200
    x_min, x_max = mean - 4.0 * std, mean + 4.0 * std
    step = (x_max - x_min) / (n_points - 1)
    curve = [(x_min + i * step, _normal_pdf(x_min + i * step, mean, std)) for i in range(n_points)]
    peak_y = max(y for _, y in curve) * 1.18

    plot_x, plot_y = 76.0, 118.0
    right_margin, bottom_reserved = 30.0, 70.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved

    def x_for(v: float) -> float:
        return plot_x + (v - x_min) / (x_max - x_min) * plot_w

    def y_for(v: float) -> float:
        return plot_y + plot_h - (v / peak_y * plot_h)

    parts: List[str] = []
    parts.append(svg_open(width, height, "bc-title", "bc-desc"))
    parts.append(f'<title id="bc-title">{xml_escape(title)}</title>')
    parts.append(f'<desc id="bc-desc">{xml_escape(subtitle)}</desc>')

    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="40" y="46" font-size="24" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(f'<text x="40" y="70" font-size="14" fill="{SECONDARY}">{xml_escape(subtitle)}</text>')

    # ---- y-axis gridlines ----
    y_ticks = 5
    for i in range(y_ticks + 1):
        val = peak_y * i / y_ticks
        ty = y_for(val)
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{ty:.1f}" x2="{plot_x + plot_w:.1f}" y2="{ty:.1f}" '
            f'stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{ty + 4:.1f}" font-size="10" font-family="{FONT_MONO}" '
            f'fill="{SECONDARY}" text-anchor="end">{val:.4f}</text>'
        )
    parts.append(
        f'<text x="20" y="{plot_y + plot_h / 2:.1f}" font-size="13" fill="{INK}" '
        f'text-anchor="middle" transform="rotate(-90 20 {plot_y + plot_h / 2:.1f})">Probability density</text>'
    )

    # ---- x-axis ----
    axis_y = plot_y + plot_h
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{axis_y:.1f}" x2="{plot_x + plot_w:.1f}" y2="{axis_y:.1f}" '
        f'stroke="{INK}" stroke-width="1"/>'
    )
    x_ticks = 8
    for i in range(x_ticks + 1):
        val = x_min + (x_max - x_min) * i / x_ticks
        tx = x_for(val)
        parts.append(
            f'<text x="{tx:.1f}" y="{axis_y + 20:.1f}" font-size="11" font-family="{FONT_MONO}" '
            f'fill="{SECONDARY}" text-anchor="middle">{val:.0f}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{axis_y + 42:.1f}" font-size="13" '
        f'fill="{INK}" text-anchor="middle">Value</text>'
    )

    # ---- filled curve ----
    top_pts = [(x_for(x), y_for(y)) for x, y in curve]
    path_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in top_pts)
    path_d += f" L {top_pts[-1][0]:.1f},{axis_y:.1f} L {top_pts[0][0]:.1f},{axis_y:.1f} Z"
    tip = f"Normal(mean={mean:.1f}, std={std:.1f}), peak density {max(y for _, y in curve):.4f} at x={mean:.1f}"
    parts.append(
        f'<path tabindex="0" d="{path_d}" fill="{COLOR_FILL}" fill-opacity="0.25" '
        f'stroke="{COLOR_STROKE}" stroke-width="2.5"><title>{xml_escape(tip)}</title></path>'
    )

    # ---- annotation lines: mean and +-1 sigma ----
    annotations = [
        (mean, f"μ = {mean:.1f}", COLOR_MEAN),
        (mean - std, f"−1σ ({mean - std:.1f})", COLOR_SIGMA1),
        (mean + std, f"+1σ ({mean + std:.1f})", COLOR_SIGMA1),
    ]
    for x_val, label, color in annotations:
        ax = x_for(x_val)
        parts.append(
            f'<line x1="{ax:.1f}" y1="{plot_y:.1f}" x2="{ax:.1f}" y2="{axis_y:.1f}" '
            f'stroke="{color}" stroke-width="1.5" stroke-dasharray="5 3"/>'
        )
        parts.append(
            f'<text x="{ax:.1f}" y="{plot_y - 8:.1f}" font-size="11" font-family="{FONT_MONO}" '
            f'fill="{color}" text-anchor="middle">{xml_escape(label)}</text>'
        )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_bellcurve(
    mean: float = 72.4,
    std: float = 9.1,
    *,
    out: Optional[Path | str] = None,
    title: str = "Distribution of Student Exam Scores",
    subtitle: str = "Normal distribution fitted to 1,840 exam results; shaded area = one standard deviation around the mean",
    width: int = 845,
    height: int = 519,
    mode: str = "self-contained",
    accessibility: str = "universal",
) -> Path:
    """Render a hand-authored bell curve figure and write the SVG to *out*.

    Parameters
    ----------
    mean : float
        Distribution mean. Default 72.4 (exam score example).
    std : float
        Standard deviation. Default 9.1.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/bellcurve.svg``.
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
    >>> p = make_bellcurve()
    >>> p.exists()
    True
    """
    svg = build_svg(mean, std, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility)
    dest = Path(out) if out else svg_example_path(__file__, "bellcurve")
    return write_svg(dest, svg)


def main() -> None:
    render_cli(__file__, "bellcurve", build_svg, description="Generate a bell curve (normal distribution) figure.")


if __name__ == "__main__":
    main()
