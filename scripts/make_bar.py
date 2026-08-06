#!/usr/bin/env python3
"""
make_bar — a house-styled grouped bar chart as a hand-authored SVG.

The default chart type for comparing a numeric value across a handful of
categories. Typical uses: revenue by region, headcount by department,
survey scores by cohort.

Previously rendered via Vega-Lite (``vl_convert``); this module now builds
the ``<svg>`` markup by hand -- no Vega, no matplotlib -- so every bar
carries a native ``<title>`` tooltip and rounds only its free (top) end
per the Sprezzature Corner Policy.

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

CATEGORIES = ["North", "South", "East", "West"]

DEMO_DATA: List[Dict[str, Any]] = [
    {"region": "North", "value": 42},
    {"region": "South", "value": 28},
    {"region": "East", "value": 19},
    {"region": "West", "value": 11},
]


def _category_colors(accessibility: str = "universal") -> Dict[str, str]:
    palette = load_palette(accessibility)
    hues = [palette.get("Blue", "#007AFF"), palette.get("Orange", "#FF9500"),
            palette.get("Green", "#34C759"), palette.get("Purple", "#AF52DE")]
    return {cat: hues[i % len(hues)] for i, cat in enumerate(CATEGORIES)}


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Revenue by Region",
    subtitle: str = "Quarterly figures",
    width: int = 745,
    height: int = 505,
    mode: str = "self-contained",
    accessibility: str = "universal",
) -> str:
    """Assemble the full grouped bar chart SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``region`` (str) and ``value`` (numeric). Defaults
        to :data:`DEMO_DATA`.
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
    colors = _category_colors(accessibility)
    ordered = sorted(rows, key=lambda r: -float(r["value"]))
    total = sum(float(r["value"]) for r in rows) or 1.0
    max_val = max(float(r["value"]) for r in rows) if rows else 1.0

    plot_x, plot_y = 64.0, 118.0
    right_margin, bottom_reserved = 32.0, 70.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved
    n = len(ordered)
    bin_w = plot_w / n if n else plot_w
    bar_w = max(1.0, bin_w * 0.6)

    y_step = max_val / 4.0
    y_ticks = [i * y_step for i in range(5)]
    y_domain = y_ticks[-1] or 1.0

    def y_for(v: float) -> float:
        return plot_y + plot_h - (v / y_domain * plot_h)

    parts: List[str] = []
    parts.append(svg_open(width, height, "bar-title", "bar-desc"))
    parts.append(f'<title id="bar-title">{xml_escape(title)}</title>')
    top = ordered[0] if ordered else None
    peak_desc = (
        f" {top['region']} leads at {float(top['value']):.0f}, "
        f"{float(top['value']) / total * 100:.0f}% of the total."
        if top else ""
    )
    parts.append(
        f'<desc id="bar-desc">Bar chart of {n} categories, tallest {max_val:.0f}.'
        f'{peak_desc}</desc>'
    )

    parts.append(
        "<style>"
        ".bar{transition:filter .15s ease,transform .15s ease;"
        "transform-box:fill-box;transform-origin:bottom;}"
        ".bar:hover,.bar:focus{filter:brightness(1.08);transform:scaleY(1.015);outline:none;}"
        "@media (prefers-reduced-motion: reduce){.bar{transition:none;}"
        ".bar:hover,.bar:focus{transform:none;}}"
        "</style>"
    )

    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="40" y="56" font-size="26" font-weight="600" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(f'<text x="40" y="84" font-size="14" fill="{SECONDARY}">{xml_escape(subtitle)}</text>')

    for tick in y_ticks:
        ty = y_for(tick)
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{ty:.1f}" x2="{plot_x + plot_w:.1f}" y2="{ty:.1f}" '
            f'stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{ty + 4:.1f}" font-size="12" '
            f'font-family="{FONT_MONO}" fill="{SECONDARY}" text-anchor="end">{tick:.0f}</text>'
        )
    parts.append(
        f'<text x="24" y="{plot_y + plot_h / 2:.1f}" font-size="14" fill="{INK}" '
        f'text-anchor="middle" transform="rotate(-90 24 {plot_y + plot_h / 2:.1f})">Value</text>'
    )

    for i, row in enumerate(ordered):
        region = str(row["region"])
        value = float(row["value"])
        x = plot_x + i * bin_w + (bin_w - bar_w) / 2
        y = y_for(value)
        h = plot_y + plot_h - y
        r = corner_radius(bar_w, max(h, 1.0), "bar")
        share = value / total * 100.0
        tip = f"{region}: {value:.0f} ({share:.1f}% of total)"
        if h <= 0:
            continue
        path = bar_path(x, y, bar_w, h, r, side="top")
        parts.append(
            f'<path class="bar" tabindex="0" d="{path}" fill="{colors.get(region, "#007AFF")}">'
            f'<title>{xml_escape(tip)}</title></path>'
        )

    axis_y = plot_y + plot_h
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{axis_y:.1f}" x2="{plot_x + plot_w:.1f}" y2="{axis_y:.1f}" '
        f'stroke="{INK}" stroke-width="1.2"/>'
    )
    for i, row in enumerate(ordered):
        tx = plot_x + i * bin_w + bin_w / 2
        parts.append(
            f'<text x="{tx:.1f}" y="{axis_y + 20:.1f}" font-size="13" fill="{INK}" '
            f'text-anchor="middle">{xml_escape(str(row["region"]))}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{axis_y + 44:.1f}" font-size="14" '
        f'fill="{INK}" text-anchor="middle">Region</text>'
    )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_bar(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Revenue by Region",
    subtitle: str = "Quarterly figures",
    width: int = 745,
    height: int = 505,
    mode: str = "self-contained",
    accessibility: str = "universal",
) -> Path:
    """Render a hand-authored grouped bar chart and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``region`` (str) and ``value`` (float).
        Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/bar.svg``.
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
    >>> p = make_bar()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility)
    dest = Path(out) if out else svg_example_path(__file__, "bar")
    return write_svg(dest, svg)


def main() -> None:
    render_cli(__file__, "bar", build_svg, description="Generate a grouped bar chart.")


if __name__ == "__main__":
    main()
