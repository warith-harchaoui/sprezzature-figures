#!/usr/bin/env python3
"""
make_step — a house-styled step line chart as hand-authored SVG.

Connects each point with a horizontal-then-vertical (step-after) line
rather than a straight diagonal, so the chart never implies a value in
between two measured states -- exactly right for anything that holds a
value constant until it changes, then jumps. Typical uses: inventory
level after each transaction, a state machine's value over discrete
steps, a price that only updates on trade, any piecewise-constant series.

Previously rendered via Vega-Lite (``interpolate: "step-after"``,
``vl_convert``); this module now builds the step path itself and paints
it by hand -- no Vega, no matplotlib. Every point carries a native
``<title>`` tooltip.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _scale import nice_ticks_range  # noqa: E402
from _svg import svg_open, tooltip_bubble, xml_escape  # noqa: E402
from _style import BG, GRIDLINE, INK, SECONDARY  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

COLOR_LINE = "#007AFF"

DEMO_DATA: List[Dict[str, Any]] = [
    {"t": 0, "y": 2}, {"t": 1, "y": 2}, {"t": 2, "y": 5}, {"t": 3, "y": 5}, {"t": 4, "y": 4},
    {"t": 5, "y": 7}, {"t": 6, "y": 7}, {"t": 7, "y": 6}, {"t": 8, "y": 9}, {"t": 9, "y": 9},
]


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Cumulative State Changes",
    subtitle: str = "Step-after interpolation: the value holds until it changes",
    width: int = 745,
    height: int = 420,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full step chart SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``t``, ``y`` (numeric). Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    mode : str, optional
        Forwarded to :func:`_interactive.fullscreen_control`.
    accessibility : str, optional
        Accepted for CLI parity but a documented no-op: a single house-
        blue step series, no categorical hues to re-level.
    theme : str, optional
        Visual theme: ``"corporate"`` (default, Roboto -- byte-identical to
        the pre-theme render) or ``"academic"`` (LaTeX-style Latin Modern).
        See :func:`sprezzature_figures.fonts.chrome_stack_for_theme`.

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    _ = accessibility
    mono_family = mono_stack_for_theme(theme)
    rows = sorted(data if data else DEMO_DATA, key=lambda r: float(r["t"]))
    ts = [float(r["t"]) for r in rows]
    ys = [float(r["y"]) for r in rows]
    t_min, t_max = min(ts), max(ts)
    raw_y_min, raw_y_max = min(ys), max(ys)
    y_pad = (raw_y_max - raw_y_min) * 0.15 or 1.0
    y_gridline_vals = nice_ticks_range(raw_y_min - y_pad, raw_y_max + y_pad, 5)
    y_min, y_max = y_gridline_vals[0], y_gridline_vals[-1]

    plot_x, plot_y = 60.0, 118.0
    right_margin, bottom_reserved = 30.0, 60.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved

    def x_for(v: float) -> float:
        return plot_x + (v - t_min) / ((t_max - t_min) or 1.0) * plot_w

    def y_for(v: float) -> float:
        return plot_y + plot_h - (v - y_min) / ((y_max - y_min) or 1.0) * plot_h

    parts: List[str] = []
    parts.append(svg_open(width, height, "step-title", "step-desc", font_family=chrome_stack_for_theme(theme)))
    parts.append(f'<title id="step-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="step-desc">Step chart of {len(rows)} points, ranging {y_min:.0f} to '
        f'{y_max:.0f}. Hover or focus a point for its exact value.</desc>'
    )
    parts.append(
        "<style>"
        ".pt{transition:r .12s ease;}"
        ".pt:hover,.pt:focus{r:5.5;outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        ".hit:hover+.tip,.hit:focus+.tip{opacity:1}"
        "@media (prefers-reduced-motion: reduce){.pt{transition:none;}"
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
        f'text-anchor="middle" transform="rotate(-90 18 {plot_y + plot_h / 2:.1f})">Value</text>'
    )

    # ---- step-after path ----
    step_pts: List[Tuple[float, float]] = []
    for i, (t, y) in enumerate(zip(ts, ys)):
        x, sy = x_for(t), y_for(y)
        if step_pts:
            step_pts.append((x, step_pts[-1][1]))
        step_pts.append((x, sy))
    path_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in step_pts)
    parts.append(f'<path d="{path_d}" fill="none" stroke="{COLOR_LINE}" stroke-width="2.5"/>')
    prev_y: float | None = None
    for t, y in zip(ts, ys):
        cx, cy = x_for(t), y_for(y)
        tip = f"t={t:.0f}: {y:.0f}"
        parts.append(
            f'<circle class="pt hit" tabindex="0" cx="{cx:.1f}" cy="{cy:.1f}" r="4" fill="{COLOR_LINE}" '
            f'stroke="{BG}" stroke-width="1.5" role="img" aria-label="{xml_escape(tip)}"/>'
        )
        delta_line = "start of series" if prev_y is None else f"{'+' if y - prev_y >= 0 else ''}{y - prev_y:.0f} from previous step"
        parts.append(
            tooltip_bubble(
                cx, cy - 16,
                [f"t = {t:.0f}", f"value {y:.0f}", delta_line],
                anchor="middle", canvas_w=width, canvas_h=height,
                ink=INK, secondary=SECONDARY, border=GRIDLINE,
            )
        )
        prev_y = y

    # ---- x-axis ----
    axis_y = plot_y + plot_h
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{axis_y:.1f}" x2="{plot_x + plot_w:.1f}" y2="{axis_y:.1f}" '
        f'stroke="{INK}" stroke-width="1.2"/>'
    )
    for t in ts:
        parts.append(
            f'<text x="{x_for(t):.1f}" y="{axis_y + 20:.1f}" font-size="11" font-family="{mono_family}" '
            f'fill="{SECONDARY}" text-anchor="middle">{t:.0f}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{axis_y + 42:.1f}" font-size="13" '
        f'fill="{INK}" text-anchor="middle">Step</text>'
    )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_step(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Cumulative State Changes",
    subtitle: str = "Step-after interpolation: the value holds until it changes",
    width: int = 745,
    height: int = 420,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored step chart and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``t``, ``y`` (float). Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/step.svg``.
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
    >>> p = make_step()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility, theme=theme)
    dest = Path(out) if out else svg_example_path(__file__, "step")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "step", build_svg, description="Generate a step (piecewise-constant) line chart.")


if __name__ == "__main__":
    main()
