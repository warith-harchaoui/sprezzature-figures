"""
Figure registry: loads sprezzature_figures/catalog/figures.json and resolves
a user-facing kind name (or one of its aliases) to a `FigureDefinition`.

This is what lets `make_figure()` stop guessing a generator's filename and
function name from the kind string. The registry says explicitly which
module and callable back a given kind, so hyphenated names like
`connected-scatter` resolve correctly even though naive
`kind.replace("-", "_")` normalisation would look for the wrong file.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .models import FigureDefinition, FigureStatus

_CATALOG_DIR = Path(__file__).resolve().parent
_DEFAULT_FIGURES_JSON = _CATALOG_DIR / "figures.json"

_registry_cache: list[FigureDefinition] | None = None
_alias_index_cache: dict[str, str] | None = None


def _normalize(name: str) -> str:
    """Collapse whitespace/underscore/hyphen runs to a single hyphen and
    lowercase, so "connected_scatter", "connected scatter" and
    "connected-scatter" all compare equal.
    """
    return re.sub(r"[\s_-]+", "-", name.strip().lower())


def load_registry(path: Path | str | None = None) -> list[FigureDefinition]:
    """Load and validate every FigureDefinition from figures.json.

    Bypasses the module-level cache; use :func:`get_registry` for the cached,
    common case.
    """
    json_path = Path(path) if path is not None else _DEFAULT_FIGURES_JSON
    raw = json.loads(json_path.read_text(encoding="utf-8"))
    return [FigureDefinition.model_validate(entry) for entry in raw]


def get_registry(*, force_reload: bool = False) -> list[FigureDefinition]:
    """Cached figure registry, loaded from the packaged figures.json."""
    global _registry_cache, _alias_index_cache
    if force_reload or _registry_cache is None:
        _registry_cache = load_registry()
        _alias_index_cache = None
    return _registry_cache


def _alias_index() -> dict[str, str]:
    """normalized alias/kind -> canonical kind, built once from the registry."""
    global _alias_index_cache
    if _alias_index_cache is not None:
        return _alias_index_cache
    index: dict[str, str] = {}
    for definition in get_registry():
        index[_normalize(definition.kind)] = definition.kind
        for alias in definition.aliases:
            index.setdefault(_normalize(alias), definition.kind)
    _alias_index_cache = index
    return index


def resolve_kind(name: str) -> str | None:
    """Resolve a user-supplied kind name or alias to the canonical kind, or
    None if nothing in the registry matches.
    """
    return _alias_index().get(_normalize(name))


def get_figure_definition(kind: str) -> FigureDefinition:
    """The FigureDefinition for `kind` (or one of its aliases).

    Raises
    ------
    ValueError
        If no registered figure matches, listing how many are available.
    """
    canonical = resolve_kind(kind)
    if canonical is None:
        available = list_kinds()
        raise ValueError(
            f"No registered figure for kind={kind!r}. "
            f"Available ({len(available)}): {', '.join(available)}"
        )
    by_kind = {d.kind: d for d in get_registry()}
    return by_kind[canonical]


def list_kinds(status: FigureStatus | None = None) -> list[str]:
    """Sorted canonical kind names, optionally filtered by status."""
    defs = get_registry()
    if status is not None:
        defs = [d for d in defs if d.status == status]
    return sorted(d.kind for d in defs)
