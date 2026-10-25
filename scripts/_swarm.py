#!/usr/bin/env python3
"""
_swarm — collision-avoidance packing shared by the make_<id>.py generators.

A beeswarm places every observation at its own value along one axis and
nudges it along the other only as far as it must to avoid overlapping a
neighbour. That is the whole idea: unlike jitter, nothing moves by a
random amount, so the width of a pile is the density of the data rather
than a side effect of a random seed.

Lifted out of ``make_beeswarm`` when a second figure needed it --
``shap-beeswarm``, which packs one swarm per feature row and therefore
needs the ``max_offset`` cap that keeps a dense pile inside its own band.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

from typing import List, Optional, Tuple


def _swarm_positions(
    items: List[Tuple[float, float]], center_y: float, radius: float,
    max_offset: Optional[float] = None,
) -> List[float]:
    """Greedy collision-avoidance layout: return one y per (x, _) in *items*.

    Processes points in the given order, trying ``center_y`` first, then
    alternating offsets of increasing magnitude, accepting the first
    position that does not overlap (in Euclidean distance) any
    already-placed point whose x is within one diameter.

    Parameters
    ----------
    max_offset : float, optional
        Cap on how far a point may be pushed from ``center_y``. A locally
        dense cluster of x-values (many points sharing nearly the same x)
        otherwise pushes the offset outward without bound: fine when a
        band has generous headroom, but a caller with a fixed row height
        (a multi-row swarm, one band per category) needs points to stay
        inside their own band rather than spill into a neighbour's. Once
        the offset would exceed this cap, the point is clamped to the
        boundary and placed there, overlap accepted, rather than pushed
        further out. ``None`` (default) preserves the original unbounded
        behaviour.
    """
    step = radius * 1.9
    placed: List[Tuple[float, float]] = []
    ys: List[float] = []
    for x, _ in items:
        offset = 0
        tried = 0
        while True:
            raw_candidate = center_y if offset == 0 else center_y + (step * ((offset + 1) // 2) * (1 if offset % 2 else -1))
            at_bound = max_offset is not None and abs(raw_candidate - center_y) >= max_offset
            # Written as a statement, not a conditional expression: `at_bound`
            # already implies `max_offset is not None`, but only a reader can
            # see that through the intermediate variable. Repeating the test
            # costs nothing at runtime and states the precondition where it is
            # used.
            if max_offset is not None and at_bound:
                candidate = center_y + max_offset * (1 if raw_candidate >= center_y else -1)
            else:
                candidate = raw_candidate
            collision = any(
                (x - px) ** 2 + (candidate - py) ** 2 < (2 * radius) ** 2
                for px, py in placed
                if abs(x - px) < 2 * radius
            )
            if not collision or tried > 400 or at_bound:
                placed.append((x, candidate))
                ys.append(candidate)
                break
            offset += 1
            tried += 1
    return ys

