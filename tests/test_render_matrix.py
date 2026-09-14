"""Rendered-figure matrix: simulated business data, every compatible kind, checked.

WHY THIS SUITE EXISTS. The Ralph Eyeball Loop answers "does this render
read?" by showing the PNG to a vision model. A service without a vision
backend has no such recourse, and still ships figures to its users. For it,
legibility has to be a property of the code, verified before anything is
rendered in anger.

So this suite renders the catalogue the way an application does — take rows,
profile them, let the library recommend compatible kinds, bind columns to
roles, render — over datasets that reproduce the shapes real callers send,
including the ones that BROKE in production: identifiers long enough to
collide on an axis, more categories than an axis can hold, French labels
with accents, decimals from a database driver.

Every render then goes through :func:`sprezzature_figures.check_render`,
which reports the factual defects an eyeball would catch: overlapping
labels, text off the canvas, demo chrome over real data, a light card left
on a dark figure, an ignored title.

A failure here is a real defect: either a generator or the check. Both are
worth knowing about before a user sees the figure.

Author
------
Warith HARCHAOUI <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from sprezzature_figures import check_render, make_figure
from sprezzature_figures.studio.ingest.profiler import profile_dataframe
from sprezzature_figures.studio.recommendation import assign_columns, recommend_figures

pd = pytest.importorskip("pandas", reason="the matrix profiles data through pandas")


# ── Les jeux simulés ────────────────────────────────────────────────────────
#
# Chacun reproduit une forme que les appelants envoient réellement, et porte
# le défaut qu'elle a produit quand elle est arrivée pour la première fois.

_JEUX: dict[str, list[dict[str, object]]] = {
    # Comparaison simple : le cas nominal, étiquettes courtes.
    "categories_courtes": [
        {"region": nom, "value": valeur}
        for nom, valeur in (("Nord", 52257), ("Sud", 27828), ("Est", 26119), ("Ouest", 25956))
    ],
    # Le cas qui a cassé : des identifiants techniques, longs et nombreux,
    # imprimés les uns sur les autres sous l'axe.
    "identifiants_longs": [
        {"region": f"cust_{i:08d}", "value": 50000 - i * 1700} for i in range(23)
    ],
    # Français accentué : rien ne doit déborder ni se tronquer.
    "libelles_francais": [
        {"region": nom, "value": valeur}
        for nom, valeur in (
            ("Ressources humaines", 18400),
            ("Qualité", 15230),
            ("Développement", 22100),
            ("Achats", 9800),
        )
    ],
    # Série temporelle mensuelle, telle qu'un GROUP BY par mois la rend.
    "serie_mensuelle": [
        {"month": f"2026-{mois:02d}", "value": 12000 + mois * 830} for mois in range(1, 13)
    ],
    # Décimales de pilote de base de données, et un total qui ne tombe pas juste.
    "montants_decimaux": [
        {"region": nom, "value": valeur}
        for nom, valeur in (("Logiciel", 12345.67), ("Conseil", 8765.43), ("Support", 4321.09))
    ],
    # Deux mesures : nuage de points, corrélations, quadrants.
    "deux_mesures": [
        {"x": 10 + i * 3, "y": 45 - i * 2, "value": 100 + i * 7, "region": f"seg{i}"}
        for i in range(12)
    ],
}

#: Un jeu qui n'engendre aucun candidat stable ne prouve rien : ce serait un
#: test qui passe en ne testant rien. On exige donc un minimum de couverture.
_CANDIDATS_MINIMUM = 2

#: Combien de types différents la matrice doit exercer AU TOTAL. Le chiffre
#: n'est pas un objectif de score : il garde la suite honnête le jour où une
#: régression du moteur de recommandation réduirait la liste à trois types
#: sans que rien n'échoue par ailleurs.
_TYPES_MINIMUM = 8


def _rendus(nom_jeu: str, lignes: list[dict[str, object]], *, limite: int = 6):
    """Rend chaque type compatible avec ``lignes``, comme le ferait une application.

    Reproduit le chemin réel : profilage, recommandation (types stables
    seulement), liaison des colonnes aux rôles, rendu. Les types dont la
    liaison échoue sont écartés silencieusement, comme en production.
    """
    profil = profile_dataframe(
        pd.DataFrame(lignes), dataset_id=nom_jeu, fingerprint=nom_jeu, source_name="test-matrix"
    )
    for definition in recommend_figures(profil, limit=limite, status="stable"):
        liaison = assign_columns(definition, profil) or {}
        if not liaison:
            continue
        liees = [{**ligne, **{role: ligne[colonne] for role, colonne in liaison.items()}}
                 for ligne in lignes]
        yield definition.kind, liees


@pytest.mark.parametrize("langue", ["fr", "en"])
@pytest.mark.parametrize("nom_jeu", sorted(_JEUX))
def test_chaque_type_compatible_rend_une_figure_lisible(nom_jeu: str, langue: str) -> None:
    """Rendu clair : aucun défaut factuel sur aucun type compatible.

    Les deux langues sont exercées, et pas seulement par acquit de
    conscience : une phrase traduite est presque toujours plus longue que
    l'originale, donc c'est en français que les débordements et les
    chevauchements se produisent d'abord.
    """
    lignes = _JEUX[nom_jeu]
    vus = 0
    with tempfile.TemporaryDirectory() as dossier:
        for kind, liees in _rendus(nom_jeu, lignes):
            vus += 1
            sortie = Path(dossier) / f"{kind}.svg"
            make_figure(kind, liees, out=str(sortie), title="Ventes par segment", language=langue)
            defauts = check_render(sortie.read_text(encoding="utf-8"))
            assert not defauts, f"{nom_jeu} / {kind} : " + " | ".join(str(d) for d in defauts)
    assert vus >= _CANDIDATS_MINIMUM, f"{nom_jeu} n'a produit que {vus} type(s) compatible(s)"


@pytest.mark.parametrize("langue", ["fr", "en"])
@pytest.mark.parametrize("nom_jeu", sorted(_JEUX))
def test_le_mode_sombre_ne_laisse_aucune_surface_claire(nom_jeu: str, langue: str) -> None:
    """Rendu sombre : mêmes règles, plus celles du fond sombre.

    C'est le mode que sert un portail à fond sombre, donc celui où un
    panneau clair oublié se voit le plus.
    """
    lignes = _JEUX[nom_jeu]
    with tempfile.TemporaryDirectory() as dossier:
        for kind, liees in _rendus(nom_jeu, lignes):
            sortie = Path(dossier) / f"{kind}.svg"
            make_figure(
                kind, liees, out=str(sortie), title="Ventes par segment",
                language=langue, dark=True,
            )
            defauts = check_render(sortie.read_text(encoding="utf-8"), dark=True)
            assert not defauts, f"{nom_jeu} / {kind} (sombre) : " + " | ".join(str(d) for d in defauts)


def test_la_matrice_couvre_un_eventail_de_types_et_pas_trois_fois_le_meme() -> None:
    """Une matrice qui n'exercerait qu'un type passerait sans rien prouver."""
    types: set[str] = set()
    for nom_jeu, lignes in _JEUX.items():
        types.update(kind for kind, _ in _rendus(nom_jeu, lignes))
    assert len(types) >= _TYPES_MINIMUM, f"seulement {len(types)} types exercés : {sorted(types)}"


def test_un_titre_demande_se_retrouve_sur_la_figure() -> None:
    """Le paramètre ``title`` n'est pas décoratif : il doit atteindre le rendu.

    Un générateur qui l'accepte pour la forme et écrit le sien produit une
    figure titrée par autre chose que ce que l'appelant a demandé — constaté
    sur un Pareto, corrigé, et gardé ici pour tous les types.
    """
    titre = "Chiffre d'affaires par client"
    manquants: list[str] = []
    with tempfile.TemporaryDirectory() as dossier:
        for kind, liees in _rendus("categories_courtes", _JEUX["categories_courtes"]):
            sortie = Path(dossier) / f"{kind}.svg"
            make_figure(kind, liees, out=str(sortie), title=titre, language="fr")
            defauts = check_render(sortie.read_text(encoding="utf-8"), expected_title=titre)
            if any(d.check == "title_ignored" for d in defauts):
                manquants.append(kind)
    assert not manquants, f"types qui ignorent le titre demandé : {manquants}"


# ── La langue du chrome ─────────────────────────────────────────────────────

#: Un témoin par type localisé le 14/09/2026, dans chaque langue. Le mot
#: choisi est du CHROME (légende, titre d'axe, annotation), jamais une donnée :
#: c'est le chrome qui restait en anglais sous une figure française.
_TEMOINS = {
    "beeswarm": {"fr": "Groupe ", "en": "Group "},
    "bellcurve": {"fr": "Densité de probabilité", "en": "Probability density"},
    "blandaltman": {"fr": "Biais", "en": "Bias"},
    "bollinger": {"fr": "Bande haute", "en": "Upper band"},
    "dotplot": {"fr": "Dans la cible", "en": "Within target"},
    "ecdf": {"fr": "Part cumulée", "en": "Cumulative share"},
    "histogram": {"fr": "Note d'examen", "en": "Exam score"},
}

_DONNEES_TEMOINS = {
    "beeswarm": [{"group": f"g{i}", "value": 10 + i} for i in range(4)],
    "bellcurve": [{"mean": 70, "std": 8}],
    "blandaltman": [{"mean": 10 + i * 3, "diff": 5 - i * 0.4} for i in range(12)],
    "bollinger": [{"day": i, "close": 100 + (i % 7) * 2.5} for i in range(30)],
    "dotplot": [{"hours": v} for v in (1.2, 2.4, 3.1, 5.5, 6.2)],
    "ecdf": [{"latency": v} for v in (2, 5, 9, 12, 18, 25, 40)],
    "histogram": [{"score": v} for v in (2, 5, 9, 12, 18, 25, 40, 44, 50, 55)],
}


@pytest.mark.parametrize("kind", sorted(_TEMOINS))
def test_le_chrome_suit_la_langue_demandee(kind: str) -> None:
    """Une figure demandée en français ne doit pas porter de chrome anglais.

    Ces sept générateurs écrivaient leur chrome en anglais quoi qu'on leur
    demande : « Value » sous un axe, « Within target » dans une légende,
    « Upper band » au bout d'une courbe. Sur un produit servi en français,
    c'est visible au premier coup d'œil.
    """
    lignes = _DONNEES_TEMOINS[kind]
    with tempfile.TemporaryDirectory() as dossier:
        for langue, attendu in _TEMOINS[kind].items():
            sortie = Path(dossier) / f"{kind}-{langue}.svg"
            make_figure(kind, lignes, out=str(sortie), language=langue)
            rendu = sortie.read_text(encoding="utf-8")
            assert attendu in rendu, f"{kind} en {langue} : « {attendu} » attendu"
            autre = _TEMOINS[kind]["en" if langue == "fr" else "fr"]
            assert autre not in rendu, f"{kind} en {langue} : « {autre} » ne devrait pas y être"


def test_le_verificateur_mesure_comme_les_generateurs() -> None:
    """
    La largeur d'un texte vient de ``_textfit``, pas d'un ratio plat.

    Le module estimait d'abord chaque texte à ``len(texte) × taille × 0.52``.
    Sur le standfirst du graphique en barres de démonstration — « The North
    brings in nearly four times what the West does », 26 px — cela donnait
    757 px là où Roboto en rend 640, et la figure était déclarée débordante
    d'un canevas où elle tient avec 65 px de marge.

    Un vérificateur qui mesure autrement que ce qu'il vérifie invente des
    défauts, et un faux positif détruit exactement ce qui fait la valeur du
    module : qu'un échec vaille la peine qu'on s'en occupe. Il utilise
    maintenant la table calibrée par caractère dont les générateurs se servent
    pour composer, si bien qu'une chaîne que le générateur a fait tenir ne peut
    plus être signalée ici.
    """
    from sprezzature_figures.render_checks import _text_width

    texte = "The North brings in nearly four times what the West does"
    largeur = _text_width(texte, 26)

    # Mesuré sur les vraies métriques de la Roboto embarquée : 639.6 px.
    assert 600 <= largeur <= 660, (
        f"{largeur:.1f} px pour un texte que Roboto rend à 639.6 px. "
        "En dessous, le vérificateur rate des débordements ; au-dessus, il en "
        "invente — c'est ce qu'a fait le ratio plat de 0.52 (757 px)."
    )
    assert largeur < 705, (
        "le standfirst du graphique de démonstration doit tenir dans les 705 px "
        "disponibles, sinon la figure de référence est signalée comme cassée"
    )
