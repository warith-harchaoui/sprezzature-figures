# sprezzature-figures

🇫🇷 [LISEZMOI.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/LISEZMOI.md) · 🇬🇧 README.md

[![Python ≥3.10](https://img.shields.io/badge/python-%3E%3D3.10-blue)](https://www.python.org/)
[![License: BSD-3-Clause](https://img.shields.io/badge/license-BSD--3--Clause-green)](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/LICENSE)

[![logo](https://raw.githubusercontent.com/warith-harchaoui/sprezzature-figures/main/assets/logo.png)](https://harchaoui.org/warith/sprezzature/)

90 publication-quality chart types — Vega-Lite, full Vega, and matplotlib/SVG — callable as a Python library or a CLI command.

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
    {"region": "North", "value": 42},
    {"region": "South", "value": 28},
    {"region": "East",  "value": 19},
    {"region": "West",  "value": 11},
]
path = make_figure("bar", data, out="revenue.png", title="Revenue by region")
print(path)  # PosixPath('revenue.png')
```

`make_figure()` will attempt any registered chart kind, but only
`status="stable"` kinds are currently render-verified end to end — see
[docs/studio/GENERATOR_AUDIT.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/docs/studio/GENERATOR_AUDIT.md)
for the per-chart status of all 90 types, and `make-figure --list --status stable`
for the ones that render today (12 as of this writing: `bar`, `line`, `area`,
`scatter`, `histogram`, `boxplot`, `heatmap`, `columnrange`, `funnel`,
`sunburst`, `treemap`, `waterfall`).

### As a CLI command

```bash
# List all available chart types (add --status stable to see only render-verified ones)
make-figure --list

# Render a chart using its built-in demo data
make-figure bar --out revenue.png --title "Revenue by region"
make-figure treemap --out budget.png --title "Budget breakdown"
make-figure funnel --out funnel.png
```

---

## Chart catalogue

90 chart types across 21 categories. See [FIGURES.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/FIGURES.md) for the full table with per-chart guidance on when to use each type.

Quick overview:

| Category | Charts |
|----------|--------|
| Comparison | bar, bar3d, columnrange, difference-chart, dotplot, dumbbell, packed-bubble, pareto, radial-bar, variwide, waterfall |
| Composition | area, parliament, pictorial, ternary, waffle |
| Distribution | bellcurve, blandaltman, boxen, boxplot, histogram, mosaic, ridgeline, rug |
| Flow | alluvial, chord, funnel, parallel-sets, sankey |
| Geospatial | binned-grid-map, dotdensity, globe3d, hexbin-map, hexmap, situation_map, spike-map, voronoi |
| Hierarchy | circle-packing, convex-hull, dendrogram, icicle, org-chart, radial-tree, sunburst, tree, treemap |
| KPI | bullet, gauge, liquid-gauge |
| Matrix / Image | heatmap, imshow-interpolated |
| Meteorology | windbarb, windrose |
| Model evaluation | calibration, liftgain, manhattan, ppplot, prcurve |
| Network | arcdiagram, dependency-wheel, edge-bundling, network, sfdp-largegraph |
| Regression | residual |
| Relationship | scatter |
| Signal | spectrogram, streamplot |
| Text | wordcloud |
| 3-D | scatter3d, wireframe3d |
| Time series | bollinger, connected-scatter, horizon, line, streamgraph, timeline |
| Multivariate | andrews, embedding_projector, jointplot, pairplot, radar, radviz, upset, venn |
| Meta-analysis | forest |
| Animated | gapminder, gapminder_variants |
| Other | polar, rose, speaking_time |

---

## Architecture

```
sprezzature-figures/
├── sprezzature_figures/
│   ├── __init__.py        # exports make_figure, list_kinds, get_figure_definition
│   ├── make_figure.py     # registry-backed dispatcher + argparse CLI
│   ├── cli.py             # Click entry point (optional, needs [cli] extra)
│   └── catalog/           # figure registry: FigureDefinition + figures.json
├── scripts/
│   ├── make_treemap.py            # self-contained chart script
│   ├── make_connected-scatter.py  # hyphenated kinds are supported
│   └── ...                        # 90 make_*.py scripts total
├── assets/
│   ├── vega-examples/     # Vega-Lite and full-Vega spec examples
│   └── svg-examples/      # SVG template examples
├── references/            # upstream chart documentation
└── tests/
```

Each `make_<kind>.py` script is self-contained: it imports what it needs, defines `make_<kind>(data, *, out=None, title="", ...) -> Path` and exposes a `DEMO_DATA` list for CLI and test use. `make_figure()` resolves the kind through `sprezzature_figures/catalog/figures.json` rather than guessing the filename — see [docs/studio/GENERATOR_AUDIT.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/docs/studio/GENERATOR_AUDIT.md) for which of the 90 scripts currently satisfy this contract.

---

## Adding a chart type

1. Create `scripts/make_<kind>.py` following the pattern of any existing script.
2. Expose `DEMO_DATA: list[dict]` and a function `make_<kind>(data, *, out=None, title="", ...) -> Path`.
3. Add a row to [FIGURES.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/FIGURES.md).
4. Run `python tools/audit_generators.py --render` then `python tools/build_figures_catalog.py` to register it in `sprezzature_figures/catalog/figures.json` (without this, `make_figure()` only reaches it through a deprecated fallback and prints a warning).
5. Run `make-figure <kind>` to verify the output.

---

## Sprezzature Studio

This repository is two things:

- **The library** (`sprezzature_figures.make_figure`, `make-figure`,
  `sprezzature-figures` CLI) — everything above. No extra dependencies
  beyond `[cli]`/`[dataviz]`.
- **Sprezzature Studio** (`sprezzature_figures.studio`, `sprezzature-studio`
  CLI) — a local NiceGUI app to import a CSV/XLSX, pick a chart type, bind
  columns, and refine the figure by chatting with **Ralph**, an LLM/VLM
  copilot that edits a structured plan and actually looks at the rendered
  PNG before deciding it's done. Needs the `studio` extra:

  ```bash
  pip install "sprezzature-figures[studio]"
  sprezzature-studio
  ```

  Full documentation: [docs/studio/README.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/docs/studio/README.md).

There is no separate "Ralph CLI" in this repository — `scripts/
ralph_eyeball_loop.py` is a standalone, repo-internal visual-QA tool used
while developing the chart generators themselves (see its own docstring);
it predates and is unrelated to the Studio's Ralph engine
(`sprezzature_figures.studio.ralph`), which is a from-scratch,
plan-driven, testable implementation.

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

BSD 3-Clause — see [LICENSE](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/LICENSE).

## Author

Warith Harchaoui — warith.harchaoui@gmail.com — [harchaoui.org/warith/sprezzature](https://harchaoui.org/warith/sprezzature/)
