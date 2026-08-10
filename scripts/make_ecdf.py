#!/usr/bin/env python3
"""
make_ecdf — a house-styled empirical cumulative distribution function (ECDF) as hand-authored SVG.

Plots the fraction of observations at or below each value as a step
function: no binning choice to second-guess (unlike a histogram), every
observation contributes exactly one step, and any percentile can be read
directly off the curve. A dashed reference line at a chosen percentile
(90th by default) turns "what's my p90 latency" into a single glance.
Typical uses: request-latency SLOs, exam-score distributions, any sample
where percentile thresholds matter more than the shape's name.

Previously rendered via Vega-Lite (a ``window`` + ``joinaggregate`` +
``calculate`` transform chain producing a step-after line, plus a rule
layer for the percentile marker; ``vl_convert``); this module now sorts
and accumulates the values itself and paints the step path by hand -- no
Vega, no matplotlib. The curve carries a native ``<title>`` tooltip.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _svg import svg_open, xml_escape  # noqa: E402
from _style import BG, GRIDLINE, INK, SECONDARY  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

COLOR_LINE = "#007AFF"
COLOR_MARKER = "#C7C7CC"


def _make_demo_data() -> List[Dict[str, Any]]:
    rng = random.Random(21)
    rows: List[Dict[str, Any]] = []
    for _ in range(240):
        latency = max(20.0, rng.lognormvariate(4.95, 0.42))
        rows.append({"latency": round(latency)})
    return rows


DEMO_DATA: List[Dict[str, Any]] = _make_demo_data()


def _percentile(sorted_vals: List[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    pos = p * (len(sorted_vals) - 1)
    lo, hi = int(pos), min(int(pos) + 1, len(sorted_vals) - 1)
    frac = pos - lo
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * frac


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    percentile: float = 0.9,
    title: Optional[str] = None,
    subtitle: str = "Cumulative distribution of request latency",
    width: int = 745,
    height: int = 420,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full ECDF SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with key ``latency`` (numeric). Defaults to :data:`DEMO_DATA`.
    percentile : float
        Reference percentile marked with a dashed line, in ``(0, 1)``.
        Default 0.9 (p90).
    title : str or None
        Chart headline. Defaults to an auto-generated "P% of requests
        finish under V ms" from the data and ``percentile``.
    subtitle : str
        Chart subtitle.
    width, height : int
        Canvas size in pixels.
    mode : str, optional
        Forwarded to :func:`_interactive.fullscreen_control`.
    accessibility : str, optional
        Accepted for CLI parity but a documented no-op: a single house-
        blue step curve, no categorical hues to re-level.
    theme : str, optional
        Visual theme: ``"corporate"`` (default, Roboto -- byte-identical to
        the pre-theme render) or ``"academic"`` (LaTeX-style Latin Modern).
        See :func:`sprezzature_figures.fonts.chrome_stack_for_theme`.

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    _ = accessibility
    mono_family = mono_stack_for_theme(theme)
    rows = data if data else DEMO_DATA
    values = sorted(float(r["latency"]) for r in rows)
    n = len(values)
    p_value = _percentile(values, percentile)
    if title is None:
        title = f"{percentile * 100:.0f}% of Requests Finish Under {p_value:.0f} ms"

    v_min, v_max = values[0], values[-1]
    pad = (v_max - v_min) * 0.04 or 1.0

    plot_x, plot_y = 64.0, 118.0
    right_margin, bottom_reserved = 30.0, 60.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved

    def x_for(v: float) -> float:
        return plot_x + (v - (v_min - pad)) / ((v_max + pad) - (v_min - pad)) * plot_w

    def y_for(cum: float) -> float:
        return plot_y + plot_h - cum * plot_h

    parts: List[str] = []
    parts.append(svg_open(width, height, "ecdf-title", "ecdf-desc", font_family=chrome_stack_for_theme(theme)))
    parts.append(f'<title id="ecdf-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="ecdf-desc">Empirical CDF of {n} observations, ranging {v_min:.0f} to '
        f'{v_max:.0f}. Dashed line marks the {percentile * 100:.0f}th percentile at {p_value:.0f}.</desc>'
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="40" y="46" font-size="22" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(f'<text x="40" y="70" font-size="14" fill="{SECONDARY}">{xml_escape(subtitle)}</text>')

    # ---- y-axis gridlines (0%, 25%, ..., 100%) ----
    for i in range(5):
        frac = i / 4.0
        ty = y_for(frac)
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{ty:.1f}" x2="{plot_x + plot_w:.1f}" y2="{ty:.1f}" '
            f'stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{ty + 4:.1f}" font-size="11" font-family="{mono_family}" '
            f'fill="{SECONDARY}" text-anchor="end">{frac * 100:.0f}%</text>'
        )
    parts.append(
        f'<text x="18" y="{plot_y + plot_h / 2:.1f}" font-size="13" fill="{INK}" '
        f'text-anchor="middle" transform="rotate(-90 18 {plot_y + plot_h / 2:.1f})">Cumulative share</text>'
    )

    # ---- percentile reference line ----
    py = y_for(percentile)
    px = x_for(p_value)
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{py:.1f}" x2="{plot_x + plot_w:.1f}" y2="{py:.1f}" '
        f'stroke="{COLOR_MARKER}" stroke-width="1.5" stroke-dasharray="4 3"/>'
    )
    parts.append(
        f'<line x1="{px:.1f}" y1="{py:.1f}" x2="{px:.1f}" y2="{plot_y + plot_h:.1f}" '
        f'stroke="{COLOR_MARKER}" stroke-width="1.5" stroke-dasharray="4 3"/>'
    )

    # ---- step-after ECDF curve ----
    step_pts: List[tuple] = []
    for i, v in enumerate(values):
        cum = (i + 1) / n
        x = x_for(v)
        if step_pts:
            step_pts.append((x, step_pts[-1][1]))
        step_pts.append((x, y_for(cum)))
    path_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in step_pts)
    tip = f"{n} observations, {percentile * 100:.0f}th percentile = {p_value:.0f} ms"
    parts.append(
        f'<path tabindex="0" d="{path_d}" fill="none" stroke="{COLOR_LINE}" stroke-width="2.2">'
        f'<title>{xml_escape(tip)}</title></path>'
    )
    parts.append(
        f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4.5" fill="{COLOR_LINE}" stroke="{BG}" stroke-width="1.5"/>'
    )

    # ---- x-axis ----
    axis_y = plot_y + plot_h
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{axis_y:.1f}" x2="{plot_x + plot_w:.1f}" y2="{axis_y:.1f}" '
        f'stroke="{INK}" stroke-width="1.2"/>'
    )
    x_ticks = 6
    for i in range(x_ticks + 1):
        val = (v_min - pad) + ((v_max + pad) - (v_min - pad)) * i / x_ticks
        tx = x_for(val)
        parts.append(
            f'<text x="{tx:.1f}" y="{axis_y + 20:.1f}" font-size="11" font-family="{mono_family}" '
            f'fill="{SECONDARY}" text-anchor="middle">{val:.0f}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{axis_y + 42:.1f}" font-size="13" '
        f'fill="{INK}" text-anchor="middle">Latency (ms)</text>'
    )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_ecdf(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    percentile: float = 0.9,
    title: Optional[str] = None,
    subtitle: str = "Cumulative distribution of request latency",
    width: int = 745,
    height: int = 420,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored ECDF and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with key ``latency`` (float). Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/ecdf.svg``.
    percentile : float
        Reference percentile marked on the curve. Default 0.9.
    title : str or None
        Chart headline. Defaults to an auto-generated "P% of requests
        finish under V ms" from the data and ``percentile``.
    subtitle : str
        Chart subtitle.
    width, height : int
        Canvas size in pixels.
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
    >>> p = make_ecdf()
    >>> p.exists()
    True
    """
    svg = build_svg(data, percentile=percentile, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility, theme=theme)
    dest = Path(out) if out else svg_example_path(__file__, "ecdf")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "ecdf", build_svg, description="Generate an empirical CDF plot.")


if __name__ == "__main__":
    main()
