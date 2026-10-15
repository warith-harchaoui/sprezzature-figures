# Worked examples that are not catalogue figures

`assets/svg-examples/` holds one SVG per catalogue kind, each written by its
`scripts/make_<kind>.py` and checked by `tests/test_committed_examples.py`.
Anything in there without a generator is drift, which is why the folder is
now tested rather than trusted.

This folder is for the other thing: hand-written SVG that teaches an idiom
rather than demonstrating a chart type.

- **`interactive-bar.svg`** — the native-`<title>` hover pattern, in the
  smallest document that shows it: five bars, no JavaScript, a tooltip and a
  dim-the-others rule that work from markup alone. Several generators point
  at it in their comments as the canonical statement of the idiom. It is not
  a catalogue kind — `bar` is — and it has no generator on purpose, because
  the point of it is to be read.

## Figures that moved out

Five map assets lived in `assets/svg-examples/` with no generator anywhere,
left behind by the v1.0.0 import: `choropleth`, `map-bivariate`,
`map-diverging`, `map-small-multiples` and
`fr-presidentielles-small-multiples`. All five shade territory, which is the
scope deliberately split off into
[sprezzature-maps](https://github.com/warith-harchaoui/sprezzature-maps) —
`FIGURES.md` has recorded that move for `choropleth` since it happened. They
were removed here rather than regenerated: the published gallery serves its
own copies, nothing in this repository referenced them, and a figure this
package cannot draw should not be sitting in the folder that promises it can.
