"""
make_figure — unified entry point for all sprezzature-figures chart types.

Dispatches to the appropriate make_<kind>.py script by chart name.
Importable as a library and exposed as the ``make-figure`` CLI command.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Any

# Scripts directory: one level up from this package, under scripts/
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def make_figure(kind: str, data: list[dict[str, Any]], **kwargs: Any) -> Path:
    """
    Render a figure of the given kind and return the output path.

    Loads the corresponding ``make_<kind>.py`` script from the scripts/
    directory and calls its ``make_<kind>`` function. The script is
    imported dynamically so that each chart type remains self-contained.

    Parameters
    ----------
    kind : str
        Chart type name, e.g. ``"bar"``, ``"scatter"``, ``"treemap"``.
        Case-insensitive; hyphens and spaces are normalised to underscores.
        Must match a ``make_<kind>.py`` script in the scripts/ directory.
    data : list[dict[str, Any]]
        Input rows forwarded to the underlying make function. Each script
        documents its expected keys (see FIGURES.md for the full catalogue).
    **kwargs
        Forwarded to the underlying make function. Common options:
        ``out`` (output path), ``title`` (chart title), ``width``, ``height``.

    Returns
    -------
    Path
        Absolute path to the rendered output file.

    Raises
    ------
    ValueError
        If no ``make_<kind>.py`` script exists for the requested kind.

    Examples
    --------
    >>> from sprezzature_figures import make_figure
    >>> path = make_figure("bar", [{"label": "A", "value": 10}], out="/tmp/bar.png")
    >>> path.exists()
    True
    """
    # Normalise: lowercase, spaces and hyphens become underscores
    normalised = kind.lower().strip().replace("-", "_").replace(" ", "_")

    candidate = _SCRIPTS_DIR / f"make_{normalised}.py"
    if not candidate.exists():
        # Build a sorted list of available kinds for a helpful error message
        available = sorted(
            p.stem[len("make_"):]
            for p in _SCRIPTS_DIR.glob("make_*.py")
            # Exclude the dispatcher itself and make_figure.py if present
            if p.stem != "make_figure"
        )
        raise ValueError(
            f"No script for kind={kind!r}. "
            f"Available ({len(available)}): {', '.join(available)}"
        )

    # Import the script as a module; use a unique name to avoid cache collisions
    module_name = f"_sprezzature_figures_make_{normalised}"
    spec = importlib.util.spec_from_file_location(module_name, candidate)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load script: {candidate}")
    mod = importlib.util.module_from_spec(spec)
    # Register in sys.modules so relative imports inside the script resolve
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]

    # The make function must be named make_<normalised>
    fn_name = f"make_{normalised}"
    fn = getattr(mod, fn_name, None)
    if fn is None:
        raise AttributeError(
            f"Script {candidate.name} has no function named {fn_name!r}."
        )

    return Path(fn(data, **kwargs))


def list_kinds() -> list[str]:
    """
    Return a sorted list of all available chart kind names.

    Parameters
    ----------
    (none)

    Returns
    -------
    list[str]
        Sorted kind names (the part after ``make_`` in each script filename).

    Examples
    --------
    >>> kinds = list_kinds()
    >>> "bar" in kinds
    True
    """
    return sorted(
        p.stem[len("make_"):]
        for p in _SCRIPTS_DIR.glob("make_*.py")
        if p.stem != "make_figure"
    )


def main() -> None:
    """
    CLI entry point for the ``make-figure`` command.

    Usage::

        make-figure bar --out output.png --title "My chart"
        make-figure --list
    """
    parser = argparse.ArgumentParser(
        prog="make-figure",
        description="Render a sprezzature-figures chart from DEMO_DATA.",
    )
    parser.add_argument(
        "kind",
        nargs="?",
        help="Chart type, e.g. bar, scatter, treemap. Use --list to see all.",
    )
    parser.add_argument("--out", default=None, help="Output file path.")
    parser.add_argument("--title", default="", help="Chart title.")
    parser.add_argument(
        "--list", action="store_true", help="Print all available chart kinds and exit."
    )

    args = parser.parse_args()

    if args.list:
        kinds = list_kinds()
        print(f"{len(kinds)} chart types available:")
        for k in kinds:
            print(f"  {k}")
        return

    if not args.kind:
        parser.print_help()
        sys.exit(1)

    # Load DEMO_DATA from the target script and render
    normalised = args.kind.lower().strip().replace("-", "_").replace(" ", "_")
    candidate = _SCRIPTS_DIR / f"make_{normalised}.py"
    if not candidate.exists():
        print(f"Error: no script for kind={args.kind!r}.", file=sys.stderr)
        print("Run `make-figure --list` to see available kinds.", file=sys.stderr)
        sys.exit(1)

    module_name = f"_sprezzature_figures_cli_{normalised}"
    spec = importlib.util.spec_from_file_location(module_name, candidate)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]

    demo_data = getattr(mod, "DEMO_DATA", [])
    kwargs: dict[str, Any] = {"title": args.title}
    if args.out:
        kwargs["out"] = args.out

    result = make_figure(args.kind, demo_data, **kwargs)
    print(result)
