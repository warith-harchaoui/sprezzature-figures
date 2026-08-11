#!/usr/bin/env python3
"""
make_clustermap — a house-styled clustered heatmap (clustermap) as hand-authored SVG.

A heatmap whose rows and columns are reordered by hierarchical clustering,
with a small dendrogram guide along each axis showing the merge structure
that produced the order. The dendrograms let the reader see cluster
membership and how tight each cluster is (branch height), while the
reordered grid itself puts similar rows and columns next to each other so
blocks of high/low value pop out visually. Typical uses: gene-expression
matrices, correlated-feature discovery, customer-segment x product
affinity.

Previously rendered via Vega-Lite (the clustering ran offline and only the
resulting row/column sort order was baked into the spec, with no
dendrogram drawn at all); this module now computes the clustering itself
-- average-linkage hierarchical agglomeration on Euclidean distance,
implemented from scratch -- and draws both the reordered grid and a real
dendrogram along each axis by hand. No Vega, no matplotlib, no scipy.
Every cell carries a native ``<title>`` tooltip.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _svg import svg_open, viridis, xml_escape  # noqa: E402
from _style import BG, INK, SECONDARY  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme  # noqa: E402

DENDRO_COLOR = "#8E8E93"

_RAMP: Tuple[Tuple[float, str], ...] = (
    (0.00, "#EAF3FF"), (0.25, "#9CC7FF"), (0.55, "#3E9BFF"),
    (0.80, "#007AFF"), (1.00, "#0A4DA0"),
)


def _ramp_hex(t: float, theme: str = "corporate") -> str:
    """Sample the sequential ramp at position ``t`` in ``[0, 1]``.

    ``theme="academic"`` swaps to the shared viridis colormap
    (:func:`_svg.viridis`); the default (``"corporate"``) keeps this
    generator's own tuned blue ramp, unchanged.
    """
    if theme == "academic":
        return viridis(t)
    t = min(1.0, max(0.0, t))
    for (lo_t, lo_c), (hi_t, hi_c) in zip(_RAMP, _RAMP[1:]):
        if lo_t <= t <= hi_t:
            local = (t - lo_t) / (hi_t - lo_t) if hi_t > lo_t else 0.0
            ar, ag, ab = int(lo_c[1:3], 16), int(lo_c[3:5], 16), int(lo_c[5:7], 16)
            br, bg, bb = int(hi_c[1:3], 16), int(hi_c[3:5], 16), int(hi_c[5:7], 16)
            r = round(ar + (br - ar) * local)
            g = round(ag + (bg - ag) * local)
            b = round(ab + (bb - ab) * local)
            return f"#{r:02X}{g:02X}{b:02X}"
    return _RAMP[-1][1]


ROWS = [f"g{i}" for i in range(8)]
COLS = [f"s{i}" for i in range(6)]


def _make_demo_data() -> List[Dict[str, Any]]:
    """Eight synthetic "genes" x six synthetic "samples", with two loose
    row-blocks and two loose column-blocks baked in so the clustering has
    real structure to find."""
    rng = random.Random(13)
    row_block = {f"g{i}": (0 if i < 4 else 1) for i in range(8)}
    col_block = {f"s{i}": (0 if i < 3 else 1) for i in range(6)}
    rows: List[Dict[str, Any]] = []
    for r in ROWS:
        for c in COLS:
            base = 6.0 if row_block[r] == col_block[c] else 1.5
            rows.append({"row": r, "col": c, "value": round(max(0.0, rng.gauss(base, 1.1)), 2)})
    return rows


DEMO_DATA: List[Dict[str, Any]] = _make_demo_data()


def _euclidean(a: List[float], b: List[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _cluster(labels: List[str], vectors: Dict[str, List[float]]) -> List[Dict[str, Any]]:
    """Average-linkage agglomerative clustering, implemented from scratch.

    Returns the list of merge events in order, each
    ``{"id", "left", "right", "height"}`` where ``left``/``right`` are
    either a leaf label or an earlier merge's ``id``. The final merge's
    ``id`` is the root.
    """
    members: Dict[str, List[str]] = {label: [label] for label in labels}
    active = list(labels)
    merges: List[Dict[str, Any]] = []
    next_id = 0
    while len(active) > 1:
        best: Optional[Tuple[float, str, str]] = None
        for i in range(len(active)):
            for j in range(i + 1, len(active)):
                a, b = active[i], active[j]
                pair_dists = [_euclidean(vectors[x], vectors[y]) for x in members[a] for y in members[b]]
                d = sum(pair_dists) / len(pair_dists)
                if best is None or d < best[0]:
                    best = (d, a, b)
        d, a, b = best  # type: ignore[misc]
        new_id = f"_c{next_id}"
        next_id += 1
        merges.append({"id": new_id, "left": a, "right": b, "height": d})
        members[new_id] = members[a] + members[b]
        active = [x for x in active if x not in (a, b)] + [new_id]
    return merges


def _leaf_order(merges: List[Dict[str, Any]], labels: List[str]) -> List[str]:
    """Flatten the dendrogram to a leaf order by walking the root's
    left/right subtrees recursively."""
    by_id = {m["id"]: m for m in merges}

    def walk(node: str) -> List[str]:
        if node in by_id:
            m = by_id[node]
            return walk(m["left"]) + walk(m["right"])
        return [node]

    root = merges[-1]["id"] if merges else labels[0]
    return walk(root)


def _dendrogram_positions(
    merges: List[Dict[str, Any]], order: List[str],
) -> Tuple[Dict[str, float], Dict[str, float], float]:
    """Assign each leaf and merge a position along the leaf axis (index-based,
    0-centered on its slot) and a height. Returns ``(position, height, max_height)``.
    """
    position: Dict[str, float] = {label: i + 0.5 for i, label in enumerate(order)}
    height: Dict[str, float] = dict.fromkeys(order, 0.0)
    for m in merges:
        position[m["id"]] = (position[m["left"]] + position[m["right"]]) / 2.0
        height[m["id"]] = m["height"]
    max_height = max((m["height"] for m in merges), default=1.0) or 1.0
    return position, height, max_height


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Clustered Expression Matrix",
    subtitle: str = "Rows and columns reordered by average-linkage hierarchical clustering",
    width: int = 620,
    height: int = 560,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full clustermap SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``row`` (str), ``col`` (str), ``value`` (numeric).
        Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    mode : str, optional
        Forwarded to :func:`_interactive.fullscreen_control`.
    accessibility : str, optional
        Accepted for CLI parity but a documented no-op: the ramp is a
        single mono-hue blue scale, already colour-vision-deficiency-safe
        by construction (magnitude reads by lightness alone).
    theme : str, optional
        Visual theme: ``"corporate"`` (default, Roboto -- byte-identical to
        the pre-theme render) or ``"academic"`` (LaTeX-style Latin Modern).
        See :func:`sprezzature_figures.fonts.chrome_stack_for_theme`.

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    _ = accessibility
    rows = data if data else DEMO_DATA
    row_labels = sorted({r["row"] for r in rows})
    col_labels = sorted({r["col"] for r in rows})
    lookup: Dict[Tuple[str, str], float] = {(r["row"], r["col"]): float(r["value"]) for r in rows}

    row_vectors = {r: [lookup.get((r, c), 0.0) for c in col_labels] for r in row_labels}
    col_vectors = {c: [lookup.get((r, c), 0.0) for r in row_labels] for c in col_labels}
    row_merges = _cluster(row_labels, row_vectors)
    col_merges = _cluster(col_labels, col_vectors)
    row_order = _leaf_order(row_merges, row_labels)
    col_order = _leaf_order(col_merges, col_labels)
    row_pos, row_height, row_max_h = _dendrogram_positions(row_merges, row_order)
    col_pos, col_height, col_max_h = _dendrogram_positions(col_merges, col_order)

    all_vals = list(lookup.values())
    v_min, v_max = (min(all_vals), max(all_vals)) if all_vals else (0.0, 1.0)
    v_span = (v_max - v_min) or 1.0

    dendro_top, dendro_left = 72.0, 40.0
    grid_x = dendro_left + 56.0
    grid_y = 134.0
    # Reserve a label gutter, sized to the actual tick text, between each
    # dendrogram and its axis labels -- without it, a merge whose height
    # maps close to the axis runs its bracket line straight through the
    # row/column label text (measured, not a fixed guess, since callers can
    # pass arbitrary label text via `data`).
    row_label_gutter = max((len(str(r)) for r in row_order), default=1) * 10 * 0.62 + 10.0
    col_label_gutter = 16.0
    right_margin, bottom_margin = 30.0, 40.0
    grid_w = width - grid_x - right_margin
    grid_h = height - grid_y - bottom_margin
    cell_w = grid_w / len(col_order)
    cell_h = grid_h / len(row_order)

    parts: List[str] = []
    parts.append(svg_open(width, height, "cm-title", "cm-desc", font_family=chrome_stack_for_theme(theme)))
    parts.append(f'<title id="cm-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="cm-desc">Clustermap of {len(row_order)} rows and {len(col_order)} columns, '
        f'values {v_min:.1f} to {v_max:.1f}. Hover or focus a cell for its exact value.</desc>'
    )
    parts.append(
        "<style>"
        ".cell{transition:stroke-width .1s ease;}"
        ".cell:hover,.cell:focus{stroke:#1D1D1F;stroke-width:1.5;outline:none;}"
        "@media (prefers-reduced-motion: reduce){.cell{transition:none;}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="20" y="34" font-size="19" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(f'<text x="20" y="54" font-size="12" fill="{SECONDARY}">{xml_escape(subtitle)}</text>')

    # ---- column dendrogram (above the grid) ----
    col_dendro_h = grid_y - dendro_top - 4.0 - col_label_gutter

    def cx_for(pos: float) -> float:
        return grid_x + pos * cell_w

    def cy_for_col(h: float) -> float:
        return dendro_top + col_dendro_h - (h / col_max_h * col_dendro_h)

    for m in col_merges:
        xl, xr = cx_for(col_pos[m["left"]]), cx_for(col_pos[m["right"]])
        yl = cy_for_col(col_height.get(m["left"], 0.0))
        yr = cy_for_col(col_height.get(m["right"], 0.0))
        ym = cy_for_col(m["height"])
        parts.append(
            f'<path d="M {xl:.1f},{yl:.1f} L {xl:.1f},{ym:.1f} L {xr:.1f},{ym:.1f} L {xr:.1f},{yr:.1f}" '
            f'fill="none" stroke="{DENDRO_COLOR}" stroke-width="1.2"/>'
        )

    # ---- row dendrogram (left of the grid) ----
    row_dendro_w = grid_x - dendro_left - 4.0 - row_label_gutter

    def cy_for(pos: float) -> float:
        return grid_y + pos * cell_h

    def cx_for_row(h: float) -> float:
        return dendro_left + row_dendro_w - (h / row_max_h * row_dendro_w)

    for m in row_merges:
        yl, yr = cy_for(row_pos[m["left"]]), cy_for(row_pos[m["right"]])
        xl = cx_for_row(row_height.get(m["left"], 0.0))
        xr = cx_for_row(row_height.get(m["right"], 0.0))
        xm = cx_for_row(m["height"])
        parts.append(
            f'<path d="M {xl:.1f},{yl:.1f} L {xm:.1f},{yl:.1f} L {xm:.1f},{yr:.1f} L {xr:.1f},{yr:.1f}" '
            f'fill="none" stroke="{DENDRO_COLOR}" stroke-width="1.2"/>'
        )

    # ---- grid ----
    for ri, r in enumerate(row_order):
        for ci, c in enumerate(col_order):
            value = lookup.get((r, c), 0.0)
            t = (value - v_min) / v_span
            x = grid_x + ci * cell_w
            y = grid_y + ri * cell_h
            tip = f"{r} x {c}: {value:.2f}"
            parts.append(
                f'<rect class="cell" tabindex="0" x="{x:.1f}" y="{y:.1f}" '
                f'width="{cell_w:.1f}" height="{cell_h:.1f}" fill="{_ramp_hex(t, theme)}" '
                f'stroke="{BG}" stroke-width="1"><title>{xml_escape(tip)}</title></rect>'
            )

    # ---- axis labels ----
    for ci, c in enumerate(col_order):
        tx = grid_x + ci * cell_w + cell_w / 2
        parts.append(
            f'<text x="{tx:.1f}" y="{grid_y - 8:.1f}" font-size="10" fill="{SECONDARY}" '
            f'text-anchor="middle">{xml_escape(c)}</text>'
        )
    for ri, r in enumerate(row_order):
        ty = grid_y + ri * cell_h + cell_h / 2 + 3
        parts.append(
            f'<text x="{grid_x - 8:.1f}" y="{ty:.1f}" font-size="10" fill="{SECONDARY}" '
            f'text-anchor="end">{xml_escape(r)}</text>'
        )

    # ---- legend ----
    ly = height - 14.0
    lx0 = grid_x
    parts.append(f'<text x="{lx0:.1f}" y="{ly:.1f}" font-size="10" fill="{SECONDARY}">{v_min:.1f}</text>')
    swatch_x = lx0 + 26.0
    n_swatches = 8
    for i in range(n_swatches):
        t = i / (n_swatches - 1)
        parts.append(f'<rect x="{swatch_x + i * 14:.1f}" y="{ly - 10:.1f}" width="12" height="11" fill="{_ramp_hex(t, theme)}"/>')
    parts.append(
        f'<text x="{swatch_x + n_swatches * 14 + 6:.1f}" y="{ly:.1f}" font-size="10" '
        f'fill="{SECONDARY}">{v_max:.1f}</text>'
    )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_clustermap(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Clustered Expression Matrix",
    subtitle: str = "Rows and columns reordered by average-linkage hierarchical clustering",
    width: int = 620,
    height: int = 560,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored clustermap and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``row`` (str), ``col`` (str), ``value`` (float).
        Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/clustermap.svg``.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
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
    >>> p = make_clustermap()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility, theme=theme)
    dest = Path(out) if out else svg_example_path(__file__, "clustermap")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "clustermap", build_svg, description="Generate a clustered heatmap (clustermap).")


if __name__ == "__main__":
    main()
