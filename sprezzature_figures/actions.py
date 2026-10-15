"""
actions — what the commands *do*, written once for both command lines.

``make-figure`` (argparse, always installed) and ``sprezzature-figures``
(Click, behind the ``[cli]`` extra) are two spellings of one tool, and the
HTTP API is a third. Rendering was already shared -- both call
:func:`~sprezzature_figures.make_figure.make_figure` -- but ``redraw``,
``recommend`` and ``check`` lived inside the Click command bodies, so the
always-installed command simply did not have them: three of the API's
routes had no command-line twin at all.

Each function here takes the arguments a caller supplies, does the work,
and returns an :class:`ActionResult`: the lines to print, the lines to
report, and the exit code. No ``click.echo``, no ``sys.exit``, no
``print`` -- the front end owns the terminal, this module owns the
behaviour. Failures that a user can fix raise :class:`ActionError`, whose
message is written to be read as-is.

Author
------
Warith HARCHAOUI <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = ["ActionError", "ActionResult", "check", "recommend", "redraw"]


class ActionError(RuntimeError):
    """Something the caller can fix: a missing file, an unreadable column, an absent extra.

    The message is the whole error report -- one sentence on what went
    wrong and one on what to do -- because both command lines print it
    verbatim and neither has anything to add.
    """


@dataclass
class ActionResult:
    """What a command produced: what to print, what to report, and how to exit."""

    out: list[str] = field(default_factory=list)
    err: list[str] = field(default_factory=list)
    code: int = 0


def _load_rows(data_path: str | None, mappings: Sequence[str]) -> list[dict[str, Any]] | None:
    """Read a ``--data`` file (or stdin) and apply the ``--map`` bindings.

    Returns ``None`` when no path was given, which every caller reads as
    "no rows of mine", not as "no rows".
    """
    from .data_source import apply_mapping, load_records, load_stdin_records, parse_mapping

    if not data_path:
        if mappings:
            raise ActionError("--map only applies with --data.")
        return None
    try:
        rows = load_stdin_records() if data_path == "-" else load_records(data_path)
        if mappings:
            rows = apply_mapping(rows, parse_mapping(list(mappings)))
    except (FileNotFoundError, ValueError) as exc:
        raise ActionError(f"Error reading --data: {exc}") from exc
    return rows


def redraw(
    image: str,
    *,
    out: str | None = None,
    data_path: str | None = None,
    mappings: Sequence[str] = (),
    kind: str | None = None,
    title: str | None = None,
    hint: str = "",
    language: str = "en",
) -> ActionResult:
    """Redraw the chart in `image` as a sprezzature figure.

    Parameters
    ----------
    image : str
        Path to a picture of somebody's existing chart -- a screenshot is
        the usual case.
    out : str or None, optional
        Output path. The extension picks the format. Defaults to
        ``<kind>-redrawn.svg``.
    data_path : str or None, optional
        Your real rows (.csv/.tsv/.json/.jsonl), or ``"-"`` for stdin.
        Without them you get the redesign on sample data.
    mappings : sequence of str, optional
        ``role=column`` bindings for `data_path`.
    kind : str or None, optional
        Skip the model's choice of chart type and redraw as this one.
    title : str or None, optional
        Override the title.
    hint : str, optional
        Anything worth telling the model about the image.
    language : str, optional
        Language of the provenance caption written onto the figure.

    Returns
    -------
    ActionResult
        The figure's path and what the redraw changed, plus any caveat as
        a reported line.

    Raises
    ------
    ActionError
        If the image cannot be read, or no vision model is available.
    """
    from .redraw import redraw as _redraw

    rows = _load_rows(data_path, mappings)
    try:
        result = _redraw(
            image, out=out, data=rows, kind=kind, title=title, hint=hint, language=language
        )
    except ImportError as exc:
        raise ActionError(
            "redraw needs a vision model. Install with: "
            "pip install 'sprezzature-figures[local]' and make sure Ollama is running."
        ) from exc
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        raise ActionError(f"Error redrawing {image!r}: {exc}") from exc

    lines = [f"{result.kind} -> {result.output}  (data: {result.data_origin})"]
    if result.changes:
        lines.append("What it does differently:")
        lines.extend(f"  - {change}" for change in result.changes)
    return ActionResult(out=lines, err=[f"note: {warning}" for warning in result.warnings])


def recommend(
    data_path: str,
    *,
    limit: int = 5,
    goal: str | None = None,
    render_out: str | None = None,
) -> ActionResult:
    """Rank the chart types `data_path` can fill, best first.

    Runs the deterministic compatibility filter and readability score the
    Studio GUI shows as recommendation cards, headless. No model involved.

    Parameters
    ----------
    data_path : str
        Data file (.csv/.tsv/.json/.jsonl), or ``"-"`` for stdin.
    limit : int, optional
        How many candidates to report.
    goal : str or None, optional
        Analytical goal (``"comparison"``, ``"trend"``, ...). Ranks the
        figures that serve it first, which is decisive when readability
        alone leaves many kinds tied.
    render_out : str or None, optional
        Also render the top recommendation to this path.

    Returns
    -------
    ActionResult
        One line per candidate, with the column bindings already worked
        out.

    Raises
    ------
    ActionError
        If the file cannot be read, the profiling stack is not installed,
        or no stable figure can be filled from these columns.
    """
    from .data_source import load_records, load_stdin_records
    from .make_figure import make_figure

    try:
        records = load_stdin_records() if data_path == "-" else load_records(data_path)
    except (FileNotFoundError, ValueError) as exc:
        raise ActionError(f"Error reading --data: {exc}") from exc

    name = "stdin" if data_path == "-" else Path(data_path).name

    try:
        import pandas as pd

        from .studio.ingest.profiler import profile_dataframe
        from .studio.recommendation import assign_columns, rank
    except ImportError as exc:
        raise ActionError(
            "recommend needs the profiling stack. Install with: "
            "pip install 'sprezzature-figures[studio]' (or [dataviz])."
        ) from exc

    profile = profile_dataframe(
        pd.DataFrame(records), dataset_id=name, fingerprint="cli", source_name=name
    )
    ranked = rank(profile, goal=goal)
    if not ranked:
        raise ActionError(
            f"No stable chart type can be filled from {name} "
            f"({profile.column_count} columns, {profile.row_count} rows). "
            "See `make-figure --list --status stable`."
        )

    lines = [f"Top {min(limit, len(ranked))} chart types for {name} (best first):"]
    for definition, figure_score in ranked[:limit]:
        binding = assign_columns(definition, profile) or {}
        roles = ", ".join(f"{role}={col}" for role, col in binding.items())
        lines.append(f"  {definition.kind:<20} score={figure_score:.2f}  {roles}")

    if render_out:
        top = ranked[0][0]
        top_binding = assign_columns(top, profile) or {}
        # Alias each bound column to the role name the generator expects,
        # keeping the originals so figures that read extra columns still work.
        bound = [
            {**row, **{role: row[col] for role, col in top_binding.items()}} for row in records
        ]
        result = make_figure(top.kind, bound, out=render_out)
        lines.append(f"rendered top recommendation ({top.kind}) -> {result}")
    return ActionResult(out=lines)


def check(
    svg: str,
    *,
    dark: bool = False,
    expected_title: str | None = None,
    forbidden: Sequence[str] = (),
    fmt: str = "text",
) -> ActionResult:
    """Check a rendered SVG for the failures that are decidable from markup.

    The Ralph Eyeball Loop answers "does this read?" by showing the PNG to
    a vision model. This asks the same questions of the source alone, so a
    service with a text-only model, or none, can still refuse to ship an
    illegible figure. Judgements of taste are not here and never will be.

    Parameters
    ----------
    svg : str
        Path to the SVG, or ``"-"`` to read it from stdin.
    dark : bool, optional
        The figure was rendered for a dark canvas. Adds the dark-mode
        rules: no light ink left behind, no large light surface.
    expected_title : str or None, optional
        Title you asked the generator for. Reported missing if no text
        carries it, which is how a generator that ignored the parameter
        gets caught.
    forbidden : sequence of str, optional
        Strings that must not appear, on top of the demo chrome already
        known.
    fmt : {"text", "json"}, optional
        ``"json"`` prints one object on stdout -- the findings with their
        rule, severity, message and detail, plus a count per severity and
        an ``ok`` flag -- and nothing on stderr, so a caller that wants to
        act on the result does not have to parse prose. The exit code is
        the same either way: a gate keeps working, a program gains a
        machine-readable answer.

    Returns
    -------
    ActionResult
        Exit code 1 on any finding, so it works as a pre-commit or CI gate.
    """
    import sys

    from .render_checks import check_render

    source = sys.stdin.read() if svg == "-" else Path(svg).read_text(encoding="utf-8")
    findings = check_render(
        source, dark=dark, expected_title=expected_title, forbidden_text=list(forbidden)
    )
    if fmt == "json":
        import json

        # Severities the caller may have to branch on are spelled out even
        # when the count is zero: a key that only appears when something
        # went wrong turns every reader into a `.get(..., 0)`.
        counts = {
            niveau: sum(1 for f in findings if f.severity == niveau)
            for niveau in ("error", "warning")
        }
        rapport = {
            "source": svg,
            "ok": not findings,
            "counts": counts,
            "findings": [
                {
                    "check": f.check,
                    "severity": f.severity,
                    "message": f.message,
                    "detail": f.detail,
                }
                for f in findings
            ],
        }
        return ActionResult(
            out=[json.dumps(rapport, ensure_ascii=False, indent=2)], code=1 if findings else 0
        )
    if not findings:
        return ActionResult(out=[f"{svg}: nothing to report."])

    reported = [f"{svg}: {len(findings)} finding(s)"]
    for finding in findings:
        reported.append(f"  {finding.check}: {finding.message}")
        if finding.detail:
            reported.append(f"    {finding.detail}")
    return ActionResult(err=reported, code=1)
