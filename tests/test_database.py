"""
Tests for models/database.py

Covers _normalize_database_url() in isolation. Deliberately does not
reload models.database or touch its module-level engine/SessionLocal --
plan_log_service.py (and everything that imports PlanLog from this
module) shares that state, so mutating it here would risk destabilizing
every other test that touches the database.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.database import _normalize_database_url


def test_normalize_database_url_rewrites_postgres_scheme():
    # Neon (and most managed Postgres providers) hand out "postgres://" URLs,
    # but SQLAlchemy 2.x requires "postgresql://".
    original = "postgres://user:pass@ep-example.neon.tech/rxlogic"
    normalized = _normalize_database_url(original)

    assert normalized == "postgresql://user:pass@ep-example.neon.tech/rxlogic"


def test_normalize_database_url_leaves_other_schemes_unchanged():
    for url in ["sqlite:///:memory:", "postgresql://already-correct/db", "sqlite:///rxlogic.db"]:
        assert _normalize_database_url(url) == url