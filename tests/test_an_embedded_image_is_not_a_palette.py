"""
A rainbow is a colormap the markup names, not letters inside a picture.

The ``rainbow-palette`` rule looked for ``jet``, ``hsv`` or ``rainbow`` as
words anywhere in the SVG, case ignored. An embedded raster is base64:
mixed-case letters between slashes and pluses, so sooner or later it spells
one of them with a boundary either side. The relief of the Libya situation
plate held ``/HsV/`` and the gallery test failed it as a rainbow colormap.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "audit_figure", Path(__file__).resolve().parents[1] / "scripts" / "audit_figure.py"
)
assert _SPEC and _SPEC.loader
audit = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(audit)


def _rules(svg: str) -> set[str]:
    return {f["rule"] for f in audit.rules_for_svg(svg, "x.svg")}


def test_base64_that_spells_hsv_is_not_a_rainbow() -> None:
    svg = '<svg><image href="data:image/png;base64,iVBORw0K/HsV/+TAk7x"/></svg>'
    assert "rainbow-palette" not in _rules(svg)


def test_a_named_rainbow_is_still_caught() -> None:
    assert "rainbow-palette" in _rules('<svg><desc>colormap: jet</desc></svg>')
