#!/usr/bin/env python3
"""
make_fishbone — causes grouped toward one effect, with the evidence marked.

A spine running to the effect under investigation, major cause
categories branching off it, and the individual causes hanging from
those. Ishikawa's diagram, drawn so the output of a session is a
*ranked* list rather than a tidy picture of everything anybody said.

Where the usual fishbone goes wrong
-------------------------------------
* **Every cause is drawn the same, so the brainstorm never becomes a
  decision.** A cause someone mentioned once and a cause behind forty
  percent of the failures occupy identical twigs. Causes carry a weight
  here, the categories are ordered by their totals, and the chrome says
  which category carries most -- turning a wall of sticky notes into
  something you can act on.
* **Nothing separates what is measured from what is suspected.** The
  diagram's whole risk is that a plausible guess written in ink becomes
  a fact by Tuesday. Causes with evidence behind them are drawn solid
  and the rest dashed, and the chrome counts both.
* **The six standard categories are used by rote.** Machine, Method,
  Material and the rest are a prompt, not a schema, and forcing a
  problem into them produces empty bones and causes filed where nobody
  will look. Whatever categories the data carries are the ones drawn.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
    {"category": "Deployment", "cause": "No staging soak", "weight": 14, "evidenced": 1},
    {"category": "Deployment", "cause": "Config drift", "weight": 9, "evidenced": 1},
    {"category": "Deployment", "cause": "Friday releases", "weight": 3, "evidenced": 0},
    {"category": "Dependencies", "cause": "Payment gateway timeouts", "weight": 11,
     "evidenced": 1},
    {"category": "Dependencies", "cause": "Unpinned minor versions", "weight": 6,
     "evidenced": 1},
    {"category": "Monitoring", "cause": "Alert only on 5xx", "weight": 8, "evidenced": 1},
    {"category": "Monitoring", "cause": "No synthetic checkout", "weight": 7,
     "evidenced": 0},
    {"category": "Monitoring", "cause": "Dashboards nobody opens", "weight": 2,
     "evidenced": 0},
    {"category": "Capacity", "cause": "Connection pool too small", "weight": 5,
     "evidenced": 1},
    {"category": "Capacity", "cause": "Cold caches after deploy", "weight": 4,
     "evidenced": 0},
    {"category": "People", "cause": "One person knows the queue", "weight": 6,
     "evidenced": 0},
    {"category": "People", "cause": "Runbook out of date", "weight": 3, "evidenced": 1},
]


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Deployment carries a third of it, and two in five causes have no evidence",
    subtitle: str = "Causes of checkout incidents, grouped and weighted, with the evidenced ones drawn solid.",
    width: int = 980,
    height: int = 620,
    category: str = "category",
    cause: str = "cause",
    weight: str = "weight",
    evidenced: str = "evidenced",
    effect: str = "Checkout incidents",
    weight_label: str = "incidents",
    evidence_label: str = "evidenced",
    hunch_label: str = "a hunch",
    method_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full cause-and-effect SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        One row per cause. Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    category, cause : str
        Row keys for the cause's group and its text.
    weight : str
        Row key for how much the cause is thought to contribute. Rows
        without one count as 1, so a plain brainstorm still draws.
    evidenced : str
        Row key for whether anything measured stands behind the cause.
    effect : str
        The thing being explained, drawn at the head of the spine.
    weight_label : str
        What the weights count.
    evidence_label, hunch_label : str
        Words for a cause with evidence and one without.
    method_note, finding : str or None
        The line describing the weights, and the sentence naming the
        heaviest category; ``None`` composes each from the data.
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
        raise ValueError("a cause-and-effect diagram needs at least one cause")

    grouped: Dict[str, List[Tuple[str, float, bool]]] = {}
    for row in rows:
        grouped.setdefault(str(row[category]), []).append((
            str(row[cause]),
            float(row.get(weight, 1) or 1),
            bool(row.get(evidenced, 0)),
        ))
    for causes in grouped.values():
        causes.sort(key=lambda item: -item[1])
    totals = {name: sum(w for _, w, _ in causes) for name, causes in grouped.items()}
    names = sorted(grouped, key=lambda name: -totals[name])
    grand = sum(totals.values()) or 1.0
    backed = sum(1 for _, causes in grouped.items() for _, _, ok in causes if ok)
    counted = sum(len(causes) for causes in grouped.values())
    heaviest = names[0]

    mono_family = mono_stack_for_theme(theme)
    palette = load_palette(accessibility, theme=theme)
    spine_ink = INK
    wheel = [
        palette.get(key, fallback) for key, fallback in (
            ("Blue", "#007AFF"), ("Orange", "#FF9500"), ("Green", "#28CD41"),
            ("Purple", "#5856D6"), ("Teal", "#30B0C7"), ("Red", "#FF3B30"),
        )
    ]

    plot_x = 56.0
    plot_y = 214.0
    plot_w = width - plot_x - 196.0
    plot_h = height - plot_y - 56.0
    spine_y = plot_y + plot_h / 2.0
    head_x = plot_x + plot_w

    # Categories alternate above and below the spine, spread along it.
    above = names[0::2]
    below = names[1::2]
    lanes: Dict[str, Tuple[float, int]] = {}
    for side, members in ((-1, above), (1, below)):
        for index, name in enumerate(members):
            step = plot_w / (len(members) + 1)
            lanes[name] = (plot_x + step * (index + 0.85), side)

    method_lines = (
        [method_note] if method_note is not None
        else [
            f"{counted} causes in {len(names)} groups, weighted by {weight_label}; "
            f"groups ordered by their totals",
            f"{backed} of {counted} are {evidence_label}, drawn solid; the rest are "
            f"{hunch_label}, dashed",
        ]
    )
    said_method = " · ".join(method_lines)
    said_parts: List[str] = []
    if finding is not None:
        said_parts.append(finding)
    else:
        said_parts.append(
            f"{heaviest} carries {fmt_number(totals[heaviest] / grand * 100.0)}% of the "
            f"weight, more than any other group."
        )
        unbacked = counted - backed
        if unbacked:
            said_parts.append(
                f"{unbacked} of {counted} causes have nothing measured behind them."
            )
    said_lines: List[str] = []
    for sentence in said_parts:
        said_lines.extend(wrap_no_orphan(sentence, 106))

    parts: List[str] = []
    parts.append(
        svg_open(width, height, "fishbone-title", "fishbone-desc",
                 font_family=chrome_stack_for_theme(theme))
    )
    parts.append(f'<title id="fishbone-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="fishbone-desc">A cause-and-effect diagram for {xml_escape(effect)}: '
        f'{counted} causes in {len(names)} groups branching from a spine. '
        f'{xml_escape(said_method)}. {xml_escape(" ".join(said_parts))}</desc>'
    )
    parts.append(
        "<style>"
        ".bone{cursor:default;}"
        ".bone:hover,.bone:focus{outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + foreground_tip_css(len(names), mark_prefix="bone", tip_prefix="bonetip")
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
        method_drawn.extend(wrap_no_orphan(clause, 106))
    for line_index, text in enumerate(method_drawn[:2]):
        parts.append(
            f'<text x="40" y="{124 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(text)}</text>'
        )
    for line_index, text in enumerate(said_lines[:2]):
        parts.append(
            f'<text x="40" y="{164 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(text)}</text>'
        )

    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{spine_y:.1f}" x2="{head_x:.1f}" '
        f'y2="{spine_y:.1f}" stroke="{spine_ink}" stroke-width="2.4"/>'
    )
    parts.append(
        f'<path d="M{head_x:.1f},{spine_y - 26:.1f} L{head_x + 54:.1f},{spine_y:.1f} '
        f'L{head_x:.1f},{spine_y + 26:.1f} Z" fill="{spine_ink}" opacity="0.12"/>'
    )
    for line_index, text in enumerate(wrap_no_orphan(effect, 18)[:2]):
        parts.append(
            f'<text x="{head_x + 62:.1f}" y="{spine_y + 4 + (line_index - 0.5) * 15:.1f}" '
            f'font-size="13" font-weight="700" fill="{INK}">{xml_escape(text)}</text>'
        )

    tips: List[str] = []
    for index, name in enumerate(names):
        root_x, side = lanes[name]
        colour = wheel[index % len(wheel)]
        reach = plot_h / 2.0 - 26.0
        tip_x = root_x - reach * 0.55
        tip_y = spine_y + side * reach
        parts.append(
            f'<line x1="{root_x:.1f}" y1="{spine_y:.1f}" x2="{tip_x:.1f}" '
            f'y2="{tip_y:.1f}" stroke="{colour}" stroke-width="2.2"/>'
        )
        share = totals[name] / grand * 100.0
        parts.append(
            f'<text x="{tip_x:.1f}" y="{tip_y + (-8 if side < 0 else 16):.1f}" '
            f'font-size="13" font-weight="700" fill="{colour}" text-anchor="middle">'
            f'{xml_escape(name)} {fmt_number(share)}%</text>'
        )
        causes = grouped[name]
        for order, (text, amount, has_evidence) in enumerate(causes):
            along = (order + 1) / (len(causes) + 1)
            branch_x = root_x + (tip_x - root_x) * along
            branch_y = spine_y + (tip_y - spine_y) * along
            twig_x = branch_x + 58.0
            parts.append(
                f'<line x1="{branch_x:.1f}" y1="{branch_y:.1f}" x2="{twig_x:.1f}" '
                f'y2="{branch_y:.1f}" stroke="{colour}" stroke-width="1.4" '
                + ("" if has_evidence else 'stroke-dasharray="3 3" ')
                + 'opacity="0.85"/>'
            )
            parts.append(
                f'<text x="{twig_x + 5:.1f}" y="{branch_y + 4:.1f}" font-size="11" '
                f'fill="{INK}" opacity="{1.0 if has_evidence else 0.65}">'
                f'{xml_escape(text)} '
                f'<tspan fill="{SECONDARY}" font-family="{mono_family}" font-size="10">'
                f'{fmt_number(amount)}</tspan></text>'
            )
        parts.append(
            f'<rect id="bone-{index}" class="bone hit" tabindex="0" role="img" '
            f'aria-label="{xml_escape(name)}: {len(causes)} causes totalling '
            f'{fmt_number(totals[name])} {xml_escape(weight_label)}, '
            f'{fmt_number(share)}% of the whole" '
            f'x="{min(root_x, tip_x) - 10:.1f}" y="{min(spine_y, tip_y) - 10:.1f}" '
            f'width="{abs(tip_x - root_x) + 20:.1f}" '
            f'height="{abs(tip_y - spine_y) + 20:.1f}" fill="transparent">'
            f'<title>{xml_escape(name)}: {fmt_number(share)}%</title></rect>'
        )
        tips.append(
            tooltip_bubble(
                (root_x + tip_x) / 2.0, (spine_y + tip_y) / 2.0,
                [name,
                 f"{fmt_number(totals[name])} {weight_label} · {fmt_number(share)}%",
                 f"{sum(1 for _, _, ok in causes if ok)} of {len(causes)} "
                 f"{evidence_label}"],
                canvas_w=width, canvas_h=height, ink=INK, secondary=SECONDARY,
                border=GRIDLINE, elem_id=f"bonetip-{index}",
            )
        )

    parts.extend(tips)
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_fishbone(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[str] = None,
    title: str = "Deployment carries a third of it, and two in five causes have no evidence",
    subtitle: str = "Causes of checkout incidents, grouped and weighted, with the evidenced ones drawn solid.",
    width: int = 980,
    height: int = 620,
    category: str = "category",
    cause: str = "cause",
    weight: str = "weight",
    evidenced: str = "evidenced",
    effect: str = "Checkout incidents",
    weight_label: str = "incidents",
    evidence_label: str = "evidenced",
    hunch_label: str = "a hunch",
    method_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Write a cause-and-effect diagram to disk and return the path.

    Parameters
    ----------
    data : list of dict or None
        One row per cause. Defaults to :data:`DEMO_DATA`.
    out : str or None
        Destination path; ``None`` writes beside the script.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    category, cause : str
        Row keys for the cause's group and its text.
    weight : str
        Row key for how much the cause contributes.
    evidenced : str
        Row key for whether anything measured stands behind it.
    effect : str
        The thing being explained.
    weight_label : str
        What the weights count.
    evidence_label, hunch_label : str
        Words for a cause with evidence and one without.
    method_note, finding : str or None
        The line describing the weights, and the sentence naming the
        heaviest group; ``None`` composes each from the data.
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
    >>> p = make_fishbone()
    >>> p.exists()
    True
    """
    svg = build_svg(
        data, title=title, subtitle=subtitle, width=width, height=height,
        category=category, cause=cause, weight=weight, evidenced=evidenced,
        effect=effect, weight_label=weight_label,
        evidence_label=evidence_label, hunch_label=hunch_label,
        method_note=method_note, finding=finding, mode=mode,
        accessibility=accessibility, theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "fishbone")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "fishbone", build_svg,
               description="Draw causes grouped toward one effect, weighted and evidenced.")


if __name__ == "__main__":
    main()
