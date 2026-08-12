#!/usr/bin/env python3
"""
make_beeswarm — a house-styled beeswarm plot as hand-authored SVG.

A beeswarm plot places one dot per observation along a shared numeric
axis, nudging dots that would overlap just far enough apart (vertically,
here) to keep every point visible -- unlike a strip plot's random jitter,
the offset is deterministic collision avoidance, so the swarm's width at
any point on the axis is itself a density cue. Colour groups the points
so the reader can compare several overlapping distributions on one axis
at once. Typical uses: exam scores across three classes, response times
across experiment arms, salaries across departments -- anywhere a
histogram would hide individual outliers and a box plot would hide shape.

Previously rendered via full Vega (``vl_convert``, a ``force`` transform
running a collide + x + y simulation); this module now runs a
deterministic greedy collision-avoidance placement itself and paints
each dot by hand -- no Vega, no matplotlib. Every dot carries a native
``<title>`` tooltip.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _style import BG, GRIDLINE, INK, SECONDARY, load_palette  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402
from _svg import svg_open, tooltip_bubble, xml_escape  # noqa: E402


GROUPS = ["A", "B", "C"]
_RADIUS = 5.0


def _make_demo_data() -> List[Dict[str, Any]]:
    rng = random.Random(7)
    means = {"A": 29.0, "B": 57.0, "C": 48.0}
    stds = {"A": 6.5, "B": 8.5, "C": 12.0}
    rows: List[Dict[str, Any]] = []
    for g in GROUPS:
        for _ in range(24):
            rows.append({"group": g, "value": round(rng.gauss(means[g], stds[g]), 1)})
    return rows


DEMO_DATA: List[Dict[str, Any]] = _make_demo_data()


def _swarm_positions(items: List[Tuple[float, float]], center_y: float, radius: float) -> List[float]:
    """Greedy collision-avoidance layout: return one y per (x, _) in *items*.

    Processes points in the given order, trying ``center_y`` first, then
    alternating offsets of increasing magnitude, accepting the first
    position that does not overlap (in Euclidean distance) any
    already-placed point whose x is within one diameter.
    """
    step = radius * 1.9
    placed: List[Tuple[float, float]] = []
    ys: List[float] = []
    for x, _ in items:
        offset = 0
        tried = 0
        while True:
            candidate = center_y if offset == 0 else center_y + (step * ((offset + 1) // 2) * (1 if offset % 2 else -1))
            collision = any(
                (x - px) ** 2 + (candidate - py) ** 2 < (2 * radius) ** 2
                for px, py in placed
                if abs(x - px) < 2 * radius
            )
            if not collision or tried > 400:
                placed.append((x, candidate))
                ys.append(candidate)
                break
            offset += 1
            tried += 1
    return ys


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Response Times Overlap Across Three Cohorts",
    subtitle: str = "Each dot is one observation; horizontal position is the measured value",
    width: int = 745,
    height: int = 360,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full beeswarm plot SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``group`` (str) and ``value`` (numeric). Defaults
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
    mono_family = mono_stack_for_theme(theme)
    rows = data if data else DEMO_DATA
    seen_groups: List[str] = []
    for r in rows:
        if r["group"] not in seen_groups:
            seen_groups.append(r["group"])
    groups = [g for g in GROUPS if g in seen_groups] + [g for g in seen_groups if g not in GROUPS]
    palette = load_palette(accessibility, theme=theme)
    # Brown/Blue/Green (not Red/Blue/Green): a grayscale-legibility fix. Red
    # (#FF3B30, relative luminance ~100) and Blue (#007AFF, ~106) are only
    # ~6 apart and collapse to the same shade once desaturated -- easy to
    # miss here since the dot cloud interleaves all three groups. Brown
    # (~68) separates cleanly from both Blue (~106) and Green (~160).
    hue_order = [palette.get("Brown", "#A52A2A"), palette.get("Blue", "#007AFF"), palette.get("Green", "#34C759")]
    colors = {g: hue_order[i % len(hue_order)] for i, g in enumerate(groups)}

    values = [float(r["value"]) for r in rows]
    v_min, v_max = min(values), max(values)
    pad = (v_max - v_min) * 0.06 or 1.0

    plot_x, plot_y = 60.0, 150.0
    right_margin, bottom_reserved = 30.0, 60.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved
    center_y = plot_y + plot_h / 2.0

    def x_for(v: float) -> float:
        return plot_x + (v - (v_min - pad)) / ((v_max + pad) - (v_min - pad)) * plot_w

    ordered_rows = sorted(rows, key=lambda r: float(r["value"]))
    items = [(x_for(float(r["value"])), 0.0) for r in ordered_rows]
    ys = _swarm_positions(items, center_y, _RADIUS)

    parts: List[str] = []
    parts.append(svg_open(width, height, "bee-title", "bee-desc", font_family=chrome_stack_for_theme(theme)))
    parts.append(f'<title id="bee-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="bee-desc">Beeswarm of {len(rows)} observations across {len(groups)} groups, '
        f'ranging {v_min:.1f} to {v_max:.1f}. Hover or focus a dot for its exact value.</desc>'
    )
    parts.append(
        "<style>"
        ".dot{transition:r .12s ease;}"
        ".dot:hover,.dot:focus{r:7;outline:none;}"
        "@media (prefers-reduced-motion: reduce){.dot{transition:none;}}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        ".hit:hover~.tip,.hit:focus~.tip{opacity:1}"
        "@media (prefers-reduced-motion:reduce){.tip{transition:none}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="40" y="46" font-size="22" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(f'<text x="40" y="70" font-size="14" fill="{SECONDARY}">{xml_escape(subtitle)}</text>')

    # ---- legend ----
    lx, ly = 40.0, 104.0
    cursor = lx
    for g in groups:
        parts.append(f'<circle cx="{cursor + 6:.1f}" cy="{ly - 4:.1f}" r="6" fill="{colors[g]}"/>')
        parts.append(f'<text x="{cursor + 20:.1f}" y="{ly:.1f}" font-size="12" fill="{INK}">Group {xml_escape(g)}</text>')
        cursor += 20 + 7.0 * (len(g) + 6) + 22

    # ---- x-axis ----
    axis_y = plot_y + plot_h + 34.0
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{axis_y:.1f}" x2="{plot_x + plot_w:.1f}" y2="{axis_y:.1f}" '
        f'stroke="{INK}" stroke-width="1.2"/>'
    )
    x_ticks = 6
    for i in range(x_ticks + 1):
        val = (v_min - pad) + ((v_max + pad) - (v_min - pad)) * i / x_ticks
        tx = x_for(val)
        parts.append(
            f'<line x1="{tx:.1f}" y1="{plot_y:.1f}" x2="{tx:.1f}" y2="{plot_y + plot_h:.1f}" '
            f'stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{tx:.1f}" y="{axis_y + 20:.1f}" font-size="11" font-family="{mono_family}" '
            f'fill="{SECONDARY}" text-anchor="middle">{val:.0f}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{axis_y + 42:.1f}" font-size="13" '
        f'fill="{INK}" text-anchor="middle">Value</text>'
    )

    # ---- dots ----
    n_rows = len(ordered_rows)
    for i, ((x, _), y, row) in enumerate(zip(items, ys, ordered_rows)):
        g = str(row["group"])
        val = float(row["value"])
        tip = f"Group {g}: {val:.1f}"
        parts.append(
            f'<circle class="dot hit" tabindex="0" cx="{x:.1f}" cy="{y:.1f}" r="{_RADIUS:.0f}" '
            f'fill="{colors.get(g, "#8E8E93")}" stroke="{BG}" stroke-width="1">'
            f'<title>{xml_escape(tip)}</title></circle>'
        )
        percentile = (i + 1) / n_rows * 100.0 if n_rows else 0.0
        parts.append(
            tooltip_bubble(
                x, y - _RADIUS - 6,
                [f"Group {g}", f"value {val:.1f}", f"{percentile:.0f}th percentile overall"],
                canvas_w=width, canvas_h=height, ink=INK, secondary=SECONDARY, border=GRIDLINE,
            )
        )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_beeswarm(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Response Times Overlap Across Three Cohorts",
    subtitle: str = "Each dot is one observation; horizontal position is the measured value",
    width: int = 745,
    height: int = 360,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored beeswarm plot and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``group`` (str) and ``value`` (float). Defaults to
        DEMO_DATA (three overlapping synthetic cohorts).
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/beeswarm.svg``.
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
    >>> p = make_beeswarm()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility, theme=theme)
    dest = Path(out) if out else svg_example_path(__file__, "beeswarm")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "beeswarm", build_svg, description="Generate a beeswarm plot.")


if __name__ == "__main__":
    main()
