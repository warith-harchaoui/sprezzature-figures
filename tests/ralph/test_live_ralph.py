"""
Opt-in live VLM test: run the full Ralph loop (interpret, validate, modify,
render, critique, safe-repair) against a real model through
best-engine-ai-helper, with the rendered PNG genuinely handed to a VLM
(vision-language model, one that can look at an image as well as read
text). This is the path every default test mocks with FakeLLMClient, whose
chat_vision discards the image instead of looking at it; here the bytes
really reach the model.

Marked ``vision`` (and ``slow`` for the real render), so deselected by
default; it skips, never fails, when no backend is reachable.

Run with:  pytest -m vision

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
from sprezzature_figures.core.figure_plan import ColumnBinding
from sprezzature_figures.studio.assistant.client import default_client
from sprezzature_figures.studio.assistant.schemas import VisualCritique
from sprezzature_figures.studio.ralph.engine import RalphEngine, RalphMode
from tests.live_backend import require_live_backend

pytestmark = [pytest.mark.vision, pytest.mark.slow]


@pytest.fixture(autouse=True)
def _gate_and_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    require_live_backend()
    monkeypatch.setenv("SPREZZATURE_STUDIO_HOME", str(tmp_path / "studio-home"))


def _profile() -> DatasetProfile:
    return DatasetProfile(
        dataset_id="d1", fingerprint="f", source_name="sales.csv", row_count=4, column_count=2,
        columns=[
            ColumnProfile(name="region", physical_dtype="object", semantic_type="categorical"),
            ColumnProfile(name="value", physical_dtype="int64", semantic_type="numeric"),
        ],
    )


def _plan() -> FigurePlan:
    return FigurePlan(
        figure_kind="bar", title="Revenue by Region",
        bindings={"region": ColumnBinding(columns=["region"]), "value": ColumnBinding(columns=["value"])},
    )


def _resolved_data() -> list[dict]:
    # Keyed by the bar generator's own role names (region/value), i.e. the
    # shape _resolve_data would produce from the plan's bindings.
    return [
        {"region": "North", "value": 42},
        {"region": "South", "value": 28},
        {"region": "East", "value": 19},
        {"region": "West", "value": 11},
    ]


def test_assisted_ralph_loop_against_a_live_vlm() -> None:
    project_dir = create_project("live ralph")
    iteration_dir = allocate_iteration_dir(project_dir)

    result = RalphEngine(default_client()).apply_user_request(
        _plan(),
        _resolved_data(),
        "Make the title clearer and enlarge the labels.",
        mode=RalphMode.assisted,
        project_id=project_dir.name,
        iteration_dir=iteration_dir,
        dataset=_profile(),
    )

    # The figure actually rendered -- this always holds regardless of the
    # model, because rendering is deterministic and local.
    assert result.render is not None
    assert result.render.preview_path.exists()
    assert result.render.preview_path.stat().st_size > 100

    # A live vision model looked at the PNG. With a capable VLM it returns a
    # schema-valid critique; with a weaker local model it may fail to emit
    # valid structured output, in which case the engine degrades to no
    # critique plus an explanatory note (never a crash). Either outcome is a
    # successful *end-to-end* exercise of the loop against a live model.
    if result.critique is not None:
        assert isinstance(result.critique, VisualCritique)
        assert result.critique.verdict in {"satisfied", "needs_changes", "blocked"}
    else:
        assert result.stopped_reason == "critique_unavailable"
        assert result.notes and "inspection unavailable" in result.notes[-1].lower()
