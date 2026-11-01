"""
Every style option is either safe for Ralph or named as needing a person.

``policy.py`` has always had a set of the fields a safe repair may touch, and
:func:`is_safe_repair` answers False for anything outside it — so an
unclassified field falls to "ask the user", which is the right direction.

The right direction chosen by *nobody* is still worth fixing. Counting on
2026-11-01 found fourteen fields on :class:`StyleOptions` and eight in the
safe set. The other six had never been considered: the default had decided for
them, and the next field added would be decided the same way, silently, by
whoever was not looking.

``sprezzature-maps`` guards this shape in its own option registry — ``OPTIONS``
and ``NOT_AN_OPTION`` together must account for every keyword a renderer takes
— and the discipline transfers: a knob has to be classified by somebody, and
the reason written down, because the next one will be classified by reading
the last one's reason.

Author
------
Project maintainers.
"""

from __future__ import annotations

import pytest

from sprezzature_figures.core.figure_plan import StyleOptions
from sprezzature_figures.core.operations import SetStyleOption
from sprezzature_figures.studio.ralph import policy


def _fields() -> set[str]:
    return set(StyleOptions.model_fields)


def test_there_are_style_options_to_classify() -> None:
    """Non-vacuity: an empty model would make every assertion below hold."""
    assert len(_fields()) >= 10, f"only {len(_fields())} style options found"


def test_every_field_is_on_exactly_one_list() -> None:
    """The property that makes a new field impossible to overlook."""
    safe = policy._SAFE_STYLE_OPTIONS
    asks = policy._NEEDS_CONFIRMATION_STYLE_OPTIONS
    fields = _fields()

    unclassified = sorted(fields - safe - asks)
    assert not unclassified, (
        "these StyleOptions fields are on neither list, so whether Ralph may "
        "change them unattended was decided by a default rather than by "
        f"anybody: {', '.join(unclassified)}"
    )
    both = sorted(safe & asks)
    assert not both, f"on both lists at once, so the answer depends on order: {both}"


def test_neither_list_names_a_field_that_does_not_exist() -> None:
    """A renamed field drops out of the safe set in silence, and the loop
    quietly stops being allowed to make a repair it used to make."""
    fields = _fields()
    for name, listed in (
        ("safe", policy._SAFE_STYLE_OPTIONS),
        ("needs-confirmation", policy._NEEDS_CONFIRMATION_STYLE_OPTIONS),
    ):
        ghosts = sorted(listed - fields)
        assert not ghosts, f"the {name} list names fields StyleOptions does not have: {ghosts}"


def _set(field: str) -> SetStyleOption:
    """One operation, with the model's own flag saying it is fine to apply.

    ``requires_confirmation=False`` on purpose. ``policy.py`` states that it
    decides for itself "even if the model itself did not flag it as such...
    a second line of defense in case the model forgets". These tests drive
    that defence rather than the model's opinion of itself.
    """
    from sprezzature_figures.core.operations import SetStyleOption

    return SetStyleOption(
        operation_id=f"test-{field}",
        option=field,
        value="anything",
        requires_confirmation=False,
    )


@pytest.mark.parametrize("field", sorted(policy._NEEDS_CONFIRMATION_STYLE_OPTIONS))
def test_a_field_that_needs_a_person_is_refused_even_when_the_model_says_otherwise(
    field: str,
) -> None:
    """The second line of defence, exercised.

    The operation arrives claiming it needs no confirmation — which is exactly
    what a model that forgot would send — and the policy refuses it anyway.
    """
    assert not policy.is_safe_repair(_set(field)), (
        f"{field} needs a person, and the policy applied it because the model "
        "said it was fine"
    )


@pytest.mark.parametrize("field", sorted(policy._SAFE_STYLE_OPTIONS))
def test_a_safe_field_really_is_offered_to_the_loop(field: str) -> None:
    """Non-vacuity in the other direction: a policy that refuses everything
    would pass the test above and leave the loop unable to do anything."""
    assert policy.is_safe_repair(_set(field)), f"{field} is listed safe and refused"
