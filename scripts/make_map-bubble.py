#!/usr/bin/env python3
"""
make_map-bubble — a house-styled proportional-symbol map as hand-authored SVG.

A *bubble map* (proportional-symbol map) encodes one quantity per place as
the **area** of a circle planted there. Against a choropleth — the other
obvious way to put a number on a map — it has one decisive advantage for
*totals*: a choropleth shades territory, so the eye reads the number as
spread over the area, and the largest countries shout while the smallest
vanish however big their number is. Russia would dominate a choropleth of
emissions it does not dominate; Singapore would disappear from one of
throughput it leads. A circle is sized by the number alone, and the map
underneath is only there to say where.

Area, not radius. Doubling a circle's radius quadruples its ink, so
radius-encoded circles overstate large values by the square. Every radius
here is ``sqrt(value)`` scaled, the only way the eye's reading of the blob
matches the number behind it.

Area is still a weak channel — Cleveland & McGill rank it below position and
length — so no bubble is left to be judged alone: each carries its own
number, and the nested-circle legend gives the eye a reference to measure
against rather than a scale it has to imagine.

This example sizes each circle by a country's annual **fossil CO₂
emissions**, in gigatonnes (2023 order of magnitude, Global Carbon Budget /
EDGAR). The takeaway is the concentration: China and the United States
together out-emit the twelve next-largest emitters on this map combined.

Geometry is self-contained: the land silhouette and the equal-area **Equal
Earth** projection come from :mod:`_worldmap`. Equal area matters doubly on
a bubble map — a projection that inflates the high latitudes would inflate
the apparent size of northern bubbles against equatorial ones, which is
exactly the comparison the figure exists to support.

A note on how the demo data was chosen. A world map 1 440 px wide gives
about 4 px to a degree of longitude, so a 30 px circle covers some 800 km:
any two places closer than that merge into one blob whatever the label
placement does. The first draft of this figure used container ports and was
unreadable for that reason — Shanghai and Ningbo-Zhoushan landed 4 px apart
under circles 46 and 39 px wide. Country-level emissions are the right
granularity for a world frame; a port map is a regional figure.

Running the module writes the SVG artifact to
``sprezzature-figures/assets/svg-examples/map-bubble.svg``.

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
#: Canvas size, in user-space pixels.
_WIDTH: int = 1480
_HEIGHT: int = 980

#: Inner map viewport. The fit is uniform on both axes -- squashing one to
#: fill the box would undo the equal-area property the projection was chosen
#: for -- so the viewport has to be given the map's own proportions or the
#: map floats in it. The vendored land spans 5.312 x 2.617 projection units,
#: an aspect of 2.03, and 1440 / 2.03 is where this height comes from. The
#: first draft guessed 2.7 and drew a 1123 px map inside a 1440 px box with
#: 180 px of white on either side.
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

#: The largest bubble's radius, in pixels. At this canvas width it covers
#: roughly 800 km, which is the resolution limit of the whole figure: two
#: places closer than that cannot be told apart whatever is done with the
#: labels. Raising it makes the encoding louder and the map blinder.
_MAX_R: float = 30.0

#: Below this a bubble is a dot whose size the eye cannot judge, so the
#: scale is floored rather than left to shrink away.
_MIN_R: float = 6.0

#: Label type sizes. The value line is set in the mono stack so the digits
#: of neighbouring labels line up down the map.
_NAME_PX: float = 14.0
_VALUE_PX: float = 12.5

#: The four places a label can sit relative to its bubble, in order of
#: preference. Right and left first: a label beside a circle reads as
#: belonging to it more readily than one stacked above or below.
_POSES: Tuple[str, ...] = ("right", "left", "above", "below")

#: How close a label may come to a bubble that is not its own before the
#: placement treats it as ambiguous. Clearing a circle by a hair is enough
#: for a geometric test and not enough for a reader.
_NEAR_PX: float = 12.0


# ------------------------------------------------------------------
# Data — annual fossil CO2 emissions, by country
# ------------------------------------------------------------------
#: ``{name, lon, lat, gt}``. Emissions are annual fossil CO₂ in gigatonnes,
#: at a 2023 order of magnitude (Global Carbon Budget / EDGAR). The
#: coordinates are a representative interior point per country, not a
#: computed centroid: a centroid puts Indonesia in the sea and Norway in
#: Sweden. A teaching figure, not an official statistical release.
DEMO_DATA: List[Dict[str, Any]] = [
    {"name": "China", "lon": 104.0, "lat": 35.0, "gt": 11.5},
    {"name": "United States", "lon": -98.0, "lat": 39.0, "gt": 4.9},
    {"name": "India", "lon": 79.0, "lat": 22.0, "gt": 2.8},
    {"name": "Russia", "lon": 95.0, "lat": 61.0, "gt": 1.8},
    {"name": "Japan", "lon": 138.0, "lat": 36.0, "gt": 1.1},
    {"name": "Iran", "lon": 53.0, "lat": 32.0, "gt": 0.75},
    {"name": "Germany", "lon": 10.0, "lat": 51.0, "gt": 0.67},
    {"name": "Saudi Arabia", "lon": 45.0, "lat": 24.0, "gt": 0.64},
    {"name": "Indonesia", "lon": 113.0, "lat": -1.0, "gt": 0.62},
    {"name": "South Korea", "lon": 128.0, "lat": 36.0, "gt": 0.61},
    {"name": "Canada", "lon": -106.0, "lat": 56.0, "gt": 0.58},
    {"name": "Brazil", "lon": -52.0, "lat": -11.0, "gt": 0.49},
    {"name": "South Africa", "lon": 25.0, "lat": -29.0, "gt": 0.44},
    {"name": "Australia", "lon": 134.0, "lat": -25.0, "gt": 0.39},
]


def _radius_scale(rows: List[Dict[str, Any]]) -> Callable[[float], float]:
    """Return ``value -> radius`` scaled by area, not by radius.

    The largest value maps to :data:`_MAX_R`; every other radius is
    ``_MAX_R * sqrt(v / v_max)``, so a country emitting half as much draws
    half the ink rather than half the width.
    """
    v_max = max(float(r["gt"]) for r in rows) or 1.0

    def radius(value: float) -> float:
        return max(_MIN_R, _MAX_R * math.sqrt(max(value, 0.0) / v_max))

    return radius


def _fmt(value: float) -> str:
    """A country's emissions, at the precision the number deserves.

    Above a gigatonne one decimal is plenty and two would be noise; below
    it, one decimal would round a third of this list to the same "0.6" and
    the eye would read a tie that is not there.
    """
    return f"{value:.1f}" if value >= 1.0 else f"{value:.2f}"


def _label_box(
    cx: float, cy: float, r: float, pose: str, name: str, value: str
) -> Tuple[float, float, float, float]:
    """Bounding box the two label lines occupy in `pose`.

    The box covers the name line and the value line under it: testing only
    the name would let the numbers collide underneath it, which is how the
    first draft of this figure passed its own placement check and failed the
    linter.
    """
    width = max(text_width(name, _NAME_PX), text_width(f"{value} Gt", _VALUE_PX))
    height = _NAME_PX + _VALUE_PX + 2.0
    gap = 5.0
    if pose == "right":
        x0, y0 = cx + r + gap, cy - height / 2.0
    elif pose == "left":
        x0, y0 = cx - r - gap - width, cy - height / 2.0
    elif pose == "above":
        x0, y0 = cx - width / 2.0, cy - r - gap - height
    else:  # below
        x0, y0 = cx - width / 2.0, cy + r + gap
    return x0, y0, x0 + width, y0 + height


def _overlaps(a: Tuple[float, ...], b: Tuple[float, ...]) -> bool:
    """True when two boxes share any area."""
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _covers_circle(box: Tuple[float, ...], cx: float, cy: float, r: float) -> bool:
    """True when a label box reaches into a circle.

    A label lying across someone else's bubble is as unreadable as one lying
    across another label, and the linter cannot see it -- it checks text
    against text. Testing it here is the only place it gets caught.
    """
    nearest_x = min(max(cx, box[0]), box[2])
    nearest_y = min(max(cy, box[1]), box[3])
    return math.hypot(cx - nearest_x, cy - nearest_y) < r


def _inside_map(box: Tuple[float, ...]) -> bool:
    """True when a label box stays inside the map viewport."""
    return (
        box[0] >= _MAP_X + 2.0
        and box[2] <= _MAP_X + _MAP_W - 2.0
        and box[1] >= _MAP_Y + 2.0
        and box[3] <= _MAP_Y + _MAP_H - 2.0
    )


def _place_labels(
    bubbles: List[Tuple[str, str, float, float, float]]
) -> Dict[str, Tuple[str, Tuple[float, float, float, float]]]:
    """Choose a pose per bubble so that nothing lands on anything.

    Bubbles are taken largest-first, so the ones a reader looks at first get
    their pick of the room and the small ones work around them. A pose is
    rejected if it leaves the map, touches a label already placed, or lies
    across any bubble; among what survives, the earliest in :data:`_POSES`
    wins. If every pose fails, the one with the fewest collisions is kept —
    a label that overlaps is recoverable by eye, a country silently dropped
    from the map is not.
    """
    chosen: Dict[str, Tuple[str, Tuple[float, float, float, float]]] = {}
    taken: List[Tuple[float, float, float, float]] = []
    circles = [(cx, cy, r) for _, _, cx, cy, r in bubbles]
    for name, value, cx, cy, r in sorted(bubbles, key=lambda b: -b[4]):
        scored: List[Tuple[int, int, str, Tuple[float, float, float, float]]] = []
        for rank, pose in enumerate(_POSES):
            box = _label_box(cx, cy, r, pose, name, value)
            cost = 4 * sum(1 for other in taken if _overlaps(box, other))
            for ox, oy, orad in circles:
                if (ox, oy) == (cx, cy):
                    continue
                if _covers_circle(box, ox, oy, orad):
                    cost += 4  # lying across someone else's bubble
                elif _covers_circle(box, ox, oy, orad + _NEAR_PX):
                    # Not touching, but close enough that a reader attributes
                    # the name to the wrong circle. South Korea's label sat
                    # this way over China's bubble in the first render: legal
                    # by every hard test, and wrong to the eye.
                    cost += 1
            if not _inside_map(box):
                cost += 20  # off-canvas is worse than any collision
            scored.append((cost, rank, pose, box))
        _, _, pose, box = min(scored)
        chosen[name] = (pose, box)
        taken.append(box)
    return chosen


def _label_origin(cx: float, cy: float, r: float, pose: str, box: Tuple[float, ...]) -> Tuple[float, float]:
    """Baseline of the name line for a pose, consistent with its box."""
    if pose in ("right", "left"):
        side = cx + r + 5.0 if pose == "right" else cx - r - 5.0
        return side, cy - 1.0
    return cx, box[1] + _NAME_PX


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
) -> str:
    """Assemble the full bubble-map SVG document as a string.

    Parameters
    ----------
    data : list of dict, optional
        Rows with ``name``, ``lon``, ``lat`` and ``gt``. Defaults to
        :data:`DEMO_DATA`.
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
    rows.sort(key=lambda r: -float(r["gt"]))
    palette = load_palette(accessibility, theme)
    fonts = chrome_stack_for_theme(theme)
    mono = mono_stack_for_theme(theme)
    blue = palette.get("Blue", "#007AFF")

    rings = load_land_rings()
    project = fit_to_viewport(rings, _MAP_X, _MAP_Y, _MAP_W, _MAP_H)
    radius = _radius_scale(rows)

    head = title or "Two countries out-emit the twelve next-largest combined"
    sub = subtitle or (
        "Annual fossil CO₂ emissions, gigatonnes · circle area is proportional "
        "to the total"
    )

    parts: List[str] = [
        svg_open(_WIDTH, _HEIGHT, "bubble-title", "bubble-desc", font_family=fonts)
    ]
    parts.append(
        f'<title id="bubble-title">{xml_escape(head)}</title>'
        f'<desc id="bubble-desc">{xml_escape(sub)}. Fourteen countries on an '
        f"Equal Earth world map, each drawn as a circle whose area is "
        f"proportional to its annual fossil carbon dioxide emissions.</desc>"
    )
    parts.append(
        "<style>"
        + os_adaptive_style({"Blue": blue})
        + os_dark_style()
        # The reveal rules only turn a bubble ON. Without this base rule every
        # tooltip would sit at full opacity, permanently, across the map.
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

    # ---- bubbles ----
    bubbles: List[Tuple[str, str, float, float, float]] = []
    for row in rows:
        cx, cy = project(float(row["lon"]), float(row["lat"]))
        bubbles.append(
            (str(row["name"]), _fmt(float(row["gt"])), cx, cy, radius(float(row["gt"])))
        )

    tips: List[str] = []
    for idx, (row, (name, value, cx, cy, r)) in enumerate(zip(rows, bubbles, strict=True)):
        parts.append(
            f'<circle id="hit-{idx}" class="hit" tabindex="0" cx="{cx:.1f}" cy="{cy:.1f}" '
            f'r="{r:.1f}" fill="{blue}" fill-opacity="0.55" stroke="{blue}" '
            f'stroke-width="1.5"><title>{xml_escape(name)} — {value} '
            f'gigatonnes of CO₂ a year</title></circle>'
        )
        tips.append(
            tooltip_bubble(
                cx, cy - r - 10.0,
                [name, f"{value} Gt CO₂ a year",
                 f"{float(row['gt']) / sum(float(x['gt']) for x in rows) * 100:.0f}% "
                 "of the countries shown"],
                anchor="middle", canvas_w=_WIDTH, canvas_h=_HEIGHT,
                ink=_INK, secondary=_SUBTLE, border=_LAND_EDGE,
                elem_id=f"tip-{idx}",
            )
        )

    # ---- labels, placed so nothing lands on anything ----
    poses = _place_labels(bubbles)
    for name, value, cx, cy, r in bubbles:
        pose, box = poses[name]
        lx, ly = _label_origin(cx, cy, r, pose, box)
        anchor = {"right": "start", "left": "end"}.get(pose, "middle")
        parts.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="{_NAME_PX:.0f}" '
            f'font-weight="600" fill="{_INK}" text-anchor="{anchor}" stroke="{_BG}" '
            f'stroke-width="3" paint-order="stroke" '
            f'style="pointer-events:none">{xml_escape(name)}</text>'
        )
        parts.append(
            f'<text x="{lx:.1f}" y="{ly + _VALUE_PX + 2.0:.1f}" '
            f'font-size="{_VALUE_PX:.1f}" font-family="{mono}" fill="{_SUBTLE}" '
            f'text-anchor="{anchor}" stroke="{_BG}" stroke-width="3" '
            f'paint-order="stroke" style="pointer-events:none">{value} Gt</text>'
        )

    parts.extend(tips)

    # ---- size legend: nested circles, a reference to measure against ----
    legend_x = _MAP_X + 70.0
    legend_base = float(_HEIGHT - 54)
    parts.append(
        f'<text x="{_MAP_X + 8:.1f}" y="{legend_base - 2 * _MAX_R - 14:.1f}" '
        f'font-size="13" font-weight="700" fill="{_INK}">'
        f'CIRCLE AREA = ANNUAL EMISSIONS</text>'
    )
    for value in (10.0, 5.0, 1.0):
        r = radius(value)
        parts.append(
            f'<circle cx="{legend_x:.1f}" cy="{legend_base - r:.1f}" r="{r:.1f}" '
            f'fill="none" stroke="{_SUBTLE}" stroke-width="1.1"/>'
        )
        parts.append(
            f'<line x1="{legend_x:.1f}" y1="{legend_base - 2 * r:.1f}" '
            f'x2="{legend_x + _MAX_R + 12:.1f}" y2="{legend_base - 2 * r:.1f}" '
            f'stroke="{_LAND_EDGE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{legend_x + _MAX_R + 18:.1f}" y="{legend_base - 2 * r + 4:.1f}" '
            f'font-size="13" fill="{_SUBTLE}">{value:.0f} Gt a year</text>'
        )

    # ---- footnote ----
    parts.append(
        f'<text x="{_WIDTH - 24:.1f}" y="{_HEIGHT - 38:.1f}" font-size="12.5" '
        f'fill="{_SUBTLE}" text-anchor="end">Equal Earth (equal-area) projection · '
        f'one circle per country, placed at a representative interior point</text>'
    )
    parts.append(
        f'<text x="{_WIDTH - 24:.1f}" y="{_HEIGHT - 18:.1f}" font-size="12.5" '
        f'fill="{_SUBTLE}" text-anchor="end">Fossil CO₂ only · 2023 order of '
        f'magnitude, Global Carbon Budget / EDGAR</text>'
    )

    parts.append(fullscreen_control(_WIDTH, _HEIGHT, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_map_bubble(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "",
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render the bubble map and write it to ``out``.

    The standard ``make_<kind>`` entry the figure registry dispatches to, so
    ``make-figure map-bubble`` and the Studio work like every other figure.

    Parameters
    ----------
    data : list of dict, optional
        Rows with ``name``, ``lon``, ``lat`` and ``gt``. Defaults to
        :data:`DEMO_DATA`.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/map-bubble.svg``.
    title : str, optional
        Overrides the headline.
    mode, accessibility, theme : str
        Forwarded to :func:`build_svg`.
    """
    svg = build_svg(
        data, mode=mode, accessibility=accessibility, theme=theme, title=title or None
    )
    dest = Path(out) if out else svg_example_path(__file__, "map-bubble")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """Write the map-bubble SVG to the skill's ``svg-examples`` folder."""
    render_cli(__file__, "map-bubble", build_svg, description="Render the map-bubble SVG.")


if __name__ == "__main__":
    main()
