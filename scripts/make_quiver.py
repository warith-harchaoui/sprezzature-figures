#!/usr/bin/env python3
"""
make_quiver — a house-styled vector field (quiver) plot as hand-authored SVG.

Draws one small triangular arrow per grid point, rotated to the local
vector's direction and coloured/sized by its magnitude, so a 2-D vector
field's overall structure -- a vortex, a source, a saddle -- reads as a
pattern at a glance rather than a table of (dx, dy) numbers. Typical
uses: fluid-flow or wind-field snapshots, gradient fields, any function
that assigns a direction and magnitude to every point in a plane.

Previously rendered via Vega-Lite (a rotated triangle point mark,
``vl_convert``); this module now computes the field and paints each
rotated triangle by hand -- no Vega, no matplotlib. Every arrow carries a
native ``<title>`` tooltip with its exact vector and magnitude.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _svg import svg_open, tooltip_bubble, viridis, xml_escape  # noqa: E402
from _style import BG, GRIDLINE, INK, SECONDARY  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme  # noqa: E402


_RAMP: Tuple[Tuple[float, str], ...] = (
    (0.00, "#EAF3FF"), (0.25, "#9CC7FF"), (0.55, "#3E9BFF"),
    (0.80, "#007AFF"), (1.00, "#0A4DA0"),
)


def _ramp_hex(t: float, theme: str = "corporate") -> str:
    """Sample the sequential ramp at position ``t`` in ``[0, 1]``.

    ``theme="academic"`` swaps to the shared viridis colormap
    (:func:`_svg.viridis`); the default (``"corporate"``) keeps this
    generator's own tuned blue ramp, unchanged.
    """
    if theme == "academic":
        return viridis(t)
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
    """A rotational (vortex) field, F(x, y) = (-y, x): a clean, easy-to-verify
    swirl pattern (arrows curl counter-clockwise around the origin, growing
    faster with distance from the centre)."""
    rows: List[Dict[str, Any]] = []
    for x in range(-5, 6):
        for y in range(-5, 6):
            fx, fy = -y, x
            rows.append({"x": x, "y": y, "fx": fx, "fy": fy})
    return rows


DEMO_DATA: List[Dict[str, Any]] = _make_demo_data()


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "A Vortex Field",
    subtitle: str = "Arrow direction and colour follow the local vector; length follows magnitude",
    width: int = 620,
    height: int = 620,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full quiver plot SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``x``, ``y`` (grid position) and ``fx``, ``fy``
        (vector components), all numeric. Defaults to :data:`DEMO_DATA`.
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
    xs = [float(r["x"]) for r in rows]
    ys = [float(r["y"]) for r in rows]
    mags = [math.hypot(float(r["fx"]), float(r["fy"])) for r in rows]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    max_mag = max(mags) or 1.0

    plot_x, plot_y = 40.0, 118.0
    right_margin = 40.0
    # 64px (not a plain 40px caption margin): the bottom row's arrowheads can
    # extend a full tri_max past their own row centre (a vertex can rotate to
    # point straight down), so a narrower margin let the bottom row's largest
    # arrows overlap the magnitude legend directly beneath the grid (found
    # via the Ralph Eyeball Loop).
    bottom_reserved = 64.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved
    n_cols = len(set(xs))
    cell_w = plot_w / max(1, n_cols - 1) if n_cols > 1 else plot_w
    tri_max = min(cell_w, plot_h / max(1, len(set(ys)) - 1)) * 0.42

    def x_for(v: float) -> float:
        return plot_x + (v - x_min) / ((x_max - x_min) or 1.0) * plot_w

    def y_for(v: float) -> float:
        return plot_y + plot_h - (v - y_min) / ((y_max - y_min) or 1.0) * plot_h

    parts: List[str] = []
    parts.append(svg_open(width, height, "qv-title", "qv-desc", font_family=chrome_stack_for_theme(theme)))
    parts.append(f'<title id="qv-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="qv-desc">Vector field over a {n_cols}x{len(set(ys))} grid, peak '
        f'magnitude {max_mag:.1f}. Hover or focus an arrow for its exact vector.</desc>'
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

    for r in rows:
        x, y = float(r["x"]), float(r["y"])
        fx, fy = float(r["fx"]), float(r["fy"])
        mag = math.hypot(fx, fy)
        t = mag / max_mag
        size = 3.0 + t * (tri_max - 3.0)
        cx, cy = x_for(x), y_for(y)
        # Screen-space rotation: y is flipped between data (up-positive) and
        # SVG (down-positive), so the visual angle is atan2(-fy, fx); a
        # triangle authored pointing along +x at rotation 0 then lands on
        # the field's true direction once flipped and rotated.
        angle_deg = math.degrees(math.atan2(-fy, fx))
        points = f"{size:.1f},0 {-size * 0.55:.1f},{size * 0.55:.1f} {-size * 0.55:.1f},{-size * 0.55:.1f}"
        tip = f"({x:.0f}, {y:.0f}): vector ({fx:.1f}, {fy:.1f}), magnitude {mag:.2f}"
        parts.append(
            f'<g class="hit" transform="translate({cx:.1f},{cy:.1f}) rotate({angle_deg:.1f})" '
            f'tabindex="0" role="img" aria-label="{xml_escape(tip)}">'
            f'<polygon points="{points}" fill="{_ramp_hex(t, theme)}" stroke="{BG}" stroke-width="0.5"/>'
            f'</g>'
        )
        parts.append(
            tooltip_bubble(
                cx, cy - tri_max / 2 - 14,
                [f"({x:.0f}, {y:.0f})", f"vector ({fx:.1f}, {fy:.1f})", f"magnitude {mag:.2f} ({t * 100:.0f}% of peak)"],
                anchor="middle", canvas_w=width, canvas_h=height,
                ink=INK, secondary=SECONDARY, border=GRIDLINE,
            )
        )

    # ---- legend ----
    ly = height - 20.0
    lx0 = plot_x
    parts.append(f'<text x="{lx0:.1f}" y="{ly:.1f}" font-size="11" fill="{SECONDARY}">0</text>')
    swatch_x = lx0 + 16.0
    n_swatches = 8
    for i in range(n_swatches):
        t = i / (n_swatches - 1)
        parts.append(f'<rect x="{swatch_x + i * 16:.1f}" y="{ly - 11:.1f}" width="14" height="12" fill="{_ramp_hex(t, theme)}"/>')
    parts.append(
        f'<text x="{swatch_x + n_swatches * 16 + 6:.1f}" y="{ly:.1f}" font-size="11" '
        f'fill="{SECONDARY}">{max_mag:.1f} (Magnitude)</text>'
    )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_quiver(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "A Vortex Field",
    subtitle: str = "Arrow direction and colour follow the local vector; length follows magnitude",
    width: int = 620,
    height: int = 620,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored quiver plot and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``x``, ``y``, ``fx``, ``fy`` (float). Defaults to
        DEMO_DATA (a rotational vortex field).
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/quiver.svg``.
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
    >>> p = make_quiver()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility, theme=theme)
    dest = Path(out) if out else svg_example_path(__file__, "quiver")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "quiver", build_svg, description="Generate a vector field (quiver) plot.")


if __name__ == "__main__":
    main()
