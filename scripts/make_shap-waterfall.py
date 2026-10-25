#!/usr/bin/env python3
"""
make_shap-waterfall — one prediction, taken apart.

A waterfall from the model's average output to this row's prediction, one
step per feature. Each step is that feature's contribution for *this*
row: how much having this value, rather than an unknown one, moved the
output.

Where the usual waterfall goes wrong
--------------------------------------
* **The baseline is unlabelled, so the bars look like they sum from
  zero.** They do not: they sum from the model's average output over a
  background sample, and without that number the whole chart is
  unanchored. It is drawn as a line, named, and the chrome gives it.
* **The units are log-odds and nobody says so.** For a classifier the
  contributions are almost always in log-odds, and a reader who takes
  "+0.42" for forty-two points of probability has misread the chart by
  a factor that depends on where they started. The unit is named, and
  with `link="logit"` the two ends are also given as probabilities, which
  is the number the reader came for.
* **The tail is lumped into "N other features" with no total.** That
  hides whether the remainder is a rounding error or half the answer.
  The lumped steps are summed and the sum is drawn as its own bar.
* **One row gets read as the model.** A waterfall explains a single
  prediction; the next row can have the opposite explanation. The
  caveat is drawn, not left to the reader.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import math
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

#: The model's average output over the background sample, in log-odds.
_BASE_VALUE = -1.86

DEMO_DATA: List[Dict[str, Any]] = [
    {"feature": "credit_utilisation", "shap": 0.94, "observed": "0.91"},
    {"feature": "months_at_address", "shap": 0.51, "observed": "4"},
    {"feature": "missed_payments_12m", "shap": 0.47, "observed": "2"},
    {"feature": "income_verified", "shap": -0.62, "observed": "yes"},
    {"feature": "loan_to_income", "shap": 0.33, "observed": "5.8"},
    {"feature": "age", "shap": -0.21, "observed": "44"},
    {"feature": "existing_customer", "shap": -0.18, "observed": "yes"},
    {"feature": "employment_years", "shap": -0.14, "observed": "11"},
    {"feature": "card_count", "shap": 0.07, "observed": "3"},
    {"feature": "region", "shap": 0.05, "observed": "North"},
    {"feature": "channel", "shap": -0.04, "observed": "branch"},
    {"feature": "device_type", "shap": 0.03, "observed": "mobile"},
    {"feature": "has_savings", "shap": -0.02, "observed": "no"},
    {"feature": "marital_status", "shap": 0.01, "observed": "married"},
]


def _logistic(value: float) -> float:
    """The logistic function, as a probability in 0 to 1."""
    if value >= 0.0:
        return 1.0 / (1.0 + math.exp(-value))
    exponent = math.exp(value)
    return exponent / (1.0 + exponent)


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "From 13% to 34%, and verified income is the biggest thing pulling the other way",
    subtitle: str = "One prediction taken apart: the model's average output, then what each feature did to it for this row.",
    width: int = 960,
    height: int = 668,
    feature: str = "feature",
    value: str = "shap",
    observed: str = "observed",
    base_value: float = _BASE_VALUE,
    top: int = 8,
    units: str = "log-odds",
    link: str = "logit",
    base_label: str = "average output",
    prediction_label: str = "this prediction",
    rest_label: str = "all other features",
    caveat: str = "this explains one row; the next applicant can have the opposite explanation",
    unit_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full waterfall SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        One row per feature, carrying its contribution and the value it
        took for this prediction. Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    feature, value, observed : str
        Row keys for the feature name, its contribution, and the value it
        took in the row being explained.
    base_value : float
        The model's average output over the background sample, in the
        same units as the contributions. The waterfall starts here, not
        at zero.
    top : int
        How many features to draw individually, largest contribution
        first. The rest are summed into one bar rather than dropped.
    units : str
        What the contributions are measured in. Named on the canvas
        because a reader who takes log-odds for probability has misread
        the chart.
    link : str
        ``"logit"`` also reports both ends as probabilities;
        ``"identity"`` leaves the numbers as they are.
    base_label, prediction_label, rest_label : str
        Captions for the starting line, the finishing line, and the bar
        that sums the features not drawn individually.
    caveat : str
        The standing limitation, drawn whatever the data says.
    unit_note, finding : str or None
        The line naming the units and the two ends, and the sentence
        summarising the move; ``None`` composes each from the data.
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
        raise ValueError("a waterfall needs at least one feature row")
    if link not in ("logit", "identity"):
        raise ValueError(f"link is 'logit' or 'identity', got {link!r}")

    ranked = sorted(rows, key=lambda row: abs(float(row[value])), reverse=True)
    drawn = ranked if top <= 0 else ranked[:top]
    lumped = [] if top <= 0 else ranked[top:]
    steps: List[Tuple[str, float, str]] = [
        (str(row[feature]), float(row[value]), str(row.get(observed, "")))
        for row in drawn
    ]
    if lumped:
        steps.append((
            f"{rest_label} ({len(lumped)})",
            sum(float(row[value]) for row in lumped),
            "",
        ))

    total = base_value + sum(amount for _, amount, _ in steps)
    positions: List[Tuple[float, float]] = []
    running = base_value
    for _, amount, _ in steps:
        positions.append((running, running + amount))
        running += amount

    mono_family = mono_stack_for_theme(theme)
    palette = load_palette(accessibility, theme=theme)
    pushes_up = palette.get("Orange", "#FF9500")
    pushes_down = palette.get("Blue", "#007AFF")

    edges = [base_value, total] + [edge for pair in positions for edge in pair]
    ticks = nice_ticks_range(min(edges), max(edges), 5)
    axis_low, axis_high = ticks[0], ticks[-1]

    plot_x = 232.0
    plot_y = 238.0
    plot_w = width - plot_x - 128.0
    plot_h = height - plot_y - 96.0
    row_h = plot_h / max(len(steps), 1)
    precision = min(
        (abs(amount) for _, amount, _ in steps if amount), default=0.0
    )

    def px(amount: float) -> float:
        return plot_x + (amount - axis_low) / (axis_high - axis_low) * plot_w

    unit_lines = (
        [unit_note] if unit_note is not None
        else [
            f"contributions in {units}, from {base_label} "
            f"{fmt_measured(base_value, precision)} to {fmt_measured(total, precision)}"
        ] + ([
            f"{fmt_number(_logistic(base_value) * 100.0)}% to "
            f"{fmt_number(_logistic(total) * 100.0)}% once passed through the logistic"
        ] if link == "logit" else [])
    )
    said_units = " · ".join(unit_lines)
    said_parts: List[str] = []
    if finding is not None:
        said_parts.append(finding)
    else:
        strongest = steps[0]
        share = abs(strongest[1]) / sum(abs(a) for _, a, _ in steps) if steps else 0.0
        said_parts.append(
            f"{strongest[0]} is worth {fmt_measured(strongest[1], precision)} on its own, "
            f"{fmt_number(share * 100.0)}% of all the movement here."
        )
        if lumped:
            rest = sum(float(row[value]) for row in lumped)
            said_parts.append(
                f"The {len(lumped)} features not drawn separately come to "
                f"{fmt_measured(rest, precision)} between them."
            )
    said_lines: List[str] = []
    for sentence in said_parts:
        said_lines.extend(wrap_no_orphan(sentence, 102))

    parts: List[str] = []
    parts.append(
        svg_open(width, height, "shapw-title", "shapw-desc",
                 font_family=chrome_stack_for_theme(theme))
    )
    parts.append(f'<title id="shapw-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="shapw-desc">A waterfall of {len(steps)} steps explaining one '
        f'prediction, from {xml_escape(base_label)} {fmt_measured(base_value, precision)} '
        f'to {fmt_measured(total, precision)}. {xml_escape(said_units)}. '
        f'{xml_escape(" ".join(said_parts))} {xml_escape(caveat)}.</desc>'
    )
    parts.append(
        "<style>"
        ".step{cursor:default;}"
        ".step:hover,.step:focus{outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + foreground_tip_css(len(steps), mark_prefix="step", tip_prefix="steptip")
        + "@media (prefers-reduced-motion:reduce){.tip{transition:none}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    title_size = fit_font_size(title, width - 96.0, 22.0, min_px=15.0)
    parts.append(
        f'<text x="40" y="46" font-size="{title_size:.1f}" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    for line_index, line in enumerate(wrap_no_orphan(subtitle, 108)[:2]):
        parts.append(
            f'<text x="40" y="{72 + line_index * 20:.1f}" font-size="14" '
            f'fill="{SECONDARY}">{xml_escape(line)}</text>'
        )
    # One clause per line: poured into a width this note broke at "once
    # passed through / the logistic".
    unit_drawn: List[str] = []
    for clause in unit_lines:
        unit_drawn.extend(wrap_no_orphan(clause, 102))
    for line_index, line in enumerate(unit_drawn[:2]):
        parts.append(
            f'<text x="40" y="{124 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(line)}</text>'
        )
    for line_index, line in enumerate(said_lines[:2]):
        parts.append(
            f'<text x="40" y="{162 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(line)}</text>'
        )
    parts.append(
        f'<text x="40" y="{height - 26:.1f}" font-size="11" fill="{SECONDARY}">'
        f'{xml_escape(caveat)}</text>'
    )

    for tick in ticks:
        parts.append(
            f'<line x1="{px(tick):.1f}" y1="{plot_y - 24:.1f}" x2="{px(tick):.1f}" '
            f'y2="{plot_y + plot_h:.1f}" stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{px(tick):.1f}" y="{plot_y + plot_h + 18:.1f}" font-size="11" '
            f'fill="{SECONDARY}" text-anchor="middle" font-family="{mono_family}">'
            f'{fmt_number(tick)}</text>'
        )

    for amount, label, dash in (
        (base_value, base_label, ' stroke-dasharray="5 4"'),
        (total, prediction_label, ""),
    ):
        parts.append(
            f'<line x1="{px(amount):.1f}" y1="{plot_y - 24:.1f}" x2="{px(amount):.1f}" '
            f'y2="{plot_y + plot_h + 4:.1f}" stroke="{INK}" stroke-width="1.6"{dash}/>'
        )
        parts.append(
            f'<text x="{px(amount):.1f}" y="{plot_y - 32:.1f}" font-size="11" '
            f'fill="{INK}" text-anchor="middle">{xml_escape(label)} '
            f'{fmt_measured(amount, precision)}</text>'
        )

    tips: List[str] = []
    for index, (name, amount, shown) in enumerate(steps):
        start, finish = positions[index]
        middle = plot_y + index * row_h + row_h / 2
        colour = pushes_up if amount >= 0.0 else pushes_down
        left, right = min(px(start), px(finish)), max(px(start), px(finish))
        parts.append(
            f'<rect x="{left:.1f}" y="{middle - row_h * 0.28:.1f}" '
            f'width="{max(right - left, 1.5):.1f}" height="{row_h * 0.56:.1f}" '
            f'fill="{colour}"/>'
        )
        if index + 1 < len(steps):
            parts.append(
                f'<line x1="{px(finish):.1f}" y1="{middle + row_h * 0.28:.1f}" '
                f'x2="{px(finish):.1f}" y2="{middle + row_h:.1f}" stroke="{SECONDARY}" '
                f'stroke-width="1" opacity="0.6"/>'
            )
        caption = f"{name} = {shown}" if shown else name
        parts.append(
            f'<text x="{plot_x - 12:.1f}" y="{middle + 4:.1f}" font-size="12" '
            f'fill="{INK}" text-anchor="end" font-family="{mono_family}">'
            f'{xml_escape(caption)}</text>'
        )
        parts.append(
            f'<text x="{right + 8 if amount >= 0 else left - 8:.1f}" y="{middle + 4:.1f}" '
            f'font-size="11" fill="{SECONDARY}" font-family="{mono_family}" '
            f'text-anchor="{"start" if amount >= 0 else "end"}">'
            f'{"+" if amount > 0 else ""}{fmt_measured(amount, precision)}</text>'
        )
        parts.append(
            f'<rect id="step-{index}" class="step hit" tabindex="0" role="img" '
            f'aria-label="{xml_escape(caption)}: {"+" if amount > 0 else ""}'
            f'{fmt_measured(amount, precision)} {xml_escape(units)}, taking the output to '
            f'{fmt_measured(finish, precision)}" x="{plot_x:.1f}" '
            f'y="{middle - row_h / 2:.1f}" width="{plot_w:.1f}" height="{row_h:.1f}" '
            f'fill="transparent"><title>{xml_escape(caption)}: '
            f'{"+" if amount > 0 else ""}{fmt_measured(amount, precision)}</title></rect>'
        )
        tips.append(
            tooltip_bubble(
                (left + right) / 2, middle,
                [caption,
                 f'{"+" if amount > 0 else ""}{fmt_measured(amount, precision)} {units}',
                 f"output now {fmt_measured(finish, precision)}"],
                canvas_w=width, canvas_h=height, ink=INK, secondary=SECONDARY,
                border=GRIDLINE, elem_id=f"steptip-{index}",
            )
        )

    parts.extend(tips)
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_shap_waterfall(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[str] = None,
    title: str = "From 13% to 34%, and verified income is the biggest thing pulling the other way",
    subtitle: str = "One prediction taken apart: the model's average output, then what each feature did to it for this row.",
    width: int = 960,
    height: int = 668,
    feature: str = "feature",
    value: str = "shap",
    observed: str = "observed",
    base_value: float = _BASE_VALUE,
    top: int = 8,
    units: str = "log-odds",
    link: str = "logit",
    base_label: str = "average output",
    prediction_label: str = "this prediction",
    rest_label: str = "all other features",
    caveat: str = "this explains one row; the next applicant can have the opposite explanation",
    unit_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Write a SHAP waterfall to disk and return the path.

    Parameters
    ----------
    data : list of dict or None
        One row per feature. Defaults to :data:`DEMO_DATA`.
    out : str or None
        Destination path; ``None`` writes beside the script.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    feature, value, observed : str
        Row keys for the feature name, its contribution, and the value it
        took in the row being explained.
    base_value : float
        The model's average output over the background sample.
    top : int
        How many features to draw individually; the rest are summed.
    units : str
        What the contributions are measured in.
    link : str
        ``"logit"`` also reports both ends as probabilities.
    base_label, prediction_label, rest_label : str
        Captions for the two reference lines and the summed bar.
    caveat : str
        The standing limitation, drawn whatever the data says.
    unit_note, finding : str or None
        The line naming the units and the two ends, and the sentence
        summarising the move; ``None`` composes each from the data.
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
    >>> p = make_shap_waterfall()
    >>> p.exists()
    True
    """
    svg = build_svg(
        data, title=title, subtitle=subtitle, width=width, height=height,
        feature=feature, value=value, observed=observed, base_value=base_value,
        top=top, units=units, link=link, base_label=base_label,
        prediction_label=prediction_label, rest_label=rest_label, caveat=caveat,
        unit_note=unit_note, finding=finding, mode=mode,
        accessibility=accessibility, theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "shap-waterfall")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "shap-waterfall", build_svg,
               description="Take one prediction apart, feature by feature.")


if __name__ == "__main__":
    main()
