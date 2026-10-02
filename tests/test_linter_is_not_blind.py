"""
The linter has to look at the code before "all checks passed" means anything.

Until 2026-10-02 ``[tool.ruff] extend-exclude`` held ``scripts``, which is
82 000 of this package's 102 000 lines of Python: every ``make_*`` generator,
``audit_figure.py``, ``ralph_eyeball_loop.py``, ``_style.py``, ``_svg.py``.
All of it ships in the wheel as ``sprezzature_figures_scripts``. The CI step
read ``ruff check sprezzature_figures tools tests`` and reported success, and
what it meant was that ruff had been handed a fifth of the package and one
directory it was configured to skip anyway.

What was hiding there: four unused imports, eleven loop variables named and
then ignored, three ``l`` identifiers that a reader cannot tell from ``1``, a
``raise`` inside an ``except`` with no ``from``, an f-string with no
placeholder, and ``from typing import Callable, Sequence, Tuple`` stranded in
the middle of ``_svg.py``, directly under the last line of a function body.
None of them broke a render. That is the point: a gate that only catches what
already crashes is not a gate.

This test does not lint anything. It asserts that the configuration still
lets ruff reach the code, so the exclusion cannot quietly come back.

Author
------
Warith HARCHAOUI <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from pathlib import Path

import pytest
import tomllib

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Directories that must stay within the linter's reach. ``assets`` is
#: generated art and is legitimately excluded; these are hand-written code.
_MUST_BE_LINTED = ("scripts", "tests", "tools", "sprezzature_figures")

#: Rules that exist to catch a mistake rather than to modernise syntax. One of
#: these silenced for ``scripts/*`` would put the blind spot back one rule at a
#: time instead of all at once.
_ERROR_GRADE = ("F", "E7", "E9", "B0")


def _ruff_config() -> dict:
    """The ``[tool.ruff]`` table, as the linter reads it."""
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle).get("tool", {}).get("ruff", {})


@pytest.mark.parametrize("directory", _MUST_BE_LINTED)
def test_the_linter_can_reach_every_directory_of_hand_written_code(directory: str) -> None:
    """No hand-written source directory is excluded wholesale."""
    config = _ruff_config()
    excluded = set(config.get("extend-exclude", [])) | set(config.get("exclude", []))
    assert directory not in excluded, (
        f"{directory}/ is excluded from ruff, so 'all checks passed' says nothing "
        f"about it. Silence individual rules under [tool.ruff.lint.per-file-ignores] "
        f"instead of hiding the directory."
    )


def test_scripts_keeps_the_rules_that_catch_mistakes() -> None:
    """The per-file relief for ``scripts/`` stays cosmetic."""
    ignores = (
        _ruff_config()
        .get("lint", {})
        .get("per-file-ignores", {})
        .get("scripts/*", [])
    )
    kept_out = [rule for rule in ignores if rule.startswith(_ERROR_GRADE)]
    assert not kept_out, (
        f"{kept_out} silenced for scripts/*. Those rules report real mistakes, "
        f"not style. Only syntax-modernisation and ordering rules belong here."
    )
