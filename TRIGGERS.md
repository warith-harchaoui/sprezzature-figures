# Triggers

What a user might say, and what to call when they say it.

This file is written for an agent — a Claude Code / OpenCode skill, an MCP
host, anything choosing a tool on someone's behalf. Humans are welcome, but
the routing rules below are the point.

---

## The routing rule, in three lines

A chart request arrives in one of three shapes. Everything else is detail.

| The user… | Call | Because |
|---|---|---|
| **names a chart type** — "make a treemap", "un sankey de ces flux" | `render_figure` (MCP) / `make_figure()` / `make-figure <kind>` | They already chose. Resolve the name, shape the rows, draw. |
| **describes what they want to see** — "compare these regions", "montre l'évolution" | `recommend_figures` **first**, then `render_figure` | They have not chosen. Ranking beats guessing — see below. |
| **shows a picture of an existing chart** — a screenshot, "améliore ça" | `redraw_figure` / `redraw()` / `sprezzature-figures redraw` | The design is in the image; the data usually is not. |

---

## Do not try to memorise 127 chart names

The catalogue is open-ended and grows; the vocabulary of **intent** is
closed. Route on the intent, let the tool pick the kind.

Nine goals are all `recommend_figures` accepts, and between them they cover
the ordinary run of requests. Match the user's sentence to one of these, send
the rows, and take the top candidate — it arrives with its column bindings
already worked out.

| Goal | What the user is saying (EN) | En français | Kinds it reaches for |
|---|---|---|---|
| `comparison` | "compare X and Y", "which is biggest", "rank these" | « comparer », « lequel est le plus gros », « classer » | bar, lollipop, dumbbell, bullet |
| `trend` | "over time", "has it grown", "since January" | « dans le temps », « l'évolution », « depuis janvier » | line, area, step, horizon, calendar-heatmap |
| `distribution` | "how spread out", "outliers", "is it normal" | « la dispersion », « les valeurs aberrantes » | boxplot, beeswarm, bellcurve, boxen, ridgeline |
| `composition` | "what is it made of", "share of total", "breakdown" | « de quoi c'est fait », « la part de », « la répartition » | stacked-bar, donut, waffle, treemap |
| `relationship` | "does X drive Y", "correlated", "versus" | « est-ce que X explique Y », « corrélé », « en fonction de » | scatter, jointplot, parcoords, corr-matrix |
| `flow` | "where does it go", "from A to B", "the pipeline" | « d'où ça vient, où ça va », « le parcours » | sankey, alluvial, chord, funnel |
| `hierarchy` | "nested", "the org", "folders", "parent and child" | « emboîté », « l'organigramme », « l'arborescence » | treemap, sunburst, icicle, tree, circle-packing |
| `geography` | "by region", "on a map", "per country" | « par région », « sur une carte », « par pays » | hexmap, spike-map, dotdensity, binned-grid-map |
| `model_evaluation` | "is my model any good", "ROC", "confusion matrix" | « mon modèle est-il bon », « matrice de confusion » | roc-curve, prcurve, calibration, confusion-matrix |

**When no goal fits**, the request is still valid — the catalogue reaches
well past the nine. Call `list_kinds` and match on the user's own noun:
finance (candlestick, bollinger), signals (spectrogram, quiver), sets (venn,
upset), planning (gantt, timeline), genomics (manhattan, volcano), text
(wordcloud), 3-D surfaces, dimensionality reduction. `get_kind` then says
what the rows must carry.

### The generalisation, stated once

> **Any sentence that means "I want to see this data" is a trigger.**
> Do not wait for the word "chart". "Can you show me…", "what does this look
> like", "put this in a picture", "fais-moi voir", "un visuel de ça" — all of
> it routes here. The only question is which of the three shapes above it is,
> and if it is the middle one, `recommend_figures` answers it for you.

---

## Phrasings, for matching

Not a closed list — the intent table above is the mechanism; these are
confirmations.

**English** — "make a chart", "draw a graph", "plot this", "visualise this
data", "show me a figure", "I need a bar chart / treemap / scatter / sankey",
"publication-quality figure", "what chart types are available", "which chart
fits my data", "redraw this chart", "make this ugly chart better", "here is a
screenshot of a chart, improve it", "my colleague sent me this graph, make it
readable", "what is wrong with this chart", "run the eyeball loop", "QA this
chart visually".

**Français** — « faire un graphique », « tracer ce graphe », « visualiser ces
données », « montre-moi une figure », « j'ai besoin d'un histogramme / d'une
carte proportionnelle / d'un nuage de points », « figure de qualité
publication », « quels types de graphiques existent », « quel graphique pour
ces données », « refaire ce graphique », « rendre ce graphique plus lisible »,
« voici une capture, tu peux l'améliorer ? », « qu'est-ce qui ne va pas dans
ce graphique ? », « passer la boucle Eyeball », « contrôle qualité visuel ».

---

## What to call, on every surface

| Job | Library | CLI | MCP tool |
|---|---|---|---|
| List the catalogue | `list_kinds()` | `make-figure --list` | `list_kinds` |
| What columns a kind needs | `get_figure_definition(kind)` | — | `get_kind` |
| Which kind fits this data | — | `sprezzature-figures recommend --data f.csv` | `recommend_figures` |
| Draw it | `make_figure(kind, rows, out=…)` | `make-figure <kind> --data f.csv` | `render_figure` |
| Redraw from a picture | `redraw(image, out=…)` | `sprezzature-figures redraw img.png` | `redraw_figure` |
| Visual QA on a rendered figure | — | `ralph_eyeball_loop.py <file>` | *(not an MCP tool)* |

The dashes are honest gaps, not omissions: the eyeball loop needs a browser
and a model and does not belong behind an HTTP request, and `recommend` has
no library alias because its ranking lives in the Studio package rather than
the core.

---

## Two contracts an agent must not break

**1. `render_figure` takes a catalogue name, not a description.** There is no
`--x/--y/--kind` combinator and no plotting-library backend behind this: all
127 kinds are SVG authored directly. If the user asks for output "in
<library>", say plainly that this package does not use one, and draw the
figure.

**2. `redraw_figure` tells you where its numbers came from — read it.**
`data_origin` is `your-data` (you sent rows; the real figure),
`read-from-image` (printed on the original and read back; approximate — say
so) or `demo` (nothing readable, so the figure carries the kind's **sample**
rows). On `demo`, tell the user those are not their numbers and ask for the
data. Presenting a mock-up as their figure is the one failure this tool can
cause.

---

## Typical call pattern

```python
from sprezzature_figures import make_figure

path = make_figure(kind, data, out="output.png", title="My chart")
```

All 127 kinds and the `data` shape each expects are in [FIGURES.md](FIGURES.md).
