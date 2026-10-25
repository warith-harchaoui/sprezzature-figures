#!/usr/bin/env python3
"""
make_funnel-area — a funnel whose area is the quantity, not its width.

Stacked trapezoids, one per stage, narrowing downward. The quantity at
each stage is the trapezoid's **area**, which is what a reader's eye
measures whether the chart intends it or not.

Where the usual funnel goes wrong
-----------------------------------
* **The height is made proportional and the area is left to the
  taper.** A funnel narrows, so a band low down is shorter across than
  one at the top; give both a height proportional to their count and
  the lower one ends up with *less area* than its count deserves. The
  eye measures area. Here the heights are solved so the areas come out
  proportional, and the chrome reports how far the naive version would
  be off -- measured on the data in front of it, not asserted.
  ``size_by="height"`` draws that version for comparison.
* **The drop between stages is not given.** A funnel is read for its
  conversion rates, and leaving them to subtraction is how a 94%
  carrying stage and a 31% carrying stage come to look similar. Each
  gap carries the rate that crossed it, and the worst one is named.
* **It is used for things that are not funnels.** A funnel claims each
  stage is a *subset* of the one above. Categories that merely differ
  in size are not, and drawing them as a funnel invents a sequence. The
  figure checks that the stages decrease and says so when they do not.

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
    fmt_number,
    foreground_tip_css,
    svg_open,
    tooltip_bubble,
    wrap_no_orphan,
    xml_escape,
)
from _textfit import fit_font_size  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

DEMO_DATA: List[Dict[str, Any]] = [
    {"stage": "Landed on the page", "count": 41_300},
    {"stage": "Started signup", "count": 38_900},
    {"stage": "Verified email", "count": 31_600},
    {"stage": "Entered payment", "count": 9_800},
    {"stage": "Paid", "count": 8_950},
]


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Two in three are lost entering payment; no other step loses more than a fifth",
    subtitle: str = "Each band's area is its count, so the eye reads the right quantity; the usual height-proportional version draws the last stage ten percent too small.",
    width: int = 900,
    height: int = 620,
    stage: str = "stage",
    value: str = "count",
    size_by: str = "area",
    taper: float = 0.18,
    rate_label: str = "carried",
    method_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full funnel SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        One row per stage, in order from widest to narrowest. Defaults
        to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    stage, value : str
        Row keys for the stage name and its count.
    size_by : str
        ``"area"`` solves each band's height so its *area* is
        proportional to its count, which is what the eye measures;
        ``"height"`` makes the height proportional and lets the area
        fall where the taper puts it, which is the usual hand-rolled
        version and under-draws every stage below the first. Named on
        the canvas either way, with the distortion measured.
    taper : float
        How much narrower the bottom of the funnel is than the top, as a
        fraction. Pure decoration, and the only reason it is an option
        is that it changes nothing about the areas.
    rate_label : str
        Word used for the share that crossed each gap.
    method_note, finding : str or None
        The line saying how the bands are sized, and the sentence naming
        the worst step; ``None`` composes each from the data.
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
    if size_by not in ("area", "height"):
        raise ValueError(f"size_by is 'area' or 'height', got {size_by!r}")
    rows = list(data if data else DEMO_DATA)
    if len(rows) < 2:
        raise ValueError(f"a funnel needs at least two stages; this data has {len(rows)}")
    names = [str(row[stage]) for row in rows]
    counts = [float(row[value]) for row in rows]
    if any(count < 0 for count in counts):
        raise ValueError("a funnel counts people, so no stage can be negative")
    if counts[0] <= 0:
        raise ValueError("the first stage is the denominator, so it cannot be zero")

    # A funnel claims each stage is a subset of the one above.
    climbs = [
        (names[index - 1], names[index])
        for index in range(1, len(counts))
        if counts[index] > counts[index - 1]
    ]
    rates = [counts[index] / counts[index - 1] for index in range(1, len(counts))]
    worst = min(range(len(rates)), key=lambda index: rates[index]) if rates else 0

    mono_family = mono_stack_for_theme(theme)
    palette = load_palette(accessibility, theme=theme)
    wheel = [
        palette.get(key, fallback) for key, fallback in (
            ("Blue", "#007AFF"), ("Teal", "#30B0C7"), ("Green", "#28CD41"),
            ("Purple", "#5856D6"), ("Orange", "#FF9500"), ("Red", "#FF3B30"),
        )
    ]
    accent = palette.get("Orange", "#FF9500")

    plot_x = 180.0
    plot_y = 214.0
    plot_w = width - plot_x - 240.0
    plot_h = height - plot_y - 72.0

    # The half-widths at each boundary: a straight taper from 1 to
    # `1 - taper`, so the funnel narrows without the narrowing carrying
    # any information of its own.
    boundaries = len(rows) + 1
    half = [
        plot_w / 2.0 * (1.0 - taper * index / max(boundaries - 1, 1))
        for index in range(boundaries)
    ]

    # Band i is a trapezoid of height h_i whose mean full width is
    # half[i] + half[i+1]; its area is the product. The two modes differ
    # in which of the two factors carries the count.
    means = [(half[index] + half[index + 1]) for index in range(len(rows))]
    if size_by == "area":
        # Solve the heights so the *areas* share out in proportion.
        weights = [counts[index] / means[index] for index in range(len(rows))]
    else:
        # The usual hand-rolled version: the height carries the count and
        # the area is whatever the taper leaves, which under-draws every
        # stage below the first in proportion to how much it has narrowed.
        weights = list(counts)
    scale = plot_h / sum(weights)
    heights = [weight * scale for weight in weights]

    # How wrong the naive version is here, measured rather than asserted:
    # the last band's share of the total area against its share of the
    # total count.
    naive_scale = plot_h / sum(counts)
    naive_areas = [counts[i] * naive_scale * means[i] for i in range(len(rows))]
    naive_share = naive_areas[-1] / sum(naive_areas) if sum(naive_areas) else 0.0
    true_share = counts[-1] / sum(counts) if sum(counts) else 0.0
    distortion = (naive_share / true_share - 1.0) * 100.0 if true_share else 0.0

    tops = [plot_y]
    for height_of in heights:
        tops.append(tops[-1] + height_of)

    method_lines = (
        [method_note] if method_note is not None
        else [
            f"each band's area is its count — the quantity the eye measures; "
            f"sizing by height instead would draw the last stage "
            f"{fmt_number(abs(distortion))}% "
            f"{'too large' if distortion > 0 else 'too small'}"
            if size_by == "area"
            else f"each band's *height* is its count, so the taper leaves the last "
                 f"stage {fmt_number(abs(distortion))}% "
                 f"{'too large' if distortion > 0 else 'too small'} by area",
            f"{fmt_number(counts[-1] / counts[0] * 100.0)}% of "
            f"{fmt_number(counts[0])} reach the last stage",
        ] + ([
            f"warning: {len(climbs)} stage(s) are larger than the one above, so this is "
            f"not a funnel"
        ] if climbs else [])
    )
    said_method = " · ".join(method_lines)
    said_parts: List[str] = []
    if finding is not None:
        said_parts.append(finding)
    elif rates:
        best = max(range(len(rates)), key=lambda index: rates[index])
        said_parts.append(
            f"The worst step is {names[worst]} to {names[worst + 1]}, carrying "
            f"{fmt_number(rates[worst] * 100.0)}%; the best is {names[best]} to "
            f"{names[best + 1]} at {fmt_number(rates[best] * 100.0)}%."
        )
    said_lines: List[str] = []
    for sentence in said_parts:
        said_lines.extend(wrap_no_orphan(sentence, 104))

    parts: List[str] = []
    parts.append(
        svg_open(width, height, "funnel-title", "funnel-desc",
                 font_family=chrome_stack_for_theme(theme))
    )
    parts.append(f'<title id="funnel-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="funnel-desc">A funnel of {len(rows)} stages from '
        f'{xml_escape(names[0])} at {fmt_number(counts[0])} down to '
        f'{xml_escape(names[-1])} at {fmt_number(counts[-1])}. '
        f'{xml_escape(said_method)}. {xml_escape(" ".join(said_parts))}</desc>'
    )
    parts.append(
        "<style>"
        ".band{cursor:default;}"
        ".band:hover,.band:focus{outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + foreground_tip_css(len(rows), mark_prefix="band", tip_prefix="bandtip")
        + "@media (prefers-reduced-motion:reduce){.tip{transition:none}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    title_size = fit_font_size(title, width - 96.0, 22.0, min_px=15.0)
    parts.append(
        f'<text x="40" y="46" font-size="{title_size:.1f}" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    for line_index, text in enumerate(wrap_no_orphan(subtitle, 110)[:2]):
        parts.append(
            f'<text x="40" y="{72 + line_index * 20:.1f}" font-size="14" '
            f'fill="{SECONDARY}">{xml_escape(text)}</text>'
        )
    method_drawn: List[str] = []
    for clause in method_lines:
        method_drawn.extend(wrap_no_orphan(clause, 104))
    for line_index, text in enumerate(method_drawn[:3]):
        parts.append(
            f'<text x="40" y="{124 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(text)}</text>'
        )
    for line_index, text in enumerate(said_lines[:2]):
        parts.append(
            f'<text x="40" y="{height - 40 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(text)}</text>'
        )

    centre = plot_x + plot_w / 2.0
    tips: List[str] = []
    for index, name in enumerate(names):
        top, bottom = tops[index], tops[index + 1]
        upper, lower = half[index], half[index + 1]
        colour = wheel[index % len(wheel)]
        parts.append(
            f'<path d="M{centre - upper:.1f},{top:.1f} L{centre + upper:.1f},{top:.1f} '
            f'L{centre + lower:.1f},{bottom:.1f} L{centre - lower:.1f},{bottom:.1f} Z" '
            f'fill="{colour}" opacity="0.88"/>'
        )
        middle = (top + bottom) / 2.0
        share = counts[index] / counts[0] * 100.0
        if bottom - top > 15.0:
            parts.append(
                f'<text x="{centre:.1f}" y="{middle + 4:.1f}" font-size="12" '
                f'fill="#FFFFFF" text-anchor="middle" font-weight="600">'
                f'{fmt_number(counts[index])}</text>'
            )
        parts.append(
            f'<text x="{plot_x - 16:.1f}" y="{middle + 4:.1f}" font-size="12" '
            f'fill="{INK}" text-anchor="end">{xml_escape(name)}</text>'
        )
        # The share sits under the stage name on the left; the rate that
        # crossed into this band sits on the right, at the boundary. Two
        # columns, because the first draft put the rate on the boundary
        # *inside* the funnel, where a short band's own count ran into it.
        parts.append(
            f'<text x="{plot_x - 16:.1f}" y="{middle + 18:.1f}" font-size="10" '
            f'fill="{SECONDARY}" text-anchor="end" font-family="{mono_family}">'
            f'{fmt_number(share)}% of the top</text>'
        )
        if index:
            rate = rates[index - 1]
            hot = index - 1 == worst
            parts.append(
                f'<text x="{plot_x + plot_w + 16:.1f}" y="{top + 4:.1f}" font-size="11" '
                f'fill="{accent if hot else SECONDARY}" '
                f'font-weight="{700 if hot else 400}">'
                f'{fmt_number(rate * 100.0)}% {xml_escape(rate_label)}</text>'
            )
        parts.append(
            f'<rect id="band-{index}" class="band hit" tabindex="0" role="img" '
            f'aria-label="{xml_escape(name)}: {fmt_number(counts[index])}, '
            f'{fmt_number(share)}% of the first stage'
            + (f", {fmt_number(rates[index - 1] * 100.0)}% of the one above"
               if index else "")
            + f'" x="{centre - upper:.1f}" y="{top:.1f}" '
            f'width="{2 * upper:.1f}" height="{max(bottom - top, 1.0):.1f}" '
            f'fill="transparent"><title>{xml_escape(name)}: '
            f'{fmt_number(counts[index])}</title></rect>'
        )
        tips.append(
            tooltip_bubble(
                centre, middle,
                [name, fmt_number(counts[index]),
                 f"{fmt_number(share)}% of the top"
                 + (f" · {fmt_number(rates[index - 1] * 100.0)}% {rate_label}"
                    if index else "")],
                canvas_w=width, canvas_h=height, ink=INK, secondary=SECONDARY,
                border=GRIDLINE, elem_id=f"bandtip-{index}",
            )
        )

    parts.extend(tips)
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_funnel_area(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[str] = None,
    title: str = "Two in three are lost entering payment; no other step loses more than a fifth",
    subtitle: str = "Each band's area is its count, so the eye reads the right quantity; the usual height-proportional version draws the last stage ten percent too small.",
    width: int = 900,
    height: int = 620,
    stage: str = "stage",
    value: str = "count",
    size_by: str = "area",
    taper: float = 0.18,
    rate_label: str = "carried",
    method_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Write a funnel to disk and return the path.

    Parameters
    ----------
    data : list of dict or None
        One row per stage, in order. Defaults to :data:`DEMO_DATA`.
    out : str or None
        Destination path; ``None`` writes beside the script.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    stage, value : str
        Row keys for the stage name and its count.
    size_by : str
        ``"area"`` or ``"height"``.
    taper : float
        How much narrower the bottom is than the top.
    rate_label : str
        Word used for the share that crossed each gap.
    method_note, finding : str or None
        The line saying how the bands are sized, and the sentence naming
        the worst step; ``None`` composes each from the data.
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
    >>> p = make_funnel_area()
    >>> p.exists()
    True
    """
    svg = build_svg(
        data, title=title, subtitle=subtitle, width=width, height=height,
        stage=stage, value=value, size_by=size_by, taper=taper,
        rate_label=rate_label, method_note=method_note, finding=finding,
        mode=mode, accessibility=accessibility, theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "funnel-area")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "funnel-area", build_svg,
               description="Draw a funnel whose area, not width, is the quantity.")


if __name__ == "__main__":
    main()
