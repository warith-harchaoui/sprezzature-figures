#!/usr/bin/env python3
"""
make_map-pie — a house-styled pie-glyph map as hand-authored SVG.

A *pie-glyph map* plants a small pie at each place, so the reader compares
**compositions** across the map. This is the one job a pie does better than
a bar: it states that the parts are a whole, and the eye reads "mostly this,
a sliver of that" from a disc faster than it reads three heights and adds
them up.

Everywhere else a bar wins, and this figure is built to stay inside the pie's
narrow competence. Angle is a weak channel — Cleveland & McGill rank it
below position and length — so nothing here asks the reader to tell 21 % from
18 % by eye; what the figure asks is whether a region's disc is mostly dark
or mostly light, which angle answers at a glance. Three parts, not seven: a
pie with many slivers is a legend with extra steps.

The discs are all the **same size**. Sizing them by regional population is
the textbook second variable for this chart, and it would make the figure
worse here: East Asia holds some thirty-eight times Oceania's people, so the
radii would stand six to one and Oceania's wedges would be unreadable at the
size that keeps East Asia's from swallowing the map. A constant radius keeps
every angle comparable with every other, which is the comparison this figure
exists to support.

This example plants one pie per world region, split by **age band** — under
15, 15 to 64, 65 and over (2023 order of magnitude, UN World Population
Prospects). The takeaway is the contrast at the two ends: in Africa children
outnumber people over 65 by about ten to one, and in Europe the ratio has
turned over entirely.

Geometry is self-contained: the land silhouette and the equal-area **Equal
Earth** projection come from :mod:`_worldmap`.

Running the module writes the SVG artifact to
``sprezzature-figures/assets/svg-examples/map-pie.svg``.

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
from _style import load_palette, os_adaptive_style, os_dark_style  # noqa: E402
from _svg import foreground_tip_css, svg_open, tooltip_bubble, xml_escape  # noqa: E402
from _textfit import text_width  # noqa: E402
from _worldmap import fit_to_viewport, graticule_paths, land_path, load_land_rings  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme  # noqa: E402

# ------------------------------------------------------------------
# Canvas + house-style constants
# ------------------------------------------------------------------
#: Canvas size, in user-space pixels.
_WIDTH: int = 1480
_HEIGHT: int = 980

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

#: Pie radius, in pixels. The same for every region, on purpose -- see the
#: module docstring. Large enough that a 4 % wedge is still a visible sliver
#: rather than a hairline.
_PIE_R: float = 33.0

#: Type size of the region name under each pie.
_NAME_PX: float = 14.0


# ------------------------------------------------------------------
# Data — population by age band, by region
# ------------------------------------------------------------------
#: The three bands every pie splits into, in drawing order from twelve
#: o'clock. Keys match the house palette so the colours survive an
#: accessibility level change.
SERIES: Tuple[Tuple[str, str], ...] = (
    ("Under 15", "Orange"),
    ("15 to 64", "Blue"),
    ("65 and over", "Purple"),
)

#: ``{region, lon, lat, values}`` with one share per entry of :data:`SERIES`,
#: as a percentage of the region's population, at a 2023 order of magnitude
#: (UN World Population Prospects). Each row sums to 100 by construction;
#: :func:`build_svg` normalises anyway, because a caller's rows will not.
#: Coordinates are a representative point for the region, not a centroid. A
#: teaching figure, not an official statistical release.
DEMO_DATA: List[Dict[str, Any]] = [
    {"region": "Africa", "lon": 20.0, "lat": 3.0, "values": [40.0, 56.0, 4.0]},
    {"region": "South Asia", "lon": 78.0, "lat": 21.0, "values": [27.0, 66.0, 7.0]},
    {"region": "Middle East", "lon": 47.0, "lat": 29.0, "values": [28.0, 66.0, 6.0]},
    {"region": "South America", "lon": -58.0, "lat": -14.0, "values": [22.0, 68.0, 10.0]},
    {"region": "Oceania", "lon": 140.0, "lat": -26.0, "values": [23.0, 64.0, 13.0]},
    {"region": "North America", "lon": -100.0, "lat": 46.0, "values": [18.0, 64.0, 18.0]},
    {"region": "East Asia", "lon": 108.0, "lat": 38.0, "values": [16.0, 69.0, 15.0]},
    {"region": "Europe", "lon": 16.0, "lat": 52.0, "values": [15.0, 64.0, 21.0]},
]


def _wedge(cx: float, cy: float, r: float, start: float, end: float) -> str:
    """The ``d`` attribute of one pie wedge, from `start` to `end` radians.

    Angles are measured clockwise from twelve o'clock, which is where a
    reader expects a pie to begin. A wedge wider than half the circle needs
    the large-arc flag set: leaving it at 0 draws the *minor* arc, so a 69 %
    slice silently renders as its 31 % complement -- the kind of error that
    looks like a plausible chart and states the opposite of the data.
    """
    if end - start >= 2 * math.pi - 1e-9:
        # A single band holding everything: two half-circles, because an arc
        # whose endpoints coincide is degenerate and draws nothing at all.
        return (
            f"M{cx:.1f},{cy - r:.1f}"
            f"A{r:.1f},{r:.1f} 0 1 1 {cx:.1f},{cy + r:.1f}"
            f"A{r:.1f},{r:.1f} 0 1 1 {cx:.1f},{cy - r:.1f}Z"
        )
    x0 = cx + r * math.sin(start)
    y0 = cy - r * math.cos(start)
    x1 = cx + r * math.sin(end)
    y1 = cy - r * math.cos(end)
    large = 1 if (end - start) > math.pi else 0
    return f"M{cx:.1f},{cy:.1f}L{x0:.1f},{y0:.1f}A{r:.1f},{r:.1f} 0 {large} 1 {x1:.1f},{y1:.1f}Z"


def _nudge_into_map(cx: float, cy: float, half_w: float) -> Tuple[float, float]:
    """Shift a pie back inside the map viewport, returning the new centre.

    A region's representative point can sit close enough to an edge that its
    disc, or the name under it, hangs off the canvas. Moving the glyph a few
    pixels is a smaller lie than clipping it: the point was already a
    stand-in for a whole region.
    """
    top = cy - _PIE_R - 4.0
    bottom = cy + _PIE_R + _NAME_PX + 10.0
    if cx - half_w < _MAP_X + 4.0:
        cx = _MAP_X + 4.0 + half_w
    elif cx + half_w > _MAP_X + _MAP_W - 4.0:
        cx = _MAP_X + _MAP_W - 4.0 - half_w
    if top < _MAP_Y + 4.0:
        cy += _MAP_Y + 4.0 - top
    elif bottom > _MAP_Y + _MAP_H - 4.0:
        cy -= bottom - (_MAP_Y + _MAP_H - 4.0)
    return cx, cy


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
) -> str:
    """Assemble the full pie-glyph map SVG document as a string.

    Parameters
    ----------
    data : list of dict, optional
        Rows with ``region``, ``lon``, ``lat`` and a ``values`` list holding
        one share per entry of :data:`SERIES`. Shares are normalised per row,
        so they need not already sum to 100. Defaults to :data:`DEMO_DATA`.
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
    palette = load_palette(accessibility, theme)
    fonts = chrome_stack_for_theme(theme)
    colors = [palette.get(key, "#007AFF") for _, key in SERIES]

    rings = load_land_rings()
    project = fit_to_viewport(rings, _MAP_X, _MAP_Y, _MAP_W, _MAP_H)

    head = title or "Where children outnumber the old, and where that has turned over"
    sub = subtitle or (
        "Share of the population by age band · every disc is the same size, so "
        "only the angles differ"
    )

    parts: List[str] = [svg_open(_WIDTH, _HEIGHT, "pie-title", "pie-desc", font_family=fonts)]
    parts.append(
        f'<title id="pie-title">{xml_escape(head)}</title>'
        f'<desc id="pie-desc">{xml_escape(sub)}. Eight world regions on an '
        f"Equal Earth map, each carrying a three-part pie splitting its "
        f"population into under 15, 15 to 64, and 65 and over.</desc>"
    )
    parts.append(
        "<style>"
        + os_adaptive_style({key: col for (_, key), col in zip(SERIES, colors, strict=True)})
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

    # ---- pies ----
    tips: List[str] = []
    for idx, row in enumerate(rows):
        cx, cy = project(float(row["lon"]), float(row["lat"]))
        name = str(row["region"])
        nw = text_width(name, _NAME_PX)
        cx, cy = _nudge_into_map(cx, cy, max(_PIE_R, nw / 2.0) + 2.0)

        raw = [max(0.0, float(v)) for v in row["values"]]
        total = sum(raw) or 1.0
        shares = [v / total for v in raw]

        parts.append(f'<g id="hit-{idx}" class="hit" tabindex="0">')
        angle = 0.0
        for share, col in zip(shares, colors, strict=True):
            end = angle + share * 2 * math.pi
            parts.append(
                f'<path d="{_wedge(cx, cy, _PIE_R, angle, end)}" fill="{col}" '
                f'stroke="{_BG}" stroke-width="1.2"/>'
            )
            angle = end
        parts.append("</g>")

        ny = cy + _PIE_R + _NAME_PX + 4.0
        parts.append(
            f'<text x="{cx:.1f}" y="{ny:.1f}" text-anchor="middle" '
            f'font-size="{_NAME_PX:.0f}" font-weight="600" fill="{_INK}" '
            f'stroke="{_BG}" stroke-width="3" paint-order="stroke" '
            f'style="pointer-events:none">{xml_escape(name)}</text>'
        )

        tips.append(
            tooltip_bubble(
                cx,
                cy - _PIE_R - 10.0,
                [name]
                + [
                    f"{label}: {share * 100:.0f}%"
                    for (label, _), share in zip(SERIES, shares, strict=True)
                ],
                anchor="middle",
                canvas_w=_WIDTH,
                canvas_h=_HEIGHT,
                ink=_INK,
                secondary=_SUBTLE,
                border=_LAND_EDGE,
                elem_id=f"tip-{idx}",
            )
        )

    parts.extend(tips)

    # ---- legend ----
    lx = _MAP_X + 10.0
    ly = float(_HEIGHT - 116)
    parts.append(
        f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="13" font-weight="700" '
        f'fill="{_INK}">SHARE OF THE POPULATION AGED</text>'
    )
    for i, ((label, _), col) in enumerate(zip(SERIES, colors, strict=True)):
        row_y = ly + 24.0 + i * 25.0
        parts.append(
            f'<rect x="{lx:.1f}" y="{row_y - 12:.1f}" width="14" height="14" fill="{col}" rx="2"/>'
        )
        parts.append(
            f'<text x="{lx + 22:.1f}" y="{row_y:.1f}" font-size="14" '
            f'fill="{_INK}">{xml_escape(label)}</text>'
        )

    # ---- reading aid: the two ends of the contrast, spelled out ----
    rx = lx + 300.0
    parts.append(
        f'<text x="{rx:.1f}" y="{ly:.1f}" font-size="13" font-weight="700" '
        f'fill="{_INK}">THE TWO ENDS</text>'
    )
    for i, line in enumerate(
        (
            "Africa: 40% under 15, 4% over 65 — ten to one",
            "Europe: 15% under 15, 21% over 65 — the other way up",
            "Every disc is the same size; only the angles carry data",
        )
    ):
        parts.append(
            f'<text x="{rx:.1f}" y="{ly + 24.0 + i * 25.0:.1f}" font-size="14" '
            f'fill="{_SUBTLE}">{xml_escape(line)}</text>'
        )

    # ---- footnote ----
    parts.append(
        f'<text x="{_WIDTH - 24:.1f}" y="{_HEIGHT - 38:.1f}" font-size="12.5" '
        f'fill="{_SUBTLE}" text-anchor="end">Equal Earth (equal-area) projection · '
        f"one pie per region, placed at a representative point</text>"
    )
    parts.append(
        f'<text x="{_WIDTH - 24:.1f}" y="{_HEIGHT - 18:.1f}" font-size="12.5" '
        f'fill="{_SUBTLE}" text-anchor="end">2023 order of magnitude, UN World '
        f"Population Prospects · hover a region for its three shares</text>"
    )

    parts.append(fullscreen_control(_WIDTH, _HEIGHT, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_map_pie(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "",
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render the pie-glyph map and write it to ``out``.

    The standard ``make_<kind>`` entry the figure registry dispatches to, so
    ``make-figure map-pie`` and the Studio work like every other figure.

    Parameters
    ----------
    data : list of dict, optional
        Rows with ``region``, ``lon``, ``lat`` and ``values``. Defaults to
        :data:`DEMO_DATA`.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/map-pie.svg``.
    title : str, optional
        Overrides the headline.
    mode, accessibility, theme : str
        Forwarded to :func:`build_svg`.
    """
    svg = build_svg(data, mode=mode, accessibility=accessibility, theme=theme, title=title or None)
    dest = Path(out) if out else svg_example_path(__file__, "map-pie")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """Write the map-pie SVG to the skill's ``svg-examples`` folder."""
    render_cli(__file__, "map-pie", build_svg, description="Render the map-pie SVG.")


if __name__ == "__main__":
    main()
