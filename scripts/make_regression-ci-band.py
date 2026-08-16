#!/usr/bin/env python3
"""
make_regression-ci-band — a house-styled OLS regression with a confidence band as hand-authored SVG.

Fits a straight line to a scatter of points by ordinary least squares and
plots it with a shaded 95% confidence band around the fitted mean:
narrower near the centre of the data, widening toward the edges, exactly
where the fit is least certain. The scatter stays visible underneath so
the reader can judge the fit's plausibility directly. The default chart
for "is there a linear trend here, and how sure are we".

Previously rendered via Vega-Lite (the regression computed offline, three
layers: band, scatter, line; ``vl_convert``). This module now runs the
OLS fit itself (closed-form least squares, residual standard error, the
standard formula for the standard error of the mean prediction) and
paints all three layers by hand. No Vega, no matplotlib, no scipy. The
fitted line carries a native ``<title>`` tooltip with the fit equation.

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
from _svg import svg_open, tooltip_bubble, xml_escape  # noqa: E402
from _style import BG, GRIDLINE, INK, SECONDARY  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

COLOR_BAND = "#FF3B30"
COLOR_POINT = "#8E8E93"
COLOR_LINE = "#FF3B30"


def _make_demo_data() -> List[Dict[str, Any]]:
    rng = random.Random(23)
    rows: List[Dict[str, Any]] = []
    for _ in range(80):
        x = rng.uniform(0.0, 10.0)
        y = 2.8 + 1.35 * x + rng.gauss(0.0, 1.6)
        rows.append({"x": round(x, 2), "y": round(y, 2)})
    return rows


DEMO_DATA: List[Dict[str, Any]] = _make_demo_data()


def _ols_fit(xs: List[float], ys: List[float]) -> Dict[str, float]:
    """Ordinary least squares slope/intercept plus residual standard error."""
    n = len(xs)
    x_bar, y_bar = sum(xs) / n, sum(ys) / n
    s_xx = sum((x - x_bar) ** 2 for x in xs)
    s_xy = sum((x - x_bar) * (y - y_bar) for x, y in zip(xs, ys))
    slope = s_xy / s_xx
    intercept = y_bar - slope * x_bar
    residuals = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
    s2 = sum(r * r for r in residuals) / max(1, n - 2)
    return {"slope": slope, "intercept": intercept, "s2": s2, "x_bar": x_bar, "s_xx": s_xx, "n": n}


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "A Clear Positive Trend",
    subtitle: str = "Linear fit with 95% confidence band",
    width: int = 745,
    height: int = 480,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full regression-with-CI-band SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``x``, ``y`` (numeric). Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    mode : str, optional
        Forwarded to :func:`_interactive.fullscreen_control`.
    accessibility : str, optional
        Accepted for CLI parity but a documented no-op: fixed fit/scatter
        colours, no categorical hues to re-level.
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
    xs = [float(r["x"]) for r in rows]
    ys = [float(r["y"]) for r in rows]
    fit = _ols_fit(xs, ys)

    x_min, x_max = min(xs), max(xs)
    n_grid = 41
    step = (x_max - x_min) / (n_grid - 1)
    grid_x = [x_min + i * step for i in range(n_grid)]

    def predict(x: float) -> float:
        return fit["intercept"] + fit["slope"] * x

    def se(x: float) -> float:
        return math.sqrt(fit["s2"] * (1.0 / fit["n"] + (x - fit["x_bar"]) ** 2 / fit["s_xx"]))

    yhat = [predict(x) for x in grid_x]
    lo = [predict(x) - 1.96 * se(x) for x in grid_x]
    hi = [predict(x) + 1.96 * se(x) for x in grid_x]

    y_min = min(min(lo), min(ys))
    y_max = max(max(hi), max(ys))
    y_pad = (y_max - y_min) * 0.08 or 1.0
    x_pad = (x_max - x_min) * 0.04 or 1.0

    plot_x, plot_y = 60.0, 118.0
    right_margin, bottom_reserved = 30.0, 60.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved

    def x_for(v: float) -> float:
        return plot_x + (v - (x_min - x_pad)) / ((x_max + x_pad) - (x_min - x_pad)) * plot_w

    def y_for(v: float) -> float:
        return plot_y + plot_h - (v - (y_min - y_pad)) / ((y_max + y_pad) - (y_min - y_pad)) * plot_h

    parts: List[str] = []
    parts.append(svg_open(width, height, "reg-title", "reg-desc", font_family=chrome_stack_for_theme(theme)))
    parts.append(f'<title id="reg-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="reg-desc">Linear regression of {len(rows)} points: '
        f'y = {fit["intercept"]:.2f} + {fit["slope"]:.2f}x, with a 95% confidence band.</desc>'
    )
    parts.append(
        "<style>"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        ".hit:hover+.tip,.hit:focus+.tip{opacity:1}"
        "@media (prefers-reduced-motion: reduce){.tip{transition:none}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="40" y="46" font-size="22" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(f'<text x="40" y="70" font-size="14" fill="{SECONDARY}">{xml_escape(subtitle)}</text>')

    # ---- gridlines ----
    y_ticks = 5
    for i in range(y_ticks + 1):
        val = (y_min - y_pad) + ((y_max + y_pad) - (y_min - y_pad)) * i / y_ticks
        ty = y_for(val)
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{ty:.1f}" x2="{plot_x + plot_w:.1f}" y2="{ty:.1f}" '
            f'stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{ty + 4:.1f}" font-size="11" font-family="{mono_family}" '
            f'fill="{SECONDARY}" text-anchor="end">{val:.1f}</text>'
        )
    parts.append(
        f'<text x="18" y="{plot_y + plot_h / 2:.1f}" font-size="13" fill="{INK}" '
        f'text-anchor="middle" transform="rotate(-90 18 {plot_y + plot_h / 2:.1f})">y</text>'
    )

    # ---- confidence band ----
    top_pts = [(x_for(x), y_for(v)) for x, v in zip(grid_x, hi)]
    bot_pts = [(x_for(x), y_for(v)) for x, v in zip(grid_x, lo)]
    band_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in top_pts)
    band_d += " L " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in reversed(bot_pts)) + " Z"
    parts.append(f'<path d="{band_d}" fill="{COLOR_BAND}" fill-opacity="0.15"/>')

    # ---- scatter ----
    for x, y in zip(xs, ys):
        cx, cy = x_for(x), y_for(y)
        resid = y - predict(x)
        pt_tip = f"x = {x:.2f}, y = {y:.2f} (residual {resid:+.2f})"
        parts.append(
            f'<circle class="hit" tabindex="0" cx="{cx:.1f}" cy="{cy:.1f}" r="3" '
            f'fill="{COLOR_POINT}" fill-opacity="0.55" role="img" aria-label="{xml_escape(pt_tip)}"/>'
        )
        parts.append(
            tooltip_bubble(
                cx, cy - 12,
                [f"x = {x:.2f}", f"y = {y:.2f}", f"residual {resid:+.2f}"],
                anchor="middle", canvas_w=width, canvas_h=height,
                ink=INK, secondary=SECONDARY, border=GRIDLINE,
            )
        )

    # ---- fitted line ----
    line_pts = [(x_for(x), y_for(v)) for x, v in zip(grid_x, yhat)]
    line_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in line_pts)
    tip = f"y = {fit['intercept']:.2f} + {fit['slope']:.2f}x (n={fit['n']:.0f})"
    parts.append(
        f'<path class="hit" tabindex="0" d="{line_d}" fill="none" stroke="{COLOR_LINE}" '
        f'stroke-width="2.5" role="img" aria-label="{xml_escape(tip)}"/>'
    )
    mid_x, mid_y = line_pts[len(line_pts) // 2]
    parts.append(
        tooltip_bubble(
            mid_x, mid_y - 16,
            ["OLS fit", f"y = {fit['intercept']:.2f} + {fit['slope']:.2f}x", f"n = {fit['n']:.0f} points"],
            anchor="middle", canvas_w=width, canvas_h=height,
            ink=INK, secondary=SECONDARY, border=GRIDLINE,
        )
    )

    # ---- x-axis ----
    axis_y = plot_y + plot_h
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{axis_y:.1f}" x2="{plot_x + plot_w:.1f}" y2="{axis_y:.1f}" '
        f'stroke="{INK}" stroke-width="1.2"/>'
    )
    x_ticks = 6
    for i in range(x_ticks + 1):
        val = (x_min - x_pad) + ((x_max + x_pad) - (x_min - x_pad)) * i / x_ticks
        tx = x_for(val)
        parts.append(
            f'<text x="{tx:.1f}" y="{axis_y + 20:.1f}" font-size="11" font-family="{mono_family}" '
            f'fill="{SECONDARY}" text-anchor="middle">{val:.1f}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{axis_y + 42:.1f}" font-size="13" '
        f'fill="{INK}" text-anchor="middle">x</text>'
    )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_regression_ci_band(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "A Clear Positive Trend",
    subtitle: str = "Linear fit with 95% confidence band",
    width: int = 745,
    height: int = 480,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored regression-with-CI-band figure and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``x``, ``y`` (float). Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to
        ``assets/svg-examples/regression-ci-band.svg``.
    title, subtitle : str
        Chart text.
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
    >>> p = make_regression_ci_band()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility, theme=theme)
    dest = Path(out) if out else svg_example_path(__file__, "regression-ci-band")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "regression-ci-band", build_svg, description="Generate a linear regression with a confidence band.")


if __name__ == "__main__":
    main()
