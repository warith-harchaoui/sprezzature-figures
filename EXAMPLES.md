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
(horsepower/mpg); `sprezzature-figures describe scatter` prints the exact
role names, and the same command answers for every other kind.

```python
import random
data = [{"horsepower": random.uniform(80, 320), "mpg": random.uniform(10, 40)} for _ in range(200)]
path = make_figure("scatter", data, out="scatter.png")
```

## Gapminder (animated)

With no rows (an empty list or `None`), the Gapminder chart draws its built-in dataset. From the command line:

```bash
sprezzature-figures render gapminder --out gapminder.html
```

## Word cloud

```python
# `group` is one of "praise", "gripe" or "neutral": the three colours of the cloud.
data = [
    {"word": "quiet", "count": 812, "group": "praise"},
    {"word": "smooth", "count": 468, "group": "praise"},
    {"word": "noisy", "count": 300, "group": "gripe"},
    {"word": "grinder", "count": 250, "group": "neutral"},
]
path = make_figure("wordcloud", data, out="cloud.png")
```

## Redraw somebody else's chart from a picture of it

```python
from sprezzature_figures import redraw

# A screenshot, and the numbers you actually have
result = redraw(
    "their-chart.png",
    out="ours.svg",
    data=[{"region": "North", "value": 61}, {"region": "South", "value": 39}],
)
print(result.kind)         # 'bar' -- what the vision model saw
print(result.data_origin)  # 'your-data' -- the numbers are yours, not read off pixels
for change in result.changes:
    print("-", change)     # what the redraw does differently, costliest first

# No data to hand: you get the redesign on sample rows, captioned as such
mockup = redraw("their-chart.png", out="mockup.svg")
mockup.data_origin         # 'demo' -- look at it, don't publish it
```

```bash
sprezzature-figures redraw their-chart.png --out ours.svg --data sales.csv
sprezzature-figures redraw their-chart.png --kind treemap --language fr
```

Needs a vision model (`pip install 'sprezzature-figures'` and a running
Ollama). Accepts PNG, JPEG, GIF, WebP and SVG.

## List all available kinds

```python
from sprezzature_figures import list_kinds
print(list_kinds())
# ['ablation_matrix', 'acf', 'alluvial', 'andrews', 'arcdiagram', 'area', ...]
```

## CLI examples

```bash
# List all chart types (add --status stable for the render-verified ones)
sprezzature-figures list --status stable

# Render each chart with its DEMO_DATA
sprezzature-figures render waterfall --out waterfall.png
sprezzature-figures render funnel --out funnel.png --title "Hiring funnel"
sprezzature-figures render sunburst --out sunburst.png
sprezzature-figures render heatmap --out heatmap.png
sprezzature-figures render dumbbell --out dumbbell.png --title "Pay gap by role"

# Render your own file instead of the demo data (.csv, .tsv, .json, .jsonl)
sprezzature-figures render treemap --data budget.csv --out budget.png
sprezzature-figures render bar --data sales.json --out sales.svg --title "Sales by region"

# Pipe data in from stdin with --data - (JSON, JSONL, or CSV, sniffed from content)
curl -s https://example.com/sales.json | sprezzature-figures render bar --data - --out sales.png

# Upsample raster/PDF output for hi-DPI with --scale (ignored for .svg/.html)
sprezzature-figures render treemap --data budget.csv --out budget@3x.png --scale 3

# Bind columns to roles when the headers differ (repeatable)
sprezzature-figures render bar --data gdp.csv --map region=Country --map value=GDP --out gdp.png

# Ask a figure what it needs and what it accepts, with every default
sprezzature-figures describe sankey
sprezzature-figures render sankey --help          # the same options, as flags

# Set them: one flag per option, or --set for the scriptable spelling
sprezzature-figures render bar --out sales.svg --subtitle "FY-2024" --width 1200 --theme academic
sprezzature-figures render sankey --out flow.svg --set volume-unit=sessions
sprezzature-figures render bar --out sales-fr.svg --language fr --accessibility high-contrast

# Ask which chart types fit your file, then render the best one
# (deterministic, no model involved)
sprezzature-figures recommend --data sales.csv
sprezzature-figures recommend --data sales.csv --render best.png

# State your analytical goal so the ranking picks the figure for that intent
# (comparison, trend, distribution, composition, relationship, flow,
#  hierarchy, geography, model_evaluation) instead of readability alone
sprezzature-figures recommend --data sales.csv --intent comparison

# Check a rendered figure for what its markup can prove wrong (exit 1 on a finding)
sprezzature-figures check sales.svg --expect-title "Sales by region"
```

`budget.csv` above is just a table whose columns match the chart's roles, e.g.

```csv
parent,name,value
Marketing,Ads,120
Marketing,Events,80
Engineering,Salaries,300
```
