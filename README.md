# sprezzature-figures

🇫🇷 [LISEZMOI.md](LISEZMOI.md) · 🇬🇧 README.md

[![Python ≥3.10](https://img.shields.io/badge/python-%3E%3D3.10-blue)](https://www.python.org/)
[![License: BSD-3-Clause](https://img.shields.io/badge/license-BSD--3--Clause-green)](LICENSE)

[![logo](assets/logo.png)](https://harchaoui.org/warith/sprezzature/)

84 publication-quality chart types — Vega-Lite, full Vega, and matplotlib/SVG — callable as a Python library or a CLI command.

Part of the [sprezzature](https://harchaoui.org/warith/sprezzature/) suite.

---

## Install

```bash
pip install sprezzature-figures
```

With the optional Click CLI:

```bash
pip install "sprezzature-figures[cli]"
```

---

## Quick start

### As a library

```python
from sprezzature_figures import make_figure

data = [
    {"label": "North", "value": 42},
    {"label": "South", "value": 28},
    {"label": "East",  "value": 19},
    {"label": "West",  "value": 11},
]
path = make_figure("bar", data, out="revenue.png", title="Revenue by region")
print(path)  # PosixPath('revenue.png')
```

### As a CLI command

```bash
# List all available chart types
make-figure --list

# Render a chart using its built-in demo data
make-figure treemap --out budget.png --title "Budget breakdown"
make-figure gapminder --out gapminder.html
make-figure sankey --out energy-flow.png
```

---

## Chart catalogue

84 chart types across 15 categories. See [FIGURES.md](FIGURES.md) for the full table with per-chart guidance on when to use each type.

Quick overview:

| Category | Charts |
|----------|--------|
| Comparison | bar3d, bullet, columnrange, dotplot, dumbbell, pareto, variwide |
| Composition | circle-packing, mosaic, packed-bubble, parliament, pictorial, sunburst, treemap, waffle |
| Distribution | andrews, bellcurve, boxen, jointplot, pairplot, ridgeline, rug |
| Flow | alluvial, chord, dependency-wheel, funnel, parallel-sets, sankey, streamgraph |
| Geospatial | binned-grid-map, dotdensity, globe3d, hexbin-map, hexmap, situation_map, spike-map, voronoi |
| Hierarchy | dendrogram, icicle, org-chart, radial-tree, tree |
| KPI | gauge, liquid-gauge |
| Meteorology | windbarb, windrose |
| Model evaluation | calibration, liftgain, prcurve |
| Network | arcdiagram, edge-bundling, network, sfdp-largegraph |
| Regression | blandaltman, ppplot, residual |
| Signal | spectrogram |
| Text | wordcloud |
| 3-D | scatter3d, wireframe3d |
| Time series | bollinger, connected-scatter, difference-chart, horizon, streamplot, timeline |
| Multivariate | convex-hull, embedding_projector, polar, radar, radial-bar, radviz, ternary, venn, upset |
| Meta-analysis | forest |
| Animated | gapminder |
| Other | rose, speaking_time |

---

## Architecture

```
sprezzature-figures/
├── sprezzature_figures/
│   ├── __init__.py        # exports make_figure
│   ├── make_figure.py     # dispatcher + list_kinds() + argparse CLI
│   └── cli.py             # Click entry point (optional)
├── scripts/
│   ├── make_bar.py        # self-contained chart script
│   ├── make_treemap.py    # ...
│   └── ...                # 84 make_*.py scripts total
├── assets/
│   ├── vega-examples/     # Vega-Lite and full-Vega spec examples
│   └── svg-examples/      # SVG template examples
├── references/            # upstream chart documentation
└── tests/
```

Each `make_<kind>.py` script is self-contained: it imports what it needs, defines `make_<kind>(data, **kwargs) -> str` and exposes a `DEMO_DATA` list for CLI and test use.

---

## Adding a chart type

1. Create `scripts/make_<kind>.py` following the pattern of any existing script.
2. Expose `DEMO_DATA: list[dict]` and a function `make_<kind>(data, **kwargs) -> str`.
3. Add a row to [FIGURES.md](FIGURES.md).
4. Run `make-figure <kind>` to verify the output.

---

## Development

```bash
git clone https://github.com/warith-harchaoui/sprezzature-figures.git
cd sprezzature-figures
pip install -e ".[dev,cli]"
ruff check sprezzature_figures/
python -m pytest tests/ -q
```

Slow render tests (require display or vl-convert):

```bash
python -m pytest -m slow tests/
```

---

## License

BSD 3-Clause — see [LICENSE](LICENSE).

## Author

Warith Harchaoui — warith.harchaoui@gmail.com — [harchaoui.org/warith/sprezzature](https://harchaoui.org/warith/sprezzature/)
