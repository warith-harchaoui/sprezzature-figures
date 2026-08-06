#!/usr/bin/env python3
"""
make_area — a house-styled stacked area chart as a hand-authored SVG.

Shows how a whole made of several categories evolves over an ordered axis,
emphasising both the total and each category's contribution. Typical uses:
traffic by acquisition channel over time, cumulative headcount by
department, resource usage by workload type.

Previously rendered via Vega-Lite (``vl_convert``); this module now stacks
the series itself and paints the bands by hand -- no Vega, no matplotlib.
Each band carries a native ``<title>`` tooltip on hover, and a pure-CSS
hover rule lifts the hovered band's opacity while dimming the rest.

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
CHANNELS = ["Direct", "Organic search", "Paid search", "Social"]

DEMO_DATA: List[Dict[str, Any]] = [
    {"month": m, "channel": c, "visits": v}
    for c, values in {
        "Organic search": [20, 22, 24, 25, 27, 29, 30, 32, 33, 35, 36, 38],
        "Paid search": [10, 11, 10, 12, 13, 12, 14, 15, 14, 16, 17, 18],
        "Social": [5, 6, 7, 9, 11, 13, 14, 16, 18, 19, 21, 23],
        "Direct": [8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13],
    }.items()
    for m, v in zip(MONTHS, values)
]


def _channel_colors(channels: List[str], accessibility: str = "universal") -> Dict[str, str]:
    palette = load_palette(accessibility)
    hues = [palette.get("Purple", "#AF52DE"), palette.get("Blue", "#007AFF"),
            palette.get("Orange", "#FF9500"), palette.get("Green", "#34C759")]
    return {ch: hues[i % len(hues)] for i, ch in enumerate(channels)}


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Website Traffic by Channel",
    subtitle: str = "Monthly visits, thousands",
    width: int = 845,
    height: int = 519,
    mode: str = "self-contained",
    accessibility: str = "universal",
) -> str:
    """Assemble the full stacked-area chart SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``month``, ``channel``, ``visits``. Defaults to
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
    # "channel" is an optional role (see catalog): rows may omit it entirely
    # (single unnamed series) or carry values outside the built-in demo set.
    seen: List[str] = []
    for r in rows:
        ch = r.get("channel", "")
        if ch not in seen:
            seen.append(ch)
    channels = [c for c in CHANNELS if c in seen] + [c for c in seen if c not in CHANNELS]
    months = sorted({r["month"] for r in rows}, key=lambda m: MONTHS.index(m) if m in MONTHS else 0)
    colors = _channel_colors(channels, accessibility)

    lookup: Dict[tuple, float] = {(r["month"], r.get("channel", "")): float(r["visits"]) for r in rows}
    # Cumulative stack, bottom-to-top in channel order, per month.
    cum: Dict[str, List[float]] = {m: [] for m in months}
    for m in months:
        running = 0.0
        for ch in channels:
            running += lookup.get((m, ch), 0.0)
            cum[m].append(running)
    totals = {m: cum[m][-1] if cum[m] else 0.0 for m in months}
    max_total = max(totals.values()) if totals else 1.0

    plot_x, plot_y = 60.0, 150.0
    right_margin, bottom_reserved = 30.0, 70.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved
    n = len(months)
    step = plot_w / max(n - 1, 1)

    def x_for(i: int) -> float:
        return plot_x + i * step

    def y_for(v: float) -> float:
        return plot_y + plot_h - (v / max_total * plot_h if max_total else 0.0)

    parts: List[str] = []
    parts.append(svg_open(width, height, "area-title", "area-desc"))
    parts.append(f'<title id="area-title">{xml_escape(title)}</title>')
    top_channel = channels[-1] if len(channels) > 1 else ""
    stack_note = f" {xml_escape(top_channel)} sits on top of the stack." if top_channel else ""
    parts.append(
        f'<desc id="area-desc">Stacked area chart of {len(channels)} channel'
        f'{"s" if len(channels) != 1 else ""} over {n} months, peaking at '
        f'{max_total:.0f} thousand visits.{stack_note}</desc>'
    )

    parts.append(
        "<style>"
        ".band{transition:opacity .15s ease;}"
        "svg:hover .band,svg:focus-within .band{opacity:.35;}"
        + "".join(
            f'svg:has(.band-{i}:hover,.band-{i}:focus) .band-{i}{{opacity:1;}}'
            for i in range(len(channels))
        )
        + "@media (prefers-reduced-motion: reduce){.band{transition:none;}}"
        "</style>"
    )

    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="40" y="46" font-size="24" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(f'<text x="40" y="70" font-size="14" fill="{SECONDARY}">{xml_escape(subtitle)}</text>')

    # ---- legend (top-left, below subtitle) ----
    # A single unnamed series needs no legend box -- the title already names it.
    if len(channels) > 1:
        lx = 40.0
        ly = 100.0
        parts.append(f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="13" font-weight="700" fill="{INK}">Channel</text>')
        cursor = lx
        ly2 = ly + 22
        for i, ch in enumerate(channels):
            parts.append(f'<circle cx="{cursor + 6:.1f}" cy="{ly2 - 5:.1f}" r="6" fill="{colors[ch]}"/>')
            parts.append(f'<text x="{cursor + 18:.1f}" y="{ly2:.1f}" font-size="12" fill="{INK}">{xml_escape(ch)}</text>')
            cursor += 18 + 7.2 * len(ch) + 22

    # ---- y-axis gridlines ----
    y_step = max_total / 4.0
    for i in range(5):
        val = i * y_step
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
        f'Visits (thousands)</text>'
    )

    # ---- stacked bands (bottom-to-top) ----
    for ci, ch in enumerate(channels):
        top_pts = [(x_for(i), y_for(cum[m][ci])) for i, m in enumerate(months)]
        bottom_val_key = ci - 1
        if bottom_val_key >= 0:
            bottom_pts = [(x_for(i), y_for(cum[m][bottom_val_key])) for i, m in enumerate(months)]
        else:
            bottom_pts = [(x_for(i), y_for(0.0)) for i in range(n)]
        path_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in top_pts)
        path_d += " L " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in reversed(bottom_pts)) + " Z"
        band_total = sum(lookup.get((m, ch), 0.0) for m in months)
        tip = f"{ch}: {band_total:.0f} thousand visits total over {n} months"
        parts.append(
            f'<path class="band band-{ci}" tabindex="0" d="{path_d}" '
            f'fill="{colors[ch]}" fill-opacity="0.82"><title>{xml_escape(tip)}</title></path>'
        )

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


def make_area(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Website Traffic by Channel",
    subtitle: str = "Monthly visits, thousands",
    width: int = 845,
    height: int = 519,
    mode: str = "self-contained",
    accessibility: str = "universal",
) -> Path:
    """Render a hand-authored stacked area chart and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``month`` (str), ``channel`` (str), ``visits`` (float).
        Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/area.svg``.
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
    >>> p = make_area()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility)
    dest = Path(out) if out else svg_example_path(__file__, "area")
    return write_svg(dest, svg)


def main() -> None:
    render_cli(__file__, "area", build_svg, description="Generate a stacked area chart.")


if __name__ == "__main__":
    main()
