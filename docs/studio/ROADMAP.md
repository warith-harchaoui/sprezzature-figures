# Roadmap

## Built (the original 13-commit build plan, plus follow-up hardening)

- Reproducible generator audit (`tools/audit_generators.py`) and an
  explicit figure registry (`sprezzature_figures/catalog/`) that resolves
  hyphenated kind names correctly and decouples the public kind name from
  the backing filename/function name.
- Registry-backed `make_figure()` dispatcher with a deprecated fallback for
  unregistered scripts.
- Core Pydantic domain models: `DatasetProfile`, `FigurePlan`,
  `StyleOptions`, the `Transform`/`FigureOperation` discriminated unions.
- CSV/XLSX/clipboard ingestion + deterministic semantic-type profiling.
- 15 of 90 chart types promoted to `status="stable"` (7 new Vega-Lite
  generators + `treemap`/`funnel`/`waffle`/`dumbbell`/`sankey`/
  `sunburst`/`waterfall`/`columnrange` adapted to the contract). `sankey`
  in particular was rewritten from hardcoded demo nodes/links to accept
  arbitrary `{source, target, value}` flow data with automatic
  topological layering.
- Unified rendering (`core.rendering`) with atomic writes and PNG previews,
  and isolated per-project workspaces (`core.projects`).
- LLM client integration wrapping `best-engine-ai-helper`, with validated
  Pydantic schemas, a repair-on-invalid-JSON flow, and a `FakeLLMClient`
  so the whole test suite runs without a model.
- The Ralph engine: manual/assisted/autopilot modes, a safe-repair
  whitelist and confirmation-required blacklist enforced independent of
  what the model itself claims, and bounded stopping criteria.
- A NiceGUI app (`sprezzature-studio`): import → pick a stable kind → bind
  roles → render → chat with Ralph, with per-session isolation.
- Iteration history (undo/redo/revert/branch, no separate branch-tracking
  structure needed) and reproducible `.sprezzature.zip` export bundles,
  verified by actually running the exported `reproduce.py`.
- Deterministic execution of `FigurePlan.transformations`
  (`core.transformations`): filter / sort / aggregate / top-N / group-others /
  calculate run over the imported rows on the render and export paths, so a
  chat-requested filter or sort actually changes the figure.
- Grammar-constrained structured output end to end (the response schema is
  passed to the model, discriminated unions flattened for Ollama), model-facing
  schemas described field by field, and a Ralph loop that degrades to
  `RalphResult.notes` instead of crashing when a live model fails.
- A lightweight CI workflow (not in the original plan, added on request),
  which caught one real cross-environment bug local development couldn't
  have.

## Deliberately deferred

Scoped out along the way, each documented at the point it was cut (see
`docs/studio/STATUS.md` for the specific commit and reasoning):

- **`difference-chart` generator adaptation.** ~640 lines of numpy
  Catmull-Rom curve smoothing, dual clipPath band fills, and crossing
  detection: a different order of complexity than the other
  hand-authored-SVG generators, and 15 stable figures already clears the
  build plan's ≥10 MVP bar.
- **The deterministic figure-recommendation engine** (plan §6:
  `studio/recommendation/compatibility.py`, `scoring.py`). Not in the
  13-commit build plan at all. `assistant.recommend.explain_recommendations()`
  builds the LLM-facing rerank/explain half only, expecting an
  already-filtered candidate list from a caller.
- **Four of eight planned UI components**: `recommendation_cards.py` (no
  recommendation engine to back it), `property_panel.py`,
  `history_panel.py`, `export_dialog.py` (backends complete and tested:
  `core.history`, `studio.export`, but no button in the app calls them
  yet).
- **Separate `pages/home.py` / `pages/settings.py` routes.** Merged into
  one page to avoid session-id hand-off across NiceGUI page navigation,
  which the MVP's single import→edit loop doesn't need.
- **Deep NiceGUI UI interaction tests** (simulated browser clicks via
  `nicegui.testing.User`). Attempted, abandoned when the assumed
  upload-simulation API didn't exist in the installed version; not worth
  chasing further against the plan's own caution against exhaustive
  pixel-level UI testing. Covered instead by direct unit tests of the
  logic behind each UI action, plus a real subprocess server + HTTP smoke
  test. The model path itself now has opt-in `llm`/`vision`-marked tests
  that exercise the live `BestEngineLLMClient` and the full Ralph loop
  against a real VLM (skipped when no backend is reachable, kept out of the
  default and CI runs).

## Not attempted at all (out of the MVP's stated scope)

Authentication, multi-tenant hosting, real-time collaboration, direct
Vega/SVG editing by the user, arbitrary code generation, full adaptation of
all 90 figures, remote databases, Google Sheets integration, pixel-level
manual editing, an agent that modifies this repository, fine-tuning,
cloud storage, legacy XLS support, automatic slide-deck export.
