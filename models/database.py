"""
Persistence layer (Layer 5, Section 4.1).

Stores an immutable, timestamped log of every generated plan -- input
medications, the resulting schedule, flagged interactions, and the
full goal-stack trace. This is what makes "rule-firing logs for
auditability" (Section 6.3) an actual queryable record, not just a
folder name.

Design boundary: this module knows nothing about services/reasoning_service.py
or the reasoning pipeline. It only knows how to store and retrieve
plain dicts/JSON. The translation between typed DailyPlan objects and
this layer happens in routes/api.py, keeping the schema boundary
(Section 6.1) intact -- the reasoning core has zero dependency on
SQLAlchemy or any persistence detail.

Uses SQLite in-memory for tests (fast, no network) and Postgres
(Neon) in production, via a single DATABASE_URL env var -- the ORM
layer is the same either way.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

def _normalize_database_url(url: str) -> str:
    """Neon (and most managed Postgres providers) hand out URLs with the
    "postgres://" scheme, but SQLAlchemy 2.x requires "postgresql://"."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


DATABASE_URL = _normalize_database_url(os.getenv("DATABASE_URL", "sqlite:///:memory:"))

if DATABASE_URL == "sqlite:///:memory:":
    # In-memory SQLite gives each thread its own separate, empty
    # database by default -- fine for a single-threaded test run,
    # but the dev server can hand requests to a different thread
    # than the one that created the tables, causing
    # "no such table" errors. StaticPool + check_same_thread=False
    # forces every thread to share the one connection/database.
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


class PlanLog(Base):
    """
    One immutable row per generate_daily_plan() call.

    Stored as JSON columns rather than a fully normalized schema on
    purpose (Section 10, Future Scope): the reasoning core's output
    shape may still evolve, and a normalized schema would need a
    migration on every schema.py change. JSON columns keep this layer
    stable while the reasoning core is actively developed; a Future
    Scope item is normalizing this once the schema is frozen.
    """

    __tablename__ = "plan_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    source: Mapped[str] = mapped_column(String(16))  # "structured" or "natural_language"
    input_medications: Mapped[list] = mapped_column(JSON)  # list[dict] -- raw Medication fields
    entries: Mapped[list] = mapped_column(JSON)             # list[dict] -- ScheduleEntry fields
    warnings: Mapped[list] = mapped_column(JSON)             # list[dict] -- Interaction fields
    goal_trace: Mapped[list] = mapped_column(JSON)           # list[str]


def init_db() -> None:
    """Creates all tables if they don't already exist. Safe to call on
    every app startup -- it's a no-op once tables exist."""
    Base.metadata.create_all(bind=engine)


def get_session() -> Session:
    """Returns a new SQLAlchemy session. Caller is responsible for
    closing it (use as a context manager: `with get_session() as s:`)."""
    return SessionLocal()