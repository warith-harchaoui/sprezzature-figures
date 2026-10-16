"""
sprezzature_figures — publication-quality data figures.

167 chart types, every one a hand-authored SVG.
Every chart is callable as a library function and as a CLI command.
Rows come in as a list of dicts, a pandas / polars / Arrow frame, or a
dict of columns; the path that comes back draws itself in a notebook.
The Ralph Eyeball Loop provides autonomous visual quality feedback.
redraw() takes a picture of somebody else's chart and redraws it here.

Author
------
Warith HARCHAOUI <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from .darkmode import to_dark
from .frames import as_rows
from .make_figure import get_figure_definition, list_kinds, make_figure, validate_figure_input
from .notebook import FigurePath
from .redraw import RedrawResult, redraw
from .render_checks import RenderFinding, check_render

__all__ = [
    "make_figure",
    "get_figure_definition",
    "list_kinds",
    "validate_figure_input",
    "as_rows",
    "FigurePath",
    "to_dark",
    "check_render",
    "RenderFinding",
    "redraw",
    "RedrawResult",
]

__version__ = "2.7.0"
__author__ = "Warith HARCHAOUI"
__email__ = "warith.harchaoui@gmail.com"
