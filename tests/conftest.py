"""Shared pytest configuration."""

from __future__ import annotations

import pytest

_LLM_ENVIRONMENT_VARIABLES = (
    "LLM_PROVIDER",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_MODEL",
    "OLLAMA_BASE_URL",
    "OLLAMA_MODEL",
)


@pytest.fixture(autouse=True)
def _isolate_llm_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep a developer's local ``.env`` (loaded by ``app``) from changing which
    LLM backend a test exercises; tests opt in to a provider explicitly."""
    for name in _LLM_ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(name, raising=False)
