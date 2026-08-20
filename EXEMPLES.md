# Exemples

Tous les exemples utilisent `make_figure(kind, data, **kwargs)` depuis `sprezzature_figures`.

## Diagramme en barres

```python
from sprezzature_figures import make_figure

data = [
    {"region": "T1", "value": 120},
    {"region": "T2", "value": 95},
    {"region": "T3", "value": 140},
    {"region": "T4", "value": 175},
]
path = make_figure("bar", data, out="revenu_trimestriel.png", title="Revenu trimestriel")
```

## Treemap (budget hiérarchique)

```python
data = [
    {"parent": "Ingénierie", "name": "Backend", "value": 40},
    {"parent": "Ingénierie", "name": "Frontend", "value": 20},
    {"parent": "Marketing", "name": "Digital", "value": 25},
    {"parent": "Marketing", "name": "Événements", "value": 15},
]
path = make_figure("treemap", data, out="budget.png", title="Répartition du budget")
```

## Sankey (flux d'énergie)

```python
data = [
    {"source": "Charbon", "target": "Électricité", "value": 120},
    {"source": "Gaz",  "target": "Électricité", "value": 80},
    {"source": "Électricité", "target": "Industrie", "value": 90},
    {"source": "Électricité", "target": "Foyers",    "value": 110},
]
path = make_figure("sankey", data, out="energie.png", title="Flux d'énergie")
```

## Nuage de points (bivarié)

Les rôles requis par `scatter` portent le nom de son scénario de démonstration
(`horsepower`/`mpg`, puissance et consommation) : voir
`make-figure --list --status stable` et la fiche de chaque type dans
[FIGURES.md](FIGURES.md) pour le nom exact des rôles qu'un graphique donné
attend.

```python
import random
data = [{"horsepower": random.uniform(80, 320), "mpg": random.uniform(10, 40)} for _ in range(200)]
path = make_figure("scatter", data, out="nuage.png")
```

## Gapminder (animé)

Le graphique Gapminder utilise son propre jeu de données intégré ; on lui
passe une liste vide, ou on appelle directement la CLI :

```bash
make-figure gapminder --out gapminder.html
```

## Nuage de mots

```python
data = [
    {"word": "Python", "weight": 100},
    {"word": "donnée", "weight": 80},
    {"word": "graphique", "weight": 60},
    {"word": "figure", "weight": 50},
]
path = make_figure("wordcloud", data, out="nuage_mots.png")
```

## Lister tous les types disponibles

```python
from sprezzature_figures.make_figure import list_kinds
print(list_kinds())
# ['alluvial', 'andrews', 'arcdiagram', 'bar3d', 'bellcurve', ...]
```

## Exemples en ligne de commande

```bash
# Lister tous les types de graphiques (ajouter --status stable pour ceux
# dont le rendu est vérifié)
make-figure --list --status stable

# Rendre chaque graphique avec ses DEMO_DATA
make-figure waterfall --out waterfall.png
make-figure funnel --out funnel.png --title "Entonnoir de recrutement"
make-figure sunburst --out sunburst.png
make-figure heatmap --out heatmap.png
make-figure dumbbell --out dumbbell.png --title "Écart de rémunération par poste"

# Rendre son propre fichier plutôt que les données de démonstration
# (.csv, .tsv, .json, .jsonl)
make-figure treemap --data budget.csv --out budget.png
make-figure bar --data ventes.json --out ventes.svg --title "Ventes par région"

# Envoyer des données par l'entrée standard avec --data -
# (JSON, JSONL ou CSV, détecté au contenu)
curl -s https://exemple.com/ventes.json | make-figure bar --data - --out ventes.png

# Suréchantillonner la sortie raster/PDF pour l'écran haute densité avec
# --scale (ignoré pour .svg/.html)
make-figure treemap --data budget.csv --out budget@3x.png --scale 3

# Faire correspondre des colonnes à des rôles quand les en-têtes diffèrent
# (répétable)
make-figure bar --data pib.csv --map region=Pays --map value=PIB --out pib.png

# Demander quels types de graphiques conviennent à son fichier, puis rendre
# le meilleur (nécessite les extras [cli] + [studio], aucun modèle requis)
sprezzature-figures recommend --data ventes.csv
sprezzature-figures recommend --data ventes.csv --render meilleur.png

# Préciser son objectif d'analyse pour que le classement choisisse la figure
# adaptée à cette intention (comparison, trend, distribution, composition,
# relationship, flow, hierarchy, geography, model_evaluation) plutôt que la
# seule lisibilité
sprezzature-figures recommend --data ventes.csv --intent comparison
```

Le fichier `budget.csv` ci-dessus n'est qu'un tableau dont les colonnes
correspondent aux rôles du graphique, par exemple :

```csv
parent,name,value
Marketing,Publicité,120
Marketing,Événements,80
Ingénierie,Salaires,300
```
