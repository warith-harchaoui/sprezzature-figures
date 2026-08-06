# Figure Catalogue

100 chart types, each mapping to a `make_<kind>.py` script under `scripts/`, plus the internal `figure` dispatcher row documented below (not itself a chart type).

Invoke via:

```python
from sprezzature_figures import make_figure
path = make_figure("bar", data, out="output.png")
```

or via CLI:

```bash
make-figure bar --out output.png --title "Revenue by region"
```

Only `status="stable"` kinds are render-verified end to end today; run
`make-figure --list --status stable` or see `docs/studio/GENERATOR_AUDIT.md`
for the current per-chart status.

## Full Catalogue

| Kind | Script | Category | When to use |
|------|--------|----------|-------------|
| `alluvial` | make_alluvial.py | Flow | Trace how categorical populations shift across multiple sequential stages (e.g., patient treatment paths, hiring funnel). Use over sankey when stages are time-ordered and each row belongs to exactly one bin per stage. |
| `andrews` | make_andrews.py | Multivariate | Project multivariate observations as Fourier curves. Clusters of similar rows become visually coincident curves; use for detecting clusters or outliers in high-dimensional data before running PCA. |
| `arcdiagram` | make_arcdiagram.py | Network | Show pairwise connections along a linear node axis. Ideal for sequences where crossing arcs reveal unexpected long-range dependencies (e.g., citation links, gene co-expression). |
| `area` | make_area.py | Composition | Stacked area chart showing how a whole made of several categories evolves over an ordered axis. Use for traffic by channel, cumulative headcount, or resource usage over time. |
| `bar` | make_bar.py | Comparison | Grouped bar chart comparing a numeric value across a handful of categories. The default chart for straightforward category comparisons (revenue by region, headcount by department). |
| `bar-grouped` | make_bar-grouped.py | Comparison | Clustered bars: an outer categorical axis (e.g. quarter) holds a group of side-by-side bars, one per inner category (e.g. region), colour-coded. Use to compare sub-category totals within a period and each sub-category's trend across periods at once. |
| `bar3d` | make_bar3d.py | Comparison | 3-D bar chart for a 2-D categorical grid (row × column → height). Use only when a third dimension adds genuine information; prefer grouped or stacked bar for most comparisons. |
| `beeswarm` | make_beeswarm.py | Distribution | One dot per observation along a shared numeric axis, nudged apart just enough to avoid overlap so the swarm's width is itself a density cue; colour groups several overlapping distributions on one axis. Use where a histogram would hide individual outliers and a box plot would hide shape. |
| `bellcurve` | make_bellcurve.py | Distribution | Overlay a fitted Normal curve on a histogram. Use to test whether a sample is approximately Gaussian or to annotate mean ± σ reference lines for a report audience. |
| `binned-grid-map` | make_binned-grid-map.py | Geospatial | Aggregate point events into equal-area hexagonal or square grid cells on a map. Use when raw point density is too high to read (e.g., taxi pickups, earthquake epicentres). |
| `blandaltman` | make_blandaltman.py | Agreement | Plot mean of two measurements vs. their difference (Bland-Altman / Tukey mean-difference). Required for method-comparison studies in clinical or engineering contexts. |
| `bollinger` | make_bollinger.py | Finance | Time-series price line with Bollinger Bands (rolling mean ± 2σ). Use to visualise volatility regimes and overbought/oversold signals in financial or sensor data. |
| `boxen` | make_boxen.py | Distribution | Letter-value / "boxen" plot: extends the box plot with additional quantile boxes. Use for large samples (n > 10 000) where a standard box plot hides distributional detail. |
| `boxplot` | make_boxplot.py | Distribution | Box plot summarising median, quartiles, and outliers per category (Tukey 1.5×IQR rule). Use for salary by department, response time by service, scores by class. |
| `bubble` | make_bubble.py | Comparison | Gapminder-style bubble chart: x and y for two measures, bubble area for a third, colour for a category. Use to compare many entities across three numeric dimensions plus a group at once. |
| `bullet` | make_bullet.py | KPI | Bullet chart: a single bar against a reference measure and qualitative performance bands. The compact alternative to a gauge for dashboards with many KPIs. |
| `calendar-heatmap` | make_calendar-heatmap.py | Time series | GitHub-style week x day grid, cell colour is a daily count on a single pale-to-navy blue ramp. Use for commit activity, daily active users, or habit tracking viewed over months at a glance. |
| `calibration` | make_calibration.py | Model evaluation | Plot predicted probability vs. observed frequency. Use after training a classifier to check whether its scores are well-calibrated (reliable confidence estimates). |
| `chord` | make_chord.py | Flow | Circular chord diagram for symmetric or directed flows between categories. Use when every pair of categories can exchange and the total volume matters (e.g., migration between countries). |
| `circle-packing` | make_circle-packing.py | Hierarchy | Represent a hierarchy as nested circles whose area encodes a numeric value. Use for a single level of nesting where the visual impact of size differences matters more than precise reading. |
| `columnrange` | make_columnrange.py | Range | Vertical bars spanning from a low to a high value per category. Use for temperature ranges, salary bands, confidence intervals, or any per-group min–max. |
| `confusion-matrix` | make_confusion-matrix.py | Model evaluation | Confusion matrix: actual class (rows) vs predicted class (columns), both axes labelled with the class names, cells shaded by count with a strong correct diagonal. Use to see exactly which classes a classifier confuses. |
| `connected-scatter` | make_connected-scatter.py | Bivariate time series | Scatter plot where consecutive time points are connected by lines. Use to reveal the joint trajectory of two variables over time (e.g., GDP vs. life expectancy). |
| `convex-hull` | make_convex-hull.py | Clustering | Scatter plot with convex-hull polygons drawn around labelled clusters. Use to visually delimit group boundaries after clustering or classification. |
| `cycle` | make_cycle.py | Cyclic | Directed ring of proportional arcs for a process that returns to its start (a crop rotation, the seasons, a product lifecycle, a sprint). Each arc's length is that phase's share of one full turn, wrapped by a flow arrow. Use over a pie when order and recurrence matter. |
| `dendrogram` | make_dendrogram.py | Hierarchy / Clustering | Hierarchical clustering tree showing how items merge. Use alongside a heatmap for gene expression or customer segmentation; standalone for phylogenetics. |
| `dependency-wheel` | make_dependency-wheel.py | Network | Circular chord variant emphasising directed dependencies between software modules, packages, or systems. Highlights which components are most depended-upon. |
| `difference-chart` | make_difference-chart.py | Comparison | Two area or line series with the gap between them shaded. Use to emphasise the magnitude and sign of the difference between two time series. |
| `donut` | make_donut.py | Composition | Pie chart with an open centre; each category's share of a whole is an arc's angular span, ordered largest to smallest, with a percentage label per wedge. Use for a small (2-6 category) part-of-whole breakdown: traffic by channel, budget by category, votes by candidate. |
| `dotdensity` | make_dotdensity.py | Geospatial | Each dot represents a fixed count of a quantity on a map. Use to show spatial distribution and relative magnitude without imposing arbitrary choropleth boundaries. |
| `dotplot` | make_dotplot.py | Distribution | Wilkinson dot plot: one dot per observation, binned and stacked so the sample size stays countable while the silhouette shows the distribution's shape. Use for small-to-medium samples where a histogram's bars would hide individual points. |
| `dumbbell` | make_dumbbell.py | Change | Two dots connected by a line per category (before vs. after). Use for clear before–after or group-A vs. group-B comparison across many categories. |
| `edge-bundling` | make_edge-bundling.py | Network | Hierarchical edge-bundling groups edges along their shared ancestry, reducing visual clutter in large graphs. Use for software dependency or call-graph visualisation. |
| `elbow` | make_elbow.py | Model selection | Detect the elbow (knee) of a diminishing-returns curve with the Kneedle method: pick k for k-means, the number of PCA components, or `eps` for DBSCAN. An inset draws the normalised difference curve whose peak locates the elbow. |
| `embedding_projector` | make_embedding_projector.py | Dimensionality reduction | 2-D or 3-D scatter of high-dimensional embeddings coloured by label. Use to inspect whether a learned embedding separates classes or clusters semantically. |
| `figure` | make_figure.py | — | Internal dispatcher; do not invoke directly. |
| `forest` | make_forest.py | Meta-analysis | Forest plot: effect size with confidence interval per study, plus a pooled diamond. Standard in systematic reviews and meta-analyses. |
| `funnel` | make_funnel.py | Pipeline | Horizontal bars narrowing to show drop-off across sequential stages (conversion funnel, hiring, clinical trial enrolment). Percentage labels on each stage. |
| `gapminder` | make_gapminder.py | Animated bubble | Animated scatter: x = income, y = life expectancy, size = population, colour = region. Use to show development trends across countries over decades. |
| `gapminder_variants` | make_gapminder_variants.py | Animated bubble | Regional or subset variants of the Gapminder chart. |
| `gauge` | make_gauge.py | KPI | Semicircular gauge dial. Use for a single KPI read at a glance; prefer bullet charts in text-heavy reports. |
| `heatmap` | make_heatmap.py | Matrix / Image | Row × column matrix with cell color encoding a numeric value. Use for activity by day-of-week × hour, correlation matrices, or cohort × variant test results. |
| `hexbin-map` | make_hexbin-map.py | Geospatial | US (or world) map where equal-area hexagons replace geographic regions. Eliminates size-biased area distortion from choropleth maps. |
| `hexmap` | make_hexmap.py | Geospatial | Generic hexagonal binning map. Use for local or regional point density where standard hexbin-map doesn't fit. |
| `histogram` | make_histogram.py | Distribution | Bins a single numeric variable and counts observations per bin. The default chart for understanding a distribution's shape, spread, and skew. |
| `horizon` | make_horizon.py | Time series | Horizon chart: fold a time series at regular intervals and overlay bands. Enables many series in compact vertical space (e.g., server metrics, sensor arrays). |
| `icicle` | make_icicle.py | Hierarchy | Top-down rectangular treemap (icicle / flame chart). Use to show execution profiles, file-system trees, or budget breakdowns where reading order matters. |
| `imshow-interpolated` | make_imshow-interpolated.py | Matrix / Image | Display a 2-D matrix as a heatmap with smooth interpolation. Use for spatial fields (temperature grids, image patches) rather than discrete data. |
| `interruption-matrix` | make_interruption-matrix.py | Communication | Directed "who cuts whom" heatmap: rows are speakers being cut off, columns the interrupters, each cell the number of interruptions, tinted by the interrupter. Row/column totals and a crosshair hover make conversational dominance readable at a glance -- who interrupts most (dark column), who gets cut most (dark row). |
| `jointplot` | make_jointplot.py | Bivariate distribution | Central scatter or hexbin with marginal histograms or KDE on each axis. Use to show bivariate distribution and its univariate projections simultaneously. |
| `liftgain` | make_liftgain.py | Model evaluation | Lift and gain curves for binary classifiers. Use to evaluate how much better than random a model performs when targeting the top N% of a population. |
| `line` | make_line.py | Time series | Multi-series line chart with points, the default for showing how a numeric value evolves over an ordered axis. Use for monthly revenue by product line, daily active users, sensor readings. |
| `liquid-gauge` | make_liquid-gauge.py | KPI | Animated liquid fill gauge (wave inside a circle). Use for a single percentage KPI in consumer-facing dashboards where animation adds appeal. |
| `manhattan` | make_manhattan.py | Genomics / Statistics | Manhattan plot: −log₁₀(p-value) vs. genomic position. The standard chart for genome-wide association study (GWAS) results. |
| `mosaic` | make_mosaic.py | Categorical | Mosaic (Marimekko) plot: tile area encodes joint frequency of two categorical variables. Use to show contingency tables and test independence visually. |
| `network` | make_network.py | Network | Force-directed network graph. Use to show relationships in social, citation, or infrastructure networks when node count is < 500. |
| `org-chart` | make_org-chart.py | Hierarchy | Top-down organisation chart. Use for reporting structures, software architecture layers, or any strict parent–child hierarchy. |
| `packed-bubble` | make_packed-bubble.py | Comparison | Circles packed together, sized by value. Use as a visually engaging alternative to a pie chart when comparing parts of a whole across many categories. |
| `pairplot` | make_pairplot.py | Multivariate | Matrix of scatter plots (or KDE on the diagonal) for every pair of numeric variables. Standard EDA chart for tabular datasets up to ~10 columns. |
| `parallel-sets` | make_parallel-sets.py | Categorical flow | Parallel sets / parallel coordinates for categorical variables. Use to show co-occurrence and flow across multiple categorical dimensions simultaneously. |
| `parcoords` | make_parcoords.py | Relationship | Parallel coordinates: one vertical axis per numeric metric (with units), each record a polyline crossing them all. Use to see how a few groups separate across several measures at once. |
| `pareto` | make_pareto.py | Quality / Ranking | Bar chart sorted descending with a cumulative-percentage line. Use to identify the "vital few" factors that account for the majority of an effect (80/20 rule). |
| `parliament` | make_parliament.py | Political / Composition | Semicircular seat chart for legislative bodies. Use to show seat distribution in elections or any grouped proportional allocation. |
| `pictorial` | make_pictorial.py | Infographic | Bar or unit chart where bars are replaced by repeating icons. Use for general audiences where engagement matters more than precision. |
| `polar` | make_polar.py | Cyclic | Polar bar chart for cyclic or directional data (hours of the day, compass bearings, seasonal patterns). |
| `ppplot` | make_ppplot.py | Goodness of fit | Probability-probability plot: theoretical vs. empirical CDF. Use alongside Q-Q plot to diagnose distributional fit in the body (not tails) of a distribution. |
| `prcurve` | make_prcurve.py | Model evaluation | Precision-Recall curve for binary classifiers. Preferred over ROC when classes are imbalanced, because it focuses on the minority (positive) class performance. |
| `radar` | make_radar.py | Multivariate | Radar / spider chart: multiple quantitative axes radiating from a common centre. Use for comparing a small number of entities across 4–8 dimensions. |
| `radial-bar` | make_radial-bar.py | Comparison | Bar chart bent into a circle. Use when aesthetic impact matters and absolute length comparison is secondary. |
| `radial-tree` | make_radial-tree.py | Hierarchy | Dendrogram laid out radially rather than top-down. Fits deeper or wider trees into a square canvas. |
| `radviz` | make_radviz.py | Multivariate | RadViz: data points attracted to anchors around a circle, each anchor a variable. Use for visual cluster detection in multivariate data. |
| `residual` | make_residual.py | Regression diagnostics | Residuals vs. fitted values (or index). Required in any regression reporting to check homoscedasticity and detect patterns in errors. |
| `ridgeline` | make_ridgeline.py | Distribution | Stacked KDE curves, offset on the y-axis. Use to compare distributions of many groups compactly (e.g., scores across regions, latency across time slices). |
| `rose` | make_rose.py | Cyclic | Polar area chart (Nightingale rose). Use to show magnitude in directional or seasonal data where the angle encodes a cyclic category. |
| `rug` | make_rug.py | Distribution | 1-D tick marks along an axis showing individual data points. Use as a supplement to a KDE or histogram to expose sample size and individual-point positions. |
| `sankey` | make_sankey.py | Flow | Sankey diagram: flows between nodes with width proportional to volume. Use for energy balance, budget allocation, or any source → sink flow across categories. |
| `scatter` | make_scatter.py | Relationship | Plots two numeric variables against each other, with optional color and size encodings. The default chart for revealing correlation, clusters, or outliers. |
| `scatter3d` | make_scatter3d.py | 3-D | Interactive 3-D scatter plot for three continuous variables. Use when a 2-D projection loses important structure (e.g., embedding manifolds). |
| `sfdp-largegraph` | make_sfdp-largegraph.py | Network | Scalable Force-Directed Placement for large graphs (thousands of nodes). Use when standard force-directed layouts become too slow or cluttered. |
| `situation_map` | make_situation_map.py | Geospatial | Annotated situation map with icons and labels at specific coordinates. Use for field operations, logistics, or incident mapping. |
| `speaking_time` | make_speaking_time.py | Communication | Speaking-time breakdown chart (waterfall or stacked bar). Use to visualise turn-taking or time allocation in meetings, debates, or interviews. |
| `spectrogram` | make_spectrogram.py | Signal | Frequency × time heatmap of a signal's energy. Use for audio, seismic, or any time-varying spectral data. |
| `spike-map` | make_spike-map.py | Geospatial | Vertical spikes on a map proportional to a value at each location. Cleaner than a dot map for comparing magnitudes; less distorting than a choropleth. |
| `streamgraph` | make_streamgraph.py | Time series / Composition | Stacked area chart with a central baseline, flowing like a stream. Use for showing how categorical composition evolves over time when the baseline is less important than the flow. |
| `streamplot` | make_streamplot.py | Vector field | Stream lines showing a 2-D vector field (wind, fluid flow, electromagnetic). Use to visualise flow direction and speed across a continuous domain. |
| `sunburst` | make_sunburst.py | Hierarchy | Radial treemap: nested rings for hierarchical data. Use when two or three levels of hierarchy need to be read simultaneously (e.g., budget by department → team → line item). |
| `surface3d` | make_surface3d.py | 3-D surface | Static isometric 3-D surface for z = f(x, y): depth-sorted mesh quads shaded by height with a height legend. Hand-authored SVG (no matplotlib). |
| `ternary` | make_ternary.py | Compositional | Ternary (triangular) plot for three components that sum to a constant. Use in chemistry, geology, or any three-part compositional analysis. |
| `timeline` | make_timeline.py | Temporal | Gantt-style horizontal timeline of events or phases. Use for project schedules, historical chronologies, or clinical trial phases. |
| `tree` | make_tree.py | Hierarchy | Top-down or left-right tree diagram for strict hierarchies. Simpler than a dendrogram when the tree structure itself (not distances) is the message. |
| `treemap` | make_treemap.py | Hierarchy / Composition | Nested rectangles where area encodes a numeric value. Use for part-of-whole data with a two-level hierarchy (e.g., market capitalisation by sector → company). |
| `upset` | make_upset.py | Set intersection | UpSet plot: matrix of set membership with bar charts for intersection sizes. Replaces Venn diagrams when more than three sets are compared. |
| `variwide` | make_variwide.py | Comparison | Column chart where column width encodes a second variable (e.g., bar height = GDP per capita, width = population). Use to pack two dimensions into a single bar-chart read. |
| `venn` | make_venn.py | Set intersection | Venn diagram for two or three overlapping sets. Use only for two or three sets; switch to UpSet for more. |
| `voronoi` | make_voronoi.py | Geospatial / Spatial | Voronoi tessellation: colour each region by the nearest point. Use to show catchment areas, service regions, or proximity-based assignments. |
| `waffle` | make_waffle.py | Composition | Square grid of unit cells coloured by category. Use as an engaging, precise alternative to a pie chart for part-of-whole comparisons (each cell = 1 % or N units). |
| `waterfall` | make_waterfall.py | Accounting / Decomposition | Running-total bar chart where positive and negative contributions are shown in sequence. Use for financial P&L bridges, budget variance, or cumulative effect analysis. |
| `windbarb` | make_windbarb.py | Meteorology | Meteorological wind barbs showing direction and speed with feather notation. Standard in weather and oceanographic reporting. |
| `windrose` | make_windrose.py | Meteorology / Cyclic | Polar histogram of wind frequency and speed by direction. Use to summarise directional data (wind, ocean current, traffic) over a period. |
| `wireframe3d` | make_wireframe3d.py | 3-D surface | 3-D wireframe surface plot for z = f(x, y). Use to visualise mathematical functions, terrain, or response surfaces from two-factor experiments. |
| `wordcloud` | make_wordcloud.py | Text | Word cloud where font size encodes term frequency or TF-IDF weight. Use for exploratory text analysis or communication; avoid when precise comparison is needed. |

---

*This file is auto-maintained. To add a chart type: add a `make_<kind>.py` script to `scripts/`, add its DEMO_DATA, and append a row to this table.*
