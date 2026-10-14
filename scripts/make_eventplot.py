#!/usr/bin/env python3
"""
make_eventplot — one tick per event, one row per thing it happened to.

A raster: every event is a short vertical mark at the time it occurred,
on the row of whatever it happened to. No binning, no smoothing, no
counting -- the individual events are the data, and the eye does the
rest.

Where the usual raster goes wrong
-----------------------------------
* **The rows are in whatever order the data arrived.** Structure across
  rows is the whole reason to stack them, and an arbitrary order hides
  it. `order` sorts by first event, by count, or leaves the given
  order, and the chrome says which -- because "the top row fires first"
  means nothing until you know the rows were not sorted by first event.
* **Dense rows turn into a solid bar.** Past a few hundred events a row
  is a black line and the ticks stop carrying information. Each row's
  count is printed, so a reader can tell a busy row from a saturated
  one.
* **Nothing marks the moment everything is about.** A raster is almost
  always read against something -- a stimulus, a deploy, an incident.
  `onset` draws it and the chrome reports how long each row took to
  respond.
* **Bursts are left to the eye.** Events arriving closer together than
  `burst_within` are a burst, and that is computable. They are drawn
  heavier and counted.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
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

_DEPLOY_AT = 305.0
_SERVICES = [
    ("checkout", 0.055, True, 2.0),
    ("payments", 0.040, True, 3.5),
    ("search", 0.075, False, 0.0),
    ("catalogue", 0.030, False, 0.0),
    ("auth", 0.022, True, 7.0),
    ("recommendations", 0.095, False, 0.0),
    ("email", 0.018, False, 0.0),
    ("warehouse", 0.012, False, 0.0),
]


def _errors(seed: int = 47) -> List[Dict[str, Any]]:
    """Eight hours of error events across eight services, with a deploy in the middle.

    Three services depend on the code that shipped at minute 305 and
    start failing within minutes of it; the other five carry on at their
    usual rate. That is the reading a raster is for and the one an
    ordered-by-arrival raster hides: the three affected rows are not
    adjacent in the data, and only sorting them by their first *burst*
    after the deploy puts the staircase on the page. Sorting by their
    first *event* does not -- `recommendations` is chatty enough to fire
    within a minute of any moment, and the first draft duly listed it
    third among the casualties.
    """
    rng = random.Random(seed)
    rows: List[Dict[str, Any]] = []
    for name, rate, affected, delay in _SERVICES:
        minute = 0.0
        while minute < 480.0:
            minute += rng.expovariate(rate)
            if minute < 480.0:
                rows.append({"service": name, "minute": round(minute, 1)})
        if affected:
            burst = _DEPLOY_AT + delay
            while burst < _DEPLOY_AT + delay + 34.0:
                burst += rng.expovariate(1.4)
                if burst < 480.0:
                    rows.append({"service": name, "minute": round(burst, 1)})
    return rows


DEMO_DATA: List[Dict[str, Any]] = _errors()


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Three services start failing within seven minutes of the deploy",
    subtitle: str = "One tick per error, one row per service, sorted by how soon each row burst after the marked moment.",
    width: int = 960,
    height: int = 580,
    row: str = "service",
    at: str = "minute",
    order: str = "first-after-onset",
    onset: Optional[float] = _DEPLOY_AT,
    onset_label: str = "deploy",
    burst_within: float = 2.0,
    burst_of: int = 4,
    x_label: str = "Minutes since midnight",
    order_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full raster SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        One row per event. Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    row, at : str
        Row keys for what the event happened to, and when.
    order : str
        How the rows are stacked: ``"given"`` keeps the order they
        arrived in, ``"first"`` sorts by earliest event, ``"count"`` by
        how many events each row has, and ``"first-after-onset"`` by how
        soon each row *burst* after `onset` -- by burst rather than by
        event, because a chatty row fires soon after any moment and
        would otherwise sort among the ones that actually responded.
    onset : float or None
        The moment the raster is read against, drawn as a rule. ``None``
        draws none and falls back to ``"first"`` ordering.
    onset_label : str
        Caption on the onset rule.
    burst_within : float
        Events arriving closer together than this count as a burst.
    burst_of : int
        How many close events in a row make a burst worth marking.
    x_label : str
        Axis title.
    order_note, finding : str or None
        The line saying how the rows are sorted, and the sentence naming
        what responded; ``None`` composes each from the data.
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
    if order not in ("given", "first", "count", "first-after-onset"):
        raise ValueError(
            f"order is 'given', 'first', 'count' or 'first-after-onset', got {order!r}"
        )
    rows = list(data if data else DEMO_DATA)
    if not rows:
        raise ValueError("a raster needs at least one event")

    events: Dict[str, List[float]] = {}
    given: List[str] = []
    for item in rows:
        name = str(item[row])
        if name not in events:
            events[name] = []
            given.append(name)
        events[name].append(float(item[at]))
    for name in events:
        events[name].sort()

    wanted = order
    if onset is None and order == "first-after-onset":
        wanted = "first"

    def first_event_after(name: str) -> float:
        """When this row next fired after the onset, or infinity."""
        later = [moment for moment in events[name] if onset is not None and moment >= onset]
        return later[0] - (onset or 0.0) if later else float("inf")

    if wanted == "given":
        names = given
    elif wanted == "first":
        names = sorted(given, key=lambda name: events[name][0])
    elif wanted == "count":
        names = sorted(given, key=lambda name: -len(events[name]))
    else:
        names = sorted(given, key=lambda name: (first_event_after(name), name))

    # A burst: `burst_of` events each within `burst_within` of the last.
    bursts: Dict[str, List[Tuple[float, float]]] = {}
    for name in names:
        run: List[float] = []
        found: List[Tuple[float, float]] = []
        for moment in events[name]:
            if run and moment - run[-1] > burst_within:
                if len(run) >= burst_of:
                    found.append((run[0], run[-1]))
                run = []
            run.append(moment)
        if len(run) >= burst_of:
            found.append((run[0], run[-1]))
        bursts[name] = found

    mono_family = mono_stack_for_theme(theme)
    palette = load_palette(accessibility, theme=theme)
    quiet = palette.get("Blue", "#007AFF")
    loud = palette.get("Orange", "#FF9500")

    moments = [moment for name in names for moment in events[name]]
    span_low, span_high = min(moments), max(moments)
    if span_high - span_low < 1e-9:
        span_low, span_high = span_low - 1.0, span_high + 1.0

    plot_x = 176.0
    plot_y = 206.0
    plot_w = width - plot_x - 80.0
    plot_h = height - plot_y - 92.0
    lane = plot_h / max(len(names), 1)
    precision = (span_high - span_low) / 200.0

    def px(moment: float) -> float:
        return plot_x + (moment - span_low) / (span_high - span_low) * plot_w

    def first_burst_after(name: str) -> float:
        """How long after the onset this row *started misbehaving*.

        The first burst, not the first event. Sorting rows by their next
        event after the moment looks right and is confounded by base
        rate: a chatty row fires soon after *any* moment, so it lands
        among the responders without having responded. The first draft
        put `recommendations` third on exactly that mistake.
        """
        if onset is None:
            return float("inf")
        later = [start for start, _ in bursts[name] if start >= onset]
        return later[0] - onset if later else float("inf")

    if wanted == "first-after-onset":
        names = sorted(given, key=lambda name: (first_burst_after(name), name))

    responders = [
        name for name in names if first_burst_after(name) != float("inf")
    ]
    order_lines = (
        [order_note] if order_note is not None
        else [
            {
                "given": "rows in the order the data arrived",
                "first": "rows sorted by earliest event",
                "count": "rows sorted by how many events they carry",
                "first-after-onset": f"rows sorted by how soon they burst after the "
                                     f"{onset_label}, not by when they next fired",
            }[wanted],
            f"a burst is {burst_of} or more events each within "
            f"{fmt_number(burst_within)} of the last",
        ]
    )
    said_order = " · ".join(order_lines)
    said_parts: List[str] = []
    if finding is not None:
        said_parts.append(finding)
    elif responders:
        delays = ", ".join(
            f"{name} after {fmt_measured(first_burst_after(name), precision)}"
            for name in responders[:3]
        )
        said_parts.append(
            f"{len(responders)} of {len(names)} rows burst after the {onset_label}: "
            f"{delays}."
        )
    else:
        said_parts.append(
            f"No row bursts after the {onset_label}."
            if onset is not None
            else f"{sum(len(bursts[name]) for name in names)} bursts across "
                 f"{len(names)} rows."
        )
    said_lines: List[str] = []
    for sentence in said_parts:
        said_lines.extend(wrap_no_orphan(sentence, 104))

    parts: List[str] = []
    parts.append(
        svg_open(width, height, "raster-title", "raster-desc",
                 font_family=chrome_stack_for_theme(theme))
    )
    parts.append(f'<title id="raster-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="raster-desc">A raster of {len(moments)} events across {len(names)} '
        f'rows, each event a tick at the moment it happened. {xml_escape(said_order)}. '
        f'{xml_escape(" ".join(said_parts))}</desc>'
    )
    parts.append(
        "<style>"
        ".lane{cursor:default;}"
        ".lane:hover,.lane:focus{outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + foreground_tip_css(len(names), mark_prefix="lane", tip_prefix="lanetip")
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
    order_drawn: List[str] = []
    for clause in order_lines:
        order_drawn.extend(wrap_no_orphan(clause, 104))
    for line_index, text in enumerate(order_drawn[:2]):
        parts.append(
            f'<text x="40" y="{122 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(text)}</text>'
        )
    for line_index, text in enumerate(said_lines[:2]):
        parts.append(
            f'<text x="40" y="{164 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(text)}</text>'
        )

    if onset is not None and span_low <= onset <= span_high:
        parts.append(
            f'<line x1="{px(onset):.1f}" y1="{plot_y - 16:.1f}" x2="{px(onset):.1f}" '
            f'y2="{plot_y + plot_h:.1f}" stroke="{INK}" stroke-width="1.6" '
            f'stroke-dasharray="5 4"/>'
        )
        parts.append(
            f'<text x="{px(onset) + 6:.1f}" y="{plot_y - 20:.1f}" font-size="11" '
            f'fill="{INK}">{xml_escape(onset_label)} '
            f'{fmt_measured(onset, precision)}</text>'
        )

    tips: List[str] = []
    for index, name in enumerate(names):
        middle = plot_y + (index + 0.5) * lane
        half = min(lane * 0.34, 9.0)
        inside = {
            moment for start, stop in bursts[name] for moment in events[name]
            if start <= moment <= stop
        }
        for moment in events[name]:
            hot = moment in inside
            parts.append(
                f'<line x1="{px(moment):.1f}" y1="{middle - half:.1f}" '
                f'x2="{px(moment):.1f}" y2="{middle + half:.1f}" '
                f'stroke="{loud if hot else quiet}" '
                f'stroke-width="{1.6 if hot else 1.0}" '
                f'opacity="{0.95 if hot else 0.6}"/>'
            )
        parts.append(
            f'<text x="{plot_x - 56:.1f}" y="{middle + 4:.1f}" font-size="12" '
            f'fill="{INK}" text-anchor="end" font-family="{mono_family}">'
            f'{xml_escape(name)}</text>'
        )
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{middle + 4:.1f}" font-size="10" '
            f'fill="{SECONDARY}" text-anchor="end" font-family="{mono_family}">'
            f'{len(events[name])}</text>'
        )
        delay = first_burst_after(name)
        parts.append(
            f'<rect id="lane-{index}" class="lane hit" tabindex="0" role="img" '
            f'aria-label="{xml_escape(name)}: {len(events[name])} events, '
            f'{len(bursts[name])} burst{"" if len(bursts[name]) == 1 else "s"}'
            + (f", first burst after the {xml_escape(onset_label)} at "
               f"{fmt_measured(delay, precision)}" if delay != float("inf") else "")
            + f'" x="{plot_x:.1f}" y="{middle - lane / 2:.1f}" width="{plot_w:.1f}" '
            f'height="{lane:.1f}" fill="transparent">'
            f'<title>{xml_escape(name)}: {len(events[name])}</title></rect>'
        )
        tips.append(
            tooltip_bubble(
                plot_x + plot_w * 0.5, middle,
                [name, f"{len(events[name])} events",
                 f"{len(bursts[name])} burst{'' if len(bursts[name]) == 1 else 's'}"],
                canvas_w=width, canvas_h=height, ink=INK, secondary=SECONDARY,
                border=GRIDLINE, elem_id=f"lanetip-{index}",
            )
        )

    for step in range(6):
        moment = span_low + (span_high - span_low) * step / 5.0
        parts.append(
            f'<text x="{px(moment):.1f}" y="{plot_y + plot_h + 20:.1f}" font-size="11" '
            f'fill="{SECONDARY}" text-anchor="middle" font-family="{mono_family}">'
            f'{fmt_number(moment)}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{plot_y + plot_h + 46:.1f}" '
        f'font-size="12" fill="{SECONDARY}" text-anchor="middle">'
        f'{xml_escape(x_label)}</text>'
    )
    parts.append(
        f'<text x="{plot_x - 10:.1f}" y="{plot_y - 20:.1f}" font-size="10" '
        f'fill="{SECONDARY}" text-anchor="end" font-family="{mono_family}">events</text>'
    )

    parts.extend(tips)
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_eventplot(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[str] = None,
    title: str = "Three services start failing within seven minutes of the deploy",
    subtitle: str = "One tick per error, one row per service, sorted by how soon each row burst after the marked moment.",
    width: int = 960,
    height: int = 580,
    row: str = "service",
    at: str = "minute",
    order: str = "first-after-onset",
    onset: Optional[float] = _DEPLOY_AT,
    onset_label: str = "deploy",
    burst_within: float = 2.0,
    burst_of: int = 4,
    x_label: str = "Minutes since midnight",
    order_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Write a raster to disk and return the path.

    Parameters
    ----------
    data : list of dict or None
        One row per event. Defaults to :data:`DEMO_DATA`.
    out : str or None
        Destination path; ``None`` writes beside the script.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    row, at : str
        Row keys for what the event happened to, and when.
    order : str
        ``"given"``, ``"first"``, ``"count"`` or ``"first-after-onset"``.
    onset : float or None
        The moment the raster is read against.
    onset_label : str
        Caption on the onset rule.
    burst_within : float
        Events closer together than this count as a burst.
    burst_of : int
        How many close events make a burst worth marking.
    x_label : str
        Axis title.
    order_note, finding : str or None
        The line saying how the rows are sorted, and the sentence naming
        what responded; ``None`` composes each from the data.
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
    >>> p = make_eventplot()
    >>> p.exists()
    True
    """
    svg = build_svg(
        data, title=title, subtitle=subtitle, width=width, height=height,
        row=row, at=at, order=order, onset=onset, onset_label=onset_label,
        burst_within=burst_within, burst_of=burst_of, x_label=x_label,
        order_note=order_note, finding=finding, mode=mode,
        accessibility=accessibility, theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "eventplot")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "eventplot", build_svg,
               description="Draw a raster: one tick per event, one row per thing.")


if __name__ == "__main__":
    main()
