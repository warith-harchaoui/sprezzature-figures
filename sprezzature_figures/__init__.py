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
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

from ._textfit_bridge import text_width
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
    # The same calibrated advance table the generators lay out with and the render check
    # measures against. Public because a host application drawing its own figures beside
    # these ones needs to reserve room the same way: measuring differently from the thing
    # that checks you is how a label ends up clipped while every check passes.
    "text_width",
    "redraw",
    "RedrawResult",
]

__version__ = "2.7.0"
__author__ = "Warith HARCHAOUI"
__email__ = "warithmetics@deraison.ai"
