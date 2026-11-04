"""
A caller's mistake is a ValueError that names it, not a crash deep in a generator.

Two generators used to fail on input the caller controls with an exception
that said nothing about that input: ``sankey`` with fewer ``stage_names``
than the flows have layers raised ``IndexError`` while drawing the headings,
and ``wordcloud`` with an unknown ``group`` raised a bare ``KeyError``. Both
reach the command line and the HTTP API, where a ``ValueError`` becomes a
readable message and a 422; the other two became a traceback and a 500.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sprezzature_figures import make_figure


def test_sankey_with_too_few_stage_names_says_how_many_it_needs(tmp_path: Path) -> None:
    """The demo flows form four layers; two names must be refused by count."""
    with pytest.raises(ValueError, match=r"2 name\(s\).*4 layers"):
        make_figure("sankey", None, out=tmp_path / "s.svg", stage_names=["a", "b"])


def test_wordcloud_with_an_unknown_group_names_the_known_ones(tmp_path: Path) -> None:
    """An unknown theme is refused with the list of themes that exist."""
    rows = [{"word": "grinder", "count": 3, "group": "meh"}]
    with pytest.raises(ValueError, match=r"'meh'.*'praise', 'gripe', 'neutral'"):
        make_figure("wordcloud", rows, out=tmp_path / "w.svg")
