#!/usr/bin/env python3
"""
make_permutation-importance — what the model loses when a column is shuffled.

One bar per feature: how much worse the model scores when that column's
values are shuffled and everything else is left alone. Shuffling breaks
the link between the column and the target without retraining anything,
so the drop is a direct measure of how much the fitted model leans on it.

Where the usual importance plot goes wrong
--------------------------------------------
* **One shuffle, one bar, no spread.** A permutation is a random draw,
  and a single pass gives a number that moves when you run it again.
  This takes the repeats as input, draws the mean with its spread, and
  says how many repeats it had. A feature whose interval straddles zero
  is drawn hollow and named: it is not distinguishable from a column of
  noise, which is a finding, not a small bar.
* **Negative importance is clipped to zero.** Shuffling a column can
  make the model score *better*, and that is information -- the column
  was being used and should not have been. Clipping it to zero deletes
  exactly the features worth removing. Negative bars are drawn on their
  own side of the baseline.
* **It never says which data the score was measured on.** Permutation
  importance on the training set measures what the model *can* lean on;
  on held-out data it measures what actually generalises. The two
  routinely disagree, and the chrome names the one in front of you.
* **Correlated columns split their importance and both look useless.**
  Shuffling one leaves the model the other, so neither shows a drop.
  Nothing in the numbers reveals it, so the figure says so in a standing
  caveat rather than letting the picture imply independence it cannot
  check.

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
from _textfit import fit_font_size  # noqa: E402
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

_REPEATS = 10

# Mean drop in held-out AUC when each column is shuffled, and how much
# that drop itself varies from one shuffle to the next.
_TRUE_EFFECT = [
    ("contract_type", 0.0840, 0.0062),
    ("tenure_months", 0.0415, 0.0051),
    ("monthly_charge", 0.0397, 0.0048),
    ("support_tickets", 0.0268, 0.0040),
    ("payment_method", 0.0122, 0.0031),
    ("has_fibre", 0.0074, 0.0028),
    ("paperless_billing", 0.0012, 0.0030),
    ("signup_channel", 0.0006, 0.0028),
    ("customer_id_hash", -0.0042, 0.0022),
]


def _repeats(seed: int = 1) -> List[Dict[str, Any]]:
    """Ten shuffles per column of a churn model, scored on held-out data.

    Three of the nine columns are here to be *unconvincing*, and that is
    the point of taking repeats as input rather than a single number:

    ``paperless_billing`` and ``signup_channel`` have small positive
    means that any one shuffle could produce from noise. With the spread
    drawn, their intervals cross zero and the figure says so.

    ``customer_id_hash`` has a slightly negative mean -- shuffling it
    makes the model marginally better. A plot that clips at zero shows a
    bar of length nothing and loses the only column the reader should
    act on immediately.

    ``tenure_months`` and ``monthly_charge`` sit close together on
    purpose: in a real churn model those two move together, and this
    figure cannot see that. Which is why it says so instead.
    """
    rng = random.Random(seed)
    rows: List[Dict[str, Any]] = []
    for feature, effect, spread in _TRUE_EFFECT:
        for repeat in range(_REPEATS):
            rows.append(
                {
                    "feature": feature,
                    "repeat": repeat + 1,
                    "drop": round(rng.gauss(effect, spread), 5),
                }
            )
    return rows


DEMO_DATA: List[Dict[str, Any]] = _repeats()


def _mean(values: List[float]) -> float:
    """Arithmetic mean; 0.0 for an empty list."""
    return sum(values) / len(values) if values else 0.0


def _standard_error(values: List[float]) -> float:
    """Standard error of the mean; 0.0 for fewer than two values."""
    if len(values) < 2:
        return 0.0
    mean = _mean(values)
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return (variance / len(values)) ** 0.5


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Two columns cannot be told from noise, and one is worse than noise",
    subtitle: str = "Drop in held-out AUC when each column is shuffled, ten shuffles per column, mean with two standard errors.",
    width: int = 940,
    height: int = 620,
    feature: str = "feature",
    value: str = "drop",
    error_multiple: float = 2.0,
    top: int = 0,
    set_label: str = "held-out data",
    score_label: str = "Drop in AUC when shuffled",
    caveat: str = "two columns that move together each keep the other's score up, and no permutation can see it",
    measure_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full permutation-importance SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        One row per feature and repeat, carrying the score drop for that
        shuffle. Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    feature, value : str
        Row keys for the column name and the score drop.
    error_multiple : float
        How many standard errors the interval spans either side of the
        mean. Two is the usual reading of "not distinguishable from".
    top : int
        Draw only the `top` features by mean drop; 0 draws all of them.
    set_label : str
        Which data the score was measured on. Named on the canvas
        because importance on the training set and on held-out data are
        different claims that routinely disagree.
    score_label : str
        Axis title.
    caveat : str
        The standing limitation, drawn whatever the data says.
    measure_note, finding : str or None
        The line describing the measurement, and the sentence naming
        what the intervals show; ``None`` composes each from the data.
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
        raise ValueError("a permutation-importance chart needs at least one row")

    draws: Dict[str, List[float]] = {}
    for row in rows:
        draws.setdefault(str(row[feature]), []).append(float(row[value]))
    summary: List[Tuple[str, float, float, int]] = [
        (name, _mean(values), _standard_error(values), len(values))
        for name, values in draws.items()
    ]
    summary.sort(key=lambda item: item[1], reverse=True)
    if top > 0:
        summary = summary[:top]
    repeats = min(count for _, _, _, count in summary)

    uncertain = [
        name
        for name, mean, error, _ in summary
        if error > 0.0 and abs(mean) <= error_multiple * error
    ]
    harmful = [name for name, mean, _, _ in summary if mean < 0.0]

    mono_family = mono_stack_for_theme(theme)
    palette = load_palette(accessibility, theme=theme)
    solid = palette.get("Blue", "#007AFF")
    adverse = palette.get("Orange", "#FF9500")

    # The precision the numbers are quoted at, read off the tightest
    # interval on the chart: fmt_number would print "0.04 to 0.04" for an
    # interval that runs 0.0414 to 0.0431 and lose the whole point.
    errors = [error_multiple * error for _, _, error, _ in summary if error > 0.0]
    precision = min(errors) if errors else 0.0

    reach = [mean + error_multiple * error for _, mean, error, _ in summary]
    reach += [mean - error_multiple * error for _, mean, error, _ in summary] + [0.0]
    ticks = nice_ticks_range(min(reach), max(reach), 5)
    axis_low, axis_high = ticks[0], ticks[-1]

    plot_x = 206.0
    plot_y = 206.0
    plot_w = width - plot_x - 56.0
    plot_h = height - plot_y - 92.0
    row_h = plot_h / max(len(summary), 1)

    def px(amount: float) -> float:
        return plot_x + (amount - axis_low) / (axis_high - axis_low) * plot_w

    said_measure = (
        measure_note
        if measure_note is not None
        else (
            f"mean of {repeats} shuffles per column on {set_label}, bars span "
            f"±{fmt_number(error_multiple)} standard errors"
        )
    )
    said_parts: List[str] = []
    if finding is not None:
        said_parts.append(finding)
    else:
        if uncertain:
            said_parts.append(
                f"{len(uncertain)} of {len(summary)} columns have an interval that "
                f"crosses zero: {', '.join(uncertain)}."
            )
        else:
            said_parts.append(
                f"Every one of the {len(summary)} columns has an interval clear of zero."
            )
        if harmful:
            said_parts.append(
                f"Shuffling {', '.join(harmful)} makes the model score better, which is "
                f"the case for dropping it."
            )
    said_lines: List[str] = []
    for sentence in said_parts:
        said_lines.extend(wrap_no_orphan(sentence, 100))

    parts: List[str] = []
    parts.append(
        svg_open(
            width, height, "perm-title", "perm-desc", font_family=chrome_stack_for_theme(theme)
        )
    )
    parts.append(f'<title id="perm-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="perm-desc">Permutation importance for {len(summary)} columns, '
        f"ordered by mean drop from {xml_escape(summary[0][0])} at "
        f"{fmt_measured(summary[0][1], precision)} down to "
        f"{xml_escape(summary[-1][0])} at "
        f"{fmt_measured(summary[-1][1], precision)}. {xml_escape(said_measure)}. "
        f"{xml_escape(' '.join(said_parts))} {xml_escape(caveat)}.</desc>"
    )
    parts.append(
        "<style>"
        ".bar{cursor:default;}"
        ".bar:hover,.bar:focus{outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + foreground_tip_css(len(summary), mark_prefix="bar", tip_prefix="bartip")
        + "@media (prefers-reduced-motion:reduce){.tip{transition:none}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    # Sized to the canvas rather than fixed at 22. The academic theme sets
    # a serif face that runs wider than the sans one, and a title that fits
    # in corporate came out with its last two words off the edge.
    title_size = fit_font_size(title, width - 96.0, 22.0, min_px=15.0)
    parts.append(
        f'<text x="40" y="46" font-size="{title_size:.1f}" font-weight="700" '
        f'fill="{INK}" letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    for line_index, line in enumerate(wrap_no_orphan(subtitle, 106)[:2]):
        parts.append(
            f'<text x="40" y="{72 + line_index * 20:.1f}" font-size="14" '
            f'fill="{SECONDARY}">{xml_escape(line)}</text>'
        )
    parts.append(
        f'<text x="40" y="124" font-size="12" fill="{SECONDARY}" '
        f'font-family="{mono_family}">{xml_escape(said_measure)}</text>'
    )
    for line_index, line in enumerate(said_lines[:2]):
        parts.append(
            f'<text x="40" y="{144 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(line)}</text>'
        )
    parts.append(
        f'<text x="40" y="{height - 26:.1f}" font-size="11" fill="{SECONDARY}">'
        f"{xml_escape(caveat)}</text>"
    )

    for tick in ticks:
        parts.append(
            f'<line x1="{px(tick):.1f}" y1="{plot_y - 6:.1f}" x2="{px(tick):.1f}" '
            f'y2="{plot_y + plot_h:.1f}" stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{px(tick):.1f}" y="{plot_y + plot_h + 18:.1f}" font-size="11" '
            f'fill="{SECONDARY}" text-anchor="middle" font-family="{mono_family}">'
            f"{fmt_number(tick)}</text>"
        )
    parts.append(
        f'<line x1="{px(0.0):.1f}" y1="{plot_y - 6:.1f}" x2="{px(0.0):.1f}" '
        f'y2="{plot_y + plot_h:.1f}" stroke="{INK}" stroke-width="1.4"/>'
    )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{plot_y + plot_h + 44:.1f}" '
        f'font-size="12" fill="{SECONDARY}" text-anchor="middle">'
        f"{xml_escape(score_label)}</text>"
    )

    tips: List[str] = []
    for index, (name, mean, error, count) in enumerate(summary):
        middle = plot_y + index * row_h + row_h / 2
        spans_zero = error > 0.0 and abs(mean) <= error_multiple * error
        colour = adverse if mean < 0.0 else solid
        # A bar whose mean is near zero is a pixel wide, so drawing it
        # hollow says nothing at this scale. The row carries the tint
        # instead, and the eye finds it before it reads the chrome.
        if spans_zero:
            parts.append(
                f'<rect x="{plot_x:.1f}" y="{middle - row_h / 2:.1f}" '
                f'width="{plot_w:.1f}" height="{row_h:.1f}" fill="{INK}" '
                f'opacity="0.045"/>'
            )
        left, right = min(px(0.0), px(mean)), max(px(0.0), px(mean))
        parts.append(
            f'<rect x="{left:.1f}" y="{middle - row_h * 0.26:.1f}" '
            f'width="{max(right - left, 1.0):.1f}" height="{row_h * 0.52:.1f}" '
            + (
                f'fill="none" stroke="{colour}" stroke-width="1.6" stroke-dasharray="4 3"/>'
                if spans_zero
                else f'fill="{colour}"/>'
            )
        )
        bar_low, bar_high = mean - error_multiple * error, mean + error_multiple * error
        parts.append(
            f'<line x1="{px(bar_low):.1f}" y1="{middle:.1f}" x2="{px(bar_high):.1f}" '
            f'y2="{middle:.1f}" stroke="{INK}" stroke-width="1.4"/>'
        )
        for edge in (bar_low, bar_high):
            parts.append(
                f'<line x1="{px(edge):.1f}" y1="{middle - 5:.1f}" x2="{px(edge):.1f}" '
                f'y2="{middle + 5:.1f}" stroke="{INK}" stroke-width="1.4"/>'
            )
        parts.append(
            f'<text x="{plot_x - 12:.1f}" y="{middle + 4:.1f}" font-size="12" '
            f'fill="{INK}" text-anchor="end" font-family="{mono_family}">'
            f"{xml_escape(name)}</text>"
        )
        parts.append(
            f'<rect id="bar-{index}" class="bar hit" tabindex="0" role="img" '
            f'aria-label="{xml_escape(name)}: {fmt_measured(mean, precision)} mean drop '
            f"over {count} shuffles, interval {fmt_measured(bar_low, precision)} "
            f"to {fmt_measured(bar_high, precision)}"
            f'{", crossing zero" if spans_zero else ""}" '
            f'x="{plot_x:.1f}" y="{middle - row_h / 2:.1f}" width="{plot_w:.1f}" '
            f'height="{row_h:.1f}" fill="transparent">'
            f"<title>{xml_escape(name)}: {fmt_measured(mean, precision)}</title></rect>"
        )
        tips.append(
            tooltip_bubble(
                px(mean),
                middle,
                [
                    name,
                    f"{fmt_measured(mean, precision)} over {count} shuffles",
                    f"{fmt_measured(bar_low, precision)} to {fmt_measured(bar_high, precision)}",
                ],
                canvas_w=width,
                canvas_h=height,
                ink=INK,
                secondary=SECONDARY,
                border=GRIDLINE,
                elem_id=f"bartip-{index}",
            )
        )

    parts.extend(tips)
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_permutation_importance(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[str] = None,
    title: str = "Two columns cannot be told from noise, and one is worse than noise",
    subtitle: str = "Drop in held-out AUC when each column is shuffled, ten shuffles per column, mean with two standard errors.",
    width: int = 940,
    height: int = 620,
    feature: str = "feature",
    value: str = "drop",
    error_multiple: float = 2.0,
    top: int = 0,
    set_label: str = "held-out data",
    score_label: str = "Drop in AUC when shuffled",
    caveat: str = "two columns that move together each keep the other's score up, and no permutation can see it",
    measure_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Write a permutation-importance chart to disk and return the path.

    Parameters
    ----------
    data : list of dict or None
        One row per feature and repeat. Defaults to :data:`DEMO_DATA`.
    out : str or None
        Destination path; ``None`` writes beside the script.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    feature, value : str
        Row keys for the column name and the score drop.
    error_multiple : float
        How many standard errors the interval spans either side.
    top : int
        Draw only the `top` features by mean drop; 0 draws all.
    set_label : str
        Which data the score was measured on.
    score_label : str
        Axis title.
    caveat : str
        The standing limitation, drawn whatever the data says.
    measure_note, finding : str or None
        The line describing the measurement, and the sentence naming what
        the intervals show; ``None`` composes each from the data.
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
    >>> p = make_permutation_importance()
    >>> p.exists()
    True
    """
    svg = build_svg(
        data,
        title=title,
        subtitle=subtitle,
        width=width,
        height=height,
        feature=feature,
        value=value,
        error_multiple=error_multiple,
        top=top,
        set_label=set_label,
        score_label=score_label,
        caveat=caveat,
        measure_note=measure_note,
        finding=finding,
        mode=mode,
        accessibility=accessibility,
        theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "permutation-importance")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(
        __file__,
        "permutation-importance",
        build_svg,
        description="Draw what a model loses when each column is shuffled.",
    )


if __name__ == "__main__":
    main()
