"""
build_landscape.py — regenerate the data-viz landscape quadrant via standpoint.

``assets/landscape.{svg,white.svg,png,white.png,md,yaml}`` compare
sprezzature-figures to 36 other data-viz tools on two axes derived by PCA
(principal component analysis: a standard statistical method that takes many
measured criteria and compresses them down to the handful of axes that
capture most of the differences between tools, so 22 criteria can be plotted
on just two). This diagram sits outside the ``make_<kind>.py`` chart catalog:
no generator produces it, it is not in FIGURES.md, and ``make_figure()``
cannot reach it. It is a one-off marketing quadrant, not a reusable chart
type.

It used to be hand-authored Vega (then, briefly, a hand-rolled SVG replica of
that Vega layout). Both are gone. The actual tool for this job now is
``standpoint`` (https://github.com/warith-harchaoui/standpoint), a
positioning-map library built on the same PCA idea, which emits a direct,
hand-authored, interactive SVG of its own (``to_svg``, no Vega anywhere), so
this script is now a thin call into it against the committed source table,
``landscape.csv`` (37 tools by 22 criteria, with sprezzature-figures as the
reference row). ``standpoint`` is a dev-time tool for regenerating this one
asset, not a runtime dependency of the shipped package (it is not listed in
``pyproject.toml``), matching how the Ralph Eyeball Loop's own dev tooling
stays outside the installable ``dataviz`` extra.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

from pathlib import Path

import standpoint as sp

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    pos = sp.positioning(str(ROOT / "landscape.csv"), reference=0)
    written = pos.export(str(ROOT / "assets"), stem="landscape")
    for path in written:
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
