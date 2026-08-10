"""
audit_generators — reproducible audit of every scripts/make_*.py generator.

For each generator script, records whether it can be imported, whether it
exposes the ``make_<kind>`` / ``DEMO_DATA`` contract the dispatcher relies on,
whether the dispatcher's hyphen-to-underscore normalisation can actually
reach it, and (with ``--render``) whether it renders successfully to a
throwaway temp path.

Exceptions are never swallowed silently: import and render failures record
the exception class and message so the report explains *why* a script is
not usable, not just that it isn't.

Usage
-----
    python tools/audit_generators.py                    # static checks only
    python tools/audit_generators.py --render            # also try rendering
    python tools/audit_generators.py --render --timeout 20

Writes ``docs/studio/generator_audit.json`` and ``docs/studio/GENERATOR_AUDIT.md``.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import argparse
import importlib.util
import inspect
import json
import signal
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
DOCS_DIR = REPO_ROOT / "docs" / "studio"

_VEGA_LITE_MARKERS = ("import altair", "alt.Chart", "vegalite")
_MATPLOTLIB_MARKERS = ("import matplotlib", "matplotlib.pyplot")
_SVG_MARKERS = ("def build_svg(", "<svg ")
_HTML_MARKERS = ("import plotly", "write_html", "<html")
_HARDCODED_PATH_MARKERS = ("assets/svg-examples", "assets/vega-examples", "assets/gallery")


class _Timeout(Exception):
    pass


def _alarm_handler(signum: int, frame: Any) -> None:  # noqa: ARG001
    raise _Timeout("render exceeded timeout")


def discover_scripts() -> list[Path]:
    """Every scripts/make_*.py generator, excluding the dispatcher itself."""
    return sorted(
        p for p in SCRIPTS_DIR.glob("make_*.py") if p.stem != "make_figure"
    )


def derive_kind(path: Path) -> str:
    """Public kind name: filename stem with the ``make_`` prefix stripped.

    Kept exactly as it appears on disk (hyphens included) — this is the
    "canonical" public name per the studio plan's registry design.
    """
    return path.stem[len("make_") :]


def expected_callable_name(kind: str) -> str:
    return f"make_{kind.replace('-', '_')}"


def dispatcher_reachable(kind: str, path: Path) -> bool:
    """Replicates sprezzature_figures.make_figure()'s current filename
    resolution: hyphens/spaces normalised to underscores, then looks for
    ``make_<normalised>.py``. Returns False when that candidate filename
    does not match the actual file on disk (the hyphenated-name bug).
    """
    normalised = kind.lower().strip().replace("-", "_").replace(" ", "_")
    candidate = SCRIPTS_DIR / f"make_{normalised}.py"
    return candidate.resolve() == path.resolve()


def import_script(path: Path, module_name: str) -> tuple[Any, str | None]:
    """Import a script as a standalone module. Returns (module, error_repr).

    Failures are never swallowed: the caller gets the exception's class name
    and message, not a blanket True/False.
    """
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        return None, "ImportError: could not build a module spec"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    try:
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
    except (Exception, SystemExit) as exc:  # noqa: BLE001 - intentionally broad, fully recorded
        # SystemExit is caught explicitly (it isn't an Exception subclass):
        # some generators raise it as a "missing optional dependency" guard at
        # import time. Letting that propagate would kill the whole audit run
        # instead of recording one script as unavailable.
        # KeyboardInterrupt/GeneratorExit are deliberately NOT caught here.
        sys.modules.pop(module_name, None)
        return None, f"{type(exc).__name__}: {exc}"
    return mod, None


def inspect_signature(fn: Any) -> dict[str, bool]:
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return {"accepts_data": False, "accepts_out": False, "accepts_title": False}
    names = set(params)
    has_var_kw = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())
    positional = [
        p
        for p in params.values()
        if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    return {
        "accepts_data": ("data" in names) or bool(positional),
        "accepts_out": ("out" in names) or has_var_kw,
        "accepts_title": ("title" in names) or has_var_kw,
    }


def detect_renderer(source: str) -> str:
    if any(m in source for m in _VEGA_LITE_MARKERS):
        return "vega_lite"
    if any(m in source for m in _SVG_MARKERS):
        return "svg"
    if any(m in source for m in _MATPLOTLIB_MARKERS):
        return "matplotlib"
    if any(m in source for m in _HTML_MARKERS):
        return "html"
    return "unknown"


def detect_hardcoded_output_path(source: str) -> bool:
    return any(marker in source for marker in _HARDCODED_PATH_MARKERS)


def detect_hardcoded_dimensions(fn: Any | None) -> bool:
    """True when width/height are fixed literals rather than data-driven."""
    if fn is None:
        return False
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False
    for name in ("width", "height"):
        p = params.get(name)
        if p is not None and isinstance(p.default, int):
            return True
    return False


def try_render(fn: Any, demo_data: list, out_path: Path, timeout: int) -> tuple[str, str | None]:
    """Attempt fn(demo_data, out=out_path, title=...). Returns (status, error_repr)."""
    use_alarm = hasattr(signal, "SIGALRM")
    if use_alarm:
        old_handler = signal.signal(signal.SIGALRM, _alarm_handler)
        signal.alarm(timeout)
    try:
        result = fn(demo_data, out=out_path, title="Generator audit")
        result_path = Path(result) if result is not None else out_path
        if not result_path.exists() or result_path.stat().st_size == 0:
            return "failed", "RenderError: no non-empty output file produced"
        return "passed", None
    except _Timeout:
        return "failed", f"TimeoutError: exceeded {timeout}s"
    except Exception as exc:  # noqa: BLE001 - intentionally broad, fully recorded
        return "failed", f"{type(exc).__name__}: {exc}"
    finally:
        if use_alarm:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)


def audit_one(path: Path, *, render: bool, timeout: int, tmp_dir: Path) -> dict[str, Any]:
    """Audit one `make_*.py` script against the `make_<kind>` contract.

    Parameters
    ----------
    path : Path
        The generator script to audit.
    render : bool
        If `True`, actually call the generator against `DEMO_DATA` and
        check the render succeeds (else the render step is skipped).
    timeout : int
        Seconds allowed for the render attempt.
    tmp_dir : Path
        Scratch directory for the render attempt's output file.

    Returns
    -------
    dict
        The audit entry: contract checks, `status`
        (`stable`/`experimental`/`legacy`/`unavailable`) and any `errors`.
    """
    kind = derive_kind(path)
    expected_callable = expected_callable_name(kind)
    reachable = dispatcher_reachable(kind, path)
    source = path.read_text(encoding="utf-8", errors="replace")

    entry: dict[str, Any] = {
        "kind": kind,
        "filename": path.name,
        "hyphenated_kind": "-" in kind,
        "dispatcher_reachable_by_kind": reachable,
        "importable": False,
        "import_error": None,
        "expected_callable": expected_callable,
        "callable_exists": False,
        "demo_data_exists": False,
        "demo_data_len": 0,
        "accepts_data": False,
        "accepts_out": False,
        "accepts_title": False,
        "renderer": detect_renderer(source),
        "writes_hardcoded_path": detect_hardcoded_output_path(source),
        "hardcoded_dimensions": False,
        "render_test": "skipped" if not render else "not_run",
        "render_error": None,
        "status": "unavailable",
        "errors": [],
    }

    module_name = f"_audit_generators_{kind.replace('-', '_')}"
    mod, import_error = import_script(path, module_name)
    if import_error is not None:
        entry["import_error"] = import_error
        entry["errors"].append(import_error)
        entry["status"] = "unavailable"
        return entry

    entry["importable"] = True

    demo_data = getattr(mod, "DEMO_DATA", None)
    entry["demo_data_exists"] = demo_data is not None
    if demo_data is not None:
        try:
            entry["demo_data_len"] = len(demo_data)
        except TypeError:
            entry["demo_data_len"] = 0
        if entry["demo_data_len"] == 0:
            entry["errors"].append("DEMO_DATA is present but empty")
    else:
        entry["errors"].append(f"No DEMO_DATA in {path.name}")

    fn = getattr(mod, expected_callable, None)
    entry["callable_exists"] = fn is not None
    if fn is None:
        entry["errors"].append(f"No callable named {expected_callable!r} in {path.name}")
    else:
        entry.update(inspect_signature(fn))
        entry["hardcoded_dimensions"] = detect_hardcoded_dimensions(fn)

    if not reachable:
        entry["errors"].append(
            f"make_figure({kind!r}) cannot resolve to {path.name}: "
            "hyphen/underscore normalisation looks for a different filename"
        )

    if entry["writes_hardcoded_path"]:
        entry["errors"].append("Default output path falls back to a shared assets/ directory")

    contract_complete = (
        entry["callable_exists"]
        and entry["demo_data_exists"]
        and entry["demo_data_len"] > 0
        and entry["accepts_data"]
        and entry["accepts_out"]
    )

    if render and contract_complete:
        out_path = tmp_dir / f"{module_name}.svg"
        status, error = try_render(fn, demo_data, out_path, timeout)
        entry["render_test"] = status
        entry["render_error"] = error
        if error:
            entry["errors"].append(error)

    if not contract_complete:
        entry["status"] = "legacy"
    elif entry["render_test"] == "failed":
        entry["status"] = "experimental"
    elif entry["render_test"] == "passed":
        entry["status"] = "stable"
    else:
        # Contract satisfied but rendering was not attempted this run.
        entry["status"] = "experimental"

    return entry


def run_audit(*, render: bool, timeout: int) -> list[dict[str, Any]]:
    """Run :func:`audit_one` over every discovered `make_*.py` script.

    Parameters
    ----------
    render, timeout
        Forwarded to :func:`audit_one`.

    Returns
    -------
    list of dict
        One audit entry per script, in :func:`discover_scripts` order.
    """
    with tempfile.TemporaryDirectory(prefix="sprezzature-audit-") as tmp:
        tmp_dir = Path(tmp)
        return [audit_one(p, render=render, timeout=timeout, tmp_dir=tmp_dir) for p in discover_scripts()]


def summarize(entries: list[dict[str, Any]]) -> dict[str, int]:
    """Count audit `entries` by their `status` value."""
    counts: dict[str, int] = {"stable": 0, "experimental": 0, "legacy": 0, "unavailable": 0}
    for e in entries:
        counts[e["status"]] = counts.get(e["status"], 0) + 1
    return counts


def to_markdown(entries: list[dict[str, Any]], counts: dict[str, int]) -> str:
    """Render `entries`/`counts` (from :func:`run_audit`/:func:`summarize`) as a Markdown report."""
    lines = [
        "# Generator audit",
        "",
        "Reproducible audit of every `scripts/make_*.py` generator against the",
        "`make_<kind>(data, *, out, title, ...) -> Path` contract the dispatcher",
        "expects. Regenerate with `python tools/audit_generators.py --render`.",
        "",
        f"- **stable**: {counts.get('stable', 0)}",
        f"- **experimental**: {counts.get('experimental', 0)}",
        f"- **legacy**: {counts.get('legacy', 0)}",
        f"- **unavailable**: {counts.get('unavailable', 0)}",
        f"- **total**: {len(entries)}",
        "",
        "| kind | status | reachable | callable | demo_data | render | errors |",
        "|---|---|---|---|---|---|---|",
    ]
    for e in entries:
        reachable = "yes" if e["dispatcher_reachable_by_kind"] else "**no**"
        callable_ok = "yes" if e["callable_exists"] else "**no**"
        demo_ok = "yes" if e["demo_data_exists"] and e["demo_data_len"] > 0 else "**no**"
        render_cell = e["render_test"]
        error_cell = "; ".join(e["errors"][:2]) if e["errors"] else ""
        lines.append(
            f"| `{e['kind']}` | {e['status']} | {reachable} | {callable_ok} | {demo_ok} "
            f"| {render_cell} | {error_cell} |"
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: run the audit and write `generator_audit.json`/`GENERATOR_AUDIT.md`."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--render", action="store_true", help="Also attempt to render each contract-complete generator."
    )
    parser.add_argument("--timeout", type=int, default=30, help="Per-script render timeout in seconds.")
    parser.add_argument(
        "--out-dir", type=Path, default=DOCS_DIR, help="Where to write generator_audit.json / GENERATOR_AUDIT.md."
    )
    args = parser.parse_args(argv)

    entries = run_audit(render=args.render, timeout=args.timeout)
    counts = summarize(entries)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "generator_audit.json").write_text(
        json.dumps({"summary": counts, "generators": entries}, indent=2) + "\n", encoding="utf-8"
    )
    (args.out_dir / "GENERATOR_AUDIT.md").write_text(to_markdown(entries, counts), encoding="utf-8")

    print(f"Audited {len(entries)} generators: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
