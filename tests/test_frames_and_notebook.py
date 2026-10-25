#!/usr/bin/env python3
"""
The two doors a data scientist actually arrives through.

Before these, the package asked a caller to hold ``list[dict]`` and to
accept a ``Path`` back. Both are correct internally and wrong at the
edges: the rows live in a DataFrame, and the answer is wanted *in the
notebook*, not on disk. These tests hold the two conversions in place.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from sprezzature_figures import make_figure
from sprezzature_figures.frames import as_rows, describe_input
from sprezzature_figures.notebook import FigurePath, as_figure_path

pandas = pytest.importorskip("pandas", reason="the pandas path needs pandas")


# --- what comes in -----------------------------------------------------


def test_no_rows_still_means_draw_your_own_demo() -> None:
    """``None`` must survive the normaliser untouched.

    It is the one value with a meaning of its own: it asks a figure for
    its author's rows *and* its author's chrome. An empty list would be
    a different request, and turning one into the other would silently
    replace somebody's title.
    """
    assert as_rows(None) is None
    assert as_rows([]) == []


def test_a_pandas_frame_arrives_as_rows() -> None:
    frame = pandas.DataFrame({"region": ["a", "b"], "value": [1.5, 2.5]})
    assert as_rows(frame) == [
        {"region": "a", "value": 1.5},
        {"region": "b", "value": 2.5},
    ]


def test_a_gap_is_spelled_none_not_nan() -> None:
    """NaN is a float, and a float reaches a figure as a number.

    Left alone it draws a bar of height nan, or raises inside a
    generator with a message about ``float()``. One spelling of absence
    everywhere, decided here, is what lets the check at the door be
    written once.
    """
    frame = pandas.DataFrame({"value": [1.0, float("nan")]})
    rows = as_rows(frame)
    assert rows is not None
    assert rows[1]["value"] is None
    assert not any(
        isinstance(cell, float) and math.isnan(cell) for row in rows for cell in row.values()
    )


def test_a_date_column_arrives_as_a_label() -> None:
    """A figure prints dates and sorts them; both want the ISO spelling."""
    frame = pandas.DataFrame({"when": pandas.to_datetime(["2026-01-01", "2026-02-03"])})
    assert as_rows(frame) == [{"when": "2026-01-01"}, {"when": "2026-02-03"}]


def test_a_dict_of_columns_is_read_as_columns() -> None:
    assert as_rows({"x": [1, 2], "y": ["a", "b"]}) == [
        {"x": 1, "y": "a"},
        {"x": 2, "y": "b"},
    ]


def test_the_caller_list_is_not_handed_to_the_figure() -> None:
    """A generator must not be able to mutate the caller's own rows."""
    mine = [{"x": 1}]
    theirs = as_rows(mine)
    assert theirs is not None
    theirs[0]["x"] = 99
    assert mine[0]["x"] == 1


@pytest.mark.parametrize(
    ("bad", "says"),
    [
        ([[1, 2]], "no column names"),
        ({"x": 1}, "single cell"),
        ({"x": [1, 2], "y": [1]}, "different lengths"),
        (42, "list of dicts"),
    ],
)
def test_a_shape_with_no_columns_in_it_says_what_to_pass(bad: object, says: str) -> None:
    """The refusal has to name the fix, not just the fault."""
    with pytest.raises(TypeError, match=says):
        as_rows(bad)


def test_describe_input_is_fit_for_an_error_message() -> None:
    assert describe_input([{"x": 1}]) == "1 row (list)"
    assert describe_input(None).startswith("no rows")
    assert "unreadable" in describe_input(42)


def test_a_frame_renders_without_the_caller_converting_it(tmp_path: Path) -> None:
    """The whole point, end to end: a frame in, a figure out."""
    frame = pandas.DataFrame({"region": ["Nord", "Sud", "Est"], "value": [42.0, 31.5, 27.0]})
    out = make_figure("bar", frame, out=tmp_path / "bar.svg")
    assert out.exists()
    svg = out.read_text(encoding="utf-8")
    assert "Nord" in svg


def test_a_gap_in_a_required_column_is_refused_with_its_row(tmp_path: Path) -> None:
    """Refused at the door, naming the column and the row.

    The alternative — dropping the row — misreports the total, and the
    alternative to that — letting it through — raises deep inside a
    generator with a message about ``float()`` that says nothing about
    the caller's data.
    """
    frame = pandas.DataFrame({"region": ["a", "b", "c"], "value": [1.0, float("nan"), 3.0]})
    with pytest.raises(ValueError) as caught:
        make_figure("bar", frame, out=tmp_path / "bar.svg")
    message = str(caught.value)
    assert "'value'" in message
    assert "1 of 3 rows" in message
    assert "row 1" in message
    assert "missing-matrix" in message


def test_a_gap_that_is_data_is_not_refused(tmp_path: Path) -> None:
    """A tree's root has no parent, and that is what makes it the root.

    The check is only as good as the figures allowed to opt out of it;
    this is the opt-out working.
    """
    rows = [
        {"id": "root", "label": "Root", "parent": None},
        {"id": "a", "label": "A", "parent": "root"},
        {"id": "b", "label": "B", "parent": "root"},
    ]
    out = make_figure("tree", rows, out=tmp_path / "tree.svg")
    assert out.exists()


# --- what goes out -----------------------------------------------------


def test_the_result_is_still_a_path(tmp_path: Path) -> None:
    """Every existing caller keeps working, which is the condition."""
    out = make_figure("bar", out=tmp_path / "bar.svg")
    assert isinstance(out, Path)
    assert isinstance(out, FigurePath)
    assert out.exists()
    assert out.name == "bar.svg"
    assert out.read_text(encoding="utf-8").startswith("<svg")


def test_a_path_operation_keeps_the_class(tmp_path: Path) -> None:
    """``.parent``, ``.resolve()`` and friends must not drop the display."""
    out = make_figure("bar", out=tmp_path / "bar.svg")
    assert isinstance(out.resolve(), FigurePath)
    assert isinstance(out.parent, FigurePath)
    assert isinstance(out.with_suffix(".png"), FigurePath)


def test_an_svg_shows_itself_as_svg(tmp_path: Path) -> None:
    """Returned as source, not as an ``<img>``.

    The figures carry their own hover tooltips in CSS, and those only
    work when the markup is in the page.
    """
    out = make_figure("bar", out=tmp_path / "bar.svg")
    drawn = out._repr_svg_()
    assert drawn is not None
    assert drawn.lstrip().startswith("<svg")
    assert out._repr_png_() is None
    assert out._repr_html_() is None


def test_a_missing_file_shows_nothing_rather_than_raising(tmp_path: Path) -> None:
    """A display convenience must never be the reason a cell blows up."""
    ghost = as_figure_path(tmp_path / "never-written.svg")
    assert ghost._repr_svg_() is None
    assert ghost._repr_png_() is None
