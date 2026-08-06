#!/usr/bin/env python3
"""
make_choropleth — a house-styled world choropleth map as hand-authored SVG.

Encodes a numeric value per country as fill colour on a world map: a
single pale-to-navy blue ramp so magnitude reads by lightness alone
(colour-vision-deficiency- and greyscale-safe by construction), countries
with no assigned value fall back to neutral grey rather than vanishing.
Typical uses: any per-country indicator -- exposure or risk index,
adoption rate, survey coverage -- where geography itself carries meaning
the reader already has spatial intuition for.

Previously rendered via Vega-Lite's ``geoshape`` mark against a bundled
TopoJSON country atlas and an ``equalEarth`` projection (``vl_convert``);
this module now decodes the same offline TopoJSON atlas
(``assets/geo/countries-110m.json``, vendored Natural Earth data, already
used by ``make_situation_map.py``) and projects it itself with a plain
equirectangular projection -- no Vega, no matplotlib, no ``pyproj``. Every
country carries a native ``<title>`` tooltip with its exact value.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _svg import svg_open, xml_escape  # noqa: E402

INK = "#1D1D1F"
SECONDARY = "#6E6E73"
BG = "#FFFFFF"
NO_DATA = "#E5E5EA"
NO_DATA_EDGE = "#D1D1D6"

_GEO = Path(__file__).resolve().parent.parent / "assets" / "geo" / "countries-110m.json"

# Sequential blue ramp — pale sky -> system blue -> deep navy (same ramp
# make_heatmap.py / make_calendar-heatmap.py use).
_RAMP: Tuple[Tuple[float, str], ...] = (
    (0.00, "#EAF3FF"),
    (0.62, "#007AFF"),
    (1.00, "#0A4DA0"),
)


def _ramp_hex(t: float) -> str:
    """Sample the house blue ramp at position ``t`` in ``[0, 1]``."""
    t = min(1.0, max(0.0, t))
    for (lo_t, lo_c), (hi_t, hi_c) in zip(_RAMP, _RAMP[1:]):
        if lo_t <= t <= hi_t:
            local = (t - lo_t) / (hi_t - lo_t) if hi_t > lo_t else 0.0
            ar, ag, ab = int(lo_c[1:3], 16), int(lo_c[3:5], 16), int(lo_c[5:7], 16)
            br, bg, bb = int(hi_c[1:3], 16), int(hi_c[3:5], 16), int(hi_c[5:7], 16)
            r = round(ar + (br - ar) * local)
            g = round(ag + (bg - ag) * local)
            b = round(ab + (bb - ab) * local)
            return f"#{r:02X}{g:02X}{b:02X}"
    return _RAMP[-1][1]


# ---------------------------------------------------------------------------
# Synthetic "global exposure index" demo values, keyed by ISO-3166-1 numeric
# country code (the same ids the vendored TopoJSON atlas uses). Invented
# figures for a fictional indicator, not real-world statistics.
# ---------------------------------------------------------------------------
DEMO_DATA: List[Dict[str, Any]] = [
    {"id": "242", "value": 23.6}, {"id": "834", "value": 10.3}, {"id": "732", "value": 39.6},
    {"id": "124", "value": 15.5}, {"id": "840", "value": 6.7}, {"id": "398", "value": 40.2},
    {"id": "860", "value": 91.8}, {"id": "598", "value": 80.0}, {"id": "360", "value": 76.5},
    {"id": "032", "value": 22.2}, {"id": "152", "value": 53.7}, {"id": "180", "value": 27.7},
    {"id": "706", "value": 17.3}, {"id": "404", "value": 10.6}, {"id": "729", "value": 21.4},
    {"id": "148", "value": 92.7}, {"id": "332", "value": 82.9}, {"id": "214", "value": 80.7},
    {"id": "643", "value": 80.0}, {"id": "044", "value": 19.3}, {"id": "238", "value": 31.0},
    {"id": "578", "value": 62.7}, {"id": "304", "value": 73.2}, {"id": "260", "value": 85.5},
    {"id": "626", "value": 88.0}, {"id": "710", "value": 8.7}, {"id": "426", "value": 60.6},
    {"id": "484", "value": 67.2}, {"id": "858", "value": 50.6}, {"id": "076", "value": 17.8},
    {"id": "068", "value": 47.4}, {"id": "604", "value": 8.9}, {"id": "170", "value": 93.5},
    {"id": "591", "value": 86.5}, {"id": "188", "value": 54.8}, {"id": "558", "value": 30.0},
    {"id": "340", "value": 90.9}, {"id": "222", "value": 57.2}, {"id": "320", "value": 88.2},
    {"id": "084", "value": 84.8}, {"id": "862", "value": 50.8}, {"id": "328", "value": 41.4},
    {"id": "740", "value": 59.9}, {"id": "250", "value": 43.1}, {"id": "218", "value": 16.1},
    {"id": "630", "value": 30.5}, {"id": "388", "value": 81.3}, {"id": "192", "value": 4.3},
    {"id": "716", "value": 4.6}, {"id": "072", "value": 62.6}, {"id": "516", "value": 28.0},
    {"id": "686", "value": 53.5}, {"id": "466", "value": 47.1}, {"id": "478", "value": 34.3},
    {"id": "204", "value": 99.7}, {"id": "562", "value": 19.6}, {"id": "566", "value": 41.3},
    {"id": "120", "value": 20.3}, {"id": "768", "value": 63.3}, {"id": "288", "value": 27.6},
    {"id": "384", "value": 35.6}, {"id": "324", "value": 74.7}, {"id": "624", "value": 32.1},
    {"id": "430", "value": 55.9}, {"id": "694", "value": 90.4}, {"id": "854", "value": 10.1},
    {"id": "140", "value": 6.2}, {"id": "178", "value": 22.9}, {"id": "266", "value": 76.5},
    {"id": "226", "value": 61.5}, {"id": "894", "value": 23.7}, {"id": "454", "value": 33.1},
    {"id": "508", "value": 17.8}, {"id": "748", "value": 45.9}, {"id": "024", "value": 4.3},
    {"id": "108", "value": 69.7}, {"id": "376", "value": 89.6}, {"id": "422", "value": 95.5},
    {"id": "450", "value": 73.5}, {"id": "275", "value": 96.0}, {"id": "270", "value": 1.8},
    {"id": "788", "value": 28.9}, {"id": "012", "value": 96.6}, {"id": "400", "value": 77.5},
    {"id": "784", "value": 41.0}, {"id": "634", "value": 94.3}, {"id": "414", "value": 62.1},
    {"id": "368", "value": 81.8}, {"id": "512", "value": 29.3}, {"id": "548", "value": 19.1},
    {"id": "116", "value": 44.4}, {"id": "764", "value": 13.6}, {"id": "418", "value": 38.2},
    {"id": "104", "value": 96.2}, {"id": "704", "value": 33.1}, {"id": "408", "value": 0.9},
    {"id": "410", "value": 4.5}, {"id": "496", "value": 17.0}, {"id": "356", "value": 78.4},
    {"id": "050", "value": 36.3}, {"id": "064", "value": 29.0}, {"id": "524", "value": 9.7},
    {"id": "586", "value": 98.2}, {"id": "004", "value": 42.4}, {"id": "762", "value": 20.8},
    {"id": "417", "value": 5.9}, {"id": "795", "value": 5.5}, {"id": "364", "value": 16.9},
    {"id": "760", "value": 67.7}, {"id": "051", "value": 15.0}, {"id": "752", "value": 4.1},
    {"id": "112", "value": 49.1}, {"id": "804", "value": 24.9}, {"id": "616", "value": 99.8},
    {"id": "040", "value": 12.2}, {"id": "348", "value": 52.9}, {"id": "498", "value": 77.4},
    {"id": "642", "value": 40.9}, {"id": "440", "value": 98.8}, {"id": "428", "value": 47.8},
    {"id": "233", "value": 24.2}, {"id": "276", "value": 41.1}, {"id": "100", "value": 3.7},
    {"id": "300", "value": 42.1}, {"id": "792", "value": 24.9}, {"id": "008", "value": 88.9},
    {"id": "191", "value": 83.1}, {"id": "756", "value": 49.9}, {"id": "442", "value": 3.2},
    {"id": "056", "value": 25.4}, {"id": "528", "value": 24.2}, {"id": "620", "value": 20.8},
    {"id": "724", "value": 23.1}, {"id": "372", "value": 87.0}, {"id": "540", "value": 14.2},
    {"id": "090", "value": 5.1}, {"id": "554", "value": 92.8}, {"id": "036", "value": 56.5},
    {"id": "144", "value": 99.1}, {"id": "156", "value": 40.3}, {"id": "158", "value": 90.1},
    {"id": "380", "value": 65.4}, {"id": "208", "value": 79.1}, {"id": "826", "value": 74.5},
    {"id": "352", "value": 49.4}, {"id": "031", "value": 9.3}, {"id": "268", "value": 21.1},
    {"id": "608", "value": 87.4}, {"id": "458", "value": 90.0}, {"id": "096", "value": 92.5},
    {"id": "705", "value": 33.7}, {"id": "246", "value": 65.7}, {"id": "703", "value": 80.0},
    {"id": "203", "value": 64.2}, {"id": "232", "value": 81.5}, {"id": "392", "value": 52.8},
    {"id": "600", "value": 65.5}, {"id": "887", "value": 68.6}, {"id": "682", "value": 26.8},
    {"id": "010", "value": 92.3}, {"id": "196", "value": 95.6}, {"id": "504", "value": 7.4},
    {"id": "818", "value": 97.1}, {"id": "434", "value": 96.2}, {"id": "231", "value": 66.8},
    {"id": "262", "value": 4.5}, {"id": "800", "value": 89.9}, {"id": "646", "value": 12.8},
    {"id": "070", "value": 96.9}, {"id": "807", "value": 66.7}, {"id": "688", "value": 6.0},
    {"id": "499", "value": 16.7}, {"id": "780", "value": 63.5}, {"id": "728", "value": 56.9},
]


def _decode_arc(arc: List[List[int]], scale: Tuple[float, float], translate: Tuple[float, float]) -> List[Tuple[float, float]]:
    """Decode one TopoJSON delta-encoded arc to absolute (lon, lat) points."""
    sx, sy = scale
    tx, ty = translate
    x = y = 0
    points: List[Tuple[float, float]] = []
    for dx, dy in arc:
        x += dx
        y += dy
        points.append((x * sx + tx, y * sy + ty))
    return points


def _ring_coords(indices: List[int], arcs: List[List[Tuple[float, float]]]) -> List[Tuple[float, float]]:
    """Assemble one polygon ring's (lon, lat) points from TopoJSON arc indices.

    A negative index ``i`` means "arc ``~i``, reversed" (the TopoJSON arc-
    sharing convention); consecutive arcs share their join point, so every
    arc after the first contributes all but its own first point.
    """
    coords: List[Tuple[float, float]] = []
    for idx in indices:
        pts = arcs[idx] if idx >= 0 else list(reversed(arcs[~idx]))
        coords.extend(pts if not coords else pts[1:])
    return coords


def _load_countries() -> List[Dict[str, Any]]:
    """Return ``[{id, name, rings: [[(lon, lat), ...], ...]}, ...]`` for every
    country polygon/multipolygon in the vendored TopoJSON atlas, each
    country flattened to its list of outer+inner rings (winding order is
    not distinguished -- the fill rule below handles holes visually via
    plain nonzero fill, close enough at this figure's scale).
    """
    topo = json.loads(_GEO.read_text(encoding="utf-8"))
    transform = topo["transform"]
    scale = tuple(transform["scale"])
    translate = tuple(transform["translate"])
    arcs = [_decode_arc(a, scale, translate) for a in topo["arcs"]]

    countries: List[Dict[str, Any]] = []
    for geom in topo["objects"]["countries"]["geometries"]:
        rings: List[List[Tuple[float, float]]] = []
        if geom["type"] == "Polygon":
            polygons = [geom["arcs"]]
        elif geom["type"] == "MultiPolygon":
            polygons = geom["arcs"]
        else:
            continue
        for polygon in polygons:
            for ring in polygon:
                rings.append(_ring_coords(ring, arcs))
        countries.append({
            "id": geom.get("id", ""),
            "name": geom.get("properties", {}).get("name", "Unknown"),
            "rings": rings,
        })
    return countries


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Global Exposure Index, by Country",
    subtitle: str = "Higher = greater exposure · synthetic demo data · no data in grey",
    width: int = 745,
    height: int = 420,
    mode: str = "self-contained",
    accessibility: str = "universal",
) -> str:
    """Assemble the full choropleth map SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``id`` (str, ISO-3166-1 numeric country code) and
        ``value`` (numeric). Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    mode : str, optional
        Forwarded to :func:`_interactive.fullscreen_control`.
    accessibility : str, optional
        Accepted for CLI parity but a documented no-op: the ramp is a
        single mono-hue blue scale, already colour-vision-deficiency-safe
        by construction (magnitude reads by lightness alone).

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    _ = accessibility
    rows = data if data else DEMO_DATA
    values_by_id = {str(r["id"]): float(r["value"]) for r in rows}
    countries = _load_countries()
    all_values = list(values_by_id.values())
    v_min, v_max = (min(all_values), max(all_values)) if all_values else (0.0, 1.0)
    v_span = (v_max - v_min) or 1.0

    top_margin, bottom_margin, side_margin = 96.0, 36.0, 20.0
    plot_w = width - 2 * side_margin
    plot_h = height - top_margin - bottom_margin
    lon_min, lon_max = -180.0, 180.0
    lat_min, lat_max = -90.0, 84.0

    def project(lon: float, lat: float) -> Tuple[float, float]:
        x = side_margin + (lon - lon_min) / (lon_max - lon_min) * plot_w
        y = top_margin + (lat_max - lat) / (lat_max - lat_min) * plot_h
        return x, y

    parts: List[str] = []
    parts.append(svg_open(width, height, "cx-title", "cx-desc"))
    parts.append(f'<title id="cx-title">{xml_escape(title)}</title>')
    n_with_data = len(values_by_id)
    parts.append(
        f'<desc id="cx-desc">Choropleth map, {n_with_data} countries with data ranging '
        f'{v_min:.1f} to {v_max:.1f}, remainder in grey. Hover or focus a country for its '
        f'exact value.</desc>'
    )
    parts.append(
        "<style>"
        ".country{transition:opacity .15s ease;}"
        ".country:hover,.country:focus{opacity:.72;outline:none;}"
        "@media (prefers-reduced-motion: reduce){.country{transition:none;}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="40" y="44" font-size="22" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(f'<text x="40" y="66" font-size="13" fill="{SECONDARY}">{xml_escape(subtitle)}</text>')

    for country in countries:
        cid = str(country["id"])
        value = values_by_id.get(cid)
        path_d_parts: List[str] = []
        for ring in country["rings"]:
            if len(ring) < 3:
                continue
            pts = [project(lon, lat) for lon, lat in ring]
            # Antimeridian wrap (e.g. Russia, Fiji cross lon +-180): a big
            # jump in screen x between consecutive points is the seam, not
            # real geometry -- break into a fresh subpath there instead of
            # drawing a line straight across the map.
            segments: List[List[Tuple[float, float]]] = [[pts[0]]]
            for (x0, _y0), (x1, y1) in zip(pts, pts[1:]):
                if abs(x1 - x0) > plot_w * 0.5:
                    segments.append([])
                segments[-1].append((x1, y1))
            for seg in segments:
                if len(seg) < 3:
                    continue
                path_d_parts.append("M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in seg) + " Z")
        if not path_d_parts:
            continue
        path_d = " ".join(path_d_parts)
        if value is None:
            fill, edge = NO_DATA, NO_DATA_EDGE
            tip = f"{country['name']}: no data"
        else:
            t = (value - v_min) / v_span
            fill, edge = _ramp_hex(t), BG
            tip = f"{country['name']}: {value:.1f}"
        parts.append(
            f'<path class="country" tabindex="0" d="{path_d}" fill="{fill}" '
            f'stroke="{edge}" stroke-width="0.4"><title>{xml_escape(tip)}</title></path>'
        )

    # ---- legend: ramp swatches + low/high labels ----
    ly = height - 16.0
    lx0 = side_margin
    parts.append(f'<text x="{lx0:.1f}" y="{ly:.1f}" font-size="11" fill="{SECONDARY}">{v_min:.0f}</text>')
    swatch_x = lx0 + 26.0
    n_swatches = 8
    for i in range(n_swatches):
        t = i / (n_swatches - 1)
        parts.append(f'<rect x="{swatch_x + i * 16:.1f}" y="{ly - 11:.1f}" width="14" height="12" fill="{_ramp_hex(t)}"/>')
    parts.append(
        f'<text x="{swatch_x + n_swatches * 16 + 6:.1f}" y="{ly:.1f}" font-size="11" '
        f'fill="{SECONDARY}">{v_max:.0f}</text>'
    )
    swatch_end = swatch_x + n_swatches * 16 + 40
    parts.append(f'<rect x="{swatch_end:.1f}" y="{ly - 11:.1f}" width="14" height="12" fill="{NO_DATA}" stroke="{NO_DATA_EDGE}"/>')
    parts.append(f'<text x="{swatch_end + 20:.1f}" y="{ly:.1f}" font-size="11" fill="{SECONDARY}">No data</text>')

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_choropleth(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Global Exposure Index, by Country",
    subtitle: str = "Higher = greater exposure · synthetic demo data · no data in grey",
    width: int = 745,
    height: int = 420,
    mode: str = "self-contained",
    accessibility: str = "universal",
) -> Path:
    """Render a hand-authored choropleth map and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``id`` (str, ISO-3166-1 numeric country code) and
        ``value`` (float). Defaults to DEMO_DATA (a synthetic global
        exposure index).
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/choropleth.svg``.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    mode, accessibility : str
        Forwarded to :func:`build_svg`.

    Returns
    -------
    Path
        Absolute path to the written SVG file.

    Examples
    --------
    >>> p = make_choropleth()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility)
    dest = Path(out) if out else svg_example_path(__file__, "choropleth")
    return write_svg(dest, svg)


def main() -> None:
    render_cli(__file__, "choropleth", build_svg, description="Generate a world choropleth map.")


if __name__ == "__main__":
    main()
