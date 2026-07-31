# sprezzature-figures

🇫🇷 LISEZMOI.md · 🇬🇧 [README.md](README.md)

[![Python ≥3.10](https://img.shields.io/badge/python-%3E%3D3.10-blue)](https://www.python.org/)
[![Licence : BSD-3-Clause](https://img.shields.io/badge/licence-BSD--3--Clause-green)](LICENSE)

[![logo](assets/logo.png)](https://harchaoui.org/warith/sprezzature/)

83 types de graphiques de qualité publication — Vega-Lite, Vega complet et matplotlib/SVG — utilisables comme bibliothèque Python ou en ligne de commande.

Fait partie de la suite [sprezzature](https://harchaoui.org/warith/sprezzature/).

---

## Installation

```bash
pip install sprezzature-figures
```

Avec l'interface Click (optionnelle) :

```bash
pip install "sprezzature-figures[cli]"
```

---

## Démarrage rapide

### En bibliothèque

```python
from sprezzature_figures import make_figure

donnees = [
    {"parent": "Marketing",    "name": "Recherche payante", "value": 42},
    {"parent": "Marketing",    "name": "Social",            "value": 28},
    {"parent": "Ingénierie",   "name": "Plateforme",        "value": 19},
    {"parent": "Ingénierie",   "name": "Mobile",            "value": 11},
]
chemin = make_figure("treemap", donnees, out="budget.png", title="Budget par équipe")
print(chemin)  # PosixPath('budget.png')
```

`make_figure()` accepte n'importe quel type enregistré, mais seuls les types
`status="stable"` sont aujourd'hui vérifiés par rendu — voir
[docs/studio/GENERATOR_AUDIT.md](docs/studio/GENERATOR_AUDIT.md) pour le
statut de chacun des 83 types, et `make-figure --list --status stable` pour
la liste de ceux qui fonctionnent dès maintenant.

### En ligne de commande

```bash
# Lister tous les types de graphiques disponibles (--status stable pour ceux vérifiés par rendu)
make-figure --list

# Générer un graphique avec ses données de démonstration intégrées
make-figure treemap --out budget.png --title "Décomposition du budget"
make-figure funnel --out entonnoir.png
make-figure waterfall --out cascade.png
```

---

## Catalogue des graphiques

83 types de graphiques dans 19 catégories. Voir [FIGURES.md](FIGURES.md) pour le tableau complet.

| Catégorie | Graphiques |
|-----------|------------|
| Comparaison | bar3d, bullet, columnrange, dotplot, dumbbell, pareto, variwide |
| Composition | circle-packing, mosaic, packed-bubble, parliament, pictorial, sunburst, treemap, waffle |
| Distribution | andrews, bellcurve, boxen, jointplot, pairplot, ridgeline, rug |
| Flux | alluvial, chord, dependency-wheel, funnel, parallel-sets, sankey, streamgraph |
| Géospatial | binned-grid-map, dotdensity, globe3d, hexbin-map, hexmap, situation_map, spike-map, voronoi |
| Hiérarchie | dendrogram, icicle, org-chart, radial-tree, tree |
| KPI | gauge, liquid-gauge |
| Météorologie | windbarb, windrose |
| Évaluation de modèles | calibration, liftgain, prcurve |
| Réseau | arcdiagram, edge-bundling, network, sfdp-largegraph |
| Régression | blandaltman, ppplot, residual |
| Signal | spectrogram |
| Texte | wordcloud |
| 3D | scatter3d, wireframe3d |
| Série temporelle | bollinger, connected-scatter, difference-chart, horizon, streamplot, timeline |
| Multivarié | convex-hull, embedding_projector, polar, radar, radial-bar, radviz, ternary, venn, upset |
| Méta-analyse | forest |
| Animé | gapminder |
| Autre | rose, speaking_time |

---

## Architecture

```
sprezzature-figures/
├── sprezzature_figures/
│   ├── __init__.py        # exporte make_figure, list_kinds, get_figure_definition
│   ├── make_figure.py     # répartiteur adossé au registre + CLI argparse
│   ├── cli.py             # point d'entrée Click (optionnel, extra [cli])
│   └── catalog/           # registre des figures : FigureDefinition + figures.json
├── scripts/
│   ├── make_treemap.py            # script autonome par type de graphique
│   ├── make_connected-scatter.py  # les types avec tiret sont supportés
│   └── ...                        # 83 scripts make_*.py au total
├── assets/
│   ├── vega-examples/     # spécifications Vega-Lite et Vega
│   └── svg-examples/      # gabarits SVG
├── references/            # documentation des sources de référence
└── tests/
```

Chaque script `make_<type>.py` est autonome : il importe ce dont il a besoin, définit `make_<type>(donnees, *, out=None, title="", ...) -> Path` et expose une liste `DEMO_DATA` pour la CLI et les tests. `make_figure()` résout le type via `sprezzature_figures/catalog/figures.json` plutôt que de deviner le nom de fichier — voir [docs/studio/GENERATOR_AUDIT.md](docs/studio/GENERATOR_AUDIT.md) pour savoir lesquels des 83 scripts respectent déjà ce contrat.

---

## Ajouter un type de graphique

1. Créer `scripts/make_<type>.py` en suivant le schéma d'un script existant.
2. Exposer `DEMO_DATA: list[dict]` et une fonction `make_<type>(donnees, *, out=None, title="", ...) -> Path`.
3. Ajouter une ligne dans [FIGURES.md](FIGURES.md).
4. Lancer `python tools/audit_generators.py --render` puis `python tools/build_figures_catalog.py` pour l'enregistrer dans `sprezzature_figures/catalog/figures.json` (sans cela, `make_figure()` ne l'atteint que via un repli déprécié qui affiche un avertissement).
5. Vérifier avec `make-figure <type>`.

---

## Développement

```bash
git clone https://github.com/warith-harchaoui/sprezzature-figures.git
cd sprezzature-figures
pip install -e ".[dev,cli]"
ruff check sprezzature_figures/
python -m pytest tests/ -q
```

Tests de rendu (nécessitent un affichage ou vl-convert) :

```bash
python -m pytest -m slow tests/
```

---

## Licence

BSD 3-Clause — voir [LICENSE](LICENSE).

## Auteur

Warith Harchaoui — warith.harchaoui@gmail.com — [harchaoui.org/warith/sprezzature](https://harchaoui.org/warith/sprezzature/)
