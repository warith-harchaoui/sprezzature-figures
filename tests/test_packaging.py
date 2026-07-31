"""
Packaging smoke test: build a wheel, install it into a throwaway venv, import
the package, and render one stable figure -- the only way to actually catch
"the wheel is missing files" bugs (e.g. figures.json or the scripts package
not being shipped), as opposed to trusting the editable install used by every
other test in this suite.

Marked @pytest.mark.packaging (excluded from the default run: it needs
network access to install dependencies into the fresh venv, and takes tens of
seconds). Run explicitly with:

    pytest -m packaging tests/test_packaging.py

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import subprocess
import sys
import venv
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.packaging
def test_wheel_ships_a_stable_renderable_figure(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(dist_dir)],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    wheels = list(dist_dir.glob("*.whl"))
    assert len(wheels) == 1, f"expected exactly one wheel, got {wheels}"
    wheel = wheels[0]

    venv_dir = tmp_path / "venv"
    venv.EnvBuilder(with_pip=True, clear=True).create(venv_dir)
    venv_python = venv_dir / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")

    subprocess.run(
        [str(venv_python), "-m", "pip", "install", "--quiet", str(wheel)],
        check=True,
        capture_output=True,
        text=True,
    )

    smoke_script = tmp_path / "smoke.py"
    smoke_script.write_text(
        "from pathlib import Path\n"
        "from sprezzature_figures import make_figure, list_kinds\n"
        "stable = list_kinds(status='stable')\n"
        "assert stable, 'no stable kinds registered in the installed wheel'\n"
        "kind = stable[0]\n"
        "from sprezzature_figures.make_figure import _demo_data_for\n"
        "from sprezzature_figures.catalog import resolve_kind\n"
        "data = _demo_data_for(resolve_kind(kind))\n"
        "out = Path('rendered.svg')\n"
        "result = make_figure(kind, data, out=str(out), title='packaging smoke test')\n"
        "assert result.exists() and result.stat().st_size > 0, f'{kind} produced no output'\n"
        "print(f'OK: rendered {kind} -> {result}')\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [str(venv_python), str(smoke_script)],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "OK: rendered" in result.stdout
