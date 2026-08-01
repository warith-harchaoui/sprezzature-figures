"""
Tests for SessionState, config.engine_status(), and the pure-logic helpers
inside data_panel/editor (upload parsing, role->column resolution, chat
summary text) -- all testable as plain Python without a running server.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from sprezzature_figures.core.dataset import ColumnProfile, DatasetProfile
from sprezzature_figures.core.figure_plan import ColumnBinding, FigurePlan
from sprezzature_figures.core.rendering import RenderResult
from sprezzature_figures.studio.assistant.schemas import VisualCritique
from sprezzature_figures.studio.components.data_panel import _load_upload
from sprezzature_figures.studio.config import engine_status
from sprezzature_figures.studio.pages.editor import _resolve_data, _summarize_result
from sprezzature_figures.studio.ralph.engine import RalphResult
from sprezzature_figures.studio.state import SessionState


def test_engine_status_never_raises_and_has_expected_keys() -> None:
    status = engine_status()
    assert set(status) == {"text_model", "vision_model", "status"}


def test_session_state_defaults_are_isolated_per_instance() -> None:
    a = SessionState()
    b = SessionState()
    assert a.session_id != b.session_id
    a.chat_log.append("mutating a's list only")  # type: ignore[arg-type]
    assert b.chat_log == []


def test_session_state_has_data_and_has_render_flags() -> None:
    state = SessionState()
    assert state.has_data is False
    assert state.has_render is False
    state.dataset_profile = DatasetProfile(
        dataset_id="d", fingerprint="f", source_name="t.csv", row_count=1, column_count=1,
        columns=[ColumnProfile(name="x", physical_dtype="int64", semantic_type="numeric")],
    )
    state.data = [{"x": 1}]
    assert state.has_data is True


@dataclass
class _FakeUploadEvent:
    name: str
    content: io.BytesIO


def test_load_upload_rejects_unsupported_extension() -> None:
    state = SessionState()
    event = _FakeUploadEvent(name="data.txt", content=io.BytesIO(b"hello"))
    error = _load_upload(state, event)
    assert error is not None and ".txt" in error


def test_load_upload_reads_valid_csv_into_state() -> None:
    state = SessionState()
    csv_bytes = b"region,value\nNorth,42\nSouth,28\n"
    event = _FakeUploadEvent(name="revenue.csv", content=io.BytesIO(csv_bytes))
    error = _load_upload(state, event)
    assert error is None
    assert state.dataset_profile is not None
    assert state.dataset_profile.row_count == 2
    assert state.data == [{"region": "North", "value": 42}, {"region": "South", "value": 28}]
    assert state.source_name == "revenue.csv"


def test_load_upload_rejects_empty_csv() -> None:
    state = SessionState()
    event = _FakeUploadEvent(name="empty.csv", content=io.BytesIO(b"region,value\n"))
    error = _load_upload(state, event)
    assert error is not None and "no data rows" in error


def test_resolve_data_maps_role_bindings_to_column_names() -> None:
    state = SessionState()
    state.data = [{"city": "Paris", "amount": 10}, {"city": "Lyon", "amount": 20}]
    plan = FigurePlan(
        figure_kind="bar",
        bindings={"region": ColumnBinding(columns=["city"]), "value": ColumnBinding(columns=["amount"])},
    )
    resolved = _resolve_data(state, plan)
    assert resolved == [{"region": "Paris", "value": 10}, {"region": "Lyon", "value": 20}]


def _render_result(tmp_path: Path) -> RenderResult:
    svg = tmp_path / "render.svg"
    png = tmp_path / "preview.png"
    svg.write_text("<svg></svg>")
    png.write_bytes(b"\x89PNG\r\n\x1a\n")
    return RenderResult(
        project_id="p1", iteration_id="0001", figure_kind="bar",
        source_path=svg, preview_path=png, mime_type="image/svg+xml", width=100, height=100,
    )


def test_summarize_result_mentions_applied_operations_and_critique(tmp_path: Path) -> None:
    plan = FigurePlan(figure_kind="bar")
    critique = VisualCritique(
        verdict="satisfied", message_alignment_score=90, readability_score=90,
        visual_hierarchy_score=90, accessibility_score=90, data_fidelity_score=90,
        concise_summary="Looks great.",
    )
    result = RalphResult(plan=plan, render=_render_result(tmp_path), critique=critique, applied_operations=[])
    summary = _summarize_result(result)
    assert "Looks great." in summary


def test_summarize_result_mentions_pending_confirmation(tmp_path: Path) -> None:
    from sprezzature_figures.core.operations import SetFigureKind

    plan = FigurePlan(figure_kind="bar")
    result = RalphResult(
        plan=plan, render=_render_result(tmp_path),
        pending_confirmation=[SetFigureKind(operation_id="op1", new_kind="line")],
    )
    summary = _summarize_result(result)
    assert "1 change(s) need your confirmation" in summary


def test_summarize_result_default_when_nothing_happened(tmp_path: Path) -> None:
    plan = FigurePlan(figure_kind="bar")
    result = RalphResult(plan=plan, render=_render_result(tmp_path))
    assert _summarize_result(result) == "No changes applied."
