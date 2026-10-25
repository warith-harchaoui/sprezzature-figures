#!/usr/bin/env python3
"""
make_pdp-ice — the average effect, and the rows that disagree with it.

One line per row of the data, each showing what the model would predict
for that row as one feature is swept across its range, with the average
of those lines drawn on top. The average is the partial dependence; the
individual lines are the conditional expectations it was computed from.

Where the usual partial-dependence plot goes wrong
----------------------------------------------------
* **The average is drawn alone.** A flat partial dependence is produced
  just as easily by a feature that does nothing as by one that pushes
  half the rows up and the other half down by the same amount. The
  individual lines are drawn here, and the share of them moving against
  the average is computed and named: that number is the whole reason the
  individual lines exist.
* **The individual lines are drawn uncentred.** Every row starts at its
  own prediction, so the plot is a stack of near-parallel lines and the
  *shape* -- the only thing the chart is about -- is invisible behind
  the spread of starting points. Each line is shifted to start at zero
  by default, which is the only way the shapes can be compared, and the
  chrome says it was done.
* **The curve is drawn where there is no data.** Sweeping a feature to
  its maximum asks the model about rows that do not exist, and the
  answer is extrapolation presented as a finding. The feature's own
  distribution is drawn underneath, and the sparse tail is faded.
* **It assumes the feature can be moved on its own.** Sweeping
  `tenure` while holding `contract_type` fixed invents combinations the
  data never contained. Nothing in the numbers reveals it, so it is
  said.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

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

_LINES = 90
_GRID = [0.0, 6.0, 12.0, 18.0, 24.0, 30.0, 36.0, 42.0, 48.0, 54.0, 60.0, 66.0, 72.0]


def _curves(seed: int = 29) -> List[Dict[str, Any]]:
    """Ninety rows of a churn model, swept across tenure from 0 to 72 months.

    The demonstration exists for one fact: **the average is nearly flat
    and almost nothing is**. Rows on a month-to-month contract get safer
    the longer they stay; rows on a two-year contract get riskier as
    their term runs out. Averaged together the two cancel, and a
    partial-dependence plot drawn alone would report that tenure does
    not matter.

    The share of rows moving against the average is what the figure
    computes and says, and here it is close to half, which is the
    strongest possible statement that the average is not describing
    anybody.
    """
    rng = random.Random(seed)
    rows: List[Dict[str, Any]] = []
    for line in range(_LINES):
        monthly = rng.random() < 0.52
        level = rng.gauss(-0.4 if monthly else -1.5, 0.45)
        slope = (-0.021 if monthly else 0.019) * rng.uniform(0.75, 1.25)
        curvature = rng.uniform(0.00012, 0.00028) * (1.0 if monthly else -1.0)
        # Tenure itself is right-skewed: most customers are recent.
        observed = min(72.0, rng.expovariate(1.0 / 22.0))
        for point in _GRID:
            rows.append(
                {
                    "line": line,
                    "tenure": point,
                    "prediction": round(
                        level + slope * point + curvature * point * point + rng.gauss(0.0, 0.012), 4
                    ),
                    "sampled": round(observed, 1),
                }
            )
    return rows


DEMO_DATA: List[Dict[str, Any]] = _curves()


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "The average says tenure barely matters; 41% of rows move against it",
    subtitle: str = "One line per row as tenure is swept, each shifted to start at zero, with their average drawn on top.",
    width: int = 960,
    height: int = 640,
    line: str = "line",
    x: str = "tenure",
    y: str = "prediction",
    sampled: str = "sampled",
    centre_lines: bool = True,
    sparse_at: float = 0.9,
    max_lines: int = 90,
    x_label: str = "Tenure (months)",
    y_label: str = "Change in prediction (log-odds)",
    average_label: str = "average (partial dependence)",
    caveat: str = "sweeping one feature holds the others fixed, which invents rows the data never contained",
    method_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full partial-dependence SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        One row per line and grid point, carrying the model's output
        there. Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    line, x, y : str
        Row keys for which curve the point belongs to, the swept feature,
        and the model's output.
    sampled : str
        Row key for the value the feature actually took in that row, used
        to draw the feature's own distribution under the curves.
    centre_lines : bool
        Shift every curve to start at zero. On by default: uncentred,
        each curve starts at its own prediction and the shapes are
        invisible behind the spread of starting points.
    sparse_at : float
        The quantile of the observed feature beyond which the sweep is
        faded, because the model is being asked about rows that are
        barely represented.
    max_lines : int
        Cap on how many individual curves are drawn; the average is
        always computed from all of them.
    x_label, y_label : str
        Axis titles.
    average_label : str
        Caption on the average curve.
    caveat : str
        The standing limitation, drawn whatever the data says.
    method_note, finding : str or None
        The line describing what was drawn, and the sentence naming the
        disagreement; ``None`` composes each from the data.
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
        raise ValueError("a partial-dependence plot needs at least one row")

    curves: Dict[Any, Dict[float, float]] = {}
    observed: Dict[Any, float] = {}
    for row in rows:
        key = row[line]
        curves.setdefault(key, {})[float(row[x])] = float(row[y])
        if sampled in row and row[sampled] is not None:
            observed[key] = float(row[sampled])
    grid = sorted({point for curve in curves.values() for point in curve})
    if len(grid) < 2:
        raise ValueError(f"a sweep needs at least two values of {x!r}; this data has {len(grid)}")
    complete = {
        key: [curve[point] for point in grid]
        for key, curve in curves.items()
        if len(curve) == len(grid)
    }
    if not complete:
        raise ValueError("no curve covers every point of the sweep")

    if centre_lines:
        shaped = {key: [v - values[0] for v in values] for key, values in complete.items()}
    else:
        shaped = dict(complete)
    average = [
        sum(values[index] for values in shaped.values()) / len(shaped) for index in range(len(grid))
    ]

    # The number the individual lines exist to produce: how many of them
    # end up on the other side of where they started from the average.
    overall = average[-1] - average[0]
    against = [key for key, values in shaped.items() if (values[-1] - values[0]) * overall < 0.0]
    share = len(against) / len(shaped) if shaped else 0.0

    sparse_from = grid[-1]
    if observed:
        seen = sorted(observed.values())
        index = min(len(seen) - 1, int(round(sparse_at * (len(seen) - 1))))
        sparse_from = seen[index]

    mono_family = mono_stack_for_theme(theme)
    palette = load_palette(accessibility, theme=theme)
    strand = palette.get("Blue", "#007AFF")
    mean_ink = palette.get("Orange", "#FF9500")

    reach = [v for values in shaped.values() for v in values]
    ticks = nice_ticks_range(min(reach), max(reach), 5)
    axis_low, axis_high = ticks[0], ticks[-1]

    plot_x = 112.0
    plot_y = 218.0
    plot_w = width - plot_x - 232.0
    plot_h = height - plot_y - 132.0
    rug_y = plot_y + plot_h + 18.0
    precision = (axis_high - axis_low) / 50.0

    def px(point: float) -> float:
        return plot_x + (point - grid[0]) / (grid[-1] - grid[0] or 1.0) * plot_w

    def py(amount: float) -> float:
        return plot_y + plot_h - (amount - axis_low) / (axis_high - axis_low) * plot_h

    method_lines = (
        [method_note]
        if method_note is not None
        else [
            f"{len(shaped)} rows swept across {len(grid)} values of {x}"
            + (", each shifted to start at zero" if centre_lines else ", uncentred"),
            f"sweep faded beyond {fmt_number(sparse_from)}, the "
            f"{fmt_number(sparse_at * 100.0)}th percentile of the observed {x}",
        ]
    )
    said_method = " · ".join(method_lines)
    said_parts: List[str] = []
    if finding is not None:
        said_parts.append(finding)
    else:
        said_parts.append(
            f"The average moves {fmt_measured(overall, precision)} across the sweep, "
            f"and {fmt_number(share * 100.0)}% of rows move the other way."
        )
    said_lines: List[str] = []
    for sentence in said_parts:
        said_lines.extend(wrap_no_orphan(sentence, 104))

    parts: List[str] = []
    parts.append(
        svg_open(width, height, "pdp-title", "pdp-desc", font_family=chrome_stack_for_theme(theme))
    )
    parts.append(f'<title id="pdp-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="pdp-desc">A partial-dependence plot with individual conditional '
        f"expectation curves: {len(shaped)} rows swept across {xml_escape(x)} from "
        f"{fmt_number(grid[0])} to {fmt_number(grid[-1])}, with their average drawn on "
        f"top. {xml_escape(said_method)}. {xml_escape(' '.join(said_parts))} "
        f"{xml_escape(caveat)}.</desc>"
    )
    parts.append(
        "<style>"
        ".node{cursor:default;}"
        ".node:hover,.node:focus{outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + foreground_tip_css(len(grid), mark_prefix="node", tip_prefix="nodetip")
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
    method_drawn: List[str] = []
    for clause in method_lines:
        method_drawn.extend(wrap_no_orphan(clause, 104))
    for line_index, text in enumerate(method_drawn[:2]):
        parts.append(
            f'<text x="40" y="{122 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(text)}</text>'
        )
    for line_index, text in enumerate(said_lines[:2]):
        parts.append(
            f'<text x="40" y="{166 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(text)}</text>'
        )
    parts.append(
        f'<text x="40" y="{height - 24:.1f}" font-size="11" fill="{SECONDARY}">'
        f"{xml_escape(caveat)}</text>"
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

    # The sweep past the bulk of the data is faded: beyond here the model
    # is being asked about rows that barely exist.
    if sparse_from < grid[-1]:
        parts.append(
            f'<rect x="{px(sparse_from):.1f}" y="{plot_y:.1f}" '
            f'width="{plot_x + plot_w - px(sparse_from):.1f}" height="{plot_h:.1f}" '
            f'fill="{BG}" opacity="0.55"/>'
        )

    every = list(shaped.values())
    drawn = every[:max_lines] if max_lines > 0 else every
    for values in drawn:
        path = " ".join(
            f"{'M' if index == 0 else 'L'}{px(point):.1f},{py(values[index]):.1f}"
            for index, point in enumerate(grid)
        )
        parts.append(
            f'<path d="{path}" fill="none" stroke="{strand}" stroke-width="1" opacity="0.26"/>'
        )
    if sparse_from < grid[-1]:
        parts.append(
            f'<rect x="{px(sparse_from):.1f}" y="{plot_y:.1f}" '
            f'width="{plot_x + plot_w - px(sparse_from):.1f}" height="{plot_h:.1f}" '
            f'fill="{BG}" opacity="0.45"/>'
        )
        parts.append(
            f'<line x1="{px(sparse_from):.1f}" y1="{plot_y:.1f}" '
            f'x2="{px(sparse_from):.1f}" y2="{plot_y + plot_h:.1f}" stroke="{SECONDARY}" '
            f'stroke-width="1" stroke-dasharray="3 3"/>'
        )

    mean_path = " ".join(
        f"{'M' if index == 0 else 'L'}{px(point):.1f},{py(average[index]):.1f}"
        for index, point in enumerate(grid)
    )
    parts.append(
        f'<path d="{mean_path}" fill="none" stroke="{mean_ink}" stroke-width="3" '
        f'stroke-linejoin="round"/>'
    )
    parts.append(
        f'<text x="{plot_x + plot_w + 10:.1f}" y="{py(average[-1]) + 4:.1f}" '
        f'font-size="12" font-weight="700" fill="{mean_ink}">'
        f"{xml_escape(average_label)}</text>"
    )

    for value_seen in observed.values():
        parts.append(
            f'<line x1="{px(min(value_seen, grid[-1])):.1f}" y1="{rug_y:.1f}" '
            f'x2="{px(min(value_seen, grid[-1])):.1f}" y2="{rug_y + 8:.1f}" '
            f'stroke="{INK}" stroke-width="1" opacity="0.28"/>'
        )
    parts.append(
        f'<text x="{plot_x - 10:.1f}" y="{rug_y + 8:.1f}" font-size="10" '
        f'fill="{SECONDARY}" text-anchor="end" font-family="{mono_family}">'
        f"{xml_escape(x)}</text>"
    )

    tips: List[str] = []
    for index, point in enumerate(grid):
        parts.append(
            f'<text x="{px(point):.1f}" y="{rug_y + 26:.1f}" font-size="11" '
            f'fill="{SECONDARY}" text-anchor="middle" font-family="{mono_family}">'
            f"{fmt_number(point)}</text>"
        )
        spread = sorted(values[index] for values in shaped.values())
        parts.append(
            f'<rect id="node-{index}" class="node hit" tabindex="0" role="img" '
            f'aria-label="at {xml_escape(x)} {fmt_number(point)}: average '
            f"{fmt_measured(average[index], precision)}, rows from "
            f"{fmt_measured(spread[0], precision)} to "
            f'{fmt_measured(spread[-1], precision)}" '
            f'x="{px(point) - plot_w / (2 * len(grid)):.1f}" y="{plot_y:.1f}" '
            f'width="{plot_w / len(grid):.1f}" height="{plot_h:.1f}" fill="transparent">'
            f"<title>{xml_escape(x)} {fmt_number(point)}: "
            f"{fmt_measured(average[index], precision)}</title></rect>"
        )
        tips.append(
            tooltip_bubble(
                px(point),
                py(average[index]),
                [
                    f"{x} {fmt_number(point)}",
                    f"average {fmt_measured(average[index], precision)}",
                    f"rows {fmt_measured(spread[0], precision)} to "
                    f"{fmt_measured(spread[-1], precision)}",
                ],
                canvas_w=width,
                canvas_h=height,
                ink=INK,
                secondary=SECONDARY,
                border=GRIDLINE,
                elem_id=f"nodetip-{index}",
            )
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{rug_y + 50:.1f}" font-size="12" '
        f'fill="{SECONDARY}" text-anchor="middle">{xml_escape(x_label)}</text>'
    )
    parts.append(
        f'<text x="40" y="{plot_y - 12:.1f}" font-size="12" fill="{SECONDARY}">'
        f"{xml_escape(y_label)}</text>"
    )

    parts.extend(tips)
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_pdp_ice(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[str] = None,
    title: str = "The average says tenure barely matters; 41% of rows move against it",
    subtitle: str = "One line per row as tenure is swept, each shifted to start at zero, with their average drawn on top.",
    width: int = 960,
    height: int = 640,
    line: str = "line",
    x: str = "tenure",
    y: str = "prediction",
    sampled: str = "sampled",
    centre_lines: bool = True,
    sparse_at: float = 0.9,
    max_lines: int = 90,
    x_label: str = "Tenure (months)",
    y_label: str = "Change in prediction (log-odds)",
    average_label: str = "average (partial dependence)",
    caveat: str = "sweeping one feature holds the others fixed, which invents rows the data never contained",
    method_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Write a partial-dependence plot to disk and return the path.

    Parameters
    ----------
    data : list of dict or None
        One row per line and grid point. Defaults to :data:`DEMO_DATA`.
    out : str or None
        Destination path; ``None`` writes beside the script.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    line, x, y : str
        Row keys for the curve identity, the swept feature, and the
        model's output.
    sampled : str
        Row key for the value the feature actually took in that row.
    centre_lines : bool
        Shift every curve to start at zero.
    sparse_at : float
        The quantile of the observed feature beyond which the sweep is
        faded.
    max_lines : int
        Cap on how many individual curves are drawn.
    x_label, y_label : str
        Axis titles.
    average_label : str
        Caption on the average curve.
    caveat : str
        The standing limitation, drawn whatever the data says.
    method_note, finding : str or None
        The line describing what was drawn, and the sentence naming the
        disagreement; ``None`` composes each from the data.
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
    >>> p = make_pdp_ice()
    >>> p.exists()
    True
    """
    svg = build_svg(
        data,
        title=title,
        subtitle=subtitle,
        width=width,
        height=height,
        line=line,
        x=x,
        y=y,
        sampled=sampled,
        centre_lines=centre_lines,
        sparse_at=sparse_at,
        max_lines=max_lines,
        x_label=x_label,
        y_label=y_label,
        average_label=average_label,
        caveat=caveat,
        method_note=method_note,
        finding=finding,
        mode=mode,
        accessibility=accessibility,
        theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "pdp-ice")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(
        __file__,
        "pdp-ice",
        build_svg,
        description="Draw the average effect of a feature, and the rows that disagree.",
    )


if __name__ == "__main__":
    main()
