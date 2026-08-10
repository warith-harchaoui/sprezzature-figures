#!/usr/bin/env python3
"""
make_volcano — a house-styled volcano plot as hand-authored SVG.

Scatters effect size (log2 fold-change) against statistical significance
(-log10 p-value) for many simultaneous tests, with dashed threshold lines
marking the fold-change and significance cutoffs -- so points earning
both a large enough effect and a small enough p-value fall into the two
upper corners ("Up"/"Down") that the eye reads as a volcano's rising
sides. The standard chart for differential-expression results in
genomics, and equally usable for any large multiple-testing comparison.

Previously rendered via Vega-Lite (a plain coloured ``point`` mark,
significance pre-classified offline, ``vl_convert``); this module now
classifies each point against the same thresholds it draws and paints
the scatter plus threshold lines by hand -- no Vega, no matplotlib.
Every point carries a native ``<title>`` tooltip.

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
from _svg import svg_open, xml_escape  # noqa: E402
from _style import BG, GRIDLINE, INK, SECONDARY  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

COLOR_UP = "#FF3B30"
COLOR_DOWN = "#007AFF"
COLOR_NS = "#C7C7CC"
COLOR_THRESHOLD = "#AEAEB2"

LFC_THRESHOLD = 1.0
P_THRESHOLD = 1.3  # -log10(0.05)


def _make_demo_data() -> List[Dict[str, Any]]:
    rng = random.Random(29)
    rows: List[Dict[str, Any]] = []
    for _ in range(240):
        lfc = rng.gauss(0.0, 0.9)
        # p-values correlate loosely with |effect size|, plus noise, like real DE data.
        neglogp = max(0.0, abs(lfc) * rng.uniform(0.6, 1.8) + rng.gauss(0.0, 0.4))
        rows.append({"lfc": round(lfc, 2), "neglogp": round(neglogp, 2)})
    # A cluster of genuinely significant up/down genes so the volcano shape is visible.
    for _ in range(22):
        rows.append({"lfc": round(rng.uniform(1.2, 3.2), 2), "neglogp": round(rng.uniform(1.5, 5.0), 2)})
    for _ in range(18):
        rows.append({"lfc": round(rng.uniform(-3.2, -1.2), 2), "neglogp": round(rng.uniform(1.5, 5.0), 2)})
    return rows


DEMO_DATA: List[Dict[str, Any]] = _make_demo_data()


def _classify(lfc: float, neglogp: float) -> str:
    if neglogp < P_THRESHOLD:
        return "n.s."
    if lfc >= LFC_THRESHOLD:
        return "Up"
    if lfc <= -LFC_THRESHOLD:
        return "Down"
    return "n.s."


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Differential Expression",
    subtitle: str = "log2 fold change vs. significance, thresholds dashed",
    width: int = 620,
    height: int = 520,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full volcano plot SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``lfc`` (log2 fold-change) and ``neglogp``
        (-log10 p-value), both numeric. Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    mode : str, optional
        Forwarded to :func:`_interactive.fullscreen_control`.
    accessibility : str, optional
        Accepted for CLI parity but a documented no-op: Up/Down/n.s. is a
        fixed three-colour semantic, not a re-levelled palette.
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
    lfcs = [float(r["lfc"]) for r in rows]
    ps = [float(r["neglogp"]) for r in rows]
    x_min, x_max = min(min(lfcs), -LFC_THRESHOLD * 1.4), max(max(lfcs), LFC_THRESHOLD * 1.4)
    y_min, y_max = 0.0, max(max(ps), P_THRESHOLD * 1.3)
    x_pad = (x_max - x_min) * 0.06 or 1.0
    y_pad = (y_max - y_min) * 0.08 or 1.0

    plot_x, plot_y = 60.0, 118.0
    right_margin, bottom_reserved = 30.0, 60.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved

    def x_for(v: float) -> float:
        return plot_x + (v - (x_min - x_pad)) / ((x_max + x_pad) - (x_min - x_pad)) * plot_w

    def y_for(v: float) -> float:
        return plot_y + plot_h - (v - (y_min - y_pad)) / ((y_max + y_pad) - (y_min - y_pad)) * plot_h

    colors = {"Up": COLOR_UP, "Down": COLOR_DOWN, "n.s.": COLOR_NS}
    n_up = sum(1 for l, p in zip(lfcs, ps) if _classify(l, p) == "Up")
    n_down = sum(1 for l, p in zip(lfcs, ps) if _classify(l, p) == "Down")

    parts: List[str] = []
    parts.append(svg_open(width, height, "volc-title", "volc-desc", font_family=chrome_stack_for_theme(theme)))
    parts.append(f'<title id="volc-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="volc-desc">Volcano plot of {len(rows)} tests: {n_up} up, {n_down} down, '
        f'rest not significant. Hover or focus a point for its exact values.</desc>'
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
    for label in ("Down", "n.s.", "Up"):
        parts.append(f'<circle cx="{cursor + 5:.1f}" cy="{ly - 4:.1f}" r="5" fill="{colors[label]}"/>')
        parts.append(f'<text x="{cursor + 16:.1f}" y="{ly:.1f}" font-size="12" fill="{INK}">{xml_escape(label)}</text>')
        cursor += 16 + 7.0 * len(label) + 20

    # ---- gridlines ----
    y_ticks = 5
    for i in range(y_ticks + 1):
        val = (y_min - y_pad) + ((y_max + y_pad) - (y_min - y_pad)) * i / y_ticks
        ty = y_for(val)
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{ty:.1f}" x2="{plot_x + plot_w:.1f}" y2="{ty:.1f}" '
            f'stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{ty + 4:.1f}" font-size="11" font-family="{mono_family}" '
            f'fill="{SECONDARY}" text-anchor="end">{val:.1f}</text>'
        )
    parts.append(
        f'<text x="18" y="{plot_y + plot_h / 2:.1f}" font-size="13" fill="{INK}" '
        f'text-anchor="middle" transform="rotate(-90 18 {plot_y + plot_h / 2:.1f})">-log10 p</text>'
    )

    # ---- threshold lines ----
    for v in (-LFC_THRESHOLD, LFC_THRESHOLD):
        tx = x_for(v)
        parts.append(
            f'<line x1="{tx:.1f}" y1="{plot_y:.1f}" x2="{tx:.1f}" y2="{plot_y + plot_h:.1f}" '
            f'stroke="{COLOR_THRESHOLD}" stroke-width="1.3" stroke-dasharray="4 3"/>'
        )
    ty = y_for(P_THRESHOLD)
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{ty:.1f}" x2="{plot_x + plot_w:.1f}" y2="{ty:.1f}" '
        f'stroke="{COLOR_THRESHOLD}" stroke-width="1.3" stroke-dasharray="4 3"/>'
    )

    # ---- points ----
    for r in rows:
        lfc, p = float(r["lfc"]), float(r["neglogp"])
        sig = _classify(lfc, p)
        cx, cy = x_for(lfc), y_for(p)
        tip = f"log2FC {lfc:.2f}, -log10p {p:.2f} ({sig})"
        parts.append(
            f'<circle tabindex="0" cx="{cx:.1f}" cy="{cy:.1f}" r="3.5" fill="{colors[sig]}" '
            f'fill-opacity="0.7"><title>{xml_escape(tip)}</title></circle>'
        )

    # ---- x-axis ----
    axis_y = plot_y + plot_h
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{axis_y:.1f}" x2="{plot_x + plot_w:.1f}" y2="{axis_y:.1f}" '
        f'stroke="{INK}" stroke-width="1.2"/>'
    )
    x_ticks = 6
    for i in range(x_ticks + 1):
        val = (x_min - x_pad) + ((x_max + x_pad) - (x_min - x_pad)) * i / x_ticks
        tx = x_for(val)
        parts.append(
            f'<text x="{tx:.1f}" y="{axis_y + 20:.1f}" font-size="11" font-family="{mono_family}" '
            f'fill="{SECONDARY}" text-anchor="middle">{val:.1f}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{axis_y + 42:.1f}" font-size="13" '
        f'fill="{INK}" text-anchor="middle">log2 fold change</text>'
    )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_volcano(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Differential Expression",
    subtitle: str = "log2 fold change vs. significance, thresholds dashed",
    width: int = 620,
    height: int = 520,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored volcano plot and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``lfc`` (float) and ``neglogp`` (float). Defaults
        to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/volcano.svg``.
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
    >>> p = make_volcano()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility, theme=theme)
    dest = Path(out) if out else svg_example_path(__file__, "volcano")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "volcano", build_svg, description="Generate a volcano plot.")


if __name__ == "__main__":
    main()
