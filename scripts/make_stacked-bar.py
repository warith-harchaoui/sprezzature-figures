#!/usr/bin/env python3
"""
make_stacked-bar — a house-styled 100%-normalised stacked bar chart as hand-authored SVG.

Stacks a categorical breakdown to fill exactly 100% of each bar, one bar
per outer category, so the reader compares *composition* (each segment's
share of the whole) across bars rather than absolute totals: the point
where a raw stacked bar's differing bar heights would otherwise get in
the way. Typical uses: revenue mix by quarter, survey answer distribution
by cohort, market share by region.

Previously rendered via Vega-Lite (``stack: "normalize"``, ``vl_convert``).
This module now normalises each bar to 100% itself and paints every
segment by hand: no Vega, no matplotlib. Every segment carries a native
``<title>`` tooltip with its exact share.

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
from _svg import foreground_tip_css, svg_open, tooltip_bubble, xml_escape  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402


QUARTERS = ["Q1", "Q2", "Q3", "Q4"]
TYPES = ["New", "Renewal", "Expansion"]

DEMO_DATA: List[Dict[str, Any]] = [
    {"quarter": "Q1", "type": "New", "share": 55}, {"quarter": "Q1", "type": "Renewal", "share": 30},
    {"quarter": "Q1", "type": "Expansion", "share": 15}, {"quarter": "Q2", "type": "New", "share": 48},
    {"quarter": "Q2", "type": "Renewal", "share": 36}, {"quarter": "Q2", "type": "Expansion", "share": 16},
    {"quarter": "Q3", "type": "New", "share": 40}, {"quarter": "Q3", "type": "Renewal", "share": 42},
    {"quarter": "Q3", "type": "Expansion", "share": 18}, {"quarter": "Q4", "type": "New", "share": 33},
    {"quarter": "Q4", "type": "Renewal", "share": 47}, {"quarter": "Q4", "type": "Expansion", "share": 20},
]


def _type_colors(
    types: List[str], accessibility: str = "universal", theme: str = "corporate"
) -> Dict[str, str]:
    return cycle_hues(types, accessibility, hues=['Blue', 'Green', 'Orange', 'Purple'], theme=theme)


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Renewals Now Lead the Revenue Mix",
    subtitle: str = "Revenue share by type, each quarter",
    width: int = 620,
    height: int = 480,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
    y_axis_title: str = "Share of revenue",
    x_axis_title: str = "Quarter",
) -> str:
    """Assemble the full 100%-stacked bar chart SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``quarter`` (str), ``type`` (str), ``share``
        (numeric; normalised to 100% per quarter regardless of input
        scale). Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    y_axis_title, x_axis_title : str, optional
        Axis titles (were hardcoded ``"Share of revenue"`` / ``"Quarter"``).
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
    seen_quarters: List[str] = []
    for r in rows:
        if r["quarter"] not in seen_quarters:
            seen_quarters.append(r["quarter"])
    quarters = [q for q in QUARTERS if q in seen_quarters] + [q for q in seen_quarters if q not in QUARTERS]
    seen_types: List[str] = []
    for r in rows:
        if r["type"] not in seen_types:
            seen_types.append(r["type"])
    types = [t for t in TYPES if t in seen_types] + [t for t in seen_types if t not in TYPES]
    colors = _type_colors(types, accessibility, theme=theme)
    lookup: Dict[tuple, float] = {(r["quarter"], r["type"]): float(r["share"]) for r in rows}

    plot_x, plot_y = 60.0, 150.0
    right_margin, bottom_reserved = 30.0, 60.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved
    n = len(quarters)
    bin_w = plot_w / n if n else plot_w
    bar_w = bin_w * 0.6

    def y_for(frac: float) -> float:
        return plot_y + plot_h - frac * plot_h

    parts: List[str] = []
    parts.append(svg_open(width, height, "sb-title", "sb-desc", font_family=chrome_stack_for_theme(theme)))
    parts.append(f'<title id="sb-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="sb-desc">100% stacked bar chart of {len(types)} segments across '
        f'{n} quarters. Hover or focus a segment for its exact share.</desc>'
    )
    parts.append(
        "<style>"
        ".seg{transition:filter .15s ease;}"
        ".seg:hover,.seg:focus{filter:brightness(1.08);outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + foreground_tip_css(len(quarters) * len(types))
        + "@media (prefers-reduced-motion: reduce){.seg{transition:none;}"
        ".tip{transition:none}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="40" y="46" font-size="22" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(f'<text x="40" y="70" font-size="14" fill="{SECONDARY}">{xml_escape(subtitle)}</text>')

    # ---- legend ----
    lx, ly = 40.0, 100.0
    cursor = lx
    for t in types:
        parts.append(f'<rect x="{cursor:.1f}" y="{ly - 12:.1f}" width="14" height="14" rx="3" fill="{colors[t]}"/>')
        parts.append(f'<text x="{cursor + 20:.1f}" y="{ly:.1f}" font-size="12" fill="{INK}">{xml_escape(t)}</text>')
        cursor += 20 + 7.0 * len(t) + 22

    # ---- y-axis gridlines (0%, 25%, ..., 100%) ----
    for i in range(5):
        frac = i / 4.0
        ty = y_for(frac)
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{ty:.1f}" x2="{plot_x + plot_w:.1f}" y2="{ty:.1f}" '
            f'stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{ty + 4:.1f}" font-size="11" font-family="{mono_family}" '
            f'fill="{SECONDARY}" text-anchor="end">{frac * 100:.0f}%</text>'
        )
    parts.append(
        f'<text x="18" y="{plot_y + plot_h / 2:.1f}" font-size="13" fill="{INK}" '
        f'text-anchor="middle" transform="rotate(-90 18 {plot_y + plot_h / 2:.1f})">{xml_escape(y_axis_title)}</text>'
    )

    # ---- bars ----
    # Every segment's bubble is queued into `bubbles` and appended once,
    # after every segment is drawn, rather than right next to its own
    # segment: SVG has no z-index, so a bubble drawn in place would be
    # covered by any segment drawn afterward, no matter which one is
    # hovered.
    bubbles: List[str] = []
    pair_idx = 0
    for qi, quarter in enumerate(quarters):
        total = sum(lookup.get((quarter, t), 0.0) for t in types) or 1.0
        x0 = plot_x + qi * bin_w + (bin_w - bar_w) / 2
        ranked = sorted(types, key=lambda t: -lookup.get((quarter, t), 0.0))
        cursor_frac = 0.0
        for t in types:
            share = lookup.get((quarter, t), 0.0)
            frac = share / total
            y_top = y_for(cursor_frac + frac)
            y_bot = y_for(cursor_frac)
            h = max(0.5, y_bot - y_top)
            tip = f"{t}, {quarter}: {frac * 100:.0f}% of revenue"
            rank = ranked.index(t) + 1
            parts.append(
                f'<rect id="hit-{pair_idx}" class="seg hit" tabindex="0" x="{x0:.1f}" y="{y_top:.1f}" '
                f'width="{bar_w:.1f}" height="{h:.1f}" fill="{colors.get(t, "#8E8E93")}" '
                f'role="img" aria-label="{xml_escape(tip)}"/>'
            )
            bubbles.append(
                tooltip_bubble(
                    x0 + bar_w / 2.0, min(y_top, y_bot) - 14,
                    [f"{t} — {quarter}", f"{frac * 100:.0f}% of revenue", f"#{rank} of {len(types)} segments"],
                    anchor="middle", canvas_w=width, canvas_h=height,
                    ink=INK, secondary=SECONDARY, border=GRIDLINE,
                    elem_id=f"tip-{pair_idx}",
                )
            )
            cursor_frac += frac
            pair_idx += 1

    # ---- x-axis ----
    axis_y = plot_y + plot_h
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{axis_y:.1f}" x2="{plot_x + plot_w:.1f}" y2="{axis_y:.1f}" '
        f'stroke="{INK}" stroke-width="1.2"/>'
    )
    for qi, quarter in enumerate(quarters):
        tx = plot_x + qi * bin_w + bin_w / 2
        parts.append(
            f'<text x="{tx:.1f}" y="{axis_y + 20:.1f}" font-size="13" fill="{INK}" '
            f'text-anchor="middle">{xml_escape(quarter)}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{axis_y + 42:.1f}" font-size="13" '
        f'fill="{INK}" text-anchor="middle">{xml_escape(x_axis_title)}</text>'
    )

    parts.extend(bubbles)
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_stacked_bar(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Renewals Now Lead the Revenue Mix",
    subtitle: str = "Revenue share by type, each quarter",
    width: int = 620,
    height: int = 480,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
    y_axis_title: str = "Share of revenue",
    x_axis_title: str = "Quarter",
) -> Path:
    """Render a hand-authored 100%-stacked bar chart and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``quarter`` (str), ``type`` (str), ``share``
        (float). Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/stacked-bar.svg``.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    mode, accessibility : str
        Forwarded to :func:`build_svg`.
    theme : str, optional
        Visual theme. Forwarded to :func:`build_svg`.
    y_axis_title, x_axis_title : str, optional
        Forwarded to :func:`build_svg` — were hardcoded ``"Share of revenue"``
        and ``"Quarter"`` with no way to override them for non-quarterly data.

    Returns
    -------
    Path
        Absolute path to the written SVG file.

    Examples
    --------
    >>> p = make_stacked_bar()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility, theme=theme,
                     y_axis_title=y_axis_title, x_axis_title=x_axis_title)
    dest = Path(out) if out else svg_example_path(__file__, "stacked-bar")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "stacked-bar", build_svg, description="Generate a 100%-normalised stacked bar chart.")


if __name__ == "__main__":
    main()
