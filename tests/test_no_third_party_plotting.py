"""
Guards against matplotlib / Vega / plotly / seaborn re-entering the
scripts that were migrated to hand-authored SVG: explain_model.py,
causal_estimate.py, render_diagram.py, ralph_eyeball_loop.py, _style.py.

Rendering tests (SHAP explanations, the causal DAG, the forest plot) are
marked @pytest.mark.slow (they fit a real model / run real SVG assembly)
and excluded from the default run:

    pytest -m slow tests/

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from xml.dom import minidom

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

_FORBIDDEN_IMPORT = re.compile(
    r"^\s*(import\s+(matplotlib|vl_convert|graphviz|plotly|seaborn)\b"
    r"|from\s+(matplotlib|vl_convert|graphviz|plotly|seaborn)\b)",
    re.MULTILINE,
)

_MIGRATED_SCRIPTS = (
    "explain_model.py",
    "causal_estimate.py",
    "render_diagram.py",
    "ralph_eyeball_loop.py",
    "_style.py",
)


@pytest.mark.parametrize("filename", _MIGRATED_SCRIPTS)
def test_no_forbidden_imports(filename: str) -> None:
    """None of the migrated scripts import matplotlib / vl_convert / graphviz / plotly / seaborn."""
    text = (_SCRIPTS_DIR / filename).read_text(encoding="utf-8")
    match = _FORBIDDEN_IMPORT.search(text)
    assert match is None, f"{filename} still imports a forbidden plotting library: {match.group(0)!r}"


def test_render_diagram_kinds_drop_vega() -> None:
    """render_diagram.py's KINDS no longer lists vega."""
    import render_diagram

    assert "vega" not in render_diagram.KINDS
    assert set(render_diagram.KINDS) == {"tikz", "mermaid", "svg"}


@pytest.mark.slow
def test_run_shap_writes_valid_matplotlib_free_svgs(tmp_path: Path) -> None:
    """run_shap fits a tiny model and writes real, valid, matplotlib-free SVGs."""
    pd = pytest.importorskip("pandas")
    pytest.importorskip("shap")
    sklearn_ensemble = pytest.importorskip("sklearn.ensemble")
    import explain_model as em
    import numpy as np

    rng = np.random.RandomState(0)
    X = pd.DataFrame({
        "f1": rng.normal(size=80),
        "f2": rng.normal(size=80),
    })
    y = X["f1"] * 2 - X["f2"] + rng.normal(scale=0.1, size=80)
    model = sklearn_ensemble.RandomForestRegressor(n_estimators=10, random_state=0).fit(X, y)

    ctx = {
        "out": tmp_path, "n_background": 15, "n_explain": 20, "top_n": 2,
        "dark": False, "waterfall_row": None, "link": "identity",
    }
    summary = em.run_shap(model, X, ctx)

    assert summary["engine"] == "shap"
    bar = tmp_path / "summary_bar.svg"
    beeswarm = tmp_path / "summary_beeswarm.svg"
    waterfall = tmp_path / f"waterfall_row_{summary['waterfall_row']}.svg"
    for svg_path in (bar, beeswarm, waterfall):
        assert svg_path.is_file(), f"{svg_path} was not written"
        text = svg_path.read_text(encoding="utf-8")
        assert "matplotlib" not in text.lower()
        minidom.parse(str(svg_path))  # raises on invalid XML


@pytest.mark.slow
def test_render_dag_is_valid_layered_svg(tmp_path: Path) -> None:
    """render_dag lays out a small DAG with the correct node/edge count, no graphviz."""
    import causal_estimate as ce

    dag = (
        'graph [ directed 1 '
        'node [ id "T" ] node [ id "Y" ] node [ id "X1" ] '
        'edge [ source "X1" target "T" ] '
        'edge [ source "X1" target "Y" ] '
        'edge [ source "T" target "Y" ] ]'
    )
    ce.render_dag(dag, tmp_path, dark=False)

    svg_path = tmp_path / "dag.svg"
    assert svg_path.is_file()
    text = svg_path.read_text(encoding="utf-8")
    assert "graphviz" not in text.lower()
    minidom.parse(str(svg_path))
    assert text.count('class="dagnode"') == 3
    assert text.count("<polygon") == 3  # one arrowhead per edge


@pytest.mark.slow
def test_render_forest_plot_is_valid_svg(tmp_path: Path) -> None:
    """render_forest_plot writes a valid, matplotlib-free SVG from a summary dict."""
    import causal_estimate as ce

    summary = {
        "outcome": "Y",
        "point_estimate": 1.2,
        "refutations": {"placebo": {"new_effect": 0.01}},
    }
    ce.render_forest_plot(summary, tmp_path, dark=False)

    svg_path = tmp_path / "forest_plot.svg"
    assert svg_path.is_file()
    text = svg_path.read_text(encoding="utf-8")
    assert "matplotlib" not in text.lower()
    minidom.parse(str(svg_path))


def test_rank_dag_topological_order() -> None:
    """_rank_dag assigns strictly increasing ranks along every edge."""
    import causal_estimate as ce

    nodes = ["X1", "X2", "T", "Y"]
    edges = [("X1", "T"), ("X2", "T"), ("X1", "Y"), ("X2", "Y"), ("T", "Y")]
    rank = ce._rank_dag(nodes, edges)

    for src, dst in edges:
        assert rank[src] < rank[dst], f"edge {src}->{dst} does not increase rank"
    assert rank["X1"] == 0 and rank["X2"] == 0
    assert rank["Y"] == max(rank.values())
