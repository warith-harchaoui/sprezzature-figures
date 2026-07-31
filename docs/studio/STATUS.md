# Sprezzature Studio — status

Maintained per commit while building Sprezzature Studio (see `.private/plan.md`
for the full spec; not itself committed). Branch: `feature/sprezzature-studio`.

## Phase

Phase 2 (§3 — stabilize catalogue and dispatcher), commit 1 of 13 landed.

## Completed

- **Commit 1 — Audit** (`tools/audit_generators.py`,
  `docs/studio/generator_audit.json`, `docs/studio/GENERATOR_AUDIT.md`,
  `tests/test_generator_audit.py`). Reproducible, exception-transparent audit
  of all 83 `scripts/make_*.py` generators against the `make_<kind>(data, *,
  out, title) -> Path` contract.

## Figures currently `stable`

Per the latest `--render` audit run: `columnrange`, `funnel`, `sunburst`,
`treemap`, `waterfall` (5 of 83). Target for MVP acceptance (plan §17): ≥10.

## Tests run

```
python3 -m pytest -q                          # 13 passed, 3 deselected
python3 -m pytest -q -m slow tests/test_generator_audit.py   # 1 passed
ruff check tools tests sprezzature_figures     # clean
```

## Known blockers / open questions

- `nicegui` is not installed anywhere in this environment yet — required for
  Commit 11 (`studio` extra, plan §15).
- `best-engine-ai-helper` (0.4.0) is installed and exposes
  `chat(prompt, *, system, images, json_schema, model, temperature)`; the
  plan's `LLMClient` protocol (§9.1, separate `chat_text`/`chat_vision`) will
  be adapted to wrap this single `chat()` signature rather than mirrored
  1:1.
- 17 generator scripts use hyphenated filenames the current dispatcher cannot
  reach at all (`connected-scatter`, `liquid-gauge`, `org-chart`, etc.) —
  fixed by the registry in Commit 2, not by patching the old normalisation.
- `sankey` has no `make_sankey()` — confirmed `legacy`; per plan §7 it must
  not be exposed in the GUI until rewritten to take real data (Commit 7).
- README/FIGURES.md `make_figure("bar", ...)` example refers to a script that
  does not exist (`make_bar.py`) — to be fixed in Commit 3b alongside the
  packaging corrections, once a real `bar` generator exists (Commit 6) or the
  example is swapped to an existing stable kind.

## Next

Commit 2 — explicit figure registry (`sprezzature_figures/catalog/`) with
canonical hyphenated kind names, aliases, and decoupled module/callable
names, so the dispatcher stops guessing filenames from kind names.
