"""
Opt-in live text-LLM tests: exercise the real BestEngineLLMClient path
(best_engine_ai_helper.llm.chat), the actual network call to a language
model that every default test run replaces with FakeLLMClient, a stand-in
that returns canned answers instead. "Opt-in" means these carry the pytest
marker ``llm``, so a plain ``pytest`` run skips them automatically; when
selected on purpose but no model backend is reachable, a test here skips
rather than fails, so a laptop with no model running never turns red for
the wrong reason.

Run with:  pytest -m llm

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import pytest

from sprezzature_figures.core import ColumnProfile, DatasetProfile, FigurePlan
from sprezzature_figures.core.figure_plan import ColumnBinding, UserIntent
from sprezzature_figures.studio.assistant.client import default_client
from sprezzature_figures.studio.assistant.edit import propose_edit
from sprezzature_figures.studio.assistant.intent import analyze_intent
from sprezzature_figures.studio.assistant.schemas import EditProposal
from tests.live_backend import require_live_backend

pytestmark = pytest.mark.llm


@pytest.fixture(autouse=True)
def _gate() -> None:
    require_live_backend()


def _profile() -> DatasetProfile:
    return DatasetProfile(
        dataset_id="d1", fingerprint="f", source_name="sales.csv", row_count=4, column_count=2,
        columns=[
            ColumnProfile(name="region", physical_dtype="object", semantic_type="categorical"),
            ColumnProfile(name="value", physical_dtype="int64", semantic_type="numeric"),
        ],
    )


def test_analyze_intent_returns_validated_user_intent() -> None:
    intent = analyze_intent(default_client(), "Compare revenue across regions", _profile())
    # The point isn't a specific goal string -- it's that a real model's JSON
    # round-tripped through the schema into a valid UserIntent.
    assert isinstance(intent, UserIntent)
    assert intent.analytical_goal


def test_propose_edit_returns_validated_edit_proposal() -> None:
    plan = FigurePlan(
        figure_kind="bar", title="Revenue",
        bindings={"category": ColumnBinding(columns=["region"]), "value": ColumnBinding(columns=["value"])},
    )
    proposal = propose_edit(
        default_client(),
        "Change the title to 'Quarterly Revenue by Region'",
        plan,
        dataset=_profile(),
    )
    assert isinstance(proposal, EditProposal)
    # Every operation the model emitted survived column/option validation
    # (propose_edit strips invalid ones), so whatever remains is applicable.
    for op in proposal.operations:
        assert op.operation_type
