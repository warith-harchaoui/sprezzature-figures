"""
Packaging smoke tests: build a wheel, install it into throwaway venvs, and
verify the installed package actually works. This is the only way to catch
"the wheel is missing files" bugs (figures.json, the scripts package, a new
subpackage not added to pyproject's packages list) that an editable install
hides, and to confirm the install procedures documented in the README hold
on a clean machine.

Marked @pytest.mark.packaging (excluded from the default run: needs network
to install into fresh venvs, and takes tens of seconds). Cross-platform:
every subprocess uses the venv's own python and OS-correct script paths, so
these run on macOS, Linux, and Windows CI alike. Run explicitly with:

    pytest -m packaging tests/test_packaging.py

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

import subprocess
import sys
import venv
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
_IS_WINDOWS = sys.platform == "win32"


def _venv_python(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts/python.exe" if _IS_WINDOWS else "bin/python")


def _venv_script(venv_dir: Path, name: str) -> Path:
    """Path to a console entry-point script inside a venv, OS-correct."""
    if _IS_WINDOWS:
        return venv_dir / "Scripts" / f"{name}.exe"
    return venv_dir / "bin" / name


def _build_wheel(dist_dir: Path) -> Path:
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(dist_dir)],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    wheels = list(dist_dir.glob("*.whl"))
    assert len(wheels) == 1, f"expected exactly one wheel, got {wheels}"
    return wheels[0]


def _make_venv(venv_dir: Path) -> Path:
    venv.EnvBuilder(with_pip=True, clear=True).create(venv_dir)
    return _venv_python(venv_dir)


def _pip_install(python: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(python), "-m", "pip", "install", "--quiet", *args],
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture(scope="module")
def wheel(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the wheel once for all packaging tests in this module."""
    return _build_wheel(tmp_path_factory.mktemp("dist"))


@pytest.mark.packaging
def test_core_wheel_installs_and_renders_a_stable_figure(wheel: Path, tmp_path: Path) -> None:
    """The bare wheel (no extras) must import and render a stable figure --
    proving figures.json and the generator scripts are actually shipped.
    """
    python = _make_venv(tmp_path / "venv")
    _pip_install(python, str(wheel))

    smoke = tmp_path / "smoke.py"
    smoke.write_text(
        "from pathlib import Path\n"
        "from sprezzature_figures import make_figure, list_kinds\n"
        "from sprezzature_figures.make_figure import _demo_data_for\n"
        "from sprezzature_figures.catalog import resolve_kind\n"
        "stable = list_kinds(status='stable')\n"
        "assert stable, 'no stable kinds registered in the installed wheel'\n"
        "kind = stable[0]\n"
        "data = _demo_data_for(resolve_kind(kind))\n"
        "result = make_figure(kind, data, out='rendered.svg', title='packaging smoke test')\n"
        "assert result.exists() and result.stat().st_size > 0, f'{kind} produced no output'\n"
        "print(f'OK: rendered {kind}')\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [str(python), str(smoke)], cwd=tmp_path, check=True, capture_output=True, text=True
    )
    assert "OK: rendered" in result.stdout


@pytest.mark.packaging
def test_core_wheel_does_not_pull_in_studio_dependencies(wheel: Path, tmp_path: Path) -> None:
    """Installing the bare wheel must NOT make nicegui/pandas importable --
    the library must stay usable without the studio extra (plan requirement).
    """
    python = _make_venv(tmp_path / "venv")
    _pip_install(python, str(wheel))

    check = tmp_path / "check.py"
    check.write_text(
        "import importlib.util\n"
        "import sprezzature_figures  # must import with no studio deps\n"
        "for mod in ('nicegui', 'pandas'):\n"
        "    assert importlib.util.find_spec(mod) is None, f'{mod} should NOT be installed by the bare wheel'\n"
        "print('OK: core install is studio-independent')\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [str(python), str(check)], cwd=tmp_path, check=True, capture_output=True, text=True
    )
    assert "OK: core install is studio-independent" in result.stdout


@pytest.mark.packaging
def test_studio_extra_installs_and_console_scripts_resolve(wheel: Path, tmp_path: Path) -> None:
    """`pip install "<wheel>[studio]"` must pull nicegui + the studio deps,
    make every studio subpackage importable, and register all three console
    entry points -- the exact `pip install "sprezzature-figures[studio]";
    sprezzature-studio` flow the README documents.
    """
    venv_dir = tmp_path / "venv"
    python = _make_venv(venv_dir)
    # PEP 508 extras on a local wheel path: "<path>[studio]".
    _pip_install(python, f"{wheel}[studio]")

    check = tmp_path / "check.py"
    check.write_text(
        "import importlib\n"
        "for mod in (\n"
        "    'sprezzature_figures.studio.app',\n"
        "    'sprezzature_figures.studio.cli',\n"
        "    'sprezzature_figures.studio.ingest',\n"
        "    'sprezzature_figures.studio.assistant',\n"
        "    'sprezzature_figures.studio.ralph',\n"
        "    'sprezzature_figures.studio.export',\n"
        "    'nicegui',\n"
        "    'pandas',\n"
        "):\n"
        "    importlib.import_module(mod)\n"
        "print('OK: studio extra fully importable')\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [str(python), str(check)], cwd=tmp_path, check=True, capture_output=True, text=True
    )
    assert "OK: studio extra fully importable" in result.stdout

    # Console entry points exist and their --help runs without importing a
    # display/server (sprezzature-studio defers the nicegui import past argparse).
    for script_name in ("make-figure", "sprezzature-figures", "sprezzature-studio"):
        script = _venv_script(venv_dir, script_name)
        assert script.exists(), f"console script {script_name} not installed at {script}"
        help_result = subprocess.run(
            [str(script), "--help"], check=True, capture_output=True, text=True
        )
        assert (
            script_name.split("-")[-1] in help_result.stdout.lower()
            or "usage" in help_result.stdout.lower()
        )


@pytest.mark.packaging
def test_installed_fonts_match_what_the_module_offers(wheel: Path, tmp_path: Path) -> None:
    """The real install is the only place the font gap was ever visible.

    From a checkout, ``assets/fonts/`` holds every face whatever the wheel was
    built to contain, so font paths pass locally by construction. That
    asymmetry is what let the module offer Roboto Serif for a release in which
    the wheel dropped it, and the discovery happened downstream:
    ``sprezzature-maps``' CI, installing from the wheel, got a bare
    ``FileNotFoundError`` naming a filename and no reason.

    ``tests/test_the_package_serves_only_fonts_it_ships.py`` covers the same
    ground fast, by reading pyproject's globs. This one skips the reading and
    asks an actual install.
    """
    python = _make_venv(tmp_path / "venv")
    _pip_install(python, str(wheel))

    check = tmp_path / "check_fonts.py"
    check.write_text(
        "from sprezzature_figures import fonts\n"
        "\n"
        "# 1. Every offered face is really on disk, both files.\n"
        "missing = [k for k in fonts.OFFERED_FACES\n"
        "           if not (fonts.font_path(k).exists() and fonts.font_path(k, woff2=True).exists())]\n"
        "assert not missing, f'wheel is missing faces the module offers: {missing}'\n"
        "\n"
        "# 2. The serif specifically -- the face this whole guard exists for.\n"
        "for key in ('serif', 'serif_italic'):\n"
        "    assert key in fonts.OFFERED_FACES, f'{key} no longer offered'\n"
        "    assert fonts.font_path(key, woff2=True).exists(), f'{key} absent from the wheel'\n"
        "assert fonts.embedded_font_css(('serif',)), 'the serif cannot be embedded'\n"
        "\n"
        "# 3. A licence travels with every family the wheel carries.\n"
        "for licence in ('OFL-Roboto.txt', 'OFL-RobotoMono.txt', 'OFL-RobotoSerif.txt'):\n"
        "    assert (fonts.FONTS_DIR / licence).is_file(), f'{licence} not shipped'\n"
        "\n"
        "# 4. available_faces() sees the install, and it is the full set.\n"
        "assert set(fonts.available_faces()) == set(fonts.OFFERED_FACES), (\n"
        "    f'available={sorted(fonts.available_faces())} offered={sorted(fonts.OFFERED_FACES)}')\n"
        "\n"
        "# 5. The CSS Studio injects links nothing this install lacks.\n"
        "css = fonts.web_font_faces_css('/sprezzature-fonts')\n"
        "linked = [chunk.split(chr(39), 1)[0].rsplit('/', 1)[1]\n"
        '          for chunk in css.split("src:url(\'")[1:]]\n'
        "assert linked, 'studio would serve no fonts at all'\n"
        "absent = [n for n in linked if not (fonts.FONTS_DIR / n).is_file()]\n"
        "assert not absent, f'studio links fonts absent from the install: {absent}'\n"
        "\n"
        "print('OK: installed fonts and offered fonts agree')\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [str(python), str(check)], cwd=tmp_path, check=True, capture_output=True, text=True
    )
    assert "OK: installed fonts and offered fonts agree" in result.stdout
