"""
A research table gets the figure a researcher would draw.

Field trials, weather stations and soil samples were the tables `recommend`
read worst: the yields by treatment came out as bars (one number per arm, the
spread hidden), a year column as bar heights, and biomass against soil
nitrogen as bars again, with the scatter's axes swapped when it was offered.
Once rendered, the axes and the legend were titled after the demo's columns
("salary", "horsepower", "segment") rather than the table's, and the scatter's
ticks fell on 0.83, 11, 22.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

import random
import re
from pathlib import Path

import pandas as pd
import pytest

from sprezzature_figures import actions
from sprezzature_figures.ingest.profiler import profile_dataframe
from sprezzature_figures.recommendation import assign_columns, infer_goal, rank


def _yields() -> list[dict[str, object]]:
    rng = random.Random(4)
    return [
        {"traitement": t, "site": s, "rendement_t_ha": round(rng.gauss(base, 0.7), 2)}
        for t, base in (("Témoin", 5.2), ("N 80", 6.6), ("N 160", 7.4))
        for s in ("Grignon", "Mons", "Colmar")
        for _ in range(8)
    ]


def _temperatures() -> list[dict[str, object]]:
    rng = random.Random(5)
    return [
        {"annee": y, "station": st, "temperature_c": round(b + rng.gauss(0, 0.3), 2)}
        for st, b in (("Avignon", 14.6), ("Rennes", 12.1))
        for y in range(2015, 2025)
    ]


def _biomass() -> list[dict[str, object]]:
    rng = random.Random(6)
    rows = []
    for site in ("Grignon", "Mons", "Colmar"):
        for _ in range(20):
            n = rng.uniform(5, 60)
            rows.append(
                {
                    "azote_sol_mg_kg": round(n, 1),
                    "biomasse_g_m2": round(120 + 9 * n + rng.gauss(0, 60), 1),
                    "site": site,
                }
            )
    return rows


def _profile(rows: list[dict[str, object]]):
    return profile_dataframe(pd.DataFrame(rows), dataset_id="t", fingerprint="t", source_name="t")


def _top(rows: list[dict[str, object]]):
    profile = _profile(rows)
    return rank(profile, goal=infer_goal(profile))[0][0], profile


def test_replicates_by_treatment_are_a_distribution_drawn_as_boxes() -> None:
    top, profile = _top(_yields())
    assert infer_goal(profile) == "distribution"
    assert top.kind == "boxplot"


def test_a_year_column_is_the_time_axis_of_a_line_per_station() -> None:
    top, profile = _top(_temperatures())
    assert profile.column("annee").semantic_type == "datetime"
    assert top.kind == "line"
    binding = assign_columns(top, profile)
    assert binding["month"] == "annee" and binding.get("series") == "station"


def test_two_measures_with_a_site_column_are_a_scatter_in_column_order() -> None:
    top, profile = _top(_biomass())
    assert infer_goal(profile) == "relationship"
    assert top.kind == "scatter"
    binding = assign_columns(top, profile)
    # x is the first measure of the table (the cause), y the second.
    assert binding["horsepower"] == "azote_sol_mg_kg"
    assert binding["mpg"] == "biomasse_g_m2"
    assert binding.get("segment") == "site"


def test_a_row_label_is_never_a_colour_group() -> None:
    rows = [{"x": i, "y": 2 * i + 1, "nom": f"seg{i}"} for i in range(12)]
    profile = _profile(rows)
    scatter = next(d for d, _ in rank(profile) if d.kind == "scatter")
    assert "segment" not in (assign_columns(scatter, profile) or {})


@pytest.mark.parametrize(
    "rows, columns",
    [
        (_yields(), ("traitement", "rendement_t_ha")),
        (_temperatures(), ("annee", "temperature_c", "station")),
        (_biomass(), ("azote_sol_mg_kg", "biomasse_g_m2", "site")),
    ],
)
def test_the_rendered_figure_names_the_tables_columns(
    tmp_path: Path, rows: list[dict[str, object]], columns: tuple[str, ...]
) -> None:
    data = tmp_path / "data.csv"
    pd.DataFrame(rows).to_csv(data, index=False)
    out = tmp_path / "top.svg"
    result = actions.recommend(str(data), render_out=str(out))
    assert any(line.startswith("render it: sprezzature-figures render ") for line in result.out)
    texts = set(re.findall(r">([^<>]+)</text>", out.read_text(encoding="utf-8")))
    for column in columns:
        assert column in texts, f"{column} is not on the figure"
    assert not texts & {"salary", "department", "horsepower", "mpg", "segment", "Series"}


def test_scatter_ticks_fall_on_round_values(tmp_path: Path) -> None:
    data = tmp_path / "data.csv"
    pd.DataFrame(_biomass()).to_csv(data, index=False)
    out = tmp_path / "scatter.svg"
    actions.recommend(str(data), render_out=str(out))
    svg = out.read_text(encoding="utf-8")
    ticks = re.findall(r'text-anchor="(?:end|middle)">(-?[0-9][0-9.,]*)</text>', svg)
    assert ticks, "no tick labels found"
    for tick in ticks:
        value = float(tick.replace(",", ""))
        assert value % 10 == 0 or value % 5 == 0, f"tick {tick} is not round"


def test_a_bar_category_with_angle_brackets_stays_valid_xml(tmp_path: Path) -> None:
    import xml.dom.minidom

    from sprezzature_figures.make_figure import make_figure

    out = tmp_path / "bar.svg"
    make_figure(
        "bar",
        [{"region": "<siège>", "value": 3}, {"region": "Autre", "value": 2}],
        out=str(out),
        theme="print",
    )
    svg = out.read_text(encoding="utf-8")
    xml.dom.minidom.parseString(svg)
    assert "#0088FF" not in svg, "a category outside the demo kept a literal blue"


def test_a_line_series_with_its_own_years_is_not_filled_with_zeros(tmp_path: Path) -> None:
    from sprezzature_figures.make_figure import make_figure

    rows = [
        {"hour": 1971, "platform": "France", "sessions": 2.4},
        {"hour": 2013, "platform": "France", "sessions": 4.0},
        {"hour": 1978, "platform": "Chine", "sessions": 3.38},
        {"hour": 2004, "platform": "Chine", "sessions": 2.22},
    ]
    out = tmp_path / "lm.svg"
    make_figure("line-multi", rows, out=str(out))
    svg = out.read_text(encoding="utf-8")
    assert len(re.findall(r'class="pt hit"', svg)) == 4, "a missing year was drawn as a point"


def test_a_gantt_of_calendar_years_does_not_start_at_zero(tmp_path: Path) -> None:
    from sprezzature_figures.make_figure import make_figure

    rows = [
        {"task": "A", "start": 1945, "end": 1970, "team": "x"},
        {"task": "B", "start": 1961, "end": 2014, "team": "y"},
    ]
    out = tmp_path / "g.svg"
    make_figure("gantt", rows, out=str(out))
    ticks = [int(t) for t in re.findall(r'text-anchor="middle">(\d+)</text>', out.read_text())]
    assert ticks and min(ticks) >= 1900, ticks


def test_a_heatmap_names_every_column_and_fits_its_row_labels(tmp_path: Path) -> None:
    from sprezzature_figures.make_figure import make_figure
    from sprezzature_figures.render_checks import check_render

    postes = ["carburant", "électricité", "engrais N", "fixation biologique", "fumier"]
    rows = [
        {
            "day": f"[3] Harchaoui & Chatzimpiros 2019 · France {i}",
            "hour": p,
            "activity": (i + j) % 2,
        }
        for i in range(4)
        for j, p in enumerate(postes)
    ]
    out = tmp_path / "h.svg"
    make_figure("heatmap", rows, out=str(out), width=900, height=500)
    svg = out.read_text(encoding="utf-8")
    for p in postes:
        assert f">{p}</text>" in svg, f"column {p} is not labelled"
    # the columns keep the data's order, not the alphabet's
    assert (
        svg.index(">électricité<") < svg.index(">engrais N<") < svg.index(">fixation biologique<")
    )
    assert not [f for f in check_render(svg) if f.check == "text_outside_canvas"]
