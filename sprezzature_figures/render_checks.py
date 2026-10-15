"""Deterministic checks on a rendered figure, for callers who have no eyes.

WHY THIS EXISTS. The Ralph Eyeball Loop answers "does this render actually
read?" by showing the PNG to a vision model. That answer is only available
where such a model is available. A service that has a text-only LLM, or no
model at all, still needs to ship figures that are legible, and it cannot
rely on someone looking at each one.

So this module asks the same questions the eyeball asks, but from the SVG
source alone, and answers them the same way every time:

  * do axis labels collide with each other?
  * does any text run off the canvas?
  * did a generator's DEMO chrome ("Region", "Quarterly figures") survive
    into a real render?
  * is the figure actually dark when dark mode was asked for, or is there a
    light card left in the middle of it?
  * is the caller's title on the figure?
  * is there an accessible title and description for a screen reader?

None of this replaces a human or a vision model on questions of taste. It
replaces them on questions of FACT, which is most of what goes wrong: the
failures seen in production were overlapping tick labels, a leftover
template title, and a white panel on a dark page. Every one of those is
decidable from the markup.

Usage::

    from sprezzature_figures import check_render, make_figure

    path = make_figure("bar", rows, out="chart.svg", dark=True, title="CA par client")
    findings = check_render(path.read_text(), dark=True, expected_title="CA par client")
    assert not findings, findings

Text width is ESTIMATED, since the actual glyph metrics live in the embedded
font. The estimate is deliberately conservative (see ``_GLYPH_WIDTH_RATIO``):
this module reports a collision when two labels are comfortably overlapping,
not when they are merely close, so that a passing check means something and
a failing one is worth acting on.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

__all__ = ["RenderFinding", "check_render"]


def _text_width(text: str, size: float) -> float:
    """
    Rendered width of `text` at `size`, in pixels.

    Measured with ``scripts/_textfit.text_width`` — the same calibrated
    per-character table the generators lay out with, so a string the generator
    fitted cannot be reported here as overflowing. That agreement is the whole
    point: a checker that measures differently from the thing it checks
    invents failures, which is exactly what a flat ratio did.

    Falls back to the flat ratio when the generators' helper is not importable
    (this module must work against an SVG from anywhere, not only one this
    package rendered).
    """
    try:
        from ._textfit_bridge import text_width
    except Exception:  # pragma: no cover - exercised only without scripts/
        return len(text) * size * _GLYPH_WIDTH_RATIO
    return float(text_width(text, size))


_SVG_NS = "{http://www.w3.org/2000/svg}"

#: Fallback mean glyph advance as a fraction of the font size, used only when
#: ``scripts/_textfit.py`` cannot be imported. A flat ratio is a poor measure:
#: at 0.52 it made "The North brings in nearly four times what the West does"
#: 757 px wide when Roboto renders it at 640, and reported the demo bar chart
#: as overflowing a canvas it fits with 65 px to spare.
_GLYPH_WIDTH_RATIO = 0.52

#: Two labels whose estimated boxes overlap by less than this many pixels are
#: not reported: at that scale the estimate itself is the uncertainty.
_OVERLAP_TOLERANCE_PX = 2.0

#: Baselines within this distance count as the same row of labels. Tick
#: labels on one axis share a baseline exactly; the tolerance absorbs the
#: sub-pixel rounding generators apply.
_SAME_ROW_PX = 2.0

#: Chrome the generators write for their own demo data. Any of these strings
#: in a render means a caller's real data is sitting under a label describing
#: someone else's example. The list holds the ones actually met in the wild;
#: it is a tripwire, not an exhaustive grammar.
_PLACEHOLDER_TEXT = (
    "Quarterly figures",
    "Share of visits by source",
    "thousands of EUR",
    "Lorem ipsum",
    "chiffres trimestriels",
)

#: Colours the house uses for a LIGHT canvas. None of them may survive a
#: dark render: ink that stayed dark is unreadable, a white or light panel is
#: a card of daylight in the middle of a dark page.
_LIGHT_INK = "#1D1D1F"
_LIGHT_SECONDARY = "#6E6E73"
_LIGHT_PANEL = "#F5F5F7"
_WHITE = "#FFFFFF"


@dataclass(frozen=True)
class RenderFinding:
    """One defect found in a rendered figure.

    Attributes
    ----------
    check
        Stable identifier of the rule that fired, e.g. ``"labels_overlap"``.
        Callers filter on this; the message is for humans.
    message
        What is wrong, in terms of the figure rather than of the markup.
    detail
        The offending fragment (label text, colour, coordinates), so the
        message can be acted on without re-deriving it.
    severity
        ``"error"`` when the figure is wrong whoever drew it and whatever it
        is for; ``"warning"`` when it is wrong under this house's charter, or
        wrong unless the author had a reason. A gate that blocks on both is a
        gate people switch off, so the two are separated at the source and the
        caller decides which it refuses to ship.
    """

    check: str
    message: str
    detail: str = ""
    severity: str = "error"

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return f"[{self.check}] {self.message}" + (f" ({self.detail})" if self.detail else "")


#: Glyphs whose ink goes below the baseline, in the fonts this house ships
#: (Roboto) and in anything close enough to them. ``Q`` is here for its tail
#: and ``Ç`` for its cedilla; the brackets and the slash drop below too.
_DESCENDEURS = frozenset("gjpqyQÇç,;()[]{}/\\|@_µß§")

#: Glyphs that stop at the x-height. A label made only of these -- "casa",
#: "sans" -- is half the height a cap or a digit would be, and treating it as
#: full height is how a caption one line below a legend gets reported as
#: colliding with it.
_HAUTEUR_X = frozenset("acemnorsuvwxzœ.,·-–—_\u2009 '\u2019\"")

#: Capitals carrying an accent: their mark sits above the cap height, high
#: enough to reach into the descenders of the line above.
_ACCENTS_HAUTS = frozenset("ÀÂÄÁÃÅÈÉÊËÌÍÎÏÒÓÔÕÖÙÚÛÜÝŸÑ")

#: Em fractions of ink above the baseline: an accented capital, a cap or
#: ascender, and x-height-only text. Roboto's cap height is 0.711 em and its
#: ascender 0.75; 0.73 covers both without inventing the 0.8 the first
#: version used everywhere.
_HAUT_ACCENT, _HAUT_CAP, _HAUT_X = 0.93, 0.73, 0.53

#: Em fraction of ink below the baseline, for text that has a descender.
#: Text that has none -- "63%", "00:00", "TOTAL" -- has exactly zero, and
#: that is not a detail: at a 150 px display figure, a flat 0.2 em invents
#: thirty pixels of ink that was never drawn.
_BAS_DESCENDEUR = 0.21

#: Where ``dominant-baseline`` puts the baseline, as an em fraction to add to
#: ``y``. Unlisted values (``alphabetic``, ``ideographic``, absent) leave the
#: baseline at ``y``. 422 text elements of this house's own catalogue carry
#: one of these, so reading ``y`` as the baseline put every one of them a
#: third of a line too high.
_LIGNE_DE_BASE = {"middle": 0.27, "central": 0.34, "hanging": 0.72, "text-before-edge": 0.75}


def _extension_verticale(text: str, size: float) -> tuple[float, float]:
    """Ink above and below the baseline of `text` at `size`, in pixels.

    A box hung from the baseline by a fixed fraction of the font size is
    wrong in both directions at once, and the error grows with the type:
    it adds a descender to text that has none, and gives x-height text the
    height of a capital.
    """
    if _ACCENTS_HAUTS & set(text):
        haut = _HAUT_ACCENT
    elif set(text) <= _HAUTEUR_X:
        haut = _HAUT_X
    else:
        haut = _HAUT_CAP
    bas = _BAS_DESCENDEUR if _DESCENDEURS & set(text) else 0.0
    return haut * size, bas * size


@dataclass(frozen=True)
class _Label:
    """A text element reduced to what a collision test needs.

    ``y`` is the BASELINE, already resolved from ``dominant-baseline``: the
    attribute on the element is an alignment point, and for the two values
    this house writes most it is the middle of the text, not its baseline.
    """

    text: str
    x: float
    y: float
    size: float
    anchor: str
    rotated: bool

    @property
    def width(self) -> float:
        return _text_width(self.text, self.size)

    @property
    def box(self) -> tuple[float, float]:
        """Horizontal extent, honouring ``text-anchor``."""
        if self.anchor == "middle":
            return self.x - self.width / 2, self.x + self.width / 2
        if self.anchor == "end":
            return self.x - self.width, self.x
        return self.x, self.x + self.width

    @property
    def bande(self) -> tuple[float, float]:
        """Vertical extent of the ink, top first."""
        haut, bas = _extension_verticale(self.text, self.size)
        return self.y - haut, self.y + bas


#: A presentation property may be written as an attribute (``font-size="10"``)
#: or inside the style attribute (``style="font-size: 10px"``). SVG the house
#: writes uses attributes; SVG from matplotlib, Plotly and most exporters uses
#: the style string. Reading only the attribute saw nothing there and fell back
#: to a default, which put every label box in the wrong place -- so the checks
#: quietly passed figures that were plainly broken.
def _presentation(element: ET.Element, name: str) -> str | None:
    """Value of presentation property `name`, attribute or ``style:`` alike."""
    direct = element.get(name)
    if direct:
        return direct.strip()
    style = element.get("style")
    if not style:
        return None
    m = re.search(rf"(?:^|;)\s*{re.escape(name)}\s*:\s*([^;]+)", style)
    return m.group(1).strip() if m else None


def _inherited(element: ET.Element, ancestors: dict, name: str) -> str | None:
    """`name` as resolved on `element`, walking up to whoever sets it."""
    node: ET.Element | None = element
    while node is not None:
        value = _presentation(node, name)
        if value:
            return value
        node = ancestors.get(node)
    return None


def _float(value: str | None, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _inherited_size(element: ET.Element, ancestors: dict[ET.Element, ET.Element]) -> float:
    """Font size of an element, walking up to the nearest ancestor that sets one.

    Generators often set ``font-size`` once on a group and let the labels
    inherit it. Reading the attribute on the text element alone would then
    see nothing and fall back to a default that is wrong by a factor of two.
    """
    size = _inherited(element, ancestors, "font-size")
    if not size:
        return 12.0
    # "10px", "0.9em", "10" -- only the absolute form is a length we can use;
    # a relative unit needs the cascade, which is not reconstructible here.
    if size.endswith(("em", "ex", "rem", "%")):
        return 12.0
    return _float(re.sub(r"[^\d.]", "", size), 12.0) or 12.0


#: Déclarations CSS qui rendent un élément invisible au repos. Les
#: infobulles des figures maison sont dans ce cas : un groupe ``class="tip"``
#: avec ``opacity:0``, révélé au survol. Le texte qu'elles portent se
#: superpose évidemment aux autres, et c'est normal : personne ne le voit
#: sans y poser la souris. Le compter comme un chevauchement rendrait la
#: vérification inutilisable sur toutes les figures interactives.
_MASQUAGE_CSS = re.compile(r"opacity:\s*0(?![.\d])|display:\s*none|visibility:\s*hidden")


def _hidden_classes(root: ET.Element) -> set[str]:
    """Classes que la feuille de style de la figure masque au repos."""
    cachees: set[str] = set()
    for style in root.iter(f"{_SVG_NS}style"):
        css = "".join(style.itertext())
        for selecteur, corps in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
            if not _MASQUAGE_CSS.search(corps):
                continue
            cachees.update(re.findall(r"\.([\w-]+)", selecteur))
    return cachees


def _est_masque(element: ET.Element, cachees: set[str]) -> bool:
    classes = set((element.get("class") or "").split())
    if classes & cachees:
        return True
    if (element.get("opacity") or "").strip() == "0":
        return True
    return bool(_MASQUAGE_CSS.search(element.get("style") or ""))


_TRANSLATE = re.compile(r"translate\(\s*(-?[\d.]+)[ ,]+(-?[\d.]+)?\s*\)")
_ROTATE_AUTOUR = re.compile(r"rotate\(\s*-?[\d.]+[ ,]+(-?[\d.]+)[ ,]+(-?[\d.]+)\s*\)")
_ROTATE_SEUL = re.compile(r"rotate\(\s*-?[\d.]+\s*\)")
#: The angle of every rotate() in a transform, whatever form it takes.
_ROTATE_ANGLE = re.compile(r"rotate\(\s*(-?[\d.]+)")


def _tourne(transform: str) -> bool:
    """True when `transform` actually turns the text.

    ``rotate(-0 cx cy)`` is what matplotlib writes on every *unrotated* tick
    label. Treating the word "rotate" as proof of rotation excluded those
    labels from the collision test -- which is the one test they needed, since
    unrotated tick labels are exactly what runs into its neighbour. A zero
    angle is not a rotation.
    """
    return any(abs(float(a)) > 0.01 for a in _ROTATE_ANGLE.findall(transform))
_AUTRE_TRANSFORM = re.compile(r"\b(scale|matrix|skewX|skewY)\s*\(")


def _decalage(element: ET.Element, ancestors: dict) -> tuple:
    """Décalage absolu appliqué à un élément, et si on sait le calculer.

    La maison n'utilise que deux transformations : ``translate``, qui déplace
    d'un vecteur constant, et ``rotate(angle cx cy)``, qui tourne AUTOUR du
    point d'ancrage et ne le déplace donc pas. Les deux se composent sans
    effort. Tout le reste (``scale``, ``matrix``, rotation sans centre)
    déplacerait le point d'une manière qu'il faudrait vraiment calculer :
    dans ce cas on le dit, et l'appelant s'abstient plutôt que de deviner une
    position et d'inventer un défaut.
    """
    dx = dy = 0.0
    calculable = True
    # Optional: the walk ends when `ancestors.get` returns None at the root.
    node: ET.Element | None = element
    while node is not None:
        transform = node.get("transform") or ""
        if transform:
            if _AUTRE_TRANSFORM.search(transform) or (
                _tourne(transform)
                and _ROTATE_SEUL.search(transform)
                and not _ROTATE_AUTOUR.search(transform)
            ):
                calculable = False
            for tx, ty in _TRANSLATE.findall(transform):
                dx += float(tx)
                dy += float(ty or 0.0)
        node = ancestors.get(node)
    return dx, dy, calculable


def _text_labels(root: ET.Element) -> list[_Label]:
    """Every visible ``<text>`` of the figure, with its geometry, once each.

    Hidden text is skipped: hover tooltips are stacked on purpose and are
    never on screen at the same time.

    A label written twice at the same spot is returned once. Figures stack
    identical text on purpose -- a halo drawn under its own glyphs, a
    highlight layer that redraws the nodes of one branch over the base
    drawing so hovering can light them up. The reader sees one label, so
    every rule here must count one: the tree figure alone redraws its root
    card eleven times, and the collision test read that as fifty-five
    labels covering each other.
    """
    ancestors = {child: parent for parent in root.iter() for child in parent}
    cachees = _hidden_classes(root)
    labels: list[_Label] = []
    for element in root.iter(f"{_SVG_NS}text"):
        contenu = "".join(element.itertext()).strip()
        if not contenu:
            continue
        masque = False
        node: ET.Element | None = element
        while node is not None:
            if _est_masque(node, cachees):
                masque = True
                break
            node = ancestors.get(node)
        if masque:
            continue
        rotated = False
        # Re-walk from the element: `node` is already declared above, so this
        # second pass reuses it rather than redeclaring the same name and type.
        node = element
        while node is not None:
            if _tourne(node.get("transform") or ""):
                rotated = True
                break
            node = ancestors.get(node)
        dx, dy, calculable = _decalage(element, ancestors)
        if not calculable:
            continue
        size = _inherited_size(element, ancestors)
        aligne = (_inherited(element, ancestors, "dominant-baseline") or "").strip()
        labels.append(
            _Label(
                text=contenu,
                x=_float(element.get("x")) + dx,
                y=_float(element.get("y")) + dy + _LIGNE_DE_BASE.get(aligne, 0.0) * size,
                size=size,
                anchor=(_inherited(element, ancestors, "text-anchor") or "start"),
                rotated=rotated,
            )
        )
    vus: set[tuple] = set()
    uniques: list[_Label] = []
    for label in labels:
        # Rounded to the pixel: a halo offset by half a unit is the same
        # label, and no two distinct labels carrying the same string sit
        # within a pixel of each other.
        cle = (label.text, round(label.x), round(label.y))
        if cle in vus:
            continue
        vus.add(cle)
        uniques.append(label)
    return uniques


def _canvas(root: ET.Element) -> tuple[float, float]:
    view_box = (root.get("viewBox") or "").split()
    if len(view_box) == 4:
        return _float(view_box[2], 0.0), _float(view_box[3], 0.0)
    return _float(root.get("width"), 0.0), _float(root.get("height"), 0.0)


def _check_overlaps(labels: Sequence[_Label]) -> list[RenderFinding]:
    """Report labels whose boxes actually cover each other.

    The test is two-dimensional on purpose. A first version compared only
    labels sharing a baseline, and missed the case that matters most in
    practice: a title that grew one line longer in translation, coming down
    onto a legend placed at a fixed height. Those two never share a baseline
    exactly, and they overlap all the same.

    The vertical extent of a label is the ink the string actually puts on
    the canvas (see :func:`_extension_verticale`), not a fixed fraction of
    the font size: "63 %" set at 150 px has nothing below its baseline, and
    charging it thirty pixels of imaginary descender reported it as running
    into the caption underneath. Rotated labels are skipped rather than
    approximated: a generator that rotates its ticks has already solved the
    crowding, and guessing the footprint of rotated text would report
    collisions that do not exist.
    """
    droits = [label for label in labels if not label.rotated]
    findings: list[RenderFinding] = []
    for i, gauche in enumerate(droits):
        g_x1, g_x2 = gauche.box
        g_y1, g_y2 = gauche.bande
        for droite in droits[i + 1:]:
            d_x1, d_x2 = droite.box
            recouvrement_x = min(g_x2, d_x2) - max(g_x1, d_x1)
            if recouvrement_x <= _OVERLAP_TOLERANCE_PX:
                continue
            d_y1, d_y2 = droite.bande
            recouvrement_y = min(g_y2, d_y2) - max(g_y1, d_y1)
            if recouvrement_y <= _OVERLAP_TOLERANCE_PX:
                continue
            findings.append(
                RenderFinding(
                    "labels_overlap",
                    "two labels cover each other, so neither can be read",
                    f"{gauche.text!r} / {droite.text!r} overlap by "
                    f"~{recouvrement_x:.0f}x{recouvrement_y:.0f}px",
                )
            )
    return findings


def _check_inside_canvas(labels: Sequence[_Label], width: float, height: float) -> list[RenderFinding]:
    if not width or not height:
        return []
    findings: list[RenderFinding] = []
    for label in labels:
        debut, fin = label.box
        # Rotated text is anchored at a point and drawn along its own axis:
        # the horizontal extent computed above does not describe it.
        if label.rotated:
            dehors = not (-1 <= label.x <= width + 1) or not (-1 <= label.y <= height + 1)
        else:
            dehors = debut < -1 or fin > width + 1 or label.y < -1 or label.y > height + 1
        if dehors:
            findings.append(
                RenderFinding(
                    "text_outside_canvas",
                    "a label is drawn outside the canvas and will be clipped",
                    f"{label.text!r} at x={label.x:.0f} y={label.y:.0f} (canvas {width:.0f}x{height:.0f})",
                )
            )
    return findings


def _check_placeholders(
    labels: Sequence[_Label], forbidden: Iterable[str]
) -> list[RenderFinding]:
    interdits = tuple(_PLACEHOLDER_TEXT) + tuple(forbidden)
    findings: list[RenderFinding] = []
    for label in labels:
        for motif in interdits:
            if motif and motif.lower() in label.text.lower():
                findings.append(
                    RenderFinding(
                        "placeholder_text",
                        "demo chrome survived into a real render",
                        f"{label.text!r} contains {motif!r}",
                    )
                )
    return findings


def _check_dark(svg: str, root: ET.Element) -> list[RenderFinding]:
    """Verify that a render asked to be dark actually is."""
    findings: list[RenderFinding] = []
    width, height = _canvas(root)

    for rect in root.iter(f"{_SVG_NS}rect"):
        fill = (rect.get("fill") or "").upper()
        if fill not in (_WHITE, _LIGHT_PANEL):
            continue
        aire = _float(rect.get("width")) * _float(rect.get("height"))
        canevas = (width or 1) * (height or 1)
        # A small white rectangle is a legend swatch or a tooltip bubble and
        # belongs on a dark figure. A large one is a page of daylight.
        if aire >= 0.1 * canevas:
            findings.append(
                RenderFinding(
                    "light_surface_on_dark",
                    "a large light surface survived dark mode and reads as a light card",
                    f"rect {rect.get('width')}x{rect.get('height')} fill={fill}",
                )
            )

    for couleur, role in ((_LIGHT_INK, "primary ink"), (_LIGHT_SECONDARY, "secondary ink")):
        if f'"{couleur}"' in svg.upper() or f'"{couleur.lower()}"' in svg:
            findings.append(
                RenderFinding(
                    "light_mode_ink_on_dark",
                    f"{role} kept its light-canvas colour and will be unreadable on dark",
                    couleur,
                )
            )
    return findings


def _check_accessible_names(root: ET.Element) -> list[RenderFinding]:
    """Vérifie qu'un lecteur d'écran a un nom ET une description à annoncer.

    Le nom peut venir d'un ``<title>`` ou d'un ``aria-label`` sur la racine :
    les deux sont des noms accessibles valides, et le catalogue emploie les
    deux selon les figures. N'en accepter qu'un ferait échouer des figures
    correctes.
    """
    titre = root.find(f"{_SVG_NS}title")
    desc = root.find(f"{_SVG_NS}desc")
    nomme = (titre is not None and (titre.text or "").strip()) or bool(
        (root.get("aria-label") or "").strip() or (root.get("aria-labelledby") or "").strip()
    )
    findings: list[RenderFinding] = []
    if not nomme:
        findings.append(
            RenderFinding(
                "missing_accessible_title",
                "the figure has neither <title> nor aria-label, so a screen "
                "reader announces nothing",
            )
        )
    if desc is None or not (desc.text or "").strip():
        findings.append(
            RenderFinding(
                "missing_accessible_description",
                "the figure has no <desc>, so its content is unavailable without sight",
            )
        )
    return findings


#: Below this many pixels ON SCREEN, a data label is decoration rather than
#: information. The floor is applied to the DISPLAYED size, not the authored
#: one: a 10-unit label inside a 1600-wide viewBox shown at 800 is five pixels
#: tall, and the authored number says nothing about that.
_LEGIBLE_FLOOR_PX = 9.0
_ILLEGIBLE_FLOOR_PX = 7.0


def _display_scale(root: ET.Element) -> float:
    """How many screen pixels one user unit becomes, or 1.0 when unknowable."""
    view_box = (root.get("viewBox") or "").split()
    if len(view_box) != 4:
        return 1.0
    authored = _float(view_box[2], 0.0)
    largeur = (root.get("width") or "").strip()
    # A percentage width says the figure fills whatever box it lands in, which
    # is a promise about the container and not a size. Stripping the "%" read
    # width="100%" as a hundred pixels and declared every label in a 1400-unit
    # figure to be a seventh of a pixel tall.
    if not largeur or largeur.endswith("%"):
        return 1.0
    shown = _float(re.sub(r"[^\d.]", "", largeur), 0.0)
    if not authored or not shown:
        return 1.0
    return shown / authored


def _check_text_is_text(root: ET.Element, labels: Sequence[_Label]) -> list[RenderFinding]:
    """Refuse to pass a figure whose text was converted to outlines.

    matplotlib's default SVG writes every glyph as a path and references it
    with ``<use>``: the figure looks identical and contains no text at all.
    Every rule in this module then finds nothing to object to, and the caller
    reads that as a pass -- the one answer worse than a failure, because it is
    a failure wearing a pass. It is also a real defect in its own right: no
    screen reader, no search, no copy, no translation.
    """
    if labels:
        return []
    marques = sum(
        1
        for tag in ("path", "rect", "circle", "polygon", "line", "use")
        for _ in root.iter(f"{_SVG_NS}{tag}")
    )
    if marques < 5:
        return []  # not a figure: an icon, a logo, an empty canvas
    return [
        RenderFinding(
            "text_as_outlines",
            "the figure carries no readable text, so nothing here can be checked "
            "and no screen reader can read it",
            f"{marques} drawn elements, 0 <text>; export with live text "
            "(matplotlib: rcParams['svg.fonttype'] = 'none')",
        )
    ]


def _check_legible_size(
    labels: Sequence[_Label], scale: float
) -> list[RenderFinding]:
    """Report labels too small to read at the size the figure is shown."""
    findings: list[RenderFinding] = []
    for label in labels:
        shown = label.size * scale
        if shown >= _LEGIBLE_FLOOR_PX:
            continue
        findings.append(
            RenderFinding(
                "text_too_small",
                "a label is below the size at which text can be read",
                f"{label.text!r} renders at {shown:.1f}px"
                + (f" ({label.size:.0f} authored x {scale:.2f})" if scale != 1.0 else ""),
                severity="error" if shown < _ILLEGIBLE_FLOOR_PX else "warning",
            )
        )
    return findings


def _check_identical_ticks(labels: Sequence[_Label]) -> list[RenderFinding]:
    """Report a run of axis labels rounded until they read the same.

    Three neighbours printing "1,2" are three different numbers the formatter
    threw away: the axis now claims a constant where the data moves. Two in a
    row can be a legitimate repeat in a matrix, so the run has to be three.
    Only numeric labels qualify -- repeated category names are a design, not
    a rounding bug.
    """
    par_ligne: dict[int, list[_Label]] = {}
    for label in labels:
        if label.rotated or not any(c.isdigit() for c in label.text):
            continue
        par_ligne.setdefault(round(label.y / 1.5), []).append(label)

    findings: list[RenderFinding] = []
    for ligne in par_ligne.values():
        ligne.sort(key=lambda label: label.x)
        run = 1
        for i in range(1, len(ligne) + 1):
            meme = i < len(ligne) and ligne[i].text == ligne[i - 1].text
            if meme:
                run += 1
                continue
            if run >= 3:
                findings.append(
                    RenderFinding(
                        "identical_adjacent_labels",
                        "consecutive axis labels were rounded until they read the "
                        "same, so the axis hides the variation it should show",
                        f"{ligne[i - 1].text!r} x{run} in a row",
                    )
                )
            run = 1
    return findings


#: Endings a wrapped line may not take, because the eye has to jump to the next
#: line to finish a word or a phrase that was never meant to be split. The
#: French elisions are glued to the word that follows them by spelling; the
#: English pair is glued by sense.
_ORPHELINS_FR = re.compile(r"(?:^|\s)(?:[ldjcsntm]|qu|jusqu|lorsqu|puisqu)[\u2019']$", re.I)
_ORPHELINS_EN = re.compile(r"\b(?:of|to|in|on|for) the$", re.I)


def _check_line_end_orphans(root: ET.Element, ancestors: dict) -> list[RenderFinding]:
    """Report a wrapped line ending on a word welded to the next one.

    House charter, hence a warning rather than an error: a line ending in
    "l'" or in "of the" makes the reader finish the word on the line below.
    Only lines that have one below them are checked -- the last line of a
    block ends where the sentence does.
    """
    findings: list[RenderFinding] = []
    for text in root.iter(f"{_SVG_NS}text"):
        lignes = [
            "".join(tspan.itertext()).strip()
            for tspan in text.findall(f"{_SVG_NS}tspan")
            if tspan.get("x") is not None or tspan.get("dy") is not None
        ]
        for ligne in lignes[:-1]:
            if not ligne:
                continue
            if _ORPHELINS_FR.search(ligne) or _ORPHELINS_EN.search(ligne):
                findings.append(
                    RenderFinding(
                        "line_end_orphan",
                        "a wrapped line ends on a word welded to the next line, so "
                        "the reader has to jump to finish it",
                        repr(ligne[-40:]),
                        severity="warning",
                    )
                )
    return findings


_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def _luminance(couleur: str) -> float | None:
    """Relative luminance of a hex colour, per WCAG 2.x, or None if unreadable."""
    couleur = couleur.strip()
    if not _HEX.match(couleur):
        return None
    brut = couleur[1:]
    if len(brut) == 3:
        brut = "".join(c * 2 for c in brut)
    canaux = []
    for i in (0, 2, 4):
        v = int(brut[i : i + 2], 16) / 255
        canaux.append(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4)
    return 0.2126 * canaux[0] + 0.7152 * canaux[1] + 0.0722 * canaux[2]


def _contraste(avant: str, arriere: str) -> float | None:
    a, b = _luminance(avant), _luminance(arriere)
    if a is None or b is None:
        return None
    clair, sombre = max(a, b), min(a, b)
    return (clair + 0.05) / (sombre + 0.05)


def _fond(root: ET.Element) -> str | None:
    """The canvas colour: the fill of a rectangle that covers the figure."""
    width, height = _canvas(root)
    if not width or not height:
        return None
    for rect in root.iter(f"{_SVG_NS}rect"):
        if _float(rect.get("width")) >= width * 0.95 and _float(rect.get("height")) >= height * 0.95:
            fill = _presentation(rect, "fill")
            if fill and _HEX.match(fill):
                return fill
    return None


#: Shapes whose outline is written in attributes, so a point can be tested
#: against them exactly. ``path`` is deliberately absent: its ``d`` would have
#: to be walked, and a wrong answer there is worse than no answer.
_FORMES_PLEINES = ("rect", "circle", "ellipse", "polygon")


def _translucide(element: ET.Element, ancestors: dict) -> bool:
    """True when the paint of `element` is blended with what it covers."""
    for nom in ("opacity", "fill-opacity"):
        valeur = _inherited(element, ancestors, nom)
        if valeur is not None:
            try:
                if float(valeur) < 0.99:
                    return True
            except ValueError:
                return True
    return False


def _couvre(element: ET.Element, tag: str, dx: float, dy: float, x: float, y: float) -> bool:
    """True when the point (`x`, `y`) falls inside `element`.

    Exact for each shape rather than on its bounding box: the corner of the
    box around a pie-chart circle belongs to the canvas, not to the circle,
    and a label sitting there would be compared against the wrong colour.
    """
    if tag == "rect":
        gx, gy = _float(element.get("x")) + dx, _float(element.get("y")) + dy
        return gx <= x <= gx + _float(element.get("width")) and gy <= y <= gy + _float(element.get("height"))
    if tag == "circle":
        cx, cy = _float(element.get("cx")) + dx, _float(element.get("cy")) + dy
        return (x - cx) ** 2 + (y - cy) ** 2 <= _float(element.get("r")) ** 2
    if tag == "ellipse":
        cx, cy = _float(element.get("cx")) + dx, _float(element.get("cy")) + dy
        rx, ry = _float(element.get("rx")), _float(element.get("ry"))
        if not rx or not ry:
            return False
        return ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1
    sommets = [
        (float(a) + dx, float(b) + dy)
        for a, _, b in (p.partition(",") for p in (element.get("points") or "").split())
        if b
    ]
    if len(sommets) < 3:
        return False
    dedans = False
    for i, (ax, ay) in enumerate(sommets):
        bx, by = sommets[i - 1]
        if (ay > y) != (by > y) and x < ax + (y - ay) / (by - ay) * (bx - ax):
            dedans = not dedans
    return dedans


def _surface_sous(
    root: ET.Element, ancestors: dict, cachees: set[str], fond: str | None
) -> dict[ET.Element, str | None]:
    """The colour each ``<text>`` is drawn ON, or ``None`` when unknowable.

    A figure is painted in document order, so the surface under a label is
    the last visible shape that covers its anchor -- the canvas only when
    nothing else does. Reading the canvas instead was the whole trouble: a
    white count printed inside a dark bar is white on white against the
    canvas and perfectly legible in fact, and the rule that compared them
    fired on twenty-seven figures of this catalogue, every one of them
    correctly drawn.

    ``None`` means "do not judge this one". A filled ``<path>`` seen since
    the last known surface may be sitting on top -- pie slices, stream
    bands and sunburst arcs all are paths -- and so may a gradient or a
    translucent fill, whose colour under the glyph is not a value written
    anywhere in the markup. Abstaining is the one answer that cannot be
    wrong, and a linter that guesses here is a linter people switch off.
    """
    surfaces: dict[ET.Element, str | None] = {}
    empile: list[tuple[ET.Element, str, float, float, str | None]] = []
    for element in root.iter():
        tag = element.tag.split("}")[-1]
        if tag == "text":
            contenu = "".join(element.itertext()).strip()
            if not contenu:
                continue
            x, y, calculable = _decalage(element, ancestors)
            if not calculable:
                continue
            x += _float(element.get("x"))
            y += _float(element.get("y"))
            dessous, inconnu = fond, False
            for forme, forme_tag, fdx, fdy, couleur in empile:
                if forme_tag == "path":
                    inconnu = True
                elif _couvre(forme, forme_tag, fdx, fdy, x, y):
                    dessous, inconnu = couleur, couleur is None
            surfaces[element] = None if inconnu else dessous
            continue
        if tag not in _FORMES_PLEINES and tag != "path":
            continue
        fill = _inherited(element, ancestors, "fill")
        if not fill or fill == "none":
            continue
        masque = False
        node: ET.Element | None = element
        while node is not None:
            if _est_masque(node, cachees):
                masque = True
                break
            node = ancestors.get(node)
        if masque:
            continue
        dx, dy, calculable = _decalage(element, ancestors)
        if not calculable:
            continue
        couleur = fill if _HEX.match(fill) and not _translucide(element, ancestors) else None
        empile.append((element, tag, dx, dy, couleur))
    return surfaces


def _check_invisible_text(root: ET.Element, ancestors: dict, fond: str | None) -> list[RenderFinding]:
    """Report text drawn in the colour of the surface it sits on.

    Deliberately blunt: it fires only below 1.5:1, which is not "hard to
    read" but "not there". Full contrast grading -- the 4.5:1 of WCAG, the
    simulation of colour-vision deficiency -- belongs to
    ``sprezzature-colors``; what is decidable here is a label nobody can
    see at all.

    What the label sits on comes from :func:`_surface_sous`, which abstains
    whenever the markup does not say. The first version of this rule asked
    the canvas instead and was wrong twenty-seven times out of twenty-seven.
    """
    cachees = _hidden_classes(root)
    surfaces = _surface_sous(root, ancestors, cachees, fond)
    findings: list[RenderFinding] = []
    vus: set[tuple[str, str]] = set()
    for element, dessous in surfaces.items():
        if dessous is None:
            continue
        contenu = "".join(element.itertext()).strip()
        masque = False
        node: ET.Element | None = element
        while node is not None:
            if _est_masque(node, cachees):
                masque = True
                break
            node = ancestors.get(node)
        if masque:
            continue
        fill = _inherited(element, ancestors, "fill")
        if not fill or not _HEX.match(fill) or _translucide(element, ancestors):
            continue
        ratio = _contraste(fill, dessous)
        if ratio is None or ratio >= 1.5 or (fill, dessous) in vus:
            continue
        vus.add((fill, dessous))
        findings.append(
            RenderFinding(
                "text_invisible_on_background",
                "text is drawn in the colour of the surface behind it",
                f"{contenu[:40]!r} in {fill} on {dessous} (contrast {ratio:.2f}:1)",
            )
        )
    return findings


def check_render(
    svg: str,
    *,
    dark: bool = False,
    expected_title: str | None = None,
    forbidden_text: Sequence[str] = (),
) -> list[RenderFinding]:
    """Check a rendered SVG and return what is wrong with it, deterministically.

    An empty list means the figure passed every rule this module knows. It
    does NOT mean the figure is beautiful, or that the chart type suits the
    question: those are judgements, and this module makes none.

    Parameters
    ----------
    svg
        The rendered SVG source.
    dark
        ``True`` when the figure was rendered for a dark canvas. Adds the
        dark-mode rules: no light ink left, no large light surface.
    expected_title
        Title the caller asked for. Reported as missing if no text element
        carries it, which catches a generator that ignores the parameter.
    forbidden_text
        Extra strings that must not appear, on top of the known demo chrome.
        A caller that knows its own placeholders passes them here.

    Returns
    -------
    list of RenderFinding
        Ordered by rule, most structural first. Empty when nothing fired.
    """
    if not svg or not svg.strip():
        return [RenderFinding("empty_render", "the render is empty")]
    try:
        root = ET.fromstring(svg)
    except ET.ParseError as exc:
        return [RenderFinding("invalid_svg", "the render is not well-formed XML", str(exc))]

    ancestors = {child: parent for parent in root.iter() for child in parent}
    labels = _text_labels(root)
    width, height = _canvas(root)

    findings: list[RenderFinding] = []
    findings += _check_accessible_names(root)
    findings += _check_text_is_text(root, labels)
    findings += _check_inside_canvas(labels, width, height)
    findings += _check_overlaps(labels)
    findings += _check_legible_size(labels, _display_scale(root))
    findings += _check_identical_ticks(labels)
    findings += _check_line_end_orphans(root, ancestors)
    findings += _check_invisible_text(root, ancestors, _fond(root))
    findings += _check_placeholders(labels, forbidden_text)
    if dark:
        findings += _check_dark(svg, root)
    if expected_title:
        attendu = " ".join(expected_title.split()).lower()
        if not any(attendu in " ".join(label.text.split()).lower() for label in labels):
            findings.append(
                RenderFinding(
                    "title_ignored",
                    "the requested title is nowhere on the figure",
                    expected_title,
                )
            )
    return findings
