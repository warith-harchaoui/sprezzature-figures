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


def test_list_kinds_catalogue() -> None:
    """list_kinds returns a sorted, non-empty list of >=80 kinds that
    includes the well-known chart types."""
    kinds = list_kinds()
    assert isinstance(kinds, list)
    assert len(kinds) >= 80
    assert kinds == sorted(kinds)
    for expected in ("treemap", "sankey", "venn", "wordcloud", "funnel"):
        assert expected in kinds, f"Expected kind {expected!r} missing from list_kinds()"


def test_make_figure_unknown_kind_raises_with_available_list() -> None:
    """An unrecognised kind raises ValueError naming the failure and the
    count of available kinds."""
    with pytest.raises(ValueError) as exc:
        make_figure("nonexistent_chart_xyz_abc", [])
    message = str(exc.value)
    assert "No script for kind" in message
    assert "Available (" in message


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


@pytest.mark.parametrize("kind", ["treemap", "funnel"])
def test_demo_data_exists(kind: str) -> None:
    """Each shipped generator script must expose non-empty DEMO_DATA."""
    data = _load_demo_data(kind)
    assert len(data) >= 1, f"make_{kind}.DEMO_DATA is empty"


@pytest.mark.slow
@pytest.mark.parametrize("kind", ["treemap", "funnel"])
def test_stable_kind_renders_to_png(kind: str, tmp_path: Path) -> None:
    """make_figure(..., out='*.png') produces a non-empty file on disk."""
    data = _load_demo_data(kind)
    out = tmp_path / f"{kind}.png"
    result = make_figure(kind, data, out=str(out))
    assert Path(result).exists(), f"Output file not created: {result}"
    assert Path(result).stat().st_size > 0


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


def test_make_figure_hyphenated_legacy_kind_warns_and_raises() -> None:
    """Regression for the hyphen/underscore dispatcher bug plus the non-stable
    warning contract, on a single realistic call.

    make_figure() must locate scripts/make_connected-scatter.py for
    kind='connected-scatter' (previously it looked for a nonexistent
    make_connected_scatter.py and raised a misleading "no script" ValueError).
    It still fails today because the script has no make_connected_scatter()
    yet -- but the failure must be AttributeError (contract gap), not
    ValueError (file not found), and a status='legacy' UserWarning must fire
    before the failure.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(AttributeError, match="make_connected_scatter"):
            make_figure("connected-scatter", [], out="/tmp/should-not-exist.svg")
    assert any("status='legacy'" in str(w.message) for w in caught)


def test_get_figure_definition_exposed_from_make_figure() -> None:
    """make_figure re-exports the registry lookup."""
    d = get_figure_definition("treemap")
    assert d.kind == "treemap"
    assert d.status == "stable"


def test_missing_required_role_is_flagged_and_raised() -> None:
    """validate_figure_input reports a missing required role as an error, and
    make_figure refuses to render (ValueError) rather than calling a generator
    with invalid data."""
    rows = [{"parent": "A", "name": "A1"}]  # missing 'value'
    issues = validate_figure_input("treemap", rows)
    assert any(i.field == "value" and i.severity == "error" for i in issues)
    with pytest.raises(ValueError, match="value"):
        make_figure("treemap", rows, out="/tmp/should-not-exist.svg")


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
