# Generator audit

Reproducible audit of every `scripts/make_*.py` generator against the
`make_<kind>(data, *, out, title, ...) -> Path` contract the dispatcher
expects. Regenerate with `python tools/audit_generators.py --render`.

- **stable**: 19
- **experimental**: 0
- **legacy**: 80
- **unavailable**: 0
- **total**: 99

| kind | status | reachable | callable | demo_data | render | errors |
|---|---|---|---|---|---|---|
| `alluvial` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_alluvial.py; No callable named 'make_alluvial' in make_alluvial.py |
| `andrews` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_andrews.py; No callable named 'make_andrews' in make_andrews.py |
| `arcdiagram` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_arcdiagram.py; No callable named 'make_arcdiagram' in make_arcdiagram.py |
| `area` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `bar-grouped` | stable | **no** | yes | yes | passed | make_figure('bar-grouped') cannot resolve to make_bar-grouped.py: hyphen/underscore normalisation looks for a different filename; Default output path falls back to a shared assets/ directory |
| `bar` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `bar3d` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_bar3d.py; No callable named 'make_bar3d' in make_bar3d.py |
| `beeswarm` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `bellcurve` | legacy | yes | yes | **no** | not_run | No DEMO_DATA in make_bellcurve.py; Default output path falls back to a shared assets/ directory |
| `binned-grid-map` | legacy | **no** | yes | **no** | not_run | No DEMO_DATA in make_binned-grid-map.py; make_figure('binned-grid-map') cannot resolve to make_binned-grid-map.py: hyphen/underscore normalisation looks for a different filename |
| `blandaltman` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_blandaltman.py; No callable named 'make_blandaltman' in make_blandaltman.py |
| `bollinger` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_bollinger.py; No callable named 'make_bollinger' in make_bollinger.py |
| `boxen` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_boxen.py; No callable named 'make_boxen' in make_boxen.py |
| `boxplot` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `bubble` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_bubble.py; No callable named 'make_bubble' in make_bubble.py |
| `bullet` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_bullet.py; No callable named 'make_bullet' in make_bullet.py |
| `calibration` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_calibration.py; No callable named 'make_calibration' in make_calibration.py |
| `chord` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_chord.py; No callable named 'make_chord' in make_chord.py |
| `circle-packing` | legacy | **no** | **no** | **no** | not_run | No DEMO_DATA in make_circle-packing.py; No callable named 'make_circle_packing' in make_circle-packing.py |
| `columnrange` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `confusion-matrix` | legacy | **no** | **no** | **no** | not_run | No DEMO_DATA in make_confusion-matrix.py; No callable named 'make_confusion_matrix' in make_confusion-matrix.py |
| `connected-scatter` | legacy | **no** | **no** | **no** | not_run | No DEMO_DATA in make_connected-scatter.py; No callable named 'make_connected_scatter' in make_connected-scatter.py |
| `convex-hull` | legacy | **no** | **no** | **no** | not_run | No DEMO_DATA in make_convex-hull.py; No callable named 'make_convex_hull' in make_convex-hull.py |
| `cycle` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_cycle.py; No callable named 'make_cycle' in make_cycle.py |
| `dendrogram` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_dendrogram.py; No callable named 'make_dendrogram' in make_dendrogram.py |
| `dependency-wheel` | legacy | **no** | **no** | **no** | not_run | No DEMO_DATA in make_dependency-wheel.py; No callable named 'make_dependency_wheel' in make_dependency-wheel.py |
| `difference-chart` | legacy | **no** | **no** | **no** | not_run | No DEMO_DATA in make_difference-chart.py; No callable named 'make_difference_chart' in make_difference-chart.py |
| `donut` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `dotdensity` | legacy | yes | yes | **no** | not_run | No DEMO_DATA in make_dotdensity.py; Default output path falls back to a shared assets/ directory |
| `dotplot` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_dotplot.py; No callable named 'make_dotplot' in make_dotplot.py |
| `dumbbell` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `edge-bundling` | legacy | **no** | **no** | **no** | not_run | No DEMO_DATA in make_edge-bundling.py; No callable named 'make_edge_bundling' in make_edge-bundling.py |
| `elbow` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_elbow.py; No callable named 'make_elbow' in make_elbow.py |
| `embedding_projector` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_embedding_projector.py; No callable named 'make_embedding_projector' in make_embedding_projector.py |
| `forest` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_forest.py; No callable named 'make_forest' in make_forest.py |
| `funnel` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `gapminder` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_gapminder.py; No callable named 'make_gapminder' in make_gapminder.py |
| `gapminder_variants` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_gapminder_variants.py; No callable named 'make_gapminder_variants' in make_gapminder_variants.py |
| `gauge` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_gauge.py; No callable named 'make_gauge' in make_gauge.py |
| `heatmap` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `hexbin-map` | legacy | **no** | yes | **no** | not_run | No DEMO_DATA in make_hexbin-map.py; make_figure('hexbin-map') cannot resolve to make_hexbin-map.py: hyphen/underscore normalisation looks for a different filename |
| `hexmap` | legacy | yes | yes | **no** | not_run | No DEMO_DATA in make_hexmap.py; Default output path falls back to a shared assets/ directory |
| `histogram` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `horizon` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_horizon.py; No callable named 'make_horizon' in make_horizon.py |
| `icicle` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_icicle.py; No callable named 'make_icicle' in make_icicle.py |
| `imshow-interpolated` | legacy | **no** | yes | **no** | not_run | No DEMO_DATA in make_imshow-interpolated.py; make_figure('imshow-interpolated') cannot resolve to make_imshow-interpolated.py: hyphen/underscore normalisation looks for a different filename |
| `interruption-matrix` | stable | **no** | yes | yes | passed | make_figure('interruption-matrix') cannot resolve to make_interruption-matrix.py: hyphen/underscore normalisation looks for a different filename |
| `jointplot` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_jointplot.py; No callable named 'make_jointplot' in make_jointplot.py |
| `liftgain` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_liftgain.py; No callable named 'make_liftgain' in make_liftgain.py |
| `line` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `liquid-gauge` | legacy | **no** | **no** | **no** | not_run | No DEMO_DATA in make_liquid-gauge.py; No callable named 'make_liquid_gauge' in make_liquid-gauge.py |
| `manhattan` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_manhattan.py; No callable named 'make_manhattan' in make_manhattan.py |
| `mosaic` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_mosaic.py; No callable named 'make_mosaic' in make_mosaic.py |
| `network` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_network.py; No callable named 'make_network' in make_network.py |
| `org-chart` | legacy | **no** | **no** | **no** | not_run | No DEMO_DATA in make_org-chart.py; No callable named 'make_org_chart' in make_org-chart.py |
| `packed-bubble` | legacy | **no** | **no** | **no** | not_run | No DEMO_DATA in make_packed-bubble.py; No callable named 'make_packed_bubble' in make_packed-bubble.py |
| `pairplot` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_pairplot.py; No callable named 'make_pairplot' in make_pairplot.py |
| `parallel-sets` | legacy | **no** | **no** | **no** | not_run | No DEMO_DATA in make_parallel-sets.py; No callable named 'make_parallel_sets' in make_parallel-sets.py |
| `parcoords` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_parcoords.py; No callable named 'make_parcoords' in make_parcoords.py |
| `pareto` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_pareto.py; No callable named 'make_pareto' in make_pareto.py |
| `parliament` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_parliament.py; No callable named 'make_parliament' in make_parliament.py |
| `pictorial` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_pictorial.py; No callable named 'make_pictorial' in make_pictorial.py |
| `polar` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_polar.py; No callable named 'make_polar' in make_polar.py |
| `ppplot` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_ppplot.py; No callable named 'make_ppplot' in make_ppplot.py |
| `prcurve` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_prcurve.py; No callable named 'make_prcurve' in make_prcurve.py |
| `radar` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_radar.py; No callable named 'make_radar' in make_radar.py |
| `radial-bar` | legacy | **no** | **no** | **no** | not_run | No DEMO_DATA in make_radial-bar.py; No callable named 'make_radial_bar' in make_radial-bar.py |
| `radial-tree` | legacy | **no** | **no** | **no** | not_run | No DEMO_DATA in make_radial-tree.py; No callable named 'make_radial_tree' in make_radial-tree.py |
| `radviz` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_radviz.py; No callable named 'make_radviz' in make_radviz.py |
| `residual` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_residual.py; No callable named 'make_residual' in make_residual.py |
| `ridgeline` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_ridgeline.py; No callable named 'make_ridgeline' in make_ridgeline.py |
| `rose` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_rose.py; No callable named 'make_rose' in make_rose.py |
| `rug` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_rug.py; No callable named 'make_rug' in make_rug.py |
| `sankey` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `scatter` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `scatter3d` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_scatter3d.py; No callable named 'make_scatter3d' in make_scatter3d.py |
| `sfdp-largegraph` | legacy | **no** | **no** | **no** | not_run | No DEMO_DATA in make_sfdp-largegraph.py; No callable named 'make_sfdp_largegraph' in make_sfdp-largegraph.py |
| `situation_map` | legacy | yes | yes | **no** | not_run | No DEMO_DATA in make_situation_map.py |
| `speaking_time` | legacy | yes | yes | **no** | not_run | No DEMO_DATA in make_speaking_time.py |
| `spectrogram` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_spectrogram.py; No callable named 'make_spectrogram' in make_spectrogram.py |
| `spike-map` | legacy | **no** | yes | **no** | not_run | No DEMO_DATA in make_spike-map.py; make_figure('spike-map') cannot resolve to make_spike-map.py: hyphen/underscore normalisation looks for a different filename |
| `streamgraph` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_streamgraph.py; No callable named 'make_streamgraph' in make_streamgraph.py |
| `streamplot` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_streamplot.py; No callable named 'make_streamplot' in make_streamplot.py |
| `sunburst` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `surface3d` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_surface3d.py; No callable named 'make_surface3d' in make_surface3d.py |
| `ternary` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_ternary.py; No callable named 'make_ternary' in make_ternary.py |
| `timeline` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_timeline.py; No callable named 'make_timeline' in make_timeline.py |
| `tree` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_tree.py; No callable named 'make_tree' in make_tree.py |
| `treemap` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `upset` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_upset.py; No callable named 'make_upset' in make_upset.py |
| `variwide` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_variwide.py; No callable named 'make_variwide' in make_variwide.py |
| `venn` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_venn.py; No callable named 'make_venn' in make_venn.py |
| `voronoi` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_voronoi.py; No callable named 'make_voronoi' in make_voronoi.py |
| `waffle` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `waterfall` | stable | yes | yes | yes | passed | Default output path falls back to a shared assets/ directory |
| `windbarb` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_windbarb.py; No callable named 'make_windbarb' in make_windbarb.py |
| `windrose` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_windrose.py; No callable named 'make_windrose' in make_windrose.py |
| `wireframe3d` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_wireframe3d.py; No callable named 'make_wireframe3d' in make_wireframe3d.py |
| `wordcloud` | legacy | yes | **no** | **no** | not_run | No DEMO_DATA in make_wordcloud.py; No callable named 'make_wordcloud' in make_wordcloud.py |
