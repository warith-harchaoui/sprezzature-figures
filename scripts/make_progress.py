#!/usr/bin/env python3
"""
make_progress — how far along, against how far along you should be.

One bar per goal, filled to what has been achieved, with a mark where
the goal *should* stand if the period were being used evenly. The mark
is the whole point: a bar at 60% is good news in month eleven and bad
news in month two, and a progress bar without it cannot tell you which.

Where the usual progress chart goes wrong
-------------------------------------------
* **There is no pace.** A filled bar says how far along, never whether
  that is far enough. The expected position is drawn as a rule on every
  bar and the gap to it is given in points, which is the number a
  reader is about to act on.
* **Everything is reported as a percentage of its own target, so goals
  of wildly different size look equal.** A bar is a share, and a share
  hides the scale. The absolute figure and the target travel with each
  bar.
* **Overshoot is clipped at 100%.** A goal already at 130% is not the
  same as one that just landed, and clipping deletes the difference.
  The bar runs past its end, marked.
* **The order is whatever the list was in.** Sorted by how far behind
  pace each goal is, the chart answers the question it is read for --
  what needs attention -- in its first row.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

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

#: ``paced`` marks a goal that *accumulates* over the period, which is
#: the only kind a pace rule can speak about. Uptime and churn are rates:
#: they do not build up, so three quarters of the year does not mean
#: three quarters of the target, and drawing a rule there would invent a
#: schedule the goal never had.
DEMO_DATA: List[Dict[str, Any]] = [
    {"goal": "New paying teams", "done": 412.0, "target": 600.0, "paced": 1},
    {"goal": "Docs pages rewritten", "done": 58.0, "target": 140.0, "paced": 1},
    {"goal": "Support tickets closed", "done": 7_430.0, "target": 9_000.0, "paced": 1},
    {"goal": "Partner integrations", "done": 11.0, "target": 9.0, "paced": 1},
    {"goal": "Uptime", "done": 0.9994, "target": 0.999, "paced": 0},
    {"goal": "Churn below 2%", "done": 0.0171, "target": 0.02, "paced": 0},
]


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Two of the four scheduled goals are behind, the docs by a third of the year",
    subtitle: str = "Each bar is progress toward its target, with a rule where the goal should stand nine months into twelve.",
    width: int = 940,
    height: int = 560,
    label: str = "goal",
    done: str = "done",
    target: str = "target",
    paced: str = "paced",
    elapsed: float = 0.75,
    sort_by_lag: bool = True,
    pace_label: str = "expected by now",
    behind_label: str = "behind",
    ahead_label: str = "ahead",
    pace_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full progress SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        One row per goal. Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    label, done, target : str
        Row keys for the goal's name, what has been achieved, and what
        it is aiming at.
    paced : str
        Row key for whether the goal *accumulates* over the period. A
        pace rule can only speak about goals that do: uptime and churn
        are rates, three quarters of the year is not three quarters of
        the target, and a rule there invents a schedule. A row without
        this key is taken as paced.
    elapsed : float
        How much of the period has gone, from 0 to 1. The expected
        position of every bar, and the reason the chart can say whether
        a number is good.
    sort_by_lag : bool
        Order the goals by how far behind pace they are, so the row that
        needs attention is the first one.
    pace_label : str
        Caption on the pace rule.
    behind_label, ahead_label : str
        Words for a goal short of pace and past it.
    pace_note, finding : str or None
        The line stating the period and the pace, and the sentence
        naming what is behind; ``None`` composes each from the data.
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
    if not 0.0 <= elapsed <= 1.0:
        raise ValueError(f"elapsed is a share of the period, 0 to 1; got {elapsed}")
    rows = list(data if data else DEMO_DATA)
    if not rows:
        raise ValueError("a progress chart needs at least one goal")

    goals: List[Dict[str, Any]] = []
    for row in rows:
        aim = float(row[target])
        if aim == 0.0:
            raise ValueError(
                f"the goal {row[label]!r} has a target of zero, so there is no share to draw"
            )
        achieved = float(row[done])
        accumulates = bool(row.get(paced, 1))
        goals.append(
            {
                "name": str(row[label]),
                "done": achieved,
                "target": aim,
                "share": achieved / aim,
                "paced": accumulates,
                "lag": (achieved / aim - elapsed) if accumulates else None,
            }
        )
    if sort_by_lag:
        # Unpaced goals have no lag to sort on, so they sit below the
        # ones a schedule can be argued about.
        goals.sort(key=lambda goal: (goal["lag"] is None, goal["lag"] or 0.0))

    tracked = [goal for goal in goals if goal["paced"]]
    behind = [goal for goal in tracked if goal["lag"] < 0.0]
    worst = min(tracked, key=lambda goal: goal["lag"]) if tracked else None

    mono_family = mono_stack_for_theme(theme)
    palette = load_palette(accessibility, theme=theme)
    on_track = palette.get("Blue", "#007AFF")
    lagging = palette.get("Orange", "#FF9500")
    over = palette.get("Green", "#28CD41")

    plot_x = 232.0
    plot_y = 206.0
    plot_w = width - plot_x - 150.0
    plot_h = height - plot_y - 72.0
    lane = plot_h / max(len(goals), 1)
    reach = max(1.0, max(goal["share"] for goal in goals))

    def px(share: float) -> float:
        return plot_x + min(share, reach) / reach * plot_w

    pace_lines = (
        [pace_note]
        if pace_note is not None
        else [
            f"{fmt_number(elapsed * 100.0)}% of the period has gone, so the rule on each "
            f"bar is where it should stand",
            f"{len(goals) - len(tracked)} of {len(goals)} goals are rates, not "
            f"accumulations, and carry no pace rule"
            if len(tracked) < len(goals)
            else "bars run past their target rather than clipping at 100%",
        ]
    )
    said_pace = " · ".join(pace_lines)
    said_parts: List[str] = []
    if finding is not None:
        said_parts.append(finding)
    elif behind and worst is not None:
        said_parts.append(
            f"{len(behind)} of the {len(tracked)} goals on a schedule are "
            f"{behind_label} pace; the furthest is {worst['name']}, "
            f"{fmt_number(abs(worst['lag']) * 100.0)} points short."
        )
    else:
        said_parts.append(f"Every goal is at or {ahead_label} of pace.")
    said_lines: List[str] = []
    for sentence in said_parts:
        said_lines.extend(wrap_no_orphan(sentence, 104))

    parts: List[str] = []
    parts.append(
        svg_open(
            width,
            height,
            "progress-title",
            "progress-desc",
            font_family=chrome_stack_for_theme(theme),
        )
    )
    parts.append(f'<title id="progress-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="progress-desc">Progress toward {len(goals)} goals, each a bar filled '
        f"to what has been achieved with a rule marking where it should stand. "
        f"{xml_escape(said_pace)}. {xml_escape(' '.join(said_parts))}</desc>"
    )
    parts.append(
        "<style>"
        ".goal{cursor:default;}"
        ".goal:hover,.goal:focus{outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + foreground_tip_css(len(goals), mark_prefix="goal", tip_prefix="goaltip")
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
    pace_drawn: List[str] = []
    for clause in pace_lines:
        pace_drawn.extend(wrap_no_orphan(clause, 104))
    for line_index, text in enumerate(pace_drawn[:2]):
        parts.append(
            f'<text x="40" y="{124 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(text)}</text>'
        )
    for line_index, text in enumerate(said_lines[:2]):
        parts.append(
            f'<text x="40" y="{166 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(text)}</text>'
        )

    tips: List[str] = []
    for index, goal in enumerate(goals):
        top = plot_y + index * lane + lane * 0.22
        thickness = lane * 0.46
        share = goal["share"]
        colour = (
            over if share >= 1.0 else (lagging if goal["paced"] and goal["lag"] < 0.0 else on_track)
        )
        parts.append(
            f'<rect x="{plot_x:.1f}" y="{top:.1f}" width="{plot_w:.1f}" '
            f'height="{thickness:.1f}" fill="{GRIDLINE}" opacity="0.5" rx="3"/>'
        )
        parts.append(
            f'<rect x="{plot_x:.1f}" y="{top:.1f}" '
            f'width="{max(px(share) - plot_x, 1.0):.1f}" height="{thickness:.1f}" '
            f'fill="{colour}" rx="3"/>'
        )
        # The target, and the pace: two different marks, because
        # "finished" and "on schedule" are two different questions.
        parts.append(
            f'<line x1="{px(1.0):.1f}" y1="{top - 3:.1f}" x2="{px(1.0):.1f}" '
            f'y2="{top + thickness + 3:.1f}" stroke="{INK}" stroke-width="1.4"/>'
        )
        if goal["paced"]:
            parts.append(
                f'<line x1="{px(elapsed):.1f}" y1="{top - 5:.1f}" x2="{px(elapsed):.1f}" '
                f'y2="{top + thickness + 5:.1f}" stroke="{INK}" stroke-width="1.2" '
                f'stroke-dasharray="3 3" opacity="0.65"/>'
            )
        parts.append(
            f'<text x="{plot_x - 14:.1f}" y="{top + thickness * 0.75:.1f}" '
            f'font-size="12" fill="{INK}" text-anchor="end">{xml_escape(goal["name"])}'
            f"</text>"
        )
        # The precision that matters for a row is the gap it is about:
        # an uptime target of 0.999 against 0.9994 needs four decimals,
        # a target of 9 against 11 needs none. Keyed to the target alone
        # this printed "11.0000 / 9.0000".
        precision = max(abs(goal["target"] - goal["done"]), abs(goal["target"]) / 1000.0)
        parts.append(
            f'<text x="{plot_x + plot_w + 12:.1f}" y="{top + thickness * 0.75:.1f}" '
            f'font-size="11" fill="{SECONDARY}" font-family="{mono_family}">'
            f"{fmt_measured(goal['done'], precision)} / "
            f"{fmt_measured(goal['target'], precision)}</text>"
        )
        gap = (goal["lag"] or 0.0) * 100.0
        standing = (
            f"{fmt_number(abs(gap))} points {behind_label if gap < 0 else ahead_label}"
            if goal["paced"]
            else "not on a schedule"
        )
        parts.append(
            f'<text x="{plot_x - 14:.1f}" y="{top + thickness + 13:.1f}" font-size="10" '
            f'fill="{lagging if goal["paced"] and gap < 0 else SECONDARY}" '
            f'text-anchor="end" font-family="{mono_family}">'
            f"{fmt_number(share * 100.0)}% · {xml_escape(standing)}</text>"
        )
        parts.append(
            f'<rect id="goal-{index}" class="goal hit" tabindex="0" role="img" '
            f'aria-label="{xml_escape(goal["name"])}: '
            f"{fmt_measured(goal['done'], precision)} of "
            f"{fmt_measured(goal['target'], precision)}, {fmt_number(share * 100.0)}%, "
            f'{xml_escape(standing)}" '
            f'x="{plot_x:.1f}" y="{plot_y + index * lane:.1f}" width="{plot_w:.1f}" '
            f'height="{lane:.1f}" fill="transparent">'
            f"<title>{xml_escape(goal['name'])}: "
            f"{fmt_number(share * 100.0)}%</title></rect>"
        )
        tips.append(
            tooltip_bubble(
                px(min(share, reach)),
                top + thickness / 2.0,
                [
                    goal["name"],
                    f"{fmt_measured(goal['done'], precision)} / "
                    f"{fmt_measured(goal['target'], precision)} · "
                    f"{fmt_number(share * 100.0)}%",
                    standing,
                ],
                canvas_w=width,
                canvas_h=height,
                ink=INK,
                secondary=SECONDARY,
                border=GRIDLINE,
                elem_id=f"goaltip-{index}",
            )
        )

    parts.append(
        f'<text x="{px(elapsed):.1f}" y="{plot_y - 10:.1f}" font-size="11" '
        f'fill="{INK}" text-anchor="middle">{xml_escape(pace_label)}</text>'
    )
    parts.append(
        f'<text x="{px(1.0):.1f}" y="{plot_y + plot_h + 22:.1f}" font-size="11" '
        f'fill="{SECONDARY}" text-anchor="middle" font-family="{mono_family}">target'
        f"</text>"
    )

    parts.extend(tips)
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_progress(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[str] = None,
    title: str = "Two of the four scheduled goals are behind, the docs by a third of the year",
    subtitle: str = "Each bar is progress toward its target, with a rule where the goal should stand nine months into twelve.",
    width: int = 940,
    height: int = 560,
    label: str = "goal",
    done: str = "done",
    target: str = "target",
    paced: str = "paced",
    elapsed: float = 0.75,
    sort_by_lag: bool = True,
    pace_label: str = "expected by now",
    behind_label: str = "behind",
    ahead_label: str = "ahead",
    pace_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Write a progress chart to disk and return the path.

    Parameters
    ----------
    data : list of dict or None
        One row per goal. Defaults to :data:`DEMO_DATA`.
    out : str or None
        Destination path; ``None`` writes beside the script.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    label, done, target : str
        Row keys for the goal's name, what has been achieved, and the
        target.
    paced : str
        Row key for whether the goal accumulates over the period.
    elapsed : float
        How much of the period has gone, from 0 to 1.
    sort_by_lag : bool
        Order the goals by how far behind pace they are.
    pace_label : str
        Caption on the pace rule.
    behind_label, ahead_label : str
        Words for a goal short of pace and past it.
    pace_note, finding : str or None
        The line stating the period and the pace, and the sentence
        naming what is behind; ``None`` composes each from the data.
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
    >>> p = make_progress()
    >>> p.exists()
    True
    """
    svg = build_svg(
        data,
        title=title,
        subtitle=subtitle,
        width=width,
        height=height,
        label=label,
        done=done,
        target=target,
        paced=paced,
        elapsed=elapsed,
        sort_by_lag=sort_by_lag,
        pace_label=pace_label,
        behind_label=behind_label,
        ahead_label=ahead_label,
        pace_note=pace_note,
        finding=finding,
        mode=mode,
        accessibility=accessibility,
        theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "progress")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(
        __file__,
        "progress",
        build_svg,
        description="Draw progress toward goals against the pace they should keep.",
    )


if __name__ == "__main__":
    main()
