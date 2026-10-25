#!/usr/bin/env python3
"""
make_bump — rank over time, one ribbon per competitor.

Every competitor is a line running left to right at its rank, crossing
the others when it overtakes them. Rank throws away how far apart things
are and keeps only the order, which is the right trade when the order is
the story and the wrong one when the gaps are.

Where the usual bump chart goes wrong
---------------------------------------
* **Rank hides the size of the lead.** Two ribbons swapping places looks
  identical whether the leader was ahead by a point or by half the
  field. The underlying values are carried through here: the chrome
  reports the gap at the first and last period, and a crossing where
  the two are within `tie_within` of each other is drawn thin, because
  that overtake is a coin toss rather than an event.
* **Everything is drawn, so nothing is followed.** A bump chart of
  thirty competitors is a ball of wool. `highlight` names the few worth
  following and greys the rest into context, which is what a reader
  does by hand with a finger anyway.
* **The axis says 1 at the bottom.** Rank 1 is the best, so it belongs
  at the top, and a chart that puts it at the bottom inverts every
  reading of "rising". The axis is inverted here and labelled so.
* **A competitor missing from a period is interpolated across.** That
  draws a line through a period where the thing did not exist or was
  not measured. Gaps are left as gaps and counted.

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

_QUARTERS = ["2024 Q1", "2024 Q2", "2024 Q3", "2024 Q4",
             "2025 Q1", "2025 Q2", "2025 Q3", "2025 Q4"]

#: Starting share and quarterly drift for each browser-like competitor.
_FIELD = [
    ("Northwind", 31.0, -1.9),
    ("Beacon", 27.5, 0.4),
    ("Tessellate", 24.0, 1.7),
    ("Halcyon", 9.5, 0.9),
    ("Quillon", 5.0, -0.4),
    ("Marram", 3.0, -0.2),
]


def _standings(seed: int = 3) -> List[Dict[str, Any]]:
    """Eight quarters of market share for six competitors.

    Built so the chart has both things a bump chart can show and the one
    it usually hides. Tessellate climbs past Beacon and then holds, which
    is the overtake the eye follows. But Beacon's four quarters at the top
    end on a lead of three tenths of a point -- a first place a rank chart
    draws exactly as confidently as a commanding one. Only the values say
    otherwise, which is why they travel with the ranks here instead of
    being thrown away at the door, and why the crossing that resolves that
    near-tie is drawn thin.
    """
    rng = random.Random(seed)
    rows: List[Dict[str, Any]] = []
    for name, start, drift in _FIELD:
        share = start
        for quarter in _QUARTERS:
            share = max(0.4, share + drift + rng.gauss(0.0, 0.45))
            rows.append({
                "quarter": quarter,
                "product": name,
                "share": round(share, 2),
            })
    return rows


DEMO_DATA: List[Dict[str, Any]] = _standings()


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Beacon held first for a year, the last of it by three tenths of a point",
    subtitle: str = "Rank by quarterly share, best at the top, with the share itself carried through so the gaps stay visible.",
    width: int = 960,
    height: int = 600,
    x: str = "quarter",
    series: str = "product",
    value: str = "share",
    highlight: Optional[List[str]] = None,
    tie_within: float = 0.6,
    higher_is_better: bool = True,
    x_label: str = "Quarter",
    rank_label: str = "Rank (1 at the top)",
    rank_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full bump chart SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        One row per competitor and period. Defaults to
        :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    x, series, value : str
        Row keys for the period, the competitor, and the quantity ranked.
    highlight : list of str or None
        Which competitors to draw in full colour; the rest are greyed
        into context. ``None`` highlights every one of them.
    tie_within : float
        How close two values must be, in the units of `value`, for the
        order between them to count as a tie. A crossing between two
        tied competitors is drawn thin, because the overtake is noise.
    higher_is_better : bool
        Whether a larger `value` earns rank 1.
    x_label, rank_label : str
        Axis titles.
    rank_note, finding : str or None
        The line describing the ranking, and the sentence naming what
        changed; ``None`` composes each from the data.
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
        raise ValueError("a bump chart needs at least one row")

    periods: List[str] = []
    names: List[str] = []
    measured: Dict[Tuple[str, str], float] = {}
    for row in rows:
        period, name = str(row[x]), str(row[series])
        if period not in periods:
            periods.append(period)
        if name not in names:
            names.append(name)
        measured[(name, period)] = float(row[value])
    if len(periods) < 2:
        raise ValueError(
            f"a bump chart needs at least two periods; this data has {len(periods)}"
        )

    ranks: Dict[Tuple[str, str], int] = {}
    for period in periods:
        present = [name for name in names if (name, period) in measured]
        present.sort(
            key=lambda name: measured[(name, period)], reverse=higher_is_better
        )
        for position, name in enumerate(present, start=1):
            ranks[(name, period)] = position
    missing = len(names) * len(periods) - len(measured)

    followed = set(highlight) if highlight else set(names)
    unknown = sorted(followed - set(names))
    if unknown:
        raise ValueError(f"highlight names competitors not in the data: {unknown}")

    mono_family = mono_stack_for_theme(theme)
    palette = load_palette(accessibility, theme=theme)
    wheel = [
        palette.get(key, fallback) for key, fallback in (
            ("Blue", "#007AFF"), ("Orange", "#FF9500"), ("Green", "#28CD41"),
            ("Purple", "#5856D6"), ("Red", "#FF3B30"), ("Teal", "#30B0C7"),
        )
    ]
    ink_for = {name: wheel[index % len(wheel)] for index, name in enumerate(names)}

    plot_x = 150.0
    plot_y = 214.0
    plot_w = width - plot_x - 164.0
    plot_h = height - plot_y - 92.0
    depth = max(ranks.values()) if ranks else 1
    step = plot_w / max(len(periods) - 1, 1)
    lane = plot_h / max(depth, 1)
    spread = max(measured.values()) - min(measured.values()) if measured else 0.0
    precision = max(tie_within, spread / 50.0)

    def px(index: int) -> float:
        return plot_x + index * step

    def py(rank: int) -> float:
        return plot_y + (rank - 0.5) * lane

    leader_first = min(
        (name for name in names if (name, periods[0]) in measured),
        key=lambda name: ranks[(name, periods[0])],
    )
    leader_last = min(
        (name for name in names if (name, periods[-1]) in measured),
        key=lambda name: ranks[(name, periods[-1])],
    )

    def lead_at(period: str) -> float:
        """How far the leader is ahead of second place, in `value` units."""
        present = sorted(
            (measured[(name, period)] for name in names if (name, period) in measured),
            reverse=higher_is_better,
        )
        return abs(present[0] - present[1]) if len(present) > 1 else 0.0

    rank_lines = (
        [rank_note] if rank_note is not None
        else [
            f"{len(names)} competitors ranked by {value} each period, "
            + ("highest first" if higher_is_better else "lowest first"),
            f"a crossing between two within {fmt_number(tie_within)} is drawn thin: "
            f"that order is a coin toss",
        ] + ([f"{missing} competitor-periods have no value and are left as gaps"]
             if missing else [])
    )
    said_rank = " · ".join(rank_lines)
    said_parts: List[str] = []
    if finding is not None:
        said_parts.append(finding)
    elif leader_first != leader_last:
        said_parts.append(
            f"{leader_last} ends first where {leader_first} began, and the lead changed "
            f"size with the name: {fmt_measured(lead_at(periods[0]), precision)} at "
            f"{periods[0]}, {fmt_measured(lead_at(periods[-1]), precision)} at "
            f"{periods[-1]}."
        )
    else:
        said_parts.append(
            f"{leader_first} leads throughout, by "
            f"{fmt_measured(lead_at(periods[0]), precision)} at the start and "
            f"{fmt_measured(lead_at(periods[-1]), precision)} at the end."
        )
    said_lines: List[str] = []
    for sentence in said_parts:
        said_lines.extend(wrap_no_orphan(sentence, 104))

    parts: List[str] = []
    parts.append(
        svg_open(width, height, "bump-title", "bump-desc",
                 font_family=chrome_stack_for_theme(theme))
    )
    parts.append(f'<title id="bump-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="bump-desc">A bump chart of {len(names)} competitors across '
        f'{len(periods)} periods from {xml_escape(periods[0])} to '
        f'{xml_escape(periods[-1])}, each a line at its rank with rank 1 at the top. '
        f'{xml_escape(said_rank)}. {xml_escape(" ".join(said_parts))}</desc>'
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
    rank_drawn: List[str] = []
    for clause in rank_lines:
        rank_drawn.extend(wrap_no_orphan(clause, 104))
    for line_index, text in enumerate(rank_drawn[:2]):
        parts.append(
            f'<text x="40" y="{122 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(text)}</text>'
        )
    for line_index, text in enumerate(said_lines[:2]):
        parts.append(
            f'<text x="40" y="{166 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(text)}</text>'
        )

    for rank in range(1, depth + 1):
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{py(rank):.1f}" x2="{plot_x + plot_w:.1f}" '
            f'y2="{py(rank):.1f}" stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{plot_x - 118:.1f}" y="{py(rank) + 4:.1f}" font-size="11" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{rank}</text>'
        )

    tips: List[str] = []
    for index, name in enumerate(names):
        colour = ink_for[name] if name in followed else SECONDARY
        opacity = 1.0 if name in followed else 0.28
        segments: List[List[Tuple[float, float, bool]]] = [[]]
        for position, period in enumerate(periods):
            if (name, period) not in measured:
                if segments[-1]:
                    segments.append([])
                continue
            tied = False
            if position:
                before = periods[position - 1]
                rival = [
                    other for other in names
                    if other != name and (other, period) in measured
                    and (other, before) in measured
                    and (ranks[(other, period)] - ranks[(name, period)])
                    * (ranks[(other, before)] - ranks[(name, before)]) < 0
                ]
                # Measured at the closest of the two periods, not at the
                # far end. Two competitors three tenths apart in Q1 and a
                # point and a half apart in Q2 crossed on the three tenths;
                # judging the crossing by where they ended up calls a coin
                # toss an event.
                tied = any(
                    min(
                        abs(measured[(other, period)] - measured[(name, period)]),
                        abs(measured[(other, before)] - measured[(name, before)]),
                    ) <= tie_within
                    for other in rival
                )
            segments[-1].append((px(position), py(ranks[(name, period)]), tied))
        for run in segments:
            for step_index in range(1, len(run)):
                x1, y1, _ = run[step_index - 1]
                x2, y2, tied = run[step_index]
                mid = (x1 + x2) / 2.0
                parts.append(
                    f'<path d="M{x1:.1f},{y1:.1f} C{mid:.1f},{y1:.1f} {mid:.1f},{y2:.1f} '
                    f'{x2:.1f},{y2:.1f}" fill="none" stroke="{colour}" '
                    f'stroke-width="{1.4 if tied else 3.0:.1f}" opacity="{opacity}"/>'
                )
            for spot_x, spot_y, _ in run:
                parts.append(
                    f'<circle cx="{spot_x:.1f}" cy="{spot_y:.1f}" r="4" fill="{colour}" '
                    f'opacity="{opacity}"/>'
                )
        if (name, periods[0]) in measured:
            parts.append(
                f'<text x="{plot_x - 12:.1f}" y="{py(ranks[(name, periods[0])]) + 4:.1f}" '
                f'font-size="12" fill="{colour}" text-anchor="end" opacity="{opacity}">'
                f'{xml_escape(name)}</text>'
            )
        if (name, periods[-1]) in measured:
            parts.append(
                f'<text x="{plot_x + plot_w + 12:.1f}" '
                f'y="{py(ranks[(name, periods[-1])]) + 4:.1f}" font-size="12" '
                f'fill="{colour}" opacity="{opacity}">'
                f'{fmt_measured(measured[(name, periods[-1])], precision)}</text>'
            )
        moved = (
            ranks.get((name, periods[0]), 0) - ranks.get((name, periods[-1]), 0)
        )
        parts.append(
            f'<rect id="lane-{index}" class="lane hit" tabindex="0" role="img" '
            f'aria-label="{xml_escape(name)}: rank '
            f'{ranks.get((name, periods[0]), 0)} at {xml_escape(periods[0])}, '
            f'{ranks.get((name, periods[-1]), 0)} at {xml_escape(periods[-1])}, '
            f'{"up" if moved > 0 else ("down" if moved < 0 else "unchanged")} '
            f'{abs(moved)}" x="{plot_x:.1f}" '
            f'y="{py(ranks.get((name, periods[-1]), 1)) - lane / 2:.1f}" '
            f'width="{plot_w:.1f}" height="{lane:.1f}" fill="transparent">'
            f'<title>{xml_escape(name)}</title></rect>'
        )
        tips.append(
            tooltip_bubble(
                plot_x + plot_w * 0.5, py(ranks.get((name, periods[-1]), 1)),
                [name,
                 f"rank {ranks.get((name, periods[0]), 0)} → "
                 f"{ranks.get((name, periods[-1]), 0)}",
                 f"{fmt_measured(measured.get((name, periods[-1]), 0.0), precision)} "
                 f"at {periods[-1]}"],
                canvas_w=width, canvas_h=height, ink=INK, secondary=SECONDARY,
                border=GRIDLINE, elem_id=f"lanetip-{index}",
            )
        )

    for position, period in enumerate(periods):
        parts.append(
            f'<text x="{px(position):.1f}" y="{plot_y + plot_h + 20:.1f}" font-size="11" '
            f'fill="{SECONDARY}" text-anchor="middle" font-family="{mono_family}">'
            f'{xml_escape(period)}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{plot_y + plot_h + 46:.1f}" '
        f'font-size="12" fill="{SECONDARY}" text-anchor="middle">'
        f'{xml_escape(x_label)}</text>'
    )
    parts.append(
        f'<text x="40" y="{plot_y - 12:.1f}" font-size="12" fill="{SECONDARY}">'
        f'{xml_escape(rank_label)}</text>'
    )

    parts.extend(tips)
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_bump(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[str] = None,
    title: str = "Beacon held first for a year, the last of it by three tenths of a point",
    subtitle: str = "Rank by quarterly share, best at the top, with the share itself carried through so the gaps stay visible.",
    width: int = 960,
    height: int = 600,
    x: str = "quarter",
    series: str = "product",
    value: str = "share",
    highlight: Optional[List[str]] = None,
    tie_within: float = 0.6,
    higher_is_better: bool = True,
    x_label: str = "Quarter",
    rank_label: str = "Rank (1 at the top)",
    rank_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Write a bump chart to disk and return the path.

    Parameters
    ----------
    data : list of dict or None
        One row per competitor and period. Defaults to :data:`DEMO_DATA`.
    out : str or None
        Destination path; ``None`` writes beside the script.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    x, series, value : str
        Row keys for the period, the competitor, and the quantity ranked.
    highlight : list of str or None
        Which competitors to draw in full colour.
    tie_within : float
        How close two values must be for their order to count as a tie.
    higher_is_better : bool
        Whether a larger `value` earns rank 1.
    x_label, rank_label : str
        Axis titles.
    rank_note, finding : str or None
        The line describing the ranking, and the sentence naming what
        changed; ``None`` composes each from the data.
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
    >>> p = make_bump()
    >>> p.exists()
    True
    """
    svg = build_svg(
        data, title=title, subtitle=subtitle, width=width, height=height,
        x=x, series=series, value=value, highlight=highlight,
        tie_within=tie_within, higher_is_better=higher_is_better,
        x_label=x_label, rank_label=rank_label, rank_note=rank_note,
        finding=finding, mode=mode, accessibility=accessibility, theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "bump")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "bump", build_svg,
               description="Draw rank over time, one ribbon per competitor.")


if __name__ == "__main__":
    main()
