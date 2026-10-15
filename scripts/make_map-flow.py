#!/usr/bin/env python3
"""
make_map-flow — a house-styled connection map as hand-authored SVG.

A *connection map* (flow map) draws a line between two places for every pair
that exchanges something, with the line's **width** encoding how much. It is
the chart for origin-destination data: migration corridors, trade lanes,
flights, remittances. A bubble map would show where the people are, a
choropleth where they are dense; only a line says *from here to there*.

The lines are **great circles**, sampled and projected point by point rather
than drawn straight. On any world projection the shortest path between two
places is a curve, and a straight segment is not a simplification of it but a
different route: the straight Beijing-to-Chicago line crosses the Pacific,
the real one goes over the Arctic. Sampling costs a few dozen points per
link and buys a figure that does not misstate its own geography.

Width is the weak link and the figure is built knowing it. Stroke width is a
length judged without a baseline, so the ranked list in the footer carries
the order precisely and the map carries only the shape of it — which
corridors exist, where they run, which one is unmistakably the thickest.
Three widths are drawn in the legend as a reference to measure against.

This example draws the ten largest international **migration corridors** by
migrant stock, in millions (2020 order of magnitude, UN DESA). The takeaway
is the single outlier: Mexico to the United States carries nearly three
times more people than the next corridor on the list.

One corridor was deliberately kept out of the demo rows, and it is worth
saying why, because the reason is a property of this chart type rather than
of this data. India and the United States sit 177 degrees of longitude
apart — nearly antipodal — and the great circle between two nearly antipodal
places passes within a few degrees of the pole: 87.5 degrees north, here.
On any pseudocylindrical projection that path sweeps the entire width of the
map along its top edge, and the result reads as a drawing error rather than
as the shortest route it correctly is. A connection map cannot draw a nearly
antipodal pair honestly *and* legibly; this one picks legibility and leaves
the pair out.

Geometry is self-contained: the land silhouette and the equal-area **Equal
Earth** projection come from :mod:`_worldmap`.

Running the module writes the SVG artifact to
``sprezzature-figures/assets/svg-examples/map-flow.svg``.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _style import load_palette, os_adaptive_style, os_dark_style  # noqa: E402
from _svg import foreground_tip_css, svg_open, tooltip_bubble, xml_escape  # noqa: E402
from _textfit import text_width  # noqa: E402
from _worldmap import fit_to_viewport, graticule_paths, land_path, load_land_rings  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

# ------------------------------------------------------------------
# Canvas + house-style constants
# ------------------------------------------------------------------
#: Canvas size, in user-space pixels. Taller than its sibling glyph maps
#: because the footer carries more: a width reference *and* the ten-row
#: ranked list that holds the order the stroke widths cannot.
_WIDTH: int = 1480
_HEIGHT: int = 1030

#: Inner map viewport, given the map's own 2.03 aspect so the drawing fills
#: it instead of floating in the middle of a box the wrong shape.
_MAP_X: float = 20.0
_MAP_Y: float = 118.0
_MAP_W: float = 1440.0
_MAP_H: float = 709.0

#: House-style inks.
_INK: str = "#1D1D1F"
_SUBTLE: str = "#6E6E73"
_BG: str = "#FFFFFF"
_LAND: str = "#EDEDF2"
_LAND_EDGE: str = "#DDDDE3"
_GRAT: str = "#F4F4F7"

#: Stroke width, in pixels, for the largest and smallest corridor. The floor
#: is not cosmetic: below about a pixel and a half a line stops reading as a
#: line at all and the corridor silently leaves the map.
_MAX_STROKE: float = 13.0
_MIN_STROKE: float = 1.6

#: How many points each great circle is sampled at. Enough that the curve is
#: smooth at poster scale; the cost is a few hundred bytes a link.
_ARC_SAMPLES: int = 64

#: A jump wider than this in *longitude* between consecutive samples means
#: the arc crossed the antimeridian and came back on the other edge of the
#: map. Drawing through it would lay a line straight across the sheet.
#:
#: The test is on the data, not on the projected pixels, and that is the
#: whole point. A great circle from East Asia to North America passes within
#: twenty degrees of the pole, and Equal Earth squeezes x by cos(theta) up
#: there -- so the 180-degree jump at the antimeridian comes out as a few
#: dozen pixels and slips under any pixel threshold. The first version of
#: this figure used 400 px and drew a line clean across the top of the world.
_WRAP_DEG: float = 180.0

#: Label type size for the place names.
_NAME_PX: float = 13.5

#: The four places a name can sit relative to its dot, in order of
#: preference.
_POSES: Tuple[str, ...] = ("right", "left", "above", "below")


# ------------------------------------------------------------------
# Data — the largest international migration corridors
# ------------------------------------------------------------------
#: ``{name: (lon, lat)}`` for every endpoint named in :data:`DEMO_DATA`. A
#: representative interior point per country, not a computed centroid.
PLACES: Dict[str, Tuple[float, float]] = {
    "Mexico": (-102.0, 23.6),
    "United States": (-98.0, 39.0),
    "Syria": (38.0, 35.0),
    "Turkey": (35.0, 39.0),
    "India": (79.0, 22.0),
    "Bangladesh": (90.0, 24.0),
    "United Arab Emirates": (54.0, 24.0),
    "Kazakhstan": (67.0, 48.0),
    "Russia": (95.0, 61.0),
    "China": (104.0, 35.0),
    "Philippines": (122.0, 12.0),
    "Venezuela": (-66.0, 7.0),
    "Colombia": (-74.0, 4.0),
    "Myanmar": (96.0, 21.0),
    "Thailand": (101.0, 15.0),
    "Algeria": (3.0, 28.0),
    "France": (2.0, 47.0),
}

#: ``{origin, destination, people}`` with migrant stock in millions, at a
#: 2020 order of magnitude (UN DESA international migrant stock). A teaching
#: figure, not an official statistical release.
DEMO_DATA: List[Dict[str, Any]] = [
    {"origin": "Mexico", "destination": "United States", "people": 10.9},
    {"origin": "Syria", "destination": "Turkey", "people": 3.8},
    {"origin": "India", "destination": "United Arab Emirates", "people": 3.5},
    {"origin": "Bangladesh", "destination": "India", "people": 2.1},
    {"origin": "Kazakhstan", "destination": "Russia", "people": 2.5},
    {"origin": "China", "destination": "United States", "people": 2.2},
    {"origin": "Philippines", "destination": "United States", "people": 2.0},
    {"origin": "Myanmar", "destination": "Thailand", "people": 1.9},
    {"origin": "Venezuela", "destination": "Colombia", "people": 1.7},
    {"origin": "Algeria", "destination": "France", "people": 1.6},
]


def great_circle(
    a: Tuple[float, float], b: Tuple[float, float], samples: int = _ARC_SAMPLES
) -> List[Tuple[float, float]]:
    """Sample the great circle from `a` to `b` as ``(lon, lat)`` degrees.

    Spherical linear interpolation. Two places exactly antipodal have no
    unique great circle between them and the formula divides by zero there;
    that case returns the straight interpolation, which is as meaningful as
    anything else would be.

    Parameters
    ----------
    a, b : tuple of float
        ``(lon, lat)`` endpoints, in degrees.
    samples : int, optional
        How many points to return, endpoints included.

    Returns
    -------
    list of tuple
        ``(lon, lat)`` points in degrees, from `a` to `b`.
    """
    lon1, lat1 = math.radians(a[0]), math.radians(a[1])
    lon2, lat2 = math.radians(b[0]), math.radians(b[1])
    d = 2.0 * math.asin(
        min(
            1.0,
            math.sqrt(
                math.sin((lat2 - lat1) / 2.0) ** 2
                + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2.0) ** 2
            ),
        )
    )
    if d < 1e-9 or abs(math.sin(d)) < 1e-9:
        return [a, b]
    out: List[Tuple[float, float]] = []
    for i in range(samples):
        f = i / (samples - 1)
        s_a = math.sin((1.0 - f) * d) / math.sin(d)
        s_b = math.sin(f * d) / math.sin(d)
        x = s_a * math.cos(lat1) * math.cos(lon1) + s_b * math.cos(lat2) * math.cos(lon2)
        y = s_a * math.cos(lat1) * math.sin(lon1) + s_b * math.cos(lat2) * math.sin(lon2)
        z = s_a * math.sin(lat1) + s_b * math.sin(lat2)
        out.append(
            (
                math.degrees(math.atan2(y, x)),
                math.degrees(math.atan2(z, math.sqrt(x * x + y * y))),
            )
        )
    return out


def arc_path(
    a: Tuple[float, float],
    b: Tuple[float, float],
    project: Callable[[float, float], Tuple[float, float]],
) -> str:
    """The ``d`` attribute of one great-circle link, broken at the wrap.

    A corridor whose arc crosses the antimeridian comes back on the other
    side of the map. Joined up, that is a line straight across the sheet
    through places the route never touches; the path is cut into separate
    subpaths at the jump instead.
    """
    samples = great_circle(a, b)
    segments: List[List[Tuple[float, float]]] = [[project(*samples[0])]]
    # Pairwise, so the second sequence is shorter by one by construction --
    # `strict=True` is the wrong tool here and raises on every call.
    for prev, cur in zip(samples, samples[1:]):  # noqa: B905
        if abs(cur[0] - prev[0]) > _WRAP_DEG:
            segments.append([project(*cur)])
        else:
            segments[-1].append(project(*cur))
    return "".join(
        f"M{seg[0][0]:.1f},{seg[0][1]:.1f}"
        + "".join(f"L{px:.1f},{py:.1f}" for px, py in seg[1:])
        for seg in segments
        if len(seg) > 1
    )


def _label_box(
    cx: float, cy: float, pose: str, name: str
) -> Tuple[float, float, float, float]:
    """Bounding box a name would occupy in `pose`, next to a dot at (cx, cy)."""
    w = text_width(name, _NAME_PX)
    h = _NAME_PX
    gap = 8.0
    if pose == "right":
        x0, y0 = cx + gap, cy - h / 2.0
    elif pose == "left":
        x0, y0 = cx - gap - w, cy - h / 2.0
    elif pose == "above":
        x0, y0 = cx - w / 2.0, cy - gap - h
    else:
        x0, y0 = cx - w / 2.0, cy + gap
    return x0, y0, x0 + w, y0 + h


def _overlaps(a: Tuple[float, ...], b: Tuple[float, ...]) -> bool:
    """True when two boxes share any area."""
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _inside_map(box: Tuple[float, ...]) -> bool:
    """True when a label box stays inside the map viewport."""
    return (
        box[0] >= _MAP_X + 2.0
        and box[2] <= _MAP_X + _MAP_W - 2.0
        and box[1] >= _MAP_Y + 2.0
        and box[3] <= _MAP_Y + _MAP_H - 2.0
    )


def _place_labels(
    dots: List[Tuple[str, float, float]]
) -> Dict[str, Tuple[str, Tuple[float, float, float, float]]]:
    """Choose a pose per endpoint so the names clear each other.

    Endpoints are taken in the order the corridors are ranked, so the places
    on the biggest flows get first pick of the room. A pose that leaves the
    map is rejected; among the rest the earliest in :data:`_POSES` that hits
    nothing wins, and if every pose collides the least bad one is kept --
    a crowded label can still be read, a missing country cannot.
    """
    chosen: Dict[str, Tuple[str, Tuple[float, float, float, float]]] = {}
    taken: List[Tuple[float, float, float, float]] = []
    for name, cx, cy in dots:
        scored = []
        for rank, pose in enumerate(_POSES):
            box = _label_box(cx, cy, pose, name)
            cost = sum(1 for other in taken if _overlaps(box, other))
            if not _inside_map(box):
                cost += 10
            scored.append((cost, rank, pose, box))
        _, _, pose, box = min(scored)
        chosen[name] = (pose, box)
        taken.append(box)
    return chosen


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
) -> str:
    """Assemble the full connection-map SVG document as a string.

    Parameters
    ----------
    data : list of dict, optional
        Rows with ``origin``, ``destination`` and ``people``. Both endpoints
        must be keys of :data:`PLACES`. Defaults to :data:`DEMO_DATA`.
    mode : str, optional
        ``"self-contained"`` embeds the web fonts; anything else links them.
    accessibility : str, optional
        Palette accessibility level, forwarded to :func:`_style.load_palette`.
    theme : str, optional
        ``"corporate"`` (Roboto) or ``"academic"`` (Latin Modern).
    title, subtitle : str, optional
        Override the headline and the line under it.

    Returns
    -------
    str
        The complete SVG document.
    """
    rows = [dict(r) for r in (data or DEMO_DATA)]
    rows.sort(key=lambda r: -float(r["people"]))
    palette = load_palette(accessibility, theme)
    fonts = chrome_stack_for_theme(theme)
    mono = mono_stack_for_theme(theme)
    blue = palette.get("Blue", "#007AFF")

    rings = load_land_rings()
    project = fit_to_viewport(rings, _MAP_X, _MAP_Y, _MAP_W, _MAP_H)

    v_max = max(float(r["people"]) for r in rows) or 1.0

    def stroke(value: float) -> float:
        return _MIN_STROKE + (_MAX_STROKE - _MIN_STROKE) * (float(value) / v_max)

    head = title or "One migration corridor is nearly three times the next"
    sub = subtitle or (
        "Largest international migration corridors, millions of people · "
        "line width is the size of the flow"
    )

    parts: List[str] = [
        svg_open(_WIDTH, _HEIGHT, "flow-title", "flow-desc", font_family=fonts)
    ]
    parts.append(
        f'<title id="flow-title">{xml_escape(head)}</title>'
        f'<desc id="flow-desc">{xml_escape(sub)}. Ten great-circle links on an '
        f"Equal Earth world map, each joining an origin country to a "
        f"destination country, the stroke width proportional to the number of "
        f"people who made the move.</desc>"
    )
    parts.append(
        "<style>"
        + os_adaptive_style({"Blue": blue}, role="stroke")
        + os_dark_style()
        + ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + "@media (prefers-reduced-motion:reduce){.tip{transition:none}}"
        + foreground_tip_css(len(rows))
        + "</style>"
    )
    parts.append(f'<rect width="{_WIDTH}" height="{_HEIGHT}" fill="{_BG}"/>')

    # ---- header band ----
    parts.append(
        f'<text x="{_MAP_X + 8:.1f}" y="52" font-size="30" font-weight="700" '
        f'fill="{_INK}">{xml_escape(head)}</text>'
    )
    parts.append(
        f'<text x="{_MAP_X + 8:.1f}" y="86" font-size="17" '
        f'fill="{_SUBTLE}">{xml_escape(sub)}</text>'
    )

    # ---- basemap ----
    for d in graticule_paths(project):
        parts.append(f'<path d="{d}" fill="none" stroke="{_GRAT}" stroke-width="1"/>')
    parts.append(
        f'<path d="{land_path(rings, project)}" fill="{_LAND}" '
        f'stroke="{_LAND_EDGE}" stroke-width="0.6"/>'
    )

    # ---- links, thinnest first so the thickest stays legible on top ----
    tips: List[str] = []
    for idx, row in enumerate(reversed(rows)):
        origin, dest = str(row["origin"]), str(row["destination"])
        people = float(row["people"])
        d = arc_path(PLACES[origin], PLACES[dest], project)
        parts.append(
            f'<path id="hit-{len(rows) - 1 - idx}" class="hit" tabindex="0" d="{d}" '
            f'fill="none" stroke="{blue}" stroke-opacity="0.52" '
            f'stroke-width="{stroke(people):.1f}" stroke-linecap="round">'
            f'<title>{xml_escape(origin)} to {xml_escape(dest)} — '
            f'{people:.1f} million people</title></path>'
        )
        ox, oy = project(*PLACES[origin])
        tips.append(
            tooltip_bubble(
                ox, oy - 14.0,
                [f"{origin} → {dest}", f"{people:.1f} million people"],
                anchor="middle", canvas_w=_WIDTH, canvas_h=_HEIGHT,
                ink=_INK, secondary=_SUBTLE, border=_LAND_EDGE,
                elem_id=f"tip-{len(rows) - 1 - idx}",
            )
        )

    # ---- endpoints, each place once however many corridors touch it ----
    seen: List[Tuple[str, float, float]] = []
    for row in rows:
        for key in ("origin", "destination"):
            name = str(row[key])
            if any(n == name for n, _, _ in seen):
                continue
            px, py = project(*PLACES[name])
            seen.append((name, px, py))
    for _, px, py in seen:
        parts.append(
            f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3.6" fill="{_INK}" '
            f'stroke="{_BG}" stroke-width="1.4"/>'
        )

    poses = _place_labels(seen)
    for name, px, py in seen:
        pose, box = poses[name]
        anchor = {"right": "start", "left": "end"}.get(pose, "middle")
        if pose in ("right", "left"):
            lx = px + 8.0 if pose == "right" else px - 8.0
            ly = py + _NAME_PX / 2.0 - 2.0
        else:
            lx, ly = px, box[1] + _NAME_PX
        parts.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="{_NAME_PX:.1f}" '
            f'font-weight="600" fill="{_INK}" text-anchor="{anchor}" '
            f'stroke="{_BG}" stroke-width="3" paint-order="stroke" '
            f'style="pointer-events:none">{xml_escape(name)}</text>'
        )

    parts.extend(tips)

    # ---- width legend: the reference the eye cannot invent ----
    lx = _MAP_X + 10.0
    ly = float(_HEIGHT - 178)
    parts.append(
        f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="13" font-weight="700" '
        f'fill="{_INK}">LINE WIDTH = PEOPLE WHO MOVED</text>'
    )
    for i, reference in enumerate((10.0, 5.0, 2.0)):
        row_y = ly + 24.0 + i * 26.0
        parts.append(
            f'<line x1="{lx:.1f}" y1="{row_y:.1f}" x2="{lx + 74:.1f}" '
            f'y2="{row_y:.1f}" stroke="{blue}" stroke-opacity="0.52" '
            f'stroke-width="{stroke(reference):.1f}" stroke-linecap="round"/>'
        )
        parts.append(
            f'<text x="{lx + 86:.1f}" y="{row_y + 5:.1f}" font-size="13" '
            f'font-family="{mono}" fill="{_SUBTLE}">{reference:.0f} million</text>'
        )

    # ---- ranked list: where the precise order lives ----
    rx = lx + 270.0
    parts.append(
        f'<text x="{rx:.1f}" y="{ly:.1f}" font-size="13" font-weight="700" '
        f'fill="{_INK}">THE TEN LARGEST CORRIDORS</text>'
    )
    for i, row in enumerate(rows):
        col, slot = divmod(i, 5)
        row_y = ly + 22.0 + slot * 20.0
        parts.append(
            f'<text x="{rx + col * 330:.1f}" y="{row_y:.1f}" '
            f'font-size="13.5" fill="{_INK}">{i + 1}. {xml_escape(str(row["origin"]))} '
            f'→ {xml_escape(str(row["destination"]))}</text>'
        )
        parts.append(
            f'<text x="{rx + col * 330 + 300:.1f}" y="{row_y:.1f}" '
            f'font-size="13.5" font-family="{mono}" fill="{_SUBTLE}" '
            f'text-anchor="end">{float(row["people"]):.1f}</text>'
        )

    # ---- footnote ----
    parts.append(
        f'<text x="{_WIDTH - 24:.1f}" y="{_HEIGHT - 38:.1f}" font-size="12.5" '
        f'fill="{_SUBTLE}" text-anchor="end">Equal Earth (equal-area) projection · '
        f'links are great circles, sampled and projected, not straight lines</text>'
    )
    parts.append(
        f'<text x="{_WIDTH - 24:.1f}" y="{_HEIGHT - 18:.1f}" font-size="12.5" '
        f'fill="{_SUBTLE}" text-anchor="end">Migrant stock, 2020 order of '
        f'magnitude, UN DESA · hover a link for its figure</text>'
    )

    parts.append(fullscreen_control(_WIDTH, _HEIGHT, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_map_flow(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "",
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render the connection map and write it to ``out``.

    The standard ``make_<kind>`` entry the figure registry dispatches to, so
    ``make-figure map-flow`` and the Studio work like every other figure.

    Parameters
    ----------
    data : list of dict, optional
        Rows with ``origin``, ``destination`` and ``people``. Defaults to
        :data:`DEMO_DATA`.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/map-flow.svg``.
    title : str, optional
        Overrides the headline.
    mode, accessibility, theme : str
        Forwarded to :func:`build_svg`.
    """
    svg = build_svg(
        data, mode=mode, accessibility=accessibility, theme=theme, title=title or None
    )
    dest = Path(out) if out else svg_example_path(__file__, "map-flow")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """Write the map-flow SVG to the skill's ``svg-examples`` folder."""
    render_cli(__file__, "map-flow", build_svg, description="Render the map-flow SVG.")


if __name__ == "__main__":
    main()
