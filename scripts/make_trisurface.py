#!/usr/bin/env python3
"""
make_trisurface — a surface over scattered points, with the mesh left visible.

Points measured wherever they could be measured, joined into triangles
and lifted into three dimensions. The form is for data that does not sit
on a grid: soundings, boreholes, sensors dropped where the ground
allowed.

Where the usual triangulated surface goes wrong
-------------------------------------------------
* **The mesh is hidden, so interpolation looks like measurement.** A
  smooth shaded surface gives no hint which parts were measured and
  which were worked out between two points a kilometre apart. The
  triangle edges are drawn faintly and the sample points are marked, so
  the density of the evidence is visible everywhere.
* **The convex hull is filled in.** A triangulation spans every gap in
  the sample, including the ones that exist because nobody could get
  there. Those appear as enormous flat triangles that the eye reads as
  flat ground. Triangles with an edge longer than `max_edge` are
  dropped, and the chrome says how many -- which is a measurement of
  how holey the sample is.
* **Colour and height say the same thing twice.** Shading by the same
  z the surface is already lifted by spends the one spare channel on a
  repeat. Here the shading is the facet's *slope*, so a cliff reads as a
  cliff even where the projection flattens it.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _project3d import project as project3d  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _style import BG, GRIDLINE, INK, SECONDARY, load_palette  # noqa: E402
from _svg import (  # noqa: E402
    fmt_measured,
    fmt_number,
    foreground_tip_css,
    svg_open,
    tooltip_bubble,
    wrap_no_orphan,
    xml_escape,
)
from _textfit import fit_font_size  # noqa: E402
from _triangulate import triangulate  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

_SAMPLES = 240


def _soundings(seed: int = 12) -> List[Dict[str, Any]]:
    """Depth soundings across a bay, with a stretch nobody surveyed.

    Scattered on purpose, and with a hole on purpose. A survey boat
    covers what it can reach; the shoal in the middle of this bay was
    left alone, and a triangulation that fills it in invents a flat
    bottom exactly where the chart most needs to say "unknown". That
    hole is why `max_edge` exists.
    """
    rng = random.Random(seed)
    rows: List[Dict[str, Any]] = []
    while len(rows) < _SAMPLES:
        x = rng.uniform(-1.0, 1.0)
        y = rng.uniform(-1.0, 1.0)
        # The unsurveyed shoal: an ellipse nobody sailed over.
        if ((x - 0.18) / 0.34) ** 2 + ((y + 0.10) / 0.22) ** 2 < 1.0:
            continue
        channel = -26.0 * math.exp(-((x + 0.45) ** 2 + (y - 0.30) ** 2) / 0.10)
        slope = -14.0 * (1.0 - (x * 0.5 + y * 0.5 + 1.0) / 2.0)
        ripple = 1.8 * math.sin(4.2 * x) * math.cos(3.6 * y)
        rows.append({
            "x": round(x, 4),
            "y": round(y, 4),
            "depth": round(channel + slope + ripple + rng.gauss(0.0, 0.35), 3),
        })
    return rows


DEMO_DATA: List[Dict[str, Any]] = _soundings()


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "The unsurveyed shoal is left as a hole, not filled in as flat ground",
    subtitle: str = "Depth soundings across a bay, triangulated, with the mesh and the sample points left visible.",
    width: int = 920,
    height: int = 580,
    x: str = "x",
    y: str = "y",
    z: str = "depth",
    max_edge: float = 0.22,
    elev: float = 26.0,
    azim: float = -46.0,
    show_mesh: bool = True,
    show_points: bool = True,
    flat_label: str = "flat",
    steep_label: str = "steep",
    mesh_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full triangulated surface SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        One row per sample point. Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    x, y, z : str
        Row keys for the two ground coordinates and the measured value.
    max_edge : float
        Longest triangle edge to keep, as a fraction of the sample's
        width. Triangles longer than this span a gap nobody measured,
        and filling them in invents ground. ``0`` keeps the whole convex
        hull.
    elev, azim : float
        Camera elevation and azimuth, in degrees.
    show_mesh : bool
        Draw the triangle edges, so interpolation is distinguishable
        from measurement.
    show_points : bool
        Mark the sample points themselves.
    flat_label, steep_label : str
        The two ends of the slope key.
    mesh_note, finding : str or None
        The line describing the mesh and the trimming, and the sentence
        naming what the surface shows; ``None`` composes each from the
        data.
    mode : str
        ``"self-contained"`` keeps the interactive chrome inside the file.
    accessibility : str
        Palette variant.
    theme : str
        Visual theme.

    Returns
    -------
    str
        The SVG document.
    """
    rows = list(data if data else DEMO_DATA)
    if len(rows) < 3:
        raise ValueError(
            f"a surface needs at least three points; this data has {len(rows)}"
        )
    ground = [(float(row[x]), float(row[y])) for row in rows]
    heights = [float(row[z]) for row in rows]

    triangles = triangulate(ground)
    if not triangles:
        raise ValueError(
            "these points are collinear, so there is no surface between them"
        )

    span = max(
        max(p[0] for p in ground) - min(p[0] for p in ground),
        max(p[1] for p in ground) - min(p[1] for p in ground),
    ) or 1.0
    limit = max_edge * span

    def longest(triangle: Tuple[int, int, int]) -> float:
        """The triangle's longest edge, on the ground plane."""
        return max(
            math.dist(ground[a], ground[b])
            for a, b in (
                (triangle[0], triangle[1]),
                (triangle[1], triangle[2]),
                (triangle[2], triangle[0]),
            )
        )

    kept = [t for t in triangles if max_edge <= 0.0 or longest(t) <= limit]
    dropped = len(triangles) - len(kept)
    if not kept:
        raise ValueError(
            f"max_edge={max_edge} drops every triangle; the sample's closest points are "
            f"further apart than that"
        )

    low_z, high_z = min(heights), max(heights)
    depth_span = (high_z - low_z) or 1.0

    # Model space normalised so the camera's fit scale is unit-free.
    def unit(values: List[float]) -> np.ndarray:
        low, high = min(values), max(values)
        return (np.array(values) - low) / ((high - low) or 1.0) * 2.0 - 1.0

    nx = unit([p[0] for p in ground])
    ny = unit([p[1] for p in ground])
    nz = unit(heights) * 0.55  # a touch of exaggeration, stated in the chrome

    mono_family = mono_stack_for_theme(theme)
    palette = load_palette(accessibility, theme=theme)
    flat_ink = palette.get("Blue", "#007AFF")
    steep_ink = palette.get("Orange", "#FF9500")

    plot_w = width - 230.0
    plot_h = height - 190.0
    centre_x, centre_y = width / 2.0 - 40.0, 176.0 + plot_h / 2.0
    px, py, depth = project3d(
        nx, ny, nz, elev_deg=elev, azim_deg=azim, plot_w=plot_w, plot_h=plot_h,
        cx=centre_x, cy=centre_y, fit="box",
    )

    # Slope: the facet's rise over its run, in the data's own units, so
    # the shading says something the height does not already say.
    def slope_of(triangle: Tuple[int, int, int]) -> float:
        """Rise over run across the facet's steepest edge."""
        return max(
            abs(heights[a] - heights[b]) / (math.dist(ground[a], ground[b]) or 1e-9)
            for a, b in (
                (triangle[0], triangle[1]),
                (triangle[1], triangle[2]),
                (triangle[2], triangle[0]),
            )
        )

    slopes = {triangle: slope_of(triangle) for triangle in kept}
    ranked = sorted(slopes.values())
    steepest = ranked[-1]
    # The colour scale is clamped to the middle ninety percent of the
    # slopes. Two samples a hand's breadth apart with very different
    # depths produce one near-vertical facet, and scaling the whole ramp
    # to it paints everything else the same flat colour -- which is the
    # dynamic-range problem, arriving in a surface this time.
    gentle_at = ranked[max(0, int(0.05 * (len(ranked) - 1)))]
    steep_at = ranked[min(len(ranked) - 1, int(0.95 * (len(ranked) - 1)))]
    slope_span = (steep_at - gentle_at) or 1.0
    gentlest = gentle_at

    def shade(slope: float) -> str:
        """Blend flat to steep ink by where `slope` falls in the range."""
        fraction = max(0.0, min(1.0, (slope - gentle_at) / slope_span))
        start = tuple(int(flat_ink[i:i + 2], 16) for i in (1, 3, 5))
        finish = tuple(int(steep_ink[i:i + 2], 16) for i in (1, 3, 5))
        blend = tuple(
            round(start[i] + (finish[i] - start[i]) * fraction) for i in range(3)
        )
        return f"rgb({blend[0]},{blend[1]},{blend[2]})"

    precision = depth_span / 200.0
    mesh_lines = (
        [mesh_note] if mesh_note is not None
        else [
            f"{len(rows)} samples, {len(kept)} triangles"
            + (f", {dropped} dropped for spanning more than "
               f"{fmt_number(max_edge * 100.0)}% of the width" if dropped else ""),
            f"shaded by slope, not by depth, the ramp clamped to the middle 90% of "
            f"slopes ({fmt_number(gentle_at)} to {fmt_number(steep_at)} per unit)",
            f"height exaggerated · camera at {fmt_number(elev)}° elevation, "
            f"{fmt_number(azim)}° azimuth",
        ]
    )
    said_mesh = " · ".join(mesh_lines)
    said_parts: List[str] = []
    if finding is not None:
        said_parts.append(finding)
    else:
        said_parts.append(
            f"Depths run {fmt_measured(low_z, precision)} to "
            f"{fmt_measured(high_z, precision)}, and the steepest facet falls "
            f"{fmt_number(steepest)} per unit of ground."
        )
        if dropped:
            said_parts.append(
                f"{dropped} of {len(triangles)} triangles spanned unsurveyed ground and "
                f"were dropped rather than drawn flat."
            )
    said_lines: List[str] = []
    for sentence in said_parts:
        said_lines.extend(wrap_no_orphan(sentence, 104))

    parts: List[str] = []
    parts.append(
        svg_open(width, height, "trisurf-title", "trisurf-desc",
                 font_family=chrome_stack_for_theme(theme))
    )
    parts.append(f'<title id="trisurf-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="trisurf-desc">A surface over {len(rows)} scattered samples, '
        f'triangulated into {len(kept)} facets and lifted into three dimensions, shaded '
        f'by slope. {xml_escape(said_mesh)}. {xml_escape(" ".join(said_parts))}</desc>'
    )
    parts.append(
        "<style>"
        ".facet{cursor:default;}"
        ".facet:hover,.facet:focus{outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + foreground_tip_css(2, mark_prefix="facet", tip_prefix="facettip")
        + "@media (prefers-reduced-motion:reduce){.tip{transition:none}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    title_size = fit_font_size(title, width - 96.0, 22.0, min_px=15.0)
    parts.append(
        f'<text x="40" y="46" font-size="{title_size:.1f}" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    for line_index, text in enumerate(wrap_no_orphan(subtitle, 104)[:2]):
        parts.append(
            f'<text x="40" y="{72 + line_index * 20:.1f}" font-size="14" '
            f'fill="{SECONDARY}">{xml_escape(text)}</text>'
        )
    mesh_drawn: List[str] = []
    for clause in mesh_lines:
        mesh_drawn.extend(wrap_no_orphan(clause, 104))
    for line_index, text in enumerate(mesh_drawn[:3]):
        parts.append(
            f'<text x="40" y="{118 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(text)}</text>'
        )
    for line_index, text in enumerate(said_lines[:2]):
        parts.append(
            f'<text x="40" y="{height - 58 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(text)}</text>'
        )

    # Painter's algorithm: far facets first, so near ones cover them.
    ordered = sorted(
        kept, key=lambda t: (depth[t[0]] + depth[t[1]] + depth[t[2]]) / 3.0
    )
    for triangle in ordered:
        a, b, c = triangle
        colour = shade(slopes[triangle])
        parts.append(
            f'<path d="M{px[a]:.1f},{py[a]:.1f} L{px[b]:.1f},{py[b]:.1f} '
            f'L{px[c]:.1f},{py[c]:.1f} Z" fill="{colour}" opacity="0.88"'
            + (f' stroke="{BG}" stroke-width="0.4"' if show_mesh else "")
            + '/>'
        )
    if show_points:
        for index in range(len(rows)):
            parts.append(
                f'<circle cx="{px[index]:.1f}" cy="{py[index]:.1f}" r="1.1" '
                f'fill="{INK}" opacity="0.45"/>'
            )

    key_x, key_y = width - 160.0, 210.0
    parts.append(
        f'<text x="{key_x:.1f}" y="{key_y - 12:.1f}" font-size="11" fill="{SECONDARY}">'
        f'{xml_escape(steep_label)}</text>'
    )
    for step in range(12):
        fraction = 1.0 - step / 11.0
        parts.append(
            f'<rect x="{key_x:.1f}" y="{key_y + step * 11:.1f}" width="13" height="11" '
            f'fill="{shade(gentlest + slope_span * fraction)}"/>'
        )
    parts.append(
        f'<text x="{key_x:.1f}" y="{key_y + 12 * 11 + 12:.1f}" font-size="11" '
        f'fill="{SECONDARY}">{xml_escape(flat_label)}</text>'
    )

    deepest = min(range(len(rows)), key=lambda index: heights[index])
    shallowest = max(range(len(rows)), key=lambda index: heights[index])
    for element, (label, index) in enumerate(
        (("deepest", deepest), ("shallowest", shallowest))
    ):
        parts.append(
            f'<circle cx="{px[index]:.1f}" cy="{py[index]:.1f}" r="4" fill="{INK}"/>'
        )
        parts.append(
            f'<rect id="facet-{element}" class="facet hit" tabindex="0" role="img" '
            f'aria-label="{label} sample at {x} {fmt_number(ground[index][0])}, {y} '
            f'{fmt_number(ground[index][1])}: {z} '
            f'{fmt_measured(heights[index], precision)}" '
            f'x="{px[index] - 9:.1f}" y="{py[index] - 9:.1f}" width="18" height="18" '
            f'fill="transparent"><title>{label}: '
            f'{fmt_measured(heights[index], precision)}</title></rect>'
        )
        parts.append(
            tooltip_bubble(
                float(px[index]), float(py[index]),
                [label, f"{z} {fmt_measured(heights[index], precision)}",
                 f"{x} {fmt_number(ground[index][0])} · {y} "
                 f"{fmt_number(ground[index][1])}"],
                canvas_w=width, canvas_h=height, ink=INK, secondary=SECONDARY,
                border=GRIDLINE, elem_id=f"facettip-{element}",
            )
        )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_trisurface(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[str] = None,
    title: str = "The unsurveyed shoal is left as a hole, not filled in as flat ground",
    subtitle: str = "Depth soundings across a bay, triangulated, with the mesh and the sample points left visible.",
    width: int = 920,
    height: int = 580,
    x: str = "x",
    y: str = "y",
    z: str = "depth",
    max_edge: float = 0.22,
    elev: float = 26.0,
    azim: float = -46.0,
    show_mesh: bool = True,
    show_points: bool = True,
    flat_label: str = "flat",
    steep_label: str = "steep",
    mesh_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Write a triangulated surface to disk and return the path.

    Parameters
    ----------
    data : list of dict or None
        One row per sample point. Defaults to :data:`DEMO_DATA`.
    out : str or None
        Destination path; ``None`` writes beside the script.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    x, y, z : str
        Row keys for the two ground coordinates and the measured value.
    max_edge : float
        Longest triangle edge to keep, as a fraction of the width.
    elev, azim : float
        Camera elevation and azimuth, in degrees.
    show_mesh, show_points : bool
        Whether to draw the triangle edges and the sample points.
    flat_label, steep_label : str
        The two ends of the slope key.
    mesh_note, finding : str or None
        The line describing the mesh and the trimming, and the sentence
        naming what the surface shows; ``None`` composes each from the
        data.
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
    >>> p = make_trisurface()
    >>> p.exists()
    True
    """
    svg = build_svg(
        data, title=title, subtitle=subtitle, width=width, height=height,
        x=x, y=y, z=z, max_edge=max_edge, elev=elev, azim=azim,
        show_mesh=show_mesh, show_points=show_points, flat_label=flat_label,
        steep_label=steep_label, mesh_note=mesh_note, finding=finding,
        mode=mode, accessibility=accessibility, theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "trisurface")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "trisurface", build_svg,
               description="Draw a surface over scattered points, mesh and all.")


if __name__ == "__main__":
    main()
