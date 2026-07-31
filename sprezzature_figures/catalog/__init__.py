"""
sprezzature_figures.catalog — the explicit figure registry.

Decouples the user-facing kind name (e.g. "connected-scatter") from the
generator's filename and function name, so the dispatcher in make_figure.py
never has to guess either from string manipulation.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from .models import FigureDefinition, FigureStatus, RendererKind, RoleDefinition, ValidationIssue
from .registry import get_figure_definition, get_registry, list_kinds, resolve_kind

__all__ = [
    "FigureDefinition",
    "FigureStatus",
    "RendererKind",
    "RoleDefinition",
    "ValidationIssue",
    "get_figure_definition",
    "get_registry",
    "list_kinds",
    "resolve_kind",
]
