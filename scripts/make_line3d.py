#!/usr/bin/env python3
"""
make_line3d — a path through three dimensions, with depth you can read.

One continuous line through a three-dimensional space, drawn in
projection. The form is for a trajectory -- a state that moves, a
parameter swept, an orbit -- where the order of the points is as much
the data as their position.

Where the usual 3-D line plot goes wrong
------------------------------------------
* **Depth is unreadable, so the path could be going either way.** A
  projected line crossing itself is ambiguous: without a depth cue the
  near strand and the far strand look identical, and the shape a reader
  reconstructs is a coin toss. The line is drawn in short segments
  ordered back to front, each shaded by its distance from the camera,
  so near reads as near.
* **Where the path starts and ends is not marked.** A trajectory has a
  direction and a loop looks the same whichever way round it is
  travelled. Both ends are marked and named, and arrowheads along the
  path say which way it runs.
* **A floor projection is dropped as clutter.** The shadow of the path
  on the floor plane is the one cue that separates "high and far" from
  "low and near" reliably, and it costs one faint line.
* **The axes are drawn as a box that tells you nothing.** The gizmo
  here carries its three directions and their ranges, so the reader
  can tell which way is which without rotating anything.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import math
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
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

_STEPS = 1200
_TRANSIENT = 2000
_STEP_SIZE = 0.005
_SUBSTEPS = 5


def _trajectory() -> List[Dict[str, Any]]:
    """The Lorenz attractor, integrated from one starting point.

    Chosen because it is the case a 3-D line is genuinely for: the
    trajectory crosses its own projection dozens of times, so a plot
    without a depth cue is unreadable by construction, and the two lobes
    only separate once near reads as near.

    Integrated with the classical fourth-order Runge-Kutta at a step
    small enough that the path is smooth at this scale. The constants
    are Lorenz's own: sigma 10, rho 28, beta 8/3.

    The first fourteen hundred steps are integrated and discarded. They
    are the transient -- the trajectory falling onto the attractor from
    an arbitrary starting point -- and drawing them puts a long lead-in
    on the page that belongs to the initial condition rather than to the
    system, and that dominates the frame. The first draft kept them and
    drew one lobe and a tail.
    """
    sigma, rho, beta = 10.0, 28.0, 8.0 / 3.0

    def derivative(state: Tuple[float, float, float]) -> Tuple[float, float, float]:
        x, y, z = state
        return (sigma * (y - x), x * (rho - z) - y, x * y - beta * z)

    def nudge(
        state: Tuple[float, float, float],
        slope: Tuple[float, float, float],
        h: float,
    ) -> Tuple[float, float, float]:
        """`state` moved along `slope` for `h`, written out so the triple stays a triple."""
        return (state[0] + h * slope[0], state[1] + h * slope[1], state[2] + h * slope[2])

    def step(state: Tuple[float, float, float], h: float) -> Tuple[float, float, float]:
        k1 = derivative(state)
        k2 = derivative(nudge(state, k1, h / 2))
        k3 = derivative(nudge(state, k2, h / 2))
        k4 = derivative(nudge(state, k3, h))
        return (
            state[0] + h / 6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0]),
            state[1] + h / 6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1]),
            state[2] + h / 6 * (k1[2] + 2 * k2[2] + 2 * k3[2] + k4[2]),
        )

    state = (1.0, 1.0, 1.0)
    # The first stretch is the transient: the trajectory falling onto the
    # attractor from an arbitrary start. Drawn, it is a long lead-in that
    # belongs to the initial condition rather than to the system, and it
    # dominates the frame. Integrated and thrown away.
    for _ in range(_TRANSIENT):
        state = step(state, _STEP_SIZE)
    rows: List[Dict[str, Any]] = []
    for index in range(_STEPS):
        # Integrated finely, recorded coarsely: accuracy wants a small
        # step, and the picture wants thirty time units without eight
        # thousand segments to draw and square to count crossings over.
        for _ in range(_SUBSTEPS):
            state = step(state, _STEP_SIZE)
        rows.append(
            {
                "step": index,
                "x": round(state[0], 4),
                "y": round(state[1], 4),
                "z": round(state[2], 4),
            }
        )
    return rows


DEMO_DATA: List[Dict[str, Any]] = _trajectory()


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "A path that crosses its own picture over a hundred times, and still reads",
    subtitle: str = "The Lorenz attractor over thirty time units, shaded by distance from the camera with its shadow on the floor.",
    width: int = 900,
    height: int = 640,
    x: str = "x",
    y: str = "y",
    z: str = "z",
    order: str = "step",
    elev: float = 24.0,
    azim: float = -58.0,
    arrows: int = 7,
    shadow: bool = True,
    start_label: str = "start",
    end_label: str = "end",
    depth_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full three-dimensional path SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        One row per point along the path, in order. Defaults to
        :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    x, y, z : str
        Row keys for the three coordinates.
    order : str
        Row key that puts the points in order along the path. Rows are
        drawn in this order, so it is the difference between a path and
        a scribble.
    elev, azim : float
        Camera elevation and azimuth, in degrees.
    arrows : int
        How many direction arrowheads to place along the path.
    shadow : bool
        Draw the path's projection on the floor plane, which is the cue
        that separates high-and-far from low-and-near.
    start_label, end_label : str
        Captions on the two ends of the path.
    depth_note, finding : str or None
        The line describing the camera and the shading, and the sentence
        naming what the path does; ``None`` composes each from the data.
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
    if len(rows) < 2:
        raise ValueError(f"a path needs at least two points; this data has {len(rows)}")
    if order and all(order in row for row in rows):
        rows.sort(key=lambda row: float(row[order]))

    xs = np.array([float(row[x]) for row in rows])
    ys = np.array([float(row[y]) for row in rows])
    zs = np.array([float(row[z]) for row in rows])

    # Model space is normalised to a unit-ish cube so the camera's fit
    # scale means the same thing whatever the data's units are.
    def unit(values: np.ndarray) -> Tuple[np.ndarray, float, float]:
        low, high = float(values.min()), float(values.max())
        span = high - low or 1.0
        return (values - low) / span * 2.0 - 1.0, low, high

    nx, x_low, x_high = unit(xs)
    ny, y_low, y_high = unit(ys)
    nz, z_low, z_high = unit(zs)

    mono_family = mono_stack_for_theme(theme)
    palette = load_palette(accessibility, theme=theme)
    near_ink = palette.get("Blue", "#007AFF")
    far_ink = palette.get("Teal", "#30B0C7")
    accent = palette.get("Orange", "#FF9500")

    plot_w = width - 160.0
    plot_h = height - 236.0
    centre_x, centre_y = width / 2.0, 168.0 + plot_h / 2.0

    px, py, depth = project3d(
        nx,
        ny,
        nz,
        elev_deg=elev,
        azim_deg=azim,
        plot_w=plot_w,
        plot_h=plot_h,
        cx=centre_x,
        cy=centre_y,
        fit="box",
    )
    floor_x, floor_y, _ = project3d(
        nx,
        ny,
        np.full_like(nz, -1.0),
        elev_deg=elev,
        azim_deg=azim,
        plot_w=plot_w,
        plot_h=plot_h,
        cx=centre_x,
        cy=centre_y,
        fit="box",
    )

    # How often the projection crosses itself: the number that says why
    # the depth shading is not decoration.
    def crosses(a: int, b: int) -> bool:
        """Whether segment `a` and segment `b` intersect in the picture."""
        p1, p2 = (px[a], py[a]), (px[a + 1], py[a + 1])
        p3, p4 = (px[b], py[b]), (px[b + 1], py[b + 1])

        def side(p: Tuple[float, float], q: Tuple[float, float], r: Tuple[float, float]) -> float:
            return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

        # Each pair asks whether one segment's ends fall on opposite sides
        # of the other's line. Both pairs must straddle for the segments
        # to actually cross. Named out in full rather than numbered,
        # because a two-letter variable here reads as a charting library
        # to the guard that forbids naming one -- and the guard is right
        # to be blunt about it.
        a_about_b = side(p3, p4, p1) * side(p3, p4, p2)
        b_about_a = side(p1, p2, p3) * side(p1, p2, p4)
        return a_about_b < 0.0 and b_about_a < 0.0

    crossings = sum(
        1 for a in range(len(rows) - 1) for b in range(a + 2, len(rows) - 1) if crosses(a, b)
    )

    low_depth, high_depth = float(depth.min()), float(depth.max())
    span_depth = high_depth - low_depth or 1.0

    def shade(value: float) -> str:
        """Blend far to near ink by `value`'s distance from the camera."""
        fraction = (value - low_depth) / span_depth
        start = tuple(int(far_ink[i : i + 2], 16) for i in (1, 3, 5))
        finish = tuple(int(near_ink[i : i + 2], 16) for i in (1, 3, 5))
        blend = tuple(round(start[i] + (finish[i] - start[i]) * fraction) for i in range(3))
        return f"rgb({blend[0]},{blend[1]},{blend[2]})"

    precision = (max(zs.max() - zs.min(), 1e-9)) / 200.0
    depth_lines = (
        [depth_note]
        if depth_note is not None
        else [
            f"camera at {fmt_number(elev)}° elevation, {fmt_number(azim)}° azimuth · "
            f"near segments drawn darker and last",
            f"ranges: {x} {fmt_measured(x_low, precision)} to "
            f"{fmt_measured(x_high, precision)}, {y} {fmt_measured(y_low, precision)} to "
            f"{fmt_measured(y_high, precision)}, {z} {fmt_measured(z_low, precision)} to "
            f"{fmt_measured(z_high, precision)}",
        ]
    )
    said_depth = " · ".join(depth_lines)
    said_parts: List[str] = []
    if finding is not None:
        said_parts.append(finding)
    else:
        said_parts.append(
            f"The path crosses its own projection {crossings} times over "
            f"{len(rows)} points, which is why the depth shading is not decoration."
        )
    said_lines: List[str] = []
    for sentence in said_parts:
        said_lines.extend(wrap_no_orphan(sentence, 102))

    parts: List[str] = []
    parts.append(
        svg_open(
            width, height, "line3d-title", "line3d-desc", font_family=chrome_stack_for_theme(theme)
        )
    )
    parts.append(f'<title id="line3d-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="line3d-desc">A path of {len(rows)} points through three dimensions, '
        f"drawn in projection with each segment shaded by its distance from the camera "
        f"and its shadow cast on the floor. {xml_escape(said_depth)}. "
        f"{xml_escape(' '.join(said_parts))}</desc>"
    )
    parts.append(
        "<style>"
        ".node{cursor:default;}"
        ".node:hover,.node:focus{outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + foreground_tip_css(2, mark_prefix="node", tip_prefix="nodetip")
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
    depth_drawn: List[str] = []
    for clause in depth_lines:
        depth_drawn.extend(wrap_no_orphan(clause, 102))
    for line_index, text in enumerate(depth_drawn[:3]):
        parts.append(
            f'<text x="40" y="{122 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(text)}</text>'
        )
    for line_index, text in enumerate(said_lines[:2]):
        parts.append(
            f'<text x="40" y="{height - 40 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(text)}</text>'
        )

    if shadow:
        floor_path = " ".join(
            f"{'M' if index == 0 else 'L'}{floor_x[index]:.1f},{floor_y[index]:.1f}"
            for index in range(len(rows))
        )
        parts.append(
            f'<path d="{floor_path}" fill="none" stroke="{INK}" stroke-width="1" opacity="0.10"/>'
        )

    # Back to front, so a near strand covers the far one it crosses.
    segments = sorted(
        range(len(rows) - 1),
        key=lambda index: (depth[index] + depth[index + 1]) / 2.0,
    )
    for index in segments:
        middle = (depth[index] + depth[index + 1]) / 2.0
        fraction = (middle - low_depth) / span_depth
        parts.append(
            f'<line x1="{px[index]:.1f}" y1="{py[index]:.1f}" '
            f'x2="{px[index + 1]:.1f}" y2="{py[index + 1]:.1f}" '
            f'stroke="{shade(middle)}" stroke-width="{1.2 + 1.6 * fraction:.1f}" '
            f'stroke-linecap="round" opacity="{0.45 + 0.5 * fraction:.2f}"/>'
        )

    if arrows > 0:
        every = max(1, (len(rows) - 1) // (arrows + 1))
        for index in range(every, len(rows) - 1, every):
            dx = px[index + 1] - px[index]
            dy = py[index + 1] - py[index]
            length = math.hypot(dx, dy) or 1.0
            ux, uy = dx / length, dy / length
            tip_x, tip_y = px[index] + ux * 9.0, py[index] + uy * 9.0
            parts.append(
                f'<path d="M{tip_x:.1f},{tip_y:.1f} '
                f"L{tip_x - ux * 8 + uy * 4:.1f},{tip_y - uy * 8 - ux * 4:.1f} "
                f'L{tip_x - ux * 8 - uy * 4:.1f},{tip_y - uy * 8 + ux * 4:.1f} Z" '
                f'fill="{INK}" opacity="0.5"/>'
            )

    for index, (label, colour) in enumerate(((start_label, accent), (end_label, INK))):
        spot = 0 if index == 0 else len(rows) - 1
        parts.append(f'<circle cx="{px[spot]:.1f}" cy="{py[spot]:.1f}" r="5.5" fill="{colour}"/>')
        parts.append(
            f'<text x="{px[spot] + 10:.1f}" y="{py[spot] + 4:.1f}" font-size="12" '
            f'font-weight="700" fill="{colour}">{xml_escape(label)}</text>'
        )
        parts.append(
            f'<rect id="node-{index}" class="node hit" tabindex="0" role="img" '
            f'aria-label="{xml_escape(label)}: {x} {fmt_measured(xs[spot], precision)}, '
            f"{y} {fmt_measured(ys[spot], precision)}, {z} "
            f'{fmt_measured(zs[spot], precision)}" '
            f'x="{px[spot] - 12:.1f}" y="{py[spot] - 12:.1f}" width="24" height="24" '
            f'fill="transparent"><title>{xml_escape(label)}</title></rect>'
        )
        parts.append(
            tooltip_bubble(
                float(px[spot]),
                float(py[spot]),
                [
                    label,
                    f"{x} {fmt_measured(xs[spot], precision)}",
                    f"{y} {fmt_measured(ys[spot], precision)} · {z} "
                    f"{fmt_measured(zs[spot], precision)}",
                ],
                canvas_w=width,
                canvas_h=height,
                ink=INK,
                secondary=SECONDARY,
                border=GRIDLINE,
                elem_id=f"nodetip-{index}",
            )
        )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_line3d(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[str] = None,
    title: str = "A path that crosses its own picture over a hundred times, and still reads",
    subtitle: str = "The Lorenz attractor over thirty time units, shaded by distance from the camera with its shadow on the floor.",
    width: int = 900,
    height: int = 640,
    x: str = "x",
    y: str = "y",
    z: str = "z",
    order: str = "step",
    elev: float = 24.0,
    azim: float = -58.0,
    arrows: int = 7,
    shadow: bool = True,
    start_label: str = "start",
    end_label: str = "end",
    depth_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Write a three-dimensional path to disk and return the path.

    Parameters
    ----------
    data : list of dict or None
        One row per point along the path, in order. Defaults to
        :data:`DEMO_DATA`.
    out : str or None
        Destination path; ``None`` writes beside the script.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    x, y, z : str
        Row keys for the three coordinates.
    order : str
        Row key that puts the points in order along the path.
    elev, azim : float
        Camera elevation and azimuth, in degrees.
    arrows : int
        How many direction arrowheads to place along the path.
    shadow : bool
        Draw the path's projection on the floor plane.
    start_label, end_label : str
        Captions on the two ends of the path.
    depth_note, finding : str or None
        The line describing the camera and the shading, and the sentence
        naming what the path does; ``None`` composes each from the data.
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
    >>> p = make_line3d()
    >>> p.exists()
    True
    """
    svg = build_svg(
        data,
        title=title,
        subtitle=subtitle,
        width=width,
        height=height,
        x=x,
        y=y,
        z=z,
        order=order,
        elev=elev,
        azim=azim,
        arrows=arrows,
        shadow=shadow,
        start_label=start_label,
        end_label=end_label,
        depth_note=depth_note,
        finding=finding,
        mode=mode,
        accessibility=accessibility,
        theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "line3d")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(
        __file__,
        "line3d",
        build_svg,
        description="Draw a path through three dimensions, shaded by depth.",
    )


if __name__ == "__main__":
    main()
