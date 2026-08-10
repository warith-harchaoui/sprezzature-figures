#!/usr/bin/env python3
"""
make_columnrange — a house-styled range (floating bar) chart as hand-authored SVG.

A column-range chart, also called a floating bar or range chart, draws a
vertical bar for each category from a low value to a high value rather than
from zero to a single value. It communicates an interval, not an absolute
quantity. Typical uses: temperature ranges by month, confidence intervals
for survey estimates, salary bands by role, and any situation where the
viewer needs to compare spans rather than point values.

Previously rendered via Vega-Lite (``vl_convert``); this module now builds
the ``<svg>`` markup by hand -- no Vega, no matplotlib -- so every floating
bar carries a native ``<title>`` tooltip and rounds both free ends per the
Sprezzature Corner Policy (a range bar has no baseline, both ends are free).

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
from _style import BG, FONT_MONO, GRIDLINE, INK, SECONDARY, cycle_hues, load_palette  # noqa: E402
from _svg import svg_open, xml_escape  # noqa: E402


MONTHS = ["Jan", "Apr", "Jul", "Oct"]
CITIES = ["Madrid", "Berlin", "Lisbon", "Stockholm", "Athens"]

DEMO_DATA: List[Dict[str, Any]] = [
    {"city": "Madrid", "month": "Jan", "low": 2, "high": 11, "sort": 1},
    {"city": "Madrid", "month": "Apr", "low": 8, "high": 18, "sort": 4},
    {"city": "Madrid", "month": "Jul", "low": 18, "high": 33, "sort": 7},
    {"city": "Madrid", "month": "Oct", "low": 10, "high": 21, "sort": 10},
    {"city": "Berlin", "month": "Jan", "low": -3, "high": 3, "sort": 1},
    {"city": "Berlin", "month": "Apr", "low": 4, "high": 14, "sort": 4},
    {"city": "Berlin", "month": "Jul", "low": 14, "high": 24, "sort": 7},
    {"city": "Berlin", "month": "Oct", "low": 6, "high": 14, "sort": 10},
    {"city": "Lisbon", "month": "Jan", "low": 8, "high": 15, "sort": 1},
    {"city": "Lisbon", "month": "Apr", "low": 12, "high": 21, "sort": 4},
    {"city": "Lisbon", "month": "Jul", "low": 19, "high": 29, "sort": 7},
    {"city": "Lisbon", "month": "Oct", "low": 14, "high": 23, "sort": 10},
    {"city": "Stockholm", "month": "Jan", "low": -5, "high": 1, "sort": 1},
    {"city": "Stockholm", "month": "Apr", "low": 2, "high": 11, "sort": 4},
    {"city": "Stockholm", "month": "Jul", "low": 13, "high": 22, "sort": 7},
    {"city": "Stockholm", "month": "Oct", "low": 4, "high": 10, "sort": 10},
    {"city": "Athens", "month": "Jan", "low": 6, "high": 14, "sort": 1},
    {"city": "Athens", "month": "Apr", "low": 11, "high": 22, "sort": 4},
    {"city": "Athens", "month": "Jul", "low": 22, "high": 34, "sort": 7},
    {"city": "Athens", "month": "Oct", "low": 15, "high": 25, "sort": 10},
]


def _city_colors(cities: List[str], accessibility: str = "universal") -> Dict[str, str]:
    return cycle_hues(cities, accessibility, hues=['Blue', 'Purple', 'Green', 'Orange', 'Red'])


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Monthly Temperature Range by City",
    subtitle: str = "Mean daily low to mean daily high, degrees Celsius, 30-year climate normal",
    width: int = 845,
    height: int = 519,
    mode: str = "self-contained",
    accessibility: str = "universal",
) -> str:
    """Assemble the full column-range chart SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``city``, ``month``, ``low``, ``high``. Defaults to
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
    seen_cities: List[str] = []
    for r in rows:
        if r["city"] not in seen_cities:
            seen_cities.append(r["city"])
    cities = [c for c in CITIES if c in seen_cities] + [c for c in seen_cities if c not in CITIES]
    months = sorted({r["month"] for r in rows}, key=lambda m: MONTHS.index(m) if m in MONTHS else 0)
    colors = _city_colors(cities, accessibility)

    lookup: Dict[tuple, tuple] = {(r["city"], r["month"]): (float(r["low"]), float(r["high"])) for r in rows}
    lows = [v[0] for v in lookup.values()]
    highs = [v[1] for v in lookup.values()]
    y_min, y_max = min(lows), max(highs)
    pad = (y_max - y_min) * 0.08
    y0, y1 = y_min - pad, y_max + pad

    plot_x, plot_y = 60.0, 150.0
    right_margin, bottom_reserved = 30.0, 70.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved
    n_groups = len(months)
    group_w = plot_w / n_groups if n_groups else plot_w
    bar_w = max(3.0, group_w / (len(cities) + 1.4))

    def y_for(v: float) -> float:
        return plot_y + plot_h - (v - y0) / (y1 - y0) * plot_h

    parts: List[str] = []
    parts.append(svg_open(width, height, "cr-title", "cr-desc"))
    parts.append(f'<title id="cr-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="cr-desc">Floating-bar range chart of {len(cities)} cities across '
        f'{n_groups} months, each bar spanning its mean daily low to mean daily high '
        f'in degrees Celsius. Range: {y_min:.0f} to {y_max:.0f}.</desc>'
    )

    parts.append(
        "<style>"
        ".rangebar{transition:filter .15s ease;}"
        ".rangebar:hover,.rangebar:focus{filter:brightness(1.1);outline:none;}"
        "@media (prefers-reduced-motion: reduce){.rangebar{transition:none;}}"
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
    parts.append(f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="13" font-weight="700" fill="{INK}">City</text>')
    cursor = lx
    ly2 = ly + 22
    for c in cities:
        parts.append(
            f'<rect x="{cursor:.1f}" y="{ly2 - 11:.1f}" width="12" height="12" rx="2" fill="{colors[c]}"/>'
        )
        parts.append(f'<text x="{cursor + 18:.1f}" y="{ly2:.1f}" font-size="12" fill="{INK}">{xml_escape(c)}</text>')
        cursor += 18 + 7.2 * len(c) + 20

    # ---- y-axis gridlines ----
    y_ticks = 6
    y_step = (y1 - y0) / y_ticks
    for i in range(y_ticks + 1):
        val = y0 + i * y_step
        ty = y_for(val)
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{ty:.1f}" x2="{plot_x + plot_w:.1f}" y2="{ty:.1f}" '
            f'stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{ty + 4:.1f}" font-size="11" font-family="{FONT_MONO}" '
            f'fill="{SECONDARY}" text-anchor="end">{val:.0f}</text>'
        )
    parts.append(
        f'<text x="18" y="{plot_y + plot_h / 2:.1f}" font-size="13" fill="{INK}" '
        f'text-anchor="middle" transform="rotate(-90 18 {plot_y + plot_h / 2:.1f})">'
        f'Temperature (°C)</text>'
    )

    # ---- floating bars, grouped by month ----
    for gi, m in enumerate(months):
        group_x0 = plot_x + gi * group_w
        offset0 = (group_w - bar_w * len(cities)) / 2
        for ci, c in enumerate(cities):
            low, high = lookup.get((c, m), (0.0, 0.0))
            x = group_x0 + offset0 + ci * bar_w
            y_top, y_bot = y_for(high), y_for(low)
            h = max(1.0, y_bot - y_top)
            r = min(bar_w / 2.0, 4.0)
            tip = f"{c}, {m}: {low:.0f}°C to {high:.0f}°C"
            parts.append(
                f'<rect class="rangebar" tabindex="0" x="{x:.1f}" y="{y_top:.1f}" '
                f'width="{bar_w:.1f}" height="{h:.1f}" rx="{r:.1f}" '
                f'fill="{colors[c]}" fill-opacity="0.85"><title>{xml_escape(tip)}</title></rect>'
            )

    # ---- x-axis (month group labels) ----
    axis_y = plot_y + plot_h
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{axis_y:.1f}" x2="{plot_x + plot_w:.1f}" y2="{axis_y:.1f}" '
        f'stroke="{INK}" stroke-width="1.2"/>'
    )
    for gi, m in enumerate(months):
        tx = plot_x + gi * group_w + group_w / 2
        parts.append(
            f'<text x="{tx:.1f}" y="{axis_y + 20:.1f}" font-size="13" fill="{INK}" '
            f'text-anchor="middle">{xml_escape(m)}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{axis_y + 44:.1f}" font-size="13" '
        f'fill="{INK}" text-anchor="middle">Month</text>'
    )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_columnrange(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Monthly Temperature Range by City",
    subtitle: str = "Mean daily low to mean daily high, degrees Celsius, 30-year climate normal",
    width: int = 845,
    height: int = 519,
    mode: str = "self-contained",
    accessibility: str = "universal",
) -> Path:
    """Render a hand-authored column-range chart and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``city``, ``month``, ``low``, ``high``. Defaults to
        DEMO_DATA (European city temperature ranges).
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/columnrange.svg``.
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
    >>> p = make_columnrange()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility)
    dest = Path(out) if out else svg_example_path(__file__, "columnrange")
    return write_svg(dest, svg)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "columnrange", build_svg, description="Generate a column-range (floating bar) chart.")


if __name__ == "__main__":
    main()
