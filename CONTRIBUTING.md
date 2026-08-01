# Contributing

## Adding a new chart type

1. Create `scripts/make_<kind>.py` following the pattern of an existing script (e.g. `make_bar.py`).
2. The script must define:
   - `DEMO_DATA: list[dict]`, minimal self-contained example data.
   - `make_<kind>(data: list[dict], *, out: str | None = None, title: str = "", **kwargs) -> str`, returns the output file path as a string.
3. The function must work when called with no `out` argument (write to a temporary path or the current directory).
4. Add a row to [FIGURES.md](FIGURES.md) with the kind name, script name, category, and when-to-use guidance.
5. Run `make-figure <kind>` to verify the output.
6. Run `python -m pytest tests/ -q` to ensure no regressions.

## Code standards

- Full type annotations on all public functions.
- NumPy-style docstrings on all public functions and classes.
- 25–30 % comment density: explain *why*, not *what*.
- `ruff check` must pass with zero warnings.
- No unused imports.

## Commit style

Short imperative subject line (50 chars max). One blank line. Optional body.

Example: `add make_radar.py radar chart with DEMO_DATA`

## Licence

By contributing you agree that your code will be released under the BSD 3-Clause licence.
