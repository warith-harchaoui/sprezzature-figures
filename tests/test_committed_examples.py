"""
The figures this package ships as its own shop window have to pass its linter.

``assets/svg-examples/*.svg`` is what README, EXAMPLES.md, the catalog cards and
the published gallery all point at. Nothing checked those files. On 2026-10-15
a sweep of the folder found that 64 of them had drifted from the generator that
writes them and 35 catalog figures had no committed example at all -- the
generators had been fixed and the art had never been re-exported. One of the
drifted files, ``beeswarm.svg``, printed its axis title at ``y=376`` on a
360-tall canvas: clipped, shipped, and on the front page. The generator had been
correct for months.

That is the failure mode this file closes. It does not re-render anything -- it
reads the bytes that are committed and runs the same ``check_render`` the
``check`` command runs, so a stale export cannot sit in the repository looking
finished. Judgements of taste are not here, for the same reason they are not in
``render_checks``: this asks only whether a label is clipped, colliding,
unreadably small, or absent, which the markup answers on its own.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sprezzature_figures.render_checks import check_render

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = REPO_ROOT / "assets" / "svg-examples"

#: ``placeholder_text`` fires on this corpus by design and carries no
#: information here. The rule exists to catch *this house's* demo chrome
#: surfacing in *a caller's* render -- "Quarterly figures" sitting over
#: someone's real sales. These files are the demo renders: their chrome is
#: the content, and "Share of visits by source" is the honest subtitle of a
#: donut about visits by source. Excluded for this corpus only; the rule stays
#: live everywhere it can mean something.
_BY_DESIGN_HERE = frozenset({"placeholder_text"})

#: Examples with no generator anywhere, allowed to fail the gate until one is
#: written. Empty, and meant to stay that way.
#:
#: It held ``map-bars``, ``map-bubble`` and ``map-pie`` for exactly as long as
#: it took to write them: pre-generator assets from the v1.0.0 import, 176
#: ``<path>`` elements and not one ``<text>``, still served by the published
#: gallery. An entry here is a debt, not a category -- the figure is shipping
#: and unreadable, and the note is the only thing keeping that visible.
_NO_GENERATOR_ANYWHERE: frozenset[str] = frozenset()


def _examples() -> list[Path]:
    """Every committed example, English and localised alike."""
    return sorted(EXAMPLES_DIR.glob("*.svg"))


def test_the_examples_folder_is_not_empty() -> None:
    """A gate that finds no files to check passes for the wrong reason.

    The floor is read from the registry rather than written down, because a
    number written down here goes stale the next time a figure is added and
    then guards nothing at a threshold nobody rechecked.
    """
    from sprezzature_figures.catalog.registry import list_kinds

    found = len(_examples())
    assert found >= len(list_kinds()), (
        f"{EXAMPLES_DIR} holds {found} SVGs for {len(list_kinds())} catalogue "
        "kinds, so something has moved and this test is now checking nothing"
    )


@pytest.mark.parametrize("svg_path", _examples(), ids=lambda p: p.stem)
def test_committed_example_passes_the_linter(svg_path: Path) -> None:
    """No shipped figure may carry a defect its own linter can name."""
    findings = [
        f
        for f in check_render(svg_path.read_text(encoding="utf-8"))
        if f.severity == "error" and f.check not in _BY_DESIGN_HERE
    ]
    if svg_path.stem in _NO_GENERATOR_ANYWHERE:
        pytest.xfail(
            f"{svg_path.name} has no generator in this repo or in "
            "sprezzature-maps; see _NO_GENERATOR_ANYWHERE"
        )
    assert not findings, "\n".join(
        f"  [{f.check}] {f.message} ({f.detail})" for f in findings
    )


@pytest.mark.parametrize("svg_path", _examples(), ids=lambda p: p.stem)
def test_committed_example_has_no_illegible_text(svg_path: Path) -> None:
    """Text below the legibility floor is a warning; shipping it is not.

    ``text_too_small`` is a warning in ``render_checks`` because a caller may
    have a reason -- a dense annotation layer, a figure printed at twice its
    authored size. This house's own examples have no such reason: they are
    shown at the size they declare, and ``circle-packing`` shipped four line
    counts at 8.5 px because one of ``_fit_label``'s four paths floored at 8.5
    where the other three floored at 9.
    """
    if svg_path.stem in _NO_GENERATOR_ANYWHERE:
        pytest.skip("no generator; covered by test_committed_example_passes_the_linter")
    small = [
        f
        for f in check_render(svg_path.read_text(encoding="utf-8"))
        if f.check == "text_too_small"
    ]
    assert not small, "\n".join(f"  {f.detail}" for f in small)
