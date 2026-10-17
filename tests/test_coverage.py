"""
The coverage matrix has to stay true, or it is advertising.

``COVERAGE.md`` makes a checkable claim: every chart seaborn, matplotlib,
Plotly, Chart.js / QuickChart, AntV, ECharts, Vega-Lite, Observable Plot,
ggplot2, Highcharts, Datawrapper or RAWGraphs can draw is either answered by
a registered kind here, waiting on a named one, handed to
``sprezzature-maps``, or not a chart. Three ways that claim rots, and one
test each:

- a figure gets renamed and the row still points at the old name;
- a gap gets built and nobody flips the row, so the page still reports a
  hole that has been filled;
- the committed ``coverage.csv`` / ``COVERAGE.md`` drift from the mapping
  they are generated from.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

from build_coverage import (  # noqa: E402
    MAPPING,
    OUT_CSV,
    OUT_MD,
    SOURCES,
    _rows,
    gap_names,
    problems,
    render_markdown,
)

from sprezzature_figures.catalog import list_kinds, resolve_kind  # noqa: E402

ROWS = _rows()


def test_the_mapping_is_internally_sound() -> None:
    """Every covered kind exists, every gap does not, every status is one we know.

    This is the whole validator in one assertion on purpose: its message
    names the offending row and what to do about it, which is more useful
    than a dozen tests that each catch a third of a problem.
    """
    assert problems(ROWS) == []


def test_every_library_names_where_it_was_read() -> None:
    """A row a reader cannot check against its source is a row they have to trust."""
    assert set(MAPPING) == set(SOURCES)
    assert all(SOURCES[library] for library in MAPPING)


def test_no_library_is_listed_twice_under_one_name() -> None:
    """Two rows for one chart would double-count it in the headline numbers."""
    for library, entries in MAPPING.items():
        names = [chart for chart, _kind, _status, _note in entries]
        duplicated = sorted({name for name in names if names.count(name) > 1})
        assert duplicated == [], f"{library} lists {duplicated} more than once"


def test_the_committed_files_match_the_mapping() -> None:
    """Regenerate with `python tools/build_coverage.py` when this fails."""
    assert OUT_MD.read_text(encoding="utf-8") == render_markdown(ROWS) + "\n"
    with OUT_CSV.open(encoding="utf-8", newline="") as handle:
        on_disk = list(csv.DictReader(handle))
    assert on_disk == ROWS


def test_the_matrix_covers_the_libraries_the_promise_names() -> None:
    """The README's claim and this file's contents have to be the same list."""
    promised = {
        "seaborn",
        "matplotlib",
        "plotly",
        "quickchart",
        "antv",
        "echarts",
        "vega-lite",
        "observable-plot",
        "ggplot2",
        "highcharts",
        "datawrapper",
        "rawgraphs",
    }
    assert promised <= set(MAPPING)


def test_the_build_list_is_ordered_by_how_many_libraries_ask() -> None:
    """The order is the argument: seven libraries want a pie, one wants voxels."""
    wanted = gap_names(ROWS)
    if not wanted:
        pytest.skip("nothing left to build")
    asks = [
        sum(1 for row in ROWS if row["status"] == "gap" and row["kind"] == name) for name in wanted
    ]
    assert asks == sorted(asks, reverse=True)


def test_geography_is_pointed_at_the_sibling_package_by_name() -> None:
    """ "It lives elsewhere" is only useful if it says where.

    The point of the sibling status is to stop the two catalogues drawing
    the same map twice, which needs a pointer, not a shrug.
    """
    siblings = [row for row in ROWS if row["status"] == "sibling"]
    assert siblings, "the maps boundary should be stated, not implied"
    for row in siblings:
        assert "sprezzature-maps" in row["note"]
        assert "`" in row["note"], f"{row['chart']} does not name a sibling generator"


def test_thematic_geography_stayed_here() -> None:
    """The maps that are abstractions rather than basemaps are not siblings.

    A hex-binned map or a dot-density plate needs no coastline and no
    projection library; moving those out would be giving away figures this
    package already draws.
    """
    for kind in ("dotdensity", "hexmap", "hexbin-map", "binned-grid-map", "spike-map"):
        assert resolve_kind(kind) is not None


def test_every_registered_kind_is_a_real_answer_somewhere() -> None:
    """Report which kinds no other library asks for -- the ones that are ours alone.

    Not a failure: a catalogue that only matched other people's catalogues
    would have nothing of its own. This pins the number so a drop in it is
    visible.
    """
    answered = {row["kind"] for row in ROWS if row["status"] == "covered"}
    ours_alone = sorted(set(list_kinds()) - answered)
    assert len(ours_alone) < len(list_kinds()), "no kind answers any other library"
