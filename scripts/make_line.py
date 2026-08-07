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

# Chrome text (Studio detects "en"/"fr" from the imported CSV's column
# names; the CLI/library/API/MCP default to "en"). Title/subtitle are
# already caller-supplied strings (Studio always passes an explicit
# `title=`), so only this generator's own fixed labels need a translation:
# the legend header, the two axis titles, and the accessible <desc>
# template. Series/month/value labels always come from the caller's data
# and are never translated here.
_STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "legend_header": "Series",
        "y_axis": "Value",
        "x_axis": "Month",
        "desc": "Multi-series line chart of {n_series} series over {n_months} months, "
                "peaking at {max_val:.0f}. Hover or focus a point for its exact value.",
    },
    "fr": {
        "legend_header": "Séries",
        "y_axis": "Valeur",
        "x_axis": "Mois",
        "desc": "Graphique en courbes de {n_series} séries sur {n_months} mois, "
                "culminant à {max_val:.0f}. Survolez ou activez le focus sur un "
                "point pour sa valeur exacte.",
    },
}


def _strings(language: str) -> Dict[str, str]:
    """Chrome-text dict for `language`, falling back to English."""
    return _STRINGS.get(language, _STRINGS["en"])


def _series_colors(series: List[str], accessibility: str = "universal") -> Dict[str, str]:
    palette = load_palette(accessibility)
    hues = [palette.get("Blue", "#007AFF"), palette.get("Orange", "#FF9500"),
            palette.get("Green", "#34C759"), palette.get("Purple", "#AF52DE")]
    return {s: hues[i % len(hues)] for i, s in enumerate(series)}


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Monthly Revenue by Product Line",
    subtitle: str = "Monthly figures, thousands of EUR",
    width: int = 845,
    height: int = 519,
    mode: str = "self-contained",
    accessibility: str = "universal",
    language: str = "en",
) -> str:
    """Assemble the full multi-series line chart SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``month``, ``value``, and optionally ``series``
        (rows without it are treated as one series named "Value", and the
        legend is skipped since a single line doesn't need to label
        itself). Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    mode, accessibility : str, optional
        Forwarded to :func:`_interactive.fullscreen_control` /
        :func:`_style.load_palette`.
    language : str, optional
        Chrome-text language, ``"en"`` or ``"fr"`` (see :data:`_STRINGS`).
        Only this generator's own fixed labels switch; `title`/`subtitle`
        and every data-derived label render exactly as given regardless of
        `language`. Defaults to ``"en"``.

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    strings = _strings(language)
    rows = data if data else DEMO_DATA
    # "series" is an optional role (single-line data is a normal, valid
    # input): default absent/blank values to one constant series name rather
    # than a bare ``r["series"]`` lookup, which raised a raw KeyError for
    # every dataset that only bound the two required roles (month, value).
    seen_series: List[str] = []
    for r in rows:
        s = r.get("series") or "Value"
        if s not in seen_series:
            seen_series.append(s)
    series = [s for s in SERIES if s in seen_series] + [s for s in seen_series if s not in SERIES]
    # Preserve the rows' own order for axis labels that aren't the canonical
    # Jan..Dec demo set (e.g. ISO dates): sorting a *set* of such labels by
    # "MONTHS.index if present else 0" ties every one of them at key 0, so
    # the axis order silently fell back to Python's set-hash order instead of
    # the CSV's already-chronological row order.
    months_seen = list(dict.fromkeys(r["month"] for r in rows))
    months = sorted(months_seen, key=MONTHS.index) if all(m in MONTHS for m in months_seen) else months_seen
    colors = _series_colors(series, accessibility)

    lookup: Dict[tuple, float] = {(r.get("series") or "Value", r["month"]): float(r["value"]) for r in rows}
    all_vals = list(lookup.values())
    max_val = max(all_vals) if all_vals else 1.0

    plot_x, plot_y = 60.0, 150.0
    # The last x-axis tick label is centred (text-anchor="middle") on the
    # rightmost plot point, so half its width overflows past plot_x+plot_w;
    # a fixed 30px margin (enough for "Dec") clipped a wider custom label
    # such as an ISO date ("2025-12-01"). Size the margin off the actual
    # widest label instead (Roboto Mono at 11px, ~0.62em/char, same estimate
    # used in make_bar3d.py's legend fix).
    widest_month_px = max((len(str(m)) for m in months), default=0) * 11 * 0.62
    right_margin = max(30.0, widest_month_px / 2 + 12)
    plot_w = width - plot_x - right_margin
    n = len(months)
    step = plot_w / max(n - 1, 1)
    # Horizontal, centred labels ("Jan", "Feb", ...) fit fine at typical tick
    # spacing, but a longer custom label (an ISO date) at the same spacing
    # overlaps its neighbours -- not just the last one clipping the canvas
    # edge, every adjacent pair touches. Once a label would be wider than the
    # gap between ticks, angle them 45deg instead, which needs more vertical
    # room at the bottom.
    rotate_ticks = widest_month_px + 6 > step
    bottom_reserved = 96.0 if rotate_ticks else 70.0
    plot_h = height - plot_y - bottom_reserved

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
        f'<desc id="line-desc">'
        f'{strings["desc"].format(n_series=len(series), n_months=n, max_val=max_val)}'
        f'</desc>'
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

    # ---- legend (a single-series line doesn't need one to label itself) ----
    if len(series) > 1:
        lx, ly = 40.0, 100.0
        parts.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="13" font-weight="700" '
            f'fill="{INK}">{strings["legend_header"]}</text>'
        )
        cursor = lx
        ly2 = ly + 22
        for s in series:
            parts.append(
                f'<line x1="{cursor:.1f}" y1="{ly2 - 5:.1f}" x2="{cursor + 16:.1f}" y2="{ly2 - 5:.1f}" '
                f'stroke="{colors[s]}" stroke-width="2.5"/>'
            )
            parts.append(
                f'<text x="{cursor + 22:.1f}" y="{ly2:.1f}" font-size="12" fill="{INK}">{xml_escape(s)}</text>'
            )
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
        f'text-anchor="middle" transform="rotate(-90 18 {plot_y + plot_h / 2:.1f})">{strings["y_axis"]}</text>'
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
        tx, ty = x_for(i), axis_y + 20
        if rotate_ticks:
            parts.append(
                f'<text x="{tx:.1f}" y="{ty:.1f}" font-size="11" font-family="{FONT_MONO}" '
                f'fill="{SECONDARY}" text-anchor="end" '
                f'transform="rotate(-45 {tx:.1f} {ty:.1f})">{xml_escape(m)}</text>'
            )
        else:
            parts.append(
                f'<text x="{tx:.1f}" y="{ty:.1f}" font-size="11" font-family="{FONT_MONO}" '
                f'fill="{SECONDARY}" text-anchor="middle">{xml_escape(m)}</text>'
            )
    axis_title_y = axis_y + (76 if rotate_ticks else 42)
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{axis_title_y:.1f}" font-size="13" '
        f'fill="{INK}" text-anchor="middle">{strings["x_axis"]}</text>'
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
    language: str = "en",
) -> Path:
    """Render a hand-authored multi-series line chart and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``month`` (str), ``value`` (float), and optionally
        ``series`` (str). Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/line.svg``.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    mode, accessibility, language : str
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
                     mode=mode, accessibility=accessibility, language=language)
    dest = Path(out) if out else svg_example_path(__file__, "line")
    return write_svg(dest, svg)


def main() -> None:
    render_cli(__file__, "line", build_svg, description="Generate a multi-series line chart.")


if __name__ == "__main__":
    main()
