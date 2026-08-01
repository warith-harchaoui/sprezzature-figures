"""
Tests for SessionState, config.engine_status(), and the pure-logic helpers
inside data_panel/editor (upload parsing, role->column resolution, chat
summary text) -- all testable as plain Python without a running server.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from pathlib import Path

from sprezzature_figures.core.dataset import ColumnProfile, DatasetProfile
from sprezzature_figures.core.figure_plan import ColumnBinding, FigurePlan
from sprezzature_figures.core.operations import SetFigureKind
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


def test_session_state_defaults_are_isolated_and_flags_track_content() -> None:
    a, b = SessionState(), SessionState()
    # Each instance gets its own id and its own mutable containers.
    assert a.session_id != b.session_id
    a.chat_log.append("mutating a's list only")  # type: ignore[arg-type]
    assert b.chat_log == []

    # has_data / has_render start False and flip once content is attached.
    assert a.has_data is False
    assert a.has_render is False
    a.dataset_profile = DatasetProfile(
        dataset_id="d", fingerprint="f", source_name="t.csv", row_count=1, column_count=1,
        columns=[ColumnProfile(name="x", physical_dtype="int64", semantic_type="numeric")],
    )
    a.data = [{"x": 1}]
    assert a.has_data is True


def test_load_upload_reads_valid_csv_and_rejects_bad_input() -> None:
    # A valid CSV populates the whole state (profile, rows, source name).
    state = SessionState()
    error = _load_upload(state, "revenue.csv", b"region,value\nNorth,42\nSouth,28\n")
    assert error is None
    assert state.dataset_profile is not None and state.dataset_profile.row_count == 2
    assert state.data == [{"region": "North", "value": 42}, {"region": "South", "value": 28}]
    assert state.source_name == "revenue.csv"

    # Unsupported extension and header-only (no rows) files are rejected with
    # an explanatory message rather than crashing.
    unsupported = _load_upload(SessionState(), "data.txt", b"hello")
    assert unsupported is not None and ".txt" in unsupported

    empty = _load_upload(SessionState(), "empty.csv", b"region,value\n")
    assert empty is not None and "no data rows" in empty


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


def test_summarize_result_reflects_what_happened(tmp_path: Path) -> None:
    plan = FigurePlan(figure_kind="bar")

    # Applied operations + a critique -> critique text surfaces in the summary.
    critique = VisualCritique(
        verdict="satisfied", message_alignment_score=90, readability_score=90,
        visual_hierarchy_score=90, accessibility_score=90, data_fidelity_score=90,
        concise_summary="Looks great.",
    )
    applied = RalphResult(plan=plan, render=_render_result(tmp_path), critique=critique, applied_operations=[])
    assert "Looks great." in _summarize_result(applied)

    # Pending changes -> the summary asks for confirmation.
    pending = RalphResult(
        plan=plan, render=_render_result(tmp_path),
        pending_confirmation=[SetFigureKind(operation_id="op1", new_kind="line")],
    )
    assert "1 change(s) need your confirmation" in _summarize_result(pending)

    # Nothing happened -> the default message.
    nothing = RalphResult(plan=plan, render=_render_result(tmp_path))
    assert _summarize_result(nothing) == "No changes applied."
