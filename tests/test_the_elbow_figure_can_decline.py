"""The elbow figure can now refuse, and refusing is off by default on purpose.

What was missing. ``kneedle_elbow`` always answers. That is Kneedle working
as specified -- it returns the peak of a difference curve, and a difference
curve has a peak on a straight line too -- and it is the one thing the figure
could not check about itself. Measured on 24-point curves before this change:
Kneedle placed the elbow at k = 22, 23, 20, 4 and 4 on five noisy straight
lines, and at k = 1, 1, 4, 1 and 2 on five curves of uniform noise. Ten
confident answers over ten curves with nothing to be confident about, each of
which this package would have drawn with a marker, a pill and a sentence
naming the k.

The abstention state did exist -- ``is_clear=False`` greys the curve, drops
the marker and prints a reason -- but only a caller who had already done the
statistics could reach it. The figure was able to avoid lying only if somebody
else decided whether it would be lying. ``robust=True`` closes that by handing
the curve to ``elbow_helper.robust_elbow``, which abstained on all ten of
those curves with a named gate.

Why it is opt-in, which is the part a future reader will want to re-litigate.
``robust_elbow`` is calibrated for twenty points or more and rejects any
candidate within five points of an end. A k-means sweep is neither: this
module's demo is k = 1..10 with a clear elbow at 4, so the test abstains on it
with ``INSUFFICIENT_DATA``, and lowering ``min_samples`` to 8 only moves the
refusal to ``ALL_CANDIDATES_WEAK``. On planted noiseless elbows at a fifth of
the range it abstains at n = 10, 15 and 20 and accepts from n = 24 up. So the
measure puts a case we know is good on the wrong side, and defaulting it on
would print "No clear elbow" over the flagship figure of "here is the elbow".
:func:`test_the_demo_sweep_is_under_the_detector_s_floor` pins that boundary,
so flipping the default cannot be done quietly.

Not asserted here, because it is not this figure's claim: that
``robust_elbow`` and Kneedle return the same k. Measured, they agree at 8, 12
and 20 on noiseless sweeps and differ by 2 and 4 on the two longest (33 vs 35,
60 vs 64), and pinning a specific k from a third-party bootstrap would be a
test of elbow-helper's release notes rather than of this generator.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

import importlib.util
import math
import random
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GENERATOR = REPO_ROOT / "scripts" / "make_elbow.py"

pytest.importorskip(
    "elbow_helper",
    reason="elbow-helper is declared in the `dataviz` extra",
)

#: Marker the generator emits only when it is reporting a point estimate.
_ABSTAINED = "No clear elbow"


@pytest.fixture(scope="module")
def generator() -> Any:
    """The generator module, loaded by path because it imports siblings by name."""
    spec = importlib.util.spec_from_file_location("make_elbow", GENERATOR)
    assert spec and spec.loader, f"cannot load {GENERATOR}"
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(GENERATOR.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(GENERATOR.parent))
    return module


def _rows(xs: list[int], ys: list[float]) -> list[dict[str, Any]]:
    """The ``{"k": …, "inertia": …}`` row shape the catalogue's roles name."""
    return [{"k": x, "inertia": y} for x, y in zip(xs, ys, strict=True)]


def _straight_line(n: int = 24, seed: int = 0) -> list[dict[str, Any]]:
    """A noisy straight line: decreasing, convex nowhere, elbow nowhere."""
    rng = random.Random(seed)
    xs = list(range(1, n + 1))
    return _rows(xs, [1000.0 - 30.0 * x + rng.gauss(0, 1) for x in xs])


def _well_sampled_elbow(n: int = 24) -> list[dict[str, Any]]:
    """A convex decreasing sweep long enough for the robust test to speak."""
    xs = list(range(1, n + 1))
    return _rows(xs, [1000.0 * math.exp(-0.30 * (x - 1)) + 95.0 for x in xs])


def test_the_default_is_still_kneedle_and_still_answers(generator: Any) -> None:
    """``robust`` off changes nothing, which is what keeps the committed asset.

    ``assets/svg-examples/elbow.svg`` is rendered from the demo sweep with the
    defaults, so this is the assertion that the new parameter did not quietly
    re-draw a tracked file.
    """
    svg = generator.build_svg()
    assert _ABSTAINED not in svg, "the default render abstained"
    assert "Kneedle method" in svg, "the default render stopped naming Kneedle"
    assert svg == generator.build_svg(robust=False), "robust=False is not the default"


def test_kneedle_alone_asserts_an_elbow_on_a_straight_line(generator: Any) -> None:
    """The defect, stated as a property rather than as history.

    If this ever starts failing because Kneedle learned to decline, the
    `robust` parameter has lost its reason to exist and should go.
    """
    svg = generator.build_svg(_straight_line())
    assert _ABSTAINED not in svg, (
        "Kneedle declined a straight line, which it is not supposed to be able to do"
    )
    assert "flags the elbow at k =" in svg


def test_robust_declines_the_straight_line_and_says_why(generator: Any) -> None:
    """And the reason reaches the picture, not just the return value.

    An abstention a reader cannot see the grounds for is an unexplained blank
    chart.
    """
    svg = generator.build_svg(_straight_line(), robust=True)
    assert _ABSTAINED in svg, "robust=True asserted an elbow on a straight line"
    assert "candidates were rejected" in svg, (
        "the figure abstained without printing elbow-helper's reason"
    )
    assert 'class="elb-marker"' not in svg, "an elbow marker was drawn anyway"


def test_robust_declines_pure_noise(generator: Any) -> None:
    """The second shape with no elbow, and a different gate closes on it."""
    rng = random.Random(7)
    xs = list(range(1, 25))
    svg = generator.build_svg(_rows(xs, [rng.uniform(200, 1000) for _ in xs]), robust=True)
    assert _ABSTAINED in svg, "robust=True asserted an elbow on uniform noise"


def test_the_demo_sweep_is_under_the_detector_s_floor(generator: Any) -> None:
    """Ten points is below the twenty ``robust_elbow`` is calibrated for.

    This is the measurement that decided ``robust`` would be opt-in, so it is
    asserted rather than left in a commit message. Were the default flipped,
    the shipped example figure would read "No clear elbow" over a curve whose
    elbow at k = 4 is plain to the eye and which the same module locates
    correctly with Kneedle.
    """
    assert len(generator.DEMO_DATA) == 10
    verdict = generator.robust_verdict(
        [float(row["k"]) for row in generator.DEMO_DATA],
        [float(row["inertia"]) for row in generator.DEMO_DATA],
    )
    assert not verdict.is_clear, (
        "robust_elbow now accepts the ten-point demo sweep; re-run the n = 10/15/20/24 "
        "measurement in this file's docstring and reconsider the default"
    )
    assert verdict.abstain_reason and "20" in verdict.abstain_reason, (
        f"the abstention stopped naming the sample floor: {verdict.abstain_reason!r}"
    )
    # Kneedle, on the same curve, is right.
    index, _ = generator.kneedle_elbow(
        [float(row["k"]) for row in generator.DEMO_DATA],
        [float(row["inertia"]) for row in generator.DEMO_DATA],
    )
    assert generator.DEMO_DATA[index]["k"] == 4, (
        "the demo elbow moved; the argument for keeping Kneedle as the default rests "
        "on it being correct here"
    )


def test_a_well_sampled_sweep_is_accepted_with_its_uncertainty(generator: Any) -> None:
    """Above the floor it speaks, and what it says reaches the inset.

    The interval, the detection rate and the null-model p-value were already
    parameters of this figure; before this change only a caller who had
    computed them by hand could fill them in.
    """
    data = _well_sampled_elbow()
    verdict = generator.robust_verdict(
        [float(row["k"]) for row in data], [float(row["inertia"]) for row in data]
    )
    assert verdict.is_clear, "a clean 24-point convex sweep was refused"
    assert verdict.ci is not None and verdict.ci[0] <= verdict.ci[1]
    assert verdict.detection_rate is not None and 0.0 <= verdict.detection_rate <= 1.0
    assert verdict.null_p_value is not None and 0.0 <= verdict.null_p_value <= 1.0
    assert verdict.elbow_index is not None

    svg = generator.build_svg(data, robust=True)
    assert _ABSTAINED not in svg
    assert "robust knee test" in svg, "the subtitle still credited Kneedle for the call"
    assert "detection rate" in svg and "null-model p" in svg, (
        "the uncertainty the robust test computed never reached the inset"
    )


def test_an_explicit_interval_still_wins(generator: Any) -> None:
    """A caller who brings its own numbers keeps them.

    ``robust=True`` is a default-filler, not a seizure: a caller with a better
    interval than a 100-replicate bootstrap must be able to say so.
    """
    data = _well_sampled_elbow()
    svg = generator.build_svg(data, robust=True, detection_rate=0.42)
    assert "42%" in svg, "the caller's detection rate was overwritten by the computed one"


def test_the_verdict_is_reproducible(generator: Any) -> None:
    """Same curve, same picture.

    ``RobustKneeConfig`` defaults ``random_seed`` to ``None``, and two runs of
    the bootstrap over the same curve returned detection rates of 0.91 and
    0.95 while that was in force. A figure that is not byte-stable cannot be
    committed, and a detection rate that moves is a number a reader would
    reasonably treat as having moved for a reason.
    """
    data = _well_sampled_elbow()
    assert generator.build_svg(data, robust=True) == generator.build_svg(data, robust=True)


def test_the_abstention_is_written_in_the_requested_language(generator: Any) -> None:
    """French too, since the reason comes from elbow-helper and not from here.

    The figure's own chrome has had both languages from the start; an
    abstention reason in English under a French chart would be a regression
    the reason's provenance makes easy to miss.
    """
    data = _straight_line()
    english = generator.build_svg(data, robust=True, language="en")
    french = generator.build_svg(data, robust=True, language="fr")
    assert "Aucun coude net" in french, "the French abstention title is missing"
    assert "candidats" in french, "the reason stayed in English under a French chart"
    assert english != french
