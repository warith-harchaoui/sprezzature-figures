#!/usr/bin/env python3
"""
make_errorbar — a house-styled error bar chart as hand-authored SVG.

Plots a point estimate per category with a capped vertical bar spanning
its uncertainty interval (a 95% confidence interval, a standard
deviation, a min-max range -- whatever the caller's ``lo``/``hi`` mean).
The default chart for "here's the number, and here's how sure we are"
across a handful of groups: A/B test lifts, experiment arms, survey
means by cohort.

Previously rendered via Vega-Lite (a layered ``rule`` + ``point`` mark,
``vl_convert``); this module now paints the whisker, caps, and point by
hand -- no Vega, no matplotlib. Every error bar carries a native
``<title>`` tooltip with the mean and interval.

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
from _svg import svg_open, xml_escape  # noqa: E402
from _style import BG, GRIDLINE, INK, SECONDARY  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

COLOR_POINT = "#007AFF"

DEMO_DATA: List[Dict[str, Any]] = [
    {"g": "A", "mean": 40, "lo": 34, "hi": 46},
    {"g": "B", "mean": 55, "lo": 47, "hi": 63},
    {"g": "C", "mean": 48, "lo": 43, "hi": 53},
    {"g": "D", "mean": 67, "lo": 57, "hi": 77},
]


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Mean with 95% Interval",
    subtitle: str = "Point estimate per group, capped bar spans the confidence interval",
    width: int = 620,
    height: int = 420,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full error bar chart SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``g`` (str), ``mean``, ``lo``, ``hi`` (numeric).
        Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    mode : str, optional
        Forwarded to :func:`_interactive.fullscreen_control`.
    accessibility : str, optional
        Accepted for CLI parity but a documented no-op: a single house-
        blue point/whisker, no categorical hues to re-level.
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
    rows = data if data else DEMO_DATA
    los = [float(r["lo"]) for r in rows]
    his = [float(r["hi"]) for r in rows]
    v_min, v_max = min(los), max(his)
    pad = (v_max - v_min) * 0.15 or 1.0

    plot_x, plot_y = 64.0, 118.0
    right_margin, bottom_reserved = 30.0, 60.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved
    n = len(rows)
    bin_w = plot_w / n if n else plot_w
    cap_w = min(28.0, bin_w * 0.3)

    def y_for(v: float) -> float:
        return plot_y + plot_h - (v - (v_min - pad)) / ((v_max + pad) - (v_min - pad)) * plot_h

    parts: List[str] = []
    parts.append(svg_open(width, height, "eb-title", "eb-desc", font_family=chrome_stack_for_theme(theme)))
    parts.append(f'<title id="eb-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="eb-desc">Error bar chart of {n} groups. Hover or focus a bar for its '
        f'exact mean and interval.</desc>'
    )
    parts.append(
        "<style>"
        ".errbar{transition:opacity .15s ease;}"
        ".errbar:hover,.errbar:focus{opacity:.72;outline:none;}"
        "@media (prefers-reduced-motion: reduce){.errbar{transition:none;}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="40" y="46" font-size="22" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(f'<text x="40" y="70" font-size="14" fill="{SECONDARY}">{xml_escape(subtitle)}</text>')

    # ---- y-axis gridlines ----
    y_ticks = 5
    for i in range(y_ticks + 1):
        val = (v_min - pad) + ((v_max + pad) - (v_min - pad)) * i / y_ticks
        ty = y_for(val)
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{ty:.1f}" x2="{plot_x + plot_w:.1f}" y2="{ty:.1f}" '
            f'stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{ty + 4:.1f}" font-size="12" font-family="{mono_family}" '
            f'fill="{SECONDARY}" text-anchor="end">{val:.0f}</text>'
        )
    parts.append(
        f'<text x="18" y="{plot_y + plot_h / 2:.1f}" font-size="13" fill="{INK}" '
        f'text-anchor="middle" transform="rotate(-90 18 {plot_y + plot_h / 2:.1f})">Value</text>'
    )

    # ---- error bars ----
    for i, r in enumerate(rows):
        cx = plot_x + i * bin_w + bin_w / 2
        y_lo, y_hi = y_for(float(r["lo"])), y_for(float(r["hi"]))
        y_mean = y_for(float(r["mean"]))
        tip = f"{r['g']}: mean {float(r['mean']):.0f} (95% CI {float(r['lo']):.0f}-{float(r['hi']):.0f})"
        parts.append('<g class="errbar" tabindex="0">')
        parts.append(f'<title>{xml_escape(tip)}</title>')
        parts.append(f'<line x1="{cx:.1f}" y1="{y_lo:.1f}" x2="{cx:.1f}" y2="{y_hi:.1f}" stroke="{INK}" stroke-width="1.5"/>')
        parts.append(f'<line x1="{cx - cap_w / 2:.1f}" y1="{y_lo:.1f}" x2="{cx + cap_w / 2:.1f}" y2="{y_lo:.1f}" stroke="{INK}" stroke-width="1.5"/>')
        parts.append(f'<line x1="{cx - cap_w / 2:.1f}" y1="{y_hi:.1f}" x2="{cx + cap_w / 2:.1f}" y2="{y_hi:.1f}" stroke="{INK}" stroke-width="1.5"/>')
        parts.append(f'<circle cx="{cx:.1f}" cy="{y_mean:.1f}" r="6" fill="{COLOR_POINT}" stroke="{BG}" stroke-width="1.5"/>')
        parts.append("</g>")

    # ---- x-axis ----
    axis_y = plot_y + plot_h
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{axis_y:.1f}" x2="{plot_x + plot_w:.1f}" y2="{axis_y:.1f}" '
        f'stroke="{INK}" stroke-width="1.2"/>'
    )
    for i, r in enumerate(rows):
        tx = plot_x + i * bin_w + bin_w / 2
        parts.append(
            f'<text x="{tx:.1f}" y="{axis_y + 20:.1f}" font-size="13" fill="{INK}" '
            f'text-anchor="middle">{xml_escape(str(r["g"]))}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{axis_y + 42:.1f}" font-size="13" '
        f'fill="{INK}" text-anchor="middle">Group</text>'
    )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_errorbar(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Mean with 95% Interval",
    subtitle: str = "Point estimate per group, capped bar spans the confidence interval",
    width: int = 620,
    height: int = 420,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored error bar chart and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``g`` (str), ``mean``, ``lo``, ``hi`` (float).
        Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/errorbar.svg``.
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
    >>> p = make_errorbar()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility, theme=theme)
    dest = Path(out) if out else svg_example_path(__file__, "errorbar")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "errorbar", build_svg, description="Generate an error bar chart.")


if __name__ == "__main__":
    main()
