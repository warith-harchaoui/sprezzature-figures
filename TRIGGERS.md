# Triggers

Natural-language phrases that should invoke `sprezzature-figures`.

## English

- "make a chart"
- "draw a graph"
- "visualise / visualize this data"
- "plot this"
- "render a figure"
- "I need a bar chart / treemap / scatter plot / sankey / …"
- "show me a data visualisation"
- "create a publication-quality figure"
- "what chart types are available?"
- "list the chart kinds"
- "make a Gapminder animation"
- "generate a wordcloud"
- "draw a network graph"
- "visualise these embeddings"
- "produce a waffle chart"
- "run the eyeball loop on this figure"
- "QA this chart visually"
- "redraw this chart"
- "make this ugly chart better"
- "here is a screenshot of a chart, can you improve it"
- "my colleague sent me this graph, make it readable"
- "rebuild this figure with your tool"
- "what is wrong with this chart?"

## Français

- "faire un graphique"
- "dessiner un diagramme"
- "visualiser ces données"
- "tracer ce graphe"
- "générer une figure"
- "j'ai besoin d'un histogramme / carte proportionnelle / nuage de points / …"
- "afficher une visualisation de données"
- "créer une figure de qualité publication"
- "quels types de graphiques sont disponibles ?"
- "liste des types de graphiques"
- "faire une animation Gapminder"
- "générer un nuage de mots"
- "dessiner un graphe de réseau"
- "visualiser ces plongements"
- "refaire ce graphique"
- "rendre ce graphique plus lisible"
- "voici une capture d'un graphique, tu peux l'améliorer ?"
- "un collègue m'a envoyé ce graphe, rends-le lisible"
- "reconstruire cette figure avec ton outil"
- "qu'est-ce qui ne va pas dans ce graphique ?"
- "produire un diagramme en gaufre"
- "passer la boucle Eyeball sur cette figure"
- "contrôle qualité visuel de ce graphique"

## Typical call pattern

```python
from sprezzature_figures import make_figure

path = make_figure(kind, data, out="output.png", title="My chart")
```

All 127 kinds and their expected `data` shape are documented in [FIGURES.md](FIGURES.md).
