"""
Mermaid and ``mmdc`` are gone from this package; ``flowchart`` draws diagrams.

The decision (Warith HARCHAOUI, 2026-11-08) has three halves, and each needs
its own guard, because a removal fails in three different ways:

* a file written in that language must be turned away with one sentence that
  says what to do instead, not a traceback and not an "unknown suffix";
* the command that sentence names must exist;
* the name must not grow back in the docs, the docstrings and the help. The
  sweep runs over every tracked text file, so a new page is covered the day
  it lands, and it has exactly two exemptions: the suffix tuple the refusal
  needs, and the one row of TRIGGERS.md that routes the request to
  ``flowchart``.

CHANGELOG.md is exempt whole: history is not rewritten.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from sprezzature_figures.cli import cli

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

TOOLS = ["render_diagram.py", "ralph_eyeball_loop.py"]
REFUSED_NAMES = ["flow.mmd", "flow.mermaid", "FLOW.MMD", "a.b.mermaid"]
ADVICE = "sprezzature-figures render flowchart"

_NAME = re.compile(r"mermaid|mmdc|\.mmd\b", re.IGNORECASE)
_BASE64 = re.compile(r"base64,[A-Za-z0-9+/=]+")
_TEXT_SUFFIXES = {
    ".md",
    ".py",
    ".csv",
    ".yml",
    ".yaml",
    ".toml",
    ".txt",
    ".sh",
    ".svg",
    ".html",
    ".json",
    ".ini",
}
_SUFFIX_TUPLE = '(".mmd", ".mermaid")'


def _run(tool: str, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / tool), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=120,
    )


@pytest.mark.parametrize("tool", TOOLS)
@pytest.mark.parametrize("name", REFUSED_NAMES)
def test_a_source_in_that_language_is_a_usage_error(tool: str, name: str, tmp_path: Path) -> None:
    """Exit 2, one sentence, no traceback, and the command to use instead."""
    source = tmp_path / name
    source.write_text("graph TD\n  A --> B\n", encoding="utf-8")
    done = _run(tool, str(source), cwd=tmp_path)
    assert done.returncode == 2, done.stderr
    assert done.stdout == ""
    lines = done.stderr.strip().splitlines()
    assert len(lines) == 1, done.stderr
    assert ADVICE in lines[0]
    assert source.name in lines[0]
    assert "Traceback" not in done.stderr


@pytest.mark.parametrize("tool", TOOLS)
def test_the_refusal_needs_no_file_on_disk(tool: str, tmp_path: Path) -> None:
    """A mistyped path still gets the advice rather than "file not found"."""
    done = _run(tool, str(tmp_path / "absent.mmd"), cwd=tmp_path)
    assert done.returncode == 2
    assert ADVICE in done.stderr


def test_the_refusal_writes_nothing(tmp_path: Path) -> None:
    """The loop stops before its output directory, so no empty journal is left."""
    (tmp_path / "flow.mmd").write_text("graph TD\n", encoding="utf-8")
    copy = tmp_path / "ralph_eyeball_loop.py"
    copy.write_bytes((SCRIPTS / "ralph_eyeball_loop.py").read_bytes())
    done = subprocess.run(
        [sys.executable, str(copy), "flow.mmd"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        timeout=120,
    )
    assert done.returncode == 2, done.stderr
    assert not (tmp_path / ".private").exists()


def test_the_command_the_refusal_names_renders(tmp_path: Path) -> None:
    """Advice pointing at a command that broke would be worse than none."""
    rows = tmp_path / "arrows.csv"
    rows.write_text("source,target\nUpload,Render\n", encoding="utf-8")
    out = tmp_path / "flow.svg"
    done = CliRunner().invoke(
        cli, ADVICE.split()[1:] + ["--data", str(rows), "--out", str(out)], catch_exceptions=False
    )
    assert done.exit_code == 0, done.output
    assert "Upload" in out.read_text(encoding="utf-8")


def test_content_alone_no_longer_routes_to_a_third_kind() -> None:
    """Without a decisive suffix, a diagram-language body is simply unknown."""
    import render_diagram

    assert render_diagram.KINDS == ("tikz", "svg")
    with pytest.raises(SystemExit, match="Could not detect"):
        render_diagram.detect_kind("flow.txt", "graph TD\n  A --> B\n")
    with pytest.raises(SystemExit, match="Could not detect"):
        render_diagram.detect_kind("flow.txt", "%%{init: {}}%%\nflowchart LR\n")


def test_the_tikz_and_svg_routes_still_stand() -> None:
    """What the removal left behind still detects and themes as before."""
    import render_diagram

    assert render_diagram.detect_kind("a.svg", "") == "svg"
    assert render_diagram.detect_kind("a.tikz", "") == "tikz"
    assert render_diagram.detect_kind("a.txt", "<svg></svg>") == "svg"
    assert render_diagram.detect_kind("a.txt", r"\documentclass{standalone}") == "tikz"
    themed = render_diagram.themed_source("tikz", r"\draw (0,0) -- (1,1);", False, True)
    assert r"\definecolor{sprezzatureFg}" in themed
    assert render_diagram.themed_source("svg", "<svg/>", False, True) == "<svg/>"


@pytest.mark.parametrize("flag", ["--check-tools", "--install-tools"])
def test_the_toolchain_commands_do_not_list_it(flag: str, tmp_path: Path) -> None:
    """Neither the name nor the Node install command appears in either report."""
    done = _run("ralph_eyeball_loop.py", flag, cwd=tmp_path)
    assert done.returncode == 0, done.stderr
    assert not _NAME.search(done.stdout)
    assert "npm" not in done.stdout


def _offending_lines(path: Path) -> list[str]:
    text = _BASE64.sub("", path.read_text(encoding="utf-8", errors="replace"))
    return [line for line in text.splitlines() if _NAME.search(line)]


def _tracked_text_files() -> list[Path]:
    listed = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, cwd=REPO_ROOT, check=True
    ).stdout.splitlines()
    return [REPO_ROOT / name for name in listed if Path(name).suffix.lower() in _TEXT_SUFFIXES]


def test_the_sweep_sees_the_tree() -> None:
    """An empty listing would make the sweep below pass without reading a thing."""
    names = {p.relative_to(REPO_ROOT).as_posix() for p in _tracked_text_files()}
    assert {"README.md", "TRIGGERS.md", "scripts/render_diagram.py"} <= names


def test_the_name_appears_nowhere_but_the_refusal_and_the_route() -> None:
    """Docs, docstrings, help texts and tools: the sweep the decision asks for."""
    allowed_elsewhere = {"CHANGELOG.md", "tests/test_no_mermaid.py"}
    offenders: list[str] = []
    for path in _tracked_text_files():
        relative = path.relative_to(REPO_ROOT).as_posix()
        if relative in allowed_elsewhere or not path.is_file():
            continue
        lines = _offending_lines(path)
        if relative.startswith("scripts/"):
            lines = [line for line in lines if _SUFFIX_TUPLE not in line]
        if relative == "TRIGGERS.md":
            lines = [line for line in lines if not line.startswith("| `flowchart` |")]
        if relative.startswith("sprezzature_figures/skill/"):
            # The skill ships in the package since 2026-11-12, and routes the
            # request the same way TRIGGERS.md does: the quoted phrase someone
            # types, sent to the `flowchart` kind. Only the phrase is allowed.
            lines = [
                line for line in lines
                if '"mermaid diagram"' not in line and "`mermaid diagram`" not in line
            ]
        offenders += [f"{relative}: {line.strip()[:120]}" for line in lines]
    assert not offenders, "\n".join(offenders)


def test_triggers_routes_the_request_to_flowchart_in_one_line() -> None:
    """Somebody asking for it must still arrive here, at the right kind."""
    lines = _offending_lines(REPO_ROOT / "TRIGGERS.md")
    assert len(lines) == 1, lines
    assert lines[0].startswith("| `flowchart` |")
    assert '"mermaid diagram"' in lines[0]
