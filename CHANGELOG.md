# Changelog

## Unreleased

### Removed

- **The last live Vega code path.** `scripts/make_figure.py` (a legacy
  CSV/x/y/kind dispatcher emitting Vega-Lite JSON or matplotlib) predated the
  one-generator-per-kind SVG architecture and was never wired to any
  console-script entry point, but stayed directly runnable and documented in
  `references/publication-presets.md`. Both are deleted, along with
  `_style.vega_config` (its only caller) and `references/figure-catalog.md`
  (an obsolete "prefer Vega-Lite" policy doc). All 126 chart kinds are
  hand-authored SVG; the only Vega left anywhere in the repo is
  `render_diagram.py` rasterising a caller-supplied external spec.

### Fixed

- **Two library crashes found by live-testing the CLI/API surfaces.**
  `make_bar`'s "leads at ..." subtitle formatted `value` with `:.0f` without
  the `float()` cast every other aggregate already had, so a string-typed
  `value` column (the common case from CSV/JSON input) raised `ValueError`.
  `make_area` indexed `row["channel"]` unconditionally and colored bands from
  a dict keyed to the four hardcoded demo channel names, even though
  `channel` is declared optional in the catalog — real data with no channel
  column, or a channel value outside that fixed set, raised `KeyError`.
  Channels are now derived from whatever the data actually carries, falling
  back to a single unnamed series with no legend. Found via
  `sprezzature-figures recommend --render` on a plain three-column CSV.

### Changed

- **`references/` moved off `main` onto a `skills` branch.** It's guidance
  for a human or coding agent (Ralph Eyeball Loop protocol, corner-radius
  policy, engine-selection tables, ...), not something any script or the
  packaged library reads at runtime, and isn't shipped by `pyproject.toml`.
  It now lives alongside the planned Claude/OpenCode `SKILL.md` rewrite on
  the `skills` branch.
- **CI cut from 9 jobs per push to 2.** The 3-OS x 2-Python test matrix plus
  a 3-OS packaging matrix wasn't needed for day-to-day regression coverage
  and left runs queuing during a burst of pushes. Both jobs now run once on
  `ubuntu-latest` / Python 3.12, with a `concurrency` group
  (`cancel-in-progress: true`) so a fast sequence of pushes supersedes its
  own stale runs instead of piling up.

### Fixed

- **`--out` now honours the file extension.** The SVG-first generators used to
  write their SVG string verbatim into whatever path you named, so `--out
  chart.png` produced SVG bytes in a `.png` file. `write_svg` (the shared tail
  every generator calls) now converts the font-embedded SVG to the requested
  format: `.png`, `.pdf`, `.jpg` via `resvg_py`, `.html` wrapped in a minimal
  responsive document, and `.svg` written byte-for-byte as before. Applies to
  the library and both CLIs. (The Studio was already correct here: it always
  renders the figure to `.svg` and rasterizes a separate PNG preview.)

### Fixed

- **Seven hero-SVG generators are reachable through the dispatcher again.**
  `speaking_time`, `situation_map`, `binned-grid-map`, `hexmap`, `hexbin-map`,
  `spike-map`, and `dotdensity` failed under `make-figure <kind>` / the Studio:
  some crashed importing their sibling helpers (`_interactive`, `_render`, ...),
  the rest had no `make_<kind>` callable for the registry to dispatch to.
  `make_figure._load_module` now guarantees the generator's directory is on
  `sys.path` before import (so a generator loads the same whether it runs first
  or tenth), and each of the seven grew the standard
  `make_<kind>(data=None, *, out=None, ...)` entry that builds its bundled demo.
  The three map generators that render onto a basemap now find their vendored
  Natural Earth data (`assets/geo/countries-50m.json`, `countries-110m.json`,
  `fr/departements-simplifiee.geojson`), which had been referenced but not
  committed. `gapminder` / `gapminder_variants` remain blocked on a separate
  missing dataset and are unchanged.

### Added

- **New figure: `interruption-matrix` ("Qui coupe qui ?").** A directed
  "who cuts whom" heatmap for conversation analysis — rows are speakers being
  cut off, columns the interrupters, each cell the interruption count tinted by
  the interrupter, with row/column totals and a one-line bilan. It carries a
  crosshair hover (self-contained mode): pointing at a cell lights that
  interrupter's whole column and that interrupted's whole row and dims the rest,
  so "everyone X cut" and "everyone who cut X" light up together. Full house
  treatment — accessibility levels, dark mode, forced-colors fallback, native
  tooltips, `role="img"` + a computed `<desc>`. Companion to `speaking_time`;
  92 chart types now. Roles: `interrupter`, `interrupted`, `count`.
- **Intent-aware recommendation ranking.** `sprezzature-figures recommend`
  gained `--intent GOAL` (comparison, trend, distribution, composition,
  relationship, flow, hierarchy, geography, model_evaluation). Without it the
  readability score leaves many kinds tied at 1.00; with it, figures whose
  category serves the stated goal are ranked first (top band [0.6, 1.0], others
  [0.0, 0.4]), with readability breaking ties within each band. The engine
  (`studio.recommendation.score` / `rank`) now takes an optional `goal`, derived
  from each figure's populated `category` (the `intents` catalog field is empty
  across all kinds), so the signal covers all 91 figures with no hand
  annotation. `goal=None` is unchanged, byte-for-byte, from before.
- **`--scale N` for hi-DPI raster output.** Both render CLIs (`make-figure`
  and `sprezzature-figures render`) take `--scale N` to upsample `.png` /
  `.jpg` / `.pdf` output N times, e.g. `--out chart.png --scale 3` for a
  crisp 3x raster. It threads through to the single rasterisation choke point
  (`scripts/_render.py`) via the `SPREZZATURE_RENDER_SCALE` env var, so no
  generator signature changed; the default (1x) leaves output byte-identical,
  and `.svg` / `.html` are unaffected.
- **`--data -` reads from standard input.** `make-figure <kind> --data -`,
  `sprezzature-figures render --data -`, and `recommend --data -` read piped
  JSON / JSONL / CSV (the shape is sniffed from the content, since stdin has no
  filename), so data can flow straight from a pipe without a temp file:
  `curl -s … | make-figure bar --data -`.
- **Render your own data from the CLI.** `make-figure <kind> --data file`
  (and the Click twin `sprezzature-figures render --data file`) now reads a
  local `.csv` / `.tsv` / `.json` / `.jsonl` file into the row shape every
  generator expects, instead of only the built-in demo data. The loader
  (`sprezzature_figures.data_source.load_records`) stays dependency-light: it
  uses pandas when installed and falls back to the stdlib `csv` reader with
  numeric coercion otherwise, so it works on a bare install. `make_figure.py`
  also gained a `__main__` guard, so `python -m sprezzature_figures.make_figure`
  works.
- **`--map role=column` for the render CLIs.** When a data file's headers
  don't match the figure's role names, bind them without editing the file, e.g.
  `make-figure bar --data gdp.csv --map region=Country --map value=GDP`
  (repeatable). Backed by `data_source.parse_mapping` / `apply_mapping`. The
  render CLIs also now report a clean error (with a `--map` hint) instead of a
  traceback when the data doesn't fit the chosen figure.
- **The Studio data panel accepts JSON too.** File import now takes
  `.csv` / `.tsv` / `.xlsx` / `.json` / `.jsonl`, routing JSON through the same
  `data_source.load_records` the CLI uses, so both surfaces accept identical
  shapes.
- **Headless chart recommendation from the CLI.** `sprezzature-figures
  recommend --data file` ranks the chart types your data can fill, best first,
  showing each figure's score and its `role=column` binding. It reuses the same
  deterministic `studio.recommendation` filter + readability score the Studio
  GUI shows as cards, with no model involved. `--render out` also renders the
  top pick, applying its role binding automatically. Needs the `[cli]` +
  `[studio]` extras (falls back to a clear install hint otherwise).
- **Transformations now execute.** `core.transformations.apply_transformations`
  runs a `FigurePlan`'s filter / sort / aggregate / top-N / group-others /
  calculate / temporal steps deterministically over the imported rows, in list
  order, with no code evaluation. The editor's render path and the export
  bundle both apply it, so a filter or sort requested in the chat actually
  changes the rendered figure and the exported `transformed.csv`. A transform
  whose column is absent is skipped with a note rather than silently emptying
  the figure.
- **The Ralph loop is resilient to a live model failing.** A model that
  returns empty or malformed JSON, times out, or is unreachable no longer
  crashes the turn: the figure still renders and the reason is reported in
  `RalphResult.notes` (stop reason `critique_unavailable`), across manual,
  assisted, and autopilot modes.
- **Model-facing schemas carry field descriptions** and the intent / edit /
  recommend / critique prompts were rewritten so a live model fills every
  field instead of defaulting to empty. `SetStyleOption.option` is now a
  `Literal` of the real `StyleOptions` fields, so the model can only target a
  style setting that exists.
- **Deterministic figure recommendation** (`studio.recommendation`): a
  hard-constraint compatibility filter and a readability score, surfaced as
  one-click auto-bound recommendation cards in the data panel. Stable figures
  gained readability limits (max categories / rows) so the ranking is
  meaningful.
- **Editor side panels**: iteration history is now recorded, an undo / redo /
  "Export .zip" toolbar and a style property panel were added, and edit chat
  operations are de-duplicated. Transform and model-failure notes are shown to
  the user instead of only logged.
- **Sprezzature Studio** (`sprezzature-studio` CLI, `[studio]` extra): a
  local NiceGUI app to import a CSV/XLSX, pick a chart type, bind columns
  to data roles, and refine the figure by chatting with Ralph, an
  LLM/VLM copilot that edits a structured `FigurePlan` and inspects the
  rendered PNG before deciding it's done. See
  [docs/studio/README.md](docs/studio/README.md).
- 7 new chart types: bar, line, area, scatter, histogram, boxplot, heatmap.
  The first `make_figure("bar", ...)` example in the README is finally
  literally true.
- Explicit figure registry (`sprezzature_figures/catalog/figures.json`):
  decouples a chart's public kind name from its filename/function name.
  `make_figure()` and `make-figure --list --status stable` now report an
  honest `stable`/`experimental`/`legacy`/`unavailable` status per figure
  instead of assuming all 90 work.
- Reproducible generator audit (`tools/audit_generators.py`).
- A lightweight GitHub Actions CI workflow.
- **Self-hosted house typography** (`sprezzature_figures/fonts.py`):
  Roboto, Roboto Serif and Roboto Mono are now bundled as variable
  TTF/WOFF2 files in the repo/wheel (`assets/fonts/`, shipped as the
  `sprezzature_figures_fonts` package) instead of being assumed present
  on the host or fetched from a CDN. Every hand-written SVG generator and
  every Vega-Lite generator now embeds `@font-face` (base64 WOFF2)
  directly in its output (`write_svg()`/`svg_open()`), matplotlib
  generators register the bundled fonts with `font_manager` (and bake
  `svg.fonttype="path"` for portable SVG output), the Vega-Lite → PNG
  preview pipeline points `vl_convert` at the bundled font directory, and
  the Studio web app self-hosts the same WOFF2 files (no Google Fonts
  CDN) via `@font-face`. Figures and the Studio UI now look identical
  regardless of what fonts are installed on the machine viewing them.

### Changed

- The default LLM/VLM backend ([best-engine-ai-helper]) now passes each request
  a JSON schema for grammar-constrained structured output, and defaults to a
  text model that honours it (`qwen3:8b`) and a vision model that does the same
  for image prompts (`gemma3:12b`). Override with `BEST_LLM_TEXT` /
  `BEST_LLM_VISION`. Studio's chat and visual-critique features now work out of
  the box against a local Ollama.

[best-engine-ai-helper]: https://github.com/warith-harchaoui/best-engine-ai-helper

### Fixed

- `make_figure()` (and the `make-figure`/`sprezzature-figures` CLIs) can
  now actually reach the 17 generator scripts whose filenames keep their
  hyphens (`connected-scatter`, `liquid-gauge`, `org-chart`, ...); the
  dispatcher previously guessed a filename by replacing hyphens with
  underscores, which doesn't match the file on disk.
- `sankey` rewritten to accept real `{source, target, value}` flow data
  (with automatic node/layer inference) instead of hardcoded demo
  nodes/links; it previously had no `make_sankey()` at all.
- `waffle`/`dumbbell` adapted to accept arbitrary data instead of a
  hardcoded module-level dataset.
- The `[cli]` extra (`click>=8.1`) is now actually declared; it was
  documented but missing from `pyproject.toml`.
- `figures.json` (the new registry) was missing from the built wheel;
  fixed and covered by a packaging test that builds + installs the wheel
  and renders a figure from it.
- `make_situation_map.py` raised `SystemExit` (not a catchable
  `Exception`) for a missing optional dependency at import time; now
  raises `ImportError`.

---

## 1.0.1 — 2026-07-29

### Added

- 6 new chart types: bell curve (bellcurve), column range (columnrange), funnel, sunburst, treemap, waterfall.
- FIGURES.md catalogue expanded with when-to-use guidance for new entries.

---

## 1.0.0 — 2026-07-29

Initial public release.

- 84 chart types across Vega-Lite, full Vega, matplotlib, and SVG renderers.
- `make_figure(kind, data, **kwargs)` unified dispatcher.
- `list_kinds()` returns all available chart types.
- `make-figure` CLI (argparse) always installed; Click CLI via `[cli]` extra.
- Ralph Eyeball Loop integration for autonomous visual QA (`audit_figure.py`).
- Full type annotations, ruff-clean, pytest test suite.
