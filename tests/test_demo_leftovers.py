"""
No figure prints its own demo over somebody else's data.

Every generator ships a demo: rows, a headline written about them, legends and
annotations that name its people, cities and products. Printed over a caller's
rows that text is false, and the report figures of a real project (2026-11-07)
found it seven times in one evening: a timeline legend saying "Flown mission"
over a study calendar, a tree subtitled "Supervised learning..." over a kernel
grammar, a cycle that drew the winter-wheat year whatever it was given.

The test renders every kind from its own demo rows with every display string
replaced by a token ("ux1", "ux2"...). Whatever demo text still prints came
from the generator, not from the data, and ``check_render(kind=...)`` names it.
Two lists say where the rule is knowingly bent, each entry with its reason:

* ``CODE_COLUMNS``: columns whose values are codes the generator dispatches
  on (a label side, a sentiment group), not text it prints. Renaming them
  tests nothing but the dispatch, so they keep their demo values.
* ``KNOWN``: kinds that still leak or fail on renamed rows. ``xfail`` with
  ``strict=True``, so a fixed generator turns its entry into a failure until
  the entry is deleted, and the list can only shrink.

The method's own words ("upper control limit", "collider") are declared by
each generator in ``METHOD_TEXT`` and are never reported.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path
from typing import Any

import pytest

from sprezzature_figures import list_kinds, make_figure
from sprezzature_figures.make_figure import _demo_data_for
from sprezzature_figures.render_checks import check_render

#: Kind -> columns that hold codes, kept as they are.
CODE_COLUMNS: dict[str, set[str]] = {
    "connected-scatter": {"side"},   # which side of the point its label sits
    "wordcloud": {"group"},          # one of praise / gripe / neutral
    "manifold_path": {"series"},     # "path" marks the walked route
    "windrose": {"direction", "band"},  # compass points and speed bins, in order
    "sfdp-largegraph": {"palette_key"},  # a palette hue name
    "map-flow": {"origin", "destination"},  # places, located by their name
    "horizon": {"label"},            # "name  group", split on the double space
    "difference-chart": {"series"},  # plan / actual, the two lines compared
    "liftgain": {"series"},          # the model curve and the random baseline
    "rose": {"cause"},               # the three causes the colours are keyed on
}

#: Calendar names are ordinal codes: a renamed month has no place in the year.
_CALENDAR = {
    "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun",
}

#: Kind -> why it still prints demo text (or fails) over renamed rows.
KNOWN: dict[str, str] = {
    # Categories fixed by the demo: renamed ones are not in the generator's table.
    "alluvial": "axes and categories are fixed in AXES; a renamed category crashes the totals",
    "parallel-sets": "axes and categories are fixed in the demo's table; a renamed one crashes",
    "radviz": "renamed rows leave a dimension empty and the scaling fails (min of nothing)",
    # A fixed list of the demo's names drawn instead of the caller's.
    "arcdiagram": "draws the demo's people as node labels",
    "chord": "draws the demo's teams around the ring",
    "convex-hull": "names the demo's segments in its legend",
    "dependency-wheel": "draws the demo's regions around the wheel",
    "dotdensity": "names the demo's regions",
    "edge-bundling": "draws the demo's modules on the ring",
    "embedding_projector": "labels points from the demo's word table",
    "mosaic": "names the demo's payment methods",
    "population-pyramid": "names the demo's two sexes on its halves",
    "scatter3d": "names the demo's grape varieties in its legend",
    # A sentence written about the demo, printed as a literal.
    "boxen": "prints a takeaway about the demo's latency tiers",
    "icicle": "prints a subtitle about the demo's checkout request",
    "liquid-gauge": "prints the demo lake's caption",
    "map-pie": "prints an annotation about the demo's Africa slice",
    "radial-tree": "prints a subtitle and pillar names from the demo",
    "spectrogram": "prints annotations of the demo's sound events",
    "spike-map": "prints a caption about the demo's megacities",
    "variwide": "prints a caption about the demo's countries",
}

_DATE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?([T ][\d:]+)?$")


def _tokenised(kind: str) -> list[dict[str, Any]]:
    """The demo rows of `kind` with every display string renamed to a token."""
    keep = CODE_COLUMNS.get(kind, set())
    names: dict[str, str] = {}

    def token(value: Any, column: str) -> Any:
        if column in keep:
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text or _DATE.match(text) or text.startswith("#") or text in _CALENDAR:
                return value
            if re.fullmatch(r"[-+]?\d+(\.\d+)?%?", text):
                return value
            return names.setdefault(value, f"ux{len(names) + 1}")
        if isinstance(value, list):
            return [token(item, column) for item in value]
        if isinstance(value, dict):
            return {k: token(v, k) for k, v in value.items()}
        return value

    return [{k: token(v, k) for k, v in row.items()} for row in _demo_data_for(kind)]


def _cases() -> list[Any]:
    """One case per kind, the known ones marked as strict expected failures."""
    cases = []
    for kind in list_kinds():
        marks = [pytest.mark.xfail(strict=True, reason=KNOWN[kind])] if kind in KNOWN else []
        cases.append(pytest.param(kind, marks=marks, id=kind))
    return cases


@pytest.mark.slow
@pytest.mark.parametrize("kind", _cases())
def test_no_demo_text_over_renamed_rows(kind: str, tmp_path: Path) -> None:
    """A render of renamed demo rows carries none of the kind's demo text."""
    rows = _tokenised(kind)
    out = tmp_path / f"{kind}.svg"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        make_figure(kind, rows, out=out, title="Zq title", subtitle="Zq subtitle",
                    embed_fonts=False)
    # A code column keeps its demo values, so they are the caller's text too.
    kept = {str(row[c]) for row in _demo_data_for(kind) for c in CODE_COLUMNS.get(kind, ()) if c in row}
    leftovers = [f for f in check_render(out.read_text(encoding="utf-8"), kind=kind,
                                         allowed_text=sorted(kept))
                 if f.check == "demo_text"]
    assert not leftovers, "\n".join(f"  {f.detail}" for f in leftovers)
