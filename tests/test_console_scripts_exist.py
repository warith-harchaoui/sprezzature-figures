"""
Every command the help text names has to be a command you can run.

Found three times across the suite, never by a crash: a script builds its
parser with ``prog="sprezzature-…"`` and nothing installs that name, so the
usage line and every example tell the reader to type a command that is not
there. ``caption_diarize.py`` in sprezzature-audio had it, both of that
package's installers had it, and sprezzature-ux-laws shipped its entire
auditor with no console script at all. Documentation that says
``python scripts/x.py`` has the same problem from the other side: that path
exists in a clone and not in a wheel.

Nothing here is wrong in this package today. The check is cheap and derives
both sides from the files rather than from a list kept by hand, so it stays
true as scripts are added.

Author
------
Warith HARCHAOUI <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import tomllib

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

#: A ``prog=`` or Click ``name=`` argument spelling a suite command name.
_PROG_RE = re.compile(r'(?:prog|name)\s*=\s*["\'](sprezzature[a-z0-9-]*)["\']')


def _declared_console_scripts() -> set[str]:
    """The names ``pip install`` actually puts on a user's PATH."""
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        return set(tomllib.load(handle)["project"].get("scripts", {}))


def _advertised_names() -> list[tuple[str, str]]:
    """``(script file name, command it tells the reader to type)`` pairs."""
    out: list[tuple[str, str]] = []
    for path in sorted(SCRIPTS_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in _PROG_RE.finditer(text):
            out.append((path.name, match.group(1)))
    return out


@pytest.mark.parametrize(
    "script_name,advertised",
    _advertised_names(),
    ids=lambda value: value,
)
def test_the_command_the_help_names_is_a_command_that_exists(
    script_name: str, advertised: str
) -> None:
    """A ``prog=`` must match a console script pyproject.toml installs."""
    declared = _declared_console_scripts()
    assert advertised in declared, (
        f"{script_name} tells the reader to run {advertised!r}, which "
        f"[project.scripts] does not install. Installed: {sorted(declared)}. "
        f"Either declare it, or name the script after something that exists."
    )


def test_every_console_script_points_at_something_importable() -> None:
    """The other direction: no entry point naming a module that is not there.

    Skipped on a checkout that was never installed. The mapped script package
    (``..._scripts``) only exists once pip has read ``[tool.setuptools]
    package-dir``, so on a bare clone this would fail for the environment
    rather than for the code. CI installs the package first, which is where
    the check is meant to bite.
    """
    import importlib
    import importlib.util

    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        scripts = tomllib.load(handle)["project"].get("scripts", {})

    for name, target in sorted(scripts.items()):
        module_name, _, attribute = target.partition(":")
        if importlib.util.find_spec(module_name.split(".")[0]) is None:
            pytest.skip(
                f"{module_name.split('.')[0]} is not importable here: this "
                f"checkout is not installed (pip install -e .)."
            )
        module = importlib.import_module(module_name)
        assert hasattr(module, attribute), (
            f"console script {name} points at {target}, but {module_name} has "
            f"no attribute {attribute!r}."
        )
