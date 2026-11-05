"""
A render with no ``out`` lands in the working directory, nowhere else.

Every generator falls back to ``assets/svg-examples/<kind>.svg`` one level
above ``scripts/``. Reached through ``make_figure()`` or ``sprezzature-figures
render``, that fallback overwrote the committed example in a checkout and wrote
under ``site-packages/`` in an installed package: a bare ``render bar`` edited
the shop window, or the interpreter. Both doors now default to
``<kind>.svg`` in the current directory, and these tests hold them to it
without touching the committed example.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from sprezzature_figures import make_figure
from sprezzature_figures.cli import cli

EXAMPLE = Path(__file__).resolve().parent.parent / "assets" / "svg-examples" / "bar.svg"


@pytest.fixture
def example_untouched():
    """Fail if the committed ``bar.svg`` example is rewritten during the test."""
    before = EXAMPLE.stat().st_mtime_ns
    yield
    assert EXAMPLE.stat().st_mtime_ns == before, "the committed example was rewritten"


def test_make_figure_without_out_writes_kind_svg_in_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, example_untouched: None
) -> None:
    monkeypatch.chdir(tmp_path)
    path = make_figure("bar")
    assert path == (tmp_path / "bar.svg").resolve()
    assert path.read_text(encoding="utf-8").lstrip().startswith(("<svg", "<?xml"))


def test_cli_render_without_out_writes_kind_svg_in_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, example_untouched: None
) -> None:
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli, ["render", "bar"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "bar.svg").exists()
    assert str((tmp_path / "bar.svg").resolve()) in result.output


def test_an_alias_names_the_file_after_the_canonical_kind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    path = make_figure("connected_scatter")
    assert path.name == "connected-scatter.svg"
    assert path.parent == tmp_path.resolve()
