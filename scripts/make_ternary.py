#!/usr/bin/env python3
"""
make_ternary — a house-styled ternary (barycentric) plot as a hand-authored SVG.

A ternary plot places every three-part composition — three fractions
that sum to one — as a single point inside an equilateral triangle.
Each corner is a pure end-member (100 % of one part, 0 % of the other
two); the perpendicular distance from the opposite edge encodes that
part's share. It is the natural chart for compositional data, where the
three numbers are *not independent* (they always sum to 100 %) so a
Cartesian scatter would double-count and mislead.

This module builds the SVG string by hand (no matplotlib / seaborn /
plotly, and no Vega — Vega-Lite has no first-class ternary geometry, so
the barycentric projection is authored directly). It follows the
sprezzature-* house style pulled from :mod:`_style`: the Apple-ish saturated
palette, Roboto typography, ink ``#1D1D1F`` on a white background,
rounded markers, a takeaway title, and a one-line subtitle.

The example is a soil-texture chart — the classic use of a ternary:
each sample is a mix of **sand**, **silt**, and **clay** (the three
mineral grain sizes, which by definition sum to 100 %), grouped by the
soil textbook's texture class. The figure is interactive without any
JavaScript: hovering or keyboard-focusing a legend entry (a texture
class) dims the other classes so one cloud of samples stands out, and
every marker carries a native ``<title>`` tooltip reading back its
exact sand / silt / clay split.

Running the module writes the SVG artifact to
``sprezzature-figures/assets/svg-examples/ternary.svg``.

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
from _style import load_palette, os_adaptive_style, os_dark_style  # noqa: E402
from _svg import svg_open, tooltip_bubble, xml_escape  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _interactive import fullscreen_control  # noqa: E402


# ------------------------------------------------------------------
# Geometry + house-style constants
# ------------------------------------------------------------------
#: Canvas size, in user-space pixels. Poster-scale: a large, generous
#: figure so the triangle, its grid, and the three sample clouds read
#: clearly without squinting.
_WIDTH: int = 1040
_HEIGHT: int = 820

#: Triangle geometry. The three corners of the equilateral triangle in
#: SVG user space. ``_TOP`` is the apex (100 % clay), ``_LEFT`` the
#: bottom-left (100 % sand), ``_RIGHT`` the bottom-right (100 % silt).
_SIDE: float = 620.0                       # edge length in pixels
_APEX_X: float = 495.0                     # horizontal centre of the apex
_APEX_Y: float = 168.0                     # apex y
_BASE_Y: float = _APEX_Y + _SIDE * math.sqrt(3) / 2.0  # bottom edge y
_LEFT_X: float = _APEX_X - _SIDE / 2.0     # bottom-left corner x
_RIGHT_X: float = _APEX_X + _SIDE / 2.0    # bottom-right corner x

#: House-style inks.
_INK: str = "#1D1D1F"       # primary text
_SUBTLE: str = "#6E6E73"    # secondary text
_GRID: str = "#D8D8DD"      # inner grid lines
_EDGE: str = "#1D1D1F"      # triangle outline
_BG: str = "#FFFFFF"        # background
_FOCUS: str = "#0A4DA0"     # focus-ring blue

#: Number of inner grid lines (every 20 %).
_GRID_STEP: int = 5


#: Row records: one per topsoil sample, ``sand``/``silt``/``clay`` the
#: three grain-size percentages (each row sums to 100) and ``class`` the
#: USDA-style texture class it belongs to. Field topsoil samples grouped
#: into three texture classes so the reader sees how each class occupies
#: its own region of the triangle.
DEMO_DATA: List[Dict[str, Any]] = [
    {"class": cls, "sand": s, "silt": si, "clay": c}
    for cls, pts in (
        (
            "Sandy loam",
            [
                (68, 24, 8), (74, 14, 12), (63, 29, 8), (71, 15, 14),
                (60, 26, 14), (77, 17, 6), (66, 20, 14), (58, 34, 8),
                (72, 22, 6), (64, 18, 18),
            ],
        ),
        (
            "Silt loam",
            [
                (22, 66, 12), (16, 68, 16), (28, 58, 14), (19, 63, 18),
                (13, 72, 15), (25, 65, 10), (31, 55, 14), (17, 61, 22),
                (23, 70, 7), (14, 66, 20),
            ],
        ),
        (
            "Clay",
            [
                (20, 22, 58), (14, 24, 62), (26, 16, 58), (12, 20, 68),
                (24, 14, 62), (18, 28, 54), (10, 26, 64), (28, 18, 54),
                (16, 18, 66), (22, 26, 52),
            ],
        ),
    )
    for s, si, c in pts
]

#: Hue cycle for texture classes, in first-seen order (matches the shipped
#: Sandy loam / Silt loam / Clay story: Orange, Blue, Purple).
_CLASS_HUES = ("Orange", "Blue", "Purple", "Green", "Teal", "Red")


def _dataset(
    accessibility: str = "universal", data: Optional[List[Dict[str, Any]]] = None,
    theme: str = "corporate",
) -> List[Dict[str, Any]]:
    """Group row records into the internal per-class plotting shape.

    Parameters
    ----------
    accessibility : str, optional
        Palette accessibility level forwarded to
        :func:`_style.load_palette`.
    data : list of dict or None
        Rows with keys ``class``, ``sand``, ``silt`` and ``clay``. Defaults
        to :data:`DEMO_DATA`.
    theme : str, optional
        Forwarded to :func:`_style.load_palette`.

    Returns
    -------
    list of dict
        One dict per texture class with ``label`` (str), ``color``
        (hex), and ``points`` (list of ``(sand, silt, clay)`` triples
        in percent, each summing to 100).
    """
    palette = load_palette(accessibility, theme=theme)
    rows = list(data) if data else DEMO_DATA
    classes: Dict[str, List[Tuple[float, float, float]]] = {}
    for row in rows:
        classes.setdefault(str(row["class"]), []).append(
            (float(row["sand"]), float(row["silt"]), float(row["clay"]))
        )
    return [
        {
            "label": label,
            "color": palette.get(_CLASS_HUES[i % len(_CLASS_HUES)], "#007AFF"),
            "points": pts,
        }
        for i, (label, pts) in enumerate(classes.items())
    ]


def _project(sand: float, silt: float, clay: float) -> Tuple[float, float]:
    """Barycentric-project a (sand, silt, clay) composition to SVG (x, y).

    The three fractions are the barycentric weights of the three
    triangle corners: ``clay`` weights the apex, ``sand`` the
    bottom-left corner, ``silt`` the bottom-right corner. The point is
    their weighted average, so it lands exactly where a physical
    balance would settle.

    Parameters
    ----------
    sand, silt, clay : float
        Percentages (each 0..100) that together sum to 100.

    Returns
    -------
    tuple of float
        The ``(x, y)`` position in SVG user space.
    """
    total = sand + silt + clay
    a, b, c = sand / total, silt / total, clay / total
    x = a * _LEFT_X + b * _RIGHT_X + c * _APEX_X
    y = a * _BASE_Y + b * _BASE_Y + c * _APEX_Y
    return x, y


def _slug(label: str) -> str:
    """Turn a class label into a CSS-class-safe slug."""
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in label).strip("-")


# Local alias for the shared escape helper; call sites keep the _xml name.
_xml = xml_escape


def _grid_lines() -> List[str]:
    """Build the inner reference grid (iso-share lines every 20 %).

    Three families of parallel lines, one per component. Each line is a
    locus of constant share of one component (e.g. "clay = 40 %"),
    drawn between the two edges where that share is met.

    Returns
    -------
    list of str
        SVG ``<line>`` fragments.
    """
    lines: List[str] = []
    for k in range(1, _GRID_STEP):
        f = k / _GRID_STEP  # the constant share, e.g. 0.2, 0.4, ...
        # Constant clay = f: a horizontal-ish line from the sand edge to
        # the silt edge at height f up the triangle.
        p1 = _project((1 - f) * 100, 0, f * 100)      # on the sand-clay edge
        p2 = _project(0, (1 - f) * 100, f * 100)      # on the silt-clay edge
        # Constant sand = f: from the silt-clay edge to the silt-sand edge.
        p3 = _project(f * 100, (1 - f) * 100, 0)      # on the sand-silt edge
        p4 = _project(f * 100, 0, (1 - f) * 100)      # on the sand-clay edge
        # Constant silt = f: from the sand-clay edge to the sand-silt edge.
        p5 = _project((1 - f) * 100, f * 100, 0)      # on the sand-silt edge
        p6 = _project(0, f * 100, (1 - f) * 100)      # on the silt-clay edge
        for (ax, ay), (bx, by) in ((p1, p2), (p3, p4), (p5, p6)):
            lines.append(
                f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" '
                f'y2="{by:.1f}" stroke="{_GRID}" stroke-width="1.4"/>'
            )
    return lines


def _axis_labels() -> List[str]:
    """Build the three corner titles and the per-edge percentage ticks.

    Returns
    -------
    list of str
        SVG ``<text>`` fragments.
    """
    parts: List[str] = []
    # Corner titles.
    parts.append(
        f'<text x="{_APEX_X:.1f}" y="{_APEX_Y - 26:.1f}" font-size="23" '
        f'font-weight="700" fill="{_INK}" text-anchor="middle">Clay</text>'
    )
    parts.append(
        f'<text x="{_LEFT_X - 10:.1f}" y="{_BASE_Y + 48:.1f}" font-size="23" '
        f'font-weight="700" fill="{_INK}" text-anchor="start">Sand</text>'
    )
    parts.append(
        f'<text x="{_RIGHT_X + 10:.1f}" y="{_BASE_Y + 48:.1f}" font-size="23" '
        f'font-weight="700" fill="{_INK}" text-anchor="end">Silt</text>'
    )

    # Percentage ticks along each edge (every 20 %), as small mono labels.
    for k in range(1, _GRID_STEP):
        f = k / _GRID_STEP
        pct = int(round(f * 100))
        # Bottom edge — sand share increasing left->right (label sand %).
        bx, by = _project(f * 100, (1 - f) * 100, 0)
        parts.append(
            f'<text x="{bx:.1f}" y="{by + 26:.1f}" font-size="15" '
            f'font-family="Roboto Mono, monospace" fill="{_SUBTLE}" '
            f'text-anchor="middle">{pct}</text>'
        )
        # Left edge — clay share increasing bottom->top (label clay %).
        lx, ly = _project((1 - f) * 100, 0, f * 100)
        parts.append(
            f'<text x="{lx - 16:.1f}" y="{ly + 5:.1f}" font-size="15" '
            f'font-family="Roboto Mono, monospace" fill="{_SUBTLE}" '
            f'text-anchor="end">{pct}</text>'
        )
        # Right edge — silt share increasing top->bottom. At height ``f``
        # up the edge the silt share is ``(1 - f)``, so the tick reads
        # ``100 - pct`` (100 % silt at the bottom-right corner, 0 % at
        # the apex).
        rx, ry = _project(0, (1 - f) * 100, f * 100)
        parts.append(
            f'<text x="{rx + 16:.1f}" y="{ry + 5:.1f}" font-size="15" '
            f'font-family="Roboto Mono, monospace" fill="{_SUBTLE}" '
            f'text-anchor="start">{100 - pct}</text>'
        )
    return parts


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full ternary-plot SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``class``, ``sand``, ``silt`` and ``clay`` (each row
        summing to 100). Defaults to :data:`DEMO_DATA`.
    mode : str, optional
        Interactivity mode passed to :func:`_interactive.fullscreen_control`
        (``"self-contained"`` / ``"external"`` / ``"static"``). Defaults to
        ``"self-contained"``.
    accessibility : str, optional
        Palette accessibility level passed to :func:`_style.load_palette`
        (``"universal"`` default, plus ``"high-contrast"``, ``"monochrome"``,
        ``"deuteranopia"``, ``"protanopia"`` and ``"tritanopia"``). Wired
        through the ``--accessibility`` CLI flag by :func:`_render.render_cli`.
    theme : str, optional
        Visual theme: ``"corporate"`` (default, Roboto -- byte-identical to
        the pre-theme render) or ``"academic"`` (LaTeX-style Latin Modern).
        See :func:`sprezzature_figures.fonts.chrome_stack_for_theme`.

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    grouped = _dataset(accessibility, data, theme=theme)

    # ---- header ----
    parts: List[str] = []
    parts.append(svg_open(_WIDTH, _HEIGHT, "tn-title", "tn-desc", font_family=chrome_stack_for_theme(theme)))
    parts.append(
        '<title id="tn-title">Soil texture as a ternary of sand, silt '
        'and clay</title>'
    )
    desc = (
        "Ternary plot: an equilateral triangle whose corners are 100 % "
        "clay (top), 100 % sand (bottom-left) and 100 % silt "
        "(bottom-right). Each dot is one topsoil sample, positioned by "
        "its sand / silt / clay percentages, which always sum to 100. "
        "Samples cluster into three texture classes: "
        + ", ".join(_xml(str(d["label"])) for d in grouped)
        + ". Sandy loam sits toward the sand corner, silt loam toward "
        "the silt corner, and clay near the top."
    )
    parts.append(f'<desc id="tn-desc">{desc}</desc>')

    # ---- interactivity + house style (pure CSS, no JS) ----
    style_rows = [
        ".dot { transition: opacity .18s ease; }",
        # Hover/focus any class (a marker or its legend swatch) dims the rest.
        "svg:hover .cls, svg:focus-within .cls { opacity: .16; }",
    ]
    for d in grouped:
        s = _slug(str(d["label"]))
        style_rows.append(
            f".cls-{s}:hover .cls-{s}, .cls-{s}:focus .cls-{s}, "
            f".cls-{s}:hover, .cls-{s}:focus {{ opacity: 1; }}"
        )
    style_rows.extend([
        ".legend-row { cursor: pointer; }",
        f".legend-row:focus {{ outline: 3px solid {_FOCUS}; outline-offset: 2px; }}",
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}",
        ".hit:hover+.tip,.hit:focus+.tip{opacity:1}",
        "@media (prefers-reduced-motion: reduce) { .dot { transition: none; } .tip{transition:none} }",
    ])
    # OS-adaptive overrides (additive; the default render is byte-identical
    # because every rule below lives inside a media query and a class rule only
    # outranks the inline fill once a preference is active). Under
    # prefers-contrast the three texture-class hues deepen to their
    # high-contrast values on the markers and legend swatches. Under forced
    # colours the classes hand off to the system palette — legitimate here
    # because each cloud is separated in the triangle and named in the legend,
    # so identity survives with no colour; a stronger marker stroke keeps the
    # now-monochrome dots from merging where clouds brush the same region.
    class_series = {f".cls-{_slug(str(d['label']))}": str(d["color"]) for d in grouped}
    style_rows.append(
        os_adaptive_style(
            class_series,
            role="fill",
            forced=True,
            extra_forced=".dot{stroke:Canvas !important;stroke-width:2 !important;}",
        )
    )
    # Additive OS dark-mode block. The white page darkens and the ink text flips
    # to light via the ink-map default; we also darken the near-white triangle
    # face (#FCFCFD) and its inner grid (#D8D8DD), and lighten the triangle
    # outline (a #1D1D1F *stroke*, which the fill-only ink map cannot reach) so
    # the frame still reads. The class hues and the white marker keylines are
    # data / separators and left alone. No multiply groups.
    style_rows.append(
        os_dark_style(
            screen_blend=False,
            extra='[fill="#FCFCFD"]{fill:#141416;} '
            '[stroke="#D8D8DD"]{stroke:#3A3A3C;} '
            '[stroke="#1D1D1F"]{stroke:#F2F2F7;}',
        )
    )
    parts.append("<style>\n" + "\n".join(style_rows) + "\n</style>")

    # ---- background ----
    parts.append(f'<rect width="{_WIDTH}" height="{_HEIGHT}" fill="{_BG}"/>')

    # ---- title + subtitle ----
    parts.append(
        f'<text x="56" y="60" font-size="29" font-weight="700" '
        f'fill="{_INK}">Three soil textures, three corners of the triangle</text>'
    )
    parts.append(
        f'<text x="56" y="94" font-size="18" fill="{_SUBTLE}">'
        f'Topsoil samples by grain-size mix · sand + silt + clay = 100 % '
        f'</text>'
    )

    # ---- triangle fill + inner grid ----
    tri = (
        f'{_LEFT_X:.1f},{_BASE_Y:.1f} {_RIGHT_X:.1f},{_BASE_Y:.1f} '
        f'{_APEX_X:.1f},{_APEX_Y:.1f}'
    )
    parts.append(
        f'<polygon points="{tri}" fill="#FCFCFD" stroke="none"/>'
    )
    parts.extend(_grid_lines())
    parts.append(
        f'<polygon points="{tri}" fill="none" stroke="{_EDGE}" '
        f'stroke-width="2.4" stroke-linejoin="round"/>'
    )

    # ---- axis / corner labels + ticks ----
    parts.extend(_axis_labels())

    # ---- sample markers, grouped by texture class ----
    for d in grouped:
        s = _slug(str(d["label"]))
        color = str(d["color"])
        parts.append(f'<g class="cls cls-{s}">')
        for (sand, silt, clay) in d["points"]:  # type: ignore[union-attr]
            x, y = _project(float(sand), float(silt), float(clay))
            tip = f"{d['label']} — sand {sand} %, silt {silt} %, clay {clay} %"
            parts.append(
                f'<circle class="dot cls-{s} hit" tabindex="0" cx="{x:.1f}" cy="{y:.1f}" '
                f'r="9.5" fill="{color}" fill-opacity="0.82" '
                f'stroke="#FFFFFF" stroke-width="1.8" '
                f'role="img" aria-label="{_xml(tip)}"/>'
            )
            parts.append(
                tooltip_bubble(
                    x, y - 16,
                    [str(d["label"]), f"sand {sand} %", f"silt {silt} % · clay {clay} %"],
                    anchor="middle", canvas_w=_WIDTH, canvas_h=_HEIGHT,
                    ink=_INK, secondary=_SUBTLE, border=_GRID,
                )
            )
        parts.append('</g>')

    # ---- legend (top-right) ----
    legend_x = 812.0
    legend_y = 200.0
    row_h = 44.0
    parts.append(f'<g transform="translate({legend_x:.1f},{legend_y:.1f})">')
    parts.append(
        f'<text x="0" y="-16" font-size="16" font-weight="700" '
        f'fill="{_SUBTLE}">Texture class</text>'
    )
    for k, d in enumerate(grouped):
        s = _slug(str(d["label"]))
        color = str(d["color"])
        cy = k * row_h
        parts.append(
            f'<g class="cls cls-{s} legend-row" tabindex="0" role="listitem" '
            f'transform="translate(0,{cy:.1f})">'
            f'<title>{_xml(str(d["label"]))}: '
            f'{len(d["points"])} samples</title>'  # type: ignore[arg-type]
        )
        parts.append(
            f'<circle class="cls-{s}" cx="11" cy="11" r="11" fill="{color}" '
            f'fill-opacity="0.82" stroke="#FFFFFF" stroke-width="1.8"/>'
        )
        parts.append(
            f'<text x="34" y="17" font-size="19" font-weight="600" '
            f'fill="{_INK}">{_xml(str(d["label"]))}</text>'
        )
        parts.append('</g>')
    parts.append('</g>')

    # ---- reading hint ----
    parts.append(
        f'<text x="56" y="{_HEIGHT - 26:.1f}" font-size="15" '
        f'fill="{_SUBTLE}">Read each corner as 100 % of that grain size; '
        f'a dot near an edge means the opposite corner is near 0 %.</text>'
    )

    parts.append(fullscreen_control(_WIDTH, _HEIGHT, mode))
    parts.append('</svg>')
    return "\n".join(parts)


def make_ternary(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "",
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render the ternary plot and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``class``, ``sand``, ``silt`` and ``clay``. Defaults
        to :data:`DEMO_DATA`.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/ternary.svg``.
    title : str, optional
        Accepted for dispatcher parity; the plot's own headline states the
        specific takeaway, so this is unused.
    mode, accessibility : str
        Forwarded to :func:`build_svg`.
    theme : str, optional
        Visual theme. Forwarded to :func:`build_svg`.

    Returns
    -------
    Path
        Absolute path to the written SVG file.
    """
    del title
    svg = build_svg(data, mode=mode, accessibility=accessibility, theme=theme)
    dest = Path(out) if out else svg_example_path(__file__, "ternary")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """Write the ternary SVG to the skill's ``svg-examples`` folder."""
    render_cli(__file__, "ternary", build_svg, description="Render the ternary SVG.")


if __name__ == "__main__":
    main()
