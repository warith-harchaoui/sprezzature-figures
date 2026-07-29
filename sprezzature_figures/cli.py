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
    from .make_figure import list_kinds, make_figure

    @click.group()
    def main() -> None:  # type: ignore[misc]
        """sprezzature-figures: render publication-quality data figures."""

    @main.command("list")
    def list_cmd() -> None:
        """Print all available chart kind names."""
        kinds = list_kinds()
        click.echo(f"{len(kinds)} chart types available:")
        for k in kinds:
            click.echo(f"  {k}")

    @main.command("render")
    @click.argument("kind")
    @click.option("--out", default=None, help="Output file path.")
    @click.option("--title", default="", help="Chart title.")
    def render_cmd(kind: str, out: str | None, title: str) -> None:
        """Render KIND using its DEMO_DATA. KIND is a chart type name."""
        import importlib.util
        import sys as _sys

        from .make_figure import _SCRIPTS_DIR

        normalised = kind.lower().strip().replace("-", "_").replace(" ", "_")
        candidate = _SCRIPTS_DIR / f"make_{normalised}.py"
        if not candidate.exists():
            click.echo(f"Error: no script for kind={kind!r}.", err=True)
            click.echo("Run `sprezzature-figures list` to see available kinds.", err=True)
            raise SystemExit(1)

        mod_name = f"_sfig_cli_{normalised}"
        spec = importlib.util.spec_from_file_location(mod_name, candidate)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        _sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]

        demo_data = getattr(mod, "DEMO_DATA", [])
        kwargs: dict = {"title": title}
        if out:
            kwargs["out"] = out

        result = make_figure(kind, demo_data, **kwargs)
        click.echo(result)
