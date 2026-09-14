"""
Reach ``scripts/_textfit.py`` from inside the installed package.

The generators live in ``scripts/`` and import their helpers by bare name;
installed, that directory is mapped to the ``sprezzature_figures_scripts``
distribution. Both layouts have to work — this is the same both-ways import
that ``api.py`` needed before a clean install could find its own scripts.

Author
------
Warith HARCHAOUI <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

try:  # installed layout
    _textfit = importlib.import_module("sprezzature_figures_scripts._textfit")
except ModuleNotFoundError:  # checkout layout
    _scripts = Path(__file__).resolve().parent.parent / "scripts"
    if str(_scripts) not in sys.path:
        sys.path.insert(0, str(_scripts))
    _textfit = importlib.import_module("_textfit")

text_width = _textfit.text_width

__all__ = ["text_width"]
