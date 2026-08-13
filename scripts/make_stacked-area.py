#!/usr/bin/env python3
"""
make_stacked-area — a house-styled stacked area chart over a continuous axis as hand-authored SVG.

Stacks several series' values on top of each other along a continuous
quantitative x-axis (month number, as opposed to ``make_area``'s
categorical month-name axis), so the top edge traces the running total
while each band's own thickness traces its individual contribution.
Typical uses: monthly cost by service, cumulative resource usage, any
composition that should read both as a whole and as its parts.

Previously rendered via Vega-Lite (``vl_convert``); this module now
computes the cumulative stacking and paints each band by hand -- no
Vega, no matplotlib. Hovering a band highlights it via CSS ``:has()``;
every band carries a native ``<title>`` tooltip.

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
from _scale import nice_ticks  # noqa: E402
from _style import BG, GRIDLINE, INK, SECONDARY, cycle_hues  # noqa: E402
from _svg import svg_open, tooltip_bubble, xml_escape  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402


SERVICES = ["Compute", "Storage", "Network"]

DEMO_DATA: List[Dict[str, Any]] = [
    {"month": m, "service": s, "cost": v}
    for s, values in {
        "Compute": [21.5, 20.4, 22.8, 24.1, 26.0, 28.4, 30.1, 32.5, 34.0, 36.8, 39.2, 42.0],
        "Storage": [8.0, 8.2, 8.5, 8.9, 9.3, 9.8, 10.4, 11.0, 11.6, 12.3, 13.0, 13.8],
        "Network": [5.0, 4.8, 5.2, 5.5, 5.9, 6.3, 6.8, 7.2, 7.6, 8.1, 8.6, 9.1],
    }.items()
    for m, v in zip(range(1, 13), values)
]


def _service_colors(
    services: List[str], accessibility: str = "universal", theme: str = "corporate"
) -> Dict[str, str]:
    return cycle_hues(services, accessibility, theme=theme)


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Compute Drives the Cloud Bill",
    subtitle: str = "Monthly cost by service (k$)",
    width: int = 745,
    height: int = 480,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full continuous-axis stacked area chart SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``month`` (numeric), ``service`` (str), ``cost``
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

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    mono_family = mono_stack_for_theme(theme)
    rows = data if data else DEMO_DATA
    seen_services: List[str] = []
    for r in rows:
        if r["service"] not in seen_services:
            seen_services.append(r["service"])
    services = [s for s in SERVICES if s in seen_services] + [s for s in seen_services if s not in SERVICES]
    colors = _service_colors(services, accessibility, theme=theme)
    months = sorted({float(r["month"]) for r in rows})

    lookup: Dict[tuple, float] = {(r["service"], float(r["month"])): float(r["cost"]) for r in rows}
    cum: Dict[str, List[float]] = {}
    running = [0.0] * len(months)
    for s in services:
        band = []
        for i, m in enumerate(months):
            running[i] += lookup.get((s, m), 0.0)
            band.append(running[i])
        cum[s] = band
    max_total = max(running) if running else 1.0
    x_min, x_max = min(months), max(months)

    plot_x, plot_y = 60.0, 150.0
    right_margin, bottom_reserved = 30.0, 60.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved

    def x_for(m: float) -> float:
        return plot_x + (m - x_min) / ((x_max - x_min) or 1.0) * plot_w

    # Nice round tick values (Heckbert "nice numbers") instead of naive
    # linear division of max_total into 4 raw steps -- max_total/4.0-style
    # division lands the top gridline exactly on the data peak but produces
    # unscannable labels like 16/32/49/65 instead of 0/16/32/48/64 or
    # similar round numbers a reader can do mental math with.
    y_ticks = nice_ticks(max_total, 4)
    y_domain = y_ticks[-1] or 1.0

    def y_for(v: float) -> float:
        return plot_y + plot_h - (v / y_domain * plot_h)

    parts: List[str] = []
    parts.append(svg_open(width, height, "sa-title", "sa-desc", font_family=chrome_stack_for_theme(theme)))
    parts.append(f'<title id="sa-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="sa-desc">Stacked area of {len(services)} services over {len(months)} '
        f'months, ending at {running[-1]:.0f}. Hover or focus a band for its exact value.</desc>'
    )
    parts.append(
        "<style>"
        ".band-group{transition:opacity .15s ease;}"
        "svg:hover .band-group,svg:focus-within .band-group{opacity:.45;}"
        + "".join(f'svg:has(.b{i}:hover,.b{i}:focus) .b{i}{{opacity:1;}}' for i in range(len(services)))
        + ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        ".hit:hover+.tip,.hit:focus+.tip{opacity:1}"
        + "@media (prefers-reduced-motion: reduce){.band-group{transition:none;}"
        ".tip{transition:none}}"
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
    for s in services:
        parts.append(f'<rect x="{cursor:.1f}" y="{ly - 12:.1f}" width="14" height="14" rx="3" fill="{colors[s]}"/>')
        parts.append(f'<text x="{cursor + 20:.1f}" y="{ly:.1f}" font-size="12" fill="{INK}">{xml_escape(s)}</text>')
        cursor += 20 + 7.0 * len(s) + 22

    # ---- y-axis gridlines ----
    for tick in y_ticks:
        ty = y_for(tick)
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{ty:.1f}" x2="{plot_x + plot_w:.1f}" y2="{ty:.1f}" '
            f'stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{ty + 4:.1f}" font-size="11" font-family="{mono_family}" '
            f'fill="{SECONDARY}" text-anchor="end">{tick:.0f}</text>'
        )
    parts.append(
        f'<text x="18" y="{plot_y + plot_h / 2:.1f}" font-size="13" fill="{INK}" '
        f'text-anchor="middle" transform="rotate(-90 18 {plot_y + plot_h / 2:.1f})">Cost (k$)</text>'
    )

    # ---- stacked bands ----
    prev = [0.0] * len(months)
    for si, s in enumerate(services):
        top = cum[s]
        top_pts = [(x_for(m), y_for(v)) for m, v in zip(months, top)]
        bot_pts = [(x_for(m), y_for(v)) for m, v in zip(months, prev)]
        d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in top_pts)
        d += " L " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in reversed(bot_pts)) + " Z"
        latest = top[-1] - prev[-1]
        latest_share = latest / (running[-1] or 1.0) * 100.0
        tip = f"{s}: {latest:.1f}k$ in the latest month"
        parts.append(f'<g class="band-group b{si}">')
        parts.append(
            f'<path class="hit" tabindex="0" d="{d}" fill="{colors[s]}" fill-opacity="0.82" '
            f'role="img" aria-label="{xml_escape(tip)}"/>'
        )
        mid_i = len(months) // 2
        parts.append(
            tooltip_bubble(
                top_pts[mid_i][0], (top_pts[mid_i][1] + bot_pts[mid_i][1]) / 2.0 - 14,
                [s, f"{top[mid_i] - prev[mid_i]:.1f}k$ that month", f"{latest_share:.0f}% of latest total"],
                anchor="middle", canvas_w=width, canvas_h=height,
                ink=INK, secondary=SECONDARY, border=GRIDLINE,
            )
        )
        parts.append("</g>")
        prev = top

    # ---- x-axis ----
    axis_y = plot_y + plot_h
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{axis_y:.1f}" x2="{plot_x + plot_w:.1f}" y2="{axis_y:.1f}" '
        f'stroke="{INK}" stroke-width="1.2"/>'
    )
    for m in months:
        if int(m) % 2 != 1:
            continue
        parts.append(
            f'<text x="{x_for(m):.1f}" y="{axis_y + 20:.1f}" font-size="11" font-family="{mono_family}" '
            f'fill="{SECONDARY}" text-anchor="middle">{m:.0f}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{axis_y + 42:.1f}" font-size="13" '
        f'fill="{INK}" text-anchor="middle">Month</text>'
    )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_stacked_area(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Compute Drives the Cloud Bill",
    subtitle: str = "Monthly cost by service (k$)",
    width: int = 745,
    height: int = 480,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored continuous-axis stacked area chart and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``month`` (float), ``service`` (str), ``cost``
        (float). Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to
        ``assets/svg-examples/stacked-area.svg``.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    mode, accessibility : str
        Forwarded to :func:`build_svg`.
    theme : str, optional
        Visual theme. Forwarded to :func:`build_svg`.

    Returns
    -------
    Path
        Absolute path to the written SVG file.

    Examples
    --------
    >>> p = make_stacked_area()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility, theme=theme)
    dest = Path(out) if out else svg_example_path(__file__, "stacked-area")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "stacked-area", build_svg, description="Generate a stacked area chart over a continuous axis.")


if __name__ == "__main__":
    main()
