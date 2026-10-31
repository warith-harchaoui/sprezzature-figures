# sprezzature-figures

🇫🇷 [LISEZMOI.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/LISEZMOI.md) · 🇬🇧 README.md

[![Python ≥3.10](https://img.shields.io/badge/python-%3E%3D3.10-blue)](https://www.python.org/)
[![License: BSD-3-Clause](https://img.shields.io/badge/license-BSD--3--Clause-green)](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/LICENSE)

[![logo](https://raw.githubusercontent.com/warith-harchaoui/sprezzature-figures/main/assets/logo.png)](https://sprezzature.ai/)

Publication-quality chart types, all hand-authored SVG callable as a Python library or a CLI command.

Part of the [sprezzature](https://sprezzature.ai/) suite.

---

## How it works

![Flow diagram. At the top, your rows or somebody else's chart feed two lanes. The left lane draws: it ranks the kinds that serve your goal, writes the SVG directly with no charting library underneath, and can redraw a screenshot of someone else's chart without inventing its numbers. The right lane audits: a static check reads any SVG at all for labels printed over each other and names off the canvas, then the Ralph Eyeball Loop renders the figure, looks at it, and refines the source. Both meet in one outcome, a figure that is correct before it is beautiful.](https://raw.githubusercontent.com/warith-harchaoui/sprezzature-figures/main/assets/how-it-works.svg)

## Install

Requires **Python 3.10–3.13**. Tested on 🍎 macOS, 🐧 Ubuntu, and 🪟 Windows
(CI runs the full suite plus a wheel-install check on all three).

```bash
pip install sprezzature-figures
```

Optional extras (combine as needed, e.g. `"sprezzature-figures[dataviz]"`):

| Extra | Adds |
|-------|------|
| `[dataviz]` | networkx / scikit-learn / pandas / shapely / pyproj / pyyaml — the data side (tables, geometry, models) behind the catalogue, causal inference and explainability; nothing here draws |
| `[studio]` | Sprezzature Studio: the NiceGUI app + Ralph copilot (see below) |
| `[api]` | FastAPI HTTP surface (see below) |
| `[mcp]` | MCP (Model Context Protocol) tool surface on top of `[api]`, for calling this library from an AI assistant (see below) |

Use a virtual environment to keep things isolated:

<details>
<summary>🍎 macOS / 🐧 Ubuntu</summary>

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install "sprezzature-figures[dataviz]"
```
</details>

<details>
<summary>🪟 Windows (PowerShell)</summary>

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install "sprezzature-figures[dataviz]"
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

### From a DataFrame, in a notebook

The rows can be whatever you are already holding — a pandas, polars or
Arrow frame, or a dict of columns. Nothing is imported to read them: the
conversion is by duck typing, so none of those libraries is a dependency
and a caller with none of them installed pays nothing.

```python
import pandas as pd
from sprezzature_figures import make_figure

df = pd.read_csv("revenue.csv")          # region, value
make_figure("bar", df, out="revenue.svg", title="Revenue by region")
```

A cell ending in that call **shows the figure**. The return value is still
a `Path` — `isinstance(result, Path)` holds, and so does every method —
it simply knows how to draw itself when a notebook asks.

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
`float()`. Figures whose subject *is* absence — `missing-matrix`, a tree's
root with no parent, a forecast with no history — declare it and are let
through.

All 167 registered chart kinds are `status="stable"` (render-verified end to
end); see [docs/studio/GENERATOR_AUDIT.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/docs/studio/GENERATOR_AUDIT.md)
for the per-chart audit detail, and `make-figure --list --status stable` to
confirm the current set. Every stable kind tolerates optional roles being
left unbound: it renders a sensible default rather than crashing.

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

Every figure also has its own keywords — a subtitle, a canvas size, axis
titles, a theme, the language of the chrome it writes itself, plus whatever
is particular to that one chart. Ask the figure what it takes:

```bash
# What this chart needs (data roles) and what it accepts (options), with defaults
make-figure treemap --describe

# The same list as flags, once you name the figure
make-figure sankey --help
```

Then pass them. Each option is a flag of its own, and `--set name=value` is
the scriptable spelling that reaches any of them:

```bash
make-figure bar --out sales.svg --subtitle "FY-2024" --width 1200 --theme academic
make-figure sankey --out flow.svg --set volume-unit=sessions --set stage-names="Visit,Trial,Paid"
make-figure bar --out sales.svg --language fr --accessibility monochrome
```

An option the figure does not accept is an error naming the ones it does —
never a silent no-op, which is how a misspelt flag used to come back looking
like the figure had ignored it.

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
`[studio]` extra for the profiling stack). This runs the same deterministic
compatibility + readability ranking the Studio GUI shows as cards, with no
model involved:

```bash
make-figure recommend --data budget.csv
make-figure recommend --data budget.csv --render best.png  # + render the top pick
make-figure recommend --data budget.csv --intent hierarchy  # rank for a goal
```

`recommend`, `redraw`, `check`, `list` and `describe` are sub-commands of
both command lines: `make-figure recommend ...` and `sprezzature-figures
recommend ...` do the same thing, because they are the same callable under
two names. Both are always installed.

Add `--intent GOAL` (`comparison`, `trend`, `distribution`, `composition`,
`relationship`, `flow`, `hierarchy`, `geography`, `model_evaluation`) to rank
the figures that serve that goal first. Without it, many kinds tie at the top
because readability alone rarely separates them; the goal is what makes the
ranking decisive.

### From a picture of somebody else's chart

You are sent a screenshot of a chart that is hard to read, and asked to make
it better. `redraw` does the reading: a vision model looks at the picture,
says what kind of chart it is and what costs the reader effort, and the
figure is drawn here.

```bash
sprezzature-figures redraw theirs.png --out ours.svg

# With your real numbers -- the mode whose output is worth publishing
sprezzature-figures redraw theirs.png --data sales.csv --out ours.svg

# Override what the model chose
sprezzature-figures redraw theirs.png --kind bar --title "Exports carry the quarter"
```

```python
from sprezzature_figures import redraw

result = redraw("theirs.png", out="ours.svg", data=rows)
result.kind          # 'bar'
result.data_origin   # 'your-data'
result.changes       # what it does differently, costliest first
```

A picture of a chart carries two things, and carries them with very different
confidence. The **design** — what kind of chart it is, what it is about, what
it costs the reader — is legible from pixels. The **data** usually is not: a
chart drawn without data labels does not contain its own numbers, and a model
asked for them anyway will produce some, because that is what models do.

So `redraw` never guesses, and every result says which one it got:

| `data_origin` | What you have |
|---|---|
| `your-data` | You passed rows. The image supplied only the design. The real figure. |
| `read-from-image` | The numbers were printed on the original and read back. Approximate, and the figure says so on its face. |
| `demo` | Nothing readable. The **redesign** on sample data — the right chart type and the house typography, captioned as such. Look at it; do not publish it. |

That caption is written onto the figure itself, in a strip grown below the
drawing, not just returned to the caller: the SVG outlives the function call
and will be looked at by someone who never saw it.

Input can be PNG, JPEG, GIF, WebP or SVG — a screenshot is the usual case. A
PDF is refused by name, with what to do instead. Needs a vision model: the
`[local]` extra plus a running [Ollama](https://ollama.com), same as every
other model call in the suite.

What to expect from the model you run it on: a 7B vision model on a laptop
takes about 90 seconds, reliably gets the chart kind and the text printed on
the image, and reports one or two of the reading problems. The judgement
fields (`what_it_shows`, a title that states the result) are where a bigger
model earns its keep — when they come back empty, the redraw falls back to
the original's own title rather than inventing one.

### Check a figure — yours, or anyone's

A chart can be wrong in ways that have nothing to do with taste: two labels
printed on top of each other, a name running off the canvas, a value drawn in
the colour of the bar behind it, demo chrome that survived into a real render,
a title the generator was given and quietly dropped. `check` finds those in
the SVG source alone — no browser, no vision model, no judgement.

```bash
sprezzature-figures check mine.svg
sprezzature-figures check theirs.svg --format json      # for a gate, not a reader
make-figure check mine.svg --expect-title "Q3 revenue"  # did the title arrive?
cat mine.svg | make-figure check - --dark               # from a pipe, dark canvas
```

```python
from sprezzature_figures import check_render

for finding in check_render(open("mine.svg").read()):
    print(finding.check, finding.severity, finding.message)
```

It reads **any** SVG, not only ours. That is the point: the published
work on visualisation linting checks a chart *specification*, so it has
nothing to say about a figure that was not written in one. This reads the
drawing. The geometry it needs is read the way every exporter writes it —
`font-size` as an attribute or inside `style=`, `dominant-baseline` as an
alignment point rather than a baseline, `rotate(-0 …)` as the non-rotation it
is, `width="100%"` as a proportion rather than a hundred pixels.

Exit code is 1 on any finding, so it works as a pre-commit or CI gate.
Findings carry a `severity`: `error` is wrong whoever drew the figure and
whatever it is for, `warning` is wrong under this house's charter or wrong
unless the author had a reason. A gate that blocks on both is a gate people
switch off.

**Its honest limit.** It cannot check a figure whose text was converted to
outlines — once every glyph is a `<path>`, there is no text to read, no
screen reader can read it either, and every rule would pass on an empty
sight. That is the default of more than one widely used exporter, so the
linter says so out loud (`text_as_outlines`) rather than returning the empty
list that looks like a pass. Re-export with live text — whatever wrote the
file, the setting is usually one flag — and run it again.

The same finding covers the other road to the same place: a figure that was
never given labels at all. The report distinguishes them, because telling
an author to re-export is useless advice when there was nothing to export.

What it will never do is tell you the chart type suits the question, or that
the figure is beautiful. Those are judgements; the Ralph Eyeball Loop
(`scripts/ralph_eyeball_loop.py`) is where a vision model is asked for them,
and it is never allowed to contradict a fact established here.

---

---

## Chart catalogue

167 chart types across 52 categories. See [FIGURES.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/FIGURES.md) for the full table with per-chart guidance on when to use each type.

Quick overview:

| Category | Charts |
|----------|--------|
| Comparison | bar, bar-grouped, bar3d, bubble, columnrange, difference-chart, dotplot, dumbbell, lollipop, packed-bubble, pareto, radial-bar, variwide, waterfall |
| Composition | area, donut, parliament, pictorial, stacked-area, stacked-bar, ternary, waffle |
| Distribution | beeswarm, bellcurve, blandaltman, boxen, boxplot, corr-matrix, ecdf, errorbar, hexbin, histogram, kde1d, kde2d-contour, mosaic, population-pyramid, ridgeline, rug, strip, violin |
| Flow | alluvial, chord, funnel, parallel-sets, sankey |
| Geospatial | binned-grid-map, choropleth, dotdensity, hexbin-map, hexmap, situation_map, spike-map, voronoi |
| Hierarchy | circle-packing, convex-hull, dendrogram, icicle, org-chart, radial-tree, sunburst, tree, treemap |
| KPI | bullet, gauge, liquid-gauge |
| Matrix / Image | clustermap, heatmap, imshow-interpolated |
| Meteorology | windbarb, windrose |
| Model evaluation | calibration, confusion-matrix, elbow, gaussian-process, liftgain, manhattan, ppplot, prcurve, qqplot, roc-curve, survival-km |
| Network | arcdiagram, dependency-wheel, edge-bundling, network, sfdp-largegraph |
| Regression | regression-ci-band, residual |
| Relationship | parcoords, scatter, volcano |
| Signal | quiver, spectrogram, streamplot |
| Text | wordcloud |
| 3-D | scatter3d, surface3d, wireframe3d |
| Time series | bollinger, calendar-heatmap, candlestick, connected-scatter, horizon, line, line-multi, slope, step, streamgraph, timeline |
| Multivariate | andrews, embedding_projector, jointplot, pairplot, radar, radviz, upset, venn |
| Meta-analysis | forest |
| Animated | gapminder, gapminder_variants |
| Other | cycle, gantt, interruption-matrix, polar, rose, speaking_time |

---

## Visual themes

Every chart supports a `theme` parameter for how it looks (fonts, colors),
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
  [Okabe-Ito](https://jfly.uni-koeln.de/color/) categorical palette (Okabe
  and Ito, 2002). That palette is CVD-safe by construction: it was
  designed so its colours stay distinguishable under the common forms of
  colour-vision deficiency, which is why it has been the standard
  recommendation for scientific figures since Wong's 2011 editorial in
  *Nature Methods*.

```python
make_figure("bar", data, out="revenue.svg", theme="academic")
```

```bash
make-figure bar --out revenue.svg --theme academic
```

Both fonts are embedded (self-contained SVGs need no external font
loading); licenses are vendored in `assets/fonts/` (Roboto: OFL, Latin
Modern: GUST Font License, both permit bundling).

`theme="academic"` also switches sequential colour ramps (heatmaps, hexbin
density, cluster maps, and similar) to [viridis](https://bids.github.io/colormap/),
the perceptually-uniform, colour-vision-deficiency-safe colormap
recommended for scientific figures; `"corporate"` keeps each chart's own
tuned single-hue ramp unchanged.

---

## Architecture

```
sprezzature-figures/
├── sprezzature_figures/
│   ├── __init__.py        # exports make_figure, list_kinds, get_figure_definition
│   ├── make_figure.py     # registry-backed dispatcher + the figure helpers
│   ├── cli.py             # the command line, in click (make-figure AND sprezzature-figures)
│   └── catalog/           # figure registry: FigureDefinition + figures.json
├── scripts/
│   ├── make_treemap.py            # self-contained chart script
│   ├── make_connected-scatter.py  # hyphenated kinds are supported
│   └── ...                        # 167 make_*.py scripts total
├── assets/
│   └── svg-examples/      # SVG template examples
└── tests/
```

Each `make_<kind>.py` script is self-contained: it imports what it needs, defines `make_<kind>(data, *, out=None, title="", ...) -> Path` and exposes a `DEMO_DATA` list for CLI and test use. `make_figure()` resolves the kind through `sprezzature_figures/catalog/figures.json` rather than guessing the filename; see [docs/studio/GENERATOR_AUDIT.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/docs/studio/GENERATOR_AUDIT.md) for which of the 167 scripts currently satisfy this contract.

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
  beyond `[dataviz]`.
- **Sprezzature Studio** (`sprezzature_figures.studio`, `sprezzature-studio`
  CLI): a local NiceGUI app to import a CSV/TSV/XLSX/JSON file, pick a chart type, bind
  columns, and refine the figure by chatting with **Ralph**, a copilot built
  on a language model that reads your text (an LLM) paired with a vision
  model that looks at the rendered image (a VLM). Ralph edits a structured
  plan and actually looks at the rendered PNG before deciding it's done.
  Needs the `studio` extra:

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

Beyond the command line, the same `make_figure()` function is reachable
over the network in two ways: as a plain HTTP API, and as an MCP tool.
MCP (the Model Context Protocol) is a standard that lets an AI assistant
call a program's functions directly, the same way a human would call them
from a script, instead of having to read documentation and guess. Three
ways reach the same `make_figure()` dispatcher, and offer the same
commands:

| Interface | Always installed? | Entry point |
|---|---|---|
| CLI (click) | Yes | `make-figure` and `sprezzature-figures`, one callable |
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

`GET /kinds/{kind}/options` is the HTTP half of `make-figure <kind>
--describe`: every keyword that figure accepts, with its type, its default
and its allowed values. Options go in `render`'s `options` object under
those names; one that the figure does not accept comes back as a 422 naming
the ones it does, rather than being dropped on the way in.

`POST /redraw` answers JSON rather than file bytes: the figure arrives
base64-encoded in `figure_base64`, next to the diagnosis that justified it
(`kind`, `data_origin`, `changes`, `reading`). Reading `data_origin` before
using the figure is the point — see
[From a picture of somebody else's chart](#from-a-picture-of-somebody-elses-chart).

`POST /recommend` ranks which chart kinds your rows can fill, each with its
role bindings already worked out — the same deterministic ranking the CLI's
`recommend` command runs, over HTTP. It is the route to call before
`/render/{kind}` whenever nobody has named a chart type.

The MCP surface (`sprezzature-figures[api,mcp]`) exposes the exact same
routes as MCP tools (`list_kinds`, `get_kind`, `list_kind_options`,
`recommend_figures`, `render_figure`, `redraw_figure`, `check_render`) at
`/mcp` on the same FastAPI app. Each
carries a written summary and a description saying **when** to call it —
see [TRIGGERS.md](https://github.com/warith-harchaoui/sprezzature-figures/blob/main/TRIGGERS.md)
for the routing rules an agent should follow.
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

Warith HARCHAOUI · warithmetics@deraison.ai · [sprezzature.ai](https://sprezzature.ai/)
