#!/usr/bin/env python3
"""
make_hexbin — a house-styled hexagonal binning plot as hand-authored SVG.

Aggregates a dense scatter of points into a hexagonal grid, colouring each
cell by how many points fall inside it. Hexagons tile the plane with less
visual bias than square bins (every neighbour is equidistant) and read as
a smoother density surface than a raw scatter once point count climbs
into the thousands. Typical uses: overplotted scatter data, 2-D density
of any two continuous variables.

Previously rendered via Vega-Lite (points pre-binned offline into hexagon
centres + counts, then drawn with a fixed hexagon-shaped point mark,
``vl_convert``); this module now runs the binning itself -- axial hex-grid
assignment via the standard flat-top axial-round algorithm -- on raw
scatter points, and paints true hexagon cells by hand. No Vega, no
matplotlib. Every cell carries a native ``<title>`` tooltip with its count.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import math
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _svg import svg_open, xml_escape  # noqa: E402
from _style import BG, INK, SECONDARY  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme  # noqa: E402


_RAMP: Tuple[Tuple[float, str], ...] = (
    (0.00, "#EAF3FF"), (0.25, "#9CC7FF"), (0.55, "#3E9BFF"),
    (0.80, "#007AFF"), (1.00, "#0A4DA0"),
)


def _ramp_hex(t: float) -> str:
    """Sample the house blue ramp at position ``t`` in ``[0, 1]``."""
    t = min(1.0, max(0.0, t))
    for (lo_t, lo_c), (hi_t, hi_c) in zip(_RAMP, _RAMP[1:]):
        if lo_t <= t <= hi_t:
            local = (t - lo_t) / (hi_t - lo_t) if hi_t > lo_t else 0.0
            ar, ag, ab = int(lo_c[1:3], 16), int(lo_c[3:5], 16), int(lo_c[5:7], 16)
            br, bg, bb = int(hi_c[1:3], 16), int(hi_c[3:5], 16), int(hi_c[5:7], 16)
            r = round(ar + (br - ar) * local)
            g = round(ag + (bg - ag) * local)
            b = round(ab + (bb - ab) * local)
            return f"#{r:02X}{g:02X}{b:02X}"
    return _RAMP[-1][1]


def _make_demo_data() -> List[Dict[str, Any]]:
    """Two overlapping bivariate-normal clusters, so the binned density
    shows a genuine two-lobe structure rather than a single blob."""
    rng = random.Random(9)
    rows: List[Dict[str, Any]] = []
    for _ in range(650):
        rows.append({"x": rng.gauss(2.0, 1.1), "y": rng.gauss(2.5, 1.0)})
    for _ in range(450):
        rows.append({"x": rng.gauss(5.5, 0.9), "y": rng.gauss(4.5, 1.2)})
    return rows


DEMO_DATA: List[Dict[str, Any]] = _make_demo_data()

_SQRT3 = math.sqrt(3.0)


def _axial_round(q: float, r: float) -> Tuple[int, int]:
    s = -q - r
    rq, rr, rs = round(q), round(r), round(s)
    q_diff, r_diff, s_diff = abs(rq - q), abs(rr - r), abs(rs - s)
    if q_diff > r_diff and q_diff > s_diff:
        rq = -rr - rs
    elif r_diff > s_diff:
        rr = -rq - rs
    return int(rq), int(rr)


def _hex_bin(points: List[Tuple[float, float]], size: float) -> Dict[Tuple[int, int], int]:
    """Bin points into a flat-top axial hex grid of the given radius."""
    counts: Dict[Tuple[int, int], int] = defaultdict(int)
    for px, py in points:
        q = (2.0 / 3.0 * px) / size
        r = (-1.0 / 3.0 * px + _SQRT3 / 3.0 * py) / size
        cell = _axial_round(q, r)
        counts[cell] += 1
    return counts


def _hex_center(q: int, r: int, size: float) -> Tuple[float, float]:
    x = size * (1.5 * q)
    y = size * (_SQRT3 / 2.0 * q + _SQRT3 * r)
    return x, y


def _hex_corners(cx: float, cy: float, size: float) -> List[Tuple[float, float]]:
    return [
        (cx + size * math.cos(math.radians(60 * i)), cy + size * math.sin(math.radians(60 * i)))
        for i in range(6)
    ]


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Where the Points Pile Up",
    subtitle: str = "Hexagonally binned scatter, cell colour is the point count",
    width: int = 745,
    height: int = 480,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full hexbin plot SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Raw scatter rows with keys ``x``, ``y`` (numeric). Defaults to
        :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    mode : str, optional
        Forwarded to :func:`_interactive.fullscreen_control`.
    accessibility : str, optional
        Accepted for CLI parity but a documented no-op: the ramp is a
        single mono-hue blue scale, already colour-vision-deficiency-safe
        by construction (magnitude reads by lightness alone).
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
    points = [(float(r["x"]), float(r["y"])) for r in rows]
    x_min, x_max = min(p[0] for p in points), max(p[0] for p in points)
    y_min, y_max = min(p[1] for p in points), max(p[1] for p in points)

    plot_x, plot_y = 60.0, 118.0
    right_margin, bottom_reserved = 30.0, 60.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved

    data_span_x = (x_max - x_min) or 1.0
    hex_size = data_span_x / 22.0

    counts = _hex_bin(points, hex_size)
    max_count = max(counts.values()) if counts else 1

    def x_for(v: float) -> float:
        return plot_x + (v - x_min) / data_span_x * plot_w

    def y_for(v: float) -> float:
        return plot_y + plot_h - (v - y_min) / ((y_max - y_min) or 1.0) * plot_h

    # Scale factor from data units to screen pixels (assume roughly
    # isotropic mapping is close enough for a hex plot's visual purpose).
    px_per_unit_x = plot_w / data_span_x
    hex_size_px = hex_size * px_per_unit_x

    parts: List[str] = []
    parts.append(svg_open(width, height, "hex-title", "hex-desc", font_family=chrome_stack_for_theme(theme)))
    parts.append(f'<title id="hex-title">{xml_escape(title)}</title>')
    n_cells = len(counts)
    parts.append(
        f'<desc id="hex-desc">Hexbin of {len(points)} points into {n_cells} cells, densest cell '
        f'{max_count}. Hover or focus a cell for its exact count.</desc>'
    )
    parts.append(
        "<style>"
        ".hex{transition:opacity .15s ease;}"
        ".hex:hover,.hex:focus{opacity:.72;outline:none;}"
        "@media (prefers-reduced-motion: reduce){.hex{transition:none;}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="40" y="46" font-size="22" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(f'<text x="40" y="70" font-size="14" fill="{SECONDARY}">{xml_escape(subtitle)}</text>')

    for (q, r), count in counts.items():
        hx, hy = _hex_center(q, r, hex_size)
        cx, cy = x_for(x_min + hx), y_for(y_min + hy)
        corners = _hex_corners(cx, cy, hex_size_px * 1.02)
        d = "M " + " L ".join(f"{px:.1f},{py:.1f}" for px, py in corners) + " Z"
        t = count / max_count
        tip = f"{count} point{'s' if count != 1 else ''} in this cell"
        parts.append(
            f'<path class="hex" tabindex="0" d="{d}" fill="{_ramp_hex(t)}">'
            f'<title>{xml_escape(tip)}</title></path>'
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

    # ---- legend ----
    ly = height - 12.0
    lx0 = plot_x
    parts.append(f'<text x="{lx0:.1f}" y="{ly:.1f}" font-size="11" fill="{SECONDARY}">0</text>')
    swatch_x = lx0 + 18.0
    n_swatches = 8
    for i in range(n_swatches):
        t = i / (n_swatches - 1)
        parts.append(f'<rect x="{swatch_x + i * 16:.1f}" y="{ly - 11:.1f}" width="14" height="12" fill="{_ramp_hex(t)}"/>')
    parts.append(
        f'<text x="{swatch_x + n_swatches * 16 + 6:.1f}" y="{ly:.1f}" font-size="11" '
        f'fill="{SECONDARY}">{max_count} (Count)</text>'
    )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_hexbin(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Where the Points Pile Up",
    subtitle: str = "Hexagonally binned scatter, cell colour is the point count",
    width: int = 745,
    height: int = 480,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored hexbin plot and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Raw scatter rows with keys ``x``, ``y`` (float). Defaults to
        DEMO_DATA (two overlapping synthetic clusters).
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/hexbin.svg``.
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
    >>> p = make_hexbin()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility, theme=theme)
    dest = Path(out) if out else svg_example_path(__file__, "hexbin")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "hexbin", build_svg, description="Generate a hexagonal binning plot.")


if __name__ == "__main__":
    main()
