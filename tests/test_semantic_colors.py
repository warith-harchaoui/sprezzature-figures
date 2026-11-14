"""
Colour = meaning: ``semantic_colors`` reads a label and picks its hue.

The palette's hues each carry a psychological dimension
(<https://deraison.ai/en/colors>): red is danger and warning, blue is
trust and security, green is health and growth. A label that
names one of those gets that hue; anything else keeps the usual cycle, and
the plain cycle itself does not move by a byte.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from sprezzature_figures import semantic_colors, semantic_hue

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import _style  # noqa: E402


@pytest.mark.parametrize(
    "label, hue",
    [
        ("Risque opérationnel", "Red"),
        ("Errors per day", "Red"),
        ("erreurs", "Red"),
        ("Confiance client", "Blue"),
        ("Fiable", "Blue"),
        ("Données sûres", "Blue"),
        ("Santé", "Green"),
        ("Revenue growth", "Green"),
        ("Croissance", "Green"),
        ("Clarté", "Turquoise"),
        ("Innovation", "Orange"),
        ("Prudence", "Yellow"),
        ("Peur", "Purple"),
        ("Autres", "Gray"),
    ],
)
def test_a_label_naming_a_meaning_gets_its_hue(label: str, hue: str) -> None:
    assert semantic_hue(label) == hue


@pytest.mark.parametrize("label", ["Q3", "North", "sur le marché", "Fearless", ""])
def test_a_label_naming_no_meaning_gets_none(label: str) -> None:
    # "sur" is a French preposition, not "sûr"; "fearless" is not fear.
    assert semantic_hue(label) is None


def test_academic_theme_resolves_to_the_academic_palette() -> None:
    colors = semantic_colors(["Risque", "Confiance", "Croissance"], theme="academic")
    assert colors == {"Risque": "#E73121", "Confiance": "#0072B2", "Croissance": "#009E73"}


def test_unmatched_labels_take_the_cycle_minus_the_hues_already_taken() -> None:
    colors = semantic_colors(["Q1", "Trust", "Q2"])
    blue = _style.load_palette()["Blue"]
    assert colors["Trust"] == blue
    # Blue opens the default cycle; it is taken, so the others skip it.
    assert blue not in (colors["Q1"], colors["Q2"])
    assert colors["Q1"] != colors["Q2"]


def test_two_labels_of_one_meaning_stay_distinguishable() -> None:
    colors = semantic_colors(["Risque marché", "Risque crédit"], theme="academic")
    assert colors["Risque marché"] == "#E73121"
    assert colors["Risque crédit"] != "#E73121"


def test_the_plain_cycle_is_unchanged() -> None:
    keys = ["Risk", "Trust", "Growth", "North", "South"]
    assert _style.cycle_hues(keys) == _style.cycle_hues(keys, semantic=False)
    assert _style.cycle_hues(keys)["Risk"] == _style.load_palette()["Blue"]
