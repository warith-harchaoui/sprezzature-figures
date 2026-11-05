"""
``explain_model`` has one default for how many rows it explains.

``--n-explain`` defaulted to 500, and so did the SHAP and Shapash paths, but
``run_lime`` fell back to 10 when ``ctx`` had no ``n_explain``. The command
line always passes one, so no run of the script ever saw the 10: only a
library caller did, and got fifty times fewer explanations than the help
text promised. One constant now feeds the flag and every engine.

The LIME check runs ``run_lime`` against a stub ``lime`` package so it
counts explained rows without paying for 500 real LIME fits.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

import ast
import sys
import types
from pathlib import Path
from typing import Any

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

import explain_model  # noqa: E402


def test_the_flag_defaults_to_the_constant() -> None:
    args = explain_model.build_parser().parse_args(["--model", "m.pkl", "--data", "x.csv"])
    assert args.n_explain == explain_model.DEFAULT_N_EXPLAIN == 500


def test_no_engine_has_a_fallback_of_its_own() -> None:
    """Every ``ctx.get("n_explain", …)`` falls back to the constant, not a literal."""
    tree = ast.parse((_SCRIPTS_DIR / "explain_model.py").read_text(encoding="utf-8"))
    fallbacks = [
        node.args[1]
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and len(node.args) == 2
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "n_explain"
    ]
    assert len(fallbacks) >= 3, "the regex-free walk found fewer engines than exist"
    literal = [ast.unparse(f) for f in fallbacks if not (isinstance(f, ast.Name) and f.id == "DEFAULT_N_EXPLAIN")]
    assert literal == []


def test_run_lime_without_n_explain_explains_the_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    np = pytest.importorskip("numpy")
    explained: list[int] = []

    class _Explanation:
        def save_to_file(self, path: str) -> None:
            Path(path).write_text("<html></html>", encoding="utf-8")

    class _Explainer:
        def __init__(self, **_: Any) -> None:
            pass

        def explain_instance(self, row: Any, *_: Any, **__: Any) -> _Explanation:
            explained.append(1)
            return _Explanation()

    lime = types.ModuleType("lime")
    tabular = types.ModuleType("lime.lime_tabular")
    tabular.LimeTabularExplainer = _Explainer  # type: ignore[attr-defined]
    lime.lime_tabular = tabular  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "lime", lime)
    monkeypatch.setitem(sys.modules, "lime.lime_tabular", tabular)

    class _Model:
        def predict_proba(self, x: Any) -> Any:
            return np.zeros((len(x), 2))

    data = np.zeros((explain_model.DEFAULT_N_EXPLAIN + 20, 3))
    summary = explain_model.run_lime(_Model(), data, {"out": tmp_path})
    assert summary["n_explained"] == explain_model.DEFAULT_N_EXPLAIN
    assert len(explained) == explain_model.DEFAULT_N_EXPLAIN
