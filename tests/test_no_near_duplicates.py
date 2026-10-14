"""
Two figures that take the same data and sit in the same drawer had better be two figures.

A catalogue this size grows by addition, and the cheapest way to grow it
badly is to add a chart that is another chart with a different name. The
reader then has to choose between two entries that look identical from the
outside -- same category, same required columns -- and the catalogue's size
stops being a measure of what it can draw.

The check is deliberately crude, because a subtle one would not fire: two
kinds clash when they declare the **same category and the same required
roles**. That is the shape of a duplicate as a *caller* meets it, which is
the only shape that matters. Every clash the catalogue already contains is
listed below with the sentence that distinguishes the pair -- and writing
that sentence is the point: a pair that cannot be told apart in one line
probably should not be two kinds.

Author
------
Warith HARCHAOUI <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import collections

from sprezzature_figures.catalog import get_figure_definition, list_kinds

#: Pairs that look alike from the outside and are not, with why. Each entry
#: is a promise a reader can check against the two figures.
DISTINCT_PAIRS: dict[tuple[str, ...], str] = {
    ("funnel", "funnel-area"): (
        "The same stages drawn two ways, and the difference is what the "
        "shape is for. A funnel is horizontal bars whose length is the "
        "count: comparable, measurable, and honest because equal heights "
        "make area follow length. A funnel-area is a tapering silhouette "
        "carved so each band's *area* is the count, which is the form "
        "presentations want and the one that lies unless the heights are "
        "solved for. Reach for funnel when the numbers are the point; for "
        "funnel-area when the shape is, and you want the taper without "
        "the taper misreporting."
    ),
    ("candlestick", "ohlc"): (
        "The same four prices drawn two ways, and the difference is what "
        "survives. A candlestick fills the body between open and close, so "
        "direction is an area and reads instantly -- in colour. An OHLC bar "
        "ticks the open to the left and the close to the right, so direction "
        "is a *position* and survives a monochrome print and a red-green "
        "reader. Candlestick when the chart is screen-first and the reader "
        "wants the sweep; OHLC when it has to hold up in print, or when the "
        "bodies would crowd into a solid block at the density on hand."
    ),
    ("beeswarm", "strip"): (
        "A strip plot jitters points at random; a beeswarm packs them so none "
        "overlap, which costs the exact position and buys an honest count. Reach "
        "for strip when the shape of the distribution is the question and the rows "
        "number in the thousands; for beeswarm when every point is a case the "
        "reader may want to find, and there are few enough to place."
    ),
    ("radial-tree", "tree"): (
        "The same hierarchy laid out two ways, solving opposite crowding. Reach for "
        "tree when the structure is deep and narrow and depth is what the reader "
        "follows; for radial-tree when it is shallow and wide, where a tidy layout "
        "runs out of page sideways long before it runs out of levels."
    ),
    ("surface3d", "wireframe3d"): (
        "A filled surface reads height by shading and hides whatever is behind it; a "
        "wireframe shows the far side through the near one and reads the mesh's "
        "shape. A surface for a landscape, a wireframe for a function with folds."
    ),
    ("upset", "venn"): (
        "A Venn diagram draws every intersection as an area and stops working at "
        "four sets; an UpSet plot draws intersections as a matrix of columns and "
        "keeps working at twenty. Venn when the picture is the argument, UpSet when "
        "the counts are."
    ),
}


def _clashes() -> dict[tuple[str, tuple[str, ...]], list[str]]:
    """Kinds grouped by the pair a caller sees: category and required columns."""
    grouped: dict[tuple[str, tuple[str, ...]], list[str]] = collections.defaultdict(list)
    for kind in list_kinds():
        definition = get_figure_definition(kind)
        roles = tuple(sorted(role.name for role in definition.required_roles))
        grouped[(definition.category, roles)].append(kind)
    return {key: kinds for key, kinds in grouped.items() if len(kinds) > 1}


def test_every_look_alike_pair_says_how_it_differs() -> None:
    """A new figure that collides with an old one has to earn its entry.

    Failing here is not a verdict that the figure is a duplicate; it is a
    request for the sentence that says it is not. If that sentence cannot
    be written, the figure is an option on an existing kind rather than a
    kind of its own.
    """
    undocumented = [
        (category, roles, kinds)
        for (category, roles), kinds in _clashes().items()
        if tuple(sorted(kinds)) not in DISTINCT_PAIRS
    ]
    assert undocumented == [], (
        "these share a category and a set of required columns, and nothing says how "
        "they differ:\n  "
        + "\n  ".join(
            f"{', '.join(kinds)} ({category}, needs {list(roles)})"
            for category, roles, kinds in undocumented
        )
        + "\nAdd the distinguishing sentence to DISTINCT_PAIRS, or fold one into the other."
    )


def test_the_distinguishing_notes_name_real_kinds() -> None:
    """A renamed or removed figure must not leave a promise behind."""
    known = set(list_kinds())
    dangling = sorted(
        {kind for pair in DISTINCT_PAIRS for kind in pair if kind not in known}
    )
    assert dangling == [], f"DISTINCT_PAIRS names kinds that no longer exist: {dangling}"


def test_no_note_describes_a_pair_that_no_longer_collides() -> None:
    """When two figures stop looking alike, the note has done its job and can go.

    Not cosmetic: a stale entry is a licence to add a real duplicate under
    a name that happens to match it.
    """
    colliding = {tuple(sorted(kinds)) for kinds in _clashes().values()}
    stale = sorted(pair for pair in DISTINCT_PAIRS if pair not in colliding)
    assert stale == [], f"these no longer share a category and roles; drop the note: {stale}"


def test_each_note_is_a_sentence_a_reader_can_use() -> None:
    """A note that says "they are different" documents nothing."""
    thin = {
        pair: note
        for pair, note in DISTINCT_PAIRS.items()
        if len(note) < 80 or not any(word in note.lower() for word in ("when", "for", "than"))
    }
    assert thin == {}, (
        "these notes do not say when to reach for one rather than the other: "
        f"{sorted(thin)}"
    )


def test_no_two_kinds_share_a_name_or_an_alias() -> None:
    """The registry resolves a name to one figure, so two must never claim it."""
    claimed: dict[str, str] = {}
    collisions: list[str] = []
    for kind in list_kinds():
        definition = get_figure_definition(kind)
        for name in [definition.kind, *definition.aliases]:
            normalised = name.lower().replace("-", "_").replace(" ", "_")
            if normalised in claimed and claimed[normalised] != kind:
                collisions.append(f"{name!r}: {claimed[normalised]} and {kind}")
            claimed[normalised] = kind
    assert collisions == [], f"a name resolves to two figures: {collisions}"
