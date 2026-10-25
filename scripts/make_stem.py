#!/usr/bin/env python3
"""
make_stem — a discrete signal, one stalk per sample.

A stalk from the baseline to each sample's value, with a head on top.
The form exists for data that is genuinely discrete -- counts per hour,
taps per second, coefficients at each lag -- where joining the samples
with a line would draw values that were never measured.

Where the usual stem plot goes wrong
--------------------------------------
* **The baseline is assumed to be zero.** For a signal that varies
  around a level, stalks from zero are all the same length and the
  variation is a fringe on top of a wall. ``baseline="mean"`` roots
  them at the mean instead, and the chrome says where the floor is,
  because a stem's length only means something once you know what it
  is measured from.
* **It is reached for when a line would do.** A stem plot of two
  hundred closely spaced samples is a solid block with a ragged top --
  a line chart with extra ink. The chrome reports the spacing and says
  so when the samples are dense enough that a line would read better.
* **Heads and stalks are drawn at one weight.** The samples that matter
  are the ones far from the baseline, and nothing distinguishes them.
  Samples beyond `mark_beyond` of the spread are drawn solid and the
  rest lightly, so the shape arrives before the detail.

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
    fmt_measured,
    fmt_number,
    foreground_tip_css,
    svg_open,
    tooltip_bubble,
    wrap_no_orphan,
    xml_escape,
)
from _textfit import fit_font_size  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

_HOURS = 48


def _signal(seed: int = 19) -> List[Dict[str, Any]]:
    """Forty-eight hours of card declines at a payment gateway.

    Counts per hour, which is the case a stem plot is actually for: the
    quantity exists at each hour and nowhere between, so a line joining
    them would draw a decline rate at half past that was never measured.

    Two hours are deliberately far from the rest -- a processor outage
    in the early morning of the second day -- so the figure has
    something to pick out.
    """
    rng = random.Random(seed)
    rows: List[Dict[str, Any]] = []
    for hour in range(_HOURS):
        daily = 1.0 + 0.45 * math.sin(2.0 * math.pi * (hour - 4) / 24.0)
        base = 17.0 * daily
        spike = 54.0 if hour in (27, 28) else 0.0
        rows.append(
            {
                "hour": hour,
                "declines": max(0, int(round(base + spike + rng.gauss(0.0, 3.2)))),
            }
        )
    return rows


DEMO_DATA: List[Dict[str, Any]] = _signal()


def _mean(values: List[float]) -> float:
    """Arithmetic mean; 0.0 for an empty list."""
    return sum(values) / len(values) if values else 0.0


def _standard_deviation(values: List[float]) -> float:
    """Sample standard deviation; 0.0 for fewer than two values."""
    if len(values) < 2:
        return 0.0
    mean = _mean(values)
    return (sum((v - mean) ** 2 for v in values) / (len(values) - 1)) ** 0.5


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Two hours out of forty-eight carry 15% of the declines",
    subtitle: str = "Card declines per hour over two days, one stalk per hour, rooted at the mean rather than at zero.",
    width: int = 940,
    height: int = 580,
    x: str = "hour",
    y: str = "declines",
    baseline: str = "mean",
    baseline_value: Optional[float] = None,
    mark_beyond: float = 2.0,
    dense_at: int = 120,
    x_label: str = "Hour",
    y_label: str = "Declines",
    baseline_label: str = "mean",
    floor_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full stem plot SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        One row per sample. Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    x, y : str
        Row keys for the sample position and its value.
    baseline : str
        Where the stalks are rooted: ``"zero"``, ``"mean"``, or
        ``"given"`` to use `baseline_value`.
    baseline_value : float or None
        The floor to use when `baseline` is ``"given"``.
    mark_beyond : float
        How many standard deviations from the baseline a sample must sit
        before it is drawn solid rather than lightly.
    dense_at : int
        Above this many samples the chrome says a line chart would read
        better, because the stalks will have merged into a block.
    x_label, y_label : str
        Axis titles.
    baseline_label : str
        Caption on the baseline rule.
    floor_note, finding : str or None
        The line saying where the floor is, and the sentence naming the
        samples that stand out; ``None`` composes each from the data.
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
    if baseline not in ("zero", "mean", "given"):
        raise ValueError(f"baseline is 'zero', 'mean' or 'given', got {baseline!r}")
    if baseline == "given" and baseline_value is None:
        raise ValueError("baseline='given' needs a baseline_value")

    def position(row: Dict[str, Any]) -> Tuple[int, float, str]:
        """Sort key that works for an index and for "2026-01" alike."""
        raw = row[x]
        try:
            return (0, float(raw), "")
        except (TypeError, ValueError):
            return (1, 0.0, str(raw))

    rows = sorted(data if data else DEMO_DATA, key=position)
    if not rows:
        raise ValueError("a stem plot needs at least one sample")
    labels = [str(row[x]) for row in rows]
    values = [float(row[y]) for row in rows]
    n = len(values)

    floor = (
        0.0
        if baseline == "zero"
        else (_mean(values) if baseline == "mean" else float(baseline_value or 0.0))
    )
    spread = _standard_deviation(values)
    threshold = mark_beyond * spread
    standout = [
        index
        for index, value in enumerate(values)
        if spread > 0.0 and abs(value - floor) > threshold
    ]

    mono_family = mono_stack_for_theme(theme)
    palette = load_palette(accessibility, theme=theme)
    quiet = palette.get("Blue", "#007AFF")
    loud = palette.get("Orange", "#FF9500")

    ticks = nice_ticks_range(min(values + [floor]), max(values + [floor]), 5)
    axis_low, axis_high = ticks[0], ticks[-1]

    plot_x = 92.0
    plot_y = 202.0
    plot_w = width - plot_x - 56.0
    plot_h = height - plot_y - 92.0
    precision = (axis_high - axis_low) / 100.0

    def px(index: int) -> float:
        return plot_x + (index + 0.5) * plot_w / max(n, 1)

    def py(value: float) -> float:
        return plot_y + plot_h - (value - axis_low) / (axis_high - axis_low) * plot_h

    floor_lines = (
        [floor_note]
        if floor_note is not None
        else [
            f"stalks rooted at the {baseline_label} of "
            f"{fmt_measured(floor, precision)}, not at zero"
            if baseline != "zero"
            else "stalks rooted at zero",
        ]
        + (
            [f"{n} samples is dense for stalks: a line would read better above {dense_at}"]
            if n > dense_at
            else []
        )
    )
    said_floor = " · ".join(floor_lines)
    said_parts: List[str] = []
    if finding is not None:
        said_parts.append(finding)
    elif standout:
        total = sum(values)
        carried = sum(values[index] for index in standout)
        named = ", ".join(labels[index] for index in standout[:4])
        more = f" and {len(standout) - 4} more" if len(standout) > 4 else ""
        said_parts.append(
            f"{len(standout)} of {n} samples sit more than "
            f"{fmt_number(mark_beyond)} standard deviations from the baseline: "
            f"{named}{more}."
        )
        if total:
            said_parts.append(f"They carry {fmt_number(carried / total * 100.0)}% of the total.")
    else:
        said_parts.append(
            f"No sample sits more than {fmt_number(mark_beyond)} standard deviations "
            f"from the baseline."
        )
    said_lines: List[str] = []
    for sentence in said_parts:
        said_lines.extend(wrap_no_orphan(sentence, 102))

    parts: List[str] = []
    parts.append(
        svg_open(
            width, height, "stem-title", "stem-desc", font_family=chrome_stack_for_theme(theme)
        )
    )
    parts.append(f'<title id="stem-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="stem-desc">A stem plot of {n} samples from {xml_escape(labels[0])} '
        f"to {xml_escape(labels[-1])}, each a stalk from the baseline to its value. "
        f"{xml_escape(said_floor)}. {xml_escape(' '.join(said_parts))}</desc>"
    )
    parts.append(
        "<style>"
        ".stalk{cursor:default;}"
        ".stalk:hover,.stalk:focus{outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + foreground_tip_css(n, mark_prefix="stalk", tip_prefix="stalktip")
        + "@media (prefers-reduced-motion:reduce){.tip{transition:none}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    title_size = fit_font_size(title, width - 96.0, 22.0, min_px=15.0)
    parts.append(
        f'<text x="40" y="46" font-size="{title_size:.1f}" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    for line_index, text in enumerate(wrap_no_orphan(subtitle, 106)[:2]):
        parts.append(
            f'<text x="40" y="{72 + line_index * 20:.1f}" font-size="14" '
            f'fill="{SECONDARY}">{xml_escape(text)}</text>'
        )
    floor_drawn: List[str] = []
    for clause in floor_lines:
        floor_drawn.extend(wrap_no_orphan(clause, 102))
    for line_index, text in enumerate(floor_drawn[:2]):
        parts.append(
            f'<text x="40" y="{122 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(text)}</text>'
        )
    for line_index, text in enumerate(said_lines[:2]):
        parts.append(
            f'<text x="40" y="{160 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(text)}</text>'
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
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{py(floor):.1f}" x2="{plot_x + plot_w:.1f}" '
        f'y2="{py(floor):.1f}" stroke="{INK}" stroke-width="1.4"/>'
    )
    parts.append(
        f'<text x="{plot_x + plot_w + 6:.1f}" y="{py(floor) + 4:.1f}" font-size="10" '
        f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(baseline_label)}</text>'
    )

    tips: List[str] = []
    marked = set(standout)
    for index, value in enumerate(values):
        hit = index in marked
        colour = loud if hit else quiet
        opacity = 1.0 if hit else 0.55
        parts.append(
            f'<line x1="{px(index):.1f}" y1="{py(floor):.1f}" x2="{px(index):.1f}" '
            f'y2="{py(value):.1f}" stroke="{colour}" stroke-width="{2.2 if hit else 1.6}" '
            f'opacity="{opacity}"/>'
        )
        parts.append(
            f'<circle cx="{px(index):.1f}" cy="{py(value):.1f}" r="{3.4 if hit else 2.6}" '
            f'fill="{colour}" opacity="{opacity}"/>'
        )
        parts.append(
            f'<rect id="stalk-{index}" class="stalk hit" tabindex="0" role="img" '
            f'aria-label="{xml_escape(x)} {xml_escape(labels[index])}: '
            f"{fmt_measured(value, precision)}"
            f'{", beyond the threshold" if hit else ""}" '
            f'x="{px(index) - plot_w / (2 * n):.1f}" y="{plot_y:.1f}" '
            f'width="{plot_w / n:.1f}" height="{plot_h:.1f}" fill="transparent">'
            f"<title>{xml_escape(labels[index])}: "
            f"{fmt_measured(value, precision)}</title></rect>"
        )
        tips.append(
            tooltip_bubble(
                px(index),
                py(value),
                [f"{x} {labels[index]}", fmt_measured(value, precision)]
                + (["beyond the threshold"] if hit else []),
                canvas_w=width,
                canvas_h=height,
                ink=INK,
                secondary=SECONDARY,
                border=GRIDLINE,
                elem_id=f"stalktip-{index}",
            )
        )

    every = max(1, n // 12)
    for index in range(0, n, every):
        parts.append(
            f'<text x="{px(index):.1f}" y="{plot_y + plot_h + 20:.1f}" font-size="11" '
            f'fill="{SECONDARY}" text-anchor="middle" font-family="{mono_family}">'
            f"{xml_escape(labels[index])}</text>"
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{plot_y + plot_h + 46:.1f}" '
        f'font-size="12" fill="{SECONDARY}" text-anchor="middle">'
        f"{xml_escape(x_label)}</text>"
    )
    parts.append(
        f'<text x="40" y="{plot_y - 12:.1f}" font-size="12" fill="{SECONDARY}">'
        f"{xml_escape(y_label)}</text>"
    )

    parts.extend(tips)
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_stem(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[str] = None,
    title: str = "Two hours out of forty-eight carry 15% of the declines",
    subtitle: str = "Card declines per hour over two days, one stalk per hour, rooted at the mean rather than at zero.",
    width: int = 940,
    height: int = 580,
    x: str = "hour",
    y: str = "declines",
    baseline: str = "mean",
    baseline_value: Optional[float] = None,
    mark_beyond: float = 2.0,
    dense_at: int = 120,
    x_label: str = "Hour",
    y_label: str = "Declines",
    baseline_label: str = "mean",
    floor_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Write a stem plot to disk and return the path.

    Parameters
    ----------
    data : list of dict or None
        One row per sample. Defaults to :data:`DEMO_DATA`.
    out : str or None
        Destination path; ``None`` writes beside the script.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    x, y : str
        Row keys for the sample position and its value.
    baseline : str
        ``"zero"``, ``"mean"``, or ``"given"``.
    baseline_value : float or None
        The floor to use when `baseline` is ``"given"``.
    mark_beyond : float
        Standard deviations from the baseline that mark a sample.
    dense_at : int
        Above this many samples the chrome recommends a line chart.
    x_label, y_label : str
        Axis titles.
    baseline_label : str
        Caption on the baseline rule.
    floor_note, finding : str or None
        The line saying where the floor is, and the sentence naming the
        samples that stand out; ``None`` composes each from the data.
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
    >>> p = make_stem()
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
        baseline=baseline,
        baseline_value=baseline_value,
        mark_beyond=mark_beyond,
        dense_at=dense_at,
        x_label=x_label,
        y_label=y_label,
        baseline_label=baseline_label,
        floor_note=floor_note,
        finding=finding,
        mode=mode,
        accessibility=accessibility,
        theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "stem")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(
        __file__, "stem", build_svg, description="Draw a discrete signal as one stalk per sample."
    )


if __name__ == "__main__":
    main()
