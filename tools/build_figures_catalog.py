"""
build_figures_catalog — (re)generate sprezzature_figures/catalog/figures.json
from FIGURES.md (kind, category, description) and
docs/studio/generator_audit.json (module, callable, status).

Run `python tools/audit_generators.py --render` first so the audit file is
current, then run this script. Hand-authored enrichment (required_roles for
the currently-stable figures) lives in HAND_ROLES below and is re-applied on
every run, so regenerating from FIGURES.md never silently drops it.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
FIGURES_MD = REPO_ROOT / "FIGURES.md"
AUDIT_JSON = REPO_ROOT / "docs" / "studio" / "generator_audit.json"
OUT_JSON = REPO_ROOT / "sprezzature_figures" / "catalog" / "figures.json"

_ROW_RE = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$")

# Data roles for figures that have already been brought to the stable
# make_<kind>(data, *, out, title) -> Path contract (§3.1 required_roles).
# Every other figure defaults to no declared roles until it is adapted.
HAND_ROLES: dict[str, dict[str, list[dict[str, Any]]]] = {
    "columnrange": {
        "required_roles": [
            {"name": "month", "label": "Category (x-axis)", "accepted_types": ["categorical"], "required": True},
            {"name": "low", "label": "Low value", "accepted_types": ["numeric"], "required": True},
            {"name": "high", "label": "High value", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [
            {"name": "city", "label": "Series / grouping", "accepted_types": ["categorical"], "required": False},
            {"name": "sort", "label": "Sort order", "accepted_types": ["numeric"], "required": False},
        ],
    },
    "funnel": {
        "required_roles": [
            {"name": "stage", "label": "Stage", "accepted_types": ["categorical"], "required": True},
            {"name": "count", "label": "Count", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "sunburst": {
        "required_roles": [
            {"name": "parent", "label": "Parent category", "accepted_types": ["categorical"], "required": True},
            {"name": "name", "label": "Name", "accepted_types": ["categorical"], "required": True},
            {"name": "value", "label": "Value", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "treemap": {
        "required_roles": [
            {"name": "parent", "label": "Parent category", "accepted_types": ["categorical"], "required": True},
            {"name": "name", "label": "Name", "accepted_types": ["categorical"], "required": True},
            {"name": "value", "label": "Value", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "waterfall": {
        "required_roles": [
            {"name": "label", "label": "Label", "accepted_types": ["categorical"], "required": True},
            {"name": "value", "label": "Value (signed)", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [
            {"name": "kind", "label": "Bar kind (total/positive/negative)", "accepted_types": ["categorical"], "required": False},
        ],
    },
    "bar": {
        "required_roles": [
            {"name": "region", "label": "Category", "accepted_types": ["categorical"], "required": True},
            {"name": "value", "label": "Value", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "line": {
        "required_roles": [
            {"name": "month", "label": "Ordinal/temporal axis", "accepted_types": ["categorical", "datetime"], "required": True},
            {"name": "value", "label": "Value", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [
            {"name": "series", "label": "Series / grouping", "accepted_types": ["categorical"], "required": False},
        ],
    },
    "area": {
        "required_roles": [
            {"name": "month", "label": "Ordinal/temporal axis", "accepted_types": ["categorical", "datetime"], "required": True},
            {"name": "visits", "label": "Value", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [
            {"name": "channel", "label": "Series / grouping (stacked)", "accepted_types": ["categorical"], "required": False},
        ],
    },
    "scatter": {
        "required_roles": [
            {"name": "horsepower", "label": "X value", "accepted_types": ["numeric"], "required": True},
            {"name": "mpg", "label": "Y value", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [
            {"name": "segment", "label": "Color grouping", "accepted_types": ["categorical"], "required": False},
            {"name": "weight", "label": "Size", "accepted_types": ["numeric"], "required": False},
        ],
    },
    "histogram": {
        "required_roles": [
            {"name": "score", "label": "Numeric value to bin", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "boxplot": {
        "required_roles": [
            {"name": "department", "label": "Category", "accepted_types": ["categorical"], "required": True},
            {"name": "salary", "label": "Numeric value", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "heatmap": {
        "required_roles": [
            {"name": "day", "label": "Row category", "accepted_types": ["categorical"], "required": True},
            {"name": "hour", "label": "Column category", "accepted_types": ["categorical", "numeric"], "required": True},
            {"name": "activity", "label": "Cell value", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "waffle": {
        "required_roles": [
            {"name": "label", "label": "Category", "accepted_types": ["categorical"], "required": True},
            {"name": "value", "label": "Weight / share", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "donut": {
        "required_roles": [
            {"name": "source", "label": "Category", "accepted_types": ["categorical"], "required": True},
            {"name": "visits", "label": "Weight / share", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "bar-grouped": {
        "required_roles": [
            {"name": "period", "label": "Outer category", "accepted_types": ["categorical"], "required": True},
            {"name": "region", "label": "Inner (grouped) category", "accepted_types": ["categorical"], "required": True},
            {"name": "v", "label": "Numeric value", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "beeswarm": {
        "required_roles": [
            {"name": "group", "label": "Group", "accepted_types": ["categorical"], "required": True},
            {"name": "value", "label": "Numeric value", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "calendar-heatmap": {
        "required_roles": [
            {"name": "week", "label": "Week index", "accepted_types": ["numeric"], "required": True},
            {"name": "day", "label": "Day of week", "accepted_types": ["categorical"], "required": True},
            {"name": "count", "label": "Daily count", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "candlestick": {
        "required_roles": [
            {"name": "day", "label": "Period", "accepted_types": ["numeric", "categorical"], "required": True},
            {"name": "open", "label": "Open", "accepted_types": ["numeric"], "required": True},
            {"name": "close", "label": "Close", "accepted_types": ["numeric"], "required": True},
            {"name": "high", "label": "High", "accepted_types": ["numeric"], "required": True},
            {"name": "low", "label": "Low", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "choropleth": {
        "required_roles": [
            {"name": "id", "label": "ISO-3166-1 numeric country code", "accepted_types": ["categorical"], "required": True},
            {"name": "value", "label": "Numeric value", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "clustermap": {
        "required_roles": [
            {"name": "row", "label": "Row category", "accepted_types": ["categorical"], "required": True},
            {"name": "col", "label": "Column category", "accepted_types": ["categorical"], "required": True},
            {"name": "value", "label": "Cell value", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "dumbbell": {
        "required_roles": [
            {"name": "category", "label": "Category", "accepted_types": ["categorical"], "required": True},
            {"name": "group_a", "label": "First group value", "accepted_types": ["numeric"], "required": True},
            {"name": "group_b", "label": "Second group value", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "sankey": {
        "required_roles": [
            {"name": "source", "label": "Source node", "accepted_types": ["categorical"], "required": True},
            {"name": "target", "label": "Target node", "accepted_types": ["categorical"], "required": True},
            {"name": "value", "label": "Flow volume", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "interruption-matrix": {
        "required_roles": [
            {"name": "interrupter", "label": "Interrupter (cuts in)", "accepted_types": ["categorical"], "required": True},
            {"name": "interrupted", "label": "Interrupted (gets cut off)", "accepted_types": ["categorical"], "required": True},
            {"name": "count", "label": "Number of interruptions", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
}


def parse_figures_md() -> dict[str, dict[str, str]]:
    """kind -> {category, description}, skipping the internal 'figure' dispatcher row."""
    rows: dict[str, dict[str, str]] = {}
    for line in FIGURES_MD.read_text(encoding="utf-8").splitlines():
        m = _ROW_RE.match(line)
        if not m:
            continue
        kind, _script, category, description = m.groups()
        if kind == "figure":
            continue
        rows[kind] = {"category": category, "description": description}
    return rows


def load_audit() -> dict[str, dict[str, Any]]:
    data = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
    return {entry["kind"]: entry for entry in data["generators"]}


def default_aliases(kind: str) -> list[str]:
    aliases = {kind.replace("-", "_"), kind.replace("-", " ")}
    aliases.discard(kind)
    return sorted(aliases)


# Readability limits per stable figure, so the deterministic recommender
# (studio.recommendation.scoring) can tell, e.g., a bar chart of 8 categories
# from one of 800. Values are judgement calls from common dataviz guidance, not
# hard rules: `min_rows` is a hard floor (excludes the figure), the
# `max_recommended_*` are soft (they only lower the score). Kinds absent here
# keep the None defaults.
HAND_LIMITS: dict[str, dict[str, int]] = {
    "bar": {"max_recommended_categories": 25},
    "columnrange": {"max_recommended_categories": 25},
    "dumbbell": {"max_recommended_categories": 20},
    "waterfall": {"max_recommended_categories": 15},
    "funnel": {"max_recommended_categories": 10},
    "waffle": {"max_recommended_categories": 8},
    "donut": {"max_recommended_categories": 6},
    "bar-grouped": {"max_recommended_categories": 8},
    "beeswarm": {"min_rows": 10, "max_recommended_rows": 400},
    "treemap": {"max_recommended_categories": 50},
    "sunburst": {"max_recommended_categories": 50},
    "heatmap": {"max_recommended_categories": 30},
    "sankey": {"max_recommended_categories": 20},
    "scatter": {"min_rows": 3, "max_recommended_rows": 5000},
    "line": {"min_rows": 2, "max_recommended_rows": 2000},
    "area": {"min_rows": 2, "max_recommended_rows": 2000},
    "histogram": {"min_rows": 10},
    "boxplot": {"min_rows": 5, "max_recommended_categories": 20},
}


def build_entry(kind: str, md_row: dict[str, str] | None, audit_entry: dict[str, Any]) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "kind": kind,
        "label": kind.replace("-", " ").replace("_", " ").title(),
        "aliases": default_aliases(kind),
        "category": (md_row or {}).get("category", "Uncategorized"),
        "description": (md_row or {}).get("description", ""),
        "intents": [],
        "status": audit_entry["status"],
        "renderer": audit_entry["renderer"] if audit_entry["renderer"] != "unknown" else "svg",
        "module": f"scripts/{audit_entry['filename']}",
        "callable_name": audit_entry["expected_callable"],
        "required_roles": [],
        "optional_roles": [],
        "supported_outputs": ["svg", "png"],
        "min_rows": None,
        "max_recommended_rows": None,
        "max_recommended_categories": None,
        "default_width": 900,
        "default_height": 600,
        "options_schema": {},
        "warnings": list(audit_entry["errors"]),
    }
    hand = HAND_ROLES.get(kind)
    if hand:
        entry["required_roles"] = hand["required_roles"]
        entry["optional_roles"] = hand["optional_roles"]
    entry.update(HAND_LIMITS.get(kind, {}))
    return entry


def main() -> int:
    md_rows = parse_figures_md()
    audit = load_audit()

    missing_from_md = sorted(set(audit) - set(md_rows))
    missing_from_audit = sorted(set(md_rows) - set(audit))
    if missing_from_md:
        print(f"warning: {len(missing_from_md)} generator(s) undocumented in FIGURES.md: {missing_from_md}")
    if missing_from_audit:
        print(f"warning: {len(missing_from_audit)} FIGURES.md row(s) with no matching generator: {missing_from_audit}")

    entries = [build_entry(kind, md_rows.get(kind), audit_entry) for kind, audit_entry in sorted(audit.items())]

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(entries)} entries to {OUT_JSON.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
