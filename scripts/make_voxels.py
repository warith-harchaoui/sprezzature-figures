#!/usr/bin/env python3
"""
make_voxels — filled cells of a three-dimensional grid, counting what they hide.

A value measured on every cell of an x by y by z lattice: a grid search
over three hyper-parameters, an occupancy map, a three-way histogram.
Cells at or above a `threshold` are drawn as solid blocks, and the shape
they make is the answer.

Where the usual voxel plot goes wrong
-------------------------------------
* **It never says what it is hiding.** A solid block is opaque, so the
  interior of the volume is simply not in the picture, and nothing on the
  figure admits it. Every filled cell is tested against the ones in front
  of it here, and the count that cannot be seen is written in the chrome.
  A figure that hides a third of its data should say which third.
* **It offers no way to look inside.** The standard remedy for an opaque
  volume is to cut it open, and almost no implementation ships one.
  ``cut`` removes the octant or the half nearest the camera, which is
  what a reader reaches for the moment the count above is not zero.
* **The blocks are flush, so the volume reads as one lump.** Cells drawn
  edge to edge merge into a silhouette with no internal structure.
  `gap` shrinks each cell inside its own slot, which costs nothing and
  buys back the lattice.
* **Depth order is left to the renderer.** There isn't one: SVG paints
  in document order. The cells are sorted back to front by their own
  centre, their hidden faces are culled by screen-space winding, and the
  three face orientations are shaded apart so the form reads as a solid
  rather than as a pile of lozenges.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _project3d import project as project3d  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _style import BG, GRIDLINE, INK, SECONDARY, load_palette  # noqa: E402
from _textfit import fit_font_size  # noqa: E402
from _svg import (  # noqa: E402
    fmt_measured,
    fmt_number,
    foreground_tip_css,
    hex_to_rgb,
    svg_open,
    tooltip_bubble,
    viridis,
    wrap_no_orphan,
    xml_escape,
)
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

#: The demo's grid: five learning rates, four depths, four subsample
#: fractions. Eighty cells is what a real three-way search costs and few
#: enough that the kit's data.csv is a file a person can read.
_RATES = (0.01, 0.02, 0.05, 0.1, 0.2)
_DEPTHS = (3, 5, 7, 9)
_SUBSAMPLES = (0.6, 0.7, 0.85, 1.0)


def _search() -> List[Dict[str, Any]]:
    """A three-way grid search whose best cell sits on an edge of the grid.

    Deliberately so. The most useful thing a grid search can tell you is
    that it was drawn too small, and it tells you by putting its optimum
    against a wall: the score is still climbing as the learning rate
    falls, and 0.01 was simply the smallest rate anyone tried. A plot
    that does not make that visible lets a team ship the edge of its own
    search space as a finding.
    """
    rows: List[Dict[str, Any]] = []
    for rate in _RATES:
        for depth in _DEPTHS:
            for subsample in _SUBSAMPLES:
                # Still improving as the rate falls: the ridge runs off
                # the low-rate face of the cube.
                from_rate = 0.055 * math.log10(0.2 / rate)
                # A genuine interior optimum on depth, near 6.
                from_depth = -0.0034 * (depth - 6.2) ** 2
                # Mild, saturating gain from more rows per tree.
                from_rows = 0.021 * (subsample - 0.6)
                # Deep trees on a small subsample overfit: the one
                # interaction that stops the volume being a stack of
                # independent slabs.
                interaction = -0.040 * max(0.0, depth - 6) * max(0.0, 0.8 - subsample)
                rows.append(
                    {
                        "learning_rate": rate,
                        "max_depth": depth,
                        "subsample": subsample,
                        "auc": round(0.806 + from_rate + from_depth + from_rows + interaction, 4),
                    }
                )
    return rows


DEMO_DATA: List[Dict[str, Any]] = _search()

#: The eight corners of a unit cell, as offsets in ``(i, j, k)``.
_CORNERS: Tuple[Tuple[int, int, int], ...] = (
    (0, 0, 0),
    (1, 0, 0),
    (1, 1, 0),
    (0, 1, 0),
    (0, 0, 1),
    (1, 0, 1),
    (1, 1, 1),
    (0, 1, 1),
)

#: The six faces of a cell, as corner indices wound consistently, with
#: the lightness each orientation is shaded by. Two faces of a pair are
#: never visible at once, so one lightness per axis is enough.
_FACES: Tuple[Tuple[Tuple[int, int, int, int], float], ...] = (
    ((0, 3, 2, 1), 0.70),  # bottom, normal -z
    ((4, 5, 6, 7), 1.00),  # top, normal +z
    ((0, 1, 5, 4), 0.86),  # normal -y
    ((3, 7, 6, 2), 0.86),  # normal +y
    ((0, 4, 7, 3), 0.60),  # normal -x
    ((1, 2, 6, 5), 0.60),  # normal +x
)

#: Sign of the screen-space shoelace area of a camera-facing face. Every
#: entry in :data:`_FACES` is wound outward by the right-hand rule, and
#: the projection flips y, so an outward face comes out clockwise on
#: screen -- which this formula reports as positive. Three faces of a
#: cube pass at a time, which is exactly the three a viewer can see.
_FACING = 1.0


def _screen_area(quad: Sequence[Tuple[float, float]]) -> float:
    """Twice the signed area of a projected face, in screen coordinates.

    Parameters
    ----------
    quad : sequence of tuple of float
        The four projected corners, in the order :data:`_FACES` gives.

    Returns
    -------
    float
        Positive when the face turns toward the camera.

    Examples
    --------
    >>> _screen_area([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)])
    1.0
    """
    total = 0.0
    for index in range(len(quad)):
        ax, ay = quad[index]
        bx, by = quad[(index + 1) % len(quad)]
        total += ax * by - bx * ay
    return total / 2.0


def _shade(colour: str, lightness: float) -> str:
    """`colour` moved toward white or black by `lightness`.

    Parameters
    ----------
    colour : str
        A ``#rrggbb`` base colour, which here carries the cell's value.
    lightness : float
        ``1.0`` leaves the colour alone; below that darkens toward black.

    Returns
    -------
    str
        The shaded colour, as ``#rrggbb``.

    Examples
    --------
    >>> _shade("#808080", 1.0)
    '#808080'
    >>> _shade("#808080", 0.5)
    '#404040'
    """
    red, green, blue = hex_to_rgb(colour)
    return "#{:02x}{:02x}{:02x}".format(
        max(0, min(255, int(round(red * lightness)))),
        max(0, min(255, int(round(green * lightness)))),
        max(0, min(255, int(round(blue * lightness)))),
    )


def _inside(point: Tuple[float, float], quad: Sequence[Tuple[float, float]]) -> bool:
    """Whether `point` falls inside the convex projected `quad`.

    Parameters
    ----------
    point : tuple of float
        The pixel to test.
    quad : sequence of tuple of float
        The polygon's corners in order. A projected cell face is always
        convex, so the same-side-of-every-edge test is exact.

    Returns
    -------
    bool
        True when the point is inside or on the boundary.
    """
    sign = 0
    count = len(quad)
    for index in range(count):
        ax, ay = quad[index]
        bx, by = quad[(index + 1) % count]
        cross = (bx - ax) * (point[1] - ay) - (by - ay) * (point[0] - ax)
        if cross > 1e-9:
            if sign < 0:
                return False
            sign = 1
        elif cross < -1e-9:
            if sign > 0:
                return False
            sign = -1
    return True


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "The best cell is against a wall, so the search stopped early",
    subtitle: str = "A three-way grid search. Cells at or above the threshold are filled; the rest are left out.",
    width: int = 790,
    height: int = 620,
    x: str = "learning_rate",
    y: str = "max_depth",
    z: str = "subsample",
    value: str = "auc",
    threshold: Optional[float] = None,
    keep_share: float = 0.45,
    gap: float = 0.14,
    cut: str = "none",
    elev: float = 24.0,
    azim: float = -52.0,
    zoom: float = 0.98,
    show_edges: bool = True,
    show_box: bool = True,
    mark_best: bool = True,
    x_label: Optional[str] = None,
    y_label: Optional[str] = None,
    z_label: Optional[str] = None,
    value_label: Optional[str] = None,
    summary: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full voxel SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        One row per cell of the lattice, with keys named by `x`, `y`, `z`
        and `value`. Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    x, y, z : str
        Which keys hold the three grid coordinates. Their distinct values,
        sorted, become the lattice.
    value : str
        Which key holds the measured value.
    threshold : float or None
        Cells at or above this are filled, the rest left out. ``None``
        derives it so that `keep_share` of the cells survive.
    keep_share : float
        The share of cells to keep when `threshold` is ``None``.
    gap : float
        How much of its own slot each cell gives back, as a fraction.
        Zero draws the cells flush and the volume reads as one lump.
    cut : str
        ``"none"``, ``"corner"`` to drop the octant nearest the camera,
        or ``"half"`` to drop the nearer half along the axis most facing
        it. The remedy for a volume that hides its own interior.
    elev, azim : float
        Camera elevation and azimuth, in degrees.
    zoom : float
        Multiplier on the fit scale.
    show_edges : bool
        Outline each cell's visible faces.
    show_box : bool
        Draw the lattice's bounding box.
    mark_best : bool
        Call out the highest-valued cell and say whether it sits on a
        face of the grid.
    x_label, y_label, z_label, value_label : str or None
        Axis titles and the name of the value. ``None`` uses the column
        names.
    summary : str or None
        The chrome block. ``None`` composes it.
    finding : str or None
        The closing lines under the plot. ``None`` composes them.
    mode, accessibility : str, optional
        Forwarded to :func:`_interactive.fullscreen_control` /
        :func:`_style.load_palette`.
    theme : str, optional
        Visual theme: ``"corporate"`` (default, Roboto) or ``"academic"``
        (LaTeX-style Latin Modern).

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    if cut not in ("none", "corner", "half"):
        raise ValueError(f"cut is 'none', 'corner' or 'half', got {cut!r}")

    rows = list(data if data else DEMO_DATA)
    mono_family = mono_stack_for_theme(theme)
    load_palette(accessibility, theme=theme)

    xs = sorted({row[x] for row in rows}, key=lambda v: (float(v), str(v)))
    ys = sorted({row[y] for row in rows}, key=lambda v: (float(v), str(v)))
    zs = sorted({row[z] for row in rows}, key=lambda v: (float(v), str(v)))
    nx, ny, nz = len(xs), len(ys), len(zs)
    at_x = {v: i for i, v in enumerate(xs)}
    at_y = {v: i for i, v in enumerate(ys)}
    at_z = {v: i for i, v in enumerate(zs)}

    cells: Dict[Tuple[int, int, int], float] = {}
    for row in rows:
        cells[(at_x[row[x]], at_y[row[y]], at_z[row[z]])] = float(row[value])
    values = sorted(cells.values())
    v_lo, v_hi = values[0], values[-1]
    scale_of = max(v_hi - v_lo, 1e-12)

    cut_at = threshold
    if cut_at is None:
        keep = max(1, min(len(values), int(round(keep_share * len(values)))))
        cut_at = values[len(values) - keep]
    filled = {key: val for key, val in cells.items() if val >= cut_at}

    best_key = max(cells, key=lambda k: cells[k])
    on_face = best_key[0] in (0, nx - 1) or best_key[1] in (0, ny - 1) or best_key[2] in (0, nz - 1)

    # ---- the cutaway, decided from where the camera actually is ----
    # Which octant is nearest is a fact about the camera, not about the
    # data, so it is read off the projected corners rather than fixed.
    box_x = np.array([0.0, float(nx)])
    corner_px, corner_py, corner_depth = project3d(
        np.array([c[0] for c in _CORNERS], dtype=float) * nx,
        np.array([c[1] for c in _CORNERS], dtype=float) * ny,
        np.array([c[2] for c in _CORNERS], dtype=float) * nz,
        elev_deg=elev,
        azim_deg=azim,
        plot_w=1.0,
        plot_h=1.0,
        cx=0.0,
        cy=0.0,
    )
    near_corner = _CORNERS[int(np.argmax(corner_depth))]
    removed = 0
    if cut != "none" and filled:
        # Halved against what is actually drawn, not against the whole
        # lattice: a filled region that sits away from the camera's own
        # octant would otherwise make `cut` a no-op, and an option that
        # silently does nothing is worse than no option.
        middles = [
            (min(key[axis] for key in filled) + max(key[axis] for key in filled) + 1) / 2.0
            for axis in range(3)
        ]

        def in_near_half(key: Tuple[int, int, int], axis: int) -> bool:
            return key[axis] >= middles[axis] if near_corner[axis] else key[axis] < middles[axis]

        if cut == "corner":
            doomed = {key for key in filled if all(in_near_half(key, axis) for axis in range(3))}
        else:
            # The axis the camera faces most squarely is the one whose
            # halves separate cleanly on screen; cutting any other one
            # takes a slab out of the side rather than off the front.
            spread = [
                abs(float(corner_depth[1]) - float(corner_depth[0])),
                abs(float(corner_depth[3]) - float(corner_depth[0])),
                abs(float(corner_depth[4]) - float(corner_depth[0])),
            ]
            axis = int(max(range(3), key=lambda a: spread[a]))
            doomed = {key for key in filled if in_near_half(key, axis)}
        removed = len(doomed)
        filled = {key: val for key, val in filled.items() if key not in doomed}
    del box_x

    # ---- how much room the chrome wants, before the map is placed ----
    # How many characters a line of chrome may hold, derived from the
    # canvas rather than guessed: a magic 104 fits one width and spills
    # off every narrower one, and a line of chrome that runs off the
    # page is worse than no chrome.
    plot_x = 56.0
    # The academic theme's serif runs about a seventh wider than the
    # metric model, which is built on the sans stack. One allowance,
    # applied to every text budget, rather than a different magic number
    # per block.
    wide = 1.15 if theme == "academic" else 1.0
    mono_chars = max(24, int((width - plot_x - 24.0) / (7.8 * wide)))
    prose_chars = max(24, int((width - plot_x - 24.0) / (7.2 * wide)))
    cut_said = {
        "none": [],
        "corner": [f"the octant nearest the camera cut away, {removed} cells"],
        "half": [f"the nearer half cut away, {removed} cells"],
    }[cut]
    subtitle_lines = wrap_no_orphan(subtitle, prose_chars)[:2]
    # The lines are composed below, once the occlusion is known; their
    # *count* is known now, and the count is all the layout needs.
    chrome_count = (
        len(wrap_no_orphan(summary, mono_chars)) if summary is not None else 3 + len(cut_said)
    )
    if finding is not None:
        found_count = len(wrap_no_orphan(finding, mono_chars))
    elif mark_best:
        found_count = 2 if on_face else 1
    else:
        found_count = 0

    # ---- geometry ----
    chrome_top = 72.0 + len(subtitle_lines) * 18.0 + 22.0
    plot_y = chrome_top + chrome_count * 17.0 + 24.0
    plot_h = height - plot_y - (46.0 + found_count * 17.0)
    plot_w = width - plot_x - 158.0
    span = float(max(nx, ny, nz))

    def model(i: float, j: float, k: float) -> Tuple[float, float, float]:
        """Grid coordinates to a model-space box centred on the origin.

        The longest axis is mapped to ``[-1, 1]``; the other two keep
        their proportion, so a 5 by 4 by 4 grid stays a 5 by 4 by 4 box
        rather than being squared off into a cube it is not.
        """
        return (2.0 * i / span - nx / span, 2.0 * j / span - ny / span, 2.0 * k / span - nz / span)

    def project_many(
        points: Sequence[Tuple[float, float, float]],
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        arr = np.array(points, dtype=float)
        return project3d(
            arr[:, 0],
            arr[:, 1],
            arr[:, 2],
            elev_deg=elev,
            azim_deg=azim,
            plot_w=plot_w,
            plot_h=plot_h,
            cx=plot_x + plot_w / 2.0,
            cy=plot_y + plot_h / 2.0,
            zoom=zoom,
            fit="box",
        )

    inset = max(0.0, min(0.45, gap / 2.0))
    order: List[Tuple[int, int, int]] = []
    silhouettes: Dict[Tuple[int, int, int], List[List[Tuple[float, float]]]] = {}
    centres: Dict[Tuple[int, int, int], Tuple[float, float]] = {}
    depths: Dict[Tuple[int, int, int], float] = {}
    corners_px: Dict[Tuple[int, int, int], List[Tuple[float, float]]] = {}

    for key in filled:
        i, j, k = key
        points = [
            model(
                i + inset + dx * (1.0 - 2.0 * inset),
                j + inset + dy * (1.0 - 2.0 * inset),
                k + inset + dz * (1.0 - 2.0 * inset),
            )
            for dx, dy, dz in _CORNERS
        ]
        points.append(model(i + 0.5, j + 0.5, k + 0.5))
        px, py, depth = project_many(points)
        corners_px[key] = [(float(px[n]), float(py[n])) for n in range(8)]
        centres[key] = (float(px[8]), float(py[8]))
        depths[key] = float(depth[8])
        faces = [
            [corners_px[key][c] for c in corner_ids]
            for corner_ids, _ in _FACES
            if _screen_area([corners_px[key][c] for c in corner_ids]) * _FACING > 0.0
        ]
        silhouettes[key] = faces
        order.append(key)
    order.sort(key=lambda key: depths[key])

    # ---- what this angle hides ----
    # A cell counts as hidden when every corner of it and its centre fall
    # inside a nearer cell's visible faces. Not a proof -- a sliver could
    # still show between two of them -- but it is the test a reader would
    # run by eye, and it is stated rather than assumed.
    hidden: set[Tuple[int, int, int]] = set()
    for position, key in enumerate(order):
        probes = corners_px[key] + [centres[key]]
        nearer = order[position + 1 :]
        covered = 0
        for probe in probes:
            for other in nearer:
                if any(_inside(probe, quad) for quad in silhouettes[other]):
                    covered += 1
                    break
        if covered == len(probes):
            hidden.add(key)

    def level_formatter(levels: Sequence[Any]) -> Any:
        """One spelling for a whole axis, decided by the axis.

        Formatting each level on its own merits writes 0.60, 0.70, 0.85
        and then 1 -- three decimals' worth of care followed by a bare
        integer, which reads as a different quantity. The decimals are
        counted once across the axis and applied to all of it.
        """
        places = 0
        for level in levels:
            try:
                text = str(level)
            except (TypeError, ValueError):  # pragma: no cover - defensive
                return str
            if "." in text:
                places = max(places, len(text.split(".", 1)[1].rstrip("0")))

        def spell(raw: Any) -> str:
            try:
                number = float(raw)
            except (TypeError, ValueError):
                return str(raw)
            return f"{number:.{places}f}"

        return spell

    spell_x = level_formatter(xs)
    spell_y = level_formatter(ys)
    spell_z = level_formatter(zs)
    spellers = {"x": spell_x, "y": spell_y, "z": spell_z}

    def shown(axis: str, raw: Any) -> str:
        return str(spellers[axis](raw))

    x_name = x_label if x_label is not None else x.replace("_", " ")
    y_name = y_label if y_label is not None else y.replace("_", " ")
    z_name = z_label if z_label is not None else z.replace("_", " ")
    v_name = value_label if value_label is not None else value.replace("_", " ")

    def measured(number: float) -> str:
        return fmt_measured(number, scale_of / 10.0)

    said_lines = (
        wrap_no_orphan(summary, mono_chars)
        if summary is not None
        else [
            # "at or above" rather than a greater-or-equal sign: the
            # mono face the chrome is set in has the glyph in its cmap
            # and the renderer still falls back on it, which re-shapes
            # the whole line in the proportional italic. One character
            # is not worth a line of chrome in the wrong font.
            f"{nx} × {ny} × {nz} grid, {len(cells)} cells · {len(filled)} filled at "
            f"{v_name} {measured(cut_at)} and above",
            *cut_said,
            f"{measured(v_lo)} to {measured(v_hi)} · camera at {fmt_number(elev)}° "
            f"elevation, {fmt_number(azim)}° azimuth",
            f"{len(hidden)} of them are hidden behind nearer cells from this angle",
        ]
    )
    if finding is not None:
        found_lines = wrap_no_orphan(finding, mono_chars)
    elif mark_best and on_face:
        edges = []
        if best_key[0] in (0, nx - 1):
            edges.append(f"{x_name} {shown('x', xs[best_key[0]])}")
        if best_key[1] in (0, ny - 1):
            edges.append(f"{y_name} {shown('y', ys[best_key[1]])}")
        if best_key[2] in (0, nz - 1):
            edges.append(f"{z_name} {shown('z', zs[best_key[2]])}")
        found_lines = [
            f"The best cell, {v_name} {measured(cells[best_key])}, sits on a face of "
            f"the grid: {', '.join(edges)}.",
            "Whatever is beyond that face was never tried, so the search bounds are "
            "part of the result.",
        ]
    elif mark_best:
        found_lines = [
            f"The best cell, {v_name} {measured(cells[best_key])}, sits inside the "
            f"grid, so the bounds did not decide it.",
        ]
    else:
        found_lines = []

    said = " · ".join(said_lines)
    found = " ".join(found_lines)

    parts: List[str] = []
    parts.append(
        svg_open(
            width, height, "voxels-title", "voxels-desc", font_family=chrome_stack_for_theme(theme)
        )
    )
    parts.append(f'<title id="voxels-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="voxels-desc">A voxel plot of {xml_escape(v_name)} over a '
        f"{nx} by {ny} by {nz} grid of {xml_escape(x_name)}, {xml_escape(y_name)} and "
        f"{xml_escape(z_name)}. {xml_escape(said)}. {xml_escape(found)}</desc>"
    )
    parts.append(
        "<style>"
        ".hit{cursor:default;}"
        ".hit:hover,.hit:focus{outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + foreground_tip_css(len(order), mark_prefix="cell", tip_prefix="celltip")
        + "@media (prefers-reduced-motion:reduce){.tip{transition:none}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    title_size = fit_font_size(title, (width - 2.0 * plot_x) / wide, 22.0, min_px=14.0)
    parts.append(
        f'<text x="{plot_x:.1f}" y="46" font-size="{title_size:.1f}" '
        f'font-weight="700" fill="{INK}" letter-spacing="-0.3">'
        f"{xml_escape(title)}</text>"
    )
    for line_no, line in enumerate(subtitle_lines):
        parts.append(
            f'<text x="{plot_x:.1f}" y="{72 + line_no * 18:.1f}" font-size="14" '
            f'fill="{SECONDARY}">{xml_escape(line)}</text>'
        )
    for line_no, line in enumerate(said_lines):
        parts.append(
            f'<text x="{plot_x:.1f}" y="{chrome_top + line_no * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(line)}</text>'
        )

    # ---- the lattice's bounding box, behind the cells ----
    box_points = [model(c[0] * nx, c[1] * ny, c[2] * nz) for c in _CORNERS]
    box_px, box_py, _ = project_many(box_points)
    box_edges = (
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 0),
        (4, 5),
        (5, 6),
        (6, 7),
        (7, 4),
        (0, 4),
        (1, 5),
        (2, 6),
        (3, 7),
    )
    if show_box:
        path = " ".join(
            f"M {box_px[a]:.1f},{box_py[a]:.1f} L {box_px[b]:.1f},{box_py[b]:.1f}"
            for a, b in box_edges
        )
        parts.append(
            f'<path d="{path}" fill="none" stroke="{GRIDLINE}" stroke-width="1" opacity="0.8"/>'
        )

    # ---- the cells, back to front ----
    for key in order:
        colour = viridis((cells[key] - v_lo) / scale_of)
        for corner_ids, lightness in _FACES:
            quad = [corners_px[key][c] for c in corner_ids]
            if _screen_area(quad) * _FACING <= 0.0:
                continue
            drawn = " ".join(f"{px:.1f},{py:.1f}" for px, py in quad)
            edge = f' stroke="{_shade(colour, 0.45)}" stroke-width="0.6"' if show_edges else ""
            parts.append(f'<polygon points="{drawn}" fill="{_shade(colour, lightness)}"{edge}/>')

    # ---- the axes, on whichever edges of the box face outward ----
    box_centre = (float(np.mean(box_px)), float(np.mean(box_py)))
    axis_specs = (
        (nx, xs, "x", x_name, ((0, 1), (3, 2), (4, 5), (7, 6))),
        (ny, ys, "y", y_name, ((0, 3), (1, 2), (4, 7), (5, 6))),
        (nz, zs, "z", z_name, ((0, 4), (1, 5), (2, 6), (3, 7))),
    )
    for count, levels, column, name, candidates in axis_specs:
        # The outermost parallel edge on screen: the one whose midpoint
        # is farthest from the projected centre of the box, which is the
        # edge a reader's eye already treats as the axis.
        start, end = max(
            candidates,
            key=lambda e: (
                ((box_px[e[0]] + box_px[e[1]]) / 2.0 - box_centre[0]) ** 2
                + ((box_py[e[0]] + box_py[e[1]]) / 2.0 - box_centre[1]) ** 2
            ),
        )
        away_x = (box_px[start] + box_px[end]) / 2.0 - box_centre[0]
        away_y = (box_py[start] + box_py[end]) / 2.0 - box_centre[1]
        reach = math.hypot(away_x, away_y) or 1.0
        off_x, off_y = away_x / reach * 20.0, away_y / reach * 20.0
        # Anchored away from the box rather than centred on the tick: a
        # centred label on a near-vertical edge sits half on top of the
        # volume it is meant to be outside of.
        anchor = "middle"
        if abs(off_x) > 7.0:
            anchor = "start" if off_x > 0 else "end"
        spelled = [shown(column, level) for level in levels]
        edge_px = math.hypot(float(box_px[end] - box_px[start]), float(box_py[end] - box_py[start]))
        widest = max((len(text) for text in spelled), default=1) * 6.0 + 6.0
        # A foreshortened edge cannot carry every tick: showing fewer is
        # legible, showing all of them is a smudge.
        stride = max(1, int(math.ceil(count * widest / max(edge_px, 1.0))))
        if abs(off_x) <= 7.0:
            stride = max(1, int(math.ceil(count * 13.0 / max(edge_px, 1.0))))
        for index, text in enumerate(spelled):
            if index % stride:
                continue
            share = (index + 0.5) / count
            tx = box_px[start] + (box_px[end] - box_px[start]) * share + off_x
            ty = box_py[start] + (box_py[end] - box_py[start]) * share + off_y
            parts.append(
                f'<text x="{tx:.1f}" y="{ty + 3:.1f}" font-size="9.5" '
                f'fill="{SECONDARY}" text-anchor="{anchor}" '
                f'font-family="{mono_family}">{xml_escape(text)}</text>'
            )
        parts.append(
            f'<text x="{(box_px[start] + box_px[end]) / 2.0 + off_x * 3.4:.1f}" '
            f'y="{(box_py[start] + box_py[end]) / 2.0 + off_y * 3.4 + 3:.1f}" '
            f'font-size="11" fill="{SECONDARY}" text-anchor="{anchor}">'
            f"{xml_escape(name)}</text>"
        )

    # ---- the best cell, called out where it sits ----
    if mark_best and best_key in centres:
        bx, by = centres[best_key]
        parts.append(
            f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="4.5" fill="none" '
            f'stroke="{INK}" stroke-width="1.8"/>'
        )
        parts.append(
            f'<text x="{bx:.1f}" y="{by - 10:.1f}" font-size="10.5" font-weight="700" '
            f'fill="{INK}" text-anchor="middle" font-family="{mono_family}">'
            f"{xml_escape(measured(cells[best_key]))}</text>"
        )

    # ---- hover: every cell says its three coordinates and its value ----
    for index, key in enumerate(order):
        cx, cy = centres[key]
        label = (
            f"{x_name} {shown('x', xs[key[0]])}, {y_name} {shown('y', ys[key[1]])}, "
            f"{z_name} {shown('z', zs[key[2]])}: {v_name} {measured(cells[key])}"
        )
        parts.append(
            f'<circle class="hit" id="cell-{index}" cx="{cx:.1f}" cy="{cy:.1f}" '
            f'r="9" fill="transparent" tabindex="0" role="img" '
            f'aria-label="{xml_escape(label)}">'
            f"<title>{xml_escape(label)}</title></circle>"
        )
    for index, key in enumerate(order):
        cx, cy = centres[key]
        parts.append(
            tooltip_bubble(
                cx,
                cy - 12.0,
                [
                    f"{v_name} {measured(cells[key])}",
                    f"{x_name} {shown('x', xs[key[0]])} · {y_name} {shown('y', ys[key[1]])}",
                    f"{z_name} {shown('z', zs[key[2]])}",
                ],
                canvas_w=width,
                canvas_h=height,
                bg=BG,
                border=GRIDLINE,
                ink=INK,
                secondary=SECONDARY,
                font_family=chrome_stack_for_theme(theme),
                elem_id=f"celltip-{index}",
            )
        )

    # ---- the value ramp ----
    legend_x = width - 138.0
    legend_y = plot_y + 20.0
    steps = 28
    band = 7.0
    parts.append(
        f'<text x="{legend_x:.1f}" y="{legend_y - 12:.1f}" font-size="11" '
        f'fill="{SECONDARY}">{xml_escape(v_name)}</text>'
    )
    for step in range(steps):
        top = legend_y + (steps - 1 - step) * band
        parts.append(
            f'<rect x="{legend_x:.1f}" y="{top:.1f}" width="14" height="{band + 0.5:.1f}" '
            f'fill="{viridis(step / (steps - 1))}"/>'
        )
    parts.append(
        f'<text x="{legend_x + 22:.1f}" y="{legend_y + 8:.1f}" font-size="10" '
        f'fill="{SECONDARY}" font-family="{mono_family}">{measured(v_hi)}</text>'
    )
    parts.append(
        f'<text x="{legend_x + 22:.1f}" y="{legend_y + steps * band:.1f}" font-size="10" '
        f'fill="{SECONDARY}" font-family="{mono_family}">{measured(v_lo)}</text>'
    )
    keep_top = legend_y + (1.0 - (cut_at - v_lo) / scale_of) * (steps - 1) * band
    parts.append(
        f'<path d="M {legend_x - 6:.1f},{keep_top:.1f} L {legend_x + 16:.1f},'
        f'{keep_top:.1f}" stroke="{INK}" stroke-width="1.6"/>'
    )
    parts.append(
        f'<text x="{legend_x + 22:.1f}" y="{keep_top + 4:.1f}" font-size="10" '
        f'fill="{INK}" font-family="{mono_family}">{measured(cut_at)}</text>'
    )
    parts.append(
        f'<text x="{legend_x:.1f}" y="{legend_y + steps * band + 22:.1f}" '
        f'font-size="10" fill="{SECONDARY}">filled at or above</text>'
    )

    for line_no, line in enumerate(found_lines):
        parts.append(
            f'<text x="{plot_x:.1f}" '
            f'y="{height - 24 - (len(found_lines) - 1 - line_no) * 17:.1f}" '
            f'font-size="12" fill="{SECONDARY}" font-family="{mono_family}">'
            f"{xml_escape(line)}</text>"
        )
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_voxels(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "The best cell is against a wall, so the search stopped early",
    subtitle: str = "A three-way grid search. Cells at or above the threshold are filled; the rest are left out.",
    width: int = 790,
    height: int = 620,
    x: str = "learning_rate",
    y: str = "max_depth",
    z: str = "subsample",
    value: str = "auc",
    threshold: Optional[float] = None,
    keep_share: float = 0.45,
    gap: float = 0.14,
    cut: str = "none",
    elev: float = 24.0,
    azim: float = -52.0,
    zoom: float = 0.98,
    show_edges: bool = True,
    show_box: bool = True,
    mark_best: bool = True,
    x_label: Optional[str] = None,
    y_label: Optional[str] = None,
    z_label: Optional[str] = None,
    value_label: Optional[str] = None,
    summary: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored voxel plot and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        One row per lattice cell with keys ``learning_rate``,
        ``max_depth``, ``subsample`` and ``auc``, or whatever `x`, `y`,
        `z` and `value` name. Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/voxels.svg``.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    x, y, z, value : str
        Which keys hold the three coordinates and the measured value.
    threshold : float or None
        Fill cells at or above this; ``None`` keeps `keep_share` of them.
    keep_share : float
        Share of cells kept when `threshold` is ``None``.
    gap : float
        How much of its own slot each cell gives back.
    cut : str
        ``"none"``, ``"corner"`` or ``"half"``: how much of the near side
        to remove so the interior can be seen.
    elev, azim, zoom : float
        Camera elevation, azimuth and zoom.
    show_edges, show_box, mark_best : bool
        Which layers to draw.
    x_label, y_label, z_label, value_label : str or None
        Axis titles and the value's name; ``None`` uses the column names.
    summary, finding : str or None
        The chrome block and the closing lines; ``None`` composes them.
    mode, accessibility : str
        Forwarded to :func:`build_svg`.
    theme : str, optional
        Visual theme. Forwarded to :func:`build_svg`.

    Returns
    -------
    Path
        Absolute path to the written SVG file.

    Examples
    --------
    >>> p = make_voxels()
    >>> p.exists()
    True
    """
    svg = build_svg(
        data,
        title=title,
        subtitle=subtitle,
        width=width,
        height=height,
        x=x,
        y=y,
        z=z,
        value=value,
        threshold=threshold,
        keep_share=keep_share,
        gap=gap,
        cut=cut,
        elev=elev,
        azim=azim,
        zoom=zoom,
        show_edges=show_edges,
        show_box=show_box,
        mark_best=mark_best,
        x_label=x_label,
        y_label=y_label,
        z_label=z_label,
        value_label=value_label,
        summary=summary,
        finding=finding,
        mode=mode,
        accessibility=accessibility,
        theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "voxels")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(
        __file__,
        "voxels",
        build_svg,
        description="Generate a voxel plot of a three-dimensional grid.",
    )


if __name__ == "__main__":
    main()
