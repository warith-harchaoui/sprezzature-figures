"""`sprezzature-figures --help` must not load the catalogue.

Every console script imports the package first. When the package's
``__init__`` and the CLI loaded the catalogue eagerly (pydantic models for
168 kinds, the option models, redraw), ``--help`` took 0.8 s before printing
a line. The names now load on first use; this keeps it that way.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

import subprocess
import sys

_PROBE = (
    "import sys, sprezzature_figures.cli; "
    "heavy = [m for m in ('pydantic', 'sprezzature_figures.catalog', "
    "'sprezzature_figures.make_figure', 'sprezzature_figures.redraw') if m in sys.modules]; "
    "print(','.join(heavy))"
)


def test_importing_the_cli_loads_no_catalogue() -> None:
    out = subprocess.run(
        [sys.executable, "-c", _PROBE], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert out == "", f"the CLI loads at import: {out}"


def test_the_public_function_survives_its_submodule_loading() -> None:
    probe = (
        "import sprezzature_figures as f, sprezzature_figures.make_figure as m; "
        "assert callable(f.make_figure), type(f.make_figure); print('ok')"
    )
    out = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert out == "ok"
