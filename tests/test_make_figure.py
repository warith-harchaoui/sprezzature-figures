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
import warnings
from pathlib import Path

import pytest

from sprezzature_figures.catalog import list_kinds as registry_list_kinds
from sprezzature_figures.make_figure import (
    get_figure_definition,
    list_kinds,
    make_figure,
    validate_figure_input,
)


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


@pytest.mark.slow
@pytest.mark.parametrize("kind", registry_list_kinds(status="stable"))
def test_every_stable_kind_renders_from_registry(kind: str, tmp_path: Path) -> None:
    """Every kind the registry marks 'stable' must render its own DEMO_DATA.

    Parametrized off the registry itself (not a hardcoded pair of names) so
    this test automatically covers new figures as more are promoted to
    'stable', instead of needing a new hand-written test per generator.
    """
    data = _load_demo_data(kind)
    assert data, f"{kind} is marked stable but exposes no DEMO_DATA"
    out = tmp_path / f"{kind}.svg"
    result = make_figure(kind, data, out=str(out))
    assert Path(result).exists() and Path(result).stat().st_size > 0


def test_make_figure_reaches_hyphenated_scripts_now() -> None:
    """Regression test for the hyphen/underscore dispatcher bug: make_figure()
    must locate scripts/make_connected-scatter.py for kind='connected-scatter'
    (previously it looked for a nonexistent make_connected_scatter.py and
    raised a misleading "no script" ValueError). It still fails today because
    the script itself has no make_connected_scatter() yet -- but the failure
    must be AttributeError (contract gap), not ValueError (file not found).
    """
    with pytest.raises(AttributeError, match="make_connected_scatter"):
        make_figure("connected-scatter", [], out="/tmp/should-not-exist.svg")


def test_make_figure_warns_on_non_stable_kind() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(AttributeError):
            make_figure("sankey", [], out="/tmp/should-not-exist.svg")
    assert any("status='legacy'" in str(w.message) for w in caught)


def test_get_figure_definition_exposed_from_make_figure() -> None:
    d = get_figure_definition("treemap")
    assert d.kind == "treemap"
    assert d.status == "stable"


def test_validate_figure_input_flags_missing_required_role() -> None:
    issues = validate_figure_input("treemap", [{"parent": "A", "name": "A1"}])  # missing 'value'
    assert any(i.field == "value" and i.severity == "error" for i in issues)


def test_make_figure_raises_on_missing_required_role() -> None:
    with pytest.raises(ValueError, match="value"):
        make_figure("treemap", [{"parent": "A", "name": "A1"}], out="/tmp/should-not-exist.svg")


def test_make_figure_falls_back_to_deprecated_path_for_unregistered_script(tmp_path: Path) -> None:
    """A generator script that exists on disk but was never added to
    figures.json must still work via the deprecated filename-guessing
    fallback, with a DeprecationWarning -- never a hard failure.
    """
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    throwaway = scripts_dir / "make_test_throwaway_kind.py"
    throwaway.write_text(
        "from pathlib import Path\n"
        "DEMO_DATA = [{'x': 1}]\n"
        "def make_test_throwaway_kind(data, *, out=None, title=''):\n"
        "    p = Path(out)\n"
        "    p.write_text('ok')\n"
        "    return p\n",
        encoding="utf-8",
    )
    try:
        out = tmp_path / "throwaway.svg"
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = make_figure("test_throwaway_kind", [{"x": 1}], out=str(out))
        assert Path(result).exists()
        assert any(issubclass(w.category, DeprecationWarning) for w in caught)
    finally:
        throwaway.unlink(missing_ok=True)
