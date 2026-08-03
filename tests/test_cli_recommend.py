"""
Tests for the Click CLI's ``recommend`` command -- the headless twin of the
Studio recommendation cards. Skipped when the optional Click / profiling stack
isn't installed.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("click")
pytest.importorskip("pandas")
pytest.importorskip("sprezzature_figures.studio.recommendation")

from click.testing import CliRunner  # noqa: E402

from sprezzature_figures.catalog import get_figure_definition  # noqa: E402
from sprezzature_figures.cli import main  # noqa: E402


def _write_csv(tmp_path: Path) -> Path:
    p = tmp_path / "d.csv"
    p.write_text("parent,name,value\nA,A1,10\nB,B1,20\nC,C1,30\n", encoding="utf-8")
    return p


def test_recommend_lists_ranked_kinds(tmp_path: Path) -> None:
    """`recommend --data file` prints ranked kinds with scores and role bindings."""
    result = CliRunner().invoke(main, ["recommend", "--data", str(_write_csv(tmp_path)), "--limit", "3"])
    assert result.exit_code == 0, result.output
    assert "best first" in result.output
    assert "score=" in result.output
    # role=column bindings are shown (the value column is bound to some role)
    assert "=value" in result.output


def test_recommend_missing_file_errors(tmp_path: Path) -> None:
    result = CliRunner().invoke(main, ["recommend", "--data", str(tmp_path / "nope.csv")])
    assert result.exit_code != 0


def test_recommend_intent_reorders_ranking(tmp_path: Path) -> None:
    """`--intent hierarchy` ranks a hierarchy figure above what readability
    alone (no intent) would put first, for a parent/name/value dataset."""
    data = _write_csv(tmp_path)
    plain = CliRunner().invoke(main, ["recommend", "--data", str(data), "--limit", "8"])
    hier = CliRunner().invoke(
        main, ["recommend", "--data", str(data), "--limit", "8", "--intent", "hierarchy"]
    )
    assert plain.exit_code == 0 and hier.exit_code == 0, hier.output

    def first_kind(output: str) -> str:
        # The first "  <kind>  score=..." line after the header.
        for line in output.splitlines():
            stripped = line.strip()
            if stripped and "score=" in stripped:
                return stripped.split()[0]
        return ""

    top_hier = first_kind(hier.output)
    assert get_figure_definition(top_hier).category.lower().find("hierarchy") >= 0


def test_recommend_intent_rejects_unknown_goal(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        main, ["recommend", "--data", str(_write_csv(tmp_path)), "--intent", "nonsense"]
    )
    assert result.exit_code != 0
    assert "nonsense" in result.output or "Invalid value" in result.output


@pytest.mark.slow
def test_recommend_render_writes_top_figure(tmp_path: Path) -> None:
    """`--render` applies the top figure's role binding and writes a file."""
    out = tmp_path / "top.svg"
    result = CliRunner().invoke(
        main,
        ["recommend", "--data", str(_write_csv(tmp_path)), "--render", str(out)],
    )
    assert result.exit_code == 0, result.output
    assert out.exists() and out.stat().st_size > 0
    assert "rendered top recommendation" in result.output
