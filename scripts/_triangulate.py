#!/usr/bin/env python3
"""
_triangulate — a Delaunay triangulation, shared by the irregular-grid figures.

Given scattered points in the plane, return the triangles that join them
without any point falling inside another triangle's circumcircle. That
property is what makes a Delaunay triangulation the right default: it
avoids the long thin slivers a naive triangulation produces, and a
sliver is where an interpolated surface or contour goes visibly wrong.

Written out rather than taken from a dependency because this project
draws its own geometry, and because the algorithm is short: Bowyer and
Watson's incremental method, which inserts points one at a time, deletes
every triangle whose circumcircle contains the new point, and re-fills
the hole from its boundary.

Callers that already hold a triangulation -- from a mesh, from a solver,
from a previous run -- should pass it rather than recompute it. This is
the fallback for the common case where a caller has points and nothing
else.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

#: Triangles are returned as index triples into the caller's point list.
Triangle = Tuple[int, int, int]

#: Points closer than this count as the same point. Duplicates break the
#: circumcircle test by making a triangle degenerate.
_SAME_POINT = 1e-12


def _circumcircle(
    a: Tuple[float, float], b: Tuple[float, float], c: Tuple[float, float]
) -> Tuple[float, float, float]:
    """Centre and squared radius of the circle through three points.

    Parameters
    ----------
    a, b, c : tuple of float
        The triangle's corners.

    Returns
    -------
    tuple of float
        ``(cx, cy, r2)``. A degenerate triangle -- three collinear
        points -- returns an infinite radius, which makes the
        containment test below always true and so deletes the triangle
        on the next insertion rather than leaving a zero-area sliver in
        the mesh.
    """
    ax, ay = a
    bx, by = b
    cx, cy = c
    d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-18:
        return (0.0, 0.0, float("inf"))
    a2 = ax * ax + ay * ay
    b2 = bx * bx + by * by
    c2 = cx * cx + cy * cy
    ux = (a2 * (by - cy) + b2 * (cy - ay) + c2 * (ay - by)) / d
    uy = (a2 * (cx - bx) + b2 * (ax - cx) + c2 * (bx - ax)) / d
    return (ux, uy, (ux - ax) ** 2 + (uy - ay) ** 2)


def triangulate(points: Sequence[Tuple[float, float]]) -> List[Triangle]:
    """Delaunay triangles over `points`, as index triples.

    Bowyer-Watson: start from one triangle big enough to contain
    everything, insert each point in turn, remove the triangles whose
    circumcircle it falls inside, and stitch the resulting hole back up
    to the new point. Finish by dropping every triangle that still
    touches a corner of the starting triangle, which is scaffolding
    rather than data.

    Parameters
    ----------
    points : sequence of tuple of float
        The points, as ``(x, y)``. Fewer than three, or all collinear,
        gives no triangles.

    Returns
    -------
    list of tuple of int
        Index triples into `points`, each in no particular winding.

    Examples
    --------
    >>> triangles = triangulate([(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)])
    >>> len(triangles)
    1
    >>> sorted(triangles[0])
    [0, 1, 2]
    """
    if len(points) < 3:
        return []

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    low_x, high_x = min(xs), max(xs)
    low_y, high_y = min(ys), max(ys)
    span = max(high_x - low_x, high_y - low_y) or 1.0
    mid_x = (low_x + high_x) / 2.0
    mid_y = (low_y + high_y) / 2.0

    # The super-triangle: big enough that every real point falls inside
    # it, so no real point ever sits outside the mesh being built.
    working: List[Tuple[float, float]] = list(points) + [
        (mid_x - 20.0 * span, mid_y - span),
        (mid_x, mid_y + 20.0 * span),
        (mid_x + 20.0 * span, mid_y - span),
    ]
    first = len(points)
    mesh: List[Triangle] = [(first, first + 1, first + 2)]

    for index in range(len(points)):
        point = working[index]
        doomed: List[Triangle] = []
        for triangle in mesh:
            cx, cy, r2 = _circumcircle(*(working[corner] for corner in triangle))
            if (point[0] - cx) ** 2 + (point[1] - cy) ** 2 <= r2 + _SAME_POINT:
                doomed.append(triangle)
        if not doomed:
            continue

        # The hole's boundary: edges belonging to exactly one doomed
        # triangle. Shared edges are interior and get stitched over.
        seen: dict[Tuple[int, int], int] = {}
        for triangle in doomed:
            for edge in (
                (triangle[0], triangle[1]),
                (triangle[1], triangle[2]),
                (triangle[2], triangle[0]),
            ):
                key = (min(edge), max(edge))
                seen[key] = seen.get(key, 0) + 1
        mesh = [triangle for triangle in mesh if triangle not in doomed]
        for (left, right), count in seen.items():
            if count == 1:
                mesh.append((left, right, index))

    return [triangle for triangle in mesh if all(corner < first for corner in triangle)]


def edges_of(triangles: Sequence[Triangle]) -> List[Tuple[int, int]]:
    """Every distinct edge of `triangles`, each as a sorted index pair.

    Parameters
    ----------
    triangles : sequence of tuple of int
        Index triples, as returned by :func:`triangulate`.

    Returns
    -------
    list of tuple of int
        Each edge once, in the order first met.

    Examples
    --------
    >>> edges_of([(0, 1, 2)])
    [(0, 1), (1, 2), (0, 2)]
    """
    found: List[Tuple[int, int]] = []
    known = set()
    for triangle in triangles:
        for edge in (
            (triangle[0], triangle[1]),
            (triangle[1], triangle[2]),
            (triangle[2], triangle[0]),
        ):
            key = (min(edge), max(edge))
            if key not in known:
                known.add(key)
                found.append(key)
    return found
