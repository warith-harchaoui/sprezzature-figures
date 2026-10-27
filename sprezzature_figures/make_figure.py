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
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

import argparse
import importlib.util
import inspect
import sys
import warnings
from pathlib import Path
from typing import Any

from .catalog import FigureDefinition, ValidationIssue
from .catalog import get_figure_definition as _get_figure_definition
from .catalog import list_kinds as _list_kinds
from .catalog import resolve_kind as _resolve_kind
from .frames import as_rows
from .notebook import FigurePath, as_figure_path


def _resolve_scripts_dir(pkg_parent: Path) -> Path:
    """Find the chart-generator directory relative to *pkg_parent*.

    In the source tree that directory is ``scripts/``; once installed it
    ships (collision-free) as ``sprezzature_figures_scripts/``. Checks the
    dedicated installed name FIRST: a bare ``scripts/`` at the root of
    site-packages is a generic name another, unrelated package can also
    claim, and if that collision wins here every figure render fails
    silently. The dedicated name can only ever refer to us, so it is the
    safe first guess; the generic ``scripts/`` is only used as a fallback
    for the source tree, where the dedicated name never exists.
    """
    return next(
        (
            pkg_parent / name
            for name in ("sprezzature_figures_scripts", "scripts")
            if (pkg_parent / name).is_dir()
        ),
        pkg_parent / "scripts",
    )


# Chart generators live one level up from this package.
_pkg_parent = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _resolve_scripts_dir(_pkg_parent)


def _legacy_filename_guess(kind: str) -> Path:
    """The dispatcher's old (buggy) hyphen->underscore filename guess.

    Kept only as a deprecated fallback for generator scripts that exist on
    disk but have not been added to the registry yet -- never used for
    anything the registry already knows about.
    """
    normalised = kind.lower().strip().replace("-", "_").replace(" ", "_")
    return _SCRIPTS_DIR / f"make_{normalised}.py"


def _load_module(path: Path, module_name: str) -> Any:
    # Generators import their sibling helpers by bare name (``from _render
    # import ...``, ``from _interactive import ...``). Most self-insert their
    # own directory onto sys.path first, but a handful of legacy ones forgot to,
    # so they only imported when another generator had already put scripts/ on
    # the path. Guarantee it here, at the one place every generator is loaded,
    # so a generator renders the same whether it runs first or tenth.
    scripts_dir = str(path.resolve().parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
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
    module_name = (
        f"_sprezzature_figures_democonfig_{canonical_kind.replace('-', '_').replace(' ', '_')}"
    )
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


def _filter_kwargs_for(fn: Any, kwargs: dict[str, Any]) -> dict[str, Any]:
    """Drop kwargs the generator's signature does not accept.

    Chrome-text kwargs (``subtitle``, ``x_label``, ...) are shared
    vocabulary but not a universal contract: a couple of generators take
    none of them, and axis labels only exist on axis-bearing charts.
    """
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return kwargs
    if any(p.kind is p.VAR_KEYWORD for p in params.values()):
        return kwargs
    return {k: v for k, v in kwargs.items() if k in params}


def describe_required_roles(kind: str) -> str:
    """One-line, human-readable list of a kind's required data roles.

    E.g. for ``bar``: ``"region (Category, categorical), value (Value,
    numeric)"``. Empty string when the kind is unknown or declares no
    roles. Used by the CLI error hints so a user who guessed the wrong
    ``--map`` key sees every accepted role at once.
    """
    canonical = _resolve_kind(kind)
    if canonical is None:
        return ""
    definition = _get_figure_definition(canonical)
    return ", ".join(
        f"{r.name} ({r.label}, {'/'.join(r.accepted_types) or 'any'})"
        for r in definition.required_roles
    )


def resolve_role_mapping(kind: str, mapping: dict[str, str]) -> dict[str, str]:
    """Translate ``--map`` keys given as role *labels* into role names.

    Role names are historical (``bar`` calls its category ``region``,
    after its demo data); the label (``Category``) is the discoverable
    half. Accept either, case-insensitively: a key matching exactly one
    role's label is rewritten to that role's name. Keys already naming a
    role, or matching no label (or an ambiguous one), pass through
    untouched.
    """
    canonical = _resolve_kind(kind)
    if canonical is None or not mapping:
        return mapping
    definition = _get_figure_definition(canonical)
    names = {r.name for r in definition.required_roles + definition.optional_roles}
    by_label: dict[str, list[str]] = {}
    for r in definition.required_roles + definition.optional_roles:
        by_label.setdefault(r.label.lower(), []).append(r.name)
    resolved: dict[str, str] = {}
    for key, column in mapping.items():
        if key not in names:
            candidates = by_label.get(key.lower(), [])
            if len(candidates) == 1:
                key = candidates[0]
        resolved[key] = column
    return resolved


#: Noms de rôle du catalogue, en français. Les rôles sont un vocabulaire
#: FERMÉ (``region``, ``value``, ``month``...), écrit en anglais dans la
#: définition des figures : servis tels quels comme titres d'axes, ils
#: mettaient de l'anglais sous une figure rendue en français. La table ne
#: traduit que ce vocabulaire-là, jamais les données de l'appelant.
_ROLE_LABELS_FR = {
    "region": "Région",
    "value": "Valeur",
    "month": "Mois",
    "day": "Jour",
    "week": "Semaine",
    "year": "Année",
    "quarter": "Trimestre",
    "category": "Catégorie",
    "count": "Effectif",
    "share": "Part",
    "score": "Score",
    "name": "Nom",
    "label": "Libellé",
    "group": "Groupe",
    "stage": "Étape",
    "date": "Date",
    "time": "Temps",
    "x": "x",
    "y": "y",
    "mean": "Moyenne",
    "diff": "Écart",
    "std": "Écart-type",
    "close": "Clôture",
    "hours": "Heures",
    "parent": "Parent",
    "source": "Source",
    "target": "Cible",
    "price": "Prix",
    "quantity": "Quantité",
    "rate": "Taux",
    "total": "Total",
}


def user_data_chrome_kwargs(
    kind: str, mapping: dict[str, str] | None = None, language: str = "en"
) -> dict[str, Any]:
    """Chrome-text overrides for rendering *user* data instead of DEMO_DATA.

    Generators fall back to demo captions when chrome kwargs are omitted
    (e.g. make_bar's "Quarterly figures" subtitle and "Region" axis title);
    that chrome belongs to the built-in demo data only. Suppresses the demo
    subtitle, and titles the axes after the user's own columns when the
    role binding is unambiguous. ``mapping`` is the ``{role: column}`` dict
    from ``--map`` (columns already carrying a role name need no entry).
    """
    mapping = mapping or {}
    # The title is demo chrome too, and the most quoted line on the figure:
    # several generators default it to a sentence about their own demo rows
    # ("Organic search fills the funnel..."). Suppressed here for the same
    # reason as the subtitle -- over somebody else's numbers it is simply
    # false. An explicit --title, or a `title=` from a library caller, still
    # wins: this only fills what the caller left unsaid.
    kwargs: dict[str, Any] = {"title": "", "subtitle": ""}
    canonical = _resolve_kind(kind)
    if canonical is None:
        return kwargs
    definition = _get_figure_definition(canonical)
    category_roles = [r for r in definition.required_roles if "numeric" not in r.accepted_types]
    numeric_roles = [r for r in definition.required_roles if "numeric" in r.accepted_types]

    def libelle(nom: str) -> str:
        propose = mapping.get(nom, nom)
        if propose != nom:  # l'appelant a nommé sa colonne : on n'y touche pas
            return propose
        if language.lower().startswith("fr"):
            return _ROLE_LABELS_FR.get(nom, nom)
        return nom

    if len(category_roles) == 1:
        kwargs["x_label"] = libelle(category_roles[0].name)
    if len(numeric_roles) == 1:
        kwargs["y_label"] = libelle(numeric_roles[0].name)
    return kwargs


def _without_demo_chrome(
    kind: str, data: list[dict[str, Any]] | None, kwargs: dict[str, Any]
) -> dict[str, Any]:
    """Fill the chrome kwargs a caller left empty, so demo chrome cannot show.

    Every generator carries captions written for ITS OWN demo data: a
    subtitle ("Quarterly figures"), axis titles ("Region", "Value"). They are
    the right thing to print when the generator renders its demo. Printed
    over somebody else's data they are simply false, and false chrome is
    worse than none: it affirms.

    The CLI has always suppressed them through
    :func:`user_data_chrome_kwargs`. Library callers had to know to do the
    same, and one that did not shipped a revenue chart subtitled "Quarterly
    figures". The knowledge belongs here, once, rather than in every caller.

    Only kwargs the caller did NOT set are filled: an explicit subtitle or
    axis title always wins, including an explicitly empty one.
    """
    if not data:
        # No caller data means the generator renders its own demo, where the
        # demo chrome is exactly right.
        return kwargs
    rempli = dict(kwargs)
    langue = str(kwargs.get("language") or "en")
    for cle, valeur in user_data_chrome_kwargs(kind, language=langue).items():
        rempli.setdefault(cle, valeur)
    return rempli


def validate_figure_input(
    kind: str, data: Any = None, **kwargs: Any
) -> list[ValidationIssue]:
    """
    Check `data` against the registered required data roles for `kind`.

    Only checks the roles the registry currently declares (most figures
    have not been role-annotated yet, so this is best-effort, not a
    guarantee of renderability). Column-type/cardinality checks belong to
    the richer validation engine in sprezzature_figures.core (not built
    here yet).

    Parameters
    ----------
    kind : str
        Chart type name or alias.
    data : Any, optional
        The rows, in whatever the caller is holding -- the same shapes
        :func:`make_figure` takes, normalised the same way, so asking
        "would this render?" never needs a different conversion from
        rendering it.
    **kwargs
        Accepted and ignored; present so a caller can forward the same
        keyword arguments to both functions.

    Returns
    -------
    list of ValidationIssue
        One per required role the rows do not carry; empty when nothing
        is missing, which includes the case of no rows at all (the
        figure then draws its own).
    """
    definition = _get_figure_definition(kind)
    issues: list[ValidationIssue] = []
    rows = as_rows(data)
    if not rows:
        return issues
    first_row = rows[0]
    keys = set(first_row) if isinstance(first_row, dict) else set()
    for role in definition.required_roles:
        if role.name not in keys:
            issues.append(
                ValidationIssue(
                    field=role.name,
                    message=(
                        f"required role {role.name!r} ({role.label}) not found "
                        f"in data rows for kind={kind!r}"
                    ),
                    severity="error",
                )
            )
            continue
        if role.tolerates_gaps:
            continue
        # A gap in a required column is refused here rather than inside a
        # generator, where it surfaces as "float() argument must be a
        # string or a real number". The row is named, because finding the
        # one empty cell in fifty thousand is the actual work.
        empty = [n for n, row in enumerate(rows) if row.get(role.name) is None]
        if empty:
            where = ", ".join(str(n) for n in empty[:5])
            more = f" and {len(empty) - 5} more" if len(empty) > 5 else ""
            issues.append(
                ValidationIssue(
                    field=role.name,
                    message=(
                        f"{role.name!r} ({role.label}) is empty in "
                        f"{len(empty)} of {len(rows)} rows (row {where}{more}). "
                        "A figure cannot draw a value that is not there: drop "
                        "those rows, fill them, or reach for 'missing-matrix', "
                        "which is the figure whose subject is where the gaps are."
                    ),
                    severity="error",
                )
            )
    return issues


def _without_embedded_fonts(svg: str) -> str:
    """Return *svg* with the embedded ``@font-face`` block removed, byte for byte.

    Every figure carries its own typeface so it renders identically anywhere, which is
    right for a figure that travels alone. It is the wrong trade for a figure *embedded in
    a page that already serves those faces*: six figures inlined into one report is the
    same 430 kB of base64 Roboto repeated six times, 2.5 MB of a document whose text is
    already in the right font.

    The block is rebuilt from :mod:`.fonts` and removed by equality, never matched by
    pattern, so a figure's own ``<defs>`` or ``<style>`` cannot be swept up by accident.
    """
    from .fonts import DEFAULT_SVG_FACES, svg_faces_for_theme, svg_font_defs

    candidates = {DEFAULT_SVG_FACES}
    for theme in ("corporate", "academic"):
        faces = svg_faces_for_theme(theme)
        if faces:
            candidates.add(tuple(faces))
    out = svg
    for faces in candidates:
        out = out.replace(svg_font_defs(faces), "", 1)
    return out


def make_figure(kind: str, data: Any = None, **kwargs: Any) -> FigurePath:
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
    data : Any, optional
        The rows to draw, in whatever the caller is holding: a list of
        dicts, a pandas / polars / Arrow frame, or a dict of equal-length
        columns. :func:`sprezzature_figures.frames.as_rows` normalises
        it, spells every absent cell ``None`` and writes dates in ISO
        form; nothing is imported to do it, so a caller with none of
        those libraries installed pays nothing. Each script documents
        the column names it expects (see FIGURES.md for the full
        catalogue). ``None`` -- the default -- renders that figure's own
        demo rows *with its own chrome*: the title and subtitle its author
        wrote for them. Passing the demo rows explicitly is not the same
        thing, and gets the chrome suppressed like any other caller data,
        because nothing downstream can tell them apart.
    **kwargs
        Forwarded to the underlying make function. Common options:
        ``out`` (output path), ``title`` (chart title), ``width``, ``height``.
        ``dark`` (bool): render for a DARK canvas -- transparent background and
        lightened chrome so the figure reads on a dark surface. Handled by
        make_figure itself (SVG output), not passed to the generator; see
        :mod:`sprezzature_figures.darkmode`.
        ``embed_fonts`` (bool, default True): carry the house typeface inside the
        SVG. Pass False when the figure is inlined into a page that already serves
        those faces, so the same 430 kB of base64 is not repeated once per figure.
        Handled by make_figure itself (SVG output), not passed to the generator.

    Returns
    -------
    FigurePath
        Absolute path to the rendered output file. A ``Path`` in every
        respect -- ``isinstance(result, Path)`` holds, and so does every
        method -- which additionally draws itself when a notebook asks
        it to, so a cell ending in this call shows the figure rather
        than printing where it went.

    Raises
    ------
    TypeError
        If `data` is a shape with no column names in it -- a list of
        lists, a bare array.
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
    >>> path = make_figure("treemap", data, out="treemap.svg")
    >>> path.exists()
    True
    """
    # ``dark`` is a make_figure-level option, not a per-generator argument: pop
    # it before the kwargs ever reach a figure script (which would reject it),
    # and apply it to the rendered SVG at the end (see :mod:`.darkmode`).
    dark = bool(kwargs.pop("dark", False))
    # ``embed_fonts`` is a make_figure-level option for the same reason ``dark`` is: it
    # describes the destination, not the chart. False suits a figure inlined into a page
    # that already serves the house faces; see :func:`_without_embedded_fonts`.
    embed_fonts = bool(kwargs.pop("embed_fonts", True))
    # One normalisation, at the one door every caller comes through: all
    # 162 generators gain DataFrame support here rather than each one
    # growing its own conversion.
    data = as_rows(data)
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
                raise AttributeError(
                    f"Script {legacy_path.name} has no function named {fn_name!r}."
                )
            legacy_out = Path(fn(data, **_filter_kwargs_for(fn, kwargs)))
            if dark and legacy_out.suffix.lower() == ".svg":
                from .darkmode import to_dark

                legacy_out.write_text(
                    to_dark(legacy_out.read_text(encoding="utf-8")), encoding="utf-8"
                )
            return as_figure_path(legacy_out)
        available = _list_kinds()
        raise ValueError(
            f"No script for kind={kind!r}. Available ({len(available)}): {', '.join(available)}"
        )

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
            f"Invalid data for kind={canonical!r}: "
            + "; ".join(f"{i.field}: {i.message}" for i in errors)
        )

    script_path = _SCRIPTS_DIR / Path(definition.module).name
    if not script_path.exists():
        raise FileNotFoundError(
            f"Registered module {definition.module!r} not found at {script_path}"
        )

    module_name = f"_sprezzature_figures_make_{canonical.replace('-', '_').replace(' ', '_')}"
    mod = _load_module(script_path, module_name)

    fn = getattr(mod, definition.callable_name, None)
    if fn is None:
        raise AttributeError(
            f"Registered module {script_path.name} has no function named "
            f"{definition.callable_name!r} (kind={canonical!r}, status={definition.status!r})."
        )

    result = fn(data, **_filter_kwargs_for(fn, _without_demo_chrome(canonical, data, kwargs)))
    result_path = Path(result).resolve()
    if not result_path.exists():
        raise RuntimeError(
            f"make_figure({canonical!r}) did not produce an output file at {result_path}"
        )
    if result_path.suffix.lower() == ".svg" and (dark or not embed_fonts):
        rendered = result_path.read_text(encoding="utf-8")
        if dark:
            from .darkmode import to_dark

            rendered = to_dark(rendered)
        if not embed_fonts:
            rendered = _without_embedded_fonts(rendered)
        result_path.write_text(rendered, encoding="utf-8")
    return as_figure_path(result_path)


def _kind_option_flags(parser: argparse.ArgumentParser, kind: str, options: dict[str, Any]) -> None:
    """Give `kind`'s own keywords a flag each, in their own ``--help`` section.

    The generators already work this way one level down: ``render_cli`` in
    ``scripts/_render.py`` grows a flag whenever a ``build_svg`` grows a
    parameter. This does the same for ``make-figure``, from the frozen
    catalogue rather than from a live signature, so ``make-figure sankey
    --help`` costs a JSON read and lists ``--volume-unit`` and
    ``--stage-names`` -- which existed, and which no command line could
    reach.

    ``title`` is skipped: it is a top-level flag already, shared by every
    kind. Nothing is coerced here; values arrive as text and go through
    :func:`~sprezzature_figures.options.coerce_option` with the ``--set``
    ones, so both spellings fail the same way on a bad value.
    """
    if not options:
        return
    group = parser.add_argument_group(
        f"{kind} options",
        f"Keywords {kind} accepts beyond its data. "
        f"`make-figure {kind} --describe` prints them with their defaults.",
    )
    for option in options.values():
        if not option.cli_flag or option.name == "title":
            continue
        shown = "" if option.default is None else f" (default: {option.default!r})"
        help_text = (option.description or f"{option.name} option.") + shown
        if option.type == "bool":
            group.add_argument(
                option.cli_flag,
                dest=f"opt_{option.name}",
                action=argparse.BooleanOptionalAction,
                default=None,
                help=help_text,
            )
        elif option.choices:
            # No metavar here on purpose: argparse prints the metavar *or*
            # the choice list, and for a closed set the choices are the
            # help.
            group.add_argument(
                option.cli_flag,
                dest=f"opt_{option.name}",
                default=None,
                choices=list(option.choices),
                help=help_text,
            )
        else:
            group.add_argument(
                option.cli_flag,
                dest=f"opt_{option.name}",
                default=None,
                metavar=option.name.upper(),
                help=help_text,
            )


def _build_parser(kind: str | None, options: dict[str, Any]) -> argparse.ArgumentParser:
    """The ``make-figure`` parser, with `kind`'s own options folded in when one is named."""
    parser = argparse.ArgumentParser(
        prog="make-figure",
        description=(
            "Render one of the sprezzature-figures chart types, from your own data "
            "or from the figure's built-in demo rows."
        ),
        epilog=(
            "Sub-commands (each takes its own --help):\n"
            "  list        every chart kind, optionally filtered by status\n"
            "  describe    what a figure needs and what it accepts\n"
            "  redraw      redraw somebody else's chart from a picture of it\n"
            "  recommend   rank the chart types your data can fill\n"
            "  check       check a rendered SVG for the failures markup can show\n"
            "\n"
            "Examples:\n"
            "  make-figure --list\n"
            "  make-figure treemap --describe\n"
            "  make-figure bar --out sales.svg --title 'Q3 sales' --theme academic\n"
            "  make-figure bar --data sales.csv --map value=revenue --width 1200\n"
            "  make-figure sankey --set volume-unit=sessions --out flow.svg\n"
            "\n"
            "Every keyword a figure accepts has a flag of its own once you name the "
            "figure (`make-figure <kind> --help`), and `--set name=value` reaches any "
            "of them without one."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "kind",
        nargs="?",
        help="Chart type, e.g. treemap, funnel, waterfall. Use --list to see all.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output file path. The extension picks the format: .svg, .png, .pdf, .jpg, or .html.",
    )
    parser.add_argument(
        "--title",
        default=None,
        help="Chart title. Omitted, the figure keeps its own default title for demo "
        "data and goes untitled for your data.",
    )
    parser.add_argument(
        "--dark",
        action="store_true",
        help="Render for a dark canvas: transparent background + lightened chrome (SVG output).",
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=None,
        metavar="N",
        help="Upsample raster/PDF output N times for hi-DPI (e.g. --out chart.png --scale 3). "
        "Ignored for .svg/.html. Default: 1.",
    )
    parser.add_argument(
        "--data",
        default=None,
        help="Render your own data file (.csv/.tsv/.json/.jsonl) instead of the built-in demo data. "
        "Use '-' to read from stdin.",
    )
    parser.add_argument(
        "--map",
        action="append",
        default=[],
        metavar="ROLE=COLUMN",
        help="Bind a figure role to a data column when they differ, e.g. --map value=GDP "
        "(repeatable). Only used with --data.",
    )
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        dest="set_options",
        metavar="NAME=VALUE",
        help="Set any option this figure accepts, e.g. --set subtitle='Q3 figures' "
        "(repeatable). The scriptable twin of the per-figure flags below.",
    )
    parser.add_argument(
        "--describe",
        action="store_true",
        help="Print what this figure needs (data roles) and what it accepts (options), then exit.",
    )
    parser.add_argument(
        "--list", action="store_true", help="Print all available chart kinds and exit."
    )
    parser.add_argument(
        "--status",
        default=None,
        choices=["stable", "experimental", "legacy", "unavailable"],
        help="With --list, only show kinds with this status.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="With --list or --describe, print machine-readable JSON instead of text.",
    )
    if kind is not None:
        _kind_option_flags(parser, kind, options)
    return parser


def _describe(kind: str, as_json: bool) -> str:
    """Everything a caller needs before rendering `kind`: its roles, then its options."""
    from .options import describe_options, options_for

    definition = _get_figure_definition(kind)
    if as_json:
        import json

        return json.dumps(definition.model_dump(mode="json"), indent=2)

    def roles(items: Any) -> str:
        return (
            "\n".join(
                f"  {role.name}  ({role.label}; {'/'.join(role.accepted_types) or 'any'})"
                for role in items
            )
            or "  (none)"
        )

    options = options_for(kind)
    return "\n".join(
        [
            f"{kind} -- {definition.label} ({definition.category}, {definition.status})",
            "",
            definition.description,
            "",
            "Required data roles (every row must carry these keys):",
            roles(definition.required_roles),
            "",
            "Optional data roles:",
            roles(definition.optional_roles),
            "",
            f"Options ({len(options)}):",
            describe_options(kind),
            "",
            f"Renders to: {', '.join(definition.supported_outputs)}. "
            f"Default canvas: {definition.default_width}x{definition.default_height}.",
        ]
    )


def _unrecognised(kind: str | None, unknown: list[str], command: str = "make-figure") -> str:
    """Say which flag was not understood, and where the real ones are listed.

    Shared by both command lines, so `command` names the one the reader is
    actually typing into -- a Click user told to run ``make-figure`` would
    be sent to a different program.
    """
    import difflib

    from .options import options_for

    describe = (
        f"{command} {kind} --describe" if command == "make-figure" else f"{command} describe {kind}"
    )
    listing = "make-figure --list" if command == "make-figure" else f"{command} list"
    flags = [token for token in unknown if token.startswith("-")] or unknown
    if kind is None:
        return (
            f"Unrecognised argument: {flags[0]}. Name a chart kind first -- most flags "
            f"belong to a figure, not to the command -- and `{listing}` shows every kind."
        )
    known = options_for(kind)
    accepted = [option.cli_flag for option in known.values() if option.cli_flag]
    close = difflib.get_close_matches(flags[0], accepted, n=1, cutoff=0.6)
    hint = f" Did you mean {close[0]}?" if close else ""
    return (
        f"{kind} has no option {flags[0]}.{hint} It accepts: "
        f"{', '.join(sorted(accepted)) or 'no options'}. "
        f"Run `{describe}` for defaults and accepted values."
    )


def _run_action(build: Any) -> int:
    """Run one shared action and give its result to the terminal.

    The twin of ``_emit`` in the Click command: both call the same
    function in :mod:`sprezzature_figures.actions`, so the two command
    lines cannot answer the same question differently. All that differs
    here is ``print`` instead of ``click.echo``.
    """
    from .actions import ActionError

    try:
        result = build()
    except ActionError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    for line in result.out:
        print(line)
    for line in result.err:
        print(line, file=sys.stderr)
    return result.code


def _verb_parser(verb: str, description: str) -> argparse.ArgumentParser:
    """A sub-command parser named so ``--help`` says ``make-figure <verb>``."""
    return argparse.ArgumentParser(prog=f"make-figure {verb}", description=description)


def _verb_list(argv: list[str]) -> int:
    """``make-figure list`` -- the sub-command spelling of ``--list``."""
    parser = _verb_parser("list", "Print every chart kind this package can draw.")
    parser.add_argument(
        "--status",
        default=None,
        choices=["stable", "experimental", "legacy", "unavailable"],
        help="Only show kinds with this status.",
    )
    parser.add_argument("--json", action="store_true", help="Print the names as a JSON array.")
    args = parser.parse_args(argv)
    kinds = list_kinds(status=args.status)
    if args.json:
        import json

        print(json.dumps(kinds, indent=2))
    else:
        print(f"{len(kinds)} chart types available:")
        for kind in kinds:
            print(f"  {kind}")
    return 0


def _verb_describe(argv: list[str]) -> int:
    """``make-figure describe KIND`` -- the sub-command spelling of ``KIND --describe``."""
    parser = _verb_parser(
        "describe", "Show what a figure needs (data roles) and what it accepts (options)."
    )
    parser.add_argument("kind", help="Chart type name or alias.")
    parser.add_argument(
        "--json", action="store_true", help="Print the full catalogue entry as JSON."
    )
    args = parser.parse_args(argv)
    canonical = _resolve_kind(args.kind)
    if canonical is None:
        print(f"Error: no script for kind={args.kind!r}.", file=sys.stderr)
        print("Run `make-figure --list` to see available kinds.", file=sys.stderr)
        return 1
    print(_describe(canonical, args.json))
    return 0


def _verb_redraw(argv: list[str]) -> int:
    """``make-figure redraw IMAGE`` -- twin of ``sprezzature-figures redraw``."""
    parser = _verb_parser(
        "redraw",
        "Take a picture of somebody else's chart and draw it properly, with reasons. "
        "Pass --data and you get a real figure; without it you get the redesign on "
        "sample data, captioned as such -- this never guesses numbers off a picture.",
    )
    parser.add_argument("image", help="Picture of the chart to redraw (a screenshot, usually).")
    parser.add_argument(
        "--out",
        default=None,
        help="Output file path. The extension picks the format. Defaults to <kind>-redrawn.svg.",
    )
    parser.add_argument(
        "--data",
        "--rows",
        dest="data_path",
        default=None,
        help="Your real rows (.csv/.tsv/.json/.jsonl). Use '-' to read from stdin.",
    )
    parser.add_argument(
        "--map",
        action="append",
        default=[],
        metavar="ROLE=COLUMN",
        help="Bind a figure role to a column of --data when they differ (repeatable).",
    )
    parser.add_argument(
        "--kind", default=None, help="Skip the model's choice of chart type and redraw as this one."
    )
    parser.add_argument("--title", default=None, help="Override the title.")
    parser.add_argument(
        "--hint",
        default="",
        help="Anything you want to tell the model about the image (what it is, what it shows).",
    )
    parser.add_argument(
        "--language",
        default="en",
        choices=["en", "fr"],
        help="Language of the provenance caption written onto the figure (default: en).",
    )
    args = parser.parse_args(argv)

    from . import actions

    return _run_action(
        lambda: actions.redraw(
            args.image,
            out=args.out,
            data_path=args.data_path,
            mappings=args.map,
            kind=args.kind,
            title=args.title,
            hint=args.hint,
            language=args.language,
        )
    )


def _verb_recommend(argv: list[str]) -> int:
    """``make-figure recommend --data FILE`` -- twin of ``sprezzature-figures recommend``."""
    parser = _verb_parser(
        "recommend",
        "Rank the chart types your data can fill, best first. Runs the deterministic "
        "compatibility filter and readability score the Studio GUI shows as cards, "
        "headless. No model involved.",
    )
    parser.add_argument(
        "--data",
        dest="data_path",
        required=True,
        help="Data file (.csv/.tsv/.json/.jsonl). Use '-' to read from stdin.",
    )
    parser.add_argument(
        "--limit", type=int, default=5, help="How many recommendations to show (default: 5)."
    )
    parser.add_argument(
        "--intent",
        dest="goal",
        default=None,
        choices=[
            "comparison",
            "trend",
            "distribution",
            "composition",
            "relationship",
            "flow",
            "hierarchy",
            "geography",
            "model_evaluation",
        ],
        help="Your analytical goal. Ranks figures that serve it first, instead of "
        "readability alone -- decisive when many kinds otherwise tie.",
    )
    parser.add_argument(
        "--render",
        dest="render_out",
        default=None,
        help="Also render the top recommendation to this output path.",
    )
    args = parser.parse_args(argv)

    from . import actions

    return _run_action(
        lambda: actions.recommend(
            args.data_path, limit=args.limit, goal=args.goal, render_out=args.render_out
        )
    )


def _verb_check(argv: list[str]) -> int:
    """``make-figure check FILE.svg`` -- twin of ``sprezzature-figures check``."""
    parser = _verb_parser(
        "check",
        "Check a rendered SVG for the failures that are decidable from markup: "
        "colliding labels, text off the canvas, leftover demo chrome, a light card "
        "on a dark page, a title the generator dropped. Exit code 1 on any finding, "
        "so it works as a pre-commit or CI gate.",
    )
    parser.add_argument("svg", help="The SVG to check. Use '-' to read it from stdin.")
    parser.add_argument(
        "--dark",
        action="store_true",
        help="The figure was rendered for a dark canvas. Adds the dark-mode rules.",
    )
    parser.add_argument(
        "--expect-title",
        dest="expected_title",
        default=None,
        help="Title you asked the generator for. Reported missing if no text carries it.",
    )
    parser.add_argument(
        "--forbid",
        dest="forbidden",
        action="append",
        default=[],
        metavar="TEXT",
        help="A string that must not appear, on top of the demo chrome already known (repeatable).",
    )
    parser.add_argument(
        "--format",
        dest="fmt",
        choices=("text", "json"),
        default="text",
        help="json prints one object on stdout -- rule, severity, message, detail, and a "
        "count per severity -- for a caller that acts on the result instead of reading "
        "it. The exit code is the same either way. (default: text)",
    )
    args = parser.parse_args(argv)

    from . import actions

    return _run_action(
        lambda: actions.check(
            args.svg,
            dark=args.dark,
            expected_title=args.expected_title,
            forbidden=args.forbidden,
            fmt=args.fmt,
        )
    )


#: ``make-figure`` sub-commands, by the word that selects them. They are the
#: argparse twins of the Click command group, so the always-installed command
#: can do everything the optional one can -- ``redraw``, ``recommend`` and
#: ``check`` used to exist only behind the ``[cli]`` extra, while the HTTP API
#: exposed all three as routes. A word here only wins if it is not also a
#: chart kind; :func:`_verbs_are_not_chart_kinds` keeps that true.
_VERBS: dict[str, Any] = {
    "list": _verb_list,
    "describe": _verb_describe,
    "redraw": _verb_redraw,
    "recommend": _verb_recommend,
    "check": _verb_check,
}


def main(argv: list[str] | None = None) -> None:
    """
    CLI entry point for the ``make-figure`` command.

    Parses in two passes so a figure's own keywords can become flags: the
    first pass reads which kind was named, the second re-parses with that
    kind's options declared. This is why ``make-figure sankey --help``
    documents ``--volume-unit`` while ``make-figure --help`` does not --
    the flag only exists for the figures that accept it.

    Parameters
    ----------
    argv : list of str or None, optional
        Arguments to parse. ``None`` reads ``sys.argv``.

    Usage::

        make-figure --list
        make-figure treemap --describe
        make-figure treemap --out output.svg --title "My chart"
        make-figure bar --data sales.csv --map value=revenue --width 1200
    """
    from .options import OptionError, options_for, parse_option_assignments, validate_options

    argv = list(sys.argv[1:] if argv is None else argv)

    # A sub-command, when the first word names one and no figure answers to
    # that name. `make-figure redraw shot.png` was a chart kind called
    # "redraw" as far as this parser was concerned, and the three commands
    # the Click twin and the HTTP API both had -- redraw, recommend, check --
    # had no spelling here at all.
    if argv and argv[0] in _VERBS and _resolve_kind(argv[0]) is None:
        sys.exit(_VERBS[argv[0]](argv[1:]))

    # ``--help`` is answered by whichever parser is built last, so hold it
    # back through the probe pass: otherwise `make-figure bar --help` would
    # print the generic help and never mention bar's own flags.
    wants_help = any(token in ("-h", "--help") for token in argv)
    argv_without_help = [token for token in argv if token not in ("-h", "--help")]

    probe, _ = _build_parser(None, {}).parse_known_args(argv_without_help)
    canonical = _resolve_kind(probe.kind) if probe.kind else None
    if canonical is None:
        # An unknown flag ahead of the kind steals the positional slot
        # (`make-figure --subtitle Foo bar` reads Foo as the kind). Only the
        # probe is affected -- it exists to decide which flags to declare --
        # so recover by taking the first word that names a real figure.
        canonical = next(
            (
                resolved
                for token in argv_without_help
                if not token.startswith("-")
                for resolved in [_resolve_kind(token)]
                if resolved is not None
            ),
            None,
        )
    kind_options = options_for(canonical) if canonical else {}

    parser = _build_parser(canonical, kind_options)
    if wants_help:
        parser.print_help()
        return

    args, unknown = parser.parse_known_args(argv_without_help)
    if unknown:
        print(f"Error: {_unrecognised(canonical, unknown)}", file=sys.stderr)
        sys.exit(2)

    if args.list:
        kinds = list_kinds(status=args.status)
        if args.json:
            import json

            print(json.dumps(kinds, indent=2))
        else:
            print(f"{len(kinds)} chart types available:")
            for k in kinds:
                print(f"  {k}")
        return

    if not args.kind:
        parser.print_help()
        sys.exit(1)

    if canonical is None:
        print(f"Error: no script for kind={args.kind!r}.", file=sys.stderr)
        print("Run `make-figure --list` to see available kinds.", file=sys.stderr)
        sys.exit(1)

    if args.describe:
        print(_describe(canonical, args.json))
        return

    # Per-figure flags and --set are two spellings of one thing, so a name
    # given both ways is a mistake rather than a precedence puzzle.
    try:
        options: dict[str, Any] = parse_option_assignments(canonical, args.set_options)
        from_flags = {
            name[len("opt_") :]: value
            for name, value in vars(args).items()
            if name.startswith("opt_") and value is not None
        }
        clash = sorted(set(options) & set(from_flags))
        if clash:
            raise OptionError(
                f"{clash[0]} was given twice: as --{clash[0].replace('_', '-')} and "
                f"as --set {clash[0]}=... Keep one."
            )
        options.update(validate_options(canonical, from_flags))
    except OptionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(2)

    mapping: dict[str, str] = {}
    data: list[dict[str, Any]] | None = None
    if args.data:
        from .data_source import apply_mapping, load_records, load_stdin_records, parse_mapping

        try:
            data = load_stdin_records() if args.data == "-" else load_records(args.data)
            mapping = resolve_role_mapping(canonical, parse_mapping(args.map))
            data = apply_mapping(data, mapping)
        except (FileNotFoundError, ValueError) as exc:
            print(f"Error reading --data: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        if args.map:
            print("--map only applies with --data.", file=sys.stderr)
            sys.exit(1)
        # None, not the demo rows read back: handing a generator its own
        # DEMO_DATA looks like caller data from the inside, and the demo
        # chrome gets suppressed as a precaution against captioning
        # somebody else's numbers. `make-figure bar` should draw the
        # reference figure, title and all.
        data = None

    if args.scale is not None:
        import os

        os.environ["SPREZZATURE_RENDER_SCALE"] = repr(args.scale)

    kwargs: dict[str, Any] = dict(options)
    # An omitted --title used to arrive as "", which overrode each figure's
    # own headline: `make-figure sankey` drew the demo sankey untitled, and
    # no flag could get the title back. Omitted now means omitted, and the
    # generator's default applies -- except over your own data, where that
    # default is a sentence about the demo rows and would be a lie.
    if args.title is not None:
        kwargs["title"] = args.title
    if args.dark:
        kwargs["dark"] = True
    if args.out:
        kwargs["out"] = args.out
    if args.data:
        # User data must not inherit the demo chrome (title, subtitle, axis titles).
        for key, value in user_data_chrome_kwargs(canonical, mapping).items():
            kwargs.setdefault(key, value)

    try:
        result = make_figure(canonical, data, **kwargs)
    except (ValueError, AttributeError, FileNotFoundError, RuntimeError) as exc:
        print(f"Error rendering {args.kind!r}: {exc}", file=sys.stderr)
        if args.data:
            roles = describe_required_roles(canonical)
            if roles:
                print(f"{canonical} requires: {roles}.", file=sys.stderr)
            print(
                "If your columns don't match the figure's roles, bind them with "
                "--map role=column (the role's name or its label both work).",
                file=sys.stderr,
            )
        sys.exit(1)
    print(result)


if __name__ == "__main__":
    main()
