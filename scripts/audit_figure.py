#!/usr/bin/env python3
"""
audit_figure
============

Static auditor for data-science figures. Reads an SVG chart, or an HTML
file containing ``<figure>`` blocks, and reports the small set of
data-viz mistakes that survive review:

    pie-3d              rainbow-palette     chartjunk
    radius-over-cap     unformatted-tick    iso-date-tick
    role-img-missing    alt-missing

Each finding carries a severity (``error`` / ``warning`` / ``info``).
Exit codes:

* ``0`` — no errors (warnings only or clean).
* ``1`` — one or more errors, or any finding under ``--strict``.
* ``2`` — CLI or parse error.

The auditor is **stdlib + PyYAML** only, with no browser, no model, no
network. SVG and HTML are read with ``xml.etree`` and ``html.parser``.

Every figure in this stack is authored as SVG directly, so the rendered
markup *is* the source: there is no separate chart spec to audit, and
no spec-only rule set to run.

Usage
-----
::

    python audit_figure.py fig.svg                        # human-readable
    python audit_figure.py public/*.html --json           # CI
    python audit_figure.py fig.svg --strict               # warnings → errors
    python audit_figure.py fig.svg --ignore chartjunk

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _argparse import make_parser  # noqa: E402


# ------------------------------------------------------------------
# Finding model
# ------------------------------------------------------------------
def make_finding(rule: str, severity: str, message: str, path: str = "", line: int = 1) -> Dict[str, Any]:
    """Build a finding dict."""
    return {"path": path, "line": line, "rule": rule, "severity": severity, "message": message}


# ------------------------------------------------------------------
# HTML parsing
# ------------------------------------------------------------------
class _FigureScanner(HTMLParser):
    """Collect ``<figure>`` blocks and inner ``<img>`` tags."""

    def __init__(self) -> None:
        """Initialise the ``<figure>`` collector with empty figure list and stack."""
        super().__init__(convert_charrefs=True)
        self.figures: List[Dict[str, Any]] = []
        self._stack: List[Dict[str, Any]] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        """Track ``<figure>`` / ``<figcaption>`` / ``<img>`` openings and their nesting."""
        attr_map = {k.lower(): (v or "") for k, v in attrs}
        if tag == "figure":
            entry = {"role": attr_map.get("role", ""), "has_caption": False, "imgs": [], "line": self.getpos()[0]}
            self.figures.append(entry)
            self._stack.append(entry)
        elif tag == "figcaption" and self._stack:
            self._stack[-1]["has_caption"] = True
        elif tag == "img" and self._stack:
            self._stack[-1]["imgs"].append({"alt": attr_map.get("alt", None), "line": self.getpos()[0]})

    def handle_endtag(self, tag: str) -> None:
        """Pop the current ``<figure>`` off the stack when it closes."""
        if tag == "figure" and self._stack:
            self._stack.pop()


def rules_for_html(text: str, path: str) -> List[Dict[str, Any]]:
    """Scan an HTML document for figure-level a11y and viz sins."""
    findings: List[Dict[str, Any]] = []
    scanner = _FigureScanner()
    scanner.feed(text)
    for fig in scanner.figures:
        if fig["role"] != "img" and not fig["has_caption"]:
            findings.append(make_finding(
                "role-img-missing", "error",
                "<figure> without role=\"img\" and no <figcaption>",
                path, fig["line"],
            ))
        for img in fig["imgs"]:
            if img["alt"] is None:
                findings.append(make_finding(
                    "alt-missing", "error",
                    "<img> inside <figure> has no alt attribute",
                    path, img["line"],
                ))
    return findings


# ------------------------------------------------------------------
# SVG parsing
# ------------------------------------------------------------------
def rules_for_svg(text: str, path: str) -> List[Dict[str, Any]]:
    """Best-effort rules against any SVG chart."""
    findings: List[Dict[str, Any]] = []

    # rainbow palette heuristic
    if re.search(r"\b(jet|hsv|rainbow)\b", text, re.IGNORECASE):
        findings.append(make_finding(
            "rainbow-palette", "error",
            "SVG references a rainbow colormap (jet/hsv/rainbow)",
            path,
        ))

    # chartjunk — shadows / filter blurs
    if "<filter" in text and ("feDropShadow" in text or "feGaussianBlur" in text):
        findings.append(make_finding("chartjunk", "warning", "SVG uses a drop-shadow / blur filter", path))

    # pie-3d — perspective transform
    if re.search(r"transform=\"matrix\([^\"]*perspective", text, re.IGNORECASE):
        findings.append(make_finding("pie-3d", "error", "SVG uses a perspective transform", path))

    # corner policy: no rounding over the xl cap (16px) on any rect/path corner.
    over = sorted({float(m) for m in re.findall(r'rx="([0-9.]+)"', text) if float(m) > 16})
    if over:
        findings.append(make_finding(
            "radius-over-cap", "warning",
            f"rx over the 16px corner cap: {', '.join(f'{v:g}' for v in over)}", path))

    # Tick labels that are raw, unformatted magnitudes: "1000000" instead of
    # "1M" or "1 000 000". Found by eyeballing a real revenue chart whose y-axis
    # read 200000 / 400000 / 600000 — legible only after counting zeros, which
    # is exactly the work a chart is supposed to remove. Five digits is the
    # threshold because four-digit years ("2024") are legitimate tick labels.
    bare = sorted({
        m for m in re.findall(r">\s*(\d{5,})\s*<", text)
        if not (len(m) == 4 and m.startswith(("19", "20")))
    }, key=len, reverse=True)
    if len(bare) >= 3:
        findings.append(make_finding(
            "unformatted-tick", "warning",
            "axis ticks are raw magnitudes with no separator or unit suffix "
            f"({', '.join(bare[:3])}...): a reader has to count digits",
            path))

    # Tick labels left as ISO dates. A time axis reading "2024-07-01" twenty-four
    # times, rotated to fit, is machine output shown to a human: "juil. 2024" or
    # "Jul 2024" carries the same information in half the width.
    iso = re.findall(r">\s*(\d{4}-\d{2}-\d{2})\s*<", text)
    if len(iso) >= 4:
        findings.append(make_finding(
            "iso-date-tick", "warning",
            f"{len(iso)} tick labels are raw ISO dates ({iso[0]}...): format them "
            "for a reader, not for a machine",
            path))

    return findings


# ------------------------------------------------------------------
# Formatting
# ------------------------------------------------------------------
def format_human(findings: List[Dict[str, Any]], kinds: Optional[set] = None) -> str:
    """Human-readable finding summary.

    ``kinds`` carries which input types were actually audited, so a clean
    result can say what it covered. Without it, a bare "clean" reads as
    "audited and fine" when these rules only ever see what the markup
    literally says: a chart can pass every one of them and still encode the
    wrong thing, mislead on scale, or simply look bad. A verification that
    overstates itself is worse than no verification, because it stops the
    reader from looking.
    """
    if not findings:
        if kinds:
            reduced = ", ".join(sorted(kinds))
            return (
                f"no finding among the rules that apply to {reduced}. "
                "These are surface rules read off the markup; no static rule "
                "replaces looking at the image."
            )
        return "clean"
    lines = []
    counts = {"error": 0, "warning": 0, "info": 0}
    for f in findings:
        counts[f["severity"]] += 1
        lines.append(f"  {f['path']}:{f['line']}:1  {f['severity']:<8} {f['rule']:<24} {f['message']}")
    lines.append(f"{counts['error']} error(s), {counts['warning']} warning(s), {counts['info']} info")
    return "\n".join(lines)


def format_json(findings: List[Dict[str, Any]]) -> str:
    """JSON finding summary."""
    counts = {"errors": 0, "warnings": 0, "info": 0}
    for f in findings:
        key = f["severity"] + ("s" if f["severity"] != "info" else "")
        counts[key] += 1
    return json.dumps({"findings": findings, "summary": counts}, indent=2, ensure_ascii=False)


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    """Return the argparse parser for the script."""
    parser = make_parser(
        prog="audit_figure",
        description=(
            "Static auditor for SVG charts, or HTML with <figure> blocks. "
            "Flags the small set of data-viz mistakes that survive review."
        ),
    )
    parser.add_argument("paths", nargs="+", help="Files or directories to audit.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of the human-readable summary.")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors for the exit code.")
    parser.add_argument("--ignore", default="", help="Comma-separated rule IDs to skip.")
    parser.add_argument("--only", default="", help="Comma-separated rule IDs to keep (exclusive with --ignore).")
    return parser


def iter_files(paths: List[str]) -> List[Path]:
    """Expand paths (files or directories) into a flat file list."""
    out: List[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            for suffix in (".svg", ".html", ".htm"):
                out.extend(sorted(p.rglob(f"*{suffix}")))
        elif p.is_file():
            out.append(p)
    return out


def audit_one(path: Path) -> List[Dict[str, Any]]:
    """Dispatch to the right rule set based on file extension."""
    text = path.read_text(encoding="utf-8", errors="replace")
    ext = path.suffix.lower()
    if ext == ".svg":
        return rules_for_svg(text, str(path))
    if ext in (".html", ".htm"):
        return rules_for_html(text, str(path))
    return [make_finding("unsupported-format", "info", f"skipping {ext}", str(path))]


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point."""
    args = build_parser().parse_args(argv)
    ignore = {s.strip() for s in args.ignore.split(",") if s.strip()}
    only = {s.strip() for s in args.only.split(",") if s.strip()}

    all_findings: List[Dict[str, Any]] = []
    # Which input types were seen, so the clean message can state its coverage.
    kinds: set = set()
    for p in iter_files(args.paths):
        kinds.add(p.suffix.lower().lstrip("."))
        findings = audit_one(p)
        for f in findings:
            if only and f["rule"] not in only:
                continue
            if f["rule"] in ignore:
                continue
            all_findings.append(f)

    if args.json:
        print(format_json(all_findings))
    else:
        print(format_human(all_findings, kinds))

    errors = sum(1 for f in all_findings if f["severity"] == "error")
    warnings = sum(1 for f in all_findings if f["severity"] == "warning")
    if errors > 0:
        return 1
    if args.strict and warnings > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
