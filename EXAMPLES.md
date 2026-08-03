# Examples

All examples use `make_figure(kind, data, **kwargs)` from `sprezzature_figures`.

## Bar chart

```python
from sprezzature_figures import make_figure

data = [
    {"region": "Q1", "value": 120},
    {"region": "Q2", "value": 95},
    {"region": "Q3", "value": 140},
    {"region": "Q4", "value": 175},
]
path = make_figure("bar", data, out="quarterly.png", title="Quarterly revenue")
```

## Treemap (hierarchical budget)

```python
data = [
    {"parent": "Engineering", "name": "Backend", "value": 40},
    {"parent": "Engineering", "name": "Frontend", "value": 20},
    {"parent": "Marketing", "name": "Digital", "value": 25},
    {"parent": "Marketing", "name": "Events", "value": 15},
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

`scatter`'s required roles are named after its demo scenario
(horsepower/mpg); see `make-figure --list --status stable` and each
kind's entry in [FIGURES.md](FIGURES.md) for the exact role names a given
chart expects.

```python
import random
data = [{"horsepower": random.uniform(80, 320), "mpg": random.uniform(10, 40)} for _ in range(200)]
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
# List all chart types (add --status stable for the render-verified ones)
make-figure --list --status stable

# Render each chart with its DEMO_DATA
make-figure waterfall --out waterfall.png
make-figure funnel --out funnel.png --title "Hiring funnel"
make-figure sunburst --out sunburst.png
make-figure heatmap --out heatmap.png
make-figure dumbbell --out dumbbell.png --title "Pay gap by role"

# Render your own file instead of the demo data (.csv, .tsv, .json, .jsonl)
make-figure treemap --data budget.csv --out budget.png
make-figure bar --data sales.json --out sales.svg --title "Sales by region"

# Pipe data in from stdin with --data - (JSON, JSONL, or CSV, sniffed from content)
curl -s https://example.com/sales.json | make-figure bar --data - --out sales.png

# Upsample raster/PDF output for hi-DPI with --scale (ignored for .svg/.html)
make-figure treemap --data budget.csv --out budget@3x.png --scale 3

# Bind columns to roles when the headers differ (repeatable)
make-figure bar --data gdp.csv --map region=Country --map value=GDP --out gdp.png

# Ask which chart types fit your file, then render the best one
# (needs the [cli] + [studio] extras; no model involved)
sprezzature-figures recommend --data sales.csv
sprezzature-figures recommend --data sales.csv --render best.png

# State your analytical goal so the ranking picks the figure for that intent
# (comparison, trend, distribution, composition, relationship, flow,
#  hierarchy, geography, model_evaluation) instead of readability alone
sprezzature-figures recommend --data sales.csv --intent comparison
```

`budget.csv` above is just a table whose columns match the chart's roles, e.g.

```csv
parent,name,value
Marketing,Ads,120
Marketing,Events,80
Engineering,Salaries,300
```
