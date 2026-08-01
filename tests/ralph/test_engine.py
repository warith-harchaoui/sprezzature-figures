"""
End-to-end tests for RalphEngine.apply_user_request() across all three
modes (manual/assisted/autopilot), against FakeLLMClient and real
rendering (so these are marked slow, like the other render-touching
tests in this suite).

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


def test_manual_mode_applies_request_and_renders_without_critique() -> None:
    proposal = EditProposal(summary="rename", operations=[SetTitle(operation_id="op1", title="Revenue")])
    engine = RalphEngine(client=FakeLLMClient([proposal]))
    project_id, iteration_dir = _new_iteration()

    result = engine.apply_user_request(
        FigurePlan(figure_kind="bar", title="Old"), _data(), "rename",
        mode=RalphMode.manual, project_id=project_id, iteration_dir=iteration_dir, dataset=_profile(),
    )

    assert result.plan.title == "Revenue"
    assert result.critique is None
    assert result.render.source_path.exists()
    assert result.render.preview_path.exists()
    assert result.stopped_reason == "manual_mode_no_inspection"
    assert result.rounds == 0


def test_manual_mode_holds_confirmation_required_operations() -> None:
    proposal = EditProposal(summary="switch kind", operations=[SetFigureKind(operation_id="op1", new_kind="line")])
    engine = RalphEngine(client=FakeLLMClient([proposal]))
    project_id, iteration_dir = _new_iteration()

    result = engine.apply_user_request(
        FigurePlan(figure_kind="bar"), _data(), "switch to a line chart",
        mode=RalphMode.manual, project_id=project_id, iteration_dir=iteration_dir, dataset=_profile(),
    )

    assert result.plan.figure_kind == "bar"  # not applied
    assert [op.operation_id for op in result.pending_confirmation] == ["op1"]
    assert result.applied_operations == []


def test_assisted_mode_applies_one_safe_repair_pass() -> None:
    proposal = EditProposal(summary="no-op", operations=[])
    repair_op = SetStyleOption(operation_id="r1", option="font_scale", value=1.4)
    critique = VisualCritique(
        verdict="needs_changes", message_alignment_score=60, readability_score=40,
        visual_hierarchy_score=60, accessibility_score=50, data_fidelity_score=90,
        issues=[VisualIssue(category="labeling", severity="high", observation="small labels")],
        safe_repairs=[repair_op],
    )
    engine = RalphEngine(client=FakeLLMClient([proposal, critique]))
    project_id, iteration_dir = _new_iteration()

    result = engine.apply_user_request(
        FigurePlan(figure_kind="bar"), _data(), "make it nicer",
        mode=RalphMode.assisted, project_id=project_id, iteration_dir=iteration_dir, dataset=_profile(),
    )

    assert result.plan.style.font_scale == 1.4
    assert [op.operation_id for op in result.applied_operations] == ["r1"]
    assert result.rounds == 1
    assert result.stopped_reason == "assisted_single_pass"


def test_autopilot_mode_loops_until_satisfied() -> None:
    proposal = EditProposal(summary="no-op", operations=[])
    repair_op = SetStyleOption(operation_id="r1", option="font_scale", value=1.4)
    needs_fix = VisualCritique(
        verdict="needs_changes", message_alignment_score=60, readability_score=40,
        visual_hierarchy_score=60, accessibility_score=50, data_fidelity_score=90,
        issues=[VisualIssue(category="labeling", severity="high", observation="small labels")],
        safe_repairs=[repair_op],
    )
    satisfied = VisualCritique(
        verdict="satisfied", message_alignment_score=90, readability_score=90,
        visual_hierarchy_score=90, accessibility_score=90, data_fidelity_score=95,
    )
    engine = RalphEngine(client=FakeLLMClient([proposal, needs_fix, satisfied]))
    project_id, iteration_dir = _new_iteration()

    result = engine.apply_user_request(
        FigurePlan(figure_kind="bar"), _data(), "make it nicer",
        mode=RalphMode.autopilot, project_id=project_id, iteration_dir=iteration_dir, dataset=_profile(),
    )

    assert result.critique.verdict == "satisfied"
    assert result.stopped_reason == "satisfied"
    assert result.rounds == 1
    assert [op.operation_id for op in result.applied_operations] == ["r1"]


def test_autopilot_mode_stops_after_max_repairs_even_if_still_needs_changes() -> None:
    proposal = EditProposal(summary="no-op", operations=[])

    def _needs_fix(i: int) -> VisualCritique:
        return VisualCritique(
            verdict="needs_changes", message_alignment_score=60, readability_score=40,
            visual_hierarchy_score=60, accessibility_score=50, data_fidelity_score=90,
            issues=[VisualIssue(category="labeling", severity="high", observation=f"issue variant {i}")],
            safe_repairs=[SetStyleOption(operation_id=f"r{i}", option="font_scale", value=1.0 + i * 0.1)],
        )

    # Distinct issue text each round so "repeated signature" doesn't stop it
    # early -- this test wants to exercise the max-repairs cap specifically.
    responses = [proposal, _needs_fix(1), _needs_fix(2), _needs_fix(3)]
    engine = RalphEngine(client=FakeLLMClient(responses))
    project_id, iteration_dir = _new_iteration()

    result = engine.apply_user_request(
        FigurePlan(figure_kind="bar"), _data(), "make it nicer",
        mode=RalphMode.autopilot, project_id=project_id, iteration_dir=iteration_dir, dataset=_profile(),
    )

    assert result.stopped_reason == "max_auto_repairs_applied"
    assert result.rounds == 2  # exactly MAX_AUTO_REPAIRS rounds applied


def test_autopilot_mode_stops_on_repeated_issue_signature() -> None:
    proposal = EditProposal(summary="no-op", operations=[])
    same_issue = VisualIssue(category="labeling", severity="high", observation="same issue every time")
    # The repair itself doesn't fix the reported issue -- the next critique
    # reports the identical signature, so the loop should stop early.
    unhelpful_repair = SetStyleOption(operation_id="r1", option="font_scale", value=1.1)
    critique = VisualCritique(
        verdict="needs_changes", message_alignment_score=60, readability_score=40,
        visual_hierarchy_score=60, accessibility_score=50, data_fidelity_score=90,
        issues=[same_issue], safe_repairs=[unhelpful_repair],
    )
    engine = RalphEngine(client=FakeLLMClient([proposal, critique, critique]))
    project_id, iteration_dir = _new_iteration()

    result = engine.apply_user_request(
        FigurePlan(figure_kind="bar"), _data(), "make it nicer",
        mode=RalphMode.autopilot, project_id=project_id, iteration_dir=iteration_dir, dataset=_profile(),
    )

    assert result.stopped_reason == "repeated_issue_signature"
    assert result.rounds == 1


def test_autopilot_accepts_shared_history_across_calls() -> None:
    """A caller reusing one RalphHistory across chat turns should still see
    the max-repairs cap enforced cumulatively, not reset per call.
    """
    proposal = EditProposal(summary="no-op", operations=[])
    repair_op = SetStyleOption(operation_id="r1", option="font_scale", value=1.3)

    def _needs_fix(text: str) -> VisualCritique:
        return VisualCritique(
            verdict="needs_changes", message_alignment_score=60, readability_score=40,
            visual_hierarchy_score=60, accessibility_score=50, data_fidelity_score=90,
            issues=[VisualIssue(category="labeling", severity="high", observation=text)],
            safe_repairs=[repair_op],
        )

    history = RalphHistory()
    # Simulate two prior repair rounds already recorded (e.g. from an
    # earlier call), each with a distinct issue so signature-repetition
    # isn't what stops this call -- the repair-count cap should be.
    history.record(_needs_fix("round one issue"), [repair_op])
    history.record(_needs_fix("round two issue"), [repair_op])

    this_call_critique = _needs_fix("round three issue")
    engine = RalphEngine(client=FakeLLMClient([proposal, this_call_critique]))
    project_id, iteration_dir = _new_iteration()
    result = engine.apply_user_request(
        FigurePlan(figure_kind="bar"), _data(), "tweak more",
        mode=RalphMode.autopilot, project_id=project_id, iteration_dir=iteration_dir,
        dataset=_profile(), history=history,
    )
    assert result.stopped_reason == "max_auto_repairs_applied"
    assert result.rounds == 0
