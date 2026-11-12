from __future__ import annotations

from pathlib import Path

import pytest

from services.knowledge_release import KnowledgeReleaseError
from services.reasoning_service import generate_daily_plan


def test_active_release_runtime_mode_fails_closed_without_pointer(monkeypatch, tmp_path):
    monkeypatch.setenv("RXLOGIC_KNOWLEDGE_MODE", "active_release")
    monkeypatch.setenv("RXLOGIC_KNOWLEDGE_ROOT", str(tmp_path))
    with pytest.raises(KnowledgeReleaseError, match="no active approved knowledge release"):
        generate_daily_plan([])


def test_unknown_runtime_mode_is_rejected(monkeypatch):
    monkeypatch.setenv("RXLOGIC_KNOWLEDGE_MODE", "automatic")
    with pytest.raises(ValueError, match="RXLOGIC_KNOWLEDGE_MODE"):
        generate_daily_plan([])


def test_legacy_development_mode_remains_explicitly_available(monkeypatch):
    monkeypatch.setenv("RXLOGIC_KNOWLEDGE_MODE", "legacy_development")
    # Empty input is rejected by the reasoning service after loading the
    # legacy development datasets, demonstrating this mode is still wired.
    from models.exceptions import InsufficientDataError
    with pytest.raises(InsufficientDataError):
        generate_daily_plan([])
