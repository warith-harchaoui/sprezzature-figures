"""The Ralph loop's VLM critique is keyed on the pixels, not on the path.

The defect this guards. ``ralph_eyeball_loop.py --local`` sends a PNG to
``qwen3-vl:8b`` and the loop's own message says "first call loads the model,
~30 s cold". Nothing was memoized. The critique is written to
``.private/ralph-loop/assessment-<hash>.md``, which looks exactly like
content-addressed storage, but ``_source_hash`` hashes the resolved *path* --
and it is right to, because that file is a journal and iteration 2 is appended
under iteration 1. So the one thing in the loop that looked like a cache was
not one, and two runs over an unchanged figure repaid the whole inference.

Measured on ``assets/svg-examples/elbow.svg`` rendered at 700 px, with the
model already resident in memory so neither number includes a cold load:

* before -- two identical calls, **121.3 s** then **94.6 s**;
* after  -- **94.98 s** for the first call, then **0.0032 s** from a *separate
  process*, same 2 938-character critique.

The second number is also an argument about truth and not only about time. The
two "before" critiques came back 3 039 and 3 495 characters long: an unchanged
figure drew a different verdict each run, and the journal's next iteration read
as progress when nothing had been edited.

What this asserts is the four properties ``wallet_helper`` has that a
hand-rolled JSON dictionary does not, because "does it cache" is not the
question:

1. **Content addressing.** The same bytes reached by a different path hit;
   one byte different at the same path misses. This is precisely the direction
   a path hash cannot do -- the same shape as the ``os_helper.hashfile``
   defect found the same morning, which returned a digest of the path when
   asked for a digest of the content, and therefore could not notice that the
   file was not there at all.
2. **Survival across processes.** A fresh wallet over the same ledger file
   reuses what the previous one stored. An in-process dict cannot.
3. **Cross-process single-flight.** Two processes starting together on the
   same key run the heavy call *once*, the loser waiting on the winner.
   Measured both ways: with ``SqliteLedger`` the call ran once, with the
   default JSON ``Ledger`` it ran twice.
4. **A bound.** ``max_entries`` is set, so the store cannot grow for ever --
   the difference between a cache and a directory that only accumulates.

The model is never called here. ``_llm_chat`` is replaced by a counter, so
what is under test is the key and the ledger, not Ollama.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
LOOP = REPO_ROOT / "scripts" / "ralph_eyeball_loop.py"

wallet_helper = pytest.importorskip(
    "wallet_helper",
    reason="wallet-helper is declared in the `dev` and `local` extras; install one",
)

#: Two PNGs that differ in one byte. Not real PNGs -- nothing decodes them
#: here, and the point is the digest, not the image.
_PIXELS_A = b"\x89PNG\r\n\x1a\n" + b"pretend-this-is-a-chart" * 40
_PIXELS_B = _PIXELS_A[:-1] + b"X"


@pytest.fixture
def loop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """The loop module, with its ledger redirected into ``tmp_path``.

    Loaded by path because the file is a script rather than a package module,
    and re-loaded per test so that ``_critique_wallet``'s ``lru_cache`` cannot
    carry one test's ledger into the next.
    """
    spec = importlib.util.spec_from_file_location("ralph_eyeball_loop", LOOP)
    assert spec and spec.loader, f"cannot load {LOOP}"
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(LOOP.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(LOOP.parent))
    monkeypatch.setattr(module, "_CRITIQUE_LEDGER", tmp_path / "critique-ledger.db")
    module._critique_wallet.cache_clear()
    return module


def _counting_model(calls: list[bytes]) -> Any:
    """A stand-in for ``_llm_chat`` that records every call it actually serves."""

    def chat(prompt: str, images: list[bytes], model: str) -> str:
        calls.append(images[0])
        return f"critique #{len(calls)} of {len(images[0])} bytes by {model}"

    return chat


def test_the_same_pixels_at_a_different_path_are_not_paid_for_twice(
    loop: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Content addressing, in the direction a path hash cannot reach."""
    calls: list[bytes] = []
    monkeypatch.setattr(loop, "_llm_chat", _counting_model(calls))

    here = tmp_path / "figure.png"
    here.write_bytes(_PIXELS_A)
    elsewhere = tmp_path / "copies" / "renamed.png"
    elsewhere.parent.mkdir()
    elsewhere.write_bytes(_PIXELS_A)

    first = loop._vlm_critique(here, "svg")
    assert len(calls) == 1, "the first critique did not reach the model"
    second = loop._vlm_critique(elsewhere, "svg")
    assert len(calls) == 1, (
        "the same bytes under a second path paid for the inference again, which is "
        "what keying on the path does"
    )
    assert first == second, "the stored critique came back altered"


def test_one_byte_of_difference_is_a_different_figure(
    loop: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """And the other direction: the same path with edited pixels must miss.

    This is the half a path key gets wrong in the expensive direction -- it
    would serve the old critique of a figure that has been fixed since.
    """
    calls: list[bytes] = []
    monkeypatch.setattr(loop, "_llm_chat", _counting_model(calls))

    png = tmp_path / "figure.png"
    png.write_bytes(_PIXELS_A)
    loop._vlm_critique(png, "svg")
    png.write_bytes(_PIXELS_B)
    loop._vlm_critique(png, "svg")
    assert len(calls) == 2, (
        "the figure was edited and the loop served the critique of the old pixels"
    )
    assert calls[0] != calls[1]


def test_the_prompt_and_the_model_are_in_the_key(
    loop: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """All three inputs the critique is a function of, not just the image.

    A web page and an SVG get different prompts for the same pixels, and the
    model name is a per-call override, so either changing without the key
    changing would serve an answer to a question nobody asked.
    """
    calls: list[bytes] = []
    monkeypatch.setattr(loop, "_llm_chat", _counting_model(calls))
    png = tmp_path / "figure.png"
    png.write_bytes(_PIXELS_A)

    loop._vlm_critique(png, "svg")
    assert loop._build_critique_prompt("html") != loop._build_critique_prompt("svg"), (
        "the fixture assumes the html prompt differs from the svg one"
    )
    loop._vlm_critique(png, "html")
    assert len(calls) == 2, "the surface kind changed the prompt but not the key"

    monkeypatch.setattr(loop, "_VISION_MODEL", "qwen3-vl:4b")
    loop._vlm_critique(png, "svg")
    assert len(calls) == 3, "the model name changed but the key did not"


def test_the_store_outlives_the_process_that_wrote_it(
    loop: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second wallet over the same file reuses the first one's work.

    An in-process dictionary gives everything above and not this, and this is
    the property the loop needs: each run of the script is a new process.
    """
    calls: list[bytes] = []
    monkeypatch.setattr(loop, "_llm_chat", _counting_model(calls))
    png = tmp_path / "figure.png"
    png.write_bytes(_PIXELS_A)

    stored = loop._vlm_critique(png, "svg")
    assert len(calls) == 1
    # Drop the wallet entirely, as ending the process would.
    loop._critique_wallet.cache_clear()
    assert loop._vlm_critique(png, "svg") == stored
    assert len(calls) == 1, "a new wallet over the same ledger re-ran the inference"


def test_asking_again_is_possible_and_is_recorded(
    loop: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--no-critique-cache`` reaches the model and refreshes what is stored.

    The model is not deterministic, so a second opinion on the same pixels is
    a real thing to want; a cache with no way past it would have taken it
    away.
    """
    calls: list[bytes] = []
    monkeypatch.setattr(loop, "_llm_chat", _counting_model(calls))
    png = tmp_path / "figure.png"
    png.write_bytes(_PIXELS_A)

    first = loop._vlm_critique(png, "svg")
    fresh = loop._vlm_critique(png, "svg", use_cache=False)
    assert len(calls) == 2, "--no-critique-cache consulted the store anyway"
    assert fresh != first, "the stand-in model was supposed to answer differently"


def test_the_store_is_bounded(loop: Any) -> None:
    """``max_entries`` is set, so the ledger cannot grow without end."""
    assert loop._CRITIQUE_MAX_ENTRIES > 0
    ledger = wallet_helper.SqliteLedger(loop._CRITIQUE_LEDGER, max_entries=3)
    for index in range(6):
        ledger.put(f"k{index}", {"critique": "x" * 100})
    survivors = [f"k{index}" for index in range(6) if ledger.has(f"k{index}")]
    assert survivors == ["k3", "k4", "k5"], f"eviction kept {survivors} instead of the newest three"


def test_a_backend_failure_leaves_no_poisoned_claim(
    loop: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A call that raises is not stored, and the next caller may retry.

    The reason ``_VisionBackendUnreachable`` exists rather than letting
    ``SystemExit`` -- a ``BaseException`` -- travel through the ledger's
    in-flight bookkeeping.
    """
    png = tmp_path / "figure.png"
    png.write_bytes(_PIXELS_A)

    def unreachable(prompt: str, images: list[bytes], model: str) -> str:
        raise ConnectionError("read timed out")

    monkeypatch.setattr(loop, "_llm_chat", unreachable)
    with pytest.raises(SystemExit) as failure:
        loop._vlm_critique(png, "svg")
    assert "ollama serve" in str(failure.value), "the install hint was lost"

    calls: list[bytes] = []
    monkeypatch.setattr(loop, "_llm_chat", _counting_model(calls))
    loop._critique_wallet.cache_clear()
    loop._vlm_critique(png, "svg")
    assert len(calls) == 1, "the failed call left a claim the next caller waited on"


#: Two processes racing the same key, each writing a line per real execution.
#: The count of lines is the number of times the heavy call actually ran.
_RACE_WORKER = textwrap.dedent(
    """
    import sys, time
    from pathlib import Path
    import wallet_helper as wh

    db, marker, backend = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    ledger = wh.SqliteLedger(db) if backend == "sqlite" else wh.Ledger(db.parent)
    wallet = wh.Wallet(ledger)

    def heavy():
        with marker.open("a") as handle:
            handle.write("ran\\n")
        time.sleep(2.0)
        return "CRITIQUE"

    wallet.call("ns", {"png": b"same-pixels", "prompt": "p", "model": "m"}, heavy)
    """
)


@pytest.mark.slow
@pytest.mark.parametrize(
    ("backend", "expected_runs"),
    [("sqlite", 1), ("json", 2)],
)
def test_two_loops_on_one_figure_collapse_into_one_inference(
    tmp_path: Path, backend: str, expected_runs: int
) -> None:
    """The reason the backend is ``SqliteLedger`` and not the default.

    Parametrised over both backends because the number that justifies the
    choice is the *difference*: one execution against two. Asserting only the
    SQLite side would pass just as well if single-flight did nothing and the
    two processes simply never overlapped.
    """
    worker = tmp_path / "worker.py"
    worker.write_text(_RACE_WORKER, encoding="utf-8")
    database = tmp_path / backend / "ledger.db"
    database.parent.mkdir()
    marker = tmp_path / backend / "ran.txt"
    # Create the database first: two processes racing the *creation* of the
    # file collide inside SqliteLedger's own `PRAGMA journal_mode=WAL`, which
    # is a different thing from the single-flight under test here (and the
    # reason `_critique_wallet` retries).
    if backend == "sqlite":
        wallet_helper.SqliteLedger(database)

    racers = [
        subprocess.Popen(  # noqa: S603 - fixed argv, no shell
            [sys.executable, str(worker), str(database), str(marker), backend]
        )
        for _ in range(2)
    ]
    for racer in racers:
        assert racer.wait(timeout=120) == 0, "a racing worker failed"

    runs = marker.read_text(encoding="utf-8").count("ran")
    assert runs == expected_runs, (
        f"with the {backend} ledger the heavy call ran {runs} time(s), expected {expected_runs}"
    )
