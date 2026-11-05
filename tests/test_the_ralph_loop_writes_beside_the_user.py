"""The Ralph loop installed from the wheel writes under the cwd, not site-packages.

The defect this guards. ``ralph_eyeball_loop.py`` puts its PNGs, assessments
and critique ledger in ``<root>/.private/ralph-loop/``, with ``<root>`` the
parent of the directory holding the script. In a clone that is the repository,
and ``.private/`` is gitignored there. The README also says the wheel carries
the loop and ``python -m sprezzature_figures_scripts.ralph_eyeball_loop`` runs
it; installed that way, the same parent is ``site-packages/``, and every run
wrote into the interpreter's own tree.

The test lays the script out as the wheel does (no ``pyproject.toml`` beside
``sprezzature_figures_scripts/``), imports it from there, and asks where it
would write.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ralph_eyeball_loop.py"


def _import_from(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return module


def test_installed_layout_writes_under_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    site = tmp_path / "site-packages"
    (site / "sprezzature_figures_scripts").mkdir(parents=True)
    copy = site / "sprezzature_figures_scripts" / "ralph_eyeball_loop.py"
    shutil.copy(SCRIPT, copy)
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)

    module = _import_from(copy, "_ralph_as_installed")

    where: Path = module._PRIVATE_LOOP_DIR
    assert where == work / ".private" / "ralph-loop"
    assert site not in where.parents


def test_a_clone_still_writes_into_its_own_private_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    module = _import_from(SCRIPT, "_ralph_from_clone")
    where: Path = module._PRIVATE_LOOP_DIR
    assert where == SCRIPT.parents[1] / ".private" / "ralph-loop"
