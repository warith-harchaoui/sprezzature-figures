# sprezzature-figures

🇫🇷 LISEZMOI.md · 🇬🇧 [README.md](README.md)

[![Python ≥3.10](https://img.shields.io/badge/python-%3E%3D3.10-blue)](https://www.python.org/)
[![Licence : BSD-3-Clause](https://img.shields.io/badge/licence-BSD--3--Clause-green)](LICENSE)

[![logo](assets/logo.png)](https://sprezzature.ai/)

127 types de graphiques de qualité publication, tous en SVG écrit à la main, y compris les sorties statistiques (inférence causale, explicabilité), utilisables comme bibliothèque Python ou en ligne de commande.

Fait partie de la suite [sprezzature](https://sprezzature.ai/).

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
| `[dataviz]` | networkx / scikit-learn / pandas / shapely / pyproj / pyyaml — le côté données (tableaux, géométrie, modèles) derrière le catalogue, l'inférence causale et l'explicabilité ; rien ici ne dessine |
| `[studio]` | Sprezzature Studio : l'application NiceGUI + le copilote Ralph (voir plus bas) |
| `[api]` | Surface HTTP FastAPI (voir plus bas) |
| `[mcp]` | Surface d'outils MCP (_Model Context Protocol_) au-dessus de `[api]`, pour appeler cette bibliothèque depuis un assistant IA (voir plus bas) |

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

Les 127 types enregistrés sont tous `status="stable"` (vérifiés par rendu de
bout en bout). Voir [docs/studio/GENERATOR_AUDIT.md](docs/studio/GENERATOR_AUDIT.md)
pour le détail de l'audit par type, ou lancer `make-figure --list --status stable`
pour confirmer l'ensemble actuel. Chaque type stable tolère qu'un rôle
optionnel reste non lié : il produit un rendu par défaut sensé au lieu de
planter.

### En ligne de commande

```bash
# Lister tous les types de graphiques disponibles (--status stable pour ceux vérifiés par rendu)
make-figure --list

# Générer un graphique avec ses données de démonstration intégrées
make-figure bar --out revenu.png --title "Revenu par région"
make-figure treemap --out budget.png --title "Décomposition du budget"
make-figure funnel --out entonnoir.png

# Générer à partir de vos propres données (.csv, .tsv, .json, .jsonl)
make-figure treemap --data budget.csv --out budget.png --title "Décomposition du budget"

# Si les colonnes ne correspondent pas aux rôles, associez-les avec --map
make-figure bar --data pib.csv --map region=Pays --map value=PIB --out pib.png

# Lire les données depuis l'entrée standard avec --data - et suréchantillonner avec --scale
cat ventes.jsonl | make-figure bar --data - --out ventes@2x.png --scale 2
```

Le format de sortie suit l'extension de `--out` : `.svg` (par défaut,
autonome avec polices embarquées), `.png`, `.pdf`, `.jpg` ou `.html`. Pour les
sorties raster et PDF, `--scale N` suréchantillonne N fois pour les écrans
haute densité (`--out chart.png --scale 3`) ; l'option est sans effet sur les
formats vectoriels `.svg`/`.html`.

Le fichier `--data` est lu en une ligne (un dictionnaire) par enregistrement :
les cellules CSV/TSV sont typées automatiquement (les nombres restent des
nombres) et le JSON accepte soit un tableau d'objets, soit un objet
enveloppant un tableau `"data"`. Passez `--data -` pour lire les mêmes formats
depuis l'entrée standard (le format est détecté d'après le contenu). Les noms
de colonnes doivent correspondre aux rôles attendus par le graphique.

Vous ne savez pas quel graphique convient à votre fichier ? Demandez une
recommandation (nécessite les extras `[cli]` et `[studio]`). C'est le même
classement déterministe (compatibilité et lisibilité) que les cartes de la GUI
Studio, sans aucun modèle :

```bash
sprezzature-figures recommend --data budget.csv
sprezzature-figures recommend --data budget.csv --render best.png
sprezzature-figures recommend --data budget.csv --intent hierarchy
```

Ajoutez `--intent BUT` (`comparison`, `trend`, `distribution`, `composition`,
`relationship`, `flow`, `hierarchy`, `geography`, `model_evaluation`) pour
classer d'abord les figures qui servent ce but analytique. Sans cette option,
de nombreux types se retrouvent à égalité en tête, car la seule lisibilité les
départage rarement ; c'est le but qui rend le classement décisif.

### À partir de l'image du graphique de quelqu'un d'autre

On vous envoie la capture d'écran d'un graphique pénible à lire, en vous
demandant de faire mieux. `redraw` s'occupe de la lecture : un modèle de
vision regarde l'image, dit de quel type de graphique il s'agit et ce qui
coûte des efforts au lecteur ; la figure, elle, est dessinée ici.

```bash
sprezzature-figures redraw leur-graphique.png --out le-notre.svg

# Avec vos vrais chiffres — le seul mode dont la sortie mérite d'être publiée
sprezzature-figures redraw leur-graphique.png --data ventes.csv --out le-notre.svg

# Passer outre le choix du modèle
sprezzature-figures redraw leur-graphique.png --kind bar --language fr
```

```python
from sprezzature_figures import redraw

resultat = redraw("leur-graphique.png", out="le-notre.svg", data=lignes, language="fr")
resultat.kind          # 'bar'
resultat.data_origin   # 'your-data'
resultat.changes       # ce qui change, le plus coûteux d'abord
```

L'image d'un graphique porte deux choses, et avec des certitudes très
différentes. Le **dessin** — quel type de graphique, de quoi il parle, ce
qu'il coûte à lire — se lit dans les pixels. Les **données**, en général,
non : un graphique tracé sans étiquettes de valeurs ne contient pas ses
propres chiffres, et un modèle à qui on les demande quand même en produira,
parce que c'est ce que font les modèles.

Donc `redraw` ne devine jamais, et chaque résultat dit ce qu'il a obtenu :

| `data_origin` | Ce que vous avez |
|---|---|
| `your-data` | Vous avez fourni les lignes. L'image n'a servi qu'au dessin. La vraie figure. |
| `read-from-image` | Les chiffres étaient imprimés sur l'original et ont été relus. Approximatifs, et la figure le dit sur elle-même. |
| `demo` | Rien de lisible. La **refonte** sur des données d'exemple — le bon type de graphique et la typographie de la maison, légendée comme telle. À regarder ; pas à publier. |

Cette mention est écrite sur la figure elle-même, dans un bandeau ajouté sous
le dessin, et pas seulement renvoyée à l'appelant : le SVG survit à l'appel
de fonction et sera regardé par quelqu'un qui n'aura rien vu de tout cela.

L'entrée accepte PNG, JPEG, GIF, WebP ou SVG — une capture d'écran fait
l'affaire. Un PDF est refusé nommément, en disant quoi faire à la place. Il
faut un modèle de vision : l'extra `[local]` et un [Ollama](https://ollama.com)
qui tourne, comme tous les appels de modèle de la suite.

Ce qu'on peut attendre du modèle qu'on lui donne : un modèle de vision 7B sur
un portable met environ 90 secondes, trouve sans faute le type de graphique et
le texte imprimé sur l'image, et relève un ou deux des défauts de lecture. Les
champs de jugement (`what_it_shows`, un titre qui dit le résultat) sont là où
un modèle plus grand justifie son coût — quand ils reviennent vides, la refonte
reprend le titre de l'original plutôt que d'en inventer un.

---

---

## Catalogue des graphiques

127 types de graphiques dans 21 catégories. Voir [FIGURES.md](FIGURES.md) pour le tableau complet.

| Catégorie | Graphiques |
|-----------|------------|
| Comparaison | bar, bar-grouped, bar3d, bubble, columnrange, difference-chart, dotplot, dumbbell, lollipop, packed-bubble, pareto, radial-bar, variwide, waterfall |
| Composition | area, donut, parliament, pictorial, stacked-area, stacked-bar, ternary, waffle |
| Distribution | beeswarm, bellcurve, blandaltman, boxen, boxplot, corr-matrix, ecdf, errorbar, hexbin, histogram, kde1d, kde2d-contour, mosaic, population-pyramid, ridgeline, rug, strip, violin |
| Flux | alluvial, chord, funnel, parallel-sets, sankey |
| Géospatial | binned-grid-map, choropleth, dotdensity, hexbin-map, hexmap, situation_map, spike-map, voronoi |
| Hiérarchie | circle-packing, convex-hull, dendrogram, icicle, org-chart, radial-tree, sunburst, tree, treemap |
| KPI | bullet, gauge, liquid-gauge |
| Matrice / Image | clustermap, heatmap, imshow-interpolated |
| Météorologie | windbarb, windrose |
| Évaluation de modèles | calibration, confusion-matrix, elbow, gaussian-process, liftgain, manhattan, ppplot, prcurve, qqplot, roc-curve, survival-km |
| Réseau | arcdiagram, dependency-wheel, edge-bundling, network, sfdp-largegraph |
| Régression | regression-ci-band, residual |
| Relation | parcoords, scatter, volcano |
| Signal | quiver, spectrogram, streamplot |
| Texte | wordcloud |
| 3D | scatter3d, surface3d, wireframe3d |
| Série temporelle | bollinger, calendar-heatmap, candlestick, connected-scatter, horizon, line, line-multi, slope, step, streamgraph, timeline |
| Multivarié | andrews, embedding_projector, jointplot, pairplot, radar, radviz, upset, venn |
| Méta-analyse | forest |
| Animé | gapminder, gapminder_variants |
| Autre | cycle, gantt, interruption-matrix, polar, rose, speaking_time |

---

## Thèmes visuels

Chaque graphique accepte un paramètre `theme`, qui règle l'apparence
(polices, couleurs), séparé du paramètre `accessibility`, qui garantit que
la palette reste lisible en cas de daltonisme (au sens large : tout trouble
de la vision des couleurs). Les deux se combinent librement parce qu'ils
répondent à deux questions différentes : l'un est affaire de goût, l'autre
détermine qui peut réellement lire le graphique.

- **`"corporate"`** (par défaut) : Roboto pour le texte d'habillage
  (titre, sous-titre, libellés d'axes), Roboto Mono pour les graduations
  et les valeurs numériques, avec une palette catégorielle dérivée du
  style Apple. Le rendu est identique au bit près à tout ce qui existait
  avant l'introduction de `theme`, donc adopter ce paramètre ne change
  rien pour le code déjà en place.
- **`"academic"`** : Latin Modern Roman et Mono, l'extension libre et
  native LaTeX de Computer Modern, pour un rendu façon figure de revue
  scientifique, associée à la palette catégorielle
  [Okabe-Ito](https://jfly.uni-koeln.de/color/) (Okabe et Ito, 2002).
  Cette palette a été conçue pour rester lisible sous les formes
  courantes de daltonisme ; c'est pourquoi elle sert de référence
  recommandée pour les figures scientifiques depuis l'éditorial de Wong,
  publié dans *Nature Methods* en 2011.

```python
make_figure("bar", data, out="revenue.svg", theme="academic")
```

```bash
make-figure bar --out revenue.svg --theme academic
```

Les deux polices sont intégrées au SVG (aucun chargement externe requis
pour un SVG autonome) ; les licences sont embarquées dans `assets/fonts/`
(Roboto : OFL, Latin Modern : GUST Font License, toutes deux autorisant
la redistribution groupée).

`theme="academic"` bascule aussi les rampes de couleurs séquentielles
(cartes de chaleur, densité hexbin, cartes de clusters, etc.) vers
[viridis](https://bids.github.io/colormap/), la palette perceptuellement
uniforme et sûre pour la vision des couleurs recommandée pour les figures
scientifiques ; `"corporate"` conserve la rampe propre à chaque graphique,
inchangée.

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
│   └── ...                        # 127 scripts make_*.py au total
├── assets/
│   └── svg-examples/      # gabarits SVG
└── tests/
```

Chaque script `make_<type>.py` est autonome : il importe ce dont il a besoin, définit `make_<type>(donnees, *, out=None, title="", ...) -> Path` et expose une liste `DEMO_DATA` pour la CLI et les tests. `make_figure()` résout le type via `sprezzature_figures/catalog/figures.json` plutôt que de deviner le nom de fichier ; voir [docs/studio/GENERATOR_AUDIT.md](docs/studio/GENERATOR_AUDIT.md) pour savoir lesquels des 127 scripts respectent déjà ce contrat.

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
  CLI `sprezzature-figures`) : tout ce qui précède, sans dépendance
  supplémentaire au-delà de `[cli]`/`[dataviz]`.
- **Sprezzature Studio** (`sprezzature_figures.studio`, CLI
  `sprezzature-studio`) : une application NiceGUI locale pour importer un
  CSV/TSV/XLSX/JSON, choisir un type de graphique, associer les colonnes, puis
  affiner la figure en dialoguant avec **Ralph**, un copilote adossé à un
  modèle de langage qui lit votre texte (un LLM) et à un modèle de vision
  qui regarde le rendu (un VLM). Ralph modifie un plan structuré et regarde
  vraiment le rendu avant de décider que c'est terminé. Nécessite l'extra
  `studio` :

  ```bash
  pip install "sprezzature-figures[studio]"
  sprezzature-studio
  ```

  Le modèle LLM/VLM de Ralph est fourni par
  [best-engine-ai-helper](https://github.com/warith-harchaoui/best-engine-ai-helper),
  qui s'adresse par défaut à un Ollama local (modèle texte `qwen3:8b`,
  modèle vision `gemma3:12b` ; à surcharger via `BEST_LLM_TEXT` /
  `BEST_LLM_VISION`). L'application **démarre et reste pleinement utilisable
  sans aucun modèle** : import, profilage, choix manuel du graphique,
  réglages, historique et export fonctionnent en mode dégradé ; seules les
  fonctions de dialogue et de critique nécessitent un modèle joignable. Rien
  ne quitte votre machine tant que vous ne pointez pas vers un service
  distant (voir
  [DATA_PRIVACY.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/docs/studio/DATA_PRIVACY.md)).

  Documentation complète : [docs/studio/README.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/docs/studio/README.md).

Il n'existe pas de « CLI Ralph » distincte dans ce dépôt. `scripts/ralph_eyeball_loop.py`
est un outil de QA visuelle interne, utilisé pendant le développement des
générateurs de graphiques eux-mêmes (voir sa propre docstring) ; il précède
et n'a aucun rapport avec le moteur Ralph du Studio
(`sprezzature_figures.studio.ralph`), qui est une implémentation entièrement
nouvelle, conforme au plan et testée.

---

## API HTTP & MCP

Au-delà de la ligne de commande, la même fonction `make_figure()` est
joignable sur le réseau de deux façons : comme une simple API HTTP, et
comme un outil MCP. Le MCP (_Model Context Protocol_) est une norme qui
permet à un assistant IA d'appeler directement les fonctions d'un
programme, de la même façon qu'un humain les appellerait depuis un script,
sans avoir à lire une documentation et à deviner. Trois interfaces
exposent au total le même dispatcheur `make_figure()` :

| Interface | Toujours installée ? | Point d'entrée |
|---|---|---|
| CLI (argparse) | Oui | `make-figure` |
| CLI (Click) | Extra `[cli]` | `sprezzature-figures` |
| API HTTP (FastAPI) | Extra `[api]` | `uvicorn sprezzature_figures.api:app` |
| Outils MCP (fastapi-mcp) | Extras `[api,mcp]` | `sprezzature-figures-mcp` |

```bash
pip install "sprezzature-figures[api]"
uvicorn sprezzature_figures.api:app --host 0.0.0.0 --port 8000

# Lister les types stables
curl http://localhost:8000/kinds?status=stable

# Rendre le treemap de démonstration en SVG
curl -X POST http://localhost:8000/render/treemap -o treemap.svg

# Rendre avec vos propres données
curl -X POST http://localhost:8000/render/bar -H 'Content-Type: application/json' \
     -d '{"data": [{"region": "North", "value": 42}], "title": "Mon graphique"}' -o bar.svg

# Refaire le graphique de quelqu'un d'autre à partir de son image
curl -X POST http://localhost:8000/redraw -H 'Content-Type: application/json' \
     -d "{\"image_base64\": \"$(base64 < leur-graphique.png)\"}" | jq -r .data_origin

# Documentation OpenAPI complète
open http://localhost:8000/docs
```

`POST /redraw` répond du JSON plutôt que des octets : la figure arrive
encodée en base64 dans `figure_base64`, à côté du diagnostic qui la
justifie (`kind`, `data_origin`, `changes`, `reading`). Lire `data_origin`
avant de se servir de la figure, c'est tout l'intérêt — voir
[À partir de l'image du graphique de quelqu'un d'autre](#à-partir-de-limage-du-graphique-de-quelquun-dautre).

`POST /recommend` classe les types de graphiques que vos lignes peuvent
remplir, chacun avec ses rôles déjà associés à vos colonnes — le même
classement déterministe que la commande `recommend`, mais en HTTP. C'est la
route à appeler avant `/render/{kind}` quand personne n'a nommé de type.

La surface MCP (`sprezzature-figures[api,mcp]`) expose ces mêmes routes
comme autant d'outils MCP (`list_kinds`, `get_kind`, `recommend_figures`,
`render_figure`, `redraw_figure`) sur `/mcp`, dans la même app FastAPI.
Chacun porte un résumé écrit à la main et une description qui dit **quand**
l'appeler — voir [TRIGGERS.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/TRIGGERS.md)
pour les règles d'aiguillage qu'un agent doit suivre.
[fastapi-mcp](https://github.com/tadata-org/fastapi_mcp) enveloppe toute
la surface HTTP en une seule ligne, les routes ne sont donc jamais
dupliquées :

```bash
pip install "sprezzature-figures[api,mcp]"
sprezzature-figures-mcp
```

---

## Développement

```bash
git clone https://github.com/warith-harchaoui/sprezzature-figures.git
cd sprezzature-figures
pip install -e ".[dev,cli]"
ruff check sprezzature_figures/
python -m pytest tests/ -q
```

Tests de rendu (génèrent réellement les figures, quelques secondes chacun) :

```bash
python -m pytest -m slow tests/
```

---

## Licence

BSD 3-Clause. Voir [LICENSE](LICENSE).

## Auteur

Warith HARCHAOUI · warith.harchaoui@gmail.com · [harchaoui.org/warith/sprezzature](https://sprezzature.ai/)
