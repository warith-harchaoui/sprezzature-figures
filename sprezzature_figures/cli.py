"""
cli — Click entry point for the ``sprezzature-figures`` command.

Wraps :mod:`sprezzature_figures.make_figure` in a Click interface.
The argparse-based ``make-figure`` command is always installed;
this Click twin is available with the ``[cli]`` extra.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

import sys

try:
    import click
except ImportError:
    # Click is optional; the argparse CLI in make_figure.py is always available.
    def main() -> None:  # type: ignore[misc]
        """Placeholder when click is not installed."""
        print(
            "sprezzature-figures click CLI requires click. "
            "Install with: pip install 'sprezzature-figures[cli]'",
            file=sys.stderr,
        )
        sys.exit(1)
else:
    from collections.abc import Callable

    from .actions import ActionError, ActionResult
    from .catalog import resolve_kind
    from .make_figure import list_kinds, make_figure

    # The group gets its own name so the `@cli.command(...)` decorators below
    # attach to a real `click.Group`. Binding it to `main` directly made the
    # name mean a plain function in the fallback branch and a Group here, and
    # every decorator then read as an attribute on a function.
    @click.group()
    def cli() -> None:
        """sprezzature-figures: render publication-quality data figures."""

    def _emit(action: Callable[[], ActionResult]) -> None:
        """Run one shared action and give its result to the terminal.

        The work lives in :mod:`sprezzature_figures.actions` so the
        argparse command can do exactly the same thing; all that is left
        here is which stream each line goes to and what to exit with.
        """
        try:
            result = action()
        except ActionError as exc:
            click.echo(str(exc), err=True)
            raise SystemExit(1) from exc
        for line in result.out:
            click.echo(line)
        for line in result.err:
            click.echo(line, err=True)
        if result.code:
            raise SystemExit(result.code)

    @cli.command("list")
    @click.option(
        "--status",
        default=None,
        type=click.Choice(["stable", "experimental", "legacy", "unavailable"]),
        help="Only show kinds with this status.",
    )
    @click.option(
        "--json",
        "as_json",
        is_flag=True,
        help="Print the names as a JSON array, for a caller that is not a person.",
    )
    def list_cmd(status: str | None, as_json: bool) -> None:
        """Print all available chart kind names."""
        kinds = list_kinds(status=status)
        if as_json:
            import json

            click.echo(json.dumps(kinds, indent=2))
            return
        click.echo(f"{len(kinds)} chart types available:")
        for k in kinds:
            click.echo(f"  {k}")

    class FigureRenderCommand(click.Command):
        """``render``, grown a flag for every keyword the named figure accepts.

        Click builds a command's options once, at import time, from its
        decorators; the options a figure accepts are not known until the
        caller names the figure. So the parameter list is rebuilt here, at
        the top of parsing, from the frozen catalogue -- which is also when
        ``--help`` is answered, so ``sprezzature-figures render sankey
        --help`` documents ``--volume-unit`` and the bare ``render --help``
        does not. The argparse twin (``make-figure``) does the same thing
        with a two-pass parse; both read the same ``options_schema``, so a
        flag exists in both commands or in neither.
        """

        #: The decorator-declared options, kept aside the first time the
        #: command runs so each parse starts from them rather than from the
        #: previous parse's figure.
        _base_params: list[click.Parameter] | None = None

        def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
            """Declare the named figure's options, then parse normally."""
            if self._base_params is None:
                type(self)._base_params = list(self.params)
            # The first word that names a real figure is the figure: a value
            # sitting after a flag (`--title bar`) can look like a positional
            # to a parser that does not yet know which flags take values.
            kind = next(
                (
                    resolved
                    for token in args
                    if not token.startswith("-")
                    for resolved in [resolve_kind(token)]
                    if resolved is not None
                ),
                None,
            )
            self.params = [*(self._base_params or []), *_figure_params(kind)]
            try:
                return super().parse_args(ctx, args)
            except click.NoSuchOption as exc:
                # Click's own message offers the nearest *generic* flag
                # ("--width? did you mean --data?"). The useful answer is
                # which options this figure has, which is the same sentence
                # the argparse twin prints.
                from .make_figure import _unrecognised

                raise click.UsageError(
                    _unrecognised(kind, [exc.option_name], "sprezzature-figures"), ctx=ctx
                ) from exc

    def _figure_params(kind: str | None) -> list[click.Parameter]:
        """One Click option per keyword `kind` accepts, minus the ones render already owns."""
        if kind is None:
            return []
        from .options import options_for

        params: list[click.Parameter] = []
        for option in options_for(kind).values():
            if not option.cli_flag or option.name == "title":
                continue
            shown = "" if option.default is None else f"  [default: {option.default!r}]"
            help_text = (option.description or f"{option.name} option.") + shown
            if option.type == "bool":
                flag = f"{option.cli_flag}/--no-{option.name.replace('_', '-')}"
                params.append(
                    click.Option([flag, f"opt_{option.name}"], default=None, help=help_text)
                )
            else:
                params.append(
                    click.Option(
                        [option.cli_flag, f"opt_{option.name}"],
                        default=None,
                        metavar=None if option.choices else option.name.upper(),
                        type=click.Choice(list(option.choices)) if option.choices else str,
                        help=help_text,
                    )
                )
        return params

    @cli.command("render", cls=FigureRenderCommand)
    @click.argument("kind")
    @click.option(
        "--out",
        default=None,
        help="Output file path. The extension picks the format: .svg, .png, .pdf, .jpg, or .html.",
    )
    @click.option(
        "--title",
        default=None,
        help="Chart title. Omitted, the figure keeps its own default title for demo "
        "data and goes untitled for your data.",
    )
    @click.option(
        "--dark",
        is_flag=True,
        help="Render for a dark canvas: transparent background + lightened chrome (SVG output).",
    )
    @click.option(
        "--scale",
        default=None,
        type=float,
        metavar="N",
        help="Upsample raster/PDF output N times for hi-DPI (e.g. --out chart.png --scale 3). "
        "Ignored for .svg/.html.",
    )
    @click.option(
        "--data",
        "data_path",
        default=None,
        type=click.Path(exists=True, dir_okay=False, allow_dash=True),
        help="Render your own data file (.csv/.tsv/.json/.jsonl) instead of the demo data. "
        "Use '-' to read from stdin.",
    )
    @click.option(
        "--map",
        "mappings",
        multiple=True,
        metavar="ROLE=COLUMN",
        help="Bind a figure role to a data column when they differ, e.g. --map value=GDP "
        "(repeatable). Only used with --data.",
    )
    @click.option(
        "--set",
        "set_options",
        multiple=True,
        metavar="NAME=VALUE",
        help="Set any option this figure accepts, e.g. --set subtitle='Q3 figures' "
        "(repeatable). The scriptable twin of the per-figure flags.",
    )
    def render_cmd(
        kind: str,
        out: str | None,
        title: str | None,
        dark: bool,
        scale: float | None,
        data_path: str | None,
        mappings: tuple[str, ...],
        set_options: tuple[str, ...],
        **figure_options: object,
    ) -> None:
        """Render KIND from a --data file, or its DEMO_DATA. KIND is a chart type name.

        Every keyword the figure accepts has a flag of its own here --
        `sprezzature-figures render <kind> --help` lists them with their
        defaults -- and `--set name=value` reaches any of them without one.
        """
        from .options import OptionError, parse_option_assignments, validate_options

        canonical = resolve_kind(kind)
        if canonical is None:
            click.echo(f"Error: no script for kind={kind!r}.", err=True)
            click.echo("Run `sprezzature-figures list` to see available kinds.", err=True)
            raise SystemExit(1)

        # Per-figure flags and --set are two spellings of one thing, so a
        # name given both ways is a mistake rather than a precedence puzzle.
        try:
            options = parse_option_assignments(canonical, list(set_options))
            from_flags = {
                name[len("opt_") :]: value
                for name, value in figure_options.items()
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
            click.echo(f"Error: {exc}", err=True)
            raise SystemExit(2) from exc

        mapping: dict[str, str] = {}
        if data_path:
            from .data_source import apply_mapping, load_records, load_stdin_records, parse_mapping

            try:
                from .make_figure import resolve_role_mapping

                data = load_stdin_records() if data_path == "-" else load_records(data_path)
                mapping = resolve_role_mapping(canonical, parse_mapping(list(mappings)))
                data = apply_mapping(data, mapping)
            except (FileNotFoundError, ValueError) as exc:
                click.echo(f"Error reading --data: {exc}", err=True)
                raise SystemExit(1) from exc
        else:
            if mappings:
                click.echo("--map only applies with --data.", err=True)
                raise SystemExit(1)
            # None, not the demo rows read back -- see the note in
            # make_figure.main(): a generator handed its own DEMO_DATA
            # cannot tell it from caller data, and drops its own chrome.
            data = None

        if scale is not None:
            import os

            os.environ["SPREZZATURE_RENDER_SCALE"] = repr(scale)

        kwargs: dict = dict(options)
        # An omitted --title means omitted: the figure keeps its own
        # headline over its own demo rows, and goes untitled over yours,
        # where that headline would be a sentence about data you did not
        # supply.
        if title is not None:
            kwargs["title"] = title
        if dark:
            kwargs["dark"] = True
        if out:
            kwargs["out"] = out
        if data_path:
            # User data must not inherit the demo chrome (title, subtitle, axis titles).
            from .make_figure import user_data_chrome_kwargs

            for key, value in user_data_chrome_kwargs(canonical, mapping).items():
                kwargs.setdefault(key, value)

        try:
            result = make_figure(canonical, data, **kwargs)
        except (ValueError, AttributeError, FileNotFoundError, RuntimeError) as exc:
            click.echo(f"Error rendering {kind!r}: {exc}", err=True)
            if data_path:
                from .make_figure import describe_required_roles

                roles = describe_required_roles(canonical)
                if roles:
                    click.echo(f"{canonical} requires: {roles}.", err=True)
                click.echo(
                    "If your columns don't match the figure's roles, bind them with "
                    "--map role=column (the role's name or its label both work).",
                    err=True,
                )
            raise SystemExit(1) from exc
        click.echo(result)

    @cli.command("describe")
    @click.argument("kind")
    @click.option(
        "--json",
        "as_json",
        is_flag=True,
        help="Print the figure's full catalogue entry as JSON instead of text.",
    )
    def describe_cmd(kind: str, as_json: bool) -> None:
        """Show what KIND needs (data roles) and what it accepts (options).

        The one place that answers "which columns must my rows carry, and
        what can I pass besides them" without reading the generator's
        source. Same output as `make-figure KIND --describe`.
        """
        from .make_figure import _describe

        canonical = resolve_kind(kind)
        if canonical is None:
            click.echo(f"Error: no script for kind={kind!r}.", err=True)
            click.echo("Run `sprezzature-figures list` to see available kinds.", err=True)
            raise SystemExit(1)
        click.echo(_describe(canonical, as_json))

    @cli.command("redraw")
    @click.argument("image", type=click.Path(exists=True, dir_okay=False))
    @click.option(
        "--out",
        default=None,
        help="Output file path. The extension picks the format: .svg, .png, .pdf, .jpg, or .html. "
        "Defaults to <kind>-redrawn.svg.",
    )
    @click.option(
        "--data",
        "data_path",
        default=None,
        type=click.Path(exists=True, dir_okay=False, allow_dash=True),
        help="Your real rows (.csv/.tsv/.json/.jsonl). Without this you get the redesign "
        "on sample data -- the right chart, not your numbers.",
    )
    @click.option(
        "--map",
        "mappings",
        multiple=True,
        metavar="ROLE=COLUMN",
        help="Bind a figure role to a column of --data when they differ (repeatable).",
    )
    @click.option(
        "--kind",
        default=None,
        help="Skip the model's choice of chart type and redraw as this one.",
    )
    @click.option("--title", default=None, help="Override the title.")
    @click.option(
        "--hint",
        default="",
        help="Anything you want to tell the model about the image (what it is, what it should show).",
    )
    @click.option(
        "--language",
        default="en",
        type=click.Choice(["en", "fr"]),
        show_default=True,
        help="Language of the provenance caption written onto the figure.",
    )
    def redraw_cmd(
        image: str,
        out: str | None,
        data_path: str | None,
        mappings: tuple[str, ...],
        kind: str | None,
        title: str | None,
        hint: str,
        language: str,
    ) -> None:
        """Redraw the chart in IMAGE as a sprezzature figure.

        IMAGE is a picture of somebody's existing chart -- a screenshot is the
        usual case. A vision model reads what it is and what makes it hard to
        read; the figure is then drawn here.

        The numbers are the honest part. Pass --data and you get a real figure.
        Without it you get the redesign on sample data, captioned as such: this
        never guesses numbers off a picture.
        """
        from . import actions

        _emit(
            lambda: actions.redraw(
                image,
                out=out,
                data_path=data_path,
                mappings=mappings,
                kind=kind,
                title=title,
                hint=hint,
                language=language,
            )
        )

    @cli.command("recommend")
    @click.option(
        "--data",
        "data_path",
        required=True,
        type=click.Path(exists=True, dir_okay=False, allow_dash=True),
        help="Data file (.csv/.tsv/.json/.jsonl) to recommend chart types for. "
        "Use '-' to read from stdin.",
    )
    @click.option("--limit", default=5, show_default=True, help="How many recommendations to show.")
    @click.option(
        "--intent",
        "goal",
        default=None,
        type=click.Choice(
            [
                "comparison",
                "trend",
                "distribution",
                "composition",
                "relationship",
                "flow",
                "hierarchy",
                "geography",
                "model_evaluation",
            ]
        ),
        help="Your analytical goal. Ranks figures that serve it first, instead of "
        "readability alone -- decisive when many kinds otherwise tie.",
    )
    @click.option(
        "--render",
        "render_out",
        default=None,
        help="Also render the top recommendation to this output path.",
    )
    def recommend_cmd(data_path: str, limit: int, goal: str | None, render_out: str | None) -> None:
        """Rank the chart types your DATA file can fill, best first.

        Runs the same deterministic compatibility filter + readability score the
        Studio GUI shows as recommendation cards, headless. No model involved.
        Add --intent to rank by your analytical goal (comparison, trend, ...).
        """
        from . import actions

        _emit(lambda: actions.recommend(data_path, limit=limit, goal=goal, render_out=render_out))

    @cli.command("check")
    @click.argument("svg", type=click.Path(exists=True, dir_okay=False, allow_dash=True))
    @click.option(
        "--dark",
        is_flag=True,
        help="The figure was rendered for a dark canvas. Adds the dark-mode rules: "
        "no light ink left behind, no large light surface in the middle of it.",
    )
    @click.option(
        "--expect-title",
        "expected_title",
        default=None,
        help="Title you asked the generator for. Reported missing if no text carries "
        "it, which is how you catch a generator that ignored the parameter.",
    )
    @click.option(
        "--forbid",
        "forbidden",
        multiple=True,
        metavar="TEXT",
        help="A string that must not appear, on top of the demo chrome already known "
        "(repeatable). Pass your own placeholders here.",
    )
    @click.option(
        "--format",
        "fmt",
        type=click.Choice(["text", "json"]),
        default="text",
        show_default=True,
        help="json prints one object on stdout -- rule, severity, message, detail, "
        "and a count per severity -- for a caller that acts on the result instead "
        "of reading it. The exit code is the same either way.",
    )
    def check_cmd(
        svg: str,
        dark: bool,
        expected_title: str | None,
        forbidden: tuple[str, ...],
        fmt: str,
    ) -> None:
        """Check a rendered SVG for the failures that are decidable from markup.

        The Ralph Eyeball Loop answers "does this read?" by showing the PNG to a
        vision model. This asks the same questions from the source alone, so a
        service with a text-only model, or none, can still refuse to ship an
        illegible figure: colliding labels, text off the canvas, leftover demo
        chrome, a light card on a dark page, a title the generator dropped.

        Exit code 1 on any finding, so it works as a pre-commit or CI gate.
        Judgements of taste are not here and never will be.
        """
        from . import actions

        _emit(
            lambda: actions.check(
                svg, dark=dark, expected_title=expected_title, forbidden=forbidden, fmt=fmt
            )
        )

    # The console script in pyproject.toml points at `main`.
    main = cli
