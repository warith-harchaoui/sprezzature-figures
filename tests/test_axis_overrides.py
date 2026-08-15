"""
Tests for the explicit axis-override kwargs: `_scale.fixed_step_ticks`, the
`vmin`/`vmax` color-scale override on `make_heatmap`, and the
`x_domain`/`x_tick_step`/`y_domain`/`y_tick_step`/`y_minor_step` axis
overrides on `make_line_multi`. Left at their defaults, every one of these
generators must render byte-identical to its pre-override output -- that
invariant is the main thing under test, alongside the actual override
behaviour.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from _scale import fixed_step_ticks  # noqa: E402
from make_heatmap import build_svg as heatmap_build_svg  # noqa: E402


def _load_module(stem: str):
    """Import a hyphenated `make_<stem>.py` (not a valid module name for a
    plain `import` statement) by file path."""
    spec = importlib.util.spec_from_file_location(f"_test_{stem}", SCRIPTS_DIR / f"make_{stem}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"_test_{stem}"] = mod
    spec.loader.exec_module(mod)
    return mod


line_multi_build_svg = _load_module("line-multi").build_svg


# ---------------------------------------------------------------------------
# _scale.fixed_step_ticks
# ---------------------------------------------------------------------------


def test_fixed_step_ticks_hits_both_ends_when_step_divides_evenly() -> None:
    ticks = fixed_step_ticks(-1.6, 1.6, 0.2)
    assert ticks[0] == -1.6
    assert ticks[-1] == 1.6
    assert len(ticks) == 17


def test_fixed_step_ticks_never_overshoots_hi() -> None:
    """Regression: a naive round() of the tick count could push the last
    tick past `hi` when `step` does not evenly divide `hi - lo` (e.g. a
    24-hour axis ticked every 3 units from a 23-inclusive domain), placing
    a gridline/label outside the plotted axis."""
    ticks = fixed_step_ticks(0, 23, 3)
    assert ticks == [0.0, 3.0, 6.0, 9.0, 12.0, 15.0, 18.0, 21.0]
    assert max(ticks) <= 23


def test_fixed_step_ticks_empty_for_invalid_range_or_step() -> None:
    assert fixed_step_ticks(1, 0, 0.1) == []
    assert fixed_step_ticks(0, 10, 0) == []
    assert fixed_step_ticks(0, 10, -1) == []


# ---------------------------------------------------------------------------
# make_heatmap: vmin/vmax
# ---------------------------------------------------------------------------


def test_heatmap_default_vmin_vmax_matches_data_range() -> None:
    default_svg = heatmap_build_svg()
    explicit_svg = heatmap_build_svg(vmin=None, vmax=None)
    assert default_svg == explicit_svg


def test_heatmap_vmin_vmax_override_the_legend_range() -> None:
    svg = heatmap_build_svg(vmin=0, vmax=100)
    assert ">100<" in svg
    assert ">0<" in svg


# ---------------------------------------------------------------------------
# make_line-multi: x_domain/x_tick_step/y_domain/y_tick_step/y_minor_step
# ---------------------------------------------------------------------------


def test_line_multi_default_axis_kwargs_match_unset_kwargs() -> None:
    default_svg = line_multi_build_svg()
    explicit_svg = line_multi_build_svg(
        x_domain=None, x_tick_step=None, y_domain=None, y_tick_step=None, y_minor_step=None,
    )
    assert default_svg == explicit_svg


def test_line_multi_x_tick_step_respects_x_domain_bound() -> None:
    svg = line_multi_build_svg(x_domain=(0, 23), x_tick_step=3)
    assert ">24<" not in svg
    assert ">21<" in svg


def test_line_multi_y_domain_and_tick_step_label_the_axis() -> None:
    svg = line_multi_build_svg(y_domain=(0, 140), y_tick_step=20)
    assert ">140<" in svg
    assert ">0<" in svg


def test_line_multi_y_minor_step_requires_y_domain() -> None:
    """A minor step with no domain is a no-op (nothing to walk between),
    not an error -- same fallback contract as x_tick_step/y_tick_step."""
    svg = line_multi_build_svg(y_minor_step=10)
    assert svg == line_multi_build_svg()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
