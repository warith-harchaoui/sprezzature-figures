#!/usr/bin/env python3
"""
make_sankey — publication-quality Sankey diagram as a hand-authored SVG.

A Sankey diagram shows *flows* between nodes as ribbons whose width is
proportional to the volume they carry. It answers "where does the
quantity go, and how much is lost at each hop?" better than any bar or
pie chart, because the eye reads the width of a ribbon as a magnitude
and follows it across the whole cascade.

Vega-Lite has no native Sankey mark, so this figure is built as an SVG
string by hand rather than through ``vl_convert``. The layout is a
left-to-right layered graph:

* **Nodes** are stacked vertical bars, one column ("layer") per stage
  of the journey, auto-assigned from the flow data by longest-path
  topological layering (a node with no inbound flow is layer 0; every
  other node's layer is one past its deepest predecessor). Each node's
  height is proportional to the volume that passes through it.
* **Links** are cubic Bézier ribbons whose vertical thickness at both
  ends equals the volume of that flow; a flow that splits keeps its
  total width conserved (widths in = widths out at every node).

House style follows ``_style.py`` / ``bar.vl.json``: Roboto type, the
Apple-system categorical palette, ink ``#1D1D1F`` on white, rounded
node corners, a start-anchored title plus a one-line takeaway subtitle.
Every layer-0 ("root") node gets a distinct hue from the accessibility
palette; every downstream node and ribbon borrows the hue of whichever
root contributes the most volume to it, so the origin story survives
the whole cascade.

Interaction (no JavaScript): every ribbon carries a native ``<title>``
tooltip with its exact volume, and a CSS ``:hover`` / ``:focus`` rule
dims the other ribbons so the hovered flow pops — the "hover-highlight
a flow" affordance that suits this capability. The figure is otherwise
static (a Sankey does not benefit from animation), so ``animated`` is
false and ``interactive`` is true.

Running the module writes the SVG to
``sprezzature-figures/assets/svg-examples/sankey.svg``.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _style import forced_color_patterns, load_palette, os_adaptive_style, os_dark_style  # noqa: E402
from _render import svg_example_path, write_svg  # noqa: E402
from _svg import svg_open  # noqa: E402
from _interactive import fullscreen_control  # noqa: E402

# ------------------------------------------------------------------
# Canvas + house-style tokens
# ------------------------------------------------------------------
WIDTH = 1360
HEIGHT = 820
MARGIN_LEFT = 44
MARGIN_RIGHT = 44
MARGIN_TOP = 168         # room for title + subtitle + stage headers
MARGIN_BOTTOM = 56

INK = "#1D1D1F"          # primary text
SUBINK = "#6E6E73"       # secondary text
GRIDLINE = "#E5E5EA"     # hairline neutral
BG = "#FFFFFF"

NODE_WIDTH = 24          # px width of each node bar
NODE_PAD = 40            # vertical gap between stacked nodes in a layer
LABEL_GAP = 14           # gap between a node bar and its text label

FONT = "Roboto, system-ui, sans-serif"
FONT_MONO = "Roboto Mono, ui-monospace, monospace"

_DEFAULT_STAGE_NAMES = ("Channel", "Engagement", "Intent", "Outcome")
_NEUTRAL_RIBBON = "#AEAEB2"
_NEUTRAL_NODE = "#8E8E93"

# ------------------------------------------------------------------
# The story: a week of visitors to a SaaS
# marketing site, from acquisition channel through the funnel to the
# outcome. The takeaway: organic search is the biggest top-of-funnel
# source, yet paid traffic converts to a paid plan at a higher rate.
# Rows are flow records; nodes and their layers are inferred from them
# (see :func:`_nodes_and_links`) rather than declared separately.
# ------------------------------------------------------------------
DEMO_DATA: List[Dict[str, Any]] = [
    {"source": "Organic search", "target": "Browsed", "value": 4200},
    {"source": "Organic search", "target": "Bounced", "value": 1800},
    {"source": "Paid ads", "target": "Browsed", "value": 2600},
    {"source": "Paid ads", "target": "Bounced", "value": 900},
    {"source": "Referral", "target": "Browsed", "value": 1400},
    {"source": "Referral", "target": "Bounced", "value": 400},
    {"source": "Browsed", "target": "Signed up", "value": 3100},
    {"source": "Browsed", "target": "Left", "value": 5100},
    {"source": "Signed up", "target": "Paid plan", "value": 900},
    {"source": "Signed up", "target": "Free plan", "value": 1700},
    {"source": "Signed up", "target": "Churned", "value": 500},
]


def _slug(label: str) -> str:
    """Turn a node name into a CSS-class-safe slug."""
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in label).strip("-") or "n"


def _nodes_and_links(data: List[Dict[str, Any]]) -> Tuple[List[Tuple[str, str, int]], List[Tuple[str, str, float]]]:
    """Derive (id, label, layer) nodes and (source, target, value) links from
    flow records, auto-layering nodes by longest path from a root (a node
    with no inbound flow) so callers never declare layers by hand.
    """
    links = [(str(row["source"]), str(row["target"]), float(row["value"])) for row in data]
    node_ids = {s for s, _t, _v in links} | {t for _s, t, _v in links}

    incoming: Dict[str, List[str]] = {n: [] for n in node_ids}
    for s, t, _v in links:
        incoming[t].append(s)

    layer_of: Dict[str, int] = {}

    def _layer(node: str, seen: frozenset) -> int:
        if node in layer_of:
            return layer_of[node]
        if node in seen:  # defensive cycle guard; Sankeys are normally DAGs
            return 0
        preds = incoming.get(node, [])
        layer_of[node] = 0 if not preds else 1 + max(_layer(p, seen | {node}) for p in preds)
        return layer_of[node]

    for n in node_ids:
        _layer(n, frozenset())

    nodes = sorted(((n, n, layer_of[n]) for n in node_ids), key=lambda row: (row[2], row[0]))
    return nodes, links


def _root_dominance(nodes: List[Tuple[str, str, int]], links: List[Tuple[str, str, float]]) -> Dict[str, str | None]:
    """Map every node id to the layer-0 ("root") node that contributes the
    most cumulative volume to it, walking inbound links back to the roots.
    Root nodes map to themselves; a node with no traceable root (should not
    happen in a connected DAG) maps to None.
    """
    roots = {n for n, _l, layer in nodes if layer == 0}
    by_target: Dict[str, List[Tuple[str, float]]] = {}
    for s, t, v in links:
        by_target.setdefault(t, []).append((s, v))

    dominant: Dict[str, str | None] = {}

    def _resolve(node: str, seen: frozenset) -> str | None:
        if node in dominant:
            return dominant[node]
        if node in roots:
            dominant[node] = node
            return node
        if node in seen:
            return None
        tally: Dict[str, float] = {}
        for s, v in by_target.get(node, []):
            root = _resolve(s, seen | {node})
            if root is not None:
                tally[root] = tally.get(root, 0.0) + v
        dominant[node] = max(tally, key=lambda k: tally[k]) if tally else None
        return dominant[node]

    for n, _l, _layer in nodes:
        _resolve(n, frozenset())
    return dominant


# ------------------------------------------------------------------
# Layout maths
# ------------------------------------------------------------------
def _node_volume(node_id: str, links: List[Tuple[str, str, float]]) -> float:
    """Return the throughput of a node = max(inflow, outflow).

    A pure source node has no inflow, a pure sink has no outflow; using
    the max keeps a node's bar height equal to the total volume that
    actually passes through it.
    """
    inflow = sum(v for s, t, v in links if t == node_id)
    outflow = sum(v for s, t, v in links if s == node_id)
    return max(inflow, outflow)


def _layers(nodes: List[Tuple[str, str, int]]) -> Dict[int, List[str]]:
    """Group node ids by their layer index, preserving declaration order."""
    layers: Dict[int, List[str]] = {}
    for node_id, _label, layer in nodes:
        layers.setdefault(layer, []).append(node_id)
    return layers


def _compute_geometry(
    nodes: List[Tuple[str, str, int]], links: List[Tuple[str, str, float]]
) -> Tuple[Dict[str, dict], float]:
    """Place every node and return (geometry, volume→pixel scale).

    Returns
    -------
    geometry : dict
        ``{node_id: {"x", "y", "h", "vol", "layer",
        "in_cursor", "out_cursor"}}`` in SVG pixel coordinates. The
        cursors track how much of a node's top/bottom edge has already
        been consumed by ribbons, so stacked links do not overlap.
    scale : float
        Pixels per unit volume, chosen so the tallest layer fills the
        plot height minus its inter-node padding.
    """
    layers = _layers(nodes)
    plot_top = MARGIN_TOP
    plot_bottom = HEIGHT - MARGIN_BOTTOM
    plot_h = plot_bottom - plot_top
    plot_left = MARGIN_LEFT
    plot_right = WIDTH - MARGIN_RIGHT

    # Vertical scale: the densest layer (most total volume) must fit.
    max_layer_vol = 0.0
    for ids in layers.values():
        total = sum(_node_volume(n, links) for n in ids)
        pad_total = NODE_PAD * (len(ids) - 1)
        max_layer_vol = max(max_layer_vol, total / max(1e-9, (plot_h - pad_total)))
    scale = 1.0 / max_layer_vol if max_layer_vol else 1.0

    n_layers = len(layers)
    xs = [
        plot_left + i * (plot_right - plot_left - NODE_WIDTH) / max(1, n_layers - 1)
        for i in range(n_layers)
    ]

    geometry: Dict[str, dict] = {}
    for layer_idx in sorted(layers):
        ids = layers[layer_idx]
        heights = [_node_volume(n, links) * scale for n in ids]
        pad_total = NODE_PAD * (len(ids) - 1)
        stack_h = sum(heights) + pad_total
        y = plot_top + (plot_h - stack_h) / 2.0
        for node_id, h in zip(ids, heights):
            geometry[node_id] = {
                "x": xs[layer_idx],
                "y": y,
                "h": h,
                "vol": _node_volume(node_id, links),
                "layer": layer_idx,
                "out_cursor": y,
                "in_cursor": y,
            }
            y += h + NODE_PAD

    return geometry, scale


# ------------------------------------------------------------------
# SVG emission
# ------------------------------------------------------------------
def _ribbon_path(x0: float, y0: float, x1: float, y1: float, thick: float) -> str:
    """Build a filled cubic-Bézier ribbon of constant vertical thickness.

    The ribbon leaves the source node's right edge at ``(x0, y0)`` and
    lands on the target node's left edge at ``(x1, y1)``; ``y0`` / ``y1``
    are the *top* of the ribbon at each end. Control points sit at the
    horizontal midpoint for the classic Sankey S-curve.
    """
    xc = (x0 + x1) / 2.0
    top = (
        f"M{x0:.1f},{y0:.1f} "
        f"C{xc:.1f},{y0:.1f} {xc:.1f},{y1:.1f} {x1:.1f},{y1:.1f}"
    )
    bottom = (
        f"L{x1:.1f},{y1 + thick:.1f} "
        f"C{xc:.1f},{y1 + thick:.1f} {xc:.1f},{y0 + thick:.1f} {x0:.1f},{y0 + thick:.1f} Z"
    )
    return top + " " + bottom


def _fmt_k(v: float) -> str:
    """Format a volume compactly (e.g. 4200 → '4.2k')."""
    if v >= 1000:
        return f"{v / 1000:.1f}k".replace(".0k", "k")
    return str(int(v)) if float(v).is_integer() else f"{v:g}"


def build_svg(
    data: List[Dict[str, Any]] | None = None,
    *,
    title: str = "Organic search fills the funnel, but paid ads convert",
    subtitle: str = "One week of site visitors, from channel to outcome",
    desc: str | None = None,
    stage_names: List[str] | None = None,
    volume_unit: str = "visitors",
    mode: str = "self-contained",
    accessibility: str = "universal",
) -> str:
    """Assemble the full Sankey SVG document as a string.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Flow rows with ``source`` (str), ``target`` (str), ``value``
        (float) keys. Node identity and stage (layer) are inferred from
        the graph structure. Defaults to DEMO_DATA.
    title, subtitle : str
        Chart text.
    desc : str or None
        Accessible long description. Auto-generated from the data when
        not given.
    stage_names : list[str] or None
        One label per layer, shown as column headers. Defaults to the
        illustrative scenario's stage names when the layer count matches
        (4), otherwise generic "Stage N" labels.
    volume_unit : str
        Unit word appended to tooltips and node counts (e.g. "visitors",
        "units", "€").
    mode : str, optional
        Interactivity mode for the fullscreen control (``"self-contained"``
        / ``"external"`` / ``"static"``).
    accessibility : str, optional
        Palette accessibility level (``"universal"``, ``"high-contrast"``,
        ``"monochrome"``, ``"deuteranopia"``, ``"protanopia"`` or
        ``"tritanopia"``).

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    data = data if data is not None else DEMO_DATA
    nodes, links = _nodes_and_links(data)
    dominant = _root_dominance(nodes, links)
    roots = [n for n, _l, layer in nodes if layer == 0]

    palette = load_palette(accessibility)
    palette_colors = list(palette.values())
    root_color = {root: palette_colors[i % len(palette_colors)] for i, root in enumerate(roots)}

    geometry, _scale = _compute_geometry(nodes, links)
    label_of = {nid: lbl for nid, lbl, _ in nodes}
    layers = _layers(nodes)
    n_layers = len(layers)

    if stage_names is None:
        stage_names = list(_DEFAULT_STAGE_NAMES) if n_layers == len(_DEFAULT_STAGE_NAMES) else [
            f"Stage {i + 1}" for i in range(n_layers)
        ]

    if desc is None:
        top_root = max(roots, key=lambda r: _node_volume(r, links)) if roots else None
        desc = (
            f"Sankey diagram of flow across {n_layers} stages: "
            + ", ".join(stage_names)
            + f". Ribbon width is proportional to {volume_unit}."
            + (f" {label_of.get(top_root, top_root)} is the largest source." if top_root else "")
        )

    parts: List[str] = []

    # --- header: accessible role + title + description ---
    parts.append(svg_open(WIDTH, HEIGHT, "sankey-title", "sankey-desc", font_family=FONT))
    parts.append(f'<title id="sankey-title">{escape(title)}</title>')
    parts.append(f'<desc id="sankey-desc">{escape(desc)}</desc>')

    # OS-adaptive overrides (additive; every rule lives inside an @media block,
    # so the default render stays unchanged for accessibility="universal").
    # Each root channel carries a ``.sk-<slug>`` class on both its ribbons and
    # its own node, so prefers-contrast can deepen the hue and forced-colors
    # can hand it a distinct Canvas pattern, keeping every origin distinguishable.
    sk_series = {f".sk-{_slug(root)}": root_color[root] for root in roots}
    fcp_defs, fcp_style = forced_color_patterns(list(sk_series), prefix="sk-fcp")
    parts.append(
        "<style>"
        ".link{transition:opacity .15s ease}"
        "#links:hover .link{opacity:.18}"
        "#links .link:hover,#links .link:focus{opacity:1}"
        ".link:focus{outline:none}"
        + os_adaptive_style(sk_series, role="fill")
        + fcp_style
        + os_dark_style()
        + "</style>"
    )
    parts.append(f"<defs>{fcp_defs}</defs>")

    # --- background ---
    parts.append(f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{BG}"/>')

    # --- title + subtitle (start-anchored, house style) ---
    parts.append(
        f'<text x="{MARGIN_LEFT}" y="58" font-size="34" font-weight="700" '
        f'fill="{INK}">{escape(title)}</text>'
    )
    parts.append(
        f'<text x="{MARGIN_LEFT}" y="92" font-size="20" fill="{SUBINK}">'
        f'{escape(subtitle)}</text>'
    )

    # --- stage headers across the top of the plot ---
    for layer_idx in sorted(layers):
        any_node = layers[layer_idx][0]
        gx = geometry[any_node]["x"]
        anchor = "start"
        tx = gx
        if layer_idx == n_layers - 1:
            anchor = "end"
            tx = gx + NODE_WIDTH
        parts.append(
            f'<text x="{tx:.1f}" y="{MARGIN_TOP - 22:.1f}" font-size="16" '
            f'font-weight="600" letter-spacing="1.0" fill="{SUBINK}" '
            f'text-anchor="{anchor}">{escape(stage_names[layer_idx].upper())}</text>'
        )

    # --- ribbons (drawn before nodes so nodes sit on top) ---
    parts.append('<g id="links">')
    ordered = sorted(links, key=lambda lk: -lk[2])
    endpoints: Dict[Tuple[str, str], Tuple[float, float, float, float, float]] = {}
    for s, t, vol in links:
        gs = geometry[s]
        gt = geometry[t]
        thick = gs["h"] * (vol / max(1e-9, gs["vol"]))
        x0 = gs["x"] + NODE_WIDTH
        y0 = gs["out_cursor"]
        x1 = gt["x"]
        y1 = gt["in_cursor"]
        gs["out_cursor"] += thick
        gt["in_cursor"] += thick
        endpoints[(s, t)] = (x0, y0, x1, y1, thick)

    for s, t, vol in ordered:
        x0, y0, x1, y1, thick = endpoints[(s, t)]
        # A ribbon carries the color of the root that dominates its *source*
        # node, so the origin story survives the whole cascade.
        root = dominant.get(s)
        color = root_color.get(root, _NEUTRAL_RIBBON) if root else _NEUTRAL_RIBBON
        chan_cls = f" sk-{_slug(root)}" if root else ""
        vol_txt = _fmt_k(vol)
        tip = f"{label_of[s]} → {label_of[t]}: {vol_txt} {volume_unit}"
        parts.append(
            f'<path class="link{chan_cls}" tabindex="0" role="img" '
            f'aria-label="{escape(tip)}" d="{_ribbon_path(x0, y0, x1, y1, thick)}" '
            f'fill="{color}" fill-opacity="0.55" stroke="#FFFFFF" stroke-width="1.25" '
            f'stroke-opacity="0.9">'
            f'<title>{escape(tip)}</title></path>'
        )
    parts.append("</g>")

    # --- nodes + labels ---
    parts.append('<g id="nodes">')
    for node_id, label, layer_idx in nodes:
        g = geometry[node_id]
        root = dominant.get(node_id)
        if root == node_id:
            ncol = root_color[node_id]
            node_cls = f" sk-{_slug(node_id)}"
        elif root is not None:
            ncol = root_color[root]
            node_cls = f" sk-{_slug(root)}"
        else:
            ncol = _NEUTRAL_NODE
            node_cls = ""
        vol_txt = _fmt_k(g["vol"])
        parts.append(
            f'<rect class="node{node_cls}" x="{g["x"]:.1f}" y="{g["y"]:.1f}" '
            f'width="{NODE_WIDTH}" height="{max(1.0, g["h"]):.1f}" rx="5" fill="{ncol}">'
            f'<title>{escape(label)}: {vol_txt} {volume_unit}</title></rect>'
        )
        cy = g["y"] + g["h"] / 2.0
        if layer_idx == n_layers - 1:
            lx = g["x"] - LABEL_GAP
            anchor = "end"
        else:
            lx = g["x"] + NODE_WIDTH + LABEL_GAP
            anchor = "start"
        parts.append(
            f'<text x="{lx:.1f}" y="{cy:.1f}" text-anchor="{anchor}">'
            f'<tspan x="{lx:.1f}" dy="-0.35em" font-size="19" '
            f'font-weight="600" fill="{INK}">{escape(label)}</tspan>'
            f'<tspan x="{lx:.1f}" dy="1.25em" font-family="{FONT_MONO}" '
            f'font-weight="400" fill="{SUBINK}" font-size="15">'
            f'{escape(vol_txt)}</tspan></text>'
        )
    parts.append("</g>")

    # --- footnote: read the hover affordance ---
    parts.append(
        f'<text x="{MARGIN_LEFT}" y="{HEIGHT - 20}" font-size="15" '
        f'fill="{SUBINK}">Ribbon width ∝ {volume_unit} · hover or focus a '
        f'flow to trace it</text>'
    )

    parts.append(fullscreen_control(WIDTH, HEIGHT, mode))
    parts.append("</svg>")
    return "".join(parts)


def make_sankey(
    data: List[Dict[str, Any]] | None = None,
    *,
    out: Path | str | None = None,
    title: str = "Organic search fills the funnel, but paid ads convert",
    subtitle: str = "One week of site visitors, from channel to outcome",
    desc: str | None = None,
    stage_names: List[str] | None = None,
    volume_unit: str = "visitors",
    mode: str = "self-contained",
    accessibility: str = "universal",
) -> Path:
    """Render a Sankey diagram and write it to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Flow rows with ``source`` (str), ``target`` (str), ``value``
        (float) keys. Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/sankey.svg``.
    title, subtitle : str
        Chart text.
    desc : str or None
        Accessible long description; auto-generated when not given.
    stage_names : list[str] or None
        One label per inferred layer/stage.
    volume_unit : str
        Unit word for tooltips and node counts.
    mode : str
        Interactivity mode for the fullscreen control.
    accessibility : str
        Palette accessibility level.

    Returns
    -------
    Path
        Absolute path to the written SVG file.

    Examples
    --------
    >>> p = make_sankey()
    >>> p.exists()
    True
    """
    svg = build_svg(
        data,
        title=title,
        subtitle=subtitle,
        desc=desc,
        stage_names=stage_names,
        volume_unit=volume_unit,
        mode=mode,
        accessibility=accessibility,
    )
    dest = Path(out) if out else svg_example_path(__file__, "sankey")
    return write_svg(dest, svg)


def main() -> None:
    """Write the Sankey SVG to the skill's example asset folder."""
    parser = argparse.ArgumentParser(description="Render the Sankey diagram SVG.")
    parser.add_argument(
        "--mode",
        choices=("self-contained", "external", "static"),
        default="self-contained",
        help="Interactivity mode for the fullscreen control.",
    )
    parser.add_argument(
        "--accessibility",
        choices=(
            "universal",
            "high-contrast",
            "monochrome",
            "deuteranopia",
            "protanopia",
            "tritanopia",
        ),
        default="universal",
        help="Palette accessibility level (default: universal, the CVD-safe standard).",
    )
    parser.add_argument("--out", default=None, help="Output path (defaults to the example asset).")
    args = parser.parse_args()
    make_sankey(out=args.out, mode=args.mode, accessibility=args.accessibility)


if __name__ == "__main__":
    main()
