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
    @click.option("--out", default=None, help="Output file path.")
    @click.option("--title", default="", help="Chart title.")
    @click.option(
        "--data",
        "data_path",
        default=None,
        type=click.Path(exists=True, dir_okay=False),
        help="Render your own data file (.csv/.tsv/.json/.jsonl) instead of the demo data.",
    )
    def render_cmd(kind: str, out: str | None, title: str, data_path: str | None) -> None:
        """Render KIND from a --data file, or its DEMO_DATA. KIND is a chart type name."""
        canonical = resolve_kind(kind)
        if canonical is None:
            click.echo(f"Error: no script for kind={kind!r}.", err=True)
            click.echo("Run `sprezzature-figures list` to see available kinds.", err=True)
            raise SystemExit(1)

        if data_path:
            from .data_source import load_records

            try:
                data = load_records(data_path)
            except (FileNotFoundError, ValueError) as exc:
                click.echo(f"Error reading --data: {exc}", err=True)
                raise SystemExit(1) from exc
        else:
            data = _demo_data_for(canonical)

        kwargs: dict = {"title": title}
        if out:
            kwargs["out"] = out

        result = make_figure(kind, data, **kwargs)
        click.echo(result)
