# Testing

```bash
python -m pytest -q                    # default: fast tests only
python -m pytest -q -m slow            # + real rendering, LLM-free Ralph rounds, real server launch
python -m pytest -q -m packaging       # builds + installs the wheel, incl. [studio] extra (network, ~50s)
python -m pytest -q -m llm             # hits a live text model via best-engine-ai-helper
python -m pytest -q -m vision          # hits a live vision model / VLM
ruff check sprezzature_figures tools tests
```

The suite holds about 100 test functions. It follows the project's
test-rationalization philosophy ("test count is not a quality metric"):
similar cases are merged with `@pytest.mark.parametrize`, and a test earns its
place only when it catches a failure nothing else does. Coverage sits at ~81%.

## Markers

| Marker | What it means | In default run? |
|---|---|---|
| *(none)* | pure logic, no rendering, no I/O beyond a `tmp_path` | yes |
| `slow` | renders a real figure, launches a real subprocess server, or otherwise takes real seconds | no (`pytest -m slow`) |
| `packaging` | builds a wheel with `python -m build` and installs it in a fresh venv | no (needs network) |
| `llm` | calls a live text model through `best-engine-ai-helper` | no (`pytest -m llm`) |
| `vision` | calls a live vision model / VLM through `best-engine-ai-helper` | no (`pytest -m vision`) |

The `llm` / `vision` tests **skip** (never fail) when no model backend is
reachable, so running them without Ollama up is safe. They exercise the real
`BestEngineLLMClient` path, and the full Ralph loop with the rendered PNG
handed to a live VLM. Everything else stubs the model with
`assistant.fake_client.FakeLLMClient`, which needs neither Ollama nor a
network call.

## What's genuinely exercised vs. what isn't

- **Every generator's `make_<kind>()` contract**: `test_make_figure.py`'s
  `test_every_stable_kind_renders_from_registry` is parametrized off the
  registry itself, so it automatically covers new figures as they're
  promoted to `stable`, not two hardcoded kind names.
- **The registry/dispatcher fix for hyphenated kinds**: a regression test
  asserts `make_figure("connected-scatter", ...)` actually reaches
  `make_connected-scatter.py` (raising `AttributeError` for the real
  contract gap, not a misleading "no script" `ValueError`).
- **The Ralph engine**: full end-to-end tests for all three modes
  (manual/assisted/autopilot), including the stopping criteria, against
  real rendering and `FakeLLMClient`, plus resilience tests that script the
  model to fail (empty JSON, timeout) and assert the loop degrades to
  `RalphResult.notes` / `critique_unavailable` instead of crashing.
- **Transformations**: `test_transformations.py` exercises every `Transform`
  type applied to rows (filter / sort / aggregate / top-N / group-others /
  calculate), the list-order semantics, the string/number tolerance, and the
  missing-column skip-note.
- **Export**: a test unzips a produced `.sprezzature.zip` and runs
  `python reproduce.py` as an actual subprocess in the extracted
  directory, not just a string check that the template contains the
  right import.
- **The NiceGUI app**: a real subprocess-launched server, HTTP-checked for
  the expected page content (`test_app_smoke.py`). Deeper UI interaction
  (upload a file and click through via a simulated browser) was attempted
  with `nicegui.testing.User` and abandoned: the upload-simulation API
  assumed didn't exist in the installed nicegui version, and chasing it
  further wasn't worth it against the build plan's own caution against
  testing "every visual detail by pixel coordinates." Instead, every piece
  of non-NiceGUI logic behind the UI (`_load_upload`, `_resolve_data`,
  `_summarize_result`, `engine_status`, `SessionState` isolation) is unit
  tested directly.
- **Not covered**: the deterministic figure-recommendation *compatibility*
  engine (plan §6, not built yet, see [ROADMAP.md](ROADMAP.md)) and the
  history/export NiceGUI panels (backend tested, no UI wired up to call it
  yet). Live-model reliability on the harder chart edits (operations carrying
  a nested transform, or an intent-to-style-option mapping) is a known limit
  of small local models rather than a coverage gap; the engine handles a
  failed or dropped operation gracefully.

## CI

`.github/workflows/ci.yml` runs on 🍎 macOS, 🐧 Ubuntu, and 🪟 Windows, on
push to `main` and on pull requests:

- **`test` job**: ruff + the default suite + `-m slow`, across the 3 OSes ×
  Python 3.10 and 3.13 (6 combinations).
- **`packaging` job**, `-m packaging` on each of the 3 OSes (Python 3.12):
  builds the wheel, installs it clean, renders a figure, confirms the bare
  install stays studio-independent, then installs the `[studio]` extra and
  checks every studio subpackage imports and all three console scripts
  (`make-figure`, `sprezzature-figures`, `sprezzature-studio`) resolve.
  This is the check that the documented `pip install` procedures actually
  hold on a clean machine, on every supported OS.

CI caught a real bug local development never surfaced: `make_situation_map.py`
(since moved to the [sprezzature-maps](https://github.com/warith-harchaoui/sprezzature-maps)
repo, along with `choropleth`, but the bug and the lesson predate that
move) raised `SystemExit` (not an `Exception` subclass) at module import
time for a missing dependency, which killed the whole test run in a clean
environment where that dependency wasn't already installed globally (as it
happened to be on the development machine). Fixed at the source (see
`docs/studio/STATUS.md`'s Commit 10 entry for the full story).
