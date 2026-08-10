#!/usr/bin/env python3
"""
make_bubble — publication-quality bubble chart as hand-authored SVG.

The classic Gapminder-style bubble chart: each point is one place, x is
GDP per capita, y is life expectancy, the bubble's *area* is population,
and colour marks the region. Replaces the Vega-Lite render this figure
used to ship as (``assets/vega-examples/bubble.vl.json``) -- house policy
is hand-authored SVG only (see ``no-matplotlib`` / no-new-Vega-Lite),
and the Vega-Lite version carried no per-point identity: every bubble
was anonymous, so hovering told a reader nothing beyond what the axes
already show. This version gives every bubble a name.

Data is synthetic and the place names are invented (not real countries)
so nothing here is mistakable for real economic or demographic
statistics attributed to a real place.

Interaction (no JavaScript): every bubble carries a native ``<title>``
tooltip naming the place, its region, and its three measures, plus a
pure-CSS ``:hover``/``:focus`` lift so the hovered bubble comes forward.

Running the module writes the SVG to
``sprezzature-figures/assets/svg-examples/bubble.svg``.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _scale import log_position, log_ticks  # noqa: E402
from _style import BG, FONT_MONO, GRIDLINE, INK, load_palette, os_adaptive_style, os_dark_style  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _svg import fmt_number, svg_open  # noqa: E402
from _interactive import fullscreen_control  # noqa: E402

WIDTH = 860
HEIGHT = 560
SUBINK = "#6E6E73"

FONT = "Roboto, system-ui, sans-serif"

REGION_ORDER: List[str] = ["Asia", "Europe", "Africa"]

# (name, gdp_per_capita_k$, life_expectancy_years, population_millions, region)
# Invented place names -- not real countries -- paired with the original
# synthetic gdp/life/pop values so every bubble now carries an identity a
# tooltip can name, without attaching real statistics to a real place.
PLACES: List[Tuple[str, float, float, float, str]] = [
    ("Veridara", 26.5, 66.7, 23.7, "Asia"),
    ("Nordholm", 47.9, 73.0, 72.9, "Europe"),
    ("Kalindra", 49.6, 74.8, 79.8, "Africa"),
    ("Sundaraq", 34.7, 66.8, 56.2, "Asia"),
    ("Vastergaard", 39.3, 74.1, 102.9, "Europe"),
    ("Serengara", 10.3, 57.0, 20.0, "Africa"),
    ("Kelanthir", 28.8, 74.5, 84.7, "Asia"),
    ("Kastellum", 43.0, 75.1, 105.7, "Europe"),
    ("Nubantu", 7.4, 56.2, 96.0, "Africa"),
    ("Baytoria", 40.5, 74.3, 16.8, "Asia"),
    ("Brennheim", 16.1, 59.6, 43.0, "Europe"),
    ("Mombeza", 44.9, 73.8, 124.7, "Africa"),
    ("Meridien East", 48.6, 74.0, 56.1, "Asia"),
    ("Ellisfjord", 28.1, 63.3, 62.3, "Europe"),
    ("Zanjira", 50.0, 75.4, 85.6, "Africa"),
    ("Northaven", 8.4, 60.2, 125.9, "Asia"),
    ("Marendal", 12.8, 55.5, 16.3, "Europe"),
    ("Tashenga", 30.6, 64.5, 16.5, "Africa"),
    ("Aureliss", 28.3, 74.2, 61.7, "Asia"),
    ("Corvath", 23.1, 68.2, 17.6, "Europe"),
    ("Okavelo", 32.7, 67.4, 87.2, "Africa"),
    ("Kestrelia", 52.8, 76.0, 79.9, "Asia"),
    ("Wyndemere", 34.1, 67.9, 41.2, "Europe"),
    ("Bantajo", 54.7, 88.3, 21.4, "Africa"),
    ("Thornmere", 39.4, 80.1, 37.0, "Asia"),
    ("Halbrecht", 34.4, 66.7, 54.4, "Europe"),
    ("Ilumira", 37.7, 74.9, 109.6, "Africa"),
    ("Solvangar", 6.6, 56.5, 121.6, "Asia"),
]


def _region_color(accessibility: str = "universal") -> Dict[str, str]:
    """Return the per-region fill colour at a given accessibility level.

    Parameters
    ----------
    accessibility : str, optional
        Palette accessibility level forwarded to :func:`_style.load_palette`.

    Returns
    -------
    dict of str to str
        ``{region_name: "#RRGGBB"}`` for the three regions.
    """
    palette = load_palette(accessibility)
    return {
        "Asia": palette.get("Blue", "#007AFF"),
        "Europe": palette.get("Orange", "#FF9500"),
        "Africa": palette.get("Green", "#34C759"),
    }


def _fmt1(v: float) -> str:
    """Format a float with exactly one decimal place."""
    return f"{v:.1f}"


# The make_<kind> contract's row-record view of PLACES: one row per place.
DEMO_DATA: List[Dict[str, Any]] = [
    {"name": name, "gdp": gdp, "life": life, "pop": pop, "region": region}
    for name, gdp, life, pop, region in PLACES
]


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    x_label: str = "GDP per capita (thousands of dollars)",
    y_label: str = "Life expectancy (years)",
    log_x: bool = False,
) -> str:
    """Assemble the full bubble-chart SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``name``, ``region`` (str) and ``gdp``, ``life``,
        ``pop`` (numeric) — see :data:`DEMO_DATA`. Defaults to a synthetic
        set of illustrative places.
    mode : str, optional
        Interactivity mode passed to :func:`_interactive.fullscreen_control`.
    accessibility : str, optional
        Palette accessibility level passed to :func:`_style.load_palette`.
    x_label, y_label : str, optional
        Axis titles.
    log_x : bool, optional
        Use a logarithmic GDP axis — the classic Gapminder convention,
        since income is the measure most likely to span orders of
        magnitude. No `log_y`: life expectancy is bounded to a narrow
        range and isn't a log-scale candidate.

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    region_color = _region_color(accessibility)
    places = data if data else DEMO_DATA

    gdps = [float(p["gdp"]) for p in places]
    lifes = [float(p["life"]) for p in places]
    pops = [float(p["pop"]) for p in places]
    gdp_min, gdp_max = min(gdps), max(gdps)
    life_min, life_max = min(lifes), max(lifes)
    pop_max = max(pops)

    plot_x, plot_y = 76.0, 132.0
    right_margin, bottom_reserved = 176.0, 70.0
    plot_w = WIDTH - plot_x - right_margin
    plot_h = HEIGHT - plot_y - bottom_reserved

    gdp_pad = (gdp_max - gdp_min) * 0.08
    life_pad = (life_max - life_min) * 0.10
    x0, x1 = gdp_min - gdp_pad, gdp_max + gdp_pad
    y0, y1 = life_min - life_pad, life_max + life_pad

    gdp_pos = [g for g in gdps if g > 0]
    xlog_min = min(gdp_pos) if gdp_pos else 1.0

    def x_for(gdp: float) -> float:
        if log_x and gdp > 0 and gdp_max > xlog_min:
            return log_position(gdp, xlog_min, gdp_max, plot_x, plot_x + plot_w)
        return plot_x + (gdp - x0) / (x1 - x0) * plot_w

    def y_for(life: float) -> float:
        return plot_y + plot_h - (life - y0) / (y1 - y0) * plot_h

    r_min, r_max = 5.0, 26.0

    def r_for(pop: float) -> float:
        return r_min + (r_max - r_min) * math.sqrt(max(pop, 0.0) / pop_max)

    title_txt = "Wealth, longevity, and population"
    subtitle_txt = "Synthetic sample · invented place names, not real countries"
    desc_txt = (
        f"Bubble chart of {len(places)} synthetic places. The horizontal axis is "
        "GDP per capita in thousands of dollars; the vertical axis is life "
        "expectancy in years; bubble area is population in millions; colour "
        "marks the region (Asia, Europe, Africa). Hover or focus a bubble for "
        "its name, region, and exact figures. Data and place names are "
        "invented, not real statistics."
    )

    parts: List[str] = []
    parts.append(svg_open(WIDTH, HEIGHT, "bub-title", "bub-desc", font_family=FONT))
    parts.append(f'<title id="bub-title">{escape(title_txt)}</title>')
    parts.append(f'<desc id="bub-desc">{escape(desc_txt)}</desc>')

    css: List[str] = [
        ".bubble{transition:opacity .15s ease,filter .15s ease;"
        "transform-box:fill-box;transform-origin:center;}",
        ".bubble:hover,.bubble:focus{filter:brightness(1.08);outline:none;}",
        ".bubble:hover circle,.bubble:focus circle{stroke-width:2.4;}",
        "@media (prefers-reduced-motion: reduce){.bubble{transition:none;}}",
    ]
    region_series = {f'circle[data-region="{reg}"]': col for reg, col in region_color.items()}
    css.append(os_adaptive_style(region_series, role="fill", forced=True))
    css.append(os_dark_style())
    parts.append("<style>" + "".join(css) + "</style>")

    parts.append(f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{BG}"/>')
    parts.append(
        f'<text x="40" y="46" font-size="24" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{escape(title_txt)}</text>'
    )
    parts.append(f'<text x="40" y="70" font-size="14" fill="{SUBINK}">{escape(subtitle_txt)}</text>')

    # ---- y-axis gridlines + labels ----
    y_ticks = 5
    for i in range(y_ticks + 1):
        life_val = y0 + (y1 - y0) * i / y_ticks
        ty = y_for(life_val)
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{ty:.1f}" x2="{plot_x + plot_w:.1f}" y2="{ty:.1f}" '
            f'stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{ty + 4:.1f}" font-size="11" '
            f'font-family="{FONT_MONO}" fill="{SUBINK}" text-anchor="end">{life_val:.0f}</text>'
        )
    parts.append(
        f'<text x="20" y="{plot_y + plot_h / 2:.1f}" font-size="13" fill="{INK}" '
        f'text-anchor="middle" transform="rotate(-90 20 {plot_y + plot_h / 2:.1f})">'
        f'{escape(y_label)}</text>'
    )

    # ---- x-axis ticks + labels ----
    axis_y = plot_y + plot_h
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{axis_y:.1f}" x2="{plot_x + plot_w:.1f}" y2="{axis_y:.1f}" '
        f'stroke="{INK}" stroke-width="1.2"/>'
    )
    if log_x:
        gdp_ticks = [d for d in log_ticks(xlog_min, gdp_max) if x0 <= d <= x1]
    else:
        gdp_ticks = [x0 + (x1 - x0) * i / 5 for i in range(6)]
    for gdp_val in gdp_ticks:
        tx = x_for(gdp_val)
        parts.append(
            f'<line x1="{tx:.1f}" y1="{axis_y:.1f}" x2="{tx:.1f}" y2="{axis_y + 6:.1f}" '
            f'stroke="{INK}" stroke-width="1"/>'
        )
        # fmt_number only for log ticks (decade values can be fractional);
        # the linear branch keeps its original :.0f} so the default render
        # is unchanged.
        tick_label = fmt_number(gdp_val) if log_x else f"{gdp_val:.0f}"
        parts.append(
            f'<text x="{tx:.1f}" y="{axis_y + 20:.1f}" font-size="11" font-family="{FONT_MONO}" '
            f'fill="{SUBINK}" text-anchor="middle">{tick_label}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{axis_y + 42:.1f}" font-size="13" '
        f'fill="{INK}" text-anchor="middle">{escape(x_label)}</text>'
    )

    # ---- bubbles, largest-first so small ones never hide under big ones ----
    ordered = sorted(places, key=lambda p: float(p["pop"]), reverse=True)
    for row in ordered:
        name, region = str(row["name"]), str(row["region"])
        gdp, life, pop = float(row["gdp"]), float(row["life"]), float(row["pop"])
        cx, cy = x_for(gdp), y_for(life)
        r = r_for(pop)
        color = region_color[region]
        tip = (
            f"{name} ({region}): life expectancy {_fmt1(life)} years, "
            f"GDP per capita ${gdp:.0f}k, population {_fmt1(pop)}M"
        )
        parts.append(
            f'<g class="bubble" tabindex="0" role="img" aria-label="{escape(tip)}">'
            f'<title>{escape(tip)}</title>'
            f'<circle data-region="{region}" cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" '
            f'fill="{color}" fill-opacity="0.72" stroke="{color}" stroke-width="1.2"/>'
            f'</g>'
        )

    # ---- region legend (top-right) ----
    leg_x = WIDTH - right_margin + 28
    leg_y = 132.0
    parts.append(
        f'<text x="{leg_x:.1f}" y="{leg_y:.1f}" font-size="13" font-weight="700" '
        f'fill="{INK}">Region</text>'
    )
    for i, region in enumerate(REGION_ORDER):
        ry = leg_y + 26 + i * 26
        parts.append(
            f'<circle cx="{leg_x + 7:.1f}" cy="{ry - 5:.1f}" r="7" '
            f'fill="{region_color[region]}" fill-opacity="0.85"/>'
        )
        parts.append(
            f'<text x="{leg_x + 20:.1f}" y="{ry:.1f}" font-size="13" fill="{INK}">{escape(region)}</text>'
        )

    # ---- population size legend (below region legend) ----
    size_leg_y = leg_y + 26 + len(REGION_ORDER) * 26 + 30
    parts.append(
        f'<text x="{leg_x:.1f}" y="{size_leg_y:.1f}" font-size="13" font-weight="700" '
        f'fill="{INK}">Population (M)</text>'
    )
    size_anchors = [pop_max, pop_max / 3]
    cursor_y = size_leg_y + 22
    for val in size_anchors:
        r = r_for(val)
        cy = cursor_y + r
        parts.append(
            f'<circle cx="{leg_x + r_max:.1f}" cy="{cy:.1f}" r="{r:.1f}" '
            f'fill="none" stroke="{SUBINK}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{leg_x + r_max * 2 + 10:.1f}" y="{cy + 4:.1f}" font-size="12" '
            f'font-family="{FONT_MONO}" fill="{SUBINK}">{val:.0f}</text>'
        )
        cursor_y = cy + r + 8

    parts.append(fullscreen_control(WIDTH, HEIGHT, mode))
    parts.append("</svg>")
    return "".join(parts)


def main() -> None:
    """Write the bubble-chart SVG to the skill's example asset folder."""
    render_cli(__file__, "bubble", build_svg, description="Render the bubble chart SVG.")


def make_bubble(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "",
    mode: str = "self-contained",
    accessibility: str = "universal",
    x_label: str = "GDP per capita (thousands of dollars)",
    y_label: str = "Life expectancy (years)",
    log_x: bool = False,
) -> Path:
    """Render the house-styled Gapminder-style bubble chart and write it to *out*.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``name``, ``region`` (str) and ``gdp``, ``life``,
        ``pop`` (numeric) — see :data:`DEMO_DATA`. Defaults to a synthetic
        set of illustrative places (invented names, not real countries).
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/bubble.svg``.
    title : str, optional
        Accepted for CLI/dispatcher parity; this figure's title stays fixed.
    mode, accessibility : str
        Forwarded to :func:`build_svg`.
    x_label, y_label : str, optional
        Axis titles. Forwarded to :func:`build_svg`.
    log_x : bool, optional
        Use a logarithmic GDP axis. Forwarded to :func:`build_svg`.

    Returns
    -------
    Path
        Absolute path to the written SVG file.

    Examples
    --------
    >>> p = make_bubble()
    >>> p.exists()
    True
    """
    _ = title
    svg = build_svg(data, mode=mode, accessibility=accessibility,
                     x_label=x_label, y_label=y_label, log_x=log_x)
    dest = Path(out) if out else svg_example_path(__file__, "bubble")
    return write_svg(dest, svg)


if __name__ == "__main__":
    main()
