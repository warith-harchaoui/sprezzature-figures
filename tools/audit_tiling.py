#!/usr/bin/env python3
"""
audit_tiling — find lattices whose cells cover each other.

Reading the generators for this defect does not work: the pixels-per-unit
factor is spelled a different way in every file, and the bug is not a
misspelling anyway, it is a geometric claim that the source never states. So
this measures the claim in the *output* instead.

A tiling is a set of congruent cells that partition a region: neighbours share
edges and nothing else. When a lattice is laid out in data units but painted
with one pixel radius, the cells keep their shape and lose their spacing, and
every cell swallows part of its neighbours. That shows up as overlap area
between congruent polygons, which is what this measures.

Marks that are *supposed* to overlap -- scatter points, beeswarm dots, Venn
circles -- will also score here. The number is evidence, not a verdict: read
the figure the number points at.

Calibration: the hexbin generator, before its lattice was moved into pixel
space, scored 64% overlap; after, 0.0%. Every genuine tiling in the
catalogue -- heatmap, waffle, treemap, voronoi, the hex maps, the two
rasters -- now scores under 0.2%.

Usage:
    python tools/audit_tiling.py assets/*.svg

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import math
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import List, Tuple

Point = Tuple[float, float]
Polygon = List[Point]

# A closed path of straight segments: "M x,y L x,y … Z", the shape every
# hand-authored cell in this stack is written as.
_PATH = re.compile(r'\sd="M\s*([-\d.,\s L]+?)\s*Z"', re.I)
_RECT = re.compile(
    r'<rect\b(?=[^>]*\bx="([-\d.]+)")(?=[^>]*\by="([-\d.]+)")'
    r'(?=[^>]*\bwidth="([\d.]+)")(?=[^>]*\bheight="([\d.]+)")[^>]*>'
)


def _polygons(svg: str) -> List[Polygon]:
    """Every closed straight-edged shape in the document, as a point list."""
    out: List[Polygon] = []
    for body in _PATH.findall(svg):
        pts: Polygon = []
        for token in re.split(r"[\sL]+", body.strip()):
            if not token:
                continue
            try:
                sx, sy = token.split(",")
                pts.append((float(sx), float(sy)))
            except ValueError:
                pts = []
                break
        if len(pts) >= 3:
            out.append(pts)
    for sx, sy, sw, sh in _RECT.findall(svg):
        x, y, w, h = float(sx), float(sy), float(sw), float(sh)
        out.append([(x, y), (x + w, y), (x + w, y + h), (x, y + h)])
    return out


def _area(poly: Polygon) -> float:
    """Shoelace area, unsigned."""
    total = 0.0
    for i in range(len(poly)):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % len(poly)]
        total += x0 * y1 - x1 * y0
    return abs(total) / 2.0


def _clip(subject: Polygon, clipper: Polygon) -> Polygon:
    """Sutherland-Hodgman: the part of ``subject`` inside convex ``clipper``."""
    # "Inside" is the side the clipper's own centre falls on. Deciding it from
    # the signed area instead would need the winding convention, which flips
    # in SVG's y-down frame; the centre of a convex polygon never does.
    cx = sum(p[0] for p in clipper) / len(clipper)
    cy = sum(p[1] for p in clipper) / len(clipper)

    output = subject
    for i in range(len(clipper)):
        if not output:
            return []
        ax, ay = clipper[i]
        bx, by = clipper[(i + 1) % len(clipper)]
        ex, ey = bx - ax, by - ay
        sign = 1.0 if ex * (cy - ay) - ey * (cx - ax) >= 0 else -1.0

        def edge(p: Point) -> float:
            return sign * (ex * (p[1] - ay) - ey * (p[0] - ax))

        def cross(p: Point, q: Point) -> Point:
            dx, dy = q[0] - p[0], q[1] - p[1]
            denominator = edge(q) - edge(p)
            if abs(denominator) < 1e-12:
                return q
            s = -edge(p) / denominator
            return (p[0] + dx * s, p[1] + dy * s)

        clipped: Polygon = []
        for j in range(len(output)):
            current, previous = output[j], output[j - 1]
            if edge(current) >= -1e-9:
                if edge(previous) < -1e-9:
                    clipped.append(cross(previous, current))
                clipped.append(current)
            elif edge(previous) >= -1e-9:
                clipped.append(cross(previous, current))
        output = clipped
    return output


def _bbox(poly: Polygon) -> Tuple[float, float, float, float]:
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def audit(path: Path) -> None:
    polys = _polygons(path.read_text(encoding="utf-8"))
    if len(polys) < 12:
        print(f"{path.stem:26} — {len(polys)} formes, pas une trame")
        return

    # Congruent cells: same vertex count, same area to 2%. A lattice is the
    # largest such family; anything smaller is chrome (legend swatches, axes).
    families = defaultdict(list)
    for poly in polys:
        a = _area(poly)
        if a < 4.0:
            continue
        families[(len(poly), round(math.log(a) / math.log(1.02)))].append(poly)
    if not families:
        print(f"{path.stem:26} — aucune famille de cellules")
        return
    cells = max(families.values(), key=len)
    if len(cells) < 12:
        print(f"{path.stem:26} — plus grande famille = {len(cells)} cellules, trop peu")
        return

    # Only near neighbours can overlap; bucket by a cell-sized grid.
    typical = sorted(_area(c) for c in cells)[len(cells) // 2]
    step = max(1.0, typical**0.5)
    buckets = defaultdict(list)
    for index, cell in enumerate(cells):
        x0, y0, x1, y1 = _bbox(cell)
        for gx in range(int(x0 // step), int(x1 // step) + 1):
            for gy in range(int(y0 // step), int(y1 // step) + 1):
                buckets[(gx, gy)].append(index)

    pairs = set()
    for members in buckets.values():
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                pairs.add((min(a, b), max(a, b)))

    overlap = 0.0
    worst = 0.0
    for a, b in pairs:
        piece = _clip(cells[a], cells[b])
        shared = _area(piece) if len(piece) >= 3 else 0.0
        overlap += shared
        worst = max(worst, shared / typical)
    ratio = overlap / (typical * len(cells))

    verdict = "PAVAGE SAIN" if ratio < 0.02 else "RECOUVREMENT" if ratio < 0.15 else "CASSÉ"
    print(
        f"{path.stem:26} {len(cells):5} cellules  recouvrement {ratio * 100:6.1f} %"
        f"  pire paire {worst * 100:5.1f} %   {verdict}"
    )


if __name__ == "__main__":
    for argument in sys.argv[1:]:
        audit(Path(argument))
