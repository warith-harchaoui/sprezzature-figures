#!/usr/bin/env python3
"""
make_pie — the plain pie chart, drawn the way a pie should be drawn.

The most asked-for chart in the whole catalogue, and the one this package
did not have: ``donut`` is a different figure, with a hole that buys back
the centre for a label and costs the reader the one thing a pie is good
at, which is reading a half or a quarter off the shape of a whole disc.
(COVERAGE.md names who else ships one and why that matters; a figure's own
file is about the figure.)

A pie earns its place only for part-of-whole data with few parts, read at
the level of "about half", "about a quarter". Past six or seven slices the
angles stop being comparable and a bar chart wins; the ``max_slices``
parameter rolls the tail into one "Other" wedge rather than letting the
figure degrade silently.

What this draws differently from the usual pie
----------------------------------------------
* **Sorted, clockwise from twelve.** An unordered pie forces the reader to
  compare every pair of angles. Largest first from the top means the first
  two slices answer most questions before the eye moves.
* **Labelled in place, no legend.** A legend turns reading a pie into a
  lookup: colour, then key, then back. Each slice carries its own name,
  its share and its value -- inside when the slice is wide enough to hold
  them, outside on a leader line when it is not.
* **Adjacency-aware colour.** Slices touch, and the last one wraps around
  to touch the first, so the hue order front-loads the quartet that stays
  distinct under colour-vision deficiency and only reaches the red/green
  pair when there are enough slices to separate them.
* **The total, stated.** A share is a claim about a whole; the whole is
  printed rather than left to be inferred from the slices.

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
from _style import BG, GRIDLINE, INK, SECONDARY, load_palette  # noqa: E402
from _svg import foreground_tip_css, svg_open, tooltip_bubble, xml_escape  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme  # noqa: E402

#: World electricity generation by source. A part-of-whole with a dominant
#: pair, a readable middle and a tail -- which is the shape a pie is for,
#: and the shape that shows what the leader lines and the "Other" rollup
#: are doing.
DEMO_DATA: List[Dict[str, Any]] = [
    {"source": "Coal", "share": 35.5},
    {"source": "Natural gas", "share": 22.5},
    {"source": "Hydro", "share": 14.3},
    {"source": "Nuclear", "share": 9.1},
    {"source": "Wind", "share": 7.8},
    {"source": "Solar", "share": 5.5},
    {"source": "Oil", "share": 2.8},
    {"source": "Biomass", "share": 2.5},
]

#: Below this angular span a slice cannot hold its own label, and the label
#: goes outside on a leader line. 0.42 rad is about 24 degrees, which is
#: where a two-line label stops fitting at the radii used here.
_INSIDE_MIN_ANGLE = 0.42


def _polar(cx: float, cy: float, r: float, angle: float) -> Tuple[float, float]:
    """Point at `angle` radians clockwise from twelve o'clock, `r` from the centre."""
    return cx + r * math.sin(angle), cy - r * math.cos(angle)


def _sector_path(cx: float, cy: float, r: float, a0: float, a1: float) -> str:
    """A pie wedge: centre, out to the arc, around, and back.

    The full-circle case is drawn as two half arcs: an arc command whose
    start and end points coincide draws nothing at all, so a single-category
    pie would come out blank.
    """
    if a1 - a0 >= 2.0 * math.pi - 1e-9:
        top = _polar(cx, cy, r, 0.0)
        bottom = _polar(cx, cy, r, math.pi)
        return (
            f"M {top[0]:.2f},{top[1]:.2f} A {r:.2f} {r:.2f} 0 1 1 {bottom[0]:.2f},{bottom[1]:.2f} "
            f"A {r:.2f} {r:.2f} 0 1 1 {top[0]:.2f},{top[1]:.2f} Z"
        )
    large_arc = 1 if (a1 - a0) > math.pi else 0
    x0, y0 = _polar(cx, cy, r, a0)
    x1, y1 = _polar(cx, cy, r, a1)
    return (
        f"M {cx:.2f},{cy:.2f} L {x0:.2f},{y0:.2f} "
        f"A {r:.2f} {r:.2f} 0 {large_arc} 1 {x1:.2f},{y1:.2f} Z"
    )


def _rolled_up(
    rows: List[Dict[str, Any]], category: str, value: str, max_slices: int, other_label: str
) -> List[Dict[str, Any]]:
    """Sort descending and fold everything past `max_slices` into one wedge.

    A pie with fifteen slices is not a pie, it is a colour wheel. Folding
    the tail is the honest version of the same figure: the rolled-up wedge
    says how many categories it stands for in its tooltip, so nothing is
    hidden, only summarised.
    """
    ordered = sorted(rows, key=lambda r: -float(r[value]))
    if max_slices <= 0 or len(ordered) <= max_slices:
        return ordered
    head, tail = ordered[: max_slices - 1], ordered[max_slices - 1 :]
    rolled = {
        category: other_label,
        value: sum(float(r[value]) for r in tail),
        "_rolled": len(tail),
    }
    return [*head, rolled]


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Two thirds of the world's electricity still comes from burning something",
    subtitle: str = "Share of global generation by source, 2024",
    width: int = 820,
    height: int = 560,
    category: str = "source",
    value: str = "share",
    unit: str = "%",
    max_slices: int = 7,
    other_label: str = "Other",
    footer: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full pie chart SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with a category key and a numeric key, named by `category` and
        `value`. Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    category, value : str
        Which key in each row holds the slice name and the slice size.
    unit : str
        Printed after each value. ``"%"`` is appended without a space, any
        other unit with one.
    max_slices : int
        Slices past this count are folded into one ``other_label`` wedge;
        0 disables the rollup and draws every row.
    other_label : str
        Name of the rolled-up wedge.
    footer : str or None
        The line at the foot of the figure. ``None`` composes it: the
        number of parts, the total when the unit is not a percentage, and
        a note naming the rolled-up wedge when there is one. Give a string
        to say something else entirely -- nothing a reader sees should be
        reachable only by editing this file.
    mode, accessibility : str, optional
        Forwarded to :func:`_interactive.fullscreen_control` /
        :func:`_style.load_palette`.
    theme : str, optional
        Visual theme: ``"corporate"`` (default, Roboto) or ``"academic"``
        (LaTeX-style Latin Modern).

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    rows = _rolled_up(
        list(data if data else DEMO_DATA), category, value, max_slices, other_label
    )
    total = sum(float(r[value]) for r in rows) or 1.0
    palette = load_palette(accessibility, theme=theme)
    # Slices are adjacent by construction and the last one wraps back onto
    # the first, so whichever hues land next to each other have to stay
    # apart under colour-vision deficiency. make_donut's order puts Red at
    # index 5 and Green at 6, which is fine for the 2-6 slices a donut is
    # for and wrong here, where the default rollup allows 7: the first
    # render of this figure put a red Solar wedge against a green Other.
    # Green moves to index 3 instead, so no adjacent pair -- including the
    # wrap from last back to first -- is ever red against green. The worst
    # remaining neighbours are teal and blue at exactly six slices, which
    # differ in lightness and are parted by the 2px background stroke.
    hue_order = [
        palette.get(h, d)
        for h, d in (
            ("Blue", "#007AFF"), ("Orange", "#FF9500"), ("Purple", "#AF52DE"),
            ("Green", "#28CD41"), ("Yellow", "#FFCC00"), ("Teal", "#79DBDC"),
            ("Red", "#FF3B30"), ("Pink", "#FF2D55"),
        )
    ]

    def quantity(raw: float) -> str:
        """The value as written on the figure, unit attached the way unit wants."""
        shown = f"{raw:,.1f}".rstrip("0").rstrip(".")
        return f"{shown}{unit}" if unit == "%" else f"{shown} {unit}".rstrip()

    top_margin, bottom_margin = 104.0, 64.0
    cx = width / 2.0
    cy = top_margin + (height - top_margin - bottom_margin) / 2.0
    # The radius leaves room for a label column on each side; the disc is
    # the figure, but an outside label that runs off the canvas is worse
    # than a slightly smaller disc.
    r_outer = min((height - top_margin - bottom_margin) / 2.0, width / 2.0 - 190.0)

    parts: List[str] = []
    parts.append(
        svg_open(width, height, "pie-title", "pie-desc", font_family=chrome_stack_for_theme(theme))
    )
    parts.append(f'<title id="pie-title">{xml_escape(title)}</title>')
    biggest = rows[0]
    parts.append(
        f'<desc id="pie-desc">Pie chart of {len(rows)} parts of a whole totalling '
        f'{quantity(total)}. The largest is {xml_escape(str(biggest[category]))} at '
        f'{float(biggest[value]) / total * 100:.0f}%. Every slice is labelled on the '
        f'figure; hover or focus one for its exact value.</desc>'
    )
    parts.append(
        "<style>"
        ".slice{transition:opacity .15s ease;cursor:default;}"
        ".slice:hover,.slice:focus{opacity:.78;outline:none;}"
        "@media (prefers-reduced-motion: reduce){.slice{transition:none;}}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + foreground_tip_css(len(rows), mark_prefix="slice", tip_prefix="slicetip")
        + "@media (prefers-reduced-motion:reduce){.tip{transition:none}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="{width / 2:.1f}" y="46" font-size="22" font-weight="700" fill="{INK}" '
        f'text-anchor="middle" letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(
        f'<text x="{width / 2:.1f}" y="72" font-size="14" fill="{SECONDARY}" '
        f'text-anchor="middle">{xml_escape(subtitle)}</text>'
    )

    angle = 0.0
    wedges: List[str] = []
    leaders: List[str] = []
    labels: List[str] = []
    tips: List[str] = []
    outside: List[Dict[str, Any]] = []
    for i, row in enumerate(rows):
        raw = float(row[value])
        share = raw / total
        a0, a1 = angle, angle + share * 2.0 * math.pi
        angle = a1
        mid = (a0 + a1) / 2.0
        color = hue_order[i % len(hue_order)]
        name = str(row[category])
        rolled = int(row.get("_rolled", 0))

        # With percentages, the value and the share are the same number, and
        # "14.3% · 14.3% of the whole" says it twice. Caught by running the
        # gallery localiser, which lists every visible string: a duplicate
        # reads as noise in one language and as a translation bug in the next.
        if unit == "%":
            measured = f"{share * 100:.1f}% of the whole"
        else:
            measured = f"{quantity(raw)} · {share * 100:.1f}% of the whole"
        tip_lines = [name, measured]
        if rolled:
            tip_lines.append(f"{rolled} smaller categories, summed")
        else:
            tip_lines.append(f"rank {i + 1} of {len(rows)}")
        wedges.append(
            f'<path id="slice-{i}" class="slice hit" tabindex="0" role="img" '
            f'aria-label="{xml_escape(name)}: {share * 100:.1f} percent" '
            f'd="{_sector_path(cx, cy, r_outer, a0, a1)}" fill="{color}" '
            f'stroke="{BG}" stroke-width="2">'
            f'<title>{xml_escape(f"{name}: {measured}")}</title></path>'
        )

        if a1 - a0 >= _INSIDE_MIN_ANGLE:
            lx, ly = _polar(cx, cy, r_outer * 0.62, mid)
            labels.append(
                f'<text x="{lx:.1f}" y="{ly - 7:.1f}" font-size="14" font-weight="700" '
                f'fill="{BG}" text-anchor="middle">{xml_escape(name)}</text>'
            )
            labels.append(
                f'<text x="{lx:.1f}" y="{ly + 11:.1f}" font-size="13" fill="{BG}" '
                f'text-anchor="middle" opacity="0.92">{share * 100:.1f}%</text>'
            )
            tips.append(
                tooltip_bubble(
                    lx, ly + 14, tip_lines, canvas_w=width, canvas_h=height,
                    ink=INK, secondary=SECONDARY, border=GRIDLINE, elem_id=f"slicetip-{i}",
                )
            )
        else:
            outside.append({"i": i, "name": name, "share": share, "mid": mid, "tip": tip_lines})

    # Outside labels are placed only once every wedge is known, because
    # where one can go depends on where the others went. The first render
    # stacked them in slice order -- largest slice first -- and slice order
    # is not vertical order: on the left of a pie, each following slice sits
    # *higher*, so the second label was pushed below a label that belonged
    # under it and the two leader lines crossed. Sorting each side by where
    # its label naturally wants to sit, then pushing down only to clear the
    # one above, removes the crossing by construction.
    for side in ("right", "left"):
        on_this_side = [
            item for item in outside
            if (math.sin(item["mid"]) >= 0) == (side == "right")
        ]
        for item in on_this_side:
            item["ex"], item["ey"] = _polar(cx, cy, r_outer + 10.0, item["mid"])
        on_this_side.sort(key=lambda item: item["ey"])
        sign = 1.0 if side == "right" else -1.0
        anchor = "start" if side == "right" else "end"
        free = 78.0
        for item in on_this_side:
            ly = max(item["ey"], free)
            free = ly + 34.0
            # Each label sits beside *its own* slice rather than in a column
            # pinned to the edge of the canvas. A column is what a page with
            # ten outside labels needs; with two it draws a long shallow line
            # across empty space and makes the reader trace which slice it
            # came from. Leaving first along the radius, then turning, says
            # "this belongs to that wedge" in the shape of the line itself.
            radial_x, radial_y = _polar(cx, cy, r_outer + 18.0, item["mid"])
            label_x = radial_x + 26.0 * sign
            label_x = min(max(label_x, 70.0), width - 70.0)
            leaders.append(
                f'<path d="M {item["ex"]:.1f},{item["ey"]:.1f} L {radial_x:.1f},{radial_y:.1f} '
                f'L {label_x - 8.0 * sign:.1f},{ly:.1f} L {label_x:.1f},{ly:.1f}" '
                f'fill="none" stroke="{GRIDLINE}" stroke-width="1.2"/>'
            )
            labels.append(
                f'<text x="{label_x:.1f}" y="{ly - 3:.1f}" font-size="13" font-weight="700" '
                f'fill="{INK}" text-anchor="{anchor}">{xml_escape(str(item["name"]))}</text>'
            )
            labels.append(
                f'<text x="{label_x:.1f}" y="{ly + 14:.1f}" font-size="12" fill="{SECONDARY}" '
                f'text-anchor="{anchor}">{float(item["share"]) * 100:.1f}%</text>'
            )
            tips.append(
                tooltip_bubble(
                    label_x, ly + 16, list(item["tip"]), canvas_w=width, canvas_h=height,
                    ink=INK, secondary=SECONDARY, border=GRIDLINE,
                    elem_id=f"slicetip-{item['i']}",
                )
            )

    parts.extend(leaders)
    parts.extend(wedges)
    parts.extend(labels)
    # Bubbles last: SVG has no z-index, so anything drawn after a bubble
    # would cover it.
    parts.extend(tips)
    # The total sits at the foot, not under the subtitle: sorting the slices
    # largest-first from twelve o'clock puts the *smallest* ones just left of
    # twelve by construction, so the band directly above the disc is exactly
    # where their labels have to go. A line of chrome there costs the figure
    # its only free space.
    # "Total 100% across 7 parts" tells a reader of percentages nothing they
    # did not already know. What they cannot see, on a printed copy with no
    # tooltips, is that the last wedge is a rollup -- so that is what the
    # foot says when there is one.
    rolled_wedge = next((r for r in rows if int(r.get("_rolled", 0))), None)
    if footer is not None:
        foot = footer
    else:
        if unit == "%" and 99.0 <= total <= 101.0:
            foot = f"{len(rows)} parts of a whole"
        else:
            foot = (
                f"Total {quantity(total)} across {len(rows)} "
                f"{'part' if len(rows) == 1 else 'parts'}"
            )
        if rolled_wedge is not None:
            foot += (
                f" · {rolled_wedge[category]} groups the "
                f"{int(rolled_wedge['_rolled'])} smallest"
            )
    parts.append(
        f'<text x="{width / 2:.1f}" y="{height - 20:.1f}" font-size="12" fill="{SECONDARY}" '
        f'text-anchor="middle">{xml_escape(foot)}</text>'
    )
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_pie(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Two thirds of the world's electricity still comes from burning something",
    subtitle: str = "Share of global generation by source, 2024",
    width: int = 820,
    height: int = 560,
    category: str = "source",
    value: str = "share",
    unit: str = "%",
    max_slices: int = 7,
    other_label: str = "Other",
    footer: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored pie chart and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``source`` (str) and ``share`` (float), or whatever
        `category` and `value` name. Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/pie.svg``.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    category, value : str
        Which key holds the slice name and the slice size.
    unit : str
        Printed after each value; ``"%"`` attaches without a space.
    max_slices : int
        Fold the tail past this many slices into one wedge; 0 draws them all.
    other_label : str
        Name of that rolled-up wedge.
    footer : str or None
        The line at the foot; ``None`` composes the default.
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
    >>> p = make_pie()
    >>> p.exists()
    True
    """
    svg = build_svg(
        data, title=title, subtitle=subtitle, width=width, height=height,
        category=category, value=value, unit=unit, max_slices=max_slices,
        other_label=other_label, footer=footer, mode=mode,
        accessibility=accessibility, theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "pie")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "pie", build_svg, description="Generate a pie chart.")


if __name__ == "__main__":
    main()
