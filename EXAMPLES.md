# Examples

All examples use `make_figure(kind, data, **kwargs)` from `sprezzature_figures`.

## Bar chart

```python
from sprezzature_figures import make_figure

data = [
    {"label": "Q1", "value": 120},
    {"label": "Q2", "value": 95},
    {"label": "Q3", "value": 140},
    {"label": "Q4", "value": 175},
]
path = make_figure("bar", data, out="quarterly.png", title="Quarterly revenue")
```

## Treemap (hierarchical budget)

```python
data = [
    {"path": ["Engineering", "Backend"], "value": 40},
    {"path": ["Engineering", "Frontend"], "value": 20},
    {"path": ["Marketing", "Digital"], "value": 25},
    {"path": ["Marketing", "Events"], "value": 15},
]
path = make_figure("treemap", data, out="budget.png", title="Budget breakdown")
```

## Sankey (energy flow)

```python
data = [
    {"source": "Coal", "target": "Electricity", "value": 120},
    {"source": "Gas",  "target": "Electricity", "value": 80},
    {"source": "Electricity", "target": "Industry", "value": 90},
    {"source": "Electricity", "target": "Homes",    "value": 110},
]
path = make_figure("sankey", data, out="energy.png", title="Energy flow")
```

## Scatter (bivariate)

```python
import random
data = [{"x": random.gauss(0, 1), "y": random.gauss(0, 1)} for _ in range(200)]
path = make_figure("scatter", data, out="scatter.png")
```

## Gapminder (animated)

The Gapminder chart uses its built-in dataset; pass an empty list or use the CLI:

```bash
make-figure gapminder --out gapminder.html
```

## Word cloud

```python
data = [
    {"word": "Python", "weight": 100},
    {"word": "data", "weight": 80},
    {"word": "chart", "weight": 60},
    {"word": "figure", "weight": 50},
]
path = make_figure("wordcloud", data, out="cloud.png")
```

## List all available kinds

```python
from sprezzature_figures.make_figure import list_kinds
print(list_kinds())
# ['alluvial', 'andrews', 'arcdiagram', 'bar3d', 'bellcurve', ...]
```

## CLI examples

```bash
# List all chart types
make-figure --list

# Render each chart with its DEMO_DATA
make-figure waterfall --out waterfall.png
make-figure funnel --out funnel.png --title "Hiring funnel"
make-figure sunburst --out sunburst.png
make-figure venn --out venn.png
make-figure radar --out radar.png --title "Skills profile"
```
