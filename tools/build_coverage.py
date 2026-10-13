#!/usr/bin/env python3
"""
build_coverage — what the other chart libraries draw, and what answers it here.

The claim this file exists to make checkable: anything seaborn, matplotlib,
Plotly, Chart.js / QuickChart, AntV, ECharts, Vega-Lite, Observable Plot,
ggplot2 / plotnine, Highcharts, Datawrapper or RAWGraphs can draw should be
drawable here too, and better. A claim like that is worth nothing unless it
names every chart on the other side and says which kind answers it, so this
module holds that mapping, one row per chart type per library.

``MAPPING`` below is hand-authored -- it is a judgement about what answers
what, which no introspection can derive -- and everything else is generated
from it: ``coverage.csv`` for machines, ``COVERAGE.md`` for readers.
``tests/test_coverage.py`` checks that every kind named here exists in the
registry, so a renamed figure breaks the build rather than the claim.

Status vocabulary
-----------------
``covered``
    A registered kind draws this. The ``kind`` column names it.
``gap``
    Nothing here draws it yet. The ``kind`` column names the figure that
    will answer it, so the matrix *is* the build list: several libraries
    asking for the same thing collapse onto one name (seven of them want
    a plain ``pie``), and the test refuses a row still marked ``gap``
    once that kind exists.
``sibling``
    Geographic work that lives in ``sprezzature-maps``, deliberately not in
    this package: real projections, coastlines, relief and a world basemap
    are that package's job, and drawing them twice is how two catalogues
    start disagreeing about the same map. Each row names the sibling
    generator (``choropleth``, ``density``, ``situation_map``) so the
    boundary is a pointer and not a shrug. Note which geographic forms are
    NOT siblings: ``dotdensity``, ``hexmap``, ``hexbin-map``,
    ``binned-grid-map`` and ``spike-map`` are thematic abstractions of
    geography rather than maps of it, and stay here.
``not-a-figure``
    Not a chart: a table, a mind map, an axis or a tooltip component, a
    free-form diagram. Mermaid and TikZ cover the diagram cases through the
    Ralph Eyeball Loop; the rest are chart-library plumbing.

Usage
-----
::

    python tools/build_coverage.py            # rewrite coverage.csv + COVERAGE.md
    python tools/build_coverage.py --check    # verify only, write nothing

Author
------
Warith HARCHAOUI <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from sprezzature_figures.catalog import resolve_kind  # noqa: E402

OUT_CSV = REPO_ROOT / "coverage.csv"
OUT_MD = REPO_ROOT / "COVERAGE.md"

#: Where each library's catalogue was read, so a reader can check the rows
#: against the source rather than trusting them.
SOURCES: dict[str, str] = {
    "seaborn": "https://seaborn.pydata.org/api.html",
    "matplotlib": "https://matplotlib.org/stable/plot_types/index.html",
    "plotly": "https://plotly.com/python-api-reference/plotly.express.html",
    "quickchart": "https://quickchart.io/documentation/chart-types/",
    "antv": "https://github.com/antvis/mcp-server-chart",
    "echarts": "https://echarts.apache.org/en/cheat-sheet.html",
    "vega-lite": "https://vega.github.io/vega-lite/docs/mark.html",
    "observable-plot": "https://observablehq.com/plot/features/marks",
    "ggplot2": "https://ggplot2.tidyverse.org/reference/",
    "highcharts": "https://www.highcharts.com/demo",
    "datawrapper": "https://www.datawrapper.de/charts",
    "rawgraphs": "https://www.rawgraphs.io/learning",
    "data-science": "the working vocabulary of scikit-learn, statsmodels, SHAP and DoWhy",
}

#: ``library -> [(their name, our kind, status, note)]``. For ``covered``
#: the kind must exist; for ``gap`` it must NOT yet exist -- that column is
#: the name the figure will be registered under. ``sibling`` and
#: ``not-a-figure`` rows carry no kind.
MAPPING: dict[str, list[tuple[str, str, str, str]]] = {
    "seaborn": [
        ("scatterplot", "scatter", "covered", ""),
        ("lineplot", "line", "covered", ""),
        ("relplot", "facet", "covered", ""),
        ("histplot (univariate)", "histogram", "covered", ""),
        ("histplot (bivariate)", "hist2d", "covered", ""),
        ("kdeplot (univariate)", "kde1d", "covered", ""),
        ("kdeplot (bivariate)", "kde2d-contour", "covered", ""),
        ("ecdfplot", "ecdf", "covered", ""),
        ("rugplot", "rug", "covered", ""),
        ("displot", "facet", "covered", ""),
        ("stripplot", "strip", "covered", ""),
        ("swarmplot", "beeswarm", "covered", ""),
        ("boxplot", "boxplot", "covered", ""),
        ("violinplot", "violin", "covered", ""),
        ("boxenplot", "boxen", "covered", ""),
        ("pointplot", "pointplot", "covered", ""),
        ("barplot", "bar", "covered", ""),
        ("countplot", "bar", "covered", "a bar chart of counts"),
        ("catplot", "facet", "covered", ""),
        ("regplot", "regression-ci-band", "covered", ""),
        ("residplot", "residual", "covered", ""),
        ("lmplot", "facet", "covered", ""),
        ("heatmap", "heatmap", "covered", ""),
        ("clustermap", "clustermap", "covered", ""),
        ("pairplot", "pairplot", "covered", ""),
        ("jointplot", "jointplot", "covered", ""),
        ("objects.Dot / Dots", "dotplot", "covered", ""),
        ("objects.Line / Path", "connected-scatter", "covered", ""),
        ("objects.Dash", "rug", "covered", ""),
        ("objects.Range", "columnrange", "covered", ""),
        ("objects.Bar / Bars", "bar", "covered", ""),
        ("objects.Area", "area", "covered", ""),
        ("objects.Band", "regression-ci-band", "covered", ""),
        ("objects.Text", "", "not-a-figure", "an annotation layer, not a chart"),
    ],
    "matplotlib": [
        ("plot", "line", "covered", ""),
        ("scatter", "scatter", "covered", ""),
        ("bar / barh", "bar", "covered", ""),
        ("stem", "stem", "gap", "lollipops on a baseline, for discrete signals"),
        ("fill_between", "area", "covered", ""),
        ("stackplot", "stacked-area", "covered", ""),
        ("stairs", "step", "covered", ""),
        ("hist", "histogram", "covered", ""),
        ("boxplot", "boxplot", "covered", ""),
        ("errorbar", "errorbar", "covered", ""),
        ("violinplot", "violin", "covered", ""),
        ("eventplot", "eventplot", "gap", "spike raster: one tick per event, one row per series"),
        ("hist2d", "hist2d", "covered", ""),
        ("hexbin", "hexbin", "covered", ""),
        ("pie", "pie", "covered", ""),
        ("ecdf", "ecdf", "covered", ""),
        ("imshow", "imshow-interpolated", "covered", ""),
        ("pcolormesh", "heatmap", "covered", ""),
        ("contour / contourf", "contour", "covered", ""),
        ("barbs", "windbarb", "covered", ""),
        ("quiver", "quiver", "covered", ""),
        ("streamplot", "streamplot", "covered", ""),
        ("tricontour / tripcolor / triplot", "tricontour", "gap", "irregular, triangulated grids"),
        ("bar3d", "bar3d", "covered", ""),
        ("plot (3-D line)", "line3d", "gap", "a path through three dimensions"),
        ("scatter (3-D)", "scatter3d", "covered", ""),
        ("plot_surface", "surface3d", "covered", ""),
        ("plot_wireframe", "wireframe3d", "covered", ""),
        ("plot_trisurf", "trisurface", "gap", "surface over a triangulated, irregular domain"),
        ("voxels", "voxels", "gap", "filled volumetric cells"),
        ("quiver (3-D)", "quiver3d", "gap", "vector field in three dimensions"),
    ],
    "plotly": [
        ("scatter", "scatter", "covered", ""),
        ("line", "line", "covered", ""),
        ("area", "stacked-area", "covered", ""),
        ("bar", "bar", "covered", ""),
        ("timeline", "gantt", "covered", ""),
        ("pie", "pie", "covered", ""),
        ("funnel", "funnel", "covered", ""),
        ("funnel_area", "funnel-area", "gap", "stacked proportional sectors, not a funnel of bars"),
        ("histogram", "histogram", "covered", ""),
        ("box", "boxplot", "covered", ""),
        ("violin", "violin", "covered", ""),
        ("strip", "strip", "covered", ""),
        ("ecdf", "ecdf", "covered", ""),
        ("density_contour", "kde2d-contour", "covered", ""),
        ("density_heatmap", "hist2d", "covered", ""),
        ("imshow", "imshow-interpolated", "covered", ""),
        ("treemap", "treemap", "covered", ""),
        ("sunburst", "sunburst", "covered", ""),
        ("icicle", "icicle", "covered", ""),
        ("scatter_matrix", "pairplot", "covered", ""),
        ("parallel_coordinates", "parcoords", "covered", ""),
        ("parallel_categories", "parallel-sets", "covered", ""),
        ("scatter_polar / line_polar", "polar", "covered", ""),
        ("bar_polar", "rose", "covered", ""),
        ("scatter_ternary / line_ternary", "ternary", "covered", ""),
        ("scatter_3d", "scatter3d", "covered", ""),
        ("line_3d", "line3d", "gap", "a path through three dimensions"),
        ("choropleth / choropleth_map", "", "sibling", "sprezzature-maps `choropleth`"),
        ("scatter_geo / scatter_map", "", "sibling", "sprezzature-maps `situation_map`"),
        ("line_geo / line_map", "", "sibling", "sprezzature-maps `situation_map`"),
        ("density_map", "", "sibling", "sprezzature-maps `density`"),
    ],
    "quickchart": [
        ("bar / horizontalBar", "bar", "covered", ""),
        ("line", "line", "covered", ""),
        ("radar", "radar", "covered", ""),
        ("pie", "pie", "covered", ""),
        ("doughnut", "donut", "covered", ""),
        ("polarArea", "rose", "covered", ""),
        ("scatter", "scatter", "covered", ""),
        ("bubble", "bubble", "covered", ""),
        ("radialGauge", "gauge", "covered", ""),
        ("gauge (speedometer)", "gauge", "covered", ""),
        ("violin", "violin", "covered", ""),
        ("boxplot", "boxplot", "covered", ""),
        ("funnel", "funnel", "covered", ""),
        ("candlestick", "candlestick", "covered", ""),
        ("ohlc", "ohlc", "gap", "open-high-low-close bars, not candle bodies"),
        ("sparkline", "sparkline", "covered", ""),
        ("sankey", "sankey", "covered", ""),
        ("progressBar", "progress", "gap", ""),
        ("mixed (bar + line)", "dual-axis", "covered", ""),
        ("QR code", "", "not-a-figure", "not a chart"),
    ],
    "antv": [
        ("generate_area_chart", "area", "covered", ""),
        ("generate_bar_chart", "bar", "covered", ""),
        ("generate_column_chart", "bar", "covered", ""),
        ("generate_boxplot_chart", "boxplot", "covered", ""),
        ("generate_dual_axes_chart", "dual-axis", "covered", ""),
        ("generate_fishbone_diagram", "fishbone", "gap", "Ishikawa cause-and-effect"),
        ("generate_flow_diagram", "", "not-a-figure", "Mermaid, through the Ralph loop"),
        ("generate_funnel_chart", "funnel", "covered", ""),
        ("generate_histogram_chart", "histogram", "covered", ""),
        ("generate_line_chart", "line", "covered", ""),
        ("generate_liquid_chart", "liquid-gauge", "covered", ""),
        ("generate_mind_map", "", "not-a-figure", "Mermaid, through the Ralph loop"),
        ("generate_network_graph", "network", "covered", ""),
        ("generate_organization_chart", "org-chart", "covered", ""),
        ("generate_pie_chart", "pie", "covered", ""),
        ("generate_radar_chart", "radar", "covered", ""),
        ("generate_sankey_chart", "sankey", "covered", ""),
        ("generate_scatter_chart", "scatter", "covered", ""),
        ("generate_treemap_chart", "treemap", "covered", ""),
        ("generate_venn_chart", "venn", "covered", ""),
        ("generate_violin_chart", "violin", "covered", ""),
        ("generate_word_cloud_chart", "wordcloud", "covered", ""),
        ("generate_spreadsheet", "table", "gap", ""),
        ("generate_district_map", "", "sibling", "sprezzature-maps `choropleth`"),
        ("generate_pin_map", "", "sibling", "sprezzature-maps `situation_map`"),
        ("generate_path_map", "", "sibling", "sprezzature-maps `situation_map`"),
    ],
    "echarts": [
        ("bar", "bar", "covered", ""),
        ("line", "line", "covered", ""),
        ("pie", "pie", "covered", ""),
        ("scatter / effectScatter", "scatter", "covered", ""),
        ("candlestick", "candlestick", "covered", ""),
        ("radar", "radar", "covered", ""),
        ("heatmap", "heatmap", "covered", ""),
        ("tree", "tree", "covered", ""),
        ("treemap", "treemap", "covered", ""),
        ("sunburst", "sunburst", "covered", ""),
        ("graph", "network", "covered", ""),
        ("boxplot", "boxplot", "covered", ""),
        ("parallel", "parcoords", "covered", ""),
        ("gauge", "gauge", "covered", ""),
        ("funnel", "funnel", "covered", ""),
        ("sankey", "sankey", "covered", ""),
        ("themeRiver", "streamgraph", "covered", ""),
        ("pictorialBar", "pictorial", "covered", ""),
        ("map", "", "sibling", "sprezzature-maps `choropleth`"),
        ("lines (flow map)", "", "sibling", "sprezzature-maps `situation_map`"),
        ("custom", "", "not-a-figure", "an extension point, not a chart"),
    ],
    "vega-lite": [
        ("arc", "donut", "covered", "the full circle is `pie`, still a gap"),
        ("area", "area", "covered", ""),
        ("bar", "bar", "covered", ""),
        ("boxplot", "boxplot", "covered", ""),
        ("circle / point / square", "scatter", "covered", ""),
        ("errorband", "regression-ci-band", "covered", ""),
        ("errorbar", "errorbar", "covered", ""),
        ("line", "line", "covered", ""),
        ("rect", "heatmap", "covered", ""),
        ("rule", "errorbar", "covered", ""),
        ("tick", "rug", "covered", ""),
        ("trail", "variwide", "covered", "a line whose width carries a value"),
        ("geoshape", "", "sibling", "sprezzature-maps `choropleth`"),
        ("image / text", "", "not-a-figure", "layout primitives"),
    ],
    "observable-plot": [
        ("areaX / areaY", "area", "covered", ""),
        ("barX / barY", "bar", "covered", ""),
        ("boxX / boxY", "boxplot", "covered", ""),
        ("bollinger", "bollinger", "covered", ""),
        ("cell", "heatmap", "covered", ""),
        ("contour", "contour", "covered", ""),
        ("delaunay / voronoi", "voronoi", "covered", ""),
        ("density", "kde2d-contour", "covered", ""),
        ("dot", "scatter", "covered", ""),
        ("hexbin / hexgrid", "hexbin", "covered", ""),
        ("line", "line", "covered", ""),
        ("linearRegression", "regression-ci-band", "covered", ""),
        ("link", "arcdiagram", "covered", ""),
        ("raster", "imshow-interpolated", "covered", ""),
        ("rect", "heatmap", "covered", ""),
        ("rule / tick", "rug", "covered", ""),
        ("tree", "tree", "covered", ""),
        ("vector / arrow", "quiver", "covered", ""),
        ("waffle", "waffle", "covered", ""),
        ("geo / sphere / graticule", "", "sibling", "sprezzature-maps `choropleth`"),
        ("axis / frame / grid / tip", "", "not-a-figure", "chart furniture"),
    ],
    "ggplot2": [
        ("geom_point", "scatter", "covered", ""),
        ("geom_line / geom_path", "line", "covered", ""),
        ("geom_bar / geom_col", "bar", "covered", ""),
        ("geom_histogram", "histogram", "covered", ""),
        ("geom_density", "kde1d", "covered", ""),
        ("geom_boxplot", "boxplot", "covered", ""),
        ("geom_violin", "violin", "covered", ""),
        ("geom_jitter", "strip", "covered", ""),
        ("geom_dotplot", "dotplot", "covered", ""),
        ("geom_smooth", "regression-ci-band", "covered", ""),
        ("geom_area / geom_ribbon", "area", "covered", ""),
        ("geom_step", "step", "covered", ""),
        ("geom_tile / geom_raster", "heatmap", "covered", ""),
        ("geom_hex", "hexbin", "covered", ""),
        ("geom_bin2d", "hist2d", "covered", ""),
        ("geom_contour", "contour", "covered", ""),
        ("geom_qq", "qqplot", "covered", ""),
        ("geom_errorbar / geom_linerange", "errorbar", "covered", ""),
        ("geom_pointrange / geom_crossbar", "pointplot", "covered", ""),
        ("geom_segment / geom_curve", "dumbbell", "covered", ""),
        ("geom_spoke", "quiver", "covered", ""),
        ("geom_rug", "rug", "covered", ""),
        ("geom_count", "bubble", "covered", ""),
        ("facet_wrap / facet_grid", "facet", "covered", ""),
        ("geom_map / coord_map", "", "sibling", "sprezzature-maps `choropleth`"),
    ],
    "highcharts": [
        ("packedbubble", "packed-bubble", "covered", ""),
        ("bullet", "bullet", "covered", ""),
        ("dependencywheel", "dependency-wheel", "covered", ""),
        ("item (parliament)", "parliament", "covered", ""),
        ("xrange", "gantt", "covered", ""),
        ("windbarb", "windbarb", "covered", ""),
        ("streamgraph", "streamgraph", "covered", ""),
        ("bellcurve", "bellcurve", "covered", ""),
        ("pareto", "pareto", "covered", ""),
        ("tilemap", "hexmap", "covered", ""),
        ("organization", "org-chart", "covered", ""),
        ("treegraph", "tree", "covered", ""),
        ("arcdiagram", "arcdiagram", "covered", ""),
        ("dumbbell / lollipop", "dumbbell", "covered", ""),
        ("variwide", "variwide", "covered", ""),
        ("timeline", "timeline", "covered", ""),
        ("solidgauge", "gauge", "covered", ""),
        ("wordcloud", "wordcloud", "covered", ""),
        ("venn", "venn", "covered", ""),
        ("vector", "quiver", "covered", ""),
        ("waterfall", "waterfall", "covered", ""),
        ("pyramid", "funnel", "covered", "an inverted funnel"),
        ("pie / semicircle pie", "pie", "covered", ""),
        ("sparkline", "sparkline", "covered", ""),
        ("ohlc", "ohlc", "gap", ""),
        ("heatmap", "heatmap", "covered", ""),
        ("network graph", "network", "covered", ""),
        ("sunburst", "sunburst", "covered", ""),
    ],
    "datawrapper": [
        ("bar / column / stacked", "bar", "covered", ""),
        ("line / area", "line", "covered", ""),
        ("scatter", "scatter", "covered", ""),
        ("range plot", "columnrange", "covered", ""),
        ("arrow plot", "difference-chart", "covered", ""),
        ("donut / election donut", "donut", "covered", ""),
        ("pie", "pie", "covered", ""),
        ("multiple pies / small multiples", "facet", "covered", ""),
        ("table", "table", "gap", ""),
        ("election hemicycle", "parliament", "covered", ""),
        (
            "locator / choropleth / symbol map",
            "",
            "sibling",
            "sprezzature-maps `choropleth` / `situation_map`",
        ),
    ],
    "rawgraphs": [
        ("alluvial", "alluvial", "covered", ""),
        ("beeswarm", "beeswarm", "covered", ""),
        ("bump chart", "bump", "gap", "rank over time, one ribbon per competitor"),
        ("circle packing", "circle-packing", "covered", ""),
        ("circular dendrogram", "radial-tree", "covered", ""),
        ("contour plot", "contour", "covered", ""),
        ("convex hull", "convex-hull", "covered", ""),
        ("gantt", "gantt", "covered", ""),
        ("hexagonal binning", "hexbin", "covered", ""),
        ("horizon graph", "horizon", "covered", ""),
        ("matrix plot", "heatmap", "covered", ""),
        ("multi-set bar", "bar-grouped", "covered", ""),
        ("parallel coordinates", "parcoords", "covered", ""),
        ("sankey", "sankey", "covered", ""),
        ("slope", "slope", "covered", ""),
        ("streamgraph", "streamgraph", "covered", ""),
        ("sunburst", "sunburst", "covered", ""),
        ("treemap", "treemap", "covered", ""),
        ("violin", "violin", "covered", ""),
        ("voronoi", "voronoi", "covered", ""),
    ],
    "data-science": [
        ("ROC curve", "roc-curve", "covered", ""),
        ("precision-recall curve", "prcurve", "covered", ""),
        ("confusion matrix", "confusion-matrix", "covered", ""),
        ("calibration curve", "calibration", "covered", ""),
        ("lift / gain chart", "liftgain", "covered", ""),
        ("residual plot", "residual", "covered", ""),
        ("Q-Q plot", "qqplot", "covered", ""),
        ("P-P plot", "ppplot", "covered", ""),
        ("elbow (k selection)", "elbow", "covered", ""),
        ("correlation matrix", "corr-matrix", "covered", ""),
        ("ablation study", "ablation_matrix", "covered", ""),
        ("embedding projection (t-SNE / UMAP)", "embedding_projector", "covered", ""),
        ("Kaplan-Meier survival", "survival-km", "covered", ""),
        ("forest plot (meta-analysis)", "forest", "covered", ""),
        ("volcano plot", "volcano", "covered", ""),
        ("Manhattan plot", "manhattan", "covered", ""),
        ("Bland-Altman", "blandaltman", "covered", ""),
        ("Gaussian process posterior", "gaussian-process", "covered", ""),
        ("learning curve", "learning-curve", "covered", ""),
        ("validation curve", "validation-curve", "covered", ""),
        ("training / loss curve", "loss-curve", "covered", ""),
        ("silhouette plot", "silhouette", "covered", ""),
        ("ACF / PACF correlogram", "acf", "covered", ""),
        ("seasonal decomposition", "seasonal-decomposition", "covered", ""),
        ("forecast fan chart", "forecast-fan", "covered", ""),
        (
            "SHAP beeswarm",
            "shap-beeswarm",
            "gap",
            "per-feature SHAP values, coloured by feature value",
        ),
        (
            "SHAP waterfall",
            "shap-waterfall",
            "gap",
            "one prediction, decomposed contribution by contribution",
        ),
        (
            "partial dependence / ICE",
            "pdp-ice",
            "gap",
            "average effect of a feature, and per-sample",
        ),
        (
            "permutation importance",
            "permutation-importance",
            "gap",
            "importance with its spread, not a bare bar",
        ),
        ("causal DAG", "causal-dag", "gap", "the DoWhy graph: treatment, outcome, confounders"),
        ("missing-data matrix", "missing-matrix", "covered", ""),
        ("control chart (SPC)", "control-chart", "covered", ""),
        ("cohort retention", "cohort-retention", "gap", "triangle of cohorts against age"),
    ],
}


def _rows() -> list[dict[str, str]]:
    """Flatten MAPPING into one dict per chart type, library column first."""
    return [
        {
            "library": library,
            "chart": chart,
            "kind": kind,
            "status": status,
            "note": note,
        }
        for library, entries in MAPPING.items()
        for chart, kind, status, note in entries
    ]


def problems(rows: list[dict[str, str]]) -> list[str]:
    """Everything wrong with the mapping, as sentences a reader can act on."""
    found: list[str] = []
    for row in rows:
        where = f"{row['library']}:{row['chart']}"
        if row["status"] == "covered":
            if not row["kind"]:
                found.append(f"{where} is marked covered but names no kind.")
            elif resolve_kind(row["kind"]) is None:
                found.append(f"{where} names {row['kind']!r}, which no longer exists.")
        elif row["status"] == "gap":
            if not row["kind"]:
                found.append(f"{where} is a gap but does not name the kind to build.")
            elif resolve_kind(row["kind"]) is not None:
                found.append(
                    f"{where} is still marked a gap, but {row['kind']!r} now exists: "
                    "flip the row to covered."
                )
        elif row["kind"]:
            found.append(f"{where} is {row['status']} but names a kind; clear it.")
        if row["status"] not in {"covered", "gap", "sibling", "not-a-figure"}:
            found.append(f"{where} has an unknown status {row['status']!r}.")
    return found


def gap_names(rows: list[dict[str, str]]) -> list[str]:
    """The kinds still to build, most-asked-for first, ties in catalogue order.

    Ordering by how many libraries ask for a thing is the whole point of
    counting them: a plain pie is wanted by seven and a voxel grid by one,
    and that is the build order.
    """
    asks = Counter(row["kind"] for row in rows if row["status"] == "gap")
    first_seen: dict[str, int] = {}
    for index, row in enumerate(rows):
        if row["status"] == "gap":
            first_seen.setdefault(row["kind"], index)
    return sorted(asks, key=lambda name: (-asks[name], first_seen[name]))


def render_markdown(rows: list[dict[str, str]]) -> str:
    """COVERAGE.md: the headline numbers, then one table per library."""
    counts = Counter(row["status"] for row in rows)
    libraries = list(MAPPING)
    gaps = [row for row in rows if row["status"] == "gap"]
    charts = len({(row["library"], row["chart"]) for row in rows})

    lines = [
        "# Coverage",
        "",
        "What every other chart library draws, and what answers it here.",
        "",
        "The promise is a superset: anything seaborn, matplotlib, Plotly, Chart.js /",
        "QuickChart, AntV, ECharts, Vega-Lite, Observable Plot, ggplot2, Highcharts,",
        "Datawrapper or RAWGraphs can draw should be drawable here, and better. A",
        "promise like that is only worth something if it names every chart on the",
        "other side, so this page does, one row each.",
        "",
        f"**{charts} chart types across {len(libraries)} libraries.** "
        f"{counts['covered']} answered by a registered kind, {counts['gap']} still open, "
        f"{counts['sibling']} geographic (they live in `sprezzature-maps`), "
        f"{counts['not-a-figure']} not charts at all.",
        "",
        "This file is generated by `tools/build_coverage.py`; the machine-readable",
        "twin is [`coverage.csv`](coverage.csv). `tests/test_coverage.py` checks that",
        "every kind named here still exists, so a renamed figure breaks the build",
        "rather than the claim.",
        "",
        "| Status | Meaning |",
        "|---|---|",
        "| `covered` | A registered kind draws this. |",
        "| `gap` | Nothing here draws it yet. This is the build list. |",
        "| `sibling` | Geographic work, deliberately in `sprezzature-maps`. |",
        "| `not-a-figure` | A table, a mind map, chart furniture. Mermaid and TikZ cover the diagrams. |",
        "",
    ]

    if gaps:
        lines += [
            "## Still open",
            "",
            "Every gap, and the libraries that ask for it. Each becomes a",
            "hand-authored SVG generator, verified through the Ralph Eyeball Loop",
            "like every other figure here.",
            "",
            "| Wanted | Asks | Asked for by | What it is |",
            "|---|---:|---|---|",
        ]
        by_target: dict[str, dict[str, list[str]]] = {}
        for row in gaps:
            entry = by_target.setdefault(row["kind"], {"asked": [], "what": []})
            entry["asked"].append(f"{row['library']} `{row['chart']}`")
            if row["note"]:
                entry["what"].append(row["note"])
        for target in gap_names(rows):
            entry = by_target[target]
            what = entry["what"][0] if entry["what"] else ""
            lines.append(
                f"| `{target}` | {len(entry['asked'])} | {', '.join(entry['asked'])} | {what} |"
            )
        lines.append("")

    for library in libraries:
        entries = [row for row in rows if row["library"] == library]
        done = sum(1 for row in entries if row["status"] == "covered")
        lines += [
            f"## {library}",
            "",
            f"{done}/{len(entries)} answered. Read from {SOURCES[library]}.",
            "",
            "| Their chart | Here | Status | Note |",
            "|---|---|---|---|",
        ]
        for row in entries:
            kind = f"`{row['kind']}`" if row["kind"] else "—"
            lines.append(f"| `{row['chart']}` | {kind} | {row['status']} | {row['note']} |")
        lines.append("")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Rewrite coverage.csv and COVERAGE.md, or just check the mapping."""
    parser = argparse.ArgumentParser(
        prog="build_coverage",
        description="Regenerate the cross-library coverage matrix.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate the mapping and report the gaps; write nothing.",
    )
    args = parser.parse_args(argv)

    rows = _rows()
    found = problems(rows)
    for problem in found:
        print(f"error: {problem}", file=sys.stderr)
    if found:
        return 1

    counts = Counter(row["status"] for row in rows)
    print(
        f"{len(rows)} rows: {counts['covered']} covered, {counts['gap']} gaps, "
        f"{counts['sibling']} sibling, {counts['not-a-figure']} not a figure"
    )
    if args.check:
        for name in gap_names(rows):
            print(f"  wanted: {name}")
        return 0

    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["library", "chart", "kind", "status", "note"])
        writer.writeheader()
        writer.writerows(rows)
    OUT_MD.write_text(render_markdown(rows) + "\n", encoding="utf-8")
    print(f"wrote {OUT_CSV.relative_to(REPO_ROOT)} and {OUT_MD.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
