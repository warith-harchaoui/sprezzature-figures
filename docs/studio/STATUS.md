# Sprezzature Studio — status

Maintained per commit while building Sprezzature Studio (see `.private/plan.md`
for the full spec; not itself committed). Branch: `feature/sprezzature-studio`.

## Phase

Phase 2 (§3), Phase 3 (§4-§5), and the "basic figures" half of Phase 4 (§7)
complete. Commits 1-6 of 13 landed.

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
- **Commit 5 — Ingest** (`sprezzature_figures/studio/ingest/`:
  `csv_reader.py`, `excel_reader.py`, `clipboard.py`, `profiler.py`,
  `semantic_types.py`, `validation.py`). First module needing the new
  `studio` extra (`nicegui`, `pandas>=2.0`, `openpyxl>=3.1`,
  `charset-normalizer>=3`, `best-engine-ai-helper>=0.4.0`,
  `os-helper>=1.8.0` — the last two are the sibling helper libraries flagged
  earlier). Confirmed `from sprezzature_figures import make_figure` still
  doesn't import pandas as a side effect (plan §15's hard requirement).
  - CSV: `charset_normalizer` + `csv.Sniffer` for encoding/delimiter
    detection, explicit override, 500-row preview.
  - XLSX: sheet listing/selection, and `excel_warnings()` using raw
    `openpyxl` (not pandas, which silently flattens this away) to detect
    merged-cell ranges, unnamed columns, and a last-row-looks-like-a-totals-row
    heuristic.
  - Clipboard: tab/comma-sniffed paste parsing for Excel/Sheets copy-paste.
  - `semantic_types.py`: numeric/categorical/text/datetime/boolean/
    identifier/latitude/longitude/percentage/currency/url/email detection,
    all deterministic (plan §5.5 — no LLM in this path).
  - Fingerprinting via `os_helper.hashfile`/`hash_string` rather than
    hand-rolled hashing.
  - Two real bugs caught by writing tests, not by inspection: (1) bare month
    names ("Jan", "Apr") were misclassified as `datetime` because
    `pd.to_datetime` parses them "successfully" against an implicit
    year/day — fixed by requiring the raw strings contain digits before
    trusting the parse; (2) profiling a DataFrame with duplicate column
    labels crashed (`df[col]` returns a DataFrame, not a Series, when the
    label repeats) — fixed by indexing positionally (`df.iloc[:, i]`)
    everywhere a column is pulled out during profiling.
  - `sprezzature_figures.studio`/`.studio.ingest` registered in
    `pyproject.toml`'s explicit `packages` list and confirmed present in a
    real wheel build (third time this exact packaging gap has bitten this
    branch — now checked as a matter of course for every new subpackage).
  - 33 new tests in `tests/ingest/test_ingest.py`, including regression
    tests for both bugs above.
- **Commit 6 — Basic Vega-Lite figures** (`scripts/make_{bar,line,area,
  scatter,histogram,boxplot,heatmap}.py`). Seven new self-contained
  generators following the exact existing house pattern (same
  INK/SECONDARY/BG/GRIDLINE/FONT constants, `_render.svg_example_path`/
  `write_svg` epilogue, argparse CLI, `DEMO_DATA` + `make_<kind>(data, *,
  out, title, ...) -> Path`) — deliberately not a new abstraction, matching
  plan §21.2 ("don't rewrite historical scripts en masse", extended here to
  "match their pattern for new ones too").
  - `make_bar.py`'s `DEMO_DATA` is literally the original README example
    data (`region`/`value`, North/South/East/West) — this is what finally
    makes `make_figure("bar", ...)` true again instead of needing the
    `treemap` substitution from Commit 3b.
  - Visually spot-checked 3 of the 7 (bar, scatter, heatmap) by rendering to
    PNG and viewing them directly before trusting the automated tests —
    caught nothing wrong, but this is the check that would have caught it
    (e.g. the scatter size legend's auto-rounded 0-1500 domain against
    1100-1900 actual data range is a little loose but not misleading;
    left as-is, not a defect).
  - Registered in `tools/build_figures_catalog.py`'s `HAND_ROLES` (required/
    optional roles for the recommendation engine, Commit 6 of the plan's
    own §6) and in `FIGURES.md`'s table at the correct alphabetical
    position, with real category/description text — not left to the
    generation script's `"Uncategorized"`/empty-string fallback.
  - Re-ran `tools/audit_generators.py --render` + `tools/build_figures_catalog.py`:
    **12 of 90 figures now `stable`** (`bar`, `line`, `area`, `scatter`,
    `histogram`, `boxplot`, `heatmap`, plus the 5 from before) — clears the
    plan §17 MVP acceptance bar of ≥10 stable figures.
  - README.md/LISEZMOI.md: restored the `bar` example (real now, no longer
    needs the `treemap` stand-in), and regenerated the "quick overview"
    category table *programmatically* from `figures.json` rather than
    hand-editing it — this incidentally caught a pre-existing omission
    (`imshow-interpolated`, category "Matrix / Image", was missing from the
    table entirely) and fixed the miscounted category total (19 → 21, since
    "Matrix / Image" and "Relationship" are genuinely new buckets). All
    counts (90 chart types, 90 `make_*.py` scripts, 21 categories) now
    verified against the registry rather than hand-maintained.
  - No packaging surprises this time: `scripts/*.py` ships via the existing
    `sprezzature_figures_scripts` package registration (plain module files
    in an already-registered package are auto-included; unlike `catalog`/
    `core`/`studio`, no new package-data or packages-list entry was needed).
    Verified anyway with the `-m packaging` wheel-build test.

## Figures currently `stable`

Per the latest `--render` audit run (90 generators total):
`bar`, `line`, `area`, `scatter`, `histogram`, `boxplot`, `heatmap`,
`columnrange`, `funnel`, `sunburst`, `treemap`, `waterfall` (12 of 90).
Clears the plan §17 MVP acceptance bar of ≥10 stable figures.

## Tests run

```
python3 -m pytest -q                              # 75 passed, 16 deselected
python3 -m pytest -q -m slow                       # 15 passed, 76 deselected
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

Commit 7 — adapt initial specialized figures (treemap and funnel are already
stable; dumbbell, difference-chart, waffle still need the `make_<kind>`
contract; sankey needs a real rewrite to accept data instead of hardcoded
`NODES`/`LINKS` before it can be exposed at all, per plan §7's explicit
condition).
