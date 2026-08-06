#!/usr/bin/env python3
"""
make_line — a house-styled multi-series line chart as a hand-authored SVG.

The default chart for showing how a numeric value evolves over an ordered
axis (typically time) across a small number of series. Typical uses:
monthly revenue by product line, daily active users, sensor readings
over time.

Previously rendered via Vega-Lite (``vl_convert``); this module now draws
the polylines and points by hand -- no Vega, no matplotlib -- so every
point carries a native ``<title>`` tooltip and hovering a series highlights
its line while dimming the rest.

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

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
SERIES = ["Hardware", "Software", "Services"]

DEMO_DATA: List[Dict[str, Any]] = [
    {"month": m, "series": s, "value": v}
    for s, values in {
        "Hardware": [12, 14, 13, 17, 19, 22, 21, 24, 23, 26, 28, 31],
        "Software": [8, 9, 10, 11, 13, 14, 16, 17, 19, 21, 23, 25],
        "Services": [5, 5, 6, 6, 7, 8, 8, 9, 10, 11, 12, 13],
    }.items()
    for m, v in zip(MONTHS, values)
]


def _series_colors(accessibility: str = "universal") -> Dict[str, str]:
    palette = load_palette(accessibility)
    hues = [palette.get("Blue", "#007AFF"), palette.get("Orange", "#FF9500"),
            palette.get("Green", "#34C759")]
    return {s: hues[i % len(hues)] for i, s in enumerate(SERIES)}


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Monthly Revenue by Product Line",
    subtitle: str = "Monthly figures, thousands of EUR",
    width: int = 845,
    height: int = 519,
    mode: str = "self-contained",
    accessibility: str = "universal",
) -> str:
    """Assemble the full multi-series line chart SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``month``, ``series``, ``value``. Defaults to
        :data:`DEMO_DATA`.
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
    series = [s for s in SERIES if any(r["series"] == s for r in rows)] or SERIES
    months = sorted({r["month"] for r in rows}, key=lambda m: MONTHS.index(m) if m in MONTHS else 0)
    colors = _series_colors(accessibility)

    lookup: Dict[tuple, float] = {(r["series"], r["month"]): float(r["value"]) for r in rows}
    all_vals = list(lookup.values())
    max_val = max(all_vals) if all_vals else 1.0

    plot_x, plot_y = 60.0, 150.0
    right_margin, bottom_reserved = 30.0, 70.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved
    n = len(months)
    step = plot_w / max(n - 1, 1)

    def x_for(i: int) -> float:
        return plot_x + i * step

    y_step = max_val / 4.0
    y_ticks = [i * y_step for i in range(5)]
    y_domain = y_ticks[-1] or 1.0

    def y_for(v: float) -> float:
        return plot_y + plot_h - (v / y_domain * plot_h)

    parts: List[str] = []
    parts.append(svg_open(width, height, "line-title", "line-desc"))
    parts.append(f'<title id="line-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="line-desc">Multi-series line chart of {len(series)} series over '
        f'{n} months, peaking at {max_val:.0f}. Hover or focus a point for its exact '
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
    parts.append(f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="13" font-weight="700" fill="{INK}">Series</text>')
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
        f'text-anchor="middle" transform="rotate(-90 18 {plot_y + plot_h / 2:.1f})">Value</text>'
    )

    # ---- lines + points ----
    for si, s in enumerate(series):
        pts = [(x_for(i), y_for(lookup.get((s, m), 0.0))) for i, m in enumerate(months)]
        path_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        parts.append(f'<g class="series-group s{si}">')
        parts.append(f'<path d="{path_d}" fill="none" stroke="{colors[s]}" stroke-width="2.5"/>')
        for i, m in enumerate(months):
            v = lookup.get((s, m), 0.0)
            cx, cy = x_for(i), y_for(v)
            tip = f"{s}, {m}: {v:.0f}"
            parts.append(
                f'<circle class="pt" tabindex="0" cx="{cx:.1f}" cy="{cy:.1f}" r="4" '
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
    for i, m in enumerate(months):
        parts.append(
            f'<text x="{x_for(i):.1f}" y="{axis_y + 20:.1f}" font-size="11" font-family="{FONT_MONO}" '
            f'fill="{SECONDARY}" text-anchor="middle">{xml_escape(m)}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{axis_y + 42:.1f}" font-size="13" '
        f'fill="{INK}" text-anchor="middle">Month</text>'
    )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_line(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Monthly Revenue by Product Line",
    subtitle: str = "Monthly figures, thousands of EUR",
    width: int = 845,
    height: int = 519,
    mode: str = "self-contained",
    accessibility: str = "universal",
) -> Path:
    """Render a hand-authored multi-series line chart and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``month`` (str), ``series`` (str), ``value`` (float).
        Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/line.svg``.
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
    >>> p = make_line()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility)
    dest = Path(out) if out else svg_example_path(__file__, "line")
    return write_svg(dest, svg)


def main() -> None:
    render_cli(__file__, "line", build_svg, description="Generate a multi-series line chart.")


if __name__ == "__main__":
    main()
