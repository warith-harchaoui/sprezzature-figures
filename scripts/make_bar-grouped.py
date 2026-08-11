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
from _style import BG, GRIDLINE, INK, SECONDARY, corner_radius, cycle_hues  # noqa: E402
from _svg import bar_path, svg_open, xml_escape  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402


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

# Chrome text (title/subtitle/legend heading/axis titles/desc/tooltip
# templates) in the two languages Studio can ask for (studio/i18n.py detects
# the language from the imported CSV's column names; the CLI/library/API/MCP
# always call with the "en" default). Period/region names and numeric labels
# are never translated here -- they render exactly as the caller's data gives
# them.
_STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "title": "Sales by Region and Quarter",
        "subtitle": "Units sold per region, by quarter",
        "legend_heading": "Region",
        "axis_units": "Units",
        "axis_period": "Quarter",
        "desc_template": (
            "Grouped bar chart of {n_regions} regions across {n_periods} "
            "periods, peaking at {max_val:.0f}. Hover or focus a bar for its exact value."
        ),
        "tooltip_template": "{region}, {period}: {value:.0f}",
    },
    "fr": {
        "title": "Ventes par région et par trimestre",
        "subtitle": "Unités vendues par région, par trimestre",
        "legend_heading": "Région",
        "axis_units": "Unités",
        "axis_period": "Trimestre",
        "desc_template": (
            "Graphique à barres groupées de {n_regions} régions sur {n_periods} "
            "périodes, maximum {max_val:.0f}. Survolez ou activez une barre pour sa valeur exacte."
        ),
        "tooltip_template": "{region}, {period} : {value:.0f}",
    },
}


def _strings(language: str) -> Dict[str, str]:
    """Chrome-text dict for `language`, falling back to English."""
    return _STRINGS.get(language, _STRINGS["en"])


def _region_colors(
    regions: List[str], accessibility: str = "universal", theme: str = "corporate"
) -> Dict[str, str]:
    # Explicit hues (not cycle_hues' default Blue/Orange/Green/Purple order):
    # a grayscale-legibility fix. Orange (#FF9500, relative luminance ~161)
    # and Green (#28CD41, ~160) -- positions 2 and 3 of the default cycle,
    # adjacent bars in every group here -- collapse to the same shade once
    # desaturated. Blue/Brown/Yellow spread luminance ~106/68/200, so every
    # bar in a group stays distinguishable in grayscale.
    return cycle_hues(regions, accessibility, hues=['Blue', 'Brown', 'Yellow'], theme=theme)


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    width: int = 745,
    height: int = 505,
    mode: str = "self-contained",
    accessibility: str = "universal",
    language: str = "en",
    theme: str = "corporate",
) -> str:
    """Assemble the full grouped bar chart SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``period`` (str), ``region`` (str), ``v``
        (numeric). Defaults to :data:`DEMO_DATA`.
    title, subtitle : str or None
        Chart text. ``None`` (the default) falls back to `language`'s
        chrome default; an explicit string always wins regardless of
        `language`.
    width, height : int
        Canvas size in pixels.
    mode, accessibility : str, optional
        Forwarded to :func:`_interactive.fullscreen_control` /
        :func:`_style.load_palette`.
    language : str, optional
        Chrome-text language, ``"en"`` or ``"fr"``. Only title/subtitle
        defaults, the legend heading, axis titles, and the desc/tooltip
        wording switch; period/region names and numeric labels always
        render as given in `data`. Defaults to ``"en"``.
    theme : str, optional
        Visual theme: ``"corporate"`` (default, Roboto -- byte-identical to
        the pre-theme render) or ``"academic"`` (LaTeX-style Latin Modern).
        See :func:`sprezzature_figures.fonts.chrome_stack_for_theme`.

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    mono_family = mono_stack_for_theme(theme)
    strings = _strings(language)
    title = strings["title"] if title is None else title
    subtitle = strings["subtitle"] if subtitle is None else subtitle
    rows = data if data else DEMO_DATA
    seen_periods: List[str] = []
    for row in rows:
        if row["period"] not in seen_periods:
            seen_periods.append(row["period"])
    periods = [p for p in PERIODS if p in seen_periods] + [p for p in seen_periods if p not in PERIODS]
    # "region" may carry values outside the built-in demo set (REGIONS is only
    # the canonical ordering/colour preference, not an allowlist) -- keep the
    # canonical ones first for stable colours, then append whatever else the
    # data actually has, so no region silently disappears from the chart.
    seen_regions: List[str] = []
    for row in rows:
        if row["region"] not in seen_regions:
            seen_regions.append(row["region"])
    regions = [r for r in REGIONS if r in seen_regions] + [r for r in seen_regions if r not in REGIONS]
    colors = _region_colors(regions, accessibility, theme=theme)
    lookup: Dict[tuple, float] = {(r["period"], r["region"]): float(r["v"]) for r in rows}
    max_val = max(lookup.values()) if lookup else 1.0

    y_step = max_val / 4.0
    y_ticks = [i * y_step for i in range(5)]
    y_domain = y_ticks[-1] or 1.0

    plot_y = 150.0
    # 64px was sized for short (2-3 digit) tick numbers; imported data with
    # bigger values (5-6 digit revenue, say) would push the widest tick's
    # right-anchored text back over the rotated axis title, the same bug
    # found and fixed in make_bar.py. Widen it to the actual widest tick
    # (mono font, flat per-char estimate) plus room for that title.
    max_tick_chars = max((len(f"{t:.0f}") for t in y_ticks), default=1)
    tick_label_w = max_tick_chars * 12 * 0.62
    plot_x = max(64.0, 10 + tick_label_w + 24)
    right_margin, bottom_reserved = 32.0, 70.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved
    n_periods = len(periods)
    n_regions = len(regions)
    bin_w = plot_w / n_periods if n_periods else plot_w
    group_w = bin_w * 0.78
    bar_w = group_w / n_regions if n_regions else group_w

    def y_for(v: float) -> float:
        return plot_y + plot_h - (v / y_domain * plot_h)

    parts: List[str] = []
    parts.append(svg_open(width, height, "bg-title", "bg-desc", font_family=chrome_stack_for_theme(theme)))
    parts.append(f'<title id="bg-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="bg-desc">{strings["desc_template"].format(n_regions=n_regions, n_periods=n_periods, max_val=max_val)}</desc>'
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
    parts.append(f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="13" font-weight="700" fill="{INK}">{xml_escape(strings["legend_heading"])}</text>')
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
            f'<text x="{plot_x - 10:.1f}" y="{ty + 4:.1f}" font-size="12" font-family="{mono_family}" '
            f'fill="{SECONDARY}" text-anchor="end">{tick:.0f}</text>'
        )
    axis_units_x = 18.0
    axis_units_y = plot_y + plot_h / 2
    parts.append(
        f'<text x="{axis_units_x:.1f}" y="{axis_units_y:.1f}" font-size="13" fill="{INK}" '
        f'text-anchor="middle" transform="rotate(-90 {axis_units_x:.1f} {axis_units_y:.1f})">'
        f'{xml_escape(strings["axis_units"])}</text>'
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
            tip = strings["tooltip_template"].format(region=region, period=period, value=value)
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
        f'fill="{INK}" text-anchor="middle">{xml_escape(strings["axis_period"])}</text>'
    )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_bar_grouped(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    width: int = 745,
    height: int = 505,
    mode: str = "self-contained",
    accessibility: str = "universal",
    language: str = "en",
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored grouped bar chart and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``period`` (str), ``region`` (str), ``v`` (float).
        Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/bar-grouped.svg``.
    title, subtitle : str or None
        Chart text. ``None`` falls back to `language`'s chrome default.
    width, height : int
        Canvas size in pixels.
    mode, accessibility : str
        Forwarded to :func:`build_svg`.
    language : str, optional
        Chrome-text language, ``"en"`` or ``"fr"``. Defaults to ``"en"``;
        Sprezzature Studio passes the language detected from the imported
        CSV's column names (see :data:`_STRINGS`).
    theme : str, optional
        Visual theme. Forwarded to :func:`build_svg`.

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
                     mode=mode, accessibility=accessibility, language=language, theme=theme)
    dest = Path(out) if out else svg_example_path(__file__, "bar-grouped")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "bar-grouped", build_svg, description="Generate a grouped (clustered) bar chart.")


if __name__ == "__main__":
    main()
