#!/usr/bin/env python3
"""
make_manifold_path — a walk across a landscape, as a hand-authored SVG with an
animated traversal.

A **manifold path** is the figure a latent-space optimisation paper needs: a
scalar landscape over two coordinates, drawn as a shaded 3-D surface, with the
optimiser's actual trajectory laid on top of it. It answers "where did the
search go, and where did it stop", which a loss curve alone cannot: a loss
curve tells you the search plateaued, not that it plateaued *on the wrong
peak*.

What is drawn:

* the **surface**, a regular grid of quads sorted back-to-front and shaded
  twice over — by height on a sequential ramp, and by a Lambert term from each
  quad's own normal, so the relief reads as relief and not as a contour map
  that happens to be tilted;
* the **path**, drawn in full and statically, in a warm hue with a paper
  casing so it stays legible over both the pale peaks and the dark troughs;
* the **global optimum**, marked, whether or not the walk reaches it;
* an **objective sparkline** under the panel, so the same walk can be read as
  a curve and the plateau has a length in steps, not just a look.

The traversal is animated: a marker travels the path while a bright overlay
draws in behind it, and the sparkline cursor moves in lockstep — both driven
from the *same* frame list, so they cannot drift apart. The full path and the
full sparkline are drawn statically underneath, so the first frame — a PNG
export, a thumbnail, a reader with ``prefers-reduced-motion`` — is a complete
figure and never a blank panel with a dot in it.

The demo landscape makes the honest point rather than the flattering one:
plain gradient ascent from the given start converges, and converges to a local
peak well short of the global one. The path is computed by actually running
the ascent on the analytic surface, not drawn by hand to look convincing.

Running the module writes the SVG artifact to
``sprezzature-figures/assets/svg-examples/manifold_path.svg``.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _style import BG, FONT_MONO, GRIDLINE, INK, SECONDARY, load_palette, os_dark_style  # noqa: E402
from _svg import svg_open, viridis, xml_escape  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme  # noqa: E402


#: Grid resolution of the demo surface, per axis.
_GRID = 34

#: Gradient-ascent steps in the demo walk.
_STEPS = 44

#: Viewing angles, in degrees. A shallow tip keeps the far half of the surface
#: from collapsing into a line while still reading as a solid.
_ELEV = 26.0
_AZIM = -52.0

#: Sequential height ramp anchors for the corporate theme (pale -> deep blue).
_LO_RGB = (234, 243, 255)
_HI_RGB = (10, 77, 160)

#: Bumps of the demo landscape: (centre x, centre y, amplitude, width).
_BUMPS: Tuple[Tuple[float, float, float, float], ...] = (
    (1.55, -0.35, 1.00, 0.95),    # global optimum
    (-1.30, 0.95, 0.72, 0.85),    # the local peak the walk settles on
    (-0.15, -1.70, 0.46, 0.80),
    (0.35, 1.75, 0.38, 0.70),
    (-2.05, -1.35, 0.30, 0.65),
)

#: Where the walk starts, and its step size.
_START = (-2.15, 0.05)
_LR = 0.16

#: Frames held still at each end of the sweep, so the loop's restart reads as
#: a pause rather than as a jump cut.
_END_HOLD = 6


def _surface_z(x: float, y: float) -> float:
    """Height of the demo landscape at ``(x, y)``: a sum of Gaussian bumps."""
    return sum(
        a * math.exp(-((x - bx) ** 2 + (y - by) ** 2) / (2.0 * s * s))
        for bx, by, a, s in _BUMPS
    )


def _surface_grad(x: float, y: float) -> Tuple[float, float]:
    """Analytic gradient of :func:`_surface_z` at ``(x, y)``."""
    gx = gy = 0.0
    for bx, by, a, s in _BUMPS:
        e = a * math.exp(-((x - bx) ** 2 + (y - by) ** 2) / (2.0 * s * s))
        gx += e * (-(x - bx) / (s * s))
        gy += e * (-(y - by) / (s * s))
    return gx, gy


def _make_demo_data() -> List[Dict[str, Any]]:
    """The landscape grid plus a genuine gradient-ascent walk over it.

    The walk is *run*, not drawn: each step follows the analytic gradient of
    :func:`_surface_z` with a fixed step size. It converges to the nearer,
    lower peak, which is the point of the figure.
    """
    rows: List[Dict[str, Any]] = []
    lo, hi = -2.6, 2.6
    for i in range(_GRID):
        for j in range(_GRID):
            x = lo + (hi - lo) * i / (_GRID - 1)
            y = lo + (hi - lo) * j / (_GRID - 1)
            rows.append({"series": "surface", "x": x, "y": y, "z": _surface_z(x, y)})

    x, y = _START
    for step in range(_STEPS):
        rows.append({"series": "path", "step": step, "x": x, "y": y, "z": _surface_z(x, y)})
        gx, gy = _surface_grad(x, y)
        norm = math.hypot(gx, gy)
        if norm < 1e-9:
            # Converged: hold still for the remaining steps rather than
            # stopping the list short, so the plateau is visible as a
            # plateau in the sparkline instead of as a missing tail.
            continue
        x += _LR * gx / norm
        y += _LR * gy / norm
    return rows


DEMO_DATA: List[Dict[str, Any]] = _make_demo_data()


def _shade(t: float, theme: str) -> Tuple[int, int, int]:
    """Sample the height ramp at ``t`` in [0, 1], as an RGB triple."""
    t = min(1.0, max(0.0, t))
    if theme == "academic":
        hexv = viridis(t)
        return (int(hexv[1:3], 16), int(hexv[3:5], 16), int(hexv[5:7], 16))
    return tuple(  # type: ignore[return-value]
        round(a + (b - a) * t) for a, b in zip(_LO_RGB, _HI_RGB)
    )


def _reshape(
    data: Optional[List[Dict[str, Any]]],
) -> Tuple[List[Tuple[float, float, float]], List[Tuple[float, float, float]]]:
    """Split the rows into the surface grid and the path, in order.

    Parameters
    ----------
    data : list of dict or None
        Flat rows with a ``series`` key of ``"surface"`` or ``"path"``, plus
        ``x``, ``y``, ``z`` (float). Path rows also carry ``step`` (ordinal),
        which sets their order. Defaults to :data:`DEMO_DATA`.

    Returns
    -------
    surface : list of (float, float, float)
        Grid samples, in the order given.
    path : list of (float, float, float)
        Walk samples, sorted by ``step``.
    """
    rows = list(data) if data else DEMO_DATA
    surface = [
        (float(r["x"]), float(r["y"]), float(r["z"]))
        for r in rows
        if str(r.get("series", "surface")) == "surface"
    ]
    path_rows = [r for r in rows if str(r.get("series", "")) == "path"]
    path_rows.sort(key=lambda r: float(r.get("step", 0)))
    path = [(float(r["x"]), float(r["y"]), float(r["z"])) for r in path_rows]
    return surface, path


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "The walk converges — one peak short of the best one",
    subtitle: str = "Gradient ascent on a two-coordinate objective. The path is run, not drawn; the global optimum is marked whether or not it is reached.",
    width: int = 940,
    duration: float = 9.0,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the manifold-path SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Flat rows; see :func:`_reshape` for the key contract. Defaults to
        :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text. The title should state the takeaway, not name the chart.
    width : int
        Canvas width in pixels; the height follows from the layout.
    duration : float, optional
        Seconds for one traversal sweep, including the pauses at each end.
    mode : str, optional
        Forwarded to :func:`_interactive.fullscreen_control`.
    accessibility : str, optional
        Accepted for CLI parity but a documented no-op: height is encoded on
        a single mono-hue sequential ramp, and the path is separated from the
        surface by lightness and by a paper casing, not by hue alone.
    theme : str, optional
        Visual theme: ``"corporate"`` (default, Roboto, blue height ramp) or
        ``"academic"`` (Latin Modern, viridis).

    Returns
    -------
    str
        A complete, standalone SVG document.

    Raises
    ------
    ValueError
        If the data contains no path rows, or a surface that is not square.
    """
    _ = accessibility
    surface, path = _reshape(data)
    if not path:
        raise ValueError("manifold_path needs at least one row with series='path'")
    n = int(round(math.sqrt(len(surface))))
    if n * n != len(surface):
        raise ValueError(f"surface must be a square grid; got {len(surface)} samples")

    palette = load_palette("universal", theme)
    path_hue = palette["Orange"]
    best_hue = palette["Red"]

    # ---- geometry ----
    left_pad = 40.0
    right_pad = 40.0
    panel_y0 = 112.0
    panel_h = 454.0
    spark_y0 = panel_y0 + panel_h + 76.0
    spark_h = 84.0
    height = int(spark_y0 + spark_h + 58.0)
    panel_w = width - left_pad - right_pad

    az, el = math.radians(_AZIM), math.radians(_ELEV)
    cos_a, sin_a = math.cos(az), math.sin(az)
    cos_e, sin_e = math.cos(el), math.sin(el)
    z_lo = min(p[2] for p in surface)
    z_hi = max(p[2] for p in surface)
    z_span = (z_hi - z_lo) or 1.0
    # Vertical exaggeration: the objective's range is small next to the plan
    # extent, and an unexaggerated relief would read as a flat sheet.
    z_gain = 2.1

    def rotate(x: float, y: float, z: float) -> Tuple[float, float, float]:
        """Model point -> (screen x, screen y, depth), before panel fitting."""
        x1 = x * cos_a - y * sin_a
        y1 = x * sin_a + y * cos_a
        z1 = (z - z_lo) / z_span * z_gain
        depth = y1 * cos_e - z1 * sin_e
        up = y1 * sin_e + z1 * cos_e
        return x1, -up, depth

    projected = [rotate(*p) for p in surface]
    px_all = [p[0] for p in projected]
    py_all = [p[1] for p in projected]
    x_lo, x_hi = min(px_all), max(px_all)
    y_lo, y_hi = min(py_all), max(py_all)
    scale = min(panel_w / ((x_hi - x_lo) or 1.0), panel_h / ((y_hi - y_lo) or 1.0))
    off_x = left_pad + (panel_w - (x_hi - x_lo) * scale) / 2.0
    off_y = panel_y0 + (panel_h - (y_hi - y_lo) * scale) / 2.0

    def to_screen(x: float, y: float, z: float) -> Tuple[float, float, float]:
        sx, sy, depth = rotate(x, y, z)
        return off_x + (sx - x_lo) * scale, off_y + (sy - y_lo) * scale, depth

    parts: List[str] = []
    parts.append(
        svg_open(width, height, "mp-title", "mp-desc", font_family=chrome_stack_for_theme(theme))
    )
    parts.append(f'<title id="mp-title">{xml_escape(title)}</title>')
    best = max(surface, key=lambda p: p[2])
    reached = path[-1][2]
    shortfall = (best[2] - reached) / (best[2] or 1.0) * 100.0
    parts.append(
        f'<desc id="mp-desc">A {n} by {n} sampled objective surface shown as a shaded '
        f'3-D relief, with a {len(path)}-step gradient-ascent walk drawn on it. The walk '
        f'settles at objective {reached:.2f}; the global optimum is {best[2]:.2f}, so it '
        f'stops {shortfall:.0f} percent short. The sparkline below the panel shows the '
        f'same walk as objective against step.</desc>'
    )

    style_rows = [
        ".q{stroke:#FFFFFF;stroke-width:0.4;stroke-linejoin:round}",
        ".wp{cursor:pointer}",
        f'.wp:focus{{outline:3px solid {path_hue};outline-offset:2px}}',
        os_dark_style(screen_blend=False, extra=".q{stroke:#0B0B0C;}"),
    ]
    parts.append("<style>\n" + "\n".join(style_rows) + "\n</style>")
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')

    parts.append(
        f'<text x="{left_pad:.0f}" y="52" font-size="26" font-weight="700" '
        f'fill="{INK}" letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    for i, line in enumerate(_wrap(subtitle, 120)):
        parts.append(
            f'<text x="{left_pad:.0f}" y="{78 + i * 20:.0f}" font-size="14.5" '
            f'fill="{SECONDARY}">{xml_escape(line)}</text>'
        )

    # ---- surface: quads, painter's algorithm, height + Lambert shading ----
    def grid_at(i: int, j: int) -> Tuple[float, float, float]:
        return surface[i * n + j]

    quads: List[Tuple[float, str]] = []
    light = (-0.45, -0.55, 0.70)  # a fixed key light, up and to the left
    for i in range(n - 1):
        for j in range(n - 1):
            corners = [grid_at(i, j), grid_at(i + 1, j), grid_at(i + 1, j + 1), grid_at(i, j + 1)]
            screen = [to_screen(*c) for c in corners]
            depth = sum(s[2] for s in screen) / 4.0
            mean_z = sum(c[2] for c in corners) / 4.0
            # Normal from the two diagonals of the model-space quad.
            ax = corners[2][0] - corners[0][0]
            ay = corners[2][1] - corners[0][1]
            azn = (corners[2][2] - corners[0][2]) * z_gain
            bx = corners[3][0] - corners[1][0]
            by = corners[3][1] - corners[1][1]
            bzn = (corners[3][2] - corners[1][2]) * z_gain
            nx, ny, nz = ay * bzn - azn * by, azn * bx - ax * bzn, ax * by - ay * bx
            nlen = math.hypot(math.hypot(nx, ny), nz) or 1.0
            lam = (nx * light[0] + ny * light[1] + nz * light[2]) / nlen
            # Half-Lambert: a raw dot product drives the shadow side to black
            # and loses the shape there; this keeps the far slopes readable.
            shade = 0.62 + 0.38 * max(-1.0, min(1.0, lam))
            r, g, b = _shade((mean_z - z_lo) / z_span, theme)
            r, g, b = (round(v * shade) for v in (r, g, b))
            pts = " ".join(f"{s[0]:.1f},{s[1]:.1f}" for s in screen)
            quads.append((depth, f'<polygon class="q" points="{pts}" fill="#{r:02X}{g:02X}{b:02X}"/>'))
    # Farthest first, so nearer quads paint over them.
    quads.sort(key=lambda q: -q[0])
    parts.extend(frag for _, frag in quads)

    # ---- the path, drawn in full and statically ----
    screen_path = [to_screen(*p) for p in path]
    d = "M " + " L ".join(f"{s[0]:.1f} {s[1]:.1f}" for s in screen_path)
    seg_len = [
        math.hypot(screen_path[i + 1][0] - screen_path[i][0], screen_path[i + 1][1] - screen_path[i][1])
        for i in range(len(screen_path) - 1)
    ]
    total_len = sum(seg_len) or 1.0
    parts.append(
        f'<path d="{d}" fill="none" stroke="{BG}" stroke-width="7" stroke-opacity="0.85" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
    )
    parts.append(
        f'<path d="{d}" fill="none" stroke="{path_hue}" stroke-width="3.2" '
        f'stroke-opacity="0.55" stroke-linecap="round" stroke-linejoin="round"/>'
    )

    # ---- global optimum, marked whether or not the walk gets there ----
    bx, by, _ = to_screen(*best)
    parts.append(
        f'<g role="img" aria-label="Global optimum, objective {best[2]:.2f}">'
        f'<title>Global optimum · objective {best[2]:.2f}</title>'
        f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="10" fill="none" stroke="{BG}" stroke-width="4"/>'
        f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="10" fill="none" stroke="{best_hue}" stroke-width="2.4"/>'
        f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="2.6" fill="{best_hue}"/>'
        f'</g>'
    )
    parts.append(
        f'<text x="{bx + 16:.1f}" y="{by + 4:.1f}" font-size="12.5" font-weight="600" '
        f'paint-order="stroke" stroke="{BG}" stroke-width="3.5" stroke-linejoin="round" '
        f'fill="{best_hue}">global optimum {best[2]:.2f}</text>'
    )

    # ---- start and end waypoints ----
    for label, (sx, sy, _dep), value in (
        ("start", screen_path[0], path[0][2]),
        ("settles here", screen_path[-1], path[-1][2]),
    ):
        parts.append(
            f'<g class="wp" tabindex="0" role="img" '
            f'aria-label="Walk {label}, objective {value:.2f}">'
            f'<title>{label} · objective {value:.2f}</title>'
            f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="6.5" fill="{path_hue}" '
            f'stroke="{BG}" stroke-width="2.5"/>'
            f'</g>'
        )
    parts.append(
        f'<text x="{screen_path[-1][0] + 14:.1f}" y="{screen_path[-1][1] + 20:.1f}" '
        f'font-size="12.5" font-weight="600" paint-order="stroke" stroke="{BG}" '
        f'stroke-width="3.5" stroke-linejoin="round" fill="{INK}">settles at {reached:.2f} '
        f'({shortfall:.0f}% short)</text>'
    )

    # ---- animated traversal ----
    # Frame list shared by the overlay, the marker and the sparkline cursor,
    # so the three can never drift apart. Held at both ends so the sweep's
    # restart reads as a pause rather than as a jump cut.
    n_pts = len(screen_path)
    frames = [0] * _END_HOLD + list(range(n_pts)) + [n_pts - 1] * _END_HOLD
    dur = f"{duration:g}s"
    cum = [0.0]
    for length in seg_len:
        cum.append(cum[-1] + length)
    offsets = [total_len - cum[i] for i in frames]
    parts.append(
        f'<path d="{d}" fill="none" stroke="{path_hue}" stroke-width="3.6" '
        f'stroke-linecap="round" stroke-linejoin="round" '
        f'stroke-dasharray="{total_len:.1f} {total_len:.1f}" '
        f'stroke-dashoffset="{total_len:.1f}">'
        f'<animate attributeName="stroke-dashoffset" '
        f'values="{";".join(f"{v:.1f}" for v in offsets)}" dur="{dur}" repeatCount="indefinite"/>'
        f'</path>'
    )
    mx = [screen_path[i][0] for i in frames]
    my = [screen_path[i][1] for i in frames]
    parts.append(
        f'<circle cx="{mx[0]:.1f}" cy="{my[0]:.1f}" r="6" fill="{path_hue}" '
        f'stroke="{BG}" stroke-width="2.5">'
        f'<animate attributeName="cx" values="{";".join(f"{v:.1f}" for v in mx)}" dur="{dur}" repeatCount="indefinite"/>'
        f'<animate attributeName="cy" values="{";".join(f"{v:.1f}" for v in my)}" dur="{dur}" repeatCount="indefinite"/>'
        f'</circle>'
    )

    # ---- objective sparkline ----
    zs = [p[2] for p in path]
    s_lo, s_hi = min(zs + [best[2]]), max(zs + [best[2]])
    s_span = (s_hi - s_lo) or 1.0
    spark_w = panel_w

    def spark_xy(i: int, value: float) -> Tuple[float, float]:
        return (
            left_pad + (i / max(1, n_pts - 1)) * spark_w,
            spark_y0 + spark_h - (value - s_lo) / s_span * spark_h,
        )

    parts.append(
        f'<text x="{left_pad:.1f}" y="{spark_y0 - 16:.1f}" font-size="13" '
        f'font-weight="600" fill="{INK}">Objective along the walk</text>'
    )
    best_y = spark_y0 + spark_h - (best[2] - s_lo) / s_span * spark_h
    parts.append(
        f'<line x1="{left_pad:.1f}" y1="{best_y:.1f}" x2="{left_pad + spark_w:.1f}" '
        f'y2="{best_y:.1f}" stroke="{best_hue}" stroke-width="1.4" stroke-dasharray="5 4"/>'
    )
    parts.append(
        f'<text x="{left_pad + spark_w:.1f}" y="{best_y - 7:.1f}" font-size="11.5" '
        f'fill="{best_hue}" text-anchor="end">global optimum</text>'
    )
    parts.append(
        f'<line x1="{left_pad:.1f}" y1="{spark_y0 + spark_h:.1f}" '
        f'x2="{left_pad + spark_w:.1f}" y2="{spark_y0 + spark_h:.1f}" '
        f'stroke="{GRIDLINE}" stroke-width="1.5"/>'
    )
    spark_pts = [spark_xy(i, v) for i, v in enumerate(zs)]
    parts.append(
        f'<polyline fill="none" stroke="{path_hue}" stroke-width="2.4" '
        f'points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in spark_pts)}"/>'
    )
    parts.append(
        f'<text x="{left_pad:.1f}" y="{spark_y0 + spark_h + 18:.1f}" font-size="11" '
        f'fill="{SECONDARY}" font-family="{FONT_MONO}">step 0</text>'
    )
    parts.append(
        f'<text x="{left_pad + spark_w:.1f}" y="{spark_y0 + spark_h + 18:.1f}" font-size="11" '
        f'fill="{SECONDARY}" font-family="{FONT_MONO}" text-anchor="end">step {n_pts - 1}</text>'
    )
    cx_s = [spark_pts[i][0] for i in frames]
    cy_s = [spark_pts[i][1] for i in frames]
    parts.append(
        f'<circle cx="{cx_s[0]:.1f}" cy="{cy_s[0]:.1f}" r="5" fill="{path_hue}" '
        f'stroke="{BG}" stroke-width="2">'
        f'<animate attributeName="cx" values="{";".join(f"{v:.1f}" for v in cx_s)}" dur="{dur}" repeatCount="indefinite"/>'
        f'<animate attributeName="cy" values="{";".join(f"{v:.1f}" for v in cy_s)}" dur="{dur}" repeatCount="indefinite"/>'
        f'</circle>'
    )

    parts.append(
        '<script><![CDATA['
        '(function(){var s=document.documentElement;try{'
        'if(matchMedia("(prefers-reduced-motion: reduce)").matches){'
        's.pauseAnimations();s.setCurrentTime(0);}}catch(e){}})();'
        ']]></script>'
    )
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def _wrap(text: str, width: int) -> List[str]:
    """Greedy word wrap for the subtitle, which is longer than one line."""
    words = text.split()
    lines: List[str] = []
    cur = ""
    for w in words:
        candidate = f"{cur} {w}".strip()
        if len(candidate) > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = candidate
    if cur:
        lines.append(cur)
    return lines


def make_manifold_path(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "The walk converges — one peak short of the best one",
    subtitle: str = "Gradient ascent on a two-coordinate objective. The path is run, not drawn; the global optimum is marked whether or not it is reached.",
    width: int = 940,
    duration: float = 9.0,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render the manifold-path figure and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Flat rows with a ``series`` key of ``"surface"`` or ``"path"``, plus
        ``x``, ``y``, ``z``; path rows also carry ``step``. Defaults to
        :data:`DEMO_DATA`.
    out : Path, str, or None
        Output path (.svg). Defaults to
        ``assets/svg-examples/manifold_path.svg``.
    title, subtitle : str
        Chart text.
    width : int
        Canvas width in pixels.
    duration : float
        Seconds for one traversal sweep.
    mode, accessibility, theme : str
        Forwarded to :func:`build_svg`.

    Returns
    -------
    Path
        Absolute path to the written SVG file.

    Examples
    --------
    >>> p = make_manifold_path()
    >>> p.exists()
    True
    """
    svg = build_svg(
        data,
        title=title,
        subtitle=subtitle,
        width=width,
        duration=duration,
        mode=mode,
        accessibility=accessibility,
        theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "manifold_path")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(
        __file__,
        "manifold_path",
        build_svg,
        description="Generate a shaded objective surface with an animated optimisation walk on it.",
    )


if __name__ == "__main__":
    main()
