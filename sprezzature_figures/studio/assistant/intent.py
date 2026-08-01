"""
Intent analysis: turn a user's free-text request plus a dataset profile
into a structured UserIntent (plan §10.1). Never sees raw data rows.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from sprezzature_figures.core.dataset import DatasetProfile
from sprezzature_figures.core.figure_plan import UserIntent

from .client import LLMClient
from .prompts import INTENT_SYSTEM, intent_prompt


def analyze_intent(client: LLMClient, request: str, profile: DatasetProfile) -> UserIntent:
    """Ask the model what the user is trying to show.

    Parameters
    ----------
    client : LLMClient
        Real (BestEngineLLMClient) or fake, injected by the caller.
    request : str
        The user's free-text description of what they want.
    profile : DatasetProfile
        Synthetic dataset summary -- the only data context sent.

    Returns
    -------
    UserIntent
    """
    result = client.chat_text(
        intent_prompt(request, profile),
        system=INTENT_SYSTEM,
        response_model=UserIntent,
        temperature=0.1,
    )
    assert isinstance(result, UserIntent)  # chat_text guarantees this when response_model is given
    return result
