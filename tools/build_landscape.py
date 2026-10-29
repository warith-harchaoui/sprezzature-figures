"""
build_landscape.py — regenerate the data-viz landscape quadrant via standpoint.

``assets/landscape.{svg,white.svg,png,white.png,md,yaml}`` compare
sprezzature-figures to 40 other data-viz tools on two axes derived by PCA
(principal component analysis: a standard statistical method that takes many
measured criteria and compresses them down to the handful of axes that
capture most of the differences between tools, so 22 criteria can be plotted
on just two). This diagram sits outside the ``make_<kind>.py`` chart catalog:
no generator produces it, it is not in FIGURES.md, and ``make_figure()``
cannot reach it. It is a one-off marketing quadrant, not a reusable chart
type.

The tool for this job is ``standpoint``
(https://github.com/warith-harchaoui/standpoint), a positioning-map library
built on the same PCA idea, which emits a direct, hand-authored, interactive
SVG of its own (``to_svg``), so this script is a thin call into it against the committed source table,
``assets/landscape.csv`` (41 tools by 22 criteria, with sprezzature-figures
as the reference row). That CSV is itself generated from the star table in
``LANDSCAPE.md`` by ``sprezzature/scripts/landscape_to_csv.py``, which is the
single source of truth: the Markdown table is written, the CSV is derived,
and nothing is rated twice. ``standpoint`` is a dev-time tool for regenerating this one
asset, not a runtime dependency of the shipped package (it is not listed in
``pyproject.toml``), matching how the Ralph Eyeball Loop's own dev tooling
stays outside the installable ``dataviz`` extra.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

from pathlib import Path

import standpoint as sp

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    pos = sp.positioning(str(ROOT / "assets" / "landscape.csv"), reference=0)
    written = pos.export(str(ROOT / "assets"), stem="landscape")
    for path in written:
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
