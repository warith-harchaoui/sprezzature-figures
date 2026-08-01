"""
Isolated per-project workspaces on disk, so a Studio session never writes
into assets/, web/, or whatever directory the process happens to be run
from (plan §8).

Layout::

    ~/.sprezzature-studio/projects/<project-id>/
    ├── manifest.json
    ├── source/
    ├── data/
    ├── iterations/
    │   ├── 0001/
    │   │   ├── plan.json
    │   │   ├── render.svg
    │   │   ├── preview.png
    │   │   ├── critique.json
    │   │   └── event.json
    │   └── 0002/
    └── exports/

The root directory is overridable via the ``SPREZZATURE_STUDIO_HOME``
environment variable (tests use this to avoid touching the real home dir).

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from .rendering import atomic_write_text

_ID_RE = re.compile(r"^[a-z0-9-]+$")


class ProjectManifest(BaseModel):
    project_id: str
    name: str
    created_at: str
    source_name: str = ""
    current_iteration: int = 0


def studio_home() -> Path:
    override = os.environ.get("SPREZZATURE_STUDIO_HOME")
    return Path(override) if override else Path.home() / ".sprezzature-studio"


def projects_root() -> Path:
    return studio_home() / "projects"


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "project"


def create_project(name: str, *, source_name: str = "") -> Path:
    """Create a fresh, isolated project workspace and return its directory.

    The project id is `<slug-of-name>-<8 hex chars>` so it stays
    human-readable in a directory listing while remaining collision-free.
    """
    project_id = f"{_slugify(name)}-{uuid.uuid4().hex[:8]}"
    project_dir = projects_root() / project_id
    for sub in ("source", "data", "iterations", "exports"):
        (project_dir / sub).mkdir(parents=True, exist_ok=True)

    manifest = ProjectManifest(
        project_id=project_id,
        name=name,
        created_at=datetime.now(timezone.utc).isoformat(),
        source_name=source_name,
    )
    save_manifest(project_dir, manifest)
    return project_dir


def load_manifest(project_dir: Path) -> ProjectManifest:
    return ProjectManifest.model_validate_json((project_dir / "manifest.json").read_text(encoding="utf-8"))


def save_manifest(project_dir: Path, manifest: ProjectManifest) -> Path:
    return Path(atomic_write_text(project_dir / "manifest.json", manifest.model_dump_json(indent=2)))


def allocate_iteration_dir(project_dir: Path) -> Path:
    """Create and return the next zero-padded iteration directory
    (0001, 0002, ...), and bump the manifest's `current_iteration`.
    """
    iterations_dir = project_dir / "iterations"
    iterations_dir.mkdir(parents=True, exist_ok=True)
    existing = [int(p.name) for p in iterations_dir.iterdir() if p.is_dir() and p.name.isdigit()]
    next_n = max(existing, default=0) + 1
    iteration_dir = iterations_dir / f"{next_n:04d}"
    iteration_dir.mkdir(parents=True, exist_ok=False)

    manifest = load_manifest(project_dir)
    manifest.current_iteration = next_n
    save_manifest(project_dir, manifest)

    return iteration_dir


def write_iteration_json(iteration_dir: Path, filename: str, payload: dict) -> Path:
    """Atomically write one of an iteration's JSON side-files (plan.json,
    critique.json, event.json, ...).
    """
    return Path(atomic_write_text(iteration_dir / filename, json.dumps(payload, indent=2, default=str)))
