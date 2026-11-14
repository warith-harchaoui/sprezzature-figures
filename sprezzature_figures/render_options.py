"""
What an editor hands a generator: one plan, turned into the keyword
arguments ``make_figure`` actually reads.

Before this module, every render from a plan passed a title and a
language and nothing else. The style panel wrote ``font_scale``,
``legend_position``, ``show_grid`` and ``show_labels`` into the plan, and
no generator takes any of the four, so each control re-rendered an
identical picture. The subtitle Ralph could set was dropped the same way.
The figure's own options (``x_label``, ``accessibility``, ``theme``,
``log_y``...) were out of reach entirely.

:func:`figure_kwargs` is now the only place a plan becomes a call: the
editor, Ralph's engine and the exported ``reproduce.py`` all go through
it, so the picture on screen, the one Ralph critiques and the one a
reader rebuilds from the archive are drawn from the same arguments.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

from typing import Any

from sprezzature_figures.catalog import get_figure_definition
from sprezzature_figures.core.figure_plan import FigurePlan
from sprezzature_figures.options import OptionDefinition, options_for

#: Options the editor sets itself and never shows as a free field: the
#: language follows the data, ``mode`` is the SVG's
#: script packaging (a publishing concern, not a look), and the canvas
#: size is fixed by the generator's own proportions.
EDITOR_OWNED = frozenset({"language", "lang", "mode", "width", "height", "transparent", "seed"})

#: Text options that name a part of the chart. They get a text field of
#: their own, in this order, under the title and subtitle.
LABEL_OPTIONS = (
    "x_label",
    "y_label",
    "x_axis_title",
    "y_axis_title",
    "axis_left_title",
    "legend_title",
    "value_label",
    "unit",
    "value_unit",
)

#: ``make_figure`` itself handles this one (sprezzature_figures.darkmode),
#: so it never appears in a generator's signature.
DARK = "dark"

_BY = {"en": "by", "fr": "par"}


def accepted_options(kind: str) -> dict[str, OptionDefinition]:
    """The options ``kind``'s generator declares, read from the frozen
    catalogue (no generator module is imported)."""
    return options_for(kind)


def _bound_column(plan: FigurePlan, role: str) -> str | None:
    binding = plan.bindings.get(role)
    return binding.columns[0] if binding and binding.columns else None


def default_title(plan: FigurePlan, *, language: str = "en") -> str:
    """A plain title read off the bindings: the measure *by* the
    dimension ("CA par Pays", "abonnes by mois").

    Not a headline -- the house rule is that a title states the finding,
    and only the person holding the data knows it -- but it names what is
    drawn, which the kind's own name ("Bar") never did.
    """
    definition = get_figure_definition(plan.figure_kind)
    measures: list[str] = []
    dimensions: list[str] = []
    for role in definition.required_roles:
        column = _bound_column(plan, role.name)
        if column is None:
            continue
        if role.accepted_types == ["numeric"]:
            measures.append(column)
        else:
            dimensions.append(column)
    if measures and dimensions:
        text = f"{measures[-1]} {_BY.get(language, 'by')} {dimensions[0]}"
    elif measures or dimensions:
        text = (measures or dimensions)[0]
    else:
        text = definition.label
    return text[:1].upper() + text[1:]


def default_axis_labels(plan: FigurePlan) -> dict[str, str]:
    """Axis titles that can be read off the bindings without guessing.

    Only for a generator that takes ``x_label``/``y_label`` and has at most
    two required roles: there the first role is the horizontal axis and
    the second the vertical one in every such generator of the catalogue.
    With three roles or more (a heatmap's day, hour and value) the mapping
    is the generator's business, and a wrong axis title is worse than the
    generic one it draws itself.
    """
    accepted = accepted_options(plan.figure_kind)
    roles = get_figure_definition(plan.figure_kind).required_roles
    if len(roles) > 2:
        return {}
    labels: dict[str, str] = {}
    for option, role in zip(("x_label", "y_label"), roles, strict=False):
        column = _bound_column(plan, role.name)
        if option in accepted and column:
            labels[option] = column
    return labels


def figure_kwargs(plan: FigurePlan, *, language: str | None = None) -> dict[str, Any]:
    """The keyword arguments a render of ``plan`` passes to ``make_figure``.

    Precedence, lowest first: what can be read off the bindings (title,
    axis titles), then what the person typed or chose (``plan.title``,
    ``plan.subtitle``, ``plan.options``). An option the current kind does
    not declare is dropped here, so switching kinds never sends a bar's
    ``x_label`` to a treemap.
    """
    accepted = accepted_options(plan.figure_kind)
    kwargs: dict[str, Any] = {}

    title_option = accepted.get("title")
    # A generator whose title defaults to "" computes its own headline
    # (pareto writes the 80/20 finding); a default title would bury it.
    if plan.title:
        kwargs["title"] = plan.title
    elif title_option is None or title_option.default != "":
        kwargs["title"] = default_title(plan, language=language or "en")

    if plan.subtitle and "subtitle" in accepted:
        kwargs["subtitle"] = plan.subtitle

    kwargs.update(default_axis_labels(plan))

    # The canvas size, only once something changed it (SetOutputSize, or
    # Ralph's size repair): the StyleOptions default is not the generator's,
    # and sending it would resize every figure drawn from a plan.
    default_style = type(plan.style)()
    for dimension in ("width", "height"):
        value = getattr(plan.style, dimension)
        if dimension in accepted and value != getattr(default_style, dimension):
            kwargs[dimension] = value

    for name, value in plan.options.items():
        # A cleared field means "back to automatic", not "draw nothing".
        if value is None or value == "":
            continue
        if name == DARK:
            kwargs[DARK] = bool(value)
        elif name in accepted and name not in EDITOR_OWNED:
            kwargs[name] = value

    if language is not None:
        kwargs["language"] = language
    return kwargs


def figure_option_is_valid(kind: str, name: str, value: Any) -> bool:
    """Whether ``kind`` takes option ``name`` with ``value``: the name is
    declared (or is ``dark``), the editor does not own it, and a value
    with a closed set of choices is one of them. ``None`` always is (it
    means "back to automatic")."""
    if name == DARK:
        return value is None or isinstance(value, bool)
    option = accepted_options(kind).get(name)
    if option is None or name in EDITOR_OWNED:
        return False
    if value is None:
        return True
    return not option.choices or value in option.choices


def describe_for_prompt(kind: str) -> str:
    """One line per option the assistant may set on ``kind``, for its prompt."""
    lines = []
    for option in editable_options(kind):
        choices = f", one of {', '.join(option.choices)}" if option.choices else ""
        lines.append(f"- {option.name} ({option.type}{choices}): {option.description}".rstrip(": "))
    lines.append("- dark (bool): draw for a dark background.")
    return "\n".join(lines)


def editable_options(kind: str) -> list[OptionDefinition]:
    """The options worth a control in the panel, beyond title and subtitle:
    every declared option the editor does not own, of a type a single
    field can hold. List- and map-typed options (``highlight``, ``colors``)
    stay reachable through Ralph and the library, not through a form."""
    single = {"str", "int", "float", "bool"}
    return [
        option
        for name, option in accepted_options(kind).items()
        if name not in EDITOR_OWNED and name not in ("title", "subtitle") and option.type in single
    ]
