"""
sprezzature_figures.studio.export — reproducible ``.sprezzature.zip``
project archives (plan §14).

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from .alt_text import generate_alt_text
from .bundle import export_project
from .code import generate_reproduce_script
from .images import copy_output_images
from .manifest import build_export_manifest

__all__ = [
    "build_export_manifest",
    "copy_output_images",
    "export_project",
    "generate_alt_text",
    "generate_reproduce_script",
]
