#!/usr/bin/env python3
"""
make_shap-beeswarm — every row's explanation, one feature at a time.

One swarm per feature: each dot is one row of the data, placed at that
row's contribution and coloured by the value the feature took. A
waterfall explains one prediction; this shows the shape of the
explanation across all of them -- whether a feature pushes one way for
everyone, or both ways for different rows.

Where the usual beeswarm goes wrong
-------------------------------------
* **"High" and "low" with no numbers.** The colour runs from the
  feature's lowest value to its highest, and that range is different for
  every row of the chart -- a point of the scale means something else on
  each line. The two ends of each row carry the actual values, so the
  colour can be read rather than guessed at.
* **It invites "red on the right, so more is worse", and does not check
  it.** For a feature with a non-monotone effect the colours mix on both
  sides and that reading is simply wrong. The rank correlation between
  value and contribution is computed per feature, and a row where the
  colour does *not* line up is marked and named, which is the one thing
  this chart can say and the usual version never does.
* **Overplotting is hidden with random jitter.** A random vertical
  offset makes the width of a pile depend on a random seed. The dots are
  packed instead -- each one nudged only as far as it must go to clear
  its neighbour -- so the width of a pile is its density.
* **The ordering is a global summary posing as a ranking.** Rows are
  ordered by mean absolute contribution, which is a sensible default and
  not a statement about any single row; the chrome says so.

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
from _swarm import _swarm_positions  # noqa: E402
from _textfit import fit_font_size  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

_ROWS = 220


def _explanations(seed: int = 17) -> List[Dict[str, Any]]:
    """Two hundred and twenty rows of a churn model, explained feature by feature.

    Five of the six features behave the way a beeswarm is usually read:
    the contribution rises with the value, so the colour lines up along
    the axis and "more of this pushes the prediction up" is a fair
    summary.

    ``tenure_months`` does not, and it is here for that reason. Both the
    newest customers and the longest-standing ones are pushed *up* --
    the new ones because they have not settled, the old ones because
    they are on legacy contracts -- while everyone in the middle is
    pushed down. On the page that is red at both ends and blue in the
    middle, and the usual reading of the chart gets it exactly wrong.
    The rank correlation catches it: near zero, while the contribution
    is large.
    """
    rng = random.Random(seed)
    rows: List[Dict[str, Any]] = []
    for index in range(_ROWS):
        utilisation = rng.betavariate(2.0, 3.0)
        tenure = rng.uniform(0.0, 72.0)
        charge = rng.uniform(18.0, 118.0)
        tickets = rng.choice([0, 0, 0, 1, 1, 2, 3, 5])
        fibre = rng.random() < 0.42
        age = rng.uniform(19.0, 78.0)
        # The non-monotone one: a U, not a slope.
        settled = 1.0 - abs(tenure - 36.0) / 36.0
        rows.append(
            {
                "row": index,
                "feature": "credit_utilisation",
                "shap": round(1.9 * (utilisation - 0.4) + rng.gauss(0, 0.09), 4),
                "observed": round(utilisation, 3),
            }
        )
        rows.append(
            {
                "row": index,
                "feature": "tenure_months",
                "shap": round(0.95 * (0.5 - settled) + rng.gauss(0, 0.07), 4),
                "observed": round(tenure, 1),
            }
        )
        rows.append(
            {
                "row": index,
                "feature": "monthly_charge",
                "shap": round(0.012 * (charge - 62.0) + rng.gauss(0, 0.07), 4),
                "observed": round(charge, 2),
            }
        )
        rows.append(
            {
                "row": index,
                "feature": "support_tickets",
                "shap": round(0.16 * tickets - 0.13 + rng.gauss(0, 0.05), 4),
                "observed": tickets,
            }
        )
        rows.append(
            {
                "row": index,
                "feature": "has_fibre",
                "shap": round((0.22 if fibre else -0.16) + rng.gauss(0, 0.04), 4),
                "observed": 1 if fibre else 0,
            }
        )
        rows.append(
            {
                "row": index,
                "feature": "age",
                "shap": round(-0.009 * (age - 48.0) + rng.gauss(0, 0.05), 4),
                "observed": round(age, 1),
            }
        )
    return rows


DEMO_DATA: List[Dict[str, Any]] = _explanations()


def _ranks(values: List[float]) -> List[float]:
    """Average ranks of `values`, ties sharing the mean of their positions."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    position = 0
    while position < len(order):
        stop = position
        while stop + 1 < len(order) and values[order[stop + 1]] == values[order[position]]:
            stop += 1
        shared = (position + stop) / 2.0 + 1.0
        for index in range(position, stop + 1):
            ranks[order[index]] = shared
        position = stop + 1
    return ranks


def _rank_correlation(left: List[float], right: List[float]) -> float:
    """Spearman's rho between two equal-length lists; 0.0 if undefined.

    Rank-based rather than Pearson because the question is only whether
    the colour lines up along the axis, not whether it does so in a
    straight line. A feature whose effect is monotone but curved should
    still count as lining up.
    """
    if len(left) < 3:
        return 0.0
    a, b = _ranks(left), _ranks(right)
    mean_a, mean_b = sum(a) / len(a), sum(b) / len(b)
    top = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b, strict=True))
    left_spread = sum((x - mean_a) ** 2 for x in a) ** 0.5
    right_spread = sum((y - mean_b) ** 2 for y in b) ** 0.5
    if left_spread <= 0.0 or right_spread <= 0.0:
        return 0.0
    return top / (left_spread * right_spread)


def _ramp(fraction: float) -> Tuple[float, float, float]:
    """Blue to red across `fraction` in 0 to 1, as (r, g, b) in 0-255."""
    fraction = max(0.0, min(1.0, fraction))
    low = (0.0, 122.0, 255.0)
    high = (255.0, 59.0, 48.0)
    return tuple(low[i] + (high[i] - low[i]) * fraction for i in range(3))  # type: ignore[return-value]


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Five features push one way with their value; tenure pushes up at both ends",
    subtitle: str = "One dot per row per feature, placed at its contribution and coloured by the value the feature took.",
    width: int = 960,
    height: int = 660,
    feature: str = "feature",
    value: str = "shap",
    observed: str = "observed",
    top: int = 0,
    monotone_at: float = 0.45,
    units: str = "log-odds",
    x_label: str = "Contribution to the prediction",
    mixed_label: str = "colour does not line up",
    order_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full beeswarm SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        One row per observation and feature, carrying the contribution
        and the value the feature took. Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    feature, value, observed : str
        Row keys for the feature name, its contribution, and the feature
        value for that observation.
    top : int
        Draw only the `top` features by mean absolute contribution;
        0 draws all of them.
    monotone_at : float
        How strong the rank correlation between value and contribution
        must be before the row counts as lining up with its colour.
    units : str
        What the contributions are measured in.
    x_label : str
        Axis title.
    mixed_label : str
        What a row whose colour does not line up is called.
    order_note, finding : str or None
        The line describing the ordering and the colour, and the
        sentence naming the rows that do not line up; ``None`` composes
        each from the data.
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
        raise ValueError("a beeswarm needs at least one row")

    grouped: Dict[str, List[Tuple[float, float]]] = {}
    for row in rows:
        grouped.setdefault(str(row[feature]), []).append((float(row[value]), float(row[observed])))
    summary = sorted(
        (
            (
                name,
                sum(abs(shap) for shap, _ in pairs) / len(pairs),
                _rank_correlation([shap for shap, _ in pairs], [seen for _, seen in pairs]),
                pairs,
            )
            for name, pairs in grouped.items()
        ),
        key=lambda item: item[1],
        reverse=True,
    )
    if top > 0:
        summary = summary[:top]
    mixed = [name for name, _, rho, _ in summary if abs(rho) < monotone_at]

    mono_family = mono_stack_for_theme(theme)
    palette = load_palette(accessibility, theme=theme)
    marker = palette.get("Orange", "#FF9500")

    spread = [shap for _, _, _, pairs in summary for shap, _ in pairs]
    ticks = nice_ticks_range(min(spread), max(spread), 5)
    axis_low, axis_high = ticks[0], ticks[-1]

    plot_x = 182.0
    plot_y = 214.0
    plot_w = width - plot_x - 196.0
    plot_h = height - plot_y - 92.0
    row_h = plot_h / max(len(summary), 1)
    radius = max(1.6, min(3.0, row_h / 10.0))
    precision = (axis_high - axis_low) / 50.0

    def px(amount: float) -> float:
        return plot_x + (amount - axis_low) / (axis_high - axis_low) * plot_w

    said_order = (
        order_note
        if order_note is not None
        else (
            f"rows ordered by mean absolute contribution, a summary over all "
            f"{len(summary[0][3])} observations and not a claim about any one of them · "
            f"colour runs from each feature's own lowest value to its own highest"
        )
    )
    said_parts: List[str] = []
    if finding is not None:
        said_parts.append(finding)
    elif mixed:
        said_parts.append(
            f"{len(mixed)} of {len(summary)} rows "
            f"{'has' if len(mixed) == 1 else 'have'} a rank correlation below "
            f"{fmt_number(monotone_at)} between value and contribution: {', '.join(mixed)}."
        )
        said_parts.append(
            "There, reading the colour along the axis gets it backwards for part of the data."
        )
    else:
        said_parts.append(
            f"Every row's colour lines up along the axis: the rank correlation is above "
            f"{fmt_number(monotone_at)} throughout."
        )
    said_lines: List[str] = []
    for sentence in said_parts:
        said_lines.extend(wrap_no_orphan(sentence, 104))

    parts: List[str] = []
    parts.append(
        svg_open(
            width, height, "shapb-title", "shapb-desc", font_family=chrome_stack_for_theme(theme)
        )
    )
    parts.append(f'<title id="shapb-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="shapb-desc">A beeswarm of {len(summary)} features over '
        f"{len(summary[0][3])} observations, each dot one observation placed at its "
        f"contribution and coloured by the value the feature took. "
        f"{xml_escape(said_order)}. {xml_escape(' '.join(said_parts))}</desc>"
    )
    parts.append(
        "<style>"
        ".swarm{cursor:default;}"
        ".swarm:hover,.swarm:focus{outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + foreground_tip_css(len(summary), mark_prefix="swarm", tip_prefix="swarmtip")
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
    for line_index, line in enumerate(wrap_no_orphan(said_order, 104)[:2]):
        parts.append(
            f'<text x="40" y="{118 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(line)}</text>'
        )
    for line_index, line in enumerate(said_lines[:2]):
        parts.append(
            f'<text x="40" y="{160 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(line)}</text>'
        )

    for tick in ticks:
        parts.append(
            f'<line x1="{px(tick):.1f}" y1="{plot_y:.1f}" x2="{px(tick):.1f}" '
            f'y2="{plot_y + plot_h:.1f}" stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{px(tick):.1f}" y="{plot_y + plot_h + 18:.1f}" font-size="11" '
            f'fill="{SECONDARY}" text-anchor="middle" font-family="{mono_family}">'
            f"{fmt_number(tick)}</text>"
        )
    parts.append(
        f'<line x1="{px(0.0):.1f}" y1="{plot_y:.1f}" x2="{px(0.0):.1f}" '
        f'y2="{plot_y + plot_h:.1f}" stroke="{INK}" stroke-width="1.2"/>'
    )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{plot_y + plot_h + 44:.1f}" '
        f'font-size="12" fill="{SECONDARY}" text-anchor="middle">'
        f"{xml_escape(x_label)}</text>"
    )

    tips: List[str] = []
    for index, (name, strength, rho, pairs) in enumerate(summary):
        middle = plot_y + index * row_h + row_h / 2
        seen = [value_seen for _, value_seen in pairs]
        low, high = min(seen), max(seen)
        span = (high - low) or 1.0
        ordered = sorted(pairs, key=lambda pair: pair[0])
        positions = _swarm_positions(
            [(px(shap), 0.0) for shap, _ in ordered],
            middle,
            radius,
            max_offset=row_h * 0.42,
        )
        for (shap, value_seen), y in zip(ordered, positions, strict=True):
            red, green, blue = _ramp((value_seen - low) / span)
            parts.append(
                f'<circle cx="{px(shap):.1f}" cy="{y:.1f}" r="{radius:.1f}" '
                f'fill="rgb({red:.0f},{green:.0f},{blue:.0f})" opacity="0.82"/>'
            )
        caption = f"{name}"
        parts.append(
            f'<text x="{plot_x - 12:.1f}" y="{middle + 4:.1f}" font-size="12" '
            f'fill="{INK}" text-anchor="end" font-family="{mono_family}">'
            f"{xml_escape(caption)}</text>"
        )
        # The two ends of this row's own colour scale, in the feature's
        # own units: "high" and "low" alone cannot be read.
        parts.append(
            f'<text x="{plot_x + plot_w + 12:.1f}" y="{middle - 2:.1f}" font-size="10" '
            f'fill="{SECONDARY}" font-family="{mono_family}">'
            f"{fmt_number(low)} → {fmt_number(high)}</text>"
        )
        if abs(rho) < monotone_at:
            parts.append(
                f'<text x="{plot_x + plot_w + 12:.1f}" y="{middle + 11:.1f}" '
                f'font-size="10" fill="{marker}" font-weight="700">'
                f"{xml_escape(mixed_label)}</text>"
            )
        parts.append(
            f'<rect id="swarm-{index}" class="swarm hit" tabindex="0" role="img" '
            f'aria-label="{xml_escape(name)}: mean absolute contribution '
            f"{fmt_measured(strength, precision)} {xml_escape(units)} over {len(pairs)} "
            f"observations, values {fmt_number(low)} to {fmt_number(high)}, rank "
            f'correlation {fmt_number(rho)}" x="{plot_x:.1f}" '
            f'y="{middle - row_h / 2:.1f}" width="{plot_w:.1f}" height="{row_h:.1f}" '
            f'fill="transparent"><title>{xml_escape(name)}: '
            f"{fmt_measured(strength, precision)}</title></rect>"
        )
        tips.append(
            tooltip_bubble(
                plot_x + plot_w * 0.5,
                middle,
                [
                    name,
                    f"mean |contribution| {fmt_measured(strength, precision)} {units}",
                    f"rank correlation {fmt_number(rho)}",
                ],
                canvas_w=width,
                canvas_h=height,
                ink=INK,
                secondary=SECONDARY,
                border=GRIDLINE,
                elem_id=f"swarmtip-{index}",
            )
        )

    parts.extend(tips)
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_shap_beeswarm(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[str] = None,
    title: str = "Five features push one way with their value; tenure pushes up at both ends",
    subtitle: str = "One dot per row per feature, placed at its contribution and coloured by the value the feature took.",
    width: int = 960,
    height: int = 660,
    feature: str = "feature",
    value: str = "shap",
    observed: str = "observed",
    top: int = 0,
    monotone_at: float = 0.45,
    units: str = "log-odds",
    x_label: str = "Contribution to the prediction",
    mixed_label: str = "colour does not line up",
    order_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Write a SHAP beeswarm to disk and return the path.

    Parameters
    ----------
    data : list of dict or None
        One row per observation and feature. Defaults to
        :data:`DEMO_DATA`.
    out : str or None
        Destination path; ``None`` writes beside the script.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    feature, value, observed : str
        Row keys for the feature name, its contribution, and the feature
        value for that observation.
    top : int
        Draw only the `top` features by mean absolute contribution.
    monotone_at : float
        How strong the rank correlation must be before a row counts as
        lining up with its colour.
    units : str
        What the contributions are measured in.
    x_label : str
        Axis title.
    mixed_label : str
        What a row whose colour does not line up is called.
    order_note, finding : str or None
        The line describing the ordering and the colour, and the sentence
        naming the rows that do not line up; ``None`` composes each from
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
    >>> p = make_shap_beeswarm()
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
        observed=observed,
        top=top,
        monotone_at=monotone_at,
        units=units,
        x_label=x_label,
        mixed_label=mixed_label,
        order_note=order_note,
        finding=finding,
        mode=mode,
        accessibility=accessibility,
        theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "shap-beeswarm")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(
        __file__,
        "shap-beeswarm",
        build_svg,
        description="Draw every row's explanation, one feature per swarm.",
    )


if __name__ == "__main__":
    main()
