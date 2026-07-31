"""
Tests for sprezzature_figures.catalog: registry loading, alias resolution,
and that every scripts/make_*.py generator has a matching entry.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sprezzature_figures.catalog import (
    FigureDefinition,
    get_figure_definition,
    get_registry,
    list_kinds,
    resolve_kind,
)

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"


def test_registry_loads_and_validates() -> None:
    entries = get_registry()
    assert len(entries) >= 80
    assert all(isinstance(e, FigureDefinition) for e in entries)


def test_every_generator_script_has_a_registry_entry() -> None:
    on_disk = {p.stem[len("make_") :] for p in SCRIPTS_DIR.glob("make_*.py") if p.stem != "make_figure"}
    registered = {e.kind for e in get_registry()}
    missing = on_disk - registered
    assert not missing, f"generator scripts missing from figures.json: {sorted(missing)}"


def test_hyphenated_kind_resolves_via_all_alias_spellings() -> None:
    for spelling in ("connected-scatter", "connected_scatter", "connected scatter", "Connected-Scatter"):
        assert resolve_kind(spelling) == "connected-scatter"


def test_resolve_kind_returns_none_for_unknown() -> None:
    assert resolve_kind("totally-not-a-chart") is None


def test_get_figure_definition_reports_module_and_callable_for_hyphenated_kind() -> None:
    d = get_figure_definition("connected-scatter")
    assert d.module == "scripts/make_connected-scatter.py"
    assert d.callable_name == "make_connected_scatter"


def test_get_figure_definition_unknown_kind_raises_with_available_list() -> None:
    with pytest.raises(ValueError, match=r"Available \(\d+\)"):
        get_figure_definition("nonexistent_chart_xyz")


def test_sankey_registered_as_legacy_missing_make_callable() -> None:
    d = get_figure_definition("sankey")
    assert d.callable_name == "make_sankey"
    assert d.status == "legacy"


def test_list_kinds_stable_matches_registry_status() -> None:
    stable = list_kinds(status="stable")
    assert stable
    for kind in stable:
        assert get_figure_definition(kind).status == "stable"


def test_stable_figures_declare_required_roles() -> None:
    """Figures already on the make_<kind> contract should have role metadata
    so a future recommendation engine can match them to real data (plan §1.5:
    a figure is only GUI-eligible once its contract, including roles, is known).
    """
    for kind in list_kinds(status="stable"):
        d = get_figure_definition(kind)
        assert d.required_roles, f"{kind} is stable but declares no required_roles"
