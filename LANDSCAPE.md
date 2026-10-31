# Landscape

`sprezzature-figures` is the data-visualisation brick of the [sprezzature](https://sprezzature.ai/) suite, ten Python packages for building publication-quality web content. It holds 167 chart types in 68 categories, every one of them written as SVG directly, with no charting library underneath. It also holds the Ralph Eyeball Loop, which renders a figure, looks at the picture, and edits the source until the picture reads.

## How it fits in the ecosystem

```
sprezzature suite
├── sprezzature-figures        ← this package (167 chart types, the Ralph Eyeball Loop)
├── sprezzature-maps           (the same numbers attached to real places)
├── sprezzature-colors         (the palettes a figure is drawn in)
├── sprezzature-accessibility  (static HTML lint, and the alt text it says is missing)
├── sprezzature-ui             (the page a figure is embedded in)
├── sprezzature-ux-laws        (whether that page feels right)
├── sprezzature-cli-gui        (a web form over a command-line tool)
├── sprezzature-publish        (Markdown to a findable site, narration included)
├── sprezzature-audio          (speech to text, text to speech)
└── sprezzature-video          (what a film about a project claims, checked)
```

What comes before: rows, from a CSV file, a DataFrame, standard input, or a screenshot of somebody else's chart. What comes after: an SVG file, which `sprezzature-publish` puts on a page and `sprezzature-accessibility` then lints. The sister brick is `sprezzature-maps`: the moment the numbers are attached to real places, projections, basemaps and choropleths become the whole problem, and that is a different repository. `choropleth` and `situation_map` used to live here and moved there.

## When to choose it

- You want a chart kind by name and you do not want to read a tutorial first. `make_figure("treemap", rows, out="t.svg")` resolves the kind through `sprezzature_figures/catalog/figures.json` and returns a path. There are 167 names, and all 167 are marked stable.
- You need the figure to stay on your machine. Import, profiling, the choice of chart kind, the render and the export all run with no model and no account. The only step that wants a model is the critique, and `--local` runs it offline through Ollama.
- You want a copilot that actually looks at what it drew. Most assistants emit a chart and move on. The Ralph Eyeball Loop renders, reads the picture, writes a critique, edits the source, and renders again.
- You have somebody else's chart and want it redrawn without the numbers being invented. `redraw()` separates the design from the data, and every result carries a `data_origin` field saying which of the two it recovered.
- You are feeding figures into a web page and want the SVG to be self-contained: embedded fonts, an accessible title and description, dark-mode peers, reduced-motion guards.

## When to pick something else

- **A live dashboard over a database.** Apache Superset, Metabase and Grafana connect to the warehouse, refresh on a schedule, and give a team somewhere to look. This package draws one figure from rows you already have. It scores one star on dashboards and business intelligence (BI) and deserves it.
- **A chart over a very large table.** [Mosaic](https://idl.uw.edu/mosaic/) pushes the work into DuckDB and keeps a view over a billion rows interactive by building data-cube indexes. This package writes SVG elements, and SVG stops being the right container somewhere in the tens of thousands of marks.
- **Anything geographic.** `deck.gl`, Apache ECharts and D3 do projections and basemaps properly. Inside this suite the answer is `sprezzature-maps`. The eleven map-shaped kinds that remain here are marks arranged in the shape of a country, not cartography.
- **A chart a newsroom publishes this afternoon.** [Datawrapper](https://www.datawrapper.de/) and Flourish are faster from spreadsheet to embed than any library can be, they handle the responsive behaviour, and Datawrapper's accessibility defaults are better than most libraries manage after a week of work.
- **A reusable component in a React application.** Recharts has a TypeScript rewrite, two and a half million weekly downloads, and lives inside the component tree where the state already is. An SVG file written by a Python process does not.
- **The ecosystem itself.** Matplotlib has twenty years of answered questions, every statistics textbook, and a backend for every output you can name. This package has one author and a short history. On maturity it scores one star against Matplotlib's five, and that is the honest reading.

## Ideas worth stealing

Forty-two tools were read for this document. Studying a competitor and bringing nothing back is wasted work, so here is what is worth taking, best value first. Two entries are refusals, with the reason.

**[Vega-Lite](https://vega.github.io/vega-lite/): a published JSON Schema, and a `$schema` key in every spec.** A Vega-Lite document names the schema it was written against, so an editor completes it, a validator rejects it before anything renders, and a version mismatch is a readable error rather than a wrong picture. Here, `sprezzature_figures/catalog/models.py` is already Pydantic, so `model_json_schema()` exists and nobody publishes it. The work is a `sprezzature-figures schema <kind>` command that emits it, a `$schema` field on the `FigurePlan`, and a stable URL per version. That gives `sprezzature-cli-gui` a form it can generate without reading our code, and gives Model Context Protocol (MCP) clients the same validation the HTTP routes do. Cost: half a day, because the hard half is already written. Best ratio on this list.

**[AgentVision](https://github.com/amitpatole/agent-vision): a three-level verdict, and issues with coordinates.** Its loop returns `pass` / `warn` / `fail` plus issues anchored to a box on the image, so a calling agent knows whether it may claim it is done. Here, `check_render()` in `sprezzature_figures/render_checks.py` returns a flat list of findings and the `check` action in `actions.py` turns any non-empty list into a non-zero exit. A build that trips one soft warning fails the same way as a build with text off the canvas, so in practice the check gets switched off. The work is a severity field on `RenderFinding`, a verdict on `ActionResult`, and a `--fail-on warn|error` flag. Cost: an afternoon. This is the idea the brick has half: the checks are all there, the triage is not.

**[Mosaic](https://idl.uw.edu/mosaic/): bin before you draw, rather than drawing everything.** Mosaic never sends a million marks to the browser; it computes a binned summary in the database and draws that. Here, `max_recommended_rows` is already a field on every entry in `figures.json`, and the only code that reads it is `sprezzature_figures/studio/recommendation/scoring.py`, where it is a soft scoring penalty. `make_figure()` ignores it completely and will happily emit fifty thousand `<circle>` elements. The work is a check in `make_figure.py` that refuses past the ceiling and names the binned kind to use instead (`scatter` to `hexbin`, `line` to `horizon`), with a `--force` escape. Cost: a day, most of it writing the fallback table. The full Mosaic architecture is refused: DuckDB as a hard dependency is a different product.

**[Quarto](https://quarto.org/): the freeze manifest.** Quarto writes a `_freeze/` record of what was computed and from what, so a rebuild skips unchanged documents and a reader can tell whether an artefact matches its source. Here, the brick writes a `reproduce.py` that replays a figure, which answers "how was this made" but not "is this still true". A small sidecar JSON next to each SVG holding the kind, the resolved option values, a checksum of the rows and the package version would let `check` say "this figure is stale with respect to its data". Cost: an afternoon for the manifest, a day for the staleness check. It also hands `sprezzature-video` the asset ledger it already asks for, which is why it is this high.

**[Datawrapper](https://www.datawrapper.de/): the chart carries its own evidence.** Every published Datawrapper chart has a visible source line and a "get the data" link, by default, not as an option somebody remembers to switch on. Here the figures are self-contained SVG with embedded fonts, so there is room: a `source=` option in the shared chrome and the rows themselves in a `<metadata>` island would make a figure checkable by the person reading it. Cost: cheaper than it looks, and checking that was worth it. `scripts/_svg.py:svg_open` is called by 144 of the 167 generators (`grep -l 'svg_open(' scripts/make_*.py | wc -l`), so one slot in the shared chrome reaches most of the catalogue in a single edit and leaves 23 stragglers to sweep by hand. Call it an afternoon for `svg_open`, a day for the rest, and cap the embedded rows (500, say) so a big figure does not double in size. Note that the docstring of `_svg.py` still puts the helper's reach at about 46, where the real number is 144, which was true once and has been wrong for a long time.

**[Claude Dashboards](https://www.anthropic.com/news/claude-dashboards-and-motion): every chart shows the query that produced it.** Each chart on a Claude dashboard carries the query underneath it, by default, so a reader who distrusts a number can read the derivation without asking anyone. That is a different payload from Datawrapper's above: Datawrapper shows you the *data*, Dashboards shows you the *step from the data to this mark*. Here the derivation exists and almost never travels: `generate_reproduce_script` in `sprezzature_figures/studio/export/code.py` writes a standalone `reproduce.py`, and `grep -rn generate_reproduce_script` finds no caller outside `studio/export/`, so it ships only inside a Studio export archive. A figure drawn by `make_figure` or by one of the 167 `make_*.py` generators — which is how nearly every figure in this suite is actually drawn — carries nothing at all. The work rides the same `svg_open` slot the Datawrapper entry asks for, one slot with two payloads: the resolved kind and option values as a `<metadata>` island, and an optional visible derivation line. Cost: an afternoon on top of that entry, and it is worth doing in the same edit rather than twice. What is *not* taken is the live refresh behind it — that is the Quarto freeze entry above, and it is a staleness check, not a connector.

**[Great Tables](https://posit-dev.github.io/great-tables/): a name for every region of the output.** Its API is built on named parts, `tab_header`, `tab_source_note`, `tab_spanner`, `tab_stubhead`, so an instruction like "put a footnote on the third column" has somewhere to land. Here, `sprezzature_figures/core/operations.py` has typed operations for the data (`SetTitle`, `SetSubtitle`, `SetStyleOption`) but the chrome of the drawing has no vocabulary, so when the critic says the legend overlaps the subtitle, the apply layer has no operation that means that. A named-parts enum shared by `svg_open`, the critic prompt and `operations.py` would close that gap. Cost: a week, and it is the one on this list most likely to grow. Worth it only if the critic is going to be trusted to repair layout unattended.

**[marimo](https://marimo.io/): `marimo pair`, an agent driving a live session. Refused.** marimo opened its notebook kernel to coding agents with token authentication and live cell execution, which is genuinely the right shape for iterating on one figure across many turns. The equivalent here would be a stateful MCP session holding an open `FigurePlan`. It is refused because `sprezzature_figures/mcp.py` is deliberately a one-line wrap of the FastAPI application via `fastapi_mcp`: the MCP tools and the HTTP routes cannot drift because they are the same routes. Session state would end that, and the drift it would permit costs more than the round trips it would save.

**[Observable Framework](https://observablehq.com/framework): data loaders, any executable in any language. Refused as written.** In Framework, `data/sales.csv` is produced by `data/sales.csv.py`, and the build runs it. It is an elegant convention and it would suit `--data` perfectly: a figure in a repository could be rebuilt from a query instead of from a committed extract. It is refused in that form because `make-figure --data foo.csv` executing `foo.csv.py` means a chart command runs code the user did not know was there. If it is ever taken, it is behind an explicit `--allow-exec` flag, never by file extension alone.

## How the field divides

The first split is between a **library** and a **product**. A library gives you a function and leaves the rest to you: Matplotlib, D3, Chart.js, Recharts, Observable Plot, this package. A product gives you somewhere to log in and something to look at: Tableau, Power BI, Looker, Metabase, Datawrapper. The library camp wins on control and reproducibility; the product camp wins on time to first chart and on everything that happens after the chart exists, which is most of the work in an organisation. Between them sits a third camp that barely existed five years ago, the **BI-as-code** tools: Evidence, Observable Framework, Quarto with its dashboards, and `marimo`. These keep the product's output and the library's source control, defining a whole site in a git repository.

The second split is **static artefact against running view**. A figure is a file: it can be put in a paper, a slide deck, an email, a printed report, and it will look the same in ten years. A view is a process: it queries something, it refreshes, it responds to a click, and it is dead the moment the service behind it stops. Apache ECharts, Plotly/Dash, Bokeh, HoloViews and Mosaic are in the second camp and are much better at it than anything in the first. This package is firmly in the first, which is why it scores three stars on interactive and one on dashboards. The map below finds this split on its own and puts it on the vertical axis.

The third split is newer and it is about **who writes the chart**. In 2026 every large model will produce a chart from a sentence, and the business intelligence vendors have all shipped a natural-language layer: Power BI Copilot, Tableau Pulse, ThoughtSpot Spotter, Looker with Gemini. What almost none of them do is look at the result. The assistant writes plotting code, the code runs, an image comes out, and nothing in the chain reads that image to check that the labels did not collide. [Microsoft's LIDA](https://microsoft.github.io/lida/) framed the generate-and-filter shape back in 2023, and the research since, [ChartAgent](https://arxiv.org/abs/2510.04514) and the pixel-guided self-refine work, has mostly been about closing exactly that gap. Claude Dashboards, shipped in October 2026, is that layer approached from the opposite side: rather than a warehouse growing an assistant, an assistant grew warehouse connectors, and it still does not read back what it drew. AgentVision, shipped the same month, is the first tool found for this document that treats the visual feedback loop as the product rather than as a feature. It draws nothing, which is the point: it is the one row in the table that competes with this package on a single column and loses everywhere else.

## How it compares

Every alternative is rated 1 to 5 on each criterion, higher is better (⭐ weak to ⭐⭐⭐⭐⭐ strongest). The scores are an argued judgement, not a benchmark, and every axis is oriented so that more stars mean stronger on that trait, including cost, where more stars mean cheaper or more open. The machine-readable source is [`assets/landscape.csv`](assets/landscape.csv), generated from the table below: 42 tools across 22 criteria.

| Data Viz Tool | Free or open source | Chart type breadth | Publication quality | Ease of use | Programmability | Interactive | AI natural language copilot | Vision QA on render | Local and offline (no account) | Reproducibility | Export to SVG PNG PDF | Customization and theming | Data source flexibility | Maturity and community | Geospatial and maps | Dashboards and BI | Accessibility features | Animated | Large-dataset performance | Web embeddability | Statistical and analytical depth | Responsive |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| sprezzature-figures | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| Matplotlib | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| Seaborn | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| Plotly / Dash | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Bokeh | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| Altair | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| ggplot2 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| HoloViews | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| PyGWalker | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| Streamlit | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| marimo | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| Great Tables | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| Quarto | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Observable Framework | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| Evidence | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| Mosaic / vgplot | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| D3.js | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| Chart.js | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| Apache ECharts | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Highcharts | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Recharts | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ |
| Vega-Lite / Vega | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| Observable Plot | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| Datawrapper | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| Flourish | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| RAWGraphs | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| Vizzu | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| Tableau | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Power BI | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Looker | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Apache Superset | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| Metabase | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| Grafana | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| ThoughtSpot | ⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Julius AI | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| ChatGPT | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| Claude | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| Claude Dashboards | ⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| Gemini | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ |
| AgentVision | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ |
| Excel | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ |
| Canva | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐ |

![Positioning map of 42 data-visualisation tools on two axes derived by principal component analysis. The horizontal axis runs from Dynamic on the left to Intuitive on the right; the vertical runs from Insightful at the bottom to Adaptable at the top. sprezzature-figures sits in the top-right corner, by construction, since it is the reference row, with AgentVision directly below it at the same far-right edge, the only other tool that looks at what was rendered. Matplotlib, ggplot2, D3.js, Altair and Quarto are high up, the adaptable band. Apache ECharts, Plotly/Dash, D3.js and Highcharts are far left, where the running, embeddable, responsive view lives. Claude Dashboards is at the very bottom of the map, lower than ThoughtSpot, Power BI, Looker and Tableau, which sit above it in the same lower band: hosted products with a natural-language layer and a dashboard behind it.](assets/landscape.svg)

The source is [`assets/landscape.csv`](assets/landscape.csv), the star table above and nothing added, and the map is regenerated with:

```sh
python ../sprezzature/scripts/landscape_to_csv.py LANDSCAPE.md
standpoint assets/landscape.csv --outdir assets --stem landscape --check
```

The geometry is ordinary correlation principal component analysis (PCA) and it is **deterministic**: the same table gives the same map every run, whatever model named the poles. What the model contributes is the four words at the edges, and those words are vaguer than the loadings behind them, so here is what the two axes are actually made of.

**Horizontal, `Dynamic` on the left against `Intuitive` on the right.** Interactive (−0.342), responsive (−0.338), geospatial and maps (−0.328), dashboards and business intelligence (−0.322) and web embeddability (−0.309) all load together leftward. That pole is one coherent thing, a product somebody browses, and the right is mostly its absence: a finished artefact. Apache ECharts, Plotly/Dash, D3 and Highcharts are at the far left; this package, AgentVision, ChatGPT and Canva are on the right. The map is noticing on its own that "makes you a picture" and "gives you a dashboard" are different businesses. One warning about the right-hand pole: the only criterion that loads it positively is vision quality assurance on the render (+0.248), and that column is nearly constant, 35 of the 42 tools scoring one star. A thin column makes a thin pole, and the word `Intuitive` is carrying more than the arithmetic gives it.

**Vertical, `Insightful` at the bottom against `Adaptable` at the top.** Free or open source (+0.351), local and offline (+0.336), reproducibility (+0.311) and publication quality (+0.281) pull up. The AI natural-language copilot (−0.347), ease of use (−0.312), dashboards and BI (−0.241) and data-source flexibility (−0.222) pull down. It is the craft-against-immediacy axis: at the top you build the figure yourself and keep it, at the bottom you ask for one and get it. `sprezzature-figures` is at the top by construction, because it is the reference row and `standpoint` anchors the reference top-right. Matplotlib, ggplot2, Altair and Quarto are just as high on their own merits. **Claude Dashboards is the lowest point on the map**, at −4.35, below ThoughtSpot, Power BI, Looker and Tableau: it is the purest instance of that pole in the table, which is what you would expect of a product whose entire proposition is a plain-language question answered off a live warehouse. The newest entrant turns out to be the furthest thing here from this package, and on one axis only.

**The two axes carry 51.1 % of the table between them.** That is the number to hold onto: just under half of what those 22 criteria say is not on this page. With 22 criteria across 42 tools a figure around half is expected, because these tools genuinely differ in more than two ways, but it means the map is a first orientation and the table is the evidence.

That percentage belongs to the **plane**, not to the horizontal and the vertical separately, and this file used to split it as though it did. `standpoint` names the axes it *draws* but reports variance for the underlying principal components, and the drawn frame is a rotation of that plane: 155.1° here, −71.7° on the previous run. Rotating preserves the plane, so the cumulative figure is sound while any per-axis share is not attributable, and the earlier wording here — "30.0 % horizontally and 20.4 % vertically" — was reading a split that the rotation had already mixed. The loadings above are quoted from `standpoint`'s oriented frame, so those *do* describe the horizontal and the vertical as drawn.

The same rotation is why the map should be read against the loadings and never against last month's figure. Adding one row, Claude Dashboards, moved the rotation far enough that the drawn horizontal and vertical **swapped which split they carry**: the running-view axis was vertical on the 41-tool map and is horizontal here, with the same content and nearly the same loadings. Nothing about the field changed; the camera turned.

Two honest caveats remain. First, `standpoint --check` reports `readable: False` on this map: at 42 points some labels sit close enough to risk overlapping (Seaborn and Great Tables, Bokeh and HoloViews, Altair and Quarto, Streamlit and marimo). The interactive SVG separates them on hover; the static PNG does not. Second, `standpoint` also writes a prose interpretation next to the figure, and it is not reproduced here. Its own layout check caught that interpretation placing Excel at the top when Excel sits at the bottom, which is the short argument for not quoting it: a model reading back ratings somebody else wrote is not a finding, and this file is more useful if the judgements stay visibly mine.

## Sources

- [Mosaic, UW Interactive Data Lab](https://idl.uw.edu/mosaic/), the DuckDB-backed architecture for interactive views over very large tables.
- [Evidence](https://evidence.dev/blog/business-intelligence-tools), whose own review of code-based business-intelligence tools is the most useful single page on that family.
- [Observable Framework](https://observablehq.com/framework), data loaders and static data apps.
- [Great Tables v0.22.0](https://opensource.posit.co/blog/2026-06-25_great-tables-0-22-0/), June 2026, image export and much improved LaTeX output.
- [AgentVision](https://github.com/amitpatole/agent-vision), October 2026, the render-perceive-report-fix loop as a product in itself.
- [ChartAgent](https://arxiv.org/abs/2510.04514), a multimodal agent that looks at its own intermediate renders to verify them.
- [Microsoft LIDA](https://microsoft.github.io/lida/), the 2023 paper that framed grammar-agnostic generation of visualisations with large language models.
- [Best React chart libraries in 2026, LogRocket](https://blog.logrocket.com/best-react-chart-libraries-2026/), for where Recharts, nivo and Tremor stand today.
- [Plotly Studio](https://plotly.com/studio/), the desktop AI app builder that put a copilot in front of Dash in 2026.
