"""
The two command lines must describe the same figures the same way.

``make-figure`` (argparse, always installed) and ``sprezzature-figures``
(Click, behind the ``[cli]`` extra) are two spellings of one tool. They
grow their per-figure flags by different mechanisms -- a two-pass parse on
one side, a Click ``Command`` that rebuilds its parameter list on the
other -- from the same ``options_schema``. These tests pin the thing that
would otherwise drift: that a flag exists in both or in neither.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

from pathlib import Path

import pytest

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


def test_click_describe_matches_the_argparse_describe(
    runner: CliRunner, capsys: pytest.CaptureFixture
) -> None:
    """One figure, one description, whichever command asked for it."""
    from sprezzature_figures.make_figure import main as argparse_main

    argparse_main(["sankey", "--describe"])
    from_argparse = capsys.readouterr().out.strip()
    from_click = runner.invoke(cli, ["describe", "sankey"]).output.strip()
    assert from_click == from_argparse


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
def test_both_commands_render_the_same_figure(tmp_path: Path, runner: CliRunner) -> None:
    """Same kind, same options, byte-for-byte the same SVG from either command."""
    from sprezzature_figures.make_figure import main as argparse_main

    through_argparse = tmp_path / "argparse.svg"
    argparse_main(
        ["bar", "--out", str(through_argparse), "--width", "1234", "--set", "subtitle=Q3"]
    )
    through_click = tmp_path / "click.svg"
    result = runner.invoke(
        cli,
        ["render", "bar", "--out", str(through_click), "--width", "1234", "--set", "subtitle=Q3"],
    )
    assert result.exit_code == 0
    assert through_click.read_text(encoding="utf-8") == through_argparse.read_text(encoding="utf-8")


@pytest.mark.slow
def test_click_demo_render_keeps_its_own_chrome(tmp_path: Path, runner: CliRunner) -> None:
    out = tmp_path / "sankey.svg"
    result = runner.invoke(cli, ["render", "sankey", "--out", str(out)])
    assert result.exit_code == 0
    assert "Organic search fills the funnel" in out.read_text(encoding="utf-8")


def test_no_chart_kind_is_named_like_a_sub_command() -> None:
    """``make-figure redraw`` must mean the command, and never a figure.

    The argparse command line has no sub-parser: the first word is either
    a verb or a chart kind, decided by this exact check. A figure added
    later under one of these names would silently take the word over.
    """
    from sprezzature_figures.catalog import resolve_kind
    from sprezzature_figures.make_figure import _VERBS

    shadowed = {verb: resolve_kind(verb) for verb in _VERBS if resolve_kind(verb) is not None}
    assert shadowed == {}, f"these kinds shadow a sub-command: {shadowed}"


def test_both_command_lines_offer_the_same_commands() -> None:
    """Whatever one can do, the other can -- including the three that were Click-only.

    ``redraw``, ``recommend`` and ``check`` had routes in the HTTP API and
    commands in the Click twin, and no spelling at all in the
    always-installed ``make-figure``.
    """
    from sprezzature_figures.make_figure import _VERBS

    # `render` is the bare `make-figure <kind>` form, which needs no verb.
    assert set(cli.commands) == set(_VERBS) | {"render"}


def test_both_command_lines_report_the_same_findings(tmp_path: Path, runner: CliRunner) -> None:
    """``check`` answers the same way whichever command asked."""
    from sprezzature_figures.make_figure import _VERBS

    svg = tmp_path / "flat.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50"></svg>',
        encoding="utf-8",
    )
    through_click = runner.invoke(cli, ["check", str(svg)])
    code = _VERBS["check"]([str(svg)])
    assert code == through_click.exit_code
    assert str(svg) in through_click.output


def test_both_console_names_resolve_to_the_click_command() -> None:
    """
    ``sprezzature-figures`` and ``make-figure`` are one command.

    ``make-figure`` was the argparse front door until 2026-10-25; both names
    now point at the Click one, so the parity the tests above check is no
    longer an agreement that has to be maintained between two installed
    commands — it is one command compared against the internal implementation
    it grew out of.

    That internal ``make_figure.main`` is now unreachable as an entry point.
    It is left in place deliberately: the click command still imports a dozen
    helpers that live beside it, and pulling the parser out of 662 interleaved
    lines is its own change, not a side effect of this one.
    """
    from pathlib import Path

    import tomllib

    root = Path(__file__).resolve().parent.parent
    scripts = tomllib.loads((root / "pyproject.toml").read_text())["project"]["scripts"]
    assert scripts["sprezzature-figures"] == scripts["make-figure"]
    assert scripts["make-figure"] == "sprezzature_figures.cli:main"


def test_click_is_a_base_dependency_not_an_extra() -> None:
    """With argparse gone from the console scripts, click cannot be optional."""
    from pathlib import Path

    import tomllib

    root = Path(__file__).resolve().parent.parent
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    assert any(dep.startswith("click") for dep in project["dependencies"])
    assert "cli" not in project.get("optional-dependencies", {})
