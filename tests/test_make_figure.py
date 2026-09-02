"""
Tests for the make_figure dispatcher, the function that looks up a chart
kind's name and calls its generator, and the list_kinds utility.

Slow tests, those that render actual figures, are marked with
@pytest.mark.slow and excluded from the default pytest run. Run them
explicitly with:

    pytest -m slow tests/

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import importlib.util
import sys
import warnings
from pathlib import Path

import pytest

from sprezzature_figures.catalog import list_kinds as registry_list_kinds
from sprezzature_figures.make_figure import (
    describe_required_roles,
    get_figure_definition,
    list_kinds,
    make_figure,
    resolve_role_mapping,
    validate_figure_input,
)


def test_list_kinds_catalogue() -> None:
    """list_kinds returns a sorted, non-empty list of >=80 kinds that
    includes the well-known chart types."""
    kinds = list_kinds()
    assert isinstance(kinds, list)
    assert len(kinds) >= 80
    assert kinds == sorted(kinds)
    for expected in ("treemap", "sankey", "venn", "wordcloud", "funnel"):
        assert expected in kinds, f"Expected kind {expected!r} missing from list_kinds()"


def test_make_figure_unknown_kind_raises_with_available_list() -> None:
    """An unrecognised kind raises ValueError naming the failure and the
    count of available kinds."""
    with pytest.raises(ValueError) as exc:
        make_figure("nonexistent_chart_xyz_abc", [])
    message = str(exc.value)
    assert "No script for kind" in message
    assert "Available (" in message


def _load_demo_data(kind: str) -> list:
    """Load DEMO_DATA from a make_<kind>.py script without calling make_figure."""
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    # Hyphenated kinds keep the hyphen in the filename (make_hexbin-map.py,
    # make_interruption-matrix.py); a few older ones use the underscore form.
    # Try the verbatim name first, then the normalised fallback.
    normalised = kind.replace("-", "_")
    candidate = next(
        (scripts_dir / f"make_{stem}.py" for stem in (kind, normalised)
         if (scripts_dir / f"make_{stem}.py").exists()),
        None,
    )
    if candidate is None:
        return []
    # Sibling helpers (_render, _style, ...) import by bare name, so the scripts
    # dir must be importable when we exec the module standalone.
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    spec = importlib.util.spec_from_file_location(f"_test_load_{normalised}", candidate)
    if spec is None or spec.loader is None:
        return []
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"_test_load_{normalised}"] = mod
    try:
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
    except Exception:
        return []
    return getattr(mod, "DEMO_DATA", [])


@pytest.mark.parametrize("kind", ["treemap", "funnel"])
def test_demo_data_exists(kind: str) -> None:
    """Each shipped generator script must expose non-empty DEMO_DATA."""
    data = _load_demo_data(kind)
    assert len(data) >= 1, f"make_{kind}.DEMO_DATA is empty"


def test_line_renders_single_series_data_without_the_optional_series_role(tmp_path: Path) -> None:
    """`series` is declared optional on the "line" kind, so a plain
    month+value dataset (no `series` column at all -- the shape produced
    when Studio's recommendation cards only bind required roles) must
    render, not raise a bare KeyError('series'). Also checks the custom
    axis labels keep the rows' own chronological order: sorting a set of
    non-canonical labels by "MONTHS.index if present else 0" used to tie
    them all at key 0 and fall back to Python's set-hash order instead.
    """
    rows = [
        {"month": "2025-01-01", "value": 1200},
        {"month": "2025-02-01", "value": 1350},
        {"month": "2025-03-01", "value": 1410},
    ]
    out = tmp_path / "line_single_series.svg"
    result = make_figure("line", rows, out=str(out))
    svg = Path(result).read_text()
    assert svg.index(">2025-01-01<") < svg.index(">2025-02-01<") < svg.index(">2025-03-01<")


@pytest.mark.slow
@pytest.mark.parametrize("kind", ["treemap", "funnel"])
def test_stable_kind_renders_to_png(kind: str, tmp_path: Path) -> None:
    """make_figure(..., out='*.png') produces a non-empty file on disk."""
    data = _load_demo_data(kind)
    out = tmp_path / f"{kind}.png"
    result = make_figure(kind, data, out=str(out))
    assert Path(result).exists(), f"Output file not created: {result}"
    assert Path(result).stat().st_size > 0


@pytest.mark.slow
@pytest.mark.parametrize("kind", registry_list_kinds(status="stable"))
def test_every_stable_kind_renders_from_registry(kind: str, tmp_path: Path) -> None:
    """Every kind the registry marks 'stable' must render its own DEMO_DATA.

    Parametrized off the registry itself (not a hardcoded pair of names) so
    this test automatically covers new figures as more are promoted to
    'stable', instead of needing a new hand-written test per generator.
    """
    data = _load_demo_data(kind)
    assert data, f"{kind} is marked stable but exposes no DEMO_DATA"
    out = tmp_path / f"{kind}.svg"
    result = make_figure(kind, data, out=str(out))
    assert Path(result).exists() and Path(result).stat().st_size > 0


@pytest.mark.slow
@pytest.mark.parametrize(
    ("ext", "magic"),
    [
        (".svg", b"<svg"),
        (".png", b"\x89PNG"),
        (".pdf", b"%PDF"),
        (".jpg", b"\xff\xd8\xff"),
        (".html", b"<!doctype html"),
    ],
)
def test_out_extension_controls_output_format(ext: str, magic: bytes, tmp_path: Path) -> None:
    """`--out chart.png` must yield a real PNG, not SVG bytes in a .png file.

    Regression for the SVG-first generators writing their SVG string verbatim
    regardless of the requested extension. write_svg now converts to the
    destination format (png via resvg_py, pdf/jpg via resvg_py + Pillow,
    html wrapper), leaving .svg byte-identical.
    """
    data = _load_demo_data("treemap")
    out = tmp_path / f"treemap{ext}"
    result = make_figure("treemap", data, out=str(out))
    head = Path(result).read_bytes()[:16].lstrip()
    assert head.lower().startswith(magic.lower()), f"{ext}: got {head!r}"


# Hero-SVG generators that were unreachable through the dispatcher until they
# grew a standard ``make_<kind>`` callable (and the loader learned to put
# scripts/ on sys.path for their sibling imports). Rendering some of them relies
# on vendored basemaps under assets/geo, so this doubles as a check those data
# files are present.
_REPAIRED_KINDS = [
    "speaking_time",
    "binned-grid-map",
    "hexmap",
    "hexbin-map",
    "spike-map",
    "dotdensity",
]


@pytest.mark.slow
@pytest.mark.parametrize("kind", _REPAIRED_KINDS)
def test_repaired_hero_kind_dispatches_and_renders(kind: str, tmp_path: Path) -> None:
    """Each repaired hero generator now renders through make_figure (it built
    its own demo from a bare call), where it used to raise 'no callable'."""
    out = tmp_path / f"{kind}.svg"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # these are still catalogued 'legacy'
        result = make_figure(kind, [], out=str(out))
    body = Path(result).read_bytes()
    assert body[:200].lstrip().startswith(b"<svg") or b"<svg" in body[:200]
    assert len(body) > 1000


@pytest.mark.slow
def test_renders_on_fallback_palette_when_colors_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Figures must render on the bundled fallback palette, not only the full
    sprezzature-colors CSV. CI has no sprezzature-colors, so the fallback (whose
    colour names differ — Teal/Mint, no Turquoise/Pink) is what actually runs;
    a generator that indexes palette names the fallback lacks passes locally and
    dies in CI. Force the fallback here so that gap is caught locally.
    """
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import _style

    monkeypatch.setattr(_style, "_sibling_palette_csv", lambda: None)
    data = _load_demo_data("interruption-matrix")
    out = tmp_path / "im.svg"
    result = make_figure("interruption-matrix", data, out=str(out))
    assert Path(result).exists() and Path(result).stat().st_size > 0


def _png_dimensions(png: bytes) -> tuple[int, int]:
    """Width and height from a PNG's IHDR chunk (bytes 16-24, big-endian)."""
    import struct

    return struct.unpack(">II", png[16:24])


@pytest.mark.slow
def test_scale_env_upsamples_raster(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SPREZZATURE_RENDER_SCALE (set by the render CLIs' --scale) multiplies the
    raster's pixel dimensions; the default remains 1x."""
    data = _load_demo_data("treemap")

    base = Path(make_figure("treemap", data, out=str(tmp_path / "base.png"))).read_bytes()
    bw, bh = _png_dimensions(base)

    monkeypatch.setenv("SPREZZATURE_RENDER_SCALE", "3")
    scaled = Path(make_figure("treemap", data, out=str(tmp_path / "scaled.png"))).read_bytes()
    sw, sh = _png_dimensions(scaled)

    assert (sw, sh) == (bw * 3, bh * 3)


@pytest.mark.slow
def test_scale_env_ignored_for_svg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A vector .svg output is byte-identical whatever the scale; scaling only
    touches the raster/PDF converters."""
    data = _load_demo_data("treemap")
    plain = Path(make_figure("treemap", data, out=str(tmp_path / "a.svg"))).read_bytes()
    monkeypatch.setenv("SPREZZATURE_RENDER_SCALE", "4")
    scaled = Path(make_figure("treemap", data, out=str(tmp_path / "b.svg"))).read_bytes()
    assert plain == scaled


@pytest.mark.slow
def test_make_figure_hyphenated_kind_dispatches_correctly(tmp_path: Path) -> None:
    """Regression for the hyphen/underscore dispatcher bug.

    make_figure() must locate scripts/make_connected-scatter.py for
    kind='connected-scatter' (it previously looked for a nonexistent
    make_connected_scatter.py and raised a misleading "no script" ValueError).
    connected-scatter is now a contract-complete, stable kind (make_connected_scatter
    exists), so the strongest version of this regression check is a full
    successful render, not just "found the file but no callable yet".
    """
    out = tmp_path / "connected-scatter.svg"
    result = Path(make_figure("connected-scatter", None, out=str(out)))
    assert result == out
    assert out.exists()


def test_make_figure_warns_on_non_stable_status(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The status != 'stable' UserWarning contract, exercised without relying
    on any real kind currently being non-stable (all 126 are 'stable' as of
    the legacy-generator promotion -- there is no naturally-broken fixture
    left in the registry). Monkeypatches the dispatcher's own definition
    lookup for one call so the warning path still gets real coverage.
    """
    import sys

    # sprezzature_figures/__init__.py does `from .make_figure import make_figure`,
    # which shadows the `sprezzature_figures.make_figure` *submodule* attribute
    # with the function of the same name -- go through sys.modules to get the
    # actual module object instead of `import ... as`.
    make_figure_module = sys.modules["sprezzature_figures.make_figure"]

    real_get_definition = make_figure_module._get_figure_definition

    def fake_get_definition(kind: str):
        definition = real_get_definition(kind)
        if kind == "treemap":
            definition = definition.model_copy(update={"status": "experimental"})
        return definition

    monkeypatch.setattr(make_figure_module, "_get_figure_definition", fake_get_definition)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        out = tmp_path / "treemap.svg"
        result = Path(make_figure("treemap", None, out=str(out)))
    assert result == out
    assert out.exists()
    assert any("status='experimental'" in str(w.message) for w in caught)


def test_get_figure_definition_exposed_from_make_figure() -> None:
    """make_figure re-exports the registry lookup."""
    d = get_figure_definition("treemap")
    assert d.kind == "treemap"
    assert d.status == "stable"


def test_missing_required_role_is_flagged_and_raised() -> None:
    """validate_figure_input reports a missing required role as an error, and
    make_figure refuses to render (ValueError) rather than calling a generator
    with invalid data."""
    rows = [{"parent": "A", "name": "A1"}]  # missing 'value'
    issues = validate_figure_input("treemap", rows)
    assert any(i.field == "value" and i.severity == "error" for i in issues)
    with pytest.raises(ValueError, match="value"):
        make_figure("treemap", rows, out="/tmp/should-not-exist.svg")


def test_make_figure_falls_back_to_deprecated_path_for_unregistered_script(tmp_path: Path) -> None:
    """A generator script that exists on disk but was never added to
    figures.json must still work via the deprecated filename-guessing
    fallback, with a DeprecationWarning -- never a hard failure.
    """
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    throwaway = scripts_dir / "make_test_throwaway_kind.py"
    throwaway.write_text(
        "from pathlib import Path\n"
        "DEMO_DATA = [{'x': 1}]\n"
        "def make_test_throwaway_kind(data, *, out=None, title=''):\n"
        "    p = Path(out)\n"
        "    p.write_text('ok')\n"
        "    return p\n",
        encoding="utf-8",
    )
    try:
        out = tmp_path / "throwaway.svg"
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = make_figure("test_throwaway_kind", [{"x": 1}], out=str(out))
        assert Path(result).exists()
        assert any(issubclass(w.category, DeprecationWarning) for w in caught)
    finally:
        throwaway.unlink(missing_ok=True)


def test_resolve_scripts_dir_prefers_dedicated_name_over_generic_collision(tmp_path: Path) -> None:
    """A third-party package can also drop a generic ``scripts/`` at the
    root of site-packages -- unrelated to us, pure name collision. If that
    generic name won, every figure render would silently resolve into the
    wrong directory and fail. The dedicated ``sprezzature_figures_scripts/``
    name can only ever be ours, so it must be preferred whenever both exist.
    """
    from sprezzature_figures.make_figure import _resolve_scripts_dir

    generic = tmp_path / "scripts"
    generic.mkdir()
    (generic / "unrelated_third_party_marker.py").write_text("", encoding="utf-8")

    dedicated = tmp_path / "sprezzature_figures_scripts"
    dedicated.mkdir()
    (dedicated / "make_bar.py").write_text("", encoding="utf-8")

    assert _resolve_scripts_dir(tmp_path) == dedicated


def test_resolve_scripts_dir_falls_back_to_generic_in_source_tree(tmp_path: Path) -> None:
    """In the source tree, only the generic ``scripts/`` exists (the
    dedicated name is an install-time artifact) -- must still resolve.
    """
    from sprezzature_figures.make_figure import _resolve_scripts_dir

    generic = tmp_path / "scripts"
    generic.mkdir()

    assert _resolve_scripts_dir(tmp_path) == generic


def test_resolve_role_mapping_accepts_role_labels() -> None:
    """--map keys may use a role's discoverable label instead of its
    historical name: 'Category' (any case) resolves to bar's 'region'.
    Exact role names and unknown keys pass through untouched."""
    assert resolve_role_mapping("bar", {"Category": "month"}) == {"region": "month"}
    assert resolve_role_mapping("bar", {"category": "m", "value": "v"}) == {
        "region": "m",
        "value": "v",
    }
    assert resolve_role_mapping("bar", {"region": "m"}) == {"region": "m"}
    assert resolve_role_mapping("bar", {"nonsense": "m"}) == {"nonsense": "m"}


def test_describe_required_roles_lists_names_and_labels() -> None:
    """The CLI error hint names every required role with its label, so a
    wrong --map guess surfaces the accepted keys."""
    desc = describe_required_roles("bar")
    assert "region" in desc and "Category" in desc and "value" in desc
    assert describe_required_roles("no-such-kind") == ""
