#!/usr/bin/env python3
"""
make_kde1d — a house-styled 1-D kernel density estimate as hand-authored SVG.

Smooths a sample of numeric observations into a continuous density curve
using a Gaussian kernel at each point, summed and normalised -- no
binning choice the way a histogram forces one, and the bandwidth is the
only smoothing knob. A vertical gradient fill (pale at the baseline, full
house blue at the curve) keeps the shape readable without a legend.
Typical uses: any single numeric sample where the exact bin edges of a
histogram would be a distraction from the shape itself.

Previously rendered via Vega-Lite (the ``density`` transform, ``vl_convert``);
this module now computes the kernel density estimate itself and paints the
filled curve by hand -- no Vega, no matplotlib, no scipy. The curve carries
a native ``<title>`` tooltip.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _svg import svg_open, xml_escape  # noqa: E402

INK = "#1D1D1F"
SECONDARY = "#6E6E73"
BG = "#FFFFFF"
GRIDLINE = "#E5E5EA"
FONT_MONO = "Roboto Mono, ui-monospace, monospace"
COLOR_TOP = "#007AFF"
COLOR_BOTTOM = "#EAF3FF"


def _make_demo_data() -> List[Dict[str, Any]]:
    rng = random.Random(17)
    rows: List[Dict[str, Any]] = []
    for _ in range(90):
        rows.append({"x": round(rng.gauss(6.3, 0.85), 2)})
    return rows


DEMO_DATA: List[Dict[str, Any]] = _make_demo_data()


def _gaussian_kde(samples: List[float], x_eval: List[float], bandwidth: float) -> List[float]:
    """Evaluate a Gaussian-kernel density estimate of *samples* at *x_eval*."""
    n = len(samples)
    norm = 1.0 / (n * bandwidth * math.sqrt(2.0 * math.pi))
    density: List[float] = []
    for x in x_eval:
        total = sum(math.exp(-0.5 * ((x - s) / bandwidth) ** 2) for s in samples)
        density.append(norm * total)
    return density


def _silverman_bandwidth(samples: List[float]) -> float:
    """Silverman's rule-of-thumb bandwidth for a Gaussian KDE."""
    n = len(samples)
    mean = sum(samples) / n
    std = math.sqrt(sum((s - mean) ** 2 for s in samples) / max(1, n - 1)) or 1.0
    return 0.9 * std * n ** (-1.0 / 5.0)


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Estimated Density",
    subtitle: str = "Gaussian kernel density estimate",
    width: int = 620,
    height: int = 380,
    mode: str = "self-contained",
    accessibility: str = "universal",
) -> str:
    """Assemble the full 1-D KDE SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with key ``x`` (numeric). Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    mode : str, optional
        Forwarded to :func:`_interactive.fullscreen_control`.
    accessibility : str, optional
        Accepted for CLI parity but a documented no-op: a single
        house-blue gradient fill, no categorical hues to re-level.

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    _ = accessibility
    rows = data if data else DEMO_DATA
    samples = [float(r["x"]) for r in rows]
    bandwidth = _silverman_bandwidth(samples)
    s_min, s_max = min(samples), max(samples)
    span = (s_max - s_min) or 1.0
    x_lo, x_hi = s_min - span * 0.3, s_max + span * 0.3

    n_points = 200
    step = (x_hi - x_lo) / (n_points - 1)
    x_eval = [x_lo + i * step for i in range(n_points)]
    density = _gaussian_kde(samples, x_eval, bandwidth)
    peak = max(density) * 1.12

    plot_x, plot_y = 60.0, 118.0
    right_margin, bottom_reserved = 30.0, 60.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved

    def x_for(v: float) -> float:
        return plot_x + (v - x_lo) / (x_hi - x_lo) * plot_w

    def y_for(v: float) -> float:
        return plot_y + plot_h - (v / peak * plot_h)

    parts: List[str] = []
    parts.append(svg_open(width, height, "kde-title", "kde-desc"))
    parts.append(f'<title id="kde-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="kde-desc">Kernel density estimate of {len(samples)} observations, '
        f'bandwidth {bandwidth:.2f}, ranging {s_min:.1f} to {s_max:.1f}.</desc>'
    )
    parts.append(
        f'<defs><linearGradient id="kdeGrad" x1="0" y1="1" x2="0" y2="0">'
        f'<stop offset="0" stop-color="{COLOR_BOTTOM}"/>'
        f'<stop offset="1" stop-color="{COLOR_TOP}"/>'
        f'</linearGradient></defs>'
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="40" y="46" font-size="22" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(f'<text x="40" y="70" font-size="14" fill="{SECONDARY}">{xml_escape(subtitle)}</text>')

    # ---- gridlines ----
    y_ticks = 4
    for i in range(y_ticks + 1):
        val = peak * i / y_ticks
        ty = y_for(val)
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{ty:.1f}" x2="{plot_x + plot_w:.1f}" y2="{ty:.1f}" '
            f'stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{ty + 4:.1f}" font-size="10" font-family="{FONT_MONO}" '
            f'fill="{SECONDARY}" text-anchor="end">{val:.3f}</text>'
        )
    parts.append(
        f'<text x="18" y="{plot_y + plot_h / 2:.1f}" font-size="13" fill="{INK}" '
        f'text-anchor="middle" transform="rotate(-90 18 {plot_y + plot_h / 2:.1f})">Density</text>'
    )

    # ---- filled curve ----
    axis_y = plot_y + plot_h
    top_pts = [(x_for(x), y_for(d)) for x, d in zip(x_eval, density)]
    path_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in top_pts)
    path_d += f" L {top_pts[-1][0]:.1f},{axis_y:.1f} L {top_pts[0][0]:.1f},{axis_y:.1f} Z"
    tip = f"KDE of {len(samples)} observations, bandwidth {bandwidth:.2f}"
    parts.append(
        f'<path tabindex="0" d="{path_d}" fill="url(#kdeGrad)" fill-opacity="0.85" '
        f'stroke="{COLOR_TOP}" stroke-width="2"><title>{xml_escape(tip)}</title></path>'
    )

    # ---- x-axis ----
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{axis_y:.1f}" x2="{plot_x + plot_w:.1f}" y2="{axis_y:.1f}" '
        f'stroke="{INK}" stroke-width="1.2"/>'
    )
    x_ticks = 7
    for i in range(x_ticks + 1):
        val = x_lo + (x_hi - x_lo) * i / x_ticks
        tx = x_for(val)
        parts.append(
            f'<text x="{tx:.1f}" y="{axis_y + 20:.1f}" font-size="11" font-family="{FONT_MONO}" '
            f'fill="{SECONDARY}" text-anchor="middle">{val:.1f}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{axis_y + 42:.1f}" font-size="13" '
        f'fill="{INK}" text-anchor="middle">x</text>'
    )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_kde1d(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Estimated Density",
    subtitle: str = "Gaussian kernel density estimate",
    width: int = 620,
    height: int = 380,
    mode: str = "self-contained",
    accessibility: str = "universal",
) -> Path:
    """Render a hand-authored 1-D KDE and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with key ``x`` (float). Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/kde1d.svg``.
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
    >>> p = make_kde1d()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility)
    dest = Path(out) if out else svg_example_path(__file__, "kde1d")
    return write_svg(dest, svg)


def main() -> None:
    render_cli(__file__, "kde1d", build_svg, description="Generate a 1-D kernel density estimate.")


if __name__ == "__main__":
    main()
