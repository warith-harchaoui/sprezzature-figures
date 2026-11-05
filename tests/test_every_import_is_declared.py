"""Every third-party module this repository imports is declared as a dependency.

The defect this guards. ``tools/build_landscape.py`` opened with a bare
``import standpoint as sp`` at module scope, and ``standpoint`` appeared in no
``pyproject.toml`` table and in neither requirements file. Three separate
readers all failed to notice:

* **pip** never had to resolve it. Measured in a fresh venv holding only the
  base dependencies: no installed distribution declares ``standpoint``, so it
  did not arrive by transitivity either. It was on the author's machine
  because the author had cloned it next door.
* **mypy** reads the module as ``Any``. ``mypy.ini`` carries
  ``ignore_missing_imports = True`` on purpose -- the optional backends are
  not installed in the light CI lane -- and that setting cannot tell a
  deliberately-optional import from an undeclared one. CI runs ``mypy tools``
  and was green.
* **CI** never runs the script. It is a one-off asset regenerator, so no job
  imports the file.

Which leaves exactly one reader: a contributor on a clean clone, who runs the
documented ``pip install -e ".[dev]"`` and then gets a bare
``ModuleNotFoundError``. ``sprezzature-video``'s manifest states the class
outright -- a dependency you use directly but inherit transitively is exactly
what a clean venv turns into an ImportError nobody saw coming.

So this walks every ``import`` in the three directories of hand-written code
and asserts each third-party top-level name resolves to something
``pyproject.toml`` declares, in any table. It found ``standpoint`` and three
more of the same shape on its first run: ``explain_model.py`` imports
``timeshap``, ``lime`` and ``joblib``, all three declared in
``scripts/requirements-explain.txt`` and none of them in the ``explain``
extra, so ``pip install "sprezzature-figures"`` installed SHAP and
Shapash and left the TimeSHAP and LIME paths to die on import.

What it does not catch, measured on the same run: the converse. Five
distributions are declared and imported nowhere in these 279 files --
``scipy`` (in the base ``dependencies``, while nine generators say "no scipy"
in their own docstrings), ``shapely`` and ``pyproj`` (declared for
``make_situation_map.py``, which is not in this repository, and dropped on
2026-11-05), ``econml`` and ``pyyaml``. Asserting that direction would be red today and is a decision
about the published dependency surface, not a defect to fix in a test file.

It is also blind to a dependency used by a *name* that differs from its
distribution's and is not in :data:`_IMPORT_TO_DISTRIBUTION` below -- the
mapping has to be written down, and an unwritten one reads as undeclared, so
the failure is loud rather than silent.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# `tomllib` is stdlib only from 3.11 and this package supports 3.10, where a
# bare import fails collection of the whole file. `tomli` is the same parser
# under its pre-stdlib name, declared in the `dev` extra for 3.10 alone.
try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 only
    import tomli as tomllib

REPO_ROOT = Path(__file__).resolve().parent.parent

#: The directories of hand-written code, the same three the linter and the
#: type gate are pointed at. `tests/` is deliberately out: a test may import
#: something only the developer lane has, and `dev` is where that is declared.
_CODE_DIRS = ("sprezzature_figures", "scripts", "tools")

#: Import names that differ from the distribution that provides them. Each
#: entry is a fact about PyPI, not a preference, and leaving one out makes the
#: test fail rather than pass -- the safe direction.
_IMPORT_TO_DISTRIBUTION = {
    "PIL": "pillow",
    "sklearn": "scikit-learn",
    "yaml": "pyyaml",
    "cv2": "opencv-python",
}

#: Modules reached off a runtime ``sys.path``, from a sibling repository
#: rather than from a distribution, each behind its own existence check so the
#: absence is handled instead of raised.
#:
#: ``accessibility_levels`` is ``sprezzature-colors/scripts/accessibility_levels.py``.
#: ``scripts/_style.py`` tests ``(scripts / "accessibility_levels.py").is_file()``
#: before importing it and falls back to the unmodified palette when it is not
#: there, which is the shape that makes an undeclared import legitimate: the
#: code already knows it might be missing.
_SIBLING_REPO_MODULES = {"accessibility_levels"}


def _normalise(name: str) -> str:
    """PEP 503 normalisation: lowercase, and any run of ``-_.`` to a hyphen."""
    out: list[str] = []
    for char in name.lower():
        if char in "-_.":
            if out and out[-1] == "-":
                continue
            out.append("-")
        else:
            out.append(char)
    return "".join(out)


def _declared_distributions() -> set[str]:
    """Every distribution name ``pyproject.toml`` declares, from every table."""
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        project = tomllib.load(handle).get("project", {})
    requirements = list(project.get("dependencies", []))
    for extra in project.get("optional-dependencies", {}).values():
        requirements.extend(extra)
    names = set()
    for requirement in requirements:
        # "uvicorn[standard]>=0.30" -> "uvicorn"; "tomli; python_version < …" -> "tomli"
        head = requirement.split(";")[0].strip()
        for separator in ("[", "<", ">", "=", "!", "~", " "):
            head = head.split(separator)[0]
        if head:
            names.add(_normalise(head))
    return names


def _local_module_names() -> set[str]:
    """Names that resolve inside this repository rather than to a distribution.

    The generators add their own directory to ``sys.path`` and import
    siblings by bare name (``from _style import INK``), so every file stem in
    the scanned directories is a local name, as is each directory itself and
    the two aliases the wheel publishes them under.
    """
    names = {
        "sprezzature_figures",
        "sprezzature_figures_scripts",
        "sprezzature_figures_fonts",
        "tests",
    }
    for directory in _CODE_DIRS:
        names.add(directory)
        for path in (REPO_ROOT / directory).rglob("*.py"):
            names.add(path.stem)
    return names


def _third_party_imports() -> dict[str, list[str]]:
    """Map every third-party top-level import name to the files importing it."""
    local = _local_module_names()
    found: dict[str, list[str]] = {}
    for directory in _CODE_DIRS:
        for path in sorted((REPO_ROOT / directory).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    roots = [alias.name.split(".")[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    # A relative import resolves inside the package by definition.
                    roots = [] if node.level or not node.module else [node.module.split(".")[0]]
                else:
                    continue
                for root in roots:
                    if root in sys.stdlib_module_names or root in local:
                        continue
                    found.setdefault(root, []).append(str(path.relative_to(REPO_ROOT)))
    return found


def test_the_scan_finds_the_imports_it_is_supposed_to_check() -> None:
    """The walk reaches real code, so a green result is not an empty one.

    A scanner that silently matches nothing is the failure mode this whole
    file exists to prevent in the dependency table; it would be absurd for
    the guard to have it too. The floors are low enough to survive ordinary
    refactoring and high enough that a broken walk cannot pass.
    """
    scanned = sum(1 for d in _CODE_DIRS for _ in (REPO_ROOT / d).rglob("*.py"))
    assert scanned > 200, f"only {scanned} Python files found in {_CODE_DIRS}"
    imports = _third_party_imports()
    assert len(imports) > 15, f"only {len(imports)} third-party imports found: {sorted(imports)}"
    assert "numpy" in imports, "numpy is imported by dozens of generators; the walk missed it"
    assert _declared_distributions() >= {"numpy", "pillow", "click"}, (
        "the pyproject table did not parse into the base dependencies"
    )


def test_no_module_is_imported_without_being_declared() -> None:
    """Every third-party import maps to a distribution ``pyproject.toml`` asks for."""
    declared = _declared_distributions()
    undeclared: list[str] = []
    for name, files in sorted(_third_party_imports().items()):
        if name in _SIBLING_REPO_MODULES:
            continue
        distribution = _IMPORT_TO_DISTRIBUTION.get(name, _normalise(name))
        if distribution not in declared:
            where = ", ".join(sorted(set(files))[:3])
            undeclared.append(f"{name} (as {distribution!r}) imported by {where}")
    assert not undeclared, (
        "imported but declared in no pyproject.toml table, so a clean venv raises "
        "ModuleNotFoundError:\n  " + "\n  ".join(undeclared)
    )
