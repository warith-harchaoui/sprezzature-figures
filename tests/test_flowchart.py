"""
The flowchart draws the caller's process and nothing else.

A method diagram in a report is a list of steps, the arrows between them, the
text on some arrows, a frame around some steps and, for a loop, one arrow
going back. These tests hold the generator to that: every word the caller
gave is drawn, no word of the demo is, a long name wraps between words and
never inside one, a returning arrow is drawn apart from the forward ones, and
the same rows always give the same bytes.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import make_flowchart  # noqa: E402

from sprezzature_figures.render_checks import check_render  # noqa: E402

NS = {"s": "http://www.w3.org/2000/svg"}

ROWS: list[dict[str, Any]] = [
    {"source": "Act on one thing", "target": "Render an observable artifact"},
    {"source": "Render an observable artifact", "target": "Judge with something independent"},
    {"source": "Judge with something independent", "target": "Decide and write the reason",
     "label": "verdict"},
    {"source": "Decide and write the reason", "target": "Act on one thing", "label": "next turn",
     "back": 1},
]


def _texts(svg: str) -> list[str]:
    """Every visible text line of a render."""
    root = ET.fromstring(svg)
    return ["".join(t.itertext()) for t in root.iter("{http://www.w3.org/2000/svg}text")]


def test_every_caller_word_is_drawn_and_no_demo_word_is() -> None:
    """Node names and arrow labels come back; the demo's never show."""
    svg = make_flowchart.build_svg(ROWS)
    drawn = " ".join(_texts(svg))
    for word in ("Act", "observable", "independent", "reason", "verdict", "next turn"):
        assert word in drawn
    for demo in ("Raw data", "Modelling", "held-out", "Ship the forecast"):
        assert demo not in drawn
    assert make_flowchart.DEMO_TITLE not in svg


def test_a_returning_arrow_is_drawn_apart_from_the_flow() -> None:
    """The back edge gets its own lane path, the forward edges their curves."""
    svg = make_flowchart.build_svg(ROWS)
    titles = re.findall(r"<title>([^<]*)</title></path>", svg)
    assert any("back to" in t for t in titles)
    assert sum("back to" not in t for t in titles) == 3


def test_long_names_wrap_between_words_and_never_inside_one() -> None:
    """Every line is made of whole words of the name it belongs to."""
    name = "Supercalifragilistic expialidocious arrangement of components"
    svg = make_flowchart.build_svg([{"source": name, "target": "Done"}], width=360)
    lines = [t for t in _texts(svg) if t and t != "Done"]
    words = set(name.split())
    assert len(lines) >= 2
    for line in lines:
        assert set(line.split()) <= words
    assert "-" not in "".join(lines)


def test_a_typed_line_break_forces_a_new_line() -> None:
    """A CSV cell's ``\\n`` (two characters) starts a new line in the box."""
    svg = make_flowchart.build_svg([{"source": "First line\\nsecond line", "target": "End"}])
    lines = _texts(svg)
    assert "First line" in lines and "second line" in lines


def test_groups_frame_their_members_and_are_named() -> None:
    """A group's name is drawn once, as the frame's title."""
    rows = [dict(r, source_group="Loop", target_group="Loop") for r in ROWS]
    lines = _texts(make_flowchart.build_svg(rows))
    assert lines.count("Loop") == 1


def test_top_to_bottom_stacks_the_layers_vertically() -> None:
    """Direction TB makes the canvas grow down the layers."""
    chain = [{"source": f"step {i}", "target": f"step {i + 1}"} for i in range(5)]
    lr = ET.fromstring(make_flowchart.build_svg(chain))
    tb = ET.fromstring(make_flowchart.build_svg(chain, direction="TB"))
    assert float(tb.get("height", 0)) > float(lr.get("height", 0))


def test_the_same_rows_give_the_same_bytes_and_a_clean_check() -> None:
    """Deterministic, and the house linter has nothing to say."""
    first = make_flowchart.build_svg(ROWS)
    assert first == make_flowchart.build_svg(ROWS)
    assert check_render(first) == []
