"""
FakeLLMClient: a scriptable stand-in for LLMClient so every test in this
suite runs without Ollama or any network call (plan §9.3). Real-model
tests are marked separately (pytest.ini's `llm`/`vision`/`slow` markers)
and excluded from the default run.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import json
from collections import deque
from typing import Any

from pydantic import BaseModel

from .repair import validate_or_repair


class FakeLLMTimeout(TimeoutError):
    """Raised by FakeLLMClient when scripted to simulate a timeout."""


class FakeLLMClient:
    """Queue up responses (or exceptions) and FakeLLMClient returns them in
    order, one per `chat_text`/`chat_vision` call. Each queued item is
    either:

    - a `BaseModel` instance: returned as-is when `response_model` matches
      its type, otherwise dumped to dict and run through the same
      validate-or-repair path a real client would use (so schema-mismatch
      tests exercise real validation, not a shortcut).
    - a `str`: treated as raw model output (may be invalid JSON --
      useful for testing the repair path).
    - an `Exception` instance: raised when it's this call's turn.
    - `FakeLLMTimeout`: same, but signals a timeout specifically.

    If the queue runs out, the last item is repeated indefinitely (handy
    when a test only cares about the first call but the code path makes
    more than one).
    """

    def __init__(self, responses: list[Any] | None = None) -> None:
        self._queue: deque[Any] = deque(responses or [])
        self._last: Any = None
        self.calls: list[dict[str, Any]] = []

    def _next(self) -> Any:
        if self._queue:
            self._last = self._queue.popleft()
        if self._last is None:
            raise RuntimeError("FakeLLMClient has no scripted response queued")
        return self._last

    def _respond(
        self, prompt: str, *, system: str | None, response_model: type[BaseModel] | None, temperature: float
    ) -> Any:
        self.calls.append({"prompt": prompt, "system": system, "response_model": response_model, "temperature": temperature})
        item = self._next()
        if isinstance(item, BaseException):
            raise item
        if response_model is None:
            return item if isinstance(item, str) else json.dumps(item)
        if isinstance(item, response_model):
            return item
        raw = item.model_dump() if isinstance(item, BaseModel) else item

        def _ask(_repair_prompt: str) -> Any:
            # No real repair round-trip in the fake -- surface the same
            # (still-invalid) payload so validate_or_repair's second
            # validation fails deterministically and raises LLMResponseError.
            return raw

        return validate_or_repair(raw, response_model, ask=_ask)

    def chat_text(
        self,
        prompt: str,
        *,
        system: str | None = None,
        response_model: type[BaseModel] | None = None,
        temperature: float = 0.1,
    ) -> Any:
        return self._respond(prompt, system=system, response_model=response_model, temperature=temperature)

    def chat_vision(
        self,
        prompt: str,
        image: bytes,
        *,
        system: str | None = None,
        response_model: type[BaseModel] | None = None,
        temperature: float = 0.1,
    ) -> Any:
        return self._respond(prompt, system=system, response_model=response_model, temperature=temperature)
