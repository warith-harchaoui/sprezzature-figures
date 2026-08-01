"""
The export archive's manifest.json (plan §14): a summary of what's in the
bundle, independent of the full FigurePlan/IterationRecord detail.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sprezzature_figures.core.figure_plan import FigurePlan
from sprezzature_figures.core.rendering import RenderResult

_LIBRARY_NAME = "sprezzature-figures"


def _library_version() -> str:
    try:
        from importlib.metadata import version

        return version(_LIBRARY_NAME)
    except Exception:  # noqa: BLE001 - version pin is best-effort, never fatal
        return "unknown"


def build_export_manifest(
    *,
    project_name: str,
    plan: FigurePlan,
    render: RenderResult,
) -> dict[str, Any]:
    return {
        "project_name": project_name,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "sprezzature_figures_version": _library_version(),
        "figure_kind": plan.figure_kind,
        "title": plan.title,
        "bindings": {role: binding.columns for role, binding in plan.bindings.items()},
        "renderer": render.metadata.get("renderer"),
        "status": render.metadata.get("status"),
    }
