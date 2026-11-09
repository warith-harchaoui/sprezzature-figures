#!/usr/bin/env python3
"""
make_flowchart — a labelled box-and-arrow flow as hand-authored SVG.

Draws any directed process the caller describes: one row per arrow
(``source`` → ``target``), an optional text on the arrow, an optional group
for each end, and an optional flag that marks an arrow as going *back*
(the return edge of a loop). Boxes are laid out in layers, left to right or
top to bottom (Sugiyama's layered method: longest-path layers, relay points
for arrows that skip a layer, barycentre ordering), so a pipeline reads in
its own order and a loop shows as one arrow returning under the boxes.

Every word on the figure comes from the rows: a box shows its node name,
wrapped at word boundaries and never hyphenated (a ``\\n`` in the name forces
a break); an arrow shows its own label; a group frame shows the group's
name. Nothing is printed about the demo unless the demo is what is drawn.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _style import BG, INK, SECONDARY, cycle_hues, os_dark_style  # noqa: E402
from _svg import svg_open, xml_escape  # noqa: E402
from _textfit import split_words, text_width, wrap_to_width  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme  # noqa: E402

#: The demo: a modelling workflow with one feedback loop and two groups.
DEMO_DATA: List[Dict[str, Any]] = [
    {"source": "Raw data", "target": "Clean and align", "label": "", "source_group": "Data",
     "target_group": "Data"},
    {"source": "Clean and align", "target": "Fit the model", "label": "training rows",
     "source_group": "Data", "target_group": "Modelling"},
    {"source": "Fit the model", "target": "Score on held-out rows", "label": "",
     "source_group": "Modelling", "target_group": "Modelling"},
    {"source": "Score on held-out rows", "target": "Ship the forecast", "label": "passes",
     "source_group": "Modelling", "target_group": ""},
    {"source": "Score on held-out rows", "target": "Fit the model", "label": "retune",
     "back": 1, "source_group": "Modelling", "target_group": "Modelling"},
]
DEMO_TITLE = "One loop, one exit: a model ships only once it passes held-out scoring"
DEMO_SUBTITLE = "Each box is a step, each arrow hands its output on; the arrow underneath returns"

CARD_FILL = "#F5F5F7"   # light card, distinct from the white page
CARD_STROKE = "#C7C7CC"
EDGE_INK = SECONDARY
MARGIN = 24.0
PAD_X, PAD_Y = 12.0, 9.0
NODE_GAP = 18.0          # between two boxes of one layer
GROUP_PAD = 12.0
GROUP_TITLE = 20.0       # band at the top of a group frame for its name
BACK_LANE = 26.0         # vertical (or horizontal) room per returning arrow
LABEL_MAX = 120.0        # an arrow label wraps beyond this width
MIN_FONT = 10.0          # the type never shrinks below this to fit the canvas
#: The width table is an estimate; a line set right up to it touched the box
#: edge in the rendered PDF, so every measured line gets this much air.
TEXT_SLACK = 1.08

Point = Tuple[float, float]
LOGGER = logging.getLogger(__name__)

FRAME_GAP = 10.0         # least room between the frames of two groups
#: Below this share of the requested size the figure says so: past about six
#: layers a left-to-right flow only fits by shrinking its text.
LEGIBLE_SHARE = 0.8


def _truthy(value: Any) -> bool:
    """Read a flag cell: 1, true, yes, y (any case) mean yes; blank means no."""
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "y")
    return bool(value) and value == value  # NaN is falsy here


def _text(value: Any) -> str:
    """A cell as display text: None and NaN become empty."""
    if value is None or (isinstance(value, float) and value != value):
        return ""
    return str(value)


def _graph(rows: List[Dict[str, Any]]) -> Tuple[List[str], List[Dict[str, Any]], Dict[str, str]]:
    """Nodes in first-appearance order, edges, and each node's group.

    A row whose target is empty declares a lone node. A node takes the first
    non-empty group any row gives it, so a group is declared once and
    inherited everywhere the node appears.
    """
    nodes: List[str] = []
    group: Dict[str, str] = {}
    edges: List[Dict[str, Any]] = []
    for r in rows:
        src, tgt = _text(r.get("source")), _text(r.get("target"))
        for name, g in ((src, _text(r.get("source_group"))), (tgt, _text(r.get("target_group")))):
            if name and name not in nodes:
                nodes.append(name)
            if name and g and name not in group:
                group[name] = g
        if src and tgt:
            edges.append({"source": src, "target": tgt, "label": _text(r.get("label")),
                          "back": _truthy(r.get("back")), "dashed": _truthy(r.get("dashed"))})
    return nodes, edges, group


def _layers(nodes: List[str], edges: List[Dict[str, Any]]) -> Dict[str, int]:
    """Longest-path layer of every node over the forward arrows.

    Arrows flagged ``back`` are left out, and so is any further arrow that
    would close a cycle (found by a depth-first walk in row order): those are
    drawn as returning arrows, so the forward graph is acyclic by construction.
    """
    out: Dict[str, List[Dict[str, Any]]] = {n: [] for n in nodes}
    for e in edges:
        if not e["back"]:
            out[e["source"]].append(e)
    state: Dict[str, int] = {}

    def visit(n: str) -> None:
        state[n] = 1
        for e in out[n]:
            t = e["target"]
            if state.get(t) == 1:
                e["back"] = True  # closes a cycle: becomes a returning arrow
            elif t not in state:
                visit(t)
        state[n] = 2

    for n in nodes:
        if n not in state:
            visit(n)
    layer = {n: 0 for n in nodes}
    # Relax in row order until stable; an acyclic graph settles in |V| passes.
    for _ in range(len(nodes)):
        changed = False
        for e in edges:
            if not e["back"] and layer[e["target"]] < layer[e["source"]] + 1:
                layer[e["target"]] = layer[e["source"]] + 1
                changed = True
        if not changed:
            break
    return layer


def _order(
    nodes: List[str], edges: List[Dict[str, Any]], layer: Dict[str, int], group: Dict[str, str]
) -> Tuple[List[List[str]], Dict[Tuple[str, str, int], List[str]]]:
    """Order every layer by barycentre, keeping each group's boxes together.

    Forward arrows that skip layers get one relay point per skipped layer, so
    no arrow crosses a box on its way. Returns the layers (lists of node or
    relay ids) and, per arrow, its relay ids in order.
    """
    n_layers = max(layer.values(), default=0) + 1
    rank: List[List[str]] = [[] for _ in range(n_layers)]
    for n in nodes:
        rank[layer[n]].append(n)
    relays: Dict[Tuple[str, str, int], List[str]] = {}
    neighbours: Dict[str, List[str]] = {n: [] for n in nodes}
    for i, e in enumerate(edges):
        if e["back"]:
            continue
        chain = [e["source"]]
        for k in range(layer[e["source"]] + 1, layer[e["target"]]):
            rid = f"\x00relay{i}-{k}"
            rank[k].append(rid)
            neighbours[rid] = []
            chain.append(rid)
        chain.append(e["target"])
        relays[(e["source"], e["target"], i)] = chain[1:-1]
        for a, b in zip(chain, chain[1:], strict=False):
            neighbours[a].append(b)
            neighbours[b].append(a)
    group_rank = {g: i for i, g in enumerate(dict.fromkeys(group[n] for n in nodes if n in group))}
    position = {v: float(i) for col in rank for i, v in enumerate(col)}
    for sweep in range(8):
        cols = range(1, n_layers) if sweep % 2 == 0 else range(n_layers - 2, -1, -1)
        for k in cols:
            bary = {}
            for v in rank[k]:
                adj = [position[u] for u in neighbours[v] if u in position]
                bary[v] = sum(adj) / len(adj) if adj else position[v]
            # A group sorts as one block, at the mean barycentre of its boxes.
            block: Dict[str, float] = {}
            for v in rank[k]:
                g = group.get(v, "")
                if g:
                    members = [bary[u] for u in rank[k] if group.get(u, "") == g]
                    block[g] = sum(members) / len(members)
            rank[k].sort(key=lambda v: (block.get(group.get(v, ""), bary[v]),
                                        group_rank.get(group.get(v, ""), -1), bary[v]))
            for i, v in enumerate(rank[k]):
                position[v] = float(i)
    if any(len({group[v] for v in col if v in group}) > 1 for col in rank):
        # Two groups side by side must keep one order in every layer, or their
        # frames cross each other however far apart the boxes are pushed.
        where: Dict[str, List[float]] = {}
        for v, p in position.items():
            if v in group:
                where.setdefault(group[v], []).append(p)
        mean = {g: sum(ps) / len(ps) for g, ps in where.items()}
        for col in rank:
            col.sort(key=lambda v: (mean.get(group.get(v, ""), position[v]), position[v]))
    return rank, relays


def _cubic(p: Point, q: Point, horizontal: bool) -> str:
    """A smooth arrow segment leaving ``p`` and entering ``q`` along the flow axis."""
    if horizontal:
        mx = (p[0] + q[0]) / 2
        return f"C{mx:.1f},{p[1]:.1f} {mx:.1f},{q[1]:.1f} {q[0]:.1f},{q[1]:.1f}"
    my = (p[1] + q[1]) / 2
    return f"C{p[0]:.1f},{my:.1f} {q[0]:.1f},{my:.1f} {q[0]:.1f},{q[1]:.1f}"


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    width: int = 760,
    height: Optional[int] = None,
    direction: str = "LR",
    font_size: float = 16.0,
    max_box_width: float = 210.0,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the flowchart SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        One row per arrow with ``source`` and ``target`` (node names; an
        empty target declares a lone node), and optionally ``label`` (text on
        the arrow), ``source_group`` / ``target_group`` (the frame each end
        sits in), ``back`` (1 to draw the arrow as a return under or beside
        the flow) and ``dashed`` (1 for a dashed arrow). Defaults to
        :data:`DEMO_DATA`.
    title, subtitle : str or None
        Header text. ``None`` prints the demo's header over the demo and no
        header over caller data; an empty string prints none.
    width : int
        Canvas width in pixels. Boxes and gaps shrink to fit it. When that
        takes the text below 80 % of ``font_size`` a warning says so.
    height : int or None
        Canvas height; ``None`` sizes the canvas to its content.
    direction : str
        ``"LR"`` (left to right, default) or ``"TB"`` (top to bottom).
    font_size : float
        Box text size in pixels; arrow labels use 85 % of it.
    max_box_width : float
        Widest a box grows before its text wraps; a narrow canvas can hold
        every box below it.
    mode, accessibility, theme : str, optional
        Interactivity mode, palette accessibility level and visual theme.

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    rows = data if data else DEMO_DATA
    if title is None:
        title = DEMO_TITLE if not data else ""
    if subtitle is None:
        subtitle = DEMO_SUBTITLE if not data else ""
    horizontal = str(direction).upper() != "TB"
    nodes, edges, group = _graph(rows)
    layer = _layers(nodes, edges)
    rank, relays = _order(nodes, edges, layer, group)
    n_layers = len(rank)
    label_fs = round(font_size * 0.85, 1)
    line_h = font_size * 1.25

    # ---- header ----
    header: List[str] = []
    y_cursor = MARGIN
    if title:
        for line in wrap_to_width(title, width - 2 * MARGIN, 22, bold=True):
            y_cursor += 28
            header.append(f'<text x="{MARGIN}" y="{y_cursor:.1f}" font-size="22" font-weight="700" '
                          f'fill="{INK}">{xml_escape(line)}</text>')
    if subtitle:
        for line in wrap_to_width(subtitle, width - 2 * MARGIN, 14):
            y_cursor += 20
            header.append(f'<text x="{MARGIN}" y="{y_cursor:.1f}" font-size="14" '
                          f'fill="{SECONDARY}">{xml_escape(line)}</text>')
    top = y_cursor + (18 if header else 0)

    has_groups = bool(group)
    n_back = sum(1 for e in edges if e["back"])
    avail = width - 2 * MARGIN - (n_back * BACK_LANE if not horizontal else 0)

    def pieces(n: str) -> List[str]:
        """A node name split at its forced breaks (a typed ``\\n`` or a newline)."""
        return n.replace("\\n", "\n").split("\n")

    def separation(a: str, b: str) -> float:
        """Room between two neighbours of a layer: more when a group frame ends."""
        ga, gb = group.get(a, ""), group.get(b, "")
        sep = NODE_GAP
        if ga != gb:
            sep += (GROUP_PAD if ga else 0) + (GROUP_PAD + GROUP_TITLE if gb else 0)
        return sep

    def frame_ends(col: List[str]) -> float:
        """Room a group frame takes at the two ends of a layer."""
        if not col:
            return 0.0
        return (GROUP_PAD + GROUP_TITLE if group.get(col[0]) else 0) + (GROUP_PAD if group.get(col[-1]) else 0)

    def sizes(fs: float) -> Tuple[float, List[float], Dict[str, float]]:
        """Overall length, the gaps after each layer and each box's width at size ``fs``.

        A box is never narrower than its longest word (a word is never cut)
        nor wider than ``max_box_width``; between those, every box shrinks
        to one common cap, the largest that fits the canvas.
        """
        lfs = round(fs * 0.85, 1)
        gaps = []
        for k in range(n_layers - 1):
            room = []
            for e in edges:
                if e["label"] and not e["back"] and layer[e["source"]] == k:
                    lines = wrap_to_width(e["label"], LABEL_MAX, lfs)
                    room.append(max(text_width(t, lfs) for t in lines) if horizontal
                                else len(lines) * lfs * 1.2)
            gaps.append(max(40.0, max(room, default=0.0) + 24.0)
                        + (2 * GROUP_PAD + GROUP_TITLE if has_groups else 0))
        lo = {n: TEXT_SLACK * max(text_width(w, fs) for p in pieces(n) for w in (split_words(p) or [""]))
              + 2 * PAD_X for n in nodes}
        hi = {n: max(lo[n], min(max_box_width, TEXT_SLACK * max(text_width(p, fs) for p in pieces(n))
                                + 2 * PAD_X)) for n in nodes}

        def length(cap: float) -> Tuple[float, Dict[str, float]]:
            w = {n: max(lo[n], min(hi[n], cap)) for n in nodes}
            if horizontal:
                widest = [max([w[v] for v in col if v in w] or [6.0]) for col in rank]
                return sum(widest) + sum(gaps), w
            spans = [sum(w.get(v, 6.0) for v in col) + sum(separation(a, b) for a, b in zip(col, col[1:], strict=False))
                     + frame_ends(col) for col in rank]
            return max(spans, default=0.0), w

        low, high = 0.0, max_box_width
        for _ in range(30):  # bisection on the common cap
            mid = (low + high) / 2
            if length(mid)[0] <= avail:
                low = mid
            else:
                high = mid
        total, w = length(low)
        return total, gaps, w

    # Shrink the type only when even the narrowest boxes overflow the canvas.
    fs = float(font_size)
    total, gaps, box_wd = sizes(fs)
    while total > avail and fs > MIN_FONT:
        fs = max(MIN_FONT, fs - 0.5)
        total, gaps, box_wd = sizes(fs)
    if fs < font_size * LEGIBLE_SHARE or total > avail:
        LOGGER.warning(
            "flowchart: %d layers do not fit %d px at the requested text size (%.1f px "
            "drawn, %.1f asked): the text prints small; direction='TB' or fewer "
            "layers read better", n_layers, width, fs, font_size,
        )
    font_size = fs
    label_fs = round(fs * 0.85, 1)
    line_h = fs * 1.25
    width = int(max(width, total + 2 * MARGIN + (n_back * BACK_LANE if not horizontal else 0)))
    text_lines = {n: [t for p in pieces(n)
                      for t in wrap_to_width(p, (box_wd[n] - 2 * PAD_X) / TEXT_SLACK, fs)]
                  for n in nodes}
    box_h = {n: len(text_lines[n]) * line_h + 2 * PAD_Y for n in nodes}
    if horizontal:
        layer_w = [max([box_wd[v] for v in col if v in box_wd] or [6.0]) for col in rank]
    else:
        layer_w = [max([box_h[v] for v in col if v in box_h] or [6.0]) for col in rank]

    def extent(v: str) -> float:
        """Room a box (or a relay point) takes along its layer."""
        if v not in box_h:
            return 6.0
        return box_h[v] if horizontal else box_wd[v]

    # ---- place every layer, centred on a common band ----
    spans = [sum(extent(v) for v in col) + sum(separation(a, b) for a, b in zip(col, col[1:], strict=False))
             + frame_ends(col) for col in rank]
    band = max(spans, default=0.0)
    flow_len = sum(layer_w) + sum(gaps)
    centre: Dict[str, Point] = {}
    which_layer: Dict[str, int] = {}
    if horizontal:
        depth = MARGIN + max(0.0, (width - 2 * MARGIN - flow_len) / 2)
    else:
        depth = top + (GROUP_PAD + GROUP_TITLE if has_groups else 0)
    for k, col in enumerate(rank):
        if horizontal:
            cross = top + (band - spans[k]) / 2
        else:
            cross = MARGIN + max(0.0, (avail - band) / 2) + (band - spans[k]) / 2
        cross += GROUP_PAD + GROUP_TITLE if col and group.get(col[0]) else 0
        for i, v in enumerate(col):
            if i:
                cross += separation(col[i - 1], v)
            c = cross + extent(v) / 2
            centre[v] = (depth + layer_w[k] / 2, c) if horizontal else (c, depth + layer_w[k] / 2)
            which_layer[v] = k
            cross += extent(v)
        depth += layer_w[k] + (gaps[k] if k < len(gaps) else 0)

    def box(v: str) -> Tuple[float, float, float, float]:
        """Left, top, width, height of a node's box."""
        cx, cy = centre[v]
        w = layer_w[which_layer[v]] if horizontal else box_wd[v]
        h = box_h[v]
        return cx - w / 2, cy - h / 2, w, h

    # ---- frames that share layers are pushed apart ----
    def frame(g: str) -> Tuple[float, float, float, float]:
        """Cross start, cross end, flow start and flow end of a group's frame."""
        members = [box(n) for n in nodes if group.get(n) == g]
        x0 = min(b[0] for b in members) - GROUP_PAD
        x1 = max(b[0] + b[2] for b in members) + GROUP_PAD
        y0 = min(b[1] for b in members) - GROUP_PAD - GROUP_TITLE
        y1 = max(b[1] + b[3] for b in members) + GROUP_PAD
        return (y0, y1, x0, x1) if horizontal else (x0, x1, y0, y1)

    cross_axis = 1 if horizontal else 0
    named = list(dict.fromkeys(group[n] for n in nodes if n in group))
    for _ in range(len(named) ** 2):
        named.sort(key=lambda g: frame(g)[0])
        pair = next(((a, b) for i, a in enumerate(named) for b in named[i + 1:]
                     if frame(a)[2] < frame(b)[3] and frame(b)[2] < frame(a)[3]
                     and frame(b)[0] < frame(a)[1] + FRAME_GAP), None)
        if pair is None:
            break
        lower = pair[1]
        push = frame(pair[0])[1] + FRAME_GAP - frame(lower)[0]
        # In each layer the lower group and everything after it moves together,
        # so a layer keeps its order and nothing lands on a neighbour.
        for col in rank:
            ours = [centre[v][cross_axis] for v in col if group.get(v) == lower]
            if ours:
                start = min(ours)
                for v in col:
                    if centre[v][cross_axis] >= start:
                        moved = list(centre[v])
                        moved[cross_axis] += push
                        centre[v] = (moved[0], moved[1])

    # ---- canvas size ----
    far = max((box(n)[1] + box(n)[3] for n in nodes), default=top) if horizontal else \
        max((box(n)[0] + box(n)[2] for n in nodes), default=MARGIN)
    if has_groups:
        far += GROUP_PAD
    lane0 = far + 22.0

    def label_box(text: str) -> Tuple[float, float]:
        """Width and height of an arrow label's halo."""
        lines = wrap_to_width(text, LABEL_MAX, label_fs)
        return max(text_width(s, label_fs) for s in lines) + 8, len(lines) * label_fs * 1.2 + 4

    # One line of label sits on its lane. A longer one sits beside the lane,
    # which then keeps clear of it: a tall halo on the line reached up into the
    # boxes and left the arrow running through the text.
    beside = [len(wrap_to_width(e["label"], LABEL_MAX, label_fs)) > 1 if e["label"] else False
              for e in edges if e["back"]]
    extra = [(label_box(e["label"])[1 if horizontal else 0] + 6) if side else 0.0
             for e, side in zip((e for e in edges if e["back"]), beside, strict=True)]
    lane_end = lane0 + n_back * BACK_LANE + sum(extra)
    if horizontal:
        canvas_h = lane_end + MARGIN if n_back else far + MARGIN
        canvas_w = width
    else:
        width = int(max(width, (lane_end if n_back else far) + MARGIN))
        canvas_w = width
        canvas_h = max(box(n)[1] + box(n)[3] for n in nodes) + (GROUP_PAD if has_groups else 0) + MARGIN
    if height:
        canvas_h = max(canvas_h, float(height))

    parts: List[str] = []
    desc = (f"Flowchart of {len(nodes)} steps and {len(edges)} arrows. "
            + " ".join(f"{e['source']} to {e['target']}{(' (' + e['label'] + ')') if e['label'] else ''}"
                       f"{' returns' if e['back'] else ''}." for e in edges))
    parts.append(svg_open(width, f"{canvas_h:.0f}", "flowchart-title", "flowchart-desc",
                          font_family=chrome_stack_for_theme(theme)))
    parts.append(f'<title id="flowchart-title">{xml_escape(title or "Flowchart")}</title>')
    parts.append(f'<desc id="flowchart-desc">{xml_escape(desc.replace(chr(92) + "n", " ").replace(chr(10), " "))}</desc>')
    parts.append(
        "<style>.fc-node:hover rect,.fc-node:focus rect{stroke:" + INK + ";stroke-width:2}"
        ".fc-node:focus{outline:none}"
        + os_dark_style(ink_map={INK: "#F2F2F7", SECONDARY: "#AEAEB2", BG: "#000000"},
                        screen_blend=False,
                        extra=f'rect[fill="{CARD_FILL}"]{{fill:#2C2C2E;}} '
                              f'[stroke="{CARD_STROKE}"]{{stroke:#48484A;}} '
                              f'path[stroke="{EDGE_INK}"]{{stroke:#AEAEB2;}} '
                              f'polygon[fill="{EDGE_INK}"]{{fill:#AEAEB2;}} '
                              f'rect.halo{{fill:#000000;}}')
        + "</style>"
    )
    parts.append(f'<rect width="{canvas_w}" height="{canvas_h:.0f}" fill="{BG}"/>')
    parts.extend(header)

    # ---- group frames, drawn first so boxes sit on top ----
    groups = list(dict.fromkeys(group[n] for n in nodes if n in group))
    hue = cycle_hues(groups, accessibility, theme=theme) if groups else {}
    for g in groups:
        members = [box(n) for n in nodes if group.get(n) == g]
        x0 = min(b[0] for b in members) - GROUP_PAD
        y0 = min(b[1] for b in members) - GROUP_PAD - GROUP_TITLE
        x1 = max(b[0] + b[2] for b in members) + GROUP_PAD
        y1 = max(b[1] + b[3] for b in members) + GROUP_PAD
        parts.append(f'<rect class="fc-group" x="{x0:.1f}" y="{y0:.1f}" width="{x1 - x0:.1f}" height="{y1 - y0:.1f}" '
                     f'rx="12" fill="{hue[g]}" fill-opacity="0.07" stroke="{hue[g]}" '
                     f'stroke-opacity="0.55" stroke-width="1.2"/>')
        parts.append(f'<text x="{x0 + 10:.1f}" y="{y0 + 15:.1f}" font-size="{label_fs}" '
                     f'font-weight="600" fill="{SECONDARY}">{xml_escape(g)}</text>')

    # ---- arrows ----
    arrow_parts: List[str] = []
    label_parts: List[str] = []

    def halo_label(x: float, y: float, text: str) -> None:
        """An arrow label on a white halo, wrapped at :data:`LABEL_MAX`."""
        lines = wrap_to_width(text, LABEL_MAX, label_fs)
        w = max(text_width(s, label_fs) for s in lines) + 8
        h = len(lines) * label_fs * 1.2 + 4
        label_parts.append(f'<rect class="halo" x="{x - w / 2:.1f}" y="{y - h / 2:.1f}" width="{w:.1f}" '
                           f'height="{h:.1f}" rx="4" fill="{BG}"/>')
        for i, s in enumerate(lines):
            ty = y - h / 2 + 2 + label_fs * (i + 0.95) * 1.2 - label_fs * 0.2
            label_parts.append(f'<text x="{x:.1f}" y="{ty:.1f}" font-size="{label_fs}" fill="{SECONDARY}" '
                               f'text-anchor="middle">{xml_escape(s)}</text>')

    # Ports: arrows leave and enter a box spread along its side, in the
    # order of the box at their other end, so parallel arrows never merge.
    outgoing: Dict[str, List[Tuple[float, int]]] = {}
    incoming: Dict[str, List[Tuple[float, int]]] = {}
    for i, e in enumerate(edges):
        if e["back"]:
            continue
        chain = relays[(e["source"], e["target"], i)]
        nxt = chain[0] if chain else e["target"]
        prv = chain[-1] if chain else e["source"]
        axis = 1 if horizontal else 0
        outgoing.setdefault(e["source"], []).append((centre[nxt][axis], i))
        incoming.setdefault(e["target"], []).append((centre[prv][axis], i))

    def port(v: str, i: int, side: str) -> Point:
        """Where arrow ``i`` meets box ``v`` on its outgoing or incoming side."""
        x, y, w, h = box(v)
        lst = sorted(outgoing[v] if side == "out" else incoming[v])
        k = [j for _, j in lst].index(i)
        frac = (k + 1) / (len(lst) + 1)
        if horizontal:
            return (x + w if side == "out" else x, y + h * (0.25 + 0.5 * frac) if len(lst) > 1 else y + h / 2)
        return (x + w * (0.25 + 0.5 * frac) if len(lst) > 1 else x + w / 2, y + h if side == "out" else y)

    for i, e in enumerate(edges):
        dash = ' stroke-dasharray="6 4"' if e["dashed"] else ""
        tip = f'{e["source"]} to {e["target"]}' + (f': {e["label"]}' if e["label"] else "")
        if e["back"]:
            continue
        chain = relays[(e["source"], e["target"], i)]
        pts = [port(e["source"], i, "out")] + [centre[r] for r in chain] + [port(e["target"], i, "in")]
        end = pts[-1]
        # Stop the line short of the box so the arrow head, not the line, meets it.
        stop = (end[0] - 7, end[1]) if horizontal else (end[0], end[1] - 7)
        pts[-1] = stop
        d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f} " + " ".join(_cubic(a, b, horizontal) for a, b in zip(pts, pts[1:], strict=False))
        arrow_parts.append(f'<path d="{d}" fill="none" stroke="{EDGE_INK}" stroke-width="1.6"{dash}>'
                           f'<title>{xml_escape(tip)}</title></path>')
        head = (f"{end[0]:.1f},{end[1]:.1f} {end[0] - 8:.1f},{end[1] - 4.5:.1f} {end[0] - 8:.1f},{end[1] + 4.5:.1f}"
                if horizontal else
                f"{end[0]:.1f},{end[1]:.1f} {end[0] - 4.5:.1f},{end[1] - 8:.1f} {end[0] + 4.5:.1f},{end[1] - 8:.1f}")
        arrow_parts.append(f'<polygon points="{head}" fill="{EDGE_INK}"/>')
        if e["label"]:
            a, b = pts[0], pts[1]
            halo_label((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, e["label"])

    # Returning arrows run in their own lanes beyond the flow, one lane each.
    lane = 0
    depth_so_far = lane0
    for e in edges:
        if not e["back"]:
            continue
        dash = ' stroke-dasharray="6 4"' if e["dashed"] else ""
        sx, sy, sw, sh = box(e["source"])
        tx, ty, tw, th = box(e["target"])
        depth = depth_so_far
        if horizontal:
            a = (sx + sw / 2, sy + sh)
            b = (tx + tw / 2, ty + th)
            d = (f"M{a[0]:.1f},{a[1]:.1f} L{a[0]:.1f},{depth - 10:.1f} Q{a[0]:.1f},{depth:.1f} "
                 f"{a[0] - 10:.1f},{depth:.1f} L{b[0] + 10:.1f},{depth:.1f} Q{b[0]:.1f},{depth:.1f} "
                 f"{b[0]:.1f},{depth - 10:.1f} L{b[0]:.1f},{b[1] + 7:.1f}")
            head = f"{b[0]:.1f},{b[1]:.1f} {b[0] - 4.5:.1f},{b[1] + 8:.1f} {b[0] + 4.5:.1f},{b[1] + 8:.1f}"
            mid = ((a[0] + b[0]) / 2, depth)
        else:
            a = (sx + sw, sy + sh / 2)
            b = (tx + tw, ty + th / 2)
            d = (f"M{a[0]:.1f},{a[1]:.1f} L{depth - 10:.1f},{a[1]:.1f} Q{depth:.1f},{a[1]:.1f} "
                 f"{depth:.1f},{a[1] - 10:.1f} L{depth:.1f},{b[1] + 10:.1f} Q{depth:.1f},{b[1]:.1f} "
                 f"{depth - 10:.1f},{b[1]:.1f} L{b[0] + 7:.1f},{b[1]:.1f}")
            head = f"{b[0]:.1f},{b[1]:.1f} {b[0] + 8:.1f},{b[1] - 4.5:.1f} {b[0] + 8:.1f},{b[1] + 4.5:.1f}"
            mid = (depth, (a[1] + b[1]) / 2)
        tip = f'{e["source"]} back to {e["target"]}' + (f': {e["label"]}' if e["label"] else "")
        arrow_parts.append(f'<path d="{d}" fill="none" stroke="{EDGE_INK}" stroke-width="1.6"{dash}>'
                           f'<title>{xml_escape(tip)}</title></path>')
        arrow_parts.append(f'<polygon points="{head}" fill="{EDGE_INK}"/>')
        if e["label"]:
            if beside[lane]:
                w, h = label_box(e["label"])
                mid = (mid[0], depth + h / 2 + 4) if horizontal else (depth + w / 2 + 4, mid[1])
            halo_label(mid[0], mid[1], e["label"])
        depth_so_far += BACK_LANE + extra[lane]
        lane += 1

    parts.extend(arrow_parts)

    # ---- boxes ----
    for n in nodes:
        x, y, w, h = box(n)
        parts.append(f'<g class="fc-node" tabindex="0"><title>{xml_escape(n.replace(chr(92) + "n", " ").replace(chr(10), " "))}</title>')
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="10" '
                     f'fill="{CARD_FILL}" stroke="{CARD_STROKE}" stroke-width="1.2"/>')
        lines = text_lines[n]
        first = y + h / 2 - (len(lines) - 1) * line_h / 2 + font_size * 0.35
        for i, s in enumerate(lines):
            parts.append(f'<text x="{x + w / 2:.1f}" y="{first + i * line_h:.1f}" font-size="{font_size}" '
                         f'fill="{INK}" text-anchor="middle">{xml_escape(s)}</text>')
        parts.append("</g>")

    # Labels last: SVG has no z-index, and a label under a box is lost.
    parts.extend(label_parts)
    parts.append(fullscreen_control(width, int(canvas_h), mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_flowchart(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    width: int = 760,
    height: Optional[int] = None,
    direction: str = "LR",
    font_size: float = 16.0,
    max_box_width: float = 210.0,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render a flowchart and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Arrow rows (see :func:`build_svg`). Defaults to :data:`DEMO_DATA`.
    out : Path, str, or None
        Output path. Defaults to ``assets/svg-examples/flowchart.svg``.
    title, subtitle, width, height, direction, font_size, max_box_width : optional
        Forwarded to :func:`build_svg`.
    mode, accessibility, theme : str
        Forwarded to :func:`build_svg`.

    Returns
    -------
    Path
        Absolute path to the written SVG file.

    Examples
    --------
    >>> p = make_flowchart()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                    direction=direction, font_size=font_size, max_box_width=max_box_width,
                    mode=mode, accessibility=accessibility, theme=theme)
    dest = Path(out) if out else svg_example_path(__file__, "flowchart")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "flowchart", build_svg, description="Generate a labelled flowchart.")


if __name__ == "__main__":
    main()
