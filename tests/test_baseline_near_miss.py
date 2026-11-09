"""
Wrapping never moves a first line: the ``baseline_near_miss`` rule.

Three cards side by side, each centring its own text vertically: the middle
subtitle fits on one line, its neighbours' wrap to two, and the middle title
sits half a line lower than the two others. Nothing overlaps and nothing
leaves the canvas, so every other rule passes; the row no longer reads as a
row. ``check_render`` reports it as a warning, and the generators that lay
out sibling blocks (flowchart, treemap, timeline) share one block height so
they never produce it.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

import pytest

from sprezzature_figures import check_render, make_figure

# ── Fixtures ─────────────────────────────────────────────────────────────


def _svg(corps: str) -> str:
    """A minimal figure with its accessible name, so findings stay on topic."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 240" role="img" '
        'aria-labelledby="t d"><title id="t">Cards</title>'
        '<desc id="d">Three cards side by side.</desc>'
        f"{corps}</svg>"
    )


def _card(x: float, title: str, sub: list[str], first: float) -> str:
    """One card: a bold title and its subtitle lines, one ``<text>`` each."""
    out = [
        f'<rect x="{x - 100}" y="40" width="200" height="140" fill="#F5F5F7"/>',
        f'<text x="{x}" y="{first}" font-size="18" font-weight="700" '
        f'text-anchor="middle">{title}</text>',
    ]
    for i, line in enumerate(sub):
        out.append(
            f'<text x="{x}" y="{first + 26 + i * 20}" font-size="15" '
            f'text-anchor="middle">{line}</text>'
        )
    return "".join(out)


def _centred(n_sub: int) -> float:
    """First baseline of a card that centres its own block (the defect)."""
    block = 26 + (n_sub - 1) * 20
    return 110 - block / 2


#: The middle card's subtitle fits one line, so a self-centring card puts its
#: title 10 px lower than its two neighbours'.
DEFECT = _svg(
    _card(120, "Collect", ["every source", "in one place"], _centred(2))
    + _card(360, "Clean", ["one pass"], _centred(1))
    + _card(600, "Model", ["fit, then", "score held out"], _centred(2))
)

#: The same three cards laid out from the shared block height: every title on
#: one baseline, the shorter subtitle simply ends sooner.
ALIGNED = _svg(
    _card(120, "Collect", ["every source", "in one place"], _centred(2))
    + _card(360, "Clean", ["one pass"], _centred(2))
    + _card(600, "Model", ["fit, then", "score held out"], _centred(2))
)


def _near_misses(svg: str) -> list:
    return [f for f in check_render(svg) if f.check == "baseline_near_miss"]


# ── The rule ─────────────────────────────────────────────────────────────


def test_a_title_moved_by_its_neighbours_wrapping_is_reported() -> None:
    found = _near_misses(DEFECT)
    assert found, "the middle title sits 10 px below its neighbours and nothing said so"
    assert all(f.severity == "warning" for f in found)
    detail = " ".join(f.detail for f in found)
    # The finding names the text and the offset, so it can be acted on.
    assert "'Clean'" in detail and "dy=10.0px" in detail


def test_cards_laid_out_from_a_shared_height_are_clean() -> None:
    assert _near_misses(ALIGNED) == []
    assert not [f for f in check_render(ALIGNED) if f.severity == "error"]


def test_the_first_line_of_a_tspan_block_is_what_is_compared() -> None:
    """A block written as one ``<text>`` with tspan lines starts at its first tspan."""

    def block(x: float, lines: list[str], first: float) -> str:
        spans = "".join(
            f'<tspan x="{x}" y="{first + i * 20}">{s}</tspan>' for i, s in enumerate(lines)
        )
        return f'<text font-size="15" text-anchor="middle">{spans}</text>'

    defect = _svg(
        block(120, ["Raw", "data"], 100)
        + block(360, ["Ship"], 110)
        + block(600, ["Clean", "and align"], 100)
    )
    aligned = _svg(
        block(120, ["Raw", "data"], 100)
        + block(360, ["Ship"], 100)
        + block(600, ["Clean", "and align"], 100)
    )
    assert _near_misses(defect)
    assert _near_misses(aligned) == []


def test_bottom_anchored_labels_with_their_first_baselines_aligned_are_clean() -> None:
    """Labels under bars: one wraps to two lines, the first lines still share a baseline."""
    corps = "".join(
        f'<text x="{x}" y="200" font-size="14" text-anchor="middle">{a}</text>'
        + (f'<text x="{x}" y="217" font-size="14" text-anchor="middle">{b}</text>' if b else "")
        for x, a, b in ((100, "North", None), (250, "South", "and islands"), (400, "East", None))
    )
    assert _near_misses(_svg(corps)) == []


def test_a_second_line_is_not_a_near_miss_of_its_neighbour() -> None:
    """A whole line height apart is a different line, not a missed baseline."""
    corps = (
        '<text x="100" y="100" font-size="14">Left label</text>'
        '<text x="300" y="118" font-size="14">Right, one line lower</text>'
    )
    assert _near_misses(_svg(corps)) == []


def test_labels_placed_by_their_data_alone_are_not_a_row() -> None:
    """Two map or scatter labels a few pixels apart are not evidence of a row."""
    corps = (
        '<text x="100" y="100" font-size="14" font-weight="700">Lyon</text>'
        '<text x="300" y="106" font-size="14" font-weight="700">Marseille</text>'
    )
    assert _near_misses(_svg(corps)) == []


# ── The generators that lay out sibling blocks ───────────────────────────


@pytest.mark.parametrize(
    "kind, rows",
    [
        # Left to right: one box wraps to three lines, the others fit on one,
        # and one group frame sits around two of them.
        (
            "flowchart",
            [
                {
                    "source": "Raw data",
                    "target": "Clean it",
                    "source_group": "Data",
                    "target_group": "Data",
                },
                {
                    "source": "Clean it",
                    "target": "Score the model on the held-out rows of last quarter",
                },
                {
                    "source": "Score the model on the held-out rows of last quarter",
                    "target": "Ship",
                },
            ],
        ),
    ],
)
def test_generators_keep_sibling_first_lines_on_one_baseline(
    kind: str, rows: list, tmp_path
) -> None:
    out = make_figure(kind, rows, out=tmp_path / f"{kind}.svg")
    assert _near_misses(out.read_text(encoding="utf-8")) == []
