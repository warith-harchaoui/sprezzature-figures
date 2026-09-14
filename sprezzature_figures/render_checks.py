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

_SVG_NS = "{http://www.w3.org/2000/svg}"

#: Mean glyph advance as a fraction of the font size, for the house sans
#: (Roboto). Measured across mixed-case Latin text; digits and uppercase run
#: wider, lowercase narrower. Under-estimating would invent collisions, so
#: the value sits at the low end of the observed range and the overlap test
#: additionally requires a real, visible overlap before reporting.
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
    """

    check: str
    message: str
    detail: str = ""

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return f"[{self.check}] {self.message}" + (f" ({self.detail})" if self.detail else "")


@dataclass(frozen=True)
class _Label:
    """A text element reduced to what a collision test needs."""

    text: str
    x: float
    y: float
    size: float
    anchor: str
    rotated: bool

    @property
    def width(self) -> float:
        return len(self.text) * self.size * _GLYPH_WIDTH_RATIO

    @property
    def box(self) -> tuple[float, float]:
        """Horizontal extent, honouring ``text-anchor``."""
        if self.anchor == "middle":
            return self.x - self.width / 2, self.x + self.width / 2
        if self.anchor == "end":
            return self.x - self.width, self.x
        return self.x, self.x + self.width


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
    node: ET.Element | None = element
    while node is not None:
        size = node.get("font-size")
        if size:
            return _float(re.sub(r"[^\d.]", "", size), 12.0)
        node = ancestors.get(node)
    return 12.0


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
    node = element
    while node is not None:
        transform = node.get("transform") or ""
        if transform:
            if _AUTRE_TRANSFORM.search(transform) or (
                _ROTATE_SEUL.search(transform) and not _ROTATE_AUTOUR.search(transform)
            ):
                calculable = False
            for tx, ty in _TRANSLATE.findall(transform):
                dx += float(tx)
                dy += float(ty or 0.0)
        node = ancestors.get(node)
    return dx, dy, calculable


def _text_labels(root: ET.Element) -> list[_Label]:
    """Every visible ``<text>`` of the figure, with its geometry.

    Hidden text is skipped: hover tooltips are stacked on purpose and are
    never on screen at the same time.
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
        node: ET.Element | None = element
        while node is not None:
            if "rotate" in (node.get("transform") or ""):
                rotated = True
                break
            node = ancestors.get(node)
        dx, dy, calculable = _decalage(element, ancestors)
        if not calculable:
            continue
        labels.append(
            _Label(
                text=contenu,
                x=_float(element.get("x")) + dx,
                y=_float(element.get("y")) + dy,
                size=_inherited_size(element, ancestors),
                anchor=(element.get("text-anchor") or "start").strip(),
                rotated=rotated,
            )
        )
    return labels


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

    The vertical extent of a label is derived from its font size around its
    baseline (most of a Latin glyph sits above it). Rotated labels are
    skipped rather than approximated: a generator that rotates its ticks has
    already solved the crowding, and guessing the footprint of rotated text
    would report collisions that do not exist.
    """
    droits = [label for label in labels if not label.rotated]
    findings: list[RenderFinding] = []
    for i, gauche in enumerate(droits):
        g_x1, g_x2 = gauche.box
        g_y1, g_y2 = gauche.y - gauche.size * 0.8, gauche.y + gauche.size * 0.2
        for droite in droits[i + 1:]:
            d_x1, d_x2 = droite.box
            recouvrement_x = min(g_x2, d_x2) - max(g_x1, d_x1)
            if recouvrement_x <= _OVERLAP_TOLERANCE_PX:
                continue
            d_y1, d_y2 = droite.y - droite.size * 0.8, droite.y + droite.size * 0.2
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

    labels = _text_labels(root)
    width, height = _canvas(root)

    findings: list[RenderFinding] = []
    findings += _check_accessible_names(root)
    findings += _check_inside_canvas(labels, width, height)
    findings += _check_overlaps(labels)
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
