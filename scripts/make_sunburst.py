#!/usr/bin/env python3
"""
make_sunburst — a house-styled sunburst (radial hierarchy) chart as hand-authored SVG.

A sunburst chart displays a hierarchy as a set of concentric rings. The
innermost ring represents the top-level category; the outer ring shows the
children of the segment directly below it. Arc length is proportional to
the aggregate value of all leaves below each node. The reader can follow a
spoke outward from the centre to trace an entire branch, and compare
siblings by arc length within any ring.

Sunbursts suit hierarchies with two or three levels. Deeper hierarchies
produce arcs too thin to label. For two-level data with fewer categories,
a donut chart is more legible. For many-leaf flat hierarchies, a treemap
uses area more efficiently.

Previously rendered via full Vega (``vl_convert``, ``stratify`` +
``partition`` transforms); this module now computes the ring geometry
itself and paints the annular sectors by hand -- no Vega, no matplotlib.
Every arc carries a native ``<title>`` tooltip with its exact value.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _style import BG, GRIDLINE, INK, SECONDARY, load_palette  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme  # noqa: E402
from _svg import svg_open, tooltip_bubble, xml_escape  # noqa: E402


REGIONS = ["Americas", "Asia Pacific", "Europe", "Middle East & Africa"]

# Chrome text (title/subtitle/legend header/accessible desc) in the two
# languages Studio can ask for (studio/i18n.py detects the language from the
# imported CSV's column names; the CLI/library/API/MCP always call with the
# "en" default). Data-derived text -- parent/name labels, numeric values --
# is never translated here; it already carries whatever language the
# caller's data uses.
_STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "title": "Global R&D Investment by Region and Country — 2023",
        "subtitle": "Total expenditure in billions of USD; arc length proportional to investment",
        "legend_header": "Region",
        "desc_template": (
            "Sunburst of {n_parents} regions and {n_children} countries, "
            "total {total} billion USD. Hover or focus an arc for its exact value."
        ),
    },
    "fr": {
        "title": "Investissement mondial en R&D par région et pays — 2023",
        "subtitle": "Dépense totale en milliards de dollars ; la longueur d'arc est proportionnelle à l'investissement",
        "legend_header": "Région",
        "desc_template": (
            "Diagramme en soleil de {n_parents} régions et {n_children} pays, "
            "total {total} milliards de dollars. Survolez ou activez le focus "
            "sur un arc pour sa valeur exacte."
        ),
    },
}


def _strings(language: str) -> Dict[str, str]:
    """Chrome-text dict for `language`, falling back to English."""
    return _STRINGS.get(language, _STRINGS["en"])

# ---------------------------------------------------------------------------
# Demo data: global R&D investment by region and country (billion USD, 2023).
# Two-level hierarchy: region -> country.
# ---------------------------------------------------------------------------
DEMO_DATA: List[Dict[str, Any]] = [
    # Europe
    {"parent": "Europe", "name": "Germany", "value": 119.4},
    {"parent": "Europe", "name": "France", "value": 62.1},
    {"parent": "Europe", "name": "United Kingdom", "value": 53.8},
    {"parent": "Europe", "name": "Sweden", "value": 22.6},
    {"parent": "Europe", "name": "Netherlands", "value": 19.3},
    {"parent": "Europe", "name": "Other Europe", "value": 84.5},
    # Americas
    {"parent": "Americas", "name": "United States", "value": 738.2},
    {"parent": "Americas", "name": "Canada", "value": 30.4},
    {"parent": "Americas", "name": "Brazil", "value": 22.9},
    {"parent": "Americas", "name": "Other Americas", "value": 18.1},
    # Asia Pacific
    {"parent": "Asia Pacific", "name": "China", "value": 570.6},
    {"parent": "Asia Pacific", "name": "Japan", "value": 172.3},
    {"parent": "Asia Pacific", "name": "South Korea", "value": 99.4},
    {"parent": "Asia Pacific", "name": "India", "value": 59.2},
    {"parent": "Asia Pacific", "name": "Australia", "value": 24.1},
    # Middle East & Africa
    {"parent": "Middle East & Africa", "name": "Israel", "value": 24.9},
    {"parent": "Middle East & Africa", "name": "Saudi Arabia", "value": 11.6},
    {"parent": "Middle East & Africa", "name": "South Africa", "value": 5.3},
]


def _polar(cx: float, cy: float, r: float, angle: float) -> Tuple[float, float]:
    """Point at *angle* radians clockwise from 12 o'clock, radius *r*."""
    return cx + r * math.sin(angle), cy - r * math.cos(angle)


def _annular_sector_path(cx: float, cy: float, r_inner: float, r_outer: float,
                          a0: float, a1: float) -> str:
    """Return an SVG path ``d`` for a donut wedge between angles *a0* and *a1*."""
    large_arc = 1 if (a1 - a0) > math.pi else 0
    ox0, oy0 = _polar(cx, cy, r_outer, a0)
    ox1, oy1 = _polar(cx, cy, r_outer, a1)
    ix1, iy1 = _polar(cx, cy, r_inner, a1)
    ix0, iy0 = _polar(cx, cy, r_inner, a0)
    return (
        f"M {ox0:.2f},{oy0:.2f} A {r_outer:.2f} {r_outer:.2f} 0 {large_arc} 1 {ox1:.2f},{oy1:.2f} "
        f"L {ix1:.2f},{iy1:.2f} A {r_inner:.2f} {r_inner:.2f} 0 {large_arc} 0 {ix0:.2f},{iy0:.2f} Z"
    )


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str | None = None,
    subtitle: str | None = None,
    width: int = 800,
    height: int = 640,
    mode: str = "self-contained",
    accessibility: str = "universal",
    language: str = "en",
    theme: str = "corporate",
) -> str:
    """Assemble the full sunburst SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Flat rows with keys ``parent`` (region), ``name`` (country),
        ``value`` (numeric). Defaults to :data:`DEMO_DATA`.
    title, subtitle : str or None
        Chart text. ``None`` (the default) picks the illustrative title/
        subtitle for `language`; an explicit string is always honoured
        verbatim regardless of `language`.
    width, height : int
        Canvas size in pixels.
    mode, accessibility : str, optional
        Forwarded to :func:`_interactive.fullscreen_control` /
        :func:`_style.load_palette`.
    language : str, optional
        Chrome-text language, ``"en"`` or ``"fr"`` (see :data:`_STRINGS`).
        Only the title/subtitle default, legend header and accessible desc
        switch; ``parent``/``name`` labels and values always render as
        given in `data`. Defaults to ``"en"``.
    theme : str, optional
        Visual theme: ``"corporate"`` (default, Roboto -- byte-identical to
        the pre-theme render) or ``"academic"`` (LaTeX-style Latin Modern).
        See :func:`sprezzature_figures.fonts.chrome_stack_for_theme`.

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    strings = _strings(language)
    title = strings["title"] if title is None else title
    subtitle = strings["subtitle"] if subtitle is None else subtitle
    rows = data if data else DEMO_DATA
    region_totals: Dict[str, float] = defaultdict(float)
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        region_totals[row["parent"]] += float(row["value"])
        grouped[row["parent"]].append(row)
    regions_sorted = sorted(region_totals, key=lambda r: -region_totals[r])
    for r in grouped:
        grouped[r].sort(key=lambda x: -float(x["value"]))
    total = sum(region_totals.values()) or 1.0

    palette = load_palette(accessibility, theme=theme)
    hue_order = [palette.get("Blue", "#007AFF"), palette.get("Green", "#34C759"),
                 palette.get("Orange", "#FF9500"), palette.get("Purple", "#AF52DE")]
    region_colors = {r: hue_order[i % len(hue_order)] for i, r in enumerate(regions_sorted)}

    legend_w = 190.0
    side_margin, top_margin, bottom_margin = 40.0, 118.0, 30.0
    avail_w = width - side_margin * 2 - legend_w
    avail_h = height - top_margin - bottom_margin
    r_outer_canvas = min(avail_w, avail_h) / 2.0
    cx = side_margin + avail_w / 2.0
    cy = top_margin + avail_h / 2.0

    hole = r_outer_canvas * 0.30
    ring1_inner, ring1_outer = hole, hole + (r_outer_canvas - hole) * 0.42
    ring2_inner, ring2_outer = hole + (r_outer_canvas - hole) * 0.48, r_outer_canvas

    parts: List[str] = []
    parts.append(svg_open(width, height, "sb-title", "sb-desc", font_family=chrome_stack_for_theme(theme)))
    parts.append(f'<title id="sb-title">{xml_escape(title)}</title>')
    desc = strings["desc_template"].format(
        n_parents=len(regions_sorted), n_children=len(rows), total=f"{total:,.1f}"
    )
    parts.append(f'<desc id="sb-desc">{xml_escape(desc)}</desc>')

    parts.append(
        "<style>"
        ".arc{transition:opacity .15s ease;cursor:default;}"
        ".arc:hover,.arc:focus{opacity:.72;outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        ".hit:hover~.tip,.hit:focus~.tip{opacity:1}"
        "@media (prefers-reduced-motion: reduce){.arc{transition:none;}"
        ".tip{transition:none}}"
        "</style>"
    )

    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="40" y="46" font-size="24" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(f'<text x="40" y="70" font-size="14" fill="{SECONDARY}">{xml_escape(subtitle)}</text>')

    # ---- ring 1: regions ----
    angle = 0.0
    region_angles: Dict[str, Tuple[float, float]] = {}
    for r in regions_sorted:
        share = region_totals[r] / total
        a0, a1 = angle, angle + share * 2.0 * math.pi
        region_angles[r] = (a0, a1)
        angle = a1
        d = _annular_sector_path(cx, cy, ring1_inner, ring1_outer, a0, a1)
        tip = f"{r}: {region_totals[r]:,.1f} bn USD ({share * 100:.1f}% of total)"
        parts.append(
            f'<path class="arc hit" tabindex="0" d="{d}" fill="{region_colors[r]}" '
            f'stroke="{BG}" stroke-width="1.5" role="img" aria-label="{xml_escape(tip)}"/>'
        )
        tip_x, tip_y = _polar(cx, cy, ring1_outer, (a0 + a1) / 2.0)
        parts.append(
            tooltip_bubble(
                tip_x, tip_y - 14,
                [r, f"{region_totals[r]:,.1f} bn USD", f"{share * 100:.1f}% of total"],
                anchor="middle", canvas_w=width, canvas_h=height,
                ink=INK, secondary=SECONDARY, border=GRIDLINE,
            )
        )
        if (a1 - a0) > 0.18:
            mid_r = (ring1_inner + ring1_outer) / 2.0
            lx, ly = _polar(cx, cy, mid_r, (a0 + a1) / 2.0)
            parts.append(
                f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="12" font-weight="700" fill="{BG}" '
                f'text-anchor="middle" dominant-baseline="middle">{xml_escape(r)}</text>'
            )

    # ---- ring 2: countries ----
    for r in regions_sorted:
        a0_region, a1_region = region_angles[r]
        span_region = a1_region - a0_region
        sub_total = region_totals[r] or 1.0
        angle = a0_region
        for row in grouped[r]:
            share_local = float(row["value"]) / sub_total
            a0, a1 = angle, angle + share_local * span_region
            angle = a1
            d = _annular_sector_path(cx, cy, ring2_inner, ring2_outer, a0, a1)
            tip = f"{r} / {row['name']}: {float(row['value']):,.1f} bn USD"
            parts.append(
                f'<path class="arc hit" tabindex="0" d="{d}" fill="{region_colors[r]}" fill-opacity="0.55" '
                f'stroke="{BG}" stroke-width="1" role="img" aria-label="{xml_escape(tip)}"/>'
            )
            tip_x2, tip_y2 = _polar(cx, cy, ring2_outer, (a0 + a1) / 2.0)
            parts.append(
                tooltip_bubble(
                    tip_x2, tip_y2 - 14,
                    [row["name"], f"{float(row['value']):,.1f} bn USD", f"{share_local * 100:.1f}% of {r}"],
                    anchor="middle", canvas_w=width, canvas_h=height,
                    ink=INK, secondary=SECONDARY, border=GRIDLINE,
                )
            )

    # ---- legend ----
    lx0 = side_margin + avail_w + 30.0
    ly0 = top_margin
    parts.append(
        f'<text x="{lx0:.1f}" y="{ly0:.1f}" font-size="13" font-weight="700" '
        f'fill="{INK}">{xml_escape(strings["legend_header"])}</text>'
    )
    for i, r in enumerate(regions_sorted):
        ly = ly0 + 26.0 + i * 24.0
        parts.append(f'<circle cx="{lx0 + 6:.1f}" cy="{ly - 4:.1f}" r="6" fill="{region_colors[r]}"/>')
        parts.append(f'<text x="{lx0 + 20:.1f}" y="{ly:.1f}" font-size="12" fill="{INK}">{xml_escape(r)}</text>')

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_sunburst(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str | None = None,
    subtitle: str | None = None,
    width: int = 800,
    height: int = 640,
    mode: str = "self-contained",
    accessibility: str = "universal",
    language: str = "en",
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored sunburst chart and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Flat rows with keys ``parent`` (str), ``name`` (str), ``value``
        (float). Defaults to DEMO_DATA (R&D investment by region/country).
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/sunburst.svg``.
    title, subtitle : str or None
        Chart text. ``None`` picks the `language`-appropriate default.
    width, height : int
        Canvas size in pixels.
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
    >>> p = make_sunburst()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility, language=language, theme=theme)
    dest = Path(out) if out else svg_example_path(__file__, "sunburst")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "sunburst", build_svg, description="Generate a sunburst radial hierarchy chart.")


if __name__ == "__main__":
    main()
