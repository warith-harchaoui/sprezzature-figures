#!/usr/bin/env python3
"""
make_donut — a house-styled donut chart as hand-authored SVG.

A donut chart is a pie chart with the centre punched out: each category's
share of a whole is encoded as an arc's angular span, ordered largest to
smallest so the eye reads dominance at a glance. The open centre keeps the
figure legible even with a percentage label sitting just outside each arc.
Typical uses: traffic by acquisition channel, budget by category, votes by
candidate — any small (2-6 category) part-of-whole breakdown where a bar
chart would waste the "whole" framing a donut gives for free.

Previously rendered via Vega-Lite (``vl_convert``, a layered ``arc`` +
``text`` mark with a ``theta`` encoding); this module now computes the
wedge angles itself and paints the annulus by hand -- no Vega, no
matplotlib. Every wedge carries a native ``<title>`` tooltip.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _style import BG, GRIDLINE, INK, SECONDARY, load_palette  # noqa: E402
from _svg import svg_open, tooltip_bubble, xml_escape  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme  # noqa: E402


DEMO_DATA: List[Dict[str, Any]] = [
    {"source": "Search", "visits": 41},
    {"source": "Direct", "visits": 27},
    {"source": "Social", "visits": 18},
    {"source": "Referral", "visits": 14},
]


def _polar(cx: float, cy: float, r: float, angle: float) -> Tuple[float, float]:
    return cx + r * math.sin(angle), cy - r * math.cos(angle)


def _annular_sector_path(cx: float, cy: float, r_inner: float, r_outer: float,
                          a0: float, a1: float) -> str:
    large_arc = 1 if (a1 - a0) > math.pi else 0
    ox0, oy0 = _polar(cx, cy, r_outer, a0)
    ox1, oy1 = _polar(cx, cy, r_outer, a1)
    ix1, iy1 = _polar(cx, cy, r_inner, a1)
    ix0, iy0 = _polar(cx, cy, r_inner, a0)
    return (
        f"M {ox0:.2f},{oy0:.2f} A {r_outer:.2f} {r_outer:.2f} 0 {large_arc} 1 {ox1:.2f},{oy1:.2f} "
        f"L {ix1:.2f},{iy1:.2f} A {r_inner:.2f} {r_inner:.2f} 0 {large_arc} 0 {ix0:.2f},{iy0:.2f} Z"
    )


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Search and Direct Bring Most Traffic",
    subtitle: str = "Share of visits by source",
    width: int = 520,
    height: int = 480,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full donut chart SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``source`` (str) and ``visits`` (numeric). Defaults
        to :data:`DEMO_DATA`.
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
    rows = sorted(data if data else DEMO_DATA, key=lambda r: -float(r["visits"]))
    total = sum(float(r["visits"]) for r in rows) or 1.0
    palette = load_palette(accessibility, theme=theme)
    hue_order = [palette.get(h, d) for h, d in (
        ("Red", "#FF3B30"), ("Orange", "#FF9500"), ("Yellow", "#FFCC00"),
        ("Green", "#28CD41"), ("Teal", "#79DBDC"), ("Blue", "#007AFF"),
        ("Purple", "#AF52DE"), ("Pink", "#FF2D55"),
    )]
    colors = {r["source"]: hue_order[i % len(hue_order)] for i, r in enumerate(rows)}

    top_margin, bottom_margin = 120.0, 110.0
    cx = width / 2.0
    cy = top_margin + (height - top_margin - bottom_margin) / 2.0
    r_outer = min(width - 40.0, height - top_margin - bottom_margin) / 2.0
    r_inner = r_outer * 0.627
    r_label = r_outer + 24.0

    parts: List[str] = []
    parts.append(svg_open(width, height, "donut-title", "donut-desc", font_family=chrome_stack_for_theme(theme)))
    parts.append(f'<title id="donut-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="donut-desc">Donut chart of {len(rows)} sources totalling {total:,.0f}. '
        f'Hover or focus a wedge for its exact share.</desc>'
    )
    parts.append(
        "<style>"
        ".wedge{transition:opacity .15s ease;cursor:default;}"
        ".wedge:hover,.wedge:focus{opacity:.75;outline:none;}"
        "@media (prefers-reduced-motion: reduce){.wedge{transition:none;}}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        ".hit:hover~.tip,.hit:focus~.tip{opacity:1}"
        "@media (prefers-reduced-motion:reduce){.tip{transition:none}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="{width / 2:.1f}" y="46" font-size="22" font-weight="700" fill="{INK}" '
        f'text-anchor="middle" letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(
        f'<text x="{width / 2:.1f}" y="70" font-size="14" fill="{SECONDARY}" '
        f'text-anchor="middle">{xml_escape(subtitle)}</text>'
    )

    angle = 0.0
    for rank, r in enumerate(rows, start=1):
        share = float(r["visits"]) / total
        a0, a1 = angle, angle + share * 2.0 * math.pi
        angle = a1
        color = colors[r["source"]]
        d = _annular_sector_path(cx, cy, r_inner, r_outer, a0, a1)
        tip = f"{r['source']}: {float(r['visits']):,.0f} ({share * 100:.0f}%)"
        parts.append(
            f'<path class="wedge hit" tabindex="0" d="{d}" fill="{color}" '
            f'stroke="{BG}" stroke-width="2"><title>{xml_escape(tip)}</title></path>'
        )
        mid = (a0 + a1) / 2.0
        lx, ly = _polar(cx, cy, r_label, mid)
        parts.append(
            tooltip_bubble(
                lx, ly + 12, [str(r["source"]), f"{float(r['visits']):,.0f} visits ({share * 100:.0f}%)",
                              f"rank {rank} of {len(rows)}"],
                canvas_w=width, canvas_h=height, ink=INK, secondary=SECONDARY, border=GRIDLINE,
            )
        )
        parts.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="13" font-weight="700" fill="{INK}" '
            f'text-anchor="middle" dominant-baseline="middle">{share * 100:.0f}%</text>'
        )

    # ---- legend ----
    ly0 = height - bottom_margin + 40.0
    total_w = sum(24.0 + 7.0 * len(r["source"]) + 22.0 for r in rows)
    cursor = (width - total_w) / 2.0
    for r in rows:
        color = colors[r["source"]]
        parts.append(f'<circle cx="{cursor + 6:.1f}" cy="{ly0 - 4:.1f}" r="6" fill="{color}"/>')
        parts.append(
            f'<text x="{cursor + 20:.1f}" y="{ly0:.1f}" font-size="12" fill="{INK}">{xml_escape(r["source"])}</text>'
        )
        cursor += 24.0 + 7.0 * len(r["source"]) + 22.0

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_donut(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Search and Direct Bring Most Traffic",
    subtitle: str = "Share of visits by source",
    width: int = 520,
    height: int = 480,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored donut chart and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``source`` (str) and ``visits`` (float). Defaults to
        DEMO_DATA (traffic by acquisition source).
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/donut.svg``.
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
    >>> p = make_donut()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility, theme=theme)
    dest = Path(out) if out else svg_example_path(__file__, "donut")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "donut", build_svg, description="Generate a donut chart.")


if __name__ == "__main__":
    main()
