"""
make_interruption-matrix — a directed "Qui coupe qui ?" interruption heatmap.

Turns a set of directed interruption counts (speaker B cut speaker A, N times)
into an asymmetric speaker×speaker matrix: each **column** is an interrupter
(who cuts the parole), each **row** is the interrupted (who gets cut). A cell
``(row A, col B)`` is how many times B cut A, filled in B's speaker colour with
opacity proportional to the count, so a dark column reads at a glance as a big
interrupter and a dark row as someone who gets cut a lot. A right ``Σ`` strip
totals each row (times interrupted); a bottom ``Σ`` strip totals each column
(cuts made). The diagonal is inert: nobody cuts themselves.

Beyond the native per-cell tooltip, the figure carries a **crosshair hover**
(self-contained mode): pointing at any cell lights that interrupter's whole
column and that interrupted's whole row, totals included, and dims the rest,
so "everyone X cut" and "everyone who cut X" light up together. Hovering a name
header does the same for that speaker. It is pure enhancement: the numbers are
printed in every cell, so the figure reads fully as a static image too.

Pure-Python, hand-built SVG string (no Vega, no matplotlib) so the grid geometry
and the hover wiring can be placed exactly.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

from _interactive import fullscreen_control
from _render import render_cli, svg_example_path, write_svg
from _style import INK, SECONDARY, leveled_colors, os_adaptive_style, os_dark_style
from _svg import tooltip_bubble, xml_escape
from sprezzature_figures.fonts import chrome_stack_for_theme

# ------------------------------------------------------------------
#  — the "No Priors" episode with Andrej Karpathy
# (host duo Sarah Guo + Elad Gil). One row per directed pair: the
# interrupter cut the interrupted `count` times. The union of names
# is the speaker set; the matrix is built from these pairs.
# ------------------------------------------------------------------
DEMO_DATA: List[Dict[str, Any]] = [
    {"interrupter": "Sarah Guo", "interrupted": "Andrej Karpathy", "count": 20},
    {"interrupter": "Andrej Karpathy", "interrupted": "Sarah Guo", "count": 13},
    {"interrupter": "Elad Gil", "interrupted": "Andrej Karpathy", "count": 10},
    {"interrupter": "Andrej Karpathy", "interrupted": "Elad Gil", "count": 8},
    {"interrupter": "Sarah Guo", "interrupted": "Elad Gil", "count": 2},
    {"interrupter": "Elad Gil", "interrupted": "Sarah Guo", "count": 2},
]

HAIRLINE = "#ECECEC"
IDLE = "#F5F5F7"
ZERO = "#FBFBFD"
DIAG_LINE = "#D2D2D7"
FONT = "Roboto, system-ui, sans-serif"

# Geometry — a generous, rounded grid. The grid's left origin and the canvas
# width are computed per figure (they depend on the speaker count and the
# subtitle length), so only the fixed metrics live here.
CELL = 78
GUTTER = 156   # room for the right-aligned row names + colour chip
TOP = 236      # room for title, subtitle and the rotated column names
MARGIN = 48
PAD_B = 86     # bottom band for the Σ row + the one-line "bilan"
SUBTITLE = "Colonne = coupe la parole · ligne = se fait couper · case = nombre de coupures"
TITLE = "Qui coupe qui ?"


def _text_w(text: str, size: float) -> float:
    """A generous estimate of a Roboto string's rendered width, in px.

    Only used to size the canvas so the centred title/subtitle never clip;
    erring wide just leaves a little more air, never an overflow.
    """
    return sum(0.60 if c.isupper() else 0.53 for c in text) * size


#: Speaker hues — a fixed, deep wheel chosen to satisfy two house standards at
#: once. (1) WCAG: every hue is dark enough to clear AA (>= 4.5:1) as name text
#: on the white background, so identity labels stay legible. (2) CVD: the hues
#: are ordered so the most-used first few stay separable under protanopia,
#: deuteranopia and tritanopia (teal / violet / rust / green lead, red and
#: amber later). Because they are literal hexes (not palette-name lookups) the
#: wheel can never KeyError on any palette, and :func:`_style.leveled_colors`
#: still remaps them per accessibility level below. Cycles past seven speakers.
_WHEEL: List[str] = [
    "#0e7490",  # teal-700
    "#6d28d9",  # violet-700
    "#c2410c",  # rust-700
    "#15803d",  # green-700
    "#b91c1c",  # red-700
    "#a16207",  # amber-700
    "#be185d",  # pink-700
]


def _person_colors(order: List[str], accessibility: str = "universal") -> Dict[str, str]:
    """Map each speaker to a stable, CVD-safe, contrast-safe hue.

    The same speaker keeps the same colour across renders (and cycles past the
    wheel length). :func:`_style.leveled_colors` applies the requested
    accessibility level (identity at ``"universal"``), so ``--accessibility
    deuteranopia`` and friends remap the wheel when sprezzature-colors is
    co-installed.
    """
    base = {name: _WHEEL[i % len(_WHEEL)] for i, name in enumerate(order)}
    return leveled_colors(base, accessibility)


def _aggregate(data: List[Dict[str, Any]]) -> Tuple[List[str], Dict[str, Dict[str, int]], Dict[str, int], Dict[str, int]]:
    """Fold the directed pairs into an ordered matrix and its margins.

    Returns ``(order, m, made, got)`` where ``m[interrupted][interrupter]`` is
    the count, ``made[b]`` the column total (cuts B made) and ``got[a]`` the row
    total (times A was cut). Speakers are ordered by total involvement
    (made + got) descending, so the most active talker leads the axis; ties fall
    back to cuts made, then name, for a fully deterministic order.
    """
    names: List[str] = []
    for row in data:
        for key in ("interrupter", "interrupted"):
            who = str(row[key])
            if who not in names:
                names.append(who)

    m = {a: {b: 0 for b in names} for a in names}
    for row in data:
        b, a = str(row["interrupter"]), str(row["interrupted"])
        if a == b:
            continue  # a self-cut is meaningless; drop it
        m[a][b] += int(row.get("count", 1))

    made = {b: sum(m[a][b] for a in names) for b in names}
    got = {a: sum(m[a][b] for b in names) for a in names}
    order = sorted(names, key=lambda s: (-(made[s] + got[s]), -made[s], s))
    return order, m, made, got


def _hover_style() -> str:
    """CSS for the crosshair hover: cell pop, row/column highlight, dim rest."""
    return (
        ".cell,.head,.sig{transition:opacity .18s ease;}"
        ".box{transition:transform .18s ease,filter .18s ease;"
        "transform-box:fill-box;transform-origin:center;}"
        ".cell:hover .box{transform:scale(1.07);"
        "filter:drop-shadow(0 6px 14px rgba(0,0,0,.20));}"
        "svg.cross .cell,svg.cross .head,svg.cross .sig{opacity:.24;}"
        "svg.cross .lit{opacity:1;}"
        "svg.cross .lit .box{filter:saturate(1.2);}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        ".hit:hover+.tip,.hit:focus+.tip{opacity:1}"
        "@media (prefers-reduced-motion:reduce){"
        ".cell,.head,.sig,.box{transition:none;}"
        ".cell:hover .box{transform:none;}.tip{transition:none}}"
    )


def _hover_script() -> str:
    """Vanilla-JS crosshair: light the hovered cell's row + column, dim the rest.

    Wired only in self-contained mode. Inert when the figure is embedded as an
    ``<img>`` (scripts never run there) — the static grid still carries every
    number, so nothing is lost.
    """
    return (
        '<script><![CDATA['
        "(function(){"
        "var svg=document.currentScript.parentNode;"
        "var nodes=svg.querySelectorAll('[data-r],[data-c]');"
        "function enter(el){"
        "var r=el.getAttribute('data-r'),c=el.getAttribute('data-c');"
        "svg.classList.add('cross');"
        "nodes.forEach(function(o){"
        "var or=o.getAttribute('data-r'),oc=o.getAttribute('data-c');"
        "if((r!==null&&or===r)||(c!==null&&oc===c)){o.classList.add('lit');}"
        "else{o.classList.remove('lit');}});}"
        "function leave(){svg.classList.remove('cross');"
        "nodes.forEach(function(o){o.classList.remove('lit');});}"
        "nodes.forEach(function(el){"
        "el.addEventListener('pointerenter',function(){enter(el);});"
        "el.addEventListener('pointerleave',leave);});"
        "})();"
        ']]></script>'
    )


def build_svg(
    data: List[Dict[str, Any]] | None = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full "Qui coupe qui ?" interruption matrix as an SVG string.

    Parameters
    ----------
    data : list of dict or None
        Directed pairs ``{"interrupter", "interrupted", "count"}``. Defaults to
        :data:`DEMO_DATA` (the No Priors episode). The speaker set is the union
        of the names; the matrix and its margins are derived by :func:`_aggregate`.
    mode : str, optional
        Interactivity mode forwarded to :func:`_interactive.fullscreen_control`
        and gating the crosshair-hover script (``"self-contained"`` default,
        plus ``"external"`` / ``"static"``).
    accessibility : str, optional
        Palette accessibility level passed to :func:`_style.load_palette`
        (``"universal"`` default, plus ``"high-contrast"``, ``"monochrome"``,
        ``"deuteranopia"``, ``"protanopia"``, ``"tritanopia"``).
    theme : str, optional
        Visual theme: ``"corporate"`` (default, Roboto -- byte-identical to
        the pre-theme render) or ``"academic"`` (LaTeX-style Latin Modern).
        See :func:`sprezzature_figures.fonts.chrome_stack_for_theme`.
    """
    rows = data if data else DEMO_DATA
    order, m, made, got = _aggregate(rows)
    n = len(order)
    color_of = _person_colors(order, accessibility)
    hi = max([v for r in m.values() for v in r.values()] + [1])

    # Centre the content block (row-label gutter + the (n+1)-wide grid) inside a
    # canvas wide enough for the centred subtitle, so nothing clips and the
    # composition stays balanced whatever the speaker count.
    grid_w = (n + 1) * CELL
    content_w = GUTTER + grid_w
    inner_w = max(content_w, _text_w(SUBTITLE, 16), _text_w(TITLE, 30))
    # Round the canvas box to 2dp: `_text_w` accumulates float error (e.g.
    # 758.5600000000001) that would otherwise leak, verbatim, into the root
    # <svg width>/<viewBox> — harmless to rendering but ugly in the markup.
    w = round(inner_w + 2 * MARGIN, 2)
    top = TOP
    h = round(top + (n + 1) * CELL + PAD_B, 2)
    left = MARGIN + (inner_w - content_w) / 2 + GUTTER  # x of the grid's left edge

    def cx(c: float) -> float:
        return left + c * CELL

    def cy(r: float) -> float:
        return top + r * CELL

    # Accessible name + description: name the standout interrupter, the most
    # interrupted, and the single heaviest exchange, so a screen reader gets the
    # same headline a sighted reader reads off the dark column, dark row and
    # darkest cell.
    top_cutter = max(order, key=lambda s: made[s])
    top_target = max(order, key=lambda s: got[s])
    hot = max(((a, b, m[a][b]) for a in order for b in order if a != b), key=lambda t: t[2])
    a11y_desc = (
        f"Matrice orientée des interruptions entre {n} intervenants. Chaque "
        "colonne est un intervenant qui coupe la parole, chaque ligne un "
        "intervenant qui se fait couper ; une case indique combien de fois la "
        "personne en colonne a coupé la personne en ligne, teintée dans la "
        "couleur de l'interrupteur avec une opacité proportionnelle au nombre. "
        "La diagonale est vide. La colonne de droite totalise les interruptions "
        "subies par ligne, la ligne du bas les interruptions commises par "
        f"colonne. {xml_escape(top_cutter)} coupe le plus ({made[top_cutter]} "
        f"fois), {xml_escape(top_target)} se fait couper le plus "
        f"({got[top_target]} fois) ; l'échange le plus fréquent est "
        f"{xml_escape(hot[1])} coupant {xml_escape(hot[0])} {hot[2]} fois. "
        "Données illustratives."
    )

    p: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" font-family="{chrome_stack_for_theme(theme)}" role="img" '
        f'aria-labelledby="im-title im-desc">',
        f'<title id="im-title">{xml_escape(TITLE)}</title>',
        f'<desc id="im-desc">{a11y_desc}</desc>',
    ]

    # OS-adaptive overrides: dark-mode, plus the hover CSS. Each speaker's
    # column cells carry a ``.spk-i`` hook so prefers-contrast can deepen the
    # hue; identity never rests on colour alone (every cell prints its count and
    # both axes are named), so this stays accessible.
    spk_series = {f".spk-{i}": color_of[name] for i, name in enumerate(order)}
    p.append(
        "<style>\n"
        + _hover_style()
        + os_adaptive_style(spk_series, role="fill", forced=True, forced_keyword="Canvas")
        + os_dark_style()
        + "\n</style>"
    )

    p.append(f'<rect width="{w}" height="{h}" fill="#FFFFFF"/>')
    p.append(
        f'<text x="{w / 2:.1f}" y="62" text-anchor="middle" font-size="30" font-weight="700" '
        f'fill="{INK}">{xml_escape(TITLE)}</text>'
    )
    p.append(
        f'<text x="{w / 2:.1f}" y="92" text-anchor="middle" font-size="16" fill="{SECONDARY}">'
        f"{xml_escape(SUBTITLE)}</text>"
    )

    idx = {name: i for i, name in enumerate(order)}

    # Column headers (interrupter), rotated so long names never collide, each a
    # crosshair anchor for its column.
    for c, b in enumerate(order):
        xc = cx(c) + CELL / 2
        col = color_of[b]
        p.append(
            f'<g class="head" data-c="{c}" transform="translate({xc:.1f},{top - 14}) rotate(-38)">'
            f'<circle cx="-8" cy="-4" r="4" fill="{col}"/>'
            f'<text x="4" y="0" text-anchor="start" font-size="14" font-weight="600" fill="{col}">'
            f'{xml_escape(b)}</text></g>'
        )
    p.append(
        f'<text x="{cx(n) + CELL / 2:.1f}" y="{top - 16}" text-anchor="middle" font-size="14" '
        f'font-weight="700" fill="{INK}">Σ subies</text>'
    )

    # Rows.
    for r, a in enumerate(order):
        yc = cy(r) + CELL / 2
        rcol = color_of[a]
        p.append(
            f'<g class="head" data-r="{r}">'
            f'<text x="{left - 22:.1f}" y="{yc:.1f}" text-anchor="end" dominant-baseline="central" '
            f'font-size="14" font-weight="600" fill="{rcol}">{xml_escape(a)}</text>'
            f'<circle cx="{left - 12:.1f}" cy="{yc:.1f}" r="4" fill="{rcol}"/></g>'
        )
        for c, b in enumerate(order):
            x, y = cx(c), cy(r)
            if a == b:  # diagonal — inert, no self-cuts
                p.append(
                    f'<g class="cell" data-r="{r}" data-c="{c}">'
                    f'<rect class="box" x="{x + 3}" y="{y + 3}" width="{CELL - 6}" height="{CELL - 6}" '
                    f'rx="12" fill="{IDLE}"/>'
                    f'<line x1="{x + CELL * 0.34:.0f}" y1="{y + CELL * 0.66:.0f}" '
                    f'x2="{x + CELL * 0.66:.0f}" y2="{y + CELL * 0.34:.0f}" '
                    f'stroke="{DIAG_LINE}" stroke-width="1.6"/></g>'
                )
                continue
            v = m[a][b]
            norm = v / hi
            # Opacity encodes magnitude, but capped at 0.66 so the tint never
            # gets so dark that the INK cell number drops below WCAG AA (4.5:1);
            # the count is always printed in INK, verified >= 4.76:1 across the
            # whole wheel and opacity range. So contrast never rests on the
            # colour switch, and the number is legible on every cell.
            op = 0.0 if v == 0 else 0.14 + 0.52 * norm
            fill = ZERO if v == 0 else color_of[b]
            klass = "cell hit" if v == 0 else f"cell hit spk-{idx[b]}"
            tip = f"{xml_escape(b)} coupe {xml_escape(a)} × {v}" if v else f"{xml_escape(b)} ne coupe jamais {xml_escape(a)}"
            g = [
                f'<g class="{klass}" tabindex="0" data-r="{r}" data-c="{c}"><title>{tip}</title>',
                f'<rect class="box" x="{x + 3}" y="{y + 3}" width="{CELL - 6}" height="{CELL - 6}" rx="12" '
                f'fill="{fill}" fill-opacity="{op:.3f}" stroke="{HAIRLINE}" stroke-width="1"/>',
            ]
            if v:
                g.append(
                    f'<text x="{x + CELL / 2:.1f}" y="{y + CELL / 2:.1f}" text-anchor="middle" '
                    f'dominant-baseline="central" font-size="19" font-weight="700" fill="{INK}" '
                    f'pointer-events="none">{v}</text>'
                )
            g.append("</g>")
            p.append("".join(g))
            bubble_lines = [f"{b} coupe {a}"]
            bubble_lines.append(f"{v} fois" if v else "jamais (0 fois)")
            if v:
                bubble_lines.append(f"{norm * 100:.0f}% de l'échange le plus intense")
            p.append(
                tooltip_bubble(
                    x + CELL / 2,
                    max(4.0, y - 84.0),
                    bubble_lines,
                    canvas_w=w,
                    canvas_h=h,
                    ink=INK,
                    secondary=SECONDARY,
                    border=HAIRLINE,
                )
            )

        # Row total Σ (times A was cut) — lights with A's row.
        xt = cx(n)
        p.append(
            f'<g class="sig" data-r="{r}">'
            f'<rect class="box" x="{xt + 3}" y="{cy(r) + 3}" width="{CELL - 6}" height="{CELL - 6}" rx="12" '
            f'fill="{IDLE}"/>'
            f'<text x="{xt + CELL / 2:.1f}" y="{cy(r) + CELL / 2:.1f}" text-anchor="middle" '
            f'dominant-baseline="central" font-size="19" font-weight="700" fill="{INK}">{got[a]}</text></g>'
        )

    # Bottom Σ row (cuts made by each column) + its header.
    yb = cy(n)
    p.append(
        f'<text x="{left - 22:.1f}" y="{yb + CELL / 2:.1f}" text-anchor="end" dominant-baseline="central" '
        f'font-size="14" font-weight="700" fill="{INK}">Σ commises</text>'
    )
    for c, b in enumerate(order):
        x = cx(c)
        p.append(
            f'<g class="sig" data-c="{c}">'
            f'<rect class="box" x="{x + 3}" y="{yb + 3}" width="{CELL - 6}" height="{CELL - 6}" rx="12" '
            f'fill="{IDLE}"/>'
            f'<text x="{x + CELL / 2:.1f}" y="{yb + CELL / 2:.1f}" text-anchor="middle" '
            f'dominant-baseline="central" font-size="19" font-weight="700" fill="{INK}">{made[b]}</text></g>'
        )

    # One-line "bilan" under the grid: the two headline reads, each in the
    # speaker's colour, so the takeaway survives even as a static thumbnail.
    by = yb + CELL + 34
    p.append(
        f'<text x="{w / 2:.1f}" y="{by:.1f}" text-anchor="middle" font-size="15" fill="{SECONDARY}">'
        f'<tspan font-weight="700" fill="{color_of[top_cutter]}">{xml_escape(top_cutter)}</tspan>'
        f" coupe le plus ({made[top_cutter]}) · "
        f'<tspan font-weight="700" fill="{color_of[top_target]}">{xml_escape(top_target)}</tspan>'
        f" se fait le plus couper ({got[top_target]})</text>"
    )

    if mode == "self-contained":
        p.append(_hover_script())
    p.append(fullscreen_control(w, h, mode))
    p.append("</svg>")
    return "".join(p)


def make_interruption_matrix(
    data: "List[Dict[str, Any]] | None" = None,
    *,
    out: "Path | str | None" = None,
    title: str = "",
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render the interruption matrix and write it to ``out``.

    The standard ``make_<kind>`` entry the figure registry dispatches to, so
    ``make-figure interruption-matrix`` and the Studio work like every other
    figure. ``data`` is directed pairs
    ``{"interrupter", "interrupted", "count"}``; omit it for the built-in demo.
    ``title`` is accepted for signature parity and unused (the headline is baked
    into the figure). ``theme`` is forwarded to :func:`build_svg`.
    """
    svg = build_svg(data=data, mode=mode, accessibility=accessibility, theme=theme)
    dest = Path(out) if out else svg_example_path(__file__, "interruption-matrix")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """Render the interruption matrix to SVG from the command line."""
    render_cli(__file__, "interruption-matrix", build_svg, description="Render the 'Qui coupe qui ?' interruption matrix.")


if __name__ == "__main__":
    main()
