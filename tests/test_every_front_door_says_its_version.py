"""
Every console script answers ``-V`` and ``--version`` with the installed version.

Until 2.9.0 only ``sprezzature-figures-mcp`` did. The front door
(``sprezzature-figures`` / ``make-figure``, and ``python -m
sprezzature_figures``) had no version option at all, and
``sprezzature-studio`` knew ``--version`` but not ``-V``. Three entry points
of one package disagreeing on how to ask the most basic question.

The expected string is :func:`importlib.metadata.version`, the source Click
reads, so a stale editable install shows up as the same number on both sides
rather than as a failure here; what this guards is the flag, not the release.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

import subprocess
import sys
from importlib.metadata import version

import click
import pytest

from sprezzature_figures.cli import main as figures_main
from sprezzature_figures.studio.cli import main as studio_main

VERSION = version("sprezzature-figures")
FLAGS = ("-V", "--version")


def _run(command: click.Command, flag: str, prog: str, capsys: pytest.CaptureFixture) -> str:
    try:
        command.main(args=[flag], prog_name=prog, standalone_mode=False)
    except SystemExit as stop:  # pragma: no cover - standalone_mode=False returns
        assert stop.code in (0, None)
    return capsys.readouterr().out


@pytest.mark.parametrize("flag", FLAGS)
@pytest.mark.parametrize("prog", ["sprezzature-figures", "make-figure"])
def test_front_door_says_its_version(prog: str, flag: str, capsys: pytest.CaptureFixture) -> None:
    """Both names reach the same group; the suffix is what this asserts.

    Click's ``version_option`` callback remembers the first program name it
    printed (``nonlocal prog_name``), so in one test process the second name
    would come back as the first. A real console script is a fresh process
    each time; the exact ``<prog>, version <v>`` line is checked by the
    subprocess test below.
    """
    printed = _run(figures_main, flag, prog, capsys)
    assert printed.strip().endswith(f", version {VERSION}"), printed


@pytest.mark.parametrize("flag", FLAGS)
def test_studio_says_its_version(flag: str, capsys: pytest.CaptureFixture) -> None:
    printed = _run(studio_main, flag, "sprezzature-studio", capsys)
    assert printed.strip().endswith(f", version {VERSION}"), printed


@pytest.mark.parametrize("flag", FLAGS)
def test_mcp_server_says_its_version(flag: str, capsys: pytest.CaptureFixture) -> None:
    from sprezzature_figures.mcp import main as mcp_main

    assert mcp_main([flag]) == 0
    assert capsys.readouterr().out.strip().endswith(f", version {VERSION}")


@pytest.mark.parametrize("flag", FLAGS)
def test_module_run_says_its_version(flag: str) -> None:
    """``python -m sprezzature_figures`` goes through ``__main__``, a separate path."""
    done = subprocess.run(
        [sys.executable, "-m", "sprezzature_figures", flag],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == f"sprezzature-figures, version {VERSION}"


def test_no_sub_command_takes_the_version_spellings() -> None:
    """A sub-command option spelled ``-V`` would read as the group's flag to a person."""
    offenders = [
        f"{name} {opt}"
        for name, sub in figures_main.commands.items()
        for param in sub.params
        for opt in (*param.opts, *param.secondary_opts)
        if opt in FLAGS
    ]
    assert offenders == []
