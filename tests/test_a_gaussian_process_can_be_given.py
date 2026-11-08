"""The Gaussian-process figure draws a posterior somebody else computed.

What was missing. ``gaussian-process`` fitted its own posterior, an RBF
kernel with fixed hyper-parameters, to whatever ``x, y`` it was handed. A
caller holding the posterior of its own model (a structure search's kernel,
a sum of periodic and linear parts, a component of it) could not draw that
posterior at all: the figure would have replaced it with an RBF fit of the
same points, under the same title.

Rows carrying ``mean`` and ``sd`` are now that posterior, drawn as given on
their ``x`` grid. The tests below check that nothing is refitted, that no
sample draws are invented (there is no covariance to draw them from), that
the observed range is ruled when the grid leaves it, and that the demo is
unchanged.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

from sprezzature_figures import check_render, make_figure

REPO_ROOT = Path(__file__).resolve().parent.parent
GENERATOR = REPO_ROOT / "scripts" / "make_gaussian-process.py"


def _load() -> Any:
    """Load the generator module from its file, as make_figure does.

    Returns
    -------
    module
        The generator.
    """
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("make_gaussian_process", GENERATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rows() -> list[dict[str, Any]]:
    """A straight-line posterior on 0..10, observed on 2..8 only.

    Returns
    -------
    list of dict
        Grid rows with mean and sd, then observation rows.
    """
    grid = [
        {"x": float(t), "y": None, "mean": 2.0 * t, "sd": 0.5 + 0.1 * abs(t - 5)}
        for t in range(11)
    ]
    points = [
        {"x": float(t), "y": 2.0 * t + 0.3, "mean": None, "sd": None}
        for t in range(2, 9)
    ]
    return grid + points


def test_the_given_mean_is_the_drawn_mean() -> None:
    """A straight given mean comes out as a straight path, not refitted."""
    gp = _load()
    svg = gp.build_svg(_rows(), title="Given", subtitle="A given posterior")
    mean_path = re.search(r'<path tabindex="0" d="([^"]+)"', svg)
    assert mean_path is not None
    ys = [float(pair.split(",")[1]) for pair in mean_path.group(1)[2:].split(" L ")]
    steps = [b - a for a, b in zip(ys, ys[1:], strict=False)]
    # Coordinates are written to 0.1 px, so equal steps differ by at most 0.1.
    assert max(steps) - min(steps) <= 0.11, f"a straight given mean was redrawn as a curve: {steps}"


def test_no_sample_draws_are_invented() -> None:
    """A given posterior has no covariance, so no sample draws are drawn."""
    gp = _load()
    svg = gp.build_svg(_rows(), title="Given", subtitle="A given posterior")
    assert gp.COLOR_SAMPLE not in svg
    assert "RBF kernel" not in svg


def test_the_extrapolation_is_ruled_and_named() -> None:
    """Both edges of the observed range are ruled and labelled."""
    gp = _load()
    svg = gp.build_svg(_rows(), title="Given", subtitle="A given posterior")
    assert svg.count('stroke-dasharray="3 3"') == 2
    assert svg.count(">extrapolation</text>") == 2


def test_the_axis_titles_reach_the_figure() -> None:
    """x_label and y_label title the axes."""
    gp = _load()
    svg = gp.build_svg(_rows(), x_label="Year", y_label="Passengers")
    assert ">Year</text>" in svg
    assert ">Passengers</text>" in svg


def test_make_figure_accepts_rows_without_an_observation(tmp_path: Path) -> None:
    """Grid rows with no y pass validation and render cleanly.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Pytest's temporary directory.
    """
    out = make_figure(
        "gaussian-process",
        _rows(),
        out=str(tmp_path / "given.svg"),
        title="A given posterior",
        subtitle="Mean and 95% band as computed by the caller",
    )
    svg = Path(out).read_text()
    assert not check_render(svg, expected_title="A given posterior")


def test_the_demo_still_fits_its_own() -> None:
    """Without given rows the demo fits its RBF posterior and draws three samples."""
    gp = _load()
    svg = gp.build_svg()
    assert svg.count(f'stroke="{gp.COLOR_SAMPLE}"') == 3
    assert "extrapolation" not in svg


def test_without_a_fit_the_data_are_drawn_alone() -> None:
    """fit=False draws the observed series only: no band, no samples."""
    gp = _load()
    rows = [{"x": float(t), "y": float(t % 3)} for t in range(100)]
    svg = gp.build_svg(rows, title="Data", subtitle="Raw", fit=False)
    assert "Observed series of 100 points" in svg
    assert gp.COLOR_BAND not in svg
    assert gp.COLOR_SAMPLE not in svg
