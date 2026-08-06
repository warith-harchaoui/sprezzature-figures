#!/usr/bin/env python3
"""
make_qqplot — a house-styled normal Q-Q plot as hand-authored SVG.

Plots each sorted sample value against the value a normal distribution
would produce at the same rank (its theoretical quantile), so a sample
drawn from a genuinely normal population falls on the dashed y=x
reference line -- systematic curvature or S-shapes reveal skew or
heavy/light tails at a glance, far more sensitively than a histogram's
silhouette. The standard diagnostic for "is this residual/measurement
sample approximately Gaussian".

Previously rendered via Vega-Lite (theoretical quantiles computed offline
against a reference line, ``vl_convert``); this module now computes the
theoretical normal quantiles itself -- Acklam's rational approximation of
the inverse normal CDF, no scipy -- and paints both the points and the
reference line by hand. No Vega, no matplotlib. Every point carries a
native ``<title>`` tooltip.

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
COLOR_POINT = "#007AFF"
COLOR_REF = "#C7C7CC"

# Acklam's rational approximation coefficients for the inverse standard
# normal CDF (public-domain algorithm, accurate to ~1.15e-9).
_ACKLAM_A = (-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02,
             1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00)
_ACKLAM_B = (-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
             6.680131188771972e01, -1.328068155288572e01)
_ACKLAM_C = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00,
             -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00)
_ACKLAM_D = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00,
             3.754408661907416e00)


def _norm_ppf(p: float) -> float:
    """Inverse standard normal CDF via Acklam's rational approximation."""
    p_low, p_high = 0.02425, 1.0 - 0.02425
    if p < p_low:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((_ACKLAM_C[0] * q + _ACKLAM_C[1]) * q + _ACKLAM_C[2]) * q + _ACKLAM_C[3]) * q + _ACKLAM_C[4]) * q + _ACKLAM_C[5]) / (
            (((_ACKLAM_D[0] * q + _ACKLAM_D[1]) * q + _ACKLAM_D[2]) * q + _ACKLAM_D[3]) * q + 1.0
        )
    if p <= p_high:
        q = p - 0.5
        r = q * q
        return (((((_ACKLAM_A[0] * r + _ACKLAM_A[1]) * r + _ACKLAM_A[2]) * r + _ACKLAM_A[3]) * r + _ACKLAM_A[4]) * r + _ACKLAM_A[5]) * q / (
            ((((_ACKLAM_B[0] * r + _ACKLAM_B[1]) * r + _ACKLAM_B[2]) * r + _ACKLAM_B[3]) * r + _ACKLAM_B[4]) * r + 1.0
        )
    q = math.sqrt(-2.0 * math.log(1.0 - p))
    return -(((((_ACKLAM_C[0] * q + _ACKLAM_C[1]) * q + _ACKLAM_C[2]) * q + _ACKLAM_C[3]) * q + _ACKLAM_C[4]) * q + _ACKLAM_C[5]) / (
        (((_ACKLAM_D[0] * q + _ACKLAM_D[1]) * q + _ACKLAM_D[2]) * q + _ACKLAM_D[3]) * q + 1.0
    )


def _make_demo_data() -> List[Dict[str, Any]]:
    rng = random.Random(15)
    rows: List[Dict[str, Any]] = []
    for _ in range(60):
        # A touch of right-skew so the tail visibly departs from the
        # reference line, not a perfectly normal toy sample.
        v = rng.gauss(50.0, 8.0) + max(0.0, rng.gauss(0.0, 6.0)) ** 1.4 * 0.15
        rows.append({"sample": round(v, 2)})
    return rows


DEMO_DATA: List[Dict[str, Any]] = _make_demo_data()


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Normal Q-Q Plot",
    subtitle: str = "Sorted sample vs. theoretical normal quantiles",
    width: int = 520,
    height: int = 520,
    mode: str = "self-contained",
    accessibility: str = "universal",
) -> str:
    """Assemble the full Q-Q plot SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with key ``sample`` (numeric). Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    mode : str, optional
        Forwarded to :func:`_interactive.fullscreen_control`.
    accessibility : str, optional
        Accepted for CLI parity but a documented no-op: a single house-
        blue point series, no categorical hues to re-level.

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    _ = accessibility
    rows = data if data else DEMO_DATA
    sample = sorted(float(r["sample"]) for r in rows)
    n = len(sample)
    mean = sum(sample) / n
    std = math.sqrt(sum((v - mean) ** 2 for v in sample) / max(1, n - 1)) or 1.0

    # Blom's plotting positions -- the standard choice for normal Q-Q plots.
    theoretical = [mean + std * _norm_ppf((i - 0.375) / (n + 0.25)) for i in range(1, n + 1)]

    v_min = min(min(sample), min(theoretical))
    v_max = max(max(sample), max(theoretical))
    pad = (v_max - v_min) * 0.08 or 1.0
    lo, hi = v_min - pad, v_max + pad

    plot_x, plot_y = 70.0, 118.0
    right_margin, bottom_reserved = 30.0, 60.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved

    def x_for(v: float) -> float:
        return plot_x + (v - lo) / (hi - lo) * plot_w

    def y_for(v: float) -> float:
        return plot_y + plot_h - (v - lo) / (hi - lo) * plot_h

    parts: List[str] = []
    parts.append(svg_open(width, height, "qq-title", "qq-desc"))
    parts.append(f'<title id="qq-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="qq-desc">Normal Q-Q plot of {n} observations. Points on the dashed line '
        f'indicate an approximately normal sample.</desc>'
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="40" y="46" font-size="22" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(f'<text x="40" y="70" font-size="14" fill="{SECONDARY}">{xml_escape(subtitle)}</text>')

    # ---- gridlines ----
    ticks = 5
    for i in range(ticks + 1):
        val = lo + (hi - lo) * i / ticks
        tx, ty = x_for(val), y_for(val)
        parts.append(f'<line x1="{plot_x:.1f}" y1="{ty:.1f}" x2="{plot_x + plot_w:.1f}" y2="{ty:.1f}" stroke="{GRIDLINE}" stroke-width="1"/>')
        parts.append(f'<line x1="{tx:.1f}" y1="{plot_y:.1f}" x2="{tx:.1f}" y2="{plot_y + plot_h:.1f}" stroke="{GRIDLINE}" stroke-width="1"/>')
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{ty + 4:.1f}" font-size="11" font-family="{FONT_MONO}" '
            f'fill="{SECONDARY}" text-anchor="end">{val:.0f}</text>'
        )
        parts.append(
            f'<text x="{tx:.1f}" y="{plot_y + plot_h + 20:.1f}" font-size="11" font-family="{FONT_MONO}" '
            f'fill="{SECONDARY}" text-anchor="middle">{val:.0f}</text>'
        )
    parts.append(
        f'<text x="20" y="{plot_y + plot_h / 2:.1f}" font-size="13" fill="{INK}" '
        f'text-anchor="middle" transform="rotate(-90 20 {plot_y + plot_h / 2:.1f})">Sample quantile</text>'
    )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{plot_y + plot_h + 42:.1f}" font-size="13" '
        f'fill="{INK}" text-anchor="middle">Theoretical quantile</text>'
    )

    # ---- reference y=x line ----
    parts.append(
        f'<line x1="{x_for(lo):.1f}" y1="{y_for(lo):.1f}" x2="{x_for(hi):.1f}" y2="{y_for(hi):.1f}" '
        f'stroke="{COLOR_REF}" stroke-width="1.5" stroke-dasharray="5 3"/>'
    )

    # ---- points ----
    for t, s in zip(theoretical, sample):
        cx, cy = x_for(t), y_for(s)
        tip = f"Theoretical {t:.1f}, sample {s:.1f}"
        parts.append(
            f'<circle tabindex="0" cx="{cx:.1f}" cy="{cy:.1f}" r="3.5" fill="{COLOR_POINT}" '
            f'fill-opacity="0.85"><title>{xml_escape(tip)}</title></circle>'
        )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_qqplot(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Normal Q-Q Plot",
    subtitle: str = "Sorted sample vs. theoretical normal quantiles",
    width: int = 520,
    height: int = 520,
    mode: str = "self-contained",
    accessibility: str = "universal",
) -> Path:
    """Render a hand-authored Q-Q plot and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with key ``sample`` (float). Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/qqplot.svg``.
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
    >>> p = make_qqplot()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility)
    dest = Path(out) if out else svg_example_path(__file__, "qqplot")
    return write_svg(dest, svg)


def main() -> None:
    render_cli(__file__, "qqplot", build_svg, description="Generate a normal Q-Q plot.")


if __name__ == "__main__":
    main()
