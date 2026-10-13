#!/usr/bin/env python3
"""
make_facet — small multiples: the same chart, once per group, on one scale.

Six of the catalogues this package is measured against reach for this and
call it something different every time -- faceting, small multiples, a grid
of panels -- and it was the largest hole here. One chart with eight lines
asks the reader to untangle eight lines. Eight panels, each with one line,
asks them to compare eight shapes, which the eye does far better.

What makes a grid of panels work, and what usually breaks it
------------------------------------------------------------
* **One scale for every panel.** Panels on their own scales look
  comparable and are not: a flat line in one and a flat line in another
  can be twenty times apart. Every panel here shares the x and y domain,
  which is the entire reason to use this form.
* **The others, in grey, behind each one.** Each panel draws every other
  group first in a pale ink, then its own on top. Without it a grid is n
  separate charts; with it every panel is a comparison, and the reader
  never has to hold a shape in their head while moving to the next cell.
* **Ticks once, not n times.** Axis labels on the left column and the
  bottom row only. Repeating them in every cell is ink that says the same
  thing nine times, and it is what makes most faceted output look busy.
* **Ordered by the thing being read.** Panels are laid out by their last
  value, largest first, so position in the grid is itself information.

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
from _svg import fmt_number, foreground_tip_css, svg_open, tooltip_bubble, xml_escape  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

#: Orders per market, indexed to 100 in January. Eight shapes that are hard
#: to tell apart in one chart and obvious in eight panels: two that rise
#: every single month, one that rises then gives it back, one seasonal, one
#: flat, and three that drift down. The title is a claim about exactly
#: these numbers, which is the only kind of claim demo data can carry.
_SERIES: Dict[str, Tuple[float, ...]] = {
    "India": (100, 104, 109, 113, 118, 124, 129, 135, 141, 148, 155, 163),
    "Nigeria": (100, 103, 106, 108, 111, 115, 118, 122, 125, 129, 133, 138),
    "United States": (100, 102, 105, 103, 107, 110, 113, 111, 115, 118, 116, 120),
    "Germany": (100, 101, 104, 108, 112, 115, 113, 109, 106, 104, 103, 102),
    "Japan": (100, 99, 101, 100, 102, 101, 100, 102, 101, 100, 101, 100),
    "Brazil": (100, 103, 101, 98, 96, 99, 101, 97, 94, 92, 93, 91),
    "France": (100, 98, 97, 95, 96, 93, 91, 92, 89, 87, 86, 84),
    "Italy": (100, 97, 95, 94, 91, 89, 90, 87, 85, 83, 80, 78),
}

DEMO_DATA: List[Dict[str, Any]] = [
    {"market": market, "month": month, "orders": value}
    for market, values in _SERIES.items()
    for month, value in zip(_MONTHS, values, strict=True)
]


def _grid_shape(count: int, columns: int) -> Tuple[int, int]:
    """Rows and columns for `count` panels, squarish unless `columns` says otherwise.

    Squarish rather than a single row: a long strip of narrow panels makes
    every shape look steeper than it is, which is the one distortion this
    figure exists to avoid.
    """
    if columns > 0:
        cols = min(columns, count)
    else:
        cols = min(4, max(1, math.ceil(math.sqrt(count))))
    return math.ceil(count / cols), cols


def _nice_bounds(low: float, high: float) -> Tuple[float, float]:
    """A rounded pair containing [low, high], with a little air above and below.

    Not zero-anchored: these panels carry an index around 100, where a
    zero baseline would squash every shape into the top tenth of the cell.
    An index or a rate is read by its movement, and the axis says so by
    starting where the data does.
    """
    span = (high - low) or abs(high) or 1.0
    pad = span * 0.12
    low, high = low - pad, high + pad
    step = 10.0 ** math.floor(math.log10(span)) / 2.0
    return math.floor(low / step) * step, math.ceil(high / step) * step


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Only two markets grew in every single month",
    subtitle: str = "Orders per market, indexed to 100 in January. Grey lines are the other markets.",
    width: int = 1000,
    height: int = 700,
    facet: str = "market",
    x: str = "month",
    y: str = "orders",
    columns: int = 0,
    context: bool = True,
    x_label: str = "",
    y_label: str = "Index (January = 100)",
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full small-multiples SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows carrying a panel key, a position key and a value key, named by
        `facet`, `x` and `y`. Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    facet, x, y : str
        Which key splits the panels, which orders the points along the
        panel, and which is drawn.
    columns : int
        Panels per row; 0 picks a squarish grid.
    context : bool
        Draw every other group behind each panel in a pale ink. Turning it
        off gives n separate charts, which is the thing worth avoiding.
    x_label, y_label : str
        Axis titles, written once for the whole grid rather than per panel.
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

    # x is ordinal: its order is the order the rows present it in, not
    # alphabetical, because "Apr" before "Jan" would be nonsense and no
    # parse of the label can be trusted to know that.
    positions: List[str] = []
    for row in rows:
        label = str(row[x])
        if label not in positions:
            positions.append(label)
    index_of = {label: i for i, label in enumerate(positions)}

    by_panel: Dict[str, List[Tuple[int, float]]] = {}
    for row in rows:
        by_panel.setdefault(str(row[facet]), []).append((index_of[str(row[x])], float(row[y])))
    for points in by_panel.values():
        points.sort()

    # Largest last value first: where a panel sits in the grid then carries
    # information, instead of being an accident of dict order.
    panels = sorted(by_panel, key=lambda name: -by_panel[name][-1][1])
    values = [value for points in by_panel.values() for _, value in points]
    y_lo, y_hi = _nice_bounds(min(values), max(values))

    n_rows, n_cols = _grid_shape(len(panels), columns)
    # One line per panel means colour encodes nothing the panel title does
    # not already say, and eight hues invite the reader to look for a
    # categorical key that is not there. The first render had the best
    # market in red and the worst in pink, which is worse than meaningless.
    # Direction is the one thing colour can carry here for free, and it is
    # what the figure is about: blue rose, orange fell. Blue against orange
    # rather than the usual blue against red because this pair survives
    # every colour-vision deficiency, and nothing here is an alarm.
    palette = load_palette(accessibility, theme=theme)
    rising = palette.get("Blue", "#007AFF")
    falling = palette.get("Orange", "#FF9500")
    # A series that ended where it started is neither, and colouring it as
    # a riser is a small lie the grid repeats every time it is read. Near
    # black separates it from the pale context lines without claiming a
    # direction.
    flat = INK

    top = 128.0
    left, right_margin, bottom_margin = 74.0, 26.0, 56.0
    grid_w = width - left - right_margin
    grid_h = height - top - bottom_margin
    gap_x, gap_y = 26.0, 42.0
    cell_w = (grid_w - gap_x * (n_cols - 1)) / n_cols
    cell_h = (grid_h - gap_y * (n_rows - 1)) / n_rows

    def cell_origin(index: int) -> Tuple[float, float]:
        row_i, col_i = divmod(index, n_cols)
        return left + col_i * (cell_w + gap_x), top + row_i * (cell_h + gap_y)

    def px(ox: float, position: int) -> float:
        return ox + position / max(len(positions) - 1, 1) * cell_w

    def py(oy: float, value: float) -> float:
        return oy + cell_h - (value - y_lo) / ((y_hi - y_lo) or 1.0) * cell_h

    def polyline(ox: float, oy: float, points: List[Tuple[int, float]]) -> str:
        return " ".join(f"{px(ox, p):.1f},{py(oy, v):.1f}" for p, v in points)

    parts: List[str] = []
    parts.append(
        svg_open(
            width, height, "facet-title", "facet-desc", font_family=chrome_stack_for_theme(theme)
        )
    )
    parts.append(f'<title id="facet-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="facet-desc">A grid of {len(panels)} panels, one per '
        f"{xml_escape(facet)}, all on the same scale from {fmt_number(y_lo)} to "
        f"{fmt_number(y_hi)}. Each panel draws its own series in colour over every "
        f"other series in grey, so the panels compare rather than merely sit side by "
        f"side. Panels run largest last value first: "
        f"{xml_escape(', '.join(panels))}.</desc>"
    )
    parts.append(
        "<style>"
        ".panel{transition:opacity .15s ease;cursor:default;}"
        ".panel:hover,.panel:focus{opacity:.82;outline:none;}"
        "@media (prefers-reduced-motion: reduce){.panel{transition:none;}}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + foreground_tip_css(len(panels), mark_prefix="panel", tip_prefix="paneltip")
        + "@media (prefers-reduced-motion:reduce){.tip{transition:none}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="{left:.1f}" y="46" font-size="22" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(
        f'<text x="{left:.1f}" y="72" font-size="14" fill="{SECONDARY}">'
        f"{xml_escape(subtitle)}</text>"
    )
    if y_label:
        parts.append(
            f'<text x="{left:.1f}" y="100" font-size="12" fill="{SECONDARY}">'
            f"{xml_escape(y_label)}</text>"
        )

    y_ticks = [y_lo, (y_lo + y_hi) / 2.0, y_hi]
    tips: List[str] = []
    for index, name in enumerate(panels):
        ox, oy = cell_origin(index)
        row_i, col_i = divmod(index, n_cols)
        points = by_panel[name]
        drift = points[-1][1] - points[0][1]
        # Rounded, not raw: a drift of 0.4 prints as "0" and must not be
        # coloured as a rise the label does not show.
        rounded_drift = float(fmt_number(abs(drift)).replace(",", ""))
        if rounded_drift == 0:
            color = flat
        else:
            color = rising if drift > 0 else falling

        for value in y_ticks:
            gy = py(oy, value)
            parts.append(
                f'<line x1="{ox:.1f}" y1="{gy:.1f}" x2="{ox + cell_w:.1f}" y2="{gy:.1f}" '
                f'stroke="{GRIDLINE}" stroke-width="1"/>'
            )
            if col_i == 0:
                parts.append(
                    f'<text x="{ox - 10:.1f}" y="{gy + 4:.1f}" font-size="11" '
                    f'fill="{SECONDARY}" text-anchor="end" font-family="{mono_family}">'
                    f"{fmt_number(value)}</text>"
                )

        if context:
            for other in panels:
                if other == name:
                    continue
                parts.append(
                    f'<polyline points="{polyline(ox, oy, by_panel[other])}" fill="none" '
                    f'stroke="{GRIDLINE}" stroke-width="1.4" stroke-linejoin="round"/>'
                )

        parts.append(
            f'<polyline points="{polyline(ox, oy, points)}" fill="none" stroke="{color}" '
            f'stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>'
        )
        last_p, last_v = points[-1]
        first_v = points[0][1]
        parts.append(
            f'<circle cx="{px(ox, last_p):.1f}" cy="{py(oy, last_v):.1f}" r="3.6" '
            f'fill="{color}" stroke="{BG}" stroke-width="1.5"/>'
        )
        parts.append(
            f'<text x="{ox:.1f}" y="{oy - 10:.1f}" font-size="13" font-weight="700" '
            f'fill="{INK}">{xml_escape(name)}</text>'
        )
        change = last_v - first_v
        # "+0" is not a number anyone writes; a market that ended where it
        # started gets a plain 0 and keeps the sign for movement that happened.
        signed = (
            "0" if rounded_drift == 0 else f"{'+' if change > 0 else '−'}{fmt_number(abs(change))}"
        )
        parts.append(
            f'<text x="{ox + cell_w:.1f}" y="{oy - 10:.1f}" font-size="12" '
            f'fill="{color}" text-anchor="end" font-family="{mono_family}">'
            f"{signed}</text>"
        )

        if row_i == n_rows - 1 or index + n_cols >= len(panels):
            for position in (0, len(positions) - 1):
                parts.append(
                    f'<text x="{px(ox, position):.1f}" y="{oy + cell_h + 18:.1f}" '
                    f'font-size="11" fill="{SECONDARY}" text-anchor="'
                    f'{"start" if position == 0 else "end"}">'
                    f"{xml_escape(positions[position])}</text>"
                )

        parts.append(
            f'<rect id="panel-{index}" class="panel hit" tabindex="0" role="img" '
            f'aria-label="{xml_escape(name)}: {fmt_number(first_v)} to {fmt_number(last_v)}" '
            f'x="{ox:.1f}" y="{oy:.1f}" width="{cell_w:.1f}" height="{cell_h:.1f}" '
            f'fill="transparent"><title>{xml_escape(name)}: {fmt_number(first_v)} → '
            f"{fmt_number(last_v)}</title></rect>"
        )
        tips.append(
            tooltip_bubble(
                ox + cell_w / 2.0,
                oy + cell_h / 2.0,
                [
                    name,
                    f"{positions[0]} {fmt_number(first_v)} → {positions[-1]} {fmt_number(last_v)}",
                    f"{'up' if change >= 0 else 'down'} {fmt_number(abs(change))} over "
                    f"{len(positions)} {xml_escape(x)}s",
                ],
                canvas_w=width,
                canvas_h=height,
                ink=INK,
                secondary=SECONDARY,
                border=GRIDLINE,
                elem_id=f"paneltip-{index}",
            )
        )

    parts.extend(tips)
    if x_label:
        parts.append(
            f'<text x="{width / 2:.1f}" y="{height - 16:.1f}" font-size="12" '
            f'fill="{SECONDARY}" text-anchor="middle">{xml_escape(x_label)}</text>'
        )
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_facet(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Only two markets grew in every single month",
    subtitle: str = "Orders per market, indexed to 100 in January. Grey lines are the other markets.",
    width: int = 1000,
    height: int = 700,
    facet: str = "market",
    x: str = "month",
    y: str = "orders",
    columns: int = 0,
    context: bool = True,
    x_label: str = "",
    y_label: str = "Index (January = 100)",
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored small-multiples grid and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``market``, ``month`` and ``orders``, or whatever
        `facet`, `x` and `y` name. Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/facet.svg``.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    facet, x, y : str
        Which key splits the panels, orders the points, and is drawn.
    columns : int
        Panels per row; 0 picks a squarish grid.
    context : bool
        Draw the other groups behind each panel in grey.
    x_label, y_label : str
        Axis titles, written once for the grid.
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
    >>> p = make_facet()
    >>> p.exists()
    True
    """
    svg = build_svg(
        data,
        title=title,
        subtitle=subtitle,
        width=width,
        height=height,
        facet=facet,
        x=x,
        y=y,
        columns=columns,
        context=context,
        x_label=x_label,
        y_label=y_label,
        mode=mode,
        accessibility=accessibility,
        theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "facet")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "facet", build_svg, description="Generate a small-multiples grid.")


if __name__ == "__main__":
    main()
