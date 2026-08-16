"""
Generate ``reproduce.py`` for the export archive (plan §14): a standalone
script using only sprezzature-figures' public API
(``from sprezzature_figures import make_figure``), never any internal
studio module, so it runs in a clean environment with just the declared
library installed.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from sprezzature_figures.core.figure_plan import FigurePlan

_TEMPLATE = '''\
"""
Reproduce this figure from the exported data using the public
sprezzature-figures API.

Usage
-----
    pip install sprezzature-figures=={version}
    python reproduce.py
"""

import csv

from sprezzature_figures import make_figure

with open("data/transformed.csv", newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

# Role bindings recorded in figure-plan.json, resolved to the column names
# each row already carries after this project's transformations.
BINDINGS = {bindings!r}

data = [{{role: row[columns[0]] for role, columns in BINDINGS.items()}} for row in rows]

path = make_figure(
    {kind!r},
    data,
    out="output/figure.svg",
    title={title!r},
)
print(f"Wrote {{path}}")
'''


def generate_reproduce_script(plan: FigurePlan, *, library_version: str = "1.0.0") -> str:
    bindings = {role: binding.columns for role, binding in plan.bindings.items()}
    return _TEMPLATE.format(
        version=library_version, bindings=bindings, kind=plan.figure_kind, title=plan.title
    )
