#!/usr/bin/env python3
"""
make_bar-grouped — a house-styled grouped (clustered) bar chart as hand-authored SVG.

Compares a numeric value across two categorical dimensions at once: an
outer axis (e.g. a time period) holds a cluster of bars, one per inner
category (e.g. a region), placed side by side and colour-coded. Reads
easier than a single stacked bar when the reader needs to compare both
the sub-category totals within a period AND each sub-category's trend
across periods. Typical uses: sales by region and quarter, survey scores
by cohort and year, headcount by department and site.

Previously rendered via Vega-Lite (``x`` + ``xOffset`` encoding,
``vl_convert``); this module now computes the two-level band layout
itself and paints each bar by hand -- no Vega, no matplotlib. Every bar
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
from _style import corner_radius, load_palette  # noqa: E402
from _svg import bar_path, svg_open, xml_escape  # noqa: E402

INK = "#1D1D1F"
SECONDARY = "#6E6E73"
BG = "#FFFFFF"
GRIDLINE = "#E5E5EA"
FONT_MONO = "Roboto Mono, ui-monospace, monospace"

PERIODS = ["Q1", "Q2", "Q3", "Q4"]
REGIONS = ["North", "South", "East"]

DEMO_DATA: List[Dict[str, Any]] = [
    {"period": "Q1", "region": "North", "v": 42}, {"period": "Q1", "region": "South", "v": 55},
    {"period": "Q1", "region": "East", "v": 30}, {"period": "Q2", "region": "North", "v": 65},
    {"period": "Q2", "region": "South", "v": 48}, {"period": "Q2", "region": "East", "v": 38},
    {"period": "Q3", "region": "North", "v": 71}, {"period": "Q3", "region": "South", "v": 52},
    {"period": "Q3", "region": "East", "v": 44}, {"period": "Q4", "region": "North", "v": 58},
    {"period": "Q4", "region": "South", "v": 40}, {"period": "Q4", "region": "East", "v": 33},
]


def _region_colors(accessibility: str = "universal") -> Dict[str, str]:
    palette = load_palette(accessibility)
    hues = [palette.get("Blue", "#007AFF"), palette.get("Orange", "#FF9500"),
            palette.get("Green", "#34C759"), palette.get("Purple", "#AF52DE")]
    return {r: hues[i % len(hues)] for i, r in enumerate(REGIONS)}


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Sales by Region and Quarter",
    subtitle: str = "Units sold per region, by quarter",
    width: int = 745,
    height: int = 505,
    mode: str = "self-contained",
    accessibility: str = "universal",
) -> str:
    """Assemble the full grouped bar chart SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``period`` (str), ``region`` (str), ``v``
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
    periods = [p for p in PERIODS if any(r["period"] == p for r in rows)] or sorted({r["period"] for r in rows})
    regions = [r for r in REGIONS if any(row["region"] == r for row in rows)] or sorted({r["region"] for r in rows})
    colors = _region_colors(accessibility)
    lookup: Dict[tuple, float] = {(r["period"], r["region"]): float(r["v"]) for r in rows}
    max_val = max(lookup.values()) if lookup else 1.0

    plot_x, plot_y = 64.0, 150.0
    right_margin, bottom_reserved = 32.0, 70.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved
    n_periods = len(periods)
    n_regions = len(regions)
    bin_w = plot_w / n_periods if n_periods else plot_w
    group_w = bin_w * 0.78
    bar_w = group_w / n_regions if n_regions else group_w

    y_step = max_val / 4.0
    y_ticks = [i * y_step for i in range(5)]
    y_domain = y_ticks[-1] or 1.0

    def y_for(v: float) -> float:
        return plot_y + plot_h - (v / y_domain * plot_h)

    parts: List[str] = []
    parts.append(svg_open(width, height, "bg-title", "bg-desc"))
    parts.append(f'<title id="bg-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="bg-desc">Grouped bar chart of {n_regions} regions across {n_periods} '
        f'periods, peaking at {max_val:.0f}. Hover or focus a bar for its exact value.</desc>'
    )
    parts.append(
        "<style>"
        ".bar{transition:filter .15s ease;}"
        ".bar:hover,.bar:focus{filter:brightness(1.08);outline:none;}"
        "@media (prefers-reduced-motion: reduce){.bar{transition:none;}}"
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
    parts.append(f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="13" font-weight="700" fill="{INK}">Region</text>')
    cursor = lx
    ly2 = ly + 22
    for reg in regions:
        parts.append(f'<rect x="{cursor:.1f}" y="{ly2 - 12:.1f}" width="14" height="14" rx="3" fill="{colors[reg]}"/>')
        parts.append(f'<text x="{cursor + 20:.1f}" y="{ly2:.1f}" font-size="12" fill="{INK}">{xml_escape(reg)}</text>')
        cursor += 20 + 7.0 * len(reg) + 22

    # ---- y-axis gridlines ----
    for tick in y_ticks:
        ty = y_for(tick)
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{ty:.1f}" x2="{plot_x + plot_w:.1f}" y2="{ty:.1f}" '
            f'stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{ty + 4:.1f}" font-size="12" font-family="{FONT_MONO}" '
            f'fill="{SECONDARY}" text-anchor="end">{tick:.0f}</text>'
        )
    parts.append(
        f'<text x="18" y="{plot_y + plot_h / 2:.1f}" font-size="13" fill="{INK}" '
        f'text-anchor="middle" transform="rotate(-90 18 {plot_y + plot_h / 2:.1f})">Units</text>'
    )

    # ---- bars ----
    for pi, period in enumerate(periods):
        group_x = plot_x + pi * bin_w + (bin_w - group_w) / 2
        for ri, region in enumerate(regions):
            value = lookup.get((period, region), 0.0)
            x = group_x + ri * bar_w
            y = y_for(value)
            h = plot_y + plot_h - y
            if h <= 0:
                continue
            r = corner_radius(bar_w, h, "bar")
            tip = f"{region}, {period}: {value:.0f}"
            path = bar_path(x, y, bar_w * 0.88, h, r, side="top")
            parts.append(
                f'<path class="bar" tabindex="0" d="{path}" fill="{colors.get(region, "#007AFF")}">'
                f'<title>{xml_escape(tip)}</title></path>'
            )

    # ---- x-axis ----
    axis_y = plot_y + plot_h
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{axis_y:.1f}" x2="{plot_x + plot_w:.1f}" y2="{axis_y:.1f}" '
        f'stroke="{INK}" stroke-width="1.2"/>'
    )
    for pi, period in enumerate(periods):
        tx = plot_x + pi * bin_w + bin_w / 2
        parts.append(
            f'<text x="{tx:.1f}" y="{axis_y + 20:.1f}" font-size="13" fill="{INK}" '
            f'text-anchor="middle">{xml_escape(period)}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{axis_y + 44:.1f}" font-size="13" '
        f'fill="{INK}" text-anchor="middle">Quarter</text>'
    )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_bar_grouped(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Sales by Region and Quarter",
    subtitle: str = "Units sold per region, by quarter",
    width: int = 745,
    height: int = 505,
    mode: str = "self-contained",
    accessibility: str = "universal",
) -> Path:
    """Render a hand-authored grouped bar chart and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``period`` (str), ``region`` (str), ``v`` (float).
        Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/bar-grouped.svg``.
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
    >>> p = make_bar_grouped()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility)
    dest = Path(out) if out else svg_example_path(__file__, "bar-grouped")
    return write_svg(dest, svg)


def main() -> None:
    render_cli(__file__, "bar-grouped", build_svg, description="Generate a grouped (clustered) bar chart.")


if __name__ == "__main__":
    main()
