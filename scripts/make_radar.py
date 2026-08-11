#!/usr/bin/env python3
"""Generate a publication-quality *radar (spider) chart* as a standalone SVG.

A radar chart plots several **quantitative criteria** as spokes radiating from a
common centre; each subject (a product, a city, a team) becomes a closed polygon
whose vertices sit on the spokes. Its whole reason to exist is *profile
comparison at a glance*: you see the **shape** of a subject's strengths and
weaknesses, and you see where two subjects trade places. It is the R
``fmsb::radarchart`` / matplotlib ``polar`` / plotly ``scatterpolar`` idiom.

The classic failure mode of the chart is **colour-on-colour**: two translucent
filled polygons overlap into a muddy grey blob and no series stays readable.
This generator sidesteps that entirely — each series is a **thick coloured
outline** with **vertex dots** and only a *very light* fill, so overlaps never
turn grey and every profile stays traceable to its legend colour.

This module builds the SVG string **by hand** (no matplotlib / seaborn /
plotly, no Vega): it lays out the angular spokes, draws concentric grid rings
with a rounded radial scale, and paints one outlined polygon per subject. The
figure is deliberately **static** — the shape *is* the insight, and a still
renders it in full. Everything is in the sprezzature-* house style: Roboto type, the
Apple-system palette, ink ``#1D1D1F`` on a white ground, rounded framing, and
native ``<title>`` hover tooltips (no JavaScript).

The example data is illustrative: three managed cloud databases scored 0–100
across six buyer criteria, chosen so the three profiles genuinely cross — one
wins on speed, one on ecosystem, one on price — which is exactly the situation a
radar chart is built to reveal.

Usage
-----
    python make_radar.py                 # writes the house SVG
    python make_radar.py --out other.svg

Style rules: numpy docstrings, full typing, dict-as-record over ad-hoc
classes, generous comments.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Reuse the shared, output-identical SVG primitives.
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _svg import fmt_compact, point_on_circle, svg_open, xml_escape  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _style import (  # noqa: E402
    forced_color_patterns,
    leveled_colors,
    os_adaptive_style,
    os_dark_style,
    qualitative_sequence,
)
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402


# House-style tokens (mirrors the house-style constants, kept literal so this
# generator needs no import of the dataviz tier at build time).
_INK = "#1D1D1F"        # primary text
_SECONDARY = "#6E6E73"  # subtitle / secondary text
_BG = "#FFFFFF"         # white ground
_GRID = "#E5E5EA"       # light grid rings / spokes
_GRID_STRONG = "#C7C7CC"  # the outer ring, a touch stronger for a clean rim
_FONT = "Roboto, system-ui, sans-serif"
_MONO = "Roboto Mono, ui-monospace, monospace"

# Series palette — three saturated, well-separated Apple-system hues, one per
# database. Blue / Orange / Purple stay distinct under the common colour-vision
# deficiencies (they differ in hue *and* lightness), so the outlines never
# collapse into one another even where the polygons cross. This is a *fixed
# categorical* set (one hue per series, no magnitude ordering), so it answers to
# ``--accessibility`` via :func:`_style.leveled_colors`: ``universal`` (default)
# leaves it byte-for-byte unchanged; the other levels remap all three hues
# through the shared sprezzature-colors engine so the polygons stay separable under a
# named colour-vision deficiency, monochrome, or high contrast.
_SERIES_COLORS: Dict[str, str] = {
    "Aurora": "#007AFF",
    "Cloud SQL": "#FF9500",
    "Cosmos": "#AF52DE",
}

# Ralph Eyeball Loop finding: Blue (#007AFF) and Purple (#AF52DE) are close
# enough in perceptual luminance that a plain grayscale conversion of the
# *default* (universal) render collapses them into two nearly-identical dark
# grey outlines -- verified by screenshotting the rendered SVG through a CSS
# grayscale filter, not just assumed from the hex values. ``accessibility=
# "monochrome"`` already remaps the hues to genuinely separable greys
# (#6D6D6D/#8F8F8F/#1B1B1B), but that is an opt-in level; the default render
# itself needs a colour-independent channel too, since most viewers never
# pass that flag and a screenshot/printout can still land in grayscale.
# Solid/dashed/dotted outlines are a redundant channel on top of hue, so the
# series stay separable by pattern alone regardless of colour rendering.
_DASH_PATTERNS: Tuple[str, ...] = ("", "16,8", "3,5")


# --------------------------------------------------------------------------- #
#                                                             #
# --------------------------------------------------------------------------- #
def _sample_scores() -> Dict[str, object]:
    """Return the illustrative radar dataset: 3 databases × 6 criteria.

    Scores are on a 0–100 "higher is better" scale (each raw metric already
    normalised into that frame, so the outer ring is always "best"). The three
    profiles are shaped to genuinely cross: *Aurora* leads on raw speed and
    scaling, *Cloud SQL* on ecosystem and ease of use, *Cosmos* on global
    reach and price — no single polygon dominates, which is the whole point of
    reaching for a radar.

    Returns
    -------
    dict
        ``{"axes": [str, ...], "series": [{"name": str, "values":
        [float, ...]}, ...]}`` — one value per axis, in axis order.
    """
    axes = [
        "Query speed",
        "Auto-scaling",
        "Ecosystem",
        "Ease of use",
        "Global reach",
        "Price",
    ]
    series = [
        {"name": "Aurora", "values": [92.0, 88.0, 70.0, 64.0, 58.0, 52.0]},
        {"name": "Cloud SQL", "values": [74.0, 66.0, 90.0, 86.0, 62.0, 68.0]},
        {"name": "Cosmos", "values": [68.0, 78.0, 60.0, 58.0, 94.0, 84.0]},
    ]
    return {"axes": axes, "series": series}


#: Row-record demo data: one row per (axis, series) score, the contract's
#: ``list[dict[str, Any]]`` shape. :func:`_rows_to_radar_data` reshapes it
#: (or any caller-supplied row list of the same shape) into the
#: ``{"axes": [...], "series": [...]}`` structure :func:`build_svg` needs.
_SAMPLE = _sample_scores()
DEMO_DATA: List[Dict[str, Any]] = [
    {"axis": axis, "series": s["name"], "value": v}
    for s in _SAMPLE["series"]
    for axis, v in zip(_SAMPLE["axes"], s["values"], strict=True)
]
del _SAMPLE


def _rows_to_radar_data(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Reshape ``{"axis", "series", "value"}`` rows into the radar's axes/series shape.

    Parameters
    ----------
    rows : list of dict
        Rows with ``axis`` (str), ``series`` (str) and ``value`` (numeric)
        keys. Axis order follows first appearance; series order likewise.

    Returns
    -------
    dict
        ``{"axes": [str, ...], "series": [{"name", "values"}, ...]}``, the
        shape :func:`build_svg` expects.
    """
    axes: List[str] = []
    series_map: "Dict[str, Dict[str, Any]]" = {}
    for r in rows:
        axis = str(r["axis"])
        name = str(r["series"])
        if axis not in axes:
            axes.append(axis)
        bucket = series_map.setdefault(name, {"name": name, "values": {}})
        bucket["values"][axis] = float(r["value"])
    series = [
        {"name": name, "values": [bucket["values"].get(a, 0.0) for a in axes]}
        for name, bucket in series_map.items()
    ]
    return {"axes": axes, "series": series}


# --------------------------------------------------------------------------- #
# Geometry                                                                     #
# --------------------------------------------------------------------------- #
def _spoke_angle_deg(index: int, n: int) -> float:
    """Return the clock angle (deg, clockwise from top) for spoke ``index``.

    Spoke 0 sits at the top (12 o'clock) and the rest are spaced evenly
    clockwise, the orientation readers expect from a radar / spider chart.
    """
    return (index / n) * 360.0


def _polar_to_xy(cx: float, cy: float, r: float, theta_deg: float) -> Tuple[float, float]:
    """Convert a clock-oriented polar coordinate to an SVG ``(x, y)`` pixel.

    ``theta_deg`` is measured clockwise from the top (12 o'clock = 0°). Under
    :func:`_svg.point_on_circle` (math convention, 0° = +x, CCW), "clockwise
    from top" is the angle ``theta_deg - 90`` — so we delegate the trig to the
    shared helper and keep the output byte-identical to an inline computation.

    Parameters
    ----------
    cx, cy : float
        Centre of the dial in pixels.
    r : float
        Radius in pixels.
    theta_deg : float
        Angle in degrees, clockwise from the 12 o'clock position.

    Returns
    -------
    tuple of float
        The ``(x, y)`` pixel position.
    """
    return point_on_circle(cx, cy, r, math.radians(theta_deg - 90.0))


# --------------------------------------------------------------------------- #
# SVG assembly                                                                 #
# --------------------------------------------------------------------------- #
def build_svg(
    data: Optional[Dict[str, Any]] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full radar-chart SVG document as a string.

    Parameters
    ----------
    data : dict or None
        The dataset from :func:`_sample_scores`: ``axes`` (list of str) and
        ``series`` (list of ``{"name", "values"}`` records). Defaults to
        :data:`DEMO_DATA`, reshaped via :func:`_rows_to_radar_data`.
    mode : str, optional
        Interactivity mode passed to :func:`_interactive.fullscreen_control`
        (``"self-contained"``, ``"external"`` or ``"static"``). Controls
        whether the emitted SVG carries its own fullscreen button; the raster
        output is unaffected. Defaults to ``"self-contained"``.
    accessibility : str, optional
        Palette accessibility level for the *fixed categorical* series hues
        (``"universal"``, ``"high-contrast"``, ``"monochrome"``,
        ``"deuteranopia"``, ``"protanopia"`` or ``"tritanopia"``). The three
        per-database hues are one-per-series with no magnitude ordering, so they
        are remapped through :func:`_style.leveled_colors`. Defaults to
        ``"universal"``, which leaves the colours (and the emitted bytes)
        unchanged.
    theme : str, optional
        Visual theme: ``"corporate"`` (default, Roboto -- byte-identical to
        the pre-theme render) or ``"academic"`` (LaTeX-style Latin Modern).
        See :func:`sprezzature_figures.fonts.chrome_stack_for_theme`.

    Returns
    -------
    str
        A complete, self-contained SVG document.
    """
    data = data if data is not None else _rows_to_radar_data(DEMO_DATA)
    axes: List[str] = list(data["axes"])           # type: ignore[arg-type]
    series: List[Dict[str, Any]] = list(data["series"])
    n = len(axes)

    # Level the fixed categorical series hues to the requested accessibility
    # level; ``universal`` is the identity, so the default stays byte-identical.
    # A caller-supplied series name outside the curated three falls back to
    # the house qualitative sequence, so custom data never KeyErrors here.
    mono_family = mono_stack_for_theme(theme)
    series_colors = leveled_colors(_SERIES_COLORS, accessibility)
    fallback_hues = qualitative_sequence(max(len(series), 1), theme=theme)
    palette = [
        series_colors.get(str(s["name"]), fallback_hues[i % len(fallback_hues)])
        for i, s in enumerate(series)
    ]

    # Poster-scale canvas: a generous square dial with room for the title band
    # up top, the axis labels around the rim, and the legend along the bottom.
    width, height = 1000, 1080

    cx = width / 2.0
    cy = 588.0
    r_outer = 344.0     # outermost grid ring == score 100
    score_max = 100.0
    rings = [20.0, 40.0, 60.0, 80.0, 100.0]  # radial gridlines

    def r_px(value: float) -> float:
        """Map a 0–100 score to a pixel radius on the dial."""
        return (value / score_max) * r_outer

    parts: List[str] = []

    # ---- header / accessibility ------------------------------------------- #
    title = "No database wins on every sprezzature"
    subtitle = (
        "Three managed cloud databases scored 0–100 across six buyer criteria "
        ""
    )
    aria = (
        "Radar chart comparing three managed cloud databases — Aurora, Cloud "
        "SQL and Cosmos — across six criteria arranged as spokes: query speed, "
        "auto-scaling, ecosystem, ease of use, global reach and price, each "
        "scored 0 to 100 where the outer ring is best. Aurora forms a tall "
        "profile on query speed and auto-scaling; Cloud SQL peaks on ecosystem "
        "and ease of use; Cosmos reaches furthest on global reach and price. "
        "The three profiles cross, so no single database dominates."
    )
    parts.append(svg_open(width, height, "radar-title", "radar-desc", font_family=chrome_stack_for_theme(theme)))
    parts.append(f'<title id="radar-title">{xml_escape(title)}</title>')
    parts.append(f'<desc id="radar-desc">{xml_escape(aria)}</desc>')
    parts.append(f'<rect width="{width}" height="{height}" rx="22" fill="{_BG}"/>')

    # ---- OS-adaptive overrides (additive; every rule lives inside an @media
    # block, so the default render is byte-for-byte unchanged). Each series
    # carries a stable ``.rad-i`` class on its polygon outline, vertex dots and
    # legend disk. Under prefers-contrast the three hues deepen together to
    # their high-contrast spacing (role="both": the outline stroke and the dot /
    # disk / light-tint fills), keeping the crossing profiles pairwise
    # separable. Under forced-colors (Windows High Contrast) the ~4-colour system
    # palette cannot preserve three crossing hues, so each profile is instead
    # handed a distinct Canvas/CanvasText PATTERN (hatch / dots / cross) via
    # forced_color_patterns: the fill of every polygon, vertex dot and legend disk
    # for a series becomes that series' pattern, so the profiles stay pairwise
    # distinguishable even when colour is stripped.
    rad_series = {f".rad-{i}": palette[i] for i in range(len(series))}
    fcp_defs, fcp_style = forced_color_patterns(
        [f".rad-{i}" for i in range(len(series))], prefix="radar-fcp"
    )
    # Dark mode: paper + inks invert via os_dark_style defaults; the light grid
    # rings / spokes (strokes) are dimmed to a dark-surface grey so they frame
    # without glaring, and any multiply blend flips to screen.
    dark_extra = (
        '[stroke="#E5E5EA"]{stroke:#2C2C2E;}'
        '[stroke="#C7C7CC"]{stroke:#3A3A3C;}'
    )
    parts.append(
        "<style>"
        + os_adaptive_style(rad_series, role="both")
        + fcp_style
        + os_dark_style(extra=dark_extra)
        + "</style>"
    )
    parts.append(f"<defs>{fcp_defs}</defs>")

    parts.append(
        f'<text x="64" y="80" font-size="38" font-weight="700" fill="{_INK}">'
        f"{xml_escape(title)}</text>"
    )
    parts.append(
        f'<text x="64" y="120" font-size="21" fill="{_SECONDARY}">'
        f"{xml_escape(subtitle)}</text>"
    )

    # ---- grid rings + radial tick labels ---------------------------------- #
    # Concentric polygons (not circles) so the grid echoes the chart's own
    # geometry — the classic spider web. The outermost ring is drawn a touch
    # stronger so the plot area reads as a clean bounded field.
    for ring_val in rings:
        rr = r_px(ring_val)
        pts = " ".join(
            f"{fmt_compact(x)},{fmt_compact(y)}"
            for x, y in (
                _polar_to_xy(cx, cy, rr, _spoke_angle_deg(i, n)) for i in range(n)
            )
        )
        stroke = _GRID_STRONG if ring_val == rings[-1] else _GRID
        sw = 1.6 if ring_val == rings[-1] else 1.0
        parts.append(
            f'<polygon points="{pts}" fill="none" stroke="{stroke}" '
            f'stroke-width="{sw}"/>'
        )
        # Radial tick label along the top spoke, nudged just right of it so it
        # never sits on the vertical gridline.
        lx, ly = _polar_to_xy(cx, cy, rr, 0.0)
        parts.append(
            f'<text x="{fmt_compact(lx + 10)}" y="{fmt_compact(ly + 5)}" font-size="15" '
            f'font-family="{mono_family}" fill="{_SECONDARY}">{int(ring_val)}</text>'
        )

    # ---- spokes + axis labels --------------------------------------------- #
    for i, axis_name in enumerate(axes):
        ang = _spoke_angle_deg(i, n)
        ex, ey = _polar_to_xy(cx, cy, r_outer, ang)
        parts.append(
            f'<line x1="{fmt_compact(cx)}" y1="{fmt_compact(cy)}" x2="{fmt_compact(ex)}" '
            f'y2="{fmt_compact(ey)}" stroke="{_GRID}" stroke-width="1"/>'
        )
        # Axis label just outside the rim. Side-aware anchoring keeps the text
        # from crowding the polygons: labels on the right hang left-aligned,
        # labels on the left right-aligned, and the top/bottom labels centre.
        lx, ly = _polar_to_xy(cx, cy, r_outer + 34, ang)
        if 5.0 < ang < 175.0:
            anchor = "start"
        elif 185.0 < ang < 355.0:
            anchor = "end"
        else:
            anchor = "middle"
        # A small vertical nudge so a bottom label drops below its dot and a
        # top label lifts above it, clear of the rim.
        dy = 7.0
        if abs(ang - 180.0) < 5.0:
            dy = 24.0
        elif ang < 5.0 or ang > 355.0:
            dy = -8.0
        parts.append(
            f'<text x="{fmt_compact(lx)}" y="{fmt_compact(ly + dy)}" text-anchor="{anchor}" '
            f'font-size="21" font-weight="600" fill="{_INK}">'
            f"{xml_escape(axis_name)}</text>"
        )

    # ---- series polygons -------------------------------------------------- #
    # Each subject is a THICK coloured outline with a VERY light fill and vertex
    # dots. The light fill (opacity 0.10) tints the interior enough to read the
    # shape but never enough for two overlapping fills to muddy into grey — the
    # colour on the interior is dominated by the crisp stroke, not the fill.
    for s_idx, subject in enumerate(series):
        color = palette[s_idx]
        name = str(subject["name"])
        values: List[float] = [float(v) for v in subject["values"]]  # type: ignore[union-attr]
        dash = _DASH_PATTERNS[s_idx % len(_DASH_PATTERNS)]
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""

        verts: List[Tuple[float, float]] = [
            _polar_to_xy(cx, cy, r_px(values[i]), _spoke_angle_deg(i, n))
            for i in range(n)
        ]
        pts = " ".join(f"{fmt_compact(x)},{fmt_compact(y)}" for x, y in verts)
        parts.append(
            f'<polygon class="rad-{s_idx}" points="{pts}" fill="{color}" '
            f'fill-opacity="0.07" stroke="{color}" stroke-width="3.6" '
            f'stroke-linejoin="round"{dash_attr}/>'
        )
        # Vertex dots, each with a thin white keyline so a dot from one series
        # stays crisp even where it lands atop another series' outline. Native
        # <title> gives a no-JavaScript hover tooltip.
        for i, (vx, vy) in enumerate(verts):
            tip = f"{name} — {axes[i]}: {values[i]:.0f}/100"
            parts.append(
                f'<g><title>{xml_escape(tip)}</title>'
                f'<circle cx="{fmt_compact(vx)}" cy="{fmt_compact(vy)}" r="6.5" '
                f'fill="{color}" stroke="{_BG}" stroke-width="2.2"/></g>'
            )

    # ---- legend (bottom, centred) ----------------------------------------- #
    # One coloured disk + name per series. Disks match the series colour with no
    # dark ring — the swatch reads as the same ink as the polygon outline. A
    # short line in the series' own dasharray sits behind each disk so the
    # legend teaches the pattern-to-name mapping too, not just colour-to-name
    # (see _DASH_PATTERNS: colour alone collapses under grayscale).
    legend_y = height - 52.0
    # Measure a rough total width to centre the row.
    gap = 56.0
    disk_r = 9.0
    swatch_line_half = 22.0  # half-length of the dash-pattern line behind each disk
    label_gap = 16.0
    char_w = 12.5  # rough advance for the 22px legend label
    entry_widths = [disk_r * 2 + label_gap + len(str(s["name"])) * char_w for s in series]
    total_w = sum(entry_widths) + gap * (len(series) - 1)
    x = cx - total_w / 2.0
    for s_idx, subject in enumerate(series):
        color = palette[s_idx]
        name = str(subject["name"])
        dash = _DASH_PATTERNS[s_idx % len(_DASH_PATTERNS)]
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        cxs = x + disk_r
        parts.append(
            f'<line x1="{fmt_compact(cxs - swatch_line_half)}" y1="{fmt_compact(legend_y)}" '
            f'x2="{fmt_compact(cxs + swatch_line_half)}" y2="{fmt_compact(legend_y)}" '
            f'stroke="{color}" stroke-width="3.6"{dash_attr}/>'
        )
        parts.append(
            f'<circle class="rad-{s_idx}" cx="{fmt_compact(cxs)}" '
            f'cy="{fmt_compact(legend_y)}" r="{disk_r}" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{fmt_compact(cxs + swatch_line_half + label_gap)}" y="{fmt_compact(legend_y + 8)}" '
            f'font-size="22" font-weight="600" fill="{_INK}">'
            f"{xml_escape(name)}</text>"
        )
        x += entry_widths[s_idx] + gap + (swatch_line_half - disk_r) * 2

    # ---- scale caption ---------------------------------------------------- #
    parts.append(
        f'<text x="{fmt_compact(cx)}" y="152" text-anchor="middle" font-size="17" '
        f'fill="{_SECONDARY}">Each spoke: 0 at the centre to 100 at the rim '
        f"(higher is better)</text>"
    )

    # Fullscreen control (the top-right corner is clear; the title sits
    # top-left and the legend runs along the bottom), per interactivity mode.
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "".join(parts)


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #
def make_radar(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "",
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render the radar (spider) chart and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``axis`` (str), ``series`` (str) and ``value``
        (numeric, 0-100). Defaults to :data:`DEMO_DATA`.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/radar.svg``.
    title : str, optional
        Accepted for signature parity; the figure's headline is baked into
        the takeaway text (unused).
    mode, accessibility : str
        Forwarded to :func:`build_svg`.
    theme : str, optional
        Visual theme. Forwarded to :func:`build_svg`.

    Returns
    -------
    Path
        Absolute path to the written SVG file.
    """
    _ = title
    rows = data if data else DEMO_DATA
    radar_data = _rows_to_radar_data(rows)
    svg = build_svg(radar_data, mode=mode, accessibility=accessibility, theme=theme)
    dest = Path(out) if out else svg_example_path(__file__, "radar")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "radar", build_svg, description="Write the house-style radar (spider) chart SVG example.")


if __name__ == "__main__":
    main()
