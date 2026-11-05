# sprezzature-figures

🇫🇷 [LISEZMOI.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/LISEZMOI.md) · 🇬🇧 README.md

[![Python ≥3.10](https://img.shields.io/badge/python-%3E%3D3.10-blue)](https://www.python.org/)
[![License: BSD-3-Clause](https://img.shields.io/badge/license-BSD--3--Clause-green)](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/LICENSE)

[![logo](https://raw.githubusercontent.com/warith-harchaoui/sprezzature-figures/main/assets/logo.png)](https://sprezzature.ai/)

167 publication-quality chart types, every one written as SVG directly, with no
charting library underneath. Also: a static checker for any rendered SVG, a
redraw of somebody else's chart from a picture of it, and Sprezzature Studio, a
local chat-driven figure editor.

Part of the [sprezzature](https://sprezzature.ai/) suite.

---

## How it works

![Flow diagram. At the top, your rows or somebody else's chart feed two lanes. The left lane draws: it ranks the kinds that serve your goal, writes the SVG directly with no charting library underneath, and can redraw a screenshot of someone else's chart without inventing its numbers. The right lane audits: a static check reads any SVG at all for labels printed over each other and names off the canvas, then the Ralph Eyeball Loop renders the figure, looks at it, and refines the source. Both meet in one outcome, a figure that is correct before it is beautiful.](https://raw.githubusercontent.com/warith-harchaoui/sprezzature-figures/main/assets/how-it-works.svg)

## Five ways in

The same engine answers on five surfaces. Each one calls the same
`make_figure()` dispatcher and the same catalogue.

| Surface | Entry point | Section |
|---|---|---|
| Python library | `from sprezzature_figures import make_figure` | [Quick start](#quick-start) |
| Command line (Click) | `sprezzature-figures`, also installed as `make-figure` | [Command line](#command-line) |
| HTTP API (FastAPI), with Docker and Compose | `uvicorn sprezzature_figures.api:app`, `docker compose up` | [HTTP API, MCP and Docker](#http-api-mcp-and-docker) |
| MCP tools | `sprezzature-figures-mcp` | [HTTP API, MCP and Docker](#http-api-mcp-and-docker) |
| Agent skill | `sprezzature-figures/SKILL.md` in the [sprezzature hub](https://github.com/warith-harchaoui/sprezzature) | [TRIGGERS.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/TRIGGERS.md) |

MCP (Model Context Protocol) is a standard that lets an AI assistant call a
program's functions directly as tools. A skill is the instruction file an agent
such as Claude Code reads to decide when to use this package; it lives in the
hub repository, not here.

## Install

Requires **Python 3.10 to 3.13**.

```bash
pip install sprezzature-figures
```

That one command installs everything: the generators, the data side (pandas,
scikit-learn, networkx, pyyaml), the causal stack (dowhy, econml, and pydot
for DAGs written in DOT), the explainability stack (shap, shapash, timeshap,
lime), Sprezzature Studio (NiceGUI), the FastAPI app and the MCP server. There are no feature
extras. They were folded into the base on 2026-11-01. The only extra left is
`[dev]`, the test and lint toolchain for contributors.

Use a virtual environment to keep things isolated:

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

Verify the install:

```bash
sprezzature-figures --version          # or -V; every console script answers both
sprezzature-figures list --status stable
sprezzature-figures render bar --out check.svg
```

CI runs on Ubuntu: lint, type checks and the full suite on Python 3.12, a
wheel build and clean install, and an install-and-import check on Python 3.10.

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
print(path)  # the absolute path of revenue.png
```

`make_figure(kind, data=None, **kwargs)` returns the written file as a
`FigurePath`, a `pathlib.Path` subclass. Omit `data` and the figure draws its
own demo rows.

The other public names in `sprezzature_figures`:

| Name | What it does |
|---|---|
| `list_kinds(status=None)` | The catalogue, as canonical kind names. |
| `get_figure_definition(kind)` | One kind's entry: data roles, aliases, default size, options. |
| `validate_figure_input(kind, data)` | Check rows against a kind's required roles without rendering. |
| `as_rows(data)` | Turn a DataFrame or a dict of columns into the `list[dict]` the figures take. |
| `FigurePath` | The returned path, which displays itself in a notebook. |
| `check_render(svg)` / `RenderFinding` | Static check of a rendered SVG (see [Check a figure](#check-a-figure-yours-or-anyones)). |
| `to_dark(svg)` | Rewrite a rendered SVG for a dark canvas. |
| `text_width(text, font_size)` | The text-width estimate the generators lay out with and the check measures against. |
| `redraw(image)` / `RedrawResult` | Redraw a chart from a picture of it (see [below](#from-a-picture-of-somebody-elses-chart)). |

`sprezzature_figures.options.options_for(kind)` lists every keyword one figure
accepts besides its rows.

### From a DataFrame, in a notebook

The rows can be whatever you are already holding: a pandas, polars or Arrow
frame, or a dict of columns. Nothing is imported to read them. The conversion
works by duck typing, so none of those libraries is needed to call it.

```python
import pandas as pd
from sprezzature_figures import make_figure

df = pd.read_csv("revenue.csv")          # region, value
make_figure("bar", df, out="revenue.svg", title="Revenue by region")
```

A cell ending in that call **shows the figure**. The return value is still
a `Path`: `isinstance(result, Path)` holds, and so does every method. It
simply knows how to draw itself when a notebook asks.

Gaps are spelled `None` on the way in, whatever the source called them
(`NaN`, `NaT`, `pd.NA`), and a gap in a column a figure needs is refused
at the door, naming the column and the row:

```
ValueError: Invalid data for kind='bar': value: 'value' (Value) is empty in
1 of 3 rows (row 1). A figure cannot draw a value that is not there: drop
those rows, fill them, or reach for 'missing-matrix', which is the figure
whose subject is where the gaps are.
```

Dropping the row quietly would have misreported the total; letting it
through would have raised inside a generator with a message about
`float()`. Figures whose subject *is* absence (`missing-matrix`, a tree's
root with no parent, a forecast with no history) declare it and are let
through.

All 167 registered chart kinds are `status="stable"`: each one is rendered end
to end by the generator audit. See [docs/studio/GENERATOR_AUDIT.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/docs/studio/GENERATOR_AUDIT.md)
for the per-chart detail. Every stable kind tolerates optional roles being
left unbound: it renders a sensible default rather than crashing.

### Command line

One Click command group, installed under two names: `sprezzature-figures` and
`make-figure` run the same code, and so does `python -m sprezzature_figures`.
Its sub-commands are `list`, `render`, `describe`, `recommend`, `redraw` and
`check`.

```bash
# List all chart types (--status stable for the render-verified ones, --json for a program)
sprezzature-figures list

# Render a chart from its built-in demo data
sprezzature-figures render bar --out revenue.png --title "Revenue by region"
sprezzature-figures render treemap --out budget.png --title "Budget breakdown"
sprezzature-figures render funnel --out funnel.png

# Render your own data instead of the demo rows (.csv, .tsv, .json, .jsonl)
sprezzature-figures render treemap --data budget.csv --out budget.png --title "Budget breakdown"

# When your columns don't match the figure's role names, bind them with --map
sprezzature-figures render bar --data gdp.csv --map region=Country --map value=GDP --out gdp.png

# Pipe data in with --data - and upsample the raster with --scale
cat sales.jsonl | sprezzature-figures render bar --data - --out sales@2x.png --scale 2
```

Every figure also has its own keywords. Depending on the figure, they cover a
subtitle, a canvas size, axis titles, a theme, an accessibility palette, the
language of the text it writes itself, and whatever is particular to that one
chart. Ask the figure what it takes:

```bash
# What this chart needs (data roles) and what it accepts (options), with defaults
sprezzature-figures describe treemap

# The same options as flags, once you name the figure
sprezzature-figures render sankey --help
```

Then pass them. Each option is a flag of its own, and `--set name=value` is
the scriptable spelling that reaches any of them:

```bash
sprezzature-figures render bar --out sales.svg --subtitle "FY-2024" --width 1200 --theme academic
sprezzature-figures render sankey --out flow.svg --set volume-unit=sessions --set stage-names="Source,Landing,Action,Outcome"
sprezzature-figures render bar --out sales.svg --language fr --accessibility monochrome
```

An option the figure does not accept is an error naming the ones it does. It
is never a silent no-op, which is how a misspelt flag used to come back
looking like the figure had ignored it. Giving the same option both as a flag
and through `--set` is also an error.

The output format follows the `--out` extension: `.svg` (default, fully
self-contained with embedded fonts), `.png`, `.pdf`, `.jpg`, or `.html`. For
raster and PDF output, `--scale N` upsamples N times for hi-DPI (high dots per
inch) displays (`--out chart.png --scale 3`); it is ignored for `.svg` and
`.html`. `--dark` renders for a dark canvas.

Without `--out` (or `out=` in Python), the figure is written to `<kind>.svg`
in the current directory, named after the canonical kind (`connected_scatter`
gives `connected-scatter.svg`).

The `--data` file is read into one row dict per record: CSV/TSV cells are
type-coerced (numbers stay numbers), and JSON accepts either a bare array of
objects or an object wrapping a `"data"` array. Pass `--data -` to read the
same formats from standard input (the shape is sniffed from the content).
Column names should match the roles the chart expects
(`sprezzature-figures describe <kind>` lists them);
when they don't, `--map role=column` binds them without touching the file.

Not sure which chart fits your file? Ask for a recommendation. It runs the
same deterministic compatibility filter and readability score the Studio shows
as cards, with no model involved:

```bash
sprezzature-figures recommend --data budget.csv
sprezzature-figures recommend --data budget.csv --render best.png    # also render the top pick
sprezzature-figures recommend --data budget.csv --intent hierarchy   # rank for a goal
```

Add `--intent GOAL` (`comparison`, `trend`, `distribution`, `composition`,
`relationship`, `flow`, `hierarchy`, `geography`, `model_evaluation`) to rank
first the figures whose catalogue category serves that goal. Without it, many
kinds tie at the top because readability alone rarely separates them; the goal
is what makes the ranking decisive. `--limit N` sets how many come back
(default 5).

### From a picture of somebody else's chart

You are sent a screenshot of a chart that is hard to read, and asked to make
it better. `redraw` does the reading: a vision model looks at the picture,
says what kind of chart it is and what costs the reader effort, and the
figure is drawn here.

```bash
sprezzature-figures redraw theirs.png --out ours.svg

# With your real numbers: the mode whose output is worth publishing
sprezzature-figures redraw theirs.png --data sales.csv --out ours.svg

# Override what the model chose
sprezzature-figures redraw theirs.png --kind bar --title "Exports carry the quarter"
```

Without `--out`, the figure is written to `<kind>-redrawn.svg`. `--hint` passes
a note to the model, and `--language en|fr` sets the language of the
provenance caption.

```python
from sprezzature_figures import redraw

result = redraw("theirs.png", out="ours.svg", data=rows)
result.kind          # 'bar'
result.data_origin   # 'your-data'
result.changes       # what it does differently, costliest first
```

A picture of a chart carries two things, and carries them with very different
confidence. The **design** (what kind of chart it is, what it is about, what
it costs the reader) is legible from pixels. The **data** usually is not: a
chart drawn without data labels does not contain its own numbers, and a model
asked for them anyway will produce some, because that is what models do.

So `redraw` never guesses, and every result says which one it got:

| `data_origin` | What you have |
|---|---|
| `your-data` | You passed rows. The image supplied only the design. The real figure. |
| `read-from-image` | The numbers were printed on the original and read back. Approximate, and the figure says so on its face. |
| `demo` | Nothing readable. The **redesign** on sample data: the right chart type and the house typography, captioned as such. Look at it; do not publish it. |

That caption is written onto the figure itself, in a strip grown below the
drawing, not just returned to the caller: the SVG outlives the function call
and will be looked at by someone who never saw it.

Input can be PNG, JPEG, GIF, WebP or SVG; a screenshot is the usual case. A
PDF is refused by name, with what to do instead. It needs a vision model,
reached through [best-engine-ai-helper](https://github.com/warith-harchaoui/best-engine-ai-helper)
and a running [Ollama](https://ollama.com) by default, like every other model
call in the suite.

What to expect from the model you run it on: a 7B vision model on a laptop
takes about 90 seconds, reliably gets the chart kind and the text printed on
the image, and reports one or two of the reading problems. The judgement
fields (`what_it_shows`, a title that states the result) are where a bigger
model earns its keep. When they come back empty, the redraw falls back to the
original's own title rather than inventing one.

### Check a figure, yours or anyone's

A chart can be wrong in ways that have nothing to do with taste: two labels
printed on top of each other, a name running off the canvas, a value drawn in
the colour of the bar behind it, demo chrome that survived into a real render,
a title the generator was given and quietly dropped. `check` finds those in
the SVG source alone: no browser, no vision model, no judgement.

```bash
sprezzature-figures check mine.svg
sprezzature-figures check theirs.svg --format json         # for a gate, not a reader
sprezzature-figures check mine.svg --expect-title "Q3 revenue"   # did the title arrive?
cat mine.svg | sprezzature-figures check - --dark          # from a pipe, dark canvas
```

`--forbid TEXT` (repeatable) adds your own placeholder strings to the demo
chrome it already knows.

```python
from sprezzature_figures import check_render

for finding in check_render(open("mine.svg").read()):
    print(finding.check, finding.severity, finding.message)
```

It reads **any** SVG, not only ours. That is the point: the published
work on visualisation linting checks a chart *specification*, so it has
nothing to say about a figure that was not written in one. This reads the
drawing. The geometry it needs is read the way every exporter writes it:
`font-size` as an attribute or inside `style=`, `dominant-baseline` as an
alignment point rather than a baseline, `rotate(-0 …)` as the non-rotation it
is, `width="100%"` as a proportion rather than a hundred pixels.

The exit code is 1 on any finding, so it works as a pre-commit or CI gate.
Findings carry a `severity`: `error` is wrong whoever drew the figure and
whatever it is for, `warning` is wrong under this house's charter or wrong
unless the author had a reason. A gate that blocks on both is a gate people
switch off.

**Its honest limit.** It cannot check a figure whose text was converted to
outlines. Once every glyph is a `<path>`, there is no text to read, no
screen reader can read it either, and every rule would pass on an empty
sight. That is the default of more than one widely used exporter, so the
linter says so out loud (`text_as_outlines`) rather than returning the empty
list that looks like a pass. Re-export with live text (whatever wrote the
file, the setting is usually one flag) and run it again.

The same finding covers the other road to the same place: a figure that was
never given labels at all. The report distinguishes them, because telling
an author to re-export is useless advice when there was nothing to export.

What it will never do is tell you the chart type suits the question, or that
the figure is beautiful. Those are judgements; the Ralph Eyeball Loop
(below) is where a vision model is asked for them, and it is never allowed to
contradict a fact established here.

### The Ralph Eyeball Loop

`scripts/ralph_eyeball_loop.py` renders any visual made from code (`.svg`,
`.html`, a TikZ `.tex`, a Mermaid `.mmd`) to a PNG and writes an assessment
file under `.private/ralph-loop/`. You edit the source and run it again; each
run appends an iteration. In the default mode the agent running it reads the
PNG itself. With `--local`, a local vision model (`qwen3-vl:8b`, through
best-engine-ai-helper) writes the critique offline.

```bash
python scripts/ralph_eyeball_loop.py figure.svg
python scripts/ralph_eyeball_loop.py figure.svg --local
python scripts/ralph_eyeball_loop.py --check-tools
```

It is a script, not a console command: from a clone, run it as above; after
`pip install sprezzature-figures`, the wheel carries it and
`python -m sprezzature_figures_scripts.ralph_eyeball_loop figure.svg` runs the
same loop. The Studio's Ralph
engine (`sprezzature_figures.studio.ralph`) is a separate implementation.

### Other scripts

The repository's `scripts/` directory also holds standalone tools, each with
its own `--help`:

| Script | What it does |
|---|---|
| `render_diagram.py` | Rasterise a TikZ, Mermaid or SVG source to PNG, themed with the house palette. |
| `audit_figure.py` | Static auditor for SVG charts, or HTML with `<figure>` blocks. |
| `explain_model.py` | Explain a pickled model with SHAP, Shapash, TimeSHAP or LIME (local interpretable model-agnostic explanations). `--n-explain` (default 500) is both the SHAP sample and the number of LIME rows. |
| `causal_estimate.py` | Estimate a causal effect with DoWhy and EconML, given a DAG (directed acyclic graph). |
| `install_figures.py` | Install the pinned requirement tiers in `scripts/requirements-*.txt` with the detected environment manager. |

---

## Chart catalogue

167 chart types in 68 categories, as the catalogue
(`sprezzature_figures/catalog/figures.json`) records them. See
[FIGURES.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/FIGURES.md)
for the full table with guidance on when to use each type, and
[TRIGGERS.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/TRIGGERS.md)
for the sentence that reaches each one.

The [figure gallery on sprezzature.ai](https://sprezzature.ai/figures.html) is
a different count on purpose: it shows 160 of the 167. The five glyph maps
(`map-bars`, `map-bubble`, `map-flow`, `map-pie`, `map-tilegrid`) are on the
maps page, and the two Gapminder figures on the page about Hans ROSLING.

| Category | Kinds |
|----------|-------|
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

`choropleth` and `situation_map` are not here: they live in
[sprezzature-maps](https://github.com/warith-harchaoui/sprezzature-maps).

---

## Visual themes

Every chart takes a `theme` parameter for how it looks (fonts, colours),
kept separate from `accessibility`, which controls whether the palette
stays readable for colour-vision deficiency (CVD, the general term for
what is commonly called colour blindness). The two settings compose
freely because they solve different problems: one is taste, the other is
who can actually read the chart.

- **`"corporate"`** (default): Roboto for the chrome text (title,
  subtitle, axis labels), Roboto Mono for tick and numeric labels, and a
  categorical palette derived from Apple's system colours. Renders
  byte-identical to every chart made before `theme` existed, so adopting
  the parameter changes nothing for existing callers.
- **`"academic"`**: Latin Modern Roman and Mono, the free, LaTeX-native
  extension of Computer Modern, for a journal-figure look, paired with the
  [Okabe-Ito](https://jfly.uni-koeln.de/color/) categorical palette (Masataka
  OKABE and Kei ITO, 2002). That palette is CVD-safe by construction: it was
  designed so its colours stay distinguishable under the common forms of
  colour-vision deficiency, which is why it has been the standard
  recommendation for scientific figures since Bang WONG's 2011 column in
  *Nature Methods*.

```python
make_figure("bar", data, out="revenue.svg", theme="academic")
```

```bash
sprezzature-figures render bar --out revenue.svg --theme academic
```

`theme="academic"` also switches sequential colour ramps (heatmaps, hexbin
density, cluster maps, and similar) to [viridis](https://bids.github.io/colormap/),
the perceptually uniform, CVD-safe colormap recommended for scientific
figures; `"corporate"` keeps each chart's own tuned single-hue ramp.

### Fonts

The suite's typography is three Roboto families: Roboto (sans), Roboto Serif
and Roboto Mono. This package is the single source of those font files for the
whole suite. The full faces sit in `assets/fonts/` and ship in the wheel as the
`sprezzature_figures_fonts` package, beside Latin Modern for the academic
theme. `sprezzature_figures.fonts` exposes the stacks (`SANS_STACK`,
`SERIF_STACK`, `MONO_STACK`), the directory (`FONTS_DIR`) and the CSS helpers
(`embedded_font_css()`, `web_font_faces_css()`), so another package imports
them rather than retyping a font stack.

SVG output embeds its fonts and needs no external font loading. When several
figures are inlined into a page that already serves those faces,
`make_figure(..., embed_fonts=False)` leaves them out rather than repeating
the same base64 once per figure. The licences are vendored next to the
files: SIL Open Font License for the three Roboto, GUST Font License for
Latin Modern. Both permit bundling.

---

## Architecture

```
sprezzature-figures/
├── sprezzature_figures/
│   ├── __init__.py        # the public names listed in Quick start
│   ├── make_figure.py     # registry-backed dispatcher + the figure helpers
│   ├── cli.py             # the command line, in Click (sprezzature-figures and make-figure)
│   ├── actions.py         # what redraw / recommend / check do, shared by the CLI
│   ├── api.py             # the FastAPI app
│   ├── mcp.py             # the MCP server, wrapping api.py with fastapi-mcp
│   ├── options.py         # every figure's own keywords, read from its signature
│   ├── render_checks.py   # check_render()
│   ├── redraw.py          # redraw()
│   ├── fonts.py           # font stacks and font files
│   ├── catalog/           # figure registry: FigureDefinition + figures.json
│   ├── core/              # Studio domain models and pure logic
│   └── studio/            # Sprezzature Studio (NiceGUI app, Ralph engine, recommendation)
├── scripts/
│   ├── make_treemap.py            # one self-contained generator per kind
│   ├── make_connected-scatter.py  # hyphenated kinds are supported
│   └── ...                        # 167 make_*.py scripts total, plus the tools above
├── assets/
│   ├── fonts/             # Roboto, Roboto Serif, Roboto Mono, Latin Modern
│   └── svg-examples/      # one committed rendering per kind
├── tools/                 # catalogue, audit, coverage and count maintenance
└── tests/
```

Each `make_<kind>.py` script is self-contained: it imports what it needs,
defines `make_<kind>(data, *, out=None, title="", ...) -> Path` and exposes a
`DEMO_DATA` list for the CLI and the tests. `make_figure()` resolves the kind
through `sprezzature_figures/catalog/figures.json` rather than guessing the
filename; see
[docs/studio/GENERATOR_AUDIT.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/docs/studio/GENERATOR_AUDIT.md)
for which of the 167 scripts currently satisfy this contract.

---

## Adding a chart type

1. Create `scripts/make_<kind>.py` following the pattern of any existing script.
2. Expose `DEMO_DATA: list[dict]` and a function `make_<kind>(data, *, out=None, title="", ...) -> Path`.
3. Add a row to [FIGURES.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/FIGURES.md).
4. Run `python tools/audit_generators.py --render` then `python tools/build_figures_catalog.py` to register it in `sprezzature_figures/catalog/figures.json` (without this, `make_figure()` only reaches it through a deprecated fallback and prints a warning).
5. Run `python tools/bump_catalogue_count.py` so every document that quotes the catalogue size says the new number.
6. Run `sprezzature-figures render <kind> --out check.svg` and `sprezzature-figures check check.svg` to verify the output.

---

## Sprezzature Studio

`sprezzature-studio` launches a local NiceGUI app. You import a
CSV/TSV/XLSX/JSON/JSONL file, pick a chart type (the recommendation cards rank
the ones your columns can fill), bind columns, and refine the figure by
chatting with **Ralph**. Ralph is a copilot built on a language model that
reads your text (an LLM, large language model) and a vision model that looks
at the rendered image (a VLM, vision-language model). It edits a structured
plan and looks at the rendered PNG before deciding it is done. History
(undo, redo, compare) and a reproducible export bundle are in the editor.

```bash
pip install sprezzature-figures
sprezzature-studio                     # http://127.0.0.1:8080, opens a browser tab
sprezzature-studio --port 9000 --no-browser
sprezzature-studio --native            # a desktop window instead of a tab
```

Ralph's LLM and VLM are resolved by
[best-engine-ai-helper](https://github.com/warith-harchaoui/best-engine-ai-helper),
which talks to a local Ollama by default (text model `qwen3:8b`, vision model
`gemma3:12b`; override with `BEST_LLM_TEXT` / `BEST_LLM_VISION`). The app
**starts and stays usable with no model at all**: import, profiling,
recommendation, manual chart choice, property tweaks, history and export all
work; only the chat and the critique need a reachable model. Projects are
stored under `~/.sprezzature-studio/` (override with `SPREZZATURE_STUDIO_HOME`).
Nothing leaves your machine unless you point it at a remote backend
([DATA_PRIVACY.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/docs/studio/DATA_PRIVACY.md)).

Full documentation: [docs/studio/README.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/docs/studio/README.md).

---

## HTTP API, MCP and Docker

The FastAPI app exposes the same functions over HTTP, so the catalogue can be
used from any language:

| Route | `operation_id` (MCP tool name) | What it does |
|---|---|---|
| `GET /health` | `health` | Liveness probe. |
| `GET /kinds` | `list_kinds` | The catalogue; `?status=stable` filters. |
| `GET /kinds/{kind}` | `get_kind` | One kind's definition, data roles first. |
| `GET /kinds/{kind}/options` | `list_kind_options` | Every keyword the kind accepts besides its rows. |
| `POST /recommend` | `recommend_figures` | Rank the kinds these rows can fill, with column bindings. |
| `POST /render/{kind}` | `render_figure` | Render and return the file bytes. |
| `POST /redraw` | `redraw_figure` | Redraw a chart from a base64 picture; answers JSON. |
| `POST /check_render` | `check_render` | Static check of a rendered SVG; answers a list of findings. |

```bash
uvicorn sprezzature_figures.api:app --host 0.0.0.0 --port 8000

# List stable chart kinds
curl http://localhost:8000/kinds?status=stable

# Render the demo treemap as SVG
curl -X POST http://localhost:8000/render/treemap -o treemap.svg

# Render your own data
curl -X POST http://localhost:8000/render/bar -H 'Content-Type: application/json' \
     -d '{"data": [{"region": "North", "value": 42}], "title": "My chart"}' -o bar.svg

# What else that chart type accepts, with types, defaults and allowed values
curl http://localhost:8000/kinds/bar/options

# ...passed under `options`, by the names that route returned
curl -X POST http://localhost:8000/render/bar -H 'Content-Type: application/json' \
     -d '{"options": {"subtitle": "FY-2024", "width": 1200, "theme": "academic"}}' -o bar.svg

# Redraw somebody else's chart from a picture of it
curl -X POST http://localhost:8000/redraw -H 'Content-Type: application/json' \
     -d "{\"image_base64\": \"$(base64 < theirs.png)\"}" | jq -r .data_origin

# Full OpenAPI docs
open http://localhost:8000/docs
```

The `POST /render/{kind}` body takes `data`, `title`, `format` (`svg`, `png`,
`pdf`, `jpg`, `html`), `scale`, `dark` and `options`. Omit `data` to render the
kind's demo rows. An option the figure does not accept comes back as a 422
naming the ones it does, rather than being dropped on the way in. A row missing
a required role is also a 422.

`POST /redraw` answers JSON rather than file bytes: the figure arrives
base64-encoded in `figure_base64`, next to the diagnosis that justified it
(`kind`, `data_origin`, `changes`, `warnings`, `reading`). Reading `data_origin`
before using the figure is the point; see
[From a picture of somebody else's chart](#from-a-picture-of-somebody-elses-chart).

`POST /recommend` takes `data`, `limit` (1 to 50, default 5) and `goal`. It is
the route to call before `/render/{kind}` whenever nobody has named a chart
type.

### MCP

`sprezzature-figures-mcp` serves the same app with the MCP endpoint mounted at
`/mcp`, through [fastapi-mcp](https://github.com/tadata-org/fastapi_mcp). Every
route in the table above becomes an MCP tool named by its `operation_id`:
`health`, `list_kinds`, `get_kind`, `list_kind_options`, `recommend_figures`,
`render_figure`, `redraw_figure` and `check_render`. Each carries a written
summary and a description saying **when** to call it; see
[TRIGGERS.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/TRIGGERS.md)
for the routing rules an agent should follow.

```bash
sprezzature-figures-mcp                          # 127.0.0.1:8000, MCP at /mcp
sprezzature-figures-mcp --host 0.0.0.0 --port 8000
```

The defaults also come from `SPREZZATURE_FIGURES_HOST` and
`SPREZZATURE_FIGURES_PORT`.

### Docker and Compose

The image's default command is `sprezzature-figures-mcp --host 0.0.0.0 --port
8000`: one process serves the HTTP routes and the MCP endpoint at `/mcp`, on
the same port. There is no entrypoint, so any of the package's commands can
replace it.

```bash
docker compose up -d                              # the API and /mcp on :8000
curl -s localhost:8000/health
docker compose run --rm api sprezzature-figures render bellcurve --out /work/bell.svg
docker compose --profile studio up -d             # + the Studio on :8080
docker compose --profile assist up -d             # + an Ollama server for the chat and the eyeball loop
```

`./work` on the host is mounted at `/work` in the containers. Without Compose:

```bash
docker build -t sprezzature-figures .
docker run --rm -p 8000:8000 sprezzature-figures   # HTTP routes + /mcp
```

---

## Development

```bash
git clone https://github.com/warith-harchaoui/sprezzature-figures.git
cd sprezzature-figures
pip install -e ".[dev]"
ruff check .
python -m pytest -q
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
reachable, so they are safe to run without Ollama up. CI runs the default
suite, `slow` and `packaging`, never `llm` or `vision`. The headless-Chromium
checks need a one-time `playwright install chromium` after the `[dev]` install.

### Alternative: conda

`requirements.txt` holds a single line, `-e .`, so `pyproject.toml` stays the
only dependency list. `environment.yaml` pins the interpreter and installs it:

```bash
conda env create -f environment.yaml
conda activate sprezzature-figures
pip install -r requirements-dev.txt   # pytest, ruff, build, playwright, httpx2
playwright install chromium           # one-time, for headless-Chromium checks
```

---

## License

BSD 3-Clause. See [LICENSE](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/LICENSE).

## Author

Warith HARCHAOUI · warithmetics@deraison.ai · [sprezzature.ai](https://sprezzature.ai/)
