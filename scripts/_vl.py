"""
_vl — tiny Vega-Lite spec-building helper shared by the make_* generators
that colour-encode an optional categorical role (series/channel/segment/
city, ...).

:func:`categorical_domain_and_range` is the one thing that recurred,
identically broken, across four generators (make_line, make_area,
make_scatter, make_columnrange): each built its color scale's ``domain``
from a **hardcoded** list of demo category names (or worse, from
``row["field"]`` with no ``.get()``) instead of the data actually passed
in. Once that role is optional -- as it is for all four in the figure
registry -- a caller who doesn't bind it gets either a ``KeyError`` crash
(direct ``row["field"]`` access) or a legend showing categories that don't
exist in the data at all (a hardcoded ``scale.domain``). Both were real
bugs, not stylistic choices; see docs/studio/STATUS.md.

The module is **stdlib-only**, importing nothing -- these generators only
need a plain function, not a dataclass or a dependency.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def categorical_domain_and_range(
    data: List[Dict[str, Any]],
    field: str,
    named_colors: Dict[str, str],
    *,
    fallback: str = "#007AFF",
) -> Optional[Tuple[List[str], List[str]]]:
    """The ``(domain, range)`` pair for a Vega-Lite categorical color scale,
    derived from the **actual distinct values** of `field` present in
    `data` -- never a fixed list of demo category names.

    Returns ``None`` when no row carries `field` at all (an optional data
    role the caller left unbound): the generator should then omit the
    color encoding entirely rather than emit a scale/legend for categories
    that don't exist in the data (or crash trying to read a missing key).

    Parameters
    ----------
    data : list of dict
        The rows actually being rendered (never DEMO_DATA -- callers pass
        their real `data` argument here).
    field : str
        The row key to color by (e.g. ``"series"``, ``"channel"``).
    named_colors : dict of str to str
        House colors for known category names (e.g. the demo dataset's own
        categories), reused when the data happens to match them so the
        rendered demo/typical case keeps its curated palette.
    fallback : str, optional
        Color for any distinct value not in `named_colors` (e.g. a user's
        own category names) -- the house brand blue by default.

    Returns
    -------
    tuple of (list of str, list of str), or None
        ``(domain, range)`` sorted by domain value, or ``None`` if `field`
        is absent from every row.

    Examples
    --------
    >>> categorical_domain_and_range([{"x": 1}], "series", {})
    >>> categorical_domain_and_range(
    ...     [{"series": "B"}, {"series": "A"}], "series", {"A": "#111111"}
    ... )
    (['A', 'B'], ['#111111', '#007AFF'])
    """
    values = sorted({row[field] for row in data if field in row and row[field] is not None})
    if not values:
        return None
    return values, [named_colors.get(v, fallback) for v in values]
