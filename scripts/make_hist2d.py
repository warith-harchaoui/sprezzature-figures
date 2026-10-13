#!/usr/bin/env python3
"""
make_hist2d — a two-dimensional histogram: count the points, do not draw them.

Four of the catalogues this package is measured against have this under
four names (``hist2d``, ``density_heatmap``, ``geom_bin2d``, bivariate
``histplot``). It is what a scatter plot should become once the points
start landing on top of each other: past a few thousand, a scatter shows
where data *is* and hides how much of it is there, and the densest region
looks exactly like the second densest.

Not the same chart as its neighbours here: ``heatmap`` colours a matrix
that is already a table, ``hexbin`` bins to hexagons (better packing,
harder to read a value off), ``jointplot`` is a scatter with marginals.
This one bins raw points to a rectangular grid, which is the form whose
cell a reader can locate on both axes without a second thought.

What this does that most 2-D histograms do not
----------------------------------------------
* **Empty is not dark, empty is empty.** A cell with no points is left as
  canvas rather than painted the bottom of the ramp. On a viridis scale,
  zero and one are nearly the same purple, and "nothing happened here"
  then reads as "a little happened here" -- which, on a figure whose whole
  job is density, is the one error that matters.
* **The bin size is on the figure.** Every 2-D histogram is an argument
  about bin width, and changing it changes what the reader concludes.
  Stating it is the difference between a measurement and a mood.
* **A legend that is a scale, with stops along it.** Not a gradient bar
  with a number floating near it: counts written at both ends and twice in
  between, because on the square-root ramp the middle of the bar is a
  quarter of the busiest bin, not half, and a reader who assumes otherwise
  is off by a factor of two over most of the figure.
* **Colour on a square-root scale, said out loud.** Bin counts are
  long-tailed almost every time; mapped linearly the chart comes out one
  flat purple. The first render of this figure did exactly that.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _style import BG, GRIDLINE, INK, SECONDARY, load_palette  # noqa: E402
from _svg import fmt_number, svg_open, viridis, xml_escape  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402


def _demo_points(count: int = 2600, seed: int = 11) -> List[Dict[str, Any]]:
    """Taxi trips: a fare-per-mile ridge, plus the airport flat fare as its own cloud.

    Generated rather than written out, because a two-dimensional histogram
    needs thousands of rows to be the right chart at all and a literal of
    that size would be unreadable. Seeded, so the figure is the same on
    every machine and in every release; Box-Muller from ``random()``
    rather than ``gauss()`` because the latter caches a second value
    between calls and that makes the sequence harder to reason about.
    """
    rng = random.Random(seed)

    def normal(mean: float, sigma: float) -> float:
        u1 = max(rng.random(), 1e-12)
        u2 = rng.random()
        return mean + sigma * math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)

    rows: List[Dict[str, Any]] = []
    for _ in range(count):
        if rng.random() < 0.08:
            # The flat-rate airport run: a fixed fare over a narrow band of
            # distances, which is the second cloud the title is about.
            distance = normal(17.2, 1.4)
            fare = normal(52.0, 2.2)
        else:
            distance = min(rng.expovariate(1 / 2.6) + 0.4, 24.0)
            fare = 3.2 + 2.45 * distance + normal(0.0, 1.6 + 0.12 * distance)
        if distance <= 0 or fare <= 0:
            continue
        rows.append({"distance": round(distance, 2), "fare": round(fare, 2)})
    return rows


DEMO_DATA: List[Dict[str, Any]] = _demo_points()


def _bin_edges(low: float, high: float, bins: int) -> Tuple[float, float, float]:
    """Rounded bounds and a bin width, so the axis ticks fall on readable numbers."""
    span = (high - low) or 1.0
    step = 10.0 ** math.floor(math.log10(span / bins))
    for scale in (1.0, 2.0, 2.5, 5.0, 10.0):
        if span / (step * scale) <= bins:
            step *= scale
            break
    return math.floor(low / step) * step, math.ceil(high / step) * step, step


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "The airport flat fare shows up as a cloud of its own",
    subtitle: str = "Every taxi trip of one week, counted into bins. A scatter of these would be one black smear.",
    width: int = 880,
    height: int = 620,
    x: str = "distance",
    y: str = "fare",
    bins: int = 34,
    x_label: str = "Trip distance (miles)",
    y_label: str = "Fare ($)",
    legend_title: str = "Points per bin",
    empty_label: str = "no trips",
    summary: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full two-dimensional histogram SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with two numeric keys, named by `x` and `y`. Defaults to
        :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    x, y : str
        Which key is binned along each axis.
    bins : int
        Target number of bins on the longer axis; the bin width is rounded
        to a readable number, so the count that results is close to this
        rather than exactly it.
    x_label, y_label : str
        Axis titles.
    legend_title : str
        Heading above the colour scale.
    empty_label : str
        What the blank swatch in the legend is called -- the one that says
        a bin with no points was left as canvas rather than coloured.
    summary : str or None
        The line stating the point count, the bin size and the scale.
        ``None`` composes it. Nothing a reader sees should be reachable
        only by editing this file.
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

    xs = [float(r[x]) for r in rows]
    ys = [float(r[y]) for r in rows]
    x_lo, x_hi, x_step = _bin_edges(min(xs), max(xs), bins)
    y_lo, y_hi, y_step = _bin_edges(min(ys), max(ys), bins)
    n_x = max(1, int(round((x_hi - x_lo) / x_step)))
    n_y = max(1, int(round((y_hi - y_lo) / y_step)))

    counts: Dict[Tuple[int, int], int] = {}
    for xv, yv in zip(xs, ys, strict=True):
        cx = min(int((xv - x_lo) / x_step), n_x - 1)
        cy = min(int((yv - y_lo) / y_step), n_y - 1)
        counts[(cx, cy)] = counts.get((cx, cy), 0) + 1
    busiest = max(counts.values()) if counts else 1

    def shade_of(count: int) -> float:
        """Where `count` sits on the colour ramp, on a square-root scale.

        Counts in a 2-D histogram are almost always long-tailed: here the
        busiest bin holds 235 and most hold between one and five. Mapped
        linearly, nineteen cells in twenty land in the bottom tenth of the
        ramp and the figure comes out a single flat purple -- on a chart
        whose entire subject is density. A square root is the usual fix for
        count data (gentler than a log, which would flatten the peak that
        matters), and the legend says it is one rather than leaving the
        reader to assume the scale is linear.
        """
        return math.sqrt(count / busiest)

    plot_x, plot_y = 74.0, 136.0
    right_margin, bottom_margin = 150.0, 74.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_margin
    cell_w = plot_w / n_x
    cell_h = plot_h / n_y

    parts: List[str] = []
    parts.append(
        svg_open(width, height, "hist2d-title", "hist2d-desc",
                 font_family=chrome_stack_for_theme(theme))
    )
    parts.append(f'<title id="hist2d-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="hist2d-desc">A two-dimensional histogram of {len(rows):,} points, '
        f'binned {fmt_number(x_step)} by {fmt_number(y_step)} into a {n_x} by {n_y} grid. '
        f'Colour is the count in a bin, from 1 to {busiest}; a bin with no points is left '
        f'blank rather than coloured. {xml_escape(x_label or x)} runs across, '
        f'{xml_escape(y_label or y)} up.</desc>'
    )
    parts.append(
        "<style>"
        ".cell{cursor:default;}"
        ".cell:hover,.cell:focus{stroke:" + INK + ";stroke-width:1.5;outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        "@media (prefers-reduced-motion:reduce){.tip{transition:none}}"
        "</style>"
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
    # The bin size is the figure's main assumption, so it is written on it.
    said = summary if summary is not None else (
        f"{len(rows):,} points · bins of {fmt_number(x_step)} × {fmt_number(y_step)} · "
        f"busiest holds {busiest} · colour on a square-root scale"
    )
    parts.append(
        f'<text x="{plot_x:.1f}" y="98" font-size="12" fill="{SECONDARY}" '
        f'font-family="{mono_family}">{xml_escape(said)}</text>'
    )

    parts.append(
        f'<rect x="{plot_x:.1f}" y="{plot_y:.1f}" width="{plot_w:.1f}" height="{plot_h:.1f}" '
        f'fill="none" stroke="{GRIDLINE}" stroke-width="1"/>'
    )

    for (cx, cy), count in sorted(counts.items()):
        px = plot_x + cx * cell_w
        py = plot_y + plot_h - (cy + 1) * cell_h
        shade = viridis(shade_of(count))
        x_from, y_from = x_lo + cx * x_step, y_lo + cy * y_step
        label = (
            f"{fmt_number(x_from)}–{fmt_number(x_from + x_step)} × "
            f"{fmt_number(y_from)}–{fmt_number(y_from + y_step)}: "
            f"{count} {'point' if count == 1 else 'points'}"
        )
        parts.append(
            f'<rect class="cell" x="{px:.2f}" y="{py:.2f}" width="{cell_w + 0.5:.2f}" '
            f'height="{cell_h + 0.5:.2f}" fill="{shade}" role="img" '
            f'aria-label="{xml_escape(label)}"><title>{xml_escape(label)}</title></rect>'
        )

    # ---- axes ----
    x_tick_every = max(1, n_x // 8)
    for i in range(0, n_x + 1, x_tick_every):
        tx = plot_x + i * cell_w
        parts.append(
            f'<text x="{tx:.1f}" y="{plot_y + plot_h + 20:.1f}" font-size="11" '
            f'fill="{SECONDARY}" text-anchor="middle" font-family="{mono_family}">'
            f'{fmt_number(x_lo + i * x_step)}</text>'
        )
    y_tick_every = max(1, n_y // 6)
    for j in range(0, n_y + 1, y_tick_every):
        ty = plot_y + plot_h - j * cell_h
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{ty + 4:.1f}" font-size="11" fill="{SECONDARY}" '
            f'text-anchor="end" font-family="{mono_family}">'
            f'{fmt_number(y_lo + j * y_step)}</text>'
        )
    if x_label:
        parts.append(
            f'<text x="{plot_x + plot_w / 2:.1f}" y="{plot_y + plot_h + 48:.1f}" font-size="12" '
            f'fill="{SECONDARY}" text-anchor="middle">{xml_escape(x_label)}</text>'
        )
    if y_label:
        parts.append(
            f'<text x="{plot_x:.1f}" y="{plot_y - 12:.1f}" font-size="12" fill="{SECONDARY}">'
            f'{xml_escape(y_label)}</text>'
        )

    # ---- the scale, with both ends written ----
    legend_x = plot_x + plot_w + 36.0
    legend_h = min(plot_h, 240.0)
    legend_y = plot_y
    steps = 48
    for i in range(steps):
        t = i / (steps - 1)
        parts.append(
            f'<rect x="{legend_x:.1f}" y="{legend_y + legend_h - (i + 1) * legend_h / steps:.2f}" '
            f'width="16" height="{legend_h / steps + 0.5:.2f}" fill="{viridis(t)}"/>'
        )
    # Ends and two stops in between: on a square-root ramp the midpoint of
    # the bar is a quarter of the busiest count, not half, and a legend with
    # only its ends labelled invites exactly that mistake.
    ticks = sorted({1, max(1, busiest // 16), max(1, busiest // 4), busiest})
    for count in ticks:
        ty = legend_y + legend_h - shade_of(count) * legend_h
        parts.append(
            f'<line x1="{legend_x:.1f}" y1="{ty:.1f}" x2="{legend_x + 20:.1f}" y2="{ty:.1f}" '
            f'stroke="{BG}" stroke-width="1" opacity="0.7"/>'
        )
        parts.append(
            f'<text x="{legend_x + 24:.1f}" y="{ty + 4:.1f}" font-size="11" fill="{SECONDARY}" '
            f'font-family="{mono_family}">{count}</text>'
        )
    parts.append(
        f'<text x="{legend_x:.1f}" y="{legend_y - 12:.1f}" font-size="11" fill="{SECONDARY}">'
        f'{xml_escape(legend_title)}</text>'
    )
    # An empty bin is canvas, and the legend says so rather than leaving the
    # reader to guess whether white means zero or means missing.
    parts.append(
        f'<rect x="{legend_x:.1f}" y="{legend_y + legend_h + 20:.1f}" width="16" height="16" '
        f'fill="{BG}" stroke="{GRIDLINE}" stroke-width="1"/>'
    )
    parts.append(
        f'<text x="{legend_x + 24:.1f}" y="{legend_y + legend_h + 32:.1f}" font-size="11" '
        f'fill="{SECONDARY}">{xml_escape(empty_label)}</text>'
    )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_hist2d(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "The airport flat fare shows up as a cloud of its own",
    subtitle: str = "Every taxi trip of one week, counted into bins. A scatter of these would be one black smear.",
    width: int = 880,
    height: int = 620,
    x: str = "distance",
    y: str = "fare",
    bins: int = 34,
    x_label: str = "Trip distance (miles)",
    y_label: str = "Fare ($)",
    legend_title: str = "Points per bin",
    empty_label: str = "no trips",
    summary: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored two-dimensional histogram and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``distance`` and ``fare``, or whatever `x` and `y`
        name. Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/hist2d.svg``.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    x, y : str
        Which key is binned along each axis.
    bins : int
        Target bin count on the longer axis.
    x_label, y_label : str
        Axis titles.
    legend_title, empty_label : str
        Heading above the colour scale, and the name of its blank swatch.
    summary : str or None
        The line stating points, bin size and scale; ``None`` composes it.
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
    >>> p = make_hist2d()
    >>> p.exists()
    True
    """
    svg = build_svg(
        data, title=title, subtitle=subtitle, width=width, height=height,
        x=x, y=y, bins=bins, x_label=x_label, y_label=y_label,
        legend_title=legend_title, empty_label=empty_label, summary=summary,
        mode=mode, accessibility=accessibility, theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "hist2d")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "hist2d", build_svg, description="Generate a 2-D histogram.")


if __name__ == "__main__":
    main()
