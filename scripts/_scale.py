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


def _nice_num(value: float, round_up_only: bool) -> float:
    """Round `value` to the nearest 1/2/5-times-a-power-of-ten "nice" number.

    Shared step of the classic Heckbert (1990) "nice numbers for graph
    labels" algorithm, used twice by :func:`nice_ticks`: once to round the
    overall span *up* (``round_up_only=True`` is misleading naming avoided —
    see call sites) and once to round the per-tick step to the nearest of
    ``{1, 2, 5, 10}`` (``round_up_only=False``, i.e. round-to-nearest).
    """
    exponent = math.floor(math.log10(value))
    fraction = value / (10.0**exponent)
    if round_up_only:
        nice_fraction = 10.0 if fraction > 5 else 5.0 if fraction > 2 else 2.0 if fraction > 1 else 1.0
    else:
        nice_fraction = 1.0 if fraction < 1.5 else 2.0 if fraction < 3 else 5.0 if fraction < 7 else 10.0
    return nice_fraction * (10.0**exponent)


def nice_ticks(max_val: float, n: int = 4) -> list[float]:
    """Evenly-spaced "nice" tick values from ``0`` up to a rounded ceiling ``>= max_val``.

    Several linear-axis generators (bar, grouped-bar, stacked-area,
    column-range, ...) used to divide ``max_val`` into `n` raw equal steps
    (``max_val / n``), which lands the top gridline exactly on the data peak
    but produces label values like ``23``/``46``/``69``/``92`` —
    arithmetically even, but not numbers a reader can scan or do quick mental
    math with. This is the classic "nice numbers for graph labels" fix
    (Heckbert 1990 / the same idea behind D3's ``scale.nice()``): round the
    overall span up to a nice ceiling, then pick a nice step near
    ``ceiling / n``, so ticks land on ``0``/``20``/``40``/``60``/``80``/
    ``100`` instead of ``0``/``23``/``46``/``69``/``92``. Because the step is
    rounded rather than forced, the returned list can have more or fewer than
    ``n + 1`` entries — the point is round numbers, not an exact count. The
    tradeoff is that the top tick (and therefore the axis ceiling a caller
    derives from ``ticks[-1]``) may now sit a little *above* ``max_val``
    rather than exactly on it — deliberate: it gives the tallest bar/area a
    sliver of headroom below the plot's top edge instead of touching it,
    which is the more common professional-chart convention anyway.

    Parameters
    ----------
    max_val : float
        The largest value the axis must cover. Non-positive input returns
        ``[0.0]`` (a degenerate single-tick axis) rather than raising.
    n : int, optional
        Target number of steps (actual count may differ slightly once the
        step is rounded to a nice number). Defaults to ``4``, matching every
        existing caller's previous ``max_val / 4.0``.

    Returns
    -------
    list of float
        Ascending ticks ``[0, step, 2*step, ...]`` with `step` a nice
        1/2/5-times-a-power-of-ten value. The last entry is always
        ``>= max_val`` (assuming `max_val` is positive).

    Examples
    --------
    >>> nice_ticks(92)
    [0.0, 20.0, 40.0, 60.0, 80.0, 100.0]
    >>> nice_ticks(0)
    [0.0]
    """
    if max_val <= 0:
        return [0.0]
    nice_range = _nice_num(max_val, True)
    step = _nice_num(nice_range / n, False)
    nice_max = math.ceil(max_val / step) * step
    count = int(round(nice_max / step))
    return [i * step for i in range(count + 1)]


def nice_ticks_range(lo: float, hi: float, n: int = 5) -> list[float]:
    """Nice tick values covering an arbitrary ``[lo, hi]`` span (not anchored at 0).

    :func:`nice_ticks` assumes a ``0``-anchored axis (bar/area charts). Axes
    whose floor isn't ``0`` (a beeswarm's value axis padded around
    ``[v_min, v_max]``, a column-range's padded ``[y_min, y_max]``) instead
    divided their *raw* span by a fixed tick count, which -- exactly like the
    ``0``-anchored case -- produces label values that are evenly spaced but
    not round (e.g. a beeswarm spanning 14.3..74.6 got ticks at 14/24/35/...
    instead of 10/20/30/...). This rounds both the step *and* the two bounds
    outward to the nearest nice multiple, the same Heckbert approach as
    :func:`nice_ticks` generalized to a non-zero floor.

    Parameters
    ----------
    lo, hi : float
        The span to cover (typically already includes the caller's own
        padding). `hi` must be greater than `lo`.
    n : int, optional
        Target number of steps; the actual count may differ once the step is
        rounded to a nice number. Defaults to ``5``.

    Returns
    -------
    list of float
        Ascending ticks whose first entry is ``<= lo`` and last is ``>= hi``.
        Empty if `hi` <= `lo`.

    Examples
    --------
    >>> nice_ticks_range(14.3, 74.6)
    [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0]
    """
    if hi <= lo:
        return []
    span = hi - lo
    raw_step = span / n
    step = _nice_num(raw_step, False)
    nice_lo = math.floor(lo / step) * step
    nice_hi = math.ceil(hi / step) * step
    count = int(round((nice_hi - nice_lo) / step))
    return [nice_lo + i * step for i in range(count + 1)]


if __name__ == "__main__":  # tiny self-test
    assert log_position(1, 1, 100, 0.0, 100.0) == 0.0
    assert log_position(100, 1, 100, 0.0, 100.0) == 100.0
    assert log_ticks(3, 420) == [1.0, 10.0, 100.0, 1000.0]
    assert log_ticks(0, 5) == []
    assert nice_ticks(92) == [0.0, 20.0, 40.0, 60.0, 80.0, 100.0]
    assert nice_ticks(0) == [0.0]
    assert nice_ticks_range(14.3, 74.6) == [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0]
    assert nice_ticks_range(5, 5) == []
    print("_scale self-test OK")
