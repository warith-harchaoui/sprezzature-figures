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
from pydantic import ValidationError

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
# repair.validate_or_repair -- the whole escalation ladder in one pass:
# valid dict passes straight through, an unparseable payload triggers exactly
# one repair round-trip, and a second failure raises with the raw response.
# --------------------------------------------------------------------------


def test_validate_or_repair_escalation() -> None:
    # (1) already-valid payload never calls the repair hook.
    passthrough = validate_or_repair({"summary": "ok"}, EditProposal, ask=lambda _p: {"summary": "unused"})
    assert passthrough.summary == "ok"

    # (2) one bad payload -> exactly one repair call, whose result is used.
    calls: list[str] = []

    def ask(repair_prompt: str):
        calls.append(repair_prompt)
        return {"summary": "fixed"}

    repaired = validate_or_repair("not json {{{", EditProposal, ask=ask)
    assert repaired.summary == "fixed"
    assert len(calls) == 1

    # (3) the repair also failing raises LLMResponseError carrying the raw text.
    with pytest.raises(LLMResponseError) as exc_info:
        validate_or_repair("still not json", EditProposal, ask=lambda _p: "also not json")
    assert exc_info.value.raw_response == "also not json"


# --------------------------------------------------------------------------
# FakeLLMClient contract (guards how tests stub the LLM everywhere else).
# --------------------------------------------------------------------------


def test_fake_client_chat_text_queue_and_recording() -> None:
    intent = UserIntent(analytical_goal="trend")
    client = FakeLLMClient([intent])

    # Queued model instance is returned as-is; once drained, the last response
    # is repeated instead of raising.
    first = client.chat_text("a", response_model=UserIntent, system="sys", temperature=0.3)
    second = client.chat_text("b", response_model=UserIntent)
    assert first is intent and second is intent

    # Every call is recorded with its full argument set.
    assert client.calls[0] == {
        "prompt": "a",
        "system": "sys",
        "response_model": UserIntent,
        "temperature": 0.3,
    }


def test_fake_client_raises_queued_exception() -> None:
    client = FakeLLMClient([FakeLLMTimeout("simulated timeout")])
    with pytest.raises(FakeLLMTimeout):
        client.chat_text("x")


def test_fake_client_chat_vision_accepts_image_bytes() -> None:
    client = FakeLLMClient(["described"])
    assert client.chat_vision("describe this", b"\x89PNG...", system="sys") == "described"


# --------------------------------------------------------------------------
# intent.analyze_intent
# --------------------------------------------------------------------------


def test_analyze_intent_returns_user_intent() -> None:
    intent = UserIntent(analytical_goal="comparison", message_to_convey="revenue by region")
    client = FakeLLMClient([intent])
    result = analyze_intent(client, "show revenue by region", _profile())
    assert result.analytical_goal == "comparison"
    assert result.message_to_convey == "revenue by region"


# --------------------------------------------------------------------------
# edit.propose_edit -- operation filtering against the real dataset columns.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "operations, expected_ids, expected_summary",
    [
        # Valid ops pass through untouched.
        ([SetTitle(operation_id="op1", title="New")], ["op1"], "rename"),
        # Ops referencing unknown columns are dropped, valid ones kept.
        (
            [
                BindColumn(operation_id="bad", role="x", columns=["nonexistent"]),
                BindColumn(operation_id="good", role="x", columns=["region"]),
            ],
            ["good"],
            "bind",
        ),
        # When every op is dropped, the summary still survives.
        ([BindColumn(operation_id="bad", role="x", columns=["ghost"])], [], "attempted bind"),
    ],
)
def test_propose_edit_filters_operations(operations, expected_ids, expected_summary) -> None:
    plan = FigurePlan(figure_kind="bar")
    proposal = EditProposal(summary=expected_summary, operations=operations)
    client = FakeLLMClient([proposal])
    result = propose_edit(client, "edit it", plan, dataset=_profile())
    assert [op.operation_id for op in result.operations] == expected_ids
    assert result.summary == expected_summary


def test_propose_edit_deduplicates_identical_operations() -> None:
    # A local model sometimes emits the same edit twice; only one survives.
    plan = FigurePlan(figure_kind="bar")
    proposal = EditProposal(
        summary="retitle",
        operations=[
            SetTitle(operation_id="a", title="Revenue"),
            SetTitle(operation_id="b", title="Revenue"),  # same content, different id
        ],
    )
    result = propose_edit(FakeLLMClient([proposal]), "retitle", plan, dataset=_profile())
    assert [op.title for op in result.operations] == ["Revenue"]


def test_set_style_option_undeclared_option_cannot_be_built() -> None:
    # An undeclared style option is now impossible to construct (option is a
    # Literal of the real StyleOptions fields), so a bad one can never reach
    # propose_edit's drop step in the first place -- a stronger guarantee than
    # dropping it after the fact.
    with pytest.raises(ValidationError):
        SetStyleOption(operation_id="bad", option="not_a_real_field", value=1)


# --------------------------------------------------------------------------
# recommend.explain_recommendations
# --------------------------------------------------------------------------


def test_explain_recommendations_filters_invented_kinds_and_skips_empty() -> None:
    defn = get_figure_definition("bar")
    intent = UserIntent(analytical_goal="comparison")

    # Hallucinated kinds are dropped, real ones survive.
    rec_set = RecommendationSet(
        recommendations=[
            FigureRecommendation(kind="bar", reason="good fit"),
            FigureRecommendation(kind="not-a-real-kind", reason="hallucinated"),
        ]
    )
    client = FakeLLMClient([rec_set])
    assert [r.kind for r in explain_recommendations(client, [defn], intent)] == ["bar"]

    # With no candidates the model is never even asked.
    empty_client = FakeLLMClient([RecommendationSet(recommendations=[])])
    assert explain_recommendations(empty_client, [], intent) == []
    assert empty_client.calls == []
