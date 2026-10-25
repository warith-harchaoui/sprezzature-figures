#!/usr/bin/env python3
"""
make_causal-dag — the graph, and what it says to adjust for.

Nodes and arrows for the assumed causal structure, with the treatment and
the outcome marked, and every other node coloured by the part it plays
between them: confounder, mediator, collider.

Where the usual causal diagram goes wrong
-------------------------------------------
* **It draws the graph and leaves the decision to the reader.** A DAG
  exists to answer one question -- what to condition on -- and the
  usual rendering stops one step short of it. This enumerates the
  backdoor paths from treatment to outcome, tests the proposed
  adjustment set against them, and says which paths are blocked and
  which are left open.
* **Colliders look like any other node.** Conditioning on a collider
  *creates* the bias it looks like it removes, which is the single most
  expensive mistake a DAG is meant to prevent. Colliders on a
  treatment-outcome path are found and marked "do not adjust".
* **Mediators get adjusted for out of habit.** Conditioning on a node
  on the causal path blocks part of the very effect being estimated.
  Mediators are found the same way and marked for the same reason.
* **Unobserved nodes are drawn solid.** A confounder you cannot measure
  is the difference between an estimate and a guess. Unobserved nodes
  are drawn hollow, and a backdoor path left open through one is
  reported as open rather than quietly dropped.

The roles are computed from the arrows, not declared: a node that
becomes a mediator because an arrow was added is relabelled by the
figure, which is the point of drawing the graph at all.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _style import BG, GRIDLINE, INK, SECONDARY, load_palette  # noqa: E402
from _svg import (  # noqa: E402
    foreground_tip_css,
    svg_open,
    tooltip_bubble,
    wrap_no_orphan,
    xml_escape,
)
from _textfit import fit_font_size  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

#: One row per arrow. ``observed`` marks whether the *source* node was
#: measured; a node is unobserved only if every row naming it says so.
DEMO_DATA: List[Dict[str, Any]] = [
    {"source": "social class", "target": "statin prescribed", "observed": 1},
    {"source": "social class", "target": "heart attack", "observed": 1},
    {"source": "family history", "target": "statin prescribed", "observed": 1},
    {"source": "family history", "target": "heart attack", "observed": 1},
    {"source": "genetic risk", "target": "cholesterol", "observed": 0},
    {"source": "genetic risk", "target": "heart attack", "observed": 0},
    {"source": "cholesterol", "target": "statin prescribed", "observed": 1},
    {"source": "statin prescribed", "target": "ldl level", "observed": 1},
    {"source": "ldl level", "target": "heart attack", "observed": 1},
    {"source": "statin prescribed", "target": "hospital record", "observed": 1},
    {"source": "heart attack", "target": "hospital record", "observed": 1},
]


def _edges(rows: Sequence[Dict[str, Any]], source: str, target: str) -> List[Tuple[str, str]]:
    """The arrows, as (from, to) pairs in the order they were given."""
    return [(str(row[source]), str(row[target])) for row in rows]


def _descendants(start: str, arrows: Sequence[Tuple[str, str]]) -> Set[str]:
    """Every node reachable from `start` by following arrows forwards."""
    seen: Set[str] = set()
    queue = [start]
    while queue:
        node = queue.pop()
        for tail, head in arrows:
            if tail == node and head not in seen:
                seen.add(head)
                queue.append(head)
    return seen


def _ancestors(start: str, arrows: Sequence[Tuple[str, str]]) -> Set[str]:
    """Every node that can reach `start` by following arrows forwards."""
    seen: Set[str] = set()
    queue = [start]
    while queue:
        node = queue.pop()
        for tail, head in arrows:
            if head == node and tail not in seen:
                seen.add(tail)
                queue.append(tail)
    return seen


def _simple_paths(
    start: str, finish: str, arrows: Sequence[Tuple[str, str]], cap: int = 400
) -> List[List[str]]:
    """Every simple path between two nodes, ignoring arrow direction.

    Direction is ignored on purpose: a backdoor path runs *against* the
    arrows for part of its length, which is exactly what makes it a
    backdoor. The directions are put back when each path is tested.
    """
    neighbours: Dict[str, Set[str]] = {}
    for tail, head in arrows:
        neighbours.setdefault(tail, set()).add(head)
        neighbours.setdefault(head, set()).add(tail)
    found: List[List[str]] = []

    def walk(node: str, seen: List[str]) -> None:
        if len(found) >= cap:
            return
        for step in sorted(neighbours.get(node, ())):
            if step in seen:
                continue
            if step == finish:
                found.append([*seen, node, step])
            else:
                walk(step, [*seen, node])

    walk(start, [])
    return found


def _is_collider(before: str, node: str, after: str, arrows: Sequence[Tuple[str, str]]) -> bool:
    """Whether `node` has both its neighbours on the path pointing into it."""
    return (before, node) in arrows and (after, node) in arrows


def _blocked(
    path: List[str], adjust: Set[str], arrows: Sequence[Tuple[str, str]]
) -> bool:
    """Whether conditioning on `adjust` blocks `path`.

    The two halves of d-separation, in the order they bite: a chain or a
    fork is blocked by conditioning on its middle node, and a collider is
    blocked *unless* it or one of its descendants is conditioned on.
    """
    for index in range(1, len(path) - 1):
        before, node, after = path[index - 1], path[index], path[index + 1]
        if _is_collider(before, node, after, arrows):
            opened = node in adjust or bool(
                _descendants(node, arrows) & adjust
            )
            if not opened:
                return True
        elif node in adjust:
            return True
    return False


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Adjust for three; the hospital record would open a path that is closed",
    subtitle: str = "The assumed causal structure, with every node's part worked out from the arrows rather than declared.",
    width: int = 980,
    height: int = 620,
    source: str = "source",
    target: str = "target",
    observed: str = "observed",
    treatment: str = "statin prescribed",
    outcome: str = "heart attack",
    adjust_for: Optional[List[str]] = None,
    treatment_label: str = "treatment",
    outcome_label: str = "outcome",
    confounder_label: str = "confounder",
    mediator_label: str = "mediator · do not adjust",
    collider_label: str = "collider · do not adjust",
    unobserved_label: str = "unobserved",
    set_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full causal diagram SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        One row per arrow, from `source` to `target`. Defaults to
        :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    source, target, observed : str
        Row keys for the two ends of each arrow and for whether the
        source node was measured.
    treatment, outcome : str
        The two nodes the graph is about. Every other node's part is
        worked out relative to these.
    adjust_for : list of str or None
        The proposed adjustment set. ``None`` proposes the observed
        parents of `treatment`, which is the usual first answer and the
        one the figure then tests.
    treatment_label, outcome_label, confounder_label, mediator_label,
    collider_label, unobserved_label : str
        Names for the parts a node can play, used in the key and in the
        accessibility labels.
    set_note, finding : str or None
        The line naming the adjustment set, and the sentence reporting
        the backdoor paths; ``None`` composes each from the data.
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
        raise ValueError("a causal diagram needs at least one arrow")
    arrows = _edges(rows, source, target)
    nodes: List[str] = []
    for tail, head in arrows:
        for node in (tail, head):
            if node not in nodes:
                nodes.append(node)
    for named, which in ((treatment, "treatment"), (outcome, "outcome")):
        if named not in nodes:
            raise ValueError(f"the {which} {named!r} is not a node of this graph")

    measured: Dict[str, bool] = {node: True for node in nodes}
    for row in rows:
        if observed in row and not bool(row[observed]):
            measured[str(row[source])] = False

    after_treatment = _descendants(treatment, arrows)
    before_outcome = _ancestors(outcome, arrows)
    paths = _simple_paths(treatment, outcome, arrows)
    backdoor = [path for path in paths if (path[1], path[0]) in arrows]

    colliders: Set[str] = set()
    for path in paths:
        for index in range(1, len(path) - 1):
            if _is_collider(path[index - 1], path[index], path[index + 1], arrows):
                colliders.add(path[index])

    role: Dict[str, str] = {}
    for node in nodes:
        if node == treatment:
            role[node] = "treatment"
        elif node == outcome:
            role[node] = "outcome"
        elif node in after_treatment and node in before_outcome:
            role[node] = "mediator"
        elif node in colliders:
            role[node] = "collider"
        elif node in _ancestors(treatment, arrows) and node in before_outcome:
            role[node] = "confounder"
        else:
            role[node] = "other"

    proposed = (
        set(adjust_for) if adjust_for is not None
        else {
            tail for tail, head in arrows
            if head == treatment and measured.get(tail, True)
        }
    )
    unknown = sorted(proposed - set(nodes))
    if unknown:
        raise ValueError(f"the adjustment set names nodes not in the graph: {unknown}")
    open_paths = [path for path in backdoor if not _blocked(path, proposed, arrows)]

    mono_family = mono_stack_for_theme(theme)
    palette = load_palette(accessibility, theme=theme)
    ink_for = {
        "treatment": palette.get("Blue", "#007AFF"),
        "outcome": palette.get("Green", "#28CD41"),
        "confounder": palette.get("Orange", "#FF9500"),
        "mediator": palette.get("Purple", "#5856D6"),
        "collider": palette.get("Red", "#FF3B30"),
        "other": SECONDARY,
    }
    label_for = {
        "treatment": treatment_label,
        "outcome": outcome_label,
        "confounder": confounder_label,
        "mediator": mediator_label,
        "collider": collider_label,
        "other": "",
    }

    # Layered left to right by longest path from a source, which puts
    # causes before effects; the band within a layer separates the parts.
    depth: Dict[str, int] = {node: 0 for node in nodes}
    for _ in range(len(nodes)):
        for tail, head in arrows:
            depth[head] = max(depth[head], depth[tail] + 1)
    band = {"confounder": 0, "other": 0, "treatment": 1, "mediator": 1,
            "outcome": 1, "collider": 2}
    layers: Dict[int, List[str]] = {}
    for node in sorted(nodes, key=lambda n: (depth[n], band[role[n]], n)):
        layers.setdefault(depth[node], []).append(node)

    plot_x = 72.0
    plot_y = 232.0
    plot_w = width - plot_x - 72.0
    plot_h = height - plot_y - 104.0
    columns = max(layers) + 1
    at: Dict[str, Tuple[float, float]] = {}
    for layer, members in layers.items():
        column_x = plot_x + (layer + 0.5) * plot_w / columns
        for index, node in enumerate(members):
            at[node] = (
                column_x,
                plot_y + (index + 0.5) * plot_h / len(members),
            )

    set_lines = (
        [set_note] if set_note is not None
        else [
            f"proposed adjustment set: {', '.join(sorted(proposed)) or 'nothing'}",
            f"{len(backdoor)} backdoor path"
            f"{'' if len(backdoor) == 1 else 's'} from {treatment} to {outcome}",
        ]
    )
    said_set = " · ".join(set_lines)
    # The set the caller proposed may itself be the problem. Checked before
    # the backdoor report, because a set containing a collider can block
    # every backdoor path and still be wrong: it opens a path that was
    # closed, and the backdoor count says nothing about that.
    harmful = sorted(
        node for node in proposed
        if role.get(node) in ("mediator", "collider")
    )
    said_parts: List[str] = []
    if finding is not None:
        said_parts.append(finding)
    elif harmful:
        said_parts.append(
            f"The proposed set contains {' and '.join(harmful)}, which "
            f"{'is' if len(harmful) == 1 else 'are'} not "
            f"{'a confounder' if len(harmful) == 1 else 'confounders'}: conditioning "
            f"there biases the estimate rather than correcting it."
        )
    elif open_paths:
        route = " → ".join(open_paths[0])
        said_parts.append(
            f"{len(open_paths)} of {len(backdoor)} backdoor paths stay open, the first "
            f"through {route}."
        )
    else:
        said_parts.append(
            f"All {len(backdoor)} backdoor paths are blocked by this set: the effect "
            f"is identified under these assumptions."
        )
    blocked_names = sorted(
        {node for node in nodes if role[node] in ("mediator", "collider")}
        - set(harmful)
    )
    if blocked_names and finding is None:
        named = (
            " or ".join(blocked_names) if len(blocked_names) == 2
            else ", ".join(blocked_names)
        )
        said_parts.append(
            f"Do not add {named}: conditioning there blocks the effect or opens a "
            f"closed path."
        )
    said_lines: List[str] = []
    for sentence in said_parts:
        said_lines.extend(wrap_no_orphan(sentence, 106))

    parts: List[str] = []
    parts.append(
        svg_open(width, height, "dag-title", "dag-desc",
                 font_family=chrome_stack_for_theme(theme))
    )
    parts.append(f'<title id="dag-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="dag-desc">A causal diagram of {len(nodes)} nodes and {len(arrows)} '
        f'arrows, with {xml_escape(treatment)} as the treatment and {xml_escape(outcome)} '
        f'as the outcome. {xml_escape(said_set)}. {xml_escape(" ".join(said_parts))}</desc>'
    )
    parts.append(
        "<style>"
        ".node{cursor:default;}"
        ".node:hover,.node:focus{outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + foreground_tip_css(len(nodes), mark_prefix="node", tip_prefix="nodetip")
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
    set_drawn: List[str] = []
    for clause in set_lines:
        set_drawn.extend(wrap_no_orphan(clause, 106))
    for line_index, text in enumerate(set_drawn[:2]):
        parts.append(
            f'<text x="40" y="{124 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(text)}</text>'
        )
    for line_index, text in enumerate(said_lines[:3]):
        parts.append(
            f'<text x="40" y="{166 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(text)}</text>'
        )

    parts.append(
        '<defs><marker id="dag-arrow" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{SECONDARY}"/></marker></defs>'
    )
    radius = 15.0
    for tail, head in arrows:
        x1, y1 = at[tail]
        x2, y2 = at[head]
        span = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5 or 1.0
        step_x, step_y = (x2 - x1) / span, (y2 - y1) / span
        parts.append(
            f'<line x1="{x1 + step_x * radius:.1f}" y1="{y1 + step_y * radius:.1f}" '
            f'x2="{x2 - step_x * (radius + 8):.1f}" '
            f'y2="{y2 - step_y * (radius + 8):.1f}" stroke="{SECONDARY}" '
            f'stroke-width="1.4" marker-end="url(#dag-arrow)" opacity="0.75"/>'
        )

    tips: List[str] = []
    for index, node in enumerate(nodes):
        x, y = at[node]
        colour = ink_for[role[node]]
        seen = measured.get(node, True)
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" '
            + (f'fill="{colour}"/>' if seen
               else f'fill="{BG}" stroke="{colour}" stroke-width="2.4" '
                    f'stroke-dasharray="4 3"/>')
        )
        if node in proposed:
            parts.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius + 5:.1f}" fill="none" '
                f'stroke="{INK}" stroke-width="1.4"/>'
            )
        for line_index, text in enumerate(wrap_no_orphan(node, 18)[:2]):
            parts.append(
                f'<text x="{x:.1f}" y="{y + radius + 16 + line_index * 13:.1f}" '
                f'font-size="11" fill="{INK}" text-anchor="middle">'
                f'{xml_escape(text)}</text>'
            )
        part = label_for[role[node]] or "node"
        state = "" if seen else f", {unobserved_label}"
        member = ", in the adjustment set" if node in proposed else ""
        parts.append(
            f'<rect id="node-{index}" class="node hit" tabindex="0" role="img" '
            f'aria-label="{xml_escape(node)}: {xml_escape(part)}{state}{member}" '
            f'x="{x - radius - 6:.1f}" y="{y - radius - 6:.1f}" '
            f'width="{2 * radius + 12:.1f}" height="{2 * radius + 12:.1f}" '
            f'fill="transparent"><title>{xml_escape(node)}: '
            f'{xml_escape(part)}</title></rect>'
        )
        tips.append(
            tooltip_bubble(
                x, y, [node, part] + ([unobserved_label] if not seen else [])
                + (["in the adjustment set"] if node in proposed else []),
                canvas_w=width, canvas_h=height, ink=INK, secondary=SECONDARY,
                border=GRIDLINE, elem_id=f"nodetip-{index}",
            )
        )

    key_y = height - 38.0
    key_x = 40.0
    for part_name in ("treatment", "outcome", "confounder", "mediator", "collider"):
        caption = label_for[part_name]
        parts.append(
            f'<circle cx="{key_x + 6:.1f}" cy="{key_y - 4:.1f}" r="6" '
            f'fill="{ink_for[part_name]}"/>'
        )
        parts.append(
            f'<text x="{key_x + 18:.1f}" y="{key_y:.1f}" font-size="11" '
            f'fill="{SECONDARY}">{xml_escape(caption)}</text>'
        )
        key_x += 30.0 + len(caption) * 5.6
    parts.append(
        f'<circle cx="{key_x + 6:.1f}" cy="{key_y - 4:.1f}" r="6" fill="{BG}" '
        f'stroke="{SECONDARY}" stroke-width="2" stroke-dasharray="3 2"/>'
    )
    parts.append(
        f'<text x="{key_x + 18:.1f}" y="{key_y:.1f}" font-size="11" fill="{SECONDARY}">'
        f'{xml_escape(unobserved_label)}</text>'
    )

    parts.extend(tips)
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_causal_dag(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[str] = None,
    title: str = "Adjust for three; the hospital record would open a path that is closed",
    subtitle: str = "The assumed causal structure, with every node's part worked out from the arrows rather than declared.",
    width: int = 980,
    height: int = 620,
    source: str = "source",
    target: str = "target",
    observed: str = "observed",
    treatment: str = "statin prescribed",
    outcome: str = "heart attack",
    adjust_for: Optional[List[str]] = None,
    treatment_label: str = "treatment",
    outcome_label: str = "outcome",
    confounder_label: str = "confounder",
    mediator_label: str = "mediator · do not adjust",
    collider_label: str = "collider · do not adjust",
    unobserved_label: str = "unobserved",
    set_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Write a causal diagram to disk and return the path.

    Parameters
    ----------
    data : list of dict or None
        One row per arrow. Defaults to :data:`DEMO_DATA`.
    out : str or None
        Destination path; ``None`` writes beside the script.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    source, target, observed : str
        Row keys for the two ends of each arrow and for whether the
        source node was measured.
    treatment, outcome : str
        The two nodes the graph is about.
    adjust_for : list of str or None
        The proposed adjustment set; ``None`` proposes the observed
        parents of `treatment`.
    treatment_label, outcome_label, confounder_label, mediator_label,
    collider_label, unobserved_label : str
        Names for the parts a node can play.
    set_note, finding : str or None
        The line naming the adjustment set, and the sentence reporting
        the backdoor paths; ``None`` composes each from the data.
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
    >>> p = make_causal_dag()
    >>> p.exists()
    True
    """
    svg = build_svg(
        data, title=title, subtitle=subtitle, width=width, height=height,
        source=source, target=target, observed=observed, treatment=treatment,
        outcome=outcome, adjust_for=adjust_for, treatment_label=treatment_label,
        outcome_label=outcome_label, confounder_label=confounder_label,
        mediator_label=mediator_label, collider_label=collider_label,
        unobserved_label=unobserved_label, set_note=set_note, finding=finding,
        mode=mode, accessibility=accessibility, theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "causal-dag")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "causal-dag", build_svg,
               description="Draw a causal diagram and test what it says to adjust for.")


if __name__ == "__main__":
    main()
