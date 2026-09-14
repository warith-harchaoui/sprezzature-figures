"""
cli — Click entry point for the ``sprezzature-figures`` command.

Wraps :mod:`sprezzature_figures.make_figure` in a Click interface.
The argparse-based ``make-figure`` command is always installed;
this Click twin is available with the ``[cli]`` extra.

Author
------
Warith HARCHAOUI <warith.harchaoui@gmail.com>
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
    from .catalog import resolve_kind
    from .make_figure import _demo_data_for, list_kinds, make_figure

    @click.group()
    def main() -> None:  # type: ignore[misc]
        """sprezzature-figures: render publication-quality data figures."""

    @main.command("list")
    @click.option(
        "--status",
        default=None,
        type=click.Choice(["stable", "experimental", "legacy", "unavailable"]),
        help="Only show kinds with this status.",
    )
    def list_cmd(status: str | None) -> None:
        """Print all available chart kind names."""
        kinds = list_kinds(status=status)
        click.echo(f"{len(kinds)} chart types available:")
        for k in kinds:
            click.echo(f"  {k}")

    @main.command("render")
    @click.argument("kind")
    @click.option(
        "--out",
        default=None,
        help="Output file path. The extension picks the format: .svg, .png, .pdf, .jpg, or .html.",
    )
    @click.option("--title", default="", help="Chart title.")
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
    def render_cmd(
        kind: str,
        out: str | None,
        title: str,
        scale: float | None,
        data_path: str | None,
        mappings: tuple[str, ...],
    ) -> None:
        """Render KIND from a --data file, or its DEMO_DATA. KIND is a chart type name."""
        canonical = resolve_kind(kind)
        if canonical is None:
            click.echo(f"Error: no script for kind={kind!r}.", err=True)
            click.echo("Run `sprezzature-figures list` to see available kinds.", err=True)
            raise SystemExit(1)

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
            data = _demo_data_for(canonical)

        if scale is not None:
            import os

            os.environ["SPREZZATURE_RENDER_SCALE"] = repr(scale)

        kwargs: dict = {"title": title}
        if out:
            kwargs["out"] = out
        if data_path:
            # User data must not inherit the demo chrome (subtitle, axis titles).
            from .make_figure import user_data_chrome_kwargs

            for key, value in user_data_chrome_kwargs(canonical, mapping).items():
                kwargs.setdefault(key, value)

        try:
            result = make_figure(kind, data, **kwargs)
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

    @main.command("redraw")
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
        from .redraw import redraw

        rows = None
        if data_path:
            from .data_source import apply_mapping, load_records, load_stdin_records, parse_mapping

            try:
                rows = load_stdin_records() if data_path == "-" else load_records(data_path)
                if mappings:
                    rows = apply_mapping(rows, parse_mapping(list(mappings)))
            except (FileNotFoundError, ValueError) as exc:
                click.echo(f"Error reading --data: {exc}", err=True)
                raise SystemExit(1) from exc
        elif mappings:
            click.echo("--map only applies with --data.", err=True)
            raise SystemExit(1)

        try:
            result = redraw(
                image,
                out=out,
                data=rows,
                kind=kind,
                title=title,
                hint=hint,
                language=language,
            )
        except (ValueError, FileNotFoundError, RuntimeError) as exc:
            click.echo(f"Error redrawing {image!r}: {exc}", err=True)
            raise SystemExit(1) from exc
        except ImportError as exc:
            click.echo(
                "redraw needs a vision model. Install with: "
                "pip install 'sprezzature-figures[local]' and make sure Ollama is running.",
                err=True,
            )
            raise SystemExit(1) from exc

        click.echo(f"{result.kind} -> {result.output}  (data: {result.data_origin})")
        if result.changes:
            click.echo("What it does differently:")
            for change in result.changes:
                click.echo(f"  - {change}")
        for warning in result.warnings:
            click.echo(f"note: {warning}", err=True)

    @main.command("recommend")
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
        from pathlib import Path

        from .data_source import load_records, load_stdin_records

        try:
            records = load_stdin_records() if data_path == "-" else load_records(data_path)
        except (FileNotFoundError, ValueError) as exc:
            click.echo(f"Error reading --data: {exc}", err=True)
            raise SystemExit(1) from exc

        name = "stdin" if data_path == "-" else Path(data_path).name

        try:
            import pandas as pd

            from .studio.ingest.profiler import profile_dataframe
            from .studio.recommendation import assign_columns, rank
        except ImportError as exc:
            click.echo(
                "recommend needs the profiling stack. Install with: "
                "pip install 'sprezzature-figures[studio]' (or [dataviz]).",
                err=True,
            )
            raise SystemExit(1) from exc

        profile = profile_dataframe(
            pd.DataFrame(records), dataset_id=name, fingerprint="cli", source_name=name
        )
        ranked = rank(profile, goal=goal)
        if not ranked:
            click.echo(
                f"No stable chart type can be filled from {name} "
                f"({profile.column_count} columns, {profile.row_count} rows). "
                "See `sprezzature-figures list --status stable`.",
                err=True,
            )
            raise SystemExit(1)

        click.echo(f"Top {min(limit, len(ranked))} chart types for {name} (best first):")
        for definition, figure_score in ranked[:limit]:
            binding = assign_columns(definition, profile) or {}
            roles = ", ".join(f"{role}={col}" for role, col in binding.items())
            click.echo(f"  {definition.kind:<20} score={figure_score:.2f}  {roles}")

        if render_out:
            top = ranked[0][0]
            top_binding = assign_columns(top, profile) or {}
            # Alias each bound column to the role name the generator expects,
            # keeping the originals so figures that read extra columns still work.
            bound = [
                {**row, **{role: row[col] for role, col in top_binding.items()}} for row in records
            ]
            result = make_figure(top.kind, bound, out=render_out)
            click.echo(f"rendered top recommendation ({top.kind}) -> {result}")

    @main.command("check")
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
    def check_cmd(
        svg: str, dark: bool, expected_title: str | None, forbidden: tuple[str, ...]
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
        import sys as _sys
        from pathlib import Path

        from .render_checks import check_render

        source = _sys.stdin.read() if svg == "-" else Path(svg).read_text(encoding="utf-8")
        findings = check_render(
            source, dark=dark, expected_title=expected_title, forbidden_text=forbidden
        )
        if not findings:
            click.echo(f"{svg}: nothing to report.")
            return

        click.echo(f"{svg}: {len(findings)} finding(s)", err=True)
        for finding in findings:
            click.echo(f"  {finding.check}: {finding.message}", err=True)
            if finding.detail:
                click.echo(f"    {finding.detail}", err=True)
        raise SystemExit(1)
