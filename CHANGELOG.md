# Changelog

## 1.0.0 — 2026-07-29

Initial public release.

- 84 chart types across Vega-Lite, full Vega, matplotlib, and SVG renderers.
- `make_figure(kind, data, **kwargs)` unified dispatcher.
- `list_kinds()` returns all available chart types.
- `make-figure` CLI (argparse) always installed; Click CLI via `[cli]` extra.
- Ralph Eyeball Loop integration for autonomous visual QA (`audit_figure.py`).
- Full type annotations, ruff-clean, pytest test suite.
