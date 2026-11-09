"""
Layout defects found while the figures of a real report were being built.

Each test reproduces one defect on realistic rows: a formula split at a
non-breaking space, a long label on a returning arrow, two group frames in the
same layers, task names and bars outside a Gantt, a tick label under a turned
axis title, unexplained numbers on a facet panel.

Author
------
Warith Harchaoui <warithmetics@deraison.ai>
"""

from __future__ import annotations

import importlib
import logging
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import make_facet  # noqa: E402
import make_flowchart  # noqa: E402
import make_gantt  # noqa: E402
from _textfit import split_words, wrap_to_width  # noqa: E402

from sprezzature_figures.render_checks import check_render  # noqa: E402

line_multi = importlib.import_module("make_line-multi")
SVG = "{http://www.w3.org/2000/svg}"
NBSP = " "


def _texts(svg: str) -> list[str]:
    """Return every text line of a render.

    Parameters
    ----------
    svg : str
        The SVG document.

    Returns
    -------
    list of str
        The content of each ``<text>`` element.
    """
    return ["".join(t.itertext()) for t in ET.fromstring(svg).iter(f"{SVG}text")]


def _checks(svg: str) -> set[str]:
    """Return the rules a render breaks.

    Parameters
    ----------
    svg : str
        The SVG document.

    Returns
    -------
    set of str
        The names of the rules that fired.
    """
    return {f.check for f in check_render(svg)}


LOOP: list[dict[str, Any]] = [
    {"source": "Inject rho", "target": "Fit the field"},
    {"source": "Fit the field", "target": "Share rejecting"},
    {"source": "Share rejecting", "target": "Inject rho", "back": 1,
     "label": "repeat over draws then over each value of rho"},
]
GROUPS: list[dict[str, Any]] = [
    {"source": "A one", "target": "A two", "source_group": "A", "target_group": "A"},
    {"source": "B one", "target": "B two", "source_group": "B", "target_group": "B"},
    {"source": "X", "target": "A two", "source_group": "B", "target_group": "A"},
    {"source": "A two", "target": "End", "source_group": "A"},
    {"source": "B two", "target": "End", "source_group": "B"},
]


def test_a_non_breaking_space_holds_a_formula_together() -> None:
    """A line never breaks at U+00A0, in the helper or in a box."""
    formula = f"h{NBSP}={NBSP}1"
    assert split_words(f"at {formula} only") == ["at", formula, "only"]
    assert any(formula in line for line in wrap_to_width(f"the error at {formula} only", 40.0, 14.0))
    rows = [{"source": f"The error at {formula} only", "target": "Next"}]
    assert formula in " ".join(_texts(make_flowchart.build_svg(rows, max_box_width=70.0)))


def test_a_long_label_on_a_returning_arrow_sits_beside_its_lane() -> None:
    """Below the lane in LR, right of it in TB: the arrow never runs through the text."""
    for direction, axis in (("LR", 1), ("TB", 0)):
        root = ET.fromstring(make_flowchart.build_svg(LOOP, direction=direction))
        halo = next(r for r in root.iter(f"{SVG}rect") if r.get("class") == "halo")
        start = float(halo.get("y" if axis else "x"))
        back = next(p for p in root.iter(f"{SVG}path") if "back to" in "".join(p.itertext()))
        numbers = [float(v) for v in re.findall(r"-?\d+\.\d+", back.get("d"))]
        lane = max(numbers[axis::2])
        assert start > lane, (direction, start, lane)


def test_group_frames_sharing_layers_never_cover_each_other() -> None:
    """The frames are pushed apart in both directions and the check agrees."""
    for direction in ("LR", "TB"):
        assert "frames_overlap" not in _checks(make_flowchart.build_svg(GROUPS, direction=direction))


def test_the_check_reports_frames_that_cover_each_other() -> None:
    """Two overlapping frames are a finding."""
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200">'
           '<title>t</title><desc>d</desc>'
           '<rect class="fc-group" x="0" y="0" width="50" height="50"/>'
           '<rect class="fc-group" x="40" y="40" width="50" height="50"/></svg>')
    assert "frames_overlap" in _checks(svg)


def test_max_box_width_sets_the_widest_box() -> None:
    """A narrower limit gives narrower, taller boxes when the canvas leaves room."""
    rows = [{"source": "A rather long step name that wraps a lot here", "target": "Next step"}]
    width = {}
    for limit in (110.0, 300.0):
        root = ET.fromstring(make_flowchart.build_svg(rows, width=900, max_box_width=limit))
        width[limit] = max(float(r.get("width")) for r in root.iter(f"{SVG}rect") if r.get("rx") == "10")
    assert width[110.0] == 110.0 < width[300.0]


def test_a_flow_too_long_for_its_canvas_says_so(caplog: Any) -> None:
    """Ten layers on 760 px print small, and a warning names the way out."""
    rows = [{"source": f"Stage {i}", "target": f"Stage {i + 1}"} for i in range(9)]
    with caplog.at_level(logging.WARNING):
        make_flowchart.build_svg(rows, title="Nine steps", width=760)
    assert "direction='TB'" in caplog.text


def test_gantt_opens_its_axis_for_a_negative_start() -> None:
    """A bar before zero stays on the plot and zero stays labelled."""
    rows = [{"task": "Known errors", "start": -40, "end": -5, "team": "w"},
            {"task": "Forecast", "start": 0, "end": 12, "team": "w"}]
    svg = make_gantt.build_svg(rows, title="t", subtitle="s")
    root = ET.fromstring(svg)
    bar = next(r for r in root.iter(f"{SVG}rect") if r.get("id") == "bar-0")
    assert float(bar.get("x")) >= 130.0
    assert "-40" in _texts(svg) or "-20" in _texts(svg)
    assert "0" in _texts(svg)


def test_gantt_long_names_stay_on_the_canvas() -> None:
    """A long task name widens the name column, then wraps; nothing is cut."""
    name = "A very long task name that goes on for many words and would leave the canvas"
    rows = [{"task": name, "start": 0, "end": 3, "team": "w"}]
    svg = make_gantt.build_svg(rows, title="t", subtitle="s")
    assert not {"text_outside_canvas", "text_overflow"} & _checks(svg)
    assert name not in _texts(svg)  # wrapped
    # Name lines are the end-anchored texts of the name column.
    root = ET.fromstring(svg)
    lines = ["".join(t.itertext()) for t in root.iter(f"{SVG}text")
             if t.get("text-anchor") == "end" and t.get("font-size") == "12" and t.get("fill")]
    assert " ".join(lines) == name


def test_line_multi_clears_the_axis_title_on_a_log_scale() -> None:
    """The plot moves right for a long tick; the margin option overrides it."""
    rows = [{"hour": i, "platform": "a", "sessions": 10.0 ** -(i / 2)} for i in range(1, 8)]
    svg = line_multi.build_svg(rows, title="t", subtitle="s", log_y=True, y_label="Level granted")
    assert "axis_title_overlap" not in _checks(svg)
    narrow = line_multi.build_svg(rows, title="t", subtitle="s", log_y=True, y_label="Level granted",
                                  left_margin=44.0)
    assert "axis_title_overlap" in _checks(narrow)


def test_facet_prints_no_bare_change_over_caller_data() -> None:
    """The demo keeps its deltas; caller data gets them only on request, with words."""
    rows = [{"market": m, "month": t, "orders": v}
            for m, base in (("One", 10), ("Two", 40)) for t, v in ((1, base), (2, base + 5), (3, base + 9))]
    assert not [t for t in _texts(make_facet.build_svg(rows, title="t", subtitle="s")) if t.startswith("+")]
    shown = _texts(make_facet.build_svg(rows, title="t", subtitle="s", show_change=True))
    assert any(t.endswith("first to last") for t in shown)
    assert any(t.startswith("+") for t in _texts(make_facet.build_svg()))
