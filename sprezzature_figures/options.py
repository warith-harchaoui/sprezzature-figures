"""
options — what each of the 127 figures accepts, beyond its data.

Every generator is a function with a signature: ``make_bar(data, *, out,
title, subtitle, width, height, mode, accessibility, language, x_label,
y_label, theme)``. A library caller reads that signature and passes what
it wants. A CLI caller and an HTTP caller could not: the ``make-figure``
command offered ``--title`` and nothing else, and ``POST /render`` took a
free-form ``options`` object it never checked, so a misspelt key was
dropped in silence by :func:`~sprezzature_figures.make_figure._filter_kwargs_for`
and the figure came back looking ignored rather than wrong.

This module is the one description of that surface, shared by all three
callers. It reads a generator's signature and its numpydoc docstring into
a list of :class:`OptionDefinition` (type, default, allowed values,
one-line help), which the catalogue builder freezes into
``catalog/figures.json`` so listing a kind's options costs a JSON read
rather than importing 127 modules. :func:`introspect_options` stays
importable so a test can re-derive the live signatures and fail when the
frozen copy drifts.

The vocabulary is deliberately small -- six types, because across 127
generators only eleven distinct annotations are in use -- so that a value
typed on a command line, sent as JSON, or handed over by an MCP host all
land as the same Python object.

Author
------
Warith HARCHAOUI <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import difflib
import inspect
import re
import textwrap
from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field

__all__ = [
    "OptionDefinition",
    "OptionError",
    "OPTION_CHOICES",
    "RESERVED_CLI_NAMES",
    "coerce_option",
    "describe_options",
    "introspect_options",
    "options_for",
    "parse_option_assignments",
    "validate_options",
]

OptionType = Literal["str", "int", "float", "bool", "str_list", "float_pair"]

#: Parameters that are not options: the rows themselves, and the output
#: path. Both are owned by the caller's transport (``--out``, the API's
#: ``format``), not by the figure, and exposing them twice would let a
#: request set an output path on a server.
_NOT_OPTIONS = frozenset({"data", "out"})

#: Flags the ``make-figure`` / ``sprezzature-figures render`` parsers
#: already define. A generator parameter colliding with one of these keeps
#: its ``--set name=value`` form but gets no flag of its own, so a figure
#: can never shadow ``--data`` or ``--scale``.
RESERVED_CLI_NAMES = frozenset(
    {"data", "out", "map", "set", "list", "status", "scale", "dark", "help", "version", "json"}
)

#: Closed value sets shared by every generator that takes the parameter.
#: They live in ``scripts/_render.py`` (``render_cli``'s own flags) and
#: ``scripts/_style.py`` (``load_palette``); repeated here because this
#: module must stay importable without the generator scripts on the path,
#: and guarded by a test that compares the two.
OPTION_CHOICES: dict[str, tuple[str, ...]] = {
    "mode": ("self-contained", "external", "static"),
    "accessibility": (
        "universal",
        "high-contrast",
        "monochrome",
        "deuteranopia",
        "protanopia",
        "tritanopia",
    ),
    "theme": ("corporate", "academic"),
    "language": ("en", "fr"),
    "lang": ("en", "fr"),
    # ablation_matrix validates this at render time and raised on anything
    # else; the catalogue advertised it as free text, so the CLI offered no
    # choices and the API accepted a value that could only fail downstream.
    "mark": ("dot", "bar"),
    # validation-curve: which direction along the swept parameter makes the
    # model simpler. A closed set, and declaring it is what tells the
    # "every text option reaches the drawing" probe that this one is a
    # switch rather than a caption.
    "simpler_is": ("larger", "smaller"),
    # seasonal-decomposition: whether the season adds to the level or
    # scales it. Two different claims about the data, and the figure
    # computes different components for each.
    "model": ("additive", "multiplicative"),
    # control-chart: where the sigma behind the limits comes from, and
    # which run rules are applied. The second is a *list* of choices --
    # see the element-wise check in `coerce_option`.
    "limit_from": ("moving-range", "sd"),
    "rules": ("beyond", "run", "trend", "two-of-three"),
    # shap-waterfall: whether the contributions are passed through a
    # logistic before the two ends are quoted as probabilities.
    "link": ("logit", "identity"),
    # stem: where the stalks are rooted. A closed set, and the figure
    # raises on anything else.
    "baseline": ("zero", "mean", "given"),
    # eventplot: how the rows of the raster are stacked.
    "order": ("given", "first", "count", "first-after-onset"),
}

#: House meaning of the keywords many generators share. A generator
#: documents the parameters that are its own and, very often, says only
#: "Forwarded to build_svg" about the ones every figure has -- true, and
#: useless to someone reading ``--help``. Where the docstring says that or
#: says nothing, the shared sentence below is printed instead; where it
#: says anything of its own, the author's words win. 289 of the 847
#: options were pass-through notes and 100 were silent before this table.
SHARED_DESCRIPTIONS: dict[str, str] = {
    "title": "Headline above the figure. Omitted, the figure keeps its own.",
    "subtitle": "The line under the title, for the caveat a headline cannot carry.",
    "desc": "Accessible long description; written from the data when not given.",
    "width": "Canvas width in pixels.",
    "height": "Canvas height in pixels.",
    "mode": (
        "How the SVG carries its interactivity: self-contained ships its own script, "
        "external expects the page to supply one, static leaves it out."
    ),
    "accessibility": ("Palette accessibility level; universal is the colour-vision-safe default."),
    "theme": ("corporate (Roboto, house palette) or academic (Latin Modern, Okabe-Ito)."),
    "language": "Language of the chrome the figure writes itself -- titles, legends, units.",
    "lang": "Language of the chrome the figure writes itself -- titles, legends, units.",
    "x_label": "Title under the x axis.",
    "y_label": "Title beside the y axis.",
    "x_axis_title": "Title under the x axis.",
    "y_axis_title": "Title beside the y axis.",
    "axis_title": "Title on the value axis.",
    "legend_title": "Heading above the legend.",
    "log_x": "Use a logarithmic x axis.",
    "log_y": "Use a logarithmic y axis.",
    "seed": "Random seed, for a figure whose demo layout is drawn at random.",
    "unit": "Unit word printed after values.",
    "value_unit": "Unit word printed after values.",
    "animated": "Animate the figure; the animation ships inside the SVG.",
    "duration": "Length of the animation, in seconds.",
    "square": "Force a square canvas.",
}

#: A docstring that says only where the value goes, and nothing about what
#: it does. ``"Visual theme. Forwarded to build_svg."`` is not one of these
#: -- it says something first -- so the author's sentence survives.
_PASS_THROUGH_RE = re.compile(r"^forwarded to [\w.:`~ ]+\.?$", re.IGNORECASE)

#: Annotation text -> option type. Generators all carry ``from __future__
#: import annotations``, so an annotation reaches us as the source string
#: the author wrote, never as a typing object. Matched longest-first on
#: the normalised string, since ``"Optional[float]"`` contains ``"float"``.
_ANNOTATION_TYPES: tuple[tuple[str, OptionType], ...] = (
    ("bool", "bool"),
    ("list[str]", "str_list"),
    ("tuple", "float_pair"),
    ("float", "float"),
    ("int", "int"),
    ("str", "str"),
)

_TRUE = frozenset({"1", "true", "yes", "y", "on"})
_FALSE = frozenset({"0", "false", "no", "n", "off"})


class OptionError(ValueError):
    """A caller asked for an option this figure does not accept, or a value it cannot take.

    Carries the message the three front ends print verbatim: the CLI to
    stderr, the API as a 422 detail, the MCP host as a tool error. Written
    as one sentence plus the way out, because the reader is mid-command
    and wants the correction, not a taxonomy.
    """


class OptionDefinition(BaseModel):
    """One keyword a figure's generator accepts, described for a caller who cannot read Python.

    ``default`` is the generator's own default, verbatim: for several
    figures that is the demo caption ("Organic search fills the funnel,
    …"), which is exactly what a caller needs to see before deciding to
    replace it.
    """

    name: str = Field(description="Keyword name, as the generator declares it.")
    type: OptionType = Field(
        default="str",
        description="How a string from a command line or JSON is read into a Python value.",
    )
    default: Any = Field(
        default=None, description="What the generator uses when this option is omitted."
    )
    choices: list[str] = Field(
        default_factory=list,
        description="Closed set of accepted values; empty means any value of `type`.",
    )
    description: str = Field(
        default="", description="One-line help, taken from the generator's own docstring."
    )

    @computed_field(  # type: ignore[prop-decorator]
        description="Command-line spelling of this option, or '' when only --set reaches it."
    )
    @property
    def cli_flag(self) -> str:
        """``--x-label`` for ``x_label``; empty when the name is reserved by the CLI itself."""
        if self.name in RESERVED_CLI_NAMES:
            return ""
        return "--" + self.name.replace("_", "-")


def _option_type(annotation: Any, default: Any) -> OptionType:
    """Classify a parameter from its annotation, falling back to its default's type.

    An unannotated parameter is rare here but legal; its default still
    says what it is, and a default of ``None`` with no annotation leaves
    ``str``, which round-trips any value a caller types.
    """
    text = str(annotation).lower().replace(" ", "")
    if annotation is not inspect.Parameter.empty:
        for needle, option_type in _ANNOTATION_TYPES:
            if needle in text:
                return option_type
    if isinstance(default, bool):
        return "bool"
    if isinstance(default, int):
        return "int"
    if isinstance(default, float):
        return "float"
    if isinstance(default, tuple):
        return "float_pair"
    return "str"


_RST_ROLE_RE = re.compile(r":[a-z:]+:`~?([^`]+)`")
_SECTION_RE = re.compile(r"^(\w[\w ]*)\n-{3,}$", re.MULTILINE)


def _clean_rst(text: str) -> str:
    """Flatten the docstring markup that helps Sphinx and hurts a terminal."""
    text = _RST_ROLE_RE.sub(lambda m: m.group(1).rsplit(".", 1)[-1], text)
    text = text.replace("``", "").replace("`", "")
    return re.sub(r"\s+", " ", text).strip()


def _docstring_parameters(doc: str | None) -> dict[str, str]:
    """Map parameter name -> its prose, from a numpydoc ``Parameters`` section.

    Handles the shared-line form the generators use a lot (``title,
    subtitle : str or None``) by giving every name on the line the same
    description, which is what the author meant by writing them together.
    """
    if not doc:
        return {}
    body = inspect.cleandoc(doc)
    sections = {m.group(1): m.end() for m in _SECTION_RE.finditer(body)}
    start = sections.get("Parameters")
    if start is None:
        return {}
    ends = [m.start() for m in _SECTION_RE.finditer(body) if m.start() > start]
    block = body[start : ends[0] if ends else len(body)]

    described: dict[str, str] = {}
    names: list[str] = []
    prose: list[str] = []

    def flush() -> None:
        if names:
            text = _clean_rst(" ".join(prose))
            for name in names:
                described.setdefault(name, text)

    for line in block.splitlines():
        if not line.strip():
            continue
        if line[:1].isspace():  # continuation: the parameter's prose
            prose.append(line.strip())
            continue
        flush()
        head = line.split(":", 1)[0]
        names = [n.strip() for n in head.split(",") if n.strip().isidentifier()]
        prose = []
    flush()
    return described


def introspect_options(fn: Callable[..., Any]) -> dict[str, OptionDefinition]:
    """Read one generator's keyword surface off its signature and docstring.

    This is the derivation the catalogue builder freezes into
    ``figures.json``; a test calls it again against the live modules so
    that a generator which gains, loses or retypes a parameter fails
    instead of quietly outgrowing its published interface.

    Parameters
    ----------
    fn : callable
        A ``make_<kind>`` generator.

    Returns
    -------
    dict of str to OptionDefinition
        Keyed by parameter name, in signature order. ``data`` and ``out``
        are excluded: they are the caller's transport, not the figure's
        options.

    Examples
    --------
    >>> def make_demo(data=None, *, out=None, width: int = 900):
    ...     '''Draw it.
    ...
    ...     Parameters
    ...     ----------
    ...     width : int
    ...         Canvas width in pixels.
    ...     '''
    >>> options = introspect_options(make_demo)
    >>> options["width"].type, options["width"].default
    ('int', 900)
    """
    try:
        signature = inspect.signature(fn)
    except (TypeError, ValueError):  # pragma: no cover - builtins only
        return {}
    described = _docstring_parameters(fn.__doc__)
    options: dict[str, OptionDefinition] = {}
    for name, parameter in signature.parameters.items():
        if name in _NOT_OPTIONS or name.startswith("_"):
            continue
        if parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
            continue
        default = None if parameter.default is inspect.Parameter.empty else parameter.default
        if isinstance(default, tuple):
            default = list(default)
        written = described.get(name, "").strip()
        if not written or _PASS_THROUGH_RE.match(written):
            written = SHARED_DESCRIPTIONS.get(name, written)
        options[name] = OptionDefinition(
            name=name,
            type=_option_type(parameter.annotation, default),
            default=default,
            choices=list(OPTION_CHOICES.get(name, ())),
            description=written,
        )
    return options


def options_for(kind: str) -> dict[str, OptionDefinition]:
    """Every option the figure `kind` accepts, from the frozen catalogue.

    Reads ``catalog/figures.json``, so it costs no module import and is
    safe to call for all 127 kinds in a loop (the CLI's ``--describe``,
    the API's ``/kinds/{kind}/options``).

    Parameters
    ----------
    kind : str
        Chart kind name or alias; resolved the usual forgiving way.

    Returns
    -------
    dict of str to OptionDefinition
        Empty when the kind is unknown.
    """
    from .catalog import get_figure_definition, resolve_kind

    canonical = resolve_kind(kind)
    if canonical is None:
        return {}
    schema = get_figure_definition(canonical).options_schema
    return {
        name: payload
        if isinstance(payload, OptionDefinition)
        else OptionDefinition(**{"name": name, **payload})
        for name, payload in schema.items()
    }


def coerce_option(option: OptionDefinition, raw: Any) -> Any:
    """Read `raw` into the Python value the generator expects.

    A command line hands over strings and JSON hands over typed values;
    both arrive here so that ``--set width=1200`` and ``{"width": 1200}``
    reach the generator as the same ``int``.

    Parameters
    ----------
    option : OptionDefinition
        The option being set, from :func:`options_for`.
    raw : Any
        The value as typed or sent.

    Returns
    -------
    Any
        The coerced value.

    Raises
    ------
    OptionError
        If the text cannot be read as the option's type, or names a value
        outside a closed set.
    """
    value: Any = raw
    text = raw.strip() if isinstance(raw, str) else raw
    try:
        if option.type == "bool":
            if isinstance(raw, bool):
                value = raw
            elif str(text).lower() in _TRUE:
                value = True
            elif str(text).lower() in _FALSE:
                value = False
            else:
                raise ValueError(f"{raw!r} is not a yes/no value")
        elif option.type == "int":
            value = int(text)
        elif option.type == "float":
            value = float(text)
        elif option.type == "str_list":
            value = (
                [str(item) for item in raw]
                if isinstance(raw, (list, tuple))
                else [part.strip() for part in str(text).split(",") if part.strip()]
            )
        elif option.type == "float_pair":
            parts = raw if isinstance(raw, (list, tuple)) else str(text).split(",")
            pair = [float(part) for part in parts]
            if len(pair) != 2:
                raise ValueError("expected two numbers, 'low,high'")
            value = (pair[0], pair[1])
        else:
            value = str(text)
    except (TypeError, ValueError) as exc:
        raise OptionError(
            f"--{option.name.replace('_', '-')} expects {_type_hint(option)}; got {raw!r} ({exc})."
        ) from exc

    # Checked element by element, because a closed vocabulary is as common
    # on a list option as on a single one: control-chart's `rules` takes any
    # subset of four names. The earlier spelling compared `str(value)` to the
    # vocabulary, which for a list compares "['beyond']" to "beyond" and can
    # only ever fail -- so a list option could not declare choices at all,
    # and its values went unvalidated by both the CLI and the API.
    if option.choices:
        candidates = value if isinstance(value, list) else [value]
        rejected = [item for item in candidates if str(item) not in option.choices]
        if rejected:
            raise OptionError(
                f"{option.name}={raw!r} is not one of: {', '.join(option.choices)}."
                if len(candidates) == 1
                else f"{option.name}={raw!r} has {len(rejected)} value(s) outside "
                     f"{', '.join(option.choices)}: {', '.join(str(r) for r in rejected)}."
            )
    return value


def _type_hint(option: OptionDefinition) -> str:
    """How to spell this option's value, in the words a caller would use."""
    return {
        "bool": "true or false",
        "int": "a whole number",
        "float": "a number",
        "str_list": "a comma-separated list",
        "float_pair": "two numbers as 'low,high'",
        "str": "text",
    }[option.type]


def _unknown_option_message(kind: str, name: str, known: dict[str, OptionDefinition]) -> str:
    """Name the mistake, then the nearest real option, then every real one.

    Deliberately ends with the accepted names rather than with a command to
    run: the same sentence is read on a terminal, in a 422 body and by an
    MCP host, and only one of those three has a shell. Each front end adds
    its own "run this next" line.
    """
    close = difflib.get_close_matches(name, list(known), n=1, cutoff=0.6)
    hint = f" Did you mean {close[0]!r}?" if close else ""
    return (
        f"{kind} has no option named {name!r}.{hint} "
        f"It accepts: {', '.join(sorted(known)) or 'nothing but data'}."
    )


def validate_options(kind: str, options: dict[str, Any]) -> dict[str, Any]:
    """Check `options` against what `kind` accepts, and coerce every value.

    The three front ends call this before :func:`~sprezzature_figures.make_figure.make_figure`,
    which drops unknown keywords on purpose (shared chrome vocabulary is
    not a universal contract). Dropping is right for a library caller
    forwarding a bundle of chrome kwargs; it is wrong for a person who
    typed an option by hand and deserves to be told it did nothing.

    Parameters
    ----------
    kind : str
        Chart kind name or alias.
    options : dict
        Caller-supplied keywords, values typed or as text.

    Returns
    -------
    dict
        The same keys with coerced values, ready to pass as ``**kwargs``.

    Raises
    ------
    OptionError
        On an unknown option name, or a value of the wrong type.
    """
    known = options_for(kind)
    if not known:
        return dict(options)
    coerced: dict[str, Any] = {}
    for name, raw in options.items():
        option = known.get(name)
        if option is None:
            raise OptionError(_unknown_option_message(kind, name, known))
        coerced[name] = coerce_option(option, raw)
    return coerced


def parse_option_assignments(kind: str, assignments: list[str] | tuple[str, ...]) -> dict[str, Any]:
    """Turn repeated ``--set name=value`` arguments into coerced keywords.

    Parameters
    ----------
    kind : str
        Chart kind name or alias, used to look up what is accepted.
    assignments : list of str
        Raw ``name=value`` strings, in the order given.

    Returns
    -------
    dict
        Coerced keywords.

    Raises
    ------
    OptionError
        On a malformed assignment, a repeated name, an unknown option, or
        a value of the wrong type.

    Examples
    --------
    >>> parse_option_assignments("bar", ["width=1200", "theme=academic"])
    {'width': 1200, 'theme': 'academic'}
    """
    raw: dict[str, Any] = {}
    for assignment in assignments:
        if "=" not in assignment:
            raise OptionError(
                f"--set takes name=value; got {assignment!r}. Example: --set subtitle='Q3 figures'."
            )
        name, _, value = assignment.partition("=")
        name = name.strip().replace("-", "_")
        if name in raw:
            raise OptionError(f"--set {name} given twice; keep one.")
        raw[name] = value
    return validate_options(kind, raw)


def describe_options(kind: str) -> str:
    """A terminal-shaped listing of everything `kind` accepts beyond its data.

    One line per option: its flag, its type, the generator's own default
    and the prose from the generator's docstring. Printed by
    ``make-figure <kind> --describe`` and by the Click twin's ``describe``
    command.

    Parameters
    ----------
    kind : str
        Chart kind name or alias.

    Returns
    -------
    str
        The listing, or a one-line note when the kind takes no options.
    """
    options = options_for(kind)
    if not options:
        return f"{kind} declares no options."
    lines = []
    for option in options.values():
        flag = option.cli_flag or f"--set {option.name}=VALUE"
        shown = "" if option.default is None else f"  [default: {option.default!r}]"
        values = (
            f"  one of: {', '.join(option.choices)}"
            if option.choices
            else f"  {_type_hint(option)}"
        )
        lines.append(f"  {flag}{values}{shown}")
        if option.description:
            lines.extend(
                textwrap.wrap(
                    option.description,
                    width=76,
                    initial_indent="      ",
                    subsequent_indent="      ",
                )
            )
    return "\n".join(lines)
