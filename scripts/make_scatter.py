#!/usr/bin/env python3
"""
make_scatter — a house-styled scatter plot as a hand-authored SVG.

Plots two numeric variables against each other, with an optional
categorical color and numeric size encoding, to reveal correlation,
clusters, or outliers. Typical uses: price vs. quality rating, engine
size vs. fuel economy, marketing spend vs. conversions.

Previously rendered via Vega-Lite (``vl_convert``); this module now builds
the ``<svg>`` markup by hand -- no Vega, no matplotlib -- so every point
carries a native ``<title>`` tooltip with its exact reading.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _style import BG, FONT_MONO, GRIDLINE, INK, SECONDARY, cycle_hues, load_palette  # noqa: E402
from _svg import fmt_number, svg_open, xml_escape  # noqa: E402


SEGMENTS = ["Economy", "Midsize", "Premium"]


def _make_demo_data() -> List[Dict[str, Any]]:
    rng = random.Random(11)
    rows: List[Dict[str, Any]] = []
    segments = {
        "Economy": (25, 35, 90, 120),
        "Midsize": (18, 26, 130, 180),
        "Premium": (10, 18, 200, 320),
    }
    for segment, (mpg_lo, mpg_hi, hp_lo, hp_hi) in segments.items():
        for _ in range(15):
            rows.append({
                "segment": segment,
                "horsepower": round(rng.uniform(hp_lo, hp_hi), 1),
                "mpg": round(rng.uniform(mpg_lo, mpg_hi), 1),
                "weight": round(rng.uniform(1100, 1900), 0),
            })
    return rows


DEMO_DATA: List[Dict[str, Any]] = _make_demo_data()


def _segment_colors(segments: List[str], accessibility: str = "universal") -> Dict[str, str]:
    return cycle_hues(segments, accessibility)


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Horsepower vs. Fuel Economy",
    subtitle: str = "Synthetic sample, sized by weight, colored by segment",
    width: int = 845,
    height: int = 519,
    mode: str = "self-contained",
    accessibility: str = "universal",
    x_label: str = "Horsepower",
    y_label: str = "Fuel economy (mpg)",
    diagonal: bool = False,
    square: bool = False,
) -> str:
    """Assemble the full scatter plot SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``segment``, ``horsepower``, ``mpg``, ``weight``.
        Defaults to :data:`DEMO_DATA`.
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
    seen_segments: List[str] = []
    for r in rows:
        seg = r.get("segment")
        if seg is not None and seg not in seen_segments:
            seen_segments.append(seg)
    segments = [s for s in SEGMENTS if s in seen_segments] + [s for s in seen_segments if s not in SEGMENTS]
    colors = _segment_colors(segments, accessibility)
    has_weight = any("weight" in r and r["weight"] is not None for r in rows)

    xs = [float(r["horsepower"]) for r in rows]
    ys = [float(r["mpg"]) for r in rows]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    x_pad, y_pad = (x_max - x_min) * 0.08, (y_max - y_min) * 0.10
    x0, x1 = x_min - x_pad, x_max + x_pad
    y0, y1 = y_min - y_pad, y_max + y_pad
    # Do not pad an axis below zero when all its values are non-negative (distances,
    # counts, magnitudes): a negative axis floor would be meaningless.
    if x_min >= 0:
        x0 = max(0.0, x0)
    if y_min >= 0:
        y0 = max(0.0, y0)
    if square:
        # One shared domain so both axes carry the same units, and (with a square plot
        # area below) the same resolution, making the y = x line a true 45-degree diagonal.
        lo, hi = min(x0, y0), max(x1, y1)
        x0 = y0 = lo
        x1 = y1 = hi

    right_margin = 176.0 if (has_weight or len(segments) > 1) else 40.0
    plot_x, plot_y = 60.0, 118.0
    bottom_reserved = 70.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved
    if square:
        plot_w = plot_h = min(plot_w, plot_h)  # equal pixels per unit on both axes

    def x_for(v: float) -> float:
        return plot_x + (v - x0) / (x1 - x0) * plot_w

    def y_for(v: float) -> float:
        return plot_y + plot_h - (v - y0) / (y1 - y0) * plot_h

    weights = [float(r.get("weight") or 0) for r in rows]
    w_max = max(weights) if weights and has_weight else 1.0
    r_min, r_max = 4.5, 11.0

    def r_for(w: float) -> float:
        if not has_weight or w_max <= 0:
            return 6.0
        return r_min + (r_max - r_min) * math.sqrt(max(w, 0.0) / w_max)

    parts: List[str] = []
    parts.append(svg_open(width, height, "sc-title", "sc-desc"))
    parts.append(f'<title id="sc-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="sc-desc">Scatter plot of {len(rows)} points. Horizontal axis is the '
        f'first measure, vertical axis the second{"; bubble size is weight" if has_weight else ""}'
        f'{"; colour marks the segment" if len(segments) > 1 else ""}. Hover or focus a point '
        f'for its exact reading.</desc>'
    )

    parts.append(
        "<style>"
        ".pt{transition:opacity .12s ease,stroke-width .12s ease;}"
        ".pt:hover,.pt:focus{stroke-width:2.4;outline:none;}"
        "@media (prefers-reduced-motion: reduce){.pt{transition:none;}}"
        "</style>"
    )

    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="40" y="46" font-size="24" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(f'<text x="40" y="70" font-size="14" fill="{SECONDARY}">{xml_escape(subtitle)}</text>')

    # ---- y-axis gridlines ----
    y_ticks = 6
    for i in range(y_ticks + 1):
        val = y0 + (y1 - y0) * i / y_ticks
        ty = y_for(val)
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{ty:.1f}" x2="{plot_x + plot_w:.1f}" y2="{ty:.1f}" '
            f'stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{ty + 4:.1f}" font-size="11" font-family="{FONT_MONO}" '
            f'fill="{SECONDARY}" text-anchor="end">{fmt_number(val)}</text>'
        )
    parts.append(
        f'<text x="18" y="{plot_y + plot_h / 2:.1f}" font-size="13" fill="{INK}" '
        f'text-anchor="middle" transform="rotate(-90 18 {plot_y + plot_h / 2:.1f})">{xml_escape(y_label)}</text>'
    )

    # ---- x-axis ----
    axis_y = plot_y + plot_h
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{axis_y:.1f}" x2="{plot_x + plot_w:.1f}" y2="{axis_y:.1f}" '
        f'stroke="{INK}" stroke-width="1.2"/>'
    )
    x_ticks = 6
    for i in range(x_ticks + 1):
        val = x0 + (x1 - x0) * i / x_ticks
        tx = x_for(val)
        parts.append(
            f'<line x1="{tx:.1f}" y1="{axis_y:.1f}" x2="{tx:.1f}" y2="{axis_y + 6:.1f}" stroke="{INK}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{tx:.1f}" y="{axis_y + 20:.1f}" font-size="11" font-family="{FONT_MONO}" '
            f'fill="{SECONDARY}" text-anchor="middle">{fmt_number(val)}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{axis_y + 42:.1f}" font-size="13" '
        f'fill="{INK}" text-anchor="middle">{xml_escape(x_label)}</text>'
    )

    # ---- optional y = x reference line (identity: points on it are unchanged) ----
    if diagonal:
        lo, hi = max(x0, y0), min(x1, y1)
        if hi > lo:
            parts.append(
                f'<line x1="{x_for(lo):.1f}" y1="{y_for(lo):.1f}" x2="{x_for(hi):.1f}" y2="{y_for(hi):.1f}" '
                f'stroke="{SECONDARY}" stroke-width="1.3" stroke-dasharray="5 4" opacity="0.8"/>'
            )

    # ---- points, largest-first so small ones never hide under big ones ----
    ordered = sorted(rows, key=lambda r: -(float(r.get("weight") or 0)))
    for row in ordered:
        seg = row.get("segment", segments[0] if segments else "")
        cx, cy = x_for(float(row["horsepower"])), y_for(float(row["mpg"]))
        r = r_for(float(row.get("weight") or 0))
        color = colors.get(seg, colors[segments[0]] if segments else "#007AFF")
        bits = [f"Horsepower {row['horsepower']:.0f}", f"Fuel economy {row['mpg']:.1f} mpg"]
        if has_weight:
            bits.append(f"weight {row['weight']:.0f} kg")
        if seg:
            bits.insert(0, str(seg))
        tip = ", ".join(bits)
        parts.append(
            f'<circle class="pt" tabindex="0" cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" '
            f'fill="{color}" fill-opacity="0.72" stroke="{color}" stroke-width="1.2">'
            f'<title>{xml_escape(tip)}</title></circle>'
        )

    # ---- segment legend ----
    if len(segments) > 1:
        leg_x = width - right_margin + 28
        leg_y = 118.0
        parts.append(f'<text x="{leg_x:.1f}" y="{leg_y:.1f}" font-size="13" font-weight="700" fill="{INK}">Segment</text>')
        for i, seg in enumerate(segments):
            ry = leg_y + 26 + i * 26
            parts.append(f'<circle cx="{leg_x + 7:.1f}" cy="{ry - 5:.1f}" r="7" fill="{colors[seg]}" fill-opacity="0.85"/>')
            parts.append(f'<text x="{leg_x + 20:.1f}" y="{ry:.1f}" font-size="13" fill="{INK}">{xml_escape(seg)}</text>')

        if has_weight:
            size_leg_y = leg_y + 26 + len(segments) * 26 + 30
            parts.append(f'<text x="{leg_x:.1f}" y="{size_leg_y:.1f}" font-size="13" font-weight="700" fill="{INK}">Weight (kg)</text>')
            cursor_y = size_leg_y + 22
            for val in (w_max, w_max / 3):
                r = r_for(val)
                cy = cursor_y + r
                parts.append(f'<circle cx="{leg_x + r_max:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="none" stroke="{SECONDARY}" stroke-width="1"/>')
                parts.append(
                    f'<text x="{leg_x + r_max * 2 + 10:.1f}" y="{cy + 4:.1f}" font-size="12" '
                    f'font-family="{FONT_MONO}" fill="{SECONDARY}">{val:.0f}</text>'
                )
                cursor_y = cy + r + 8

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_scatter(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Horsepower vs. Fuel Economy",
    subtitle: str = "Synthetic sample, sized by weight, colored by segment",
    width: int = 845,
    height: int = 519,
    mode: str = "self-contained",
    accessibility: str = "universal",
    x_label: str = "Horsepower",
    y_label: str = "Fuel economy (mpg)",
    diagonal: bool = False,
    square: bool = False,
) -> Path:
    """Render a hand-authored scatter plot and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``segment`` (str), ``horsepower`` (float), ``mpg``
        (float), ``weight`` (float). Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/scatter.svg``.
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
    >>> p = make_scatter()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility, x_label=x_label, y_label=y_label,
                     diagonal=diagonal, square=square)
    dest = Path(out) if out else svg_example_path(__file__, "scatter")
    return write_svg(dest, svg)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "scatter", build_svg, description="Generate a scatter plot.")


if __name__ == "__main__":
    main()
