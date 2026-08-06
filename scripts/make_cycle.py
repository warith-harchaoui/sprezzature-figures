#!/usr/bin/env python3
"""
make_cycle — a house-styled cyclic-process wheel (rotation / cycle diagram) as a hand-authored SVG.

A cycle wheel answers a question a bar chart cannot: *how does one thing
spend its turn?* Where a pie slices a static whole, a cycle wheel reads
as a **loop** — a ring of coloured arcs whose lengths are each phase's
share of one full turn, wrapped by a directional arrow so the eye follows
the sequence round and round. It is the natural figure for anything that
comes back to where it started: a crop rotation, the seasons, a product
lifecycle, a sprint, the water or carbon cycle, a sleep or menstrual
cycle.

This module rebuilds the form in the sprezzature-* house style around an
agronomy exemplar — the growth calendar of a field of **winter wheat**,
sown in October and harvested the following July. The seven acts of the
crop year (sowing, tillering, stem extension, heading, grain filling,
harvest, and the bare-soil intercrop before the next sowing) each take a
different number of months, so the ring is deliberately *uneven*: the
long cool tillering arc dominates the winter while the frantic
reproductive stages of late spring are thin, fast slivers. The clockwise
arrow makes the whole thing turn; every October the loop closes and
begins again. The form follows the crop-rotation plates in the *Mémo
visuel d'agronomie* (Dunod, 2024); the calendar here is an illustrative
single-crop year, not a transcription of that book's data.

The SVG is built by hand — no matplotlib / seaborn / plotly, and no
Vega, because a directed ring of proportional annular arcs with radial
labels and a flow arrow is not a native Vega-Lite mark and reads far more
cleanly authored directly. It follows the tokens from :mod:`_style`: the
Apple-ish palette (here mapped so each arc's hue also nods at its season
— amber autumn, cool winter, green spring, gold summer, earth-brown bare
soil), Roboto typography, ink ``#1D1D1F`` on a white ground, well-sat
rounded corners, a takeaway title and a one-line subtitle.

The figure is interactive without any JavaScript: hovering or
keyboard-focusing any arc or its label dims the other phases so one act
of the year stands out, and each arc carries a native ``<title>`` tooltip
with its month span and share of the year. The directional arrow flows
as gentle marching ants to signal the loop's sense — motion that is
switched off under ``prefers-reduced-motion`` and simply renders as a
static arrow in a raster export.

Running the module writes the SVG artifact to
``sprezzature-figures/assets/svg-examples/cycle.svg``.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# The house-style palette lives in _style (stdlib-only, safe to import
# without the dataviz tier).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _style import forced_color_patterns, leveled_colors, os_adaptive_style, os_dark_style  # noqa: E402
from _svg import point_on_circle, svg_open, xml_escape  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _interactive import fullscreen_control  # noqa: E402


# ------------------------------------------------------------------
# Geometry + house-style constants
# ------------------------------------------------------------------
#: Canvas size, in user-space pixels. Poster-scale so the wheel reads at a
#: glance and every phase arc is comfortably large with room for radial labels.
_WIDTH: int = 1180
_HEIGHT: int = 900

#: Wheel centre and the donut's inner / outer radii. The ring is thick
#: enough to carry an in-arc month count, with a generous hub for the title.
_CX: float = 560.0
_CY: float = 496.0
_R_OUT: float = 300.0
_R_IN: float = 188.0

#: House-style inks.
_INK: str = "#1D1D1F"      # primary text
_SUBTLE: str = "#6E6E73"   # secondary text
_GRID: str = "#E5E5EA"     # hub ring + guides
_BG: str = "#FFFFFF"       # background
_FOCUS: str = "#0A4DA0"    # focus-ring blue

#: The bearing of the first phase's start: 0 = top (12 o'clock). The year
#: begins at the top and sweeps clockwise, like a clock and like a calendar.
_START_DEG: float = 0.0


def _phases(accessibility: str = "universal") -> List[Dict[str, object]]:
    """Return the ordered phases of the winter-wheat year, with seasonal hues.

    Each phase is one act of the crop year, in the order the loop sweeps
    clockwise from the top. ``months`` is the phase's duration and sets its
    arc length — the ring is proportional to time, so the reader sees at a
    glance that the plant spends most of the year in the slow, cool
    tillering stage and races through its reproductive stages in spring.

    Colours are chosen so each arc's hue also nods at its season — amber
    for the autumn sowing, cool blue/teal through winter, greens in
    spring, harvest gold in summer, and an earth brown for the bare-soil
    intercrop — but identity never rests on colour alone: every arc is
    labelled at the rim, so the wheel reads in greyscale and under colour
    vision deficiency. The hues are still routed through
    :func:`_style.leveled_colors` so the ``accessibility`` request is
    honoured for viewers who ask for a re-levelled palette.

    Parameters
    ----------
    accessibility : str, optional
        Palette accessibility level forwarded to
        :func:`_style.leveled_colors`. Defaults to ``"universal"``.

    Returns
    -------
    list of dict
        One dict per phase with ``key`` (stable slug), ``label`` (human
        name), ``sub`` (the month span), ``months`` (float duration →
        arc length) and ``color`` (hex), in cycle order.
    """
    # Season-evocative hues from the curated palette. Amber autumn, cool
    # winter, green spring, gold summer, earth-brown fallow.
    base = {
        "semis": "#FF9500",       # Orange  — autumn sowing
        "tallage": "#5AC8FA",     # Teal    — the long cold winter
        "montaison": "#34C759",   # Green   — spring flush of growth
        "epiaison": "#00C7BE",    # Mint    — heading & flowering
        "remplissage": "#FFCC00", # Yellow  — grain ripening to gold
        "moisson": "#FF3B30",     # Red     — the harvest fortnight
        "interculture": "#A2845E",# Brown   — bare soil / cover crop
    }
    colors = leveled_colors(base, accessibility)
    return [
        {"key": "semis", "label": "Sowing", "sub": "October", "months": 1.0,
         "color": colors["semis"]},
        {"key": "tallage", "label": "Tillering", "sub": "Nov–Feb", "months": 4.0,
         "color": colors["tallage"]},
        {"key": "montaison", "label": "Stem extension", "sub": "Mar–Apr", "months": 2.0,
         "color": colors["montaison"]},
        {"key": "epiaison", "label": "Heading & flowering", "sub": "May", "months": 1.0,
         "color": colors["epiaison"]},
        {"key": "remplissage", "label": "Grain filling", "sub": "June", "months": 1.0,
         "color": colors["remplissage"]},
        {"key": "moisson", "label": "Harvest", "sub": "July", "months": 1.0,
         "color": colors["moisson"]},
        {"key": "interculture", "label": "Bare soil & cover crop", "sub": "Aug–Sep",
         "months": 2.0, "color": colors["interculture"]},
    ]


def _polar(cx: float, cy: float, r: float, angle_deg: float) -> Tuple[float, float]:
    """Convert a clock bearing + radius to an SVG (x, y) point.

    Parameters
    ----------
    cx, cy : float
        Wheel centre in user space.
    r : float
        Radius from the centre.
    angle_deg : float
        Bearing in degrees, 0 = top (12 o'clock), increasing clockwise
        (90 = 3 o'clock). SVG y grows downward, so the top maps to ``-y``
        and the sweep matches a clock face — the natural reading order for
        a calendar year.

    Returns
    -------
    tuple of float
        The ``(x, y)`` point on the SVG canvas.
    """
    theta = math.radians(angle_deg - 90.0)
    return point_on_circle(cx, cy, r, theta)


def _annular_sector(
    cx: float, cy: float, r0: float, r1: float, a0: float, a1: float
) -> str:
    """Build an SVG path for a filled annular sector (one phase's arc band).

    Parameters
    ----------
    cx, cy : float
        Wheel centre.
    r0, r1 : float
        Inner and outer radius of the band (``r0`` < ``r1``).
    a0, a1 : float
        Start and end bearing in degrees (``a0`` < ``a1``).

    Returns
    -------
    str
        The ``d`` attribute of a closed SVG ``<path>``.
    """
    x00, y00 = _polar(cx, cy, r0, a0)
    x01, y01 = _polar(cx, cy, r0, a1)
    x10, y10 = _polar(cx, cy, r1, a0)
    x11, y11 = _polar(cx, cy, r1, a1)
    # Set the large-arc flag honestly so a phase wider than a semicircle
    # still draws (a two-phase cycle would need it).
    large = 1 if (a1 - a0) > 180.0 else 0
    # Outer arc sweeps clockwise (sweep-flag 1), inner arc back (0).
    return (
        f"M {x10:.2f} {y10:.2f} "
        f"A {r1:.2f} {r1:.2f} 0 {large} 1 {x11:.2f} {y11:.2f} "
        f"L {x01:.2f} {y01:.2f} "
        f"A {r0:.2f} {r0:.2f} 0 {large} 0 {x00:.2f} {y00:.2f} "
        f"Z"
    )


def _arc_path(cx: float, cy: float, r: float, a0: float, a1: float) -> str:
    """Return an open ``<path>`` ``d`` tracing a clockwise arc at radius ``r``.

    Used for the directional flow arrow that curves through the donut hole.

    Parameters
    ----------
    cx, cy : float
        Circle centre.
    r : float
        Arc radius.
    a0, a1 : float
        Start and end bearing in degrees (clockwise, ``a1`` > ``a0``).

    Returns
    -------
    str
        The ``d`` attribute of an open SVG ``<path>`` (no ``Z``).
    """
    x0, y0 = _polar(cx, cy, r, a0)
    x1, y1 = _polar(cx, cy, r, a1)
    large = 1 if (a1 - a0) > 180.0 else 0
    return f"M {x0:.2f} {y0:.2f} A {r:.2f} {r:.2f} 0 {large} 1 {x1:.2f} {y1:.2f}"


# Local alias for the shared escape helper; call sites keep the _xml name.
_xml = xml_escape

#: Row-record view of :func:`_phases`' default (``accessibility="universal"``)
#: order, the shape the ``make_<kind>`` contract asks for: one dict per
#: growth stage with its label, month span and duration. This is the same
#: story :func:`build_svg` renders by default; the colour is left out since
#: it is re-derived per accessibility level inside ``build_svg``.
DEMO_DATA: List[Dict[str, Any]] = [
    {"key": p["key"], "label": p["label"], "sub": p["sub"], "months": p["months"]}
    for p in _phases()
]


def build_svg(mode: str = "self-contained", accessibility: str = "universal") -> str:
    """Assemble the full cycle-wheel SVG document as a string.

    Parameters
    ----------
    mode : str, optional
        Interactivity mode passed to :func:`_interactive.fullscreen_control`
        (``"self-contained"`` / ``"external"`` / ``"static"``). Defaults to
        ``"self-contained"``.
    accessibility : str, optional
        Palette accessibility level passed through to :func:`_phases`
        (``"universal"`` default, plus ``"high-contrast"``, ``"monochrome"``,
        ``"deuteranopia"``, ``"protanopia"`` and ``"tritanopia"``). Wired
        through the ``--accessibility`` CLI flag by :func:`_render.render_cli`.

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    phases = _phases(accessibility)
    total = sum(float(p["months"]) for p in phases)
    r_mid = (_R_IN + _R_OUT) / 2.0
    pad_deg = 1.2  # hairline gap so arcs read as distinct acts

    # The longest phase, flagged so the eye lands on the story: the crop
    # spends most of the year in the slow winter tillering stage.
    peak_idx = max(range(len(phases)), key=lambda i: float(phases[i]["months"]))

    # Precompute each phase's angular span [start, end], clockwise from the top.
    spans: List[Tuple[float, float]] = []
    cursor = _START_DEG
    for p in phases:
        sweep = 360.0 * float(p["months"]) / total
        spans.append((cursor, cursor + sweep))
        cursor += sweep

    parts: List[str] = []

    # ---- header + accessibility ----
    parts.append(svg_open(_WIDTH, _HEIGHT, "cycle-title", "cycle-desc"))
    parts.append(
        '<title id="cycle-title">The winter-wheat year: one field spends most '
        'of its turn in the slow winter tillering stage</title>'
    )
    peak = phases[peak_idx]
    desc = (
        "Cycle wheel of the winter-wheat crop year. A ring of coloured arcs, "
        "one per growth stage, sweeps clockwise from the top; each arc's length "
        "is that stage's share of the twelve-month year, and a curved arrow "
        "inside the ring shows the loop's direction. The stages, in order, are "
        + ", ".join(
            f"{_xml(str(p['label']))} ({_xml(str(p['sub']))})" for p in phases
        )
        + f". The longest is {_xml(str(peak['label']))}, {float(peak['months']):.0f} "
        "months over winter; the reproductive stages of late spring are the "
        "thinnest, fastest arcs."
    )
    parts.append(f'<desc id="cycle-desc">{desc}</desc>')

    # ---- interactivity + house style (pure CSS, no JS) ----
    keys = [str(p["key"]) for p in phases]
    style_rows = [
        ".arc, .phase-label { transition: opacity .18s ease; }",
        # Hover/focus anywhere dims every phase; the per-phase rules below then
        # restore the one being pointed at (its arc AND its rim label together).
        "svg:hover .phase, svg:focus-within .phase { opacity: .18; }",
    ]
    for k in keys:
        style_rows.append(
            f"svg:has(.phase-{k}:hover) .phase-{k}, "
            f"svg:has(.phase-{k}:focus) .phase-{k} {{ opacity: 1; }}"
        )
    style_rows.extend([
        ".arc { cursor: pointer; }",
        ".arc:focus { outline: none; }",
        f".arc:focus {{ stroke: {_FOCUS}; stroke-width: 3; }}",
        f".label-hit:focus {{ outline: 3px solid {_FOCUS}; outline-offset: 2px; }}",
        # Marching-ants flow on the directional arrow, ON only when the reader
        # has not asked for reduced motion. A raster export freezes frame 0.
        "@media (prefers-reduced-motion: no-preference) {"
        " .flow { animation: cycle-flow 2.4s linear infinite; } }",
        "@keyframes cycle-flow { to { stroke-dashoffset: -28; } }",
    ])
    # OS-adaptive overrides (additive; every rule lives in an @media block, so
    # the default render is byte-for-byte unchanged). Under prefers-contrast the
    # arc fills deepen together to their high-contrast spacing (role="fill" only,
    # so each arc's white keyline is untouched). Under forced-colors (Windows
    # High Contrast) the ~4-colour system palette cannot hold seven hues, so each
    # phase is handed a distinct Canvas/CanvasText PATTERN (hatch / dots) — the
    # arc and its rim swatch take that pattern, so the acts stay separable with
    # no colour at all, reinforced by the always-present rim labels.
    phase_series = {f".phase-{p['key']}": str(p["color"]) for p in phases}
    style_rows.append(os_adaptive_style(phase_series, role="fill"))
    fcp_defs, fcp_style = forced_color_patterns(
        [f".arc.phase-{p['key']}" for p in phases], prefix="cycle-fcp"
    )
    style_rows.append(fcp_style)
    # Dark mode: invert paper + inks, dim the light hub ring / guides (#E5E5EA).
    # Arc white keylines are left untouched by os_dark_style.
    style_rows.append(os_dark_style(extra='[stroke="#E5E5EA"]{stroke:#2C2C2E;}'))
    parts.append("<style>\n" + "\n".join(style_rows) + "\n</style>")
    parts.append(f"<defs>{fcp_defs}</defs>")

    # ---- background ----
    parts.append(f'<rect width="{_WIDTH}" height="{_HEIGHT}" fill="{_BG}"/>')

    # ---- title + subtitle ----
    parts.append(
        f'<text x="56" y="66" font-size="33" font-weight="700" '
        f'fill="{_INK}">A field is never idle: the winter-wheat year</text>'
    )
    parts.append(
        f'<text x="56" y="100" font-size="18" fill="{_SUBTLE}">'
        f'Share of the crop year each growth stage occupies &#183; sown in '
        f'October, harvested the next July</text>'
    )

    # ---- phase arcs (the ring) ----
    parts.append('<g>')
    for i, p in enumerate(phases):
        k = str(p["key"])
        color = str(p["color"])
        a0, a1 = spans[i]
        start = a0 + pad_deg / 2.0
        end = a1 - pad_deg / 2.0
        path = _annular_sector(_CX, _CY, _R_IN, _R_OUT, start, end)
        share = 100.0 * float(p["months"]) / total
        months = float(p["months"])
        month_word = "month" if months == 1 else "months"
        tip = (
            f'{_xml(str(p["label"]))} &#183; {_xml(str(p["sub"]))} &#183; '
            f'{months:.0f} {month_word} ({share:.0f}% of the year)'
        )
        parts.append(
            f'<g class="phase phase-{k}">'
            f'<path class="arc phase-{k}" tabindex="0" role="listitem" '
            f'd="{path}" fill="{color}" stroke="{_BG}" stroke-width="2" '
            f'stroke-linejoin="round"><title>{tip}</title></path>'
        )
        # In-arc month count, centred on the band. Shown on every phase,
        # including the one-month arcs: the count is the figure's whole point,
        # so a narrow arc gets a slightly smaller glyph rather than none.
        mid = (a0 + a1) / 2.0
        mx, my = _polar(_CX, _CY, r_mid, mid)
        count_size = 21 if months >= 1.5 else 17
        parts.append(
            f'<text x="{mx:.1f}" y="{my:.1f}" font-size="{count_size}" '
            f'font-weight="700" font-family="Roboto Mono, monospace" '
            f'fill="#FFFFFF" text-anchor="middle" dominant-baseline="central" '
            f'style="pointer-events:none">{months:.0f}</text>'
        )
        parts.append('</g>')
    parts.append('</g>')

    # ---- rim labels: phase name + month span, radially outside each arc ----
    for i, p in enumerate(phases):
        k = str(p["key"])
        a0, a1 = spans[i]
        mid = (a0 + a1) / 2.0
        # A short radial leader tick from the rim outward, then the two-line
        # label anchored by side so it never crowds the circle.
        tx0, ty0 = _polar(_CX, _CY, _R_OUT + 6.0, mid)
        tx1, ty1 = _polar(_CX, _CY, _R_OUT + 22.0, mid)
        lx, ly = _polar(_CX, _CY, _R_OUT + 34.0, mid)
        dx = lx - _CX
        if dx > 6.0:
            anchor, ha = "start", 1.0
        elif dx < -6.0:
            anchor, ha = "end", -1.0
        else:
            anchor, ha = "middle", 0.0
        is_peak = i == peak_idx
        name_fill = _INK
        name_weight = 700 if is_peak else 600
        # A generous label hit-box (invisible) makes the whole label focusable
        # and hoverable to isolate its phase, keyboard included.
        parts.append(
            f'<g class="phase phase-{k}">'
            f'<line x1="{tx0:.1f}" y1="{ty0:.1f}" x2="{tx1:.1f}" y2="{ty1:.1f}" '
            f'stroke="{_GRID}" stroke-width="1.6"/>'
            f'<g class="phase-label label-hit" tabindex="0" role="listitem" '
            f'aria-label="{_xml(str(p["label"]))}, {_xml(str(p["sub"]))}">'
            f'<text x="{lx:.1f}" y="{ly - 8:.1f}" font-size="18.5" '
            f'font-weight="{name_weight}" fill="{name_fill}" '
            f'text-anchor="{anchor}" dominant-baseline="middle">'
            f'{_xml(str(p["label"]))}</text>'
            f'<text x="{lx:.1f}" y="{ly + 13:.1f}" font-size="14.5" '
            f'font-family="Roboto Mono, monospace" fill="{_SUBTLE}" '
            f'text-anchor="{anchor}" dominant-baseline="middle">'
            f'{_xml(str(p["sub"]))}</text>'
            f'</g></g>'
        )
        _ = ha  # side computed for anchor; retained for future dx nudging

    # ---- directional flow arrow through the hole (the loop's sense) ----
    # An almost-complete clockwise arc just inside the ring, dashed so it
    # flows as marching ants, capped with an arrowhead near the top so the
    # eye sees the year close and begin again.
    r_flow = _R_IN - 26.0
    flow_path = _arc_path(_CX, _CY, r_flow, _START_DEG + 20.0, _START_DEG + 320.0)
    parts.append(
        f'<path class="flow" d="{flow_path}" fill="none" stroke="{_SUBTLE}" '
        f'stroke-width="3" stroke-linecap="round" stroke-dasharray="2 12" '
        f'opacity="0.55"/>'
    )
    # Arrowhead at the arc's end, tangent to the circle (pointing clockwise).
    ahx, ahy = _polar(_CX, _CY, r_flow, _START_DEG + 320.0)
    tan = math.radians((_START_DEG + 320.0) - 90.0) + math.pi / 2.0  # clockwise tangent
    hx, hy = math.cos(tan), math.sin(tan)
    px, py = -hy, hx  # perpendicular
    s = 11.0
    p1 = (ahx + hx * s, ahy + hy * s)
    p2 = (ahx - hx * 4 + px * s * 0.7, ahy - hy * 4 + py * s * 0.7)
    p3 = (ahx - hx * 4 - px * s * 0.7, ahy - hy * 4 - py * s * 0.7)
    parts.append(
        f'<path d="M {p1[0]:.1f} {p1[1]:.1f} L {p2[0]:.1f} {p2[1]:.1f} '
        f'L {p3[0]:.1f} {p3[1]:.1f} Z" fill="{_SUBTLE}" opacity="0.7"/>'
    )

    # ---- hub: the crop + the loop, at the centre ----
    parts.append(
        f'<circle cx="{_CX}" cy="{_CY}" r="{_R_IN - 46:.1f}" fill="none" '
        f'stroke="{_GRID}" stroke-width="1.4"/>'
    )
    parts.append(
        f'<text x="{_CX}" y="{_CY - 16:.1f}" font-size="17" '
        f'font-family="Roboto Mono, monospace" fill="{_SUBTLE}" '
        f'text-anchor="middle" letter-spacing="2">ONE FIELD</text>'
    )
    parts.append(
        f'<text x="{_CX}" y="{_CY + 14:.1f}" font-size="30" font-weight="700" '
        f'fill="{_INK}" text-anchor="middle">Winter wheat</text>'
    )
    parts.append(
        f'<text x="{_CX}" y="{_CY + 42:.1f}" font-size="16" fill="{_SUBTLE}" '
        f'text-anchor="middle">12 months, one turn</text>'
    )

    # ---- reading annotation on the longest phase ----
    # Anchor the leader on the LOWER part of the peak arc (not its mid, which
    # already carries the in-arc month count) and run it to a note tucked in
    # the lower-right, so the line stays short and never crosses the wheel.
    peak_a0, peak_a1 = spans[peak_idx]
    anchor_deg = peak_a0 + 0.72 * (peak_a1 - peak_a0)
    ppx, ppy = _polar(_CX, _CY, _R_OUT - 20.0, anchor_deg)
    nx, ny = 706.0, 790.0
    parts.append(
        f'<line x1="{ppx:.1f}" y1="{ppy:.1f}" x2="{nx + 8:.1f}" '
        f'y2="{ny - 30:.1f}" stroke="{_INK}" stroke-width="1.4" '
        f'stroke-opacity="0.45"/>'
    )
    parts.append(f'<circle cx="{ppx:.1f}" cy="{ppy:.1f}" r="4" fill="{_INK}"/>')
    share_peak = 100.0 * float(peak["months"]) / total
    parts.append(
        f'<text x="{nx:.1f}" y="{ny:.1f}" font-size="18" font-weight="700" '
        f'fill="{_INK}">Winter does most of the waiting</text>'
    )
    parts.append(
        f'<text x="{nx:.1f}" y="{ny + 23:.1f}" font-size="15" '
        f'fill="{_SUBTLE}">Tillering alone fills {float(peak["months"]):.0f} of the 12 months,</text>'
    )
    parts.append(
        f'<text x="{nx:.1f}" y="{ny + 42:.1f}" font-size="15" '
        f'fill="{_SUBTLE}">{share_peak:.0f}% of the year, before spring races in.</text>'
    )

    # ---- how-to-read note, top-right ----
    note_x = 852.0
    note_y = 150.0
    # Wrapped by hand: no line may end on a dangling function word ("of the",
    # "of", "the", ...) -- a hard house rule, EN and FR alike.
    read_lines = [
        "How to read it",
        "The ring is one full year; follow it",
        "clockwise from the top. Each arc’s",
        "length is its share of the whole year.",
    ]
    parts.append(
        f'<text x="{note_x:.0f}" y="{note_y:.0f}" font-size="16" '
        f'font-weight="700" fill="{_INK}">{read_lines[0]}</text>'
    )
    for j, line in enumerate(read_lines[1:], start=1):
        parts.append(
            f'<text x="{note_x:.0f}" y="{note_y + 8 + j * 22:.0f}" '
            f'font-size="15" fill="{_SUBTLE}">{line}</text>'
        )

    parts.append(fullscreen_control(_WIDTH, _HEIGHT, mode))
    parts.append('</svg>')
    return "\n".join(parts)


def make_cycle(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "",
    mode: str = "self-contained",
    accessibility: str = "universal",
) -> Path:
    """Render the winter-wheat cycle-wheel SVG and write it to ``out``.

    The standard ``make_<kind>`` entry the figure registry dispatches to.
    The seven growth-stage phases, their month spans and the whole
    narrative annotation are baked into :func:`build_svg`, matching
    :data:`DEMO_DATA`; ``data`` is accepted for dispatcher parity but not
    threaded into the drawn ring, since the figure's prose (title,
    "how to read it", the peak-phase callout) is written for this specific
    seven-phase story rather than an arbitrary phase list.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Accepted for contract parity; unused (see above). Defaults to
        :data:`DEMO_DATA` conceptually.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/cycle.svg``.
    title : str, optional
        Accepted for dispatcher/CLI parity; unused, since the chart's
        title is fixed prose.
    mode, accessibility : str
        Forwarded to :func:`build_svg`.

    Returns
    -------
    Path
        Absolute path to the written SVG file.
    """
    _ = data, title  # accepted for dispatcher parity; see docstring
    svg = build_svg(mode=mode, accessibility=accessibility)
    dest = Path(out) if out else svg_example_path(__file__, "cycle")
    return write_svg(dest, svg)


def main() -> None:
    """Write the cycle-wheel SVG to the skill's ``svg-examples`` folder."""
    render_cli(__file__, "cycle", build_svg, description="Render the cycle-wheel SVG.")


if __name__ == "__main__":
    main()
