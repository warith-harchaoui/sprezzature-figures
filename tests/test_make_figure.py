"""
Tests for the make_figure dispatcher and list_kinds utility.

Slow tests (those that render actual figures) are marked with @pytest.mark.slow
and excluded from the default pytest run. Run them explicitly with:

    pytest -m slow tests/

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from sprezzature_figures.make_figure import list_kinds, make_figure


def test_list_kinds_returns_nonempty_list() -> None:
    """list_kinds must return at least 80 chart types."""
    kinds = list_kinds()
    assert isinstance(kinds, list)
    assert len(kinds) >= 80


def test_list_kinds_contains_common_charts() -> None:
    """Spot-check that well-known chart types are present."""
    kinds = set(list_kinds())
    for expected in ("treemap", "sankey", "venn", "wordcloud", "funnel"):
        assert expected in kinds, f"Expected kind {expected!r} missing from list_kinds()"


def test_list_kinds_is_sorted() -> None:
    """list_kinds must return kinds in alphabetical order."""
    kinds = list_kinds()
    assert kinds == sorted(kinds)


def test_make_figure_unknown_kind_raises() -> None:
    """make_figure must raise ValueError for an unrecognised kind."""
    with pytest.raises(ValueError, match="No script for kind"):
        make_figure("nonexistent_chart_xyz_abc", [])


def test_make_figure_unknown_kind_lists_available() -> None:
    """The ValueError message must include a count of available kinds."""
    with pytest.raises(ValueError, match=r"Available \(\d+\)"):
        make_figure("nonexistent_chart_xyz_abc", [])


def _load_demo_data(kind: str) -> list:
    """Load DEMO_DATA from a make_<kind>.py script without calling make_figure."""
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    normalised = kind.replace("-", "_")
    candidate = scripts_dir / f"make_{normalised}.py"
    if not candidate.exists():
        return []
    spec = importlib.util.spec_from_file_location(f"_test_load_{normalised}", candidate)
    if spec is None or spec.loader is None:
        return []
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"_test_load_{normalised}"] = mod
    try:
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
    except Exception:
        return []
    return getattr(mod, "DEMO_DATA", [])


def test_demo_data_exists_for_treemap() -> None:
    """make_treemap.py must expose non-empty DEMO_DATA."""
    data = _load_demo_data("treemap")
    assert len(data) >= 1, "make_treemap.DEMO_DATA is empty"


def test_demo_data_exists_for_funnel() -> None:
    """make_funnel.py must expose non-empty DEMO_DATA."""
    data = _load_demo_data("funnel")
    assert len(data) >= 1, "make_funnel.DEMO_DATA is empty"


@pytest.mark.slow
def test_make_figure_treemap_renders(tmp_path: Path) -> None:
    """make_figure('treemap', ...) must produce a file on disk."""
    data = _load_demo_data("treemap")
    out = tmp_path / "treemap.png"
    result = make_figure("treemap", data, out=str(out))
    assert Path(result).exists(), f"Output file not created: {result}"
    assert Path(result).stat().st_size > 0


@pytest.mark.slow
def test_make_figure_funnel_renders(tmp_path: Path) -> None:
    """make_figure('funnel', ...) must produce a file on disk."""
    data = _load_demo_data("funnel")
    out = tmp_path / "funnel.png"
    result = make_figure("funnel", data, out=str(out))
    assert Path(result).exists()
