#!/usr/bin/env python3
"""
make_pointplot — an estimate per group, its interval, and the n behind it.

A point estimate with an interval, repeated across categories and joined
by a line per series. It is the figure a model comparison ends up as: one
dot per dataset per method, the spread of repeated runs around it.

Where the usual version goes wrong
----------------------------------
* **The interval is never named.** Every library draws a bar through the
  dot and almost none says what it is -- a standard deviation, a standard
  error, a 95% confidence interval, a bootstrap percentile band? Those
  differ by a factor of three on the same data, and a reader who assumes
  the wrong one reads the wrong conclusion. This one computes a stated
  interval and prints what it is on the figure.
* **The n disappears.** A mean of three runs and a mean of three hundred
  are drawn identically. Here each group carries its own count, so an
  interval that is wide because the data is noisy can be told from one
  that is wide because there is hardly any.
* **Overlapping intervals are read as "no difference".** They are not the
  same claim, and the figure says so rather than letting the reader infer
  a test that was never run.

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
from _svg import fmt_number, foreground_tip_css, svg_open, tooltip_bubble, xml_escape  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

#: Five benchmarks, three methods, ten seeds each. Written as the means and
#: spreads a run would produce, then expanded into the runs themselves,
#: because this figure's whole subject is what repeated runs do.
#:
#: The five accuracies sit deliberately close together. A first draft spread
#: them from 0.60 to 0.96, and on a shared axis the intervals -- which are
#: the entire point of the figure -- collapsed to less than a pixel. A point
#: plot across groups whose levels differ by tens of points is the wrong
#: chart for those groups: `facet` gives each its own scale.
_BENCHMARKS: Dict[str, Dict[str, Tuple[float, float]]] = {
    "CIFAR-10": {"Baseline": (0.874, 0.004), "Tuned": (0.881, 0.005), "Ours": (0.906, 0.004)},
    "SVHN": {"Baseline": (0.901, 0.003), "Tuned": (0.906, 0.004), "Ours": (0.910, 0.011)},
    "Fashion": {"Baseline": (0.889, 0.005), "Tuned": (0.893, 0.006), "Ours": (0.897, 0.016)},
    "STL-10": {"Baseline": (0.862, 0.006), "Tuned": (0.871, 0.006), "Ours": (0.898, 0.005)},
    "Tiny-IN": {"Baseline": (0.878, 0.007), "Tuned": (0.882, 0.007), "Ours": (0.886, 0.018)},
}


def _runs(seed: int = 5, repeats: int = 10) -> List[Dict[str, Any]]:
    """Expand the benchmark table into one row per run, deterministically."""
    rng = random.Random(seed)
    rows: List[Dict[str, Any]] = []
    for dataset, methods in _BENCHMARKS.items():
        for method, (mean, spread) in methods.items():
            for _ in range(repeats):
                u1 = max(rng.random(), 1e-12)
                u2 = rng.random()
                draw = mean + spread * math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
                rows.append(
                    {
                        "dataset": dataset,
                        "method": method,
                        "score": round(min(max(draw, 0.0), 1.0), 4),
                    }
                )
    return rows


DEMO_DATA: List[Dict[str, Any]] = _runs()

#: 1.96 standard errors either side of the mean: the normal approximation
#: to a 95% interval. Named here rather than buried, because which
#: interval a bar shows is the question this figure exists to answer.
_Z95 = 1.959964


def _estimate(values: List[float]) -> Tuple[float, float, float, int]:
    """Mean, low, high and n, on the stated normal approximation.

    A bootstrap would be defensible and is what some libraries do by
    default; it is also not reproducible without stating a seed, and a
    figure whose interval moves between renders is worse than a slightly
    conservative one. The approximation is written on the chart.
    """
    n = len(values)
    mean = sum(values) / n
    if n < 2:
        return mean, mean, mean, n
    variance = sum((v - mean) ** 2 for v in values) / (n - 1)
    half = _Z95 * math.sqrt(variance / n)
    return mean, mean - half, mean + half, n


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "On two benchmarks of five, the new method clears the baseline's interval",
    subtitle: str = "Accuracy over ten seeds per cell. Bars are 95% intervals; overlapping bars are not a test.",
    width: int = 900,
    height: int = 580,
    category: str = "dataset",
    series: str = "method",
    value: str = "score",
    y_label: str = "Accuracy",
    interval_label: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full point-estimate SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        One row per observation, with a category key, a series key and a
        numeric key, named by `category`, `series` and `value`. Defaults
        to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    category, series, value : str
        Which key splits the x axis, which splits the lines, and which is
        measured.
    y_label : str
        Title beside the value axis.
    interval_label : str or None
        What the bars are, in words. ``None`` writes the interval this
        figure actually computed -- which is the point: a bar whose
        meaning is unstated can be read three ways.
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
    hues = [
        palette.get(name, fallback)
        for name, fallback in (
            ("Blue", "#007AFF"),
            ("Orange", "#FF9500"),
            ("Purple", "#AF52DE"),
            ("Green", "#28CD41"),
            ("Teal", "#79DBDC"),
            ("Red", "#FF3B30"),
        )
    ]

    categories: List[str] = []
    series_names: List[str] = []
    grouped: Dict[Tuple[str, str], List[float]] = {}
    for row in rows:
        cat, ser = str(row[category]), str(row[series])
        if cat not in categories:
            categories.append(cat)
        if ser not in series_names:
            series_names.append(ser)
        grouped.setdefault((cat, ser), []).append(float(row[value]))

    estimates = {key: _estimate(values) for key, values in grouped.items()}
    lows = [low for _, low, _, _ in estimates.values()]
    highs = [high for _, _, high, _ in estimates.values()]
    span = (max(highs) - min(lows)) or 1.0
    # Round the *step*, then walk out from the data: padding first and
    # rounding after leaves ticks on values like 0.89 and 0.77, which read
    # as data rather than as an axis.
    step = 10.0 ** math.floor(math.log10(span / 4.0))
    for nice in (1.0, 2.0, 2.5, 5.0, 10.0):
        if span / 4.0 <= step * nice:
            step *= nice
            break
    y_lo = math.floor((min(lows) - span * 0.18) / step) * step
    y_hi = math.ceil((max(highs) + span * 0.12) / step) * step

    plot_x, plot_y = 84.0, 150.0
    right_margin, bottom_margin = 150.0, 72.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_margin
    slot = plot_w / max(len(categories), 1)
    # Series are nudged apart inside a category so their bars do not sit on
    # top of each other; the nudge is small enough that the group still
    # reads as one column.
    spread = min(slot * 0.5, 54.0)

    def cx(cat_index: int, series_index: int) -> float:
        if len(series_names) == 1:
            return plot_x + (cat_index + 0.5) * slot
        offset = (series_index / (len(series_names) - 1) - 0.5) * spread
        return plot_x + (cat_index + 0.5) * slot + offset

    def cy(v: float) -> float:
        return plot_y + plot_h - (v - y_lo) / ((y_hi - y_lo) or 1.0) * plot_h

    parts: List[str] = []
    parts.append(
        svg_open(
            width, height, "point-title", "point-desc", font_family=chrome_stack_for_theme(theme)
        )
    )
    parts.append(f'<title id="point-title">{xml_escape(title)}</title>')
    sample = next(iter(estimates.values()))
    parts.append(
        f'<desc id="point-desc">A point estimate per {xml_escape(category)} and '
        f"{xml_escape(series)}, {len(categories)} by {len(series_names)}, each with a 95% "
        f"interval computed from {sample[3]} observations on the normal approximation. "
        f"Series: {xml_escape(', '.join(series_names))}. Overlapping intervals are not a "
        f"significance test and the figure does not claim one.</desc>"
    )
    parts.append(
        "<style>"
        ".est{cursor:default;}"
        ".est:hover,.est:focus{outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + foreground_tip_css(len(estimates), mark_prefix="est", tip_prefix="esttip")
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
        f"{xml_escape(subtitle)}</text>"
    )
    said = (
        interval_label
        if interval_label is not None
        else (
            f"Bars: mean ± {_Z95:.2f} standard errors (95%, normal approximation) · "
            f"n per point is in its tooltip"
        )
    )
    parts.append(
        f'<text x="{plot_x:.1f}" y="98" font-size="12" fill="{SECONDARY}" '
        f'font-family="{mono_family}">{xml_escape(said)}</text>'
    )
    parts.append(
        f'<text x="{plot_x:.1f}" y="{plot_y - 14:.1f}" font-size="12" fill="{SECONDARY}">'
        f"{xml_escape(y_label)}</text>"
    )

    for step in range(5):
        value_at = y_lo + step / 4.0 * (y_hi - y_lo)
        gy = cy(value_at)
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{gy:.1f}" x2="{plot_x + plot_w:.1f}" y2="{gy:.1f}" '
            f'stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{gy + 4:.1f}" font-size="11" fill="{SECONDARY}" '
            f'text-anchor="end" font-family="{mono_family}">{fmt_number(value_at)}</text>'
        )

    for index, cat in enumerate(categories):
        parts.append(
            f'<text x="{plot_x + (index + 0.5) * slot:.1f}" y="{plot_y + plot_h + 22:.1f}" '
            f'font-size="12" fill="{INK}" text-anchor="middle">{xml_escape(cat)}</text>'
        )

    tips: List[str] = []
    for series_index, ser in enumerate(series_names):
        colour = hues[series_index % len(hues)]
        points = [
            (cx(i, series_index), estimates[(cat, ser)])
            for i, cat in enumerate(categories)
            if (cat, ser) in estimates
        ]
        parts.append(
            '<polyline points="'
            + " ".join(f"{x:.1f},{cy(est[0]):.1f}" for x, est in points)
            + f'" fill="none" stroke="{colour}" stroke-width="1.6" opacity="0.5"/>'
        )
        for i, cat in enumerate(categories):
            key = (cat, ser)
            if key not in estimates:
                continue
            mean, low, high, n = estimates[key]
            x = cx(i, series_index)
            parts.append(
                f'<line x1="{x:.1f}" y1="{cy(low):.1f}" x2="{x:.1f}" y2="{cy(high):.1f}" '
                f'stroke="{colour}" stroke-width="2" stroke-linecap="round"/>'
            )
            parts.append(
                f'<circle cx="{x:.1f}" cy="{cy(mean):.1f}" r="4.4" fill="{colour}" '
                f'stroke="{BG}" stroke-width="1.6"/>'
            )
            element = len(tips)
            parts.append(
                f'<rect id="est-{element}" class="est hit" tabindex="0" role="img" '
                f'aria-label="{xml_escape(cat)}, {xml_escape(ser)}: {fmt_number(mean)}, '
                f'95% interval {fmt_number(low)} to {fmt_number(high)}, {n} runs" '
                f'x="{x - 11:.1f}" y="{cy(high) - 11:.1f}" width="22" '
                f'height="{max(cy(low) - cy(high) + 22, 22):.1f}" fill="transparent">'
                f"<title>{xml_escape(cat)} · {xml_escape(ser)}: {fmt_number(mean)}</title></rect>"
            )
            tips.append(
                tooltip_bubble(
                    x,
                    cy(mean),
                    [
                        f"{cat} · {ser}",
                        f"{fmt_number(mean)} (95%: {fmt_number(low)} to {fmt_number(high)})",
                        f"over {n} runs",
                    ],
                    canvas_w=width,
                    canvas_h=height,
                    ink=INK,
                    secondary=SECONDARY,
                    border=GRIDLINE,
                    elem_id=f"esttip-{element}",
                )
            )

    # Direct labels at the right edge instead of a legend: the lines end
    # there anyway, so the name goes where the eye already is.
    # Direct labels want to sit where their line ends, and three lines that
    # end a thousandth apart want to sit in the same place: the first render
    # printed all three on top of each other. Sorted by where they want to
    # be, then pushed apart only as far as needed.
    wanted = sorted(
        (
            (cy(estimates[(categories[-1], ser)][0]), index, ser)
            for index, ser in enumerate(series_names)
            if (categories[-1], ser) in estimates
        )
    )
    free = -1e9
    for y_at, series_index, ser in wanted:
        y_at = max(y_at, free + 17.0)
        free = y_at
        colour = hues[series_index % len(hues)]
        parts.append(
            f'<text x="{plot_x + plot_w + 14:.1f}" y="{y_at + 4:.1f}" font-size="12" '
            f'font-weight="700" fill="{colour}">{xml_escape(ser)}</text>'
        )

    parts.extend(tips)
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_pointplot(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "On two benchmarks of five, the new method clears the baseline's interval",
    subtitle: str = "Accuracy over ten seeds per cell. Bars are 95% intervals; overlapping bars are not a test.",
    width: int = 900,
    height: int = 580,
    category: str = "dataset",
    series: str = "method",
    value: str = "score",
    y_label: str = "Accuracy",
    interval_label: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored point-estimate plot and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        One row per observation, with keys ``dataset``, ``method`` and
        ``score``, or whatever `category`, `series` and `value` name.
        Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/pointplot.svg``.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    category, series, value : str
        Which keys split the axis, split the lines, and are measured.
    y_label : str
        Title beside the value axis.
    interval_label : str or None
        What the bars are, in words; ``None`` writes what was computed.
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
    >>> p = make_pointplot()
    >>> p.exists()
    True
    """
    svg = build_svg(
        data,
        title=title,
        subtitle=subtitle,
        width=width,
        height=height,
        category=category,
        series=series,
        value=value,
        y_label=y_label,
        interval_label=interval_label,
        mode=mode,
        accessibility=accessibility,
        theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "pointplot")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(
        __file__,
        "pointplot",
        build_svg,
        description="Generate a point-estimate plot with intervals.",
    )


if __name__ == "__main__":
    main()
