# Coding standards

## Language

Python 3.11+. Full type annotations on all public functions and classes.

## Style

- `ruff check` with zero warnings. `ruff format` applied.
- Line length: 88 characters.
- Imports: stdlib → third-party → local, separated by blank lines.

## Docstrings

NumPy-style docstrings on all public functions and classes. Short summary line, then Parameters, Returns, Raises, Examples sections as needed.

```python
def make_bar(data: list[dict], *, out: str | None = None, title: str = "") -> str:
    """
    Render a vertical bar chart.

    Parameters
    ----------
    data : list[dict]
        Rows with keys ``label`` (str) and ``value`` (float).
    out : str | None, optional
        Output file path. Defaults to ``bar.png`` in the current directory.
    title : str, optional
        Chart title shown above the figure.

    Returns
    -------
    str
        Absolute path to the rendered output file.
    """
```

## Comments

25–30 % comment density. Explain *why*, never *what*. No commented-out code.

## Script structure for make_*.py

Each chart script must follow this structure:

```python
"""
Module docstring: what chart this is, when to use it.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

# ... imports ...

DEMO_DATA: list[dict] = [
    # minimal self-contained example data
]


def make_<kind>(
    data: list[dict],
    *,
    out: str | None = None,
    title: str = "",
    **kwargs,
) -> str:
    """Render the chart and return the output file path."""
    ...


if __name__ == "__main__":
    print(make_<kind>(DEMO_DATA))
```

## Testing

- All fast tests in `tests/test_make_figure.py` must pass with `pytest -q`.
- Slow render tests (requiring display or vl-convert) are marked `@pytest.mark.slow` and excluded from the default run.
- No mocking of file I/O or rendering. Test the real dispatcher.

## Dependencies

Declare all dependencies in `pyproject.toml` under `[project.dependencies]`. Do not pin exact versions in pyproject.toml (use `>=` lower bounds only). Pin in `requirements.txt` for reproducibility.
