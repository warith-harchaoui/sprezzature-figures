"""
The figure linter, checked against the SVG everyone else writes.

``check_render`` used to be aimed at this house's own output, where every
figure is hand-authored to one set of conventions: ``font-size`` as an
attribute, no ``dominant-baseline``, text that is text. Pointed at an SVG
from anywhere else it read the geometry wrong in four separate ways and
reported, on a figure with nine real collisions, nothing at all.

So the fixtures below are deliberately *foreign*. They are written by hand
rather than exported, because the exporters that produce them cannot be
test dependencies: this package forbids third-party plotting libraries, and
adding one to draw a fixture would put back exactly what the ban removed.
Each fixture therefore reproduces one documented habit of a real exporter,
named in the test that uses it.

The second half checks the opposite risk. A linter that fires on correct
work gets switched off, and five of the rules here were calibrated against
the 162 figures of this catalogue before being let out -- one of them was
wrong twenty-seven times out of twenty-seven. Those cases are kept as
tests, so the figures that must stay silent stay silent.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from sprezzature_figures import actions, check_render

click = pytest.importorskip("click")
from sprezzature_figures.cli import cli  # noqa: E402

# ── Helpers ──────────────────────────────────────────────────────────────


def _svg(corps: str, largeur: int = 400, hauteur: int = 300, **attrs: str) -> str:
    """A minimal well-formed figure around `corps`, with a title and a desc.

    The accessible-name rule is not what any of these tests is about, so
    every fixture carries the pair it wants and the findings stay about
    the rule under test.
    """
    extra = "".join(f' {nom.replace("_", "-")}="{valeur}"' for nom, valeur in attrs.items())
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {largeur} {hauteur}"'
        f'{extra} role="img" aria-labelledby="t d">'
        f'<title id="t">A figure</title><desc id="d">Something the figure shows.</desc>'
        f"{corps}</svg>"
    )


def _regles(svg: str, **kwargs) -> set[str]:
    """The set of rules that fired, which is what the tests assert on."""
    return {f.check for f in check_render(svg, **kwargs)}


def _de(svg: str, regle: str, **kwargs) -> list:
    return [f for f in check_render(svg, **kwargs) if f.check == regle]


# ── Reading someone else's SVG ───────────────────────────────────────────


def test_un_svg_dont_le_texte_est_vectorise_est_declare_invérifiable() -> None:
    """Glyphs turned into paths: the worst possible pass is a silent one.

    It is the default of at least one widely used exporter, and it leaves
    nothing to check: no ``<text>``, so no rule has anything to say, and a
    caller reading an empty finding list concludes the figure is sound. A
    suite of checks has to be able to say "I could verify nothing"
    distinctly from "I found nothing".
    """
    vectorise = _svg(
        '<g><path d="M10,20 L14,20 L14,8 Z" fill="#1D1D1F"/>'
        '<path d="M20,20 L26,20 L26,8 L20,8 Z" fill="#1D1D1F"/>'
        '<path d="M32,20 L38,20 L38,8 Z" fill="#1D1D1F"/>'
        '<path d="M44,20 L50,20 L50,8 Z" fill="#1D1D1F"/>'
        '<path d="M56,20 L62,20 L62,8 Z" fill="#1D1D1F"/></g>'
    )
    assert "text_as_outlines" in _regles(vectorise)


def test_la_taille_et_l_ancre_ecrites_dans_style_sont_lues() -> None:
    """``style="font-size:…"`` is where most exporters put it.

    This house writes presentation properties as attributes. Reading only
    the attribute found nothing, fell back to a default size, and placed
    every label box somewhere the label was not -- which is why a figure
    with labels plainly on top of each other came back clean.
    """
    chevauchent = _svg(
        '<text x="200" y="100" style="font-size: 13px; text-anchor: middle; '
        'fill: #1D1D1F">Provence-Alpes-Côte d’Azur</text>'
        '<text x="230" y="104" style="font-size: 13px; text-anchor: middle; '
        'fill: #1D1D1F">Bourgogne-Franche-Comté</text>'
    )
    assert "labels_overlap" in _regles(chevauchent)


def test_un_rotate_de_zero_degre_ne_rend_pas_une_etiquette_intouchable() -> None:
    """``rotate(-0 cx cy)`` is written on text that was *not* rotated.

    Rotated labels are excluded from the collision test on purpose -- a
    generator that turns its ticks has already dealt with the crowding.
    Treating the word "rotate" as proof of rotation excluded every
    horizontal tick label of such an export, which is the one population
    that actually runs into its neighbour.
    """
    faux_rotate = _svg(
        '<g transform="rotate(-0 60 100)">'
        '<text x="60" y="100" style="font-size:12px" fill="#000000">1 January 2026</text></g>'
        '<g transform="rotate(-0 90 102)">'
        '<text x="90" y="102" style="font-size:12px" fill="#000000">8 January 2026</text></g>'
    )
    assert "labels_overlap" in _regles(faux_rotate)


def test_une_largeur_en_pourcentage_n_est_pas_une_largeur_en_pixels() -> None:
    """``width="100%"`` with a viewBox: the figure is not a hundred wide.

    Stripping the sign and reading a hundred pixels made a 1400-unit
    figure scale by 1/14, and every label in it became a fraction of a
    pixel tall -- so the legibility floor fired on all of them.
    """
    grand = _svg(
        '<text x="40" y="60" style="font-size:16px" fill="#1D1D1F">Readable at any zoom</text>',
        largeur=1400,
        hauteur=900,
        width="100%",
    )
    assert "text_too_small" not in _regles(grand)


def test_dominant_baseline_milieu_deplace_la_ligne_de_base() -> None:
    """``dominant-baseline`` makes ``y`` an alignment point, not a baseline.

    Four hundred and twenty-two text elements of this catalogue carry one,
    and every one of them was placed a third of a line too high -- enough
    to report a heading as colliding with the subtitle above it.
    """
    propre = _svg(
        '<text x="40" y="40" font-size="18" fill="#6E6E73">A subtitle that runs fairly wide</text>'
        '<text x="200" y="62" font-size="20" text-anchor="middle" '
        'dominant-baseline="middle" fill="#1D1D1F">00:00</text>'
    )
    assert "labels_overlap" not in _regles(propre)


# ── The ink a string actually puts on the canvas ─────────────────────────


def test_un_nombre_n_a_pas_de_jambage_sous_la_ligne_de_base() -> None:
    """ "63 %" set large has nothing below its baseline, and the caption is clear.

    A box hung from the baseline by a flat fraction of the font size
    charged a 150 px figure thirty pixels of descender it never drew, and
    reported it as running into the line underneath.
    """
    jauge = _svg(
        '<text x="200" y="150" font-size="150" text-anchor="middle" fill="#003C7E">63%</text>'
        '<text x="200" y="194" font-size="24" text-anchor="middle" fill="#003C7E">'
        "of usable capacity</text>",
        hauteur=400,
    )
    assert "labels_overlap" not in _regles(jauge)


def test_deux_etiquettes_vraiment_superposees_sont_toujours_signalees() -> None:
    """The ink model is not an excuse to stop reporting collisions."""
    collees = _svg(
        '<text x="200" y="150" font-size="20" text-anchor="middle" fill="#1D1D1F">China</text>'
        '<text x="214" y="154" font-size="20" text-anchor="middle" fill="#1D1D1F">Brazil</text>'
    )
    assert "labels_overlap" in _regles(collees)


def test_une_etiquette_ecrite_deux_fois_au_meme_endroit_est_une_etiquette() -> None:
    """A halo, or a highlight layer, redraws the same string in place.

    The tree figure of this catalogue redraws its root card eleven times,
    once per branch it can light up on hover. Counted as eleven labels,
    they produced fifty-five collisions with themselves.
    """
    halo = _svg(
        '<text x="200" y="150" font-size="19" text-anchor="middle" stroke="#FFFFFF" '
        'stroke-width="3" fill="#1D1D1F">Machine learning</text>'
        '<text x="200" y="150" font-size="19" text-anchor="middle" fill="#1D1D1F">'
        "Machine learning</text>"
    )
    assert "labels_overlap" not in _regles(halo)


# ── Text nobody can see ──────────────────────────────────────────────────


def test_du_blanc_sur_une_carte_blanche_est_signale() -> None:
    """The case the rule exists for: a label that is simply not there."""
    invisible = _svg(
        '<rect x="0" y="0" width="400" height="300" fill="#FFFFFF"/>'
        '<rect x="40" y="40" width="200" height="60" fill="#FFFFFF"/>'
        '<text x="140" y="75" font-size="16" text-anchor="middle" fill="#FFFFFF">Total</text>'
    )
    trouve = _de(invisible, "text_invisible_on_background")
    assert trouve and "#FFFFFF" in trouve[0].detail


def test_du_blanc_dans_une_barre_sombre_est_lisible_et_se_tait() -> None:
    """White on white *against the canvas*, and perfectly legible in fact.

    Comparing a label with the canvas instead of with the mark it sits on
    fired on twenty-seven figures of this catalogue, every one of them
    correctly drawn. What is behind the label is what decides.
    """
    lisible = _svg(
        '<rect x="0" y="0" width="400" height="300" fill="#FFFFFF"/>'
        '<rect x="40" y="40" width="200" height="60" fill="#1D1D1F"/>'
        '<text x="140" y="75" font-size="16" text-anchor="middle" fill="#FFFFFF">74</text>'
    )
    assert "text_invisible_on_background" not in _regles(lisible)


def test_un_chemin_rempli_par_dessus_fait_renoncer_la_regle() -> None:
    """A pie slice is a ``<path>``, and its extent is not read from here.

    The bias of a linter is to under-report: an answer it cannot work out
    from the markup is one it must not invent. Pie, sunburst and
    streamgraph all put their labels on paths.
    """
    tranche = _svg(
        '<rect x="0" y="0" width="400" height="300" fill="#FFFFFF"/>'
        '<path d="M200,150 L200,40 A110,110 0 0,1 310,150 Z" fill="#0A84FF"/>'
        '<text x="240" y="110" font-size="14" fill="#FFFFFF">Coal</text>'
    )
    assert "text_invisible_on_background" not in _regles(tranche)


def test_un_aplat_semi_transparent_fait_renoncer_la_regle() -> None:
    """The colour under the glyph is a blend, written nowhere in the markup."""
    voile = _svg(
        '<rect x="0" y="0" width="400" height="300" fill="#FFFFFF"/>'
        '<rect x="40" y="40" width="200" height="60" fill="#FFFFFF" fill-opacity="0.4"/>'
        '<text x="140" y="75" font-size="16" text-anchor="middle" fill="#FFFFFF">Total</text>'
    )
    assert "text_invisible_on_background" not in _regles(voile)


# ── Rules that fire nowhere in this catalogue ────────────────────────────


def test_des_graduations_arrondies_jusqu_a_se_confondre_sont_signalees() -> None:
    """Three neighbours rounded until they read the same hide the variation.

    Nothing in the catalogue triggers it, which is why it is tested on a
    built case: a rule never exercised is a rule nobody knows works.
    """
    aplaties = _svg(
        '<text x="40" y="200" font-size="12" fill="#6E6E73">1.2</text>'
        '<text x="120" y="200" font-size="12" fill="#6E6E73">1.2</text>'
        '<text x="200" y="200" font-size="12" fill="#6E6E73">1.2</text>'
        '<text x="280" y="200" font-size="12" fill="#6E6E73">1.3</text>'
    )
    assert "identical_adjacent_labels" in _regles(aplaties)


def test_une_ligne_finissant_sur_une_elision_est_un_avertissement() -> None:
    """House charter: never end a wrapped line on "l'" or on "of the"."""
    orphelin = _svg(
        '<text x="40" y="60" font-size="14" fill="#1D1D1F">'
        '<tspan x="40">Part de marché de l’</tspan>'
        '<tspan x="40" dy="18">entreprise en 2026</tspan></text>'
    )
    trouve = _de(orphelin, "line_end_orphan")
    assert trouve and trouve[0].severity == "warning"


def test_un_defaut_de_charte_n_a_pas_la_meme_gravite_qu_un_defaut_de_figure() -> None:
    """``severity`` separates "wrong for anyone" from "wrong for us".

    A gate that blocks on both is a gate people switch off, so the two are
    told apart at the source and the caller decides what it refuses.
    """
    minuscule = _svg('<text x="40" y="60" font-size="8" fill="#1D1D1F">Barely there</text>')
    trouve = _de(minuscule, "text_too_small")
    assert trouve and trouve[0].severity == "warning"
    coupe = _svg('<text x="380" y="60" font-size="14" fill="#1D1D1F">Clipped on the right</text>')
    assert _de(coupe, "text_outside_canvas")[0].severity == "error"


# ── Degenerate input ─────────────────────────────────────────────────────


def test_un_rendu_vide_et_un_rendu_malforme_sont_dits_tels() -> None:
    assert _regles("") == {"empty_render"}
    assert _regles("<svg><text>unclosed") == {"invalid_svg"}


# ── The machine-readable answer ──────────────────────────────────────────


def test_la_sortie_json_porte_la_regle_la_gravite_et_le_compte() -> None:
    """``--format json`` is for a caller that acts, not for a reader.

    The prose form says the same things and is the default, but a gate
    that wants to block on errors and merely log warnings should not have
    to parse sentences to tell them apart. Both severities are always
    counted, even at zero: a key that appears only when something is
    wrong turns every reader into a ``.get(..., 0)``.
    """
    faute = _svg('<text x="380" y="60" font-size="14" fill="#1D1D1F">Clipped on the right</text>')
    with TemporaryDirectory() as dossier:
        chemin = Path(dossier) / "figure.svg"
        chemin.write_text(faute, encoding="utf-8")
        result = actions.check(str(chemin), fmt="json")
    rapport = json.loads("\n".join(result.out))
    assert result.code == 1 and not result.err, "the JSON belongs on stdout, whole"
    assert rapport["ok"] is False
    assert rapport["counts"] == {"error": 1, "warning": 0}
    assert rapport["findings"][0]["check"] == "text_outside_canvas"
    assert rapport["findings"][0]["severity"] == "error"


def test_les_deux_lignes_de_commande_offrent_le_meme_drapeau() -> None:
    """``check`` is one command with two spellings; a flag lands on both."""
    from click.testing import CliRunner

    from sprezzature_figures.make_figure import _verb_check

    aide = CliRunner().invoke(cli, ["check", "--help"]).output
    assert "--format" in aide and "json" in aide

    tampon = io.StringIO()
    with contextlib.redirect_stdout(tampon), pytest.raises(SystemExit):
        _verb_check(["--help"])
    assert "--format" in tampon.getvalue()
