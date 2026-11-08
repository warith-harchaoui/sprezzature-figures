"""
Demo chrome is caught at the door, in the check, and on the ticks.

Three mechanisms keep a demo's words off a caller's figure, and one keeps a
small axis legible:

* make_figure titles an axis after the column it draws (a generator's
  ``AXIS_ROLES`` says which), and empties every caption whose default is the
  demo's, rather than printing a sentence about data that is not there;
* ``check_render(kind=...)`` reports a kind's demo text in a render, except
  the method's own vocabulary (``METHOD_TEXT``) and what the caller allows;
* ``check_render`` reports two labels that touch (the "-8" running into the
  "0" at an origin corner), but not the lines of one stacked list;
* ``fmt_tick`` gives a tick the decimals of its step, so an axis stepping by
  0.05 no longer reads "1, 1, 1".

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

import math
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from _svg import fmt_tick  # noqa: E402

from sprezzature_figures import make_figure  # noqa: E402
from sprezzature_figures.make_figure import demo_texts  # noqa: E402
from sprezzature_figures.render_checks import check_render  # noqa: E402


def _svg(width: int, texts: list[tuple[float, float, str, str, float]]) -> str:
    """A minimal SVG holding the given (x, y, anchor, text, size) labels."""
    body = "".join(
        f'<text x="{x}" y="{y}" text-anchor="{a}" font-size="{s}">{t}</text>'
        for x, y, a, t, s in texts
    )
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="200" '
            f'role="img" aria-labelledby="t d"><title id="t">T</title><desc id="d">D</desc>'
            f"{body}</svg>")


def _render(kind: str, rows: list[dict], tmp_path: Path, **kwargs) -> str:
    out = tmp_path / f"{kind}.svg"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        make_figure(kind, rows, out=out, embed_fonts=False, **kwargs)
    return out.read_text(encoding="utf-8")


def test_touching_labels_on_different_rows_are_reported() -> None:
    """The origin-corner case: an end-anchored y label meets a centred x label."""
    svg = _svg(300, [(100, 104, "end", "-8", 11), (102, 112, "middle", "0", 11)])
    assert any(f.check == "labels_touch" for f in check_render(svg))


def test_separated_labels_and_stacked_lists_are_not() -> None:
    """Air between two labels, or one list read line by line, passes."""
    apart = _svg(300, [(100, 80, "end", "-8", 11), (102, 120, "middle", "0", 11)])
    listed = _svg(300, [(100, 100, "end", "cust_01", 11), (100, 112, "end", "cust_02", 11)])
    assert not [f for f in check_render(apart) if f.check == "labels_touch"]
    assert not [f for f in check_render(listed) if f.check == "labels_touch"]


def test_demo_text_is_reported_only_when_the_kind_is_named(tmp_path: Path) -> None:
    """A tree drawn with one of the demo's labels: flagged under kind=, allowed on request."""
    rows = [{"id": "a", "label": "Kernel", "parent": None},
            {"id": "b", "label": "Supervised", "parent": "a"}]
    svg = _render("tree", rows, tmp_path)
    assert not [f for f in check_render(svg) if f.check == "demo_text"]
    flagged = [f for f in check_render(svg, kind="tree") if f.check == "demo_text"]
    assert any("Supervised" in f.detail for f in flagged)
    assert not [f for f in check_render(svg, kind="tree", allowed_text=["Supervised"])
                if f.check == "demo_text"]


def test_the_methods_own_words_are_never_demo_text() -> None:
    """A causal graph's role legend is right over any graph."""
    assert "collider · do not adjust" not in demo_texts("causal-dag")
    assert "upper control limit" not in demo_texts("control-chart")


def test_axes_are_titled_after_the_columns_they_draw(tmp_path: Path) -> None:
    """A line chart's x axis is its x column, never its series column."""
    rows = [{"platform": s, "hour": i, "sessions": 8 * math.sin(i / 9 + k)}
            for k, s in enumerate(["a", "b"]) for i in range(0, 60, 3)]
    svg = _render("line-multi", rows, tmp_path)
    assert ">hour</text>" in svg
    assert ">platform</text>" not in svg


def test_demo_captions_are_emptied_over_caller_rows(tmp_path: Path) -> None:
    """The dumbbell's demo axis title does not survive a caller's data."""
    rows = [{"category": "x", "group_a": 1.0, "group_b": 2.0},
            {"category": "y", "group_a": 1.5, "group_b": 2.5}]
    assert "Median hourly pay" not in _render("dumbbell", rows, tmp_path)


def test_ticks_take_the_decimals_of_their_step() -> None:
    """Whole steps stay whole; fractional steps keep what tells them apart."""
    assert fmt_tick(10.0, 5.0) == "10"
    assert fmt_tick(0.95, 0.05) == "0.95"
    assert fmt_tick(0.5, 0.25) == "0.50"
    assert fmt_tick(0.2, 0.2) == "0.2"
