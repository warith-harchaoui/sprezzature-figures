#!/usr/bin/env python3
"""
make_tricontour — iso-lines over scattered samples, honest about the gaps.

A field measured where instruments could be put, not on a grid: sensors,
wells, stations, soil cores. There is no cell to march through, so the
samples are triangulated first and the iso-lines are cut through the
triangles.

Where the usual triangulated contour goes wrong
-----------------------------------------------
* **It draws the same line everywhere.** A contour between two sensors
  200 m apart is a measurement; the same contour between two sensors
  4 km apart is a guess drawn with the same pen. Segments crossing a
  triangle wider than the sensors' own spacing are dashed and counted,
  so a reader can see which half of a decision line is evidence.
* **The convex hull is filled in.** A triangulation spans every gap,
  including the ones that exist because nobody measured there. Triangles
  with an edge longer than `max_edge` are dropped, and the gap stays a
  gap instead of becoming a smooth interpolation nobody measured.
* **The line that matters is drawn like the rest.** A guideline, a
  limit, a spec bound is the only level most readers act on. It gets its
  own weight and its own label here, and the share of it that falls on
  unsupported ground is stated rather than left to be noticed.
* **Saddles are not a problem here.** Marching squares has to guess how
  to join a cell whose corners alternate; over a triangle the field is
  linear and the join is forced. Triangulating first buys that for free,
  and it is worth saying out loud because it is the usual reason a
  gridded contour joins two basins that are not joined.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _scale import nice_ticks_range  # noqa: E402
from _style import BG, GRIDLINE, INK, SECONDARY, load_palette  # noqa: E402
from _svg import (  # noqa: E402
    fmt_measured,
    fmt_number,
    foreground_tip_css,
    svg_open,
    tooltip_bubble,
    viridis,
    wrap_no_orphan,
    xml_escape,
)
from _triangulate import triangulate  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

#: How many sensors the demo network has. Small on purpose: a low-cost
#: network is a few dozen boxes on lamp-posts, not a grid, and the whole
#: point of this figure is what happens between them.
_STATIONS = 78


def _network(seed: int = 7) -> List[Dict[str, Any]]:
    """A low-cost air-quality network over a city, clustered as they really are.

    Sensors go where there is a volunteer, a lamp-post and a plug: dense
    in the centre, thin on the ring road, absent over the river and the
    industrial strip. The field underneath is a plume from a works in the
    east, a traffic corridor along the main road, and a background that
    rises with the valley floor -- so the highest readings are precisely
    where the network is thinnest, which is the usual and uncomfortable
    case.
    """
    rng = random.Random(seed)

    def level(x: float, y: float) -> float:
        plume = 21.0 * math.exp(-((x - 6.6) ** 2 / 5.2 + (y - 4.3) ** 2 / 2.0))
        corridor = 9.5 * math.exp(-((y - 2.2 - 0.26 * x) ** 2) / 0.62)
        valley = 4.4 * math.exp(-((y - 1.0) ** 2) / 26.0)
        return 5.2 + plume + corridor + valley

    rows: List[Dict[str, Any]] = []
    # Two in five cluster around the centre, the rest are scattered: the
    # mix is what makes the triangle sizes span an order of magnitude,
    # which is the whole subject of the figure.
    while len(rows) < _STATIONS:
        if len(rows) < int(_STATIONS * 0.42):
            x = rng.gauss(3.2, 1.6)
            y = rng.gauss(2.8, 1.4)
        else:
            x = rng.uniform(0.0, 9.0)
            y = rng.uniform(0.0, 7.0)
        if not (0.0 <= x <= 9.0 and 0.0 <= y <= 7.0):
            continue
        # The works and its yard: fenced, no sensor inside it.
        if 6.0 <= x <= 7.9 and 3.3 <= y <= 5.3:
            continue
        rows.append({
            "east_km": round(x, 3),
            "north_km": round(y, 3),
            "pm25": round(level(x, y) + rng.gauss(0.0, 0.9), 2),
        })
    return rows


DEMO_DATA: List[Dict[str, Any]] = _network()


def _nice_levels(low: float, high: float, count: int) -> List[float]:
    """`count` or so levels from `low` to `high`, on a step worth printing.

    Linear rather than geometric: a concentration is read against a
    guideline, and a guideline is a round number on a linear scale. The
    step is snapped to 1, 2 or 5 times a power of ten so the labels are
    numbers a reader already holds in mind.
    """
    span = high - low
    if span <= 0 or count < 2:
        return [low]
    raw = span / count
    magnitude = 10.0 ** math.floor(math.log10(raw))
    for option in (1.0, 2.0, 2.5, 5.0, 10.0):
        step = option * magnitude
        if step >= raw:
            break
    first = math.ceil(low / step) * step
    out: List[float] = []
    value = first
    while value < high:
        out.append(round(value, 10))
        value += step
    return out


def _segment_at(
    corners: Sequence[Tuple[float, float, float]], level: float
) -> Optional[Tuple[float, float, float, float]]:
    """Where `level` crosses one triangle, as a single segment.

    Parameters
    ----------
    corners : sequence of tuple of float
        The triangle's three corners as ``(x, y, z)``.
    level : float
        The iso-value.

    Returns
    -------
    tuple of float or None
        ``(x0, y0, x1, y1)``, or ``None`` when the level misses the
        triangle. The field is linear over a triangle, so the level
        crosses exactly two of its three edges or none of them -- no
        saddle to resolve, which is the whole reason to triangulate
        before contouring.
    """
    crossings: List[Tuple[float, float]] = []
    for index in range(3):
        ax, ay, az = corners[index]
        bx, by, bz = corners[(index + 1) % 3]
        if (az < level) == (bz < level):
            continue
        if bz == az:
            continue
        share = (level - az) / (bz - az)
        crossings.append((ax + share * (bx - ax), ay + share * (by - ay)))
    if len(crossings) != 2:
        return None
    return (crossings[0][0], crossings[0][1], crossings[1][0], crossings[1][1])


def _clip_above(
    polygon: Sequence[Tuple[float, float, float]], level: float, keep_above: bool
) -> List[Tuple[float, float, float]]:
    """Sutherland-Hodgman clip of a polygon by the plane ``z = level``.

    The field is linear over a triangle, so the half-space ``z >= level``
    cuts it into a convex polygon with exact corners -- which is what
    makes the filled bands agree with the lines rather than merely
    resemble them.

    Parameters
    ----------
    polygon : sequence of tuple of float
        Corners as ``(x, y, z)``, in order.
    level : float
        The cutting value.
    keep_above : bool
        Keep the ``z >= level`` side when true, the other side when false.

    Returns
    -------
    list of tuple of float
        The clipped corners; empty when nothing survives.
    """
    def inside(z: float) -> bool:
        return z >= level if keep_above else z <= level

    out: List[Tuple[float, float, float]] = []
    count = len(polygon)
    for index in range(count):
        current = polygon[index]
        following = polygon[(index + 1) % count]
        here, there = inside(current[2]), inside(following[2])
        if here:
            out.append(current)
        if here != there and following[2] != current[2]:
            share = (level - current[2]) / (following[2] - current[2])
            out.append((
                current[0] + share * (following[0] - current[0]),
                current[1] + share * (following[1] - current[1]),
                level,
            ))
    return out


def _smallest_angle(
    a: Tuple[float, float], b: Tuple[float, float], c: Tuple[float, float]
) -> float:
    """The triangle's narrowest angle, in degrees.

    A Delaunay triangulation is free of slivers inside the sample, but
    its outer boundary is the convex hull, and the hull is stitched from
    whatever points happen to lie near it: three almost-collinear sensors
    give a splinter of a triangle that reaches far across ground none of
    them measured. The long-edge test misses those, because a splinter's
    edges can all be short. Its narrowest angle cannot.

    Parameters
    ----------
    a, b, c : tuple of float
        The corners, as ``(x, y)``.

    Returns
    -------
    float
        The smallest interior angle in degrees; ``0.0`` when two corners
        coincide.
    """
    angles: List[float] = []
    corners = (a, b, c)
    for index in range(3):
        px, py = corners[index]
        qx, qy = corners[(index + 1) % 3]
        rx, ry = corners[(index + 2) % 3]
        left = math.hypot(qx - px, qy - py)
        right = math.hypot(rx - px, ry - py)
        if left == 0.0 or right == 0.0:
            return 0.0
        cosine = ((qx - px) * (rx - px) + (qy - py) * (ry - py)) / (left * right)
        angles.append(math.degrees(math.acos(max(-1.0, min(1.0, cosine)))))
    return min(angles)


def _nearest_spacing(points: Sequence[Tuple[float, float]]) -> float:
    """Median distance from a point to its nearest neighbour.

    The network's own resolution, in the data's own units. Everything
    wider than a small multiple of it is ground the network does not
    actually cover, whatever the triangulation draws across it.
    """
    gaps: List[float] = []
    for index, (px, py) in enumerate(points):
        best = float("inf")
        for other, (qx, qy) in enumerate(points):
            if other == index:
                continue
            best = min(best, math.hypot(px - qx, py - qy))
        if best < float("inf"):
            gaps.append(best)
    if not gaps:
        return 0.0
    gaps.sort()
    middle = len(gaps) // 2
    if len(gaps) % 2:
        return gaps[middle]
    return (gaps[middle - 1] + gaps[middle]) / 2.0


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "A third of the guideline line is a guess, and is drawn as one",
    subtitle: str = "PM2.5 across a city's sensor network, triangulated and dashed where no sensor is near.",
    width: int = 880,
    height: int = 700,
    x: str = "east_km",
    y: str = "north_km",
    z: str = "pm25",
    levels: int = 7,
    cuts: Optional[List[float]] = None,
    threshold: Optional[float] = 15.0,
    threshold_label: str = "WHO 24-hour guideline",
    max_edge: float = 0.26,
    support_radius: Optional[float] = None,
    support_spacing: float = 2.0,
    min_angle: float = 3.0,
    fill: bool = True,
    show_mesh: bool = True,
    show_points: bool = True,
    label_levels: bool = True,
    x_label: str = "east, km",
    y_label: str = "north, km",
    value_label: str = "PM2.5, µg/m³",
    unit: str = "µg/m³",
    coord_unit: str = "km",
    summary: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full triangulated-contour SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Scattered rows with keys named by `x`, `y` and `z`. Defaults to
        :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    x, y, z : str
        Which keys hold the two coordinates and the measured value.
    levels : int
        Roughly how many iso-levels to draw, on a step snapped to 1, 2,
        2.5 or 5 times a power of ten. Ignored when `cuts` is given.
    cuts : list of float or None
        Explicit levels, in the value's own units. ``None`` derives them
        from `levels`.
    threshold : float or None
        One level to draw heavier, as the one a reader acts on. ``None``
        draws no such line.
    threshold_label : str
        What that line is, written beside it.
    max_edge : float
        Triangles with an edge longer than this fraction of the larger
        coordinate span are dropped rather than drawn: they span ground
        nobody measured, and filling them in invents a field.
    support_radius : float or None
        How far, in the data's own units, a piece of contour may sit
        from the nearest sample and still count as supported. Further
        than this and it is drawn dashed. ``None`` derives it as
        `support_spacing` times the median nearest-neighbour distance.
    support_spacing : float
        The multiple of the network's own spacing beyond which a segment
        counts as unsupported. Ignored when `support_radius` is given.
    min_angle : float
        Triangles narrower than this, in degrees, are dropped as hull
        splinters: three almost-collinear samples otherwise stitch a
        shard that reaches across ground none of them measured.
    fill : bool
        Fill the bands between levels as well as drawing the lines.
    show_mesh : bool
        Draw the triangulation's edges.
    show_points : bool
        Mark the sample locations.
    label_levels : bool
        Write each level's value on its own line.
    x_label, y_label, value_label, unit : str
        Axis titles, the name of the field, and its unit.
    coord_unit : str
        The unit the two coordinates are in, used when reporting how far
        apart the sensors are.
    summary : str or None
        The chrome line stating counts, spacing and range. ``None``
        composes it.
    finding : str or None
        The closing line under the plot. ``None`` composes it from the
        measured share of the threshold line that is unsupported.
    mode, accessibility : str, optional
        Forwarded to :func:`_interactive.fullscreen_control` /
        :func:`_style.load_palette`.
    theme : str, optional
        Visual theme: ``"corporate"`` (default, Roboto) or ``"academic"``
        (LaTeX-style Latin Modern).

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    rows = list(data if data else DEMO_DATA)
    mono_family = mono_stack_for_theme(theme)
    load_palette(accessibility, theme=theme)

    points = [(float(r[x]), float(r[y])) for r in rows]
    values = [float(r[z]) for r in rows]
    z_lo, z_hi = min(values), max(values)
    x_lo, x_hi = min(p[0] for p in points), max(p[0] for p in points)
    y_lo, y_hi = min(p[1] for p in points), max(p[1] for p in points)
    span = max(x_hi - x_lo, y_hi - y_lo) or 1.0

    spacing = _nearest_spacing(points)
    support_at = (
        support_radius if support_radius is not None else spacing * support_spacing
    )

    def longest_edge(triangle: Tuple[int, int, int]) -> float:
        return max(
            math.hypot(
                points[triangle[i]][0] - points[triangle[(i + 1) % 3]][0],
                points[triangle[i]][1] - points[triangle[(i + 1) % 3]][1],
            )
            for i in range(3)
        )

    raw_mesh = triangulate(points)
    mesh = [t for t in raw_mesh if longest_edge(t) <= max_edge * span]
    stretched = len(raw_mesh) - len(mesh)

    # Peel the hull's splinters, and keep peeling: removing one exposes
    # the next, and a chain of near-collinear sensors makes a whole
    # fringe of them. Interior triangles are left alone whatever their
    # shape -- a thin one inside the sample still joins three real
    # measurements, and cutting it out would punch a hole in ground that
    # *was* covered.
    peeled = 0
    while True:
        tally: Dict[Tuple[int, int], int] = {}
        for triangle in mesh:
            for i in range(3):
                a, b = triangle[i], triangle[(i + 1) % 3]
                key = (min(a, b), max(a, b))
                tally[key] = tally.get(key, 0) + 1

        doomed = {
            triangle for triangle in mesh
            # On the hull: at least one edge belongs to this triangle alone.
            if any(
                tally[(min(triangle[i], triangle[(i + 1) % 3]),
                       max(triangle[i], triangle[(i + 1) % 3]))] == 1
                for i in range(3)
            )
            and _smallest_angle(
                points[triangle[0]], points[triangle[1]], points[triangle[2]]
            ) < min_angle
        }
        if not doomed:
            break
        mesh = [triangle for triangle in mesh if triangle not in doomed]
        peeled += len(doomed)

    def unsupported(mx: float, my: float) -> bool:
        """True when no sample sits within `support_at` of ``(mx, my)``.

        The test a reader would run by eye and by ruler: is there an
        instrument near this piece of line, or is it interpolation. It is
        deliberately about the samples and not about the triangle --- a
        long thin triangle can still carry a segment that passes right
        beside a sensor, and that segment is evidence.
        """
        return all(
            math.hypot(mx - px, my - py) > support_at for px, py in points
        )

    bands = cuts if cuts is not None else _nice_levels(z_lo, z_hi, levels)
    bands = [c for c in bands if z_lo < c < z_hi]
    drawn = list(bands)
    if threshold is not None and z_lo < threshold < z_hi and threshold not in drawn:
        drawn.append(threshold)
    drawn.sort()

    def measured(value: float) -> str:
        return fmt_measured(value, max(z_hi - z_lo, 1e-9) / 10.0)

    def located(value: float) -> str:
        return fmt_measured(value, span / 10.0)

    # ---- the iso-lines, cut and measured before anything is laid out ----
    # Cut in the data's own coordinates, not in pixels: the share of a
    # line that is unsupported is a fact about the ground, and it has to
    # be known before the chrome that reports it can be written -- which
    # in turn is what decides how much room is left for the map.
    cut_lines: List[Dict[str, Any]] = []
    supported_km = 0.0
    unsupported_km = 0.0
    for index, level in enumerate(drawn):
        firm: List[Tuple[float, float, float, float]] = []
        loose: List[Tuple[float, float, float, float]] = []
        is_threshold = threshold is not None and level == threshold
        for triangle in mesh:
            corners = [(points[i][0], points[i][1], values[i]) for i in triangle]
            crossing = _segment_at(corners, level)
            if crossing is None:
                continue
            length = math.hypot(crossing[2] - crossing[0], crossing[3] - crossing[1])
            if unsupported(
                (crossing[0] + crossing[2]) / 2.0, (crossing[1] + crossing[3]) / 2.0
            ):
                loose.append(crossing)
                if is_threshold:
                    unsupported_km += length
            else:
                firm.append(crossing)
                if is_threshold:
                    supported_km += length
        if firm or loose:
            cut_lines.append({
                "index": index, "level": level, "firm": firm, "loose": loose,
                "threshold": is_threshold,
            })

    total_km = supported_km + unsupported_km
    share = (unsupported_km / total_km) if total_km else 0.0

    splinters = (
        "1 peeled as a hull splinter" if peeled == 1
        else f"{peeled} peeled as hull splinters"
    )
    # Composed as whole lines rather than as one paragraph that wraps:
    # a wrapped line breaks wherever the width runs out, which makes
    # each half a fragment -- unreadable on its own, and untranslatable
    # as a unit. One statement per line survives both.
    said_lines = (
        wrap_no_orphan(summary, 108) if summary is not None else [
            f"{len(rows)} sensors · {len(mesh)} triangles, {stretched} dropped for "
            f"spanning more than {fmt_number(max_edge * 100)}% of the width, "
            f"{splinters}",
            f"{measured(z_lo)} to {measured(z_hi)} {unit} · dashed where no sensor "
            f"lies within {located(support_at)} {coord_unit}, "
            f"{fmt_number(support_spacing)} times the median sensor spacing",
        ]
    )
    if finding is not None:
        found_lines = wrap_no_orphan(finding, 108)
    elif threshold is not None and total_km and unsupported_km > 0.0:
        found_lines = [
            f"{fmt_number(share * 100)}% of the {threshold_label} line runs across "
            f"ground no sensor is near enough to support.",
            f"That is {located(unsupported_km)} {coord_unit} of "
            f"{located(total_km)}, and it is drawn dashed.",
        ]
    elif threshold is not None and total_km:
        found_lines = [
            f"Every one of the {located(total_km)} {coord_unit} of the "
            f"{threshold_label} line has a sensor within "
            f"{located(support_at)} {coord_unit} of it.",
        ]
    else:
        found_lines = []

    said = " · ".join(said_lines)
    found = " ".join(found_lines)
    subtitle_lines = wrap_no_orphan(subtitle, 104)[:2]

    # ---- the room the chrome leaves, and the map that fits in it ----
    frame_x = 72.0
    right_margin = 178.0
    chrome_top = 72.0 + len(subtitle_lines) * 18.0 + 20.0
    frame_y = chrome_top + len(said_lines) * 17.0 + 26.0
    bottom_margin = 76.0 + len(found_lines) * 17.0
    room_w = width - frame_x - right_margin
    room_h = height - frame_y - bottom_margin
    # One scale for both axes: ground distances read with two different
    # scales make a map of a place that does not exist. The frame is then
    # drawn around what that leaves rather than around the room it was
    # given, so the plot has no empty aprons on the two sides the aspect
    # ratio did not need.
    scale = min(room_w / (x_hi - x_lo or 1.0), room_h / (y_hi - y_lo or 1.0))
    plot_x = frame_x
    plot_w = (x_hi - x_lo) * scale
    plot_h = (y_hi - y_lo) * scale
    plot_y = frame_y + (room_h - plot_h) / 2.0

    def to_px(px: float, py: float) -> Tuple[float, float]:
        return (
            plot_x + (px - x_lo) * scale,
            plot_y + plot_h - (py - y_lo) * scale,
        )

    def as_path(segments: Sequence[Tuple[float, float, float, float]]) -> str:
        return " ".join(
            "M {:.1f},{:.1f} L {:.1f},{:.1f}".format(
                *to_px(s[0], s[1]), *to_px(s[2], s[3])
            )
            for s in segments
        )

    # ---- the document, in drawing order ----
    parts: List[str] = []
    parts.append(
        svg_open(width, height, "tricontour-title", "tricontour-desc",
                 font_family=chrome_stack_for_theme(theme))
    )
    parts.append(f'<title id="tricontour-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="tricontour-desc">Iso-lines of {xml_escape(value_label)} over '
        f'{len(rows)} scattered sensors, triangulated into {len(mesh)} facets and '
        f'filled in bands. {xml_escape(said)}. {xml_escape(found)}</desc>'
    )
    parts.append(
        "<style>"
        ".hit{cursor:default;}"
        ".hit:hover,.hit:focus{outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + foreground_tip_css(len(points) if show_points else 0,
                             mark_prefix="sensor", tip_prefix="sensortip")
        + "@media (prefers-reduced-motion:reduce){.tip{transition:none}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="{frame_x:.1f}" y="46" font-size="22" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    for line_no, line in enumerate(subtitle_lines):
        parts.append(
            f'<text x="{frame_x:.1f}" y="{72 + line_no * 18:.1f}" font-size="14" '
            f'fill="{SECONDARY}">{xml_escape(line)}</text>'
        )
    for line_no, line in enumerate(said_lines):
        parts.append(
            f'<text x="{frame_x:.1f}" y="{chrome_top + line_no * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(line)}</text>'
        )

    # ---- the filled bands, clipped exactly against the levels ----
    if fill:
        for triangle in mesh:
            corners = [(points[i][0], points[i][1], values[i]) for i in triangle]
            edges = [z_lo - 1.0] + list(bands) + [z_hi + 1.0]
            for index in range(len(edges) - 1):
                piece_poly = _clip_above(corners, edges[index], True)
                if len(piece_poly) >= 3:
                    piece_poly = _clip_above(piece_poly, edges[index + 1], False)
                if len(piece_poly) < 3:
                    continue
                path = " ".join(
                    ("M " if k == 0 else "L ") + "{:.1f},{:.1f}".format(*to_px(cx, cy))
                    for k, (cx, cy, _) in enumerate(piece_poly)
                )
                colour = viridis(index / max(len(bands), 1))
                # Stroked in its own fill colour: abutting polygons leave an
                # anti-aliasing seam, and four hundred of them read as a
                # cobweb over a fill meant to be seen as continuous.
                parts.append(
                    f'<path d="{path} Z" fill="{colour}" stroke="{colour}" '
                    f'stroke-width="1"/>'
                )

    if show_mesh:
        mesh_path = " ".join(
            "M {:.1f},{:.1f} L {:.1f},{:.1f}".format(
                *to_px(*points[triangle[i]]), *to_px(*points[triangle[(i + 1) % 3]])
            )
            for triangle in mesh
            for i in range(3)
        )
        # White over the fill, grey without it: the mesh is meant to be
        # the faintest thing on the figure, and "faint" is a different
        # colour depending on what it is drawn over.
        parts.append(
            f'<path d="{mesh_path}" fill="none" '
            f'stroke="{BG if fill else GRIDLINE}" stroke-width="0.5" '
            f'opacity="{0.3 if fill else 0.7}"/>'
        )

    labels: List[Tuple[int, bool, float, List[Tuple[float, float, float, float]]]] = []
    for line in cut_lines:
        index = int(line["index"])
        is_threshold = bool(line["threshold"])
        # Light ink over the dark end of the ramp, dark over the bright
        # end: one fixed line colour is unreadable across half of any
        # fill. With no fill under them the lines are all ink, because
        # white on white is not a line.
        ink = "#FFFFFF" if fill and index < len(drawn) * 0.58 else INK
        weight = 2.4 if is_threshold else 1.1
        if line["firm"]:
            parts.append(
                f'<path d="{as_path(line["firm"])}" fill="none" stroke="{ink}" '
                f'stroke-width="{weight}" opacity="{0.95 if is_threshold else 0.75}"/>'
            )
        if line["loose"]:
            parts.append(
                f'<path d="{as_path(line["loose"])}" fill="none" stroke="{ink}" '
                f'stroke-width="{weight}" stroke-dasharray="5 5" '
                f'opacity="{0.9 if is_threshold else 0.45}"/>'
            )

        if label_levels:
            labels.append((index, is_threshold, float(line["level"]),
                           list(line["firm"]) + list(line["loose"])))

    # ---- the sensors themselves ----
    if show_points:
        for px, py in points:
            cx, cy = to_px(px, py)
            parts.append(
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="2.1" fill="{BG}" '
                f'stroke="{INK}" stroke-width="0.9" opacity="0.85"/>'
            )

    # ---- the level numbers, written over everything they label ----
    # Last of the plot layers on purpose: a number drawn as its own level
    # finishes is crossed by the next level's line and by every sample
    # dot after it, and a 1 with a dot on its head reads as a 9.
    for index, is_threshold, level_value, pieces in labels:
        # Each level gets its own anchor, walked round the plot by the
        # golden angle: nearest-the-centre puts every label on the same
        # shoulder of the same peak, and five of them pile up there.
        angle = index * 2.39996
        target = (
            plot_x + plot_w * (0.5 + 0.33 * math.cos(angle)),
            plot_y + plot_h * (0.5 - 0.33 * math.sin(angle)),
        )
        anchors = [
            to_px((piece[0] + piece[2]) / 2.0, (piece[1] + piece[3]) / 2.0)
            for piece in pieces
        ]
        lx, ly = min(
            anchors,
            key=lambda a: (a[0] - target[0]) ** 2 + (a[1] - target[1]) ** 2,
        )
        text = measured(level_value)
        parts.append(
            f'<rect x="{lx - 3.6 * len(text) - 4:.1f}" y="{ly - 8:.1f}" '
            f'width="{7.2 * len(text) + 8:.1f}" height="15" fill="{BG}" rx="3"/>'
        )
        parts.append(
            f'<text x="{lx:.1f}" y="{ly + 4:.1f}" font-size="10" fill="{INK}" '
            f'text-anchor="middle" font-family="{mono_family}" '
            f'font-weight="{700 if is_threshold else 400}">{xml_escape(text)}</text>'
        )

        for index, (px, py) in enumerate(points):
            cx, cy = to_px(px, py)
            label = (
                f"sensor at east {located(px)}, north {located(py)}: "
                f"{measured(values[index])} {unit}"
            )
            parts.append(
                f'<circle class="hit" id="sensor-{index}" cx="{cx:.1f}" cy="{cy:.1f}" '
                f'r="7" fill="transparent" tabindex="0" role="img" '
                f'aria-label="{xml_escape(label)}">'
                f'<title>{xml_escape(label)}</title></circle>'
            )
        for index, (px, py) in enumerate(points):
            cx, cy = to_px(px, py)
            parts.append(
                tooltip_bubble(
                    cx, cy - 10.0,
                    [
                        f"{measured(values[index])} {unit}",
                        f"east {located(px)} · north {located(py)}",
                    ],
                    canvas_w=width, canvas_h=height,
                    bg=BG, border=GRIDLINE, ink=INK, secondary=SECONDARY,
                    font_family=chrome_stack_for_theme(theme),
                    elem_id=f"sensortip-{index}",
                )
            )

    parts.append(
        f'<rect x="{plot_x:.1f}" y="{plot_y:.1f}" width="{plot_w:.1f}" height="{plot_h:.1f}" '
        f'fill="none" stroke="{GRIDLINE}" stroke-width="1"/>'
    )

    # ---- axes ----
    for value in nice_ticks_range(x_lo, x_hi, 5):
        if not x_lo <= value <= x_hi:
            continue
        px, _ = to_px(value, y_lo)
        parts.append(
            f'<text x="{px:.1f}" y="{plot_y + plot_h + 20:.1f}" font-size="11" '
            f'fill="{SECONDARY}" text-anchor="middle" font-family="{mono_family}">'
            f'{fmt_number(value)}</text>'
        )
    for value in nice_ticks_range(y_lo, y_hi, 5):
        if not y_lo <= value <= y_hi:
            continue
        _, py = to_px(x_lo, value)
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{py + 4:.1f}" font-size="11" '
            f'fill="{SECONDARY}" text-anchor="end" font-family="{mono_family}">'
            f'{fmt_number(value)}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{plot_y + plot_h + 44:.1f}" font-size="12" '
        f'fill="{SECONDARY}" text-anchor="middle">{xml_escape(x_label)}</text>'
    )
    parts.append(
        f'<text x="{plot_x:.1f}" y="{plot_y - 12:.1f}" font-size="12" fill="{SECONDARY}">'
        f'{xml_escape(y_label)}</text>'
    )

    # ---- the band legend, each band labelled with the level that opens it ----
    legend_x = plot_x + plot_w + 36.0
    band_h = min(26.0, plot_h / (len(bands) + 1))
    parts.append(
        f'<text x="{legend_x:.1f}" y="{plot_y - 12:.1f}" font-size="11" fill="{SECONDARY}">'
        f'{xml_escape(value_label)}</text>'
    )
    for index in range(len(bands), -1, -1):
        top = plot_y + (len(bands) - index) * band_h
        if fill:
            parts.append(
                f'<rect x="{legend_x:.1f}" y="{top:.1f}" width="16" '
                f'height="{band_h:.1f}" fill="{viridis(index / max(len(bands), 1))}"/>'
            )
        if index > 0:
            # Without a fill there are no bands to key, only levels, so
            # the swatches go and the numbers move into their place: a
            # colour key for colours nothing was painted in is furniture
            # that means nothing.
            parts.append(
                f'<text x="{legend_x + (24 if fill else 0):.1f}" '
                f'y="{top + band_h + 4:.1f}" font-size="10" '
                f'fill="{SECONDARY}" font-family="{mono_family}">'
                f'{measured(bands[index - 1])}</text>'
            )
    if threshold is not None:
        key_y = plot_y + (len(bands) + 1) * band_h + 30.0
        parts.append(
            f'<path d="M {legend_x:.1f},{key_y:.1f} L {legend_x + 30:.1f},{key_y:.1f}" '
            f'stroke="{INK}" stroke-width="2.4" fill="none"/>'
        )
        parts.append(
            f'<text x="{legend_x:.1f}" y="{key_y + 16:.1f}" font-size="10" '
            f'fill="{SECONDARY}">{xml_escape(threshold_label)}</text>'
        )
        parts.append(
            f'<text x="{legend_x:.1f}" y="{key_y + 29:.1f}" font-size="10" '
            f'fill="{SECONDARY}" font-family="{mono_family}">'
            f'{measured(threshold)} {xml_escape(unit)}</text>'
        )
        parts.append(
            f'<path d="M {legend_x:.1f},{key_y + 50:.1f} L {legend_x + 30:.1f},'
            f'{key_y + 50:.1f}" stroke="{INK}" stroke-width="2.4" '
            f'stroke-dasharray="5 5" fill="none"/>'
        )
        parts.append(
            f'<text x="{legend_x:.1f}" y="{key_y + 66:.1f}" font-size="10" '
            f'fill="{SECONDARY}">no sensor within</text>'
        )
        parts.append(
            f'<text x="{legend_x:.1f}" y="{key_y + 79:.1f}" font-size="10" '
            f'fill="{SECONDARY}" font-family="{mono_family}">'
            f'{located(support_at)} {xml_escape(coord_unit)}</text>'
        )

    for line_no, line_text in enumerate(found_lines):
        parts.append(
            f'<text x="{frame_x:.1f}" '
            f'y="{height - 24 - (len(found_lines) - 1 - line_no) * 17:.1f}" '
            f'font-size="12" fill="{SECONDARY}" font-family="{mono_family}">'
            f'{xml_escape(line_text)}</text>'
        )
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_tricontour(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "A third of the guideline line is a guess, and is drawn as one",
    subtitle: str = "PM2.5 across a city's sensor network, triangulated and dashed where no sensor is near.",
    width: int = 880,
    height: int = 700,
    x: str = "east_km",
    y: str = "north_km",
    z: str = "pm25",
    levels: int = 7,
    cuts: Optional[List[float]] = None,
    threshold: Optional[float] = 15.0,
    threshold_label: str = "WHO 24-hour guideline",
    max_edge: float = 0.26,
    support_radius: Optional[float] = None,
    support_spacing: float = 2.0,
    min_angle: float = 3.0,
    fill: bool = True,
    show_mesh: bool = True,
    show_points: bool = True,
    label_levels: bool = True,
    x_label: str = "east, km",
    y_label: str = "north, km",
    value_label: str = "PM2.5, µg/m³",
    unit: str = "µg/m³",
    coord_unit: str = "km",
    summary: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored triangulated contour and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Scattered rows with keys ``east_km``, ``north_km`` and ``pm25``,
        or whatever `x`, `y` and `z` name. Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to
        ``assets/svg-examples/tricontour.svg``.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    x, y, z : str
        Which keys hold the coordinates and the measured value.
    levels : int
        Roughly how many iso-levels to draw. Ignored when `cuts` is given.
    cuts : list of float or None
        Explicit levels in the value's own units.
    threshold : float or None
        The level to draw heavier, as the one a reader acts on.
    threshold_label : str
        What that line is.
    max_edge : float
        Drop triangles with an edge longer than this fraction of the span.
    support_radius : float or None
        How far a piece of contour may sit from the nearest sample and
        still count as supported, in the data's own units.
    support_spacing : float
        Multiple of the network's own spacing used when `support_radius`
        is ``None``.
    min_angle : float
        Drop triangles narrower than this, in degrees, as hull splinters.
    fill, show_mesh, show_points, label_levels : bool
        Which layers to draw.
    x_label, y_label, value_label, unit : str
        Axis titles, the field's name and its unit.
    coord_unit : str
        The unit the coordinates are in.
    summary, finding : str or None
        The chrome line and the closing line; ``None`` composes them.
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
    >>> p = make_tricontour()
    >>> p.exists()
    True
    """
    svg = build_svg(
        data, title=title, subtitle=subtitle, width=width, height=height,
        x=x, y=y, z=z, levels=levels, cuts=cuts, threshold=threshold,
        threshold_label=threshold_label, max_edge=max_edge,
        support_radius=support_radius, support_spacing=support_spacing,
        min_angle=min_angle,
        fill=fill, show_mesh=show_mesh, show_points=show_points,
        label_levels=label_levels, x_label=x_label, y_label=y_label,
        value_label=value_label, unit=unit, coord_unit=coord_unit,
        summary=summary, finding=finding,
        mode=mode, accessibility=accessibility, theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "tricontour")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(
        __file__, "tricontour", build_svg,
        description="Generate iso-lines over scattered, triangulated samples.",
    )


if __name__ == "__main__":
    main()
