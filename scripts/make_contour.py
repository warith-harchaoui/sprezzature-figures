#!/usr/bin/env python3
"""
make_contour — iso-lines over a scalar field, with the levels written on them.

The catalogue had ``kde2d-contour``, which contours a *density* estimated
from points, and nothing for a field that is simply given. A field is not
always a density: a loss surface, a temperature, a potential, a model's
output over two inputs are all z = f(x, y) with no points underneath to
estimate anything from. (COVERAGE.md names who else draws this and under
what name; a figure's own file is about the figure.)

What this does that most contour plots do not
---------------------------------------------
* **The lines carry their own value.** Contour labels are an opt-in
  almost everywhere and almost nobody opts in, which leaves the reader a
  topography with no altitude, counting rings against a legend. Every
  level here is written on its own line, in a gap cut out of the line so
  the number stays readable.
* **Filled bands and lines together.** The fill answers "where is it high"
  at a glance; the lines answer "how high, exactly". Either alone leaves
  one of the two questions to guesswork.
* **Levels on a stated sequence.** A loss surface spans three orders of
  magnitude; evenly spaced levels then draw nine lines around the
  mountains and none in the basins, which is where the reader is looking.
  The sequence is geometric by default and printed on the figure.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _style import BG, GRIDLINE, INK, SECONDARY, load_palette  # noqa: E402
from _svg import fmt_number, raster_row_rects, svg_open, viridis, xml_escape  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

#: Grid resolution of the demo field. 61 x 45 is enough for the iso-lines
#: to come out smooth and few enough rows that the kit's data.csv stays a
#: file a person can open.
_NX, _NY = 61, 45


def _himmelblau(x: float, y: float) -> float:
    """The standard four-basin test surface for optimisers.

    Chosen over a terrain because the audience for this package meets it
    as a loss landscape far more often than as a hill: four minima of
    equal depth, separated by ridges, is exactly the picture that explains
    why where you start decides where you end up.
    """
    return (x * x + y - 11.0) ** 2 + (x + y * y - 7.0) ** 2


DEMO_DATA: List[Dict[str, Any]] = [
    {
        "x": round(-5.0 + 10.0 * i / (_NX - 1), 4),
        "y": round(-5.0 + 10.0 * j / (_NY - 1), 4),
        "z": round(_himmelblau(-5.0 + 10.0 * i / (_NX - 1), -5.0 + 10.0 * j / (_NY - 1)), 3),
    }
    for j in range(_NY)
    for i in range(_NX)
]


def _geometric_levels(low: float, high: float, count: int) -> List[float]:
    """`count` levels from `low` to `high`, rounded to numbers worth printing.

    Geometric rather than even: a field spanning three orders of magnitude
    gets nine evenly spaced lines bunched around its maximum and none in
    the basins, which is the half of the figure a reader is looking at.
    """
    low = max(low, high / 1e4) or 1e-6
    raw = [low * (high / low) ** (i / (count - 1)) for i in range(count)]
    nice: List[float] = []
    for value in raw:
        magnitude = 10.0 ** math.floor(math.log10(value))
        for step in (1.0, 2.0, 5.0, 10.0):
            if value <= step * magnitude:
                value = step * magnitude
                break
        if not nice or value > nice[-1]:
            nice.append(value)
    return nice


def _marching_squares(
    grid: List[List[float]], level: float, nx: int, ny: int
) -> List[Tuple[float, float, float, float]]:
    """Segments of the `level` iso-line, in grid coordinates.

    The plain marching-squares cases, with the saddle ambiguity resolved
    by the cell's own mean -- the usual choice, and the one that keeps two
    basins from being joined by a line that is not there.
    """
    segments: List[Tuple[float, float, float, float]] = []

    def interpolate(a: float, b: float) -> float:
        return 0.0 if a == b else (level - a) / (b - a)

    for j in range(ny - 1):
        for i in range(nx - 1):
            bl, br = grid[j][i], grid[j][i + 1]
            tl, tr = grid[j + 1][i], grid[j + 1][i + 1]
            case = (
                (1 if bl > level else 0)
                | (2 if br > level else 0)
                | (4 if tr > level else 0)
                | (8 if tl > level else 0)
            )
            if case in (0, 15):
                continue
            bottom = (i + interpolate(bl, br), float(j))
            right = (float(i + 1), j + interpolate(br, tr))
            top = (i + interpolate(tl, tr), float(j + 1))
            left = (float(i), j + interpolate(bl, tl))
            joins = {
                1: [(left, bottom)], 2: [(bottom, right)], 3: [(left, right)],
                4: [(right, top)], 6: [(bottom, top)], 7: [(left, top)],
                8: [(top, left)], 9: [(top, bottom)], 11: [(top, right)],
                12: [(right, left)], 13: [(right, bottom)], 14: [(bottom, left)],
            }
            if case in (5, 10):
                # Saddle: the four corners alternate, so two lines cross this
                # cell and which pair they join is genuinely ambiguous. The
                # cell mean decides, which is what every implementation worth
                # trusting does.
                centre = (bl + br + tl + tr) / 4.0
                if (case == 5) == (centre > level):
                    pairs = [(left, top), (bottom, right)]
                else:
                    pairs = [(left, bottom), (top, right)]
            else:
                pairs = joins[case]
            for (x0, y0), (x1, y1) in pairs:
                segments.append((x0, y0, x1, y1))
    return segments


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Four basins of equal depth, and a start decides which one you reach",
    subtitle: str = "Himmelblau's surface. Lines are iso-levels; the fill is the same value, banded.",
    width: int = 900,
    height: int = 640,
    x: str = "x",
    y: str = "y",
    z: str = "z",
    levels: int = 9,
    x_label: str = "x",
    y_label: str = "y",
    value_label: str = "f(x, y)",
    summary: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full contour SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows on a regular grid, with keys named by `x`, `y` and `z`.
        Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    x, y, z : str
        Which keys hold the two coordinates and the field value.
    levels : int
        How many iso-levels to draw, on a geometric sequence rounded to
        readable numbers; the count that results is at most this.
    x_label, y_label, value_label : str
        Axis titles and the name of the field.
    summary : str or None
        The line stating the grid size, the number of levels and the range.
        ``None`` composes it.
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
    rows = list(data if data else DEMO_DATA)
    mono_family = mono_stack_for_theme(theme)
    load_palette(accessibility, theme=theme)

    xs = sorted({float(r[x]) for r in rows})
    ys = sorted({float(r[y]) for r in rows})
    nx, ny = len(xs), len(ys)
    x_index = {v: i for i, v in enumerate(xs)}
    y_index = {v: j for j, v in enumerate(ys)}
    grid = [[0.0] * nx for _ in range(ny)]
    for row in rows:
        grid[y_index[float(row[y])]][x_index[float(row[x])]] = float(row[z])

    flat = [value for line in grid for value in line]
    z_lo, z_hi = min(flat), max(flat)
    cuts = [
        cut for cut in _geometric_levels(max(z_lo, z_hi / 1e3) or 1.0, z_hi, levels)
        if cut <= z_hi
    ]

    plot_x, plot_y = 70.0, 140.0
    right_margin, bottom_margin = 160.0, 72.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_margin
    cell_w = plot_w / (nx - 1)
    cell_h = plot_h / (ny - 1)

    def to_px(gx: float, gy: float) -> Tuple[float, float]:
        return plot_x + gx * cell_w, plot_y + plot_h - gy * cell_h

    def band_colour(value: float) -> str:
        """The band a value falls in, as a colour.

        Quantised to the levels rather than continuous: it is what makes
        the fill agree with the lines instead of merely resembling them,
        and it is what lets ``raster_row_rects`` merge a row into a handful
        of rects rather than one per cell.
        """
        band = sum(1 for cut in cuts if value >= cut)
        return viridis(band / max(len(cuts), 1))

    parts: List[str] = []
    parts.append(
        svg_open(width, height, "contour-title", "contour-desc",
                 font_family=chrome_stack_for_theme(theme))
    )
    parts.append(f'<title id="contour-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="contour-desc">A contour plot of {xml_escape(value_label)} over a '
        f'{nx} by {ny} grid, from {fmt_number(z_lo)} to {fmt_number(z_hi)}. '
        f'{len(cuts)} iso-levels are drawn and labelled: '
        f'{", ".join(fmt_number(c) for c in cuts)}. The fill is the same value in bands, '
        f'dark where it is low and bright where it is high.</desc>'
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="{plot_x:.1f}" y="46" font-size="22" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(
        f'<text x="{plot_x:.1f}" y="72" font-size="14" fill="{SECONDARY}">'
        f'{xml_escape(subtitle)}</text>'
    )
    said = summary if summary is not None else (
        f"{nx} × {ny} grid · {len(cuts)} levels on a geometric sequence · "
        f"{fmt_number(z_lo)} to {fmt_number(z_hi)}"
    )
    parts.append(
        f'<text x="{plot_x:.1f}" y="98" font-size="12" fill="{SECONDARY}" '
        f'font-family="{mono_family}">{xml_escape(said)}</text>'
    )

    # ---- the banded fill ----
    # Painted one data cell at a time, the bands come out as horizontal
    # stripes with ragged edges: a cell is eleven pixels across here, and
    # the band boundary inside it is thrown away. The fill is therefore
    # sampled on a finer grid, bilinearly between the data points -- the
    # same interpolation `imshow-interpolated` does, and the same one the
    # eye performs anyway when it reads a field as continuous. The lines
    # are still cut from the original grid: those are a measurement, and
    # interpolating a measurement is not the same as smoothing a picture.
    fine = 3
    fine_w, fine_h = cell_w / fine, cell_h / fine
    for jj in range((ny - 1) * fine):
        row_colours: List[str] = []
        gy = jj / fine
        j0 = min(int(gy), ny - 2)
        fy = gy - j0
        for ii in range((nx - 1) * fine):
            gx = ii / fine
            i0 = min(int(gx), nx - 2)
            fx = gx - i0
            value = (
                grid[j0][i0] * (1 - fx) * (1 - fy)
                + grid[j0][i0 + 1] * fx * (1 - fy)
                + grid[j0 + 1][i0] * (1 - fx) * fy
                + grid[j0 + 1][i0 + 1] * fx * fy
            )
            row_colours.append(band_colour(value))
        parts.extend(
            # Half a pixel taller than its own pitch: rows that merely abut
            # leave an anti-aliasing seam, and 135 of them read as hairline
            # stripes across a fill the reader is meant to see as continuous.
            raster_row_rects(
                row_colours, plot_x, plot_y + plot_h - (jj + 1) * fine_h,
                fine_w, fine_h + 0.5,
            )
        )

    # ---- the iso-lines, each labelled with its own value ----
    for index, level in enumerate(cuts):
        segments = _marching_squares(grid, level, nx, ny)
        if not segments:
            continue
        path = " ".join(
            "M {:.1f},{:.1f} L {:.1f},{:.1f}".format(*to_px(x0, y0), *to_px(x1, y1))
            for x0, y0, x1, y1 in segments
        )
        # Light ink on the dark end of the ramp, dark on the bright end:
        # one fixed line colour is unreadable over half of any fill.
        ink = "#FFFFFF" if index < len(cuts) * 0.62 else INK
        parts.append(
            f'<path d="{path}" fill="none" stroke="{ink}" stroke-width="1.1" '
            f'opacity="0.78"/>'
        )
        # Where to put the number. Nearest-the-centre put every level's
        # label in the same place, so five of them piled up on one shoulder
        # of one basin. Each level is given its own anchor instead, walked
        # around the plot by the golden angle, which spreads n labels over a
        # ring without any two landing together whatever n is.
        angle = index * 2.39996
        radius = 0.34
        target = (
            nx * (0.5 + radius * math.cos(angle)),
            ny * (0.5 + radius * math.sin(angle)),
        )
        best = min(
            segments,
            key=lambda s: (s[0] - target[0]) ** 2 + (s[1] - target[1]) ** 2,
        )
        lx, ly = to_px((best[0] + best[2]) / 2.0, (best[1] + best[3]) / 2.0)
        text = fmt_number(level)
        parts.append(
            f'<rect x="{lx - 3.5 * len(text) - 3:.1f}" y="{ly - 8:.1f}" '
            f'width="{7.0 * len(text) + 6:.1f}" height="14" fill="{BG}" opacity="0.82" rx="2"/>'
        )
        parts.append(
            f'<text x="{lx:.1f}" y="{ly + 4:.1f}" font-size="10" fill="{INK}" '
            f'text-anchor="middle" font-family="{mono_family}">{text}</text>'
        )

    parts.append(
        f'<rect x="{plot_x:.1f}" y="{plot_y:.1f}" width="{plot_w:.1f}" height="{plot_h:.1f}" '
        f'fill="none" stroke="{GRIDLINE}" stroke-width="1"/>'
    )

    # ---- axes ----
    for i in range(0, nx, max(1, (nx - 1) // 5)):
        px, _ = to_px(i, 0)
        parts.append(
            f'<text x="{px:.1f}" y="{plot_y + plot_h + 20:.1f}" font-size="11" '
            f'fill="{SECONDARY}" text-anchor="middle" font-family="{mono_family}">'
            f'{fmt_number(xs[i])}</text>'
        )
    for j in range(0, ny, max(1, (ny - 1) // 5)):
        _, py = to_px(0, j)
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{py + 4:.1f}" font-size="11" fill="{SECONDARY}" '
            f'text-anchor="end" font-family="{mono_family}">{fmt_number(ys[j])}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{plot_y + plot_h + 46:.1f}" font-size="12" '
        f'fill="{SECONDARY}" text-anchor="middle">{xml_escape(x_label)}</text>'
    )
    parts.append(
        f'<text x="{plot_x:.1f}" y="{plot_y - 12:.1f}" font-size="12" fill="{SECONDARY}">'
        f'{xml_escape(y_label)}</text>'
    )

    # ---- the band legend, each band labelled with the level that opens it ----
    legend_x = plot_x + plot_w + 34.0
    band_h = min(26.0, plot_h / (len(cuts) + 1))
    parts.append(
        f'<text x="{legend_x:.1f}" y="{plot_y - 12:.1f}" font-size="11" fill="{SECONDARY}">'
        f'{xml_escape(value_label)}</text>'
    )
    for index in range(len(cuts), -1, -1):
        top = plot_y + (len(cuts) - index) * band_h
        parts.append(
            f'<rect x="{legend_x:.1f}" y="{top:.1f}" width="16" height="{band_h:.1f}" '
            f'fill="{viridis(index / max(len(cuts), 1))}"/>'
        )
        if index > 0:
            parts.append(
                f'<text x="{legend_x + 24:.1f}" y="{top + band_h + 4:.1f}" font-size="10" '
                f'fill="{SECONDARY}" font-family="{mono_family}">'
                f'{fmt_number(cuts[index - 1])}</text>'
            )
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_contour(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Four basins of equal depth, and a start decides which one you reach",
    subtitle: str = "Himmelblau's surface. Lines are iso-levels; the fill is the same value, banded.",
    width: int = 900,
    height: int = 640,
    x: str = "x",
    y: str = "y",
    z: str = "z",
    levels: int = 9,
    x_label: str = "x",
    y_label: str = "y",
    value_label: str = "f(x, y)",
    summary: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored contour plot and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows on a regular grid with keys ``x``, ``y`` and ``z``, or
        whatever `x`, `y` and `z` name. Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/contour.svg``.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    x, y, z : str
        Which keys hold the coordinates and the field value.
    levels : int
        How many iso-levels to draw.
    x_label, y_label, value_label : str
        Axis titles and the name of the field.
    summary : str or None
        The line stating grid, levels and range; ``None`` composes it.
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
    >>> p = make_contour()
    >>> p.exists()
    True
    """
    svg = build_svg(
        data, title=title, subtitle=subtitle, width=width, height=height,
        x=x, y=y, z=z, levels=levels, x_label=x_label, y_label=y_label,
        value_label=value_label, summary=summary, mode=mode,
        accessibility=accessibility, theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "contour")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "contour", build_svg, description="Generate a contour plot.")


if __name__ == "__main__":
    main()
