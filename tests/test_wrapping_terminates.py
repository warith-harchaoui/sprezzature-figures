"""
``wrap_to_width`` must return. It did not, on a sentence ending in a run of
function words.

Two rules used to run against each other. The orphan pass pushes a dangling
function word off the end of a line onto the next one; a companion rule split
one off the *last* line onto a line of its own. On "... so an install says what
it is for.", the second rule handed a word to a line the first rule then handed
straight back, forever. The caller got no bad line break and no exception: it
got a process that never came back, which is the hardest shape of failure to
attribute. The fix exempts the last line, which is also the right reading: a
function word at the end of the text is the end of the sentence, not something
left hanging.

The guard runs the call on a thread and gives it five seconds. A plain call
would hang the test session instead of failing it, and a hung job reads as a
slow runner rather than as a bug.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from _textfit import _ends_on_orphan, wrap_to_width  # noqa: E402

#: Sentences whose tail is function words. Each one hung before the fix.
TRAILING_FUNCTION_WORDS = [
    "The lint has no dependencies at all, which is what makes it worth a "
    "pre-commit hook. Everything heavier is an extra named after the tool "
    "that needs it, so an install says what it is for.",
    "Twenty rules a browser never has to run, and the alt text they ask for.",
    "a theme.extend.colors snippet or a full configuration, so no project in "
    "the stack hand-copies a hex code from",
    "Chaque brique fait ce qu'elle sait faire et rend la main à",
]


def _wrap_within(text: str, max_px: float, size: float, seconds: float = 5.0) -> list[str]:
    """Call ``wrap_to_width`` on a thread and fail the test if it does not return."""
    out: list[list[str] | None] = [None]

    def run() -> None:
        out[0] = wrap_to_width(text, max_px, size)

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(seconds)
    assert not worker.is_alive(), (
        f"wrap_to_width did not return within {seconds:g}s on {text[:60]!r}... "
        "The orphan pass and the trailing rule are handing the same word back "
        "and forth."
    )
    result = out[0]
    assert result is not None
    return result


def test_a_sentence_ending_in_function_words_wraps() -> None:
    """Every one of these returns, at several widths, with nothing lost."""
    for text in TRAILING_FUNCTION_WORDS:
        for max_px, size in ((820.0, 13.5), (400.0, 13.5), (180.0, 16.0)):
            lines = _wrap_within(text, max_px, size)
            assert lines, (text, max_px)
            assert "".join(lines).replace(" ", "") == text.replace(" ", ""), (
                f"the wrap dropped or duplicated words: {lines}"
            )


def test_the_last_word_of_a_sentence_stays_on_the_last_line() -> None:
    """A trailing function word is the end of the sentence, not an orphan.

    The old rule gave "... they ask for." a second line holding the single
    word "for.", in a box eight hundred pixels wide.
    """
    text = "Twenty rules a browser never has to run, and the alt text they ask for."
    lines = _wrap_within(text, 820.0, 13.5)
    assert lines == [text], lines


def test_the_orphan_rule_still_does_its_job() -> None:
    """The fix must not switch the rule off: a line before the last still loses its orphan."""
    lines = _wrap_within(
        "The ring is one full year; follow it clockwise from the top.", 180.0, 15.0
    )
    assert len(lines) > 1, lines
    for line in lines[:-1]:
        assert not _ends_on_orphan(line), lines
