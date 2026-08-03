"""
cli — Click entry point for the ``sprezzature-figures`` command.

Wraps :mod:`sprezzature_figures.make_figure` in a Click interface.
The argparse-based ``make-figure`` command is always installed;
this Click twin is available with the ``[cli]`` extra.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
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

        if data_path:
            from .data_source import apply_mapping, load_records, load_stdin_records, parse_mapping

            try:
                data = load_stdin_records() if data_path == "-" else load_records(data_path)
                data = apply_mapping(data, parse_mapping(list(mappings)))
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

        try:
            result = make_figure(kind, data, **kwargs)
        except (ValueError, AttributeError, FileNotFoundError, RuntimeError) as exc:
            click.echo(f"Error rendering {kind!r}: {exc}", err=True)
            if data_path:
                click.echo("If your columns don't match the figure's roles, bind them with --map role=column.", err=True)
            raise SystemExit(1) from exc
        click.echo(result)

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
        "--render",
        "render_out",
        default=None,
        help="Also render the top recommendation to this output path.",
    )
    def recommend_cmd(data_path: str, limit: int, render_out: str | None) -> None:
        """Rank the chart types your DATA file can fill, best first.

        Runs the same deterministic compatibility filter + readability score the
        Studio GUI shows as recommendation cards, headless. No model involved.
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
        ranked = rank(profile)
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
            bound = [{**row, **{role: row[col] for role, col in top_binding.items()}} for row in records]
            result = make_figure(top.kind, bound, out=render_out)
            click.echo(f"rendered top recommendation ({top.kind}) -> {result}")
