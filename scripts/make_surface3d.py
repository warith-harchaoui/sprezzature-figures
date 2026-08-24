#!/usr/bin/env python3
"""
make_surface3d — a hand-authored 3-D surface as a static isometric SVG.

A single central peak sampled on a regular grid, rotated in 3-D, projected with
a light perspective camera, and drawn as depth-sorted filled quads shaded by
height (a blue ramp), with a thin mesh and a height legend. No matplotlib, no
Vega: the geometry is computed directly and emitted as SVG, exactly like the
sibling 3-D heroes (wireframe3d / scatter3d / bar3d).

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _svg import svg_open, tooltip_bubble  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _interactive import fullscreen_control  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme  # noqa: E402

_WIDTH = 900
_HEIGHT = 680
_INK = "#1D1D1F"
_SUBTLE = "#6E6E73"
_BG = "#FFFFFF"
_MESH = "#FFFFFF"

# Blue height ramp (low -> high).
_LO = (234, 243, 255)   # #EAF3FF
_HI = (10, 77, 160)     # #0A4DA0

_ELEV = 24.0
_AZIM = -58.0
_N = 30                 # grid resolution


def _shade(t: float) -> str:
    t = max(0.0, min(1.0, t))
    r = round(_LO[0] + (_HI[0] - _LO[0]) * t)
    g = round(_LO[1] + (_HI[1] - _LO[1]) * t)
    b = round(_LO[2] + (_HI[2] - _LO[2]) * t)
    return f"#{r:02X}{g:02X}{b:02X}"


def _rotate(pts: np.ndarray, elev_deg: float, azim_deg: float) -> np.ndarray:
    """Rotate model points about z (azimuth) then x (elevation tip)."""
    az, el = np.radians(azim_deg), np.radians(elev_deg)
    ca, sa, ce, se = np.cos(az), np.sin(az), np.cos(el), np.sin(el)
    x, y, z = pts[:, 0], pts[:, 1], pts[:, 2]
    x1, y1 = ca * x - sa * y, sa * x + ca * y
    y2, z2 = ce * y1 - se * z, se * y1 + ce * z
    return np.column_stack([x1, y2, z2])


def _sample() -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """A central-peak surface on a regular grid; z runs about -1 .. 3."""
    g = np.linspace(-1.4, 1.4, _N)
    xx, yy = np.meshgrid(g, g)
    zz = 3.0 * np.exp(-(xx ** 2 + yy ** 2) / 0.45) - 0.9
    return xx, yy, zz


#: Row records: the flattened :func:`_sample` grid, one dict per vertex
#: with ``x``, ``y`` and ``z``. The contract's required row shape for a
#: figure whose natural data is a ``z = f(x, y)`` grid.
DEMO_DATA: List[Dict[str, float]] = [
    {"x": float(x), "y": float(y), "z": float(z)}
    for x, y, z in zip(*(a.ravel() for a in _sample()))
]


def _rows_to_grid(rows: List[Dict[str, float]]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Reshape ``{"x", "y", "z"}`` row records back into a regular grid.

    Requires the rows to form a complete rectangular grid (every ``x`` paired
    with every ``y``); raises otherwise, since the depth-sorted-quad renderer
    needs a regular lattice.

    Parameters
    ----------
    rows : list of dict
        Row records with ``x``, ``y`` and ``z`` keys.

    Returns
    -------
    tuple of numpy.ndarray
        ``(xx, yy, zz)``, matching the shape :func:`_sample` returns.
    """
    xs = sorted({float(r["x"]) for r in rows})
    ys = sorted({float(r["y"]) for r in rows})
    if len(xs) * len(ys) != len(rows):
        raise ValueError(
            "make_surface3d requires `data` to form a complete rectangular "
            f"x/y grid ({len(xs)} x-values x {len(ys)} y-values != {len(rows)} rows)"
        )
    lookup = {(float(r["x"]), float(r["y"])): float(r["z"]) for r in rows}
    xx, yy = np.meshgrid(xs, ys)
    zz = np.array([[lookup[(x, y)] for x in xs] for y in ys])
    return xx, yy, zz


def build_svg(
    data: Optional[List[Dict[str, float]]] = None,
    z_axis_title: str = "Height",
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full 3-D surface SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Row records with ``x``, ``y`` and ``z``, forming a complete
        rectangular grid. Defaults to :data:`DEMO_DATA`.
    z_axis_title : str
        Label above the height colour-bar legend (was hardcoded ``"Height"``).
    mode, accessibility : str
        Forwarded to :func:`_interactive.fullscreen_control` /
        palette selection (accessibility is a documented no-op here — see
        below).
    theme : str, optional
        Visual theme: ``"corporate"`` (default, Roboto -- byte-identical to
        the pre-theme render) or ``"academic"`` (LaTeX-style Latin Modern).
        See :func:`sprezzature_figures.fonts.chrome_stack_for_theme`.
    """
    _ = accessibility  # single blue height ramp reads in greyscale / CVD
    xx, yy, zz = _rows_to_grid(list(data)) if data else _sample()
    n_rows, n_cols = zz.shape
    zmin, zmax = float(zz.min()), float(zz.max())

    cx, cy = 500.0, 380.0
    plot_w = 560.0
    pts = np.column_stack([xx.ravel(), yy.ravel(), (zz * 0.6).ravel()])
    cam = _rotate(pts, _ELEV, _AZIM)
    cxm, cym, czm = cam[:, 0], cam[:, 1], cam[:, 2]
    dist = 4.2
    persp = dist / (dist - cym)
    span = 1.7
    scale = plot_w / (2.0 * span)
    px = (cx + cxm * persp * scale).reshape(n_rows, n_cols)
    py = (cy - czm * persp * scale).reshape(n_rows, n_cols)
    depth = (-cym).reshape(n_rows, n_cols)

    # Quads, painter-sorted far -> near, shaded by mean height.
    quads: List[Tuple[float, str, str]] = []
    for i in range(n_rows - 1):
        for j in range(n_cols - 1):
            corners = [(i, j), (i, j + 1), (i + 1, j + 1), (i + 1, j)]
            poly = " ".join(f"{px[a, b]:.1f},{py[a, b]:.1f}" for a, b in corners)
            zmean = float(np.mean([zz[a, b] for a, b in corners]))
            dmean = float(np.mean([depth[a, b] for a, b in corners]))
            t = (zmean - zmin) / (zmax - zmin) if zmax > zmin else 0.0
            quads.append((dmean, poly, _shade(t)))
    quads.sort(key=lambda q: q[0])

    parts: List[str] = []
    parts.append(svg_open(_WIDTH, _HEIGHT, "s3d-title", "s3d-desc", font_family=chrome_stack_for_theme(theme)))
    parts.append(
        '<title id="s3d-title">A 3-D surface with a single central peak, shaded '
        'by height</title>'
    )
    parts.append(
        '<desc id="s3d-desc">A smooth surface with one central peak, sampled on '
        'a regular grid and drawn as a static isometric 3-D projection: '
        'depth-sorted mesh quads shaded on a blue ramp by height, from about -1 '
        'at the edges to 3 at the peak, with a height legend.</desc>'
    )
    # The mesh geometry is static (a projected isometric render, no orbit
    # controls), but the one genuinely useful reading -- the peak's exact
    # height -- was previously not exposed anywhere except the rounded
    # legend endpoint. A single hover/focus marker at the peak vertex gives
    # that exact value without cluttering the 841 tiny mesh quads with their
    # own tooltips (which would bloat the file and be nearly impossible to
    # aim a pointer at individually).
    hover_css = (
        ".peak-hit{cursor:pointer;}"
        ".peak-hit:hover+.peak-dot,.peak-hit:focus+.peak-dot{r:6;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        ".peak-hit:hover+.peak-dot+.tip,.peak-hit:focus+.peak-dot+.tip{opacity:1}"
        "@media (prefers-reduced-motion: reduce){.peak-dot{transition:none;}"
        ".tip{transition:none}}"
    )
    parts.append(f"<style>{hover_css}</style>")
    parts.append(f'<rect width="{_WIDTH}" height="{_HEIGHT}" fill="{_BG}"/>')
    parts.append(
        f'<text x="40" y="56" font-size="26" font-weight="600" fill="{_INK}" '
        f'letter-spacing="-0.3">A central peak on a 3-D surface</text>'
    )
    parts.append(
        f'<text x="40" y="84" font-size="14" fill="{_SUBTLE}">'
        f'Static isometric projection · colour maps to height</text>'
    )

    parts.append('<g>')
    for _d, poly, fill in quads:
        parts.append(
            f'<polygon points="{poly}" fill="{fill}" stroke="{_MESH}" '
            f'stroke-width="0.6" stroke-linejoin="round"/>'
        )
    parts.append('</g>')

    # ---- peak marker: the one point on the surface worth an exact reading ----
    peak_i, peak_j = np.unravel_index(np.argmax(zz), zz.shape)
    peak_px, peak_py = float(px[peak_i, peak_j]), float(py[peak_i, peak_j])
    peak_z = float(zz[peak_i, peak_j])
    parts.append(
        f'<circle class="peak-hit" tabindex="0" cx="{peak_px:.1f}" cy="{peak_py:.1f}" '
        f'r="10" fill="transparent" role="img" aria-label="Peak height {peak_z:.2f}"/>'
    )
    parts.append(
        f'<circle class="peak-dot" cx="{peak_px:.1f}" cy="{peak_py:.1f}" r="4" '
        f'fill="#FFFFFF" stroke="{_shade(1.0)}" stroke-width="2"/>'
    )
    parts.append(
        tooltip_bubble(
            peak_px, peak_py - 14,
            ["Peak", f"height {peak_z:.2f}"],
            anchor="middle", canvas_w=_WIDTH, canvas_h=_HEIGHT,
            ink=_INK, secondary=_SUBTLE, border="#E5E5EA",
        )
    )

    # Height legend (vertical colour bar, left).
    lx, lt, lb, lw = 56.0, 200.0, 560.0, 22.0
    grad = "s3d-grad"
    parts.append(
        f'<defs><linearGradient id="{grad}" x1="0" y1="1" x2="0" y2="0">'
        f'<stop offset="0" stop-color="{_shade(0.0)}"/>'
        f'<stop offset="0.5" stop-color="{_shade(0.5)}"/>'
        f'<stop offset="1" stop-color="{_shade(1.0)}"/></linearGradient></defs>'
    )
    parts.append(
        f'<text x="{lx:.0f}" y="{lt - 14:.0f}" font-size="15" font-weight="700" '
        f'fill="{_INK}">{z_axis_title}</text>'
    )
    parts.append(
        f'<rect x="{lx:.0f}" y="{lt:.0f}" width="{lw:.0f}" height="{lb - lt:.0f}" '
        f'fill="url(#{grad})" rx="2.5"/>'
    )
    for frac, val in ((1.0, zmax), (0.5, (zmin + zmax) / 2), (0.0, zmin)):
        ty = lb - frac * (lb - lt)
        parts.append(
            f'<text x="{lx + lw + 8:.0f}" y="{ty + 5:.0f}" font-size="12.5" '
            f'font-family="Roboto Mono, monospace" fill="{_SUBTLE}">{val:.0f}</text>'
        )

    parts.append(fullscreen_control(_WIDTH, _HEIGHT, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_surface3d(
    data: Optional[List[Dict[str, float]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "",
    z_axis_title: str = "Height",
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render the 3-D surface and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, float]] or None
        Row records with ``x``, ``y`` and ``z``, forming a complete
        rectangular grid. Defaults to :data:`DEMO_DATA`.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/surface3d.svg``.
    title : str, optional
        Accepted for dispatcher parity; the figure's own headline is fixed,
        so this is unused.
    z_axis_title : str
        Label above the height colour-bar legend. Forwarded to :func:`build_svg`.
    mode, accessibility : str
        Forwarded to :func:`build_svg`.
    theme : str, optional
        Visual theme. Forwarded to :func:`build_svg`.

    Returns
    -------
    Path
        Absolute path to the written SVG file.
    """
    del title
    svg = build_svg(data, z_axis_title=z_axis_title, mode=mode, accessibility=accessibility, theme=theme)
    dest = Path(out) if out else svg_example_path(__file__, "surface3d")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """Write the 3-D surface SVG to the canonical assets path."""
    render_cli(__file__, "surface3d", build_svg,
               description="Render the 3-D surface SVG.")


if __name__ == "__main__":
    main()
