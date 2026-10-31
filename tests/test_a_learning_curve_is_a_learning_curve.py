"""The demo data behind the learning curve behaves like a learning curve.

The defect this guards. ``make_learning-curve.py`` shipped two straight
lines in ``log2(n)``: training ``0.995 - 0.0055 * doublings``, validation
``0.742 + 0.0265 * doublings``. They looked right at the scale a chart is
read, and three impossible things followed from the algebra.

* Linear in the log of ``n`` never flattens. Every doubling buys exactly
  what the last one bought, for ever, so that validation line reaches
  accuracy ``1.0000`` at 213 000 examples and goes on past it.
* The gap closed at ``0.032`` per doubling from ``0.253``, so validation
  overtook training at about 60 000 examples -- a model scoring better on
  data it has never seen. The last point plotted was 32 000. The curves did
  not avoid the crossing; the x-axis stopped one doubling short of it, and a
  comment in the generator claimed the case had been designed out.
* The figure exists to answer whether the last doubling still bought
  anything. On a line, the slope over the final doubling is the slope
  everywhere. The one number the chart was built to deliver could not vary,
  and the "flat" verdict the generator knows how to write was unreachable
  from its own demo.

Nothing could notice. The SVG rendered, the curves were monotone over the
plotted range, and every property that failed did so either outside the
x-axis or in a derivative no test took.

So this asserts the shape rather than the formula. It reads the rows the
module ships -- ``DEMO_DATA``, after rounding and fold noise -- because that
is what gets drawn, and a correct closed form with a rounding step that
breaks monotonicity would still ship a wrong picture. The extrapolation
tests are the exception and call the generator directly: the point of those
is what happens at training sizes no chart plots.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GENERATOR = REPO_ROOT / "scripts" / "make_learning-curve.py"

#: Training sizes far past anything a chart plots. A learning curve's
#: impossible behaviour lives in its tail: the old lines were monotone and
#: well separated everywhere the demo looked, and crossed one doubling after
#: it stopped looking. 2.4e11 is about every labelled image on Earth.
_ABSURD_SIZES = (1.0e5, 1.0e6, 1.0e8, 2.4e11)


@pytest.fixture(scope="module")
def generator() -> Any:
    """The generator module, loaded by path because its name has a hyphen."""
    spec = importlib.util.spec_from_file_location("make_learning_curve", GENERATOR)
    assert spec and spec.loader, f"cannot load {GENERATOR}"
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(GENERATOR.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(GENERATOR.parent))
    return module


def _means(rows: list[dict[str, Any]], split: str) -> list[tuple[float, float]]:
    """Mean score per training size for one split, ascending by size."""
    per_size: dict[float, list[float]] = {}
    for row in rows:
        if row["split"] == split:
            per_size.setdefault(float(row["size"]), []).append(float(row["score"]))
    assert per_size, f"the demo data carries no {split!r} rows"
    return sorted((size, sum(v) / len(v)) for size, v in per_size.items())


def test_every_score_is_a_score(generator: Any) -> None:
    """No fold of either split scores outside ``(0, 1)``.

    Including the noise, not just the means: the band is drawn from the
    fold-to-fold extremes, so it is an extreme that would be the first thing
    to leave the interval.
    """
    out_of_range = [
        (row["size"], row["split"], row["fold"], row["score"])
        for row in generator.DEMO_DATA
        if not 0.0 < float(row["score"]) < 1.0
    ]
    assert not out_of_range, f"score(s) outside (0, 1): {out_of_range}"


def test_validation_climbs_and_training_falls(generator: Any) -> None:
    """More data helps the held-out score and hurts the fitted one.

    The second half is the part that is easy to get backwards. A training
    score that rises with more data describes a model that memorises better
    the more there is to memorise.
    """
    validation = _means(generator.DEMO_DATA, "Validation")
    training = _means(generator.DEMO_DATA, "Training")
    for name, series, want_rising in (
        ("Validation", validation, True),
        ("Training", training, False),
    ):
        for (small, lower), (large, higher) in zip(series, series[1:], strict=False):
            rising = higher > lower
            assert rising == want_rising, (
                f"{name} goes from {lower:.4f} at {small:.0f} examples to "
                f"{higher:.4f} at {large:.0f}, which is the wrong direction"
            )


def test_the_curves_never_cross(generator: Any) -> None:
    """Validation stays below training at every plotted size."""
    validation = dict(_means(generator.DEMO_DATA, "Validation"))
    training = dict(_means(generator.DEMO_DATA, "Training"))
    crossed = [
        (size, training[size], validation[size])
        for size in sorted(validation)
        if validation[size] >= training[size]
    ]
    assert not crossed, "validation scores at or above training at " + ", ".join(
        f"{s:.0f} examples ({v:.4f} vs {t:.4f})" for s, t, v in crossed
    )


def test_the_curves_do_not_cross_outside_the_plot_either(generator: Any) -> None:
    """And they still do not cross at sizes no chart shows.

    This is the one the old version failed. Its demo crossed at roughly
    60 000 examples while plotting to 32 000, so the figure was correct
    exactly as far as it was drawn.
    """
    for size in _ABSURD_SIZES:
        train, valid = generator._mean_scores(size)
        assert valid < train, (
            f"at {size:.0f} examples validation {valid:.6f} has overtaken training {train:.6f}"
        )
        assert 0.0 < valid < 1.0 and 0.0 < train < 1.0, (
            f"at {size:.0f} examples the scores are {train:.6f} / {valid:.6f}, outside (0, 1)"
        )


def test_each_doubling_buys_less_than_the_one_before(generator: Any) -> None:
    """The validation curve decelerates, which is what makes its slope a reading.

    A learning curve saturates. If it does not -- if every doubling buys the
    same -- then "the slope over the last doubling", the number this figure
    is built to deliver, is a constant and says nothing about where you are
    on the curve.

    Asserted on the shipped rows, so fold noise has to be small enough that
    the deceleration survives it. That is a property of the figure too: a
    demo whose noise swamps its own trend does not teach the trend.
    """
    validation = _means(generator.DEMO_DATA, "Validation")
    slopes = [
        ((large, small), (higher - lower) / math.log2(large / small))
        for (small, lower), (large, higher) in zip(validation, validation[1:], strict=False)
    ]
    assert len(slopes) >= 3, "too few sizes to speak of deceleration"
    for (_, prev), ((to, _), nxt) in zip(slopes, slopes[1:], strict=False):
        assert nxt < prev, (
            f"the doubling ending at {to:.0f} examples bought {nxt:+.4f}, as much "
            f"as or more than the {prev:+.4f} before it: the curve is not saturating"
        )
    first, last = slopes[0][1], slopes[-1][1]
    assert last < first / 2.0, (
        f"the last doubling bought {last:+.4f} against {first:+.4f} for the first "
        f"-- not enough of a difference for the number to be worth printing"
    )


def test_the_fit_finds_a_ceiling_the_data_can_carry(generator: Any) -> None:
    """A ceiling is fitted, it is a real score, and there is room under it.

    These three are what the generator checks before it draws the dashed line
    and writes the headroom sentence, so they are the preconditions of the
    figure's own claim.
    """
    validation = _means(generator.DEMO_DATA, "Validation")
    fit = generator._fit_ceiling(validation)
    assert fit is not None, "no ceiling could be fitted to the validation curve"
    ceiling, exponent = fit
    last = validation[-1][1]
    assert last < ceiling <= 1.0, (
        f"the fitted ceiling {ceiling:.4f} is not above the last observation "
        f"{last:.4f} and at or below 1"
    )
    assert exponent > 0.0, f"a non-positive exponent ({exponent:.4f}) is not a decay"


def test_the_fit_recovers_a_ceiling_that_was_put_there(generator: Any) -> None:
    """The fit is checked against an answer that is known, not only for shape.

    Fed the noiseless means, it has to come back with the constant the
    generator built them from. Without this, every other assertion about the
    ceiling would hold just as well for a fit that returns a plausible wrong
    number.
    """
    noiseless = [(float(size), generator._mean_scores(size)[1]) for size in generator._SIZES]
    fit = generator._fit_ceiling(noiseless)
    assert fit is not None, "the fit refused noiseless data from its own model"
    ceiling, exponent = fit
    assert abs(ceiling - generator._CEILING) < 0.002, (
        f"fitted ceiling {ceiling:.4f} against a planted {generator._CEILING}"
    )
    assert abs(exponent - generator._VALID_EXPONENT) < 0.02, (
        f"fitted exponent {exponent:.4f} against a planted {generator._VALID_EXPONENT}"
    )


def test_the_fit_refuses_data_that_will_not_carry_a_ceiling(generator: Any) -> None:
    """It answers None rather than a number, on each way the claim can fail.

    Drawing a reference line means a reader will read it. The generator
    withholds the line when the fit is not supportable, which is only worth
    anything if the fit actually says so.
    """
    falling = [(float(size), 0.9 - 0.01 * index) for index, size in enumerate(generator._SIZES)]
    assert generator._fit_ceiling(falling) is None, "accepted a falling curve"
    too_few = [(250.0, 0.7), (500.0, 0.8), (1000.0, 0.85)]
    assert generator._fit_ceiling(too_few) is None, "accepted three sizes"
    flat = [(float(size), 0.8) for size in generator._SIZES]
    assert generator._fit_ceiling(flat) is None, "accepted a flat curve"


def test_the_band_is_a_band_at_every_size(generator: Any) -> None:
    """Fold spread stays positive and shrinks with data.

    It is drawn as a filled region, so a spread that reaches zero is a region
    that vanishes, and a negative one is a region drawn inside out. The old
    version decayed it linearly in doublings and would have gone negative
    past about 7.5 million examples -- the same tail defect as the curves.
    """
    for split in ("Training", "Validation"):
        spreads = []
        per_size: dict[float, list[float]] = {}
        for row in generator.DEMO_DATA:
            if row["split"] == split:
                per_size.setdefault(float(row["size"]), []).append(float(row["score"]))
        for size in sorted(per_size):
            scores = per_size[size]
            assert len(scores) > 1, f"{split} at {size:.0f} has a single fold"
            spreads.append((size, max(scores) - min(scores)))
        for size, spread in spreads:
            assert spread > 0.0, f"{split} at {size:.0f} examples has no spread"
        assert spreads[-1][1] < spreads[0][1], (
            f"{split} spread is {spreads[-1][1]:.4f} at the largest size against "
            f"{spreads[0][1]:.4f} at the smallest: folds should agree more with more data"
        )


def test_the_rendered_figure_states_the_ceiling_it_fitted(generator: Any) -> None:
    """What the fit found reaches the SVG, as a line and as a sentence.

    The arithmetic being right is not the deliverable; the picture is. Both
    carry the same three decimals, because the headroom is 0.023 and the
    house number formatter prints that as 0.02 -- the digit that rounds away
    is the one the reader needed.
    """
    validation = _means(generator.DEMO_DATA, "Validation")
    fit = generator._fit_ceiling(validation)
    assert fit is not None
    ceiling = fit[0]

    svg = generator.build_svg()
    assert f"ceiling {ceiling:.3f}" in svg, (
        f"the plot does not label the fitted ceiling {ceiling:.3f}"
    )
    assert f"Fitted ceiling {ceiling:.3f}" in svg, (
        f"the chrome does not state the fitted ceiling {ceiling:.3f}"
    )
    assert 'stroke-dasharray="7 5"' in svg, "the ceiling line is not drawn"
