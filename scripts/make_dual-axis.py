#!/usr/bin/env python3
"""
make_dual_axis — two series, two units, one frame, and the caveat printed.

The combo chart: bars on a left axis, a line on a right one. It has a bad
reputation and most of it is deserved. Two independent scales can be slid
against each other until any two series appear to move together, and the
place where the line crosses the bars is a consequence of that sliding and
not a fact about the data. Plenty of published charts have made exactly
that claim by accident.

It is also, sometimes, the right chart: revenue in thousands and
conversion in percent genuinely do not share an axis, and putting them on
separate figures costs the reader the one thing they came for, which is
whether the two moved together.

So this draws it, and answers the objection on the figure rather than in a
footnote nobody reads.

How the objection is answered
-----------------------------
* **Both axes start at zero unless told otherwise.** A dual axis with two
  floating baselines is the version that can be made to show anything.
  ``zero_anchored=False`` is available and says so on the figure when used.
* **The caveat is printed, not implied.** One line under the chrome:
  where the line meets the bars follows from two scales, not from the
  data. It is the sentence a reader needs and the one that always gets
  left out.
* **Each axis is coloured like its series.** Not a legend to cross-check:
  the left ticks are the colour of the bars and the right ticks the colour
  of the line, so no reader ever has to work out which axis is which.
* **The correlation, computed.** If the two series really do move
  together, the figure says by how much, with Pearson's r over the window
  -- a number the reader can judge, rather than an impression the chart
  can manufacture.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _style import BG, GRIDLINE, INK, SECONDARY, load_palette  # noqa: E402
from _svg import (  # noqa: E402
    bar_path,
    fmt_number,
    foreground_tip_css,
    svg_open,
    tooltip_bubble,
    xml_escape,
)
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

#: Twelve months of a business that grew its revenue and lost ground on
#: conversion -- the pair a combo chart is reached for, and the pair most
#: likely to be misread as "growth caused the slip".
DEMO_DATA: List[Dict[str, Any]] = [
    {"month": "Jan", "revenue": 412, "conversion": 4.6},
    {"month": "Feb", "revenue": 438, "conversion": 4.5},
    {"month": "Mar", "revenue": 471, "conversion": 4.4},
    {"month": "Apr", "revenue": 455, "conversion": 4.4},
    {"month": "May", "revenue": 503, "conversion": 4.1},
    {"month": "Jun", "revenue": 548, "conversion": 4.0},
    {"month": "Jul", "revenue": 572, "conversion": 3.8},
    {"month": "Aug", "revenue": 559, "conversion": 3.9},
    {"month": "Sep", "revenue": 611, "conversion": 3.6},
    {"month": "Oct", "revenue": 648, "conversion": 3.5},
    {"month": "Nov", "revenue": 693, "conversion": 3.3},
    {"month": "Dec", "revenue": 741, "conversion": 3.2},
]


def _axis_top(value: float, intervals: int = 4) -> float:
    """A ceiling that divides into `intervals` round steps.

    Rounding the ceiling alone is not enough, and the first render of this
    figure showed why: a maximum of 4.6 rounds up to a tidy 5, and 5 over
    four gridlines is a step of 1.25, printed as 1.2, 2.5, 3.8 -- labels
    rounded onto positions that are exact, which is a label that lies by a
    pixel and by a tenth. Rounding the *step* instead and multiplying back
    gives 1.5 and a ceiling of 6: every tick lands on a number that is both
    round and true.
    """
    if value <= 0:
        return float(intervals)
    target = value / intervals
    magnitude = 10.0 ** math.floor(math.log10(target))
    for step in (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 7.5, 10.0):
        if target <= step * magnitude:
            return step * magnitude * intervals
    return 10.0 * magnitude * intervals


def _pearson(xs: List[float], ys: List[float]) -> Optional[float]:
    """Pearson's r, or None when a series does not vary enough to have one."""
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((v - mx) ** 2 for v in xs)
    syy = sum((v - my) ** 2 for v in ys)
    if sxx <= 0 or syy <= 0:
        return None
    sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys, strict=True))
    return sxy / math.sqrt(sxx * syy)


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Revenue up 80% over the year, trial conversion down a third",
    subtitle: str = "Monthly revenue and trial conversion. Two scales, so where the line meets the bars means nothing.",
    width: int = 900,
    height: int = 560,
    x: str = "month",
    bars: str = "revenue",
    line: str = "conversion",
    bars_label: str = "Revenue (k$)",
    line_label: str = "Trial conversion (%)",
    x_label: str = "",
    zero_anchored: bool = True,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full dual-axis combo SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with a position key and two numeric keys, named by `x`,
        `bars` and `line`. Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    x, bars, line : str
        Which key orders the points, which is drawn as bars on the left
        axis, and which as a line on the right.
    bars_label, line_label, x_label : str
        Axis titles. The two value labels are drawn in their series'
        colour, which is what removes the legend.
    zero_anchored : bool
        Start both value axes at zero. Turning it off is the version of
        this chart that can be made to show anything, so the figure says
        on itself when it is off.
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
    palette = load_palette(accessibility, theme=theme)
    bar_colour = palette.get("Blue", "#007AFF")
    line_colour = palette.get("Orange", "#FF9500")

    labels = [str(r[x]) for r in rows]
    bar_values = [float(r[bars]) for r in rows]
    line_values = [float(r[line]) for r in rows]

    if zero_anchored:
        bar_lo, bar_hi = 0.0, _axis_top(max(bar_values))
        line_lo, line_hi = 0.0, _axis_top(max(line_values))
    else:
        bar_lo, bar_hi = min(bar_values) * 0.92, _axis_top(max(bar_values))
        line_lo, line_hi = min(line_values) * 0.92, _axis_top(max(line_values))

    plot_x, plot_y = 78.0, 150.0
    right_margin, bottom_margin = 86.0, 74.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_margin
    slot = plot_w / max(len(rows), 1)
    bar_w = slot * 0.58

    def bar_y(value: float) -> float:
        return plot_y + plot_h - (value - bar_lo) / ((bar_hi - bar_lo) or 1.0) * plot_h

    def line_y(value: float) -> float:
        return plot_y + plot_h - (value - line_lo) / ((line_hi - line_lo) or 1.0) * plot_h

    def centre(index: int) -> float:
        return plot_x + (index + 0.5) * slot

    r = _pearson(bar_values, line_values)

    parts: List[str] = []
    parts.append(
        svg_open(width, height, "dual-title", "dual-desc",
                 font_family=chrome_stack_for_theme(theme))
    )
    parts.append(f'<title id="dual-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="dual-desc">A combo chart of {len(rows)} periods. '
        f'{xml_escape(bars_label)} is drawn as bars against the left axis, from '
        f'{fmt_number(bar_lo)} to {fmt_number(bar_hi)}; {xml_escape(line_label)} as a line '
        f'against the right axis, from {fmt_number(line_lo)} to {fmt_number(line_hi)}. The '
        f'two axes are independent, so the point where the line meets the bars carries no '
        f'meaning.'
        + (f' Pearson correlation over the window is {r:+.2f}.' if r is not None else "")
        + '</desc>'
    )
    parts.append(
        "<style>"
        ".slot{cursor:default;}"
        ".slot:hover,.slot:focus{outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + foreground_tip_css(len(rows), mark_prefix="slot", tip_prefix="slottip")
        + "@media (prefers-reduced-motion:reduce){.tip{transition:none}}"
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
    # The caveat belongs on the figure. A dual axis is read in seconds and
    # the footnote that would have qualified it is read by nobody.
    anchoring = (
        "Both axes start at zero."
        if zero_anchored
        else "Neither axis starts at zero, so the gap between the two series is a choice."
    )
    correlation = (
        f" Pearson r over these {len(rows)} periods: {r:+.2f}." if r is not None else ""
    )
    parts.append(
        f'<text x="{plot_x:.1f}" y="98" font-size="12" fill="{SECONDARY}" '
        f'font-family="{mono_family}">{xml_escape(anchoring + correlation)}</text>'
    )
    # Axis titles in their series' colour: that is the legend, removed.
    parts.append(
        f'<text x="{plot_x:.1f}" y="{plot_y - 16:.1f}" font-size="12" font-weight="700" '
        f'fill="{bar_colour}">{xml_escape(bars_label)}</text>'
    )
    parts.append(
        f'<text x="{plot_x + plot_w:.1f}" y="{plot_y - 16:.1f}" font-size="12" '
        f'font-weight="700" fill="{line_colour}" text-anchor="end">'
        f'{xml_escape(line_label)}</text>'
    )

    # ---- gridlines and the two value axes ----
    for step in range(5):
        fraction = step / 4.0
        gy = plot_y + plot_h - fraction * plot_h
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{gy:.1f}" x2="{plot_x + plot_w:.1f}" y2="{gy:.1f}" '
            f'stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{gy + 4:.1f}" font-size="11" fill="{bar_colour}" '
            f'text-anchor="end" font-family="{mono_family}">'
            f'{fmt_number(bar_lo + fraction * (bar_hi - bar_lo))}</text>'
        )
        parts.append(
            f'<text x="{plot_x + plot_w + 10:.1f}" y="{gy + 4:.1f}" font-size="11" '
            f'fill="{line_colour}" font-family="{mono_family}">'
            f'{fmt_number(line_lo + fraction * (line_hi - line_lo))}</text>'
        )

    tips: List[str] = []
    for index in range(len(rows)):
        value = bar_values[index]
        top = bar_y(value)
        parts.append(
            f'<path d="{bar_path(centre(index) - bar_w / 2, top, bar_w, plot_y + plot_h - top, 3)}" '
            f'fill="{bar_colour}" opacity="0.88"/>'
        )
        parts.append(
            f'<text x="{centre(index):.1f}" y="{plot_y + plot_h + 20:.1f}" font-size="11" '
            f'fill="{SECONDARY}" text-anchor="middle">{xml_escape(labels[index])}</text>'
        )

    polyline = " ".join(
        f"{centre(i):.1f},{line_y(v):.1f}" for i, v in enumerate(line_values)
    )
    parts.append(
        f'<polyline points="{polyline}" fill="none" stroke="{line_colour}" stroke-width="2.6" '
        f'stroke-linejoin="round" stroke-linecap="round"/>'
    )
    for index, value in enumerate(line_values):
        parts.append(
            f'<circle cx="{centre(index):.1f}" cy="{line_y(value):.1f}" r="3.4" '
            f'fill="{line_colour}" stroke="{BG}" stroke-width="1.4"/>'
        )

    for index in range(len(rows)):
        parts.append(
            f'<rect id="slot-{index}" class="slot hit" tabindex="0" role="img" '
            f'aria-label="{xml_escape(labels[index])}: {xml_escape(bars_label)} '
            f'{fmt_number(bar_values[index])}, {xml_escape(line_label)} '
            f'{fmt_number(line_values[index])}" '
            f'x="{plot_x + index * slot:.1f}" y="{plot_y:.1f}" width="{slot:.1f}" '
            f'height="{plot_h:.1f}" fill="transparent">'
            f'<title>{xml_escape(labels[index])}: {fmt_number(bar_values[index])} · '
            f'{fmt_number(line_values[index])}</title></rect>'
        )
        tips.append(
            tooltip_bubble(
                centre(index), bar_y(bar_values[index]),
                [
                    labels[index],
                    f"{bars_label}: {fmt_number(bar_values[index])}",
                    f"{line_label}: {fmt_number(line_values[index])}",
                ],
                canvas_w=width, canvas_h=height, ink=INK, secondary=SECONDARY,
                border=GRIDLINE, elem_id=f"slottip-{index}",
            )
        )

    parts.extend(tips)
    if x_label:
        parts.append(
            f'<text x="{plot_x + plot_w / 2:.1f}" y="{height - 20:.1f}" font-size="12" '
            f'fill="{SECONDARY}" text-anchor="middle">{xml_escape(x_label)}</text>'
        )
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_dual_axis(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Revenue up 80% over the year, trial conversion down a third",
    subtitle: str = "Monthly revenue and trial conversion. Two scales, so where the line meets the bars means nothing.",
    width: int = 900,
    height: int = 560,
    x: str = "month",
    bars: str = "revenue",
    line: str = "conversion",
    bars_label: str = "Revenue (k$)",
    line_label: str = "Trial conversion (%)",
    x_label: str = "",
    zero_anchored: bool = True,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored dual-axis combo chart and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``month``, ``revenue`` and ``conversion``, or
        whatever `x`, `bars` and `line` name. Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/dual-axis.svg``.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    x, bars, line : str
        Which keys order the points and supply the two series.
    bars_label, line_label, x_label : str
        Axis titles, drawn in their series' colour.
    zero_anchored : bool
        Start both value axes at zero.
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
    >>> p = make_dual_axis()
    >>> p.exists()
    True
    """
    svg = build_svg(
        data, title=title, subtitle=subtitle, width=width, height=height,
        x=x, bars=bars, line=line, bars_label=bars_label, line_label=line_label,
        x_label=x_label, zero_anchored=zero_anchored, mode=mode,
        accessibility=accessibility, theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "dual-axis")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "dual-axis", build_svg, description="Generate a dual-axis combo chart.")


if __name__ == "__main__":
    main()
