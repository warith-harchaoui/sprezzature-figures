#!/usr/bin/env python3
"""
make_cohort-retention — who stays, by when they arrived.

One row per cohort, one column per period of age, each cell the share of
that cohort still present. The triangle shape is not a flaw: the newest
cohort has had one month to be measured, and the oldest has had twelve.

Where the usual retention triangle goes wrong
----------------------------------------------
* **Not-yet-measured is drawn as zero.** The top-right of the grid is
  empty because those periods have not happened yet, and a colour scale
  that starts at zero paints them the same dark shade as a cohort that
  left. Here they carry no fill and a hatched outline, and the chrome
  says how many cells are waiting rather than missing.
* **The colour scale runs from 0 to 100%.** Retention past the first
  month is rarely above half, so every cell lands in the bottom third of
  the ramp and the grid reads as one flat colour. The scale is taken
  from the measured cells and both ends are labelled.
* **Nobody marks where the curve flattens.** The decision a retention
  triangle informs is whether the churn stops, and at what level. The
  age at which the average cohort's month-on-month loss first falls
  below `plateau_at` is marked with a rule and named.
* **A bad month reads as a bad cohort.** An outage hits every cohort on
  the same *calendar* date, which in a triangle is a diagonal, not a
  row. The diagonals are checked, and one that sits well below its
  neighbours is named by the period it fell in.

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
    fmt_number,
    foreground_tip_css,
    svg_open,
    tooltip_bubble,
    wrap_no_orphan,
    xml_escape,
)
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

_COHORTS = 12
_OUTAGE_MONTH = 9  # calendar month index where the service broke


def _signups(seed: int = 23) -> List[Dict[str, Any]]:
    """Twelve monthly cohorts of a subscription, measured up to today.

    Each cohort is followed only as far as the present, which is what
    makes the triangle a triangle: the cohort that signed up last month
    has one period of history, not twelve of zeros.

    One calendar month is deliberately bad. In month 9 the service broke,
    and every cohort alive at that date lost extra members -- the cohort
    that was six months old and the one that was one month old alike.
    That lands on a *diagonal* of this grid, not a row, which is exactly
    the reading the usual triangle makes hard and the reason the
    diagonals are checked here.
    """
    rng = random.Random(seed)
    rows: List[Dict[str, Any]] = []
    for cohort_index in range(_COHORTS):
        size = rng.randint(820, 1450)
        alive = float(size)
        for age in range(_COHORTS - cohort_index):
            if age:
                # Churn eases as the cohort settles: steep in the first
                # months, then a long flat tail.
                leaving = 0.04 + 0.55 / (age + 1.0) ** 2
                calendar = cohort_index + age
                if calendar == _OUTAGE_MONTH:
                    leaving += 0.18
                alive *= 1.0 - leaving * rng.uniform(0.9, 1.1)
            rows.append({
                "cohort": f"2025-{cohort_index + 1:02d}",
                "period": age,
                "users": int(round(alive)),
            })
    return rows


DEMO_DATA: List[Dict[str, Any]] = _signups()


def _ramp(fraction: float) -> Tuple[float, float, float]:
    """A light-to-saturated ramp as (r, g, b) in 0-255, for `fraction` in 0-1."""
    fraction = max(0.0, min(1.0, fraction))
    start = (232.0, 240.0, 254.0)
    end = (12.0, 74.0, 166.0)
    return tuple(start[i] + (end[i] - start[i]) * fraction for i in range(3))  # type: ignore[return-value]


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Churn settles at month 5, and one bad calendar month cuts across every cohort",
    subtitle: str = "Twelve monthly cohorts, each followed as far as today; the empty corner is not yet measured.",
    width: int = 940,
    height: int = 664,
    cohort: str = "cohort",
    period: str = "period",
    value: str = "users",
    value_is_rate: bool = False,
    include_period_zero: bool = False,
    plateau_at: float = 0.06,
    diagonal_gap: float = 0.08,
    cohort_label: str = "Cohort",
    period_label: str = "Months since signup",
    pending_label: str = "not yet measured",
    scale_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full retention triangle SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        One row per cohort and period. Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    cohort, period, value : str
        Row keys for the cohort name, the age in periods, and the
        measured quantity.
    value_is_rate : bool
        Whether `value` is already a share in 0 to 1. ``False`` reads it
        as a count and divides each cohort by its own period-zero count.
    include_period_zero : bool
        Draw the period-zero column, which is 100% by construction.
        Omitted by default: it spends a column of the grid stating a
        definition, and the chrome says it was dropped.
    plateau_at : float
        The month-on-month loss, median over cohorts, below which the
        curve counts as flat.
    diagonal_gap : float
        How far below its neighbours a calendar diagonal must sit before
        it is called out.
    cohort_label, period_label : str
        Axis titles.
    pending_label : str
        What the unfilled cells are called in the key.
    scale_note, finding : str or None
        The line describing the colour scale, and the sentence naming
        the plateau and any bad calendar month; ``None`` composes each
        from the data.
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
        raise ValueError("a retention triangle needs at least one row")

    cohorts: List[str] = []
    for row in rows:
        name = str(row[cohort])
        if name not in cohorts:
            cohorts.append(name)
    ages = sorted({int(row[period]) for row in rows})
    if not ages:
        raise ValueError(f"no row carries a period under {period!r}")

    measured: Dict[Tuple[str, int], float] = {}
    base: Dict[str, float] = {}
    for row in rows:
        name, age = str(row[cohort]), int(row[period])
        amount = float(row[value])
        if value_is_rate:
            measured[(name, age)] = amount
        else:
            if age == min(ages):
                base[name] = amount
            measured[(name, age)] = amount
    if not value_is_rate:
        missing_base = [name for name in cohorts if not base.get(name)]
        if missing_base:
            raise ValueError(
                f"{len(missing_base)} cohort(s) have no period-{min(ages)} row to divide "
                f"by, so their retention cannot be computed: {', '.join(missing_base[:4])}"
            )
        measured = {
            (name, age): amount / base[name] for (name, age), amount in measured.items()
        }

    shown_ages = [age for age in ages if include_period_zero or age != min(ages)]
    if not shown_ages:
        raise ValueError("nothing left to draw once period zero is dropped")

    present = [
        measured[(name, age)]
        for name in cohorts for age in shown_ages if (name, age) in measured
    ]
    if not present:
        raise ValueError("no cell has a value to draw")
    low, high = min(present), max(present)
    if high - low < 1e-9:
        low, high = low - 0.01, high + 0.01
    pending = len(cohorts) * len(shown_ages) - len(present)

    # Where the curve flattens: the first age at which the average cohort
    # loses less than `plateau_at` of itself against the previous age.
    def loss_between(previous: int, current: int) -> Optional[float]:
        """Mean share lost between two ages, over cohorts measured at both.

        Paired on purpose. Averaging each column and differencing the
        averages compares two *different* sets of cohorts, because the
        newest ones drop out of the older columns -- so a composition
        change reads as churn, and the plateau lands wherever the
        membership happens to shift.
        """
        pairs = [
            (measured[(name, previous)], measured[(name, current)])
            for name in cohorts
            if (name, previous) in measured and (name, current) in measured
        ]
        usable = sorted(
            (before - after) / before for before, after in pairs if before > 0.0
        )
        if not usable:
            return None
        # The median, not the mean. One cohort caught by a bad calendar
        # month loses three times what the others do, and a mean carries
        # that across the threshold for every pair it appears in -- which
        # moved the plateau this figure reports from month 5 to month 10.
        middle = len(usable) // 2
        return (
            usable[middle] if len(usable) % 2
            else (usable[middle - 1] + usable[middle]) / 2.0
        )

    plateau: Optional[int] = None
    for index in range(1, len(shown_ages)):
        loss = loss_between(shown_ages[index - 1], shown_ages[index])
        if loss is not None and loss < plateau_at:
            plateau = shown_ages[index]
            break

    # A calendar month, not a cohort: in this grid that is a diagonal.
    # Compared against what each cell's *age* predicts, not against the
    # other diagonals. A later diagonal holds older cells and is lower for
    # that reason alone; ranking the raw means would call every one of
    # them a bad month and the last one the worst.
    by_age = {
        age: [measured[(name, age)] for name in cohorts if (name, age) in measured]
        for age in shown_ages
    }
    expected = {age: sum(v) / len(v) for age, v in by_age.items() if v}
    residuals: Dict[int, List[float]] = {}
    for cohort_index, name in enumerate(cohorts):
        for age in shown_ages:
            if (name, age) in measured and expected.get(age):
                residuals.setdefault(cohort_index + age, []).append(
                    measured[(name, age)] / expected[age] - 1.0
                )
    bad_calendar: Optional[int] = None
    scored = {k: sum(v) / len(v) for k, v in residuals.items() if len(v) > 1}
    if scored:
        worst = min(scored, key=lambda k: scored[k])
        if scored[worst] < -diagonal_gap:
            bad_calendar = worst

    mono_family = mono_stack_for_theme(theme)
    palette = load_palette(accessibility, theme=theme)
    accent = palette.get("Orange", "#FF9500")

    plot_x = 128.0
    plot_y = 252.0
    plot_w = width - plot_x - 56.0
    plot_h = height - plot_y - 96.0
    cell_w = plot_w / len(shown_ages)
    cell_h = plot_h / len(cohorts)

    scale_lines = (
        [scale_note] if scale_note is not None
        else [
            f"colour runs {fmt_number(low * 100.0)}% to {fmt_number(high * 100.0)}%, "
            f"the range of the measured cells, not 0 to 100"
        ] + ([] if include_period_zero else ["period 0 omitted, it is 100% by definition"])
    )
    said_scale = " · ".join(scale_lines)
    said_parts: List[str] = []
    if finding is not None:
        said_parts.append(finding)
    else:
        if plateau is not None:
            said_parts.append(
                f"The typical cohort stops losing more than "
                f"{fmt_number(plateau_at * 100.0)}% a period at month {plateau}."
            )
        else:
            said_parts.append(
                f"No period yet brings the typical loss under "
                f"{fmt_number(plateau_at * 100.0)}%: the curve has not flattened."
            )
        if bad_calendar is not None:
            said_parts.append(
                f"Calendar period {bad_calendar} sits more than "
                f"{fmt_number(diagonal_gap * 100.0)}% below the rest: a bad month, not a "
                f"bad cohort."
            )
        if pending:
            said_parts.append(
                f"{pending} of {len(cohorts) * len(shown_ages)} cells are "
                f"{pending_label}."
            )
    said_lines: List[str] = []
    for sentence in said_parts:
        said_lines.extend(wrap_no_orphan(sentence, 100))

    parts: List[str] = []
    parts.append(
        svg_open(width, height, "cohort-title", "cohort-desc",
                 font_family=chrome_stack_for_theme(theme))
    )
    parts.append(f'<title id="cohort-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="cohort-desc">A retention triangle of {len(cohorts)} cohorts against '
        f'{len(shown_ages)} periods of age, each cell shaded by the share of its cohort '
        f'still present. {xml_escape(said_scale)}. '
        f'{xml_escape(" ".join(said_parts))}</desc>'
    )
    parts.append(
        "<style>"
        ".cell{cursor:default;}"
        ".cell:hover,.cell:focus{outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + foreground_tip_css(len(cohorts) * len(shown_ages),
                             mark_prefix="cell", tip_prefix="celltip")
        + "@media (prefers-reduced-motion:reduce){.tip{transition:none}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="40" y="46" font-size="22" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    for line_index, line in enumerate(wrap_no_orphan(subtitle, 106)[:2]):
        parts.append(
            f'<text x="40" y="{72 + line_index * 20:.1f}" font-size="14" '
            f'fill="{SECONDARY}">{xml_escape(line)}</text>'
        )
    # One clause per line: poured into a fixed width, this note broke at
    # "it is 100% / by definition".
    scale_drawn: List[str] = []
    for clause in scale_lines:
        scale_drawn.extend(wrap_no_orphan(clause, 100))
    for line_index, line in enumerate(scale_drawn[:2]):
        parts.append(
            f'<text x="40" y="{124 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(line)}</text>'
        )
    for line_index, line in enumerate(said_lines[:3]):
        parts.append(
            f'<text x="40" y="{162 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(line)}</text>'
        )

    tips: List[str] = []
    for cohort_index, name in enumerate(cohorts):
        top = plot_y + cohort_index * cell_h
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{top + cell_h / 2 + 4:.1f}" font-size="11" '
            f'fill="{SECONDARY}" text-anchor="end" font-family="{mono_family}">'
            f'{xml_escape(name)}</text>'
        )
        for age_index, age in enumerate(shown_ages):
            left = plot_x + age_index * cell_w
            element = len(tips)
            if (name, age) not in measured:
                parts.append(
                    f'<rect x="{left + 1:.1f}" y="{top + 1:.1f}" '
                    f'width="{cell_w - 2:.1f}" height="{cell_h - 2:.1f}" fill="none" '
                    f'stroke="{GRIDLINE}" stroke-width="1" stroke-dasharray="2 3"/>'
                )
                continue
            rate = measured[(name, age)]
            red, green, blue = _ramp((rate - low) / (high - low))
            parts.append(
                f'<rect x="{left + 1:.1f}" y="{top + 1:.1f}" width="{cell_w - 2:.1f}" '
                f'height="{cell_h - 2:.1f}" fill="rgb({red:.0f},{green:.0f},{blue:.0f})"/>'
            )
            if cell_w > 36.0:
                ink = "#FFFFFF" if (rate - low) / (high - low) > 0.55 else INK
                parts.append(
                    f'<text x="{left + cell_w / 2:.1f}" y="{top + cell_h / 2 + 4:.1f}" '
                    f'font-size="10" fill="{ink}" text-anchor="middle" '
                    f'font-family="{mono_family}">{fmt_number(rate * 100.0)}</text>'
                )
            parts.append(
                f'<rect id="cell-{element}" class="cell hit" tabindex="0" role="img" '
                f'aria-label="{xml_escape(name)}, month {age}: '
                f'{fmt_number(rate * 100.0)}% still present" '
                f'x="{left + 1:.1f}" y="{top + 1:.1f}" width="{cell_w - 2:.1f}" '
                f'height="{cell_h - 2:.1f}" fill="transparent">'
                f'<title>{xml_escape(name)} month {age}: '
                f'{fmt_number(rate * 100.0)}%</title></rect>'
            )
            tips.append(
                tooltip_bubble(
                    left + cell_w / 2, top + cell_h / 2,
                    [f"{name} · month {age}", f"{fmt_number(rate * 100.0)}%"],
                    canvas_w=width, canvas_h=height, ink=INK, secondary=SECONDARY,
                    border=GRIDLINE, elem_id=f"celltip-{element}",
                )
            )

    for age_index, age in enumerate(shown_ages):
        parts.append(
            f'<text x="{plot_x + age_index * cell_w + cell_w / 2:.1f}" '
            f'y="{plot_y - 10:.1f}" font-size="11" fill="{SECONDARY}" '
            f'text-anchor="middle" font-family="{mono_family}">{age}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{plot_y - 30:.1f}" font-size="12" '
        f'fill="{SECONDARY}" text-anchor="middle">{xml_escape(period_label)}</text>'
    )
    parts.append(
        f'<text x="{plot_x - 10:.1f}" y="{plot_y - 30:.1f}" font-size="12" '
        f'fill="{SECONDARY}" text-anchor="end">{xml_escape(cohort_label)}</text>'
    )

    if plateau is not None and plateau in shown_ages:
        rule_x = plot_x + shown_ages.index(plateau) * cell_w
        parts.append(
            f'<line x1="{rule_x:.1f}" y1="{plot_y - 4:.1f}" x2="{rule_x:.1f}" '
            f'y2="{plot_y + plot_h + 4:.1f}" stroke="{accent}" stroke-width="2"/>'
        )

    key_y = plot_y + plot_h + 38.0
    parts.append(
        f'<text x="{plot_x:.1f}" y="{key_y + 4:.1f}" font-size="11" fill="{SECONDARY}" '
        f'font-family="{mono_family}">{fmt_number(low * 100.0)}%</text>'
    )
    for step in range(12):
        red, green, blue = _ramp(step / 11.0)
        parts.append(
            f'<rect x="{plot_x + 44 + step * 14:.1f}" y="{key_y - 8:.1f}" width="14" '
            f'height="11" fill="rgb({red:.0f},{green:.0f},{blue:.0f})"/>'
        )
    parts.append(
        f'<text x="{plot_x + 220:.1f}" y="{key_y + 4:.1f}" font-size="11" '
        f'fill="{SECONDARY}" font-family="{mono_family}">'
        f'{fmt_number(high * 100.0)}%</text>'
    )
    parts.append(
        f'<rect x="{plot_x + 276:.1f}" y="{key_y - 8:.1f}" width="14" height="11" '
        f'fill="none" stroke="{GRIDLINE}" stroke-width="1" stroke-dasharray="2 3"/>'
    )
    parts.append(
        f'<text x="{plot_x + 298:.1f}" y="{key_y + 4:.1f}" font-size="11" '
        f'fill="{SECONDARY}">{xml_escape(pending_label)}</text>'
    )

    parts.extend(tips)
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_cohort_retention(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[str] = None,
    title: str = "Churn settles at month 5, and one bad calendar month cuts across every cohort",
    subtitle: str = "Twelve monthly cohorts, each followed as far as today; the empty corner is not yet measured.",
    width: int = 940,
    height: int = 664,
    cohort: str = "cohort",
    period: str = "period",
    value: str = "users",
    value_is_rate: bool = False,
    include_period_zero: bool = False,
    plateau_at: float = 0.06,
    diagonal_gap: float = 0.08,
    cohort_label: str = "Cohort",
    period_label: str = "Months since signup",
    pending_label: str = "not yet measured",
    scale_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Write a retention triangle to disk and return the path.

    Parameters
    ----------
    data : list of dict or None
        One row per cohort and period. Defaults to :data:`DEMO_DATA`.
    out : str or None
        Destination path; ``None`` writes beside the script.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    cohort, period, value : str
        Row keys for the cohort name, the age in periods, and the
        measured quantity.
    value_is_rate : bool
        Whether `value` is already a share in 0 to 1.
    include_period_zero : bool
        Draw the period-zero column, which is 100% by construction.
    plateau_at : float
        The month-on-month loss, median over cohorts, below which the
        curve counts as flat.
    diagonal_gap : float
        How far below its neighbours a calendar diagonal must sit before
        it is called out.
    cohort_label, period_label : str
        Axis titles.
    pending_label : str
        What the unfilled cells are called in the key.
    scale_note, finding : str or None
        The line describing the colour scale, and the sentence naming the
        plateau and any bad calendar month; ``None`` composes each from
        the data.
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
    >>> p = make_cohort_retention()
    >>> p.exists()
    True
    """
    svg = build_svg(
        data, title=title, subtitle=subtitle, width=width, height=height,
        cohort=cohort, period=period, value=value, value_is_rate=value_is_rate,
        include_period_zero=include_period_zero, plateau_at=plateau_at,
        diagonal_gap=diagonal_gap, cohort_label=cohort_label,
        period_label=period_label, pending_label=pending_label,
        scale_note=scale_note, finding=finding, mode=mode,
        accessibility=accessibility, theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "cohort-retention")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "cohort-retention", build_svg,
               description="Draw a retention triangle: who stays, by when they arrived.")


if __name__ == "__main__":
    main()
