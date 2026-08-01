"""
Validate an LLM response against a Pydantic schema, with exactly one repair
attempt on failure (plan §9.2): call, validate, on failure send a single
"fix your JSON" follow-up, validate again, and on a second failure raise a
clear error rather than continuing with a partially-valid object.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

ModelT = TypeVar("ModelT", bound=BaseModel)


class LLMResponseError(RuntimeError):
    """Raised when a model's response still doesn't match the required
    schema after one repair attempt. Always carries the original text so
    the caller can show the user what actually came back.
    """

    def __init__(self, message: str, *, raw_response: str) -> None:
        super().__init__(message)
        self.raw_response = raw_response


def _coerce(raw: str | dict[str, Any], model: type[ModelT]) -> ModelT:
    if isinstance(raw, dict):
        return model.model_validate(raw)
    if isinstance(raw, str):
        return model.model_validate_json(raw)
    raise TypeError(f"Expected str or dict from the model, got {type(raw).__name__}")


def validate_or_repair(
    raw: str | dict[str, Any],
    model: type[ModelT],
    *,
    ask: Callable[[str], str | dict[str, Any]],
) -> ModelT:
    """Validate `raw` against `model`; on failure, call `ask(repair_prompt)`
    once for a corrected response and validate that instead.

    Parameters
    ----------
    raw : str or dict
        The model's first response.
    model : type[BaseModel]
        The expected schema.
    ask : callable
        Re-invokes the LLM with a repair prompt and returns its raw
        response (str or dict), already scoped to the same
        system/temperature/image context as the original call.

    Returns
    -------
    ModelT

    Raises
    ------
    LLMResponseError
        If the response still doesn't validate after the repair attempt.
    """
    try:
        return _coerce(raw, model)
    except (ValidationError, json.JSONDecodeError, TypeError) as first_error:
        repair_prompt = (
            "Your previous response was not valid JSON matching the required schema.\n"
            f"Validation error: {first_error}\n"
            "Respond ONLY with corrected JSON matching the schema -- no prose, no markdown fences."
        )
        repaired = ask(repair_prompt)
        try:
            return _coerce(repaired, model)
        except (ValidationError, json.JSONDecodeError, TypeError) as second_error:
            raw_text = repaired if isinstance(repaired, str) else json.dumps(repaired)
            raise LLMResponseError(
                f"Model response did not match {model.__name__} schema after one repair attempt: {second_error}",
                raw_response=raw_text,
            ) from second_error
