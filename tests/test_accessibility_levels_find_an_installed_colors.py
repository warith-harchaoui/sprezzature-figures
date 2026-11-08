"""A level other than ``universal`` reaches the wheel of sprezzature-colors.

``_style`` looked for the colour engine beside a checkout and in a skill folder.
The wheel installs the same files as ``sprezzature_colors_scripts`` and
``sprezzature_colors_references``, so after ``pip install sprezzature-colors``
every level still drew the universal palette: same bytes, one Python warning.

A checkout next to this one hides the defect, which is why the test takes the
checkout, the skill folders and the environment variable away first.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def style_without_a_checkout(tmp_path, monkeypatch):
    """``_style`` on a machine with a fake colors wheel and nothing else."""
    monkeypatch.setattr(sys, "path", [str(SCRIPTS), str(tmp_path / "site"), *sys.path])
    monkeypatch.delitem(sys.modules, "accessibility_levels", raising=False)
    monkeypatch.delitem(sys.modules, "sprezzature_colors_scripts", raising=False)
    monkeypatch.delitem(sys.modules, "sprezzature_colors_references", raising=False)
    import _style

    scripts = tmp_path / "site" / "sprezzature_colors_scripts"
    references = tmp_path / "site" / "sprezzature_colors_references"
    scripts.mkdir(parents=True)
    references.mkdir()
    (scripts / "__init__.py").write_text("")
    (references / "__init__.py").write_text("")
    (references / "palette.csv").write_text("Name,HEX\n")
    (scripts / "accessibility_levels.py").write_text(
        "def apply_level(palette, level):\n"
        "    return {key: '#123456' for key in palette}\n"
    )
    monkeypatch.delenv("SPREZZATURE_COLORS_PALETTE", raising=False)
    monkeypatch.delenv("FRONT_COLORS_PALETTE", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    monkeypatch.setattr(_style, "__file__", str(tmp_path / "a" / "b" / "c" / "_style.py"))
    yield _style
    sys.modules.pop("accessibility_levels", None)


def test_a_level_is_applied_by_the_installed_wheel(style_without_a_checkout) -> None:
    """With only the wheel present, ``monochrome`` goes through its engine."""
    remapped = style_without_a_checkout._apply_accessibility_level({"x": "#FF0000"}, "monochrome")
    assert remapped == {"x": "#123456"}


def test_the_palette_is_read_from_the_installed_wheel(style_without_a_checkout) -> None:
    """The canonical CSV is found the same way as the engine beside it."""
    assert style_without_a_checkout._sibling_palette_csv().name == "palette.csv"
    assert style_without_a_checkout._sibling_palette_csv().parent.name == (
        "sprezzature_colors_references"
    )
