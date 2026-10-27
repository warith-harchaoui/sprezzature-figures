"""
make_speaking_time — a speaker-diarisation "who spoke, and for how long" donut.

Turns a diarisation result (one row per speaker, with a talk-time in
seconds) into a large, clean donut where each slice is one speaker. Each
slice is annotated **outside the ring** with the speaker's name, the
human-readable duration (``mm:ss``) and its share of the conversation
(``%``); a thin leader line ties each annotation to its arc, and labels
are side-aware (right labels left-aligned, left labels right-aligned) so
the spacing stays harmonious all the way round. The hole carries the
total running time: the headline number.

Pure-Python, hand-built SVG string, so the label geometry can be placed
exactly. Big canvas by design.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import svg_example_path, write_raster_companions, write_svg  # noqa: E402
from _style import load_palette, os_adaptive_style, os_dark_style, qualitative_sequence  # noqa: E402
from _svg import foreground_tip_css, point_on_circle, tooltip_bubble, xml_escape  # noqa: E402
from _textfit import text_width  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme  # noqa: E402

# ------------------------------------------------------------------
# Illustrative diarisation output — a 40-minute round-table. Talk-time
# is whole seconds so ``mm:ss`` and ``%`` stay mutually consistent; the
# four values sum to 2400 s = 40:00 with clean integer percentages.
#
# Row-record demo data: one row per speaker, the contract's
# ``list[dict[str, Any]]`` shape (``name`` + ``seconds``).
# ------------------------------------------------------------------
# Chrome written for :data:`DEMO_DATA` and for it alone. ``make_figure`` blanks both the
# moment a caller supplies its own rows (``_without_demo_chrome``), which only works if
# they are *parameters*: while the subtitle was hardcoded inside the builder, every caller
# got "a 40-minute round table" printed over its own recording. False chrome is worse than
# none, because it affirms. ``None`` means "use these", ``""`` means "print nothing".
TITLE: str = "Who spoke, and for how long"
SUBTITLE: str = "Speaking time per participant · a 40-minute round table"

#: The caption under the total, in the middle of the ring. A parameter rather than a
#: literal because the host page may well be in another language: a French report with an
#: English "total time" in the middle of its figure reads as a picture borrowed from
#: somewhere else.
CENTRE_LABEL: str = "total time"

DEMO_DATA: List[Dict[str, Any]] = [
    {"name": "Alice NGUYEN", "seconds": 984},   # 16:24 · 41 %
    {"name": "Marc DUBOIS", "seconds": 648},     # 10:48 · 27 %
    {"name": "Sofia ROSSI", "seconds": 432},     # 07:12 · 18 %
    {"name": "Karim HADDAD", "seconds": 336},    # 05:36 · 14 %
]

def _slice_colors(accessibility: str = "universal", n: int = 4, theme: str = "corporate") -> List[str]:
    """Return ``n`` donut-slice hues at a given accessibility level.

    The first four match the house Blue/Orange/Green/Purple set (so the
    shipped four-speaker demo stays byte-for-byte the same); any additional
    slice a caller's row data needs is filled from the house qualitative
    sequence.

    Parameters
    ----------
    accessibility : str, optional
        Palette accessibility level forwarded to :func:`_style.load_palette`.
    n : int, optional
        Number of slice colours to return (one per speaker). Default 4.
    theme : str, optional
        Forwarded to :func:`_style.load_palette` / :func:`_style.qualitative_sequence`.

    Returns
    -------
    list of str
        ``n`` hex strings, one per speaker slice (in speaker order).
    """
    pal = load_palette(accessibility, theme=theme)
    base = [pal["Blue"], pal["Orange"], pal["Green"], pal["Purple"]]
    if n <= len(base):
        return base[:n]
    return (base + qualitative_sequence(n, theme=theme))[:n]


SLICE_COLORS = _slice_colors()

INK = "#1D1D1F"
SECONDARY = "#6E6E73"
LEADER = "#C7C7CC"

# Geometry — deliberately large.
W, H = 1120, 760
CX, CY = 540, 430
R_OUT, R_IN = 250, 158


def _mmss(seconds: int) -> str:
    """Format whole seconds as ``m:ss`` (or ``mm:ss``)."""
    return f"{seconds // 60}:{seconds % 60:02d}"


# Thin wrapper over the shared polar helper; call sites keep the _pt name
# and the (cx, cy, radius, angle) argument order.
def _pt(cx: float, cy: float, radius: float, angle: float) -> tuple[float, float]:
    """Cartesian point at ``radius``/``angle`` (radians) about a centre."""
    return point_on_circle(cx, cy, radius, angle)


#: Corner radius on each segment end, and the angular gap between
#: neighbouring segments (radians). Together these give the modern
#: "floating rounded pills" donut look — rounded but never notched.
CORNER = 14.0
GAP = 0.028


def _segment(a0: float, a1: float) -> str:
    """SVG path ``d`` for one donut segment with rounded corners + a gap.

    Insets each end by :data:`GAP` (so neighbours don't touch) and fillets
    all four corners with a :data:`CORNER`-radius quarter arc, drawn
    clockwise: outer arc → outer/end fillet → radial in → inner/end
    fillet → inner arc back → inner/start fillet → radial out →
    outer/start fillet.
    """
    a0 += GAP
    a1 -= GAP
    cr = CORNER
    dao = cr / R_OUT  # angular back-off for a corner at the outer radius
    dai = cr / R_IN
    seg: List[str] = []
    x, y = _pt(CX, CY, R_OUT, a0 + dao)
    seg.append(f"M{x:.2f},{y:.2f}")
    x, y = _pt(CX, CY, R_OUT, a1 - dao)
    large = 1 if (a1 - dao) - (a0 + dao) > math.pi else 0
    seg.append(f"A{R_OUT},{R_OUT} 0 {large} 1 {x:.2f},{y:.2f}")
    x, y = _pt(CX, CY, R_OUT - cr, a1)
    seg.append(f"A{cr},{cr} 0 0 1 {x:.2f},{y:.2f}")
    x, y = _pt(CX, CY, R_IN + cr, a1)
    seg.append(f"L{x:.2f},{y:.2f}")
    x, y = _pt(CX, CY, R_IN, a1 - dai)
    seg.append(f"A{cr},{cr} 0 0 1 {x:.2f},{y:.2f}")
    x, y = _pt(CX, CY, R_IN, a0 + dai)
    large = 1 if (a1 - dai) - (a0 + dai) > math.pi else 0
    seg.append(f"A{R_IN},{R_IN} 0 {large} 0 {x:.2f},{y:.2f}")
    x, y = _pt(CX, CY, R_IN + cr, a0)
    seg.append(f"A{cr},{cr} 0 0 1 {x:.2f},{y:.2f}")
    x, y = _pt(CX, CY, R_OUT - cr, a0)
    seg.append(f"L{x:.2f},{y:.2f}")
    x, y = _pt(CX, CY, R_OUT, a0 + dao)
    seg.append(f"A{cr},{cr} 0 0 1 {x:.2f},{y:.2f}")
    seg.append("Z")
    return " ".join(seg)


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    centre_label: Optional[str] = None,
    description: str = "",
    colors: Optional[Dict[str, str]] = None,
) -> str:
    """Assemble the full speaking-time donut as an SVG string.

    Parameters
    ----------
    data : list of dict, optional
        Rows with ``name`` (str) and ``seconds`` (numeric) keys, one per
        speaker. Defaults to :data:`DEMO_DATA`.
    mode : str, optional
        Interactivity mode passed to :func:`_interactive.fullscreen_control`
        (``"self-contained"`` / ``"external"`` / ``"static"``). Defaults to
        ``"self-contained"``.
    accessibility : str, optional
        Palette accessibility level passed to :func:`_style.load_palette`
        (``"universal"`` default, plus ``"high-contrast"``, ``"monochrome"``,
        ``"deuteranopia"``, ``"protanopia"`` and ``"tritanopia"``). Wired
        through the ``--accessibility`` CLI flag by :func:`main`.
    theme : str, optional
        Visual theme: ``"corporate"`` (default, Roboto -- byte-identical to
        the pre-theme render) or ``"academic"`` (LaTeX-style Latin Modern).
        See :func:`sprezzature_figures.fonts.chrome_stack_for_theme`.
    title, subtitle : str, optional
        The headline and the line under it. ``None`` (default) prints
        :data:`TITLE` / :data:`SUBTITLE`, which describe the demo rows; ``""``
        prints nothing, which is what ``make_figure`` asks for over caller data.
    description : str, optional
        What a screen reader is told about the figure. Empty (default) composes the
        English description below from the data; a host whose page is in another language
        passes its own.
    centre_label : str, optional
        The caption under the total in the middle of the ring. Defaults to
        :data:`CENTRE_LABEL`; pass the host page's own wording to keep the figure
        in the language of the document it sits in.
    colors : dict of str to str, optional
        The host page's own ``{name: "#RRGGBB"}`` mapping, for a figure embedded
        where each participant already carries a colour (a transcript view, a
        speaker legend): matching them is what makes the figure read as part of
        the page rather than as a picture pasted into it. A name absent from the
        mapping keeps its position in the house sequence, so a partial mapping is
        safe, and the OS-adaptive contrast overrides are derived from whatever
        hues end up being used.
    """
    speakers = data if data else DEMO_DATA
    is_demo = not data
    slice_colors = _slice_colors(accessibility, n=len(speakers), theme=theme)
    if colors:
        slice_colors = [
            colors.get(str(spk["name"]), house)
            for spk, house in zip(speakers, slice_colors, strict=True)
        ]
    total = sum(int(s["seconds"]) for s in speakers)

    # Accessible name + description. Every slice is also labelled outside
    # the ring with its speaker's name, duration and share, so identity is
    # never carried by colour alone — it survives colour-blindness and
    # greyscale. The description names the speakers in order so a screen
    # reader conveys the same ranking a sighted reader sees.
    ranked = ", ".join(
        f"{s['name']} {_mmss(int(s['seconds']))} "
        f"({round(100 * int(s['seconds']) / total)} %)"
        for s in speakers
    )
    # Built from the rows, not from the demo: this text used to state a forty-minute
    # round table and a 40:00 centre whatever it was given, so a screen reader was told
    # the wrong duration on every real recording. (It was also half-translated
    # mid-sentence.) One language, and every number taken from the data.
    a11y_title = title if title is not None else TITLE
    a11y_desc = description or (
        f"Donut of speaking time per participant over {_mmss(total)} of recording. "
        "Each slice is one participant, labelled outside the ring with a name, a "
        f"duration (mm:ss) and a share of the total: {ranked}. The centre shows the "
        f"total, {_mmss(total)}." + (" Illustrative data." if is_demo else "")
    )

    # None means "the caller said nothing, print the demo chrome"; "" means "the caller
    # said: print nothing". `or` would collapse the two and resurrect the demo headline
    # over caller data, which is exactly what make_figure blanks it to avoid.
    title = TITLE if title is None else title
    subtitle = SUBTITLE if subtitle is None else subtitle
    centre_label = CENTRE_LABEL if centre_label is None else centre_label

    parts: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family="{chrome_stack_for_theme(theme)}" role="img" '
        f'aria-labelledby="st-title st-desc">',
        f'<title id="st-title">{xml_escape(a11y_title)}</title>',
        f'<desc id="st-desc">{xml_escape(a11y_desc)}</desc>',
        f'<rect width="{W}" height="{H}" fill="#FFFFFF"/>',
        # Title block.
        f'<text x="60" y="66" font-size="30" font-weight="700" fill="{INK}">'
        f"{xml_escape(title)}</text>",
        f'<text x="60" y="98" font-size="18" fill="{SECONDARY}">'
        f"{xml_escape(subtitle)}</text>",
    ]

    # OS-adaptive overrides (additive, all inside @media so the default render
    # is byte-for-byte unchanged). Each slice carries a stable ``.slice-i``
    # class as an @media hook: under prefers-contrast the slice fills deepen to
    # their high-contrast hues, and under forced colours the ring drops to
    # system-palette line art — legitimate here because every slice is also
    # labelled outside the ring (name, duration, share), so identity is carried
    # by the labels, not by colour.
    slice_series = {f".slice-{i}": color for i, color in enumerate(slice_colors)}
    parts.append(
        "<style>\n"
        + os_adaptive_style(
            slice_series,
            role="fill",
            forced=True,
            forced_keyword="Canvas",
            extra_forced=".slice{stroke:CanvasText;stroke-width:2;}",
        )
        + os_dark_style()
        + ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + foreground_tip_css(len(speakers))
        + "@media (prefers-reduced-motion: reduce){.tip{transition:none}}"
        + "\n</style>"
    )

    # Arcs start at the top (−90°) and run clockwise.
    angle = -math.pi / 2
    labels: List[str] = []
    # Every slice's bubble is queued into `bubbles` and appended once, after
    # every slice is drawn, rather than right next to its own slice: SVG has
    # no z-index, so a bubble drawn in place would be covered by any slice
    # drawn afterward, no matter which one is hovered.
    bubbles: List[str] = []
    # (x, measured width, anchor) per label drawn outside the ring, for _fit_canvas.
    side_labels: List[tuple] = []
    ranked_names = [s["name"] for s in sorted(speakers, key=lambda s: -int(s["seconds"]))]
    for i, (spk, color) in enumerate(zip(speakers, slice_colors, strict=True)):
        secs = int(spk["seconds"])
        frac = secs / total
        a0, a1 = angle, angle + 2 * math.pi * frac
        angle = a1
        rank = ranked_names.index(spk["name"]) + 1
        slice_tip = f"{spk['name']}: {_mmss(secs)} ({round(100 * secs / total)}%)"
        parts.append(
            f'<path id="hit-{i}" class="slice slice-{i} hit" tabindex="0" d="{_segment(a0, a1)}" fill="{color}" '
            f'role="img" aria-label="{xml_escape(slice_tip)}"/>'
        )
        mid_pt_x, mid_pt_y = _pt(CX, CY, (R_OUT + R_IN) / 2.0, (a0 + a1) / 2.0)
        bubbles.append(
            tooltip_bubble(
                mid_pt_x, mid_pt_y - 14,
                [spk["name"], f"{_mmss(secs)} · {round(100 * secs / total)}%", f"#{rank} of {len(speakers)} speakers"],
                anchor="middle", canvas_w=W, canvas_h=H,
                ink=INK, secondary=SECONDARY, border=LEADER,
                elem_id=f"tip-{i}",
            )
        )

        # Side-aware outside annotation with a thin leader.
        mid = (a0 + a1) / 2
        cos_m = math.cos(mid)
        rx, ry = _pt(CX, CY, R_OUT + 6, mid)
        ex, ey = _pt(CX, CY, R_OUT + 30, mid)
        if cos_m > 0.25:
            tx, anchor = ex + 14, "start"
            hx = tx
        elif cos_m < -0.25:
            tx, anchor = ex - 14, "end"
            hx = tx
        else:
            tx, anchor = ex, "middle"
            hx = ex
        pct = round(100 * secs / total)
        value_line = f"{_mmss(secs)} · {pct}%"
        # Measured with the same table the checker uses, so the canvas and the check agree.
        side_labels.append((tx, text_width(spk["name"], 19), anchor))
        side_labels.append((tx, text_width(value_line, 16), anchor))
        labels.append(
            f'<polyline points="{rx:.1f},{ry:.1f} {ex:.1f},{ey:.1f} {hx:.1f},{ey:.1f}" '
            f'fill="none" stroke="{LEADER}" stroke-width="1.4"/>'
            f'<text x="{tx:.1f}" y="{ey - 4:.1f}" font-size="19" font-weight="700" '
            f'fill="{INK}" text-anchor="{anchor}">{spk["name"]}</text>'
            f'<text x="{tx:.1f}" y="{ey + 18:.1f}" font-size="16" '
            f'fill="{SECONDARY}" text-anchor="{anchor}">{_mmss(secs)} · {pct}%</text>'
        )

    parts.extend(labels)
    parts.extend(bubbles)

    # Centre: total running time — the headline number.
    parts.append(
        f'<text x="{CX}" y="{CY - 4}" font-size="52" font-weight="700" '
        f'fill="{INK}" text-anchor="middle">{_mmss(total)}</text>'
    )
    parts.append(
        f'<text x="{CX}" y="{CY + 30}" font-size="19" fill="{SECONDARY}" '
        f'text-anchor="middle">{xml_escape(centre_label)}</text>'
    )
    parts.append(fullscreen_control(W, H, mode))
    parts.append("</svg>")
    svg = "".join(parts)
    return _fit_canvas(svg, side_labels)


#: Clearance kept between a side label and the canvas edge, as a share of the label's own
#: measured width plus a flat margin. Proportional because the per-character width table
#: is an estimate and its error grows with the string: measured on "Général Dominique
#: Trinquand" in the 19 px bold face, the table was ~7 % short, which was enough to put the
#: capital's stem outside a canvas the table said it cleared by 16 px.
LABEL_CLEARANCE_RATIO: float = 0.10
LABEL_CLEARANCE_FLAT: float = 24.0


def _fit_canvas(svg: str, side_labels: List[tuple]) -> str:
    """Widen the canvas so no side label is cut, keeping every coordinate as drawn.

    The ring, its leaders and its labels are laid out against a fixed 1120-wide canvas,
    which is right until a participant has a long name: the outermost label then runs off
    the edge and the capital is clipped. Rather than move the drawing (every coordinate,
    the tooltips, the fullscreen control), the viewBox is allowed to start left of zero and
    end right of ``W``, so the picture is unchanged and the frame grows around it.

    Parameters
    ----------
    svg : str
        The assembled document, whose root still carries the nominal ``W`` x ``H``.
    side_labels : list of tuple
        ``(x, width, anchor)`` for every label drawn outside the ring.

    Returns
    -------
    str
        The same document, with the root ``viewBox`` / ``width`` widened when needed.
    """
    left, right = 0.0, float(W)
    for x, width, anchor in side_labels:
        start = x - width if anchor == "end" else (x - width / 2 if anchor == "middle" else x)
        clearance = width * LABEL_CLEARANCE_RATIO + LABEL_CLEARANCE_FLAT
        left = min(left, start - clearance)
        right = max(right, start + width + clearance)
    if left >= 0 and right <= W:
        return svg
    total = right - left
    svg = svg.replace(
        f'width="{W}" height="{H}" viewBox="0 0 {W} {H}"',
        f'width="{total:.0f}" height="{H}" viewBox="{left:.0f} 0 {total:.0f} {H}"',
        1,
    )
    # The background rectangle has to grow with the frame, or the widened strip renders
    # transparent (black, once flattened). Its width and height stay equal to the root's,
    # which is how :mod:`sprezzature_figures.darkmode` recognises a full-canvas background
    # and drops it.
    return svg.replace(
        f'<rect width="{W}" height="{H}" fill="#FFFFFF"/>',
        f'<rect x="{left:.0f}" y="0" width="{total:.0f}" height="{H}" fill="#FFFFFF"/>',
        1,
    )


def make_speaking_time(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: "Path | str | None" = None,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    centre_label: Optional[str] = None,
    description: str = "",
    colors: Optional[Dict[str, str]] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render the speaking-time donut and write it to ``out``.

    The standard ``make_<kind>`` entry the figure registry dispatches to, so
    ``make-figure speaking_time`` and the Studio behave like every other figure.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with ``name`` (str) and ``seconds`` (numeric) keys, one per
        speaker. Defaults to :data:`DEMO_DATA`.
    out : Path, str, or None
        Output path (.svg). Defaults to
        ``assets/svg-examples/speaking_time.svg``.
    title, subtitle : str, optional
        The headline and the line under it. ``None`` keeps :data:`TITLE` /
        :data:`SUBTITLE` (written for the demo rows), ``""`` prints nothing.
    centre_label : str, optional
        Caption under the total, in the host's language. Forwarded to :func:`build_svg`.
    colors : dict of str to str, optional
        The host page's ``{name: colour}`` mapping. Forwarded to :func:`build_svg`.
    mode, accessibility : str
        Forwarded to :func:`build_svg`.
    theme : str, optional
        Visual theme. Forwarded to :func:`build_svg`.
    """
    svg = build_svg(data, mode=mode, accessibility=accessibility, theme=theme,
                    title=title, subtitle=subtitle, centre_label=centre_label,
                    description=description, colors=colors)
    dest = Path(out) if out else svg_example_path(__file__, "speaking_time")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """Render the speaking-time donut to SVG (and a companion PNG)."""
    parser = argparse.ArgumentParser(description="Render the speaking-time SVG (and a PNG companion).")
    parser.add_argument(
        "--mode",
        choices=("self-contained", "external", "static"),
        default="self-contained",
        help="interactivity mode of the emitted SVG (default: self-contained)",
    )
    parser.add_argument(
        "--accessibility",
        choices=("universal", "high-contrast", "monochrome", "deuteranopia", "protanopia", "tritanopia"),
        default="universal",
        help="palette accessibility level (default: universal, the CVD-safe standard)",
    )
    parser.add_argument(
        "--theme",
        choices=("corporate", "academic"),
        default="corporate",
        help="visual theme: corporate (default, Roboto) or academic (LaTeX-style Latin Modern)",
    )
    args = parser.parse_args()
    svg = build_svg(mode=args.mode, accessibility=args.accessibility, theme=args.theme)
    out_svg = svg_example_path(__file__, "speaking_time")
    write_svg(out_svg, svg, theme=args.theme)
    write_raster_companions(svg, __file__, "speaking_time")


if __name__ == "__main__":
    main()
