"""
sprezzature_figures — publication-quality data figures.

84+ chart types rendered via Vega-Lite, full Vega, or matplotlib/SVG.
Every chart is callable as a library function and as a CLI command.
The Ralph Eyeball Loop provides autonomous visual quality feedback.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from .make_figure import get_figure_definition, list_kinds, make_figure, validate_figure_input

__all__ = ["make_figure", "get_figure_definition", "list_kinds", "validate_figure_input"]

__version__ = "1.0.0"
__author__ = "Warith Harchaoui"
__email__ = "warith.harchaoui@gmail.com"
