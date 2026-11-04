"""
Every console script of the package is a Click command, and nothing in the
package parses a command line with argparse.

The suite settled on Click alone for its own command lines. In this package
that took two steps: the front door moved on 2026-10-25, and the last
argparse parsers (the ``sprezzature-figures-mcp`` server and the dead
``make_figure.main``) went on 2026-11-04. This guard is what keeps a new
console script from bringing argparse back.

The standalone generator scripts under ``scripts/`` are outside it on
purpose: they are not console scripts, they run from a downloaded skill with
nothing but the standard library, and ``scripts/_render.py`` builds their
flags from each ``build_svg`` signature.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

import ast
import importlib
import re
from pathlib import Path

import click
import pytest

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "sprezzature_figures"


def _console_scripts() -> dict[str, str]:
    """``[project.scripts]``, read with a regex: ``tomllib`` is 3.11+, the floor is 3.10."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    block = re.search(r"^\[project\.scripts\]\s*$(.*?)(?=^\[|\Z)", text, re.M | re.S)
    assert block is not None, "pyproject.toml has no [project.scripts] table"
    return dict(re.findall(r'^([\w.-]+)\s*=\s*"([^"]+)"', block.group(1), re.M))


SCRIPTS = _console_scripts()


def test_there_are_console_scripts_to_check() -> None:
    """A regex that stopped matching would make every case below vanish."""
    assert len(SCRIPTS) >= 4, SCRIPTS


@pytest.mark.parametrize("name", sorted(SCRIPTS))
def test_console_script_answers_help_the_click_way(
    name: str, capsys: pytest.CaptureFixture
) -> None:
    """``<script> --help`` exits 0 and prints Click's ``Usage:``, not argparse's ``usage:``."""
    module_name, _, attribute = SCRIPTS[name].partition(":")
    target = getattr(importlib.import_module(module_name), attribute)
    if isinstance(target, click.Command):
        code = target.main(args=["--help"], prog_name=name, standalone_mode=False)
    else:
        try:
            code = target(["--help"])
        except SystemExit as stop:
            code = stop.code
    assert code in (0, None), f"{name} --help exited {code}"
    printed = capsys.readouterr().out
    assert printed.startswith("Usage:"), f"{name} --help is not Click's: {printed[:80]!r}"


def _imports_argparse(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(a.name == "argparse" for a in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and node.module == "argparse":
            return True
    return False


def test_no_package_module_imports_argparse() -> None:
    """The package's own modules parse arguments with Click only."""
    offenders = sorted(
        str(path.relative_to(ROOT)) for path in PACKAGE.rglob("*.py") if _imports_argparse(path)
    )
    assert offenders == [], f"argparse imported in: {offenders}"


def test_no_console_script_points_into_scripts() -> None:
    """The exemption for ``scripts/`` holds only while none of them is a console script."""
    assert all(target.startswith("sprezzature_figures.") for target in SCRIPTS.values()), SCRIPTS
