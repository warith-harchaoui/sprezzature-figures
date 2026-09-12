"""
sprezzature_figures — publication-quality data figures.

124 chart types, every one a hand-authored SVG.
Every chart is callable as a library function and as a CLI command.
The Ralph Eyeball Loop provides autonomous visual quality feedback.

Author
------
Warith HARCHAOUI <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from .make_figure import get_figure_definition, list_kinds, make_figure, validate_figure_input

__all__ = ["make_figure", "get_figure_definition", "list_kinds", "validate_figure_input"]

__version__ = "2.0.0"
__author__ = "Warith HARCHAOUI"
__email__ = "warith.harchaoui@gmail.com"
