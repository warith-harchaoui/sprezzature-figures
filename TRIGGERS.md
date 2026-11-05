# Triggers

What a user might say, and what to call when they say it.

This file is written for an agent: a Claude Code or OpenCode skill, an MCP
(Model Context Protocol) host, anything choosing a tool on someone's behalf.
Humans are welcome, but the routing rules below are the point.

---

## The generalisation, stated first

> **Any sentence that means "I want to see this data" is a trigger, and so is
> any sentence that hands over a picture of a chart or a rendered figure.**
> Do not wait for the word "chart". "Can you show me…", "what does this look
> like", "put this in a picture", « fais-moi voir », « un visuel de ça » all
> route here.

Route on the domain's closed vocabulary, not on phrasings. Phrasings are
open-ended; the vocabulary this package answers to is closed and can be listed
from the code:

1. **Four request shapes.** The user names a chart type, describes what they
   want to see, shows a picture of an existing chart, or hands over a rendered
   figure to be checked. Each shape has one first call (table below).
2. **Nine goals.** `comparison`, `trend`, `distribution`, `composition`,
   `relationship`, `flow`, `hierarchy`, `geography`, `model_evaluation`. That
   is the whole list `recommend_figures` accepts as `goal`.
3. **167 kind names.** The catalogue is a closed set, returned by `list_kinds`.
   `render_figure` takes a name from it, never a free description.

Match the user's sentence to a shape, then to a goal, and let the tool pick
the kind. The phrase tables further down are confirmations of that mapping,
not the mechanism.

| The user… | First call | Because |
|---|---|---|
| **names a chart type**: "make a treemap", « un sankey de ces flux » | `render_figure` (after `get_kind` if the row shape is unclear) | They already chose. Resolve the name, shape the rows, draw. |
| **describes what they want to see**: "compare these regions", « montre l'évolution » | `recommend_figures` with a `goal`, then `render_figure` | They have not chosen. Ranking beats guessing. |
| **shows a picture of an existing chart**: a screenshot, « améliore ça » | `redraw_figure` | The design is in the image; the data usually is not. |
| **hands over a rendered SVG**: "is this OK to ship", "the labels overlap" | `check_render` | The failures it finds are decidable from markup, with no model. |

A request about numbers attached to real places drawn as filled regions (a
choropleth, a situation map) belongs to
[sprezzature-maps](https://github.com/warith-harchaoui/sprezzature-maps), not
here. The glyph maps (`map-bars`, `map-bubble`, `map-flow`, `map-pie`,
`map-tilegrid`) and the other geographic kinds below are here.

---

## The nine goals

Send the rows with the goal that matches the sentence and take the top
candidate: it arrives with its column bindings already worked out. The goal
ranks first the kinds whose catalogue category serves it; the compatibility
filter has already dropped every kind your columns cannot fill.

| Goal | What the user is saying (EN) | En français | Kinds it ranks first, among others |
|---|---|---|---|
| `comparison` | "compare X and Y", "which is biggest", "rank these" | « comparer », « lequel est le plus gros », « classer » | bar, lollipop, bump, pareto, dual-axis |
| `trend` | "over time", "has it grown", "since January" | « dans le temps », « l'évolution », « depuis janvier » | line, step, horizon, slope, calendar-heatmap |
| `distribution` | "how spread out", "outliers", "is it normal" | « la dispersion », « les valeurs aberrantes » | boxplot, beeswarm, histogram, violin, ridgeline |
| `composition` | "what is it made of", "share of total", "breakdown" | « de quoi c'est fait », « la part de », « la répartition » | stacked-bar, donut, waffle, treemap, waterfall |
| `relationship` | "does X drive Y", "correlated", "versus" | « est-ce que X explique Y », « corrélé », « en fonction de » | scatter, jointplot, parcoords, pairplot |
| `flow` | "where does it go", "from A to B", "the pipeline" | « d'où ça vient, où ça va », « le parcours » | sankey, alluvial, chord, funnel, network |
| `hierarchy` | "nested", "the org", "folders", "parent and child" | « emboîté », « l'organigramme », « l'arborescence » | treemap, sunburst, icicle, tree, circle-packing |
| `geography` | "by region", "on a map", "per country" | « par région », « sur une carte », « par pays » | hexmap, spike-map, dotdensity, map-bubble, windrose |
| `model_evaluation` | "is my model any good", "ROC", "confusion matrix" | « mon modèle est-il bon », « matrice de confusion » | roc-curve, prcurve, calibration, confusion-matrix, qqplot |

**When no goal fits**, the request is still valid. 54 of the catalogue's
entries sit in a category no goal matches (finance, KPI, signals, 3-D, model
explanation, sets, text…), so a goal cannot bring them to the top. Match the user's own noun against
[the per-kind tables below](#every-kind-and-the-sentence-that-reaches-it), then
call `get_kind` for what the rows must carry.

---

## Every tool, and the request it answers

| Tool | Where it lives | The request it answers |
|---|---|---|
| `render_figure` | MCP, `POST /render/{kind}`, `make_figure()`, `sprezzature-figures render` | "Draw this data as a bar chart / treemap / sankey." |
| `recommend_figures` | MCP, `POST /recommend`, `sprezzature-figures recommend` | "Which chart should I use for this data?" |
| `list_kinds` | MCP, `GET /kinds`, `list_kinds()`, `sprezzature-figures list` | "What chart types are there?" |
| `get_kind` | MCP, `GET /kinds/{kind}`, `get_figure_definition()`, `sprezzature-figures describe` | "Which columns does a sankey need?" |
| `list_kind_options` | MCP, `GET /kinds/{kind}/options`, `options_for()`, `sprezzature-figures describe` | "Can I set the subtitle, the width, the unit?" |
| `redraw_figure` | MCP, `POST /redraw`, `redraw()`, `sprezzature-figures redraw` | "Here is a screenshot of a chart, make it readable." |
| `check_render` | MCP, `POST /check_render`, `check_render()`, `sprezzature-figures check` | "Is anything wrong with this SVG before I ship it?" |
| `health` | MCP, `GET /health` | Only "is the figure server answering?", to diagnose a connection. |
| `validate_figure_input` | library | "Will these rows fit this kind?", without rendering. |
| `to_dark` | library | "Make this rendered SVG work on a dark page." |
| `as_rows` | library | "Turn my DataFrame into the rows a figure takes." |
| `text_width` | library | "How wide will this label be?", to lay out beside these figures. |
| `sprezzature-studio` | console command | "Let me import a spreadsheet and edit a chart by chatting." |
| `ralph_eyeball_loop.py` | repository script | "Does this figure, page or diagram actually read? QA it visually." |
| `render_diagram.py` | repository script | "Render this Mermaid or TikZ source to PNG." |
| `audit_figure.py` | repository script | "Audit these SVG charts, or the `<figure>` blocks of this HTML page." |
| `explain_model.py` | repository script | "Explain my model: SHAP, Shapash, TimeSHAP or LIME plots." |
| `causal_estimate.py` | repository script | "Estimate the causal effect of X on Y, given this DAG (directed acyclic graph)." |
| `install_figures.py` | repository script | "Install the pinned data-viz, explainability or causality tier." |

The six repository scripts have no console command of their own, but the
wheel carries them: once installed, each runs as
`python -m sprezzature_figures_scripts.<name>` (`ralph_eyeball_loop`,
`render_diagram`, `audit_figure`, `explain_model`, `causal_estimate`,
`install_figures`).

The MCP server (`sprezzature-figures-mcp`) publishes exactly eight tools:
`health`, `list_kinds`, `get_kind`, `list_kind_options`, `recommend_figures`,
`render_figure`, `redraw_figure` and `check_render`. Each tool name is the
route's FastAPI `operation_id`.

---

## What to call, on every surface

| Job | Library (`sprezzature_figures`) | CLI | MCP tool (`operation_id`) | HTTP route |
|---|---|---|---|---|
| List the catalogue | `list_kinds(status=…)` | `sprezzature-figures list [--status stable] [--json]` | `list_kinds` | `GET /kinds` |
| What columns a kind needs | `get_figure_definition(kind)` | `sprezzature-figures describe <kind>` | `get_kind` | `GET /kinds/{kind}` |
| What else a kind accepts | `options.options_for(kind)` | `sprezzature-figures describe <kind>`, `render <kind> --help` | `list_kind_options` | `GET /kinds/{kind}/options` |
| Which kind fits this data | none at top level | `sprezzature-figures recommend --data f.csv [--intent GOAL]` | `recommend_figures` | `POST /recommend` |
| Draw it | `make_figure(kind, rows, out=…)` | `sprezzature-figures render <kind> --data f.csv --out f.svg` | `render_figure` | `POST /render/{kind}` |
| Set a figure's own options | `make_figure(kind, rows, width=…)` | `render <kind> --width …` or `--set width=…` | `render_figure` (`options`) | `POST /render/{kind}` (`options`) |
| Redraw from a picture | `redraw(image, out=…)` | `sprezzature-figures redraw img.png` | `redraw_figure` | `POST /redraw` |
| Check a rendered SVG | `check_render(svg)` | `sprezzature-figures check fig.svg` | `check_render` | `POST /check_render` |
| Is the server up | none | none | `health` | `GET /health` |
| Visual QA on a rendered figure | none | `python scripts/ralph_eyeball_loop.py <file>` from a clone, `python -m sprezzature_figures_scripts.ralph_eyeball_loop <file>` once installed | none | none |

`make-figure` is the same Click group as `sprezzature-figures`: every CLI cell
works under either name.

The gaps are deliberate. The eyeball loop needs a browser and a model and does
not belong behind an HTTP request. Recommendation has no top-level library
function: its ranking lives in the Studio package, as
`sprezzature_figures.studio.recommendation.rank(profile, goal=…)` over a
profile built by `studio.ingest.profiler.profile_dataframe`.

An option a figure does not accept is refused, not ignored: the command line
names the ones it does accept, the API answers 422. Ask `list_kind_options`
(or `describe`) before guessing one.

---

## Two contracts an agent must not break

**1. `render_figure` takes a catalogue name, not a description.** There is no
`--x/--y/--kind` combinator and no plotting-library backend behind this: all
167 kinds are SVG authored directly. If the user asks for output "in
<library>", say plainly that this package does not use one, and draw the
figure.

**2. `redraw_figure` tells you where its numbers came from. Read it.**
`data_origin` is `your-data` (you sent rows; the real figure),
`read-from-image` (printed on the original and read back; approximate, say
so) or `demo` (nothing readable, so the figure carries the kind's **sample**
rows). On `demo`, tell the user those are not their numbers and ask for the
data. Presenting a mock-up as their figure is the one failure this tool can
cause.

---

## Phrasings, for matching

Not a closed list: the shapes and goals above are the mechanism; these are
confirmations.

**English**: "make a chart", "draw a graph", "plot this", "visualise this
data", "show me a figure", "I need a bar chart / treemap / scatter / sankey",
"publication-quality figure", "what chart types are available", "which chart
fits my data", "redraw this chart", "make this ugly chart better", "here is a
screenshot of a chart, improve it", "my colleague sent me this graph, make it
readable", "what is wrong with this chart", "check this SVG", "run the eyeball
loop", "QA this chart visually".

**Français** : « faire un graphique », « tracer ce graphe », « visualiser ces
données », « montre-moi une figure », « j'ai besoin d'un histogramme / d'une
carte proportionnelle / d'un nuage de points », « figure de qualité
publication », « quels types de graphiques existent », « quel graphique pour
ces données », « refaire ce graphique », « rendre ce graphique plus lisible »,
« voici une capture, tu peux l'améliorer ? », « qu'est-ce qui ne va pas dans
ce graphique ? », « vérifie ce SVG », « passer la boucle Eyeball », « contrôle
qualité visuel ».

---

## Every kind, and the sentence that reaches it

Route on the nine goals first: they answer the ordinary request without
anyone naming a chart. These tables are for the rest: when a user reaches for
a domain noun ("the ROC curve", « la rose des vents », "a Gantt"), when the
recommender's top candidate looks wrong, or when you want to know what else
was on the shelf. All 167 kinds appear once.

Read them as *triggers*, not as definitions: the phrase is what someone says,
the kind is what to call. The last column is computed from the code: the goal
whose category keywords match the kind's catalogue category, or `none` when no
goal ranks it first. The sections group kinds by meaning, so a section and a
goal do not always coincide. [FIGURES.md](FIGURES.md) says what each kind draws
and what its rows must carry; `get_kind` says it at run time.


### Compare and rank

| Kind | They say | Ils disent | Goal that ranks it first |
|---|---|---|---|
| `bar` | "compare these categories, which is biggest" | « comparer ces catégories, lequel est le plus gros » | `comparison` |
| `bar-grouped` | "by quarter and by product, side by side" | « par trimestre et par produit, côte à côte » | `comparison` |
| `lollipop` | "a ranked bar chart that is not so heavy" | « un classement en barres, mais plus léger » | `comparison` |
| `dumbbell` | "before and after, per category" | « avant / après, par catégorie » | `trend` |
| `slope` | "who moved between these two dates" | « qui a bougé entre ces deux dates » | `trend` |
| `bump` | "who overtook whom in the rankings" | « qui a doublé qui au classement » | `comparison` |
| `dual-axis` | "revenue and conversion rate on one chart" | « le chiffre d'affaires et le taux sur un même graphique » | `comparison` |
| `difference-chart` | "how far apart these two series are" | « l'écart entre ces deux séries » | `comparison` |
| `variwide` | "big bars for big markets, wide for volume" | « des barres hautes par valeur, larges par volume » | `comparison` |
| `packed-bubble` | "a prettier pie, many categories" | « un camembert plus joli, beaucoup de catégories » | `comparison` |
| `radial-bar` | "bars bent into a circle, for the slide" | « des barres en cercle, pour la présentation » | `comparison` |
| `bubble` | "three measures at once, by country" | « trois mesures d'un coup, par pays » | `comparison` |
| `pareto` | "which few causes make most of the trouble" | « quelles rares causes font l'essentiel des ennuis » | `comparison` |
| `columnrange` | "the min and max per category" | « le mini et le maxi par catégorie » | `distribution` |
| `bar3d` | "a grid of categories with a height each" | « une grille de catégories avec une hauteur chacune » | `comparison` |
| `table` | "just give me the numbers in a table" | « donne-moi simplement les chiffres dans un tableau » | none |


### Over time

| Kind | They say | Ils disent | Goal that ranks it first |
|---|---|---|---|
| `line` | "how has this changed since January" | « l'évolution depuis janvier » | `trend` |
| `line-multi` | "several series over the hours of the day" | « plusieurs séries au fil des heures » | `trend` |
| `step` | "the price held, then jumped" | « le tarif a tenu, puis a sauté » | `trend` |
| `area` | "the total over time, split by category" | « le total dans le temps, par catégorie » | `composition` |
| `stacked-area` | "the same, on a numeric time axis" | « pareil, sur un axe de temps numérique » | `composition` |
| `streamgraph` | "how the mix flowed over the years" | « comment le mélange a coulé au fil des ans » | `trend`, `composition` |
| `sparkline` | "twenty metrics on one page, no axes" | « vingt indicateurs sur une page, sans axes » | `trend` |
| `horizon` | "forty series stacked in little space" | « quarante séries empilées en peu de place » | `trend` |
| `calendar-heatmap` | "activity per day, GitHub style" | « l'activité jour par jour, façon GitHub » | `trend` |
| `timeline` | "the phases of the project, end to end" | « les phases du projet, de bout en bout » | `trend` |
| `gantt` | "the schedule with owners and overlaps" | « le planning avec les responsables » | none |
| `connected-scatter` | "how the two moved together over time" | « comment les deux ont bougé ensemble » | `trend`, `relationship` |
| `seasonal-decomposition` | "split it into trend and season" | « séparer la tendance de la saison » | `composition` |
| `forecast-fan` | "the forecast with its uncertainty" | « la prévision avec son incertitude » | none |
| `acf` | "is there autocorrelation, at which lag" | « y a-t-il autocorrélation, à quel décalage » | `relationship` |
| `control-chart` | "is this process in control" | « ce procédé est-il sous contrôle » | none |
| `cohort-retention` | "how many come back, by signup month" | « combien reviennent, par mois d'inscription » | none |


### Spread and shape

| Kind | They say | Ils disent | Goal that ranks it first |
|---|---|---|---|
| `histogram` | "how is this spread out" | « comment c'est réparti » | `distribution` |
| `kde1d` | "a smooth density rather than bins" | « une densité lisse plutôt que des classes » | `distribution` |
| `bellcurve` | "is my sample roughly normal" | « mon échantillon est-il à peu près normal » | `distribution` |
| `boxplot` | "median, quartiles, outliers per group" | « médiane, quartiles, valeurs aberrantes » | `distribution` |
| `boxen` | "a box plot that keeps the far tail" | « une boîte qui garde la queue lointaine » | `distribution` |
| `violin` | "the shape of each group's distribution" | « la forme de chaque distribution » | `distribution` |
| `beeswarm` | "every point, none hidden behind another" | « chaque point, aucun caché derrière un autre » | `distribution` |
| `strip` | "all the points, jittered, thousands of them" | « tous les points, dispersés, par milliers » | `distribution` |
| `dotplot` | "small sample, I want to count the dots" | « petit échantillon, je veux compter les points » | `distribution` |
| `ridgeline` | "many groups' densities, stacked" | « les densités de beaucoup de groupes, empilées » | `distribution` |
| `ecdf` | "what share falls below this value" | « quelle part est sous cette valeur » | `distribution` |
| `rug` | "mark the individual observations on the axis" | « marquer les observations sur l'axe » | `distribution` |
| `errorbar` | "the estimate with its confidence interval" | « l'estimation avec son intervalle de confiance » | `distribution` |
| `pointplot` | "the estimates per group, joined" | « les estimations par groupe, reliées » | `distribution` |
| `population-pyramid` | "men and women by age band" | « hommes et femmes par tranche d'âge » | `distribution` |
| `hexbin` | "a scatter so dense it is a blob" | « un nuage si dense qu'il fait une tache » | `distribution` |
| `qqplot` | "is this normally distributed" | « cette distribution est-elle normale » | `model_evaluation` |
| `ppplot` | "check the fit in the middle, not the tails" | « vérifier l'ajustement au centre » | `model_evaluation` |
| `blandaltman` | "do these two instruments agree" | « ces deux appareils sont-ils d'accord » | `model_evaluation` |


### What it is made of

| Kind | They say | Ils disent | Goal that ranks it first |
|---|---|---|---|
| `pie` | "the share of each, as a pie" | « la part de chacun, en camembert » | `composition` |
| `donut` | "a pie with the total in the middle" | « un camembert avec le total au centre » | `composition` |
| `stacked-bar` | "the mix per group, as percentages" | « le mélange par groupe, en pourcentages » | `composition` |
| `waffle` | "a hundred squares, so people can count" | « cent carrés, pour qu'on puisse compter » | `composition` |
| `pictorial` | "icons instead of bars, for the public" | « des icônes au lieu de barres, grand public » | none |
| `treemap` | "the budget by division then by team" | « le budget par division puis par équipe » | `composition`, `hierarchy` |
| `parliament` | "the seats after the election" | « les sièges après l'élection » | `composition` |
| `mosaic` | "two categorical variables crossed" | « deux variables qualitatives croisées » | none |
| `ternary` | "three parts that add up to one" | « trois composants dont la somme fait un » | `composition` |
| `waterfall` | "from last year's figure to this year's" | « du chiffre de l'an dernier à celui de cette année » | `composition` |
| `funnel` | "the drop-off through the stages" | « la déperdition étape par étape » | `flow` |
| `funnel-area` | "the same taper, as a shape" | « le même entonnoir, comme une forme » | `flow` |


### Does X explain Y

| Kind | They say | Ils disent | Goal that ranks it first |
|---|---|---|---|
| `scatter` | "is there a link between these two" | « y a-t-il un lien entre ces deux-là » | `relationship` |
| `jointplot` | "the scatter plus each margin" | « le nuage, plus chaque marge » | `distribution`, `relationship` |
| `hist2d` | "bin the pairs into a grid and count" | « classer les couples dans une grille » | `distribution`, `relationship` |
| `kde2d-contour` | "where the points are densest" | « où les points sont les plus denses » | `distribution`, `relationship` |
| `corr-matrix` | "which columns are correlated" | « quelles colonnes sont corrélées » | `distribution` |
| `pairplot` | "every pair of variables at once" | « chaque paire de variables d'un coup » | `relationship` |
| `parcoords` | "many metrics, one line per record" | « beaucoup de mesures, une ligne par enregistrement » | `relationship` |
| `radar` | "a profile across several axes" | « un profil sur plusieurs axes » | `relationship` |
| `radviz` | "which variable pulls each point" | « quelle variable attire chaque point » | `relationship` |
| `andrews` | "do the clusters separate as curves" | « les groupes se séparent-ils en courbes » | `relationship` |
| `regression-ci-band` | "fit a line with its confidence band" | « ajuster une droite avec sa bande » | `relationship` |
| `residual` | "check the residuals of my regression" | « vérifier les résidus de ma régression » | `relationship`, `model_evaluation` |
| `convex-hull` | "draw a boundary round each cluster" | « tracer une frontière autour de chaque groupe » | none |
| `clustermap` | "reorder the heatmap by similarity" | « réordonner la carte de chaleur par similarité » | `distribution` |


### Where it goes

| Kind | They say | Ils disent | Goal that ranks it first |
|---|---|---|---|
| `sankey` | "the energy balance, from source to use" | « le bilan, de la source à l'usage » | `flow` |
| `alluvial` | "how the groups shift from stage to stage" | « comment les groupes changent d'étape en étape » | `flow` |
| `chord` | "who trades with whom, both ways" | « qui échange avec qui, dans les deux sens » | `flow` |
| `parallel-sets` | "categorical variables, one after another" | « des variables qualitatives, l'une après l'autre » | `flow` |
| `dependency-wheel` | "which module depends on which" | « quel module dépend de quel autre » | `flow` |
| `cycle` | "a process that returns to its start" | « un processus qui revient à son point de départ » | none |


### Nested and parent-child

| Kind | They say | Ils disent | Goal that ranks it first |
|---|---|---|---|
| `tree` | "the structure itself, as a tree" | « la structure elle-même, en arbre » | `hierarchy` |
| `org-chart` | "who reports to whom" | « qui rapporte à qui » | `hierarchy` |
| `radial-tree` | "a deep tree that has to fit a square" | « un arbre profond qui doit tenir dans un carré » | `hierarchy` |
| `dendrogram` | "how the clusters merge" | « comment les groupes fusionnent » | `hierarchy` |
| `icicle` | "the flame graph of this profile" | « le graphe de flamme de ce profil » | `hierarchy` |
| `sunburst` | "nested rings, two or three levels" | « des anneaux emboîtés, deux ou trois niveaux » | `hierarchy` |
| `circle-packing` | "nested circles sized by value" | « des cercles emboîtés dimensionnés par la valeur » | `hierarchy` |


### Who is connected to whom

| Kind | They say | Ils disent | Goal that ranks it first |
|---|---|---|---|
| `network` | "the graph of these relationships" | « le graphe de ces relations » | `flow` |
| `arcdiagram` | "connections along one line of nodes" | « des liens le long d'une ligne de nœuds » | `flow` |
| `edge-bundling` | "a hairball I need to untangle" | « une pelote de liens à démêler » | `flow` |
| `sfdp-largegraph` | "thousands of nodes, laid out" | « des milliers de nœuds, disposés » | `flow` |
| `interruption-matrix` | "who cuts whom off in the meeting" | « qui coupe la parole à qui en réunion » | none |


### On a map

| Kind | They say | Ils disent | Goal that ranks it first |
|---|---|---|---|
| `hexmap` | "point density by region, in hexagons" | « la densité par région, en hexagones » | `geography` |
| `hexbin-map` | "a map where every state is equal in size" | « une carte où chaque région pèse pareil » | `geography` |
| `binned-grid-map` | "aggregate these events into map cells" | « agréger ces événements en cellules » | `geography` |
| `dotdensity` | "one dot per thousand people" | « un point pour mille habitants » | `geography` |
| `spike-map` | "a value per place, as spikes" | « une valeur par lieu, en pics » | `geography` |
| `voronoi` | "the catchment area of each site" | « la zone de chalandise de chaque site » | `geography` |

### A glyph on each place

| Kind | They say | Ils disent | Goal that ranks it first |
|---|---|---|---|
| `map-bars` | "several numbers per region, compared on the map" | « plusieurs chiffres par région, comparés sur la carte » | `geography` |
| `map-bubble` | "a total per place, as circles sized by area" | « un total par lieu, en cercles proportionnels à la surface » | `geography` |
| `map-flow` | "who moves from where to where, on a map" | « qui va d'où à où, sur une carte » | `geography` |
| `map-pie` | "the mix in each region, on the map" | « la répartition de chaque région, sur la carte » | `geography` |
| `map-tilegrid` | "a rate per country, every country the same size" | « un taux par pays, chaque pays de la même taille » | `geography` |


### Is my model any good

| Kind | They say | Ils disent | Goal that ranks it first |
|---|---|---|---|
| `roc-curve` | "the ROC curve, the AUC" | « la courbe ROC, l'aire sous la courbe » | `model_evaluation` |
| `prcurve` | "precision and recall, classes are imbalanced" | « précision et rappel, classes déséquilibrées » | `model_evaluation` |
| `confusion-matrix` | "the confusion matrix" | « la matrice de confusion » | `model_evaluation` |
| `calibration` | "are my probabilities honest" | « mes probabilités sont-elles honnêtes » | `model_evaluation` |
| `liftgain` | "how much better than random" | « combien mieux que le hasard » | `model_evaluation` |
| `learning-curve` | "would more data help" | « est-ce que plus de données aiderait » | `model_evaluation` |
| `validation-curve` | "which value of this hyper-parameter" | « quelle valeur pour cet hyperparamètre » | `model_evaluation` |
| `loss-curve` | "training and validation loss per epoch" | « la perte par époque, apprentissage et validation » | `model_evaluation` |
| `ablation_matrix` | "which component is actually earning its keep" | « quel composant sert vraiment à quelque chose » | `model_evaluation` |
| `gaussian-process` | "fit a posterior to a handful of points" | « ajuster une loi a posteriori à quelques points » | `model_evaluation` |
| `silhouette` | "is my clustering any good" | « mon partitionnement vaut-il quelque chose » | `model_evaluation` |
| `elbow` | "how many clusters should I take" | « combien de groupes faut-il prendre » | none |


### Why did the model say that

| Kind | They say | Ils disent | Goal that ranks it first |
|---|---|---|---|
| `permutation-importance` | "which features matter" | « quelles variables comptent » | none |
| `shap-waterfall` | "why this one prediction" | « pourquoi cette prédiction-là » | none |
| `shap-beeswarm` | "which features move the output, and which way" | « quelles variables poussent la sortie, dans quel sens » | none |
| `pdp-ice` | "what happens as I sweep this feature" | « que se passe-t-il quand je balaie cette variable » | none |
| `causal-dag` | "what must I adjust for to get the effect" | « sur quoi ajuster pour avoir l'effet » | none |


### High dimensions, laid flat

| Kind | They say | Ils disent | Goal that ranks it first |
|---|---|---|---|
| `embedding_projector` | "plot my embeddings, coloured by label" | « projeter mes plongements, par étiquette » | `relationship` |
| `diffusion_trajectory` | "show the noise schedule, forward and back" | « montrer le calendrier de bruit, aller-retour » | `relationship` |
| `manifold_path` | "the path gradient descent actually took" | « le chemin réellement suivi par la descente » | none |


### Markets

| Kind | They say | Ils disent | Goal that ranks it first |
|---|---|---|---|
| `candlestick` | "the candles for this ticker" | « les chandeliers de ce titre » | none |
| `ohlc` | "open-high-low-close, print-safe" | « ouverture-haut-bas-clôture, pour l'impression » | none |
| `bollinger` | "the price with its volatility bands" | « le cours avec ses bandes de volatilité » | none |


### Signals and fields

| Kind | They say | Ils disent | Goal that ranks it first |
|---|---|---|---|
| `spectrogram` | "the frequency content over time" | « le contenu fréquentiel au fil du temps » | none |
| `stem` | "discrete samples, counts, taps" | « des échantillons discrets, des comptes » | none |
| `eventplot` | "a raster of when things happened" | « un raster de quand les choses sont arrivées » | none |
| `quiver` | "the wind field, as arrows" | « le champ de vent, en flèches » | none |
| `quiver3d` | "a vector field in three dimensions" | « un champ de vecteurs en trois dimensions » | none |
| `streamplot` | "the flow lines of this field" | « les lignes de courant de ce champ » | none |
| `contour` | "iso-lines over a field on a grid" | « des iso-lignes sur un champ en grille » | none |
| `tricontour` | "iso-lines over scattered sensors" | « des iso-lignes sur des capteurs épars » | none |
| `heatmap` | "a matrix, coloured by value" | « une matrice, teintée par la valeur » | none |
| `imshow-interpolated` | "the same, smoothed into a field" | « pareil, lissé en un champ » | none |
| `windbarb` | "wind barbs, the way a forecaster reads them" | « des barbules de vent, comme en météo » | `geography` |
| `windrose` | "the wind rose for this station" | « la rose des vents de cette station » | `geography` |
| `polar` | "hours of the day, round the clock" | « les heures du jour, tout autour du cadran » | none |
| `rose` | "a Nightingale rose by direction" | « une rose de Nightingale par direction » | none |


### Three dimensions

| Kind | They say | Ils disent | Goal that ranks it first |
|---|---|---|---|
| `scatter3d` | "three continuous variables, in space" | « trois variables continues, dans l'espace » | none |
| `surface3d` | "the surface z = f(x, y)" | « la surface z = f(x, y) » | none |
| `wireframe3d` | "the same surface, as a wireframe" | « la même surface, en fil de fer » | none |
| `trisurface` | "a surface over points measured anywhere" | « une surface sur des points mesurés n'importe où » | none |
| `voxels` | "the cells of a three-way grid, filled" | « les cellules d'une grille à trois axes, pleines » | none |
| `line3d` | "a trajectory through three dimensions" | « une trajectoire en trois dimensions » | none |


### Science and statistics

| Kind | They say | Ils disent | Goal that ranks it first |
|---|---|---|---|
| `manhattan` | "the GWAS plot, by genomic position" | « le graphique GWAS, par position génomique » | none |
| `volcano` | "fold change against significance" | « l'amplitude contre la significativité » | none |
| `survival-km` | "the Kaplan-Meier curve" | « la courbe de Kaplan-Meier » | none |
| `forest` | "the forest plot for this meta-analysis" | « le graphique en forêt de cette méta-analyse » | `model_evaluation` |


### One number, and the furniture

| Kind | They say | Ils disent | Goal that ranks it first |
|---|---|---|---|
| `bullet` | "this KPI against its target" | « cet indicateur face à sa cible » | none |
| `gauge` | "a dial for the dashboard" | « un cadran pour le tableau de bord » | none |
| `liquid-gauge` | "a percentage, for a consumer screen" | « un pourcentage, pour un écran grand public » | none |
| `progress` | "how far along each goal is" | « où en est chaque objectif » | none |
| `fishbone` | "why does this keep going wrong" | « pourquoi ça se reproduit » | none |
| `missing-matrix` | "where are the holes in this dataset" | « où sont les trous dans ce jeu de données » | none |
| `venn` | "two or three overlapping sets" | « deux ou trois ensembles qui se recoupent » | none |
| `upset` | "more sets than a Venn can hold" | « plus d'ensembles qu'un Venn n'en tient » | none |
| `wordcloud` | "the words that come up most" | « les mots qui reviennent le plus » | none |
| `speaking_time` | "who spoke for how long" | « qui a parlé combien de temps » | none |
| `facet` | "the same chart, once per group" | « le même graphique, un par groupe » | none |
| `gapminder` | "income against life expectancy, animated" | « revenu contre espérance de vie, animé » | none |
| `gapminder_variants` | "the same, for one region" | « le même, pour une seule région » | none |


### When two of them look the same

The catalogue keeps near-neighbours apart on purpose, and the difference is
always *what the reader can do with the result*. The pairs worth knowing:

| Pair | Reach for the first when… | …and the second when |
|---|---|---|
| `pie` / `donut` | the slices are the whole story | a total belongs in the middle |
| `funnel` / `funnel-area` | the numbers are the point | the taper is, as a shape |
| `candlestick` / `ohlc` | the chart is screen-first | it has to survive print, or red-green blindness |
| `beeswarm` / `strip` | every point is a case to find | there are thousands, and the shape is the question |
| `tree` / `radial-tree` | the tree is shallow, read top-down | it is deep, or wide, and has to fit a square |
| `tree` / `dendrogram` | the structure is given | the structure is a *result*, with merge heights |
| `contour` / `tricontour` | the field sits on a grid | the samples sit wherever they could be measured |
| `surface3d` / `trisurface` | z is a function of a grid | the points are scattered, the mesh is evidence |
| `venn` / `upset` | two or three sets | four or more |
| `boxplot` / `boxen` | the tail is short | the tail is long and worth keeping |
| `heatmap` / `imshow-interpolated` | the cells are the unit | the matrix samples something continuous |
| `bullet` / `gauge` | the page is text-heavy | the page is a dashboard |
| `treemap` / `circle-packing` | area must be comparable | the nesting is the point |

The full note on each pair lives in `tests/test_no_near_duplicates.py`, where
it is enforced: a new figure that collides with an old one has to earn its
entry by saying how it differs.

---

## Typical call pattern

```python
from sprezzature_figures import make_figure

path = make_figure(kind, data, out="output.png", title="My chart")
```

All 167 kinds and the `data` shape each expects are in [FIGURES.md](FIGURES.md).
