# Changelog

## Unreleased

### Added

- **Render your own data from the CLI.** `make-figure <kind> --data file`
  (and the Click twin `sprezzature-figures render --data file`) now reads a
  local `.csv` / `.tsv` / `.json` / `.jsonl` file into the row shape every
  generator expects, instead of only the built-in demo data. The loader
  (`sprezzature_figures.data_source.load_records`) stays dependency-light: it
  uses pandas when installed and falls back to the stdlib `csv` reader with
  numeric coercion otherwise, so it works on a bare install. `make_figure.py`
  also gained a `__main__` guard, so `python -m sprezzature_figures.make_figure`
  works.
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
