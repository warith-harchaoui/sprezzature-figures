#!/usr/bin/env python3
"""
_worldmap — the world basemap the glyph-on-a-map figures share.

A *glyph map* puts a small chart at a place: a bar group, a pie, a
proportional circle. Whatever the glyph, the substrate underneath is always
the same job — decode the vendored land silhouette, project it equal-area,
fit it to a viewport, and hand back a function that turns a ``(lon, lat)``
into a pixel. Before this module that job was written out twice, inside
``make_spike-map.py`` and ``make_hexbin-map.py``, and the three glyph maps
added next to them would have made it five.

Equal area is not a detail here. A glyph map asks the reader to compare marks
across the sheet, and a projection that inflates the high latitudes inflates
whatever sits on them; Greenland-sized distortion turns an honest circle into
a lie about the north. The projection is **Equal Earth** (Šavrič, Patterson &
Jenny 2018), closed-form, equal-area, with enough globe-like curvature to read
as a world map rather than a rectangle. No ``pyproj``: the forward formula is
four polynomial constants, and the inverse is never needed.

The land comes from ``assets/geo/countries-110m.json``, the vendored
Natural Earth 1:110m TopoJSON. The ``land`` object is a single fused
silhouette, so no internal borders clutter the backdrop under the glyphs.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Callable, List, Sequence, Tuple

#: One closed ring of ``(lon, lat)`` vertices, in degrees.
Ring = List[Tuple[float, float]]

#: Polynomial constants of the Equal Earth forward projection, from the
#: original paper. They are the projection; nothing here is tunable.
_A1, _A2, _A3, _A4 = 1.340264, -0.081106, 0.000893, 0.003796
_M = math.sqrt(3.0) / 2.0


def load_land_rings() -> List[Ring]:
    """Decode the vendored world land silhouette from TopoJSON.

    The minimal TopoJSON contract of ``countries-110m.json``: quantised,
    delta-encoded arcs plus a ``scale`` / ``translate`` transform, stitched
    into closed lon/lat rings.

    Returns
    -------
    list of Ring
        One list of ``(lon, lat)`` tuples, in degrees, per land ring.
    """
    geo_path = Path(__file__).resolve().parent.parent / "assets" / "geo" / "countries-110m.json"
    topo = json.loads(geo_path.read_text(encoding="utf-8"))
    scale = topo["transform"]["scale"]
    translate = topo["transform"]["translate"]
    raw_arcs = topo["arcs"]

    def decode_arc(index: int) -> List[Tuple[float, float]]:
        # A negative index means the arc is traversed in reverse (~index).
        reverse = index < 0
        arc = raw_arcs[~index if reverse else index]
        pts: List[Tuple[float, float]] = []
        x = y = 0
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append((x * scale[0] + translate[0], y * scale[1] + translate[1]))
        return pts[::-1] if reverse else pts

    def stitch(arc_indices: Sequence[int]) -> Ring:
        ring: Ring = []
        for j, idx in enumerate(arc_indices):
            pts = decode_arc(idx)
            ring.extend(pts if j == 0 else pts[1:])
        return ring

    rings: List[Ring] = []
    for geom in topo["objects"]["land"]["geometries"]:
        if geom["type"] == "Polygon":
            for part in geom["arcs"]:
                rings.append(stitch(part))
        elif geom["type"] == "MultiPolygon":
            for poly in geom["arcs"]:
                for part in poly:
                    rings.append(stitch(part))
    return rings


def equal_earth(lon: float, lat: float, *, central_meridian: float = 0.0) -> Tuple[float, float]:
    """Project ``(lon, lat)`` in degrees to Equal Earth planar ``(x, y)``.

    Parameters
    ----------
    lon, lat : float
        Longitude and latitude in degrees.
    central_meridian : float, optional
        Longitude placed at the middle of the map, in degrees. The default
        0 gives the Atlantic-centred world everyone expects; a hexbin map of
        the Pacific rim wants 160, so the Ring of Fire reads as one arc
        instead of being cut in half at both edges. Longitudes are wrapped
        into ``[-180, 180]`` about it.

    Returns
    -------
    tuple of float
        Planar ``(x, y)`` in projection units, ``y`` pointing up. Callers
        fit these to a viewport with :func:`fit_to_viewport`.
    """
    if central_meridian:
        lon = ((lon - central_meridian + 180.0) % 360.0) - 180.0
    lam = math.radians(lon)
    phi = math.radians(lat)
    theta = math.asin(_M * math.sin(phi))  # parametric latitude
    t2 = theta * theta
    t6 = t2 * t2 * t2
    x = (
        2.0
        * math.sqrt(3.0)
        * lam
        * math.cos(theta)
        / (3.0 * (_A1 + 3.0 * _A2 * t2 + t6 * (7.0 * _A3 + 9.0 * _A4 * t2)))
    )
    y = theta * (_A1 + _A2 * t2 + t6 * (_A3 + _A4 * t2))
    return x, y


def fit_to_viewport(
    rings: Sequence[Ring],
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    pad: float = 8.0,
    central_meridian: float = 0.0,
) -> Callable[[float, float], Tuple[float, float]]:
    """Return a ``(lon, lat) -> (px, py)`` projector fitted to one viewport.

    The scale is uniform on both axes, so the equal-area property survives
    the fit: squashing one axis to fill the box would undo the whole reason
    the projection was chosen. The drawn map is centred in whatever room is
    left over.

    Parameters
    ----------
    rings : sequence of Ring
        The geometry to fit, normally the output of :func:`load_land_rings`.
    x, y, width, height : float
        The viewport rectangle, in user-space pixels.
    pad : float, optional
        Inner margin kept on every side, in pixels.
    central_meridian : float, optional
        Forwarded to :func:`equal_earth`, and used for the fit as well as
        for the returned projector -- fitting on one centring and drawing on
        another would silently shift the whole map.

    Returns
    -------
    callable
        ``project(lon, lat) -> (px, py)`` with screen ``y`` pointing down.
    """
    projected = [
        equal_earth(lon, lat, central_meridian=central_meridian)
        for ring in rings
        for lon, lat in ring
    ]
    min_px = min(p[0] for p in projected)
    max_px = max(p[0] for p in projected)
    min_py = min(p[1] for p in projected)
    max_py = max(p[1] for p in projected)
    span_x = max_px - min_px
    span_y = max_py - min_py
    scale = min((width - 2 * pad) / span_x, (height - 2 * pad) / span_y)
    offset_x = x + (width - span_x * scale) / 2.0
    offset_y = y + (height - span_y * scale) / 2.0

    def project(lon: float, lat: float) -> Tuple[float, float]:
        px, py = equal_earth(lon, lat, central_meridian=central_meridian)
        # Screen y grows downward; the projection's grows up.
        return (
            offset_x + (px - min_px) * scale,
            offset_y + span_y * scale - (py - min_py) * scale,
        )

    return project


def land_path(
    rings: Sequence[Ring],
    project: Callable[[float, float], Tuple[float, float]],
    *,
    min_vertices: int = 4,
) -> str:
    """Build the ``d`` attribute of the whole land silhouette, as one path.

    One path for every ring, rather than one path per ring, because the
    silhouette is backdrop: it carries no data, takes no hover, and needs no
    per-ring identity. A single element is also what keeps the document small
    enough to inline in a page.

    Parameters
    ----------
    rings : sequence of Ring
        Land rings in ``(lon, lat)`` degrees.
    project : callable
        A projector from :func:`fit_to_viewport`.
    min_vertices : int, optional
        Rings with fewer vertices than this are dropped. At 1:110m these are
        specks a pixel wide; drawing them costs bytes and shows nothing.

    Returns
    -------
    str
        The concatenated ``M … L … Z`` subpaths.
    """
    parts: List[str] = []
    for ring in rings:
        if len(ring) < min_vertices:
            continue
        pts = [project(lon, lat) for lon, lat in ring]
        head = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
        tail = "".join(f"L{px:.1f},{py:.1f}" for px, py in pts[1:])
        parts.append(f"{head}{tail}Z")
    return "".join(parts)


def graticule_paths(
    project: Callable[[float, float], Tuple[float, float]],
    *,
    lon_step: int = 30,
    lat_step: int = 30,
    sample: int = 2,
) -> List[str]:
    """Build meridian and parallel paths for a faint reference grid.

    Equal Earth bends both families of lines, so a graticule drawn as
    straight segments would sit visibly off the land it is supposed to
    register against. Each line is therefore sampled every `sample` degrees
    and projected point by point.

    Parameters
    ----------
    project : callable
        A projector from :func:`fit_to_viewport`.
    lon_step, lat_step : int, optional
        Spacing of meridians and parallels, in degrees.
    sample : int, optional
        Sampling step along each line, in degrees.

    Returns
    -------
    list of str
        One ``d`` attribute per graticule line.
    """
    lines: List[str] = []
    for lon in range(-180, 181, lon_step):
        pts = [project(lon, lat) for lat in range(-90, 91, sample)]
        lines.append(
            f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
            + "".join(f"L{px:.1f},{py:.1f}" for px, py in pts[1:])
        )
    for lat in range(-60, 61, lat_step):
        pts = [project(lon, lat) for lon in range(-180, 181, sample)]
        lines.append(
            f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
            + "".join(f"L{px:.1f},{py:.1f}" for px, py in pts[1:])
        )
    return lines
