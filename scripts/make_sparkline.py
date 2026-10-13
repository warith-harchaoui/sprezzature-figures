#!/usr/bin/env python3
"""
make_sparkline — a stack of word-sized lines, one metric each, no axes.

A sparkline is a line drawn small enough to sit in a sentence: no axes, no
gridlines, no legend, nothing but the shape. One on its own is a decoration;
the form earns its place as a *stack* of them, which is how a dashboard of
twenty metrics fits on one screen and still says something.

Not the same chart as `facet`, and the difference is the whole point. A
grid of panels puts every series on one scale so they can be compared;
a stack of sparklines gives each series its own, so each is read for its
own shape. Revenue in millions and error rate in percent belong on the
same page and never on the same axis.

What this does that most sparkline stacks do not
------------------------------------------------
* **The band is the usual range.** Behind each line sits the middle half
  of its own window -- first to third quartile -- so the line leaves the
  band exactly when the series is doing something out of the ordinary.
  Banding the whole row, which is what a first draft of this did, says
  nothing at all: the line is scaled to fill the row, so the band is
  always full.
* **The number that matters, written.** A shape with no value is an
  impression. Each row ends with its latest reading and its change over
  the window, so the stack is readable without hovering.
* **Direction is coloured, and called direction.** One line per row means
  colour can carry nothing else, so it carries the sign of the change, in
  the pair that survives colour-vision deficiency. The subtitle says it is
  direction and not judgement, because a stack like this mixes revenue
  with error rate and a reader will otherwise read blue as good news on a
  row where rising is the bad outcome.
* **No shared axis, said out loud.** The subtitle states that each row has
  its own scale -- the one thing a reader could otherwise get wrong, and
  the one thing no amount of care in the drawing can fix.

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

_WEEKS = 26


def _walk(start: float, drift: float, wobble: float, seed: int, shape: str = "drift") -> List[float]:
    """A deterministic series with a shape worth looking at.

    A plain random walk makes every sparkline look like every other
    sparkline, which would hide exactly what the figure is for. Each
    metric here gets a named shape -- a drift, a step, a spike, a seasonal
    swing -- so the stack shows what a stack is good at: that these nine
    series are not doing the same thing.
    """
    values: List[float] = []
    state = float(seed * 7919 % 1000) / 1000.0
    level = start
    for week in range(_WEEKS):
        state = (state * 1103515245 + 12345) % 1.0 if state else 0.37
        state = (math.sin(seed * 3.1 + week * 1.7) + 1.0) / 2.0
        noise = (state - 0.5) * wobble
        if shape == "step":
            level = start * (1.0 + (drift if week >= _WEEKS // 2 else 0.0))
        elif shape == "spike":
            level = start + (start * drift if week == _WEEKS - 6 else 0.0)
        elif shape == "season":
            level = start * (1.0 + drift * math.sin(week / _WEEKS * 4.0 * math.pi))
        else:
            level = start * (1.0 + drift * week / _WEEKS)
        values.append(round(level + noise, 2))
    return values


#: Nine metrics a team would actually have on one screen, in units that do
#: not share an axis: money, counts, percentages, milliseconds.
_METRICS: List[Tuple[str, str, List[float]]] = [
    ("Revenue", "k$", _walk(412.0, 0.34, 18.0, 3)),
    ("New signups", "", _walk(1840.0, 0.12, 120.0, 5)),
    ("Active teams", "", _walk(624.0, 0.21, 14.0, 7)),
    ("Churn", "%", _walk(3.4, -0.28, 0.22, 11)),
    ("p95 latency", "ms", _walk(238.0, 0.9, 11.0, 13, "spike")),
    ("Error rate", "%", _walk(0.42, 1.6, 0.05, 17, "step")),
    ("Support tickets", "", _walk(310.0, 0.0, 26.0, 19, "season")),
    ("Trial conversion", "%", _walk(18.6, 0.09, 0.9, 23)),
    ("Infra cost", "k$", _walk(96.0, 0.19, 3.0, 29)),
]

DEMO_DATA: List[Dict[str, Any]] = [
    {"metric": name, "week": week + 1, "value": value, "unit": unit}
    for name, unit, series in _METRICS
    for week, value in enumerate(series)
]


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Nine metrics, nine scales, one screen",
    subtitle: str = "Each row has its own scale; the grey band is its middle half. Blue rose, orange fell: direction, not judgement.",
    width: int = 920,
    height: int = 520,
    series: str = "metric",
    x: str = "week",
    y: str = "value",
    unit: str = "unit",
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full sparkline stack SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with a series key, a position key and a value key, named by
        `series`, `x` and `y`. An optional `unit` key is printed after the
        latest reading. Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    series, x, y, unit : str
        Which keys name the row, order the points, carry the value and
        (optionally) the unit.
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
    rising = palette.get("Blue", "#007AFF")
    falling = palette.get("Orange", "#FF9500")

    order: List[str] = []
    points: Dict[str, List[Tuple[float, float]]] = {}
    units: Dict[str, str] = {}
    for row in rows:
        name = str(row[series])
        if name not in points:
            order.append(name)
            points[name] = []
        points[name].append((float(row[x]), float(row[y])))
        units.setdefault(name, str(row.get(unit, "") or ""))
    for values in points.values():
        values.sort()

    top = 118.0
    label_w, spark_w = 150.0, 330.0
    left = 56.0
    row_h = min(38.0, (height - top - 44.0) / max(len(order), 1))
    spark_h = row_h - 12.0

    parts: List[str] = []
    parts.append(
        svg_open(width, height, "spark-title", "spark-desc",
                 font_family=chrome_stack_for_theme(theme))
    )
    parts.append(f'<title id="spark-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="spark-desc">{len(order)} sparklines stacked, one metric per row, each on '
        f'its own vertical scale over {len(points[order[0]]) if order else 0} periods. Behind '
        f'each line is a pale band from that metric\'s own minimum to its own maximum, and the '
        f'last point is marked. Each row ends with its latest reading and its change over the '
        f'window.</desc>'
    )
    parts.append(
        "<style>"
        ".sparkrow{cursor:default;}"
        ".sparkrow:hover,.sparkrow:focus{outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + foreground_tip_css(len(order), mark_prefix="sparkrow", tip_prefix="sparktip")
        + "@media (prefers-reduced-motion:reduce){.tip{transition:none}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="{left:.1f}" y="48" font-size="22" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(
        f'<text x="{left:.1f}" y="74" font-size="14" fill="{SECONDARY}">'
        f'{xml_escape(subtitle)}</text>'
    )
    parts.append(
        f'<text x="{left + label_w:.1f}" y="104" font-size="11" fill="{SECONDARY}">'
        f'Last {len(points[order[0]]) if order else 0} periods</text>'
    )
    parts.append(
        f'<text x="{left + label_w + spark_w + 86:.1f}" y="104" font-size="11" '
        f'fill="{SECONDARY}" text-anchor="end">Latest</text>'
    )
    parts.append(
        f'<text x="{width - 44:.1f}" y="104" font-size="11" fill="{SECONDARY}" '
        f'text-anchor="end">Change</text>'
    )

    def px(position: float, first: float, last: float) -> float:
        """Horizontal position of a point inside a row's sparkline."""
        return left + label_w + (position - first) / ((last - first) or 1.0) * spark_w

    def py(value: float, row_y: float, lo: float, span: float) -> float:
        """Vertical position of a value inside a row, on that row's own scale."""
        return row_y + spark_h - (value - lo) / span * spark_h

    tips: List[str] = []
    for index, name in enumerate(order):
        values = points[name]
        row_y = top + index * row_h
        lo = min(v for _, v in values)
        hi = max(v for _, v in values)
        span = (hi - lo) or 1.0
        first, last = values[0][1], values[-1][1]
        change = last - first
        colour = rising if change >= 0 else falling


        # The band is the series' usual range -- the middle half of the
        # window, between its first and third quartiles. The first render
        # banded the whole row instead, which is the same thing as the row
        # itself: the line is scaled to fill it, so the band could never be
        # anything but full, and it said nothing. Banding the middle half
        # makes the line leave the band exactly when the series is doing
        # something unusual, which is the one question a chart this small
        # can answer.
        ordered = sorted(v for _, v in values)
        q1 = ordered[len(ordered) // 4]
        q3 = ordered[min(len(ordered) * 3 // 4, len(ordered) - 1)]
        parts.append(
            f'<rect x="{left + label_w:.1f}" y="{py(q3, row_y, lo, span):.1f}" '
            f'width="{spark_w:.1f}" '
            f'height="{max(py(q1, row_y, lo, span) - py(q3, row_y, lo, span), 1.5):.1f}" '
            f'fill="{GRIDLINE}" opacity="0.8"/>'
        )
        parts.append(
            f'<text x="{left + label_w - 12:.1f}" y="{row_y + spark_h / 2 + 4:.1f}" '
            f'font-size="12" fill="{INK}" text-anchor="end">{xml_escape(name)}</text>'
        )
        first_p, last_p = values[0][0], values[-1][0]
        line = " ".join(
            f"{px(p, first_p, last_p):.1f},{py(v, row_y, lo, span):.1f}"
            for p, v in values
        )
        parts.append(
            f'<polyline points="{line}" fill="none" stroke="{colour}" stroke-width="1.6" '
            f'stroke-linejoin="round" stroke-linecap="round"/>'
        )
        parts.append(
            f'<circle cx="{px(last_p, first_p, last_p):.1f}" '
            f'cy="{py(last, row_y, lo, span):.1f}" r="2.8" fill="{colour}"/>'
        )

        measure = units.get(name, "")
        latest = f"{fmt_number(last)}{(' ' + measure) if measure and measure != '%' else measure}"
        parts.append(
            f'<text x="{left + label_w + spark_w + 86:.1f}" y="{row_y + spark_h / 2 + 4:.1f}" '
            f'font-size="12" fill="{INK}" text-anchor="end" font-family="{mono_family}">'
            f'{xml_escape(latest)}</text>'
        )
        shown = fmt_number(abs(change))
        signed = "0" if float(shown.replace(",", "")) == 0 else (
            f'{"+" if change > 0 else "−"}{shown}'
        )
        parts.append(
            f'<text x="{width - 44:.1f}" y="{row_y + spark_h / 2 + 4:.1f}" font-size="12" '
            f'fill="{colour}" text-anchor="end" font-family="{mono_family}">{signed}</text>'
        )
        parts.append(
            f'<rect id="sparkrow-{index}" class="sparkrow hit" tabindex="0" role="img" '
            f'aria-label="{xml_escape(name)}: latest {xml_escape(latest)}, '
            f'{"up" if change > 0 else "down" if change < 0 else "unchanged"} '
            f'{fmt_number(abs(change))} over the window" '
            f'x="{left:.1f}" y="{row_y:.1f}" width="{width - left - 36:.1f}" '
            f'height="{spark_h:.1f}" fill="transparent">'
            f'<title>{xml_escape(name)}: {xml_escape(latest)}</title></rect>'
        )
        tips.append(
            tooltip_bubble(
                left + label_w + spark_w / 2, row_y + spark_h,
                [
                    name,
                    f"latest {latest} · range {fmt_number(lo)} to {fmt_number(hi)}",
                    f"{signed} over {len(values)} periods",
                ],
                canvas_w=width, canvas_h=height, ink=INK, secondary=SECONDARY,
                border=GRIDLINE, elem_id=f"sparktip-{index}",
            )
        )

    parts.extend(tips)
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_sparkline(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Nine metrics, nine scales, one screen",
    subtitle: str = "Each row has its own scale; the grey band is its middle half. Blue rose, orange fell: direction, not judgement.",
    width: int = 920,
    height: int = 520,
    series: str = "metric",
    x: str = "week",
    y: str = "value",
    unit: str = "unit",
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored sparkline stack and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``metric``, ``week``, ``value`` and optionally
        ``unit``, or whatever `series`, `x`, `y` and `unit` name. Defaults
        to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/sparkline.svg``.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    series, x, y, unit : str
        Which keys name the row, order the points, carry the value and the unit.
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
    >>> p = make_sparkline()
    >>> p.exists()
    True
    """
    svg = build_svg(
        data, title=title, subtitle=subtitle, width=width, height=height,
        series=series, x=x, y=y, unit=unit, mode=mode,
        accessibility=accessibility, theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "sparkline")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "sparkline", build_svg, description="Generate a stack of sparklines.")


if __name__ == "__main__":
    main()
