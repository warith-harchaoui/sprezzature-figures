#!/usr/bin/env python3
"""
audit_generator_hardcoded_text
===============================

Static auditor for the hand-authored ``make_<kind>.py`` SVG *generators*
themselves (source code, not rendered output) — flags axis titles, legend
headers, and tooltip units baked into an f-string as a literal, with no
function parameter a caller could pass to override them.

Born from a real bug: ``make_columnrange.py``'s y-axis title
("Temperature (°C)") and legend header ("City") were hardcoded literals —
any caller plotting non-weather data (a revenue forecast, a confidence
interval on survey responses, anything) silently inherited nonsensical
axis chrome, because there was no parameter to override it with. Fixed by
hand in that one generator; this script makes the check mechanical so the
same bug class does not quietly recur in any of the other generators.

``audit_figure.py`` (the sibling tool) audits *rendered* Vega-Lite JSON /
SVG / HTML for a different rule set (missing axis titles, dual y-axes,
rainbow palettes...) — it cannot see this bug, because a hardcoded
literal renders as perfectly valid, well-formed SVG text. This script
reads the *generator source* instead, where the absence of a parameter is
visible.

Two finding classes
--------------------
``unparameterized-chrome-text`` (warning)
    A short (≤3 word) literal that looks like structural chart chrome —
    an axis title, a legend header, a unit suffix (``"Value"``,
    ``"City"``, ``"°C"``, ``"Group"``). These are almost always a real
    bug: give the caller a keyword parameter.

``unparameterized-narrative-text`` (info)
    A longer literal — an insight annotation, a callout sentence
    ("Winter does most of the waiting"). These are often *intentionally*
    tied to that generator's own demo dataset and may be fine to leave as
    a documented example default; still worth a caller-overridable
    parameter if the generator is meant to plot arbitrary data, but not
    automatically a bug the way chrome text is. Reported at ``info`` so a
    strict gate does not block on editorial content, while still keeping
    an inventory of what to consider generalizing.

Deliberately excludes: single-character/symbol residues (mark-only tick
formatting like ``"%"`` or ``"$"`` glued to a computed value), and any
``<text>`` content that is entirely one or more ``{...}`` f-string
expressions with no literal residue (already parameterized correctly —
this is the *absence* of a bug, not a finding).

Usage
-----
::

    python audit_generator_hardcoded_text.py scripts/make_columnrange.py
    python audit_generator_hardcoded_text.py scripts/ --json
    python audit_generator_hardcoded_text.py scripts/ --strict

Exit codes: ``0`` clean (or warnings only, without ``--strict``), ``1``
one or more warnings under ``--strict`` (info never fails the gate),
``2`` CLI error.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _argparse import make_parser  # noqa: E402

# A <text ...>CONTENT</text> as it appears in the f-string SOURCE (not
# rendered output): CONTENT may interleave literal text and {expression}
# placeholders. Matches within a single source line, which is how every
# existing generator writes its text elements (one f-string literal per
# call to .append(...), possibly continued across lines with implicit
# string concatenation — line-based matching covers the codebase's actual
# style; a generator that reformats this differently would need a fancier
# parser, out of scope for a fast pre-commit gate).
_TEXT_CONTENT_RE = re.compile(r">([^<{}]*(?:\{[^{}]*\}[^<{}]*)*)</text>")
_BRACE_EXPR_RE = re.compile(r"\{[^{}]*\}")
_ALPHA_RUN_RE = re.compile(r"[A-Za-zÀ-ÿ]{2,}")

# Residues that are structurally fine to hardcode even though they match
# the "short literal" shape: single symbols/units glued onto a computed
# number (e.g. an f-string ending "...{val}%</text>" leaves "%" as
# residue), and empty/whitespace-only matches.
_SAFE_RESIDUES = {"%", "€", "$", "°", "-", "—", "·", ":", ",", ".", ""}


def make_finding(rule: str, severity: str, message: str, path: str = "", line: int = 1) -> Dict[str, Any]:
    return {"path": path, "line": line, "rule": rule, "severity": severity, "message": message}


def _function_param_names(source: str) -> set[str]:
    """All parameter names across every function def in the module — the
    set of names a caller could plausibly already use to override text.
    Deliberately not scoped to one function: a generator's ``build_svg``
    and its public ``make_<kind>`` wrapper both count, and some callers
    read module-level constants too."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            for a in (*args.posonlyargs, *args.args, *args.kwonlyargs):
                names.add(a.arg)
    return names


def _literal_residue(content: str) -> str:
    """Strip every {expression} span, collapse whitespace, return what's left."""
    residue = _BRACE_EXPR_RE.sub(" ", content)
    return re.sub(r"\s+", " ", residue).strip()


def _looks_like_chrome(residue: str) -> bool:
    """Short (<=3 words), starts with an uppercase letter — the shape of an
    axis title / legend header / short label, as opposed to a full sentence."""
    words = residue.split()
    return 1 <= len(words) <= 3 and residue[:1].isupper()


def audit_source(path: Path) -> List[Dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    if "def build_svg" not in text and "def make_" not in text:
        return []  # not a sprezzature-figures generator module
    param_names = _function_param_names(text)
    findings: List[Dict[str, Any]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for match in _TEXT_CONTENT_RE.finditer(line):
            content = match.group(1)
            if "{" not in content and not content.strip():
                continue
            residue = _literal_residue(content)
            if residue in _SAFE_RESIDUES or not _ALPHA_RUN_RE.search(residue):
                continue
            # Already-parameterized case: the residue's own words match a
            # known parameter name (e.g. a generator that literally writes
            # `f'>{prefix}Value</text>'` where `prefix` is itself a param) —
            # heuristic, errs toward reporting rather than silently skipping
            # a real bug, so this only skips an exact single-word match.
            if residue.lower().replace(" ", "_") in param_names:
                continue
            if _looks_like_chrome(residue):
                findings.append(make_finding(
                    "unparameterized-chrome-text", "warning",
                    f'hardcoded axis/legend/unit text {residue!r} in a <text> element — '
                    f"no function parameter overrides it; a caller plotting different data "
                    f"inherits this literally. Add a keyword parameter (see make_columnrange.py "
                    f"y_axis_title/legend_title/unit for the pattern).",
                    str(path), lineno,
                ))
            else:
                findings.append(make_finding(
                    "unparameterized-narrative-text", "info",
                    f'hardcoded annotation text {residue!r} in a <text> element — '
                    f"likely tied to this generator's own demo dataset; consider a caller-"
                    f"overridable parameter if this generator is meant to plot arbitrary data.",
                    str(path), lineno,
                ))
    return findings


def format_human(findings: List[Dict[str, Any]]) -> str:
    if not findings:
        return "clean"
    lines = []
    counts = {"error": 0, "warning": 0, "info": 0}
    for f in findings:
        counts[f["severity"]] += 1
        lines.append(f"  {f['path']}:{f['line']}:1  {f['severity']:<8} {f['rule']:<28} {f['message']}")
    lines.append(f"{counts['error']} error(s), {counts['warning']} warning(s), {counts['info']} info")
    return "\n".join(lines)


def format_json(findings: List[Dict[str, Any]]) -> str:
    import json
    counts = {"errors": 0, "warnings": 0, "info": 0}
    for f in findings:
        key = f["severity"] + ("s" if f["severity"] != "info" else "")
        counts[key] += 1
    return json.dumps({"findings": findings, "summary": counts}, indent=2, ensure_ascii=False)


def iter_files(paths: List[str]) -> List[Path]:
    out: List[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            out.extend(sorted(p.glob("make_*.py")))
        elif p.is_file():
            out.append(p)
    return out


def build_parser():
    parser = make_parser(
        prog="audit_generator_hardcoded_text",
        description=(
            "Static auditor for make_<kind>.py generator SOURCE (not rendered output): "
            "flags axis-title/legend-header/unit text hardcoded as a literal with no "
            "parameter to override it."
        ),
    )
    parser.add_argument("paths", nargs="+", help="make_<kind>.py files, or a directory to scan (scripts/).")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of the human-readable summary.")
    parser.add_argument("--strict", action="store_true", help="Non-zero exit on any warning (chrome-text findings).")
    parser.add_argument("--ignore", default="", help="Comma-separated rule IDs to skip.")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    ignore = {s.strip() for s in args.ignore.split(",") if s.strip()}

    all_findings: List[Dict[str, Any]] = []
    for p in iter_files(args.paths):
        for f in audit_source(p):
            if f["rule"] in ignore:
                continue
            all_findings.append(f)

    print(format_json(all_findings) if args.json else format_human(all_findings))

    warnings = sum(1 for f in all_findings if f["severity"] == "warning")
    if args.strict and warnings > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
