#!/usr/bin/env python3
"""
make_strip — a house-styled strip plot as hand-authored SVG.

Plots one dot per observation along a categorical axis, jittered
horizontally within each category's band so overlapping points stay
individually visible instead of stacking into an unreadable column.
Simpler than a beeswarm's deterministic collision avoidance (pure
random jitter) and correspondingly quicker to read for a modest sample
size per category. Typical uses: dose-response data, raw measurements
behind a box plot, any small-to-medium sample split by category.

Previously rendered via Vega-Lite (a ``calculate: "random()"`` transform
feeding an ``xOffset`` encoding, ``vl_convert``). This module now jitters
each point itself (a seeded RNG, reproducible across renders) and paints
every dot by hand: no Vega, no matplotlib. Every dot carries a native
``<title>`` tooltip.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _scale import nice_ticks_range  # noqa: E402
from _style import BG, GRIDLINE, INK, SECONDARY, cycle_hues  # noqa: E402
from _svg import foreground_tip_css, svg_open, tooltip_bubble, xml_escape  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402


GROUPS = ["Control", "Low", "High"]


def _make_demo_data() -> List[Dict[str, Any]]:
    rng = random.Random(19)
    means = {"Control": 52.0, "Low": 61.0, "High": 74.0}
    rows: List[Dict[str, Any]] = []
    for g in GROUPS:
        for _ in range(35):
            rows.append({"group": g, "value": round(rng.gauss(means[g], 8.5), 1)})
    return rows


DEMO_DATA: List[Dict[str, Any]] = _make_demo_data()


def _group_colors(
    groups: List[str], accessibility: str = "universal", theme: str = "corporate"
) -> Dict[str, str]:
    return cycle_hues(groups, accessibility, theme=theme)


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Response by Dose",
    subtitle: str = "Each dot is one observation, jittered within its group",
    width: int = 620,
    height: int = 480,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full strip plot SVG document as a string.

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
    colors = _group_colors(groups, accessibility, theme=theme)
    values = [float(r["value"]) for r in rows]
    raw_v_min, raw_v_max = min(values), max(values)
    pad = (raw_v_max - raw_v_min) * 0.1 or 1.0
    y_gridline_vals = nice_ticks_range(raw_v_min - pad, raw_v_max + pad, 5)
    v_min, v_max = y_gridline_vals[0], y_gridline_vals[-1]

    plot_x, plot_y = 60.0, 118.0
    right_margin, bottom_reserved = 30.0, 60.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved
    n_groups = len(groups)
    bin_w = plot_w / n_groups if n_groups else plot_w
    jitter_w = bin_w * 0.55

    def y_for(v: float) -> float:
        return plot_y + plot_h - (v - v_min) / ((v_max - v_min) or 1.0) * plot_h

    rng = random.Random(41)
    parts: List[str] = []
    parts.append(svg_open(width, height, "strip-title", "strip-desc", font_family=chrome_stack_for_theme(theme)))
    parts.append(f'<title id="strip-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="strip-desc">Strip plot of {len(rows)} observations across {n_groups} '
        f'groups. Hover or focus a dot for its exact value.</desc>'
    )
    parts.append(
        "<style>"
        ".dot{transition:r .12s ease;}"
        ".dot:hover,.dot:focus{r:6;outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + foreground_tip_css(len(rows))
        + "@media (prefers-reduced-motion: reduce){.dot{transition:none;}"
        ".tip{transition:none}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="40" y="46" font-size="22" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(f'<text x="40" y="70" font-size="14" fill="{SECONDARY}">{xml_escape(subtitle)}</text>')

    # ---- gridlines ----
    for val in y_gridline_vals:
        ty = y_for(val)
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{ty:.1f}" x2="{plot_x + plot_w:.1f}" y2="{ty:.1f}" '
            f'stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{ty + 4:.1f}" font-size="11" font-family="{mono_family}" '
            f'fill="{SECONDARY}" text-anchor="end">{val:.0f}</text>'
        )
    parts.append(
        f'<text x="18" y="{plot_y + plot_h / 2:.1f}" font-size="13" fill="{INK}" '
        f'text-anchor="middle" transform="rotate(-90 18 {plot_y + plot_h / 2:.1f})">Response</text>'
    )

    # ---- strips ----
    # Every dot's bubble is queued into `bubbles` and appended once, after
    # every dot is drawn, rather than right next to its own dot: SVG has no
    # z-index, so a bubble drawn in place would be covered by any dot drawn
    # afterward, no matter which one is hovered (a real risk here -- strips
    # jitter dots so they can and do sit close together).
    bubbles: List[str] = []
    dot_idx = 0
    for gi, g in enumerate(groups):
        cx0 = plot_x + gi * bin_w + bin_w / 2
        color = colors.get(g, "#8E8E93")
        group_rows = [r for r in rows if r["group"] == g]
        ranked = sorted(group_rows, key=lambda r: -float(r["value"]))
        for r in group_rows:
            v = float(r["value"])
            jitter = (rng.random() - 0.5) * jitter_w
            cx, cy = cx0 + jitter, y_for(v)
            rank = ranked.index(r) + 1
            tip = f"{g}: {v:.1f}"
            parts.append(
                f'<circle id="hit-{dot_idx}" class="dot hit" tabindex="0" cx="{cx:.1f}" cy="{cy:.1f}" r="4" '
                f'fill="{color}" fill-opacity="0.65" role="img" aria-label="{xml_escape(tip)}"/>'
            )
            bubbles.append(
                tooltip_bubble(
                    cx, cy - 14,
                    [g, f"{v:.1f}", f"#{rank} of {len(group_rows)} in {g}"],
                    anchor="middle", canvas_w=width, canvas_h=height,
                    ink=INK, secondary=SECONDARY, border=GRIDLINE,
                    elem_id=f"tip-{dot_idx}",
                )
            )
            dot_idx += 1

    # ---- x-axis ----
    axis_y = plot_y + plot_h
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{axis_y:.1f}" x2="{plot_x + plot_w:.1f}" y2="{axis_y:.1f}" '
        f'stroke="{INK}" stroke-width="1.2"/>'
    )
    for gi, g in enumerate(groups):
        tx = plot_x + gi * bin_w + bin_w / 2
        parts.append(
            f'<text x="{tx:.1f}" y="{axis_y + 20:.1f}" font-size="13" fill="{INK}" '
            f'text-anchor="middle">{xml_escape(g)}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{axis_y + 42:.1f}" font-size="13" '
        f'fill="{INK}" text-anchor="middle">Group</text>'
    )

    parts.extend(bubbles)
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_strip(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Response by Dose",
    subtitle: str = "Each dot is one observation, jittered within its group",
    width: int = 620,
    height: int = 480,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored strip plot and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``group`` (str) and ``value`` (float). Defaults to
        DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/strip.svg``.
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
    >>> p = make_strip()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility, theme=theme)
    dest = Path(out) if out else svg_example_path(__file__, "strip")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "strip", build_svg, description="Generate a strip plot.")


if __name__ == "__main__":
    main()
