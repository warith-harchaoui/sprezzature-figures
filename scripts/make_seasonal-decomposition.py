#!/usr/bin/env python3
"""
make_seasonal-decomposition — a series split into trend, season and what is left.

Four stacked panels: the series as observed, the trend the moving average
sees through it, the yearly shape that repeats, and the remainder -- the
part no component explains. The remainder is the panel people skip and
the one that pays: it is where the month that did not follow the rules
shows up.

Where the usual decomposition plot goes wrong
---------------------------------------------
* **Four panels, four different vertical scales, and nothing says so.**
  A remainder drawn edge to edge looks as big as the trend above it,
  which is how a 3-unit wobble comes to look like a 60-unit climb.
  ``shared_scale=True`` puts all four on one scale and ends the argument;
  either way each panel carries its own range, so the comparison a reader
  makes by eye is a comparison they can check.
* **"How much of this is seasonality?" goes unanswered.** The panels show
  the components and leave the reader to eyeball their relative size. The
  chrome reports the two strength measures from Hyndman & Athanasopoulos,
  *Forecasting: Principles and Practice* -- 1 - Var(R)/Var(S+R) for the
  season, 1 - Var(R)/Var(T+R) for the trend -- each on 0 to 1, each the
  answer to the question actually being asked.
* **The trend stops short and nobody explains the gap.** A centred moving
  average of length `period` cannot reach the first or last half-period:
  those months have no window around them. The usual plot draws the hole
  and says nothing; here the uncovered months are named.

The decomposition is computed here, from the series. A caller has a time
series, not a table of components, and making them run a statistics
package before they can draw a picture of their own data is the kind of
step that stops a figure from being drawn at all.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
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

_MONTHS = 72
_CLOSURE_MONTH = 40

# A terrace café: quiet in winter, full in summer. The profile is the
# shape of the year, in euros of weekly average revenue.
_SEASONAL_PROFILE = {
    1: -21.0, 2: -19.0, 3: -11.0, 4: -2.0, 5: 9.0, 6: 19.0,
    7: 24.0, 8: 22.0, 9: 11.0, 10: -1.0, 11: -13.0, 12: -18.0,
}


def _series(seed: int = 7) -> List[Dict[str, Any]]:
    """Six years of monthly café revenue: a climb, a summer, and one closure.

    The shock in month 40 is deliberate and it is the reason this demo
    exists rather than a cleaner one. A decomposition whose remainder is
    flat noise teaches nothing: the reader sees three tidy panels and a
    fourth they learn to ignore. Put one real event in the series and the
    remainder panel becomes the point -- every other component absorbs
    what it can, and the month that refused to follow the yearly shape is
    left standing alone, which is exactly what the panel is for.
    """
    rng = random.Random(seed)
    rows: List[Dict[str, Any]] = []
    for index in range(_MONTHS):
        year, month_of_year = divmod(index, 12)
        month_of_year += 1
        trend = 148.0 + 1.35 * index
        seasonal = _SEASONAL_PROFILE[month_of_year]
        noise = (rng.random() - 0.5) * 9.0
        shock = -46.0 if index + 1 == _CLOSURE_MONTH else 0.0
        rows.append({
            "month": f"{2020 + year}-{month_of_year:02d}",
            "revenue": round(trend + seasonal + noise + shock, 2),
        })
    return rows


DEMO_DATA: List[Dict[str, Any]] = _series()


def _centred_average(values: Sequence[float], period: int) -> List[Optional[float]]:
    """The trend: a centred moving average, ``None`` where the window runs out.

    For an even period the window is averaged twice -- a 2x`period` moving
    average -- because a plain window of even length is centred between two
    observations rather than on one, and would shift the whole trend by
    half a month.
    """
    n = len(values)
    half = period // 2
    trend: List[Optional[float]] = [None] * n
    for index in range(n):
        if index - half < 0 or index + half >= n:
            continue
        if period % 2 == 0:
            window = values[index - half:index + half + 1]
            weights = [0.5] + [1.0] * (period - 1) + [0.5]
            trend[index] = sum(v * w for v, w in zip(window, weights, strict=True)) / period
        else:
            window = values[index - half:index + half + 1]
            trend[index] = sum(window) / period
    return trend


def _seasonal_means(
    detrended: Sequence[Optional[float]], period: int, centre: float
) -> List[float]:
    """One value per position in the cycle, shifted so the cycle averages to `centre`.

    The centring is what makes the season a *shape* rather than a shape
    plus a level: without it the seasonal panel carries part of the trend,
    and the remainder inherits the difference.
    """
    buckets: List[List[float]] = [[] for _ in range(period)]
    for index, value in enumerate(detrended):
        if value is not None:
            buckets[index % period].append(value)
    means = [sum(b) / len(b) if b else centre for b in buckets]
    offset = sum(means) / period - centre
    return [m - offset for m in means]


def _variance(values: Sequence[float]) -> float:
    """Population variance; 0.0 for fewer than two values."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return sum((v - mean) ** 2 for v in values) / len(values)


def _strength(component: Sequence[float], remainder: Sequence[float]) -> float:
    """1 - Var(R)/Var(C+R), floored at 0 and capped at 1.

    The measure from Hyndman & Athanasopoulos: how much of the variation
    that a component and the remainder carry together belongs to the
    component. It is 0 when the component explains nothing beyond noise
    and approaches 1 when the remainder is negligible beside it.
    """
    together = [c + r for c, r in zip(component, remainder, strict=True)]
    denominator = _variance(together)
    if denominator <= 0.0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - _variance(remainder) / denominator))


def _decompose(
    values: Sequence[float], period: int, model: str
) -> Tuple[List[Optional[float]], List[float], List[Optional[float]]]:
    """Split the series into trend, season and remainder.

    A multiplicative model is an additive one on the logarithms: a season
    that multiplies the level by 1.2 adds a constant to its log. Doing it
    that way keeps one code path and makes the strength measures, which
    are variance ratios, mean the same thing under both models.
    """
    if model == "multiplicative":
        if any(v <= 0.0 for v in values):
            raise ValueError(
                "a multiplicative decomposition needs strictly positive values; "
                "this series has one that is not, so use model='additive'"
            )
        work = [math.log(v) for v in values]
        centre = 0.0
    else:
        work = list(values)
        centre = 0.0

    trend = _centred_average(work, period)
    detrended: List[Optional[float]] = [
        None if t is None else w - t for w, t in zip(work, trend, strict=True)
    ]
    means = _seasonal_means(detrended, period, centre)
    seasonal = [means[index % period] for index in range(len(work))]
    remainder: List[Optional[float]] = [
        None if t is None else w - t - s
        for w, t, s in zip(work, trend, seasonal, strict=True)
    ]

    if model == "multiplicative":
        trend = [None if t is None else math.exp(t) for t in trend]
        seasonal = [math.exp(s) for s in seasonal]
        remainder = [None if r is None else math.exp(r) for r in remainder]
    return trend, seasonal, remainder


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "A strong season, a stronger climb, and one month that belongs to neither",
    subtitle: str = "Six years of monthly revenue, split into the climb, the year's shape, and what neither accounts for.",
    width: int = 900,
    height: int = 840,
    x: str = "month",
    y: str = "revenue",
    period: int = 12,
    model: str = "additive",
    observed_label: str = "Observed",
    trend_label: str = "Trend",
    seasonal_label: str = "Seasonal",
    remainder_label: str = "Remainder",
    x_label: str = "Month",
    shared_scale: bool = False,
    outlier_sigma: float = 3.0,
    strength_label: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full decomposition SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        The time series itself, one row per observation, ordered by `x`
        and measured by `y`. Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    x, y : str
        Row keys for the ordering column and the measured column.
    period : int
        Observations per cycle: 12 for monthly data with a yearly season,
        4 for quarterly, 7 for daily data with a weekly one.
    model : str
        ``"additive"`` when the season adds a constant to the level,
        ``"multiplicative"`` when it scales it. A multiplicative model
        needs strictly positive values.
    observed_label, trend_label, seasonal_label, remainder_label : str
        Panel titles, top to bottom.
    x_label : str
        Title under the shared time axis.
    shared_scale : bool
        Draw all four panels on one vertical scale, so their sizes can be
        compared directly. Off by default, because a remainder a hundred
        times smaller than the series then collapses to a flat line --
        true, and unreadable.
    outlier_sigma : float
        How many standard deviations of the remainder mark an observation
        as one the components do not explain.
    strength_label, finding : str or None
        The line reporting the strength measures, and the sentence naming
        what the remainder found; ``None`` composes each from the data.
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
    def position(row: Dict[str, Any]) -> Tuple[int, float, str]:
        """Sort key that works for a month number and for "2026-01" alike."""
        raw = row[x]
        try:
            return (0, float(raw), "")
        except (TypeError, ValueError):
            return (1, 0.0, str(raw))

    rows = sorted(data if data else DEMO_DATA, key=position)
    values = [float(row[y]) for row in rows]
    labels = [str(row[x]) for row in rows]
    n = len(values)
    if n < 2 * period:
        raise ValueError(
            f"a decomposition over a period of {period} needs at least {2 * period} "
            f"observations to see the cycle twice; this series has {n}"
        )

    mono_family = mono_stack_for_theme(theme)
    palette = load_palette(accessibility, theme=theme)
    ordinary = palette.get("Blue", "#007AFF")
    standout = palette.get("Orange", "#FF9500")

    trend, seasonal, remainder = _decompose(values, period, model)
    covered = [index for index, t in enumerate(trend) if t is not None]
    first, last = covered[0], covered[-1]

    # `covered` holds exactly the indices where the moving average has a
    # window, so neither list can contain a None; the narrowing is local.
    inner_trend = [t for t in trend if t is not None]
    inner_season = [seasonal[i] for i in covered]
    inner_rest = [r for r in remainder if r is not None]
    neutral = 1.0 if model == "multiplicative" else 0.0
    season_strength = _strength(
        [s - neutral for s in inner_season], [r - neutral for r in inner_rest]
    )
    trend_strength = _strength(
        [t - sum(inner_trend) / len(inner_trend) for t in inner_trend],
        [r - neutral for r in inner_rest],
    )

    spread = math.sqrt(_variance(inner_rest))
    threshold = outlier_sigma * spread
    def departure(index: int) -> float:
        """How far the remainder at `index` sits from where it should be.

        Written out rather than ``remainder[index] or neutral`` because a
        remainder of exactly zero is a real value, not a missing one, and
        the shorter spelling silently treats the two the same.
        """
        value = remainder[index]
        return 0.0 if value is None else abs(value - neutral)

    outliers = [
        index for index in covered if spread > 0.0 and departure(index) > threshold
    ]

    plot_x = 96.0
    right_margin = 40.0
    plot_w = width - plot_x - right_margin
    panel_h = 112.0
    gap = 42.0
    first_top = 213.0
    panels: List[Tuple[str, List[Optional[float]], float]] = [
        (observed_label, [float(v) for v in values], first_top),
        (trend_label, list(trend), first_top + (panel_h + gap)),
        (seasonal_label, [float(s) for s in seasonal], first_top + 2 * (panel_h + gap)),
        (remainder_label, list(remainder), first_top + 3 * (panel_h + gap)),
    ]

    def extent(series: Sequence[Optional[float]]) -> Tuple[float, float]:
        present = [v for v in series if v is not None]
        low, high = min(present), max(present)
        if high - low < 1e-9:
            low, high = low - 1.0, high + 1.0
        pad = (high - low) * 0.12
        return low - pad, high + pad

    if shared_scale:
        everything = [v for _, series, _ in panels for v in series if v is not None]
        shared = extent(everything)
        scales = [shared] * len(panels)
    else:
        scales = [extent(series) for _, series, _ in panels]

    def px(index: int) -> float:
        return plot_x + index / max(n - 1, 1) * plot_w

    def py(value: float, top: float, scale: Tuple[float, float]) -> float:
        low, high = scale
        return top + panel_h - (value - low) / (high - low) * panel_h

    said_strength = strength_label if strength_label is not None else (
        f"{model} model, period {period} · seasonal strength {fmt_number(season_strength)} "
        f"· trend strength {fmt_number(trend_strength)}, both on 0 to 1"
    )
    uncovered = n - len(covered)
    # Built as whole sentences and wrapped only if one is too long, rather
    # than poured into a fixed width. A chrome line should break where the
    # meaning breaks: the line is what a reader reads, and it is also what
    # a translator is handed -- a sentence cut mid-clause by the wrapper is
    # a fragment in both roles.
    said_parts: List[str] = []
    if finding is not None:
        said_parts.append(finding)
    elif outliers:
        named = ", ".join(labels[index] for index in outliers[:4])
        more = f" and {len(outliers) - 4} more" if len(outliers) > 4 else ""
        said_parts.append(
            f"{len(outliers)} of {len(covered)} months "
            f"{'sits' if len(outliers) == 1 else 'sit'} more than "
            f"{fmt_number(outlier_sigma)} standard deviations from trend plus season: "
            f"{named}{more}."
        )
    else:
        said_parts.append(
            f"No month departs from the trend and the season by more than "
            f"{fmt_number(outlier_sigma)} standard deviations."
        )
    if uncovered:
        said_parts.append(
            f"Trend covers {labels[first]} to {labels[last]}; the centred average "
            f"cannot reach the first or last {uncovered // 2} months."
        )
    said = " ".join(said_parts)
    said_lines: List[str] = []
    for sentence in said_parts:
        said_lines.extend(wrap_no_orphan(sentence, 98))

    parts: List[str] = []
    parts.append(
        svg_open(width, height, "decomp-title", "decomp-desc",
                 font_family=chrome_stack_for_theme(theme))
    )
    parts.append(f'<title id="decomp-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="decomp-desc">A series of {n} observations split into four stacked '
        f'panels: {xml_escape(observed_label)}, {xml_escape(trend_label)}, '
        f'{xml_escape(seasonal_label)} and {xml_escape(remainder_label)}. '
        f'{xml_escape(said_strength)}. {xml_escape(said)}</desc>'
    )
    parts.append(
        "<style>"
        ".pt{cursor:default;}"
        ".pt:hover,.pt:focus{outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + foreground_tip_css(n * len(panels), mark_prefix="pt", tip_prefix="pttip")
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
        f'font-family="{mono_family}">{xml_escape(said_strength)}</text>'
    )
    for line_index, line in enumerate(said_lines[:3]):
        parts.append(
            f'<text x="{plot_x - 64:.1f}" y="{144 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(line)}</text>'
        )

    tips: List[str] = []
    for panel_index, (label, series, top) in enumerate(panels):
        scale = scales[panel_index]
        low, high = scale
        parts.append(
            f'<text x="{plot_x:.1f}" y="{top - 12:.1f}" font-size="13" font-weight="700" '
            f'fill="{INK}">{xml_escape(label)}</text>'
        )
        # Each panel says the range it is drawn on, because four panels on
        # four scales is the one way this chart routinely misleads.
        parts.append(
            f'<text x="{plot_x + plot_w:.1f}" y="{top - 12:.1f}" font-size="11" '
            f'fill="{SECONDARY}" text-anchor="end" font-family="{mono_family}">'
            f'{fmt_number(low)} to {fmt_number(high)}</text>'
        )
        parts.append(
            f'<rect x="{plot_x:.1f}" y="{top:.1f}" width="{plot_w:.1f}" '
            f'height="{panel_h:.1f}" fill="none" stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        if low < neutral < high and panel_index >= 2:
            parts.append(
                f'<line x1="{plot_x:.1f}" y1="{py(neutral, top, scale):.1f}" '
                f'x2="{plot_x + plot_w:.1f}" y2="{py(neutral, top, scale):.1f}" '
                f'stroke="{INK}" stroke-width="1" opacity="0.45"/>'
            )
        middle = neutral if low < neutral < high else (low + high) / 2.0
        for value_at in (low, middle, high):
            parts.append(
                f'<text x="{plot_x - 10:.1f}" y="{py(value_at, top, scale) + 4:.1f}" '
                f'font-size="10" fill="{SECONDARY}" text-anchor="end" '
                f'font-family="{mono_family}">{fmt_number(value_at)}</text>'
            )

        run: List[str] = []
        for index, value in enumerate(series):
            if value is None:
                if run:
                    parts.append(
                        f'<path d="{" ".join(run)}" fill="none" stroke="{ordinary}" '
                        f'stroke-width="2" stroke-linejoin="round"/>'
                    )
                    run = []
                continue
            command = "M" if not run else "L"
            run.append(f"{command}{px(index):.1f},{py(value, top, scale):.1f}")
        if run:
            parts.append(
                f'<path d="{" ".join(run)}" fill="none" stroke="{ordinary}" '
                f'stroke-width="2" stroke-linejoin="round"/>'
            )

        for index in outliers if panel_index in (0, len(panels) - 1) else []:
            value = series[index]
            if value is None:
                continue
            parts.append(
                f'<circle cx="{px(index):.1f}" cy="{py(value, top, scale):.1f}" r="4" '
                f'fill="{standout}"/>'
            )

        for index, value in enumerate(series):
            if value is None:
                continue
            element = len(tips)
            flagged = index in outliers and panel_index in (0, len(panels) - 1)
            parts.append(
                f'<rect id="pt-{element}" class="pt hit" tabindex="0" role="img" '
                f'aria-label="{xml_escape(label)} at {xml_escape(labels[index])}: '
                f'{fmt_number(value)}'
                f'{", further than the threshold" if flagged else ""}" '
                f'x="{px(index) - 5:.1f}" y="{top:.1f}" width="10" '
                f'height="{panel_h:.1f}" fill="transparent">'
                f'<title>{xml_escape(labels[index])}: {fmt_number(value)}</title></rect>'
            )
            tips.append(
                tooltip_bubble(
                    px(index), py(value, top, scale),
                    [f"{label} · {labels[index]}", fmt_number(value)]
                    + (["further than the threshold"] if flagged else []),
                    canvas_w=width, canvas_h=height, ink=INK, secondary=SECONDARY,
                    border=GRIDLINE, elem_id=f"pttip-{element}",
                )
            )

        if panel_index == len(panels) - 1:
            step = max(1, n // 12)
            for index in range(0, n, step):
                parts.append(
                    f'<text x="{px(index):.1f}" y="{top + panel_h + 20:.1f}" font-size="11" '
                    f'fill="{SECONDARY}" text-anchor="middle" font-family="{mono_family}">'
                    f'{xml_escape(labels[index])}</text>'
                )
            parts.append(
                f'<text x="{plot_x + plot_w / 2:.1f}" y="{top + panel_h + 46:.1f}" '
                f'font-size="12" fill="{SECONDARY}" text-anchor="middle">'
                f'{xml_escape(x_label)}</text>'
            )

    parts.extend(tips)
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_seasonal_decomposition(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[str] = None,
    title: str = "A strong season, a stronger climb, and one month that belongs to neither",
    subtitle: str = "Six years of monthly revenue, split into the climb, the year's shape, and what neither accounts for.",
    width: int = 900,
    height: int = 840,
    x: str = "month",
    y: str = "revenue",
    period: int = 12,
    model: str = "additive",
    observed_label: str = "Observed",
    trend_label: str = "Trend",
    seasonal_label: str = "Seasonal",
    remainder_label: str = "Remainder",
    x_label: str = "Month",
    shared_scale: bool = False,
    outlier_sigma: float = 3.0,
    strength_label: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Write a seasonal decomposition to disk and return the path.

    Parameters
    ----------
    data : list of dict or None
        The time series, one row per observation. Defaults to
        :data:`DEMO_DATA`.
    out : str or None
        Destination path; ``None`` writes beside the script.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    x, y : str
        Row keys for the ordering column and the measured column.
    period : int
        Observations per cycle.
    model : str
        ``"additive"`` or ``"multiplicative"``.
    observed_label, trend_label, seasonal_label, remainder_label : str
        Panel titles, top to bottom.
    x_label : str
        Title under the shared time axis.
    shared_scale : bool
        Draw all four panels on one vertical scale.
    outlier_sigma : float
        Standard deviations of the remainder that mark an unexplained month.
    strength_label, finding : str or None
        The strength line and the sentence naming what the remainder
        found; ``None`` composes each from the data.
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
    >>> p = make_seasonal_decomposition()
    >>> p.exists()
    True
    """
    svg = build_svg(
        data, title=title, subtitle=subtitle, width=width, height=height,
        x=x, y=y, period=period, model=model, observed_label=observed_label,
        trend_label=trend_label, seasonal_label=seasonal_label,
        remainder_label=remainder_label, x_label=x_label,
        shared_scale=shared_scale, outlier_sigma=outlier_sigma,
        strength_label=strength_label, finding=finding, mode=mode,
        accessibility=accessibility, theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "seasonal-decomposition")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "seasonal-decomposition", build_svg,
               description="Split a time series into trend, season and remainder.")


if __name__ == "__main__":
    main()
