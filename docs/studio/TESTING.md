# Testing

```bash
python -m pytest -q                              # default: fast tests only
python -m pytest -q -m slow                       # + real rendering, real LLM-free Ralph rounds, real server launch
python -m pytest -q -m packaging tests/test_packaging.py   # builds+installs a wheel (network, ~11s)
ruff check sprezzature_figures tools tests
```

## Markers

| Marker | What it means | In default run? |
|---|---|---|
| *(none)* | pure logic, no rendering, no I/O beyond a `tmp_path` | yes |
| `slow` | renders a real figure, launches a real subprocess server, or otherwise takes real seconds | no — `pytest -m slow` |
| `packaging` | builds a wheel with `python -m build` and installs it in a fresh venv | no — needs network |

No `llm`/`vision` marker exists yet because there are no tests that call a
real model — every LLM/VLM-touching test in this suite runs against
`assistant.fake_client.FakeLLMClient`, which needs neither Ollama nor a
network call. If real-model tests are added later, mark them `llm`/`vision`
per the build plan and keep them out of the default run.

## What's genuinely exercised vs. what isn't

- **Every generator's `make_<kind>()` contract**: `test_make_figure.py`'s
  `test_every_stable_kind_renders_from_registry` is parametrized off the
  registry itself, so it automatically covers new figures as they're
  promoted to `stable` — not two hardcoded kind names.
- **The registry/dispatcher fix for hyphenated kinds**: a regression test
  asserts `make_figure("connected-scatter", ...)` actually reaches
  `make_connected-scatter.py` (raising `AttributeError` for the real
  contract gap, not a misleading "no script" `ValueError`).
- **The Ralph engine**: full end-to-end tests for all three modes
  (manual/assisted/autopilot), including the stopping criteria, against
  real rendering and `FakeLLMClient`.
- **Export**: a test unzips a produced `.sprezzature.zip` and runs
  `python reproduce.py` as an actual subprocess in the extracted
  directory — not just a string check that the template contains the
  right import.
- **The NiceGUI app**: a real subprocess-launched server, HTTP-checked for
  the expected page content (`test_app_smoke.py`). Deeper UI interaction
  (upload a file and click through via a simulated browser) was attempted
  with `nicegui.testing.User` and abandoned — the upload-simulation API
  assumed didn't exist in the installed nicegui version, and chasing it
  further wasn't worth it against the build plan's own caution against
  testing "every visual detail by pixel coordinates." Instead, every piece
  of non-NiceGUI logic behind the UI (`_load_upload`, `_resolve_data`,
  `_summarize_result`, `engine_status`, `SessionState` isolation) is unit
  tested directly.
- **Not covered**: `FigurePlan.transformations` execution against a live
  dataset (the engine itself doesn't exist yet — see
  [ROADMAP.md](ROADMAP.md)), the deterministic figure-recommendation
  engine (same reason), and the history/export NiceGUI panels (backend
  tested, no UI wired up to call it yet).

## CI

`.github/workflows/ci.yml`: ruff + the default suite + `-m slow`, on
Python 3.10 and 3.13, on push to `main` and on pull requests. Deliberately
excludes `-m packaging` (needs network, ~11-20s) to stay lightweight. CI
caught a real bug local development never surfaced: `make_situation_map.py`
raised `SystemExit` — not an `Exception` subclass — at module import time
for a missing dependency, which killed the whole test run in a clean
environment where that dependency wasn't already installed globally (as it
happened to be on the development machine). Fixed at the source (see
`docs/studio/STATUS.md`'s Commit 10 entry for the full story).
