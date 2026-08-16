"""
Shared reachability gate for the opt-in live LLM/VLM tests. A VLM, or
vision-language model, is a model that can look at an image as well as
read text; these tests carry the pytest markers ``llm`` and ``vision``.
They are deselected by default (see pyproject.toml's ``addopts``); when
explicitly selected, they skip rather than fail whenever
best-engine-ai-helper or its backend isn't actually reachable, so running
them can never break CI or a laptop with no model server.

Not a test module itself (its filename carries no ``test_`` prefix, so
pytest never collects it directly); the live test files import it.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import os
import urllib.request

import pytest


def require_live_backend() -> None:
    """Skip the calling test unless best-engine-ai-helper imports AND its
    configured backend answers a quick, cheap probe."""
    pytest.importorskip("best_engine_ai_helper", reason="best-engine-ai-helper not installed")

    backend = os.environ.get("SPREZZATURE_LLM_BACKEND", "ollama").lower()
    base_url = os.environ.get("SPREZZATURE_LLM_BASE_URL", "http://localhost:11434").rstrip("/")

    if backend != "ollama":
        # For non-Ollama backends we can't cheaply probe; let the test run and
        # rely on the client raising if it's misconfigured.
        return

    try:
        with urllib.request.urlopen(f"{base_url}/api/tags", timeout=3) as resp:
            if resp.status != 200:
                pytest.skip(f"Ollama at {base_url} returned status {resp.status}")
    except Exception as exc:  # noqa: BLE001 - any failure means "not reachable"
        pytest.skip(f"live backend not reachable at {base_url}: {exc}")
