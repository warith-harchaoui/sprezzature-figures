#!/usr/bin/env python3
"""
make_map-tilegrid — a house-styled tile-grid cartogram as hand-authored SVG.

A *tile-grid cartogram* replaces every country with an equal square, laid out
so the arrangement still reads as a world map. It throws away shape, area and
exact position, and buys one thing with them: **every country gets the same
visual weight**. On a choropleth, Russia and Canada shout across the page
while Iceland, Denmark and Costa Rica are too small to see at all, so the
reader's impression is a map of territory wearing a map of data.

That trade is only worth making for a **rate**. A share, a percentage, a
per-person figure belongs to a country rather than to its square kilometres,
so equal tiles state it fairly. Put a *total* on a tile grid and the figure
lies twice over: it hides that China's bar is a billion people's worth and
Iceland's is four hundred thousand's, and it offers no size cue to recover
that from. Use a bubble map for totals; this is for rates.

Position is approximate by construction. Tiles are placed on an 11 by 9
grid in roughly the right direction from one another — Nordics up and
right of Britain, Indonesia below the Asian mainland — and a reader who
measures distances off this figure has misunderstood it. The country codes
are therefore part of the chart, not decoration: without them the layout is
unreadable, and they are the reason a tile may never be smaller than the
text it has to hold.

This example shades each tile by the share of that country's **electricity
generated from low-carbon sources** — renewables plus nuclear — as a
percentage (2023 order of magnitude, Ember). The takeaway is who the leaders
actually are: seven countries already generate 90 % or more without carbon,
and on a conventional map most of them are too small or too faint to notice.

Running the module writes the SVG artifact to
``sprezzature-figures/assets/svg-examples/map-tilegrid.svg``.

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
from _style import load_palette, os_dark_style  # noqa: E402
from _svg import foreground_tip_css, svg_open, tooltip_bubble, xml_escape  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

# ------------------------------------------------------------------
# Canvas + house-style constants
# ------------------------------------------------------------------
#: Canvas size, in user-space pixels. Sized to the grid it holds -- 11
#: columns and 9 rows at the pitch below, plus the header band and the
#: legend -- rather than rounded up to something tidy, which left 120 px of
#: white down the right of the first draft.
_WIDTH: int = 940
_HEIGHT: int = 945

#: The grid: 11 columns by 9 rows, one tile each, with the gap between
#: tiles counted inside the pitch.
_COLS: int = 11
_ROWS: int = 9
_TILE: float = 72.0
_GAP: float = 6.0

#: Top-left corner of the grid.
_GRID_X: float = 40.0
_GRID_Y: float = 132.0

#: House-style inks.
_INK: str = "#1D1D1F"
_SUBTLE: str = "#6E6E73"
_BG: str = "#FFFFFF"
_EMPTY: str = "#F4F4F7"


# ------------------------------------------------------------------
# Layout — where each country's tile sits
# ------------------------------------------------------------------
#: ``{code: (column, row)}``, column 0 at the left, row 0 at the top. Laid
#: out so neighbours are in roughly the right direction from one another;
#: no distance on this grid means anything.
LAYOUT: Dict[str, Tuple[int, int]] = {
    "CAN": (0, 0), "ISL": (3, 0), "NOR": (4, 0), "SWE": (5, 0), "RUS": (8, 0),
    "USA": (0, 1), "IRL": (2, 1), "GBR": (3, 1), "NLD": (4, 1), "POL": (5, 1),
    "UKR": (6, 1), "KAZ": (7, 1), "JPN": (10, 1),
    "MEX": (0, 2), "ESP": (2, 2), "FRA": (3, 2), "DEU": (4, 2), "TUR": (6, 2),
    "PAK": (7, 2), "CHN": (8, 2), "KOR": (9, 2),
    "COL": (1, 3), "PRT": (2, 3), "MAR": (3, 3), "ITA": (4, 3), "GRC": (5, 3),
    "IRN": (7, 3),
    "PER": (1, 4), "BRA": (2, 4), "DZA": (4, 4), "EGY": (5, 4), "SAU": (6, 4),
    "IND": (7, 4), "THA": (8, 4), "VNM": (9, 4), "PHL": (10, 4),
    "ARG": (1, 5), "NGA": (3, 5), "ETH": (5, 5), "IDN": (9, 5),
    "CHL": (1, 6), "COD": (4, 6), "KEN": (5, 6),
    "ZAF": (4, 7), "AUS": (9, 7),
    "NZL": (10, 8),
}

#: Full names, for the hover card and the accessible label -- a three-letter
#: code is a handle, not a name, and a screen reader saying "D Z A" has told
#: the listener nothing.
NAMES: Dict[str, str] = {
    "CAN": "Canada", "ISL": "Iceland", "NOR": "Norway", "SWE": "Sweden",
    "RUS": "Russia", "USA": "United States", "IRL": "Ireland",
    "GBR": "United Kingdom", "NLD": "Netherlands", "POL": "Poland",
    "UKR": "Ukraine", "KAZ": "Kazakhstan", "JPN": "Japan", "MEX": "Mexico",
    "ESP": "Spain", "FRA": "France", "DEU": "Germany", "TUR": "Türkiye",
    "PAK": "Pakistan", "CHN": "China", "KOR": "South Korea", "COL": "Colombia",
    "PRT": "Portugal", "MAR": "Morocco", "ITA": "Italy", "GRC": "Greece",
    "IRN": "Iran", "PER": "Peru", "BRA": "Brazil", "DZA": "Algeria",
    "EGY": "Egypt", "SAU": "Saudi Arabia", "IND": "India", "THA": "Thailand",
    "VNM": "Viet Nam", "PHL": "Philippines", "ARG": "Argentina",
    "NGA": "Nigeria", "ETH": "Ethiopia", "IDN": "Indonesia", "CHL": "Chile",
    "COD": "DR Congo", "KEN": "Kenya", "ZAF": "South Africa",
    "AUS": "Australia", "NZL": "New Zealand",
}

#: Class breaks, as percentages. Fixed bands rather than quintiles: quintiles
#: would put a fifth of the countries in each colour whatever the numbers
#: are, so the ramp would look identical on a world that had decarbonised and
#: on one that had not. These bands mean the same thing every year.
BANDS: Tuple[Tuple[float, str], ...] = (
    (20.0, "Under 20%"),
    (40.0, "20 to 40%"),
    (60.0, "40 to 60%"),
    (80.0, "60 to 80%"),
    (100.1, "80% and over"),
)

#: ``{code: percent}``. Share of electricity generated from low-carbon
#: sources -- renewables plus nuclear -- at a 2023 order of magnitude
#: (Ember). A teaching figure, not an official statistical release.
DEMO_DATA: List[Dict[str, Any]] = [
    {"code": c, "percent": v}
    for c, v in (
        ("ISL", 100.0), ("ETH", 100.0), ("NOR", 98.0), ("SWE", 98.0),
        ("COD", 98.0), ("FRA", 92.0), ("KEN", 90.0), ("BRA", 89.0),
        ("CAN", 82.0), ("NZL", 82.0), ("COL", 75.0), ("ESP", 75.0),
        ("PRT", 72.0), ("UKR", 65.0), ("CHL", 62.0), ("GBR", 60.0),
        ("PER", 60.0), ("DEU", 56.0), ("GRC", 50.0), ("VNM", 48.0),
        ("NLD", 45.0), ("PAK", 45.0), ("ITA", 44.0), ("TUR", 42.0),
        ("USA", 41.0), ("IRL", 40.0), ("RUS", 40.0), ("AUS", 39.0),
        ("KOR", 39.0), ("CHN", 36.0), ("ARG", 35.0), ("JPN", 32.0),
        ("POL", 27.0), ("MEX", 24.0), ("IND", 23.0), ("NGA", 22.0),
        ("PHL", 22.0), ("IDN", 20.0), ("MAR", 20.0), ("THA", 15.0),
        ("ZAF", 15.0), ("EGY", 12.0), ("KAZ", 12.0), ("IRN", 7.0),
        ("DZA", 1.0), ("SAU", 1.0),
    )
]


def _band_index(percent: float) -> int:
    """Which class `percent` falls into, as an index into :data:`BANDS`."""
    for i, (upper, _) in enumerate(BANDS):
        if percent < upper:
            return i
    return len(BANDS) - 1


def _ramp(palette: Dict[str, str]) -> List[str]:
    """Five steps of one hue, lightest to darkest.

    Built by mixing the palette's blue toward white rather than by naming
    five hex values, so an accessibility level that changes the blue changes
    the whole ramp with it instead of leaving four hardcoded cousins behind.
    """
    base = palette.get("Blue", "#007AFF").lstrip("#")
    r, g, b = (int(base[i : i + 2], 16) for i in (0, 2, 4))
    out: List[str] = []
    for i in range(len(BANDS)):
        # The lightest step keeps a little colour: a white tile would read as
        # "no data", which is a different statement from "almost none".
        t = 0.80 - 0.80 * (i / (len(BANDS) - 1))
        out.append(
            "#%02X%02X%02X"
            % (
                round(r + (255 - r) * t),
                round(g + (255 - g) * t),
                round(b + (255 - b) * t),
            )
        )
    return out


def _ink_on(fill: str) -> str:
    """Ink or white for a label on `fill`, whichever the eye can read."""
    r, g, b = (int(fill.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))
    return "#FFFFFF" if (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0 < 0.55 else _INK


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
) -> str:
    """Assemble the full tile-grid cartogram SVG document as a string.

    Parameters
    ----------
    data : list of dict, optional
        Rows with ``code`` (a key of :data:`LAYOUT`) and ``percent``.
        Defaults to :data:`DEMO_DATA`.
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
    values = {str(r["code"]): float(r["percent"]) for r in rows}
    palette = load_palette(accessibility, theme)
    fonts = chrome_stack_for_theme(theme)
    mono = mono_stack_for_theme(theme)
    ramp = _ramp(palette)

    head = title or "Seven countries already generate 90% of their power without carbon"
    sub = subtitle or (
        "Share of electricity from low-carbon sources · every country is one "
        "equal tile, so a small country counts as much as a large one"
    )

    parts: List[str] = [
        svg_open(_WIDTH, _HEIGHT, "tile-title", "tile-desc", font_family=fonts)
    ]
    parts.append(
        f'<title id="tile-title">{xml_escape(head)}</title>'
        f'<desc id="tile-desc">{xml_escape(sub)}. Forty-six countries as equal '
        f"squares on an eleven by nine grid arranged in roughly geographic "
        f"order, each shaded by the share of its electricity generated from "
        f"renewables and nuclear.</desc>"
    )
    parts.append(
        "<style>"
        + os_dark_style()
        + ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + "@media (prefers-reduced-motion:reduce){.tip{transition:none}}"
        + foreground_tip_css(len(LAYOUT))
        + "</style>"
    )
    parts.append(f'<rect width="{_WIDTH}" height="{_HEIGHT}" fill="{_BG}"/>')

    # ---- header band ----
    parts.append(
        f'<text x="{_GRID_X:.1f}" y="52" font-size="27" font-weight="700" '
        f'fill="{_INK}">{xml_escape(head)}</text>'
    )
    for i, line in enumerate(
        (
            "Share of electricity from low-carbon sources — renewables plus nuclear.",
            "Every country is one equal tile, so a small country counts as much as a large one.",
        )
    ):
        parts.append(
            f'<text x="{_GRID_X:.1f}" y="{82 + i * 22}" font-size="15" '
            f'fill="{_SUBTLE}">{xml_escape(line)}</text>'
        )

    # ---- tiles ----
    pitch = _TILE + _GAP
    tips: List[str] = []
    for idx, (code, (col, row)) in enumerate(sorted(LAYOUT.items())):
        x = _GRID_X + col * pitch
        y = _GRID_Y + row * pitch
        percent = values.get(code)
        fill = _EMPTY if percent is None else ramp[_band_index(percent)]
        ink = _SUBTLE if percent is None else _ink_on(fill)
        name = NAMES.get(code, code)
        label = (
            f"{name}: no data"
            if percent is None
            else f"{name}: {percent:.0f}% low-carbon electricity"
        )
        parts.append(
            f'<rect id="hit-{idx}" class="hit" tabindex="0" x="{x:.1f}" y="{y:.1f}" '
            f'width="{_TILE:.1f}" height="{_TILE:.1f}" rx="7" fill="{fill}">'
            f'<title>{xml_escape(label)}</title></rect>'
        )
        parts.append(
            f'<text x="{x + _TILE / 2:.1f}" y="{y + _TILE / 2 - 5:.1f}" '
            f'text-anchor="middle" dominant-baseline="central" font-size="17" '
            f'font-weight="700" fill="{ink}" style="pointer-events:none">{code}</text>'
        )
        parts.append(
            f'<text x="{x + _TILE / 2:.1f}" y="{y + _TILE / 2 + 16:.1f}" '
            f'text-anchor="middle" dominant-baseline="central" '
            f'font-family="{mono}" font-size="14" fill="{ink}" opacity="0.88" '
            f'style="pointer-events:none">'
            f'{"—" if percent is None else f"{percent:.0f}%"}</text>'
        )
        tips.append(
            tooltip_bubble(
                x + _TILE / 2, y - 8.0,
                [name, "No data" if percent is None
                 else f"{percent:.0f}% from low-carbon sources"],
                anchor="middle", canvas_w=_WIDTH, canvas_h=_HEIGHT,
                ink=_INK, secondary=_SUBTLE, border="#E5E5EA",
                elem_id=f"tip-{idx}",
            )
        )
    parts.extend(tips)

    # ---- legend ----
    ly = _GRID_Y + _ROWS * pitch + 24.0
    parts.append(
        f'<text x="{_GRID_X:.1f}" y="{ly:.1f}" font-size="13" font-weight="700" '
        f'fill="{_INK}">SHARE OF ELECTRICITY FROM LOW-CARBON SOURCES</text>'
    )
    cursor = _GRID_X
    # `swatch`, not `col`: the tile loop above binds `col` to a grid column,
    # which is an integer, and reusing the name here for a colour put two
    # meanings on one name in one scope. mypy caught it; a reader would not.
    for (_, caption), swatch in zip(BANDS, ramp, strict=True):
        parts.append(
            f'<rect x="{cursor:.1f}" y="{ly + 12:.1f}" width="22" height="14" '
            f'rx="3" fill="{swatch}"/>'
        )
        parts.append(
            f'<text x="{cursor + 28:.1f}" y="{ly + 23:.1f}" font-size="13.5" '
            f'fill="{_INK}">{xml_escape(caption)}</text>'
        )
        cursor += 28 + 9.0 * len(caption) + 22
    parts.append(
        f'<text x="{_GRID_X:.1f}" y="{ly + 52:.1f}" font-size="12.5" '
        f'fill="{_SUBTLE}">Tiles are placed in roughly geographic order; no '
        f'distance on this grid means anything. 2023 order of magnitude, Ember.</text>'
    )

    parts.append(fullscreen_control(_WIDTH, _HEIGHT, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_map_tilegrid(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "",
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render the tile-grid cartogram and write it to ``out``.

    The standard ``make_<kind>`` entry the figure registry dispatches to, so
    ``make-figure map-tilegrid`` and the Studio work like every other figure.

    Parameters
    ----------
    data : list of dict, optional
        Rows with ``code`` and ``percent``. Defaults to :data:`DEMO_DATA`.
    out : Path, str, or None
        Output path (.svg). Defaults to
        ``assets/svg-examples/map-tilegrid.svg``.
    title : str, optional
        Overrides the headline.
    mode, accessibility, theme : str
        Forwarded to :func:`build_svg`.
    """
    svg = build_svg(
        data, mode=mode, accessibility=accessibility, theme=theme, title=title or None
    )
    dest = Path(out) if out else svg_example_path(__file__, "map-tilegrid")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """Write the map-tilegrid SVG to the skill's ``svg-examples`` folder."""
    render_cli(
        __file__, "map-tilegrid", build_svg, description="Render the map-tilegrid SVG."
    )


if __name__ == "__main__":
    main()
