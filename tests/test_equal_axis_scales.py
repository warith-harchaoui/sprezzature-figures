"""
When two axes carry the same unit, they have to be drawn at the same scale.

A gain chart, a ROC curve, a reliability diagram, a P-P plot, a Q-Q plot: in
each of them the horizontal and the vertical axis measure *the same kind of
thing*, and the figure invites the reader to compare the two directions by
eye -- against a y = x reference line, or by the shape and the area of a
curve. That comparison is only true when a unit of data is worth the same
number of pixels on both axes:

    plot_w / (x_max - x_min) == plot_h / (y_max - y_min)

``liftgain`` shipped with the comment *"square plot, so the diagonal reads at
45°"* sitting on top of an 862 x 620 frame whose y axis ran to 1.06. The
random baseline it called "the diagonal" was drawn at 34.2°, and the gain
band above it -- the whole point of the figure -- looked bigger than it was.
The comment is the interesting part: the code asserted the invariant it broke,
so a reader of the source had no reason to check. ``ppplot`` went further and
printed **"Perfect fit (45°)"** on a line drawn at 39.7°, with the caption
rotated -45 so that it crossed the very line it named.

Note that *square frame* is not the invariant and does not imply it: a square
frame over unequal spans (1.0 of population against 1.06 of gain) lies exactly
as much. The rule is pixels per unit, which is why this file measures them.

What it measures, per figure, is whichever reading the figure itself offers:

* the **angle of the reference diagonal** it draws, for the figures that draw
  one -- read off the longest diagonal ``<line>`` in the document, which must
  come out at 45°;
* the **ratio of pixels per unit** on the two axes, read off the tick labels,
  for a figure that has shared-unit axes and no diagonal (``prcurve``, whose
  reference is the horizontal prevalence line, not a diagonal).

Neither 45 nor 34 is written here as a number somebody remembered: both come
out of the rendered markup. And because a measurement that always answers 45
would pass this file while seeing nothing,
:func:`test_the_measurement_can_see_a_tilted_diagonal` builds a deliberately
unequal plot and checks that the reading follows it -- the sabotage kept
in-suite, so the guard stays verified rather than having been verified once.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from sprezzature_figures.catalog import get_figure_definition
from sprezzature_figures.make_figure import _SCRIPTS_DIR, _load_module

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
EXAMPLES_DIR = REPO_ROOT / "assets" / "svg-examples"

#: How far from a true 45° a drawn reference diagonal may land. Coordinates are
#: written to one decimal, so the slack is rounding, not taste: the four figures
#: measured here come out at 45.00 and the defect this file was written for was
#: 10.8° away.
_ANGLE_TOLERANCE_DEG = 0.1

#: Same slack, expressed on the pixels-per-unit ratio.
_RATIO_TOLERANCE = 0.002


@dataclass(frozen=True)
class SharedUnitFigure:
    """One figure whose two axes carry the same unit, and how to read it.

    Attributes
    ----------
    kind : str
        Catalogue kind, as :func:`sprezzature_figures.catalog.get_figure_definition`
        knows it.
    reading : str
        ``"diagonal"`` when the figure draws a y = x reference line (the angle
        is the measurement), ``"ticks"`` when it does not and the pixels-per-unit
        ratio has to be read off the two tick scales instead.
    why : str
        The unit the two axes share. Written down because *that* is the premise
        under which the measurement means anything.
    options : dict
        Keyword arguments to ``build_svg``. Non-empty only where the shared unit
        is itself an option the caller turns on.
    committed : bool
        Whether ``assets/svg-examples/<kind>.svg`` is a render of this same
        configuration, and so can be measured in the fast lane.
    """

    kind: str
    reading: str
    why: str
    options: dict = field(default_factory=dict)
    committed: bool = True


#: Every figure in this house whose two axes carry one unit.
#:
#: Membership is a statement about the data, not about the markup, so it is
#: written down rather than sniffed: "recall and precision are both shares of a
#: count" is not a fact any SVG parser can recover.
#: :func:`test_the_registry_covers_every_generator_that_claims_the_invariant`
#: is what keeps the list from going stale as figures are added.
SHARED_UNIT_FIGURES: tuple[SharedUnitFigure, ...] = (
    SharedUnitFigure(
        "roc-curve",
        "diagonal",
        "true-positive rate against false-positive rate, both shares in [0, 1]",
    ),
    SharedUnitFigure(
        "liftgain",
        "diagonal",
        "share of the population contacted against share of positives captured",
    ),
    SharedUnitFigure(
        "calibration",
        "diagonal",
        "predicted probability against observed frequency, both in [0, 1]",
    ),
    SharedUnitFigure(
        "ppplot",
        "diagonal",
        "theoretical against empirical probability, both in [0, 1]",
    ),
    SharedUnitFigure(
        "qqplot",
        "diagonal",
        "theoretical against sample quantiles of one variable, one domain",
    ),
    SharedUnitFigure(
        "scatter",
        "diagonal",
        "x against y on one shared domain -- what square=True means",
        options={"square": True, "diagonal": True},
        # The committed example is the default render (square=False), where the
        # two axes are horsepower and miles per gallon and have no business
        # sharing a scale.
        committed=False,
    ),
    SharedUnitFigure(
        "prcurve",
        "ticks",
        "recall against precision, both shares in [0, 1]",
    ),
)

#: Generators that name a 45-degree line without being members: the guard below
#: scans source text, and source text can mention the angle rhetorically.
#:
#: ``pairplot`` earns its place here by saying its diagonal cells hold densities
#: "rather than a wasted 45-degree line". Its off-diagonal cells pair two
#: different variables -- internal resistance against cycle life -- which share
#: no unit and must not share a scale.
_NOT_MEMBERS = {"pairplot": "a SPLOM: each cell pairs two different variables"}

_LINE_TAG = re.compile(r"<line\b[^>]*>")
_TEXT_TAG = re.compile(r"<text\b([^>]*)>(.*?)</text>", re.S)
_ATTR = re.compile(r'([A-Za-z_][\w:-]*)="([^"]*)"')
_NUMERIC_LABEL = re.compile(r"^-?\d+(?:\.\d+)?%?$")


def _attributes(tag: str) -> dict[str, str]:
    """Return the attributes of one SVG start tag."""
    return dict(_ATTR.findall(tag))


def _diagonal_reading(svg: str) -> tuple[float, float]:
    """Measure the longest diagonal ``<line>``: ``(angle_deg, length_px)``.

    Gridlines, axes, ticks and the dropped guides of an operating point are all
    axis-parallel, so requiring both legs to be substantial leaves the reference
    line and anything drawn parallel to it (a tolerance ribbon's rules). The
    angle is in the reader's orientation -- counter-clockwise from the
    horizontal -- not the y-down orientation of the SVG coordinate system.
    """
    best = (0.0, 0.0)
    for tag in _LINE_TAG.findall(svg):
        attrs = _attributes(tag)
        try:
            x1, y1, x2, y2 = (float(attrs[k]) for k in ("x1", "y1", "x2", "y2"))
        except (KeyError, ValueError):
            continue
        dx, dy = x2 - x1, y2 - y1
        if abs(dx) < 20.0 or abs(dy) < 20.0:
            continue
        length = math.hypot(dx, dy)
        if length > best[1]:
            best = (math.degrees(math.atan2(-dy, dx)), length)
    return best


def _label_value(body: str) -> float | None:
    """Parse a tick label into a number, or ``None`` when it is not one.

    ``"20%"`` is 0.2 and ``"0.2"`` is 0.2, so a percent-formatted axis and a
    decimal one are read on one scale. Both axes of a given figure use one
    formatting anyway, which is all the ratio below needs.
    """
    text = re.sub(r"<[^>]*>", "", body).strip().replace("−", "-")
    if not _NUMERIC_LABEL.match(text):
        return None
    if text.endswith("%"):
        return float(text[:-1]) / 100.0
    return float(text)


def _ticks_reading(svg: str) -> tuple[float, float, int]:
    """Measure pixels per unit on both axes: ``(x_per_unit, y_per_unit, n)``.

    An axis is recovered as a run of numeric labels sharing one coordinate --
    the x tick labels all sit on one baseline, the y tick labels all on one
    right edge -- and the scale is the least-squares slope of pixel against
    value over that run. Rotated text (axis titles, a label riding a curve) is
    skipped: its ``x``/``y`` are in its own rotated frame.

    The run with the most labels wins on each axis, and the caller checks that
    the two runs carry *the same set of values* before comparing them. Without
    that check this would happily measure ``calibration``'s histogram panel,
    whose count labels share a left edge with nothing in the reliability square
    above it, and report a ratio of 1888.
    """
    rows: dict[float, list[tuple[float, float]]] = {}
    cols: dict[float, list[tuple[float, float]]] = {}
    for raw_attrs, body in _TEXT_TAG.findall(svg):
        attrs = _attributes(raw_attrs)
        value = _label_value(body)
        if value is None or "transform" in attrs:
            continue
        try:
            x, y = float(attrs["x"]), float(attrs["y"])
        except (KeyError, ValueError):
            continue
        rows.setdefault(round(y, 1), []).append((value, x))
        cols.setdefault(round(x, 1), []).append((value, y))

    def best_run(groups: dict[float, list[tuple[float, float]]]) -> list[tuple[float, float]]:
        runs = [g for g in groups.values() if len({v for v, _ in g}) >= 3]
        return max(runs, key=len) if runs else []

    x_run, y_run = best_run(rows), best_run(cols)
    if not x_run or not y_run:
        return (0.0, 0.0, 0)
    x_values = sorted({round(v, 6) for v, _ in x_run})
    y_values = sorted({round(v, 6) for v, _ in y_run})
    if x_values != y_values:
        return (0.0, 0.0, 0)
    return (_slope(x_run), _slope(y_run), len(x_values))


def _slope(run: list[tuple[float, float]]) -> float:
    """Least-squares pixels per unit over one axis' labelled ticks."""
    n = len(run)
    mean_v = sum(v for v, _ in run) / n
    mean_p = sum(p for _, p in run) / n
    numerator = sum((v - mean_v) * (p - mean_p) for v, p in run)
    denominator = sum((v - mean_v) ** 2 for v, _ in run)
    return abs(numerator / denominator) if denominator else 0.0


def _render(figure: SharedUnitFigure) -> str:
    """Render one registry entry from its live generator."""
    definition = get_figure_definition(figure.kind)
    module = _load_module(
        _SCRIPTS_DIR / Path(definition.module).name,
        f"_equal_scales_{figure.kind.replace('-', '_')}",
    )
    return module.build_svg(**figure.options)


def _assert_equal_scales(figure: SharedUnitFigure, svg: str, where: str) -> None:
    """Assert that *svg* draws ``figure``'s two shared-unit axes at one scale."""
    if figure.reading == "diagonal":
        angle, length = _diagonal_reading(svg)
        assert length > 0.0, (
            f"{figure.kind} ({where}) draws no diagonal reference line, so the "
            "reading this figure is registered for is not there to take"
        )
        assert abs(angle - 45.0) <= _ANGLE_TOLERANCE_DEG, (
            f"{figure.kind} ({where}) draws its y = x reference at "
            f"{angle:.2f}°, not 45°. Its axes both carry {figure.why}, so one "
            "unit has to be worth the same pixels on each: "
            "plot_w / x_span == plot_h / y_span. A square frame over unequal "
            "spans does not do it."
        )
        return

    x_per_unit, y_per_unit, n_ticks = _ticks_reading(svg)
    assert n_ticks >= 3, (
        f"{figure.kind} ({where}): could not read two comparable tick scales "
        f"off the markup (found {n_ticks} shared tick values), so nothing was "
        "measured and this assertion is the only thing that noticed"
    )
    ratio = x_per_unit / y_per_unit
    assert abs(ratio - 1.0) <= _RATIO_TOLERANCE, (
        f"{figure.kind} ({where}) draws {x_per_unit:.1f} px per unit on x "
        f"against {y_per_unit:.1f} on y (ratio {ratio:.4f}). Its axes both "
        f"carry {figure.why}, so the curve's shape, the gap between two curves "
        "and the area under either one are all stretched by that factor in one "
        "direction."
    )


@pytest.mark.slow
def test_the_measurement_places_the_known_good_case_at_45() -> None:
    """Check the ruler on a figure known to be right before trusting it.

    ``roc-curve`` has always set ``plot_w = plot_h = size`` over two 0..1 axes,
    so it is the control: a measurement that cannot put *it* at 45° is saying
    nothing about the figures it then condemns. Both readings are taken here,
    and they have to agree -- the angle and the pixels-per-unit ratio are
    independent paths through the same markup.
    """
    control = next(f for f in SHARED_UNIT_FIGURES if f.kind == "roc-curve")
    svg = _render(control)
    angle, length = _diagonal_reading(svg)
    assert abs(angle - 45.0) <= _ANGLE_TOLERANCE_DEG, f"control reads {angle:.2f}°"
    assert length > 300.0, "the line found is too short to be the reference diagonal"
    x_per_unit, y_per_unit, n_ticks = _ticks_reading(svg)
    assert n_ticks >= 3
    assert abs(x_per_unit / y_per_unit - 1.0) <= _RATIO_TOLERANCE, (
        f"the two readings disagree on the control: {angle:.2f}° against a "
        f"ratio of {x_per_unit / y_per_unit:.4f}"
    )


def test_the_measurement_can_see_a_tilted_diagonal() -> None:
    """Sabotage, kept in the suite: an unequal plot has to read as unequal.

    A reading hard-wired to 45 -- a parse that silently finds nothing and a
    ``best`` that stays at its initial value, say -- would pass every other test
    in this file. So here is a plot drawn exactly as the defect drew it: one
    unit of x worth 800 px and one unit of y worth 600, both axes labelled
    0 to 1. The y = x line across it is at 36.87° and the two scales differ by
    a third, and both readings have to say so.
    """
    width, height, left, top = 800.0, 600.0, 0.0, 0.0
    ticks = [0.0, 0.25, 0.5, 0.75, 1.0]
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="900" height="700">']
    parts.append(
        f'<line x1="{left}" y1="{top + height}" x2="{left + width}" y2="{top}" stroke="#000"/>'
    )
    for t in ticks:
        parts.append(f'<text x="{left + t * width:.1f}" y="{top + height + 20:.1f}">{t}</text>')
        parts.append(f'<text x="{left - 10:.1f}" y="{top + (1 - t) * height:.1f}">{t}</text>')
    parts.append("</svg>")
    svg = "".join(parts)

    angle, length = _diagonal_reading(svg)
    assert length > 0.0, "the sabotage drew a diagonal and the reading missed it"
    assert abs(angle - math.degrees(math.atan2(height, width))) < 0.05, (
        f"a {width:.0f} x {height:.0f} plot reads as {angle:.2f}°, not the 36.87° it is drawn at"
    )
    assert abs(angle - 45.0) > 1.0, "the angle reading answers 45 no matter what"

    x_per_unit, y_per_unit, n_ticks = _ticks_reading(svg)
    assert n_ticks == len(ticks)
    assert abs(x_per_unit - width) < 0.5 and abs(y_per_unit - height) < 0.5
    assert abs(x_per_unit / y_per_unit - 1.0) > _RATIO_TOLERANCE, (
        "the pixels-per-unit reading answers 1.0 no matter what"
    )


@pytest.mark.slow
@pytest.mark.parametrize("figure", SHARED_UNIT_FIGURES, ids=lambda f: f.kind)
def test_shared_unit_axes_are_drawn_at_one_scale(figure: SharedUnitFigure) -> None:
    """Render each member of the class and measure what it actually drew."""
    _assert_equal_scales(figure, _render(figure), "rendered")


@pytest.mark.parametrize(
    "figure",
    [f for f in SHARED_UNIT_FIGURES if f.committed],
    ids=lambda f: f.kind,
)
def test_the_committed_example_is_drawn_at_one_scale(figure: SharedUnitFigure) -> None:
    """And measure the bytes that ship, which is what a reader actually sees.

    The generator and the exported example are two different artifacts: fixing
    the first and forgetting to re-export the second is how 64 of these files
    drifted once already (see ``test_committed_examples``). This lane is also
    the fast one -- it reads a file instead of rendering 167 figures' worth of
    numpy -- so the defect is caught in the default run, not only under
    ``-m slow``.
    """
    path = EXAMPLES_DIR / f"{figure.kind}.svg"
    assert path.exists(), f"{path} is missing"
    _assert_equal_scales(figure, path.read_text(encoding="utf-8"), "committed")


def test_the_registry_covers_every_generator_that_claims_the_invariant() -> None:
    """A new figure that names the 45° line has to be measured, not just say it.

    The registry above is a judgement about data, so nothing can derive it. What
    *can* be derived is the opposite risk: a generator whose source talks about
    a 45-degree line, a square plot or equal pixels per unit, and that nothing
    in this file ever measures. That is precisely the state ``liftgain``,
    ``ppplot`` and ``qqplot`` were in -- the claim in the comment, no reading
    anywhere -- and it is the state this test refuses to allow again.
    """
    claim = re.compile(r"45\s?°|45[- ]degree|equal pixels per unit", re.I)
    registered = {f.kind for f in SHARED_UNIT_FIGURES} | set(_NOT_MEMBERS)
    unmeasured = []
    for script in sorted(SCRIPTS_DIR.glob("make_*.py")):
        kind = script.stem[len("make_") :]
        if kind in registered:
            continue
        if claim.search(script.read_text(encoding="utf-8")):
            unmeasured.append(kind)
    assert not unmeasured, (
        "these generators claim a 45-degree reference or equal scales and "
        "nothing measures them: " + ", ".join(unmeasured) + ". Add each to "
        "SHARED_UNIT_FIGURES, or to _NOT_MEMBERS with the reason its two axes "
        "do not share a unit."
    )


def test_the_not_members_list_stays_honest() -> None:
    """An exemption has to name a figure that exists, and say why."""
    for kind, reason in _NOT_MEMBERS.items():
        assert (SCRIPTS_DIR / f"make_{kind}.py").exists(), (
            f"_NOT_MEMBERS names {kind}, which has no generator"
        )
        assert len(reason) > 20, f"_NOT_MEMBERS[{kind}] does not say why"
