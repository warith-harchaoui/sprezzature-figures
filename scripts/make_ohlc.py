#!/usr/bin/env python3
"""
make_ohlc — the session as a bar: where it opened, how far it ran, where it closed.

One vertical bar per session spanning low to high, with a tick left for
the open and a tick right for the close. The bar is the range the price
actually travelled; the two ticks are where it started and where it
ended, which are rarely the same thing and rarely the extremes.

Where the usual OHLC chart goes wrong
---------------------------------------
* **The axis is dates, so the gaps are holes.** Markets close. Plotted
  against real time, a weekend is two days of blank chart and every bar
  is thinner than it needs to be; plotted by session, the bars are even
  and the time between them is uneven. Neither is wrong and the reader
  has to know which they are looking at, so the chrome says it and
  names the longest gap that got closed up.
* **Direction is left to colour alone.** On a monochrome print, or for
  a red-green colour-blind reader -- about one man in twelve -- an OHLC
  chart with only colour to say up or down says nothing at all. The
  open and close ticks point in opposite directions by construction,
  which is the form's own answer, and the palette is a second channel
  rather than the only one.
* **The range is drawn and never measured.** The question an OHLC chart
  is read for is which sessions were wild, and the answer is a number:
  the widest range, and how it compares to the median one.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import random
import sys
from datetime import date, timedelta
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

_SESSIONS = 46


def _sessions(seed: int = 13) -> List[Dict[str, Any]]:
    """Forty-six trading sessions from a Monday, with the weekends missing.

    Real dates, really skipping Saturdays and Sundays, because the figure
    makes a claim about what its axis hides and a claim has to be true.
    Nine weekends fall inside this stretch, so one bar per session closes
    up eighteen days of calendar.

    One session is deliberately wild, with a range about four times the
    median, so the chart has something to find and the title has
    something to say.
    """
    rng = random.Random(seed)
    rows: List[Dict[str, Any]] = []
    price = 148.0
    when = date(2026, 3, 2)  # a Monday
    while len(rows) < _SESSIONS:
        if when.weekday() >= 5:
            when += timedelta(days=1)
            continue
        opening = price
        closing = max(1.0, opening + rng.gauss(0.18, 1.9))
        wild = len(rows) == 29
        reach = 14.0 if wild else rng.uniform(0.9, 2.6)
        high = max(opening, closing) + abs(rng.gauss(0.0, 0.7)) + reach / 2.0
        low = min(opening, closing) - abs(rng.gauss(0.0, 0.7)) - reach / 2.0
        rows.append(
            {
                "day": when.isoformat(),
                "open": round(opening, 2),
                "high": round(high, 2),
                "low": round(max(1.0, low), 2),
                "close": round(closing, 2),
            }
        )
        price = closing
        when += timedelta(days=1)
    return rows


DEMO_DATA: List[Dict[str, Any]] = _sessions()


def _median(values: List[float]) -> float:
    """The middle value, or the mean of the two middles."""
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2.0


def _day_number(label: str) -> Optional[int]:
    """A date written ``YYYY-MM-DD`` as an ordinal day, or ``None``.

    Exact rather than approximate, and the first draft shows why: rounding
    every month to thirty-one days reports a phantom one-day gap at the
    end of April, which the chrome would then print as calendar the axis
    closed up. A label in any other shape opts out of that sentence.
    """
    try:
        return date.fromisoformat(label).toordinal()
    except ValueError:
        return None


#: Short month names for an axis. English only, on purpose: the French
#: gallery is produced by `web/tools/localize_figures.py` from
#: `web/i18n/figures.fr.patterns.yaml`, which already carries a rule per month
#: in exactly this shape (``Mar ([-+\d.,\u202f ]+)`` → ``Mars {0}``). Writing
#: the month before the day is what makes those twelve rules apply here too,
#: instead of asking for thirteen more.
_MONTHS: tuple[str, ...] = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


def _axis_label(label: str) -> str:
    """An axis label a person reads, not a key a machine sorts by.

    ``2026-03-02`` is machine output: correct, sortable, and three times the
    width of ``Mar 2`` for the same information. The suite's own figure
    auditor has a rule for it — ``iso-date-tick`` — and the gallery's own
    candlestick chart was breaking it, because nothing ran that auditor over
    the gallery.

    Only the axis. The hover bubble keeps the full date: it is read one at a
    time, on demand, and the year is worth having there.

    A label in any other shape is returned untouched — the session key belongs
    to the caller, and most callers do not pass dates.
    """
    try:
        when = date.fromisoformat(label)
    except ValueError:
        return label
    return f"{_MONTHS[when.month - 1]} {when.day}"


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "One session ran nearly four times the usual range; the axis hides nine weekends",
    subtitle: str = "Each bar spans the session's low to high, with the open ticked left and the close ticked right.",
    width: int = 960,
    height: int = 600,
    x: str = "day",
    open_key: str = "open",
    high_key: str = "high",
    low_key: str = "low",
    close_key: str = "close",
    tick_width: float = 5.0,
    x_label: str = "Session",
    y_label: str = "Price",
    axis_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full OHLC SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        One row per session. Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    x : str
        Row key for the session label.
    open_key, high_key, low_key, close_key : str
        Row keys for the four prices.
    tick_width : float
        How far the open and close ticks reach from the bar, in pixels.
    x_label, y_label : str
        Axis titles.
    axis_note, finding : str or None
        The line saying what the axis counts, and the sentence naming the
        widest session; ``None`` composes each from the data.
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
        raise ValueError("an OHLC chart needs at least one session")
    sessions: List[Tuple[str, float, float, float, float]] = []
    for row in rows:
        opening = float(row[open_key])
        high = float(row[high_key])
        low = float(row[low_key])
        closing = float(row[close_key])
        if high < low:
            raise ValueError(f"session {row[x]!r} has a high of {high} below its low of {low}")
        sessions.append((str(row[x]), opening, high, low, closing))

    ranges = [high - low for _, _, high, low, _ in sessions]
    widest = max(range(len(sessions)), key=lambda index: ranges[index])
    middle_range = _median(ranges)

    # How much calendar the session axis closes up.
    numbers = [_day_number(label) for label, *_ in sessions]
    gaps = [
        (later - earlier - 1, sessions[index][0])
        # Deliberately ragged: pairing each session with the next one
        # leaves the last unpaired, so strict= would be wrong here.
        for index, (earlier, later) in enumerate(zip(numbers, numbers[1:], strict=False))
        if earlier is not None and later is not None and later - earlier > 1
    ]
    skipped = sum(size for size, _ in gaps)

    mono_family = mono_stack_for_theme(theme)
    palette = load_palette(accessibility, theme=theme)
    rising = palette.get("Blue", "#007AFF")
    falling = palette.get("Orange", "#FF9500")

    ticks = nice_ticks_range(
        min(low for *_, low, _ in sessions), max(high for _, _, high, *_ in sessions), 5
    )
    axis_low, axis_high = ticks[0], ticks[-1]

    plot_x = 86.0
    plot_y = 206.0
    plot_w = width - plot_x - 56.0
    plot_h = height - plot_y - 92.0
    step = plot_w / max(len(sessions), 1)
    precision = (axis_high - axis_low) / 100.0

    def px(index: int) -> float:
        return plot_x + (index + 0.5) * step

    def py(price: float) -> float:
        return plot_y + plot_h - (price - axis_low) / (axis_high - axis_low) * plot_h

    axis_lines = (
        [axis_note]
        if axis_note is not None
        else [
            f"one bar per session, not per day: {len(gaps)} gap"
            f"{'' if len(gaps) == 1 else 's'} of {skipped} days closed up"
            if gaps
            else "one bar per session; the labels run consecutively",
            "open ticks left, close ticks right",
        ]
    )
    said_axis = " · ".join(axis_lines)
    said_parts: List[str] = []
    if finding is not None:
        said_parts.append(finding)
    else:
        label, _, high, low, _ = sessions[widest]
        multiple = (high - low) / middle_range if middle_range else 0.0
        said_parts.append(
            f"The widest session is {label}, running {fmt_measured(high - low, precision)} "
            f"from {fmt_measured(low, precision)} to {fmt_measured(high, precision)} — "
            f"{fmt_number(multiple)} times the median range of "
            f"{fmt_measured(middle_range, precision)}."
        )
    said_lines: List[str] = []
    for sentence in said_parts:
        said_lines.extend(wrap_no_orphan(sentence, 104))

    parts: List[str] = []
    parts.append(
        svg_open(
            width, height, "ohlc-title", "ohlc-desc", font_family=chrome_stack_for_theme(theme)
        )
    )
    parts.append(f'<title id="ohlc-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="ohlc-desc">An open-high-low-close chart of {len(sessions)} sessions '
        f"from {xml_escape(sessions[0][0])} to {xml_escape(sessions[-1][0])}, each a "
        f"vertical bar from low to high with the open ticked left and the close ticked "
        f"right. {xml_escape(said_axis)}. {xml_escape(' '.join(said_parts))}</desc>"
    )
    parts.append(
        "<style>"
        ".bar{cursor:default;}"
        ".bar:hover,.bar:focus{outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + foreground_tip_css(len(sessions), mark_prefix="bar", tip_prefix="bartip")
        + "@media (prefers-reduced-motion:reduce){.tip{transition:none}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    title_size = fit_font_size(title, width - 96.0, 22.0, min_px=15.0)
    parts.append(
        f'<text x="40" y="46" font-size="{title_size:.1f}" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    for line_index, text in enumerate(wrap_no_orphan(subtitle, 108)[:2]):
        parts.append(
            f'<text x="40" y="{72 + line_index * 20:.1f}" font-size="14" '
            f'fill="{SECONDARY}">{xml_escape(text)}</text>'
        )
    axis_drawn: List[str] = []
    for clause in axis_lines:
        axis_drawn.extend(wrap_no_orphan(clause, 104))
    for line_index, text in enumerate(axis_drawn[:2]):
        parts.append(
            f'<text x="40" y="{122 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(text)}</text>'
        )
    for line_index, text in enumerate(said_lines[:2]):
        parts.append(
            f'<text x="40" y="{164 + line_index * 17:.1f}" font-size="12" '
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

    tips: List[str] = []
    for index, (label, opening, high, low, closing) in enumerate(sessions):
        colour = rising if closing >= opening else falling
        centre = px(index)
        parts.append(
            f'<line x1="{centre:.1f}" y1="{py(low):.1f}" x2="{centre:.1f}" '
            f'y2="{py(high):.1f}" stroke="{colour}" stroke-width="1.8"/>'
        )
        parts.append(
            f'<line x1="{centre - tick_width:.1f}" y1="{py(opening):.1f}" '
            f'x2="{centre:.1f}" y2="{py(opening):.1f}" stroke="{colour}" '
            f'stroke-width="1.8"/>'
        )
        parts.append(
            f'<line x1="{centre:.1f}" y1="{py(closing):.1f}" '
            f'x2="{centre + tick_width:.1f}" y2="{py(closing):.1f}" stroke="{colour}" '
            f'stroke-width="1.8"/>'
        )
        if index == widest:
            parts.append(
                f'<rect x="{centre - step / 2:.1f}" y="{plot_y:.1f}" '
                f'width="{step:.1f}" height="{plot_h:.1f}" fill="{INK}" '
                f'opacity="0.05"/>'
            )
        direction = "up" if closing >= opening else "down"
        parts.append(
            f'<rect id="bar-{index}" class="bar hit" tabindex="0" role="img" '
            f'aria-label="{xml_escape(label)}: opened {fmt_measured(opening, precision)}, '
            f"high {fmt_measured(high, precision)}, low {fmt_measured(low, precision)}, "
            f'closed {fmt_measured(closing, precision)}, {direction}" '
            f'x="{centre - step / 2:.1f}" y="{plot_y:.1f}" width="{step:.1f}" '
            f'height="{plot_h:.1f}" fill="transparent">'
            f"<title>{xml_escape(label)}: {fmt_measured(closing, precision)}</title></rect>"
        )
        tips.append(
            tooltip_bubble(
                centre,
                py((high + low) / 2.0),
                [
                    label,
                    f"open {fmt_measured(opening, precision)} · close "
                    f"{fmt_measured(closing, precision)}",
                    f"low {fmt_measured(low, precision)} · high {fmt_measured(high, precision)}",
                ],
                canvas_w=width,
                canvas_h=height,
                ink=INK,
                secondary=SECONDARY,
                border=GRIDLINE,
                elem_id=f"bartip-{index}",
            )
        )

    every = max(1, len(sessions) // 8)
    for index in range(0, len(sessions), every):
        parts.append(
            f'<text x="{px(index):.1f}" y="{plot_y + plot_h + 20:.1f}" font-size="11" '
            f'fill="{SECONDARY}" text-anchor="middle" font-family="{mono_family}">'
            f"{xml_escape(_axis_label(sessions[index][0]))}</text>"
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


def make_ohlc(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[str] = None,
    title: str = "One session ran nearly four times the usual range; the axis hides nine weekends",
    subtitle: str = "Each bar spans the session's low to high, with the open ticked left and the close ticked right.",
    width: int = 960,
    height: int = 600,
    x: str = "day",
    open_key: str = "open",
    high_key: str = "high",
    low_key: str = "low",
    close_key: str = "close",
    tick_width: float = 5.0,
    x_label: str = "Session",
    y_label: str = "Price",
    axis_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Write an OHLC chart to disk and return the path.

    Parameters
    ----------
    data : list of dict or None
        One row per session. Defaults to :data:`DEMO_DATA`.
    out : str or None
        Destination path; ``None`` writes beside the script.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    x : str
        Row key for the session label.
    open_key, high_key, low_key, close_key : str
        Row keys for the four prices.
    tick_width : float
        How far the open and close ticks reach from the bar, in pixels.
    x_label, y_label : str
        Axis titles.
    axis_note, finding : str or None
        The line saying what the axis counts, and the sentence naming the
        widest session; ``None`` composes each from the data.
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
    >>> p = make_ohlc()
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
        open_key=open_key,
        high_key=high_key,
        low_key=low_key,
        close_key=close_key,
        tick_width=tick_width,
        x_label=x_label,
        y_label=y_label,
        axis_note=axis_note,
        finding=finding,
        mode=mode,
        accessibility=accessibility,
        theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "ohlc")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(
        __file__, "ohlc", build_svg, description="Draw open-high-low-close bars, one per session."
    )


if __name__ == "__main__":
    main()
