"""
Tests for sprezzature_figures.catalog: loading the registry, resolving a
chart kind's aliases (alternate names that should still find the right
generator), and checking that every scripts/make_*.py generator has a
matching catalog entry.

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


def test_resolve_kind_handles_aliases_and_unknowns() -> None:
    """A canonical kind resolves from every alias spelling (case, hyphen,
    underscore, space interchangeable); an unknown name resolves to None."""
    for spelling in ("connected-scatter", "connected_scatter", "connected scatter", "Connected-Scatter"):
        assert resolve_kind(spelling) == "connected-scatter"
    assert resolve_kind("totally-not-a-chart") is None


def test_get_figure_definition_contract() -> None:
    """get_figure_definition decouples the kind string from the backing module
    and callable, reflects promotion status, and errors helpfully for unknowns.
    """
    # Hyphenated kind: module/callable are recorded explicitly, not guessed.
    cs = get_figure_definition("connected-scatter")
    assert cs.module == "scripts/make_connected-scatter.py"
    assert cs.callable_name == "make_connected_scatter"
    # Regression: sankey used to expose only build_svg()/main(), no
    # make_sankey() (plan §7). Now rewritten to take real data and promoted.
    sankey = get_figure_definition("sankey")
    assert sankey.callable_name == "make_sankey"
    assert sankey.status == "stable"
    # Unknown kind raises, listing how many are available.
    with pytest.raises(ValueError, match=r"Available \(\d+\)"):
        get_figure_definition("nonexistent_chart_xyz")


def test_stable_kinds_have_stable_status_and_required_roles() -> None:
    """Every kind returned by list_kinds(status='stable') actually carries the
    'stable' status, and declares required_roles so a future recommendation
    engine can match it to real data (plan §1.5: a figure is only GUI-eligible
    once its contract, including roles, is known).
    """
    stable = list_kinds(status="stable")
    assert stable
    for kind in stable:
        d = get_figure_definition(kind)
        assert d.status == "stable"
        assert d.required_roles, f"{kind} is stable but declares no required_roles"
