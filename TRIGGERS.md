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

## Do not try to memorise 167 chart names

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
well past the nine. Match the user's own noun against
[the full trigger table below](#every-kind-and-the-sentence-that-reaches-it),
which lists every one of the 167 kinds with the phrase that reaches it, in
English and in French. `get_kind` then says what the rows must carry.

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

## Every kind, and the sentence that reaches it

Route on the nine goals first: they answer the ordinary request without
anyone naming a chart. This table is for the rest — when a user reaches for
a domain noun ("the ROC curve", « la rose des vents », "a Gantt"), when the
recommender's top candidate looks wrong, or when you want to know what else
was on the shelf.

Read it as *triggers*, not as definitions: the phrase is what someone says,
the kind is what to call. [FIGURES.md](FIGURES.md) says what each one draws
and what its rows must carry; `get_kind` says it at run time.


### Compare and rank — goal `comparison`

| Kind | They say | Ils disent |
|---|---|---|
| `bar` | "compare these categories, which is biggest" | « comparer ces catégories, lequel est le plus gros » |
| `bar-grouped` | "by quarter and by product, side by side" | « par trimestre et par produit, côte à côte » |
| `lollipop` | "a ranked bar chart that is not so heavy" | « un classement en barres, mais plus léger » |
| `dumbbell` | "before and after, per category" | « avant / après, par catégorie » |
| `slope` | "who moved between these two dates" | « qui a bougé entre ces deux dates » |
| `bump` | "who overtook whom in the rankings" | « qui a doublé qui au classement » |
| `dual-axis` | "revenue and conversion rate on one chart" | « le chiffre d'affaires et le taux sur un même graphique » |
| `difference-chart` | "how far apart these two series are" | « l'écart entre ces deux séries » |
| `variwide` | "big bars for big markets, wide for volume" | « des barres hautes par valeur, larges par volume » |
| `packed-bubble` | "a prettier pie, many categories" | « un camembert plus joli, beaucoup de catégories » |
| `radial-bar` | "bars bent into a circle, for the slide" | « des barres en cercle, pour la présentation » |
| `bubble` | "three measures at once, by country" | « trois mesures d'un coup, par pays » |
| `pareto` | "which few causes make most of the trouble" | « quelles rares causes font l'essentiel des ennuis » |
| `columnrange` | "the min and max per category" | « le mini et le maxi par catégorie » |
| `bar3d` | "a grid of categories with a height each" | « une grille de catégories avec une hauteur chacune » |
| `table` | "just give me the numbers in a table" | « donne-moi simplement les chiffres dans un tableau » |


### Over time — goal `trend`

| Kind | They say | Ils disent |
|---|---|---|
| `line` | "how has this changed since January" | « l'évolution depuis janvier » |
| `line-multi` | "several series over the hours of the day" | « plusieurs séries au fil des heures » |
| `step` | "the price held, then jumped" | « le tarif a tenu, puis a sauté » |
| `area` | "the total over time, split by category" | « le total dans le temps, par catégorie » |
| `stacked-area` | "the same, on a numeric time axis" | « pareil, sur un axe de temps numérique » |
| `streamgraph` | "how the mix flowed over the years" | « comment le mélange a coulé au fil des ans » |
| `sparkline` | "twenty metrics on one page, no axes" | « vingt indicateurs sur une page, sans axes » |
| `horizon` | "forty series stacked in little space" | « quarante séries empilées en peu de place » |
| `calendar-heatmap` | "activity per day, GitHub style" | « l'activité jour par jour, façon GitHub » |
| `timeline` | "the phases of the project, end to end" | « les phases du projet, de bout en bout » |
| `gantt` | "the schedule with owners and overlaps" | « le planning avec les responsables » |
| `connected-scatter` | "how the two moved together over time" | « comment les deux ont bougé ensemble » |
| `seasonal-decomposition` | "split it into trend and season" | « séparer la tendance de la saison » |
| `forecast-fan` | "the forecast with its uncertainty" | « la prévision avec son incertitude » |
| `acf` | "is there autocorrelation, at which lag" | « y a-t-il autocorrélation, à quel décalage » |
| `control-chart` | "is this process in control" | « ce procédé est-il sous contrôle » |
| `cohort-retention` | "how many come back, by signup month" | « combien reviennent, par mois d'inscription » |


### Spread and shape — goal `distribution`

| Kind | They say | Ils disent |
|---|---|---|
| `histogram` | "how is this spread out" | « comment c'est réparti » |
| `kde1d` | "a smooth density rather than bins" | « une densité lisse plutôt que des classes » |
| `bellcurve` | "is my sample roughly normal" | « mon échantillon est-il à peu près normal » |
| `boxplot` | "median, quartiles, outliers per group" | « médiane, quartiles, valeurs aberrantes » |
| `boxen` | "a box plot that keeps the far tail" | « une boîte qui garde la queue lointaine » |
| `violin` | "the shape of each group's distribution" | « la forme de chaque distribution » |
| `beeswarm` | "every point, none hidden behind another" | « chaque point, aucun caché derrière un autre » |
| `strip` | "all the points, jittered, thousands of them" | « tous les points, dispersés, par milliers » |
| `dotplot` | "small sample, I want to count the dots" | « petit échantillon, je veux compter les points » |
| `ridgeline` | "many groups' densities, stacked" | « les densités de beaucoup de groupes, empilées » |
| `ecdf` | "what share falls below this value" | « quelle part est sous cette valeur » |
| `rug` | "mark the individual observations on the axis" | « marquer les observations sur l'axe » |
| `errorbar` | "the estimate with its confidence interval" | « l'estimation avec son intervalle de confiance » |
| `pointplot` | "the estimates per group, joined" | « les estimations par groupe, reliées » |
| `population-pyramid` | "men and women by age band" | « hommes et femmes par tranche d'âge » |
| `hexbin` | "a scatter so dense it is a blob" | « un nuage si dense qu'il fait une tache » |
| `qqplot` | "is this normally distributed" | « cette distribution est-elle normale » |
| `ppplot` | "check the fit in the middle, not the tails" | « vérifier l'ajustement au centre » |
| `blandaltman` | "do these two instruments agree" | « ces deux appareils sont-ils d'accord » |


### What it is made of — goal `composition`

| Kind | They say | Ils disent |
|---|---|---|
| `pie` | "the share of each, as a pie" | « la part de chacun, en camembert » |
| `donut` | "a pie with the total in the middle" | « un camembert avec le total au centre » |
| `stacked-bar` | "the mix per group, as percentages" | « le mélange par groupe, en pourcentages » |
| `waffle` | "a hundred squares, so people can count" | « cent carrés, pour qu'on puisse compter » |
| `pictorial` | "icons instead of bars, for the public" | « des icônes au lieu de barres, grand public » |
| `treemap` | "the budget by division then by team" | « le budget par division puis par équipe » |
| `parliament` | "the seats after the election" | « les sièges après l'élection » |
| `mosaic` | "two categorical variables crossed" | « deux variables qualitatives croisées » |
| `ternary` | "three parts that add up to one" | « trois composants dont la somme fait un » |
| `waterfall` | "from last year's figure to this year's" | « du chiffre de l'an dernier à celui de cette année » |
| `funnel` | "the drop-off through the stages" | « la déperdition étape par étape » |
| `funnel-area` | "the same taper, as a shape" | « le même entonnoir, comme une forme » |


### Does X explain Y — goal `relationship`

| Kind | They say | Ils disent |
|---|---|---|
| `scatter` | "is there a link between these two" | « y a-t-il un lien entre ces deux-là » |
| `jointplot` | "the scatter plus each margin" | « le nuage, plus chaque marge » |
| `hist2d` | "bin the pairs into a grid and count" | « classer les couples dans une grille » |
| `kde2d-contour` | "where the points are densest" | « où les points sont les plus denses » |
| `corr-matrix` | "which columns are correlated" | « quelles colonnes sont corrélées » |
| `pairplot` | "every pair of variables at once" | « chaque paire de variables d'un coup » |
| `parcoords` | "many metrics, one line per record" | « beaucoup de mesures, une ligne par enregistrement » |
| `radar` | "a profile across several axes" | « un profil sur plusieurs axes » |
| `radviz` | "which variable pulls each point" | « quelle variable attire chaque point » |
| `andrews` | "do the clusters separate as curves" | « les groupes se séparent-ils en courbes » |
| `regression-ci-band` | "fit a line with its confidence band" | « ajuster une droite avec sa bande » |
| `residual` | "check the residuals of my regression" | « vérifier les résidus de ma régression » |
| `convex-hull` | "draw a boundary round each cluster" | « tracer une frontière autour de chaque groupe » |
| `clustermap` | "reorder the heatmap by similarity" | « réordonner la carte de chaleur par similarité » |


### Where it goes — goal `flow`

| Kind | They say | Ils disent |
|---|---|---|
| `sankey` | "the energy balance, from source to use" | « le bilan, de la source à l'usage » |
| `alluvial` | "how the groups shift from stage to stage" | « comment les groupes changent d'étape en étape » |
| `chord` | "who trades with whom, both ways" | « qui échange avec qui, dans les deux sens » |
| `parallel-sets` | "categorical variables, one after another" | « des variables qualitatives, l'une après l'autre » |
| `dependency-wheel` | "which module depends on which" | « quel module dépend de quel autre » |
| `cycle` | "a process that returns to its start" | « un processus qui revient à son point de départ » |


### Nested and parent-child — goal `hierarchy`

| Kind | They say | Ils disent |
|---|---|---|
| `tree` | "the structure itself, as a tree" | « la structure elle-même, en arbre » |
| `org-chart` | "who reports to whom" | « qui rapporte à qui » |
| `radial-tree` | "a deep tree that has to fit a square" | « un arbre profond qui doit tenir dans un carré » |
| `dendrogram` | "how the clusters merge" | « comment les groupes fusionnent » |
| `icicle` | "the flame graph of this profile" | « le graphe de flamme de ce profil » |
| `sunburst` | "nested rings, two or three levels" | « des anneaux emboîtés, deux ou trois niveaux » |
| `circle-packing` | "nested circles sized by value" | « des cercles emboîtés dimensionnés par la valeur » |


### Who is connected to whom — goal `relationship`

| Kind | They say | Ils disent |
|---|---|---|
| `network` | "the graph of these relationships" | « le graphe de ces relations » |
| `arcdiagram` | "connections along one line of nodes" | « des liens le long d'une ligne de nœuds » |
| `edge-bundling` | "a hairball I need to untangle" | « une pelote de liens à démêler » |
| `sfdp-largegraph` | "thousands of nodes, laid out" | « des milliers de nœuds, disposés » |
| `interruption-matrix` | "who cuts whom off in the meeting" | « qui coupe la parole à qui en réunion » |


### On a map — goal `geography`

| Kind | They say | Ils disent |
|---|---|---|
| `hexmap` | "point density by region, in hexagons" | « la densité par région, en hexagones » |
| `hexbin-map` | "a map where every state is equal in size" | « une carte où chaque région pèse pareil » |
| `binned-grid-map` | "aggregate these events into map cells" | « agréger ces événements en cellules » |
| `dotdensity` | "one dot per thousand people" | « un point pour mille habitants » |
| `spike-map` | "a value per place, as spikes" | « une valeur par lieu, en pics » |
| `voronoi` | "the catchment area of each site" | « la zone de chalandise de chaque site » |


### Is my model any good — goal `model_evaluation`

| Kind | They say | Ils disent |
|---|---|---|
| `roc-curve` | "the ROC curve, the AUC" | « la courbe ROC, l'aire sous la courbe » |
| `prcurve` | "precision and recall, classes are imbalanced" | « précision et rappel, classes déséquilibrées » |
| `confusion-matrix` | "the confusion matrix" | « la matrice de confusion » |
| `calibration` | "are my probabilities honest" | « mes probabilités sont-elles honnêtes » |
| `liftgain` | "how much better than random" | « combien mieux que le hasard » |
| `learning-curve` | "would more data help" | « est-ce que plus de données aiderait » |
| `validation-curve` | "which value of this hyper-parameter" | « quelle valeur pour cet hyperparamètre » |
| `loss-curve` | "training and validation loss per epoch" | « la perte par époque, apprentissage et validation » |
| `ablation_matrix` | "which component is actually earning its keep" | « quel composant sert vraiment à quelque chose » |
| `gaussian-process` | "fit a posterior to a handful of points" | « ajuster une loi a posteriori à quelques points » |
| `silhouette` | "is my clustering any good" | « mon partitionnement vaut-il quelque chose » |
| `elbow` | "how many clusters should I take" | « combien de groupes faut-il prendre » |


### Why did the model say that — goal `model_evaluation`

| Kind | They say | Ils disent |
|---|---|---|
| `permutation-importance` | "which features matter" | « quelles variables comptent » |
| `shap-waterfall` | "why this one prediction" | « pourquoi cette prédiction-là » |
| `shap-beeswarm` | "which features move the output, and which way" | « quelles variables poussent la sortie, dans quel sens » |
| `pdp-ice` | "what happens as I sweep this feature" | « que se passe-t-il quand je balaie cette variable » |
| `causal-dag` | "what must I adjust for to get the effect" | « sur quoi ajuster pour avoir l'effet » |


### High dimensions, laid flat — goal `relationship`

| Kind | They say | Ils disent |
|---|---|---|
| `embedding_projector` | "plot my embeddings, coloured by label" | « projeter mes plongements, par étiquette » |
| `diffusion_trajectory` | "show the noise schedule, forward and back" | « montrer le calendrier de bruit, aller-retour » |
| `manifold_path` | "the path gradient descent actually took" | « le chemin réellement suivi par la descente » |


### Markets — goal `trend`

| Kind | They say | Ils disent |
|---|---|---|
| `candlestick` | "the candles for this ticker" | « les chandeliers de ce titre » |
| `ohlc` | "open-high-low-close, print-safe" | « ouverture-haut-bas-clôture, pour l'impression » |
| `bollinger` | "the price with its volatility bands" | « le cours avec ses bandes de volatilité » |


### Signals and fields — goal *(no goal — name the kind)*

| Kind | They say | Ils disent |
|---|---|---|
| `spectrogram` | "the frequency content over time" | « le contenu fréquentiel au fil du temps » |
| `stem` | "discrete samples, counts, taps" | « des échantillons discrets, des comptes » |
| `eventplot` | "a raster of when things happened" | « un raster de quand les choses sont arrivées » |
| `quiver` | "the wind field, as arrows" | « le champ de vent, en flèches » |
| `quiver3d` | "a vector field in three dimensions" | « un champ de vecteurs en trois dimensions » |
| `streamplot` | "the flow lines of this field" | « les lignes de courant de ce champ » |
| `contour` | "iso-lines over a field on a grid" | « des iso-lignes sur un champ en grille » |
| `tricontour` | "iso-lines over scattered sensors" | « des iso-lignes sur des capteurs épars » |
| `heatmap` | "a matrix, coloured by value" | « une matrice, teintée par la valeur » |
| `imshow-interpolated` | "the same, smoothed into a field" | « pareil, lissé en un champ » |
| `windbarb` | "wind barbs, the way a forecaster reads them" | « des barbules de vent, comme en météo » |
| `windrose` | "the wind rose for this station" | « la rose des vents de cette station » |
| `polar` | "hours of the day, round the clock" | « les heures du jour, tout autour du cadran » |
| `rose` | "a Nightingale rose by direction" | « une rose de Nightingale par direction » |


### Three dimensions — goal *(no goal — name the kind)*

| Kind | They say | Ils disent |
|---|---|---|
| `scatter3d` | "three continuous variables, in space" | « trois variables continues, dans l'espace » |
| `surface3d` | "the surface z = f(x, y)" | « la surface z = f(x, y) » |
| `wireframe3d` | "the same surface, as a wireframe" | « la même surface, en fil de fer » |
| `trisurface` | "a surface over points measured anywhere" | « une surface sur des points mesurés n'importe où » |
| `voxels` | "the cells of a three-way grid, filled" | « les cellules d'une grille à trois axes, pleines » |
| `line3d` | "a trajectory through three dimensions" | « une trajectoire en trois dimensions » |


### Science and statistics — goal *(no goal — name the kind)*

| Kind | They say | Ils disent |
|---|---|---|
| `manhattan` | "the GWAS plot, by genomic position" | « le graphique GWAS, par position génomique » |
| `volcano` | "fold change against significance" | « l'amplitude contre la significativité » |
| `survival-km` | "the Kaplan-Meier curve" | « la courbe de Kaplan-Meier » |
| `forest` | "the forest plot for this meta-analysis" | « le graphique en forêt de cette méta-analyse » |


### One number, and the furniture — goal *(no goal — name the kind)*

| Kind | They say | Ils disent |
|---|---|---|
| `bullet` | "this KPI against its target" | « cet indicateur face à sa cible » |
| `gauge` | "a dial for the dashboard" | « un cadran pour le tableau de bord » |
| `liquid-gauge` | "a percentage, for a consumer screen" | « un pourcentage, pour un écran grand public » |
| `progress` | "how far along each goal is" | « où en est chaque objectif » |
| `fishbone` | "why does this keep going wrong" | « pourquoi ça se reproduit » |
| `missing-matrix` | "where are the holes in this dataset" | « où sont les trous dans ce jeu de données » |
| `venn` | "two or three overlapping sets" | « deux ou trois ensembles qui se recoupent » |
| `upset` | "more sets than a Venn can hold" | « plus d'ensembles qu'un Venn n'en tient » |
| `wordcloud` | "the words that come up most" | « les mots qui reviennent le plus » |
| `speaking_time` | "who spoke for how long" | « qui a parlé combien de temps » |
| `facet` | "the same chart, once per group" | « le même graphique, un par groupe » |
| `gapminder` | "income against life expectancy, animated" | « revenu contre espérance de vie, animé » |
| `gapminder_variants` | "the same, for one region" | « le même, pour une seule région » |


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

## What to call, on every surface

| Job | Library | CLI | MCP tool |
|---|---|---|---|
| List the catalogue | `list_kinds()` | `make-figure --list` | `list_kinds` |
| What columns a kind needs | `get_figure_definition(kind)` | `make-figure <kind> --describe` | `get_kind` |
| What else a kind accepts | `options_for(kind)` | `make-figure <kind> --describe` | `list_kind_options` |
| Which kind fits this data | — | `make-figure recommend --data f.csv` | `recommend_figures` |
| Draw it | `make_figure(kind, rows, out=…)` | `make-figure <kind> --data f.csv` | `render_figure` |
| Set a figure's own options | `make_figure(kind, rows, width=…)` | `make-figure <kind> --width …` | `render_figure` (`options`) |
| Redraw from a picture | `redraw(image, out=…)` | `make-figure redraw img.png` | `redraw_figure` |
| Check a rendered SVG | `check_render(svg)` | `make-figure check fig.svg` | `check_render` |
| Visual QA on a rendered figure | — | `ralph_eyeball_loop.py <file>` | *(not an MCP tool)* |

Every CLI cell works with `sprezzature-figures` too (`render`, `describe`,
`list`, `recommend`, `redraw`, `check`): the Click twin is the same commands
through the same code, behind the `[cli]` extra.

The dashes are honest gaps, not omissions: the eyeball loop needs a browser
and a model and does not belong behind an HTTP request, and `recommend` has
no library alias because its ranking lives in the Studio package rather than
the core.

An option a figure does not accept is refused, not ignored — by the command
lines with the nearest real name, by the API with a 422. Ask
`list_kind_options` (or `--describe`) before guessing one.

---

## Two contracts an agent must not break

**1. `render_figure` takes a catalogue name, not a description.** There is no
`--x/--y/--kind` combinator and no plotting-library backend behind this: all
167 kinds are SVG authored directly. If the user asks for output "in
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

All 167 kinds and the `data` shape each expects are in [FIGURES.md](FIGURES.md).
