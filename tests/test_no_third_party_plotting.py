"""
Guards against matplotlib / Vega / plotly / seaborn / graphviz re-entering
this package. Every figure here is authored as SVG directly, so a charting
library appearing anywhere in the source is a regression, not a choice.

Two sweeps, both over the whole tree rather than a hand-kept shortlist
(the shortlist version of this file guarded five scripts while 120 others
drifted):

* :func:`test_no_forbidden_imports` — no module imports one.
* :func:`test_no_plotting_library_mentions` — no module or shipped doc so
  much as names one, outside :data:`MENTION_ALLOWLIST`. That is what keeps
  the docstrings from quietly re-acquiring "previously rendered via ..."
  paragraphs the next time a generator is touched.

Rendering tests (SHAP explanations, the causal DAG, the forest plot) are
marked @pytest.mark.slow (they fit a real model / run real SVG assembly)
and excluded from the default run:

    pytest -m slow tests/

Author
------
Warith HARCHAOUI <warith.harchaoui@gmail.com>
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

_REPO_ROOT = Path(__file__).resolve().parent.parent

#: Every Python module that ships: the generators and shared helpers under
#: ``scripts/``, plus the library package. Collected by walking the tree, so
#: a new generator is covered the moment it lands.
_SOURCE_FILES = tuple(
    sorted(
        p
        for p in [
            *_SCRIPTS_DIR.rglob("*.py"),
            *(_REPO_ROOT / "sprezzature_figures").rglob("*.py"),
        ]
        if "__pycache__" not in p.parts
    )
)

#: Any spelling of a charting library, in prose or in code. ``pydot`` is
#: absent on purpose: it parses the DOT *format* for ``--dag x.dot`` and
#: draws nothing, unlike the ``graphviz`` binding beside it in the list.
_MENTION = re.compile(
    r"vega|vl_convert|vl-convert|plotly|matplotlib|pyplot|seaborn|bokeh"
    r"|altair|graphviz|\bd3\b|chart\.js|highcharts|echarts",
    re.IGNORECASE,
)

#: Files allowed to name a charting library, and why. Two legitimate
#: reasons only: a guard that must name what it forbids, and a competitive
#: landscape that must name what it is compared against. Paths are relative
#: to the repo root.
MENTION_ALLOWLIST: frozenset[str] = frozenset(
    {
        # This file: it cannot forbid a name without writing it.
        "tests/test_no_third_party_plotting.py",
        # Classifies a generator by backend so a non-conforming one is
        # flagged; the markers are the whole mechanism.
        "tools/audit_generators.py",
        # Its pack layout is a faithful port of a published algorithm whose
        # reference implementation is d3's ``packSiblings`` / ``packEnclose``.
        # Naming the source of ported code is provenance, not a dependency,
        # and stripping it while keeping the code would be the dishonest half.
        "scripts/make_circle-packing.py",
    }
)


@pytest.mark.parametrize("path", _SOURCE_FILES, ids=lambda p: p.name)
def test_no_forbidden_imports(path: Path) -> None:
    """No shipped module imports matplotlib / vl_convert / graphviz / plotly / seaborn."""
    relative = path.relative_to(_REPO_ROOT).as_posix()
    # Nothing is exempt from the import rule: the allowlist buys the right to
    # *name* a library in prose, never to import one.
    match = _FORBIDDEN_IMPORT.search(path.read_text(encoding="utf-8"))
    assert match is None, f"{relative} imports a forbidden plotting library: {match.group(0)!r}"


@pytest.mark.parametrize("path", _SOURCE_FILES, ids=lambda p: p.name)
def test_no_plotting_library_mentions(path: Path) -> None:
    """
    No shipped module so much as names a charting library.

    An import guard alone let 120 generators keep paragraphs like
    "previously rendered via Vega-Lite (``vl_convert``); this module now
    builds the ``<svg>`` markup by hand" — accurate history, but history
    the reader does not need and the stack no longer has.
    """
    relative = path.relative_to(_REPO_ROOT).as_posix()
    if relative in MENTION_ALLOWLIST:
        pytest.skip(f"{relative} is allowlisted")
    hits = sorted({m.group(0).lower() for m in _MENTION.finditer(path.read_text(encoding="utf-8"))})
    assert not hits, f"{relative} names a charting library: {', '.join(hits)}"


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
