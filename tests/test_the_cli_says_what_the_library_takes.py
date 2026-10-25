"""
A generator whose library takes a language lets its command line say one.

``build_svg(language=…)`` picks the chrome text a figure prints in — the
labels and the one-sentence finding it narrates. Sixteen generators take it.
``make_bollinger`` was one of them and its ``--help`` had no ``--language``:
it built its own ``argparse.ArgumentParser`` from scratch instead of the
shared ``_argparse.make_parser``, and the flag went missing with everything
else that helper carries. ``main()`` never passed one either, so even a caller
who guessed the flag got English.

Two surfaces of one engine disagreeing is what ``SURFACES.md`` forbids, and
here it had a price. ``web/tools/build_figure_kits.py`` decides a generator is
bilingual by looking for ``language`` in the **library** signature, then runs
the **script** with ``--language``. For this one figure both kits failed to
build, in both languages, and the gallery card went on offering a zip from
13 September — a month and a half stale — because the kit zips are build
artefacts nothing validates against the generators they contain.

Asked of the command line itself rather than of the source text. Fifteen other
generators pass this and none of them writes ``--language`` anywhere: they get
it from the shared parser, which is the right way and invisible to a grep. A
guard that reads source would have called all fifteen broken.

And asked by *rendering*, not by ``--help``. The first version of this ran
``--language fr --help`` on the theory that argparse rejects an unknown option
before it reaches the help action. It does not: ``parse_args`` collects
unrecognised arguments and complains about them at the end, while ``--help``
fires during the walk and exits 0 first. So the check passed with the flag
deleted, which is the only thing a guard must never do. Rendering costs a
quarter of a second per figure and also covers the second half of the defect —
``main()`` not forwarding the flag it parsed.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

#: ``def make_<slug>(`` through to its ``) ->``: the library signature, read
#: as text so this costs nothing and imports nothing.
_SIGNATURE = re.compile(r"^def (make_\w+)\((.*?)\) ->", re.M | re.S)


def _takes_language(source: str) -> bool:
    for _, parameters in _SIGNATURE.findall(source):
        if re.search(r"\blanguage\b\s*:", parameters):
            return True
    return False


BILINGUAL: list[Path] = sorted(
    path
    for path in SCRIPTS.glob("make_*.py")
    if _takes_language(path.read_text(encoding="utf-8", errors="replace"))
)


@pytest.mark.parametrize("script", BILINGUAL, ids=lambda p: p.stem)
def test_a_bilingual_generator_renders_in_the_language_it_is_given(
    script: Path, tmp_path: Path
) -> None:
    """The whole path: the flag parses, and ``main()`` hands it on."""
    out = tmp_path / f"{script.stem}.svg"
    done = subprocess.run(
        [sys.executable, str(script), "--language", "fr", "--out", str(out)],
        capture_output=True, text=True, timeout=180,
    )
    assert done.returncode == 0, (
        f"{script.name} takes a `language` in its library signature and its "
        f"command line will not render with one: "
        f"{(done.stderr.strip().splitlines() or ['(no output)'])[-1]}"
    )
    assert out.is_file() and out.stat().st_size > 0, (
        f"{script.name} exited 0 and wrote nothing to {out}"
    )


def test_there_are_bilingual_generators_to_check() -> None:
    """A pattern that stopped matching would make every case above vanish."""
    assert len(BILINGUAL) >= 10, (
        f"found {len(BILINGUAL)} generators whose library takes a language; "
        f"the catalogue has sixteen"
    )
