"""
Tests for sprezzature_figures.studio.assistant: the FakeLLMClient contract,
schema validation/repair, intent analysis, edit proposals (with operation
filtering), and recommendation reranking. No real LLM/VLM call anywhere in
this file -- everything runs against FakeLLMClient.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import pytest

from sprezzature_figures.catalog import get_figure_definition
from sprezzature_figures.core import ColumnProfile, DatasetProfile, FigurePlan, UserIntent
from sprezzature_figures.core.operations import BindColumn, SetStyleOption, SetTitle
from sprezzature_figures.studio.assistant import (
    FakeLLMClient,
    LLMResponseError,
    analyze_intent,
    explain_recommendations,
    propose_edit,
    validate_or_repair,
)
from sprezzature_figures.studio.assistant.fake_client import FakeLLMTimeout
from sprezzature_figures.studio.assistant.schemas import (
    EditProposal,
    FigureRecommendation,
    RecommendationSet,
)


def _profile() -> DatasetProfile:
    return DatasetProfile(
        dataset_id="d1",
        fingerprint="f",
        source_name="test.csv",
        row_count=10,
        column_count=2,
        columns=[
            ColumnProfile(name="region", physical_dtype="object", semantic_type="categorical"),
            ColumnProfile(name="value", physical_dtype="int64", semantic_type="numeric"),
        ],
    )


# --------------------------------------------------------------------------
# repair.validate_or_repair
# --------------------------------------------------------------------------


def test_validate_or_repair_passes_through_valid_dict() -> None:
    result = validate_or_repair({"summary": "ok"}, EditProposal, ask=lambda _p: {"summary": "unused"})
    assert result.summary == "ok"


def test_validate_or_repair_uses_repair_response_on_first_failure() -> None:
    calls = []

    def ask(repair_prompt: str):
        calls.append(repair_prompt)
        return {"summary": "fixed"}

    result = validate_or_repair("not json {{{", EditProposal, ask=ask)
    assert result.summary == "fixed"
    assert len(calls) == 1


def test_validate_or_repair_raises_llm_response_error_after_second_failure() -> None:
    with pytest.raises(LLMResponseError) as exc_info:
        validate_or_repair("still not json", EditProposal, ask=lambda _p: "also not json")
    assert exc_info.value.raw_response == "also not json"


# --------------------------------------------------------------------------
# FakeLLMClient
# --------------------------------------------------------------------------


def test_fake_client_returns_queued_model_instance_directly() -> None:
    intent = UserIntent(analytical_goal="trend", confidence=0.5)
    client = FakeLLMClient([intent])
    result = client.chat_text("x", response_model=UserIntent)
    assert result is intent


def test_fake_client_raises_queued_exception() -> None:
    client = FakeLLMClient([FakeLLMTimeout("simulated timeout")])
    with pytest.raises(FakeLLMTimeout):
        client.chat_text("x")


def test_fake_client_repeats_last_response_when_queue_exhausted() -> None:
    intent = UserIntent(analytical_goal="trend", confidence=0.5)
    client = FakeLLMClient([intent])
    first = client.chat_text("a", response_model=UserIntent)
    second = client.chat_text("b", response_model=UserIntent)
    assert first is intent and second is intent


def test_fake_client_records_calls() -> None:
    client = FakeLLMClient(["plain text response"])
    client.chat_text("hello", system="sys", temperature=0.3)
    assert client.calls == [{"prompt": "hello", "system": "sys", "response_model": None, "temperature": 0.3}]


def test_fake_client_chat_vision_accepts_image_bytes() -> None:
    client = FakeLLMClient(["described"])
    result = client.chat_vision("describe this", b"\x89PNG...", system="sys")
    assert result == "described"


# --------------------------------------------------------------------------
# intent.analyze_intent
# --------------------------------------------------------------------------


def test_analyze_intent_returns_user_intent() -> None:
    intent = UserIntent(analytical_goal="comparison", message_to_convey="revenue by region", confidence=0.9)
    client = FakeLLMClient([intent])
    result = analyze_intent(client, "show revenue by region", _profile())
    assert result.analytical_goal == "comparison"
    assert result.confidence == 0.9


# --------------------------------------------------------------------------
# edit.propose_edit
# --------------------------------------------------------------------------


def test_propose_edit_returns_valid_operations_unfiltered() -> None:
    plan = FigurePlan(figure_kind="bar", title="Old")
    proposal = EditProposal(summary="rename", operations=[SetTitle(operation_id="op1", title="New")])
    client = FakeLLMClient([proposal])
    result = propose_edit(client, "rename the title", plan, dataset=_profile())
    assert [op.operation_id for op in result.operations] == ["op1"]


def test_propose_edit_drops_operations_referencing_unknown_columns() -> None:
    plan = FigurePlan(figure_kind="bar")
    bad = BindColumn(operation_id="bad", role="x", columns=["nonexistent"])
    good = BindColumn(operation_id="good", role="x", columns=["region"])
    proposal = EditProposal(summary="bind", operations=[bad, good])
    client = FakeLLMClient([proposal])
    result = propose_edit(client, "bind x", plan, dataset=_profile())
    assert [op.operation_id for op in result.operations] == ["good"]


def test_propose_edit_drops_operations_with_undeclared_style_option() -> None:
    plan = FigurePlan(figure_kind="bar")
    bad = SetStyleOption(operation_id="bad", option="not_a_real_field", value=1)
    proposal = EditProposal(summary="style", operations=[bad])
    client = FakeLLMClient([proposal])
    result = propose_edit(client, "change style", plan, dataset=_profile())
    assert result.operations == []


def test_propose_edit_preserves_summary_even_when_all_operations_dropped() -> None:
    plan = FigurePlan(figure_kind="bar")
    bad = BindColumn(operation_id="bad", role="x", columns=["ghost"])
    proposal = EditProposal(summary="attempted bind", operations=[bad])
    client = FakeLLMClient([proposal])
    result = propose_edit(client, "bind x", plan, dataset=_profile())
    assert result.summary == "attempted bind"
    assert result.operations == []


# --------------------------------------------------------------------------
# recommend.explain_recommendations
# --------------------------------------------------------------------------


def test_explain_recommendations_drops_invented_kinds() -> None:
    defn = get_figure_definition("bar")
    intent = UserIntent(analytical_goal="comparison", confidence=0.8)
    rec_set = RecommendationSet(
        recommendations=[
            FigureRecommendation(kind="bar", reason="good fit"),
            FigureRecommendation(kind="not-a-real-kind", reason="hallucinated"),
        ]
    )
    client = FakeLLMClient([rec_set])
    result = explain_recommendations(client, [defn], intent)
    assert [r.kind for r in result] == ["bar"]


def test_explain_recommendations_returns_empty_for_no_candidates() -> None:
    intent = UserIntent(analytical_goal="comparison", confidence=0.8)
    client = FakeLLMClient([RecommendationSet(recommendations=[])])
    assert explain_recommendations(client, [], intent) == []
    assert client.calls == []  # never even asks the model with no candidates
