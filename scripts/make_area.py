#!/usr/bin/env python3
"""
make_area — a house-styled stacked area chart as a hand-authored SVG.

Shows how a whole made of several categories evolves over an ordered axis,
emphasising both the total and each category's contribution. Typical uses:
traffic by acquisition channel over time, cumulative headcount by
department, resource usage by workload type.

Previously rendered via Vega-Lite (``vl_convert``); this module now stacks
the series itself and paints the bands by hand, not with Vega or matplotlib.
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
from _scale import log_position, log_ticks, nice_ticks  # noqa: E402
from _style import BG, GRIDLINE, INK, SECONDARY, cycle_hues  # noqa: E402
from _svg import fmt_number, foreground_tip_css, svg_open, tooltip_bubble, xml_escape  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402


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


def _channel_colors(
    channels: List[str], accessibility: str = "universal", theme: str = "corporate"
) -> Dict[str, str]:
    # Brown/Blue/Yellow/Green (not the more obvious Purple/Blue/Orange/Green):
    # a grayscale-legibility fix. The original two adjacent stack pairs
    # (Purple #AF52DE ~lum 112 vs Blue #007AFF ~lum 106, and Orange #FF9500
    # ~lum 161 vs Green #28CD41 ~lum 160) collapse to the same shade once
    # desaturated -- caught by the grayscale pass of the Ralph Eyeball Loop.
    # This set's adjacent-band luminance gaps are all >=38, so every band
    # boundary stays visible in grayscale.
    return cycle_hues(channels, accessibility, hues=['Brown', 'Blue', 'Yellow', 'Green'], theme=theme)


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Website Traffic by Channel",
    subtitle: str = "Monthly visits, thousands",
    width: int = 845,
    height: int = 519,
    mode: str = "self-contained",
    accessibility: str = "universal",
    x_label: str = "Month",
    y_label: str = "Visits (thousands)",
    log_y: bool = False,
    theme: str = "corporate",
    legend_title: str = "Channel",
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
    x_label, y_label : str, optional
        Axis titles.
    log_y : bool, optional
        Use a logarithmic total-visits axis. The x-axis (month) is ordinal,
        not a numeric quantity, so it has no log form. Note that on a
        stacked chart, log spacing distorts each band's apparent thickness
        relative to its actual share — this is meant for reading the
        *total*'s growth, not for comparing band sizes by eye.
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
    colors = _channel_colors(channels, accessibility, theme=theme)

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

    if log_y:
        pos_totals = [v for v in totals.values() if v > 0]
        min_pos = min(pos_totals) if pos_totals else 1.0
        y_ticks = log_ticks(min_pos, max_total)
        y_lo, y_hi = y_ticks[0], y_ticks[-1]

        def y_for(v: float) -> float:
            return log_position(v, y_lo, y_hi, plot_y + plot_h, plot_y)
    else:
        # Round the axis ceiling up to a "nice" number (nice_ticks) instead of
        # scaling to the raw peak -- see _scale.nice_ticks. y_domain (>= max_total)
        # is what the fill actually scales against, so the gridlines drawn
        # below from the same tick list always land on the plot's top edge.
        y_ticks = nice_ticks(max_total)
        y_domain = y_ticks[-1] or 1.0

        def y_for(v: float) -> float:
            return plot_y + plot_h - (v / y_domain * plot_h if y_domain else 0.0)

    parts: List[str] = []
    parts.append(svg_open(width, height, "area-title", "area-desc", font_family=chrome_stack_for_theme(theme)))
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
        + ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        # A bubble drawn right next to its own band would be covered by any
        # band drawn afterward (SVG paints in document order, regardless of
        # hover) -- bands draw first, bubbles last, paired by id; see
        # _svg.foreground_tip_css.
        + foreground_tip_css(len(channels), mark_prefix="band-hit", tip_prefix="band-tip")
        + "@media (prefers-reduced-motion:reduce){.tip{transition:none}}"
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
        parts.append(f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="13" font-weight="700" fill="{INK}">{xml_escape(legend_title)}</text>')
        cursor = lx
        ly2 = ly + 22
        for i, ch in enumerate(channels):
            parts.append(f'<circle cx="{cursor + 6:.1f}" cy="{ly2 - 5:.1f}" r="6" fill="{colors[ch]}"/>')
            parts.append(f'<text x="{cursor + 18:.1f}" y="{ly2:.1f}" font-size="12" fill="{INK}">{xml_escape(ch)}</text>')
            cursor += 18 + 7.2 * len(ch) + 22

    # ---- y-axis gridlines ----
    # y_ticks is already the right list for both branches: log_ticks(...) above
    # for log_y, nice_ticks(...) above otherwise.
    y_gridline_vals = y_ticks
    for val in y_gridline_vals:
        ty = y_for(val)
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{ty:.1f}" x2="{plot_x + plot_w:.1f}" y2="{ty:.1f}" '
            f'stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        # fmt_number only for log ticks (decade values can be fractional,
        # e.g. 0.1 -- a plain :.0f} would truncate them to "0"); the linear
        # branch keeps its original :.0f} so the default (non-log) render
        # is unchanged.
        tick_label = fmt_number(val) if log_y else f"{val:.0f}"
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{ty + 4:.1f}" font-size="11" font-family="{mono_family}" '
            f'fill="{SECONDARY}" text-anchor="end">{tick_label}</text>'
        )
    parts.append(
        f'<text x="18" y="{plot_y + plot_h / 2:.1f}" font-size="13" fill="{INK}" '
        f'text-anchor="middle" transform="rotate(-90 18 {plot_y + plot_h / 2:.1f})">'
        f'{xml_escape(y_label)}</text>'
    )

    # ---- stacked bands (bottom-to-top) ----
    band_tips: List[str] = []
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
            f'<path id="band-hit-{ci}" class="band band-{ci} hit" tabindex="0" d="{path_d}" '
            f'fill="{colors[ch]}" fill-opacity="0.82"><title>{xml_escape(tip)}</title></path>'
        )
        mid_i = n // 2
        share = (band_total / sum(totals.values()) * 100.0) if sum(totals.values()) else 0.0
        band_tips.append(
            tooltip_bubble(
                top_pts[mid_i][0], min(top_pts[mid_i][1], bottom_pts[mid_i][1]),
                [ch, f"{band_total:.0f}k visits total", f"{share:.0f}% of stacked total"],
                canvas_w=width, canvas_h=height, ink=INK, secondary=SECONDARY, border=GRIDLINE,
                elem_id=f"band-tip-{ci}",
            )
        )
    parts.extend(band_tips)

    # ---- x-axis ----
    axis_y = plot_y + plot_h
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{axis_y:.1f}" x2="{plot_x + plot_w:.1f}" y2="{axis_y:.1f}" '
        f'stroke="{INK}" stroke-width="1.2"/>'
    )
    for i, m in enumerate(months):
        parts.append(
            f'<text x="{x_for(i):.1f}" y="{axis_y + 20:.1f}" font-size="11" font-family="{mono_family}" '
            f'fill="{SECONDARY}" text-anchor="middle">{xml_escape(m)}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{axis_y + 42:.1f}" font-size="13" '
        f'fill="{INK}" text-anchor="middle">{xml_escape(x_label)}</text>'
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
    x_label: str = "Month",
    y_label: str = "Visits (thousands)",
    log_y: bool = False,
    theme: str = "corporate",
    legend_title: str = "Channel",
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
    x_label, y_label : str, optional
        Axis titles. Forwarded to :func:`build_svg`.
    log_y : bool, optional
        Use a logarithmic total-visits axis. Forwarded to :func:`build_svg`.
    theme : str, optional
        Visual theme. Forwarded to :func:`build_svg`.

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
                     mode=mode, accessibility=accessibility, x_label=x_label,
                     y_label=y_label, log_y=log_y, theme=theme, legend_title=legend_title)
    dest = Path(out) if out else svg_example_path(__file__, "area")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "area", build_svg, description="Generate a stacked area chart.")


if __name__ == "__main__":
    main()
