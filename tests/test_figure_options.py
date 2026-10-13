"""
Tests for the per-figure option surface: what each of the 127 generators
accepts beyond its rows, and the three front ends that publish it.

The surface itself is derived, not written: ``options.introspect_options``
reads a generator's signature and docstring, and
``tools/build_figures_catalog.py`` freezes the result into
``catalog/figures.json`` so the CLI and the HTTP API can list it without
importing 127 modules. Frozen derivations drift, so the test that matters
here is :func:`test_frozen_options_match_the_live_signatures`: it re-derives
everything from the live modules and fails when a generator has gained,
lost or retyped a parameter the catalogue still describes the old way.

Tests that render an actual figure carry @pytest.mark.slow, like the rest
of the suite. The drift guard does not: it imports all 127 generators and
still runs in well under a second, and a guard that only fires in the
second pass is a guard that fires late.

Author
------
Warith HARCHAOUI <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from sprezzature_figures.catalog import get_figure_definition, list_kinds
from sprezzature_figures.make_figure import _SCRIPTS_DIR, _load_module, main
from sprezzature_figures.options import (
    OPTION_CHOICES,
    OptionDefinition,
    OptionError,
    coerce_option,
    describe_options,
    introspect_options,
    options_for,
    parse_option_assignments,
    validate_options,
)

ALL_KINDS = list_kinds()


def _live_options(kind: str) -> dict[str, OptionDefinition]:
    """Re-derive one kind's options by importing its generator, as the builder does."""
    definition = get_figure_definition(kind)
    module = _load_module(
        _SCRIPTS_DIR / Path(definition.module).name,
        f"_options_test_{kind.replace('-', '_')}",
    )
    return introspect_options(getattr(module, definition.callable_name))


def test_every_kind_publishes_its_options() -> None:
    """No figure is a black box: each declares at least its own title and theme.

    An empty schema used to be the norm -- all 127 of them -- which is why
    no command line could set a subtitle.
    """
    silent = [kind for kind in ALL_KINDS if not options_for(kind)]
    assert silent == [], f"{len(silent)} kinds publish no options: {silent[:5]}"


def test_catalogue_covers_every_registered_kind() -> None:
    """The option listing is for all of them, not for the ones somebody got to."""
    assert len(ALL_KINDS) == 127
    assert all(options_for(kind) for kind in ALL_KINDS)


def test_frozen_options_match_the_live_signatures() -> None:
    """The catalogue's frozen options still describe the generators as they are.

    This is the drift guard. Rebuild with ``python
    tools/build_figures_catalog.py`` when it fails -- the generator is
    right and the catalogue is stale, never the other way round.
    """
    drift: list[str] = []
    for kind in ALL_KINDS:
        frozen = options_for(kind)
        live = _live_options(kind)
        if set(frozen) != set(live):
            drift.append(f"{kind}: names {sorted(set(frozen) ^ set(live))}")
            continue
        for name, option in live.items():
            stored = frozen[name]
            if (stored.type, stored.default, stored.choices) != (
                option.type,
                option.default,
                option.choices,
            ):
                drift.append(f"{kind}.{name}: {stored!r} != {option!r}")
    assert drift == [], (
        f"{len(drift)} option(s) drifted from their generator; "
        f"run `python tools/build_figures_catalog.py`. First: {drift[0]}"
    )


def test_option_choices_match_the_generators_own_command_line() -> None:
    """The closed value sets are the ones ``scripts/_render.py`` already enforces.

    ``OPTION_CHOICES`` restates them so the package stays importable
    without the generator scripts on the path; restating is only safe
    while the two agree.
    """
    render_helper = _load_module(_SCRIPTS_DIR / "_render.py", "_options_test_render_helper")
    source = inspect.getsource(render_helper.render_cli)
    for value in OPTION_CHOICES["mode"]:
        assert f'"{value}"' in source
    for value in OPTION_CHOICES["accessibility"]:
        assert f'"{value}"' in source
    for value in OPTION_CHOICES["theme"]:
        assert f'"{value}"' in source
    interactive = _load_module(_SCRIPTS_DIR / "_interactive.py", "_options_test_interactive")
    assert tuple(OPTION_CHOICES["mode"]) == tuple(interactive.MODES)


def test_shared_vocabulary_is_described_everywhere_it_appears() -> None:
    """``--width`` says what it does on every figure that has it, not on some.

    Generators document their own parameters and often say only
    "Forwarded to build_svg" about the shared ones; the house sentence
    fills that in, and the point of the table is that it leaves no gap.
    """
    undescribed = [
        f"{kind}.{name}"
        for kind in ALL_KINDS
        for name, option in options_for(kind).items()
        if name in {"width", "height", "mode", "accessibility", "theme", "language", "subtitle"}
        and not option.description
    ]
    assert undescribed == [], f"{len(undescribed)} shared options with no help: {undescribed[:5]}"


def test_defaults_are_the_generators_own() -> None:
    """A default shown to a caller is the one the generator would use."""
    assert options_for("bar")["width"].default == 745
    assert options_for("treemap")["width"].default == 900
    assert options_for("sankey")["volume_unit"].default == "visitors"
    assert get_figure_definition("bar").default_width == 745


def test_coercion_reads_command_line_text_as_python_values() -> None:
    """A value typed on a terminal and the same value sent as JSON arrive alike."""
    width = options_for("bar")["width"]
    assert coerce_option(width, "1200") == 1200
    assert coerce_option(width, 1200) == 1200
    stages = options_for("sankey")["stage_names"]
    assert coerce_option(stages, "a, b ,c") == ["a", "b", "c"]
    assert coerce_option(stages, ["a", "b"]) == ["a", "b"]


def test_a_closed_set_refuses_a_value_outside_it() -> None:
    theme = options_for("bar")["theme"]
    assert coerce_option(theme, "academic") == "academic"
    with pytest.raises(OptionError, match="corporate, academic"):
        coerce_option(theme, "neon")


def test_a_number_option_refuses_a_word() -> None:
    with pytest.raises(OptionError, match="whole number"):
        coerce_option(options_for("bar")["width"], "wide")


def test_an_unknown_option_names_the_nearest_real_one() -> None:
    """The reader mistyped something; the answer is the correction, not a list to scan."""
    with pytest.raises(OptionError, match="Did you mean 'width'"):
        validate_options("bar", {"widht": 900})


def test_an_option_another_figure_has_is_still_unknown_here() -> None:
    """``rose`` has no canvas size, so ``--width`` on it is an error, not a no-op.

    Silently dropping it is what the dispatcher does for library callers
    forwarding a bundle of chrome kwargs. For somebody who typed it, the
    figure coming back unchanged looks like the option did not work.
    """
    assert "width" in options_for("bar")
    with pytest.raises(OptionError, match="rose has no option"):
        validate_options("rose", {"width": 900})


def test_set_assignments_parse_with_either_spelling() -> None:
    """``--set x-label=...`` and ``--set x_label=...`` are the same option."""
    assert parse_option_assignments("bar", ["x-label=Region"]) == {"x_label": "Region"}
    assert parse_option_assignments("bar", ["width=1200", "theme=academic"]) == {
        "width": 1200,
        "theme": "academic",
    }


def test_set_without_an_equals_sign_says_what_the_form_is() -> None:
    with pytest.raises(OptionError, match="name=value"):
        parse_option_assignments("bar", ["subtitle"])


def test_the_same_option_twice_is_refused() -> None:
    with pytest.raises(OptionError, match="given twice"):
        parse_option_assignments("bar", ["width=800", "width=900"])


def test_describe_prints_the_flag_the_default_and_the_help() -> None:
    text = describe_options("sankey")
    assert "--volume-unit" in text
    assert "'visitors'" in text
    assert "--stage-names" in text


def test_cli_describe_lists_roles_then_options(capsys: pytest.CaptureFixture) -> None:
    """``make-figure <kind> --describe`` answers both halves of "how do I call this"."""
    main(["treemap", "--describe"])
    printed = capsys.readouterr().out
    assert "Required data roles" in printed
    assert "parent" in printed and "value" in printed
    assert "--value-unit" in printed
    assert "--width" in printed


def test_cli_describe_as_json_is_the_catalogue_entry(capsys: pytest.CaptureFixture) -> None:
    import json

    main(["treemap", "--describe", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "treemap"
    assert payload["options_schema"]["width"]["default"] == 900


def test_cli_refuses_an_option_the_figure_does_not_have(
    capsys: pytest.CaptureFixture,
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["rose", "--width", "900"])
    assert exit_info.value.code == 2
    assert "rose has no option --width" in capsys.readouterr().err


def test_cli_suggests_the_option_that_was_meant(capsys: pytest.CaptureFixture) -> None:
    with pytest.raises(SystemExit):
        main(["bar", "--subtitel", "oops"])
    assert "Did you mean --subtitle" in capsys.readouterr().err


def test_cli_refuses_an_option_given_twice(capsys: pytest.CaptureFixture) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["bar", "--width", "800", "--set", "width=900"])
    assert exit_info.value.code == 2
    assert "given twice" in capsys.readouterr().err


@pytest.mark.slow
def test_cli_options_reach_the_figure(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """A flag and a --set assignment both land in the rendered SVG."""
    out = tmp_path / "bar.svg"
    main(["bar", "--out", str(out), "--width", "1234", "--set", "subtitle=Q3 figures"])
    capsys.readouterr()
    svg = out.read_text(encoding="utf-8")
    assert 'width="1234"' in svg
    assert "Q3 figures" in svg


@pytest.mark.slow
def test_a_demo_render_keeps_the_chrome_written_for_it(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """``make-figure sankey`` draws the reference figure, headline and all.

    The CLI used to pass ``title=""`` always, and to hand the generator
    its own DEMO_DATA -- which the dispatcher cannot tell from caller data,
    so it suppressed the demo chrome as well. Between them the demo render
    came out untitled, with no flag able to bring the title back.
    """
    out = tmp_path / "sankey.svg"
    main(["sankey", "--out", str(out)])
    capsys.readouterr()
    svg = out.read_text(encoding="utf-8")
    assert "Organic search fills the funnel" in svg
    assert "One week of site visitors" in svg


@pytest.mark.slow
def test_your_data_never_inherits_the_demo_chrome(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """The flip side: over your rows, the demo's captions are simply false."""
    source = tmp_path / "rows.csv"
    source.write_text("region,value\nParis,12\nLyon,8\n", encoding="utf-8")
    out = tmp_path / "bar.svg"
    main(["bar", "--out", str(out), "--data", str(source)])
    capsys.readouterr()
    assert "Quarterly" not in out.read_text(encoding="utf-8")


def test_every_option_the_catalogue_advertises_is_accepted_by_its_generator() -> None:
    """Calling a generator with each advertised option must not raise TypeError.

    The schema is the promise; this is the promise kept. It checks the
    binding rather than the drawing, so it passes no values -- a bound
    call with the generator's own defaults is exactly what a caller who
    read ``--describe`` would write.
    """
    unbindable: list[str] = []
    for kind in ALL_KINDS:
        definition = get_figure_definition(kind)
        module = _load_module(
            _SCRIPTS_DIR / Path(definition.module).name,
            f"_bind_test_{kind.replace('-', '_')}",
        )
        function = getattr(module, definition.callable_name)
        signature = inspect.signature(function)
        for name, option in options_for(kind).items():
            try:
                signature.bind(None, **{name: option.default})
            except TypeError as exc:
                unbindable.append(f"{kind}.{name}: {exc}")
    assert unbindable == [], f"{len(unbindable)} advertised but unbindable: {unbindable[:5]}"
