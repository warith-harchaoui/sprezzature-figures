"""
Deterministic execution of ``FigurePlan.transformations`` over row data.

The FigurePlan records *what* data-shaping steps should apply (filter, sort,
aggregate, top-N, ...) as an auditable list of typed :mod:`~.operations`
``Transform`` models. This module is the missing executor that actually
*applies* them to ``list[dict]`` rows, in list order, before the rows reach a
generator. Nothing here evaluates free-form code -- every step is a closed,
typed operation, matching plan §4.3.

Two rules keep the output trustworthy:

- A transform that references a column absent from *every* row is skipped
  rather than silently emptying the dataset (an unknown column can't filter
  what isn't there; the plan validator flags such columns upstream). This is
  reported through :class:`TransformNote`, never hidden.
- Rows are never mutated in place -- each step returns fresh dicts.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from .operations import (
    AggregateTransform,
    CalculateDerived,
    FilterByRange,
    FilterByValue,
    FilterTemporal,
    GroupOthers,
    RenameDisplay,
    SortTransform,
    TopN,
    Transform,
)

Row = dict[str, Any]


class TransformNote(str):
    """A one-line, human-readable note about a transform that was skipped or
    degraded (e.g. an unknown column). Subclasses ``str`` so it prints
    plainly while still being distinguishable from an ordinary message."""


# --------------------------------------------------------------------------
# Small, defensive coercions -- user data is messy; never raise on a bad cell
# --------------------------------------------------------------------------


def _to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip().replace(",", ""))
    except (TypeError, ValueError):
        return None


def _to_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    # Try full ISO first, then a date-only prefix (handles "2022-01-01 …").
    for candidate in (text, text[:10]):
        try:
            return datetime.fromisoformat(candidate).date()
        except ValueError:
            continue
    return None


def _values_equal(a: Any, b: Any) -> bool:
    """Equality that tolerates the string/number drift typical of CSV cells
    (the value 3 loaded as "3" still matches a filter value of 3)."""
    if a == b:
        return True
    fa, fb = _to_float(a), _to_float(b)
    if fa is not None and fb is not None:
        return fa == fb
    return str(a).strip() == str(b).strip()


def _has_column(rows: list[Row], column: str) -> bool:
    return any(column in row for row in rows)


def _sort_key(value: Any) -> tuple[int, float, str]:
    """Order key that keeps mixed/None cells from raising: None sinks last,
    then numeric-by-value, then lexicographic for everything else."""
    if value is None:
        return (2, 0.0, "")
    number = _to_float(value)
    if number is not None:
        return (0, number, "")
    return (1, 0.0, str(value))


# --------------------------------------------------------------------------
# Per-transform appliers -- each takes rows + note sink, returns new rows
# --------------------------------------------------------------------------


def _apply_filter_value(rows: list[Row], t: FilterByValue) -> list[Row]:
    keep_if_member = t.op in ("eq", "in")
    return [
        row
        for row in rows
        if (any(_values_equal(row.get(t.column), v) for v in t.values)) == keep_if_member
    ]


def _apply_filter_range(rows: list[Row], t: FilterByRange) -> list[Row]:
    out: list[Row] = []
    for row in rows:
        number = _to_float(row.get(t.column))
        if number is None:
            continue  # a range filter can't judge a non-numeric cell
        if t.minimum is not None and number < t.minimum:
            continue
        if t.maximum is not None and number > t.maximum:
            continue
        out.append(row)
    return out


def _apply_filter_temporal(rows: list[Row], t: FilterTemporal) -> list[Row]:
    start = _to_date(t.start)
    end = _to_date(t.end)
    out: list[Row] = []
    for row in rows:
        when = _to_date(row.get(t.column))
        if when is None:
            continue
        if start is not None and when < start:
            continue
        if end is not None and when > end:
            continue
        out.append(row)
    return out


def _apply_sort(rows: list[Row], t: SortTransform) -> list[Row]:
    return sorted(rows, key=lambda row: _sort_key(row.get(t.column)), reverse=not t.ascending)


def _apply_aggregate(rows: list[Row], t: AggregateTransform) -> list[Row]:
    out_col = t.output_column or (t.value_column if t.agg != "count" else "count")
    groups: dict[tuple[Any, ...], list[Row]] = {}
    order: list[tuple[Any, ...]] = []
    for row in rows:
        key = tuple(row.get(col) for col in t.group_by)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(row)

    result: list[Row] = []
    for key in order:
        members = groups[key]
        new_row: Row = dict(zip(t.group_by, key, strict=True))
        new_row[out_col] = _aggregate_values([row.get(t.value_column) for row in members], t.agg)
        result.append(new_row)
    return result


def _aggregate_values(values: list[Any], agg: str) -> Any:
    if agg == "count":
        return len(values)
    numbers = [n for n in (_to_float(v) for v in values) if n is not None]
    if not numbers:
        return None
    if agg == "sum":
        return sum(numbers)
    if agg == "mean":
        return sum(numbers) / len(numbers)
    if agg == "min":
        return min(numbers)
    if agg == "max":
        return max(numbers)
    if agg == "median":
        ordered = sorted(numbers)
        mid = len(ordered) // 2
        if len(ordered) % 2:
            return ordered[mid]
        return (ordered[mid - 1] + ordered[mid]) / 2
    return None  # unreachable given the Literal, but explicit beats implicit


def _apply_top_n(rows: list[Row], t: TopN) -> list[Row]:
    if t.n <= 0:
        return []
    if t.by is not None and _has_column(rows, t.by):
        ranked = sorted(
            enumerate(rows),
            key=lambda pair: _sort_key(pair[1].get(t.by)),
            reverse=True,
        )
        keep_indices = {index for index, _ in ranked[: t.n]}
        # Preserve the rows' original order so a later sort stays in control.
        return [row for index, row in enumerate(rows) if index in keep_indices]
    return rows[: t.n]


def _apply_group_others(rows: list[Row], t: GroupOthers) -> list[Row]:
    keep = set(t.keep)
    out: list[Row] = []
    for row in rows:
        value = row.get(t.column)
        if value in keep:
            out.append(row)
        else:
            out.append({**row, t.column: t.other_label})
    return out


def _apply_calculate(rows: list[Row], t: CalculateDerived) -> list[Row]:
    out: list[Row] = []
    for row in rows:
        left = _to_float(row.get(t.left))
        right = _to_float(row.get(t.right))
        if left is None or right is None:
            value: Any = None
        elif t.calc == "difference":
            value = left - right
        else:  # ratio
            value = left / right if right != 0 else None
        out.append({**row, t.output_column: value})
    return out


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------


# Every transform declares the column(s) it needs present to do anything.
# Aggregate/top-N with a missing *value* column still group/slice, so they
# guard only on their structural columns.
def _required_columns(t: Transform) -> list[str]:
    if isinstance(t, (FilterByValue, FilterByRange, FilterTemporal, SortTransform, GroupOthers)):
        return [t.column]
    if isinstance(t, TopN):
        return [t.column]
    if isinstance(t, AggregateTransform):
        return list(t.group_by) or [t.value_column]
    if isinstance(t, CalculateDerived):
        return [t.left, t.right]
    return []  # RenameDisplay has no data-level effect


_APPLIERS = {
    FilterByValue: _apply_filter_value,
    FilterByRange: _apply_filter_range,
    FilterTemporal: _apply_filter_temporal,
    SortTransform: _apply_sort,
    AggregateTransform: _apply_aggregate,
    TopN: _apply_top_n,
    GroupOthers: _apply_group_others,
    CalculateDerived: _apply_calculate,
}


def apply_transformations(
    rows: list[Row],
    transforms: list[Transform],
) -> tuple[list[Row], list[TransformNote]]:
    """Apply ``transforms`` to ``rows`` in order, returning new rows + notes.

    ``RenameDisplay`` is deliberately a no-op here: the render contract keys
    data by role, not by column, so a *display* rename is a labelling concern
    handled by the style/axis layer, not a change to the data. It stays in
    the plan as intent; this executor just doesn't touch rows for it.

    Notes call out any transform skipped because a column it needs is absent
    from the data, so a stale filter can never silently empty the figure.
    """
    notes: list[TransformNote] = []
    current = list(rows)

    for transform in transforms:
        if isinstance(transform, RenameDisplay):
            continue

        needed = _required_columns(transform)
        missing = [col for col in needed if not _has_column(current, col)]
        if missing:
            notes.append(
                TransformNote(f"Skipped {transform.kind}: column(s) {missing} not in the data.")
            )
            continue

        applier = _APPLIERS[type(transform)]
        current = applier(current, transform)

    return current, notes
