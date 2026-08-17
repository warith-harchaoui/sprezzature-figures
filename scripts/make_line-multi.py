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
the polylines and points by hand, with no Vega and no matplotlib. Every point
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
from _style import BG, GRIDLINE, INK, SECONDARY, cycle_hues  # noqa: E402
from _scale import fixed_step_ticks, log_position, log_ticks, nice_ticks, nice_ticks_range  # noqa: E402
from _svg import fmt_number, foreground_tip_css, svg_open, tooltip_bubble, xml_escape  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402


PLATFORMS = ["Desktop", "Mobile"]

_DESKTOP = [41, 41, 42, 40, 39, 43, 58, 77, 92, 98, 101, 103, 99, 104, 108, 106, 99, 91, 80, 70, 62, 55, 48, 44]
_MOBILE = [30, 30, 30, 28, 27, 29, 35, 44, 52, 58, 61, 63, 66, 68, 71, 78, 90, 105, 118, 124, 116, 98, 74, 48]

DEMO_DATA: List[Dict[str, Any]] = [
    {"hour": h, "platform": "Desktop", "sessions": v} for h, v in enumerate(_DESKTOP)
] + [
    {"hour": h, "platform": "Mobile", "sessions": v} for h, v in enumerate(_MOBILE)
]


def _series_colors(
    series: List[str], accessibility: str = "universal", theme: str = "corporate"
) -> Dict[str, str]:
    return cycle_hues(series, accessibility, theme=theme)


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Mobile Use Peaks in the Evening",
    subtitle: str = "Sessions per hour by platform",
    width: int = 745,
    height: int = 480,
    mode: str = "self-contained",
    accessibility: str = "universal",
    x_label: str = "Hour of Day",
    y_label: str = "Sessions",
    log_x: bool = False,
    log_y: bool = False,
    theme: str = "corporate",
    x_domain: Optional[tuple] = None,
    x_tick_step: Optional[float] = None,
    y_domain: Optional[tuple] = None,
    y_tick_step: Optional[float] = None,
    y_minor_step: Optional[float] = None,
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
    theme : str, optional
        Visual theme: ``"corporate"`` (default, Roboto -- byte-identical to
        the pre-theme render) or ``"academic"`` (LaTeX-style Latin Modern).
        See :func:`sprezzature_figures.fonts.chrome_stack_for_theme`.
    x_domain, y_domain : tuple of (float, float), optional
        Explicit ``(lo, hi)`` axis bounds, overriding the default of the
        data's own min/max (x) or a 0-anchored nice ceiling (y). Ignored for
        an axis in log mode.
    x_tick_step, y_tick_step : float, optional
        Explicit, evenly-spaced labeled-tick step (see
        :func:`_scale.fixed_step_ticks`), overriding the default heuristic
        tick placement. Requires the matching `x_domain`/`y_domain` to be
        set too (the step needs bounds to walk between). Ignored in log
        mode.
    y_minor_step : float, optional
        When set, draws unlabeled minor gridlines across `y_domain` at this
        step, in addition to the labeled `y_tick_step` ones -- for a case
        where the meaningful grid is finer than what could legibly carry a
        label on every line (e.g. a 0.1 grid with a label only every 0.5).
        Requires `y_domain`.

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    mono_family = mono_stack_for_theme(theme)
    rows = data if data else DEMO_DATA
    seen_platforms: List[str] = []
    for r in rows:
        if r["platform"] not in seen_platforms:
            seen_platforms.append(r["platform"])
    series = [s for s in PLATFORMS if s in seen_platforms] + [s for s in seen_platforms if s not in PLATFORMS]
    colors = _series_colors(series, accessibility, theme=theme)

    lookup: Dict[tuple, float] = {(r["platform"], float(r["hour"])): float(r["sessions"]) for r in rows}

    hours = sorted({float(r["hour"]) for r in rows})
    all_vals = list(lookup.values())
    max_val = max(all_vals) if all_vals else 1.0
    pos_vals = [v for v in all_vals if v > 0]
    min_pos = min(pos_vals) if pos_vals else 1.0
    x_min, x_max = (float(x_domain[0]), float(x_domain[1])) if x_domain else (min(hours), max(hours))
    x_pos = [h for h in hours if h > 0]
    xlog_min = min(x_pos) if x_pos else 1.0

    plot_x, plot_y = 60.0, 150.0
    right_margin, bottom_reserved = 30.0, 60.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved

    def x_for(h: float) -> float:
        if log_x and h > 0 and x_max > xlog_min:
            return log_position(h, xlog_min, x_max, plot_x, plot_x + plot_w)
        return plot_x + (h - x_min) / ((x_max - x_min) or 1.0) * plot_w

    # y scale + ticks: linear (0..max, 5 ticks) or logarithmic (decade ticks spanning the data)
    if log_y:
        y_ticks = log_ticks(min_pos, max_val)
        y_lo, y_hi = y_ticks[0], y_ticks[-1]

        def y_for(v: float) -> float:
            return log_position(v, y_lo, y_hi, plot_y + plot_h, plot_y)
    elif y_domain:
        y_lo, y_hi = float(y_domain[0]), float(y_domain[1])
        y_ticks = fixed_step_ticks(y_lo, y_hi, y_tick_step) if y_tick_step else nice_ticks_range(y_lo, y_hi)

        def y_for(v: float) -> float:
            return plot_y + plot_h - (v - y_lo) / ((y_hi - y_lo) or 1.0) * plot_h
    else:
        # Nice, round ticks (shared _scale.nice_ticks, the house convention
        # used by make_bar.py/make_area.py/etc.) instead of raw max_val/4
        # fractions, which produced unreadable labels like 124/93/62/31/0.
        y_ticks = nice_ticks(max_val, 4)
        y_lo, y_hi = 0.0, (y_ticks[-1] or 1.0)

        def y_for(v: float) -> float:
            return plot_y + plot_h - (v / y_hi * plot_h)

    parts: List[str] = []
    parts.append(svg_open(width, height, "lm-title", "lm-desc", font_family=chrome_stack_for_theme(theme)))
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
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        f"{foreground_tip_css(len(series) * len(hours), mark_prefix='pt', tip_prefix='pttip')}"
        "@media (prefers-reduced-motion: reduce){.series-group,.pt{transition:none;}.tip{transition:none}}"
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

    # ---- y-axis minor gridlines (unlabeled, finer than the labeled ticks) ----
    if y_minor_step and y_domain:
        for tick in fixed_step_ticks(y_lo, y_hi, y_minor_step):
            ty = y_for(tick)
            parts.append(
                f'<line x1="{plot_x:.1f}" y1="{ty:.1f}" x2="{plot_x + plot_w:.1f}" y2="{ty:.1f}" '
                f'stroke="{GRIDLINE}" stroke-width="0.5" opacity="0.5"/>'
            )

    # ---- y-axis gridlines ----
    for tick in y_ticks:
        ty = y_for(tick)
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{ty:.1f}" x2="{plot_x + plot_w:.1f}" y2="{ty:.1f}" '
            f'stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{ty + 4:.1f}" font-size="11" font-family="{mono_family}" '
            f'fill="{SECONDARY}" text-anchor="end">{fmt_number(tick)}</text>'
        )
    parts.append(
        f'<text x="18" y="{plot_y + plot_h / 2:.1f}" font-size="13" fill="{INK}" '
        f'text-anchor="middle" transform="rotate(-90 18 {plot_y + plot_h / 2:.1f})">{xml_escape(y_label)}</text>'
    )

    # ---- lines + points ----
    # Points draw first, every bubble is collected and appended once, last
    # -- but each series lives in its own <g class="series-group">, and CSS
    # `~` only matches same-parent siblings, so each series' bubbles go
    # before *that series'* closing tag, not at the very end of the whole
    # document. SVG has no z-index: a bubble next to its own point would be
    # covered by any point drawn after it, within the same series -- see
    # _svg.foreground_tip_css's docstring for the full pattern.
    pt_id = 0
    for si, s in enumerate(series):
        pts = [(x_for(h), y_for(lookup.get((s, h), 0.0))) for h in hours]
        path_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        parts.append(f'<g class="series-group s{si}">')
        parts.append(f'<path d="{path_d}" fill="none" stroke="{colors[s]}" stroke-width="2.5"/>')
        series_tips: List[str] = []
        for h in hours:
            v = lookup.get((s, h), 0.0)
            cx, cy = x_for(h), y_for(v)
            tip = f"{s}, {x_label} {fmt_number(h)}: {fmt_number(v)}"
            parts.append(
                f'<circle id="pt-{pt_id}" class="pt hit" tabindex="0" cx="{cx:.1f}" cy="{cy:.1f}" r="3.5" '
                f'fill="{colors[s]}" stroke="{BG}" stroke-width="1.5">'
                f'<title>{xml_escape(tip)}</title></circle>'
            )
            series_tips.append(
                tooltip_bubble(
                    cx,
                    max(4.0, cy - 34.0),
                    [s, f"{x_label} {fmt_number(h)}: {fmt_number(v)}"],
                    canvas_w=width,
                    canvas_h=height,
                    ink=INK,
                    secondary=SECONDARY,
                    border=GRIDLINE,
                    elem_id=f"pttip-{pt_id}",
                )
            )
            pt_id += 1
        parts.extend(series_tips)
        parts.append("</g>")

    # ---- x-axis ----
    axis_y = plot_y + plot_h
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{axis_y:.1f}" x2="{plot_x + plot_w:.1f}" y2="{axis_y:.1f}" '
        f'stroke="{INK}" stroke-width="1.2"/>'
    )
    # x ticks: decade ticks (log), an explicit fixed step (opt-in), the classic
    # every-3rd-hour rule for small integer axes (keeps the demo unchanged), or
    # ~8 evenly-spaced samples for a wide continuous range.
    if log_x:
        xticks = [d for d in log_ticks(xlog_min, x_max) if x_min * 0.9999 <= d <= x_max * 1.0000001]
    elif x_tick_step and x_domain:
        xticks = fixed_step_ticks(x_min, x_max, x_tick_step)
    elif x_max <= 24 and all(float(h).is_integer() for h in hours):
        xticks = [h for h in hours if int(h) % 3 == 0]
    else:
        step = max(1, len(hours) // 8)
        xticks = hours[::step]
    for h in xticks:
        parts.append(
            f'<text x="{x_for(h):.1f}" y="{axis_y + 20:.1f}" font-size="11" font-family="{mono_family}" '
            f'fill="{SECONDARY}" text-anchor="middle">{fmt_number(h)}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{axis_y + 42:.1f}" font-size="13" '
        f'fill="{INK}" text-anchor="middle">{xml_escape(x_label)}</text>'
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
    x_label: str = "Hour of Day",
    y_label: str = "Sessions",
    log_x: bool = False,
    log_y: bool = False,
    theme: str = "corporate",
    x_domain: Optional[tuple] = None,
    x_tick_step: Optional[float] = None,
    y_domain: Optional[tuple] = None,
    y_tick_step: Optional[float] = None,
    y_minor_step: Optional[float] = None,
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
    theme : str, optional
        Visual theme. Forwarded to :func:`build_svg`.
    x_domain, x_tick_step, y_domain, y_tick_step, y_minor_step : optional
        Explicit axis control, forwarded to :func:`build_svg`; see its
        docstring. Left at their defaults, the axes behave exactly as
        before (data-driven domain, heuristic ticks).

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
                     mode=mode, accessibility=accessibility, x_label=x_label, y_label=y_label,
                     log_x=log_x, log_y=log_y, theme=theme, x_domain=x_domain,
                     x_tick_step=x_tick_step, y_domain=y_domain, y_tick_step=y_tick_step,
                     y_minor_step=y_minor_step)
    dest = Path(out) if out else svg_example_path(__file__, "line-multi")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "line-multi", build_svg, description="Generate a multi-series line chart over a continuous axis.")


if __name__ == "__main__":
    main()
