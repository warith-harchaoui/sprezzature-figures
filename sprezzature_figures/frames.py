#!/usr/bin/env python3
"""
frames — whatever the caller is holding, turned into the rows a figure wants.

Every generator in this package takes ``list[dict]``: one dict per row,
column names as keys. That is the right internal shape -- it is what an
SVG author iterates over, it serialises to JSON for the API without a
conversion, and it carries no library with it.

It is not what a data scientist is holding. They have a pandas frame, or
a polars one, or an Arrow table, or the dict of columns a query driver
just handed back, and asking them to write ``df.to_dict("records")``
before every call is a toll booth on the way in. This module removes it.

How it decides, and why it never imports anything
-------------------------------------------------
The dispatch is by *duck typing*, not by ``isinstance``: nothing here
imports pandas, polars or pyarrow, and nothing here declares them as
dependencies. A frame is recognised by the method it offers --
``to_dicts`` (polars), ``to_pylist`` (Arrow), ``to_dict(orient=...)``
(pandas) -- so a library this file has never heard of works the moment
it offers one of them, and a user with none of them installed pays
nothing.

Missing values
--------------
``NaN`` is pandas' way of spelling "absent", and it is a float, so it
survives every conversion and lands in a figure as a number. Every path
through this module turns a not-a-number float into ``None``, which is
what the generators already treat as missing. ``NaT`` and pandas' ``NA``
go the same way.

Dates
-----
A frame's date column arrives as ``Timestamp`` or ``datetime`` objects.
Every figure here wants a *label* -- something to print on an axis and
sort by -- so a datetime is spelled out in ISO form, and a midnight one
loses the time it never had. ``2026-01-01``, not
``Timestamp('2026-01-01 00:00:00')``.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import datetime as _dt
import math
from collections.abc import Mapping, Sequence
from typing import Any

__all__ = ["as_rows", "describe_input"]


def _clean(value: Any) -> Any:
    """One cell, with every spelling of "absent" turned into ``None``.

    Parameters
    ----------
    value : Any
        A cell as the source library handed it over.

    Returns
    -------
    Any
        The value, or ``None`` when it is a not-a-number float, a
        ``NaT``, or a library's own null sentinel.

    Examples
    --------
    >>> _clean(3)
    3
    >>> _clean(float("nan")) is None
    True
    >>> _clean("nan")
    'nan'
    >>> import datetime
    >>> _clean(datetime.datetime(2026, 1, 1))
    '2026-01-01'
    >>> _clean(datetime.datetime(2026, 1, 1, 9, 30))
    '2026-01-01 09:30:00'
    """
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    # pandas' NaT and pd.NA, numpy's masked constant: all of them report
    # themselves as null through this protocol, and none of them are
    # worth importing a library to recognise.
    if value is not value:  # NaN-like: not equal to itself
        return None
    marker = getattr(type(value), "__name__", "")
    if marker in ("NaTType", "NAType"):
        return None
    # A date is a label here, not an instant: it goes on an axis and gets
    # sorted, and both want the ISO spelling. A Timestamp is a datetime
    # subclass, so pandas and the standard library land in the same place.
    if isinstance(value, _dt.datetime):
        if (value.hour, value.minute, value.second, value.microsecond) == (0, 0, 0, 0):
            return value.date().isoformat()
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, _dt.date):
        return value.isoformat()
    return value


def _rows_from_records(records: Any) -> list[dict[str, Any]]:
    """A sequence of mappings, copied into plain dicts with cells cleaned."""
    out: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise TypeError(
                f"row {index} is a {type(record).__name__}, not a mapping of "
                "column name to value. Figure data is one dict per row, or a "
                "DataFrame; a list of lists has no column names to bind."
            )
        out.append({str(key): _clean(value) for key, value in record.items()})
    return out


def _is_column(value: Any) -> bool:
    """Whether a mapping's value looks like a column rather than a cell."""
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes))


def as_rows(data: Any) -> list[dict[str, Any]] | None:
    """`data`, whatever it is, as the ``list[dict]`` the figures take.

    Parameters
    ----------
    data : Any
        ``None``; a list of dicts (returned cleaned, not as-is); a
        pandas, polars, cuDF or Modin DataFrame; a pyarrow Table or
        RecordBatch; a dict of equal-length columns; or anything else
        offering ``to_dicts()``, ``to_pylist()`` or
        ``to_dict(orient="records")``.

    Returns
    -------
    list of dict or None
        One dict per row, column names as string keys, every absent cell
        spelled ``None``. ``None`` in gives ``None`` out, which is how a
        caller asks a figure for its own demo rows.

    Raises
    ------
    TypeError
        When `data` is a shape with no column names in it -- a list of
        lists, a bare array -- or a mapping whose columns are of
        different lengths. The message says what to pass instead.

    Examples
    --------
    >>> as_rows(None) is None
    True
    >>> as_rows([{"x": 1, "y": 2.0}])
    [{'x': 1, 'y': 2.0}]
    >>> as_rows({"x": [1, 2], "y": ["a", "b"]})
    [{'x': 1, 'y': 'a'}, {'x': 2, 'y': 'b'}]
    >>> as_rows([{"x": float("nan")}])
    [{'x': None}]
    """
    if data is None:
        return None

    # Already the house shape. Copied rather than returned as-is: the
    # caller's list is theirs, and a figure must not be able to mutate it.
    if isinstance(data, (list, tuple)):
        return _rows_from_records(data)

    # polars, and anything that copied its API.
    to_dicts = getattr(data, "to_dicts", None)
    if callable(to_dicts):
        return _rows_from_records(to_dicts())

    # pyarrow Table and RecordBatch.
    to_pylist = getattr(data, "to_pylist", None)
    if callable(to_pylist):
        return _rows_from_records(to_pylist())

    # pandas, and its distributed twins (Modin, cuDF, Dask's compute
    # result). ``where(notna(), None)`` first, because ``to_dict`` on a
    # numeric column with gaps hands back NaN floats that look like data.
    to_dict = getattr(data, "to_dict", None)
    notna = getattr(data, "notna", None)
    where = getattr(data, "where", None)
    if callable(to_dict) and callable(notna) and callable(where):
        try:
            filled = where(notna(), None)
        except (TypeError, ValueError):  # pragma: no cover - defensive
            filled = data
        return _rows_from_records(filled.to_dict(orient="records"))
    if callable(to_dict) and not isinstance(data, Mapping):
        return _rows_from_records(data.to_dict(orient="records"))

    # A dict of columns, which is what most query drivers and most
    # hand-built examples look like.
    if isinstance(data, Mapping):
        if not data:
            return []
        if not all(_is_column(column) for column in data.values()):
            raise TypeError(
                "a dict is read as column name -> column of values, and at "
                "least one value here is a single cell. Pass [dict] for one "
                "row, or give every column a list."
            )
        lengths = {len(column) for column in data.values()}
        if len(lengths) > 1:
            sizes = ", ".join(f"{name}: {len(column)}" for name, column in data.items())
            raise TypeError(f"the columns are of different lengths ({sizes}).")
        height = lengths.pop()
        return [
            {str(name): _clean(column[index]) for name, column in data.items()}
            for index in range(height)
        ]

    # The dataframe interchange protocol says "I am a frame" without
    # saying how to read one in a line of code. Rather than implement the
    # protocol here, say so and name the one-liner.
    if hasattr(data, "__dataframe__"):
        raise TypeError(
            f"{type(data).__name__} is a DataFrame this package cannot read "
            "directly. Call .to_pandas(), .to_arrow() or .to_dict('records') "
            "on it first -- the result is accepted."
        )

    raise TypeError(
        f"figure data is a list of dicts, a DataFrame, or a dict of columns; "
        f"got {type(data).__name__}."
    )


def describe_input(data: Any) -> str:
    """What `as_rows` made of `data`, in a sentence fit for an error message.

    Parameters
    ----------
    data : Any
        The object a caller passed as figure data.

    Returns
    -------
    str
        A short description naming the type and the row count.

    Examples
    --------
    >>> describe_input([{"x": 1}, {"x": 2}])
    '2 rows (list)'
    >>> describe_input(None)
    'no rows (the figure draws its own demo data)'
    """
    if data is None:
        return "no rows (the figure draws its own demo data)"
    try:
        rows = as_rows(data)
    except TypeError as exc:
        return f"unreadable ({exc})"
    count = len(rows or [])
    return f"{count} row{'' if count == 1 else 's'} ({type(data).__name__})"
