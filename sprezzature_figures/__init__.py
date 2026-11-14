"""
sprezzature_figures — publication-quality data figures.

168 chart types, every one a hand-authored SVG.
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

import sys as _sys
import types as _types
from importlib import import_module
from typing import TYPE_CHECKING, Any

#: Public name -> the submodule that defines it. Loaded on first use, not at
#: import: every console script imports this package first, and loading the
#: catalogue (pydantic), the option models and redraw here made
#: `sprezzature-figures --help` take 0.8 s before it printed a line.
_LAZY: dict[str, str] = {
    "skill_path": "._skill",
    "semantic_colors": "._style_bridge",
    "semantic_hue": "._style_bridge",
    "text_width": "._textfit_bridge",
    "to_dark": ".darkmode",
    "as_rows": ".frames",
    "get_figure_definition": ".make_figure",
    "list_kinds": ".make_figure",
    "make_figure": ".make_figure",
    "validate_figure_input": ".make_figure",
    "FigurePath": ".notebook",
    "RedrawResult": ".redraw",
    "redraw": ".redraw",
    "RenderFinding": ".render_checks",
    "check_render": ".render_checks",
}

if TYPE_CHECKING:
    from ._skill import skill_path
    from ._style_bridge import semantic_colors, semantic_hue
    from ._textfit_bridge import text_width
    from .darkmode import to_dark
    from .frames import as_rows
    from .make_figure import get_figure_definition, list_kinds, make_figure, validate_figure_input
    from .notebook import FigurePath
    from .redraw import RedrawResult, redraw
    from .render_checks import RenderFinding, check_render


def __getattr__(name: str) -> Any:
    """Import a public name from its submodule the first time it is asked for."""
    module = _LAZY.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module, __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY))


class _Package(_types.ModuleType):
    """This package, refusing to let a submodule shadow a public function.

    ``make_figure`` names both a submodule and the function it defines. The
    import system binds a submodule onto its package the first time it loads
    it, so with the names resolved lazily, whoever loaded the submodule first
    replaced the function with the module and ``make_figure(...)`` raised
    "'module' object is not callable".
    """

    def __setattr__(self, name: str, value: Any) -> None:
        if name in _LAZY and isinstance(value, _types.ModuleType):
            return
        super().__setattr__(name, value)


_sys.modules[__name__].__class__ = _Package


__all__ = [
    "skill_path",
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
    # Colour = meaning: a label about risk gets the danger hue, one about trust the
    # trust hue, the rest the usual cycle. A suggestion a caller passes to a figure's
    # own colour option; no figure's default colours change.
    "semantic_colors",
    "semantic_hue",
]

__version__ = "2.14.0"
__author__ = "Warith HARCHAOUI"
__email__ = "warithmetics@deraison.ai"
