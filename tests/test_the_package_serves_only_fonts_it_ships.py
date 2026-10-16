"""
The faces this package *offers* and the faces its wheel *carries* are one set.

They were two sets at 2.6.0. ``pyproject.toml`` narrowed the font package-data
to drop Roboto Serif -- 12.2 MB of an 18.6 MB wheel, for a family no generator
sets -- while ``fonts.py`` went on listing ``serif`` and ``serif_italic`` among
the faces it offers. The built wheel had eight faces. The module offered ten.

What made that invisible is an asymmetry no local check can see past: the
source tree's ``assets/fonts/`` holds every face regardless of what the wheel
is built to contain, so every font path passes from a checkout by
construction. The gap could only appear downstream, in an installed copy, and
it did -- as ``FileNotFoundError: RobotoSerif-Variable.woff2`` in
``sprezzature-maps``' CI: a filename, naming neither the face that asked for it
nor the fact that the absence was a decision rather than an accident.

The serif ships again, and that is a typography decision rather than a
packaging one: the suite sets three Roboto -- sans, serif, mono -- and a rule
that holds only where the source tree is checked out is not a rule. The 12.2 MB
is the price, paid knowingly.

Which leaves these tests to hold the invariant that was missing the whole time,
and would have caught the split whichever way it was resolved: **every face
``fonts.OFFERED_FACES`` names must match a package-data glob**. They read those
globs out of ``pyproject.toml`` rather than looking at the directory, because
the directory is exactly what cannot tell the difference.

Author
------
Warith HARCHAOUI <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import fnmatch
from pathlib import Path

import pytest

# `tomllib` is stdlib only from 3.11 and this package supports 3.10, where a
# bare import fails collection of the whole file. `tomli` is the same parser
# under its pre-stdlib name, declared in the `dev` extra for 3.10 alone -- the
# pattern `tests/test_linter_is_not_blind.py` already uses to read this same
# file. A regex would do for one value; what this needs is a nested table.
try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 only
    import tomli as tomllib

from sprezzature_figures import fonts

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"

#: The package-data key the font files ship under -- see pyproject's
#: ``[tool.setuptools.package-dir]``, which maps ``assets/fonts`` to this name.
_FONTS_PACKAGE = "sprezzature_figures_fonts"


def _packaged_font_globs() -> list[str]:
    """The filename globs pyproject tells setuptools to put in the wheel."""
    config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    package_data = config["tool"]["setuptools"]["package-data"]
    assert _FONTS_PACKAGE in package_data, (
        f"pyproject has no package-data for {_FONTS_PACKAGE!r}; if the fonts moved, "
        "this test moved with them"
    )
    return list(package_data[_FONTS_PACKAGE])


def _ships(filename: str) -> bool:
    return any(fnmatch.fnmatch(filename, pattern) for pattern in _packaged_font_globs())


def test_the_wheel_ships_every_face_the_module_offers() -> None:
    """The invariant, stated once.

    Both files per face, not either: a face whose TTF ships without its WOFF2
    is useless to the embed path, and one whose WOFF2 ships without its TTF is
    useless to resvg. A half-shipped face is a missing face.

    This is the test that would have caught 2.6.0 -- ``_FACES`` had ten
    entries, the globs matched eight, and nothing anywhere compared the two.
    """
    unshipped = sorted(
        key
        for key in fonts.OFFERED_FACES
        if not (_ships(fonts._FACES[key]["ttf"]) and _ships(fonts._FACES[key]["woff2"]))
    )
    assert not unshipped, (
        f"fonts.py offers {unshipped} but pyproject's package-data globs leave them out of "
        "the wheel; a source checkout cannot see the difference, so a consumer finds it"
    )


def test_offered_faces_is_the_whole_face_table() -> None:
    """No private side door: a key added to ``_FACES`` is offered, and therefore
    has to ship, rather than existing in a third unexamined category."""
    assert set(fonts.OFFERED_FACES) == set(fonts._FACES)


def test_roboto_serif_is_shipped_and_stays_shipped() -> None:
    """Pin the decision itself.

    Leaving the serif out again is a legitimate call -- it is most of the
    wheel. It should not be reachable by quietly editing a glob, because that
    is precisely how it happened the first time.
    """
    assert {"serif", "serif_italic"} <= set(fonts.OFFERED_FACES)
    for key in ("serif", "serif_italic"):
        face = fonts._FACES[key]
        assert _ships(face["ttf"]) and _ships(face["woff2"])


def test_every_bundled_font_family_ships_its_licence() -> None:
    """An OFL/GUST font may be redistributed only with its licence beside it.
    Adding Roboto Serif to the globs without ``OFL-RobotoSerif.txt`` would ship
    12.2 MB of font with no licence -- the same omission the Latin Modern faces
    once had, which is why the families are listed one at a time."""
    for licence in ("OFL-Roboto.txt", "OFL-RobotoMono.txt", "OFL-RobotoSerif.txt"):
        assert (fonts.FONTS_DIR / licence).is_file(), f"{licence} missing from assets/fonts"
        assert _ships(licence), f"{licence} is not packaged"


def test_the_default_svg_faces_are_all_offered() -> None:
    """Every generated figure embeds :data:`fonts.DEFAULT_SVG_FACES`, so an
    install missing one of them breaks every render, not just a serif."""
    assert set(fonts.DEFAULT_SVG_FACES) <= set(fonts.OFFERED_FACES)


def test_every_theme_embeds_only_offered_faces() -> None:
    """Same for the academic theme: Latin Modern ships, and must keep doing so."""
    for theme in fonts.THEMES:
        faces = set(fonts.svg_faces_for_theme(theme))
        assert faces <= set(fonts.OFFERED_FACES), f"theme {theme!r} embeds an unoffered face"


# --------------------------------------------------------------------------
# The consumer paths, exercised against a *damaged* font directory -- the one
# state in which offering and carrying can still come apart.
# --------------------------------------------------------------------------


@pytest.fixture
def damaged_fonts_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A font directory with every face except the serif.

    Files are copied rather than symlinked so nothing resolves back out to the
    checkout, and the module caches are cleared on the way in and out:
    ``_data_uri`` and ``embedded_font_css`` are ``functools.cache``d, so a
    base64 blob encoded from the real directory would otherwise survive the
    monkeypatch and answer for a file this directory does not have.
    """
    for key, face in fonts._FACES.items():
        if key in ("serif", "serif_italic"):
            continue
        for filename in (face["ttf"], face["woff2"]):
            (tmp_path / filename).write_bytes((fonts.FONTS_DIR / filename).read_bytes())
    monkeypatch.setattr(fonts, "FONTS_DIR", tmp_path)
    fonts._data_uri.cache_clear()
    fonts.embedded_font_css.cache_clear()
    yield tmp_path
    fonts._data_uri.cache_clear()
    fonts.embedded_font_css.cache_clear()


def test_the_web_app_links_no_font_the_install_lacks(damaged_fonts_dir: Path) -> None:
    """Studio mounts :data:`fonts.FONTS_DIR` as static files and injects
    :func:`fonts.web_font_faces_css` into every page's head, so the set of
    rules and the set of files on disk have to be the same set.

    The default used to be the whole face table, which under a wheel that
    excluded the serif meant four URLs that 404ed on every page. It now reads
    the directory, so a damaged install degrades to the faces it still has
    instead of linking ones it does not -- a dead ``@font-face`` source is a
    404 the browser swallows on its way to the next family in the stack, which
    is why this never announced itself.
    """
    css = fonts.web_font_faces_css("/sprezzature-fonts")
    linked = {
        line.split("/sprezzature-fonts/", 1)[1].split("'", 1)[0]
        for line in css.split("src:url('")[1:]
    }
    assert linked, "the web app would serve no fonts at all"
    missing = sorted(name for name in linked if not (damaged_fonts_dir / name).is_file())
    assert not missing, f"Studio links fonts this install does not have: {missing}"


def test_available_faces_reads_the_directory_not_the_table(damaged_fonts_dir: Path) -> None:
    """The docstring used to promise "normally all six" for a table of ten.
    What the function actually reports is what is on disk -- which is the whole
    point of having it, and the reason the web app now defers to it."""
    assert set(fonts.available_faces()) == set(fonts.OFFERED_FACES) - {"serif", "serif_italic"}


def test_a_face_this_install_lacks_fails_by_name_with_its_reason(
    damaged_fonts_dir: Path,
) -> None:
    """``FileNotFoundError: RobotoSerif-Variable.woff2`` is a true statement
    that explains nothing: it names a file, not the face that asked for it, and
    gives no sign of what to do next. That bare error is what sent the
    ``sprezzature-maps`` session chasing a packaging bug. The replacement names
    the face and says the install is incomplete, which it now always is -- the
    wheel carries every face offered, so there is no innocent reading left.
    """
    with pytest.raises(fonts.MissingFaceError) as excinfo:
        fonts.embedded_font_css(("serif",))
    message = str(excinfo.value)
    assert "serif" in message
    assert "RobotoSerif-Variable.woff2" in message
    assert "incomplete" in message.lower()
    # Still a FileNotFoundError, so callers that already catch that keep working.
    assert isinstance(excinfo.value, FileNotFoundError)
