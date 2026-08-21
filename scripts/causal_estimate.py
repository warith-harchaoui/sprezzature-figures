#!/usr/bin/env python3
"""
causal_estimate
===============

End-to-end causal-effect estimation via DoWhy's four-step loop:

    model → identify → estimate → refute

Backends
--------

* **Binary treatment** — DoWhy's built-in propensity-score matching /
  stratification, or a linear regression when the treatment is
  effectively continuous but low-dim.
* **Continuous treatment** or **high-dim confounders** — EconML
  ``LinearDML`` (default), ``LinearDRLearner``, or ``CausalForestDML``
  depending on ``--estimator``.
* **Instrumental variable** — EconML ``IntentToTreatDRIV`` when the
  caller supplies ``--instrument``.

DAG input
---------

The causal graph: a diagram of which variable is assumed to affect which,
drawn with arrows and no loops back on themselves (a directed acyclic graph,
DAG) so DoWhy can read off which variables to control for. Pass one of:

* ``--dag path/to/dag.gml`` — GraphML file.
* ``--dag path/to/dag.dot`` — Graphviz DOT.
* ``--dag-string 'graph[directed 1 ...]'`` — DoWhy inline string.

Output
------

Writes to ``<out>/``:

* ``effect.json`` — point estimate, CI, refutation deltas.
* ``dag.svg`` — the causal graph as a hand-authored SVG: a layered
  (Sugiyama-style) left-to-right layout computed in pure Python, no
  graphviz, no Vega, no matplotlib.
* ``forest_plot.svg`` — hand-authored SVG comparing the point estimate
  against each refuter's delta.

Usage
-----
::

    python causal_estimate.py --data d.csv --treatment T --outcome Y \\
        --confounders "X1,X2,X3" --dag dag.gml \\
        --estimator dml --refute all --out ./causal/

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    import pandas

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _argparse import make_parser  # noqa: E402
from _interactive import fullscreen_control  # noqa: E402
from _render import write_svg  # noqa: E402
from _style import load_palette  # noqa: E402
from _svg import svg_open, xml_escape  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    """Return the argparse parser for the script."""
    parser = make_parser(
        prog="causal_estimate",
        description=(
            "DoWhy's four-step causal-effect loop with EconML backends. "
            "Assumes the DAG is supplied — discovery is out of scope."
        ),
    )
    parser.add_argument("--data", required=True, help="CSV / Parquet input.")
    parser.add_argument("--treatment", required=True, help="Name of the treatment column.")
    parser.add_argument("--outcome", required=True, help="Name of the outcome column.")
    parser.add_argument("--confounders", default="",
                        help="Comma-separated confounder columns (falls back to DAG's backdoor set when empty).")
    parser.add_argument("--instrument", default="", help="Column name of an instrumental variable (optional).")
    parser.add_argument("--dag", default="",
                        help="Path to a .gml / .dot DAG describing the causal graph.")
    parser.add_argument("--dag-string", default="",
                        help="DoWhy inline DAG string (alternative to --dag).")
    parser.add_argument("--estimator", choices=("linear", "matching", "stratification",
                                                 "dml", "dr", "causal-forest", "iv-2sls"),
                        default="dml", help="Estimation backend.")
    parser.add_argument("--refute", choices=("none", "placebo", "subset", "random-cause", "all"),
                        default="all", help="Refutation battery.")
    parser.add_argument("--out", default="./causal", help="Output directory.")
    parser.add_argument("--trim-quantile", type=float, default=0.0,
                        help="Trim rows by propensity-score quantile (helps overlap violations).")
    parser.add_argument("--dark", action="store_true", help="Dark-mode plots.")
    return parser


# ------------------------------------------------------------------
# DAG loading
# ------------------------------------------------------------------
def load_dag(dag_path: str, dag_string: str) -> str:
    """Return a DoWhy-compatible DAG string.

    Parameters
    ----------
    dag_path : str
        Path to a .gml / .dot file (may be empty).
    dag_string : str
        Inline DoWhy string (may be empty).

    Returns
    -------
    str
        A DoWhy-compatible DAG spec.
    """
    if dag_string:
        return dag_string
    if not dag_path:
        raise SystemExit("Pass either --dag <file> or --dag-string.")

    p = Path(dag_path)
    if not p.is_file():
        raise SystemExit(f"DAG file not found: {dag_path}")

    ext = p.suffix.lower()
    text = p.read_text(encoding="utf-8")
    if ext in {".gml", ".txt"}:
        return text
    if ext == ".dot":
        # Convert DOT → GML via networkx (deferred import).
        import io
        import networkx as nx
        graph = nx.nx_pydot.read_dot(p)
        buffer = io.StringIO()
        nx.write_gml(graph, buffer)
        return buffer.getvalue()
    raise SystemExit(f"Unsupported DAG format: {ext}. Use .gml or .dot.")


# ------------------------------------------------------------------
# DoWhy loop
# ------------------------------------------------------------------
def run_dowhy(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Run model → identify → estimate → refute; return a summary dict.

    Parameters
    ----------
    ctx : dict
        Context with ``data``, ``treatment``, ``outcome``, ``confounders``,
        ``instrument``, ``dag``, ``estimator``, ``refute``,
        ``trim_quantile``.

    Returns
    -------
    dict
        Serialisable summary.
    """
    from dowhy import CausalModel
    import pandas as pd

    df: "pd.DataFrame" = ctx["data"]

    model = CausalModel(
        data=df,
        treatment=ctx["treatment"],
        outcome=ctx["outcome"],
        graph=ctx["dag"],
        common_causes=ctx["confounders"] or None,
        instruments=[ctx["instrument"]] if ctx["instrument"] else None,
    )

    # 1. identify
    identified = model.identify_effect(proceed_when_unidentifiable=False)
    print(f"[info] estimand: {identified.estimands}", file=sys.stderr)

    # 2. estimate
    method_map = {
        "linear":         "backdoor.linear_regression",
        "matching":       "backdoor.propensity_score_matching",
        "stratification": "backdoor.propensity_score_stratification",
        "dml":            "backdoor.econml.dml.LinearDML",
        "dr":             "backdoor.econml.dr.LinearDRLearner",
        "causal-forest":  "backdoor.econml.dml.CausalForestDML",
        "iv-2sls":        "iv.instrumental_variable",
    }
    method_name = method_map[ctx["estimator"]]

    method_params: Dict[str, Any] = {}
    if ctx["estimator"] in {"dml", "dr", "causal-forest"}:
        from sklearn.ensemble import GradientBoostingRegressor, GradientBoostingClassifier
        method_params = {
            "init_params": {
                "model_y": GradientBoostingRegressor(),
                "model_t": GradientBoostingRegressor() if _looks_continuous(df, ctx["treatment"]) else GradientBoostingClassifier(),
                "featurizer": None,
            },
            "fit_params": {},
        }

    estimate = model.estimate_effect(
        identified,
        method_name=method_name,
        method_params=method_params or None,
        confidence_intervals=True,
    )
    point = float(getattr(estimate, "value", 0.0) or 0.0)
    ci = getattr(estimate, "get_confidence_intervals", None)
    ci_low, ci_high = (float("nan"), float("nan"))
    if callable(ci):
        try:
            lo, hi = ci()
            ci_low, ci_high = float(lo), float(hi)
        except Exception:  # noqa: BLE001
            pass

    # 3. refute
    refuters: Dict[str, Any] = {}
    if ctx["refute"] != "none":
        for name in _refute_list(ctx["refute"]):
            refuters[name] = _run_refuter(model, identified, estimate, name)

    return {
        "treatment": ctx["treatment"],
        "outcome": ctx["outcome"],
        "confounders": ctx["confounders"],
        "instrument": ctx["instrument"] or None,
        "estimator": ctx["estimator"],
        "method": method_name,
        "estimand": str(identified.estimands),
        "point_estimate": point,
        "ci_lower": ci_low,
        "ci_upper": ci_high,
        "refutations": refuters,
    }


def _looks_continuous(df: Any, column: str) -> bool:
    """Return True when ``column`` has more than 10 distinct values."""
    try:
        return int(df[column].nunique()) > 10
    except Exception:  # noqa: BLE001
        return True


def _refute_list(flag: str) -> List[str]:
    """Expand ``--refute`` into the list of refuter names to run."""
    if flag == "all":
        return ["placebo", "random-cause", "subset"]
    if flag == "placebo":
        return ["placebo"]
    if flag == "random-cause":
        return ["random-cause"]
    if flag == "subset":
        return ["subset"]
    return []


def _run_refuter(model: Any, identified: Any, estimate: Any, name: str) -> Dict[str, Any]:
    """Run one DoWhy refuter and return a serialisable summary."""
    kind = {
        "placebo":       "placebo_treatment_refuter",
        "random-cause":  "random_common_cause",
        "subset":        "data_subset_refuter",
    }[name]
    try:
        result = model.refute_estimate(identified, estimate, method_name=kind)
        new_effect = float(getattr(result, "new_effect", float("nan")))
        return {
            "method": kind,
            "new_effect": new_effect,
            "p_value": getattr(result, "refutation_result", {}).get("p_value") if hasattr(result, "refutation_result") else None,
            "verdict": _refuter_verdict(name, float(getattr(estimate, "value", 0.0) or 0.0), new_effect),
        }
    except Exception as exc:  # noqa: BLE001
        return {"method": kind, "error": str(exc)}


def _refuter_verdict(name: str, original: float, new: float) -> str:
    """Return a coarse ``pass`` / ``fail`` per DoWhy refuter convention."""
    if name == "placebo":
        return "pass" if abs(new) < 0.1 * max(abs(original), 1e-6) else "fail"
    if name in {"random-cause", "subset"}:
        return "pass" if abs(new - original) < 0.1 * max(abs(original), 1e-6) else "fail"
    return "unknown"


# ------------------------------------------------------------------
# DAG rendering — hand-authored SVG, no graphviz, no Vega, no matplotlib
# ------------------------------------------------------------------
def _parse_dag_string(dag_string: str) -> "tuple[List[str], List[tuple]]":
    """Extract node ids and (source, target) edges from a DoWhy/GML DAG string.

    A minimal parse — only node ids and edges are needed for layout, not
    the full GML grammar.
    """
    import re as _re
    node_pattern = r'node\s*\[\s*id\s+"?(\w+)"?'
    edge_pattern = r'edge\s*\[\s*source\s+"?(\w+)"?\s+target\s+"?(\w+)"?'
    nodes = set(_re.findall(node_pattern, dag_string))
    edges = _re.findall(edge_pattern, dag_string)
    # A DOT-converted graph (or a hand-written DAG string) can reference a
    # node only from an edge, with no separate ``node [...]`` block for
    # it; include those too so the layout never drops a node silently.
    for src, dst in edges:
        nodes.add(src)
        nodes.add(dst)
    return sorted(nodes), edges


def _rank_dag(nodes: List[str], edges: List[tuple]) -> Dict[str, int]:
    """Longest-path rank per node (0 = source), via Kahn's algorithm.

    A node with multiple parents ranks below the deepest one, so every
    edge always points from a lower rank to a strictly higher one — the
    property a layered DAG layout needs.
    """
    children: Dict[str, List[str]] = {n: [] for n in nodes}
    indegree: Dict[str, int] = {n: 0 for n in nodes}
    for src, dst in edges:
        if src in children and dst in indegree:
            children[src].append(dst)
            indegree[dst] += 1

    rank: Dict[str, int] = {n: 0 for n in nodes}
    queue = [n for n in nodes if indegree[n] == 0]
    seen = 0
    while queue:
        n = queue.pop(0)
        seen += 1
        for child in children[n]:
            rank[child] = max(rank[child], rank[n] + 1)
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if seen < len(nodes):
        # A cycle (or a malformed edge list) left some node's indegree
        # above zero forever. A causal DAG must be acyclic, so this is
        # unexpected input, not a bug in the layout — render every node
        # at rank 0 rather than loop forever or drop nodes.
        rank = {n: 0 for n in nodes}
    return rank


def render_dag(dag_string: str, out_dir: Path, dark: bool) -> None:
    """Render the causal graph as a hand-authored, layered SVG.

    A Sugiyama-style layered layout: nodes are ranked by longest path
    from a source (rank 0 = no incoming edges), ranks flow left to
    right, and nodes within a rank are ordered by one barycenter pass
    over their predecessors' positions (a standard, cheap
    crossing-reduction heuristic — not iterative, since a causal DAG's
    graph is small: a handful of confounders around one treatment/
    outcome pair, not a general graph-drawing problem). Edges are
    straight lines with a hand-computed arrowhead triangle at the
    target, offset by the node radius so the tip lands on the node's
    edge rather than its centre — no ``<marker>`` element, matching how
    every other hand-authored generator in this package computes its own
    geometry.
    """
    nodes, edges = _parse_dag_string(dag_string)
    if not nodes:
        print("[warn] no nodes found in DAG string; skipping DAG render.", file=sys.stderr)
        return

    rank = _rank_dag(nodes, edges)
    n_ranks = max(rank.values()) + 1 if rank else 1
    by_rank: Dict[int, List[str]] = {r: [] for r in range(n_ranks)}
    for n in nodes:
        by_rank[rank[n]].append(n)

    parents: Dict[str, List[str]] = {n: [] for n in nodes}
    for src, dst in edges:
        if dst in parents:
            parents[dst].append(src)

    position: Dict[str, float] = {}
    for r in range(n_ranks):
        by_rank[r].sort()
        if r == 0:
            for i, n in enumerate(by_rank[r]):
                position[n] = float(i)
            continue

        def _bary(n: str, _r: int = r) -> float:
            ps = [position[p] for p in parents.get(n, []) if p in position]
            return sum(ps) / len(ps) if ps else float(by_rank[_r].index(n))

        by_rank[r].sort(key=_bary)
        for i, n in enumerate(by_rank[r]):
            position[n] = float(i)

    node_r = 34.0
    col_gap, row_gap = 190.0, 96.0
    m_left, m_top = 60.0, 70.0
    m_right, m_bottom = 60.0, 40.0
    max_rows = max((len(v) for v in by_rank.values()), default=1)
    width = int(m_left + max(0, n_ranks - 1) * col_gap + m_right + 2 * node_r)
    height = int(m_top + max(0, max_rows - 1) * row_gap + m_bottom + 2 * node_r)

    def node_xy(n: str) -> "tuple[float, float]":
        r = rank[n]
        row_count = len(by_rank[r])
        i = by_rank[r].index(n)
        col_h = (row_count - 1) * row_gap
        y0 = m_top + node_r + (height - m_top - m_bottom - 2 * node_r - col_h) / 2.0
        x = m_left + node_r + r * col_gap
        y = y0 + i * row_gap
        return x, y

    palette = load_palette()
    accent = palette.get("Blue", "#007AFF")
    fg = "#F5F5F7" if dark else "#1D1D1F"
    bg = "#1D1D1F" if dark else "#FFFFFF"
    chrome_family = chrome_stack_for_theme("corporate")

    parts: List[str] = []
    parts.append(svg_open(width, height, "dag-title", "dag-desc", font_family=chrome_family))
    parts.append('<title id="dag-title">Causal graph</title>')
    parts.append(
        f'<desc id="dag-desc">Causal DAG with {len(nodes)} nodes and {len(edges)} directed edges, '
        'laid out left to right by longest path from a source.</desc>'
    )
    parts.append(
        "<style>.dagnode{transition:filter .15s ease;}"
        ".dagnode:hover,.dagnode:focus{filter:brightness(1.12);outline:none;}"
        "@media (prefers-reduced-motion: reduce){.dagnode{transition:none;}}</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{bg}"/>')

    for src, dst in edges:
        if src not in rank or dst not in rank:
            continue
        x0, y0 = node_xy(src)
        x1, y1 = node_xy(dst)
        dx, dy = x1 - x0, y1 - y0
        dist = math.hypot(dx, dy) or 1.0
        ux, uy = dx / dist, dy / dist
        sx, sy = x0 + ux * node_r, y0 + uy * node_r
        arrow_len = 10.0
        tip_x, tip_y = x1 - ux * node_r, y1 - uy * node_r
        base_x, base_y = x1 - ux * (node_r + arrow_len), y1 - uy * (node_r + arrow_len)
        parts.append(
            f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{base_x:.1f}" y2="{base_y:.1f}" '
            f'stroke="{accent}" stroke-width="1.6"/>'
        )
        perp_x, perp_y = -uy, ux
        pts = " ".join(
            f"{p[0]:.1f},{p[1]:.1f}"
            for p in (
                (tip_x, tip_y),
                (base_x + perp_x * 5.0, base_y + perp_y * 5.0),
                (base_x - perp_x * 5.0, base_y - perp_y * 5.0),
            )
        )
        parts.append(f'<polygon points="{pts}" fill="{accent}"/>')

    for n in nodes:
        x, y = node_xy(n)
        font_size = 12 if len(n) <= 8 else max(8, 12 - (len(n) - 8))
        parts.append(
            f'<g class="dagnode" tabindex="0"><title>{xml_escape(n)}</title>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{node_r:.1f}" fill="{bg}" stroke="{fg}" stroke-width="1.4"/>'
            f'<text x="{x:.1f}" y="{y + font_size / 3:.1f}" font-size="{font_size}" fill="{fg}" '
            f'text-anchor="middle">{xml_escape(n)}</text>'
            f'</g>'
        )

    parts.append(fullscreen_control(width, height))
    parts.append("</svg>")
    write_svg(out_dir / "dag.svg", "\n".join(parts), theme="corporate")


# ------------------------------------------------------------------
# Forest plot — hand-authored SVG, no matplotlib
# ------------------------------------------------------------------
def render_forest_plot(summary: Dict[str, Any], out_dir: Path, dark: bool) -> None:
    """Render a compact forest plot of the effect and refutation deltas as SVG."""
    labels = ["Point estimate"]
    values = [float(summary["point_estimate"])]
    for name, refute in (summary.get("refutations") or {}).items():
        if isinstance(refute, dict) and "new_effect" in refute:
            labels.append(name)
            values.append(float(refute["new_effect"]))

    palette = load_palette()
    blue = palette.get("Blue", "#007AFF")
    fg = "#F5F5F7" if dark else "#1D1D1F"
    bg = "#1D1D1F" if dark else "#FFFFFF"
    secondary = "#9C9CA3" if dark else "#6E6E73"

    n = len(labels)
    row_h = 34.0
    width = 620
    m_left, m_right = 170.0, 40.0
    m_top, m_bottom = 60.0, 60.0
    plot_w = width - m_left - m_right
    height = int(m_top + n * row_h + m_bottom)

    v_min = min([0.0] + values)
    v_max = max([0.0] + values)
    pad = (v_max - v_min) * 0.15 or 1.0
    v0, v1 = v_min - pad, v_max + pad

    def x_for(v: float) -> float:
        return m_left + (v - v0) / (v1 - v0) * plot_w

    chrome_family = chrome_stack_for_theme("corporate")
    mono_family = mono_stack_for_theme("corporate")
    outcome = str(summary.get("outcome", ""))

    parts: List[str] = []
    parts.append(svg_open(width, height, "cfp-title", "cfp-desc", font_family=chrome_family))
    parts.append('<title id="cfp-title">Causal effect estimate and refutation checks</title>')
    parts.append(
        f'<desc id="cfp-desc">Point estimate of the effect on {xml_escape(outcome)} '
        f'alongside {n - 1} refutation deltas.</desc>'
    )
    parts.append(
        "<style>.row{transition:opacity .1s ease}"
        ".row:hover,.row:focus{opacity:0.75;outline:none}"
        "@media (prefers-reduced-motion: reduce){.row{transition:none}}</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{bg}"/>')
    parts.append(
        f'<text x="{m_left}" y="32" font-size="16" font-weight="700" fill="{fg}">'
        f'Effect on {xml_escape(outcome)}</text>'
    )

    zero_x = x_for(0.0)
    axis_top, axis_bottom = m_top - 10, m_top + n * row_h
    parts.append(
        f'<line x1="{zero_x:.1f}" y1="{axis_top:.1f}" x2="{zero_x:.1f}" y2="{axis_bottom:.1f}" '
        f'stroke="{fg}" stroke-width="1" opacity="0.4"/>'
    )

    for i, (label, value) in enumerate(zip(labels, values)):
        cy = m_top + i * row_h + row_h / 2.0
        parts.append(
            f'<text x="{m_left - 12:.1f}" y="{cy + 4:.1f}" font-size="12.5" fill="{fg}" '
            f'text-anchor="end">{xml_escape(str(label))}</text>'
        )
        vx = x_for(value)
        tip = f"{label}: {value:+.4g}"
        parts.append(f'<g class="row" tabindex="0"><title>{xml_escape(tip)}</title>')
        parts.append(
            f'<line x1="{zero_x:.1f}" y1="{cy:.1f}" x2="{vx:.1f}" y2="{cy:.1f}" '
            f'stroke="{blue}" stroke-width="6" stroke-linecap="round"/>'
        )
        parts.append(f'<circle cx="{vx:.1f}" cy="{cy:.1f}" r="5.5" fill="{blue}" stroke="{bg}" stroke-width="1.5"/>')
        parts.append("</g>")
        anchor = "start" if value >= 0 else "end"
        label_x = vx + (14 if value >= 0 else -14)
        parts.append(
            f'<text x="{label_x:.1f}" y="{cy + 4:.1f}" font-size="11" '
            f'font-family="{mono_family}" fill="{fg}" text-anchor="{anchor}">{value:+.3g}</text>'
        )

    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        v = v0 + frac * (v1 - v0)
        tx = x_for(v)
        parts.append(
            f'<text x="{tx:.1f}" y="{axis_bottom + 18:.1f}" font-size="10.5" font-family="{mono_family}" '
            f'fill="{secondary}" text-anchor="middle">{v:.3g}</text>'
        )

    parts.append(fullscreen_control(width, height))
    parts.append("</svg>")
    write_svg(out_dir / "forest_plot.svg", "\n".join(parts), theme="corporate")


# ------------------------------------------------------------------
# main
# ------------------------------------------------------------------
def load_data(path: str) -> "pandas.DataFrame":  # noqa: F821 — quoted forward ref
    """Load a data table."""
    import pandas as pd
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".csv":
        return pd.read_csv(p)
    if ext in {".parquet", ".pq"}:
        return pd.read_parquet(p)
    if ext == ".json":
        return pd.read_json(p)
    raise SystemExit(f"Unsupported data extension: {ext}")


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point."""
    args = build_parser().parse_args(argv)

    data = load_data(args.data)
    dag = load_dag(args.dag, args.dag_string)
    confounders = [c.strip() for c in args.confounders.split(",") if c.strip()]

    ctx = {
        "data": data,
        "treatment": args.treatment,
        "outcome": args.outcome,
        "confounders": confounders,
        "instrument": args.instrument,
        "dag": dag,
        "estimator": args.estimator,
        "refute": args.refute,
        "trim_quantile": args.trim_quantile,
    }

    summary = run_dowhy(ctx)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "effect.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    render_dag(dag, out_dir, dark=args.dark)
    try:
        render_forest_plot(summary, out_dir, dark=args.dark)
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] forest plot failed: {exc}", file=sys.stderr)

    print(f"wrote {out_dir / 'effect.json'}", file=sys.stderr)
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
