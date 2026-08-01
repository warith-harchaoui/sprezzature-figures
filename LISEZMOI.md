# sprezzature-figures

🇫🇷 LISEZMOI.md · 🇬🇧 [README.md](README.md)

[![Python ≥3.10](https://img.shields.io/badge/python-%3E%3D3.10-blue)](https://www.python.org/)
[![Licence : BSD-3-Clause](https://img.shields.io/badge/licence-BSD--3--Clause-green)](LICENSE)

[![logo](assets/logo.png)](https://harchaoui.org/warith/sprezzature/)

90 types de graphiques de qualité publication — Vega-Lite, Vega complet et matplotlib/SVG — utilisables comme bibliothèque Python ou en ligne de commande.

Fait partie de la suite [sprezzature](https://harchaoui.org/warith/sprezzature/).

---

## Installation

Nécessite **Python 3.10–3.13**. Testé sur 🍎 macOS, 🐧 Ubuntu et 🪟 Windows
(la CI exécute toute la suite plus une vérification d'installation de la
wheel sur les trois).

```bash
pip install sprezzature-figures
```

Extras optionnels (combinables, ex. `"sprezzature-figures[cli,dataviz]"`) :

| Extra | Ajoute |
|-------|--------|
| `[cli]` | l'interface Click, jumelle de la CLI `make-figure` toujours installée |
| `[dataviz]` | matplotlib / networkx / wordcloud / shapely / pyproj / pyyaml — nécessaires aux générateurs non Vega-Lite |
| `[studio]` | Sprezzature Studio : l'application NiceGUI + le copilote Ralph (voir plus bas) |

Utilisez un environnement virtuel pour tout isoler :

<details>
<summary>🍎 macOS / 🐧 Ubuntu</summary>

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install "sprezzature-figures[cli,dataviz]"
```
</details>

<details>
<summary>🪟 Windows (PowerShell)</summary>

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install "sprezzature-figures[cli,dataviz]"
```
</details>

Vérifier l'installation :

```bash
make-figure --list --status stable
make-figure bar --out check.svg
```

---

## Démarrage rapide

### En bibliothèque

```python
from sprezzature_figures import make_figure

donnees = [
    {"region": "Nord",  "value": 42},
    {"region": "Sud",   "value": 28},
    {"region": "Est",   "value": 19},
    {"region": "Ouest", "value": 11},
]
chemin = make_figure("bar", donnees, out="revenu.png", title="Revenu par région")
print(chemin)  # PosixPath('revenu.png')
```

`make_figure()` accepte n'importe quel type enregistré, mais seuls les types
`status="stable"` sont aujourd'hui vérifiés par rendu — voir
[docs/studio/GENERATOR_AUDIT.md](docs/studio/GENERATOR_AUDIT.md) pour le
statut de chacun des 90 types, et `make-figure --list --status stable` pour
la liste de ceux qui fonctionnent dès maintenant (12 à ce jour : `bar`,
`line`, `area`, `scatter`, `histogram`, `boxplot`, `heatmap`, `columnrange`,
`funnel`, `sunburst`, `treemap`, `waterfall`).

### En ligne de commande

```bash
# Lister tous les types de graphiques disponibles (--status stable pour ceux vérifiés par rendu)
make-figure --list

# Générer un graphique avec ses données de démonstration intégrées
make-figure bar --out revenu.png --title "Revenu par région"
make-figure treemap --out budget.png --title "Décomposition du budget"
make-figure funnel --out entonnoir.png
```

---

## Catalogue des graphiques

90 types de graphiques dans 21 catégories. Voir [FIGURES.md](FIGURES.md) pour le tableau complet.

| Catégorie | Graphiques |
|-----------|------------|
| Comparaison | bar, bar3d, columnrange, difference-chart, dotplot, dumbbell, packed-bubble, pareto, radial-bar, variwide, waterfall |
| Composition | area, parliament, pictorial, ternary, waffle |
| Distribution | bellcurve, blandaltman, boxen, boxplot, histogram, mosaic, ridgeline, rug |
| Flux | alluvial, chord, funnel, parallel-sets, sankey |
| Géospatial | binned-grid-map, dotdensity, globe3d, hexbin-map, hexmap, situation_map, spike-map, voronoi |
| Hiérarchie | circle-packing, convex-hull, dendrogram, icicle, org-chart, radial-tree, sunburst, tree, treemap |
| KPI | bullet, gauge, liquid-gauge |
| Matrice / Image | heatmap, imshow-interpolated |
| Météorologie | windbarb, windrose |
| Évaluation de modèles | calibration, liftgain, manhattan, ppplot, prcurve |
| Réseau | arcdiagram, dependency-wheel, edge-bundling, network, sfdp-largegraph |
| Régression | residual |
| Relation | scatter |
| Signal | spectrogram, streamplot |
| Texte | wordcloud |
| 3D | scatter3d, wireframe3d |
| Série temporelle | bollinger, connected-scatter, horizon, line, streamgraph, timeline |
| Multivarié | andrews, embedding_projector, jointplot, pairplot, radar, radviz, upset, venn |
| Méta-analyse | forest |
| Animé | gapminder, gapminder_variants |
| Autre | polar, rose, speaking_time |

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
│   └── ...                        # 90 scripts make_*.py au total
├── assets/
│   ├── vega-examples/     # spécifications Vega-Lite et Vega
│   └── svg-examples/      # gabarits SVG
├── references/            # documentation des sources de référence
└── tests/
```

Chaque script `make_<type>.py` est autonome : il importe ce dont il a besoin, définit `make_<type>(donnees, *, out=None, title="", ...) -> Path` et expose une liste `DEMO_DATA` pour la CLI et les tests. `make_figure()` résout le type via `sprezzature_figures/catalog/figures.json` plutôt que de deviner le nom de fichier — voir [docs/studio/GENERATOR_AUDIT.md](docs/studio/GENERATOR_AUDIT.md) pour savoir lesquels des 90 scripts respectent déjà ce contrat.

---

## Ajouter un type de graphique

1. Créer `scripts/make_<type>.py` en suivant le schéma d'un script existant.
2. Exposer `DEMO_DATA: list[dict]` et une fonction `make_<type>(donnees, *, out=None, title="", ...) -> Path`.
3. Ajouter une ligne dans [FIGURES.md](FIGURES.md).
4. Lancer `python tools/audit_generators.py --render` puis `python tools/build_figures_catalog.py` pour l'enregistrer dans `sprezzature_figures/catalog/figures.json` (sans cela, `make_figure()` ne l'atteint que via un repli déprécié qui affiche un avertissement).
5. Vérifier avec `make-figure <type>`.

---

## Sprezzature Studio

Ce dépôt contient deux choses :

- **La bibliothèque** (`sprezzature_figures.make_figure`, `make-figure`,
  CLI `sprezzature-figures`) — tout ce qui précède. Aucune dépendance
  supplémentaire au-delà de `[cli]`/`[dataviz]`.
- **Sprezzature Studio** (`sprezzature_figures.studio`, CLI
  `sprezzature-studio`) — une application NiceGUI locale pour importer un
  CSV/XLSX, choisir un type de graphique, associer les colonnes, puis
  affiner la figure en dialoguant avec **Ralph**, un copilote LLM/VLM qui
  modifie un plan structuré et regarde vraiment le rendu avant de décider
  que c'est terminé. Nécessite l'extra `studio` :

  ```bash
  pip install "sprezzature-figures[studio]"
  sprezzature-studio
  ```

  Documentation complète : [docs/studio/README.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/docs/studio/README.md).

Il n'existe pas de « CLI Ralph » distincte dans ce dépôt — `scripts/
ralph_eyeball_loop.py` est un outil de QA visuelle interne, utilisé pendant
le développement des générateurs de graphiques eux-mêmes (voir sa propre
docstring) ; il précède et n'a aucun rapport avec le moteur Ralph du
Studio (`sprezzature_figures.studio.ralph`), qui est une implémentation
entièrement nouvelle, conforme au plan et testée.

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
