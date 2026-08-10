#!/usr/bin/env python3
"""
_scale — logarithmic axis mapping shared by the make_<id>.py generators.

A handful of generators expose a ``log_x``/``log_y`` toggle for an axis
whose data spans several orders of magnitude (session counts, prices,
p-values). The linear case is a single, self-explanatory line
(``p0 + (v - lo) / (hi - lo) * (p1 - p0)``) that each generator keeps as its
own inline closure — too trivial and too coupled to each script's own plot
geometry names to be worth abstracting. The *log* case is not: it needs a
zero/negative guard, a log-domain interpolation, and a decade-tick
generator with floating-point slop at the boundary, and getting any of
those slightly wrong is easy to miss on a chart that renders anyway (just
with a mis-placed point or a missing top tick). This module is the one
place that math lives, extracted from the first generator to need it
(``make_line-multi.py``) so every later log-axis adopter shares one
implementation instead of a fourth hand-rolled copy.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import math


def log_position(v: float, lo: float, hi: float, p0: float, p1: float) -> float:
    """Map ``v`` from the log-domain ``[lo, hi]`` to the pixel range ``[p0, p1]``.

    Works for either axis direction: pass ``p0`` as the pixel position of
    ``lo`` and ``p1`` as the pixel position of ``hi`` — for a y-axis (pixels
    grow downward, values grow upward) that means ``p0`` is the *bottom* of
    the plot and ``p1`` is the *top*, which flips the sign naturally without
    a separate code path.

    Parameters
    ----------
    v : float
        The data value to place. Values below `lo` clamp to `lo` (matching
        an axis floor), rather than mapping to a negative-infinity pixel.
    lo, hi : float
        The log-domain bounds. Must both be positive; `hi` must be
        greater than `lo`.
    p0, p1 : float
        Pixel positions of `lo` and `hi` respectively.

    Returns
    -------
    float
        The pixel position, linear in log10(v).

    Examples
    --------
    >>> log_position(10, 1, 100, 0.0, 100.0)
    50.0
    >>> log_position(0.5, 1, 100, 0.0, 100.0)
    0.0
    """
    if lo <= 0 or hi <= lo:
        return p0
    v = max(v, lo)
    frac = (math.log10(v) - math.log10(lo)) / (math.log10(hi) - math.log10(lo))
    return p0 + frac * (p1 - p0)


def log_ticks(lo: float, hi: float) -> list[float]:
    """Decade tick values (``..., 1, 10, 100, ...``) spanning ``[lo, hi]``.

    Rounds outward to the nearest decade on both ends so the first and last
    tick always bracket the data (``floor(log10(lo))`` to ``ceil(log10(hi))``),
    which means the returned ticks can extend a little past `lo`/`hi` — filter
    the result against the plotted domain if a caller wants ticks strictly
    inside it (as the x-axis case does, since its domain floor is the
    smallest *positive* data value rather than a round decade).

    Parameters
    ----------
    lo, hi : float
        The data range to cover. Must both be positive; `hi` must be
        greater than or equal to `lo`.

    Returns
    -------
    list of float
        Ascending decade values, e.g. ``[1.0, 10.0, 100.0]``. Empty if
        `lo`/`hi` are not both positive or `hi` < `lo`.

    Examples
    --------
    >>> log_ticks(3, 420)
    [1.0, 10.0, 100.0, 1000.0]
    """
    if lo <= 0 or hi <= 0 or hi < lo:
        return []
    d = 10.0 ** math.floor(math.log10(lo))
    # The upper bound is rounded outward too, so the loop needs the same
    # tiny multiplicative slop as the boundary decade itself to include it
    # despite float rounding (e.g. log10(1000) landing at 2.9999999998).
    hi_bound = 10.0 ** math.ceil(math.log10(hi))
    ticks: list[float] = []
    while d <= hi_bound * 1.0000001:
        ticks.append(d)
        d *= 10
    return ticks


if __name__ == "__main__":  # tiny self-test
    assert log_position(1, 1, 100, 0.0, 100.0) == 0.0
    assert log_position(100, 1, 100, 0.0, 100.0) == 100.0
    assert log_ticks(3, 420) == [1.0, 10.0, 100.0, 1000.0]
    assert log_ticks(0, 5) == []
    print("_scale self-test OK")
