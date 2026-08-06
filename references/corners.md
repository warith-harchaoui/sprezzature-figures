# The Sprezzature Corner Policy

*A house policy for corners and corner radii across every sprezzature surface:
figures (`sprezzature-figures`), UI (`sprezzature-ui`), and published pages
(`sprezzature-publish`). Load this before choosing any `rx` / `border-radius` /
`cornerRadius` value.*

## 1. Ethos

Sprezzatura is studied nonchalance: the polish should look effortless, never
fussy. Corners carry a lot of that feeling. Two failure modes to avoid:

- **Too sharp everywhere** reads as unfinished / default-toolkit.
- **Too round, or rounded in the wrong places** reads as a toy, and on data
  marks it actively *lies* (a rounded bar cap hides where the value ends).

So the policy is not "round everything a bit." It is: **round the chrome and the
free ends generously and smoothly; keep the measurements and the grid crisp; let
radius scale with the mark and cap early.**

## 2. Learn from Apple: continuous curvature + concentricity

Apple's corners are worth copying for two specific ideas, not for a single magic
number.

**a) Continuous curvature (the "squircle").** Apple corners are a *superellipse*,
not a circular arc: the curvature ramps up gradually from the straight edge
instead of snapping to a fixed-radius arc. This is the "continuous" corner style
(`RoundedRectangle(cornerRadius:style: .continuous)` in SwiftUI; iOS icons sit
near a quintic superellipse, n ≈ 5; the icon grid uses a corner radius ≈ 22.37%
of width with corner-smoothing ≈ 60%). It simply looks calmer.

- **Where the medium supports it, use continuous corners.** UI: CSS
  `corner-shape: superellipse()` where available (Chromium 139+), else the
  Figma/SwiftUI-style smoothed path; native apps: `.continuous`. Figma:
  corner smoothing ≈ **60%**.
- **Where it does not (plain SVG `rx`/`cornerRadius`, older CSS): fall back to a
  circular arc.** A circular radius from this policy is always acceptable; the
  squircle is the upgrade, not a requirement. Do **not** hand-roll superellipse
  path math in every figure — reach for it only in the few hero SVGs where the
  container shape is prominent.

**b) Concentric nesting (Apple's `ConcentricRectangle`, iOS 26).** When a rounded
element sits inside a rounded container, their curves must share a center or the
gap looks lumpy. The rule:

> **inner radius = outer radius − gap** (the padding between them).
> If the gap ≥ the outer radius, the inner corner is **square (0)**.

Apply this to every nested rounded thing: a chart panel inside a card, a legend
chip inside a legend box, an inset (the elbow difference-curve panel) inside the
main frame, a tooltip inside the figure.

## 3. The radius scale (tokens)

One scale, expressed in both units. UI uses the rem tokens (already in
`studio/theme.py`); figures use the px tokens (add to `scripts/_style.py`).
SVG has no relative radius, so figures pick the px token nearest the mark size.

| Token | px (figures) | rem (UI) | Use |
|---|---|---|---|
| `corner-none` | 0 | 0 | measurements, grids, adjacent/baseline corners |
| `corner-hairline` | 1 | — | the *most* a grid cell may ever have |
| `corner-xs` | 2–3 | .1875 | tiles (treemap/mosaic/waffle), arc segments, small chips |
| `corner-sm` | 4 | .375 | bar value-ends, legend swatches, small controls |
| `corner-md` | 6–8 | .5 | buttons, inputs, node boxes, badges, tooltips |
| `corner-lg` | 12 | .75 | cards, chart panels, the figure frame |
| `corner-xl` | 16 | 1 | large containers / hero panels |
| `corner-full` | ∞ (h/2) | 9999px | pills (entity nodes), dots, toggles, avatars |

## 4. The sizing rule (size-relative, capped)

A big mark can take a big radius; a small one cannot, or it turns to mush. So
radius is proportional to the mark's **smaller** dimension, clamped:

```
radius = clamp(0, k · min(width, height), cap)
```

- Bars / columns: `k = 0.18`, `cap = corner-sm (4px)`.
- Tiles (treemap/mosaic/waffle): `k = 0.12`, `cap = corner-xs`, **and** `radius ≤
  gap/2` so tiles never overlap their white separators.
- Arc segments (pie/donut/sunburst/rose/radial-bar): `cap = corner-xs (2–3px)`,
  and `radius ≤ (arc thickness)/2` and `≤ (angular gap)/2`.
- Panels / cards: fixed `corner-lg`/`corner-xl` (chrome doesn't scale with data).

Below ~8px in the smaller dimension the cap drives radius to ~0 — tiny marks stay
square. That is intended.

## 5. Per-mark-family rules

- **Bars & columns.** Round **only the value end** (the two corners away from the
  baseline); the baseline corners stay square so bars sit flat on the axis.
  Grouped/stacked: only the outermost segment's free
  end rounds; internal stack joins stay square so the part-of-whole reads.
  Keep it subtle — the cap is 4px precisely because an over-rounded cap hides
  where the value ends.
- **Pie / donut / sunburst / rose / radial-bar.** A *gentle* `cornerRadius`
  (2–3px), never more, so slices still read as one whole. Never round so much
  that a thin slice becomes a lozenge.
- **Treemap / mosaic / icicle / waffle.** Small uniform radius (`corner-xs`) with
  a white gap; radius ≤ half the gap. A waffle "unit" that is conceptually a dot
  may go `corner-full`.
- **Node boxes / pills** (org-chart, tree, flow, network, parliament legend).
  *Entities* → `corner-full` (capsule). *Boxes/containers of text* → `corner-md`.
  Size boxes to the text first (see the adaptive-layout policy), then round.
- **Cards, panels, the figure frame, tooltips, callouts, badges** → `corner-lg`
  (frame/cards), `corner-md` (tooltips/badges). Apply concentricity (§2b).
- **Points, bubbles, dots** (scatter, dotplot, packed-bubble, beeswarm) → circles
  by nature. Marker shapes used to separate series for colour-blind readers
  (square, triangle, diamond) **keep their sharp corners** — the shape is the
  signal.
- **Lines, areas, connectors** → `stroke-linejoin: round`, `stroke-linecap:
  round` for a soft, confident stroke. Area fills are **not** corner-rounded.

## 6. Never round (crisp = honest)

- **Measurement / precision marks**: candlestick bodies & wicks, box-plot boxes &
  whiskers, error bars, gauge ticks, axis ticks, reference/target lines. Rounding
  reads as imprecision.
- **Grid cells**: heatmap, correlation matrix, confusion matrix, clustermap,
  calendar heatmap. At most `corner-hairline (1px)`; default 0 — the grid is the
  message.
- **Any corner that meets an axis, a baseline, or an adjacent mark.** Alignment
  and adjacency beat softness.
- **Marks smaller than ~8px** in the smaller dimension (the cap handles this).

## 7. Dark mode / forced-colors / CVD

Radius is geometry, not colour: it is **identical** across light, dark,
high-contrast and forced-colors. Never change a radius per theme.

## 8. Implementation hooks

- **Tokens.** The px scale lives in `scripts/_style.py` (mirroring the rem tokens in
  `studio/theme.py`) as the `CORNERS` dict and the `corner_radius(w, h, family)`
  helper implementing §4.
- **Per-generator application.** Each `make_<kind>.py` SVG generator calls
  `_style.corner_radius()` directly and writes the result into its own `rx=`/`ry=`
  attributes — bars round the value end, arcs get the gentle radius, grids stay
  square, per §5 above.
- **Concentricity helper**: `inner_radius(outer, gap) = max(0, outer - gap)`.
- **Auditor rule** (`scripts/audit_figure.py`): flag (a) grid-cell marks with
  radius > 1px, (b) bars rounded on the baseline side, (c) any radius above its
  family cap, (d) a nested element whose radius ≠ `outer − gap`.
- **Migration**: today generators hand-set `rx="2".."22"` ad hoc (survey:
  `rx=3/5/7/6` common). Replace with token lookups so the scale is enforced, not
  guessed.

## 9. One-line checklist

1. Is this a **measurement or a grid**? → square. Stop.
2. Is it **chrome** (card/panel/frame/tooltip)? → `corner-lg`/`corner-md`, and
   apply concentricity to anything nested in it.
3. Is it an **entity node**? → capsule (`corner-full`).
4. Otherwise it's a **data mark**: radius = `clamp(0, k·min_dim, cap)`, round only
   free ends, keep it subtle.
5. Can the medium do **continuous corners**? → use them; else a circular arc of
   the same radius is fine.

## Sources

- [How Apple Uses Squircles in iOS Design](https://squircle.js.org/blog/squircles-in-apple-design)
- [The Math Behind iOS Bezels: Continuous Curvature vs. Standard CSS Border-Radius](https://www.appscreenstudio.com/en/blog/understanding-ios-squircle-continuous-curvature)
- [Squircles in CSS: corner-shape, superellipse() and Browser Support (2026)](https://squircle.js.org/blog/squircles-in-css)
- [Corner concentricity in SwiftUI on iOS 26](https://nilcoalescing.com/blog/ConcentricRectangleInSwiftUI/)
- [Concentric Radius: Nested Corners Done Right](https://pv21design.pt/concentric-radius-nested-corners-done-right/)
- [Bar Charts Best Practices (on rounded bar caps)](https://nastengraph.medium.com/bar-charts-best-practices-5e81ebc7b340)
- [Rounded-tip bar charts — Vizstas](https://vizstas.com/2020/08/20/rounded-tip-bar-charts/)
