#!/usr/bin/env python3
"""
make_map-bars — a house-styled bar-glyph map as hand-authored SVG.

A *bar-glyph map* plants a small grouped bar chart at each place, so the
reader compares categories **within** a region by bar height and compares
regions by where the ink sits on the map. It is the glyph to reach for when
each place carries several independent magnitudes: a bubble can show one
number, a pie can show a composition, and neither can show three totals that
are free to move separately.

Height along a common baseline is the strongest comparison the eye can make
— Cleveland & McGill put position along a common scale at the top of their
ranking — which is the whole argument for bars over the pie next door. The
cost is room: a bar group is wider than a circle, so a bar-glyph map holds
fewer places than a bubble map of the same size before the glyphs collide.
Eight world regions is about the ceiling at this canvas width; a map of
sixty countries wants a different chart.

Every group here shares one scale, drawn once in the legend rather than
repeated as eight tiny axes. That is the quiet condition a bar-glyph map
has to meet and often does not: groups scaled individually would let a
0.5 MWh bar in one region stand as tall as a 7 MWh bar in another, which
turns the map into eight unrelated charts that merely share a page.

This example plants one group per world region, bar height ∝ annual
electricity generation per person, in MWh, from **fossil fuel**, **hydro**,
and **wind and solar** (2023 order of magnitude, Ember / IEA). The takeaway
is the one region that breaks the pattern: South America is the only one
generating more from water than from fuel.

Geometry is self-contained: the land silhouette and the equal-area **Equal
Earth** projection come from :mod:`_worldmap`.

Running the module writes the SVG artifact to
``sprezzature-figures/assets/svg-examples/map-bars.svg``.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

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
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

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

#: Bar geometry, in pixels: one bar's width, the gap between bars of a
#: group, and the height the largest value in the data is drawn at.
_BAR_W: float = 9.0
_BAR_GAP: float = 2.0
_MAX_BAR_H: float = 86.0

#: Type sizes. The region name sits under its group; the value labels live
#: in the tooltip, because three numbers printed at every one of eight
#: groups is twenty-four more labels than this map has room for.
_NAME_PX: float = 14.0


# ------------------------------------------------------------------
# Data — electricity generation by region and source
# ------------------------------------------------------------------
#: The three sources every group compares, in drawing order. Keys match the
#: house palette so the colours survive an accessibility level change.
SERIES: Tuple[Tuple[str, str], ...] = (
    ("Fossil fuel", "Blue"),
    ("Hydro", "Green"),
    ("Wind and solar", "Orange"),
)

#: ``{region, lon, lat, values}`` with one value per entry of :data:`SERIES`,
#: in MWh of annual electricity generation **per person**, at a 2023 order of
#: magnitude (Ember / IEA). Coordinates are a representative point for the
#: region, not a centroid. A teaching figure, not an official statistical
#: release.
#:
#: Per person rather than in total, for a reason that is about the chart and
#: not about the subject. Absolute generation spans 200 to 6 800 TWh across
#: these eight regions, a ratio of thirty-four to one: on one shared scale
#: East Asia fills the glyph and six of the eight regions collapse into a
#: smear a few pixels tall. Dividing by population cuts the spread to about
#: fifteen to one, every group stays readable, and the quantity answers a
#: better question anyway -- a map of absolute totals is largely a map of
#: where people live, which the reader already knows.
DEMO_DATA: List[Dict[str, Any]] = [
    {"region": "North America", "lon": -100.0, "lat": 46.0, "values": [7.0, 1.7, 1.7]},
    {"region": "Oceania", "lon": 140.0, "lat": -26.0, "values": [4.6, 1.0, 1.6]},
    {"region": "Middle East", "lon": 47.0, "lat": 28.0, "values": [4.5, 0.05, 0.15]},
    {"region": "East Asia", "lon": 108.0, "lat": 38.0, "values": [4.3, 0.95, 0.95]},
    {"region": "Europe", "lon": 16.0, "lat": 52.0, "values": [2.3, 1.1, 1.6]},
    {"region": "South Asia", "lon": 78.0, "lat": 21.0, "values": [0.9, 0.15, 0.12]},
    {"region": "South America", "lon": -58.0, "lat": -14.0, "values": [0.7, 1.7, 0.3]},
    {"region": "Africa", "lon": 20.0, "lat": 3.0, "values": [0.5, 0.15, 0.05]},
]


def _group_width() -> float:
    """Total width of one bar group, in pixels."""
    n = len(SERIES)
    return n * _BAR_W + (n - 1) * _BAR_GAP


def _overlaps(a: Tuple[float, ...], b: Tuple[float, ...]) -> bool:
    """True when two boxes share any area."""
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _nudge_into_map(
    x0: float, y0: float, x1: float, y1: float
) -> Tuple[float, float]:
    """Shift a glyph box back inside the map viewport, returning the offset.

    A region's representative point can sit close enough to an edge that its
    group, which extends upward and to both sides of that point, hangs off
    the canvas. Moving the glyph a few pixels is a smaller lie than clipping
    a bar, since the point was already a stand-in for a whole region.
    """
    dx = dy = 0.0
    if x0 < _MAP_X + 4.0:
        dx = _MAP_X + 4.0 - x0
    elif x1 > _MAP_X + _MAP_W - 4.0:
        dx = _MAP_X + _MAP_W - 4.0 - x1
    if y0 < _MAP_Y + 4.0:
        dy = _MAP_Y + 4.0 - y0
    elif y1 > _MAP_Y + _MAP_H - 4.0:
        dy = _MAP_Y + _MAP_H - 4.0 - y1
    return dx, dy


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
) -> str:
    """Assemble the full bar-glyph map SVG document as a string.

    Parameters
    ----------
    data : list of dict, optional
        Rows with ``region``, ``lon``, ``lat`` and a ``values`` list holding
        one number per entry of :data:`SERIES`. Defaults to
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
    palette = load_palette(accessibility, theme)
    fonts = chrome_stack_for_theme(theme)
    mono = mono_stack_for_theme(theme)
    colors = [palette.get(key, "#007AFF") for _, key in SERIES]

    rings = load_land_rings()
    project = fit_to_viewport(rings, _MAP_X, _MAP_Y, _MAP_W, _MAP_H)

    # One scale for every group. Eight groups scaled individually would be
    # eight charts sharing a page, not one map.
    v_max = max(float(v) for r in rows for v in r["values"]) or 1.0

    def bar_h(value: float) -> float:
        return max(0.0, float(value)) / v_max * _MAX_BAR_H

    head = title or "South America is the only region that runs more on water than on fuel"
    sub = subtitle or (
        "Annual electricity generation per person, megawatt-hours · all eight "
        "groups share one scale"
    )

    parts: List[str] = [
        svg_open(_WIDTH, _HEIGHT, "bars-title", "bars-desc", font_family=fonts)
    ]
    parts.append(
        f'<title id="bars-title">{xml_escape(head)}</title>'
        f'<desc id="bars-desc">{xml_escape(sub)}. Eight world regions on an '
        f"Equal Earth map, each carrying a group of three bars for electricity "
        f"generated from fossil fuel, hydro, and wind and solar.</desc>"
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

    # ---- bar groups ----
    gw = _group_width()
    tips: List[str] = []
    name_boxes: List[Tuple[float, float, float, float]] = []
    for idx, row in enumerate(rows):
        px, py = project(float(row["lon"]), float(row["lat"]))
        values = [float(v) for v in row["values"]]
        tallest = max(bar_h(v) for v in values)
        name = str(row["region"])
        nw = text_width(name, _NAME_PX)
        # The glyph occupies the bars, the baseline, and the name under it.
        gx0, gx1 = px - max(gw, nw) / 2.0, px + max(gw, nw) / 2.0
        gy0, gy1 = py - tallest - 6.0, py + _NAME_PX + 8.0
        dx, dy = _nudge_into_map(gx0, gy0, gx1, gy1)
        px, py = px + dx, py + dy

        base_x = px - gw / 2.0
        parts.append(f'<g id="hit-{idx}" class="hit" tabindex="0">')
        # An invisible catcher so the whole glyph is hoverable, not only the
        # few pixels a short bar actually paints.
        parts.append(
            f'<rect x="{px - max(gw, nw) / 2.0:.1f}" y="{py - tallest - 6:.1f}" '
            f'width="{max(gw, nw):.1f}" height="{tallest + _NAME_PX + 14:.1f}" '
            f'fill="transparent"/>'
        )
        for i, value in enumerate(values):
            h = bar_h(value)
            bx = base_x + i * (_BAR_W + _BAR_GAP)
            parts.append(
                f'<rect x="{bx:.1f}" y="{py - h:.1f}" width="{_BAR_W:.1f}" '
                f'height="{h:.1f}" fill="{colors[i]}" rx="1"/>'
            )
        # A baseline under the group: without it the bars float and the eye
        # has no common scale to read the heights against.
        parts.append(
            f'<line x1="{base_x - 2:.1f}" y1="{py:.1f}" x2="{base_x + gw + 2:.1f}" '
            f'y2="{py:.1f}" stroke="{_INK}" stroke-width="1.1"/>'
        )
        parts.append("</g>")

        ny = py + _NAME_PX + 4.0
        parts.append(
            f'<text x="{px:.1f}" y="{ny:.1f}" text-anchor="middle" '
            f'font-size="{_NAME_PX:.0f}" font-weight="600" fill="{_INK}" '
            f'stroke="{_BG}" stroke-width="3" paint-order="stroke" '
            f'style="pointer-events:none">{xml_escape(name)}</text>'
        )
        name_boxes.append((px - nw / 2.0, ny - _NAME_PX, px + nw / 2.0, ny + 3.0))

        tips.append(
            tooltip_bubble(
                px, py - tallest - 12.0,
                [name] + [
                    f"{label}: {value:.2f} MWh a person"
                    for (label, _), value in zip(SERIES, values, strict=True)
                ],
                anchor="middle", canvas_w=_WIDTH, canvas_h=_HEIGHT,
                ink=_INK, secondary=_SUBTLE, border=_LAND_EDGE,
                elem_id=f"tip-{idx}",
            )
        )

    parts.extend(tips)

    # ---- footer: the height scale and the series key, side by side ----
    # Stacked, they collided: the scale is 86 px tall by construction and the
    # key sat inside that height. Two columns is the layout the content wants.
    sx = _MAP_X + 10.0
    sy = float(_HEIGHT - 30)
    parts.append(
        f'<text x="{sx - 2:.1f}" y="{sy - _MAX_BAR_H - 12:.1f}" font-size="13" '
        f'font-weight="700" fill="{_INK}">BAR HEIGHT</text>'
    )
    for value in (6.0, 3.0, 1.0):
        h = bar_h(value)
        parts.append(
            f'<line x1="{sx:.1f}" y1="{sy - h:.1f}" x2="{sx + 34:.1f}" '
            f'y2="{sy - h:.1f}" stroke="{_LAND_EDGE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{sx + 40:.1f}" y="{sy - h + 4:.1f}" font-size="12.5" '
            f'font-family="{mono}" fill="{_SUBTLE}">{value:.0f} MWh</text>'
        )
    parts.append(
        f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{sx + 34:.1f}" y2="{sy:.1f}" '
        f'stroke="{_INK}" stroke-width="1.1"/>'
    )

    lx = sx + 230.0
    ly = sy - _MAX_BAR_H - 12
    parts.append(
        f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="13" font-weight="700" '
        f'fill="{_INK}">ELECTRICITY GENERATED FROM</text>'
    )
    for i, ((label, _), col) in enumerate(zip(SERIES, colors, strict=True)):
        row_y = ly + 22.0 + i * 24.0
        parts.append(
            f'<rect x="{lx:.1f}" y="{row_y - 11:.1f}" width="13" height="13" '
            f'fill="{col}" rx="2"/>'
        )
        parts.append(
            f'<text x="{lx + 21:.1f}" y="{row_y:.1f}" font-size="14" '
            f'fill="{_INK}">{xml_escape(label)}</text>'
        )

    # ---- footnote ----
    parts.append(
        f'<text x="{_WIDTH - 24:.1f}" y="{_HEIGHT - 38:.1f}" font-size="12.5" '
        f'fill="{_SUBTLE}" text-anchor="end">Equal Earth (equal-area) projection · '
        f'one group per region, placed at a representative point</text>'
    )
    parts.append(
        f'<text x="{_WIDTH - 24:.1f}" y="{_HEIGHT - 18:.1f}" font-size="12.5" '
        f'fill="{_SUBTLE}" text-anchor="end">2023 order of magnitude, Ember / IEA · '
        f'hover a group for its three figures</text>'
    )

    parts.append(fullscreen_control(_WIDTH, _HEIGHT, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_map_bars(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "",
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render the bar-glyph map and write it to ``out``.

    The standard ``make_<kind>`` entry the figure registry dispatches to, so
    ``make-figure map-bars`` and the Studio work like every other figure.

    Parameters
    ----------
    data : list of dict, optional
        Rows with ``region``, ``lon``, ``lat`` and ``values``. Defaults to
        :data:`DEMO_DATA`.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/map-bars.svg``.
    title : str, optional
        Overrides the headline.
    mode, accessibility, theme : str
        Forwarded to :func:`build_svg`.
    """
    svg = build_svg(
        data, mode=mode, accessibility=accessibility, theme=theme, title=title or None
    )
    dest = Path(out) if out else svg_example_path(__file__, "map-bars")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """Write the map-bars SVG to the skill's ``svg-examples`` folder."""
    render_cli(__file__, "map-bars", build_svg, description="Render the map-bars SVG.")


if __name__ == "__main__":
    main()
