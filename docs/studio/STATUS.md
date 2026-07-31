# Sprezzature Studio — status

Maintained per commit while building Sprezzature Studio (see `.private/plan.md`
for the full spec; not itself committed). Branch: `feature/sprezzature-studio`.

## Phase

Phase 2 (§3 — stabilize catalogue and dispatcher) complete. Phase 3 (§4 —
core domain models) commit 4 of 13 landed.

## Completed

- **Commit 1 — Audit** (`tools/audit_generators.py`,
  `docs/studio/generator_audit.json`, `docs/studio/GENERATOR_AUDIT.md`,
  `tests/test_generator_audit.py`). Reproducible, exception-transparent audit
  of all 83 `scripts/make_*.py` generators against the `make_<kind>(data, *,
  out, title) -> Path` contract.
- **Commit 2 — Catalog** (`sprezzature_figures/catalog/`:
  `models.py`, `registry.py`, `figures.json`, `tools/build_figures_catalog.py`,
  `tests/catalog/`). Explicit `FigureDefinition` registry generated from
  FIGURES.md + the audit; decouples public kind name from filename/callable;
  resolves hyphen/underscore/space alias spellings.
- **Commit 3 — Dispatcher** (`sprezzature_figures/make_figure.py`,
  `sprezzature_figures/__init__.py`). `make_figure()` now resolves through the
  registry instead of guessing filenames. Adds `get_figure_definition()`,
  `list_kinds(status=...)`, `validate_figure_input()`. Non-stable kinds warn
  (`UserWarning`) with the registry's recorded reasons instead of failing
  silently. Unregistered-but-on-disk scripts still work via a deprecated,
  `DeprecationWarning`-emitting fallback (must never be used by the Studio GUI).
- **Commit 3b — Packaging + docs** (`pyproject.toml`, `sprezzature_figures/cli.py`,
  `README.md`, `LISEZMOI.md`, `FIGURES.md`, `tests/test_packaging.py`):
  - Added the `[cli]` extra (`click>=8.1`) that README/LISEZMOI already
    advertised but pyproject never declared.
  - Fixed `sprezzature_figures/cli.py`'s Click `render` command, which
    duplicated the *old* buggy hyphen-guessing logic to locate a script for
    its early "unknown kind" check — it now uses `catalog.resolve_kind()`
    like the argparse CLI, via a shared `_demo_data_for()` helper.
  - Registered `sprezzature_figures.catalog` as a package and added
    `figures.json` to `package-data` — it was silently missing from the
    wheel (explicit `packages = [...]` list, no `package-data` block).
    Verified with a new `@pytest.mark.packaging` test that builds the wheel,
    installs it in a throwaway venv, and renders a stable figure end to end
    (confirmed 118 files in the wheel, `figures.json` and
    `sprezzature_figures_scripts/make_treemap.py` both present).
  - Replaced the `make_figure("bar", ...)` / `make-figure bar` examples
    (README, LISEZMOI, FIGURES.md) — no `make_bar.py` has ever existed — with
    a working `treemap` example, plus a note pointing at
    `--status stable` / GENERATOR_AUDIT.md.
  - Fixed the `make_bar.py` reference in both architecture-tree diagrams.
  - Corrected inflated/wrong counts found while touching these docs: "84
    chart types" → 83 (the 84th FIGURES.md row documents the `figure`
    dispatcher itself, not a chart); "15 categories" → 19 (actual row count
    in the README/LISEZMOI quick-overview table); return type documented as
    `-> str` → `-> Path` (matches every generator's actual signature).
  - "Adding a chart type" instructions now include the registration step
    (`tools/build_figures_catalog.py`) that Commit 2 introduced.
- **Commit 4 — Core domain models** (`sprezzature_figures/core/`:
  `dataset.py`, `figure_plan.py`, `operations.py`, `validation.py`).
  `DatasetProfile`/`ColumnProfile` (plan §4.1), `FigurePlan`/`StyleOptions`/
  `ColumnBinding`/`UserIntent` (reuses the same shape plan §10.1 calls
  `IntentAnalysis`, rather than defining it twice), a discriminated
  `Transform` union (filter/sort/aggregate/rename/top-N/group-others/
  calculate — plan §4.3, no free-form formulas) and a discriminated
  `FigureOperation` union (the 15 plan-editing commands from §4.2). Both
  unions round-trip through `pydantic.TypeAdapter` JSON validation cleanly —
  needed later for constraining LLM structured output (Commit 9/10) to only
  these types. `validate_operation()`/`validate_plan()` reject operations
  referencing nonexistent columns or undeclared `StyleOptions` fields, and
  flag a plan missing a figure's required role bindings (reusing
  `catalog.ValidationIssue`, not a second validation-issue type).
  `sprezzature_figures/core/rendering.py`, `projects.py`, `iterations.py`
  (also listed under plan §4) are deliberately deferred to Commits 8 and 12,
  where they're actually used — plan's own commit table splits "models"
  from "unified rendering" and "history", so building them now would be
  speculative/untested code with no caller yet.

## Figures currently `stable`

Per the latest `--render` audit run: `columnrange`, `funnel`, `sunburst`,
`treemap`, `waterfall` (5 of 83). Target for MVP acceptance (plan §17): ≥10.

## Tests run

```
python3 -m pytest -q                              # 42 passed, 9 deselected
python3 -m pytest -q -m slow                       # 8 passed, 29 deselected
python3 -m pytest -q -m packaging tests/test_packaging.py   # 1 passed (~11s, needs network)
ruff check sprezzature_figures tools tests          # clean
```

## Known blockers / open questions

- `nicegui` is not installed anywhere in this environment yet — required for
  Commit 11 (`studio` extra, plan §15).
- `best-engine-ai-helper` (0.4.0) is installed and exposes
  `chat(prompt, *, system, images, json_schema, model, temperature)`; the
  plan's `LLMClient` protocol (§9.1, separate `chat_text`/`chat_vision`) will
  be adapted to wrap this single `chat()` signature rather than mirrored 1:1.
- Also available locally and worth reusing rather than reimplementing:
  `os-helper` (cross-platform file I/O/hashing/temp-file utilities — good fit
  for the ingest/export modules) and `wallet-helper` (content-addressed
  memoization/caching — good fit for caching LLM calls in the Ralph loop,
  Commit 9/10). Both installed (`pip show os-helper wallet-helper`).
- `sankey` has no `make_sankey()` — confirmed `legacy`; per plan §7 it must
  not be exposed in the GUI until rewritten to take real data (Commit 7).
- The Click CLI (`sprezzature-figures render <kind>`) and argparse CLI
  (`make-figure <kind>`) still let an `AttributeError`/`RuntimeError` from a
  non-stable kind propagate as a raw traceback rather than a clean CLI error
  message. Pre-existing behaviour, not a regression from this branch; worth
  cleaning up but out of scope for the dispatcher/catalog commits.
- `required_roles` are only populated for the 5 currently-stable figures;
  every other registry entry has empty role lists until it's adapted
  (Commit 7) or newly built (Commit 6).

## Next

Commit 5 — CSV/XLSX/clipboard ingestion + profiler
(`sprezzature_figures/studio/ingest/`), producing `DatasetProfile` from real
files. User confirmed "keep going autonomously" through Commits 4-13, with
another check-in after the render/LLM core is in place and before the GUI
itself.
