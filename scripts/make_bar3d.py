#!/usr/bin/env python3
"""Generate a publication-quality *3D bar chart* figure as a standalone SVG.

A 3D bar chart raises a solid box at each cell of a two-way categorical
grid, the box height encoding a single quantity ``z = f(row, col)``. It is
the matplotlib ``Axes3D.bar3d`` idiom; R, seaborn, and plotly have no
first-class equivalent in this house style, so a hand-built SVG is the
natural home for it here. It is used *sparingly* — a 3D bar field trades
some readability for the "landscape" gestalt of a rows x cols surface, and
earns its keep only when the reader is meant to feel the overall relief of
the grid (which rows/cols are tall, where the ridge runs) rather than read
exact values off an axis.

This module builds the SVG string **by hand** (no matplotlib / seaborn /
plotly, no Vega): each grid cell is projected with a fixed axonometric
(oblique-isometric) camera, every bar is drawn as three shaded quadrilateral
faces (top, left, right) so the solid reads as a solid, and the whole field
is painted back-to-front (painter's algorithm) so nearer bars correctly
occlude farther ones. Depth is reinforced twice: bar height drives a house
blue->teal fill ramp, and the three faces of each bar carry graded lightness
(top lightest, right mid, left darkest) so every box has an unambiguous 3D
read. A value label rides the top cap of every bar so the exact number is
one glance away — the relief tells the story, the labels close the loop.

The figure is a **static** poster: a 3D bar field is a still landscape, and
its whole point (the ridge, the plain) is legible in one look. Motion would
add nothing a reader cannot already see, so this generator emits no
animation.

The example data is illustrative: quarterly cloud-infrastructure spend across
four engineering teams, the textbook "two categoricals, one measure" table a
3D bar field is made to show — one team's ridge (Data) towers over the grid
while another (Docs) stays a flat plain.

Usage
-----
    python make_bar3d.py                 # writes the house SVG
    python make_bar3d.py --out other.svg

Style rules: numpy docstrings, full typing, dict-as-record over ad-hoc
classes, generous comments.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# _render/_svg/_style/_interactive live in this file's own directory, not on
# the default import path when this module is loaded from elsewhere (e.g.
# `python -m` from the repo root, or another script importing this one) --
# every other scripts/make_*.py generator has this same line.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _svg import fmt_compact, tooltip_bubble  # noqa: E402
from _style import os_dark_style  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

# House-style tokens (mirrors the house-style constants, kept literal so this
# generator needs no import of the dataviz tier at build time).
_INK = "#1D1D1F"        # primary text
_SECONDARY = "#6E6E73"  # subtitle / secondary / axis text
_BG = "#FFFFFF"         # white ground
_MONO = "Roboto Mono, ui-monospace, monospace"

# Height ramp endpoints: short bars read a pale teal, tall bars a deep house
# blue, so height is legible from colour alone as well as from the box height
# — a redundant channel that survives greyscale and colour-vision deficiency.
_LOW = "#B9E4E8"        # pale teal  — shortest bars
_HIGH = "#0A4DA0"       # deep blue  — tallest bars

# Chrome text (title/subtitle/desc/legend) in the two languages Studio can
# ask for (studio/i18n.py detects the language from the imported CSV's
# column names; the CLI/library/API/MCP always call with the "en" default).
# The bar/cell data itself (row, column, value labels) is never translated
# here — it already carries whatever language the caller's data uses.
_STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "title": "The Data team's cloud bill is running away from everyone else",
        "subtitle": "Quarterly infrastructure spend by team (thousands of USD)",
        "desc": (
            "3D bar chart: a 4x4 grid of solid bars, one per team per "
            "quarter, height and blue depth of colour both encoding quarterly "
            "cloud spend. The Data team's bars form a rising ridge along the back "
            "that towers over the flat Docs plain in the foreground."
        ),
        "legend_low": "lower",
        "legend_high": "higher spend (top-cap number = $ thousands)",
    },
    "fr": {
        "title": "La facture cloud de l'équipe Data explose face aux autres équipes",
        "subtitle": "Dépenses trimestrielles d'infrastructure par équipe (milliers de $)",
        "desc": (
            "Graphique à barres 3D : une grille de barres pleines, une par équipe "
            "et par trimestre, la hauteur et la profondeur de bleu codant toutes "
            "deux la dépense cloud trimestrielle. Les barres de l'équipe Data "
            "forment une crête montante qui domine la plaine plate de l'équipe "
            "Docs au premier plan."
        ),
        "legend_low": "plus bas",
        "legend_high": "dépense plus élevée (chiffre en haut = milliers de $)",
    },
}


def _strings(language: str) -> Dict[str, str]:
    """Chrome-text dict for `language`, falling back to English."""
    return _STRINGS.get(language, _STRINGS["en"])


# --------------------------------------------------------------------------- #
#                                                             #
# --------------------------------------------------------------------------- #
def _sample_grid() -> Dict[str, Any]:
    """Return the illustrative rows x cols x heights table for the 3D bars.

    A small, hand-tuned table so the figure tells one clear story: quarterly
    cloud-infrastructure spend (in thousands of US dollars) for four teams
    across four quarters. The **Data** team's spend ramps hard through the
    year (a rising ridge along the back), while **Docs** stays a low, flat
    plain — the kind of relief a 3D bar field communicates at a glance.

    Returns
    -------
    dict
        ``{"rows": [...], "cols": [...], "z": [[...], ...]}`` where ``z`` is
        indexed ``z[row][col]`` and the units are thousands of US dollars.
    """
    rows = ["Data", "Web", "Mobile", "Docs"]      # depth axis (back -> sprezzature)
    cols = ["Q1", "Q2", "Q3", "Q4"]               # width axis (left -> right)
    # z[row][col] — thousands of USD. Data ramps up; Docs stays flat.
    z = [
        [42.0, 58.0, 74.0, 96.0],   # Data  — the towering ridge
        [31.0, 34.0, 40.0, 46.0],   # Web
        [22.0, 28.0, 25.0, 33.0],   # Mobile
        [9.0, 11.0, 10.0, 12.0],    # Docs  — the flat plain
    ]
    return {"rows": rows, "cols": cols, "z": z}


def _grid_to_rows(grid: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten a ``{"rows", "cols", "z"}`` grid into row records.

    Parameters
    ----------
    grid : dict
        A grid as returned by :func:`_sample_grid` (or with the same shape).

    Returns
    -------
    list of dict
        One record per cell: ``{"team": row_name, "quarter": col_name,
        "spend_k": value}``.
    """
    rows, cols, z = grid["rows"], grid["cols"], grid["z"]
    return [
        {"team": r, "quarter": c, "spend_k": float(z[ri][ci])}
        for ri, r in enumerate(rows)
        for ci, c in enumerate(cols)
    ]


def _rows_to_grid(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Reshape row records back into the ``{"rows", "cols", "z"}`` grid shape.

    Parameters
    ----------
    records : list of dict
        Rows shaped ``{"team": ..., "quarter": ..., "spend_k": ...}`` (see
        :data:`DEMO_DATA`); row/column order follows first appearance.

    Returns
    -------
    dict
        ``{"rows": [...], "cols": [...], "z": [[...], ...]}`` — the shape
        :func:`build_svg` works with.
    """
    rows: List[str] = []
    cols: List[str] = []
    values: Dict[Tuple[str, str], float] = {}
    for rec in records:
        team = str(rec["team"])
        quarter = str(rec["quarter"])
        if team not in rows:
            rows.append(team)
        if quarter not in cols:
            cols.append(quarter)
        values[(team, quarter)] = float(rec["spend_k"])
    z = [[values.get((r, c), 0.0) for c in cols] for r in rows]
    return {"rows": rows, "cols": cols, "z": z}


# The make_<kind> contract's row-record view of the sample grid: one row
# per (team, quarter) cell. make_bar3d() reshapes this back into the
# {"rows", "cols", "z"} grid build_svg() works with via _rows_to_grid().
DEMO_DATA: List[Dict[str, Any]] = _grid_to_rows(_sample_grid())


# --------------------------------------------------------------------------- #
# Colour helpers                                                               #
# --------------------------------------------------------------------------- #
def _lerp_hex(a: str, b: str, t: float) -> str:
    """Linearly interpolate two ``#RRGGBB`` colours in sRGB space.

    Parameters
    ----------
    a, b : str
        Endpoint colours as ``#RRGGBB``.
    t : float
        Blend factor in ``[0, 1]`` (0 -> ``a``, 1 -> ``b``).

    Returns
    -------
    str
        The blended colour as ``#RRGGBB``.
    """
    t = max(0.0, min(1.0, t))
    ar, ag, ab = int(a[1:3], 16), int(a[3:5], 16), int(a[5:7], 16)
    br, bg, bb = int(b[1:3], 16), int(b[3:5], 16), int(b[5:7], 16)
    r = round(ar + (br - ar) * t)
    g = round(ag + (bg - ag) * t)
    bl = round(ab + (bb - ab) * t)
    return f"#{r:02X}{g:02X}{bl:02X}"


def _shade(hex_colour: str, factor: float) -> str:
    """Lighten (factor>1) or darken (factor<1) a ``#RRGGBB`` colour.

    Used to give the three visible faces of each bar graded lightness — the
    top face brightest, the right face mid, the left face darkest — which is
    the classic cue that sells a flat quadrilateral trio as a solid box.

    Parameters
    ----------
    hex_colour : str
        Base fill as ``#RRGGBB``.
    factor : float
        Multiplier on each channel; clamped to ``[0, 255]`` per channel.

    Returns
    -------
    str
        The shaded colour as ``#RRGGBB``.
    """
    r = min(255, max(0, round(int(hex_colour[1:3], 16) * factor)))
    g = min(255, max(0, round(int(hex_colour[3:5], 16) * factor)))
    b = min(255, max(0, round(int(hex_colour[5:7], 16) * factor)))
    return f"#{r:02X}{g:02X}{b:02X}"


def _luminance(hex_colour: str) -> float:
    """Return relative luminance (0..1) of a ``#RRGGBB`` colour.

    A quick perceptual-weight luminance used to decide whether a value label
    sitting on a coloured top cap should be ink or white for legibility.

    Parameters
    ----------
    hex_colour : str
        Colour as ``#RRGGBB``.

    Returns
    -------
    float
        Approximate relative luminance in ``[0, 1]``.
    """
    r = int(hex_colour[1:3], 16) / 255.0
    g = int(hex_colour[3:5], 16) / 255.0
    b = int(hex_colour[5:7], 16) / 255.0
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


# --------------------------------------------------------------------------- #
# Axonometric projection                                                       #
# --------------------------------------------------------------------------- #
#: The fixed camera basis. In this oblique-axonometric ("diamond floor") view
#: three model axes map to screen deltas: ``u`` (columns / quarters) fans to
#: the right-and-down, ``v`` (rows / teams) fans to the left-and-down toward
#: the viewer, and ``h`` runs straight up (bar height). With both floor axes
#: heading *down* from a back apex, larger row and larger col are both nearer
#: the camera — exactly the painter-order key used below. Constants are tuned
#: so cells stay separated and the Data ridge reads clearly. Scaled up for a
#: generous, poster-sized field.
_U = (88.0, 37.0)    # per column step: (dx, dy) — right + down (toward viewer)
_V = (-68.0, 28.0)   # per row step:    (dx, dy) — left  + down (toward viewer)
_H = (0.0, -1.0)     # per height unit: straight up (dy negative = up on screen)


def _project(
    col: float,
    row: float,
    height: float,
    *,
    ox: float,
    oy: float,
    h_scale: float,
) -> Tuple[float, float]:
    """Project a model point ``(col, row, height)`` to pixel ``(x, y)``.

    Parameters
    ----------
    col, row : float
        Grid coordinates along the width (columns) and depth (rows) axes.
    height : float
        Vertical model coordinate (0 at the floor).
    ox, oy : float
        Pixel origin — where model ``(0, 0, 0)`` lands.
    h_scale : float
        Pixels of screen height per model height unit.

    Returns
    -------
    tuple of float
        The projected ``(x, y)`` in pixel space.
    """
    x = ox + col * _U[0] + row * _V[0] + height * _H[0] * h_scale
    y = oy + col * _U[1] + row * _V[1] + height * _H[1] * h_scale
    return x, y


# --------------------------------------------------------------------------- #
# SVG assembly helpers                                                         #
# --------------------------------------------------------------------------- #
def _poly(points: List[Tuple[float, float]], fill: str, extra: str = "") -> str:
    """Return one ``<polygon>`` face with a hairline seam for crisp edges."""
    pts = " ".join(f"{fmt_compact(x)},{fmt_compact(y)}" for x, y in points)
    return (
        f'<polygon points="{pts}" fill="{fill}" '
        f'stroke="{fill}" stroke-width="0.5" stroke-linejoin="round"{extra}/>'
    )


def _bar_faces(
    col: int,
    row: int,
    height: float,
    *,
    ox: float,
    oy: float,
    h_scale: float,
    bar_w: float,
    fill: str,
    value: float,
    mono_family: str = _MONO,
) -> str:
    """Draw one bar as three shaded faces (top, left, right) plus a value cap.

    The bar footprint is a ``bar_w x bar_w`` square centred on the integer
    cell ``(col, row)``. Its three viewer-facing faces are painted with graded
    lightness so the box reads as a solid, and the whole bar carries a native
    ``<title>`` for hover tooltips. A value label rides the centre of the top
    cap (ink on pale caps, white on deep caps) so the exact number is
    readable without an axis round-trip.

    Parameters
    ----------
    col, row : int
        Integer grid cell (0-based) along width and depth.
    height : float
        Bar height in model units.
    ox, oy, h_scale : float
        Projection origin and vertical scale (see :func:`_project`).
    bar_w : float
        Footprint side length as a fraction of one cell step (0..1).
    fill : str
        Base fill colour for the bar (the height-ramp colour).
    value : float
        The measured quantity, rendered as ``$Nk`` on the top cap.
    mono_family : str, optional
        Font stack for the value label. Defaults to :data:`_MONO`
        (corporate); pass the academic stack under ``theme="academic"``.

    Returns
    -------
    str
        The ``<g>`` group of three ``<polygon>`` faces plus the cap label.
    """
    half = bar_w / 2.0
    # Footprint corners in model (col, row) space, at floor (h=0).
    c0, c1 = col - half, col + half
    r0, r1 = row - half, row + half

    def p(cc: float, rr: float, hh: float) -> Tuple[float, float]:
        return _project(cc, rr, hh, ox=ox, oy=oy, h_scale=h_scale)

    # Both floor axes head down-toward the viewer, so the near corner of every
    # footprint is (max col, max row). The two walls the camera sees are the
    # +col wall (right, along increasing col at r1) and the +row wall (left,
    # along increasing row at c1). Name the four floor corners by screen role.
    near = p(c1, r1, 0.0)          # nearest floor corner (down-front)
    col_far_floor = p(c0, r1, 0.0)  # up the +col wall, floor
    row_far_floor = p(c1, r0, 0.0)  # up the +row wall, floor
    # Their tops at full height (straight up).
    near_top = p(c1, r1, height)
    col_far_top = p(c0, r1, height)
    row_far_top = p(c1, r0, height)
    back_top = p(c0, r0, height)    # top cap's far corner

    # Face shades: top brightest, right wall mid, left wall darkest (light
    # from upper right). These multipliers give a calm, solid look.
    top_fill = _shade(fill, 1.12)
    right_fill = _shade(fill, 0.92)
    left_fill = _shade(fill, 0.74)

    # Right wall (+col), left wall (+row), then the top cap on top.
    right = _poly([near, col_far_floor, col_far_top, near_top], right_fill)
    left = _poly([near, row_far_floor, row_far_top, near_top], left_fill)
    top = _poly([near_top, col_far_top, back_top, row_far_top], top_fill)

    # Value label at the centroid of the top cap — ink on pale caps, white on
    # deep caps (chosen by cap luminance) so it stays legible on any bar.
    cx = (near_top[0] + col_far_top[0] + back_top[0] + row_far_top[0]) / 4.0
    cy = (near_top[1] + col_far_top[1] + back_top[1] + row_far_top[1]) / 4.0
    label_fill = _INK if _luminance(top_fill) > 0.5 else "#FFFFFF"
    cap_label = (
        f'<text x="{fmt_compact(cx)}" y="{fmt_compact(cy + 4)}" font-size="14" '
        f'font-family="{mono_family}" font-weight="600" fill="{label_fill}" '
        f'text-anchor="middle">{value:.0f}</text>'
    )

    faces = right + left + top
    # The caller splices an accessible <title> tooltip in as the first child
    # of this <g>, so the group opens plain here.
    return f"<g>{faces}{cap_label}</g>"


# --------------------------------------------------------------------------- #
# Full document                                                                #
# --------------------------------------------------------------------------- #
def build_svg(
    grid: Optional[Dict[str, Any]] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    language: str = "en",
    theme: str = "corporate",
) -> str:
    """Assemble the full 3D-bar SVG document as a string.

    Parameters
    ----------
    grid : dict or None
        The table from :func:`_sample_grid` — ``rows``, ``cols``, ``z``.
        Defaults to :data:`DEMO_DATA`, reshaped via :func:`_rows_to_grid`.
    language : str, optional
        Chrome-text language, ``"en"`` or ``"fr"`` (see :data:`_STRINGS`).
        Only the title/subtitle/desc/legend switch; row, column and value
        labels always render as given in `grid`. Defaults to ``"en"``.
    mode : str, optional
        Interactivity mode passed to :func:`_interactive.fullscreen_control`
        (``"self-contained"``, ``"external"`` or ``"static"``). Controls
        whether the emitted SVG carries its own fullscreen button; the raster
        output is unaffected. Defaults to ``"self-contained"``.
    accessibility : str, optional
        Accessibility level (``"universal"``, ``"high-contrast"``,
        ``"monochrome"``, ``"deuteranopia"``, ``"protanopia"`` or
        ``"tritanopia"``). **No-op by design:** bar height is encoded by a
        single-hue *sequential* teal→blue value ramp (``_LOW``→``_HIGH``), a
        perceptual map that is already colour-vision- and greyscale-safe because
        it leans on lightness, not on a red/green contrast — and each bar's
        three faces carry graded lightness (``_shade``) tuned to that base fill.
        Re-anchoring the ramp through the categorical accessibility engine
        compresses the sweep and de-tunes those face shades, so the level is
        deliberately *not* applied. The flag is accepted for a uniform command
        line. Defaults to ``"universal"``.
    theme : str, optional
        Visual theme: ``"corporate"`` (default, Roboto -- byte-identical to
        the pre-theme render) or ``"academic"`` (LaTeX-style Latin Modern).
        See :func:`sprezzature_figures.fonts.chrome_stack_for_theme`.

    Returns
    -------
    str
        A complete, self-contained SVG document. The figure is static: a 3D
        bar field is a still landscape whose whole message (the ridge, the
        plain) reads in one look, so no animation is emitted.
    """
    # ``accessibility`` is accepted for a uniform CLI but intentionally unused:
    # the teal→blue sequential height ramp (and its per-face shading) is already
    # CVD/greyscale-safe (see the parameter note above), so levelling it would
    # only de-tune it.
    _ = accessibility
    chrome_family = chrome_stack_for_theme(theme)
    mono_family = mono_stack_for_theme(theme)
    grid = grid if grid is not None else _rows_to_grid(DEMO_DATA)
    strings = _strings(language)
    rows: List[str] = list(grid["rows"])
    cols: List[str] = list(grid["cols"])
    z: List[List[float]] = grid["z"]
    n_rows, n_cols = len(rows), len(cols)

    z_max = max(max(r) for r in z)

    # ---- canvas geometry -------------------------------------------------- #
    # Generous, poster-sized canvas. The diamond floor is centred
    # horizontally and seated low enough to leave headroom for the tallest
    # bar plus its value cap.
    width, height = 1040, 800
    ox = 500.0 - (_U[0] * (n_cols - 1) + _V[0] * (n_rows - 1)) / 2.0
    # Seated lower than the legend/subtitle block so the tallest possible bar
    # (worst case: the max value lands on the back-most cell, whose top edge
    # reaches straight up to oy - target) always clears it with visible air,
    # instead of grazing the legend baseline as it did at oy=452.
    oy = 520.0
    # Tallest bar always lands at ~260px regardless of the data's own units
    # (thousands of dollars in the demo grid, raw dollars or any other scale
    # in imported data) — a fixed h_scale sized for z_max~96 blew up to
    # ~140,000px tall on data in the tens of thousands.
    _TARGET_TALLEST_BAR_PX = 260.0
    h_scale = _TARGET_TALLEST_BAR_PX / z_max if z_max else 3.15

    parts: List[str] = []

    # ---- header ----------------------------------------------------------- #
    title = strings["title"]
    subtitle = strings["subtitle"]
    parts.append(
        f'<svg role="img" aria-label="{title}" '
        f'xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="{chrome_family}">'
    )
    # prefers-contrast (additive; the default render is byte-for-byte unchanged
    # because every rule lives inside a media query). This is a PERCEPTUAL figure:
    # bar height is encoded by the teal->blue value ramp, which stays untouched.
    # We only STRENGTHEN STRUCTURE — deepen the secondary/axis ink toward the
    # primary ink and darken + thicken the floor lattice — so the ground plane
    # and labels read harder for a low-vision reader without re-tuning the ramp.
    contrast = (
        "@media (prefers-contrast: more){"
        f'[fill="{_SECONDARY}"]{{fill:{_INK};}}'
        '[stroke="#D2D2D7"]{stroke:#8A8A8E;stroke-width:2;}'
        "}"
    )
    # Additive dark-mode block. The bar-top value labels are white
    # (``fill="#FFFFFF"``) sitting on bright bar faces, so a blanket paper
    # inversion would darken them into the bar; invert the paper via its own
    # ``.paper`` class instead and leave ``#FFFFFF`` labels alone. The floor
    # lattice is a light grey stroke the ink map cannot see, so darken it here.
    parts.append(
        "<style>"
        + contrast
        + os_dark_style(
            ink_map={"#1D1D1F": "#F2F2F7", "#6E6E73": "#9C9CA3"},
            extra=".paper{fill:#0B0B0C;}[stroke=\"#D2D2D7\"]{stroke:#3A3A3C;}",
        )
        + ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + ".hit:hover~.tip,.hit:focus~.tip{opacity:1}"
        + "@media (prefers-reduced-motion:reduce){.tip{transition:none}}"
        + "</style>"
    )
    parts.append(f"<title>{title}</title><desc>{strings['desc']}</desc>")
    parts.append(f'<rect class="paper" width="{width}" height="{height}" rx="14" fill="{_BG}"/>')
    parts.append(
        f'<text x="52" y="60" font-size="30" font-weight="700" '
        f'fill="{_INK}">{title}</text>'
    )
    parts.append(
        f'<text x="52" y="92" font-size="18" '
        f'fill="{_SECONDARY}">{subtitle}</text>'
    )

    # ---- floor grid (a subtle plane the bars stand on) -------------------- #
    # Draw the (n_rows+1) x (n_cols+1) lattice of floor lines so the field has
    # an unambiguous ground plane — a light "this is a grid" cue.
    floor: List[str] = []
    for r in range(n_rows + 1):
        x0, y0 = _project(-0.5, r - 0.5, 0.0, ox=ox, oy=oy, h_scale=h_scale)
        x1, y1 = _project(n_cols - 0.5, r - 0.5, 0.0, ox=ox, oy=oy, h_scale=h_scale)
        floor.append(
            f'<line x1="{fmt_compact(x0)}" y1="{fmt_compact(y0)}" x2="{fmt_compact(x1)}" y2="{fmt_compact(y1)}" '
            f'stroke="#D2D2D7" stroke-width="1.4"/>'
        )
    for c in range(n_cols + 1):
        x0, y0 = _project(c - 0.5, -0.5, 0.0, ox=ox, oy=oy, h_scale=h_scale)
        x1, y1 = _project(c - 0.5, n_rows - 0.5, 0.0, ox=ox, oy=oy, h_scale=h_scale)
        floor.append(
            f'<line x1="{fmt_compact(x0)}" y1="{fmt_compact(y0)}" x2="{fmt_compact(x1)}" y2="{fmt_compact(y1)}" '
            f'stroke="#D2D2D7" stroke-width="1.4"/>'
        )
    parts.append(f'<g class="floor">{"".join(floor)}</g>')

    # ---- the bars, painted back-to-front ---------------------------------- #
    # Painter's algorithm: a bar occludes another when it is nearer the camera.
    # In this basis, larger (row + col) is nearer the viewer, so sort ascending
    # by (row + col) and draw farthest first.
    bar_w = 0.5
    order = sorted(
        ((r, c) for r in range(n_rows) for c in range(n_cols)),
        key=lambda rc: rc[0] + rc[1],
    )
    bars: List[str] = []
    for r, c in order:
        val = z[r][c]
        t = val / z_max if z_max else 0.0
        fill = _lerp_hex(_LOW, _HIGH, t)
        label = f"{rows[r]} · {cols[c]}: ${val:.0f}k"
        group = _bar_faces(
            c, r, val,
            ox=ox, oy=oy, h_scale=h_scale, bar_w=bar_w,
            fill=fill, value=val, mono_family=mono_family,
        )
        # Splice the accessible per-bar tooltip in as the group's first child,
        # and mark the group as the hover/focus hit target.
        group = group.replace("<g>", f'<g class="hit" tabindex="0"><title>{label}</title>', 1)
        bars.append(group)
        cap_x, cap_y = _project(c, r, val, ox=ox, oy=oy, h_scale=h_scale)
        share = (val / z_max * 100.0) if z_max else 0.0
        bars.append(
            tooltip_bubble(
                cap_x, cap_y - 10,
                [f"{rows[r]} · {cols[c]}", f"${val:.0f}k", f"{share:.0f}% of tallest bar"],
                canvas_w=width, canvas_h=height, ink=_INK, secondary=_SECONDARY, border="#D2D2D7",
            )
        )
    parts.append(f'<g class="bars">{"".join(bars)}</g>')

    # ---- axis labels ------------------------------------------------------ #
    # Quarters (columns) label the front-right floor edge (row_max side);
    # teams (rows) label the front-left floor edge (col_max side). Each sits
    # just outside the floor so it never collides with a bar or its neighbour.
    axis: List[str] = []
    # Quarters ride the front-right edge (the +col / _U direction, row_max side).
    for c in range(n_cols):
        lx, ly = _project(c, n_rows - 1 + 0.72, 0.0, ox=ox, oy=oy, h_scale=h_scale)
        axis.append(
            f'<text x="{fmt_compact(lx + 8)}" y="{fmt_compact(ly + 18)}" font-size="17" '
            f'font-family="{mono_family}" fill="{_SECONDARY}" text-anchor="start">{cols[c]}</text>'
        )
    # Teams ride the front-left edge (the +row / _V direction, col_max side).
    for r in range(n_rows):
        lx, ly = _project(n_cols - 1 + 0.72, r, 0.0, ox=ox, oy=oy, h_scale=h_scale)
        axis.append(
            f'<text x="{fmt_compact(lx - 8)}" y="{fmt_compact(ly + 18)}" font-size="17" '
            f'font-family="{mono_family}" fill="{_SECONDARY}" text-anchor="end">{rows[r]}</text>'
        )
    parts.append(f'<g class="axis-labels">{"".join(axis)}</g>')

    # ---- height ramp legend (low -> high spend) --------------------------- #
    # Seated in the clear band under the subtitle so it never collides with
    # the sprezzature row of bars or their floor labels.
    lx, ly = 52, 150
    parts.append(
        f'<text x="{lx}" y="{ly}" font-size="15" font-family="{mono_family}" '
        f'fill="{_SECONDARY}">{strings["legend_low"]}</text>'
    )
    # Gap sized off the actual rendered text instead of a fixed offset tuned
    # for English "lower" -- a longer FR label was overlapping the gradient
    # swatch at a hardcoded lx+62. Roboto Mono is a fixed-width face, so a
    # flat per-character advance (calibrated a touch generous, same spirit
    # as _textfit.text_width) is exact enough at this one font size.
    _MONO_CHAR_EM = 0.62
    swatch_x = lx + len(strings["legend_low"]) * 15 * _MONO_CHAR_EM + 14
    n_swatch = 30
    swatch_w = 5.2
    for k in range(n_swatch):
        tt = k / (n_swatch - 1)
        colour = _lerp_hex(_LOW, _HIGH, tt)
        parts.append(
            f'<rect x="{swatch_x + k * swatch_w:.1f}" y="{ly - 13}" '
            f'width="{swatch_w + 0.3:.1f}" height="13" fill="{colour}"/>'
        )
    parts.append(
        f'<text x="{swatch_x + n_swatch * swatch_w + 12:.1f}" y="{ly}" '
        f'font-size="15" font-family="{mono_family}" '
        f'fill="{_SECONDARY}">{strings["legend_high"]}</text>'
    )

    # Fullscreen control (top-right corner is clear; bottom band holds the
    # legend), emitted per interactivity mode just before the document closes.
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "".join(parts)


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #
def make_bar3d(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "",
    mode: str = "self-contained",
    accessibility: str = "universal",
    language: str = "en",
    theme: str = "corporate",
) -> Path:
    """Render the house-styled 3D-bar chart and write the SVG to *out*.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``team``, ``quarter`` (str) and ``spend_k`` (float),
        one per grid cell (see :data:`DEMO_DATA`). Row/column order follows
        first appearance. Defaults to the illustrative quarterly
        cloud-infrastructure-spend grid.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/bar3d.svg``.
    title : str, optional
        Accepted for CLI/dispatcher parity; this figure's title names the
        tallest ridge and stays fixed regardless of the data supplied.
    mode, accessibility : str
        Forwarded to :func:`build_svg`.
    language : str, optional
        Chrome-text language, ``"en"`` or ``"fr"``. Defaults to ``"en"``;
        Sprezzature Studio passes the language detected from the imported
        CSV's column names (see :data:`_STRINGS`).
    theme : str, optional
        Visual theme. Forwarded to :func:`build_svg`.

    Returns
    -------
    Path
        Absolute path to the written SVG file.

    Examples
    --------
    >>> p = make_bar3d()
    >>> p.exists()
    True
    """
    _ = title
    rows = data if data else DEMO_DATA
    grid = _rows_to_grid(rows)
    svg = build_svg(grid, mode=mode, accessibility=accessibility, language=language, theme=theme)
    dest = Path(out) if out else svg_example_path(__file__, "bar3d")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "bar3d", build_svg, description="Write the house-style 3D-bar-chart SVG example.")


if __name__ == "__main__":
    main()
