"""
make_speaking_time — a speaker-diarisation "who spoke, and for how long" donut.

Turns a diarisation result (one row per speaker, with a talk-time in
seconds) into a large, clean donut where each slice is one speaker. Each
slice is annotated **outside the ring** with the speaker's name, the
human-readable duration (``mm:ss``) and its share of the conversation
(``%``); a thin leader line ties each annotation to its arc, and labels
are side-aware (right labels left-aligned, left labels right-aligned) so
the spacing stays harmonious all the way round. The hole carries the
total running time — the headline number.

Pure-Python, hand-built SVG string (no Vega, no matplotlib) so the label
geometry can be placed exactly. Big canvas by design.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
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
from _svg import point_on_circle, xml_escape  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme  # noqa: E402

# ------------------------------------------------------------------
# Illustrative diarisation output — a 40-minute round-table. Talk-time
# is whole seconds so ``mm:ss`` and ``%`` stay mutually consistent; the
# four values sum to 2400 s = 40:00 with clean integer percentages.
#
# Row-record demo data: one row per speaker, the contract's
# ``list[dict[str, Any]]`` shape (``name`` + ``seconds``).
# ------------------------------------------------------------------
DEMO_DATA: List[Dict[str, Any]] = [
    {"name": "Alice Nguyen", "seconds": 984},   # 16:24 · 41 %
    {"name": "Marc Dubois", "seconds": 648},     # 10:48 · 27 %
    {"name": "Sofia Rossi", "seconds": 432},     # 07:12 · 18 %
    {"name": "Karim Haddad", "seconds": 336},    # 05:36 · 14 %
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
    """
    speakers = data if data else DEMO_DATA
    slice_colors = _slice_colors(accessibility, n=len(speakers), theme=theme)
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
    a11y_title = "Qui a parlé, et combien de temps"
    a11y_desc = (
        "Anneau (donut) du temps de parole par intervenant sur une table "
        "ronde de 40 minutes. Chaque part est un intervenant, étiquetée à "
        "l'extérieur de l'anneau avec son nom, sa durée (mm:ss) et sa part "
        f"du total en pourcentage : {ranked}. Le centre affiche le temps "
        "total, 40:00. Données illustratives."
    )

    parts: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family="{chrome_stack_for_theme(theme)}" role="img" '
        f'aria-labelledby="st-title st-desc">',
        f'<title id="st-title">{xml_escape(a11y_title)}</title>',
        f'<desc id="st-desc">{xml_escape(a11y_desc)}</desc>',
        f'<rect width="{W}" height="{H}" fill="#FFFFFF"/>',
        # Title block.
        f'<text x="60" y="66" font-size="30" font-weight="700" fill="{INK}">'
        f"Qui a parlé, et combien de temps</text>",
        f'<text x="60" y="98" font-size="18" fill="{SECONDARY}">'
        f"Temps de parole par intervenant · table ronde de 40 min</text>",
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
        + "\n</style>"
    )

    # Arcs start at the top (−90°) and run clockwise.
    angle = -math.pi / 2
    labels: List[str] = []
    for i, (spk, color) in enumerate(zip(speakers, slice_colors, strict=True)):
        secs = int(spk["seconds"])
        frac = secs / total
        a0, a1 = angle, angle + 2 * math.pi * frac
        angle = a1
        parts.append(f'<path class="slice slice-{i}" d="{_segment(a0, a1)}" fill="{color}"/>')

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
        labels.append(
            f'<polyline points="{rx:.1f},{ry:.1f} {ex:.1f},{ey:.1f} {hx:.1f},{ey:.1f}" '
            f'fill="none" stroke="{LEADER}" stroke-width="1.4"/>'
            f'<text x="{tx:.1f}" y="{ey - 4:.1f}" font-size="19" font-weight="700" '
            f'fill="{INK}" text-anchor="{anchor}">{spk["name"]}</text>'
            f'<text x="{tx:.1f}" y="{ey + 18:.1f}" font-size="16" '
            f'fill="{SECONDARY}" text-anchor="{anchor}">{_mmss(secs)} · {pct}%</text>'
        )

    parts.extend(labels)

    # Centre: total running time — the headline number.
    parts.append(
        f'<text x="{CX}" y="{CY - 4}" font-size="52" font-weight="700" '
        f'fill="{INK}" text-anchor="middle">{_mmss(total)}</text>'
    )
    parts.append(
        f'<text x="{CX}" y="{CY + 30}" font-size="19" fill="{SECONDARY}" '
        f'text-anchor="middle">temps total</text>'
    )
    parts.append(fullscreen_control(W, H, mode))
    parts.append("</svg>")
    return "".join(parts)


def make_speaking_time(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: "Path | str | None" = None,
    title: str = "",
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
    title : str, optional
        Accepted for signature parity; the figure's headline is in French
        by design (unused).
    mode, accessibility : str
        Forwarded to :func:`build_svg`.
    theme : str, optional
        Visual theme. Forwarded to :func:`build_svg`.
    """
    _ = title
    svg = build_svg(data, mode=mode, accessibility=accessibility, theme=theme)
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
