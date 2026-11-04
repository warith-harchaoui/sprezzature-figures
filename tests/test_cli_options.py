"""
The Click command offers every figure's own options, and only those.

Both console scripts, ``sprezzature-figures`` and ``make-figure``, run the
Click group in :mod:`sprezzature_figures.cli`, and click is a base
dependency. Until 2026-11-04 these tests compared it with the argparse parser
it grew out of; that parser is gone, so what they pin now is the thing that
parser comparison stood for: ``render <kind>`` grows one flag per keyword the
catalogue says the figure accepts, for every figure, and refuses the rest.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_MANIFEST_ROOT = Path(__file__).resolve().parent.parent


def _console_scripts() -> dict[str, str]:
    """
    ``[project.scripts]``, read with a regex rather than ``tomllib``.

    ``tomllib`` is standard library only from 3.11 and this package supports
    3.10, where the import alone fails -- in CI, while passing on every
    developer machine. sprezzature-cli-gui's own test says exactly this in a
    comment, and it was written there because it had already happened once.
    """
    text = (_MANIFEST_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    block = re.search(r"^\[project\.scripts\]\s*$(.*?)(?=^\[|\Z)", text, re.M | re.S)
    if block is None:
        return {}
    return dict(re.findall(r'^([\w.-]+)\s*=\s*"([^"]+)"', block.group(1), re.M))


def _base_dependencies() -> str:
    """The ``dependencies = [...]`` block as text, comments stripped."""
    text = (_MANIFEST_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    block = re.search(r"^dependencies\s*=\s*\[(.*?)\]", text, re.M | re.S)
    return re.sub(r"#[^\n]*", "", block.group(1)) if block else ""


def _extras() -> set[str]:
    """The extras this package declares."""
    text = (_MANIFEST_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    block = re.search(r"^\[project\.optional-dependencies\]\s*$(.*?)(?=^\[|\Z)", text, re.M | re.S)
    return set(re.findall(r"^([\w.-]+)\s*=\s*\[", block.group(1), re.M)) if block else set()


click = pytest.importorskip("click")
from click.testing import CliRunner  # noqa: E402

from sprezzature_figures.cli import cli  # noqa: E402
from sprezzature_figures.options import options_for  # noqa: E402

#: One figure per shape of option: a plain canvas-and-chrome chart, a
#: chart with its own vocabulary (volume_unit, stage_names), and one with
#: almost nothing (rose takes neither width nor subtitle).
SAMPLE_KINDS = ("bar", "sankey", "rose", "treemap", "waterfall")


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.mark.parametrize("kind", SAMPLE_KINDS)
def test_click_help_lists_exactly_the_figures_options(runner: CliRunner, kind: str) -> None:
    """``render <kind> --help`` documents that figure's keywords, and no others."""
    result = runner.invoke(cli, ["render", kind, "--help"])
    assert result.exit_code == 0
    for option in options_for(kind).values():
        assert option.cli_flag in result.output, f"{kind} --help omits {option.cli_flag}"


def test_click_does_not_offer_an_option_the_figure_lacks(runner: CliRunner) -> None:
    """``rose`` has no canvas size; the flag must not appear, and must not work."""
    assert "width" not in options_for("rose")
    result = runner.invoke(cli, ["render", "rose", "--help"])
    assert "--width" not in result.output
    refused = runner.invoke(cli, ["render", "rose", "--width", "900"])
    assert refused.exit_code == 2
    assert "rose has no option --width" in refused.output


def test_click_error_points_at_the_click_command(runner: CliRunner) -> None:
    """A Click user is sent to ``sprezzature-figures describe``, not to the other binary."""
    result = runner.invoke(cli, ["render", "rose", "--width", "900"])
    assert "sprezzature-figures describe rose" in result.output
    assert "make-figure rose --describe" not in result.output


def test_render_exposes_every_option_of_every_generator(runner: CliRunner) -> None:
    """Every keyword in the catalogue has its flag under ``render <kind> --help``.

    Replaces the comparison with the argparse parser: the property that
    comparison protected was "a flag the figure accepts is a flag you can
    type", and this asks it of the whole catalogue rather than of a sample.
    """
    from sprezzature_figures.catalog import list_kinds

    missing: dict[str, list[str]] = {}
    for kind in list_kinds():
        result = runner.invoke(cli, ["render", kind, "--help"])
        assert result.exit_code == 0, f"render {kind} --help failed: {result.output}"
        absent = [
            option.cli_flag
            for option in options_for(kind).values()
            if option.cli_flag and option.cli_flag not in result.output
        ]
        if absent:
            missing[kind] = absent
    assert missing == {}, f"options with no flag under render <kind> --help: {missing}"


def test_describe_lists_the_same_flags_render_accepts(runner: CliRunner) -> None:
    """``describe`` and ``render --help`` name one set of flags for a figure."""
    described = runner.invoke(cli, ["describe", "sankey"]).output
    for option in options_for("sankey").values():
        if option.cli_flag:
            assert option.cli_flag in described, f"describe sankey omits {option.cli_flag}"


def test_click_list_json_is_the_same_catalogue(runner: CliRunner) -> None:
    import json

    from sprezzature_figures.catalog import list_kinds

    result = runner.invoke(cli, ["list", "--json"])
    assert json.loads(result.output) == list_kinds()


def test_click_refuses_an_option_given_twice(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["render", "bar", "--width", "800", "--set", "width=900"])
    assert result.exit_code == 2
    assert "given twice" in result.output


def test_click_rejects_a_value_outside_a_closed_set(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["render", "bar", "--theme", "neon"])
    assert result.exit_code == 2
    assert "neon" in result.output


@pytest.mark.slow
def test_click_demo_render_keeps_its_own_chrome(tmp_path: Path, runner: CliRunner) -> None:
    out = tmp_path / "sankey.svg"
    result = runner.invoke(cli, ["render", "sankey", "--out", str(out)])
    assert result.exit_code == 0
    assert "Organic search fills the funnel" in out.read_text(encoding="utf-8")


def test_no_chart_kind_is_named_like_a_sub_command() -> None:
    """``render`` takes a kind; no kind should read like one of the commands beside it."""
    from sprezzature_figures.catalog import resolve_kind

    shadowed = {name: resolve_kind(name) for name in cli.commands if resolve_kind(name) is not None}
    assert shadowed == {}, f"these kinds shadow a sub-command: {shadowed}"


def test_check_reports_on_the_file_it_was_given(tmp_path: Path, runner: CliRunner) -> None:
    """``check`` names the SVG it read, so a CI log says which figure failed."""
    svg = tmp_path / "flat.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50"></svg>',
        encoding="utf-8",
    )
    through_click = runner.invoke(cli, ["check", str(svg)])
    assert through_click.exit_code in (0, 1)
    assert str(svg) in through_click.output


def test_both_console_names_resolve_to_the_click_command() -> None:
    """
    ``sprezzature-figures`` and ``make-figure`` are one command.

    ``make-figure`` was the argparse front door until 2026-10-25; both names
    now point at the Click one. The argparse ``make_figure.main`` it left
    behind was removed on 2026-11-04, so there is one implementation to test.
    """
    scripts = _console_scripts()
    assert scripts["sprezzature-figures"] == scripts["make-figure"]
    assert scripts["make-figure"] == "sprezzature_figures.cli:main"


def test_click_is_a_base_dependency_not_an_extra() -> None:
    """Click parses every command line of the package, so it cannot be optional."""
    assert "click" in _base_dependencies()
    assert "cli" not in _extras()
