"""
make_figure — unified entry point for all sprezzature-figures chart types.

Dispatches to the appropriate make_<kind>.py script by chart name, resolved
through the explicit figure registry (sprezzature_figures.catalog) rather
than by guessing a filename from the kind string. This is what lets
hyphenated kinds like "connected-scatter" resolve correctly: the registry
records the real module and callable name for every kind, decoupled from
each other.

Importable as a library and exposed as the ``make-figure`` CLI command.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
import warnings
from pathlib import Path
from typing import Any

from .catalog import FigureDefinition, ValidationIssue
from .catalog import get_figure_definition as _get_figure_definition
from .catalog import list_kinds as _list_kinds
from .catalog import resolve_kind as _resolve_kind

# Chart generators live one level up from this package. In the source tree
# that directory is ``scripts/``; once installed it ships (collision-free)
# as ``sprezzature_figures_scripts/``. Resolve whichever exists.
_pkg_parent = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = next(
    (_pkg_parent / name for name in ("scripts", "sprezzature_figures_scripts") if (_pkg_parent / name).is_dir()),
    _pkg_parent / "scripts",
)


def _legacy_filename_guess(kind: str) -> Path:
    """The dispatcher's old (buggy) hyphen->underscore filename guess.

    Kept only as a deprecated fallback for generator scripts that exist on
    disk but have not been added to the registry yet -- never used for
    anything the registry already knows about.
    """
    normalised = kind.lower().strip().replace("-", "_").replace(" ", "_")
    return _SCRIPTS_DIR / f"make_{normalised}.py"


def _load_module(path: Path, module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load script: {path}")
    mod = importlib.util.module_from_spec(spec)
    # Register in sys.modules so relative imports inside the script resolve
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _demo_data_for(canonical_kind: str) -> list[dict[str, Any]]:
    """Load DEMO_DATA from the registered module for an already-resolved kind."""
    definition = _get_figure_definition(canonical_kind)
    script_path = _SCRIPTS_DIR / Path(definition.module).name
    module_name = f"_sprezzature_figures_democonfig_{canonical_kind.replace('-', '_').replace(' ', '_')}"
    mod = _load_module(script_path, module_name)
    return getattr(mod, "DEMO_DATA", [])


def get_figure_definition(kind: str) -> FigureDefinition:
    """The registry entry for `kind` (module, callable, status, roles, ...)."""
    return _get_figure_definition(kind)


def list_kinds(status: str | None = None) -> list[str]:
    """
    Sorted list of registered chart kind names, optionally filtered by
    ``status`` ("stable", "experimental", "legacy", or "unavailable").

    Examples
    --------
    >>> kinds = list_kinds()
    >>> "treemap" in kinds
    True
    >>> "treemap" in list_kinds(status="stable")
    True
    """
    return _list_kinds(status=status)  # type: ignore[arg-type]


def validate_figure_input(kind: str, data: list[dict[str, Any]] | None, **kwargs: Any) -> list[ValidationIssue]:
    """
    Check `data` against the registered required data roles for `kind`.

    Only checks the roles the registry currently declares (most figures
    have not been role-annotated yet, so this is best-effort, not a
    guarantee of renderability). Column-type/cardinality checks belong to
    the richer validation engine in sprezzature_figures.core (not built
    here yet).
    """
    definition = _get_figure_definition(kind)
    issues: list[ValidationIssue] = []
    if not data:
        return issues
    first_row = data[0] if isinstance(data, list) else None
    keys = set(first_row) if isinstance(first_row, dict) else set()
    for role in definition.required_roles:
        if role.name not in keys:
            issues.append(
                ValidationIssue(
                    field=role.name,
                    message=f"required role {role.name!r} not found in data rows for kind={kind!r}",
                    severity="error",
                )
            )
    return issues


def make_figure(kind: str, data: list[dict[str, Any]], **kwargs: Any) -> Path:
    """
    Render a figure of the given kind and return the output path.

    Resolves ``kind`` (case-insensitively, hyphen/underscore/space
    interchangeable, aliases included) through the figure registry to find
    the backing module and callable, imports that module, validates `data`
    against any declared required roles, calls the generator, and confirms
    the output file was actually written.

    Parameters
    ----------
    kind : str
        Chart type name or alias, e.g. ``"treemap"``, ``"connected-scatter"``,
        ``"connected_scatter"``. See ``list_kinds()`` for the full catalogue.
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
        If no registered figure matches ``kind``, or `data` is missing a
        role the figure declares as required.
    AttributeError
        If the registered module does not actually expose the registered
        callable (a "legacy" figure whose contract is not yet satisfied).
    RuntimeError
        If the generator ran but produced no output file.

    Examples
    --------
    >>> from sprezzature_figures import make_figure
    >>> data = [{"parent": "A", "name": "A1", "value": 10}]
    >>> path = make_figure("treemap", data, out="/tmp/treemap.svg")
    >>> path.exists()
    True
    """
    canonical = _resolve_kind(kind)
    if canonical is None:
        legacy_path = _legacy_filename_guess(kind)
        if legacy_path.exists():
            warnings.warn(
                f"kind={kind!r} is not in the figure registry; falling back to the "
                f"deprecated filename-guessing path ({legacy_path.name}). Add it to "
                "sprezzature_figures/catalog/figures.json. This fallback must never "
                "be relied on by the Studio GUI.",
                DeprecationWarning,
                stacklevel=2,
            )
            module_name = f"_sprezzature_figures_legacy_{kind.replace('-', '_').replace(' ', '_')}"
            mod = _load_module(legacy_path, module_name)
            fn_name = f"make_{kind.lower().strip().replace('-', '_').replace(' ', '_')}"
            fn = getattr(mod, fn_name, None)
            if fn is None:
                raise AttributeError(f"Script {legacy_path.name} has no function named {fn_name!r}.")
            return Path(fn(data, **kwargs))
        available = _list_kinds()
        raise ValueError(f"No script for kind={kind!r}. Available ({len(available)}): {', '.join(available)}")

    definition = _get_figure_definition(canonical)
    if definition.status != "stable":
        warnings.warn(
            f"kind={canonical!r} is registered as status={definition.status!r}, not 'stable'. "
            f"{'; '.join(definition.warnings) if definition.warnings else 'Its output has not been render-verified.'}",
            UserWarning,
            stacklevel=2,
        )

    issues = validate_figure_input(canonical, data, **kwargs)
    errors = [i for i in issues if i.severity == "error"]
    if errors:
        raise ValueError(
            f"Invalid data for kind={canonical!r}: " + "; ".join(f"{i.field}: {i.message}" for i in errors)
        )

    script_path = _SCRIPTS_DIR / Path(definition.module).name
    if not script_path.exists():
        raise FileNotFoundError(f"Registered module {definition.module!r} not found at {script_path}")

    module_name = f"_sprezzature_figures_make_{canonical.replace('-', '_').replace(' ', '_')}"
    mod = _load_module(script_path, module_name)

    fn = getattr(mod, definition.callable_name, None)
    if fn is None:
        raise AttributeError(
            f"Registered module {script_path.name} has no function named "
            f"{definition.callable_name!r} (kind={canonical!r}, status={definition.status!r})."
        )

    result = fn(data, **kwargs)
    result_path = Path(result).resolve()
    if not result_path.exists():
        raise RuntimeError(f"make_figure({canonical!r}) did not produce an output file at {result_path}")
    return result_path


def main() -> None:
    """
    CLI entry point for the ``make-figure`` command.

    Usage::

        make-figure treemap --out output.svg --title "My chart"
        make-figure --list
    """
    parser = argparse.ArgumentParser(
        prog="make-figure",
        description="Render a sprezzature-figures chart from DEMO_DATA.",
    )
    parser.add_argument(
        "kind",
        nargs="?",
        help="Chart type, e.g. treemap, funnel, waterfall. Use --list to see all.",
    )
    parser.add_argument("--out", default=None, help="Output file path.")
    parser.add_argument("--title", default="", help="Chart title.")
    parser.add_argument(
        "--list", action="store_true", help="Print all available chart kinds and exit."
    )
    parser.add_argument(
        "--status",
        default=None,
        choices=["stable", "experimental", "legacy", "unavailable"],
        help="With --list, only show kinds with this status.",
    )

    args = parser.parse_args()

    if args.list:
        kinds = list_kinds(status=args.status)
        print(f"{len(kinds)} chart types available:")
        for k in kinds:
            print(f"  {k}")
        return

    if not args.kind:
        parser.print_help()
        sys.exit(1)

    canonical = _resolve_kind(args.kind)
    if canonical is None:
        print(f"Error: no script for kind={args.kind!r}.", file=sys.stderr)
        print("Run `make-figure --list` to see available kinds.", file=sys.stderr)
        sys.exit(1)

    demo_data = _demo_data_for(canonical)
    kwargs: dict[str, Any] = {"title": args.title}
    if args.out:
        kwargs["out"] = args.out

    result = make_figure(args.kind, demo_data, **kwargs)
    print(result)
