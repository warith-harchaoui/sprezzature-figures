#!/usr/bin/env python3
"""
make_forecast-fan — a forecast drawn with the width of its own uncertainty.

History on the left in solid ink, the forecast on the right as a dashed
line inside nested intervals that widen with the horizon. The widening is
the point: a forecast is a distribution, and a fan chart is the only
common chart that draws one over time instead of collapsing it to a line.

Where the usual fan chart goes wrong
------------------------------------
* **History and forecast are drawn in the same ink.** A reader cannot see
  where measurement stops and projection starts, which is the single most
  important boundary on the chart. Here the forecast is dashed, the
  boundary is ruled and labelled, and the last observed value is marked.
* **The bands are shaded and never named.** Readers take the outer edge
  for "the worst case" when a 95% interval says the opposite: one time in
  forty the outcome falls below it. Each band carries its level at the
  right edge, and the chrome spells out what the level means in a
  sentence rather than a percentage sign.
* **The fan's width is never anchored to a number.** "It gets wider"
  is not a decision. The chrome reports the interval at the final
  horizon in data units and as a share of the point forecast, which is
  the figure a reader is actually about to act on.

The intervals are computed here from a forecast and its standard error,
one column each, so the levels drawn are a presentation choice rather
than something baked into the data. A caller holding explicit bounds
instead of a standard error can pass ``se = (upper - forecast) / 1.96``
for a 95% bound and get the same picture.

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
from _scale import nice_ticks_range  # noqa: E402
from _style import BG, GRIDLINE, INK, SECONDARY, load_palette  # noqa: E402
from _svg import (  # noqa: E402
    fmt_number,
    foreground_tip_css,
    svg_open,
    tooltip_bubble,
    wrap_no_orphan,
    xml_escape,
)
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

_HISTORY = 36
_HORIZON = 12


def _series(seed: int = 19) -> List[Dict[str, Any]]:
    """Three years of monthly subscriptions, then a year of forecast.

    The standard error grows as the square root of the horizon, which is
    what a random walk does and what makes the fan a fan rather than a
    wedge. It is also the reason the figure can make a claim a reader can
    check without a calculator: four times the horizon is twice the
    interval, so month 12 is exactly twice as uncertain as month 3.
    """
    rng = random.Random(seed)
    rows: List[Dict[str, Any]] = []
    level = 1180.0
    for index in range(_HISTORY):
        level += 11.0 + (rng.random() - 0.5) * 46.0
        rows.append(
            {
                "month": index + 1,
                "subscriptions": round(level, 1),
                "forecast": None,
                "se": None,
            }
        )
    step = 11.0
    for horizon in range(1, _HORIZON + 1):
        rows.append(
            {
                "month": _HISTORY + horizon,
                "subscriptions": None,
                "forecast": round(level + step * horizon, 1),
                "se": round(24.0 * math.sqrt(horizon), 2),
            }
        )
    return rows


DEMO_DATA: List[Dict[str, Any]] = _series()


def _normal_quantile(probability: float) -> float:
    """The inverse normal CDF, by Acklam's rational approximation.

    Written out rather than tabled for the usual levels, because the set
    of bands is an option: a reader who asks for a 67% interval should
    get a 67% interval, not the nearest one somebody pre-computed.
    Accurate to about 1.15e-9 across the open unit interval, which is
    several digits more than a chart can draw.
    """
    if not 0.0 < probability < 1.0:
        raise ValueError(
            f"a quantile needs a probability strictly inside 0 and 1, got {probability}"
        )
    a = (
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    )
    b = (
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    )
    c = (
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    )
    d = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00, 3.754408661907416e00)
    low, high = 0.02425, 1.0 - 0.02425
    if probability < low:
        q = math.sqrt(-2.0 * math.log(probability))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        )
    if probability > high:
        q = math.sqrt(-2.0 * math.log(1.0 - probability))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        )
    q = probability - 0.5
    r = q * q
    return (
        (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5])
        * q
        / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
    )


def _z_for(level: float) -> float:
    """The multiplier for a two-sided interval at `level` percent."""
    if not 0.0 < level < 100.0:
        raise ValueError(
            f"an interval level is a percentage strictly inside 0 and 100, got {level}"
        )
    return _normal_quantile(0.5 + level / 200.0)


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Twelve months out, the interval is twice as wide as at three",
    subtitle: str = "Three years of monthly subscriptions, then a year of forecast drawn at the width of its uncertainty.",
    width: int = 900,
    height: int = 610,
    x: str = "month",
    y: str = "subscriptions",
    forecast_key: str = "forecast",
    se_key: str = "se",
    levels: Optional[List[str]] = None,
    anchor_level: float = 80.0,
    history_label: str = "Observed",
    forecast_label: str = "Forecast",
    boundary_label: str = "forecast starts",
    x_label: str = "Month",
    y_label: str = "Subscriptions",
    band_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full fan chart SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        One row per period. History rows carry `y`; forecast rows carry
        `forecast_key` and `se_key`. Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    x, y : str
        Row keys for the time axis and the observed value.
    forecast_key, se_key : str
        Row keys for the point forecast and its standard error.
    levels : list of str or None
        Interval levels to draw, as percentages, widest last. ``None``
        draws 50, 80 and 95.
    anchor_level : float
        Which level, as a percentage, the chrome quotes at the final
        horizon.
    history_label, forecast_label : str
        Names for the two halves of the line.
    boundary_label : str
        Caption on the rule between the last observation and the first
        forecast.
    x_label, y_label : str
        Axis titles.
    band_note, finding : str or None
        The sentence explaining what a level means, and the one quoting
        the interval at the horizon; ``None`` composes each from the data.
    mode : str
        ``"self-contained"`` keeps the interactive chrome inside the file.
    accessibility : str
        Palette variant.
    theme : str
        Visual theme.

    Returns
    -------
    str
        The SVG document.
    """
    rows = list(data if data else DEMO_DATA)
    if not rows:
        raise ValueError("a fan chart needs at least one row")

    def position(row: Dict[str, Any]) -> Tuple[int, float, str]:
        """Sort key that works for a period number and for "2026-01" alike."""
        raw = row[x]
        try:
            return (0, float(raw), "")
        except (TypeError, ValueError):
            return (1, 0.0, str(raw))

    rows.sort(key=position)
    labels = [str(row[x]) for row in rows]
    history = [(index, float(row[y])) for index, row in enumerate(rows) if row.get(y) is not None]
    future = [
        (index, float(row[forecast_key]), float(row[se_key]))
        for index, row in enumerate(rows)
        if row.get(forecast_key) is not None and row.get(se_key) is not None
    ]
    if not history:
        raise ValueError(f"no row carries an observed value under {y!r}")
    if not future:
        raise ValueError(
            f"no row carries both a forecast under {forecast_key!r} and a standard "
            f"error under {se_key!r}; without them there is no fan to draw"
        )

    wanted = levels if levels else ["50", "80", "95"]
    bands = sorted(
        ((float(level), _z_for(float(level))) for level in wanted), key=lambda pair: pair[0]
    )
    widest = bands[-1]

    mono_family = mono_stack_for_theme(theme)
    palette = load_palette(accessibility, theme=theme)
    observed_ink = palette.get("Blue", "#007AFF")
    forecast_ink = palette.get("Orange", "#FF9500")

    low = min([value for _, value in history] + [point - widest[1] * se for _, point, se in future])
    high = max(
        [value for _, value in history] + [point + widest[1] * se for _, point, se in future]
    )
    ticks = nice_ticks_range(low, high, 5)
    axis_low, axis_high = ticks[0], ticks[-1]

    plot_x = 96.0
    plot_y = 202.0
    plot_w = width - plot_x - 104.0
    plot_h = height - plot_y - 92.0
    n = len(rows)

    def px(index: int) -> float:
        return plot_x + index / max(n - 1, 1) * plot_w

    def py(value: float) -> float:
        return plot_y + plot_h - (value - axis_low) / (axis_high - axis_low) * plot_h

    last_index, last_value = history[-1]
    # The fan is anchored on the last observation: at horizon zero the
    # interval has no width, and starting the bands one period later
    # leaves a visible notch that reads as a jump in the forecast.
    joined = [(last_index, last_value, 0.0)] + future
    horizon_index, horizon_point, horizon_se = future[-1]

    anchor_z = _z_for(anchor_level)
    anchor_low = horizon_point - anchor_z * horizon_se
    anchor_high = horizon_point + anchor_z * horizon_se
    share = (anchor_z * horizon_se) / horizon_point if horizon_point else 0.0

    said_bands = (
        band_note
        if band_note is not None
        else (
            f"bands are {', '.join(fmt_number(level) for level, _ in bands)}% intervals: "
            f"{fmt_number(100.0 - widest[0])} times in 100 the outcome falls outside the "
            f"widest one"
        )
    )
    said_parts: List[str] = []
    if finding is not None:
        said_parts.append(finding)
    else:
        said_parts.append(
            f"{len(future)} periods out, the {fmt_number(anchor_level)}% interval runs "
            f"{fmt_number(anchor_low)} to {fmt_number(anchor_high)}: plus or minus "
            f"{fmt_number(share * 100.0)}% of the {fmt_number(horizon_point)} forecast."
        )
    said_lines: List[str] = []
    for sentence in said_parts:
        said_lines.extend(wrap_no_orphan(sentence, 98))

    parts: List[str] = []
    parts.append(
        svg_open(width, height, "fan-title", "fan-desc", font_family=chrome_stack_for_theme(theme))
    )
    parts.append(f'<title id="fan-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="fan-desc">A fan chart: {len(history)} observed periods from '
        f"{xml_escape(labels[history[0][0]])} to {xml_escape(labels[last_index])}, then "
        f"{len(future)} forecast periods to {xml_escape(labels[horizon_index])}, each "
        f"drawn inside nested intervals that widen with the horizon. "
        f"{xml_escape(said_bands)}. {xml_escape(' '.join(said_parts))}</desc>"
    )
    parts.append(
        "<style>"
        ".pt{cursor:default;}"
        ".pt:hover,.pt:focus{outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + foreground_tip_css(n, mark_prefix="pt", tip_prefix="pttip")
        + "@media (prefers-reduced-motion:reduce){.tip{transition:none}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="{plot_x - 64:.1f}" y="46" font-size="22" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    for line_index, line in enumerate(wrap_no_orphan(subtitle, 104)[:2]):
        parts.append(
            f'<text x="{plot_x - 64:.1f}" y="{72 + line_index * 20:.1f}" font-size="14" '
            f'fill="{SECONDARY}">{xml_escape(line)}</text>'
        )
    parts.append(
        f'<text x="{plot_x - 64:.1f}" y="124" font-size="12" fill="{SECONDARY}" '
        f'font-family="{mono_family}">{xml_escape(said_bands)}</text>'
    )
    for line_index, line in enumerate(said_lines[:2]):
        parts.append(
            f'<text x="{plot_x - 64:.1f}" y="{144 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(line)}</text>'
        )

    for tick in ticks:
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{py(tick):.1f}" x2="{plot_x + plot_w:.1f}" '
            f'y2="{py(tick):.1f}" stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{py(tick) + 4:.1f}" font-size="11" '
            f'fill="{SECONDARY}" text-anchor="end" font-family="{mono_family}">'
            f"{fmt_number(tick)}</text>"
        )

    # Widest band first, so the narrower ones sit on top and read darker.
    for band_index, (level, z) in enumerate(reversed(bands)):
        upper = " ".join(
            f"{'M' if step == 0 else 'L'}{px(index):.1f},{py(point + z * se):.1f}"
            for step, (index, point, se) in enumerate(joined)
        )
        lower = " ".join(
            f"L{px(index):.1f},{py(point - z * se):.1f}" for index, point, se in reversed(joined)
        )
        opacity = 0.10 + 0.09 * band_index
        parts.append(f'<path d="{upper} {lower} Z" fill="{forecast_ink}" opacity="{opacity:.2f}"/>')
        edge = py(horizon_point + z * horizon_se)
        parts.append(
            f'<text x="{px(horizon_index) + 8:.1f}" y="{edge + 4:.1f}" font-size="11" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{fmt_number(level)}%</text>'
        )

    parts.append(
        f'<line x1="{px(last_index):.1f}" y1="{plot_y:.1f}" x2="{px(last_index):.1f}" '
        f'y2="{plot_y + plot_h:.1f}" stroke="{INK}" stroke-width="1" '
        f'stroke-dasharray="3 3" opacity="0.5"/>'
    )
    parts.append(
        f'<text x="{px(last_index) + 6:.1f}" y="{plot_y - 8:.1f}" font-size="11" '
        f'fill="{SECONDARY}">{xml_escape(boundary_label)}</text>'
    )

    observed_path = " ".join(
        f"{'M' if step == 0 else 'L'}{px(index):.1f},{py(value):.1f}"
        for step, (index, value) in enumerate(history)
    )
    parts.append(
        f'<path d="{observed_path}" fill="none" stroke="{observed_ink}" stroke-width="2.4" '
        f'stroke-linejoin="round"/>'
    )
    forecast_path = " ".join(
        f"{'M' if step == 0 else 'L'}{px(index):.1f},{py(point):.1f}"
        for step, (index, point, _) in enumerate(joined)
    )
    parts.append(
        f'<path d="{forecast_path}" fill="none" stroke="{forecast_ink}" stroke-width="2.4" '
        f'stroke-dasharray="6 4" stroke-linejoin="round"/>'
    )
    parts.append(
        f'<circle cx="{px(last_index):.1f}" cy="{py(last_value):.1f}" r="4" fill="{observed_ink}"/>'
    )

    # Both labels are placed against their own series rather than in a
    # corner: the first draft put "Observed" under the axis title and
    # "Forecast" inside the fan, where each sat on top of something else.
    anchor_history = history[len(history) // 3]
    parts.append(
        f'<text x="{px(anchor_history[0]):.1f}" y="{py(anchor_history[1]) - 12:.1f}" '
        f'font-size="12" font-weight="700" fill="{observed_ink}">'
        f"{xml_escape(history_label)}</text>"
    )
    middle = joined[len(joined) // 2]
    parts.append(
        f'<text x="{px(middle[0]):.1f}" y="{py(middle[1] + widest[1] * middle[2]) - 10:.1f}" '
        f'font-size="12" font-weight="700" fill="{forecast_ink}" text-anchor="middle">'
        f"{xml_escape(forecast_label)}</text>"
    )

    step_x = max(1, n // 12)
    for index in range(0, n, step_x):
        parts.append(
            f'<text x="{px(index):.1f}" y="{plot_y + plot_h + 20:.1f}" font-size="11" '
            f'fill="{SECONDARY}" text-anchor="middle" font-family="{mono_family}">'
            f"{xml_escape(labels[index])}</text>"
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{plot_y + plot_h + 46:.1f}" '
        f'font-size="12" fill="{SECONDARY}" text-anchor="middle">{xml_escape(x_label)}</text>'
    )
    parts.append(
        f'<text x="{plot_x - 64:.1f}" y="{plot_y - 8:.1f}" font-size="12" '
        f'fill="{SECONDARY}">{xml_escape(y_label)}</text>'
    )

    tips: List[str] = []
    for index, row in enumerate(rows):
        observed = row.get(y)
        point = row.get(forecast_key)
        if observed is not None:
            value = float(observed)
            caption = [f"{history_label} · {labels[index]}", fmt_number(value)]
        elif point is not None and row.get(se_key) is not None:
            value = float(point)
            se = float(row[se_key])
            caption = [
                f"{forecast_label} · {labels[index]}",
                fmt_number(value),
                f"{fmt_number(anchor_level)}%: {fmt_number(value - anchor_z * se)} "
                f"to {fmt_number(value + anchor_z * se)}",
            ]
        else:
            continue
        element = len(tips)
        parts.append(
            f'<rect id="pt-{element}" class="pt hit" tabindex="0" role="img" '
            f'aria-label="{xml_escape(" · ".join(caption))}" '
            f'x="{px(index) - 6:.1f}" y="{plot_y:.1f}" width="12" height="{plot_h:.1f}" '
            f'fill="transparent"><title>{xml_escape(labels[index])}: '
            f"{fmt_number(value)}</title></rect>"
        )
        tips.append(
            tooltip_bubble(
                px(index),
                py(value),
                caption,
                canvas_w=width,
                canvas_h=height,
                ink=INK,
                secondary=SECONDARY,
                border=GRIDLINE,
                elem_id=f"pttip-{element}",
            )
        )

    parts.extend(tips)
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_forecast_fan(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[str] = None,
    title: str = "Twelve months out, the interval is twice as wide as at three",
    subtitle: str = "Three years of monthly subscriptions, then a year of forecast drawn at the width of its uncertainty.",
    width: int = 900,
    height: int = 610,
    x: str = "month",
    y: str = "subscriptions",
    forecast_key: str = "forecast",
    se_key: str = "se",
    levels: Optional[List[str]] = None,
    anchor_level: float = 80.0,
    history_label: str = "Observed",
    forecast_label: str = "Forecast",
    boundary_label: str = "forecast starts",
    x_label: str = "Month",
    y_label: str = "Subscriptions",
    band_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Write a fan chart to disk and return the path.

    Parameters
    ----------
    data : list of dict or None
        One row per period; history rows carry `y`, forecast rows carry
        `forecast_key` and `se_key`. Defaults to :data:`DEMO_DATA`.
    out : str or None
        Destination path; ``None`` writes beside the script.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    x, y : str
        Row keys for the time axis and the observed value.
    forecast_key, se_key : str
        Row keys for the point forecast and its standard error.
    levels : list of str or None
        Interval levels to draw, as percentages.
    anchor_level : float
        Which level, as a percentage, the chrome quotes at the final
        horizon.
    history_label, forecast_label, boundary_label : str
        Names for the two halves of the line and for the rule between them.
    x_label, y_label : str
        Axis titles.
    band_note, finding : str or None
        The sentence explaining what a level means, and the one quoting
        the interval at the horizon; ``None`` composes each from the data.
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
    >>> p = make_forecast_fan()
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
        forecast_key=forecast_key,
        se_key=se_key,
        levels=levels,
        anchor_level=anchor_level,
        history_label=history_label,
        forecast_label=forecast_label,
        boundary_label=boundary_label,
        x_label=x_label,
        y_label=y_label,
        band_note=band_note,
        finding=finding,
        mode=mode,
        accessibility=accessibility,
        theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "forecast-fan")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(
        __file__,
        "forecast-fan",
        build_svg,
        description="Draw a forecast inside the widening fan of its uncertainty.",
    )


if __name__ == "__main__":
    main()
