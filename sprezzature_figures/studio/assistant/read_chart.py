"""
Look at a picture of a chart and say what it is.

One vision call, one typed answer. The model is handed the image and the
catalogue's kind names -- nothing else -- and must pick its answer out of
that list, the same rule ``recommend.explain_recommendations`` applies to
figure recommendations: naming a kind outside the list it was given is a
hard error, not a result to be repaired downstream.

The kinds are sent as bare ``name (Category)`` lines rather than with their
descriptions. The full catalogue with descriptions is 12 KB of prompt, most
of it explaining chart types a vision model already recognises on sight;
the category is what disambiguates the handful of names that are genuinely
ambiguous out of context.

Author
------
Warith HARCHAOUI <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from sprezzature_figures.catalog import FigureDefinition, get_registry, resolve_kind

from .client import LLMClient
from .schemas import ChartReading

READ_CHART_SYSTEM = (
    "You are shown a picture of an existing chart -- often a rough or hard-to-read one -- "
    "and your job is to say what it is so it can be redrawn well.\n"
    "Return a single JSON object matching the given schema.\n"
    "Two rules decide whether your answer is usable:\n"
    "1. `kind` MUST be copied exactly from the candidate list you are given. Naming "
    "anything outside that list is a hard error. If the original is drawn as a poor "
    "choice for what it shows, name the kind that would show it well instead.\n"
    "2. NEVER invent numbers. Fill `series[].values` only from printed data labels or a "
    "gridded axis you can read without estimating, and set `values_are_readable` to "
    "false whenever you are inferring magnitudes from the size or position of a mark. An "
    "empty values list is a correct answer; a plausible-looking wrong one is not.\n"
    "Copy title, subtitle and axis titles verbatim from the image -- do not translate or "
    "improve them; `suggested_title` is where a better title goes.\n"
    "Fill EVERY field of the schema. `drawn_as`, `what_it_shows` and `suggested_title` "
    "are judgements about a picture you can see, not facts you might be missing: leave "
    "them empty only if the image is genuinely unreadable.\n"
    "In `issues`, report what costs the reader effort: duplicated axes, dashed lines "
    "competing with data, two warm hues carrying the whole signal, a legend parked away "
    "from the marks it names, a title that describes the contents instead of the result. "
    "Judge the reading load, not the analysis."
)


class ChartReadingError(ValueError):
    """The model's answer could not be trusted as a reading of the image."""


def candidate_lines(candidates: list[FigureDefinition]) -> str:
    """The candidate list as the prompt sends it: one ``kind (Category)`` per line."""
    return "\n".join(f"- {d.kind} ({d.category})" for d in candidates)


def read_chart_prompt(candidates: list[FigureDefinition], *, hint: str = "") -> str:
    """The user half of the vision call."""
    parts = []
    if hint:
        parts.append(f"What the person who sent this image says about it: {hint!r}\n")
    parts.append(
        "Look at the attached image of a chart and describe it against the schema.\n\n"
        f"Candidate chart kinds -- `kind` must be one of these {len(candidates)} names, "
        f"copied exactly:\n{candidate_lines(candidates)}\n\n"
        "Report what the chart shows, the text printed on it, the series you can make "
        "out, whether its numbers are genuinely readable, and what makes it harder to "
        "read than it needs to be."
    )
    return "".join(parts)


def read_chart(
    client: LLMClient,
    image: bytes,
    *,
    candidates: list[FigureDefinition] | None = None,
    hint: str = "",
) -> ChartReading:
    """Read `image` into a :class:`ChartReading`.

    Parameters
    ----------
    client : LLMClient
        Anything satisfying the client protocol; a vision-capable model is
        required, since this is the one call in the package that must look.
    image : bytes
        The picture, as raster bytes (PNG/JPEG/WebP).
    candidates : list of FigureDefinition, optional
        The kinds the model may choose from. Defaults to every stable kind
        in the registry.
    hint : str, optional
        Whatever the user said about the image -- what it is, what they wish
        it showed. Free text, passed through to the prompt.

    Returns
    -------
    ChartReading
        With ``kind`` resolved to a canonical registry kind.

    Raises
    ------
    ChartReadingError
        If the model named a kind outside the candidate list. Not repaired:
        a reading whose one structured field was disregarded is not evidence
        about the image, and the caller can always name the kind itself.
    """
    if candidates is None:
        candidates = [d for d in get_registry() if d.status == "stable"]
    if not candidates:
        raise ChartReadingError("no candidate kinds to choose from")

    reading = client.chat_vision(
        read_chart_prompt(candidates, hint=hint),
        image,
        system=READ_CHART_SYSTEM,
        response_model=ChartReading,
        temperature=0.1,
    )
    assert isinstance(reading, ChartReading)

    allowed = {d.kind for d in candidates}
    canonical = resolve_kind(reading.kind)
    if canonical is None or canonical not in allowed:
        raise ChartReadingError(
            f"the model answered kind={reading.kind!r}, which is not one of the "
            f"{len(allowed)} candidates it was given. Name the kind yourself to skip "
            f"this step."
        )
    reading.kind = canonical
    return reading
