#!/usr/bin/env python3
"""
notebook — the path a figure returns, drawing itself where that is wanted.

:func:`~sprezzature_figures.make_figure.make_figure` returns the path of
the file it wrote, and that is the right answer: a path can be opened,
moved, committed, served. In a notebook it is the *wrong* answer out
loud -- the cell prints ``PosixPath('chart.svg')`` and the figure the
caller asked for is somewhere on disk, unseen, two commands away.

So the return value is still a path -- the same class, the same methods,
``isinstance(result, Path)`` still true -- that additionally knows how to
show itself when a notebook asks. Nothing else changes: code that ignores
the display protocol never notices it is there.

Why not return an image object
------------------------------
Because then the path would be gone, and with it every caller that
writes ``make_figure(...).read_text()`` or passes the result to
``shutil.move``. A richer return type that breaks the simple one is not
richer. This is the other way round: a path first, a picture second.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

__all__ = ["FigurePath"]

#: Beyond this, an inlined SVG stops being a convenience. A figure that
#: embeds its own fonts runs to a few hundred kilobytes, and twenty of
#: them in one notebook is a file nobody can open. Past the cap the cell
#: shows the path and says why.
_INLINE_LIMIT = 4 * 1024 * 1024

#: The concrete Path class this platform hands out. Subclassing
#: ``pathlib.Path`` itself only became legal in 3.12; subclassing the
#: concrete one, and carrying its ``_flavour`` over, works on every
#: version this package supports.
_ConcretePath = type(Path())


class FigurePath(_ConcretePath):  # type: ignore[misc,valid-type]
    """A ``Path`` that renders itself in a notebook cell.

    Behaves as a path everywhere else: ``exists()``, ``read_text()``,
    ``open()``, ``str()``, ``os.fspath()``, ``isinstance(p, Path)``.

    Examples
    --------
    >>> from pathlib import Path
    >>> p = FigurePath("chart.svg")
    >>> isinstance(p, Path)
    True
    >>> p.name
    'chart.svg'
    >>> p.with_suffix(".png").name
    'chart.png'
    """

    # Python 3.10 and 3.11 build a concrete path through ``_flavour``;
    # a subclass that does not carry it over raises on construction.
    _flavour = getattr(_ConcretePath, "_flavour", None)

    def _payload(self) -> bytes | None:
        """The file's bytes, or ``None`` when it is missing or too large."""
        try:
            if self.stat().st_size > _INLINE_LIMIT:
                return None
            return self.read_bytes()
        except OSError:
            return None

    def _repr_svg_(self) -> str | None:
        """The SVG itself, for a notebook that can draw one.

        Returned as source rather than as an ``<img>``: the figures carry
        their own hover tooltips and focus rings in CSS, and those only
        work when the markup is in the page.
        """
        if self.suffix.lower() != ".svg":
            return None
        payload = self._payload()
        if payload is None:
            return None
        return payload.decode("utf-8", errors="replace")

    def _repr_png_(self) -> bytes | None:
        """The PNG bytes, for a figure rendered as a raster."""
        if self.suffix.lower() != ".png":
            return None
        return self._payload()

    def _repr_html_(self) -> str | None:
        """A fallback for the formats a notebook has no native slot for.

        Only used for the rasters that are neither SVG nor PNG; the two
        common cases are handled above, where the richer protocol gives a
        cleaner result.
        """
        suffix = self.suffix.lower()
        if suffix in (".svg", ".png"):
            return None
        media = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }.get(suffix)
        if media is None:
            return None
        payload = self._payload()
        if payload is None:
            return None
        encoded = base64.b64encode(payload).decode("ascii")
        return f'<img src="data:{media};base64,{encoded}" alt="{self.name}" style="max-width:100%">'


def as_figure_path(path: Any) -> FigurePath:
    """`path`, as the self-displaying path a caller should get back.

    Parameters
    ----------
    path : Any
        Anything ``Path()`` accepts.

    Returns
    -------
    FigurePath
        The same location, resolved, able to show itself in a notebook.
        Falls back to the plain concrete path if this interpreter will
        not let the subclass be built, so a display convenience can never
        be the reason a render fails.

    Examples
    --------
    >>> as_figure_path("chart.svg").name
    'chart.svg'
    """
    try:
        return FigurePath(path)
    except Exception:  # pragma: no cover - defensive, see docstring
        return Path(path)  # type: ignore[return-value]
