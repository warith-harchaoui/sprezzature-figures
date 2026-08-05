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
from typing import List, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _svg import svg_open, xml_escape  # noqa: E402
from _render import render_cli  # noqa: E402
from _interactive import fullscreen_control  # noqa: E402

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


def build_svg(mode: str = "self-contained", accessibility: str = "universal") -> str:
    _ = accessibility  # single blue height ramp reads in greyscale / CVD
    xx, yy, zz = _sample()
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
    px = (cx + cxm * persp * scale).reshape(_N, _N)
    py = (cy - czm * persp * scale).reshape(_N, _N)
    depth = (-cym).reshape(_N, _N)

    # Quads, painter-sorted far -> near, shaded by mean height.
    quads: List[Tuple[float, str, str]] = []
    for i in range(_N - 1):
        for j in range(_N - 1):
            corners = [(i, j), (i, j + 1), (i + 1, j + 1), (i + 1, j)]
            poly = " ".join(f"{px[a, b]:.1f},{py[a, b]:.1f}" for a, b in corners)
            zmean = float(np.mean([zz[a, b] for a, b in corners]))
            dmean = float(np.mean([depth[a, b] for a, b in corners]))
            t = (zmean - zmin) / (zmax - zmin) if zmax > zmin else 0.0
            quads.append((dmean, poly, _shade(t)))
    quads.sort(key=lambda q: q[0])

    parts: List[str] = []
    parts.append(svg_open(_WIDTH, _HEIGHT, "s3d-title", "s3d-desc"))
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
        f'fill="{_INK}">Height</text>'
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


def main() -> None:
    """Write the 3-D surface SVG to the canonical assets path."""
    render_cli(__file__, "surface-3d", build_svg,
               description="Render the 3-D surface SVG.")


if __name__ == "__main__":
    main()
