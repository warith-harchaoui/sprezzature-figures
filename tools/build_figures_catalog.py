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
    "alluvial": {
        "required_roles": [
            {
                "name": "channel",
                "label": "Channel",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "plan", "label": "Plan", "accepted_types": ["categorical"], "required": True},
            {
                "name": "outcome",
                "label": "Outcome",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "count", "label": "Count", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "andrews": {
        "required_roles": [
            {
                "name": "species",
                "label": "Species",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "bill_length",
                "label": "Bill length",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {
                "name": "bill_depth",
                "label": "Bill depth",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {
                "name": "flipper_length",
                "label": "Flipper length",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {
                "name": "body_mass",
                "label": "Body mass",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "arcdiagram": {
        "required_roles": [
            {
                "name": "source",
                "label": "Source",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "target",
                "label": "Target",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "weight", "label": "Weight", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "bar3d": {
        "required_roles": [
            {"name": "team", "label": "Team", "accepted_types": ["categorical"], "required": True},
            {
                "name": "quarter",
                "label": "Quarter",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "spend_k",
                "label": "Spend k",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "bellcurve": {
        "required_roles": [
            {"name": "mean", "label": "Mean", "accepted_types": ["numeric"], "required": True},
            {"name": "std", "label": "Std", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "binned-grid-map": {
        "required_roles": [
            {"name": "lon", "label": "Longitude", "accepted_types": ["numeric"], "required": True},
            {"name": "lat", "label": "Latitude", "accepted_types": ["numeric"], "required": True},
            {"name": "weight", "label": "Weight", "accepted_types": ["numeric"], "required": True},
            {"name": "sigma", "label": "Sigma", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "blandaltman": {
        "required_roles": [
            {"name": "mean", "label": "Mean", "accepted_types": ["numeric"], "required": True},
            {"name": "diff", "label": "Diff", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "bollinger": {
        "required_roles": [
            {"name": "day", "label": "Day", "accepted_types": ["numeric"], "required": True},
            {"name": "close", "label": "Close", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "boxen": {
        "required_roles": [
            {
                "name": "label",
                "label": "Label",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "median", "label": "Median", "accepted_types": ["numeric"], "required": True},
            {"name": "sigma", "label": "Sigma", "accepted_types": ["numeric"], "required": True},
            {"name": "seed", "label": "Seed", "accepted_types": ["numeric"], "required": True},
            {"name": "n", "label": "N", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "bubble": {
        "required_roles": [
            {"name": "name", "label": "Name", "accepted_types": ["categorical"], "required": True},
            {"name": "gdp", "label": "Gdp", "accepted_types": ["numeric"], "required": True},
            {"name": "life", "label": "Life", "accepted_types": ["numeric"], "required": True},
            {"name": "pop", "label": "Pop", "accepted_types": ["numeric"], "required": True},
            {
                "name": "region",
                "label": "Region",
                "accepted_types": ["categorical"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "bullet": {
        "required_roles": [
            {"name": "name", "label": "Name", "accepted_types": ["categorical"], "required": True},
            {"name": "unit", "label": "Unit", "accepted_types": ["categorical"], "required": True},
            {"name": "value", "label": "Value", "accepted_types": ["numeric"], "required": True},
            {"name": "target", "label": "Target", "accepted_types": ["numeric"], "required": True},
            {
                "name": "axis_max",
                "label": "Axis max",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {
                "name": "bands",
                "label": "Bands",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "higher",
                "label": "Higher",
                "accepted_types": ["categorical"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "calibration": {
        "required_roles": [
            {
                "name": "predicted",
                "label": "Predicted",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {
                "name": "observed",
                "label": "Observed",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {"name": "count", "label": "Count", "accepted_types": ["numeric"], "required": True},
            {"name": "gap", "label": "Gap", "accepted_types": ["numeric"], "required": True},
            {"name": "over", "label": "Over", "accepted_types": ["categorical"], "required": True},
        ],
        "optional_roles": [],
    },
    "chord": {
        "required_roles": [
            {
                "name": "author_team",
                "label": "Author team",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "reviewer_team",
                "label": "Reviewer team",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "reviews",
                "label": "Reviews",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "circle-packing": {
        "required_roles": [
            {"name": "path", "label": "Path", "accepted_types": ["categorical"], "required": True},
            {"name": "lines", "label": "Lines", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "confusion-matrix": {
        "required_roles": [
            {
                "name": "actual",
                "label": "Actual",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "predicted",
                "label": "Predicted",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "count", "label": "Count", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "connected-scatter": {
        "required_roles": [
            {"name": "year", "label": "Year", "accepted_types": ["numeric"], "required": True},
            {"name": "gdp", "label": "Gdp", "accepted_types": ["numeric"], "required": True},
            {"name": "co2", "label": "Co2", "accepted_types": ["numeric"], "required": True},
            {
                "name": "label",
                "label": "Label",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "side", "label": "Side", "accepted_types": ["categorical"], "required": True},
        ],
        "optional_roles": [],
    },
    "convex-hull": {
        "required_roles": [
            {
                "name": "segment",
                "label": "Segment",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "spend", "label": "Spend", "accepted_types": ["numeric"], "required": True},
            {"name": "days", "label": "Days", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "cycle": {
        "required_roles": [
            {"name": "key", "label": "Key", "accepted_types": ["categorical"], "required": True},
            {
                "name": "label",
                "label": "Label",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "sub", "label": "Sub", "accepted_types": ["categorical"], "required": True},
            {"name": "months", "label": "Months", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "dendrogram": {
        "required_roles": [
            {"name": "left", "label": "Left", "accepted_types": ["categorical"], "required": True},
            {
                "name": "right",
                "label": "Right",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "height", "label": "Height", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "dependency-wheel": {
        "required_roles": [
            {
                "name": "source",
                "label": "Source",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "target",
                "label": "Target",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "value", "label": "Value", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "difference-chart": {
        "required_roles": [
            {
                "name": "month",
                "label": "Month",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "series",
                "label": "Series",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "value", "label": "Value", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "dotdensity": {
        "required_roles": [
            {
                "name": "department",
                "label": "Department",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "population",
                "label": "Population",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {
                "name": "region",
                "label": "Region",
                "accepted_types": ["categorical"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "dotplot": {
        "required_roles": [
            {"name": "hours", "label": "Hours", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "edge-bundling": {
        "required_roles": [
            {
                "name": "source",
                "label": "Source",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "target",
                "label": "Target",
                "accepted_types": ["categorical"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "elbow": {
        "required_roles": [
            {"name": "k", "label": "K", "accepted_types": ["numeric"], "required": True},
            {
                "name": "inertia",
                "label": "Inertia",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "embedding_projector": {
        "required_roles": [
            {"name": "word", "label": "Word", "accepted_types": ["categorical"], "required": True},
            {
                "name": "cluster",
                "label": "Cluster",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "ci", "label": "Ci", "accepted_types": ["numeric"], "required": True},
            {"name": "x", "label": "X coordinate", "accepted_types": ["numeric"], "required": True},
            {"name": "y", "label": "Y coordinate", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "forest": {
        "required_roles": [
            {
                "name": "label",
                "label": "Label",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "n", "label": "N", "accepted_types": ["numeric"], "required": True},
            {"name": "or_", "label": "Or ", "accepted_types": ["numeric"], "required": True},
            {"name": "lo", "label": "Lo", "accepted_types": ["numeric"], "required": True},
            {"name": "hi", "label": "Hi", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "gapminder": {
        "required_roles": [
            {
                "name": "country",
                "label": "Country",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "continent",
                "label": "Continent",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "year", "label": "Year", "accepted_types": ["numeric"], "required": True},
            {
                "name": "gdpPercap",
                "label": "GdpPercap",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {
                "name": "lifeExp",
                "label": "LifeExp",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {"name": "pop", "label": "Pop", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "gauge": {
        "required_roles": [
            {
                "name": "label",
                "label": "Label",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "sublabel",
                "label": "Sublabel",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "value", "label": "Value", "accepted_types": ["numeric"], "required": True},
            {"name": "unit", "label": "Unit", "accepted_types": ["categorical"], "required": True},
            {
                "name": "settle_from",
                "label": "Settle from",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "hexbin-map": {
        "required_roles": [
            {"name": "lon", "label": "Longitude", "accepted_types": ["numeric"], "required": True},
            {"name": "lat", "label": "Latitude", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "hexmap": {
        "required_roles": [
            {"name": "x", "label": "X coordinate", "accepted_types": ["numeric"], "required": True},
            {"name": "y", "label": "Y coordinate", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "horizon": {
        "required_roles": [
            {
                "name": "label",
                "label": "Label",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "values",
                "label": "Values",
                "accepted_types": ["categorical"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "icicle": {
        "required_roles": [
            {"name": "id", "label": "Node ID", "accepted_types": ["categorical"], "required": True},
            {
                "name": "parent",
                "label": "Parent ID",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "name", "label": "Name", "accepted_types": ["categorical"], "required": True},
            {"name": "ms", "label": "Ms", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "imshow-interpolated": {
        "required_roles": [
            {"name": "x", "label": "X coordinate", "accepted_types": ["numeric"], "required": True},
            {"name": "y", "label": "Y coordinate", "accepted_types": ["numeric"], "required": True},
            {"name": "value", "label": "Value", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "jointplot": {
        "required_roles": [
            {"name": "sleep", "label": "Sleep", "accepted_types": ["numeric"], "required": True},
            {"name": "rt", "label": "Rt", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "liftgain": {
        "required_roles": [
            {"name": "pop", "label": "Pop", "accepted_types": ["numeric"], "required": True},
            {"name": "gain", "label": "Gain", "accepted_types": ["numeric"], "required": True},
            {
                "name": "series",
                "label": "Series",
                "accepted_types": ["categorical"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "liquid-gauge": {
        "required_roles": [
            {
                "name": "metric",
                "label": "Metric",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "label",
                "label": "Label",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "value", "label": "Value", "accepted_types": ["numeric"], "required": True},
            {"name": "median", "label": "Median", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "manhattan": {
        "required_roles": [
            {
                "name": "chromosome",
                "label": "Chromosome",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "position_fraction",
                "label": "Position fraction",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {
                "name": "neg_log10p",
                "label": "Neg log10p",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {"name": "gene", "label": "Gene", "accepted_types": ["categorical"], "required": True},
        ],
        "optional_roles": [],
    },
    "mosaic": {
        "required_roles": [
            {
                "name": "device",
                "label": "Device",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "share", "label": "Share", "accepted_types": ["numeric"], "required": True},
            {
                "name": "method",
                "label": "Method",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "fraction",
                "label": "Fraction",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "network": {
        "required_roles": [
            {
                "name": "source",
                "label": "Source",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "source_label",
                "label": "Source label",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "source_team",
                "label": "Source team",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "target",
                "label": "Target",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "target_label",
                "label": "Target label",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "target_team",
                "label": "Target team",
                "accepted_types": ["categorical"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "org-chart": {
        "required_roles": [
            {"name": "id", "label": "Node ID", "accepted_types": ["categorical"], "required": True},
            {"name": "role", "label": "Role", "accepted_types": ["categorical"], "required": True},
            {
                "name": "headcount",
                "label": "Headcount",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {
                "name": "parent",
                "label": "Parent ID",
                "accepted_types": ["categorical"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "packed-bubble": {
        "required_roles": [
            {"name": "name", "label": "Name", "accepted_types": ["categorical"], "required": True},
            {"name": "share", "label": "Share", "accepted_types": ["numeric"], "required": True},
            {
                "name": "family",
                "label": "Family",
                "accepted_types": ["categorical"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "pairplot": {
        "required_roles": [
            {
                "name": "chemistry",
                "label": "Chemistry",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "density",
                "label": "Density",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {"name": "charge", "label": "Charge", "accepted_types": ["numeric"], "required": True},
            {
                "name": "resistance",
                "label": "Resistance",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {"name": "cycles", "label": "Cycles", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "parallel-sets": {
        "required_roles": [
            {
                "name": "Travel class",
                "label": "Travel class",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "Sex", "label": "Sex", "accepted_types": ["categorical"], "required": True},
            {
                "name": "Age group",
                "label": "Age group",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "Outcome",
                "label": "Outcome",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "count", "label": "Count", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "parcoords": {
        "required_roles": [
            {
                "name": "car_class",
                "label": "Car class",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "mpg", "label": "Mpg", "accepted_types": ["numeric"], "required": True},
            {"name": "hp", "label": "Hp", "accepted_types": ["numeric"], "required": True},
            {"name": "weight", "label": "Weight", "accepted_types": ["numeric"], "required": True},
            {"name": "accel", "label": "Accel", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "pareto": {
        "required_roles": [
            {
                "name": "reason",
                "label": "Reason",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "count", "label": "Count", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "parliament": {
        "required_roles": [
            {
                "name": "party",
                "label": "Party",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "label",
                "label": "Label",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "seats", "label": "Seats", "accepted_types": ["numeric"], "required": True},
            {"name": "hue", "label": "Hue", "accepted_types": ["categorical"], "required": True},
        ],
        "optional_roles": [],
    },
    "pictorial": {
        "required_roles": [
            {
                "name": "label",
                "label": "Label",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "value", "label": "Value", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "polar": {
        "required_roles": [
            {"name": "hour", "label": "Hour", "accepted_types": ["numeric"], "required": True},
            {"name": "count", "label": "Count", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "ppplot": {
        "required_roles": [
            {
                "name": "empirical",
                "label": "Empirical",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {
                "name": "theoretical",
                "label": "Theoretical",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {
                "name": "minutes",
                "label": "Minutes",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "prcurve": {
        "required_roles": [
            {
                "name": "transaction",
                "label": "Transaction",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {
                "name": "is_fraud",
                "label": "Is fraud",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "score_strong",
                "label": "Score strong",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {
                "name": "score_weak",
                "label": "Score weak",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "radar": {
        "required_roles": [
            {"name": "axis", "label": "Axis", "accepted_types": ["categorical"], "required": True},
            {
                "name": "series",
                "label": "Series",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "value", "label": "Value", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "radial-bar": {
        "required_roles": [
            {"name": "hour", "label": "Hour", "accepted_types": ["numeric"], "required": True},
            {"name": "trips", "label": "Trips", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "radial-tree": {
        "required_roles": [
            {"name": "id", "label": "Node ID", "accepted_types": ["categorical"], "required": True},
            {
                "name": "label",
                "label": "Label",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "parent",
                "label": "Parent ID",
                "accepted_types": ["categorical"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "radviz": {
        "required_roles": [
            {
                "name": "variety",
                "label": "Variety",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "Area", "label": "Area", "accepted_types": ["numeric"], "required": True},
            {
                "name": "Perimeter",
                "label": "Perimeter",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {
                "name": "Kernel length",
                "label": "Kernel length",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {
                "name": "Kernel width",
                "label": "Kernel width",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {
                "name": "Compactness",
                "label": "Compactness",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {
                "name": "Asymmetry",
                "label": "Asymmetry",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {
                "name": "Groove length",
                "label": "Groove length",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "residual": {
        "required_roles": [
            {"name": "fitted", "label": "Fitted", "accepted_types": ["numeric"], "required": True},
            {
                "name": "residual",
                "label": "Residual",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "ridgeline": {
        "required_roles": [
            {
                "name": "month",
                "label": "Month",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "mean_c", "label": "Mean c", "accepted_types": ["numeric"], "required": True},
            {
                "name": "spread_c",
                "label": "Spread c",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "rose": {
        "required_roles": [
            {
                "name": "month",
                "label": "Month",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "cause",
                "label": "Cause",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "value", "label": "Value", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "rug": {
        "required_roles": [
            {
                "name": "response_ms",
                "label": "Response ms",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "scatter3d": {
        "required_roles": [
            {
                "name": "cultivar",
                "label": "Cultivar",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "colour_intensity",
                "label": "Colour intensity",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {
                "name": "flavanoid",
                "label": "Flavanoid",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {
                "name": "proline",
                "label": "Proline",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "sfdp-largegraph": {
        "required_roles": [
            {
                "name": "community",
                "label": "Community",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "palette_key",
                "label": "Palette key",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "size", "label": "Size", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "speaking_time": {
        "required_roles": [
            {"name": "name", "label": "Name", "accepted_types": ["categorical"], "required": True},
            {
                "name": "seconds",
                "label": "Seconds",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "spectrogram": {
        "required_roles": [
            {
                "name": "component",
                "label": "Component",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "start_hz",
                "label": "Start hz",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {"name": "end_hz", "label": "End hz", "accepted_types": ["numeric"], "required": True},
            {
                "name": "amplitude",
                "label": "Amplitude",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "spike-map": {
        "required_roles": [
            {"name": "name", "label": "Name", "accepted_types": ["categorical"], "required": True},
            {"name": "lon", "label": "Longitude", "accepted_types": ["numeric"], "required": True},
            {"name": "lat", "label": "Latitude", "accepted_types": ["numeric"], "required": True},
            {
                "name": "population",
                "label": "Population",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "streamgraph": {
        "required_roles": [
            {"name": "year", "label": "Year", "accepted_types": ["numeric"], "required": True},
            {
                "name": "genre",
                "label": "Genre",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "value", "label": "Value", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "streamplot": {
        "required_roles": [
            {
                "name": "component",
                "label": "Component",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "speed_kmh",
                "label": "Speed kmh",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "surface3d": {
        "required_roles": [
            {"name": "x", "label": "X coordinate", "accepted_types": ["numeric"], "required": True},
            {"name": "y", "label": "Y coordinate", "accepted_types": ["numeric"], "required": True},
            {"name": "z", "label": "Z value", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "ternary": {
        "required_roles": [
            {
                "name": "class",
                "label": "Class",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "sand", "label": "Sand", "accepted_types": ["numeric"], "required": True},
            {"name": "silt", "label": "Silt", "accepted_types": ["numeric"], "required": True},
            {"name": "clay", "label": "Clay", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "timeline": {
        "required_roles": [
            {"name": "year", "label": "Year", "accepted_types": ["numeric"], "required": True},
            {"name": "name", "label": "Name", "accepted_types": ["categorical"], "required": True},
            {
                "name": "blurb",
                "label": "Blurb",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "era", "label": "Era", "accepted_types": ["categorical"], "required": True},
        ],
        "optional_roles": [],
    },
    "tree": {
        "required_roles": [
            {"name": "id", "label": "Node ID", "accepted_types": ["categorical"], "required": True},
            {
                "name": "label",
                "label": "Label",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "parent",
                "label": "Parent ID",
                "accepted_types": ["categorical"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "upset": {
        "required_roles": [
            {"name": "sets", "label": "Sets", "accepted_types": ["categorical"], "required": True},
            {"name": "count", "label": "Count", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "variwide": {
        "required_roles": [
            {"name": "name", "label": "Name", "accepted_types": ["categorical"], "required": True},
            {"name": "iso", "label": "Iso", "accepted_types": ["categorical"], "required": True},
            {"name": "pop", "label": "Pop", "accepted_types": ["numeric"], "required": True},
            {
                "name": "gdp_cap",
                "label": "Gdp cap",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {
                "name": "color",
                "label": "Color",
                "accepted_types": ["categorical"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "venn": {
        "required_roles": [
            {"name": "sets", "label": "Sets", "accepted_types": ["categorical"], "required": True},
            {"name": "count", "label": "Count", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "voronoi": {
        "required_roles": [
            {"name": "x", "label": "X coordinate", "accepted_types": ["numeric"], "required": True},
            {"name": "y", "label": "Y coordinate", "accepted_types": ["numeric"], "required": True},
            {
                "name": "chain",
                "label": "Chain",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "name", "label": "Name", "accepted_types": ["categorical"], "required": True},
        ],
        "optional_roles": [],
    },
    "windbarb": {
        "required_roles": [
            {"name": "name", "label": "Name", "accepted_types": ["categorical"], "required": True},
            {"name": "lon", "label": "Longitude", "accepted_types": ["numeric"], "required": True},
            {"name": "lat", "label": "Latitude", "accepted_types": ["numeric"], "required": True},
            {
                "name": "direction",
                "label": "Direction",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {"name": "speed", "label": "Speed", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "windrose": {
        "required_roles": [
            {
                "name": "direction",
                "label": "Direction",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "band", "label": "Band", "accepted_types": ["categorical"], "required": True},
            {"name": "value", "label": "Value", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "wireframe3d": {
        "required_roles": [
            {"name": "x", "label": "X coordinate", "accepted_types": ["numeric"], "required": True},
            {"name": "y", "label": "Y coordinate", "accepted_types": ["numeric"], "required": True},
            {"name": "z", "label": "Z value", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "wordcloud": {
        "required_roles": [
            {"name": "word", "label": "Word", "accepted_types": ["categorical"], "required": True},
            {"name": "count", "label": "Count", "accepted_types": ["numeric"], "required": True},
            {
                "name": "group",
                "label": "Group",
                "accepted_types": ["categorical"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "gapminder_variants": {
        "required_roles": [
            {
                "name": "country",
                "label": "Country",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "continent",
                "label": "Continent",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "year", "label": "Year", "accepted_types": ["numeric"], "required": True},
            {
                "name": "fertility",
                "label": "Fertility",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {
                "name": "lifeExp",
                "label": "LifeExp",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {"name": "pop", "label": "Pop", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "columnrange": {
        "required_roles": [
            {
                "name": "month",
                "label": "Category (x-axis)",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "low", "label": "Low value", "accepted_types": ["numeric"], "required": True},
            {
                "name": "high",
                "label": "High value",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [
            {
                "name": "city",
                "label": "Series / grouping",
                "accepted_types": ["categorical"],
                "required": False,
            },
            {
                "name": "sort",
                "label": "Sort order",
                "accepted_types": ["numeric"],
                "required": False,
            },
        ],
    },
    "funnel": {
        "required_roles": [
            {
                "name": "stage",
                "label": "Stage",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "count", "label": "Count", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "sunburst": {
        "required_roles": [
            {
                "name": "parent",
                "label": "Parent category",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "name", "label": "Name", "accepted_types": ["categorical"], "required": True},
            {"name": "value", "label": "Value", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "treemap": {
        "required_roles": [
            {
                "name": "parent",
                "label": "Parent category",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "name", "label": "Name", "accepted_types": ["categorical"], "required": True},
            {"name": "value", "label": "Value", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "waterfall": {
        "required_roles": [
            {
                "name": "label",
                "label": "Label",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "value",
                "label": "Value (signed)",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [
            {
                "name": "kind",
                "label": "Bar kind (total/positive/negative)",
                "accepted_types": ["categorical"],
                "required": False,
            },
        ],
    },
    "bar": {
        "required_roles": [
            {
                "name": "region",
                "label": "Category",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "value", "label": "Value", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "line": {
        "required_roles": [
            {
                "name": "month",
                "label": "Ordinal/temporal axis",
                "accepted_types": ["categorical", "datetime"],
                "required": True,
            },
            {"name": "value", "label": "Value", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [
            {
                "name": "series",
                "label": "Series / grouping",
                "accepted_types": ["categorical"],
                "required": False,
            },
        ],
    },
    "area": {
        "required_roles": [
            {
                "name": "month",
                "label": "Ordinal/temporal axis",
                "accepted_types": ["categorical", "datetime"],
                "required": True,
            },
            {"name": "visits", "label": "Value", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [
            {
                "name": "channel",
                "label": "Series / grouping (stacked)",
                "accepted_types": ["categorical"],
                "required": False,
            },
        ],
    },
    "scatter": {
        "required_roles": [
            {
                "name": "horsepower",
                "label": "X value",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {"name": "mpg", "label": "Y value", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [
            {
                "name": "segment",
                "label": "Color grouping",
                "accepted_types": ["categorical"],
                "required": False,
            },
            {"name": "weight", "label": "Size", "accepted_types": ["numeric"], "required": False},
        ],
    },
    "histogram": {
        "required_roles": [
            {
                "name": "score",
                "label": "Numeric value to bin",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "boxplot": {
        "required_roles": [
            {
                "name": "department",
                "label": "Category",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "salary",
                "label": "Numeric value",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "heatmap": {
        "required_roles": [
            {
                "name": "day",
                "label": "Row category",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "hour",
                "label": "Column category",
                "accepted_types": ["categorical", "numeric"],
                "required": True,
            },
            {
                "name": "activity",
                "label": "Cell value",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "waffle": {
        "required_roles": [
            {
                "name": "label",
                "label": "Category",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "value",
                "label": "Weight / share",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "donut": {
        "required_roles": [
            {
                "name": "source",
                "label": "Category",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "visits",
                "label": "Weight / share",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "bar-grouped": {
        "required_roles": [
            {
                "name": "period",
                "label": "Outer category",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "region",
                "label": "Inner (grouped) category",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "v",
                "label": "Numeric value",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "beeswarm": {
        "required_roles": [
            {
                "name": "group",
                "label": "Group",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "value",
                "label": "Numeric value",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "calendar-heatmap": {
        "required_roles": [
            {
                "name": "week",
                "label": "Week index",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {
                "name": "day",
                "label": "Day of week",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "count",
                "label": "Daily count",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "candlestick": {
        "required_roles": [
            {
                "name": "day",
                "label": "Period",
                "accepted_types": ["numeric", "categorical"],
                "required": True,
            },
            {"name": "open", "label": "Open", "accepted_types": ["numeric"], "required": True},
            {"name": "close", "label": "Close", "accepted_types": ["numeric"], "required": True},
            {"name": "high", "label": "High", "accepted_types": ["numeric"], "required": True},
            {"name": "low", "label": "Low", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "clustermap": {
        "required_roles": [
            {
                "name": "row",
                "label": "Row category",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "col",
                "label": "Column category",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "value",
                "label": "Cell value",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "corr-matrix": {
        "required_roles": [
            {
                "name": "a",
                "label": "Feature A",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "b",
                "label": "Feature B",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "r",
                "label": "Correlation coefficient",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "ecdf": {
        "required_roles": [
            {
                "name": "latency",
                "label": "Numeric value",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "errorbar": {
        "required_roles": [
            {"name": "g", "label": "Category", "accepted_types": ["categorical"], "required": True},
            {
                "name": "mean",
                "label": "Point estimate",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {
                "name": "lo",
                "label": "Interval low",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {
                "name": "hi",
                "label": "Interval high",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "gantt": {
        "required_roles": [
            {"name": "task", "label": "Task", "accepted_types": ["categorical"], "required": True},
            {
                "name": "start",
                "label": "Start day",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {"name": "end", "label": "End day", "accepted_types": ["numeric"], "required": True},
            {
                "name": "team",
                "label": "Owning team",
                "accepted_types": ["categorical"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "gaussian-process": {
        "required_roles": [
            {"name": "x", "label": "X value", "accepted_types": ["numeric"], "required": True},
            {"name": "y", "label": "Y value", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "hexbin": {
        "required_roles": [
            {"name": "x", "label": "X value", "accepted_types": ["numeric"], "required": True},
            {"name": "y", "label": "Y value", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "kde1d": {
        "required_roles": [
            {
                "name": "x",
                "label": "Numeric value",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "kde2d-contour": {
        "required_roles": [
            {"name": "x", "label": "X value", "accepted_types": ["numeric"], "required": True},
            {"name": "y", "label": "Y value", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "line-multi": {
        "required_roles": [
            {
                "name": "hour",
                "label": "Continuous x value",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {
                "name": "platform",
                "label": "Series",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "sessions",
                "label": "Numeric value",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "lollipop": {
        "required_roles": [
            {"name": "c", "label": "Category", "accepted_types": ["categorical"], "required": True},
            {
                "name": "v",
                "label": "Numeric value",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "population-pyramid": {
        "required_roles": [
            {
                "name": "age",
                "label": "Age band",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "sex",
                "label": "Category",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "pct",
                "label": "Share (%, signed)",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "qqplot": {
        "required_roles": [
            {
                "name": "sample",
                "label": "Numeric value",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "quiver": {
        "required_roles": [
            {"name": "x", "label": "Grid X", "accepted_types": ["numeric"], "required": True},
            {"name": "y", "label": "Grid Y", "accepted_types": ["numeric"], "required": True},
            {
                "name": "fx",
                "label": "Vector X component",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {
                "name": "fy",
                "label": "Vector Y component",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "regression-ci-band": {
        "required_roles": [
            {"name": "x", "label": "X value", "accepted_types": ["numeric"], "required": True},
            {"name": "y", "label": "Y value", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "roc-curve": {
        "required_roles": [
            {
                "name": "score",
                "label": "Predicted score",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {
                "name": "label",
                "label": "True label (0/1)",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "slope": {
        "required_roles": [
            {"name": "item", "label": "Item", "accepted_types": ["categorical"], "required": True},
            {
                "name": "period",
                "label": "Period",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "v",
                "label": "Numeric value",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "stacked-area": {
        "required_roles": [
            {
                "name": "month",
                "label": "Continuous x value",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {
                "name": "service",
                "label": "Series",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "cost",
                "label": "Numeric value",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "stacked-bar": {
        "required_roles": [
            {
                "name": "quarter",
                "label": "Outer category",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "type",
                "label": "Segment",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "share",
                "label": "Numeric value",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "step": {
        "required_roles": [
            {"name": "t", "label": "X value", "accepted_types": ["numeric"], "required": True},
            {"name": "y", "label": "Y value", "accepted_types": ["numeric"], "required": True},
        ],
        "optional_roles": [],
    },
    "strip": {
        "required_roles": [
            {
                "name": "group",
                "label": "Category",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "value",
                "label": "Numeric value",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "survival-km": {
        "required_roles": [
            {
                "name": "arm",
                "label": "Arm / group",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {"name": "t", "label": "Duration", "accepted_types": ["numeric"], "required": True},
            {
                "name": "event",
                "label": "Event occurred (bool)",
                "accepted_types": ["categorical", "numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "violin": {
        "required_roles": [
            {"name": "g", "label": "Category", "accepted_types": ["categorical"], "required": True},
            {
                "name": "y",
                "label": "Numeric value",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "volcano": {
        "required_roles": [
            {
                "name": "lfc",
                "label": "Log2 fold change",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {
                "name": "neglogp",
                "label": "-log10 p-value",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "dumbbell": {
        "required_roles": [
            {
                "name": "category",
                "label": "Category",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "group_a",
                "label": "First group value",
                "accepted_types": ["numeric"],
                "required": True,
            },
            {
                "name": "group_b",
                "label": "Second group value",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "sankey": {
        "required_roles": [
            {
                "name": "source",
                "label": "Source node",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "target",
                "label": "Target node",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "value",
                "label": "Flow volume",
                "accepted_types": ["numeric"],
                "required": True,
            },
        ],
        "optional_roles": [],
    },
    "interruption-matrix": {
        "required_roles": [
            {
                "name": "interrupter",
                "label": "Interrupter (cuts in)",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "interrupted",
                "label": "Interrupted (gets cut off)",
                "accepted_types": ["categorical"],
                "required": True,
            },
            {
                "name": "count",
                "label": "Number of interruptions",
                "accepted_types": ["numeric"],
                "required": True,
            },
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
    """Load `generator_audit.json` (from `tools/audit_generators.py`), keyed by kind."""
    data = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
    return {entry["kind"]: entry for entry in data["generators"]}


def default_aliases(kind: str) -> list[str]:
    """Underscore/space spelling variants of `kind`, for fuzzy lookup (e.g. `"bar-grouped"` -> `["bar grouped", "bar_grouped"]`)."""
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
    "hexbin": {"min_rows": 50, "max_recommended_rows": 20000},
}


def build_entry(
    kind: str, md_row: dict[str, str] | None, audit_entry: dict[str, Any]
) -> dict[str, Any]:
    """Assemble one catalog entry for `kind` from its `FIGURES.md` row and audit result.

    Parameters
    ----------
    kind : str
        The figure kind (e.g. `"bar"`, `"bar-grouped"`).
    md_row : dict or None
        The parsed `FIGURES.md` row for `kind`, if one exists.
    audit_entry : dict
        This kind's entry from :func:`load_audit`.

    Returns
    -------
    dict
        The catalog entry, merging `md_row`, `audit_entry`,
        :data:`HAND_ROLES` and :data:`HAND_LIMITS` for `kind`.
    """
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
    """CLI entry point: regenerate the figures catalog JSON from `FIGURES.md` + the generator audit."""
    md_rows = parse_figures_md()
    audit = load_audit()

    missing_from_md = sorted(set(audit) - set(md_rows))
    missing_from_audit = sorted(set(md_rows) - set(audit))
    if missing_from_md:
        print(
            f"warning: {len(missing_from_md)} generator(s) undocumented in FIGURES.md: {missing_from_md}"
        )
    if missing_from_audit:
        print(
            f"warning: {len(missing_from_audit)} FIGURES.md row(s) with no matching generator: {missing_from_audit}"
        )

    entries = [
        build_entry(kind, md_rows.get(kind), audit_entry)
        for kind, audit_entry in sorted(audit.items())
    ]

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(entries)} entries to {OUT_JSON.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
