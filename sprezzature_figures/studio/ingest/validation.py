"""
Pre-flight checks on an upload before it's read at all (plan §5.4).

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from pathlib import Path

from sprezzature_figures.core.dataset import DataWarning

from .profiler import MAX_UPLOAD_BYTES


def validate_upload_size(
    path: str | Path, *, max_bytes: int = MAX_UPLOAD_BYTES
) -> list[DataWarning]:
    size = Path(path).stat().st_size
    if size > max_bytes:
        return [
            DataWarning(
                message=f"file is {size / 1_000_000:.1f} MB, over the {max_bytes / 1_000_000:.0f} MB limit",
                severity="error",
            )
        ]
    return []
