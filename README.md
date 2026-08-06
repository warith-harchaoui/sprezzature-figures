# sprezzature-figures

🇫🇷 [LISEZMOI.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/LISEZMOI.md) · 🇬🇧 README.md

[![Python ≥3.10](https://img.shields.io/badge/python-%3E%3D3.10-blue)](https://www.python.org/)
[![License: BSD-3-Clause](https://img.shields.io/badge/license-BSD--3--Clause-green)](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/LICENSE)

[![logo](https://raw.githubusercontent.com/warith-harchaoui/sprezzature-figures/main/assets/logo.png)](https://harchaoui.org/warith/sprezzature/)

96 publication-quality chart types, almost all hand-authored SVG (no Vega) with a handful of matplotlib-based statistical outputs (causal inference, explainability), callable as a Python library or a CLI command.

Part of the [sprezzature](https://harchaoui.org/warith/sprezzature/) suite.

---

## Install

Requires **Python 3.10–3.13**. Tested on 🍎 macOS, 🐧 Ubuntu, and 🪟 Windows
(CI runs the full suite plus a wheel-install check on all three).

```bash
pip install sprezzature-figures
```

Optional extras (combine as needed, e.g. `"sprezzature-figures[cli,dataviz]"`):

| Extra | Adds |
|-------|------|
| `[cli]` | the Click twin of the always-installed `make-figure` CLI |
| `[dataviz]` | matplotlib / networkx / wordcloud / shapely / pyproj / pyyaml, needed for the small set of matplotlib-based generators (causal inference, explainability) |
| `[studio]` | Sprezzature Studio: the NiceGUI app + Ralph copilot (see below) |
| `[api]` | FastAPI HTTP surface (see below) |
| `[mcp]` | MCP tool surface on top of `[api]` (see below) |

Use a virtual environment to keep things isolated:

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

Verify the install:

```bash
make-figure --list --status stable
make-figure bar --out check.svg
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
`status="stable"` kinds are currently render-verified end to end; see
[docs/studio/GENERATOR_AUDIT.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/docs/studio/GENERATOR_AUDIT.md)
for the per-chart status of all 91 types, and `make-figure --list --status stable`
for the ones that render today (15 as of this writing: `area`, `bar`, `boxplot`,
`columnrange`, `dumbbell`, `funnel`, `heatmap`, `histogram`, `line`, `sankey`,
`scatter`, `sunburst`, `treemap`, `waffle`, `waterfall`). Every stable kind
tolerates optional roles being left unbound: it renders a sensible default
rather than crashing.

### As a CLI command

```bash
# List all available chart types (add --status stable to see only render-verified ones)
make-figure --list

# Render a chart using its built-in demo data
make-figure bar --out revenue.png --title "Revenue by region"
make-figure treemap --out budget.png --title "Budget breakdown"
make-figure funnel --out funnel.png

# Render your own data instead of the demo rows (.csv, .tsv, .json, .jsonl)
make-figure treemap --data budget.csv --out budget.png --title "Budget breakdown"

# When your columns don't match the figure's role names, bind them with --map
make-figure bar --data gdp.csv --map region=Country --map value=GDP --out gdp.png

# Pipe data in with --data - and upsample the raster with --scale
cat sales.jsonl | make-figure bar --data - --out sales@2x.png --scale 2
```

The output format follows the `--out` extension: `.svg` (default, fully
self-contained with embedded fonts), `.png`, `.pdf`, `.jpg`, or `.html`. For
raster and PDF output, `--scale N` upsamples N times for hi-DPI displays
(`--out chart.png --scale 3`); it is ignored for the vector `.svg`/`.html`
forms.

The `--data` file is read into one row dict per record: CSV/TSV cells are
type-coerced (numbers stay numbers), and JSON accepts either a bare array of
objects or an object wrapping a `"data"` array. Pass `--data -` to read the
same formats from standard input (the shape is sniffed from the content).
Column names should match the
roles the chart expects (`make-figure --list --status stable`, then see
[FIGURES.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/FIGURES.md));
when they don't, `--map role=column` binds them without touching the file.

Not sure which chart fits your file? Ask for a recommendation (needs the
`[cli]` and `[studio]` extras). This runs the same deterministic
compatibility + readability ranking the Studio GUI shows as cards, with no
model involved:

```bash
sprezzature-figures recommend --data budget.csv
sprezzature-figures recommend --data budget.csv --render best.png  # + render the top pick
sprezzature-figures recommend --data budget.csv --intent hierarchy  # rank for a goal
```

Add `--intent GOAL` (`comparison`, `trend`, `distribution`, `composition`,
`relationship`, `flow`, `hierarchy`, `geography`, `model_evaluation`) to rank
the figures that serve that goal first. Without it, many kinds tie at the top
because readability alone rarely separates them; the goal is what makes the
ranking decisive.

---

## Chart catalogue

91 chart types across 21 categories. See [FIGURES.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/FIGURES.md) for the full table with per-chart guidance on when to use each type.

Quick overview:

| Category | Charts |
|----------|--------|
| Comparison | bar, bar3d, columnrange, difference-chart, dotplot, dumbbell, packed-bubble, pareto, radial-bar, variwide, waterfall |
| Composition | area, parliament, pictorial, ternary, waffle |
| Distribution | bellcurve, blandaltman, boxen, boxplot, histogram, mosaic, ridgeline, rug |
| Flow | alluvial, chord, funnel, parallel-sets, sankey |
| Geospatial | binned-grid-map, dotdensity, hexbin-map, hexmap, situation_map, spike-map, voronoi |
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

Each `make_<kind>.py` script is self-contained: it imports what it needs, defines `make_<kind>(data, *, out=None, title="", ...) -> Path` and exposes a `DEMO_DATA` list for CLI and test use. `make_figure()` resolves the kind through `sprezzature_figures/catalog/figures.json` rather than guessing the filename; see [docs/studio/GENERATOR_AUDIT.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/docs/studio/GENERATOR_AUDIT.md) for which of the 90 scripts currently satisfy this contract.

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
  `sprezzature-figures` CLI): everything above, with no extra dependencies
  beyond `[cli]`/`[dataviz]`.
- **Sprezzature Studio** (`sprezzature_figures.studio`, `sprezzature-studio`
  CLI): a local NiceGUI app to import a CSV/TSV/XLSX/JSON file, pick a chart type, bind
  columns, and refine the figure by chatting with **Ralph**, an LLM/VLM
  copilot that edits a structured plan and actually looks at the rendered
  PNG before deciding it's done. Needs the `studio` extra:

  ```bash
  pip install "sprezzature-figures[studio]"
  sprezzature-studio
  ```

  Ralph's LLM/VLM is resolved by
  [best-engine-ai-helper](https://github.com/warith-harchaoui/best-engine-ai-helper),
  which talks to a local Ollama by default (text model `qwen3:8b`, vision model
  `gemma3:12b`; override with `BEST_LLM_TEXT` / `BEST_LLM_VISION`). The app
  **starts and stays fully usable with no model at all**: import, profiling,
  manual chart choice, property tweaks, history, and export all work in
  degraded mode; only the chat/critique features need a reachable model. Nothing
  leaves your machine unless you point it at a remote backend
  ([DATA_PRIVACY.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/docs/studio/DATA_PRIVACY.md)).

  Full documentation: [docs/studio/README.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/docs/studio/README.md).

There is no separate "Ralph CLI" in this repository. `scripts/
ralph_eyeball_loop.py` is a standalone, repo-internal visual-QA tool used
while developing the chart generators themselves (see its own docstring);
it predates and is unrelated to the Studio's Ralph engine
(`sprezzature_figures.studio.ralph`), which is a from-scratch,
plan-driven, testable implementation.

---

## HTTP API & MCP

Three interfaces expose the same `make_figure()` dispatcher:

| Interface | Always installed? | Entry point |
|---|---|---|
| CLI (argparse) | Yes | `make-figure` |
| CLI (Click) | `[cli]` extra | `sprezzature-figures` |
| HTTP API (FastAPI) | `[api]` extra | `uvicorn sprezzature_figures.api:app` |
| MCP tools (fastapi-mcp) | `[api,mcp]` extras | `sprezzature-figures-mcp` |

```bash
pip install "sprezzature-figures[api]"
uvicorn sprezzature_figures.api:app --host 0.0.0.0 --port 8000

# List stable chart kinds
curl http://localhost:8000/kinds?status=stable

# Render the demo treemap as SVG
curl -X POST http://localhost:8000/render/treemap -o treemap.svg

# Render your own data
curl -X POST http://localhost:8000/render/bar -H 'Content-Type: application/json' \
     -d '{"data": [{"region": "North", "value": 42}], "title": "My chart"}' -o bar.svg

# Full OpenAPI docs
open http://localhost:8000/docs
```

The MCP surface (`sprezzature-figures[api,mcp]`) exposes the exact same
routes as MCP tools (`list_kinds`, `get_kind`, `render_figure`) at `/mcp`
on the same FastAPI app.
[fastapi-mcp](https://github.com/tadata-org/fastapi_mcp) wraps the whole
HTTP surface in one line, so the route definitions are never duplicated:

```bash
pip install "sprezzature-figures[api,mcp]"
sprezzature-figures-mcp
```

---

## Development

```bash
git clone https://github.com/warith-harchaoui/sprezzature-figures.git
cd sprezzature-figures
pip install -e ".[dev,cli]"
ruff check sprezzature_figures/
python -m pytest tests/ -q
```

The default `pytest` run excludes four marked groups (see
[docs/studio/TESTING.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/docs/studio/TESTING.md)):

```bash
python -m pytest -m slow        # actually render figures (seconds each)
python -m pytest -m packaging   # build a wheel, install it in a fresh venv
python -m pytest -m llm         # hit a live text model via best-engine-ai-helper
python -m pytest -m vision      # hit a live vision model / VLM
```

The `llm` / `vision` tests **skip** (never fail) when no model backend is
reachable, so they are safe to run without Ollama up. CI runs everything
except `llm` / `vision`.

### Alternative: conda (local) / Docker (server)

`requirements.txt` (`-e .[cli,dataviz,studio]`) is the shared dependency list
behind both; `pyproject.toml`'s extras stay the actual source of truth, and
this file just selects which of them to install, so there is nothing to
fall out of sync.

```bash
# local dev
conda env create -f environment.yaml
conda activate sprezzature-figures
pip install -r requirements-dev.txt   # pytest, ruff, playwright
playwright install chromium           # one-time, for headless-Chromium checks

# server (Studio app + CLI, same dependency set as above)
docker build -t sprezzature-figures .
docker run --rm sprezzature-figures --list
```

---

## License

BSD 3-Clause. See [LICENSE](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/LICENSE).

## Author

Warith Harchaoui · warith.harchaoui@gmail.com · [harchaoui.org/warith/sprezzature](https://harchaoui.org/warith/sprezzature/)
