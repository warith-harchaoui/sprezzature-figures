# sprezzature-figures

🇫🇷 LISEZMOI.md · 🇬🇧 [README.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/README.md)

[![Python ≥3.10](https://img.shields.io/badge/python-%3E%3D3.10-blue)](https://www.python.org/)
[![Licence : BSD-3-Clause](https://img.shields.io/badge/licence-BSD--3--Clause-green)](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/LICENSE)

[![logo](https://raw.githubusercontent.com/warith-harchaoui/sprezzature-figures/main/assets/logo.png)](https://sprezzature.ai/)

167 types de graphiques de qualité publication, chacun écrit directement en
SVG, sans bibliothèque de tracé dessous. Aussi : un contrôle statique de
n'importe quel SVG rendu, le redessin du graphique de quelqu'un d'autre à
partir de son image, et the editor, un éditeur de figures local piloté
par la conversation.

Fait partie de la suite [sprezzature](https://sprezzature.ai/).

---

## Comment ça marche

![Schéma de flux. En haut, vos données ou la figure de quelqu'un d'autre alimentent deux voies. La voie de gauche dessine : elle classe les types selon votre objectif, écrit le SVG directement sans bibliothèque de tracé dessous, et sait redessiner la capture d'écran d'une figure sans en inventer les nombres. La voie de droite contrôle : un examen statique lit n'importe quel SVG pour y trouver les étiquettes superposées et les noms sortis du cadre, puis la boucle Ralph rend la figure, la regarde, et corrige la source. Les deux se rejoignent en un seul résultat, une figure juste avant d'être belle.](https://raw.githubusercontent.com/warith-harchaoui/sprezzature-figures/main/assets/comment-ca-marche.svg)

## Cinq portes d'entrée

Le même moteur répond sur cinq surfaces. Chacune appelle le même
répartiteur `make_figure()` et le même catalogue.

| Surface | Point d'entrée | Section |
|---|---|---|
| Bibliothèque Python | `from sprezzature_figures import make_figure` | [Démarrage rapide](#démarrage-rapide) |
| Ligne de commande (Click) | `sprezzature-figures`, aussi installée sous le nom `make-figure` | [Ligne de commande](#ligne-de-commande) |
| API HTTP (FastAPI), avec Docker et Compose | `uvicorn sprezzature_figures.api:app`, `docker compose up` | [API HTTP, MCP et Docker](#api-http-mcp-et-docker) |
| Outils MCP | `sprezzature-figures-mcp` | [API HTTP, MCP et Docker](#api-http-mcp-et-docker) |
| Skill pour agent | `sprezzature-figures/SKILL.md` dans le [dépôt central sprezzature](https://github.com/warith-harchaoui/sprezzature) | [TRIGGERS.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/TRIGGERS.md) |

MCP (Model Context Protocol) est un standard qui permet à un assistant d'IA
d'appeler directement les fonctions d'un programme comme des outils. Un skill
est le fichier d'instructions qu'un agent comme Claude Code lit pour décider
quand se servir de ce paquet ; il vit dans le dépôt central, pas ici.

## Installation

Nécessite **Python 3.10 à 3.13**.

```bash
pip install sprezzature-figures
```

Cette seule commande installe tout : les générateurs, le côté données (pandas,
scikit-learn, networkx, shapely, pyproj, pyyaml), la pile causale (dowhy,
econml), la pile d'explicabilité (shap, shapash, timeshap, lime), Sprezzature
Editor (NiceGUI), l'application FastAPI et le serveur MCP. Il n'y a pas
d'extras de fonctionnalité. Ils ont été versés dans la base le 2026-11-01. Le
seul extra restant est `[dev]`, l'outillage de test et de lint pour qui
contribue.

Utilisez un environnement virtuel pour tout isoler :

<details>
<summary>macOS / Ubuntu</summary>

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install sprezzature-figures
```
</details>

<details>
<summary>Windows (PowerShell)</summary>

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install sprezzature-figures
```
</details>

Vérifier l'installation :

```bash
sprezzature-figures list --status stable
sprezzature-figures render bar --out check.svg
```

La CI tourne sur Ubuntu : lint, vérification des types et suite complète sous
Python 3.12, construction de la roue et installation propre, et un contrôle
d'installation et d'import sous Python 3.10.

---

## Démarrage rapide

### En bibliothèque

```python
from sprezzature_figures import make_figure

data = [
    {"region": "North", "value": 42},
    {"region": "South", "value": 28},
    {"region": "East",  "value": 19},
    {"region": "West",  "value": 11},
]
path = make_figure("bar", data, out="revenue.png", title="Chiffre d'affaires par région")
print(path)  # le chemin absolu de revenue.png
```

`make_figure(kind, data=None, **kwargs)` renvoie le fichier écrit sous forme de
`FigurePath`, une sous-classe de `pathlib.Path`. Sans `data`, la figure dessine
ses propres lignes de démonstration.

Les autres noms publics de `sprezzature_figures` :

| Nom | Ce qu'il fait |
|---|---|
| `list_kinds(status=None)` | Le catalogue, en noms de types canoniques. |
| `get_figure_definition(kind)` | La fiche d'un type : rôles de données, alias, taille par défaut, options. |
| `validate_figure_input(kind, data)` | Vérifie des lignes contre les rôles requis d'un type, sans rendu. |
| `as_rows(data)` | Transforme un DataFrame ou un dictionnaire de colonnes en la `list[dict]` que prennent les figures. |
| `FigurePath` | Le chemin renvoyé, qui s'affiche lui-même dans un carnet. |
| `check_render(svg)` / `RenderFinding` | Contrôle statique d'un SVG rendu (voir [Vérifier une figure](#vérifier-une-figure-la-vôtre-ou-celle-dun-autre)). |
| `to_dark(svg)` | Réécrit un SVG rendu pour un fond sombre. |
| `text_width(text, font_size)` | L'estimation de largeur de texte avec laquelle les générateurs mettent en page et que le contrôle mesure. |
| `redraw(image)` / `RedrawResult` | Redessine un graphique à partir de son image (voir [plus bas](#à-partir-de-limage-du-graphique-de-quelquun-dautre)). |

`sprezzature_figures.options.options_for(kind)` liste tous les mots-clés
qu'une figure accepte en plus de ses lignes.

### Depuis un DataFrame, dans un carnet

Les lignes peuvent être ce que vous avez déjà en main : un DataFrame pandas,
polars ou Arrow, ou un dictionnaire de colonnes. Rien n'est importé pour les
lire. La conversion se fait par typage structurel (« duck typing »), donc
aucune de ces bibliothèques n'est nécessaire pour l'appeler.

```python
import pandas as pd
from sprezzature_figures import make_figure

df = pd.read_csv("revenue.csv")          # region, value
make_figure("bar", df, out="revenue.svg", title="Chiffre d'affaires par région")
```

Une cellule qui se termine par cet appel **affiche la figure**. La valeur
renvoyée reste un `Path` : `isinstance(result, Path)` est vrai, et toutes les
méthodes fonctionnent. Il sait simplement se dessiner quand un carnet le lui
demande.

Les trous s'écrivent `None` à l'entrée, quel que soit le nom que leur donnait
la source (`NaN`, `NaT`, `pd.NA`), et un trou dans une colonne dont la figure a
besoin est refusé dès l'entrée, avec le nom de la colonne et de la ligne :

```
ValueError: Invalid data for kind='bar': value: 'value' (Value) is empty in
1 of 3 rows (row 1). A figure cannot draw a value that is not there: drop
those rows, fill them, or reach for 'missing-matrix', which is the figure
whose subject is where the gaps are.
```

Écarter la ligne en silence aurait faussé le total ; la laisser passer aurait
levé une erreur au fond d'un générateur, avec un message sur `float()`. Les
figures dont le sujet *est* l'absence (`missing-matrix`, la racine d'un arbre
sans parent, une prévision sans historique) le déclarent et passent.

Les 167 types de graphiques enregistrés sont `status="stable"` : chacun est
rendu de bout en bout par l'audit des générateurs. Voir
[docs/editor/GENERATOR_AUDIT.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/docs/editor/GENERATOR_AUDIT.md)
pour le détail par graphique. Chaque type stable tolère qu'on laisse ses rôles
optionnels sans colonne : il dessine une valeur par défaut raisonnable au lieu
de planter.

### Ligne de commande

Un seul groupe de commandes Click, installé sous deux noms :
`sprezzature-figures` et `make-figure` exécutent le même code, tout comme
`python -m sprezzature_figures`. Ses sous-commandes sont `list`, `render`,
`describe`, `recommend`, `redraw` et `check`.

```bash
# Lister tous les types (--status stable pour ceux vérifiés par rendu, --json pour un programme)
sprezzature-figures list

# Générer un graphique avec ses données de démonstration intégrées
sprezzature-figures render bar --out revenue.png --title "Chiffre d'affaires par région"
sprezzature-figures render treemap --out budget.png --title "Répartition du budget"
sprezzature-figures render funnel --out funnel.png

# Générer à partir de vos propres données (.csv, .tsv, .json, .jsonl)
sprezzature-figures render treemap --data budget.csv --out budget.png --title "Répartition du budget"

# Si les colonnes ne correspondent pas aux rôles de la figure, associez-les avec --map
sprezzature-figures render bar --data pib.csv --map region=Pays --map value=PIB --out pib.png

# Lire les données depuis l'entrée standard avec --data - et suréchantillonner avec --scale
cat ventes.jsonl | sprezzature-figures render bar --data - --out ventes@2x.png --scale 2
```

Chaque figure a aussi ses propres mots-clés. Selon la figure, ils couvrent un
sous-titre, une taille de canevas, des titres d'axes, un thème, une palette
d'accessibilité, la langue du texte qu'elle écrit elle-même, et ce qui est
propre à ce graphique-là. Demandez à la figure ce qu'elle accepte :

```bash
# Ce que ce graphique exige (rôles de données) et ce qu'il accepte (options), avec les défauts
sprezzature-figures describe treemap

# Les mêmes options sous forme de drapeaux, une fois la figure nommée
sprezzature-figures render sankey --help
```

Puis passez-les. Chaque option est un drapeau à part entière, et
`--set nom=valeur` est la forme scriptable qui les atteint toutes :

```bash
sprezzature-figures render bar --out ventes.svg --subtitle "Exercice 2024" --width 1200 --theme academic
sprezzature-figures render sankey --out flux.svg --set volume-unit=sessions --set stage-names="Source,Arrivée,Action,Issue"
sprezzature-figures render bar --out ventes.svg --language fr --accessibility monochrome
```

Une option que la figure n'accepte pas est une erreur qui nomme celles
qu'elle accepte. Ce n'est jamais un drapeau ignoré en silence, ce qui faisait
autrefois passer une faute de frappe pour une figure qui n'écoutait pas.
Donner la même option à la fois en drapeau et par `--set` est aussi une
erreur.

Le format de sortie suit l'extension de `--out` : `.svg` (par défaut,
entièrement autonome avec les polices intégrées), `.png`, `.pdf`, `.jpg` ou
`.html`. Pour les sorties matricielles et PDF, `--scale N` suréchantillonne N
fois pour les écrans haute densité (`--out chart.png --scale 3`) ; il est
ignoré pour `.svg` et `.html`. `--dark` rend pour un fond sombre.

Passez toujours `--out` (ou `out=` en Python). Sans lui, le générateur se
rabat sur son propre chemin d'exemple, `assets/svg-examples/<type>.svg` un
niveau au-dessus du répertoire `scripts/` : dans un dépôt cloné, cela écrase
l'exemple versionné, et dans un paquet installé, cela écrit sous
`site-packages/`.

Le fichier `--data` est lu en un dictionnaire par enregistrement : les
cellules CSV/TSV sont typées (les nombres restent des nombres), et le JSON
accepte soit un tableau d'objets nu, soit un objet qui enveloppe un tableau
`"data"`. Passez `--data -` pour lire les mêmes formats depuis l'entrée
standard (la forme est reconnue d'après le contenu). Les noms de colonnes
doivent correspondre aux rôles attendus
(`sprezzature-figures describe <type>` les liste) ;
sinon `--map role=colonne` les associe sans toucher au fichier.

Vous ne savez pas quel graphique convient à votre fichier ? Demandez une
recommandation. Elle exécute le même filtre de compatibilité déterministe et
le même score de lisibilité que les cartes de l'éditeur, sans aucun modèle :

```bash
sprezzature-figures recommend --data budget.csv
sprezzature-figures recommend --data budget.csv --render best.png    # rendre aussi le premier choix
sprezzature-figures recommend --data budget.csv --intent hierarchy   # classer selon un objectif
```

Ajoutez `--intent OBJECTIF` (`comparison`, `trend`, `distribution`,
`composition`, `relationship`, `flow`, `hierarchy`, `geography`,
`model_evaluation`) pour classer en tête les figures dont la catégorie de
catalogue sert cet objectif. Sans lui, beaucoup de types sont à égalité en
tête, parce que la lisibilité seule les départage rarement ; c'est l'objectif
qui rend le classement décisif. `--limit N` fixe le nombre de réponses (5 par
défaut).

### À partir de l'image du graphique de quelqu'un d'autre

On vous envoie la capture d'écran d'un graphique difficile à lire, et on vous
demande de l'améliorer. `redraw` fait la lecture : un modèle de vision regarde
l'image, dit de quel type de graphique il s'agit et ce qui coûte un effort au
lecteur, puis la figure est dessinée ici.

```bash
sprezzature-figures redraw le-leur.png --out le-notre.svg

# Avec vos vrais chiffres : le seul mode dont la sortie mérite d'être publiée
sprezzature-figures redraw le-leur.png --data ventes.csv --out le-notre.svg

# Passer outre le choix du modèle
sprezzature-figures redraw le-leur.png --kind bar --title "Les exportations portent le trimestre"
```

Sans `--out`, la figure est écrite dans `<type>-redrawn.svg`. `--hint` transmet
une note au modèle, et `--language en|fr` fixe la langue de la légende de
provenance.

```python
from sprezzature_figures import redraw

result = redraw("le-leur.png", out="le-notre.svg", data=rows)
result.kind          # 'bar'
result.data_origin   # 'your-data'
result.changes       # ce qu'il fait autrement, du plus coûteux au moins coûteux
```

L'image d'un graphique porte deux choses, avec des degrés de confiance très
différents. Le **dessin** (quel type de graphique, de quoi il parle, ce qu'il
coûte au lecteur) se lit sur les pixels. Les **données**, en général, non : un
graphique tracé sans étiquettes de valeurs ne contient pas ses propres
nombres, et un modèle à qui on les demande quand même en produira, parce que
c'est ce que font les modèles.

Donc `redraw` ne devine jamais, et chaque résultat dit ce qu'il a obtenu :

| `data_origin` | Ce que vous avez |
|---|---|
| `your-data` | Vous avez fourni les lignes. L'image n'a fourni que le dessin. La vraie figure. |
| `read-from-image` | Les nombres étaient imprimés sur l'original et ont été relus. Approximatif, et la figure le dit sur sa face. |
| `demo` | Rien de lisible. La **refonte** sur des données d'exemple : le bon type de graphique et la typographie maison, légendée comme telle. À regarder, pas à publier. |

Cette légende est écrite sur la figure elle-même, dans un bandeau ajouté sous
le dessin, et pas seulement renvoyée à l'appelant : le SVG survit à l'appel de
fonction et sera regardé par quelqu'un qui ne l'a jamais vu.

L'entrée peut être en PNG, JPEG, GIF, WebP ou SVG ; une capture d'écran est
le cas habituel. Un PDF est refusé nommément, avec ce qu'il faut faire à la
place. Il faut un modèle de vision, atteint par
[best-engine-ai-helper](https://github.com/warith-harchaoui/best-engine-ai-helper)
et un [Ollama](https://ollama.com) en marche par défaut, comme tout autre appel
de modèle dans la suite.

Ce qu'on peut attendre du modèle utilisé : un modèle de vision de 7B sur un
portable met environ 90 secondes, reconnaît de façon fiable le type de
graphique et le texte imprimé sur l'image, et signale un ou deux des problèmes
de lecture. Les champs de jugement (`what_it_shows`, un titre qui énonce le
résultat) sont là où un modèle plus gros se rend utile. Quand ils reviennent
vides, le redessin reprend le titre de l'original plutôt que d'en inventer un.

### Vérifier une figure, la vôtre ou celle d'un autre

Un graphique peut être faux d'une manière qui n'a rien à voir avec le goût :
deux étiquettes imprimées l'une sur l'autre, un nom qui sort du canevas, une
valeur écrite dans la couleur de la barre derrière elle, un habillage de
démonstration qui a survécu dans un vrai rendu, un titre donné au générateur
et abandonné en silence. `check` trouve tout cela dans la seule source SVG :
ni navigateur, ni modèle de vision, ni jugement.

```bash
sprezzature-figures check la-mienne.svg
sprezzature-figures check la-leur.svg --format json          # pour une porte de contrôle, pas pour un lecteur
sprezzature-figures check la-mienne.svg --expect-title "CA T3"   # le titre est-il arrivé ?
cat la-mienne.svg | sprezzature-figures check - --dark       # depuis un tube, fond sombre
```

`--forbid TEXTE` (répétable) ajoute vos propres textes de remplissage à
l'habillage de démonstration qu'il connaît déjà.

```python
from sprezzature_figures import check_render

for finding in check_render(open("la-mienne.svg").read()):
    print(finding.check, finding.severity, finding.message)
```

Il lit **n'importe quel** SVG, pas seulement les nôtres. C'est tout l'intérêt :
les travaux publiés sur le lint de visualisations vérifient une
*spécification* de graphique, et n'ont donc rien à dire d'une figure qui n'a
pas été écrite dans l'une d'elles. Celui-ci lit le dessin. La géométrie dont
il a besoin est lue comme chaque exportateur l'écrit : `font-size` en attribut
ou dans `style=`, `dominant-baseline` comme point d'alignement et non comme
ligne de base, `rotate(-0 …)` comme la non-rotation qu'il est, `width="100%"`
comme une proportion et non comme cent pixels.

Le code de sortie vaut 1 dès qu'il trouve quelque chose, il sert donc de porte
de contrôle en pre-commit ou en CI. Chaque constat porte une `severity` :
`error` est faux quel que soit l'auteur et quel que soit l'usage, `warning`
est faux selon la charte maison, ou faux sauf si l'auteur avait une raison.
Une porte qui bloque sur les deux est une porte que les gens désactivent.

**Sa limite honnête.** Il ne peut pas vérifier une figure dont le texte a été
converti en contours. Dès que chaque glyphe est un `<path>`, il n'y a plus de
texte à lire, aucun lecteur d'écran ne peut le lire non plus, et toutes les
règles passeraient sur une figure vide de sens. C'est le réglage par défaut de
plus d'un exportateur répandu, alors le contrôle le dit à voix haute
(`text_as_outlines`) plutôt que de renvoyer la liste vide qui ressemble à une
réussite. Réexportez avec du texte réel (quel que soit l'outil d'origine, le
réglage tient en général à une option) et relancez.

Le même constat couvre l'autre chemin vers le même endroit : une figure qui
n'a jamais reçu d'étiquettes. Le rapport distingue les deux cas, parce que
conseiller de réexporter ne sert à rien quand il n'y avait rien à exporter.

Ce qu'il ne fera jamais, c'est vous dire que le type de graphique convient à
la question, ou que la figure est belle. Ce sont des jugements ; la boucle
Ralph Eyeball (plus bas) est l'endroit où un modèle de vision est interrogé
sur eux, et elle n'a jamais le droit de contredire un fait établi ici.

### La boucle Ralph Eyeball

`scripts/ralph_eyeball_loop.py` rend en PNG n'importe quel visuel produit par
du code (`.svg`, `.html`, un `.tex` TikZ, un `.mmd` Mermaid) et écrit un
fichier d'évaluation sous `.private/ralph-loop/`. Vous modifiez la source et
vous relancez ; chaque passage ajoute une itération. Par défaut, l'agent qui
l'exécute lit le PNG lui-même. Avec `--local`, un modèle de vision local
(`qwen3-vl:8b`, via best-engine-ai-helper) écrit la critique hors ligne.

```bash
python scripts/ralph_eyeball_loop.py figure.svg
python scripts/ralph_eyeball_loop.py figure.svg --local
python scripts/ralph_eyeball_loop.py --check-tools
```

C'est un script du dépôt, pas une commande installée. Le moteur Ralph du
Editor (`sprezzature_figures.editor.ralph`) est une implémentation distincte.

### Autres scripts

Le répertoire `scripts/` du dépôt contient aussi des outils autonomes, chacun
avec son `--help` :

| Script | Ce qu'il fait |
|---|---|
| `render_diagram.py` | Rend en PNG une source TikZ, Mermaid ou SVG, aux couleurs de la palette maison. |
| `audit_figure.py` | Contrôle statique de graphiques SVG, ou de HTML contenant des blocs `<figure>`. |
| `explain_model.py` | Explique un modèle sérialisé avec SHAP, Shapash, TimeSHAP ou LIME (explications locales indépendantes du modèle). |
| `causal_estimate.py` | Estime un effet causal avec DoWhy et EconML, à partir d'un DAG (graphe orienté acyclique). |
| `install_figures.py` | Installe les paliers de dépendances figés dans `scripts/requirements-*.txt` avec le gestionnaire d'environnement détecté. |

---

## Catalogue des graphiques

167 types de graphiques dans 68 catégories, tels que le catalogue
(`sprezzature_figures/catalog/figures.json`) les enregistre. Voir
[FIGURES.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/FIGURES.md)
pour le tableau complet, avec quand utiliser chaque type, et
[TRIGGERS.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/TRIGGERS.md)
pour la phrase qui mène à chacun.

La [galerie de figures sur sprezzature.ai](https://sprezzature.ai/figures.html)
compte autre chose, exprès : elle en montre 160 sur 167. Les cinq cartes à
glyphes (`map-bars`, `map-bubble`, `map-flow`, `map-pie`, `map-tilegrid`) sont
sur la page des cartes, et les deux figures Gapminder sur la page consacrée à
Hans ROSLING.

Les noms de catégories sont ceux du catalogue, en anglais.

| Catégorie | Types |
|-----------|-------|
| 3-D | scatter3d |
| 3-D lattice | voxels |
| 3-D path | line3d |
| 3-D surface | manifold_path, surface3d, trisurface, wireframe3d |
| Accounting / Decomposition | waterfall |
| Agreement | blandaltman |
| Animated bubble | gapminder, gapminder_variants |
| Bivariate distribution | hist2d, jointplot, kde2d-contour |
| Bivariate time series | connected-scatter |
| Categorical | mosaic |
| Categorical flow | parallel-sets |
| Causal inference | causal-dag |
| Cause and effect | fishbone |
| Change | dumbbell, slope |
| Clustering | convex-hull |
| Communication | interruption-matrix, speaking_time |
| Comparison | bar, bar-grouped, bar3d, bubble, difference-chart, dual-axis, lollipop, packed-bubble, radial-bar, variwide |
| Composition | area, donut, pie, stacked-area, stacked-bar, waffle |
| Compositional | ternary |
| Cyclic | cycle, polar, rose |
| Data quality | missing-matrix |
| Decomposition | seasonal-decomposition |
| Dimensionality reduction | diffusion_trajectory, embedding_projector |
| Distribution | beeswarm, bellcurve, boxen, boxplot, clustermap, corr-matrix, dotplot, ecdf, errorbar, hexbin, histogram, kde1d, pointplot, population-pyramid, ridgeline, rug, strip, violin |
| Finance | bollinger, candlestick, ohlc |
| Flow | alluvial, chord, sankey |
| Forecast | forecast-fan |
| Genomics / Statistics | manhattan, survival-km, volcano |
| Geospatial | binned-grid-map, dotdensity, hexbin-map, hexmap, map-bars, map-bubble, map-flow, map-pie, map-tilegrid, spike-map |
| Geospatial / Spatial | voronoi |
| Goodness of fit | ppplot, qqplot |
| Gridded field | contour |
| Hierarchy | circle-packing, icicle, org-chart, radial-tree, sunburst, tree |
| Hierarchy / Clustering | dendrogram |
| Hierarchy / Composition | treemap |
| Infographic | pictorial |
| KPI | bullet, gauge, liquid-gauge, progress |
| Matrix / Image | heatmap, imshow-interpolated |
| Meta-analysis | forest |
| Meteorology | windbarb |
| Meteorology / Cyclic | windrose |
| Model evaluation | ablation_matrix, calibration, confusion-matrix, gaussian-process, learning-curve, liftgain, loss-curve, prcurve, roc-curve, silhouette, validation-curve |
| Model explanation | pdp-ice, permutation-importance, shap-beeswarm, shap-waterfall |
| Model selection | elbow |
| Multivariate | andrews, pairplot, radar, radviz |
| Network | arcdiagram, dependency-wheel, edge-bundling, network, sfdp-largegraph |
| Pipeline | funnel, funnel-area |
| Political / Composition | parliament |
| Process control | control-chart |
| Project planning | gantt |
| Quality / Ranking | pareto |
| Range | columnrange |
| Ranking | bump |
| Regression | regression-ci-band |
| Regression diagnostics | residual |
| Relationship | parcoords, scatter |
| Retention | cohort-retention |
| Scattered field | tricontour |
| Serial correlation | acf |
| Set intersection | upset, venn |
| Signal | eventplot, spectrogram, stem |
| Small multiples | facet |
| Table | table |
| Temporal | timeline |
| Text | wordcloud |
| Time series | calendar-heatmap, horizon, line, line-multi, sparkline, step |
| Time series / Composition | streamgraph |
| Vector field | quiver, quiver3d, streamplot |

`choropleth` et `situation_map` ne sont pas ici : ils vivent dans
[sprezzature-maps](https://github.com/warith-harchaoui/sprezzature-maps).

---

## Thèmes visuels

Chaque graphique accepte un paramètre `theme`, qui règle l'apparence
(polices, couleurs), séparé du paramètre `accessibility`, qui garantit que
la palette reste lisible en cas de daltonisme (au sens large : tout trouble
de la vision des couleurs). Les deux se combinent librement parce qu'ils
répondent à deux questions différentes : l'un est affaire de goût, l'autre
détermine qui peut réellement lire le graphique.

- **`"corporate"`** (par défaut) : Roboto pour le texte d'habillage
  (titre, sous-titre, libellés d'axes), Roboto Mono pour les graduations
  et les valeurs numériques, avec une palette catégorielle dérivée des
  couleurs système d'Apple. Le rendu est identique au bit près à tout ce qui
  existait avant l'introduction de `theme`, donc adopter ce paramètre ne
  change rien pour le code déjà en place.
- **`"academic"`** : Latin Modern Roman et Mono, l'extension libre et
  native LaTeX de Computer Modern, pour un rendu façon figure de revue
  scientifique, associée à la palette catégorielle
  [Okabe-Ito](https://jfly.uni-koeln.de/color/) (Masataka OKABE et Kei ITO,
  2002). Cette palette a été conçue pour rester lisible sous les formes
  courantes de daltonisme ; c'est pourquoi elle sert de référence
  recommandée pour les figures scientifiques depuis la chronique de Bang
  WONG, publiée dans *Nature Methods* en 2011.

```python
make_figure("bar", data, out="revenue.svg", theme="academic")
```

```bash
sprezzature-figures render bar --out revenue.svg --theme academic
```

`theme="academic"` bascule aussi les rampes de couleurs séquentielles
(cartes de chaleur, densité hexbin, cartes de clusters, etc.) vers
[viridis](https://bids.github.io/colormap/), la palette perceptuellement
uniforme et sûre pour la vision des couleurs recommandée pour les figures
scientifiques ; `"corporate"` conserve la rampe propre à chaque graphique.

### Polices

La typographie de la suite tient en trois familles Roboto : Roboto (sans
empattement), Roboto Serif et Roboto Mono. Ce paquet est la source unique de
ces fichiers de police pour toute la suite. Les fontes complètes sont dans
`assets/fonts/` et partent dans la roue sous le paquet
`sprezzature_figures_fonts`, à côté de Latin Modern pour le thème académique.
`sprezzature_figures.fonts` expose les piles (`SANS_STACK`, `SERIF_STACK`,
`MONO_STACK`), le répertoire (`FONTS_DIR`) et les aides CSS
(`embedded_font_css()`, `web_font_faces_css()`), pour qu'un autre paquet les
importe au lieu de retaper une pile de polices.

La sortie SVG intègre ses polices et n'a besoin d'aucun chargement externe.
Quand plusieurs figures sont insérées dans une page qui sert déjà ces fontes,
`make_figure(..., embed_fonts=False)` les laisse de côté au lieu de répéter le
même base64 à chaque figure. Les licences sont livrées à côté des
fichiers : SIL Open Font License pour les trois Roboto, GUST Font License
pour Latin Modern. Toutes deux autorisent la redistribution groupée.

---

## Architecture

```
sprezzature-figures/
├── sprezzature_figures/
│   ├── __init__.py        # les noms publics listés dans Démarrage rapide
│   ├── make_figure.py     # répartiteur adossé au registre + les aides des figures
│   ├── cli.py             # la ligne de commande, en Click (sprezzature-figures et make-figure)
│   ├── actions.py         # ce que font redraw / recommend / check, partagé par la CLI
│   ├── api.py             # l'application FastAPI
│   ├── mcp.py             # le serveur MCP, qui enveloppe api.py avec fastapi-mcp
│   ├── options.py         # les mots-clés propres à chaque figure, lus dans sa signature
│   ├── render_checks.py   # check_render()
│   ├── redraw.py          # redraw()
│   ├── fonts.py           # piles et fichiers de police
│   ├── catalog/           # registre des figures : FigureDefinition + figures.json
│   ├── core/              # modèles du domaine de l'éditeur et logique pure
│   └── editor/            # the editor (application NiceGUI, moteur Ralph, recommandation)
├── scripts/
│   ├── make_treemap.py            # un générateur autonome par type
│   ├── make_connected-scatter.py  # les noms avec tiret sont pris en charge
│   └── ...                        # 167 scripts make_*.py au total, plus les outils ci-dessus
├── assets/
│   ├── fonts/             # Roboto, Roboto Serif, Roboto Mono, Latin Modern
│   └── svg-examples/      # un rendu versionné par type
├── tools/                 # maintenance du catalogue, des audits, de la couverture et des comptes
└── tests/
```

Chaque script `make_<type>.py` est autonome : il importe ce dont il a besoin,
définit `make_<type>(data, *, out=None, title="", ...) -> Path` et expose une
liste `DEMO_DATA` pour la CLI et les tests. `make_figure()` résout le type par
`sprezzature_figures/catalog/figures.json` au lieu de deviner le nom de
fichier ; voir
[docs/editor/GENERATOR_AUDIT.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/docs/editor/GENERATOR_AUDIT.md)
pour savoir lesquels des 167 scripts respectent aujourd'hui ce contrat.

---

## Ajouter un type de graphique

1. Créer `scripts/make_<type>.py` sur le modèle de n'importe quel script existant.
2. Exposer `DEMO_DATA: list[dict]` et une fonction `make_<type>(data, *, out=None, title="", ...) -> Path`.
3. Ajouter une ligne dans [FIGURES.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/FIGURES.md).
4. Lancer `python tools/audit_generators.py --render` puis `python tools/build_figures_catalog.py` pour l'enregistrer dans `sprezzature_figures/catalog/figures.json` (sans cela, `make_figure()` ne l'atteint que par un repli déprécié, avec un avertissement).
5. Lancer `python tools/bump_catalogue_count.py` pour que chaque document qui cite la taille du catalogue donne le nouveau nombre.
6. Lancer `sprezzature-figures render <type> --out check.svg` puis `sprezzature-figures check check.svg` pour vérifier la sortie.

---

## the editor

`sprezzature-figures` lance une application NiceGUI locale. Vous importez un
fichier CSV/TSV/XLSX/JSON/JSONL, choisissez un type de graphique (les cartes
de recommandation classent ceux que vos colonnes peuvent remplir), associez
les colonnes, et affinez la figure en discutant avec **Ralph**. Ralph est un
copilote construit sur un modèle de langage qui lit votre texte (un LLM, grand
modèle de langage) et un modèle de vision qui regarde l'image rendue (un VLM,
modèle vision-langage). Il modifie un plan structuré et regarde le PNG rendu
avant de décider qu'il a fini. L'historique (annuler, rétablir, comparer) et
un export reproductible sont dans l'éditeur.

```bash
pip install sprezzature-figures
sprezzature-figures                     # http://127.0.0.1:8080, ouvre un onglet
sprezzature-figures --port 9000 --no-browser
sprezzature-figures --native            # une fenêtre de bureau au lieu d'un onglet
```

Le LLM et le VLM de Ralph sont résolus par
[best-engine-ai-helper](https://github.com/warith-harchaoui/best-engine-ai-helper),
qui s'adresse par défaut à un Ollama local (modèle de texte `qwen3:8b`, modèle
de vision `gemma3:12b` ; à surcharger avec `BEST_LLM_TEXT` / `BEST_LLM_VISION`).
L'application **démarre et reste utilisable sans aucun modèle** : import,
profilage, recommandation, choix manuel du graphique, réglage des propriétés,
historique et export fonctionnent ; seuls la conversation et la critique ont
besoin d'un modèle joignable. Les projets sont rangés sous
`~/.sprezzature-figures/` (à surcharger avec `SPREZZATURE_FIGURES_HOME`). Rien ne
quitte votre machine, sauf si vous la pointez vers un service distant
([DATA_PRIVACY.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/docs/editor/DATA_PRIVACY.md)).

Documentation complète (en anglais) : [docs/editor/README.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/docs/editor/README.md).

---

## API HTTP, MCP et Docker

L'application FastAPI expose les mêmes fonctions en HTTP, pour que le
catalogue serve depuis n'importe quel langage :

| Route | `operation_id` (nom de l'outil MCP) | Ce qu'elle fait |
|---|---|---|
| `GET /health` | `health` | Sonde de vie. |
| `GET /kinds` | `list_kinds` | Le catalogue ; `?status=stable` filtre. |
| `GET /kinds/{kind}` | `get_kind` | La fiche d'un type, rôles de données en tête. |
| `GET /kinds/{kind}/options` | `list_kind_options` | Tous les mots-clés que le type accepte en plus de ses lignes. |
| `POST /recommend` | `recommend_figures` | Classe les types que ces lignes peuvent remplir, avec l'association des colonnes. |
| `POST /render/{kind}` | `render_figure` | Rend la figure et renvoie les octets du fichier. |
| `POST /redraw` | `redraw_figure` | Redessine un graphique à partir d'une image en base64 ; répond en JSON. |
| `POST /check_render` | `check_render` | Contrôle statique d'un SVG rendu ; répond par une liste de constats. |

```bash
uvicorn sprezzature_figures.api:app --host 0.0.0.0 --port 8000

# Lister les types stables
curl http://localhost:8000/kinds?status=stable

# Rendre le treemap de démonstration en SVG
curl -X POST http://localhost:8000/render/treemap -o treemap.svg

# Rendre avec vos propres données
curl -X POST http://localhost:8000/render/bar -H 'Content-Type: application/json' \
     -d '{"data": [{"region": "Nord", "value": 42}], "title": "Mon graphique"}' -o bar.svg

# Ce que ce type accepte d'autre : types, valeurs par défaut, valeurs admises
curl http://localhost:8000/kinds/bar/options

# ...passé dans `options`, sous les noms que cette route a renvoyés
curl -X POST http://localhost:8000/render/bar -H 'Content-Type: application/json' \
     -d '{"options": {"subtitle": "Exercice 2024", "width": 1200, "theme": "academic"}}' -o bar.svg

# Refaire le graphique de quelqu'un d'autre à partir de son image
curl -X POST http://localhost:8000/redraw -H 'Content-Type: application/json' \
     -d "{\"image_base64\": \"$(base64 < le-leur.png)\"}" | jq -r .data_origin

# Documentation OpenAPI complète
open http://localhost:8000/docs
```

Le corps de `POST /render/{kind}` prend `data`, `title`, `format` (`svg`,
`png`, `pdf`, `jpg`, `html`), `scale`, `dark` et `options`. Sans `data`, le
type rend ses lignes de démonstration. Une option que la figure n'accepte pas
revient en 422 avec le nom de celles qu'elle accepte, au lieu d'être perdue en
route. Une ligne à laquelle manque un rôle requis est aussi un 422.

`POST /redraw` répond en JSON plutôt qu'en octets de fichier : la figure
arrive encodée en base64 dans `figure_base64`, à côté du diagnostic qui l'a
justifiée (`kind`, `data_origin`, `changes`, `warnings`, `reading`). Lire
`data_origin` avant d'utiliser la figure est tout l'enjeu ; voir
[À partir de l'image du graphique de quelqu'un d'autre](#à-partir-de-limage-du-graphique-de-quelquun-dautre).

`POST /recommend` prend `data`, `limit` (de 1 à 50, 5 par défaut) et `goal`.
C'est la route à appeler avant `/render/{kind}` chaque fois que personne n'a
nommé de type de graphique.

### MCP

`sprezzature-figures-mcp` sert la même application, avec le point MCP monté
sur `/mcp`, par [fastapi-mcp](https://github.com/tadata-org/fastapi_mcp).
Chaque route du tableau ci-dessus devient un outil MCP nommé d'après son
`operation_id` : `health`, `list_kinds`, `get_kind`, `list_kind_options`,
`recommend_figures`, `render_figure`, `redraw_figure` et `check_render`.
Chacun porte un résumé écrit et une description qui dit **quand** l'appeler ;
voir [TRIGGERS.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/TRIGGERS.md)
pour les règles de routage qu'un agent doit suivre.

```bash
sprezzature-figures-mcp                          # 127.0.0.1:8000, MCP sur /mcp
sprezzature-figures-mcp --host 0.0.0.0 --port 8000
```

Les valeurs par défaut viennent aussi de `SPREZZATURE_FIGURES_HOST` et
`SPREZZATURE_FIGURES_PORT`.

### Docker et Compose

La commande par défaut de l'image est `sprezzature-figures-mcp --host 0.0.0.0
--port 8000` : un seul processus sert les routes HTTP et le point MCP sur
`/mcp`, sur le même port. Il n'y a pas de point d'entrée imposé, donc n'importe
quelle commande du paquet peut la remplacer.

```bash
docker compose up -d                              # l'API et /mcp sur :8000
curl -s localhost:8000/health
docker compose run --rm api sprezzature-figures render bellcurve --out /work/bell.svg
docker compose --profile editor up -d             # + l'éditeur sur :8080
docker compose --profile assist up -d             # + un serveur Ollama pour la conversation et la boucle Eyeball
```

`./work` côté hôte est monté sur `/work` dans les conteneurs. Sans Compose :

```bash
docker build -t sprezzature-figures .
docker run --rm -p 8000:8000 sprezzature-figures   # routes HTTP + /mcp
```

---

## Développement

```bash
git clone https://github.com/warith-harchaoui/sprezzature-figures.git
cd sprezzature-figures
pip install -e ".[dev]"
ruff check .
python -m pytest -q
```

L'exécution par défaut de `pytest` exclut quatre groupes marqués (voir
[docs/editor/TESTING.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/docs/editor/TESTING.md)) :

```bash
python -m pytest -m slow        # rendent réellement des figures (quelques secondes chacun)
python -m pytest -m packaging   # construisent une roue et l'installent dans un venv neuf
python -m pytest -m llm         # interrogent un modèle de texte réel via best-engine-ai-helper
python -m pytest -m vision      # interrogent un modèle de vision / VLM réel
```

Les tests `llm` / `vision` **sont sautés** (jamais en échec) quand aucun modèle
n'est joignable, on peut donc les lancer sans Ollama. La CI exécute la suite
par défaut, `slow` et `packaging`, jamais `llm` ni `vision`. Les vérifications
par Chromium sans interface demandent un `playwright install chromium` unique
après l'installation de `[dev]`.

### Variante : conda

`requirements.txt` tient en une ligne, `-e .`, si bien que `pyproject.toml`
reste la seule liste de dépendances. `environment.yaml` fixe l'interpréteur et
l'installe :

```bash
conda env create -f environment.yaml
conda activate sprezzature-figures
pip install -r requirements-dev.txt   # pytest, ruff, build, playwright, httpx2
playwright install chromium           # une fois, pour les vérifications par Chromium sans interface
```

---

## Licence

BSD 3-Clause. Voir [LICENSE](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/LICENSE).

## Auteur

Warith HARCHAOUI · warithmetics@deraison.ai · [sprezzature.ai](https://sprezzature.ai/)
