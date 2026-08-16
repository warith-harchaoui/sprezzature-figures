"""
The LLM/VLM client interface (plan §9.1) and its real implementation, a
thin wrapper over best_engine_ai_helper.llm.chat(). Nothing in this
package calls Ollama or any backend directly -- best-engine-ai-helper
resolves the model and backend, this module only shapes the call and
enforces the response schema.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

from .repair import validate_or_repair

ModelT = TypeVar("ModelT", bound=BaseModel)


@runtime_checkable
class LLMClient(Protocol):
    """What the assistant/ and ralph/ packages depend on -- never a
    concrete backend. FakeLLMClient (tests) and BestEngineLLMClient
    (production) both satisfy this.
    """

    def chat_text(
        self,
        prompt: str,
        *,
        system: str | None = None,
        response_model: type[BaseModel] | None = None,
        temperature: float = 0.1,
    ) -> str | BaseModel: ...

    def chat_vision(
        self,
        prompt: str,
        image: bytes,
        *,
        system: str | None = None,
        response_model: type[BaseModel] | None = None,
        temperature: float = 0.1,
    ) -> str | BaseModel: ...


class BestEngineLLMClient:
    """Wraps `best_engine_ai_helper.llm.chat()`. Model selection (which
    tag, which backend) is entirely best-engine-ai-helper's job -- this
    class never hardcodes a model name.
    """

    def _call(
        self,
        prompt: str,
        *,
        system: str | None,
        images: list[bytes] | None,
        response_model: type[ModelT] | None,
        temperature: float,
    ) -> str | ModelT:
        from best_engine_ai_helper.llm import chat

        json_schema = response_model.model_json_schema() if response_model is not None else None

        def _ask(p: str) -> str | dict[str, Any]:
            return chat(
                p, system=system, images=images, json_schema=json_schema, temperature=temperature
            )

        raw = _ask(prompt)
        if response_model is None:
            return raw if isinstance(raw, str) else str(raw)
        return validate_or_repair(raw, response_model, ask=_ask)

    def chat_text(
        self,
        prompt: str,
        *,
        system: str | None = None,
        response_model: type[ModelT] | None = None,
        temperature: float = 0.1,
    ) -> str | ModelT:
        return self._call(
            prompt,
            system=system,
            images=None,
            response_model=response_model,
            temperature=temperature,
        )

    def chat_vision(
        self,
        prompt: str,
        image: bytes,
        *,
        system: str | None = None,
        response_model: type[ModelT] | None = None,
        temperature: float = 0.1,
    ) -> str | ModelT:
        return self._call(
            prompt,
            system=system,
            images=[image],
            response_model=response_model,
            temperature=temperature,
        )


def default_client() -> LLMClient:
    """The production client. A thin factory so callers don't import
    BestEngineLLMClient directly and so tests can monkeypatch this one spot.
    """
    return BestEngineLLMClient()
