#!/usr/bin/env python3
"""
make_slope — a house-styled slope chart as hand-authored SVG.

Connects each item's value at two points in time with a straight line
between two vertical axes, one per period. The line's slope reads as
change at a glance: steep up means a big gain, steep down a big loss,
flat means no change, and crossing lines instantly flag rank reversals.
A tighter, more readable alternative to a grouped bar chart for a small
number of items measured before and after.

Previously rendered via Vega-Lite (a nominal two-category ``x`` encoding
with a line mark, ``vl_convert``); this module now paints each item's
line and end labels by hand -- no Vega, no matplotlib. Every line carries
a native ``<title>`` tooltip with both values and the change.

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
FONT_MONO = "Roboto Mono, ui-monospace, monospace"

ITEMS = ["Alpha", "Beta", "Gamma", "Delta", "Eps"]
PERIODS = ["2023", "2024"]

DEMO_DATA: List[Dict[str, Any]] = [
    {"item": "Alpha", "period": "2023", "v": 42}, {"item": "Alpha", "period": "2024", "v": 55},
    {"item": "Beta", "period": "2023", "v": 60}, {"item": "Beta", "period": "2024", "v": 48},
    {"item": "Gamma", "period": "2023", "v": 35}, {"item": "Gamma", "period": "2024", "v": 61},
    {"item": "Delta", "period": "2023", "v": 51}, {"item": "Delta", "period": "2024", "v": 52},
    {"item": "Eps", "period": "2023", "v": 28}, {"item": "Eps", "period": "2024", "v": 40},
]


def _item_colors(accessibility: str = "universal") -> Dict[str, str]:
    palette = load_palette(accessibility)
    hues = [palette.get(h, d) for h, d in (
        ("Blue", "#007AFF"), ("Orange", "#FF9500"), ("Green", "#34C759"),
        ("Purple", "#AF52DE"), ("Red", "#FF3B30"), ("Teal", "#79DBDC"),
    )]
    return {item: hues[i % len(hues)] for i, item in enumerate(ITEMS)}


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Score Change 2023 to 2024",
    subtitle: str = "One line per item, connecting its value at each period",
    width: int = 480,
    height: int = 520,
    mode: str = "self-contained",
    accessibility: str = "universal",
) -> str:
    """Assemble the full slope chart SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``item`` (str), ``period`` (str, exactly two
        distinct values), ``v`` (numeric). Defaults to :data:`DEMO_DATA`.
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
    items = [i for i in ITEMS if any(r["item"] == i for r in rows)] or sorted({r["item"] for r in rows})
    periods = [p for p in PERIODS if any(r["period"] == p for r in rows)] or sorted({r["period"] for r in rows})
    colors = _item_colors(accessibility)
    lookup: Dict[tuple, float] = {(r["item"], r["period"]): float(r["v"]) for r in rows}
    all_vals = list(lookup.values())
    v_min, v_max = min(all_vals), max(all_vals)
    pad = (v_max - v_min) * 0.12 or 1.0

    plot_x, plot_y = 90.0, 118.0
    right_margin, bottom_reserved = 90.0, 60.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved
    n_periods = len(periods)

    def x_for(pi: int) -> float:
        return plot_x + pi / max(1, n_periods - 1) * plot_w

    def y_for(v: float) -> float:
        return plot_y + plot_h - (v - (v_min - pad)) / ((v_max + pad) - (v_min - pad)) * plot_h

    parts: List[str] = []
    parts.append(svg_open(width, height, "slope-title", "slope-desc"))
    parts.append(f'<title id="slope-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="slope-desc">Slope chart of {len(items)} items across {n_periods} periods. '
        f'Hover or focus a line for its exact change.</desc>'
    )
    parts.append(
        "<style>"
        ".slope-line{transition:opacity .15s ease;}"
        ".slope-line:hover,.slope-line:focus{opacity:.55;outline:none;}"
        "@media (prefers-reduced-motion: reduce){.slope-line{transition:none;}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="30" y="46" font-size="21" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(f'<text x="30" y="70" font-size="13" fill="{SECONDARY}">{xml_escape(subtitle)}</text>')

    # ---- vertical axes ----
    for pi, period in enumerate(periods):
        px = x_for(pi)
        parts.append(f'<line x1="{px:.1f}" y1="{plot_y:.1f}" x2="{px:.1f}" y2="{plot_y + plot_h:.1f}" stroke="#E5E5EA" stroke-width="1"/>')
        parts.append(
            f'<text x="{px:.1f}" y="{plot_y - 16:.1f}" font-size="13" font-weight="700" fill="{INK}" '
            f'text-anchor="middle">{xml_escape(period)}</text>'
        )

    # ---- slope lines ----
    for item in items:
        pts = [(x_for(pi), y_for(lookup.get((item, p), 0.0))) for pi, p in enumerate(periods)]
        path_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        v0 = lookup.get((item, periods[0]), 0.0)
        v1 = lookup.get((item, periods[-1]), 0.0)
        change = v1 - v0
        sign = "+" if change >= 0 else ""
        tip = f"{item}: {v0:.0f} to {v1:.0f} ({sign}{change:.0f})"
        color = colors.get(item, "#8E8E93")
        parts.append('<g class="slope-line" tabindex="0">')
        parts.append(f'<title>{xml_escape(tip)}</title>')
        parts.append(f'<path d="{path_d}" fill="none" stroke="{color}" stroke-width="2.2"/>')
        for x, y in pts:
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}" stroke="{BG}" stroke-width="1.5"/>')
        parts.append("</g>")

        # End labels: item name + value at the first and last period.
        x0, y0 = pts[0]
        x1, y1 = pts[-1]
        parts.append(
            f'<text x="{x0 - 12:.1f}" y="{y0 + 4:.1f}" font-size="12" fill="{INK}" '
            f'text-anchor="end">{xml_escape(item)} ({v0:.0f})</text>'
        )
        parts.append(
            f'<text x="{x1 + 12:.1f}" y="{y1 + 4:.1f}" font-size="12" fill="{INK}" '
            f'text-anchor="start">{xml_escape(item)} ({v1:.0f})</text>'
        )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_slope(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Score Change 2023 to 2024",
    subtitle: str = "One line per item, connecting its value at each period",
    width: int = 480,
    height: int = 520,
    mode: str = "self-contained",
    accessibility: str = "universal",
) -> Path:
    """Render a hand-authored slope chart and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``item`` (str), ``period`` (str), ``v`` (float).
        Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/slope.svg``.
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
    >>> p = make_slope()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility)
    dest = Path(out) if out else svg_example_path(__file__, "slope")
    return write_svg(dest, svg)


def main() -> None:
    render_cli(__file__, "slope", build_svg, description="Generate a slope chart.")


if __name__ == "__main__":
    main()
