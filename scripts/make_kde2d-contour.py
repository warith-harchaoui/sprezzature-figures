#!/usr/bin/env python3
"""
make_kde2d-contour — a house-styled 2-D kernel density contour plot as hand-authored SVG.

Smooths a 2-D scatter into a continuous density surface (a bivariate
Gaussian kernel at each point, summed onto a grid) and draws it as
isocontour lines -- concentric rings around each mode, closer together
where density changes fastest. The faint scatter underneath keeps the
raw data visible so the reader can sanity-check the smoothing against
the points it summarises. Typical uses: 2-D density of two continuous
variables, visualising where a bivariate sample concentrates.

Previously rendered via full Vega (the ``kde2d`` transform onto a grid,
then ``isocontour`` for marching-squares-style contour extraction,
``vl_convert``); this module now computes the 2-D KDE itself (numpy,
already a core dependency) and runs its own marching-squares contour
extraction -- no Vega, no matplotlib, no scipy, no d3-contour. Each
contour ring carries a native ``<title>`` tooltip with its density level.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _scale import nice_ticks_range  # noqa: E402
from _svg import fmt_number, svg_open, tooltip_bubble, xml_escape  # noqa: E402
from _style import BG, GRIDLINE, INK, SECONDARY  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

COLOR_POINT = "#C7C7CC"
COLOR_CONTOUR = "#007AFF"

# Marching-squares case -> which crossed edges to connect, keyed by corner
# bitmask (bit0=BL, bit1=BR, bit2=TR, bit3=TL, 1 = above the level). Cases 5
# and 10 are the ambiguous saddle configurations; either diagonal resolution
# is visually fine for a line contour (no fill to get wrong).
_CASE_EDGES: Dict[int, List[Tuple[str, str]]] = {
    1: [("l", "b")], 2: [("b", "r")], 3: [("l", "r")], 4: [("r", "t")],
    5: [("l", "b"), ("r", "t")], 6: [("b", "t")], 7: [("l", "t")],
    8: [("l", "t")], 9: [("b", "t")], 10: [("b", "r"), ("l", "t")],
    11: [("r", "t")], 12: [("l", "r")], 13: [("b", "r")], 14: [("l", "b")],
}


def _make_demo_data() -> List[Dict[str, Any]]:
    rng = random.Random(31)
    rows: List[Dict[str, Any]] = []
    for _ in range(220):
        rows.append({"x": rng.gauss(3.0, 1.0), "y": rng.gauss(2.0, 0.9)})
    for _ in range(90):
        rows.append({"x": rng.gauss(6.0, 0.7), "y": rng.gauss(4.5, 0.8)})
    return rows


DEMO_DATA: List[Dict[str, Any]] = _make_demo_data()


def _kde2d_grid(
    samples: np.ndarray, x_coords: np.ndarray, y_coords: np.ndarray,
) -> np.ndarray:
    """Evaluate a bivariate Gaussian KDE of *samples* on the *x*/*y* grid.

    Returns a ``(len(y_coords), len(x_coords))`` density array (row-major,
    matching typical grid/image indexing: ``grid[j][i]`` is the density at
    ``(x_coords[i], y_coords[j])``).
    """
    n = len(samples)
    std_x, std_y = samples[:, 0].std() or 1.0, samples[:, 1].std() or 1.0
    h_x = 0.9 * std_x * n ** (-1.0 / 6.0)
    h_y = 0.9 * std_y * n ** (-1.0 / 6.0)
    gx, gy = np.meshgrid(x_coords, y_coords)  # each (ny, nx)
    dx = (gx[..., None] - samples[None, None, :, 0]) / h_x
    dy = (gy[..., None] - samples[None, None, :, 1]) / h_y
    kernel = np.exp(-0.5 * (dx**2 + dy**2))
    return kernel.sum(axis=-1) / (n * h_x * h_y * 2.0 * np.pi)


def _marching_squares(
    grid: np.ndarray, level: float, x_coords: np.ndarray, y_coords: np.ndarray,
) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
    """Extract line segments where *grid* crosses *level* (marching squares)."""
    ny, nx = grid.shape
    segments: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
    for j in range(ny - 1):
        for i in range(nx - 1):
            x0, x1 = x_coords[i], x_coords[i + 1]
            y0, y1 = y_coords[j], y_coords[j + 1]
            v_bl, v_br = grid[j, i], grid[j, i + 1]
            v_tl, v_tr = grid[j + 1, i], grid[j + 1, i + 1]
            case = (
                (1 if v_bl > level else 0)
                | (2 if v_br > level else 0)
                | (4 if v_tr > level else 0)
                | (8 if v_tl > level else 0)
            )
            edges = _CASE_EDGES.get(case)
            if not edges:
                continue
            pts: Dict[str, Tuple[float, float]] = {}
            if (v_bl > level) != (v_br > level):
                t = (level - v_bl) / (v_br - v_bl)
                pts["b"] = (x0 + t * (x1 - x0), y0)
            if (v_br > level) != (v_tr > level):
                t = (level - v_br) / (v_tr - v_br)
                pts["r"] = (x1, y0 + t * (y1 - y0))
            if (v_tl > level) != (v_tr > level):
                t = (level - v_tl) / (v_tr - v_tl)
                pts["t"] = (x0 + t * (x1 - x0), y1)
            if (v_bl > level) != (v_tl > level):
                t = (level - v_bl) / (v_tl - v_bl)
                pts["l"] = (x0, y0 + t * (y1 - y0))
            for a, b in edges:
                if a in pts and b in pts:
                    segments.append((pts[a], pts[b]))
    return segments


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Two Modes, One Density Surface",
    subtitle: str = "2-D kernel density estimate, drawn as isocontours over the raw scatter",
    width: int = 745,
    height: int = 520,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full 2-D KDE contour plot SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``x``, ``y`` (numeric). Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    mode : str, optional
        Forwarded to :func:`_interactive.fullscreen_control`.
    accessibility : str, optional
        Accepted for CLI parity but a documented no-op: a single house-
        blue contour stroke, no categorical hues to re-level.
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
    rows = data if data else DEMO_DATA
    samples = np.array([[float(r["x"]), float(r["y"])] for r in rows])
    x_min, x_max = samples[:, 0].min(), samples[:, 0].max()
    y_min, y_max = samples[:, 1].min(), samples[:, 1].max()
    x_pad, y_pad = (x_max - x_min) * 0.15 or 1.0, (y_max - y_min) * 0.15 or 1.0
    x_lo, x_hi = x_min - x_pad, x_max + x_pad
    y_lo, y_hi = y_min - y_pad, y_max + y_pad

    grid_n = 55
    x_coords = np.linspace(x_lo, x_hi, grid_n)
    y_coords = np.linspace(y_lo, y_hi, grid_n)
    density = _kde2d_grid(samples, x_coords, y_coords)

    n_levels = 6
    d_min, d_max = density.min(), density.max()
    levels = [d_min + (d_max - d_min) * (i + 1) / (n_levels + 1) for i in range(n_levels)]

    plot_x, plot_y = 60.0, 118.0
    right_margin, bottom_reserved = 30.0, 60.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved

    def x_for(v: float) -> float:
        return plot_x + (v - x_lo) / (x_hi - x_lo) * plot_w

    def y_for(v: float) -> float:
        return plot_y + plot_h - (v - y_lo) / (y_hi - y_lo) * plot_h

    parts: List[str] = []
    parts.append(svg_open(width, height, "kdec-title", "kdec-desc", font_family=chrome_stack_for_theme(theme)))
    parts.append(f'<title id="kdec-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="kdec-desc">2-D kernel density contours of {len(rows)} points at '
        f'{n_levels} density levels.</desc>'
    )
    parts.append(
        "<style>"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        ".hit:hover+.tip,.hit:focus+.tip{opacity:1}"
        "@media (prefers-reduced-motion: reduce){.tip{transition:none}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="40" y="46" font-size="22" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(f'<text x="40" y="70" font-size="14" fill="{SECONDARY}">{xml_escape(subtitle)}</text>')

    # ---- gridlines + tick labels ----
    # Without these the reader can see the density shape but has no scale
    # reference at all (a real "hard to read" gap caught by visual review) --
    # ~5 nice, round ticks per axis (shared _scale.nice_ticks_range, already
    # adopted by make_beeswarm.py) instead of raw equal-fraction values,
    # which produced unreadable labels like 7.5/5.2/2.9/0.63/-1.7. Ticks
    # outside the padded window are dropped, drawn behind the data.
    mono_family = mono_stack_for_theme(theme)
    x_ticks = [t for t in nice_ticks_range(x_lo, x_hi, 5) if x_lo - 1e-9 <= t <= x_hi + 1e-9]
    y_ticks = [t for t in nice_ticks_range(y_lo, y_hi, 5) if y_lo - 1e-9 <= t <= y_hi + 1e-9]
    for xt in x_ticks:
        tx = x_for(xt)
        parts.append(
            f'<line x1="{tx:.1f}" y1="{plot_y:.1f}" x2="{tx:.1f}" y2="{plot_y + plot_h:.1f}" '
            f'stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{tx:.1f}" y="{plot_y + plot_h + 18:.1f}" font-size="11" '
            f'font-family="{mono_family}" fill="{SECONDARY}" text-anchor="middle">{fmt_number(xt)}</text>'
        )
    for yt in y_ticks:
        ty = y_for(yt)
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{ty:.1f}" x2="{plot_x + plot_w:.1f}" y2="{ty:.1f}" '
            f'stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{plot_x - 8:.1f}" y="{ty + 4:.1f}" font-size="11" '
            f'font-family="{mono_family}" fill="{SECONDARY}" text-anchor="end">{fmt_number(yt)}</text>'
        )

    # ---- raw scatter (faint) ----
    for x, y in samples:
        px, py = x_for(x), y_for(y)
        pt_tip = f"x={fmt_number(float(x))}, y={fmt_number(float(y))}"
        parts.append(
            f'<circle class="hit" tabindex="0" cx="{px:.1f}" cy="{py:.1f}" r="2" '
            f'fill="{COLOR_POINT}" fill-opacity="0.6"><title>{xml_escape(pt_tip)}</title></circle>'
        )
        parts.append(
            tooltip_bubble(
                px,
                max(4.0, py - 26.0),
                [f"x = {fmt_number(float(x))}", f"y = {fmt_number(float(y))}"],
                canvas_w=width,
                canvas_h=height,
                ink=INK,
                secondary=SECONDARY,
                border=GRIDLINE,
                font_size=10.5,
            )
        )

    # ---- contour levels ----
    for li, level in enumerate(levels):
        segments = _marching_squares(density, level, x_coords, y_coords)
        if not segments:
            continue
        opacity = 0.35 + 0.55 * (li / max(1, n_levels - 1))
        d_parts = [
            f"M {x_for(p0[0]):.1f},{y_for(p0[1]):.1f} L {x_for(p1[0]):.1f},{y_for(p1[1]):.1f}"
            for p0, p1 in segments
        ]
        path_d = " ".join(d_parts)
        tip = f"Density contour {li + 1} of {n_levels} (level {level:.4f})"
        parts.append(
            f'<path class="hit" tabindex="0" d="{path_d}" fill="none" stroke="{COLOR_CONTOUR}" '
            f'stroke-width="1.5" stroke-opacity="{opacity:.2f}"><title>{xml_escape(tip)}</title></path>'
        )
        cx_pts = [x_for(p0[0]) for p0, p1 in segments] + [x_for(p1[0]) for p0, p1 in segments]
        cy_pts = [y_for(p0[1]) for p0, p1 in segments] + [y_for(p1[1]) for p0, p1 in segments]
        anchor_x = sum(cx_pts) / len(cx_pts)
        anchor_y = min(cy_pts)
        parts.append(
            tooltip_bubble(
                anchor_x,
                max(4.0, anchor_y - 34.0),
                [f"Contour {li + 1} of {n_levels}", f"density level {level:.4f}"],
                canvas_w=width,
                canvas_h=height,
                ink=INK,
                secondary=SECONDARY,
                border=GRIDLINE,
            )
        )

    # ---- axes ----
    axis_y = plot_y + plot_h
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{axis_y:.1f}" x2="{plot_x + plot_w:.1f}" y2="{axis_y:.1f}" '
        f'stroke="{INK}" stroke-width="1.2"/>'
    )
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{plot_y:.1f}" x2="{plot_x:.1f}" y2="{axis_y:.1f}" '
        f'stroke="{INK}" stroke-width="1.2"/>'
    )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{axis_y + 30:.1f}" font-size="13" '
        f'fill="{INK}" text-anchor="middle">x</text>'
    )
    parts.append(
        f'<text x="22" y="{plot_y + plot_h / 2:.1f}" font-size="13" fill="{INK}" '
        f'text-anchor="middle" transform="rotate(-90 22 {plot_y + plot_h / 2:.1f})">y</text>'
    )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_kde2d_contour(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Two Modes, One Density Surface",
    subtitle: str = "2-D kernel density estimate, drawn as isocontours over the raw scatter",
    width: int = 745,
    height: int = 520,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored 2-D KDE contour plot and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``x``, ``y`` (float). Defaults to DEMO_DATA (two
        overlapping synthetic clusters).
    out : Path, str, or None
        Output path (.svg). Defaults to
        ``assets/svg-examples/kde2d-contour.svg``.
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
    >>> p = make_kde2d_contour()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility, theme=theme)
    dest = Path(out) if out else svg_example_path(__file__, "kde2d-contour")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "kde2d-contour", build_svg, description="Generate a 2-D kernel density contour plot.")


if __name__ == "__main__":
    main()
