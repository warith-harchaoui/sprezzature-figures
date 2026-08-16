# Coding standards

## Language

Python 3.10+ (see `requires-python` in `pyproject.toml`). Full type
annotations on all public functions and classes.

## Style

- `ruff check` with zero warnings, `ruff format` applied, for
  `sprezzature_figures/` and `tools/` only. `pyproject.toml`'s
  `[tool.ruff] extend-exclude` deliberately leaves out `scripts/` (the 124
  `make_<kind>.py` chart generators) and `tests/`. Reason: `scripts/`
  keeps the older `List`/`Dict`/`Tuple` typing style and hand-formatted
  f-strings on purpose, so that two sibling generators stay easy to diff
  side by side and a stray `ruff format` never changes what a generator
  actually renders. Do not run `ruff --fix` or `ruff format` on
  `scripts/*.py`.
- Line length: 100 characters (`[tool.ruff] line-length` in
  `pyproject.toml`).
- Imports: standard library first, then third-party packages, then local
  modules, each group separated by a blank line.

## Docstrings

NumPy-style docstrings on all public functions and classes: a one-line
summary, then `Parameters`, `Returns`, `Raises`, `Examples` as needed. For
the length and detail level expected, read any `build_svg`/`make_<kind>`
pair in `scripts/`, for example `scripts/make_heatmap.py`.

## Comments

Comment density of 25 to 30 percent of lines. A comment explains *why*
something is done, never *what* the code already says in plain sight (if
the code needs a comment to say what it does, the fix is usually a better
name, not a comment). No commented-out code left behind.

## Script structure for make_*.py

`scripts/make_rose.py` is the reference "hero SVG" script: the pattern
every `make_<kind>.py` follows. Read it rather than a template copied
here, because a hand-written copy in this document goes stale the moment
the real convention moves on and the script does not. In short, each
script defines:

- `DEMO_DATA: List[Dict[str, Any]]`: a minimal, self-contained example
  dataset the script can render with no other input, used by the CLI's
  default run and by the tests.
- `build_svg(data=None, *, mode="self-contained", accessibility="universal", ..., theme="corporate") -> str`:
  assembles the chart and returns it as one complete SVG document
  (a string of XML-like markup a browser can display directly, with no
  external file it depends on). Every keyword parameter this function
  declares by name (never a catch-all `**kwargs`) is one tunable knob on
  the chart. `_render.py`'s `render_cli` reads that list of declared
  names through Python's own introspection and, for the ones it
  recognizes (`width`, `title`, `log_x`, `vmin`, `x_domain`, and so on,
  see `_OPTIONAL_FLAGS`), generates a matching `--flag` automatically. A
  new parameter can gain a working command-line flag this way with no
  argparse code to write by hand.
- `make_<kind>(data=None, *, out=None, ...) -> Path`: the function other
  code actually calls to get a chart. It calls `build_svg(...)` to get
  the SVG text, then `_render.write_svg(dest, svg, theme=theme)` to save
  it to disk, and returns the saved file's location as a `Path` object,
  never as a plain string.
- `def main(): render_cli(__file__, "<kind>", build_svg, description="...")`
  under `if __name__ == "__main__":`: the shared command-line entry
  point every script ends with. Shared helpers live in the sibling
  `_style.py`, `_svg.py`, `_render.py`, `_interactive.py`, and `_scale.py`
  modules; import what is needed from them instead of re-deriving axis
  math, color palettes, or the write-and-report steps inline in a new
  script.

`scripts/` is excluded from `ruff` and `ruff format` (see Style above),
so match the formatting of the sibling scripts by hand instead of running
the formatter on them.

## Testing

- The fast suite, run with `pytest -q` (the default `addopts` set in
  `pyproject.toml`), spans `tests/` broadly: `catalog/`, `studio/`,
  `ralph/`, `ingest/`, `core/`, plus `test_api.py`, `test_cli_recommend.py`,
  `test_mcp.py`, `test_make_figure.py`, and `test_generator_audit.py`. It
  is not limited to `test_make_figure.py`, and it must pass before any
  change lands.
- Tests marked `@pytest.mark.slow` render real figures and are excluded
  from the default run; run them with `pytest -m slow`. Tests marked
  `packaging`, `llm`, or `vision` are excluded from CI's default run too
  and have their own job or opt-in path (see `.github/workflows/ci.yml`).
- A change to `scripts/*.py` should also pass
  `python tools/audit_generators.py --render` (see CONTRIBUTING.md): that
  tool is what actually exercises all 124 generators end to end. There is
  no separate unit test per generator to keep in sync by hand.
- No mocking of file I/O or rendering. Tests exercise the real dispatcher,
  the same code path a real caller would run.

## Dependencies

Declare every dependency in `pyproject.toml` under `[project.dependencies]`.
Do not pin exact versions there; use `>=` lower bounds only, and reserve
exact pins for `requirements.txt`, whose only job is a reproducible
install.
