"""
Reach the colour-meaning helpers of ``scripts/_style.py`` from the package.

The table that maps a label's words to a palette hue lives once, beside the
palette the generators draw with, so a caller asking for a suggestion and a
generator colouring a series can never read two different tables. This is
the same both-ways import as ``_textfit_bridge``: installed, ``scripts/`` is
the ``sprezzature_figures_scripts`` distribution; in a checkout it is a
sibling directory.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

try:  # installed layout
    _style = importlib.import_module("sprezzature_figures_scripts._style")
except ModuleNotFoundError:  # checkout layout
    _scripts = Path(__file__).resolve().parent.parent / "scripts"
    if str(_scripts) not in sys.path:
        sys.path.insert(0, str(_scripts))
    _style = importlib.import_module("_style")

semantic_colors = _style.semantic_colors
semantic_hue = _style.semantic_hue
SEMANTIC_KEYWORDS = _style.SEMANTIC_KEYWORDS

__all__ = ["SEMANTIC_KEYWORDS", "semantic_colors", "semantic_hue"]
