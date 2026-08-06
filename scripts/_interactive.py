"""
_interactive — the interactivity MODE layer shared by the make_* generators.

A figure can ship in one of three interactivity *modes*, and the choice is a
plain argument on the generator (default ``"self-contained"``):

* ``"self-contained"`` — the SVG carries its own fullscreen button and the
  script that wires it. Opened directly, served via ``<object>`` or inlined, the
  figure is fully usable on its own, with no page JavaScript. This is the
  default because the SVG is the deliverable.
* ``"external"`` — the SVG ships *without* an internal button; a page-level
  module (``figure-fullscreen.js``) supplies the button and a rich tooltip and
  drives fullscreen for a whole dashboard. The internal layer stands down so the
  two never duplicate.
* ``"static"`` — no interactivity at all, only the responsive ``viewBox`` that
  :func:`_svg.svg_open` already gives. For print or plain ``<img>`` embedding.

This module owns the *only* piece that is identical across figures: the
fullscreen wiring (a generic script, no visible chrome of its own). The
figure-specific hit regions and tooltips stay in each generator.

There is no on-canvas button — the whole figure is the hit target. A
``<img>``-embedded SVG never runs the ``<script>`` at all (browsers don't
execute scripts inside `<img>`-referenced SVGs), so nothing changes for
thumbnails; the script only ever runs once the SVG is a live document.

The module is **stdlib-only** (no imports) so it loads wherever the generators
do. Composes with :func:`_svg.svg_open` (the responsive, accessible root) and
mirrors the contract in ``sprezzature-ui/assets/components/figure-fullscreen.html``.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

#: The three supported interactivity modes (see the module docstring).
MODES = ("self-contained", "external", "static")

#: Generic fullscreen script, identical for every figure. No on-canvas icon —
#: the whole figure is the hit target, so it stays clean at thumbnail size.
#: Stands down inside a page-module-managed card (``[data-fs-target]``) and
#: never runs at all inside an ``<img>``-embedded SVG (browsers don't execute
#: scripts there).
#:
#: Three contexts, told apart by ``window.frameElement``:
#:
#: * **Gallery card** (embedded as a live ``<object>``, ``window.parent`` is
#:   the host page, not the lightbox's own object): a click anywhere on the
#:   figure can never bubble to the host page — ``<object>`` is a real,
#:   isolated document. So a click posts a message instead; ``lightbox.js`` in
#:   the web repo opens the modal on receipt. This keeps the card's own
#:   ``pointer-events:auto`` (native hover/``<title>`` tooltips stay live).
#: * **Lightbox's own enlarged object** (``data-lb-obj``): the figure is
#:   already shown at modal size, so a click on it does nothing extra.
#: * **Standalone** (opened as its own file/tab, or inlined outside the
#:   gallery — no ``frameElement`` at all): there is no host page to hand off
#:   to, so a click (or Enter/Space once focused) toggles the browser's own
#:   Fullscreen API directly on the SVG.
_FS_SCRIPT = (
    "(function(){"
    "var me=document.currentScript,svg=me.ownerSVGElement||me.parentNode;"
    # A page module owns this figure (dashboard): let it drive; do nothing here.
    "if(svg.closest&&svg.closest('[data-fs-target]'))return;"
    "var fe=null;try{fe=window.frameElement}catch(err){}"
    "if(fe&&fe.hasAttribute('data-lb-obj'))return;"      # already full-size in the lightbox
    "if(fe&&window.parent!==window){"
    "svg.addEventListener('click',function(){"
    "window.parent.postMessage({szFig:1,type:'open-fullscreen'},'*');"
    "});"
    "return;"
    "}"
    "var req=svg.requestFullscreen||svg.webkitRequestFullscreen;"
    "if(!req)return;"
    "var t=function(){var f=document.fullscreenElement||document.webkitFullscreenElement;"
    "if(f===svg)(document.exitFullscreen||document.webkitExitFullscreen).call(document);"
    "else req.call(svg);};"
    "svg.style.cursor='pointer';"
    "svg.setAttribute('tabindex','0');"
    "svg.addEventListener('click',t);"
    "svg.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();t();}});"
    "})();"
)


def fullscreen_control(
    width: float,
    height: float,
    mode: str = "self-contained",
    *,
    inset: float = 14.0,
) -> str:
    """Return the fullscreen wiring script for a figure, per interactivity mode.

    Append the result just before the closing ``</svg>`` of a generator's
    document. In ``"self-contained"`` mode it is the generic wiring script
    (see :data:`_FS_SCRIPT`) — no on-canvas button, the whole figure is the
    hit target. In ``"external"`` and ``"static"`` modes it is the empty
    string, so nothing ships.

    Parameters
    ----------
    width, height : float
        The SVG canvas size. Unused now that there is no button to place, but
        kept in the signature so the ~90 existing call sites (and any future
        placement need) stay source-compatible.
    mode : str, optional
        One of :data:`MODES`. Defaults to ``"self-contained"``.
    inset : float, optional
        Unused now that there is no button to place; kept for the same
        call-site-compatibility reason as ``width``/``height``.

    Returns
    -------
    str
        The ``<script>`` fragment, or ``""`` for the non-self-contained modes.

    Raises
    ------
    ValueError
        If ``mode`` is not one of :data:`MODES`.

    Examples
    --------
    >>> fullscreen_control(800, 600, "static")
    ''
    >>> fullscreen_control(800, 600, "external")
    ''
    >>> "<script>" in fullscreen_control(800, 600)
    True
    """
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
    # External mode defers to the page module; static ships no interactivity.
    if mode != "self-contained":
        return ""
    _ = width, height, inset  # kept for call-site compatibility; see docstring.
    return f'<script><![CDATA[{_FS_SCRIPT}]]></script>'


def hover_isolate_css(class_name: str, count: int, *, dim: float = 0.35) -> str:
    """Return the "hover one mark, dim the rest" CSS block shared by figures
    with N repeated marks (bars, bands, arcs, nodes, edges, ...).

    Every hand-authored generator with a small multiple of marks (one per
    category/series/node) wants the same interaction: hovering or focusing
    *any* mark dims all the others so the hovered one reads clearly. Rather
    than every generator hand-writing this CSS block (it was drifting
    slightly differently across files), this is the one shared source.

    Expects each mark to carry both a shared class (``class_name``) and an
    index-suffixed class (``f"{class_name}-{i}"`` for ``i`` in
    ``range(count)``) — e.g. ``class="band band-2"`` for the third band. The
    figure-specific parts (the marks themselves, tooltips, colors) stay in
    the generator; only this interaction pattern is shared.

    Parameters
    ----------
    class_name : str
        The shared class every mark carries (e.g. ``"band"``, ``"node"``).
    count : int
        How many marks there are (indices ``0..count-1``).
    dim : float, optional
        Opacity applied to non-hovered marks while any mark is hovered/focused
        (default ``0.35``).

    Returns
    -------
    str
        A ``<style>``-ready CSS string (no surrounding ``<style>`` tags).

    Examples
    --------
    >>> css = hover_isolate_css("band", 3)
    >>> ".band{transition:opacity .15s ease;}" in css
    True
    >>> "svg:has(.band-2:hover,.band-2:focus) .band-2{opacity:1;}" in css
    True
    """
    per_mark = "".join(
        f"svg:has(.{class_name}-{i}:hover,.{class_name}-{i}:focus) .{class_name}-{i}{{opacity:1;}}"
        for i in range(count)
    )
    return (
        f".{class_name}{{transition:opacity .15s ease;}}"
        f"svg:hover .{class_name},svg:focus-within .{class_name}{{opacity:{dim};}}"
        f"{per_mark}"
        "@media (prefers-reduced-motion: reduce){"
        f".{class_name}{{transition:none;}}"
        "}"
    )
