# Generator audit

Reproducible audit of every `scripts/make_*.py` generator against the
`make_<kind>(data, *, out, title, ...) -> Path` contract the dispatcher
expects. Regenerate with `python tools/audit_generators.py --render`.

- **stable**: 126
- **experimental**: 0
- **legacy**: 0
- **unavailable**: 0
- **total**: 126

| kind | status | reachable | callable | demo_data | render | errors |
|---|---|---|---|---|---|---|
| `alluvial` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `andrews` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `arcdiagram` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `area` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `bar-grouped` | stable | **no** | yes | yes | passed | make_figure('bar-grouped') cannot resolve to make_bar-grouped.py: hyphen/underscore normalisation looks for a different filename; Default output path falls back to a shared assets/ directory |
| `bar` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `bar3d` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `beeswarm` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `bellcurve` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `binned-grid-map` | stable | **no** | yes | yes | passed | make_figure('binned-grid-map') cannot resolve to make_binned-grid-map.py: hyphen/underscore normalisation looks for a different filename; Default output path falls back to a shared assets/ directory |
| `blandaltman` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `bollinger` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `boxen` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `boxplot` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `bubble` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `bullet` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `calendar-heatmap` | stable | **no** | yes | yes | passed | make_figure('calendar-heatmap') cannot resolve to make_calendar-heatmap.py: hyphen/underscore normalisation looks for a different filename; Default output path falls back to a shared assets/ directory |
| `calibration` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `candlestick` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `chord` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `choropleth` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `circle-packing` | stable | **no** | yes | yes | passed | make_figure('circle-packing') cannot resolve to make_circle-packing.py: hyphen/underscore normalisation looks for a different filename; Default output path falls back to a shared assets/ directory |
| `clustermap` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `columnrange` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `confusion-matrix` | stable | **no** | yes | yes | passed | make_figure('confusion-matrix') cannot resolve to make_confusion-matrix.py: hyphen/underscore normalisation looks for a different filename; Default output path falls back to a shared assets/ directory |
| `connected-scatter` | stable | **no** | yes | yes | passed | make_figure('connected-scatter') cannot resolve to make_connected-scatter.py: hyphen/underscore normalisation looks for a different filename; Default output path falls back to a shared assets/ directory |
| `convex-hull` | stable | **no** | yes | yes | passed | make_figure('convex-hull') cannot resolve to make_convex-hull.py: hyphen/underscore normalisation looks for a different filename; Default output path falls back to a shared assets/ directory |
| `corr-matrix` | stable | **no** | yes | yes | passed | make_figure('corr-matrix') cannot resolve to make_corr-matrix.py: hyphen/underscore normalisation looks for a different filename; Default output path falls back to a shared assets/ directory |
| `cycle` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `dendrogram` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `dependency-wheel` | stable | **no** | yes | yes | passed | make_figure('dependency-wheel') cannot resolve to make_dependency-wheel.py: hyphen/underscore normalisation looks for a different filename; Default output path falls back to a shared assets/ directory |
| `difference-chart` | stable | **no** | yes | yes | passed | make_figure('difference-chart') cannot resolve to make_difference-chart.py: hyphen/underscore normalisation looks for a different filename; Default output path falls back to a shared assets/ directory |
| `donut` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `dotdensity` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `dotplot` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `dumbbell` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `ecdf` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `edge-bundling` | stable | **no** | yes | yes | passed | make_figure('edge-bundling') cannot resolve to make_edge-bundling.py: hyphen/underscore normalisation looks for a different filename; Default output path falls back to a shared assets/ directory |
| `elbow` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `embedding_projector` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `errorbar` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `forest` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `funnel` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `gantt` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `gapminder` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `gapminder_variants` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `gauge` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `gaussian-process` | stable | **no** | yes | yes | passed | make_figure('gaussian-process') cannot resolve to make_gaussian-process.py: hyphen/underscore normalisation looks for a different filename; Default output path falls back to a shared assets/ directory |
| `heatmap` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `hexbin-map` | stable | **no** | yes | yes | passed | make_figure('hexbin-map') cannot resolve to make_hexbin-map.py: hyphen/underscore normalisation looks for a different filename; Default output path falls back to a shared assets/ directory |
| `hexbin` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `hexmap` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `histogram` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `horizon` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `icicle` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `imshow-interpolated` | stable | **no** | yes | yes | passed | make_figure('imshow-interpolated') cannot resolve to make_imshow-interpolated.py: hyphen/underscore normalisation looks for a different filename |
| `interruption-matrix` | stable | **no** | yes | yes | passed | make_figure('interruption-matrix') cannot resolve to make_interruption-matrix.py: hyphen/underscore normalisation looks for a different filename |
| `jointplot` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `kde1d` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `kde2d-contour` | stable | **no** | yes | yes | passed | make_figure('kde2d-contour') cannot resolve to make_kde2d-contour.py: hyphen/underscore normalisation looks for a different filename; Default output path falls back to a shared assets/ directory |
| `liftgain` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `line-multi` | stable | **no** | yes | yes | passed | make_figure('line-multi') cannot resolve to make_line-multi.py: hyphen/underscore normalisation looks for a different filename; Default output path falls back to a shared assets/ directory |
| `line` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `liquid-gauge` | stable | **no** | yes | yes | passed | make_figure('liquid-gauge') cannot resolve to make_liquid-gauge.py: hyphen/underscore normalisation looks for a different filename; Default output path falls back to a shared assets/ directory |
| `lollipop` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `manhattan` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `mosaic` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `network` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `org-chart` | stable | **no** | yes | yes | passed | make_figure('org-chart') cannot resolve to make_org-chart.py: hyphen/underscore normalisation looks for a different filename; Default output path falls back to a shared assets/ directory |
| `packed-bubble` | stable | **no** | yes | yes | passed | make_figure('packed-bubble') cannot resolve to make_packed-bubble.py: hyphen/underscore normalisation looks for a different filename; Default output path falls back to a shared assets/ directory |
| `pairplot` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `parallel-sets` | stable | **no** | yes | yes | passed | make_figure('parallel-sets') cannot resolve to make_parallel-sets.py: hyphen/underscore normalisation looks for a different filename; Default output path falls back to a shared assets/ directory |
| `parcoords` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `pareto` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `parliament` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `pictorial` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `polar` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `population-pyramid` | stable | **no** | yes | yes | passed | make_figure('population-pyramid') cannot resolve to make_population-pyramid.py: hyphen/underscore normalisation looks for a different filename; Default output path falls back to a shared assets/ directory |
| `ppplot` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `prcurve` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `qqplot` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `quiver` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `radar` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `radial-bar` | stable | **no** | yes | yes | passed | make_figure('radial-bar') cannot resolve to make_radial-bar.py: hyphen/underscore normalisation looks for a different filename; Default output path falls back to a shared assets/ directory |
| `radial-tree` | stable | **no** | yes | yes | passed | make_figure('radial-tree') cannot resolve to make_radial-tree.py: hyphen/underscore normalisation looks for a different filename; Default output path falls back to a shared assets/ directory |
| `radviz` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `regression-ci-band` | stable | **no** | yes | yes | passed | make_figure('regression-ci-band') cannot resolve to make_regression-ci-band.py: hyphen/underscore normalisation looks for a different filename; Default output path falls back to a shared assets/ directory |
| `residual` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `ridgeline` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `roc-curve` | stable | **no** | yes | yes | passed | make_figure('roc-curve') cannot resolve to make_roc-curve.py: hyphen/underscore normalisation looks for a different filename; Default output path falls back to a shared assets/ directory |
| `rose` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `rug` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `sankey` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `scatter` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `scatter3d` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `sfdp-largegraph` | stable | **no** | yes | yes | passed | make_figure('sfdp-largegraph') cannot resolve to make_sfdp-largegraph.py: hyphen/underscore normalisation looks for a different filename; Default output path falls back to a shared assets/ directory |
| `situation_map` | stable | yes | yes | yes | passed |  |
| `slope` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `speaking_time` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `spectrogram` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `spike-map` | stable | **no** | yes | yes | passed | make_figure('spike-map') cannot resolve to make_spike-map.py: hyphen/underscore normalisation looks for a different filename; Default output path falls back to a shared assets/ directory |
| `stacked-area` | stable | **no** | yes | yes | passed | make_figure('stacked-area') cannot resolve to make_stacked-area.py: hyphen/underscore normalisation looks for a different filename; Default output path falls back to a shared assets/ directory |
| `stacked-bar` | stable | **no** | yes | yes | passed | make_figure('stacked-bar') cannot resolve to make_stacked-bar.py: hyphen/underscore normalisation looks for a different filename; Default output path falls back to a shared assets/ directory |
| `step` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `streamgraph` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `streamplot` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `strip` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `sunburst` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `surface3d` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `survival-km` | stable | **no** | yes | yes | passed | make_figure('survival-km') cannot resolve to make_survival-km.py: hyphen/underscore normalisation looks for a different filename; Default output path falls back to a shared assets/ directory |
| `ternary` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `timeline` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `tree` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `treemap` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `upset` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `variwide` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `venn` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `violin` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `volcano` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `voronoi` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `waffle` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `waterfall` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `windbarb` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `windrose` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `wireframe3d` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `wordcloud` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
