# Data privacy

## Local by default

Sprezzature Studio runs entirely on your machine. Imported files, rendered
figures, and project history live under `~/.sprezzature-studio/projects/`
(overridable via `SPREZZATURE_STUDIO_HOME`, mainly used by the test suite
to avoid touching your real home directory). Nothing is uploaded anywhere
by this package.

## What reaches the LLM/VLM

The model itself may be local (Ollama) or remote (an OpenAI-compatible or
LangChain-routed API), entirely as configured through
`best-engine-ai-helper`; this package doesn't choose or ship a backend. By
default `best-engine-ai-helper` targets a **local** Ollama (text model
`qwen3:8b`, vision model `gemma3:12b`), so out of the box nothing leaves your
machine at all. Pointing `BEST_LLM_*` / `SPREZZATURE_LLM_BASE_URL` at a remote
service is the only way data reaches a third party, and then only the fields
below. Whichever backend is configured, only this leaves the process:

- **Intent analysis**: your free-text request, plus a `DatasetProfile`:
  column names, semantic types (categorical/numeric/datetime/...), null
  ratios, unique counts, min/max/mean/median, a handful of sample values
  per column. See `core.dataset.ColumnProfile` for the exact fields.
- **Edit proposals**: your chat message, the current `FigurePlan`'s kind,
  title, bound columns, and available column names.
- **Visual critique**: the rendered **PNG preview** of the current figure,
  plus the same kind of narrow context above (figure kind, bound roles,
  title/subtitle, dimensions, a statistical summary, applied
  transformations, the previous critique if any).

**Raw data rows are never sent** unless a future setting explicitly opts
in (plan §1.4 describes such a toggle; it is not implemented: there is
currently no code path that sends row-level data to the model at all, not
even behind a flag).

## Export

`.sprezzature.zip` archives (see `studio/export/`) are written only to the
project's own `exports/` directory, never uploaded. `alt-text.txt` inside
the archive is generated **deterministically**, with no model call; export
is one of the flows required to work with no LLM/VLM configured at all.

## Degraded mode

The app starts, imports data, profiles it, and lets you manually pick a
figure kind and bind columns whether or not an LLM/VLM is configured or
reachable (`studio.config.engine_status()` is a non-blocking, best-effort
snapshot: it never probes the backend at startup, so an unreachable model
never delays or blocks launch). Manual-mode Ralph requests (apply the
explicit edit, render, report; no inspection) work without a model too;
only `assisted`/`autopilot` modes and the chat's structured-interpretation
step need one.
