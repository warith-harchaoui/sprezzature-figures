"""
End-to-end tests for RalphEngine.apply_user_request() across all three
modes: manual (the user approves every change), assisted (Ralph proposes,
the user confirms), and autopilot (Ralph applies and self-corrects without
asking). Runs against FakeLLMClient with real rendering, so, like the
other render-touching tests in this suite, it's marked slow.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sprezzature_figures.core import (
    ColumnProfile,
    DatasetProfile,
    FigurePlan,
    allocate_iteration_dir,
    create_project,
)
from sprezzature_figures.core.operations import SetFigureKind, SetStyleOption, SetTitle
from sprezzature_figures.studio.assistant import FakeLLMClient
from sprezzature_figures.studio.assistant.schemas import EditProposal, VisualCritique, VisualIssue
from sprezzature_figures.studio.ralph.engine import RalphEngine, RalphMode
from sprezzature_figures.studio.ralph.history import RalphHistory

pytestmark = pytest.mark.slow


@pytest.fixture(autouse=True)
def _isolated_studio_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPREZZATURE_STUDIO_HOME", str(tmp_path / "studio-home"))


def _profile() -> DatasetProfile:
    return DatasetProfile(
        dataset_id="d1", fingerprint="f", source_name="t.csv", row_count=4, column_count=2,
        columns=[
            ColumnProfile(name="region", physical_dtype="object", semantic_type="categorical"),
            ColumnProfile(name="value", physical_dtype="int64", semantic_type="numeric"),
        ],
    )


def _data() -> list[dict]:
    return [
        {"region": "North", "value": 42},
        {"region": "South", "value": 28},
        {"region": "East", "value": 19},
        {"region": "West", "value": 11},
    ]


def _new_iteration() -> tuple[str, Path]:
    project_dir = create_project("engine test")
    return project_dir.name, allocate_iteration_dir(project_dir)


def _needs_fix(observation: str, repair: SetStyleOption) -> VisualCritique:
    return VisualCritique(
        verdict="needs_changes", message_alignment_score=60, readability_score=40,
        visual_hierarchy_score=60, accessibility_score=50, data_fidelity_score=90,
        issues=[VisualIssue(category="labeling", severity="high", observation=observation)],
        safe_repairs=[repair],
    )


def _run(engine: RalphEngine, plan: FigurePlan, message: str, mode: RalphMode, **kwargs):
    project_id, iteration_dir = _new_iteration()
    return engine.apply_user_request(
        plan, _data(), message,
        mode=mode, project_id=project_id, iteration_dir=iteration_dir, dataset=_profile(), **kwargs,
    )


def test_manual_mode_applies_request_and_renders_without_critique() -> None:
    proposal = EditProposal(summary="rename", operations=[SetTitle(operation_id="op1", title="Revenue")])
    result = _run(RalphEngine(client=FakeLLMClient([proposal])), FigurePlan(figure_kind="bar", title="Old"),
                  "rename", RalphMode.manual)

    assert result.plan.title == "Revenue"
    assert result.critique is None
    assert result.render.source_path.exists()
    assert result.render.preview_path.exists()
    assert result.stopped_reason == "manual_mode_no_inspection"
    assert result.rounds == 0


def test_manual_mode_holds_confirmation_required_operations() -> None:
    proposal = EditProposal(summary="switch kind", operations=[SetFigureKind(operation_id="op1", new_kind="line")])
    result = _run(RalphEngine(client=FakeLLMClient([proposal])), FigurePlan(figure_kind="bar"),
                  "switch to a line chart", RalphMode.manual)

    assert result.plan.figure_kind == "bar"  # not applied
    assert [op.operation_id for op in result.pending_confirmation] == ["op1"]
    assert result.applied_operations == []


def test_assisted_mode_applies_one_safe_repair_pass() -> None:
    proposal = EditProposal(summary="no-op", operations=[])
    repair_op = SetStyleOption(operation_id="r1", option="font_scale", value=1.4)
    critique = _needs_fix("small labels", repair_op)
    result = _run(RalphEngine(client=FakeLLMClient([proposal, critique])), FigurePlan(figure_kind="bar"),
                  "make it nicer", RalphMode.assisted)

    assert result.plan.style.font_scale == 1.4
    assert [op.operation_id for op in result.applied_operations] == ["r1"]
    assert result.rounds == 1
    assert result.stopped_reason == "assisted_single_pass"


@pytest.mark.parametrize("mode", [RalphMode.assisted, RalphMode.autopilot])
def test_mode_survives_a_failing_visual_critique(mode: RalphMode) -> None:
    # A live VLM returning junk / timing out must not crash the turn: the
    # figure still rendered, so return it with the reason noted. Same
    # graceful degradation whether we'd have applied one pass (assisted) or
    # looped (autopilot).
    proposal = EditProposal(summary="no-op", operations=[])
    client = FakeLLMClient([proposal, RuntimeError("backend returned empty JSON")])
    result = _run(RalphEngine(client=client), FigurePlan(figure_kind="bar"), "make it nicer", mode)

    assert result.render.preview_path.exists()
    assert result.critique is None
    assert result.rounds == 0
    assert result.stopped_reason == "critique_unavailable"
    assert result.notes and "inspection unavailable" in result.notes[-1].lower()


def test_manual_mode_survives_a_failing_interpretation() -> None:
    # If the text model can't interpret the request, the current figure still
    # renders unchanged and the failure is reported, not raised.
    client = FakeLLMClient([RuntimeError("model returned no JSON")])
    result = _run(RalphEngine(client=client), FigurePlan(figure_kind="bar", title="Original"),
                  "do something ambiguous", RalphMode.manual)

    assert result.render.preview_path.exists()
    assert result.applied_operations == []
    assert result.plan.title == "Original"
    assert result.notes and "could not interpret" in result.notes[0].lower()


def test_autopilot_mode_loops_until_satisfied() -> None:
    proposal = EditProposal(summary="no-op", operations=[])
    repair_op = SetStyleOption(operation_id="r1", option="font_scale", value=1.4)
    needs_fix = _needs_fix("small labels", repair_op)
    satisfied = VisualCritique(
        verdict="satisfied", message_alignment_score=90, readability_score=90,
        visual_hierarchy_score=90, accessibility_score=90, data_fidelity_score=95,
    )
    result = _run(RalphEngine(client=FakeLLMClient([proposal, needs_fix, satisfied])),
                  FigurePlan(figure_kind="bar"), "make it nicer", RalphMode.autopilot)

    assert result.critique.verdict == "satisfied"
    assert result.stopped_reason == "satisfied"
    assert result.rounds == 1
    assert [op.operation_id for op in result.applied_operations] == ["r1"]


def test_autopilot_mode_stops_on_repeated_issue_signature() -> None:
    proposal = EditProposal(summary="no-op", operations=[])
    # The repair itself doesn't fix the reported issue -- the next critique
    # reports the identical signature, so the loop should stop early.
    unhelpful_repair = SetStyleOption(operation_id="r1", option="font_scale", value=1.1)
    critique = _needs_fix("same issue every time", unhelpful_repair)
    result = _run(RalphEngine(client=FakeLLMClient([proposal, critique, critique])),
                  FigurePlan(figure_kind="bar"), "make it nicer", RalphMode.autopilot)

    assert result.stopped_reason == "repeated_issue_signature"
    assert result.rounds == 1


@pytest.mark.parametrize(
    ("preloaded_rounds", "later_critiques", "expected_rounds"),
    [
        # Cap reached within a single call: three distinct blocking critiques,
        # only MAX_AUTO_REPAIRS (2) repair passes are applied before stopping.
        (0, ["variant 1", "variant 2", "variant 3"], 2),
        # Cap enforced cumulatively across chat turns: two repair rounds are
        # already recorded on a shared history, so this call stops at round 0.
        (2, ["round three issue"], 0),
    ],
    ids=["within_one_call", "cumulative_shared_history"],
)
def test_autopilot_enforces_max_auto_repairs_cap(
    preloaded_rounds: int, later_critiques: list[str], expected_rounds: int
) -> None:
    proposal = EditProposal(summary="no-op", operations=[])
    repair_op = SetStyleOption(operation_id="r1", option="font_scale", value=1.3)

    # Distinct issue text each round so "repeated signature" doesn't stop the
    # loop early -- this test exercises the max-repairs cap specifically.
    history = RalphHistory()
    for i in range(preloaded_rounds):
        history.record(_needs_fix(f"prior round {i}", repair_op), [repair_op])

    responses = [proposal, *[_needs_fix(text, repair_op) for text in later_critiques]]
    result = _run(RalphEngine(client=FakeLLMClient(responses)), FigurePlan(figure_kind="bar"),
                  "tweak more", RalphMode.autopilot, history=history)

    assert result.stopped_reason == "max_auto_repairs_applied"
    assert result.rounds == expected_rounds
