"""
Tests that the three hand-authored-SVG figures adapted for user data
(waffle, dumbbell, sankey) actually work with arbitrary user data through
make_figure(), not just their own built-in DEMO_DATA. The project's
internal design plan explicitly calls this out for sankey, in §7
("ajouter des tests avec des données utilisateur", French for "add tests
with user data"); applied here to all three, since the same bug, data
hardcoded at module level and baked into build_svg instead of read from
the function argument, affected all of them before this fix.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sprezzature_figures import make_figure

pytestmark = pytest.mark.slow


def test_waffle_renders_with_user_data_not_summing_to_100(tmp_path: Path) -> None:
    data = [{"label": "A", "value": 7}, {"label": "B", "value": 3}]
    out = tmp_path / "waffle.svg"
    result = make_figure("waffle", data, out=str(out), title="Custom split")
    assert result.exists() and result.stat().st_size > 0
    svg = result.read_text(encoding="utf-8")
    assert "Custom split" in svg
    assert svg.count('class="tile cat-a"') + svg.count('class="tile cat-b"') > 0


def test_waffle_apportions_squares_to_sum_to_100_for_arbitrary_weights() -> None:
    import importlib.util

    from sprezzature_figures.make_figure import _SCRIPTS_DIR

    spec = importlib.util.spec_from_file_location("_t_waffle", _SCRIPTS_DIR / "make_waffle.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    colored = mod._with_colors([{"label": "A", "value": 1}, {"label": "B", "value": 2}, {"label": "C", "value": 7}], "universal")
    assert sum(d["squares"] for d in colored) == 100


def test_dumbbell_renders_with_user_data_and_custom_group_labels(tmp_path: Path) -> None:
    data = [
        {"category": "Q1", "group_a": 10, "group_b": 15},
        {"category": "Q2", "group_a": 20, "group_b": 12},
    ]
    out = tmp_path / "dumbbell.svg"
    result = make_figure(
        "dumbbell",
        data,
        out=str(out),
        title="Custom dumbbell",
        group_a_label="Before",
        group_b_label="After",
        value_prefix="",
        value_suffix=" units",
    )
    assert result.exists() and result.stat().st_size > 0
    svg = result.read_text(encoding="utf-8")
    assert "Before" in svg and "After" in svg
    assert "units" in svg


def test_sankey_renders_with_user_data_and_infers_layers(tmp_path: Path) -> None:
    data = [
        {"source": "A", "target": "B", "value": 10},
        {"source": "A", "target": "C", "value": 5},
        {"source": "B", "target": "D", "value": 8},
        {"source": "C", "target": "D", "value": 5},
    ]
    out = tmp_path / "sankey.svg"
    result = make_figure(
        "sankey",
        data,
        out=str(out),
        title="Custom flow",
        subtitle="test flow",
        volume_unit="items",
    )
    assert result.exists() and result.stat().st_size > 0
    svg = result.read_text(encoding="utf-8")
    assert "Custom flow" in svg
    assert "STAGE 1" in svg and "STAGE 3" in svg  # auto-layered, not the DEMO_DATA stage names
    assert "items" in svg


def test_sankey_auto_layers_a_linear_chain() -> None:
    import importlib.util

    from sprezzature_figures.make_figure import _SCRIPTS_DIR

    spec = importlib.util.spec_from_file_location("_t_sankey", _SCRIPTS_DIR / "make_sankey.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    data = [
        {"source": "start", "target": "middle", "value": 1},
        {"source": "middle", "target": "end", "value": 1},
    ]
    nodes, links = mod._nodes_and_links(data)
    layer_of = {n: layer for n, _label, layer in nodes}
    assert layer_of == {"start": 0, "middle": 1, "end": 2}
