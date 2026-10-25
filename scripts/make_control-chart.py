#!/usr/bin/env python3
"""
make_control-chart — the process behaving, until it stops.

An individuals chart: one point per unit produced, a centre line, and
control limits computed from how much the process moves between
consecutive units. Points and runs that the rules call signals are
marked, and the rule that fired is named.

Where the usual control chart goes wrong
----------------------------------------
* **The limits are computed from the standard deviation of all the
  points.** That is the error that empties the chart of meaning: a
  process that shifted halfway through has a large overall standard
  deviation *because* it shifted, so the limits widen until they swallow
  the very shift they exist to catch. The limits here come from the mean
  moving range -- the average jump between consecutive units, divided by
  1.128 -- which measures variation *within* the process rather than
  across the shift. On this figure's own demo the difference is not
  academic: with sigma from the moving range a batch crosses a limit and
  two pairs sit past two sigma; with sigma from the standard deviation of
  every point, neither rule fires. ``limit_from="sd"`` draws that version
  for comparison, and the chrome says which one it drew.
* **Control limits get read as specification limits.** They are not the
  same claim and not even the same kind of claim: control limits say what
  this process does, specification limits say what the customer accepts.
  A process can sit inside its control limits and fail every unit. The
  chrome says which it is drawing, and spec limits, when given, are drawn
  in a different ink and labelled.
* **Only points outside the limits are flagged.** A process that drifts
  without ever crossing a limit is the common case, and the run rules
  were written for exactly that. Four of them are applied here, each
  named in the finding when it fires.

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
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

# d2 for a moving range of two consecutive observations: the factor that
# turns a mean moving range into an estimate of the process standard
# deviation. Tabulated in every statistical process control text.
_D2_FOR_PAIRS = 1.128

_BATCHES = 60
_SHIFT_AT = 43

# What the customer accepts for this fill, in grams. Carried by the demo
# rather than defaulted into every caller's chart, because specification
# limits belong to a contract and not to a figure: 497 on somebody else's
# data would be a number the figure invented. They are drawn when the
# caller brings no data of their own, which is the one case where the
# figure knows what process it is looking at -- and the default render is
# then the one that shows the distinction the chart keeps being asked
# about, control limits inside spec limits.
_DEMO_SPEC = (497.0, 504.0)


def _series(seed: int = 150) -> List[Dict[str, Any]]:
    """Sixty batches of fill weight, with the line drifting from batch 43.

    The drift is small on purpose -- about 1.4 estimated standard
    deviations -- because that is the case the chart exists for and the
    case the common mistake destroys. Measured on this series: sigma from
    the mean moving range is 0.83, sigma from the standard deviation of
    every point is 0.98, nineteen percent larger because the shift itself
    inflates it. That nineteen percent is the difference between a chart
    that flags batch 45 for crossing a limit and two pairs past two
    sigma, and a chart on which **neither sigma rule fires at all**. The
    run rule survives either way: it only looks at which side of the
    centre a point falls on, which is why it is the rule that catches
    this shift first, at batch 43.
    """
    rng = random.Random(seed)
    rows: List[Dict[str, Any]] = []
    for index in range(_BATCHES):
        drift = 0.0 if index + 1 < _SHIFT_AT else 1.15
        weight = 500.0 + drift + rng.gauss(0.0, 0.78)
        rows.append({"batch": index + 1, "weight": round(weight, 2)})
    return rows


DEMO_DATA: List[Dict[str, Any]] = _series()


def _mean(values: List[float]) -> float:
    """Arithmetic mean; 0.0 for an empty list."""
    return sum(values) / len(values) if values else 0.0


def _sigma_from_moving_range(values: List[float]) -> float:
    """The process standard deviation, estimated from consecutive jumps.

    This is the estimate a control chart is supposed to use. It asks how
    far the process moves from one unit to the next, which a sustained
    shift barely affects: two units on either side of a shift are still
    close to each other, and only the single pair that straddles it is
    large. The standard deviation of all the points, by contrast, grows
    with the size of the shift, which is why that version of the chart
    goes blind exactly when something has happened.
    """
    if len(values) < 2:
        return 0.0
    moving = [abs(values[index] - values[index - 1]) for index in range(1, len(values))]
    return _mean(moving) / _D2_FOR_PAIRS


def _sigma_from_sd(values: List[float]) -> float:
    """The sample standard deviation of every point, for comparison."""
    if len(values) < 2:
        return 0.0
    mean = _mean(values)
    return (sum((v - mean) ** 2 for v in values) / (len(values) - 1)) ** 0.5


def _beyond_limits(
    values: List[float], centre: float, sigma: float, multiplier: float
) -> List[int]:
    """Rule 1: a single point past the control limits."""
    span = multiplier * sigma
    return [i for i, v in enumerate(values) if abs(v - centre) > span]


def _long_run(values: List[float], centre: float, length: int) -> List[int]:
    """Rule 2: `length` points in a row on the same side of the centre."""
    flagged: List[int] = []
    run_start, run_sign = 0, 0
    for index, value in enumerate(values):
        sign = 1 if value > centre else (-1 if value < centre else 0)
        if sign == 0 or sign != run_sign:
            run_sign, run_start = sign, index
        if sign != 0 and index - run_start + 1 >= length:
            flagged.extend(range(run_start, index + 1))
    return sorted(set(flagged))


def _trend(values: List[float], length: int) -> List[int]:
    """Rule 3: `length` points in a row all rising or all falling."""
    flagged: List[int] = []
    rising = falling = 1
    for index in range(1, len(values)):
        rising = rising + 1 if values[index] > values[index - 1] else 1
        falling = falling + 1 if values[index] < values[index - 1] else 1
        for run in (rising, falling):
            if run >= length:
                flagged.extend(range(index - run + 1, index + 1))
    return sorted(set(flagged))


def _two_of_three(values: List[float], centre: float, sigma: float) -> List[int]:
    """Rule 4: two of three consecutive points past two sigma, same side."""
    flagged: List[int] = []
    span = 2.0 * sigma
    for index in range(2, len(values)):
        window = list(range(index - 2, index + 1))
        for sign in (1, -1):
            far = [i for i in window if sign * (values[i] - centre) > span]
            if len(far) >= 2:
                flagged.extend(far)
    return sorted(set(flagged))


_RULE_NAMES = {
    "beyond": "a point past the limits",
    "run": "a run on one side of the centre",
    "trend": "a steady climb or fall",
    "two-of-three": "two of three points past two sigma",
}


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "The run rule saw the shift at batch 43; a crossing came only at 45",
    subtitle: str = "Sixty batches of fill weight. From the overall standard deviation instead, neither sigma rule fires.",
    width: int = 900,
    height: int = 580,
    x: str = "batch",
    y: str = "weight",
    sigma_multiplier: float = 3.0,
    limit_from: str = "moving-range",
    rules: Optional[List[str]] = None,
    run_length: int = 9,
    trend_length: int = 6,
    centre: Optional[float] = None,
    spec_low: Optional[float] = None,
    spec_high: Optional[float] = None,
    zones: bool = True,
    centre_label: str = "centre",
    spec_caution: str = "control limits, not specification limits",
    upper_label: str = "upper control limit",
    lower_label: str = "lower control limit",
    spec_low_label: str = "spec low",
    spec_high_label: str = "spec high",
    x_label: str = "Batch",
    y_label: str = "Fill weight (g)",
    limit_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full control chart SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        One row per unit, ordered by `x` and measured by `y`. Defaults to
        :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    x, y : str
        Row keys for the sequence column and the measured column.
    sigma_multiplier : float
        How many estimated standard deviations the control limits sit at.
    limit_from : str
        ``"moving-range"`` estimates the process standard deviation from
        consecutive jumps, which is what a control chart is for;
        ``"sd"`` uses the standard deviation of every point, which a
        sustained shift inflates.
    rules : list of str or None
        Which run rules to apply: ``beyond``, ``run``, ``trend``,
        ``two-of-three``. ``None`` applies all four.
    run_length : int
        Points in a row on one side of the centre that count as a run.
    trend_length : int
        Points in a row rising or falling that count as a trend.
    centre : float or None
        The centre line; ``None`` uses the mean of the data.
    spec_low, spec_high : float or None
        Specification limits, drawn apart from the control limits
        because they are a different claim. ``None`` draws none, except
        on the demo data, which carries the spec its own process has.
    spec_low_label, spec_high_label : str
        Captions on the two specification limits.
    zones : bool
        Shade the one and two sigma zones.
    spec_caution : str
        The standing caution under the limit line, drawn whether or not
        specification limits are given, because the confusion it answers
        does not wait for them.
    centre_label, upper_label, lower_label : str
        Captions on the centre line and on the two control limits; each
        is drawn with its value beside it.
    x_label, y_label : str
        Axis titles.
    limit_note, finding : str or None
        The line saying where the limits came from, and the sentence
        naming what fired; ``None`` composes each from the data.
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
        """Sort key that works for a batch number and for "2026-01" alike."""
        raw = row[x]
        try:
            return (0, float(raw), "")
        except (TypeError, ValueError):
            return (1, 0.0, str(raw))

    if data is None and spec_low is None and spec_high is None:
        spec_low, spec_high = _DEMO_SPEC
    rows = sorted(data if data else DEMO_DATA, key=position)
    values = [float(row[y]) for row in rows]
    labels = [str(row[x]) for row in rows]
    n = len(values)
    if n < 2:
        raise ValueError(
            "a control chart needs at least two units to measure movement between them"
        )

    wanted = set(rules) if rules else set(_RULE_NAMES)
    unknown = sorted(wanted - set(_RULE_NAMES))
    if unknown:
        raise ValueError(f"unknown rule(s) {unknown}; the rules are {sorted(_RULE_NAMES)}")
    if limit_from not in ("moving-range", "sd"):
        raise ValueError(f"limit_from is 'moving-range' or 'sd', got {limit_from!r}")

    middle = centre if centre is not None else _mean(values)
    sigma = (
        _sigma_from_moving_range(values) if limit_from == "moving-range" else _sigma_from_sd(values)
    )
    upper = middle + sigma_multiplier * sigma
    lower = middle - sigma_multiplier * sigma

    fired: Dict[str, List[int]] = {}
    if "beyond" in wanted:
        hits = _beyond_limits(values, middle, sigma, sigma_multiplier)
        if hits:
            fired["beyond"] = hits
    if "run" in wanted:
        hits = _long_run(values, middle, run_length)
        if hits:
            fired["run"] = hits
    if "trend" in wanted:
        hits = _trend(values, trend_length)
        if hits:
            fired["trend"] = hits
    if "two-of-three" in wanted:
        hits = _two_of_three(values, middle, sigma)
        if hits:
            fired["two-of-three"] = hits
    flagged = sorted({index for hits in fired.values() for index in hits})

    mono_family = mono_stack_for_theme(theme)
    palette = load_palette(accessibility, theme=theme)
    ordinary = palette.get("Blue", "#007AFF")
    signal = palette.get("Orange", "#FF9500")
    spec_ink = palette.get("Purple", palette.get("Teal", "#5856D6"))

    span_values = values + [upper, lower]
    if spec_low is not None:
        span_values.append(spec_low)
    if spec_high is not None:
        span_values.append(spec_high)
    ticks = nice_ticks_range(min(span_values), max(span_values), 5)
    axis_low, axis_high = ticks[0], ticks[-1]

    plot_x = 100.0
    plot_y = 202.0
    plot_w = width - plot_x - 164.0
    plot_h = height - plot_y - 92.0

    def px(index: int) -> float:
        return plot_x + index / max(n - 1, 1) * plot_w

    def py(value: float) -> float:
        return plot_y + plot_h - (value - axis_low) / (axis_high - axis_low) * plot_h

    def measured(value: float) -> str:
        """`value` at the precision sigma makes meaningful."""
        return fmt_measured(value, sigma)

    limit_lines = (
        [limit_note]
        if limit_note is not None
        else [
            f"control limits at {measured(middle)} ± {fmt_number(sigma_multiplier)} × "
            f"{measured(sigma)}, sigma from the "
            + (
                "mean moving range"
                if limit_from == "moving-range"
                else "standard deviation of all points"
            ),
            spec_caution,
        ]
    )
    said_limits = " · ".join(limit_lines)
    said_parts: List[str] = []
    if finding is not None:
        said_parts.append(finding)
    elif fired:
        named = "; ".join(
            f"{_RULE_NAMES[rule]} from {labels[min(hits)]}" for rule, hits in fired.items()
        )
        said_parts.append(
            f"{len(fired)} of {len(wanted)} rules fired over {len(flagged)} units: {named}."
        )
    else:
        said_parts.append(
            f"No rule fired over {n} units: nothing here is distinguishable from the "
            f"process behaving as it always has."
        )
    said_lines: List[str] = []
    for sentence in said_parts:
        said_lines.extend(wrap_no_orphan(sentence, 98))

    parts: List[str] = []
    parts.append(
        svg_open(width, height, "spc-title", "spc-desc", font_family=chrome_stack_for_theme(theme))
    )
    parts.append(f'<title id="spc-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="spc-desc">An individuals control chart of {n} units from '
        f"{xml_escape(labels[0])} to {xml_escape(labels[-1])}, with a centre line at "
        f"{measured(middle)} and control limits at {measured(lower)} and "
        f"{measured(upper)}. {xml_escape(said_limits)}. "
        f"{xml_escape(' '.join(said_parts))}</desc>"
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
        f'<text x="{plot_x - 68:.1f}" y="46" font-size="22" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    for line_index, line in enumerate(wrap_no_orphan(subtitle, 104)[:2]):
        parts.append(
            f'<text x="{plot_x - 68:.1f}" y="{72 + line_index * 20:.1f}" font-size="14" '
            f'fill="{SECONDARY}">{xml_escape(line)}</text>'
        )
    # One clause per line, by construction: the wrapper used to cut this
    # note at "control limits, not / specification limits", which is both
    # a worse read and a fragment for a translator.
    limit_drawn: List[str] = []
    for clause in limit_lines:
        limit_drawn.extend(wrap_no_orphan(clause, 98))
    for line_index, line in enumerate(limit_drawn[:2]):
        parts.append(
            f'<text x="{plot_x - 68:.1f}" y="{124 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(line)}</text>'
        )
    for line_index, line in enumerate(said_lines[:2]):
        parts.append(
            f'<text x="{plot_x - 68:.1f}" y="{162 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(line)}</text>'
        )

    if zones and sigma > 0.0:
        for multiple, opacity in ((1.0, 0.10), (2.0, 0.06)):
            top = py(middle + multiple * sigma)
            bottom = py(middle - multiple * sigma)
            parts.append(
                f'<rect x="{plot_x:.1f}" y="{top:.1f}" width="{plot_w:.1f}" '
                f'height="{bottom - top:.1f}" fill="{ordinary}" opacity="{opacity}"/>'
            )

    for tick in ticks:
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{py(tick) + 4:.1f}" font-size="11" '
            f'fill="{SECONDARY}" text-anchor="end" font-family="{mono_family}">'
            f"{fmt_number(tick)}</text>"
        )

    for value, label, dash in (
        (middle, f"{centre_label} {measured(middle)}", ""),
        (upper, f"{upper_label} {measured(upper)}", ' stroke-dasharray="6 4"'),
        (lower, f"{lower_label} {measured(lower)}", ' stroke-dasharray="6 4"'),
    ):
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{py(value):.1f}" x2="{plot_x + plot_w:.1f}" '
            f'y2="{py(value):.1f}" stroke="{INK}" stroke-width="1"{dash} opacity="0.7"/>'
        )
        parts.append(
            f'<text x="{plot_x + plot_w + 6:.1f}" y="{py(value) + 4:.1f}" font-size="10" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(label)}</text>'
        )

    for spec, spec_label in ((spec_low, spec_low_label), (spec_high, spec_high_label)):
        if spec is None:
            continue
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{py(spec):.1f}" x2="{plot_x + plot_w:.1f}" '
            f'y2="{py(spec):.1f}" stroke="{spec_ink}" stroke-width="1.6" '
            f'stroke-dasharray="2 4"/>'
        )
        parts.append(
            f'<text x="{plot_x + plot_w + 6:.1f}" y="{py(spec) + 4:.1f}" font-size="10" '
            f'fill="{spec_ink}" font-family="{mono_family}">{xml_escape(spec_label)} '
            f"{measured(spec)}</text>"
        )

    path = " ".join(
        f"{'M' if index == 0 else 'L'}{px(index):.1f},{py(value):.1f}"
        for index, value in enumerate(values)
    )
    parts.append(
        f'<path d="{path}" fill="none" stroke="{ordinary}" stroke-width="1.6" '
        f'stroke-linejoin="round" opacity="0.8"/>'
    )

    flagged_set = set(flagged)
    tips: List[str] = []
    for index, value in enumerate(values):
        hit = index in flagged_set
        colour = signal if hit else ordinary
        parts.append(
            f'<circle cx="{px(index):.1f}" cy="{py(value):.1f}" r="{4.0 if hit else 2.6:.1f}" '
            f'fill="{colour}"/>'
        )
        why = sorted(rule for rule, hits in fired.items() if index in hits)
        caption = [f"{labels[index]}", measured(value)]
        caption += [_RULE_NAMES[rule] for rule in why]
        parts.append(
            f'<rect id="pt-{index}" class="pt hit" tabindex="0" role="img" '
            f'aria-label="{xml_escape(x_label)} {xml_escape(labels[index])}: '
            f"{measured(value)}"
            + ("".join(f", {_RULE_NAMES[rule]}" for rule in why))
            + f'" x="{px(index) - 5:.1f}" y="{plot_y:.1f}" width="10" '
            f'height="{plot_h:.1f}" fill="transparent">'
            f"<title>{xml_escape(labels[index])}: {measured(value)}</title></rect>"
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
                elem_id=f"pttip-{index}",
            )
        )

    step = max(1, n // 12)
    for index in range(0, n, step):
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
        f'<text x="{plot_x - 68:.1f}" y="{plot_y - 12:.1f}" font-size="12" '
        f'fill="{SECONDARY}">{xml_escape(y_label)}</text>'
    )

    parts.extend(tips)
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_control_chart(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[str] = None,
    title: str = "The run rule saw the shift at batch 43; a crossing came only at 45",
    subtitle: str = "Sixty batches of fill weight. From the overall standard deviation instead, neither sigma rule fires.",
    width: int = 900,
    height: int = 580,
    x: str = "batch",
    y: str = "weight",
    sigma_multiplier: float = 3.0,
    limit_from: str = "moving-range",
    rules: Optional[List[str]] = None,
    run_length: int = 9,
    trend_length: int = 6,
    centre: Optional[float] = None,
    spec_low: Optional[float] = None,
    spec_high: Optional[float] = None,
    zones: bool = True,
    centre_label: str = "centre",
    spec_caution: str = "control limits, not specification limits",
    upper_label: str = "upper control limit",
    lower_label: str = "lower control limit",
    spec_low_label: str = "spec low",
    spec_high_label: str = "spec high",
    x_label: str = "Batch",
    y_label: str = "Fill weight (g)",
    limit_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Write a control chart to disk and return the path.

    Parameters
    ----------
    data : list of dict or None
        One row per unit. Defaults to :data:`DEMO_DATA`.
    out : str or None
        Destination path; ``None`` writes beside the script.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    x, y : str
        Row keys for the sequence column and the measured column.
    sigma_multiplier : float
        How many estimated standard deviations the control limits sit at.
    limit_from : str
        ``"moving-range"`` or ``"sd"``.
    rules : list of str or None
        Which run rules to apply; ``None`` applies all four.
    run_length, trend_length : int
        Lengths that count as a run and as a trend.
    centre : float or None
        The centre line; ``None`` uses the mean.
    spec_low, spec_high : float or None
        Specification limits, drawn apart from the control limits.
    spec_low_label, spec_high_label : str
        Captions on the two specification limits.
    zones : bool
        Shade the one and two sigma zones.
    centre_label, upper_label, lower_label : str
        Captions on the centre line and on the two control limits; each
        is drawn with its value beside it.
    x_label, y_label : str
        Axis titles.
    limit_note, finding : str or None
        The line saying where the limits came from, and the sentence
        naming what fired; ``None`` composes each from the data.
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
    >>> p = make_control_chart()
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
        sigma_multiplier=sigma_multiplier,
        limit_from=limit_from,
        rules=rules,
        run_length=run_length,
        trend_length=trend_length,
        centre=centre,
        spec_low=spec_low,
        spec_high=spec_high,
        spec_low_label=spec_low_label,
        spec_high_label=spec_high_label,
        zones=zones,
        spec_caution=spec_caution,
        centre_label=centre_label,
        upper_label=upper_label,
        lower_label=lower_label,
        x_label=x_label,
        y_label=y_label,
        limit_note=limit_note,
        finding=finding,
        mode=mode,
        accessibility=accessibility,
        theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "control-chart")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(
        __file__,
        "control-chart",
        build_svg,
        description="Draw an individuals control chart with run rules applied.",
    )


if __name__ == "__main__":
    main()
