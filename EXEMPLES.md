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
(`horsepower`/`mpg`, puissance et consommation) :
`sprezzature-figures describe scatter` en donne le nom exact, et la même
commande répond pour tous les autres types.

```python
import random
data = [{"horsepower": random.uniform(80, 320), "mpg": random.uniform(10, 40)} for _ in range(200)]
path = make_figure("scatter", data, out="nuage.png")
```

## Gapminder (animé)

Sans lignes (une liste vide ou `None`), le graphique Gapminder dessine son
jeu de données intégré. En ligne de commande :

```bash
sprezzature-figures render gapminder --out gapminder.html
```

## Nuage de mots

```python
# `group` vaut « praise », « gripe » ou « neutral » : les trois couleurs du nuage.
data = [
    {"word": "silencieux", "count": 812, "group": "praise"},
    {"word": "fluide", "count": 468, "group": "praise"},
    {"word": "bruyant", "count": 300, "group": "gripe"},
    {"word": "moulin", "count": 250, "group": "neutral"},
]
path = make_figure("wordcloud", data, out="nuage_mots.png")
```

## Refaire le graphique de quelqu'un d'autre à partir de son image

```python
from sprezzature_figures import redraw

# Une capture d'écran, et les chiffres que vous avez vraiment
resultat = redraw(
    "leur-graphique.png",
    out="le-notre.svg",
    data=[{"region": "Nord", "value": 61}, {"region": "Sud", "value": 39}],
    language="fr",
)
print(resultat.kind)         # 'bar' — ce que le modèle de vision a reconnu
print(resultat.data_origin)  # 'your-data' — les chiffres sont les vôtres
for changement in resultat.changes:
    print("-", changement)   # ce qui change, le plus coûteux d'abord

# Sans données sous la main : la refonte sur des lignes d'exemple, légendée
maquette = redraw("leur-graphique.png", out="maquette.svg", language="fr")
maquette.data_origin         # 'demo' — à regarder, pas à publier
```

```bash
sprezzature-figures redraw leur-graphique.png --out le-notre.svg --data ventes.csv
sprezzature-figures redraw leur-graphique.png --kind treemap --language fr
```

Nécessite un modèle de vision (`pip install 'sprezzature-figures'` et un
Ollama qui tourne). Accepte PNG, JPEG, GIF, WebP et SVG (Scalable Vector Graphics, une image écrite en texte).

## Lister tous les types disponibles

```python
from sprezzature_figures import list_kinds
print(list_kinds())
# ['ablation_matrix', 'acf', 'alluvial', 'andrews', 'arcdiagram', 'area', ...]
```

## Exemples en ligne de commande

La commande est `sprezzature-figures`, aussi installée sous le nom `make-figure`.

```bash
# Lister tous les types de graphiques (ajouter --status stable pour ceux
# dont le rendu est vérifié)
sprezzature-figures list --status stable

# Rendre chaque graphique avec ses DEMO_DATA
sprezzature-figures render waterfall --out waterfall.png
sprezzature-figures render funnel --out funnel.png --title "Entonnoir de recrutement"
sprezzature-figures render sunburst --out sunburst.png
sprezzature-figures render heatmap --out heatmap.png
sprezzature-figures render dumbbell --out dumbbell.png --title "Écart de rémunération par poste"

# Rendre son propre fichier plutôt que les données de démonstration
# (.csv, .tsv, .json, .jsonl)
sprezzature-figures render treemap --data budget.csv --out budget.png
sprezzature-figures render bar --data ventes.json --out ventes.svg --title "Ventes par région"

# Envoyer des données par l'entrée standard avec --data -
# (JSON, JSONL ou CSV, détecté au contenu)
curl -s https://exemple.com/ventes.json | sprezzature-figures render bar --data - --out ventes.png

# Suréchantillonner la sortie raster/PDF pour l'écran haute densité avec
# --scale (ignoré pour .svg/.html)
sprezzature-figures render treemap --data budget.csv --out budget@3x.png --scale 3

# Faire correspondre des colonnes à des rôles quand les en-têtes diffèrent
# (répétable)
sprezzature-figures render bar --data pib.csv --map region=Pays --map value=PIB --out pib.png

# Demander à une figure ce qu'elle exige et ce qu'elle accepte, avec les
# valeurs par défaut
sprezzature-figures describe sankey
sprezzature-figures render sankey --help          # les mêmes options, en drapeaux

# Les passer : un drapeau par option, ou --set pour l'écriture scriptable
sprezzature-figures render bar --out ventes.svg --subtitle "Exercice 2024" --width 1200 --theme academic
sprezzature-figures render sankey --out flux.svg --set volume-unit=sessions
sprezzature-figures render bar --out ventes-fr.svg --language fr --accessibility high-contrast

# Demander quels types de graphiques conviennent à son fichier, puis rendre
# le meilleur (classement déterministe, aucun modèle requis)
sprezzature-figures recommend --data ventes.csv
sprezzature-figures recommend --data ventes.csv --render meilleur.png

# Préciser son objectif d'analyse pour que le classement choisisse la figure
# adaptée à cette intention (comparison, trend, distribution, composition,
# relationship, flow, hierarchy, geography, model_evaluation) plutôt que la
# seule lisibilité
sprezzature-figures recommend --data ventes.csv --intent comparison

# Vérifier une figure rendue sur ce que son balisage peut démentir
# (code de sortie 1 au moindre constat)
sprezzature-figures check ventes.svg --expect-title "Ventes par région"
```

Le fichier `budget.csv` ci-dessus n'est qu'un tableau dont les colonnes
correspondent aux rôles du graphique, par exemple :

```csv
parent,name,value
Marketing,Publicité,120
Marketing,Événements,80
Ingénierie,Salaires,300
```

## the editor et le skill pour agent

```bash
# L'éditeur local : les données, un graphique choisi parmi les cartes, le
# panneau Ajuster, un menu Télécharger (SVG, PNG, archive), et Ralph à qui parler
sprezzature-figures

# Poser le skill embarqué par ce paquet là où Claude Code le lit, puis vérifier
sprezzature-figures-skill --install
sprezzature-figures-skill            # « à jour », ou combien de fichiers diffèrent
```
