"""
An option the catalogue advertises has to change the figure.

The catalogue derives each kind's options from its generator's signature,
and both command lines and the HTTP API publish that list. None of that
checks the one thing a caller cares about: that passing the option does
something. It frequently did not. A sweep in October 2026 found **74 of
133 figures accepting a `title` they ignored** -- `make-figure alluvial
--title "..."` drew the same picture, in silence, while `--help` offered
the flag. Some generators computed their headline from the data (a good
habit: `bullet` writes "Three of five targets cleared" so the headline
cannot drift from the bars) and simply never let the caller override it;
others had no `title` parameter on `build_svg` at all and said so in their
docstring, "accepted for signature parity".

So this renders every kind once with a sentinel in every text option and
checks the sentinel comes back out. It is the only form of the check that
works: reading the source misses a wrapper that drops the argument, an
argument spliced into the wrong call, or -- found twice during the sweep --
an edit that silently failed to apply.

Marked slow: 133 renders.

Author
------
Warith HARCHAOUI <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import contextlib
import io
from pathlib import Path

import pytest

from sprezzature_figures import make_figure
from sprezzature_figures.catalog import get_figure_definition, list_kinds
from sprezzature_figures.options import OptionDefinition, options_for

#: Kinds whose text options still do not reach the drawing, with the names
#: that do not. **This list can only shrink.** Each entry is a figure whose
#: headline is written as a literal inside the call that draws it, split
#: across f-string fragments, or composed in a helper -- shapes that need a
#: reading rather than a sweep. ``test_the_allowlist_holds_no_passing_kind``
#: fails when one is fixed and left here, so the debt cannot quietly
#: outlive itself.
KNOWN_UNWIRED: dict[str, tuple[str, ...]] = {
    "alluvial": ("title",),
    "binned-grid-map": ("title",),
    "connected-scatter": ("title",),
    "elbow": ("abstain_reason", "title"),
    "gapminder": ("title",),
    "gapminder_variants": ("title",),
    "hexbin-map": ("title",),
    "interruption-matrix": ("title",),
    "jointplot": ("subtitle",),
    "liftgain": ("title",),
    "org-chart": ("title",),
    "pairplot": ("title",),
    "parallel-sets": ("title",),
    "pictorial": ("title",),
    "ppplot": ("title",),
    "prcurve": ("title",),
    "ternary": ("title",),
    "timeline": ("title",),
}


def _text_options(kind: str) -> dict[str, OptionDefinition]:
    """The options that are prose a reader sees, and not something else.

    Two exclusions, both necessary. An option with a closed set of values
    cannot take a sentinel -- `theme`, `mode`, `accessibility` -- and one
    whose default names a data role is a *column selector*: passing a
    sentinel to `bar`'s ``value`` asks the figure to plot a column that
    does not exist, which is a different test's job.
    """
    definition = get_figure_definition(kind)
    roles = {role.name for role in definition.required_roles + definition.optional_roles}
    return {
        name: option
        for name, option in options_for(kind).items()
        if option.type == "str"
        and not option.choices
        and not (isinstance(option.default, str) and option.default in roles)
    }


def _render_with(kind: str, probes: dict[str, str], tmp_path: Path) -> list[str]:
    """Render `kind` with those sentinels and report the ones that vanished."""
    if not probes:
        return []
    target = tmp_path / f"{kind.replace('/', '_')}.svg"
    # Generators print "wrote <path>" as a side effect of being runnable
    # scripts; that is not this test's business.
    with contextlib.redirect_stdout(io.StringIO()):
        make_figure(kind, out=str(target), **probes)
    drawn = target.read_text(encoding="utf-8")
    return sorted(name for name, token in probes.items() if token not in drawn)


def _unwired(kind: str, tmp_path: Path) -> list[str]:
    """Which of `kind`'s text options never show up in what it draws.

    Two renders, not one, and the reason is a blind spot this test found in
    itself. Several figures take an override option defaulting to ``None``
    -- `verdict`, `footer`, `summary`, `caveat` -- which *replaces* a
    sentence composed from other options. Setting every option at once then
    reports the composing options as unwired, because the override they
    feed was overridden. So the composing options are probed together, and
    the overrides in a second pass of their own.
    """
    options = _text_options(kind)
    composing = {
        name: f"ZQ{index}X"
        for index, name in enumerate(options)
        if options[name].default is not None
    }
    overriding = {
        name: f"ZW{index}X"
        for index, name in enumerate(options)
        if options[name].default is None
    }
    return sorted(
        _render_with(kind, composing, tmp_path) + _render_with(kind, overriding, tmp_path)
    )


@pytest.mark.slow
@pytest.mark.parametrize("kind", list_kinds())
def test_every_text_option_reaches_the_drawing(kind: str, tmp_path: Path) -> None:
    """Pass a sentinel into every text option; it has to come back out.

    When this fails for a figure you have just written, the option is
    declared and dropped somewhere between the wrapper and the drawing --
    which is worse than a hardcoded string, because `--help` advertises it.
    """
    missing = _unwired(kind, tmp_path)
    allowed = sorted(KNOWN_UNWIRED.get(kind, ()))
    assert missing == allowed, (
        f"{kind}: options that do not reach the figure changed.\n"
        f"  now: {missing}\n  allowed: {allowed}\n"
        "Wire the option through, or -- only if it genuinely cannot be "
        "honoured -- say so in KNOWN_UNWIRED with the reason."
    )


@pytest.mark.slow
def test_the_allowlist_holds_no_passing_kind(tmp_path: Path) -> None:
    """A figure that has been fixed must leave the list.

    Without this the allowlist is a place where entries go to be forgotten,
    and the count stops meaning anything.
    """
    stale = [kind for kind in KNOWN_UNWIRED if not _unwired(kind, tmp_path)]
    assert stale == [], f"these now honour every text option; drop them from KNOWN_UNWIRED: {stale}"


def test_the_allowlist_names_only_real_kinds() -> None:
    """A renamed figure must not leave a dead entry behind."""
    unknown = sorted(set(KNOWN_UNWIRED) - set(list_kinds()))
    assert unknown == [], f"KNOWN_UNWIRED names kinds that no longer exist: {unknown}"


def test_the_allowlist_names_only_real_options() -> None:
    """An entry has to name an option the figure actually declares."""
    wrong = {
        kind: sorted(set(names) - set(options_for(kind)))
        for kind, names in KNOWN_UNWIRED.items()
        if set(names) - set(options_for(kind))
    }
    assert wrong == {}, f"KNOWN_UNWIRED names options that do not exist: {wrong}"


def test_most_of_the_catalogue_honours_its_text_options() -> None:
    """Pin the debt so it cannot grow back quietly.

    Cheap on purpose -- it counts the allowlist rather than rendering
    anything -- so the number is in front of whoever adds a figure, not
    only in the slow lane.
    """
    assert len(KNOWN_UNWIRED) <= 18, (
        f"{len(KNOWN_UNWIRED)} kinds do not honour a text option; it was 18 after the "
        "October 2026 sweep and 74 before it. The list is meant to shrink."
    )
