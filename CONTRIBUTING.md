# Contributing

## Adding a new chart type

This is the same procedure as README.md's own "Adding a chart type"
section, kept here in more detail. If the two ever disagree, fix both
together; do not just pick one and leave the other stale.

1. Create `scripts/make_<kind>.py`, modeled on `scripts/make_rose.py` (the
   reference "hero SVG" script; see CODING.md's "Script structure for
   make_*.py"), or on a close sibling if a more similar one already
   exists.
2. The script must define:
   - `DEMO_DATA: List[Dict[str, Any]]`, a minimal, self-contained example
     dataset.
   - `build_svg(data=None, *, mode=..., accessibility=..., theme=...) -> str`.
   - `make_<kind>(data=None, *, out=None, ...) -> Path`. Note the return
     type: a `Path` object, not a plain `str`, produced internally by
     `_render.write_svg`.
3. `make_<kind>` must work when called with no `out` argument at all. In
   that case it falls back to the skill's own
   `assets/svg-examples/<kind>.svg`, computed by
   `_render.svg_example_path(__file__, "<kind>")`.
4. Add a row to [FIGURES.md](FIGURES.md), in alphabetical order, with the
   kind's name, script name, category, and a short note on when to reach
   for it.
5. Run `python tools/audit_generators.py --render --timeout 40`, then
   `python tools/build_figures_catalog.py`. This step is not optional.
   Skip it, and `make_figure()`, the CLI, the HTTP API, and the MCP tools
   still cannot reach the new kind directly: they fall through to a
   deprecated compatibility path that prints a warning instead (see
   README.md's "Adding a chart type" for why that fallback exists). After
   running both commands, check that the diff to
   `sprezzature_figures/catalog/figures.json` only adds the new kind and
   does not change any other kind's recorded status.
6. Render the new SVG to a PNG
   (`python scripts/render_diagram.py <svg> --out x.png`) and actually
   look at the image before calling the chart finished. This is the
   project's own visual-review step, nicknamed the Ralph Eyeball Loop:
   problems like overlapping labels, a clipped subtitle, or a leader line
   crossing the whole figure are easy to miss while reading the SVG's
   source markup and obvious the moment you look at the rendered picture.
   Fix `build_svg`, not the PNG, then re-render and look again.
7. Run `python -m pytest -q` to check for regressions across the whole
   suite. For fast, targeted coverage of the catalog step specifically,
   run `pytest tests/test_generator_audit.py tests/catalog
   tests/test_make_figure.py`.

## Code standards

- Full type annotations on all public functions.
- NumPy-style docstrings on all public functions and classes.
- Comment density of 25 to 30 percent of lines: a comment explains *why*,
  never *what* the code already shows.
- `ruff check` and `ruff format` must both pass with zero warnings, for
  `sprezzature_figures/` and `tools/`. `scripts/` and `tests/` are
  excluded from both by `pyproject.toml`; match the existing style of the
  sibling scripts there by hand instead (see CODING.md for why).
- No unused imports.

## Commit style

`type: subject`, written in the imperative, with no hard length limit but
kept to one line. `fix:`, `figures:`, `refactor:`, and `docs:` are the
prefixes actually in use in this repository's history. Add a body when
something is not obvious: what broke, why this particular fix, what was
verified before committing.

Example: `figures: add make_radar.py radar chart with DEMO_DATA`

## Licence

By contributing you agree that your code will be released under the BSD 3-Clause licence.
