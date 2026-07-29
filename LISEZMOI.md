# sprezzature-figures

84 types de graphiques de qualité publication — Vega-Lite, Vega complet, et matplotlib/SVG — utilisables comme bibliothèque Python ou en ligne de commande.

Fait partie de la suite [sprezzature](https://github.com/sprezzature/sprezzature).

---

## Installation

```bash
pip install sprezzature-figures
```

Avec l'interface en ligne de commande Click (optionnelle) :

```bash
pip install "sprezzature-figures[cli]"
```

---

## Démarrage rapide

### En bibliothèque

```python
from sprezzature_figures import make_figure

donnees = [
    {"label": "Nord",  "value": 42},
    {"label": "Sud",   "value": 28},
    {"label": "Est",   "value": 19},
    {"label": "Ouest", "value": 11},
]
chemin = make_figure("bar", donnees, out="revenu.png", title="Revenu par région")
print(chemin)  # PosixPath('revenu.png')
```

### En ligne de commande

```bash
# Lister tous les types de graphiques disponibles
make-figure --list

# Générer un graphique avec ses données de démonstration intégrées
make-figure treemap --out budget.png --title "Décomposition du budget"
make-figure gapminder --out gapminder.html
make-figure sankey --out flux-energie.png
```

---

## Catalogue des graphiques

84 types de graphiques dans 15 catégories. Voir [FIGURES.md](FIGURES.md) pour le tableau complet avec des conseils sur le choix du bon graphique.

---

## Architecture

```
sprezzature-figures/
├── sprezzature_figures/
│   ├── __init__.py        # exporte make_figure
│   ├── make_figure.py     # répartiteur + list_kinds() + CLI argparse
│   └── cli.py             # point d'entrée Click (optionnel)
├── scripts/
│   ├── make_bar.py        # script autonome par type de graphique
│   └── ...                # 84 scripts make_*.py au total
├── assets/
│   ├── vega-examples/     # exemples de spécifications Vega-Lite et Vega
│   └── svg-examples/      # gabarits SVG
├── references/            # documentation des sources de référence
└── tests/
```

Chaque script `make_<type>.py` est autonome : il importe ce dont il a besoin, définit `make_<type>(donnees, **kwargs) -> str` et expose une liste `DEMO_DATA` pour la CLI et les tests.

---

## Ajouter un type de graphique

1. Créer `scripts/make_<type>.py` en suivant le schéma d'un script existant.
2. Exposer `DEMO_DATA: list[dict]` et une fonction `make_<type>(donnees, **kwargs) -> str`.
3. Ajouter une ligne dans [FIGURES.md](FIGURES.md).
4. Vérifier avec `make-figure <type>`.

---

## Développement

```bash
git clone https://github.com/sprezzature/sprezzature-figures.git
cd sprezzature-figures
pip install -e ".[dev,cli]"
ruff check sprezzature_figures/
python -m pytest tests/ -q
```

Tests de rendu lents (nécessitent un affichage ou vl-convert) :

```bash
python -m pytest -m slow tests/
```

---

## Licence

BSD 3-Clause — voir [LICENSE](LICENSE).

## Auteur

Warith Harchaoui — warith.harchaoui@gmail.com — [sprezzature.com](https://sprezzature.com)
