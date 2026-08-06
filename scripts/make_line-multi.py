#!/usr/bin/env python3
"""
make_line-multi — a house-styled multi-series line chart over a continuous axis as hand-authored SVG.

Plots several series against a continuous quantitative x-axis (typically
hour-of-day or another fine-grained numeric axis, as opposed to
``make_line``'s categorical month axis), with a point marker at every
sample. Hovering a series highlights its line while dimming the rest, so
crossing lines stay readable. Typical uses: sessions per hour by
platform, sensor readings per minute by device, any small set of series
sampled densely along one continuous axis.

Previously rendered via Vega-Lite (``vl_convert``); this module now draws
the polylines and points by hand -- no Vega, no matplotlib. Every point
carries a native ``<title>`` tooltip.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _style import load_palette  # noqa: E402
from _svg import svg_open, xml_escape  # noqa: E402

INK = "#1D1D1F"
SECONDARY = "#6E6E73"
BG = "#FFFFFF"
GRIDLINE = "#E5E5EA"
FONT_MONO = "Roboto Mono, ui-monospace, monospace"

PLATFORMS = ["Desktop", "Mobile"]

_DESKTOP = [41, 41, 42, 40, 39, 43, 58, 77, 92, 98, 101, 103, 99, 104, 108, 106, 99, 91, 80, 70, 62, 55, 48, 44]
_MOBILE = [30, 30, 30, 28, 27, 29, 35, 44, 52, 58, 61, 63, 66, 68, 71, 78, 90, 105, 118, 124, 116, 98, 74, 48]

DEMO_DATA: List[Dict[str, Any]] = [
    {"hour": h, "platform": "Desktop", "sessions": v} for h, v in enumerate(_DESKTOP)
] + [
    {"hour": h, "platform": "Mobile", "sessions": v} for h, v in enumerate(_MOBILE)
]


def _series_colors(accessibility: str = "universal") -> Dict[str, str]:
    palette = load_palette(accessibility)
    hues = [palette.get("Blue", "#007AFF"), palette.get("Orange", "#FF9500")]
    return {s: hues[i % len(hues)] for i, s in enumerate(PLATFORMS)}


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Mobile Use Peaks in the Evening",
    subtitle: str = "Sessions per hour by platform",
    width: int = 745,
    height: int = 480,
    mode: str = "self-contained",
    accessibility: str = "universal",
) -> str:
    """Assemble the full multi-series (continuous-axis) line chart SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``hour`` (numeric), ``platform`` (str), ``sessions``
        (numeric). Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    mode, accessibility : str, optional
        Forwarded to :func:`_interactive.fullscreen_control` /
        :func:`_style.load_palette`.

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    rows = data if data else DEMO_DATA
    series = [s for s in PLATFORMS if any(r["platform"] == s for r in rows)] or sorted({r["platform"] for r in rows})
    colors = _series_colors(accessibility)

    lookup: Dict[tuple, float] = {(r["platform"], float(r["hour"])): float(r["sessions"]) for r in rows}
    hours = sorted({float(r["hour"]) for r in rows})
    all_vals = list(lookup.values())
    max_val = max(all_vals) if all_vals else 1.0
    x_min, x_max = min(hours), max(hours)

    plot_x, plot_y = 60.0, 150.0
    right_margin, bottom_reserved = 30.0, 60.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved

    def x_for(h: float) -> float:
        return plot_x + (h - x_min) / ((x_max - x_min) or 1.0) * plot_w

    y_step = max_val / 4.0
    y_ticks = [i * y_step for i in range(5)]
    y_domain = y_ticks[-1] or 1.0

    def y_for(v: float) -> float:
        return plot_y + plot_h - (v / y_domain * plot_h)

    parts: List[str] = []
    parts.append(svg_open(width, height, "lm-title", "lm-desc"))
    parts.append(f'<title id="lm-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="lm-desc">Multi-series line chart of {len(series)} series over '
        f'{len(hours)} hours, peaking at {max_val:.0f}. Hover or focus a point for its exact '
        f'value.</desc>'
    )
    parts.append(
        "<style>"
        ".series-group{transition:opacity .15s ease;}"
        "svg:hover .series-group,svg:focus-within .series-group{opacity:.35;}"
        + "".join(
            f'svg:has(.s{i}:hover,.s{i}:focus) .s{i}{{opacity:1;}}'
            for i in range(len(series))
        )
        + ".pt{transition:r .12s ease;}"
        ".pt:hover,.pt:focus{r:5.5;outline:none;}"
        "@media (prefers-reduced-motion: reduce){.series-group,.pt{transition:none;}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="40" y="46" font-size="24" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(f'<text x="40" y="70" font-size="14" fill="{SECONDARY}">{xml_escape(subtitle)}</text>')

    # ---- legend ----
    lx, ly = 40.0, 100.0
    cursor = lx
    ly2 = ly + 22
    for s in series:
        parts.append(
            f'<line x1="{cursor:.1f}" y1="{ly2 - 5:.1f}" x2="{cursor + 16:.1f}" y2="{ly2 - 5:.1f}" '
            f'stroke="{colors[s]}" stroke-width="2.5"/>'
        )
        parts.append(f'<text x="{cursor + 22:.1f}" y="{ly2:.1f}" font-size="12" fill="{INK}">{xml_escape(s)}</text>')
        cursor += 22 + 7.2 * len(s) + 20

    # ---- y-axis gridlines ----
    for tick in y_ticks:
        ty = y_for(tick)
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{ty:.1f}" x2="{plot_x + plot_w:.1f}" y2="{ty:.1f}" '
            f'stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{ty + 4:.1f}" font-size="11" font-family="{FONT_MONO}" '
            f'fill="{SECONDARY}" text-anchor="end">{tick:.0f}</text>'
        )
    parts.append(
        f'<text x="18" y="{plot_y + plot_h / 2:.1f}" font-size="13" fill="{INK}" '
        f'text-anchor="middle" transform="rotate(-90 18 {plot_y + plot_h / 2:.1f})">Sessions</text>'
    )

    # ---- lines + points ----
    for si, s in enumerate(series):
        pts = [(x_for(h), y_for(lookup.get((s, h), 0.0))) for h in hours]
        path_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        parts.append(f'<g class="series-group s{si}">')
        parts.append(f'<path d="{path_d}" fill="none" stroke="{colors[s]}" stroke-width="2.5"/>')
        for h in hours:
            v = lookup.get((s, h), 0.0)
            cx, cy = x_for(h), y_for(v)
            tip = f"{s}, {h:.0f}:00: {v:.0f} sessions"
            parts.append(
                f'<circle class="pt" tabindex="0" cx="{cx:.1f}" cy="{cy:.1f}" r="3.5" '
                f'fill="{colors[s]}" stroke="{BG}" stroke-width="1.5">'
                f'<title>{xml_escape(tip)}</title></circle>'
            )
        parts.append("</g>")

    # ---- x-axis ----
    axis_y = plot_y + plot_h
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{axis_y:.1f}" x2="{plot_x + plot_w:.1f}" y2="{axis_y:.1f}" '
        f'stroke="{INK}" stroke-width="1.2"/>'
    )
    for h in hours:
        if int(h) % 3 != 0:
            continue
        parts.append(
            f'<text x="{x_for(h):.1f}" y="{axis_y + 20:.1f}" font-size="11" font-family="{FONT_MONO}" '
            f'fill="{SECONDARY}" text-anchor="middle">{h:.0f}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{axis_y + 42:.1f}" font-size="13" '
        f'fill="{INK}" text-anchor="middle">Hour of Day</text>'
    )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_line_multi(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Mobile Use Peaks in the Evening",
    subtitle: str = "Sessions per hour by platform",
    width: int = 745,
    height: int = 480,
    mode: str = "self-contained",
    accessibility: str = "universal",
) -> Path:
    """Render a hand-authored multi-series (continuous-axis) line chart and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``hour`` (float), ``platform`` (str), ``sessions``
        (float). Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/line-multi.svg``.
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
    >>> p = make_line_multi()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility)
    dest = Path(out) if out else svg_example_path(__file__, "line-multi")
    return write_svg(dest, svg)


def main() -> None:
    render_cli(__file__, "line-multi", build_svg, description="Generate a multi-series line chart over a continuous axis.")


if __name__ == "__main__":
    main()
